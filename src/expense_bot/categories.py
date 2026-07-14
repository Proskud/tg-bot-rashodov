from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class Category(StrEnum):
    PRODUCTS = "products"
    ENTERTAINMENT = "entertainment"
    MEDICINE = "medicine"
    OTHER = "other"


CATEGORY_LABELS: dict[Category, str] = {
    Category.PRODUCTS: "Продукты",
    Category.ENTERTAINMENT: "Развлечения",
    Category.MEDICINE: "Медицина",
    Category.OTHER: "Другое",
}

# Exact category names are treated as a deliberate, explicit choice.
EXPLICIT_ALIASES: dict[Category, tuple[str, ...]] = {
    Category.PRODUCTS: ("products", "продукты"),
    Category.ENTERTAINMENT: ("entertainment", "развлечения"),
    Category.MEDICINE: ("medicine", "медицина"),
    Category.OTHER: ("other", "другое", "прочее"),
}

KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.PRODUCTS: (
        "перекр[её]сток",
        "пят[её]рочка",
        "вкусвилл",
        "лента",
        "ашан",
        "магнит",
        "супермаркет",
        "продукт",
        "еда",
        "обед",
        "ужин",
        "завтрак",
        "кофе",
    ),
    Category.ENTERTAINMENT: (
        "кино",
        "театр",
        "концерт",
        "музей",
        "ресторан",
        "бар",
        "клуб",
        "игр",
        "подписк",
        "netflix",
    ),
    Category.MEDICINE: (
        "аптек",
        "лекарств",
        "таблет",
        "врач",
        "клиник",
        "стоматолог",
        "анализ",
    ),
    Category.OTHER: ("такси", "транспорт", "одежд", "связь", "интернет", "коммунал"),
}


@dataclass(frozen=True)
class CategoryMatch:
    category: Category | None
    confident: bool


def detect_category(description: str) -> CategoryMatch:
    """Classify locally. Conflicting or absent signals intentionally require confirmation."""
    normalized = description.lower().replace("ё", "е")

    explicit_matches = [
        category
        for category, aliases in EXPLICIT_ALIASES.items()
        if any(re.search(rf"(?<!\\w){re.escape(alias)}(?!\\w)", normalized) for alias in aliases)
    ]
    if len(set(explicit_matches)) == 1:
        return CategoryMatch(explicit_matches[0], confident=True)
    if len(set(explicit_matches)) > 1:
        return CategoryMatch(None, confident=False)

    scores = {
        category: sum(bool(re.search(keyword, normalized)) for keyword in keywords)
        for category, keywords in KEYWORDS.items()
    }
    best_score = max(scores.values())
    if best_score == 0:
        return CategoryMatch(None, confident=False)

    winners = [category for category, score in scores.items() if score == best_score]
    if len(winners) != 1:
        return CategoryMatch(None, confident=False)
    return CategoryMatch(winners[0], confident=True)


def category_label(category: Category | str) -> str:
    return CATEGORY_LABELS[Category(category)]
