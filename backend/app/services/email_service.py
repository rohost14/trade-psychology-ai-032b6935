"""
Email Service for TradeMentor AI

Sends HTML email reports using SMTP (smtplib) via asyncio executor.
Safe mode when SMTP credentials are not configured — logs only.

Setup: set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM in .env

    # Gmail example
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=reports@yourdomain.com
    SMTP_PASS=your-app-password          # Gmail: use App Password, not account password
    EMAIL_FROM=TradeMentor AI <reports@yourdomain.com>
"""

import smtplib
import logging
import asyncio
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import partial
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASS
        self.from_addr = settings.EMAIL_FROM

    @property
    def is_configured(self) -> bool:
        """True when SMTP credentials are fully set."""
        return bool(self.host and self.user and self.password and self.from_addr)

    def _send_sync(self, to: str, subject: str, html: str, text: str) -> None:
        """Blocking SMTP send — called in executor thread."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = to
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(self.user, self.password)
            smtp.sendmail(self.from_addr, [to], msg.as_string())

    async def send_email(
        self,
        to: str,
        subject: str,
        html: str,
        text: Optional[str] = None,
    ) -> bool:
        """
        Send an HTML email. Returns True if sent (or safe-moded).

        Args:
            to: Recipient email address.
            subject: Email subject line.
            html: HTML body.
            text: Plain-text fallback. Auto-stripped from HTML if None.
        """
        if not self.is_configured:
            logger.info(
                "Email Safe Mode: subject=%s to=%s | html_len=%d",
                subject, to, len(html),
            )
            return True

        if text is None:
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s{2,}", " ", text).strip()

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                partial(self._send_sync, to, subject, html, text),
            )
            logger.info("Email sent: '%s' → %s", subject, to)
            return True
        except Exception as e:
            logger.error("Email send failed to %s: %s", to, e)
            return False


# ── HTML email templates ──────────────────────────────────────────────────────

def _email_wrap(title: str, body_html: str) -> str:
    """Wrap content in a minimal, email-client-safe HTML shell."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:24px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
          <!-- Header -->
          <tr>
            <td style="background:#0d9488;padding:20px 28px;border-radius:8px 8px 0 0;">
              <p style="margin:0;font-size:18px;font-weight:600;color:#ffffff;letter-spacing:-0.3px;">
                TradeMentor AI
              </p>
              <p style="margin:4px 0 0;font-size:13px;color:rgba(255,255,255,0.8);">{title}</p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="background:#ffffff;padding:28px;border-radius:0 0 8px 8px;border:1px solid #e4e4e7;border-top:none;">
              {body_html}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:16px 0;text-align:center;">
              <p style="margin:0;font-size:12px;color:#71717a;">
                TradeMentor AI &nbsp;·&nbsp; Trading Psychology Platform
              </p>
              <p style="margin:4px 0 0;font-size:11px;color:#a1a1aa;">
                To stop these emails, disable email reports in Settings.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _pnl_color(pnl: float) -> str:
    return "#16a34a" if pnl >= 0 else "#dc2626"


def _pnl_sign(pnl: float) -> str:
    return f"+₹{pnl:,.0f}" if pnl >= 0 else f"₹{pnl:,.0f}"


