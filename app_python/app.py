"""DevOps Info Service main application module."""

import logging
import os
import platform
import socket
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, TextIO

import structlog
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


def add_app_name(
    logger: logging.Logger, method_name: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    event_dict["app_name"] = settings.app_name
    return event_dict


def drop_color_message(
    logger: logging.Logger, method_name: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging(stream: TextIO | None = None) -> None:
    """Configure application and uvicorn loggers through structlog."""
    log_stream = stream or sys.stderr
    shared_processors: list[structlog.typing.Processor] = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        drop_color_message,
        add_app_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if log_stream.isatty():
        renderer = structlog.dev.ConsoleRenderer(colors=True, event_key="message")
    else:
        renderer: structlog.typing.Processor = structlog.processors.JSONRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.EventRenamer(to="message"),
            renderer,
        ],
    )

    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(formatter)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    log_level = settings.log_level.upper()
    for logger_name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        target_logger = logging.getLogger(logger_name)
        target_logger.handlers = [handler]
        target_logger.setLevel(log_level)
        target_logger.propagate = False


configure_logging()
logger = structlog.get_logger(settings.app_name)


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

    logger.info("http_request_started", **context)
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    logger.info(
        "http_request_finished",
        **context,
        status_code=response.status_code,
        duration_ms=duration_ms,
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
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else None,
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
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
        app_version=settings.app_version,
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
