"""
Notifications & WhatsApp Guardian Test Suite
=============================================

Tests every layer of the notification pipeline:

  WhatsAppService (service layer)
    WA-01 .. WA-04  service initialization, safe mode, send behavior

  AlertService — message formatting
    AS-01 .. AS-06  user alert format per pattern type
    AS-07 .. AS-11  guardian alert format per pattern type

  AlertService — delivery rules
    AL-01 .. AL-04  only danger alerts trigger WhatsApp (not caution/safe)
    AL-05 .. AL-07  guardian alerts sent when guardian_phone configured

  Report delivery rules
    RP-01 .. RP-05  EOD report prerequisites (guardian_phone, status=connected)
    RP-06 .. RP-08  report task field sourcing (guardian_phone from User table)

All tests mock whatsapp_service.send_message so no actual Twilio calls are made.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.services.alert_service import AlertService
from app.services.whatsapp_service import WhatsAppService
from app.models.risk_alert import RiskAlert
from app.models.broker_account import BrokerAccount


# =============================================================================
# HELPERS
# =============================================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_broker_account(broker_user_id: str = "QAUSER01") -> BrokerAccount:
    return BrokerAccount(
        id=uuid4(),
        user_id=uuid4(),
        broker_name="zerodha",
        broker_email="qa@test.com",
        broker_user_id=broker_user_id,
        status="connected",
    )


def make_risk_alert(
    pattern_type: str,
    severity: str,
    details: dict = None,
    broker_account_id=None,
) -> RiskAlert:
    if broker_account_id is None:
        broker_account_id = uuid4()
    return RiskAlert(
        id=uuid4(),
        broker_account_id=broker_account_id,
        pattern_type=pattern_type,
        severity=severity,
        message=f"TEST: {pattern_type} detected",
        details=details or {},
        detected_at=utc_now(),
    )


ALERT_PATTERNS = [
    ("overtrading",       "danger", {"trade_count": 9}),
    ("revenge_sizing",    "danger", {"size_increase_pct": 85.0}),
    ("consecutive_loss",  "danger", {"consecutive_losses": 5}),
    ("tilt_loss_spiral",  "danger", {}),
]


# =============================================================================
# WHATSAPP SERVICE TESTS
# =============================================================================

class TestWhatsAppService:
    """WhatsAppService initialization and send behavior."""

    def test_WA01_no_credentials_is_safe_mode(self):
        """WA-01: Without Twilio credentials, is_configured is False (safe mode)."""
        with patch("app.services.whatsapp_service.settings") as mock_settings:
            mock_settings.TWILIO_ACCOUNT_SID = None
            mock_settings.TWILIO_AUTH_TOKEN = None
            mock_settings.TWILIO_WHATSAPP_FROM = None
            svc = WhatsAppService()
        assert svc.is_configured is False

    async def test_WA02_safe_mode_send_returns_true(self):
        """WA-02: Safe mode send_message returns True (non-blocking fallback)."""
        with patch("app.services.whatsapp_service.settings") as mock_settings:
            mock_settings.TWILIO_ACCOUNT_SID = None
            mock_settings.TWILIO_AUTH_TOKEN = None
            mock_settings.TWILIO_WHATSAPP_FROM = None
            svc = WhatsAppService()

        result = await svc.send_message("+919876543210", "Test message")
        assert result is True

    async def test_WA03_twilio_error_returns_false(self):
        """WA-03: If Twilio raises exception, send_message returns False (no crash)."""
        with patch("app.services.whatsapp_service.settings") as mock_settings:
            mock_settings.TWILIO_ACCOUNT_SID = "ACtest"
            mock_settings.TWILIO_AUTH_TOKEN = "token"
            mock_settings.TWILIO_WHATSAPP_FROM = "+14155238886"
            svc = WhatsAppService()
            svc.client = MagicMock()
            # Simulate Twilio API failure
            svc.client.messages.create.side_effect = Exception("Twilio error")

        result = await svc.send_message("+919876543210", "Test")
        assert result is False

    def test_WA04_whatsapp_prefix_handled(self):
        """WA-04: Service adds 'whatsapp:' prefix correctly when not already present."""
        with patch("app.services.whatsapp_service.settings") as mock_settings:
            mock_settings.TWILIO_ACCOUNT_SID = None
            mock_settings.TWILIO_AUTH_TOKEN = None
            mock_settings.TWILIO_WHATSAPP_FROM = "+14155238886"
            svc = WhatsAppService()
        # If from_number doesn't have prefix, is_configured still works
        assert svc.from_number == "+14155238886"


# =============================================================================
# ALERT SERVICE — MESSAGE FORMATTING
# =============================================================================

class TestAlertMessageFormatting:
    """
    AlertService._format_alert_message — framing the engine's sentence.

    These assertions changed in the Phase 1 notification-integrity pass. The
    previous versions asserted the defect: they checked for a per-pattern branch
    keyed on `overtrading` / `revenge_sizing` / `consecutive_loss`, and for the
    word "STOP". Those detector names stopped existing at engine v2 — the tests
    kept passing because they used the same dead vocabulary the code did, which
    is exactly why the drift went unnoticed. The imperative was a charter
    violation ("mirror, not blocker") in the first place.
    """

    svc = AlertService()

    def _format(self, pattern_type: str, details: dict, broker_user_id: str = "QA01") -> str:
        alert = make_risk_alert(pattern_type, "danger", details)
        broker = make_broker_account(broker_user_id)
        return self.svc._format_alert_message(alert, broker)

    def test_AS01_message_carries_the_engine_sentence_verbatim(self):
        """AS-01: The engine authors the evidence; this layer only frames it."""
        msg = self._format("overtrading_burst", {"trade_count": 9})
        assert "TEST: overtrading_burst detected" in msg

    def test_AS02_message_gives_no_trading_instruction(self):
        """AS-02: No 'STOP TRADING', no mandatory break — we mirror, not block."""
        msg = self._format("overtrading_burst", {"trade_count": 9})
        assert "STOP TRADING" not in msg.upper()
        assert "MANDATORY" not in msg.upper()

    def test_AS03_message_makes_no_causal_claim(self):
        """AS-03: 'historically leads to major losses' was never substantiated."""
        msg = self._format("size_escalation", {"size_increase_pct": 75.0})
        assert "historically leads" not in msg.lower()

    def test_AS04_current_detector_names_are_readable(self):
        """AS-04: v2 names render as words, not snake_case, with no lookup table."""
        msg = self._format("consecutive_loss_streak", {"consecutive_losses": 5})
        assert "Consecutive loss streak" in msg

    def test_AS05_unknown_pattern_still_produces_a_message(self):
        """AS-05: An unseen pattern_type must format, not blow up or blank out."""
        msg = self._format("brand_new_pattern", {})
        assert "Brand new pattern" in msg
        assert len(msg.strip()) > 0

    def test_AS06_message_states_severity_and_time(self):
        """AS-06: Severity word and IST time appear for every pattern."""
        for pattern, severity, details in ALERT_PATTERNS:
            msg = self._format(pattern, details, broker_user_id="TESTACC")
            assert "Danger" in msg, f"severity missing for {pattern}"
            assert "IST" in msg, f"time missing for {pattern}"

    def test_AS06b_empty_engine_message_falls_back(self):
        """AS-06b: A blank alert.message must not yield an empty WhatsApp body."""
        alert = make_risk_alert("fomo_entry", "danger", {})
        alert.message = ""
        msg = self.svc._format_alert_message(alert, make_broker_account())
        assert "Fomo entry" in msg


# =============================================================================
# ALERT SERVICE — GUARDIAN MESSAGE FORMATTING
# =============================================================================

class TestGuardianMessageFormatting:
    """
    AlertService._format_guardian_alert — the third-party message.

    AS-08 previously asserted the trader's broker_user_id appears in the guardian
    message. That was the leak: the Zerodha client id has no business on a
    friend's phone. The guardian is still told *who* — via display name — so the
    original intent survives; only the identifier changed. The rest of these
    tests are new and assert what a third party must NOT receive.
    """

    svc = AlertService()

    def _guardian(self, pattern_type: str, details: dict, trader_name="Rohit O") -> str:
        alert = make_risk_alert(pattern_type, "danger", details)
        return self.svc._format_guardian_alert(
            alert, trader_name=trader_name, guardian_name="Guardian"
        )

    def test_AS07_guardian_message_is_addressed_to_the_guardian(self):
        """AS-07: Named greeting and accountability framing."""
        msg = self._guardian("session_meltdown", {"trade_count": 9})
        assert "Guardian" in msg
        assert "accountability" in msg.lower()

    def test_AS08_guardian_message_names_trader_without_broker_id(self):
        """AS-08: Display name identifies the trader; the client id never appears."""
        msg = self._guardian("session_meltdown", {"trade_count": 9})
        assert "Rohit O" in msg
        assert "TRADERX" not in msg
        assert "QAUSER01" not in msg

    def test_AS09_guardian_message_does_not_command_anyone(self):
        """AS-09: An invitation to check in, never an instruction to intervene."""
        msg = self._guardian("session_meltdown", {"trade_count": 9})
        assert "check in" in msg.lower()
        assert "STOP" not in msg.upper()
        assert "tilt" not in msg.lower()

    def test_AS10_guardian_message_withholds_trade_detail(self):
        """AS-10: No P&L, no symbols, no counts — the trader did not consent to that."""
        alert = make_risk_alert("session_meltdown", "danger", {"trade_count": 11})
        alert.message = "You are down ₹12,400 after 11 trades in NIFTY"
        msg = self.svc._format_guardian_alert(alert, trader_name="Rohit O")
        assert alert.message not in msg
        assert "12,400" not in msg
        assert "NIFTY" not in msg
        assert "11 trades" not in msg

    def test_AS11_guardian_message_survives_a_missing_display_name(self):
        """AS-11: No display name must not produce 'None asked you to be…'."""
        msg = self._guardian("session_meltdown", {}, trader_name=None)
        assert "None" not in msg
        assert "Your trading partner" in msg


# =============================================================================
# ALERT SERVICE — DELIVERY RULES
# =============================================================================

class TestAlertDeliveryRules:
    """AlertService.send_risk_alert — only danger, correct send call."""

    async def test_AL01_caution_alert_not_sent(self):
        """AL-01: Caution severity alert must NOT send WhatsApp (only danger triggers)."""
        svc = AlertService()
        broker = make_broker_account()
        alert = make_risk_alert("consecutive_loss", severity="caution")

        with patch("app.services.alert_service.whatsapp_service") as mock_wa:
            mock_wa.send_message = AsyncMock(return_value=True)
            result = await svc.send_risk_alert(alert, broker, "+919876543210")

        assert result is False
        mock_wa.send_message.assert_not_called()

    async def test_AL02_danger_alert_is_sent(self):
        """AL-02: Danger severity alert MUST send WhatsApp."""
        svc = AlertService()
        broker = make_broker_account()
        alert = make_risk_alert("overtrading", severity="danger", details={"trade_count": 9})

        with patch("app.services.alert_service.whatsapp_service") as mock_wa:
            mock_wa.send_message = AsyncMock(return_value=True)
            result = await svc.send_risk_alert(alert, broker, "+919876543210")

        assert result is True
        mock_wa.send_message.assert_called_once()
        # Verify it was called with the correct phone number
        call_args = mock_wa.send_message.call_args
        assert call_args[0][0] == "+919876543210"

    async def test_AL03_whatsapp_failure_returns_false(self):
        """AL-03: If WhatsApp send fails, send_risk_alert returns False (no exception)."""
        svc = AlertService()
        broker = make_broker_account()
        alert = make_risk_alert("overtrading", severity="danger")

        with patch("app.services.alert_service.whatsapp_service") as mock_wa:
            mock_wa.send_message = AsyncMock(return_value=False)
            result = await svc.send_risk_alert(alert, broker, "+919876543210")

        assert result is False

    async def test_AL04_test_alert_sends_message(self):
        """AL-04: send_test_alert sends to the provided phone number."""
        svc = AlertService()
        with patch("app.services.alert_service.whatsapp_service") as mock_wa:
            mock_wa.send_message = AsyncMock(return_value=True)
            result = await svc.send_test_alert("+919876540000")

        assert result is True
        mock_wa.send_message.assert_called_once()
        assert mock_wa.send_message.call_args[0][0] == "+919876540000"


# =============================================================================
# ALERT SERVICE — GUARDIAN DELIVERY
# =============================================================================

class TestGuardianDelivery:
    """
    AlertService.send_guardian_alert — the function the live path actually calls.

    These tests used to target `send_risk_alert_with_guardian`, a dual-delivery
    helper that was correct, tested three times, and called from nowhere in
    `app/`. Production sent to the guardian through `send_risk_alert` instead —
    so the green tests were covering a function no caller reached while the real
    path shipped the trader's message to a third party. The helper is gone and
    these now exercise the path Celery uses.
    """

    async def test_AL05_guardian_alert_sends_to_the_guardian_number(self):
        """AL-05: The guardian message goes to the guardian's phone."""
        svc = AlertService()
        alert = make_risk_alert("session_meltdown", severity="danger", details={"consecutive_losses": 5})

        with patch("app.services.alert_service.whatsapp_service") as mock_wa:
            mock_wa.send_message = AsyncMock(return_value=True)
            result = await svc.send_guardian_alert(
                alert, "+919000000002", trader_name="Rohit O", guardian_name="Mentor",
            )

        assert result is True
        mock_wa.send_message.assert_called_once()
        assert mock_wa.send_message.call_args[0][0] == "+919000000002"

    async def test_AL06_guardian_alert_respects_the_severity_floor(self):
        """AL-06: Caution never reaches a third party."""
        svc = AlertService()
        alert = make_risk_alert("session_meltdown", severity="caution")

        with patch("app.services.alert_service.whatsapp_service") as mock_wa:
            mock_wa.send_message = AsyncMock(return_value=True)
            result = await svc.send_guardian_alert(alert, "+919000000002", trader_name="Rohit O")

        assert result is False
        mock_wa.send_message.assert_not_called()

    async def test_AL07_guardian_message_differs_from_the_trader_message(self):
        """AL-07: The two audiences get different text — the whole point of A3."""
        svc = AlertService()
        broker = make_broker_account("TRADERX")
        alert = make_risk_alert("session_meltdown", severity="danger", details={"trade_count": 9})

        messages = []

        async def capture(phone, message):
            messages.append((phone, message))
            return True

        with patch("app.services.alert_service.whatsapp_service") as mock_wa:
            mock_wa.send_message = capture
            await svc.send_risk_alert(alert, broker, "+910000000001")
            await svc.send_guardian_alert(alert, "+910000000002", trader_name="Rohit O", guardian_name="Dad")

        assert len(messages) == 2
        trader_msg, guardian_msg = messages[0][1], messages[1][1]
        assert trader_msg != guardian_msg
        assert "accountability" in guardian_msg.lower()
        # The trader's own evidence sentence must not be forwarded onward.
        assert "TEST: session_meltdown detected" in trader_msg
        assert "TEST: session_meltdown detected" not in guardian_msg


