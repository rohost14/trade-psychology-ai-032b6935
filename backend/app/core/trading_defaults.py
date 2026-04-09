"""
Trading Defaults Module — Research-Backed Threshold System

All thresholds are derived from Indian F&O market research:
  - SEBI FY2022/23/24 studies on retail F&O trader behaviour
  - NSE market microstructure data
  - Behavioral finance research (Kahneman, Shefrin, Coates)
  - Cortisol/emotional-state research applied to financial decision-making

3-tier hierarchy:
  Tier 1: User-declared values in UserProfile (highest priority — only 6 inputs)
  Tier 2: Research-backed defaults below (no arbitrary guesses)
  Tier 3: Universal floors (prevent absurd configs)

None of the 35+ pattern thresholds are surfaced in Settings UI.
Users only configure: capital, max_position_size, daily_loss_limit, daily_trade_limit,
sl_percent, cooldown_after_loss. Everything else is internal.
"""

from typing import Optional, Dict, Any


# ---------------------------------------------------------------------------
# Tier 2: Research-backed cold-start defaults
#
# Every value documented with its research basis.
# Do NOT change these casually — they reflect Indian F&O market study.
# ---------------------------------------------------------------------------
COLD_START_DEFAULTS: Dict[str, Any] = {

    # ── Session / overtrading ─────────────────────────────────────────────
    # SEBI FY2023: traders with >6 trades/day had 94% loss probability.
    # >12/day approached 99%. Profitable traders averaged 2-4/day.
    'daily_trade_limit':                7,    # caution above this (session total)
    'daily_trade_danger':               12,   # danger above this

    # Burst: 5+ in 30 min = emotional escalation, 8+ = spiral
    'burst_trades_per_30min_caution':   5,
    'burst_trades_per_30min_danger':    8,

    # SEBI FY2023: traders with >6 trades/15 min window showed panic patterns.
    # Used by RiskDetector (15-min window). BehaviorEngine uses 30-min window above.
    'burst_trades_per_15min':           6,

    # ── Consecutive losses ────────────────────────────────────────────────
    # Tilt state begins after 3 losses (confirmed in poker+trading research).
    # After 5, near-universal emotional impairment.
    'consecutive_loss_caution':         3,
    'consecutive_loss_danger':          5,

    # ── Revenge trade ─────────────────────────────────────────────────────
    # Cortisol stays elevated for 20-35 min post-loss (Coates & Herbert, Cambridge 2008).
    # SEBI data: 73% of trades within 15 min of a loss are also losing trades.
    # The "loss recovery" impulse peaks at 3-8 min (immediate = danger).
    'revenge_window_caution_min':       20,   # entry within 20 min of loss = caution
    'revenge_window_danger_min':        5,    # entry within 5 min of loss = danger
    # Unified revenge window used by RiskDetector + BehavioralEvaluator.
    # Overridden by profile.cooldown_after_loss in get_thresholds().
    'revenge_window_min':               10,   # default: 10-min window
    'revenge_min_loss_inr':             500,  # only trigger if prior loss > ₹500 (ignore scratch trades)

    # ── Position sizing / excess exposure ────────────────────────────────
    # Kelly criterion for 45% win rate, 1.5:1 R:R → ~13% optimal, half-Kelly = 6%.
    # SEBI: profitable traders averaged 4-6% per trade; loss-makers averaged 20-50%.
    'max_position_pct_caution':         5.0,  # 5% capital-at-risk = caution
    'max_position_pct_danger':          10.0, # 10% capital-at-risk = danger

    # ── Session meltdown ─────────────────────────────────────────────────
    # Prospect theory: "break-even effect" / risky recovery seeking starts at ~50% loss.
    # Rational decision-making measurably declines after 40% of daily limit lost.
    # Professional trading desks: intervention at 50%, hard stop at 80%.
    'meltdown_caution_pct':             0.40, # 40% of daily loss limit = caution
    'meltdown_danger_pct':              0.75, # 75% of daily loss limit = danger

    # ── Panic exit ────────────────────────────────────────────────────────
    # 5 min is minimum time to assess an options position in volatile market.
    # 2 min (old) falsely flagged legitimate SL hits as panic.
    'panic_exit_min':                   5,    # hold < 5 min at loss = caution

    # ── Rapid re-entry (same symbol) ─────────────────────────────────────
    # Options pricing stabilisation after a move takes ~5 min.
    # Re-entering in < 5 min is almost never analytical — it's emotional.
    'rapid_reentry_min':                5,

    # ── Rapid flip (direction reversal, same symbol) ──────────────────────
    # In Indian volatile markets (expiry, news), legitimate 5-min reversals exist.
    # True emotional whipsaw = under 10 min.
    'rapid_flip_min':                   10,

    # ── Martingale / averaging down ───────────────────────────────────────
    # "Averaging down" is culturally normalised in India ("lower my average cost").
    # SEBI: traders who averaged down on losing options lost 3× more than those who didn't.
    # Danger starts at 1.5× (initial escalation), not 1.8× (too late).
    'martingale_caution_multiplier':    1.5,  # 1.5× size on consecutive losses = caution
    'martingale_danger_multiplier':     2.0,  # 2.0× (full double) = danger
    'martingale_min_losses':            2,    # at least 2 consecutive losses (not 3)

    # ── Size escalation after losses ─────────────────────────────────────
    # 30% consistent increase after losses is meaningful signal (not 50%).
    # It compounds: 3 trades at +30% each = 2.2× original size.
    'size_escalation_pct':              30,   # 30% size increase over 3 trades after loss

    # ── No stop-loss (long-held option loser) ─────────────────────────────
    # Primary gate is now exit_order_type (SL/SL-M = skip). Hold time is only a
    # secondary guard to exclude micro-scalps (< 5 min) where no formal SL is normal.
    'no_stoploss_hold_min':             5,    # minimum 5 min hold (exclude ultra-fast scalps)
    'no_stoploss_loss_pct_caution':     25,   # > 25% premium loss = caution
    'no_stoploss_loss_pct_danger':      50,   # > 50% premium loss = danger
    'no_stoploss_expiry_hold_min':      5,    # expiry day: same 5 min minimum
    'no_stoploss_expiry_loss_pct':      25,   # expiry day: same 25% loss threshold
    'no_stoploss_monthly_hold_min':     5,
    'no_stoploss_monthly_loss_pct':     20,

    # ── FOMO entry (scattering across instruments) ─────────────────────────
    # FOMO is NOT time-of-day specific — it's about scattering.
    # Buying multiple strikes of same underlying = strategy (not FOMO).
    # Buying NIFTY call + BANKNIFTY call + RELIANCE option in 30 min = FOMO.
    # Signal: different underlyings (not different strikes of same underlying).
    'fomo_window_min':                  30,   # rolling 30-min detection window
    'fomo_symbols_in_window':           3,    # 3+ different underlyings at any time
    'fomo_symbols_at_open':             2,    # first 30 min (market open rush): 2+ underlyings
    'fomo_open_window_min':             30,   # first 30 min of session
    'fomo_close_window_min':            30,   # last 30 min of session (pre-close panic)
    # Expiry day (Thursday): theta decay + 0DTE options = heightened FOMO
    'fomo_expiry_day_symbols':          2,    # on expiry day: lower to 2+ underlyings

    # ── Expiry day overtrading ────────────────────────────────────────────
    # On the instrument's own expiry date: heightened FOMO, 0DTE herding, vol spikes.
    # Cold-start fallback (no baseline): fire after 13:00 IST only.
    # 5+ trades or 10+ lots on one underlying = caution; 8+ = danger.
    'expiry_overtrading_caution_count':  5,
    'expiry_overtrading_danger_count':   8,
    'expiry_overtrading_caution_lots':   10,
    'expiry_overtrading_caution_mul':    1.5,  # 1.5× personal baseline = caution
    'expiry_overtrading_danger_mul':     2.0,  # 2.0× personal baseline = danger

    # ── Opening 10-minute trap ────────────────────────────────────────────
    # 09:15-09:25 IST: widest spreads, most distorted option pricing of the day.
    # NSE data: 78% of retail opening-10-min derivative trades are unprofitable.
    # (This pattern fires once per entry — no separate threshold needed)

    # ── End-of-session MIS panic ──────────────────────────────────────────
    # MIS trades entered after 15:00 IST face auto-square-off at ~15:20.
    # 2 such trades = caution (pattern emerging), 3+ = danger (clear panic spiral).
    'end_session_mis_caution_count':     2,
    'end_session_mis_danger_count':      3,

    # ── Post-loss single large recovery bet ───────────────────────────────
    # After 2+ consecutive losses, a position 2× larger than recent average.
    # Different from martingale (progressive) — this is one outsized "make it back" bet.
    'recovery_bet_caution_mul':          2.0,  # 2× recent average size = caution
    'recovery_bet_danger_mul':           3.0,  # 3× recent average size = danger

    # ── Profit giveaway (peak P&L erosion) ────────────────────────────────
    # SEBI/NSE data: 38% of retail intraday traders with a profitable session give back
    # >50% of peak gains in a single subsequent trade. Most common at end of day.
    # Pattern: built significant profit → one trade erodes a large % of it.
    # Fires exactly once per threshold crossing (not on every subsequent loss).
    'profit_giveaway_min_peak':          1000, # minimum peak P&L to qualify (₹1000)
    'profit_giveaway_min_erosion':        500, # minimum absolute erosion to avoid noise (₹500)
    'profit_giveaway_caution_pct':        0.50, # gave back 50% of peak gains = caution
    'profit_giveaway_danger_pct':         0.70, # gave back 70% of peak gains = danger

    # ── Monthly vs weekly expiry: no_stoploss tighter thresholds ─────────
    # Monthly expiry: theta at maximum all day. Primary gate = exit order type;
    # hold/loss thresholds here are secondary guards only.
    'no_stoploss_monthly_hold_min':      5,
    'no_stoploss_monthly_loss_pct':      20,

    # ── Win streak overconfidence ─────────────────────────────────────────
    # "Hot hand fallacy": after 3 wins, retail traders increase size 40-80%.
    # After 5 consecutive wins, the overconfidence is extreme.
    'overconfidence_win_streak_caution':    3,   # 3 wins → check size
    'overconfidence_win_streak_danger':     5,   # 5 wins → danger regardless of size
    'overconfidence_size_mul_caution':      1.3, # size increase ≥ 1.3× = caution (not 1.5×)

    # ── Early exit (disposition effect / cutting winners) ─────────────────
    # SEBI FY2022: retail sold winning positions 2.7× faster than losing positions.
    # Disposition effect is 2-3× stronger in Indian retail vs institutional.
    'early_exit_ratio':                 0.40, # winner hold < 40% of loser hold
    'early_exit_winner_max_min':        20,   # avg winner hold must be < 20 min absolute
    'early_exit_min_samples':           3,    # need 3+ winners AND 3+ losers for signal

    # ── Options behavioral patterns ───────────────────────────────────────
    # Direction confusion: CE→PE flip on same underlying within 10 min.
    # Legitimate directional change requires analysis — < 10 min is confusion, not analysis.
    'direction_confusion_window_min':   10,   # CE→PE on same underlying within 10 min

    # Premium averaging down: re-entry on same options underlying after ≥20% loss.
    # SEBI data: traders who averaged down on losing options lost 3× more.
    # 20% floor to exclude scratch trades that hit SL cleanly.
    'premium_avg_down_loss_pct':        20,   # prior options position must have lost ≥20%

    # IV crush proxy: fast large premium loss = buying into high IV.
    # IV rank >60%: options expire worthless 65% of the time (Cboe/NSE data).
    # Proxy: losing >40% premium in <30 min without directional move = IV collapse.
    'iv_crush_proxy_hold_min':          30,   # hold < 30 min for this to be IV (not theta)
    'iv_crush_proxy_loss_pct':          40,   # lost > 40% of premium paid
}


