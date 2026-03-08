"""
Seed Knowledge Base with Trading Psychology Content

This script populates the knowledge_base table with curated
trading psychology content for RAG-based coaching.

Run with: python -m scripts.seed_knowledge_base
"""

import asyncio
import httpx
from sqlalchemy import text
from app.core.database import async_session_maker
from app.core.config import settings

# Trading Psychology Knowledge Base Content
KNOWLEDGE_BASE_ENTRIES = [
    # ==========================================
    # REVENGE TRADING
    # ==========================================
    {
        "category": "pattern",
        "subcategory": "revenge_trading",
        "title": "Understanding Revenge Trading",
        "content": """Revenge trading occurs when a trader tries to recover losses by immediately taking another trade, often with larger position sizes or without proper analysis. This is driven by emotional response to loss rather than rational decision-making. The brain's loss aversion triggers a fight response, pushing you to 'win back' what was lost. This almost always leads to larger losses because decisions are made from emotion, not strategy.""",
        "tags": ["revenge", "psychology", "loss-recovery", "emotional-trading"],
        "relevance_patterns": ["revenge_trading", "loss_chasing"],
        "severity_level": "critical"
    },
    {
        "category": "intervention",
        "subcategory": "revenge_trading",
        "title": "Breaking the Revenge Trading Cycle",
        "content": """To break revenge trading: 1) Recognize the emotional state - if you feel frustrated or angry after a loss, that's your warning sign. 2) Step away from the screen for at least 15-30 minutes. 3) Do a physical activity - walk, stretch, or breathe deeply. 4) Review your trading plan before the next trade. 5) Size down your next position by 50% until you're emotionally neutral. The goal is to interrupt the emotional cycle before it leads to action.""",
        "tags": ["intervention", "cooldown", "emotional-regulation"],
        "relevance_patterns": ["revenge_trading"],
        "severity_level": "critical"
    },

    # ==========================================
    # OVERTRADING
    # ==========================================
    {
        "category": "pattern",
        "subcategory": "overtrading",
        "title": "The Overtrading Trap",
        "content": """Overtrading is taking too many positions, often due to boredom, FOMO, or confusing activity with productivity. Signs include: trading outside your planned setups, taking marginal opportunities, feeling restless when not in a trade, and focusing on quantity over quality. Overtrading increases transaction costs, reduces focus on each trade, and often leads to lower win rates. Quality traders wait patiently for A+ setups.""",
        "tags": ["overtrading", "discipline", "patience"],
        "relevance_patterns": ["overtrading", "chop_addiction"],
        "severity_level": "warning"
    },
    {
        "category": "strategy",
        "subcategory": "overtrading",
        "title": "Controlling Trade Frequency",
        "content": """To prevent overtrading: 1) Set a maximum number of trades per day (3-5 for most styles). 2) Require your checklist to be complete before entry. 3) Focus on your top 2-3 setups only. 4) Journal why you took each trade - review for pattern violations. 5) Have a 'walk away' rule after hitting daily profit target. 6) Treat 'no trade' as a valid trading decision. Remember: the market will be there tomorrow.""",
        "tags": ["discipline", "rules", "trade-management"],
        "relevance_patterns": ["overtrading"],
        "severity_level": "warning"
    },

    # ==========================================
    # FOMO (Fear of Missing Out)
    # ==========================================
    {
        "category": "pattern",
        "subcategory": "fomo",
        "title": "FOMO in Trading",
        "content": """FOMO (Fear of Missing Out) leads traders to chase moves after they've already happened. You see a stock running up and jump in without analysis, often buying at the top. FOMO is triggered by: social media showing others' gains, watching a move happen without you, or regret from past missed opportunities. FOMO trades typically have poor risk/reward because you're entering late.""",
        "tags": ["fomo", "psychology", "late-entry"],
        "relevance_patterns": ["fomo", "late_entry"],
        "severity_level": "warning"
    },
    {
        "category": "intervention",
        "subcategory": "fomo",
        "title": "Overcoming FOMO",
        "content": """To overcome FOMO: 1) Accept that you will miss opportunities - it's part of trading. 2) Focus on YOUR setups, not what others are trading. 3) Keep a 'missed trades' journal - you'll see many of them fail. 4) Calculate where your stop would be if you entered now - often it's too far away. 5) Remember: there are new opportunities every day. 6) Unfollow traders who trigger your FOMO. The best traders have strong JOMO (Joy of Missing Out).""",
        "tags": ["mindset", "discipline", "self-awareness"],
        "relevance_patterns": ["fomo"],
        "severity_level": "warning"
    },

    # ==========================================
    # TILT / EMOTIONAL STATE
    # ==========================================
    {
        "category": "pattern",
        "subcategory": "tilt",
        "title": "Recognizing Tilt",
        "content": """Tilt is an emotional state where frustration, anger, or desperation impairs your trading decisions. Signs of tilt: increasing position sizes after losses, abandoning your trading plan, feeling physically tense or agitated, revenge trading, blaming the market or others, and making impulsive decisions. Tilt is like playing poker after losing several hands - your judgment is compromised even if you don't realize it.""",
        "tags": ["tilt", "emotions", "psychology"],
        "relevance_patterns": ["tilt", "revenge_trading", "emotional_trading"],
        "severity_level": "critical"
    },
    {
        "category": "intervention",
        "subcategory": "tilt",
        "title": "Recovering from Tilt",
        "content": """When on tilt: 1) STOP trading immediately - this is non-negotiable. 2) Close all monitoring apps and charts. 3) Do physical activity - the stress hormones need an outlet. 4) Accept the current loss rather than fighting it. 5) Review your worst-case scenario - it's usually survivable. 6) Don't trade again today. 7) Journal what triggered the tilt before you forget. Tomorrow is a fresh day with a fresh mind. No single day should define your trading career.""",
        "tags": ["recovery", "intervention", "self-care"],
        "relevance_patterns": ["tilt"],
        "severity_level": "critical"
    },

    # ==========================================
    # POSITION SIZING
    # ==========================================
    {
        "category": "strategy",
        "subcategory": "risk_management",
        "title": "Position Sizing Fundamentals",
        "content": """Proper position sizing is your primary defense against account blowups. Rules: 1) Never risk more than 1-2% of capital per trade. 2) Calculate position size based on your stop loss, not based on how much you want to make. 3) Reduce size after consecutive losses - you might be in a bad phase. 4) Never add to losing positions (averaging down in leveraged products). 5) Size down when uncertain, size up only when you have confirmed edge. Survival comes before profits.""",
        "tags": ["risk-management", "position-sizing", "capital-preservation"],
        "relevance_patterns": ["martingale", "oversizing"],
        "severity_level": "critical"
    },

    # ==========================================
    # TIME-BASED PATTERNS
    # ==========================================
    {
        "category": "pattern",
        "subcategory": "time_based",
        "title": "First 15 Minutes Trading",
        "content": """The first 15 minutes after market open (9:15-9:30 AM IST) is extremely volatile with gap fills, news reactions, and large order flows. Many retail traders lose money here because: spreads are wider, fake breakouts are common, and emotional reactions to gaps dominate. Consider waiting for the dust to settle. Professional traders often let the open establish a range before taking positions.""",
        "tags": ["timing", "market-open", "volatility"],
        "relevance_patterns": ["early_trading"],
        "severity_level": "info"
    },
    {
        "category": "pattern",
        "subcategory": "time_based",
        "title": "Last Hour Trading",
        "content": """The last hour of trading (2:30-3:30 PM IST) has unique characteristics: increased volatility as positions are squared off, large institutional flows, and gamma effects in options near expiry. If you're not experienced in this window, consider closing positions by 2:30 PM. Many profitable intraday traders bank their gains before the final hour chaos.""",
        "tags": ["timing", "market-close", "expiry"],
        "relevance_patterns": ["late_trading"],
        "severity_level": "info"
    },

    # ==========================================
    # STOP LOSS PSYCHOLOGY
    # ==========================================
    {
        "category": "psychology",
        "subcategory": "stop_loss",
        "title": "Why Traders Move Their Stop Loss",
        "content": """Traders move stop losses because of loss aversion - the pain of realizing a loss is psychologically harder than the hope of recovery. When price approaches your stop, your brain starts negotiating: 'just a little more room', 'it's coming back'. This is hope replacing strategy. A stop loss is your pre-committed exit when your trade thesis is wrong. Moving it means you're now gambling, not trading.""",
        "tags": ["stop-loss", "discipline", "loss-aversion"],
        "relevance_patterns": ["stop_loss_violation", "loss_widening"],
        "severity_level": "warning"
    },

    # ==========================================
    # WINNING MINDSET
    # ==========================================
    {
        "category": "psychology",
        "subcategory": "mindset",
        "title": "Process Over Outcome",
        "content": """Professional traders focus on process, not individual trade outcomes. A good trade can lose money, and a bad trade can make money - in the short term. What matters is: Did you follow your plan? Was the setup valid? Was your size correct? Was your execution clean? If yes, the outcome is noise. Keep following the process and let probabilities work over hundreds of trades. Judge yourself on process adherence, not P&L.""",
        "tags": ["mindset", "process", "professional-trading"],
        "relevance_patterns": [],
        "severity_level": "info"
    },
    {
        "category": "psychology",
        "subcategory": "mindset",
        "title": "Accepting Losses",
        "content": """Losses are the cost of doing business in trading. Even the best strategies have 40-50% losing trades. Accepting this fact emotionally is crucial. Every loss teaches you something - about the market, about your strategy, or about yourself. The goal isn't to never lose, but to keep losses small and learnings large. A loss only becomes a failure if you don't learn from it or if you let it destroy your discipline.""",
        "tags": ["mindset", "losses", "growth"],
        "relevance_patterns": ["loss_normalization"],
        "severity_level": "info"
    },

    # ==========================================
    # JOURNALING
    # ==========================================
    {
        "category": "strategy",
        "subcategory": "improvement",
        "title": "The Power of Trade Journaling",
        "content": """A trading journal is your most powerful improvement tool. For each trade, record: 1) Setup and reason for entry, 2) Your emotional state before, during, and after, 3) What went right/wrong, 4) What you would do differently. Review weekly. You'll start seeing patterns in YOUR trading that no generic advice can reveal. The journal converts experience into wisdom and prevents repeating the same mistakes.""",
        "tags": ["journaling", "improvement", "self-analysis"],
        "relevance_patterns": [],
        "severity_level": "info"
    },

    # ==========================================
    # COOLDOWN EFFECTIVENESS
    # ==========================================
    {
        "category": "intervention",
        "subcategory": "cooldown",
        "title": "Why Cooldowns Work",
        "content": """Cooldown periods work because they interrupt the emotional cycle. After a stressful event (loss, missed opportunity, tilt), your body releases cortisol and adrenaline. These hormones take 15-30 minutes to clear. During this time, your prefrontal cortex (rational thinking) is suppressed while your amygdala (fight/flight) is active. A cooldown gives your brain chemistry time to return to baseline so you can make rational decisions.""",
        "tags": ["cooldown", "neuroscience", "intervention"],
        "relevance_patterns": ["tilt", "revenge_trading"],
        "severity_level": "info"
    },
]


