"""Database schema initialization."""

from app.constants import (
    EMPLOYMENT_STATUSES,
    DESIGNATIONS_BY_DEPARTMENT,
    MAX_ANNUAL_GROSS_BASE_SALARY,
    SUPPORTED_CURRENCIES,
)
from app.database import connect


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
            columns = connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'employees'"
            ).fetchall() if connection.dialect == "postgresql" else connection.execute(
                "PRAGMA table_info(employees)"
            ).fetchall()
            column_names = {row["column_name"] if connection.dialect == "postgresql" else row["name"] for row in columns}
            if "designation" not in column_names:
                connection.execute("ALTER TABLE employees ADD COLUMN designation TEXT")
            for department, designations in DESIGNATIONS_BY_DEPARTMENT.items():
                for index, designation in enumerate(designations):
                    connection.execute(
                        "UPDATE employees SET designation = ? WHERE department = ? "
                        "AND CAST(SUBSTR(employee_id, 5) AS INTEGER) % 5 = ? "
                        "AND (designation IS NULL OR length(trim(designation)) = 0)",
                        (designation, department, index),
                    )
            connection.execute(
                "UPDATE employees SET designation = 'Employee' "
                "WHERE designation IS NULL OR length(trim(designation)) = 0"
            )
            if connection.dialect == "postgresql":
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
