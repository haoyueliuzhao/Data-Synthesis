from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import (
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    NodeKind,
)
from trusted_synthesis.hashing import canonical_hash


class EvidenceGraphBuilder:
    def build(self, bundle: EvidenceBundle) -> EvidenceGraph:
        nodes: dict[str, EvidenceNode] = {}
        edges: dict[str, EvidenceEdge] = {}
        for evidence in bundle.evidence:
            identifiers = {
                "entity": f"entity:{evidence.domain}:{evidence.entity.entity_id}",
                "property": f"property:{evidence.domain}:{evidence.property.property_id}",
                "evidence": evidence.evidence_id,
                "source": f"source:{evidence.domain}:{evidence.source.source_id}",
                "time": (
                    f"time:{evidence.domain}:"
                    f"{canonical_hash(evidence.time.model_dump(mode='json', exclude_none=True))}"
                ),
            }
            nodes[identifiers["entity"]] = EvidenceNode(
                node_id=identifiers["entity"],
                kind=NodeKind.ENTITY,
                properties=evidence.entity.model_dump(mode="json", exclude_none=True),
            )
            nodes[identifiers["property"]] = EvidenceNode(
                node_id=identifiers["property"],
                kind=NodeKind.PROPERTY,
                properties=evidence.property.model_dump(mode="json", exclude_none=True),
            )
            nodes[identifiers["evidence"]] = EvidenceNode(
                node_id=identifiers["evidence"],
                kind=NodeKind.EVIDENCE,
                properties={
                    "value": str(evidence.value),
                    "unit": evidence.unit,
                    "currency": evidence.currency,
                    "status": evidence.status.value,
                },
            )
            nodes[identifiers["source"]] = EvidenceNode(
                node_id=identifiers["source"],
                kind=NodeKind.SOURCE,
                properties=evidence.source.model_dump(mode="json", exclude_none=True),
            )
            nodes[identifiers["time"]] = EvidenceNode(
                node_id=identifiers["time"],
                kind=NodeKind.TIME,
                properties=evidence.time.model_dump(mode="json", exclude_none=True),
            )
            for source_role, relation, target_role in (
                ("entity", "HAS_EVIDENCE", "evidence"),
                ("evidence", "MEASURES", "property"),
                ("evidence", "FROM_SOURCE", "source"),
                ("evidence", "IN_TIME", "time"),
            ):
                edge = _edge(
                    identifiers[source_role],
                    relation,
                    identifiers[target_role],
                )
                edges[edge.edge_id] = edge
        return EvidenceGraph(
            graph_id=canonical_hash(
                {"bundle_hash": bundle.bundle_hash, "schema": "evidence_graph.v1"},
                prefix="graph:",
            ),
            nodes=tuple(sorted(nodes.values(), key=lambda item: item.node_id)),
            edges=tuple(sorted(edges.values(), key=lambda item: item.edge_id)),
            source_build_id=bundle.graph_build_id,
        )


def _edge(source_id: str, relation: str, target_id: str) -> EvidenceEdge:
    identity = {"source": source_id, "relation": relation, "target": target_id}
    return EvidenceEdge(
        edge_id=canonical_hash(identity, prefix="edge:"),
        source_id=source_id,
        relation=relation,
        target_id=target_id,
    )
