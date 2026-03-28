# TradeMentor AI — Production Launch Plan
*Created: 2026-03-17 | Owner: Engineering + Product*
*This is the master plan. Update it as items complete.*

---

## How to Use This Document

Work **top to bottom, sprint by sprint**. Do not jump ahead. Every sprint builds on the
previous one. Items within a sprint can be parallelised if you have multiple people.

**Status legend:**
- `[ ]` Not started
- `[→]` In progress
- `[✓]` Complete
- `[~]` Deferred / deprioritised

---

## Current State Snapshot (before this plan)

| Area | Status | Score |
|------|--------|-------|
| Core backend (FastAPI, DB, Celery, Redis) | ✅ Production-grade | 9/10 |
| Behavioral detection (15 patterns) | ✅ Done | 9/10 |
| Real-time events (WebSocket, Redis Streams) | ✅ Done | 9/10 |
| Security (JWT, OAuth, encryption, rate limiting) | ✅ Done | 8.5/10 |
| Frontend (8 screens, mobile nav, dark mode) | ✅ Done | 8/10 |
| AI Coach (with SEBI guardrails) | ✅ Done | 8/10 |
| Push notifications (VAPID + service worker) | ✅ Done | 9/10 |
| WhatsApp (Twilio + safe mode) | ✅ Done | 9/10 |
| Email reports (SMTP) | ✅ Done | 8/10 |
| SEBI compliance (ToS, Privacy, consent gate) | ✅ Done | 8/10 |
| Tests (296 unit + 26 integration) | ✅ Done | 8/10 |
| DevOps (Docker, .env.example, maintenance mode) | ✅ Done | 8/10 |
| **Payments / subscriptions** | ❌ Missing | 0/10 |
| **Landing page (marketing)** | ❌ Missing | 0/10 |
| **Authentication (OTP, guardian verify)** | ❌ Missing | 0/10 |
| **Admin panel** | ❌ Missing | 0/10 |
| **Feature gating (free vs paid)** | ❌ Missing | 0/10 |

**Overall: 8.5/10 technical, 4/10 business-ready. This plan closes the gap.**

---

## SPRINT 0 — Do This Before Writing Any Code
### (1–3 days, no code, just setup)

These block every sprint that follows. Do them in parallel.

---

### S0-1: Run the app end-to-end
**Problem:** The app has never been run with real Zerodha credentials. There will be bugs.

**Steps:**
1. Set up `backend/.env` with all credentials (use `.env.example` as guide)
2. Apply all migrations (035–047) to Supabase if not already done
3. Start backend: `uvicorn app.main:app --reload --port 8000`
4. Start frontend: `npm run dev`
5. Connect with your own Zerodha account
6. Click through every single screen
7. Log every bug in a `bugs.md` file
8. Fix bugs before proceeding

**What to check specifically:**
- [ ] Dashboard loads positions and trades
- [ ] Analytics shows data for all 5 tabs
- [ ] AI Coach responds (needs `OPENROUTER_API_KEY`)
- [ ] Alerts page shows live/history/patterns
- [ ] Blowup Shield page loads
- [ ] Portfolio Radar loads
- [ ] Settings saves and reloads correctly
- [ ] Mobile view (F12 → mobile simulation) looks right
- [ ] Dark mode toggle works
- [ ] Guest mode shows demo data correctly
- [ ] Welcome page consent checkbox gates CTAs correctly

---

### S0-2: Create Razorpay account
**Why now:** Razorpay account approval takes 2–5 business days. Start immediately.

**Steps:**
1. Go to razorpay.com → Create account
2. Business type: "Individual" or register a company (recommended: register LLP/Pvt Ltd before launch)
3. Complete KYC (PAN, bank account, business proof)
4. Enable "Subscriptions" product in dashboard
5. Set GSTIN if you have one (auto-GST invoicing)
6. Note down: `Key ID`, `Key Secret`, `Webhook Secret`
7. Create test subscription plans:
   - Pro Monthly: ₹499/month, 3-month mandatory
   - Pro Yearly: ₹3,999/year
8. Note the `plan_id` for each

**Config to add to `.env`:**
```
RAZORPAY_KEY_ID=rzp_test_xxx
RAZORPAY_KEY_SECRET=xxx
RAZORPAY_WEBHOOK_SECRET=xxx
RAZORPAY_PRO_MONTHLY_PLAN_ID=plan_xxx
RAZORPAY_PRO_YEARLY_PLAN_ID=plan_xxx
```

---

### S0-3: Define free vs paid features
**Make this decision now, in writing, before building the gate.**

**Recommended split:**

| Feature | Free | Pro (₹499/mo) |
|---------|------|---------------|
| Connect Zerodha | ✅ | ✅ |
| Trade history (last 30 days) | ✅ | ✅ |
| Dashboard (positions, P&L) | ✅ | ✅ |
| Basic analytics (Summary tab only) | ✅ | ✅ |
| 5 behavioral patterns | ✅ | ✅ |
| All 15 behavioral patterns | ❌ | ✅ |
| Analytics (all 5 tabs) | ❌ | ✅ |
| AI Coach | ❌ | ✅ |
| WhatsApp reports | ❌ | ✅ |
| Email reports | ❌ | ✅ |
| Push notifications | ✅ limited | ✅ unlimited |
| Guardian mode | ❌ | ✅ |
| Portfolio Radar | ❌ | ✅ |
| Reports Hub | ❌ | ✅ |
| Blowup Shield | ✅ view only | ✅ fully configurable |
| Trade history (unlimited) | ❌ | ✅ |
| Journal | ✅ 10 entries | ✅ unlimited |

