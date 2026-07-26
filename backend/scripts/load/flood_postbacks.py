"""
Flood the engine path with synthetic COMPLETE fills (Celery throughput test).

Enqueues process_webhook_trade tasks directly (bypasses the HTTP + checksum layer)
so it stresses the real bottleneck: TradeSync -> PositionLedger -> BehaviorEngine ->
alerts, and the Celery queue. Watch alert_e2e_lag_ms + queue depth while it runs.

Run from backend/ (needs Redis + a Celery worker consuming the `trades` queue):
    python -m scripts.load.flood_postbacks --account-index 0 --count 500 --rate 20
    python -m scripts.load.flood_postbacks --all --count 20 --rate 50   # spread across all seeded accounts
"""
import os
import json
import time
import uuid
import random
import argparse
from datetime import datetime, timezone

HERE = os.path.dirname(__file__)
TOKENS_PATH = os.path.join(HERE, "tokens.json")
SYMBOLS = [("NIFTY25JULFUT", "NFO"), ("CRUDEOIL25JULFUT", "MCX"), ("RELIANCE25JULFUT", "NFO")]


def _fill(account_id: str) -> dict:
    sym, exch = random.choice(SYMBOLS)
    px = round(random.uniform(100, 6000), 2)
    qty = random.choice([50, 75, 1])
    return {
        "order_id": f"load-{uuid.uuid4().hex[:16]}",
        "status": "COMPLETE",
        "tradingsymbol": sym,
        "exchange": exch,
        "transaction_type": random.choice(["BUY", "SELL"]),
        "order_type": "MARKET",
        "product": "MIS",
        "quantity": qty,
        "filled_quantity": qty,
        "pending_quantity": 0,
        "cancelled_quantity": 0,
        "price": px,
        "average_price": px,
        "trigger_price": 0.0,
        "order_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "exchange_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "tag": f"user_{account_id}",
        "variety": "regular",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--account-index", type=int, default=0, help="index into tokens.json")
    p.add_argument("--all", action="store_true", help="spread fills across ALL seeded accounts")
    p.add_argument("--count", type=int, default=500, help="fills per account (or total if --all)")
    p.add_argument("--rate", type=float, default=20, help="fills/sec")
    args = p.parse_args()

    from app.tasks.trade_tasks import process_webhook_trade

    tokens = json.load(open(TOKENS_PATH, encoding="utf-8"))
    if args.all:
        targets = [t["account_id"] for t in tokens]
    else:
        targets = [tokens[args.account_index]["account_id"]]

    interval = 1.0 / args.rate if args.rate > 0 else 0
    sent = 0
    start = time.time()
    per_target = args.count if not args.all else max(1, args.count // len(targets))

    for account_id in targets:
        for _ in range(per_target):
            process_webhook_trade.delay(_fill(account_id), account_id, f"load-{sent}")
            sent += 1
            if interval:
                time.sleep(interval)
            if sent % 100 == 0:
                print(f"  enqueued {sent} fills ({sent / (time.time() - start):.0f}/s)")

    print(f"done: enqueued {sent} fills across {len(targets)} account(s). "
          f"Watch: alert_e2e_lag_ms (admin engine-metrics) + `redis-cli LLEN trades`.")


if __name__ == "__main__":
    main()
