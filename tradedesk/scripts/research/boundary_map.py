"""
Where the five related detectors actually sit relative to each other.

Each scenario is run BOTH ways: through the contract's reference measurement
(fill level) and through the REAL existing detectors (completed-trade level).
Nothing is merged or deleted - this only measures the boundary.
"""
import sys

sys.path.insert(0, r"C:\Users\being\.claude\jobs\33a73186/tmp")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contract_tests import Fill, walk, ct, run_real_detectors  # noqa: E402

SYM = "NIFTY25AUG24000CE"
ROWS = []


def scenario(name, fills, trades, itype="CE", symbol=SYM, spread=False):
    w = walk(fills, itype, symbol, is_spread=spread) if fills else None
    contract = "-"
    if w:
        r, a = len(w.reported), len(w.abstained)
        contract = f"REPORT x{r}" if r else ("ABSTAIN" if a else "-")
    real = run_real_detectors(trades) if trades else {}
    ROWS.append((name, contract, real))


# 1. One position, three constant-size adverse adds. One CompletedTrade.
scenario(
    "1 position, 3 adverse adds (constant size)",
    [Fill(200, 5.05), Fill(200, 4.55), Fill(200, 4.00), Fill(200, 3.50)],
    [ct(SYM, "CE", "LONG", 800, 4.28, 3.00, 0)],
)

# 2. Three SEPARATE positions, each bigger, each a loss. No adds at all.
scenario(
    "3 separate positions, escalating size, no adds",
    None,
    [ct(SYM, "CE", "LONG", 75, 50, 45, 0),
     ct(SYM, "CE", "LONG", 150, 48, 43, 20),
     ct(SYM, "CE", "LONG", 300, 46, 41, 40)],
)

# 3. Both: three escalating positions AND adverse adds inside the last one.
scenario(
    "3 escalating positions + adverse adds in the last",
    [Fill(300, 46.0), Fill(300, 41.0), Fill(300, 36.0)],
    [ct(SYM, "CE", "LONG", 75, 50, 45, 0),
     ct(SYM, "CE", "LONG", 150, 48, 43, 20),
     ct(SYM, "CE", "LONG", 900, 41, 36, 40)],
)

# 4. Pyramiding: adds only after favourable moves.
scenario(
    "1 position, adds only while in profit",
    [Fill(75, 50.0), Fill(75, 60.0), Fill(75, 70.0)],
    [ct(SYM, "CE", "LONG", 225, 60, 65, 0)],
)

# 5. Held while down, never added. holding_loser's territory.
scenario(
    "1 position held while down, never added",
    [Fill(75, 50.0)],
    [ct(SYM, "CE", "LONG", 75, 50, 35, 0, dur=90)],
)

# 6. Re-entry after a closed loss on the same underlying (a DIFFERENT strike),
#    which is what options_premium_avg_down actually looks for.
scenario(
    "closed loss, then a NEW position on the same underlying",
    [Fill(75, 50.0), Fill(-75, 35.0)],
    [ct("NIFTY25AUG24000CE", "CE", "LONG", 75, 50, 35, 0),
     ct("NIFTY25AUG24500CE", "CE", "LONG", 75, 40, 38, 20)],
)

# 7. Spread: adverse adds inside a hedged structure.
scenario(
    "hedged spread leg, adverse adds",
    [Fill(75, 50.0), Fill(75, 45.0), Fill(75, 40.0)],
    [ct(SYM, "CE", "LONG", 225, 45, 40, 0)],
    spread=True,
)

# ── print ────────────────────────────────────────────────────────────────
cols = ["martingale_behaviour", "size_escalation",
        "options_premium_avg_down", "same_symbol_obsession"]
print("=" * 116)
print("BOUNDARY MAP — contract (fill level) vs the existing detectors (completed-trade level)")
print("=" * 116)
head = f"{'scenario':<46}{'contract':>12}"
for c in cols:
    head += f"{c.replace('_behaviour','').replace('options_premium_','opt_')[:14]:>16}"
print(head)
print("-" * 116)
for name, contract, real in ROWS:
    line = f"{name:<46}{contract:>12}"
    for c in cols:
        line += f"{str(real.get(c, '-')):>16}"
    print(line)

print("""
Reading:
  scenario 1  the behaviour happens inside ONE position. Every existing detector
              is silent, because there is only one completed trade to compare.
  scenario 2  three separate escalating positions, no adds. The contract is
              silent - correctly, nothing was added to an open position - and the
              completed-trade detectors are the ones with something to say.
  scenario 4  pyramiding. Both sides silent, which is the desired answer.
  scenario 5  held while down, never added. Both silent; this is holding_loser.
  scenario 6  re-entry after a closed loss. The contract is silent; this is what
              options_premium_avg_down actually looks at.
  scenario 7  hedged structure. The contract ABSTAINS rather than guess.
""")
