"""Create or update the Velocity moderator account.
Usage: .venv\\Scripts\\python -m scripts.create_moderator <email> <display_name> <password>
"""

import asyncio
import sys

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import Credential, User
from app.security import hash_password

CEO_BALANCE = 1_000_000_000_000_000  # effectively infinite coins


async def main(email: str, name: str, password: str) -> None:
    async with SessionLocal() as s:
        user = await s.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            user = User(email=email.lower(), display_name=name, balance=CEO_BALANCE,
                        is_moderator=True, is_admin=True)
            s.add(user)
            await s.flush()
            s.add(Credential(user_id=user.id, password_hash=hash_password(password)))
        else:
            user.display_name, user.is_moderator, user.is_admin = name, True, True
            user.balance = max(user.balance, CEO_BALANCE)
            cred = await s.scalar(select(Credential).where(Credential.user_id == user.id))
            if cred:
                cred.password_hash = hash_password(password)
            else:
                s.add(Credential(user_id=user.id, password_hash=hash_password(password)))
        await s.commit()
        print(f"Moderator ready: {user.display_name} (#{user.id}), balance {user.balance:,}")
    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
