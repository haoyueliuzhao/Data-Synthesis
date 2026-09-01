from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Final, NoReturn, cast, get_args

from pydantic import BaseModel

from trusted_synthesis.core.task import fresh_artifact_backed_outcome_authority as authority
from trusted_synthesis.core.task import (
    fresh_artifact_backed_terminal_to_outcome_integration as integration,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    json_explicit_authoritative_execution_kernel as execution_kernel,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_models as v194_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_preflight as v194,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_outcome_authority_preflight as v195,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_independent_audit_models as models,  # noqa: E501
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_models as v197_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_explicit_prompt_contract_preflight as v192,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_prompt_authority_repair_models as v193_models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    StageOneRequestBindingCertificate,
    make_stage_one_request_body,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

RUN_ID: Final = (
    "finance_v26_198_fresh_artifact_backed_terminal_to_outcome_integration_repair_"
    "independent_audit_v3_20260901"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
AUDITED_V197_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_197_fresh_artifact_backed_terminal_to_outcome_integration_repair_"
    "preflight_v1_20260901"
)
V196_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_196_fresh_artifact_backed_outcome_authority_independent_audit_"
    "v1_20260901"
)
V195_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_195_fresh_artifact_backed_outcome_authority_preflight_v1_20260901"
)
V194_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_194_authoritative_execution_kernel_parent_preflight_v1_20260901"
)
AUDITED_SOURCE_COMMIT: Final = "2551fc331f5e1327a5b78054423223d158f08d6a"
AUDITED_SOURCE_TREE: Final = "a5b1699e8e1de3622f2ddb567d6df2148a47f47e"
EXPECTED_EXTERNAL_AUDIT_SHA256: Final = (
    "2069ec4b8d3297e062146bc44e1b154196fff365a5fe7165067ba1ad5439d32d"
)
EXPECTED_EXTERNAL_AUDIT_BYTES: Final = 12_070
V197_REPORT_ID: Final = (
    "finance_v26_197_terminal_outcome_repair_preflight_report:"
    "57692819ab14fc6f7f6a9fa90f7f6c9ddb887da77ce997286d0392aed5d07954"
)
V197_TRANSITION_ID: Final = (
    "finance_v26_197_transition:fde49915b1cf82ebd95f8a37e3458976579f33a9236e1c6c77e9c59978bee01f"
)
V197_SEALED_ROOT: Final = (
    "finance_v26_197_sealed_evidence_artifact_root:"
    "cc217ac3b877c74341070ad8cfb8298c6d232f5c1d6bb514aafc936fc1142598"
)
V197_DISTRIBUTION_ROOT: Final = (
    "finance_v26_197_distribution_artifact_root:"
    "4d9760be75c4dc3f1acdd79648cddfadab30e84e823aaef2d27874346131e6e2"
)
V197_INTEGRATION_CONTRACT_ID: Final = (
    "fresh_terminal_to_outcome_integration_contract:"
    "d8de732958e439dabedd63baec87e3f504f29dfd8bd2050881652da4aef29c58"
)
EXPECTED_V197_FORMAL_FILE_COUNT: Final = 48
EXPECTED_V197_FORMAL_BYTE_COUNT: Final = 285_781
CORE_SOURCE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/core/task/"
    "fresh_artifact_backed_terminal_to_outcome_integration.py"
)
OLD_KERNEL_SOURCE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "json_explicit_authoritative_execution_kernel.py"
)
OLD_AUDIT_FIXTURE: Final = (
    "trusted_data_synthesis/tests/fixtures/v26_196_terminal_to_outcome_integration_repair_audit.txt"
)
REACHABLE_TERMINALS: Final = tuple(
    value
    for value in get_args(authority.TerminalKind)
    if value not in {"policy_horizon_exhausted", "measurement_support_exit"}
)
EXCLUDED_TERMINALS: Final = (
    "measurement_support_exit",
    "policy_horizon_exhausted",
)


class IndependentAuditError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}:{reason}")


def _fail(stage: str, reason: str) -> NoReturn:
    raise IndependentAuditError(stage, reason)


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", warnings=False)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _canonical_bytes(value: Any, *, newline: bool = True) -> bytes:
    payload = json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return payload + (b"\n" if newline else b"")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _write_no_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _git(repository_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(repository_root), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git_identity(repository_root: Path) -> tuple[str, str]:
    commit = _git(repository_root, "rev-parse", "HEAD")
    tree = _git(repository_root, "show", "-s", "--format=%T", "HEAD")
    if len(commit) != 40 or len(tree) != 40:
        _fail("git", "source Git identity is not exact")
    return commit, tree


def _git_blob(repository_root: Path, commit: str, relative_path: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(repository_root), "show", f"{commit}:{relative_path}"),
        check=True,
        capture_output=True,
    )
    return completed.stdout


def _recursive_bindings(root: Path) -> tuple[models.FileBinding, ...]:
    return tuple(
        models.FileBinding(
            relative_path=path.relative_to(root).as_posix(),
            sha256=_sha256_bytes(path.read_bytes()),
            byte_count=path.stat().st_size,
        )
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    )


def _make_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    identity_value = canonical_hash(
        provisional.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )
    return model_type(**{field: identity_value}, **values)


def _authorization(
    audit_path: Path,
) -> tuple[models.IndependentAuditAuthorization, bytes]:
    if not audit_path.is_file():
        _fail("authorization", "external v26.197 independent audit parent is missing")
    payload = audit_path.read_bytes()
    if (
        len(payload) != EXPECTED_EXTERNAL_AUDIT_BYTES
        or _sha256_bytes(payload) != EXPECTED_EXTERNAL_AUDIT_SHA256
    ):
        _fail("authorization", "external v26.197 independent audit bytes differ")
    authorization = cast(
        models.IndependentAuditAuthorization,
        models.make_identity(
            models.IndependentAuditAuthorization,
            {
                "audit_sha256": EXPECTED_EXTERNAL_AUDIT_SHA256,
                "audit_byte_count": EXPECTED_EXTERNAL_AUDIT_BYTES,
                "audit_decision": "v26_197_accepted_independent_audit_only",
                "source_transition_id": V197_TRANSITION_ID,
                "audited_source_commit": AUDITED_SOURCE_COMMIT,
            },
            field="authorization_id",
            prefix="finance_v26_198_external_independent_audit_authorization:",
        ),
    )
    return authorization, payload


def _verify_v197_formal(
    *,
    repository_root: Path,
    authorization: models.IndependentAuditAuthorization,
) -> models.V197FreezeAudit:
    root = repository_root / AUDITED_V197_DIR
    bindings = _recursive_bindings(root)
    if len(bindings) != EXPECTED_V197_FORMAL_FILE_COUNT:
        _fail("freeze.files", "v26.197 formal file count differs")
    if sum(item.byte_count for item in bindings) != EXPECTED_V197_FORMAL_BYTE_COUNT:
        _fail("freeze.bytes", "v26.197 formal byte count differs")
    distribution = v197_models.ArtifactManifest.model_validate(
        _load(root / "artifact_manifest.json")
    )
    sealed = v197_models.ArtifactManifest.model_validate(
        _load(root / "sealed_evidence_manifest.json")
    )
    report = v197_models.RepairPreflightReport.model_validate(_load(root / "report.json"))
    transition = v197_models.ProspectiveTransition.model_validate(
        _load(root / "prospective_transition.json")
    )
    contract = integration.TerminalOutcomeIntegrationContract.model_validate(
        _load(root / "terminal_to_outcome_integration_contract.json")
    )
    if (
        report.report_id != V197_REPORT_ID
        or report.source_commit != AUDITED_SOURCE_COMMIT
        or report.source_tree != AUDITED_SOURCE_TREE
        or report.sealed_evidence_artifact_root != V197_SEALED_ROOT
        or transition.transition_id != V197_TRANSITION_ID
        or transition.next_stage != models.AUTHORIZED_STAGE
        or distribution.artifact_root != V197_DISTRIBUTION_ROOT
        or distribution.file_count != 47
        or sealed.artifact_root != V197_SEALED_ROOT
        or sealed.file_count != 45
        or contract.contract_id != V197_INTEGRATION_CONTRACT_ID
    ):
        _fail("freeze.identity", "v26.197 report, transition, Root, or Contract differs")
    distribution_members = {item.relative_path: item for item in distribution.members}
    observed_paths = {item.relative_path for item in bindings}
    if observed_paths != set(distribution_members) | {"artifact_manifest.json"}:
        _fail("freeze.manifest", "v26.197 distribution member set differs")
    for relative_path, member in distribution_members.items():
        payload = (root / relative_path).read_bytes()
        if (member.sha256, member.byte_count) != (_sha256_bytes(payload), len(payload)):
            _fail("freeze.member", f"v26.197 member differs:{relative_path}")
    v195_root = repository_root / V195_DIR
    expected_six = (
        authority.FreshTerminalRegistry.model_validate(
            _load(v195_root / "fresh_terminal_registry.json")
        ).registry_id,
        authority.FreshRawExecutionDescriptorContract.model_validate(
            _load(v195_root / "fresh_raw_execution_descriptor_contract.json")
        ).contract_id,
        authority.FreshJobResultDescriptorContract.model_validate(
            _load(v195_root / "fresh_job_result_descriptor_contract.json")
        ).contract_id,
        authority.FreshJobBoundAttemptTraceContract.model_validate(
            _load(v195_root / "fresh_job_bound_attempt_trace_contract.json")
        ).contract_id,
        authority.FreshOutcomeRowContract.model_validate(
            _load(v195_root / "fresh_outcome_row_contract.json")
        ).contract_id,
        authority.FreshExactEvidenceSetEvaluatorContract.model_validate(
            _load(v195_root / "fresh_exact_evidence_set_evaluator_contract.json")
        ).contract_id,
    )
    observed_six = (
        contract.terminal_registry_id,
        contract.raw_descriptor_contract_id,
        contract.result_descriptor_contract_id,
        contract.attempt_trace_contract_id,
        contract.outcome_row_contract_id,
        contract.evaluator_contract_id,
    )
    if observed_six != expected_six:
        _fail("freeze.authority", "v26.197 six authority identities differ")
    return cast(
        models.V197FreezeAudit,
        models.make_identity(
            models.V197FreezeAudit,
            {
                "authorization_id": authorization.authorization_id,
                "v197_report_id": report.report_id,
                "v197_transition_id": transition.transition_id,
                "v197_source_commit": report.source_commit,
                "v197_source_tree": report.source_tree,
                "v197_sealed_artifact_root": sealed.artifact_root,
                "v197_distribution_artifact_root": distribution.artifact_root,
            },
            field="audit_id",
            prefix="finance_v26_198_v197_source_artifact_freeze_audit:",
        ),
    )


