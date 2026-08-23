import json
d = json.load(open("docs/research/data/episodes_full.json"))
eps, sessions = d["episodes"], d["sessions"]
print(f"sessions={sessions}  episode candidates (>=2 attempts)={len(eps)}")

h2 = [e for e in eps if e["attempts"] >= 3 and e["exposure_grew"]]
print(f"\nH2 firings (>=3 attempts AND exposure grew): {len(h2)}")
print(f"  = {len(h2)/sessions*100:.1f}% of sessions, ~1 per {sessions/max(len(h2),1):.0f} sessions")

import collections
print("\nattempts distribution:", dict(sorted(collections.Counter(e['attempts'] for e in eps).items())))
print("exposure grew:", sum(1 for e in eps if e['exposure_grew']), "of", len(eps))

prof = [e for e in h2 if e["total_pnl"] > 0]
loss = [e for e in h2 if e["total_pnl"] <= 0]
print(f"\nH2 firings on PROFITABLE episode P&L: {len(prof)}")
print(f"H2 firings on LOSING episode P&L    : {len(loss)}")

print("\nEvery H2 firing:")
print(f"{'day':11s} {'und':14s} {'att':>3s} {'qtys':28s} {'pnl':>9s} end")
for e in sorted(h2, key=lambda e: e["day"]):
    q = "->".join(str(x) for x in e["qtys"])[:28]
    print(f"{e['day']:11s} {e['underlying'][:14]:14s} {e['attempts']:3d} {q:28s} "
          f"{e['total_pnl']:9,.0f} {'WIN' if e['ended_in_win'] else '-'}")
