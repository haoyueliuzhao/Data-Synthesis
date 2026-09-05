from __future__ import annotations

import copy
import subprocess
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_candidate_family.models import CandidateRoute
from trusted_synthesis.experiments.qa_reasoning_candidate_family.preflight import (
    PREDECESSOR_DIRECTORY,
    CandidateFamilyError,
    build_preflight,
    files_at,
    helper_boundary,
    source_group,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_candidate_family.source import (
    build_family,
    source_inventory,
)
from trusted_synthesis.experiments.qa_reasoning_candidate_family.validation import (
    validate_candidate,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import (
    DurableArtifactWriter,
    FixedFixtureRuntimeError,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    catalog_operation_registry,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/a54baae5-d4ec-47be-99d3-73e60df917cc/pasted-text.txt"
)


def git(value: str) -> str:
    return subprocess.run(
        ("git", "-C", str(ROOT), "rev-parse", value), check=True, capture_output=True, text=True
    ).stdout.strip()


def build(target: Path) -> dict[str, Any]:
    return build_preflight(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=git("HEAD"),
        source_tree=git("HEAD^{tree}"),
        output_directory=target,
    )


@pytest.fixture(scope="module")
def products(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return build(tmp_path_factory.mktemp("qa_candidate_family") / "formal")


def test_source_inventory_and_family_do_not_execute_operations_or_oracles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = catalog_operation_registry()
    targets = set()
    for row in registry.manifest():
        definition = registry.require(str(row["operator_id"]))
        targets.add((type(definition.executor), "execute"))
        targets.add((type(definition.oracle_verifier), "verify"))

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("candidate outcome inspected before source registration")

    for owner, name in targets:
        monkeypatch.setattr(owner, name, forbidden)
    inventory, fixtures = source_inventory(ROOT)
    registration, candidates = build_family(fixtures, inventory)
    assert len(fixtures) == 2 and len(candidates) == 6
    assert len(registration["main_candidate_ids"]) == 4
    assert len(registration["control_candidate_ids"]) == 2


def test_exact_parent_and_declared_sources_are_frozen(products: dict[str, Any]) -> None:
    freeze = products["predecessor_freeze"]
    assert freeze["file_count"] == 15 and freeze["total_bytes"] == 64237
    assert freeze["historical_next_stage_authorized"] is False
    source = products["source_authority"]
    assert source["implementation"]["member_count"] == 7
    paths = {r["path"] for r in source["declared_references"]["members"]}
    assert all(
        r["relative_path"] in paths for r in products["source_inventory"]["source_file_bindings"]
    )


def test_finite_route_registration_preserves_tasks_and_registered_semantic_operations(
    products: dict[str, Any],
) -> None:
    assert [
        (c["fixture_id"], c["group"], len(c["program"].nodes)) for c in products["candidates"]
    ] == [
        ("F1", "B", 8),
        ("F1", "A", 4),
        ("F1", "C", 8),
        ("F2", "B", 8),
        ("F2", "A", 4),
        ("F2", "C", 8),
    ]
    for fixture in products["fixtures"]:
        group = [c for c in products["candidates"] if c["fixture_id"] == fixture["fixture_id"]]
        assert len({c["task_id"] for c in group}) == 1
        assert len({c["scope_binding_id"] for c in group}) == 1
        assert len(fixture["package"].task.oracle.task_program.nodes) == 8
        for candidate in group:
            assert [
                n.operator_id for n in candidate["program"].nodes if n.operator_id != "lookup"
            ] == [
                "growth",
                "growth",
                "signed_percentage_point_gap",
                "absolute_percentage_point_gap",
            ]


def test_actual_registration_is_durable_before_every_operation_dispatch(
    products: dict[str, Any],
) -> None:
    writer = products["writer"]
    registered = next(
        e["event_ordinal"]
        for e in writer.events
        if e["kind"] == "directory_fsync" and e["relative_path"] == "registration_receipt.json"
    )
    dispatches = [e for e in writer.events if e["kind"] == "action_dispatch"]
    assert len(dispatches) == 40
    assert all(e["event_ordinal"] > registered for e in dispatches)
    assert products["registration_receipt"]["outcomes_seen_at_registration"] == 0
    assert products["registration_receipt"]["preselection_candidate_executor_or_oracle_calls"] == 0


def test_six_own_executions_and_five_obligations_are_verified(products: dict[str, Any]) -> None:
    execution = products["execution_audit"]
    assert execution["positive_runtime_executions"] == 6
    assert execution["primary_candidates"] == 4 and execution["schedule_controls"] == 2
    assert execution["actual_registered_actions"] == 40
    assert execution["final_closing_artifacts"] == 6
    assert execution["qa_valid"] == execution["trajectory_valid"] == execution["qualified"] == 6
    for validation in products["validations"]:
        assert len(validation["evidence_to_obligation_discharge"]) == 5
        assert validation["first_failure"] is None


def test_direct_route_is_accepted_without_oracle_lookup_step_backfill(
    products: dict[str, Any],
) -> None:
    execution = products["execution_audit"]
    assert execution["direct_evidence_qualified"] == 2
    assert execution["own_trajectory_oracle_node_replays"] == 40
    assert execution["answer_oracle_node_replays"] == 48
    assert execution["answer_oracle_steps_backfilled_as_candidate_actions"] == 0
    for candidate, result, validation in zip(
        products["candidates"],
        products["results"],
        products["validations"],
        strict=True,
    ):
        if candidate["group"] == "A":
            assert result["actual_registered_action_count"] == 4
            assert validation["trajectory_oracle_node_replay_count"] == 4
            assert validation["answer_oracle_node_replay_count"] == 8


def test_swap_is_accepted_by_same_new_validator_without_new_mapper_claim(
    products: dict[str, Any],
) -> None:
    assert products["execution_audit"]["swap_controls_qualified"] == 2
    assert products["execution_audit"]["quotient_class_count"] is None
    assert not products["execution_audit"]["formal_semantic_projection_created"]
    assert products["execution_audit"]["semantic_separation_result"] == "not_evaluated"
    assert helper_boundary()["passed"]


def test_direct_isolated_controls_reject_and_cosmetic_label_is_accepted(
    products: dict[str, Any],
) -> None:
    negative = products["negative_controls"]
    assert negative["attempted"] == 10
    assert negative["rejected"] == 9 and negative["accepted"] == 1
    assert negative["positive_runtime_executions"] == 0
    assert negative["baseline_independent_replay_count"] == 1
    assert negative["negative_independent_replay_count"] == 10
    assert negative["formal_artifact_bytes_unchanged"] and negative["passed"]
    label = next(r for r in negative["controls"] if r["name"] == "route_label_only")
    assert label["qualified"] and not label["counted_as_new_semantic_class"]
    assert all(r["passed"] for r in negative["controls"])


def test_independent_replay_uses_saved_files_not_runtime_memory(products: dict[str, Any]) -> None:
    for candidate, result, expected in zip(
        products["candidates"],
        products["results"],
        products["validations"],
        strict=True,
    ):
        fixture = next(
            f for f in products["fixtures"] if f["fixture_id"] == candidate["fixture_id"]
        )
        reader = DurableArtifactWriter(products["writer"].root)
        assert reader.events == []
        actual = validate_candidate(
            writer=reader, fixture=fixture, candidate=candidate, result=result
        )
        assert canonical_json_bytes(actual) == canonical_json_bytes(expected)


def test_candidate_labels_cannot_replace_content_identity(products: dict[str, Any]) -> None:
    candidate = copy.deepcopy(products["candidates"][0])
    candidate["field_provenance"]["program"] = "model_proposed"
    with pytest.raises(ValueError):
        CandidateRoute.model_validate(candidate)


def test_source_guard_review_and_no_replace_fail_before_new_execution(
    products: dict[str, Any],
    tmp_path: Path,
) -> None:
    altered = tmp_path / "review.txt"
    altered.write_bytes(REVIEW.read_bytes() + b"\n")
    target = tmp_path / "must_not_exist"
    with pytest.raises(CandidateFamilyError) as error:
        build_preflight(
            repo_root=ROOT,
            external_audit_path=altered,
            source_commit="0" * 40,
            source_tree="1" * 40,
            output_directory=target,
        )
    assert error.value.stage == "authorization.review" and not target.exists()
    with pytest.raises(CandidateFamilyError):
        source_group(ROOT, "0" * 40, "1" * 40, ())
    writer = products["writer"]
    original = writer.read_bytes("candidate_preregistration.json")
    with pytest.raises(FixedFixtureRuntimeError):
        writer.write_bytes("candidate_preregistration.json", b"forged")
    assert writer.read_bytes("candidate_preregistration.json") == original


def test_complete_second_build_reproduces_actual_bytes_without_historical_writes(
    products: dict[str, Any],
    tmp_path: Path,
) -> None:
    previous = files_at(ROOT / PREDECESSOR_DIRECTORY)
    second = build(tmp_path / "second")
    first_files = files_at(products["writer"].root)
    assert first_files == files_at(second["writer"].root)
    assert previous == files_at(ROOT / PREDECESSOR_DIRECTORY)
    validate_manifest(
        first_files, products["manifest"]["manifest_id"], products["manifest"]["artifact_root"]
    )


def test_manifest_rejects_same_length_substitution(products: dict[str, Any]) -> None:
    altered = files_at(products["writer"].root)
    altered["operator_directive.txt"] = b"x" * len(altered["operator_directive.txt"])
    with pytest.raises(CandidateFamilyError):
        validate_manifest(
            altered, products["manifest"]["manifest_id"], products["manifest"]["artifact_root"]
        )


def test_current_results_do_not_imply_class_count_model_or_online_authority(
    products: dict[str, Any],
) -> None:
    assert products["gate_evaluation"]["passed"] == 5
    assert products["gate_evaluation"]["failed"] == 0
    assert not products["gate_evaluation"]["two_semantic_classes_required"]
    assert products["report"]["semantic_class_count"] is None
    scope = products["scope"]
    assert scope["Provider_calls"] == scope["credential_lookups"] == scope["GPU_jobs"] == 0
    assert scope["new_operations"] == scope["new_algebraic_rules"] == scope["new_task_cases"] == 0
    assert not products["transition"]["next_stage_authorized"]
    assert not products["transition"]["mechanical_repeat_independent_audit_required"]
    assert not scope["old_mainline_resumed"]
