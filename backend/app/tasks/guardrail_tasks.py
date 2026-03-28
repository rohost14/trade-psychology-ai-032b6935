"""
Guardrail Rule Monitor

Evaluates active guardrail rules every 60 seconds during market hours.
Reads LTP from Redis cache (KiteTicker) — zero KiteConnect API calls.
Fires WhatsApp + push notification on first trigger, then marks as triggered (done).

Redis keys used:
  guardrail:loss_start:{rule_id}:{symbol}  → ISO timestamp when position entered loss
  (clock resets when position turns positive — continuous loss duration only)
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

MARKET_OPEN_HOUR = 9
MARKET_OPEN_MIN = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MIN = 25


def _get_redis():
    import redis as redis_lib
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


def _is_market_hours() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    open_m = MARKET_OPEN_HOUR * 60 + MARKET_OPEN_MIN
    close_m = MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MIN
    return open_m <= minutes <= close_m


def _get_cached_ltp(r, instrument_token: int) -> float | None:
    val = r.get(f"ltp:{instrument_token}")
    return float(val) if val else None


@celery_app.task(name="app.tasks.guardrail_tasks.check_guardrail_rules")
def check_guardrail_rules():
    """Beat task — every 60 seconds during market hours."""
    if not _is_market_hours():
        return
    import asyncio
    asyncio.run(_run_checks())


async def _run_checks():
    from app.core.database import SessionLocal
    from app.models.guardrail_rule import GuardrailRule
    from app.models.position import Position
    from sqlalchemy import select

    now_utc = datetime.now(timezone.utc)
    r = _get_redis()

    async with SessionLocal() as db:
        # Fetch all active, non-expired rules
        result = await db.execute(
            select(GuardrailRule).where(
                GuardrailRule.status == "active",
                GuardrailRule.expires_at > now_utc,
            )
        )
        rules = result.scalars().all()

        if not rules:
            return

        # Group rules by account
        by_account: dict[UUID, list] = {}
        for rule in rules:
            by_account.setdefault(rule.broker_account_id, []).append(rule)

        for account_id, account_rules in by_account.items():
            # Fetch open positions for this account
            pos_result = await db.execute(
                select(Position).where(
                    Position.broker_account_id == account_id,
                    Position.status == "open",
                )
            )
            positions = pos_result.scalars().all()
            if not positions:
                continue

            # Build unrealized P&L map: symbol → unrealized_pnl
            pnl_map: dict[str, float] = {}
            for pos in positions:
                ltp = _get_cached_ltp(r, pos.instrument_token) if pos.instrument_token else None
                if ltp is None:
                    # Fall back to stored unrealized_pnl
                    pnl_map[pos.tradingsymbol] = float(pos.unrealized_pnl or pos.pnl or 0)
                else:
                    avg = float(pos.average_price or 0)
                    qty = int(pos.quantity or 0)
                    multiplier = 1 if (pos.transaction_type or "BUY") == "BUY" else -1
                    pnl_map[pos.tradingsymbol] = (ltp - avg) * qty * multiplier

            total_pnl = sum(pnl_map.values())

            for rule in account_rules:
                triggered = await _evaluate_rule(rule, pnl_map, total_pnl, r)
                if triggered:
                    await _fire_rule(rule, pnl_map, total_pnl, account_id, db)

        await db.commit()


async def _evaluate_rule(rule, pnl_map: dict, total_pnl: float, r) -> bool:
    """Return True if rule condition is met."""
    ct = rule.condition_type
    val = float(rule.condition_value)
    targets = rule.target_symbols  # None = all positions

    if ct == "total_pnl_drop":
        return total_pnl <= val

    # Filter to target symbols
    if targets:
        relevant = {s: p for s, p in pnl_map.items() if s in targets}
    else:
        relevant = pnl_map

    if not relevant:
        return False

    if ct == "loss_threshold":
        return min(relevant.values()) <= val

    if ct == "profit_target":
        return max(relevant.values()) >= val

    if ct == "loss_range_time":
        # Check continuous loss duration using Redis timestamps
        now_utc = datetime.now(timezone.utc)
        for symbol, pnl in relevant.items():
            key = f"guardrail:loss_start:{rule.id}:{symbol}"
            if pnl < 0:
                ts_str = r.get(key)
                if ts_str is None:
                    # Just entered loss — record start time
                    r.set(key, now_utc.isoformat(), ex=86400)
                else:
                    loss_start = datetime.fromisoformat(ts_str)
                    elapsed_minutes = (now_utc - loss_start).total_seconds() / 60
                    if elapsed_minutes >= val:
                        return True
            else:
                # Position turned positive — reset clock
                r.delete(key)
        return False

    return False


async def _fire_rule(rule, pnl_map: dict, total_pnl: float, account_id: UUID, db):
    """Mark rule as triggered and send notifications."""
    from app.models.broker_account import BrokerAccount
    from app.models.user_profile import UserProfile
    from app.services.whatsapp_service import WhatsAppService
    from app.services.push_notification_service import PushNotificationService
    from sqlalchemy import select

    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(IST)

    # Mark triggered immediately (prevent double-fire if task runs again before commit)
    rule.status = "triggered"
    rule.triggered_at = now_utc
    rule.trigger_count = (rule.trigger_count or 0) + 1
    rule.updated_at = now_utc

    # Build human-readable description
    ct = rule.condition_type
    val = float(rule.condition_value)
    targets = rule.target_symbols
    symbol_str = ", ".join(targets) if targets else "all positions"

    if ct == "loss_threshold":
        worst = min((pnl_map.get(s, 0) for s in (targets or pnl_map)), default=0)
        condition_desc = f"Position loss ₹{abs(worst):,.0f} exceeded threshold ₹{abs(val):,.0f}"
        current_val = f"₹{worst:,.0f}"
    elif ct == "profit_target":
        best = max((pnl_map.get(s, 0) for s in (targets or pnl_map)), default=0)
        condition_desc = f"Profit ₹{best:,.0f} hit target ₹{val:,.0f}"
        current_val = f"₹{best:,.0f}"
    elif ct == "total_pnl_drop":
        condition_desc = f"Portfolio P&L ₹{total_pnl:,.0f} hit floor ₹{abs(val):,.0f}"
        current_val = f"₹{total_pnl:,.0f}"
    else:  # loss_range_time
        condition_desc = f"Position in loss for {int(val)}+ minutes"
        current_val = "continuous loss"

    message = (
        f"🚨 Guardrail Alert: \"{rule.name}\"\n"
        f"Symbol: {symbol_str}\n"
        f"{condition_desc}\n"
        f"Current P&L: {current_val}\n"
        f"Time: {now_ist.strftime('%H:%M IST')}\n\n"
        f"→ Check your positions now"
    )

    # Fetch account details for WhatsApp number
    acc_result = await db.execute(
        select(BrokerAccount).where(BrokerAccount.id == account_id)
    )
    account = acc_result.scalar_one_or_none()

    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.broker_account_id == account_id)
    )
    profile = profile_result.scalar_one_or_none()

    # Send WhatsApp
    if rule.notify_whatsapp and profile and profile.whatsapp_number:
        try:
            wa = WhatsAppService()
            await wa.send_message(profile.whatsapp_number, message)
        except Exception as e:
            logger.error(f"WhatsApp failed for guardrail {rule.id}: {e}")

    # Send push notification
    if rule.notify_push:
        try:
            push = PushNotificationService()
            await push.send_notification(
                broker_account_id=account_id,
                title=f"🚨 {rule.name}",
                body=condition_desc,
                db=db,
                severity="danger",
                tag=f"guardrail-{rule.id}",
            )
        except Exception as e:
            logger.error(f"Push failed for guardrail {rule.id}: {e}")

    logger.info(f"Guardrail {rule.id} ({rule.name}) triggered for {account_id}")
