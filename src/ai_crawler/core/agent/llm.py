"""LLM client boundary for AI control-plane decisions."""

from typing import Protocol

from ai_crawler.core.models import AgentAction, EvidenceBundle, ToolResult


class LLMClient(Protocol):
    """Minimal interface for selecting the next structured agent action."""

    def next_action(
        self,
        evidence: EvidenceBundle,
        history: tuple[ToolResult, ...],
    ) -> AgentAction:
        """Choose the next action from current evidence and tool history."""
