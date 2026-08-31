from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_prompt_authority_repair as repair,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_prompt_authority_repair_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    source_projected_json_prompt_authority_repair_runner as source_runner,
)

ATTACHED_AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/ddcb1eae-087c-4cb6-830f-49c56fafedf9/pasted-text.txt"
)


def _package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _repository() -> Path:
    return _package_root().parent


def _source_commit() -> str:
    return subprocess.run(
        (
            "git",
            "log",
            "-1",
            "--format=%H",
            "--",
            repair.RUNNER_SOURCE_RELATIVE_PATH,
        ),
        cwd=_repository(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, object]]:
    root = tmp_path_factory.mktemp("v26-193")
    output = root / "formal"
    report = source_runner.run_source_projected_repair(
        repo_root=_repository(),
        source_commit=_source_commit(),
        output_dir=output,
        external_audit_path=ATTACHED_AUDIT,
        v192_source_archive_output=root / "v192.tar",
        v179_source_archive_output=root / "v179.tar",
        current_source_archive_output=root / "v193.tar",
    )
    return output, report


def _load(output: Path, name: str) -> dict[str, object]:
    return json.loads((output / name).read_text(encoding="utf-8"))


def test_source_projection_is_archive_executed_and_byte_exact(
    built: tuple[Path, dict[str, object]],
) -> None:
    output, _ = built
    source = models.SourceProjectionAudit.model_validate(
        _load(output, "source_projection_audit.json")
    )
    assert source.audited_v26_192_source_commit == repair.AUDITED_V192_SOURCE_COMMIT
    assert source.audited_v26_192_source_tree == repair.AUDITED_V192_SOURCE_TREE
    assert source.v26_192_formal_file_count == 17
    assert source.v26_192_byte_match_count == 17
    assert source.v26_192_mismatch_count == 0
    assert source.transitive_source_file_count == len(source.transitive_source_files)
    assert source.transitive_source_file_count > 100
    assert not source.caller_supplied_source_identity_trusted


def test_parent_authority_and_exact_prompt_set(
    built: tuple[Path, dict[str, object]],
) -> None:
    output, _ = built
    parent = models.ParentAuthorityAudit.model_validate(
        _load(output, "parent_authority_audit.json")
    )
    evidence = models.ExactPromptEvidenceSet.model_validate(
        _load(output, "exact_prompt_evidence_set.json")
    )
    assert parent.package_source_parent_match_count == 32
    assert parent.job_source_parent_match_count == 192
    assert parent.job_package_parent_match_count == 192
    assert parent.exact_source_job_set_match
    assert len(evidence.rows) == 792
    assert len({row.row_id for row in evidence.rows}) == 792
    assert len({row.coordinate.coordinate_id for row in evidence.rows}) == 792
    assert len({row.coordinate.fresh_job_id for row in evidence.rows}) == 192
    assert all(
        row.prompt_core_sha256 == row.coordinate.expected_prompt_core_sha256
        for row in evidence.rows
    )
    assert all(
        row.invocation_event_sequence == ("render", "body", "validate", "sink")
        for row in evidence.rows
    )
    assert not evidence.complete_model_reachable_state_census_claimed


def test_runner_callsite_totality_has_real_sink_and_no_bypass(
    built: tuple[Path, dict[str, object]],
) -> None:
    output, _ = built
    audit = models.RunnerCallsiteTotalityAudit.model_validate(
        _load(output, "runner_callsite_totality_audit.json")
    )
    assert audit.invoke_method_count == 1
    assert audit.renderer_callsite_count == 1
    assert audit.request_body_builder_callsite_count == 1
    assert audit.transport_sink_callsite_count == 1
    assert audit.bypass_callsite_count == 0
    assert audit.renderer_precedes_request_body_callsite
    assert audit.request_body_precedes_transport_sink_callsite
    assert audit.local_invocation_count == 792
    assert audit.reachability_basis == "source_callsite_totality_not_792_row_exhaustion"


