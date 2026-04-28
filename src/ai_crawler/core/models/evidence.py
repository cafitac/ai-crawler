"""Evidence bundle model for AI/control-plane inputs."""

from pydantic import Field

from ai_crawler.core.models.base import DomainModel
from ai_crawler.core.models.trace import NetworkEvent


class EvidenceBundle(DomainModel):
    """Redacted evidence collected while inspecting a target."""

    target_url: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    events: tuple[NetworkEvent, ...] = ()
    observations: tuple[str, ...] = ()
    redactions: tuple[str, ...] = ()
