from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FINANCE_CAPABILITY_MECHANISM_ORACLE_KEY,
    FinanceCapabilityMechanismScenario,
    FinanceCompletionRole,
    make_candidate_verification_scenario,
    make_state_dependent_stopping_scenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
    RuntimeTaskBinding,
    _make_runtime_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    CapabilityRolloutOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_development import (
    _answer_contract_passes,
    _candidate_iterator,
    _CapabilityTaskBuilder,
    _CoreSelection,
    _load_evidence_pool,
    _matched_contract_passes,
    _matched_intervention_passes,
    _materialize_group,
    _select_mechanism_distractors,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_flash_development import (  # noqa: E501
    MechanismBehaviorObservation,
    MechanismSelectionDecision,
    _make_terminals,
    _rate,
    _selection_decisions,
    make_mechanism_behavior_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_ir import (
    CORE_FAMILY_BY_MECHANISM,
    MechanismDevelopmentGroup,
    MechanismTaskVariant,
    MechanismTier,
    mechanism_group_hash,
    mechanism_group_id,
    mechanism_task_variant_hash,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
    capability_sensitive_task_artifact_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_support_confirmation import (
    FinanceCapabilitySupportConfirmationContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    _execute_stage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    RuntimeResolutionStage,
    RuntimeTerminalOutcome,
    _load_records,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
    ExplorerModelContract,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

MECHANISM_REPAIR_VERSION = "finance_capability_mechanism_repair.v4"
MECHANISM_REPAIR_POPULATION_VERSION = "finance_capability_mechanism_repair_population.v4"
MECHANISM_REPAIR_FREEZE_VERSION = "finance_capability_mechanism_repair_freeze.v4"
MECHANISM_REPAIR_CONTRACT_VERSION = "finance_capability_mechanism_repair_contract.v4"
MECHANISM_REPAIR_REPORT_VERSION = "finance_capability_mechanism_repair_report.v4"

VERIFICATION_MECHANISM_ID = "finance.candidate_verification_and_repair"
STOPPING_MECHANISM_ID = "finance.state_dependent_control_and_stopping"
REPAIRED_MECHANISM_IDS: tuple[str, ...] = (
    VERIFICATION_MECHANISM_ID,
    STOPPING_MECHANISM_ID,
)
PRIOR_CONFIRMED_MECHANISM_IDS: tuple[str, ...] = (
    "finance.typed_tool_plan_and_argument_recovery",
    "finance.cross_family_failure_recovery",
)
INFORMATION_GEOMETRY_MECHANISM_IDS: tuple[str, ...] = (
    *PRIOR_CONFIRMED_MECHANISM_IDS,
    *REPAIRED_MECHANISM_IDS,
)
DEVELOPMENT_TIER_SCHEDULE: tuple[MechanismTier, ...] = (
    "bridge",
    "bridge",
    "bridge",
    "bridge",
    "frontier",
    "frontier",
    "frontier",
    "frontier",
)
CONFIRMATION_TIER_SCHEDULE: tuple[MechanismTier, ...] = (
    "bridge",
    "bridge",
    "frontier",
    "frontier",
    "frontier",
)
DEVELOPMENT_REPLICAS = 3
CONFIRMATION_REPLICAS = 5

RepairStage = Literal["development", "confirmation"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MechanismRepairStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    stage: RepairStage
    mechanism_ids: tuple[str, ...]
    group_count: int = Field(ge=1)
    expected_group_count: int = Field(ge=1)
    operation_replay_pass_rate: float = Field(ge=0, le=1)
    matched_contract_pass_rate: float = Field(ge=0, le=1)
    matched_intervention_pass_rate: float = Field(ge=0, le=1)
    answer_contract_pass_rate: float = Field(ge=0, le=1)
    runtime_scenario_coverage_rate: float = Field(ge=0, le=1)
    public_oracle_isolation_rate: float = Field(ge=0, le=1)
    verification_candidate_corruption_rate: float = Field(ge=0, le=1)
    verification_semantic_error_rate: float = Field(ge=0, le=1)
    stopping_role_observability_rate: float = Field(ge=0, le=1)
    stopping_asymmetric_cost_rate: float = Field(ge=0, le=1)
    stopping_transition_observability_rate: float = Field(ge=0, le=1)
    within_population_evidence_disjoint: bool
    prior_task_disjoint: bool
    prior_group_disjoint: bool
    prior_evidence_disjoint: bool
    prior_evidence_version_disjoint: bool
    prior_semantic_disjoint: bool
    benchmark_content_isolation_passed: bool
    rejection_reasons: tuple[str, ...]
    ready: bool
    next_permitted_stage: Literal[
        "flash_repaired_mechanism_development",
        "flash_repaired_mechanism_confirmation",
        "mechanism_task_repair_only",
    ]
    schema_version: str = MECHANISM_REPAIR_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> MechanismRepairStaticAudit:
        if self.mechanism_ids != REPAIRED_MECHANISM_IDS:
            raise ValueError("repair audit changes the preregistered mechanism set")
        expected_ready = not self.rejection_reasons
        if self.ready != expected_ready:
            raise ValueError("repair audit readiness is inconsistent")
        expected_stage = (
            (
                "flash_repaired_mechanism_development"
                if self.stage == "development"
                else "flash_repaired_mechanism_confirmation"
            )
            if expected_ready
            else "mechanism_task_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("repair audit transition is not fail-closed")
        if self.audit_id != repair_static_audit_id(self):
            raise ValueError("repair static audit identity is invalid")
        return self


class CapabilityMechanismRepairPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    stage: RepairStage
    source_artifacts_path: str = Field(min_length=1)
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    prior_confirmation_report_path: str = Field(min_length=1)
    prior_confirmation_report_sha256: str = Field(min_length=64, max_length=64)
    prior_confirmation_report_id: str = Field(min_length=1)
    prior_confirmed_mechanism_ids: tuple[str, ...]
    selection_freeze_path: str | None = None
    selection_freeze_sha256: str | None = None
    selection_freeze_id: str | None = None
    exclusion_population_paths: tuple[str, ...] = Field(min_length=1)
    exclusion_population_sha256: dict[str, str]
    sampling_salt: str = Field(min_length=1)
    tier_schedule: tuple[MechanismTier, ...]
    groups: tuple[MechanismDevelopmentGroup, ...] = Field(min_length=1)
    static_audit: MechanismRepairStaticAudit
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    next_permitted_stage: Literal[
        "flash_repaired_mechanism_development",
        "flash_repaired_mechanism_confirmation",
        "mechanism_task_repair_only",
    ]
    schema_version: str = MECHANISM_REPAIR_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> CapabilityMechanismRepairPopulation:
        expected_schedule = (
            DEVELOPMENT_TIER_SCHEDULE if self.stage == "development" else CONFIRMATION_TIER_SCHEDULE
        )
        if self.tier_schedule != expected_schedule:
            raise ValueError("repair population changes the frozen tier schedule")
        if self.prior_confirmed_mechanism_ids != PRIOR_CONFIRMED_MECHANISM_IDS:
            raise ValueError("repair population changes replicated prior findings")
        freeze_identity = (
            self.selection_freeze_path,
            self.selection_freeze_sha256,
            self.selection_freeze_id,
        )
        if self.stage == "confirmation" and not all(freeze_identity):
            raise ValueError("repair Confirmation population lacks its selection freeze identity")
        if self.stage == "development" and any(freeze_identity):
            raise ValueError("repair Development population cannot bind a selection freeze")
        expected_count = len(REPAIRED_MECHANISM_IDS) * len(expected_schedule)
        if len(self.groups) != expected_count:
            raise ValueError("repair population has an incomplete group denominator")
        if self.static_audit.next_permitted_stage != self.next_permitted_stage:
            raise ValueError("repair population stage differs from its audit")
        if self.population_id != repair_population_id(self):
            raise ValueError("repair population identity is invalid")
        return self

    @property
    def tasks(self) -> tuple[CapabilitySensitiveTaskArtifact, ...]:
        return tuple(
            variant.artifact
            for group in self.groups
            for variant in (group.control, group.mechanism)
        )


class MechanismRepairSelectionFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_population_path: str = Field(min_length=1)
    source_population_sha256: str = Field(min_length=64, max_length=64)
    source_population_id: str = Field(min_length=1)
    source_report_path: str = Field(min_length=1)
    source_report_sha256: str = Field(min_length=64, max_length=64)
    source_report_id: str = Field(min_length=1)
    source_contract_path: str = Field(min_length=1)
    source_contract_sha256: str = Field(min_length=64, max_length=64)
    source_contract_id: str = Field(min_length=1)
    selected_mechanism_ids: tuple[str, ...]
    confirmation_tier_schedule: dict[str, tuple[MechanismTier, ...]]
    excluded_task_artifact_ids: tuple[str, ...] = Field(min_length=1)
    excluded_group_ids: tuple[str, ...] = Field(min_length=1)
    excluded_evidence_ids: tuple[str, ...] = Field(min_length=1)
    excluded_evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    excluded_core_semantic_signatures: tuple[str, ...] = Field(min_length=1)
    confirmation_response_access: Literal["forbidden"] = "forbidden"
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    next_permitted_stage: Literal["fresh_repaired_mechanism_confirmation_population"] = (
        "fresh_repaired_mechanism_confirmation_population"
    )
    schema_version: str = MECHANISM_REPAIR_FREEZE_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> MechanismRepairSelectionFreeze:
        if self.selected_mechanism_ids != REPAIRED_MECHANISM_IDS:
            raise ValueError("repair freeze requires both repaired mechanisms")
        if set(self.confirmation_tier_schedule) != set(REPAIRED_MECHANISM_IDS):
            raise ValueError("repair freeze schedule is incomplete")
        if any(
            value != CONFIRMATION_TIER_SCHEDULE
            for value in self.confirmation_tier_schedule.values()
        ):
            raise ValueError("repair freeze changes the Confirmation schedule")
        for values in (
            self.excluded_task_artifact_ids,
            self.excluded_group_ids,
            self.excluded_evidence_ids,
            self.excluded_evidence_version_ids,
            self.excluded_core_semantic_signatures,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("repair freeze exclusions are not canonical")
        if self.freeze_id != repair_freeze_id(self):
            raise ValueError("repair selection freeze identity is invalid")
        return self


class FinanceCapabilityMechanismRepairContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    stage: RuntimeResolutionStage
    repair_stage: RepairStage
    source_population_path: str = Field(min_length=1)
    source_population_sha256: str = Field(min_length=64, max_length=64)
    source_population_id: str = Field(min_length=1)
    source_selection_freeze_path: str | None = None
    source_selection_freeze_sha256: str | None = None
    source_selection_freeze_id: str | None = None
    source_v25_20_contract_path: str = Field(min_length=1)
    source_v25_20_contract_sha256: str = Field(min_length=64, max_length=64)
    source_v25_20_contract_id: str = Field(min_length=1)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(min_length=1, max_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    tasks: tuple[CapabilitySensitiveTaskArtifact, ...] = Field(min_length=1)
    task_group_ids: dict[str, str]
    task_mechanism_ids: dict[str, str]
    task_mechanism_tiers: dict[str, MechanismTier]
    task_variant_roles: dict[str, Literal["resolved_control", "mechanism_required"]]
    bindings: tuple[RuntimeTaskBinding, ...] = Field(min_length=1)
    replicas: int = Field(ge=3, le=5)
    requested_rollout_count: int = Field(ge=1)
    maximum_model_tokens_per_rollout: int = Field(ge=1)
    maximum_observation_summary_bytes: int = Field(ge=1)
    maximum_public_context_bytes: int = Field(ge=1)
    model_contract_repair_attempts: int = Field(ge=0)
    rollout_identity_tokens: dict[str, str]
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "flash_repaired_mechanism_development",
        "flash_repaired_mechanism_confirmation",
    ]
    schema_version: str = MECHANISM_REPAIR_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceCapabilityMechanismRepairContract:
        expected_runtime_stage = (
            RuntimeResolutionStage.RESIDUAL_DEVELOPMENT
            if self.repair_stage == "development"
            else RuntimeResolutionStage.HELDOUT_CONFIRMATION
        )
        expected_replicas = (
            DEVELOPMENT_REPLICAS
            if self.repair_stage == "development"
            else CONFIRMATION_REPLICAS
        )
        if self.stage != expected_runtime_stage or self.replicas != expected_replicas:
            raise ValueError("repair contract stage or replica denominator is invalid")
        if self.repair_stage == "confirmation":
            if not (
                self.source_selection_freeze_path
                and self.source_selection_freeze_sha256
                and self.source_selection_freeze_id
            ):
                raise ValueError("repair Confirmation lacks an immutable selection freeze")
        elif any(
            (
                self.source_selection_freeze_path,
                self.source_selection_freeze_sha256,
                self.source_selection_freeze_id,
            )
        ):
            raise ValueError("repair Development improperly reads a selection freeze")
        if {item.arm for item in self.model_contracts} != {ExplorerArm.FLASH}:
            raise ValueError("repaired mechanism experiment is Flash-only")
        task_ids = {item.artifact_id for item in self.tasks}
        if len(task_ids) != len(self.tasks):
            raise ValueError("repair contract duplicates a task artifact")
        if {item.task_artifact_id for item in self.bindings} != task_ids:
            raise ValueError("repair contract task/binding identity is incomplete")
        maps = (
            self.task_group_ids,
            self.task_mechanism_ids,
            self.task_mechanism_tiers,
            self.task_variant_roles,
        )
        if any(set(item) != task_ids for item in maps):
            raise ValueError("repair contract task metadata maps are incomplete")
        if set(self.task_mechanism_ids.values()) != set(REPAIRED_MECHANISM_IDS):
            raise ValueError("repair contract changes the mechanism set")
        if self.requested_rollout_count != len(self.bindings) * self.replicas:
            raise ValueError("repair contract rollout denominator is inconsistent")
        expected_tokens = {
            f"{binding.binding_id}|{replicate}"
            for binding in self.bindings
            for replicate in range(self.replicas)
        }
        if set(self.rollout_identity_tokens) != expected_tokens:
            raise ValueError("repair rollout identities are incomplete")
        expected_next = (
            "flash_repaired_mechanism_development"
            if self.repair_stage == "development"
            else "flash_repaired_mechanism_confirmation"
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("repair contract transition is invalid")
        if self.contract_id != repair_contract_id(self):
            raise ValueError("repair contract identity is invalid")
        return self


class FinanceCapabilityMechanismRepairReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    stage: RepairStage
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=1)
    runtime_eligible_rollout_count: int = Field(ge=0)
    api_transport_resolution_rate: float = Field(ge=0, le=1)
    bounded_json_resolution_rate: float = Field(ge=0, le=1)
    observation_replay_rate: float = Field(ge=0, le=1)
    authority_integrity_rate: float = Field(ge=0, le=1)
    runtime_pathology_rate: float = Field(ge=0, le=1)
    semantic_accuracy_given_runtime_eligible: float = Field(ge=0, le=1)
    end_to_end_valid_success_rate: float = Field(ge=0, le=1)
    selection_decisions: tuple[MechanismSelectionDecision, ...] = Field(min_length=2, max_length=2)
    selected_or_confirmed_mechanism_ids: tuple[str, ...]
    all_repaired_mechanisms_passed: bool
    prior_confirmed_mechanism_ids: tuple[str, ...]
    all_information_geometry_mechanisms_confirmed: bool
    information_geometry_authorized: bool
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    pro_api_call_count: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    failure_codes: tuple[str, ...]
    next_permitted_stage: Literal[
        "freeze_repaired_mechanism_selection",
        "fresh_repaired_mechanism_confirmation_population",
        "flash_mechanism_information_geometry",
        "mechanism_task_repair_only",
        "runtime_measurement_repair_only",
    ]
    schema_version: str = MECHANISM_REPAIR_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceCapabilityMechanismRepairReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("repair report lacks its complete denominator")
        observed = tuple(
            item.mechanism_id for item in self.selection_decisions if item.selected_for_confirmation
        )
        if self.selected_or_confirmed_mechanism_ids != observed:
            raise ValueError("repair report mechanism list differs from decisions")
        all_repaired = observed == REPAIRED_MECHANISM_IDS
        if self.all_repaired_mechanisms_passed != all_repaired:
            raise ValueError("repair report pass state is inconsistent")
        expected_all = (
            self.stage == "confirmation"
            and all_repaired
            and self.prior_confirmed_mechanism_ids == PRIOR_CONFIRMED_MECHANISM_IDS
        )
        if self.all_information_geometry_mechanisms_confirmed != expected_all:
            raise ValueError("combined mechanism confirmation state is inconsistent")
        if self.information_geometry_authorized != expected_all:
            raise ValueError("information geometry authorization is inconsistent")
        if self.stage == "development" and self.information_geometry_authorized:
            raise ValueError("Development cannot authorize information geometry")
        if self.report_id != repair_report_id(self):
            raise ValueError("repair report identity is invalid")
        return self


def repair_static_audit_id(value: MechanismRepairStaticAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_capability_mechanism_repair_static_audit:",
    )


def repair_population_id(value: CapabilityMechanismRepairPopulation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"population_id"}),
        prefix="finance_capability_mechanism_repair_population:",
    )


def repair_freeze_id(value: MechanismRepairSelectionFreeze) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"freeze_id"}),
        prefix="finance_capability_mechanism_repair_freeze:",
    )


def repair_contract_id(value: FinanceCapabilityMechanismRepairContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_capability_mechanism_repair_contract:",
    )


def repair_report_id(value: FinanceCapabilityMechanismRepairReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_capability_mechanism_repair_report:",
    )


def build_repair_population(
    *,
    stage: RepairStage,
    source_artifacts_path: Path,
    prior_confirmation_report_path: Path,
    exclusion_population_paths: tuple[Path, ...],
    output_dir: Path,
    run_id: str,
    sampling_salt: str,
    selection_freeze_path: Path | None = None,
) -> CapabilityMechanismRepairPopulation:
    output_path = output_dir / "finance_capability_mechanism_repair_population.json"
    if output_path.exists():
        raise ValueError("mechanism repair population is immutable")
    prior_report = _load_prior_confirmation_report(prior_confirmation_report_path)
    if tuple(prior_report["confirmed_mechanism_ids"]) != PRIOR_CONFIRMED_MECHANISM_IDS:
        raise ValueError("repair population lacks the two replicated v25.21 mechanisms")
    schedule = DEVELOPMENT_TIER_SCHEDULE if stage == "development" else CONFIRMATION_TIER_SCHEDULE
    freeze: MechanismRepairSelectionFreeze | None = None
    if stage == "confirmation":
        if selection_freeze_path is None:
            raise ValueError("repair Confirmation requires a frozen Development selection")
        freeze = MechanismRepairSelectionFreeze.model_validate_json(
            selection_freeze_path.read_text(encoding="utf-8")
        )
        if freeze.selected_mechanism_ids != REPAIRED_MECHANISM_IDS:
            raise ValueError("repair Confirmation changes the frozen mechanism set")
        exclusion_population_paths = tuple(
            dict.fromkeys(
                (
                    *exclusion_population_paths,
                    Path(freeze.source_population_path),
                )
            )
        )
    elif selection_freeze_path is not None:
        raise ValueError("repair Development cannot access Confirmation selection")
    exclusions = _collect_exclusions(exclusion_population_paths)
    pool = _load_evidence_pool(source_artifacts_path)
    builder = _CapabilityTaskBuilder(pool, sampling_salt=sampling_salt)
    groups = _build_repair_groups(
        builder,
        tuple(pool.public.values()),
        schedule=schedule,
        exclusions=exclusions,
        sampling_salt=sampling_salt,
    )
    audit = make_repair_static_audit(
        stage=stage,
        groups=groups,
        exclusions=exclusions,
        expected_group_count=len(REPAIRED_MECHANISM_IDS) * len(schedule),
    )
    values = {
        "run_id": run_id,
        "stage": stage,
        "source_artifacts_path": str(source_artifacts_path.resolve()),
        "source_artifacts_sha256": _sha256(source_artifacts_path),
        "prior_confirmation_report_path": str(prior_confirmation_report_path.resolve()),
        "prior_confirmation_report_sha256": _sha256(prior_confirmation_report_path),
        "prior_confirmation_report_id": str(prior_report["report_id"]),
        "prior_confirmed_mechanism_ids": PRIOR_CONFIRMED_MECHANISM_IDS,
        "selection_freeze_path": (
            str(selection_freeze_path.resolve()) if selection_freeze_path else None
        ),
        "selection_freeze_sha256": (
            _sha256(selection_freeze_path) if selection_freeze_path else None
        ),
        "selection_freeze_id": freeze.freeze_id if freeze else None,
        "exclusion_population_paths": tuple(
            str(item.resolve()) for item in exclusion_population_paths
        ),
        "exclusion_population_sha256": {
            str(item.resolve()): _sha256(item) for item in exclusion_population_paths
        },
        "sampling_salt": sampling_salt,
        "tier_schedule": schedule,
        "groups": groups,
        "static_audit": audit,
        "next_permitted_stage": audit.next_permitted_stage,
    }
    provisional = CapabilityMechanismRepairPopulation.model_construct(
        population_id="pending", **values
    )
    population = CapabilityMechanismRepairPopulation(
        population_id=repair_population_id(provisional), **values
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, population.model_dump(mode="json"))
    _write_json_atomic(
        output_dir / "finance_capability_mechanism_repair_static_audit.json",
        audit.model_dump(mode="json"),
    )
    return population


def _build_repair_groups(
    builder: _CapabilityTaskBuilder,
    evidence_pool: tuple[EvidenceItem, ...],
    *,
    schedule: tuple[MechanismTier, ...],
    exclusions: dict[str, set[str]],
    sampling_salt: str,
) -> tuple[MechanismDevelopmentGroup, ...]:
    used_ids = set(exclusions["evidence_ids"])
    used_versions = set(exclusions["evidence_version_ids"])
    groups: list[MechanismDevelopmentGroup] = []
    for mechanism_id in REPAIRED_MECHANISM_IDS:
        family = CORE_FAMILY_BY_MECHANISM[mechanism_id]
        for group_index, tier in enumerate(schedule):
            source_tiers = (
                ("frontier", "easy_control") if tier == "frontier" else ("easy_control", "frontier")
            )
            planned: tuple[_CoreSelection, tuple[EvidenceItem, ...]] | None = None
            for source_tier_raw in source_tiers:
                from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
                    DifficultyTier,
                )

                source_tier = DifficultyTier(source_tier_raw)
                for gold, program, instruction, projection in _candidate_iterator(
                    builder, family, source_tier
                ):
                    gold_ids = {item.evidence_id for item in gold}
                    gold_versions = {item.evidence_version_id for item in gold}
                    if gold_ids & used_ids or gold_versions & used_versions:
                        continue
                    selection = _CoreSelection(
                        mechanism_id=mechanism_id,
                        mechanism_tier=tier,
                        group_index=group_index,
                        family=family,
                        source_tier=source_tier,
                        gold=gold,
                        program=program,
                        instruction=instruction,
                        answer_projection=projection,
                    )
                    try:
                        distractors = _select_mechanism_distractors(
                            selection,
                            evidence_pool,
                            reserved_evidence_ids=used_ids | gold_ids,
                            reserved_evidence_version_ids=used_versions | gold_versions,
                            sampling_salt=sampling_salt,
                        )
                    except ValueError:
                        continue
                    planned = selection, distractors
                    break
                if planned is not None:
                    break
            if planned is None:
                raise ValueError(
                    "real Finance Evidence cannot support a fresh repaired mechanism cell: "
                    f"{mechanism_id}/{tier}/{group_index}"
                )
            selection, distractors = planned
            base = _materialize_group(builder, selection, distractors)
            repaired = _repair_group(base)
            groups.append(repaired)
            for artifact in (
                repaired.control.artifact.public_corpus,
                repaired.mechanism.artifact.public_corpus,
            ):
                used_ids.update(item.evidence_id for item in artifact.evidence)
                used_versions.update(item.evidence_version_id for item in artifact.evidence)
    return tuple(groups)


def _repair_group(group: MechanismDevelopmentGroup) -> MechanismDevelopmentGroup:
    mechanism = group.mechanism
    expected = mechanism.artifact.projected_expected_output
    if group.mechanism_id == VERIFICATION_MECHANISM_ID:
        candidate, canonical_candidate, target_field = _make_subtle_candidate(
            expected,
            mechanism.artifact.evidence_bundle.evidence,
            mechanism.artifact.public_corpus.evidence,
            group.mechanism_tier,
            group.group_index,
        )
        scenario = make_candidate_verification_scenario(
            candidate_payload=candidate,
            canonical_candidate_payload=canonical_candidate,
            repair_target_field=target_field,
        )
        artifact = _with_repair_scenario(
            mechanism.artifact,
            scenario,
            candidate_payload=candidate,
        )
        candidate_status = "invalid_localized"
    elif group.mechanism_id == STOPPING_MECHANISM_ID:
        roles = _completion_roles(mechanism.artifact.evidence_bundle.evidence)
        scenario = make_state_dependent_stopping_scenario(required_roles=roles)
        artifact = _with_repair_scenario(
            mechanism.artifact,
            scenario,
            candidate_payload=None,
        )
        candidate_status = "not_applicable"
    else:
        raise ValueError(f"unexpected repair mechanism: {group.mechanism_id}")
    variant_values = {
        "role": mechanism.role,
        "mechanism_id": mechanism.mechanism_id,
        "mechanism_tier": mechanism.mechanism_tier,
        "artifact": artifact,
        "action_graph": mechanism.action_graph,
        "public_completeness_invariant": mechanism.public_completeness_invariant,
        "compatibility_policy": mechanism.compatibility_policy,
        "candidate_status": candidate_status,
        "recovery_origin_family": None,
    }
    provisional_variant = MechanismTaskVariant.model_construct(
        variant_id="pending",
        contract_hash="pending",
        **variant_values,
    )
    contract_hash = mechanism_task_variant_hash(provisional_variant)
    repaired_variant = MechanismTaskVariant(
        variant_id=canonical_hash(
            {
                "repair_version": MECHANISM_REPAIR_VERSION,
                "contract_hash": contract_hash,
            },
            prefix="finance_capability_mechanism_repair_variant:",
        ),
        contract_hash=contract_hash,
        **variant_values,
    )
    group_values = {
        "mechanism_id": group.mechanism_id,
        "mechanism_tier": group.mechanism_tier,
        "group_index": group.group_index,
        "core_semantic_signature": group.core_semantic_signature,
        "control": group.control,
        "mechanism": repaired_variant,
        "mutations": group.mutations,
    }
    provisional_group = MechanismDevelopmentGroup.model_construct(
        group_id="pending",
        group_hash="pending",
        **group_values,
    )
    group_id = mechanism_group_id(provisional_group)
    provisional_group = provisional_group.model_copy(update={"group_id": group_id})
    return MechanismDevelopmentGroup(
        group_id=group_id,
        group_hash=mechanism_group_hash(provisional_group),
        **group_values,
    )


def _make_subtle_candidate(
    expected: Mapping[str, Any],
    gold_evidence: Sequence[EvidenceItem],
    public_evidence: Sequence[EvidenceItem],
    tier: MechanismTier,
    group_index: int,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    canonical = dict(expected)
    semantic_getters = {
        "source_id": lambda item: item.source.source_id,
        "definition_id": lambda item: item.definition.definition_id,
        "time_basis": lambda item: item.temporal_context.basis,
        "frequency": lambda item: item.temporal_context.frequency,
        "unit": lambda item: getattr(item.payload, "unit", None),
        "currency": lambda item: getattr(item.payload, "currency", None),
    }
    semantic_alternatives: list[tuple[str, Any]] = []
    gold_ids = {item.evidence_id for item in gold_evidence}
    for field, getter in semantic_getters.items():
        gold_values = {str(value) for item in gold_evidence if (value := getter(item))}
        if len(gold_values) != 1:
            continue
        canonical_value = next(iter(gold_values))
        canonical[field] = canonical_value
        alternatives = sorted(
            {
                str(value)
                for item in public_evidence
                if item.evidence_id not in gold_ids
                and (value := getter(item))
                and str(value) != canonical_value
            }
        )
        if alternatives:
            semantic_alternatives.append((field, alternatives[0]))
    collection_getters = {
        "entity_scope": lambda item: item.subject.subject_id,
        "metric_scope": lambda item: item.predicate,
        "period_scope": lambda item: item.temporal_context.label,
    }
    for field, getter in collection_getters.items():
        canonical_values = sorted(
            {str(value) for item in gold_evidence if (value := getter(item))}
        )
        if not canonical_values:
            continue
        canonical[field] = canonical_values
        alternatives = sorted(
            {
                str(value)
                for item in public_evidence
                if item.evidence_id not in gold_ids
                and (value := getter(item))
                and str(value) not in canonical_values
            }
        )
        if alternatives:
            replacement_values = sorted(
                {*canonical_values[:-1], alternatives[0]}
            )
            semantic_alternatives.append((field, replacement_values))
    if semantic_alternatives:
        preferred = (
            (
                "definition_id",
                "period_scope",
                "source_id",
                "time_basis",
                "unit",
                "entity_scope",
                "metric_scope",
                "frequency",
                "currency",
            )
            if tier == "frontier"
            else (
                "period_scope",
                "unit",
                "entity_scope",
                "metric_scope",
                "frequency",
                "time_basis",
                "source_id",
                "definition_id",
                "currency",
            )
        )
        ranked = sorted(
            semantic_alternatives,
            key=lambda item: (
                preferred.index(item[0]) if item[0] in preferred else len(preferred),
                item[0],
            ),
        )
        target, replacement = ranked[group_index % len(ranked)]
        candidate = dict(canonical)
        candidate[target] = replacement
        return candidate, canonical, target

    fallback_target = next(
        (field for field in ("difference", "value", "ratio", "growth") if field in expected),
        None,
    )
    if fallback_target is None:
        raise ValueError("verification repair lacks a localizable candidate field")
    try:
        number = Decimal(str(expected[fallback_target]))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("verification repair fallback target is not numeric") from exc
    relative = Decimal("0.0005") if tier == "bridge" else Decimal("0.0001")
    floor = Decimal("0.000001")
    delta = max(abs(number) * relative, floor)
    if group_index % 2:
        delta = -delta
    candidate = dict(canonical)
    candidate[fallback_target] = str(number + delta)
    if candidate[fallback_target] == str(expected[fallback_target]):
        raise ValueError("verification candidate mutation collapsed")
    return candidate, canonical, fallback_target


def _completion_roles(evidence: Sequence[EvidenceItem]) -> tuple[FinanceCompletionRole, ...]:
    roles = tuple(
        FinanceCompletionRole(
            role_id=f"required_role_{index}",
            subject_alias=item.subject.name,
            metric_alias=item.predicate,
            period_label=str(item.temporal_context.label),
            public_filters={
                "source_id": item.source.source_id,
                "definition_id": item.definition.definition_id,
            },
        )
        for index, item in enumerate(evidence, start=1)
    )
    signatures = {
        canonical_hash(
            item.model_dump(mode="json", exclude={"role_id"}),
            prefix="finance_completion_role_selector:",
        )
        for item in roles
    }
    if len(roles) < 2 or len(signatures) != len(roles):
        raise ValueError("stopping repair requires unique observable public roles")
    return roles


def _with_repair_scenario(
    artifact: CapabilitySensitiveTaskArtifact,
    scenario: FinanceCapabilityMechanismScenario,
    *,
    candidate_payload: dict[str, Any] | None,
) -> CapabilitySensitiveTaskArtifact:
    public = artifact.task.public
    metadata = dict(public.metadata)
    old_contract_raw = metadata.get("v25_21_mechanism")
    if not isinstance(old_contract_raw, Mapping):
        raise ValueError("repair task lacks its source mechanism contract")
    old_contract = dict(old_contract_raw)
    if candidate_payload is not None:
        old_contract["untrusted_candidate"] = candidate_payload
    metadata["v25_21_mechanism"] = old_contract
    metadata.pop("v25_22_runtime_scenario", None)
    repair_contract = {
        "repair_version": MECHANISM_REPAIR_VERSION,
        "mechanism_kind": scenario.mechanism_kind,
        "candidate_requires_independent_replay": (
            scenario.mechanism_kind == "candidate_verification_and_repair"
        ),
        "candidate_contains_exactly_one_local_error": (
            scenario.mechanism_kind == "candidate_verification_and_repair"
        ),
        "candidate_preserve_unaffected_fields": (
            scenario.mechanism_kind == "candidate_verification_and_repair"
        ),
        "incomplete_state_observation_required": (
            scenario.mechanism_kind == "state_dependent_control_and_stopping"
        ),
        "verified_completion_required_before_answer": True,
        "redundant_action_policy": scenario.redundant_action_policy,
        "transition_policy": scenario.transition_policy,
    }
    metadata["v25_22_task_repair"] = repair_contract
    guidance_raw = metadata.get("agent_contract_guidance")
    guidance = dict(guidance_raw) if isinstance(guidance_raw, Mapping) else {}
    guidance["capability_mechanism_contract"] = old_contract
    guidance["capability_mechanism_repair_contract"] = repair_contract
    metadata["agent_contract_guidance"] = guidance
    instruction = public.instruction
    if candidate_payload is not None:
        candidate_clause = (
            "The untrusted candidate payload is "
            + json.dumps(candidate_payload, ensure_ascii=False, sort_keys=True)
            + ". "
        )
        instruction, replacement_count = re.subn(
            r"The untrusted candidate payload is \{.*?\}\. ",
            lambda _: candidate_clause,
            instruction,
            count=1,
        )
        if replacement_count != 1:
            raise ValueError("verification source instruction lacks one candidate clause")
        instruction = (
            "Independently derive the answer before trusting the candidate. Submit the repaired "
            "candidate under claim_or_result.candidate_payload to cross_check_evidence; change "
            "only the localized target field and preserve every other field exactly. " + instruction
        )
    else:
        instruction = (
            "The Host exposes a state transition: after selecting a strict nonempty subset of "
            "required records, every non-verification action is blocked until you call "
            "cross_check_evidence and observe completion_state.complete=false. Then retrieve the "
            "remaining roles, execute the calculation, and obtain a verified "
            "completion_state.complete=true. Emit the final answer immediately after that "
            "verification; every additional tool call incurs the frozen redundancy cost. "
            + instruction
        )
    updated_public = public.model_copy(update={"instruction": instruction, "metadata": metadata})
    oracle = artifact.task.oracle
    selection_contract = dict(oracle.selection_contract)
    selection_contract[FINANCE_CAPABILITY_MECHANISM_ORACLE_KEY] = scenario.model_dump(mode="json")
    updated_oracle = oracle.model_copy(update={"selection_contract": selection_contract})
    task = artifact.task.model_copy(
        update={"public": updated_public, "oracle": updated_oracle}
    )
    provisional = artifact.model_copy(update={"artifact_id": "pending", "task": task})
    return artifact.model_copy(
        update={
            "artifact_id": capability_sensitive_task_artifact_id(provisional),
            "task": task,
        }
    )


def make_repair_static_audit(
    *,
    stage: RepairStage,
    groups: tuple[MechanismDevelopmentGroup, ...],
    exclusions: dict[str, set[str]],
    expected_group_count: int,
) -> MechanismRepairStaticAudit:
    variants = tuple(variant for group in groups for variant in (group.control, group.mechanism))
    scenarios = tuple(_scenario_from_group(group) for group in groups)
    verification_groups = tuple(
        group for group in groups if group.mechanism_id == VERIFICATION_MECHANISM_ID
    )
    stopping_groups = tuple(
        group for group in groups if group.mechanism_id == STOPPING_MECHANISM_ID
    )
    public_sets = tuple(
        {item.evidence_id for item in group.mechanism.artifact.public_corpus.evidence}
        for group in groups
    )
    within_disjoint = all(
        not left & right
        for index, left in enumerate(public_sets)
        for right in public_sets[index + 1 :]
    )
    task_ids = {variant.artifact.artifact_id for variant in variants}
    group_ids = {group.group_id for group in groups}
    evidence_ids = set().union(*public_sets) if public_sets else set()
    evidence_versions = {
        item.evidence_version_id
        for group in groups
        for item in group.mechanism.artifact.public_corpus.evidence
    }
    semantics = {group.core_semantic_signature for group in groups}
    operation_rate = _rate(item.artifact.verification.passed for item in variants)
    matched_rate = _rate(_matched_contract_passes(group) for group in groups)
    intervention_rate = _rate(_matched_intervention_passes(group) for group in groups)
    answer_rate = _rate(_answer_contract_passes(variant) for variant in variants)
    scenario_rate = _rate(item is not None for item in scenarios)
    isolation_rate = _rate(_public_oracle_isolated(group) for group in groups)
    candidate_rate = _rate(
        _verification_candidate_is_corrupt(group) for group in verification_groups
    )
    semantic_error_rate = _rate(
        _verification_candidate_has_semantic_error(group)
        for group in verification_groups
    )
    stopping_roles = _rate(_stopping_roles_are_observable(group) for group in stopping_groups)
    stopping_cost = _rate(
        _scenario_from_group(group).redundant_action_policy
        == "reject_every_tool_call_after_verified_completion"
        for group in stopping_groups
    )
    stopping_transition = _rate(
        _scenario_from_group(group).transition_policy
        == "require_incomplete_probe_before_remaining_roles"
        for group in stopping_groups
    )
    prior_task_disjoint = not task_ids & exclusions["task_ids"]
    prior_group_disjoint = not group_ids & exclusions["group_ids"]
    prior_evidence_disjoint = not evidence_ids & exclusions["evidence_ids"]
    prior_version_disjoint = not evidence_versions & exclusions["evidence_version_ids"]
    prior_semantic_disjoint = not semantics & exclusions["semantic_signatures"]
    benchmark_isolated = all(
        not _contains_benchmark_content(variant.artifact.task.public.model_dump(mode="json"))
        for variant in variants
    )
    reasons: list[str] = []
    checks = (
        (len(groups) == expected_group_count, "group_denominator_incomplete"),
        (
            {group.mechanism_id for group in groups} == set(REPAIRED_MECHANISM_IDS),
            "repair_mechanism_set_mismatch",
        ),
        (operation_rate == 1.0, "operation_replay_failed"),
        (matched_rate == 1.0, "matched_contract_failed"),
        (intervention_rate == 1.0, "matched_intervention_failed"),
        (answer_rate == 1.0, "answer_contract_failed"),
        (scenario_rate == 1.0, "runtime_scenario_missing"),
        (isolation_rate == 1.0, "public_oracle_isolation_failed"),
        (candidate_rate == 1.0, "verification_candidate_not_localized"),
        (semantic_error_rate == 1.0, "verification_semantic_error_missing"),
        (stopping_roles == 1.0, "stopping_roles_not_observable"),
        (stopping_cost == 1.0, "stopping_asymmetric_cost_missing"),
        (stopping_transition == 1.0, "stopping_transition_observability_missing"),
        (within_disjoint, "within_population_evidence_overlap"),
        (prior_task_disjoint, "prior_task_overlap"),
        (prior_group_disjoint, "prior_group_overlap"),
        (prior_evidence_disjoint, "prior_evidence_overlap"),
        (prior_version_disjoint, "prior_evidence_version_overlap"),
        (prior_semantic_disjoint, "prior_semantic_overlap"),
        (benchmark_isolated, "public_benchmark_content_detected"),
    )
    reasons.extend(code for passed, code in checks if not passed)
    next_stage = (
        (
            "flash_repaired_mechanism_development"
            if stage == "development"
            else "flash_repaired_mechanism_confirmation"
        )
        if not reasons
        else "mechanism_task_repair_only"
    )
    values = {
        "stage": stage,
        "mechanism_ids": REPAIRED_MECHANISM_IDS,
        "group_count": len(groups),
        "expected_group_count": expected_group_count,
        "operation_replay_pass_rate": operation_rate,
        "matched_contract_pass_rate": matched_rate,
        "matched_intervention_pass_rate": intervention_rate,
        "answer_contract_pass_rate": answer_rate,
        "runtime_scenario_coverage_rate": scenario_rate,
        "public_oracle_isolation_rate": isolation_rate,
        "verification_candidate_corruption_rate": candidate_rate,
        "verification_semantic_error_rate": semantic_error_rate,
        "stopping_role_observability_rate": stopping_roles,
        "stopping_asymmetric_cost_rate": stopping_cost,
        "stopping_transition_observability_rate": stopping_transition,
        "within_population_evidence_disjoint": within_disjoint,
        "prior_task_disjoint": prior_task_disjoint,
        "prior_group_disjoint": prior_group_disjoint,
        "prior_evidence_disjoint": prior_evidence_disjoint,
        "prior_evidence_version_disjoint": prior_version_disjoint,
        "prior_semantic_disjoint": prior_semantic_disjoint,
        "benchmark_content_isolation_passed": benchmark_isolated,
        "rejection_reasons": tuple(reasons),
        "ready": not reasons,
        "next_permitted_stage": next_stage,
    }
    provisional = MechanismRepairStaticAudit.model_construct(audit_id="pending", **values)
    return MechanismRepairStaticAudit(audit_id=repair_static_audit_id(provisional), **values)


def _scenario_from_group(
    group: MechanismDevelopmentGroup,
) -> FinanceCapabilityMechanismScenario:
    raw = group.mechanism.artifact.task.oracle.selection_contract.get(
        FINANCE_CAPABILITY_MECHANISM_ORACLE_KEY
    )
    return FinanceCapabilityMechanismScenario.model_validate(raw)


def _public_oracle_isolated(group: MechanismDevelopmentGroup) -> bool:
    artifact = group.mechanism.artifact
    public_payload = json.dumps(
        artifact.task.public.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )
    forbidden_tokens = (
        FINANCE_CAPABILITY_MECHANISM_ORACLE_KEY,
        "canonical_candidate_payload",
        "candidate_repair_target_field",
        "candidate_preserve_fields",
        "required_completion_role_ids",
        "scenario_id",
    )
    return (
        FINANCE_CAPABILITY_MECHANISM_ORACLE_KEY
        in artifact.task.oracle.selection_contract
        and all(token not in public_payload for token in forbidden_tokens)
    )


def _verification_candidate_is_corrupt(group: MechanismDevelopmentGroup) -> bool:
    scenario = _scenario_from_group(group)
    expected = group.mechanism.artifact.projected_expected_output
    target = str(scenario.repair_target_field)
    candidate = dict(scenario.candidate_payload or {})
    canonical = dict(scenario.canonical_candidate_payload or {})
    mismatches = {
        field for field in candidate if candidate.get(field) != canonical.get(field)
    }
    return (
        scenario.mechanism_kind == "candidate_verification_and_repair"
        and set(expected) <= set(canonical)
        and all(canonical[field] == value for field, value in expected.items())
        and set(candidate) == set(canonical)
        and mismatches == {target}
        and set(scenario.preserve_fields) == set(canonical) - {target}
    )


def _verification_candidate_has_semantic_error(
    group: MechanismDevelopmentGroup,
) -> bool:
    scenario = _scenario_from_group(group)
    return scenario.repair_target_field in {
        "source_id",
        "definition_id",
        "time_basis",
        "frequency",
        "unit",
        "currency",
        "entity_scope",
        "metric_scope",
        "period_scope",
    }


def _stopping_roles_are_observable(group: MechanismDevelopmentGroup) -> bool:
    scenario = _scenario_from_group(group)
    evidence = group.mechanism.artifact.evidence_bundle.evidence
    if scenario.mechanism_kind != "state_dependent_control_and_stopping":
        return False
    role_signatures = {
        canonical_hash(
            item.model_dump(mode="json", exclude={"role_id"}),
            prefix="finance_completion_role_selector:",
        )
        for item in scenario.required_roles
    }
    return (
        len(scenario.required_roles) == len(evidence)
        and len(role_signatures) == len(scenario.required_roles)
        and len(scenario.required_roles) >= 2
    )


def _collect_exclusions(paths: Sequence[Path]) -> dict[str, set[str]]:
    output: dict[str, set[str]] = {
        "task_ids": set(),
        "group_ids": set(),
        "evidence_ids": set(),
        "evidence_version_ids": set(),
        "semantic_signatures": set(),
    }
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        groups = payload.get("groups", ())
        if not isinstance(groups, list):
            raise ValueError(f"exclusion population has no groups: {path}")
        for group in groups:
            if not isinstance(group, Mapping):
                continue
            if group.get("group_id"):
                output["group_ids"].add(str(group["group_id"]))
            if group.get("core_semantic_signature"):
                output["semantic_signatures"].add(str(group["core_semantic_signature"]))
            for role in ("control", "mechanism"):
                variant = group.get(role)
                if not isinstance(variant, Mapping):
                    continue
                artifact = variant.get("artifact")
                if not isinstance(artifact, Mapping):
                    continue
                if artifact.get("artifact_id"):
                    output["task_ids"].add(str(artifact["artifact_id"]))
                corpus = artifact.get("public_corpus")
                evidence = corpus.get("evidence", ()) if isinstance(corpus, Mapping) else ()
                for item in evidence:
                    if not isinstance(item, Mapping):
                        continue
                    if item.get("evidence_id"):
                        output["evidence_ids"].add(str(item["evidence_id"]))
                    if item.get("evidence_version_id"):
                        output["evidence_version_ids"].add(str(item["evidence_version_id"]))
    return output


def _load_prior_confirmation_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"report_id", "confirmed_mechanism_ids", "information_geometry_authorized"}
    if not required <= set(payload):
        raise ValueError("prior mechanism Confirmation report is incomplete")
    if payload["information_geometry_authorized"] is not False:
        raise ValueError("repair incorrectly starts from an authorized prior report")
    return payload


def _contains_benchmark_content(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False).lower()
    forbidden = (
        "finqa prompt",
        "tat-qa question",
        "byteSeedxpert/finsearchcomp".lower(),
        "response_reference",
    )
    return any(item in text for item in forbidden)


def freeze_repair_selection(
    *,
    source_population_path: Path,
    source_contract_path: Path,
    source_report_path: Path,
    output_path: Path,
    run_id: str,
) -> MechanismRepairSelectionFreeze:
    if output_path.exists():
        raise ValueError("repair selection freeze is immutable")
    population = CapabilityMechanismRepairPopulation.model_validate_json(
        source_population_path.read_text(encoding="utf-8")
    )
    report = FinanceCapabilityMechanismRepairReport.model_validate_json(
        source_report_path.read_text(encoding="utf-8")
    )
    contract = FinanceCapabilityMechanismRepairContract.model_validate_json(
        source_contract_path.read_text(encoding="utf-8")
    )
    if (
        population.stage != "development"
        or contract.repair_stage != "development"
        or report.stage != "development"
    ):
        raise ValueError("repair selection freeze requires Development artifacts")
    if contract.source_population_id != population.population_id:
        raise ValueError("repair selection contract does not bind the source population")
    if report.contract_id != contract.contract_id:
        raise ValueError("repair selection report does not bind the source contract")
    if not report.all_repaired_mechanisms_passed:
        raise ValueError("both repaired mechanisms must pass before freezing")
    groups = population.groups
    values = {
        "run_id": run_id,
        "source_population_path": str(source_population_path.resolve()),
        "source_population_sha256": _sha256(source_population_path),
        "source_population_id": population.population_id,
        "source_report_path": str(source_report_path.resolve()),
        "source_report_sha256": _sha256(source_report_path),
        "source_report_id": report.report_id,
        "source_contract_path": str(source_contract_path.resolve()),
        "source_contract_sha256": _sha256(source_contract_path),
        "source_contract_id": contract.contract_id,
        "selected_mechanism_ids": REPAIRED_MECHANISM_IDS,
        "confirmation_tier_schedule": {
            item: CONFIRMATION_TIER_SCHEDULE for item in REPAIRED_MECHANISM_IDS
        },
        "excluded_task_artifact_ids": tuple(
            sorted(
                variant.artifact.artifact_id
                for group in groups
                for variant in (group.control, group.mechanism)
            )
        ),
        "excluded_group_ids": tuple(sorted(group.group_id for group in groups)),
        "excluded_evidence_ids": tuple(
            sorted(
                {
                    item.evidence_id
                    for group in groups
                    for item in group.mechanism.artifact.public_corpus.evidence
                }
            )
        ),
        "excluded_evidence_version_ids": tuple(
            sorted(
                {
                    item.evidence_version_id
                    for group in groups
                    for item in group.mechanism.artifact.public_corpus.evidence
                }
            )
        ),
        "excluded_core_semantic_signatures": tuple(
            sorted(group.core_semantic_signature for group in groups)
        ),
    }
    provisional = MechanismRepairSelectionFreeze.model_construct(freeze_id="pending", **values)
    freeze = MechanismRepairSelectionFreeze(freeze_id=repair_freeze_id(provisional), **values)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, freeze.model_dump(mode="json"))
    return freeze