**Write this to a `FEATURE_FLAGS.md` file in `/docs` before building.**

---

### S0-4: Lawyer review (1 hour, ₹5,000–15,000)
**Why:** The ToS and Privacy Policy were AI-generated. Before you have paying customers,
have a startup lawyer in India review and countersign them. Specifically ask about:
- Whether TradeMentor qualifies as Investment Adviser under SEBI IA Regs 2013
- DPDP Act 2023 compliance checklist
- Razorpay's requirement for refund policy

---

## SPRINT 1 — Payments (Week 1–2)
### Goal: Users can pay. Revenue flows.

This is the most important sprint. Everything else is secondary.

---

### S1-1: Database migrations

**File:** `backend/migrations/048_subscriptions.sql`

```sql
-- Subscription plans (admin-seeded)
CREATE TABLE subscription_plans (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_key           TEXT UNIQUE NOT NULL,
    -- 'free', 'pro_monthly', 'pro_yearly'
    display_name       TEXT NOT NULL,
    price_paise        INTEGER NOT NULL DEFAULT 0,
    -- 0 = free; 49900 = ₹499; 399900 = ₹3,999
    billing_interval   TEXT NOT NULL,
    -- 'month', 'year', 'lifetime'
    razorpay_plan_id   TEXT,
    features           JSONB NOT NULL DEFAULT '{}',
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- User subscriptions
CREATE TABLE subscriptions (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id                     UUID NOT NULL REFERENCES subscription_plans(id),
    status                      TEXT NOT NULL DEFAULT 'trialing',
    -- 'trialing', 'active', 'past_due', 'cancelled', 'expired'
    razorpay_subscription_id    TEXT UNIQUE,
    razorpay_customer_id        TEXT,
    current_period_start        TIMESTAMPTZ,
    current_period_end          TIMESTAMPTZ,
    trial_end                   TIMESTAMPTZ,
    cancel_at_period_end        BOOLEAN NOT NULL DEFAULT FALSE,
    cancelled_at                TIMESTAMPTZ,
    pause_collection_until      TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Payment transactions (full audit trail)
CREATE TABLE payment_transactions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id       UUID REFERENCES subscriptions(id),
    user_id               UUID NOT NULL REFERENCES users(id),
    razorpay_payment_id   TEXT UNIQUE,
    razorpay_order_id     TEXT,
    razorpay_invoice_id   TEXT,
    amount_paise          INTEGER NOT NULL,
    currency              TEXT NOT NULL DEFAULT 'INR',
    status                TEXT NOT NULL,
    -- 'captured', 'failed', 'refunded', 'pending'
    failure_reason        TEXT,
    failure_code          TEXT,
    refund_id             TEXT,
    refund_amount_paise   INTEGER,
    metadata              JSONB DEFAULT '{}',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed plans
INSERT INTO subscription_plans (plan_key, display_name, price_paise, billing_interval, features)
VALUES
('free', 'Free', 0, 'month', '{"max_patterns": 5, "history_days": 30, "ai_coach": false, "reports": false, "guardian": false, "journal_limit": 10}'),
('pro_monthly', 'Pro Monthly', 49900, 'month', '{"max_patterns": 15, "history_days": 9999, "ai_coach": true, "reports": true, "guardian": true, "journal_limit": 9999}'),
('pro_yearly', 'Pro Yearly', 399900, 'year', '{"max_patterns": 15, "history_days": 9999, "ai_coach": true, "reports": true, "guardian": true, "journal_limit": 9999}');

-- Indexes
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status  ON subscriptions(status);
CREATE INDEX idx_subscriptions_period  ON subscriptions(current_period_end);
CREATE INDEX idx_payment_txns_user     ON payment_transactions(user_id);
CREATE INDEX idx_payment_txns_sub      ON payment_transactions(subscription_id);
```

---

### S1-2: Subscription SQLAlchemy models

