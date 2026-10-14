"""API tests for creating and fetching employees."""

import asyncio

import pytest
from httpx2 import ASGITransport, AsyncClient, Response

from app.constants import EMPLOYMENT_STATUSES, SUPPORTED_CURRENCIES
from app.db_schema import init_db
from app.database import connect
from app.main import app
from app.repository import create_employee as repository_create_employee
from app.schemas import EmployeeCreate


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
    params: dict[str, str | int] | None = None,
) -> Response:
    async def send_request() -> Response:
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=payload, params=params)

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


def valid_update_payload() -> dict[str, object]:
    payload = valid_employee_payload()
    del payload["employee_id"]
    return payload


def _seed_employees(
    employees: list[dict[str, object]],
) -> None:
    connection = connect()
    try:
        for employee in employees:
            repository_create_employee(connection, EmployeeCreate(**employee))
    finally:
        connection.close()


def _list_filter_employees() -> list[dict[str, object]]:
    return [
        {
            **valid_employee_payload(),
            "employee_id": "EMP-00001",
            "name": "Alice Smith",
            "department": "People",
            "country": "Canada",
            "employment_status": "Active",
            "currency": "CAD",
        },
        {
            **valid_employee_payload(),
            "employee_id": "EMP-00002",
            "name": "Alicia Morgan",
            "department": "People",
            "country": "Canada",
            "employment_status": "Inactive",
            "currency": "CAD",
        },
        {
            **valid_employee_payload(),
            "employee_id": "EMP-00003",
            "name": "Bob Smith",
            "department": "Engineering",
            "country": "India",
            "employment_status": "Active",
            "currency": "INR",
        },
        {
            **valid_employee_payload(),
            "employee_id": "EMP-00004",
            "name": "Charlie Lee",
            "department": "Engineering",
            "country": "Canada",
            "employment_status": "Active",
            "currency": "CAD",
        },
    ]


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


def test_employee_filter_options_return_distinct_values_and_supported_options(
    api_transport: ASGITransport,
) -> None:
    _seed_employees(
        [
            {
                **valid_employee_payload(),
                "employee_id": "EMP-00001",
                "country": "Canada",
                "department": "Engineering",
            },
            {
                **valid_employee_payload(),
                "employee_id": "EMP-00002",
                "country": "Canada",
                "department": "Finance",
            },
            {
                **valid_employee_payload(),
                "employee_id": "EMP-00003",
                "country": "India",
                "department": "Engineering",
            },
        ]
    )

    response = _request(api_transport, "GET", "/employees/filters")

    assert response.status_code == 200
    assert response.json() == {
        "countries": ["Canada", "India"],
        "departments": ["Engineering", "Finance"],
        "employment_statuses": list(EMPLOYMENT_STATUSES),
        "currencies": list(SUPPORTED_CURRENCIES),
    }


def test_update_employee_returns_replacement_record(api_transport: ASGITransport) -> None:
    _request(api_transport, "POST", "/employees", valid_employee_payload())
    payload = valid_update_payload()
    payload.update(
        {
            "name": "Jordan Example",
            "department": "Finance",
            "country": "Canada",
            "employment_status": "Inactive",
            "annual_gross_base_salary": 72000,
            "currency": "CAD",
        }
    )

    response = _request(api_transport, "PUT", "/employees/EMP-00001", payload)

    assert response.status_code == 200
    assert response.json() == {
        "employee_id": "EMP-00001",
        **payload,
        "annual_gross_base_salary": 72000.0,
    }


def test_update_missing_employee_returns_not_found(
    api_transport: ASGITransport,
) -> None:
    response = _request(
        api_transport,
        "PUT",
        "/employees/EMP-99999",
        valid_update_payload(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Employee not found"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("currency", "XYZ"),
        ("annual_gross_base_salary", -1),
    ],
)
def test_update_employee_rejects_invalid_payloads(
    api_transport: ASGITransport, field: str, value: object
) -> None:
    payload = valid_update_payload()
    payload[field] = value

    response = _request(api_transport, "PUT", "/employees/EMP-00001", payload)

    assert response.status_code == 422


def test_update_employee_rejects_employee_id_in_body(
    api_transport: ASGITransport,
) -> None:
    payload = valid_update_payload()
    payload["employee_id"] = "EMP-00002"

    response = _request(api_transport, "PUT", "/employees/EMP-00001", payload)

    assert response.status_code == 422


def test_delete_employee_returns_no_content_and_fetch_then_returns_not_found(
    api_transport: ASGITransport,
) -> None:
    _request(api_transport, "POST", "/employees", valid_employee_payload())

    response = _request(api_transport, "DELETE", "/employees/EMP-00001")

    assert response.status_code == 204
    assert response.content == b""
    assert _request(api_transport, "GET", "/employees/EMP-00001").status_code == 404


