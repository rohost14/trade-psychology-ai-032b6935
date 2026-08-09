"""
Checks that run against an OPEN position, from streamed prices.

E4. The exit-time engine can only tell a trader that 80% of their premium is
gone once they have closed the position and taken the loss. The same fact is
knowable while the position is live — we already stream a last-traded price for
every open position — and at that point it is still something they can act on.

Two design rules, both about not being wrong:

  * **A missing price is silence, never zero.** `get_cached_ltp` returns None for
    anything older than two seconds. Treating a stale or absent price as a real
    one would fabricate a loss percentage on a real position, which is the worst
    false positive available and the same silent-zero class this codebase has
    produced before.
  * **Thresholds match the exit-time detector exactly**, including the
    expiry-day shift, so the live reading and the post-hoc reading of the same
    position never disagree.

Not here: live `no_stoploss`. It needs to know whether an open position has a
stop-loss order resting against it, and the `orders` table is only populated by
`sync_orders_to_db` on a manual or end-of-day sync — a stop placed thirty
seconds ago is not in it. Shipping it would tell disciplined traders who use
SL-M orders that they have no stop, which is exactly backwards. It needs
real-time order-book visibility we do not have.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

#: Premium destruction is a buyer's problem — the exit-time detector is LONG
#: options only, and this mirrors it.
LIVE_PREMIUM_DIRECTIONS = ("LONG",)


def premium_loss_pct(avg_entry_price: Optional[float], ltp: Optional[float]) -> Optional[float]:
    """
    How much of the premium paid is currently gone, as a positive percentage.

    None when it cannot be computed — no price, no entry price, or a position
    that is up rather than down. None means "say nothing", not "zero".
    """
    if avg_entry_price is None or ltp is None:
        return None
    try:
        entry = float(avg_entry_price)
        last = float(ltp)
    except (TypeError, ValueError):
        return None
    if entry <= 0 or last < 0:
        return None
    loss = (entry - last) / entry * 100
    return loss if loss > 0 else None


def evaluate_live_premium_loss(
    avg_entry_price: Optional[float],
    ltp: Optional[float],
    quantity: int,
    thresholds: Dict[str, Any],
    is_expiry_day: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Should we tell the trader that this open option position is bleeding out?

    Mirrors `_detect_premium_loss_event`: long options only, the same 40/60/80
    bands, the same expiry-day shift. The one thing it does not carry is the
    repeat-escalation rule, which needs completed trades — the exit pass still
    applies that.

    Returns None whenever the answer is not certain, which includes every case
    where the price feed has nothing fresh to say.
    """
    if quantity is None or quantity <= 0:
        return None   # short options: premium received, not destroyed

    loss_pct = premium_loss_pct(avg_entry_price, ltp)
    if loss_pct is None:
        return None

    caution = float(thresholds.get("premium_loss_caution_pct", 40))
    danger = float(thresholds.get("premium_loss_danger_pct", 60))
    critical = float(thresholds.get("premium_loss_critical_pct", 80))

    if is_expiry_day:
        # Options decay hard on expiry day, so the same percentage means less.
        shift = float(thresholds.get("premium_loss_expiry_shift_pct", 15))
        caution += shift
        danger += shift
        critical += shift

    if loss_pct < caution:
        return None

    severity = ("critical" if loss_pct >= critical
                else "danger" if loss_pct >= danger
                else "caution")

    unrealised = (float(avg_entry_price) - float(ltp)) * abs(int(quantity))
    return {
        "severity": severity,
        "loss_pct": round(loss_pct, 1),
        "unrealised_loss": round(unrealised),
        "levels": {"caution": caution, "danger": danger, "critical": critical},
        "expiry_day": is_expiry_day,
    }


def live_premium_message(symbol: str, result: Dict[str, Any]) -> str:
    """
    The observation, with no instruction attached.

    We are describing arithmetic that is already true about a position the
    trader holds — their broker shows them the same number. It would become
    advice the moment we appended "consider exiting", so we do not.
    """
    expiry_note = " (expiry day, so the bar is higher)" if result.get("expiry_day") else ""
    return (
        f"{symbol} is down {result['loss_pct']:.0f}% of the premium you paid — "
        f"₹{abs(result['unrealised_loss']):,.0f} unrealised. This position is OPEN"
        f"{expiry_note}."
    )
