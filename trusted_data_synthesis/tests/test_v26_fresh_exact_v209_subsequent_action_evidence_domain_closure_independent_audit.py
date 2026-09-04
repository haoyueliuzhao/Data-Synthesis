# ruff: noqa: E501, SLF001
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_subsequent_action_evidence_domain_closure_independent_audit as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_subsequent_action_evidence_domain_closure_independent_audit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)

ROOT = Path(__file__).resolve().parents[2]
ATTACHED_REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/7962601e-c573-4534-aea8-b4b62d5f480f/pasted-text.txt"
)
REVIEW_SHA256 = "69aaedaadd50882f5ba154ebd6d86fe87b239dfc75676d529d1dbd7f3bb02e94"
DIRECTIVE_SHA256 = "8e30b645e46c5682c61a1e4ca820e51aa5c8b07bfa052274b665ebd20afd33fa"


def _formal_dir() -> Path:
    direct = ROOT / subject.OUTPUT_DIR
    nested = ROOT / "trusted_data_synthesis" / subject.OUTPUT_DIR
    return direct if direct.is_dir() or not nested.is_dir() else nested


def _review_path() -> Path:
    explicit = os.environ.get("V26_228_EXTERNAL_REVIEW")
    formal = _formal_dir() / "external_review.txt"
    path = Path(explicit) if explicit else (formal if formal.is_file() else ATTACHED_REVIEW)
    if not path.is_file():
        pytest.skip("exact v26.228 external review is unavailable")
    return path


