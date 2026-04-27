"""
DevOps Info Service
Main application module
"""

import json
import logging
import os
import platform
import socket
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, ClassVar

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = os.getenv("APP_NAME", "devops-python-info-service")
    app_version: str = os.getenv("APP_VERSION", "2026.04")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "5000"))
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return False


settings = Settings()


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for Loki/Promtail ingestion."""

    empty_record: ClassVar[logging.LogRecord] = logging.LogRecord(
        name="",
        level=0,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    )

    def format(self, record: logging.LogRecord) -> str:
        log_record: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "app_name": settings.app_name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            # fields in empty records are techinal Python object fields, 
            # not what we actually want to log
            if key not in self.empty_record.__dict__ and key not in log_record:
                log_record[key] = value

        return json.dumps(log_record, default=str, separators=(",", ":"))


def configure_logging() -> None:
    """Configure application and uvicorn loggers to emit JSON only."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    log_level = settings.log_level.upper()
    for logger_name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        target_logger = logging.getLogger(logger_name)
        target_logger.handlers = [handler]
        target_logger.setLevel(log_level)
        target_logger.propagate = False


configure_logging()
logger = logging.getLogger(settings.app_name)


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
            "name": settings.app_name,
            "version": settings.app_version,
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


@app.middleware("http")
async def log_http_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Log HTTP request start and completion with structured context."""
    start_time = time.perf_counter()
    client_ip = request.client.host if request.client else None
    context = {
        "method": request.method,
        "path": request.url.path,
        "client_ip": client_ip,
    }

    logger.info("http_request_started", extra=context)
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    logger.info(
        "http_request_finished",
        extra={
            **context,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


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
    logger.exception(
        "unhandled_exception",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else None,
        },
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": f"An unexpected error occurred {exc}",
        },
    )


if __name__ == "__main__":
    logger.info(
        "app_startup",
        extra={
            "host": settings.host,
            "port": settings.port,
            "debug": settings.debug,
            "app_version": settings.app_version,
        },
    )
    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
        access_log=False,
        log_config=None,
    )
