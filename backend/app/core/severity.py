"""
The alert severity vocabulary — one definition, imported everywhere.

Why this module exists: severity started as two values (`caution`, `danger`) and
grew to four when engine v2 added `info` and `critical`. Every comparison written
against the old world kept compiling and kept running, silently meaning something
narrower than its author intended:

    if alert.severity != "danger": return False      # drops every critical alert
    any(a.severity == "danger" for a in alerts)      # a critical session reads "caution"
    title = "DANGER" if severity == "danger" else "Caution"   # critical labelled Caution

None of those raise. They just quietly exclude the most serious class we have.
A literal string comparison cannot be updated by a rename, so the fix is to stop
writing literals: ask this module the question instead.

`info` is analytics-only — recorded as evidence, never sent anywhere.
"""
from __future__ import annotations

from typing import Optional

#: Every severity the engine may emit, weakest first. Order is meaningful.
SEVERITY_ORDER: tuple[str, ...] = ("info", "caution", "danger", "critical")

#: Severities that may reach a notification channel (push, WhatsApp, guardian).
#: This is the set that `!= "danger"` was trying and failing to express.
NOTIFIABLE: frozenset[str] = frozenset({"danger", "critical"})

#: The top of the scale. Kept separate from NOTIFIABLE because "worth sending"
#: and "worst case" are different questions and will diverge again if conflated.
HIGHEST: str = "critical"


def rank(severity: Optional[str]) -> int:
    """
    Position on the scale; -1 for anything unrecognised.

    Unknown severities rank below `info` deliberately: a value we do not
    recognise must never sort above one we do, or a typo becomes an escalation.
    """
    try:
        return SEVERITY_ORDER.index((severity or "").lower())
    except ValueError:
        return -1


def is_notifiable(severity: Optional[str]) -> bool:
    """True when this severity is allowed to reach a notification channel."""
    return (severity or "").lower() in NOTIFIABLE


def at_least(severity: Optional[str], floor: str) -> bool:
    """True when `severity` is `floor` or worse. Unknown values are never severe."""
    r = rank(severity)
    return r >= 0 and r >= rank(floor)


def worst(severities) -> Optional[str]:
    """The most serious severity in an iterable, or None if none are recognised."""
    best: Optional[str] = None
    best_rank = -1
    for s in severities:
        r = rank(s)
        if r > best_rank:
            best, best_rank = (s or "").lower(), r
    return best if best_rank >= 0 else None


def label(severity: Optional[str]) -> str:
    """Human-facing word for a severity. Title case, no emoji, no shouting."""
    s = (severity or "").lower()
    return {
        "info": "Note",
        "caution": "Caution",
        "danger": "Danger",
        "critical": "Critical",
    }.get(s, "Alert")
