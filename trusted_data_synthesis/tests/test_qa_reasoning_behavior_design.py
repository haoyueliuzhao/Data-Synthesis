from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_behavior_design.contracts import (
    build_contract,
    classify_change,
    run_design_controls,
)
from trusted_synthesis.experiments.qa_reasoning_behavior_design.design import (
    NEXT_CANDIDATE,
    PREDECESSOR_DIRECTORY,
    BehaviorDesignError,
    boundary_audit,
    build_design,
    files_at,
    source_group,
    validate_manifest,
    write_formal,
)
from trusted_synthesis.experiments.qa_reasoning_behavior_design.models import DesignChangeRequest

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/3f09364e-ec74-4313-aa59-22a37b79f76c/pasted-text.txt"
)


def git(value: str) -> str:
    return subprocess.run(
        ("git", "-C", str(ROOT), "rev-parse", value), check=True, capture_output=True, text=True
    ).stdout.strip()


def request(*dimensions: str, **kwargs: Any) -> dict[str, Any]:
    return {"execution_status": "design_unexecuted", "changed_dimensions": dimensions, **kwargs}


def build(target: Path) -> dict[str, Any]:
    return build_design(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=git("HEAD"),
        source_tree=git("HEAD^{tree}"),
        output_directory=target,
    )


