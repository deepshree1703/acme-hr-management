"""Database schema initialization."""

from app.constants import (
    EMPLOYMENT_STATUSES,
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
    finally:
        connection.close()
