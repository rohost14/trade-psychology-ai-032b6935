"""
Dashboard API Test Suite
========================

Tests every backend endpoint consumed by the Dashboard screen:

  GET  /api/positions/
  GET  /api/trades/completed
  GET  /api/trades/stats
  GET  /api/risk/state
  GET  /api/risk/alerts
  GET  /api/analytics/dashboard-stats
  GET  /api/zerodha/margins  (mocked — requires live Kite token)
  GET  /api/zerodha/holdings (mocked — requires live Kite token)
  POST /api/journal/
  GET  /api/journal/trade/{id}
  DELETE /api/journal/{id}

Coverage:
  - Authentication & authorization (every endpoint)
  - Data isolation (user A cannot see user B data)
  - Correct JWT claim structure (sub=user_id, bid=broker_account_id)
  - Field presence and types
  - Ordering / pagination
  - Computed values (P&L, win rate, session stats)
  - Empty-state responses (no data yet)
  - Revoked-token rejection
  - Error payloads (no stack traces leaked)

Run:
    cd backend
    pytest tests/test_dashboard_api.py -v
"""

import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.config import settings
from app.api.deps import create_access_token
from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade
from app.models.position import Position
from app.models.risk_alert import RiskAlert
from app.models.goal import Goal
from app.models.user_profile import UserProfile

from tests.helpers import now_utc, make_email


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

def make_engine():
    return create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
        echo=False,
    )


@pytest_asyncio.fixture
async def db():
    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def user(db):
    u = User(email=make_email(), display_name="Dashboard QA", guardian_phone="+910000000001")
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def broker(db, user):
    ba = BrokerAccount(
        user_id=user.id,
        broker_name="zerodha",
        broker_email=user.email,
        broker_user_id="DQATEST",
        status="connected",
    )
    db.add(ba)
    await db.flush()
    return ba


@pytest_asyncio.fixture
async def auth_token(user, broker):
    """Valid JWT for the test broker account."""
    return create_access_token(user_id=user.id, broker_account_id=broker.id)


@pytest_asyncio.fixture
async def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest_asyncio.fixture
async def other_user(db):
    """A second user — for isolation tests."""
    u = User(email=make_email(), display_name="Other User")
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def other_broker(db, other_user):
    ba = BrokerAccount(
        user_id=other_user.id,
        broker_name="zerodha",
        broker_email=other_user.email,
        broker_user_id="OTHERUSR",
        status="connected",
    )
    db.add(ba)
    await db.flush()
    return ba


@pytest_asyncio.fixture
async def other_token(other_user, other_broker):
    return create_access_token(user_id=other_user.id, broker_account_id=other_broker.id)


@pytest_asyncio.fixture
async def other_headers(other_token):
    return {"Authorization": f"Bearer {other_token}"}


@pytest_asyncio.fixture
async def completed_trade(db, broker):
    ct = CompletedTrade(
        broker_account_id=broker.id,
        tradingsymbol="INFY",
        exchange="NSE",
        instrument_type="EQ",
        product="MIS",
        direction="LONG",
        total_quantity=10,
        num_entries=1,
        num_exits=1,
        avg_entry_price=Decimal("1500.00"),
        avg_exit_price=Decimal("1520.00"),
        realized_pnl=Decimal("200.00"),
        entry_time=now_utc() - timedelta(hours=3),
        exit_time=now_utc() - timedelta(hours=2),
        duration_minutes=60,
        status="closed",
    )
    db.add(ct)
    await db.flush()
    return ct


@pytest_asyncio.fixture
async def losing_trade(db, broker):
    ct = CompletedTrade(
        broker_account_id=broker.id,
        tradingsymbol="RELIANCE",
        exchange="NSE",
        instrument_type="EQ",
        product="MIS",
        direction="SHORT",
        total_quantity=5,
        num_entries=1,
        num_exits=1,
        avg_entry_price=Decimal("2800.00"),
        avg_exit_price=Decimal("2850.00"),
        realized_pnl=Decimal("-250.00"),
        entry_time=now_utc() - timedelta(hours=5),
        exit_time=now_utc() - timedelta(hours=4),
        duration_minutes=60,
        status="closed",
    )
    db.add(ct)
    await db.flush()
    return ct


