"""
Every place that writes a BehaviorEvent must set an idempotency key.

WHY THIS FILE EXISTS

`behavior_events` has no primary key. That is deliberate and documented in
`migrations/067_partition_behavior_events.sql` - the table is append-only
evidence, nothing joins into it by id, and a partitioned table's primary key
would have to include the partition key. Verified: 0 foreign keys point into
the table.

The consequence is that ALL uniqueness protection comes from one partial index:

    uq_behavior_events_idem
      UNIQUE (broker_account_id, idempotency_key, detected_at)
      WHERE idempotency_key IS NOT NULL

A row written without a key is excluded from that index by the WHERE clause. It
therefore has no uniqueness guarantee of any kind - not from a primary key,
because there isn't one, and not from the unique index, because it does not
apply. A retried Celery task writes the row twice and nothing objects.

WHAT WENT WRONG, AND WHY THE CHECK IS MECHANICAL

The Phase 2 plan stated "both documented writers construct a key
unconditionally (behavior_engine.py:664, trade_tasks.py:522)". That was
inherited and repeated without being checked, and it was wrong twice over:
`trade_tasks.py:522` is a PositionLedger key, not a BehaviorEvent one, and
there were five BehaviorEvent writers, not two. Three of them set no key at
all.

A plain grep for `BehaviorEvent(` would ALSO have missed one, because
`behavior_engine.py:71` imports it as `BehaviorEventRecord`. So this walks the
AST and resolves the alias each module binds, rather than matching a name.

The rule this enforces: a claim of the form "every writer does X" belongs in a
test, not in a document. Documents do not fail when they go stale.
"""
from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

#: Writers that produce an unkeyed event, each with the reason it is accepted.
#:
#: An entry needs an argument that survives "what happens when this is retried
#: or run twice at once?". "It has never fired yet" is NOT such an argument - a
#: scheduled task that has not fired yet will fire.
#:
#: Why these three are accepted rather than given keys: a key alone would not
#: protect them. `uq_behavior_events_idem` is UNIQUE on (broker_account_id,
#: idempotency_key, detected_at), and all three set `detected_at` to the
#: processing clock. Two runs produce two different `detected_at` values, so the
#: tuples differ and nothing collides no matter what key is attached. Adding one
#: would look like protection while providing none, which is worse than the
#: honest gap. Making `detected_at` deterministic instead would change what
#: these events mean - they record a moment of observation, not a trade's exit -
#: and that is a product decision, not a constraint fix.
#:
#: Each is instead protected in application code, verified by reading it.
UNKEYED_WRITERS_ALLOWED: dict[str, str] = {
    "app/tasks/maintenance_tasks.py:533": (
        "tilt_recovery. Guarded by an explicit read-before-write immediately "
        "above the insert: it selects any existing tilt_recovery event for the "
        "same account since the IST day start and skips if one exists "
        "(maintenance_tasks.py:518-527). A Celery retry re-runs the whole "
        "function and sees the committed row, so retries are handled. The "
        "residual exposure is two workers racing the same beat, which Celery "
        "beat does not normally produce."
    ),
    "app/tasks/position_monitor_tasks.py:508": (
        "Written inside _fire_position_alert, which returns False without "
        "writing when a 30-minute, escalation-aware dedup window already "
        "covers the alert (position_monitor_tasks.py:424-448). The event is "
        "only written when a genuinely new RiskAlert was created, and it "
        "carries that alert's id in risk_alert_id."
    ),
    "app/tasks/position_monitor_tasks.py:722": (
        "The entry-shadow writer, shadow=True and data_quality=PARTIAL. Shadow "
        "rows are evidence about an unresolved position and are excluded from "
        "every trader-facing surface, so a duplicate misleads nobody."
    ),
}


def _behavior_event_names(tree: ast.Module) -> set[str]:
    """
    Local names bound to `app.models.behavior_event.BehaviorEvent` in a module.

    Resolves `as` aliases: `behavior_engine.py` imports it as
    `BehaviorEventRecord`, and a check that matched the literal name would
    silently skip the single largest writer in the codebase.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").endswith("models.behavior_event"):
                for alias in node.names:
                    if alias.name == "BehaviorEvent":
                        names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.endswith("models.behavior_event"):
                    # `import app.models.behavior_event` - calls would be
                    # attribute access, handled by the caller below.
                    names.add((alias.asname or alias.name).split(".")[-1])
    return names


def _writers() -> list[tuple[str, int, list[str]]]:
    """`(file:line, keyword names)` for every BehaviorEvent construction."""
    found: list[tuple[str, int, list[str]]] = []

    for path in sorted(APP_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:  # pragma: no cover
            continue

        names = _behavior_event_names(tree)
        if not names:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                called = func.id
            elif isinstance(func, ast.Attribute):
                called = func.attr
            else:
                continue
            if called not in names and called != "BehaviorEvent":
                continue
            keywords = [kw.arg for kw in node.keywords if kw.arg]
            found.append((
                f"{path.relative_to(APP_ROOT.parent).as_posix()}:{node.lineno}",
                node.lineno,
                keywords,
            ))

    return found


def test_the_writers_can_actually_be_found():
    """
    Guards the guard. If the AST walk stops matching - the model moves, the
    import style changes - this file would pass by finding nothing, which is
    the failure mode it exists to prevent.
    """
    writers = _writers()
    assert len(writers) >= 4, (
        f"only {len(writers)} BehaviorEvent writer(s) found, expected at least "
        "4. The detection has probably broken rather than the writers having "
        f"gone away: {[w[0] for w in writers]}"
    )


def test_every_behavior_event_writer_sets_an_idempotency_key():
    """
    THE ONE THAT MATTERS.

    A BehaviorEvent with no idempotency key falls outside
    `uq_behavior_events_idem` because that index is partial, and the table has
    no primary key to fall back on. Such a row has no uniqueness guarantee at
    all, so a retried task duplicates it silently.
    """
    unkeyed = [
        location for location, _line, keywords in _writers()
        if "idempotency_key" not in keywords
        and location not in UNKEYED_WRITERS_ALLOWED
    ]

    assert not unkeyed, (
        "BehaviorEvent written with no idempotency_key:\n  "
        + "\n  ".join(unkeyed)
        + "\n\nbehavior_events has no primary key (deliberately - see "
        "migrations/067), so uq_behavior_events_idem is the ONLY uniqueness "
        "protection, and it is partial: WHERE idempotency_key IS NOT NULL. A "
        "row written without a key is excluded from it and nothing prevents a "
        "retry from writing it twice.\n"
        "Give the writer a deterministic key, or add it to "
        "UNKEYED_WRITERS_ALLOWED with a real reason."
    )


def test_every_allowlisted_writer_still_exists_and_carries_a_reason():
    """
    An allowlist nobody maintains is the same as no check.

    Two ways it rots, both caught here: an entry whose reason is thin, and an
    entry for a writer that has moved or been fixed - which would leave the
    allowlist quietly excusing a line number that now means something else.
    """
    thin = sorted(k for k, v in UNKEYED_WRITERS_ALLOWED.items() if len(v.strip()) < 80)
    assert not thin, (
        f"allowlist entries with no real argument: {thin}. Each must answer "
        "'what happens when this is retried or run twice at once?'"
    )

    unkeyed = {
        location for location, _line, keywords in _writers()
        if "idempotency_key" not in keywords
    }
    stale = sorted(set(UNKEYED_WRITERS_ALLOWED) - unkeyed)
    assert not stale, (
        f"allowlisted writer(s) no longer exist or now set a key: {stale}. "
        "Remove them, or the allowlist is excusing a line that has moved."
    )
