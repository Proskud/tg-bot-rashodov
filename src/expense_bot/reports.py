from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from expense_bot.categories import CATEGORY_LABELS, Category, category_label
from expense_bot.models import Expense


@dataclass(frozen=True)
class CategoryTotal:
    category: Category
    amount: Decimal
    percent: Decimal


@dataclass(frozen=True)
class ExpenseReport:
    total: Decimal
    count: int
    by_category: tuple[CategoryTotal, ...]
    largest_expense: Expense | None
    largest_category: Category | None


def month_bounds(year: int, month: int, tz: ZoneInfo) -> tuple[datetime, datetime]:
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    start_local = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        end_local = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end_local = datetime(year, month + 1, 1, tzinfo=tz)
    return start_local.astimezone(ZoneInfo("UTC")), end_local.astimezone(ZoneInfo("UTC"))


def day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start_local = datetime.combine(day, time.min, tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(ZoneInfo("UTC")), end_local.astimezone(ZoneInfo("UTC"))


def build_report(expenses: list[Expense]) -> ExpenseReport:
    totals = {category: Decimal("0.00") for category in Category}
    for expense in expenses:
        totals[Category(expense.category)] += Decimal(expense.amount)

    total = sum(totals.values(), start=Decimal("0.00"))
    category_totals = tuple(
        CategoryTotal(
            category=category,
            amount=amount.quantize(Decimal("0.01")),
            percent=(
                (amount / total * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                if total
                else Decimal("0.0")
            ),
        )
        for category, amount in totals.items()
    )
    largest_expense = max(expenses, key=lambda item: (item.amount, item.id), default=None)
    largest_category = max(
        Category,
        key=lambda category: (totals[category], -list(Category).index(category)),
        default=None,
    )
    if not total:
        largest_category = None
    return ExpenseReport(
        total=total.quantize(Decimal("0.01")),
        count=len(expenses),
        by_category=category_totals,
        largest_expense=largest_expense,
        largest_category=largest_category,
    )


def format_report(report: ExpenseReport, currency: str, title: str) -> str:
    lines = [
        title,
        "",
        f"Итого: <b>{format_money(report.total)} {currency}</b>",
        f"Записей: {report.count}",
        "",
        "По категориям:",
    ]
    for item in report.by_category:
        label = CATEGORY_LABELS[item.category]
        amount = format_money(item.amount)
        lines.append(f"• {label}: {amount} {currency} ({item.percent}%)")
    if report.largest_expense:
        lines.extend(
            [
                "",
                "Самый крупный расход:",
                f"• {format_money(Decimal(report.largest_expense.amount))} {currency} — "
                f"{report.largest_expense.description}",
                f"Крупнейшая категория: {category_label(report.largest_category)}",
            ]
        )
    return "\n".join(lines)


def format_money(amount: Decimal) -> str:
    return f"{amount.quantize(Decimal('0.01')):,.2f}".replace(",", " ").replace(".", ",")
