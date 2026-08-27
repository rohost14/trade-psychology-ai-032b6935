"""
Pattern #10 - `size_escalation`, measured.

The claim, as shown to the trader:

  "NIFTY: position size increased across 3 consecutive trades while losing —
   1500->2250->3000 qty (SYM1 / SYM2 / SYM3)."

WHAT TO MEASURE

  1. what it fires on, and which of the two branches (same-underlying by
     QUANTITY vs any-instrument by NOTIONAL) produced it
  2. THE WINDOW QUESTION. `prior` excludes `ct`. The detector fires ON the trade
     that just closed but describes the THREE TRADES BEFORE IT. Does the
     triggering trade appear in its own alert?
  3. "while losing" = `sum(1 for p in pnls[:2] if p < 0) >= 1` - only the first
     TWO of three, and only one loss needed. What is the base rate of that
     condition? If it is near-universal it is not a condition.
  4. the shuffle null: preserve each session's trades and sizes, permute the
     ORDER, run the REAL detector. Escalation is a claim about sequence, so if
     the real order fires no more than a shuffled one, the sequence carries
     nothing.
  5. does it predict anything - outcome after a firing vs the session baseline
  6. threshold sensitivity: how much does 30 actually decide?
"""
import random
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tradedesk.scripts.replay_tradebook import read_fills, carry_fills  # noqa: E402
from app.services.behavior_engine import BehaviorEngine, EngineContext  # noqa: E402
from app.services.instrument_parser import parse_symbol  # noqa: E402

engine = BehaviorEngine()
IST = ZoneInfo("Asia/Kolkata")


def meta(sym):
    try:
        p = parse_symbol(sym or "")
        return (p.instrument_type or "EQ"), (p.underlying or sym or "")
    except Exception:
        return "EQ", sym or ""


def build(day_fills, carry):
    st = defaultdict(lambda: {"qty": 0, "avg": 0.0, "opened": None, "pnl": 0.0})
    out = []
    for f in list(carry) + list(day_fills):
        sym = f["symbol"]
        p = st[sym]
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
        c = min(abs(s), abs(p["qty"]))
        d = 1 if p["qty"] > 0 else -1
        p["pnl"] += (px - p["avg"]) * c * d
        p["qty"] += s
        if p["qty"] == 0:
            it, und = meta(sym)
            out.append(SimpleNamespace(
                id=uuid4(), broker_account_id=None, tradingsymbol=sym,
                exchange="NFO", product="MIS", instrument_type=it,
                direction="LONG" if d > 0 else "SHORT", total_quantity=abs(c),
                avg_entry_price=Decimal(str(round(p["avg"], 4))),
                avg_exit_price=Decimal(str(px)),
                realized_pnl=Decimal(str(round(p["pnl"], 2))),
                pnl_pct=None, duration_minutes=None,
                entry_time=p["opened"], exit_time=f["at"],
                num_entries=1, num_exits=1, closed_by_flip=False,
                status="closed", quality_score=None))
            p.update(qty=0, avg=0.0, opened=None, pnl=0.0)
    return [t for t in out if t.exit_time and t.exit_time.date() == day_fills[0]["date"]]


def load():
    fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    fills.sort(key=lambda f: f["at"])
    byday = defaultdict(list)
    for f in fills:
        byday[f["date"]].append(f)
    sessions = []
    for day in sorted(byday):
        ts = build(byday[day], carry_fills(fills, day))
        if ts:
            ts.sort(key=lambda t: t.entry_time or t.exit_time)
            sessions.append((day, ts))
    return sessions


def run(sessions, thresholds=None):
    """Run the REAL detector over every session, in order. Returns firings."""
    out = []
    for day, ts in sessions:
        for i, ct in enumerate(ts):
            ctx = EngineContext(
                broker_account_id=uuid4(),
                session=SimpleNamespace(session_pnl=Decimal("0"),
                                        session_date=day, market_open=None),
                completed_trade=ct, session_trades=ts[:i],
                active_cooldowns=[], thresholds=thresholds or {})
            ev = engine._detect_size_escalation(ctx)
            if ev:
                out.append((day, i, ct, ts, ev))
    return out


