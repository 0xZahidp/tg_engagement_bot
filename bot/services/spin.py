# bot/services/spin.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from random import Random

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    DailyActionType,
    PointSource,
    SpinHistory,
    SpinRewardType,
)
from bot.database.tx import transactional
from bot.services.points import PointsService
from bot.services.task_progress import TaskProgressService
from bot.utils.dates import week_start_monday


@dataclass(frozen=True, slots=True)
class SpinResult:
    ok: bool
    locked: bool
    already: bool
    message: str
    reward_type: SpinRewardType | None = None
    reward_value: int = 0


class SpinService:
    # Probabilities (tweak anytime)
    # - cash: very rare
    # - none: some
    # - points: most
    CASH_CHANCE = 0.01      # 1%
    NONE_CHANCE = 0.15      # 15%
    # points is the remainder

    # points bucket (simple)
    POINTS_MIN = 1
    POINTS_MAX = 5

    # cash prize config (store cents in reward_value)
    CASH_CENTS = 500  # $5
    CASH_MAX_PER_USER_PER_WEEK = 1

    @staticmethod
    async def spin(
        session: AsyncSession,
        *,
        user_id: int,
        day_utc: date,
        require_poll: bool,
    ) -> SpinResult:
        # 1) Gatekeeping
        done = await TaskProgressService.done_set(session, user_id=user_id, day_utc=day_utc)

        required = {
            DailyActionType.CHECKIN.value,
            DailyActionType.QUIZ.value,
            DailyActionType.SCREENSHOT.value,
        }
        if require_poll:
            required.add(DailyActionType.POLL_VOTE.value)

        missing = [x for x in sorted(required) if x not in done]
        if missing:
            pretty = ", ".join(missing)
            return SpinResult(
                ok=False,
                locked=True,
                already=False,
                message=(
                    "🎰 <b>Spin is locked</b>\n"
                    "Complete today’s tasks first (UTC):\n"
                    f"• Missing: <b>{pretty}</b>\n\n"
                    "Run /status to see progress."
                ),
            )

        week_start = week_start_monday(day_utc)

        # 2) One spin per day (idempotent insert)
        try:
            async with transactional(session):
                session.add(
                    SpinHistory(
                        user_id=user_id,
                        day_utc=day_utc,
                        week_start=week_start,
                        reward_type=SpinRewardType.NONE,  # will update after roll
                        reward_value=0,
                    )
                )
                await session.flush()
        except IntegrityError:
            await session.rollback()
            return SpinResult(
                ok=True,
                locked=False,
                already=True,
                message="🎰 <b>You already used your spin today (UTC).</b>\nCome back tomorrow!",
            )

        # 3) Roll reward (deterministic per user/day for audit; no external RNG needed)
        seed = f"{user_id}:{day_utc.isoformat()}"
        rng = Random(seed)
        roll = rng.random()

        reward_type: SpinRewardType
        reward_value: int

        # 4) Cash cap per user/week
        can_cash = True
        if SpinService.CASH_MAX_PER_USER_PER_WEEK > 0:
            res = await session.execute(
                select(SpinHistory.id).where(
                    SpinHistory.user_id == user_id,
                    SpinHistory.week_start == week_start,
                    SpinHistory.reward_type == SpinRewardType.CASH,
                )
            )
            cash_wins = len(res.all())
            can_cash = cash_wins < SpinService.CASH_MAX_PER_USER_PER_WEEK

        if roll < SpinService.CASH_CHANCE and can_cash:
            reward_type = SpinRewardType.CASH
            reward_value = SpinService.CASH_CENTS
        elif roll < SpinService.CASH_CHANCE + SpinService.NONE_CHANCE:
            reward_type = SpinRewardType.NONE
            reward_value = 0
        else:
            reward_type = SpinRewardType.POINTS
            reward_value = rng.randint(SpinService.POINTS_MIN, SpinService.POINTS_MAX)

        # 5) Persist reward + award points if needed
        async with transactional(session):
            # Update history row for today
            # (we re-fetch the row to update it safely)
            hist = await session.scalar(
                select(SpinHistory).where(
                    SpinHistory.user_id == user_id,
                    SpinHistory.day_utc == day_utc,
                )
            )
            if hist is None:
                # should never happen, but avoid crashing
                return SpinResult(ok=False, locked=False, already=False, message="Spin error: history missing.")

            hist.reward_type = reward_type
            hist.reward_value = reward_value
            hist.roll = f"{roll:.6f}"

            if reward_type == SpinRewardType.POINTS and reward_value > 0:
                await PointsService.add_points(
                    session,
                    user_id=user_id,
                    week_start=week_start,
                    day_utc=day_utc,
                    source=PointSource.SPIN,
                    points=reward_value,
                    ref_type="spin",
                    ref_id=int(day_utc.strftime("%Y%m%d")),
                )

        # 6) Mark daily action done (use SAVEPOINT-safe mark_done you fixed)
        await TaskProgressService.mark_done(
            session,
            user_id=user_id,
            day_utc=day_utc,
            action_type=DailyActionType.SPIN,
        )

        # 7) Message
        if reward_type == SpinRewardType.CASH:
            msg = "💸 <b>JACKPOT!</b>\nYou won <b>$5 cash</b>! An admin will contact you."
        elif reward_type == SpinRewardType.NONE:
            msg = "😅 <b>No luck this time.</b>\nTry again tomorrow (UTC)."
        else:
            msg = f"🎉 <b>You won +{reward_value} points!</b>"

        return SpinResult(
            ok=True,
            locked=False,
            already=False,
            message=msg,
            reward_type=reward_type,
            reward_value=reward_value,
        )