**File:** `backend/app/models/subscription.py`
```python
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from uuid import uuid4
from app.core.database import Base

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_key         = Column(String, unique=True, nullable=False)
    display_name     = Column(String, nullable=False)
    price_paise      = Column(Integer, nullable=False, default=0)
    billing_interval = Column(String, nullable=False)
    razorpay_plan_id = Column(String, nullable=True)
    features         = Column(JSONB, default=dict)
    is_active        = Column(Boolean, default=True)
    created_at       = Column(TIMESTAMP(timezone=True), server_default=text("now()"))


class Subscription(Base):
    __tablename__ = "subscriptions"
    id                       = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id                  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id                  = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False)
    status                   = Column(String, nullable=False, default="trialing")
    razorpay_subscription_id = Column(String, unique=True, nullable=True)
    razorpay_customer_id     = Column(String, nullable=True)
    current_period_start     = Column(TIMESTAMP(timezone=True), nullable=True)
    current_period_end       = Column(TIMESTAMP(timezone=True), nullable=True)
    trial_end                = Column(TIMESTAMP(timezone=True), nullable=True)
    cancel_at_period_end     = Column(Boolean, default=False)
    cancelled_at             = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at               = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at               = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    plan                     = relationship("SubscriptionPlan")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    subscription_id     = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)
    user_id             = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    razorpay_payment_id = Column(String, unique=True, nullable=True)
    razorpay_order_id   = Column(String, nullable=True)
    razorpay_invoice_id = Column(String, nullable=True)
    amount_paise        = Column(Integer, nullable=False)
    currency            = Column(String, default="INR")
    status              = Column(String, nullable=False)
    failure_reason      = Column(String, nullable=True)
    failure_code        = Column(String, nullable=True)
    refund_id           = Column(String, nullable=True)
    metadata            = Column(JSONB, default=dict)
    created_at          = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
```

---

### S1-3: BillingService

**File:** `backend/app/services/billing_service.py`
```python
"""
Billing Service — Razorpay subscription management.

Key methods:
  get_or_create_subscription(user_id)  → current Subscription
  create_razorpay_subscription(...)    → Razorpay subscription object
  cancel_subscription(user_id)
  get_plan_features(user_id)           → dict of features user can access
  is_pro(user_id)                      → bool
  handle_webhook(event, payload)       → process Razorpay webhook
"""
import razorpay
import hmac, hashlib, logging
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.models.subscription import Subscription, SubscriptionPlan, PaymentTransaction
from app.models.user import User

logger = logging.getLogger(__name__)

FREE_FEATURES = {
    "max_patterns": 5,
    "history_days": 30,
    "ai_coach": False,
    "reports": False,
    "guardian": False,
    "journal_limit": 10,
}

PRO_FEATURES = {
    "max_patterns": 15,
    "history_days": 9999,
    "ai_coach": True,
    "reports": True,
    "guardian": True,
    "journal_limit": 9999,
}


class BillingService:
    def __init__(self):
        if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
            self.client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
        else:
            self.client = None
            logger.warning("Razorpay not configured — billing in safe mode")

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    async def get_active_subscription(
        self, user_id: UUID, db: AsyncSession
    ) -> Subscription | None:
        result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .where(Subscription.status.in_(["active", "trialing", "past_due"]))
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_plan_features(self, user_id: UUID, db: AsyncSession) -> dict:
        """Return the feature dict for the user's current plan."""
        sub = await self.get_active_subscription(user_id, db)
        if not sub:
            return FREE_FEATURES
        if sub.status == "past_due":
            # Grace period: still has pro features for 7 days
            grace_end = sub.current_period_end + timedelta(days=7)
            if datetime.now(timezone.utc) < grace_end:
                return PRO_FEATURES
            return FREE_FEATURES
        return PRO_FEATURES if sub.status in ("active", "trialing") else FREE_FEATURES

    async def is_pro(self, user_id: UUID, db: AsyncSession) -> bool:
        features = await self.get_plan_features(user_id, db)
        return features.get("ai_coach", False)

    async def create_free_trial(
        self, user_id: UUID, db: AsyncSession
    ) -> Subscription:
        """Called when user first connects broker. 14-day Pro trial."""
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.plan_key == "pro_monthly")
        )
        pro_plan = result.scalar_one_or_none()
        if not pro_plan:
            raise ValueError("pro_monthly plan not seeded in DB")

        trial_end = datetime.now(timezone.utc) + timedelta(days=14)
        sub = Subscription(
            user_id=user_id,
            plan_id=pro_plan.id,
            status="trialing",
            trial_end=trial_end,
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        logger.info(f"Free trial created for user {user_id}, ends {trial_end.date()}")
        return sub

    async def create_razorpay_subscription(
        self,
        user_id: UUID,
        plan_key: str,  # 'pro_monthly' or 'pro_yearly'
        db: AsyncSession,
    ) -> dict:
        """
        Create a Razorpay subscription. Returns the Razorpay subscription object
        (frontend uses subscription.short_url or embeds checkout).
        """
        if not self.is_configured:
            return {"error": "Billing not configured"}

        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.plan_key == plan_key)
        )
        plan = result.scalar_one_or_none()
        if not plan or not plan.razorpay_plan_id:
            raise ValueError(f"Plan {plan_key} not found or missing razorpay_plan_id")

        user = await db.get(User, user_id)

        rp_sub = self.client.subscription.create({
            "plan_id": plan.razorpay_plan_id,
            "customer_notify": 1,
            "total_count": 12 if plan.billing_interval == "month" else 1,
            "notes": {
                "user_id": str(user_id),
                "plan_key": plan_key,
            },
        })

        # Save locally
        sub = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            status="created",
            razorpay_subscription_id=rp_sub["id"],
        )
        db.add(sub)
        await db.commit()
        return rp_sub

    async def cancel_subscription(
        self, user_id: UUID, db: AsyncSession, at_period_end: bool = True
    ) -> bool:
        sub = await self.get_active_subscription(user_id, db)
        if not sub:
            return False

        if sub.razorpay_subscription_id and self.is_configured:
            self.client.subscription.cancel(
                sub.razorpay_subscription_id,
                {"cancel_at_cycle_end": 1 if at_period_end else 0},
            )

        sub.cancel_at_period_end = at_period_end
        if not at_period_end:
            sub.status = "cancelled"
            sub.cancelled_at = datetime.now(timezone.utc)
        await db.commit()
        return True

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """Verify Razorpay webhook signature."""
        if not settings.RAZORPAY_WEBHOOK_SECRET:
            return True  # safe mode
        expected = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def handle_webhook(
        self, event: str, payload: dict, db: AsyncSession
    ) -> bool:
        """Process Razorpay webhook events."""
        logger.info(f"Razorpay webhook: {event}")

        sub_data = payload.get("subscription", {})
        payment_data = payload.get("payment", {}) if "payment" in payload else {}
        rp_sub_id = sub_data.get("id") or payload.get("subscription_id")

        if not rp_sub_id:
            logger.warning(f"Webhook {event} has no subscription_id")
            return False

        result = await db.execute(
            select(Subscription).where(
                Subscription.razorpay_subscription_id == rp_sub_id
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            logger.warning(f"Subscription {rp_sub_id} not found locally")
            return False

        if event == "subscription.activated":
            sub.status = "active"
            sub.current_period_start = datetime.now(timezone.utc)

        elif event == "subscription.charged":
            sub.status = "active"
            # Record transaction
            payment = payment_data.get("entity", {})
            txn = PaymentTransaction(
                subscription_id=sub.id,
                user_id=sub.user_id,
                razorpay_payment_id=payment.get("id"),
                razorpay_order_id=payment.get("order_id"),
                razorpay_invoice_id=payment.get("invoice_id"),
                amount_paise=payment.get("amount", 0),
                status="captured",
            )
            db.add(txn)
            # TODO: send receipt email

        elif event == "subscription.halted":
            sub.status = "past_due"
            # TODO: send "payment failed" push + email

        elif event == "subscription.cancelled":
            sub.status = "cancelled"
            sub.cancelled_at = datetime.now(timezone.utc)

        elif event == "subscription.completed":
            sub.status = "expired"

        elif event == "payment.failed":
            payment = payment_data.get("entity", {})
            txn = PaymentTransaction(
                subscription_id=sub.id,
                user_id=sub.user_id,
                razorpay_payment_id=payment.get("id"),
                amount_paise=payment.get("amount", 0),
                status="failed",
                failure_reason=payment.get("error_description"),
                failure_code=payment.get("error_code"),
            )
            db.add(txn)

        await db.commit()
        return True


billing_service = BillingService()
```

