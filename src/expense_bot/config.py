from __future__ import annotations

from functools import cached_property
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration read from environment variables and .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: SecretStr
    allowed_telegram_user_ids: str = Field(default="")
    database_url: str = "sqlite+aiosqlite:///./data/expenses.db"
    timezone: str = "Asia/Yekaterinburg"
    currency: str = "RUB"
    monthly_report_hour: int = Field(default=20, ge=0, le=23)
    log_level: str = "INFO"

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        value = value.upper().strip()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("CURRENCY must be a three-letter ISO code")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"Unknown IANA timezone: {value}") from error
        return value

    @cached_property
    def allowed_user_ids(self) -> frozenset[int]:
        values = (item.strip() for item in self.allowed_telegram_user_ids.split(","))
        try:
            return frozenset(int(item) for item in values if item)
        except ValueError as error:
            raise ValueError(
                "ALLOWED_TELEGRAM_USER_IDS must be comma-separated integers"
            ) from error

    @cached_property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @cached_property
    def async_database_url(self) -> str:
        """Normalise common SQLAlchemy sync URLs to async driver URLs."""
        url = self.database_url.strip()
        if url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
            return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    def is_user_allowed(self, telegram_user_id: int) -> bool:
        """Deny all access until at least one explicit identifier is configured."""
        return bool(self.allowed_user_ids) and telegram_user_id in self.allowed_user_ids

    def ensure_sqlite_directory(self) -> None:
        if (
            self.async_database_url.startswith("sqlite")
            and ":memory:" not in self.async_database_url
        ):
            database_path = self.async_database_url.rsplit("///", maxsplit=1)[-1]
            Path(database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
