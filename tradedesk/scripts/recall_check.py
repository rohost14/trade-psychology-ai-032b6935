"""
Does the behaviour exist in the tradebook, and did the engine see it?

Every check so far asked "did the detector fire". That cannot find a detector
which is blind, because a blind detector is silent and silence looks like a
clean session. Martingale was silent across 61 real sessions belonging to a
trader who knew he had martingaled, and only his memory caught it.

This does the same thing mechanically. It reads the tradebook and counts the
behaviours DIRECTLY — no engine, no thresholds from trading_defaults, no shared
code with the detectors. Then the counts are compared against what the engine
reported for the same file. A gap is a recall problem with specific days
attached to it.

    python tradedesk/scripts/recall_check.py docs/tradebook.csv

Deliberately a SECOND IMPLEMENTATION. Everywhere else in this project a second
copy is the bug — here it is the instrument. If this shared code with the
engine it would share the engine's assumptions, and those assumptions are the
thing under test.

What it cannot do: decide whether a behaviour deserves an alert. It finds
candidates. Whether ten martingale sequences in three months should produce ten
alerts is a product judgement, and the trader's to make.
"""
from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def underlying(symbol: str) -> str:
    """Leading alphabetic run. Crude on purpose — no shared parser."""
    out = []
    for ch in symbol:
        if ch.isalpha():
            out.append(ch)
        else:
            break
    return "".join(out)


def round_trips(path: Path):
    """
    Completed round trips per day, built FIFO per symbol.

    Reconstructed here rather than read from the engine's CompletedTrade rows,
    so a fault in the engine's position tracking cannot hide itself.
    """
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            try:
                rows.append({
                    "sym": r["symbol"].strip().upper(),
                    "buy": r["trade_type"].lower().startswith("b"),
                    "qty": int(float(r["quantity"])),
                    "price": float(r["price"]),
                    "at": datetime.fromisoformat(r["order_execution_time"]),
                })
            except (KeyError, ValueError, TypeError):
                continue
    rows.sort(key=lambda x: x["at"])

    by_day = defaultdict(list)
    for r in rows:
        by_day[r["at"].date()].append(r)

    sessions = {}
    for day, day_rows in by_day.items():
        books, trips = defaultdict(list), []
        for r in day_rows:
            book = books[r["sym"]]
            qty = r["qty"]
            # Close against opposite-side lots first; whatever is left opens.
            while qty > 0 and book and book[0]["buy"] != r["buy"]:
                lot = book[0]
                take = min(qty, lot["qty"])
                pnl = ((r["price"] - lot["price"]) if lot["buy"]
                       else (lot["price"] - r["price"])) * take
                trips.append({
                    "sym": r["sym"], "und": underlying(r["sym"]), "qty": take,
                    "entry": lot["price"], "exit": r["price"], "pnl": pnl,
                    "value": lot["price"] * take,
                    "in": lot["at"], "out": r["at"],
                })
                lot["qty"] -= take
                qty -= take
                if lot["qty"] == 0:
                    book.pop(0)
            if qty > 0:
                book.append({"buy": r["buy"], "qty": qty,
                             "price": r["price"], "at": r["at"]})
        trips.sort(key=lambda t: t["out"])
        sessions[day] = trips
    return sessions


# ── The behaviours, defined from scratch ────────────────────────────────────

def martingale(trips):
    """Position VALUE rises >=1.5x after a loss, twice or more in a run."""
    hits = []
    for i in range(2, len(trips)):
        window = trips[i - 2:i + 1]
        losses = sum(1 for t in window[:-1] if t["pnl"] < 0)
        if losses < 2:
            continue
        values = [t["value"] for t in window]
        if any(values[j] >= values[j - 1] * 1.5 for j in range(1, len(values))):
            hits.append(window[-1])
    return hits


def size_escalation(trips):
    """Three consecutive trades of rising value, all losing."""
    return [trips[i] for i in range(2, len(trips))
            if all(t["pnl"] < 0 for t in trips[i - 2:i + 1])
            and trips[i - 2]["value"] < trips[i - 1]["value"] < trips[i]["value"]]


def recovery_bet(trips):
    """Two losses, then a position >=2x the recent average value."""
    hits = []
    for i in range(2, len(trips)):
        if not all(t["pnl"] < 0 for t in trips[i - 2:i]):
            continue
        avg = statistics.mean(t["value"] for t in trips[max(0, i - 3):i])
        if avg > 0 and trips[i]["value"] >= avg * 2:
            hits.append(trips[i])
    return hits


def revenge(trips):
    """Re-entry within 20 minutes of a loss over ₹500."""
    hits = []
    for i in range(1, len(trips)):
        prev = trips[i - 1]
        if prev["pnl"] >= -500:
            continue
        gap = (trips[i]["in"] - prev["out"]).total_seconds() / 60
        if 0 <= gap <= 20:
            hits.append(trips[i])
    return hits


def obsession(trips):
    """Three or more losses on one underlying in a session."""
    per = defaultdict(list)
    for t in trips:
        per[t["und"]].append(t)
    return [group[-1] for group in per.values()
            if sum(1 for t in group if t["pnl"] < 0) >= 3 and len(group) >= 4]


def giveaway(trips):
    """Ran a peak profit, then handed back 50% or more of it."""
    if not trips:
        return []
    running = peak = 0.0
    for t in trips:
        running += t["pnl"]
        peak = max(peak, running)
    if peak <= 0:
        return []
    given = peak - running
    return [trips[-1]] if given >= peak * 0.5 and given >= 500 else []


CHECKS = [
    ("martingale_behaviour", martingale),
    ("size_escalation", size_escalation),
    ("post_loss_recovery_bet", recovery_bet),
    ("revenge_trade", revenge),
    ("same_symbol_obsession", obsession),
    ("profit_giveaway", giveaway),
]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: recall_check.py <tradebook.csv>", file=sys.stderr)
        return 2
    sessions = round_trips(Path(sys.argv[1]))
    total_trips = sum(len(t) for t in sessions.values())
    print(f"{len(sessions)} sessions · {total_trips} round trips "
          f"(reconstructed independently of the engine)\n")

    print(f"{'behaviour':<28}{'days':>6}{'occurrences':>13}")
    print("-" * 47)
    findings = {}
    for name, fn in CHECKS:
        days, hits = 0, 0
        for day, trips in sessions.items():
            found = fn(trips)
            if found:
                days += 1
                hits += len(found)
        findings[name] = (days, hits)
        print(f"{name:<28}{days:>6}{hits:>13}")

    print("\nCompare against the engine's counts in the replay report.")
    print("A behaviour present here and absent there is a recall gap —")
    print("open those days before assuming the trader was clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
