from __future__ import annotations

from trusted_synthesis.core.graph.schema import NodeKind, ProofGraph
from trusted_synthesis.hashing import canonical_hash


class ProofSubgraphExtractor:
    """Extract recursive evidence closure plus each evidence's semantic neighborhood."""

    _recursive_relations = {
        "DERIVED_FROM",
        "SUPPORTED_BY",
        "QUALIFIED_BY",
        "CONTRADICTED_BY",
    }

    def extract(self, graph: ProofGraph, evidence_ids: tuple[str, ...]) -> ProofGraph:
        requested = set(evidence_ids)
        known_evidence = {node.node_id for node in graph.nodes if node.kind == NodeKind.EVIDENCE}
        missing = requested - known_evidence
        if missing:
            raise ValueError(f"proof graph does not contain evidence: {sorted(missing)}")
        evidence_closure = set(requested)
        changed = True
        while changed:
            changed = False
            for edge in graph.edges:
                if edge.relation not in self._recursive_relations:
                    continue
                if edge.source_id in evidence_closure and edge.target_id in known_evidence:
                    if edge.target_id not in evidence_closure:
                        evidence_closure.add(edge.target_id)
                        changed = True
                if edge.target_id in evidence_closure and edge.source_id in known_evidence:
                    if edge.source_id not in evidence_closure:
                        evidence_closure.add(edge.source_id)
                        changed = True
        selected_edges = [
            edge
            for edge in graph.edges
            if edge.source_id in evidence_closure or edge.target_id in evidence_closure
        ]
        selected_nodes = set(evidence_closure)
        for edge in selected_edges:
            selected_nodes.update((edge.source_id, edge.target_id))
        nodes = tuple(node for node in graph.nodes if node.node_id in selected_nodes)
        identity = {
            "parent_graph_hash": graph.graph_hash,
            "evidence_ids": sorted(requested),
            "schema": graph.schema_version,
        }
        return ProofGraph(
            graph_id=canonical_hash(identity, prefix="proof_subgraph:"),
            nodes=nodes,
            edges=tuple(selected_edges),
            source_build_id=graph.source_build_id,
            schema_version=graph.schema_version,
        )
