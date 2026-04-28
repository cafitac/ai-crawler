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


def test_browser_probe_returns_evidence_bundle_from_injected_driver() -> None:
    event = NetworkEvent(
        method="get",
        url="https://example.test/api/products?page=1",
        status_code=200,
        resource_type="xhr",
    )
    driver = FakeBrowserDriver(events=(event,))
    config = BrowserProbeConfig(wait_after_load_ms=123)
    probe = BrowserNetworkProbe(driver=driver, config=config)

    evidence = probe.probe("https://example.test/products", goal="collect products")

    assert evidence.target_url == "https://example.test/products"
    assert evidence.goal == "collect products"
    assert evidence.events == (event,)
    assert evidence.observations == ("captured 1 browser network event(s)",)
    assert driver.captured_url == "https://example.test/products"
    assert driver.captured_wait_ms == 123


def test_browser_probe_filters_resource_types_and_limits_events() -> None:
    events = (
        NetworkEvent(
            method="GET",
            url="https://example.test/app.js",
            status_code=200,
            resource_type="script",
        ),
        NetworkEvent(
            method="GET",
            url="https://example.test/api/products?page=1",
            status_code=200,
            resource_type="xhr",
        ),
        NetworkEvent(
            method="GET",
            url="https://example.test/api/products?page=2",
            status_code=200,
            resource_type="fetch",
        ),
    )
    driver = FakeBrowserDriver(events=events)
    config = BrowserProbeConfig(
        include_resource_types=("xhr", "fetch"),
        max_events=1,
    )
    probe = BrowserNetworkProbe(driver=driver, config=config)

    evidence = probe.probe("https://example.test/products", goal="collect products")

    assert tuple(event.url for event in evidence.events) == (
        "https://example.test/api/products?page=1",
    )
    assert evidence.observations == ("captured 1 browser network event(s)",)
