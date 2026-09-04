# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_subsequent_action_evidence_domain_closure_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_subsequent_action_evidence_domain_closure_preflight as subject,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/145db1ca-b499-4795-b6ba-86db485d7178/pasted-text.txt"
)
FORMAL = ROOT / subject.OUTPUT_DIR


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    assert isinstance(value, dict)
    return value


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _observed(output: Path) -> tuple[dict[str, Any], ...]:
    return tuple(
        _load(path)
        for path in sorted((output / "replay_evidence" / "observed").glob("*.json"))
    )


def _rebuild_evidence(payload: dict[str, Any]) -> models.ObservedEvidence:
    values = dict(payload)
    values.pop("evidence_id", None)
    kind = values.get("evidence_kind")
    if kind == "subsequent_action_parser_rejection":
        return models.make_identity(
            models.ParserSubsequentActionEvidence,
            values,
            field="evidence_id",
            prefix="finance_v26_227_parser_subsequent_action_evidence:",
        )
    if kind == "subsequent_action_reference_failure":
        return models.make_identity(
            models.ReferenceSubsequentActionEvidence,
            values,
            field="evidence_id",
            prefix="finance_v26_227_reference_subsequent_action_evidence:",
        )
    return models.OBSERVED_EVIDENCE_ADAPTER.validate_python(payload)


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, tuple[str, str]]:
    if FORMAL.is_dir():
        source = _load(FORMAL / "source_identity.json")
        source_identity = (str(source["source_commit"]), str(source["source_tree"]))
    else:
        commit = os.environ.get("V26_227_TEST_SOURCE_COMMIT")
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
    output = tmp_path_factory.mktemp("v26_227") / "build"
    subject.build(
        repository_root=ROOT,
        output_dir=output,
        external_review_path=REVIEW,
        source_identity=source_identity,
    )
    return ROOT, output, source_identity


