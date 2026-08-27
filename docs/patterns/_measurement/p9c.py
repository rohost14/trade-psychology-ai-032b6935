"""Pattern 9 part 3 - the fair day-level test of the OVERTRADING claim, plus
whether a units fix would rescue the lots clause."""
import sys, random
from collections import Counter, defaultdict
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo
sys.path.insert(0,"D:/trade-psychology-ai"); sys.path.insert(0,"D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
exec(open("C:/Users/being/.claude/jobs/33a73186/tmp/p9_expiry.py").read().split("def main()")[0].split('"""')[2])

LOT = {"NIFTY":75,"BANKNIFTY":35,"FINNIFTY":65,"MIDCPNIFTY":140,"SENSEX":20,"BANKEX":30}

fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
fills.sort(key=lambda f: f["at"])
byday=defaultdict(list)
for f in fills: byday[f["date"]].append(f)
sessions=[]
for day in sorted(byday):
    ts=build(byday[day], carry_fills(fills,day))
    if ts: ts.sort(key=lambda t:t.entry_time or t.exit_time); sessions.append((day,ts))

def expiry_of(ts):
    out=[]
    for t in ts:
        if t.instrument_type not in ("CE","PE","FUT") or not t.entry_time: continue
        i=t.entry_time.astimezone(IST)
        if is_expiry_day(t.tradingsymbol or "", i.date()): out.append((t,i))
    return out

print("="*78); print("A. UNITS FIX - would `lots` discriminate if it were really lots?")
print("="*78)
exp_all=[x for _,ts in sessions for x in expiry_of(ts)]
after=[x for x in exp_all if x[1].hour>=13]
real=[]
for t,_ in exp_all:
    u=parse_symbol(t.tradingsymbol or "").underlying
    real.append(int(t.total_quantity)/LOT.get(u,75))
real.sort()
print(f"  true lots per position: min {real[0]:.0f}  median {real[len(real)//2]:.0f}  max {real[-1]:.0f}")
print(f"  single positions already at/above 10 TRUE lots: "
      f"{sum(1 for r in real if r>=10)} of {len(real)} ({100*sum(1 for r in real if r>=10)/len(real):.0f}%)")
# cumulative true lots per (day, underlying) at each post-13:00 trade
cum=[]
for day,ts in sessions:
    acc=defaultdict(float)
    for t in ts:
        if t.instrument_type not in ("CE","PE","FUT") or not t.entry_time: continue
        i=t.entry_time.astimezone(IST)
        if not is_expiry_day(t.tradingsymbol or "", i.date()): continue
        u=parse_symbol(t.tradingsymbol or "").underlying
        acc[u]+=int(t.total_quantity)/LOT.get(u,75)
        if i.hour>=13: cum.append(acc[u])
over=sum(1 for c in cum if c>=10)
print(f"  eligible trades whose CUMULATIVE true lots >= 10: {over} of {len(cum)} ({100*over/len(cum):.0f}%)")
print("  -> a units fix changes the pass rate from 100% to the number above.")

print("\n"+"="*78); print("B. DAY LEVEL - is a heavy expiry-day session actually a worse session?")
print("="*78)
rows=[]
for day,ts in sessions:
    e=expiry_of(ts)
    if not e: continue
    n=len(e); pnl=sum(float(t.realized_pnl) for t in ts)
    epnl=sum(float(t.realized_pnl) for t,_ in e)
    rows.append((n,pnl,epnl))
print(f"  expiry-active sessions: {len(rows)}")
buckets=defaultdict(list)
for n,pnl,epnl in rows: buckets[min(n,5)].append((pnl,epnl))
print(f"    {'expiry trades':>14}{'days':>6}{'mean session Rs':>18}{'mean expiry Rs':>17}")
for k in sorted(buckets):
    v=buckets[k]; lbl=f"{k}" if k<5 else "5+"
    print(f"    {lbl:>14}{len(v):>6}{sum(p for p,_ in v)/len(v):>18,.0f}{sum(e for _,e in v)/len(v):>17,.0f}")
xs=[n for n,_,_ in rows]; ys=[p for _,p,_ in rows]
mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
cov=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
r=cov/((sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))**0.5)
rnd=random.Random(7); hits=0
for _ in range(20000):
    sh=ys[:]; rnd.shuffle(sh)
    if abs(sum((x-mx)*(y-my) for x,y in zip(xs,sh)))>=abs(cov): hits+=1
print(f"\n  expiry-trade-count vs SESSION P&L: r = {r:+.3f}  p = {hits/20000:.3f}  n = {len(rows)}")
print("  'overtrading on expiry hurts' predicts r < 0.")

print("\n"+"="*78); print("C. Is expiry day itself a worse day than a non-expiry day?")
print("="*78)
ed=[]; nd=[]
for day,ts in sessions:
    p=sum(float(t.realized_pnl) for t in ts)
    (ed if expiry_of(ts) else nd).append(p)
for lbl,v in (("expiry-active sessions",ed),("sessions with no expiry trade",nd)):
    w=sum(1 for x in v if x>0)
    print(f"  {lbl:<34} n={len(v):<4} green {100*w/len(v):>5.1f}%  mean Rs {sum(v)/len(v):>9,.0f}")
pool=ed+nd; obs=sum(ed)/len(ed)-sum(nd)/len(nd); rnd=random.Random(7); hits=0
for _ in range(20000):
    rnd.shuffle(pool)
    if abs(sum(pool[:len(ed)])/len(ed)-sum(pool[len(ed):])/len(nd))>=abs(obs): hits+=1
print(f"  difference Rs {obs:,.0f}/session   p = {hits/20000:.3f}")
