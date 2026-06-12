"""
Create or update an admin user in the database.

Usage (from backend/ directory):
    python scripts/create_admin.py

Reads DATABASE_URL from backend/.env automatically.
"""
import asyncio
import sys
import os
import getpass
from pathlib import Path

# Load .env from backend/
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in backend/.env")
    sys.exit(1)


async def main():
    import bcrypt as _bcrypt
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    import uuid
    from datetime import datetime, timezone

    # asyncpg needs postgresql+asyncpg scheme
    db_url = DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Lazy import after env is loaded
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from app.models.admin_user import AdminUser

    print("=== TradeMentor Admin User Creator ===\n")
    email    = input("Email: ").strip()
    name     = input("Name:  ").strip()
    role     = input("Role [superadmin/ops/support] (default: superadmin): ").strip() or "superadmin"
    password = getpass.getpass("Password: ")
    confirm  = getpass.getpass("Confirm:  ")

    if password != confirm:
        print("ERROR: Passwords do not match.")
        sys.exit(1)
    if len(password) < 12:
        print("ERROR: Password must be at least 12 characters.")
        sys.exit(1)
    if role not in ("superadmin", "ops", "support"):
        print("ERROR: Invalid role.")
        sys.exit(1)

    pw_hash = _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8")

    async with Session() as db:
        existing = (await db.execute(select(AdminUser).where(AdminUser.email == email))).scalar_one_or_none()
        if existing:
            existing.password_hash = pw_hash
            existing.name          = name
            existing.role          = role
            existing.is_active     = True
            await db.commit()
            print(f"\n✓ Updated existing admin: {email} (role: {role})")
        else:
            admin = AdminUser(
                id=uuid.uuid4(),
                email=email,
                name=name,
                role=role,
                password_hash=pw_hash,
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            db.add(admin)
            await db.commit()
            print(f"\n✓ Created admin user: {email} (role: {role})")

    print("\nLogin at: http://localhost:8080/admin/login")
    print("Two-factor auth: email OTP sent to your email on each login.")
    print("(Upgrade to TOTP via Admin → Config → Authenticator App)")


if __name__ == "__main__":
    asyncio.run(main())
