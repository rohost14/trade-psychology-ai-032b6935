"""The case matrix. Run: python contract_cases.py"""
import sys

sys.path.insert(0, r"C:\Users\being\.claude\jobs\33a73186/tmp")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contract_tests import Fill, walk, ct, run_real_detectors  # noqa: E402

PASS = FAIL = 0
results = []


def case(n, label, fills, itype, symbol, spread=False, *,
         expect_report=0, expect_ignore=0, expect_abstain=0, note=""):
    global PASS, FAIL
    w = walk(fills, itype, symbol, is_spread=spread)
    rep = len(w.reported)
    ign = sum(1 for e in w.events if e.verdict == "IGNORE")
    abst = len(w.abstained)
    ok = (rep == expect_report and ign == expect_ignore and abst == expect_abstain)
    PASS += ok
    FAIL += (not ok)
    results.append((n, label, w, ok, rep, ign, abst,
                    expect_report, expect_ignore, expect_abstain, note))
    return w


# ── directional symmetry: every instrument, both ways ────────────────────
case(1, "long equity, adds while down",
     [Fill(100, 100.0), Fill(100, 90.0)], "EQ", "RELIANCE", expect_report=1)
case(2, "short equity, adds while up",
     [Fill(-100, 100.0), Fill(-100, 110.0)], "EQ", "RELIANCE", expect_report=1)
case(3, "long futures, adds while down",
     [Fill(75, 24000.0), Fill(75, 23760.0)], "FUT", "NIFTY25AUGFUT", expect_report=1)
case(4, "short futures, adds while up",
     [Fill(-75, 24000.0), Fill(-75, 24240.0)], "FUT", "NIFTY25AUGFUT", expect_report=1)
case(5, "long CE, premium falls",
     [Fill(75, 50.0), Fill(75, 40.0)], "CE", "NIFTY25AUG24000CE", expect_report=1)
case(6, "long PE, premium falls",
     [Fill(75, 50.0), Fill(75, 40.0)], "PE", "NIFTY25AUG24000PE", expect_report=1)
case(7, "short CE, premium rises",
     [Fill(-75, 50.0), Fill(-75, 60.0)], "CE", "NIFTY25AUG24000CE", expect_report=1)
case(8, "short PE, premium rises",
     [Fill(-75, 50.0), Fill(-75, 60.0)], "PE", "NIFTY25AUG24000PE", expect_report=1)

# ── add size: smaller / same / larger ────────────────────────────────────
case(9, "adverse add SMALLER than held",
     [Fill(150, 50.0), Fill(50, 40.0)], "CE", "NIFTY25AUG24000CE", expect_report=1)
case(10, "adverse add SAME size",
      [Fill(75, 50.0), Fill(75, 40.0)], "CE", "NIFTY25AUG24000CE", expect_report=1)
case(11, "adverse add LARGER than held",
      [Fill(75, 50.0), Fill(225, 40.0)], "CE", "NIFTY25AUG24000CE", expect_report=1)

# ── repetition and escalation ────────────────────────────────────────────
case(12, "three constant-size adverse adds",
      [Fill(200, 5.05), Fill(200, 4.55), Fill(200, 4.00), Fill(200, 3.50)],
      "CE", "ASIANPAINT25JUN2400CE", expect_report=3)
case(13, "three increasing-size adverse adds",
      [Fill(75, 50.0), Fill(75, 45.0), Fill(150, 40.0), Fill(300, 30.0)],
      "CE", "NIFTY25AUG24000CE", expect_report=3)

# ── favourable and break-even ────────────────────────────────────────────
case(14, "add after a FAVOURABLE move (long)",
      [Fill(75, 50.0), Fill(75, 60.0)], "CE", "NIFTY25AUG24000CE", expect_ignore=1)
case(15, "add after a FAVOURABLE move (short)",
      [Fill(-75, 50.0), Fill(-75, 40.0)], "CE", "NIFTY25AUG24000CE", expect_ignore=1)
