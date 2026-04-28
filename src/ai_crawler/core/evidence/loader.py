"""Evidence loading helpers."""

import json
from pathlib import Path
from typing import Any

from ai_crawler.core.models import EvidenceBundle


class EvidenceLoader:
    """Load redacted evidence documents into domain models."""

    def load_file(self, path: Path | str) -> EvidenceBundle:
        """Load an EvidenceBundle from a UTF-8 JSON file."""
        evidence_path = Path(path)
        return self.load_text(evidence_path.read_text(encoding="utf-8"))

    def load_text(self, text: str) -> EvidenceBundle:
        """Load an EvidenceBundle from JSON text."""
        payload = _load_json(text)
        return EvidenceBundle.model_validate(payload)


def _load_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        msg = "Evidence JSON must contain an object at the document root."
        raise ValueError(msg)
    return payload
