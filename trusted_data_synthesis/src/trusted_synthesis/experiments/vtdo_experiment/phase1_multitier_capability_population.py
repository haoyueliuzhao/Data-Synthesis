from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.program import InputRefKind, TaskProgram
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    make_finance_typed_recovery_scenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    MAXIMUM_REQUIRED_TOOL_CALLS,
    CapabilityRuntimeArm,
    make_v25_native_runtime_context,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_SENSITIVE_FAMILIES,
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
    RecoveryBranch,
    _CapabilityTaskBuilder,
    _load_evidence_pool,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_capability_ladder import (
    MATCHED_GROUP_COUNT,
    MATCHED_GROUPS_PER_FAMILY,
    MATCHED_STATIC_RECORD_COUNT,
    MatchedLadderAudit,
    MatchedLadderGroup,
    _core_instruction,
    _public_selector_collision,
    _tier_instruction,
    core_task_semantic_signature,
    load_exposed_tasks,
    make_matched_ladder_audit,
    matched_group_invariant_failures,
    matched_ladder_group_hash,
    matched_ladder_group_id,
    signature_set_hash,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_regression import (
    ExposureContractReference,
    FinancePublicContractRegressionContract,
    FinancePublicContractRegressionReport,
    _make_exposure_contract_reference,
    load_exposed_tasks_from_references,
    resolve_regression_population_path,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_satisfiability import (
    PublicContractSatisfiabilityAudit,
    make_public_contract_audit,
    make_public_contract_record,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

MULTITIER_POPULATION_VERSION = "finance_multitier_capability_population.v2"
MULTITIER_POPULATION_AUDIT_VERSION = "finance_multitier_capability_population_audit.v1"
ANSWER_PROJECTION_CONTRACT_VERSION = "v1"
FINANCE_OPERATION_EXECUTION_CONTRACT_VERSION = "finance_operation_execution_contract.v3"

CORE_PROGRAM_TIERS: dict[str, DifficultyTier] = {
    "finance.multi_hop_retrieval_join": DifficultyTier.HARD_CONTROL,
    "finance.branching_operation_plan": DifficultyTier.EASY_CONTROL,
    "finance.calculation_chain": DifficultyTier.FRONTIER,
    "finance.definition_reconciliation": DifficultyTier.FRONTIER,
    "finance.verification_sensitive_selection": DifficultyTier.FRONTIER,
    "finance.recovery_guided_search": DifficultyTier.FRONTIER,
    "finance.stopping_decision_control": DifficultyTier.FRONTIER,
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MultiTierPopulationAudit(FrozenModel):
    matched_audit: MatchedLadderAudit
    core_program_tiers: dict[str, DifficultyTier]
    answer_projection_contract_coverage: float = Field(ge=0, le=1)
    recovery_intervention_task_count: int = Field(ge=0)
    expected_recovery_intervention_task_count: int = Field(ge=1)
    recovery_intervention_complete: bool
    stopping_scripted_primary_role: str = "secondary_diagnostic_only"
    static_record_count: int = Field(ge=1)
    multi_tier_population_ready: bool
    next_permitted_stage: str
    audit_hash: str = Field(min_length=1)
    schema_version: str = MULTITIER_POPULATION_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> MultiTierPopulationAudit:
        if set(self.core_program_tiers) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("multi-Tier core-program policy omits a family")
        expected_recovery = (
            self.recovery_intervention_task_count == self.expected_recovery_intervention_task_count
        )
        if self.recovery_intervention_complete != expected_recovery:
            raise ValueError("multi-Tier recovery intervention decision is inconsistent")
        ready = (
            self.matched_audit.matched_ladder_ready
            and self.answer_projection_contract_coverage == 1.0
            and expected_recovery
            and self.static_record_count == MATCHED_STATIC_RECORD_COUNT
        )
        if self.multi_tier_population_ready != ready:
            raise ValueError("multi-Tier population readiness is inconsistent")
        expected_stage = (
            "flash_first_multitier_confirmation" if ready else "multitier_population_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("multi-Tier population transition is not fail-closed")
        if self.audit_hash != multitier_population_audit_hash(self):
            raise ValueError("multi-Tier population audit identity is invalid")
        return self


class MultiTierCapabilityPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_artifacts_path: str = Field(min_length=1)
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    regression_contract_path: str = Field(min_length=1)
    regression_contract_sha256: str = Field(min_length=64, max_length=64)
    regression_contract_id: str = Field(min_length=1)
    regression_report_path: str = Field(min_length=1)
    regression_report_sha256: str = Field(min_length=64, max_length=64)
    regression_report_id: str = Field(min_length=1)
    additional_exposure_contract_references: tuple[ExposureContractReference, ...] = Field(
        min_length=1
    )
    excluded_core_signatures: tuple[str, ...] = Field(min_length=1)
    excluded_core_signature_set_hash: str = Field(min_length=1)
    excluded_evidence_ids: tuple[str, ...] = Field(min_length=1)
    excluded_evidence_id_set_hash: str = Field(min_length=1)
    excluded_evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    excluded_evidence_version_set_hash: str = Field(min_length=1)
    sampling_salt: str = Field(min_length=1)
    core_program_tiers: dict[str, DifficultyTier]
    protocol_profile: IterativeAgentProtocolProfile
    groups: tuple[MatchedLadderGroup, ...] = Field(
        min_length=MATCHED_GROUP_COUNT,
        max_length=MATCHED_GROUP_COUNT,
    )
    public_contract_audit: PublicContractSatisfiabilityAudit
    audit: MultiTierPopulationAudit
    model_api_calls: int = Field(default=0, ge=0, le=0)
    validation_objective_access: str = "forbidden"
    authorization_objective_access: str = "forbidden"
    exact_target_evaluated: bool = False
    gp_c_evaluated: bool = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = MULTITIER_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> MultiTierCapabilityPopulation:
        if self.schema_version != MULTITIER_POPULATION_VERSION:
            raise ValueError("multi-Tier population version is unsupported")
        if self.core_program_tiers != CORE_PROGRAM_TIERS:
            raise ValueError("multi-Tier core-program policy differs from preregistration")
        if tuple(sorted(set(self.excluded_core_signatures))) != self.excluded_core_signatures:
            raise ValueError("multi-Tier exclusion signatures are not canonical")
        if self.excluded_core_signature_set_hash != signature_set_hash(
            self.excluded_core_signatures,
            prefix="finance_multitier_excluded_core_signatures:",
        ):
            raise ValueError("multi-Tier exclusion signature hash is invalid")
        regression = FinancePublicContractRegressionContract.model_validate_json(
            Path(self.regression_contract_path).read_text(encoding="utf-8")
        )
        exposed = (
            *load_exposed_tasks(regression),
            *load_exposed_tasks_from_references(self.additional_exposure_contract_references),
        )
        if not {core_task_semantic_signature(item) for item in exposed} <= set(
            self.excluded_core_signatures
        ):
            raise ValueError("multi-Tier population omitted an immutable exposure")
        exposed_evidence_ids, exposed_version_ids = _exposed_evidence_id_sets(exposed)
        if not exposed_evidence_ids <= set(self.excluded_evidence_ids):
            raise ValueError("multi-Tier population omitted an exposed Evidence ID")
        if not exposed_version_ids <= set(self.excluded_evidence_version_ids):
            raise ValueError("multi-Tier population omitted an exposed Evidence Version")
        if self.excluded_evidence_id_set_hash != signature_set_hash(
            self.excluded_evidence_ids,
            prefix="finance_multitier_excluded_evidence_ids:",
        ):
            raise ValueError("multi-Tier Evidence exclusion hash is invalid")
        if self.excluded_evidence_version_set_hash != signature_set_hash(
            self.excluded_evidence_version_ids,
            prefix="finance_multitier_excluded_evidence_versions:",
        ):
            raise ValueError("multi-Tier Evidence Version exclusion hash is invalid")
        if any(
            evidence.evidence_id in exposed_evidence_ids
            or evidence.evidence_version_id in exposed_version_ids
            for task in self.tasks
            for evidence in task.public_corpus.evidence
        ):
            raise ValueError("multi-Tier confirmation Evidence overlaps Development")
        if len({item.group_id for item in self.groups}) != MATCHED_GROUP_COUNT:
            raise ValueError("multi-Tier population duplicates a Ladder Group")
        if len({item.core_semantic_signature for item in self.groups}) != MATCHED_GROUP_COUNT:
            raise ValueError("multi-Tier population duplicates core semantics")
        if self.public_contract_audit.population_id != self.population_id:
            raise ValueError("multi-Tier static audit belongs to another population")
        expected_audit = make_multitier_population_audit(
            self.groups,
            excluded_core_signatures=self.excluded_core_signatures,
            public_contract_audit=self.public_contract_audit,
        )
        if self.audit != expected_audit:
            raise ValueError("multi-Tier audit differs from frozen groups")
        if self.population_id != multitier_population_id(self):
            raise ValueError("multi-Tier population identity is invalid")
        return self

    @property
    def tasks(self) -> tuple[CapabilitySensitiveTaskArtifact, ...]:
        return tuple(
            sorted(
                (task for group in self.groups for task in group.variants),
                key=lambda item: (item.family, item.artifact_id),
            )
        )


def build_multitier_capability_population(
    *,
    source_artifacts_path: Path,
    regression_contract_path: Path,
    regression_report_path: Path,
    output_path: Path,
    run_id: str,
    sampling_salt: str,
    additional_exposure_contract_paths: tuple[Path, ...],
) -> MultiTierCapabilityPopulation:
    if output_path.exists():
        raise ValueError("multi-Tier population is immutable and already exists")
    if not additional_exposure_contract_paths:
        raise ValueError("v25.12 requires an explicit v25.11 exposure reference")
    source_artifacts_path = source_artifacts_path.resolve()
    regression_contract_path = regression_contract_path.resolve()
    regression_report_path = regression_report_path.resolve()
    exposure_paths = tuple(item.resolve() for item in additional_exposure_contract_paths)
    regression = FinancePublicContractRegressionContract.model_validate_json(
        regression_contract_path.read_text(encoding="utf-8")
    )
    regression_report = FinancePublicContractRegressionReport.model_validate_json(
        regression_report_path.read_text(encoding="utf-8")
    )
    if (
        regression_report.contract_id != regression.contract_id
        or regression_report.status != "passed"
        or regression_report.next_permitted_stage != "matched_ladder_construction_only"
    ):
        raise ValueError("multi-Tier population lacks a passing public regression")
    source_population = CapabilitySensitiveFrontierPopulation.model_validate_json(
        resolve_regression_population_path(regression).read_text(encoding="utf-8")
    )
    if Path(source_population.source_artifacts_path).resolve() != source_artifacts_path:
        raise ValueError("multi-Tier source artifacts differ from regression")
    if _sha256(source_artifacts_path) != source_population.source_artifacts_sha256:
        raise ValueError("multi-Tier source artifacts changed after regression")

    references = tuple(_make_exposure_contract_reference(item) for item in exposure_paths)
    exposed_tasks = (
        *load_exposed_tasks(regression),
        *load_exposed_tasks_from_references(references),
    )
    excluded = tuple(sorted({core_task_semantic_signature(item) for item in exposed_tasks}))
    exposed_evidence_ids, exposed_version_ids = _exposed_evidence_id_sets(exposed_tasks)
    evidence_pool = _load_evidence_pool(source_artifacts_path)
    blocked_evidence_ids = exposed_evidence_ids | {
        item.evidence_id
        for item in evidence_pool.public.values()
        if item.evidence_version_id in exposed_version_ids
    }
    builder = _CapabilityTaskBuilder(
        evidence_pool,
        sampling_salt=sampling_salt,
    )
    builder._used_evidence_ids.update(blocked_evidence_ids)
    groups = _build_multitier_groups(builder, excluded_signatures=set(excluded))
    protocol = regression.protocol_profile
    identity = {
        "run_id": run_id,
        "source_artifacts_sha256": _sha256(source_artifacts_path),
        "regression_contract_id": regression.contract_id,
        "regression_report_id": regression_report.report_id,
        "additional_exposure_ids": tuple(item.contract_id for item in references),
        "excluded_core_signature_set_hash": signature_set_hash(
            excluded,
            prefix="finance_multitier_excluded_core_signatures:",
        ),
        "excluded_evidence_id_set_hash": signature_set_hash(
            tuple(sorted(blocked_evidence_ids)),
            prefix="finance_multitier_excluded_evidence_ids:",
        ),
        "excluded_evidence_version_set_hash": signature_set_hash(
            tuple(sorted(exposed_version_ids)),
            prefix="finance_multitier_excluded_evidence_versions:",
        ),
        "sampling_salt": sampling_salt,
        "core_program_tiers": CORE_PROGRAM_TIERS,
        "protocol_profile_hash": protocol.profile_hash,
        "group_hashes": tuple(item.group_hash for item in groups),
    }
    population_id = canonical_hash(
        identity,
        prefix="finance_multitier_capability_population:",
    )
    records = tuple(
        make_public_contract_record(
            task=task,
            runtime_arm=cast(Any, runtime.value),
            runtime_task=context.task,
            manifest=manifest,
            maximum_required_tool_calls=MAXIMUM_REQUIRED_TOOL_CALLS,
        )
        for group in groups
        for task in group.variants
        for runtime in CapabilityRuntimeArm
        for context, manifest, _ in (make_v25_native_runtime_context(task, runtime, protocol),)
    )
    static_audit = make_public_contract_audit(
        population_id=population_id,
        records=records,
        required_runtime_arms=tuple(
            cast(Any, runtime.value) for runtime in CapabilityRuntimeArm
        ),
    )
    audit = make_multitier_population_audit(
        groups,
        excluded_core_signatures=excluded,
        public_contract_audit=static_audit,
    )
    values = {
        "run_id": run_id,
        "source_artifacts_path": str(source_artifacts_path),
        "source_artifacts_sha256": _sha256(source_artifacts_path),
        "regression_contract_path": str(regression_contract_path),
        "regression_contract_sha256": _sha256(regression_contract_path),
        "regression_contract_id": regression.contract_id,
        "regression_report_path": str(regression_report_path),
        "regression_report_sha256": _sha256(regression_report_path),
        "regression_report_id": regression_report.report_id,
        "additional_exposure_contract_references": references,
        "excluded_core_signatures": excluded,
        "excluded_core_signature_set_hash": signature_set_hash(
            excluded,
            prefix="finance_multitier_excluded_core_signatures:",
        ),
        "excluded_evidence_ids": tuple(sorted(blocked_evidence_ids)),
        "excluded_evidence_id_set_hash": signature_set_hash(
            tuple(sorted(blocked_evidence_ids)),
            prefix="finance_multitier_excluded_evidence_ids:",
        ),
        "excluded_evidence_version_ids": tuple(sorted(exposed_version_ids)),
        "excluded_evidence_version_set_hash": signature_set_hash(
            tuple(sorted(exposed_version_ids)),
            prefix="finance_multitier_excluded_evidence_versions:",
        ),
        "sampling_salt": sampling_salt,
        "core_program_tiers": CORE_PROGRAM_TIERS,
        "protocol_profile": protocol,
        "groups": groups,
        "public_contract_audit": static_audit,
        "audit": audit,
        "model_api_calls": 0,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    population = MultiTierCapabilityPopulation(
        population_id=population_id,
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, population.model_dump(mode="json"))
    return population


def _build_multitier_groups(
    builder: _CapabilityTaskBuilder,
    *,
    excluded_signatures: set[str],
    groups_per_family: int = MATCHED_GROUPS_PER_FAMILY,
    core_program_tiers: Mapping[str, DifficultyTier] = CORE_PROGRAM_TIERS,
) -> tuple[MatchedLadderGroup, ...]:
    if groups_per_family < 1:
        raise ValueError("multi-Tier group count must be positive")
    if set(core_program_tiers) != set(CAPABILITY_SENSITIVE_FAMILIES):
        raise ValueError("multi-Tier core-program policy omits a family")
    groups: list[MatchedLadderGroup] = []
    used_signatures: set[str] = set()
    used_public_ids: set[str] = set()
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        built = 0
        core_tier = core_program_tiers[family]
        candidates = (
            builder._cross_candidates(family, core_tier)
            if family == "finance.branching_operation_plan"
            else builder._temporal_candidates(family, core_tier)
        )
        for gold, program, original_instruction, answer_projection in candidates:
            gold_ids = {item.evidence_id for item in gold}
            if gold_ids & (used_public_ids | builder._used_evidence_ids):
                continue
            selected = builder._select_distractors(
                family,
                gold,
                DifficultyTier.HARD_CONTROL,
            )
            if selected is None:
                continue
            hard_distractors, hard_recovery = selected
            required_recovery = 3 if family == "finance.recovery_guided_search" else 2
            if len(hard_distractors) != 6 or len(hard_recovery) < required_recovery:
                continue
            if any(_public_selector_collision(item, gold) for item in hard_distractors):
                continue
            if {item.evidence_id for item in hard_distractors} & used_public_ids:
                continue
            frontier_recovery_count = 2 if family == "finance.recovery_guided_search" else 1
            frontier_distractors = _frontier_subset_for_recovery(
                gold,
                hard_distractors,
                required_recovery_ids={
                    item.distractor_evidence_id for item in hard_recovery[:frontier_recovery_count]
                },
            )
            if frontier_distractors is None:
                continue
            core_instruction = _core_instruction(original_instruction)
            variants = tuple(
                builder._materialize(
                    family=family,
                    tier=tier,
                    gold=gold,
                    distractors=(
                        ()
                        if tier == DifficultyTier.EASY_CONTROL
                        else (
                            frontier_distractors
                            if tier == DifficultyTier.FRONTIER
                            else hard_distractors
                        )
                    ),
                    recovery_branches=(
                        ()
                        if tier == DifficultyTier.EASY_CONTROL
                        else tuple(
                            hard_recovery[
                                : (
                                    frontier_recovery_count
                                    if tier == DifficultyTier.FRONTIER
                                    else required_recovery
                                )
                            ]
                        )
                    ),
                    program=program,
                    instruction=finance_public_calculation_instruction(
                        _tier_instruction(core_instruction, tier),
                        family=family,
                        tier=tier,
                        gold=gold,
                        program=program,
                    ),
                    answer_projection=answer_projection,
                    public_metadata=_public_contract_metadata(
                        family=family,
                        tier=tier,
                        gold=gold,
                        program=program,
                        answer_projection=answer_projection,
                        recovery_branches=(
                            ()
                            if tier == DifficultyTier.EASY_CONTROL
                            else tuple(
                                hard_recovery[
                                    : (
                                        frontier_recovery_count
                                        if tier == DifficultyTier.FRONTIER
                                        else required_recovery
                                    )
                                ]
                            )
                        ),
                    ),
                )
                for tier in DifficultyTier
            )
            signature = core_task_semantic_signature(variants[0])
            if signature in excluded_signatures or signature in used_signatures:
                continue
            if matched_group_invariant_failures(variants):
                continue
            group_values = {
                "family": family,
                "core_semantic_signature": signature,
                "core_instruction": core_instruction,
                "variants": variants,
            }
            provisional = MatchedLadderGroup.model_construct(
                group_id="pending",
                group_hash="pending",
                **group_values,
            )
            group_id = matched_ladder_group_id(provisional)
            with_id = MatchedLadderGroup.model_construct(
                group_id=group_id,
                group_hash="pending",
                **group_values,
            )
            group = MatchedLadderGroup(
                group_id=group_id,
                group_hash=matched_ladder_group_hash(with_id),
                **group_values,
            )
            groups.append(group)
            used_signatures.add(signature)
            hard_ids = {item.evidence_id for item in variants[-1].public_corpus.evidence}
            used_public_ids.update(hard_ids)
            builder._used_evidence_ids.update(hard_ids)
            built += 1
            if built == groups_per_family:
                break
        if built != groups_per_family:
            raise ValueError(
                f"real Finance Evidence supports only {built} fresh multi-Tier groups for {family}"
            )
    return tuple(sorted(groups, key=lambda item: (item.family, item.core_semantic_signature)))


def _frontier_subset_for_recovery(
    gold: tuple[Any, ...],
    hard_distractors: tuple[Any, ...],
    *,
    required_recovery_ids: set[str],
) -> tuple[Any, ...] | None:
    gold_sources = {item.source.source_id for item in gold}
    candidates = tuple(
        subset
        for subset in itertools.combinations(hard_distractors, 3)
        if required_recovery_ids <= {item.evidence_id for item in subset}
        and len(gold_sources | {item.source.source_id for item in subset}) == 2
    )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda values: canonical_hash(
            tuple(item.evidence_version_id for item in values),
            prefix="finance_multitier_frontier_subset:",
        ),
    )


def _exposed_evidence_id_sets(
    tasks: Sequence[Mapping[str, Any]],
) -> tuple[set[str], set[str]]:
    evidence_ids: set[str] = set()
    version_ids: set[str] = set()
    for task in tasks:
        corpus = task.get("public_corpus")
        if not isinstance(corpus, Mapping):
            raise ValueError("exposed task lacks a structured public Corpus")
        evidence = corpus.get("evidence")
        if not isinstance(evidence, list):
            raise ValueError("exposed task public Corpus lacks Evidence")
        for item in evidence:
            if not isinstance(item, Mapping):
                raise ValueError("exposed task contains malformed Evidence")
            evidence_id = str(item.get("evidence_id") or "")
            version_id = str(item.get("evidence_version_id") or "")
            if not evidence_id or not version_id:
                raise ValueError("exposed Evidence lacks immutable identity")
            evidence_ids.add(evidence_id)
            version_ids.add(version_id)
    if not evidence_ids or not version_ids:
        raise ValueError("exposure manifest contains no Evidence identities")
    return evidence_ids, version_ids


def _public_contract_metadata(
    *,
    family: str,
    tier: DifficultyTier,
    gold: tuple[Any, ...],
    program: TaskProgram,
    answer_projection: Mapping[str, str],
    recovery_branches: tuple[RecoveryBranch, ...],
) -> dict[str, Any]:
    allowed_labels = tuple(sorted(set(answer_projection.values())))
    guidance: dict[str, Any] = {
        "answer_reference_contract": {
            "allowed_reference_labels": allowed_labels,
            "difference_semantics": "absolute non-negative decimal copied from calculator",
        },
        "operation_execution_contract": finance_operation_execution_contract(
            family=family,
            tier=tier,
            gold=gold,
            program=program,
        ),
    }
    if allowed_labels:
        guidance["answer_field_constraints"] = {
            "higher_ref": {"allowed_values": (*allowed_labels, None)},
            "difference": {"numeric_minimum": "0"},
        }
    output_node = next(node for node in program.nodes if node.node_id == program.output_node_id)
    numeric_field = "difference" if output_node.output_schema == "comparison" else "value"
    guidance["answer_observation_constraints"] = {
        "source_tool_id": "calculator",
        "source_operation_role": "terminal",
        "source_result_selector": ("result", "output"),
        "field_selectors": {numeric_field: (numeric_field,)},
        "exact_fields": (numeric_field,),
    }
    output: dict[str, Any] = {
        "answer_projection_contract_version": ANSWER_PROJECTION_CONTRACT_VERSION,
        "agent_contract_guidance": guidance,
        "multitier_confirmation": {
            "core_program_tier": CORE_PROGRAM_TIERS[family].value,
            "observed_workflow_tier": tier.value,
        },
    }
    if family == "finance.recovery_guided_search" and recovery_branches:
        scenario = make_finance_typed_recovery_scenario(
            scope_identity=canonical_hash(
                {
                    "family": family,
                    "tier": tier.value,
                    "gold_versions": tuple(item.evidence_version_id for item in gold),
                },
                prefix="finance_multitier_recovery_scope:",
            ),
            mismatch_fields=tuple(
                sorted({field for branch in recovery_branches for field in branch.mismatch_fields})
            ),
        )
        output["typed_recovery_scenario"] = scenario.model_dump(mode="json")
    return output


def finance_public_calculation_instruction(
    instruction: str,
    *,
    family: str,
    tier: DifficultyTier,
    gold: tuple[Any, ...],
    program: TaskProgram,
) -> str:
    contract = finance_operation_execution_contract(
        family=family,
        tier=tier,
        gold=gold,
        program=program,
    )
    suffix = (
        "Use each exact signed arithmetic step disclosed by the Host as it becomes current. "
        f"The final output rule is: {contract['final_output_rule']}. Do not round."
    )
    if suffix in instruction:
        return instruction
    return f"{instruction} {suffix}"


def finance_operation_execution_contract(
    *,
    family: str,
    tier: DifficultyTier,
    gold: tuple[Any, ...],
    program: TaskProgram,
) -> dict[str, Any]:
    if family not in CAPABILITY_SENSITIVE_FAMILIES:
        raise ValueError(f"unknown Finance capability family: {family}")
    program_tier = CORE_PROGRAM_TIERS[family]
    variables = tuple(
        _finance_operation_variable(item, index) for index, item in enumerate(gold, start=1)
    )
    symbol_by_evidence_id = {
        item.evidence_id: f"v{index}" for index, item in enumerate(gold, start=1)
    }
    steps = []
    for node in program.nodes:
        inputs = tuple(
            symbol_by_evidence_id[ref.ref_id] if ref.kind == InputRefKind.EVIDENCE else ref.ref_id
            for ref in node.input_refs
        )
        selectors = tuple(ref.selector for ref in node.input_refs)
        steps.append(
            {
                "step_id": node.node_id,
                "tool_id": "calculator",
                "tool_operator": node.operator_id,
                "inputs": inputs,
                "input_selectors": selectors,
                "parameters": node.parameters,
                "expression": _public_operation_expression(
                    node.operator_id, inputs, node.parameters
                ),
                "output_schema": node.output_schema,
            }
        )
    output_node = next(node for node in program.nodes if node.node_id == program.output_node_id)
    final_rule = (
        "higher_ref plus absolute difference"
        if output_node.output_schema == "comparison"
        else f"value = {program.output_node_id}"
    )
    return {
        "contract_version": FINANCE_OPERATION_EXECUTION_CONTRACT_VERSION,
        "source_program_hash": program.program_hash,
        "observed_workflow_tier": tier.value,
        "program_semantic_tier": program_tier.value,
        "variables": variables,
        "steps": tuple(steps),
        "output_step_id": program.output_node_id,
        "strict_step_order": True,
        "step_reference_policy": (
            "execute every step in order; for an operation input copy the exact operation_ref "
            "returned by that prior successful calculator step"
        ),
        "operator_semantics": {
            "difference": "difference(left, right) = right - left",
            "growth": "growth(earlier, later) = 100 * (later - earlier) / abs(earlier)",
            "ratio": "ratio(numerator, denominator) = numerator / denominator",
            "compare": (
                "higher_ref identifies the larger input and difference is the absolute "
                "non-negative gap"
            ),
        },
        "final_output_rule": final_rule,
        "rounding_policy": "preserve the exact calculator decimal string; no rounding",
    }


def _finance_operation_variable(item: Any, index: int) -> dict[str, Any]:
    equals: list[dict[str, Any]] = [
        {"selector": ("subject", "name"), "value": item.subject.name},
        {"selector": ("metric", "predicate"), "value": item.predicate},
        {"selector": ("period",), "value": item.temporal_context.label},
        {"selector": ("source", "source_id"), "value": item.source.source_id},
        {
            "selector": ("metric", "definition_id"),
            "value": item.definition.definition_id,
        },
        {"selector": ("time_basis",), "value": item.temporal_context.basis},
        {"selector": ("frequency",), "value": item.temporal_context.frequency},
    ]
    for selector, value in (
        (("payload", "unit"), getattr(item.payload, "unit", None)),
        (("payload", "currency"), getattr(item.payload, "currency", None)),
    ):
        if value not in (None, ""):
            equals.append({"selector": selector, "value": value})
    return {
        "symbol": f"v{index}",
        "subject": item.subject.name,
        "metric": item.predicate,
        "period": item.temporal_context.label,
        "selection_match": {
            "collection_selector": ("facts",),
            "evidence_id_selector": ("evidence_id",),
            "equals": tuple(equals),
        },
    }


def _public_operation_expression(
    operator: str,
    inputs: tuple[str, ...],
    parameters: Mapping[str, Any],
) -> str:
    if operator == "difference" and len(inputs) == 2:
        return f"{inputs[1]} - {inputs[0]}"
    if operator == "ratio" and len(inputs) == 2:
        return f"{inputs[0]} / {inputs[1]}"
    if operator == "growth" and len(inputs) == 2:
        return f"100 * ({inputs[1]} - {inputs[0]}) / abs({inputs[0]})"
    if operator == "compare" and len(inputs) == 2:
        return (
            f"higher_ref = argmax({inputs[0]}, {inputs[1]}); "
            f"difference = abs({inputs[0]} - {inputs[1]})"
        )
    if operator == "aggregate":
        method = str(parameters.get("method") or "")
        return f"{method}({', '.join(inputs)})"
    if operator == "lookup" and len(inputs) == 1:
        return inputs[0]
    return f"{operator}({', '.join(inputs)})"


def make_multitier_population_audit(
    groups: tuple[MatchedLadderGroup, ...],
    *,
    excluded_core_signatures: Sequence[str],
    public_contract_audit: PublicContractSatisfiabilityAudit,
) -> MultiTierPopulationAudit:
    matched = make_matched_ladder_audit(
        groups,
        excluded_core_signatures=excluded_core_signatures,
        public_contract_audit=public_contract_audit,
    )
    tasks = tuple(task for group in groups for task in group.variants)
    projection_count = sum(
        task.task.public.metadata.get("answer_projection_contract_version")
        == ANSWER_PROJECTION_CONTRACT_VERSION
        for task in tasks
    )
    recovery_tasks = tuple(
        task
        for task in tasks
        if task.family == "finance.recovery_guided_search"
        and task.tier != DifficultyTier.EASY_CONTROL
    )
    intervention_count = sum(
        "typed_recovery_scenario" in task.task.public.metadata for task in recovery_tasks
    )
    expected_recovery = MATCHED_GROUPS_PER_FAMILY * 2
    values = {
        "matched_audit": matched,
        "core_program_tiers": CORE_PROGRAM_TIERS,
        "answer_projection_contract_coverage": projection_count / len(tasks),
        "recovery_intervention_task_count": intervention_count,
        "expected_recovery_intervention_task_count": expected_recovery,
        "recovery_intervention_complete": intervention_count == expected_recovery,
        "stopping_scripted_primary_role": "secondary_diagnostic_only",
        "static_record_count": len(public_contract_audit.records),
        "multi_tier_population_ready": (
            matched.matched_ladder_ready
            and projection_count == len(tasks)
            and intervention_count == expected_recovery
            and len(public_contract_audit.records) == MATCHED_STATIC_RECORD_COUNT
        ),
        "next_permitted_stage": (
            "flash_first_multitier_confirmation"
            if (
                matched.matched_ladder_ready
                and projection_count == len(tasks)
                and intervention_count == expected_recovery
                and len(public_contract_audit.records) == MATCHED_STATIC_RECORD_COUNT
            )
            else "multitier_population_repair_only"
        ),
    }
    provisional = MultiTierPopulationAudit.model_construct(
        audit_hash="pending",
        **values,
    )
    return MultiTierPopulationAudit(
        audit_hash=multitier_population_audit_hash(provisional),
        **values,
    )


def multitier_population_audit_hash(value: MultiTierPopulationAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_hash"}),
        prefix="finance_multitier_capability_population_audit:",
    )


def multitier_population_id(value: MultiTierCapabilityPopulation) -> str:
    return canonical_hash(
        {
            "run_id": value.run_id,
            "source_artifacts_sha256": value.source_artifacts_sha256,
            "regression_contract_id": value.regression_contract_id,
            "regression_report_id": value.regression_report_id,
            "additional_exposure_ids": tuple(
                item.contract_id for item in value.additional_exposure_contract_references
            ),
            "excluded_core_signature_set_hash": value.excluded_core_signature_set_hash,
            "excluded_evidence_id_set_hash": value.excluded_evidence_id_set_hash,
            "excluded_evidence_version_set_hash": (value.excluded_evidence_version_set_hash),
            "sampling_salt": value.sampling_salt,
            "core_program_tiers": value.core_program_tiers,
            "protocol_profile_hash": value.protocol_profile.profile_hash,
            "group_hashes": tuple(item.group_hash for item in value.groups),
        },
        prefix="finance_multitier_capability_population:",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def population_cli_summary(
    population: MultiTierCapabilityPopulation,
) -> dict[str, Any]:
    return {
        "population_id": population.population_id,
        "group_count": len(population.groups),
        "task_count": len(population.tasks),
        "static_contract_count": population.audit.static_record_count,
        "static_contract_pass_count": (population.public_contract_audit.passed_record_count),
        "excluded_evidence_version_count": len(population.excluded_evidence_version_ids),
        "ready": population.audit.multi_tier_population_ready,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the fresh v25.12 multi-Tier Finance capability population."
    )
    parser.add_argument("--source-artifacts", type=Path, required=True)
    parser.add_argument("--regression-contract", type=Path, required=True)
    parser.add_argument("--regression-report", type=Path, required=True)
    parser.add_argument("--additional-exposure-contract", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sampling-salt", required=True)
    args = parser.parse_args(argv)
    population = build_multitier_capability_population(
        source_artifacts_path=args.source_artifacts,
        regression_contract_path=args.regression_contract,
        regression_report_path=args.regression_report,
        output_path=args.output,
        run_id=args.run_id,
        sampling_salt=args.sampling_salt,
        additional_exposure_contract_paths=tuple(args.additional_exposure_contract),
    )
    print(
        json.dumps(
            population_cli_summary(population),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
