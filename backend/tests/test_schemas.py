"""Tests for employee Pydantic validation models."""

import pytest
from pydantic import ValidationError

from app.schemas import EmployeeCreate, EmployeeRead, EmployeeUpdate


VALID_CREATE = {
    "employee_id": "EMP-00001",
    "name": "  Alex Example  ",
    "department": "  Operations ",
    "country": " India ",
    "employment_status": "Active",
    "annual_gross_base_salary": 0,
    "currency": "INR",
}

VALID_UPDATE = {key: value for key, value in VALID_CREATE.items() if key != "employee_id"}


def test_employee_models_accept_valid_data_and_trim_required_text() -> None:
    created = EmployeeCreate(**VALID_CREATE)
    updated = EmployeeUpdate(**VALID_UPDATE)
    read = EmployeeRead(**VALID_CREATE)

    assert created.employee_id == "EMP-00001"
    assert created.name == updated.name == read.name == "Alex Example"
    assert created.department == "Operations"
    assert created.country == "India"
    assert created.annual_gross_base_salary == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("employee_id", "EMP-1234"),
        ("name", "   "),
        ("department", ""),
        ("country", "  "),
        ("employment_status", "On leave"),
        ("annual_gross_base_salary", -0.01),
        ("annual_gross_base_salary", "50000"),
        ("currency", "XYZ"),
    ],
)
def test_employee_create_rejects_invalid_values(field: str, value: object) -> None:
    payload = VALID_CREATE.copy()
    payload[field] = value

    with pytest.raises(ValidationError):
        EmployeeCreate(**payload)


def test_employee_update_requires_fields_and_rejects_employee_id() -> None:
    payload = VALID_UPDATE | {"employee_id": "EMP-00002"}

    with pytest.raises(ValidationError):
        EmployeeUpdate(**payload)

    incomplete_payload = VALID_UPDATE.copy()
    del incomplete_payload["name"]
    with pytest.raises(ValidationError):
        EmployeeUpdate(**incomplete_payload)
