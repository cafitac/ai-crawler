from ai_crawler.core.inference.endpoint_score import rank_endpoint_candidates
from ai_crawler.core.models import NetworkEvent


def test_rank_endpoint_candidates_prefers_successful_xhr_api_requests() -> None:
    events = (
        NetworkEvent(
            method="GET",
            url="https://example.com/static/app.js",
            status_code=200,
            resource_type="script",
        ),
        NetworkEvent(
            method="GET",
            url="https://example.com/api/products?page=1",
            status_code=200,
            resource_type="xhr",
        ),
        NetworkEvent(
            method="GET",
            url="https://example.com/logo.png",
            status_code=200,
            resource_type="image",
        ),
        NetworkEvent(
            method="GET",
            url="https://example.com/api/missing",
            status_code=404,
            resource_type="xhr",
        ),
    )

    candidates = rank_endpoint_candidates(events)

    assert candidates[0].url == "https://example.com/api/products?page=1"
    assert candidates[0].score > candidates[1].score
    assert "xhr_or_fetch" in candidates[0].reasons
    assert "api_url" in candidates[0].reasons


def test_rank_endpoint_candidates_deduplicates_urls_with_best_score() -> None:
    events = (
        NetworkEvent(
            method="GET",
            url="https://example.com/api/products?page=1",
            status_code=500,
            resource_type="xhr",
        ),
        NetworkEvent(
            method="GET",
            url="https://example.com/api/products?page=1",
            status_code=200,
            resource_type="xhr",
        ),
    )

    candidates = rank_endpoint_candidates(events)

    assert len(candidates) == 1
    assert candidates[0].status_code == 200
    assert "successful_status" in candidates[0].reasons
