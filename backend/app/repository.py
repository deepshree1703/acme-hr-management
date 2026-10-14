"""Parameterized employee persistence operations."""

import sqlite3

from app.constants import PAGE_SIZE
from app.schemas import (
    CurrencySalarySummary,
    EmployeeCreate,
    EmployeeRead,
    EmployeeUpdate,
)

_EMPLOYEE_SELECT = """
SELECT
    employee_id,
    name,
    department,
    country,
    employment_status,
    annual_gross_base_salary,
    currency
FROM employees
WHERE employee_id = ?
"""


class DuplicateEmployeeError(Exception):
    """Raised when an employee ID is already present in the database."""


def create_employee(
    connection: sqlite3.Connection, employee: EmployeeCreate
) -> EmployeeRead:
    """Insert an employee and return the validated record."""
    with connection:
        cursor = connection.execute(
            """
            INSERT INTO employees (
                employee_id,
                name,
                department,
                country,
                employment_status,
                annual_gross_base_salary,
                currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_id) DO NOTHING
            """,
            (
                employee.employee_id,
                employee.name,
                employee.department,
                employee.country,
                employee.employment_status,
                employee.annual_gross_base_salary,
                employee.currency,
            ),
        )
        if cursor.rowcount == 0:
            raise DuplicateEmployeeError(
                f"Employee ID {employee.employee_id} already exists"
            )

    return EmployeeRead.model_validate(employee.model_dump())


def get_employee_by_id(
    connection: sqlite3.Connection, employee_id: str
) -> EmployeeRead | None:
    """Fetch an employee by ID, returning None when no record matches."""
    row = connection.execute(_EMPLOYEE_SELECT, (employee_id,)).fetchone()

    if row is None:
        return None
    return EmployeeRead.model_validate(dict(row))


def update_employee(
    connection: sqlite3.Connection,
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
                country = ?,
                employment_status = ?,
                annual_gross_base_salary = ?,
                currency = ?
            WHERE employee_id = ?
            """,
            (
                data.name,
                data.department,
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


def delete_employee(connection: sqlite3.Connection, employee_id: str) -> bool:
    """Delete an employee and report whether a row was removed."""
    with connection:
        cursor = connection.execute(
            "DELETE FROM employees WHERE employee_id = ?",
            (employee_id,),
        )
    return cursor.rowcount > 0


def list_employees(
    connection: sqlite3.Connection,
    *,
    page: int,
    search: str | None = None,
    country: str | None = None,
    department: str | None = None,
    employment_status: str | None = None,
) -> tuple[list[EmployeeRead], int]:
    """Return one fixed-size employee page and the total matching count."""
    conditions: list[str] = []
    parameters: list[str] = []

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

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    total = connection.execute(
        f"SELECT COUNT(*) FROM employees {where_clause}",
        parameters,
    ).fetchone()[0]
    rows = connection.execute(
        f"""
        SELECT
            employee_id,
            name,
            department,
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


def get_salary_dashboard(
    connection: sqlite3.Connection,
) -> tuple[list[CurrencySalarySummary], int]:
    """Return per-currency salary aggregates and the overall employee count."""
    rows = connection.execute(
        """
        SELECT
            currency,
            COUNT(*) AS headcount,
            ROUND(AVG(annual_gross_base_salary), 2)
                AS average_annual_gross_base_salary,
            (SELECT COUNT(*) FROM employees) AS total_headcount
        FROM employees
        GROUP BY currency
        ORDER BY currency
        """
    ).fetchall()
    summaries = [
        CurrencySalarySummary(
            currency=row["currency"],
            headcount=row["headcount"],
            average_annual_gross_base_salary=row[
                "average_annual_gross_base_salary"
            ],
        )
        for row in rows
    ]
    total_headcount = rows[0]["total_headcount"] if rows else 0
    return summaries, total_headcount
