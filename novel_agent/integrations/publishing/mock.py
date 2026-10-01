from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(slots=True)
class MockPublisher:
    name: str = "mock"

    def publish(self, project_id: str, chapter_id: str, title: str, content: str) -> dict[str, str]:
        fingerprint = hashlib.sha256(f"{project_id}:{chapter_id}".encode()).hexdigest()[:16]
        return {"status": "MOCK_PUBLISHED", "external_id": f"mock_{fingerprint}"}
