"""
Logging configuration for the application.
"""
import logging
import sys
from typing import Any, Dict

import structlog
from structlog.types import Processor

from app.core.config import settings


def configure_logging() -> None:
    """Configure logging for the application using structlog."""
    shared_processors: list[Processor] = [
        # Include context vars like request_id in logs
        structlog.contextvars.merge_contextvars,
        
        # Add basic log info
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        
        # Add exception info if present
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        
        # Add the hostname to distinguish logs from different machines
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.JSON_LOGS:
        # Production: JSON logs for machine processing
        formatter = structlog.processors.JSONRenderer()
    else:
        # Development: Console logs for human reading
        formatter = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
        wrapper_class=structlog.stdlib.BoundLogger,
    )

    # Configure stdlib logging
    log_level = getattr(logging, settings.LOG_LEVEL.upper())
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        stream=sys.stdout,
    )