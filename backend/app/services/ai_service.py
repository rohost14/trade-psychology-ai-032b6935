import os
import httpx
import json
from typing import List, Dict, Optional
import logging
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)

class AIService:
    """
    AI service using OpenRouter API for LLM calls.
    Supports reasoning models for better trading psychology analysis.
    """
    
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set. AI features will use fallback logic.")
        else:
            logger.info(f"AI Service initialized with OpenRouter key (configured={bool(self.api_key)})")

        # Model selection
        self.primary_model = "anthropic/claude-3.5-haiku"   # fast, cheap — default for chat
        self.deep_model    = "anthropic/claude-sonnet-4-5"   # deep analysis — user-triggered
        self.reasoning_model = "openai/gpt-4o-mini"
        self.free_model = "google/gemini-flash-1.5-8b"

    async def _make_request(
        self,
        messages: List[Dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        use_reasoning: bool = False
    ) -> Optional[Dict]:
        """Make async request to OpenRouter API using httpx."""

        if not self.api_key:
            logger.warning("No API key configured, skipping AI request")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://trademental.ai",
            "X-Title": "TradeMentor AI"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        if use_reasoning:
            payload["reasoning"] = {"enabled": True}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.base_url, headers=headers, json=payload)

            if response.status_code != 200:
                logger.error(f"OpenRouter API error: {response.status_code} - {response.text[:300]}")
                return None

            result = response.json()
            return result['choices'][0]['message']

        except httpx.TimeoutException:
            logger.error("OpenRouter API timeout")
            return None
        except Exception as e:
            logger.error(f"OpenRouter API request failed: {e}")
            return None
    
    async def generate_trading_persona(
        self, 
        patterns_detected: List[Dict],
        total_trades: int,
        emotional_tax: float,
        time_performance: Dict
    ) -> Dict:
        """
        Generate comprehensive trading persona using AI reasoning.
        
        Returns: {
            "persona": "The Impulsive Scalper",
            "description": "2-3 sentence psychological profile",
            "strengths": ["strength 1", "strength 2", "strength 3"],
            "weaknesses": ["weakness 1", "weakness 2", "weakness 3"],
            "next_steps": "Specific actionable advice"
        }
        """
        
        # Build detailed pattern summary
        negative_patterns = [p for p in patterns_detected if not p.get('is_positive', False)]
        positive_patterns = [p for p in patterns_detected if p.get('is_positive', False)]
        
        pattern_details = []
        for p in negative_patterns:
            pattern_details.append(
                f"• {p['name']} (Severity: {p['severity'].upper()}) - "
                f"Detected {p['frequency']} times, Cost: ₹{p.get('pnl_impact', 0):.0f}"
            )
        
        positive_details = []
        for p in positive_patterns:
            positive_details.append(f"• {p['name']} - {p.get('frequency', 0)} instances")
        
        # Build performance context
        perf_context = ""
        if time_performance:
            best_hour = time_performance.get('best_hour', 'N/A')
            best_wr = time_performance.get('best_hour_winrate', 0)
            worst_hour = time_performance.get('worst_hour', 'N/A')
            worst_wr = time_performance.get('worst_hour_winrate', 0)
            
            perf_context = f"""
**Time-Based Performance:**
- Best trading window: {best_hour} ({best_wr}% win rate)
- Worst trading window: {worst_hour} ({worst_wr}% win rate)
"""
        
        system_prompt = """You are an expert trading psychologist specializing in behavioral finance and F&O trading psychology. Your role is to analyze behavioral patterns and classify traders into psychological profiles with clinical precision.

You MUST classify the trader into ONE of these 6 personas:
1. **The Tilted Gambler** - Multiple severe patterns, complete emotional dysregulation, high blow-up risk
2. **The Recovery Chaser** - Martingale behavior, loss aversion, doubling down to recover
3. **The Compulsive Scalper** - Overtrading, chop addiction, confusing activity with progress
4. **The Impulsive Scalper** - Revenge trading, FOMO, poor impulse control
5. **The Death by Cuts Trader** - Loss normalization, death by a thousand small losses
6. **The Developing Trader** - Improving discipline, manageable issues, on right path

Be brutally honest but constructive. This is financial survival, not a feel-good session."""

        user_prompt = f"""Analyze this F&O trader's psychological profile:

**Trading Statistics:**
- Total positions analyzed: {total_trades}
- Emotional tax (cost of emotions): ₹{emotional_tax:.2f}

**Negative Behavioral Patterns:**
{chr(10).join(pattern_details) if pattern_details else '- No major issues detected (excellent!)'}

**Positive Behavioral Patterns:**
{chr(10).join(positive_details) if positive_details else '- None detected yet (still developing discipline)'}

{perf_context}

**Output Requirements:**
Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "persona": "exact name from the 6 personas above",
  "description": "2-3 sentences: their current psychological state, primary failure mode, and immediate risk level",
  "strengths": ["3 specific behavioral strengths based on data", "use actual pattern names when relevant", "be specific not generic"],
  "weaknesses": ["3 specific high-impact weaknesses", "prioritize by severity and cost", "use detected pattern names"],
  "next_steps": "One focused paragraph: the ONE behavior change that will have biggest impact right now. Be specific: what to do, when, and how to track it. Include time-based recommendations if relevant."
}}

Be direct and practical. Focus on behavior modification, not theory."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Use reasoning model for complex psychological analysis
        response = await self._make_request(
            messages=messages,
            model=self.reasoning_model,
            temperature=0.7,
            max_tokens=1000,
            use_reasoning=True
        )
        
        if not response:
            logger.warning("AI persona generation failed, using fallback")
            return self._fallback_persona(negative_patterns, positive_patterns)
        
        try:
            content = response.get('content', '').strip()
            
            # Clean markdown fences
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            persona_data = json.loads(content)
            
            # Validate required fields
            required_fields = ['persona', 'description', 'strengths', 'weaknesses', 'next_steps']
            if not all(field in persona_data for field in required_fields):
                raise ValueError("Missing required fields in AI response")
            
            logger.info(f"✅ AI Persona generated: {persona_data['persona']}")
            
            # Log reasoning if available (for debugging)
            if 'reasoning_details' in response:
                logger.debug(f"AI reasoning tokens: {response['reasoning_details'].get('tokens_used', 0)}")
            
            return persona_data
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse AI persona response: {e}")
            logger.debug(f"Raw response: {response.get('content', '')[:500]}")
            return self._fallback_persona(negative_patterns, positive_patterns)
    
    def _fallback_persona(self, negative_patterns: List[Dict], positive_patterns: List[Dict]) -> Dict:
        """Rule-based fallback when AI unavailable."""
        logger.warning(f"AI_FALLBACK: Using rule-based persona (negative={len(negative_patterns)}, positive={len(positive_patterns)})")

        pattern_names = [p['name'] for p in negative_patterns]
        
        # Rule-based classification
        if len(negative_patterns) >= 5:
            persona = "The Tilted Gambler"
            desc = "Multiple destructive patterns active simultaneously. High risk of account blow-up. Immediate intervention required."
        elif any('Martingale' in name or 'Recovery' in name for name in pattern_names):
            persona = "The Recovery Chaser"
            desc = "Attempting to force recovery through position sizing increases. Classic 'get back to zero' mentality. High blow-up risk."
        elif any('Revenge' in name or 'Impulse' in name for name in pattern_names):
            persona = "The Impulsive Scalper"
            desc = "Emotional decision-making dominates. FOMO and revenge trading are primary failure modes. Need strict cooldown rules."
        elif any('Overtrading' in name or 'Chop' in name for name in pattern_names):
            persona = "The Compulsive Scalper"
            desc = "Confusing activity with productivity. High trade frequency without edge. Need to focus on quality over quantity."
        elif any('Loss Normalization' in name for name in pattern_names):
            persona = "The Death by Cuts Trader"
            desc = "Small losses accumulating systematically. Lack of hard stops. Death by a thousand cuts pattern."
        else:
            persona = "The Developing Trader"
            desc = "Building discipline with some manageable issues. On the right path but needs consistency."
        
        return {
            "persona": persona,
            "description": desc,
            "strengths": [
                "Following basic risk management",
                "Consistent position sizing" if len(positive_patterns) > 0 else "Executing planned trades",
                "Time management awareness"
            ],
            "weaknesses": [p['name'] for p in negative_patterns[:3]] if negative_patterns else ["Building foundational discipline"],
            "next_steps": f"Primary focus: Address your {negative_patterns[0]['name'] if negative_patterns else 'position sizing'}. Set a hard rule: no more than 3 trades after a loss until you've taken a 15-minute break. Track compliance daily for 2 weeks."
        }
    
    async def generate_analytics_narrative(
        self,
        tab: str,
        data: dict,
        behavior_score: int = None,
        patterns: list = None,
    ) -> dict:
        """
        Generate AI narrative for an analytics tab.
        Hybrid: LLM when API key available, rule-based templates otherwise.

        Args:
            tab: One of 'overview', 'behavior', 'performance', 'risk'
            data: Tab-specific metrics dict
            behavior_score: Optional behavior score (0-100)
            patterns: Optional list of detected pattern names

        Returns:
            {
                "narrative": "Your trading this month...",
                "key_insight": "Most impactful: ...",
                "action_item": "Consider...",
            }
        """
        # Try LLM first
        if self.api_key:
            result = await self._llm_narrative(tab, data, behavior_score, patterns)
            if result:
                logger.info(f"AI_USAGE tab={tab} model={self.primary_model} type=narrative")
                return result

        # Fallback to rule-based
        return self._rule_based_narrative(tab, data, behavior_score, patterns)

    async def _llm_narrative(
        self,
        tab: str,
        data: dict,
        behavior_score: int = None,
        patterns: list = None,
    ) -> dict | None:
        """LLM-powered narrative generation using Claude Haiku."""
        system_prompt = (
            "You are a trading psychology analyst for Indian F&O traders. "
            "Given the data below, write a concise 3-5 sentence analysis. "
            "Be specific with numbers. Use ₹ for currency. "
            "Focus on actionable insights, not generic advice."
        )

        # Build tab-specific data summary
        if tab == "overview":
            user_prompt = self._overview_prompt(data)
        elif tab == "behavior":
            user_prompt = self._behavior_prompt(data, behavior_score, patterns)
        elif tab == "performance":
            user_prompt = self._performance_prompt(data)
        elif tab == "risk":
            user_prompt = self._risk_prompt(data)
        else:
            return None

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = await self._make_request(
            messages=messages,
            model=self.primary_model,
            temperature=0.7,
            max_tokens=300,
            use_reasoning=False,
        )

        if not response:
            return None

        content = response.get("content", "").strip()
        if not content:
            return None

        # Parse structured response (LLM returns 3 sections separated by newlines)
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        narrative = lines[0] if lines else content
        key_insight = lines[1] if len(lines) > 1 else ""
        action_item = lines[2] if len(lines) > 2 else ""

        # If LLM didn't split cleanly, use full text as narrative
        if len(lines) <= 1:
            narrative = content
            key_insight = ""
            action_item = ""

        return {
            "narrative": narrative,
            "key_insight": key_insight,
            "action_item": action_item,
        }

    def _overview_prompt(self, data: dict) -> str:
        kpis = data.get("kpis", {})
        return (
            f"Analyze this trader's overview for the period:\n"
            f"- Total P&L: ₹{kpis.get('total_pnl', 0):,.2f}\n"
            f"- Trades: {kpis.get('total_trades', 0)} (Win Rate: {kpis.get('win_rate', 0)}%)\n"
            f"- Profit Factor: {kpis.get('profit_factor', 0)}\n"
            f"- Expectancy: ₹{kpis.get('expectancy', 0):,.2f}\n"
            f"- Best Day: ₹{kpis.get('largest_win', 0):,.2f}, Worst Day: ₹{kpis.get('largest_loss', 0):,.2f}\n"
            f"- Win Streak: {kpis.get('max_win_streak', 0)}, Loss Streak: {kpis.get('max_loss_streak', 0)}\n\n"
            f"Provide exactly 3 lines:\n1. A narrative paragraph (3-5 sentences)\n"
            f"2. Key Insight: one sentence starting with 'Key Insight:'\n"
            f"3. Action Item: one sentence starting with 'Action:'"
        )

    def _behavior_prompt(self, data: dict, score: int = None, patterns: list = None) -> str:
        pattern_str = ", ".join(patterns[:5]) if patterns else "None detected"
        return (
            f"Analyze this trader's behavioral patterns:\n"
            f"- Behavior Score: {score or 'N/A'}/100\n"
            f"- Patterns Detected: {pattern_str}\n"
            f"- Emotional Tax: ₹{data.get('emotional_tax', 0):,.2f}\n\n"
            f"Provide exactly 3 lines:\n1. A narrative paragraph (3-5 sentences)\n"
            f"2. Key Insight: one sentence starting with 'Key Insight:'\n"
            f"3. Action Item: one sentence starting with 'Action:'"
        )

    def _performance_prompt(self, data: dict) -> str:
        top_instr = data.get("by_instrument", [{}])[0] if data.get("by_instrument") else {}
        return (
            f"Analyze this trader's performance breakdown:\n"
            f"- Total Trades: {data.get('total_trades', 0)}\n"
            f"- Top Instrument: {top_instr.get('symbol', 'N/A')} ({top_instr.get('trades', 0)} trades, "
            f"WR: {top_instr.get('win_rate', 0)}%)\n"
            f"- Direction: LONG {data.get('by_direction', {}).get('LONG', {}).get('win_rate', 0)}% WR, "
            f"SHORT {data.get('by_direction', {}).get('SHORT', {}).get('win_rate', 0)}% WR\n\n"
            f"Provide exactly 3 lines:\n1. A narrative paragraph (3-5 sentences)\n"
            f"2. Key Insight: one sentence starting with 'Key Insight:'\n"
            f"3. Action Item: one sentence starting with 'Action:'"
        )

    def _risk_prompt(self, data: dict) -> str:
        dd = data.get("max_drawdown", {})
        return (
            f"Analyze this trader's risk metrics:\n"
            f"- Max Drawdown: ₹{dd.get('amount', 0):,.2f}\n"
            f"- Daily Volatility: ₹{data.get('daily_volatility', 0):,.2f}\n"
            f"- VaR (95%): ₹{data.get('var_95', 0):,.2f}\n"
            f"- Risk/Reward Ratio: {data.get('risk_reward_ratio', 0)}\n\n"
            f"Provide exactly 3 lines:\n1. A narrative paragraph (3-5 sentences)\n"
            f"2. Key Insight: one sentence starting with 'Key Insight:'\n"
            f"3. Action Item: one sentence starting with 'Action:'"
        )

    def _rule_based_narrative(
        self,
        tab: str,
        data: dict,
        behavior_score: int = None,
        patterns: list = None,
    ) -> dict:
        """Rule-based template narrative when LLM is unavailable."""
        if tab == "overview":
            kpis = data.get("kpis", {})
            total_pnl = kpis.get("total_pnl", 0)
            win_rate = kpis.get("win_rate", 0)
            pf = kpis.get("profit_factor", 0)
            expectancy = kpis.get("expectancy", 0)

            pnl_word = "profit" if total_pnl >= 0 else "loss"
            wr_assessment = "above average" if win_rate >= 50 else "below the 50% threshold"

            narrative = (
                f"Your net {pnl_word} of ₹{abs(total_pnl):,.0f} over {kpis.get('total_trades', 0)} trades "
                f"shows a win rate of {win_rate}%, which is {wr_assessment}. "
            )
            if pf > 1.5:
                narrative += f"Your profit factor of {pf:.2f} is strong — your wins significantly outweigh your losses. "
            elif pf > 1:
                narrative += f"Your profit factor of {pf:.2f} is positive but could improve with better loss management. "
            elif pf > 0:
                narrative += f"Your profit factor of {pf:.2f} is below 1 — losses are outweighing wins. "

            if expectancy > 0:
                key_insight = f"Key Insight: Positive expectancy of ₹{expectancy:,.0f} per trade means your edge is real."
            else:
                key_insight = f"Key Insight: Negative expectancy of ₹{expectancy:,.0f} per trade — focus on cutting losses earlier."

            action_item = "Action: Review your worst trading day and identify the pattern that caused it."
            return {"narrative": narrative, "key_insight": key_insight, "action_item": action_item}

        elif tab == "behavior":
            score = behavior_score or 50
            pattern_list = patterns or []

            if score >= 80:
                narrative = "Excellent behavioral discipline. Your patterns show strong emotional control and consistent execution."
            elif score >= 60:
                narrative = f"Moderate discipline with {len(pattern_list)} active pattern(s). Some emotional trading detected but manageable."
            else:
                narrative = f"Multiple behavioral patterns active ({len(pattern_list)}). Emotional trading is significantly impacting your P&L."

            tax = data.get("emotional_tax", 0)
            if tax > 0:
                key_insight = f"Key Insight: Emotional trading has cost you ₹{tax:,.0f} — this is recoverable with discipline changes."
            else:
                key_insight = "Key Insight: No measurable emotional tax detected. Maintain your current discipline."

            if pattern_list:
                action_item = f"Action: Focus on eliminating {pattern_list[0]} — it's your highest-impact improvement area."
            else:
                action_item = "Action: Keep journaling every trade to maintain awareness of your emotional state."
            return {"narrative": narrative, "key_insight": key_insight, "action_item": action_item}

        elif tab == "performance":
            total = data.get("total_trades", 0)
            top_instr = data.get("by_instrument", [{}])[0] if data.get("by_instrument") else {}
            symbol = top_instr.get("symbol", "your primary instrument")
            wr = top_instr.get("win_rate", 0)

            narrative = f"Across {total} trades, {symbol} is your most traded instrument with a {wr}% win rate. "
            long_wr = data.get("by_direction", {}).get("LONG", {}).get("win_rate", 0)
            short_wr = data.get("by_direction", {}).get("SHORT", {}).get("win_rate", 0)
            if long_wr > short_wr + 10:
                narrative += "You perform notably better on long trades — consider reducing short-side exposure."
            elif short_wr > long_wr + 10:
                narrative += "Your short trades outperform longs — lean into this directional edge."

            key_insight = f"Key Insight: Your best direction is {'LONG' if long_wr >= short_wr else 'SHORT'} ({max(long_wr, short_wr)}% WR)."
            action_item = "Action: Increase position size on your highest win-rate setups and reduce on the weakest."
            return {"narrative": narrative, "key_insight": key_insight, "action_item": action_item}

        elif tab == "risk":
            dd = data.get("max_drawdown", {}).get("amount", 0)
            vol = data.get("daily_volatility", 0)
            rr = data.get("risk_reward_ratio", 0)

            narrative = f"Your max drawdown of ₹{abs(dd):,.0f} "
            if abs(dd) > vol * 3:
                narrative += "is significant — over 3x your daily volatility. This suggests occasional large losses are dragging performance."
            else:
                narrative += "is within normal range relative to your daily volatility."

            if rr >= 2:
                key_insight = f"Key Insight: Your risk/reward ratio of {rr:.1f} is excellent — you're making more on wins than losing on losses."
            elif rr >= 1:
                key_insight = f"Key Insight: Risk/reward of {rr:.1f} is acceptable but ideally should be above 2.0."
            else:
                key_insight = f"Key Insight: Risk/reward of {rr:.1f} is poor — your losses are larger than your wins on average."

            action_item = "Action: Set a hard daily loss limit at 2x your average daily P&L to prevent drawdown deepening."
            return {"narrative": narrative, "key_insight": key_insight, "action_item": action_item}

        # Fallback
        return {
            "narrative": "Insufficient data for analysis. Continue trading and journaling.",
            "key_insight": "",
            "action_item": "Action: Trade at least 20 positions to enable meaningful analysis.",
        }

    async def generate_coach_insight(
        self,
        risk_state: str,
        total_pnl: float,
        patterns_active: List[str],
        recent_trades: int,
        time_of_day: str,
        user_profile_context: str = ""
    ) -> str:
        """
        Generate contextual coach message with variable tone.
        
        Tone hierarchy:
        - SAFE + profit: Friendly, encouraging (but not complacent)
        - SAFE + loss: Supportive, process-focused
        - CAUTION: Firm, warning tone
        - DANGER: Urgent, direct, commanding
        """
        
        system_prompt = f"""You are a strict but supportive F&O trading coach. Your messages are SHORT (1-2 sentences max), direct, and actionable.

