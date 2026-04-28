"""Agent tool for deterministic recipe repairs."""

import json
from typing import Any

from pydantic import ValidationError

from ai_crawler.core.models import AgentAction, EvidenceBundle, ExtractSpec, Recipe, ToolResult


class RepairRecipeTool:
    """Agent tool that repairs known weak baseline recipe patterns."""

    def __call__(self, action: AgentAction, evidence: EvidenceBundle) -> ToolResult:
        recipe = _load_recipe_artifact(action)
        if recipe is None:
            return ToolResult(
                action_name=action.name,
                ok=False,
                summary="missing recipe artifact for repair_recipe",
            )
        if isinstance(recipe, InvalidRecipeArtifact):
            return ToolResult(
                action_name=action.name,
                ok=False,
                summary="invalid recipe artifact for repair_recipe",
            )

        repair_result = _repair_recipe(recipe=recipe, action=action)
        if repair_result.recipe == recipe:
            summary = f"recipe did not need deterministic repair: {recipe.name}"
        elif repair_result.inferred_fields:
            summary = f"repaired recipe: {recipe.name} inferred JSON items fields"
        else:
            summary = f"repaired recipe: {recipe.name} added default JSON items extraction"
        return ToolResult(
            action_name=action.name,
            ok=True,
            summary=summary,
            artifacts={"recipe": repair_result.recipe.model_dump(mode="json")},
        )


class InvalidRecipeArtifact:
    """Sentinel for malformed recipe artifacts."""


class RepairResult:
    """Result of a deterministic recipe repair attempt."""

    def __init__(self, recipe: Recipe, inferred_fields: bool) -> None:
        self.recipe = recipe
        self.inferred_fields = inferred_fields


def _load_recipe_artifact(action: AgentAction) -> Recipe | InvalidRecipeArtifact | None:
    artifact = action.arguments.get("recipe")
    if artifact is None:
        return None
    try:
        return Recipe.model_validate(artifact)
    except ValidationError:
        return InvalidRecipeArtifact()


def _repair_recipe(recipe: Recipe, action: AgentAction) -> RepairResult:
    if recipe.extract.item_path:
        return RepairResult(recipe=recipe, inferred_fields=False)
    if _items_written(action) != 0:
        return RepairResult(recipe=recipe, inferred_fields=False)

    fields = _infer_json_items_fields(action)
    repaired_recipe = recipe.model_copy(
        update={"extract": ExtractSpec(item_path="$.items[*]", fields=fields)}
    )
    return RepairResult(recipe=repaired_recipe, inferred_fields=bool(fields))


def _items_written(action: AgentAction) -> int:
    crawl_result = action.arguments.get("crawl_result")
    if not isinstance(crawl_result, dict):
        return -1
    items_written = crawl_result.get("items_written")
    if isinstance(items_written, int):
        return items_written
    return -1


def _infer_json_items_fields(action: AgentAction) -> dict[str, str]:
    test_report = action.arguments.get("test_report")
    if not isinstance(test_report, dict):
        return {}
    body_sample = test_report.get("body_sample")
    if not isinstance(body_sample, str) or not body_sample:
        return {}
    try:
        payload = json.loads(body_sample)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return {}
    first_item = raw_items[0]
    if not isinstance(first_item, dict):
        return {}
    return _scalar_field_paths(first_item)


def _scalar_field_paths(item: dict[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key, value in item.items():
        if isinstance(key, str) and _is_scalar(value):
            fields[key] = f"$.{key}"
    return fields


def _is_scalar(value: Any) -> bool:
    return isinstance(value, str | int | float | bool)
