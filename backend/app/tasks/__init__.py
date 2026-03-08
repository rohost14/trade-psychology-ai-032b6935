"""
Celery Tasks Package

Contains async tasks for:
- Trade processing (trade_tasks)
- Alert notifications (alert_tasks)
- Scheduled reports (report_tasks)
"""

from app.tasks.trade_tasks import (
    process_webhook_trade,
    sync_trades_for_account,
    run_risk_detection,
    send_danger_alert,
)

from app.tasks.alert_tasks import (
    send_whatsapp_alert,
    send_risk_alert_notification,
    send_bulk_alerts,
)

from app.tasks.report_tasks import (
    generate_eod_reports,
    generate_commodity_eod,
    send_morning_prep,
    send_weekly_summary,
)

__all__ = [
    # Trade tasks
    "process_webhook_trade",
    "sync_trades_for_account",
    "run_risk_detection",
    "send_danger_alert",
    # Alert tasks
    "send_whatsapp_alert",
    "send_risk_alert_notification",
    "send_bulk_alerts",
    # Report tasks
    "generate_eod_reports",
    "generate_commodity_eod",
    "send_morning_prep",
    "send_weekly_summary",
]
