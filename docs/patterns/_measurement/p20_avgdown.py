"""
Pattern 20 — `options_premium_avg_down`, and the product question:

    is it a distinct behaviour, or a manifestation of
    `adding_to_adverse_position`?

READ THE TWO SUBJECTS BEFORE THE NUMBERS. They are not the same shape.

  adding_to_adverse_position   POSITION level. One symbol, one OPEN position.
                               Reads the FILL SEQUENCE and keeps only adds made
                               while that position was under water.

  options_premium_avg_down     SESSION level. Same UNDERLYING, not same
                               contract. Its "prior losers" are CLOSED rounds
                               with a realised loss. It never inspects a fill
                               sequence, never requires an open position, and
                               never requires the trader to have added to
                               anything.

So on the code, this is NOT an average-down at all: it fires on a NEW long
option entry after a DIFFERENT long option on the same underlying was closed at
a loss today. That is re-entry after a loss.

WHAT TO MEASURE

  1. does it fire, how often, and does it withhold
  2. CAN the two ever describe the same event? Same trade, both fire?
  3. what its firings actually are: same contract, same strike, same expiry,
     or a different option entirely
  4. the behaviour it really overlaps - `same_symbol_obsession`,
     `revenge_trade`, `rapid_reentry` - since its true subject is re-entry
  5. false positives on legitimate structure: a CE and a PE on one underlying
     is a straddle, not an average-down
  6. unique coverage: what would disappear if it went

HARNESS NOTE - THIS IS NEW
`adding_to_adverse_position` was recorded as UNMEASURABLE from the CSV harness
because it reads a fill sequence the round reconstruction discards. That was
true of the reconstruction, not of the tradebook: `read_fills` returns the
individual fills, so the sequence can be rebuilt and classified exactly as the
ledger classifies it. `validate()` proves the detector fires on the rebuilt
sequence before any comparison below is trusted. If it did not, every overlap
number here would be a false zero.
"""
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from statistics import mean, median
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p12_stoploss.py",
           encoding="utf-8").read()
exec(src.rsplit("\nmain()", 1)[0])

from app.core.position_fills import PositionFill, adverse_adds   # noqa: E402
from app.core.trading_defaults import COLD_START_DEFAULTS        # noqa: E402
from app.services.instrument_parser import parse_symbol as _ps    # noqa: E402

AVG = engine._detect_options_premium_avg_down
AAP = engine._detect_adding_to_adverse_position


# ── rebuild the fill sequence, classified as the ledger classifies it ──────

def build_with_fills(day_fills, carry):
    """
    Same FIFO walk as p12.build, but also emits each round's PositionFill
    sequence so `adding_to_adverse_position` becomes measurable.
    """
    st = defaultdict(lambda: {"qty": 0, "avg": 0.0, "opened": None,
                              "pnl": 0.0, "fills": []})
    out = []
    for f in list(carry) + list(day_fills):
        sym = f["symbol"]; p = st[sym]
        s = f["qty"] if f["side"] == "BUY" else -f["qty"]
        px = float(f["price"])
        before = p["qty"]

        if before == 0:
            et = "OPEN"
        elif (before > 0) == (s > 0):
            et = "INCREASE"
        elif abs(s) < abs(before):
            et = "DECREASE"
        elif abs(s) == abs(before):
            et = "CLOSE"
        else:
            et = "FLIP"

        # apply
        if before == 0:
            p.update(qty=s, avg=px, opened=f["at"], pnl=0.0, fills=[])
        elif (before > 0) == (s > 0):
            nq = before + s
            p["avg"] = (p["avg"] * abs(before) + px * abs(s)) / abs(nq)
            p["qty"] = nq
        else:
            c = min(abs(s), abs(before)); d = 1 if before > 0 else -1
            p["pnl"] += (px - p["avg"]) * c * d
            p["qty"] = before + s

        p["fills"].append(PositionFill(
            entry_type=et, fill_qty=s, fill_price=px,
            position_qty_after=p["qty"],
            avg_entry_price_after=p["avg"] if p["qty"] else None,
            occurred_at=f["at"]))

        if p["qty"] == 0:
            it, u = meta(sym)
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
                num_entries=sum(1 for x in p["fills"] if x.entry_type in ("OPEN", "INCREASE", "FLIP")),
                num_exits=1, closed_by_flip=False, status="closed",
                quality_score=None, underlying=u,
                _fills=list(p["fills"])))
            p.update(qty=0, avg=0.0, opened=None, pnl=0.0, fills=[])
    return [t for t in out if t.exit_time and t.exit_time.date() == day_fills[0]["date"]]


