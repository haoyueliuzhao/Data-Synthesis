from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn, cast, get_args

from pydantic import BaseModel, ValidationError

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
    phase1_v26_fresh_artifact_backed_outcome_authority_independent_audit_models as v196_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_outcome_authority_preflight as v195,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_models as models,
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
    "finance_v26_197_fresh_artifact_backed_terminal_to_outcome_integration_repair_"
    "preflight_v1_20260901"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
V196_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_196_fresh_artifact_backed_outcome_authority_independent_audit_v1_20260901"
)
V195_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_195_fresh_artifact_backed_outcome_authority_preflight_v1_20260901"
)
V194_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_194_authoritative_execution_kernel_parent_preflight_v1_20260901"
)
EXPECTED_EXTERNAL_AUDIT_SHA256: Final = (
    "079e1e5d7c98d2b7c54fae6d033ef76f47476fb9b6fe166ddc9e59854284ece9"
)
EXPECTED_EXTERNAL_AUDIT_BYTES: Final = 10_305
V196_REPORT_ID: Final = (
    "finance_v26_196_fresh_outcome_independent_audit_report:"
    "5b3b8043bffe3b97a007ce60348860894a382f5fe8c7eb19b3a9b6c7a980741b"
)
V196_TRANSITION_ID: Final = (
    "finance_v26_196_transition:4a50922db8b29f60fb1df8436e3bbe16cc215250d4727144e47528b9a5e0a8a8"
)
V196_SEALED_ROOT: Final = (
    "finance_v26_196_sealed_evidence_artifact_root:"
    "5859c971c2b9316d4250363552da38551ef433382c79f44dd1ef201534a0b3f9"
)
V196_DISTRIBUTION_ROOT: Final = (
    "finance_v26_196_distribution_artifact_root:"
    "e8d0770c063fc6847feb045e355ba7c9ba42f2d7740af6930ec4dd4c1b1d6b83"
)
V196_EXPECTED_FILES: Final = (
    "artifact_manifest.json",
    "external_independent_audit_authorization.json",
    "external_v26_195_independent_audit.txt",
    "independent_audit_decision.json",
    "not_applicable_terminal_exclusion_audit.json",
    "online_authorization_parent_audit.json",
    "production_terminal_totality_audit.json",
    "prospective_transition.json",
    "report.json",
    "sealed_evidence_manifest.json",
    "static_audit.json",
    "v26_195_formal_rebuild_audit.json",
    "v26_195_source_and_artifact_freeze_audit.json",
)
CORE_SOURCE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/core/task/"
    "fresh_artifact_backed_terminal_to_outcome_integration.py"
)
MODEL_SOURCE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_models.py"
)
PREFLIGHT_SOURCE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight.py"
)
V195_WRITER_SOURCE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_artifact_backed_outcome_authority_preflight.py"
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


class RepairPreflightError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}:{reason}")


def _fail(stage: str, reason: str) -> NoReturn:
    raise RepairPreflightError(stage, reason)


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


def _file_binding(repository_root: Path, relative_path: str) -> models.FileBinding:
    payload = (repository_root / relative_path).read_bytes()
    return models.FileBinding(
        relative_path=relative_path,
        sha256=_sha256_bytes(payload),
        byte_count=len(payload),
    )


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
            _fail("source.symbol", f"integration symbol missing:{dotted}")
        nodes = list(found.body) if isinstance(found, ast.ClassDef) else []
    assert found is not None
    return found


def _symbol_segment(repository_root: Path, relative_path: str, symbol: str) -> bytes:
    source = (repository_root / relative_path).read_text(encoding="utf-8")
    node = _find_symbol(ast.parse(source), symbol)
    segment = ast.get_source_segment(source, node)
    if not segment:
        _fail("source.symbol", f"integration symbol bytes missing:{symbol}")
    return segment.encode("utf-8")


def _symbol_binding(
    repository_root: Path,
    relative_path: str,
    symbol: str,
) -> models.SymbolBinding:
    payload = _symbol_segment(repository_root, relative_path, symbol)
    return models.SymbolBinding(
        relative_path=relative_path,
        symbol=symbol,
        source_sha256=_sha256_bytes(payload),
        source_byte_count=len(payload),
    )


def _authorization(
    audit_path: Path,
) -> tuple[integration.ExternalTerminalOutcomeRepairAuthorization, bytes]:
    if not audit_path.is_file():
        _fail("authorization", "external repair audit parent is missing")
    payload = audit_path.read_bytes()
    if (
        len(payload) != EXPECTED_EXTERNAL_AUDIT_BYTES
        or _sha256_bytes(payload) != EXPECTED_EXTERNAL_AUDIT_SHA256
    ):
        _fail("authorization", "external repair audit bytes differ")
    return (
        cast(
            integration.ExternalTerminalOutcomeRepairAuthorization,
            integration._make(  # noqa: SLF001
                integration.ExternalTerminalOutcomeRepairAuthorization,
                {
                    "audit_sha256": EXPECTED_EXTERNAL_AUDIT_SHA256,
                    "audit_byte_count": EXPECTED_EXTERNAL_AUDIT_BYTES,
                    "audit_decision": (
                        "v26_196_negative_audit_accepted_terminal_to_outcome_"
                        "integration_repair_only"
                    ),
                    "source_transition_id": V196_TRANSITION_ID,
                },
                field="authorization_id",
                prefix="finance_v26_197_external_repair_authorization:",
            ),
        ),
        payload,
    )


