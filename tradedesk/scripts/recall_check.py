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
    python tradedesk/scripts/recall_check.py docs/tradebook.csv \
        --engine docs/tradebook-replay.json          # measured recall, per day

Deliberately a SECOND IMPLEMENTATION. Everywhere else in this project a second
copy is the bug — here it is the instrument. If this shared code with the
engine it would share the engine's assumptions, and those assumptions are the
thing under test.

What it cannot do: decide whether a behaviour deserves an alert. It finds
candidates. Whether ten martingale sequences in three months should produce ten
alerts is a product judgement, and the trader's to make.

ON THE DEFINITIONS BELOW. Each is deliberately crude and uses round human
numbers, chosen to describe the behaviour a trader would recognise rather than
to match any threshold in the engine. They are supposed to be a bit loose: a
checker tuned to agree with the engine measures nothing. Where a definition
needs a fact the export does not carry, it is marked INFERRED and the inference
is stated, so a gap on that row can be discounted rather than chased.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
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


def option_type(symbol: str) -> str | None:
    """CE / PE / None. The export has no instrument-type column."""
    tail = symbol.strip().upper()[-2:]
    return tail if tail in ("CE", "PE") else None


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
                expiry = None
                raw_expiry = (r.get("expiry_date") or "").strip()
                if raw_expiry:
                    try:
                        expiry = date.fromisoformat(raw_expiry)
                    except ValueError:
                        expiry = None
                rows.append({
                    "sym": r["symbol"].strip().upper(),
                    "buy": r["trade_type"].lower().startswith("b"),
                    "qty": int(float(r["quantity"])),
                    "price": float(r["price"]),
                    "at": datetime.fromisoformat(r["order_execution_time"]),
                    "expiry": expiry,
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
                    "opt": option_type(r["sym"]),
                    "long": lot["buy"],
                    "expiry": r["expiry"],
                })
                lot["qty"] -= take
                qty -= take
                if lot["qty"] == 0:
                    book.pop(0)
            if qty > 0:
                book.append({"buy": r["buy"], "qty": qty,
                             "price": r["price"], "at": r["at"]})
        # A symbol with lots still open at the close was carried overnight.
        # Same inference the replay makes, reached independently: flat by end
        # of day = intraday. Only the square-off checks depend on it.
        carried = {sym for sym, book in books.items() if book}
        for t in trips:
            t["intraday"] = t["sym"] not in carried
        trips.sort(key=lambda t: t["out"])
        sessions[day] = trips
    return sessions


# ── The behaviours, defined from scratch ────────────────────────────────────
#
# Six of these existed before and have found real defects. The other eleven
# cover every remaining pattern that fired at least once across a year, which
# were firing with nothing measuring what they missed. That unmeasured majority
# is exactly where martingale hid.

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


def loss_streak(trips):
    """Three losing round trips back to back, and every loss after that."""
    hits, run = [], 0
    for t in trips:
        run = run + 1 if t["pnl"] < 0 else 0
        if run >= 3:
            hits.append(t)
    return hits


def daily_overtrading(trips):
    """Eight or more completed round trips in one session."""
    return [trips[-1]] if len(trips) >= 8 else []


def overtrading_burst(trips):
    """Four or more ENTRIES inside any 30-minute window."""
    entries = sorted(trips, key=lambda t: t["in"])
    hits, seen = [], set()
    for i in range(len(entries)):
        window = [t for t in entries[i:]
                  if t["in"] - entries[i]["in"] <= timedelta(minutes=30)]
        if len(window) >= 4 and id(window[3]) not in seen:
            seen.add(id(window[3]))
            hits.append(window[3])
    return hits


def fomo_entry(trips):
    """Three or more DIFFERENT underlyings entered inside 15 minutes."""
    entries = sorted(trips, key=lambda t: t["in"])
    hits, seen_days = [], set()
    for i in range(len(entries)):
        window = [t for t in entries[i:]
                  if t["in"] - entries[i]["in"] <= timedelta(minutes=15)]
        unds = {t["und"] for t in window}
        if len(unds) >= 3:
            key = tuple(sorted(unds))
            if key not in seen_days:
                seen_days.add(key)
                hits.append(window[-1])
    return hits


def expiry_overtrading(trips):
    """Four or more round trips on instruments expiring THAT day."""
    expiring = [t for t in trips if t["expiry"] and t["expiry"] == t["out"].date()]
    return [expiring[-1]] if len(expiring) >= 4 else []