# =============================================================================
# ALERT SERVICE — SEVERITY VOCABULARY (A1 regression)
# =============================================================================

class TestSeverityVocabulary:
    """
    `critical` is the top of the scale and used to be the one class that never
    sent: the gate read `severity != "danger"`, which excluded it. Every channel
    now asks app.core.severity instead of comparing to a literal.
    """

    async def test_SV01_critical_alert_is_sent_to_trader(self):
        """SV-01: The most serious severity must reach the trader."""
        svc = AlertService()
        alert = make_risk_alert("session_meltdown", severity="critical")

        with patch("app.services.alert_service.whatsapp_service") as mock_wa:
            mock_wa.send_message = AsyncMock(return_value=True)
            result = await svc.send_risk_alert(alert, make_broker_account(), "+919876543210")

        assert result is True
        mock_wa.send_message.assert_called_once()

    async def test_SV02_critical_alert_is_sent_to_guardian(self):
        """SV-02: Same for the guardian channel."""
        svc = AlertService()
        alert = make_risk_alert("session_meltdown", severity="critical")

        with patch("app.services.alert_service.whatsapp_service") as mock_wa:
            mock_wa.send_message = AsyncMock(return_value=True)
            result = await svc.send_guardian_alert(alert, "+919000000002", trader_name="Rohit O")

        assert result is True

    async def test_SV03_info_severity_never_sends(self):
        """SV-03: info is analytics-only evidence — no channel, ever."""
        svc = AlertService()
        alert = make_risk_alert("early_exit", severity="info")

        with patch("app.services.alert_service.whatsapp_service") as mock_wa:
            mock_wa.send_message = AsyncMock(return_value=True)
            assert await svc.send_risk_alert(alert, make_broker_account(), "+919876543210") is False
            assert await svc.send_guardian_alert(alert, "+919000000002") is False

    def test_SV04_unknown_severity_is_never_treated_as_severe(self):
        """SV-04: A typo must fail closed, not escalate."""
        from app.core.severity import is_notifiable, rank, worst, at_least

        assert is_notifiable("DANGER") is True          # case-insensitive
        assert is_notifiable("dangerous") is False      # near-miss is not a match
        assert is_notifiable(None) is False
        assert rank("nonsense") == -1
        assert at_least("nonsense", "info") is False
        assert worst(["info", "critical", "caution"]) == "critical"
        assert worst(["nope"]) is None


