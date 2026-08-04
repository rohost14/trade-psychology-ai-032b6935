"""
ARCHIVED 2026-08-04 — two verified-dead implementations, removed from live modules.

Not importable, not wired to anything. Kept verbatim so the history is readable
without a git archaeology session. Do NOT restore either of these without reading
why they died first.

────────────────────────────────────────────────────────────────────────────────
1. PnLCalculator.calculate_trade_pnl_realtime   (was pnl_calculator.py:773-863)
────────────────────────────────────────────────────────────────────────────────
The per-webhook P&L path. Replaced by PositionLedger at the Phase 3 cutover; the
code was never removed, so the file carried two FIFO matchers for a year — one
live batch matcher and this orphan. Zero callers; two live comments already said
it had been replaced (position_ledger_service.py:20, trade_tasks.py:423).

Three reasons it should not come back:
  - it replays EVERY prior trade for the symbol on every single fill, which is
    the exact design PositionLedger's append-only ledger exists to replace;
  - it still charges P&L against the oldest open lot (strict FIFO). That
    convention was retired on 2026-08-04 (S1) in favour of the weighted average,
    because Kite's positions payload carries only aggregates and no fill
    sequence, so the `realised` a trader sees there cannot be FIFO;
  - it never created CompletedTrades, so nothing downstream depended on it.

Its removal also cleared a long-standing pyflakes warning (`opposite_side`
assigned and never used) — dead code inside dead code.

────────────────────────────────────────────────────────────────────────────────
2. ZerodhaClient.validate_postback_checksum     (was zerodha_service.py:593-615)
────────────────────────────────────────────────────────────────────────────────
A third implementation of postback checksum verification. The live webhook
endpoint has its own two and uses those exclusively:
    api/webhooks.py:27  verify_zerodha_checksum         (form-body checksum)
    api/webhooks.py:50  verify_zerodha_checksum_header  (X-Kite-Checksum header)
Zero callers. Security-relevant duplication is worth removing on its own merits:
three copies of one verification rule is three places to get it wrong, and only
the two in webhooks.py were ever exercised or tested.
"""

# ══════════════════════════════════════════════════════════════════════════════
# 1. pnl_calculator.PnLCalculator.calculate_trade_pnl_realtime
# ══════════════════════════════════════════════════════════════════════════════
#
#     async def calculate_trade_pnl_realtime(
#         self,
#         trade: Trade,
#         db: AsyncSession
#     ) -> Optional[Decimal]:
#         """
#         Calculate P&L for a single trade in real-time (webhook flow).
#         Replays prior trades to build opening queue, then matches.
#
#         Does NOT create CompletedTrades — that happens in batch FIFO.
#         """
#         trade_qty = trade.filled_quantity or trade.quantity or 0
#         trade_price = float(trade.average_price or trade.price or 0)
#         lot_multiplier = Decimal(str(get_lot_multiplier(
#             trade.exchange or "", trade.tradingsymbol or ""
#         )))
#
#         if trade.transaction_type == "SELL":
#             opposite_side = "BUY"
#         else:
#             opposite_side = "SELL"
#
#         # Find all completed trades for this symbol before this trade
#         result = await db.execute(
#             select(Trade).where(
#                 and_(
#                     Trade.broker_account_id == trade.broker_account_id,
#                     Trade.tradingsymbol == trade.tradingsymbol,
#                     Trade.exchange == trade.exchange,
#                     Trade.status == "COMPLETE",
#                     Trade.order_timestamp < trade.order_timestamp
#                 )
#             ).order_by(Trade.order_timestamp.asc())
#         )
#         prior_trades = result.scalars().all()
#
#         if not prior_trades:
#             return None  # First trade for this symbol, must be opening
#
#         # Replay prior trades to find the current open position
#         opening_queue: List[Dict] = []
#         for pt in prior_trades:
#             pt_qty = pt.filled_quantity or pt.quantity or 0
#             pt_price = float(pt.average_price or pt.price or 0)
#             pt_side = pt.transaction_type
#
#             if pt_qty <= 0:
#                 continue
#
#             if not opening_queue or pt_side == opening_queue[0]["side"]:
#                 opening_queue.append({
#                     "remaining_qty": pt_qty, "price": pt_price, "side": pt_side
#                 })
#             else:
#                 remaining = pt_qty
#                 while remaining > 0 and opening_queue:
#                     match_qty = min(opening_queue[0]["remaining_qty"], remaining)
#                     opening_queue[0]["remaining_qty"] -= match_qty
#                     remaining -= match_qty
#                     if opening_queue[0]["remaining_qty"] <= 0:
#                         opening_queue.pop(0)
#                 if remaining > 0:
#                     opening_queue.append({
#                         "remaining_qty": remaining, "price": pt_price, "side": pt_side
#                     })
#
#         # Check if the current trade is closing (opposite to queue head)
#         if not opening_queue or trade.transaction_type == opening_queue[0]["side"]:
#             return None  # Opening trade, no P&L
#
#         # Closing trade — match against the opening queue
#         total_pnl = Decimal("0")
#         remaining_close_qty = trade_qty
#
#         while remaining_close_qty > 0 and opening_queue:
#             opening = opening_queue[0]
#             match_qty = min(opening["remaining_qty"], remaining_close_qty)
#
#             if opening["side"] == "BUY":
#                 match_pnl = Decimal(str((trade_price - opening["price"]) * match_qty)) * lot_multiplier
#             else:
#                 match_pnl = Decimal(str((opening["price"] - trade_price) * match_qty)) * lot_multiplier
#
#             total_pnl += match_pnl
#             opening["remaining_qty"] -= match_qty
#             remaining_close_qty -= match_qty
#
#             if opening["remaining_qty"] <= 0:
#                 opening_queue.pop(0)
#
#         return total_pnl if (trade_qty - remaining_close_qty) > 0 else None


# ══════════════════════════════════════════════════════════════════════════════
# 2. zerodha_service.ZerodhaClient.validate_postback_checksum
# ══════════════════════════════════════════════════════════════════════════════
#
#     def validate_postback_checksum(self, payload: Dict, checksum: str) -> bool:
#         """
#         Validate Kite postback checksum for webhook security.
#
#         Kite sends: SHA-256(order_id + order_timestamp + api_secret)
#         """
#         order_id = payload.get("order_id", "")
#         timestamp = payload.get("order_timestamp", "")
#
#         expected = hashlib.sha256(
#             f"{order_id}{timestamp}{self.api_secret}".encode()
#         ).hexdigest()
#
#         return expected == checksum
#
# Note the `==` on the last line: a plain string compare, where both live
# verifiers in webhooks.py use hmac.compare_digest. One more reason this copy
# should not be revived — it was the weakest of the three.