def load_with_fills():
    fills = read_fills(BOOK)
    fills.sort(key=lambda f: f["at"])
    byday = defaultdict(list)
    for f in fills:
        byday[f["date"]].append(f)
    sessions, carry = [], []
    for day in sorted(byday):
        trades = build_with_fills(byday[day], carry)
        carry = []
        if trades:
            sessions.append((day, trades))
    return sessions


def ctx_fills(ct, prior):
    """p12's ctx_for plus the rebuilt fill sequence."""
    c = ctx_for(ct, prior)
    c.position_fills = list(getattr(ct, "_fills", []))
    return c


def fired(r):
    return bool(getattr(r, "fired", r)) if r is not None else False


def und(t):
    try:
        return _ps(t.tradingsymbol or "").underlying or t.tradingsymbol or ""
    except Exception:
        return t.tradingsymbol or ""


def strike_of(t):
    try:
        return _ps(t.tradingsymbol or "").strike
    except Exception:
        return None


def validate(sessions):
    a = sum(1 for _, tr in sessions for i, ct in enumerate(tr)
            if fired(AVG(ctx_fills(ct, tr[:i]))))
    b = sum(1 for _, tr in sessions for i, ct in enumerate(tr)
            if fired(AAP(ctx_fills(ct, tr[:i]))))
    print(f"  options_premium_avg_down fires      : {a}")
    print(f"  adding_to_adverse_position fires    : {b}")
    assert a > 0, "avg_down harness inert"
    assert b > 0, ("adding_to_adverse_position never fires on the rebuilt fill "
                   "sequence - the reconstruction is wrong and every overlap "
                   "number below would be a false zero")
    multi = sum(1 for _, tr in sessions for t in tr if (t.num_entries or 1) > 1)
    print(f"  positions built from >1 entry       : {multi}")
    return a, b


