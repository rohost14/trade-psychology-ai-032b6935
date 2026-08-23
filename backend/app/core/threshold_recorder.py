"""
Record which thresholds a detector actually read, and where each came from.

THE PROBLEM THIS SOLVES

An alert stores its message, its severity and the detector's own free-form
context. It does not store the numbers it was judged against. That was tolerable
while every threshold was a constant in a file — you could go and read it. It is
not tolerable now: thresholds resolve through a six-rung ladder, personal
baselines move as the trader trades, and adaptation is capped per period. The
value that fired an alert on Tuesday may not exist anywhere by Friday.

So "why did this fire?" becomes unanswerable, for the trader and for us. Worse,
it becomes unanswerable *silently* — the alert still renders, it just cannot be
checked.

HOW

`RecordingThresholds` is a dict that remembers which keys were read. The engine
resets it before each detector and reads back the keys afterwards, so all 27
detectors record their inputs without one of them being modified. Detectors that
read nothing record nothing.

What gets stored per key is the value, the ladder rung that produced it, and its
Kind — so an alert can later be shown as "5 losses against your limit of 4,
which came from your own declared rule" rather than "5 losses against 4".

WHAT THIS IS NOT

Not a general audit log. It records the thresholds a detector READ, which is a
proxy for the thresholds it USED — a detector that reads a key and ignores it
still records it. That over-records rather than under-records, which is the
right direction for an explanation: a number that turns out to be irrelevant is
a smaller problem than a missing one.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Set


class RecordingThresholds(dict):
    """
    The threshold dict, plus a note of which keys were looked at.

    Subclasses dict so every existing detector keeps working untouched — they
    call `.get(key, default)` and neither know nor care that the read was noted.
    """

    def __init__(self, values: Dict[str, Any], meta: Optional[Dict[str, Any]] = None):
        super().__init__(values)
        #: key -> Resolved, from the resolution ladder. May be empty when a
        #: caller supplied plain values, in which case provenance is simply
        #: unknown and says so rather than being invented.
        self._meta: Dict[str, Any] = meta or {}
        self._read: Set[str] = set()

    # -- dict surface: every read path has to be noted, not just the common one --

    def get(self, key, default=None):
        self._read.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self._read.add(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        # A detector branching on presence has used the key to make its decision
        # just as surely as one that reads the value.
        self._read.add(key)
        return super().__contains__(key)

    # -- recording control, driven by the engine --

    def start_recording(self) -> None:
        self._read = set()

    def keys_read(self) -> Set[str]:
        return set(self._read)

    def provenance(self, keys: Optional[Iterable[str]] = None) -> Dict[str, Dict[str, Any]]:
        """
        What the given keys were, and where they came from.

        Keys the detector read but that do not exist in the threshold set are
        skipped: a `.get("maybe_key")` that returned None says nothing worth
        storing. Keys that exist but have no provenance record are reported with
        `source: "unknown"` rather than omitted — a threshold whose origin we
        cannot state is exactly the thing worth flagging.
        """
        out: Dict[str, Dict[str, Any]] = {}
        for key in sorted(keys if keys is not None else self._read):
            if key not in dict(self):
                continue
            entry: Dict[str, Any] = {"value": _plain(dict(self)[key])}
            resolved = self._meta.get(key)
            if resolved is None:
                entry["source"] = "unknown"
            else:
                entry["source"] = _name(getattr(resolved, "source", None))
                kind = getattr(resolved, "kind", None)
                if kind is not None:
                    entry["kind"] = _name(kind)
                confidence = getattr(resolved, "confidence", None)
                if confidence:
                    entry["confidence"] = round(float(confidence), 3)
                detail = getattr(resolved, "detail", None)
                if detail:
                    entry["detail"] = str(detail)
                # A threshold whose Kind says "personal" but whose Source says
                # "global" is not a contradiction - Kind is what it IS, Source is
                # where it resolved THIS time - but read side by side it looks
                # like one, and the honest reading matters: the trader is being
                # judged by a default because they have no history yet, not by
                # anything of theirs. Say so rather than leaving it to be
                # inferred from two enum names.
                is_personal_kind = entry.get("kind", "").startswith("personal")
                if is_personal_kind and entry.get("source") == "global":
                    entry["personalised"] = False
                    entry["note"] = (
                        "meant to be personal; using the shared default until "
                        "there is enough of this trader's history"
                    )
            out[key] = entry
        return out


def _name(value) -> Optional[str]:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _plain(value):
    """JSON-safe. Evidence is stored as JSONB and must survive the round trip."""
    from decimal import Decimal

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    return str(value)
