"""Small JSON extraction helpers for recipe runner output."""

from typing import Any

JsonObject = dict[str, Any]


def extract_items(
    payload: JsonObject,
    item_path: str,
    fields: dict[str, str],
) -> tuple[JsonObject, ...]:
    """Extract item objects from a JSON payload using a small supported path subset."""
    raw_items = _select_items(payload, item_path)
    if not fields:
        return tuple(raw_items)
    return tuple(_project_fields(item, fields) for item in raw_items)


def _select_items(payload: JsonObject, item_path: str) -> tuple[JsonObject, ...]:
    if item_path != "$.items[*]":
        return ()
    raw_items = payload.get("items", [])
    if not isinstance(raw_items, list):
        return ()
    return tuple(item for item in raw_items if isinstance(item, dict))


def _project_fields(item: JsonObject, fields: dict[str, str]) -> JsonObject:
    projected: JsonObject = {}
    for output_name, field_path in fields.items():
        projected[output_name] = _select_scalar(item, field_path)
    return projected


def _select_scalar(item: JsonObject, field_path: str) -> Any:
    if not field_path.startswith("$."):
        return ""
    key = field_path[2:]
    return item.get(key, "")
