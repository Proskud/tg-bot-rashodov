# Expense Tracker Bot

> Личный Telegram-бот для быстрого учёта расходов: напишите сумму обычным сообщением, подтвердите запись — и получайте понятные отчёты без таблиц и ручного ввода.

[![CI](https://github.com/Proskud/tg-bot-rashodov/actions/workflows/ci.yml/badge.svg)](https://github.com/Proskud/tg-bot-rashodov/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3120/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`Expense Tracker Bot` принимает расходы в свободной форме, сам выделяет сумму, дату и предполагаемую категорию. Он работает по локальным правилам: внутри нет OpenAI API, LLM или передачи финансовых данных сторонним сервисам.

## Что умеет

- Принимает сообщения в привычной форме: `1450 продукты Перекрёсток`, `Кофе 320`, `740 такси вчера`.
- Понимает целые и дробные суммы с точкой или запятой: `320.50`, `320,50`, `1 450`.
- Распознаёт `сегодня`, `вчера`, `YYYY-MM-DD` и `ДД.ММ.ГГГГ`; по умолчанию использует текущий день в выбранном часовом поясе.
- Определяет категории `products`, `entertainment`, `medicine`, `other` по явному названию или локальному словарю. При сомнении показывает inline-кнопки выбора.
- Всегда показывает карточку подтверждения перед сохранением: «Сохранить», «Изменить категорию», «Отмена».
- Строит дневные и месячные отчёты: итог, разбивка и проценты по категориям, число записей, крупнейший расход и крупнейшая категория.
- Выгружает расходы за месяц в UTF-8 CSV.
- В последний день месяца автоматически присылает отчёт в часовом поясе `TIMEZONE`; повторная отправка за тот же месяц исключена.

## Установка на сервер одной командой

Для чистого сервера на Ubuntu или Debian выполните:

```bash
(install_script="$(mktemp)" && trap 'rm -f "$install_script"' EXIT && curl -fsSL https://raw.githubusercontent.com/Proskud/tg-bot-rashodov/main/bootstrap.sh -o "$install_script" && sudo bash "$install_script")
```

Установщик без вывода токена запросит:

1. токен Telegram-бота от [@BotFather](https://t.me/BotFather);
2. один или несколько разрешённых Telegram ID через запятую;

Он скачает проект в `/opt/tg-bot-rashodov`, создаст `.env` с правами `600`, при необходимости установит Git, Docker и Docker Compose из системных пакетов Ubuntu/Debian, соберёт образ и запустит бота. Токен не передаётся через аргументы команд и не попадает в историю терминала. GitHub-логин и пароль не требуются.

По умолчанию используются `Asia/Yekaterinburg`, `RUB` и отправка автоматического отчёта в `20:00`. При необходимости измените `TIMEZONE`, `CURRENCY` и `MONTHLY_REPORT_HOUR` в `/opt/tg-bot-rashodov/.env`, затем перезапустите контейнер.

Альтернативная установка через Git также работает без авторизации:

```bash
git clone --depth 1 https://github.com/Proskud/tg-bot-rashodov.git && sudo bash tg-bot-rashodov/install.sh
```

### Обновление и повторная настройка

```bash
(install_script="$(mktemp)" && trap 'rm -f "$install_script"' EXIT && curl -fsSL https://raw.githubusercontent.com/Proskud/tg-bot-rashodov/main/bootstrap.sh -o "$install_script" && sudo bash "$install_script")
```

Bootstrap-скрипт обновит проект через `git pull --ff-only`. Если `.env` уже существует, установщик предложит оставить текущую конфигурацию или ввести значения заново.

### Проверка после установки

```bash
cd /opt/tg-bot-rashodov
sudo docker compose ps
sudo docker compose logs -f bot
```

## Как пользоваться

Отправьте боту сообщение с суммой и описанием. Он покажет результат и попросит подтверждение.

| Сообщение | Что будет сохранено |
| --- | --- |
| `1450 продукты Перекрёсток` | 1 450 RUB · продукты · сегодня |
| `Кофе 320` | 320 RUB · продукты · сегодня |
| `Аптека 1840` | 1 840 RUB · медицина · сегодня |
| `2500 кино и ресторан` | 2 500 RUB · развлечения · сегодня |
| `740 такси вчера` | 740 RUB · другое · вчера |

Если одно сообщение подходит нескольким категориям или не подходит ни к одной, бот не угадывает — он просит выбрать категорию кнопкой.

### Команды

| Команда | Назначение |
| --- | --- |
| `/start` | Краткое знакомство и примеры |
| `/help` | Подсказка по формату расходов и командам |
| `/today` | Расходы за текущий день в `TIMEZONE` |
| `/month` | Отчёт за текущий месяц |
| `/report 2026-07` | Отчёт за выбранный месяц |
| `/last` | Последний сохранённый расход |
| `/undo` | Удалить последний расход |
| `/categories` | Список правил категорий |
| `/export` | CSV за текущий месяц |
| `/export 2026-07` | CSV за выбранный месяц |

## Конфигурация

Все параметры задаются в `.env`; шаблон есть в [.env.example](.env.example).

| Переменная | Обязательность | Описание |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | да | Токен от BotFather. Обрабатывается как секрет и не выводится в логи. |
| `ALLOWED_TELEGRAM_USER_IDS` | да | Список разрешённых числовых ID через запятую: `123,456`. Пустой список запрещает доступ всем. |
| `DATABASE_URL` | нет | SQLite по умолчанию: `sqlite+aiosqlite:///./data/expenses.db`. |
| `TIMEZONE` | нет | IANA-часовой пояс, по умолчанию `Asia/Yekaterinburg`. |
| `CURRENCY` | нет | Трёхбуквенный код валюты, по умолчанию `RUB`. |
| `MONTHLY_REPORT_HOUR` | нет | Час ежедневной проверки последнего дня месяца, `0–23`; по умолчанию `20`. |
| `LOG_LEVEL` | нет | Уровень JSON-логов, по умолчанию `INFO`. |

Для PostgreSQL укажите, например:

```dotenv
DATABASE_URL=postgresql+asyncpg://expense_bot:strong-password@db:5432/expenses
```

Поддерживаются также URL `postgresql://…` и `sqlite:///…`: приложение само добавит асинхронный драйвер.

## Локальный запуск

Нужен Python 3.12.

```bash
cp .env.example .env
# Заполните TELEGRAM_BOT_TOKEN и ALLOWED_TELEGRAM_USER_IDS
python3.12 -m venv .venv
source .venv/bin/activate
pip install '.[dev]'
alembic upgrade head
python -m expense_bot
```

Либо запустите через Compose:

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f bot
```

SQLite хранится в именованном Docker-томе `expense_data`. Для нескольких реплик или более высокой параллельной нагрузки используйте PostgreSQL и общее хранилище FSM (например, Redis).

## Безопасность и данные

- Доступ ограничен явным allow-list из `ALLOWED_TELEGRAM_USER_IDS`; неизвестные пользователи игнорируются.
- Токен не логируется, а `.env` исключён из Git.
- Суммы сохраняются в точном `Decimal`-типе, а не в `float`.
- По умолчанию данные остаются в вашей SQLite-базе; для управляемой БД поддерживается PostgreSQL.
- Классификация и обработка текста работают локально, без внешних AI-сервисов.

## Технологии

Python 3.12 · aiogram 3 · SQLAlchemy 2 · Alembic · APScheduler · SQLite / PostgreSQL · pytest · Docker Compose

## Разработка и проверки

```bash
alembic upgrade head
ruff format --check .
ruff check .
pytest -q
bash -n install.sh
bash install.sh --self-test
```

При каждом push и pull request GitHub Actions запускает форматирование, линтер и тесты на Python 3.12.

Для новой миграции:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Структура проекта

```text
src/expense_bot/
├── parsing.py       # сумма, описание и дата
├── categories.py    # локальные правила категорий
├── handlers.py      # команды, inline-кнопки и CSV
├── reports.py       # периоды и месячные отчёты
├── scheduler.py     # рассылка в последний день месяца
├── models.py        # SQLAlchemy-модели
└── repositories.py  # операции с данными
alembic/             # миграции схемы
tests/               # тесты правил, отчётов и доступа
install.sh           # интерактивная серверная установка
bootstrap.sh         # загрузка и запуск установщика одной командой
```

## Релизы

Текущий релиз: [v0.1.0](CHANGELOG.md#010---2026-07-14). История изменений — в [CHANGELOG.md](CHANGELOG.md). Проект распространяется по [MIT License](LICENSE).
