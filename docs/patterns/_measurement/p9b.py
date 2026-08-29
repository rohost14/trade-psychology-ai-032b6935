"""Pattern 9 - part 2. Does it discriminate at all, and is the claim significant?"""
import sys, random
from collections import Counter, defaultdict
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo
sys.path.insert(0, "D:/trade-psychology-ai"); sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
exec(open("C:/Users/being/.claude/jobs/33a73186/tmp/p9_expiry.py").read().split("def main()")[0].split('"""')[2])

def main():
    fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    fills.sort(key=lambda f: f["at"])
    byday = defaultdict(list)
    for f in fills: byday[f["date"]].append(f)
    sessions = []
    for day in sorted(byday):
        ts = build(byday[day], carry_fills(fills, day))
        if ts:
            ts.sort(key=lambda t: t.entry_time or t.exit_time); sessions.append((day, ts))
    allp = [t for _, t in sessions for t in t]

    exp = []
    for _, ts in sessions:
        for t in ts:
            if t.instrument_type not in ("CE","PE","FUT") or not t.entry_time: continue
            ist = t.entry_time.astimezone(IST)
            if is_expiry_day(t.tradingsymbol or "", ist.date()): exp.append((t, ist))
    after = [x for x in exp if x[1].hour >= 13]
    before = [x for x in exp if x[1].hour < 13]

    fired_ids = set(); rows = []
    for day, ts in sessions:
        for i, ct in enumerate(ts):
            ctx = EngineContext(broker_account_id=uuid4(),
                session=SimpleNamespace(session_pnl=Decimal("0"), session_date=day, market_open=None),
                completed_trade=ct, session_trades=ts[:i], thresholds={})
            ev = engine._detect_expiry_day_overtrading(ctx)
            if ev:
                fired_ids.add(id(ct)); rows.append((ct, ev))

    print("="*78); print("DISCRIMINATION - of the positions it is ALLOWED to judge, how many pass?")
    print("="*78)
    print(f"  eligible (expiry + CE/PE/FUT + entry >= 13:00): {len(after)}")
    print(f"  of those, detector FIRED on              : {sum(1 for t,_ in after if id(t) in fired_ids)}")
    print(f"  of those, detector stayed SILENT on      : {sum(1 for t,_ in after if id(t) not in fired_ids)}")
    print("  -> if these are equal, the trade-count logic is inert and the")
    print("     detector is a FILTER (expiry + afternoon), not a detector.")

    print("\n  What the trader actually reads (first 6 firings):")
    for ct, ev in rows[:6]:
        print(f"    [{ev.severity:>7}] {ev.message}")
    print("\n  `today_lots` is a sum of total_quantity = CONTRACTS. NIFTY lot = 75.")
    q = sorted(int(t.total_quantity) for t,_ in exp)
    print(f"    quantities seen: {q[:6]} ... {q[-4:]}")
    print(f"    'lots' shown to trader is therefore ~{q[len(q)//2]//75}x-inflated at median.")

    print("\n" + "="*78); print("SIGNIFICANCE - post-13:00 expiry vs the alternatives")
    print("="*78)
    A = [float(t.realized_pnl) for t,_ in after]
    B = [float(t.realized_pnl) for t,_ in before]
    expset = {id(t) for t,_ in exp}
    C = [float(t.realized_pnl) for t in allp if id(t) not in expset]

    def perm(a, b, label, n=20000):
        obs = sum(a)/len(a) - sum(b)/len(b)
        pool = a + b; hits = 0
        rnd = random.Random(7)
        for _ in range(n):
            rnd.shuffle(pool)
            d = sum(pool[:len(a)])/len(a) - sum(pool[len(a):])/len(b)
            if abs(d) >= abs(obs): hits += 1
        print(f"  {label:<46} diff Rs {obs:>8,.0f}/trade   p = {hits/n:.3f}")

    def permwin(a, b, label, n=20000):
        wa = sum(1 for x in a if x>0)/len(a); wb = sum(1 for x in b if x>0)/len(b)
        obs = wa - wb; pool=[1 if x>0 else 0 for x in a+b]; hits=0
        rnd = random.Random(7)
        for _ in range(n):
            rnd.shuffle(pool)
            d = sum(pool[:len(a)])/len(a) - sum(pool[len(a):])/len(b)
            if abs(d) >= abs(obs): hits += 1
        print(f"  {label:<46} diff {100*obs:>7.1f}pp      p = {hits/n:.3f}")

    print("  mean P&L per position:")
    perm(A, B, "post-13:00 expiry  vs  pre-13:00 expiry")
    perm(A, C, "post-13:00 expiry  vs  all non-expiry")
    print("  win rate:")
    permwin(A, B, "post-13:00 expiry  vs  pre-13:00 expiry")
    permwin(A, C, "post-13:00 expiry  vs  all non-expiry")

    print("\n" + "="*78); print("THE 85% CLAIM - 'last 2 hours of expiry day, loss rate above 85%'")
    print("="*78)
    for hr, lbl in ((13,"entered 13:00+"), (14,"entered 14:00+ (true last 2h)"), (15,"entered 15:00+")):
        s = [float(t.realized_pnl) for t,i in exp if i.hour >= hr]
        if s:
            loss = sum(1 for x in s if x <= 0)
            print(f"  {lbl:<34} n={len(s):<4} loss rate {100*loss/len(s):>5.1f}%   (claim: >85%)")

    print("\n" + "="*78); print("THE 'EACH ADDITIONAL TRADE' CLAIM - direction test")
    print("="*78)
    seq = defaultdict(list)
    for day, ts in sessions:
        n = 0
        for t in ts:
            if t.instrument_type not in ("CE","PE","FUT") or not t.entry_time: continue
            ist = t.entry_time.astimezone(IST)
            if not is_expiry_day(t.tradingsymbol or "", ist.date()) or ist.hour < 13: continue
            n += 1; seq[n].append((n, float(t.realized_pnl)))
    pts = [p for v in seq.values() for p in v]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    mx = sum(xs)/len(xs); my = sum(ys)/len(ys)
    cov = sum((x-mx)*(y-my) for x,y in pts)
    vx = sum((x-mx)**2 for x in xs); vy = sum((y-my)**2 for y in ys)
    r = cov/((vx*vy)**0.5)
    rnd = random.Random(7); hits=0
    for _ in range(20000):
        sh = ys[:]; rnd.shuffle(sh)
        c = sum((x-mx)*(y-my) for x,y in zip(xs, sh))
        if abs(c) >= abs(cov): hits += 1
    print(f"  correlation of trade-number vs P&L: r = {r:+.3f}   p = {hits/20000:.3f}   n = {len(pts)}")
    print("  claim asserts r < 0 (each extra trade worse).")
    print(f"  observed sign: {'NEGATIVE - consistent with claim' if r < 0 else 'POSITIVE - OPPOSITE of the claim'}")

main()