def format_eod_email(report: dict) -> tuple[str, str]:
    """
    Return (subject, html) for a post-market EOD email.

    Args:
        report: dict from DailyReportsService.generate_post_market_report()
    """
    summary = report.get("summary", {})
    patterns = report.get("patterns_detected", [])
    lessons = report.get("key_lessons", [])
    tomorrow = report.get("tomorrow_focus", {})
    journey = report.get("emotional_journey", {})
    report_date = report.get("report_date", "")

    pnl = summary.get("total_pnl", 0)
    total_trades = summary.get("total_trades", 0)
    win_rate = summary.get("win_rate", 0)
    largest_win = summary.get("largest_win", 0)
    largest_loss = summary.get("largest_loss", 0)

    pnl_color = _pnl_color(pnl)
    pnl_text = _pnl_sign(pnl)
    pnl_emoji = "📈" if pnl >= 0 else "📉"

    subject = f"{pnl_emoji} Post-Market Report — {pnl_text} | {total_trades} trade(s)"

    # Build stats row
    stats_html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
      <tr>
        <td width="25%" style="text-align:center;padding:12px 8px;background:#f4f4f5;border-radius:8px;">
          <p style="margin:0;font-size:22px;font-weight:700;color:{pnl_color};">{pnl_text}</p>
          <p style="margin:4px 0 0;font-size:11px;color:#71717a;text-transform:uppercase;letter-spacing:.5px;">Net P&amp;L</p>
        </td>
        <td width="4%"></td>
        <td width="25%" style="text-align:center;padding:12px 8px;background:#f4f4f5;border-radius:8px;">
          <p style="margin:0;font-size:22px;font-weight:700;color:#18181b;">{total_trades}</p>
          <p style="margin:4px 0 0;font-size:11px;color:#71717a;text-transform:uppercase;letter-spacing:.5px;">Trades</p>
        </td>
        <td width="4%"></td>
        <td width="25%" style="text-align:center;padding:12px 8px;background:#f4f4f5;border-radius:8px;">
          <p style="margin:0;font-size:22px;font-weight:700;color:#18181b;">{win_rate:.0f}%</p>
          <p style="margin:4px 0 0;font-size:11px;color:#71717a;text-transform:uppercase;letter-spacing:.5px;">Win Rate</p>
        </td>
        <td width="4%"></td>
        <td width="25%" style="text-align:center;padding:12px 8px;background:#f4f4f5;border-radius:8px;">
          <p style="margin:0;font-size:22px;font-weight:700;color:#18181b;">
            {summary.get('profit_factor', 0):.1f}x
          </p>
          <p style="margin:4px 0 0;font-size:11px;color:#71717a;text-transform:uppercase;letter-spacing:.5px;">P.Factor</p>
        </td>
      </tr>
    </table>"""

    # Win/Loss detail
    detail_html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;border:1px solid #e4e4e7;border-radius:8px;overflow:hidden;">
      <tr style="background:#f9f9fa;">
        <td style="padding:10px 14px;font-size:12px;font-weight:600;color:#71717a;text-transform:uppercase;letter-spacing:.5px;">Best Trade</td>
        <td style="padding:10px 14px;text-align:right;font-size:14px;font-weight:600;color:#16a34a;">+₹{largest_win:,.0f}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;font-size:12px;font-weight:600;color:#71717a;text-transform:uppercase;letter-spacing:.5px;border-top:1px solid #e4e4e7;">Worst Trade</td>
        <td style="padding:10px 14px;text-align:right;font-size:14px;font-weight:600;color:#dc2626;border-top:1px solid #e4e4e7;">₹{largest_loss:,.0f}</td>
      </tr>
      <tr style="background:#f9f9fa;">
        <td style="padding:10px 14px;font-size:12px;font-weight:600;color:#71717a;text-transform:uppercase;letter-spacing:.5px;border-top:1px solid #e4e4e7;">Winners / Losers</td>
        <td style="padding:10px 14px;text-align:right;font-size:14px;color:#18181b;border-top:1px solid #e4e4e7;">{summary.get('winners', 0)} W &nbsp; / &nbsp; {summary.get('losers', 0)} L</td>
      </tr>
    </table>"""

    # Emotional journey
    journey_html = ""
    if journey.get("timeline"):
        emojis = " → ".join(t["emoji"] for t in journey["timeline"][:8])
        journey_html = f"""
    <div style="margin-bottom:20px;padding:14px;background:#f4f4f5;border-radius:8px;">
      <p style="margin:0 0 6px;font-size:12px;font-weight:600;color:#71717a;text-transform:uppercase;letter-spacing:.5px;">Emotional Journey</p>
      <p style="margin:0;font-size:20px;letter-spacing:3px;">{emojis}</p>
    </div>"""

    # Patterns
    danger_patterns = [p for p in patterns if p.get("severity") == "danger"]
    patterns_html = ""
    if danger_patterns:
        rows = ""
        for p in danger_patterns[:3]:
            rows += f"""<li style="margin:4px 0;font-size:13px;color:#7c2d12;">
              ⚠️ {p['pattern'].replace('_', ' ').title()} at {p.get('time', '?')}
            </li>"""
        patterns_html = f"""
    <div style="margin-bottom:20px;padding:14px;background:#fef3c7;border:1px solid #fde68a;border-radius:8px;">
      <p style="margin:0 0 8px;font-size:12px;font-weight:600;color:#92400e;text-transform:uppercase;">Patterns Detected</p>
      <ul style="margin:0;padding-left:16px;">{rows}</ul>
    </div>"""
    elif total_trades > 0:
        patterns_html = """
    <div style="margin-bottom:20px;padding:14px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;">
      <p style="margin:0;font-size:13px;color:#166534;">✅ No danger patterns detected — clean trading day</p>
    </div>"""

    # Key lesson
    lesson_html = ""
    if lessons:
        lesson = lessons[0]
        lesson_html = f"""
    <div style="margin-bottom:20px;padding:14px;background:#eff6ff;border-left:3px solid #3b82f6;border-radius:0 8px 8px 0;">
      <p style="margin:0 0 4px;font-size:12px;font-weight:600;color:#1e40af;text-transform:uppercase;">Key Lesson</p>
      <p style="margin:0;font-size:13px;color:#1e3a5f;line-height:1.5;">{lesson['lesson']}</p>
    </div>"""

    # Tomorrow focus
    tomorrow_html = ""
    if tomorrow.get("primary"):
        tomorrow_html = f"""
    <div style="margin-bottom:8px;padding:14px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;">
      <p style="margin:0 0 6px;font-size:12px;font-weight:600;color:#166534;text-transform:uppercase;">Tomorrow's Focus</p>
      <p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#14532d;">{tomorrow['primary']}</p>
      <p style="margin:0;font-size:12px;color:#166534;font-style:italic;">Rule: {tomorrow.get('rule', '')}</p>
    </div>"""

    body = f"""
    <h2 style="margin:0 0 4px;font-size:16px;font-weight:600;color:#18181b;">Post-Market Report</h2>
    <p style="margin:0 0 20px;font-size:13px;color:#71717a;">{report_date}</p>
    {stats_html}
    {detail_html}
    {journey_html}
    {patterns_html}
    {lesson_html}
    {tomorrow_html}
    <p style="margin:16px 0 0;font-size:11px;color:#a1a1aa;text-align:center;">
      View full analytics at <a href="#" style="color:#0d9488;">TradeMentor AI</a>
    </p>"""

    return subject, _email_wrap("Post-Market Report", body)


