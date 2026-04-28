from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import urlopen

from ai_crawler.testing.fixture_site import FixtureSite


def read_text(url: str) -> str:
    try:
        with urlopen(url, timeout=5) as response:
            return response.read().decode("utf-8")
    except HTTPError as error:
        return error.read().decode("utf-8")


def read_json(url: str) -> dict[str, object]:
    return json.loads(read_text(url))


def test_fixture_site_serves_products_page_with_api_reference() -> None:
    with FixtureSite() as site:
        body = read_text(f"{site.base_url}/products")

    assert "Fixture Products" in body
    assert "/api/products?page=1" in body


def test_fixture_site_serves_paginated_product_api() -> None:
    with FixtureSite() as site:
        page_1 = read_json(f"{site.base_url}/api/products?page=1")
        page_2 = read_json(f"{site.base_url}/api/products?page=2")
        page_3 = read_json(f"{site.base_url}/api/products?page=3")

    assert page_1["items"] == [
        {"id": "p1", "name": "Keyboard", "price": 120},
        {"id": "p2", "name": "Mouse", "price": 40},
    ]
    assert page_2["items"] == [{"id": "p3", "name": "Monitor", "price": 300}]
    assert page_3["items"] == []


def test_fixture_site_serves_cloudflare_like_challenge_boundary() -> None:
    with FixtureSite() as site:
        body = read_text(f"{site.base_url}/challenge/cloudflare-like")

    assert "Checking if the site connection is secure" in body
    assert "challenge-form" in body
