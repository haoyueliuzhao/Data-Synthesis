from __future__ import annotations

import argparse
import hashlib
import json
import threading
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import StaticModelAuthorityPathCatalog
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    EmpiricalPilotJob,
    EmpiricalPilotRollout,
    empirical_pilot_job_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_runner import (  # noqa: E501
    _run_one,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
    PublicOperationRematerializationReport,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import OpenAICompatibleJsonClient
from trusted_synthesis.runtime.agent.public_operation import public_operation_progress
from trusted_synthesis.runtime.agent.schema import AgentModelConfig
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest, AgentToolObservation

V26_OPERATION_CLOSURE_REGRESSION_VERSION = "finance_v26_operation_closure_regression.v1"
V26_OPERATION_CLOSURE_SELECTION_VERSION = "finance_v26_operation_closure_selection.v1"
EXPECTED_TASK_COUNT = 8
ROLLOUTS_PER_TASK = 4
EXPECTED_ROLLOUT_COUNT = 32
MAXIMUM_MODEL_TOKENS_PER_ROLLOUT = 120_000
MAXIMUM_TOTAL_ESTIMATED_COST_USD = 2.0
DEFAULT_WORKERS = 16

TARGET_MECHANISMS = (
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
)
IMPLEMENTATION_SOURCE_PATHS = (
    "src/trusted_synthesis/core/trajectory/public_operation.py",
    "src/trusted_synthesis/domains/finance/executable_support_runtime.py",
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_support_pilot.py"),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_support_runner.py"),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_operation_closure_regression.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_public_operation_rematerialization.py"
    ),
    "src/trusted_synthesis/runtime/agent/iterative.py",
    "src/trusted_synthesis/runtime/agent/public_operation.py",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceArtifactFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class ImplementationSourceFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)


class OperationClosureRegressionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_report_id: str = Field(min_length=1)
    source_report_sha256: str = Field(min_length=64, max_length=64)
    source_artifact_files: tuple[SourceArtifactFile, ...] = Field(min_length=12)
    selected_task_record_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    selected_task_package_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    mechanism_task_counts: dict[str, int]
    selection_policy_version: Literal["finance_v26_operation_closure_selection.v1"] = (
        "finance_v26_operation_closure_selection.v1"
    )
    selection_salt: str = Field(min_length=1)
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    fallback_models: tuple[str, ...] = ()
    require_requested_model: Literal[True] = True
    model_invocation_config: dict[str, Any]
    model_config_hash: str = Field(min_length=1)
    provider_route: dict[str, Any]
    provider_route_hash: str = Field(min_length=1)
    task_count: Literal[8] = 8
    rollouts_per_task: Literal[4] = 4
    expected_rollout_count: Literal[32] = 32
    maximum_total_model_tokens_per_rollout: Literal[120000] = 120000
    maximum_total_estimated_cost_usd: float = Field(default=2.0, ge=2.0, le=2.0)
    capability_only_tasks: Literal[True] = True
    unconditional_sampling_only: Literal[True] = True
    measurement_instrument_only: Literal[True] = True
    task_selection_from_model_outcomes_forbidden: Literal[True] = True
    model_comparison_forbidden: Literal[True] = True
    state_mapping_forbidden: Literal[True] = True
    validity_not_an_instrument_gate: Literal[True] = True
    invalid_model_outcomes_retained: Literal[True] = True
    compiler_witnesses_excluded: Literal[True] = True
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=8, max_length=8
    )
    schema_version: str = V26_OPERATION_CLOSURE_REGRESSION_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> OperationClosureRegressionContract:
        groups = (self.selected_task_record_ids, self.selected_task_package_ids)
        if any(group != tuple(sorted(set(group))) for group in groups):
            raise ValueError("regression task identities are not canonical")
        if self.mechanism_task_counts != {mechanism: 2 for mechanism in TARGET_MECHANISMS}:
            raise ValueError("regression mechanism quotas changed")
        if self.model_invocation_config.get("model") != self.model_id:
            raise ValueError("regression model config differs from frozen Flash identity")
        if tuple(self.model_invocation_config.get("fallback_models", ())) != self.fallback_models:
            raise ValueError("regression fallback contract changed")
        if self.model_invocation_config.get("require_requested_model") is not True:
            raise ValueError("regression does not fail closed on model mismatch")
        if self.model_config_hash != canonical_hash(
            self.model_invocation_config,
            prefix="finance_v26_operation_regression_model_config:",
        ):
            raise ValueError("regression model config hash is invalid")
        if self.provider_route_hash != canonical_hash(
            self.provider_route,
            prefix="finance_v26_operation_regression_provider_route:",
        ):
            raise ValueError("regression Provider route hash is invalid")
        if tuple(item.relative_path for item in self.implementation_source_files) != tuple(
            sorted(IMPLEMENTATION_SOURCE_PATHS)
        ):
            raise ValueError("regression implementation manifest is incomplete")
        if self.contract_id != operation_closure_regression_contract_id(self):
            raise ValueError("Operation-closure regression contract identity is invalid")
        return self


class OperationClosureRegressionJobManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    jobs: tuple[EmpiricalPilotJob, ...] = Field(min_length=32, max_length=32)
    schema_version: str = V26_OPERATION_CLOSURE_REGRESSION_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> OperationClosureRegressionJobManifest:
        if any(item.contract_id != self.contract_id for item in self.jobs):
            raise ValueError("regression jobs cross execution contracts")
        ids = tuple(item.job_id for item in self.jobs)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("regression job identities are not canonical")
        task_counts = Counter(item.task_package_id for item in self.jobs)
        if len(task_counts) != EXPECTED_TASK_COUNT or set(task_counts.values()) != {
            ROLLOUTS_PER_TASK
        }:
            raise ValueError("regression task rollout denominators changed")
        if any(item.sampling_mode != "capability_unconditional" for item in self.jobs):
            raise ValueError("regression contains a conditioned or reachability job")
        if self.manifest_id != operation_closure_regression_job_manifest_id(self):
            raise ValueError("Operation-closure job manifest identity is invalid")
        return self


class OperationClosureRolloutDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    replicate_index: int = Field(ge=0, lt=4)
    terminal_category: str = Field(min_length=1)
    exact_requested_model: bool
    fallback_used: bool
    required_node_count: int = Field(ge=1)
    completed_node_count: int = Field(ge=0)
    full_program_lineage_completed: bool
    terminal_node_completed: bool
    postterminal_verification_completed: bool
    stop_ready: bool
    premature_verification_observed: bool
    postcompletion_violation: bool
    final_answer_before_stop_ready_rejected: bool
    stop_ready_false_positive: bool
    stop_ready_false_negative: bool
    independent_validity: bool
    public_contract_in_initial_prompt: bool
    decision_prompt_observed: bool
    public_progress_in_decision_prompt: bool
    initial_prompt_private_identity_free: bool
    schema_version: str = V26_OPERATION_CLOSURE_REGRESSION_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> OperationClosureRolloutDiagnostic:
        if self.completed_node_count > self.required_node_count:
            raise ValueError("regression completed-node count exceeds its contract")
        if self.full_program_lineage_completed != (
            self.completed_node_count == self.required_node_count
        ):
            raise ValueError("regression full-lineage flag differs from node completion")
        if self.diagnostic_id != operation_closure_rollout_diagnostic_id(self):
            raise ValueError("Operation-closure rollout diagnostic identity is invalid")
        return self


class OperationClosureRawIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    expected_rollout_count: Literal[32] = 32
    observed_rollout_count: int = Field(ge=0, le=32)
    byte_hash_pass_count: int = Field(ge=0, le=32)
    identity_pass_count: int = Field(ge=0, le=32)
    prompt_hash_pass_count: int = Field(ge=0, le=32)
    recursive_noninterference_pass_count: int = Field(ge=0, le=32)
    provider_call_ids_unique: bool
    duplicate_provider_call_ids: tuple[str, ...] = ()
    failed_artifacts: tuple[str, ...] = ()
    status: Literal["passed", "partial", "failed"]
    schema_version: str = V26_OPERATION_CLOSURE_REGRESSION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> OperationClosureRawIntegrityAudit:
        counts = (
            self.byte_hash_pass_count,
            self.identity_pass_count,
            self.prompt_hash_pass_count,
            self.recursive_noninterference_pass_count,
        )
        complete = all(item == self.expected_rollout_count for item in counts)
        expected = (
            "passed"
            if self.observed_rollout_count == self.expected_rollout_count
            and complete
            and self.provider_call_ids_unique
            and not self.failed_artifacts
            else "partial"
            if all(item == self.observed_rollout_count for item in counts)
            and self.provider_call_ids_unique
            and not self.failed_artifacts
            else "failed"
        )
        if self.status != expected:
            raise ValueError("regression raw-integrity status is inconsistent")
        if self.audit_id != operation_closure_raw_integrity_audit_id(self):
            raise ValueError("Operation-closure raw audit identity is invalid")
        return self


class OperationClosureRegressionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    job_manifest_id: str = Field(min_length=1)
    discovered_models: tuple[str, ...]
    completed_rollout_count: int = Field(ge=0, le=32)
    terminal_counts: dict[str, int]
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str = Field(min_length=1)
    raw_integrity_audit: OperationClosureRawIntegrityAudit
    diagnostics: tuple[OperationClosureRolloutDiagnostic, ...]
    model_outcome_count: int = Field(ge=0, le=32)
    runtime_failure_count: int = Field(ge=0, le=32)
    instrument_failure_count: int = Field(ge=0, le=32)
    exact_model_rollout_count: int = Field(ge=0, le=32)
    fallback_rollout_count: int = Field(ge=0, le=32)
    public_contract_prompt_count: int = Field(ge=0, le=32)
    decision_prompt_observed_count: int = Field(ge=0, le=32)
    public_progress_prompt_count: int = Field(ge=0, le=32)
    initial_prompt_private_identity_free_count: int = Field(ge=0, le=32)
    full_program_lineage_count: int = Field(ge=0, le=32)
    terminal_node_completion_count: int = Field(ge=0, le=32)
    postterminal_verification_count: int = Field(ge=0, le=32)
    premature_verification_count: int = Field(ge=0, le=32)
    final_answer_before_stop_ready_rejection_count: int = Field(ge=0, le=32)
    stop_ready_false_positive_count: int = Field(ge=0, le=32)
    stop_ready_false_negative_count: int = Field(ge=0, le=32)
    independently_valid_trajectory_count: int = Field(ge=0, le=32)
    resource_budget_passed: bool
    validity_used_as_instrument_gate: Literal[False] = False
    task_selection_performed: Literal[False] = False
    model_comparison_performed: Literal[False] = False
    state_mapping_performed: Literal[False] = False
    instrument_ready: bool
    status: Literal["preflight", "partial", "passed", "blocked"]
    next_permitted_stage: Literal[
        "model_execution_only",
        "operation_closure_regression_resume_only",
        "capability_development_and_state_reachability_protocol_only",
        "runtime_or_public_operation_instrument_repair_only",
        "resource_budget_audit_only",
    ]
    capability_development_authorized: Literal[False] = False
    state_reachability_pilot_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_OPERATION_CLOSURE_REGRESSION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> OperationClosureRegressionReport:
        if sum(self.terminal_counts.values()) != self.completed_rollout_count:
            raise ValueError("regression terminal denominator is incomplete")
        if len(self.diagnostics) != self.completed_rollout_count:
            raise ValueError("regression diagnostic denominator is incomplete")
        expected_terminals = dict(
            sorted(Counter(item.terminal_category for item in self.diagnostics).items())
        )
        if self.terminal_counts != expected_terminals:
            raise ValueError("regression terminal counts differ from rollout diagnostics")
        expected_aggregates = {
            "model_outcome_count": sum(
                item.terminal_category in {"model_valid_trajectory", "model_invalid_trajectory"}
                for item in self.diagnostics
            ),
            "runtime_failure_count": sum(
                item.terminal_category == "runtime_failure" for item in self.diagnostics
            ),
            "instrument_failure_count": sum(
                item.terminal_category == "instrument_failure" for item in self.diagnostics
            ),
            "exact_model_rollout_count": sum(
                item.exact_requested_model for item in self.diagnostics
            ),
            "fallback_rollout_count": sum(item.fallback_used for item in self.diagnostics),
            "public_contract_prompt_count": sum(
                item.public_contract_in_initial_prompt for item in self.diagnostics
            ),
            "decision_prompt_observed_count": sum(
                item.decision_prompt_observed for item in self.diagnostics
            ),
            "public_progress_prompt_count": sum(
                item.public_progress_in_decision_prompt for item in self.diagnostics
            ),
            "initial_prompt_private_identity_free_count": sum(
                item.initial_prompt_private_identity_free for item in self.diagnostics
            ),
            "full_program_lineage_count": sum(
                item.full_program_lineage_completed for item in self.diagnostics
            ),
            "terminal_node_completion_count": sum(
                item.terminal_node_completed for item in self.diagnostics
            ),
            "postterminal_verification_count": sum(
                item.postterminal_verification_completed for item in self.diagnostics
            ),
            "premature_verification_count": sum(
                item.premature_verification_observed for item in self.diagnostics
            ),
            "final_answer_before_stop_ready_rejection_count": sum(
                item.final_answer_before_stop_ready_rejected for item in self.diagnostics
            ),
            "stop_ready_false_positive_count": sum(
                item.stop_ready_false_positive for item in self.diagnostics
            ),
            "stop_ready_false_negative_count": sum(
                item.stop_ready_false_negative for item in self.diagnostics
            ),
            "independently_valid_trajectory_count": sum(
                item.independent_validity for item in self.diagnostics
            ),
        }
        if any(
            getattr(self, field_name) != expected
            for field_name, expected in expected_aggregates.items()
        ):
            raise ValueError("regression aggregate differs from rollout diagnostics")
        instrument = (
            self.completed_rollout_count == EXPECTED_ROLLOUT_COUNT
            and self.raw_integrity_audit.status == "passed"
            and self.model_outcome_count == EXPECTED_ROLLOUT_COUNT
            and self.runtime_failure_count == 0
            and self.instrument_failure_count == 0
            and self.exact_model_rollout_count == EXPECTED_ROLLOUT_COUNT
            and self.fallback_rollout_count == 0
            and self.public_contract_prompt_count == EXPECTED_ROLLOUT_COUNT
            and self.public_progress_prompt_count == EXPECTED_ROLLOUT_COUNT
            and self.initial_prompt_private_identity_free_count == EXPECTED_ROLLOUT_COUNT
            and self.stop_ready_false_positive_count == 0
            and self.stop_ready_false_negative_count == 0
        )
        if self.instrument_ready != instrument:
            raise ValueError("regression instrument decision is inconsistent")
        resource = Decimal(self.estimated_cost_usd) <= Decimal(
            str(MAXIMUM_TOTAL_ESTIMATED_COST_USD)
        )
        if self.resource_budget_passed != resource:
            raise ValueError("regression resource-budget decision is inconsistent")
        expected_status = (
            "preflight"
            if self.completed_rollout_count == 0
            else "partial"
            if self.completed_rollout_count < EXPECTED_ROLLOUT_COUNT
            else "passed"
            if instrument and resource
            else "blocked"
        )
        if self.status != expected_status:
            raise ValueError("regression report status is inconsistent")
        expected_stage = (
            "model_execution_only"
            if expected_status == "preflight"
            else "operation_closure_regression_resume_only"
            if expected_status == "partial"
            else "capability_development_and_state_reachability_protocol_only"
            if expected_status == "passed"
            else "resource_budget_audit_only"
            if instrument and not resource
            else "runtime_or_public_operation_instrument_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("regression report transition is inconsistent")
        if self.report_id != operation_closure_regression_report_id(self):
            raise ValueError("Operation-closure regression report identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _implementation_source_files(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    values = []
    for relative in sorted(IMPLEMENTATION_SOURCE_PATHS):
        path = package_root / relative
        if not path.is_file():
            raise ValueError(f"regression implementation source is missing: {relative}")
        values.append(ImplementationSourceFile(relative_path=relative, sha256=_sha256(path)))
    return tuple(values)


def _source_artifact_files(source_dir: Path) -> tuple[SourceArtifactFile, ...]:
    report = PublicOperationRematerializationReport.model_validate_json(
        (source_dir / "report.json").read_text(encoding="utf-8")
    )
    values = [
        SourceArtifactFile(
            relative_path="report.json",
            sha256=_sha256(source_dir / "report.json"),
            record_count=1,
        )
    ]
    for item in report.immutable_artifact_files:
        path = source_dir / item.relative_path
        if _sha256(path) != item.sha256:
            raise ValueError(f"v26.60 source Artifact changed: {item.relative_path}")
        values.append(
            SourceArtifactFile(
                relative_path=item.relative_path,
                sha256=item.sha256,
                record_count=item.record_count,
            )
        )
    return tuple(sorted(values, key=lambda item: item.relative_path))


def _load_source(
    source_dir: Path,
    package_root: Path,
) -> tuple[
    PublicOperationRematerializationReport,
    tuple[OperationalTaskRecord, ...],
    tuple[AgentToolEnvironmentManifest, ...],
    tuple[StaticModelAuthorityPathCatalog, ...],
]:
    report = PublicOperationRematerializationReport.model_validate_json(
        (source_dir / "report.json").read_text(encoding="utf-8")
    )
    if (
        report.status != "passed"
        or not report.small_regression_protocol_authorized
        or report.next_permitted_stage != "fresh_operation_closure_regression_protocol_only"
    ):
        raise ValueError("v26.60 does not authorize the small regression protocol")
    _source_artifact_files(source_dir)
    for item in report.implementation_source_files:
        if _sha256(package_root / item.relative_path) != item.sha256:
            raise ValueError(f"v26.60 implementation changed: {item.relative_path}")
    records = tuple(
        OperationalTaskRecord.model_validate(item)
        for item in json.loads((source_dir / "operational_task_records.json").read_text())
    )
    environments = tuple(
        AgentToolEnvironmentManifest.model_validate(item)
        for item in json.loads((source_dir / "tool_environment_manifests.json").read_text())
    )
    catalogs = tuple(
        StaticModelAuthorityPathCatalog.model_validate(item)
        for item in json.loads(
            (source_dir / "static_model_authority_path_catalogs.json").read_text()
        )
    )
    if {item.record_id for item in records} != {item.record_id for item in report.task_records}:
        raise ValueError("v26.60 record identities differ from its report")
    if {item.environment_manifest_id for item in records} != {
        item.manifest_id for item in environments
    }:
        raise ValueError("v26.60 environment identities differ from its task records")
    return report, records, environments, catalogs


def build_operation_closure_regression_contract(
    *,
    run_id: str,
    source_dir: Path,
    model_config: AgentModelConfig,
    package_root: Path,
    selection_salt: str,
) -> tuple[OperationClosureRegressionContract, tuple[OperationalTaskRecord, ...]]:
    report, records, _, _ = _load_source(source_dir, package_root)
    selected = []
    for mechanism in TARGET_MECHANISMS:
        candidates = [
            item
            for item in records
            if item.intended_use == "capability_measurement" and item.mechanism_id == mechanism
        ]
        candidates.sort(
            key=lambda item: canonical_hash(
                {
                    "selection_salt": selection_salt,
                    "task_package_id": item.task_package.package_id,
                },
                prefix="finance_v26_operation_regression_task_rank:",
            )
        )
        if len(candidates) < 2:
            raise ValueError(f"v26.60 lacks two capability tasks for {mechanism}")
        selected.extend(candidates[:2])
    selected.sort(key=lambda item: item.record_id)
    model_payload = model_config.model_dump(mode="json")
    endpoint = urlparse(model_config.endpoint)
    provider_route = {
        "provider": model_config.provider,
        "endpoint_host": endpoint.netloc,
        "model": model_config.model,
    }
    values = {
        "run_id": run_id,
        "source_report_id": report.report_id,
        "source_report_sha256": _sha256(source_dir / "report.json"),
        "source_artifact_files": _source_artifact_files(source_dir),
        "selected_task_record_ids": tuple(item.record_id for item in selected),
        "selected_task_package_ids": tuple(
            sorted(item.task_package.package_id for item in selected)
        ),
        "mechanism_task_counts": {
            mechanism: sum(item.mechanism_id == mechanism for item in selected)
            for mechanism in TARGET_MECHANISMS
        },
        "selection_salt": selection_salt,
        "model_invocation_config": model_payload,
        "model_config_hash": canonical_hash(
            model_payload,
            prefix="finance_v26_operation_regression_model_config:",
        ),
        "provider_route": provider_route,
        "provider_route_hash": canonical_hash(
            provider_route,
            prefix="finance_v26_operation_regression_provider_route:",
        ),
        "implementation_source_files": _implementation_source_files(package_root),
    }
    provisional = OperationClosureRegressionContract.model_construct(
        contract_id="pending", **values
    )
    contract = OperationClosureRegressionContract(
        contract_id=operation_closure_regression_contract_id(provisional),
        **values,
    )
    return contract, tuple(selected)


def build_operation_closure_regression_manifest(
    contract: OperationClosureRegressionContract,
    records: Sequence[OperationalTaskRecord],
) -> OperationClosureRegressionJobManifest:
    jobs = []
    for record in records:
        for replicate in range(ROLLOUTS_PER_TASK):
            values = {
                "contract_id": contract.contract_id,
                "task_record_id": record.record_id,
                "task_package_id": record.task_package.package_id,
                "mechanism_id": record.mechanism_id,
                "intended_use": record.intended_use,
                "sampling_mode": "capability_unconditional",
                "replicate_index": replicate,
            }
            provisional = EmpiricalPilotJob.model_construct(job_id="pending", **values)
            jobs.append(
                EmpiricalPilotJob(
                    job_id=empirical_pilot_job_id(provisional),
                    **values,
                )
            )
    jobs.sort(key=lambda item: item.job_id)
    values = {"contract_id": contract.contract_id, "jobs": tuple(jobs)}
    provisional = OperationClosureRegressionJobManifest.model_construct(
        manifest_id="pending", **values
    )
    return OperationClosureRegressionJobManifest(
        manifest_id=operation_closure_regression_job_manifest_id(provisional),
        **values,
    )


def _write_json_atomic(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"regression immutable JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def _load_checkpoint(
    path: Path,
    contract: OperationClosureRegressionContract,
    manifest: OperationClosureRegressionJobManifest,
) -> tuple[EmpiricalPilotRollout, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        EmpiricalPilotRollout.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("regression checkpoint contains duplicate jobs")
    for item in rows:
        job = jobs.get(item.job_id)
        if (
            job is None
            or item.contract_id != contract.contract_id
            or item.task_package_id != job.task_package_id
            or item.replicate_index != job.replicate_index
        ):
            raise ValueError("regression checkpoint differs from its frozen job")
    return rows


def _raw_payload(item: EmpiricalPilotRollout) -> dict[str, Any]:
    raw = Path(item.raw_artifact_uri).read_bytes()
    if hashlib.sha256(raw).hexdigest() != item.raw_artifact_sha256:
        raise ValueError("regression raw Artifact hash replay failed")
    payload = json.loads(raw)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if raw != canonical:
        raise ValueError("regression raw Artifact is not canonical JSON")
    return cast(dict[str, Any], payload)


def _raw_integrity_audit(
    rollouts: Sequence[EmpiricalPilotRollout],
) -> OperationClosureRawIntegrityAudit:
    byte_pass = identity_pass = prompt_pass = noninterference_pass = 0
    failures: list[str] = []
    provider_ids: list[str] = []
    for item in rollouts:
        try:
            payload = _raw_payload(item)
            byte_pass += 1
            if (
                payload["contract_id"] == item.contract_id
                and payload["job"]["job_id"] == item.job_id
                and payload["task_package_id"] == item.task_package_id
                and payload["terminal_category"] == item.terminal_category
                and tuple(payload["provider_call_ids"]) == item.provider_call_ids
            ):
                identity_pass += 1
            else:
                raise ValueError("raw regression identity mismatch")
            prompts = tuple(payload["actual_model_request_prompts"])
            hashes = tuple(hashlib.sha256(value.encode()).hexdigest() for value in prompts)
            if hashes == item.actual_prompt_hashes:
                prompt_pass += 1
            else:
                raise ValueError("raw regression Prompt hash mismatch")
            if (
                payload["recursive_noninterference_passed"] is True
                and item.recursive_noninterference_passed
            ):
                noninterference_pass += 1
            else:
                raise ValueError("raw regression noninterference mismatch")
            provider_ids.extend(item.provider_call_ids)
        except Exception:
            failures.append(item.raw_artifact_uri)
    duplicates = tuple(sorted(key for key, count in Counter(provider_ids).items() if count > 1))
    complete = (
        len(rollouts)
        == byte_pass
        == identity_pass
        == prompt_pass
        == noninterference_pass
        == EXPECTED_ROLLOUT_COUNT
    )
    partial = len(rollouts) == byte_pass == identity_pass == prompt_pass == noninterference_pass
    values = {
        "observed_rollout_count": len(rollouts),
        "byte_hash_pass_count": byte_pass,
        "identity_pass_count": identity_pass,
        "prompt_hash_pass_count": prompt_pass,
        "recursive_noninterference_pass_count": noninterference_pass,
        "provider_call_ids_unique": not duplicates,
        "duplicate_provider_call_ids": duplicates,
        "failed_artifacts": tuple(sorted(failures)),
        "status": (
            "passed"
            if complete and not duplicates and not failures
            else "partial"
            if partial and not duplicates and not failures
            else "failed"
        ),
    }
    provisional = OperationClosureRawIntegrityAudit.model_construct(audit_id="pending", **values)
    return OperationClosureRawIntegrityAudit(
        audit_id=operation_closure_raw_integrity_audit_id(provisional),
        **values,
    )


def _observations(payload: Mapping[str, Any]) -> tuple[AgentToolObservation, ...]:
    failure = payload.get("failure_artifact")
    if isinstance(failure, Mapping):
        return tuple(AgentToolObservation.model_validate(item) for item in failure["observations"])
    trajectory = payload.get("trajectory")
    if not isinstance(trajectory, Mapping):
        return ()
    output = []
    for step in trajectory.get("steps") or ():
        observation = step.get("observation") if isinstance(step, Mapping) else None
        if isinstance(observation, Mapping) and "observation_id" in observation:
            output.append(AgentToolObservation.model_validate(observation))
    return tuple(output)


def _premature_verification(
    record: OperationalTaskRecord,
    observations: tuple[AgentToolObservation, ...],
) -> bool:
    terminal_index = None
    task = record.task_package.task.public
    for index in range(1, len(observations) + 1):
        progress = public_operation_progress(task, observations[:index])
        if progress is not None and progress["terminal_node_completed"]:
            terminal_index = index - 1
            break
    return any(
        item.call.tool_id == "cross_check_evidence"
        and item.status == "succeeded"
        and item.result.get("verified") is True
        and (terminal_index is None or index < terminal_index)
        for index, item in enumerate(observations)
    )


_STOP_GATE_REJECTION_CODES = frozenset(
    {
        "missing_observed_evidence",
        "missing_required_evidence_selection",
        "missing_required_calculation",
        "missing_required_verification",
    }
)


def _is_stop_gate_rejection(value: Mapping[str, Any]) -> bool:
    reason = str(value.get("reason_code") or value.get("host_rejection_reason") or "")
    feedback = str(value.get("feedback") or value.get("host_feedback") or "")
    return reason in _STOP_GATE_REJECTION_CODES or any(
        marker in feedback
        for marker in (
            "stopped before public Program closure",
            "stopped before completing the public operation contract",
        )
    )


def _stop_decision_readiness(
    record: OperationalTaskRecord,
    payload: Mapping[str, Any],
) -> tuple[tuple[bool, bool, bool, bool], ...]:
    task = record.task_package.task.public
    trajectory = payload.get("trajectory")
    rows: list[tuple[bool, bool, bool, bool]] = []
    if isinstance(trajectory, Mapping):
        observed: list[AgentToolObservation] = []
        raw_steps = trajectory.get("steps")
        if not isinstance(raw_steps, (list, tuple)):
            raise ValueError("regression trajectory has no replayable steps")
        for step in raw_steps:
            if not isinstance(step, Mapping):
                raise ValueError("regression trajectory contains a malformed step")
            observation = step.get("observation")
            if isinstance(observation, Mapping) and "observation_id" in observation:
                observed.append(AgentToolObservation.model_validate(observation))
                continue
            if str(step.get("action") or "") != "answer":
                continue
            progress = public_operation_progress(task, tuple(observed))
            if progress is None:
                raise ValueError("regression stop decision lost its public Operation contract")
            status = str(step.get("status") or "")
            if status not in {"succeeded", "failed"}:
                raise ValueError("regression answer step has an invalid status")
            rejected = status == "failed"
            rows.append(
                (
                    status == "succeeded",
                    rejected,
                    bool(progress["stop_ready"]),
                    bool(
                        rejected
                        and isinstance(observation, Mapping)
                        and _is_stop_gate_rejection(observation)
                    ),
                )
            )
        return tuple(rows)

    failure = payload.get("failure_artifact")
    if not isinstance(failure, Mapping):
        return ()
    observations = tuple(
        AgentToolObservation.model_validate(item) for item in failure.get("observations") or ()
    )
    decisions = failure.get("decisions") or ()
    rejections = failure.get("stop_rejections") or ()
    rejection_by_index = {
        int(item["decision_index"]): item
        for item in rejections
        if isinstance(item, Mapping) and "decision_index" in item
    }
    observed = []
    observation_index = 0
    for decision_index, decision in enumerate(decisions):
        if not isinstance(decision, Mapping):
            raise ValueError("regression failure Artifact contains a malformed decision")
        if decision.get("decision_type") == "tool_call":
            if observation_index >= len(observations):
                break
            observed.append(observations[observation_index])
            observation_index += 1
            continue
        if decision.get("decision_type") != "final_answer":
            raise ValueError("regression failure Artifact contains an unknown decision")
        rejection = rejection_by_index.get(decision_index)
        if rejection is None:
            raise ValueError("regression failure Artifact has an unclassified final decision")
        progress = public_operation_progress(task, tuple(observed))
        if progress is None:
            raise ValueError("regression stop decision lost its public Operation contract")
        rows.append(
            (
                False,
                True,
                bool(progress["stop_ready"]),
                _is_stop_gate_rejection(rejection),
            )
        )
    return tuple(rows)


def _diagnostic(
    rollout: EmpiricalPilotRollout,
    record: OperationalTaskRecord,
) -> OperationClosureRolloutDiagnostic:
    payload = _raw_payload(rollout)
    observations = _observations(payload)
    progress = public_operation_progress(record.task_package.task.public, observations)
    if progress is None:
        raise ValueError("regression rollout lost its public Operation contract")
    prompts = tuple(str(item) for item in payload["actual_model_request_prompts"])
    initial = prompts[0] if prompts else ""
    stop_rows = _stop_decision_readiness(record, payload)
    early_stop_rejected = any(
        rejected and not stop_ready for _, rejected, stop_ready, _ in stop_rows
    )
    false_positive = any(accepted and not stop_ready for accepted, _, stop_ready, _ in stop_rows)
    false_negative = any(
        stop_gate_rejection and stop_ready for _, _, stop_ready, stop_gate_rejection in stop_rows
    )
    decision_prompts = tuple(item for item in prompts if '"operation_execution_progress"' in item)
    progress_projection_passed = all(
        '"unresolved_variable_requirements"' in item
        and '"terminal_node_completed"' in item
        and '"all_steps_completed"' in item
        for item in decision_prompts
    )
    package = record.task_package
    private_values = (
        *record.target_program_evidence_ids,
        *(item.node_id for item in package.task.oracle.task_program.nodes),
        package.semantic_source.semantic_source_id,
        package.verifier_binding.binding_id,
        package.verifier_binding.source_program_dag_hash,
        package.verifier_binding.source_verifier_dag_hash,
        "mechanism_private_state",
        "target_program_evidence_ids",
        "source_program_node_id",
        "expected_operator_id",
        "source_program_dag_hash",
        "source_verifier_dag_hash",
        "verifier_binding_id",
    )
    values = {
        "rollout_id": rollout.rollout_id,
        "job_id": rollout.job_id,
        "task_package_id": rollout.task_package_id,
        "mechanism_id": rollout.mechanism_id,
        "replicate_index": rollout.replicate_index,
        "terminal_category": rollout.terminal_category,
        "exact_requested_model": rollout.exact_requested_model,
        "fallback_used": rollout.fallback_used,
        "required_node_count": len(record.task_package.stop_readiness_contract.required_node_ids),
        "completed_node_count": len(progress["completed_node_ids"]),
        "full_program_lineage_completed": bool(progress["all_steps_completed"]),
        "terminal_node_completed": bool(progress["terminal_node_completed"]),
        "postterminal_verification_completed": bool(
            progress["verification_after_terminal_completed"]
        ),
        "stop_ready": bool(progress["stop_ready"]),
        "premature_verification_observed": _premature_verification(record, observations),
        "postcompletion_violation": bool(progress["postcompletion_violation"]),
        "final_answer_before_stop_ready_rejected": early_stop_rejected,
        "stop_ready_false_positive": false_positive,
        "stop_ready_false_negative": false_negative,
        "independent_validity": bool(
            rollout.verification is not None and rollout.verification.valid
        ),
        "public_contract_in_initial_prompt": ("public_operation_execution_contract" in initial),
        "decision_prompt_observed": bool(decision_prompts),
        "public_progress_in_decision_prompt": progress_projection_passed,
        "initial_prompt_private_identity_free": all(
            str(value) not in initial for value in private_values
        ),
    }
    provisional = OperationClosureRolloutDiagnostic.model_construct(
        diagnostic_id="pending", **values
    )
    return OperationClosureRolloutDiagnostic(
        diagnostic_id=operation_closure_rollout_diagnostic_id(provisional),
        **values,
    )


def _make_report(
    *,
    contract: OperationClosureRegressionContract,
    manifest: OperationClosureRegressionJobManifest,
    discovered_models: tuple[str, ...],
    rollouts: tuple[EmpiricalPilotRollout, ...],
    records: Sequence[OperationalTaskRecord],
    raw_audit: OperationClosureRawIntegrityAudit,
    preflight: bool = False,
) -> OperationClosureRegressionReport:
    by_record = {item.record_id: item for item in records}
    diagnostics = tuple(
        sorted(
            (_diagnostic(item, by_record[item.task_record_id]) for item in rollouts),
            key=lambda item: item.diagnostic_id,
        )
    )
    terminals = Counter(item.terminal_category for item in rollouts)
    model_outcomes = sum(
        item.terminal_category in {"model_valid_trajectory", "model_invalid_trajectory"}
        for item in rollouts
    )
    estimated_cost = sum((Decimal(item.estimated_cost_usd) for item in rollouts), Decimal("0"))
    resource = estimated_cost <= Decimal(str(MAXIMUM_TOTAL_ESTIMATED_COST_USD))
    instrument = (
        len(rollouts) == EXPECTED_ROLLOUT_COUNT
        and raw_audit.status == "passed"
        and model_outcomes == EXPECTED_ROLLOUT_COUNT
        and terminals["runtime_failure"] == 0
        and terminals["instrument_failure"] == 0
        and sum(item.exact_requested_model for item in rollouts) == EXPECTED_ROLLOUT_COUNT
        and not any(item.fallback_used for item in rollouts)
        and sum(item.public_contract_in_initial_prompt for item in diagnostics)
        == EXPECTED_ROLLOUT_COUNT
        and sum(item.public_progress_in_decision_prompt for item in diagnostics)
        == EXPECTED_ROLLOUT_COUNT
        and sum(item.initial_prompt_private_identity_free for item in diagnostics)
        == EXPECTED_ROLLOUT_COUNT
        and not any(item.stop_ready_false_positive for item in diagnostics)
        and not any(item.stop_ready_false_negative for item in diagnostics)
    )
    status = (
        "preflight"
        if preflight
        else "partial"
        if len(rollouts) < EXPECTED_ROLLOUT_COUNT
        else "passed"
        if instrument and resource
        else "blocked"
    )
    next_stage = (
        "model_execution_only"
        if status == "preflight"
        else "operation_closure_regression_resume_only"
        if status == "partial"
        else "capability_development_and_state_reachability_protocol_only"
        if status == "passed"
        else "resource_budget_audit_only"
        if instrument and not resource
        else "runtime_or_public_operation_instrument_repair_only"
    )
    values = {
        "run_id": contract.run_id,
        "contract_id": contract.contract_id,
        "job_manifest_id": manifest.manifest_id,
        "discovered_models": discovered_models,
        "completed_rollout_count": len(rollouts),
        "terminal_counts": dict(sorted(terminals.items())),
        "provider_call_count": sum(item.provider_call_count for item in rollouts),
        "provider_total_tokens": sum(item.provider_total_tokens for item in rollouts),
        "estimated_cost_usd": str(estimated_cost),
        "raw_integrity_audit": raw_audit,
        "diagnostics": diagnostics,
        "model_outcome_count": model_outcomes,
        "runtime_failure_count": terminals["runtime_failure"],
        "instrument_failure_count": terminals["instrument_failure"],
        "exact_model_rollout_count": sum(item.exact_requested_model for item in rollouts),
        "fallback_rollout_count": sum(item.fallback_used for item in rollouts),
        "public_contract_prompt_count": sum(
            item.public_contract_in_initial_prompt for item in diagnostics
        ),
        "decision_prompt_observed_count": sum(
            item.decision_prompt_observed for item in diagnostics
        ),
        "public_progress_prompt_count": sum(
            item.public_progress_in_decision_prompt for item in diagnostics
        ),
        "initial_prompt_private_identity_free_count": sum(
            item.initial_prompt_private_identity_free for item in diagnostics
        ),
        "full_program_lineage_count": sum(
            item.full_program_lineage_completed for item in diagnostics
        ),
        "terminal_node_completion_count": sum(item.terminal_node_completed for item in diagnostics),
        "postterminal_verification_count": sum(
            item.postterminal_verification_completed for item in diagnostics
        ),
        "premature_verification_count": sum(
            item.premature_verification_observed for item in diagnostics
        ),
        "final_answer_before_stop_ready_rejection_count": sum(
            item.final_answer_before_stop_ready_rejected for item in diagnostics
        ),
        "stop_ready_false_positive_count": sum(
            item.stop_ready_false_positive for item in diagnostics
        ),
        "stop_ready_false_negative_count": sum(
            item.stop_ready_false_negative for item in diagnostics
        ),
        "independently_valid_trajectory_count": sum(
            item.independent_validity for item in diagnostics
        ),
        "resource_budget_passed": resource,
        "instrument_ready": instrument,
        "status": status,
        "next_permitted_stage": next_stage,
    }
    provisional = OperationClosureRegressionReport.model_construct(report_id="pending", **values)
    return OperationClosureRegressionReport(
        report_id=operation_closure_regression_report_id(provisional),
        **values,
    )


def run_operation_closure_regression(
    *,
    run_id: str,
    source_dir: Path,
    model_config_path: Path,
    output_dir: Path,
    package_root: Path,
    selection_salt: str,
    workers: int,
    audit_only: bool = False,
) -> OperationClosureRegressionReport:
    model_payload = json.loads(model_config_path.read_text(encoding="utf-8"))
    model_config = AgentModelConfig.model_validate(model_payload.get("model", model_payload))
    report60, all_records, environments, catalogs = _load_source(source_dir, package_root)
    del report60
    contract, selected = build_operation_closure_regression_contract(
        run_id=run_id,
        source_dir=source_dir,
        model_config=model_config,
        package_root=package_root,
        selection_salt=selection_salt,
    )
    manifest = build_operation_closure_regression_manifest(contract, selected)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_dir / "execution_contract.json", contract.model_dump(mode="json"))
    _write_json_atomic(output_dir / "job_manifest.json", manifest.model_dump(mode="json"))
    empty_audit = _raw_integrity_audit(())
    if audit_only:
        report = _make_report(
            contract=contract,
            manifest=manifest,
            discovered_models=(),
            rollouts=(),
            records=selected,
            raw_audit=empty_audit,
            preflight=True,
        )
        _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
        return report

    record_by_id = {item.record_id: item for item in all_records}
    environment_by_id = {item.manifest_id: item for item in environments}
    catalog_by_task = {item.task_package_id: item for item in catalogs}
    checkpoint_path = output_dir / "rollout_observations.checkpoint.jsonl"
    existing = _load_checkpoint(checkpoint_path, contract, manifest)
    completed = {item.job_id: item for item in existing}
    pending = [item for item in manifest.jobs if item.job_id not in completed]
    client: OpenAICompatibleJsonClient | None = None
    if pending:
        client = OpenAICompatibleJsonClient(model_config)
        discovered_models = client.discover_models()
        if contract.model_id not in discovered_models:
            raise ValueError("frozen DeepSeek V4-Flash identity is unavailable")
    else:
        prior_report_path = output_dir / "report.json"
        if prior_report_path.is_file():
            prior_report = OperationClosureRegressionReport.model_validate_json(
                prior_report_path.read_text(encoding="utf-8")
            )
            if (
                prior_report.contract_id != contract.contract_id
                or prior_report.job_manifest_id != manifest.manifest_id
            ):
                raise ValueError("completed regression report differs from its frozen inputs")
            discovered_models = prior_report.discovered_models
        else:
            discovered_models = (contract.model_id,)
    print(
        f"[v26.61] resuming {len(completed)}/{EXPECTED_ROLLOUT_COUNT}; "
        f"executing {len(pending)} jobs with {workers} workers",
        flush=True,
    )
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1))) as executor:
        future_map = {
            executor.submit(
                _run_one,
                job=job,
                contract=cast(Any, contract),
                record=cast(Any, record_by_id[job.task_record_id]),
                environment=environment_by_id[
                    record_by_id[job.task_record_id].environment_manifest_id
                ],
                catalog=catalog_by_task[job.task_package_id],
                client=cast(OpenAICompatibleJsonClient, client),
                output_dir=output_dir,
            ): job
            for job in pending
        }
        for future in as_completed(future_map):
            rollout = future.result()
            with lock:
                if rollout.job_id in completed:
                    raise ValueError("regression produced a duplicate job result")
                completed[rollout.job_id] = rollout
                _append_jsonl(checkpoint_path, rollout.model_dump(mode="json"))
            if len(completed) % max(1, workers) == 0 or len(completed) == EXPECTED_ROLLOUT_COUNT:
                print(
                    f"[v26.61] completed {len(completed)}/{EXPECTED_ROLLOUT_COUNT}",
                    flush=True,
                )
    ordered = tuple(completed[item.job_id] for item in manifest.jobs if item.job_id in completed)
    _write_json_atomic(
        output_dir / "empirical_rollouts.json",
        [item.model_dump(mode="json") for item in ordered],
    )
    raw_audit = _raw_integrity_audit(ordered)
    _write_json_atomic(output_dir / "raw_integrity_audit.json", raw_audit.model_dump(mode="json"))
    report = _make_report(
        contract=contract,
        manifest=manifest,
        discovered_models=discovered_models,
        rollouts=ordered,
        records=selected,
        raw_audit=raw_audit,
    )
    _write_json_atomic(
        output_dir / "rollout_diagnostics.json",
        [item.model_dump(mode="json") for item in report.diagnostics],
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def operation_closure_regression_contract_id(
    value: OperationClosureRegressionContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_v26_operation_closure_regression_contract:",
    )


def operation_closure_regression_job_manifest_id(
    value: OperationClosureRegressionJobManifest,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_v26_operation_closure_regression_jobs:",
    )


def operation_closure_rollout_diagnostic_id(
    value: OperationClosureRolloutDiagnostic,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v26_operation_closure_rollout_diagnostic:",
    )


def operation_closure_raw_integrity_audit_id(
    value: OperationClosureRawIntegrityAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_operation_closure_raw_integrity:",
    )


def operation_closure_regression_report_id(
    value: OperationClosureRegressionReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_operation_closure_regression_report:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the non-authorizing Finance v26.61 Operation-closure regression"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--selection-salt", required=True)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    report = run_operation_closure_regression(
        run_id=args.run_id,
        source_dir=args.source_dir,
        model_config_path=args.model_config,
        output_dir=args.output_dir,
        package_root=args.package_root,
        selection_salt=args.selection_salt,
        workers=args.workers,
        audit_only=args.audit_only,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
