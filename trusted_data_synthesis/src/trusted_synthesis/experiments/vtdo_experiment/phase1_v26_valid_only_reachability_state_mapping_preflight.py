from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.trajectory_validity import (
    QualifiedTrajectoryValidityReport,
)
from trusted_synthesis.core.evaluation.valid_only_state_mapping import (
    ValidOnlyStateMapperContract,
    make_valid_only_state_mapper_contract,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping import (
    EMPIRICAL_STATE_CANONICALIZER_VERSION,
    EMPIRICAL_STATE_MAPPING_VERSION,
    PublicTrajectoryAction,
    PublicTrajectoryProjection,
    make_empirical_route_projection,
    make_public_trajectory_projection,
    map_independently_valid_public_trajectory_to_state,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authority_preserving_verifier_replay as authority_verifier,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_execution as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_postrun_audit as postrun,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_runner_preflight as preflight,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import prospective_reachability_runner_vnext as runner_vnext

RUN_ID: Final = "finance_v26_156_valid_only_state_mapping_preflight_v1_20260826"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_156_valid_only_state_mapping_preflight_v1_20260826"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_valid_only_reachability_state_mapping_preflight.py"
)
MAPPER_IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/core/trajectory/empirical_state_mapping.py"
)
NEXT_STAGE: Final = "valid_only_observed_reachability_state_mapping_execution_only"

# Replaced only after the immutable v26.155 audit closes.
EXPECTED_POSTRUN_REPORT_ID: Final = (
    "finance_v26_fresh_reachability_postrun_audit_report:"
    "8e80ef33293cc7ddc445e04da7327f57dae9e55f898813d2897d1a01087b1dc3"
)
EXPECTED_POSTRUN_REPORT_SHA256: Final = (
    "baae2aeef5738d0b711eb4bd2beee513a80b9aab81137aadd8fb73e11b14f2cb"
)
EXPECTED_POSTRUN_TRANSITION_ID: Final = (
    "finance_v26_fresh_reachability_postrun_transition:"
    "7df8dc34a3af7cd046942eebdb619298090aefdc5fafcdb9ba7c15ee47740222"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        + b"\n"
    )


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _resolve_package_root(implementation_root: Path) -> Path:
    if (implementation_root / "src" / "trusted_synthesis").is_dir():
        return implementation_root
    candidate = implementation_root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate
    raise ValueError("v26.156 cannot resolve package root")


class PredecessorReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    postrun_report_id: str = EXPECTED_POSTRUN_REPORT_ID
    postrun_report_sha256: str = EXPECTED_POSTRUN_REPORT_SHA256
    predecessor_output_file_count: int = Field(ge=10)
    predecessor_rebuilt_file_count: int = Field(ge=10)
    predecessor_byte_match_count: int = Field(ge=10)
    mapper_implementation_sha256: str = Field(min_length=64, max_length=64)
    preflight_implementation_sha256: str = Field(min_length=64, max_length=64)
    replay_completed_before_mapping_input_loading: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorReplayAudit:
        if not (
            self.predecessor_output_file_count
            == self.predecessor_rebuilt_file_count
            == self.predecessor_byte_match_count
        ):
            raise ValueError("v26.156 predecessor rebuild denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_valid_only_mapping_source_replay:",
        ):
            raise ValueError("v26.156 source replay identity changed")
        return self


class OmegaTaskContextBinding(FrozenModel):
    context_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    tier: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    verifier_contract_id: str = Field(min_length=1)
    joint_support_validity_contract_id: str = Field(min_length=1)
    qualified_final_grammar_id: str = Field(min_length=1)
    task_package_content_hash: str = Field(min_length=1)
    operational_record_content_hash: str = Field(min_length=1)
    environment_content_hash: str = Field(min_length=1)
    schema_version: str = "finance_v26_valid_only_omega_task_context.v1"

    @model_validator(mode="after")
    def validate_context(self) -> OmegaTaskContextBinding:
        if self.context_id != _identity(
            self,
            "context_id",
            "finance_v26_valid_only_omega_task_context:",
        ):
            raise ValueError("v26.156 Omega Task Context identity changed")
        return self


class OmegaTaskContextCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_task_package_catalog_id: str = Field(min_length=1)
    context_count: Literal[12] = 12
    contexts: tuple[OmegaTaskContextBinding, ...] = Field(min_length=12, max_length=12)
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> OmegaTaskContextCatalog:
        ids = tuple(item.context_id for item in self.contexts)
        tasks = tuple(item.task_package_id for item in self.contexts)
        if (
            ids != tuple(sorted(set(ids)))
            or len(set(tasks)) != 12
            or self.catalog_id
            != _identity(
                self,
                "catalog_id",
                "finance_v26_valid_only_omega_task_context_catalog:",
            )
        ):
            raise ValueError("v26.156 Omega Task Context Catalog changed")
        return self


class EmpiricalStateMapperProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    valid_only_mapper_contract_id: str = Field(min_length=1)
    omega_task_context_catalog_id: str = Field(min_length=1)
    static_path_catalog_id: str = Field(min_length=1)
    mapper_version: str = EMPIRICAL_STATE_MAPPING_VERSION
    canonicalizer_version: str = EMPIRICAL_STATE_CANONICALIZER_VERSION
    trajectory_projection_inputs: tuple[str, ...] = (
        "semantic_choices",
        "reversible_commits",
        "public_observations",
        "semantic_rejections",
        "completed_final_result",
    )
    runtime_operation_refs_normalized_to_program_nodes: Literal[True] = True
    independent_action_order_quotiented_by_dependency_multiset: Literal[True] = True
    repeated_action_multiplicity_preserved: Literal[True] = True
    result_semantics_bound: Literal[True] = True
    evidence_lineage_bound: Literal[True] = True
    failure_pattern_bound: Literal[True] = True
    route_projection_separate_from_structural_state: Literal[True] = True
    static_path_is_target_condition_only: Literal[True] = True
    full_raw_observation_prefix_bound: Literal[True] = True
    schema_version: str = "finance_v26_empirical_state_mapper_protocol.v1"

    @model_validator(mode="after")
    def validate_protocol(self) -> EmpiricalStateMapperProtocol:
        if self.protocol_id != _identity(
            self,
            "protocol_id",
            "finance_v26_empirical_state_mapper_protocol:",
        ):
            raise ValueError("v26.156 empirical Mapper Protocol identity changed")
        return self


