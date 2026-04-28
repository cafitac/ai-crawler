"""Browser probe adapter boundary tests."""

from ai_crawler.adapters.browser import BrowserNetworkProbe, BrowserProbeConfig
from ai_crawler.core.models import NetworkEvent


class FakeBrowserDriver:
    def __init__(self, events: tuple[NetworkEvent, ...]) -> None:
        self.events = events
        self.captured_url = ""
        self.captured_wait_ms = 0

    def capture_network_events(self, url: str, wait_after_load_ms: int) -> tuple[NetworkEvent, ...]:
        self.captured_url = url
        self.captured_wait_ms = wait_after_load_ms
        return self.events


def _event(
    url: str,
    resource_type: str = "fetch",
    status_code: int = 200,
    method: str = "GET",
) -> NetworkEvent:
    return NetworkEvent(
        method=method,
        url=url,
        status_code=status_code,
        resource_type=resource_type,
    )


def test_browser_probe_returns_evidence_bundle_from_injected_driver() -> None:
    event = _event("https://example.test/api/products?page=1", resource_type="xhr")
    driver = FakeBrowserDriver(events=(event,))
    config = BrowserProbeConfig(wait_after_load_ms=123)
    probe = BrowserNetworkProbe(driver=driver, config=config)

    evidence = probe.probe("https://example.test/products", goal="collect products")

    assert evidence.target_url == "https://example.test/products"
    assert evidence.goal == "collect products"
    assert evidence.events == (event,)
    assert evidence.observations == (
        "captured 1 raw browser network event(s)",
        "kept 1 replay candidate event(s)",
        "dropped 0 noise/static/error event(s)",
        "top candidate: GET https://example.test/api/products?page=1 status=200 type=xhr",
    )
    assert driver.captured_url == "https://example.test/products"
    assert driver.captured_wait_ms == 123


def test_browser_probe_filters_static_assets_and_non_replay_resource_types_by_default() -> None:
    events = (
        _event("https://example.test/products", resource_type="document"),
        _event("https://example.test/assets/app.js", resource_type="script"),
        _event("https://example.test/assets/style.css", resource_type="stylesheet"),
        _event("https://example.test/assets/logo.png", resource_type="image"),
        _event("https://example.test/assets/font.woff2", resource_type="font"),
        _event("https://example.test/api/products?page=1", resource_type="xhr"),
        _event("https://example.test/api/search?q=keyboard", resource_type="fetch"),
    )
    probe = BrowserNetworkProbe(driver=FakeBrowserDriver(events=events))

    evidence = probe.probe("https://example.test/products", goal="collect products")

    assert tuple(event.url for event in evidence.events) == (
        "https://example.test/api/products?page=1",
        "https://example.test/api/search?q=keyboard",
    )
    assert evidence.observations == (
        "captured 7 raw browser network event(s)",
        "kept 2 replay candidate event(s)",
        "dropped 5 noise/static/error event(s)",
        "top candidate: GET https://example.test/api/products?page=1 status=200 type=xhr",
    )


def test_browser_probe_filters_error_statuses_and_reports_no_useful_candidates() -> None:
    events = (
        _event("https://example.test/api/products", status_code=404, resource_type="fetch"),
        _event("https://example.test/api/search", status_code=500, resource_type="xhr"),
        _event("https://example.test/logo.png", status_code=200, resource_type="image"),
    )
    probe = BrowserNetworkProbe(driver=FakeBrowserDriver(events=events))

    evidence = probe.probe("https://example.test/products", goal="collect products")

    assert evidence.events == ()
    assert evidence.observations == (
        "captured 3 raw browser network event(s)",
        "kept 0 replay candidate event(s)",
        "dropped 3 noise/static/error event(s)",
        "no useful replay candidates captured; retry probe or inspect "
        "authorization/challenge state",
    )


def test_browser_probe_filters_resource_types_and_limits_events_after_filtering() -> None:
    events = (
        _event("https://example.test/app.js", resource_type="script"),
        _event("https://example.test/api/products?page=1", resource_type="xhr"),
        _event("https://example.test/api/products?page=2", resource_type="fetch"),
        _event("https://example.test/api/products?page=3", resource_type="fetch"),
    )
    config = BrowserProbeConfig(
        include_resource_types=("xhr", "fetch"),
        max_events=2,
    )
    probe = BrowserNetworkProbe(driver=FakeBrowserDriver(events=events), config=config)

    evidence = probe.probe("https://example.test/products", goal="collect products")

    assert tuple(event.url for event in evidence.events) == (
        "https://example.test/api/products?page=1",
        "https://example.test/api/products?page=2",
    )
    assert evidence.observations == (
        "captured 4 raw browser network event(s)",
        "kept 2 replay candidate event(s)",
        "dropped 1 noise/static/error event(s)",
        "limited replay candidates to max_events=2",
        "top candidate: GET https://example.test/api/products?page=1 status=200 type=xhr",
    )


def test_browser_probe_allows_custom_resource_types_for_document_debugging() -> None:
    document = _event("https://example.test/products", resource_type="document")
    config = BrowserProbeConfig(include_resource_types=("document",))
    probe = BrowserNetworkProbe(driver=FakeBrowserDriver(events=(document,)), config=config)

    evidence = probe.probe("https://example.test/products", goal="debug document")

    assert evidence.events == (document,)
    assert evidence.observations[-1] == (
        "top candidate: GET https://example.test/products status=200 type=document"
    )
