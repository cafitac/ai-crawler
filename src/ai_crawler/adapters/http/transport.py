"""Transport protocol used by HTTP fetchers."""

from __future__ import annotations

from typing import Any, Protocol


class HttpTransport(Protocol):
    """Minimal request transport protocol compatible with curl-cffi sessions."""

    def request(self, **kwargs: Any) -> Any:
        """Execute a request and return a response-like object."""