def prepare_repair_contract(
    *,
    source_population_path: Path,
    source_v25_20_contract_path: Path,
    output_path: Path,
    run_id: str,
    selection_freeze_path: Path | None = None,
) -> FinanceCapabilityMechanismRepairContract:
    if output_path.exists():
        raise ValueError("mechanism repair contract is immutable")
    population = CapabilityMechanismRepairPopulation.model_validate_json(
        source_population_path.read_text(encoding="utf-8")
    )
    if not population.static_audit.ready:
        raise ValueError("mechanism repair contract lacks a passing static audit")
    source = FinanceCapabilitySupportConfirmationContract.model_validate_json(
        source_v25_20_contract_path.read_text(encoding="utf-8")
    )
    model_contracts = tuple(
        item for item in source.model_contracts if item.arm == ExplorerArm.FLASH
    )
    if len(model_contracts) != 1:
        raise ValueError("source contract does not freeze exactly one Flash model")
    freeze: MechanismRepairSelectionFreeze | None = None
    if population.stage == "confirmation":
        if selection_freeze_path is None:
            raise ValueError("repair Confirmation contract lacks a selection freeze")
        freeze = MechanismRepairSelectionFreeze.model_validate_json(
            selection_freeze_path.read_text(encoding="utf-8")
        )
        expected_freeze_identity = (
            str(selection_freeze_path.resolve()),
            _sha256(selection_freeze_path),
            freeze.freeze_id,
        )
        population_freeze_identity = (
            population.selection_freeze_path,
            population.selection_freeze_sha256,
            population.selection_freeze_id,
        )
        if population_freeze_identity != expected_freeze_identity:
            raise ValueError("repair Confirmation population selection freeze identity differs")
        if Path(freeze.source_population_path) not in {
            Path(item) for item in population.exclusion_population_paths
        }:
            raise ValueError("repair Confirmation population did not exclude Development")
    elif selection_freeze_path is not None:
        raise ValueError("repair Development cannot use a selection freeze")
    variants = tuple(
        (group, variant)
        for group in population.groups
        for variant in (group.control, group.mechanism)
    )
    tasks = tuple(variant.artifact for _, variant in variants)
    bindings = tuple(
        _make_runtime_binding(
            task,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
            source.protocol_profile,
        )
        for task in tasks
    )
    replicas = DEVELOPMENT_REPLICAS if population.stage == "development" else CONFIRMATION_REPLICAS
    tokens = {
        f"{binding.binding_id}|{replicate}": canonical_hash(
            {
                "run_id": run_id,
                "population_id": population.population_id,
                "binding_id": binding.binding_id,
                "replicate": replicate,
                "stage": population.stage,
            },
            prefix="finance_capability_mechanism_repair_rollout:",
        )
        for binding in bindings
        for replicate in range(replicas)
    }
    implementation = _implementation_manifest()
    finance_config = Path(source.finance_archive_config_path)
    values = {
        "run_id": run_id,
        "stage": (
            RuntimeResolutionStage.RESIDUAL_DEVELOPMENT
            if population.stage == "development"
            else RuntimeResolutionStage.HELDOUT_CONFIRMATION
        ),
        "repair_stage": population.stage,
        "source_population_path": str(source_population_path.resolve()),
        "source_population_sha256": _sha256(source_population_path),
        "source_population_id": population.population_id,
        "source_selection_freeze_path": (
            str(selection_freeze_path.resolve()) if selection_freeze_path else None
        ),
        "source_selection_freeze_sha256": (
            _sha256(selection_freeze_path) if selection_freeze_path else None
        ),
        "source_selection_freeze_id": freeze.freeze_id if freeze else None,
        "source_v25_20_contract_path": str(source_v25_20_contract_path.resolve()),
        "source_v25_20_contract_sha256": _sha256(source_v25_20_contract_path),
        "source_v25_20_contract_id": source.contract_id,
        "finance_archive_config_path": str(finance_config.resolve()),
        "finance_archive_config_sha256": _sha256(finance_config),
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_capability_mechanism_repair_implementation:",
        ),
        "model_contracts": model_contracts,
        "protocol_profile": source.protocol_profile,
        "tasks": tasks,
        "task_group_ids": {
            variant.artifact.artifact_id: group.group_id for group, variant in variants
        },
        "task_mechanism_ids": {
            variant.artifact.artifact_id: group.mechanism_id for group, variant in variants
        },
        "task_mechanism_tiers": {
            variant.artifact.artifact_id: group.mechanism_tier for group, variant in variants
        },
        "task_variant_roles": {
            variant.artifact.artifact_id: variant.role for _, variant in variants
        },
        "bindings": bindings,
        "replicas": replicas,
        "requested_rollout_count": len(bindings) * replicas,
        "maximum_model_tokens_per_rollout": source.maximum_model_tokens_per_rollout,
        "maximum_observation_summary_bytes": source.maximum_observation_summary_bytes,
        "maximum_public_context_bytes": source.maximum_public_context_bytes,
        "model_contract_repair_attempts": source.model_contract_repair_attempts,
        "rollout_identity_tokens": tokens,
        "next_permitted_stage": (
            "flash_repaired_mechanism_development"
            if population.stage == "development"
            else "flash_repaired_mechanism_confirmation"
        ),
    }
    provisional = FinanceCapabilityMechanismRepairContract.model_construct(
        contract_id="pending", **values
    )
    contract = FinanceCapabilityMechanismRepairContract(
        contract_id=repair_contract_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_repair_contract(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceCapabilityMechanismRepairReport:
    contract = FinanceCapabilityMechanismRepairContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_contract_inputs(contract)
    prefix = f"capability_mechanism_repair_{contract.repair_stage}"
    outcomes, discovered = _execute_stage(
        contract=cast(Any, contract),
        tasks={item.artifact_id: item for item in contract.tasks},
        bindings=contract.bindings,
        model_arm=ExplorerArm.FLASH,
        replicas=contract.replicas,
        output_dir=output_dir,
        prefix=prefix,
        workers=workers,
    )
    records = _load_records(output_dir / f"{prefix}_records.jsonl")
    terminals = _make_terminals(cast(Any, contract), records, outcomes)
    behaviors = make_mechanism_behavior_observations(
        cast(Any, contract),
        records,
        terminals,
    )
    _write_jsonl_atomic(
        output_dir / f"{prefix}_terminal_outcomes.jsonl",
        (item.model_dump(mode="json") for item in terminals),
    )
    _write_jsonl_atomic(
        output_dir / f"{prefix}_behavior_observations.jsonl",
        (item.model_dump(mode="json") for item in behaviors),
    )
    report = make_repair_report(contract, outcomes, terminals, behaviors)
    report_path = output_dir / "finance_capability_mechanism_repair_report.json"
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_json_atomic(
        output_dir / "finance_capability_mechanism_repair_manifest.json",
        {
            "contract_id": contract.contract_id,
            "report_id": report.report_id,
            "stage": contract.repair_stage,
            "runtime_stage": contract.stage,
            "discovered_models": discovered,
            "records_sha256": _sha256(output_dir / f"{prefix}_records.jsonl"),
            "report_sha256": _sha256(report_path),
            "pro_api_call_count": 0,
            "gpu_jobs": 0,
        },
    )
    return report


def make_repair_report(
    contract: FinanceCapabilityMechanismRepairContract,
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
    behaviors: Sequence[MechanismBehaviorObservation],
) -> FinanceCapabilityMechanismRepairReport:
    if not (len(outcomes) == len(terminals) == len(behaviors) == contract.requested_rollout_count):
        raise ValueError("repair report has an incomplete denominator")
    api = _rate(item.api_transport_resolved for item in terminals)
    bounded = _rate(item.bounded_json_resolution_success for item in terminals)
    replay = _rate(item.observation_replay_success for item in terminals)
    authority = _rate(item.authority_integrity_success for item in terminals)
    pathology = _rate(item.runtime_pathology for item in terminals)
    runtime_passed = (
        api >= 0.98
        and bounded >= 0.95
        and replay >= 0.98
        and authority >= 0.98
        and pathology <= 0.02
    )
    decisions_by_id = {
        item.mechanism_id: item
        for item in _selection_decisions(cast(Any, contract), behaviors, runtime_passed)
        if item.mechanism_id in REPAIRED_MECHANISM_IDS
    }
    if set(decisions_by_id) != set(REPAIRED_MECHANISM_IDS):
        raise ValueError("repair report lacks a preregistered mechanism decision")
    decisions = tuple(decisions_by_id[item] for item in REPAIRED_MECHANISM_IDS)
    selected = tuple(item.mechanism_id for item in decisions if item.selected_for_confirmation)
    all_repaired = selected == REPAIRED_MECHANISM_IDS
    population = CapabilityMechanismRepairPopulation.model_validate_json(
        Path(contract.source_population_path).read_text(encoding="utf-8")
    )
    combined = (
        contract.repair_stage == "confirmation"
        and all_repaired
        and population.prior_confirmed_mechanism_ids == PRIOR_CONFIRMED_MECHANISM_IDS
    )
    failures: list[str] = []
    if not runtime_passed:
        failures.append("flash_runtime_qualification_failed")
    failures.extend(
        f"repaired_mechanism_not_confirmed:{item.mechanism_id}"
        for item in decisions
        if not item.selected_for_confirmation
    )
    if not runtime_passed:
        next_stage = "runtime_measurement_repair_only"
    elif contract.repair_stage == "development":
        next_stage = (
            "freeze_repaired_mechanism_selection" if all_repaired else "mechanism_task_repair_only"
        )
    else:
        next_stage = (
            "flash_mechanism_information_geometry" if combined else "mechanism_task_repair_only"
        )
    eligible = tuple(item for item in terminals if item.runtime_eligible_for_capability_denominator)
    values = {
        "contract_id": contract.contract_id,
        "stage": contract.repair_stage,
        "requested_rollout_count": contract.requested_rollout_count,
        "recorded_rollout_count": len(outcomes),
        "runtime_eligible_rollout_count": len(eligible),
        "api_transport_resolution_rate": api,
        "bounded_json_resolution_rate": bounded,
        "observation_replay_rate": replay,
        "authority_integrity_rate": authority,
        "runtime_pathology_rate": pathology,
        "semantic_accuracy_given_runtime_eligible": _rate(
            item.semantic_answer_correct for item in eligible
        ),
        "end_to_end_valid_success_rate": _rate(item.valid_success for item in outcomes),
        "selection_decisions": decisions,
        "selected_or_confirmed_mechanism_ids": selected,
        "all_repaired_mechanisms_passed": all_repaired,
        "prior_confirmed_mechanism_ids": population.prior_confirmed_mechanism_ids,
        "all_information_geometry_mechanisms_confirmed": combined,
        "information_geometry_authorized": combined,
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "failure_codes": tuple(failures),
        "next_permitted_stage": next_stage,
    }
    provisional = FinanceCapabilityMechanismRepairReport.model_construct(
        report_id="pending", **values
    )
    return FinanceCapabilityMechanismRepairReport(report_id=repair_report_id(provisional), **values)


def _verify_contract_inputs(
    contract: FinanceCapabilityMechanismRepairContract,
) -> None:
    pairs = (
        (contract.source_population_path, contract.source_population_sha256),
        (contract.source_v25_20_contract_path, contract.source_v25_20_contract_sha256),
        (contract.finance_archive_config_path, contract.finance_archive_config_sha256),
    )
    for path_value, expected in pairs:
        if _sha256(Path(path_value)) != expected:
            raise ValueError(f"repair contract frozen input changed:{path_value}")
    population = CapabilityMechanismRepairPopulation.model_validate_json(
        Path(contract.source_population_path).read_text(encoding="utf-8")
    )
    if (
        population.population_id != contract.source_population_id
        or population.stage != contract.repair_stage
    ):
        raise ValueError("repair contract population identity or stage differs")
    source = FinanceCapabilitySupportConfirmationContract.model_validate_json(
        Path(contract.source_v25_20_contract_path).read_text(encoding="utf-8")
    )
    if source.contract_id != contract.source_v25_20_contract_id:
        raise ValueError("repair source runtime contract identity differs")
    if contract.source_selection_freeze_path is not None:
        freeze_path = Path(contract.source_selection_freeze_path)
        if _sha256(freeze_path) != contract.source_selection_freeze_sha256:
            raise ValueError("repair selection freeze changed after contract creation")
        freeze = MechanismRepairSelectionFreeze.model_validate_json(
            freeze_path.read_text(encoding="utf-8")
        )
        expected_freeze_identity = (
            str(freeze_path.resolve()),
            contract.source_selection_freeze_sha256,
            freeze.freeze_id,
        )
        if contract.source_selection_freeze_id != freeze.freeze_id:
            raise ValueError("repair contract selection freeze identity differs")
        if (
            population.selection_freeze_path,
            population.selection_freeze_sha256,
            population.selection_freeze_id,
        ) != expected_freeze_identity:
            raise ValueError("repair population and contract selection freeze differ")
    implementation = _implementation_manifest()
    if implementation != contract.implementation_manifest:
        raise ValueError("repair implementation changed after contract freeze")


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        Path(__file__).resolve(),
        Path(__file__).with_name("phase1_capability_boundary.py"),
        Path(__file__).with_name("phase1_capability_boundary_runner.py"),
        Path(__file__).with_name("phase1_capability_mechanism_flash_development.py"),
        root / "src/trusted_synthesis/domains/finance/agent_tools.py",
        root / "src/trusted_synthesis/domains/finance/interactive_agent_runtime.py",
        root / "src/trusted_synthesis/domains/finance/iterative_agent_verifier.py",
        root / "src/trusted_synthesis/runtime/agent/iterative.py",
    )
    return {str(path.relative_to(root)): _sha256(path) for path in sorted(paths)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, value: Any) -> None:
    _write_text_atomic(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl_atomic(path: Path, rows: Sequence[Any] | Any) -> None:
    _write_text_atomic(
        path,
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in rows),
    )


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fail-closed v25.22 Verification/Stopping repair experiment."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-population")
    build.add_argument("--stage", choices=("development", "confirmation"), required=True)
    build.add_argument("--source-artifacts", type=Path, required=True)
    build.add_argument("--prior-confirmation-report", type=Path, required=True)
    build.add_argument("--exclude-population", type=Path, action="append", required=True)
    build.add_argument("--selection-freeze", type=Path)
    build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument("--run-id", required=True)
    build.add_argument("--sampling-salt", required=True)

    freeze = subparsers.add_parser("freeze-selection")
    freeze.add_argument("--source-population", type=Path, required=True)
    freeze.add_argument("--source-contract", type=Path, required=True)
    freeze.add_argument("--source-report", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--run-id", required=True)

    prepare = subparsers.add_parser("prepare-contract")
    prepare.add_argument("--source-population", type=Path, required=True)
    prepare.add_argument("--source-v25-20-contract", type=Path, required=True)
    prepare.add_argument("--selection-freeze", type=Path)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)

    run = subparsers.add_parser("run")
    run.add_argument("--contract", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "build-population":
        population = build_repair_population(
            stage=cast(RepairStage, args.stage),
            source_artifacts_path=args.source_artifacts,
            prior_confirmation_report_path=args.prior_confirmation_report,
            exclusion_population_paths=tuple(args.exclude_population),
            output_dir=args.output_dir,
            run_id=args.run_id,
            sampling_salt=args.sampling_salt,
            selection_freeze_path=args.selection_freeze,
        )
        print(
            json.dumps(
                {
                    "population_id": population.population_id,
                    "stage": population.stage,
                    "group_count": len(population.groups),
                    "ready": population.static_audit.ready,
                    "next_permitted_stage": population.next_permitted_stage,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif args.command == "freeze-selection":
        freeze = freeze_repair_selection(
            source_population_path=args.source_population,
            source_contract_path=args.source_contract,
            source_report_path=args.source_report,
            output_path=args.output,
            run_id=args.run_id,
        )
        print(
            json.dumps(
                {
                    "freeze_id": freeze.freeze_id,
                    "selected_mechanism_ids": freeze.selected_mechanism_ids,
                    "next_permitted_stage": freeze.next_permitted_stage,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif args.command == "prepare-contract":
        contract = prepare_repair_contract(
            source_population_path=args.source_population,
            source_v25_20_contract_path=args.source_v25_20_contract,
            selection_freeze_path=args.selection_freeze,
            output_path=args.output,
            run_id=args.run_id,
        )
        print(
            json.dumps(
                {
                    "contract_id": contract.contract_id,
                    "stage": contract.repair_stage,
                    "runtime_stage": contract.stage,
                    "task_count": len(contract.tasks),
                    "requested_rollout_count": contract.requested_rollout_count,
                    "next_permitted_stage": contract.next_permitted_stage,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        report = run_repair_contract(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        print(
            json.dumps(
                {
                    "report_id": report.report_id,
                    "stage": report.stage,
                    "recorded_rollout_count": report.recorded_rollout_count,
                    "confirmed_mechanism_ids": (report.selected_or_confirmed_mechanism_ids),
                    "information_geometry_authorized": (report.information_geometry_authorized),
                    "next_permitted_stage": report.next_permitted_stage,
                },
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
