"""
Pattern #11 follow-up: can the detector SEPARATE abnormal flipping from a
legitimate change of view?

Firing is not discrimination. The question is whether the subset it selects -
CE<->PE on one underlying inside 10 minutes - differs from the CE<->PE
transitions it does NOT select. If a flagged flip looks like an unflagged one,
the detector is a timer, not a judgement.

TESTS
  A. taxonomy of every CE<->PE transition on one underlying:
     simultaneous (legs overlap = hedge/structure) / rapid sequential (<10m,
     FLAGGED) / slow sequential (>=10m, NOT flagged)
  B. flagged vs unflagged sequential: outcome, size change, rest-of-session
  C. repeated flipping: do multi-flip sessions end worse, against a
     trade-count-matched control (position-in-session confound)
  D. flips after a loss vs after a win
  E. size and pace around the flip
  F. overlap with revenge_trade / rapid_reentry / same_symbol_obsession on the
     SAME trade
"""
import random
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

exec(open("C:/Users/being/.claude/jobs/33a73186/tmp/p11_flip.py")
     .read().rsplit("\nmain()", 1)[0])

from app.core.detector_result import DetectorResult  # noqa: E402

WINDOW = 10


def fired(r):
    if r is None:
        return False
    if isinstance(r, DetectorResult):
        return r.fired
    if isinstance(r, list):
        return bool(r)
    return getattr(r, "event_type", None) is not None


def und(t):
    return meta(t.tradingsymbol)[1]


def transitions(sessions):
    """Every CE<->PE pair on one underlying, classified."""
    out = []
    for day, ts in sessions:
        for i, a in enumerate(ts):
            if a.instrument_type not in ("CE", "PE"):
                continue
            for b in ts[i + 1:]:
                if b.instrument_type not in ("CE", "PE"):
                    continue
                if und(a) != und(b) or a.instrument_type == b.instrument_type:
                    continue
                if not (a.exit_time and b.entry_time and a.entry_time):
                    continue
                # overlap => both legs live at once => hedge / structure
                if b.entry_time < a.exit_time:
                    kind = "simultaneous"
                    gap = (b.entry_time - a.exit_time).total_seconds() / 60
                else:
                    gap = (b.entry_time - a.exit_time).total_seconds() / 60
                    kind = "rapid" if gap < WINDOW else "slow"
                out.append({"day": day, "kind": kind, "gap": gap, "prior": a,
                            "cur": b, "both_long": a.direction == "LONG" and b.direction == "LONG"})
                break   # nearest following opposite-type leg only
    return out


def stat(v, label, width=46):
    if not v:
        print(f"  {label:<{width}} n=0")
        return
    w = sum(1 for x in v if x > 0)
    print(f"  {label:<{width}} n={len(v):<4} win {100*w/len(v):>5.1f}%  "
          f"mean Rs {sum(v)/len(v):>9,.0f}")


def perm(a, b, label, n=20000):
    if not a or not b:
        print(f"  {label}: insufficient n")
        return
    obs = sum(a)/len(a) - sum(b)/len(b)
    pool = a + b
    rnd = random.Random(7)
    hits = 0
    for _ in range(n):
        rnd.shuffle(pool)
        if abs(sum(pool[:len(a)])/len(a) - sum(pool[len(a):])/len(b)) >= abs(obs):
            hits += 1
    print(f"  {label}: diff Rs {obs:,.0f}/trade   p = {hits/n:.3f}")


