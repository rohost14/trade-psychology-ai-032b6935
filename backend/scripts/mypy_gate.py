"""
Run mypy and fail only on findings that are NOT in the recorded baseline.

WHY THIS EXISTS

mypy has been in CI since it was added to catch "the wrong method / attribute
that doesn't exist" class that only surfaces at runtime. It was set
`continue-on-error: true` "until the untyped-code noise is triaged", and the
triage never happened. On 2026-09-06 it was found to be reporting two real
bugs that had been live for months:

  * `app/api/profile.py` imported `_get_user_id_from_broker_account` from
    `app.api.zerodha`, a symbol that exists nowhere. Both guardian endpoints
    raised ImportError on every call, so `guardian_confirmed` — whose only
    setter is inside one of them — could never become true, and the trader's
    nominated guardian could never be told anything.
  * `app/api/danger_zone.py` called `get_escalation_status(account_id=...)`
    against a signature of `(user_id, trigger_reason)`. TypeError on every call.

Both were reported. Nobody saw them, because a non-blocking check is a check
nobody reads — the same lesson as the build that stayed red for three days
while a correct pyflakes failure named the exact file and line of a third bug.

WHY A BASELINE RATHER THAN JUST TURNING IT ON

There are 65 existing findings across 24 files, overwhelmingly typing noise:
`Result[Any].rowcount` (correct at runtime for DML), `"object" has no
attribute "append"` from untyped dicts, `Sequence` vs `list` returns. Making
mypy blocking with those present would put CI red immediately, which recreates
exactly the condition that let all three bugs through.

So this records what exists and fails on what is new. Same shape as
`backend/tests/_schema_baseline.json`, and for the same reason: a check that is
red on day one gets ignored, and an ignored check protects nothing.

THE BASELINE IS KEYED WITHOUT LINE NUMBERS

`file | error-code | message`, never the line. An allowlist keyed on line
numbers goes stale the moment anything above it moves, and then it excuses a
position that has shifted — which is worse than having no allowlist. That
mistake was made once already today, in `test_behavior_event_writers.py`, and
is not being repeated here.

USAGE

    python scripts/mypy_gate.py              # check; non-zero exit on new findings
    python scripts/mypy_gate.py --update     # rewrite the baseline (deliberate act)
"""
from __future__ import annotations

import collections
import re
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
BASELINE = BACKEND / "mypy_baseline.txt"

#: `path:line: error: message  [code]` — line is captured and then discarded.
LINE_RE = re.compile(r"^(?P<path>[^:]+):\d+:(?:\d+:)?\s+error:\s+(?P<msg>.*?)\s*\[(?P<code>[a-z-]+)\]\s*$")


def _run_mypy() -> list[str]:
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", "--config-file", "mypy.ini", "--no-color-output", "app"],
        cwd=BACKEND, capture_output=True, text=True,
    )
    return (proc.stdout or "").splitlines()


def _findings(lines: list[str]) -> collections.Counter:
    """`{ "path|code|message": count }` — path separators normalised.

    Windows mypy prints `app\\api\\x.py`, Linux prints `app/api/x.py`. A
    baseline recorded on one and checked on the other would report every
    finding as new, so the separator is normalised here rather than in the
    file.
    """
    found: collections.Counter = collections.Counter()
    for line in lines:
        m = LINE_RE.match(line.strip())
        if not m:
            continue
        path = m.group("path").replace("\\", "/").strip()
        found[f"{path}|{m.group('code')}|{m.group('msg')}"] += 1
    return found


def _load_baseline() -> collections.Counter:
    if not BASELINE.exists():
        return collections.Counter()
    counts: collections.Counter = collections.Counter()
    for raw in BASELINE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        count, _, key = line.partition("\t")
        counts[key] = int(count)
    return counts


def main() -> int:
    lines = _run_mypy()
    found = _findings(lines)

    if "--update" in sys.argv:
        body = "\n".join(f"{n}\t{k}" for k, n in sorted(found.items()))
        BASELINE.write_text(
            "# mypy findings accepted as of the last deliberate update.\n"
            "# Keyed `path|code|message` WITHOUT a line number, so an edit above\n"
            "# a finding does not make it look new.\n"
            "# Regenerate ONLY on purpose: `python scripts/mypy_gate.py --update`.\n"
            "# Shrinking this file is progress; growing it needs a reason.\n"
            f"{body}\n",
            encoding="utf-8",
        )
        print(f"baseline written: {sum(found.values())} findings, {len(found)} distinct")
        return 0

    baseline = _load_baseline()

    new = {k: n - baseline.get(k, 0) for k, n in found.items() if n > baseline.get(k, 0)}
    fixed = {k: baseline[k] - found.get(k, 0) for k in baseline if baseline[k] > found.get(k, 0)}

    if new:
        print("mypy found issues that are NOT in the baseline:\n")
        for key, extra in sorted(new.items()):
            path, code, msg = key.split("|", 2)
            print(f"  {path}  [{code}]\n      {msg}" + (f"   (x{extra} new)" if extra > 1 else ""))
        print(
            "\nThis gate exists because two bugs that had been live for months — "
            "the guardian ImportError and the cooldown TypeError — were reported "
            "here and never read, while mypy was non-blocking.\n"
            "Fix the finding, or record it with `python scripts/mypy_gate.py --update` "
            "and say why in the commit."
        )
        return 1

    if fixed:
        print(f"{sum(fixed.values())} baselined finding(s) no longer occur. "
              "Run `python scripts/mypy_gate.py --update` to shrink the baseline.")

    print(f"mypy gate: OK ({sum(found.values())} known findings, none new)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
