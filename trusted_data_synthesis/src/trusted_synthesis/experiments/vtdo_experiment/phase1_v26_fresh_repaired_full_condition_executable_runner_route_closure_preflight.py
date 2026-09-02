# ruff: noqa: E501, SLF001
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import subprocess
import tempfile
from collections import Counter, deque
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn, Protocol, cast

from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_models as v194_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_online_execution as v188,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_action_interface_full_condition_integration_preflight as v206,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_action_interface_full_condition_integration_preflight_models as v206_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_executable_runner_route_closure_preflight_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_preflight_independent_audit_models as v207_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_prompt_authority_repair as v193,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_prompt_authority_repair_models as v193_models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    parse_qualified_final_response,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    SemanticActionResponseRejection,
    parse_exact_canonical_action_payload,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    make_stage_one_request_body,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = (
    "finance_v26_208_fresh_repaired_full_condition_executable_runner_"
    "route_closure_preflight_v1_20260902"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
EXTERNAL_REVIEW_SHA256: Final = "4777e6e354b5bd114dcfa1fc549bb419be1ea5daed58e8e64ebaf263ab35b2f1"
EXTERNAL_REVIEW_BYTES: Final = 13_410
OPERATOR_DIRECTIVE: Final = "参照审计执行v26.208，你刚才缺漏了"
V207_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_207_fresh_repaired_full_condition_preflight_"
    "independent_audit_v1_20260902"
)
V206_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_206_fresh_repaired_action_interface_full_condition_"
    "integration_preflight_v1_20260902"
)
V194_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_194_authoritative_execution_kernel_parent_preflight_v1_20260901"
)
V193_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_193_json_prompt_authority_repair_preflight_v2_20260901"
)
MODEL_PROFILE: Final = (
    "trusted_data_synthesis/config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
)
INJECTED_TRANSPORT_SEAM_ID: Final = (
    "fresh_repaired_executable_injected_transport_seam:current_state_validated_request_only.v1"
)
IMPLEMENTATION_FILES: Final = tuple(
    sorted(
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_full_condition_executable_runner_route_closure_preflight.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_full_condition_executable_runner_route_closure_preflight_models.py",
            "trusted_data_synthesis/tests/"
            "test_v26_fresh_repaired_full_condition_executable_runner_route_closure_preflight.py",
        )
    )
)


class V208Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


