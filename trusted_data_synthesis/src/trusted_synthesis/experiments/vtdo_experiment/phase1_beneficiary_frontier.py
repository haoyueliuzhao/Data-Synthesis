from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
    FinanceCapabilityBoundaryContract,
    RuntimeTaskBinding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    ConfidenceInterval,
    EmpiricalCapabilityInformationAudit,
    SignedConfidenceInterval,
    TechnicalGate,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_SENSITIVE_FAMILIES,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
)
from trusted_synthesis.hashing import canonical_hash

BENEFICIARY_IDENTITY_VERSION = "beneficiary_model_identity.v2"
BENEFICIARY_SCREENING_CONTRACT_VERSION = "beneficiary_screening_contract.v4"
BENEFICIARY_OUTCOME_VERSION = "beneficiary_frontier_outcome.v4"
BENEFICIARY_SCREENING_ARTIFACT_VERSION = "beneficiary_frontier_screening.v4"
BENEFICIARY_REPLICAS = 5


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BeneficiaryModelIdentity(FrozenModel):
    requested_model_family: Literal["Qwen2.5-7B"] = "Qwen2.5-7B"
    training_report_path: str = Field(min_length=1)
    training_report_sha256: str = Field(min_length=64, max_length=64)
    training_report_hash: str = Field(min_length=1)
    base_model_manifest_path: str = Field(min_length=1)
    base_model_manifest_sha256: str = Field(min_length=64, max_length=64)
    base_model_manifest_hash: str = Field(min_length=1)
    base_model_dir: str = Field(min_length=1)
    adapter_dir: str = Field(min_length=1)
    adapter_tensor_sha256: str = Field(min_length=64, max_length=64)
    adapter_file_manifest_hash: str = Field(min_length=1)
    checkpoint_hash: str = Field(min_length=1)
    model_state_id: str = Field(min_length=1)
    identity_hash: str = Field(min_length=1)
    schema_version: str = BENEFICIARY_IDENTITY_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> BeneficiaryModelIdentity:
        if self.schema_version != BENEFICIARY_IDENTITY_VERSION:
            raise ValueError("beneficiary model identity version is unsupported")
        if self.identity_hash != beneficiary_model_identity_hash(self):
            raise ValueError("beneficiary model identity is invalid")
        return self


class BeneficiaryScreeningThresholds(FrozenModel):
    minimum_completion_rate: float = Field(default=0.98, ge=0, le=1)
    minimum_boundary_task_fraction: float = Field(default=0.25, ge=0, le=1)
    boundary_probability_lower: float = Field(default=0.10, ge=0, le=1)
    boundary_probability_upper: float = Field(default=0.90, ge=0, le=1)
    minimum_mean_success_rate: float = Field(default=0.05, ge=0, le=1)
    maximum_mean_success_rate: float = Field(default=0.90, ge=0, le=1)
    capability_ordering_tolerance: float = Field(default=0.05, ge=0, le=1)
    minimum_ordered_family_fraction: float = Field(default=0.50, ge=0, le=1)
    minimum_selected_task_count: int = Field(default=7, ge=1)
    bootstrap_replicates: int = Field(default=400, ge=100)

    @model_validator(mode="after")
    def validate_thresholds(self) -> BeneficiaryScreeningThresholds:
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("beneficiary boundary interval is empty")
        if self.minimum_mean_success_rate >= self.maximum_mean_success_rate:
            raise ValueError("beneficiary success interval is empty")
        return self


class BeneficiaryScreeningContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    boundary_contract_id: str = Field(min_length=1)
    empirical_audit_id: str = Field(min_length=1)
    beneficiary: BeneficiaryModelIdentity
    bindings: tuple[RuntimeTaskBinding, ...] = Field(min_length=84, max_length=84)
    replicas: int = Field(default=BENEFICIARY_REPLICAS, ge=5, le=5)
    requested_rollout_count: int = Field(ge=1)
    thresholds: BeneficiaryScreeningThresholds
    next_permitted_stage: Literal["local_beneficiary_frontier_screening"] = (
        "local_beneficiary_frontier_screening"
    )
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = BENEFICIARY_SCREENING_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> BeneficiaryScreeningContract:
        if self.schema_version != BENEFICIARY_SCREENING_CONTRACT_VERSION:
            raise ValueError("beneficiary screening contract version is unsupported")
        by_task: dict[str, set[CapabilityRuntimeArm]] = defaultdict(set)
        for binding in self.bindings:
            by_task[binding.task_artifact_id].add(binding.runtime_arm)
        if len(by_task) != 28 or any(
            runtimes != set(CapabilityRuntimeArm) for runtimes in by_task.values()
        ):
            raise ValueError("beneficiary contract must bind 28 tasks to all runtimes")
        expected = len(self.bindings) * self.replicas
        if self.requested_rollout_count != expected:
            raise ValueError("beneficiary rollout count is inconsistent")
        if self.contract_id != beneficiary_screening_contract_id(self):
            raise ValueError("beneficiary screening contract identity is invalid")
        return self


class BeneficiaryRolloutOutcome(FrozenModel):
    outcome_id: str = Field(min_length=1)
    screening_contract_id: str = Field(min_length=1)
    binding_id: str = Field(min_length=1)
    task_artifact_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    runtime_arm: CapabilityRuntimeArm
    replicate: int = Field(ge=0)
    completed: bool
    deterministic_valid: bool
    semantic_answer_correct: bool
    valid_success: bool
    negative_log_likelihood: float | None = Field(default=None, ge=0)
    tool_selection_correct: bool
    verification_success: bool
    query_reformulated: bool
    recovery_opportunity: bool
    recovery_success: bool
    stop_quality_success: bool
    state_id: str | None = None
    tool_sequence_hash: str | None = None
    schema_version: str = BENEFICIARY_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_outcome(self) -> BeneficiaryRolloutOutcome:
        if self.schema_version != BENEFICIARY_OUTCOME_VERSION:
            raise ValueError("beneficiary outcome version is unsupported")
        if self.family not in CAPABILITY_SENSITIVE_FAMILIES:
            raise ValueError("beneficiary outcome uses an unknown family")
        if self.valid_success != (self.deterministic_valid and self.semantic_answer_correct):
            raise ValueError("beneficiary valid-success result is inconsistent")
        if self.completed != (self.negative_log_likelihood is not None):
            raise ValueError("completed beneficiary outcome must include NLL")
        if self.recovery_success and not self.recovery_opportunity:
            raise ValueError("beneficiary recovery success lacks an opportunity")
        if not self.completed and any(
            (
                self.deterministic_valid,
                self.semantic_answer_correct,
                self.valid_success,
                self.tool_selection_correct,
                self.verification_success,
                self.query_reformulated,
                self.recovery_opportunity,
                self.recovery_success,
                self.stop_quality_success,
                self.state_id is not None,
                self.tool_sequence_hash is not None,
            )
        ):
            raise ValueError("failed beneficiary outcome contains successful results")
        if self.outcome_id != beneficiary_rollout_outcome_id(self):
            raise ValueError("beneficiary outcome identity is invalid")
        return self


class BeneficiaryRuntimeSummary(FrozenModel):
    runtime_arm: CapabilityRuntimeArm
    task_count: int = Field(ge=1)
    rollout_count: int = Field(ge=1)
    completion_rate: float = Field(ge=0, le=1)
    mean_success_rate: float = Field(ge=0, le=1)
    boundary_task_fraction: float = Field(ge=0, le=1)
    mean_negative_log_likelihood: float = Field(ge=0)
    tool_selection_success_rate: float = Field(ge=0, le=1)
    verification_success_rate: float = Field(ge=0, le=1)
    query_reformulation_rate: float = Field(ge=0, le=1)
    recovery_opportunity_count: int = Field(ge=0)
    recovery_success_rate: float = Field(ge=0, le=1)
    stop_quality_success_rate: float = Field(ge=0, le=1)
    accepted_state_count: int = Field(ge=0)
    mean_tool_sequence_diversity: float = Field(ge=0, le=1)
    family_success_rates: dict[str, float]
    task_success_probabilities: dict[str, float]
    task_family_by_id: dict[str, str]

    @model_validator(mode="after")
    def validate_summary(self) -> BeneficiaryRuntimeSummary:
        if set(self.family_success_rates) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("beneficiary summary lacks a capability family")
        if len(self.task_success_probabilities) != self.task_count:
            raise ValueError("beneficiary summary task probabilities are incomplete")
        if set(self.task_family_by_id) != set(self.task_success_probabilities):
            raise ValueError("beneficiary summary task-family lineage is incomplete")
        if not set(self.task_family_by_id.values()) <= set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("beneficiary summary uses an unknown task family")
        return self


