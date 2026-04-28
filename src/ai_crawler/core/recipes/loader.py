"""YAML recipe loader."""

from pathlib import Path
from typing import Any

from ai_crawler.core.models import Recipe


class RecipeLoader:
    """Load recipe documents into explicit domain models."""

    def load_file(self, path: Path | str) -> Recipe:
        """Load a recipe from a UTF-8 YAML file."""
        recipe_path = Path(path)
        return self.load_text(recipe_path.read_text(encoding="utf-8"))

    def load_text(self, text: str) -> Recipe:
        """Load a recipe from YAML text."""
        payload = _load_yaml(text)
        return Recipe.model_validate(payload)


def _load_yaml(text: str) -> dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError as error:
        msg = "Install YAML support with `pip install pyyaml` or `uv sync`."
        raise RuntimeError(msg) from error

    payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        msg = "Recipe YAML must contain a mapping at the document root."
        raise ValueError(msg)
    return payload
