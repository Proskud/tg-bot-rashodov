from datetime import datetime
from zoneinfo import ZoneInfo

from expense_bot.scheduler import is_last_day_of_month


def test_last_day_check_uses_configured_timezone() -> None:
    tz = ZoneInfo("Asia/Yekaterinburg")
    # 20:30 UTC on 31 January is already 1 February in Yekaterinburg.
    assert is_last_day_of_month(datetime(2026, 1, 31, 20, 30, tzinfo=ZoneInfo("UTC")), tz) is False
    assert is_last_day_of_month(datetime(2026, 1, 31, 10, 0, tzinfo=ZoneInfo("UTC")), tz) is True
