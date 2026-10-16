"""Pydantic models for employee data validation."""

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.constants import (
    DESIGNATIONS_BY_DEPARTMENT,
    EMPLOYEE_ID_PATTERN,
    EMPLOYMENT_STATUSES,
    MAX_ANNUAL_GROSS_BASE_SALARY,
    SUPPORTED_CURRENCIES,
)


class EmployeeFields(BaseModel):
    """Employee fields shared by create, update, and read models."""

    model_config = ConfigDict(extra="forbid")

    name: str
    department: str
    designation: str
    country: str
    employment_status: str
    annual_gross_base_salary: float = Field(allow_inf_nan=False)
    currency: str

    @field_validator("name", "department", "designation", "country")
    @classmethod
    def trim_nonblank_text(cls, value: str) -> str:
        """Trim text fields and reject values that are blank after trimming."""
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank")
        return value

    @field_validator("employment_status")
    @classmethod
    def validate_employment_status(cls, value: str) -> str:
        """Ensure the employment status is one of the supported values."""
        if value not in EMPLOYMENT_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(EMPLOYMENT_STATUSES)}")
        return value

    @field_validator("annual_gross_base_salary", mode="before")
    @classmethod
    def require_numeric_salary(cls, value: Any) -> Any:
        """Validate that salary is finite, nonnegative, and has at most two decimals."""
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError("Salary must be a number")
        try:
            salary = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("Salary must be a finite number") from exc
        if not salary.is_finite():
            raise ValueError("Salary must be a finite number")
        if salary < 0:
            raise ValueError("Salary must be at least 0")
        if salary > Decimal(str(MAX_ANNUAL_GROSS_BASE_SALARY)):
            raise ValueError("Salary must not exceed 9999999999.99")
        if max(-salary.as_tuple().exponent, 0) > 2:
            raise ValueError("Salary must have at most 2 decimal places")
        return value

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        """Ensure the currency is supported."""
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Currency must be one of: {', '.join(SUPPORTED_CURRENCIES)}")
        return value


class ControlledEmployeeFields(EmployeeFields):
    """Employee fields restricted to the department-specific designation lists."""

    @field_validator("department")
    @classmethod
    def validate_department(cls, value: str) -> str:
        """Require one of the configured department names after trimming."""
        if value not in DESIGNATIONS_BY_DEPARTMENT:
            allowed = ", ".join(DESIGNATIONS_BY_DEPARTMENT)
            raise ValueError(f"Department must be one of: {allowed}")
        return value

    @field_validator("designation")
    @classmethod
    def validate_designation(cls, value: str, info: ValidationInfo) -> str:
        """Require a designation listed for the selected department."""
        department = info.data.get("department")
        if department is None:
            return value
        allowed_designations = DESIGNATIONS_BY_DEPARTMENT.get(department, ())
        if value not in allowed_designations:
            allowed = ", ".join(allowed_designations)
            raise ValueError(f"Designation must be one of: {allowed}")
        return value


class EmployeeCreate(ControlledEmployeeFields):
    """Validated employee data for creating a record."""


class EmployeeUpdate(ControlledEmployeeFields):
    """Validated replacement employee data; employee_id cannot be changed."""


class EmployeeRead(EmployeeFields):
    """Validated employee data returned by the API."""

    employee_id: str

    @field_validator("employee_id")
    @classmethod
    def validate_employee_id(cls, value: str) -> str:
        """Ensure the employee ID matches the required format."""
        if re.fullmatch(EMPLOYEE_ID_PATTERN, value) is None:
            raise ValueError("Employee ID must match EMP-00001 format")
        return value


class EmployeeListResponse(BaseModel):
    """Paginated employee list and match metadata."""

    items: list[EmployeeRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class CurrencySalarySummary(BaseModel):
    """Employee count and salary statistics, all measured in one currency."""

    currency: str
    headcount: int
    average_annual_gross_base_salary: float
    minimum_annual_gross_base_salary: float
    maximum_annual_gross_base_salary: float


class SalaryGroupSummary(BaseModel):
    """Salary statistics for a department or country, split by currency."""

    name: str
    headcount: int
    currencies: list[CurrencySalarySummary]


class SalaryDashboardResponse(BaseModel):
    """Filtered salary summaries by currency and overall employee headcount."""

    currencies: list[CurrencySalarySummary]
    total_headcount: int


class EmployeeFilterOptions(BaseModel):
    """Distinct employee filter values and the supported status/currency values."""

    countries: list[str]
    departments: list[str]
    employment_statuses: list[str]
    currencies: list[str]
    designations_by_department: dict[str, list[str]]