def format_morning_email(briefing: dict) -> tuple[str, str]:
    """
    Return (subject, html) for a morning briefing email.

    Args:
        briefing: dict from DailyReportsService.generate_morning_briefing()
    """
    readiness = briefing.get("readiness_score", {})
    day_warning = briefing.get("day_warning")
    recent = briefing.get("recent_summary", {})
    watch_outs = briefing.get("watch_outs", [])
    checklist = briefing.get("checklist", [])
    day_name = briefing.get("day_name", "Today")
    report_date = briefing.get("report_date", "")

    score = readiness.get("score", 100)
    status = readiness.get("status", "ready")

    if status == "warning":
        score_color = "#dc2626"
        score_bg = "#fef2f2"
        score_border = "#fecaca"
        status_label = "High Risk"
    elif status == "caution":
        score_color = "#d97706"
        score_bg = "#fffbeb"
        score_border = "#fde68a"
        status_label = "Caution"
    else:
        score_color = "#16a34a"
        score_bg = "#f0fdf4"
        score_border = "#bbf7d0"
        status_label = "Ready"

    subject = f"🌅 Morning Brief — {day_name} | Readiness {score}/100"

    readiness_html = f"""
    <div style="margin-bottom:20px;padding:16px;background:{score_bg};border:1px solid {score_border};border-radius:8px;">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <p style="margin:0 0 2px;font-size:12px;font-weight:600;color:#71717a;text-transform:uppercase;">Readiness Score</p>
          <p style="margin:0;font-size:28px;font-weight:700;color:{score_color};">{score}<span style="font-size:14px;font-weight:400;">/100</span></p>
          <p style="margin:4px 0 0;font-size:13px;color:{score_color};">{status_label} — {readiness.get('message', '')}</p>
        </div>
      </div>
    </div>"""

    # Day warning
    warning_html = ""
    if day_warning and day_warning.get("is_danger_day"):
        warning_html = f"""
    <div style="margin-bottom:20px;padding:14px;background:#fef3c7;border:1px solid #fde68a;border-radius:8px;">
      <p style="margin:0;font-size:13px;color:#92400e;">⚠️ {day_warning['message']}</p>
    </div>"""

    # Recent summary
    recent_html = ""
    if recent.get("has_recent_trades") and recent.get("message"):
        recent_html = f"""
    <div style="margin-bottom:20px;padding:14px;background:#f4f4f5;border-radius:8px;">
      <p style="margin:0 0 4px;font-size:12px;font-weight:600;color:#71717a;text-transform:uppercase;">Yesterday</p>
      <p style="margin:0;font-size:13px;color:#3f3f46;line-height:1.5;">{recent['message']}</p>
    </div>"""

    # Watch-outs
    watch_html = ""
    if watch_outs:
        items = ""
        for wo in watch_outs[:4]:
            severity_color = "#dc2626" if wo.get("severity") == "high" else "#d97706" if wo.get("severity") == "medium" else "#3f3f46"
            items += f"""<tr>
              <td style="padding:8px 0;font-size:13px;color:{severity_color};border-bottom:1px solid #e4e4e7;">
                {wo['icon']} {wo['message']}
              </td>
            </tr>"""
        watch_html = f"""
    <div style="margin-bottom:20px;">
      <p style="margin:0 0 10px;font-size:12px;font-weight:600;color:#71717a;text-transform:uppercase;letter-spacing:.5px;">Today's Watch-Outs</p>
      <table width="100%" cellpadding="0" cellspacing="0">{items}</table>
    </div>"""

    # Checklist
    checklist_html = ""
    if checklist:
        items = "".join(
            f'<li style="margin:6px 0;font-size:13px;color:#3f3f46;">☐ {item["item"]}</li>'
            for item in checklist[:5]
        )
        checklist_html = f"""
    <div style="margin-bottom:8px;padding:14px;background:#eff6ff;border-radius:8px;">
      <p style="margin:0 0 10px;font-size:12px;font-weight:600;color:#1e40af;text-transform:uppercase;">Mental Checklist</p>
      <ul style="margin:0;padding-left:18px;">{items}</ul>
    </div>"""

    body = f"""
    <h2 style="margin:0 0 4px;font-size:16px;font-weight:600;color:#18181b;">Morning Readiness Brief</h2>
    <p style="margin:0 0 20px;font-size:13px;color:#71717a;">{day_name}, {report_date}</p>
    {readiness_html}
    {warning_html}
    {recent_html}
    {watch_html}
    {checklist_html}
    <p style="margin:16px 0 0;font-size:13px;color:#71717a;font-style:italic;text-align:center;">
      Markets open at 9:15 AM IST. Trade with discipline.
    </p>"""

    return subject, _email_wrap("Morning Readiness Brief", body)


# Singleton instance
email_service = EmailService()
