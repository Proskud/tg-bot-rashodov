from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from expense_bot.parsing import ParseExpenseError, parse_expense_message

TZ = ZoneInfo("Asia/Yekaterinburg")
NOW = datetime(2026, 7, 13, 12, 30, tzinfo=TZ)


@pytest.mark.parametrize(
    ("message", "expected_amount", "expected_description"),
    [
        ("1450 продукты Перекрёсток", Decimal("1450.00"), "продукты Перекрёсток"),
        ("Кофе 320", Decimal("320.00"), "Кофе"),
        ("Аптека 1840", Decimal("1840.00"), "Аптека"),
        ("2500 кино и ресторан", Decimal("2500.00"), "кино и ресторан"),
    ],
)
def test_parses_integer_amount(
    message: str, expected_amount: Decimal, expected_description: str
) -> None:
    parsed = parse_expense_message(message, TZ, NOW)
    assert parsed.amount == expected_amount
    assert parsed.description == expected_description


def test_parses_comma_decimal_amount() -> None:
    parsed = parse_expense_message("кофе 320,50", TZ, NOW)
    assert parsed.amount == Decimal("320.50")
    assert parsed.description == "кофе"


def test_parses_yesterday_in_local_timezone() -> None:
    parsed = parse_expense_message("740 такси вчера", TZ, NOW)
    assert parsed.spent_at.astimezone(TZ).date().isoformat() == "2026-07-12"
    assert parsed.description == "такси"


def test_parses_explicit_date_before_amount() -> None:
    parsed = parse_expense_message("кино 01.07.2026 100", TZ, NOW)
    assert parsed.amount == Decimal("100.00")
    assert parsed.spent_at.astimezone(TZ).date().isoformat() == "2026-07-01"


def test_rejects_message_without_amount() -> None:
    with pytest.raises(ParseExpenseError):
        parse_expense_message("кофе", TZ, NOW)