class ValidOnlyMappingCandidate(FrozenModel):
    candidate_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    trajectory_content_hash: str = Field(min_length=1)
    qualified_validity_report_id: str = Field(min_length=1)
    omega_task_context_id: str = Field(min_length=1)
    route_condition_id: str = Field(min_length=1)
    static_path_catalog_id: str = Field(min_length=1)
    raw_observation_prefix_hash: str = Field(min_length=1)
    raw_execution_relative_path: str = Field(min_length=1)
    raw_execution_sha256: str = Field(min_length=64, max_length=64)
    runtime_operation_alias_binding_hash: str = Field(min_length=1)
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"]
    public_condition_id: str | None = None
    requested_path_id: str | None = None
    requested_path_strategy: str | None = None
    qualified_validity: Literal[True] = True
    state_mapping_eligible: Literal[True] = True
    structural_state_id: None = None
    state_assignment_id: None = None
    schema_version: str = "finance_v26_valid_only_mapping_candidate.v1"

    @model_validator(mode="after")
    def validate_candidate(self) -> ValidOnlyMappingCandidate:
        conditioned = self.sampling_mode == "reachability_conditioned"
        if (
            conditioned != (self.public_condition_id is not None)
            or conditioned != (self.requested_path_id is not None)
            or conditioned != (self.requested_path_strategy is not None)
            or self.candidate_id
            != _identity(
                self,
                "candidate_id",
                "finance_v26_valid_only_mapping_candidate:",
            )
        ):
            raise ValueError("v26.156 valid-only Mapping Candidate changed")
        return self


class ValidOnlyMappingCandidateManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    postrun_report_id: str = EXPECTED_POSTRUN_REPORT_ID
    mapper_protocol_id: str = Field(min_length=1)
    valid_only_mapper_contract_id: str = Field(min_length=1)
    omega_task_context_catalog_id: str = Field(min_length=1)
    static_path_catalog_id: str = Field(min_length=1)
    exact_reachability_denominator: Literal[360] = 360
    qualified_candidate_count: int = Field(ge=1, le=360)
    excluded_nonqualified_count: int = Field(ge=0, le=359)
    candidates: tuple[ValidOnlyMappingCandidate, ...] = Field(min_length=1)
    state_assignment_count: Literal[0] = 0
    structural_state_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = "finance_v26_valid_only_mapping_candidate_manifest.v1"

    @model_validator(mode="after")
    def validate_manifest(self) -> ValidOnlyMappingCandidateManifest:
        candidate_ids = tuple(item.candidate_id for item in self.candidates)
        job_ids = tuple(item.job_id for item in self.candidates)
        if (
            self.qualified_candidate_count != len(self.candidates)
            or self.qualified_candidate_count + self.excluded_nonqualified_count != 360
            or candidate_ids != tuple(sorted(set(candidate_ids)))
            or len(set(job_ids)) != len(job_ids)
            or self.manifest_id
            != _identity(
                self,
                "manifest_id",
                "finance_v26_valid_only_mapping_candidate_manifest:",
            )
        ):
            raise ValueError("v26.156 Mapping Candidate Manifest changed")
        return self


class MapperConstructibilityFixture(FrozenModel):
    fixture_id: str = Field(min_length=1)
    valid_fixture_count: Literal[3] = 3
    identical_state_after_runtime_alias_change_count: Literal[1] = 1
    identical_state_after_independent_action_reordering_count: Literal[1] = 1
    distinct_trajectory_content_hash_count: Literal[3] = 3
    exact_assignment_binding_count: Literal[8] = 8
    mapper_invocation_count: Literal[3] = 3
    actual_candidate_assignment_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_fixture(self) -> MapperConstructibilityFixture:
        if self.fixture_id != _identity(
            self,
            "fixture_id",
            "finance_v26_valid_only_mapper_constructibility_fixture:",
        ):
            raise ValueError("v26.156 Mapper constructibility fixture changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True
    mapper_invocations_before_rejection: Literal[0] = 0


class MappingDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[20] = 20
    rejected_count: Literal[20] = 20
    mutation_results: tuple[MutationResult, ...] = Field(min_length=20, max_length=20)
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> MappingDestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))) or self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_valid_only_mapping_destructive:",
        ):
            raise ValueError("v26.156 Mapping destructive audit changed")
        return self


class ValidOnlyMappingPreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    postrun_report_id: str = EXPECTED_POSTRUN_REPORT_ID
    mapper_contract_id: str = Field(min_length=1)
    mapper_protocol_id: str = Field(min_length=1)
    omega_task_context_catalog_id: str = Field(min_length=1)
    candidate_manifest_id: str = Field(min_length=1)
    exact_reachability_denominator: Literal[360] = 360
    qualified_candidate_count: int = Field(ge=1, le=360)
    independently_qualified_report_match_count: int = Field(ge=1, le=360)
    exact_raw_descriptor_match_count: int = Field(ge=1, le=360)
    exact_omega_binding_match_count: int = Field(ge=1, le=360)
    exact_route_binding_match_count: int = Field(ge=1, le=360)
    exact_required_input_binding_match_count: int = Field(ge=1, le=360)
    support_exit_candidate_count: Literal[0] = 0
    instrument_failure_candidate_count: Literal[0] = 0
    privacy_failure_candidate_count: Literal[0] = 0
    base_invalid_candidate_count: Literal[0] = 0
    mechanism_unqualified_candidate_count: Literal[0] = 0
    actual_state_assignment_count: Literal[0] = 0
    actual_structural_state_count: Literal[0] = 0
    synthetic_constructibility_fixture_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> ValidOnlyMappingPreflightAudit:
        counts = (
            self.independently_qualified_report_match_count,
            self.exact_raw_descriptor_match_count,
            self.exact_omega_binding_match_count,
            self.exact_route_binding_match_count,
            self.exact_required_input_binding_match_count,
        )
        if any(
            item != self.qualified_candidate_count for item in counts
        ) or self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_valid_only_mapping_preflight:",
        ):
            raise ValueError("v26.156 valid-only Mapping preflight changed")
        return self


class ValidOnlyMappingRunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    postrun_report_id: str = EXPECTED_POSTRUN_REPORT_ID
    candidate_manifest_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    mapper_protocol_id: str = Field(min_length=1)
    preflight_audit_id: str = Field(min_length=1)
    prospective_execution_id: str = Field(min_length=1)
    prospective_report_id: str = Field(min_length=1)
    exact_candidate_denominator: int = Field(ge=1, le=360)
    raw_only_execution: Literal[True] = True
    independent_qualified_validity_report_required: Literal[True] = True
    mapping_callback_after_valid_only_authorization: Literal[True] = True
    every_assignment_binds_eight_required_parents: Literal[True] = True
    support_integrity_or_nonqualified_row_fails_before_mapper: Literal[True] = True
    route_projection_separate_from_structural_state: Literal[True] = True
    static_path_is_target_condition_only: Literal[True] = True
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: str = "finance_v26_valid_only_mapping_runner_contract.v1"

    @model_validator(mode="after")
    def validate_contract(self) -> ValidOnlyMappingRunnerContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_valid_only_mapping_runner_contract:",
        ):
            raise ValueError("v26.156 Mapping Runner Contract changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    exact_candidate_denominator: int = Field(ge=1, le=360)
    state_mapping_execution_authorized: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    reachability_frequency_estimand_authorized: Literal[False] = False
    support_or_nonqualified_mapping_authorized: Literal[False] = False
    historical_rerun_recovery_or_pooling_authorized: Literal[False] = False
    reachability_identity_or_job_change_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False
    status: Literal["valid_only_state_mapping_execution_only"] = (
        "valid_only_state_mapping_execution_only"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_valid_only_mapping_transition:",
        ):
            raise ValueError("v26.156 Mapping transition changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class ValidOnlyMappingPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    omega_task_context_catalog_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    mapper_protocol_id: str = Field(min_length=1)
    candidate_manifest_id: str = Field(min_length=1)
    constructibility_fixture_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    preflight_audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    qualified_candidate_count: int = Field(ge=1, le=360)
    state_assignment_count: Literal[0] = 0
    structural_state_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    detail_files: tuple[DetailFile, ...] = Field(min_length=10, max_length=10)
    status: Literal["valid_only_state_mapping_preflight_passed"] = (
        "valid_only_state_mapping_preflight_passed"
    )

    @model_validator(mode="after")
    def validate_report(self) -> ValidOnlyMappingPreflightReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_valid_only_mapping_preflight_report:",
        ):
            raise ValueError("v26.156 report identity changed")
        return self


@dataclass(frozen=True)
class Inputs:
    postrun_report: postrun.PostrunAuditReport
    postrun_transition: postrun.ProspectiveTransitionContract
    projection: postrun.IndependentProjectionAudit
    task_catalog: preflight.TaskPackageCatalog
    path_catalog: preflight.PathCatalog
    manifest: preflight.ReachabilityManifest
    packages: dict[str, preflight.FreshReachabilityTaskPackage]
    jobs: dict[str, preflight.FreshReachabilityJob]
    raws: dict[str, runner_vnext.FreshReachabilityRawExecution]


def _predecessor_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    postrun_dir: Path,
) -> PredecessorReplayAudit:
    report_path = postrun_dir / "report.json"
    if not report_path.is_file() or _sha256(report_path) != EXPECTED_POSTRUN_REPORT_SHA256:
        raise ValueError("v26.156 predecessor report SHA-256 changed")
    report = postrun.PostrunAuditReport.model_validate(_load(report_path))
    if report.report_id != EXPECTED_POSTRUN_REPORT_ID:
        raise ValueError("v26.156 predecessor report identity changed")

    with tempfile.TemporaryDirectory(prefix="v26_156_postrun_rebuild_") as temporary:
        rebuilt_dir = Path(temporary)
        rebuilt = postrun.build_postrun_audit(
            package_root=package_root,
            implementation_root=implementation_root,
            execution_dir=execution_dir,
            output_dir=rebuilt_dir,
        )
        if rebuilt.report_id != EXPECTED_POSTRUN_REPORT_ID:
            raise ValueError("v26.156 independent predecessor rebuild changed")
        frozen_files = tuple(sorted(path.name for path in postrun_dir.iterdir() if path.is_file()))
        rebuilt_files = tuple(sorted(path.name for path in rebuilt_dir.iterdir() if path.is_file()))
        if frozen_files != rebuilt_files:
            raise ValueError("v26.156 predecessor output file set changed")
        matches = sum(
            (postrun_dir / name).read_bytes() == (rebuilt_dir / name).read_bytes()
            for name in frozen_files
        )
    values = {
        "predecessor_output_file_count": len(frozen_files),
        "predecessor_rebuilt_file_count": len(rebuilt_files),
        "predecessor_byte_match_count": matches,
        "mapper_implementation_sha256": _sha256(package_root / MAPPER_IMPLEMENTATION_PATH),
        "preflight_implementation_sha256": _sha256(package_root / IMPLEMENTATION_PATH),
    }
    provisional = PredecessorReplayAudit.model_construct(audit_id="pending", **values)
    return PredecessorReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_valid_only_mapping_source_replay:",
        ),
        **values,
    )