def _run(*args: str, env: dict[str, str] | None = None) -> None:
    try:
        subprocess.run(args, check=True, capture_output=True, env=env)
    except subprocess.CalledProcessError as error:
        stderr = (error.stderr or b"").decode("utf-8", errors="replace")
        _fail("subprocess", stderr.strip() or repr(error.cmd))


def _credential_free_environment(source_root: Path) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not (
            key.endswith("_API_KEY")
            or "TOKEN" in key
            or "SECRET" in key
            or "PASSWORD" in key
            or "CREDENTIAL" in key
        )
    }
    environment["PYTHONPATH"] = str(source_root / "trusted_data_synthesis/src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _formal_rebuild(
    *,
    repository_root: Path,
    authorization: models.IndependentAuditAuthorization,
    freeze: models.V197FreezeAudit,
) -> models.FormalRebuildAudit:
    frozen_root = repository_root / AUDITED_V197_DIR
    frozen = _recursive_bindings(frozen_root)
    with tempfile.TemporaryDirectory(prefix="v26-198-v197-rebuild-") as temporary:
        temporary_root = Path(temporary)
        clone = temporary_root / "source"
        rebuilt = temporary_root / "rebuilt"
        _run(
            "git",
            "clone",
            "--quiet",
            "--shared",
            "--no-checkout",
            str(repository_root),
            str(clone),
        )
        _run("git", "-C", str(clone), "sparse-checkout", "init", "--no-cone")
        _run(
            "git",
            "-C",
            str(clone),
            "sparse-checkout",
            "set",
            "/trusted_data_synthesis/src/",
            "/" + OLD_AUDIT_FIXTURE,
            "/" + V194_DIR + "/",
            "/" + V195_DIR + "/",
            "/" + V196_DIR + "/",
            "/" + v194.V192_DIR + "/",
            "/" + v194.V193_DIR + "/",
            "/" + v194.MODEL_PROFILE,
        )
        _run(
            "git",
            "-C",
            str(clone),
            "checkout",
            "--quiet",
            "--detach",
            AUDITED_SOURCE_COMMIT,
        )
        detached_commit, detached_tree = _git_identity(clone)
        if (detached_commit, detached_tree) != (AUDITED_SOURCE_COMMIT, AUDITED_SOURCE_TREE):
            _fail("rebuild.source", "detached v26.197 source identity differs")
        environment = _credential_free_environment(clone)
        _run(
            sys.executable,
            "-m",
            "trusted_synthesis.experiments.vtdo_experiment."
            "phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight",
            "--repository-root",
            str(clone),
            "--audit-path",
            str(clone / OLD_AUDIT_FIXTURE),
            "--output-dir",
            str(rebuilt),
            env=environment,
        )
        observed = _recursive_bindings(rebuilt)
        frozen_map = {item.relative_path: item for item in frozen}
        observed_map = {item.relative_path: item for item in observed}
        if set(frozen_map) != set(observed_map):
            _fail("rebuild.paths", "rebuilt v26.197 path set differs")
        if frozen_map != observed_map:
            _fail("rebuild.bindings", "rebuilt v26.197 hashes or byte counts differ")
        byte_matches = sum(
            (frozen_root / relative).read_bytes() == (rebuilt / relative).read_bytes()
            for relative in sorted(frozen_map)
        )
        if byte_matches != EXPECTED_V197_FORMAL_FILE_COUNT:
            _fail("rebuild.bytes", "rebuilt v26.197 actual bytes differ")
    return cast(
        models.FormalRebuildAudit,
        models.make_identity(
            models.FormalRebuildAudit,
            {
                "authorization_id": authorization.authorization_id,
                "freeze_audit_id": freeze.audit_id,
                "detached_source_commit": AUDITED_SOURCE_COMMIT,
                "detached_source_tree": AUDITED_SOURCE_TREE,
            },
            field="audit_id",
            prefix="finance_v26_198_v197_formal_rebuild_audit:",
        ),
    )


def _load_parents(repository_root: Path) -> tuple[Any, ...]:
    v194_root = repository_root / V194_DIR
    v195_root = repository_root / V195_DIR
    return (
        v194_models.AuthoritativeRunnerPackageCatalog.model_validate(
            _load(v194_root / "authoritative_runner_package_catalog.json")
        ),
        v194_models.AuthoritativeDevelopmentManifest.model_validate(
            _load(v194_root / "authoritative_development_manifest.json")
        ),
        v194_models.AuthoritativeRunnerContract.model_validate(
            _load(v194_root / "authoritative_runner_contract.json")
        ),
        v194_models.AuthoritativeExecutionContract.model_validate(
            _load(v194_root / "authoritative_execution_contract.json")
        ),
        authority.FreshTerminalRegistry.model_validate(
            _load(v195_root / "fresh_terminal_registry.json")
        ),
        authority.FreshRawExecutionDescriptorContract.model_validate(
            _load(v195_root / "fresh_raw_execution_descriptor_contract.json")
        ),
        authority.FreshJobResultDescriptorContract.model_validate(
            _load(v195_root / "fresh_job_result_descriptor_contract.json")
        ),
        authority.FreshJobBoundAttemptTraceContract.model_validate(
            _load(v195_root / "fresh_job_bound_attempt_trace_contract.json")
        ),
        authority.FreshOutcomeRowContract.model_validate(
            _load(v195_root / "fresh_outcome_row_contract.json")
        ),
        authority.FreshExactEvidenceSetEvaluatorContract.model_validate(
            _load(v195_root / "fresh_exact_evidence_set_evaluator_contract.json")
        ),
    )


def _candidate_integration_objects(
    repository_root: Path,
) -> tuple[
    integration.ExternalTerminalOutcomeRepairAuthorization,
    bytes,
    integration.AuthorizationAdmission,
    integration.TerminalOutcomeIntegrationContract,
]:
    root = repository_root / AUDITED_V197_DIR
    authorization = integration.ExternalTerminalOutcomeRepairAuthorization.model_validate(
        _load(root / "external_repair_authorization.json")
    )
    authorization_bytes = (root / "external_v26_196_repair_audit.txt").read_bytes()
    admission = integration.AuthorizationAdmission.model_validate(
        _load(root / "authorization_admission.json")
    )
    contract = integration.TerminalOutcomeIntegrationContract.model_validate(
        _load(root / "terminal_to_outcome_integration_contract.json")
    )
    strict_admission = integration.PrecredentialAuthorizationGuard().admit(
        authorization=authorization,
        authorization_bytes=authorization_bytes,
        provider_execution_requested=False,
    )
    if strict_admission != admission or contract.authorization_id != authorization.authorization_id:
        _fail("candidate.authorization", "v26.197 authorization admission differs")
    return authorization, authorization_bytes, admission, contract


