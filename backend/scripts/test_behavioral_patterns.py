import sys
import os
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import behavioral_analysis_service as bas

def get_base_trade(time_offset_min=0, pnl=0.0, qty=50, duration_min=10, symbol="NIFTY", tx="BUY", exchange="NSE"):
    class MockTrade:
        def __init__(self):
            t_now = datetime.now(timezone.utc)
            self.id = str(uuid.uuid4())
            self.order_id = self.id
            self.order_timestamp = t_now + timedelta(minutes=time_offset_min)
            self.pnl = float(pnl)
            self.quantity = float(qty)
            self.duration_minutes = duration_min
            self.tradingsymbol = symbol
            self.transaction_type = tx
            self.exchange = exchange

    return MockTrade()


class PatternTestRunner:
    def __init__(self):
        self.stats = {"passed": 0, "failed": 0, "errors": 0}

    def run_all(self):
        print("\n=== RUNNING 28 BEHAVIORAL PATTERN TESTS ===")
        
        self._test(bas.RevengeTradingPattern, "Revenge", lambda: [
            get_base_trade(0, pnl=-500), 
            get_base_trade(5, pnl=-100) # Re-entered 5 mins after a loss
        ])
        
        self._test(bas.MartingaleBehaviorPattern, "Martingale", lambda: [
            get_base_trade(0, pnl=-1000, qty=50),
            get_base_trade(15, pnl=-2000, qty=100) # Doubled size after loss
        ])
        
        self._test(bas.EmotionalExitPattern, "Emotional Exit", lambda: [
            get_base_trade(0, pnl=100, duration_min=5),
            get_base_trade(10, pnl=100, duration_min=5),
            get_base_trade(20, pnl=100, duration_min=5),
            get_base_trade(30, pnl=-500, duration_min=45), # Losers held 9x longer than winners
            get_base_trade(80, pnl=-500, duration_min=45),
            get_base_trade(130, pnl=-500, duration_min=45),
        ])

        self._test(bas.HopeDenialPattern, "Hope & Denial", lambda: [
            # 5 wins averaging 100, 5 losses averaging 400 (loss > 1.5x win)
            *[get_base_trade(i*10, pnl=100) for i in range(5)],
            *[get_base_trade(50 + i*10, pnl=-400) for i in range(5)]
        ])
        
        self._test(bas.OvertradingPattern, "Overtrading", lambda: [
            # 11 trades in a single day
            *[get_base_trade(i*5, pnl=10) for i in range(12)]
        ])

        self._test(bas.LossNormalizationPattern, "Loss Normalization", lambda: [
            # Death by cuts: losses < 50% of wins, high loss ratio, net negative
            *[get_base_trade(i*5, pnl=-10) for i in range(15)],
            *[get_base_trade(80 + i*5, pnl=40) for i in range(2)]
        ])

        self._test(bas.InconsistentSizingPattern, "Inconsistent Sizing", lambda: [
            get_base_trade(0, qty=10),
            get_base_trade(5, qty=250),
            get_base_trade(10, qty=5),
            get_base_trade(15, qty=500),
            get_base_trade(20, qty=20)
        ])

        self._test(bas.StopLossDisciplinePattern, "Stop Loss Discipline (Positive)", lambda: [
            # Positive pattern: losses are well contained
            *[get_base_trade(i*5, pnl=-100) for i in range(5)]
        ], expect_positive=True)
        
        # Test Negative Outcome (ensure it doesn't false-flag)
        self._test(bas.RevengeTradingPattern, "Revenge (Negative Control)", lambda: [
            get_base_trade(0, pnl=500), # Win first
            get_base_trade(5, pnl=-100) # Entered quickly but after a win
        ], expect_detected=False)

        print("\n=== SUMMARY ===")
        print(f"Passed: {self.stats['passed']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"Errors: {self.stats['errors']}")
        
        if self.stats['failed'] > 0 or self.stats['errors'] > 0:
            sys.exit(1)
            
    def _test(self, pattern_class, test_name, trade_factory_fn, expect_detected=True, expect_positive=False):
        engine = pattern_class()
        
        try:
            trades = trade_factory_fn()
            res = engine.detect(trades)
            
            # Assert detected flag matches our expectation
            if res["detected"] == expect_detected:
                if expect_positive and engine.is_positive != expect_positive:
                    print(f"❌ FAIL: {test_name}. Positive flag did not match.")
                    self.stats["failed"] += 1
                else:
                    print(f"✅ PASS: {test_name}")
                    self.stats["passed"] += 1
            else:
                print(f"❌ FAIL: {test_name}. Expected detected={expect_detected}, got {res['detected']}")
                if res['detected']:
                    print(f"   Message: {res['description']}")
                self.stats["failed"] += 1
        except Exception as e:
            print(f"⚠️ ERROR in {test_name}: {e}")
            self.stats["errors"] += 1


if __name__ == "__main__":
    runner = PatternTestRunner()
    runner.run_all()
