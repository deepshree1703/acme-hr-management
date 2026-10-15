"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import DATABASE_ERRORS, check_database
from app.db_schema import init_db
from app.routers.dashboard import router as dashboard_router
from app.routers.employees import router as employees_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize the configured database schema before serving requests."""
    init_db()
    yield

app = FastAPI(
    title="ACME Employee Salary Management API",
    description="Backend API for the ACME Employee Salary Management project.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(employees_router)
app.include_router(dashboard_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Report API and database connectivity."""
    try:
        check_database()
    except (OSError, *DATABASE_ERRORS) as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc

    return {"status": "ok", "database": "ok"}
