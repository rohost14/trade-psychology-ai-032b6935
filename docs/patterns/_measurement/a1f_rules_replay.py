# -*- coding: utf-8 -*-
"""
Rules-enabled replay, for the four death_spiral questions.

Drives the existing harness rather than editing it: same `read_fills`,
`carry_fills`, `replay_day` and the SAME `_single_run` lock, so it cannot
collide with a normal replay. Writes its sidecar to the job tmp dir, so
`docs/*-replay.json` — which is gitignored and unrecoverable — is untouched.

WHAT IS DIFFERENT FROM A NORMAL RUN

  1. A declared `daily_loss_limit`, so `constitution_violation` can fire and
     the `discipline` domain becomes reachable at all. The value is 5,000 —
     the figure Pattern 17 already used, not a new one. No other rule is
     declared: every extra rule would only ADD discipline events, so every
     count here is a LOWER bound on what a fully-ruled trader would see.
  2. BehaviorEvents are captured, not just RiskAlerts. death_spiral reads
     events INCLUDING suppressed ones, and with rules on, the engine suppresses
     siblings as `constitution_breach` — so an alert-only sidecar would hide
     exactly the domain contributors under test.
  3. death_spiral's `details` are captured, which carry `domains`,
     `continued_escalation`, `compressed_within_min` and `trigger_events`.

Nothing in the repo is modified. No thresholds are changed.
"""
import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path("D:/trade-psychology-ai")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tradedesk" / "scripts"))

import replay_tradebook as H  # noqa: E402

OUT = Path(r"C:\Users\being\.claude\jobs\33a73186\tmp\RULES-replay.json")
CSV = ROOT / "docs" / "tradebook-CY6001-FO2025-26.csv"
CAPITAL = 200_000.0
PROFILE = {"daily_loss_limit": 5000.0}


async def collect_events(db):
    from sqlalchemy import select
    from app.models.behavior_event import BehaviorEvent
    from alertlab.runner.harness import account_id

    rows = (await db.execute(
        select(BehaviorEvent).where(
            BehaviorEvent.broker_account_id == account_id())
    )).scalars().all()
    return [{
        "detector": r.detector,
        "severity": r.severity,
        "detected_at": r.detected_at.isoformat() if r.detected_at else None,
        "shadow": bool(r.shadow),
        "suppressed": (r.evidence or {}).get("_suppressed"),
        "evidence": (r.evidence or {}) if r.detector == "death_spiral" else None,
    } for r in rows]


async def main():
    csv = CSV
    if not csv.exists():
        cands = sorted(ROOT.glob("docs/*.csv"))
        print("CSV not found. Candidates: %s" % [c.name for c in cands])
        return 2

    fills = H.read_fills(csv)
    by_day = defaultdict(list)
    for f in fills:
        by_day[f["date"]].append(f)
    days = sorted(by_day)
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        days = days[-int(sys.argv[1]):]      # smoke mode: last N sessions
    print("%d fills across %d sessions; replaying %d." % (len(fills), len(by_day), len(days)),
          flush=True)
    print("RULES ENABLED: %s   capital Rs %.0f" % (PROFILE, CAPITAL), flush=True)

    out = {}
    started = datetime.now()
    for i, day in enumerate(days, 1):
        alerts, positions = await H.replay_day(
            day, by_day[day], CAPITAL, PROFILE, carry=H.carry_fills(fills, day))
        async with H._db()() as db:
            events = await collect_events(db)

        # `no_stoploss` stays unjudgeable (no order type in a tradebook).
        # CAPITAL_DERIVED is NOT skipped here: rules are on, so session_meltdown
        # has a declared limit to work from - that is the point of this run.
        judged = [a for a in alerts if a["pattern_type"] not in H.UNJUDGEABLE]
        pnl = round(sum(c["pnl"] for c in positions["closed"]), 2)
        out[str(day)] = {
            "pnl": pnl,
            "alerts": [{"pattern_type": a["pattern_type"], "severity": a["severity"],
                        "detected_at": a["detected_at"],
                        "details": a.get("details") if a["pattern_type"] == "death_spiral" else None}
                       for a in judged],
            "events": events,
            "trades": [{"symbol": c["symbol"], "pnl": c["pnl"],
                        "entry_time": c.get("entry_time"), "exit_time": c.get("exit_time")}
                       for c in positions["closed"]],
        }
        ds = [a for a in judged if a["pattern_type"] == "death_spiral"]
        el = (datetime.now() - started).total_seconds() / 60
        print("  [%d/%d] %s  %3d trades  P&L %10.0f  %2d alerts  %2d events%s  (%.0fm)"
              % (i, len(days), day, len(positions["closed"]), pnl, len(judged),
                 len(events),
                 ("  DEATH_SPIRAL=" + ",".join(a["severity"] for a in ds)) if ds else "",
                 el), flush=True)

        OUT.write_text(json.dumps({
            "source": csv.name, "capital": CAPITAL, "profile": PROFILE,
            "sessions_done": i, "sessions_total": len(days),
            "skipped_patterns": sorted(H.UNJUDGEABLE),
            "days": out,
        }, indent=1), encoding="utf-8")

    print("\nDONE. %d sessions -> %s" % (len(days), OUT), flush=True)
    return 0


if __name__ == "__main__":
    H.use_identity(H.DESK)
    with H._single_run():
        raise SystemExit(asyncio.run(main()))
