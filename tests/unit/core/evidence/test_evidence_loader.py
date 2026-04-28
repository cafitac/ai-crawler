"""Evidence bundle loader tests."""

import json

from ai_crawler.core.evidence import EvidenceLoader
from ai_crawler.core.models import EvidenceBundle, NetworkEvent


def test_evidence_loader_loads_json_file(tmp_path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "target_url": "https://example.test/products",
                "goal": "collect products",
                "events": [
                    {
                        "method": "get",
                        "url": "https://example.test/api/products",
                        "status_code": 200,
                        "resource_type": "fetch",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    evidence = EvidenceLoader().load_file(evidence_path)

    assert evidence == EvidenceBundle(
        target_url="https://example.test/products",
        goal="collect products",
        events=(
            NetworkEvent(
                method="GET",
                url="https://example.test/api/products",
                status_code=200,
                resource_type="fetch",
            ),
        ),
    )
