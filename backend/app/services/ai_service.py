import os
import requests
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
        
        # Model selection (cost-efficient)
        self.primary_model = "anthropic/claude-3.5-haiku"  # $0.80/1M tokens, fast
        self.reasoning_model = "openai/gpt-4o-mini"  # $0.15/1M tokens, reasoning capable
        self.free_model = "google/gemini-flash-1.5-8b"  # Free tier fallback
    
    def _make_request(
        self, 
        messages: List[Dict], 
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        use_reasoning: bool = False
    ) -> Optional[Dict]:
        """Make request to OpenRouter API."""
        
        if not self.api_key:
            logger.warning("No API key, skipping AI request")
            return None
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://trademental.ai",  # Optional: for rankings
            "X-Title": "TradeMentor AI"  # Optional: show in rankings
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # Add reasoning for complex analysis
        if use_reasoning:
            payload["reasoning"] = {"enabled": True}
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                return None
            
            result = response.json()
            return result['choices'][0]['message']
            
        except requests.exceptions.Timeout:
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
        response = self._make_request(
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
    
    async def generate_coach_insight(
        self,
        risk_state: str,
        total_pnl: float,
        patterns_active: List[str],
        recent_trades: int,
        time_of_day: str
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

Generate ONLY the coach message (1-2 sentences, no explanation, no preamble)."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self._make_request(
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
        elif recent_trades == 0:
            return "No trades yet. Remember: patience is a position. Wait for A+ setups."
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
        
        response = self._make_request(
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

    async def generate_chat_response(
        self,
        user_message: str,
        trading_context: str,
        chat_history: List[Dict]
    ) -> str:
        """
        Generate conversational response for trading coach chat.
        Uses trading context to provide personalized advice.
        """

        system_prompt = f"""You are TradeMentor, an expert F&O trading psychology coach. You help Indian traders improve their discipline and avoid emotional trading mistakes.

Your personality:
- Direct and practical, no fluff
- Empathetic but firm about discipline
- Always refer to actual data when available
- Give specific, actionable advice
- Use ₹ for currency (Indian Rupee)
- Keep responses concise (2-4 sentences unless detailed analysis requested)

{trading_context}

Base your advice on this actual trading data. If asked about patterns or performance, refer to real numbers. If data is insufficient, acknowledge it and give general guidance."""

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

        response = self._make_request(
            messages=messages,
            model=self.primary_model,
            temperature=0.7,
            max_tokens=500,
            use_reasoning=False
        )

        if not response:
            return self._fallback_chat_response(user_message, trading_context)

        content = response.get('content', '').strip()
        logger.info(f"✅ Chat response generated: {content[:50]}...")
        return content

    def _fallback_chat_response(self, user_message: str, trading_context: str) -> str:
        """Fallback when AI unavailable."""
        msg_lower = user_message.lower()

        if 'mistake' in msg_lower or 'wrong' in msg_lower:
            return "Looking at your data, focus on position sizing and avoid trading during the first 15 minutes after market open. Most emotional mistakes happen when we chase early moves."
        elif 'improve' in msg_lower or 'better' in msg_lower:
            return "Three things to improve: 1) Set a daily loss limit and stick to it, 2) Wait for confirmation before entries, 3) Journal every trade with your emotional state."
        elif 'pattern' in msg_lower:
            return "I can see your trading patterns in the data. The most impactful change would be reducing trade frequency - quality over quantity leads to better results."
        elif 'time' in msg_lower or 'when' in msg_lower:
            return "Based on general patterns, avoid trading in the first 15 mins (9:15-9:30) and last 30 mins (3:00-3:30). Your best setups likely come mid-morning."
        else:
            return "Focus on your process, not just profits. Set clear rules before market opens and follow them strictly. What specific aspect of your trading would you like to discuss?"

# Singleton instance
ai_service = AIService()