def _prompt_inputs(
    repository_root: Path,
    manifest: v194_models.AuthoritativeDevelopmentManifest,
) -> tuple[
    v192.JsonExplicitPromptContract,
    v192.JsonExplicitPromptSchema,
    AgentModelConfig,
    dict[str, dict[str, Any] | str],
]:
    v192_root = repository_root / v194.V192_DIR
    prompt_contract = v192.JsonExplicitPromptContract.model_validate(
        _load(v192_root / "json_explicit_prompt_contract.json")
    )
    prompt_schema = v192.JsonExplicitPromptSchema.model_validate(
        _load(v192_root / "json_explicit_prompt_schema.json")
    )
    config = AgentModelConfig.model_validate(_load(repository_root / v194.MODEL_PROFILE)["model"])
    evidence = v193_models.ExactPromptEvidenceSet.model_validate(
        _load(repository_root / v194.V193_DIR / "exact_prompt_evidence_set.json")
    )
    by_source: dict[str, list[Any]] = {}
    for row in evidence.rows:
        by_source.setdefault(row.coordinate.fresh_job_id, []).append(row)
    cores: dict[str, dict[str, Any] | str] = {}
    for job in manifest.jobs:
        source = min(
            by_source[job.source_job_id],
            key=lambda item: item.coordinate.invocation_index,
        )
        cores[job.job_id] = json.loads(source.rendered_prompt)["prompt_core"]
    return prompt_contract, prompt_schema, config, cores


def _control_payload(**values: Any) -> integration.DispatchControlPayload:
    return cast(
        integration.DispatchControlPayload,
        _make_model(
            integration.DispatchControlPayload,
            values,
            field="payload_id",
            prefix="terminal_dispatch_control_payload:",
        ),
    )


def _independent_payloads() -> dict[str, integration.DispatchControlPayload]:
    return {
        "completed_qualified": _control_payload(
            phase="final",
            task_completion=True,
            task_verifier_invoked=True,
            final_response_abi_valid=True,
            final_result_id=canonical_hash(
                {"control": "completed_qualified"},
                prefix="v26_197_control_final_result:",
            ),
            final_base_valid=True,
            final_mechanism_qualified=True,
            final_qualified_valid=True,
        ),
        "completed_invalid": _control_payload(
            phase="final",
            task_completion=True,
            task_verifier_invoked=True,
            final_response_abi_valid=True,
            final_result_id=canonical_hash(
                {"control": "completed_invalid"},
                prefix="v26_197_control_final_result:",
            ),
            final_base_valid=False,
            final_mechanism_qualified=True,
            final_qualified_valid=False,
        ),
        "first_response_abi_invalid": _control_payload(
            phase="primary_action",
            response_abi_valid=False,
        ),
        "first_action_reference_invalid": _control_payload(
            phase="primary_action",
            response_abi_valid=True,
            action_reference_valid=False,
        ),
        "correction_response_abi_invalid": _control_payload(
            phase="correction_action",
            response_abi_valid=True,
            action_reference_valid=True,
            state_precondition_valid=False,
            action_accepted=False,
            correction_invoked=True,
            correction_response_abi_valid=False,
        ),
        "correction_action_reference_invalid": _control_payload(
            phase="correction_action",
            response_abi_valid=True,
            action_reference_valid=True,
            state_precondition_valid=False,
            action_accepted=False,
            correction_invoked=True,
            correction_response_abi_valid=True,
            correction_action_reference_valid=False,
        ),
        "correction_attempt_typed_invalid": _control_payload(
            phase="correction_action",
            response_abi_valid=True,
            action_reference_valid=True,
            state_precondition_valid=False,
            action_accepted=False,
            correction_invoked=True,
            correction_response_abi_valid=True,
            correction_action_reference_valid=True,
            correction_state_precondition_valid=False,
            correction_accepted=False,
        ),
        "final_response_abi_invalid": _control_payload(
            phase="final",
            task_completion=True,
            task_verifier_invoked=False,
            final_response_abi_valid=False,
        ),
    }


@dataclass(frozen=True)
class _IndependentClientPlan:
    payload: dict[str, Any] | None = None
    error_type: type[RuntimeError] | None = None
    error_reason: str = ""


def _independent_client_plans() -> tuple[_IndependentClientPlan, ...]:
    payloads = _independent_payloads()
    exceptions: dict[str, type[RuntimeError]] = {
        "provider_failure_no_payload": integration.ProviderNoPayloadError,
        "provider_transport_failure": integration.ProviderTransportError,
        "resource_budget_exhausted": integration.ResourceBudgetError,
        "instrument_failure": integration.InstrumentIntegrityError,
        "provider_identity_failure": integration.ProviderIdentityIntegrityError,
        "thinking_integrity_failure": integration.ThinkingIntegrityError,
        "usage_integrity_failure": integration.UsageIntegrityError,
    }
    plans: list[_IndependentClientPlan] = []
    for terminal in REACHABLE_TERMINALS:
        if terminal == "privacy_rejection":
            plans.append(_IndependentClientPlan(payload={"reasoning_control": "private"}))
        elif terminal in exceptions:
            plans.append(
                _IndependentClientPlan(
                    error_type=exceptions[terminal],
                    error_reason=f"zero-provider observed failure:{terminal}",
                )
            )
        else:
            plans.append(
                _IndependentClientPlan(
                    payload=payloads[terminal].model_dump(mode="json", warnings=False)
                )
            )
    return tuple(plans)


class _IndependentZeroProviderClient:
    def __init__(
        self,
        config: AgentModelConfig,
        plans: tuple[_IndependentClientPlan, ...],
    ) -> None:
        self.config = config
        self._plans = plans
        self.local_invocation_count = 0

    def complete_json_certified(
        self,
        prompt: str,
        certificate: StageOneRequestBindingCertificate,
    ) -> execution_kernel.CertifiedClientResponse:
        plan = self._plans[self.local_invocation_count]
        self.local_invocation_count += 1
        if plan.error_type is not None:
            raise plan.error_type(plan.error_reason)
        if plan.payload is None:
            _fail("replay.client", "independent client plan has no payload")
        body_sha = _sha256_bytes(
            _canonical_bytes(
                make_stage_one_request_body(self.config, prompt),
                newline=False,
            )
        )
        payload_bytes = _canonical_bytes(plan.payload, newline=False)
        telemetry = ModelCallTelemetry(
            provider="credential_free_terminal_integration_preflight",
            endpoint_host="none",
            model_requested=self.config.model,
            model_selected=self.config.model,
            response_model=self.config.model,
            request_hash=_sha256_bytes(prompt.encode("utf-8")),
            response_hash=_sha256_bytes(payload_bytes),
            http_success=False,
            json_contract_success=True,
            response_content_length=len(payload_bytes),
            reasoning_content_present=False,
            reasoning_content_length=0,
            reasoning_tokens=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )
        return cast(
            execution_kernel.CertifiedClientResponse,
            _make_model(
                execution_kernel.CertifiedClientResponse,
                {
                    "payload": plan.payload,
                    "telemetry": telemetry,
                    "consumed_request_binding_certificate_id": certificate.certificate_id,
                    "transmitted_request_body_sha256": body_sha,
                    "actual_prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
                    "provider_call_made": False,
                },
                field="response_id",
                prefix="authoritative_kernel_certified_client_response:",
            ),
        )


class _CountingFreshWriter:
    def __init__(self, root: Path) -> None:
        self._writer = v195.FreshOutcomeArtifactWriter(root)
        self.events: list[tuple[str, str]] = []

    def write_raw(self, *, job_id: str, payload: Any) -> tuple[str, int]:
        self.events.append((job_id, "raw"))
        return self._writer.write_raw(job_id=job_id, payload=payload)

    def write_result(self, *, job_id: str, payload: Any) -> tuple[str, int]:
        self.events.append((job_id, "result"))
        return self._writer.write_result(job_id=job_id, payload=payload)

    def assert_closed(self) -> None:
        self._writer.assert_closed()


def _prompt_kind(
    terminal: str,
) -> tuple[execution_kernel.PromptKind, execution_kernel.PublicAttemptPhase]:
    if terminal.startswith("correction_"):
        return "correction", "semantic_recovery"
    if terminal.startswith("completed_") or terminal == "final_response_abi_invalid":
        return "final", "primary"
    return "action", "primary"


