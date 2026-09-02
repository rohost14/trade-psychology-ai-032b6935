"""
Pattern 24 — `constitution_violation`, measured.

THIS DETECTOR IS DIFFERENT FROM EVERY OTHER ONE REVIEWED, and the difference
decides how it can be judged.

Its thresholds are NOT ours. Six of the seven values it reads are the trader's
own declared rules - loss cap, trade count, consecutive losses, cooldown,
no-trade windows, per-trade risk. The only numbers the product chooses are the
LADDER: `constitution_approaching_pct` 0.80 and `constitution_severe_pct` 1.20.

So the usual question - "is this threshold justified" - mostly does not apply.
The questions that do:

  1. does the LADDER do work, and is 0.80 / 1.20 defensible?
  2. what is the VOLUME per rule, and is it dominated by one?
  3. three retirements (4 consecutive_loss_streak, 15 cooldown_violation, and
     part of 17 session_meltdown) justified themselves by saying THIS detector
     carries the behaviour. Does it?
  4. it returns a LIST - how often do several rules fire on one trade, and does
     the trader get one alert or five?
  5. the `max_trade_risk` rule ABSTAINS via `quantities_for_trade` when capital
     is not determinable. How often, and what does the early `return` skip?
  6. the cooldown rule spells CONCLUDED as `<=` inline where the shared
     relation uses `<`. Does the difference bite?

OBSERVABILITY LIMIT, stated first: the reference book has NO USER PROFILE, so
the replay recorded "0 (rules off)". This detector cannot fire without declared
rules.

To measure it at all, rules must be supplied. NO VALUES ARE INVENTED HERE: the
three profiles are read from `constitution_service.generate_defaults`, the
product's own onboarding matrix, so every number measured is one a real trader
could have been given on day one.

CORRECTED 2026-09-02: the configuration is now DERIVED from
`constitution_service.generate_defaults` at run time, not copied into this
file. The copy went stale within a day of being written and produced a
708-of-740 artifact — see the note above `PROFILES`.

What generate_defaults actually SETS today:

    beginner      trades 5    consec 3
    intermediate  trades 10   consec 4
    experienced   trades 15   consec 5

and NOTHING ELSE. `daily_loss_limit`, `max_position_size` and
`per_trade_loss_limit` all come back None — suggested at most, never applied,
so the rules that read them cannot fire until the trader declares a value.

Capital is unknown for this book, so it is swept rather than picked.
"""
import sys
from collections import Counter, defaultdict
from decimal import Decimal

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p20_avgdown.py",
           encoding="utf-8").read()
src = src.replace("AVG = engine._detect_options_premium_avg_down\n", "")
exec(src.rsplit("\nmain()", 1)[0])

from app.core.trading_defaults import COLD_START_DEFAULTS   # noqa: E402

CV = engine._detect_constitution_violation

# ── CORRECTED 2026-09-02. The matrix that used to live here was STALE. ──────
#
# It hardcoded loss_pct / risk_pct / cooldown copied from
# `constitution_service.generate_defaults` as that function stood when this
# script was written (41d507d, 1 Sep) — and generate_defaults changed the SAME
# DAY (c606cc3) to stop suggesting a `max_position_size` at all.
#
# The consequence was not academic. Measuring with a stale `risk_pct=2.0`
# against Rs 50,000 of capital gives a Rs 1,000 per-trade cap, which one option
# lot exceeds on contact: `max_trade_risk` "fired" on 708 of 740 rounds, 703 of
# them critical, and that number was reported as engine behaviour. It was the
# harness measuring a value the product does not give anyone.
#
# So the configuration is now DERIVED, never copied. If onboarding changes
# again this script changes with it, and cannot silently disagree.

PROFILES = ("beginner", "intermediate", "experienced")


def onboarded_rules(profile, capital):
    """
    Exactly what `generate_defaults` SETS — nothing more.

    The distinction this function exists to preserve: onboarding SUGGESTS some
    numbers and SETS others. A suggested-but-unconfirmed rule DOES NOT EXIST —
    it arrives as None and nothing is enforced until the trader writes a value
    themselves. Measuring a suggestion as though it were a rule is precisely
    the error that produced the 708/740 artifact.
    """
    from app.services.constitution_service import constitution_service
    return constitution_service.generate_defaults(profile, capital)


