"""
Trading Defaults Module — 3-Tier Threshold System

Tier 1: User-declared values in UserProfile (highest priority)
Tier 2: Universal cold-start defaults (behavior-derived baselines replace style labels)
Tier 3: Universal floors (never fire alerts below these)

Note on Tier 2: Style labels (scalper/intraday/swing) were removed because the same
trader scalps on expiry day and holds overnight on slow days — labeling is inaccurate.
Tier 2 will eventually be replaced by a behavioral baseline service that derives
thresholds from the user's own 30-session history. Until then, universal defaults apply.

Usage:
    from app.core.trading_defaults import get_thresholds
    thresholds = get_thresholds(profile)
    window = thresholds['revenge_window_min']
"""

from typing import Optional, Dict, Any


# ---------------------------------------------------------------------------
# Tier 2: Universal cold-start defaults
# Applies to all traders until user-declared values (Tier 1) override them.
# Values chosen for typical F&O intraday/expiry traders on NSE.
# ---------------------------------------------------------------------------
COLD_START_DEFAULTS: Dict[str, Any] = {
    'daily_trade_limit': 10,
    'burst_trades_per_15min': 6,
    'revenge_window_min': 10,
    'consecutive_loss_caution': 3,
    'consecutive_loss_danger': 5,
}

# ---------------------------------------------------------------------------
# Tier 3: Universal floors
# Never fire alerts below these, regardless of user settings.
# Prevents absurd configs like revenge_window_min=0.
# ---------------------------------------------------------------------------
UNIVERSAL_FLOORS: Dict[str, Any] = {
    'burst_trades_per_15min': 3,    # Never alert for fewer than 3 trades in 15 min
    'revenge_window_min': 1,        # Minimum 1 min window (can't be 0)
    'consecutive_loss_caution': 2,  # At least 2 losses before any alert
}


def get_thresholds(profile=None) -> Dict[str, Any]:
    """
    Build merged threshold dict: user-declared > cold-start defaults > universal floor.

    Args:
        profile: UserProfile model instance (can be None for cold start)

    Returns:
        Dict with all threshold keys merged according to tier hierarchy.
    """
    result = dict(COLD_START_DEFAULTS)  # Start with Tier 2 cold-start defaults

    if profile:
        # Tier 2 override: behavior-derived baselines (computed from actual 30-session history).
        # Only applied when MIN_SESSIONS data is available (behavioral_baseline_service.py).
        # Baselines replace cold-start defaults where available; user-declared values (Tier 1) win.
        baseline = (getattr(profile, 'detected_patterns', None) or {}).get('baseline')
        if baseline and isinstance(baseline, dict):
            for key in (
                'daily_trade_limit', 'burst_trades_per_15min',
                'revenge_window_min', 'consecutive_loss_caution', 'consecutive_loss_danger',
            ):
                if key in baseline and baseline[key] is not None:
                    result[key] = baseline[key]

        # Tier 1 overrides: user-declared values win over everything
        if getattr(profile, 'daily_trade_limit', None):
            result['daily_trade_limit'] = profile.daily_trade_limit
        if getattr(profile, 'cooldown_after_loss', None):
            result['revenge_window_min'] = profile.cooldown_after_loss

        # Capital-derived thresholds (always from profile, no style default)
        result['trading_capital'] = getattr(profile, 'trading_capital', None)
        result['daily_loss_limit'] = getattr(profile, 'daily_loss_limit', None)
        result['max_position_size'] = getattr(profile, 'max_position_size', None)
        result['sl_percent_futures'] = getattr(profile, 'sl_percent_futures', None) or 1.0
        result['sl_percent_options'] = getattr(profile, 'sl_percent_options', None) or 50.0
        result['risk_tolerance'] = getattr(profile, 'risk_tolerance', None) or 'moderate'
    else:
        # Cold start defaults for capital fields
        result['trading_capital'] = None
        result['daily_loss_limit'] = None
        result['max_position_size'] = None
        result['sl_percent_futures'] = 1.0
        result['sl_percent_options'] = 50.0
        result['risk_tolerance'] = 'moderate'

    # Apply Tier 3 universal floors — never go below these
    for key, floor in UNIVERSAL_FLOORS.items():
        if result.get(key, 0) < floor:
            result[key] = floor

    return result


# ---------------------------------------------------------------------------
# Capital-at-risk estimation (instrument-aware)
# ---------------------------------------------------------------------------

def estimate_capital_at_risk(
    instrument_type: Optional[str],
    tradingsymbol: str,
    direction: str,
    avg_entry_price: float,
    total_quantity: int,
) -> float:
    """
    Returns estimated Rs capital at risk for a completed trade.

    For options buyers (LONG CE/PE): exact — premium paid IS the capital at risk.
    For futures/options sellers: SPAN-approximated (conservative).
    Hedged positions will appear over-estimated — acceptable for safety alerts.
    """
    notional = float(avg_entry_price or 0) * int(total_quantity or 0)

    if instrument_type in ('CE', 'PE'):
        if direction == 'LONG':
            return notional  # Premium paid = exact capital at risk
        else:
            # Short options: SPAN margin ~ same as futures on that underlying
            return _futures_span_margin(tradingsymbol, notional)

    elif instrument_type == 'FUT':
        return _futures_span_margin(tradingsymbol, notional)

    # EQ delivery or unknown — use notional (conservative)
    return notional


def _futures_span_margin(tradingsymbol: str, notional: float) -> float:
    """
    NSE-approximate SPAN margin percentages by underlying.

    These approximate the SPAN margin percentages used by NSE.
    We don't call NSE's SPAN files to avoid complexity.
    Hedged positions (spreads) will over-estimate — acceptable.

    Kite symbol formats: NIFTY25JANFUT, BANKNIFTY25JANFUT, FINNIFTY25JANFUT, etc.
    """
    sym = (tradingsymbol or '').upper()

    # Bank index: must check before NIFTY (BANKNIFTY starts with BANK, not just NIFTY)
    if sym.startswith('BANKNIFTY') or 'BANKEX' in sym:
        return notional * 0.15   # ~15% SPAN (higher volatility)

    # Broad index futures: NIFTY (not BANKNIFTY), FINNIFTY, MIDCPNIFTY, SENSEX
    if (
        (sym.startswith('NIFTY') and not sym.startswith('BANKNIFTY'))
        or sym.startswith('FINNIFTY')
        or sym.startswith('MIDCPNIFTY')
        or 'SENSEX' in sym
    ):
        return notional * 0.12   # ~12% SPAN for broad index futures

    # Stock futures: conservative 20% (varies widely, 15-25%)
    return notional * 0.20
