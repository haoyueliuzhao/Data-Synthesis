# ruff: noqa: E501
from __future__ import annotations

import argparse
import ast
import json
import subprocess
from pathlib import Path
from typing import Any, NoReturn, cast

from pydantic import BaseModel

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_population_independent_audit_models as v230_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_source_authority_recovery_population_preflight_models as v229_models,
)

RUN_ID = models.RUN_ID
V229_RUN_ID = "finance_v26_229_fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_v1_20260904"
V230_RUN_ID = "finance_v26_230_fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_independent_audit_v1_20260904"
V209_RUN_ID = "finance_v26_209_fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_repair_preflight_v1_20260902"
DIRECTIVE = "参照审计报告继续实验".encode()
SOURCE_PATHS = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_models.py",
)
REQUIRED_SYMBOLS = tuple(
    sorted(
        (
            "_admission_audit",
            "_authorization",
            "_composition",
            "_external_decision",
            "_gate",
            "_parent_attack_audit",
            "_recovery_parent_binding",
            "_recovery_execution_contract",
            "_scope",
            "_source_identity",
            "_v230_freeze",
        )
    )
)


class V231Error(ValueError):
    pass


def _fail(stage: str, reason: str) -> NoReturn:
    raise V231Error(f"{stage}:{reason}")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        _fail("load", f"object required:{path}")
    return value


def _bytes(value: Any) -> bytes:
    return models.canonical_bytes(value)


def _make(model_type: type[BaseModel], values: dict[str, Any], field: str, prefix: str) -> Any:
    return models.make_identity(model_type, values, field=field, prefix=prefix)


def _git(repository_root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ("git", *args),
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    return result.stdout


def _formal_dir(repository_root: Path, run_id: str) -> Path:
    return repository_root / "trusted_data_synthesis" / "artifacts" / "vtdo_experiment" / run_id


def _verify_manifest(directory: Path, manifest: Any) -> tuple[int, int]:
    expected_paths = {"artifact_manifest.json", *(row.relative_path for row in manifest.members)}
    actual_paths = {
        path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()
    }
    if actual_paths != expected_paths:
        _fail("freeze.paths", f"formal path set differs:{directory.name}")
    for row in manifest.members:
        payload = (directory / row.relative_path).read_bytes()
        if len(payload) != row.byte_count or models.sha(payload) != row.sha256:
            _fail("freeze.member", f"formal member differs:{row.relative_path}")
    total = sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())
    return len(actual_paths), total


def _external_decision(review_path: Path) -> tuple[models.ExternalDecision, bytes]:
    review = review_path.read_bytes()
    if (
        len(review) != 12_817
        or models.sha(review) != "a7a93482dbd8a7944f105b670ca9eb35a042fcc87f790940ca4c8910c3a6b5e4"
    ):
        _fail("external.review", "external review bytes differ")
    text = review.decode("utf-8")
    compact = "".join(text.split())
    required = (
        "AUDIT_DECISION=PASS_AS_SCOPED",
        "BLOCKING_DEFECT=NONE_FOUND",
        "MANDATORY_REVISION=NONE",
        "NEXT_UNCLOSED_GATE=RECOVERY_ONLINE_AUTHORIZATION",
        models.CONSUMED_STAGE,
    )
    if any(marker not in compact for marker in required):
        _fail("external.scope", "external review decision markers differ")
    values: dict[str, Any] = {
        "review_sha256": models.sha(review),
        "operator_directive_sha256": models.sha(DIRECTIVE),
    }
    decision = cast(
        models.ExternalDecision,
        _make(models.ExternalDecision, values, "decision_id", models.ExternalDecision.prefix()),
    )
    return decision, review