Tone guidelines based on risk state:
- SAFE + profit: "Good execution. Stay disciplined." (encouraging but grounded)
- SAFE + loss: "Losses happen. Follow your plan." (supportive, process-focused)
- CAUTION: "Risk building. Watch position sizes." (firm warning)
- DANGER: "⚠️ STOP. Take a break NOW." (urgent, commanding)

Never be generic. Reference specific data when relevant."""

        user_prompt = f"""Generate insight for trader:

**Current State:**
- Risk: {risk_state.upper()}
- Today's P&L: ₹{total_pnl:.2f}
- Trades today: {recent_trades}
- Time: {time_of_day}
- Active alerts: {', '.join(patterns_active) if patterns_active else 'None'}
{user_profile_context}
Generate ONLY the coach message (1-2 sentences, no explanation, no preamble)."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._make_request(
            messages=messages,
            model=self.primary_model,  # Use fast model for simple task
            temperature=0.8,
            max_tokens=100,
            use_reasoning=False
        )
        
        if not response:
            return self._fallback_insight(risk_state, total_pnl, patterns_active)
        
        insight = response.get('content', '').strip()
        
        # Remove quotes if AI added them
        insight = insight.strip('"\'')
        
        logger.info(f"✅ AI Insight generated: {insight[:50]}...")
        return insight
    
    def _fallback_insight(self, risk_state: str, total_pnl: float, patterns_active: List[str]) -> str:
        """Fallback insight when AI unavailable."""
        logger.warning(f"AI_FALLBACK: Using rule-based insight (risk={risk_state}, pnl={total_pnl:.0f})")

        if risk_state == 'danger':
            return "⚠️ RISK BREACH. Stop trading immediately. Review your rules."
        elif risk_state == 'caution' and patterns_active:
            return f"Caution: {patterns_active[0]} detected. Reduce position sizes."
        elif risk_state == 'caution':
            return "Risk building. Stay disciplined. Watch your sizing."
        elif total_pnl > 1000:
            return "Strong execution today. Lock in gains and follow your plan. 👍"
        elif total_pnl < -1000:
            return "Down day. Stick to your process. Don't chase recovery."
        else:
            return "All clear. Trade with discipline and follow your rules."

    async def generate_whatsapp_report(
        self,
        period_days: int,
        total_pnl: float,
        trade_count: int,
        win_rate: float,
        best_trade: float,
        worst_trade: float,
        patterns_detected: List[str],
        key_strength: str,
        key_weakness: str
    ) -> str:
        """
        Generate a concise, emoji-rich WhatsApp daily/weekly report.
        """
        
        system_prompt = """You are a trading performance analyst creating a WhatsApp summary.
Format Requirements:
- Use Emojis (📈, 📉, 💰, ⚠️, 🧠)
- Be concise (bullet points)
- Structure:
  1. Header (Timeframe & P&L)
  2. Stats (Win Rate, Trades)
  3. The Good (One bullet)
  4. The Bad (One bullet)
  5. AI Insight (One punchy sentence)
"""

        user_prompt = f"""Generate WhatsApp report for last {period_days} days:

Stats:
- P&L: ₹{total_pnl:.2f}
- Trades: {trade_count}
- Win Rate: {win_rate:.1f}%
- Best: ₹{best_trade:.2f}
- Worst: ₹{worst_trade:.2f}

Analysis:
- Active Patterns: {', '.join(patterns_detected) if patterns_detected else 'None'}
- Strength: {key_strength}
- Weakness: {key_weakness}

Output the message string only."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._make_request(
            messages=messages,
            model=self.primary_model,
            temperature=0.7,
            max_tokens=250
        )
        
        if not response:
            # Fallback report
            emoji = "🟢" if total_pnl >= 0 else "🔴"
            return (
                f"{emoji} *TradeMentor Report ({period_days} Days)*\n\n"
                f"💰 P&L: ₹{total_pnl:.2f}\n"
                f"📊 Trades: {trade_count} (WR: {win_rate:.0f}%)\n\n"
                f"⚠️ Patterns: {', '.join(patterns_detected) if patterns_detected else 'None'}\n"
                f"🧠 Focus: Improve {key_weakness or 'discipline'}."
            )
            
        return response.get('content', '').strip()

    def _build_chat_system_prompt(
        self,
        trading_context: str,
        rag_context: Optional[str],
        ai_persona: str,
    ) -> str:
        """Build the system prompt used by both streaming and non-streaming chat."""
        context_section = trading_context
        if rag_context:
            context_section += f"\n\n**Retrieved Context (from user's history and knowledge base):**\n{rag_context}"

        persona_traits = {
            "coach": "Supportive and encouraging, focused on building good habits. Empathetic but firm about discipline.",
            "mentor": "Wise and experienced, shares trading wisdom from years of experience. Speaks with authority and depth.",
            "friend": "Casual and relatable, empathetic listener who speaks like a fellow trader. Uses conversational tone.",
            "strict": "No-nonsense and brutally honest, focused on accountability and discipline. Doesn't sugarcoat.",
        }
        persona_desc = persona_traits.get(ai_persona, persona_traits["coach"])

        return f"""You are TradeMentor — a behavioral coach for F&O traders. You help traders understand their OWN patterns and psychology. You have access to their REAL trading data below.

