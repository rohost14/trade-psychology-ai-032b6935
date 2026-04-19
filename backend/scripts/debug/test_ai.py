import asyncio
import sys
import os

# Add parent directory to path
# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from app.services.ai_service import ai_service

async def test_persona():
    print("=" * 60)
    print("TESTING TRADING PERSONA GENERATION")
    print("=" * 60)
    
    test_patterns = [
        {
            "name": "Revenge Trading",
            "frequency": 5,
            "severity": "high",
            "pnl_impact": 2500,
            "is_positive": False
        },
        {
            "name": "Overtrading",
            "frequency": 8,
            "severity": "medium",
            "pnl_impact": 1200,
            "is_positive": False
        },
        {
            "name": "Stop Loss Discipline",
            "frequency": 15,
            "severity": "positive",
            "pnl_impact": 0,
            "is_positive": True
        }
    ]
    
    test_time_perf = {
        "best_hour": "10:00-11:00",
        "best_hour_winrate": 72,
        "worst_hour": "14:30-15:30",
        "worst_hour_winrate": 28
    }
    
    persona = await ai_service.generate_trading_persona(
        patterns_detected=test_patterns,
        total_trades=50,
        emotional_tax=3700,
        time_performance=test_time_perf
    )
    
    print(f"\n✅ PERSONA: {persona['persona']}")
    print(f"\n📝 DESCRIPTION:\n{persona['description']}")
    print(f"\n💪 STRENGTHS:")
    for s in persona['strengths']:
        print(f"  • {s}")
    print(f"\n⚠️ WEAKNESSES:")
    for w in persona['weaknesses']:
        print(f"  • {w}")
    print(f"\n🎯 NEXT STEPS:\n{persona['next_steps']}")
    print("\n" + "=" * 60)

async def test_insights():
    print("\nTESTING COACH INSIGHTS (VARIABLE TONE)")
    print("=" * 60)
    
    test_cases = [
        {
            "name": "Safe + Profit",
            "risk_state": "safe",
            "pnl": 5000,
            "patterns": [],
            "trades": 3
        },
        {
            "name": "Safe + Loss",
            "risk_state": "safe",
            "pnl": -2000,
            "patterns": [],
            "trades": 2
        },
        {
            "name": "Caution",
            "risk_state": "caution",
            "pnl": -3000,
            "patterns": ["Overtrading"],
            "trades": 7
        },
        {
            "name": "Danger",
            "risk_state": "danger",
            "pnl": -8000,
            "patterns": ["Revenge Trading", "Overtrading"],
            "trades": 12
        }
    ]
    
    for case in test_cases:
        insight = await ai_service.generate_coach_insight(
            risk_state=case["risk_state"],
            total_pnl=case["pnl"],
            patterns_active=case["patterns"],
            recent_trades=case["trades"],
            time_of_day="Morning session"
        )
        
        print(f"\n{case['name']} ({case['risk_state'].upper()}):")
        print(f"  P&L: ₹{case['pnl']}, Trades: {case['trades']}")
        print(f"  💬 \"{insight}\"")
    
    print("\n" + "=" * 60)

async def main():
    print("\n🤖 TradeMentor AI - Testing AI Integration\n")
    
    if not os.getenv('OPENROUTER_API_KEY'):
        print("⚠️  WARNING: OPENROUTER_API_KEY not set in environment")
        print("   Set it with: export OPENROUTER_API_KEY=sk-or-v1-xxxxx")
        print("   Continuing with fallback logic...\n")
    
    await test_persona()
    await test_insights()
    
    print("\n✅ AI Integration Test Complete!\n")

if __name__ == "__main__":
    asyncio.run(main())