def _v230_freeze(repository_root: Path, external_decision_id: str) -> models.V230Freeze:
    directory = _formal_dir(repository_root, V230_RUN_ID)
    manifest = v230_models.ArtifactManifest.model_validate(
        _load(directory / "artifact_manifest.json")
    )
    file_count, total_bytes = _verify_manifest(directory, manifest)
    report = v230_models.Report.model_validate(_load(directory / "report.json"))
    decision = v230_models.Decision.model_validate(_load(directory / "decision.json"))
    transition = v230_models.Transition.model_validate(_load(directory / "transition.json"))
    gate = v230_models.GateEvaluation.model_validate(_load(directory / "gate_evaluation.json"))
    source = v230_models.SourceIdentity.model_validate(_load(directory / "source_identity.json"))
    component_ids = tuple(
        sorted(
            (
                report.v229_freeze_audit_id,
                report.detached_rebuild_audit_id,
                report.dependency_closure_audit_id,
                report.source_partition_audit_id,
                report.journal_audit_id,
                report.replay_audit_id,
                report.identifiability_audit_id,
                report.recovery_population_audit_id,
                report.negative_control_audit_id,
                report.scope_boundary_audit_id,
            )
        )
    )
    if (
        file_count != 20
        or total_bytes != 308_132
        or manifest.file_count != 19
        or manifest.total_member_bytes != 304_982
        or source.source_commit != "bb056e0def4a7ceec4f07797b5e559ff7067f848"
        or source.source_tree != "413c52ab220393d6ff63855ce9735b248915c6b6"
        or report.decision_id != decision.decision_id
        or report.gate_evaluation_id != gate.evaluation_id
        or report.transition_id != transition.transition_id
        or gate.passed_count != 8
        or gate.failed_count != 0
        or transition.prospective_next_stage != models.CONSUMED_STAGE
        or transition.next_stage_authorized
        or report.online_authorizations != 0
        or report.provider_calls != 0
        or report.recovery_executions != 0
    ):
        _fail("freeze.v230", "v26.230 independent-audit authority differs")
    values: dict[str, Any] = {
        "external_decision_id": external_decision_id,
        "source_commit": source.source_commit,
        "source_tree": source.source_tree,
        "manifest_id": manifest.manifest_id,
        "artifact_root": manifest.artifact_root,
        "report_id": report.report_id,
        "gate_id": gate.evaluation_id,
        "decision_id": decision.decision_id,
        "transition_id": transition.transition_id,
        "component_audit_ids": component_ids,
    }
    return cast(
        models.V230Freeze,
        _make(models.V230Freeze, values, "freeze_id", models.V230Freeze.prefix()),
    )


