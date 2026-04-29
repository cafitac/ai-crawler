"""Failure classification tests."""

from ai_crawler.core.diagnostics import classify_test_report


def test_classify_test_report_identifies_challenge_boundary() -> None:
    classification = classify_test_report(
        {
            "first_response_status": 403,
            "content_type": "text/html",
            "body_sample": "<html><title>Just a moment...</title>Checking your browser</html>",
            "stop_reason": "non_success_status",
            "pages_attempted": 1,
            "requests_attempted": 1,
            "failure_reason": "non_success_status",
        }
    )

    assert classification == {
        "category": "challenge_detected",
        "retryable": False,
        "requires_human": True,
        "summary": "challenge boundary detected; manual handoff or authorized session is required",
    }


def test_classify_test_report_identifies_retry_exhaustion() -> None:
    classification = classify_test_report(
        {
            "first_response_status": 500,
            "content_type": "application/json",
            "body_sample": '{"error":"temporary"}',
            "stop_reason": "retry_exhausted",
            "pages_attempted": 1,
            "requests_attempted": 3,
            "failure_reason": "retry_exhausted",
        }
    )

    assert classification == {
        "category": "retry_exhausted",
        "retryable": True,
        "requires_human": False,
        "summary": "retry budget exhausted after transient request failures",
    }


def test_classify_test_report_identifies_no_items_extracted() -> None:
    classification = classify_test_report(
        {
            "first_response_status": 200,
            "content_type": "application/json",
            "body_sample": '{"items":[{"name":"Keyboard"}]}',
            "failure_reason": "no_items_extracted",
        }
    )

    assert classification == {
        "category": "extraction_failed",
        "retryable": False,
        "requires_human": False,
        "summary": "response succeeded but recipe extracted no items",
    }


def test_classify_test_report_identifies_success() -> None:
    classification = classify_test_report(
        {
            "first_response_status": 200,
            "content_type": "application/json",
            "body_sample": "{}",
            "failure_reason": "",
        }
    )

    assert classification == {
        "category": "success",
        "retryable": False,
        "requires_human": False,
        "summary": "test request completed successfully",
    }
