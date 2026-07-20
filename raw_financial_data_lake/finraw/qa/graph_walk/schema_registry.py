from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


WALK_GRAMMAR_VERSION = "1.0.0"


@dataclass(frozen=True, order=True)
class RelationSpec:
    relation_type: str
    source_node_type: str
    target_node_type: str
    allowed_directions: tuple[str, ...]
    cardinality: str
    semantic_role: str
    walk_cost: float
    is_answer_relevant: bool
    is_evidence_only: bool

    def target_for(self, from_type: str, direction: str) -> str | None:
        if direction not in self.allowed_directions:
            return None
        if direction == "out" and from_type == self.source_node_type:
            return self.target_node_type
        if direction == "in" and from_type == self.target_node_type:
            return self.source_node_type
        return None


def _relation(
    relation_type: str,
    source: str,
    target: str,
    *,
    cardinality: str = "many",
    role: str,
    cost: float = 1.0,
    answer: bool = True,
    evidence_only: bool = False,
) -> RelationSpec:
    return RelationSpec(
        relation_type=relation_type,
        source_node_type=source,
        target_node_type=target,
        allowed_directions=("out", "in"),
        cardinality=cardinality,
        semantic_role=role,
        walk_cost=cost,
        is_answer_relevant=answer,
        is_evidence_only=evidence_only,
    )


RELATION_SCHEMA: tuple[RelationSpec, ...] = tuple(
    sorted(
        [
            _relation("HAS_FACT", "Entity", "Fact", role="fact_binding"),
            _relation(
                "MEASURES",
                "Fact",
                "Metric",
                cardinality="one",
                role="metric_identity",
                cost=0.5,
            ),
            _relation(
                "IN_PERIOD",
                "Fact",
                "TimePeriod",
                cardinality="one",
                role="time_identity",
                cost=0.5,
            ),
            _relation(
                "FROM_SOURCE",
                "Fact",
                "DataSource",
                cardinality="one",
                role="provenance",
                cost=0.8,
                evidence_only=True,
            ),
            _relation(
                "USES_SOURCE_DEFINITION",
                "Fact",
                "SourceDefinition",
                cardinality="one",
                role="definition",
                cost=0.8,
                evidence_only=True,
            ),
            _relation(
                "TRACED_TO",
                "Fact",
                "RawObject",
                cardinality="one",
                role="raw_provenance",
                cost=0.8,
                evidence_only=True,
            ),
            _relation("DERIVED_FROM", "DerivedFact", "Fact", role="derived_input"),
            _relation(
                "ABOUT_ENTITY",
                "DerivedFact",
                "Entity",
                cardinality="one",
                role="derived_entity",
            ),
            _relation(
                "USES_METRIC", "DerivedFact", "Metric", role="derived_metric", cost=0.5
            ),
            _relation(
                "IN_PERIOD",
                "DerivedFact",
                "TimePeriod",
                cardinality="one",
                role="derived_time",
                cost=0.5,
            ),
            _relation(
                "HAS_SCOPE",
                "DerivedFact",
                "EntitySet",
                cardinality="one",
                role="scope_binding",
            ),
            _relation("CONTAINS_ENTITY", "EntitySet", "Entity", role="scope_member"),
            _relation(
                "BELONGS_TO_YEAR",
                "TimePeriod",
                "CalendarYear",
                cardinality="one",
                role="calendar_hierarchy",
                cost=0.5,
            ),
            _relation(
                "BELONGS_TO_QUARTER",
                "TimePeriod",
                "CalendarQuarter",
                cardinality="one",
                role="calendar_hierarchy",
                cost=0.5,
            ),
            _relation(
                "BELONGS_TO_MONTH",
                "TimePeriod",
                "CalendarMonth",
                cardinality="one",
                role="calendar_hierarchy",
                cost=0.5,
            ),
            _relation(
                "IN_FISCAL_YEAR",
                "TimePeriod",
                "FiscalYear",
                cardinality="one",
                role="fiscal_hierarchy",
                cost=0.5,
            ),
            _relation(
                "IN_FISCAL_YEAR_LABEL",
                "TimePeriod",
                "FiscalYearLabel",
                cardinality="one",
                role="fiscal_hierarchy",
                cost=0.5,
            ),
            _relation(
                "FILED",
                "Entity",
                "SourceDocument",
                role="document_binding",
                cost=1.2,
                evidence_only=True,
            ),
            _relation(
                "HAS_RAW_OBJECT",
                "SourceDocument",
                "RawObject",
                cardinality="one",
                role="document_provenance",
                cost=0.8,
                evidence_only=True,
            ),
            _relation(
                "FROM_SOURCE",
                "SourceDocument",
                "DataSource",
                cardinality="one",
                role="document_source",
                cost=0.8,
                evidence_only=True,
            ),
            _relation(
                "FROM_SOURCE",
                "RawObject",
                "DataSource",
                cardinality="one",
                role="raw_source",
                cost=0.8,
                evidence_only=True,
            ),
            _relation(
                "DEFINES",
                "SourceDefinition",
                "Metric",
                cardinality="one",
                role="definition_metric",
                cost=0.5,
            ),
            _relation(
                "PROVIDED_BY",
                "SourceDefinition",
                "DataSource",
                cardinality="one",
                role="definition_source",
                cost=0.5,
                evidence_only=True,
            ),
        ]
    )
)


def relation_candidates(
    from_type: str, *, answer_only: bool = False
) -> list[tuple[RelationSpec, str, str]]:
    output: list[tuple[RelationSpec, str, str]] = []
    for spec in RELATION_SCHEMA:
        if answer_only and spec.is_evidence_only:
            continue
        for direction in spec.allowed_directions:
            target = spec.target_for(from_type, direction)
            if target:
                output.append((spec, direction, target))
    return sorted(
        output,
        key=lambda item: (item[0].walk_cost, item[0].relation_type, item[1], item[2]),
    )


def validate_relation_step(
    from_type: str, relation: str, direction: str, to_type: str
) -> RelationSpec:
    matches = [
        spec
        for spec in RELATION_SCHEMA
        if spec.relation_type == relation
        and spec.target_for(from_type, direction) == to_type
    ]
    if len(matches) != 1:
        raise ValueError(
            "Unsupported typed walk edge: "
            f"{from_type} -[{relation}/{direction}]-> {to_type}"
        )
    return matches[0]


def relation_schema_manifest() -> dict[str, object]:
    rows = [asdict(spec) for spec in RELATION_SCHEMA]
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return {
        "walk_grammar_version": WALK_GRAMMAR_VERSION,
        "relation_count": len(rows),
        "relations": rows,
        "manifest_hash": hashlib.sha256(payload.encode()).hexdigest(),
    }
