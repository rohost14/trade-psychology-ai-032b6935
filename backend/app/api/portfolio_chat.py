"""
Portfolio AI Chat

MCP-like dynamic tool calling over the user's Zerodha portfolio.
All tools read from Redis cache — zero KiteConnect API calls during chat.
Data freshness guaranteed by lazy sync (on cache miss) + postback webhook.

Tools available to the LLM:
  get_holdings()           → equity CNC holdings + live LTP from KiteTicker Redis cache
  get_mf_holdings()        → mutual fund holdings
  get_margins()            → available cash, used margin, collateral
  get_open_positions()     → open F&O/MIS/NRML positions (from DB)
  get_sector_exposure()    → portfolio sector breakdown (computed at sync time)
  get_holding_detail(sym)  → details for a specific equity holding

Chat history is persisted to portfolio_chat_sessions table.
On next visit: last session messages injected as context + flashback card shown.
"""

import json
import logging
from collections import defaultdict, deque
from datetime import datetime, date, timezone, timedelta
from typing import AsyncGenerator, List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.models.position import Position
from app.models.broker_account import BrokerAccount
from app.models.portfolio_chat_session import PortfolioChatSession
from app.models.trade import Trade

router = APIRouter()
logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# ── Nifty 50 approximate sector weights (2024) for overweight/underweight analysis
NIFTY50_SECTOR_WEIGHTS = {
    "Banking": 25.0,
    "IT": 13.0,
    "Energy": 12.0,
    "Finance": 8.0,
    "FMCG": 7.5,
    "Auto": 7.0,
    "Pharma": 5.0,
    "Capital Goods": 4.5,
    "Metals": 4.0,
    "Insurance": 3.0,
    "Telecom": 3.0,
    "Consumer": 2.5,
    "Cement": 2.0,
    "Real Estate": 1.5,
    "Chemicals": 1.0,
}

