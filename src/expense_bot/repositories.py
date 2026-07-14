from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, distinct, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from expense_bot.models import Expense, MonthlyReportDelivery


class ExpenseRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(
        self,
        *,
        telegram_user_id: int,
        amount: Decimal,
        currency: str,
        category: str,
        description: str,
        spent_at: datetime,
        raw_message: str,
    ) -> Expense:
        expense = Expense(
            telegram_user_id=telegram_user_id,
            amount=amount,
            currency=currency,
            category=category,
            description=description,
            spent_at=spent_at,
            raw_message=raw_message,
        )
        async with self.session_factory() as session:
            session.add(expense)
            await session.commit()
            await session.refresh(expense)
        return expense

    async def list_between(
        self, telegram_user_id: int, start: datetime, end: datetime
    ) -> list[Expense]:
        query = (
            select(Expense)
            .where(
                Expense.telegram_user_id == telegram_user_id,
                Expense.spent_at >= start,
                Expense.spent_at < end,
            )
            .order_by(Expense.spent_at.desc(), Expense.id.desc())
        )
        async with self.session_factory() as session:
            return list((await session.scalars(query)).all())

    async def get_last(self, telegram_user_id: int) -> Expense | None:
        query = (
            select(Expense)
            .where(Expense.telegram_user_id == telegram_user_id)
            .order_by(Expense.created_at.desc(), Expense.id.desc())
            .limit(1)
        )
        async with self.session_factory() as session:
            return (await session.scalars(query)).first()

    async def delete_last(self, telegram_user_id: int) -> Expense | None:
        async with self.session_factory() as session:
            query = (
                select(Expense)
                .where(Expense.telegram_user_id == telegram_user_id)
                .order_by(Expense.created_at.desc(), Expense.id.desc())
                .limit(1)
            )
            expense = (await session.scalars(query)).first()
            if expense is None:
                return None
            await session.delete(expense)
            await session.commit()
            return expense

    async def users_with_expenses(self, start: datetime, end: datetime) -> list[int]:
        query = select(distinct(Expense.telegram_user_id)).where(
            Expense.spent_at >= start, Expense.spent_at < end
        )
        async with self.session_factory() as session:
            return list((await session.scalars(query)).all())

    async def was_month_report_sent(self, telegram_user_id: int, report_month: str) -> bool:
        query = select(MonthlyReportDelivery.id).where(
            MonthlyReportDelivery.telegram_user_id == telegram_user_id,
            MonthlyReportDelivery.report_month == report_month,
        )
        async with self.session_factory() as session:
            return (await session.scalar(query)) is not None

    async def mark_month_report_sent(self, telegram_user_id: int, report_month: str) -> None:
        async with self.session_factory() as session:
            session.add(
                MonthlyReportDelivery(
                    telegram_user_id=telegram_user_id,
                    report_month=report_month,
                )
            )
            await session.commit()

    async def clear_all(self) -> None:
        """Test-only helper; intentionally not exposed through bot commands."""
        async with self.session_factory() as session:
            await session.execute(delete(Expense))
            await session.commit()
