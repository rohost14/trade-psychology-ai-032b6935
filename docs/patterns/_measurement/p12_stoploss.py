"""
Pattern #12 — `no_stoploss`, measured.

The claim, as shown to the trader:

  "NIFTY25APR24000CE: manual exit after 43min with 61% loss of premium
   (Rs 12,400). No stop-loss order detected on this trade."

WHAT TO MEASURE

  1. does it fire, and how often — it was SKIPPED in the original replay as
     "UNJUDGEABLE", so there is no firing history at all
  2. DOES ITS PRIMARY GATE EVER WITHHOLD? The detector's first substantive test
     is `exit_types & _STOP_ORDER_TYPES -> return None`. Pattern 9 was retired
     for firing on 55 of the 55 positions it could judge. Same question here.
  3. what each remaining gate actually excludes: the 5-minute hold, the 25%
     loss, the expiry branches
  4. are the three threshold branches distinct? Two of them read 25/5.
  5. THE CLAIM. "No stop-loss order detected" is asserted from an EXIT FILL's
     order type. Is that the same question as "the trader had no stop"?
  6. consequence: is the session after a flagged trade worse than after a
     comparable unflagged loss? If not, the alert has nothing to warn about.
  7. F4 exposure: how many flagged trades are SHORT options, where the
     denominator is premium RECEIVED rather than paid?
  8. F13 as filed says futures cannot reach the loss branch. Check it.

HARNESS NOTE — read before trusting any number below

`duration_minutes` is NOT optional for this detector. `ct.duration_minutes or 0`
feeds `if duration < hold_threshold: return None`, so a None duration makes it
return None for every trade. p11_flip.py left it None because its subject did
not read it. Here it is computed, and `validate()` asserts the detector can
actually fire before anything else runs.
"""
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from statistics import mean, median
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tradedesk.scripts.replay_tradebook import read_fills            # noqa: E402
from app.services.behavior_engine import BehaviorEngine, EngineContext, _STOP_ORDER_TYPES  # noqa: E402
from app.services.instrument_parser import parse_symbol, is_expiry_day  # noqa: E402
from app.core.trading_defaults import COLD_START_DEFAULTS            # noqa: E402

engine = BehaviorEngine()
IST = ZoneInfo("Asia/Kolkata")
BOOK = "D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv"


def meta(sym):
    try:
        p = parse_symbol(sym or "")
        return (p.instrument_type or "EQ"), (p.underlying or sym or "")
    except Exception:
        return "EQ", sym or ""


