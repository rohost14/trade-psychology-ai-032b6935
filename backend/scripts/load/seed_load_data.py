"""
Seed synthetic accounts + completed trades for load testing, and emit JWTs.

Run from backend/:
    python -m scripts.load.seed_load_data --accounts 1000 --trades-per 60

Writes scripts/load/tokens.json = [{"account_id": "...", "token": "..."}] for k6.
Idempotent-ish: creates NEW synthetic rows each run (email prefixed load_<ts>_).
Clean up test data by deleting users whose email starts with 'load_'.
"""
import os
import json
import uuid
import random
import asyncio
import argparse
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(__file__)
TOKENS_PATH = os.path.join(HERE, "tokens.json")

SYMBOLS = ["NIFTY25JULFUT", "BANKNIFTY25JUL52000CE", "CRUDEOIL25JULFUT", "RELIANCE25JULFUT"]
EXCHANGES = {"NIFTY25JULFUT": "NFO", "BANKNIFTY25JUL52000CE": "NFO",
             "CRUDEOIL25JULFUT": "MCX", "RELIANCE25JULFUT": "NFO"}


async def _seed(accounts: int, trades_per: int) -> None:
    from app.core.database import SessionLocal
    from app.models.user import User
    from app.models.broker_account import BrokerAccount
    from app.models.completed_trade import CompletedTrade
    from app.api.deps import create_access_token

    stamp = int(datetime.now().timestamp())
    tokens = []

    async with SessionLocal() as db:
        for i in range(accounts):
            user = User(email=f"load_{stamp}_{i}@example.com", display_name=f"Load User {i}")
            db.add(user)
            await db.flush()

            acct = BrokerAccount(
                user_id=user.id,
                broker_name="zerodha",
                broker_user_id=f"LD{stamp}{i}",
                status="connected",
                api_key="load-test",
            )
            db.add(acct)
            await db.flush()

            now = datetime.now(timezone.utc)
            for t in range(trades_per):
                sym = random.choice(SYMBOLS)
                entry = round(random.uniform(100, 6000), 2)
                exit_ = round(entry * random.uniform(0.97, 1.03), 2)
                direction = random.choice(["LONG", "SHORT"])
                qty = random.choice([50, 75, 1, 100])
                exit_time = now - timedelta(minutes=random.randint(1, 90) + t * 5)
                pnl = (exit_ - entry) * qty if direction == "LONG" else (entry - exit_) * qty
                db.add(CompletedTrade(
                    broker_account_id=acct.id,
                    tradingsymbol=sym,
                    exchange=EXCHANGES[sym],
                    direction=direction,
                    total_quantity=qty,
                    num_entries=1,
                    num_exits=1,
                    avg_entry_price=entry,
                    avg_exit_price=exit_,
                    realized_pnl=round(pnl, 2),
                    entry_time=exit_time - timedelta(minutes=random.randint(1, 30)),
                    exit_time=exit_time,
                    duration_minutes=random.randint(1, 120),
                    status="closed",
                ))

            tokens.append({
                "account_id": str(acct.id),
                "token": create_access_token(user_id=user.id, broker_account_id=acct.id),
            })

            if (i + 1) % 100 == 0:
                await db.commit()
                print(f"  seeded {i + 1}/{accounts} accounts")

        await db.commit()

    with open(TOKENS_PATH, "w", encoding="utf-8") as f:
        json.dump(tokens, f)
    print(f"done: {accounts} accounts x {trades_per} trades. tokens -> {TOKENS_PATH}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--accounts", type=int, default=1000)
    p.add_argument("--trades-per", type=int, default=60)
    args = p.parse_args()
    asyncio.run(_seed(args.accounts, args.trades_per))


if __name__ == "__main__":
    main()