def _independent_terminal_kind(evidence: integration.TerminalExecutionEvidence) -> str:
    exception_map = {
        "ProviderNoPayloadError": "provider_failure_no_payload",
        "ProviderTransportError": "provider_transport_failure",
        "PrivacyProjectionRejected": "privacy_rejection",
        "ResourceBudgetError": "resource_budget_exhausted",
        "InstrumentIntegrityError": "instrument_failure",
        "ProviderIdentityIntegrityError": "provider_identity_failure",
        "ThinkingIntegrityError": "thinking_integrity_failure",
        "UsageIntegrityError": "usage_integrity_failure",
    }
    if evidence.exception_type is not None:
        return exception_map[evidence.exception_type]
    payload = evidence.public_payload
    if payload is None:
        _fail("reconstruct.terminal", "terminal evidence has no public payload")
    if payload.phase == "primary_action":
        if payload.response_abi_valid is False:
            return "first_response_abi_invalid"
        if payload.action_reference_valid is False:
            return "first_action_reference_invalid"
    elif payload.phase == "correction_action":
        if payload.correction_response_abi_valid is False:
            return "correction_response_abi_invalid"
        if payload.correction_action_reference_valid is False:
            return "correction_action_reference_invalid"
        if payload.correction_state_precondition_valid is False:
            return "correction_attempt_typed_invalid"
    elif payload.final_response_abi_valid is False:
        return "final_response_abi_invalid"
    elif payload.final_qualified_valid is True:
        return "completed_qualified"
    elif payload.task_verifier_invoked:
        return "completed_invalid"
    _fail("reconstruct.terminal", "evidence does not determine a terminal")


def _independent_decision(
    *,
    evidence: integration.TerminalExecutionEvidence,
    contract: integration.TerminalOutcomeIntegrationContract,
    registry: authority.FreshTerminalRegistry,
) -> integration.TerminalDecision:
    terminal = _independent_terminal_kind(evidence)
    policies = {item.terminal_kind: item for item in registry.policies}
    policy = policies[cast(authority.TerminalKind, terminal)]
    if policy.registration_status != "reachable":
        _fail("reconstruct.decision", "independent dispatcher selected excluded policy")
    return cast(
        integration.TerminalDecision,
        _make_model(
            integration.TerminalDecision,
            {
                "integration_contract_id": contract.contract_id,
                "terminal_registry_id": registry.registry_id,
                "terminal_policy_id": policy.policy_id,
                "execution_evidence_id": evidence.evidence_id,
                "job_id": evidence.job_id,
                "terminal_kind": terminal,
            },
            field="decision_id",
            prefix="authoritative_terminal_dispatch_decision:",
        ),
    )


def _independent_attempt(
    evidence: integration.TerminalExecutionEvidence,
    terminal: str,
) -> integration.IntegratedComponentAttemptEvidence:
    payload = evidence.public_payload
    values: dict[str, Any] = {
        "component_index": evidence.component_index,
        "component_key": evidence.component_key,
        "reached_state_token": canonical_hash(
            {
                "job_id": evidence.job_id,
                "component_index": evidence.component_index,
                "component_key": evidence.component_key,
                "integration_contract_id": evidence.integration_contract_id,
            },
            prefix="integrated_terminal_control_state:",
        ).split(":", 1)[1][:24],
        "first_response_abi_valid": None,
        "first_action_reference_valid": None,
        "first_action_state_precondition_valid": None,
        "first_action_accepted": None,
        "correction_invoked": False,
        "correction_response_abi_valid": None,
        "correction_action_reference_valid": None,
        "correction_state_precondition_valid": None,
        "correction_accepted": None,
        "committed": False,
        "terminal": True,
        "invocation_receipt_ids": evidence.invocation_receipt_ids,
    }
    if payload is not None and payload.phase in {"primary_action", "correction_action"}:
        values.update(
            {
                "first_response_abi_valid": payload.response_abi_valid,
                "first_action_reference_valid": payload.action_reference_valid,
                "first_action_state_precondition_valid": payload.state_precondition_valid,
                "first_action_accepted": payload.action_accepted,
                "correction_invoked": payload.correction_invoked,
                "correction_response_abi_valid": payload.correction_response_abi_valid,
                "correction_action_reference_valid": payload.correction_action_reference_valid,
                "correction_state_precondition_valid": (
                    payload.correction_state_precondition_valid
                ),
                "correction_accepted": payload.correction_accepted,
            }
        )
    elif payload is not None and payload.phase == "final":
        values.update(
            {
                "first_response_abi_valid": True,
                "first_action_reference_valid": True,
                "first_action_state_precondition_valid": True,
                "first_action_accepted": True,
                "committed": True,
                "terminal": False,
            }
        )
    if terminal in {"completed_qualified", "completed_invalid"}:
        values["committed"] = True
        values["terminal"] = False
    return cast(
        integration.IntegratedComponentAttemptEvidence,
        _make_model(
            integration.IntegratedComponentAttemptEvidence,
            values,
            field="attempt_id",
            prefix="fresh_kernel_component_attempt:",
        ),
    )


def _independent_validity(
    evidence: integration.TerminalExecutionEvidence,
    terminal: str,
) -> authority.FreshTerminalValidity:
    payload = evidence.public_payload
    values: dict[str, Any] = {
        "terminal_kind": terminal,
        "task_completion": None,
        "task_verifier_invoked": False,
        "final_response_abi_valid": None,
        "final_result_id": None,
        "final_base_valid": None,
        "final_mechanism_qualified": None,
        "final_qualified_valid": None,
    }
    if payload is not None and payload.phase == "final":
        values.update(
            {
                "task_completion": payload.task_completion,
                "task_verifier_invoked": payload.task_verifier_invoked,
                "final_response_abi_valid": payload.final_response_abi_valid,
                "final_result_id": payload.final_result_id,
                "final_base_valid": payload.final_base_valid,
                "final_mechanism_qualified": payload.final_mechanism_qualified,
                "final_qualified_valid": payload.final_qualified_valid,
            }
        )
    return cast(
        authority.FreshTerminalValidity,
        _make_model(
            authority.FreshTerminalValidity,
            values,
            field="validity_id",
            prefix="fresh_kernel_terminal_validity:",
        ),
    )


_FAILURE_STAGE: Final[dict[str, authority.FailureStage]] = {
    "completed_invalid": "base_answer",
    "first_response_abi_invalid": "action_abi",
    "correction_response_abi_invalid": "action_abi",
    "first_action_reference_invalid": "action_reference",
    "correction_action_reference_invalid": "action_reference",
    "correction_attempt_typed_invalid": "state_precondition",
    "final_response_abi_invalid": "final_abi",
    "provider_failure_no_payload": "provider",
    "provider_transport_failure": "transport",
    "privacy_rejection": "privacy",
    "resource_budget_exhausted": "resource",
    "instrument_failure": "instrument",
    "provider_identity_failure": "model_identity",
    "thinking_integrity_failure": "thinking",
    "usage_integrity_failure": "usage",
}


def _independent_failure_loci(
    *,
    terminal: str,
    evidence: integration.TerminalExecutionEvidence,
    source_descriptor_id: str,
) -> tuple[authority.FreshFailureLocus, ...]:
    if terminal == "completed_qualified":
        return ()
    return (
        cast(
            authority.FreshFailureLocus,
            _make_model(
                authority.FreshFailureLocus,
                {
                    "stage": _FAILURE_STAGE[terminal],
                    "component_key": evidence.component_key,
                    "attempt_index": 1 if terminal.startswith("correction_") else 0,
                    "reason_code": terminal,
                    "source_descriptor_id": source_descriptor_id,
                },
                field="locus_id",
                prefix="fresh_kernel_failure_locus:",
            ),
        ),
    )


