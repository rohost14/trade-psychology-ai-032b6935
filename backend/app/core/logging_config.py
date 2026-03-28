"""
Comprehensive Logging Configuration

Features:
- Structured JSON logging for production
- Human-readable logging for development
- Request/response logging middleware
- Performance metrics
- Error tracking with context
"""

import logging
import sys
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from functools import wraps
from contextlib import asynccontextmanager
import traceback
from uuid import uuid4

from app.core.config import settings


# ==========================================================================
# Custom JSON Formatter
# ==========================================================================

class JSONFormatter(logging.Formatter):
    """
    Formats log records as JSON for structured logging.

    Perfect for log aggregation systems (ELK, Datadog, CloudWatch, etc.)
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        # Add request context if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "broker_account_id"):
            log_data["broker_account_id"] = record.broker_account_id

        return json.dumps(log_data)


class DevelopmentFormatter(logging.Formatter):
    """
    Human-readable formatter for development.
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]

        message = f"{color}[{timestamp}] {record.levelname:8}{self.RESET} "
        message += f"{record.name}: {record.getMessage()}"

        if record.exc_info:
            message += "\n" + "".join(traceback.format_exception(*record.exc_info))

        return message


# ==========================================================================
# Setup Functions
# ==========================================================================

def setup_logging():
    """
    Configure application logging.

    Call this at application startup.
    """
    # Determine environment
    is_production = getattr(settings, "ENVIRONMENT", "development") == "production"

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if not is_production else logging.INFO)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if not is_production else logging.INFO)

    # Choose formatter based on environment
    if is_production:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(DevelopmentFormatter())

    root_logger.addHandler(console_handler)

    # Inject request_id from ContextVar into every log record (works in both
    # HTTP server and Celery workers — the ContextVar is set at task/request start)
    from app.core.request_context import RequestIdFilter
    root_logger.addFilter(RequestIdFilter())

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    return root_logger


# ==========================================================================
# Context Logger
# ==========================================================================

class ContextLogger:
    """
    Logger with request context support.

    Usage:
        logger = ContextLogger("my_module")
        logger.with_context(request_id="abc123", user_id="xyz")
        logger.info("Processing request")
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}

    def with_context(self, **kwargs) -> "ContextLogger":
        """Add context to all subsequent log messages."""
        self._context.update(kwargs)
        return self

    def clear_context(self):
        """Clear the context."""
        self._context.clear()

    def _log(self, level: int, message: str, *args, **kwargs):
        extra = kwargs.pop("extra", {})
        extra.update(self._context)

        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "(unknown)",
            0,
            message,
            args,
            None,
        )
        record.extra_data = extra

        for key, value in self._context.items():
            setattr(record, key, value)

        self._logger.handle(record)

    def debug(self, message: str, *args, **kwargs):
        self._log(logging.DEBUG, message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self._log(logging.INFO, message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._log(logging.WARNING, message, *args, **kwargs)

    def error(self, message: str, *args, exc_info=False, **kwargs):
        if exc_info:
            kwargs["exc_info"] = sys.exc_info()
        self._log(logging.ERROR, message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self._log(logging.CRITICAL, message, *args, **kwargs)


# ==========================================================================
# Performance Metrics
# ==========================================================================

class MetricsCollector:
    """
    Simple metrics collector for performance monitoring.

    Tracks:
    - API call durations
    - Error counts
    - Request counts by endpoint
    """

    def __init__(self):
        self._metrics: Dict[str, Any] = {
            "api_calls": {},
            "errors": {},
            "request_counts": {},
            "broker_api_calls": {},
        }
        self._start_time = datetime.now(timezone.utc)

    def record_api_call(self, endpoint: str, duration_ms: float, success: bool):
        """Record an API call metric."""
        if endpoint not in self._metrics["api_calls"]:
            self._metrics["api_calls"][endpoint] = {
                "count": 0,
                "total_duration_ms": 0,
                "errors": 0,
                "min_ms": float("inf"),
                "max_ms": 0,
            }

        stats = self._metrics["api_calls"][endpoint]
        stats["count"] += 1
        stats["total_duration_ms"] += duration_ms
        stats["min_ms"] = min(stats["min_ms"], duration_ms)
        stats["max_ms"] = max(stats["max_ms"], duration_ms)

        if not success:
            stats["errors"] += 1

    def record_broker_call(self, broker: str, endpoint: str, duration_ms: float, success: bool):
        """Record a broker API call."""
        key = f"{broker}:{endpoint}"
        if key not in self._metrics["broker_api_calls"]:
            self._metrics["broker_api_calls"][key] = {
                "count": 0,
                "total_duration_ms": 0,
                "errors": 0,
            }

        stats = self._metrics["broker_api_calls"][key]
        stats["count"] += 1
        stats["total_duration_ms"] += duration_ms
        if not success:
            stats["errors"] += 1

    def record_error(self, error_type: str, error_message: str):
        """Record an error occurrence."""
        if error_type not in self._metrics["errors"]:
            self._metrics["errors"][error_type] = {
                "count": 0,
                "last_message": None,
                "last_occurred": None,
            }

        self._metrics["errors"][error_type]["count"] += 1
        self._metrics["errors"][error_type]["last_message"] = error_message
        self._metrics["errors"][error_type]["last_occurred"] = datetime.now(timezone.utc).isoformat()

    def get_metrics(self) -> Dict:
        """Get all collected metrics."""
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        # Calculate averages
        api_summary = {}
        for endpoint, stats in self._metrics["api_calls"].items():
            if stats["count"] > 0:
                api_summary[endpoint] = {
                    "count": stats["count"],
                    "avg_duration_ms": round(stats["total_duration_ms"] / stats["count"], 2),
                    "min_ms": stats["min_ms"] if stats["min_ms"] != float("inf") else 0,
                    "max_ms": stats["max_ms"],
                    "error_rate": round(stats["errors"] / stats["count"] * 100, 2),
                }

        return {
            "uptime_seconds": round(uptime, 2),
            "started_at": self._start_time.isoformat(),
            "api_calls": api_summary,
            "broker_api_calls": self._metrics["broker_api_calls"],
            "errors": self._metrics["errors"],
        }

    def reset(self):
        """Reset all metrics."""
        self._metrics = {
            "api_calls": {},
            "errors": {},
            "request_counts": {},
            "broker_api_calls": {},
        }
        self._start_time = datetime.now(timezone.utc)


# Global metrics collector
metrics = MetricsCollector()


# ==========================================================================
# Decorators
# ==========================================================================

def log_execution_time(logger: Optional[logging.Logger] = None):
    """
    Decorator to log function execution time.

    Usage:
        @log_execution_time()
        async def my_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            _logger = logger or logging.getLogger(func.__module__)
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                _logger.debug(f"{func.__name__} completed in {duration:.2f}ms")
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                _logger.error(f"{func.__name__} failed after {duration:.2f}ms: {e}")
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            _logger = logger or logging.getLogger(func.__module__)
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                _logger.debug(f"{func.__name__} completed in {duration:.2f}ms")
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                _logger.error(f"{func.__name__} failed after {duration:.2f}ms: {e}")
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Need asyncio for the decorator
import asyncio


def track_broker_call(broker: str, endpoint: str):
    """
    Decorator to track broker API calls.

    Usage:
        @track_broker_call("zerodha", "get_trades")
        async def get_trades():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            success = True
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception:
                success = False
                raise
            finally:
                duration = (time.time() - start) * 1000
                metrics.record_broker_call(broker, endpoint, duration, success)

        return wrapper
    return decorator
