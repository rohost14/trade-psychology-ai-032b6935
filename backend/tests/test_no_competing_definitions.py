"""
Nothing may redefine a session fact for itself.

WHY A STATIC TEST RATHER THAN A CONVENTION

Nine places independently computed `consecutive_losses`, `session_pnl`,
`trades_today` or `peak_pnl`, and they disagreed. Not one of them was written by
someone who meant to fork a definition — each was three lines of obvious
arithmetic next to the data it needed. A convention does not survive that,
because the person writing those three lines has no reason to suspect they are
the fifth author.

So this scans the source for the shapes that arithmetic takes and requires every
occurrence to be on an allowlist with a reason. Adding a legitimately different
fact is a one-line change here plus a sentence explaining why it is different.
Forking an existing one fails the build.

WHAT IT CANNOT DO

Catch a determined rewrite: someone can always spell a running total in a way no
regex matches. It catches the accident, which is the failure that actually
happened, nine times.
"""
import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"

#: The canonical module. Exempt by definition — it IS the definition.
CANONICAL = "core/session_facts.py"

#: Patterns that mean "someone is accumulating a session fact by hand".
SIGNATURES = {
    "loss-streak counter": re.compile(
        r"(consecutive_loss(es)?|streak|consec)\s*\+=\s*1"
    ),
    "running peak": re.compile(
        r"(peak\s*=\s*max\s*\(|if\s+[\w.]*running[\w.]*\s*>\s*[\w.]*peak|>\s*(self\.)?peak_pnl\b)"
    ),
    "session P&L accumulated by hand": re.compile(
        r"session_pnl\s*(\+=|=\s*sum\()|"
        r"running_pnl\s*\+=|"
        r"(total|running)_pnl\s*\+=\s*.*realized_pnl"
    ),
    "trade count derived by hand": re.compile(
        r"(trades_today|trade_count)\s*=\s*len\("
    ),
}

# A `.replace(hour=0, minute=0, ...)` day boundary was tried as a signature and
# removed: it is the generic date-truncation idiom and fires on report windows,
# reconciliation sweeps and maintenance tasks that have nothing to do with
# session facts. A check that cries wolf teaches people to add allowlist entries
# without reading them, which is worse than no check. The signatures kept here
# all key on the FACT'S OWN NAME or on the exact shape of its arithmetic.

#: Every known occurrence, with why it is allowed to exist.
#:
#: An entry here is a claim that the code computes a DIFFERENT fact, not the same
#: fact differently. "It was already there" is not a reason — the nine that were
#: already there are exactly what this file exists to have removed.
ALLOWED = {
    ("services/state/session_state.py", "loss-streak counter"): (
        "The incremental fold. It is held to the canonical definition by "
        "tests/test_canonical_fact_agreement.py, which compares it against "
        "session_facts.derive across ten sequences."
    ),
    ("services/state/session_state.py", "running peak"): (
        "Same fold, same test."
    ),
    ("tasks/intent_tasks.py", "loss-streak counter"): (
        "A streak of consecutive DAYS on which the trader respected their stated "
        "intent. Different unit (days, not trades) and different subject "
        "(discipline, not losses)."
    ),
    ("services/state/session_state.py", "session P&L accumulated by hand"): (
        "Same fold, same test."
    ),
    ("api/profile.py", "trade count derived by hand"): (
        "A period aggregate over a `cutoff` window, used to learn the trader's "
        "detected_patterns. Not today's session."
    ),
    ("api/reports.py", "trade count derived by hand"): (
        "Counts rows in a REPORT PERIOD, and over raw `Trade.pnl` rather than "
        "round-trips. A different question in a different unit."
    ),
    ("tasks/report_tasks.py", "trade count derived by hand"): (
        "The 7-day WhatsApp report. Period aggregate, not a session fact."
    ),
    ("api/analytics.py", "running peak"): (
        "Drawdown along a multi-day equity curve. A session fact is bounded by "
        "one market open; this deliberately is not."
    ),
}


def _sources():
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP).as_posix()
        if "_archive" in rel or rel == CANONICAL:
            continue
        yield rel, path.read_text(encoding="utf-8", errors="replace")


def _hits():
    found = {}
    for rel, text in _sources():
        for name, pattern in SIGNATURES.items():
            for i, line in enumerate(text.splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                if pattern.search(line):
                    found.setdefault((rel, name), []).append((i, line.strip()))
    return found


def test_no_new_place_computes_a_session_fact_for_itself():
    hits = _hits()
    unexplained = {k: v for k, v in hits.items() if k not in ALLOWED}

    if unexplained:
        lines = []
        for (rel, name), occurrences in sorted(unexplained.items()):
            for lineno, src in occurrences:
                lines.append(f"  {rel}:{lineno}  [{name}]  {src}")
        pytest.fail(
            "Something is computing a session fact for itself:\n"
            + "\n".join(lines)
            + "\n\nUse app/core/session_facts instead. consecutive_losses, "
            "session_pnl, trades, peak_pnl, drawdown_from_peak, max_drawdown and "
            "longest_loss_run are all defined there, once.\n"
            "If this genuinely measures something DIFFERENT — a different unit, a "
            "different scope — add it to ALLOWED in this file with the reason. "
            "'It was already there' is not a reason."
        )


def test_the_allowlist_has_not_gone_stale():
    """
    An allowlist that outlives its entries stops being a record and starts being
    noise — and the next person reads it as permission.
    """
    hits = _hits()
    stale = sorted(set(ALLOWED) - set(hits))
    assert not stale, (
        "These allowlist entries no longer match anything and should be deleted: "
        f"{stale}"
    )


def test_the_canonical_module_is_where_the_definitions_live():
    """
    Guards against the definitions quietly migrating back out into callers — if
    session_facts stops defining these, the allowlist above is protecting nothing.
    """
    text = (APP / "core" / "session_facts.py").read_text(encoding="utf-8")
    for name in ("consecutive_losses", "peak_pnl", "drawdown_from_peak",
                 "max_drawdown", "longest_loss_run", "consecutive_wins"):
        assert f"{name}=" in text or f"{name}:" in text, (
            f"{name} is no longer defined in session_facts"
        )
