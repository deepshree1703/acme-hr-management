"""Tests for frontend CORS configuration."""

import asyncio

import pytest
from httpx2 import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app


def test_cors_origins_default_to_react_dev_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    assert get_settings().cors_origins == ("http://localhost:5173",)


def test_cors_origins_can_be_configured_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example, http://localhost:5173 ")

    assert get_settings().cors_origins == (
        "https://app.example",
        "http://localhost:5173",
    )


def test_cors_allows_react_dev_server_origin() -> None:
    async def send_preflight():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.options(
                "/employees",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )

    response = asyncio.run(send_preflight())

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
