from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

from trusted_synthesis.core.evidence.schema import EvidenceItem


class DomainAdapter(Protocol):
    adapter_id: str
    domain: str

    def inspect(self) -> dict[str, Any]: ...

    def iter_evidence(self, *, limit: int | None = None) -> Iterator[EvidenceItem]: ...