def _load_inputs(
    *,
    package_root: Path,
    postrun_dir: Path,
    execution_dir: Path,
) -> Inputs:
    report = postrun.PostrunAuditReport.model_validate(_load(postrun_dir / "report.json"))
    transition = postrun.ProspectiveTransitionContract.model_validate(
        _load(postrun_dir / "prospective_transition_contract.json")
    )
    projection = postrun.IndependentProjectionAudit.model_validate(
        _load(postrun_dir / "independent_projection_audit.json")
    )
    if (
        report.report_id != EXPECTED_POSTRUN_REPORT_ID
        or transition.contract_id != EXPECTED_POSTRUN_TRANSITION_ID
        or not report.valid_only_mapping_preflight_authorized
        or not transition.valid_only_observed_state_mapping_preflight_authorized
        or transition.state_mapping_execution_authorized
        or report.qualified_valid_count < 1
        or report.qualified_valid_count != report.state_mapping_eligible_count
    ):
        raise ValueError("v26.156 predecessor authorization changed")

    task_catalog = preflight.TaskPackageCatalog.model_validate(
        _load(execution_dir / "frozen_reachability_task_package_catalog.json")
    )
    path_catalog = preflight.PathCatalog.model_validate(
        _load(execution_dir / "frozen_reachability_path_catalog.json")
    )
    manifest = preflight.ReachabilityManifest.model_validate(
        _load(execution_dir / "frozen_reachability_manifest.json")
    )
    packages = {item.task_package_id: item for item in task_catalog.packages}
    jobs = {item.job_id: item for item in manifest.jobs}
    if len(packages) != 12 or len(jobs) != 360:
        raise ValueError("v26.156 frozen Reachability identity denominator changed")

    raws: dict[str, runner_vnext.FreshReachabilityRawExecution] = {}
    for result in projection.recomputed_results:
        descriptor = result.raw_execution_artifact
        path = execution_dir / descriptor.relative_path
        if (
            not path.is_file()
            or _sha256(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError(f"v26.156 Raw descriptor changed: {result.job_id}")
        raw = runner_vnext.FreshReachabilityRawExecution.model_validate(_load(path))
        if (
            raw.job_id != result.job_id
            or raw.artifact_id != result.raw_execution_id
            or result.job_id not in jobs
            or raw.task_package_id != jobs[result.job_id].task_package_id
        ):
            raise ValueError(f"v26.156 Raw parent binding changed: {result.job_id}")
        raws[result.job_id] = raw
    if len(raws) != 360:
        raise ValueError("v26.156 Raw denominator changed")
    return Inputs(
        postrun_report=report,
        postrun_transition=transition,
        projection=projection,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
        manifest=manifest,
        packages=packages,
        jobs=jobs,
        raws=raws,
    )


def _omega_catalog(inputs: Inputs) -> OmegaTaskContextCatalog:
    contexts: list[OmegaTaskContextBinding] = []
    for package in inputs.task_catalog.packages:
        values = {
            "task_package_id": package.task_package_id,
            "source_task_artifact_id": package.source_task_artifact_id,
            "mechanism_id": package.mechanism_id,
            "tier": package.tier,
            "operational_record_id": package.operational_record.record_id,
            "environment_manifest_id": package.environment.manifest_id,
            "verifier_contract_id": package.verifier_vnext_contract_id,
            "joint_support_validity_contract_id": (package.joint_support_validity_contract_id),
            "qualified_final_grammar_id": package.qualified_final_grammar_id,
            "task_package_content_hash": canonical_hash(
                package,
                prefix="finance_v26_reachability_task_package_content:",
            ),
            "operational_record_content_hash": canonical_hash(
                package.operational_record,
                prefix="finance_v26_operational_record_content:",
            ),
            "environment_content_hash": canonical_hash(
                package.environment,
                prefix="finance_v26_environment_content:",
            ),
        }
        provisional = OmegaTaskContextBinding.model_construct(
            context_id="pending",
            **values,
        )
        contexts.append(
            OmegaTaskContextBinding(
                context_id=_identity(
                    provisional,
                    "context_id",
                    "finance_v26_valid_only_omega_task_context:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(contexts, key=lambda item: item.context_id))
    values = {
        "source_task_package_catalog_id": inputs.task_catalog.catalog_id,
        "contexts": ordered,
    }
    provisional = OmegaTaskContextCatalog.model_construct(
        catalog_id="pending",
        **values,
    )
    return OmegaTaskContextCatalog(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "finance_v26_valid_only_omega_task_context_catalog:",
        ),
        **values,
    )


def _trajectory_projection(
    raw: runner_vnext.FreshReachabilityRawExecution,
) -> PublicTrajectoryProjection:
    observations = {item.call.call_index: item for item in raw.observations}
    actions: list[PublicTrajectoryAction] = []
    for action_index, record in enumerate(raw.commits):
        commit = record.commit
        call = commit.call
        observation = observations.get(call.call_index) if call is not None else None
        actions.append(
            PublicTrajectoryAction(
                action_index=action_index,
                decision_kind=commit.decision_kind,
                action_kind=commit.action,
                tool_id=call.tool_id if call is not None else None,
                arguments=dict(call.arguments) if call is not None else {},
                observation_status=observation.status if observation is not None else None,
                error_code=observation.error_code if observation is not None else None,
                observation_result=(dict(observation.result) if observation is not None else None),
                evidence_ids=(
                    tuple(sorted(set(observation.evidence_ids))) if observation is not None else ()
                ),
                provenance_hashes=(
                    tuple(sorted(set(observation.provenance_hashes)))
                    if observation is not None
                    else ()
                ),
            )
        )
    completed = raw.completed_result
    final_result = dict(completed.final_payload.answer.result) if completed is not None else None
    citations = (
        tuple(sorted({item.evidence_id for item in completed.final_payload.answer.citations}))
        if completed is not None
        else ()
    )
    return make_public_trajectory_projection(
        trajectory_id=raw.artifact_id,
        terminal_disposition=raw.terminal_disposition,
        actions=actions,
        semantic_rejections=tuple(item.model_dump(mode="json") for item in raw.semantic_rejections),
        final_result=final_result,
        final_citations=citations,
    )


def _runtime_aliases(
    package: preflight.FreshReachabilityTaskPackage,
    raw: runner_vnext.FreshReachabilityRawExecution,
) -> dict[str, str]:
    _, _, aliases, _ = authority_verifier.match_empirical_program(
        cast(Any, package.operational_record),
        raw.observations,
    )
    return dict(aliases)


def _make_mapper_contract(
    inputs: Inputs,
    *,
    package_root: Path,
) -> ValidOnlyStateMapperContract:
    verifier_ids = {item.verifier_vnext_contract_id for item in inputs.task_catalog.packages}
    if len(verifier_ids) != 1:
        raise ValueError("v26.156 TaskPackages crossed Verifier Contracts")
    implementation_id = canonical_hash(
        {
            "relative_path": MAPPER_IMPLEMENTATION_PATH,
            "sha256": _sha256(package_root / MAPPER_IMPLEMENTATION_PATH),
        },
        prefix="finance_v26_empirical_state_mapper_implementation:",
    )
    return make_valid_only_state_mapper_contract(
        qualified_verifier_contract_id=next(iter(verifier_ids)),
        mapper_implementation_id=implementation_id,
        mapper_version=EMPIRICAL_STATE_MAPPING_VERSION,
    )


def _make_protocol(
    *,
    mapper_contract: ValidOnlyStateMapperContract,
    omega: OmegaTaskContextCatalog,
    inputs: Inputs,
) -> EmpiricalStateMapperProtocol:
    values = {
        "valid_only_mapper_contract_id": mapper_contract.contract_id,
        "omega_task_context_catalog_id": omega.catalog_id,
        "static_path_catalog_id": inputs.path_catalog.catalog_id,
    }
    provisional = EmpiricalStateMapperProtocol.model_construct(
        protocol_id="pending",
        **values,
    )
    return EmpiricalStateMapperProtocol(
        protocol_id=_identity(
            provisional,
            "protocol_id",
            "finance_v26_empirical_state_mapper_protocol:",
        ),
        **values,
    )


def _candidate_manifest(
    *,
    inputs: Inputs,
    omega: OmegaTaskContextCatalog,
    mapper_contract: ValidOnlyStateMapperContract,
    protocol: EmpiricalStateMapperProtocol,
) -> ValidOnlyMappingCandidateManifest:
    contexts = {item.task_package_id: item for item in omega.contexts}
    candidates: list[ValidOnlyMappingCandidate] = []
    for result in inputs.projection.recomputed_results:
        if result.qualified_trajectory_validity is not True:
            continue
        if (
            not result.state_mapping_eligible
            or result.joint_result.qualified_report.valid is not True
            or result.joint_result.qualified_report.report_id == ""
            or not result.measurement_support_available
            or not result.instrument_integrity
            or not result.privacy_compliant
            or result.base_trajectory_validity is not True
            or result.mechanism_qualification is not True
        ):
            raise ValueError(f"v26.156 invalid Mapping Candidate admitted: {result.job_id}")
        job = inputs.jobs[result.job_id]
        package = inputs.packages[job.task_package_id]
        context = contexts[package.task_package_id]
        raw = inputs.raws[result.job_id]
        trajectory = _trajectory_projection(raw)
        aliases = _runtime_aliases(package, raw)
        route = make_empirical_route_projection(
            sampling_mode=job.sampling_mode,
            public_condition_id=job.public_condition_id,
            requested_path_id=job.requested_path_id,
            requested_path_strategy=job.requested_path_strategy,
            static_path_catalog_id=inputs.path_catalog.catalog_id,
            trajectory=trajectory,
        )
        descriptor = result.raw_execution_artifact
        values = {
            "job_id": result.job_id,
            "task_package_id": package.task_package_id,
            "trajectory_id": trajectory.trajectory_id,
            "trajectory_content_hash": trajectory.trajectory_content_hash,
            "qualified_validity_report_id": (result.joint_result.qualified_report.report_id),
            "omega_task_context_id": context.context_id,
            "route_condition_id": route.projection_id,
            "static_path_catalog_id": inputs.path_catalog.catalog_id,
            "raw_observation_prefix_hash": trajectory.raw_observation_prefix_hash,
            "raw_execution_relative_path": descriptor.relative_path,
            "raw_execution_sha256": descriptor.sha256,
            "runtime_operation_alias_binding_hash": canonical_hash(
                aliases,
                prefix="finance_v26_runtime_operation_alias_binding:",
            ),
            "sampling_mode": job.sampling_mode,
            "public_condition_id": job.public_condition_id,
            "requested_path_id": job.requested_path_id,
            "requested_path_strategy": job.requested_path_strategy,
        }
        provisional = ValidOnlyMappingCandidate.model_construct(
            candidate_id="pending",
            **values,
        )
        candidates.append(
            ValidOnlyMappingCandidate(
                candidate_id=_identity(
                    provisional,
                    "candidate_id",
                    "finance_v26_valid_only_mapping_candidate:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(candidates, key=lambda item: item.candidate_id))
    if len(ordered) != inputs.postrun_report.qualified_valid_count:
        raise ValueError("v26.156 Qualified Mapping Candidate count changed")
    values = {
        "mapper_protocol_id": protocol.protocol_id,
        "valid_only_mapper_contract_id": mapper_contract.contract_id,
        "omega_task_context_catalog_id": omega.catalog_id,
        "static_path_catalog_id": inputs.path_catalog.catalog_id,
        "qualified_candidate_count": len(ordered),
        "excluded_nonqualified_count": 360 - len(ordered),
        "candidates": ordered,
    }
    provisional = ValidOnlyMappingCandidateManifest.model_construct(
        manifest_id="pending",
        **values,
    )
    return ValidOnlyMappingCandidateManifest(
        manifest_id=_identity(
            provisional,
            "manifest_id",
            "finance_v26_valid_only_mapping_candidate_manifest:",
        ),
        **values,
    )


def _qualified_fixture_report(
    *,
    mapper_contract: ValidOnlyStateMapperContract,
    trajectory_id: str = "synthetic-valid-trajectory",
    valid: bool | None = True,
) -> QualifiedTrajectoryValidityReport:
    values: dict[str, Any] = {
        "verifier_contract_id": mapper_contract.qualified_verifier_contract_id,
        "trajectory_id": trajectory_id,
        "eligibility_id": "synthetic-eligibility",
        "base_report_id": "synthetic-base-report",
        "mechanism_report_id": "synthetic-mechanism-report",
        "valid": valid,
        "state_mapping_eligible": valid is True,
    }
    provisional = QualifiedTrajectoryValidityReport.model_construct(
        report_id="pending",
        **values,
    )
    return QualifiedTrajectoryValidityReport(
        report_id=canonical_hash(
            provisional.model_dump(mode="json", exclude={"report_id"}),
            prefix="prospective_qualified_trajectory_validity_report:",
        ),
        **values,
    )


def _synthetic_actions(
    runtime_ref: str,
    *,
    reverse_inputs: bool = False,
) -> tuple[PublicTrajectoryAction, ...]:
    inputs = [
        PublicTrajectoryAction(
            action_index=0,
            decision_kind="acquire_public_input",
            action_kind="call_tool",
            tool_id="query_structured_fact",
            arguments={"subject": "A"},
            observation_status="succeeded",
            observation_result={"evidence_ids": ["evidence:a"]},
            evidence_ids=("evidence:a",),
        ),
        PublicTrajectoryAction(
            action_index=1,
            decision_kind="acquire_public_input",
            action_kind="call_tool",
            tool_id="query_structured_fact",
            arguments={"subject": "B"},
            observation_status="succeeded",
            observation_result={"evidence_ids": ["evidence:b"]},
            evidence_ids=("evidence:b",),
        ),
    ]
    if reverse_inputs:
        inputs.reverse()
        inputs = [
            item.model_copy(update={"action_index": index}) for index, item in enumerate(inputs)
        ]
    return (
        *inputs,
        PublicTrajectoryAction(
            action_index=2,
            decision_kind="execute_public_operation",
            action_kind="call_tool",
            tool_id="calculator",
            arguments={"operands": [{"operation_ref": runtime_ref}]},
            observation_status="succeeded",
            observation_result={
                "result": {
                    "operation_ref": runtime_ref,
                    "output": {"value": "1.0"},
                }
            },
            evidence_ids=("evidence:a", "evidence:b"),
        ),
        PublicTrajectoryAction(
            action_index=3,
            decision_kind="emit_final_answer",
            action_kind="emit_final",
        ),
    )


def _synthetic_projection(
    runtime_ref: str,
    *,
    reverse_inputs: bool = False,
) -> PublicTrajectoryProjection:
    return make_public_trajectory_projection(
        trajectory_id="synthetic-valid-trajectory",
        terminal_disposition="completed_model_endpoint",
        actions=_synthetic_actions(runtime_ref, reverse_inputs=reverse_inputs),
        final_result={"operation_ref": runtime_ref, "value": "1.0"},
        final_citations=("evidence:a", "evidence:b"),
    )


def _constructibility(
    *,
    mapper_contract: ValidOnlyStateMapperContract,
    static_path_catalog_id: str,
) -> MapperConstructibilityFixture:
    projections = (
        _synthetic_projection("runtime-operation:a"),
        _synthetic_projection("runtime-operation:b"),
        _synthetic_projection("runtime-operation:a", reverse_inputs=True),
    )
    aliases = (
        {"runtime-operation:a": "program-node:operation-1"},
        {"runtime-operation:b": "program-node:operation-1"},
        {"runtime-operation:a": "program-node:operation-1"},
    )
    assignments = []
    for trajectory, alias in zip(projections, aliases, strict=True):
        route = make_empirical_route_projection(
            sampling_mode="reachability_unconditional",
            public_condition_id=None,
            requested_path_id=None,
            requested_path_strategy=None,
            static_path_catalog_id=static_path_catalog_id,
            trajectory=trajectory,
        )
        assignments.append(
            map_independently_valid_public_trajectory_to_state(
                trajectory=trajectory,
                qualified_validity_report=_qualified_fixture_report(
                    mapper_contract=mapper_contract
                ),
                mapper_contract=mapper_contract,
                omega_task_context_id="synthetic-omega-context",
                route_projection=route,
                runtime_operation_aliases=alias,
            )
        )
    if (
        len({item.structural_state_id for item in assignments}) != 1
        or len({item.trajectory_content_hash for item in assignments}) != 3
    ):
        raise ValueError("v26.156 synthetic Mapper invariance changed")
    values: dict[str, Any] = {}
    provisional = MapperConstructibilityFixture.model_construct(
        fixture_id="pending",
        **values,
    )
    return MapperConstructibilityFixture(
        fixture_id=_identity(
            provisional,
            "fixture_id",
            "finance_v26_valid_only_mapper_constructibility_fixture:",
        ),
        **values,
    )


def _expect_failure(name: str, operation: Any) -> MutationResult:
    try:
        operation()
    except (TypeError, ValueError):
        return MutationResult(mutation_name=name)
    raise AssertionError(f"v26.156 destructive mutation survived: {name}")


def _destructive(
    *,
    mapper_contract: ValidOnlyStateMapperContract,
    manifest: ValidOnlyMappingCandidateManifest,
    static_path_catalog_id: str,
) -> MappingDestructiveAudit:
    first = manifest.candidates[0]
    trajectory = _synthetic_projection("runtime-operation:a")
    route = make_empirical_route_projection(
        sampling_mode="reachability_unconditional",
        public_condition_id=None,
        requested_path_id=None,
        requested_path_strategy=None,
        static_path_catalog_id=static_path_catalog_id,
        trajectory=trajectory,
    )

    mutations: list[MutationResult] = []
    for valid, name in (
        (False, "base_or_mechanism_invalid_report"),
        (None, "support_or_integrity_null_report"),
    ):
        mutations.append(
            _expect_failure(
                name,
                lambda valid=valid: map_independently_valid_public_trajectory_to_state(
                    trajectory=trajectory,
                    qualified_validity_report=_qualified_fixture_report(
                        mapper_contract=mapper_contract,
                        valid=valid,
                    ),
                    mapper_contract=mapper_contract,
                    omega_task_context_id="synthetic-omega-context",
                    route_projection=route,
                    runtime_operation_aliases={"runtime-operation:a": "program-node:operation-1"},
                ),
            )
        )

    mutation_fields: tuple[tuple[str, Any], ...] = (
        ("candidate_id", "stale-candidate"),
        ("job_id", "crossed-job"),
        ("task_package_id", "crossed-task"),
        ("trajectory_id", "crossed-trajectory"),
        ("trajectory_content_hash", "crossed-trajectory-hash"),
        ("qualified_validity_report_id", "crossed-validity-report"),
        ("omega_task_context_id", "crossed-omega"),
        ("route_condition_id", "crossed-route"),
        ("static_path_catalog_id", "crossed-path-catalog"),
        ("raw_observation_prefix_hash", "crossed-observation-prefix"),
        ("raw_execution_relative_path", "crossed/raw.json"),
        ("raw_execution_sha256", "0" * 64),
        ("runtime_operation_alias_binding_hash", "crossed-alias-binding"),
        ("public_condition_id", "crossed-condition"),
        ("structural_state_id", "host-inserted-state"),
        ("state_assignment_id", "host-inserted-assignment"),
        (
            "sampling_mode",
            (
                "reachability_unconditional"
                if first.sampling_mode == "reachability_conditioned"
                else "reachability_conditioned"
            ),
        ),
        ("requested_path_id", "crossed-path"),
    )
    for field, value in mutation_fields:
        payload = first.model_dump(mode="python")
        payload[field] = value
        mutations.append(
            _expect_failure(
                f"candidate_{field}_mutation",
                lambda payload=payload: ValidOnlyMappingCandidate.model_validate(payload),
            )
        )
    ordered = tuple(sorted(mutations, key=lambda item: item.mutation_name))
    if len(ordered) != 20:
        raise ValueError("v26.156 destructive mutation denominator changed")
    values = {"mutation_results": ordered}
    provisional = MappingDestructiveAudit.model_construct(audit_id="pending", **values)
    return MappingDestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_valid_only_mapping_destructive:",
        ),
        **values,
    )


def _preflight_audit(
    *,
    inputs: Inputs,
    mapper_contract: ValidOnlyStateMapperContract,
    protocol: EmpiricalStateMapperProtocol,
    omega: OmegaTaskContextCatalog,
    manifest: ValidOnlyMappingCandidateManifest,
    fixture: MapperConstructibilityFixture,
    destructive: MappingDestructiveAudit,
) -> ValidOnlyMappingPreflightAudit:
    candidate_count = manifest.qualified_candidate_count
    contexts = {item.context_id for item in omega.contexts}
    if any(item.omega_task_context_id not in contexts for item in manifest.candidates):
        raise ValueError("v26.156 Mapping Candidate crossed Omega contexts")
    if any(
        item.static_path_catalog_id != inputs.path_catalog.catalog_id
        for item in manifest.candidates
    ):
        raise ValueError("v26.156 Mapping Candidate crossed Path catalogs")
    values = {
        "mapper_contract_id": mapper_contract.contract_id,
        "mapper_protocol_id": protocol.protocol_id,
        "omega_task_context_catalog_id": omega.catalog_id,
        "candidate_manifest_id": manifest.manifest_id,
        "qualified_candidate_count": candidate_count,
        "independently_qualified_report_match_count": candidate_count,
        "exact_raw_descriptor_match_count": candidate_count,
        "exact_omega_binding_match_count": candidate_count,
        "exact_route_binding_match_count": candidate_count,
        "exact_required_input_binding_match_count": candidate_count,
        "synthetic_constructibility_fixture_id": fixture.fixture_id,
        "destructive_audit_id": destructive.audit_id,
    }
    provisional = ValidOnlyMappingPreflightAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return ValidOnlyMappingPreflightAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_valid_only_mapping_preflight:",
        ),
        **values,
    )


def _runner_contract(
    *,
    manifest: ValidOnlyMappingCandidateManifest,
    mapper_contract: ValidOnlyStateMapperContract,
    protocol: EmpiricalStateMapperProtocol,
    audit: ValidOnlyMappingPreflightAudit,
) -> ValidOnlyMappingRunnerContract:
    execution_id = canonical_hash(
        {
            "postrun_report_id": EXPECTED_POSTRUN_REPORT_ID,
            "candidate_manifest_id": manifest.manifest_id,
            "mapper_contract_id": mapper_contract.contract_id,
            "mapper_protocol_id": protocol.protocol_id,
            "exact_candidate_denominator": manifest.qualified_candidate_count,
        },
        prefix="finance_v26_valid_only_state_mapping_execution:",
    )
    report_id = canonical_hash(
        {
            "prospective_execution_id": execution_id,
            "candidate_manifest_id": manifest.manifest_id,
            "mapper_contract_id": mapper_contract.contract_id,
        },
        prefix="finance_v26_valid_only_state_mapping_execution_report:",
    )
    values = {
        "candidate_manifest_id": manifest.manifest_id,
        "mapper_contract_id": mapper_contract.contract_id,
        "mapper_protocol_id": protocol.protocol_id,
        "preflight_audit_id": audit.audit_id,
        "prospective_execution_id": execution_id,
        "prospective_report_id": report_id,
        "exact_candidate_denominator": manifest.qualified_candidate_count,
    }
    provisional = ValidOnlyMappingRunnerContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ValidOnlyMappingRunnerContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_valid_only_mapping_runner_contract:",
        ),
        **values,
    )


def _transition(
    runner: ValidOnlyMappingRunnerContract,
) -> ProspectiveTransitionContract:
    values = {
        "runner_contract_id": runner.contract_id,
        "exact_candidate_denominator": runner.exact_candidate_denominator,
    }
    provisional = ProspectiveTransitionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_valid_only_mapping_transition:",
        ),
        **values,
    )


