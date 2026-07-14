from types import SimpleNamespace

import pytest

from expense_bot.config import Settings
from expense_bot.middlewares import AccessMiddleware


@pytest.mark.asyncio
async def test_unknown_user_is_not_passed_to_handler() -> None:
    settings = Settings(
        telegram_bot_token="test-token",
        allowed_telegram_user_ids="100,200",
    )
    middleware = AccessMiddleware(settings)
    called = False

    async def handler(event, data):
        nonlocal called
        called = True
        return "handled"

    result = await middleware(handler, SimpleNamespace(from_user=SimpleNamespace(id=999)), {})
    assert result is None
    assert called is False
