"""
Lightweight tracked SQL migration runner (deep-review P8-MIG1).

Ends the "apply .sql files by hand, no record of what's applied" problem: records
each applied migration in a `schema_migrations` table so state is known and
migrations are never silently re-applied or skipped. Alembic is the eventual
target; this is the minimum tracking that makes schema deploys safe + auditable.

Usage (run from the `backend/` directory):
    python -m scripts.db.migrate --status     # show applied vs pending
    python -m scripts.db.migrate --stamp      # BASELINE: record ALL current .sql as
                                              #   applied WITHOUT running them. Run this
                                              #   ONCE on an existing DB that already has
                                              #   the schema (003–074), so the runner does
                                              #   not try to re-apply them.
    python -m scripts.db.migrate --dry-run    # show what would be applied
    python -m scripts.db.migrate              # apply pending migrations, in order

Safety:
- Each migration runs in its own transaction; a failure stops the run (later
  migrations are NOT applied) and is reported.
- `schema_migrations` is created if missing. Additive — running --status or --stamp
  never alters your existing schema.
"""
import os
import re
import sys
import glob
import asyncio
import argparse

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "migrations")


# ── Pure logic (unit-tested) ─────────────────────────────────────────────────
def _sort_key(version: str):
    """Natural sort: leading integer, then the remaining string (so 004 < 004b < 10)."""
    m = re.match(r"^(\d+)(.*)$", version)
    if not m:
        return (10**9, version)
    return (int(m.group(1)), m.group(2))


def order_versions(versions):
    """Return versions sorted in migration order."""
    return sorted(versions, key=_sort_key)


def pending_versions(all_versions, applied):
    """Ordered versions not yet applied (preserves input order, which is already sorted)."""
    applied = set(applied)
    return [v for v in all_versions if v not in applied]


def discover_migrations(migrations_dir=MIGRATIONS_DIR):
    """Return [(version, path)] for every .sql file, in migration order."""
    paths = glob.glob(os.path.join(migrations_dir, "*.sql"))
    pairs = [(os.path.splitext(os.path.basename(p))[0], p) for p in paths]
    pairs.sort(key=lambda vp: _sort_key(vp[0]))
    return pairs


# ── DB side ──────────────────────────────────────────────────────────────────
def _dsn() -> str:
    from app.core.config import settings
    # asyncpg wants a plain postgresql:// DSN, not SQLAlchemy's +asyncpg driver form.
    return re.sub(r"^postgresql\+asyncpg://", "postgresql://", settings.DATABASE_URL)


async def _connect():
    import asyncpg
    return await asyncpg.connect(_dsn())


async def _ensure_table(conn):
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "  version TEXT PRIMARY KEY,"
        "  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ")"
    )


async def _applied(conn) -> set:
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {r["version"] for r in rows}


async def _record(conn, version: str):
    await conn.execute(
        "INSERT INTO schema_migrations(version) VALUES($1) ON CONFLICT DO NOTHING", version
    )


async def _run(args) -> int:
    migrations = discover_migrations()
    all_versions = [v for v, _ in migrations]
    conn = await _connect()
    try:
        await _ensure_table(conn)
        applied = await _applied(conn)
        pend = pending_versions(all_versions, applied)

        if args.status:
            print(f"applied: {len(applied)} | pending: {len(pend)}")
            for v in pend:
                print(f"  PENDING {v}")
            return 0

        if args.stamp:
            for v in all_versions:
                await _record(conn, v)
            print(f"stamped {len(all_versions)} migrations as applied (ran none).")
            return 0

        if not pend:
            print("nothing to apply — schema up to date.")
            return 0

        if args.dry_run:
            print("would apply (in order):")
            for v in pend:
                print(f"  {v}")
            return 0

        path_by_version = dict(migrations)
        for v in pend:
            sql = open(path_by_version[v], encoding="utf-8").read()
            print(f"applying {v} ...", flush=True)
            async with conn.transaction():
                await conn.execute(sql)
                await _record(conn, v)
        print(f"applied {len(pend)} migration(s).")
        return 0
    finally:
        await conn.close()


def main() -> int:
    p = argparse.ArgumentParser(description="Tracked SQL migration runner (MIG1).")
    p.add_argument("--status", action="store_true", help="show applied vs pending")
    p.add_argument("--stamp", action="store_true", help="baseline: record all as applied, run none")
    p.add_argument("--dry-run", action="store_true", help="show what would apply")
    args = p.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