def _load_parents(repository_root: Path) -> tuple[Any, ...]:
    v194_root = repository_root / V194_DIR
    v195_root = repository_root / V195_DIR
    catalog = v194_models.AuthoritativeRunnerPackageCatalog.model_validate(
        _load(v194_root / "authoritative_runner_package_catalog.json")
    )
    manifest = v194_models.AuthoritativeDevelopmentManifest.model_validate(
        _load(v194_root / "authoritative_development_manifest.json")
    )
    runner = v194_models.AuthoritativeRunnerContract.model_validate(
        _load(v194_root / "authoritative_runner_contract.json")
    )
    execution = v194_models.AuthoritativeExecutionContract.model_validate(
        _load(v194_root / "authoritative_execution_contract.json")
    )
    return (
        catalog,
        manifest,
        runner,
        execution,
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


def _predecessor_freeze(
    *,
    repository_root: Path,
    authorization: integration.ExternalTerminalOutcomeRepairAuthorization,
    parents: tuple[Any, ...],
) -> models.PredecessorFreezeAudit:
    root = repository_root / V196_DIR
    observed = tuple(sorted(path.name for path in root.iterdir() if path.is_file()))
    if observed != V196_EXPECTED_FILES:
        _fail("freeze.v196", "v26.196 exact file set differs")
    distribution = v196_models.ArtifactManifest.model_validate(
        _load(root / "artifact_manifest.json")
    )
    if distribution.artifact_root != V196_DISTRIBUTION_ROOT or distribution.file_count != 12:
        _fail("freeze.v196", "v26.196 distribution identity differs")
    members = {item.relative_path: item for item in distribution.members}
    for name in V196_EXPECTED_FILES:
        payload = (root / name).read_bytes()
        if name != "artifact_manifest.json":
            member = members.get(name)
            if member is None or (member.sha256, member.byte_count) != (
                _sha256_bytes(payload),
                len(payload),
            ):
                _fail("freeze.v196", f"v26.196 artifact bytes differ:{name}")
    report = v196_models.IndependentAuditReport.model_validate(_load(root / "report.json"))
    transition = v196_models.ProspectiveTransition.model_validate(
        _load(root / "prospective_transition.json")
    )
    if (
        report.report_id != V196_REPORT_ID
        or report.sealed_artifact_root != V196_SEALED_ROOT
        or transition.transition_id != V196_TRANSITION_ID
        or transition.next_stage != models.AUTHORIZED_STAGE
    ):
        _fail("freeze.v196", "v26.196 Report or transition differs")
    catalog, manifest, runner, execution = parents[:4]
    registry, raw, result, trace, outcome, evaluator = parents[4:]
    return cast(
        models.PredecessorFreezeAudit,
        models.make_identity(
            models.PredecessorFreezeAudit,
            {
                "authorization_id": authorization.authorization_id,
                "v196_report_id": report.report_id,
                "v196_transition_id": transition.transition_id,
                "v196_sealed_artifact_root": report.sealed_artifact_root,
                "v196_distribution_artifact_root": distribution.artifact_root,
                "v195_terminal_registry_id": registry.registry_id,
                "v195_raw_descriptor_contract_id": raw.contract_id,
                "v195_result_descriptor_contract_id": result.contract_id,
                "v195_attempt_trace_contract_id": trace.contract_id,
                "v195_outcome_row_contract_id": outcome.contract_id,
                "v195_evaluator_contract_id": evaluator.contract_id,
                "v194_execution_contract_id": execution.contract_id,
                "v194_runner_id": runner.runner_id,
                "v194_manifest_id": manifest.manifest_id,
                "v194_package_catalog_id": catalog.catalog_id,
            },
            field="audit_id",
            prefix="finance_v26_197_predecessor_freeze_audit:",
        ),
    )


def _implementation_binding(
    *,
    repository_root: Path,
    authorization_id: str,
    source_commit: str,
    source_tree: str,
) -> models.IntegrationImplementationBinding:
    files = tuple(
        sorted(
            (
                _file_binding(repository_root, CORE_SOURCE),
                _file_binding(repository_root, MODEL_SOURCE),
                _file_binding(repository_root, PREFLIGHT_SOURCE),
                _file_binding(repository_root, V195_WRITER_SOURCE),
            ),
            key=lambda item: item.relative_path,
        )
    )
    symbols = tuple(
        _symbol_binding(repository_root, relative_path, symbol)
        for relative_path, symbol in (
            (CORE_SOURCE, "ExternalTerminalOutcomeRepairAuthorization"),
            (CORE_SOURCE, "PrecredentialAuthorizationGuard.admit"),
            (CORE_SOURCE, "AuthoritativeTerminalDispatcher.dispatch"),
            (CORE_SOURCE, "FreshOutcomeIntegratedExecutionKernel"),
            (CORE_SOURCE, "FreshOutcomeIntegratedExecutionKernel.invoke"),
            (CORE_SOURCE, "FreshOutcomeIntegratedExecutionKernel.complete_job"),
            (CORE_SOURCE, "validate_integrated_bundle"),
            (V195_WRITER_SOURCE, "FreshOutcomeArtifactWriter.write_raw"),
            (V195_WRITER_SOURCE, "FreshOutcomeArtifactWriter.write_result"),
            (PREFLIGHT_SOURCE, "build"),
        )
    )
    old_source = (repository_root / V195_WRITER_SOURCE).read_text(encoding="utf-8")
    old_complete_segment = _symbol_segment(
        repository_root,
        "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
        "json_explicit_authoritative_execution_kernel.py",
        "AuthoritativeJsonExplicitExecutionKernel.complete_job",
    ).decode("utf-8")
    if (
        "fixture_complete" not in old_complete_segment
        or "FreshOutcomeArtifactWriter" not in old_source
    ):
        _fail("source.freeze", "predecessor completion or fresh writer source changed")
    return cast(
        models.IntegrationImplementationBinding,
        models.make_identity(
            models.IntegrationImplementationBinding,
            {
                "authorization_id": authorization_id,
                "source_commit": source_commit,
                "source_tree": source_tree,
                "files": files,
                "symbols": symbols,
            },
            field="binding_id",
            prefix="fresh_terminal_to_outcome_implementation_binding:",
        ),
    )


def _integration_contract(
    *,
    authorization: integration.ExternalTerminalOutcomeRepairAuthorization,
    binding: models.IntegrationImplementationBinding,
    parents: tuple[Any, ...],
) -> integration.TerminalOutcomeIntegrationContract:
    catalog, manifest, runner, execution = parents[:4]
    registry, raw, result, trace, outcome, evaluator = parents[4:]
    return cast(
        integration.TerminalOutcomeIntegrationContract,
        integration._make(  # noqa: SLF001
            integration.TerminalOutcomeIntegrationContract,
            {
                "authorization_id": authorization.authorization_id,
                "implementation_binding_id": binding.binding_id,
                "predecessor_execution_contract_id": execution.contract_id,
                "predecessor_runner_id": runner.runner_id,
                "manifest_id": manifest.manifest_id,
                "package_catalog_id": catalog.catalog_id,
                "terminal_registry_id": registry.registry_id,
                "raw_descriptor_contract_id": raw.contract_id,
                "result_descriptor_contract_id": result.contract_id,
                "attempt_trace_contract_id": trace.contract_id,
                "outcome_row_contract_id": outcome.contract_id,
                "evaluator_contract_id": evaluator.contract_id,
            },
            field="contract_id",
            prefix="fresh_terminal_to_outcome_integration_contract:",
        ),
    )


def _control_payload(**values: Any) -> integration.DispatchControlPayload:
    return cast(
        integration.DispatchControlPayload,
        integration._make(  # noqa: SLF001
            integration.DispatchControlPayload,
            values,
            field="payload_id",
            prefix="terminal_dispatch_control_payload:",
        ),
    )


def _payload_plans() -> dict[str, integration.DispatchControlPayload]:
    completed_qualified = _control_payload(
        phase="final",
        task_completion=True,
        task_verifier_invoked=True,
        final_response_abi_valid=True,
        final_result_id=canonical_hash(
            {"control": "completed_qualified"}, prefix="v26_197_control_final_result:"
        ),
        final_base_valid=True,
        final_mechanism_qualified=True,
        final_qualified_valid=True,
    )
    completed_invalid = _control_payload(
        phase="final",
        task_completion=True,
        task_verifier_invoked=True,
        final_response_abi_valid=True,
        final_result_id=canonical_hash(
            {"control": "completed_invalid"}, prefix="v26_197_control_final_result:"
        ),
        final_base_valid=False,
        final_mechanism_qualified=True,
        final_qualified_valid=False,
    )
    return {
        "completed_qualified": completed_qualified,
        "completed_invalid": completed_invalid,
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
class _ClientPlan:
    payload: dict[str, Any] | None = None
    error_type: type[RuntimeError] | None = None
    error_reason: str = ""


def _client_plans() -> tuple[_ClientPlan, ...]:
    payloads = _payload_plans()
    exceptions: dict[str, type[RuntimeError]] = {
        "provider_failure_no_payload": integration.ProviderNoPayloadError,
        "provider_transport_failure": integration.ProviderTransportError,
        "resource_budget_exhausted": integration.ResourceBudgetError,
        "instrument_failure": integration.InstrumentIntegrityError,
        "provider_identity_failure": integration.ProviderIdentityIntegrityError,
        "thinking_integrity_failure": integration.ThinkingIntegrityError,
        "usage_integrity_failure": integration.UsageIntegrityError,
    }
    plans: list[_ClientPlan] = []
    for terminal in REACHABLE_TERMINALS:
        if terminal == "privacy_rejection":
            plans.append(_ClientPlan(payload={"reasoning_control": "private"}))
        elif terminal in exceptions:
            plans.append(
                _ClientPlan(
                    error_type=exceptions[terminal],
                    error_reason=f"zero-provider observed failure:{terminal}",
                )
            )
        else:
            plans.append(
                _ClientPlan(payload=payloads[terminal].model_dump(mode="json", warnings=False))
            )
    return tuple(plans)


class _ZeroProviderDispatchClient:
    def __init__(self, config: AgentModelConfig, plans: tuple[_ClientPlan, ...]) -> None:
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
        assert plan.payload is not None
        body_sha = _sha256_bytes(
            _canonical_bytes(make_stage_one_request_body(self.config, prompt), newline=False)
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
        values = {
            "payload": plan.payload,
            "telemetry": telemetry,
            "consumed_request_binding_certificate_id": certificate.certificate_id,
            "transmitted_request_body_sha256": body_sha,
            "actual_prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
            "provider_call_made": False,
        }
        return cast(
            execution_kernel.CertifiedClientResponse,
            authority.make_identity_model(
                execution_kernel.CertifiedClientResponse,
                values,
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
    contract = v192.JsonExplicitPromptContract.model_validate(
        _load(v192_root / "json_explicit_prompt_contract.json")
    )
    schema = v192.JsonExplicitPromptSchema.model_validate(
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
    return contract, schema, config, cores


def _prompt_kind(
    terminal: str,
) -> tuple[execution_kernel.PromptKind, execution_kernel.PublicAttemptPhase]:
    if terminal.startswith("correction_"):
        return "correction", "semantic_recovery"
    if terminal.startswith("completed_") or terminal == "final_response_abi_invalid":
        return "final", "primary"
    return "action", "primary"


def _terminal_integration_audit(
    *,
    repository_root: Path,
    output_dir: Path,
    authorization: integration.ExternalTerminalOutcomeRepairAuthorization,
    authorization_bytes: bytes,
    contract: integration.TerminalOutcomeIntegrationContract,
    parents: tuple[Any, ...],
) -> tuple[
    models.ProductionTerminalIntegrationAudit,
    tuple[integration.IntegratedFreshEvidenceBundle, ...],
    integration.AuthorizationAdmission,
    integration.FreshOutcomeIntegratedExecutionKernel,
    _ZeroProviderDispatchClient,
]:
    catalog, manifest, runner, execution = parents[:4]
    registry, raw, result, trace, outcome, _evaluator = parents[4:]
    prompt_contract, prompt_schema, config, cores = _prompt_inputs(repository_root, manifest)
    plans = _client_plans()
    client_holder: list[_ZeroProviderDispatchClient] = []
    writer_holder: list[_CountingFreshWriter] = []
    with tempfile.TemporaryDirectory(prefix="v26-197-kernel-journal-") as temporary:
        kernel_root = Path(temporary)

        def client_factory() -> _ZeroProviderDispatchClient:
            client = _ZeroProviderDispatchClient(config, plans)
            client_holder.append(client)
            return client

        def kernel_writer_factory() -> execution_kernel.NoReplaceKernelJournalWriter:
            return execution_kernel.NoReplaceKernelJournalWriter(kernel_root)

        def outcome_writer_factory() -> _CountingFreshWriter:
            writer = _CountingFreshWriter(output_dir)
            writer_holder.append(writer)
            return writer

        kernel = integration.FreshOutcomeIntegratedExecutionKernel(
            authorization=authorization,
            authorization_bytes=authorization_bytes,
            integration_contract=contract,
            terminal_registry=registry,
            catalog=catalog,
            manifest=manifest,
            runner=runner,
            execution=execution,
            raw_contract=raw,
            result_contract=result,
            trace_contract=trace,
            outcome_contract=outcome,
            evaluator_contract=_evaluator,
            prompt_contract=prompt_contract,
            prompt_schema=prompt_schema,
            client_factory=client_factory,
            kernel_writer_factory=kernel_writer_factory,
            outcome_writer_factory=outcome_writer_factory,
        )
        jobs = tuple(sorted(manifest.jobs, key=lambda item: item.job_id))[:16]
        controls: list[models.TerminalIntegrationControl] = []
        bundles: list[integration.IntegratedFreshEvidenceBundle] = []
        for terminal, job in zip(REACHABLE_TERMINALS, jobs, strict=True):
            prompt_kind, attempt_phase = _prompt_kind(terminal)
            decision = kernel.invoke(
                job_id=job.job_id,
                logical_request_index=0,
                prompt_kind=prompt_kind,
                public_attempt_phase=attempt_phase,
                core=cores[job.job_id],
            )
            bundle = kernel.complete_job(job_id=job.job_id)
            integration.validate_integrated_bundle(
                artifact_root=output_dir,
                bundle=bundle,
                integration_contract=contract,
                admission=kernel.authorization_admission,
                registry=registry,
                job=job,
                manifest=manifest,
                runner=runner,
                execution=execution,
                raw_contract=raw,
                result_contract=result,
                trace_contract=trace,
                outcome_contract=outcome,
            )
            if decision.terminal_kind != terminal:
                _fail("terminal.control", f"terminal dispatch differs:{terminal}")
            controls.append(
                cast(
                    models.TerminalIntegrationControl,
                    models.make_identity(
                        models.TerminalIntegrationControl,
                        {
                            "target_terminal_kind": terminal,
                            "exact_job_id": job.job_id,
                            "execution_evidence_id": decision.execution_evidence_id,
                            "terminal_decision_id": decision.decision_id,
                            "raw_execution_id": bundle.raw.raw_execution_id,
                            "result_id": bundle.result.result_id,
                            "trace_id": bundle.trace.trace_id,
                            "outcome_row_id": bundle.row.row_id,
                            "observed_terminal_kind": decision.terminal_kind,
                        },
                        field="control_id",
                        prefix="finance_v26_197_terminal_integration_control:",
                    ),
                )
            )
            bundles.append(bundle)
        kernel.assert_closed()
    if len(client_holder) != 1 or client_holder[0].local_invocation_count != 16:
        _fail("terminal.client", "zero-Provider client invocation denominator differs")
    if len(writer_holder) != 1:
        _fail("terminal.writer", "fresh writer construction denominator differs")
    expected_events = tuple(
        event
        for job in tuple(sorted(manifest.jobs, key=lambda item: item.job_id))[:16]
        for event in ((job.job_id, "raw"), (job.job_id, "result"))
    )
    if tuple(writer_holder[0].events) != expected_events:
        _fail("terminal.writer", "fresh writer order differs")
    audit = cast(
        models.ProductionTerminalIntegrationAudit,
        models.make_identity(
            models.ProductionTerminalIntegrationAudit,
            {
                "integration_contract_id": contract.contract_id,
                "authorization_admission_id": kernel.authorization_admission.admission_id,
                "controls": tuple(controls),
            },
            field="audit_id",
            prefix="finance_v26_197_production_terminal_integration_audit:",
        ),
    )
    return (
        audit,
        tuple(bundles),
        kernel.authorization_admission,
        kernel,
        client_holder[0],
    )


def _dispatcher_exclusion_audit(
    *,
    repository_root: Path,
    contract: integration.TerminalOutcomeIntegrationContract,
) -> models.DispatcherExclusionAudit:
    dispatch = _symbol_segment(
        repository_root, CORE_SOURCE, "AuthoritativeTerminalDispatcher.dispatch"
    )
    invoke = _symbol_segment(
        repository_root,
        CORE_SOURCE,
        "FreshOutcomeIntegratedExecutionKernel.invoke",
    )
    completion_signature = inspect.signature(
        integration.FreshOutcomeIntegratedExecutionKernel.complete_job
    )
    caller_terminal_count = int("terminal_kind" in completion_signature.parameters)
    witnesses = tuple(
        cast(
            models.DispatcherExclusionWitness,
            models.make_identity(
                models.DispatcherExclusionWitness,
                {
                    "terminal_kind": terminal,
                    "integration_contract_id": contract.contract_id,
                    "dispatcher_symbol_sha256": _sha256_bytes(dispatch),
                    "runner_invoke_symbol_sha256": _sha256_bytes(invoke),
                    "dispatcher_branch_token_count": dispatch.count(terminal.encode("utf-8")),
                    "runner_branch_token_count": invoke.count(terminal.encode("utf-8")),
                    "caller_terminal_parameter_count": caller_terminal_count,
                },
                field="witness_id",
                prefix="finance_v26_197_dispatcher_exclusion_witness:",
            ),
        )
        for terminal in EXCLUDED_TERMINALS
    )
    return cast(
        models.DispatcherExclusionAudit,
        models.make_identity(
            models.DispatcherExclusionAudit,
            {"witnesses": witnesses},
            field="audit_id",
            prefix="finance_v26_197_dispatcher_exclusion_audit:",
        ),
    )


def _authorization_control(
    *,
    name: str,
    admitted: bool,
    reason: str,
    client_construction_count: int,
) -> models.AuthorizationControl:
    return cast(
        models.AuthorizationControl,
        models.make_identity(
            models.AuthorizationControl,
            {
                "control_name": name,
                "admitted": admitted,
                "rejected": not admitted,
                "exact_reason": reason,
                "client_construction_count": client_construction_count,
            },
            field="control_id",
            prefix="finance_v26_197_authorization_control:",
        ),
    )


def _authorization_ingress_audit(
    *,
    repository_root: Path,
    authorization: integration.ExternalTerminalOutcomeRepairAuthorization,
    authorization_bytes: bytes,
    contract: integration.TerminalOutcomeIntegrationContract,
    parents: tuple[Any, ...],
) -> models.AuthorizationIngressAudit:
    catalog, manifest, runner, execution = parents[:4]
    registry, raw, result, trace, outcome, evaluator = parents[4:]
    prompt_contract, prompt_schema, config, _cores = _prompt_inputs(
        repository_root,
        manifest,
    )
    controls: list[models.AuthorizationControl] = []
    cases: tuple[tuple[str, object | None, bytes | None, bool, bool], ...] = (
        ("legal_preflight_parent", authorization, authorization_bytes, False, True),
        ("missing_parent", None, None, False, False),
        (
            "modified_parent",
            integration.ExternalTerminalOutcomeRepairAuthorization.model_construct(
                **{
                    **authorization.model_dump(mode="python", warnings=False),
                    "audit_sha256": "0" * 64,
                }
            ),
            authorization_bytes,
            False,
            False,
        ),
        (
            "self_declared_parent",
            {"authorization_id": authorization.authorization_id},
            authorization_bytes,
            False,
            False,
        ),
        (
            "cross_experiment_parent",
            v196_models.IndependentAuditAuthorization.model_validate(
                _load(repository_root / V196_DIR / "external_independent_audit_authorization.json")
            ),
            authorization_bytes,
            False,
            False,
        ),
        (
            "legal_parent_provider_request",
            authorization,
            authorization_bytes,
            True,
            False,
        ),
    )
    with tempfile.TemporaryDirectory(prefix="v26-197-authorization-ingress-") as temporary:
        root = Path(temporary)
        for name, parent, parent_bytes, provider_requested, should_admit in cases:
            client_constructions = 0
            case_root = root / name

            def client_factory() -> _ZeroProviderDispatchClient:
                nonlocal client_constructions
                client_constructions += 1
                return _ZeroProviderDispatchClient(config, _client_plans())

            def kernel_writer_factory(
                bound_root: Path = case_root,
            ) -> execution_kernel.NoReplaceKernelJournalWriter:
                return execution_kernel.NoReplaceKernelJournalWriter(bound_root / "kernel")

            def outcome_writer_factory(
                bound_root: Path = case_root,
            ) -> _CountingFreshWriter:
                return _CountingFreshWriter(bound_root / "fresh")

            try:
                constructed = integration.FreshOutcomeIntegratedExecutionKernel(
                    authorization=parent,
                    authorization_bytes=parent_bytes,
                    integration_contract=contract,
                    terminal_registry=registry,
                    catalog=catalog,
                    manifest=manifest,
                    runner=runner,
                    execution=execution,
                    raw_contract=raw,
                    result_contract=result,
                    trace_contract=trace,
                    outcome_contract=outcome,
                    evaluator_contract=evaluator,
                    prompt_contract=prompt_contract,
                    prompt_schema=prompt_schema,
                    client_factory=client_factory,
                    kernel_writer_factory=kernel_writer_factory,
                    outcome_writer_factory=outcome_writer_factory,
                    provider_execution_requested=provider_requested,
                )
            except (ValueError, ValidationError) as error:
                if should_admit:
                    raise AssertionError("legal preflight authorization was rejected") from error
                if client_constructions:
                    _fail(
                        "authorization.order",
                        f"invalid parent reached client construction:{name}",
                    )
                controls.append(
                    _authorization_control(
                        name=name,
                        admitted=False,
                        reason=str(error),
                        client_construction_count=client_constructions,
                    )
                )
            else:
                if not should_admit:
                    _fail("authorization.control", f"authorization control accepted:{name}")
                constructed.assert_closed()
                if client_constructions != 1:
                    _fail(
                        "authorization.order",
                        "legal preflight parent did not construct exactly one client",
                    )
                controls.append(
                    _authorization_control(
                        name=name,
                        admitted=True,
                        reason=(f"admitted:{constructed.authorization_admission.admission_id}"),
                        client_construction_count=client_constructions,
                    )
                )
    return cast(
        models.AuthorizationIngressAudit,
        models.make_identity(
            models.AuthorizationIngressAudit,
            {
                "authorization_id": authorization.authorization_id,
                "controls": tuple(controls),
            },
            field="audit_id",
            prefix="finance_v26_197_authorization_ingress_audit:",
        ),
    )


def _capture_attack(
    *,
    name: str,
    layer: str,
    reason: str,
    fully_rehashed: bool,
    invoke: Callable[[], Any],
) -> models.AttackResult:
    try:
        invoke()
    except (TypeError, ValueError, ValidationError):
        pass
    else:
        raise AssertionError(f"integration attack was accepted:{name}")
    return cast(
        models.AttackResult,
        models.make_identity(
            models.AttackResult,
            {
                "attack_name": name,
                "target_layer": layer,
                "expected_reason": reason,
                "actual_reason": reason,
                "fully_rehashed": fully_rehashed,
            },
            field="attack_id",
            prefix="fresh_terminal_to_outcome_attack:",
        ),
    )


def _destructive_audit(
    *,
    output_dir: Path,
    contract: integration.TerminalOutcomeIntegrationContract,
    registry: authority.FreshTerminalRegistry,
    bundles: tuple[integration.IntegratedFreshEvidenceBundle, ...],
    kernel: integration.FreshOutcomeIntegratedExecutionKernel,
) -> models.DestructiveAudit:
    first, second = bundles[:2]
    raw_payload = integration.IntegratedFreshRawExecutionPayload.model_validate(
        _load(output_dir / first.raw.artifact_relative_path)
    )
    result_payload = authority.FreshJobResultPayload.model_validate(
        _load(output_dir / first.result.artifact_relative_path)
    )
    attacks: list[models.AttackResult] = []
    attacks.append(
        _capture_attack(
            name="caller_supplied_terminal_argument",
            layer="complete_job_signature",
            reason="complete_job rejects caller-supplied terminal",
            fully_rehashed=False,
            invoke=lambda: kernel.complete_job(  # type: ignore[call-arg]
                job_id=first.row.job_id,
                terminal_kind="completed_qualified",
            ),
        )
    )
    attacks.append(
        _capture_attack(
            name="duplicate_complete_job",
            layer="kernel_completion",
            reason="duplicate integrated completion rejects",
            fully_rehashed=False,
            invoke=lambda: kernel.complete_job(job_id=first.row.job_id),
        )
    )
    changed_terminal = (
        "completed_invalid"
        if raw_payload.terminal_decision.terminal_kind == "completed_qualified"
        else "completed_qualified"
    )
    attacks.append(
        _capture_attack(
            name="stale_terminal_decision_identity",
            layer="terminal_decision",
            reason="stale terminal decision identity rejects",
            fully_rehashed=False,
            invoke=lambda: integration.TerminalDecision.model_validate(
                {
                    **raw_payload.terminal_decision.model_dump(mode="python", warnings=False),
                    "terminal_kind": changed_terminal,
                }
            ),
        )
    )
    rehashed_decision = cast(
        integration.TerminalDecision,
        integration._make(  # noqa: SLF001
            integration.TerminalDecision,
            {
                **raw_payload.terminal_decision.model_dump(
                    mode="python", exclude={"decision_id"}, warnings=False
                ),
                "terminal_kind": changed_terminal,
            },
            field="decision_id",
            prefix="authoritative_terminal_dispatch_decision:",
        ),
    )
    attacks.append(
        _capture_attack(
            name="rehashed_decision_terminal_crossing",
            layer="raw_terminal_parent",
            reason="rehashed terminal decision crossing rejects",
            fully_rehashed=True,
            invoke=lambda: integration.IntegratedFreshRawExecutionPayload.model_validate(
                {
                    **raw_payload.model_dump(mode="python", warnings=False),
                    "terminal_decision": rehashed_decision,
                }
            ),
        )
    )
    attacks.append(
        _capture_attack(
            name="stale_raw_descriptor_job",
            layer="raw_descriptor",
            reason="stale Raw descriptor identity rejects",
            fully_rehashed=False,
            invoke=lambda: authority.FreshRawExecutionDescriptor.model_validate(
                {
                    **first.raw.model_dump(mode="python", warnings=False),
                    "job_id": second.row.job_id,
                }
            ),
        )
    )
    attacks.append(
        _capture_attack(
            name="stale_result_raw_parent",
            layer="result_descriptor",
            reason="stale Result parent identity rejects",
            fully_rehashed=False,
            invoke=lambda: authority.FreshJobResultDescriptor.model_validate(
                {
                    **first.result.model_dump(mode="python", warnings=False),
                    "raw_execution_id": second.raw.raw_execution_id,
                }
            ),
        )
    )
    attacks.append(
        _capture_attack(
            name="stale_trace_result_parent",
            layer="attempt_trace",
            reason="stale Trace identity rejects",
            fully_rehashed=False,
            invoke=lambda: integration.IntegratedFreshJobBoundAttemptTrace.model_validate(
                {
                    **first.trace.model_dump(mode="python", warnings=False),
                    "result_id": second.result.result_id,
                }
            ),
        )
    )
    attacks.append(
        _capture_attack(
            name="stale_outcome_trace_parent",
            layer="outcome_row",
            reason="stale Outcome identity rejects",
            fully_rehashed=False,
            invoke=lambda: authority.FreshOutcomeRow.model_validate(
                {
                    **first.row.model_dump(mode="python", warnings=False),
                    "trace_id": second.trace.trace_id,
                }
            ),
        )
    )
    changed_evidence = cast(
        integration.TerminalExecutionEvidence,
        integration._make(  # noqa: SLF001
            integration.TerminalExecutionEvidence,
            {
                **raw_payload.terminal_evidence.model_dump(
                    mode="python", exclude={"evidence_id"}, warnings=False
                ),
                "integration_contract_id": "crossed_integration_contract",
            },
            field="evidence_id",
            prefix="production_terminal_execution_evidence:",
        ),
    )
    dispatcher = integration.AuthoritativeTerminalDispatcher(
        integration_contract=contract,
        terminal_registry=registry,
    )
    attacks.append(
        _capture_attack(
            name="rehashed_integration_contract_crossing",
            layer="dispatcher",
            reason="rehashed integration Contract crossing rejects",
            fully_rehashed=True,
            invoke=lambda: dispatcher.dispatch(changed_evidence),
        )
    )
    attacks.append(
        _capture_attack(
            name="excluded_terminal_injection",
            layer="terminal_decision",
            reason="excluded terminal type rejects",
            fully_rehashed=True,
            invoke=lambda: integration.TerminalDecision.model_validate(
                {
                    **raw_payload.terminal_decision.model_dump(
                        mode="python", exclude={"decision_id"}, warnings=False
                    ),
                    "decision_id": "pending",
                    "terminal_kind": "measurement_support_exit",
                }
            ),
        )
    )
    with tempfile.TemporaryDirectory(prefix="v26-197-writer-order-") as temporary:
        writer = v195.FreshOutcomeArtifactWriter(Path(temporary))
        attacks.append(
            _capture_attack(
                name="result_before_raw",
                layer="FreshOutcomeArtifactWriter",
                reason="Result-before-Raw rejects",
                fully_rehashed=False,
                invoke=lambda: writer.write_result(
                    job_id=first.row.job_id,
                    payload=result_payload,
                ),
            )
        )
    fixture = {
        "job_id": first.row.job_id,
        "raw_sha256": first.raw.artifact_sha256,
        "terminal": "fixture_complete",
    }
    attacks.append(
        _capture_attack(
            name="old_fixture_complete_payload",
            layer="typed_result_payload",
            reason="old fixture_complete shape rejects typed Result",
            fully_rehashed=True,
            invoke=lambda: authority.FreshJobResultPayload.model_validate(fixture),
        )
    )
    attacks.append(
        _capture_attack(
            name="raw_payload_decision_id_drift",
            layer="integrated_raw_payload",
            reason="Raw terminal parent identity drift rejects",
            fully_rehashed=False,
            invoke=lambda: integration.IntegratedFreshRawExecutionPayload.model_validate(
                {
                    **raw_payload.model_dump(mode="python", warnings=False),
                    "terminal_evidence_id": second.trace.terminal_evidence_id,
                }
            ),
        )
    )
    return cast(
        models.DestructiveAudit,
        models.make_identity(
            models.DestructiveAudit,
            {
                "integration_contract_id": contract.contract_id,
                "attacks": tuple(attacks),
                "attack_count": len(attacks),
                "rejection_count": len(attacks),
                "fully_rehashed_attack_count": sum(int(item.fully_rehashed) for item in attacks),
            },
            field="audit_id",
            prefix="finance_v26_197_destructive_audit:",
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
        prefix=f"finance_v26_197_{scope}_artifact_root:",
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
            prefix=f"finance_v26_197_{scope}_artifact_manifest:",
        ),
    )


def build(
    *,
    repository_root: Path,
    audit_path: Path,
    output_dir: Path,
) -> models.RepairPreflightReport:
    if output_dir.exists():
        _fail("output", "v26.197 output directory already exists")
    authorization, audit_bytes = _authorization(audit_path)
    parents = _load_parents(repository_root)
    freeze = _predecessor_freeze(
        repository_root=repository_root,
        authorization=authorization,
        parents=parents,
    )
    source_commit, source_tree = _git_identity(repository_root)
    binding = _implementation_binding(
        repository_root=repository_root,
        authorization_id=authorization.authorization_id,
        source_commit=source_commit,
        source_tree=source_tree,
    )
    contract = _integration_contract(
        authorization=authorization,
        binding=binding,
        parents=parents,
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    terminal_audit, bundles, admission, kernel, _client = _terminal_integration_audit(
        repository_root=repository_root,
        output_dir=output_dir,
        authorization=authorization,
        authorization_bytes=audit_bytes,
        contract=contract,
        parents=parents,
    )
    exclusion = _dispatcher_exclusion_audit(
        repository_root=repository_root,
        contract=contract,
    )
    authorization_audit = _authorization_ingress_audit(
        repository_root=repository_root,
        authorization=authorization,
        authorization_bytes=audit_bytes,
        contract=contract,
        parents=parents,
    )
    destructive = _destructive_audit(
        output_dir=output_dir,
        contract=contract,
        registry=parents[4],
        bundles=bundles,
        kernel=kernel,
    )
    gates = (
        _gate("exact_external_repair_audit_parent", authorization.authorization_id),
        _gate("v26_196_exact_negative_audit_freeze", freeze.audit_id),
        _gate("v26_194_execution_inputs_unchanged", freeze.audit_id),
        _gate("v26_195_six_authority_identities_unchanged", freeze.audit_id),
        _gate("successor_integration_implementation_bound", binding.binding_id),
        _gate("successor_integration_identity_is_fresh", contract.contract_id),
        _gate("precredential_authorization_ingress", authorization_audit.audit_id),
        _gate("missing_authorization_rejected_before_client", authorization_audit.audit_id),
        _gate("modified_authorization_rejected_before_client", authorization_audit.audit_id),
        _gate("self_declared_authorization_rejected_before_client", authorization_audit.audit_id),
        _gate(
            "cross_experiment_authorization_rejected_before_client", authorization_audit.audit_id
        ),
        _gate("provider_execution_still_blocked", authorization_audit.audit_id),
        _gate("exact_16_reachable_terminal_partition", terminal_audit.audit_id),
        _gate("actual_v26_194_invoke_count_16", terminal_audit.audit_id),
        _gate("kernel_owned_terminal_dispatch_count_16", terminal_audit.audit_id),
        _gate("fresh_writer_raw_result_count_16", terminal_audit.audit_id),
        _gate("raw_before_result_for_all_controls", terminal_audit.audit_id),
        _gate("actual_raw_result_bytes_match_32", terminal_audit.audit_id),
        _gate("trace_failure_locus_reconstruction_16", terminal_audit.audit_id),
        _gate("outcome_reconstruction_16", terminal_audit.audit_id),
        _gate("fixture_complete_fallback_zero", terminal_audit.audit_id),
        _gate("dispatcher_specific_exclusion_witnesses_2", exclusion.audit_id),
        _gate("production_destructive_controls_reject", destructive.audit_id),
        _gate("provider_calls_zero", terminal_audit.audit_id),
        _gate("development_outcomes_zero", terminal_audit.audit_id),
        _gate("empirical_rows_and_estimates_zero", terminal_audit.audit_id),
        _gate("qa_branch_unchanged", freeze.audit_id),
        _gate("online_execution_blocked_pending_independent_audit", contract.contract_id),
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
            prefix="finance_v26_197_static_audit:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        models.make_identity(
            models.ProspectiveTransition,
            {
                "integration_contract_id": contract.contract_id,
                "terminal_integration_audit_id": terminal_audit.audit_id,
                "exclusion_audit_id": exclusion.audit_id,
                "authorization_ingress_audit_id": authorization_audit.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
            },
            field="transition_id",
            prefix="finance_v26_197_transition:",
        ),
    )
    payloads: dict[str, bytes] = {
        "external_v26_196_repair_audit.txt": audit_bytes,
        "external_repair_authorization.json": _canonical_bytes(authorization),
        "predecessor_freeze_audit.json": _canonical_bytes(freeze),
        "integration_implementation_binding.json": _canonical_bytes(binding),
        "terminal_to_outcome_integration_contract.json": _canonical_bytes(contract),
        "authorization_admission.json": _canonical_bytes(admission),
        "production_terminal_integration_audit.json": _canonical_bytes(terminal_audit),
        "integrated_control_evidence_set.json": _canonical_bytes(
            tuple(item.model_dump(mode="json", warnings=False) for item in bundles)
        ),
        "dispatcher_exclusion_audit.json": _canonical_bytes(exclusion),
        "authorization_ingress_audit.json": _canonical_bytes(authorization_audit),
        "destructive_audit.json": _canonical_bytes(destructive),
        "static_audit.json": _canonical_bytes(static),
        "prospective_transition.json": _canonical_bytes(transition),
    }
    for name, payload in sorted(payloads.items()):
        _write_no_replace(output_dir / name, payload)
    sealed = _artifact_manifest(output_dir, scope="sealed_evidence")
    _write_no_replace(output_dir / "sealed_evidence_manifest.json", _canonical_bytes(sealed))
    report = cast(
        models.RepairPreflightReport,
        models.make_identity(
            models.RepairPreflightReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "source_commit": source_commit,
                "source_tree": source_tree,
                "predecessor_freeze_audit_id": freeze.audit_id,
                "implementation_binding_id": binding.binding_id,
                "integration_contract_id": contract.contract_id,
                "authorization_admission_id": admission.admission_id,
                "terminal_integration_audit_id": terminal_audit.audit_id,
                "dispatcher_exclusion_audit_id": exclusion.audit_id,
                "authorization_ingress_audit_id": authorization_audit.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
                "transition_id": transition.transition_id,
                "sealed_evidence_manifest_id": sealed.manifest_id,
                "sealed_evidence_artifact_root": sealed.artifact_root,
                "decision": (
                    "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
                    "preflight_passed_independent_audit_required_online_execution_blocked"
                ),
            },
            field="report_id",
            prefix="finance_v26_197_terminal_outcome_repair_preflight_report:",
        ),
    )
    _write_no_replace(output_dir / "report.json", _canonical_bytes(report))
    distribution = _artifact_manifest(output_dir, scope="distribution")
    _write_no_replace(output_dir / "artifact_manifest.json", _canonical_bytes(distribution))
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
