from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    ErrorEvent,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from expense_bot.categories import CATEGORY_LABELS, Category, category_label, detect_category
from expense_bot.config import Settings
from expense_bot.parsing import ParseExpenseError, parse_expense_message
from expense_bot.reports import (
    build_report,
    day_bounds,
    format_money,
    format_report,
    month_bounds,
)
from expense_bot.repositories import ExpenseRepository

router = Router(name="expenses")
logger = logging.getLogger(__name__)


class ExpenseStates(StatesGroup):
    choosing_category = State()
    confirming = State()


HELP_TEXT = (
    "Отправьте расход обычным сообщением:\n"
    "• <code>1450 продукты Перекрёсток</code>\n"
    "• <code>Кофе 320</code>\n"
    "• <code>740 такси вчера</code>\n\n"
    "Команды: /today, /month, /report YYYY-MM, /last, /undo, /categories, /export [YYYY-MM]."
)


def category_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=CATEGORY_LABELS[category], callback_data=f"category:{category}"
                )
            ]
            for category in Category
        ]
    )


def confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сохранить", callback_data="expense:save")],
            [InlineKeyboardButton(text="Изменить категорию", callback_data="expense:category")],
            [InlineKeyboardButton(text="Отмена", callback_data="expense:cancel")],
        ]
    )


async def _show_preview(message: Message, state: FSMContext, settings: Settings) -> None:
    data = await state.get_data()
    category = Category(data["category"])
    amount = Decimal(data["amount"])
    spent_at = datetime.fromisoformat(data["spent_at"]).astimezone(settings.tzinfo)
    preview = (
        "Проверьте расход:\n"
        f"• Сумма: <b>{format_money(amount)} {settings.currency}</b>\n"
        f"• Описание: {data['description']}\n"
        f"• Категория: {category_label(category)}\n"
        f"• Дата: {spent_at:%d.%m.%Y}"
    )
    await state.set_state(ExpenseStates.confirming)
    await message.answer(preview, reply_markup=confirmation_keyboard())


async def _load_report(
    session_factory: async_sessionmaker[AsyncSession],
    telegram_user_id: int,
    start: datetime,
    end: datetime,
):
    return build_report(
        await ExpenseRepository(session_factory).list_between(telegram_user_id, start, end)
    )


@router.message(Command("start"))
async def command_start(message: Message) -> None:
    await message.answer("Привет! Я помогу учитывать личные расходы.\n\n" + HELP_TEXT)


