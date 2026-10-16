"""Salary dashboard route."""

import re

from fastapi import APIRouter, Depends, Query

from app.constants import EMPLOYMENT_STATUSES
from app.database import DatabaseConnection, get_connection
from app.repository import get_salary_dashboard, get_salary_group_summaries
from app.schemas import SalaryDashboardResponse, SalaryGroupSummary

router = APIRouter(tags=["dashboard"])
_STATUS_PATTERN = rf"^(?:{'|'.join(re.escape(value) for value in EMPLOYMENT_STATUSES)})$"


@router.get("/dashboard", response_model=SalaryDashboardResponse)
def salary_dashboard(
    department: str | None = None,
    country: str | None = None,
    employment_status: str | None = Query(default=None, pattern=_STATUS_PATTERN),
    connection: DatabaseConnection = Depends(get_connection),
) -> SalaryDashboardResponse:
    """Return filtered headcount and salary statistics grouped by currency."""
    currencies, total_headcount = get_salary_dashboard(
        connection,
        department=department,
        country=country,
        employment_status=employment_status,
    )
    return SalaryDashboardResponse(
        currencies=currencies,
        total_headcount=total_headcount,
    )


@router.get("/dashboard/by-department", response_model=list[SalaryGroupSummary])
def salary_dashboard_by_department(
    department: str | None = None,
    country: str | None = None,
    employment_status: str | None = Query(default=None, pattern=_STATUS_PATTERN),
    connection: DatabaseConnection = Depends(get_connection),
) -> list[SalaryGroupSummary]:
    """Return filtered salary statistics grouped by department and currency."""
    return get_salary_group_summaries(
        connection,
        group_by="department",
        department=department,
        country=country,
        employment_status=employment_status,
    )


@router.get("/dashboard/by-country", response_model=list[SalaryGroupSummary])
def salary_dashboard_by_country(
    department: str | None = None,
    country: str | None = None,
    employment_status: str | None = Query(default=None, pattern=_STATUS_PATTERN),
    connection: DatabaseConnection = Depends(get_connection),
) -> list[SalaryGroupSummary]:
    """Return filtered salary statistics grouped by country and currency."""
    return get_salary_group_summaries(
        connection,
        group_by="country",
        department=department,
        country=country,
        employment_status=employment_status,
    )