# ── Popular Indian MF name patterns → category + approx expense ratio (Direct plans)
# Matched via substring search on lowercased fund name from Kite
MF_METADATA: list[tuple[str, dict]] = [
    # Large Cap
    ("mirae asset large cap",     {"category": "Large Cap", "expense_ratio_approx": "0.52%"}),
    ("axis bluechip",             {"category": "Large Cap", "expense_ratio_approx": "0.54%"}),
    ("hdfc top 100",              {"category": "Large Cap", "expense_ratio_approx": "0.82%"}),
    ("nippon large cap",          {"category": "Large Cap", "expense_ratio_approx": "0.73%"}),
    ("sbi bluechip",              {"category": "Large Cap", "expense_ratio_approx": "0.82%"}),
    ("icici pru bluechip",        {"category": "Large Cap", "expense_ratio_approx": "0.89%"}),
    ("kotak bluechip",            {"category": "Large Cap", "expense_ratio_approx": "0.65%"}),
    ("canara robeco bluechip",    {"category": "Large Cap", "expense_ratio_approx": "0.32%"}),
    # Mid Cap
    ("axis midcap",               {"category": "Mid Cap", "expense_ratio_approx": "0.55%"}),
    ("kotak emerging equity",     {"category": "Mid Cap", "expense_ratio_approx": "0.50%"}),
    ("nippon india growth",       {"category": "Mid Cap", "expense_ratio_approx": "0.84%"}),
    ("hdfc mid-cap opportunities",{"category": "Mid Cap", "expense_ratio_approx": "0.79%"}),
    ("sbi magnum midcap",         {"category": "Mid Cap", "expense_ratio_approx": "0.91%"}),
    ("pgim india midcap",         {"category": "Mid Cap", "expense_ratio_approx": "0.41%"}),
    ("edelweiss mid cap",         {"category": "Mid Cap", "expense_ratio_approx": "0.44%"}),
    # Small Cap
    ("axis small cap",            {"category": "Small Cap", "expense_ratio_approx": "0.57%"}),
    ("sbi small cap",             {"category": "Small Cap", "expense_ratio_approx": "0.74%"}),
    ("nippon small cap",          {"category": "Small Cap", "expense_ratio_approx": "0.76%"}),
    ("kotak small cap",           {"category": "Small Cap", "expense_ratio_approx": "0.62%"}),
    ("hdfc small cap",            {"category": "Small Cap", "expense_ratio_approx": "0.64%"}),
    ("quant small cap",           {"category": "Small Cap", "expense_ratio_approx": "0.62%"}),
    ("canara robeco small cap",   {"category": "Small Cap", "expense_ratio_approx": "0.46%"}),
    # Flexi / Multi Cap
    ("hdfc flexi cap",            {"category": "Flexi Cap", "expense_ratio_approx": "0.79%"}),
    ("parag parikh flexi cap",    {"category": "Flexi Cap", "expense_ratio_approx": "0.63%"}),
    ("axis flexi cap",            {"category": "Flexi Cap", "expense_ratio_approx": "0.76%"}),
    ("quant flexi cap",           {"category": "Flexi Cap", "expense_ratio_approx": "0.59%"}),
    ("kotak flexi cap",           {"category": "Flexi Cap", "expense_ratio_approx": "0.60%"}),
    ("icici pru flexicap",        {"category": "Flexi Cap", "expense_ratio_approx": "0.69%"}),
    # ELSS (Tax Saving)
    ("axis long term equity",     {"category": "ELSS (Tax Saver, 3yr lock-in)", "expense_ratio_approx": "0.70%"}),
    ("mirae asset elss",          {"category": "ELSS (Tax Saver, 3yr lock-in)", "expense_ratio_approx": "0.51%"}),
    ("quant elss",                {"category": "ELSS (Tax Saver, 3yr lock-in)", "expense_ratio_approx": "0.56%"}),
    ("sbi long term equity",      {"category": "ELSS (Tax Saver, 3yr lock-in)", "expense_ratio_approx": "0.98%"}),
    ("hdfc taxsaver",             {"category": "ELSS (Tax Saver, 3yr lock-in)", "expense_ratio_approx": "1.03%"}),
    ("dsp tax saver",             {"category": "ELSS (Tax Saver, 3yr lock-in)", "expense_ratio_approx": "0.75%"}),
    # Index Funds
    ("nifty 50 index",            {"category": "Index Fund (Nifty 50)", "expense_ratio_approx": "0.10–0.20%"}),
    ("nifty next 50",             {"category": "Index Fund (Nifty Next 50)", "expense_ratio_approx": "0.18%"}),
    ("nifty 500",                 {"category": "Index Fund (Nifty 500)", "expense_ratio_approx": "0.20%"}),
    ("sensex index",              {"category": "Index Fund (Sensex)", "expense_ratio_approx": "0.10%"}),
    ("nifty midcap 150",          {"category": "Index Fund (Mid Cap)", "expense_ratio_approx": "0.25%"}),
    # Hybrid
    ("balanced advantage",        {"category": "Balanced Advantage / Dynamic Asset Allocation", "expense_ratio_approx": "0.60–0.90%"}),
    ("aggressive hybrid",         {"category": "Aggressive Hybrid", "expense_ratio_approx": "0.70–1.0%"}),
    ("equity savings",            {"category": "Equity Savings", "expense_ratio_approx": "0.50%"}),
    ("arbitrage fund",            {"category": "Arbitrage Fund", "expense_ratio_approx": "0.40%"}),
    # Debt
    ("liquid fund",               {"category": "Liquid Fund", "expense_ratio_approx": "0.10–0.20%"}),
    ("overnight fund",            {"category": "Overnight Fund", "expense_ratio_approx": "0.10%"}),
    ("short duration",            {"category": "Short Duration Debt", "expense_ratio_approx": "0.30%"}),
    ("gilt fund",                 {"category": "Gilt Fund", "expense_ratio_approx": "0.25%"}),
    ("corporate bond",            {"category": "Corporate Bond", "expense_ratio_approx": "0.35%"}),
]


def _get_mf_metadata(fund_name: str) -> Optional[dict]:
    """Fuzzy match a Kite fund name to MF metadata via substring search."""
    low = fund_name.lower()
    for pattern, meta in MF_METADATA:
        if pattern in low:
            return meta
    return None


# Use GPT-4o-mini via OpenRouter — reliable tool calling support in OpenAI format
PORTFOLIO_MODEL = "openai/gpt-4o-mini"

