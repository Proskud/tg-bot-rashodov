import pytest

from expense_bot.categories import Category, detect_category


@pytest.mark.parametrize(
    ("description", "category"),
    [
        ("Продукты Перекрёсток", Category.PRODUCTS),
        ("кино и ресторан", Category.ENTERTAINMENT),
        ("Аптека и лекарства", Category.MEDICINE),
        ("такси до дома", Category.OTHER),
    ],
)
def test_detects_category(description: str, category: Category) -> None:
    match = detect_category(description)
    assert match.category == category
    assert match.confident is True


def test_unknown_category_requires_user_choice() -> None:
    match = detect_category("подарок коллеге")
    assert match.category is None
    assert match.confident is False


def test_conflicting_categories_require_user_choice() -> None:
    match = detect_category("аптека и кино")
    assert match.category is None
    assert match.confident is False
