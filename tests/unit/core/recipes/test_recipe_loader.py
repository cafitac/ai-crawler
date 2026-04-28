"""Recipe loading and validation tests."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_crawler.core.models import Recipe, RequestSpec
from ai_crawler.core.recipes import RecipeLoader

RECIPE_YAML = """
name: products-api
start_url: https://example.test/products
requests:
  - id: list-products
    method: get
    url: https://example.test/api/products
    query:
      page: "1"
    headers:
      accept: application/json
pagination:
  strategy: query_page
  query_param: page
  start: 1
  max_pages: 3
extract:
  item_path: $.items[*]
  fields:
    name: $.name
    price: $.price
validation:
  min_items: 1
execution:
  concurrency: 2
  delay_ms: 50
"""


def test_recipe_loader_loads_yaml_string_into_explicit_models() -> None:
    recipe = RecipeLoader().load_text(RECIPE_YAML)

    assert recipe.name == "products-api"
    assert recipe.start_url == "https://example.test/products"
    assert recipe.requests == (
        RequestSpec(
            id="list-products",
            method="GET",
            url="https://example.test/api/products",
            query={"page": "1"},
            headers={"accept": "application/json"},
        ),
    )
    assert recipe.pagination.strategy == "query_page"
    assert recipe.pagination.query_param == "page"
    assert recipe.extract.item_path == "$.items[*]"
    assert recipe.extract.fields == {"name": "$.name", "price": "$.price"}
    assert recipe.validation.min_items == 1
    assert recipe.execution.concurrency == 2
    assert recipe.execution.delay_ms == 50


def test_recipe_loader_loads_yaml_file(tmp_path: Path) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    recipe_path.write_text(RECIPE_YAML, encoding="utf-8")

    recipe = RecipeLoader().load_file(recipe_path)

    assert recipe.name == "products-api"


def test_recipe_requires_at_least_one_request() -> None:
    with pytest.raises(ValidationError):
        Recipe(
            name="bad",
            start_url="https://example.test",
            requests=(),
        )