SYSTEM_PROMPT = """You are a smart, candid portfolio analysis assistant for Indian retail investors using Zerodha.
You have access to real-time data from the user's Zerodha account via tools. Think of yourself as a brilliant friend who deeply understands Indian stock markets and personal finance — direct, specific, and genuinely helpful.

CRITICAL TOOL USAGE RULES — follow exactly:
- ALWAYS call the relevant tool immediately. NEVER ask permission. NEVER say "shall I fetch" or "would you like me to".
- Holdings/stocks/portfolio value → get_holdings()
- Mutual funds/MF/SIP → get_mf_holdings()
- Cash/margin/available funds → get_margins()
- Open trades/F&O/intraday positions → get_open_positions()
- Sector/diversification/concentration → get_sector_exposure()
- Specific stock detail or "what does X do" → get_holding_detail(symbol)
- Tax/LTCG/STCG/holding period/harvesting/when can I sell tax-free → get_tax_positions()
- For multi-part questions, call multiple tools in sequence.

WHAT YOU CAN ANALYSE:

1. PORTFOLIO OVERVIEW: Total value, invested amount, overall P&L, top gainers/losers. Call get_holdings().
2. CONCENTRATION RISK: Flag single stock >20% of portfolio or single sector >35%. Call get_holdings() + get_sector_exposure().
3. TAX ANALYSIS (always use get_tax_positions for anything tax-related):
   - STCG (held <1 year): taxed at 20%. LTCG (held ≥1 year): taxed at 12.5%, ₹1,25,000/year exempt.
   - "Crossing soon" = holdings becoming LTCG in <60 days — advise holding a bit longer.
   - Tax-loss harvesting: STCL offsets STCG+LTCG; LTCL offsets only LTCG.
   - What-if: "sell X shares → STCG = ₹Y, tax ≈ ₹Z".
4. HOLDING PERIOD: How long each stock held, days to LTCG, which are already LTCG.
5. SECTOR DIVERSIFICATION: get_sector_exposure() returns your weights + Nifty 50 benchmarks. Flag 2×+ overweights.
6. MUTUAL FUNDS: get_mf_holdings() returns category + approx expense ratio per fund. Flag high-expense funds, category overlaps, ELSS lock-in.
7. REBALANCING: Compare sector vs Nifty benchmarks. Suggest trimming overweights, adding underweights.
8. WHAT-IF SCENARIOS: Compute exact P&L and tax using holdings + tax position data.
9. HOLDINGS EXPLAINER: Explain what any company does — business model, segments, macro themes.
10. MARGIN: Available cash, leverage ratio, collateral.

STYLE:
- Direct and specific. Give actual numbers, not vague generalisations.
- Currency in ₹ Indian format: ₹1,45,000 (not ₹145000).
- Use bullet points for lists, markdown tables for comparisons.
- Tax data only covers trades since account was connected — older trades may be missing.
- If a field is null or unavailable (e.g. entry_time), just omit it — do NOT comment on it.

STRICT BOUNDARIES — NEVER cross these:
- NEVER give trading psychology advice, emotional coaching, or behavioural commentary.
- NEVER tell the user to "keep detailed notes", "track emotions", "reflect on your decision-making", or anything of that nature.
- NEVER lecture about discipline, mindset, or trading habits.
- NEVER moralize about whether a trade was "lucky" or "strategic".
- If the user asks something outside portfolio analysis (e.g. entry timing, emotions, discipline) — simply say "I focus on portfolio analysis only — for trading psychology insights, use the AI Coach."
- You are a FINANCIAL DATA ANALYST, not a coach."""

