from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
    RuntimeTaskBinding,
    _make_runtime_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    CapabilityRolloutOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_development import (
    CapabilityMechanismDevelopmentPopulation,
    _answer_contract_passes,
    _benchmark_isolated,
    _candidate_iterator,
    _CapabilityTaskBuilder,
    _CoreSelection,
    _executable_mechanism_support,
    _load_evidence_pool,
    _matched_contract_passes,
    _matched_intervention_passes,
    _materialize_group,
    _select_mechanism_distractors,
    _sha256,
    _variant_contract_failures,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_flash_development import (  # noqa: E501
    FinanceCapabilityMechanismFlashReport,
    MechanismBehaviorObservation,
    MechanismSelectionDecision,
    _make_terminals,
    _rate,
    _selection_decisions,
    make_mechanism_behavior_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_flash_development import (  # noqa: E501
    _implementation_manifest as _development_implementation_manifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_ir import (
    CORE_FAMILY_BY_MECHANISM,
    MechanismDevelopmentGroup,
    MechanismTier,
    evaluate_mutation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_reanalysis import (
    FinanceCapabilityMechanismReanalysisManifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
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

MECHANISM_SELECTION_FREEZE_VERSION = "finance_capability_mechanism_selection_freeze.v1"
MECHANISM_CONFIRMATION_POPULATION_VERSION = (
    "finance_capability_mechanism_confirmation_population.v1"
)
MECHANISM_CONFIRMATION_AUDIT_VERSION = "finance_capability_mechanism_confirmation_audit.v1"
MECHANISM_CONFIRMATION_CONTRACT_VERSION = "finance_capability_mechanism_confirmation_contract.v1"
MECHANISM_CONFIRMATION_REPORT_VERSION = "finance_capability_mechanism_confirmation_report.v1"

CONFIRMATION_GROUPS_PER_MECHANISM = 5
CONFIRMATION_REPLICAS = 5
CONFIRMATION_TIER_SCHEDULE: tuple[MechanismTier, ...] = (
    "bridge",
    "bridge",
    "frontier",
    "frontier",
    "frontier",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MechanismSelectionFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_development_population_path: str = Field(min_length=1)
    source_development_population_sha256: str = Field(min_length=64, max_length=64)
    source_development_population_id: str = Field(min_length=1)
    source_development_contract_path: str = Field(min_length=1)
    source_development_contract_sha256: str = Field(min_length=64, max_length=64)
    source_development_contract_id: str = Field(min_length=1)
    source_reanalysis_manifest_path: str = Field(min_length=1)
    source_reanalysis_manifest_sha256: str = Field(min_length=64, max_length=64)
    source_reanalysis_manifest_id: str = Field(min_length=1)
    source_corrected_report_path: str = Field(min_length=1)
    source_corrected_report_sha256: str = Field(min_length=64, max_length=64)
    source_corrected_report_id: str = Field(min_length=1)
    selected_mechanism_ids: tuple[str, ...] = Field(min_length=1)
    tier_schedule: dict[str, tuple[MechanismTier, ...]]
    excluded_task_artifact_ids: tuple[str, ...] = Field(min_length=1)
    excluded_group_ids: tuple[str, ...] = Field(min_length=1)
    excluded_evidence_ids: tuple[str, ...] = Field(min_length=1)
    excluded_evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    excluded_core_semantic_signatures: tuple[str, ...] = Field(min_length=1)
    excluded_mechanism_signatures: tuple[str, ...] = Field(min_length=1)
    confirmation_response_access: Literal["forbidden"] = "forbidden"
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    next_permitted_stage: Literal["fresh_mechanism_confirmation_population"] = (
        "fresh_mechanism_confirmation_population"
    )
    schema_version: str = MECHANISM_SELECTION_FREEZE_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> MechanismSelectionFreeze:
        if set(self.tier_schedule) != set(self.selected_mechanism_ids):
            raise ValueError("mechanism freeze schedule differs from selection")
        if any(value != CONFIRMATION_TIER_SCHEDULE for value in self.tier_schedule.values()):
            raise ValueError("mechanism freeze changes the preregistered Confirmation schedule")
        for values in (
            self.excluded_task_artifact_ids,
            self.excluded_group_ids,
            self.excluded_evidence_ids,
            self.excluded_evidence_version_ids,
            self.excluded_core_semantic_signatures,
            self.excluded_mechanism_signatures,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("mechanism freeze exclusions are not canonical")
        if self.freeze_id != selection_freeze_id(self):
            raise ValueError("mechanism selection freeze identity is invalid")
        return self


class MechanismConfirmationStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    selected_mechanism_ids: tuple[str, ...] = Field(min_length=1)
    group_count: int = Field(ge=1)
    mechanism_group_counts: dict[str, int]
    mechanism_tier_counts: dict[str, dict[MechanismTier, int]]
    operation_replay_pass_rate: float = Field(ge=0, le=1)
    matched_contract_pass_rate: float = Field(ge=0, le=1)
    matched_intervention_pass_rate: float = Field(ge=0, le=1)
    mechanism_support_pass_rate: float = Field(ge=0, le=1)
    answer_contract_pass_rate: float = Field(ge=0, le=1)
    mutation_detection_rate: float = Field(ge=0, le=1)
    within_confirmation_evidence_disjoint: bool
    development_task_disjoint: bool
    development_group_disjoint: bool
    development_evidence_disjoint: bool
    development_evidence_version_disjoint: bool
    development_semantic_disjoint: bool
    development_mechanism_signature_disjoint: bool
    benchmark_content_isolation_passed: bool
    rejection_reasons: tuple[str, ...]
    confirmation_ready: bool
    next_permitted_stage: Literal[
        "flash_mechanism_fresh_confirmation",
        "mechanism_confirmation_population_repair_only",
    ]
    schema_version: str = MECHANISM_CONFIRMATION_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> MechanismConfirmationStaticAudit:
        ready = not self.rejection_reasons
        if self.confirmation_ready != ready:
            raise ValueError("mechanism Confirmation readiness is inconsistent")
        expected = (
            "flash_mechanism_fresh_confirmation"
            if ready
            else "mechanism_confirmation_population_repair_only"
        )
        if self.next_permitted_stage != expected:
            raise ValueError("mechanism Confirmation transition is not fail-closed")
        if self.audit_id != confirmation_audit_id(self):
            raise ValueError("mechanism Confirmation audit identity is invalid")
        return self


class CapabilityMechanismConfirmationPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_selection_freeze_path: str = Field(min_length=1)
    source_selection_freeze_sha256: str = Field(min_length=64, max_length=64)
    source_selection_freeze_id: str = Field(min_length=1)
    source_artifacts_path: str = Field(min_length=1)
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    sampling_salt: str = Field(min_length=1)
    selected_mechanism_ids: tuple[str, ...] = Field(min_length=1)
    groups: tuple[MechanismDevelopmentGroup, ...] = Field(min_length=5)
    static_audit: MechanismConfirmationStaticAudit
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    next_permitted_stage: Literal[
        "flash_mechanism_fresh_confirmation",
        "mechanism_confirmation_population_repair_only",
    ]
    schema_version: str = MECHANISM_CONFIRMATION_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> CapabilityMechanismConfirmationPopulation:
        freeze = MechanismSelectionFreeze.model_validate_json(
            Path(self.source_selection_freeze_path).read_text(encoding="utf-8")
        )
        expected = make_confirmation_static_audit(self.groups, freeze)
        if self.selected_mechanism_ids != freeze.selected_mechanism_ids:
            raise ValueError("Confirmation population changes frozen mechanisms")
        if self.static_audit != expected:
            raise ValueError("Confirmation static audit differs from frozen groups")
        if self.next_permitted_stage != expected.next_permitted_stage:
            raise ValueError("Confirmation population stage differs from its audit")
        if self.population_id != confirmation_population_id(self):
            raise ValueError("Confirmation population identity is invalid")
        return self

    @property
    def tasks(self) -> tuple[CapabilitySensitiveTaskArtifact, ...]:
        return tuple(
            variant.artifact
            for group in self.groups
            for variant in (group.control, group.mechanism)
        )


class FinanceCapabilityMechanismConfirmationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    stage: RuntimeResolutionStage = RuntimeResolutionStage.HELDOUT_CONFIRMATION
    source_population_path: str = Field(min_length=1)
    source_population_sha256: str = Field(min_length=64, max_length=64)
    source_population_id: str = Field(min_length=1)
    source_v25_20_contract_path: str = Field(min_length=1)
    source_v25_20_contract_sha256: str = Field(min_length=64, max_length=64)
    source_v25_20_contract_id: str = Field(min_length=1)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(min_length=1, max_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    tasks: tuple[CapabilitySensitiveTaskArtifact, ...] = Field(min_length=10)
    task_group_ids: dict[str, str]
    task_mechanism_ids: dict[str, str]
    task_mechanism_tiers: dict[str, MechanismTier]
    task_variant_roles: dict[str, Literal["resolved_control", "mechanism_required"]]
    bindings: tuple[RuntimeTaskBinding, ...] = Field(min_length=10)
    replicas: Literal[5] = 5
    requested_rollout_count: int = Field(ge=50)
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
    next_permitted_stage: Literal["flash_mechanism_fresh_confirmation"] = (
        "flash_mechanism_fresh_confirmation"
    )
    schema_version: str = MECHANISM_CONFIRMATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceCapabilityMechanismConfirmationContract:
        if self.stage != RuntimeResolutionStage.HELDOUT_CONFIRMATION:
            raise ValueError("mechanism Confirmation must be held out")
        if {item.arm for item in self.model_contracts} != {ExplorerArm.FLASH}:
            raise ValueError("mechanism Confirmation is Flash-only")
        if self.requested_rollout_count != len(self.bindings) * self.replicas:
            raise ValueError("mechanism Confirmation denominator is inconsistent")
        task_ids = {item.artifact_id for item in self.tasks}
        if {item.task_artifact_id for item in self.bindings} != task_ids:
            raise ValueError("mechanism Confirmation binding scope is incomplete")
        if any(
            set(item) != task_ids
            for item in (
                self.task_group_ids,
                self.task_mechanism_ids,
                self.task_mechanism_tiers,
                self.task_variant_roles,
            )
        ):
            raise ValueError("mechanism Confirmation metadata maps are incomplete")
        if self.contract_id != confirmation_contract_id(self):
            raise ValueError("mechanism Confirmation contract identity is invalid")
        return self


class FinanceCapabilityMechanismConfirmationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
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
    selection_decisions: tuple[MechanismSelectionDecision, ...] = Field(min_length=1)
    confirmed_mechanism_ids: tuple[str, ...]
    runtime_qualification_passed: bool
    all_frozen_mechanisms_confirmed: bool
    information_geometry_authorized: bool
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    failure_codes: tuple[str, ...]
    next_permitted_stage: Literal[
        "flash_mechanism_information_geometry",
        "mechanism_confirmation_or_task_repair_only",
        "runtime_measurement_repair_only",
    ]
    schema_version: str = MECHANISM_CONFIRMATION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceCapabilityMechanismConfirmationReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("mechanism Confirmation lacks its complete denominator")
        if self.information_geometry_authorized != (
            self.runtime_qualification_passed and self.all_frozen_mechanisms_confirmed
        ):
            raise ValueError("mechanism information authorization is inconsistent")
        expected = (
            "runtime_measurement_repair_only"
            if not self.runtime_qualification_passed
            else (
                "flash_mechanism_information_geometry"
                if self.all_frozen_mechanisms_confirmed
                else "mechanism_confirmation_or_task_repair_only"
            )
        )
        if self.next_permitted_stage != expected:
            raise ValueError("mechanism Confirmation report is not fail-closed")
        if self.report_id != confirmation_report_id(self):
            raise ValueError("mechanism Confirmation report identity is invalid")
        return self


def selection_freeze_id(value: MechanismSelectionFreeze) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"freeze_id"}),
        prefix="finance_capability_mechanism_selection_freeze:",
    )


def confirmation_audit_id(value: MechanismConfirmationStaticAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_capability_mechanism_confirmation_audit:",
    )


def confirmation_population_id(value: CapabilityMechanismConfirmationPopulation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"population_id"}),
        prefix="finance_capability_mechanism_confirmation_population:",
    )


def confirmation_contract_id(value: FinanceCapabilityMechanismConfirmationContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_capability_mechanism_confirmation_contract:",
    )


def confirmation_report_id(value: FinanceCapabilityMechanismConfirmationReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_capability_mechanism_confirmation_report:",
    )


def freeze_mechanism_selection(
    *,
    development_population_path: Path,
    development_contract_path: Path,
    reanalysis_manifest_path: Path,
    output_path: Path,
    run_id: str,
) -> MechanismSelectionFreeze:
    if output_path.exists():
        raise ValueError("mechanism selection freeze is immutable")
    population = CapabilityMechanismDevelopmentPopulation.model_validate_json(
        development_population_path.read_text(encoding="utf-8")
    )
    manifest = FinanceCapabilityMechanismReanalysisManifest.model_validate_json(
        reanalysis_manifest_path.read_text(encoding="utf-8")
    )
    report_path = Path(manifest.corrected_report_path)
    report = FinanceCapabilityMechanismFlashReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    if (
        not report.mechanism_selection_freeze_authorized
        or report.next_permitted_stage != "fresh_mechanism_confirmation_preparation"
    ):
        raise ValueError("Development report does not authorize mechanism freezing")
    if manifest.source_contract_path != str(development_contract_path.resolve()):
        raise ValueError("selection freeze reanalysis belongs to another contract")
    tasks = tuple(population.tasks)
    evidence = tuple(item for task in tasks for item in task.public_corpus.evidence)
    mechanism_signatures = tuple(
        signature
        for group in population.groups
        for signature in (
            group.group_hash,
            group.control.contract_hash,
            group.mechanism.contract_hash,
        )
    )
    values = {
        "run_id": run_id,
        "source_development_population_path": str(development_population_path.resolve()),
        "source_development_population_sha256": _sha256(development_population_path),
        "source_development_population_id": population.population_id,
        "source_development_contract_path": str(development_contract_path.resolve()),
        "source_development_contract_sha256": _sha256(development_contract_path),
        "source_development_contract_id": report.contract_id,
        "source_reanalysis_manifest_path": str(reanalysis_manifest_path.resolve()),
        "source_reanalysis_manifest_sha256": _sha256(reanalysis_manifest_path),
        "source_reanalysis_manifest_id": manifest.manifest_id,
        "source_corrected_report_path": str(report_path.resolve()),
        "source_corrected_report_sha256": _sha256(report_path),
        "source_corrected_report_id": report.report_id,
        "selected_mechanism_ids": report.selected_mechanism_ids,
        "tier_schedule": {
            mechanism_id: CONFIRMATION_TIER_SCHEDULE
            for mechanism_id in report.selected_mechanism_ids
        },
        "excluded_task_artifact_ids": tuple(sorted({item.artifact_id for item in tasks})),
        "excluded_group_ids": tuple(sorted(item.group_id for item in population.groups)),
        "excluded_evidence_ids": tuple(
            sorted({*population.excluded_evidence_ids, *(item.evidence_id for item in evidence)})
        ),
        "excluded_evidence_version_ids": tuple(
            sorted(
                {
                    *population.excluded_evidence_version_ids,
                    *(item.evidence_version_id for item in evidence),
                }
            )
        ),
        "excluded_core_semantic_signatures": tuple(
            sorted(
                {
                    *population.excluded_semantic_signatures,
                    *(item.core_semantic_signature for item in population.groups),
                }
            )
        ),
        "excluded_mechanism_signatures": tuple(sorted(set(mechanism_signatures))),
    }
    provisional = MechanismSelectionFreeze.model_construct(freeze_id="pending", **values)
    result = MechanismSelectionFreeze(freeze_id=selection_freeze_id(provisional), **values)
    _write_json_atomic(output_path, result.model_dump(mode="json"))
    return result


def build_confirmation_population(
    *,
    selection_freeze_path: Path,
    output_dir: Path,
    source_artifacts_path: Path | None = None,
    run_id: str,
    sampling_salt: str,
) -> CapabilityMechanismConfirmationPopulation:
    output_path = output_dir / "finance_capability_mechanism_confirmation_population.json"
    if output_path.exists():
        raise ValueError("mechanism Confirmation population is immutable")
    freeze = MechanismSelectionFreeze.model_validate_json(
        selection_freeze_path.read_text(encoding="utf-8")
    )
    development = CapabilityMechanismDevelopmentPopulation.model_validate_json(
        Path(freeze.source_development_population_path).read_text(encoding="utf-8")
    )
    source_artifacts = (
        source_artifacts_path.resolve()
        if source_artifacts_path is not None
        else Path(development.source_artifacts_path)
    )
    pool = _load_evidence_pool(source_artifacts)
    builder = _CapabilityTaskBuilder(pool, sampling_salt=sampling_salt)
    used_ids = set(freeze.excluded_evidence_ids)
    used_versions = set(freeze.excluded_evidence_version_ids)
    groups: list[MechanismDevelopmentGroup] = []
    for mechanism_id in freeze.selected_mechanism_ids:
        family = CORE_FAMILY_BY_MECHANISM[mechanism_id]
        for local_index, tier in enumerate(freeze.tier_schedule[mechanism_id]):
            group_index = 100 + local_index
            preferred = (
                DifficultyTier.FRONTIER if tier == "frontier" else DifficultyTier.EASY_CONTROL
            )
            planned: tuple[_CoreSelection, tuple[Any, ...]] | None = None
            for source_tier in (preferred, DifficultyTier.EASY_CONTROL):
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
                            tuple(pool.public.values()),
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
                    f"fresh Evidence cannot support {mechanism_id}/{tier}/{local_index}"
                )
            selection, distractors = planned
            group = _materialize_group(builder, selection, cast(tuple[Any, ...], distractors))
            if group.core_semantic_signature in freeze.excluded_core_semantic_signatures:
                raise ValueError("Confirmation core semantics overlap Development")
            groups.append(group)
            for item in (*selection.gold, *distractors):
                used_ids.add(item.evidence_id)
                used_versions.add(item.evidence_version_id)
    audit = make_confirmation_static_audit(tuple(groups), freeze)
    values = {
        "run_id": run_id,
        "source_selection_freeze_path": str(selection_freeze_path.resolve()),
        "source_selection_freeze_sha256": _sha256(selection_freeze_path),
        "source_selection_freeze_id": freeze.freeze_id,
        "source_artifacts_path": str(source_artifacts.resolve()),
        "source_artifacts_sha256": _sha256(source_artifacts),
        "sampling_salt": sampling_salt,
        "selected_mechanism_ids": freeze.selected_mechanism_ids,
        "groups": tuple(groups),
        "static_audit": audit,
        "next_permitted_stage": audit.next_permitted_stage,
    }
    provisional = CapabilityMechanismConfirmationPopulation.model_construct(
        population_id="pending", **values
    )
    result = CapabilityMechanismConfirmationPopulation(
        population_id=confirmation_population_id(provisional), **values
    )
    _write_json_atomic(output_path, result.model_dump(mode="json"))
    _write_json_atomic(
        output_dir / "finance_capability_mechanism_confirmation_static_audit.json",
        audit.model_dump(mode="json"),
    )
    return result


def make_confirmation_static_audit(
    groups: tuple[MechanismDevelopmentGroup, ...],
    freeze: MechanismSelectionFreeze,
) -> MechanismConfirmationStaticAudit:
    variants = tuple(v for group in groups for v in (group.control, group.mechanism))
    evidence_sets = tuple(
        {item.evidence_id for item in group.mechanism.artifact.public_corpus.evidence}
        for group in groups
    )
    all_evidence = tuple(
        item for group in groups for item in group.mechanism.artifact.public_corpus.evidence
    )
    signatures = tuple(
        value
        for group in groups
        for value in (group.group_hash, group.control.contract_hash, group.mechanism.contract_hash)
    )
    mutation_results = tuple(
        evaluate_mutation(group.mechanism, mutation)
        for group in groups
        for mutation in group.mutations
    )
    group_counts = Counter(item.mechanism_id for item in groups)
    tier_counts = {
        mechanism_id: dict(
            Counter(item.mechanism_tier for item in groups if item.mechanism_id == mechanism_id)
        )
        for mechanism_id in freeze.selected_mechanism_ids
    }
    checks = {
        "group_quota_mismatch": all(
            group_counts[item] == CONFIRMATION_GROUPS_PER_MECHANISM
            for item in freeze.selected_mechanism_ids
        )
        and len(groups) == len(freeze.selected_mechanism_ids) * CONFIRMATION_GROUPS_PER_MECHANISM,
        "tier_schedule_mismatch": all(
            tuple(item.mechanism_tier for item in groups if item.mechanism_id == mechanism_id)
            == freeze.tier_schedule[mechanism_id]
            for mechanism_id in freeze.selected_mechanism_ids
        ),
        "operation_replay_failed": all(item.artifact.verification.passed for item in variants),
        "matched_contract_failed": all(_matched_contract_passes(item) for item in groups),
        "matched_intervention_failed": all(_matched_intervention_passes(item) for item in groups),
        "mechanism_support_failed": all(
            not _variant_contract_failures(item.mechanism) and _executable_mechanism_support(item)
            for item in groups
        ),
        "answer_contract_failed": all(_answer_contract_passes(item) for item in variants),
        "mutation_escaped": all(item.detected for item in mutation_results),
        "within_confirmation_evidence_overlap": all(
            not left & right
            for index, left in enumerate(evidence_sets)
            for right in evidence_sets[index + 1 :]
        ),
        "development_task_overlap": not {item.artifact.artifact_id for item in variants}
        & set(freeze.excluded_task_artifact_ids),
        "development_group_overlap": not {item.group_id for item in groups}
        & set(freeze.excluded_group_ids),
        "development_evidence_overlap": not {item.evidence_id for item in all_evidence}
        & set(freeze.excluded_evidence_ids),
        "development_evidence_version_overlap": not {
            item.evidence_version_id for item in all_evidence
        }
        & set(freeze.excluded_evidence_version_ids),
        "development_semantic_overlap": not {item.core_semantic_signature for item in groups}
        & set(freeze.excluded_core_semantic_signatures),
        "development_mechanism_signature_overlap": not set(signatures)
        & set(freeze.excluded_mechanism_signatures),
        "benchmark_content_detected": all(_benchmark_isolated(item) for item in variants),
    }
    rejections = tuple(sorted(code for code, passed in checks.items() if not passed))
    values = {
        "selected_mechanism_ids": freeze.selected_mechanism_ids,
        "group_count": len(groups),
        "mechanism_group_counts": dict(group_counts),
        "mechanism_tier_counts": tier_counts,
        "operation_replay_pass_rate": _rate(item.artifact.verification.passed for item in variants),
        "matched_contract_pass_rate": _rate(_matched_contract_passes(item) for item in groups),
        "matched_intervention_pass_rate": _rate(
            _matched_intervention_passes(item) for item in groups
        ),
        "mechanism_support_pass_rate": _rate(
            not _variant_contract_failures(item.mechanism) and _executable_mechanism_support(item)
            for item in groups
        ),
        "answer_contract_pass_rate": _rate(_answer_contract_passes(item) for item in variants),
        "mutation_detection_rate": _rate(item.detected for item in mutation_results),
        "within_confirmation_evidence_disjoint": checks["within_confirmation_evidence_overlap"],
        "development_task_disjoint": checks["development_task_overlap"],
        "development_group_disjoint": checks["development_group_overlap"],
        "development_evidence_disjoint": checks["development_evidence_overlap"],
        "development_evidence_version_disjoint": checks["development_evidence_version_overlap"],
        "development_semantic_disjoint": checks["development_semantic_overlap"],
        "development_mechanism_signature_disjoint": checks[
            "development_mechanism_signature_overlap"
        ],
        "benchmark_content_isolation_passed": checks["benchmark_content_detected"],
        "rejection_reasons": rejections,
        "confirmation_ready": not rejections,
        "next_permitted_stage": (
            "flash_mechanism_fresh_confirmation"
            if not rejections
            else "mechanism_confirmation_population_repair_only"
        ),
    }
    provisional = MechanismConfirmationStaticAudit.model_construct(audit_id="pending", **values)
    return MechanismConfirmationStaticAudit(audit_id=confirmation_audit_id(provisional), **values)


def prepare_confirmation_contract(
    *,
    source_population_path: Path,
    source_v25_20_contract_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceCapabilityMechanismConfirmationContract:
    if output_path.exists():
        raise ValueError("mechanism Confirmation contract is immutable")
    population = CapabilityMechanismConfirmationPopulation.model_validate_json(
        source_population_path.read_text(encoding="utf-8")
    )
    source = FinanceCapabilitySupportConfirmationContract.model_validate_json(
        source_v25_20_contract_path.read_text(encoding="utf-8")
    )
    if not population.static_audit.confirmation_ready:
        raise ValueError("mechanism Confirmation lacks a passing static audit")
    model_contracts = tuple(
        item for item in source.model_contracts if item.arm == ExplorerArm.FLASH
    )
    variants = tuple(
        (group, variant)
        for group in population.groups
        for variant in (group.control, group.mechanism)
    )
    tasks = tuple(variant.artifact for _, variant in variants)
    bindings = tuple(
        _make_runtime_binding(task, CapabilityRuntimeArm.AUTONOMOUS_AGENT, source.protocol_profile)
        for task in tasks
    )
    groups = {variant.artifact.artifact_id: group.group_id for group, variant in variants}
    mechanisms = {variant.artifact.artifact_id: group.mechanism_id for group, variant in variants}
    tiers = {variant.artifact.artifact_id: group.mechanism_tier for group, variant in variants}
    roles = {variant.artifact.artifact_id: variant.role for _, variant in variants}
    tokens = {
        f"{binding.binding_id}|{replicate}": canonical_hash(
            {
                "run_id": run_id,
                "population_id": population.population_id,
                "binding_id": binding.binding_id,
                "replicate": replicate,
            },
            prefix="finance_capability_mechanism_confirmation_rollout:",
        )
        for binding in bindings
        for replicate in range(CONFIRMATION_REPLICAS)
    }
    implementation = _confirmation_implementation_manifest()
    finance_config = Path(source.finance_archive_config_path)
    values = {
        "run_id": run_id,
        "source_population_path": str(source_population_path.resolve()),
        "source_population_sha256": _sha256(source_population_path),
        "source_population_id": population.population_id,
        "source_v25_20_contract_path": str(source_v25_20_contract_path.resolve()),
        "source_v25_20_contract_sha256": _sha256(source_v25_20_contract_path),
        "source_v25_20_contract_id": source.contract_id,
        "finance_archive_config_path": str(finance_config.resolve()),
        "finance_archive_config_sha256": _sha256(finance_config),
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation, prefix="finance_capability_mechanism_confirmation_implementation:"
        ),
        "model_contracts": model_contracts,
        "protocol_profile": source.protocol_profile,
        "tasks": tasks,
        "task_group_ids": groups,
        "task_mechanism_ids": mechanisms,
        "task_mechanism_tiers": tiers,
        "task_variant_roles": roles,
        "bindings": bindings,
        "requested_rollout_count": len(bindings) * CONFIRMATION_REPLICAS,
        "maximum_model_tokens_per_rollout": source.maximum_model_tokens_per_rollout,
        "maximum_observation_summary_bytes": source.maximum_observation_summary_bytes,
        "maximum_public_context_bytes": source.maximum_public_context_bytes,
        "model_contract_repair_attempts": source.model_contract_repair_attempts,
        "rollout_identity_tokens": tokens,
    }
    provisional = FinanceCapabilityMechanismConfirmationContract.model_construct(
        contract_id="pending", **values
    )
    result = FinanceCapabilityMechanismConfirmationContract(
        contract_id=confirmation_contract_id(provisional), **values
    )
    _write_json_atomic(output_path, result.model_dump(mode="json"))
    return result


def run_confirmation(
    *, contract_path: Path, output_dir: Path, workers: int
) -> FinanceCapabilityMechanismConfirmationReport:
    contract = FinanceCapabilityMechanismConfirmationContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_confirmation_inputs(contract)
    prefix = "capability_mechanism_flash_confirmation"
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
    behaviors = make_mechanism_behavior_observations(cast(Any, contract), records, terminals)
    _write_jsonl_atomic(
        output_dir / f"{prefix}_terminal_outcomes.jsonl",
        (item.model_dump(mode="json") for item in terminals),
    )
    _write_jsonl_atomic(
        output_dir / f"{prefix}_behavior_observations.jsonl",
        (item.model_dump(mode="json") for item in behaviors),
    )
    report = make_confirmation_report(contract, outcomes, terminals, behaviors)
    report_path = output_dir / "finance_capability_mechanism_confirmation_report.json"
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_json_atomic(
        output_dir / "finance_capability_mechanism_confirmation_manifest.json",
        {
            "contract_id": contract.contract_id,
            "report_id": report.report_id,
            "discovered_models": discovered,
            "records_sha256": _sha256(output_dir / f"{prefix}_records.jsonl"),
            "report_sha256": _sha256(report_path),
            "pro_api_call_count": 0,
        },
    )
    return report


def make_confirmation_report(
    contract: FinanceCapabilityMechanismConfirmationContract,
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
    behaviors: Sequence[MechanismBehaviorObservation],
) -> FinanceCapabilityMechanismConfirmationReport:
    if not (len(outcomes) == len(terminals) == len(behaviors) == contract.requested_rollout_count):
        raise ValueError("mechanism Confirmation has an incomplete denominator")
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
    population = CapabilityMechanismConfirmationPopulation.model_validate_json(
        Path(contract.source_population_path).read_text(encoding="utf-8")
    )
    decisions = tuple(
        item
        for item in _selection_decisions(cast(Any, contract), behaviors, runtime_passed)
        if item.mechanism_id in population.selected_mechanism_ids
    )
    confirmed = tuple(item.mechanism_id for item in decisions if item.selected_for_confirmation)
    all_confirmed = confirmed == population.selected_mechanism_ids
    failures = []
    if not runtime_passed:
        failures.append("flash_runtime_qualification_failed")
    failures.extend(
        f"mechanism_not_confirmed:{item.mechanism_id}"
        for item in decisions
        if not item.selected_for_confirmation
    )
    eligible = tuple(item for item in terminals if item.runtime_eligible_for_capability_denominator)
    values = {
        "contract_id": contract.contract_id,
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
        "confirmed_mechanism_ids": confirmed,
        "runtime_qualification_passed": runtime_passed,
        "all_frozen_mechanisms_confirmed": all_confirmed,
        "information_geometry_authorized": runtime_passed and all_confirmed,
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "failure_codes": tuple(failures),
        "next_permitted_stage": (
            "runtime_measurement_repair_only"
            if not runtime_passed
            else (
                "flash_mechanism_information_geometry"
                if all_confirmed
                else "mechanism_confirmation_or_task_repair_only"
            )
        ),
    }
    provisional = FinanceCapabilityMechanismConfirmationReport.model_construct(
        report_id="pending", **values
    )
    return FinanceCapabilityMechanismConfirmationReport(
        report_id=confirmation_report_id(provisional), **values
    )


def _confirmation_implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = {
        **_development_implementation_manifest(),
        str(Path(__file__).resolve().relative_to(root)): _sha256(Path(__file__).resolve()),
    }
    return dict(sorted(paths.items()))


def _verify_confirmation_inputs(contract: FinanceCapabilityMechanismConfirmationContract) -> None:
    for path_value, expected in (
        (contract.source_population_path, contract.source_population_sha256),
        (contract.source_v25_20_contract_path, contract.source_v25_20_contract_sha256),
        (contract.finance_archive_config_path, contract.finance_archive_config_sha256),
    ):
        if _sha256(Path(path_value)) != expected:
            raise ValueError(f"mechanism Confirmation frozen input changed:{path_value}")
    implementation = _confirmation_implementation_manifest()
    if implementation != contract.implementation_manifest:
        raise ValueError("mechanism Confirmation implementation changed after freeze")


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl_atomic(path: Path, values: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in values),
        encoding="utf-8",
    )
    temporary.replace(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run v25.21 mechanism Selection and Confirmation.")
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--development-population", required=True, type=Path)
    freeze.add_argument("--development-contract", required=True, type=Path)
    freeze.add_argument("--reanalysis-manifest", required=True, type=Path)
    freeze.add_argument("--output-path", required=True, type=Path)
    freeze.add_argument("--run-id", required=True)
    build = commands.add_parser("build")
    build.add_argument("--selection-freeze", required=True, type=Path)
    build.add_argument("--source-artifacts", required=True, type=Path)
    build.add_argument("--output-dir", required=True, type=Path)
    build.add_argument("--run-id", required=True)
    build.add_argument("--sampling-salt", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--source-population", required=True, type=Path)
    prepare.add_argument("--source-v25-20-contract", required=True, type=Path)
    prepare.add_argument("--output-path", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    run = commands.add_parser("run")
    run.add_argument("--contract", required=True, type=Path)
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--workers", type=int, default=16)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "freeze":
        result: Any = freeze_mechanism_selection(
            development_population_path=args.development_population,
            development_contract_path=args.development_contract,
            reanalysis_manifest_path=args.reanalysis_manifest,
            output_path=args.output_path,
            run_id=args.run_id,
        )
    elif args.command == "build":
        result = build_confirmation_population(
            selection_freeze_path=args.selection_freeze,
            source_artifacts_path=args.source_artifacts,
            output_dir=args.output_dir,
            run_id=args.run_id,
            sampling_salt=args.sampling_salt,
        )
    elif args.command == "prepare":
        result = prepare_confirmation_contract(
            source_population_path=args.source_population,
            source_v25_20_contract_path=args.source_v25_20_contract,
            output_path=args.output_path,
            run_id=args.run_id,
        )
    else:
        result = run_confirmation(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
    payload = result.model_dump(mode="json")
    summary_keys = (
        "freeze_id",
        "population_id",
        "contract_id",
        "report_id",
        "selected_mechanism_ids",
        "confirmed_mechanism_ids",
        "requested_rollout_count",
        "recorded_rollout_count",
        "runtime_qualification_passed",
        "information_geometry_authorized",
        "next_permitted_stage",
    )
    summary = {key: payload[key] for key in summary_keys if key in payload}
    if "groups" in payload:
        summary["group_count"] = len(payload["groups"])
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
