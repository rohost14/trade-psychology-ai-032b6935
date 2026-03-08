"""
Database Schema QA Tests
========================

Validates every table's:
  - Columns & data types
  - Primary keys
  - Foreign key relationships (including missing ones flagged as issues)
  - Unique constraints
  - NOT NULL constraints
  - CASCADE delete chains
  - Data integrity across the 3-layer trade architecture

Run:
    cd backend
    pytest tests/test_db_schema.py -v

All test rows use the prefix TEST_ / test_schema_qa_ and are rolled back
after each test — no permanent data is written.
"""

import pytest
from uuid import uuid4
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade
from app.models.completed_trade_feature import CompletedTradeFeature
from app.models.position import Position
from app.models.risk_alert import RiskAlert
from app.models.alert_checkpoint import AlertCheckpoint
from app.models.journal_entry import JournalEntry
from app.models.cooldown import Cooldown
from app.models.goal import Goal, CommitmentLog, StreakData
from app.models.user_profile import UserProfile
from app.models.behavioral_event import BehavioralEvent
from app.models.holding import Holding
from app.models.order import Order
from app.models.margin_snapshot import MarginSnapshot
from app.models.push_subscription import PushSubscription
from app.models.incomplete_position import IncompletePosition
from app.models.instrument import Instrument

