# WhatsApp Setup — Complete Guide (Meta Business + Gupshup + Templates)

**Updated:** 2026-03-21
**Approach:** Template-only (business-initiated, no session window needed)

---

## How it works end-to-end

```
User opts in during onboarding (one time)
          ↓
Trade fills → BehaviorEngine → RiskAlert
          ↓
  whatsapp_service.send_alert()
          ↓
  Gupshup API → Meta → User's WhatsApp
                     → Guardian's WhatsApp (DANGER only)
```

Templates can be sent any time to any opted-in number.
No session window. No "user must message you first today."
One-time opt-in at signup = receive alerts forever.

---

## PART 1 — Meta Business Account Setup

This is the foundation. Gupshup (and every other BSP) connects TO your Meta Business Account. You own the WABA (WhatsApp Business Account). Gupshup just sends on your behalf.

### Step 1 — Create a Facebook Business Manager account

1. Go to **https://business.facebook.com**
2. Click "Create Account"
3. Enter your business name (e.g., "TradeMentor AI"), your name, your email
4. Verify your email
5. You now have a Business Manager account (also called Meta Business Suite)

> **Note:** This is NOT the same as a personal Facebook account. It's a separate business entity. You can create one even if you have a personal Facebook account.

### Step 2 — Verify your business (optional but recommended)

- Business Manager → Settings → Business Info → Start Verification
- Upload: GSTIN certificate, incorporation certificate, or utility bill in the business name
- Takes 1–5 business days
- **Without verification**: you can still set up WhatsApp and send messages, but you're limited to 250 conversations/day. Fine for early launch.
- **With verification**: 1,000 conversations/day initially, scalable to unlimited

### Step 3 — Get a dedicated phone number

You need a number that is **NOT currently registered on personal WhatsApp or WhatsApp Business app**.

Options (cheapest to most expensive):
- **Use a secondary SIM you have** — put it in any phone, ensure it's not on WhatsApp. ✅ Free.
- **Airtel/Jio virtual number** — ~₹200-400/month. Can receive OTP via call or SMS.
- **Any landline** — can receive OTP via voice call

> Once you register a number with WhatsApp Business API, you **cannot use it on the WhatsApp app anymore**. It becomes a pure API number. Plan accordingly.

---

## PART 2 — Gupshup Account Setup

### Step 1 — Create Gupshup account

1. Go to **https://www.gupshup.io**
2. Click "Sign Up" → choose "WhatsApp"
3. Fill in company details: name, email, phone, website
4. Verify email
5. You're in the Gupshup dashboard

### Step 2 — Create a WhatsApp app in Gupshup

1. Dashboard → **"Create App"**
2. Choose **"Access API"**
3. Give it a name: `tradementor-ai` (this is your `GUPSHUP_APP_NAME` env var)
4. Select channel: **WhatsApp**
5. Click Create

### Step 3 — Connect your WhatsApp Business number (Embedded Signup)

This is where Gupshup links to your Meta Business Account:

1. Inside your app → **"Go Live"** or **"Setup WhatsApp"**
2. Click **"Connect via Facebook"** (Embedded Signup)
3. A Facebook popup opens — log in with the account that owns your Business Manager
4. Select your Business Manager account
5. Select **"Create a new WhatsApp Business Account"** (or use existing)
   - Business Account Name: `TradeMentor AI`
   - Display Name (what users see): `TradeMentor`
   - Category: `Finance`
   - Business Description: `Trading psychology and behavioral analysis platform`
6. Enter your dedicated phone number
7. Choose verification method: SMS or Voice Call
8. Enter the OTP received
9. Click **Finish**

You now have:
- A WABA (WhatsApp Business Account) owned by you
- Gupshup connected as your BSP (Business Solution Provider)
- Your number is now a WhatsApp Business API number

**Copy from Gupshup dashboard:**
- API Key: Settings → API Key → copy to `GUPSHUP_API_KEY`
- App Name: the name you chose → `GUPSHUP_APP_NAME`
- Source number: your registered number in E.164 without `+` (e.g. `917XXXXXXXXX`) → `GUPSHUP_WHATSAPP_FROM`

---

## PART 3 — Create and Submit Templates

### What a template is

A template is a pre-approved message format with `{{variable}}` slots you fill at send time. Meta reviews the fixed wrapper text. Once approved, you can send it any time to opted-in numbers with any content in the slots.