def test_delete_missing_employee_returns_not_found(
    api_transport: ASGITransport,
) -> None:
    response = _request(api_transport, "DELETE", "/employees/EMP-99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Employee not found"


def test_list_employees_uses_fixed_size_pages_and_reports_totals(
    api_transport: ASGITransport,
) -> None:
    employees = []
    for index in range(1, 46):
        employee = valid_employee_payload()
        employee["employee_id"] = f"EMP-{index:05d}"
        employee["name"] = f"Employee {index:02d}"
        employees.append(employee)
    _seed_employees(employees)

    expected_page_lengths = (20, 20, 5)
    for page, expected_length in enumerate(expected_page_lengths, start=1):
        response = _request(
            api_transport,
            "GET",
            "/employees",
            params={"page": page, "page_size": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == expected_length
        assert data["total"] == 45
        assert data["page"] == page
        assert data["page_size"] == 20
        assert data["total_pages"] == 3
        assert data["items"] == sorted(data["items"], key=lambda item: item["employee_id"])

    beyond_last_page = _request(
        api_transport,
        "GET",
        "/employees",
        params={"page": 4},
    ).json()
    assert beyond_last_page["items"] == []
    assert beyond_last_page["total"] == 45
    assert beyond_last_page["total_pages"] == 3


def test_list_employees_searches_name_case_insensitively(api_transport: ASGITransport) -> None:
    _seed_employees(_list_filter_employees())

    response = _request(
        api_transport,
        "GET",
        "/employees",
        params={"search": "aLi"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["total"] == 2
    assert [item["employee_id"] for item in data["items"]] == [
        "EMP-00001",
        "EMP-00002",
    ]


def test_list_employees_searches_by_employee_id(api_transport: ASGITransport) -> None:
    _seed_employees(_list_filter_employees())

    response = _request(
        api_transport,
        "GET",
        "/employees",
        params={"search": "EMP-00003"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["total"] == 1
    assert [item["employee_id"] for item in data["items"]] == ["EMP-00003"]


def test_list_employees_searches_employee_id_by_case_insensitive_prefix(
    api_transport: ASGITransport,
) -> None:
    employees = []
    for index in range(1, 21):
        employee = valid_employee_payload()
        employee["employee_id"] = f"EMP-{index:05d}"
        employee["name"] = f"Person {index}"
        employees.append(employee)
    _seed_employees(employees)

    response = _request(
        api_transport,
        "GET",
        "/employees",
        params={"search": "emp-0001"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["total"] == 10
    assert [item["employee_id"] for item in data["items"]] == [
        f"EMP-{index:05d}" for index in range(10, 20)
    ]

    unrelated_prefix = _request(
        api_transport,
        "GET",
        "/employees",
        params={"search": "XYZ-"},
    ).json()
    assert unrelated_prefix["items"] == []
    assert unrelated_prefix["total"] == 0


@pytest.mark.parametrize(
    ("filter_params", "expected_ids"),
    [
        ({"country": "Canada"}, ["EMP-00001", "EMP-00002", "EMP-00004"]),
        ({"department": "Engineering"}, ["EMP-00003", "EMP-00004"]),
        ({"employment_status": "Active"}, ["EMP-00001", "EMP-00003", "EMP-00004"]),
    ],
)
def test_list_employees_applies_each_exact_filter(
    api_transport: ASGITransport,
    filter_params: dict[str, str],
    expected_ids: list[str],
) -> None:
    _seed_employees(_list_filter_employees())

    response = _request(
        api_transport,
        "GET",
        "/employees",
        params=filter_params,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["total"] == len(expected_ids)
    assert [item["employee_id"] for item in data["items"]] == expected_ids


def test_list_employees_combines_filters_with_and(api_transport: ASGITransport) -> None:
    _seed_employees(_list_filter_employees())

    response = _request(
        api_transport,
        "GET",
        "/employees",
        params={
            "search": "alice",
            "country": "Canada",
            "department": "People",
            "employment_status": "Active",
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["total"] == 1
    assert [item["employee_id"] for item in data["items"]] == ["EMP-00001"]


def test_list_employees_returns_empty_results_with_zero_totals(
    api_transport: ASGITransport,
) -> None:
    response = _request(
        api_transport,
        "GET",
        "/employees",
        params={"country": "Nowhere"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
    }


@pytest.mark.parametrize(
    "query", [{"employment_status": "On leave"}, {"page": 0}]
)
def test_list_employees_rejects_invalid_query_parameters(
    api_transport: ASGITransport, query: dict[str, str | int]
) -> None:
    response = _request(api_transport, "GET", "/employees", params=query)

    assert response.status_code == 422
