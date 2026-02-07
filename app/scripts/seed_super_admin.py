"""Seed the database with a super_admin user.

Usage:
    source .venv/bin/activate
    python -m app.scripts.seed_super_admin
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import select
from app.core.database import async_session
from app.models.user import User
from app.dependencies import hash_password


async def seed():
    async with async_session() as session:
        # Check if super_admin already exists
        result = await session.execute(
            select(User).where(User.role == "super_admin")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Super admin already exists: {existing.email}")
            return

        user = User(
            email="superadmin@patshala.ai",
            name="Super Admin",
            password_hash=hash_password("admin123"),
            role="super_admin",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        print(f"Super admin created!")
        print(f"  Email: {user.email}")
        print(f"  Password: admin123")
        print(f"  ID: {user.id}")
        print(f"\nUse this ID in the X-User-Id header for authenticated requests.")


if __name__ == "__main__":
    asyncio.run(seed())