def _independent_reconstruct_bundle(
    *,
    output_dir: Path,
    candidate_root: Path,
    bundle: integration.IntegratedFreshEvidenceBundle,
    contract: integration.TerminalOutcomeIntegrationContract,
    admission: integration.AuthorizationAdmission,
    registry: authority.FreshTerminalRegistry,
    job: v194_models.AuthoritativeDevelopmentJob,
    manifest: v194_models.AuthoritativeDevelopmentManifest,
    runner: v194_models.AuthoritativeRunnerContract,
    execution: v194_models.AuthoritativeExecutionContract,
    raw_contract: authority.FreshRawExecutionDescriptorContract,
    result_contract: authority.FreshJobResultDescriptorContract,
    trace_contract: authority.FreshJobBoundAttemptTraceContract,
    outcome_contract: authority.FreshOutcomeRowContract,
) -> tuple[integration.IntegratedFreshEvidenceBundle, str]:
    raw_path = output_dir / bundle.raw.artifact_relative_path
    result_path = output_dir / bundle.result.artifact_relative_path
    raw_bytes = raw_path.read_bytes()
    result_bytes = result_path.read_bytes()
    if (
        len(raw_bytes) != bundle.raw.artifact_byte_count
        or _sha256_bytes(raw_bytes) != bundle.raw.artifact_sha256
        or len(result_bytes) != bundle.result.artifact_byte_count
        or _sha256_bytes(result_bytes) != bundle.result.artifact_sha256
    ):
        _fail("reconstruct.bytes", "actual replay descriptor bytes differ")
    raw_payload = integration.IntegratedFreshRawExecutionPayload.model_validate(
        json.loads(raw_bytes)
    )
    result_payload = authority.FreshJobResultPayload.model_validate(json.loads(result_bytes))
    if raw_bytes != _canonical_bytes(
        raw_payload, newline=False
    ) or result_bytes != _canonical_bytes(result_payload, newline=False):
        _fail("reconstruct.canonical", "actual Raw or Result is not canonical typed JSON")
    decision = _independent_decision(
        evidence=raw_payload.terminal_evidence,
        contract=contract,
        registry=registry,
    )
    terminal = decision.terminal_kind
    attempt = _independent_attempt(raw_payload.terminal_evidence, terminal)
    validity = _independent_validity(raw_payload.terminal_evidence, terminal)
    raw = cast(
        authority.FreshRawExecutionDescriptor,
        _make_model(
            authority.FreshRawExecutionDescriptor,
            {
                "descriptor_contract_id": raw_contract.contract_id,
                "evidence_kind": "scripted_preflight_control",
                "job_id": job.job_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "execution_contract_id": execution.contract_id,
                "package_id": job.package_id,
                "replica_index": job.replica_index,
                "raw_namespace": job.raw_namespace,
                "artifact_relative_path": authority.expected_raw_artifact_filename(job),
                "artifact_sha256": _sha256_bytes(raw_bytes),
                "artifact_byte_count": len(raw_bytes),
                "payload_id": raw_payload.payload_id,
            },
            field="raw_execution_id",
            prefix="fresh_kernel_raw_execution_descriptor:",
        ),
    )
    result = cast(
        authority.FreshJobResultDescriptor,
        _make_model(
            authority.FreshJobResultDescriptor,
            {
                "descriptor_contract_id": result_contract.contract_id,
                "evidence_kind": "scripted_preflight_control",
                "job_id": job.job_id,
                "raw_execution_id": raw.raw_execution_id,
                "execution_contract_id": execution.contract_id,
                "result_namespace": job.result_namespace,
                "artifact_relative_path": authority.expected_result_artifact_filename(job),
                "artifact_sha256": _sha256_bytes(result_bytes),
                "artifact_byte_count": len(result_bytes),
                "payload_id": result_payload.payload_id,
            },
            field="result_id",
            prefix="fresh_kernel_job_result_descriptor:",
        ),
    )
    loci = _independent_failure_loci(
        terminal=terminal,
        evidence=raw_payload.terminal_evidence,
        source_descriptor_id=raw.raw_execution_id,
    )
    trace = cast(
        integration.IntegratedFreshJobBoundAttemptTrace,
        _make_model(
            integration.IntegratedFreshJobBoundAttemptTrace,
            {
                "trace_contract_id": trace_contract.contract_id,
                "integration_contract_id": contract.contract_id,
                "authorization_admission_id": admission.admission_id,
                "job_id": job.job_id,
                "raw_execution_id": raw.raw_execution_id,
                "result_id": result.result_id,
                "terminal_kind": terminal,
                "terminal_evidence_id": raw_payload.terminal_evidence.evidence_id,
                "terminal_decision_id": decision.decision_id,
                "component_attempts": (attempt,),
                "failure_loci": loci,
                "correction_count": int(attempt.correction_invoked),
            },
            field="trace_id",
            prefix="fresh_kernel_job_bound_attempt_trace:",
        ),
    )
    row = cast(
        authority.FreshOutcomeRow,
        _make_model(
            authority.FreshOutcomeRow,
            {
                "outcome_contract_id": outcome_contract.contract_id,
                "evidence_kind": "scripted_preflight_control",
                "job_id": job.job_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "execution_contract_id": execution.contract_id,
                "package_id": job.package_id,
                "replica_index": job.replica_index,
                "raw_execution_id": raw.raw_execution_id,
                "result_id": result.result_id,
                "trace_id": trace.trace_id,
                "terminal_registry_id": registry.registry_id,
                "terminal_kind": terminal,
                "correction_count": trace.correction_count,
                "task_completion": validity.task_completion,
                "task_verifier_invoked": validity.task_verifier_invoked,
                "final_result_id": validity.final_result_id,
                "final_base_valid": validity.final_base_valid,
                "final_mechanism_qualified": validity.final_mechanism_qualified,
                "final_qualified_valid": validity.final_qualified_valid,
                "failure_locus_ids": tuple(item.locus_id for item in loci),
                "formal_empirical_row": False,
            },
            field="row_id",
            prefix="fresh_kernel_outcome_row:",
        ),
    )
    reconstructed = integration.IntegratedFreshEvidenceBundle(
        raw=raw,
        result=result,
        trace=trace,
        row=row,
    )
    if (
        reconstructed != bundle
        or decision != raw_payload.terminal_decision
        or raw_payload.component_attempts != (attempt,)
        or result_payload.validity != validity
    ):
        _fail("reconstruct.bundle", "independent Trace or Outcome reconstruction differs")
    candidate_raw = candidate_root / bundle.raw.artifact_relative_path
    candidate_result = candidate_root / bundle.result.artifact_relative_path
    if candidate_raw.read_bytes() != raw_bytes or candidate_result.read_bytes() != result_bytes:
        _fail("reconstruct.candidate", "independent Raw or Result differs from v26.197")
    return reconstructed, terminal


