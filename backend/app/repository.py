"""Parameterized employee persistence operations."""

from app.constants import (
    DESIGNATIONS_BY_DEPARTMENT,
    EMPLOYMENT_STATUSES,
    PAGE_SIZE,
    SUPPORTED_CURRENCIES,
)
from app.database import DatabaseConnection
from app.schemas import (
    CurrencySalarySummary,
    EmployeeCreate,
    EmployeeFilterOptions,
    EmployeeRead,
    EmployeeUpdate,
    SalaryGroupSummary,
)

_EMPLOYEE_SELECT = """
SELECT
    employee_id,
    name,
    department,
    designation,
    country,
    employment_status,
    annual_gross_base_salary,
    currency
FROM employees
WHERE employee_id = ?
"""


class DuplicateEmployeeError(Exception):
    """Raised when an employee ID cannot be generated after retries."""


def _next_employee_id(connection: DatabaseConnection) -> str:
    """Generate the next employee ID from the highest existing numeric ID."""
    row = connection.execute(
        """SELECT MAX(CAST(SUBSTR(employee_id, 5) AS INTEGER)) AS highest_id
           FROM employees"""
    ).fetchone()
    highest = row["highest_id"]
    return f"EMP-{(highest or 0) + 1:05d}"


def get_next_employee_id(connection: DatabaseConnection) -> str:
    """Return the next ID preview based on the highest numeric ID part."""
    return _next_employee_id(connection)


def create_employee(
    connection: DatabaseConnection, employee: EmployeeCreate
) -> EmployeeRead:
    """Insert an employee and return the validated record."""
    with connection:
        for attempt in range(3):
            employee_id = _next_employee_id(connection)
            cursor = connection.execute(
                """
                INSERT INTO employees (
                    employee_id,
                    name,
                    department,
                    designation,
                    country,
                    employment_status,
                    annual_gross_base_salary,
                    currency
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(employee_id) DO NOTHING
                """,
                (
                    employee_id,
                    employee.name,
                    employee.department,
                    employee.designation,
                    employee.country,
                    employee.employment_status,
                    employee.annual_gross_base_salary,
                    employee.currency,
                ),
            )
            if cursor.rowcount:
                return EmployeeRead.model_validate(
                    employee.model_dump() | {"employee_id": employee_id}
                )
        raise DuplicateEmployeeError("Could not generate a unique employee ID")


def get_employee_by_id(
    connection: DatabaseConnection, employee_id: str
) -> EmployeeRead | None:
    """Fetch an employee by ID, returning None when no record matches."""
    row = connection.execute(_EMPLOYEE_SELECT, (employee_id,)).fetchone()

    if row is None:
        return None
    return EmployeeRead.model_validate(dict(row))


def update_employee(
    connection: DatabaseConnection,
    employee_id: str,
    data: EmployeeUpdate,
) -> EmployeeRead | None:
    """Replace editable fields for an employee, or return None if absent."""
    with connection:
        cursor = connection.execute(
            """
            UPDATE employees
            SET
                name = ?,
                department = ?,
                designation = ?,
                country = ?,
                employment_status = ?,
                annual_gross_base_salary = ?,
                currency = ?
            WHERE employee_id = ?
            """,
            (
                data.name,
                data.department,
                data.designation,
                data.country,
                data.employment_status,
                data.annual_gross_base_salary,
                data.currency,
                employee_id,
            ),
        )
        if cursor.rowcount == 0:
            return None

        row = connection.execute(_EMPLOYEE_SELECT, (employee_id,)).fetchone()
        if row is None:
            return None
        return EmployeeRead.model_validate(dict(row))


def delete_employee(connection: DatabaseConnection, employee_id: str) -> bool:
    """Delete an employee and report whether a row was removed."""
    with connection:
        cursor = connection.execute(
            "DELETE FROM employees WHERE employee_id = ?",
            (employee_id,),
        )
    return cursor.rowcount > 0


def list_employees(
    connection: DatabaseConnection,
    *,
    page: int,
    search: str | None = None,
    country: str | None = None,
    department: str | None = None,
    employment_status: str | None = None,
    currency: str | None = None,
    min_salary: float | None = None,
    max_salary: float | None = None,
) -> tuple[list[EmployeeRead], int]:
    """Return one fixed-size employee page and the total matching count."""
    conditions: list[str] = []
    parameters: list[object] = []

    if search:
        conditions.append(
            "(LOWER(name) LIKE LOWER(?) ESCAPE '!' "
            "OR LOWER(employee_id) LIKE LOWER(?) ESCAPE '!')"
        )
        escaped_search = search.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        parameters.extend((f"%{escaped_search}%", f"{escaped_search}%"))
    if country is not None:
        conditions.append("country = ?")
        parameters.append(country)
    if department is not None:
        conditions.append("department = ?")
        parameters.append(department)
    if employment_status is not None:
        conditions.append("employment_status = ?")
        parameters.append(employment_status)
    if currency is not None:
        conditions.append("currency = ?")
        parameters.append(currency)
    if min_salary is not None:
        conditions.append("annual_gross_base_salary >= ?")
        parameters.append(min_salary)
    if max_salary is not None:
        conditions.append("annual_gross_base_salary <= ?")
        parameters.append(max_salary)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    total = connection.execute(
        f"SELECT COUNT(*) AS total_count FROM employees {where_clause}",
        parameters,
    ).fetchone()["total_count"]
    rows = connection.execute(
        f"""
        SELECT
            employee_id,
            name,
            department,
            designation,
            country,
            employment_status,
            annual_gross_base_salary,
            currency
        FROM employees
        {where_clause}
        ORDER BY employee_id
        LIMIT ? OFFSET ?
        """,
        (*parameters, PAGE_SIZE, (page - 1) * PAGE_SIZE),
    ).fetchall()

    return [EmployeeRead.model_validate(dict(row)) for row in rows], total


