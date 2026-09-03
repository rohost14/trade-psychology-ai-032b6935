"""
Which migrations have been applied, and applying the ones that have not.

    python -m scripts.migrate status
    python -m scripts.migrate adopt --through 084     # one-time backfill
    python -m scripts.migrate adopt 077_add_entry_price_source.sql
    python -m scripts.migrate apply                   # run everything pending
    python -m scripts.migrate apply 085_schema_migrations_ledger.sql

WHY THIS EXISTS

The hand-written SQL files, applied by hand, with no record of which ran. The
prose disagreed with itself about 077 and nothing could settle it. This is not
a migration framework and is not trying to become one — it is the ledger that
was missing, plus the smallest runner that keeps the ledger honest.

THE BOOTSTRAP PROBLEM, STATED PLAINLY

The ledger starts empty, so on first use every file looks pending. Most of them
are not. `apply` would re-run them, and while the recent ones guard themselves
with IF NOT EXISTS, the older ones do not.

So `apply` REFUSES to run while the ledger is empty. You must first decide what
is already live and record it with `adopt`, which writes ledger rows WITHOUT
executing anything. That decision needs the database, not this script: check
the real schema, then adopt through the last migration you are sure of.

`adopt` marks rows `applied_by='adopt'` precisely so a later reader can tell an
asserted state from an observed one.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
LEDGER_FILE = "085_schema_migrations_ledger.sql"


def _files() -> List[Path]:
    return sorted(MIGRATIONS.glob("*.sql"), key=lambda p: p.name)


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


async def _ledger_exists(conn) -> bool:
    got = await conn.execute(text("SELECT to_regclass('public.schema_migrations')"))
    return got.scalar() is not None


async def _recorded(conn) -> Dict[str, Tuple[str, str, str]]:
    got = await conn.execute(
        text("SELECT filename, checksum, applied_by, applied_at "
             "FROM schema_migrations")
    )
    return {r[0]: (r[1], r[2], str(r[3])) for r in got}


def _classify(recorded: Dict[str, Tuple[str, str, str]]):
    applied, pending, changed = [], [], []
    for path in _files():
        row = recorded.get(path.name)
        if row is None:
            pending.append(path)
        elif row[0] != _checksum(path):
            changed.append((path, row))
        else:
            applied.append((path, row))
    return applied, pending, changed


async def cmd_status(engine) -> int:
    async with engine.connect() as conn:
        if not await _ledger_exists(conn):
            print("schema_migrations does not exist.")
            print(f"Create it first:  python -m scripts.migrate apply {LEDGER_FILE}")
            print(f"\n{len(_files())} migration files on disk, applied state UNKNOWN.")
            return 1
        recorded = await _recorded(conn)

    applied, pending, changed = _classify(recorded)
    print(f"applied : {len(applied)}")
    print(f"pending : {len(pending)}")
    print(f"changed : {len(changed)}   (file edited after it was recorded)")

    adopted = [a for a in applied if a[1][1] == "adopt"]
    if adopted:
        print(f"\n{len(adopted)} of the applied rows were ADOPTED, not run here.")

    if pending:
        print("\nPENDING")
        for p in pending:
            print(f"  {p.name}")
    if changed:
        print("\nCHANGED SINCE RECORDED — the file no longer describes the database")
        for path, row in changed:
            print(f"  {path.name}  recorded {row[0]} now {_checksum(path)}  ({row[2]})")
    return 0 if not changed else 2


async def cmd_adopt(engine, names: List[str], through: str | None, note: str) -> int:
    """Record files as already applied WITHOUT executing them."""
    targets: List[Path]
    if through:
        targets = [p for p in _files() if p.name[:3] <= through]
        if not targets:
            print(f"nothing at or below {through}")
            return 1
    elif names:
        by_name = {p.name: p for p in _files()}
        missing = [n for n in names if n not in by_name]
        if missing:
            print("no such migration file: " + ", ".join(missing))
            return 1
        targets = [by_name[n] for n in names]
    else:
        print("adopt needs --through NNN or one or more filenames.")
        print("It records files as applied WITHOUT running them, so this is a")
        print("claim about the database. Check the real schema before making it.")
        return 1

    async with engine.begin() as conn:
        if not await _ledger_exists(conn):
            print(f"schema_migrations does not exist. Run: apply {LEDGER_FILE}")
            return 1
        for path in targets:
            await conn.execute(
                text("INSERT INTO schema_migrations "
                     "(filename, checksum, applied_by, note) "
                     "VALUES (:f, :c, 'adopt', :n) "
                     "ON CONFLICT (filename) DO NOTHING"),
                {"f": path.name, "c": _checksum(path), "n": note},
            )
    print(f"adopted {len(targets)} migration(s) as already applied "
          f"(nothing was executed).")
    return 0


async def cmd_apply(engine, names: List[str]) -> int:
    async with engine.connect() as conn:
        ledger = await _ledger_exists(conn)
        recorded = await _recorded(conn) if ledger else {}

    by_name = {p.name: p for p in _files()}

    if names:
        missing = [n for n in names if n not in by_name]
        if missing:
            print("no such migration file: " + ", ".join(missing))
            return 1
        targets = [by_name[n] for n in names if n not in recorded]
    else:
        if not ledger or not recorded:
            print("REFUSING to apply: the ledger is empty, so every one of the")
            print(f"{len(_files())} files looks pending and most of them are not.")
            print("Decide what is already live against the real schema, then:")
            print("  python -m scripts.migrate adopt --through <last known good>")
            return 1
        _, targets, _ = _classify(recorded)

    if not targets:
        print("nothing to apply.")
        return 0

    for path in targets:
        sql = path.read_text(encoding="utf-8")
        # CREATE INDEX CONCURRENTLY cannot run inside a transaction block, and
        # several index migrations use it. Those files run in autocommit; every
        # other file gets one transaction, so a failure leaves the schema and
        # the ledger agreeing rather than half a migration recorded as done.
        concurrent = "CONCURRENTLY" in sql.upper()
        print(f"applying {path.name} ..."
              f"{' (autocommit: CONCURRENTLY)' if concurrent else ''}", flush=True)
        try:
            async with engine.connect() as conn:
                if concurrent:
                    conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
                else:
                    await conn.begin()
                # A migration file holds MANY statements. asyncpg's prepared
                # statement path refuses that ("cannot insert multiple commands
                # into a prepared statement"), so the file goes to the raw
                # driver connection, which uses the simple query protocol.
                raw = await conn.get_raw_connection()
                await raw.driver_connection.execute(sql)
                await conn.execute(
                    text("INSERT INTO schema_migrations "
                         "(filename, checksum, applied_by) "
                         "VALUES (:f, :c, 'runner') "
                         "ON CONFLICT (filename) DO NOTHING"),
                    {"f": path.name, "c": _checksum(path)},
                )
                if not concurrent:
                    await conn.commit()
        except Exception as exc:                       # noqa: BLE001 - reported
            print(f"  FAILED: {exc}")
            print("  stopped. Nothing after this file was attempted.")
            return 1
        print("  ok")
    return 0


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    ad = sub.add_parser("adopt")
    ad.add_argument("names", nargs="*")
    ad.add_argument("--through", help="adopt every file with a number <= this")
    ad.add_argument("--note", default="", help="why you believe these are applied")
    ap_ = sub.add_parser("apply")
    ap_.add_argument("names", nargs="*")
    args = ap.parse_args()

    # Supabase is reached through pgbouncer in transaction mode, which does not
    # keep a session for asyncpg's prepared statements. Without this the first
    # query can fail on `select pg_catalog.version()` with a
    # DuplicatePreparedStatementError. The app's own engine has its own
    # settings; this is a standalone script and needs its own.
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0,
                      "prepared_statement_cache_size": 0},
    )
    try:
        if args.cmd == "status":
            return await cmd_status(engine)
        if args.cmd == "adopt":
            return await cmd_adopt(engine, args.names, args.through, args.note)
        return await cmd_apply(engine, args.names)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
