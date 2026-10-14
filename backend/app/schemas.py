"""Pydantic models for employee data validation."""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants import EMPLOYMENT_STATUSES, SUPPORTED_CURRENCIES


class EmployeeFields(BaseModel):
    """Employee fields shared by create, update, and read models."""

    model_config = ConfigDict(extra="forbid")

    name: str
    department: str
    country: str
    employment_status: str
    annual_gross_base_salary: float = Field(ge=0, allow_inf_nan=False)
    currency: str

    @field_validator("name", "department", "country")
    @classmethod
    def trim_nonblank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank")
        return value

    @field_validator("employment_status")
    @classmethod
    def validate_employment_status(cls, value: str) -> str:
        if value not in EMPLOYMENT_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(EMPLOYMENT_STATUSES)}")
        return value

    @field_validator("annual_gross_base_salary", mode="before")
    @classmethod
    def require_numeric_salary(cls, value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Salary must be a number")
        return value

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Currency must be one of: {', '.join(SUPPORTED_CURRENCIES)}")
        return value


class EmployeeCreate(EmployeeFields):
    """Validated employee data for creating a record."""

    employee_id: str

    @field_validator("employee_id")
    @classmethod
    def validate_employee_id(cls, value: str) -> str:
        if re.fullmatch(r"EMP-\d{5}", value) is None:
            raise ValueError("Employee ID must match EMP-00001 format")
        return value


class EmployeeUpdate(EmployeeFields):
    """Validated replacement employee data; employee_id cannot be changed."""


class EmployeeRead(EmployeeCreate):
    """Validated employee data returned by the API."""


class EmployeeListResponse(BaseModel):
    """Paginated employee list and match metadata."""

    items: list[EmployeeRead]
    total: int
    page: int
    page_size: int
    total_pages: int
