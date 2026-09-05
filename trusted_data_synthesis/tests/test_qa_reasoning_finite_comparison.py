from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_candidate_family import (
    preflight as candidate_builder,
)
from trusted_synthesis.experiments.qa_reasoning_candidate_family import (
    runtime as candidate_runtime,
)
from trusted_synthesis.experiments.qa_reasoning_candidate_family import (
    source as candidate_source,
)
from trusted_synthesis.experiments.qa_reasoning_finite_comparison import preflight
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.comparison import (
    compare_family,
    compare_graphs,
    normalize_decimal,
)
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    ARTIFACT_ROOT,
    MANIFEST,
    PREDECESSOR,
    ComparisonInputError,
    FrozenReader,
    files_at,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.projection import (
    transparent_lookup_check,
)
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.rules import authorize
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import (
    FixedFixtureRuntimeError,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    catalog_operation_registry,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / (
    "trusted_data_synthesis/artifacts/qa_reasoning_finite_comparison/"
    "finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_v1_20260905/"
    "external_review.txt"
)
COMMIT = "b1e43da622c7fc10823c3d40d02d9b6445fdfe38"
TREE = "b33869265ee66faa25b997c1029bae8f6f7115c9"


def build(directory: Path) -> dict[str, Any]:
    return preflight.build_comparison(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=COMMIT,
        source_tree=TREE,
        output_directory=directory,
    )


@pytest.fixture(scope="module")
def products(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return build(tmp_path_factory.mktemp("qa_finite_comparison_tests") / "formal")


def test_exact_new_review_and_operator_scope() -> None:
    authorization = authorize(REVIEW.read_bytes())
    assert authorization["frozen_trajectories"] == 6
    assert not authorization["new_candidate_or_runtime_execution_authorized"]
    with pytest.raises(ComparisonInputError, match="review differs"):
        authorize(REVIEW.read_bytes() + b"\n")


def test_complete_saved_input_freeze_not_a_new_candidate_population(
    products: dict[str, Any],
) -> None:
    freeze = products["input_freeze"]
    assert (freeze["files"], freeze["bytes"]) == (278, 1176762)
    assert freeze["manifest_id"] == MANIFEST and freeze["artifact_root"] == ARTIFACT_ROOT
    assert freeze["primary_candidates"] == 4 and freeze["schedule_controls"] == 2
    assert freeze["new_candidate_declarations"] == freeze["input_runtime_executions"] == 0
    assert freeze["historical_next_stage_authorized"] is False
    assert [g["member_count"] for g in freeze["inherited_source_groups"]] == [7, 19]
    assert products["source_authority"]["implementation"]["member_count"] == 7


def test_rules_are_durable_before_comparator_and_explicitly_known_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = preflight.compare_family
    called = []
    output = tmp_path / "formal"

    def compare(graphs: Any) -> Any:
        receipt = json.loads((output / "rule_freeze_receipt.json").read_bytes())
        contract = json.loads((output / "measurement_contract.json").read_bytes())
        assert receipt["comparator_calls_before_freeze"] == 0
        assert receipt["candidate_outcomes_already_known"] is True
        assert contract["data_blind_confirmation_claimed"] is False
        assert any(
            e["kind"] == "directory_fsync" and e["relative_path"] == "measurement_contract.json"
            for e in receipt["durable_rule_write_events"]
        )
        called.append(True)
        return original(graphs)

    monkeypatch.setattr(preflight, "compare_family", compare)
    result = build(output)
    assert called == [True] and result["gate"]["passed"] == 4


def test_old_runtime_builders_and_registered_executors_are_never_called(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("new candidate construction or execution is forbidden")

    for owner, name in (
        (candidate_runtime, "run_candidate"),
        (candidate_builder, "build_preflight"),
        (candidate_source, "source_inventory"),
        (candidate_source, "build_family"),
    ):
        monkeypatch.setattr(owner, name, forbidden)
    registry = catalog_operation_registry()
    for owner in {
        type(registry.require(str(r["operator_id"])).executor) for r in registry.manifest()
    }:
        monkeypatch.setattr(owner, "execute", forbidden)
    result = build(tmp_path / "formal")
    assert result["scope"]["new_runtime_executions"] == 0
    assert result["revalidation"]["read_only_validator_calls"] == 6


def test_readonly_revalidation_counts_are_separate_from_candidate_execution(
    products: dict[str, Any],
) -> None:
    audit = products["revalidation"]
    assert audit["qualified"] == audit["actual_byte_projection_matches"] == 6
    assert audit["own_route_oracle_nodes"] == 40 and audit["answer_oracle_nodes"] == 48
    assert audit["operation_executor_calls"] == audit["runtime_calls"] == 0
    assert not hasattr(FrozenReader(ROOT / PREDECESSOR, {}), "write_json")


def test_all_six_actual_public_structures_are_preserved_and_projected(
    products: dict[str, Any],
) -> None:
    for task in products["graphs"].values():
        for group, graph in task.items():
            assert graph["admission"]["admitted"] and graph["normalization"]["complete"]
            assert len(graph["nodes"]) == 40 and len(graph["edges"]) == 127
            assert sum(n["kind"] == "operation" for n in graph["nodes"]) == 4
            raw = graph["audit"]["uncontracted_graph"]
            assert sum(n["kind"] == "operation" for n in raw["nodes"]) == (4 if group == "A" else 8)
            assert len(graph["audit"]["state_snapshots"]) == (5 if group == "A" else 9)


def test_sixteen_lookup_witnesses_require_all_five_actual_conditions(
    products: dict[str, Any],
) -> None:
    assert len(products["reductions"]) == 16
    for reduction in products["reductions"]:
        result = transparent_lookup_check(reduction["facts"])
        assert result["eligible"] and len(result["checks"]) == 5
        assert all(result["checks"].values())
        assert not reduction["historical_records_modified"]
        extra = copy.deepcopy(reduction["facts"])
        extra["no_extra_retained_effects"]["after_state"]["verification_conclusion"] = (
            "new-retained-effect"
        )
        assert transparent_lookup_check(extra)["status"] == "undetermined"


def test_six_pairs_have_complete_bidirectional_correspondence(products: dict[str, Any]) -> None:
    pairs = products["pairs"]
    assert [(p["fixture_id"], p["left_group"], p["right_group"]) for p in pairs] == [
        (f, a, b) for f in ("F1", "F2") for a, b in (("B", "C"), ("B", "A"), ("A", "C"))
    ]
    for pair in pairs:
        assert pair["status"] == "equivalent"
        proof = pair["correspondence"]
        assert all(
            proof[k]
            for k in (
                "complete_node_bijection_verified",
                "all_node_attributes_verified",
                "all_directed_edges_forward_verified",
                "all_directed_edges_backward_verified",
            )
        )
        assert pair["finite_search"]["completed"]


def test_primary_partition_and_control_roles_stay_per_task(products: dict[str, Any]) -> None:
    family = products["family"]
    assert family["comparison_closed"] and family["cross_task_pairs"] == 0
    for row in family["partitions"]:
        assert row["primary"]["members"] == ["B", "A"]
        assert row["primary"]["formal_semantic_class_count"] == 1
        assert row["all_candidates_with_control"]["formal_semantic_class_count"] == 1
        assert row["control"]["independent_strategy_witness"] is False


def test_projection_unit_controls_are_not_new_qualified_witnesses(products: dict[str, Any]) -> None:
    controls = products["controls"]
    assert controls["passed"] and len(controls["cases"]) == 22
    assert all(row["passed"] for row in controls["cases"])
    source = next(
        r for r in controls["cases"] if r["name"] == "same_answer_changed_evidence_source"
    )
    assert (
        source["final_semantics_unchanged"] and source["observed"] == "different_retained_semantics"
    )
    roles = next(r for r in controls["cases"] if r["name"] == "same_answer_changed_ordered_roles")
    assert (
        roles["final_semantics_unchanged"] and roles["observed"] == "different_retained_semantics"
    )


def test_missing_semantics_returns_unknown_not_a_class(products: dict[str, Any]) -> None:
    graphs = copy.deepcopy(products["graphs"])
    operation = next(n for n in graphs["F1"]["A"]["nodes"] if n["kind"] == "operation")
    del operation["attrs"]["contract"]["semantic_version"]
    family = compare_family(graphs)
    assert not family["comparison_closed"]
    assert family["partitions"][0]["formal_semantic_class_count"] is None
    assert family["partitions"][1]["formal_semantic_class_count"] == 1


def test_incomplete_search_and_cross_task_comparison_are_not_differences(
    products: dict[str, Any],
) -> None:
    graphs = products["graphs"]
    assert (
        compare_graphs(graphs["F1"]["B"], graphs["F1"]["A"], max_search_states=0)["status"]
        == "undetermined"
    )
    assert compare_graphs(graphs["F1"]["B"], graphs["F2"]["B"])["status"] == "undetermined"


def test_exact_decimal_normalization_does_not_round() -> None:
    value = "1.123456789012345678901234567890123456789"
    assert normalize_decimal(value) == normalize_decimal(value + "000")
    assert normalize_decimal(value) != normalize_decimal(value[:-1] + "8")
    assert normalize_decimal("-0.00") == "0"


def test_frozen_reader_does_not_admit_changed_or_outside_bytes() -> None:
    files = files_at(ROOT / PREDECESSOR)
    changed = dict(files)
    changed["report.json"] = b"{}"
    with pytest.raises(ComparisonInputError, match="changed on disk"):
        FrozenReader(ROOT / PREDECESSOR, changed).read_bytes("report.json")
    with pytest.raises(ComparisonInputError, match="outside admitted"):
        FrozenReader(ROOT / PREDECESSOR, files).read_bytes("../unbound.json")


def test_complete_empty_directory_rebuild_and_manifest(
    products: dict[str, Any], tmp_path: Path
) -> None:
    old = files_at(ROOT / PREDECESSOR)
    second = build(tmp_path / "second")
    assert files_at(second["writer"].root) == files_at(products["writer"].root)
    assert files_at(ROOT / PREDECESSOR) == old
    manifest = second["manifest"]
    validate_manifest(
        files_at(second["writer"].root), manifest["manifest_id"], manifest["artifact_root"]
    )
    with pytest.raises(FixedFixtureRuntimeError, match="already exists"):
        build(tmp_path / "second")


def test_scope_transition_closes_only_the_finite_comparison(products: dict[str, Any]) -> None:
    assert products["gate"]["passed"] == 4
    assert products["gate"]["failed"] == products["gate"]["unknown"] == 0
    assert products["scope"]["Provider_calls"] == products["scope"]["GPU_jobs"] == 0
    assert products["decision"]["primary_class_counts_by_task"] == {"F1": 1, "F2": 1}
    transition = products["transition"]
    assert transition["stop_expanding_lookup_deletion_direct_reference_label_and_schedule_axes"]
    assert not transition["next_stage_authorized"]
    assert not transition["mechanical_repeat_independent_audit_required"]


def test_saved_bijections_are_independently_checkable_without_comparator_helpers(
    products: dict[str, Any],
) -> None:
    for pair in products["pairs"]:
        task = products["graphs"][pair["fixture_id"]]
        left, right = task[pair["left_group"]], task[pair["right_group"]]
        proof = pair["correspondence"]
        mapping = {r["left_id"]: r["right_id"] for r in proof["node_bijection"]}
        lnodes = {n["id"]: n for n in left["nodes"]}
        rnodes = {n["id"]: n for n in right["nodes"]}
        assert set(mapping) == set(lnodes)
        assert set(mapping.values()) == set(rnodes)
        assert len(mapping) == len(set(mapping.values())) == 40
        for a, b in mapping.items():
            assert lnodes[a]["kind"] == rnodes[b]["kind"]
            assert lnodes[a]["attrs"] == rnodes[b]["attrs"]
        matched = proof["edge_bijection"]
        assert {r["left_index"] for r in matched} == set(range(len(left["edges"])))
        assert {r["right_index"] for r in matched} == set(range(len(right["edges"])))
        for row in matched:
            a, b = left["edges"][row["left_index"]], right["edges"][row["right_index"]]
            assert mapping[a["source"]] == b["source"]
            assert mapping[a["target"]] == b["target"]
            assert {k: v for k, v in a.items() if k not in {"source", "target"}} == {
                k: v for k, v in b.items() if k not in {"source", "target"}
            }


def test_incomplete_projection_keeps_full_comparison_gates_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = preflight.project_runtime

    def incomplete(fixture: Any, execution: Any, **kwargs: Any) -> Any:
        graph = original(fixture, execution, **kwargs)
        if fixture["fixture_id"] == "F1" and execution["group"] == "A":
            graph["normalization"]["complete"] = False
            graph["normalization"]["issues"].append("unit_control_uninterpreted_public_effect")
        return graph

    monkeypatch.setattr(preflight, "project_runtime", incomplete)
    result = build(tmp_path / "unknown")
    assert result["gate"]["passed"] == 2
    assert result["gate"]["unknown"] == 2
    assert result["gate"]["failed"] == 0
    assert not result["decision"]["complete_semantic_comparison"]
    assert result["decision"]["primary_class_counts_by_task"]["F1"] is None
    assert result["transition"]["closed_object"] is None