---

### S1-4: Billing API endpoints

**File:** `backend/app/api/billing.py`

```python
"""
Billing API endpoints.

GET  /api/billing/plans             → list all active plans
GET  /api/billing/subscription      → current user's subscription + features
POST /api/billing/subscribe         → create Razorpay subscription
POST /api/billing/cancel            → cancel at period end
POST /api/billing/resume            → undo cancel_at_period_end
GET  /api/billing/invoices          → list payment history
POST /api/webhooks/razorpay         → Razorpay webhook handler
"""

# Key points for implementation:
# - All /api/billing/* require get_current_user_id dependency
# - /api/webhooks/razorpay is UNAUTHENTICATED (Razorpay calls it)
#   but MUST verify X-Razorpay-Signature header
# - Return 200 immediately from webhook, process async
# - Include plan features in GET /subscription response
#   so frontend can make gating decisions without extra calls
```

**Add to `backend/app/main.py`:**
```python
from app.api import billing
app.include_router(billing.router, prefix="/api/billing", tags=["billing"])
# Razorpay webhook goes on separate path (unauthenticated):
app.include_router(billing.webhook_router, prefix="/api/webhooks", tags=["webhooks"])
```

**Add to `requirements.txt`:**
```
razorpay>=1.3.0
```

---

### S1-5: FeatureGate component

**File:** `src/components/FeatureGate.tsx`

```tsx
/**
 * Wraps Pro-only features. Shows upgrade prompt for free users.
 *
 * Usage:
 *   <FeatureGate feature="ai_coach">
 *     <ChatPage />
 *   </FeatureGate>
 *
 *   <FeatureGate feature="guardian" inline>
 *     <GuardianSettings />
 *   </FeatureGate>
 */

// Features: 'ai_coach' | 'reports' | 'guardian' | 'portfolio_radar'
//           | 'full_analytics' | 'unlimited_history' | 'all_patterns'

// Data source: GET /api/billing/subscription returns
//   { status, plan_key, features: { ai_coach: bool, ... } }
// Cache in React Query with 5-min stale time.
//
// If features.ai_coach === false:
//   Show <UpgradePrompt feature="ai_coach" />
//   (a card with feature description + "Upgrade to Pro" button → /pricing)
// Else:
//   Render children
```

---

### S1-6: Pricing page

**File:** `src/pages/Pricing.tsx`

