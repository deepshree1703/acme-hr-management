"""Tests for employee Pydantic validation models."""

import pytest
from pydantic import ValidationError

from app.schemas import EmployeeCreate, EmployeeRead, EmployeeUpdate


VALID_CREATE = {
    "name": "  Alex Example  ",
    "department": "  Operations ",
    "country": " India ",
    "employment_status": "Active",
    "annual_gross_base_salary": 0,
    "currency": "INR",
}

VALID_UPDATE = VALID_CREATE.copy()


def test_employee_models_accept_valid_data_and_trim_required_text() -> None:
    """Verify that employee models accept valid data and trim required text."""
    created = EmployeeCreate(**VALID_CREATE)
    updated = EmployeeUpdate(**VALID_UPDATE)
    read = EmployeeRead(**(VALID_CREATE | {"employee_id": "EMP-00001"}))

    assert created.name == updated.name == read.name == "Alex Example"
    assert created.department == "Operations"
    assert created.country == "India"
    assert created.annual_gross_base_salary == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
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
    """Verify that employee create rejects invalid values."""
    payload = VALID_CREATE.copy()
    payload[field] = value

    with pytest.raises(ValidationError):
        EmployeeCreate(**payload)


def test_employee_update_requires_fields_and_rejects_employee_id() -> None:
    """Verify that employee update requires fields and rejects employee id."""
    payload = VALID_UPDATE | {"employee_id": "EMP-00002"}

    with pytest.raises(ValidationError):
        EmployeeUpdate(**payload)

    incomplete_payload = VALID_UPDATE.copy()
    del incomplete_payload["name"]
    with pytest.raises(ValidationError):
        EmployeeUpdate(**incomplete_payload)


def test_employee_create_forbids_client_employee_id() -> None:
    """Verify that employee create forbids client employee id."""
    with pytest.raises(ValidationError):
        EmployeeCreate(**(VALID_CREATE | {"employee_id": "EMP-00001"}))


@pytest.mark.parametrize("model", [EmployeeCreate, EmployeeUpdate])
@pytest.mark.parametrize("salary", [9999999999.99, 100.25, 0])
def test_employee_salary_limits_accept_valid_values(model, salary) -> None:
    """Verify that employee salary limits accept valid values."""
    assert model(**(VALID_CREATE | {"annual_gross_base_salary": salary})).annual_gross_base_salary == salary


@pytest.mark.parametrize("model", [EmployeeCreate, EmployeeUpdate])
@pytest.mark.parametrize(
    "salary",
    [10000000000, 100.255, -0.01, float("nan"), float("inf"), float("-inf")],
)
def test_employee_salary_limits_reject_invalid_values(model, salary) -> None:
    """Verify that employee salary limits reject invalid values."""
    with pytest.raises(ValidationError):
        model(**(VALID_CREATE | {"annual_gross_base_salary": salary}))