def main():
    sessions = load()
    allp = [t for _, ts in sessions for t in ts]
    print(f"{len(sessions)} sessions, {len(allp)} positions")

    fired = run(sessions)

    # ── 1. what fires ────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("1. WHAT IT FIRES")
    print("=" * 78)
    days = {d for d, *_ in fired}
    print(f"  detections: {len(fired)} on {len(days)} of {len(sessions)} sessions")
    cross = sum(1 for *_, ev in fired if ev.context["cross_instrument"])
    print(f"  branch: same-underlying by QUANTITY {len(fired)-cross}"
          f"   |   any-instrument by NOTIONAL {cross}")
    print(f"  severity: {dict(Counter(ev.severity for *_, ev in fired))}")
    esc = sorted(ev.context["escalation_pct"] for *_, ev in fired)
    if esc:
        print(f"  escalation_pct: min {esc[0]:.0f}  median {esc[len(esc)//2]:.0f}  max {esc[-1]:.0f}")

    # ── 2. the window question ───────────────────────────────────────────
    print("\n" + "=" * 78)
    print("2. IS THE TRIGGERING TRADE IN ITS OWN ALERT?")
    print("=" * 78)
    inside = 0
    for day, i, ct, ts, ev in fired:
        syms = [t["symbol"] for t in ev.context["trade_list"]]
        qtys = [t["qty"] for t in ev.context["trade_list"]]
        if (ct.tradingsymbol in syms) and (ct.total_quantity in qtys):
            inside += 1
    print(f"  firings whose reported 3-trade sequence contains the trade that")
    print(f"  triggered them: {inside} of {len(fired)}")
    print("  `prior` is built from ctx.session_trades, which EXCLUDES ct, so the")
    print("  alert describes trades N-3,N-2,N-1 and is raised on trade N.")

    # how often does the SAME sequence re-fire on consecutive trades?
    seqs = defaultdict(list)
    for day, i, ct, ts, ev in fired:
        seqs[(day, tuple(ev.context["size_sequence"]))].append(i)
    repeat = {k: v for k, v in seqs.items() if len(v) > 1}
    print(f"\n  identical size sequences that fired more than once in a session: "
          f"{len(repeat)}")

    # ── 3. the "while losing" condition ──────────────────────────────────
    print("\n" + "=" * 78)
    print('3. THE "WHILE LOSING" CONDITION - how much does it exclude?')
    print("=" * 78)
    print("  code: losses_before = sum(1 for p in pnls[:2] if p < 0) >= 1")
    print("  -> only the FIRST TWO of the three trades, and ONE loss is enough.")
    pnls = [float(t.realized_pnl) for t in allp]
    lossrate = sum(1 for p in pnls if p < 0) / len(pnls)
    print(f"\n  book-wide loss rate: {100*lossrate:.1f}%")
    print(f"  P(at least one loss in two trades) if independent: "
          f"{100*(1-(1-lossrate)**2):.1f}%")
    # measured directly on the escalating windows
    both = one = none = 0
    for day, i, ct, ts, ev in fired:
        tl = ev.context["trade_list"]
        n = sum(1 for t in tl[:2] if t["pnl"] < 0)
        both += (n == 2); one += (n == 1); none += (n == 0)
    print(f"  among firings: 2 losses {both}, exactly 1 loss {one}, 0 losses {none}")
    third_loss = sum(1 for *_, ev in fired if ev.context["trade_list"][2]["pnl"] < 0)
    print(f"  the THIRD trade (unchecked by the code) was a loss in "
          f"{third_loss} of {len(fired)}")

    # ── 4. the shuffle null ──────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("4. SHUFFLE NULL - does the real ORDER carry the signal?")
    print("=" * 78)
    print("  Same trades, same sizes, same P&L, same day. Only the sequence")
    print("  changes. The REAL detector runs inside the loop.")
    rnd = random.Random(7)
    N = 200
    counts = []
    for _ in range(N):
        shuffled = []
        for day, ts in sessions:
            s = ts[:]
            rnd.shuffle(s)
            shuffled.append((day, s))
        counts.append(len(run(shuffled)))
    exp = sum(counts) / len(counts)
    counts.sort()
    lo, hi = counts[int(0.025 * N)], counts[int(0.975 * N)]
    obs = len(fired)
    more = sum(1 for c in counts if c >= obs)
    print(f"\n  observed (real order): {obs}")
    print(f"  shuffled: mean {exp:.1f}   95% range [{lo}, {hi}]   n={N} shuffles")
    print(f"  ratio observed/expected: {obs/exp:.2f}")
    print(f"  p(shuffled >= observed) = {more/N:.3f}")

    # ── 5. does it predict anything ──────────────────────────────────────
    print("\n" + "=" * 78)
    print("5. DOES A FIRING PREDICT A WORSE OUTCOME?")
    print("=" * 78)
    fired_ids = {id(ct) for _, _, ct, _, _ in fired}
    # the trade the alert fires ON
    a = [float(ct.realized_pnl) for _, _, ct, _, _ in fired]
    # every other trade that was at index >=3 in its session (same eligibility)
    b = []
    for day, ts in sessions:
        for i, t in enumerate(ts):
            if i >= 3 and id(t) not in fired_ids:
                b.append(float(t.realized_pnl))

    def stat(v, label):
        w = sum(1 for x in v if x > 0)
        print(f"  {label:<44} n={len(v):<5} win {100*w/len(v):>5.1f}%  "
              f"mean Rs {sum(v)/len(v):>9,.0f}")

    stat(a, "the trade a firing is raised on")
    stat(b, "other trades at index >=3 (same eligibility)")
    obsd = sum(a) / len(a) - sum(b) / len(b)
    pool = a + b
    rnd2 = random.Random(7)
    hits = 0
    for _ in range(20000):
        rnd2.shuffle(pool)
        if abs(sum(pool[:len(a)]) / len(a) - sum(pool[len(a):]) / len(b)) >= abs(obsd):
            hits += 1
    print(f"  difference Rs {obsd:,.0f}/trade   p = {hits/20000:.3f}")

    # rest-of-session after a firing
    print("\n  Rest-of-session P&L after the first firing of a day:")
    after, noalert = [], []
    firstfire = {}
    for day, i, ct, ts, ev in fired:
        firstfire.setdefault(day, i)
    for day, ts in sessions:
        if day in firstfire:
            k = firstfire[day]
            after.append(sum(float(t.realized_pnl) for t in ts[k + 1:]))
        elif len(ts) >= 4:
            noalert.append(sum(float(t.realized_pnl) for t in ts[4:]))
    if after:
        print(f"    after a size_escalation firing   n={len(after):<4} "
              f"mean Rs {sum(after)/len(after):>9,.0f}")
    if noalert:
        print(f"    sessions that never fired        n={len(noalert):<4} "
              f"mean Rs {sum(noalert)/len(noalert):>9,.0f}")

    # ── 6. threshold sensitivity ─────────────────────────────────────────
    print("\n" + "=" * 78)
    print("6. HOW MUCH DOES THE 30% THRESHOLD DECIDE?")
    print("=" * 78)
    for t in (0, 10, 20, 30, 40, 50, 75, 100):
        n = len(run(sessions, {"size_escalation_pct": t}))
        print(f"    threshold {t:>3}%  ->  {n:>3} firings")
    print("\n  The gate before it is sizes[0] < sizes[1] < sizes[2], strictly")
    print("  increasing. Everything the threshold can remove is already inside")
    print("  that set.")


main()