# Tool definitions in OpenAI format (required by OpenRouter for all models)
PORTFOLIO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_holdings",
            "description": "Get the user's equity holdings (CNC/delivery stocks) with quantity, average buy price, current LTP, and unrealized P&L. Use this for any question about stocks, number of holdings, portfolio value, or individual equity positions.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_mf_holdings",
            "description": "Get the user's mutual fund holdings with units, NAV, current value, P&L, fund category, and approximate expense ratio. Use this for questions about mutual funds, SIPs, fund overlap, ELSS, or expense ratios.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_margins",
            "description": "Get account margin details: available cash, used margin, collateral value, and exposure. Use this for questions about available funds or margin utilisation.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_open_positions",
            "description": "Get currently open intraday/F&O/NRML positions with live unrealized P&L. Use this for questions about active trades today.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sector_exposure",
            "description": "Get portfolio sector breakdown with percentage allocation AND Nifty 50 benchmark weights for each sector. Shows overweight/underweight vs index. Use this for diversification, concentration, or rebalancing questions.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_holding_detail",
            "description": "Get detailed information about a specific equity holding by its NSE symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "NSE tradingsymbol, e.g. INFY, TCS, HDFCBANK",
                    }
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tax_positions",
            "description": (
                "Compute LTCG/STCG tax analysis for all equity holdings using FIFO on trade history. "
                "Returns: per-stock holding batches with purchase dates, holding days, LTCG vs STCG classification, "
                "estimated tax, 'crossing LTCG soon' list (within 60 days), and tax-loss harvesting candidates. "
                "Use this for ANY question about: tax, LTCG, STCG, holding period, when to sell, "
                "tax-loss harvesting, 1-year threshold, or 'which stocks cross 1 year soon'."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def _get_redis():
    import redis as redis_lib
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


def _get_cached_ltp(r, instrument_token) -> Optional[float]:
    if not instrument_token:
        return None
    val = r.get(f"ltp:{instrument_token}")
    return float(val) if val else None


async def _ensure_portfolio_synced(broker_account_id: UUID, db: AsyncSession):
    """Trigger sync if cache is cold. Returns immediately — sync runs in Celery."""
    r = _get_redis()
    has_holdings = r.exists(f"portfolio:holdings:{broker_account_id}")
    if not has_holdings:
        from app.tasks.portfolio_sync_tasks import sync_portfolio_for_account
        sync_portfolio_for_account.delay(str(broker_account_id))


async def _execute_tool(name: str, args: dict, broker_account_id: UUID, db: AsyncSession) -> dict:
    """Execute a portfolio tool. All reads from Redis/DB — zero KiteConnect calls."""
    r = _get_redis()

    if name == "get_holdings":
        raw = r.get(f"portfolio:holdings:{broker_account_id}")
        holdings = json.loads(raw) if raw else []
        total_invested = 0.0
        total_current = 0.0
        for h in holdings:
            ltp = _get_cached_ltp(r, h.get("instrument_token")) or float(h.get("last_price", 0))
            avg = float(h.get("average_price", 0))
            qty = int(h.get("quantity", 0))
            h["ltp"] = round(ltp, 2)
            h["unrealized_pnl"] = round((ltp - avg) * qty, 2)
            h["unrealized_pnl_pct"] = round((ltp - avg) / avg * 100, 2) if avg else 0
            total_invested += avg * qty
            total_current += ltp * qty
        return {
            "holdings": holdings,
            "summary": {
                "count": len(holdings),
                "total_invested": round(total_invested, 2),
                "current_value": round(total_current, 2),
                "total_pnl": round(total_current - total_invested, 2),
                "total_pnl_pct": round((total_current - total_invested) / total_invested * 100, 2) if total_invested else 0,
            },
        }

    elif name == "get_mf_holdings":
        raw = r.get(f"portfolio:mf_holdings:{broker_account_id}")
        mf = json.loads(raw) if raw else []
        total_invested = 0.0
        total_current = 0.0
        for fund in mf:
            units = float(fund.get("quantity") or fund.get("units", 0))
            avg = float(fund.get("average_price", 0))
            nav = float(fund.get("last_price", 0))
            fund["invested"] = round(units * avg, 2)
            fund["current_value"] = round(units * nav, 2)
            fund["unrealized_pnl"] = round((nav - avg) * units, 2)
            fund["unrealized_pnl_pct"] = round((nav - avg) / avg * 100, 2) if avg else 0
            fund_name = fund.get("fund", fund.get("tradingsymbol", ""))
            meta = _get_mf_metadata(fund_name)
            if meta:
                fund["category"] = meta["category"]
                fund["expense_ratio_approx"] = meta["expense_ratio_approx"]
            else:
                fund["category"] = "Unknown"
                fund["expense_ratio_approx"] = "N/A"
            total_invested += fund["invested"]
            total_current += fund["current_value"]
        return {
            "mf_holdings": mf,
            "count": len(mf),
            "summary": {
                "total_invested": round(total_invested, 2),
                "current_value": round(total_current, 2),
                "total_pnl": round(total_current - total_invested, 2),
                "total_pnl_pct": round((total_current - total_invested) / total_invested * 100, 2) if total_invested else 0,
            },
        }

    elif name == "get_margins":
        # Margins are cached by existing margin service — fall back to live fetch if needed
        raw = r.get(f"margins:{broker_account_id}")
        if raw:
            data = json.loads(raw)
        else:
            # Live fetch as fallback (rare — margins are kept fresh by trade sync)
            result = await db.execute(
                select(BrokerAccount).where(BrokerAccount.id == broker_account_id)
            )
            account = result.scalar_one_or_none()
            if account and account.access_token:
                from app.services.zerodha_service import get_service_for_account
                svc = get_service_for_account(account)
                token = account.get_decrypted_token()
                data = await svc.get_margins(token)
            else:
                data = {}
        equity = data.get("equity", {})
        avail = equity.get("available", {})
        used = equity.get("utilised", {})
        return {
            "available_cash": avail.get("cash", 0),
            "collateral": avail.get("collateral", 0),
            "live_balance": avail.get("live_balance", 0),
            "used_margin": used.get("debits", 0),
            "span": used.get("span", 0),
            "exposure": used.get("exposure", 0),
        }

    elif name == "get_open_positions":
        result = await db.execute(
            select(Position).where(
                Position.broker_account_id == broker_account_id,
                Position.status == "open",
            )
        )
        positions = result.scalars().all()

        # For positions missing first_entry_time, look up the earliest trade today
        today_start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start.astimezone(timezone.utc)
        trade_result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.broker_account_id == broker_account_id,
                    Trade.transaction_type == "BUY",
                    Trade.order_timestamp >= today_start_utc,
                    Trade.filled_quantity > 0,
                )
            ).order_by(Trade.order_timestamp.asc())
        )
        today_trades = trade_result.scalars().all()
        # Build {symbol: earliest_buy_time} map for today
        earliest_trade_time: dict[str, datetime] = {}
        for t in today_trades:
            sym = t.tradingsymbol.upper()
            if sym not in earliest_trade_time and t.order_timestamp:
                earliest_trade_time[sym] = t.order_timestamp

        pos_list = []
        for p in positions:
            ltp = _get_cached_ltp(r, p.instrument_token) if p.instrument_token else None
            # Prefer first_entry_time; fall back to earliest trade today; omit if neither
            entry_ts = p.first_entry_time or earliest_trade_time.get(p.tradingsymbol.upper())
            entry_time_str = entry_ts.astimezone(IST).strftime("%H:%M IST") if entry_ts else None
            row = {
                "symbol": p.tradingsymbol,
                "product": p.product,
                "quantity": p.total_quantity,
                "average_price": float(p.average_entry_price or 0),
                "ltp": ltp,
                "unrealized_pnl": float(p.unrealized_pnl or p.pnl or 0),
            }
            if entry_time_str:
                row["entry_time"] = entry_time_str
            pos_list.append(row)
        return {"open_positions": pos_list, "count": len(pos_list)}

    elif name == "get_sector_exposure":
        raw = r.get(f"portfolio:sector:{broker_account_id}")
        sector: dict = json.loads(raw) if raw else {}
        # Annotate each sector with Nifty 50 benchmark weight and deviation
        enriched = {}
        for sec_name, data in sector.items():
            nifty_wt = NIFTY50_SECTOR_WEIGHTS.get(sec_name, 0.0)
            portfolio_pct = data.get("pct", 0.0) if isinstance(data, dict) else float(data)
            enriched[sec_name] = {
                "portfolio_pct": round(portfolio_pct, 1),
                "nifty50_pct": nifty_wt,
                "deviation": round(portfolio_pct - nifty_wt, 1),
                "status": (
                    "overweight" if portfolio_pct > nifty_wt * 1.5
                    else "underweight" if nifty_wt > 0 and portfolio_pct < nifty_wt * 0.5
                    else "neutral"
                ),
            }
        # Also list any Nifty sectors the user has zero exposure to
        zero_exposure = [
            {"sector": s, "nifty50_pct": w, "portfolio_pct": 0.0, "status": "not_held"}
            for s, w in NIFTY50_SECTOR_WEIGHTS.items()
            if s not in enriched and w >= 3.0
        ]
        return {
            "sector_exposure": enriched,
            "zero_exposure_sectors": zero_exposure,
            "nifty50_weights_note": "Nifty 50 sector weights are approximate 2024 figures for overweight/underweight comparison.",
        }

    elif name == "get_holding_detail":
        symbol = args.get("symbol", "").upper().strip()
        raw = r.get(f"portfolio:holdings:{broker_account_id}")
        holdings = json.loads(raw) if raw else []
        match = next((h for h in holdings if h.get("tradingsymbol") == symbol), None)
        if not match:
            return {"error": f"{symbol} not found in your holdings"}
        ltp = _get_cached_ltp(r, match.get("instrument_token")) or float(match.get("last_price", 0))
        avg = float(match.get("average_price", 0))
        qty = int(match.get("quantity", 0))
        match["ltp"] = round(ltp, 2)
        match["unrealized_pnl"] = round((ltp - avg) * qty, 2)
        match["unrealized_pnl_pct"] = round((ltp - avg) / avg * 100, 2) if avg else 0
        return match

    elif name == "get_tax_positions":
        return await _tool_get_tax_positions(broker_account_id, db, r)

    return {"error": f"Unknown tool: {name}"}


