"""Classify deterministic test-report failures for AI harnesses."""
from typing import Any

_CHALLENGE_MARKERS = (
    "just a moment",
    "checking your browser",
    "captcha",
    "cf-chl",
    "cloudflare",
    "access denied",
    "bot detection",
)


def classify_test_report(test_report: dict[str, Any]) -> dict[str, object]:
    """Return a stable machine-readable failure classification."""
    status = _status_code(test_report)
    failure_reason = _string_value(test_report.get("failure_reason"))
    body_sample = _string_value(test_report.get("body_sample")).lower()

    if _looks_like_challenge(status=status, body_sample=body_sample):
        return {
            "category": "challenge_detected",
            "retryable": False,
            "requires_human": True,
            "summary": (
                "challenge boundary detected; "
                "manual handoff or authorized session is required"
            ),
        }
    if failure_reason == "retry_exhausted":
        return {
            "category": "retry_exhausted",
            "retryable": True,
            "requires_human": False,
            "summary": "retry budget exhausted after transient request failures",
        }
    if failure_reason == "no_items_extracted":
        return {
            "category": "extraction_failed",
            "retryable": False,
            "requires_human": False,
            "summary": "response succeeded but recipe extracted no items",
        }
    if failure_reason == "non_success_status":
        return {
            "category": "http_error",
            "retryable": 500 <= status < 600,
            "requires_human": False,
            "summary": f"test request returned HTTP {status}",
        }
    if failure_reason == "no_response":
        return {
            "category": "no_response",
            "retryable": True,
            "requires_human": False,
            "summary": "no response was captured from the test request",
        }
    return {
        "category": "success",
        "retryable": False,
        "requires_human": False,
        "summary": "test request completed successfully",
    }


def _looks_like_challenge(status: int, body_sample: str) -> bool:
    if status in {401, 403, 429} and any(marker in body_sample for marker in _CHALLENGE_MARKERS):
        return True
    return any(marker in body_sample for marker in ("captcha", "cf-chl"))


def _status_code(test_report: dict[str, Any]) -> int:
    value = test_report.get("first_response_status", 0)
    if isinstance(value, int):
        return value
    return 0


def _string_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""
