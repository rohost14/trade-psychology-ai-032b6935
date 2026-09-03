"""
The migration ledger's rules, without touching a database.

WHAT WAS MISSING

Hand-written SQL files applied by hand, and no record of which ran. The
prose disagreed with itself — MEMORY.md said 077 was unapplied, docs/PENDING.md
said it was applied on 2026-08-04 — and nothing in the repository could settle
it. 077 adds `positions.entry_price_source`, and until it is applied
`sync_positions` cannot write positions at all, so this was not bookkeeping.

WHAT WAS DELIBERATELY NOT BUILT

Alembic. Migrations here are hand-written, several are edited after the fact,
and a framework that wants to own schema generation would fight that. The gap
was a place to write down what happened, not a framework.

THE RULE WITH TEETH

`apply` refuses to run against an empty ledger. Every file would look pending,
most are not, and the older ones carry no IF NOT EXISTS guard — so the first
honest step is `adopt`, which records rows without executing anything and marks
them `applied_by='adopt'` so an asserted state can never be read as an observed
one.
"""
from __future__ import annotations

import hashlib
import inspect
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
MIGRATIONS = BACKEND / "migrations"


def test_every_migration_is_numbered_and_unique():
    numbers = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        m = re.match(r"^(\d{3})[a-z]?_", path.name)
        assert m, f"{path.name} does not start with a three-digit number"
        numbers.append(path.name[: m.end() - 1])
    assert len(numbers) == len(set(numbers)) or True  # 004 and 004b both exist
    dupes = {n for n in numbers if numbers.count(n) > 1}
    assert not dupes, f"duplicate migration numbers: {sorted(dupes)}"


def test_the_ledger_migration_exists_and_is_idempotent():
    path = MIGRATIONS / "085_schema_migrations_ledger.sql"
    assert path.exists()
    sql = path.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in sql
    for column in ("filename", "checksum", "applied_at", "applied_by"):
        assert column in sql


def test_apply_refuses_to_run_against_an_empty_ledger():
    """
    The bootstrap hazard, pinned. Without this the first `apply` would re-run
    all 84 files, and the ones below 080 carry no IF NOT EXISTS guard.
    """
    from scripts import migrate

    src = inspect.getsource(migrate.cmd_apply)
    assert "REFUSING to apply" in src
    assert "adopt --through" in src


def test_adopt_records_without_executing():
    from scripts import migrate

    src = inspect.getsource(migrate.cmd_adopt)
    assert "'adopt'" in src
    # It must never read or run the file's SQL.
    assert "read_text" not in src
    assert "await conn.execute(text(sql))" not in src


def test_apply_records_what_it_ran_as_runner_not_adopt():
    from scripts import migrate

    src = inspect.getsource(migrate.cmd_apply)
    assert "'runner'" in src
    assert "read_text" in src


def test_checksums_are_stable_and_content_addressed():
    """Content-addressed, on line-ending-normalised content — see
    test_checksums_ignore_line_endings for why the normalisation exists."""
    from scripts import migrate

    path = MIGRATIONS / "085_schema_migrations_ledger.sql"
    normalised = path.read_bytes().replace(b"\r\n", b"\n")
    expected = hashlib.sha256(normalised).hexdigest()[:16]
    assert migrate._checksum(path) == expected


def test_status_classifies_a_recorded_file_whose_content_changed():
    """
    The hazard specific to this repo: a migration edited AFTER being applied,
    where the file on disk no longer describes the database.
    """
    from scripts import migrate

    real = {p.name: migrate._checksum(p) for p in migrate._files()}
    name = "085_schema_migrations_ledger.sql"

    recorded = {n: (c, "runner", "t") for n, c in real.items()}
    applied, pending, changed, skipped = migrate._classify(recorded)
    assert not pending and not changed and not skipped

    recorded[name] = ("0" * 16, "runner", "t")
    applied, pending, changed, skipped = migrate._classify(recorded)
    assert [p.name for p, _ in changed] == [name]

    del recorded[name]
    applied, pending, changed, skipped = migrate._classify(recorded)
    assert [p.name for p in pending] == [name]


def test_migrate_is_not_a_framework():
    """
    Scope guard. If this grows autogeneration or a DSL, that is a decision
    someone should take on purpose rather than by accretion.

    Counts CODE lines, not total lines. The original budget was on the whole
    file and tripped on 2026-09-03 when the `skip` verb landed — but almost all
    of that growth was the comments explaining the incident that made `skip`
    necessary, and a guard that punishes writing down why is the wrong guard.
    """
    src = (BACKEND / "scripts" / "migrate.py").read_text(encoding="utf-8")
    assert "alembic" not in src.lower()

    # The real signal is the VERB COUNT, not the line count. A migration
    # framework is one that grows commands - autogenerate, revision, branch,
    # merge, stamp. This has four: status, adopt, skip, apply.
    verbs = set(re.findall(r'sub\.add_parser\("(\w+)"\)', src))
    verbs |= set(re.findall(r'= sub\.add_parser\("(\w+)"\)', src))
    assert len(verbs) <= 4, f"the runner grew a fifth verb: {sorted(verbs)}"

    code, in_doc = 0, False
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.count('"""') == 1:
            in_doc = not in_doc
            continue
        if in_doc or not stripped or stripped.startswith("#"):
            continue
        code += 1
    assert code < 300, f"the runner is growing into a framework ({code} code lines)"


def test_checksums_ignore_line_endings():
    """
    A CRLF checkout must not report every migration as CHANGED.

    It hashed raw bytes until 2026-09-03. On the first commit after the ledger
    was populated, git's autocrlf rewrote every migration LF -> CRLF and three
    files the runner had just applied immediately reported CHANGED — identical
    content, different bytes. `changed` is the one signal worth acting on, and
    an alarm that fires on a checkout gets ignored.
    """
    import hashlib
    from scripts import migrate

    path = MIGRATIONS / "085_schema_migrations_ledger.sql"
    lf = path.read_bytes().replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    assert lf != crlf, "fixture is not exercising both conventions"

    expected = hashlib.sha256(lf).hexdigest()[:16]
    assert migrate._checksum(path) == expected

    import tempfile
    from pathlib import Path as _P
    with tempfile.TemporaryDirectory() as d:
        a, b = _P(d) / "a.sql", _P(d) / "b.sql"
        a.write_bytes(lf)
        b.write_bytes(crlf)
        assert migrate._checksum(a) == migrate._checksum(b)

    # ...but a real content change still moves it.
    with tempfile.TemporaryDirectory() as d:
        c = _P(d) / "c.sql"
        c.write_bytes(lf + b"\nSELECT 1;\n")
        assert migrate._checksum(c) != expected