def main():
    sessions = load_with_fills()
    trades = [t for _, ts in sessions for t in ts]
    print(f"BOOK: {len(sessions)} sessions, {len(trades)} rounds")
    print(f"THRESHOLD: premium_avg_down_loss_pct = "
          f"{COLD_START_DEFAULTS['premium_avg_down_loss_pct']}\n")
    n_avg, n_aap = validate(sessions)

    # collect both
    avg_fires, aap_fires, both = [], [], []
    for day, tr in sessions:
        for i, ct in enumerate(tr):
            c = ctx_fills(ct, tr[:i])
            a = AVG(c)
            b = AAP(c)
            if fired(a):
                avg_fires.append((day, ct, tr[:i], a))
            if fired(b):
                aap_fires.append((day, ct))
            if fired(a) and fired(b):
                both.append((day, ct))

    # ------------------------------------------------------------------ 1
    print("\n" + "=" * 74)
    print("1. FIRING AND WITHHOLDING")
    print("=" * 74)
    print(f"  options_premium_avg_down : {len(avg_fires)} events / "
          f"{len({d for d,_,_,_ in avg_fires})} sessions of {len(sessions)}")
    long_opts = [t for t in trades if t.instrument_type in ("CE", "PE")
                 and t.direction == "LONG"]
    print(f"  eligible (LONG CE/PE)    : {len(long_opts)} of {len(trades)} rounds")
    # how many eligible had ANY prior same-underlying long-option loser today
    elig = 0
    for _day, tr in sessions:
        for i, ct in enumerate(tr):
            if ct.instrument_type not in ("CE", "PE") or ct.direction != "LONG":
                continue
            u = und(ct)
            if any(p.instrument_type in ("CE", "PE") and p.direction == "LONG"
                   and float(p.realized_pnl) < 0 and und(p) == u for p in tr[:i]):
                elig += 1
    print(f"  had a prior same-underlying long-option LOSS : {elig}")
    if elig:
        print(f"  -> the 20% floor withholds on {elig - len(avg_fires)} of {elig} "
              f"({1 - len(avg_fires)/elig:.0%})")

    # ------------------------------------------------------------------ 2
    print("\n" + "=" * 74)
    print("2. CAN THE TWO EVER DESCRIBE THE SAME EVENT?")
    print("=" * 74)
    print(f"  adding_to_adverse_position fires : {len(aap_fires)}")
    print(f"  options_premium_avg_down fires   : {len(avg_fires)}")
    print(f"  BOTH on the same trade           : {len(both)}")
    if not both:
        print("  -> they never co-fire. Not overlapping implementations of one")
        print("     behaviour; different subjects on different objects.")

    # ------------------------------------------------------------------ 3
    print("\n" + "=" * 74)
    print("3. WHAT ITS FIRINGS ACTUALLY ARE")
    print("=" * 74)
    same_contract = same_strike = diff_strike = diff_type = 0
    prior_open = 0
    for _d, ct, prior, ev in avg_fires:
        u = und(ct)
        losers = [p for p in prior
                  if p.instrument_type in ("CE", "PE") and p.direction == "LONG"
                  and float(p.realized_pnl) < 0 and und(p) == u]
        if any(p.tradingsymbol == ct.tradingsymbol for p in losers):
            same_contract += 1
        elif any(strike_of(p) == strike_of(ct) for p in losers):
            same_strike += 1
        else:
            diff_strike += 1
        if any(p.instrument_type != ct.instrument_type for p in losers):
            diff_type += 1
        # every prior is a CLOSED round by construction
        prior_open += sum(1 for p in losers if p.status != "closed")
    print(f"  firings where a prior loser is the SAME CONTRACT : {same_contract}")
    print(f"  ...same strike, different contract               : {same_strike}")
    print(f"  ...a DIFFERENT option entirely                   : {diff_strike}")
    print(f"  firings where a prior loser is the OTHER TYPE (CE vs PE): {diff_type}")
    print(f"  firings where any prior position was still OPEN  : {prior_open}")
    print("\n  Every 'prior loser' is a CLOSED round with a realised loss, so no")
    print("  firing can be an add to an open position - which is what averaging")
    print("  down means and what the registry copy promises.")

    # ------------------------------------------------------------------ 4
    print("\n" + "=" * 74)
    print("4. OVERLAP WITH THE DETECTORS THAT SHARE ITS REAL SUBJECT")
    print("=" * 74)
    others = ("_detect_same_symbol_obsession", "_detect_revenge_trade",
              "_detect_rapid_reentry", "_detect_premium_loss_event",
              "_detect_martingale_behaviour", "_detect_post_loss_recovery_bet",
              "_detect_fomo_entry", "_detect_overtrading_burst")
    co = Counter(); alone = 0
    for _d, ct, prior, _ev in avg_fires:
        c = ctx_fills(ct, prior)
        hit = []
        for m in others:
            fn = getattr(engine, m, None)
            if not fn:
                continue
            try:
                if fired(fn(c)):
                    hit.append(m.replace("_detect_", ""))
            except Exception:
                pass
        for h in hit:
            co[h] += 1
        if not hit:
            alone += 1
    for k, v in co.most_common():
        print(f"    {k:<34} {v:>3} / {len(avg_fires)}  ({v/len(avg_fires):.0%})")
    print(f"\n  fired ALONE on {alone} of {len(avg_fires)} "
          f"({alone/len(avg_fires):.0%})" if avg_fires else "")

    # ------------------------------------------------------------------ 5
    print("\n" + "=" * 74)
    print("5. LEGITIMATE STRUCTURE - is a straddle leg being called an add?")
    print("=" * 74)
    ce_pe = 0
    for _d, ct, prior, _ev in avg_fires:
        u = und(ct)
        losers = [p for p in prior
                  if p.instrument_type in ("CE", "PE") and p.direction == "LONG"
                  and float(p.realized_pnl) < 0 and und(p) == u]
        if losers and all(p.instrument_type != ct.instrument_type for p in losers):
            ce_pe += 1
    print(f"  firings where EVERY prior loser is the opposite option type : {ce_pe}")
    print("  A CE entered after a PE lost is a direction change, not an")
    print("  average-down of that PE. The detector cannot tell them apart.")

    # ------------------------------------------------------------------ 6
    print("\n" + "=" * 74)
    print("6. CONSEQUENCE - ranks, cannot judge")
    print("=" * 74)
    fl = [float(ct.realized_pnl) for _d, ct, _p, _e in avg_fires]
    ids = {id(ct) for _d, ct, _p, _e in avg_fires}
    ctrl = [float(t.realized_pnl) for t in long_opts if id(t) not in ids]
    if fl:
        print(f"  flagged   n={len(fl):<4} mean Rs {mean(fl):>9,.0f}  "
              f"median Rs {median(fl):>8,.0f}  win {sum(1 for x in fl if x>0)/len(fl):.1%}")
    if ctrl:
        print(f"  other LONG options n={len(ctrl):<4} mean Rs {mean(ctrl):>9,.0f}  "
              f"median Rs {median(ctrl):>8,.0f}  win {sum(1 for x in ctrl if x>0)/len(ctrl):.1%}")

    # ------------------------------------------------------------------ 7
    print("\n" + "=" * 74)
    print("7. SAMPLE OF THE FIRINGS")
    print("=" * 74)
    for _d, ct, prior, ev in avg_fires[:10]:
        u = und(ct)
        losers = [p for p in prior
                  if p.instrument_type in ("CE", "PE") and p.direction == "LONG"
                  and float(p.realized_pnl) < 0 and und(p) == u]
        print(f"  {_d}  {ct.tradingsymbol}")
        print(f"      priors: {', '.join(p.tradingsymbol for p in losers[:4])}")
        print(f"      {ev.message[:110]}")


main()
