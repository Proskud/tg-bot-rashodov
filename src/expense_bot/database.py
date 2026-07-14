from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from expense_bot.config import Settings


def create_session_factory(settings: Settings) -> tuple[async_sessionmaker[AsyncSession], object]:
    settings.ensure_sqlite_directory()
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