def _recovery_parent_binding(
    repository_root: Path, freeze: models.V230Freeze
) -> models.RecoveryParentBinding:
    v229_dir = _formal_dir(repository_root, V229_RUN_ID)
    v230_dir = _formal_dir(repository_root, V230_RUN_ID)
    v209_dir = _formal_dir(repository_root, V209_RUN_ID)
    manifest = v229_models.ArtifactManifest.model_validate(
        _load(v229_dir / "artifact_manifest.json")
    )
    file_count, total_bytes = _verify_manifest(v229_dir, manifest)
    report = v229_models.Report.model_validate(_load(v229_dir / "report.json"))
    decision = v229_models.Decision.model_validate(_load(v229_dir / "decision.json"))
    transition = v229_models.Transition.model_validate(_load(v229_dir / "transition.json"))
    contract = v229_models.RecoveryContract.model_validate(
        _load(v229_dir / "recovery_contract.json")
    )
    population = v229_models.RecoveryPopulation.model_validate(
        _load(v229_dir / "recovery_population.json")
    )
    v230_population = v230_models.RecoveryPopulationAudit.model_validate(
        _load(v230_dir / "recovery_population_audit.json")
    )
    v230_replay = v230_models.ReplayAudit.model_validate(
        _load(v230_dir / "request_replay_audit.json")
    )
    if (
        file_count != 117
        or total_bytes != 1_105_367
        or manifest.file_count != 116
        or manifest.total_member_bytes != 1_088_415
        or report.decision_id != decision.decision_id
        or report.transition_id != transition.transition_id
        or report.recovery_contract_id != contract.contract_id
        or report.recovery_population_id != population.population_id
        or population.recovery_contract_id != contract.contract_id
        or v230_population.candidate_recovery_contract_id != contract.contract_id
        or v230_population.candidate_recovery_population_id != population.population_id
        or not v230_population.candidate_contract_actual_byte_match
        or not v230_population.candidate_population_actual_byte_match
    ):
        _fail("parent.v229", "v26.229 recovery parent differs")
    phase_by_ordinal = {row.job_ordinal: row.phases[-1] for row in v230_replay.rows}
    census = _load(v209_dir / "executable_invocation_census.json")
    invocation_rows = census.get("rows")
    if not isinstance(invocation_rows, list) or len(invocation_rows) != 792:
        _fail("parent.v209", "v26.209 invocation Census differs")
    baseline_requests = tuple(
        json.loads(str(row["canonical_request_body_json"])) for row in invocation_rows
    )
    if any(
        request.get("max_tokens") != 16_384
        or request.get("model") != "deepseek-v4-flash"
        or request.get("thinking") != {"type": "enabled"}
        or request.get("response_format") != {"type": "json_object"}
        for request in baseline_requests
    ):
        _fail("parent.v209", "v26.209 request resource route differs")
    budget_rows: list[models.RecoveryBudgetRow] = []
    candidate_matches = 0
    recovery_matches = 0
    for job in population.jobs:
        candidate = job.candidate
        ordinal = candidate.job_ordinal
        candidate_path = v229_dir / "recovery_candidates" / f"job_{ordinal:03d}.json"
        recovery_path = v229_dir / "recovery_jobs" / f"job_{ordinal:03d}.json"
        saved_candidate = v229_models.RecoveryCandidate.model_validate(_load(candidate_path))
        saved_job = v229_models.RecoveryPopulationJob.model_validate(_load(recovery_path))
        if _bytes(saved_candidate) != _bytes(candidate):
            _fail("parent.candidate", f"Recovery Candidate differs:{ordinal}")
        if _bytes(saved_job) != _bytes(job):
            _fail("parent.job", f"Recovery Job differs:{ordinal}")
        candidate_matches += 1
        recovery_matches += 1
        source_row = _load(v229_dir / "source_rows" / f"job_{ordinal:03d}.json")
        calls = source_row.get("provider_calls")
        if not isinstance(calls, list) or len(calls) != candidate.successful_prefix_call_count + 1:
            _fail("parent.journal", f"Provider Journal geometry differs:{ordinal}")
        successful = calls[:-1]
        failed = calls[-1]
        prefix_tokens = sum(
            int(row["input_tokens"]) + int(row["output_tokens"]) for row in successful
        )
        if (
            any(row.get("status") != "succeeded" for row in successful)
            or failed.get("status") != "provider_error"
            or failed.get("request_sha256") != candidate.exact_failed_request_sha256
        ):
            _fail("parent.request", f"failed request route differs:{ordinal}")
        phase = phase_by_ordinal.get(ordinal)
        if phase not in {"first_action", "subsequent_action", "final"}:
            _fail("parent.phase", f"failed phase differs:{ordinal}")
        budget_rows.append(
            models.RecoveryBudgetRow(
                job_ordinal=ordinal,
                recovery_job_id=job.recovery_job_id,
                recovery_candidate_id=candidate.candidate_id,
                historical_job_id=candidate.historical_job_id,
                source_row_id=candidate.source_row_id,
                failed_request_sha256=candidate.exact_failed_request_sha256,
                failed_request_byte_count=candidate.exact_failed_request_byte_count,
                failed_phase=cast(Any, phase),
                successful_prefix_call_count=candidate.successful_prefix_call_count,
                successful_prefix_usage_tokens=prefix_tokens,
                remaining_primary_request_limit=21 - candidate.successful_prefix_call_count,
                remaining_provider_call_limit=23 - candidate.successful_prefix_call_count,
                remaining_transport_invocation_limit=24 - candidate.successful_prefix_call_count,
                remaining_rollout_token_limit=1_120_000 - prefix_tokens,
            )
        )
    ordered_rows = tuple(sorted(budget_rows, key=lambda row: row.job_ordinal))
    candidate_ids = tuple(sorted(row.recovery_candidate_id for row in ordered_rows))
    job_ids = tuple(sorted(row.recovery_job_id for row in ordered_rows))
    source_ids = tuple(sorted(row.source_row_id for row in ordered_rows))
    request_hashes = tuple(sorted(row.failed_request_sha256 for row in ordered_rows))
    values: dict[str, Any] = {
        "v230_freeze_id": freeze.freeze_id,
        "v229_manifest_id": manifest.manifest_id,
        "v229_artifact_root": manifest.artifact_root,
        "v229_report_id": report.report_id,
        "v229_decision_id": decision.decision_id,
        "v229_transition_id": transition.transition_id,
        "recovery_contract_id": contract.contract_id,
        "recovery_population_id": population.population_id,
        "v230_recovery_population_audit_id": v230_population.audit_id,
        "v230_replay_audit_id": v230_replay.audit_id,
        "recovery_candidate_ids": candidate_ids,
        "recovery_job_ids": job_ids,
        "source_row_ids": source_ids,
        "failed_request_sha256s": request_hashes,
        "budget_rows": ordered_rows,
        "candidate_set_sha256": models.canonical_sha256(candidate_ids),
        "job_set_sha256": models.canonical_sha256(job_ids),
        "source_row_set_sha256": models.canonical_sha256(source_ids),
        "failed_request_set_sha256": models.canonical_sha256(request_hashes),
        "candidate_actual_byte_matches": candidate_matches,
        "recovery_job_actual_byte_matches": recovery_matches,
    }
    return cast(
        models.RecoveryParentBinding,
        _make(
            models.RecoveryParentBinding,
            values,
            "binding_id",
            models.RecoveryParentBinding.prefix(),
        ),
    )