class BeneficiaryFamilyOrdering(FrozenModel):
    family: str = Field(min_length=1)
    ordering_tolerance: float = Field(ge=0, le=1)
    beneficiary_success_interval: ConfidenceInterval
    flash_success_rate: float = Field(ge=0, le=1)
    pro_success_rate: float = Field(ge=0, le=1)
    pro_minus_flash_interval: SignedConfidenceInterval
    beneficiary_not_above_flash: bool
    flash_not_above_pro: bool
    ordered: bool

    @model_validator(mode="after")
    def validate_ordering(self) -> BeneficiaryFamilyOrdering:
        if self.family not in CAPABILITY_SENSITIVE_FAMILIES:
            raise ValueError("beneficiary ordering uses an unknown family")
        beneficiary_not_above = (
            self.beneficiary_success_interval.upper - self.flash_success_rate
            <= self.ordering_tolerance
        )
        flash_not_above = -self.pro_minus_flash_interval.lower <= self.ordering_tolerance
        if self.beneficiary_not_above_flash != beneficiary_not_above:
            raise ValueError("beneficiary-to-Flash ordering is inconsistent")
        if self.flash_not_above_pro != flash_not_above:
            raise ValueError("Flash-to-Pro ordering is inconsistent")
        expected_gap = self.pro_success_rate - self.flash_success_rate
        if not math.isclose(
            self.pro_minus_flash_interval.point,
            expected_gap,
            abs_tol=1e-9,
        ):
            raise ValueError("Pro-Flash interval is detached from family success rates")
        if self.ordered != (beneficiary_not_above and flash_not_above):
            raise ValueError("beneficiary family ordering decision is inconsistent")
        return self


