"""FastAPI application entry point."""

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.database import check_database
from app.db_schema import init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize the local database schema before serving requests."""
    init_db()
    yield

app = FastAPI(
    title="ACME Employee Salary Management API",
    description="Backend API for the ACME Employee Salary Management project.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Report API and SQLite connectivity."""
    try:
        check_database()
    except (OSError, sqlite3.Error) as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc

    return {"status": "ok", "database": "ok"}