def _independent_runtime_replay(
    *,
    repository_root: Path,
    output_dir: Path,
    authorization: models.IndependentAuditAuthorization,
) -> tuple[
    models.IndependentRuntimeReplayAudit,
    tuple[integration.IntegratedFreshEvidenceBundle, ...],
    int,
    int,
]:
    candidate_authorization, candidate_bytes, admission, contract = _candidate_integration_objects(
        repository_root
    )
    parents = _load_parents(repository_root)
    catalog, manifest, runner, execution = parents[:4]
    registry, raw_contract, result_contract, trace_contract, outcome_contract, evaluator = parents[
        4:
    ]
    prompt_contract, prompt_schema, config, cores = _prompt_inputs(repository_root, manifest)
    plans = _independent_client_plans()
    clients: list[_IndependentZeroProviderClient] = []
    writers: list[_CountingFreshWriter] = []
    old_complete_call_count = 0
    caller_terminal_rejection_count = 0
    original_old_complete = execution_kernel.AuthoritativeJsonExplicitExecutionKernel.complete_job

    def forbidden_old_complete(*args: Any, **kwargs: Any) -> Any:
        nonlocal old_complete_call_count
        old_complete_call_count += 1
        raise AssertionError("successor replay called legacy fixture completion")

    setattr(  # noqa: B010
        execution_kernel.AuthoritativeJsonExplicitExecutionKernel,
        "complete_job",
        forbidden_old_complete,
    )
    try:
        with tempfile.TemporaryDirectory(prefix="v26-198-kernel-journal-") as temporary:
            journal_root = Path(temporary)

            def client_factory() -> _IndependentZeroProviderClient:
                client = _IndependentZeroProviderClient(config, plans)
                clients.append(client)
                return client

            def kernel_writer_factory() -> execution_kernel.NoReplaceKernelJournalWriter:
                return execution_kernel.NoReplaceKernelJournalWriter(journal_root)

            def outcome_writer_factory() -> _CountingFreshWriter:
                writer = _CountingFreshWriter(output_dir)
                writers.append(writer)
                return writer

            kernel = integration.FreshOutcomeIntegratedExecutionKernel(
                authorization=candidate_authorization,
                authorization_bytes=candidate_bytes,
                integration_contract=contract,
                terminal_registry=registry,
                catalog=catalog,
                manifest=manifest,
                runner=runner,
                execution=execution,
                raw_contract=raw_contract,
                result_contract=result_contract,
                trace_contract=trace_contract,
                outcome_contract=outcome_contract,
                evaluator_contract=evaluator,
                prompt_contract=prompt_contract,
                prompt_schema=prompt_schema,
                client_factory=client_factory,
                kernel_writer_factory=kernel_writer_factory,
                outcome_writer_factory=outcome_writer_factory,
            )
            jobs = tuple(sorted(manifest.jobs, key=lambda item: item.job_id))[:16]
            controls: list[models.IndependentReplayControl] = []
            reconstructed: list[integration.IntegratedFreshEvidenceBundle] = []
            for expected_terminal, job in zip(REACHABLE_TERMINALS, jobs, strict=True):
                prompt_kind, attempt_phase = _prompt_kind(expected_terminal)
                decision = kernel.invoke(
                    job_id=job.job_id,
                    logical_request_index=0,
                    prompt_kind=prompt_kind,
                    public_attempt_phase=attempt_phase,
                    core=cores[job.job_id],
                )
                bundle = kernel.complete_job(job_id=job.job_id)
                independent_bundle, observed_terminal = _independent_reconstruct_bundle(
                    output_dir=output_dir,
                    candidate_root=repository_root / AUDITED_V197_DIR,
                    bundle=bundle,
                    contract=contract,
                    admission=admission,
                    registry=registry,
                    job=job,
                    manifest=manifest,
                    runner=runner,
                    execution=execution,
                    raw_contract=raw_contract,
                    result_contract=result_contract,
                    trace_contract=trace_contract,
                    outcome_contract=outcome_contract,
                )
                if decision.terminal_kind != observed_terminal:
                    _fail("replay.dispatch", "production and independent terminal differ")
                controls.append(
                    cast(
                        models.IndependentReplayControl,
                        models.make_identity(
                            models.IndependentReplayControl,
                            {
                                "exact_job_id": job.job_id,
                                "expected_terminal_kind": expected_terminal,
                                "observed_terminal_kind": observed_terminal,
                                "terminal_decision_id": decision.decision_id,
                                "raw_execution_id": independent_bundle.raw.raw_execution_id,
                                "result_id": independent_bundle.result.result_id,
                                "trace_id": independent_bundle.trace.trace_id,
                                "outcome_row_id": independent_bundle.row.row_id,
                                "failure_locus_count": len(independent_bundle.trace.failure_loci),
                            },
                            field="control_id",
                            prefix="finance_v26_198_independent_terminal_replay_control:",
                        ),
                    )
                )
                reconstructed.append(independent_bundle)
            kernel.assert_closed()
            try:
                completion = cast(Any, kernel.complete_job)
                completion(
                    job_id=jobs[0].job_id,
                    terminal_kind="completed_qualified",
                )
            except TypeError:
                caller_terminal_rejection_count = 1
            else:
                _fail("replay.injection", "caller-supplied terminal was accepted")
    finally:
        setattr(  # noqa: B010
            execution_kernel.AuthoritativeJsonExplicitExecutionKernel,
            "complete_job",
            original_old_complete,
        )
    if len(clients) != 1 or clients[0].local_invocation_count != 16:
        _fail("replay.client", "independent client invocation count differs")
    if len(writers) != 1:
        _fail("replay.writer", "independent writer construction count differs")
    jobs = tuple(sorted(manifest.jobs, key=lambda item: item.job_id))[:16]
    expected_events = tuple(
        event for job in jobs for event in ((job.job_id, "raw"), (job.job_id, "result"))
    )
    if tuple(writers[0].events) != expected_events or old_complete_call_count:
        _fail("replay.persistence", "fresh writer order or legacy completion differs")
    audit = cast(
        models.IndependentRuntimeReplayAudit,
        models.make_identity(
            models.IndependentRuntimeReplayAudit,
            {
                "authorization_id": authorization.authorization_id,
                "integration_contract_id": contract.contract_id,
                "controls": tuple(controls),
                "old_complete_job_call_count": old_complete_call_count,
            },
            field="audit_id",
            prefix="finance_v26_198_independent_runtime_replay_audit:",
        ),
    )
    return audit, tuple(reconstructed), caller_terminal_rejection_count, len(writers[0].events)


def _find_symbol(tree: ast.Module, dotted: str) -> ast.AST:
    nodes: list[ast.AST] = list(tree.body)
    found: ast.AST | None = None
    for part in dotted.split("."):
        found = next(
            (
                item
                for item in nodes
                if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == part
            ),
            None,
        )
        if found is None:
            _fail("source.symbol", f"source symbol missing:{dotted}")
        nodes = list(found.body) if isinstance(found, ast.ClassDef) else []
    assert found is not None
    return found


def _symbol_segment(source: bytes, dotted: str) -> bytes:
    text = source.decode("utf-8")
    node = _find_symbol(ast.parse(text), dotted)
    segment = ast.get_source_segment(text, node)
    if not segment:
        _fail("source.segment", f"source segment missing:{dotted}")
    return segment.encode("utf-8")


def _dispatcher_codomain_audit(
    *,
    repository_root: Path,
    runtime: models.IndependentRuntimeReplayAudit,
    contract: integration.TerminalOutcomeIntegrationContract,
    registry: authority.FreshTerminalRegistry,
) -> models.DispatcherCodomainAudit:
    source = _git_blob(repository_root, AUDITED_SOURCE_COMMIT, CORE_SOURCE)
    current = (repository_root / CORE_SOURCE).read_bytes()
    if source != current:
        _fail("codomain.source", "current dispatcher differs from audited source commit")
    segment = _symbol_segment(source, "AuthoritativeTerminalDispatcher.dispatch")
    node = ast.parse(segment)
    literal_outputs: set[str] = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Call) or len(item.args) < 2:
            continue
        function = item.func
        if (
            isinstance(function, ast.Attribute)
            and function.attr == "_decision"
            and isinstance(item.args[1], ast.Constant)
            and isinstance(item.args[1].value, str)
        ):
            literal_outputs.add(item.args[1].value)
    registry_reachable = {
        item.terminal_kind for item in registry.policies if item.registration_status == "reachable"
    }
    registry_excluded = {
        item.terminal_kind for item in registry.policies if item.registration_status != "reachable"
    }
    actual_outputs = {item.observed_terminal_kind for item in runtime.controls}
    if (
        literal_outputs != registry_reachable
        or actual_outputs != registry_reachable
        or registry_excluded != set(EXCLUDED_TERMINALS)
    ):
        _fail("codomain.set", "dispatcher, actual, and Registry codomains differ")
    return cast(
        models.DispatcherCodomainAudit,
        models.make_identity(
            models.DispatcherCodomainAudit,
            {
                "integration_contract_id": contract.contract_id,
                "dispatcher_source_sha256": _sha256_bytes(segment),
                "registry_reachable_terminals": tuple(sorted(registry_reachable)),
                "dispatcher_literal_outputs": tuple(sorted(literal_outputs)),
                "actual_replay_outputs": tuple(sorted(actual_outputs)),
                "excluded_terminals": tuple(sorted(registry_excluded)),
            },
            field="audit_id",
            prefix="finance_v26_198_dispatcher_codomain_audit:",
        ),
    )


def _terminal_injection_audit(
    *,
    contract: integration.TerminalOutcomeIntegrationContract,
    caller_terminal_rejection_count: int,
) -> models.TerminalInjectionAudit:
    invoke_signature = inspect.signature(integration.FreshOutcomeIntegratedExecutionKernel.invoke)
    complete_signature = inspect.signature(
        integration.FreshOutcomeIntegratedExecutionKernel.complete_job
    )
    invoke_terminal_parameters = sum(
        "terminal" in name.casefold() for name in invoke_signature.parameters
    )
    completion_terminal_parameters = sum(
        "terminal" in name.casefold() for name in complete_signature.parameters
    )
    client_plan_terminal_fields = sum(
        "terminal" in item.name.casefold() for item in fields(_IndependentClientPlan)
    )
    if (
        invoke_terminal_parameters
        or completion_terminal_parameters
        or client_plan_terminal_fields
        or caller_terminal_rejection_count != 1
    ):
        _fail("injection", "terminal entered a Kernel call or caller injection was accepted")
    return cast(
        models.TerminalInjectionAudit,
        models.make_identity(
            models.TerminalInjectionAudit,
            {
                "integration_contract_id": contract.contract_id,
                "caller_supplied_terminal_rejection_count": caller_terminal_rejection_count,
            },
            field="audit_id",
            prefix="finance_v26_198_terminal_injection_audit:",
        ),
    )


