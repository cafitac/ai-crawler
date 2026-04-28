"""Browser probe adapter boundary."""

from typing import Protocol

from pydantic import Field

from ai_crawler.core.models import EvidenceBundle, NetworkEvent
from ai_crawler.core.models.base import DomainModel


class BrowserProbeConfig(DomainModel):
    """Configuration for a short browser probe pass."""

    wait_after_load_ms: int = Field(default=1_000, ge=0)
    include_resource_types: tuple[str, ...] = ()
    max_events: int = Field(default=200, ge=1)


class BrowserProbeDriver(Protocol):
    """Low-level driver that captures browser network traffic."""

    def capture_network_events(
        self,
        url: str,
        wait_after_load_ms: int,
    ) -> tuple[NetworkEvent, ...]:
        """Open a URL and return normalized network events."""


class BrowserProbe(Protocol):
    """High-level browser probe interface used by orchestration code."""

    def probe(self, url: str, goal: str) -> EvidenceBundle:
        """Collect redacted evidence for a short browser probe."""


DEFAULT_BROWSER_PROBE_CONFIG = BrowserProbeConfig()


class BrowserNetworkProbe:
    """Browser probe implementation backed by an injected driver."""

    def __init__(
        self,
        driver: BrowserProbeDriver,
        config: BrowserProbeConfig = DEFAULT_BROWSER_PROBE_CONFIG,
    ) -> None:
        self._driver = driver
        self._config = config

    def probe(self, url: str, goal: str) -> EvidenceBundle:
        """Capture network events and return an evidence bundle."""
        raw_events = self._driver.capture_network_events(
            url=url,
            wait_after_load_ms=self._config.wait_after_load_ms,
        )
        events = _filter_events(raw_events, self._config)
        return EvidenceBundle(
            target_url=url,
            goal=goal,
            events=events,
            observations=(f"captured {len(events)} browser network event(s)",),
        )


def _filter_events(
    events: tuple[NetworkEvent, ...],
    config: BrowserProbeConfig,
) -> tuple[NetworkEvent, ...]:
    included = config.include_resource_types
    filtered = (
        event
        for event in events
        if not included or event.resource_type in included
    )
    return tuple(filtered)[: config.max_events]