We use **3 templates** with a single `{{1}}` variable each.
The full dynamic content goes in that one slot — LLM-generated at send time.

### Template 1 — `tradementor_report`

Used for: EOD post-market summary, morning readiness brief

```
📊 TradeMentor

{{1}}

Not investment advice. Open app for full report.
```

**Meta sample value for {{1}} (required when submitting):**
```
Post-Market Summary — 20 Mar

P&L: ₹+6,200 | 5 trades | 60% win rate
Best: ₹+8,100 (BANKNIFTY) | Worst: ₹-3,200 (NIFTY)

You stuck to your plan today. The 11 AM NIFTY trade was your best execution this week — you waited for confirmation instead of entering at the open.

Tomorrow: Keep the same approach. No trades in the first 10 minutes.
```

---

### Template 2 — `tradementor_alert`

Used for: Real-time behavioral alerts to the trader

```
⚠️ TradeMentor Alert

{{1}}

Not investment advice.
```

**Meta sample value for {{1}}:**
```
You've entered NIFTY 3 times in the last 20 minutes after 2 losses. Each entry was bigger than the last. Today's P&L: -₹9,400.

The pattern here is increasing size after losses, not after analysis. Take a 30-minute break before the next trade.
```

---

### Template 3 — `tradementor_guardian`

Used for: Guardian notifications when trader hits DANGER level

```
🚨 TradeMentor Guardian Alert

{{1}}

TradeMentor AI — Behavioural monitoring
```

**Meta sample value for {{1}}:**
```
[Rahul — 2:47 PM]

Rahul has placed 6 trades in the last 35 minutes, including 4 after consecutive losses. His session P&L is -₹18,400 and his risk score has reached DANGER level.

This matches an emotional trading pattern. You may want to reach out to him.
```

---

### How to submit templates in Gupshup

1. Dashboard → Your App → **"Templates"** → **"Create Template"**
2. Fill in:
   - Template Name: `tradementor_report` (lowercase, underscores only)
   - Category: **Utility** (NOT Marketing — utility approves faster and costs less)
   - Language: English
   - Header: leave blank (no header)
   - Body: paste the exact text above
   - Footer: leave blank
   - Buttons: none
3. In the **Sample Content** field for `{{1}}`: paste the sample from above
4. Submit

Repeat for all 3 templates. Submit all at once.

**Approval time:** 24–72 hours. Meta auto-reviews utility templates.

**After approval:** Each template gets a UUID. Copy them:
- `GUPSHUP_TMPL_REPORT` = UUID of `tradementor_report`
- `GUPSHUP_TMPL_ALERT` = UUID of `tradementor_alert`
- `GUPSHUP_TMPL_GUARDIAN` = UUID of `tradementor_guardian`

---

## PART 4 — Opt-In Flow

### User opt-in

During the onboarding wizard (Step 3 / Preferences), add:

```
WhatsApp Alerts
[+91 XXXXXXXXXX] ← pre-filled from their registered number
☑ Send me behavioral alerts and daily reports on WhatsApp
```

That checkbox = documented consent. No other action needed.
When they connect Zerodha, you store `whatsapp_opted_in = True` on their profile.

You can now send them templates any time.

### Guardian opt-in

When the user saves a guardian phone number in Settings, your backend:

1. Sends the guardian this message using the **`tradementor_guardian` template**:

```
[TradeMentor — Guardian Setup]

You've been added as a trading guardian by [User Name].

You'll receive an alert if they trigger high-risk behavioral patterns during a trading session.

No action needed right now. If you'd like to opt out, reply STOP.
```

2. Store `guardian_opted_in = True` for that phone number

That's it. The guardian doesn't need to message you first.

> **STOP handling:** Gupshup auto-manages STOP replies — it marks the number as opted out and stops delivery. You don't need to build this.

---

## PART 5 — Message Examples (what actually arrives on phone)

### Real-time DANGER alert (user's phone)

> ⚠️ **TradeMentor Alert**
>
> You've placed 8 trades in the last 45 minutes, 5 of them after the 10:30 NIFTY loss of ₹14,200. Each re-entry was on the same underlying with a larger position. Session P&L is now -₹31,400.
>
> This is not your trading plan — it's a recovery spiral. Close your platform for 1 hour.
>
> *Not investment advice.*