_DASHBOARD_GROUP_COLUMNS = {
    "department": "department",
    "country": "country",
}


def _dashboard_filter_clause(
    *, department: str | None, country: str | None, employment_status: str | None
) -> tuple[str, list[str]]:
    """Build parameterized equality filters shared by dashboard aggregates."""
    conditions: list[str] = []
    parameters: list[str] = []
    for column, value in (
        ("department", department),
        ("country", country),
        ("employment_status", employment_status),
    ):
        if value is not None:
            conditions.append(f"{column} = ?")
            parameters.append(value)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, parameters


def get_salary_dashboard(
    connection: DatabaseConnection,
    *,
    department: str | None = None,
    country: str | None = None,
    employment_status: str | None = None,
) -> tuple[list[CurrencySalarySummary], int]:
    """Return filtered salary statistics per currency and filtered headcount."""
    where_clause, parameters = _dashboard_filter_clause(
        department=department,
        country=country,
        employment_status=employment_status,
    )
    total_headcount = connection.execute(
        f"SELECT COUNT(*) AS total_headcount FROM employees {where_clause}",
        parameters,
    ).fetchone()["total_headcount"]
    rows = connection.execute(
        f"""
        SELECT
            currency,
            COUNT(*) AS headcount,
            ROUND(AVG(CAST(annual_gross_base_salary AS NUMERIC)), 2)
                AS average_annual_gross_base_salary,
            MIN(annual_gross_base_salary) AS minimum_annual_gross_base_salary,
            MAX(annual_gross_base_salary) AS maximum_annual_gross_base_salary
        FROM employees {where_clause}
        GROUP BY currency
        ORDER BY currency
        """,
        parameters,
    ).fetchall()
    summaries = [
        CurrencySalarySummary(
            currency=row["currency"],
            headcount=row["headcount"],
            average_annual_gross_base_salary=row[
                "average_annual_gross_base_salary"
            ],
            minimum_annual_gross_base_salary=row[
                "minimum_annual_gross_base_salary"
            ],
            maximum_annual_gross_base_salary=row[
                "maximum_annual_gross_base_salary"
            ],
        )
        for row in rows
    ]
    return summaries, total_headcount


def get_salary_group_summaries(
    connection: DatabaseConnection,
    *,
    group_by: str,
    department: str | None = None,
    country: str | None = None,
    employment_status: str | None = None,
) -> list[SalaryGroupSummary]:
    """Return salary statistics grouped by a whitelisted field and currency."""
    group_column = _DASHBOARD_GROUP_COLUMNS.get(group_by)
    if group_column is None:
        raise ValueError("Unsupported salary summary grouping")
    where_clause, parameters = _dashboard_filter_clause(
        department=department,
        country=country,
        employment_status=employment_status,
    )
    rows = connection.execute(
        f"""
        SELECT
            {group_column} AS group_name,
            currency,
            COUNT(*) AS headcount,
            ROUND(AVG(CAST(annual_gross_base_salary AS NUMERIC)), 2)
                AS average_annual_gross_base_salary,
            MIN(annual_gross_base_salary) AS minimum_annual_gross_base_salary,
            MAX(annual_gross_base_salary) AS maximum_annual_gross_base_salary
        FROM employees {where_clause}
        GROUP BY {group_column}, currency
        ORDER BY {group_column}, currency
        """,
        parameters,
    ).fetchall()

    grouped: dict[str, list[CurrencySalarySummary]] = {}
    headcounts: dict[str, int] = {}
    for row in rows:
        name = row["group_name"]
        grouped.setdefault(name, []).append(
            CurrencySalarySummary(
                currency=row["currency"],
                headcount=row["headcount"],
                average_annual_gross_base_salary=row[
                    "average_annual_gross_base_salary"
                ],
                minimum_annual_gross_base_salary=row[
                    "minimum_annual_gross_base_salary"
                ],
                maximum_annual_gross_base_salary=row[
                    "maximum_annual_gross_base_salary"
                ],
            )
        )
        headcounts[name] = headcounts.get(name, 0) + row["headcount"]
    return [
        SalaryGroupSummary(name=name, headcount=headcounts[name], currencies=currencies)
        for name, currencies in grouped.items()
    ]


def get_employee_filter_options(
    connection: DatabaseConnection,
) -> EmployeeFilterOptions:
    """Return distinct database values and supported statuses and currencies."""
    countries = connection.execute(
        "SELECT DISTINCT country FROM employees ORDER BY country"
    ).fetchall()
    departments = connection.execute(
        "SELECT DISTINCT department FROM employees ORDER BY department"
    ).fetchall()
    return EmployeeFilterOptions(
        countries=[row["country"] for row in countries],
        departments=[row["department"] for row in departments],
        employment_statuses=list(EMPLOYMENT_STATUSES),
        currencies=list(SUPPORTED_CURRENCIES),
        designations_by_department={
            department: list(designations)
            for department, designations in DESIGNATIONS_BY_DEPARTMENT.items()
        },
    )
