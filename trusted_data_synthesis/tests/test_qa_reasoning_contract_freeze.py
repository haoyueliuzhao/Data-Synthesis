from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.experiments.qa_reasoning_contract_freeze import models
from trusted_synthesis.experiments.qa_reasoning_contract_freeze.contracts import (
    quotient_signature,
)
from trusted_synthesis.experiments.qa_reasoning_contract_freeze.preflight import (
    build_finance_qa_reasoning_contract_freeze,
    write_finance_qa_reasoning_contract_freeze_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/d8560719-12ec-4185-81fb-e81ccebdb320/pasted-text.txt"
)


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", "-C", str(ROOT), *arguments),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def products() -> models.Products:
    return build_finance_qa_reasoning_contract_freeze(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=_git("rev-parse", "HEAD"),
        source_tree=_git("rev-parse", "HEAD^{tree}"),
    )


def test_exact_external_decision_and_negative_predecessor_freeze(
    products: models.Products,
) -> None:
    review = REVIEW.read_bytes()
    assert len(review) == 30_082
    assert hashlib.sha256(review).hexdigest() == models.EXTERNAL_REVIEW_SHA256
    assert products.external_review_bytes == review
    assert products.operator_directive_bytes == models.OPERATOR_DIRECTIVE.encode()
    freeze = products.predecessor_freeze
    assert (freeze["file_count"], freeze["total_bytes"]) == (24, 784_989)
    assert (freeze["manifest_member_count"], freeze["manifest_member_bytes"]) == (
        23,
        781_444,
    )
    assert freeze["manifest_id"] == models.PREDECESSOR_MANIFEST_ID
    assert freeze["artifact_root"] == models.PREDECESSOR_ROOT_ID
    assert freeze["accepted_as_valid_negative_result"] is True
    assert freeze["current_stage_rerun_required"] is False
    assert freeze["formal_artifact_rewrite_performed"] is False


def test_three_scope_clarifications_are_exact(products: models.Products) -> None:
    clarification = products.scope_clarification
    assert tuple(row["subject"] for row in clarification["clarifications"]) == (
        "target_evidence_absence",
        "g6_coverage",
        "semantic_operation_depth",
    )
    assert clarification["archive_bindings_are_distinct_task_instances"] is True
    assert clarification["same_task_multitrajectory_support_established"] is False
    assert clarification["predecessor_formal_bytes_modified"] is False


def test_exact_source_and_ten_contract_descriptors(products: models.Products) -> None:
    binding = products.source_binding
    assert binding["resolved_commit"] == _git("rev-parse", "HEAD")
    assert binding["resolved_tree"] == _git("rev-parse", "HEAD^{tree}")
    assert binding["member_count"] == len(models.SOURCE_PATHS) == 4
    assert all(row["committed_current_bytes_equal"] for row in binding["members"])
    assert len(products.contract_descriptors) == 10
    assert tuple(item.name for item in products.contract_descriptors) == models.CONTRACT_NAMES
    assert len({item.contract_id for item in products.contract_descriptors}) == 10


def test_answer_oracle_and_reasoning_graph_are_separate(products: models.Products) -> None:
    oracle = products.answer_oracle_binding
    graph = products.critical_decision_graph
    assert oracle.is_answer_correctness_oracle_only is True
    assert oracle.prescribes_unique_reasoning_path is False
    assert graph.answer_oracle_program_binding_id == oracle.binding_id
    assert graph.allows_multiple_valid_orders is True
    assert graph.language_realization_is_authority is False
    assert all(item.counterfactual_intervention_ids for item in graph.obligations if item.required)


def test_public_preaction_temporal_chain_is_complete(products: models.Products) -> None:
    state0 = products.initial_state
    envelope = products.reasoning_action
    execution = products.action_execution
    observation = products.observation
    update = products.observation_update
    state1 = products.next_state
    assert envelope.state_id == state0.state_id == execution.state_id == observation.state_id
    assert envelope.preaction_commit_sequence < execution.execution_sequence
    assert execution.parent_envelope_id == envelope.envelope_id
    assert execution.action_id == envelope.selected_action_id
    assert observation.parent_execution_id == execution.execution_id
    assert update.parent_reasoning_action_id == envelope.envelope_id
    assert update.action_execution_id == execution.execution_id
    assert update.observation_id == observation.observation_id
    assert update.next_state_id == state1.state_id
    assert state1.sequence_index == 1
    assert envelope.private_chain_of_thought_present is False
    assert state0.private_reasoning_content_present is False


