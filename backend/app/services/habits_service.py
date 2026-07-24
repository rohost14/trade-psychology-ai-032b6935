"""Habits — zero-input behavioural insights derived purely from completed trades.

No user input, no engine, no probabilistic attribution — just factual aggregates over
the trader's own realized rounds (CompletedTrade), sliced by hour, day-of-week, instrument,
and after-loss sizing. Powers the Analytics → Habits tab and the post-import recap.

Rules honoured: raw realized P&L only; IST time buckets; min-sample gating so a thin
history never shows a misleading number.
"""
import re
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")

MIN_SAMPLE = 5      # overall completed trades before we show anything
MIN_BUCKET = 3      # per-bucket floor before a bucket is eligible as best/worst

_DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _underlying(symbol: str) -> str:
    """Group key for an instrument: leading letters before the first digit.
    NIFTY24JAN18000CE -> NIFTY · BANKNIFTY24JANFUT -> BANKNIFTY · RELIANCE -> RELIANCE."""
    if not symbol:
        return "?"
    m = re.match(r"^([A-Z&]+)", symbol.upper())
    return m.group(1) if m else symbol.upper()


def _hour_label(h: int) -> str:
    ampm = "am" if h < 12 else "pm"
    hr = h % 12 or 12
    return f"{hr}{ampm}"


def _win_rate(wins: int, n: int) -> float:
    return round(wins / n * 100, 1) if n else 0.0


def build_habits(trades, days: int) -> dict:
    """`trades` = list[CompletedTrade] for one account, any order. Returns the habits payload."""
    n = len(trades)
    if n < MIN_SAMPLE:
        return {"has_data": False, "period_days": days, "sample": n, "min_sample": MIN_SAMPLE}

    by_hour: dict = {}
    by_dow: dict = {}
    by_inst: dict = {}

    def _bucket(d, key):
        b = d.setdefault(key, {"trades": 0, "net_pnl": 0.0, "wins": 0})
        return b

    entries_sorted = sorted(trades, key=lambda t: (t.exit_time or t.entry_time))
    all_notional, after_loss_notional = [], []
    prev_loss = False
    first_dt, last_dt = None, None
    gross = 0.0
    total_wins = 0

    for t in entries_sorted:
        pnl = float(t.realized_pnl or 0)
        gross += pnl
        win = pnl > 0
        if win:
            total_wins += 1
        entry = t.entry_time or t.exit_time
        exit_ = t.exit_time or t.entry_time
        if entry:
            first_dt = entry if first_dt is None or entry < first_dt else first_dt
        if exit_:
            last_dt = exit_ if last_dt is None or exit_ > last_dt else last_dt

        ist = (entry or exit_).astimezone(_IST) if (entry or exit_) else None
        if ist is not None:
            hb = _bucket(by_hour, ist.hour)
            hb["trades"] += 1; hb["net_pnl"] += pnl; hb["wins"] += int(win)
            db = _bucket(by_dow, ist.weekday())
            db["trades"] += 1; db["net_pnl"] += pnl; db["wins"] += int(win)

        ib = _bucket(by_inst, _underlying(t.tradingsymbol))
        ib["trades"] += 1; ib["net_pnl"] += pnl; ib["wins"] += int(win)

        notional = float(t.total_quantity or 0) * float(t.avg_entry_price or 0)
        if notional > 0:
            all_notional.append(notional)
            if prev_loss:
                after_loss_notional.append(notional)
        prev_loss = pnl < 0

    def _rows(d, label_fn):
        out = []
        for k, b in d.items():
            out.append({
                "key": k, "label": label_fn(k),
                "trades": b["trades"],
                "net_pnl": round(b["net_pnl"], 2),
                "win_rate": _win_rate(b["wins"], b["trades"]),
            })
        return out

    hour_rows = sorted(_rows(by_hour, _hour_label), key=lambda r: r["key"])
    dow_rows  = sorted(_rows(by_dow, lambda k: _DOW[k]), key=lambda r: r["key"])
    inst_rows = sorted(_rows(by_inst, lambda k: k), key=lambda r: r["net_pnl"])

    # best/worst among sufficiently-sampled buckets
    def _extreme(rows, most=False):
        eligible = [r for r in rows if r["trades"] >= MIN_BUCKET]
        if not eligible:
            return None
        return (max if most else min)(eligible, key=lambda r: r["net_pnl"])

    worst_hour = _extreme(hour_rows)
    best_hour  = _extreme(hour_rows, most=True)
    worst_inst = _extreme(inst_rows)
    best_inst  = _extreme(inst_rows, most=True)

    # after-loss size drift
    overall_avg = sum(all_notional) / len(all_notional) if all_notional else 0.0
    after_avg = sum(after_loss_notional) / len(after_loss_notional) if after_loss_notional else 0.0
    drift_ratio = round(after_avg / overall_avg, 2) if (overall_avg > 0 and after_loss_notional) else None

    return {
        "has_data": True,
        "period_days": days,
        "sample": n,
        "by_hour": hour_rows,
        "by_day_of_week": dow_rows,
        "by_instrument": inst_rows,
        "after_loss_size": {
            "overall_avg_notional": round(overall_avg, 2),
            "after_loss_avg_notional": round(after_avg, 2),
            "ratio": drift_ratio,               # e.g. 2.3 → 2.3× bigger after a loss
            "after_loss_count": len(after_loss_notional),
            "min_bucket": MIN_BUCKET,
        },
        "summary": {
            "total_trades": n,
            "gross_pnl": round(gross, 2),
            "win_rate": _win_rate(total_wins, n),
            "date_from": first_dt.isoformat() if first_dt else None,
            "date_to": last_dt.isoformat() if last_dt else None,
            "worst_hour": worst_hour["label"] if worst_hour else None,
            "best_hour": best_hour["label"] if best_hour else None,
            "worst_instrument": worst_inst["label"] if worst_inst else None,
            "best_instrument": best_inst["label"] if best_inst else None,
        },
        # exact expiry-day P&L needs an expiry calendar; day-of-week surfaces the
        # Thursday weekly-expiry effect factually in the meantime.
        "note": "Day-of-week captures weekly-expiry (Thursday) effects; exact expiry-day is a later addition.",
    }
