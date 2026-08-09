"""
WhatsApp delivery for risk alerts — trader messages and guardian messages.

This file used to carry its own copy of the alert copy: a per-pattern `if` chain
that wrote a tailored sentence for `overtrading`, `revenge_sizing` and
`consecutive_loss`. Engine v2 renamed those detectors, the comparisons stayed
literal, and every message quietly fell through to the generic branch. Three
hand-written messages that no user ever received.

So there is now exactly one author of alert copy: the engine, which writes an
evidenced sentence into `alert.message` at detection time ("5 positions opened
between 10:02 and 10:18 after a ₹4,200 loss"). This module frames it and sends
it. A rename cannot break framing.

Two audiences, two formatters, and they must never be swapped:

  * The **trader** gets `alert.message` verbatim. It is written for them and is
    second-person in many detectors ("You entered NIFTY after…").
  * The **guardian** must not receive that text — forwarding it tells a third
    party "you are in tilt mode" and hands them the trader's P&L and symbols.
    They get the minimum that makes a check-in possible: who, which pattern,
    how serious, when. No numbers, no instrument, no broker client id.

Voice: mirror, not blocker. We report what happened. We do not instruct anyone to
stop trading, diagnose an emotional state, or claim a pattern causes losses.
"""
from typing import Optional
import logging
from zoneinfo import ZoneInfo

from app.core.severity import is_notifiable, label as severity_label
from app.models.risk_alert import RiskAlert
from app.models.broker_account import BrokerAccount
from app.services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _pattern_label(pattern_type: Optional[str]) -> str:
    """
    'overtrading_burst' -> 'Overtrading burst'.

    Derived, not mapped. A lookup table keyed on pattern names is precisely what
    broke this file before. Phase 2 moves real labels onto DetectorSpec, where
    they live beside the name they describe; until then this cannot go stale.
    """
    if not pattern_type:
        return "Behaviour pattern"
    return pattern_type.replace("_", " ").capitalize()


def _ist_time(alert: RiskAlert) -> str:
    ts = alert.detected_at
    if not ts:
        return ""
    try:
        return ts.astimezone(IST).strftime("%I:%M %p").lstrip("0")
    except Exception:
        return ts.strftime("%I:%M %p").lstrip("0")


def guardian_reachable(user) -> tuple:
    """
    (phone, reason) — the phone to message a guardian on, or why not.

    One gate for every path that contacts an accountability partner. It existed
    in two places and not in the other four: a guardian who replied NO, or who
    never replied at all, still received scheduled reports every day and every
    week. The consent handshake (profile.py guardian/send-consent, migration
    056) promises otherwise, and a promise to a third party is not one to keep
    only on the paths someone remembered.
    """
    if not user:
        return None, "no_user"
    phone = (user.guardian_phone or "").strip() if user.guardian_phone else None
    if not phone:
        return None, "no_guardian_phone"
    if not user.guardian_confirmed:
        return None, "guardian_not_confirmed"
    return phone, None


