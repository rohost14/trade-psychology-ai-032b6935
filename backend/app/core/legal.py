"""
Terms of Service versioning.

Acceptance is recorded per user (`users.terms_accepted_at` / `users.terms_version`)
rather than held in browser state. The landing page used to gate its Connect button
behind a React `useState` checkbox: it reset on every page load, so — because Kite
tokens expire daily — the user re-ticked it every single day, and nothing was ever
persisted. If anyone had asked "prove this user accepted your terms", there was
nothing to show.

Acceptance now happens in two places, both explicit:

  1. OAuth callback — clicking "Connect Zerodha" IS the acceptance (clickwrap by
     action, the standard pattern for broker-connected apps in India). Stamped only
     when no acceptance exists yet, so it never silently overwrites an older
     version — that would destroy the signal (2) depends on.

  2. POST /api/legal/accept — an explicit re-acceptance after the terms change,
     driven by the one-time interstitial.

BUMPING THE VERSION: change CURRENT_TERMS_VERSION only for a MATERIAL change to
TermsOfService.tsx or PrivacyPolicy.tsx — a change to what data is collected, what
the service does, liability, or the user's rights. Every logged-in user is shown a
blocking interstitial on their next page load, so a bump for a typo fix trains
people to dismiss the one that matters. Date-stamped so the accepted value is
self-describing in the database.
"""

CURRENT_TERMS_VERSION = "2026-08-04"


def needs_reacceptance(accepted_version: str | None) -> bool:
    """
    Should this user be shown the terms-changed interstitial?

    Only when they HAVE accepted something and it is not the current version.

    A NULL acceptance deliberately returns False. Those users predate migration
    078; they are stamped at their next OAuth login, where pressing the button is
    itself the acceptance. Prompting them as well would ask twice for the same
    thing — and would put a blocking modal in front of every existing user the
    moment this shipped, which is precisely the daily-friction problem being fixed.
    """
    return bool(accepted_version) and accepted_version != CURRENT_TERMS_VERSION
