import sys, random
from collections import Counter, defaultdict
sys.path.insert(0,"D:/trade-psychology-ai"); sys.path.insert(0,"D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
src=open("C:/Users/being/.claude/jobs/33a73186/tmp/p10_size.py").read()
exec(src.split("def main()")[0].split('"""')[2])

sessions=load(); fired=run(sessions)
print("="*78); print("A. THE MESSAGE LABEL - does ct_underlying name the trades shown?")
print("="*78)
mismatch=0
for day,i,ct,ts,ev in fired:
    und=ev.context["underlying"]
    syms=[t["symbol"] for t in ev.context["trade_list"]]
    unds={parse_symbol(s).underlying if s and s!="—" else s for s in syms}
    if not (len(unds)==1 and und in unds): mismatch+=1
print(f"  firings where the headline underlying is NOT the single underlying of")
print(f"  the three trades shown: {mismatch} of {len(fired)}")
print("\n  Examples of what the trader reads:")
for day,i,ct,ts,ev in fired[:5]:
    print(f"   [{ev.context['underlying']}] {ev.message[:150]}")

print("\n"+"="*78); print("B. UNITS IN THE SEQUENCE")
print("="*78)
cr=[ev for *_,ev in fired if ev.context["cross_instrument"]]
print(f"  cross-instrument (NOTIONAL rupees): {len(cr)} of {len(fired)}")
print(f"  same-underlying (QUANTITY lots)   : {len(fired)-len(cr)} of {len(fired)}")
print("  Both are stored in the same `size_sequence` field; `cross_instrument`")
print("  is the only thing distinguishing rupees from lots.")

print("\n"+"="*78); print("C. OVERLAP - what else fired on the same day (replay artifact)")
print("="*78)
import json
d=json.load(open("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26-replay.json"))
days=d["days"]
al=[(dt,a) for dt,day in days.items() for a in day.get("alerts",[])]
se_days={dt for dt,a in al if a["pattern_type"]=="size_escalation"}
print(f"  size_escalation alerts in replay: {sum(1 for _,a in al if a['pattern_type']=='size_escalation')} on {len(se_days)} days")
co=Counter(); alone=0
for dt in se_days:
    others={a["pattern_type"] for a in days[dt]["alerts"]}-{"size_escalation"}
    if not others: alone+=1
    co.update(others)
print(f"  size_escalation was the ONLY alert that day: {alone} of {len(se_days)}")
fam=("martingale_behaviour","post_loss_recovery_bet")
famdays=sum(1 for dt in se_days if any(a["pattern_type"] in fam for a in days[dt]["alerts"]))
print(f"  days where a STRONGER member of its own family also fired: {famdays} of {len(se_days)}")
for k,v in co.most_common(10): print(f"    {v:>3}  {k}")

print("\n"+"="*78); print("D. THE STRICTLY-INCREASING GATE vs CHANCE")
print("="*78)
print("  3 random distinct sizes are strictly increasing 1 time in 6 (16.7%).")
tot=0; inc=0
for day,ts in sessions:
    for i in range(3,len(ts)):
        p=ts[max(0,i-3):i]
        if len(p)<3: continue
        s=[engine._notional(t) for t in p]; tot+=1; inc+= (s[0]<s[1]<s[2])
print(f"  measured over every 3-trade window in the book: {inc} of {tot} "
      f"({100*inc/max(1,tot):.1f}%) are strictly increasing by notional")
