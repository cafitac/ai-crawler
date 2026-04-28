"""JSON extraction tests."""

from ai_crawler.core.runner import extract_items


def test_extract_items_supports_simple_items_array_and_field_paths() -> None:
    payload = {
        "items": [
            {"id": "p1", "name": "Keyboard", "price": 120},
            {"id": "p2", "name": "Mouse", "price": 40},
        ]
    }

    items = extract_items(
        payload,
        item_path="$.items[*]",
        fields={"name": "$.name", "price": "$.price"},
    )

    assert items == (
        {"name": "Keyboard", "price": 120},
        {"name": "Mouse", "price": 40},
    )


def test_extract_items_returns_empty_tuple_when_path_is_missing() -> None:
    items = extract_items(
        {"data": []},
        item_path="$.items[*]",
        fields={"name": "$.name"},
    )

    assert items == ()