@pytest.fixture(scope="module")
def products(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return build(tmp_path_factory.mktemp("qa_behavior_design") / "formal")


def test_exact_closed_predecessor_is_frozen_without_rerunning_it(products: dict[str, Any]) -> None:
    freeze = products["predecessor_freeze"]
    assert freeze["file_count"] == 18 and freeze["total_bytes"] == 126608
    assert freeze["current_audit_topic"] == "closed_as_scoped"
    assert freeze["historical_next_stage_authorized"] is False
    assert freeze["old_audit_builder_calls"] == freeze["old_runtime_replays"] == 0
    assert products["source_authority"]["implementation"]["member_count"] == 4
    assert (
        sum(g["member_count"] for g in products["source_authority"]["declared_reference_sources"])
        == 3
    )


def test_oracle_and_obligations_do_not_prescribe_a_unique_route() -> None:
    contract = build_contract()
    boundary = contract["oracle_and_obligation_boundary"]
    assert boundary["is_answer_correctness_oracle_only"] is True
    assert boundary["prescribes_unique_reasoning_path"] is False
    assert contract["same_task_scope"]["actual_support_selection_is_behavior_not_task_identity"]
    assert "not universal" in boundary["historical_five_step_execute_only_graph"]
    assert "never waive" in boundary["missing_alternative_validator"]


def test_operational_changes_collapse_but_no_measured_class_is_emitted() -> None:
    changes = (
        request("wording"),
        request("runtime_identity"),
        request("schedule_order", schedule_relation="independent_commuting_swap"),
        request(
            "numeric_surface",
            numeric_before="1.00000000000000000000000000000000001",
            numeric_after="1.0000000000000000000000000000000000100",
        ),
    )
    for change in changes:
        result = classify_change(change)
        assert result["classification"] == "equivalent_by_design"
        assert not result["equivalence_or_separation_empirically_established"]
        assert result["quotient_state_id"] is None
        assert result["actual_trajectory_rows"] == result["semantic_class_witnesses"] == 0


def test_meaningful_changes_are_only_conditional_until_actual_own_validity() -> None:
    changes = (
        request("evidence_support", evidence_relation="different_admissible_visible_support"),
        request("decision_basis", basis_relation="different_typed_grounded_basis"),
        request(
            "derivation_dependencies", derivation_relation="different_typed_obligation_discharge"
        ),
        request("observation_update", update_relation="observation_grounded_rejection_or_revision"),
    )
    for change in changes:
        result = classify_change(change)
        assert result["classification"] == "retain_difference_subject_to_future_validity"
        assert result["input_relations_are_unverified_design_premises"]
        assert len(result["required_future_validations"]) >= 5
        assert result["semantic_class_witnesses"] == 0


def test_wording_or_swap_cannot_hide_a_semantic_change() -> None:
    result = classify_change(
        request(
            "wording",
            "schedule_order",
            "decision_basis",
            schedule_relation="independent_commuting_swap",
            basis_relation="different_typed_grounded_basis",
        )
    )
    assert result["classification"] == "retain_difference_subject_to_future_validity"
    undeclared = classify_change(
        request("wording", basis_relation="different_typed_grounded_basis")
    )
    assert undeclared["classification"] == "reject_design_request"


def test_scope_changes_cannot_manufacture_same_task_classes() -> None:
    for field in build_contract()["same_task_scope"]["fixed_dimensions"]:
        result = classify_change(request(field))
        assert result["classification"] == "reject_design_request"
    assert (
        classify_change(
            request("evidence_support", evidence_relation="outside_frozen_visible_universe")
        )["classification"]
        == "reject_design_request"
    )


def test_invalid_update_order_numeric_or_rewrite_is_not_a_class() -> None:
    for change in (
        request("observation_update", update_relation="unsupported_rewrite"),
        request("schedule_order", schedule_relation="dependency_crossing"),
        request("numeric_surface", numeric_before="NaN", numeric_after="NaN"),
        request("numeric_surface", numeric_before="1", numeric_after="1.000001"),
        request("unregistered_equivalence"),
    ):
        result = classify_change(change)
        assert result["classification"] == "reject_design_request"
        assert result["semantic_class_witnesses"] == 0


def test_runtime_qualification_and_model_ownership_cannot_be_injected() -> None:
    for extra in (
        {"qualified": True},
        {"measured_class_count": 2},
        {"model_behavior_evidence": True},
        {"field_origin": "model_proposed"},
    ):
        assert (
            classify_change(request("wording", **extra))["classification"]
            == "reject_design_request"
        )
    typed = DesignChangeRequest(
        execution_status="design_unexecuted", changed_dimensions=("wording",)
    )
    forged = typed.model_copy(update={"execution_status": "qualified"})
    assert classify_change(forged)["classification"] == "reject_design_request"
    roles = build_contract()["responsibility_matrix"]
    assert roles["host_fixed_trajectory_is_model_owned"] is False
    assert roles["model_reachability_or_contribution_established"] is False


def test_rehashed_design_contract_substitution_rejects() -> None:
    altered = copy.deepcopy(build_contract())
    altered["responsibility_matrix"]["host_fixed_trajectory_is_model_owned"] = True
    altered["contract_id"] = strict_canonical_hash(
        {k: v for k, v in altered.items() if k != "contract_id"},
        prefix="qa_reasoning_behavior_design_contract:",
    )
    assert classify_change(request("wording"), altered)["classification"] == "reject_design_request"


def test_design_requests_replay_after_formal_json_roundtrip(products: dict[str, Any]) -> None:
    controls = products["design_controls"]
    assert controls["passed"] and controls["actual_trajectory_rows"] == 0
    for group in ("equivalence_controls", "conditional_separation_controls", "rejected_controls"):
        for row in controls[group]:
            restored = json.loads(canonical_json_bytes(row["request"]))
            assert classify_change(restored)["classification"] == row["expected_classification"]
    assert run_design_controls(build_contract())["passed"]


def test_historical_commutation_is_retained_not_remeasured(products: dict[str, Any]) -> None:
    control = products["retained_commutation"]
    assert control["retained_task_count"] == 2 and control["retained_projection_count"] == 4
    assert all(row["same_task_projection_byte_equal"] for row in control["rows"])
    assert [row["historical_quotient_classes"] for row in control["rows"]] == [1, 1]
    assert control["new_trajectory_executions"] == control["new_semantic_class_witnesses"] == 0


def test_second_full_design_build_matches_and_keeps_history_unchanged(
    products: dict[str, Any],
    tmp_path: Path,
) -> None:
    before = files_at(ROOT / PREDECESSOR_DIRECTORY)
    second = build(tmp_path / "second")
    first_files = files_at(products["output_directory"])
    assert first_files == files_at(second["output_directory"])
    assert before == files_at(ROOT / PREDECESSOR_DIRECTORY)
    validate_manifest(
        first_files, products["manifest"]["manifest_id"], products["manifest"]["artifact_root"]
    )


def test_invalid_review_source_manifest_and_replacement_fail_closed(
    products: dict[str, Any],
    tmp_path: Path,
) -> None:
    review = tmp_path / "wrong.txt"
    review.write_bytes(REVIEW.read_bytes() + b"\n")
    target = tmp_path / "absent"
    with pytest.raises(BehaviorDesignError) as error:
        build_design(
            repo_root=ROOT,
            external_audit_path=review,
            source_commit="0" * 40,
            source_tree="1" * 40,
            output_directory=target,
        )
    assert error.value.stage == "authorization.review" and not target.exists()
    with pytest.raises(BehaviorDesignError):
        source_group(ROOT, "0" * 40, "1" * 40, ())
    altered = files_at(products["output_directory"])
    altered["operator_directive.txt"] = b"x" * len(altered["operator_directive.txt"])
    with pytest.raises(BehaviorDesignError):
        validate_manifest(
            altered, products["manifest"]["manifest_id"], products["manifest"]["artifact_root"]
        )
    with pytest.raises(BehaviorDesignError) as error:
        write_formal(products["output_directory"], {}, products["report"]["report_id"])
    assert error.value.stage == "output.no_replace"


def test_design_does_not_issue_runtime_or_repeat_audit_authority(products: dict[str, Any]) -> None:
    assert boundary_audit()["old_experiment_imports"] == 0
    assert products["gate_evaluation"]["failed"] == 0
    scope = products["scope"]
    assert scope["Provider_calls"] == scope["new_trajectory_executions"] == 0
    assert scope["semantic_class_witnesses"] == scope["model_owned_decisions_observed"] == 0
    transition = products["transition"]
    assert transition["prospective_next_stage"] == NEXT_CANDIDATE
    assert not transition["next_stage_authorized"]
    assert not transition["repeat_closed_same_task_independent_audit_required"]
