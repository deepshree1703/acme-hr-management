"""Salary dashboard route."""

from fastapi import APIRouter, Depends

from app.database import DatabaseConnection, get_connection
from app.repository import get_salary_dashboard
from app.schemas import SalaryDashboardResponse

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=SalaryDashboardResponse)
def salary_dashboard(
    connection: DatabaseConnection = Depends(get_connection),
) -> SalaryDashboardResponse:
    """Return headcount and average annual salary grouped by currency."""
    currencies, total_headcount = get_salary_dashboard(connection)
    return SalaryDashboardResponse(
        currencies=currencies,
        total_headcount=total_headcount,
    )
