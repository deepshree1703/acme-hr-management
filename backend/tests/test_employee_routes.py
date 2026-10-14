"""API tests for creating and fetching employees."""

import asyncio

import pytest
from httpx2 import ASGITransport, AsyncClient, Response

from app.db_schema import init_db
from app.main import app


@pytest.fixture
def api_transport(monkeypatch: pytest.MonkeyPatch, tmp_path) -> ASGITransport:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "employees.db"))
    init_db()
    return ASGITransport(app=app)


def _request(
    transport: ASGITransport,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> Response:
    async def send_request() -> Response:
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=payload)

    return asyncio.run(send_request())


def valid_employee_payload() -> dict[str, object]:
    return {
        "employee_id": "EMP-00001",
        "name": "Alex Example",
        "department": "Operations",
        "country": "India",
        "employment_status": "Active",
        "annual_gross_base_salary": 50000,
        "currency": "INR",
    }


def test_create_employee_returns_created_record(api_transport: ASGITransport) -> None:
    response = _request(api_transport, "POST", "/employees", valid_employee_payload())

    assert response.status_code == 201
    assert response.json() == {
        **valid_employee_payload(),
        "annual_gross_base_salary": 50000.0,
    }


def test_create_employee_returns_conflict_for_duplicate_id(
    api_transport: ASGITransport,
) -> None:
    payload = valid_employee_payload()

    assert _request(api_transport, "POST", "/employees", payload).status_code == 201
    response = _request(api_transport, "POST", "/employees", payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "Employee ID EMP-00001 already exists"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("currency", "XYZ"),
        ("annual_gross_base_salary", -1),
        ("employee_id", "EMP-1234"),
    ],
)
def test_create_employee_rejects_invalid_payloads(
    api_transport: ASGITransport, field: str, value: object
) -> None:
    payload = valid_employee_payload()
    payload[field] = value

    response = _request(api_transport, "POST", "/employees", payload)

    assert response.status_code == 422


def test_get_existing_employee_returns_record(api_transport: ASGITransport) -> None:
    payload = valid_employee_payload()
    _request(api_transport, "POST", "/employees", payload)

    response = _request(api_transport, "GET", "/employees/EMP-00001")

    assert response.status_code == 200
    assert response.json()["employee_id"] == "EMP-00001"
    assert response.json()["name"] == "Alex Example"


def test_get_missing_employee_returns_not_found(api_transport: ASGITransport) -> None:
    response = _request(api_transport, "GET", "/employees/EMP-99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Employee not found"
