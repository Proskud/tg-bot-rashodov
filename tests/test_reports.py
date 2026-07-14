from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from expense_bot.categories import Category
from expense_bot.models import Expense
from expense_bot.reports import build_report, month_bounds
from expense_bot.repositories import ExpenseRepository


def test_month_bounds_respect_timezone_at_month_boundary() -> None:
    tz = ZoneInfo("Asia/Yekaterinburg")
    start, end = month_bounds(2026, 3, tz)
    assert start.isoformat() == "2026-02-28T19:00:00+00:00"
    assert end.isoformat() == "2026-03-31T19:00:00+00:00"


def test_builds_monthly_report() -> None:
    expenses = [
        Expense(id=1, amount=Decimal("100.00"), category="products", description="Магазин"),
        Expense(id=2, amount=Decimal("300.00"), category="entertainment", description="Кино"),
        Expense(id=3, amount=Decimal("100.00"), category="products", description="Кофе"),
    ]
    report = build_report(expenses)
    assert report.total == Decimal("500.00")
    assert report.count == 3
    assert report.largest_expense is not None
    assert report.largest_expense.description == "Кино"
    assert report.largest_category == Category.ENTERTAINMENT
    products = next(item for item in report.by_category if item.category == Category.PRODUCTS)
    assert products.amount == Decimal("200.00")
    assert products.percent == Decimal("40.0")


@pytest.mark.asyncio
async def test_deletes_last_expense(session_factory) -> None:
    repository = ExpenseRepository(session_factory)
    first = await repository.create(
        telegram_user_id=42,
        amount=Decimal("100.00"),
        currency="RUB",
        category="products",
        description="Первый",
        spent_at=datetime(2026, 7, 1, tzinfo=ZoneInfo("UTC")),
        raw_message="100 Первый",
    )
    second = await repository.create(
        telegram_user_id=42,
        amount=Decimal("200.00"),
        currency="RUB",
        category="other",
        description="Второй",
        spent_at=datetime(2026, 7, 2, tzinfo=ZoneInfo("UTC")),
        raw_message="200 Второй",
    )
    deleted = await repository.delete_last(42)
    assert deleted is not None
    assert deleted.id == second.id
    assert (await repository.get_last(42)).id == first.id