async def _stream_chat(
    user_message: str,
    history: list,
    broker_account_id: UUID,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    SSE generator with tool calling loop.
    LLM decides which tools to call → we execute against Redis/DB → LLM continues.
    """
    if not settings.OPENROUTER_API_KEY:
        yield f"data: {json.dumps({'content': 'AI service not configured.'})}\n\n"
        return

    # Build message history (inject last 10 messages max)
    messages = []
    for msg in history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://trademental.ai",
        "X-Title": "TradeMentor AI Portfolio Chat",
    }

    # Tool calling loop — LLM may call multiple tools before final response
    tool_call_count = 0
    max_tool_calls = 5  # safety cap

    async with httpx.AsyncClient(timeout=60.0) as client:
        while tool_call_count < max_tool_calls:
            payload = {
                "model": PORTFOLIO_MODEL,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                "tools": PORTFOLIO_TOOLS,
                "tool_choice": "auto",
                "max_tokens": 1500,
                "temperature": 0.3,
            }

            try:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.error(f"OpenRouter error in portfolio chat: {e}")
                yield f"data: {json.dumps({'content': 'Sorry, I could not connect to the AI service. Please try again.'})}\n\n"
                return

            data = resp.json()
            choice = data.get("choices", [{}])[0]
            finish_reason = choice.get("finish_reason", "stop")
            assistant_msg = choice.get("message", {})
            content = assistant_msg.get("content", "")
            tool_calls = assistant_msg.get("tool_calls", [])

            # Add assistant turn to message history (OpenAI format)
            asst_turn: dict = {"role": "assistant", "content": content or ""}
            if tool_calls:
                asst_turn["tool_calls"] = tool_calls
            messages.append(asst_turn)

            # OpenAI format: finish_reason == "tool_calls" OR tool_calls list is non-empty
            if tool_calls and (finish_reason == "tool_calls" or finish_reason != "stop"):
                tool_call_count += len(tool_calls)
                tool_results = []
                for tc in tool_calls:
                    fn_name = tc.get("function", {}).get("name", "")
                    fn_args_str = tc.get("function", {}).get("arguments", "{}")
                    try:
                        fn_args = json.loads(fn_args_str)
                    except Exception:
                        fn_args = {}
                    result = await _execute_tool(fn_name, fn_args, broker_account_id, db)
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": json.dumps(result),
                    })
                messages.extend(tool_results)
                continue

            # LLM is done calling tools — stream the final text response
            if content:
                # Stream word by word for smooth UX
                words = content.split(" ")
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            break

    yield "data: [DONE]\n\n"


# ── Pydantic models ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []
    session_id: Optional[str] = None  # existing session to continue


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/snapshot")
async def get_portfolio_snapshot(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Return cached portfolio snapshot for the UI left panel.
    Triggers background sync if cache is cold (first visit today).
    Zero KiteConnect API calls on cache hit.
    """
    await _ensure_portfolio_synced(broker_account_id, db)

    r = _get_redis()
    synced_at_raw = r.get(f"portfolio:synced_at:{broker_account_id}")

    # Build snapshot from Redis
    holdings_raw = r.get(f"portfolio:holdings:{broker_account_id}")
    mf_raw = r.get(f"portfolio:mf_holdings:{broker_account_id}")
    sector_raw = r.get(f"portfolio:sector:{broker_account_id}")

    holdings = json.loads(holdings_raw) if holdings_raw else []
    mf_holdings = json.loads(mf_raw) if mf_raw else []
    sector_exposure = json.loads(sector_raw) if sector_raw else {}

    # Enrich holdings with live LTP
    total_invested = 0.0
    total_current = 0.0
    for h in holdings:
        ltp = _get_cached_ltp(r, h.get("instrument_token")) or float(h.get("last_price", 0))
        avg = float(h.get("average_price", 0))
        qty = int(h.get("quantity", 0))
        h["ltp"] = round(ltp, 2)
        h["unrealized_pnl"] = round((ltp - avg) * qty, 2)
        total_invested += avg * qty
        total_current += ltp * qty

    return {
        "as_of": synced_at_raw,
        "synced": bool(holdings_raw),
        "holdings_summary": {
            "count": len(holdings),
            "total_invested": round(total_invested, 2),
            "current_value": round(total_current, 2),
            "total_pnl": round(total_current - total_invested, 2),
            "total_pnl_pct": round((total_current - total_invested) / total_invested * 100, 2) if total_invested else 0,
        },
        "holdings": sorted(holdings, key=lambda h: h.get("ltp", 0) * h.get("quantity", 0), reverse=True)[:20],
        "mf_holdings": mf_holdings[:20],
        "sector_exposure": sector_exposure,
    }


@router.get("/session")
async def get_last_session(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Return the last portfolio chat session for the flashback card."""
    result = await db.execute(
        select(PortfolioChatSession)
        .where(PortfolioChatSession.broker_account_id == broker_account_id)
        .order_by(desc(PortfolioChatSession.started_at))
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    return {
        "id": str(session.id),
        "summary": session.summary,
        "message_count": session.message_count,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "messages": session.messages[-10:] if session.messages else [],
    }


@router.post("/message")
async def chat_message(
    body: ChatRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    SSE streaming portfolio chat with dynamic tool calling.
    LLM calls whichever tools it needs; all tools read from Redis/DB.
    """
    await _ensure_portfolio_synced(broker_account_id, db)

    history = [{"role": m.role, "content": m.content} for m in (body.history or [])]

    async def generate():
        full_response = []
        async for chunk in _stream_chat(body.message, history, broker_account_id, db):
            yield chunk
            # Accumulate response text for session persistence
            if chunk.startswith("data: {"):
                try:
                    data = json.loads(chunk[6:])
                    if "content" in data:
                        full_response.append(data["content"])
                except Exception:
                    pass

        # Persist session after response completes
        try:
            full_text = "".join(full_response)
            await _persist_session(
                broker_account_id=broker_account_id,
                user_message=body.message,
                assistant_response=full_text,
                prior_history=history,
                session_id=body.session_id,
                db=db,
            )
        except Exception as e:
            logger.warning(f"Session persist failed (non-fatal): {e}")

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _persist_session(
    broker_account_id: UUID,
    user_message: str,
    assistant_response: str,
    prior_history: list,
    session_id: Optional[str],
    db: AsyncSession,
):
    """Upsert session with the latest messages. Cap at 30 messages."""
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()

    new_msgs = [
        {"role": "user", "content": user_message, "timestamp": now_iso},
        {"role": "assistant", "content": assistant_response, "timestamp": now_iso},
    ]

    # Try to continue existing session (same session_id, or most recent within 2 hours)
    session = None
    if session_id:
        result = await db.execute(
            select(PortfolioChatSession).where(
                PortfolioChatSession.id == UUID(session_id),
                PortfolioChatSession.broker_account_id == broker_account_id,
            )
        )
        session = result.scalar_one_or_none()

    if not session:
        # Find an open session within the last 2 hours
        from datetime import timedelta
        cutoff = now_utc - timedelta(hours=2)
        result = await db.execute(
            select(PortfolioChatSession)
            .where(
                PortfolioChatSession.broker_account_id == broker_account_id,
                PortfolioChatSession.started_at >= cutoff,
                PortfolioChatSession.ended_at.is_(None),
            )
            .order_by(desc(PortfolioChatSession.started_at))
            .limit(1)
        )
        session = result.scalar_one_or_none()

    if session:
        # Append to existing session, cap at 30 messages
        existing = session.messages or []
        combined = existing + new_msgs
        session.messages = combined[-30:]
        session.message_count = len(session.messages)
        session.updated_at = now_utc
        # Update summary to reflect latest topic
        if len(user_message) > 10:
            session.summary = f"Last: {user_message[:120]}..."
    else:
        # New session
        session = PortfolioChatSession(
            broker_account_id=broker_account_id,
            messages=new_msgs,
            message_count=2,
            summary=f"Last: {user_message[:120]}..." if len(user_message) > 10 else None,
        )
        db.add(session)

    await db.commit()
