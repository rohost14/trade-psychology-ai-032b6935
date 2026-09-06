"""
The drift comparator's rules, tested without a database.

WHY THIS FILE EXISTS SEPARATELY FROM `test_schema_drift.py`

The comparator's value is entirely in its normalisation rules. Compare rendered
type strings and it reports 176 differences against this database, of which 14
are real - and a check that cries 176 times is a check somebody switches off.
Normalise too eagerly and it reports nothing, including the differences that
matter.

So every rule is pinned here TWICE: once proving it treats an equivalent pair
as equal, and once proving the neighbouring NON-equivalent pair still fails.
A rule with only the first half is how a comparator goes quietly blind.

These tests need no database and no models - they feed the comparator a
synthetic schema, so they run everywhere the rest of the suite runs and they
fail for exactly one reason: a rule changed.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import (
    ARRAY, BigInteger, Boolean, Column, DateTime, Float, Integer, MetaData,
    Numeric, SmallInteger, String, Table, Text,
)
from sqlalchemy.dialects.postgresql import ARRAY as PGARRAY
from sqlalchemy.dialects.postgresql import JSONB, UUID

from tests.schema_diff import (
    KINDS,
    canonical_db_type,
    canonical_model_type,
    compare,
    load_baseline,
    split_against_baseline,
    validate_baseline,
)


# ── the equivalence rules, each with its counter-example ───────────────────

def test_text_and_an_unbounded_string_are_the_same_thing():
    """
    Postgres stores a length-less `varchar` and `text` identically, and
    SQLAlchemy's `String()` with no length emits exactly that. Reporting them
    as different produced 40 false findings on this database.
    """
    assert canonical_db_type("text") == canonical_model_type(String())
    assert canonical_db_type("text") == canonical_model_type(Text())
    assert canonical_db_type("character varying") == canonical_model_type(String())


def test_but_text_against_a_bounded_string_is_a_real_difference():
    """
    THE COUNTER-EXAMPLE. The model believes in a length ceiling the database
    does not enforce - a value longer than 20 characters is accepted by
    Postgres and violates what the code assumes. Twelve columns on this
    database are in exactly that state, and collapsing all strings to one
    canonical form would hide every one of them.
    """
    assert canonical_db_type("text") != canonical_model_type(String(20))
    assert (canonical_db_type("character varying", char_len=20)
            != canonical_model_type(String(100)))


def test_a_timestamp_is_compared_on_its_timezone_flag_not_its_printed_name():
    """
    `str(DateTime(timezone=True))` is `DATETIME` and `str(TIMESTAMP())` is
    `TIMESTAMP`, for the same underlying type, and neither string carries the
    timezone flag. Comparing the printed names produced 115 false findings.
    """
    assert (canonical_db_type("timestamp with time zone")
            == canonical_model_type(DateTime(timezone=True)))


def test_but_a_naive_timestamp_against_an_aware_one_is_a_real_difference():
    """
    THE COUNTER-EXAMPLE, and the reason the flag is read off the object. A
    `timestamp without time zone` holding what the code treats as UTC is a
    silent correctness bug, and it is invisible to any string comparison.
    """
    assert (canonical_db_type("timestamp without time zone")
            != canonical_model_type(DateTime(timezone=True)))
    assert (canonical_db_type("timestamp with time zone")
            != canonical_model_type(DateTime(timezone=False)))


def test_double_precision_is_a_precision_less_float():
    assert canonical_db_type("double precision") == canonical_model_type(Float())


def test_but_a_float_against_a_fixed_point_numeric_is_a_real_difference():
    """
    THE COUNTER-EXAMPLE. `completed_trades.pnl_pct` is `double precision` in
    the database and `Numeric(8, 2)` in the model - a displayed number stored
    as binary floating point while the code believes it is fixed to two
    decimal places.
    """
    assert canonical_db_type("double precision") != canonical_model_type(Numeric(8, 2))
    assert (canonical_db_type("numeric", num_precision=15, num_scale=4)
            != canonical_model_type(Numeric(15, 2)))


def test_integer_widths_are_distinguished():
    assert canonical_db_type("smallint") == canonical_model_type(SmallInteger())
    assert canonical_db_type("integer") == canonical_model_type(Integer())
    assert canonical_db_type("bigint") == canonical_model_type(BigInteger())
    # `completed_trades.quality_score` is smallint in the database and
    # Integer in the model.
    assert canonical_db_type("smallint") != canonical_model_type(Integer())


def test_arrays_compare_on_their_element_type():
    """
    The generic `sqlalchemy.ARRAY` and the postgresql dialect's `ARRAY` must
    both resolve. Testing only the dialect class let six columns fall through
    to a fallback that canonicalised as ('array', None) and agreed with
    nothing - eight false findings on this database.
    """
    assert (canonical_db_type("ARRAY", udt_name="_text")
            == canonical_model_type(ARRAY(String)))
    assert (canonical_db_type("ARRAY", udt_name="_text")
            == canonical_model_type(PGARRAY(Text)))
    assert (canonical_db_type("ARRAY", udt_name="_uuid")
            == canonical_model_type(ARRAY(UUID(as_uuid=True))))


def test_but_an_array_of_the_wrong_element_type_is_a_real_difference():
    assert (canonical_db_type("ARRAY", udt_name="_uuid")
            != canonical_model_type(ARRAY(String)))


def test_jsonb_and_json_are_not_the_same_type():
    """
    `trades.raw_payload` is `jsonb` in the database and generic `JSON` in the
    model. They differ in storage, in operator support and in whether an index
    can be built on them, so they must not be normalised together.
    """
    assert canonical_db_type("jsonb") == canonical_model_type(JSONB())
    assert canonical_db_type("jsonb") != canonical_model_type(
        __import__("sqlalchemy").JSON()
    )


def test_a_uuid_is_recognised():
    assert canonical_db_type("uuid") == canonical_model_type(UUID(as_uuid=True))


def test_boolean_is_not_an_integer():
    assert canonical_db_type("boolean") == canonical_model_type(Boolean())
    assert canonical_db_type("boolean") != canonical_model_type(Integer())


# ── the comparison itself, against a synthetic schema ──────────────────────

def _one_table_metadata(*columns):
    metadata = MetaData()
    Table("widgets", metadata, *columns)
    return metadata


def _live(**columns):
    """`{table: {column: information_schema-shaped row}}` for `widgets`."""
    return {"widgets": columns}


def _row(data_type, *, nullable=True, char_len=None, udt=None):
    return {
        "data_type": data_type,
        "is_nullable": "YES" if nullable else "NO",
        "character_maximum_length": char_len,
        "numeric_precision": None,
        "numeric_scale": None,
        "datetime_precision": None,
        "udt_name": udt,
    }


def test_an_identical_schema_produces_no_findings():
    """The check must be silent when nothing is wrong, or nobody reads it."""
    metadata = _one_table_metadata(
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column("label", Text(), nullable=True),
        Column("count", Integer(), nullable=False),
        Column("seen_at", DateTime(timezone=True), nullable=True),
    )
    findings = compare(
        metadata,
        _live(
            id=_row("uuid", nullable=False),
            label=_row("text"),
            count=_row("integer", nullable=False),
            seen_at=_row("timestamp with time zone"),
        ),
        {"widgets": ["id"]},
    )
    assert findings == [], [f.describe() for f in findings]


# THE PROOF THAT IT CAN FAIL. A check that cannot go red on a defect it was
# built for is worth nothing, and this is the same technique the trade_count
# verification used: introduce the defect, confirm it is reported, and name
# the exact kind so a rename cannot silently weaken the test.

@pytest.mark.parametrize("defect,expected_kind", [
    # the model forgets a column the database has
    ("column_missing_from_model", "column_missing_from_model"),
    # the model declares a column the database does not have
    ("column_missing_from_db", "column_missing_from_db"),
    # the model says NOT NULL, the database allows NULL
    ("nullable_db_permissive", "nullable_db_permissive"),
    # the database says NOT NULL, the model allows NULL
    ("nullable_db_strict", "nullable_db_strict"),
    # a length ceiling only the model believes in
    ("type_mismatch", "type_mismatch"),
    # H1 itself: no primary key in the database
    ("primary_key_mismatch", "primary_key_mismatch"),
])
def test_it_goes_red_on_a_deliberate_defect(defect, expected_kind):
    columns = [
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column("label", Text(), nullable=True),
    ]
    live = {
        "id": _row("uuid", nullable=False),
        "label": _row("text"),
    }
    primary_keys = ["id"]

    if defect == "column_missing_from_model":
        live["orphan"] = _row("character varying", char_len=20)
    elif defect == "column_missing_from_db":
        columns.append(Column("phantom", Text(), nullable=True))
    elif defect == "nullable_db_permissive":
        columns[1] = Column("label", Text(), nullable=False)
    elif defect == "nullable_db_strict":
        live["label"] = _row("text", nullable=False)
    elif defect == "type_mismatch":
        columns[1] = Column("label", String(20), nullable=True)
    elif defect == "primary_key_mismatch":
        primary_keys = []

    findings = compare(
        _one_table_metadata(*columns), _live(**live), {"widgets": primary_keys},
    )
    kinds = [f.kind for f in findings]
    assert expected_kind in kinds, (
        f"introduced a {defect} defect and the comparator reported {kinds} - "
        "a check that cannot fail on the defect it was built for is worthless"
    )


def test_a_primary_key_column_is_not_reported_as_a_nullability_mismatch():
    """
    A primary key is NOT NULL in Postgres whether or not the model says so.
    Without this exclusion every table reports its own `id`, which is 39 false
    findings and drowns the real ones.
    """
    metadata = _one_table_metadata(
        Column("id", UUID(as_uuid=True), primary_key=True),
    )
    findings = compare(
        metadata, _live(id=_row("uuid", nullable=False)), {"widgets": ["id"]},
    )
    assert findings == [], [f.describe() for f in findings]


def test_a_table_with_a_model_and_no_table_in_the_database_is_reported():
    metadata = _one_table_metadata(Column("id", UUID(as_uuid=True), primary_key=True))
    findings = compare(metadata, {}, {})
    assert [f.kind for f in findings] == ["table_missing_from_db"]


# ── the baseline mechanism ─────────────────────────────────────────────────

def test_a_baselined_finding_is_subtracted_and_a_new_one_is_not():
    metadata = _one_table_metadata(
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column("label", String(20), nullable=True),
        Column("note", String(20), nullable=True),
    )
    findings = compare(
        metadata,
        _live(
            id=_row("uuid", nullable=False),
            label=_row("text"),
            note=_row("text"),
        ),
        {"widgets": ["id"]},
    )
    baseline = {
        "widgets.label:type_mismatch": {
            "db": "text", "model": "VARCHAR(20)", "phase": 6, "why": "known",
        },
    }
    new, stale = split_against_baseline(findings, baseline)
    assert [f.key for f in new] == ["widgets.note:type_mismatch"]
    assert stale == []


def test_a_baseline_entry_whose_drift_was_fixed_is_reported_as_stale():
    """
    The baseline has to SHRINK, or the Phase 6 burn-down is unmeasurable and
    the file quietly becomes a permanent allowlist.
    """
    metadata = _one_table_metadata(Column("id", UUID(as_uuid=True), primary_key=True))
    findings = compare(metadata, _live(id=_row("uuid", nullable=False)), {"widgets": ["id"]})
    baseline = {
        "widgets.gone:type_mismatch": {
            "db": "text", "model": "VARCHAR(20)", "phase": 6, "why": "fixed already",
        },
    }
    new, stale = split_against_baseline(findings, baseline)
    assert new == []
    assert stale == ["widgets.gone:type_mismatch"]


@pytest.mark.parametrize("entry,fragment", [
    ({"db": "text", "model": "VARCHAR(20)", "phase": 6}, "missing required field"),
    ({"db": "text", "model": "VARCHAR(20)", "phase": 6, "why": "  "}, "'why' is empty"),
    ({"db": "text", "model": "VARCHAR(20)", "phase": 6, "why": "x"}, None),
])
def test_a_baseline_entry_must_carry_a_reason(entry, fragment):
    """
    An entry with no reason cannot be told apart from someone silencing a
    failure they did not want to fix.
    """
    problems = validate_baseline({"widgets.label:type_mismatch": entry})
    if fragment is None:
        assert problems == []
    else:
        assert any(fragment in p for p in problems), problems


def test_a_baseline_entry_naming_an_unknown_kind_is_rejected():
    problems = validate_baseline({
        "widgets.label:invented_kind": {
            "db": "-", "model": "-", "phase": 6, "why": "x",
        },
    })
    assert any("unknown kind" in p for p in problems), problems


# ── the model set the check runs against ───────────────────────────────────

def test_every_model_module_is_loaded_not_just_the_exported_ones():
    """
    THE ORDER-DEPENDENCE REGRESSION.

    The first version of the drift check did `import app.models` and trusted
    the package to register everything. It does not: `app/models/__init__.py`
    imports 35 of the 37 model modules, leaving out `admin_login_event` and
    `admin_setting`. So `Base.metadata` held two fewer tables when the check
    ran alone than when it ran after some other test had imported them - it
    passed in isolation and failed in the full suite.

    A check whose result depends on what else ran is not a check. This asserts
    the loader covers every module on disk, so a model added tomorrow is
    included whether or not anyone remembers to export it.
    """
    from tests.schema_diff import MODELS_DIR, load_all_models

    on_disk = {p.stem for p in MODELS_DIR.glob("*.py") if not p.stem.startswith("_")}
    loaded = set(load_all_models())

    assert loaded == on_disk, (
        f"model modules on disk but not loaded: {sorted(on_disk - loaded)}; "
        f"loaded but not on disk: {sorted(loaded - on_disk)}"
    )
    assert loaded, "no model modules were found at all - MODELS_DIR is wrong"


def test_loading_every_model_registers_more_tables_than_the_package_alone():
    """
    Names the specific gap, so closing it in `app/models/__init__.py` shows up
    here as a deliberate change rather than silently making this test vacuous.
    """
    import app.models

    from tests.schema_diff import MODELS_DIR

    exported = (MODELS_DIR / "__init__.py").read_text(encoding="utf-8")
    unexported = sorted(
        p.stem for p in MODELS_DIR.glob("*.py")
        if not p.stem.startswith("_")
        and f"from app.models.{p.stem} import" not in exported
    )

    assert unexported == ["admin_login_event", "admin_setting"], (
        "the set of model modules missing from app/models/__init__.py changed: "
        f"{unexported}. That is fine, but the drift check's loader and this "
        "test both assume it, so update them together."
    )
    assert app.models is not None  # the package still imports


# ── the real baseline file ────────────────────────────────────────────────

def test_the_shipped_baseline_is_valid_and_every_entry_is_owned():
    """
    Runs against the committed file, with no database. Catches a malformed
    hand-edit at the moment it is made rather than the next time anyone runs
    the suite with a database reachable.
    """
    baseline = load_baseline()
    assert baseline, "the baseline file is missing or empty"

    problems = validate_baseline(baseline)
    assert not problems, "\n  ".join(["malformed baseline entries:"] + problems)

    unowned = sorted(
        key for key, entry in baseline.items()
        if not isinstance(entry.get("phase"), int)
    )
    assert not unowned, f"baseline entries with no owning phase: {unowned}"

    kinds = {key.rsplit(":", 1)[-1] for key in baseline}
    assert kinds <= set(KINDS), f"unknown kinds in baseline: {sorted(kinds - set(KINDS))}"


def test_the_baseline_is_valid_json_with_the_documented_shape():
    from tests.schema_diff import BASELINE_PATH

    document = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert "accepted" in document
    for field in ("_what_this_is", "_how_to_add_an_entry", "_this_file_must_shrink"):
        assert document.get(field), (
            f"{field} is missing - the file has to explain itself, because the "
            "next person to see it will be looking at a failing check"
        )