def main():
    sessions = load()
    tr = transitions(sessions)

    print("=" * 78)
    print("A. TAXONOMY — every CE<->PE transition on one underlying")
    print("=" * 78)
    c = Counter(t["kind"] for t in tr)
    print(f"  total transitions: {len(tr)}")
    for k in ("simultaneous", "rapid", "slow"):
        n = c.get(k, 0)
        tag = {"simultaneous": "legs OVERLAP — hedge / structure, detector excludes (negative gap)",
               "rapid": f"sequential, gap < {WINDOW}m — **FLAGGED**",
               "slow": f"sequential, gap >= {WINDOW}m — not flagged"}[k]
        print(f"    {k:<14} {n:>4}   {tag}")
    bl = sum(1 for t in tr if not t["both_long"])
    print(f"\n  transitions where a leg was not LONG: {bl} "
          f"(detector requires both LONG for Level 2)")

    rapid = [t for t in tr if t["kind"] == "rapid" and t["both_long"]]
    slow = [t for t in tr if t["kind"] == "slow" and t["both_long"]]
    sim = [t for t in tr if t["kind"] == "simultaneous"]

    print("\n" + "=" * 78)
    print("B. DOES THE 10-MINUTE LINE SEPARATE ANYTHING?")
    print("=" * 78)
    print("  If a flagged flip looks like an unflagged one, the window is a")
    print("  timer, not a judgement.\n")
    a = [float(t["cur"].realized_pnl) for t in rapid]
    b = [float(t["cur"].realized_pnl) for t in slow]
    stat(a, f"FLAGGED: the flip trade (gap < {WINDOW}m)")
    stat(b, f"not flagged: same transition, gap >= {WINDOW}m")
    stat([float(t["cur"].realized_pnl) for t in sim], "simultaneous legs (hedge/structure)")
    perm(a, b, "  flagged vs not-flagged")

    print("\n  The trade being REVERSED OUT OF:")
    stat([float(t["prior"].realized_pnl) for t in rapid], f"FLAGGED prior (gap < {WINDOW}m)")
    stat([float(t["prior"].realized_pnl) for t in slow], f"not-flagged prior (gap >= {WINDOW}m)")

    print("\n" + "=" * 78)
    print("E. SIZE AND PACE AROUND THE FLIP")
    print("=" * 78)

    def notional(t):
        return float(t.total_quantity or 0) * float(t.avg_entry_price or 0)

    for name, grp in (("flagged", rapid), ("not flagged", slow)):
        if not grp:
            continue
        ratios = [notional(t["cur"]) / max(notional(t["prior"]), 1) for t in grp]
        ratios.sort()
        up = sum(1 for r in ratios if r > 1.0)
        print(f"  {name:<12} size ratio flip/prior: median {ratios[len(ratios)//2]:.2f}   "
              f"larger in {up}/{len(ratios)}")
    print("  (a flip that also sizes UP is the escalation story; flat size is not)")

    print("\n" + "=" * 78)
    print("C. REPEATED FLIPPING — do multi-flip sessions end worse?")
    print("=" * 78)
    per_session = defaultdict(int)
    for t in rapid:
        per_session[t["day"]] += 1
    pnl = {day: sum(float(x.realized_pnl) for x in ts) for day, ts in sessions}
    cnt = {day: len(ts) for day, ts in sessions}

    groups = defaultdict(list)
    for day, ts in sessions:
        groups[min(per_session.get(day, 0), 2)].append(day)
    print(f"    {'flips':>7}{'days':>7}{'mean trades':>13}{'mean session Rs':>18}")
    for k in sorted(groups):
        d = groups[k]
        lbl = "2+" if k == 2 else str(k)
        print(f"    {lbl:>7}{len(d):>7}{sum(cnt[x] for x in d)/len(d):>13.1f}"
              f"{sum(pnl[x] for x in d)/len(d):>18,.0f}")
    print("\n  CONTROL for the position-in-session confound: flip sessions are")
    print("  longer, and longer sessions differ anyway. Compare only against")
    print("  no-flip sessions of a SIMILAR trade count.")
    flip_days = [d for d in pnl if per_session.get(d, 0) >= 1]
    if flip_days:
        lo = min(cnt[d] for d in flip_days)
        hi = max(cnt[d] for d in flip_days)
        matched = [d for d in pnl if per_session.get(d, 0) == 0 and lo <= cnt[d] <= hi]
        stat([pnl[d] for d in flip_days], f"sessions WITH a flip ({lo}-{hi} trades)")
        stat([pnl[d] for d in matched], f"no-flip sessions, same trade-count band")
        perm([pnl[d] for d in flip_days], [pnl[d] for d in matched], "  matched comparison")

    print("\n  Rest-of-session AFTER the first flip vs after the same trade index")
    print("  in a matched no-flip session:")
    after, ctrl = [], []
    first_idx = {}
    for t in rapid:
        day = t["day"]
        ts = dict(sessions)[day]
        i = ts.index(t["cur"])
        if day not in first_idx or i < first_idx[day]:
            first_idx[day] = i
    for day, i in first_idx.items():
        ts = dict(sessions)[day]
        after.append(sum(float(x.realized_pnl) for x in ts[i + 1:]))
    for day, ts in sessions:
        if per_session.get(day, 0):
            continue
        idxs = [i for i in first_idx.values() if i < len(ts)]
        if idxs:
            i = idxs[len(idxs) // 2]
            ctrl.append(sum(float(x.realized_pnl) for x in ts[i + 1:]))
    stat(after, "rest of session after the first flip")
    stat(ctrl, "rest of session, matched index, no flip")
    perm(after, ctrl, "  deterioration test")

    print("\n" + "=" * 78)
    print("D. FLIP AFTER A LOSS vs AFTER A WIN — is the flip trade worse?")
    print("=" * 78)
    al = [float(t["cur"].realized_pnl) for t in rapid if float(t["prior"].realized_pnl) < 0]
    aw = [float(t["cur"].realized_pnl) for t in rapid if float(t["prior"].realized_pnl) >= 0]
    stat(al, "flip trade, when the prior LOST")
    stat(aw, "flip trade, when the prior WON")
    perm(al, aw, "  loss-driven vs not")

    print("\n" + "=" * 78)
    print("F. OVERLAP — what else fires on the very same trade?")
    print("=" * 78)
    others = ["_detect_revenge_trade", "_detect_rapid_reentry",
              "_detect_same_symbol_obsession", "_detect_martingale_behaviour",
              "_detect_post_loss_recovery_bet", "_detect_options_premium_avg_down"]
    hits = Counter()
    n_fired = 0
    for day, ts in sessions:
        for i, ct in enumerate(ts):
            ctx = EngineContext(
                broker_account_id=uuid4(),
                session=SimpleNamespace(session_pnl=Decimal("0"),
                                        session_date=day, market_open=None),
                completed_trade=ct, session_trades=ts[:i],
                active_cooldowns=[], thresholds={})
            if not engine._detect_direction_instability(ctx):
                continue
            n_fired += 1
            for m in others:
                try:
                    if fired(getattr(engine, m)(ctx)):
                        hits[m.replace("_detect_", "")] += 1
                except Exception:
                    pass
    print(f"  direction_instability firings: {n_fired}")
    for k, v in hits.most_common():
        print(f"    also fired on the same trade: {k:<32} {v:>3} / {n_fired}")
    if not hits:
        print("    nothing else fired on any of them")


main()
