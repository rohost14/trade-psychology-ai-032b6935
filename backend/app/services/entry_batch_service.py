"""
Coalescing window for entry-time checks.

Entry checks used to run once per fill. That is wrong for three common cases,
all of which look identical to a burst of separate entries:

  * **Partial fills** — one 300-lot order completing in three fills.
  * **Multi-leg structures** — an iron condor arriving as four fills in two
    seconds. Naively that is four entries on four instruments.
  * **Split orders** — a trader deliberately slicing one intent into tickets.

So instead of evaluating per fill, the first opening fill starts a short window
and everything landing inside it is evaluated together, once. One mechanism,
three false-positive sources removed.

The window is *tumbling*, not sliding: the first fill fixes the deadline and
later fills join the same batch rather than extending it. A sliding window would
need to reschedule an already-queued Celery task, and the case it would buy —
a trader legging into a structure over minutes — is not solvable by any sane
window anyway. Grouping from open positions (E2) is what covers that.

Cost is a few seconds of latency on an alert a human reads, against a class of
alert that would have been wrong.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Redis key holding the fills accumulated in the current window.
_BATCH_KEY = "entry_batch:{account_id}"
#: Redis key marking that a flush is already scheduled for this account.
_PENDING_KEY = "entry_batch_pending:{account_id}"

#: Hard cap on fills kept per window. A trader filling more than this in a few
#: seconds is an event in itself; the count is preserved even when the detail is
#: trimmed, so nothing that matters for counting is lost.
MAX_BATCH_FILLS = 50

#: Safety TTLs. Both are far longer than the window: they exist so a crashed
#: flush cannot wedge an account permanently, not as timing control.
_BATCH_TTL_SEC = 300
_PENDING_TTL_SEC = 120


def _batch_key(account_id: str) -> str:
    return _BATCH_KEY.format(account_id=account_id)


def _pending_key(account_id: str) -> str:
    return _PENDING_KEY.format(account_id=account_id)


def add_fill(redis, account_id: str, fill: Dict[str, Any]) -> bool:
    """
    Record one opening fill in the account's current window.

    Returns True when this fill *opened* the window, meaning the caller owns
    scheduling the flush. Returns False when a window was already open — the
    fill has joined it and a flush is already queued.

    Raises on Redis failure; the caller falls back to evaluating inline, which
    is the pre-coalescing behaviour and never worse than not checking at all.
    """
    key = _batch_key(account_id)
    redis.rpush(key, json.dumps(fill, default=str))
    redis.ltrim(key, -MAX_BATCH_FILLS, -1)
    redis.expire(key, _BATCH_TTL_SEC)

    # SET NX is the whole concurrency story: exactly one caller gets True per
    # window, so exactly one flush is scheduled however many fills arrive.
    opened = bool(redis.set(_pending_key(account_id), 1, nx=True, ex=_PENDING_TTL_SEC))
    return opened


def release_window(redis, account_id: str) -> None:
    """
    Give up the claim on this window without draining it.

    Called when the caller won the SET NX but then failed to queue a flush —
    a broker outage, say. Leaving the marker set would mean every fill for the
    next two minutes joined a window nobody would ever process, and none of
    them would fall back to an inline check either.
    """
    try:
        redis.delete(_pending_key(account_id))
    except Exception:
        pass    # best effort; the TTL is the backstop


def drain(redis, account_id: str) -> List[Dict[str, Any]]:
    """
    Take everything in the window and clear it, atomically.

    Read-then-delete loses fills. A fill landing between the LRANGE and the
    DELETE was pushed onto a list that was about to be wiped, and because its
    SET NX succeeded it also scheduled a flush — which then drained an empty
    batch and returned early. That entry got no checks at all, silently.

    RENAME moves the list out of the way in one operation, so a fill arriving a
    microsecond later lands on a fresh key and belongs to the next window.
    The pending marker is cleared first for the same reason: that fill should
    be free to open a new window.
    """
    redis.delete(_pending_key(account_id))
    key = _batch_key(account_id)
    draining = f"{key}:draining"
    try:
        redis.rename(key, draining)
    except Exception:
        # RENAME errors when the source key does not exist — an empty window,
        # which is a normal outcome, not a failure.
        return []
    raw = redis.lrange(draining, 0, -1) or []
    redis.delete(draining)

    fills: List[Dict[str, Any]] = []
    for item in raw:
        try:
            fills.append(json.loads(item))
        except (ValueError, TypeError):
            logger.warning("[entry_batch] undecodable fill dropped for %s", account_id[:8])
    return fills


def summarise(fills: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Reduce a window to what the entry checks need.

    `symbols` is ordered and de-duplicated so a four-leg structure reports four
    instruments once each, and a partial fill of one order reports one.
    """
    symbols: List[str] = []
    for f in fills:
        sym = f.get("symbol")
        if sym and sym not in symbols:
            symbols.append(sym)
    return {
        "fill_count": len(fills),
        "symbols": symbols,
        "distinct_symbols": len(symbols),
        "scale_ins": [f.get("scale_in") for f in fills if f.get("scale_in")],
        "entry_types": [f.get("entry_type") for f in fills if f.get("entry_type")],
    }


def describe(symbols: List[str]) -> str:
    """
    How to name a batch in alert copy.

    One instrument is named. Several are counted and the first named, because
    "entered NIFTY25AUG24500CE" is a lie about a four-leg structure and listing
    all four is unreadable on a phone.
    """
    if not symbols:
        return "a position"
    if len(symbols) == 1:
        return symbols[0]
    return f"{len(symbols)} positions ({symbols[0]} +{len(symbols) - 1} more)"
