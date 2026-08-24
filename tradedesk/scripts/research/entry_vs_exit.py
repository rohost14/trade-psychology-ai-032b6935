"""
Pattern #3: what does entry-triggering actually change?

The question is not "is entry better in principle" - it is whether, on this
book, the entry moment arrives EARLIER, later, or never. 24 of 49 firings
involve overlapping positions, and at the entry of attempt N some priors may
still be open, so their losses are not yet known. Entry-time can be later.

Measured per episode: the wall-clock moment an exit-triggered detector would
speak, against the moment an entry-triggered one would.
"""
import sys
from collections import Counter, defaultdict
from decimal import Decimal

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tradedesk.scripts.replay_tradebook import read_fills  # noqa: E402
from app.services.instrument_parser import parse_symbol  # noqa: E402

MIN_LOSSES = 3


def und(sym):
    try:
        return parse_symbol(sym or "").underlying or sym or ""
    except Exception:
        return sym or ""


def positions(fills):
    """open -> flat, keeping entry and exit times."""
    st = defaultdict(lambda: {"qty": 0, "avg": 0.0, "opened": None, "pnl": 0.0})
    out = []
    for f in fills:
        k = (f["date"], f["symbol"])
        p = st[k]
        s = f["qty"] if f["side"] == "BUY" else -f["qty"]
        px = float(f["price"])
        if p["qty"] == 0:
            p.update(qty=s, avg=px, opened=f["at"], pnl=0.0)
            continue
        if (p["qty"] > 0) == (s > 0):
            nq = p["qty"] + s
            p["avg"] = (p["avg"] * abs(p["qty"]) + px * abs(s)) / abs(nq)
            p["qty"] = nq
            continue
        closing = min(abs(s), abs(p["qty"]))
        d = 1 if p["qty"] > 0 else -1
        p["pnl"] += (px - p["avg"]) * closing * d
        p["qty"] += s
        if p["qty"] == 0:
            out.append({"symbol": f["symbol"], "und": und(f["symbol"]),
                        "qty": abs(closing), "pnl": round(p["pnl"], 2),
                        "entry": p["opened"], "exit": f["at"]})
            p.update(qty=0, avg=0.0, opened=None, pnl=0.0)
    return out


def main():
    fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    fills.sort(key=lambda f: f["at"])
    byday = defaultdict(list)
    for f in fills:
        byday[f["date"]].append(f)

    verdict = Counter()
    gains = []
    detail = []

    for day in sorted(byday):
        ps = positions(byday[day])
        if not ps:
            continue
        by_und = defaultdict(list)
        for p in ps:
            by_und[p["und"]].append(p)

        for u, group in by_und.items():
            # ── EXIT trigger: the moment the 3rd loss CLOSES ──────────────
            by_exit = sorted(group, key=lambda p: p["exit"])
            losses = 0
            exit_moment = None
            for p in by_exit:
                if p["pnl"] < 0:
                    losses += 1
                    if losses == MIN_LOSSES:
                        exit_moment = p["exit"]
                        break
            if exit_moment is None:
                continue          # never fires either way

            # ── ENTRY trigger: opening a position when 3 prior CLOSED
            #    positions on this underlying have already lost ────────────
            by_entry = sorted(group, key=lambda p: p["entry"])
            entry_moment = None
            for cand in by_entry:
                closed_losses = sum(
                    1 for q in group
                    if q is not cand and q["exit"] <= cand["entry"] and q["pnl"] < 0)
                if closed_losses >= MIN_LOSSES:
                    entry_moment = cand["entry"]
                    break

            if entry_moment is None:
                verdict["entry NEVER fires"] += 1
                detail.append((str(day), u, "never", None))
                continue
            delta = (exit_moment - entry_moment).total_seconds() / 60
            if delta > 0:
                verdict["entry is EARLIER"] += 1
                gains.append(delta)
            elif delta < 0:
                verdict["entry is LATER"] += 1
            else:
                verdict["same moment"] += 1
            detail.append((str(day), u, "earlier" if delta > 0 else
                           ("later" if delta < 0 else "same"), round(delta)))

    total = sum(verdict.values())
    print(f"episodes where the exit trigger fires: {total}\n")
    for k, v in verdict.most_common():
        print(f"  {k:<22} {v:>3}  ({100*v/total:.0f}%)")

    if gains:
        gains.sort()
        print(f"\nwhen entry is earlier, by how long (minutes of open exposure "
              f"the trader is told sooner):")
        print(f"  min {gains[0]:.0f}   p25 {gains[len(gains)//4]:.0f}   "
              f"median {gains[len(gains)//2]:.0f}   "
              f"p75 {gains[3*len(gains)//4]:.0f}   max {gains[-1]:.0f}")

    print("\nper episode:")
    for d, u, kind, mins in detail:
        m = f"{mins:+} min" if mins is not None else "-"
        print(f"  {d} {u:<11} {kind:<8} {m}")


main()
