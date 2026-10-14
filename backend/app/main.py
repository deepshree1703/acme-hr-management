"""FastAPI application entry point."""

import sqlite3

from fastapi import FastAPI, HTTPException

from app.database import check_database

app = FastAPI(
    title="ACME Employee Salary Management API",
    description="Backend API for the ACME Employee Salary Management project.",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Report API and SQLite connectivity."""
    try:
        check_database()
    except (OSError, sqlite3.Error) as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc

    return {"status": "ok", "database": "ok"}
