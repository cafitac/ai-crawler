"""Deterministic baseline recipe generation tools."""

from ai_crawler.core.inference import rank_endpoint_candidates
from ai_crawler.core.models import AgentAction, EvidenceBundle, Recipe, RequestSpec, ToolResult


class BaselineRecipeGenerator:
    """Generate a minimal recipe from captured network evidence."""

    def generate(self, evidence: EvidenceBundle, name: str) -> Recipe:
        """Create a recipe using the highest ranked endpoint candidate."""
        candidates = rank_endpoint_candidates(evidence.events)
        if not candidates:
            msg = "no endpoint candidates available for recipe generation"
            raise ValueError(msg)

        top_candidate = candidates[0]
        return Recipe(
            name=name,
            start_url=evidence.target_url,
            requests=(
                RequestSpec(
                    method=top_candidate.method,
                    url=top_candidate.url,
                ),
            ),
        )


class GenerateRecipeTool:
    """Agent tool that turns evidence into a baseline recipe artifact."""

    def __init__(self, generator: BaselineRecipeGenerator | None = None) -> None:
        self._generator = generator or BaselineRecipeGenerator()

    def __call__(self, action: AgentAction, evidence: EvidenceBundle) -> ToolResult:
        name = _recipe_name(action)
        try:
            recipe = self._generator.generate(evidence=evidence, name=name)
        except ValueError as error:
            return ToolResult(
                action_name=action.name,
                ok=False,
                summary=str(error),
            )

        return ToolResult(
            action_name=action.name,
            ok=True,
            summary=f"generated baseline recipe: {recipe.name}",
            artifacts={"recipe": recipe.model_dump(mode="json")},
        )


def _recipe_name(action: AgentAction) -> str:
    name = action.arguments.get("name", "")
    if isinstance(name, str) and name:
        return name
    return "generated-recipe"
