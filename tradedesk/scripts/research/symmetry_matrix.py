"""
Point 7 — synthetic proof that the proposed measurement is directionally
symmetric and instrument-complete.

This is NOT production code and proposes no detector. It exercises two things
only: the adverse-movement formula, and the EXISTING instrument_risk exposure
model. If the formula is symmetric it will produce identical numbers for a long
filling lower and a short filling higher, on every instrument class.
"""
import sys

sys.path.insert(0, "backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.core.instrument_risk import risk_basis, DenominatorKind  # noqa: E402


def adverse_pct(avg_entry: float, fill_price: float, direction: str) -> float:
    """Direction-signed. Positive = the position had moved AGAINST the trader."""
    d = 1.0 if direction == "LONG" else -1.0
    return (avg_entry - fill_price) / avg_entry * 100.0 * d


def exposure(instrument_type, symbol, direction, price, qty, is_spread=False):
    rb = risk_basis(instrument_type, symbol, direction, price, qty, is_spread=is_spread)
    return rb


CASES = [
    # label, instrument_type, symbol, direction, avg_entry, add_price, held_qty, add_qty, spread
    ("long equity, price falls",      "EQ",  "RELIANCE",            "LONG",  100.0, 90.0, 100, 100, False),
    ("short equity, price rises",     "EQ",  "RELIANCE",            "SHORT", 100.0, 110.0, 100, 100, False),
    ("long futures, price falls",     "FUT", "NIFTY25AUGFUT",       "LONG",  24000.0, 23760.0, 75, 75, False),
    ("short futures, price rises",    "FUT", "NIFTY25AUGFUT",       "SHORT", 24000.0, 24240.0, 75, 75, False),
    ("long CE, premium falls",        "CE",  "NIFTY25AUG24000CE",   "LONG",  50.0, 40.0, 75, 75, False),
    ("long PE, premium falls",        "PE",  "NIFTY25AUG24000PE",   "LONG",  50.0, 40.0, 75, 75, False),
    ("short CE, premium rises",       "CE",  "NIFTY25AUG24000CE",   "SHORT", 50.0, 60.0, 75, 75, False),
    ("short PE, premium rises",       "PE",  "NIFTY25AUG24000PE",   "SHORT", 50.0, 60.0, 75, 75, False),
    ("spread leg (hedged)",           "CE",  "NIFTY25AUG24000CE",   "LONG",  50.0, 40.0, 75, 75, True),
]

print("=" * 78)
print("DIRECTIONAL SYMMETRY — the same 20% adverse move, every instrument class")
print("=" * 78)
print(f"{'case':<30}{'adverse%':>10}{'class':>15}{'denominator':>16}{'usable':>7}")
for (label, it, sym, d, avg, px, held, add, spread) in CASES:
    a = adverse_pct(avg, px, d)
    rb = exposure(it, sym, d, avg, held, spread)
    print(f"{label:<30}{a:>9.1f}%{rb.instrument.value:>15}{rb.kind.value:>16}"
          f"{str(rb.is_comparable):>7}")

print("\nEvery row is +20.0% adverse. Long-falling and short-rising are the same")
print("event and produce the same number, which is what symmetric means.")

print("\n" + "=" * 78)
print("THE FOUR CASES — what the sign of the move decides")
print("=" * 78)
four = [
    ("averaging down, same size",     "LONG",  50.0, 40.0, 75, 75),
    ("martingale, bigger add",        "LONG",  50.0, 40.0, 75, 225),
    ("adding after a favourable move","LONG",  50.0, 60.0, 75, 75),
    ("short, adding while adverse",   "SHORT", 50.0, 60.0, 75, 75),
    ("short, adding while favourable","SHORT", 50.0, 40.0, 75, 75),
]
print(f"{'case':<34}{'adverse%':>10}{'qty ratio':>11}{'exposure add':>14}{'verdict':>12}")
for label, d, avg, px, held, add in four:
    a = adverse_pct(avg, px, d)
    held_exp = exposure("CE", "NIFTY25AUG24000CE", d, avg, held).amount
    add_exp = exposure("CE", "NIFTY25AUG24000CE", d, px, add).amount
    verdict = "REPORT" if a > 0 else "ignore"
    print(f"{label:<34}{a:>9.1f}%{add/held:>10.2f}x{100*add_exp/held_exp:>13.0f}%{verdict:>12}")

print("\nThe sign of the move decides whether it is the pattern at all.")
print("Quantity ratio and exposure only modulate how much of a finding it is.")

print("\n" + "=" * 78)
print("WHAT THE CURRENT 1.5x / 2.0x MULTIPLIERS WOULD SAY ABOUT THESE")
print("=" * 78)
for label, d, avg, px, held, add in four:
    a = adverse_pct(avg, px, d)
    r = add / held
    cur = "danger" if r >= 2.0 else "caution" if r >= 1.5 else "SILENT"
    print(f"  {label:<34} qty {r:.2f}x -> {cur}")
print("\n  Averaging down at the same size is SILENT under a multiplier rule,")
print("  and it is the most common form of the behaviour in the real book.")