Key elements:
- Two plan cards: Free | Pro
- Toggle: Monthly / Yearly (yearly shows "Save 33%")
- Pro card highlighted with primary border + "Most Popular" badge
- Each card: feature list with ✓ / ✗ icons
- CTA button: "Start 14-day free trial" for Pro
- FAQ section below (5 questions about billing)
- Trust signals: "Cancel anytime · No hidden fees · GST invoice included"

---

### S1-7: Checkout flow

**File:** `src/pages/Checkout.tsx`

```
Route: /checkout?plan=pro_monthly (or pro_yearly)

Flow:
1. Page loads → POST /api/billing/subscribe → get Razorpay subscription_id
2. Load Razorpay checkout.js script
3. Open Razorpay modal with subscription_id
4. On success: redirect to /dashboard?welcome=pro
5. On failure: show error, retry option

Razorpay checkout options:
  key: RAZORPAY_KEY_ID
  subscription_id: from API
  name: "TradeMentor AI"
  description: "Pro Monthly Subscription"
  image: "/logo.png"
  prefill: { name, email, contact } (from account data)
  theme: { color: "#0d9488" }  (teal)
```

---

### S1-8: Billing section in Settings

**Add to `src/pages/Settings.tsx` — new "Billing" tab:**

```
Current Plan:  Pro Monthly   [Active]
Next billing:  15 April 2026 (₹499)
[Download Invoice] [Cancel Plan] [Upgrade to Yearly]

Past payments table:
Date | Plan | Amount | Status | Invoice
```

---

## SPRINT 2 — Authentication & Trust (Week 3)
### Goal: Guardian numbers are verified. Sensitive actions require confirmation.

---

### S2-1: Guardian phone OTP via WhatsApp

**Problem:** Any phone number can be added as guardian. That person gets unsolicited WhatsApp messages — TRAI violation risk.

**Solution:** When user adds a guardian number, send a WhatsApp message to that number asking for consent. Until they consent, guardian alerts are not sent.

**Migration 049:**
```sql
ALTER TABLE user_profiles
  ADD COLUMN guardian_verified         BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN guardian_pending_since    TIMESTAMPTZ,
  ADD COLUMN guardian_verification_code TEXT;  -- 6-digit code, cleared after use
```

**Backend flow:**
```python
# In profile.py, when guardian_phone is updated:
# 1. Set guardian_verified = False
# 2. Generate 6-digit code
# 3. Send WhatsApp: "TradeMentor: {user_name} wants you as trading guardian.
#    Your verification code is: {code}. Reply this code to confirm."
# 4. Store code in user_profile.guardian_verification_code

# New endpoint: POST /api/profile/verify-guardian
# Body: { code: "123456" }
# Action: if code matches, set guardian_verified = True, clear code
```

**Frontend:**
```
In Settings → Guardian section:
- If phone set but not verified: show yellow banner
  "Pending: Sent verification code to +91XXXXXXXXXX"
  [Enter code] input + [Verify] button
- If verified: green checkmark next to number
- If user changes number: reset to unverified
```

---

### S2-2: Email OTP for sensitive actions

**Actions that need OTP confirmation:**
1. Delete account
2. Cancel subscription
3. Change/remove guardian number (if already verified)
4. Download account data

**Backend:**
```python
# New endpoints:
# POST /api/auth/send-otp
#   Body: { action: "delete_account" | "cancel_subscription" | ... }
#   Action: generate 6-digit code, store in Redis with key
#           "otp:{user_id}:{action}" TTL 600s
#           Send via email_service.py

# POST /api/auth/verify-otp
#   Body: { action: "...", code: "123456" }
#   Action: check Redis, if match return signed confirmation token
#           (short-lived JWT claim for that specific action)
#   Use confirmation token in the actual destructive endpoint
```

**Redis key format:**
```
otp:{user_id}:{action}  →  "123456"  TTL: 600s
```

**Email template:** Already have `email_service.py`. Add method:
```python
async def send_otp_email(to: str, code: str, action: str) -> bool
```

---

### S2-3: On 2FA — What NOT to build

**Do not build TOTP (Google Authenticator) 2FA.**

Reason: Your only login method is Zerodha OAuth. Zerodha already requires their own
2FA (TOTP or SMS OTP) before their OAuth flow starts. You'd be adding 2FA on top of
2FA for no security benefit, while making login worse.

The email OTP for sensitive actions (S2-2) is sufficient. If you add email/password
login in the future, add TOTP then.

---

## SPRINT 3 — Landing Page (Week 4)
### Goal: Someone who finds TradeMentor via search/referral can understand it and sign up.

---

### S3-1: Expand Welcome.tsx into full landing page

The existing `/welcome` page is a stub. Expand it into a full marketing landing page.
**Keep it in the same React app** — don't build a separate Next.js site until you have
200+ users and SEO becomes a priority.

**Page sections to build:**

