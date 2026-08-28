"""
Pattern #11 - `direction_instability`, measured.

The claim, as shown to the trader:

  "NIFTY: flipped CE->PE in 4min after a loss on that view."
  "SYMBOL: direction reversed LONG->SHORT within 6min - 4 direction changes
   this session."

Registry copy: "Switching between long and short on the same underlying in a
short window. Reversing repeatedly usually tracks the price rather than a view
about it."

WHAT TO MEASURE

  1. what it fires on: level 1 (exact symbol reversal) vs level 2 (CE<->PE on one
     underlying) vs level 3 (>=3 flips -> danger)
  2. base rate - how often does this trader flip at all, and does the 10-minute
     window decide anything?
  3. THE CONSEQUENCE CLAIM. Is the trade entered after a flip worse than one
     entered after a non-flip? If not, the alert has no claim to make.
  4. does "reversing tracks price rather than a view" show up as flips being
     concentrated after LOSSES specifically?
  5. window sensitivity
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
        sym = f["symbol"]; p = st[sym]
        s = f["qty"] if f["side"] == "BUY" else -f["qty"]
        px = float(f["price"])
        if p["qty"] == 0:
            p.update(qty=s, avg=px, opened=f["at"], pnl=0.0); continue
        if (p["qty"] > 0) == (s > 0):
            nq = p["qty"] + s
            p["avg"] = (p["avg"] * abs(p["qty"]) + px * abs(s)) / abs(nq)
            p["qty"] = nq; continue
        c = min(abs(s), abs(p["qty"])); d = 1 if p["qty"] > 0 else -1
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
    out = []
    for day in sorted(byday):
        ts = build(byday[day], carry_fills(fills, day))
        if ts:
            ts.sort(key=lambda t: t.entry_time or t.exit_time)
            out.append((day, ts))
    return out


def run(sessions, th=None):
    fired = []
    for day, ts in sessions:
        for i, ct in enumerate(ts):
            ctx = EngineContext(
                broker_account_id=uuid4(),
                session=SimpleNamespace(session_pnl=Decimal("0"),
                                        session_date=day, market_open=None),
                completed_trade=ct, session_trades=ts[:i],
                active_cooldowns=[], thresholds=th or {})
            ev = engine._detect_direction_instability(ctx)
            if ev:
                fired.append((day, i, ct, ev))
    return fired


def main():
    sessions = load()
    allp = [t for _, ts in sessions for t in ts]
    print(f"{len(sessions)} sessions, {len(allp)} positions\n")

    fired = run(sessions)
    print("=" * 78); print("1. WHAT IT FIRES"); print("=" * 78)
    days = {d for d, *_ in fired}
    print(f"  detections: {len(fired)} on {len(days)} of {len(sessions)} sessions")
    print(f"  severity : {dict(Counter(ev.severity for *_, ev in fired))}")
    print(f"  level    : {dict(Counter(ev.context['level'] for *_, ev in fired))}")
    print(f"  flip_kind: {dict(Counter(ev.context['flip_kind'] for *_, ev in fired))}")
    gaps = sorted(ev.context["gap_minutes"] for *_, ev in fired)
    if gaps:
        print(f"  gap (min): min {gaps[0]:.1f}  median {gaps[len(gaps)//2]:.1f}  max {gaps[-1]:.1f}")
    aft_loss = sum(1 for *_, ev in fired if ev.context["prior_pnl"] < 0)
    print(f"  flips where the PRIOR trade lost: {aft_loss} of {len(fired)}")
    print("\n  What the trader reads (first 5):")
    for *_, ev in fired[:5]:
        print(f"    [{ev.severity:>7}] {ev.message}")

    # ── 2. base rate ─────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("2. BASE RATE — how much flipping is there, and does 10 min decide?")
    print("=" * 78)

    def flips_at(window):
        """count consecutive-pair flips in the book at a given window"""
        n = 0
        for day, ts in sessions:
            for a, b in zip(ts, ts[1:]):
                if not (a.exit_time and b.entry_time):
                    continue
                gap = (b.entry_time - a.exit_time).total_seconds() / 60
                if gap < 0:
                    continue
                exact = (a.tradingsymbol == b.tradingsymbol
                         and a.direction != b.direction and gap < window)
                und = (a.instrument_type in ("CE", "PE") and b.instrument_type in ("CE", "PE")
                       and a.instrument_type != b.instrument_type
                       and a.direction == "LONG" and b.direction == "LONG"
                       and meta(a.tradingsymbol)[1] == meta(b.tradingsymbol)[1]
                       and gap < window)
                n += bool(exact or und)
        return n

    print(f"    {'window':>8}{'flips':>8}")
    for w in (1, 2, 5, 10, 15, 30, 60, 100000):
        lbl = "no limit" if w == 100000 else f"{w}m"
        print(f"    {lbl:>8}{flips_at(w):>8}")
    print("\n  The last row is every direction reversal regardless of timing.")
    print("  The gap between it and 10m is what the window actually excludes.")

    # ── 3. the consequence claim ─────────────────────────────────────────
    print("\n" + "=" * 78)
    print("3. IS THE TRADE ENTERED AFTER A FLIP WORSE?")
    print("=" * 78)
    flip_ids = {id(ct) for _, _, ct, _ in fired}
    a = [float(ct.realized_pnl) for _, _, ct, _ in fired]
    b = []
    for day, ts in sessions:
        for i, t in enumerate(ts):
            if i >= 1 and id(t) not in flip_ids:
                b.append(float(t.realized_pnl))

    def stat(v, label):
        if not v:
            print(f"  {label:<44} n=0"); return
        w = sum(1 for x in v if x > 0)
        print(f"  {label:<44} n={len(v):<5} win {100*w/len(v):>5.1f}%  "
              f"mean Rs {sum(v)/len(v):>9,.0f}")

    stat(a, "the trade the flip alert fires on")
    stat(b, "every other trade after the session's first")

    if a and b:
        obs = sum(a)/len(a) - sum(b)/len(b)
        pool = a + b; rnd = random.Random(7); hits = 0
        for _ in range(20000):
            rnd.shuffle(pool)
            if abs(sum(pool[:len(a)])/len(a) - sum(pool[len(a):])/len(b)) >= abs(obs):
                hits += 1
        print(f"  difference Rs {obs:,.0f}/trade   p = {hits/20000:.3f}")

        wa = sum(1 for x in a if x > 0)/len(a); wb = sum(1 for x in b if x > 0)/len(b)
        pool2 = [1 if x > 0 else 0 for x in a+b]; rnd = random.Random(7); hits = 0
        for _ in range(20000):
            rnd.shuffle(pool2)
            if abs(sum(pool2[:len(a)])/len(a) - sum(pool2[len(a):])/len(b)) >= abs(wa-wb):
                hits += 1
        print(f"  win-rate difference {100*(wa-wb):+.1f}pp   p = {hits/20000:.3f}")

    # ── 4. does it concentrate after losses? ─────────────────────────────
    print("\n" + "=" * 78)
    print("4. DOES FLIPPING FOLLOW LOSSES? (the emotional claim)")
    print("=" * 78)
    # every consecutive pair: did the prior lose, and was it a flip?
    tot_after_loss = tot_after_win = flip_after_loss = flip_after_win = 0
    for day, ts in sessions:
        for x, y in zip(ts, ts[1:]):
            if not (x.exit_time and y.entry_time):
                continue
            gap = (y.entry_time - x.exit_time).total_seconds() / 60
            if gap < 0:
                continue
            exact = (x.tradingsymbol == y.tradingsymbol
                     and x.direction != y.direction and gap < 10)
            und = (x.instrument_type in ("CE", "PE") and y.instrument_type in ("CE", "PE")
                   and x.instrument_type != y.instrument_type
                   and x.direction == "LONG" and y.direction == "LONG"
                   and meta(x.tradingsymbol)[1] == meta(y.tradingsymbol)[1]
                   and gap < 10)
            isflip = bool(exact or und)
            if float(x.realized_pnl) < 0:
                tot_after_loss += 1; flip_after_loss += isflip
            else:
                tot_after_win += 1; flip_after_win += isflip
    if tot_after_loss and tot_after_win:
        pl = flip_after_loss/tot_after_loss; pw = flip_after_win/tot_after_win
        print(f"  P(next trade is a flip | prior LOST) = {100*pl:.1f}%  "
              f"({flip_after_loss}/{tot_after_loss})")
        print(f"  P(next trade is a flip | prior WON ) = {100*pw:.1f}%  "
              f"({flip_after_win}/{tot_after_win})")
        obs = pl - pw
        pool = [1]*flip_after_loss + [0]*(tot_after_loss-flip_after_loss) + \
               [1]*flip_after_win + [0]*(tot_after_win-flip_after_win)
        rnd = random.Random(7); hits = 0
        for _ in range(20000):
            rnd.shuffle(pool)
            d = sum(pool[:tot_after_loss])/tot_after_loss - sum(pool[tot_after_loss:])/tot_after_win
            if abs(d) >= abs(obs): hits += 1
        print(f"  difference {100*obs:+.1f}pp   p = {hits/20000:.3f}")
        print("  The copy says reversals track price rather than a view; the")
        print("  message adds 'after a loss on that view'. If flipping is no more")
        print("  likely after a loss, that framing is not supported.")

    # ── 5. window sensitivity on firings ─────────────────────────────────
    print("\n" + "=" * 78)
    print("5. WINDOW SENSITIVITY (detector firings, not raw pairs)")
    print("=" * 78)
    for w in (2, 5, 10, 20, 30, 60):
        n = len(run(sessions, {"rapid_flip_min": w, "direction_confusion_window_min": w}))
        print(f"    window {w:>3}m  ->  {n:>3} firings")


main()
