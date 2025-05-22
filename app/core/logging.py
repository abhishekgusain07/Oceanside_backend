"""
Configure application logging.
"""
import sys
import logging
import json
from datetime import datetime
from typing import Any, Dict
import structlog
from app.core.config import settings

def configure_logging() -> None:
    """
    Configure application logging with structured logging.
    """
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter(
            fmt="%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(console_handler)

    # Configure third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Log startup message
    logger = structlog.get_logger(__name__)
    logger.info(
        "Logging configured",
        log_level=settings.LOG_LEVEL,
        environment=settings.ENVIRONMENT,
        version=settings.VERSION,
    )

def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: The name of the logger
        
    Returns:
        structlog.BoundLogger: Configured logger instance
    """
    return structlog.get_logger(name)

def log_request(
    logger: structlog.BoundLogger,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration: float,
    **kwargs: Any,
) -> None:
    """
    Log a request with structured data.
    
    Args:
        logger: The logger instance
        request_id: The request ID
        method: The HTTP method
        path: The request path
        status_code: The response status code
        duration: The request duration in seconds
        **kwargs: Additional fields to log
    """
    logger.info(
        "Request completed",
        request_id=request_id,
        method=method,
        path=path,
        status_code=status_code,
        duration=duration,
        **kwargs,
    )

def log_error(
    logger: structlog.BoundLogger,
    request_id: str,
    error: Exception,
    **kwargs: Any,
) -> None:
    """
    Log an error with structured data.
    
    Args:
        logger: The logger instance
        request_id: The request ID
        error: The exception that occurred
        **kwargs: Additional fields to log
    """
    logger.error(
        "Request failed",
        request_id=request_id,
        error=str(error),
        error_type=error.__class__.__name__,
        exc_info=True,
        **kwargs,
    )