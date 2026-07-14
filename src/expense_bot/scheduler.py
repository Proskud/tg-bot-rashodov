from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from expense_bot.config import Settings
from expense_bot.reports import build_report, format_report, month_bounds
from expense_bot.repositories import ExpenseRepository

logger = logging.getLogger(__name__)


def is_last_day_of_month(now: datetime, tz: ZoneInfo) -> bool:
    local_now = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    return (local_now + timedelta(days=1)).month != local_now.month


async def send_month_end_reports(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(settings.tzinfo)
    if not is_last_day_of_month(now, settings.tzinfo):
        logger.info("monthly_report_check_skipped")
        return

    local_now = now.astimezone(settings.tzinfo)
    report_month = f"{local_now.year:04d}-{local_now.month:02d}"
    start, end = month_bounds(local_now.year, local_now.month, settings.tzinfo)
    repository = ExpenseRepository(session_factory)
    for user_id in await repository.users_with_expenses(start, end):
        if await repository.was_month_report_sent(user_id, report_month):
            continue
        report = build_report(await repository.list_between(user_id, start, end))
        try:
            await bot.send_message(
                user_id,
                format_report(report, settings.currency, f"Автоматический отчёт за {report_month}"),
            )
            await repository.mark_month_report_sent(user_id, report_month)
            logger.info(
                "monthly_report_sent", extra={"telegram_user_id": user_id, "month": report_month}
            )
        except Exception:
            logger.exception("monthly_report_send_failed", extra={"telegram_user_id": user_id})


def create_scheduler(
    bot: Bot, session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tzinfo)
    scheduler.add_job(
        send_month_end_reports,
        trigger=CronTrigger(hour=settings.monthly_report_hour, minute=0, timezone=settings.tzinfo),
        kwargs={"bot": bot, "session_factory": session_factory, "settings": settings},
        id="monthly_expense_report_check",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=3600,
    )
    return scheduler
