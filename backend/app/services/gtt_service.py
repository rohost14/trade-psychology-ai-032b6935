"""
GTT (Good Till Triggered) Discipline Service

Tracks whether traders honour their stop-losses by using GTT orders vs
manually overriding / closing positions before GTT fires.

How it works:
  1. On each radar cycle: poll GET /gtt/triggers for active GTTs per account.
     Upsert into gtt_tracking table.

  2. When a webhook arrives with variety='gtt': the GTT fired → outcome='honored'.

  3. When a position closes and there was an active GTT for that symbol but
     the closing order has variety='regular' → outcome='overridden'.

  4. A "discipline score" is computed as:
       honored_count / (honored_count + overridden_count)  (last 30 days)

  The score is used INTERNALLY only — it is NEVER surfaced directly on the
  frontend. It feeds the alert message generator to personalise suggestions.

Matching logic:
  - GTT condition.tradingsymbol matches position.tradingsymbol
  - If the symbol closes via a regular-variety order while a GTT exists → override
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, func, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def sync_gtt_triggers(
    broker_account_id: UUID,
    access_token: str,
    db: AsyncSession,
) -> Dict:
    """
    Fetch live GTT list from Kite and upsert into gtt_tracking.
    Returns summary: {upserted, already_up_to_date}
    """
    from app.services.zerodha_service import zerodha_client, KiteAPIError

    try:
        gtts = await zerodha_client.get_gtt_triggers(access_token)
    except KiteAPIError as e:
        logger.warning(f"[gtt_service] Failed to fetch GTTs for {broker_account_id}: {e}")
        return {"error": str(e)}

    upserted = 0
    for gtt in gtts:
        gtt_id = gtt.get("id")
        if not gtt_id:
            continue

        condition = gtt.get("condition", {})
        orders = gtt.get("orders", [])
        first_order = orders[0] if orders else {}

        trigger_price = None
        if condition.get("trigger_values"):
            trigger_price = condition["trigger_values"][0]

        status_map = {
            "active": "active",
            "triggered": "triggered",
            "disabled": "cancelled",
            "expired": "expired",
            "cancelled": "cancelled",
        }
        gtt_status = status_map.get(gtt.get("status", ""), "active")

        triggered_at = None
        if gtt_status == "triggered":
            triggered_at = datetime.now(timezone.utc)

        await db.execute(
            text(
                """
                INSERT INTO gtt_tracking
                    (broker_account_id, gtt_id, tradingsymbol, exchange,
                     trigger_price, order_type, quantity, gtt_status,
                     triggered_at, updated_at)
                VALUES
                    (:bid, :gid, :sym, :exc,
                     :tprice, :otype, :qty, :status,
                     :trig_at, now())
                ON CONFLICT (broker_account_id, gtt_id) DO UPDATE SET
                    gtt_status   = EXCLUDED.gtt_status,
                    triggered_at = COALESCE(gtt_tracking.triggered_at, EXCLUDED.triggered_at),
                    updated_at   = now()
                """
            ),
            {
                "bid": str(broker_account_id),
                "gid": gtt_id,
                "sym": condition.get("tradingsymbol"),
                "exc": condition.get("exchange"),
                "tprice": trigger_price,
                "otype": first_order.get("order_type"),
                "qty": first_order.get("quantity"),
                "status": gtt_status,
                "trig_at": triggered_at,
            },
        )
        upserted += 1

    await db.commit()
    return {"upserted": upserted}


async def record_gtt_honored(
    broker_account_id: UUID,
    tradingsymbol: str,
    order_id: str,
    db: AsyncSession,
) -> bool:
    """
    Called from webhook handler when variety='gtt'.
    Marks the matching active GTT as honored.
    Returns True if a matching GTT was found.
    """
    result = await db.execute(
        text(
            """
            UPDATE gtt_tracking
            SET outcome = 'honored',
                outcome_order_id = :order_id,
                gtt_status = 'triggered',
                triggered_at = now(),
                updated_at = now()
            WHERE broker_account_id = :bid
              AND tradingsymbol = :sym
              AND outcome IS NULL
              AND gtt_status = 'active'
            """
        ),
        {"bid": str(broker_account_id), "sym": tradingsymbol, "order_id": order_id},
    )
    await db.commit()
    found = (result.rowcount or 0) > 0
    if found:
        logger.info(f"[gtt_service] GTT honored: {broker_account_id} / {tradingsymbol}")
    return found


async def record_gtt_overridden(
    broker_account_id: UUID,
    tradingsymbol: str,
    order_id: str,
    db: AsyncSession,
) -> bool:
    """
    Called from webhook handler when a position closes via variety='regular'
    while an active GTT exists for that symbol.
    Marks the GTT as overridden (trader manually exited before SL fired).
    Returns True if a matching active GTT was found.
    """
    result = await db.execute(
        text(
            """
            UPDATE gtt_tracking
            SET outcome = 'overridden',
                outcome_order_id = :order_id,
                updated_at = now()
            WHERE broker_account_id = :bid
              AND tradingsymbol = :sym
              AND outcome IS NULL
              AND gtt_status = 'active'
            """
        ),
        {"bid": str(broker_account_id), "sym": tradingsymbol, "order_id": order_id},
    )
    await db.commit()
    found = (result.rowcount or 0) > 0
    if found:
        logger.info(f"[gtt_service] GTT overridden: {broker_account_id} / {tradingsymbol}")
    return found


async def get_discipline_summary(
    broker_account_id: UUID,
    db: AsyncSession,
    days: int = 30,
) -> Dict:
    """
    Compute SL discipline stats for the past N days.
    Returns:
    {
      "honored": int,
      "overridden": int,
      "active": int,
      "discipline_rate": float | None,   # 0.0–1.0, None if no history
      "active_gtts": [ {gtt_id, tradingsymbol, trigger_price, ...} ]
    }
    NOTE: discipline_rate is for internal use only — not shown on frontend.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        text(
            """
            SELECT
                outcome,
                COUNT(*) as cnt
            FROM gtt_tracking
            WHERE broker_account_id = :bid
              AND updated_at >= :since
              AND outcome IS NOT NULL
            GROUP BY outcome
            """
        ),
        {"bid": str(broker_account_id), "since": since},
    )
    rows = result.fetchall()
    counts = {row[0]: row[1] for row in rows}

    honored = counts.get("honored", 0)
    overridden = counts.get("overridden", 0)
    total_closed = honored + overridden
    discipline_rate = (honored / total_closed) if total_closed > 0 else None

    # Active GTTs
    active_result = await db.execute(
        text(
            """
            SELECT gtt_id, tradingsymbol, exchange, trigger_price, quantity, created_at
            FROM gtt_tracking
            WHERE broker_account_id = :bid
              AND gtt_status = 'active'
            ORDER BY created_at DESC
            """
        ),
        {"bid": str(broker_account_id)},
    )
    active_gtts = [
        {
            "gtt_id": row[0],
            "tradingsymbol": row[1],
            "exchange": row[2],
            "trigger_price": float(row[3]) if row[3] else None,
            "quantity": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
        }
        for row in active_result.fetchall()
    ]

    return {
        "honored": honored,
        "overridden": overridden,
        "active": len(active_gtts),
        "discipline_rate": round(discipline_rate, 3) if discipline_rate is not None else None,
        "active_gtts": active_gtts,
    }


async def has_active_gtt(
    broker_account_id: UUID,
    tradingsymbol: str,
    db: AsyncSession,
) -> bool:
    """Check if there's an active (unresolved) GTT for this symbol."""
    result = await db.execute(
        text(
            "SELECT 1 FROM gtt_tracking "
            "WHERE broker_account_id = :bid "
            "  AND tradingsymbol = :sym "
            "  AND gtt_status = 'active' "
            "  AND outcome IS NULL "
            "LIMIT 1"
        ),
        {"bid": str(broker_account_id), "sym": tradingsymbol},
    )
    return result.fetchone() is not None
