"""Sensitive value redaction utilities."""

import re

REDACTION = "[REDACTED]"

_BEARER_PATTERN = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([^\s;,]+)")
_ASSIGNMENT_PATTERNS = tuple(
    re.compile(rf"(?i)({name}\s*[=:]\s*)([^\s;,&]+)")
    for name in (
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "token",
        "sessionid",
        "session_id",
        "auth_token",
    )
)
_JSON_ASSIGNMENT_PATTERNS = tuple(
    re.compile(rf'(?i)("{name}"\s*:\s*")([^"]+)(")')
    for name in (
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "token",
        "sessionid",
        "session_id",
        "auth_token",
    )
)
_COOKIE_PATTERN = re.compile(r"(?i)(cookie\s*:\s*)([^\n\r]+)")


def redact_text(text: str) -> str:
    """Redact common credential-like values from text artifacts."""
    redacted = _BEARER_PATTERN.sub(rf"\1{REDACTION}", text)
    redacted = _COOKIE_PATTERN.sub(_redact_cookie_header, redacted)
    for pattern in _ASSIGNMENT_PATTERNS:
        redacted = pattern.sub(rf"\1{REDACTION}", redacted)
    for pattern in _JSON_ASSIGNMENT_PATTERNS:
        redacted = pattern.sub(rf"\1{REDACTION}\3", redacted)
    return redacted


def _redact_cookie_header(match: re.Match[str]) -> str:
    prefix = match.group(1)
    cookie_value = match.group(2)
    pairs = []
    for raw_pair in cookie_value.split(";"):
        pair = raw_pair.strip()
        if not pair:
            continue
        key, separator, value = pair.partition("=")
        if _is_sensitive_key(key):
            pairs.append(f"{key}{separator}{REDACTION}")
        else:
            pairs.append(f"{key}{separator}{value}" if separator else key)
    return prefix + "; ".join(pairs)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return normalized in {
        "sessionid",
        "session_id",
        "token",
        "access_token",
        "refresh_token",
        "auth_token",
        "jwt",
    }
