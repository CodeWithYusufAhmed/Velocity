"""M1 gate verification: run after `alembic upgrade head`.
Prints table count and the live seeded odds table with per-slot RTP."""

import asyncio

import sqlalchemy as sa

from app.db import engine


async def main() -> None:
    async with engine.connect() as c:
        tables = (
            await c.execute(
                sa.text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name != 'alembic_version'"
                )
            )
        ).scalar()
        rows = (
            await c.execute(
                sa.text(
                    "SELECT position, name, multiplier, probability "
                    "FROM odds_table ORDER BY position"
                )
            )
        ).all()
        total = (await c.execute(sa.text("SELECT SUM(probability) FROM odds_table"))).scalar()
    await engine.dispose()

    print(f"tables created: {tables}")
    print(f"probability sum: {total}")
    print(f"{'slot':<18}{'mult':>6}{'probability':>15}{'RTP':>10}")
    for pos, name, mult, prob in rows:
        print(f"{name:<18}{'x' + str(mult):>6}{float(prob):>15.6%}{float(prob) * (mult + 1):>10.4f}")


if __name__ == "__main__":
    asyncio.run(main())
