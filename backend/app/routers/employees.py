"""Employee create and fetch routes."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_connection
from app.repository import (
    DuplicateEmployeeError,
    create_employee as repository_create_employee,
    get_employee_by_id as repository_get_employee_by_id,
)
from app.schemas import EmployeeCreate, EmployeeRead

router = APIRouter(prefix="/employees", tags=["employees"])


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create_employee(
    employee: EmployeeCreate,
    connection: sqlite3.Connection = Depends(get_connection),
) -> EmployeeRead:
    """Create an employee record."""
    try:
        return repository_create_employee(connection, employee)
    except DuplicateEmployeeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get("/{employee_id}", response_model=EmployeeRead)
def get_employee(
    employee_id: str,
    connection: sqlite3.Connection = Depends(get_connection),
) -> EmployeeRead:
    """Fetch an employee by ID."""
    employee = repository_get_employee_by_id(connection, employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    return employee