---

### EOD report (user's phone)

> 📊 **TradeMentor**
>
> Post-Market Summary — 20 Mar
>
> 📈 P&L: ₹+11,200 | 4 trades | 75% win rate
> Best: ₹+9,800 (NIFTY CE) | Worst: ₹-1,400
>
> Clean session. You took 4 trades, all within your plan. The NIFTY 9:45 AM entry was particularly disciplined — you waited 30 minutes after open instead of entering at the spike.
>
> Tomorrow: Expiry day. Reduce lot sizes by 30%, no new positions after 2 PM.
>
> *Not investment advice. Open app for full report.*

---

### Guardian alert (guardian's phone)

> 🚨 **TradeMentor Guardian Alert**
>
> [Rahul — 2:47 PM]
>
> Rahul has placed 6 trades in the last 40 minutes after a ₹22,000 loss on BANKNIFTY at 2:08 PM. His session P&L is -₹38,600. Each trade since the loss has been larger than the previous one.
>
> This pattern of escalating positions after a large loss is concerning. You may want to reach out to him.
>
> *TradeMentor AI — Behavioural monitoring*

---

## PART 6 — Code (what needs to be wired)

### 6.1 `whatsapp_service.py` — Full Rewrite

```python
import httpx
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)
GUPSHUP_TEMPLATE_URL = "https://api.gupshup.io/wa/api/v1/template/msg"


class WhatsAppService:
    """
    One-way WhatsApp notifications via Gupshup BSP.
    All messages are business-initiated template messages.
    Safe mode when credentials are not configured — logs only.
    """

    @property
    def is_configured(self) -> bool:
        return bool(
            settings.GUPSHUP_API_KEY
            and settings.GUPSHUP_APP_NAME
            and settings.GUPSHUP_WHATSAPP_FROM
        )

    def _normalize(self, number: str) -> str:
        """E.164 without + prefix. 10-digit numbers get 91 prefix."""
        n = number.strip().replace(" ", "").replace("-", "").lstrip("+")
        return "91" + n if len(n) == 10 else n

    async def send_template(self, to: str, template_id: str, content: str) -> bool:
        if not self.is_configured:
            logger.info("WhatsApp safe mode → %s | %s", to, content[:100])
            return True
        if not template_id:
            logger.warning("send_template: no template_id — skipping")
            return False

        data = {
            "source":      settings.GUPSHUP_WHATSAPP_FROM,
            "destination": self._normalize(to),
            "template":    json.dumps({"id": template_id, "params": [content]}),
            "src.name":    settings.GUPSHUP_APP_NAME,
        }
        headers = {
            "apikey":       settings.GUPSHUP_API_KEY,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(GUPSHUP_TEMPLATE_URL, data=data, headers=headers)
                r.raise_for_status()
                logger.info("WA sent msgId=%s to=%s", r.json().get("messageId"), to)
                return True
        except Exception as e:
            logger.error("Gupshup send failed: %s", e)
            return False

    async def send_report(self, to: str, content: str) -> bool:
        return await self.send_template(to, settings.GUPSHUP_TMPL_REPORT, content)

    async def send_alert(self, to: str, content: str) -> bool:
        return await self.send_template(to, settings.GUPSHUP_TMPL_ALERT, content)

    async def send_guardian(self, to: str, content: str) -> bool:
        return await self.send_template(to, settings.GUPSHUP_TMPL_GUARDIAN, content)


whatsapp_service = WhatsAppService()
```

### 6.2 Wire real-time alerts into `trade_tasks.py`

After `behavior_engine.analyze()` returns, if `result.alerts` contains DANGER alerts, send WhatsApp:

```python
# After behavior engine runs and saves alerts to DB:
danger_alerts = [a for a in result.alerts if a.severity == "danger"]
if danger_alerts and user_phone:
    from app.services.ai_service import ai_service as _ai
    for alert in danger_alerts[:1]:  # max 1 WA per trade event
        content = await _ai.generate_whatsapp_alert(
            pattern_type=alert.pattern_type,
            recent_trades_summary=f"{len(session_trades)} trades today, P&L ₹{session_pnl:,.0f}",
            pnl_today=float(session_pnl),
            trade_count_today=len(session_trades),
        )
        await whatsapp_service.send_alert(user_phone, content)

# Guardian: only on DANGER + guardian phone exists
if danger_alerts and guardian_phone and trader_name:
    content = await _ai.generate_whatsapp_guardian(
        trader_name=trader_name,
        pattern_type=danger_alerts[0].pattern_type,
        recent_trades_summary=f"{len(session_trades)} trades, P&L ₹{session_pnl:,.0f}",
        pnl_today=float(session_pnl),
        time_str=datetime.now(IST).strftime("%-I:%M %p"),
    )
    await whatsapp_service.send_guardian(guardian_phone, content)
```

