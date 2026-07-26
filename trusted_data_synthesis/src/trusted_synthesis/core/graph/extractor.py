from __future__ import annotations

from trusted_synthesis.core.graph.schema import EvidenceEdge, NodeKind, ProofGraph
from trusted_synthesis.hashing import canonical_hash


class ProofSubgraphExtractor:
    """Extract the minimal one-hop proof neighborhood for selected evidence."""

    def extract(self, graph: ProofGraph, evidence_ids: tuple[str, ...]) -> ProofGraph:
        requested = set(evidence_ids)
        known_evidence = {node.node_id for node in graph.nodes if node.kind == NodeKind.EVIDENCE}
        missing = requested - known_evidence
        if missing:
            raise ValueError(f"proof graph does not contain evidence: {sorted(missing)}")
        selected_edges: list[EvidenceEdge] = []
        selected_nodes = set(requested)
        for edge in graph.edges:
            if edge.source_id in requested or edge.target_id in requested:
                selected_edges.append(edge)
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