def _recovery_execution_contract(
    parent: models.RecoveryParentBinding,
) -> models.RecoveryExecutionContract:
    values: dict[str, Any] = {
        "parent_binding_id": parent.binding_id,
        "v209_execution_contract_id": "fresh_repaired_final_continuity_executable_full_condition_execution_contract:fc10dce5cdb2a3f677c93ad0780b5aa2b2e22eb44d6a1bf3c1d43d11ac6540d4",
        "v209_runner_id": "fresh_repaired_final_continuity_executable_full_condition_runner:e58b8318667568b9becbb1fa946f1ac079937c9c744b6a2c4877661abebf0266",
        "v209_resource_contract_id": "authoritative_kernel_resource_persistence_contract:ba6fb7967c3429d05184cc7a3ddc619187bf28ea438cc1b46bd66ce6a21055b4",
        "v209_repair_profile_id": "fresh_repaired_action_interface_full_condition_profile:b0be8d7e8166f0fd5dfce43edc0ab4150e02f4f59cd97b4310e6cd49df94ab52",
    }
    return cast(
        models.RecoveryExecutionContract,
        _make(
            models.RecoveryExecutionContract,
            values,
            "contract_id",
            models.RecoveryExecutionContract.prefix(),
        ),
    )


def _composition(
    freeze: models.V230Freeze,
    parent: models.RecoveryParentBinding,
    contract: models.RecoveryExecutionContract,
) -> models.RecoveryComposition:
    values: dict[str, Any] = {
        "v230_freeze_id": freeze.freeze_id,
        "parent_binding_id": parent.binding_id,
        "execution_contract_id": contract.contract_id,
        "event_sequence": models.EVENT_SEQUENCE,
    }
    return cast(
        models.RecoveryComposition,
        _make(
            models.RecoveryComposition,
            values,
            "composition_id",
            models.RecoveryComposition.prefix(),
        ),
    )


def _authorization(
    external: models.ExternalDecision,
    freeze: models.V230Freeze,
    parent: models.RecoveryParentBinding,
    contract: models.RecoveryExecutionContract,
    composition: models.RecoveryComposition,
) -> models.ExactOnlineAuthorization:
    values: dict[str, Any] = {
        "external_decision_id": external.decision_id,
        "v230_freeze_id": freeze.freeze_id,
        "parent_binding_id": parent.binding_id,
        "execution_contract_id": contract.contract_id,
        "composition_id": composition.composition_id,
        "recovery_job_ids": parent.recovery_job_ids,
        "recovery_job_set_sha256": parent.job_set_sha256,
    }
    return cast(
        models.ExactOnlineAuthorization,
        _make(
            models.ExactOnlineAuthorization,
            values,
            "authorization_id",
            models.ExactOnlineAuthorization.prefix(),
        ),
    )


def _request(authorization: models.ExactOnlineAuthorization) -> dict[str, Any]:
    return {
        "authorization": authorization,
        "authorization_bytes": _bytes(authorization),
        "requested_stage": authorization.authorized_stage,
        "requested_v230_freeze_id": authorization.v230_freeze_id,
        "requested_parent_binding_id": authorization.parent_binding_id,
        "requested_execution_contract_id": authorization.execution_contract_id,
        "requested_composition_id": authorization.composition_id,
        "requested_recovery_job_ids": authorization.recovery_job_ids,
        "provider_execution_requested": True,
        "continuation_to_terminal_requested": True,
    }


def _control(name: str, *, admitted: bool, reason: str | None = None) -> models.AdmissionControl:
    values: dict[str, Any] = {
        "control_name": name,
        "admitted": admitted,
        "rejected": not admitted,
        "rejection_reason_sha256": None if reason is None else models.sha(reason.encode("utf-8")),
    }
    return cast(
        models.AdmissionControl,
        _make(models.AdmissionControl, values, "control_id", models.AdmissionControl.prefix()),
    )