def build(day_fills, carry):
    """FIFO round construction, identical to p11_flip.build plus duration."""
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
            dur = int((f["at"] - p["opened"]).total_seconds() // 60) if p["opened"] else 0
            out.append(SimpleNamespace(
                id=uuid4(), broker_account_id=None, tradingsymbol=sym,
                exchange="NFO", product="MIS", instrument_type=it,
                direction="LONG" if d > 0 else "SHORT", total_quantity=abs(c),
                avg_entry_price=Decimal(str(round(p["avg"], 4))),
                avg_exit_price=Decimal(str(px)),
                realized_pnl=Decimal(str(round(p["pnl"], 2))),
                pnl_pct=None, duration_minutes=dur,
                entry_time=p["opened"], exit_time=f["at"],
                num_entries=1, num_exits=1, closed_by_flip=False,
                status="closed", quality_score=None, underlying=und))
            p.update(qty=0, avg=0.0, opened=None, pnl=0.0)
    return [t for t in out if t.exit_time and t.exit_time.date() == day_fills[0]["date"]]


def load():
    fills = read_fills(BOOK)
    fills.sort(key=lambda f: f["at"])
    byday = defaultdict(list)
    for f in fills:
        byday[f["date"]].append(f)
    sessions, carry = [], []
    for day in sorted(byday):
        trades = build(byday[day], carry)
        carry = []
        if trades:
            sessions.append((day, trades))
    return sessions


def ctx_for(ct, prior, exit_types=None):
    th = dict(COLD_START_DEFAULTS)
    session = SimpleNamespace(
        session_pnl=Decimal(str(sum(float(t.realized_pnl) for t in prior))),
        session_date=ct.exit_time.date(), market_open=None)
    return EngineContext(
        broker_account_id=None, session=session, completed_trade=ct,
        session_trades=list(prior), active_cooldowns=[], thresholds=th,
        exit_order_types=exit_types or [])


def validate(sessions):
    """
    Harness trap #1 from the README: prove the detector can fire here before
    trusting a single count. If duration were left None it would return None
    every time and this whole script would report a clean zero.
    """
    fired = 0
    for _, trades in sessions:
        for i, ct in enumerate(trades):
            if engine._detect_no_stoploss(ctx_for(ct, trades[:i])):
                fired += 1
    assert fired > 0, "harness is inert - detector never fires, numbers meaningless"
    print(f"  harness validated: detector fires {fired} times with durations present")

    # And prove the SL gate works when order types ARE supplied.
    for _, trades in sessions:
        for i, ct in enumerate(trades):
            if engine._detect_no_stoploss(ctx_for(ct, trades[:i])):
                blocked = engine._detect_no_stoploss(
                    ctx_for(ct, trades[:i], exit_types=["SL-M"]))
                assert blocked is None, "the SL gate does not withhold when it should"
                print("  SL gate validated: an SL-M exit suppresses a firing trade")
                return fired
    return fired


def main():
    sessions = load()
    tot_trades = sum(len(t) for _, t in sessions)
    print(f"BOOK: {len(sessions)} sessions, {tot_trades} completed rounds\n")
    print("=" * 74)
    print("0. HARNESS VALIDATION")
    print("=" * 74)
    validate(sessions)

    # ---------------------------------------------------------------- gates
    print("\n" + "=" * 74)
    print("1. WHAT EACH GATE EXCLUDES  (funnel, in the detector's own order)")
    print("=" * 74)
    n_all = n_inst = n_loss = n_sl = n_cap = n_dur = n_pct = 0
    fires, judgeable = [], []
    for _, trades in sessions:
        for i, ct in enumerate(trades):
            n_all += 1
            it = ct.instrument_type or ""
            if it not in ("CE", "PE", "FUT"):
                continue
            n_inst += 1
            if Decimal(str(ct.realized_pnl or 0)) >= 0:
                continue
            n_loss += 1
            # gate 3 - the SL check. The tradebook carries no order type, so
            # exit_order_types is empty for every trade, exactly as it was on
            # the live path before F1.
            n_sl += 1
            judgeable.append(ct)
            entry = Decimal(str(ct.avg_entry_price or 0)) * (ct.total_quantity or 1)
            if entry <= 0:
                continue
            n_cap += 1
            if (ct.duration_minutes or 0) < 5:
                continue
            n_dur += 1
            ev = engine._detect_no_stoploss(ctx_for(ct, trades[:i]))
            if ev:
                n_pct += 1
                fires.append((ct, ev))
    rows = [("all rounds", n_all), ("CE/PE/FUT", n_inst), ("a loss", n_loss),
            ("survived the SL gate", n_sl), ("capital_at_risk > 0", n_cap),
            ("held >= 5 min", n_dur), ("loss >= threshold -> FIRES", n_pct)]
    prev = None
    for label, n in rows:
        drop = "" if prev is None else f"   (-{prev - n})"
        print(f"  {label:32} {n:>5}{drop}")
        prev = n

    print(f"\n  >>> the SL gate withheld {n_loss - n_sl} of {n_loss} judgeable trades")
    print(f"  >>> firing rate among judgeable losses: {n_pct}/{n_loss} = "
          f"{n_pct / max(n_loss, 1):.1%}")

    # ------------------------------------------------------------- severity
    print("\n" + "=" * 74)
    print("2. FIRINGS")
    print("=" * 74)
    sev = Counter(ev.severity for _, ev in fires)
    days = len({ct.exit_time.date() for ct, _ in fires})
    print(f"  {len(fires)} alerts across {days} sessions   severity: {dict(sev)}")
    inst = Counter(ct.instrument_type for ct, _ in fires)
    dirn = Counter(ct.direction for ct, _ in fires)
    print(f"  instrument: {dict(inst)}      direction: {dict(dirn)}")

    # ------------------------------------------------- threshold branch use
    print("\n" + "=" * 74)
    print("3. ARE THE THREE THRESHOLD BRANCHES DISTINCT?")
    print("=" * 74)
    D = COLD_START_DEFAULTS
    print(f"  normal  : loss >= {D['no_stoploss_loss_pct_caution']}%  hold >= {D['no_stoploss_hold_min']}min")
    print(f"  expiry  : loss >= {D['no_stoploss_expiry_loss_pct']}%  hold >= {D['no_stoploss_expiry_hold_min']}min")
    print(f"  monthly : loss >= {D['no_stoploss_monthly_loss_pct']}%  hold >= {D['no_stoploss_monthly_hold_min']}min")
    same = (D['no_stoploss_expiry_loss_pct'] == D['no_stoploss_loss_pct_caution']
            and D['no_stoploss_expiry_hold_min'] == D['no_stoploss_hold_min'])
    print(f"  -> weekly-expiry branch identical to normal: {same}")
    br = Counter()
    for ct, _ in fires:
        exp = is_expiry_day(ct.tradingsymbol or "", ct.entry_time.astimezone(IST).date()) \
            if ct.entry_time else False
        key = parse_symbol(ct.tradingsymbol or "").expiry_key if exp else ""
        br["monthly" if (exp and len(key) == 7) else ("expiry" if exp else "normal")] += 1
    print(f"  firings by branch: {dict(br)}")

    # ---------------------------------------------------------- selectivity
    print("\n" + "=" * 74)
    print("4. IS THE 25% GATE SELECTIVE?  (distribution over judgeable losses)")
    print("=" * 74)
    pcts = []
    for ct in judgeable:
        entry = float(ct.avg_entry_price or 0) * (ct.total_quantity or 1)
        if entry > 0:
            pcts.append(abs(float(ct.realized_pnl)) / entry * 100)
    pcts.sort()
    if pcts:
        def q(p): return pcts[min(int(len(pcts) * p), len(pcts) - 1)]
        print(f"  loss as % of entry value, n={len(pcts)}")
        print(f"    p10 {q(.10):5.1f}   p25 {q(.25):5.1f}   median {median(pcts):5.1f}"
              f"   p75 {q(.75):5.1f}   p90 {q(.90):5.1f}")
        for t in (10, 20, 25, 30, 50):
            n = sum(1 for x in pcts if x >= t)
            print(f"    >= {t:>2}%: {n:>4} / {len(pcts)}  ({n / len(pcts):.1%})")

    # --------------------------------------------------------- hold measure
    print("\n" + "=" * 74)
    print("5. DOES THE 5-MINUTE HOLD GATE DO ANYTHING?")
    print("=" * 74)
    durs = [ct.duration_minutes or 0 for ct in judgeable]
    under = sum(1 for d in durs if d < 5)
    print(f"  judgeable losses held < 5 min: {under} / {len(durs)} ({under/max(len(durs),1):.1%})")
    print(f"  median hold: {median(durs) if durs else 0:.0f} min")

    # ---------------------------------------------------------- consequence
    print("\n" + "=" * 74)
    print("6. CONSEQUENCE  (rest-of-session P&L after a flagged loss vs an")
    print("   unflagged loss that also survived every gate but the loss %)")
    print("=" * 74)
    flagged_ids = {id(ct) for ct, _ in fires}
    after_f, after_u = [], []
    for _, trades in sessions:
        for i, ct in enumerate(trades):
            if ct not in judgeable:
                continue
            if (ct.duration_minutes or 0) < 5:
                continue
            rest = sum(float(t.realized_pnl) for t in trades[i + 1:])
            (after_f if id(ct) in flagged_ids else after_u).append(rest)
    for label, xs in (("after FLAGGED", after_f), ("after unflagged", after_u)):
        if xs:
            print(f"  {label:16} n={len(xs):>4}  mean Rs {mean(xs):>10,.0f}   "
                  f"median Rs {median(xs):>10,.0f}")
    if after_f and after_u:
        print(f"  difference in means: Rs {mean(after_f) - mean(after_u):,.0f}")

    # ------------------------------------------------------------- F4 / F13
    print("\n" + "=" * 74)
    print("7. FILED DEFECTS, CHECKED AGAINST THIS BOOK")
    print("=" * 74)
    shorts = sum(1 for ct, _ in fires if ct.direction == "SHORT"
                 and ct.instrument_type in ("CE", "PE"))
    futs = sum(1 for ct, _ in fires if ct.instrument_type == "FUT")
    print(f"  F4  short-option firings (denominator = premium RECEIVED): {shorts}")
    print(f"  F13 futures firings (filed as 'loss branch unreachable'):  {futs}")
    print(f"      _STOP_ORDER_TYPES = {sorted(_STOP_ORDER_TYPES)}")

    print("\n" + "=" * 74)
    print("8. TEN LOUDEST ALERTS")
    print("=" * 74)
    for ct, ev in sorted(fires, key=lambda x: float(x[0].realized_pnl))[:10]:
        print(f"  {ev.severity:8} {ct.exit_time.astimezone(IST):%Y-%m-%d %H:%M}  "
              f"{ct.tradingsymbol:24} {ct.duration_minutes:>4}min  "
              f"Rs {float(ct.realized_pnl):>10,.0f}  "
              f"{ev.context['loss_pct']:>5.1f}%")


main()
