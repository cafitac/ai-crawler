"""Pure scoring functions for endpoint inference."""

from __future__ import annotations

from ai_crawler.core.models import EndpointCandidate, NetworkEvent

_API_MARKERS = ("/api/", "/graphql", ".json", "ajax")
_DATA_RESOURCE_TYPES = {"xhr", "fetch"}
_LOW_VALUE_RESOURCE_TYPES = {"image", "font", "stylesheet", "script"}


def rank_endpoint_candidates(events: tuple[NetworkEvent, ...]) -> tuple[EndpointCandidate, ...]:
    """Rank network events by likelihood of being useful data endpoints."""

    best_by_url: dict[str, EndpointCandidate] = {}
    for event in events:
        candidate = score_endpoint_event(event)
        existing = best_by_url.get(candidate.url)
        if existing is None or candidate.score > existing.score:
            best_by_url[candidate.url] = candidate

    return tuple(
        sorted(
            best_by_url.values(),
            key=lambda candidate: (-candidate.score, candidate.url),
        )
    )


def score_endpoint_event(event: NetworkEvent) -> EndpointCandidate:
    """Score a single network event as a possible data endpoint."""

    score = 0
    reasons: list[str] = []
    resource_type = event.resource_type.lower()
    url_lower = event.url.lower()

    if 200 <= event.status_code <= 299:
        score += 25
        reasons.append("successful_status")
    if resource_type in _DATA_RESOURCE_TYPES:
        score += 50
        reasons.append("xhr_or_fetch")
    if any(marker in url_lower for marker in _API_MARKERS):
        score += 30
        reasons.append("api_url")
    if resource_type in _LOW_VALUE_RESOURCE_TYPES:
        score = max(0, score - 20)
        reasons.append("low_value_resource_type")
    if event.status_code >= 400:
        score = max(0, score - 25)
        reasons.append("error_status")

    return EndpointCandidate(
        url=event.url,
        method=event.method,
        status_code=event.status_code,
        resource_type=event.resource_type,
        score=score,
        reasons=tuple(reasons),
    )
