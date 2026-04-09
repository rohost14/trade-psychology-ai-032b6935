# Onboarding — Screen Review

**Status**: REVIEWED (session 15, 2026-03-07)
**Reviewer**: Claude Code

---

## Scope

- `src/components/onboarding/OnboardingWizard.tsx` — 5-step wizard UI
- `src/hooks/useOnboarding.ts` — onboarding state management
- `backend/app/api/profile.py` — `needs_onboarding` flag + profile write
- Integration: shown in Dashboard when `showOnboarding` is true

---

## Flow

1. User connects Zerodha (OAuth)
2. Dashboard loads → `useOnboarding()` → `GET /api/profile/`
3. If `profile.onboarding_completed == false` → show `OnboardingWizard`
4. Wizard collects: name, experience, style, risk tolerance, instruments, trading hours, position limits, cooldown, weaknesses, notification prefs, guardian, AI persona
5. On complete → `POST /api/profile/onboarding/complete` → sets `onboarding_completed = true`
6. Skip → hides wizard, doesn't mark complete (shows again on next login)

---

## Observations (No Fix Required)

### ON-01 — Onboarding shown in Dashboard (may be better as overlay/modal)
The wizard is rendered inline in Dashboard.tsx when `showOnboarding=true`. This means all dashboard data loads behind the wizard. Not a bug, but a UX consideration — a full-screen overlay might be cleaner.

### ON-02 — Skip doesn't persist
Skipping onboarding only sets local state to `false`. Next login triggers it again. This is intentional — the backend `needs_onboarding` flag is only cleared when `onboarding/complete` is called. Users who skip always see it on login until they complete it. This creates some friction but ensures profile completeness.

### ON-03 — Default AI persona not applied
During onboarding, if user doesn't set `ai_persona`, it defaults to the backend fallback. The `PatternConfig` and behavioral thresholds use `UserProfile.trading_style` and `experience_level`. If onboarding is skipped, these fields are null and the system falls back to COLD_START_DEFAULTS. This is the correct and expected behavior.

---

## Status

| ID | Issue | Severity | Fixed |
|----|-------|----------|-------|
| ON-01 | Wizard in Dashboard vs overlay | LOW | Design choice |
| ON-02 | Skip doesn't persist across sessions | LOW | Intentional |
| ON-03 | No defaults from skipped onboarding | LOW | Handled by cold-start defaults |