def thresholds_for(profile, capital, accept_suggestions=False):
    """
    `accept_suggestions=False` -> AS ONBOARDED. The honest default: only rules
    the product actually sets. Money rules are None, so `max_trade_risk`,
    `daily_loss` and `per_trade_loss` cannot fire, which is correct — the
    trader has not declared them.

    `accept_suggestions=True` -> the trader accepted every number the UI
    offered. Today that is the daily loss limit only; NO max_position_size is
    suggested, so `max_trade_risk` stays silent in BOTH modes. That is the
    product's own decision (c606cc3), not an omission here.
    """
    d = onboarded_rules(profile, capital)
    th = dict(COLD_START_DEFAULTS)

    # Rules generate_defaults SETS.
    th["user_daily_trade_limit"] = d["daily_trade_limit"]
    th["max_consecutive_losses"] = d["max_consecutive_losses"]
    th["restricted_windows"] = d["restricted_windows"]

    # Money rules: None unless the trader declared them. Reproduced from the
    # returned dict rather than assumed, so this stays true if it changes.
    th["daily_loss_limit"] = d["daily_loss_limit"]
    th["max_position_size"] = d["max_position_size"]
    th["per_trade_loss_limit"] = d["per_trade_loss_limit"]

    # `cooldown_after_loss` is not in generate_defaults at all — onboarding
    # does not set one. It was in the old hardcoded matrix, which is another
    # thing that matrix claimed and the product does not do.
    th["user_cooldown_min"] = None

    if accept_suggestions:
        th["daily_loss_limit"] = d.get("suggested_daily_loss_limit")

    th["trading_capital"] = capital
    return th


def run(sessions, profile, capital):
    """Every event, tagged by rule."""
    out = []
    for d, tr in sessions:
        for ct in tr:
            pool = [t for t in tr if t.id != ct.id and t.exit_time <= ct.exit_time]
            c = ctx_fills(ct, pool)
            c.thresholds = thresholds_for(profile, capital)
            evs = CV(c)
            if evs:
                for e in evs:
                    out.append((d, ct, e))
    return out


