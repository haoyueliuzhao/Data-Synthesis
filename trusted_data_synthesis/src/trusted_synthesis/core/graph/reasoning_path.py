from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.graph.schema import ProofGraph


class ReasoningPath(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    node_ids: tuple[str, ...] = Field(min_length=1)
    edge_ids: tuple[str, ...]
    operation_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_non_repeating_nodes(self) -> ReasoningPath:
        if len(self.node_ids) != len(set(self.node_ids)):
            raise ValueError("reasoning path must not repeat nodes")
        return self

    def validate_against(self, graph: ProofGraph) -> None:
        graph_nodes = {node.node_id for node in graph.nodes}
        graph_edges = {edge.edge_id for edge in graph.edges}
        if self.graph_id != graph.graph_id:
            raise ValueError("reasoning path is bound to another graph")
        if not set(self.node_ids).issubset(graph_nodes):
            raise ValueError("reasoning path references unknown graph nodes")
        if not set(self.edge_ids).issubset(graph_edges):
            raise ValueError("reasoning path references unknown graph edges")
