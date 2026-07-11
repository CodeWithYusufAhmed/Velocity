"""The 24/7 global round loop.

State machine: BETTING (15s) → SPINNING (3s) → RESULTS (3s) → next round.
Runs whether or not anyone is connected. All bet validation happens here,
inside DB transactions — the client is never trusted.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.game import rng
from app.models import Bet, OddsSlot, Round, Transaction, User

log = logging.getLogger("velocity.engine")

BETTING, SPINNING, RESULTS = "BETTING", "SPINNING", "RESULTS"


@dataclass
class SlotInfo:
    position: int
    name: str
    multiplier: int
    probability: Decimal


@dataclass
class EngineState:
    phase: str = RESULTS
    round_id: int = 0
    commit: str = ""
    seconds_left: int = 0
    slots: list[SlotInfo] = field(default_factory=list)


class BetError(Exception):
    pass


class GameEngine:
    """One instance per server process. WS handlers call place_bet() and read
    state; subscribers receive broadcast dicts to fan out to clients."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        self.maker = session_maker
        self.state = EngineState()
        self._seed: str = ""  # secret until reveal
        self._subscribers: list = []  # async callables(dict)
        self._bet_lock = asyncio.Lock()
        self._running = False

    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def _broadcast(self, message: dict) -> None:
        for cb in list(self._subscribers):
            try:
                await cb(message)
            except Exception:  # a broken subscriber must never stall the game
                log.exception("subscriber failed")

    async def load_slots(self) -> None:
        async with self.maker() as s:
            rows = (
                await s.scalars(
                    select(OddsSlot).where(OddsSlot.is_active).order_by(OddsSlot.position)
                )
            ).all()
        self.state.slots = [
            SlotInfo(r.position, r.name, r.multiplier, Decimal(r.probability)) for r in rows
        ]
        if len(self.state.slots) < 2:
            raise RuntimeError("odds_table is empty — run alembic upgrade head")

    # ---- round lifecycle -------------------------------------------------

    async def open_round(self) -> None:
        self._seed = rng.new_server_seed()
        async with self.maker() as s:
            # Commit is computed against the sequential id Postgres assigns.
            rnd = Round(commit="pending", betting_opened_at=datetime.now(timezone.utc))
            s.add(rnd)
            await s.flush()
            rnd.commit = rng.commitment(self._seed, rnd.id)
            await s.commit()
            self.state.round_id, self.state.commit = rnd.id, rnd.commit
        self.state.phase = BETTING

    async def place_bet(self, user_id: int, slot_position: int, amount: int) -> dict:
        """Validate and persist a bet. Returns {bet_id, balance}. Raises BetError."""
        st = self.state
        if st.phase != BETTING:
            raise BetError("Betting is closed for this round")
        if slot_position not in {s.position for s in st.slots}:
            raise BetError("Unknown slot")
        if amount not in get_settings().chip_values:
            raise BetError("Invalid chip value")
        async with self._bet_lock:
            async with self.maker() as s:
                user = await s.get(User, user_id, with_for_update=True)
                if user is None or user.is_banned:
                    raise BetError("Account unavailable")
                if user.balance < amount:
                    raise BetError("Insufficient balance")

                # Anti-addiction: self-set daily round limit (counts distinct rounds).
                from app.services import economy
                first_bet_this_round = (
                    await s.scalar(
                        select(Bet.id).where(
                            Bet.round_id == st.round_id, Bet.user_id == user_id
                        ).limit(1)
                    )
                ) is None
                stats = await economy.get_daily_stats(s, user_id)
                if first_bet_this_round:
                    limit = await economy.effective_round_limit(s, user_id)
                    if limit is not None and stats.rounds_played >= limit:
                        raise BetError(
                            "You reached your self-set daily round limit — watching is still fine!"
                        )
                    stats.rounds_played += 1
                stats.total_bet += amount

                user.balance -= amount
                bet = Bet(
                    round_id=st.round_id, user_id=user_id,
                    slot_position=slot_position, amount=amount,
                )
                s.add(bet)
                await s.flush()
                s.add(
                    Transaction(
                        user_id=user_id, type="bet", amount=-amount,
                        balance_after=user.balance, round_id=st.round_id,
                    )
                )
                await s.commit()
                return {"bet_id": bet.id, "balance": user.balance}

    async def settle_round(self) -> dict:
        """Reveal seed, pick winner, pay out. Returns the spin_result message."""
        st = self.state
        probs = [s.probability for s in st.slots]
        win_idx = rng.select_slot(self._seed, st.round_id, probs)
        winning = st.slots[win_idx]

        async with self.maker() as s:
            bets = (await s.scalars(select(Bet).where(Bet.round_id == st.round_id))).all()
            per_user_won: dict[int, int] = {}
            for b in bets:
                if b.slot_position == winning.position:
                    payout = b.amount * (winning.multiplier + 1)  # stake + winnings
                    b.payout = payout
                    per_user_won[b.user_id] = per_user_won.get(b.user_id, 0) + payout

            from app.services import economy, vip
            for uid, won in per_user_won.items():
                user = await s.get(User, uid, with_for_update=True)
                user.balance += won
                s.add(
                    Transaction(
                        user_id=uid, type="win", amount=won,
                        balance_after=user.balance, round_id=st.round_id,
                    )
                )
                stats = await economy.get_daily_stats(s, uid)
                stats.total_won += won
                stats.biggest_win = max(stats.biggest_win, won)
                await vip.record_winnings(s, uid, won)  # VIP thresholds/replacement

            await s.execute(
                update(Round)
                .where(Round.id == st.round_id)
                .values(
                    server_seed=self._seed,
                    winning_position=winning.position,
                    resulted_at=datetime.now(timezone.utc),
                )
            )

            top3: list[dict] = []
            if per_user_won:
                winners = sorted(per_user_won.items(), key=lambda kv: kv[1], reverse=True)[:3]
                names = {
                    u.id: u.display_name
                    for u in (
                        await s.scalars(select(User).where(User.id.in_([w[0] for w in winners])))
                    ).all()
                }
                top3 = [
                    {"user_id": uid, "display_name": names.get(uid, "?"), "won": won}
                    for uid, won in winners
                ]
            await s.execute(update(Round).where(Round.id == st.round_id).values(top3=top3))
            await s.commit()

        return {
            "type": "spin_result",
            "round_id": st.round_id,
            "winning_position": winning.position,
            "winning_name": winning.name,
            "multiplier": winning.multiplier,
            "server_seed": self._seed,
            "commit": st.commit,
            "top3": top3,
        }

    # ---- the loop --------------------------------------------------------

    async def _countdown(self, phase: str, seconds: int, extra: dict | None = None) -> None:
        self.state.phase = phase
        for left in range(seconds, 0, -1):
            self.state.seconds_left = left
            msg = {
                "type": "round_state", "phase": phase, "round_id": self.state.round_id,
                "seconds_left": left, "commit": self.state.commit,
            }
            if extra:
                msg.update(extra)
            await self._broadcast(msg)
            await asyncio.sleep(1)

    async def run_one_round(self) -> None:
        s = get_settings()
        await self.load_slots()  # pick up admin odds edits without a restart
        await self.open_round()
        await self._countdown(BETTING, s.betting_seconds)
        self.state.phase = SPINNING  # bets locked from this instant
        await self._countdown(SPINNING, s.spinning_seconds)
        result = await self.settle_round()
        self.state.phase = RESULTS
        await self._broadcast(result)
        await self._countdown(RESULTS, s.results_seconds)

    async def run_forever(self) -> None:
        self._running = True
        await self.load_slots()
        log.info("round engine started")
        while self._running:
            try:
                await self.run_one_round()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("round crashed; pausing 5s")
                await asyncio.sleep(5)

    def stop(self) -> None:
        self._running = False
