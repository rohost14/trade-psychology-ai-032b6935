"""
Remove test-fixture users that leaked into the application database.

WHAT LEAKED, AND WHY

`test_dashboard_api` hands its DB session to the FastAPI app through a `get_db`
override. Endpoints call `db.commit()`, which made the fixture's own user and
broker rows permanent, and the fixture's closing rollback then had nothing left
to undo. Between 2026-03-05 and 2026-09-04 that put 12,010 users and 10,848
broker accounts into the live database — 91% of the users table.

The leak itself is fixed (both `db` fixtures now bind to an outer transaction
with join_transaction_mode="create_savepoint", so a commit releases a SAVEPOINT
and cannot outlive the test). This script removes what accumulated before that.

SAFE BY CONSTRUCTION

  * DRY RUN IS THE DEFAULT. Deleting needs --execute AND a typed phrase.
  * The predicate is a POSITIVE match on three known test-generator patterns,
    then an explicit NOT IN on every protected address. Belt and braces: a typo
    in a pattern still cannot reach a survivor.
  * Pre-flight assertions run before anything is deleted, and CY6001 is
    re-checked after every batch. Any drift aborts immediately.
  * Batched, because 13k users cascading across 80 tables in one statement will
    hit the 2-minute statement_timeout.

WHAT SURVIVES

  rohitostwal09@gmail.com   CY6001      the only real account (112 trades)
  alertlab@synthetic.local  LAB000001   replay harness identity, fixed UUID
  tradedesk@synthetic.local DESK00001   replay harness identity, fixed UUID

The two synthetic identities are hard-coded in `alertlab/runner/harness.py` and
recreated idempotently by `ensure_lab_account()`. They are excluded by explicit
decision rather than because deleting them would break anything.

NOT AT RISK: the 203-session replay reference book. It is a FILE
(`docs/tradebook-CY6001-FO2025-26.csv`, gitignored) and no DELETE can reach it.

Usage:
    python scripts/cleanup_test_users.py                 # dry run (default)
    python scripts/cleanup_test_users.py --execute --confirm "DELETE TEST USERS"
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text                                    # noqa: E402
from app.core.database import SessionLocal                     # noqa: E402

CONFIRM_PHRASE = "DELETE TEST USERS"

#: Positive match on the known test generators. Anything not matched here is
#: never considered, so an unknown row is kept by default.
CANDIDATE_PREDICATE = r"""
(
     u.email LIKE 'test_schema_qa_%@qa.internal'
  OR u.email ~ '^rp0[0-9]_[0-9a-f]+@qa\.internal$'
  OR u.email LIKE '%@test.com'
)
"""

#: Never deleted, whatever the predicate says.
PROTECTED_EMAILS = (
    "rohitostwal09@gmail.com",     # the only real account
    "alertlab@synthetic.local",    # replay harness identity
    "tradedesk@synthetic.local",   # replay harness identity
)

#: What CY6001 must still hold, before and after. A cleanup that changes this
#: has gone wrong and must stop.
EXPECTED_REAL_TRADES = 112

CASCADE_TABLES = (
    "completed_trades", "positions", "risk_alerts", "journal_entries",
    "trades", "behavior_events", "trading_sessions", "position_ledger", "orders",
)


def _where() -> str:
    protected = "','".join(PROTECTED_EMAILS)
    return f"{CANDIDATE_PREDICATE} AND u.email NOT IN ('{protected}')"


async def _scalar(db, sql: str, **params) -> int:
    return (await db.execute(text(sql), params)).scalar_one()


async def preflight(db) -> dict:
    """Assertions that must hold BEFORE anything is deleted."""
    where = _where()
    facts = {}

    facts["candidates"] = await _scalar(
        db, f"SELECT count(*) FROM users u WHERE {where}")
    facts["total_users"] = await _scalar(db, "SELECT count(*) FROM users")
    facts["survivors"] = facts["total_users"] - facts["candidates"]

    protected = "','".join(PROTECTED_EMAILS)
    facts["protected_present"] = await _scalar(
        db, f"SELECT count(*) FROM users WHERE email IN ('{protected}')")
    facts["protected_in_candidates"] = await _scalar(
        db, f"SELECT count(*) FROM users u WHERE {where} "
            f"  AND u.email IN ('{protected}')")
    facts["real_trades"] = await _scalar(
        db, "SELECT count(*) FROM completed_trades ct "
            "  JOIN broker_accounts ba ON ba.id = ct.broker_account_id "
            "  JOIN users u ON u.id = ba.user_id "
            "  WHERE u.email = 'rohitostwal09@gmail.com'")

    problems = []
    if facts["protected_in_candidates"] != 0:
        problems.append(
            f"{facts['protected_in_candidates']} PROTECTED account(s) matched "
            f"the delete predicate")
    if facts["real_trades"] != EXPECTED_REAL_TRADES:
        problems.append(
            f"CY6001 holds {facts['real_trades']} completed trades, expected "
            f"{EXPECTED_REAL_TRADES}")
    if facts["protected_present"] != len(PROTECTED_EMAILS):
        problems.append(
            f"only {facts['protected_present']} of {len(PROTECTED_EMAILS)} "
            f"protected accounts exist")
    if facts["candidates"] == 0:
        problems.append("nothing matches the predicate — already clean?")
    facts["problems"] = problems
    return facts


async def report(db) -> dict:
    where = _where()
    facts = await preflight(db)

    print("=" * 70)
    print("CLEANUP DRY RUN — nothing has been deleted")
    print("=" * 70)
    print(f"  users in database          : {facts['total_users']:>7}")
    print(f"  users matching predicate   : {facts['candidates']:>7}   <- would be DELETED")
    print(f"  users surviving            : {facts['survivors']:>7}")
    print()

    print("  CASCADE IMPACT (rows removed with them)")
    ba = await _scalar(
        db, f"SELECT count(*) FROM broker_accounts ba "
            f"  JOIN users u ON u.id = ba.user_id WHERE {where}")
    print(f"    {'broker_accounts':22} {ba:>7}")
    for t in CASCADE_TABLES:
        try:
            n = await _scalar(
                db, f"SELECT count(*) FROM {t} x "
                    f"  JOIN broker_accounts ba ON ba.id = x.broker_account_id "
                    f"  JOIN users u ON u.id = ba.user_id WHERE {where}")
            total = await _scalar(db, f"SELECT count(*) FROM {t}")
            print(f"    {t:22} {n:>7}  of {total}")
        except Exception as err:                   # noqa: BLE001
            print(f"    {t:22}   n/a  ({type(err).__name__})")

    print()
    print("  SURVIVORS")
    rows = (await db.execute(text(
        f"SELECT u.email, ba.broker_name, ba.broker_user_id, "
        f"       (SELECT count(*) FROM completed_trades ct "
        f"         WHERE ct.broker_account_id = ba.id) "
        f"  FROM users u LEFT JOIN broker_accounts ba ON ba.user_id = u.id "
        f" WHERE NOT ({where}) ORDER BY 1"))).all()
    for email, broker, buid, n in rows:
        print(f"    {email:<34} {str(broker or '-'):<10} "
              f"{str(buid or '-'):<11} completed_trades={n or 0}")

    print()
    print("  SAMPLE OF WHAT WOULD GO (10 of "
          f"{facts['candidates']})")
    sample = (await db.execute(text(
        f"SELECT u.email, u.created_at::date FROM users u WHERE {where} "
        f" ORDER BY u.created_at DESC LIMIT 10"))).all()
    for email, created in sample:
        print(f"    {email:<48} {created}")

    print()
    print("  PRE-FLIGHT ASSERTIONS")
    print(f"    protected accounts present        : "
          f"{facts['protected_present']}/{len(PROTECTED_EMAILS)}")
    print(f"    protected inside delete predicate : "
          f"{facts['protected_in_candidates']} (must be 0)")
    print(f"    CY6001 completed_trades           : "
          f"{facts['real_trades']} (must be {EXPECTED_REAL_TRADES})")
    if facts["problems"]:
        print()
        print("  REFUSING TO PROCEED:")
        for p in facts["problems"]:
            print(f"    - {p}")
    else:
        print("    all assertions PASS")
    return facts


async def execute(db, batch: int) -> None:
    """Delete in batches, re-verifying the real account after each."""
    where = _where()
    removed = 0
    while True:
        ids = (await db.execute(text(
            f"SELECT u.id FROM users u WHERE {where} LIMIT :n"), {"n": batch}
        )).scalars().all()
        if not ids:
            break
        await db.execute(
            text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": list(ids)})
        await db.commit()
        removed += len(ids)

        # The real account must be untouched after every single batch.
        real = await _scalar(
            db, "SELECT count(*) FROM completed_trades ct "
                "  JOIN broker_accounts ba ON ba.id = ct.broker_account_id "
                "  JOIN users u ON u.id = ba.user_id "
                "  WHERE u.email = 'rohitostwal09@gmail.com'")
        if real != EXPECTED_REAL_TRADES:
            raise SystemExit(
                f"ABORTING after {removed}: CY6001 now has {real} completed "
                f"trades, expected {EXPECTED_REAL_TRADES}")
        print(f"    deleted {removed} (CY6001 still {real} trades)")
    print(f"  done — {removed} users removed")


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true",
                    help="actually delete (default is a dry run)")
    ap.add_argument("--confirm", default="",
                    help=f'must be exactly "{CONFIRM_PHRASE}" with --execute')
    ap.add_argument("--batch", type=int, default=500)
    args = ap.parse_args()

    async with SessionLocal() as db:
        facts = await report(db)

        if not args.execute:
            print()
            print("  DRY RUN ONLY. To delete, re-run with:")
            print(f'     --execute --confirm "{CONFIRM_PHRASE}"')
            return 0

        if facts["problems"]:
            print("\n  refusing: pre-flight assertions failed")
            return 1
        if args.confirm.strip() != CONFIRM_PHRASE:
            print(f'\n  refusing: --confirm must be exactly "{CONFIRM_PHRASE}"')
            return 1

        print("\n  EXECUTING")
        await execute(db, args.batch)
        await report(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
