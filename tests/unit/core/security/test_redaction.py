"""Sensitive value redaction tests."""

from ai_crawler.core.security import redact_text


def test_redact_text_removes_common_secret_values() -> None:
    payload = (
        "Authorization: Bearer abc.def.ghi\n"
        "cookie: sessionid=s-123; theme=light\n"
        "api_key=sk-test-secret\n"
        "token=plain-token-value"
    )

    redacted = redact_text(payload)

    assert "abc.def.ghi" not in redacted
    assert "s-123" not in redacted
    assert "sk-test-secret" not in redacted
    assert "plain-token-value" not in redacted
    assert "Authorization: Bearer [REDACTED]" in redacted
    assert "sessionid=[REDACTED]" in redacted
    assert "api_key=[REDACTED]" in redacted
    assert "token=[REDACTED]" in redacted


def test_redact_text_removes_json_secret_values() -> None:
    payload = '{"access_token": "secret-token", "session_id": "session-123"}'

    redacted = redact_text(payload)

    assert "secret-token" not in redacted
    assert "session-123" not in redacted
    assert '"access_token": "[REDACTED]"' in redacted
    assert '"session_id": "[REDACTED]"' in redacted


def test_redact_text_leaves_non_sensitive_content_readable() -> None:
    payload = '{"items": [{"name": "Keyboard", "price": 120}]}'

    assert redact_text(payload) == payload
