"""
Terms acceptance is recorded against the user, not held in browser state.

The landing page used to gate its Connect button behind a React `useState`
checkbox. It reset on every page load, and because Kite access tokens expire
daily, the user re-ticked the same box every single day while nothing was ever
persisted — there was no answer to "prove this user accepted the terms".

The rule that matters, and the one these tests pin: a user who has accepted
NOTHING must not be prompted. Getting that wrong puts a blocking modal in front
of every existing user the moment it ships, which is the same daily-friction
problem in a new costume. Those users are stamped at their next OAuth login,
where pressing the button IS the acceptance.
"""

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.legal import CURRENT_TERMS_VERSION, needs_reacceptance
from app.models.user import User


class TestReacceptanceRule:
    """Pure — no DB."""

    def test_current_version_is_not_prompted(self):
        assert needs_reacceptance(CURRENT_TERMS_VERSION) is False

    def test_older_version_is_prompted(self):
        assert needs_reacceptance("2020-01-01") is True

    def test_never_accepted_is_not_prompted(self):
        """Stamped at next login instead. Prompting would ask twice."""
        assert needs_reacceptance(None) is False

    def test_empty_string_is_not_prompted(self):
        """A blank column is 'unknown', not 'accepted something old'."""
        assert needs_reacceptance("") is False


class TestAcceptancePersists:

    async def test_new_user_carries_an_acceptance_stamp(self, db):
        """
        What the OAuth callback writes for a brand-new user. The point is that a
        row exists at all — the checkbox never left one.
        """
        u = User(
            email=f"terms_{datetime.now(timezone.utc).timestamp()}@qa.internal",
            display_name="Terms QA",
            terms_accepted_at=datetime.now(timezone.utc),
            terms_version=CURRENT_TERMS_VERSION,
        )
        db.add(u)
        await db.flush()

        stored = (await db.execute(select(User).where(User.id == u.id))).scalar_one()
        assert stored.terms_accepted_at is not None
        assert stored.terms_version == CURRENT_TERMS_VERSION
        assert needs_reacceptance(stored.terms_version) is False

    async def test_user_on_an_old_version_is_flagged(self, db):
        u = User(
            email=f"terms_old_{datetime.now(timezone.utc).timestamp()}@qa.internal",
            display_name="Terms QA old",
            terms_accepted_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            terms_version="2025-01-01",
        )
        db.add(u)
        await db.flush()

        stored = (await db.execute(select(User).where(User.id == u.id))).scalar_one()
        assert needs_reacceptance(stored.terms_version) is True

    async def test_pre_migration_user_is_null_not_prompted(self, db):
        """Existing rows were deliberately NOT backfilled — see migration 078."""
        u = User(
            email=f"terms_null_{datetime.now(timezone.utc).timestamp()}@qa.internal",
            display_name="Terms QA null",
        )
        db.add(u)
        await db.flush()

        stored = (await db.execute(select(User).where(User.id == u.id))).scalar_one()
        assert stored.terms_accepted_at is None
        assert stored.terms_version is None
        assert needs_reacceptance(stored.terms_version) is False