def _admission_audit(authorization: models.ExactOnlineAuthorization) -> models.AdmissionAudit:
    guard = models.PrecredentialGuard(authorization, _bytes(authorization))
    base = _request(authorization)
    admission = guard.admit(**base)
    controls = [_control("exact_nonconsuming_diagnostic", admitted=True)]
    attacks: tuple[tuple[str, str, Any], ...] = (
        ("missing_authorization", "authorization", None),
        ("modified_authorization_bytes", "authorization_bytes", _bytes(authorization) + b"x"),
        ("changed_stage", "requested_stage", authorization.authorized_stage + "_changed"),
        (
            "changed_v230_freeze",
            "requested_v230_freeze_id",
            authorization.v230_freeze_id + "_changed",
        ),
        (
            "changed_parent_binding",
            "requested_parent_binding_id",
            authorization.parent_binding_id + "_changed",
        ),
        (
            "changed_execution_contract",
            "requested_execution_contract_id",
            authorization.execution_contract_id + "_changed",
        ),
        (
            "changed_composition",
            "requested_composition_id",
            authorization.composition_id + "_changed",
        ),
        ("changed_job_set", "requested_recovery_job_ids", authorization.recovery_job_ids[:-1]),
        ("missing_provider_intent", "provider_execution_requested", False),
        ("missing_continuation_intent", "continuation_to_terminal_requested", False),
        ("historical_prefix_reissue", "successful_prefix_provider_reissue_requested", True),
        ("historical_mutation", "historical_mutation_requested", True),
        ("historical_terminal_backfill", "historical_terminal_backfill_requested", True),
        ("replacement_192_job_run", "replacement_run_requested", True),
        ("extra_recovery_job", "extra_recovery_job_requested", True),
        ("max_tokens_change", "max_tokens_change_requested", True),
        ("empirical_estimation", "empirical_estimation_requested", True),
        ("qa_integration", "qa_integration_requested", True),
    )
    for name, field, value in attacks:
        candidate = dict(base)
        candidate[field] = value
        try:
            guard.admit(**candidate)
        except ValueError as error:
            controls.append(_control(name, admitted=False, reason=str(error)))
        else:
            _fail("admission.control", f"invalid control admitted:{name}")
    values: dict[str, Any] = {
        "authorization_id": authorization.authorization_id,
        "admission_id": admission.admission_id,
        "controls": tuple(controls),
        "invalid_control_count": len(controls) - 1,
    }
    return cast(
        models.AdmissionAudit,
        _make(models.AdmissionAudit, values, "audit_id", models.AdmissionAudit.prefix()),
    )


def _parent_attack_audit(
    authorization: models.ExactOnlineAuthorization,
) -> models.ParentAttackAudit:
    guard = models.PrecredentialGuard(authorization, _bytes(authorization))
    base_request = _request(authorization)
    mutations: list[tuple[str, str, Any]] = [
        (
            "external_decision_parent",
            "external_decision_id",
            authorization.external_decision_id + "_changed",
        ),
        ("v230_freeze_parent", "v230_freeze_id", authorization.v230_freeze_id + "_changed"),
        (
            "recovery_parent_binding",
            "parent_binding_id",
            authorization.parent_binding_id + "_changed",
        ),
        (
            "recovery_execution_contract",
            "execution_contract_id",
            authorization.execution_contract_id + "_changed",
        ),
        ("recovery_composition", "composition_id", authorization.composition_id + "_changed"),
    ]
    for index in range(5):
        changed = list(authorization.recovery_job_ids)
        changed[index] = f"finance_v26_229_recovery_job:{index:064x}"
        ordered = tuple(sorted(changed))
        mutations.append((f"recovery_job_member_{index}", "recovery_job_ids", ordered))
    results: list[models.ParentAttack] = []
    for name, field, value in mutations:
        values = authorization.model_dump(mode="python", exclude={"authorization_id"})
        values[field] = value
        if field == "recovery_job_ids":
            values["recovery_job_set_sha256"] = models.canonical_sha256(value)
        candidate = cast(
            models.ExactOnlineAuthorization,
            _make(
                models.ExactOnlineAuthorization,
                values,
                "authorization_id",
                models.ExactOnlineAuthorization.prefix(),
            ),
        )
        request = dict(base_request)
        request["authorization"] = candidate
        request["authorization_bytes"] = _bytes(candidate)
        try:
            guard.admit(**request)
        except ValueError as error:
            attack_values: dict[str, Any] = {
                "attack_name": name,
                "mutated_authorization_id": candidate.authorization_id,
                "rejection_reason_sha256": models.sha(str(error).encode("utf-8")),
            }
            results.append(
                cast(
                    models.ParentAttack,
                    _make(
                        models.ParentAttack,
                        attack_values,
                        "attack_id",
                        models.ParentAttack.prefix(),
                    ),
                )
            )
        else:
            _fail("parent.attack", f"fully rehashed parent attack admitted:{name}")
    values = {
        "authorization_id": authorization.authorization_id,
        "attacks": tuple(results),
        "attack_count": len(results),
        "rejected_attack_count": len(results),
        "fully_rehashed_object_count": len(results),
    }
    return cast(
        models.ParentAttackAudit,
        _make(models.ParentAttackAudit, values, "audit_id", models.ParentAttackAudit.prefix()),
    )