async def generate_embedding(text: str) -> list:
    """Generate embedding using OpenAI API."""
    api_key = settings.OPENAI_API_KEY

    if not api_key:
        print("Warning: OPENAI_API_KEY not set. Skipping embeddings.")
        return None

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "text-embedding-ada-002",
                "input": text
            },
            timeout=30.0
        )

        if response.status_code != 200:
            print(f"Embedding error: {response.status_code}")
            return None

        data = response.json()
        return data["data"][0]["embedding"]


async def seed_knowledge_base():
    """Seed the knowledge base with trading psychology content."""
    print("Starting knowledge base seeding...")

    async with async_session_maker() as db:
        for entry in KNOWLEDGE_BASE_ENTRIES:
            # Check if entry already exists
            result = await db.execute(
                text("SELECT id FROM knowledge_base WHERE title = :title"),
                {"title": entry["title"]}
            )
            existing = result.fetchone()

            if existing:
                print(f"Skipping existing entry: {entry['title']}")
                continue

            # Generate embedding
            embedding = await generate_embedding(entry["content"])
            embedding_str = f"[{','.join(str(x) for x in embedding)}]" if embedding else None

            # Insert entry
            query = text("""
                INSERT INTO knowledge_base (
                    category, subcategory, title, content,
                    embedding, tags, relevance_patterns, severity_level
                )
                VALUES (
                    :category, :subcategory, :title, :content,
                    :embedding::vector, :tags, :relevance_patterns, :severity_level
                )
            """)

            await db.execute(query, {
                "category": entry["category"],
                "subcategory": entry.get("subcategory"),
                "title": entry["title"],
                "content": entry["content"],
                "embedding": embedding_str,
                "tags": entry.get("tags", []),
                "relevance_patterns": entry.get("relevance_patterns", []),
                "severity_level": entry.get("severity_level")
            })

            print(f"Added: {entry['title']}")

        await db.commit()

    print("Knowledge base seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_knowledge_base())