def test_answer_and_trajectory_validity_are_noncompensatory(
    products: models.Products,
) -> None:
    assert products.answer_validity.qa_valid is True
    assert products.trajectory_validity.trajectory_valid is True
    assert products.qualification.qualified is True
    assert products.qualification.qa_valid and products.qualification.trajectory_valid
    trajectory = products.reasoning_trajectory
    required = {
        item.decision_id for item in products.critical_decision_graph.obligations if item.required
    }
    assert required <= set(trajectory.covered_decision_ids)
    assert quotient_signature(trajectory).startswith("reasoning_trajectory_quotient_state:")


def test_target_depth_and_coverage_contracts_are_narrow(products: models.Products) -> None:
    target = products.target_contract
    assert set(target.allowed_modalities) == {"management_target", "company_guidance"}
    assert set(target.forbidden_modalities) == {
        "observed_actual",
        "analyst_consensus",
        "peer_benchmark",
        "arbitrary_constant",
        "derived_margin",
    }
    metrics = products.depth_metrics
    assert (
        metrics.semantic_operation_depth,
        metrics.reasoning_depth,
        metrics.evidence_integration_depth,
        metrics.correction_depth,
    ) == (3, 1, 2, 0)
    assert metrics.critical_decision_coverage == 1.0
    assert metrics.metrics_noninterchangeable is True
    assert metrics.token_count_used_as_depth is False
    matrix = products.coverage_matrix
    assert len(matrix.axis_values) == 8
    assert len(matrix.minimum_constructive_cells) == 4
    assert matrix.coverage_measured is False
    assert matrix.benchmark_frequency_claimed is False


def test_ten_direct_contract_attacks_reject(products: models.Products) -> None:
    audit = products.negative_audit
    assert tuple(row["name"] for row in audit["controls"]) == models.ATTACK_NAMES
    assert (audit["attempted_count"], audit["rejected_count"], audit["accepted_count"]) == (
        10,
        10,
        0,
    )
    assert all(row["rejected"] for row in audit["controls"])
    assert all(row["output_writes"] == row["provider_calls"] == 0 for row in audit["controls"])


def test_gate_decision_transition_and_scope_are_exact(products: models.Products) -> None:
    assert (products.gate["passed_count"], products.gate["failed_count"]) == (8, 0)
    assert all(products.gate["gates"].values())
    assert products.decision["decision"] == models.DECISION
    assert products.decision["fixed_fixture_constructibility_established"] is False
    assert products.decision["archive_grounded_reasoning_trajectory_established"] is False
    assert products.decision["model_capability_established"] is False
    assert products.transition["next_stage"] == models.NEXT_STAGE
    assert products.transition["next_stage_authorized"] is True
    assert products.transition["independent_audit_only"] is True
    scope = products.scope_audit
    assert not any(
        scope[key]
        for key in (
            "predecessor_formal_writes",
            "archive_reads",
            "archive_expansions",
            "provider_calls",
            "credential_lookups",
            "gpu_jobs",
            "online_jobs",
            "model_responses",
            "fixed_fixture_qa_executions",
            "empirical_rows",
            "benchmark_distribution_rows",
            "task_registrations",
            "operation_registrations",
            "catalog_promotions",
            "qa_release_objects",
            "mapper_rows",
            "state_rows",
            "contribution_rows",
            "vtdo_rows",
            "training_rows",
            "production_rows",
        )
    )


def test_artifacts_are_reproducible_and_self_excluding(
    products: models.Products, tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_finance_qa_reasoning_contract_freeze_artifacts(products, left)
    write_finance_qa_reasoning_contract_freeze_artifacts(products, right)
    assert _files(left) == _files(right)
    files = _files(left)
    manifest = json.loads(files["artifact_manifest.json"])
    assert manifest["self_excluding"] is True
    assert manifest["file_count"] == len(manifest["members"]) == len(files) - 1
    for row in manifest["members"]:
        payload = files[row["relative_path"]]
        assert row["byte_count"] == len(payload)
        assert row["sha256"] == hashlib.sha256(payload).hexdigest()


def test_changed_external_review_rejects(tmp_path: Path) -> None:
    changed = tmp_path / "changed.txt"
    changed.write_bytes(REVIEW.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="external reasoning-bearing QA audit bytes differ"):
        build_finance_qa_reasoning_contract_freeze(
            repo_root=ROOT,
            external_audit_path=changed,
            source_commit=_git("rev-parse", "HEAD"),
            source_tree=_git("rev-parse", "HEAD^{tree}"),
        )