**Your personality:** {persona_desc}

**ABSOLUTE RULES — follow these without exception:**

1. ALWAYS USE THE DATA BELOW. The trading context contains their actual positions, P&L, journal entries, and behavioral patterns. When they ask about their trades, ANSWER FROM THIS DATA. Never say "I don't have access to your data" — the data IS right here.

2. TALK LIKE A REAL PERSON. You're a coach sitting across the table. Use natural, flowing sentences. No bullet points. No numbered lists. No headers. Just talk.

3. NEVER say these things:
   - "I apologize" / "I'm sorry but" / "Unfortunately"
   - "I suggest maintaining a trading journal" (THEY ALREADY HAVE ONE)
   - "Consider setting up a tracking system" (THIS APP IS THEIR TRACKING SYSTEM)
   - "Based on general best practices" (use THEIR specific data, not generic advice)

4. BE SPECIFIC ABOUT BEHAVIOR. Instead of "your recent trades show some losses", say "your BANKNIFTY trade on Monday lost ₹2,400 in 12 minutes — that's your revenge pattern showing up again." Reference actual symbols, dates, amounts from the data.

5. KEEP IT SHORT. 2–4 sentences for simple questions. Only go longer if they ask for detailed analysis.

6. USE ₹ FOR CURRENCY (Indian Rupee).

