from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from finraw.qa.graph_walk.schema_registry import (
    WALK_GRAMMAR_VERSION,
    validate_relation_step,
)


QUERY_GRAPH_IR_VERSION = 1


@dataclass(frozen=True)
class QueryGraphIR:
    query_graph_version: int
    discovery_method: str
    operation_macro_id: str
    answer_target: dict[str, Any]
    anchors: tuple[dict[str, Any], ...]
    roles: dict[str, dict[str, Any]]
    walks: tuple[dict[str, Any], ...]
    joins: tuple[dict[str, Any], ...]
    role_constraints: tuple[dict[str, Any], ...]
    semantic_constraints: tuple[dict[str, Any], ...]
    binding_projection: dict[str, Any]
    operation_template: dict[str, Any]
    answer_schema: dict[str, Any]
    evidence_policy: dict[str, Any]
    sampling: dict[str, Any]
    walk_grammar_version: str = WALK_GRAMMAR_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def query_graph_hash(self) -> str:
        return query_graph_hash(self)

    def validate(self) -> None:
        if self.query_graph_version != QUERY_GRAPH_IR_VERSION:
            raise ValueError(
                f"Unsupported QueryGraphIR version: {self.query_graph_version}"
            )
        if self.discovery_method not in {"typed_walk", "static_typed_walk"}:
            raise ValueError(
                f"Unsupported QueryGraphIR discovery method: {self.discovery_method}"
            )
        if not self.anchors:
            raise ValueError("QueryGraphIR requires at least one anchor")
        anchor_roles = {str(item.get("role")) for item in self.anchors}
        if not anchor_roles <= set(self.roles):
            raise ValueError("QueryGraphIR anchor role is not declared")
        bound = set(anchor_roles)
        seen_walk_ids: set[str] = set()
        for walk in self.walks:
            walk_id = str(walk.get("walk_id") or "")
            if not walk_id or walk_id in seen_walk_ids:
                raise ValueError(f"Invalid or duplicate walk_id: {walk_id}")
            seen_walk_ids.add(walk_id)
            local_bound = set(bound)
            for step in walk.get("steps") or []:
                from_role = str(step.get("from_role") or "")
                to_role = str(step.get("to_role") or "")
                if from_role not in local_bound and from_role not in bound:
                    raise ValueError(f"Walk {walk_id} uses unbound role: {from_role}")
                if to_role not in self.roles:
                    raise ValueError(
                        f"Walk {walk_id} targets undeclared role: {to_role}"
                    )
                from_type = str(self.roles[from_role]["node_type"])
                to_type = str(self.roles[to_role]["node_type"])
                validate_relation_step(
                    from_type,
                    str(step.get("relation")),
                    str(step.get("direction") or "out"),
                    to_type,
                )
                if to_role == from_role:
                    raise ValueError(f"Walk {walk_id} contains a role cycle: {to_role}")
                local_bound.add(to_role)
                bound.add(to_role)
        required = {
            role for role, spec in self.roles.items() if spec.get("required", True)
        }
        if not required <= bound:
            raise ValueError(
                f"QueryGraphIR has unbound required roles: {sorted(required - bound)}"
            )
        for join in self.joins:
            roles = list(join.get("roles") or [])
            roles.extend(value for key, value in join.items() if key.endswith("_role"))
            missing = sorted(
                {str(role) for role in roles if role and str(role) not in self.roles}
            )
            if missing:
                raise ValueError(
                    f"QueryGraphIR join references unknown roles: {missing}"
                )
        if not self.operation_template.get("operators"):
            raise ValueError("QueryGraphIR requires an executable operation template")
        if not self.answer_schema.get("type"):
            raise ValueError("QueryGraphIR requires an answer schema")


def canonical_query_graph(value: QueryGraphIR | dict[str, Any]) -> dict[str, Any]:
    row = value.as_dict() if isinstance(value, QueryGraphIR) else dict(value)
    row["anchors"] = sorted(
        row.get("anchors") or [],
        key=lambda item: (str(item.get("role")), str(item.get("node_type"))),
    )
    row["roles"] = {key: row["roles"][key] for key in sorted(row.get("roles") or {})}
    row["walks"] = sorted(
        row.get("walks") or [], key=lambda item: str(item.get("walk_id"))
    )
    row["joins"] = sorted(row.get("joins") or [], key=_digest)
    row["role_constraints"] = sorted(row.get("role_constraints") or [], key=_digest)
    row["semantic_constraints"] = sorted(
        row.get("semantic_constraints") or [], key=_digest
    )
    return row


def query_graph_hash(value: QueryGraphIR | dict[str, Any]) -> str:
    payload = json.dumps(
        canonical_query_graph(value), sort_keys=True, default=str, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def query_graph_from_dict(value: dict[str, Any]) -> QueryGraphIR:
    """Rehydrate persisted QueryGraphIR without trusting mutable container types."""
    row = dict(value)
    graph = QueryGraphIR(
        query_graph_version=int(row.get("query_graph_version") or 0),
        discovery_method=str(row.get("discovery_method") or ""),
        operation_macro_id=str(row.get("operation_macro_id") or ""),
        answer_target=dict(row.get("answer_target") or {}),
        anchors=tuple(dict(item) for item in row.get("anchors") or []),
        roles={
            str(role): dict(spec) for role, spec in dict(row.get("roles") or {}).items()
        },
        walks=tuple(dict(item) for item in row.get("walks") or []),
        joins=tuple(dict(item) for item in row.get("joins") or []),
        role_constraints=tuple(
            dict(item) for item in row.get("role_constraints") or []
        ),
        semantic_constraints=tuple(
            dict(item) for item in row.get("semantic_constraints") or []
        ),
        binding_projection=dict(row.get("binding_projection") or {}),
        operation_template=dict(row.get("operation_template") or {}),
        answer_schema=dict(row.get("answer_schema") or {}),
        evidence_policy=dict(row.get("evidence_policy") or {}),
        sampling=dict(row.get("sampling") or {}),
        walk_grammar_version=str(
            row.get("walk_grammar_version") or WALK_GRAMMAR_VERSION
        ),
    )
    graph.validate()
    return graph


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()
