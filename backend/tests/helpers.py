"""Shared helper functions for tests (not fixtures)."""

from uuid import uuid4
from datetime import datetime, timezone

TEST_EMAIL_PREFIX = "test_schema_qa_"


def now_utc():
    return datetime.now(timezone.utc)


def uid():
    return uuid4()


def make_email():
    return f"{TEST_EMAIL_PREFIX}{uuid4().hex[:8]}@qa.internal"
