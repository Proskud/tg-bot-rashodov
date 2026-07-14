from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

AMOUNT_PATTERN = re.compile(
    r"(?<![\w.,])(?P<amount>(?:\d{1,3}(?:[ _]\d{3})+|\d+)(?:[.,]\d{1,2})?)(?![\w.,])"
)
ISO_DATE_PATTERN = re.compile(r"(?<!\d)(?P<date>\d{4}-\d{2}-\d{2})(?!\d)")
RU_DATE_PATTERN = re.compile(r"(?<!\d)(?P<date>\d{2}\.\d{2}\.\d{4})(?!\d)")


class ParseExpenseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedExpense:
    amount: Decimal
    description: str
    spent_at: datetime
    raw_message: str


def parse_expense_message(message: str, tz: ZoneInfo, now: datetime | None = None) -> ParsedExpense:
    raw_message = message.strip()
    if not raw_message:
        raise ParseExpenseError("Пустое сообщение")

    local_now = _local_now(now, tz)
    spent_date, text_without_date = _extract_date(raw_message, local_now.date())
    amount_match = AMOUNT_PATTERN.search(text_without_date)
    if amount_match is None:
        raise ParseExpenseError("Не нашёл сумму. Пример: «1450 продукты Перекрёсток».")

    amount = _parse_amount(amount_match.group("amount"))
    cleaned = text_without_date[: amount_match.start()] + text_without_date[amount_match.end() :]
    description = _clean_description(cleaned)
    if not description:
        raise ParseExpenseError("Добавьте описание расхода, например: «Кофе 320».")

    local_spent_at = datetime.combine(spent_date, local_now.timetz().replace(tzinfo=None), tz)
    return ParsedExpense(
        amount=amount,
        description=description,
        spent_at=local_spent_at.astimezone(ZoneInfo("UTC")),
        raw_message=raw_message,
    )


def _parse_amount(value: str) -> Decimal:
    normalized = value.replace(" ", "").replace("_", "").replace(",", ".")
    try:
        amount = Decimal(normalized).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as error:
        raise ParseExpenseError("Некорректная сумма") from error
    if not Decimal("0") < amount <= Decimal("999999999999.99"):
        raise ParseExpenseError("Сумма должна быть больше нуля и не слишком большой")
    return amount


def _extract_date(text: str, default_date: date) -> tuple[date, str]:
    yesterday = re.search(r"(?<!\w)вчера(?!\w)", text, re.IGNORECASE)
    if yesterday:
        return default_date - timedelta(days=1), text[: yesterday.start()] + text[yesterday.end() :]

    today = re.search(r"(?<!\w)сегодня(?!\w)", text, re.IGNORECASE)
    if today:
        return default_date, text[: today.start()] + text[today.end() :]

    for pattern, date_format in ((ISO_DATE_PATTERN, "%Y-%m-%d"), (RU_DATE_PATTERN, "%d.%m.%Y")):
        matched = pattern.search(text)
        if matched:
            try:
                parsed = datetime.strptime(matched.group("date"), date_format).date()
            except ValueError as error:
                raise ParseExpenseError("Некорректная дата") from error
            return parsed, text[: matched.start()] + text[matched.end() :]
    return default_date, text


def _clean_description(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip(" \t,;:-")).strip()


def _local_now(now: datetime | None, tz: ZoneInfo) -> datetime:
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)