```
1. NAVBAR
   - Logo (left)
   - Links: Features | Pricing | Blog (optional) | FAQ
   - Right: [Login] button (secondary) + [Get Started Free] (primary, links to /welcome#cta)
   - Mobile: hamburger → full-screen overlay

2. HERO
   Headline: "Your trades are good. Your brain isn't."
   Sub: "TradeMentor analyses your real Zerodha trades to detect the
        behavioural patterns that cost Indian F&O traders ₹2,00,000+/year.
        Mirror, not blocker."
   Primary CTA: [Connect Zerodha — 14 days free]
   Secondary: [See a demo] (→ /dashboard in guest mode)
   Social proof bar: "Based on SEBI's finding that 89% of F&O traders lose money"
   Hero image/animation: mockup of dashboard or pattern detection card

3. PROBLEM SECTION
   Three-column cards:
   - "₹2.3L avg annual loss for retail F&O trader" (SEBI FY2023)
   - "73% of revenge trades placed within 15min of a loss"
   - "3 consecutive losses = measurable emotional impairment"
   Bottom line: "The market isn't your enemy. Your psychology is."

4. HOW IT WORKS (3 steps)
   Step 1 → Connect your Zerodha account (read-only, no trades placed)
   Step 2 → We analyse every trade for 15 behavioural patterns
   Step 3 → You see the patterns clearly and can change them

5. FEATURES GRID (6 cards)
   Behavioral Detection | AI Coach | Real-time Alerts |
   Daily Reports | Blowup Shield | Portfolio Radar

6. PATTERN SHOWCASE (the "aha moment")
   Show 4-5 pattern cards with Indian F&O context:
   - Revenge Trading: "You re-entered BANKNIFTY 8 minutes after a ₹3,200 loss"
   - Overtrading: "23 trades on Thursday. Your average: 7."
   - FOMO: "Entered NIFTY 50PE at open gap-up — 11 times this month"
   - Loss Aversion: "Held losing positions 4× longer than winning ones"

7. PRICING (same as /pricing but embedded)
   Free | Pro Monthly (₹499) | Pro Yearly (₹3,999/yr — save 33%)
   Include 14-day free trial callout

8. TESTIMONIALS
   Placeholder for now. Add 3 real ones from beta users before launch.
   Format: photo | name (first name only) | city | quote

9. FAQ (8 questions)
   See S3-2 below for exact questions

10. FINAL CTA BANNER
    "Start understanding your trading psychology today"
    [Connect Zerodha — Free for 14 days]

11. FOOTER (see S3-3)
```

---

### S3-2: FAQ content

```
Q: Is this investment advice?
A: No. TradeMentor is a behavioural analytics tool. We analyse patterns in
   your own trades — we never recommend what to buy, sell, or hold.
   We are not a SEBI-registered Investment Adviser or Research Analyst.

Q: Does TradeMentor place trades on my behalf?
A: Never. We have read-only access to your Zerodha trade history.
   We cannot and do not place, modify, or cancel any orders.

Q: Is my trading data safe?
A: Yes. Your Zerodha password is never shared with us — you authenticate
   directly with Zerodha's OAuth. Your trade data is encrypted at rest
   (AES-256) and in transit (TLS). See our Privacy Policy for full details.

Q: Which broker accounts work with TradeMentor?
A: Currently Zerodha only. Angel One, Upstox support is on our roadmap.

Q: What's the difference between Free and Pro?
A: Free gives you the dashboard and basic analytics (last 30 days, 5 patterns).
   Pro unlocks all 15 behavioural detectors, the AI Coach, daily WhatsApp/email
   reports, Guardian mode, Portfolio Radar, and unlimited trade history.

Q: Can I cancel anytime?
A: Yes. Cancel from Settings and your Pro access continues until end of the
   paid period. No penalty. 7-day money-back guarantee on first payment.

Q: Will this work for options traders?
A: Yes — TradeMentor is built specifically for Indian F&O traders. It understands
   option legs, premium averaging, IV crush behaviour, and expiry-day patterns.

Q: I trade on multiple exchanges. Does that matter?
A: TradeMentor reads whatever Zerodha reports — NSE, BSE, MCX, NFO, BFO.
   Commodity traders get a separate MCX market-close report at 11:45 PM.
```

---

### S3-3: Footer — full structure

**File:** `src/components/LandingFooter.tsx`

```
[Logo] TradeMentor AI
"A trading psychology platform for Indian F&O traders"
[Twitter/X] [LinkedIn] [YouTube] [WhatsApp support]

PRODUCT          RESOURCES        LEGAL            COMPANY
Features         Help Center      Terms of Service  About Us
Pricing          Blog             Privacy Policy    Contact
Changelog        API Status       Disclaimer        Careers
Roadmap          Contact Support  Refund Policy     Press Kit

---
© 2026 TradeMentor AI. All rights reserved.
Not investment advice. TradeMentor AI is not a SEBI-registered Investment Adviser.
Built for Indian F&O traders.
```

**Social media links to create before launch:**
- Twitter/X: @TradeMentorAI
- LinkedIn: company page
- YouTube: channel for screen recording demos (even 1 video is fine)

---

### S3-4: Additional legal pages needed

**Refund Policy** — `src/pages/RefundPolicy.tsx`
```
7-day money-back guarantee on first payment, no questions asked.
After 7 days, refunds at our discretion for technical failures.
To request: email billing@tradementor.ai with order ID.
Razorpay will credit within 5-7 business days.
```

**Cookie Policy** — `src/pages/CookiePolicy.tsx`
```
We use browser localStorage (not cookies) for:
- Authentication token (JWT)
- App preferences (theme, notification settings)
- Onboarding state

We do NOT use:
- Tracking cookies
- Advertising cookies
- Third-party analytics cookies
- Google Analytics
```