def direction_instability(trips):
    """
    Three or more CE<->PE flips on one underlying in a session.

    Flip counted between consecutive entries on the same underlying, which is
    the trader changing their mind about direction rather than running a spread
    (a spread is entered at once, not alternately).
    """
    per = defaultdict(list)
    for t in trips:
        if t["opt"]:
            per[t["und"]].append(t)
    hits = []
    for group in per.values():
        group.sort(key=lambda t: t["in"])
        flips = sum(1 for a, b in zip(group, group[1:]) if a["opt"] != b["opt"])
        if flips >= 3:
            hits.append(group[-1])
    return hits


def premium_avg_down(trips):
    """
    Re-entering the same option type on an underlying at a LOWER premium, after
    already losing on it that session. Buying it cheaper because it fell.
    """
    hits = []
    ordered = sorted(trips, key=lambda t: t["in"])
    for i, t in enumerate(ordered):
        if not t["opt"] or not t["long"]:
            continue
        prior = [p for p in ordered[:i]
                 if p["und"] == t["und"] and p["opt"] == t["opt"]
                 and p["pnl"] < 0 and p["out"] <= t["in"]]
        if prior and t["entry"] < min(p["entry"] for p in prior):
            hits.append(t)
    return hits


def premium_loss_event(trips):
    """A single bought option round trip losing half or more of the premium."""
    return [t for t in trips
            if t["opt"] and t["long"] and t["entry"] > 0
            and (t["entry"] - t["exit"]) / t["entry"] >= 0.5]


def winning_streak_overconfidence(trips):
    """Three wins in a row, then a position 1.5x the size of their average."""
    hits = []
    for i in range(3, len(trips)):
        run = trips[i - 3:i]
        if not all(t["pnl"] > 0 for t in run):
            continue
        avg = statistics.mean(t["value"] for t in run)
        if avg > 0 and trips[i]["value"] >= avg * 1.5:
            hits.append(trips[i])
    return hits


def late_session_entry(trips):
    """
    INFERRED. Entry after 15:00 on a position closed the same day — NFO squares
    off intraday positions at 15:25, so this is a trade with minutes to live.
    The export has no product column; "flat by end of day" stands in for MIS,
    the same inference the replay makes.
    """
    return [t for t in trips if t["intraday"] and t["in"].time().hour >= 15]


#: (name, function, note). Note is printed so a gap can be read against the
#: definition that produced it rather than assumed to be an engine fault.
CHECKS = [
    ("consecutive_loss_streak", loss_streak, "3 losses back to back"),
    ("revenge_trade", revenge, "re-entry <=20min after a loss >₹500"),
    ("daily_overtrading", daily_overtrading, ">=8 round trips in a session"),
    ("martingale_behaviour", martingale, "value >=1.5x after 2 losses"),
    ("fomo_entry", fomo_entry, ">=3 underlyings inside 15min"),
    ("same_symbol_obsession", obsession, ">=3 losses on one underlying"),
    ("expiry_day_overtrading", expiry_overtrading, ">=4 trips expiring that day"),
    ("profit_giveaway", giveaway, "gave back >=50% of session peak"),
    ("options_premium_avg_down", premium_avg_down, "re-entry cheaper after a loss"),
    ("direction_instability", direction_instability, ">=3 CE<->PE flips, one underlying"),
    ("premium_loss_event", premium_loss_event, "one option lost >=50% of premium"),
    ("overtrading_burst", overtrading_burst, ">=4 entries inside 30min"),
    ("size_escalation", size_escalation, "3 rising, all losing"),
    ("end_of_session_mis_panic", late_session_entry, "INFERRED: entry after 15:00, flat by close"),
    ("winning_streak_overconfidence", winning_streak_overconfidence, "3 wins, then 1.5x size"),
    ("post_loss_recovery_bet", recovery_bet, "2 losses, then >=2x average"),
]

#: death_spiral is a composite — it claims several behavioural domains are
#: deteriorating at once. Counting it needs the other answers, so it runs after
#: them, over this checker's own findings rather than the engine's.
SPIRAL_DOMAINS = {
    "consecutive_loss_streak", "revenge_trade", "martingale_behaviour",
    "size_escalation", "same_symbol_obsession", "post_loss_recovery_bet",
    "daily_overtrading", "overtrading_burst", "profit_giveaway",
}
SPIRAL_MIN_DOMAINS = 3


