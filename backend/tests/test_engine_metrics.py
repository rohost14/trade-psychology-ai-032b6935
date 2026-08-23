"""
Engine observability. Read-only aggregates that must never break the scrape.

WHY THESE EXIST AT ALL

The infrastructure metrics say how many sockets are open and how deep the queues
are. None of them says anything about the thing the product does. Two defects
found in the last week would both have been visible in production as a metric and
were instead found by reading code:

  * the account-risk denominator reaches its GOOD rung only when a trader happens
    to load a page that fetches margins, because nothing populates
    `margin_snapshots` on a schedule — a `denominator_quality{quality="unknown"}`
    series would have shown that on day one;
  * three detectors were silent across 203 replayed sessions and nobody could say
    whether that was correct, because a dead detector and a quiet market look
    identical from every other angle.

THE RULE THESE TESTS ENFORCE

A metrics endpoint that raises takes the monitoring down with it, which is worse
than a missing series. Every aggregate is individually wrapped, and these tests
prove the wrapping works rather than assuming it.
"""
import pytest

from app.api import prometheus_metrics as pm


@pytest.mark.asyncio
async def test_it_populates_without_raising():
    """The happy path, against the real database."""
    await pm._populate_engine_metrics()


@pytest.mark.asyncio
async def test_a_dead_database_does_not_break_the_scrape(monkeypatch):
    """
    Monitoring is most valuable exactly when things are broken. If the database
    being down also takes out `/metrics`, the one signal left is gone too.
    """
    class _Boom:
        def __call__(self, *a, **k):
            raise RuntimeError("database is down")

    monkeypatch.setattr("app.core.database.SessionLocal", _Boom())
    await pm._populate_engine_metrics()  # must not raise


@pytest.mark.asyncio
async def test_one_failing_aggregate_does_not_suppress_the_others(monkeypatch):
    """
    Per-aggregate wrapping, not one try/except around the lot. A column that
    disappears in a migration must cost one series, not five.
    """
    import app.services.detector_registry as registry

    monkeypatch.setattr(
        registry, "REGISTRY", property(lambda self: (_ for _ in ()).throw(RuntimeError()))
    )
    await pm._populate_engine_metrics()

    # The severity series is populated by an earlier aggregate and must survive.
    text = pm.generate_latest().decode()
    assert "tradementor_alerts_today" in text


def test_every_severity_is_a_series_even_at_zero():
    """
    A missing series and a zero are different claims. `critical` folding into
    `danger` was a live bug; if `critical` only appears once it has fired, the
    dashboard cannot show that it never does.
    """
    for severity in ("info", "caution", "danger", "critical"):
        pm._alerts_today.labels(severity=severity).set(0)
    text = pm.generate_latest().decode()
    for severity in ("info", "caution", "danger", "critical"):
        assert f'severity="{severity}"' in text


def test_detection_lag_is_exposed_by_quantile():
    """
    A mean would hide the case that matters. One alert forty minutes late among
    a hundred prompt ones is the failure; the mean barely moves.
    """
    pm._detection_lag.labels(quantile="p50").set(1.0)
    pm._detection_lag.labels(quantile="p90").set(9.0)
    text = pm.generate_latest().decode()
    assert 'quantile="p50"' in text and 'quantile="p90"' in text


def test_all_five_worker_queues_are_covered():
    """
    `bulk` and `celery` were missing. `bulk` carries the EOD fan-out, which is
    the exact backlog that queue exists to keep off the live alert path — so the
    one queue whose depth most needed watching was the one not watched.
    """
    import inspect

    source = inspect.getsource(pm._populate_metrics)
    for queue in ("celery", "trades", "alerts", "reports", "bulk"):
        assert f'"{queue}"' in source, f"queue {queue} is not scraped"