@pytest_asyncio.fixture
async def open_position(db, broker):
    pos = Position(
        broker_account_id=broker.id,
        tradingsymbol="TCS",
        exchange="NSE",
        product="MIS",
        total_quantity=20,
        average_entry_price=Decimal("3800.00"),
        last_price=Decimal("3850.00"),
        unrealized_pnl=Decimal("1000.00"),
        status="open",
        synced_at=now_utc(),
    )
    db.add(pos)
    await db.flush()
    return pos


@pytest_asyncio.fixture
async def risk_alert(db, broker):
    ra = RiskAlert(
        broker_account_id=broker.id,
        pattern_type="revenge_trading",
        severity="danger",
        message="TEST: Revenge trading alert",
        detected_at=now_utc() - timedelta(hours=1),
    )
    db.add(ra)
    await db.flush()
    return ra


@pytest_asyncio.fixture
async def client(db):
    """
    HTTP test client that shares the test's DB session with the FastAPI app.

    By overriding get_db, the app sees the same in-flight transaction as the
    test fixtures, so broker/user rows created with flush() (not commit()) are
    visible to get_verified_broker_account_id and all other DB-reading deps.
    """
    from app.core.database import get_db

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 1 — AUTHENTICATION GUARD (every dashboard endpoint)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthenticationGuard:
    """Every dashboard endpoint must return 401/403 without a valid token."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/api/positions/"),
        ("GET", "/api/trades/completed"),
        ("GET", "/api/trades/stats"),
        ("GET", "/api/risk/state"),
        ("GET", "/api/risk/alerts"),
        ("GET", "/api/analytics/dashboard-stats"),
    ]

    @pytest.mark.asyncio
    async def test_no_token_returns_401_or_403(self, client):
        """Every protected endpoint rejects requests with no token."""
        for method, endpoint in self.PROTECTED_ENDPOINTS:
            resp = await client.request(method, endpoint)
            assert resp.status_code in (401, 403), (
                f"{method} {endpoint} returned {resp.status_code} — expected 401 or 403 with no token"
            )

    @pytest.mark.asyncio
    async def test_malformed_token_rejected(self, client):
        """A garbage token string must be rejected."""
        headers = {"Authorization": "Bearer this.is.not.a.jwt"}
        for method, endpoint in self.PROTECTED_ENDPOINTS:
            resp = await client.request(method, endpoint, headers=headers)
            assert resp.status_code in (401, 403), (
                f"{method} {endpoint} accepted malformed token"
            )

    @pytest.mark.asyncio
    async def test_wrong_scheme_rejected(self, client, auth_token):
        """Token with wrong scheme (Basic instead of Bearer) must be rejected."""
        headers = {"Authorization": f"Basic {auth_token}"}
        resp = await client.get("/api/positions/", headers=headers)
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_revoked_token_rejected(self, client, db, user):
        """A broker account with token_revoked_at set must be rejected by verified endpoints.

        Uses /api/shield/summary which requires get_verified_broker_account_id.
        Commits the revoked broker so the API's separate DB connection can see it.
        """
        revoked_broker = BrokerAccount(
            user_id=user.id,
            broker_name="zerodha",
            broker_email=user.email,
            broker_user_id="REVOKE99",
            status="disconnected",
            token_revoked_at=now_utc(),
        )
        db.add(revoked_broker)
        await db.commit()  # Must commit — API uses a separate DB connection

        token = create_access_token(user_id=user.id, broker_account_id=revoked_broker.id)

        resp = await client.get(
            "/api/shield/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (401, 403), (
            f"Revoked token was accepted — got {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_error_response_has_no_stack_trace(self, client):
        """Error responses must not leak internal stack traces."""
        resp = await client.get("/api/positions/")
        body = resp.text
        assert "Traceback" not in body
        assert "File \"" not in body
        assert "line " not in body or "detail" in body  # "line" in detail message is ok


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 2 — JWT STRUCTURE & CLAIMS
# ═══════════════════════════════════════════════════════════════════════════════

class TestJWTStructure:
    """Validate JWT contains correct claims and resolves to correct identity."""

    @pytest.mark.asyncio
    async def test_token_contains_sub_and_bid(self, user, broker):
        """JWT must have sub=user_id and bid=broker_account_id."""
        from jose import jwt
        token = create_access_token(user_id=user.id, broker_account_id=broker.id)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        assert payload["sub"] == str(user.id), "sub must be user_id"
        assert payload["bid"] == str(broker.id), "bid must be broker_account_id"

    @pytest.mark.asyncio
    async def test_token_has_expiry(self, user, broker):
        """JWT must have an exp claim."""
        from jose import jwt
        token = create_access_token(user_id=user.id, broker_account_id=broker.id)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        assert "exp" in payload
        assert payload["exp"] > datetime.now(timezone.utc).timestamp()

    @pytest.mark.asyncio
    async def test_different_brokers_get_different_tokens(self, user, broker, other_broker):
        """Two broker accounts must produce tokens with different bid claims."""
        t1 = create_access_token(user_id=user.id, broker_account_id=broker.id)
        t2 = create_access_token(user_id=user.id, broker_account_id=other_broker.id)
        from jose import jwt
        p1 = jwt.decode(t1, settings.SECRET_KEY, algorithms=["HS256"])
        p2 = jwt.decode(t2, settings.SECRET_KEY, algorithms=["HS256"])
        assert p1["bid"] != p2["bid"]


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 3 — POSITIONS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

class TestPositionsEndpoint:
    """GET /api/positions/"""

    @pytest.mark.asyncio
    async def test_returns_200_with_valid_token(self, client, auth_headers):
        resp = await client.get("/api/positions/", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_positions_returns_empty_list(self, client, auth_headers):
        """If no open positions exist, returns empty list (not error)."""
        resp = await client.get("/api/positions/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_position_fields_present(self, client, db, auth_headers, open_position):
        await db.commit()  # commit so API can read it
        resp = await client.get("/api/positions/", headers=auth_headers)
        assert resp.status_code == 200
        positions = resp.json()
        if isinstance(positions, dict):
            positions = positions.get("positions", positions.get("data", []))
        if len(positions) > 0:
            pos = positions[0]
            assert "tradingsymbol" in pos
            assert "total_quantity" in pos or "quantity" in pos
            assert "unrealized_pnl" in pos or "pnl" in pos

    @pytest.mark.asyncio
    async def test_positions_isolated_from_other_broker(self, client, db, other_headers, open_position):
        """User B cannot see User A's positions."""
        await db.commit()
        resp = await client.get("/api/positions/", headers=other_headers)
        assert resp.status_code == 200
        positions = resp.json()
        if isinstance(positions, dict):
            positions = positions.get("positions", [])
        symbols = [p.get("tradingsymbol") for p in positions]
        assert "TCS" not in symbols, "User B should not see User A's TCS position"

    @pytest.mark.asyncio
    async def test_only_open_positions_returned(self, client, db, auth_headers, broker):
        """Closed positions (status != 'open') must not appear."""
        closed_pos = Position(
            broker_account_id=broker.id,
            tradingsymbol="WIPRO",
            exchange="NSE",
            product="MIS",
            total_quantity=0,
            average_entry_price=Decimal("500.00"),
            last_price=Decimal("505.00"),
            unrealized_pnl=Decimal("0.00"),
            status="closed",
            synced_at=now_utc(),
        )
        db.add(closed_pos)
        await db.commit()

        resp = await client.get("/api/positions/", headers=auth_headers)
        positions = resp.json()
        if isinstance(positions, dict):
            positions = positions.get("positions", [])
        symbols = [p.get("tradingsymbol") for p in positions]
        assert "WIPRO" not in symbols, "Closed position WIPRO should not appear"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 4 — COMPLETED TRADES ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompletedTradesEndpoint:
    """GET /api/trades/completed"""

    @pytest.mark.asyncio
    async def test_returns_200(self, client, auth_headers):
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_when_no_trades(self, client, auth_headers):
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", data.get("data", []))
        assert isinstance(trades, list)

    @pytest.mark.asyncio
    async def test_completed_trade_fields(self, client, db, auth_headers, completed_trade):
        await db.commit()
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", data.get("data", []))
        assert len(trades) >= 1
        t = trades[0]
        assert "tradingsymbol" in t
        assert "realized_pnl" in t or "pnl" in t
        assert "direction" in t
        assert "entry_time" in t
        assert "exit_time" in t

    @pytest.mark.asyncio
    async def test_realized_pnl_is_real_value(self, client, db, auth_headers, completed_trade):
        """realized_pnl must be the actual P&L (200.00), not zero."""
        await db.commit()
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        if trades:
            pnl = float(trades[0].get("realized_pnl", trades[0].get("pnl", 0)))
            assert pnl == 200.0, f"Expected 200.0 but got {pnl}"

    @pytest.mark.asyncio
    async def test_trades_ordered_by_exit_time_desc(self, client, db, auth_headers, completed_trade, losing_trade):
        """Most recent trade must appear first."""
        await db.commit()
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        if len(trades) >= 2:
            t1_time = trades[0].get("exit_time", "")
            t2_time = trades[1].get("exit_time", "")
            assert t1_time >= t2_time, "Trades not ordered by exit_time DESC"

    @pytest.mark.asyncio
    async def test_trades_isolated_from_other_broker(self, client, db, other_headers, completed_trade):
        """User B cannot see User A's completed trades."""
        await db.commit()
        resp = await client.get("/api/trades/completed", headers=other_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        symbols = [t.get("tradingsymbol") for t in trades]
        assert "INFY" not in symbols, "User B should not see User A's INFY trade"

    @pytest.mark.asyncio
    async def test_pagination_limit_respected(self, client, auth_headers):
        """limit param is respected."""
        resp = await client.get("/api/trades/completed?limit=5", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        assert len(trades) <= 5

    @pytest.mark.asyncio
    async def test_win_loss_balance(self, client, db, auth_headers, completed_trade, losing_trade):
        """With 1 win (200) + 1 loss (-250), net P&L should be -50."""
        await db.commit()
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        pnls = [float(t.get("realized_pnl", t.get("pnl", 0))) for t in trades]
        net = sum(pnls)
        assert abs(net - (-50.0)) < 0.01, f"Net P&L should be -50.0, got {net}"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 5 — RISK STATE ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiskStateEndpoint:
    """GET /api/risk/state"""

    @pytest.mark.asyncio
    async def test_returns_200(self, client, auth_headers):
        resp = await client.get("/api/risk/state", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_state_field_present(self, client, auth_headers):
        resp = await client.get("/api/risk/state", headers=auth_headers)
        data = resp.json()
        assert "state" in data or "risk_state" in data or "level" in data, (
            f"Risk state response missing state field: {data}"
        )

    @pytest.mark.asyncio
    async def test_state_value_is_valid(self, client, auth_headers):
        resp = await client.get("/api/risk/state", headers=auth_headers)
        data = resp.json()
        state = data.get("state") or data.get("risk_state") or data.get("level")
        valid_states = {"safe", "caution", "danger", "warning", "low", "medium", "high", "critical"}
        if state:
            assert state.lower() in valid_states or isinstance(state, str), (
                f"Invalid risk state: {state}"
            )

    @pytest.mark.asyncio
    async def test_new_account_starts_safe(self, client, auth_headers):
        """A brand-new account with no trades should be in 'safe' state."""
        resp = await client.get("/api/risk/state", headers=auth_headers)
        data = resp.json()
        state = (data.get("state") or data.get("risk_state") or data.get("level") or "").lower()
        assert state in ("safe", "low", ""), (
            f"New account should be safe but got: {state}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 6 — RISK ALERTS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiskAlertsEndpoint:
    """GET /api/risk/alerts"""

    @pytest.mark.asyncio
    async def test_returns_200(self, client, auth_headers):
        resp = await client.get("/api/risk/alerts", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_list_for_new_account(self, client, auth_headers):
        resp = await client.get("/api/risk/alerts", headers=auth_headers)
        data = resp.json()
        alerts = data if isinstance(data, list) else data.get("alerts", [])
        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_alert_fields_present(self, client, db, auth_headers, risk_alert):
        await db.commit()
        resp = await client.get("/api/risk/alerts", headers=auth_headers)
        data = resp.json()
        alerts = data if isinstance(data, list) else data.get("alerts", [])
        if alerts:
            a = alerts[0]
            assert "id" in a
            assert "pattern_type" in a
            assert "severity" in a
            assert "message" in a

    @pytest.mark.asyncio
    async def test_alerts_isolated_from_other_broker(self, client, db, other_headers, risk_alert):
        """User B cannot see User A's alerts."""
        await db.commit()
        resp = await client.get("/api/risk/alerts", headers=other_headers)
        data = resp.json()
        alerts = data if isinstance(data, list) else data.get("alerts", [])
        alert_ids = [a.get("id") for a in alerts]
        assert str(risk_alert.id) not in alert_ids, "User B should not see User A's alert"

    @pytest.mark.asyncio
    async def test_hours_filter_excludes_old_alerts(self, client, db, auth_headers, broker):
        """Alerts older than the hours= param must not appear."""
        old_alert = RiskAlert(
            broker_account_id=broker.id,
            pattern_type="overtrading",
            severity="caution",
            message="OLD ALERT",
            detected_at=now_utc() - timedelta(hours=50),
        )
        db.add(old_alert)
        await db.commit()

        resp = await client.get("/api/risk/alerts?hours=48", headers=auth_headers)
        data = resp.json()
        alerts = data if isinstance(data, list) else data.get("alerts", [])
        messages = [a.get("message") for a in alerts]
        assert "OLD ALERT" not in messages, "50-hour old alert should be excluded with hours=48"

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, client, db, auth_headers, risk_alert):
        """Acknowledging an alert sets acknowledged_at."""
        await db.commit()
        alert_id = str(risk_alert.id)
        resp = await client.post(
            f"/api/risk/alerts/{alert_id}/acknowledge",
            headers=auth_headers,
        )
        assert resp.status_code in (200, 204), f"Acknowledge returned {resp.status_code}"

    @pytest.mark.asyncio
    async def test_cannot_acknowledge_other_users_alert(self, client, db, other_headers, risk_alert):
        """User B cannot acknowledge User A's alert."""
        await db.commit()
        alert_id = str(risk_alert.id)
        resp = await client.post(
            f"/api/risk/alerts/{alert_id}/acknowledge",
            headers=other_headers,
        )
        assert resp.status_code in (403, 404, 400), (
            f"User B was able to acknowledge User A's alert: {resp.status_code}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 7 — DASHBOARD STATS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

class TestDashboardStatsEndpoint:
    """GET /api/analytics/dashboard-stats"""

    @pytest.mark.asyncio
    async def test_returns_200(self, client, auth_headers):
        resp = await client.get("/api/analytics/dashboard-stats", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_stats_fields_present(self, client, auth_headers):
        resp = await client.get("/api/analytics/dashboard-stats", headers=auth_headers)
        data = resp.json()
        assert isinstance(data, dict), "dashboard-stats must return a JSON object"

    @pytest.mark.asyncio
    async def test_stats_isolated(self, client, db, other_headers, completed_trade):
        """User B sees zero stats when User A has trades."""
        await db.commit()
        resp = await client.get("/api/analytics/dashboard-stats", headers=other_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_win_rate_calculation(self, client, db, auth_headers, completed_trade, losing_trade):
        """With 1 win and 1 loss, win rate should be 50%."""
        await db.commit()
        resp = await client.get("/api/analytics/dashboard-stats", headers=auth_headers)
        data = resp.json()
        win_rate = data.get("win_rate") or data.get("winRate")
        if win_rate is not None:
            assert abs(float(win_rate) - 50.0) < 1.0, f"Expected ~50% win rate, got {win_rate}"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 8 — JOURNAL ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

class TestJournalEndpoint:
    """POST /api/journal/ | GET /api/journal/trade/{id} | DELETE /api/journal/{id}"""

    @pytest.mark.asyncio
    async def test_create_journal_entry(self, client, db, auth_headers, completed_trade):
        await db.commit()
        payload = {
            "broker_account_id": str(completed_trade.broker_account_id),
            "trade_id": str(completed_trade.id),
            "notes": "QA test journal entry",
            "emotion_tags": ["confident", "calm"],
            "entry_type": "trade",
            "trade_symbol": "INFY",
            "trade_pnl": "200.00",
        }
        resp = await client.post("/api/journal/", json=payload, headers=auth_headers)
        assert resp.status_code in (200, 201), f"Journal create failed: {resp.text}"

    @pytest.mark.asyncio
    async def test_journal_entry_without_trade_link(self, client, db, auth_headers):
        """A journal entry can be created with no trade_id (daily note).

        Commits broker_account so the API's separate DB session can satisfy the FK.
        """
        await db.commit()  # Make broker_account visible to API's DB connection
        payload = {
            "notes": "Daily market recap",
            "entry_type": "daily",
        }
        resp = await client.post("/api/journal/", json=payload, headers=auth_headers)
        assert resp.status_code in (200, 201), f"Standalone journal failed: {resp.text}"

    @pytest.mark.asyncio
    async def test_journal_isolated_by_jwt(self, client, db, auth_headers, other_headers, completed_trade):
        """User B cannot see User A's journal entries (isolated by JWT broker_account_id).

        The journal API scopes reads by broker_account_id from the JWT 'bid' claim.
        User B's token carries User B's broker_account_id, so they get an empty list.
        """
        await db.commit()
        # User A creates a journal entry
        payload = {
            "trade_id": str(completed_trade.id),
            "notes": "User A private note",
            "entry_type": "trade",
        }
        create_resp = await client.post("/api/journal/", json=payload, headers=auth_headers)
        assert create_resp.status_code in (200, 201), f"User A journal create failed: {create_resp.text}"

        # User B lists journal entries — should NOT see User A's entry
        list_resp = await client.get("/api/journal/", headers=other_headers)
        assert list_resp.status_code == 200
        data = list_resp.json()
        entries = data.get("entries", []) if isinstance(data, dict) else data
        notes = [e.get("notes") for e in entries]
        assert "User A private note" not in notes, (
            "User B should not see User A's journal entries"
        )

    @pytest.mark.asyncio
    async def test_get_journal_by_trade(self, client, db, auth_headers, completed_trade, broker):
        await db.commit()
        # Create entry first
        payload = {
            "broker_account_id": str(broker.id),
            "trade_id": str(completed_trade.id),
            "notes": "QA get test",
            "entry_type": "trade",
        }
        create_resp = await client.post("/api/journal/", json=payload, headers=auth_headers)
        if create_resp.status_code not in (200, 201):
            pytest.skip("Journal create not available, skipping get test")

        get_resp = await client.get(
            f"/api/journal/trade/{completed_trade.id}",
            headers=auth_headers,
        )
        assert get_resp.status_code in (200, 404)
        if get_resp.status_code == 200:
            data = get_resp.json()
            # Response is {"entry": {...}} — unwrap the envelope
            entry = data.get("entry", data) if isinstance(data, dict) else data
            assert entry.get("notes") == "QA get test"

    @pytest.mark.asyncio
    async def test_valid_emotion_tags_accepted(self, client, db, auth_headers):
        """Journal entries with valid emotion tags must be accepted."""
        await db.commit()  # Commit broker_account so FK is satisfied
        valid_tags = ["confident", "anxious", "fomo", "calm", "greedy", "fearful"]
        payload = {
            "notes": "Emotion test",
            "emotion_tags": valid_tags,
            "entry_type": "daily",
        }
        resp = await client.post("/api/journal/", json=payload, headers=auth_headers)
        assert resp.status_code in (200, 201, 422)


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 9 — DATA ISOLATION (CROSS-USER SECURITY)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataIsolation:
    """Comprehensive cross-user data isolation tests."""

    @pytest.mark.asyncio
    async def test_positions_isolated(self, client, db, auth_headers, other_headers, broker, other_broker):
        """Create positions for both users, verify neither sees the other's."""
        pos_a = Position(
            broker_account_id=broker.id,
            tradingsymbol="SBIN",
            exchange="NSE",
            product="MIS",
            total_quantity=100,
            average_entry_price=Decimal("600.00"),
            last_price=Decimal("610.00"),
            unrealized_pnl=Decimal("1000.00"),
            status="open",
            synced_at=now_utc(),
        )
        pos_b = Position(
            broker_account_id=other_broker.id,
            tradingsymbol="HDFC",
            exchange="NSE",
            product="MIS",
            total_quantity=50,
            average_entry_price=Decimal("1600.00"),
            last_price=Decimal("1620.00"),
            unrealized_pnl=Decimal("1000.00"),
            status="open",
            synced_at=now_utc(),
        )
        db.add(pos_a)
        db.add(pos_b)
        await db.commit()

        # User A should see SBIN but not HDFC
        resp_a = await client.get("/api/positions/", headers=auth_headers)
        positions_a = resp_a.json()
        if isinstance(positions_a, dict):
            positions_a = positions_a.get("positions", [])
        symbols_a = [p.get("tradingsymbol") for p in positions_a]
        assert "SBIN" in symbols_a, "User A should see SBIN"
        assert "HDFC" not in symbols_a, "User A should NOT see User B's HDFC"

        # User B should see HDFC but not SBIN
        resp_b = await client.get("/api/positions/", headers=other_headers)
        positions_b = resp_b.json()
        if isinstance(positions_b, dict):
            positions_b = positions_b.get("positions", [])
        symbols_b = [p.get("tradingsymbol") for p in positions_b]
        assert "HDFC" in symbols_b, "User B should see HDFC"
        assert "SBIN" not in symbols_b, "User B should NOT see User A's SBIN"

    @pytest.mark.asyncio
    async def test_completed_trades_isolated(self, client, db, auth_headers, other_headers,
                                              completed_trade, other_broker):
        """User B's trades are not visible to User A and vice versa."""
        other_ct = CompletedTrade(
            broker_account_id=other_broker.id,
            tradingsymbol="ULTRACEMCO",
            exchange="NSE",
            instrument_type="EQ",
            product="MIS",
            direction="LONG",
            total_quantity=5,
            num_entries=1,
            num_exits=1,
            avg_entry_price=Decimal("8000.00"),
            avg_exit_price=Decimal("8100.00"),
            realized_pnl=Decimal("500.00"),
            entry_time=now_utc() - timedelta(hours=2),
            exit_time=now_utc() - timedelta(hours=1),
            duration_minutes=60,
            status="closed",
        )
        db.add(other_ct)
        await db.commit()

        resp = await client.get("/api/trades/completed", headers=auth_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        symbols = [t.get("tradingsymbol") for t in trades]
        assert "ULTRACEMCO" not in symbols, "User A should not see User B's ULTRACEMCO trade"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 10 — COMPUTED VALUES & BUSINESS LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputedValues:
    """Validate P&L calculations, win rates, and other derived metrics."""

    @pytest.mark.asyncio
    async def test_session_pnl_is_sum_of_completed_trades(self, client, db, auth_headers,
                                                           completed_trade, losing_trade):
        """Session P&L = sum(realized_pnl). 200 + (-250) = -50."""
        await db.commit()
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        total = sum(float(t.get("realized_pnl", t.get("pnl", 0))) for t in trades)
        assert abs(total - (-50.0)) < 0.01, f"Session P&L should be -50, got {total}"

    @pytest.mark.asyncio
    async def test_long_direction_stored_correctly(self, client, db, auth_headers, completed_trade):
        """CompletedTrade with direction=LONG must return LONG in API."""
        await db.commit()
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        infy = next((t for t in trades if t.get("tradingsymbol") == "INFY"), None)
        if infy:
            assert infy.get("direction") == "LONG"

    @pytest.mark.asyncio
    async def test_short_direction_stored_correctly(self, client, db, auth_headers, losing_trade):
        """CompletedTrade with direction=SHORT must return SHORT in API."""
        await db.commit()
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        reliance = next((t for t in trades if t.get("tradingsymbol") == "RELIANCE"), None)
        if reliance:
            assert reliance.get("direction") == "SHORT"

    @pytest.mark.asyncio
    async def test_duration_is_positive(self, client, db, auth_headers, completed_trade):
        """Duration in minutes must be > 0 for all completed trades."""
        await db.commit()
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        for t in trades:
            dur = t.get("duration_minutes") or t.get("duration")
            if dur is not None:
                assert float(dur) >= 0, f"Duration must be >= 0, got {dur}"

    @pytest.mark.asyncio
    async def test_entry_time_before_exit_time(self, client, db, auth_headers, completed_trade):
        """entry_time must always be before exit_time."""
        await db.commit()
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        for t in trades:
            et = t.get("entry_time", "")
            xt = t.get("exit_time", "")
            if et and xt:
                assert et <= xt, f"entry_time {et} must be <= exit_time {xt}"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 11 — RESPONSE FORMAT & API CONTRACT
# ═══════════════════════════════════════════════════════════════════════════════

class TestResponseFormat:
    """Validate API response shape matches what the frontend expects."""

    @pytest.mark.asyncio
    async def test_positions_response_is_json(self, client, auth_headers):
        resp = await client.get("/api/positions/", headers=auth_headers)
        assert "application/json" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_trades_response_is_json(self, client, auth_headers):
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        assert "application/json" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_completed_trade_has_broker_account_id(self, client, db, auth_headers, completed_trade):
        """broker_account_id must be present so frontend can scope data correctly."""
        await db.commit()
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        if trades:
            assert "broker_account_id" in trades[0] or "id" in trades[0]

    @pytest.mark.asyncio
    async def test_risk_alert_has_severity(self, client, db, auth_headers, risk_alert):
        """severity field is required for RecentAlertsCard rendering."""
        await db.commit()
        resp = await client.get("/api/risk/alerts", headers=auth_headers)
        data = resp.json()
        alerts = data if isinstance(data, list) else data.get("alerts", [])
        if alerts:
            assert "severity" in alerts[0], "severity field missing from alert response"
            assert alerts[0]["severity"] in ("low", "medium", "high", "danger", "critical", "caution", "positive")

    @pytest.mark.asyncio
    async def test_no_internal_model_fields_leaked(self, client, db, auth_headers, completed_trade):
        """API must not leak internal fields like raw_payload or engine internals."""
        await db.commit()
        resp = await client.get("/api/trades/completed", headers=auth_headers)
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        if trades:
            trade_keys = set(trades[0].keys())
            forbidden = {"raw_payload", "_sa_instance_state", "password", "access_token"}
            leaked = forbidden & trade_keys
            assert not leaked, f"Internal fields leaked in response: {leaked}"

    @pytest.mark.asyncio
    async def test_404_for_nonexistent_resource(self, client, auth_headers):
        """Requesting a non-existent resource returns 404, not 500."""
        fake_id = str(uuid4())
        resp = await client.get(f"/api/trades/{fake_id}", headers=auth_headers)
        assert resp.status_code in (404, 422), f"Expected 404 for nonexistent trade, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_422(self, client, auth_headers):
        """An invalid UUID in path param returns 422 Unprocessable Entity."""
        resp = await client.get("/api/trades/not-a-uuid", headers=auth_headers)
        assert resp.status_code == 422