**Add all pages to App.tsx routes:**
```tsx
<Route path="refund-policy" element={<RefundPolicy />} />
<Route path="cookie-policy" element={<CookiePolicy />} />
<Route path="about" element={<About />} />  // future
```

---

## SPRINT 4 — Admin Panel (Week 5)
### Goal: You can manage your own product without touching the database.

---

### S4-1: Admin model + middleware

**Add to `User` model:**
```sql
ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE;
```

**Backend middleware:**
```python
# New dependency: get_admin_user
async def get_admin_user(current_user = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")
    return current_user
```

---

### S4-2: Admin API endpoints

**File:** `backend/app/api/admin.py`

```
GET  /api/admin/users              → paginated user list with plan status
GET  /api/admin/users/{id}         → single user detail
POST /api/admin/users/{id}/grant-pro → manually grant Pro (for influencers)
GET  /api/admin/metrics            → MRR, churn, DAU, trial conversion rate
GET  /api/admin/subscriptions      → subscription list with status
POST /api/admin/refund             → trigger Razorpay refund
GET  /api/admin/alerts/volume      → alert volume last 7 days
```

---

### S4-3: Admin frontend

**File:** `src/pages/Admin.tsx`

- Password-protected route (admin JWT check)
- User table: email | plan | status | joined | last active | [Actions]
- Metrics cards: MRR | Active subscribers | Trial conversions | Churn rate
- Add to App.tsx outside main Layout (separate admin layout)
- **Do not add to the sidebar navigation** — admin shouldn't be visible to users

---

## SPRINT 5 — Growth Infrastructure (Week 6–8)
### Goal: Automated retention and growth.

---

### S5-1: Trial expiry email sequence

**File:** `backend/app/tasks/billing_tasks.py`

```python
# Beat task: runs daily at 9:00 AM IST
@celery_app.task
def send_trial_expiry_emails():
    """
    Check for trials expiring in 2 days → send Day-12 warning email
    Check for trials expired yesterday → send Day-15 downgrade email
    """
    pass

# Email content (use email_service.py):
# Day 12: "2 days left on your Pro trial — here's what you've learned"
#   Include: patterns detected, estimated cost avoided, features they used
#
# Day 14: "Your Pro trial ends tonight"
#   Include: specific data + big CTA button + "14 days free — no commitment"
#
# Day 15: "Your account is now on Free"
#   Include: what they lost, upgrade button
#   Tone: factual, not pushy — this is behavioral psychology, walk the talk
```

---

### S5-2: Failed payment recovery (dunning)

**Beat task:**
```python
@celery_app.task
def process_dunning():
    """
    For subscriptions with status=past_due:
    - Day 1: push notification + email "Payment failed, retry"
    - Day 3: email "Action required"
    - Day 7: downgrade to free, final email
    """
```

---

### S5-3: PostHog product analytics

**Installation — 2 lines:**

`index.html` (in `<head>`):
```html
<script>
  !function(t,e){...}(window,document,"posthog","https://app.posthog.com",{api_host:'https://app.posthog.com'});
  posthog.init('YOUR_PROJECT_API_KEY');
</script>
```

**Key events to track:**
```typescript
// In src/main.tsx or analytics wrapper:
posthog.capture('user_connected_broker')
posthog.capture('ai_coach_message_sent')
posthog.capture('pattern_detected', { pattern_type })
posthog.capture('upgrade_prompt_shown', { feature })
posthog.capture('upgrade_button_clicked', { feature, plan })
posthog.capture('subscription_started', { plan_key })
```

**Why PostHog:** Open source, GDPR/DPDP compliant, self-hostable, free <1M events/month.

---

### S5-4: PWA install prompt

The app is already a PWA (has `sw.js`). Add a Web App Install prompt.

**File:** `src/components/InstallPrompt.tsx`
```
- Listen for `beforeinstallprompt` event
- Show a dismissable bottom banner after 3 days of use:
  "Add TradeMentor to your home screen"
  [Add to Home Screen] [Later]
- On mobile Safari: show manual instruction popup
- Store "dismissed" in localStorage, never show again if dismissed
```

---

### S5-5: Data export (DPDP right to portability)

**File:** `backend/app/api/account.py` (or `danger_zone.py`)

```python
# POST /api/account/export-data
# Generates a ZIP containing:
# - trades.csv
# - positions.csv
# - journal_entries.csv
# - behavioral_alerts.csv
# - profile.json
# - reports.json
# Returns download URL (pre-signed Supabase Storage URL, 1hr TTL)
```

---

### S5-6: Social share card

**File:** `src/components/ShareCard.tsx`

```
"This month I avoided ₹12,400 in revenge trades 🧠"
"TradeMentor detected 4 patterns in my trading this week"

Features:
- Pre-fills with real user's data from the "money saved" metric
- Share button opens native share sheet (mobile) or copies text (desktop)
- Links back to tradementor.ai
- Optional: OG image generation (use Vercel OG or Cloudinary)
```

---

## SPRINT 6 — Pre-Launch Checklist (Week 8–9)
### Goal: Everything is ready for first 100 real users.