class BeneficiaryFrontierScreeningArtifact(FrozenModel):
    artifact_id: str = Field(min_length=1)
    screening_contract_id: str = Field(min_length=1)
    boundary_contract_id: str = Field(min_length=1)
    empirical_audit_id: str = Field(min_length=1)
    beneficiary_identity_hash: str = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    outcome_set_hash: str = Field(min_length=1)
    runtime_summaries: tuple[BeneficiaryRuntimeSummary, ...] = Field(min_length=3, max_length=3)
    family_ordering: tuple[BeneficiaryFamilyOrdering, ...] = Field(min_length=7, max_length=7)
    ordered_family_count: int = Field(ge=0)
    ordered_family_fraction: float = Field(ge=0, le=1)
    selected_tasks_by_family: dict[str, tuple[str, ...]]
    selected_task_artifact_ids: tuple[str, ...]
    gates: tuple[TechnicalGate, ...] = Field(min_length=1)
    beneficiary_frontier_ready: bool
    next_permitted_stage: Literal[
        "capability_sensitive_state_discovery",
        "task_or_beneficiary_redesign_only",
    ]
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = BENEFICIARY_SCREENING_ARTIFACT_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> BeneficiaryFrontierScreeningArtifact:
        if self.schema_version != BENEFICIARY_SCREENING_ARTIFACT_VERSION:
            raise ValueError("beneficiary screening artifact version is unsupported")
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("beneficiary artifact has an incomplete rollout denominator")
        if (
            sum(item.rollout_count for item in self.runtime_summaries)
            != self.recorded_rollout_count
        ):
            raise ValueError("beneficiary runtime summaries do not cover recorded rollouts")
        if {item.runtime_arm for item in self.runtime_summaries} != set(CapabilityRuntimeArm):
            raise ValueError("beneficiary artifact lacks a runtime summary")
        if {item.family for item in self.family_ordering} != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("beneficiary capability ordering is incomplete")
        expected_count = sum(item.ordered for item in self.family_ordering)
        if self.ordered_family_count != expected_count:
            raise ValueError("beneficiary ordered-family count is inconsistent")
        expected_fraction = expected_count / len(CAPABILITY_SENSITIVE_FAMILIES)
        if not math.isclose(self.ordered_family_fraction, expected_fraction, abs_tol=1e-12):
            raise ValueError("beneficiary ordered-family fraction is inconsistent")
        if set(self.selected_tasks_by_family) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("beneficiary selected-task mapping is incomplete")
        ordering = {item.family: item.ordered for item in self.family_ordering}
        if any(
            values and not ordering[family]
            for family, values in self.selected_tasks_by_family.items()
        ):
            raise ValueError("beneficiary selected a task from an unordered family")
        autonomous = next(
            item
            for item in self.runtime_summaries
            if item.runtime_arm == CapabilityRuntimeArm.AUTONOMOUS_AGENT
        )
        if any(
            autonomous.task_family_by_id.get(task_id) != family
            for family, task_ids in self.selected_tasks_by_family.items()
            for task_id in task_ids
        ):
            raise ValueError("beneficiary selected-task family lineage is invalid")
        selected = tuple(
            sorted(
                task_id for values in self.selected_tasks_by_family.values() for task_id in values
            )
        )
        if len(selected) != len(set(selected)) or self.selected_task_artifact_ids != selected:
            raise ValueError("beneficiary selected-task identity is inconsistent")
        ready = all(item.passed for item in self.gates)
        if self.beneficiary_frontier_ready != ready:
            raise ValueError("beneficiary frontier decision differs from its gates")
        expected_next = (
            "capability_sensitive_state_discovery" if ready else "task_or_beneficiary_redesign_only"
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("beneficiary frontier transition is not fail-closed")
        if self.artifact_id != beneficiary_screening_artifact_id(self):
            raise ValueError("beneficiary screening artifact identity is invalid")
        return self


def freeze_beneficiary_identity(
    *,
    training_report_path: Path,
    base_model_manifest_path: Path,
) -> BeneficiaryModelIdentity:
    training_report_path = training_report_path.resolve()
    base_model_manifest_path = base_model_manifest_path.resolve()
    report = json.loads(training_report_path.read_text(encoding="utf-8"))
    manifest = json.loads(base_model_manifest_path.read_text(encoding="utf-8"))
    report_payload = dict(report)
    observed_report_hash = report_payload.pop("report_hash", None)
    expected_report_hash = canonical_hash(report_payload, prefix="finance_phase1_beneficiary:")
    if observed_report_hash != expected_report_hash:
        raise ValueError("beneficiary training report hash is invalid")
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, dict) or not manifest_files:
        raise ValueError("beneficiary base-model manifest has no files")
    expected_manifest_hash = canonical_hash(manifest_files, prefix="base_model_content_manifest:")
    if manifest.get("manifest_hash") != expected_manifest_hash:
        raise ValueError("beneficiary base-model manifest hash is invalid")
    if report["base_model_manifest_hash"] != manifest["manifest_hash"]:
        raise ValueError("beneficiary report and base-model manifest disagree")
    adapter_dir = Path(str(report["adapter_dir"])).resolve()
    base_model_dir = Path(str(manifest["model_dir"])).resolve()
    if not base_model_dir.is_dir() or not adapter_dir.is_dir():
        raise ValueError("beneficiary model or Adapter directory is missing")
    for relative, metadata in manifest_files.items():
        path = base_model_dir / relative
        if not path.is_file() or _sha256(path) != metadata["sha256"]:
            raise ValueError(f"beneficiary base-model file changed: {relative}")
        if path.stat().st_size != int(metadata["size"]):
            raise ValueError(f"beneficiary base-model size changed: {relative}")
    adapter_files = dict(report["adapter_files"])
    for relative, metadata in adapter_files.items():
        path = adapter_dir / relative
        if not path.is_file() or _sha256(path) != metadata["sha256"]:
            raise ValueError(f"beneficiary Adapter file changed: {relative}")
        if path.stat().st_size != int(metadata["size"]):
            raise ValueError(f"beneficiary Adapter size changed: {relative}")
    expected_checkpoint_hash = canonical_hash(
        {
            "base_model_manifest_hash": expected_manifest_hash,
            "adapter_tensor_sha256": report["adapter_tensor_sha256"],
            "adapter_files": adapter_files,
        },
        prefix="qwen_beneficiary_checkpoint:",
    )
    if report.get("checkpoint_hash") != expected_checkpoint_hash:
        raise ValueError("beneficiary checkpoint hash is invalid")
    expected_model_state_id = canonical_hash(
        {
            "checkpoint_hash": expected_checkpoint_hash,
            "role": "vtdo_beneficiary",
            "task_family": "finance_phase1",
        },
        prefix="beneficiary_model_state:",
    )
    if report.get("model_state_id") != expected_model_state_id:
        raise ValueError("beneficiary model-state identity is invalid")
    values = {
        "training_report_path": str(training_report_path),
        "training_report_sha256": _sha256(training_report_path),
        "training_report_hash": expected_report_hash,
        "base_model_manifest_path": str(base_model_manifest_path),
        "base_model_manifest_sha256": _sha256(base_model_manifest_path),
        "base_model_manifest_hash": expected_manifest_hash,
        "base_model_dir": str(base_model_dir),
        "adapter_dir": str(adapter_dir),
        "adapter_tensor_sha256": str(report["adapter_tensor_sha256"]),
        "adapter_file_manifest_hash": canonical_hash(
            adapter_files, prefix="beneficiary_adapter_files:"
        ),
        "checkpoint_hash": expected_checkpoint_hash,
        "model_state_id": expected_model_state_id,
    }
    provisional = BeneficiaryModelIdentity.model_construct(identity_hash="pending", **values)
    return BeneficiaryModelIdentity(
        identity_hash=beneficiary_model_identity_hash(provisional), **values
    )