def _scope(authorization: models.ExactOnlineAuthorization) -> models.ScopeAudit:
    return cast(
        models.ScopeAudit,
        _make(
            models.ScopeAudit,
            {"authorization_id": authorization.authorization_id},
            "audit_id",
            models.ScopeAudit.prefix(),
        ),
    )


def _source_identity(
    repository_root: Path, source_commit: str, source_tree: str
) -> models.SourceIdentity:
    resolved_commit = (
        _git(repository_root, "rev-parse", f"{source_commit}^{{commit}}").decode().strip()
    )
    resolved_tree = _git(repository_root, "rev-parse", f"{source_commit}^{{tree}}").decode().strip()
    if resolved_commit != source_commit or resolved_tree != source_tree:
        _fail("source.commit_tree", "source commit/tree relation differs")
    members: list[models.SourceMember] = []
    for relative_path in SOURCE_PATHS:
        committed = _git(repository_root, "show", f"{source_commit}:{relative_path}")
        current = (repository_root / relative_path).read_bytes()
        if committed != current:
            _fail("source.current", f"current source differs:{relative_path}")
        blob = (
            _git(repository_root, "rev-parse", f"{source_commit}:{relative_path}").decode().strip()
        )
        members.append(
            models.SourceMember(
                relative_path=relative_path,
                git_blob_oid=blob,
                sha256=models.sha(committed),
                byte_count=len(committed),
                committed_current_bytes_match=True,
            )
        )
    ordered = tuple(sorted(members, key=lambda row: row.relative_path))
    values: dict[str, Any] = {
        "source_commit": source_commit,
        "source_tree": source_tree,
        "members": ordered,
        "member_set_sha256": models.canonical_sha256(
            tuple(row.model_dump(mode="json") for row in ordered)
        ),
    }
    return cast(
        models.SourceIdentity,
        _make(models.SourceIdentity, values, "source_identity_id", models.SourceIdentity.prefix()),
    )


def _implementation_binding(
    repository_root: Path,
    source: models.SourceIdentity,
    external: models.ExternalDecision,
    freeze: models.V230Freeze,
) -> models.ImplementationBinding:
    implementation_path = repository_root / SOURCE_PATHS[0]
    tree = ast.parse(implementation_path.read_text(encoding="utf-8"))
    functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if not set(REQUIRED_SYMBOLS).issubset(functions):
        _fail("implementation.symbols", "required implementation symbol missing")
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    if names & {"requests", "httpx", "urllib", "socket"} or attrs & {"urlopen", "request"}:
        _fail("implementation.network", "network symbol present")
    values: dict[str, Any] = {
        "source_identity_id": source.source_identity_id,
        "external_decision_id": external.decision_id,
        "v230_freeze_id": freeze.freeze_id,
        "required_symbols": REQUIRED_SYMBOLS,
    }
    return cast(
        models.ImplementationBinding,
        _make(
            models.ImplementationBinding,
            values,
            "binding_id",
            models.ImplementationBinding.prefix(),
        ),
    )