class TypedTransportFailure(Exception):
    def __init__(self, terminal: str, reason: str) -> None:
        super().__init__(reason)
        self.terminal = terminal
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V208Error(stage, reason)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _file_bytes(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_no_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()


def _recursive_key_count(value: Any, target: str) -> int:
    if isinstance(value, Mapping):
        return int(target in value) + sum(
            _recursive_key_count(item, target) for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return sum(_recursive_key_count(item, target) for item in value)
    return 0


def _verify_self_excluding_manifest(
    root: Path,
    manifest: Any,
    *,
    manifest_name: str = "artifact_manifest.json",
) -> tuple[int, int]:
    actual_files = tuple(sorted(path for path in root.iterdir() if path.is_file()))
    members = tuple(manifest.members)
    expected = {path.name for path in actual_files if path.name != manifest_name}
    if {item.relative_path for item in members} != expected:
        _fail("freeze.path_set", f"formal directory path set differs:{root.name}")
    for member in members:
        payload = (root / member.relative_path).read_bytes()
        if len(payload) != member.byte_count or _sha256_bytes(payload) != member.sha256:
            _fail("freeze.member_bytes", f"formal member bytes differ:{member.relative_path}")
    return len(actual_files), sum(path.stat().st_size for path in actual_files)


def _authorization(
    external_review_path: Path,
) -> tuple[models.ExternalRouteClosureAuthorization, bytes, bytes]:
    review_bytes = external_review_path.read_bytes()
    if (
        len(review_bytes) != EXTERNAL_REVIEW_BYTES
        or _sha256_bytes(review_bytes) != EXTERNAL_REVIEW_SHA256
    ):
        _fail("authorization.review", "v26.208 external review bytes differ")
    directive_bytes = OPERATOR_DIRECTIVE.encode("utf-8")
    authorization = cast(
        models.ExternalRouteClosureAuthorization,
        models.make_identity(
            models.ExternalRouteClosureAuthorization,
            {
                "review_sha256": _sha256_bytes(review_bytes),
                "review_byte_count": len(review_bytes),
                "operator_directive_sha256": _sha256_bytes(directive_bytes),
                "operator_directive_byte_count": len(directive_bytes),
            },
            field="authorization_id",
            prefix="finance_v26_208_external_route_closure_authorization:",
        ),
    )
    return authorization, review_bytes, directive_bytes


@dataclass(frozen=True)
class FrozenParents:
    freeze: models.V207PredecessorFreeze
    profile: v206_models.FullConditionRepairProfile
    source_catalog: v206_models.RepairedRunnerPackageCatalog
    source_manifest: v206_models.RepairedDevelopmentManifest
    source_runner: v206_models.RepairedRunnerContract
    source_execution: v206_models.RepairedExecutionContract
    source_estimand: v206_models.ProspectiveEstimandContract
    v194_manifest: v194_models.AuthoritativeDevelopmentManifest
    v193_evidence: v193_models.ExactPromptEvidenceSet


def _predecessor_freeze(
    *,
    repository_root: Path,
    authorization_id: str,
) -> FrozenParents:
    v207_root = repository_root / V207_DIR
    v207_manifest = v207_models.ArtifactManifest.model_validate(
        _load(v207_root / "artifact_manifest.json")
    )
    v207_files, v207_bytes = _verify_self_excluding_manifest(v207_root, v207_manifest)
    if (v207_files, v207_bytes) != (16, 1_408_911):
        _fail("freeze.v207_geometry", "v26.207 formal directory geometry differs")
    v207_report = v207_models.IndependentAuditReport.model_validate(
        _load(v207_root / "report.json")
    )
    v207_decision = v207_models.IndependentAuditDecision.model_validate(
        _load(v207_root / "decision.json")
    )
    v207_transition = v207_models.BlockedTransition.model_validate(
        _load(v207_root / "blocked_transition.json")
    )
    v207_gate = v207_models.IndependentAuditGateEvaluation.model_validate(
        _load(v207_root / "independent_audit_gate_evaluation.json")
    )
    v207_route = v207_models.SourceRouteNoBypassAudit.model_validate(
        _load(v207_root / "source_route_no_bypass_audit.json")
    )
    v207_v206_freeze = v207_models.V206PreflightFreeze.model_validate(
        _load(v207_root / "v206_preflight_freeze.json")
    )
    if (
        v207_report.formal_scope_completed is not True
        or v207_decision.future_online_runner_no_bypass_result != "unclosed_absent_executable_route"
        or v207_transition.next_stage is not None
        or v207_transition.recommended_candidate_successor != models.CONSUMED_STAGE
        or v207_gate.a3_source_level_repair_request_transport_no_bypass_passed
        or v207_route.first_unclosed_seam
        != "executable_future_runner_repair_request_validation_transport_route_absent"
    ):
        _fail("freeze.v207_decision", "v26.207 negative audit boundary differs")

    v206_root = repository_root / V206_DIR
    v206_manifest = v206_models.ArtifactManifest.model_validate(
        _load(v206_root / "artifact_manifest.json")
    )
    v206_files, v206_bytes = _verify_self_excluding_manifest(v206_root, v206_manifest)
    if (v206_files, v206_bytes) != (17, 2_519_097):
        _fail("freeze.v206_geometry", "v26.206 formal directory geometry differs")
    v206_report = v206_models.PreflightReport.model_validate(_load(v206_root / "report.json"))
    profile = v206_models.FullConditionRepairProfile.model_validate(
        _load(v206_root / "full_condition_repair_profile.json")
    )
    catalog = v206_models.RepairedRunnerPackageCatalog.model_validate(
        _load(v206_root / "repaired_runner_package_catalog.json")
    )
    manifest = v206_models.RepairedDevelopmentManifest.model_validate(
        _load(v206_root / "repaired_development_manifest.json")
    )
    runner = v206_models.RepairedRunnerContract.model_validate(
        _load(v206_root / "repaired_runner_contract.json")
    )
    execution = v206_models.RepairedExecutionContract.model_validate(
        _load(v206_root / "repaired_execution_contract.json")
    )
    estimand = v206_models.ProspectiveEstimandContract.model_validate(
        _load(v206_root / "prospective_estimand_contract.json")
    )
    if (
        v207_v206_freeze.v206_report_id != v206_report.report_id
        or v207_v206_freeze.v206_manifest_id != manifest.manifest_id
        or v207_v206_freeze.v206_runner_id != runner.runner_id
        or v207_v206_freeze.v206_execution_contract_id != execution.contract_id
        or v207_v206_freeze.v206_estimand_contract_id != estimand.contract_id
        or v207_v206_freeze.v206_artifact_manifest_id != v206_manifest.manifest_id
        or v207_v206_freeze.v206_artifact_root != v206_manifest.artifact_root
    ):
        _fail("freeze.v206_parent", "v26.207 does not bind the exact v26.206 parents")
    v194_manifest = v194_models.AuthoritativeDevelopmentManifest.model_validate(
        _load(repository_root / V194_DIR / "authoritative_development_manifest.json")
    )
    v193_evidence = v193_models.ExactPromptEvidenceSet.model_validate(
        _load(repository_root / V193_DIR / "exact_prompt_evidence_set.json")
    )
    freeze = cast(
        models.V207PredecessorFreeze,
        models.make_identity(
            models.V207PredecessorFreeze,
            {
                "authorization_id": authorization_id,
                "v207_report_id": v207_report.report_id,
                "v207_decision_id": v207_decision.decision_id,
                "v207_transition_id": v207_transition.transition_id,
                "v207_gate_evaluation_id": v207_gate.evaluation_id,
                "v207_source_route_audit_id": v207_route.audit_id,
                "v207_artifact_manifest_id": v207_manifest.manifest_id,
                "v207_artifact_root": v207_manifest.artifact_root,
                "v207_source_commit": "304d4a6f42b22524a34e76eda55c23235937acdb",
                "v207_source_tree": "40e503fc402d337b48038d65bf22ffd90b00ed21",
                "v206_report_id": v206_report.report_id,
                "v206_repair_profile_id": profile.profile_id,
                "v206_package_catalog_id": catalog.catalog_id,
                "v206_manifest_id": manifest.manifest_id,
                "v206_runner_id": runner.runner_id,
                "v206_execution_contract_id": execution.contract_id,
                "v206_estimand_contract_id": estimand.contract_id,
                "v193_prompt_evidence_set_id": v193_evidence.evidence_set_id,
                "v203_action_contract_id": profile.source_v203_action_contract_id,
                "v194_resource_contract_id": execution.resource_contract_id,
            },
            field="freeze_id",
            prefix="finance_v26_208_v207_predecessor_freeze:",
        ),
    )
    return FrozenParents(
        freeze=freeze,
        profile=profile,
        source_catalog=catalog,
        source_manifest=manifest,
        source_runner=runner,
        source_execution=execution,
        source_estimand=estimand,
        v194_manifest=v194_manifest,
        v193_evidence=v193_evidence,
    )


def _git(repository_root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository_root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        _fail("source.git", completed.stderr.decode("utf-8", errors="replace"))
    return completed.stdout


def _implementation_binding(
    *,
    repository_root: Path,
    authorization_id: str,
    predecessor_freeze_id: str,
    source_identity: tuple[str, str],
) -> models.ImplementationBinding:
    commit, tree = source_identity
    actual_tree = _git(repository_root, "rev-parse", f"{commit}^{{tree}}").decode().strip()
    if actual_tree != tree:
        _fail("source.tree", "v26.208 source commit/tree pair differs")
    bindings: list[models.SourceFileBinding] = []
    for relative in IMPLEMENTATION_FILES:
        live = (repository_root / relative).read_bytes()
        committed = _git(repository_root, "show", f"{commit}:{relative}")
        if live != committed:
            _fail("source.live_bytes", f"live source differs from source commit:{relative}")
        bindings.append(
            models.SourceFileBinding(
                relative_path=relative,
                sha256=_sha256_bytes(live),
                byte_count=len(live),
            )
        )
    return cast(
        models.ImplementationBinding,
        models.make_identity(
            models.ImplementationBinding,
            {
                "authorization_id": authorization_id,
                "predecessor_freeze_id": predecessor_freeze_id,
                "source_commit": commit,
                "source_tree": tree,
                "files": tuple(bindings),
            },
            field="implementation_id",
            prefix="fresh_repaired_executable_route_implementation_binding:",
        ),
    )


def _fresh_identity_chain(
    *,
    implementation: models.ImplementationBinding,
    parents: FrozenParents,
) -> tuple[
    models.ExecutableRunnerPackageCatalog,
    models.ExecutableDevelopmentManifest,
    models.ExecutableRunnerContract,
    models.ExecutableExecutionContract,
]:
    packages = tuple(
        cast(
            models.ExecutableRunnerPackage,
            models.make_identity(
                models.ExecutableRunnerPackage,
                {
                    "source_v206_package_id": source.package_id,
                    "source_v206_package_sha256": models.canonical_sha256(source),
                    "implementation_id": implementation.implementation_id,
                    "repair_profile_id": parents.profile.profile_id,
                    "runtime_semantic_contract_id": source.runtime_semantic_contract_id,
                    "runtime_implementation_binding_id": source.runtime_implementation_binding_id,
                    "final_grammar_id": source.final_grammar_id,
                    "resource_contract_id": source.resource_contract_id,
                    "capability_family": source.capability_family,
                    "depth": source.depth,
                    "schedule_ids": source.schedule_ids,
                    "component_keys": source.component_keys,
                },
                field="package_id",
                prefix="fresh_repaired_executable_full_condition_runner_package:",
            ),
        )
        for source in sorted(parents.source_catalog.packages, key=lambda item: item.package_id)
    )
    catalog = cast(
        models.ExecutableRunnerPackageCatalog,
        models.make_identity(
            models.ExecutableRunnerPackageCatalog,
            {
                "implementation_id": implementation.implementation_id,
                "repair_profile_id": parents.profile.profile_id,
                "packages": packages,
                "source_v206_package_ids": tuple(
                    sorted(item.source_v206_package_id for item in packages)
                ),
            },
            field="catalog_id",
            prefix="fresh_repaired_executable_full_condition_package_catalog:",
        ),
    )
    package_by_source = {item.source_v206_package_id: item for item in packages}
    jobs: list[models.ExecutableDevelopmentJob] = []
    for source in sorted(parents.source_manifest.jobs, key=lambda item: item.job_id):
        package = package_by_source[source.package_id]
        parent = {
            "source_v206_job_id": source.job_id,
            "package_id": package.package_id,
            "implementation_id": implementation.implementation_id,
            "repair_profile_id": parents.profile.profile_id,
            "replica_index": source.replica_index,
        }
        jobs.append(
            cast(
                models.ExecutableDevelopmentJob,
                models.make_identity(
                    models.ExecutableDevelopmentJob,
                    {
                        **parent,
                        "source_v206_job_sha256": models.canonical_sha256(source),
                        "source_v194_job_id": source.source_v194_job_id,
                        "source_v206_package_id": source.package_id,
                        "raw_namespace": canonical_hash(
                            parent, prefix="fresh_repaired_executable_raw_namespace:"
                        ),
                        "result_namespace": canonical_hash(
                            parent, prefix="fresh_repaired_executable_result_namespace:"
                        ),
                        "trace_namespace": canonical_hash(
                            parent, prefix="fresh_repaired_executable_trace_namespace:"
                        ),
                        "outcome_namespace": canonical_hash(
                            parent, prefix="fresh_repaired_executable_outcome_namespace:"
                        ),
                        "deterministic_seed_id": canonical_hash(
                            parent, prefix="fresh_repaired_executable_deterministic_seed:"
                        ),
                    },
                    field="job_id",
                    prefix="fresh_repaired_executable_full_condition_development_job:",
                ),
            )
        )
    job_tuple = tuple(jobs)
    manifest = cast(
        models.ExecutableDevelopmentManifest,
        models.make_identity(
            models.ExecutableDevelopmentManifest,
            {
                "package_catalog_id": catalog.catalog_id,
                "implementation_id": implementation.implementation_id,
                "repair_profile_id": parents.profile.profile_id,
                "jobs": job_tuple,
                "expected_job_ids": tuple(sorted(item.job_id for item in job_tuple)),
                "source_v206_job_ids": tuple(sorted(item.source_v206_job_id for item in job_tuple)),
            },
            field="manifest_id",
            prefix="fresh_repaired_executable_full_condition_manifest:",
        ),
    )
    runner = cast(
        models.ExecutableRunnerContract,
        models.make_identity(
            models.ExecutableRunnerContract,
            {
                "manifest_id": manifest.manifest_id,
                "package_catalog_id": catalog.catalog_id,
                "implementation_id": implementation.implementation_id,
                "repair_profile_id": parents.profile.profile_id,
                "source_v206_runner_id": parents.source_runner.runner_id,
            },
            field="runner_id",
            prefix="fresh_repaired_executable_full_condition_runner:",
        ),
    )
    execution = cast(
        models.ExecutableExecutionContract,
        models.make_identity(
            models.ExecutableExecutionContract,
            {
                "runner_id": runner.runner_id,
                "manifest_id": manifest.manifest_id,
                "package_catalog_id": catalog.catalog_id,
                "implementation_id": implementation.implementation_id,
                "repair_profile_id": parents.profile.profile_id,
                "source_v206_execution_contract_id": parents.source_execution.contract_id,
                "resource_contract_id": parents.source_execution.resource_contract_id,
            },
            field="contract_id",
            prefix="fresh_repaired_executable_full_condition_execution_contract:",
        ),
    )
    return catalog, manifest, runner, execution


@dataclass(frozen=True)
class TransportDispatch:
    request_body: Mapping[str, Any]
    certificate: models.ValidatedRequestCertificate
    receipt: models.PreTransportReceipt


class InjectedTransportSeam(Protocol):
    def send(self, dispatch: TransportDispatch) -> Mapping[str, Any]: ...


class ScriptedTransport:
    def __init__(self) -> None:
        self._queue: deque[Mapping[str, Any] | TypedTransportFailure] = deque()
        self.dispatches: list[TransportDispatch] = []

    def queue(self, value: Mapping[str, Any] | TypedTransportFailure) -> None:
        self._queue.append(value)

    def send(self, dispatch: TransportDispatch) -> Mapping[str, Any]:
        if (
            dispatch.receipt.certificate_id != dispatch.certificate.certificate_id
            or dispatch.receipt.request_id != dispatch.certificate.request_id
            or models.canonical_sha256(dispatch.request_body)
            != dispatch.certificate.canonical_request_body_sha256
        ):
            raise TypedTransportFailure(
                "instrument_failure",
                "injected transport received an invalid request/certificate/receipt chain",
            )
        if not self._queue:
            raise TypedTransportFailure(
                "instrument_failure", "injected scripted transport queue is empty"
            )
        self.dispatches.append(dispatch)
        value = self._queue.popleft()
        if isinstance(value, TypedTransportFailure):
            raise value
        return value


@dataclass(frozen=True)
class InvocationOutcome:
    record: models.ExecutableInvocationRecord
    runtime_output: Any = None
    final_result: Any = None
    terminal: str | None = None


def _compile_authoritative_messages(
    *,
    phase: models.PromptPhase,
    prompt_core: dict[str, Any] | str,
    prompt_kind: str,
    profile: v206_models.FullConditionRepairProfile,
) -> tuple[dict[str, str], ...]:
    if phase == "final":
        if not isinstance(prompt_core, str):
            _fail("runner.final_prompt", "Final Prompt is not a frozen rendered string")
        return ({"role": "user", "content": prompt_core},)
    if not isinstance(prompt_core, dict):
        _fail("runner.action_prompt", "Action Prompt core is not a public object")
    messages, _state_id, _candidates = v206._repaired_messages(
        core=prompt_core,
        prompt_kind=prompt_kind,
        profile=profile,
    )
    return messages


def _build_canonical_request_body(
    config: AgentModelConfig,
    messages: tuple[dict[str, str], ...],
) -> dict[str, Any]:
    body = make_stage_one_request_body(config, messages[-1]["content"])
    body["messages"] = [dict(item) for item in messages]
    return body


def _validate_request_and_certificate(
    *,
    job: models.ExecutableDevelopmentJob,
    invocation_index: int,
    phase: models.PromptPhase,
    current_state_id: str,
    candidate_action_ids: tuple[str, ...],
    messages: tuple[dict[str, str], ...],
    request_body: dict[str, Any],
    prompt_id: str,
    request_id: str,
    config: AgentModelConfig,
    profile: v206_models.FullConditionRepairProfile,
    final_grammar_id: str,
) -> models.ValidatedRequestCertificate:
    reconstructed = _build_canonical_request_body(config, messages)
    if reconstructed != request_body:
        _fail("runner.request_reconstruction", "canonical request builder reconstruction differs")
    if (
        request_body.get("model") != config.model
        or request_body.get("thinking") != {"type": "enabled"}
        or request_body.get("response_format") != {"type": "json_object"}
        or request_body.get("messages") != [dict(item) for item in messages]
    ):
        _fail("runner.request_binding", "request model/Thinking/format/messages differ")
    old_abi = _recursive_key_count(request_body, "response_abi")
    visible_grammar = _recursive_key_count(request_body, "grammar_id")
    if phase == "final":
        if len(messages) != 1 or messages[0]["role"] != "user" or candidate_action_ids:
            _fail("runner.final_interface", "Final request carries an Action interface")
        grammar_id = final_grammar_id
    else:
        if tuple(item["role"] for item in messages) != ("system", "user"):
            _fail("runner.action_messages", "Action/Correction messages are not system+user")
        system = json.loads(messages[0]["content"])
        user = json.loads(messages[1]["content"])
        contract = system.get("authoritative_response_contract", {})
        values = contract.get("field_values", {})
        if (
            old_abi != 0
            or visible_grammar != 0
            or tuple(contract.get("required_fields", ())) != profile.exact_required_fields
            or tuple(contract.get("allowed_fields", ())) != profile.exact_allowed_fields
            or tuple(values.get("action_id", {}).get("one_of", ())) != candidate_action_ids
            or values.get("state_id") != current_state_id
            or values.get("decision_kind") != profile.decision_kind_value
            or values.get("protocol") != profile.protocol_value
            or user.get("response_contract_location") != "system_message_only"
        ):
            _fail("runner.action_contract", "dynamic repaired Action Contract differs")
        grammar_id = profile.frozen_action_grammar_id
    return cast(
        models.ValidatedRequestCertificate,
        models.make_identity(
            models.ValidatedRequestCertificate,
            {
                "job_id": job.job_id,
                "invocation_index": invocation_index,
                "phase": phase,
                "prompt_id": prompt_id,
                "request_id": request_id,
                "current_state_id": current_state_id,
                "candidate_action_ids": candidate_action_ids,
                "canonical_messages_sha256": models.canonical_sha256(messages),
                "canonical_request_body_sha256": models.canonical_sha256(request_body),
                "repair_profile_id": profile.profile_id,
                "grammar_id": grammar_id,
                "model_id": config.model,
                "old_response_abi_key_count": old_abi,
                "model_visible_grammar_id_key_count": visible_grammar,
            },
            field="certificate_id",
            prefix="fresh_repaired_executable_request_validation_certificate:",
        ),
    )


def _pre_transport_receipt(
    *,
    certificate: models.ValidatedRequestCertificate,
) -> models.PreTransportReceipt:
    return cast(
        models.PreTransportReceipt,
        models.make_identity(
            models.PreTransportReceipt,
            {
                "certificate_id": certificate.certificate_id,
                "job_id": certificate.job_id,
                "invocation_index": certificate.invocation_index,
                "phase": certificate.phase,
                "request_id": certificate.request_id,
                "injected_transport_seam_id": INJECTED_TRANSPORT_SEAM_ID,
            },
            field="receipt_id",
            prefix="fresh_repaired_executable_pre_transport_receipt:",
        ),
    )


def _project_public_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    def prohibited(value: Any) -> bool:
        if isinstance(value, Mapping):
            return any(
                "reasoning" in str(key).casefold() or prohibited(item)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple)):
            return any(prohibited(item) for item in value)
        return False

    if prohibited(payload):
        raise TypedTransportFailure(
            "privacy_rejection", "public response contains a classifier-sensitive private key"
        )
    projected = json.loads(models.canonical_bytes(payload))
    if not isinstance(projected, dict):
        raise TypedTransportFailure("instrument_failure", "public response is not a JSON object")
    return projected


def _invocation_record(
    *,
    job: models.ExecutableDevelopmentJob,
    invocation_index: int,
    phase: models.PromptPhase,
    component_key: str | None,
    current_state_id: str,
    candidate_action_ids: tuple[str, ...],
    selected_action_id: str | None,
    prompt_id: str,
    request_id: str,
    certificate: models.ValidatedRequestCertificate,
    receipt: models.PreTransportReceipt,
    messages: tuple[dict[str, str], ...],
    request_body: dict[str, Any],
    response: dict[str, Any] | None,
    exact_response_parsed: bool,
    state_or_envelope_valid: bool,
    runtime_completed: bool,
    action_accepted: bool | None,
    typed_terminal: str | None,
    event_sequence: tuple[str, ...],
) -> models.ExecutableInvocationRecord:
    return cast(
        models.ExecutableInvocationRecord,
        models.make_identity(
            models.ExecutableInvocationRecord,
            {
                "job_id": job.job_id,
                "invocation_index": invocation_index,
                "phase": phase,
                "component_key": component_key,
                "current_state_id": current_state_id,
                "candidate_action_ids": candidate_action_ids,
                "selected_action_id": selected_action_id,
                "prompt_id": prompt_id,
                "request_id": request_id,
                "certificate_id": certificate.certificate_id,
                "pre_transport_receipt_id": receipt.receipt_id,
                "injected_transport_seam_id": INJECTED_TRANSPORT_SEAM_ID,
                "canonical_messages_sha256": models.canonical_sha256(messages),
                "canonical_messages_byte_count": len(models.canonical_bytes(messages)),
                "canonical_request_body_sha256": models.canonical_sha256(request_body),
                "canonical_request_body_byte_count": len(models.canonical_bytes(request_body)),
                "public_response_sha256": (
                    None if response is None else models.canonical_sha256(response)
                ),
                "exact_response_parsed": exact_response_parsed,
                "current_state_and_candidate_or_final_envelope_valid": state_or_envelope_valid,
                "runtime_step_or_finalize_completed": runtime_completed,
                "action_accepted": action_accepted,
                "typed_terminal": typed_terminal,
                "event_sequence": event_sequence,
            },
            field="invocation_id",
            prefix="fresh_repaired_executable_invocation_record:",
        ),
    )


class ExecutableRepairedFullConditionRunner:
    def __init__(
        self,
        *,
        transport: InjectedTransportSeam,
        config: AgentModelConfig,
        profile: v206_models.FullConditionRepairProfile,
        prepared: v188.PreparedExecution,
        implementation_id: str,
    ) -> None:
        self._transport = transport
        self._config = config
        self._profile = profile
        self._prepared = prepared
        self._implementation_id = implementation_id

    def invoke_action(
        self,
        *,
        job: models.ExecutableDevelopmentJob,
        invocation_index: int,
        state: Any,
    ) -> InvocationOutcome:
        phase: models.PromptPhase = (
            "first_action" if state.current_index == 0 else "subsequent_action"
        )
        return self._invoke_current_state(
            job=job,
            invocation_index=invocation_index,
            phase=phase,
            state=state,
            context=None,
        )

    def invoke_correction(
        self,
        *,
        job: models.ExecutableDevelopmentJob,
        invocation_index: int,
        state: Any,
    ) -> InvocationOutcome:
        return self._invoke_current_state(
            job=job,
            invocation_index=invocation_index,
            phase="correction",
            state=state,
            context=None,
        )

    def invoke_final(
        self,
        *,
        job: models.ExecutableDevelopmentJob,
        invocation_index: int,
        state: Any,
        context: Any,
    ) -> InvocationOutcome:
        return self._invoke_current_state(
            job=job,
            invocation_index=invocation_index,
            phase="final",
            state=state,
            context=context,
        )

    def _invoke_current_state(
        self,
        *,
        job: models.ExecutableDevelopmentJob,
        invocation_index: int,
        phase: models.PromptPhase,
        state: Any,
        context: Any,
    ) -> InvocationOutcome:
        events: list[str] = ["read_current_runtime_state"]
        preview_result = None
        final_envelope = None
        if phase == "final":
            if context is None or state.current_index != len(state.ordered_components):
                _fail(
                    "runner.final_state", "Final invoked before the actual terminal Runtime State"
                )
            preview_result = step_runtime.finalize(copy.deepcopy(state))
            prompt_core, final_envelope = v188.render_final_prompt(
                context=context,
                result=preview_result,
                grammar=self._prepared.final_grammar,
            )
            current_state_id = preview_result.result_id
            candidates: tuple[str, ...] = ()
            component_key = None
            prompt_kind = "final"
        else:
            if state.current_index >= len(state.ordered_components):
                _fail("runner.action_state", "Action invoked after terminal Runtime State")
            public_prompt = step_runtime.render_next_prompt(state)
            prompt_core = v193._action_core(public_prompt, self._prepared)
            current_state_id = public_prompt.state.state_token
            candidates = tuple(item.action_id for item in public_prompt.candidates)
            component_key = state.ordered_components[state.current_index].component_key
            prompt_kind = "correction" if phase == "correction" else "action"
        messages = _compile_authoritative_messages(
            phase=phase,
            prompt_core=prompt_core,
            prompt_kind=prompt_kind,
            profile=self._profile,
        )
        events.append("compile_authoritative_messages")
        request_body = _build_canonical_request_body(self._config, messages)
        events.append("build_canonical_request")
        messages_sha = models.canonical_sha256(messages)
        body_sha = models.canonical_sha256(request_body)
        prompt_id = canonical_hash(
            {
                "job_id": job.job_id,
                "invocation_index": invocation_index,
                "phase": phase,
                "current_state_id": current_state_id,
                "canonical_messages_sha256": messages_sha,
                "implementation_id": self._implementation_id,
            },
            prefix="fresh_repaired_executable_dynamic_prompt:",
        )
        request_id = canonical_hash(
            {
                "job_id": job.job_id,
                "invocation_index": invocation_index,
                "prompt_id": prompt_id,
                "canonical_request_body_sha256": body_sha,
            },
            prefix="fresh_repaired_executable_dynamic_request:",
        )
        certificate = _validate_request_and_certificate(
            job=job,
            invocation_index=invocation_index,
            phase=phase,
            current_state_id=current_state_id,
            candidate_action_ids=candidates,
            messages=messages,
            request_body=request_body,
            prompt_id=prompt_id,
            request_id=request_id,
            config=self._config,
            profile=self._profile,
            final_grammar_id=self._prepared.final_grammar.grammar_id,
        )
        events.append("validate_request_and_certificate")
        receipt = _pre_transport_receipt(certificate=certificate)
        events.append("emit_pre_transport_receipt")
        try:
            response = self._transport.send(
                TransportDispatch(
                    request_body=request_body,
                    certificate=certificate,
                    receipt=receipt,
                )
            )
            events.append("injected_transport_dispatch")
            public = _project_public_payload(response)
            events.append("project_public_payload")
        except TypedTransportFailure as error:
            if events[-1] != "injected_transport_dispatch":
                events.append("injected_transport_dispatch")
            events.append("terminal_dispatch")
            record = _invocation_record(
                job=job,
                invocation_index=invocation_index,
                phase=phase,
                component_key=component_key,
                current_state_id=current_state_id,
                candidate_action_ids=candidates,
                selected_action_id=None,
                prompt_id=prompt_id,
                request_id=request_id,
                certificate=certificate,
                receipt=receipt,
                messages=messages,
                request_body=request_body,
                response=None,
                exact_response_parsed=False,
                state_or_envelope_valid=False,
                runtime_completed=False,
                action_accepted=None,
                typed_terminal=error.terminal,
                event_sequence=tuple(events),
            )
            return InvocationOutcome(record=record, terminal=error.terminal)

        if phase == "final":
            try:
                parse_qualified_final_response(
                    public,
                    grammar=self._prepared.final_grammar,
                    envelope=final_envelope,
                )
            except (ValidationError, ValueError):
                events.extend(("parse_exact_response", "terminal_dispatch"))
                terminal = "final_response_abi_invalid"
                record = _invocation_record(
                    job=job,
                    invocation_index=invocation_index,
                    phase=phase,
                    component_key=None,
                    current_state_id=current_state_id,
                    candidate_action_ids=(),
                    selected_action_id=None,
                    prompt_id=prompt_id,
                    request_id=request_id,
                    certificate=certificate,
                    receipt=receipt,
                    messages=messages,
                    request_body=request_body,
                    response=public,
                    exact_response_parsed=False,
                    state_or_envelope_valid=False,
                    runtime_completed=False,
                    action_accepted=None,
                    typed_terminal=terminal,
                    event_sequence=tuple(events),
                )
                return InvocationOutcome(record=record, terminal=terminal)
            events.append("parse_exact_response")
            events.append("validate_current_state_and_candidate_or_final_envelope")
            actual_result = step_runtime.finalize(state)
            if preview_result is None or actual_result.result_id != preview_result.result_id:
                _fail("runner.finalize", "Final preview and actual Runtime result differ")
            events.extend(("runtime_step_or_finalize", "terminal_dispatch"))
            record = _invocation_record(
                job=job,
                invocation_index=invocation_index,
                phase=phase,
                component_key=None,
                current_state_id=current_state_id,
                candidate_action_ids=(),
                selected_action_id=None,
                prompt_id=prompt_id,
                request_id=request_id,
                certificate=certificate,
                receipt=receipt,
                messages=messages,
                request_body=request_body,
                response=public,
                exact_response_parsed=True,
                state_or_envelope_valid=True,
                runtime_completed=True,
                action_accepted=None,
                typed_terminal=None,
                event_sequence=tuple(events),
            )
            return InvocationOutcome(record=record, final_result=actual_result)

        try:
            proposal = parse_exact_canonical_action_payload(public)
        except SemanticActionResponseRejection:
            events.extend(("parse_exact_response", "terminal_dispatch"))
            terminal = (
                "correction_response_abi_invalid"
                if phase == "correction"
                else "first_response_abi_invalid"
            )
            record = _invocation_record(
                job=job,
                invocation_index=invocation_index,
                phase=phase,
                component_key=component_key,
                current_state_id=current_state_id,
                candidate_action_ids=candidates,
                selected_action_id=None,
                prompt_id=prompt_id,
                request_id=request_id,
                certificate=certificate,
                receipt=receipt,
                messages=messages,
                request_body=request_body,
                response=public,
                exact_response_parsed=False,
                state_or_envelope_valid=False,
                runtime_completed=False,
                action_accepted=None,
                typed_terminal=terminal,
                event_sequence=tuple(events),
            )
            return InvocationOutcome(record=record, terminal=terminal)
        events.append("parse_exact_response")
        if proposal.state_id != current_state_id or proposal.action_id not in candidates:
            events.extend(
                (
                    "validate_current_state_and_candidate_or_final_envelope",
                    "terminal_dispatch",
                )
            )
            terminal = (
                "correction_action_reference_invalid"
                if phase == "correction"
                else "first_action_reference_invalid"
            )
            record = _invocation_record(
                job=job,
                invocation_index=invocation_index,
                phase=phase,
                component_key=component_key,
                current_state_id=current_state_id,
                candidate_action_ids=candidates,
                selected_action_id=proposal.action_id,
                prompt_id=prompt_id,
                request_id=request_id,
                certificate=certificate,
                receipt=receipt,
                messages=messages,
                request_body=request_body,
                response=public,
                exact_response_parsed=True,
                state_or_envelope_valid=False,
                runtime_completed=False,
                action_accepted=None,
                typed_terminal=terminal,
                event_sequence=tuple(events),
            )
            return InvocationOutcome(record=record, terminal=terminal)
        events.append("validate_current_state_and_candidate_or_final_envelope")
        runtime_output = step_runtime.step(state, proposal.action_id)
        accepted = bool(getattr(runtime_output, "action_accepted", False))
        events.extend(("runtime_step_or_finalize", "terminal_dispatch"))
        record = _invocation_record(
            job=job,
            invocation_index=invocation_index,
            phase=phase,
            component_key=component_key,
            current_state_id=current_state_id,
            candidate_action_ids=candidates,
            selected_action_id=proposal.action_id,
            prompt_id=prompt_id,
            request_id=request_id,
            certificate=certificate,
            receipt=receipt,
            messages=messages,
            request_body=request_body,
            response=public,
            exact_response_parsed=True,
            state_or_envelope_valid=True,
            runtime_completed=True,
            action_accepted=accepted,
            typed_terminal=None,
            event_sequence=tuple(events),
        )
        return InvocationOutcome(record=record, runtime_output=runtime_output)


def _action_payload(
    *,
    state_id: str,
    action_id: str,
    profile: v206_models.FullConditionRepairProfile,
) -> dict[str, Any]:
    return {
        "state_id": state_id,
        "action_id": action_id,
        "decision_kind": profile.decision_kind_value,
        "protocol": profile.protocol_value,
    }


def _final_payload(result: Any, source: Any) -> dict[str, Any]:
    result_payload = result.projected_public_answer or {"preflight_status": "completed_invalid"}
    citations = result.public_citations or (
        source.public_task.semantic_task.records[0].record_handle,
    )
    return {
        "answer": {
            "result": result_payload,
            "citations": tuple({"evidence_id": item} for item in citations),
        },
        "rationale_summary": "credential-free executable Runner route-closure preflight",
    }


def _context_for_job(
    *,
    job: models.ExecutableDevelopmentJob,
    parents: FrozenParents,
    prepared: v188.PreparedExecution,
) -> Any:
    source_v206 = {item.job_id: item for item in parents.source_manifest.jobs}[
        job.source_v206_job_id
    ]
    source_v194 = {item.job_id: item for item in parents.v194_manifest.jobs}[
        source_v206.source_v194_job_id
    ]
    evidence_rows = tuple(
        item
        for item in parents.v193_evidence.rows
        if item.coordinate.fresh_job_id == source_v194.source_job_id
    )
    if not evidence_rows:
        _fail("runtime.job_parent", "v26.194 Job has no frozen v26.193 Prompt parent")
    old_job_ids = {item.coordinate.source_job_id for item in evidence_rows}
    if len(old_job_ids) != 1:
        _fail("runtime.job_parent", "one v26.194 Job crosses actual Runtime Jobs")
    old_source = {item.job_id: item for item in prepared.frozen.manifest.jobs}[old_job_ids.pop()]
    return frozen_runtime.prepare_job(old_source, prepared.runtime_catalog)


def _make_runner(
    *,
    transport: ScriptedTransport,
    config: AgentModelConfig,
    parents: FrozenParents,
    prepared: v188.PreparedExecution,
    implementation_id: str,
) -> ExecutableRepairedFullConditionRunner:
    return ExecutableRepairedFullConditionRunner(
        transport=transport,
        config=config,
        profile=parents.profile,
        prepared=prepared,
        implementation_id=implementation_id,
    )


def _run_full_condition_control(
    *,
    manifest: models.ExecutableDevelopmentManifest,
    execution: models.ExecutableExecutionContract,
    implementation: models.ImplementationBinding,
    parents: FrozenParents,
    prepared: v188.PreparedExecution,
    config: AgentModelConfig,
) -> tuple[
    models.ExecutableInvocationCensus,
    models.FullConditionExecutionControlAudit,
]:
    all_records: list[models.ExecutableInvocationRecord] = []
    job_rows: list[models.ExecutableJobControlRow] = []
    correction_distribution: Counter[int] = Counter()
    for job in sorted(manifest.jobs, key=lambda item: item.job_id):
        context = _context_for_job(job=job, parents=parents, prepared=prepared)
        state = frozen_runtime._initialize(context)
        transport = ScriptedTransport()
        runner = _make_runner(
            transport=transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=implementation.implementation_id,
        )
        records: list[models.ExecutableInvocationRecord] = []
        invocation_index = 0
        action_count = 0
        subsequent_count = 0
        correction_count = 0
        while state.current_index < len(state.ordered_components):
            component_index = state.current_index
            prompt = step_runtime.render_next_prompt(state)
            dispositions = frozen_runtime._candidate_dispositions(state, prompt)
            reference = frozen_runtime._reference_selection(
                state, prompt, dispositions, component_index
            )
            if reference.action_id is None:
                _fail("execution.reference", "reference Action lacks an Action ID")
            invalid = next(
                (item for item in dispositions if not item.acceptance.accepted),
                None,
            )
            first_action_id = invalid.action_id if invalid is not None else reference.action_id
            transport.queue(
                _action_payload(
                    state_id=prompt.state.state_token,
                    action_id=first_action_id,
                    profile=parents.profile,
                )
            )
            action = runner.invoke_action(
                job=job,
                invocation_index=invocation_index,
                state=state,
            )
            invocation_index += 1
            action_count += 1
            subsequent_count += int(component_index > 0)
            records.append(action.record)
            all_records.append(action.record)
            if action.terminal is not None:
                _fail(
                    "execution.action_terminal", f"reference control terminalized:{action.terminal}"
                )
            if invalid is None:
                if action.record.action_accepted is not True:
                    _fail("execution.reference_action", "reference Action did not commit")
                continue
            if action.record.action_accepted is not False:
                _fail("execution.typed_rejection", "registered invalid Action did not reject")
            correction_prompt = step_runtime.render_next_prompt(state)
            correction_rows = frozen_runtime._candidate_dispositions(state, correction_prompt)
            corrected = frozen_runtime._reference_correction(
                state,
                correction_prompt,
                correction_rows,
                component_index,
                invalid.action_id,
            )
            if corrected.action_id is None:
                _fail("execution.correction_reference", "reference Correction lacks Action ID")
            transport.queue(
                _action_payload(
                    state_id=correction_prompt.state.state_token,
                    action_id=corrected.action_id,
                    profile=parents.profile,
                )
            )
            correction = runner.invoke_correction(
                job=job,
                invocation_index=invocation_index,
                state=state,
            )
            invocation_index += 1
            correction_count += 1
            records.append(correction.record)
            all_records.append(correction.record)
            if correction.terminal is not None or correction.record.action_accepted is not True:
                _fail("execution.correction", "reference Correction did not commit")
        preview_result = step_runtime.finalize(copy.deepcopy(state))
        transport.queue(_final_payload(preview_result, context.source))
        final = runner.invoke_final(
            job=job,
            invocation_index=invocation_index,
            state=state,
            context=context,
        )
        records.append(final.record)
        all_records.append(final.record)
        if final.terminal is not None or final.final_result is None:
            _fail("execution.final", f"reference Final terminalized:{final.terminal}")
        result = final.final_result
        if (
            not result.task_validity.base_valid
            or not result.mechanism_qualification.mechanism_semantically_qualified
            or not result.qualified_validity.qualified_valid
        ):
            _fail("execution.validity", "scripted executable trajectory is not Qualified")
        if len(transport.dispatches) != len(records):
            _fail("execution.transport_count", "one invocation did not dispatch exactly once")
        invocation_ids = tuple(item.invocation_id for item in records)
        raw_id = canonical_hash(
            {"job_id": job.job_id, "invocation_ids": invocation_ids},
            prefix="fresh_repaired_executable_control_raw:",
        )
        result_id = canonical_hash(
            {"job_id": job.job_id, "raw_id": raw_id, "qualified_valid": True},
            prefix="fresh_repaired_executable_control_result:",
        )
        trace_id = canonical_hash(
            {"job_id": job.job_id, "raw_id": raw_id, "result_id": result_id},
            prefix="fresh_repaired_executable_control_trace:",
        )
        outcome_id = canonical_hash(
            {"job_id": job.job_id, "trace_id": trace_id, "qualified_valid": True},
            prefix="fresh_repaired_executable_control_outcome:",
        )
        job_rows.append(
            cast(
                models.ExecutableJobControlRow,
                models.make_identity(
                    models.ExecutableJobControlRow,
                    {
                        "job_id": job.job_id,
                        "source_v206_job_id": job.source_v206_job_id,
                        "invocation_ids": invocation_ids,
                        "subsequent_action_count": subsequent_count,
                        "correction_count": correction_count,
                        "action_and_correction_count": action_count + correction_count,
                        "raw_id": raw_id,
                        "result_id": result_id,
                        "trace_id": trace_id,
                        "outcome_id": outcome_id,
                    },
                    field="row_id",
                    prefix="finance_v26_208_executable_job_control_row:",
                ),
            )
        )
        correction_distribution[correction_count] += 1
    if correction_distribution != Counter({0: 144, 1: 12, 2: 12, 3: 12, 4: 12}):
        _fail(
            "execution.correction_distribution",
            f"Correction distribution differs:{dict(correction_distribution)}",
        )
    ordered_records = tuple(
        sorted(all_records, key=lambda item: (item.job_id, item.invocation_index))
    )
    if len(ordered_records) != 792:
        _fail(
            "execution.invocation_count", f"dynamic invocation count differs:{len(ordered_records)}"
        )
    census = cast(
        models.ExecutableInvocationCensus,
        models.make_identity(
            models.ExecutableInvocationCensus,
            {
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
                "implementation_id": implementation.implementation_id,
                "rows": ordered_records,
                "maximum_message_byte_count": max(
                    item.canonical_messages_byte_count for item in ordered_records
                ),
                "maximum_request_body_byte_count": max(
                    item.canonical_request_body_byte_count for item in ordered_records
                ),
            },
            field="census_id",
            prefix="finance_v26_208_executable_invocation_census:",
        ),
    )
    control = cast(
        models.FullConditionExecutionControlAudit,
        models.make_identity(
            models.FullConditionExecutionControlAudit,
            {
                "execution_contract_id": execution.contract_id,
                "invocation_census_id": census.census_id,
                "rows": tuple(sorted(job_rows, key=lambda item: item.job_id)),
            },
            field="audit_id",
            prefix="finance_v26_208_full_condition_execution_control_audit:",
        ),
    )
    return census, control


def _method(tree: ast.AST, class_name: str, method_name: str) -> ast.FunctionDef:
    classes = [
        item
        for item in ast.walk(tree)
        if isinstance(item, ast.ClassDef) and item.name == class_name
    ]
    if len(classes) != 1:
        _fail("no_bypass.class", f"{class_name} definition count differs")
    methods = [
        item
        for item in classes[0].body
        if isinstance(item, ast.FunctionDef) and item.name == method_name
    ]
    if len(methods) != 1:
        _fail("no_bypass.method", f"{class_name}.{method_name} definition count differs")
    return methods[0]


def _call_lines(node: ast.AST, name: str) -> tuple[int, ...]:
    values: list[int] = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        if isinstance(item.func, ast.Name) and item.func.id == name:
            values.append(item.lineno)
        elif isinstance(item.func, ast.Attribute) and item.func.attr == name:
            values.append(item.lineno)
    return tuple(sorted(values))


def _source_no_bypass_audit(
    *,
    repository_root: Path,
    implementation: models.ImplementationBinding,
    execution: models.ExecutableExecutionContract,
    census: models.ExecutableInvocationCensus,
) -> models.SourceAndDynamicNoBypassAudit:
    source_path = repository_root / IMPLEMENTATION_FILES[0]
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    runner_defs = [
        item
        for item in ast.walk(tree)
        if isinstance(item, ast.ClassDef) and item.name == "ExecutableRepairedFullConditionRunner"
    ]
    seam_defs = [
        item
        for item in ast.walk(tree)
        if isinstance(item, ast.ClassDef) and item.name == "InjectedTransportSeam"
    ]
    shared = _method(tree, "ExecutableRepairedFullConditionRunner", "_invoke_current_state")
    wrappers = {
        name: _method(tree, "ExecutableRepairedFullConditionRunner", name)
        for name in ("invoke_action", "invoke_correction", "invoke_final")
    }
    compiler = _call_lines(shared, "_compile_authoritative_messages")
    builder = _call_lines(shared, "_build_canonical_request_body")
    validator = _call_lines(shared, "_validate_request_and_certificate")
    receipt = _call_lines(shared, "_pre_transport_receipt")
    dispatch = _call_lines(shared, "send")
    if (
        len(runner_defs) != 1
        or len(seam_defs) != 1
        or tuple(len(values) for values in (compiler, builder, validator, receipt, dispatch))
        != (1, 1, 1, 1, 1)
        or not (compiler[0] < builder[0] < validator[0] < receipt[0] < dispatch[0])
        or any(len(_call_lines(node, "_invoke_current_state")) != 1 for node in wrappers.values())
    ):
        _fail("no_bypass.source_route", "shared source route or exact call order differs")
    banned_calls = {
        "urlopen",
        "Request",
        "post",
        "Client",
        "AsyncClient",
        "socket",
        "create_connection",
    }
    direct_network = sum(
        1
        for item in ast.walk(tree)
        if isinstance(item, ast.Call)
        and (
            (isinstance(item.func, ast.Name) and item.func.id in banned_calls)
            or (isinstance(item.func, ast.Attribute) and item.func.attr in banned_calls)
        )
    )
    phase_counts = Counter(item.phase for item in census.rows)
    return cast(
        models.SourceAndDynamicNoBypassAudit,
        models.make_identity(
            models.SourceAndDynamicNoBypassAudit,
            {
                "implementation_id": implementation.implementation_id,
                "execution_contract_id": execution.contract_id,
                "invocation_census_id": census.census_id,
                "action_transport_route_count": (
                    phase_counts["first_action"] + phase_counts["subsequent_action"]
                ),
                "correction_transport_route_count": phase_counts["correction"],
                "final_transport_route_count": phase_counts["final"],
                "direct_provider_or_network_call_count": direct_network,
            },
            field="audit_id",
            prefix="finance_v26_208_source_dynamic_no_bypass_audit:",
        ),
    )


def _reference_complete_state(context: Any) -> Any:
    state = frozen_runtime._initialize(context)
    while state.current_index < len(state.ordered_components):
        component_index = state.current_index
        prompt = step_runtime.render_next_prompt(state)
        rows = frozen_runtime._candidate_dispositions(state, prompt)
        selection = frozen_runtime._reference_selection(state, prompt, rows, component_index)
        if selection.action_id is None:
            _fail("control.reference", "failure-control reference Action is absent")
        output = step_runtime.step(state, selection.action_id)
        if not getattr(output, "action_accepted", False):
            _fail("control.reference", "failure-control reference Action did not commit")
    return state


def _find_correction_state(
    *,
    manifest: models.ExecutableDevelopmentManifest,
    parents: FrozenParents,
    prepared: v188.PreparedExecution,
) -> tuple[models.ExecutableDevelopmentJob, Any, Any]:
    for job in sorted(manifest.jobs, key=lambda item: item.job_id):
        context = _context_for_job(job=job, parents=parents, prepared=prepared)
        state = frozen_runtime._initialize(context)
        prompt = step_runtime.render_next_prompt(state)
        rows = frozen_runtime._candidate_dispositions(state, prompt)
        invalid = next((item for item in rows if not item.acceptance.accepted), None)
        if invalid is not None:
            output = step_runtime.step(state, invalid.action_id)
            if getattr(output, "action_accepted", False):
                _fail("control.correction_setup", "invalid setup Action unexpectedly committed")
            return job, context, state
    _fail("control.correction_setup", "no registered Correction State found")


def _failure_controls(
    *,
    execution: models.ExecutableExecutionContract,
    manifest: models.ExecutableDevelopmentManifest,
    implementation: models.ImplementationBinding,
    parents: FrozenParents,
    prepared: v188.PreparedExecution,
    config: AgentModelConfig,
) -> models.TypedFailureControlAudit:
    controls: list[models.TypedFailureControl] = []

    def record_control(
        name: str,
        expected: str,
        outcome: InvocationOutcome,
    ) -> None:
        if outcome.terminal != expected:
            _fail("control.terminal", f"{name} terminal differs:{outcome.terminal}")
        controls.append(
            cast(
                models.TypedFailureControl,
                models.make_identity(
                    models.TypedFailureControl,
                    {
                        "control_name": name,
                        "expected_terminal": expected,
                        "observed_terminal": outcome.terminal,
                        "invocation_id": outcome.record.invocation_id,
                    },
                    field="control_id",
                    prefix="finance_v26_208_typed_failure_control:",
                ),
            )
        )

    first_job = sorted(manifest.jobs, key=lambda item: item.job_id)[0]
    first_context = _context_for_job(job=first_job, parents=parents, prepared=prepared)

    invalid_first_transport = ScriptedTransport()
    invalid_first_state = frozen_runtime._initialize(first_context)
    invalid_first_prompt = step_runtime.render_next_prompt(invalid_first_state)
    first_rows = frozen_runtime._candidate_dispositions(invalid_first_state, invalid_first_prompt)
    invalid_first_transport.queue(
        {
            "state_id": invalid_first_prompt.state.state_token,
            "action_id": first_rows[0].action_id,
            "decision_kind": parents.profile.decision_kind_value,
        }
    )
    record_control(
        "invalid_first_action_abi",
        "first_response_abi_invalid",
        _make_runner(
            transport=invalid_first_transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=implementation.implementation_id,
        ).invoke_action(job=first_job, invocation_index=0, state=invalid_first_state),
    )

    unknown_transport = ScriptedTransport()
    unknown_state = frozen_runtime._initialize(first_context)
    unknown_prompt = step_runtime.render_next_prompt(unknown_state)
    unknown_action = "f" * 24
    if unknown_action in {item.action_id for item in unknown_prompt.candidates}:
        _fail("control.unknown", "unknown Action collided with a current Candidate")
    unknown_transport.queue(
        _action_payload(
            state_id=unknown_prompt.state.state_token,
            action_id=unknown_action,
            profile=parents.profile,
        )
    )
    record_control(
        "unknown_current_action",
        "first_action_reference_invalid",
        _make_runner(
            transport=unknown_transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=implementation.implementation_id,
        ).invoke_action(job=first_job, invocation_index=0, state=unknown_state),
    )

    correction_job, _correction_context, correction_state = _find_correction_state(
        manifest=manifest,
        parents=parents,
        prepared=prepared,
    )
    correction_transport = ScriptedTransport()
    correction_prompt = step_runtime.render_next_prompt(correction_state)
    correction_rows = frozen_runtime._candidate_dispositions(correction_state, correction_prompt)
    correction_transport.queue(
        {
            "state_id": correction_prompt.state.state_token,
            "action_id": correction_rows[0].action_id,
            "decision_kind": parents.profile.decision_kind_value,
        }
    )
    record_control(
        "invalid_correction_abi",
        "correction_response_abi_invalid",
        _make_runner(
            transport=correction_transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=implementation.implementation_id,
        ).invoke_correction(job=correction_job, invocation_index=1, state=correction_state),
    )

    final_transport = ScriptedTransport()
    final_state = _reference_complete_state(first_context)
    final_transport.queue({})
    record_control(
        "invalid_final_abi",
        "final_response_abi_invalid",
        _make_runner(
            transport=final_transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=implementation.implementation_id,
        ).invoke_final(
            job=first_job,
            invocation_index=len(final_state.ordered_components),
            state=final_state,
            context=first_context,
        ),
    )

    outer_transport = ScriptedTransport()
    outer_state = frozen_runtime._initialize(first_context)
    outer_transport.queue(
        TypedTransportFailure("instrument_failure", "registered typed outer control")
    )
    record_control(
        "typed_outer_failure",
        "instrument_failure",
        _make_runner(
            transport=outer_transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=implementation.implementation_id,
        ).invoke_action(job=first_job, invocation_index=0, state=outer_state),
    )
    return cast(
        models.TypedFailureControlAudit,
        models.make_identity(
            models.TypedFailureControlAudit,
            {
                "execution_contract_id": execution.contract_id,
                "controls": tuple(controls),
            },
            field="audit_id",
            prefix="finance_v26_208_typed_failure_control_audit:",
        ),
    )


def _dynamic_nonreference_branch(
    *,
    execution: models.ExecutableExecutionContract,
    manifest: models.ExecutableDevelopmentManifest,
    implementation: models.ImplementationBinding,
    parents: FrozenParents,
    prepared: v188.PreparedExecution,
    config: AgentModelConfig,
) -> models.DynamicNonReferenceBranchAudit:
    for job in sorted(manifest.jobs, key=lambda item: item.job_id):
        context = _context_for_job(job=job, parents=parents, prepared=prepared)
        initial = frozen_runtime._initialize(context)
        if len(initial.ordered_components) < 2:
            continue
        prompt = step_runtime.render_next_prompt(initial)
        rows = frozen_runtime._candidate_dispositions(initial, prompt)
        reference = frozen_runtime._reference_selection(initial, prompt, rows, 0)
        if reference.action_id is None:
            continue
        alternatives = tuple(
            item
            for item in rows
            if item.action_id != reference.action_id and item.acceptance.accepted
        )
        for alternative in alternatives:
            reference_state = copy.deepcopy(initial)
            reference_output = step_runtime.step(reference_state, reference.action_id)
            if not getattr(reference_output, "action_accepted", False):
                continue
            reference_next = step_runtime.render_next_prompt(reference_state)
            nonreference_state = copy.deepcopy(initial)
            transport = ScriptedTransport()
            transport.queue(
                _action_payload(
                    state_id=prompt.state.state_token,
                    action_id=alternative.action_id,
                    profile=parents.profile,
                )
            )
            runner = _make_runner(
                transport=transport,
                config=config,
                parents=parents,
                prepared=prepared,
                implementation_id=implementation.implementation_id,
            )
            first = runner.invoke_action(job=job, invocation_index=0, state=nonreference_state)
            if first.terminal is not None or first.record.action_accepted is not True:
                continue
            nonreference_next = step_runtime.render_next_prompt(nonreference_state)
            if nonreference_next.state.state_token == reference_next.state.state_token:
                continue
            next_rows = frozen_runtime._candidate_dispositions(
                nonreference_state, nonreference_next
            )
            next_reference = frozen_runtime._reference_selection(
                nonreference_state,
                nonreference_next,
                next_rows,
                nonreference_state.current_index,
            )
            if next_reference.action_id is None:
                continue
            transport.queue(
                _action_payload(
                    state_id=nonreference_next.state.state_token,
                    action_id=next_reference.action_id,
                    profile=parents.profile,
                )
            )
            second = runner.invoke_action(job=job, invocation_index=1, state=nonreference_state)
            if second.terminal is not None:
                continue
            return cast(
                models.DynamicNonReferenceBranchAudit,
                models.make_identity(
                    models.DynamicNonReferenceBranchAudit,
                    {
                        "execution_contract_id": execution.contract_id,
                        "job_id": job.job_id,
                        "component_key": initial.ordered_components[0].component_key,
                        "initial_state_id": prompt.state.state_token,
                        "reference_action_id": reference.action_id,
                        "nonreference_action_id": alternative.action_id,
                        "candidate_count": len(prompt.candidates),
                        "reference_next_state_id": reference_next.state.state_token,
                        "nonreference_next_state_id": nonreference_next.state.state_token,
                        "second_invocation_current_state_id": second.record.current_state_id,
                    },
                    field="audit_id",
                    prefix="finance_v26_208_dynamic_nonreference_branch_audit:",
                ),
            )
    _fail("dynamic_branch", "no accepted nonreference dynamic-prefix witness was found")


def _source_identity(
    source_identity: tuple[str, str],
) -> models.SourceIdentity:
    return cast(
        models.SourceIdentity,
        models.make_identity(
            models.SourceIdentity,
            {
                "source_commit": source_identity[0],
                "source_tree": source_identity[1],
                "implementation_files": IMPLEMENTATION_FILES,
            },
            field="source_identity_id",
            prefix="finance_v26_208_source_identity:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.RouteClosurePreflightReport:
    if output_dir.exists():
        raise FileExistsError(f"v26.208 output already exists:{output_dir}")
    authorization, review_bytes, directive_bytes = _authorization(external_review_path)
    parents = _predecessor_freeze(
        repository_root=repository_root,
        authorization_id=authorization.authorization_id,
    )
    implementation = _implementation_binding(
        repository_root=repository_root,
        authorization_id=authorization.authorization_id,
        predecessor_freeze_id=parents.freeze.freeze_id,
        source_identity=source_identity,
    )
    catalog, manifest, runner_contract, execution = _fresh_identity_chain(
        implementation=implementation,
        parents=parents,
    )
    predecessor_ids = {
        *(item.package_id for item in parents.source_catalog.packages),
        *(item.job_id for item in parents.source_manifest.jobs),
        *(item.raw_namespace for item in parents.source_manifest.jobs),
        *(item.result_namespace for item in parents.source_manifest.jobs),
        *(item.trace_namespace for item in parents.source_manifest.jobs),
        *(item.outcome_namespace for item in parents.source_manifest.jobs),
    }
    fresh_ids = {
        *(item.package_id for item in catalog.packages),
        *(item.job_id for item in manifest.jobs),
        *(item.raw_namespace for item in manifest.jobs),
        *(item.result_namespace for item in manifest.jobs),
        *(item.trace_namespace for item in manifest.jobs),
        *(item.outcome_namespace for item in manifest.jobs),
    }
    if predecessor_ids & fresh_ids:
        _fail("identity.collision", "v26.208 identity collides with v26.206")
    config = AgentModelConfig.model_validate(_load(repository_root / MODEL_PROFILE)["model"])
    package_root = repository_root / "trusted_data_synthesis"
    with tempfile.TemporaryDirectory(prefix="v26-208-provider-forbidden-") as temporary:
        prepared = v188.prepare_execution(
            package_root=package_root,
            output_dir=Path(temporary) / "provider_forbidden",
        )
        if (
            prepared.profile.action_grammar_id != parents.profile.frozen_action_grammar_id
            or prepared.profile.final_grammar_id
            != parents.source_catalog.packages[0].final_grammar_id
            or prepared.resource.contract_id != parents.source_execution.resource_contract_id
        ):
            _fail("freeze.generation", "frozen Grammar/resource parents differ")
        census, execution_control = _run_full_condition_control(
            manifest=manifest,
            execution=execution,
            implementation=implementation,
            parents=parents,
            prepared=prepared,
            config=config,
        )
        failures = _failure_controls(
            execution=execution,
            manifest=manifest,
            implementation=implementation,
            parents=parents,
            prepared=prepared,
            config=config,
        )
        dynamic_branch = _dynamic_nonreference_branch(
            execution=execution,
            manifest=manifest,
            implementation=implementation,
            parents=parents,
            prepared=prepared,
            config=config,
        )
    no_bypass = _source_no_bypass_audit(
        repository_root=repository_root,
        implementation=implementation,
        execution=execution,
        census=census,
    )
    boundary = cast(
        models.EstimandResourceBoundaryAudit,
        models.make_identity(
            models.EstimandResourceBoundaryAudit,
            {
                "execution_contract_id": execution.contract_id,
                "source_v206_estimand_contract_id": parents.source_estimand.contract_id,
            },
            field="audit_id",
            prefix="finance_v26_208_estimand_resource_boundary_audit:",
        ),
    )
    gate = cast(
        models.RouteClosureGateAudit,
        models.make_identity(
            models.RouteClosureGateAudit,
            {
                "predecessor_freeze_id": parents.freeze.freeze_id,
                "manifest_id": manifest.manifest_id,
                "execution_contract_id": execution.contract_id,
                "invocation_census_id": census.census_id,
                "execution_control_audit_id": execution_control.audit_id,
                "no_bypass_audit_id": no_bypass.audit_id,
                "failure_control_audit_id": failures.audit_id,
                "dynamic_branch_audit_id": dynamic_branch.audit_id,
                "boundary_audit_id": boundary.audit_id,
            },
            field="audit_id",
            prefix="finance_v26_208_route_closure_gate_audit:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        models.make_identity(
            models.ProspectiveTransition,
            {
                "gate_audit_id": gate.audit_id,
                "execution_contract_id": execution.contract_id,
                "boundary_audit_id": boundary.audit_id,
            },
            field="transition_id",
            prefix="finance_v26_208_transition:",
        ),
    )
    source = _source_identity(source_identity)
    report = cast(
        models.RouteClosurePreflightReport,
        models.make_identity(
            models.RouteClosurePreflightReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "predecessor_freeze_id": parents.freeze.freeze_id,
                "implementation_id": implementation.implementation_id,
                "package_catalog_id": catalog.catalog_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner_contract.runner_id,
                "execution_contract_id": execution.contract_id,
                "invocation_census_id": census.census_id,
                "execution_control_audit_id": execution_control.audit_id,
                "no_bypass_audit_id": no_bypass.audit_id,
                "failure_control_audit_id": failures.audit_id,
                "dynamic_branch_audit_id": dynamic_branch.audit_id,
                "boundary_audit_id": boundary.audit_id,
                "gate_audit_id": gate.audit_id,
                "transition_id": transition.transition_id,
                "source_identity_id": source.source_identity_id,
            },
            field="report_id",
            prefix="finance_v26_208_route_closure_preflight_report:",
        ),
    )
    payloads = {
        "external_review.txt": review_bytes,
        "operator_authorization.txt": directive_bytes,
        "external_authorization.json": _file_bytes(authorization),
        "predecessor_freeze.json": _file_bytes(parents.freeze),
        "implementation_binding.json": _file_bytes(implementation),
        "executable_runner_package_catalog.json": _file_bytes(catalog),
        "executable_development_manifest.json": _file_bytes(manifest),
        "executable_runner_contract.json": _file_bytes(runner_contract),
        "executable_execution_contract.json": _file_bytes(execution),
        "executable_invocation_census.json": _file_bytes(census),
        "full_condition_execution_control_audit.json": _file_bytes(execution_control),
        "source_dynamic_no_bypass_audit.json": _file_bytes(no_bypass),
        "typed_failure_control_audit.json": _file_bytes(failures),
        "dynamic_nonreference_branch_audit.json": _file_bytes(dynamic_branch),
        "estimand_resource_boundary_audit.json": _file_bytes(boundary),
        "route_closure_gate_audit.json": _file_bytes(gate),
        "prospective_transition.json": _file_bytes(transition),
        "source_identity.json": _file_bytes(source),
        "report.json": _file_bytes(report),
    }
    artifact = models.artifact_manifest(RUN_ID, payloads)
    payloads["artifact_manifest.json"] = _file_bytes(artifact)
    for name, payload in sorted(payloads.items()):
        _write_no_replace(output_dir / name, payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-review", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    report = build(
        repository_root=args.repository_root.resolve(),
        output_dir=args.output_dir.resolve(),
        external_review_path=args.external_review.resolve(),
        source_identity=(args.source_commit, args.source_tree),
    )
    print(models.canonical_bytes(report).decode())


if __name__ == "__main__":
    main()
