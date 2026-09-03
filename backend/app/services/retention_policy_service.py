"""
The retention window, and the rules about who may change it.

WHY THIS IS A SERVICE AND NOT A CONSTANT

The window itself is a product decision that was settled: `orders` is kept for
six months behind a verified-snapshot gate, `behavior_events` is kept forever.
Nothing here reopens that. What it adds is the ability for an admin to LENGTHEN
a window, or to shorten one deliberately, without a redeploy — and, more
importantly, a single place where the limits on that live.

THE CODE VALUES ARE THE FLOOR OF TRUST, NOT JUST A DEFAULT

An unreadable or malformed settings store resolves to the code values, never to
something shorter. Every failure path here errs towards keeping data: a
retention system whose failure mode is "delete more" is not a retention system.

WHAT AN ADMIN MAY NOT DO

  * go below RETENTION_FLOOR_MONTHS - the detector evidence window plus room
  * turn on `behavior_events` retention by accident: it is the trader's own
    behavioural history, so enabling it at all is a separate, explicit act
  * bypass the snapshot gate, which is enforced in the maintenance task and is
    not configurable from anywhere

Storage reuses the existing `admin_settings` table rather than adding one. The
keys are deliberately NOT registered in admin_settings_service.DEFAULTS, so the
generic /config/global endpoint rejects them as unknown and this validated path
is the only way in.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

#: Code default per partitioned parent. None = never drop.
#:
#: `orders` is EVIDENCE, not history: F4 reads protective orders only within a
#: position's own lifetime, so six months is far past anything a detector can
#: reach, and a month is summarised and verified before its partition may go.
#:
#: `behavior_events` is the trader's own behavioural history and what analytics
#: renders back to them. Deleting it is a PRODUCT decision, not a maintenance
#: one, so the code default is None and an admin has to say otherwise.
RETENTION_MONTHS: Dict[str, Optional[int]] = {
    "orders": 6,
    "behavior_events": None,
}

#: No configured window may go below this. Three months covers the longest
#: window any detector reads plus room for a late reconciliation; below it the
#: gate would be preserving summaries of data the engine still wanted.
RETENTION_FLOOR_MONTHS = 3

#: An admin may lengthen freely, but a window long enough to be a typo (fifty
#: years) is more likely a mistake than an intention.
RETENTION_CEILING_MONTHS = 120

_KEY_PREFIX = "retention_months_"


def setting_key(parent: str) -> str:
    return f"{_KEY_PREFIX}{parent}"


class RetentionPolicyError(ValueError):
    """A rejected change. Carries a message meant for the admin, not a trace."""


def validate(parent: str, months: Optional[int]) -> Optional[int]:
    """
    Return the value to store, or raise with a reason an admin can act on.

    `None` means never drop and is always allowed - it can only ever keep more
    data than the alternative.
    """
    if parent not in RETENTION_MONTHS:
        raise RetentionPolicyError(f"unknown partitioned table: {parent}")
    if months is None:
        return None
    if isinstance(months, bool) or not isinstance(months, int):
        raise RetentionPolicyError("retention must be a whole number of months, or null")
    if months < RETENTION_FLOOR_MONTHS:
        raise RetentionPolicyError(
            f"retention cannot go below {RETENTION_FLOOR_MONTHS} months - "
            f"detectors still read within that window"
        )
    if months > RETENTION_CEILING_MONTHS:
        raise RetentionPolicyError(
            f"retention above {RETENTION_CEILING_MONTHS} months is almost "
            f"certainly a typo; use null to keep data indefinitely"
        )
    return months


def is_narrowing(parent: str, current: Optional[int], proposed: Optional[int]) -> bool:
    """
    True when the change makes MORE data eligible for deletion.

    Narrowing is the only direction that can destroy anything, so it is the only
    direction that needs a typed confirmation. Turning retention ON for a table
    that had none is the sharpest case of it.
    """
    if proposed is None:
        return False                       # keeping forever narrows nothing
    if current is None:
        return True                        # never-drop -> drop is a narrowing
    return proposed < current


async def get_effective(db) -> Dict[str, Dict[str, Any]]:
    """
    The window actually in force, per parent, with where it came from.

    FAIL-SAFE: any store problem resolves to the code value. A settings table
    that cannot be read must never be able to widen what gets deleted.
    """
    from sqlalchemy import select
    from app.models.admin_setting import AdminSetting

    stored: Dict[str, Any] = {}
    try:
        rows = (await db.execute(
            select(AdminSetting).where(
                AdminSetting.key.in_([setting_key(p) for p in RETENTION_MONTHS])
            )
        )).scalars().all()
        stored = {r.key: r for r in rows}
    except Exception as err:                       # noqa: BLE001 - fail safe
        logger.error(f"[retention] settings unreadable, using code values: {err}")
        stored = {}

    out: Dict[str, Dict[str, Any]] = {}
    for parent, code_value in RETENTION_MONTHS.items():
        row = stored.get(setting_key(parent))
        months, source, updated_by, updated_at = code_value, "code", None, None
        if row is not None:
            try:
                months = validate(parent, row.value)
                source = "admin"
                updated_by = row.updated_by
                updated_at = row.updated_at.isoformat() if row.updated_at else None
            except RetentionPolicyError as err:
                # A stored value that no longer validates - a floor was raised,
                # say - must not silently take effect.
                logger.error(
                    f"[retention] stored {parent} value {row.value!r} is invalid "
                    f"({err}); falling back to the code value {code_value!r}"
                )
        out[parent] = {
            "months": months,
            "source": source,
            "code_default": code_value,
            "updated_by": updated_by,
            "updated_at": updated_at,
        }
    return out


async def get_effective_months(db) -> Dict[str, Optional[int]]:
    """Just the numbers — what the maintenance task acts on."""
    return {p: v["months"] for p, v in (await get_effective(db)).items()}


def get_effective_months_safe_sync() -> Dict[str, Optional[int]]:
    """
    Code values only. Used where no session is available; never used to DROP.
    """
    return dict(RETENTION_MONTHS)


async def set_policy(db, parent: str, months: Optional[int], admin_email: str) -> Dict[str, Any]:
    """
    Persist a window. Validation has already run in `validate`; confirmation for
    a narrowing change is enforced at the API boundary, where the admin's typed
    phrase actually is.
    """
    from datetime import datetime, timezone
    from sqlalchemy import JSON, select
    from app.models.admin_setting import AdminSetting

    value = validate(parent, months)
    key = setting_key(parent)

    # The column is JSONB NOT NULL. Assigning Python None would write SQL NULL
    # and violate it; JSON.NULL writes the JSON value `null`, which reads back
    # as None and is what "never drop" means here.
    stored_value = JSON.NULL if value is None else value

    existing = (await db.execute(
        select(AdminSetting).where(AdminSetting.key == key)
    )).scalar_one_or_none()
    if existing:
        existing.value = stored_value
        existing.updated_by = admin_email
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(AdminSetting(key=key, value=stored_value, updated_by=admin_email))
    await db.commit()

    return (await get_effective(db))[parent]


async def clear_policy(db, parent: str, admin_email: str) -> Dict[str, Any]:
    """
    Drop the admin override so the code value applies again.

    Deleting the row rather than writing the code value back into it keeps
    `source` honest: "code" should mean nobody has an opinion stored, not
    "somebody once chose the number that happens to match".
    """
    from sqlalchemy import delete
    from app.models.admin_setting import AdminSetting

    if parent not in RETENTION_MONTHS:
        raise RetentionPolicyError(f"unknown partitioned table: {parent}")

    await db.execute(
        delete(AdminSetting).where(AdminSetting.key == setting_key(parent))
    )
    await db.commit()
    logger.info(f"[retention] {parent} override cleared by {admin_email}")
    return (await get_effective(db))[parent]