7. When data genuinely doesn't exist (zero trades), say it straight: "You haven't closed any positions in the last 7 days. Once you start trading, I'll give you real insights." Don't fill space with generic tips.

8. DIAGNOSTIC QUESTIONS REQUIRE MULTI-DIMENSIONAL ANALYSIS. When asked "what went wrong", "where did I lose money", "why did I have a bad day", or similar — do NOT answer with a single data point. Cross-reference ALL of these dimensions from the data:
   a) EXACT P&L: name the trade, the exact rupee amount lost/won
   b) SESSION CONTEXT: what % of the day's peak gains did this erase? (the "Today's Session" section has this computed already — use it)
   c) RISK MANAGEMENT: was there a behavioral alert on this trade (check alerts section, especially No Stoploss, Profit Giveaway)? How long was the position held?
   d) DECISION QUALITY: what do the journal's structured fields say? (followed_plan yes/no, setup_quality, would_repeat, deviation_reason) — synthesize WHAT THESE SIGNAL about their decision-making, don't quote the fields
   e) PATTERN: does this connect to a recurring behavior (e.g., they've hit Profit Giveaway before, or always skip SL on this type of trade)?
   Then combine (a)–(e) into ONE flowing diagnosis. Example of good output: "You built ₹5,400 today then the BajFinance trade gave back ₹4,912 — 91% of your day's peak. Your journal shows you didn't follow your plan on that trade and rated the setup 2/5. The no_stoploss alert fired on it too, meaning you held through the full loss without a defined exit. That's the pattern: you trade well when you wait for structure, but one late impulsive trade undoes the session."

9. OPEN POSITIONS ARE STILL ALIVE. If a position appears under "Currently Open Positions", its P&L is unrealized and fluctuating — it is NOT a loss or a win yet. NEVER use an open position as evidence of a behavioral pattern. NEVER say things like "your SONACOMS trade is losing" or "you're repeating your pattern on SONACOMS" — you don't know how it will close. Instead, if relevant, ask: "Do you have a stop loss on SONACOMS?" or "What's your exit plan for that position?" Treat open positions as live, uncertain situations.

10. JOURNAL ENTRIES ARE YOUR RAW MATERIAL, NOT YOUR ANSWER. When journal entries are in the data, use them to identify patterns, extract insights, or notice emotional states — do NOT quote them back word for word. The trader wrote those entries themselves; reading them back adds zero value. If they asked "what did I do right?", synthesize the behavioural pattern you observe across entries (e.g., "You enter well when you wait for structure — that's a consistent edge in your winning trades"), not a transcript.

11. SEBI COMPLIANCE — STRICT. You are a behavioral coach, NOT a financial advisor or analyst. You MUST NEVER:
   - Suggest what to buy or sell
   - Give entry/exit price levels, targets, or stop-loss levels as advice
   - Recommend specific instruments, sectors, or strategies
   - Give signals or calls of any kind
   If asked for trading advice or signals, redirect clearly: "I can't give you trade recommendations — I'm a behavior coach, not an analyst. But looking at your data, what I can tell you is [behavioral observation about their past trades]."

**THEIR ACTUAL TRADING DATA:**
{context_section}

Remember: Your job is to hold up a mirror to this trader's behavior — what they've done, what patterns are costing them, and how to build better habits. Not what to trade next."""

    async def generate_chat_response(
        self,
        user_message: str,
        trading_context: str,
        chat_history: List[Dict],
        rag_context: Optional[str] = None,
        ai_persona: str = "coach",
        deep_mode: bool = False,
    ) -> str:
        """
        Generate conversational response for trading coach chat.

        Args:
            user_message: User's chat message
            trading_context: Current trading stats and patterns
            chat_history: Previous messages in conversation
            rag_context: Optional RAG-retrieved relevant content
            ai_persona: User's preferred AI personality (coach, mentor, friend, strict)
            deep_mode: Use deep model (Sonnet) with longer output for comprehensive analysis
        """
        system_prompt = self._build_chat_system_prompt(trading_context, rag_context, ai_persona)
        if deep_mode:
            system_prompt += (
                "\n\nThe user has requested a DEEP ANALYSIS. "
                "Provide a thorough, structured response covering multiple angles: "
                "behavioral patterns, statistical edge, risk management, and specific actionable steps. "
                "Be comprehensive — up to 600 words is appropriate here."
            )

        # Build messages with history
        messages = [{"role": "system", "content": system_prompt}]

        # Add chat history (last 10 messages for context)
        for msg in chat_history[-10:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        model = self.deep_model if deep_mode else self.primary_model
        max_tokens = 800 if deep_mode else 300

        response = await self._make_request(
            messages=messages,
            model=model,
            temperature=0.5 if deep_mode else 0.7,
            max_tokens=max_tokens,
            use_reasoning=False
        )

        if not response:
            return self._fallback_chat_response(user_message, trading_context)

        content = response.get('content', '').strip()
        logger.info(f"✅ Chat response generated: {content[:50]}...")
        return content

    async def generate_chat_response_stream(
        self,
        user_message: str,
        trading_context: str,
        chat_history: List[Dict],
        rag_context: Optional[str] = None,
        ai_persona: str = "coach",
        deep_mode: bool = False,
    ):
        """
        Streaming version of generate_chat_response.
        Async generator that yields text chunks as they arrive from OpenRouter.
        Falls back to a single-chunk response if streaming fails or API key is missing.
        """
        system_prompt = self._build_chat_system_prompt(trading_context, rag_context, ai_persona)
        if deep_mode:
            system_prompt += (
                "\n\nThe user has requested a DEEP ANALYSIS. "
                "Provide a thorough, structured response covering multiple angles: "
                "behavioral patterns, statistical edge, risk management, and specific actionable steps. "
                "Be comprehensive — up to 600 words is appropriate here."
            )

        messages = [{"role": "system", "content": system_prompt}]
        for msg in chat_history[-10:]:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": user_message})

        if not self.api_key:
            yield self._fallback_chat_response(user_message, trading_context)
            return

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://trademental.ai",
            "X-Title": "TradeMentor AI",
        }
        payload = {
            "model": self.deep_model if deep_mode else self.primary_model,
            "messages": messages,
            "temperature": 0.5 if deep_mode else 0.7,
            "max_tokens": 800 if deep_mode else 300,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", self.base_url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        logger.error(f"OpenRouter streaming error: {response.status_code}")
                        yield self._fallback_chat_response(user_message, trading_context)
                        return

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            text = chunk["choices"][0].get("delta", {}).get("content", "")
                            if text:
                                yield text
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

        except httpx.TimeoutException:
            logger.error("OpenRouter streaming timeout")
            yield self._fallback_chat_response(user_message, trading_context)
        except Exception as e:
            logger.error(f"OpenRouter streaming failed: {e}")
            yield self._fallback_chat_response(user_message, trading_context)

    def _fallback_chat_response(self, user_message: str, trading_context: str) -> str:
        """Fallback when AI unavailable. Tries to extract real data from context."""
        logger.warning(f"AI_FALLBACK: Using rule-based chat response (message={user_message[:50]})")
        msg_lower = user_message.lower()

        # Try to extract key stats from the trading context
        has_positions = "Closed Positions" in trading_context and "None found" not in trading_context
        has_open = "Currently Open Positions" in trading_context
        has_alerts = "Behavioral Alerts" in trading_context

        # Extract P&L if available
        pnl_str = ""
        if "Net P&L:" in trading_context:
            try:
                pnl_line = [l for l in trading_context.split("\n") if "Net P&L:" in l][0]
                pnl_str = pnl_line.split("Net P&L:")[1].strip()
            except (IndexError, ValueError):
                pass

        if 'last trade' in msg_lower or 'recent trade' in msg_lower:
            if has_positions:
                return f"Your recent trades are all tracked here — check your dashboard for the full breakdown. Your 7-day net P&L is {pnl_str or 'on the dashboard'}. Want me to dig into a specific trade or symbol?"
            return "No closed positions in the last 7 days. Once you make some trades, I'll have your full history right here."

        if 'mistake' in msg_lower or 'wrong' in msg_lower:
            if has_alerts:
                return "I can see some behavioral patterns firing in your recent trading. The biggest thing most traders mess up is trading right after a loss — that revenge instinct kicks in fast. Take a look at your alerts on the dashboard."
            return "The most common mistake I see is chasing trades right after a loss. That revenge instinct is real. Next time you take a loss, step away for 15 minutes before your next trade."

        if 'improve' in msg_lower or 'better' in msg_lower:
            return "The single biggest improvement for most traders? Fewer trades, better quality. Pick your best setup and only trade that for a week. You'll be surprised how much your win rate improves."

        if 'pattern' in msg_lower:
            if has_alerts:
                return "Your behavioral patterns are tracked automatically — I can see the alerts from the last 7 days. The key is noticing when they trigger and what you were feeling at that moment. Which pattern are you most curious about?"
            return "No behavioral patterns triggered recently, which is a good sign. Keep trading with discipline and I'll flag anything that comes up."

        if has_positions:
            return f"Your 7-day numbers are right here — {pnl_str or 'check your dashboard for the details'}. What would you like to dig into? I can talk about specific trades, patterns, or your overall approach."

        return "I'm your trading coach — I can see all your trades, patterns, and journal entries right here. Ask me anything about your trading and I'll give you a straight answer."

# Singleton instance
ai_service = AIService()
