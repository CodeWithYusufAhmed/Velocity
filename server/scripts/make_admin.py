"""Grant (or revoke) admin on an account.
Usage: .venv\\Scripts\\python -m scripts.make_admin you@example.com [--revoke]
"""

import asyncio
import sys

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import User


async def main(email: str, revoke: bool) -> None:
    async with SessionLocal() as s:
        user = await s.scalar(select(User).where(User.email == email.lower().strip()))
        if user is None:
            print(f"No account with email {email}")
            return
        user.is_admin = not revoke
        await s.commit()
        print(f"{'Revoked admin from' if revoke else 'Granted admin to'} {user.display_name} (#{user.id})")
    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1], "--revoke" in sys.argv))