case(16, "add at exactly BREAK-EVEN",
      [Fill(75, 50.0), Fill(75, 50.0)], "CE", "NIFTY25AUG24000CE", expect_ignore=1)
case(17, "mixed: favourable add then adverse add",
      [Fill(75, 50.0), Fill(75, 55.0), Fill(75, 40.0)], "CE",
      "NIFTY25AUG24000CE", expect_report=1, expect_ignore=1)

# ── reductions, closes, flips ────────────────────────────────────────────
case(18, "partial exit (decreasing exposure)",
      [Fill(150, 50.0), Fill(-75, 45.0)], "CE", "NIFTY25AUG24000CE")
case(19, "partial exit THEN re-add while adverse",
      [Fill(150, 50.0), Fill(-75, 45.0), Fill(75, 40.0)], "CE",
      "NIFTY25AUG24000CE", expect_report=1)
case(20, "close, then re-enter (separate position)",
      [Fill(75, 50.0), Fill(-75, 45.0), Fill(75, 44.0)], "CE",
      "NIFTY25AUG24000CE", note="re-entry is not an add")
case(21, "position FLIPS through zero",
      [Fill(75, 50.0), Fill(-150, 45.0), Fill(-75, 50.0)], "CE",
      "NIFTY25AUG24000CE", expect_report=1,
      note="flip resets, then the short adds while adverse")
case(22, "single fill, never added",
      [Fill(75, 50.0), Fill(-75, 45.0)], "CE", "NIFTY25AUG24000CE")

# ── multi-leg and hedges ─────────────────────────────────────────────────
case(23, "spread leg, adverse add",
      [Fill(75, 50.0), Fill(75, 40.0)], "CE", "NIFTY25AUG24000CE",
      spread=True, expect_abstain=1)
case(24, "hedged multi-leg, repeated adverse adds",
      [Fill(75, 50.0), Fill(75, 45.0), Fill(75, 40.0)], "CE",
      "NIFTY25AUG24000CE", spread=True, expect_abstain=2)

# ── report ───────────────────────────────────────────────────────────────
print("=" * 92)
print("SYNTHETIC CONTRACT TESTS")
print("=" * 92)
print(f"{'#':>3} {'case':<44}{'report':>7}{'ignore':>7}{'abst':>6}   {'expected':>16}  ok")
for (n, label, w, ok, r, i, a, er, ei, ea, note) in results:
    exp = f"{er}/{ei}/{ea}"
    print(f"{n:>3} {label:<44}{r:>7}{i:>7}{a:>6}   {exp:>16}  {'PASS' if ok else 'FAIL'}")
print(f"\n{PASS} passed, {FAIL} failed")

print("\n" + "=" * 92)
print("DIRECTIONAL SYMMETRY — each long/short pair must produce the same number")
print("=" * 92)
pairs = [(1, 2, "equity"), (3, 4, "futures"), (5, 7, "CE"), (6, 8, "PE")]
for a, b, lbl in pairs:
    wa = results[a - 1][2]
    wb = results[b - 1][2]
    va = [e.adverse_pct for e in wa.events if e.kind == "add"][0]
    vb = [e.adverse_pct for e in wb.events if e.kind == "add"][0]
    sym = "MATCH" if abs(va - vb) < 1e-9 else "MISMATCH"
    print(f"  {lbl:<10} long {va:>7.2f}%   short {vb:>7.2f}%   {sym}")

print("\n" + "=" * 92)
print("EXPOSURE — what the existing instrument-risk model returns")
print("=" * 92)
for n in (1, 2, 3, 4, 5, 7, 23):
    _, label, w, *_ = results[n - 1]
    add = [e for e in w.events if e.kind == "add"][0]
    if add.exposure_before is None:
        print(f"  {n:>2} {label:<40} ABSTAINED — {add.note}")
    else:
        grew = add.exposure_after > add.exposure_before
        print(f"  {n:>2} {label:<40} {add.exposure_before:>12,.0f} -> "
              f"{add.exposure_after:>12,.0f}  {'grew' if grew else 'fell'}")
