from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import (
    StaticModelAuthorityPathCatalog,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingHardeningReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_postrun_audit import (  # noqa: E501
    AuthorityPreservingPostrunAuditReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (
    CONDITIONED_ROLLOUTS_PER_STATE,
    MAXIMUM_ESTIMATED_ATTEMPTS_FOR_THREE,
    MINIMUM_RELEASED_REALIZATIONS,
    NATURAL_ROLLOUTS_PER_TASK,
    PublicReachabilityCondition,
    make_public_reachability_condition,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    PATH_STRATEGIES,
    PathStrategy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_operation_closure_regression import (  # noqa: E501
    OperationClosureRegressionJobManifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

V26_EMPIRICAL_ROLE_PROTOCOL_VERSION = "finance_v26_empirical_role_protocol.v1"
V26_TASK_EXPOSURE_AUDIT_VERSION = "finance_v26_task_exposure_audit.v1"
V26_REACHABILITY_JOB_DESIGN_VERSION = "finance_v26_reachability_job_design.v1"
V26_EMPIRICAL_ROLE_PROTOCOL_REPORT_VERSION = "finance_v26_empirical_role_protocol_report.v1"

IMPLEMENTATION_SOURCE_PATH: Literal[
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_role_protocol.py"
] = "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_role_protocol.py"

CAPABILITY_TASK_COUNT: Literal[12] = 12
CAPABILITY_ROLLOUTS_PER_TASK: Literal[8] = 8
CAPABILITY_JOB_COUNT: Literal[96] = 96
REACHABILITY_TASK_COUNT: Literal[12] = 12
STATIC_STATE_COUNT: Literal[36] = 36
NATURAL_JOB_COUNT: Literal[144] = 144
CONDITIONED_JOB_COUNT: Literal[216] = 216
REACHABILITY_JOB_COUNT: Literal[360] = 360

IntendedUse = Literal["capability_measurement", "vtdo_multistate_candidate"]
ReachabilitySamplingMode = Literal[
    "reachability_unconditional",
    "reachability_conditioned",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProtocolSourceFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class ProtocolImplementationSource(FrozenModel):
    relative_path: Literal[
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_role_protocol.py"
    ] = IMPLEMENTATION_SOURCE_PATH
    sha256: str = Field(min_length=64, max_length=64)


class TaskExposureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_record_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    intended_use: IntendedUse
    v26_66_instrument_job_count: int = Field(ge=0, le=4)
    api_exposed_in_v26_66: bool
    eligible_for_capability_development: Literal[False] = False
    eligible_for_state_reachability: bool
    exclusion_reason: Literal[
        "capability_role_requires_fresh_balanced_population",
        "unopened_vtdo_candidate",
    ]
    schema_version: str = V26_TASK_EXPOSURE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TaskExposureAudit:
        if self.api_exposed_in_v26_66 != (self.v26_66_instrument_job_count > 0):
            raise ValueError("task exposure flag differs from the frozen Job Manifest")
        expected_reachability = (
            self.intended_use == "vtdo_multistate_candidate" and not self.api_exposed_in_v26_66
        )
        if self.eligible_for_state_reachability != expected_reachability:
            raise ValueError("task reachability eligibility differs from its role and exposure")
        expected_reason = (
            "unopened_vtdo_candidate"
            if expected_reachability
            else "capability_role_requires_fresh_balanced_population"
        )
        if self.exclusion_reason != expected_reason:
            raise ValueError("task exposure reason is inconsistent")
        if self.audit_id != task_exposure_audit_id(self):
            raise ValueError("task exposure audit identity is invalid")
        return self


class ReachabilityJobDesign(FrozenModel):
    job_id: str = Field(min_length=1)
    protocol_scope_id: str = Field(min_length=1)
    task_record_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    sampling_mode: ReachabilitySamplingMode
    replicate_index: int = Field(ge=0)
    requested_static_path_id: str | None = None
    requested_path_strategy: PathStrategy | None = None
    requested_quotient_state_id: str | None = None
    public_condition_id: str | None = None
    model_generated_execution: Literal[False] = False
    compiler_witness_counted: Literal[False] = False
    schema_version: str = V26_REACHABILITY_JOB_DESIGN_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> ReachabilityJobDesign:
        conditioned = self.sampling_mode == "reachability_conditioned"
        fields = (
            self.requested_static_path_id,
            self.requested_path_strategy,
            self.requested_quotient_state_id,
            self.public_condition_id,
        )
        if conditioned != all(item is not None for item in fields):
            raise ValueError("reachability job condition fields are incomplete or extraneous")
        if conditioned and self.replicate_index >= CONDITIONED_ROLLOUTS_PER_STATE:
            raise ValueError("conditioned reachability replicate exceeds its denominator")
        if not conditioned and self.replicate_index >= NATURAL_ROLLOUTS_PER_TASK:
            raise ValueError("natural reachability replicate exceeds its denominator")
        if self.job_id != reachability_job_design_id(self):
            raise ValueError("reachability job design identity is invalid")
        return self


class EmpiricalRoleProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_audit_report_id: str = Field(min_length=1)
    source_audit_report_sha256: str = Field(min_length=64, max_length=64)
    task_source_report_id: str = Field(min_length=1)
    task_source_report_sha256: str = Field(min_length=64, max_length=64)
    instrument_job_manifest_id: str = Field(min_length=1)
    source_files: tuple[ProtocolSourceFile, ...] = Field(min_length=10)
    implementation_source: ProtocolImplementationSource
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    fallback_models: tuple[str, ...] = ()
    require_requested_model: Literal[True] = True
    model_invocation_config: dict[str, Any]
    model_config_hash: str = Field(min_length=1)
    provider_route: dict[str, str]
    provider_route_hash: str = Field(min_length=1)
    task_exposure_audits: tuple[TaskExposureAudit, ...] = Field(min_length=24, max_length=24)
    source_capability_task_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    source_vtdo_candidate_task_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    source_static_state_ids: tuple[str, ...] = Field(min_length=36, max_length=36)
    capability_source_task_count: Literal[12] = CAPABILITY_TASK_COUNT
    capability_api_exposed_task_count: Literal[8] = 8
    capability_unexposed_task_count: Literal[4] = 4
    capability_minimum_balanced_task_count: Literal[12] = CAPABILITY_TASK_COUNT
    capability_fresh_task_shortage: Literal[8] = 8
    capability_rollouts_per_task: Literal[8] = CAPABILITY_ROLLOUTS_PER_TASK
    capability_planned_job_count: Literal[96] = CAPABILITY_JOB_COUNT
    capability_fresh_population_required: Literal[True] = True
    capability_existing_task_reuse_forbidden: Literal[True] = True
    capability_task_primary_sampling_unit: Literal[True] = True
    capability_invalid_model_outcomes_retained: Literal[True] = True
    capability_protocol_frozen: Literal[True] = True
    capability_execution_ready: Literal[False] = False
    reachability_source_task_count: Literal[12] = REACHABILITY_TASK_COUNT
    reachability_api_exposed_task_count: Literal[0] = 0
    reachability_unexposed_task_count: Literal[12] = REACHABILITY_TASK_COUNT
    reachability_static_state_count: Literal[36] = STATIC_STATE_COUNT
    natural_rollouts_per_task: Literal[12] = NATURAL_ROLLOUTS_PER_TASK
    conditioned_rollouts_per_state: Literal[6] = CONDITIONED_ROLLOUTS_PER_STATE
    natural_job_count: Literal[144] = NATURAL_JOB_COUNT
    conditioned_job_count: Literal[216] = CONDITIONED_JOB_COUNT
    reachability_planned_job_count: Literal[360] = REACHABILITY_JOB_COUNT
    public_conditions: tuple[PublicReachabilityCondition, ...] = Field(min_length=3, max_length=3)
    reachability_job_scope_id: str = Field(min_length=1)
    reachability_jobs: tuple[ReachabilityJobDesign, ...] = Field(min_length=360, max_length=360)
    compiler_witnesses_excluded_from_empirical_counts: Literal[True] = True
    invalid_model_outcomes_retained_in_execution_denominator: Literal[True] = True
    independently_valid_model_trajectories_only_in_state_mapping: Literal[True] = True
    natural_and_conditioned_hits_separate: Literal[True] = True
    minimum_natural_hits_per_state: Literal[1] = 1
    conditioned_acceptance_lcb95_must_be_positive: Literal[True] = True
    minimum_released_realizations_per_state: Literal[3] = MINIMUM_RELEASED_REALIZATIONS
    maximum_estimated_attempts_for_three: float = MAXIMUM_ESTIMATED_ATTEMPTS_FOR_THREE
    reachability_task_primary_sampling_unit: Literal[True] = True
    rollout_secondary_sampling_unit: Literal[True] = True
    reachability_protocol_frozen: Literal[True] = True
    authority_preserving_runner_ready: Literal[False] = False
    runner_incompatibility_reasons: tuple[str, ...] = Field(min_length=3, max_length=3)
    reachability_execution_ready: Literal[False] = False
    capability_and_reachability_denominators_separate: Literal[True] = True
    historical_outcomes_used_for_task_selection: Literal[False] = False
    task_selection_performed: Literal[False] = False
    api_call_count: Literal[0] = 0
    gpu_job_count: Literal[0] = 0
    schema_version: str = V26_EMPIRICAL_ROLE_PROTOCOL_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> EmpiricalRoleProtocol:
        if self.task_exposure_audits != tuple(
            sorted(self.task_exposure_audits, key=lambda item: item.audit_id)
        ):
            raise ValueError("task exposure audits are not canonical")
        if self.reachability_jobs != tuple(
            sorted(self.reachability_jobs, key=lambda item: item.job_id)
        ):
            raise ValueError("reachability job designs are not canonical")
        exposure_counts = Counter(item.intended_use for item in self.task_exposure_audits)
        if exposure_counts != Counter(
            {
                "capability_measurement": CAPABILITY_TASK_COUNT,
                "vtdo_multistate_candidate": REACHABILITY_TASK_COUNT,
            }
        ):
            raise ValueError("protocol task roles have incomplete denominators")
        if sum(item.api_exposed_in_v26_66 for item in self.task_exposure_audits) != 8:
            raise ValueError("protocol exposure denominator differs from v26.66")
        mode_counts = Counter(item.sampling_mode for item in self.reachability_jobs)
        if mode_counts != Counter(
            {
                "reachability_unconditional": NATURAL_JOB_COUNT,
                "reachability_conditioned": CONDITIONED_JOB_COUNT,
            }
        ):
            raise ValueError("reachability job denominators changed")
        eligible_tasks = {
            item.task_package_id
            for item in self.task_exposure_audits
            if item.eligible_for_state_reachability
        }
        if {item.task_package_id for item in self.reachability_jobs} != eligible_tasks:
            raise ValueError("reachability jobs include an exposed or wrong-role task")
        if eligible_tasks != set(self.source_vtdo_candidate_task_ids):
            raise ValueError("VTDO candidate identity set differs from exposure audits")
        capability_ids = {
            item.task_package_id
            for item in self.task_exposure_audits
            if item.intended_use == "capability_measurement"
        }
        if capability_ids != set(self.source_capability_task_ids):
            raise ValueError("capability identity set differs from exposure audits")
        if {item.protocol_scope_id for item in self.reachability_jobs} != {
            self.reachability_job_scope_id
        }:
            raise ValueError("reachability jobs cross protocol-scope identities")
        state_counts = Counter(
            item.requested_quotient_state_id
            for item in self.reachability_jobs
            if item.sampling_mode == "reachability_conditioned"
        )
        if len(state_counts) != STATIC_STATE_COUNT or set(state_counts.values()) != {
            CONDITIONED_ROLLOUTS_PER_STATE
        }:
            raise ValueError("conditioned state denominators changed")
        if set(state_counts) != set(self.source_static_state_ids):
            raise ValueError("conditioned job states differ from the source catalogs")
        condition_by_strategy = {
            item.strategy: item.condition_id for item in self.public_conditions
        }
        if set(condition_by_strategy) != set(PATH_STRATEGIES):
            raise ValueError("public reachability condition set is incomplete")
        for item in self.reachability_jobs:
            if item.requested_path_strategy is not None and (
                item.public_condition_id != condition_by_strategy[item.requested_path_strategy]
            ):
                raise ValueError("reachability job condition identity changed")
        if self.protocol_id != empirical_role_protocol_id(self):
            raise ValueError("empirical role protocol identity is invalid")
        return self


class EmpiricalRoleProtocolReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    protocol: EmpiricalRoleProtocol
    capability_protocol_frozen: Literal[True] = True
    capability_execution_authorized: Literal[False] = False
    state_reachability_protocol_frozen: Literal[True] = True
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    historical_artifacts_mutated: Literal[False] = False
    api_call_count: Literal[0] = 0
    gpu_job_count: Literal[0] = 0
    status: Literal["protocols_frozen_execution_inputs_incomplete"] = (
        "protocols_frozen_execution_inputs_incomplete"
    )
    next_permitted_stage: Literal[
        "fresh_capability_population_and_authority_preserving_reachability_runner_only"
    ] = "fresh_capability_population_and_authority_preserving_reachability_runner_only"
    schema_version: str = V26_EMPIRICAL_ROLE_PROTOCOL_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> EmpiricalRoleProtocolReport:
        if self.run_id != self.protocol.run_id:
            raise ValueError("protocol report run identity changed")
        if self.report_id != empirical_role_protocol_report_id(self):
            raise ValueError("empirical role protocol report identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_count(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload) if isinstance(payload, list) else 1


def _source_file(prefix: str, root: Path, relative: str, expected: int) -> ProtocolSourceFile:
    path = root / relative
    if not path.is_file() or _record_count(path) != expected:
        raise ValueError(f"empirical protocol source denominator changed: {path}")
    return ProtocolSourceFile(
        relative_path=f"{prefix}/{relative}",
        sha256=_sha256(path),
        record_count=expected,
    )


def _write_json_atomic(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"empirical role protocol immutable JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _load_inputs(
    audit_dir: Path,
    task_source_dir: Path,
    instrument_dir: Path,
) -> tuple[
    AuthorityPreservingPostrunAuditReport,
    AuthorityPreservingHardeningReport,
    OperationClosureRegressionJobManifest,
    tuple[OperationalTaskRecord, ...],
    tuple[StaticModelAuthorityPathCatalog, ...],
    tuple[ProtocolSourceFile, ...],
]:
    audit_report = AuthorityPreservingPostrunAuditReport.model_validate_json(
        (audit_dir / "report.json").read_text(encoding="utf-8")
    )
    if (
        audit_report.status != "authority_preserving_operation_instrument_passed"
        or audit_report.next_permitted_stage
        != "capability_development_and_state_reachability_protocol_only"
        or not audit_report.authority_preserving_instrument_established
        or audit_report.capability_development_authorized
        or audit_report.state_reachability_pilot_authorized
    ):
        raise ValueError("v26.67 does not authorize empirical protocol construction")

    task_report_path = task_source_dir / "report.json"
    task_report = AuthorityPreservingHardeningReport.model_validate_json(
        task_report_path.read_text(encoding="utf-8")
    )
    if (
        audit_report.task_source_report_id != task_report.report_id
        or audit_report.task_source_report_sha256 != _sha256(task_report_path)
    ):
        raise ValueError("v26.68 task source differs from the audited v26.65 source")
    for item in task_report.immutable_artifact_files:
        path = task_source_dir / item.relative_path
        if _sha256(path) != item.sha256 or _record_count(path) != item.record_count:
            raise ValueError(f"v26.65 source Artifact changed: {item.relative_path}")

    manifest_path = instrument_dir / "job_manifest.json"
    manifest = OperationClosureRegressionJobManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    if audit_report.source_job_manifest_id != manifest.manifest_id:
        raise ValueError("v26.66 exposure manifest differs from the v26.67 audit")

    records = task_report.task_records
    catalogs = tuple(
        StaticModelAuthorityPathCatalog.model_validate(item)
        for item in json.loads(
            (task_source_dir / "static_model_authority_path_catalogs.json").read_text(
                encoding="utf-8"
            )
        )
    )
    if len(records) != 24 or len(catalogs) != 24:
        raise ValueError("v26.65 task or path-catalog denominator changed")
    catalog_by_task = {item.task_package_id: item for item in catalogs}
    if len(catalog_by_task) != 24 or {item.task_package.package_id for item in records} != set(
        catalog_by_task
    ):
        raise ValueError("v26.65 path catalogs differ from task identities")

    source_files = [
        _source_file("audit", audit_dir, "report.json", 1),
        _source_file("audit", audit_dir, "finalization_recovery_audit.json", 1),
        _source_file("audit", audit_dir, "rollout_authority_audits.json", 32),
        _source_file("audit", audit_dir, "mechanism_authority_summaries.json", 4),
        _source_file("instrument", instrument_dir, "job_manifest.json", 1),
        ProtocolSourceFile(
            relative_path="task_source/report.json",
            sha256=_sha256(task_report_path),
            record_count=1,
        ),
    ]
    source_files.extend(
        ProtocolSourceFile(
            relative_path=f"task_source/{item.relative_path}",
            sha256=item.sha256,
            record_count=item.record_count,
        )
        for item in task_report.immutable_artifact_files
    )
    return (
        audit_report,
        task_report,
        manifest,
        records,
        catalogs,
        tuple(sorted(source_files, key=lambda item: item.relative_path)),
    )


def _task_exposure_audits(
    records: Sequence[OperationalTaskRecord],
    manifest: OperationClosureRegressionJobManifest,
) -> tuple[TaskExposureAudit, ...]:
    job_counts = Counter(item.task_record_id for item in manifest.jobs)
    output = []
    for record in records:
        count = job_counts[record.record_id]
        eligible = record.intended_use == "vtdo_multistate_candidate" and count == 0
        values: dict[str, Any] = {
            "task_record_id": record.record_id,
            "task_package_id": record.task_package.package_id,
            "mechanism_id": record.mechanism_id,
            "intended_use": record.intended_use,
            "v26_66_instrument_job_count": count,
            "api_exposed_in_v26_66": count > 0,
            "eligible_for_state_reachability": eligible,
            "exclusion_reason": (
                "unopened_vtdo_candidate"
                if eligible
                else "capability_role_requires_fresh_balanced_population"
            ),
        }
        provisional = TaskExposureAudit.model_construct(audit_id="pending", **values)
        output.append(
            TaskExposureAudit(
                audit_id=task_exposure_audit_id(provisional),
                **values,
            )
        )
    return tuple(sorted(output, key=lambda item: item.audit_id))


def _reachability_jobs(
    *,
    scope_id: str,
    records: Sequence[OperationalTaskRecord],
    catalogs: Sequence[StaticModelAuthorityPathCatalog],
    conditions: Sequence[PublicReachabilityCondition],
) -> tuple[ReachabilityJobDesign, ...]:
    catalog_by_task = {item.task_package_id: item for item in catalogs}
    condition_by_strategy = {item.strategy: item for item in conditions}
    output = []

    def add(values: dict[str, Any]) -> None:
        provisional = ReachabilityJobDesign.model_construct(job_id="pending", **values)
        output.append(
            ReachabilityJobDesign(
                job_id=reachability_job_design_id(provisional),
                **values,
            )
        )

    candidates = sorted(
        (item for item in records if item.intended_use == "vtdo_multistate_candidate"),
        key=lambda item: item.task_package.package_id,
    )
    for record in candidates:
        common = {
            "protocol_scope_id": scope_id,
            "task_record_id": record.record_id,
            "task_package_id": record.task_package.package_id,
            "mechanism_id": record.mechanism_id,
        }
        for replicate in range(NATURAL_ROLLOUTS_PER_TASK):
            add(
                {
                    **common,
                    "sampling_mode": "reachability_unconditional",
                    "replicate_index": replicate,
                }
            )
        catalog = catalog_by_task[record.task_package.package_id]
        paths = {item.path_strategy_id: item for item in catalog.paths}
        if set(paths) != set(PATH_STRATEGIES):
            raise ValueError("v26.65 VTDO candidate lacks three static path strategies")
        for strategy in PATH_STRATEGIES:
            path = paths[strategy]
            condition = condition_by_strategy[strategy]
            for replicate in range(CONDITIONED_ROLLOUTS_PER_STATE):
                add(
                    {
                        **common,
                        "sampling_mode": "reachability_conditioned",
                        "replicate_index": replicate,
                        "requested_static_path_id": path.path_id,
                        "requested_path_strategy": strategy,
                        "requested_quotient_state_id": path.quotient_state_id,
                        "public_condition_id": condition.condition_id,
                    }
                )
    return tuple(sorted(output, key=lambda item: item.job_id))


def build_empirical_role_protocol(
    *,
    run_id: str,
    audit_dir: Path,
    task_source_dir: Path,
    instrument_dir: Path,
    model_config_path: Path,
    output_dir: Path,
    package_root: Path,
) -> EmpiricalRoleProtocolReport:
    (
        audit_report,
        task_report,
        manifest,
        records,
        catalogs,
        source_files,
    ) = _load_inputs(audit_dir, task_source_dir, instrument_dir)
    model_payload = json.loads(model_config_path.read_text(encoding="utf-8"))
    model = AgentModelConfig.model_validate(model_payload.get("model", model_payload))
    if model.model != "deepseek-v4-flash" or model.fallback_models:
        raise ValueError("v26.68 requires exact DeepSeek V4-Flash with no fallback")
    public_model = model.model_dump(mode="json")
    model_hash = canonical_hash(public_model, prefix="finance_v26_role_protocol_model:")
    provider_route = {
        "provider": model.provider,
        "endpoint_host": urlparse(model.endpoint).netloc,
        "model": model.model,
    }
    conditions = tuple(make_public_reachability_condition(item) for item in PATH_STRATEGIES)
    exposure_audits = _task_exposure_audits(records, manifest)
    capability_ids = tuple(
        sorted(
            item.task_package.package_id
            for item in records
            if item.intended_use == "capability_measurement"
        )
    )
    vtdo_ids = tuple(
        sorted(
            item.task_package.package_id
            for item in records
            if item.intended_use == "vtdo_multistate_candidate"
        )
    )
    state_ids = tuple(
        sorted(
            path.quotient_state_id
            for item in catalogs
            if item.task_package_id in set(vtdo_ids)
            for path in item.paths
        )
    )
    scope_id = canonical_hash(
        {
            "source_audit_report_id": audit_report.report_id,
            "task_source_report_id": task_report.report_id,
            "instrument_job_manifest_id": manifest.manifest_id,
            "model_config_hash": model_hash,
            "condition_ids": tuple(item.condition_id for item in conditions),
            "vtdo_task_ids": vtdo_ids,
            "state_ids": state_ids,
        },
        prefix="finance_v26_reachability_job_scope:",
    )
    reachability_jobs = _reachability_jobs(
        scope_id=scope_id,
        records=records,
        catalogs=catalogs,
        conditions=conditions,
    )
    values: dict[str, Any] = {
        "run_id": run_id,
        "source_audit_report_id": audit_report.report_id,
        "source_audit_report_sha256": _sha256(audit_dir / "report.json"),
        "task_source_report_id": task_report.report_id,
        "task_source_report_sha256": _sha256(task_source_dir / "report.json"),
        "instrument_job_manifest_id": manifest.manifest_id,
        "source_files": source_files,
        "implementation_source": ProtocolImplementationSource(
            sha256=_sha256(package_root / IMPLEMENTATION_SOURCE_PATH)
        ),
        "model_invocation_config": public_model,
        "model_config_hash": model_hash,
        "provider_route": provider_route,
        "provider_route_hash": canonical_hash(
            provider_route, prefix="finance_v26_role_protocol_provider_route:"
        ),
        "task_exposure_audits": exposure_audits,
        "source_capability_task_ids": capability_ids,
        "source_vtdo_candidate_task_ids": vtdo_ids,
        "source_static_state_ids": state_ids,
        "public_conditions": conditions,
        "reachability_job_scope_id": scope_id,
        "reachability_jobs": reachability_jobs,
        "runner_incompatibility_reasons": (
            "v26_57_runner_loads_the_v26_56_source_report_schema",
            "v26_57_runner_binds_legacy_task_record_and_runtime_versions",
            "v26_57_runner_lacks_v3_repair_and_terminal_target_instrument_audits",
        ),
    }
    provisional = EmpiricalRoleProtocol.model_construct(protocol_id="pending", **values)
    protocol = EmpiricalRoleProtocol(
        protocol_id=empirical_role_protocol_id(provisional),
        **values,
    )
    report_values = {"run_id": run_id, "protocol": protocol}
    report_provisional = EmpiricalRoleProtocolReport.model_construct(
        report_id="pending", **report_values
    )
    report = EmpiricalRoleProtocolReport(
        report_id=empirical_role_protocol_report_id(report_provisional),
        **report_values,
    )
    _write_json_atomic(
        output_dir / "task_exposure_audits.json",
        [item.model_dump(mode="json") for item in exposure_audits],
    )
    _write_json_atomic(
        output_dir / "reachability_job_design.json",
        [item.model_dump(mode="json") for item in reachability_jobs],
    )
    _write_json_atomic(output_dir / "protocol.json", protocol.model_dump(mode="json"))
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def task_exposure_audit_id(value: TaskExposureAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_task_exposure_audit:",
    )


def reachability_job_design_id(value: ReachabilityJobDesign) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"job_id"}),
        prefix="finance_v26_reachability_job_design:",
    )


def empirical_role_protocol_id(value: EmpiricalRoleProtocol) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"protocol_id"}),
        prefix="finance_v26_empirical_role_protocol:",
    )


def empirical_role_protocol_report_id(value: EmpiricalRoleProtocolReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_empirical_role_protocol_report:",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze the credential-free v26.68 role-separated empirical protocols"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--instrument-dir", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    report = build_empirical_role_protocol(
        run_id=args.run_id,
        audit_dir=args.audit_dir,
        task_source_dir=args.task_source_dir,
        instrument_dir=args.instrument_dir,
        model_config_path=args.model_config,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(
        json.dumps(
            {
                "report_id": report.report_id,
                "protocol_id": report.protocol.protocol_id,
                "status": report.status,
                "next_permitted_stage": report.next_permitted_stage,
                "api_call_count": report.api_call_count,
                "gpu_job_count": report.gpu_job_count,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
