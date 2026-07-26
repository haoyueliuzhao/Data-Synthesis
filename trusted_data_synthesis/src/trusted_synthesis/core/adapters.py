from __future__ import annotations

from collections.abc import Iterator
from enum import Enum
from typing import Any, Protocol

from trusted_synthesis.core.evidence.schema import EvidenceItem


class AdapterCapability(str, Enum):
    """Framework capabilities exposed by an evidence adapter."""

    EVIDENCE_STREAM = "evidence_stream"
    SOURCE_TRACE = "source_trace"
    DOMAIN_GRAPH = "domain_graph"
    ENTITY_CATALOG = "entity_catalog"
    SEMANTIC_DEFINITIONS = "semantic_definitions"


class EvidenceAdapter(Protocol):
    """Core-facing adapter contract with no dependency on a domain package."""

    adapter_id: str
    domain: str

    def capability_manifest(self) -> tuple[AdapterCapability, ...]: ...

    def inspect(self) -> dict[str, Any]: ...

    def iter_evidence(self, *, limit: int | None = None) -> Iterator[EvidenceItem]: ...


# Backward-compatible protocol name used by existing domain plugins.
DomainAdapter = EvidenceAdapter