### 6.3 `retention_service.py` — Replace free-form with template

```python
# In send_eod_report():
if phone_number:
    from app.services.ai_service import ai_service as _ai
    content = await _ai.generate_whatsapp_eod(report)
    await whatsapp_service.send_report(phone_number, content)

# In send_morning_brief():
if phone_number:
    from app.services.ai_service import ai_service as _ai
    content = await _ai.generate_whatsapp_morning(briefing)
    await whatsapp_service.send_report(phone_number, content)
```

### 6.4 `requirements.txt`

```
# Remove:
twilio>=8.10.0

# Must have:
httpx>=0.27.0
```

---

## PART 7 — Environment Variables

```bash
# backend/.env

# Gupshup WhatsApp
GUPSHUP_API_KEY=your_api_key_from_gupshup_dashboard
GUPSHUP_APP_NAME=tradementor-ai
GUPSHUP_WHATSAPP_FROM=917XXXXXXXXX     # E.164 without +

# Template UUIDs — fill after Meta approves (24-72h after submission)
GUPSHUP_TMPL_REPORT=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
GUPSHUP_TMPL_ALERT=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
GUPSHUP_TMPL_GUARDIAN=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## PART 8 — Checklist

### Day 1 (no code)
- [ ] Create Facebook Business Manager at business.facebook.com
- [ ] Get a dedicated phone number not on WhatsApp
- [ ] Create Gupshup account at gupshup.io
- [ ] Create app in Gupshup → Connect via Facebook (Embedded Signup)
- [ ] Verify phone number via OTP
- [ ] Copy API Key, App Name, Source Number to .env
- [ ] Create 3 templates (tradementor_report, tradementor_alert, tradementor_guardian)
- [ ] Submit all 3 for Meta approval

### Day 2 (code — while templates are being approved)
- [ ] Rewrite `whatsapp_service.py` (Section 6.1)
- [ ] Wire alerts into `trade_tasks.py` (Section 6.2)
- [ ] Update `retention_service.py` (Section 6.3)
- [ ] Remove twilio from `requirements.txt` (Section 6.4)
- [ ] Add 4 LLM methods to `ai_service.py` (from previous version of this doc — Section 6.3 there)

### Day 3 (test after template approval)
- [ ] Paste template UUIDs into .env
- [ ] Send test EOD report to your number: `python -c "from app... ; await whatsapp_service.send_report(...)"`
- [ ] Manually trigger a DANGER alert, verify WhatsApp arrives
- [ ] Set guardian phone in Settings, verify confirmation message arrives
- [ ] Test on both Android and iPhone

---

## PART 9 — Costs

| Item | Cost |
|---|---|
| Meta per-conversation fee (utility template) | ~₹0.35–0.60 per 24h window |
| Gupshup platform margin | ~₹0.08–0.15 per message |
| Gupshup monthly platform fee | ~₹0 (pay-per-use on self-serve) |
| Effective cost per user per day (alerts + EOD) | ~₹0.50–0.80 |
| 100 active users/day | ~₹50–80/day = ₹1,500–2,400/month |

WhatsApp charges per **conversation** (24h window), not per message. If a user gets 3 alerts and 1 EOD report in one day, that's 1 conversation charge.

---

## Why not other providers

| Provider | Same Meta verification? | India support | Notes |
|---|---|---|---|
| Twilio | Yes | OK | ~3× more expensive than Gupshup |
| WATI | Yes | Good | ₹2,500/mo base fee |
| Interakt | Yes | Good | ₹999/mo base fee |
| AiSensy | Yes | Good | ₹999/mo base fee |
| Meta Cloud API direct | Yes | Good | Free API, only pay Meta fees — but harder to set up, no support |

All of them require the same Meta Business verification. The difference is platform fees on top. Gupshup self-serve is pay-per-use with no monthly base.
