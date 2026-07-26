from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash


class NodeKind(str, Enum):
    SUBJECT = "subject"
    PREDICATE = "predicate"
    EVIDENCE = "evidence"
    SOURCE = "source"
    LOCATOR = "locator"
    TIME = "time"
    DEFINITION = "definition"
    SCOPE = "scope"


class EvidenceNode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str = Field(min_length=1)
    kind: NodeKind
    properties: dict[str, Any] = Field(default_factory=dict)


class EvidenceEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    properties: dict[str, Any] = Field(default_factory=dict)


class ProofGraph(BaseModel):
    """Task-local proof graph; distinct from an adapter-owned domain KG."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    graph_id: str = Field(min_length=1)
    nodes: tuple[EvidenceNode, ...]
    edges: tuple[EvidenceEdge, ...]
    source_build_id: str | None = None
    schema_version: str = "proof_graph.v3"

    @model_validator(mode="after")
    def validate_graph(self) -> ProofGraph:
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("graph contains duplicate node IDs")
        known = set(node_ids)
        dangling = [
            edge.edge_id
            for edge in self.edges
            if edge.source_id not in known or edge.target_id not in known
        ]
        if dangling:
            raise ValueError(f"graph contains dangling edges: {dangling[:3]}")
        return self

    @property
    def graph_hash(self) -> str:
        return canonical_hash(self, prefix="proof_graph:")

    def neighbors(self, node_id: str) -> tuple[EvidenceEdge, ...]:
        return tuple(
            edge for edge in self.edges if edge.source_id == node_id or edge.target_id == node_id
        )

    def contains_evidence(self, evidence_id: str) -> bool:
        return any(
            node.node_id == evidence_id and node.kind == NodeKind.EVIDENCE for node in self.nodes
        )