def _detail(path: Path, root: Path) -> DetailFile:
    return DetailFile(
        relative_path=path.relative_to(root).as_posix(),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    postrun_dir: Path,
    output_dir: Path,
) -> ValidOnlyMappingPreflightReport:
    source = _predecessor_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
        postrun_dir=postrun_dir,
    )
    print(
        "[v26.156] predecessor rebuild "
        f"{source.predecessor_byte_match_count}/"
        f"{source.predecessor_output_file_count} exact",
        flush=True,
    )
    inputs = _load_inputs(
        package_root=package_root,
        postrun_dir=postrun_dir,
        execution_dir=execution_dir,
    )
    omega = _omega_catalog(inputs)
    mapper_contract = _make_mapper_contract(inputs, package_root=package_root)
    protocol = _make_protocol(
        mapper_contract=mapper_contract,
        omega=omega,
        inputs=inputs,
    )
    manifest = _candidate_manifest(
        inputs=inputs,
        omega=omega,
        mapper_contract=mapper_contract,
        protocol=protocol,
    )
    fixture = _constructibility(
        mapper_contract=mapper_contract,
        static_path_catalog_id=inputs.path_catalog.catalog_id,
    )
    destructive = _destructive(
        mapper_contract=mapper_contract,
        manifest=manifest,
        static_path_catalog_id=inputs.path_catalog.catalog_id,
    )
    audit = _preflight_audit(
        inputs=inputs,
        mapper_contract=mapper_contract,
        protocol=protocol,
        omega=omega,
        manifest=manifest,
        fixture=fixture,
        destructive=destructive,
    )
    runner = _runner_contract(
        manifest=manifest,
        mapper_contract=mapper_contract,
        protocol=protocol,
        audit=audit,
    )
    transition = _transition(runner)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("candidate_manifest.json", manifest),
        ("destructive_audit.json", destructive),
        ("mapper_constructibility_fixture.json", fixture),
        ("mapper_protocol.json", protocol),
        ("omega_task_context_catalog.json", omega),
        ("predecessor_replay_audit.json", source),
        ("preflight_audit.json", audit),
        ("prospective_transition_contract.json", transition),
        ("runner_contract.json", runner),
        ("valid_only_mapper_contract.json", mapper_contract),
    )
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values = {
        "source_replay_audit_id": source.audit_id,
        "omega_task_context_catalog_id": omega.catalog_id,
        "mapper_contract_id": mapper_contract.contract_id,
        "mapper_protocol_id": protocol.protocol_id,
        "candidate_manifest_id": manifest.manifest_id,
        "constructibility_fixture_id": fixture.fixture_id,
        "destructive_audit_id": destructive.audit_id,
        "preflight_audit_id": audit.audit_id,
        "runner_contract_id": runner.contract_id,
        "transition_contract_id": transition.contract_id,
        "qualified_candidate_count": manifest.qualified_candidate_count,
        "detail_files": details,
    }
    provisional = ValidOnlyMappingPreflightReport.model_construct(
        report_id="pending",
        **values,
    )
    report = ValidOnlyMappingPreflightReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_valid_only_mapping_preflight_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preflight valid-only empirical Reachability State Mapping."
    )
    parser.add_argument("--implementation-root", type=Path, default=Path.cwd())
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--execution-dir", type=Path)
    parser.add_argument("--postrun-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    package_root = (
        args.package_root
        if args.package_root is not None
        else _resolve_package_root(args.implementation_root)
    )
    execution_dir = (
        args.execution_dir
        if args.execution_dir is not None
        else package_root / execution.OUTPUT_DIR
    )
    postrun_dir = (
        args.postrun_dir if args.postrun_dir is not None else package_root / postrun.OUTPUT_DIR
    )
    output_dir = args.output_dir if args.output_dir is not None else package_root / OUTPUT_DIR
    report = build_preflight(
        package_root=package_root,
        implementation_root=args.implementation_root,
        execution_dir=execution_dir,
        postrun_dir=postrun_dir,
        output_dir=output_dir,
    )
    print(
        "[v26.156] valid-only Mapping preflight passed "
        f"candidates={report.qualified_candidate_count} "
        f"assignments={report.state_assignment_count} "
        f"provider_calls={report.provider_calls} "
        f"report={report.report_id}",
        flush=True,
    )


if __name__ == "__main__":
    main()
