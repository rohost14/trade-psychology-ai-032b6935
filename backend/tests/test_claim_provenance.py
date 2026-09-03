"""
Trader-facing claims must have provenance — backend half.

The frontend half is `src/test/claimProvenance.test.ts` and carries the full
rationale. Both read the SAME marker vocabulary, `docs/copy/claim_markers.json`,
because a vocabulary copied into two places is the exact failure this repo has
already paid for once — pattern names drifting across four copies.

Scope here is deliberately NOT all of `backend/app`. A broad scan returned 31
hits of which 28 were docstrings, log lines and "saved to history"; a guard at
10% precision gets muted within a week. `scope.backend.files` lists the modules
that emit text a trader can actually read.

The claim this half exists for: `ai_service._fallback_chat_response` told
traders what "most traders" do, and those replies are returned precisely when
the model is unreachable — the one moment the coach speaks having read nothing.

Docstrings are skipped. They are dev-facing, and this repo's idiom is to quote
a removed claim in the comment that removes it; a guard that fails on its own
removal notes gets switched off.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"

MARKERS = json.loads((REPO / "docs/copy/claim_markers.json").read_text(encoding="utf-8"))
ALLOWLIST = json.loads(
    (REPO / "docs/copy/claims.allowlist.json").read_text(encoding="utf-8")
)["entries"]

RULES = [
    (group, re.compile(p, re.I))
    for group, spec in MARKERS["marker_groups"].items()
    for p in spec["patterns"]
]

SCOPED_FILES = [BACKEND / f for f in MARKERS["scope"]["backend"]["files"]]


def _readable_text(src: str) -> str:
    """
    The file's text with `#` comments and docstrings removed.

    REPLACED A LITERAL EXTRACTOR, 2026-09-03. The frontend half used the same
    approach and had a proven blind spot: it tracked string state to pull out
    literals, and an apostrophe in ordinary JSX prose read as an opening quote,
    swallowing everything up to the next apostrophe. A claim planted in one of
    those regions was invisible to it — demonstrated on Welcome.tsx, where the
    scanner extracted 417 literals and none contained the planted claim.

    Matching the whole text is strictly more sensitive, and the precision cost
    is near zero because every marker is a long English phrase rather than a
    token. Comments and docstrings still go, because this repo's idiom is to
    QUOTE a removed claim in the comment that removes it, and a guard that
    fails on its own removal notes gets switched off within a week.
    """
    triples = ("'" * 3, '"' * 3)
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch == "#":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if src[i : i + 3] in triples:
            closing = src[i : i + 3]
            i += 3
            while i < n and src[i : i + 3] != closing:
                i += 1
            i += 3
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def test_marker_vocabulary_loaded():
    """A wrong path silently disabling the guard is the failure that makes a
    test like this worthless. Fail loudly instead."""
    assert len(RULES) > 20
    assert len(SCOPED_FILES) >= 5
    for path in SCOPED_FILES:
        assert path.exists(), f"scoped module missing: {path}"


def test_no_unsourced_claims_in_trader_facing_modules():
    violations: list[str] = []
    for path in SCOPED_FILES:
        rel = path.relative_to(REPO).as_posix()
        for raw in _readable_text(path.read_text(encoding="utf-8")).splitlines():
            line = raw.strip()
            if not line:
                continue
            hit = next((g for g, rx in RULES if rx.search(line)), None)
            if hit is None:
                continue
            allowed = any(
                e["file"] == rel and e["literal_sha256"] == _sha(line) for e in ALLOWLIST
            )
            if not allowed:
                violations.append(f"\n  {rel}\n    [{hit}] {line[:140]!r}\n    hash: {_sha(line)}")

    assert not violations, (
        "Unsourced trader-facing claim(s)."
        + "".join(violations)
        + "\n\nFix by REMOVING the claim, or - only with genuine provenance - add to"
        "\ndocs/copy/claims.allowlist.json as DERIVED / CITED / FIXTURE / LEGAL."
        "\nThere is no UNSOURCED category. Do not source a claim to make CI green.\n"
    )


def _sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@pytest.mark.parametrize("entry", ALLOWLIST, ids=lambda e: e["file"])
def test_allowlist_entries_are_well_formed(entry):
    assert entry["category"] in {"DERIVED", "CITED", "FIXTURE", "LEGAL"}
    assert len(entry["source"].strip()) > 10, "an exception needs a real source"
    assert re.fullmatch(r"[0-9a-f]{16}", entry["literal_sha256"])
