"""
Request context propagation via ContextVar.

Allows request_id to flow from HTTP middleware → Celery tasks → async functions
and appear in every log line without explicit passing.

Usage:
    # In HTTP middleware (main.py):
    from app.core.request_context import request_id_var
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)

    # In Celery task:
    from app.core.request_context import request_id_var
    request_id_var.set(request_id)  # set at task start
"""

import logging
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """
    Injects request_id from the ContextVar into every log record.

    Add to root logger once at startup. Works in both the HTTP server
    (where middleware sets the var) and Celery workers (where the task sets it).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True
