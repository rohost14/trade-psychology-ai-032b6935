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

import csv
import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
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
from app.models.monthly_snapshot import MonthlySnapshot
from app.models.order import Order
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
        # `orders` is the one section under retention (6 months, see
        # maintenance_tasks.RETENTION_MONTHS). Including it is what makes the
        # export a real answer to "get my data before it ages out" rather than
        # a formality - everything else here is kept indefinitely.
        orders,     o_trunc = await _dump(db, Order, broker_account_id)
        snapshots,  _n_trunc = await _dump(db, MonthlySnapshot, broker_account_id)

        truncated = {
            "trades": t_trunc, "completed_trades": c_trunc, "journal_entries": j_trunc,
            "risk_alerts": a_trunc, "trading_sessions": s_trunc,
            "orders": o_trunc,
        }

        return {
            "export_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "notice": (
                "Complete copy of the data TradeMentor holds about you. Broker "
                "credentials (access token, API secret) are intentionally excluded. "
                "Your authoritative trade records remain with Zerodha. "
                f"Order-level detail is kept for {_RETENTION_MONTHS_ORDERS} months; "
                "older months appear only as monthly_snapshots."
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
            "orders": orders,
            # Kept forever, and the only record of a month whose orders have
            # already been dropped. `orders_pruned_at` says which months those
            # are, so the export never implies detail it no longer holds.
            "monthly_snapshots": snapshots,
            "orders_retention_months": _RETENTION_MONTHS_ORDERS,
            "counts": {
                "trades": len(trades),
                "completed_trades": len(completed),
                "journal_entries": len(journal),
                "risk_alerts": len(alerts),
                "trading_sessions": len(sessions),
                "orders": len(orders),
                "monthly_snapshots": len(snapshots),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Account export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


#: Mirrored from maintenance_tasks so the export can state the window without
#: importing a Celery module into the request path.
_RETENTION_MONTHS_ORDERS = 6

#: Sections written into the ZIP, in the order a person would open them.
_CSV_SECTIONS = [
    ("orders", Order, {"id", "broker_account_id"}),
    ("trades", Trade, {"id", "broker_account_id"}),
    ("completed_trades", CompletedTrade, {"id", "broker_account_id"}),
    ("risk_alerts", RiskAlert, {"id", "broker_account_id"}),
    ("journal_entries", JournalEntry, {"id", "broker_account_id"}),
    ("trading_sessions", TradingSession, {"id", "broker_account_id"}),
    ("monthly_snapshots", MonthlySnapshot, {"id", "broker_account_id"}),
]


def _rows_to_csv(rows: list[dict]) -> str:
    """
    One section as CSV.

    An empty section still gets a file in the ZIP: a missing file reads as an
    error, an empty one reads as "nothing happened", and those are different
    facts about the account.
    """
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()),
                            extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({
            # `default=str` is load-bearing, not defensive. _jsonable converts
            # the COLUMN value; it does not walk inside a JSONB payload, and
            # alert `details` really does carry nested UUIDs and datetimes.
            # Without it a live export raises and the user gets a 500.
            k: (json.dumps(v, default=str) if isinstance(v, (dict, list)) else v)
            for k, v in row.items()
        })
    return buf.getvalue()


@router.get("/export/download")
async def download_account_data(
    user_id: UUID = Depends(get_current_user_id),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(export_limiter),
):
    """
    The same data as /export, as a ZIP of CSVs - the form a trader can actually
    open in a spreadsheet.

    Access control is identical to /export and that is not incidental: the
    account id comes from `get_verified_broker_account_id`, never from the query
    string, so a user cannot name someone else's account. Credentials are
    excluded by the same rule, and the rate limiter is SHARED with /export so
    the friendlier format is not a way around the 3/hour cap.

    Exists because `orders` is dropped after six months. Every other section is
    kept indefinitely, so this endpoint's real job is to let someone take the
    order-level detail before it ages out.
    """
    try:
        account = await db.get(BrokerAccount, broker_account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Broker account not found")

        manifest = {
            "export_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "row_cap_per_section": MAX_ROWS_PER_TABLE,
            "orders_retention_months": _RETENTION_MONTHS_ORDERS,
            "notice": (
                "Broker credentials are intentionally excluded. Order-level "
                f"detail is retained for {_RETENTION_MONTHS_ORDERS} months; "
                "months older than that survive as monthly_snapshots.csv."
            ),
            "counts": {},
            "truncated": {},
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, model, exclude in _CSV_SECTIONS:
                rows, truncated = await _dump(db, model, broker_account_id, exclude)
                manifest["counts"][name] = len(rows)
                manifest["truncated"][name] = truncated
                zf.writestr(f"{name}.csv", _rows_to_csv(rows))
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        buf.seek(0)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={
                "Content-Disposition":
                    f'attachment; filename="tradementor-data-{stamp}.zip"',
                # The file names the user's own trades; a shared cache holding
                # it would be a disclosure bug, not a performance win.
                "Cache-Control": "no-store",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Account export download failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/monthly-summary")
async def monthly_summary(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Per-month summaries, newest first - what a trader still has of a month whose
    order detail has aged out.

    `orders_available` is the honest half: false once the month's partition has
    been dropped, so the UI can say the detail is gone rather than leaving
    someone to wonder why an old month will not open.
    """
    rows = (await db.execute(
        select(MonthlySnapshot)
        .where(MonthlySnapshot.broker_account_id == broker_account_id)
        .order_by(MonthlySnapshot.month.desc())
    )).scalars().all()

    return {
        "orders_retention_months": _RETENTION_MONTHS_ORDERS,
        "months": [
            {**r.to_dict(), "orders_available": r.orders_pruned_at is None}
            for r in rows
        ],
    }


def _twin_key(symbol, txn_type, qty, price, ts):
    """Identity of a fill for reconciling a tradebook row against a live-captured
    (postback) row that lacks a trade_id: (symbol, side, qty, price~2dp, minute)."""
    try:
        minute = ts.replace(second=0, microsecond=0) if ts else None
    except Exception:
        minute = None
    return (
        (symbol or "").upper(),
        (txn_type or "").upper(),
        int(qty or 0),
        round(float(price), 2) if price is not None else None,
        minute,
    )


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

    # Reconcile against POSTBACK-only rows (order_id == kite_order_id — captured live from
    # a webhook that had no per-fill trade_id, so they key differently from a tradebook
    # row's trade_id). Without this, re-importing an overlapping range would DUPLICATE
    # those fills. Match by (symbol, side, qty, price~2dp, minute) and drop the twin.
    from sqlalchemy import select as _select
    reconciled = 0
    try:
        w_lo = min(r["timestamp"] for r in rows)
        w_hi = max(r["timestamp"] for r in rows)
        existing = (await db.execute(
            _select(
                Trade.tradingsymbol, Trade.transaction_type, Trade.quantity,
                Trade.price, Trade.order_timestamp,
            ).where(
                Trade.broker_account_id == broker_account_id,
                Trade.order_id == Trade.kite_order_id,
                Trade.order_timestamp >= w_lo,
                Trade.order_timestamp <= w_hi,
            )
        )).all()
        twins = {_twin_key(sym, txn, qty, price, ts) for sym, txn, qty, price, ts in existing}
        if twins:
            kept = [
                p for p in payloads
                if _twin_key(p["tradingsymbol"], p["transaction_type"], p["quantity"], p["price"], p["order_timestamp"]) not in twins
            ]
            reconciled = len(payloads) - len(kept)
            payloads = kept
    except Exception as e:
        logger.warning(f"Tradebook reconcile skipped (non-fatal): {e}")

    imported = 0
    if payloads:
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

    # Everything not newly inserted was already present — either by trade_id (constraint)
    # or as a live postback twin (reconcile).
    duplicates = (len(payloads) - imported) + reconciled

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
        "reconciled": reconciled,   # tradebook rows collapsed onto live postback twins
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


def _redis_purge_patterns(account_id) -> list[str]:
    """Per-account Redis key patterns to erase on account deletion (DPDP).
    Pure — returned separately so the exact set is unit-testable. `*` = SCAN glob."""
    return [
        # rate limiter — both the legacy shape and the current rl:acct:{bid}:* shape
        # (F3/A1 re-keyed authed limits to acct:{bid}); TTL-bound but purge anyway.
        f"rl:{account_id}:*", f"rl:acct:{account_id}:*",
        f"margin:{account_id}", f"margins:{account_id}",
        f"dna:{account_id}:*", f"dna_refreshes:{account_id}:*",
        f"behavior_lock:{account_id}", f"fifo_lock:{account_id}",
        f"holding_loser_chain:{account_id}", f"radar_debounce:{account_id}",
        f"ew:{account_id}:*", f"circuit:{account_id}:*",
        # Event-bus per-account replay stream — holds recent trade/alert payloads
        # (symbols, P&L, order ids). Was previously NOT purged (DP2).
        f"stream:{account_id}",
    ]


def _purge_redis_for_account(account_id: UUID) -> int:
    """
    Best-effort removal of per-account Redis keys. All of it is derived cache or
    TTL-bound state, so failure here must never block or fail the erasure.
    """
    patterns = _redis_purge_patterns(account_id)
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
