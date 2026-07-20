from __future__ import annotations

import copy
import json
import pytest

from finraw.db.client import MetadataDB
from finraw.qa.binding_executor import RELATIONAL_OPERATOR_REGISTRY
from finraw.qa.evidence_finalizer import finalize_evidence
from finraw.qa.graph_walk.explorer import discover_query_graphs
from finraw.qa.graph_walk.grammar import compile_query_graph
from finraw.qa.graph_walk.operation_macros import operation_macro_manifest
from finraw.qa.graph_walk.query_graph import QueryGraphIR, query_graph_from_dict
from finraw.qa.graph_walk.schema_registry import (
    relation_schema_manifest,
    validate_relation_step,
)
from finraw.qa.pattern_mining import (
    _typed_walk_binding_identity,
    _unambiguous_typed_walk_records,
)
from finraw.qa.walk_verifier import validate_walk_binding


def test_typed_walk_registry_discovers_deterministic_query_graphs():
    first = discover_query_graphs()
    second = discover_query_graphs()

    assert len(first) == 3
    assert [item.query_graph_hash for item in first] == [
        item.query_graph_hash for item in second
    ]
    assert len({item.query_graph_hash for item in first}) == 3
    assert relation_schema_manifest()["manifest_hash"]
    assert operation_macro_manifest()["manifest_hash"]


def test_typed_walk_relation_registry_is_fail_closed():
    validate_relation_step("Entity", "HAS_FACT", "out", "Fact")

    with pytest.raises(ValueError, match="Unsupported typed walk edge"):
        validate_relation_step("Entity", "HAS_FACT", "in", "Fact")
    with pytest.raises(ValueError, match="Unsupported typed walk edge"):
        validate_relation_step("Entity", "UNKNOWN_RELATION", "out", "Fact")


def test_query_graph_compiles_role_filters_joins_coverage_and_projection_v2():
    graphs = {item.operation_macro_id: item for item in discover_query_graphs()}
    graph = graphs["scope_filter_rank_followup"]
    plan = compile_query_graph(graph)
    operators = [item["op"] for item in plan["relational_ops"]]

    assert plan["ir_version"] == 2
    assert operators[0] == "scan_pinned_graph_nodes"
    assert "expand_graph_edges" in operators
    assert "filter_graph_role" in operators
    assert "deduplicate_graph_role" in operators
    assert "assert_role_key_equal" in operators
    assert "assert_role_key_relation" in operators
    assert "require_role_coverage" in operators
    assert operators[-1] == "project_graph_binding_v2"
    assert set(operators) <= set(RELATIONAL_OPERATOR_REGISTRY)
    assert query_graph_from_dict(graph.as_dict()).query_graph_hash == (
        graph.query_graph_hash
    )


def test_typed_walk_answer_uniqueness_is_per_semantic_binding():
    binding = {
        "input_bindings": {"facts": ["f1", "f2"]},
        "fact_ids": ["f1", "f2"],
        "entity_ids": ["A_US"],
        "metric_ids": ["revenue"],
        "scope_entity_ids": ["A_US"],
        "query_graph_hash": "query",
        "graph_edge_ids": ["edge_path_a"],
    }
    same_binding_other_path = {
        **binding,
        "graph_edge_ids": ["edge_path_b"],
    }
    assert _typed_walk_binding_identity(binding) == _typed_walk_binding_identity(
        same_binding_other_path
    )

    identity = _typed_walk_binding_identity(binding)
    duplicate_records = [
        {
            "binding": binding,
            "output_hash": "answer_a",
            "_semantic_binding_hash": identity,
        },
        {
            "binding": same_binding_other_path,
            "output_hash": "answer_a",
            "_semantic_binding_hash": identity,
        },
    ]
    selected, unique_rate, group_count = _unambiguous_typed_walk_records(
        duplicate_records
    )
    assert len(selected) == 1
    assert group_count == 1
    assert unique_rate == 1.0

    conflicting = [
        *duplicate_records,
        {
            "binding": binding,
            "output_hash": "answer_b",
            "_semantic_binding_hash": identity,
        },
    ]
    selected, unique_rate, group_count = _unambiguous_typed_walk_records(conflicting)
    assert selected == []
    assert group_count == 1
    assert unique_rate == 0.0


def test_evidence_finalizer_separates_required_context_and_discarded_edges():
    binding = {
        "scope_entity_ids": ["A", "B"],
        "scope_coverage": {"coverage": 1.0},
        "walk_binding_trace": {
            "roles": {
                "facts": [
                    {"node_id": "fact_a", "node_type": "Fact", "source_pk": "a"},
                    {"node_id": "fact_b", "node_type": "Fact", "source_pk": "b"},
                ],
                "metric": [
                    {"node_id": "metric", "node_type": "Metric", "source_pk": "m"}
                ],
            },
            "edges": [
                {
                    "edge_id": "measure_a",
                    "src_node_id": "fact_a",
                    "dst_node_id": "metric",
                    "relation_type": "MEASURES",
                },
                {
                    "edge_id": "measure_b",
                    "src_node_id": "fact_b",
                    "dst_node_id": "metric",
                    "relation_type": "MEASURES",
                },
                {
                    "edge_id": "unrelated",
                    "src_node_id": "other_1",
                    "dst_node_id": "other_2",
                    "relation_type": "HAS_SECURITY",
                },
            ],
        },
    }
    output = {
        "value": "1",
        "lineage": {"input_fact_ids": ["a", "b"], "selected_fact_ids": ["a"]},
    }

    finalized = finalize_evidence(binding, output)

    assert finalized["required_evidence"]["fact_ids"] == ["a"]
    assert [item["edge_id"] for item in finalized["required_evidence"]["edges"]] == [
        "measure_a"
    ]
    assert finalized["discarded_evidence"]["edge_count"] == 1
    assert finalized["checks"]["required_evidence_coverage"] == 1.0