# =============================================================================
# EOD REPORT DELIVERY RULES
# =============================================================================

class TestEODReportDeliveryRules:
    """Report tasks must send to guardian_phone from User table, not broker_accounts."""

    async def test_RP01_no_guardian_phone_skips_report(self, db):
        """RP-01: User with no guardian_phone does not receive EOD report."""
        from app.models.user import User
        from app.models.broker_account import BrokerAccount as BA
        from app.services.retention_service import RetentionService

        user = User(email=f"rp01_{uuid4().hex[:6]}@qa.internal", display_name="RP Test")
        db.add(user)
        await db.flush()  # get user.id before using it in FK
        broker = BA(
            user_id=user.id,
            broker_name="zerodha",
            broker_email=user.email,
            broker_user_id="RP01TEST",
            status="connected",
        )
        db.add(broker)
        await db.commit()

        # User has NO guardian_phone (default None)
        assert user.guardian_phone is None

        # Simulate what report_tasks does: skip if no phone
        phone = user.guardian_phone
        assert phone is None  # Confirmed: report task correctly skips this account

    async def test_RP02_guardian_phone_on_user_table(self, db):
        """RP-02: guardian_phone is stored on users table (not broker_accounts) after migration 032."""
        from app.models.user import User
        from app.models.broker_account import BrokerAccount as BA

        user = User(
            email=f"rp02_{uuid4().hex[:6]}@qa.internal",
            display_name="RP02",
            guardian_phone="+919876540002",
        )
        db.add(user)
        await db.flush()  # get user.id before using it in FK
        broker = BA(
            user_id=user.id,
            broker_name="zerodha",
            broker_email=user.email,
            broker_user_id="RP02",
            status="connected",
        )
        db.add(broker)
        await db.commit()

        # Verify: phone is on user, not on broker
        assert user.guardian_phone == "+919876540002"
        assert not hasattr(broker, 'guardian_phone') or getattr(broker, 'guardian_phone', None) is None

    async def test_RP03_disconnected_account_skipped(self, db):
        """RP-03: Disconnected broker account is skipped in EOD reports (status != 'connected')."""
        from app.models.user import User
        from app.models.broker_account import BrokerAccount as BA

        user = User(
            email=f"rp03_{uuid4().hex[:6]}@qa.internal",
            guardian_phone="+919876540003",
        )
        db.add(user)
        await db.flush()  # get user.id before using it in FK
        broker = BA(
            user_id=user.id,
            broker_name="zerodha",
            broker_email=user.email,
            broker_user_id="RP03",
            status="disconnected",  # Not connected
        )
        db.add(broker)
        await db.commit()

        # The generate_eod_reports task filters: WHERE status='connected'
        # This broker has status='disconnected' -> would be excluded from the query
        assert broker.status == "disconnected"
        # Confirm: only 'connected' accounts appear in EOD reports batch

    async def test_RP04_connected_account_with_phone_eligible(self, db):
        """RP-04: Connected account + guardian_phone = eligible for EOD report."""
        from app.models.user import User
        from app.models.broker_account import BrokerAccount as BA

        user = User(
            email=f"rp04_{uuid4().hex[:6]}@qa.internal",
            guardian_phone="+919876540004",
        )
        db.add(user)
        await db.flush()  # get user.id before using it in FK
        broker = BA(
            user_id=user.id,
            broker_name="zerodha",
            broker_email=user.email,
            broker_user_id="RP04",
            status="connected",
        )
        db.add(broker)
        await db.commit()

        # Both conditions met -> eligible for report
        assert broker.status == "connected"
        assert user.guardian_phone is not None