def test_typed_fully_rehashed_attacks_hit_registered_boundaries(
    built: tuple[Path, dict[str, object]],
) -> None:
    output, _ = built
    audit = models.TypedDestructiveAudit.model_validate(
        _load(output, "typed_destructive_audit.json")
    )
    names = {item.attack_name for item in audit.attacks}
    assert audit.attempted_count == 14
    assert audit.rejected_count == 14
    assert audit.accepted_count == 0
    assert audit.exact_type_match_count == 14
    assert audit.exact_stage_match_count == 14
    assert audit.exact_reason_match_count == 14
    assert {
        "duplicated_census_rows_with_preserved_phase_counts",
        "dropped_job_plus_duplicated_replacement",
        "cross_job_prompt_row",
        "cross_job_prompt_core_envelope_body_swap",
        "package_job_parent_swap",
        "source_job_fresh_package_mismatch",
        "manifest_runner_parent_replacement",
        "response_format_body_envelope_mismatch",
        "provider_protocol_extra_field",
        "arbitrary_source_commit_injection",
        "arbitrary_source_tree_injection",
        "action_phase_specific_core_mutation",
        "correction_phase_specific_core_mutation",
        "final_phase_specific_core_mutation",
    } == names
    assert all(item.target_validator_reached and item.fully_rehashed for item in audit.attacks)


def test_result_drift_is_three_way_decomposed_and_fail_closed(
    built: tuple[Path, dict[str, object]],
) -> None:
    output, _ = built
    audit = models.ResultDriftDecompositionAudit.model_validate(
        _load(output, "result_drift_decomposition_audit.json")
    )
    assert audit.compared_result_count == 192
    assert audit.exact_identity_match_count == 144
    assert audit.identity_drift_count == 48
    assert len(audit.witnesses) == 48
    assert audit.v179_snapshot_replay_count == 192
    assert audit.v179_snapshot_old_byte_match_count == 192
    assert audit.v179_snapshot_current_byte_match_count == 144
    assert audit.semantic_event_or_receipt_drift_count == 48
    assert audit.semantic_validity_or_answer_drift_count == 0
    assert all(item.snapshot_matches_old_canonical_bytes for item in audit.witnesses)
    assert not audit.semantic_equivalence_claimed
    assert audit.online_execution_blocked_by_unknown_or_semantic_drift
    assert audit.historical_result_rewrite_count == 0


def test_repair_gates_pass_but_online_and_outcome_authority_remain_blocked(
    built: tuple[Path, dict[str, object]],
) -> None:
    output, report_payload = built
    report = models.RepairReport.model_validate(report_payload)
    static = models.StaticAudit.model_validate(_load(output, "static_audit.json"))
    transition = models.ProspectiveTransition.model_validate(
        _load(output, "prospective_transition.json")
    )
    gap = models.OutcomeAuthorityGapRegister.model_validate(
        _load(output, "outcome_authority_gap_register.json")
    )
    assert static.repair_preflight_gates_passed
    assert static.failed_gate_count == 0
    assert not static.online_execution_gate_passed
    assert report.repair_preflight_gates_passed
    assert not report.online_development_execution_authorized
    assert not transition.online_development_execution_authorized
    assert transition.independent_audit_required
    assert gap.missing_layer_count == 6
    assert not gap.old_v26_186_contract_reused


def test_prompt_coordinate_phase_kind_is_total() -> None:
    base = {
        "coordinate_id": "pending",
        "fresh_job_id": "fresh",
        "source_job_id": "source",
        "runner_package_id": "runner",
        "source_runner_package_id": "source-runner",
        "replica_index": 0,
        "invocation_index": 0,
        "phase": "final",
        "prompt_kind": "action",
        "state_token": "terminal",
        "expected_prompt_core_sha256": "0" * 64,
    }
    with pytest.raises(ValidationError, match="Final Prompt kind"):
        models.PromptCoordinate.model_validate(base)


def test_artifact_manifest_and_no_replace(
    built: tuple[Path, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, _ = built
    manifest = models.ArtifactManifest.model_validate(_load(output, "artifact_manifest.json"))
    assert manifest.file_count == 11
    assert {item.relative_path for item in manifest.members} == {
        path.name for path in output.iterdir() if path.name != "artifact_manifest.json"
    }
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(FileExistsError):
        repair.build(
            package_root=_package_root(),
            output_dir=output,
            external_audit_path=ATTACHED_AUDIT,
            v192_source_archive=output / "unused-v192.tar",
            v179_source_archive=output / "unused-v179.tar",
            current_source_archive=output / "unused-current.tar",
            current_source_commit="0" * 40,
            current_source_tree="0" * 40,
        )
