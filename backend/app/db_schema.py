"""Database schema initialization."""

from app.constants import (
    EMPLOYMENT_STATUSES,
    DESIGNATIONS_BY_DEPARTMENT,
    MAX_ANNUAL_GROSS_BASE_SALARY,
    SUPPORTED_CURRENCIES,
)
from app.database import DatabaseConnection, connect

_MIGRATION_BATCH_SIZE = 500


def _designation_column_rows(connection: DatabaseConnection):
    """Add the designation column where needed and return its metadata."""
    if connection.dialect == "postgresql":
        connection.execute(
            "ALTER TABLE employees ADD COLUMN IF NOT EXISTS designation TEXT"
        )
        return connection.execute(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'employees'"
        ).fetchall()

    columns = connection.execute("PRAGMA table_info(employees)").fetchall()
    if not any(column["name"] == "designation" for column in columns):
        try:
            connection.execute("ALTER TABLE employees ADD COLUMN designation TEXT")
        except Exception as exc:
            # SQLite has no ADD COLUMN IF NOT EXISTS; concurrent initializers may race.
            if "duplicate column name" not in str(exc).lower():
                raise
        columns = connection.execute("PRAGMA table_info(employees)").fetchall()
    return columns


def _backfill_designations(connection: DatabaseConnection) -> None:
    """Fill only missing designations using employee IDs and department lists."""
    rows = connection.execute(
        "SELECT employee_id, department FROM employees "
        "WHERE designation IS NULL OR trim(designation) = ''"
    ).fetchall()
    if not rows:
        return

    updates: list[tuple[str, str]] = []
    for row in rows:
        choices = DESIGNATIONS_BY_DEPARTMENT.get(row["department"])
        designation = choices[int(row["employee_id"][4:]) % 5] if choices else "Employee"
        updates.append((designation, row["employee_id"]))
    for offset in range(0, len(updates), _MIGRATION_BATCH_SIZE):
        connection.executemany(
            "UPDATE employees SET designation = ? WHERE employee_id = ?",
            updates[offset : offset + _MIGRATION_BATCH_SIZE],
        )


def init_db() -> None:
    """Create the employees table and its directory filter indexes if absent."""
    allowed_statuses = ", ".join(f"'{status}'" for status in EMPLOYMENT_STATUSES)
    allowed_currencies = ", ".join(f"'{currency}'" for currency in SUPPORTED_CURRENCIES)

    connection = connect()
    try:
        with connection:
            employee_id_check = (
                "employee_id ~ '^EMP-[0-9]{5,}$'"
                if connection.dialect == "postgresql"
                else "length(employee_id) >= 9 AND substr(employee_id, 1, 4) = 'EMP-' "
                "AND substr(employee_id, 5) NOT GLOB '*[^0-9]*'"
            )
            salary_type = (
                "DOUBLE PRECISION" if connection.dialect == "postgresql" else "REAL"
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS employees (
                    employee_id TEXT PRIMARY KEY CHECK ({employee_id_check}),
                    name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    designation TEXT NOT NULL CHECK (length(trim(designation)) > 0),
                    country TEXT NOT NULL,
                    employment_status TEXT NOT NULL
                        CHECK (employment_status IN ({allowed_statuses})),
                    annual_gross_base_salary {salary_type} NOT NULL
                        CHECK (annual_gross_base_salary >= 0 AND
                            annual_gross_base_salary <= {MAX_ANNUAL_GROSS_BASE_SALARY}),
                    currency TEXT NOT NULL
                        CHECK (currency IN ({allowed_currencies}))
                )
                """
            )
            columns = _designation_column_rows(connection)
            _backfill_designations(connection)
            if connection.dialect == "postgresql" and any(
                row["column_name"] == "designation" and row["is_nullable"] == "YES"
                for row in columns
            ):
                connection.execute(
                    "ALTER TABLE employees ALTER COLUMN designation SET NOT NULL"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_employees_country ON employees (country)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_employees_department ON employees (department)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_employees_employment_status "
                "ON employees (employment_status)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_employees_currency ON employees (currency)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_employees_currency_salary "
                "ON employees (currency, annual_gross_base_salary)"
            )
    finally:
        connection.close()
