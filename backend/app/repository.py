"""Parameterized employee persistence operations."""

import sqlite3

from app.schemas import EmployeeCreate, EmployeeRead


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
    row = connection.execute(
        """
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
        """,
        (employee_id,),
    ).fetchone()

    if row is None:
        return None
    return EmployeeRead.model_validate(dict(row))