def test_exact_v226_freeze_three_host_rows_and_provider_exclusion(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    authorization = models.ExternalAuthorization.model_validate(
        _load(output / "external_authorization.json")
    )
    freeze = models.V226Freeze.model_validate(_load(output / "v226_freeze.json"))
    host_rows = tuple(
        models.HostFailureRow.model_validate(_load(path))
        for path in sorted((output / "host_failure_rows").glob("*.json"))
    )

    assert authorization.external_review_sha256 == models.EXTERNAL_REVIEW_SHA256
    assert authorization.external_review_byte_count == 13_590
    assert hashlib.sha256(authorization.operator_directive.encode()).hexdigest() == (
        models.OPERATOR_DIRECTIVE_SHA256
    )
    assert authorization.online_execution_authorized is False
    assert (freeze.formal_file_count, freeze.formal_total_byte_count) == (
        3_428,
        99_765_014,
    )
    assert (freeze.complete_job_count, freeze.failure_record_count) == (156, 36)
    assert (freeze.host_failure_count, freeze.unbound_provider_failure_count) == (3, 33)
    assert freeze.host_failure_ordinals == models.HOST_FAILURE_ORDINALS
    assert freeze.host_failure_job_ids == models.HOST_FAILURE_JOB_IDS
    assert freeze.host_failure_record_ids == models.HOST_FAILURE_RECORD_IDS
    assert freeze.historical_terminal_assignment_authorized is False
    assert tuple(row.job_ordinal for row in host_rows) == models.HOST_FAILURE_ORDINALS
    assert tuple(row.failure_record_id for row in host_rows) == models.HOST_FAILURE_RECORD_IDS
    assert tuple(len(row.public_payloads) for row in host_rows) == (3, 3, 2)
    assert all(not row.terminal_evidence_admitted_in_v226 for row in host_rows)
    assert all(not row.historical_terminal_added for row in host_rows)


def test_zero_provider_replay_derives_two_parser_and_one_reference_terminal(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    evidence = tuple(
        models.OBSERVED_EVIDENCE_ADAPTER.validate_python(item)
        for item in _observed(output)
    )
    decisions = tuple(
        models.DispatcherDecision.model_validate(_load(path))
        for path in sorted((output / "replay_evidence" / "decision").glob("*.json"))
    )

    assert tuple(sorted(item.job_ordinal for item in evidence)) == models.HOST_FAILURE_ORDINALS
    assert sum(isinstance(item, models.ParserSubsequentActionEvidence) for item in evidence) == 2
    assert sum(isinstance(item, models.ReferenceSubsequentActionEvidence) for item in evidence) == 1
    assert {item.job_ordinal: len(item.invocation_records) for item in evidence} == {
        6: 3,
        22: 3,
        149: 2,
    }
    assert all(item.phase == "subsequent_action" for item in evidence)
    assert all(item.provider_calls == 0 for item in evidence)
    assert {
        item.job_ordinal: item.terminal_kind for item in decisions
    } == {
        6: models.PARSER_TERMINAL,
        22: models.PARSER_TERMINAL,
        149: models.REFERENCE_TERMINAL,
    }
    assert all(not item.terminal_kind_was_input for item in decisions)
    assert all(not item.terminal_policy_was_input for item in decisions)
    assert all(not item.caller_terminal_was_input for item in decisions)


def test_strict_evidence_rejects_phase_type_cross_job_and_stale_parents(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    by_ordinal = {int(item["job_ordinal"]): item for item in _observed(output)}
    parser_6 = by_ordinal[6]
    parser_22 = by_ordinal[22]
    reference_149 = by_ordinal[149]

    wrong_phase = dict(parser_6)
    wrong_phase["phase"] = "first_action"
    with pytest.raises((ValidationError, ValueError)):
        _rebuild_evidence(wrong_phase)

    wrong_type = dict(reference_149)
    wrong_type.update(
        {
            "evidence_kind": "subsequent_action_parser_rejection",
            "parser_exception_type": "SemanticActionResponseRejection",
            "parser_exception_family": "response_serialization_failure",
            "parser_exception_subtype": "canonical_action_not_exact_four_field_grammar",
            "parser_rejected": True,
        }
    )
    wrong_type.pop("parser_accepted")
    wrong_type.pop("current_reference_valid")
    with pytest.raises((ValidationError, ValueError)):
        _rebuild_evidence(wrong_type)

    cross_job = dict(parser_6)
    cross_records = list(cross_job["invocation_records"])
    cross_records[-1] = parser_22["invocation_records"][-1]
    cross_job["invocation_records"] = cross_records
    with pytest.raises((ValidationError, ValueError)):
        _rebuild_evidence(cross_job)

    stale_state = dict(parser_6)
    stale_state["current_state_id"] = parser_6["invocation_records"][0]["current_state_id"]
    stale_state["observed_state_id"] = stale_state["current_state_id"]
    with pytest.raises((ValidationError, ValueError)):
        _rebuild_evidence(stale_state)

    stale_candidates = dict(reference_149)
    stale_candidates["current_candidate_action_ids"] = tuple(
        reference_149["invocation_records"][0]["candidate_action_ids"]
    )
    with pytest.raises((ValidationError, ValueError)):
        _rebuild_evidence(stale_candidates)


def test_all_eight_negative_controls_include_full_rehash_rejection(
    built: tuple[Path, Path, tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output, _ = built
    audit = models.NegativeAudit.model_validate(
        _load(output / "negative_control_audit.json")
    )
    assert audit.control_names == models.NEGATIVE_CONTROL_NAMES
    assert (audit.attempted_count, audit.rejected_count, audit.accepted_count) == (8, 8, 0)
    assert audit.rejected_before_raw_write_count == 8
    assert audit.fully_rehashed_attack_count == 1
    assert audit.fully_rehashed_five_layer_identity_count == 5
    assert audit.historical_v226_write_count == 0
    assert audit.provider_calls == 0

    authorization = models.ExternalAuthorization.model_validate(
        _load(output / "external_authorization.json")
    )
    frozen = subject._verify_v226(  # noqa: SLF001
        repository_root=repository,
        external_authorization_id=authorization.authorization_id,
    )
    binding = models.DispatcherBinding.model_validate(
        _load(output / "dispatcher_binding.json")
    )
    controls = models.ControlAudit.model_validate(
        _load(output / "control_audit.json")
    ).controls
    authority = subject.ReplayEvidenceAuthority(
        tuple(item.host_failure.row_id for item in controls)
    )
    for control in controls:
        authority.observe(control.evidence)
    created_layer_sets: list[tuple[str, ...]] = []
    actual_five_layers = subject._five_layers  # noqa: SLF001

    def observe_five_layers(**kwargs: Any) -> models.FiveLayerArtifacts:
        result = actual_five_layers(**kwargs)
        created_layer_sets.append(
            tuple(
                item.artifact_id
                for item in (
                    result.raw,
                    result.result,
                    result.trace,
                    result.outcome,
                    result.checkpoint,
                )
            )
        )
        return result

    monkeypatch.setattr(subject, "_five_layers", observe_five_layers)
    repeated = subject._negative_audit(  # noqa: SLF001
        authorization_id=authorization.authorization_id,
        freeze=frozen,
        source_identity_id=controls[0].source_identity_id,
        dispatcher=subject.SubsequentActionDispatcher(binding, authority),
        controls=controls,
    )
    assert repeated == audit
    assert len(created_layer_sets) == 1
    assert len(set(created_layer_sets[0])) == 5


def test_three_fresh_five_layer_chains_are_nonempirical(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = models.ControlAudit.model_validate(_load(output / "control_audit.json"))
    assert (audit.exact_host_failure_count, audit.derived_terminal_count) == (3, 3)
    assert (audit.parser_control_count, audit.reference_control_count) == (2, 1)
    assert audit.five_layer_artifact_count == 15
    assert (audit.exception_escape_count, audit.empirical_row_count, audit.provider_calls) == (
        0,
        0,
        0,
    )

    layer_files = tuple(
        path
        for prefix in ("raw", "result", "trace", "outcome")
        for path in sorted((output / "replay_evidence" / prefix).glob("*.json"))
    ) + tuple(sorted((output / "replay_checkpoints").glob("*.json")))
    layers = tuple(models.LayerArtifact.model_validate(_load(path)) for path in layer_files)
    assert len(layers) == 15
    assert {item.layer_kind for item in layers} == set(models.LAYER_KINDS)
    assert all(item.historical_v226_artifact is False for item in layers)
    assert all(item.formal_empirical_row is False for item in layers)
    assert all(item.provider_calls == 0 for item in layers)
    assert len({item.artifact_id for item in layers}) == 15


def test_scope_has_no_provider_credential_or_online_authority(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    scope = models.ScopeAudit.model_validate(_load(output / "scope_boundary_audit.json"))
    decision = models.Decision.model_validate(_load(output / "decision.json"))
    transition = models.Transition.model_validate(_load(output / "prospective_transition.json"))
    assert scope.exact_replayed_host_failure_count == 3
    assert scope.provider_calls == scope.provider_client_constructions == 0
    assert scope.credential_lookups == 0
    assert scope.historical_v226_artifact_writes == 0
    assert scope.historical_outcome_backfills == 0
    assert scope.empirical_rows == scope.empirical_estimates == 0
    assert scope.online_authorizations_created == 0
    assert decision.provider_failure_terminalization_completed is False
    assert decision.independent_audit_required is True
    assert decision.online_execution_authorized is False
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.provider_failure_authority_remains_separate is True
    assert transition.fresh_online_authorization_required_after_independent_audit is True
    assert transition.provider_execution_authorized is False


def test_complete_empty_directory_second_build_is_byte_identical(
    built: tuple[Path, Path, tuple[str, str]], tmp_path: Path
) -> None:
    repository, output, source_identity = built
    rebuilt = tmp_path / "empty" / "rebuilt"
    subject.build(
        repository_root=repository,
        output_dir=rebuilt,
        external_review_path=REVIEW,
        source_identity=source_identity,
    )
    assert _files(rebuilt) == _files(output)


def test_manifest_is_self_excluding_and_decision_transition_are_bound(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    manifest = models.ArtifactManifest.model_validate(_load(output / "artifact_manifest.json"))
    gates = models.GateEvaluation.model_validate(_load(output / "gate_evaluation.json"))
    decision = models.Decision.model_validate(_load(output / "decision.json"))
    transition = models.Transition.model_validate(_load(output / "prospective_transition.json"))
    report = models.Report.model_validate(_load(output / "report.json"))
    actual = _files(output)

    assert manifest.self_excluding is True
    assert manifest.manifest_relative_path not in {item.relative_path for item in manifest.members}
    assert manifest.file_count == len(actual) - 1
    assert manifest.total_member_bytes == sum(
        len(payload) for path, payload in actual.items() if path != "artifact_manifest.json"
    )
    for member in manifest.members:
        payload = actual[member.relative_path]
        assert member.sha256 == hashlib.sha256(payload).hexdigest()
        assert member.byte_count == len(payload)
    assert (gates.passed_count, gates.failed_count) == (8, 0)
    assert tuple(item.gate_name for item in gates.gates) == models.GATE_NAMES
    assert decision.decision == models.DECISION_VALUE
    assert transition.decision_id == decision.decision_id
    assert transition.gate_evaluation_id == gates.evaluation_id
    assert report.decision_id == decision.decision_id
    assert report.transition_id == transition.transition_id
    assert report.gate_evaluation_id == gates.evaluation_id
    assert report.unbound_provider_failure_count_remaining == 33
    assert report.provider_calls == report.credential_lookups == report.empirical_rows == 0
