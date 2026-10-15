"""Employee create and fetch routes."""

import math
import re
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.constants import EMPLOYMENT_STATUSES, PAGE_SIZE
from app.database import DatabaseConnection, get_connection
from app.repository import (
    DuplicateEmployeeError,
    create_employee as repository_create_employee,
    delete_employee as repository_delete_employee,
    get_employee_by_id as repository_get_employee_by_id,
    get_employee_filter_options as repository_get_employee_filter_options,
    get_next_employee_id as repository_get_next_employee_id,
    list_employees as repository_list_employees,
    update_employee as repository_update_employee,
)
from app.schemas import (
    EmployeeCreate,
    EmployeeFilterOptions,
    EmployeeListResponse,
    EmployeeRead,
    EmployeeUpdate,
)

router = APIRouter(prefix="/employees", tags=["employees"])
_STATUS_PATTERN = rf"^(?:{'|'.join(re.escape(value) for value in EMPLOYMENT_STATUSES)})$"


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    search: str | None = None,
    country: str | None = None,
    department: str | None = None,
    employment_status: str | None = Query(default=None, pattern=_STATUS_PATTERN),
    page: int = Query(default=1, ge=1),
    connection: DatabaseConnection = Depends(get_connection),
) -> EmployeeListResponse:
    """List employees using filters and fixed-size backend pagination."""
    items, total = repository_list_employees(
        connection,
        page=page,
        search=search,
        country=country,
        department=department,
        employment_status=employment_status,
    )
    return EmployeeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=PAGE_SIZE,
        total_pages=math.ceil(total / PAGE_SIZE),
    )


@router.get("/filters", response_model=EmployeeFilterOptions)
def employee_filter_options(
    connection: DatabaseConnection = Depends(get_connection),
) -> EmployeeFilterOptions:
    """Return options used by the employee list filters."""
    return repository_get_employee_filter_options(connection)


@router.get("/next-id")
def next_employee_id(
    connection: DatabaseConnection = Depends(get_connection),
) -> dict[str, str]:
    """Preview the ID that would be generated for the next employee."""
    return {"employee_id": repository_get_next_employee_id(connection)}


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create_employee(
    employee: EmployeeCreate,
    connection: DatabaseConnection = Depends(get_connection),
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
    connection: DatabaseConnection = Depends(get_connection),
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
    connection: DatabaseConnection = Depends(get_connection),
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
    connection: DatabaseConnection = Depends(get_connection),
) -> None:
    """Delete an employee record."""
    deleted = repository_delete_employee(connection, employee_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