def _constructor_kwargs(
    *,
    repository_root: Path,
    authorization: object | None,
    authorization_bytes: bytes | None,
    provider_execution_requested: bool,
    counters: dict[str, int],
    temporary_root: Path,
) -> dict[str, Any]:
    parents = _load_parents(repository_root)
    catalog, manifest, runner, execution = parents[:4]
    registry, raw_contract, result_contract, trace_contract, outcome_contract, evaluator = parents[
        4:
    ]
    _, _, _, contract = _candidate_integration_objects(repository_root)
    prompt_contract, prompt_schema, config, _cores = _prompt_inputs(repository_root, manifest)
    plans = _independent_client_plans()

    def client_factory() -> _IndependentZeroProviderClient:
        counters["client"] += 1
        return _IndependentZeroProviderClient(config, plans)

    def kernel_writer_factory() -> execution_kernel.NoReplaceKernelJournalWriter:
        counters["kernel_writer"] += 1
        return execution_kernel.NoReplaceKernelJournalWriter(temporary_root / "journal")

    def outcome_writer_factory() -> v195.FreshOutcomeArtifactWriter:
        counters["outcome_writer"] += 1
        return v195.FreshOutcomeArtifactWriter(temporary_root / "outcome")

    return {
        "authorization": authorization,
        "authorization_bytes": authorization_bytes,
        "integration_contract": contract,
        "terminal_registry": registry,
        "catalog": catalog,
        "manifest": manifest,
        "runner": runner,
        "execution": execution,
        "raw_contract": raw_contract,
        "result_contract": result_contract,
        "trace_contract": trace_contract,
        "outcome_contract": outcome_contract,
        "evaluator_contract": evaluator,
        "prompt_contract": prompt_contract,
        "prompt_schema": prompt_schema,
        "client_factory": client_factory,
        "kernel_writer_factory": kernel_writer_factory,
        "outcome_writer_factory": outcome_writer_factory,
        "provider_execution_requested": provider_execution_requested,
    }


def _authorization_ordering_control(
    *,
    repository_root: Path,
    control_name: str,
    authorization: object | None,
    authorization_bytes: bytes | None,
    provider_execution_requested: bool,
    admitted: bool,
) -> models.AuthorizationOrderingControl:
    counters = {"client": 0, "kernel_writer": 0, "outcome_writer": 0}
    with tempfile.TemporaryDirectory(prefix=f"v26-198-auth-{control_name}-") as temporary:
        kwargs = _constructor_kwargs(
            repository_root=repository_root,
            authorization=authorization,
            authorization_bytes=authorization_bytes,
            provider_execution_requested=provider_execution_requested,
            counters=counters,
            temporary_root=Path(temporary),
        )
        rejected = False
        try:
            integration.FreshOutcomeIntegratedExecutionKernel(**kwargs)
        except (TypeError, ValueError):
            rejected = True
    if admitted:
        if rejected or counters != {"client": 1, "kernel_writer": 1, "outcome_writer": 1}:
            _fail("authorization.control", f"legal authorization failed:{control_name}")
    elif not rejected or any(counters.values()):
        _fail("authorization.control", f"invalid authorization reached a factory:{control_name}")
    return cast(
        models.AuthorizationOrderingControl,
        models.make_identity(
            models.AuthorizationOrderingControl,
            {
                "control_name": control_name,
                "admitted": admitted,
                "rejected": not admitted,
                "client_factory_count": counters["client"],
                "kernel_writer_factory_count": counters["kernel_writer"],
                "outcome_writer_factory_count": counters["outcome_writer"],
            },
            field="control_id",
            prefix="finance_v26_198_authorization_ordering_control:",
        ),
    )


def _authorization_ordering_audit(
    *,
    repository_root: Path,
    authorization: models.IndependentAuditAuthorization,
) -> models.AuthorizationOrderingAudit:
    candidate, candidate_bytes, _admission, _contract = _candidate_integration_objects(
        repository_root
    )
    self_declared = candidate.model_copy(update={"authorization_id": "self_declared"})
    controls = (
        _authorization_ordering_control(
            repository_root=repository_root,
            control_name="legal_preflight_parent",
            authorization=candidate,
            authorization_bytes=candidate_bytes,
            provider_execution_requested=False,
            admitted=True,
        ),
        _authorization_ordering_control(
            repository_root=repository_root,
            control_name="missing_parent",
            authorization=None,
            authorization_bytes=candidate_bytes,
            provider_execution_requested=False,
            admitted=False,
        ),
        _authorization_ordering_control(
            repository_root=repository_root,
            control_name="modified_parent_bytes",
            authorization=candidate,
            authorization_bytes=candidate_bytes + b"modified",
            provider_execution_requested=False,
            admitted=False,
        ),
        _authorization_ordering_control(
            repository_root=repository_root,
            control_name="self_declared_parent",
            authorization=self_declared,
            authorization_bytes=candidate_bytes,
            provider_execution_requested=False,
            admitted=False,
        ),
        _authorization_ordering_control(
            repository_root=repository_root,
            control_name="cross_experiment_parent",
            authorization=authorization,
            authorization_bytes=candidate_bytes,
            provider_execution_requested=False,
            admitted=False,
        ),
        _authorization_ordering_control(
            repository_root=repository_root,
            control_name="legal_parent_provider_request",
            authorization=candidate,
            authorization_bytes=candidate_bytes,
            provider_execution_requested=True,
            admitted=False,
        ),
    )
    source = _git_blob(repository_root, AUDITED_SOURCE_COMMIT, CORE_SOURCE)
    init_node = _find_symbol(
        ast.parse(source.decode("utf-8")),
        "FreshOutcomeIntegratedExecutionKernel.__init__",
    )
    call_lines: dict[str, int] = {}
    for item in ast.walk(init_node):
        if not isinstance(item, ast.Call):
            continue
        if isinstance(item.func, ast.Attribute) and item.func.attr == "admit":
            call_lines["guard"] = item.lineno
        elif isinstance(item.func, ast.Name) and item.func.id in {
            "client_factory",
            "kernel_writer_factory",
            "outcome_writer_factory",
        }:
            call_lines[item.func.id] = item.lineno
    required = {"guard", "client_factory", "kernel_writer_factory", "outcome_writer_factory"}
    if set(call_lines) != required or not all(
        call_lines["guard"] < call_lines[name] for name in required - {"guard"}
    ):
        _fail("authorization.source_order", "guard is not before every constructor factory")
    return cast(
        models.AuthorizationOrderingAudit,
        models.make_identity(
            models.AuthorizationOrderingAudit,
            {
                "authorization_id": authorization.authorization_id,
                "controls": controls,
            },
            field="audit_id",
            prefix="finance_v26_198_authorization_ordering_audit:",
        ),
    )


def _legacy_completion_bypass_audit(
    *,
    repository_root: Path,
    contract: integration.TerminalOutcomeIntegrationContract,
    runtime: models.IndependentRuntimeReplayAudit,
    fresh_writer_call_count: int,
) -> models.LegacyCompletionBypassAudit:
    old_source = _git_blob(repository_root, AUDITED_SOURCE_COMMIT, OLD_KERNEL_SOURCE)
    successor_source = _git_blob(repository_root, AUDITED_SOURCE_COMMIT, CORE_SOURCE)
    old_segment = _symbol_segment(
        old_source,
        "AuthoritativeJsonExplicitExecutionKernel.complete_job",
    )
    successor_segment = _symbol_segment(
        successor_source,
        "FreshOutcomeIntegratedExecutionKernel.complete_job",
    )
    successor_tree = ast.parse(successor_segment)
    calls_old = sum(
        isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and item.func.attr == "complete_job"
        for item in ast.walk(successor_tree)
    )
    if (
        b"fixture_complete" not in old_segment
        or calls_old
        or runtime.old_complete_job_call_count
        or fresh_writer_call_count != 32
        or not contract.kernel_owned_dispatcher_required
        or not contract.fresh_writer_required
    ):
        _fail("legacy.bypass", "successor can fall back to legacy fixture completion")
    return cast(
        models.LegacyCompletionBypassAudit,
        models.make_identity(
            models.LegacyCompletionBypassAudit,
            {
                "integration_contract_id": contract.contract_id,
                "v194_complete_job_source_sha256": _sha256_bytes(old_segment),
                "successor_complete_job_source_sha256": _sha256_bytes(successor_segment),
                "successor_calls_old_complete_job_count": calls_old,
                "old_complete_job_runtime_call_count": runtime.old_complete_job_call_count,
                "successor_fresh_writer_runtime_call_count": fresh_writer_call_count,
            },
            field="audit_id",
            prefix="finance_v26_198_legacy_completion_bypass_audit:",
        ),
    )


def _gate(name: str, *evidence_ids: str) -> models.StaticGate:
    return models.StaticGate(name=name, evidence_ids=tuple(evidence_ids))