def main():
    sessions = load_with_fills()
    trades = [t for _, ts in sessions for t in ts]
    print(f"BOOK: {len(sessions)} sessions, {len(trades)} rounds")
    print(f"LADDER: approaching {COLD_START_DEFAULTS['constitution_approaching_pct']} "
          f"severe {COLD_START_DEFAULTS['constitution_severe_pct']}\n")

    # ------------------------------------------------------------------ 2
    print("=" * 74)
    print("2. VOLUME PER RULE, per onboarding profile (capital Rs 50,000)")
    print("=" * 74)
    for prof in PROFILES:
        evs = run(sessions, prof, 50_000)
        by_rule = Counter(e.context["rule"] for _d, _c, e in evs)
        by_sev = Counter(e.severity for _d, _c, e in evs)
        days = len({d for d, _c, _e in evs})
        print(f"\n  {prof:<13} {len(evs):>4} events / {days} sessions of {len(sessions)}")
        print(f"    by severity: {dict(by_sev)}")
        for r, n in by_rule.most_common():
            print(f"      {r:<24} {n:>4}  ({n/len(evs):.0%})")

    # ------------------------------------------------------------------ capital sweep
    print("\n" + "=" * 74)
    print("2b. CAPITAL SENSITIVITY — the money rule against the count rules")
    print("=" * 74)
    print(f"  {'capital':>10} {'daily_loss':>11} {'daily_trades':>13} "
          f"{'consec':>8} {'cooldown':>9} {'risk':>7} {'TOTAL':>7}")
    for cap in (50_000, 100_000, 200_000, 500_000):
        evs = run(sessions, "intermediate", cap)
        r = Counter(e.context["rule"] for _d, _c, e in evs)
        print(f"  {cap:>10,} {r['daily_loss']:>11} {r['daily_trades']:>13} "
              f"{r['max_consecutive_losses']:>8} {r['cooldown']:>9} "
              f"{r['max_trade_risk']:>7} {len(evs):>7}")
    print("\n  The count rules are capital-invariant by construction; only the")
    print("  money rule moves. Pattern 17 found the same shape and it is why")
    print("  `session_meltdown` now abstains rather than deriving a limit.")

    # ------------------------------------------------------------------ 1
    print("\n" + "=" * 74)
    print("1. DOES THE LADDER DO WORK?")
    print("=" * 74)
    evs = run(sessions, "intermediate", 50_000)
    ladder_rules = ("daily_loss", "daily_trades", "max_consecutive_losses",
                    "max_trade_risk")
    for r in ladder_rules:
        sub = [e for _d, _c, e in evs if e.context["rule"] == r]
        if not sub:
            print(f"  {r:<24} no firings")
            continue
        sv = Counter(e.severity for e in sub)
        print(f"  {r:<24} {len(sub):>4}  caution {sv.get('caution',0):>3}  "
              f"danger {sv.get('danger',0):>3}  critical {sv.get('critical',0):>3}")
    binary = [e for _d, _c, e in evs if e.context["rule"] in ("cooldown", "restricted_window")]
    print(f"  {'(binary rules)':<24} {len(binary):>4}  always danger, no ladder")

    # ------------------------------------------------------------------ 4
    print("\n" + "=" * 74)
    print("4. IT RETURNS A LIST — how many rules fire on one trade?")
    print("=" * 74)
    per_trade = Counter()
    for d, tr in sessions:
        for ct in tr:
            pool = [t for t in tr if t.id != ct.id and t.exit_time <= ct.exit_time]
            c = ctx_fills(ct, pool)
            c.thresholds = thresholds_for("intermediate", 50_000)
            got = CV(c)
            if got:
                per_trade[len(got)] += 1
    tot = sum(per_trade.values())
    for k in sorted(per_trade):
        print(f"    {k} rule(s) on one trade : {per_trade[k]:>4} trades "
              f"({per_trade[k]/tot:.0%})")
    print(f"  {tot} trades produce {sum(k*v for k,v in per_trade.items())} events.")
    print("  Every one is a separate RiskAlert row at notification_level=4.")

    # ------------------------------------------------------------------ 3
    print("\n" + "=" * 74)
    print("3. DO THE THREE RETIREMENTS' BEHAVIOURS ACTUALLY LAND HERE?")
    print("=" * 74)
    for prof in PROFILES:
        evs = run(sessions, prof, 50_000)
        r = Counter(e.context["rule"] for _d, _c, e in evs)
        print(f"  {prof:<13} consecutive-loss rule {r['max_consecutive_losses']:>4}   "
              f"cooldown rule {r['cooldown']:>4}")
    print("\n  Pattern 4 retired `consecutive_loss_streak` into the first column.")
    print("  Pattern 15 retired `cooldown_violation` into the second (it measured")
    print("  181 at a declared 15-minute cooldown, against that detector's 0).")

    # ------------------------------------------------------------------ 5
    print("\n" + "=" * 74)
    print("5. THE max_trade_risk ABSTAIN, AND WHAT ITS EARLY `return` SKIPS")
    print("=" * 74)
    from app.core.risk_quantities import quantities_for_trade
    abst = 0
    for t in trades:
        rq = quantities_for_trade(t, margin=None)
        if not rq.usable_for_capital_rules:
            abst += 1
    print(f"  trades where capital is NOT determinable : {abst} of {len(trades)} "
          f"({abst/len(trades):.0%})")
    print("  On abstain the rule does `return events or None` — correct today")
    print("  because max_trade_risk is the LAST rule, but it is a `return`")
    print("  inside a rule block, not a `pass`. A rule added after it would be")
    print("  silently skipped whenever capital is not determinable.")

    # ------------------------------------------------------------------ 6
    print("\n" + "=" * 74)
    print("6. THE COOLDOWN RULE'S `<=` AGAINST THE SHARED RELATION'S `<`")
    print("=" * 74)
    same = 0
    for d, tr in sessions:
        for ct in tr:
            pool = [t for t in tr if t.id != ct.id and t.exit_time <= ct.exit_time]
            c = ctx_fills(ct, pool)
            inline = [t for t in pool if t.exit_time and t.exit_time <= ct.entry_time
                      and Decimal(str(t.realized_pnl or 0)) < 0]
            shared = [t for t in c.concluded_before_entry
                      if Decimal(str(t.realized_pnl or 0)) < 0]
            if len(inline) != len(shared):
                same += 1
    print(f"  trades where `<=` and `<` select different prior-loss sets : {same}")
    print("  (they can only differ when a close and an entry share a timestamp)")


main()
