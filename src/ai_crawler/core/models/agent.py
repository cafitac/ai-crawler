"""Agent action and tool result models."""

from typing import Any

from pydantic import Field

from ai_crawler.core.models.base import DomainModel


class AgentAction(DomainModel):
    """Structured action selected by an AI control-plane step."""

    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(DomainModel):
    """Result returned after executing an agent action."""

    action_name: str = Field(min_length=1)
    ok: bool
    summary: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()
    artifacts: dict[str, Any] = Field(default_factory=dict)


class AgentRunResult(DomainModel):
    """Summary of one AI-controlled action loop run."""

    ok: bool
    stop_reason: str = Field(min_length=1)
    steps_taken: int = Field(ge=0)
    history: tuple[ToolResult, ...] = ()
