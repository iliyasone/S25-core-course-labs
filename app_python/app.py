"""
DevOps Info Service
Main application module
"""

import logging
import os
import platform
import socket
from datetime import datetime, timezone
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "5000"))
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"


settings = Settings()
logger = logging.getLogger("uvicorn")


START_TIME = datetime.now(timezone.utc)

app = FastAPI(debug=settings.debug)


def get_uptime() -> dict[str, Any]:
    """Calculate uptime since application start."""
    delta = datetime.now(timezone.utc) - START_TIME
    seconds = int(delta.total_seconds())
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return {
        "seconds": seconds,
        "human": f"{hours} hour{'s' if hours != 1 else ''}, "
        f"{minutes} minute{'s' if minutes != 1 else ''}",
    }


@app.get("/")
async def get_info(request: Request) -> dict[str, Any]:
    """Main endpoint - service and system information."""
    uptime = get_uptime()

    return {
        "service": {
            "name": "devops-python-info-service",
            "version": "1.0.0",
            "description": "DevOps course info service made by @iliyasone",
            "framework": "FastAPI",
        },
        "system": {
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "platform_version": platform.platform(),
            "architecture": platform.machine(),
            "cpu_count": os.cpu_count(),
            "python_version": platform.python_version(),
        },
        "runtime": {
            "uptime_seconds": uptime["seconds"],
            "uptime_human": uptime["human"],
            "current_time": datetime.now(timezone.utc).isoformat(),
            "timezone": "UTC",
        },
        "request": {
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent", ""),
            "method": request.method,
            "path": request.url.path,
        },
        "endpoints": [
            {
                "path": route.path,
                "method": method,
                "description": route.summary or route.description,
            }
            for route in app.routes
            if isinstance(route, APIRoute)
            for method in route.methods
            if method not in {"HEAD", "OPTIONS"}
        ],
    }


@app.get("/health")
async def health():
    """Health check endpoint for monitoring."""

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": get_uptime()["seconds"],
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": f"An unexpected error occurred {exc}",
        },
    )


if __name__ == "__main__":
    logger.info(f"Starting server on {settings.host}:{settings.port}")
    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
