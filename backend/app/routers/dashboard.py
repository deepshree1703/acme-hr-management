"""Salary dashboard route."""

import sqlite3

from fastapi import APIRouter, Depends

from app.database import get_connection
from app.repository import get_salary_dashboard
from app.schemas import SalaryDashboardResponse

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=SalaryDashboardResponse)
def salary_dashboard(
    connection: sqlite3.Connection = Depends(get_connection),
) -> SalaryDashboardResponse:
    """Return headcount and average annual salary grouped by currency."""
    currencies, total_headcount = get_salary_dashboard(connection)
    return SalaryDashboardResponse(
        currencies=currencies,
        total_headcount=total_headcount,
    )