---

### Technical

- [ ] All migrations applied to production Supabase
- [ ] Razorpay live credentials (not test) in production .env
- [ ] Twilio credentials configured (WhatsApp + OTP)
- [ ] SMTP configured (email reports)
- [ ] VAPID keys generated + configured
- [ ] Sentry DSN configured
- [ ] Redis (Upstash) configured for production
- [ ] CORS origins updated to production domain
- [ ] `ENVIRONMENT=production` set (disables debug logs)
- [ ] SSL certificate on domain
- [ ] Celery beat running (scheduled reports + dunning)
- [ ] Health check endpoint returns 200 (`/health`)
- [ ] Uptime monitoring: Upptime or Better Uptime (free tier)
- [ ] Error rate monitoring: Sentry alerts configured

### Business / Legal

- [ ] Lawyer-reviewed ToS and Privacy Policy
- [ ] Razorpay business KYC approved
- [ ] GSTIN registered (or decide to not charge GST initially)
- [ ] Refund Policy live
- [ ] Support email configured (support@tradementor.ai)
- [ ] At least 3 real testimonials from beta users
- [ ] Demo video recorded (3 minutes)
- [ ] 5 beta users onboarded and active

### Zerodha Specifically

- [ ] Read Zerodha KiteConnect developer agreement fully
- [ ] Apply for KiteConnect publisher programme (for multi-account support)
- [ ] Confirm data usage complies with their ToS (read-only, no automated trading)
- [ ] Prepare 1-page tech brief for Zerodha BD team

---

## Open Architectural Decisions

Document these decisions before building.

### Q1: Will you support non-Zerodha users?
**If YES:** Need email/password or phone/OTP signup flow.
**If NO:** Zerodha OAuth is your only login — simpler, but limits TAM.
**Recommendation:** Zerodha-only for first 6 months. Build multi-broker after PMF.

### Q2: Where is your production database hosted?
**Current:** Supabase — check if it's on `ap-south-1` (AWS Mumbai).
**Why it matters:** SEBI prefers India-resident data. Some enterprise clients will require it.
**Action:** Supabase dashboard → Settings → Infrastructure → confirm region.

### Q3: Mobile app — when?
**Short answer:** Not now. Your web app is already a PWA (installable).
**When to build native:** After 500 active users. Revenue justifies native app development.
**Stack when you do:** React Native (reuse component logic) or Flutter.

### Q4: Sensibull partnership
**What they want:** Integration with their option strategy builder.
**What you'd get:** Distribution to their 500k+ users.
**What to build:** Webhook API that Sensibull can call when strategy is executed.
**Timeline:** After payments are live and you have a product to show.

---

## Technology Decisions Already Made (Don't Revisit)

| Decision | Choice | Reason |
|----------|--------|--------|
| Payment gateway | Razorpay only (NOT RevenueCat) | RevenueCat is for native app stores |
| 2FA | Email OTP only for sensitive actions | Zerodha OAuth is already 2FA |
| Analytics | PostHog | DPDP compliant, self-hostable, free |
| Guardian verification | WhatsApp inbound reply | Already have Twilio |
| Landing page | Expand existing React app | Avoid two deployments |
| Multi-broker | Not yet | Zerodha PMF first |

---

## Dependency Map

```
SPRINT 0 (Run app, Razorpay account, feature decision)
    ↓
SPRINT 1 (Payments) — CANNOT start without Razorpay account approval
    ↓
SPRINT 2 (Auth/OTP) — CANNOT start guardian verify without knowing Twilio is set up
    ↓
SPRINT 3 (Landing page) — CAN start in parallel with Sprint 2
    ↓
SPRINT 4 (Admin panel) — NEEDS payments to show subscription data
    ↓
SPRINT 5 (Growth) — NEEDS all above
    ↓
SPRINT 6 (Launch checklist) — Final gate
```

---

## Estimated Timeline

| Sprint | Duration | Gate to proceed |
|--------|----------|-----------------|
| Sprint 0 | 1–3 days | App runs E2E, Razorpay approved |
| Sprint 1 | 7–10 days | Payments flowing (test mode) |
| Sprint 2 | 4–5 days | Guardian verify + OTP working |
| Sprint 3 | 5–7 days | Landing page + footer complete |
| Sprint 4 | 3–4 days | Admin panel functional |
| Sprint 5 | 7–10 days | Trial emails, PostHog, install prompt |
| Sprint 6 | 2–3 days | All checklist items green |
| **Total** | **~6–7 weeks** | **Ready for first 100 paying users** |

---

## What This Plan Does NOT Cover

Intentionally deferred — not needed for first 100 users:

- Native iOS/Android app
- Multi-broker support (Angel One, Upstox)
- Referral programme
- Broker affiliate revenue sharing
- Public API / webhooks for third-party integrations
- Enterprise/team plans
- Sensibull / Zerodha deep integration
- Read replica for analytics queries (needed at ~1,000 users)
- Shared KiteTicker (needs Zerodha partnership)
- CSP nonce hardening (current `unsafe-inline` is acceptable for MVP)

---

*End of document. Update status fields as items complete.*
*Next: Start Sprint 0 — run the app, find the bugs, fix them.*
