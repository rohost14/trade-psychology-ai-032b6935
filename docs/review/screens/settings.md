# Settings Screen Review

**Status:** 6/6 FIXED
**Session:** 7 (2026-02-24)

---

## Issues Found

| ID | Severity | Description | Status |
|----|----------|-------------|--------|
| S1 | HIGH | Risk Limits tab duplicates Goals — remove per rearchitecture decision | FIXED (removed) |
| S2 | HIGH | `whatsapp_enabled` flag stored but never checked before sending | FIXED |
| S3 | HIGH | No UI indicator that WhatsApp/Twilio is not configured | FIXED |
| S4 | MEDIUM | "Test Message" button triggers full intervention (cooldown + escalation) | FIXED |
| S5 | MEDIUM | 5 confusing tabs with overlap — restructure to 2 | FIXED |
| S6 | LOW | `settings.py` error leakage: `detail=str(e)` | FIXED |

---

## Fixes Applied

### S1 + S5: Tab restructure (5 → 2)
**File:** `src/pages/Settings.tsx`
- **Profile tab:** Display name, experience, trading style, risk tolerance, trading hours, AI persona selection
- **Notifications tab:** Alert sensitivity, push notifications (existing component), WhatsApp reports toggle, Guardian Mode (full block)
- **Removed:** Risk Limits tab (duplicated Goals, per rearchitecture plan), AI Coach tab (split into Profile + Notifications), Guardian tab (merged into Notifications), Alerts tab (merged into Notifications)
- Data fields preserved in profile state and save payload — only UI removed
- Removed unused imports: `Target`, `Wallet`, `TrendingUp`, `Slider`, `SettingsIcon`

### S2: Guardian enabled check
**File:** `backend/app/services/danger_zone_service.py`
- `_send_whatsapp_notification` now checks `profile.guardian_enabled` before sending
- If guardian not enabled, returns False immediately (no notification sent)

### S3: WhatsApp status indicator
**Files:** `backend/app/api/profile.py`, `src/pages/Settings.tsx`
- New endpoint: `GET /api/profile/notification-status` returns `{whatsapp: {twilio_configured}, push: {vapid_configured}}`
- Frontend fetches on mount, shows amber banner when Twilio not configured
- Uses `whatsapp_service.is_configured` property (new)

### S4: Guardian test message
**Files:** `backend/app/api/profile.py`, `src/pages/Settings.tsx`
- New endpoint: `POST /api/profile/guardian/test` — sends benign test message via WhatsApp
  - Returns 503 if Twilio not configured (with clear error)
  - Returns 400 if no guardian phone set
  - No cooldown/escalation triggered
- Frontend button changed from `/api/danger-zone/trigger-intervention` to `/api/profile/guardian/test`
- Handles 503 with descriptive toast

### S6: Error leakage fix
**File:** `backend/app/api/settings.py`
- `str(e)` → `"Failed to update guardian settings"` (line 55)

---

## Architecture Notes
- `whatsapp_service.is_configured` property added to `backend/app/services/whatsapp_service.py`
- Profile state and save payload still include all fields (daily_loss_limit, etc.) — only UI removed
- Risk Limits will resurface in future "My Patterns" rearchitecture (goals-dangerzone-merge plan)