def load_engine(path: Path):
    """Per-day pattern types from a replay run. Output, never engine code."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {date.fromisoformat(d): set(p) for d, p in data["days"].items()}, data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--engine", type=Path, default=None,
                    help="the -replay.json sidecar, to measure recall per day")
    ap.add_argument("--show-missed", type=int, default=6,
                    help="how many missed days to name per behaviour (0 = none)")
    args = ap.parse_args()

    sessions = round_trips(args.csv)
    total_trips = sum(len(t) for t in sessions.values())
    print(f"{len(sessions)} sessions · {total_trips} round trips "
          f"(reconstructed independently of the engine)\n")

    # Findings first, keyed by day, so the composite and the recall maths can
    # both work off the same set.
    days_with: dict[str, set] = {}
    occurrences: dict[str, int] = {}
    for name, fn, _note in CHECKS:
        hit_days, count = set(), 0
        for day, trips in sessions.items():
            found = fn(trips)
            if found:
                hit_days.add(day)
                count += len(found)
        days_with[name] = hit_days
        occurrences[name] = count

    spiral_days = {
        day for day in sessions
        if sum(1 for n in SPIRAL_DOMAINS if day in days_with[n]) >= SPIRAL_MIN_DOMAINS
    }
    days_with["death_spiral"] = spiral_days
    occurrences["death_spiral"] = len(spiral_days)
    order = [n for n, _f, _n2 in CHECKS] + ["death_spiral"]
    notes = {n: note for n, _f, note in CHECKS}
    notes["death_spiral"] = f">={SPIRAL_MIN_DOMAINS} of the above on one day"

    engine_days, meta = ({}, None)
    if args.engine:
        engine_days, meta = load_engine(args.engine)
        missing = set(sessions) - set(engine_days)
        if missing:
            print(f"note: {len(missing)} session(s) in the CSV are absent from the "
                  f"replay — it was probably run with --days. Recall is measured "
                  f"over the {len(sessions) - len(missing)} shared sessions only.\n")

    if not engine_days:
        print(f"{'behaviour':<32}{'days':>6}{'occurrences':>13}  definition")
        print("-" * 96)
        for name in order:
            print(f"{name:<32}{len(days_with[name]):>6}{occurrences[name]:>13}"
                  f"  {notes[name]}")
        print("\nNo engine counts supplied, so nothing is measured yet. Run the")
        print("replay to produce the sidecar, then pass --engine <file>-replay.json.")
        return 0

    shared = sorted(set(sessions) & set(engine_days))
    shared_set = set(shared)
    print(f"Recall over {len(shared)} sessions replayed from the same file.\n")
    print(f"{'behaviour':<32}{'behav':>6}{'engine':>7}{'both':>6}{'recall':>8}"
          f"   definition")
    print("-" * 104)

    gaps = []
    for name in order:
        b_days = days_with[name] & shared_set
        e_days = {d for d in shared if name in engine_days[d]}
        both = b_days & e_days
        recall = (len(both) / len(b_days) * 100) if b_days else None
        recall_s = f"{recall:.0f}%" if recall is not None else "—"
        print(f"{name:<32}{len(b_days):>6}{len(e_days):>7}{len(both):>6}"
              f"{recall_s:>8}   {notes[name]}")
        if b_days - e_days:
            gaps.append((name, sorted(b_days - e_days), len(b_days)))

    # An engine day with no behaviour found is not automatically a false
    # positive — this checker is cruder than the engine and misses things it
    # catches. It is only ever a question worth opening.
    unmatched = [(n, sorted({d for d in shared if n in engine_days[d]} -
                            (days_with.get(n, set()) & shared_set)))
                 for n in order]
    unmatched = [(n, d) for n, d in unmatched if d]

    if args.show_missed and gaps:
        print("\nDays where the behaviour is present and the engine said nothing.")
        print("Open these before assuming the detector is fine.\n")
        for name, missed, total in sorted(gaps, key=lambda g: -len(g[1])):
            shown = ", ".join(str(d) for d in missed[:args.show_missed])
            more = f" (+{len(missed) - args.show_missed} more)" \
                if len(missed) > args.show_missed else ""
            print(f"  {name}  —  {len(missed)}/{total} days missed")
            print(f"    {shown}{more}")

    if args.show_missed and unmatched:
        print("\nThe other direction: engine fired, this checker found nothing.")
        print("Usually this checker being cruder, sometimes a false positive.\n")
        for name, extra in sorted(unmatched, key=lambda g: -len(g[1])):
            shown = ", ".join(str(d) for d in extra[:args.show_missed])
            more = f" (+{len(extra) - args.show_missed} more)" \
                if len(extra) > args.show_missed else ""
            print(f"  {name}  —  {len(extra)} day(s): {shown}{more}")

    silent = [n for n in order if not (days_with[n] & shared_set)
              and not {d for d in shared if n in engine_days[d]}]
    if silent:
        print(f"\nNeither side saw these at all: {', '.join(silent)}.")
        print("Cannot tell a clean trader from a starved baseline — a longer "
              "file is the only thing that answers it.")

    if meta and meta.get("skipped_patterns"):
        print(f"\nExcluded from the replay, so unmeasurable here: "
              f"{', '.join(meta['skipped_patterns'])}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
