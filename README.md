# Telegram-бот для учёта расходов

Бот принимает расходы в свободной форме, локально извлекает сумму, дату и категорию, показывает карточку подтверждения и сохраняет запись в SQLite или PostgreSQL. Внутри нет OpenAI API, LLM или внешней классификации: используются только правила и словарь ключевых слов.

## Возможности

- Сообщения вида `1450 продукты Перекрёсток`, `Кофе 320`, `740 такси вчера`.
- Целые и дробные суммы с точкой или запятой (`320.50`, `320,50`).
- Даты: сегодня по умолчанию, `вчера`, `сегодня`, `YYYY-MM-DD`, `ДД.ММ.ГГГГ`.
- Категории `products`, `entertainment`, `medicine`, `other`; при неуверенной классификации бот предложит выбрать категорию кнопкой.
- Подтверждение перед записью: «Сохранить», «Изменить категорию», «Отмена».
- Команды `/start`, `/help`, `/today`, `/month`, `/report YYYY-MM`, `/last`, `/undo`, `/categories`, `/export [YYYY-MM]`.
- Месячный отчёт: итог, разбивка и проценты по категориям, число записей, крупнейший расход и категория.
- CSV-экспорт за текущий или указанный месяц.
- Ежедневная проверка последнего дня месяца в часовом поясе `TIMEZONE`. Отправки идемпотентны: одному пользователю за месяц отчёт отправляется максимум один раз.
- Доступ только для ID из `ALLOWED_TELEGRAM_USER_IDS`; при пустом списке бот безопасно игнорирует всех.

## Быстрый локальный запуск

Нужен Python 3.12 и токен Telegram-бота от [@BotFather](https://t.me/BotFather).

```bash
cp .env.example .env
# Отредактируйте .env: TELEGRAM_BOT_TOKEN и ALLOWED_TELEGRAM_USER_IDS
python3.12 -m venv .venv
source .venv/bin/activate
pip install '.[dev]'
alembic upgrade head
python -m expense_bot
```

Чтобы узнать свой числовой Telegram ID, можно временно добавить его через любого проверенного ID-бота. Не добавляйте в `.env` чужие идентификаторы.

## Команды

| Команда | Назначение |
| --- | --- |
| `/today` | Расходы за текущий день в `TIMEZONE` |
| `/month` | Отчёт за текущий месяц |
| `/report 2026-07` | Отчёт за конкретный месяц |
| `/last` | Последний сохранённый расход |
| `/undo` | Удалить последний расход |
| `/categories` | Список правил категорий |
| `/export` | CSV текущего месяца |
| `/export 2026-07` | CSV указанного месяца |

## Конфигурация

Все параметры задаются в `.env`.

| Переменная | Обязательность | Описание |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | да | Токен от BotFather. Не попадает в логи. |
| `ALLOWED_TELEGRAM_USER_IDS` | да | Разрешённые ID через запятую: `123,456`. |
| `DATABASE_URL` | нет | По умолчанию SQLite: `sqlite+aiosqlite:///./data/expenses.db`. |
| `TIMEZONE` | нет | IANA-часовой пояс, по умолчанию `Asia/Yekaterinburg`. |
| `CURRENCY` | нет | Трёхбуквенный код валюты, по умолчанию `RUB`. |
| `MONTHLY_REPORT_HOUR` | нет | Час проверки последнего дня месяца, `0–23`, по умолчанию `20`. |
| `LOG_LEVEL` | нет | Уровень структурированных JSON-логов, по умолчанию `INFO`. |

Для PostgreSQL достаточно заменить URL, например:

```dotenv
DATABASE_URL=postgresql+asyncpg://expense_bot:strong-password@db:5432/expenses
```

Также принимаются распространённые URL `postgresql://...` и `sqlite:///...`: приложение автоматически подставит асинхронный драйвер.

## Docker Compose

```bash
cp .env.example .env
# Заполните TELEGRAM_BOT_TOKEN и ALLOWED_TELEGRAM_USER_IDS
docker compose up -d --build
docker compose logs -f bot
```

По умолчанию Compose использует SQLite в именованном томе `expense_data`. При запуске контейнер сам применяет миграции Alembic перед стартом long polling. Для PostgreSQL задайте соответствующий `DATABASE_URL` в `.env`; база может быть управляемой или запущенной отдельным сервисом.

```bash
docker compose down
```

## Миграции и проверки

```bash
alembic upgrade head
ruff check .
pytest
```

Для новой миграции после изменения моделей:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Архитектура

- `src/expense_bot/parsing.py` — разбор суммы, описания и даты.
- `src/expense_bot/categories.py` — локальные правила категорий.
- `src/expense_bot/models.py` и `repositories.py` — SQLAlchemy-модели и операции с данными.
- `src/expense_bot/reports.py` — границы периодов с учётом часового пояса и отчёты.
- `src/expense_bot/scheduler.py` — ежедневная проверка и рассылка в последний день месяца.
- `src/expense_bot/handlers.py` — Telegram-команды, inline-кнопки и CSV.
- `alembic/` — миграции схемы.

SQLite подходит для персонального бота с одним процессом. Для нескольких реплик или высокой параллельной нагрузки используйте PostgreSQL и вынесенное хранилище состояний FSM (например, Redis), чтобы черновики подтверждения переживали перезапуск и были общими между репликами.