def _artifact_manifest(root: Path, *, scope: str) -> models.ArtifactManifest:
    members = tuple(
        models.ArtifactMember(
            relative_path=path.relative_to(root).as_posix(),
            sha256=_sha256_bytes(path.read_bytes()),
            byte_count=path.stat().st_size,
        )
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    )
    artifact_root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix=f"finance_v26_198_{scope}_artifact_root:",
    )
    return cast(
        models.ArtifactManifest,
        models.make_identity(
            models.ArtifactManifest,
            {
                "run_id": RUN_ID,
                "members": members,
                "file_count": len(members),
                "total_byte_count": sum(item.byte_count for item in members),
                "artifact_root": artifact_root,
                "scope": scope,
            },
            field="manifest_id",
            prefix=f"finance_v26_198_{scope}_artifact_manifest:",
        ),
    )


def build(
    *,
    repository_root: Path,
    audit_path: Path,
    output_dir: Path,
) -> models.IndependentAuditReport:
    if output_dir.exists():
        _fail("output", "v26.198 output directory already exists")
    authorization, audit_bytes = _authorization(audit_path)
    freeze = _verify_v197_formal(
        repository_root=repository_root,
        authorization=authorization,
    )
    rebuild = _formal_rebuild(
        repository_root=repository_root,
        authorization=authorization,
        freeze=freeze,
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    runtime, reconstructed, caller_rejections, writer_calls = _independent_runtime_replay(
        repository_root=repository_root,
        output_dir=output_dir,
        authorization=authorization,
    )
    _candidate_authorization, _candidate_bytes, _admission, contract = (
        _candidate_integration_objects(repository_root)
    )
    registry = _load_parents(repository_root)[4]
    codomain = _dispatcher_codomain_audit(
        repository_root=repository_root,
        runtime=runtime,
        contract=contract,
        registry=registry,
    )
    injection = _terminal_injection_audit(
        contract=contract,
        caller_terminal_rejection_count=caller_rejections,
    )
    authorization_ordering = _authorization_ordering_audit(
        repository_root=repository_root,
        authorization=authorization,
    )
    bypass = _legacy_completion_bypass_audit(
        repository_root=repository_root,
        contract=contract,
        runtime=runtime,
        fresh_writer_call_count=writer_calls,
    )
    gates = (
        _gate("exact_external_v26_197_independent_audit_parent", authorization.authorization_id),
        _gate("v26_197_exact_source_identity", freeze.audit_id),
        _gate("v26_197_exact_48_file_freeze", freeze.audit_id),
        _gate("v26_197_sealed_and_distribution_roots", freeze.audit_id),
        _gate("v26_194_experiment_inputs_unchanged", freeze.audit_id),
        _gate("v26_195_six_authority_identities_unchanged", freeze.audit_id),
        _gate("detached_checkout_exact_source_commit", rebuild.audit_id),
        _gate("credential_free_detached_rebuild", rebuild.audit_id),
        _gate("v26_197_exact_48_file_byte_rebuild", rebuild.audit_id),
        _gate("candidate_report_not_used_as_outcome_oracle", runtime.audit_id),
        _gate("independent_actual_v26_194_invoke_count_16", runtime.audit_id),
        _gate("independent_reachable_terminal_replay_16", runtime.audit_id),
        _gate("independent_raw_result_actual_bytes_32", runtime.audit_id),
        _gate("independent_failure_locus_reconstruction_16", runtime.audit_id),
        _gate("independent_trace_reconstruction_16", runtime.audit_id),
        _gate("independent_outcome_reconstruction_16", runtime.audit_id),
        _gate("candidate_raw_result_byte_matches_32", runtime.audit_id),
        _gate("terminal_not_invoke_or_complete_parameter", injection.audit_id),
        _gate("caller_terminal_injection_rejected", injection.audit_id),
        _gate("dispatcher_real_codomain_equals_registry_reachable_set", codomain.audit_id),
        _gate("two_excluded_terminals_absent_from_real_codomain", codomain.audit_id),
        _gate("authorization_guard_before_all_factories", authorization_ordering.audit_id),
        _gate("invalid_authorization_factory_calls_zero", authorization_ordering.audit_id),
        _gate("legacy_fixture_completion_runtime_calls_zero", bypass.audit_id),
        _gate("successor_fresh_writer_calls_32", bypass.audit_id),
        _gate("future_online_entry_not_materialized", bypass.audit_id),
        _gate("provider_calls_zero", runtime.audit_id),
        _gate("development_and_empirical_outcomes_zero", runtime.audit_id),
        _gate("qa_branch_unchanged", freeze.audit_id),
        _gate("online_execution_still_blocked", authorization.authorization_id),
    )
    static = cast(
        models.StaticAudit,
        models.make_identity(
            models.StaticAudit,
            {
                "gates": gates,
                "gate_count": len(gates),
                "passed_count": len(gates),
            },
            field="audit_id",
            prefix="finance_v26_198_static_audit:",
        ),
    )
    decision = cast(
        models.IndependentAuditDecision,
        models.make_identity(
            models.IndependentAuditDecision,
            {
                "authorization_id": authorization.authorization_id,
                "freeze_audit_id": freeze.audit_id,
                "formal_rebuild_audit_id": rebuild.audit_id,
                "runtime_replay_audit_id": runtime.audit_id,
                "dispatcher_codomain_audit_id": codomain.audit_id,
                "terminal_injection_audit_id": injection.audit_id,
                "authorization_ordering_audit_id": authorization_ordering.audit_id,
                "legacy_completion_bypass_audit_id": bypass.audit_id,
                "static_audit_id": static.audit_id,
                "decision": (
                    "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
                    "independent_audit_passed_online_execution_still_blocked"
                ),
            },
            field="decision_id",
            prefix="finance_v26_198_independent_audit_decision:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        models.make_identity(
            models.ProspectiveTransition,
            {"decision_id": decision.decision_id},
            field="transition_id",
            prefix="finance_v26_198_transition:",
        ),
    )
    payloads: dict[str, bytes] = {
        "external_v26_197_independent_audit.txt": audit_bytes,
        "external_independent_audit_authorization.json": _canonical_bytes(authorization),
        "v26_197_source_and_artifact_freeze_audit.json": _canonical_bytes(freeze),
        "v26_197_formal_rebuild_audit.json": _canonical_bytes(rebuild),
        "independent_terminal_runtime_replay_audit.json": _canonical_bytes(runtime),
        "independent_reconstructed_evidence_set.json": _canonical_bytes(
            tuple(item.model_dump(mode="json", warnings=False) for item in reconstructed)
        ),
        "dispatcher_codomain_audit.json": _canonical_bytes(codomain),
        "terminal_injection_audit.json": _canonical_bytes(injection),
        "authorization_ordering_audit.json": _canonical_bytes(authorization_ordering),
        "legacy_completion_bypass_audit.json": _canonical_bytes(bypass),
        "static_audit.json": _canonical_bytes(static),
        "independent_audit_decision.json": _canonical_bytes(decision),
        "prospective_transition.json": _canonical_bytes(transition),
    }
    for name, payload in sorted(payloads.items()):
        _write_no_replace(output_dir / name, payload)
    sealed = _artifact_manifest(output_dir, scope="sealed_evidence")
    if sealed.file_count != 45:
        _fail("artifact.sealed", "v26.198 sealed evidence file count differs")
    _write_no_replace(output_dir / "sealed_evidence_manifest.json", _canonical_bytes(sealed))
    source_commit, source_tree = _git_identity(repository_root)
    report = cast(
        models.IndependentAuditReport,
        models.make_identity(
            models.IndependentAuditReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "source_commit": source_commit,
                "source_tree": source_tree,
                "freeze_audit_id": freeze.audit_id,
                "formal_rebuild_audit_id": rebuild.audit_id,
                "runtime_replay_audit_id": runtime.audit_id,
                "dispatcher_codomain_audit_id": codomain.audit_id,
                "terminal_injection_audit_id": injection.audit_id,
                "authorization_ordering_audit_id": authorization_ordering.audit_id,
                "legacy_completion_bypass_audit_id": bypass.audit_id,
                "static_audit_id": static.audit_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
                "sealed_manifest_id": sealed.manifest_id,
                "sealed_artifact_root": sealed.artifact_root,
                "decision": decision.decision,
            },
            field="report_id",
            prefix="finance_v26_198_terminal_outcome_repair_independent_audit_report:",
        ),
    )
    _write_no_replace(output_dir / "report.json", _canonical_bytes(report))
    distribution = _artifact_manifest(output_dir, scope="distribution")
    if distribution.file_count != 47:
        _fail("artifact.distribution", "v26.198 distribution file count differs")
    _write_no_replace(output_dir / "artifact_manifest.json", _canonical_bytes(distribution))
    if len(_recursive_bindings(output_dir)) != 48:
        _fail("artifact.final", "v26.198 formal file count differs")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--audit-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build(
        repository_root=args.repository_root.resolve(),
        audit_path=args.audit_path.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
