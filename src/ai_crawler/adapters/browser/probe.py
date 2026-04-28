"""Browser probe adapter boundary."""

from typing import Protocol
from urllib.parse import urlparse

from pydantic import Field

from ai_crawler.core.models import EvidenceBundle, NetworkEvent
from ai_crawler.core.models.base import DomainModel

DEFAULT_REPLAY_RESOURCE_TYPES = ("fetch", "xhr")
_STATIC_PATH_SUFFIXES = (
    ".css",
    ".js",
    ".mjs",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".mp4",
    ".webm",
    ".mp3",
    ".wav",
    ".pdf",
)


class BrowserProbeConfig(DomainModel):
    """Configuration for a short browser probe pass."""

    wait_after_load_ms: int = Field(default=1_000, ge=0)
    include_resource_types: tuple[str, ...] = DEFAULT_REPLAY_RESOURCE_TYPES
    max_events: int = Field(default=200, ge=1)
    min_status_code: int = Field(default=200, ge=100, le=599)
    max_status_code: int = Field(default=399, ge=100, le=599)


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


class BrowserNetworkProbe:
    """Browser probe implementation backed by an injected driver."""

    def __init__(
        self,
        driver: BrowserProbeDriver,
        config: BrowserProbeConfig | None = None,
    ) -> None:
        self._driver = driver
        self._config = config or BrowserProbeConfig()

    def probe(self, url: str, goal: str) -> EvidenceBundle:
        """Capture network events and return an evidence bundle."""
        raw_events = self._driver.capture_network_events(
            url=url,
            wait_after_load_ms=self._config.wait_after_load_ms,
        )
        filtered_events = _filter_events(raw_events, self._config)
        events = filtered_events[: self._config.max_events]
        return EvidenceBundle(
            target_url=url,
            goal=goal,
            events=events,
            observations=_build_observations(
                raw_events=raw_events,
                filtered_events=filtered_events,
                returned_events=events,
                config=self._config,
            ),
        )


def _filter_events(
    events: tuple[NetworkEvent, ...],
    config: BrowserProbeConfig,
) -> tuple[NetworkEvent, ...]:
    return tuple(event for event in events if _is_replay_candidate(event, config))


def _is_replay_candidate(event: NetworkEvent, config: BrowserProbeConfig) -> bool:
    if event.resource_type not in config.include_resource_types:
        return False
    if not config.min_status_code <= event.status_code <= config.max_status_code:
        return False
    return not _has_static_path_suffix(event.url)


def _has_static_path_suffix(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(_STATIC_PATH_SUFFIXES)


def _build_observations(
    raw_events: tuple[NetworkEvent, ...],
    filtered_events: tuple[NetworkEvent, ...],
    returned_events: tuple[NetworkEvent, ...],
    config: BrowserProbeConfig,
) -> tuple[str, ...]:
    observations = [
        f"captured {len(raw_events)} raw browser network event(s)",
        f"kept {len(returned_events)} replay candidate event(s)",
        f"dropped {len(raw_events) - len(filtered_events)} noise/static/error event(s)",
    ]
    if len(filtered_events) > len(returned_events):
        observations.append(f"limited replay candidates to max_events={config.max_events}")
    if returned_events:
        observations.append(_top_candidate_observation(returned_events[0]))
    else:
        observations.append(
            "no useful replay candidates captured; retry probe or inspect "
            "authorization/challenge state"
        )
    return tuple(observations)


def _top_candidate_observation(event: NetworkEvent) -> str:
    return (
        f"top candidate: {event.method} {event.url} "
        f"status={event.status_code} type={event.resource_type}"
    )