from tests.helpers import now_utc, uid, make_email


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 1 — TABLE EXISTENCE & COLUMN CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTableExistence:
    """Verify every expected table is present in the database."""

    EXPECTED_TABLES = [
        "users",
        "broker_accounts",
        "trades",
        "completed_trades",
        "completed_trade_features",
        "positions",
        "risk_alerts",
        "alert_checkpoints",
        "journal_entries",
        "cooldowns",
        "trading_goals",
        "commitment_logs",
        "streak_data",
        "user_profiles",
        "behavioral_events",
        "holdings",
        "orders",
        "margin_snapshots",
        "push_subscriptions",
        "incomplete_positions",
        "instruments",
    ]

    @pytest.mark.asyncio
    async def test_all_tables_exist(self, db):
        result = await db.execute(
            text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
            """)
        )
        existing = {row[0] for row in result.fetchall()}
        missing = [t for t in self.EXPECTED_TABLES if t not in existing]
        assert not missing, f"Missing tables in DB: {missing}"

    @pytest.mark.asyncio
    async def test_users_columns(self, db):
        result = await db.execute(
            text("""
                SELECT column_name, is_nullable, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users'
                ORDER BY ordinal_position
            """)
        )
        cols = {row[0]: {"nullable": row[1], "type": row[2]} for row in result.fetchall()}
        assert "id" in cols
        assert "email" in cols
        assert "guardian_phone" in cols
        assert "guardian_name" in cols
        assert cols["email"]["nullable"] == "NO", "users.email must be NOT NULL"
        assert cols["id"]["nullable"] == "NO", "users.id must be NOT NULL (PK)"

    @pytest.mark.asyncio
    async def test_broker_accounts_has_user_id_not_null(self, db):
        result = await db.execute(
            text("""
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'broker_accounts'
                  AND column_name = 'user_id'
            """)
        )
        row = result.fetchone()
        assert row is not None, "broker_accounts.user_id column missing"
        assert row[1] == "NO", "broker_accounts.user_id must be NOT NULL"

    @pytest.mark.asyncio
    async def test_broker_accounts_guardian_columns_removed(self, db):
        """guardian_phone/name must NOT exist on broker_accounts (moved to users)."""
        result = await db.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'broker_accounts'
                  AND column_name IN ('guardian_phone', 'guardian_name')
            """)
        )
        leftover = [row[0] for row in result.fetchall()]
        assert not leftover, (
            f"broker_accounts still has guardian columns: {leftover}. "
            "They should be on the users table only."
        )

    @pytest.mark.asyncio
    async def test_alert_checkpoints_columns(self, db):
        result = await db.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'alert_checkpoints'
            """)
        )
        cols = {row[0] for row in result.fetchall()}
        required = {"id", "alert_id", "broker_account_id", "positions_snapshot",
                    "pnl_at_t5", "pnl_at_t30", "pnl_at_t60", "money_saved",
                    "calculation_status", "created_at"}
        missing = required - cols
        assert not missing, f"alert_checkpoints missing columns: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 2 — FOREIGN KEY CONSTRAINTS IN DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

class TestForeignKeys:
    """Verify FK constraints exist in PostgreSQL (not just in SQLAlchemy models)."""

    @pytest.mark.asyncio
    async def test_broker_accounts_fk_to_users(self, db):
        result = await db.execute(
            text("""
                SELECT kcu.column_name, ccu.table_name AS foreign_table
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = 'broker_accounts'
                  AND kcu.column_name = 'user_id'
            """)
        )
        row = result.fetchone()
        assert row is not None, "FK broker_accounts.user_id → users.id NOT FOUND in DB"
        assert row[1] == "users", f"FK points to '{row[1]}' instead of 'users'"

    @pytest.mark.asyncio
    async def test_trades_fk_to_broker_accounts(self, db):
        result = await db.execute(
            text("""
                SELECT kcu.column_name, ccu.table_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = 'trades'
                  AND kcu.column_name = 'broker_account_id'
            """)
        )
        row = result.fetchone()
        assert row is not None, "FK trades.broker_account_id → broker_accounts.id NOT FOUND"

    @pytest.mark.asyncio
    async def test_alert_checkpoints_fk_to_risk_alerts(self, db):
        result = await db.execute(
            text("""
                SELECT kcu.column_name, ccu.table_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = 'alert_checkpoints'
                  AND kcu.column_name = 'alert_id'
            """)
        )
        row = result.fetchone()
        assert row is not None, "FK alert_checkpoints.alert_id → risk_alerts.id NOT FOUND"
        assert row[1] == "risk_alerts"

    @pytest.mark.asyncio
    async def test_completed_trade_features_fk_to_completed_trades(self, db):
        result = await db.execute(
            text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = 'completed_trade_features'
                  AND kcu.column_name = 'completed_trade_id'
            """)
        )
        row = result.fetchone()
        assert row is not None, "FK completed_trade_features.completed_trade_id NOT FOUND"

    @pytest.mark.asyncio
    async def test_trade_user_id_column_dropped(self, db):
        """
        FIXED (migration 033): trades.user_id was a nullable UUID with no FK.
        Column has been dropped — user is reachable via broker_account_id → users.
        """
        result = await db.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'trades'
                  AND column_name = 'user_id'
            """)
        )
        row = result.fetchone()
        assert row is None, (
            "trades.user_id column still exists — run migration 033 to drop it"
        )

    @pytest.mark.asyncio
    async def test_risk_alert_user_id_column_dropped(self, db):
        """
        FIXED (migration 033): risk_alerts.user_id was a nullable UUID with no FK.
        Column has been dropped — user is reachable via broker_account_id → users.
        """
        result = await db.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'risk_alerts'
                  AND column_name = 'user_id'
            """)
        )
        row = result.fetchone()
        assert row is None, (
            "risk_alerts.user_id column still exists — run migration 033 to drop it"
        )

    @pytest.mark.asyncio
    async def test_risk_alert_trigger_trade_id_set_null_on_delete(self, db):
        """
        FIXED (migration 033): trigger_trade_id FK now uses ON DELETE SET NULL.
        Deleting a Trade nullifies the reference on the alert rather than blocking.
        """
        result = await db.execute(
            text("""
                SELECT rc.delete_rule
                FROM information_schema.referential_constraints rc
                JOIN information_schema.key_column_usage kcu
                  ON rc.constraint_name = kcu.constraint_name
                WHERE kcu.table_name = 'risk_alerts'
                  AND kcu.column_name = 'trigger_trade_id'
            """)
        )
        row = result.fetchone()
        assert row is not None, "FK on risk_alerts.trigger_trade_id not found — run migration 033"
        assert row[0] == "SET NULL", (
            f"trigger_trade_id FK delete rule is '{row[0]}' — expected SET NULL. "
            "Run migration 033 to fix."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 3 — UNIQUE CONSTRAINTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestUniqueConstraints:
    """Verify one-to-one relationships enforced by UNIQUE constraints."""

    @pytest.mark.asyncio
    async def test_users_email_unique(self, db, user):
        duplicate = User(email=user.email, display_name="Dupe")
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    @pytest.mark.asyncio
    async def test_goal_unique_per_broker_account(self, db, broker):
        g1 = Goal(broker_account_id=broker.id, primary_segment="EQUITY")
        g2 = Goal(broker_account_id=broker.id, primary_segment="FNO")
        db.add(g1)
        await db.flush()
        db.add(g2)
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    @pytest.mark.asyncio
    async def test_user_profile_unique_per_broker_account(self, db, broker):
        p1 = UserProfile(broker_account_id=broker.id)
        p2 = UserProfile(broker_account_id=broker.id)
        db.add(p1)
        await db.flush()
        db.add(p2)
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    @pytest.mark.asyncio
    async def test_streak_data_unique_per_broker_account(self, db, broker):
        s1 = StreakData(broker_account_id=broker.id)
        s2 = StreakData(broker_account_id=broker.id)
        db.add(s1)
        await db.flush()
        db.add(s2)
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    @pytest.mark.asyncio
    async def test_completed_trade_feature_unique_per_completed_trade(self, db, completed_trade, broker):
        f1 = CompletedTradeFeature(
            completed_trade_id=completed_trade.id,
            broker_account_id=broker.id,
        )
        f2 = CompletedTradeFeature(
            completed_trade_id=completed_trade.id,
            broker_account_id=broker.id,
        )
        db.add(f1)
        await db.flush()
        db.add(f2)
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    @pytest.mark.asyncio
    async def test_push_subscription_endpoint_unique(self, db, broker):
        endpoint = f"https://fcm.googleapis.com/test/{uuid4().hex}"
        ps1 = PushSubscription(
            broker_account_id=broker.id,
            endpoint=endpoint,
            p256dh_key="key1",
            auth_key="auth1",
        )
        ps2 = PushSubscription(
            broker_account_id=broker.id,
            endpoint=endpoint,  # same endpoint
            p256dh_key="key2",
            auth_key="auth2",
        )
        db.add(ps1)
        await db.flush()
        db.add(ps2)
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 4 — NOT NULL CONSTRAINTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestNotNullConstraints:
    """Verify NOT NULL enforced on critical columns."""

    @pytest.mark.asyncio
    async def test_user_email_not_null(self, db):
        u = User(email=None, display_name="No Email")
        db.add(u)
        with pytest.raises((IntegrityError, Exception)):
            await db.flush()
        await db.rollback()

    @pytest.mark.asyncio
    async def test_broker_account_user_id_not_null(self, db):
        ba = BrokerAccount(
            user_id=None,
            broker_name="zerodha",
            status="connected",
        )
        db.add(ba)
        with pytest.raises((IntegrityError, Exception)):
            await db.flush()
        await db.rollback()

    @pytest.mark.asyncio
    async def test_trade_broker_account_id_not_null(self, db):
        t = Trade(
            broker_account_id=None,
            order_id="TEST_NULL",
            tradingsymbol="INFY",
            exchange="NSE",
            transaction_type="BUY",
            order_type="MARKET",
            product="MIS",
            quantity=1,
            status="COMPLETE",
            asset_class="EQUITY",
            instrument_type="EQ",
            product_type="MIS",
        )
        db.add(t)
        with pytest.raises((IntegrityError, Exception)):
            await db.flush()
        await db.rollback()

    @pytest.mark.asyncio
    async def test_risk_alert_broker_account_id_not_null(self, db):
        ra = RiskAlert(
            broker_account_id=None,
            pattern_type="test",
            severity="low",
            message="test",
        )
        db.add(ra)
        with pytest.raises((IntegrityError, Exception)):
            await db.flush()
        await db.rollback()


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 5 — CASCADE DELETE CHAINS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCascadeDeletes:
    """Verify deleting a parent removes all children automatically."""

    @pytest.mark.asyncio
    async def test_delete_user_cascades_to_broker_accounts(self, db, user, broker):
        user_id = user.id
        broker_id = broker.id

        await db.delete(user)
        await db.flush()

        result = await db.execute(
            text("SELECT id FROM broker_accounts WHERE id = :id"),
            {"id": str(broker_id)},
        )
        assert result.fetchone() is None, "broker_account should cascade-delete when user deleted"

    @pytest.mark.asyncio
    async def test_delete_broker_cascades_to_trades(self, db, broker, trade):
        broker_id = broker.id
        trade_id = trade.id

        await db.delete(broker)
        await db.flush()

        result = await db.execute(
            text("SELECT id FROM trades WHERE id = :id"),
            {"id": str(trade_id)},
        )
        assert result.fetchone() is None, "trades should cascade-delete when broker_account deleted"

    @pytest.mark.asyncio
    async def test_delete_broker_cascades_to_completed_trades(self, db, broker, completed_trade):
        ct_id = completed_trade.id
        await db.delete(broker)
        await db.flush()

        result = await db.execute(
            text("SELECT id FROM completed_trades WHERE id = :id"),
            {"id": str(ct_id)},
        )
        assert result.fetchone() is None, "completed_trades should cascade-delete"

    @pytest.mark.asyncio
    async def test_delete_broker_cascades_to_risk_alerts(self, db, broker, risk_alert):
        alert_id = risk_alert.id
        await db.delete(broker)
        await db.flush()

        result = await db.execute(
            text("SELECT id FROM risk_alerts WHERE id = :id"),
            {"id": str(alert_id)},
        )
        assert result.fetchone() is None, "risk_alerts should cascade-delete"

    @pytest.mark.asyncio
    async def test_delete_risk_alert_cascades_to_alert_checkpoint(self, db, broker, risk_alert):
        checkpoint = AlertCheckpoint(
            alert_id=risk_alert.id,
            broker_account_id=broker.id,
            calculation_status="pending",
        )
        db.add(checkpoint)
        await db.flush()
        cp_id = checkpoint.id

        await db.delete(risk_alert)
        await db.flush()

        result = await db.execute(
            text("SELECT id FROM alert_checkpoints WHERE id = :id"),
            {"id": str(cp_id)},
        )
        assert result.fetchone() is None, "alert_checkpoint should cascade-delete when alert deleted"

    @pytest.mark.asyncio
    async def test_delete_completed_trade_cascades_to_feature(self, db, broker, completed_trade):
        feature = CompletedTradeFeature(
            completed_trade_id=completed_trade.id,
            broker_account_id=broker.id,
        )
        db.add(feature)
        await db.flush()
        feat_id = feature.id

        await db.delete(completed_trade)
        await db.flush()

        result = await db.execute(
            text("SELECT id FROM completed_trade_features WHERE id = :id"),
            {"id": str(feat_id)},
        )
        assert result.fetchone() is None, "completed_trade_feature should cascade-delete"

    @pytest.mark.asyncio
    async def test_delete_broker_cascades_to_user_profile(self, db, broker):
        profile = UserProfile(broker_account_id=broker.id)
        db.add(profile)
        await db.flush()
        prof_id = profile.id

        await db.delete(broker)
        await db.flush()

        result = await db.execute(
            text("SELECT id FROM user_profiles WHERE id = :id"),
            {"id": str(prof_id)},
        )
        assert result.fetchone() is None, "user_profile should cascade-delete"

    @pytest.mark.asyncio
    async def test_delete_broker_cascades_to_goal(self, db, broker):
        goal = Goal(broker_account_id=broker.id, primary_segment="EQUITY")
        db.add(goal)
        await db.flush()
        goal_id = goal.id

        await db.delete(broker)
        await db.flush()

        result = await db.execute(
            text("SELECT id FROM trading_goals WHERE id = :id"),
            {"id": str(goal_id)},
        )
        assert result.fetchone() is None, "goal should cascade-delete"

    @pytest.mark.asyncio
    async def test_delete_broker_cascades_to_cooldowns(self, db, broker):
        cooldown = Cooldown(
            broker_account_id=broker.id,
            reason="revenge_pattern",
            duration_minutes=15,
            started_at=now_utc(),
            expires_at=now_utc() + timedelta(minutes=15),
        )
        db.add(cooldown)
        await db.flush()
        cd_id = cooldown.id

        await db.delete(broker)
        await db.flush()

        result = await db.execute(
            text("SELECT id FROM cooldowns WHERE id = :id"),
            {"id": str(cd_id)},
        )
        assert result.fetchone() is None, "cooldowns should cascade-delete"

    @pytest.mark.asyncio
    async def test_delete_broker_cascades_to_push_subscriptions(self, db, broker):
        ps = PushSubscription(
            broker_account_id=broker.id,
            endpoint=f"https://fcm.test/{uuid4().hex}",
            p256dh_key="testkey",
            auth_key="testauth",
        )
        db.add(ps)
        await db.flush()
        ps_id = ps.id

        await db.delete(broker)
        await db.flush()

        result = await db.execute(
            text("SELECT id FROM push_subscriptions WHERE id = :id"),
            {"id": str(ps_id)},
        )
        assert result.fetchone() is None, "push_subscriptions should cascade-delete"

    @pytest.mark.asyncio
    async def test_full_chain_user_to_leaf(self, db, user, broker, trade, risk_alert):
        """Delete user → broker_account → trades + risk_alerts all cascade."""
        user_id = user.id
        broker_id = broker.id
        trade_id = trade.id
        alert_id = risk_alert.id

        await db.delete(user)
        await db.flush()

        for table, row_id in [
            ("broker_accounts", broker_id),
            ("trades", trade_id),
            ("risk_alerts", alert_id),
        ]:
            result = await db.execute(
                text(f"SELECT id FROM {table} WHERE id = :id"),
                {"id": str(row_id)},
            )
            assert result.fetchone() is None, f"{table} row should be gone after user delete"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 6 — THREE-LAYER TRADE ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════════════

class TestTradeArchitecture:
    """Validate the three-layer architecture: Trade → Position → CompletedTrade."""

    @pytest.mark.asyncio
    async def test_trade_pnl_is_zero(self, db, trade):
        """Trade.pnl is always null/0 — real P&L lives in CompletedTrade."""
        result = await db.execute(
            text("SELECT pnl FROM trades WHERE id = :id"),
            {"id": str(trade.id)},
        )
        row = result.fetchone()
        pnl = row[0]
        assert pnl is None or float(pnl) == 0.0, (
            f"Trade.pnl should be 0/null (real P&L is in completed_trades). Got: {pnl}"
        )

    @pytest.mark.asyncio
    async def test_completed_trade_has_real_pnl(self, db, completed_trade):
        result = await db.execute(
            text("SELECT realized_pnl FROM completed_trades WHERE id = :id"),
            {"id": str(completed_trade.id)},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] is not None, "CompletedTrade.realized_pnl should not be null"
        assert float(row[0]) == 200.0

    @pytest.mark.asyncio
    async def test_completed_trade_direction_values(self, db, broker):
        """Only LONG or SHORT allowed as direction."""
        for direction in ["LONG", "SHORT"]:
            ct = CompletedTrade(
                broker_account_id=broker.id,
                tradingsymbol="NIFTY24JANFUT",
                exchange="NFO",
                instrument_type="FUT",
                product="NRML",
                direction=direction,
                total_quantity=50,
                num_entries=1,
                num_exits=1,
                avg_entry_price=Decimal("21000.00"),
                avg_exit_price=Decimal("21100.00"),
                realized_pnl=Decimal("5000.00"),
                entry_time=now_utc() - timedelta(hours=3),
                exit_time=now_utc() - timedelta(hours=2),
                duration_minutes=60,
                status="closed",
            )
            db.add(ct)
        await db.flush()  # Should not raise

    @pytest.mark.asyncio
    async def test_position_linked_to_broker(self, db, broker):
        pos = Position(
            broker_account_id=broker.id,
            tradingsymbol="INFY",
            exchange="NSE",
            product="MIS",
            total_quantity=10,
            average_entry_price=Decimal("1500.00"),
            last_price=Decimal("1510.00"),
            unrealized_pnl=Decimal("100.00"),
        )
        db.add(pos)
        await db.flush()

        result = await db.execute(
            text("SELECT broker_account_id FROM positions WHERE id = :id"),
            {"id": str(pos.id)},
        )
        row = result.fetchone()
        assert str(row[0]) == str(broker.id)

    @pytest.mark.asyncio
    async def test_completed_trade_entry_exit_times_logical(self, db, completed_trade):
        result = await db.execute(
            text("SELECT entry_time, exit_time, duration_minutes FROM completed_trades WHERE id = :id"),
            {"id": str(completed_trade.id)},
        )
        row = result.fetchone()
        assert row[0] < row[1], "entry_time must be before exit_time"
        assert row[2] > 0, "duration_minutes must be positive"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 7 — DATA INTEGRITY SPOT CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataIntegrity:
    """Verify cross-table data consistency rules."""

    @pytest.mark.asyncio
    async def test_risk_alert_links_to_valid_trade(self, db, risk_alert, trade):
        result = await db.execute(
            text("""
                SELECT ra.id, t.id as trade_id
                FROM risk_alerts ra
                JOIN trades t ON t.id = ra.trigger_trade_id
                WHERE ra.id = :alert_id
            """),
            {"alert_id": str(risk_alert.id)},
        )
        row = result.fetchone()
        assert row is not None, "risk_alert.trigger_trade_id must join to a valid trade"
        assert str(row[1]) == str(trade.id)

    @pytest.mark.asyncio
    async def test_alert_checkpoint_links_to_valid_alert(self, db, broker, risk_alert):
        cp = AlertCheckpoint(
            alert_id=risk_alert.id,
            broker_account_id=broker.id,
            calculation_status="pending",
        )
        db.add(cp)
        await db.flush()

        result = await db.execute(
            text("""
                SELECT ac.id, ra.id as alert_id
                FROM alert_checkpoints ac
                JOIN risk_alerts ra ON ra.id = ac.alert_id
                WHERE ac.id = :cp_id
            """),
            {"cp_id": str(cp.id)},
        )
        row = result.fetchone()
        assert row is not None, "alert_checkpoint must join to a valid risk_alert"

    @pytest.mark.asyncio
    async def test_journal_entry_no_required_trade_link(self, db, broker):
        """JournalEntry.trade_id is optional (FK was dropped in migration 030)."""
        je = JournalEntry(
            broker_account_id=broker.id,
            notes="QA test journal entry",
            entry_type="daily",
            trade_id=None,
        )
        db.add(je)
        await db.flush()

        result = await db.execute(
            text("SELECT id, trade_id FROM journal_entries WHERE id = :id"),
            {"id": str(je.id)},
        )
        row = result.fetchone()
        assert row is not None
        assert row[1] is None, "JournalEntry with no trade_id should save fine"

    @pytest.mark.asyncio
    async def test_behavioral_event_confidence_check(self, db, broker):
        """BehavioralEvent.confidence must be >= 0.70 (DB CHECK constraint)."""
        event = BehavioralEvent(
            broker_account_id=broker.id,
            event_type="revenge_trading",
            severity="HIGH",
            confidence=Decimal("0.50"),  # Below 0.70 threshold
            message="TEST low confidence event",
            detected_at=now_utc(),
        )
        db.add(event)
        with pytest.raises((IntegrityError, Exception)):
            await db.flush()
        await db.rollback()

    @pytest.mark.asyncio
    async def test_behavioral_event_valid_confidence(self, db, broker):
        event = BehavioralEvent(
            broker_account_id=broker.id,
            event_type="revenge_trading",
            severity="HIGH",
            confidence=Decimal("0.85"),
            message="TEST valid confidence event",
            detected_at=now_utc(),
        )
        db.add(event)
        await db.flush()

        result = await db.execute(
            text("SELECT confidence FROM behavioral_events WHERE id = :id"),
            {"id": str(event.id)},
        )
        row = result.fetchone()
        assert float(row[0]) == 0.85

    @pytest.mark.asyncio
    async def test_user_guardian_phone_persists(self, db, user):
        result = await db.execute(
            text("SELECT guardian_phone, guardian_name FROM users WHERE id = :id"),
            {"id": str(user.id)},
        )
        row = result.fetchone()
        assert row[0] == "+919999000001", "guardian_phone should be on users table"

    @pytest.mark.asyncio
    async def test_broker_account_user_relationship(self, db, user, broker):
        """broker_account.user_id correctly references the user."""
        result = await db.execute(
            text("""
                SELECT u.email, ba.broker_email
                FROM broker_accounts ba
                JOIN users u ON u.id = ba.user_id
                WHERE ba.id = :broker_id
            """),
            {"broker_id": str(broker.id)},
        )
        row = result.fetchone()
        assert row is not None, "broker_account must join to users via user_id"
        assert row[0] == user.email

    @pytest.mark.asyncio
    async def test_orphan_broker_account_rejected(self, db):
        """Cannot create broker_account with non-existent user_id."""
        ba = BrokerAccount(
            user_id=uuid4(),  # random UUID that doesn't exist in users
            broker_name="zerodha",
            broker_email="ghost@example.com",
            status="connected",
        )
        db.add(ba)
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    @pytest.mark.asyncio
    async def test_instrument_table_has_no_fk(self, db):
        """Instruments are a standalone cache — no FK to broker_accounts."""
        result = await db.execute(
            text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = 'instruments'
            """)
        )
        fks = [row[0] for row in result.fetchall()]
        assert not fks, f"instruments table should have no FKs, found: {fks}"

    @pytest.mark.asyncio
    async def test_margin_snapshot_timestamp_not_null(self, db, broker):
        ms = MarginSnapshot(
            broker_account_id=broker.id,
            snapshot_at=now_utc(),
            equity_available=Decimal("100000"),
            equity_used=Decimal("20000"),
            equity_total=Decimal("120000"),
            equity_utilization_pct=Decimal("16.67"),
        )
        db.add(ms)
        await db.flush()

        result = await db.execute(
            text("SELECT snapshot_at FROM margin_snapshots WHERE id = :id"),
            {"id": str(ms.id)},
        )
        row = result.fetchone()
        assert row[0] is not None


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 8 — INDEX EXISTENCE
# ═══════════════════════════════════════════════════════════════════════════════

class TestIndexes:
    """Verify critical performance indexes exist."""

    EXPECTED_INDEXES = [
        ("broker_accounts", "idx_broker_accounts_user_id"),
        ("completed_trades", "idx_completed_trades_broker_exit"),
        ("risk_alerts", "idx_risk_alerts_broker_detected"),
        ("alert_checkpoints", "idx_ac_broker_created"),
        ("alert_checkpoints", "idx_ac_alert_id"),
    ]

    @pytest.mark.asyncio
    async def test_critical_indexes_exist(self, db):
        result = await db.execute(
            text("""
                SELECT tablename, indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
            """)
        )
        existing = {(row[0], row[1]) for row in result.fetchall()}
        missing = [idx for idx in self.EXPECTED_INDEXES if idx not in existing]
        assert not missing, f"Missing indexes: {missing}"

    @pytest.mark.asyncio
    async def test_users_email_index_exists(self, db):
        result = await db.execute(
            text("""
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'users'
                  AND indexname = 'idx_users_email'
            """)
        )
        row = result.fetchone()
        assert row is not None, "idx_users_email index not found on users table"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 9 — SCHEMA SUMMARY REPORT
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchemaReport:
    """Print a summary of the full schema for documentation."""

    @pytest.mark.asyncio
    async def test_print_table_row_counts(self, db):
        """Non-asserting: prints row counts for all tables."""
        tables = [
            "users", "broker_accounts", "trades", "completed_trades",
            "completed_trade_features", "positions", "risk_alerts",
            "alert_checkpoints", "journal_entries", "cooldowns",
            "trading_goals", "commitment_logs", "streak_data", "user_profiles",
            "behavioral_events", "holdings", "orders", "margin_snapshots",
            "push_subscriptions", "incomplete_positions", "instruments",
        ]
        print("\n\n=== TABLE ROW COUNTS ===")
        for table in tables:
            try:
                result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"  {table:<30} {count:>8} rows")
            except Exception as e:
                print(f"  {table:<30} ERROR: {e}")
        print("========================\n")

    @pytest.mark.asyncio
    async def test_print_fk_relationships(self, db):
        """Non-asserting: prints all FK relationships for documentation."""
        result = await db.execute(
            text("""
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column,
                    rc.delete_rule
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                JOIN information_schema.referential_constraints rc
                  ON tc.constraint_name = rc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
                ORDER BY tc.table_name, kcu.column_name
            """)
        )
        rows = result.fetchall()
        print("\n\n=== FOREIGN KEY MAP ===")
        for row in rows:
            print(f"  {row[0]}.{row[1]} -> {row[2]}.{row[3]}  [ON DELETE {row[4]}]")
        print("=======================\n")
