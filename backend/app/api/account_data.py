"""
Account data rights — DPDP Act 2023 §11 (access/portability) and §12 (erasure).

Two user-initiated, self-service operations backing the Settings → Danger Zone:

  GET  /api/account/export          → full machine-readable copy of the user's data
  POST /api/account/delete          → permanent, irreversible deletion of the account

These are deliberately NOT the admin endpoints in api/admin/users.py. That flow
pseudonymises PII while retaining trade history for operational reasons; a user
exercising the erasure right expects the account and its data to be gone.

Deletion safety notes:
  - Every FK pointing at broker_accounts/users declares ON DELETE CASCADE
    (verified against the live schema), so removing the `users` row removes the
    broker account and all downstream rows in one statement.
  - The Zerodha access token is revoked at the broker BEFORE the local delete,
    so a leaked token cannot outlive the account.
  - Per-account Redis state is best-effort purged; it is all derived/cached data
    and TTL-bound, so a failure there never blocks the erasure.
  - An audit row is written BEFORE deletion (it references the account id, which
    stops existing afterwards) and records no personal data.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.audit_writer import audit
from app.api.deps import get_current_user_id, get_verified_broker_account_id
from app.core.database import get_db
from app.core.rate_limiter import RateLimiter
from app.models.broker_account import BrokerAccount
from app.models.completed_trade import CompletedTrade
from app.models.journal_entry import JournalEntry
from app.models.risk_alert import RiskAlert
from app.models.trade import Trade
from app.models.trading_session import TradingSession
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.tradebook_import_service import (
    TradebookParseError, parse_tradebook_csv, to_trade_payload,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Both operations are heavy and must not be scriptable in bulk.
export_limiter = RateLimiter(max_requests=3, window_seconds=3600)   # 3 exports/hour
delete_limiter = RateLimiter(max_requests=5, window_seconds=3600)   # 5 attempts/hour
import_limiter = RateLimiter(max_requests=5, window_seconds=3600)   # 5 imports/hour

# Console tradebooks are small (a 3-year F&O export is a few MB); the cap stops
# a corrupt or hostile upload from exhausting memory.
MAX_IMPORT_BYTES = 10 * 1024 * 1024

# Cap rows per collection so a very active account cannot OOM the process.
# Signalled to the user via `truncated` in the manifest.
MAX_ROWS_PER_TABLE = 20_000


def _jsonable(value: Any) -> Any:
    """Best-effort conversion of ORM column values to JSON-safe primitives."""
    from datetime import date, datetime as _dt
    from decimal import Decimal

    if isinstance(value, (_dt, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def _row_to_dict(row: Any, exclude: set[str] | None = None) -> dict:
    exclude = exclude or set()
    return {
        col.name: _jsonable(getattr(row, col.name))
        for col in row.__table__.columns
        if col.name not in exclude
    }


async def _dump(db: AsyncSession, model, broker_account_id: UUID, exclude: set[str] | None = None):
    """Fetch one table's rows for this account, capped."""
    result = await db.execute(
        select(model)
        .where(model.broker_account_id == broker_account_id)
        .limit(MAX_ROWS_PER_TABLE)
    )
    rows = result.scalars().all()
    return [_row_to_dict(r, exclude) for r in rows], len(rows) >= MAX_ROWS_PER_TABLE


