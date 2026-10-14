"""Employee create and fetch routes."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_connection
from app.repository import (
    DuplicateEmployeeError,
    create_employee as repository_create_employee,
    delete_employee as repository_delete_employee,
    get_employee_by_id as repository_get_employee_by_id,
    update_employee as repository_update_employee,
)
from app.schemas import EmployeeCreate, EmployeeRead, EmployeeUpdate

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


@router.put("/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: str,
    employee: EmployeeUpdate,
    connection: sqlite3.Connection = Depends(get_connection),
) -> EmployeeRead:
    """Replace an employee's editable fields."""
    updated_employee = repository_update_employee(connection, employee_id, employee)
    if updated_employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    return updated_employee


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(
    employee_id: str,
    connection: sqlite3.Connection = Depends(get_connection),
) -> None:
    """Delete an employee record."""
    deleted = repository_delete_employee(connection, employee_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
