"""Vercel entry point for the existing FastAPI application."""

import sys
from pathlib import Path
from typing import Any

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.main import app as fastapi_app  # noqa: E402


class ApiPrefixMiddleware:
    """Strip the public /api prefix before FastAPI matches its existing routes."""

    def __init__(self, application: Any) -> None:
        self.application = application

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            path = scope["path"]
            if path == "/api" or path.startswith("/api/"):
                scope = dict(scope)
                scope["path"] = path[4:] or "/"
                raw_path = scope.get("raw_path")
                if raw_path and raw_path.startswith(b"/api"):
                    scope["raw_path"] = raw_path[4:] or b"/"
        await self.application(scope, receive, send)


app = ApiPrefixMiddleware(fastapi_app)