@router.get("/export")
async def export_account_data(
    user_id: UUID = Depends(get_current_user_id),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(export_limiter),
):
    """
    DPDP §11 — return everything held about this user as JSON.

    Secrets are deliberately omitted: the encrypted API secret and the broker
    access token are credentials, not user data, and exporting them would widen
    the blast radius of a leaked export file.
    """
    try:
        account = await db.get(BrokerAccount, broker_account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Broker account not found")

        user = await db.get(User, user_id)

        profile_row = (
            await db.execute(
                select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
            )
        ).scalar_one_or_none()

        trades,     t_trunc = await _dump(db, Trade, broker_account_id)
        completed,  c_trunc = await _dump(db, CompletedTrade, broker_account_id)
        journal,    j_trunc = await _dump(db, JournalEntry, broker_account_id)
        alerts,     a_trunc = await _dump(db, RiskAlert, broker_account_id)
        sessions,   s_trunc = await _dump(db, TradingSession, broker_account_id)

        truncated = {
            "trades": t_trunc, "completed_trades": c_trunc, "journal_entries": j_trunc,
            "risk_alerts": a_trunc, "trading_sessions": s_trunc,
        }

        return {
            "export_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "notice": (
                "Complete copy of the data TradeMentor holds about you. Broker "
                "credentials (access token, API secret) are intentionally excluded. "
                "Your authoritative trade records remain with Zerodha."
            ),
            "row_cap_per_section": MAX_ROWS_PER_TABLE,
            "truncated": truncated,
            "account": {
                # The users table holds no credentials (verified against the live
                # schema), so dump it whole — hand-picking fields would silently
                # drop data as the model grows, and DPDP §11 requires completeness.
                "user": _row_to_dict(user) if user else None,
                "broker_account": _row_to_dict(
                    account,
                    exclude={"access_token", "refresh_token", "api_secret_enc", "api_key"},
                ),
            },
            "profile": _row_to_dict(profile_row) if profile_row else None,
            "trades": trades,
            "completed_trades": completed,
            "journal_entries": journal,
            "risk_alerts": alerts,
            "trading_sessions": sessions,
            "counts": {
                "trades": len(trades),
                "completed_trades": len(completed),
                "journal_entries": len(journal),
                "risk_alerts": len(alerts),
                "trading_sessions": len(sessions),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Account export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/import-tradebook")
async def import_tradebook(
    file: UploadFile = File(...),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(import_limiter),
):
    """
    Import historical trades from a Zerodha Console tradebook CSV.

    Kite Connect only returns the CURRENT day's trades, so this is the only way
    a new user can arrive with real history. Imported fills go through the same
    FIFO -> completed_trades -> features pipeline as live sync.

    Deliberately does NOT run the behaviour engine over imported history:
    back-dated alerts would be noise and would corrupt the alert timeline.
    Imported data powers analytics and the record lookup only.
    """
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload the CSV version of your Console tradebook (Reports → Tradebook → download as CSV).",
        )

    content = await file.read()
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than {MAX_IMPORT_BYTES // (1024 * 1024)} MB. Split the date range and import in parts.",
        )
    if not content.strip():
        raise HTTPException(status_code=400, detail="The file is empty.")

    try:
        rows, row_errors, meta = parse_tradebook_csv(content)
    except TradebookParseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Tradebook parse crashed: {e}", exc_info=True)
        raise HTTPException(status_code=422, detail="Could not read this file as a tradebook CSV.")

    if not rows:
        return {
            "imported": 0, "duplicates": 0, "rejected": len(row_errors),
            "errors": row_errors[:100], "meta": meta,
            "message": "No usable trades found in this file.",
        }

    # Insert fills. uq_trades_broker_order (broker_account_id, order_id) makes
    # this idempotent — re-uploading an overlapping range cannot duplicate.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.models.trade import Trade

    payloads = []
    for r in rows:
        p = to_trade_payload(r)
        p["broker_account_id"] = broker_account_id
        payloads.append(p)

    imported = 0
    try:
        # Chunked so a very large import doesn't build one giant statement.
        for i in range(0, len(payloads), 1000):
            chunk = payloads[i:i + 1000]
            result = await db.execute(
                pg_insert(Trade.__table__)
                .values(chunk)
                .on_conflict_do_nothing(constraint="uq_trades_broker_order")
            )
            imported += result.rowcount or 0
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Tradebook insert failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save the imported trades.")

    duplicates = len(payloads) - imported

    # Rebuild derived data over the imported window so Analytics lights up.
    oldest = min(r["timestamp"] for r in rows)
    days_back = max(1, (datetime.now(timezone.utc) - oldest).days + 1)
    pipeline_error = None
    try:
        from app.services.pnl_calculator import pnl_calculator
        await pnl_calculator.calculate_and_update_pnl(
            broker_account_id, db, days_back=min(days_back, 3650)
        )
    except Exception as e:
        # The trades are already committed; a pipeline failure must not lose them.
        pipeline_error = str(e)[:200]
        logger.error(f"Post-import pipeline failed: {e}", exc_info=True)

    logger.info(
        "[tradebook-import] account=%s parsed=%d imported=%d dupes=%d rejected=%d",
        broker_account_id, len(rows), imported, duplicates, len(row_errors),
    )

    return {
        "imported": imported,
        "duplicates": duplicates,
        "rejected": len(row_errors),
        "errors": row_errors[:100],
        "date_range": {
            "from": oldest.isoformat(),
            "to": max(r["timestamp"] for r in rows).isoformat(),
        },
        "meta": meta,
        "pipeline_error": pipeline_error,
        "message": (
            f"Imported {imported} trades"
            + (f", skipped {duplicates} already present" if duplicates else "")
            + (f", rejected {len(row_errors)} unreadable rows" if row_errors else "")
            + "."
        ),
    }


class DeleteAccountRequest(BaseModel):
    # Must equal the account's own broker_user_id. Verified server-side so the
    # confirmation cannot be bypassed by calling the API directly.
    confirmation: str


def _purge_redis_for_account(account_id: UUID) -> int:
    """
    Best-effort removal of per-account Redis keys. All of it is derived cache or
    TTL-bound state, so failure here must never block or fail the erasure.
    """
    patterns = [
        f"rl:{account_id}:*", f"margin:{account_id}", f"margins:{account_id}",
        f"dna:{account_id}:*", f"dna_refreshes:{account_id}:*",
        f"behavior_lock:{account_id}", f"fifo_lock:{account_id}",
        f"holding_loser_chain:{account_id}", f"radar_debounce:{account_id}",
        f"ew:{account_id}:*", f"circuit:{account_id}:*",
    ]
    removed = 0
    try:
        from app.core.redis_pool import get_sync_redis
        r = get_sync_redis()
        for pattern in patterns:
            if "*" in pattern:
                for key in r.scan_iter(match=pattern, count=200):
                    removed += r.delete(key)
            else:
                removed += r.delete(pattern)
    except Exception as e:
        logger.warning(f"Redis purge during account deletion was incomplete: {e}")
    return removed


@router.post("/delete")
async def delete_account(
    body: DeleteAccountRequest,
    user_id: UUID = Depends(get_current_user_id),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(delete_limiter),
):
    """
    DPDP §12 — permanently delete the account and all associated data.

    IRREVERSIBLE. There is no soft-delete and no recovery window: deleting the
    `users` row cascades through every table that references it.
    """
    account = await db.get(BrokerAccount, broker_account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Broker account not found")

    expected = (account.broker_user_id or "").strip()
    supplied = (body.confirmation or "").strip()
    if not expected or supplied.upper() != expected.upper():
        raise HTTPException(
            status_code=400,
            detail=f"Type your Zerodha user ID ({expected or 'unknown'}) exactly to confirm deletion.",
        )

    # 1. Revoke the broker token first — a token must never outlive the account.
    token_revoked = False
    if account.access_token:
        try:
            from app.services.zerodha_service import zerodha_client
            token_revoked = await zerodha_client.revoke_token(
                account.decrypt_token(account.access_token)
            )
        except Exception as e:
            # Zerodha tokens expire daily; a failure here must not trap the user
            # in an account they asked to delete.
            logger.warning(f"Token revoke failed during account deletion: {e}")

    # 2. Audit BEFORE deleting — the row references an account id that is about
    #    to stop existing. Deliberately records no personal data.
    await audit(
        db, "user:self-service", "account_self_delete",
        target_type="broker_account", target_id=str(broker_account_id),
        details={
            "note": "DPDP erasure requested by the account holder",
            "token_revoked": token_revoked,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # 3. Delete the user row; every FK cascades from here.
    try:
        if user_id:
            await db.execute(sa_delete(User).where(User.id == user_id))
        else:
            await db.execute(sa_delete(BrokerAccount).where(BrokerAccount.id == broker_account_id))
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Account deletion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Account deletion failed — nothing was deleted.")

    # 4. Derived cache — after the durable delete has committed.
    keys_removed = _purge_redis_for_account(broker_account_id)

    logger.info(
        "[account-delete] account=%s deleted by owner (token_revoked=%s, redis_keys=%d)",
        broker_account_id, token_revoked, keys_removed,
    )
    return {
        "deleted": True,
        "token_revoked": token_revoked,
        "message": "Your account and all associated data have been permanently deleted.",
    }