def prepare_beneficiary_screening_contract(
    *,
    boundary_contract: FinanceCapabilityBoundaryContract,
    empirical_audit: EmpiricalCapabilityInformationAudit,
    beneficiary: BeneficiaryModelIdentity,
) -> BeneficiaryScreeningContract:
    if empirical_audit.contract_id != boundary_contract.contract_id:
        raise ValueError("empirical audit belongs to another boundary contract")
    if not empirical_audit.empirical_capability_ready:
        raise ValueError("beneficiary screening requires empirical capability authorization")
    replayed_beneficiary = freeze_beneficiary_identity(
        training_report_path=Path(beneficiary.training_report_path),
        base_model_manifest_path=Path(beneficiary.base_model_manifest_path),
    )
    if replayed_beneficiary != beneficiary:
        raise ValueError("beneficiary identity changed before screening contract creation")
    values = {
        "boundary_contract_id": boundary_contract.contract_id,
        "empirical_audit_id": empirical_audit.audit_id,
        "beneficiary": beneficiary,
        "bindings": boundary_contract.calibration_bindings,
        "replicas": BENEFICIARY_REPLICAS,
        "requested_rollout_count": (
            len(boundary_contract.calibration_bindings) * BENEFICIARY_REPLICAS
        ),
        "thresholds": BeneficiaryScreeningThresholds(),
        "next_permitted_stage": "local_beneficiary_frontier_screening",
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = BeneficiaryScreeningContract.model_construct(contract_id="pending", **values)
    return BeneficiaryScreeningContract(
        contract_id=beneficiary_screening_contract_id(provisional), **values
    )


def make_beneficiary_screening_artifact(
    *,
    contract: BeneficiaryScreeningContract,
    empirical_audit: EmpiricalCapabilityInformationAudit,
    outcomes: tuple[BeneficiaryRolloutOutcome, ...],
) -> BeneficiaryFrontierScreeningArtifact:
    if contract.empirical_audit_id != empirical_audit.audit_id:
        raise ValueError("beneficiary results use another empirical audit")
    _validate_outcomes(contract, outcomes)
    summaries = tuple(
        _runtime_summary(contract, runtime, outcomes) for runtime in CapabilityRuntimeArm
    )
    autonomous = next(
        item for item in summaries if item.runtime_arm == CapabilityRuntimeArm.AUTONOMOUS_AGENT
    )
    empirical = {(item.model_arm, item.runtime_arm): item for item in empirical_audit.cells}
    pro = empirical[(ExplorerArm.PRO, CapabilityRuntimeArm.AUTONOMOUS_AGENT)]
    flash = empirical[(ExplorerArm.FLASH, CapabilityRuntimeArm.AUTONOMOUS_AGENT)]
    tolerance = contract.thresholds.capability_ordering_tolerance
    family_intervals = {
        family: _beneficiary_family_interval(contract, family, outcomes)
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    family_ordering = tuple(
        _make_family_ordering(
            family=family,
            tolerance=tolerance,
            beneficiary_interval=family_intervals[family],
            flash_success_rate=flash.family_success_rates[family],
            pro_success_rate=pro.family_success_rates[family],
            pro_minus_flash_interval=(empirical_audit.paired_family_model_gap_intervals[family]),
        )
        for family in CAPABILITY_SENSITIVE_FAMILIES
    )
    ordering = {item.family: item.ordered for item in family_ordering}
    ordered_count = sum(item.ordered for item in family_ordering)
    ordered_fraction = ordered_count / len(CAPABILITY_SENSITIVE_FAMILIES)
    selected_by_family = {
        family: tuple(
            sorted(
                task_id
                for task_id, probability in autonomous.task_success_probabilities.items()
                if ordering[family]
                and _task_family(outcomes, task_id) == family
                and contract.thresholds.boundary_probability_lower
                <= probability
                <= contract.thresholds.boundary_probability_upper
            )
        )
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    selected_task_ids = tuple(
        sorted(task_id for values in selected_by_family.values() for task_id in values)
    )
    completion = min(item.completion_rate for item in summaries)
    thresholds = contract.thresholds
    gates = (
        _gate(
            "beneficiary_completion",
            completion >= thresholds.minimum_completion_rate,
            completion,
            f">={thresholds.minimum_completion_rate}",
        ),
        _gate(
            "beneficiary_not_floor_or_saturated",
            thresholds.minimum_mean_success_rate
            <= autonomous.mean_success_rate
            <= thresholds.maximum_mean_success_rate,
            autonomous.mean_success_rate,
            (f"[{thresholds.minimum_mean_success_rate},{thresholds.maximum_mean_success_rate}]"),
        ),
        _gate(
            "beneficiary_boundary_mass",
            autonomous.boundary_task_fraction >= thresholds.minimum_boundary_task_fraction,
            autonomous.boundary_task_fraction,
            f">={thresholds.minimum_boundary_task_fraction}",
        ),
        _gate(
            "beneficiary_flash_pro_ordering",
            ordered_fraction >= thresholds.minimum_ordered_family_fraction,
            ordered_fraction,
            f">={thresholds.minimum_ordered_family_fraction}",
        ),
        _gate(
            "beneficiary_selected_task_support",
            len(selected_task_ids) >= thresholds.minimum_selected_task_count,
            float(len(selected_task_ids)),
            f">={thresholds.minimum_selected_task_count}",
        ),
    )
    ready = all(item.passed for item in gates)
    values = {
        "screening_contract_id": contract.contract_id,
        "boundary_contract_id": contract.boundary_contract_id,
        "empirical_audit_id": empirical_audit.audit_id,
        "beneficiary_identity_hash": contract.beneficiary.identity_hash,
        "requested_rollout_count": contract.requested_rollout_count,
        "recorded_rollout_count": len(outcomes),
        "outcome_set_hash": beneficiary_outcome_set_hash(outcomes),
        "runtime_summaries": summaries,
        "family_ordering": family_ordering,
        "ordered_family_count": ordered_count,
        "ordered_family_fraction": ordered_fraction,
        "selected_tasks_by_family": selected_by_family,
        "selected_task_artifact_ids": selected_task_ids,
        "gates": gates,
        "beneficiary_frontier_ready": ready,
        "next_permitted_stage": (
            "capability_sensitive_state_discovery" if ready else "task_or_beneficiary_redesign_only"
        ),
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = BeneficiaryFrontierScreeningArtifact.model_construct(
        artifact_id="pending", **values
    )
    return BeneficiaryFrontierScreeningArtifact(
        artifact_id=beneficiary_screening_artifact_id(provisional), **values
    )


def _validate_outcomes(
    contract: BeneficiaryScreeningContract,
    outcomes: tuple[BeneficiaryRolloutOutcome, ...],
) -> None:
    bindings = {item.binding_id: item for item in contract.bindings}
    expected = {
        (binding.binding_id, replicate)
        for binding in contract.bindings
        for replicate in range(contract.replicas)
    }
    observed = {(item.binding_id, item.replicate) for item in outcomes}
    if len(observed) != len(outcomes) or observed != expected:
        raise ValueError("beneficiary outcomes do not exactly cover frozen jobs")
    for outcome in outcomes:
        binding = bindings[outcome.binding_id]
        if outcome.screening_contract_id != contract.contract_id:
            raise ValueError("beneficiary outcome belongs to another contract")
        if (
            outcome.task_artifact_id != binding.task_artifact_id
            or outcome.family != binding.family
            or outcome.runtime_arm != binding.runtime_arm
        ):
            raise ValueError("beneficiary outcome differs from its frozen binding")


def _runtime_summary(
    contract: BeneficiaryScreeningContract,
    runtime: CapabilityRuntimeArm,
    outcomes: tuple[BeneficiaryRolloutOutcome, ...],
) -> BeneficiaryRuntimeSummary:
    selected = tuple(item for item in outcomes if item.runtime_arm == runtime)
    by_task: dict[str, list[BeneficiaryRolloutOutcome]] = defaultdict(list)
    for item in selected:
        by_task[item.task_artifact_id].append(item)
    probabilities = {
        task_id: sum(item.valid_success for item in values) / len(values)
        for task_id, values in by_task.items()
    }
    thresholds = contract.thresholds
    completed = tuple(item for item in selected if item.completed)
    nll_values = tuple(
        item.negative_log_likelihood
        for item in completed
        if item.negative_log_likelihood is not None
    )
    family_success = {
        family: sum(
            probability
            for task_id, probability in probabilities.items()
            if by_task[task_id][0].family == family
        )
        / sum(by_task[task_id][0].family == family for task_id in by_task)
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    recovery_opportunities = sum(item.recovery_opportunity for item in selected)
    tool_sequence_diversities = []
    for values in by_task.values():
        sequences = {
            item.tool_sequence_hash for item in values if item.tool_sequence_hash is not None
        }
        observed = sum(item.tool_sequence_hash is not None for item in values)
        tool_sequence_diversities.append(len(sequences) / observed if observed else 0.0)
    return BeneficiaryRuntimeSummary(
        runtime_arm=runtime,
        task_count=len(by_task),
        rollout_count=len(selected),
        completion_rate=len(completed) / len(selected),
        mean_success_rate=sum(probabilities.values()) / len(probabilities),
        boundary_task_fraction=sum(
            thresholds.boundary_probability_lower <= value <= thresholds.boundary_probability_upper
            for value in probabilities.values()
        )
        / len(probabilities),
        mean_negative_log_likelihood=sum(nll_values) / len(nll_values) if nll_values else 0.0,
        tool_selection_success_rate=sum(item.tool_selection_correct for item in selected)
        / len(selected),
        verification_success_rate=sum(item.verification_success for item in selected)
        / len(selected),
        query_reformulation_rate=sum(item.query_reformulated for item in selected) / len(selected),
        recovery_opportunity_count=recovery_opportunities,
        recovery_success_rate=(
            sum(item.recovery_success for item in selected) / recovery_opportunities
            if recovery_opportunities
            else 0.0
        ),
        stop_quality_success_rate=sum(item.stop_quality_success for item in selected)
        / len(selected),
        accepted_state_count=len({item.state_id for item in selected if item.state_id}),
        mean_tool_sequence_diversity=(
            sum(tool_sequence_diversities) / len(tool_sequence_diversities)
        ),
        family_success_rates=family_success,
        task_success_probabilities=probabilities,
        task_family_by_id={task_id: by_task[task_id][0].family for task_id in sorted(by_task)},
    )


def _make_family_ordering(
    *,
    family: str,
    tolerance: float,
    beneficiary_interval: ConfidenceInterval,
    flash_success_rate: float,
    pro_success_rate: float,
    pro_minus_flash_interval: SignedConfidenceInterval,
) -> BeneficiaryFamilyOrdering:
    beneficiary_not_above = beneficiary_interval.upper - flash_success_rate <= tolerance
    flash_not_above = -pro_minus_flash_interval.lower <= tolerance
    return BeneficiaryFamilyOrdering(
        family=family,
        ordering_tolerance=tolerance,
        beneficiary_success_interval=beneficiary_interval,
        flash_success_rate=flash_success_rate,
        pro_success_rate=pro_success_rate,
        pro_minus_flash_interval=pro_minus_flash_interval,
        beneficiary_not_above_flash=beneficiary_not_above,
        flash_not_above_pro=flash_not_above,
        ordered=beneficiary_not_above and flash_not_above,
    )


def _beneficiary_family_interval(
    contract: BeneficiaryScreeningContract,
    family: str,
    outcomes: tuple[BeneficiaryRolloutOutcome, ...],
) -> ConfidenceInterval:
    by_task: dict[str, tuple[int, ...]] = {}
    task_ids = sorted(
        {
            item.task_artifact_id
            for item in outcomes
            if item.runtime_arm == CapabilityRuntimeArm.AUTONOMOUS_AGENT and item.family == family
        }
    )
    for task_id in task_ids:
        by_task[task_id] = tuple(
            int(item.valid_success)
            for item in outcomes
            if item.runtime_arm == CapabilityRuntimeArm.AUTONOMOUS_AGENT
            and item.task_artifact_id == task_id
        )
    point = sum(sum(values) / len(values) for values in by_task.values()) / len(by_task)
    rng = random.Random(_stable_seed(contract.contract_id, family))
    samples = []
    task_values = tuple(by_task.values())
    for _ in range(contract.thresholds.bootstrap_replicates):
        selected = tuple(rng.choice(task_values) for _ in range(len(task_values)))
        means = []
        for values in selected:
            realization_sample = tuple(rng.choice(values) for _ in range(len(values)))
            means.append(sum(realization_sample) / len(realization_sample))
        samples.append(sum(means) / len(means))
    return ConfidenceInterval(
        lower=min(_quantile(samples, 0.025), point),
        point=point,
        upper=max(_quantile(samples, 0.975), point),
    )


def _task_family(outcomes: tuple[BeneficiaryRolloutOutcome, ...], task_artifact_id: str) -> str:
    return next(item.family for item in outcomes if item.task_artifact_id == task_artifact_id)


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _stable_seed(*values: str) -> int:
    digest = canonical_hash(values, prefix="beneficiary_frontier_bootstrap_seed:")
    return int(digest.rsplit(":", 1)[-1][:16], 16)


def _gate(
    gate_id: str,
    passed: bool,
    observed: float,
    requirement: str,
) -> TechnicalGate:
    return TechnicalGate(
        gate_id=gate_id,
        passed=passed,
        observed={gate_id: observed},
        requirement=requirement,
    )


def beneficiary_model_identity_hash(value: BeneficiaryModelIdentity) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"identity_hash"}),
        prefix="beneficiary_model_identity:",
    )


def beneficiary_screening_contract_id(value: BeneficiaryScreeningContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="beneficiary_screening_contract:",
    )


def beneficiary_outcome_set_hash(
    outcomes: tuple[BeneficiaryRolloutOutcome, ...],
) -> str:
    return canonical_hash(
        tuple(sorted(item.outcome_id for item in outcomes)),
        prefix="beneficiary_frontier_outcome_set:",
    )


def beneficiary_rollout_outcome_id(value: BeneficiaryRolloutOutcome) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"outcome_id"}),
        prefix="beneficiary_frontier_outcome:",
    )


def beneficiary_screening_artifact_id(
    value: BeneficiaryFrontierScreeningArtifact,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="beneficiary_frontier_screening:",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