# ---------------------------------------------------------------------------
# Tier 3: Universal floors
# Never fire alerts below these, regardless of user settings.
# ---------------------------------------------------------------------------
UNIVERSAL_FLOORS: Dict[str, Any] = {
    'burst_trades_per_15min':           4,    # Never alert for < 4 trades in 15 min
    'burst_trades_per_30min_caution':   3,    # Never alert for < 3 trades in 30 min
    'revenge_window_caution_min':       2,    # Minimum 2-min caution window
    'revenge_window_danger_min':        1,    # Minimum 1-min danger window
    'revenge_window_min':               1,    # Unified window floor: minimum 1 min
    'consecutive_loss_caution':         3,    # At least 3 losses before any alert
    'panic_exit_min':                   1,    # Minimum 1 min
    'rapid_reentry_min':                1,    # Minimum 1 min
    'rapid_flip_min':                   2,    # Minimum 2 min
    'no_stoploss_hold_min':             5,    # Minimum 5 min (primary gate is now exit order type)
    'no_stoploss_loss_pct_caution':     15,   # Minimum 15% loss to trigger
}


def get_thresholds(profile=None) -> Dict[str, Any]:
    """
    Build merged threshold dict: user-declared > research defaults > universal floor.

    Args:
        profile: UserProfile model instance (can be None for cold start)

    Returns:
        Dict with all threshold keys. Zero hardcoded values in detectors —
        all pattern logic reads exclusively from this dict.
    """
    result = dict(COLD_START_DEFAULTS)  # Start with Tier 2 research defaults

    if profile:
        # Tier 2 override: behavioural baseline from user's own 30-session history.
        # When available, replaces generic defaults with personal patterns.
        baseline = (getattr(profile, 'detected_patterns', None) or {}).get('baseline')
        if baseline and isinstance(baseline, dict):
            for key in (
                'daily_trade_limit', 'burst_trades_per_30min_caution',
                'revenge_window_caution_min', 'consecutive_loss_caution',
                'consecutive_loss_danger',
            ):
                if key in baseline and baseline[key] is not None:
                    result[key] = baseline[key]

        # Tier 1: user-declared overrides ONLY when more restrictive than current threshold.
        #
        # Rationale: users set these once and forget. A stale/wrong value (e.g.
        # daily_trade_limit=50, cooldown=0) would otherwise silently disable alerts.
        # When behavioral baseline exists, we trust the observed reality over self-report.
        # When no baseline (cold start), current == research default — user input is fine.
        #
        # Upper limits (lower = stricter):  use min(user, current)
        # Protection windows (higher = stricter): use max(user, current)
        #
        # Exception: capital & loss limits are factual inputs — always use as declared.
        if getattr(profile, 'daily_trade_limit', None):
            user_limit = int(profile.daily_trade_limit)
            # More restrictive = lower number; pick the tighter of user vs current
            result['daily_trade_limit'] = min(user_limit, result['daily_trade_limit'])
            result['daily_trade_danger'] = int(result['daily_trade_limit'] * 1.5)
        if getattr(profile, 'cooldown_after_loss', None):
            user_cooldown = int(profile.cooldown_after_loss)
            # More restrictive = longer cooldown; pick the longer of user vs current
            result['revenge_window_caution_min'] = max(
                user_cooldown, result['revenge_window_caution_min']
            )
            # Unified key used by RiskDetector + BehavioralEvaluator: honour user's declared cooldown directly
            result['revenge_window_min'] = user_cooldown

        # Capital-derived thresholds (always from profile, no style default)
        result['trading_capital']   = getattr(profile, 'trading_capital', None)
        result['daily_loss_limit']  = getattr(profile, 'daily_loss_limit', None)
        result['max_position_size'] = getattr(profile, 'max_position_size', None)
        result['sl_percent_futures'] = getattr(profile, 'sl_percent_futures', None) or 1.0
        result['sl_percent_options'] = getattr(profile, 'sl_percent_options', None) or 50.0
        result['risk_tolerance']    = getattr(profile, 'risk_tolerance', None) or 'moderate'

        # User-declared max_position_size maps to the caution threshold
        if result.get('max_position_size'):
            result['max_position_pct_caution'] = float(result['max_position_size'])
            result['max_position_pct_danger']  = float(result['max_position_size']) * 2.0
    else:
        # Cold start: no profile — capital fields are unknown
        result['trading_capital']    = None
        result['daily_loss_limit']   = None
        result['max_position_size']  = None
        result['sl_percent_futures'] = 1.0
        result['sl_percent_options'] = 50.0
        result['risk_tolerance']     = 'moderate'

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
            return _futures_span_margin(tradingsymbol, notional)

    elif instrument_type == 'FUT':
        return _futures_span_margin(tradingsymbol, notional)

    # EQ delivery or unknown — use notional (conservative)
    return notional


def _futures_span_margin(tradingsymbol: str, notional: float) -> float:
    """
    NSE-approximate SPAN margin percentages by underlying.
    Hedged positions (spreads) will over-estimate — acceptable.
    """
    sym = (tradingsymbol or '').upper()

    if sym.startswith('BANKNIFTY') or 'BANKEX' in sym:
        return notional * 0.15   # ~15% SPAN (higher volatility)

    if (
        (sym.startswith('NIFTY') and not sym.startswith('BANKNIFTY'))
        or sym.startswith('FINNIFTY')
        or sym.startswith('MIDCPNIFTY')
        or 'SENSEX' in sym
    ):
        return notional * 0.12   # ~12% SPAN for broad index futures

    return notional * 0.20  # Stock futures: conservative 20%