class AlertService:
    """
    Send WhatsApp alerts for behaviour patterns.
    Delegates transport to the shared whatsapp_service singleton.
    """

    def __init__(self):
        pass

    # ── Trader ────────────────────────────────────────────────────────────────

    async def send_risk_alert(
        self,
        risk_alert: RiskAlert,
        broker_account: BrokerAccount,
        phone_number: str,
    ) -> bool:
        """
        Send the alert to the trader.

        Gated on the shared notifiable set, not a literal. The previous
        `!= "danger"` check silently discarded every `critical` alert — the most
        serious class we raise was the one class guaranteed never to send.
        """
        try:
            if not is_notifiable(risk_alert.severity):
                logger.info(f"Skipping WhatsApp alert (severity={risk_alert.severity})")
                return False

            message = self._format_alert_message(risk_alert, broker_account)
            sent = await whatsapp_service.send_message(phone_number, message)
            if sent:
                logger.info(f"WhatsApp alert sent for alert {risk_alert.id}")
            return sent

        except Exception as e:
            logger.error(f"Failed to send WhatsApp alert: {e}", exc_info=True)
            return False

    def _format_alert_message(
        self,
        alert: RiskAlert,
        broker_account: BrokerAccount,
    ) -> str:
        """
        Frame the engine's sentence for the trader.

        No instruction to stop, no diagnosis, no "this historically leads to
        major losses". The observation is the product.
        """
        body = (alert.message or "").strip() or (
            f"{_pattern_label(alert.pattern_type)} detected on today's trading."
        )
        when = _ist_time(alert)
        lines = [
            f"*TradeMentor* · {severity_label(alert.severity)}",
            "",
            f"*{_pattern_label(alert.pattern_type)}*",
            body,
        ]
        if when:
            lines += ["", f"_{when} IST_"]
        lines += ["", "Open TradeMentor to see the trades behind this."]
        return "\n".join(lines)

    # ── Guardian ──────────────────────────────────────────────────────────────

    async def send_guardian_alert(
        self,
        risk_alert: RiskAlert,
        phone_number: str,
        trader_name: Optional[str] = None,
        guardian_name: Optional[str] = None,
    ) -> bool:
        """
        Send the accountability-partner message.

        Deliberately takes no BrokerAccount: the guardian has no business
        receiving anything derived from the trading account, and not having the
        object is the cheapest way to guarantee nothing leaks from it.

        The caller is responsible for consent (`user.guardian_confirmed`),
        eligibility (`DetectorSpec.guardian_eligible`) and the monthly budget.
        """
        try:
            if not is_notifiable(risk_alert.severity):
                logger.info(f"Skipping guardian alert (severity={risk_alert.severity})")
                return False

            message = self._format_guardian_alert(
                risk_alert, trader_name=trader_name, guardian_name=guardian_name
            )
            sent = await whatsapp_service.send_message(phone_number, message)
            if sent:
                logger.info(f"Guardian alert sent for alert {risk_alert.id}")
            return sent

        except Exception as e:
            logger.error(f"Failed to send guardian alert: {e}", exc_info=True)
            return False

    def _format_guardian_alert(
        self,
        alert: RiskAlert,
        trader_name: Optional[str] = None,
        guardian_name: Optional[str] = None,
    ) -> str:
        """
        Minimum disclosure: who, which pattern, how serious, when.

        Never `alert.message` — that text is addressed to the trader and carries
        their P&L, instruments and second-person voice. Never the broker client
        id. A guardian needs enough to decide whether to call, and nothing more;
        DPDP purpose limitation and the trader's dignity point the same way here.

        (Letting the trader choose what a guardian sees is the natural follow-up.
        Until that setting exists, the floor is the safe default.)
        """
        who = (trader_name or "").strip() or "Your trading partner"
        greeting = f"Hi {guardian_name.strip()}," if (guardian_name or "").strip() else "Hi,"
        when = _ist_time(alert)

        lines = [
            "*TradeMentor* · accountability alert",
            "",
            greeting,
            "",
            f"{who} asked you to be their accountability partner.",
            "",
            f"A *{severity_label(alert.severity).lower()}* behaviour pattern was flagged on "
            f"their trading today: *{_pattern_label(alert.pattern_type)}*.",
        ]
        if when:
            lines += ["", f"_{when} IST_"]
        lines += [
            "",
            "Trade details are not shared with you. If this is a good moment, check in with them.",
        ]
        return "\n".join(lines)

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def send_test_alert(self, phone_number: str) -> bool:
        """Verify a WhatsApp number is reachable, from Settings."""
        try:
            message = (
                "*TradeMentor* · test message\n\n"
                "WhatsApp alerts are set up correctly.\n"
                "You'll hear from us here when a behaviour pattern is flagged during a session."
            )
            return await whatsapp_service.send_message(phone_number, message)
        except Exception as e:
            logger.error(f"Failed to send test alert: {e}", exc_info=True)
            return False