@router.message(Command("help"))
async def command_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("today"))
async def command_today(
    message: Message, settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    now = datetime.now(settings.tzinfo)
    start, end = day_bounds(now.date(), settings.tzinfo)
    report = await _load_report(session_factory, message.from_user.id, start, end)
    await message.answer(
        format_report(report, settings.currency, f"Расходы за сегодня ({now:%d.%m.%Y})")
    )


@router.message(Command("month"))
async def command_month(
    message: Message, settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    now = datetime.now(settings.tzinfo)
    start, end = month_bounds(now.year, now.month, settings.tzinfo)
    report = await _load_report(session_factory, message.from_user.id, start, end)
    await message.answer(format_report(report, settings.currency, f"Отчёт за {now:%Y-%m}"))


@router.message(Command("report"))
async def command_report(
    message: Message,
    command: CommandObject,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not command.args or not re.fullmatch(r"\d{4}-\d{2}", command.args.strip()):
        await message.answer("Использование: <code>/report YYYY-MM</code>")
        return
    try:
        year, month = map(int, command.args.strip().split("-"))
        start, end = month_bounds(year, month, settings.tzinfo)
    except ValueError:
        await message.answer("Укажите существующий месяц, например: <code>/report 2026-07</code>")
        return
    report = await _load_report(session_factory, message.from_user.id, start, end)
    await message.answer(
        format_report(report, settings.currency, f"Отчёт за {year:04d}-{month:02d}")
    )


@router.message(Command("last"))
async def command_last(
    message: Message, session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    expense = await ExpenseRepository(session_factory).get_last(message.from_user.id)
    if expense is None:
        await message.answer("Расходов пока нет.")
        return
    spent_at = expense.spent_at.astimezone(settings.tzinfo)
    await message.answer(
        "Последний расход:\n"
        f"• {format_money(Decimal(expense.amount))} {expense.currency} — {expense.description}\n"
        f"• {category_label(expense.category)}, {spent_at:%d.%m.%Y}"
    )


@router.message(Command("undo"))
async def command_undo(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    expense = await ExpenseRepository(session_factory).delete_last(message.from_user.id)
    if expense is None:
        await message.answer("Удалять нечего.")
        return
    amount = format_money(Decimal(expense.amount))
    await message.answer(f"Удалён расход: {amount} {expense.currency} — {expense.description}.")


@router.message(Command("categories"))
async def command_categories(message: Message) -> None:
    await message.answer(
        "Категории:\n"
        "• Продукты — магазины, еда, кофе\n"
        "• Развлечения — кино, рестораны, концерты\n"
        "• Медицина — аптеки, врачи, анализы\n"
        "• Другое — такси, транспорт, связь и прочие расходы"
    )


@router.message(Command("export"))
async def command_export(
    message: Message,
    command: CommandObject,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    argument = command.args.strip() if command.args else ""
    if argument and not re.fullmatch(r"\d{4}-\d{2}", argument):
        await message.answer("Использование: <code>/export</code> или <code>/export YYYY-MM</code>")
        return
    if argument:
        try:
            year, month = map(int, argument.split("-"))
            start, end = month_bounds(year, month, settings.tzinfo)
        except ValueError:
            await message.answer(
                "Укажите существующий месяц, например: <code>/export 2026-07</code>"
            )
            return
    else:
        now = datetime.now(settings.tzinfo)
        year, month = now.year, now.month
        start, end = month_bounds(year, month, settings.tzinfo)
    expenses = await ExpenseRepository(session_factory).list_between(
        message.from_user.id, start, end
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        ["id", "amount", "currency", "category", "description", "spent_at", "created_at"]
    )
    for expense in expenses:
        writer.writerow(
            [
                expense.id,
                f"{Decimal(expense.amount):.2f}",
                expense.currency,
                expense.category,
                expense.description,
                expense.spent_at.astimezone(settings.tzinfo).isoformat(),
                expense.created_at.astimezone(settings.tzinfo).isoformat(),
            ]
        )
    month_label = f"{year:04d}-{month:02d}"
    document = BufferedInputFile(
        output.getvalue().encode("utf-8-sig"), filename=f"expenses-{month_label}.csv"
    )
    await message.answer_document(document, caption=f"Экспорт расходов за {month_label}.")


@router.callback_query(F.data.startswith("category:"))
async def callback_category(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    category_value = callback.data.removeprefix("category:")
    try:
        category = Category(category_value)
    except ValueError:
        await callback.answer("Неизвестная категория", show_alert=True)
        return
    data = await state.get_data()
    if not data.get("amount"):
        await callback.answer("Черновик расхода устарел", show_alert=True)
        return
    await state.update_data(category=category.value)
    await callback.answer()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await _show_preview(callback.message, state, settings)


@router.callback_query(F.data == "expense:category")
async def callback_edit_category(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("amount"):
        await callback.answer("Черновик расхода устарел", show_alert=True)
        return
    await state.set_state(ExpenseStates.choosing_category)
    await callback.answer()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Выберите категорию:", reply_markup=category_keyboard())


@router.callback_query(F.data == "expense:cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Отменено")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Расход не сохранён.")


@router.callback_query(F.data == "expense:save")
async def callback_save(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    data = await state.get_data()
    if not all(
        data.get(key) for key in ("amount", "description", "spent_at", "raw_message", "category")
    ):
        await callback.answer("Черновик расхода устарел", show_alert=True)
        return
    assert callback.from_user is not None
    expense = await ExpenseRepository(session_factory).create(
        telegram_user_id=callback.from_user.id,
        amount=Decimal(data["amount"]),
        currency=settings.currency,
        category=data["category"],
        description=data["description"],
        spent_at=datetime.fromisoformat(data["spent_at"]),
        raw_message=data["raw_message"],
    )
    await state.clear()
    await callback.answer("Сохранено")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        amount = format_money(Decimal(expense.amount))
        await callback.message.answer(
            f"Сохранено: {amount} {settings.currency} — {expense.description}."
        )
    logger.info(
        "expense_saved",
        extra={"expense_id": expense.id, "telegram_user_id": expense.telegram_user_id},
    )


@router.message(F.text)
async def incoming_expense(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.from_user is None or message.text is None:
        return
    try:
        parsed = parse_expense_message(message.text, settings.tzinfo)
    except ParseExpenseError as error:
        await message.answer(str(error))
        return

    match = detect_category(parsed.description)
    await state.update_data(
        amount=str(parsed.amount),
        description=parsed.description,
        spent_at=parsed.spent_at.isoformat(),
        raw_message=parsed.raw_message,
        category=match.category.value if match.category else None,
    )
    if match.confident and match.category:
        await _show_preview(message, state, settings)
    else:
        await state.set_state(ExpenseStates.choosing_category)
        await message.answer(
            "Не уверен в категории. Выберите её перед сохранением:",
            reply_markup=category_keyboard(),
        )


@router.error()
async def handle_error(event: ErrorEvent) -> bool:
    logger.exception("telegram_handler_failed", exc_info=event.exception)
    if isinstance(event.update.message, Message):
        await event.update.message.answer("Не удалось обработать запрос. Попробуйте ещё раз.")
    return True
