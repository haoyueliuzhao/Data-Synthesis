from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import EvidenceEdge, EvidenceNode, NodeKind, ProofGraph
from trusted_synthesis.hashing import canonical_hash


class ProofGraphBuilder:
    """Build a verifier-facing proof graph from normalized evidence."""

    def build(self, bundle: EvidenceBundle) -> ProofGraph:
        nodes: dict[str, EvidenceNode] = {}
        edges: dict[str, EvidenceEdge] = {}
        for evidence in bundle.evidence:
            ids = {
                "subject": f"subject:{evidence.domain}:{evidence.subject.subject_id}",
                "predicate": f"predicate:{evidence.domain}:{evidence.predicate}",
                "evidence": evidence.evidence_id,
                "source": f"source:{evidence.domain}:{evidence.source.source_id}",
                "locator": f"locator:{evidence.domain}:{evidence.source_locator.locator_hash}",
            }
            nodes[ids["subject"]] = EvidenceNode(
                node_id=ids["subject"],
                kind=NodeKind.SUBJECT,
                properties=evidence.subject.model_dump(mode="json", exclude_none=True),
            )
            nodes[ids["predicate"]] = EvidenceNode(
                node_id=ids["predicate"],
                kind=NodeKind.PREDICATE,
                properties={"predicate": evidence.predicate},
            )
            nodes[ids["evidence"]] = EvidenceNode(
                node_id=ids["evidence"],
                kind=NodeKind.EVIDENCE,
                properties={
                    "assertion_id": evidence.assertion_id,
                    "evidence_version_id": evidence.evidence_version_id,
                    "evidence_kind": evidence.evidence_kind.value,
                    "payload": evidence.payload.model_dump(mode="json", exclude_none=True),
                    "epistemic_status": evidence.epistemic_status.value,
                },
            )
            nodes[ids["source"]] = EvidenceNode(
                node_id=ids["source"],
                kind=NodeKind.SOURCE,
                properties=evidence.source.model_dump(mode="json", exclude_none=True),
            )
            nodes[ids["locator"]] = EvidenceNode(
                node_id=ids["locator"],
                kind=NodeKind.LOCATOR,
                properties=evidence.source_locator.model_dump(mode="json", exclude_none=True),
            )
            _add_edge(edges, ids["subject"], "HAS_EVIDENCE", ids["evidence"])
            _add_edge(edges, ids["evidence"], "ASSERTS", ids["predicate"])
            _add_edge(edges, ids["evidence"], "FROM_SOURCE", ids["source"])
            _add_edge(edges, ids["evidence"], "LOCATED_AT", ids["locator"])

            temporal = evidence.temporal_context.model_dump(mode="json", exclude_none=True)
            if temporal:
                time_id = f"time:{evidence.domain}:{canonical_hash(temporal)}"
                nodes[time_id] = EvidenceNode(
                    node_id=time_id, kind=NodeKind.TIME, properties=temporal
                )
                _add_edge(edges, ids["evidence"], "IN_TIME", time_id)
            if evidence.scope:
                scope_data = evidence.scope.model_dump(mode="json", exclude_none=True)
                scope_id = f"scope:{evidence.domain}:{canonical_hash(scope_data)}"
                nodes[scope_id] = EvidenceNode(
                    node_id=scope_id, kind=NodeKind.SCOPE, properties=scope_data
                )
                _add_edge(edges, ids["evidence"], "APPLIES_TO", scope_id)
            if evidence.definition.definition_id:
                definition_id = f"definition:{evidence.domain}:{evidence.definition.definition_id}"
                nodes[definition_id] = EvidenceNode(
                    node_id=definition_id,
                    kind=NodeKind.DEFINITION,
                    properties=evidence.definition.model_dump(mode="json", exclude_none=True),
                )
                _add_edge(edges, ids["evidence"], "HAS_DEFINITION", definition_id)

        known_evidence = {item.evidence_id for item in bundle.evidence}
        for evidence in bundle.evidence:
            for parent_id in evidence.provenance.parent_evidence_ids:
                if parent_id in known_evidence:
                    _add_edge(edges, evidence.evidence_id, "DERIVED_FROM", parent_id)

        return ProofGraph(
            graph_id=canonical_hash(
                {"bundle_hash": bundle.bundle_hash, "schema": "proof_graph.v3"},
                prefix="proof_graph:",
            ),
            nodes=tuple(sorted(nodes.values(), key=lambda item: item.node_id)),
            edges=tuple(sorted(edges.values(), key=lambda item: item.edge_id)),
            source_build_id=bundle.graph_build_id,
        )


def _add_edge(
    edges: dict[str, EvidenceEdge], source_id: str, relation: str, target_id: str
) -> None:
    identity = {"source": source_id, "relation": relation, "target": target_id}
    edge = EvidenceEdge(
        edge_id=canonical_hash(identity, prefix="edge:"),
        source_id=source_id,
        relation=relation,
        target_id=target_id,
    )
    edges[edge.edge_id] = edge