def _walk_verifier_fixture(tmp_path):
    db = MetadataDB(str(tmp_path / "walk_verifier.db"))
    db.init_schema()
    kg_build_id = "kg_walk_test"
    graph = QueryGraphIR(
        query_graph_version=1,
        discovery_method="static_typed_walk",
        operation_macro_id="test_fact_metric_trace",
        answer_target={"type": "numeric", "role": "fact"},
        anchors=({"role": "fact", "node_type": "Fact"},),
        roles={
            "fact": {"node_type": "Fact", "cardinality": "one", "required": True},
            "metric": {
                "node_type": "Metric",
                "cardinality": "one",
                "required": True,
            },
        },
        walks=(
            {
                "walk_id": "fact_metric",
                "steps": [
                    {
                        "from_role": "fact",
                        "relation": "MEASURES",
                        "direction": "out",
                        "to_role": "metric",
                        "to_node_type": "Metric",
                        "mode": "one",
                    }
                ],
            },
        ),
        joins=(),
        role_constraints=(),
        semantic_constraints=(),
        binding_projection={"fact_roles": ["fact"]},
        operation_template={
            "operators": [
                {
                    "step_id": "answer",
                    "operator": "lookup",
                    "inputs": [{"binding": "fact"}],
                }
            ],
            "output_step": "answer",
        },
        answer_schema={"type": "numeric"},
        evidence_policy={"required_roles": ["fact"]},
        sampling={},
    )
    graph.validate()
    fact_node = f"fact:f1@@{kg_build_id}"
    metric_node = f"metric:revenue@@{kg_build_id}"
    edge_id = f"edge:measure@@{kg_build_id}"
    db.execute(
        "INSERT INTO kg_nodes (node_id, stable_node_id, kg_build_id, node_type, "
        "source_pk, properties_json, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            fact_node,
            "fact:f1",
            kg_build_id,
            "Fact",
            "f1",
            json.dumps({"metric_id": "revenue"}),
            1,
        ),
    )
    db.execute(
        "INSERT INTO kg_nodes (node_id, stable_node_id, kg_build_id, node_type, "
        "source_pk, properties_json, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            metric_node,
            "metric:revenue",
            kg_build_id,
            "Metric",
            "revenue",
            "{}",
            1,
        ),
    )
    db.execute(
        "INSERT INTO kg_edges (edge_id, stable_edge_id, kg_build_id, src_node_id, "
        "dst_node_id, relation_type, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            edge_id,
            "edge:measure",
            kg_build_id,
            fact_node,
            metric_node,
            "MEASURES",
            1,
        ),
    )
    binding = {
        "query_graph_hash": graph.query_graph_hash,
        "fact_ids": ["f1"],
        "input_bindings": {"fact": "f1"},
        "walk_binding_trace": {
            "roles": {
                "fact": [
                    {"node_id": fact_node, "node_type": "Fact", "source_pk": "f1"}
                ],
                "metric": [
                    {
                        "node_id": metric_node,
                        "node_type": "Metric",
                        "source_pk": "revenue",
                    }
                ],
            },
            "edges": [
                {
                    "edge_id": edge_id,
                    "src_node_id": fact_node,
                    "dst_node_id": metric_node,
                    "relation_type": "MEASURES",
                }
            ],
        },
        "graph_edges": [],
        "scope_entity_ids": [],
        "scope_coverage": {},
    }
    output = {
        "value": "1",
        "lineage": {"input_fact_ids": ["f1"], "selected_fact_ids": ["f1"]},
    }
    pattern_spec = {
        "query_graph_ir": graph.as_dict(),
        "query_graph_hash": graph.query_graph_hash,
    }
    return db, kg_build_id, pattern_spec, binding, output


def test_walk_verifier_replays_edge_role_hash_and_lineage(tmp_path):
    db, kg_build_id, pattern_spec, binding, output = _walk_verifier_fixture(tmp_path)

    result = validate_walk_binding(db, kg_build_id, pattern_spec, binding, output)

    assert result["passed"] is True
    assert all(item["passed"] for item in result["checks"].values())

    changed_edge = copy.deepcopy(binding)
    changed_edge["walk_binding_trace"]["edges"][0]["relation_type"] = "FROM_SOURCE"
    assert (
        validate_walk_binding(db, kg_build_id, pattern_spec, changed_edge, output)[
            "checks"
        ]["walk_edge_replay"]["passed"]
        is False
    )

    changed_role = copy.deepcopy(binding)
    changed_role["walk_binding_trace"]["roles"]["metric"][0]["node_type"] = "Entity"
    assert (
        validate_walk_binding(db, kg_build_id, pattern_spec, changed_role, output)[
            "checks"
        ]["walk_role_type_match"]["passed"]
        is False
    )

    changed_hash = {**binding, "query_graph_hash": "mutated"}
    assert (
        validate_walk_binding(db, kg_build_id, pattern_spec, changed_hash, output)[
            "checks"
        ]["query_graph_hash"]["passed"]
        is False
    )

    missing_lineage = {"value": "1", "lineage": {"selected_fact_ids": ["missing"]}}
    assert (
        validate_walk_binding(db, kg_build_id, pattern_spec, binding, missing_lineage)[
            "checks"
        ]["answer_lineage_match"]["passed"]
        is False
    )