def _load(root: Path, relative_path: str) -> dict[str, Any]:
    value = json.loads((root / relative_path).read_bytes())
    assert isinstance(value, dict)
    return value


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    formal = _formal_dir()
    if formal.is_dir() and (formal / "source_identity.json").is_file():
        source = _load(formal, "source_identity.json")
        source_identity = (str(source["source_commit"]), str(source["source_tree"]))
    else:
        commit = os.environ.get("V26_228_TEST_SOURCE_COMMIT")
        if commit is None:
            commit = subprocess.run(
                ("git", "rev-parse", "HEAD"),
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        tree = subprocess.run(
            ("git", "rev-parse", f"{commit}^{{tree}}"),
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        source_identity = (commit, tree)
    output = tmp_path_factory.mktemp("v26-228") / "formal"
    subject.build(
        repository_root=ROOT,
        output_dir=output,
        external_review_path=_review_path(),
        source_identity=source_identity,
    )
    return output


def test_exact_review_directive_and_saved_bytes(built: Path) -> None:
    authorization = models.ExternalAuthorization.model_validate(
        _load(built, "external_authorization.json")
    )
    review = (built / "external_review.txt").read_bytes()
    directive = (built / "operator_directive.txt").read_bytes()
    assert len(review) == models.EXTERNAL_REVIEW_BYTE_COUNT == 15_519
    assert hashlib.sha256(review).hexdigest() == authorization.external_review_sha256
    assert authorization.external_review_sha256 == models.EXTERNAL_REVIEW_SHA256 == REVIEW_SHA256
    assert directive == models.OPERATOR_DIRECTIVE.encode("utf-8")
    assert len(directive) == authorization.operator_directive_byte_count == 30
    assert hashlib.sha256(directive).hexdigest() == authorization.operator_directive_sha256
    assert (
        authorization.operator_directive_sha256
        == models.OPERATOR_DIRECTIVE_SHA256
        == DIRECTIVE_SHA256
    )
    assert authorization.consumed_stage == models.CONSUMED_STAGE
    assert authorization.provider_calls_authorized == 0
    assert authorization.online_execution_authorized is False


def test_exact_v227_freeze_and_manifest_geometry(built: Path) -> None:
    freeze = models.V227FreezeAudit.model_validate(_load(built, "v227_freeze_audit.json"))
    v227_manifest = (
        ROOT
        / "trusted_data_synthesis"
        / "artifacts"
        / "vtdo_experiment"
        / models.V227_RUN_ID
        / "artifact_manifest.json"
    ).read_bytes()
    assert hashlib.sha256(v227_manifest).hexdigest() == (
        "4d6f2b2dd58e2cc7c2e0e44be3c4522ecce539819a2f4bf256a9964348c65210"
    )
    assert freeze.run_id == models.V227_RUN_ID
    assert (freeze.source_commit, freeze.source_tree) == (
        models.V227_SOURCE_COMMIT,
        models.V227_SOURCE_TREE,
    )
    assert (freeze.file_count, freeze.total_bytes) == (38, 3_715_790)
    assert (freeze.manifest_member_count, freeze.manifest_member_bytes) == (
        37,
        3_708_807,
    )
    assert freeze.manifest_id == models.V227_MANIFEST_ID
    assert freeze.artifact_root == models.V227_ARTIFACT_ROOT
    assert freeze.decision_id == models.V227_DECISION_ID
    assert freeze.transition_id == models.V227_TRANSITION_ID
    assert (freeze.path_matches, freeze.sha256_matches, freeze.byte_count_matches) == (
        38,
        37,
        37,
    )
    assert freeze.passed
    assert not freeze.candidate_report_used_as_oracle
    assert not freeze.candidate_gate_used_as_oracle
    assert not freeze.candidate_control_audit_used_as_oracle
    assert not freeze.candidate_negative_audit_used_as_oracle
    assert not freeze.candidate_saved_evidence_used_as_replay_input
    assert not freeze.candidate_host_rows_used_as_source_selection


def test_v26_228_source_and_independent_implementation_are_byte_bound(
    built: Path,
) -> None:
    source = models.SourceIdentity.model_validate(_load(built, "source_identity.json"))
    implementation = models.ImplementationBinding.model_validate(
        _load(built, "implementation_binding.json")
    )
    actual_tree = subprocess.run(
        ("git", "rev-parse", f"{source.source_commit}^{{tree}}"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert actual_tree == source.source_tree
    assert source.working_tree_byte_matches == 2
    assert tuple(row.relative_path for row in source.implementation_members) == tuple(
        sorted((subject.MODELS_FILE, subject.AUDIT_FILE))
    )
    for member in source.implementation_members:
        working = (ROOT / member.relative_path).read_bytes()
        committed = subprocess.run(
            ("git", "show", f"{source.source_commit}:{member.relative_path}"),
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert working == committed
        assert hashlib.sha256(working).hexdigest() == member.sha256
        assert len(working) == member.byte_count
    assert implementation.source_identity_id == source.source_identity_id
    assert implementation.implementation_files == tuple(
        sorted((subject.MODELS_FILE, subject.AUDIT_FILE))
    )
    assert len(implementation.required_independent_symbols) >= 8
    assert implementation.v227_control_helper_calls == 0
    assert implementation.v227_attack_helper_calls == 0
    assert implementation.v227_report_oracle_calls == 0
    assert implementation.v227_gate_oracle_calls == 0
    assert implementation.network_symbols == implementation.credential_symbols == 0


def test_independent_helper_boundary_keeps_local_replay_and_excludes_v227_helpers(
    built: Path,
) -> None:
    implementation = models.ImplementationBinding.model_validate(
        _load(built, "implementation_binding.json")
    )
    assert "_independent_replay" in implementation.required_independent_symbols
    tree = ast.parse((ROOT / subject.AUDIT_FILE).read_text(encoding="utf-8"))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(
        item.endswith("subsequent_action_evidence_domain_closure_preflight") for item in imports
    )
    assert implementation.v227_control_helper_calls == 0
    assert implementation.v227_attack_helper_calls == 0


@pytest.mark.parametrize(
    "field",
    (
        "exact_response_parsed",
        "current_state_and_candidate_or_final_envelope_valid",
        "runtime_step_or_finalize_completed",
    ),
)
def test_evidence_derivation_rejects_unsuccessful_earlier_prefix(built: Path, field: str) -> None:
    del built  # the fixture initializes the audit's frozen comparison parents
    v227 = ROOT / "trusted_data_synthesis" / "artifacts" / "vtdo_experiment" / models.V227_RUN_ID
    host = _load(v227, "host_failure_rows/job_006.json")
    observed_files = tuple((v227 / "replay_evidence" / "observed").glob("*.json"))
    observed = next(
        _load(path.parent.parent.parent, path.relative_to(path.parent.parent.parent).as_posix())
        for path in observed_files
        if _load(path.parent.parent.parent, path.relative_to(path.parent.parent.parent).as_posix())[
            "job_ordinal"
        ]
        == 6
    )
    record_payloads = list(observed["invocation_records"])
    first_values = dict(record_payloads[0])
    first_values.pop("invocation_id")
    first_values[field] = False
    first = v209_models.make_identity(
        v209_models.ExecutableInvocationRecord,
        first_values,
        field="invocation_id",
        prefix="fresh_repaired_final_continuity_executable_invocation_record:",
    )
    records = (
        first,
        *(
            v209_models.ExecutableInvocationRecord.model_validate(row)
            for row in record_payloads[1:]
        ),
    )
    with pytest.raises(ValueError):
        subject._derive_evidence(
            host,
            records,
            _load(v227, "external_authorization.json"),
            _load(v227, "source_identity.json"),
            subject._registry_policies(ROOT),
        )


def test_negative_controls_use_actual_earlier_parents_and_rehash_public_payload() -> None:
    host_source = inspect.getsource(subject._host_dict)
    negative_source = inspect.getsource(subject._negative_controls)
    assert "job_ordinal in" not in host_source
    assert 'value["invocation_records"][0]' in negative_source
    assert '"current_state_id"' in negative_source
    assert '"candidate_action_ids"' in negative_source
    assert '"-stale"' not in negative_source
    assert '"stale-candidate"' not in negative_source
    assert 'value["public_payload"]' in negative_source
    assert 'value["public_payload_sha256"]' in negative_source
    assert 'last["public_response_sha256"]' in negative_source


def test_detached_source_rebuild_matches_all_v227_bytes(built: Path) -> None:
    audit = models.DetachedRebuildAudit.model_validate(_load(built, "detached_rebuild_audit.json"))
    assert audit.archived_source_files == 694
    assert (audit.saved_file_count, audit.rebuilt_file_count) == (38, 38)
    assert (audit.saved_bytes, audit.rebuilt_bytes) == (3_715_790, 3_715_790)
    assert (
        audit.path_matches,
        audit.sha256_matches,
        audit.actual_byte_matches,
        audit.manifest_members_revalidated,
    ) == (38, 38, 38, 37)
    assert audit.credential_like_environment_keys == audit.credential_lookups == 0
    assert audit.provider_calls == 0
    assert audit.passed


def test_independent_three_host_and_thirty_three_provider_source_partition(
    built: Path,
) -> None:
    audit = models.SourcePartitionAudit.model_validate(_load(built, "source_partition_audit.json"))
    assert audit.host_ordinals == models.HOST_ORDINALS == (6, 22, 149)
    assert tuple(row.ordinal for row in audit.host_rows) == (6, 22, 149)
    assert tuple(row.provider_call_count for row in audit.host_rows) == (3, 3, 2)
    assert all(row.failure_kind == "host_failure" for row in audit.host_rows)
    assert all(len(row.provider_call_ids) == row.provider_call_count for row in audit.host_rows)
    assert audit.host_source_set_sha256 == (
        "dbecba00270f755044c2293ba103ed647b977cf2530af508e0515042cab8d33c"
    )
    assert audit.exclusion_count == 33
    assert audit.exclusion_failure_kind == "unbound_provider_failure"
    assert audit.exclusion_exact_kind_count == 33
    assert audit.exclusion_set_sha256 == (
        "d9243f618f547da83cae5e6698d3155030b3065058cf5372b8171bf013d3d3f0"
    )
    assert audit.exact_set_equality
    assert audit.v227_control_audit_helper_calls == 0
    assert audit.provider_calls == 0


def test_independent_eight_call_replay_binds_order_hashes_state_and_candidates(
    built: Path,
) -> None:
    audit = models.ReplayAndDerivationAudit.model_validate(
        _load(built, "replay_and_derivation_audit.json")
    )
    assert tuple(row.ordinal for row in audit.rows) == (6, 22, 149)
    assert tuple(row.invocation_count for row in audit.rows) == (3, 3, 2)
    assert audit.invocation_count == 8
    assert audit.request_hash_match_count == audit.response_hash_match_count == 8
    assert audit.replay_descriptor_request_hash_matches == 8
    assert audit.replay_descriptor_response_hash_matches == 8
    assert audit.descriptor_metadata_request_hash_matches == 8
    assert audit.descriptor_metadata_response_hash_matches == 8
    assert audit.provider_call_id_matches == 8
    assert audit.call_ordinal_matches == 8
    assert audit.successful_status_matches == 8
    assert sum(row.request_match_count for row in audit.rows) == 8
    assert sum(row.response_match_count for row in audit.rows) == 8
    assert all(row.call_order_match and row.success_status_match for row in audit.rows)
    assert all(row.last_state_id and row.last_candidate_action_ids for row in audit.rows)
    assert all(row.phases[0] == "first_action" for row in audit.rows)
    assert all(row.phases[-1] == "subsequent_action" for row in audit.rows)
    assert audit.v227_replay_helper_calls == 0


def test_independent_evidence_and_terminal_derivation_is_two_one_and_three_three(
    built: Path,
) -> None:
    audit = models.ReplayAndDerivationAudit.model_validate(
        _load(built, "replay_and_derivation_audit.json")
    )
    assert (
        audit.parser_evidence_count,
        audit.reference_evidence_count,
        audit.derived_terminal_count,
        audit.subsequent_action_phase_count,
    ) == (2, 1, 3, 3)
    assert Counter(row.evidence_kind for row in audit.rows) == {
        "subsequent_action_parser_rejection": 2,
        "subsequent_action_reference_failure": 1,
    }
    assert {row.ordinal: row.derived_terminal for row in audit.rows} == {
        6: "first_response_abi_invalid",
        22: "first_response_abi_invalid",
        149: "first_action_reference_invalid",
    }
    assert all(row.phase == "subsequent_action" for row in audit.rows)
    assert all(row.terminal_policy_id and row.derivation_rule for row in audit.rows)
    registry_path = (
        ROOT
        / "trusted_data_synthesis"
        / "artifacts"
        / "vtdo_experiment"
        / "finance_v26_195_fresh_artifact_backed_outcome_authority_preflight_v1_20260901"
        / "fresh_terminal_registry.json"
    )
    registry_bytes = registry_path.read_bytes()
    registry = json.loads(registry_bytes)
    assert hashlib.sha256(registry_bytes).hexdigest() == (
        "810edea998d24a8c3224a1d378ce2cce76dfc405e62c5b8f2908ca815035b617"
    )
    assert registry["registry_id"] == (
        "fresh_kernel_terminal_registry:a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
    )
    reachable = {
        row["terminal_kind"]: row["policy_id"]
        for row in registry["policies"]
        if row["registration_status"] == "reachable"
    }
    assert {row.derived_terminal: row.terminal_policy_id for row in audit.rows} == {
        "first_response_abi_invalid": reachable["first_response_abi_invalid"],
        "first_action_reference_invalid": reachable["first_action_reference_invalid"],
    }
    assert len({row.evidence_id for row in audit.rows}) == 3
    assert len({row.decision_id for row in audit.rows}) == 3
    assert audit.saved_evidence_byte_matches == 3
    assert audit.detached_evidence_byte_matches == 3
    assert audit.saved_decision_byte_matches == 3
    assert audit.detached_decision_byte_matches == 3
    assert audit.v227_evidence_helper_calls == 0
    assert audit.terminal_registry_id == models.TERMINAL_REGISTRY_ID
    assert audit.terminal_registry_file_sha256 == models.TERMINAL_REGISTRY_FILE_SHA256
    assert audit.reachable_policy_match_count == 3


def test_fifteen_layers_are_independently_reconstructed_byte_exact(built: Path) -> None:
    audit = models.LayerReconstructionAudit.model_validate(
        _load(built, "layer_reconstruction_audit.json")
    )
    assert len(audit.layers) == audit.layer_count == 15
    assert Counter(row.layer_kind for row in audit.layers) == {
        "raw": 3,
        "result": 3,
        "trace": 3,
        "outcome": 3,
        "checkpoint": 3,
    }
    assert audit.identity_matches == audit.actual_byte_matches == 15
    assert audit.saved_actual_byte_matches == 15
    assert audit.detached_actual_byte_matches == 15
    assert audit.raw_before_result_checks == 3
    assert all(
        row.actual_byte_match
        and row.saved_actual_byte_match
        and row.detached_actual_byte_match
        and not row.formal_empirical_row
        for row in audit.layers
    )
    assert len({row.artifact_id for row in audit.layers}) == 15
    assert audit.v227_layer_helper_calls == 0
    assert audit.empirical_rows == audit.provider_calls == 0


def test_eight_attacks_record_actual_rejection_diagnostics(built: Path) -> None:
    audit = models.NegativeControlAudit.model_validate(_load(built, "negative_control_audit.json"))
    assert tuple(row.name for row in audit.results) == models.NEGATIVE_CONTROL_NAMES
    assert (audit.attacks, audit.rejected, audit.accepted) == (8, 8, 0)
    assert audit.rejected_before_raw == 8
    assert audit.fully_rehashed_candidate_layers == 5
    assert audit.fully_rehashed_terminal_invocations == 1
    assert audit.fully_rehashed_evidence_objects == 1
    assert audit.fully_rehashed_decision_objects == 1
    assert audit.fully_rehashed_authority_rejections == 1
    assert all(row.rejected and row.exception_type and row.rejection_stage for row in audit.results)
    assert all(len(row.reason_sha256) == 64 for row in audit.results)
    assert all(row.raw_writes == 0 for row in audit.results)
    assert sum(row.candidate_rehashed_layers for row in audit.results) == 5
    full_rehash = audit.results[6]
    assert full_rehash.name == "fully_rehashed_evidence_and_five_layers_forged"
    assert full_rehash.rejection_stage == "admission.replay_owned_bytes"
    assert full_rehash.candidate_rehashed_layers == 5
    assert audit.v227_attack_helper_calls == 0
    assert audit.provider_calls == 0


def test_zero_scope_gate_decision_and_next_stage_boundary(built: Path) -> None:
    scope = models.ScopeBoundaryAudit.model_validate(_load(built, "scope_boundary_audit.json"))
    gate = models.GateEvaluation.model_validate(_load(built, "gate_evaluation.json"))
    decision = models.Decision.model_validate(_load(built, "decision.json"))
    transition = models.Transition.model_validate(_load(built, "prospective_transition.json"))
    report = models.Report.model_validate(_load(built, "report.json"))
    assert all(
        value == 0
        for value in (
            scope.provider_calls,
            scope.credential_lookups,
            scope.client_constructions,
            scope.empirical_rows,
            scope.online_authorizations,
            scope.qa_reads,
            scope.mapper_rows,
            scope.state_rows,
            scope.frequency_rows,
            scope.contribution_rows,
            scope.vtdo_rows,
            scope.historical_v226_writes,
        )
    )
    assert tuple(row.name for row in gate.gates) == models.GATE_NAMES
    assert (gate.passed_count, gate.failed_count) == (7, 0)
    assert gate.noncompensatory
    assert decision.decision == report.decision == models.DECISION_VALUE
    assert not decision.online_execution_authorized
    assert not decision.provider_failure_recovery_authorized
    assert not decision.empirical_estimation_authorized
    assert transition.next_stage == models.NEXT_STAGE
    assert not transition.next_stage_authorized
    assert transition.separate_external_audit_decision_required
    assert not transition.online_execution_authorized
    assert not report.online_execution_authorized


def test_manifest_and_second_build_are_byte_identical(built: Path, tmp_path: Path) -> None:
    manifest = models.ArtifactManifest.model_validate(_load(built, "artifact_manifest.json"))
    actual = _files(built)
    assert manifest.self_excluding
    assert manifest.manifest_relative_path not in {
        member.relative_path for member in manifest.members
    }
    assert manifest.file_count == len(actual) - 1
    assert manifest.total_member_bytes == sum(
        len(payload)
        for relative_path, payload in actual.items()
        if relative_path != manifest.manifest_relative_path
    )
    for member in manifest.members:
        payload = actual[member.relative_path]
        assert member.sha256 == hashlib.sha256(payload).hexdigest()
        assert member.byte_count == len(payload)

    source = _load(built, "source_identity.json")
    rebuilt = tmp_path / "empty" / "rebuilt"
    subject.build(
        repository_root=ROOT,
        output_dir=rebuilt,
        external_review_path=_review_path(),
        source_identity=(str(source["source_commit"]), str(source["source_tree"])),
    )
    assert _files(rebuilt) == actual


def test_source_identity_mismatch_rejects_without_output(built: Path, tmp_path: Path) -> None:
    source = _load(built, "source_identity.json")
    output = tmp_path / "source-mismatch"
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        subject.build(
            repository_root=ROOT,
            output_dir=output,
            external_review_path=_review_path(),
            source_identity=(str(source["source_commit"]), "0" * 40),
        )
    assert not output.exists()