def _gate(evidence: tuple[tuple[str, tuple[str, ...]], ...]) -> models.GateEvaluation:
    gates = tuple(
        models.Gate(name=name, evidence_ids=evidence_ids) for name, evidence_ids in evidence
    )
    return cast(
        models.GateEvaluation,
        _make(
            models.GateEvaluation, {"gates": gates}, "evaluation_id", models.GateEvaluation.prefix()
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.Report:
    external, review = _external_decision(external_review_path)
    freeze = _v230_freeze(repository_root, external.decision_id)
    parent = _recovery_parent_binding(repository_root, freeze)
    contract = _recovery_execution_contract(parent)
    composition = _composition(freeze, parent, contract)
    authorization = _authorization(external, freeze, parent, contract, composition)
    admission = _admission_audit(authorization)
    attacks = _parent_attack_audit(authorization)
    scope = _scope(authorization)
    source = _source_identity(repository_root, *source_identity)
    implementation = _implementation_binding(repository_root, source, external, freeze)
    gate = _gate(
        (
            ("G0_external_scope_and_exact_v230_freeze", (external.decision_id, freeze.freeze_id)),
            ("G1_exact_v229_contract_population_and_33_jobs", (parent.binding_id,)),
            ("G2_exact_55_prefix_and_33_failed_request_authority", (parent.binding_id,)),
            (
                "G3_continue_from_failure_to_terminal_semantics",
                (contract.contract_id, composition.composition_id),
            ),
            ("G4_explicit_residual_resource_and_call_budget", (contract.contract_id,)),
            ("G5_fresh_one_time_online_authorization", (authorization.authorization_id,)),
            ("G6_precredential_guard_and_parent_attacks", (admission.audit_id, attacks.audit_id)),
            (
                "G7_zero_provider_recovery_empirical_boundary",
                (scope.audit_id, implementation.binding_id),
            ),
        )
    )
    decision = cast(
        models.Decision,
        _make(
            models.Decision,
            {
                "external_decision_id": external.decision_id,
                "gate_evaluation_id": gate.evaluation_id,
                "authorization_id": authorization.authorization_id,
            },
            "decision_id",
            models.Decision.prefix(),
        ),
    )
    transition = cast(
        models.Transition,
        _make(
            models.Transition,
            {
                "decision_id": decision.decision_id,
                "authorization_id": authorization.authorization_id,
            },
            "transition_id",
            models.Transition.prefix(),
        ),
    )
    report = cast(
        models.Report,
        _make(
            models.Report,
            {
                "source_identity_id": source.source_identity_id,
                "implementation_binding_id": implementation.binding_id,
                "external_decision_id": external.decision_id,
                "v230_freeze_id": freeze.freeze_id,
                "parent_binding_id": parent.binding_id,
                "execution_contract_id": contract.contract_id,
                "composition_id": composition.composition_id,
                "authorization_id": authorization.authorization_id,
                "admission_audit_id": admission.audit_id,
                "parent_attack_audit_id": attacks.audit_id,
                "scope_audit_id": scope.audit_id,
                "gate_evaluation_id": gate.evaluation_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
            },
            "report_id",
            models.Report.prefix(),
        ),
    )
    payloads = {
        "decision.json": _bytes(decision),
        "exact_online_execution_authorization.json": _bytes(authorization),
        "external_online_authorization_decision.json": _bytes(external),
        "external_review.txt": review,
        "gate_evaluation.json": _bytes(gate),
        "implementation_binding.json": _bytes(implementation),
        "online_execution_composition.json": _bytes(composition),
        "operator_directive.txt": DIRECTIVE,
        "parent_attack_audit.json": _bytes(attacks),
        "precredential_admission_audit.json": _bytes(admission),
        "recovery_execution_contract.json": _bytes(contract),
        "recovery_parent_binding.json": _bytes(parent),
        "report.json": _bytes(report),
        "scope_boundary_audit.json": _bytes(scope),
        "source_identity.json": _bytes(source),
        "transition.json": _bytes(transition),
        "v230_freeze.json": _bytes(freeze),
    }
    manifest = models.artifact_manifest(payloads)
    output_dir.mkdir(parents=True, exist_ok=False)
    for relative_path, payload in sorted(payloads.items()):
        (output_dir / relative_path).write_bytes(payload)
    (output_dir / "artifact_manifest.json").write_bytes(_bytes(manifest))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-review", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    build(
        repository_root=args.repository_root.resolve(),
        output_dir=args.output_dir.resolve(),
        external_review_path=args.external_review.resolve(),
        source_identity=(args.source_commit, args.source_tree),
    )


if __name__ == "__main__":
    main()