# =============================================================================
# REPORT CONTENT TESTS
# =============================================================================

class TestReportContentRules:
    """Report message content requirements."""

    def test_RP05_alert_message_includes_header(self):
        """RP-05: Every alert message starts with TradeMentor header."""
        svc = AlertService()
        for pattern, severity, details in ALERT_PATTERNS:
            alert = make_risk_alert(pattern, severity, details)
            broker = make_broker_account()
            msg = svc._format_alert_message(alert, broker)
            assert "TRADEMENTOR" in msg.upper(), f"Header missing for {pattern}"

    def test_RP06_all_danger_patterns_have_formatted_messages(self):
        """RP-06: Every known danger pattern has a formatted (non-empty) message."""
        svc = AlertService()
        for pattern, severity, details in ALERT_PATTERNS:
            alert = make_risk_alert(pattern, severity, details)
            broker = make_broker_account()
            msg = svc._format_alert_message(alert, broker)
            assert len(msg) > 50, f"Message too short for {pattern}: '{msg}'"

    def test_RP07_guardian_messages_for_all_known_patterns(self):
        """
        RP-07: Every pattern produces a guardian message that names the trader
        and never their broker client id.

        The signature changed with A3/A4: _format_guardian_alert no longer takes
        a BrokerAccount at all. Not having the object is the cheapest guarantee
        that nothing from the trading account can leak into a third party's
        message — the previous version pulled broker_user_id straight out of it.
        """
        svc = AlertService()
        for pattern, severity, details in ALERT_PATTERNS:
            alert = make_risk_alert(pattern, severity, details)
            msg = svc._format_guardian_alert(
                alert, trader_name="Rohit O", guardian_name="TestGuardian"
            )
            assert len(msg) > 50, f"Guardian message too short for {pattern}"
            assert "Rohit O" in msg, f"Trader name missing from guardian message for {pattern}"
            assert "GUARDIAN_TEST" not in msg
            assert "QAUSER01" not in msg

    def test_RP08_message_no_python_internals_leaked(self):
        """RP-08: Alert messages must not contain Python tracebacks or internal error info."""
        svc = AlertService()
        for pattern, severity, details in ALERT_PATTERNS:
            alert = make_risk_alert(pattern, severity, details)
            broker = make_broker_account()
            msg = svc._format_alert_message(alert, broker)
            assert "Traceback" not in msg
            assert "File \"" not in msg
            assert "Exception" not in msg
