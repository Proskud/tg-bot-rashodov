from __future__ import annotations

import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncEngine

from expense_bot.config import Settings
from expense_bot.database import create_session_factory
from expense_bot.handlers import router
from expense_bot.logging import configure_logging
from expense_bot.middlewares import AccessMiddleware
from expense_bot.scheduler import create_scheduler, send_month_end_reports

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    if not settings.allowed_user_ids:
        logger.warning("allowed_user_ids_empty_bot_will_ignore_all_users")

    session_factory, engine = create_session_factory(settings)
    bot = Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    dispatcher.message.outer_middleware(AccessMiddleware(settings))
    dispatcher.callback_query.outer_middleware(AccessMiddleware(settings))
    scheduler = create_scheduler(bot, session_factory, settings)

    try:
        scheduler.start()
        # A startup pass covers restarts after the scheduled hour on the last day.
        await send_month_end_reports(bot, session_factory, settings)
        logger.info("bot_started")
        await dispatcher.start_polling(bot, settings=settings, session_factory=session_factory)
    finally:
        scheduler.shutdown(wait=False)
        with suppress(Exception):
            await bot.session.close()
        await _dispose_engine(engine)
        logger.info("bot_stopped")


async def _dispose_engine(engine: object) -> None:
    if isinstance(engine, AsyncEngine):
        await engine.dispose()
