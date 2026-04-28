"""Deterministic recipe generation tool tests."""

from ai_crawler.core.agent import BaselineRecipeGenerator, GenerateRecipeTool
from ai_crawler.core.models import AgentAction, EvidenceBundle, NetworkEvent, Recipe, RequestSpec


def test_baseline_recipe_generator_uses_highest_ranked_network_endpoint() -> None:
    evidence = EvidenceBundle(
        target_url="https://example.test/products",
        goal="collect product names and prices",
        events=(
            NetworkEvent(
                method="GET",
                url="https://example.test/assets/app.js",
                status_code=200,
                resource_type="script",
            ),
            NetworkEvent(
                method="GET",
                url="https://example.test/api/products?page=1",
                status_code=200,
                resource_type="xhr",
            ),
        ),
    )

    recipe = BaselineRecipeGenerator().generate(evidence, name="products-api")

    assert recipe == Recipe(
        name="products-api",
        start_url="https://example.test/products",
        requests=(
            RequestSpec(
                method="GET",
                url="https://example.test/api/products?page=1",
            ),
        ),
    )


def test_generate_recipe_tool_returns_recipe_artifact() -> None:
    evidence = EvidenceBundle(
        target_url="https://example.test/products",
        goal="collect products",
        events=(
            NetworkEvent(
                method="GET",
                url="https://example.test/api/products?page=1",
                status_code=200,
                resource_type="fetch",
            ),
        ),
    )
    action = AgentAction(name="generate_recipe", arguments={"name": "products-api"})

    result = GenerateRecipeTool()(action, evidence)

    assert result.ok is True
    assert result.action_name == "generate_recipe"
    assert result.summary == "generated baseline recipe: products-api"
    assert result.artifacts == {
        "recipe": Recipe(
            name="products-api",
            start_url="https://example.test/products",
            requests=(
                RequestSpec(
                    method="GET",
                    url="https://example.test/api/products?page=1",
                ),
            ),
        ).model_dump(mode="json")
    }


def test_generate_recipe_tool_returns_failure_when_no_endpoint_candidate_exists() -> None:
    evidence = EvidenceBundle(
        target_url="https://example.test/products",
        goal="collect products",
    )
    action = AgentAction(name="generate_recipe", arguments={"name": "products-api"})

    result = GenerateRecipeTool()(action, evidence)

    assert result.ok is False
    assert result.action_name == "generate_recipe"
    assert result.summary == "no endpoint candidates available for recipe generation"
    assert result.artifacts == {}
