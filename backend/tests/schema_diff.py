"""
Model <-> database schema comparison.

WHY THIS FILE EXISTS

The test suite builds its schema with `Base.metadata.create_all`, so in CI the
models and the schema agree BY CONSTRUCTION. A divergence that exists only in
the real database is invisible to every test we have. That is how
`behavior_events` lost its primary key and nobody noticed - in the test
database, that primary key exists.

This module answers the other question: does the LIVE database still look like
the models say it does. `test_schema_drift.py` runs it; this file holds the
comparison so the rules can be tested without a database.

WHY THE NORMALISATION RULES ARE THE WHOLE POINT

A naive comparator is worse than none. Comparing rendered type strings reports
`timestamp with time zone` against `TIMESTAMP` as a mismatch 69 times, and
`text` against `VARCHAR` 40 more - none of which are differences. A check that
cries 176 times gets switched off, and then it is not protecting anything.

So the rules are explicit, few, and each one is pinned by a test that also
proves it does NOT swallow a real difference:

  * `text` is equivalent to an UNBOUNDED `String()`. Postgres stores a
    length-less `varchar` and `text` identically. `text` against `String(20)`
    is NOT equivalent - the model believes in a ceiling the database does not
    enforce, and that is exactly the kind of thing worth being told about.
  * `double precision` is equivalent to a precision-less `Float()`, which is
    what SQLAlchemy emits for it. It is NOT equivalent to `Numeric(8, 2)`.
  * Timestamps are compared on their TIMEZONE FLAG, read off the type object -
    never off `str(type_)`, which prints `TIMESTAMP` and `DATETIME` for the
    same thing and drops the flag entirely.

NOTHING HERE TOUCHES THE DATABASE. It takes a schema snapshot as plain data,
which keeps the rules unit-testable and keeps this file honest about what it
is: a comparison, not a connection.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import types as satypes
# `ARRAY` is intentionally NOT imported from the postgresql dialect: see
# `canonical_model_type`. The generic `satypes.ARRAY` covers both.
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

#: Where the accepted-divergence baseline lives.
BASELINE_PATH = Path(__file__).with_name("_schema_baseline.json")

#: Where the model modules live, for `load_all_models`.
MODELS_DIR = Path(__file__).resolve().parents[1] / "app" / "models"


def load_all_models() -> list[str]:
    """
    Import EVERY module under `app/models/`, and return their names.

    `import app.models` is not enough and relying on it made this check
    order-dependent. The package's `__init__` imports 35 of the 37 model
    modules - `admin_login_event` and `admin_setting` are not in it - so
    `Base.metadata` held two fewer tables when this ran alone than when it ran
    after a test that happened to import them. The check passed in isolation
    and failed in the full suite, which is the worst possible behaviour for
    something meant to be trusted.

    Walking the directory removes the dependency on a hand-maintained list: a
    model added tomorrow is covered whether or not anyone remembers to export
    it.
    """
    import importlib

    names = []
    for path in sorted(MODELS_DIR.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        importlib.import_module(f"app.models.{path.stem}")
        names.append(path.stem)
    return names

#: Every field a baseline entry must carry. A bare name is not enough: a
#: name-only list lets a NEW drift be silenced by typing its name, with no
#: reason recorded and no owner. Requiring these makes silencing a drift a
#: reviewable act.
REQUIRED_BASELINE_FIELDS = ("db", "model", "phase", "why")


# ---------------------------------------------------------------------------
# Canonical types
# ---------------------------------------------------------------------------
# A canonical type is a (family, detail) pair. Two columns agree when their
# canonical pairs are equal. `detail` is deliberately part of the comparison:
# dropping it would make `String(20)` and `text` agree, which is one of the
# real differences this check exists to surface.

Canonical = tuple[str, Any]

#: information_schema.data_type -> (family, detail-from-row) for the simple
#: cases. Anything needing the row's precision/length is handled in code.
_PG_SIMPLE: dict[str, Canonical] = {
    "text": ("string", None),
    "boolean": ("bool", None),
    "uuid": ("uuid", None),
    "date": ("date", None),
    "bytea": ("bytes", None),
    "inet": ("inet", None),
    "jsonb": ("json", "b"),
    "json": ("json", ""),
    "smallint": ("int", 16),
    "integer": ("int", 32),
    "bigint": ("int", 64),
    "double precision": ("float", 53),
    "real": ("float", 24),
}

#: Postgres array element types arrive as `udt_name` with a leading underscore.
_PG_ARRAY_ELEMENT = {
    "_text": "string",
    "_varchar": "string",
    "_uuid": "uuid",
    "_int4": "int",
    "_int8": "int",
    "_numeric": "numeric",
    "_jsonb": "json",
}


def canonical_db_type(
    data_type: str,
    *,
    char_len: int | None = None,
    num_precision: int | None = None,
    num_scale: int | None = None,
    datetime_precision: int | None = None,
    udt_name: str | None = None,
) -> Canonical:
    """
    One `information_schema.columns` row -> canonical type.

    `data_type` is the portable name (`character varying`); `udt_name` is the
    Postgres one (`varchar`, or `_text` for an array of text). Both are needed:
    arrays report `ARRAY` as the portable name and carry the element type only
    in `udt_name`.
    """
    dt = data_type.lower()

    if dt in _PG_SIMPLE:
        return _PG_SIMPLE[dt]

    if dt in ("character varying", "varchar"):
        # No length is the same storage as `text` - see the module docstring.
        return ("string", char_len)
    if dt in ("character", "bpchar"):
        return ("char", char_len)

    if dt == "numeric":
        return ("numeric", (num_precision, num_scale))

    if dt == "timestamp with time zone":
        return ("timestamp", True)
    if dt == "timestamp without time zone":
        return ("timestamp", False)
    if dt == "time with time zone":
        return ("time", True)
    if dt == "time without time zone":
        return ("time", False)

    if dt == "array":
        return ("array", _PG_ARRAY_ELEMENT.get((udt_name or "").lower(), "unknown"))

    if dt == "user-defined":
        # A native Postgres enum or other custom type. Named by its udt so two
        # different custom types never compare equal.
        return ("user-defined", (udt_name or "").lower())

    return (dt, None)


def canonical_model_type(type_: Any) -> Canonical:
    """
    A SQLAlchemy column type OBJECT -> canonical type.

    Reads attributes off the object. `str(type_)` is never consulted: it prints
    `TIMESTAMP` for `DateTime(timezone=True)` and drops the timezone flag, so a
    string comparison reports a difference that is not there and hides one that
    is.
    """
    # Order matters where the class hierarchy nests: Text subclasses String,
    # SmallInteger/BigInteger subclass Integer, JSONB subclasses JSON.
    #
    # `satypes.ARRAY` is tested rather than the postgresql `ARRAY`, because the
    # dialect class is a SUBCLASS of the generic one - testing only the
    # dialect class misses every model that declares the generic `ARRAY`, and
    # those then fall to the fallback at the bottom of this function and
    # canonicalise as ('array', None), which agrees with nothing.
    if isinstance(type_, satypes.ARRAY):
        return ("array", canonical_model_type(type_.item_type)[0])

    if isinstance(type_, satypes.Enum):
        # Only a NATIVE enum becomes a Postgres type; a non-native one is a
        # VARCHAR with a CHECK, and must canonicalise as the string it is.
        if getattr(type_, "native_enum", True):
            return ("user-defined", (type_.name or "").lower())
        return ("string", type_.length)

    if isinstance(type_, satypes.Text):
        # `Text` has no meaningful length in Postgres.
        return ("string", None)
    if isinstance(type_, satypes.String):
        return ("string", type_.length)

    if isinstance(type_, satypes.DateTime):
        return ("timestamp", bool(type_.timezone))
    if isinstance(type_, satypes.Time):
        return ("time", bool(type_.timezone))
    if isinstance(type_, satypes.Date):
        return ("date", None)

    if isinstance(type_, satypes.SmallInteger):
        return ("int", 16)
    if isinstance(type_, satypes.BigInteger):
        return ("int", 64)
    if isinstance(type_, satypes.Integer):
        return ("int", 32)

    if isinstance(type_, satypes.Boolean):
        return ("bool", None)

    if isinstance(type_, satypes.Float):
        # SQLAlchemy emits DOUBLE PRECISION for a precision-less Float.
        return ("float", type_.precision or 53)
    if isinstance(type_, satypes.Numeric):
        return ("numeric", (type_.precision, type_.scale))

    if isinstance(type_, PGUUID) or type_.__class__.__name__ == "Uuid":
        return ("uuid", None)

    if isinstance(type_, PGJSONB):
        return ("json", "b")
    if isinstance(type_, satypes.JSON):
        return ("json", "")

    if isinstance(type_, satypes.LargeBinary):
        return ("bytes", None)

    return (type_.__class__.__name__.lower(), None)


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

#: Every kind of divergence this comparator can report. Listed so a test can
#: assert the baseline contains no kind that no longer exists.
KINDS = (
    "table_missing_from_db",
    "column_missing_from_model",
    "column_missing_from_db",
    "type_mismatch",
    "nullable_db_permissive",  # DB allows NULL, model says NOT NULL
    "nullable_db_strict",      # DB forbids NULL, model allows it
    "primary_key_mismatch",
)


@dataclass(frozen=True)
class Finding:
    """
    One divergence. `key` is what the baseline is keyed on.

    Not orderable on its fields - `column` is None for table-level findings
    and would not compare against a string. Sort on `.key`, which is always a
    string and is also what a reader recognises.
    """

    table: str
    column: str | None
    kind: str
    db: str
    model: str

    @property
    def key(self) -> str:
        return f"{self.table}.{self.column or '-'}:{self.kind}"

    def describe(self) -> str:
        return f"{self.key}\n      db={self.db}\n      model={self.model}"


# ---------------------------------------------------------------------------
# The comparison
# ---------------------------------------------------------------------------

def compare(
    metadata: Any,
    db_columns: dict[str, dict[str, dict]],
    db_primary_keys: dict[str, list[str]],
) -> list[Finding]:
    """
    Diff `Base.metadata` against a snapshot of the live schema.

    `db_columns` is `{table: {column: row-dict}}`, each row-dict carrying the
    `information_schema.columns` fields `canonical_db_type` reads plus
    `is_nullable`. `db_primary_keys` is `{table: [column, ...]}`, ordered.

    SCOPE, STATED: only tables that HAVE a model are compared. The database
    holds tables with no model at all - a separate finding class with a
    separate owner, and folding it in here would bury the model-drift signal
    under an unrelated one. A table that has a model and no table in the
    database IS reported, because that is drift.
    """
    findings: list[Finding] = []

    for table_name, table in sorted(metadata.tables.items()):
        if table_name not in db_columns:
            findings.append(Finding(
                table_name, None, "table_missing_from_db",
                db="absent", model="declared",
            ))
            continue

        live = db_columns[table_name]
        modelled = {c.name: c for c in table.columns}

        for name in sorted(set(live) - set(modelled)):
            findings.append(Finding(
                table_name, name, "column_missing_from_model",
                db=_db_type_str(live[name]), model="absent",
            ))

        for name in sorted(set(modelled) - set(live)):
            findings.append(Finding(
                table_name, name, "column_missing_from_db",
                db="absent", model=str(modelled[name].type),
            ))

        for name in sorted(set(live) & set(modelled)):
            row = live[name]
            col = modelled[name]

            db_type = canonical_db_type(
                row["data_type"],
                char_len=row.get("character_maximum_length"),
                num_precision=row.get("numeric_precision"),
                num_scale=row.get("numeric_scale"),
                datetime_precision=row.get("datetime_precision"),
                udt_name=row.get("udt_name"),
            )
            model_type = canonical_model_type(col.type)
            if db_type != model_type:
                findings.append(Finding(
                    table_name, name, "type_mismatch",
                    db=f"{_db_type_str(row)} -> {db_type}",
                    model=f"{col.type} -> {model_type}",
                ))

            db_nullable = str(row.get("is_nullable", "")).upper() == "YES"
            # A primary key column is NOT NULL whether or not the model says
            # so; comparing it would report every table's id.
            if not col.primary_key and db_nullable != bool(col.nullable):
                kind = (
                    "nullable_db_permissive" if db_nullable
                    else "nullable_db_strict"
                )
                findings.append(Finding(
                    table_name, name, kind,
                    db="NULL allowed" if db_nullable else "NOT NULL",
                    model="NULL allowed" if col.nullable else "NOT NULL",
                ))

        live_pk = db_primary_keys.get(table_name, [])
        model_pk = [c.name for c in table.primary_key.columns]
        if sorted(live_pk) != sorted(model_pk):
            findings.append(Finding(
                table_name, None, "primary_key_mismatch",
                db=str(live_pk or "NONE"), model=str(model_pk or "NONE"),
            ))

    return findings


def _db_type_str(row: dict) -> str:
    """The live type as a person would write it, for the failure message."""
    dt = row["data_type"]
    length = row.get("character_maximum_length")
    if length:
        return f"{dt}({length})"
    if dt == "numeric" and row.get("numeric_precision"):
        return f"numeric({row['numeric_precision']},{row.get('numeric_scale')})"
    if dt.lower() == "array" and row.get("udt_name"):
        return f"{dt}({row['udt_name']})"
    return dt


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

def load_baseline(path: Path | None = None) -> dict[str, dict]:
    """The accepted-divergence map, `{finding key: entry}`."""
    path = path or BASELINE_PATH
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh).get("accepted", {})


def validate_baseline(baseline: dict[str, dict]) -> list[str]:
    """
    Problems with the baseline FILE itself, as a list of messages.

    Checked because the baseline is the check's own weak point: an entry with
    no reason and no owning phase is indistinguishable from someone silencing
    a failure, and an entry naming a kind that no longer exists is a rule that
    quietly stopped applying.
    """
    problems: list[str] = []
    for key, entry in sorted(baseline.items()):
        if not isinstance(entry, dict):
            problems.append(f"{key}: entry is {type(entry).__name__}, not an object")
            continue
        missing = [f for f in REQUIRED_BASELINE_FIELDS if f not in entry]
        if missing:
            problems.append(f"{key}: missing required field(s) {missing}")
        if not str(entry.get("why", "")).strip():
            problems.append(f"{key}: 'why' is empty - say why this is accepted")
        kind = key.rsplit(":", 1)[-1]
        if kind not in KINDS:
            problems.append(f"{key}: unknown kind {kind!r}, not one of {KINDS}")
    return problems


def split_against_baseline(
    findings: Iterable[Finding], baseline: dict[str, dict],
) -> tuple[list[Finding], list[str]]:
    """
    `(new findings, baseline keys that no longer occur)`.

    The second half matters as much as the first. A baseline that is never
    pruned turns into a permanent allowlist, and the Phase 6 burn-down becomes
    unmeasurable: the file has to SHRINK as drift is fixed, so a fixed entry
    left behind is reported too.
    """
    found = {f.key: f for f in findings}
    new = [f for key, f in sorted(found.items()) if key not in baseline]
    stale = sorted(set(baseline) - set(found))
    return new, stale
