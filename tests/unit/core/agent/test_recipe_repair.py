"""Recipe repair tool tests."""

from ai_crawler.core.agent import RepairRecipeTool
from ai_crawler.core.models import AgentAction, EvidenceBundle, Recipe, RequestSpec


def test_repair_recipe_tool_adds_default_json_items_extraction_after_empty_crawl() -> None:
    recipe = Recipe(
        name="products-api",
        start_url="https://example.test/products",
        requests=(RequestSpec(method="GET", url="https://example.test/api/products"),),
    )
    tool = RepairRecipeTool()
    action = AgentAction(
        name="repair_recipe",
        arguments={
            "recipe": recipe.model_dump(mode="json"),
            "crawl_result": {
                "recipe_name": "products-api",
                "items_written": 0,
                "output_path": "probe.jsonl",
            },
            "test_report": {
                "first_response_status": 200,
                "content_type": "application/json",
                "body_sample": '{"items": [{"name": "Keyboard", "price": 120, "in_stock": true}]}',
                "failure_reason": "no_items_extracted",
            },
        },
    )

    result = tool(action, EvidenceBundle(target_url=recipe.start_url, goal="collect products"))

    assert result.ok is True
    assert result.action_name == "repair_recipe"
    assert result.summary == "repaired recipe: products-api inferred JSON items fields"
    repaired_recipe = Recipe.model_validate(result.artifacts["recipe"])
    assert repaired_recipe.extract.item_path == "$.items[*]"
    assert repaired_recipe.extract.fields == {
        "name": "$.name",
        "price": "$.price",
        "in_stock": "$.in_stock",
    }
    assert repaired_recipe.requests == recipe.requests


def test_repair_recipe_tool_returns_unchanged_recipe_when_no_repair_is_needed() -> None:
    recipe = Recipe(
        name="products-api",
        start_url="https://example.test/products",
        requests=(RequestSpec(method="GET", url="https://example.test/api/products"),),
        extract={"item_path": "$.items[*]", "fields": {}},
    )
    tool = RepairRecipeTool()
    action = AgentAction(
        name="repair_recipe",
        arguments={
            "recipe": recipe.model_dump(mode="json"),
            "crawl_result": {
                "recipe_name": "products-api",
                "items_written": 1,
                "output_path": "probe.jsonl",
            },
        },
    )

    result = tool(action, EvidenceBundle(target_url=recipe.start_url, goal="collect products"))

    assert result.ok is True
    assert result.summary == "recipe did not need deterministic repair: products-api"
    assert Recipe.model_validate(result.artifacts["recipe"]) == recipe


def test_repair_recipe_tool_returns_failure_without_recipe_artifact() -> None:
    tool = RepairRecipeTool()
    action = AgentAction(name="repair_recipe", arguments={})

    result = tool(action, EvidenceBundle(target_url="https://example.test", goal="collect"))

    assert result.ok is False
    assert result.action_name == "repair_recipe"
    assert result.summary == "missing recipe artifact for repair_recipe"
    assert result.artifacts == {}


def test_repair_recipe_tool_returns_failure_for_invalid_recipe_artifact() -> None:
    tool = RepairRecipeTool()
    action = AgentAction(name="repair_recipe", arguments={"recipe": {"name": "bad"}})

    result = tool(action, EvidenceBundle(target_url="https://example.test", goal="collect"))

    assert result.ok is False
    assert result.action_name == "repair_recipe"
    assert result.summary == "invalid recipe artifact for repair_recipe"
    assert result.artifacts == {}
