from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.builder import public_program_skeleton
from trusted_synthesis.core.task.materialization import resolved_retrieval_scope
from trusted_synthesis.core.task.program import TaskProgram
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    make_finance_typed_recovery_scenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_ir import (
    CORE_FAMILY_BY_MECHANISM,
    DEVELOPMENT_TIERS,
    MECHANISM_IDS,
    RECOVERY_ORIGIN_FAMILIES,
    CapabilitySensitiveTaskArtifact,
    MechanismDevelopmentGroup,
    MechanismMutationResult,
    MechanismTaskVariant,
    MechanismTier,
    evaluate_mutation,
    make_control_action_graph,
    make_mechanism_action_graph,
    make_mutation_specs,
    mechanism_group_hash,
    mechanism_group_id,
    mechanism_task_variant_hash,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    RecoveryBranch,
    _CapabilityTaskBuilder,
    _load_evidence_pool,
    _minimum_mismatch_fields,
    capability_sensitive_task_artifact_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_capability_population import (
    ANSWER_PROJECTION_CONTRACT_VERSION,
    _public_contract_metadata,
    finance_public_calculation_instruction,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_benchmark_capability_audit import (
    CapabilityMechanism,
    PublicBenchmarkCapabilityAudit,
)
from trusted_synthesis.hashing import canonical_hash

CAPABILITY_MECHANISM_DEVELOPMENT_VERSION = "finance_capability_mechanism_development.v3"
CAPABILITY_MECHANISM_STATIC_AUDIT_VERSION = "finance_capability_mechanism_static_audit.v3"

BENCHMARK_CONTENT_MARKERS: tuple[str, ...] = (
    "finqa",
    "tat-qa",
    "tat_qa",
    "gaia benchmark",
    "bfcl",
    "webarena",
    "swe-bench",
    "agentbench",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MechanismStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    group_count: int = Field(ge=1)
    variant_count: int = Field(ge=2)
    mechanism_tier_counts: dict[str, dict[MechanismTier, int]]
    execution_replay_pass_rate: float = Field(ge=0, le=1)
    matched_contract_pass_rate: float = Field(ge=0, le=1)
    matched_intervention_pass_rate: float = Field(ge=0, le=1)
    required_dependency_pass_rate: float = Field(ge=0, le=1)
    executable_mechanism_support_pass_rate: float = Field(ge=0, le=1)
    answer_contract_pass_rate: float = Field(ge=0, le=1)
    mutation_detection_rate: float = Field(ge=0, le=1)
    mutation_results: tuple[MechanismMutationResult, ...] = Field(min_length=1)
    group_evidence_disjoint: bool
    v25_20_evidence_disjoint: bool
    semantic_signature_disjoint: bool
    benchmark_content_isolation_passed: bool
    bridge_contract_complete: bool
    verification_candidate_balance_passed: bool
    recovery_cross_family_coverage: int = Field(ge=0)
    mechanism_depth_means: dict[str, dict[MechanismTier, float]]
    mechanism_depth_monotonic: dict[str, bool]
    rejection_reasons: tuple[str, ...]
    development_ready: bool
    next_permitted_stage: Literal[
        "flash_mechanism_development",
        "mechanism_population_repair_only",
    ]
    schema_version: str = CAPABILITY_MECHANISM_STATIC_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> MechanismStaticAudit:
        ready = not self.rejection_reasons
        if self.development_ready != ready:
            raise ValueError("mechanism static readiness is inconsistent")
        expected_stage = (
            "flash_mechanism_development" if ready else "mechanism_population_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("mechanism population transition is not fail-closed")
        if self.audit_id != mechanism_static_audit_id(self):
            raise ValueError("mechanism static audit identity is invalid")
        return self


class CapabilityMechanismDevelopmentPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_artifacts_path: str = Field(min_length=1)
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    source_v25_20_population_path: str = Field(min_length=1)
    source_v25_20_population_sha256: str = Field(min_length=64, max_length=64)
    source_v25_21_audit_path: str = Field(min_length=1)
    source_v25_21_audit_sha256: str = Field(min_length=64, max_length=64)
    source_v25_21_audit_id: str = Field(min_length=1)
    sampling_salt: str = Field(min_length=1)
    excluded_evidence_ids: tuple[str, ...] = Field(min_length=1)
    excluded_evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    excluded_semantic_signatures: tuple[str, ...] = Field(min_length=1)
    mechanisms: tuple[CapabilityMechanism, ...] = Field(min_length=7, max_length=7)
    groups: tuple[MechanismDevelopmentGroup, ...] = Field(min_length=84, max_length=84)
    static_audit: MechanismStaticAudit
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "flash_mechanism_development",
        "mechanism_population_repair_only",
    ]
    schema_version: str = CAPABILITY_MECHANISM_DEVELOPMENT_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> CapabilityMechanismDevelopmentPopulation:
        if tuple(item.mechanism_id for item in self.mechanisms) != MECHANISM_IDS:
            raise ValueError("mechanism population catalog order differs from preregistration")
        if tuple(sorted(set(self.excluded_evidence_ids))) != self.excluded_evidence_ids:
            raise ValueError("mechanism Evidence exclusions are not canonical")
        if (
            tuple(sorted(set(self.excluded_evidence_version_ids)))
            != self.excluded_evidence_version_ids
        ):
            raise ValueError("mechanism Evidence Version exclusions are not canonical")
        if (
            tuple(sorted(set(self.excluded_semantic_signatures)))
            != self.excluded_semantic_signatures
        ):
            raise ValueError("mechanism semantic exclusions are not canonical")
        expected = make_mechanism_static_audit(
            self.groups,
            excluded_evidence_ids=set(self.excluded_evidence_ids),
            excluded_evidence_version_ids=set(self.excluded_evidence_version_ids),
            excluded_semantic_signatures=set(self.excluded_semantic_signatures),
        )
        if self.static_audit != expected:
            raise ValueError("mechanism static audit differs from frozen groups")
        if self.next_permitted_stage != self.static_audit.next_permitted_stage:
            raise ValueError("mechanism population stage differs from static audit")
        if self.population_id != mechanism_population_id(self):
            raise ValueError("mechanism population identity is invalid")
        return self

    @property
    def tasks(self) -> tuple[CapabilitySensitiveTaskArtifact, ...]:
        return tuple(
            variant.artifact
            for group in self.groups
            for variant in (group.control, group.mechanism)
        )


@dataclass(frozen=True)
class _CoreSelection:
    mechanism_id: str
    mechanism_tier: MechanismTier
    group_index: int
    family: str
    source_tier: DifficultyTier
    gold: tuple[EvidenceItem, ...]
    program: TaskProgram
    instruction: str
    answer_projection: dict[str, str]


def mechanism_static_audit_id(value: MechanismStaticAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_capability_mechanism_static_audit:",
    )


def mechanism_population_id(value: CapabilityMechanismDevelopmentPopulation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"population_id"}),
        prefix="finance_capability_mechanism_development_population:",
    )


def build_capability_mechanism_development_population(
    *,
    source_artifacts_path: Path,
    source_v25_20_population_path: Path,
    source_v25_21_audit_path: Path,
    output_dir: Path,
    run_id: str,
    sampling_salt: str,
) -> CapabilityMechanismDevelopmentPopulation:
    population_path = output_dir / "finance_capability_mechanism_population.json"
    if population_path.exists():
        raise ValueError("v25.21 mechanism Development population is immutable")
    source_artifacts_path = source_artifacts_path.resolve()
    source_v25_20_population_path = source_v25_20_population_path.resolve()
    source_v25_21_audit_path = source_v25_21_audit_path.resolve()
    audit = PublicBenchmarkCapabilityAudit.model_validate_json(
        source_v25_21_audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit.audit_passed
        or audit.next_permitted_stage != "finance_v25_21_mechanism_population_construction_only"
        or audit.population_contract.minimum_development_group_count != 84
    ):
        raise ValueError("v25.21 mechanism construction lacks a passing design audit")
    prior = json.loads(source_v25_20_population_path.read_text(encoding="utf-8"))
    if not prior.get("population_ready"):
        raise ValueError("v25.21 mechanism construction lacks a ready v25.20 population")
    if Path(str(prior["source_artifacts_path"])).resolve() != source_artifacts_path:
        raise ValueError("v25.21 source artifacts differ from v25.20")
    excluded_ids, excluded_versions = _collect_evidence_identity(prior)
    excluded_ids.update(str(item) for item in prior.get("excluded_evidence_ids", ()))
    excluded_versions.update(str(item) for item in prior.get("excluded_evidence_version_ids", ()))
    excluded_signatures = {str(item) for item in prior.get("excluded_semantic_signatures", ())}
    excluded_signatures.update(
        str(item["core_semantic_signature"])
        for item in prior.get("groups", ())
        if isinstance(item, Mapping) and item.get("core_semantic_signature")
    )
    pool = _load_evidence_pool(source_artifacts_path)
    builder = _CapabilityTaskBuilder(pool, sampling_salt=sampling_salt)
    planned_groups = _select_cores_with_distractors(
        builder,
        evidence_pool=tuple(pool.public.values()),
        excluded_evidence_ids=excluded_ids,
        excluded_evidence_version_ids=excluded_versions,
        sampling_salt=sampling_salt,
    )
    groups = [
        _materialize_group(builder, selection, distractors)
        for selection, distractors in planned_groups
    ]
    static_audit = make_mechanism_static_audit(
        tuple(groups),
        excluded_evidence_ids=excluded_ids,
        excluded_evidence_version_ids=excluded_versions,
        excluded_semantic_signatures=excluded_signatures,
    )
    values = {
        "run_id": run_id,
        "source_artifacts_path": str(source_artifacts_path),
        "source_artifacts_sha256": _sha256(source_artifacts_path),
        "source_v25_20_population_path": str(source_v25_20_population_path),
        "source_v25_20_population_sha256": _sha256(source_v25_20_population_path),
        "source_v25_21_audit_path": str(source_v25_21_audit_path),
        "source_v25_21_audit_sha256": _sha256(source_v25_21_audit_path),
        "source_v25_21_audit_id": audit.report_id,
        "sampling_salt": sampling_salt,
        "excluded_evidence_ids": tuple(sorted(excluded_ids)),
        "excluded_evidence_version_ids": tuple(sorted(excluded_versions)),
        "excluded_semantic_signatures": tuple(sorted(excluded_signatures)),
        "mechanisms": audit.mechanisms,
        "groups": tuple(groups),
        "static_audit": static_audit,
        "next_permitted_stage": static_audit.next_permitted_stage,
    }
    provisional = CapabilityMechanismDevelopmentPopulation.model_construct(
        population_id="pending",
        **values,
    )
    population = CapabilityMechanismDevelopmentPopulation(
        population_id=mechanism_population_id(provisional),
        **values,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(population_path, population.model_dump(mode="json"))
    _write_json_atomic(
        output_dir / "finance_capability_mechanism_static_audit.json",
        static_audit.model_dump(mode="json"),
    )
    _write_text_atomic(
        output_dir / "finance_capability_mechanism_development_report.md",
        _render_report(population),
    )
    return population


def _select_cores_with_distractors(
    builder: _CapabilityTaskBuilder,
    *,
    evidence_pool: tuple[EvidenceItem, ...],
    excluded_evidence_ids: set[str],
    excluded_evidence_version_ids: set[str],
    sampling_salt: str,
) -> tuple[tuple[_CoreSelection, tuple[EvidenceItem, ...]], ...]:
    used_ids = set(excluded_evidence_ids)
    used_versions = set(excluded_evidence_version_ids)
    selected: list[tuple[_CoreSelection, tuple[EvidenceItem, ...]]] = []
    for mechanism_id in MECHANISM_IDS:
        family = CORE_FAMILY_BY_MECHANISM[mechanism_id]
        for group_index, mechanism_tier in enumerate(DEVELOPMENT_TIERS):
            preferred = (
                DifficultyTier.FRONTIER
                if mechanism_id == "finance.dependent_compositional_calculation"
                or mechanism_tier in {"frontier", "hard_control"}
                else DifficultyTier.EASY_CONTROL
            )
            candidate_tiers = [preferred]
            if preferred == DifficultyTier.FRONTIER and mechanism_id != MECHANISM_IDS[2]:
                candidate_tiers.append(DifficultyTier.EASY_CONTROL)
            planned = None
            for source_tier in candidate_tiers:
                for candidate in _candidate_iterator(builder, family, source_tier):
                    gold, program, instruction, projection = candidate
                    gold_ids = {item.evidence_id for item in gold}
                    gold_versions = {item.evidence_version_id for item in gold}
                    if gold_ids & used_ids or gold_versions & used_versions:
                        continue
                    selection = _CoreSelection(
                        mechanism_id=mechanism_id,
                        mechanism_tier=mechanism_tier,
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
                    "real Finance Evidence cannot jointly support a disjoint core and "
                    "mechanism distractors for "
                    f"{mechanism_id}/{mechanism_tier}/{group_index}"
                )
            selection, distractors = planned
            used_ids.update(item.evidence_id for item in selection.gold)
            used_ids.update(item.evidence_id for item in distractors)
            used_versions.update(item.evidence_version_id for item in selection.gold)
            used_versions.update(item.evidence_version_id for item in distractors)
            selected.append(planned)
    return tuple(selected)


def _candidate_iterator(
    builder: _CapabilityTaskBuilder,
    family: str,
    tier: DifficultyTier,
) -> Iterable[tuple[tuple[EvidenceItem, ...], TaskProgram, str, dict[str, str]]]:
    if family == "finance.branching_operation_plan":
        return builder._cross_candidates(family, tier)
    return builder._temporal_candidates(family, tier)


def _distractor_target(mechanism_id: str, tier: MechanismTier) -> int:
    if mechanism_id == MECHANISM_IDS[2]:
        return 0
    if mechanism_id in {MECHANISM_IDS[0], MECHANISM_IDS[3]}:
        return {
            "easy_control": 1,
            "bridge": 2,
            "frontier": 2,
            "hard_control": 3,
        }[tier]
    return 1


def _select_mechanism_distractors(
    selection: _CoreSelection,
    evidence_pool: Iterable[EvidenceItem],
    *,
    reserved_evidence_ids: set[str],
    reserved_evidence_version_ids: set[str],
    sampling_salt: str,
) -> tuple[EvidenceItem, ...]:
    target = _distractor_target(selection.mechanism_id, selection.mechanism_tier)
    if target == 0:
        return ()
    preferred_fields = (
        {"period", "definition", "payload_context", "source"}
        if selection.mechanism_id == MECHANISM_IDS[3]
        else {"subject", "predicate", "period", "source", "definition", "payload_context"}
    )
    ranked = []
    for item in evidence_pool:
        if (
            item.evidence_id in reserved_evidence_ids
            or item.evidence_version_id in reserved_evidence_version_ids
        ):
            continue
        mismatches = _minimum_mismatch_fields(item, selection.gold)
        if len(mismatches) != 1 or mismatches[0] not in preferred_fields:
            continue
        ranked.append(
            (
                canonical_hash(
                    {
                        "salt": sampling_salt,
                        "mechanism": selection.mechanism_id,
                        "tier": selection.mechanism_tier,
                        "group": selection.group_index,
                        "mismatch": mismatches[0],
                        "candidate": item.evidence_version_id,
                    },
                    prefix="finance_v25_21_mechanism_distractor:",
                ),
                mismatches[0],
                item,
            )
        )
    selected: list[EvidenceItem] = []
    represented: set[str] = set()
    for _, mismatch, item in sorted(ranked, key=lambda row: row[0]):
        if mismatch in represented and len(represented) < min(target, len(preferred_fields)):
            continue
        selected.append(item)
        represented.add(mismatch)
        if len(selected) == target:
            return tuple(selected)
    for _, _, item in sorted(ranked, key=lambda row: row[0]):
        if item in selected:
            continue
        selected.append(item)
        if len(selected) == target:
            return tuple(selected)
    raise ValueError(
        "real Finance Evidence lacks mechanism-specific single-violation distractors for "
        f"{selection.mechanism_id}/{selection.mechanism_tier}/{selection.group_index}; "
        f"required={target}, built={len(selected)}"
    )


def _materialize_group(
    builder: _CapabilityTaskBuilder,
    selection: _CoreSelection,
    distractors: tuple[EvidenceItem, ...],
) -> MechanismDevelopmentGroup:
    control_graph = make_control_action_graph(selection.mechanism_tier)
    mechanism_graph = make_mechanism_action_graph(
        selection.mechanism_id,
        selection.mechanism_tier,
    )
    compatibility = _compatibility_policy(
        selection.mechanism_id,
        selection.mechanism_tier,
    )
    invariant = _completion_invariant(selection)
    candidate_status = "not_applicable"
    candidate_payload: dict[str, Any] | None = None
    if selection.mechanism_id == MECHANISM_IDS[4]:
        candidate_status = "valid" if selection.group_index % 3 == 0 else "invalid_localized"
    recovery_origin = (
        RECOVERY_ORIGIN_FAMILIES[selection.group_index % len(RECOVERY_ORIGIN_FAMILIES)]
        if selection.mechanism_id == MECHANISM_IDS[5]
        else None
    )
    control_metadata = _public_metadata(
        selection,
        role="resolved_control",
        graph=control_graph,
        compatibility_policy=compatibility,
        completeness_invariant=invariant,
        candidate_payload=None,
        recovery_origin_family=None,
    )
    control = builder._materialize(
        family=selection.family,
        tier=selection.source_tier,
        gold=selection.gold,
        distractors=distractors,
        recovery_branches=(),
        program=selection.program,
        instruction=finance_public_calculation_instruction(
            _control_instruction(selection),
            family=selection.family,
            tier=selection.source_tier,
            gold=selection.gold,
            program=selection.program,
        ),
        answer_projection=selection.answer_projection,
        public_metadata=control_metadata,
    )
    control = _with_action_graph_tools(control, control_graph)
    control = _make_resolved_control(control, selection.gold)
    if selection.mechanism_id == MECHANISM_IDS[4]:
        candidate_payload = (
            dict(control.projected_expected_output)
            if candidate_status == "valid"
            else _mutate_candidate(control.projected_expected_output)
        )
    recovery_branches: tuple[RecoveryBranch, ...] = ()
    if selection.mechanism_id in {MECHANISM_IDS[0], MECHANISM_IDS[1], MECHANISM_IDS[5]}:
        if not distractors:
            raise ValueError("mechanism requiring recovery lacks a typed near-match")
        recovery_branches = (
            RecoveryBranch(
                distractor_evidence_id=distractors[0].evidence_id,
                mismatch_fields=_minimum_mismatch_fields(distractors[0], selection.gold),
            ),
        )
    mechanism_metadata = _public_metadata(
        selection,
        role="mechanism_required",
        graph=mechanism_graph,
        compatibility_policy=compatibility,
        completeness_invariant=invariant,
        candidate_payload=candidate_payload,
        recovery_origin_family=recovery_origin,
    )
    if selection.mechanism_id in {MECHANISM_IDS[1], MECHANISM_IDS[5]}:
        mismatch_fields = tuple(
            sorted({field for branch in recovery_branches for field in branch.mismatch_fields})
        )
        scenario = make_finance_typed_recovery_scenario(
            scope_identity=canonical_hash(
                {
                    "mechanism": selection.mechanism_id,
                    "tier": selection.mechanism_tier,
                    "group": selection.group_index,
                    "versions": tuple(item.evidence_version_id for item in selection.gold),
                },
                prefix="finance_v25_21_typed_recovery_scope:",
            ),
            mismatch_fields=mismatch_fields,
        )
        mechanism_metadata["typed_recovery_scenario"] = scenario.model_dump(mode="json")
    mechanism = builder._materialize(
        family=selection.family,
        tier=selection.source_tier,
        gold=selection.gold,
        distractors=distractors,
        recovery_branches=recovery_branches,
        program=selection.program,
        instruction=finance_public_calculation_instruction(
            _mechanism_instruction(selection, candidate_payload),
            family=selection.family,
            tier=selection.source_tier,
            gold=selection.gold,
            program=selection.program,
        ),
        answer_projection=selection.answer_projection,
        public_metadata=mechanism_metadata,
    )
    mechanism = _with_action_graph_tools(mechanism, mechanism_graph)
    control_variant = _make_variant(
        role="resolved_control",
        selection=selection,
        artifact=control,
        action_graph=control_graph,
        invariant=invariant,
        compatibility=compatibility,
        candidate_status="not_applicable",
        recovery_origin=None,
    )
    mechanism_variant = _make_variant(
        role="mechanism_required",
        selection=selection,
        artifact=mechanism,
        action_graph=mechanism_graph,
        invariant=invariant,
        compatibility=compatibility,
        candidate_status=candidate_status,
        recovery_origin=recovery_origin,
    )
    core_signature = canonical_hash(
        {
            "mechanism": selection.mechanism_id,
            "tier": selection.mechanism_tier,
            "gold_versions": tuple(item.evidence_version_id for item in selection.gold),
            "program": selection.program,
            "answer_projection": selection.answer_projection,
        },
        prefix="finance_v25_21_mechanism_core_semantics:",
    )
    mutations = make_mutation_specs(mechanism_graph)
    values = {
        "mechanism_id": selection.mechanism_id,
        "mechanism_tier": selection.mechanism_tier,
        "group_index": selection.group_index,
        "core_semantic_signature": core_signature,
        "control": control_variant,
        "mechanism": mechanism_variant,
        "mutations": mutations,
    }
    provisional = MechanismDevelopmentGroup.model_construct(
        group_id="pending",
        group_hash="pending",
        **values,
    )
    group_id = mechanism_group_id(provisional)
    provisional = provisional.model_copy(update={"group_id": group_id})
    return MechanismDevelopmentGroup(
        group_id=group_id,
        group_hash=mechanism_group_hash(provisional),
        **values,
    )


def _with_action_graph_tools(
    artifact: CapabilitySensitiveTaskArtifact,
    graph: Any,
) -> CapabilitySensitiveTaskArtifact:
    graph_tools = tuple(node.tool_id for node in graph.nodes if node.tool_id is not None)
    allowed_tools = tuple(dict.fromkeys((*artifact.task.public.allowed_tools, *graph_tools)))
    public = artifact.task.public.model_copy(update={"allowed_tools": allowed_tools})
    task = artifact.task.model_copy(update={"public": public})
    provisional = artifact.model_copy(update={"artifact_id": "pending", "task": task})
    return artifact.model_copy(
        update={
            "artifact_id": capability_sensitive_task_artifact_id(provisional),
            "task": task,
        }
    )


def _make_resolved_control(
    artifact: CapabilitySensitiveTaskArtifact,
    gold: tuple[EvidenceItem, ...],
) -> CapabilitySensitiveTaskArtifact:
    public = artifact.task.public.model_copy(
        update={
            "retrieval_track": RetrievalTrack.RESOLVED,
            "planning_track": PlanningTrack.PLAN_GIVEN,
            "retrieval_scope": resolved_retrieval_scope(gold),
            "program_skeleton": public_program_skeleton(
                artifact.task.oracle.task_program,
                default_registry(),
                gold,
            ),
        }
    )
    task = artifact.task.model_copy(update={"public": public})
    provisional = artifact.model_copy(update={"artifact_id": "pending", "task": task})
    return artifact.model_copy(
        update={
            "artifact_id": capability_sensitive_task_artifact_id(provisional),
            "task": task,
        }
    )


def _make_variant(
    *,
    role: Literal["resolved_control", "mechanism_required"],
    selection: _CoreSelection,
    artifact: CapabilitySensitiveTaskArtifact,
    action_graph: Any,
    invariant: str,
    compatibility: tuple[str, ...],
    candidate_status: str,
    recovery_origin: str | None,
) -> MechanismTaskVariant:
    values = {
        "role": role,
        "mechanism_id": selection.mechanism_id,
        "mechanism_tier": selection.mechanism_tier,
        "artifact": artifact,
        "action_graph": action_graph,
        "public_completeness_invariant": invariant,
        "compatibility_policy": compatibility,
        "candidate_status": candidate_status,
        "recovery_origin_family": recovery_origin,
    }
    provisional = MechanismTaskVariant.model_construct(
        variant_id="pending",
        contract_hash="pending",
        **values,
    )
    contract_hash = mechanism_task_variant_hash(provisional)
    return MechanismTaskVariant(
        variant_id=canonical_hash(
            {"contract_hash": contract_hash, "role": role},
            prefix="finance_capability_mechanism_variant_id:",
        ),
        contract_hash=contract_hash,
        **values,
    )


def _public_metadata(
    selection: _CoreSelection,
    *,
    role: str,
    graph: Any,
    compatibility_policy: tuple[str, ...],
    completeness_invariant: str,
    candidate_payload: dict[str, Any] | None,
    recovery_origin_family: str | None,
) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "mechanism_id": selection.mechanism_id,
        "mechanism_tier": selection.mechanism_tier,
        "variant_role": role,
        "action_contract": graph.model_dump(mode="json"),
        "public_completeness_invariant": completeness_invariant,
        "compatibility_policy": compatibility_policy,
        "required_record_count": len(selection.gold),
        "answer_preservation_rule": "same core semantics and output schema across matched variants",
    }
    if candidate_payload is not None:
        contract["untrusted_candidate"] = candidate_payload
    if recovery_origin_family is not None:
        contract["failure_origin_family"] = recovery_origin_family
    metadata = _public_contract_metadata(
        family=selection.family,
        tier=selection.source_tier,
        gold=selection.gold,
        program=selection.program,
        answer_projection=selection.answer_projection,
        recovery_branches=(),
    )
    guidance = dict(metadata["agent_contract_guidance"])
    guidance["capability_mechanism_contract"] = contract
    return {
        **metadata,
        "v25_21_mechanism": contract,
        "agent_contract_guidance": guidance,
    }


def _control_instruction(selection: _CoreSelection) -> str:
    return (
        "The Host has already resolved the compatible records and the typed operation path. "
        f"{selection.instruction} Replay the final result and return only the registered output."
    )


def _mechanism_instruction(
    selection: _CoreSelection,
    candidate_payload: dict[str, Any] | None,
) -> str:
    prefix = {
        MECHANISM_IDS[0]: (
            "Investigate competing archive paths, reject near-matches that violate one typed "
            "constraint, and join every required compatible record before calculating. "
        ),
        MECHANISM_IDS[1]: (
            "Choose the tool whose schema fits the current observation, construct its arguments, "
            "and repair only the rejected argument after typed Host feedback. "
        ),
        MECHANISM_IDS[2]: (
            "Normalize the compatible inputs, preserve intermediate lineage, and execute at least "
            "three dependent arithmetic steps in order. "
        ),
        MECHANISM_IDS[3]: (
            "Apply the public alias, unit, period, and source-definition compatibility rules; "
            "resolve bridge cases with a qualifier and reject non-comparable cases. "
        ),
        MECHANISM_IDS[4]: (
            "Treat the supplied candidate as untrusted. Independently replay it, localize any "
            "difference, repair only the failed field, and preserve unaffected fields. "
        ),
        MECHANISM_IDS[5]: (
            "When the first family action receives a typed failure, attribute the failed field, "
            "revise only that field or action, retry, and verify completion. "
        ),
        MECHANISM_IDS[6]: (
            "Use the public completeness invariant to decide whether to continue or stop; do not "
            "stop with a required role unresolved and avoid redundant actions after completion. "
        ),
    }[selection.mechanism_id]
    candidate = (
        f"The untrusted candidate payload is {json.dumps(candidate_payload, sort_keys=True)}. "
        if candidate_payload is not None
        else ""
    )
    return f"{prefix}{candidate}{selection.instruction}"


def _compatibility_policy(
    mechanism_id: str,
    tier: MechanismTier,
) -> tuple[str, ...]:
    if mechanism_id != MECHANISM_IDS[3]:
        return ("same_entity_metric_period_scope",)
    values = ["alias_equivalence"]
    if tier in {"bridge", "frontier", "hard_control"}:
        values.append("unit_period_field_normalization")
    if tier in {"frontier", "hard_control"}:
        values.append("source_definition_compatibility")
    if tier == "hard_control":
        values.append("noncomparable_multi_source_conflict_rejection")
    return tuple(values)


def _completion_invariant(selection: _CoreSelection) -> str:
    role_count = len(selection.gold)
    return {
        MECHANISM_IDS[0]: f"all_{role_count}_typed_record_roles_joined",
        MECHANISM_IDS[1]: "typed_tool_call_succeeds_after_observation_bound_argument_repair",
        MECHANISM_IDS[2]: "normalization_and_three_dependent_operations_replayed",
        MECHANISM_IDS[3]: "every_input_has_an_explicit_compatibility_decision",
        MECHANISM_IDS[4]: "candidate_replay_matches_repaired_output_and_preserves_other_fields",
        MECHANISM_IDS[5]: "failed_field_revised_and_post_repair_verification_passed",
        MECHANISM_IDS[6]: f"all_{role_count}_required_roles_resolved_and_verified",
    }[selection.mechanism_id]


def _mutate_candidate(value: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(value)
    for key in ("value", "difference", "ratio", "growth"):
        if key not in output:
            continue
        try:
            output[key] = str(Decimal(str(output[key])) + Decimal("1"))
            return output
        except (InvalidOperation, TypeError, ValueError):
            continue
    if "higher_ref" in output:
        output["higher_ref"] = "unregistered_candidate_reference"
        return output
    output["localized_mutation"] = "unexpected_extra_field"
    return output


def make_mechanism_static_audit(
    groups: tuple[MechanismDevelopmentGroup, ...],
    *,
    excluded_evidence_ids: set[str],
    excluded_evidence_version_ids: set[str],
    excluded_semantic_signatures: set[str],
) -> MechanismStaticAudit:
    tier_counts: dict[str, dict[MechanismTier, int]] = {}
    for mechanism_id in MECHANISM_IDS:
        counter = Counter(
            item.mechanism_tier for item in groups if item.mechanism_id == mechanism_id
        )
        tier_counts[mechanism_id] = {
            tier: counter[tier] for tier in ("easy_control", "bridge", "frontier", "hard_control")
        }
    variants = tuple(variant for group in groups for variant in (group.control, group.mechanism))
    execution_rate = _rate(item.artifact.verification.passed for item in variants)
    matched_rate = _rate(_matched_contract_passes(item) for item in groups)
    intervention_rate = _rate(_matched_intervention_passes(item) for item in groups)
    dependency_rate = _rate(not _variant_contract_failures(item.mechanism) for item in groups)
    executable_support_rate = _rate(_executable_mechanism_support(item) for item in groups)
    answer_contract_rate = _rate(_answer_contract_passes(item) for item in variants)
    mutation_results = tuple(
        evaluate_mutation(group.mechanism, mutation)
        for group in groups
        for mutation in group.mutations
    )
    mutation_rate = _rate(item.detected for item in mutation_results)
    group_evidence = [
        {item.evidence_id for item in group.mechanism.artifact.public_corpus.evidence}
        for group in groups
    ]
    group_disjoint = all(
        not left & right
        for index, left in enumerate(group_evidence)
        for right in group_evidence[index + 1 :]
    )
    all_items = [
        item for group in groups for item in group.mechanism.artifact.public_corpus.evidence
    ]
    prior_disjoint = all(
        item.evidence_id not in excluded_evidence_ids
        and item.evidence_version_id not in excluded_evidence_version_ids
        for item in all_items
    )
    semantic_disjoint = (
        not {item.core_semantic_signature for item in groups} & excluded_semantic_signatures
    )
    benchmark_isolation = all(_benchmark_isolated(item) for item in variants)
    bridge_complete = all(
        tier_counts[mechanism_id]["bridge"] == 4 for mechanism_id in MECHANISM_IDS
    ) and all(
        "unit_period_field_normalization" in item.mechanism.compatibility_policy
        for item in groups
        if item.mechanism_id == MECHANISM_IDS[3] and item.mechanism_tier == "bridge"
    )
    candidate_statuses = {
        item.mechanism.candidate_status for item in groups if item.mechanism_id == MECHANISM_IDS[4]
    }
    candidate_balance = candidate_statuses == {"valid", "invalid_localized"}
    recovery_coverage = len(
        {
            item.mechanism.recovery_origin_family
            for item in groups
            if item.mechanism_id == MECHANISM_IDS[5]
        }
    )
    depth_means: dict[str, dict[MechanismTier, float]] = {}
    depth_monotonic: dict[str, bool] = {}
    for mechanism_id in MECHANISM_IDS:
        means: dict[MechanismTier, float] = {
            tier: sum(
                item.mechanism.action_graph.graph_depth
                for item in groups
                if item.mechanism_id == mechanism_id and item.mechanism_tier == tier
            )
            / tier_counts[mechanism_id][tier]
            for tier in ("easy_control", "bridge", "frontier", "hard_control")
        }
        depth_means[mechanism_id] = means
        depth_monotonic[mechanism_id] = (
            means["easy_control"] < means["bridge"] < means["frontier"] < means["hard_control"]
        )
    expected_counts = {
        "easy_control": 2,
        "bridge": 4,
        "frontier": 4,
        "hard_control": 2,
    }
    checks = {
        "development_group_count_mismatch": len(groups) == 84,
        "mechanism_tier_quota_mismatch": all(
            tier_counts[mechanism_id] == expected_counts for mechanism_id in MECHANISM_IDS
        ),
        "operation_replay_failed": math.isclose(execution_rate, 1.0),
        "matched_contract_failed": math.isclose(matched_rate, 1.0),
        "matched_intervention_failed": math.isclose(intervention_rate, 1.0),
        "required_dependency_failed": math.isclose(dependency_rate, 1.0),
        "executable_mechanism_support_failed": math.isclose(executable_support_rate, 1.0),
        "answer_contract_incomplete": math.isclose(answer_contract_rate, 1.0),
        "mutation_escaped": math.isclose(mutation_rate, 1.0),
        "group_evidence_overlap": group_disjoint,
        "v25_20_evidence_overlap": prior_disjoint,
        "semantic_signature_overlap": semantic_disjoint,
        "benchmark_content_detected": benchmark_isolation,
        "bridge_contract_incomplete": bridge_complete,
        "verification_candidate_unbalanced": candidate_balance,
        "recovery_cross_family_coverage_insufficient": recovery_coverage >= 3,
        "mechanism_depth_not_monotonic": all(depth_monotonic.values()),
    }
    rejections = tuple(sorted(code for code, passed in checks.items() if not passed))
    values = {
        "group_count": len(groups),
        "variant_count": len(variants),
        "mechanism_tier_counts": tier_counts,
        "execution_replay_pass_rate": execution_rate,
        "matched_contract_pass_rate": matched_rate,
        "matched_intervention_pass_rate": intervention_rate,
        "required_dependency_pass_rate": dependency_rate,
        "executable_mechanism_support_pass_rate": executable_support_rate,
        "answer_contract_pass_rate": answer_contract_rate,
        "mutation_detection_rate": mutation_rate,
        "mutation_results": mutation_results,
        "group_evidence_disjoint": group_disjoint,
        "v25_20_evidence_disjoint": prior_disjoint,
        "semantic_signature_disjoint": semantic_disjoint,
        "benchmark_content_isolation_passed": benchmark_isolation,
        "bridge_contract_complete": bridge_complete,
        "verification_candidate_balance_passed": candidate_balance,
        "recovery_cross_family_coverage": recovery_coverage,
        "mechanism_depth_means": depth_means,
        "mechanism_depth_monotonic": depth_monotonic,
        "rejection_reasons": rejections,
        "development_ready": not rejections,
        "next_permitted_stage": (
            "flash_mechanism_development" if not rejections else "mechanism_population_repair_only"
        ),
    }
    provisional = MechanismStaticAudit.model_construct(audit_id="pending", **values)
    return MechanismStaticAudit(
        audit_id=mechanism_static_audit_id(provisional),
        **values,
    )


def _matched_contract_passes(group: MechanismDevelopmentGroup) -> bool:
    left = group.control.artifact
    right = group.mechanism.artifact
    return (
        left.task.oracle.task_program == right.task.oracle.task_program
        and left.projected_expected_output == right.projected_expected_output
        and left.task.public.answer_schema == right.task.public.answer_schema
        and tuple(item.evidence_version_id for item in left.evidence_bundle.evidence)
        == tuple(item.evidence_version_id for item in right.evidence_bundle.evidence)
        and tuple(item.evidence_version_id for item in left.public_corpus.evidence)
        == tuple(item.evidence_version_id for item in right.public_corpus.evidence)
    )


def _answer_contract_passes(variant: MechanismTaskVariant) -> bool:
    artifact = variant.artifact
    metadata = artifact.task.public.metadata
    guidance = metadata.get("agent_contract_guidance")
    if (
        metadata.get("answer_projection_contract_version")
        != ANSWER_PROJECTION_CONTRACT_VERSION
        or not isinstance(guidance, Mapping)
        or not isinstance(guidance.get("answer_reference_contract"), Mapping)
        or not isinstance(guidance.get("operation_execution_contract"), Mapping)
        or "The final output rule is:" not in artifact.task.public.instruction
        or artifact.task.oracle.selection_contract.get("answer_projection")
        != artifact.answer_projection
    ):
        return False
    projection = artifact.answer_projection
    if not projection:
        return True
    allowed_labels = tuple(sorted(set(projection.values())))
    reference_contract = guidance["answer_reference_contract"]
    constraints = guidance.get("answer_field_constraints")
    higher_ref = artifact.projected_expected_output.get("higher_ref")
    return (
        tuple(reference_contract.get("allowed_reference_labels") or ()) == allowed_labels
        and isinstance(constraints, Mapping)
        and tuple(constraints.get("higher_ref", {}).get("allowed_values") or ())
        == (*allowed_labels, None)
        and (higher_ref is None or str(higher_ref) in allowed_labels)
    )


def _executable_mechanism_support(group: MechanismDevelopmentGroup) -> bool:
    variant = group.mechanism
    artifact = variant.artifact
    metadata = artifact.task.public.metadata
    public_contract = metadata.get("v25_21_mechanism")
    guidance = metadata.get("agent_contract_guidance")
    if (
        not isinstance(public_contract, Mapping)
        or not isinstance(guidance, Mapping)
        or guidance.get("capability_mechanism_contract") != public_contract
    ):
        return False
    gold_count = len(artifact.evidence_bundle.evidence)
    corpus_count = len(artifact.public_corpus.evidence)
    allowed_tools = set(artifact.task.public.allowed_tools)
    if group.mechanism_id == MECHANISM_IDS[0]:
        return (
            gold_count >= 2
            and corpus_count > gold_count
            and {"search_archive", "query_structured_fact", "cross_check_evidence"} <= allowed_tools
        )
    if group.mechanism_id == MECHANISM_IDS[1]:
        return bool(artifact.recovery_branches) and isinstance(
            metadata.get("typed_recovery_scenario"), Mapping
        )
    if group.mechanism_id == MECHANISM_IDS[2]:
        return _program_dependency_depth(artifact.task.oracle.task_program) >= 3
    if group.mechanism_id == MECHANISM_IDS[3]:
        required = {"alias_equivalence"}
        if group.mechanism_tier in {"bridge", "frontier", "hard_control"}:
            required.add("unit_period_field_normalization")
        if group.mechanism_tier in {"frontier", "hard_control"}:
            required.add("source_definition_compatibility")
        return required <= set(variant.compatibility_policy)
    if group.mechanism_id == MECHANISM_IDS[4]:
        candidate = public_contract.get("untrusted_candidate")
        return variant.candidate_status != "not_applicable" and isinstance(candidate, Mapping)
    if group.mechanism_id == MECHANISM_IDS[5]:
        return (
            bool(artifact.recovery_branches)
            and variant.recovery_origin_family in RECOVERY_ORIGIN_FAMILIES
            and isinstance(metadata.get("typed_recovery_scenario"), Mapping)
        )
    if group.mechanism_id == MECHANISM_IDS[6]:
        return gold_count >= 2 and bool(variant.public_completeness_invariant)
    return False


def _program_dependency_depth(program: TaskProgram) -> int:
    depths: dict[str, int] = {}
    for node in program.nodes:
        dependencies = tuple(
            depths[ref.ref_id] for ref in node.input_refs if ref.kind.value == "operation"
        )
        depths[node.node_id] = 1 + max(dependencies, default=0)
    return max(depths.values(), default=0)


def _matched_intervention_passes(group: MechanismDevelopmentGroup) -> bool:
    control = group.control.artifact.task.public
    mechanism = group.mechanism.artifact.task.public
    control_guidance = control.metadata.get("agent_contract_guidance")
    mechanism_guidance = mechanism.metadata.get("agent_contract_guidance")
    control_contract = control.metadata.get("v25_21_mechanism")
    mechanism_contract = mechanism.metadata.get("v25_21_mechanism")
    return (
        control.retrieval_track == RetrievalTrack.RESOLVED
        and control.planning_track == PlanningTrack.PLAN_GIVEN
        and control.program_skeleton is not None
        and control.retrieval_scope
        == resolved_retrieval_scope(group.control.artifact.evidence_bundle.evidence)
        and mechanism.retrieval_track == RetrievalTrack.SEMI_OPEN
        and mechanism.planning_track == PlanningTrack.PLAN_HIDDEN
        and isinstance(control_guidance, Mapping)
        and control_guidance.get("capability_mechanism_contract") == control_contract
        and isinstance(mechanism_guidance, Mapping)
        and mechanism_guidance.get("capability_mechanism_contract") == mechanism_contract
    )


def _variant_contract_failures(value: MechanismTaskVariant) -> tuple[str, ...]:
    from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_ir import (
        mechanism_contract_failures,
    )

    return mechanism_contract_failures(value)


def _benchmark_isolated(value: MechanismTaskVariant) -> bool:
    text = (
        value.artifact.task.public.instruction
        + " "
        + json.dumps(value.artifact.task.public.metadata, sort_keys=True)
    ).casefold()
    return not any(marker in text for marker in BENCHMARK_CONTENT_MARKERS)


def _rate(values: Iterable[bool]) -> float:
    items = tuple(values)
    return sum(items) / len(items) if items else 0.0


def _collect_evidence_identity(value: Any) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    versions: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "evidence_id" and isinstance(item, str):
                ids.add(item)
            elif key == "evidence_version_id" and isinstance(item, str):
                versions.add(item)
            else:
                nested_ids, nested_versions = _collect_evidence_identity(item)
                ids.update(nested_ids)
                versions.update(nested_versions)
    elif isinstance(value, list):
        for item in value:
            nested_ids, nested_versions = _collect_evidence_identity(item)
            ids.update(nested_ids)
            versions.update(nested_versions)
    return ids, versions


def _render_report(value: CapabilityMechanismDevelopmentPopulation) -> str:
    audit = value.static_audit
    lines = [
        "# Finance v25.21 Capability Mechanism Development Report",
        "",
        "## Decision",
        "",
        f"- Population ID: `{value.population_id}`",
        f"- Development groups: **{audit.group_count}**",
        f"- Matched task variants: **{audit.variant_count}**",
        f"- Static audit ready: **{audit.development_ready}**",
        f"- Next permitted stage: `{audit.next_permitted_stage}`",
        "- Model API calls: **0**",
        "- GPU jobs: **0**",
        "",
        "## Hard Gates",
        "",
        f"- Operation replay: **{audit.execution_replay_pass_rate:.2%}**",
        f"- Matched answer/evidence contract: **{audit.matched_contract_pass_rate:.2%}**",
        f"- Matched intervention contract: **{audit.matched_intervention_pass_rate:.2%}**",
        f"- Required dependency contract: **{audit.required_dependency_pass_rate:.2%}**",
        f"- Executable mechanism support: **{audit.executable_mechanism_support_pass_rate:.2%}**",
        f"- Public answer-contract coverage: **{audit.answer_contract_pass_rate:.2%}**",
        f"- Destructive mutation detection: **{audit.mutation_detection_rate:.2%}**",
        f"- Cross-group Evidence disjoint: **{audit.group_evidence_disjoint}**",
        f"- v25.20 Evidence disjoint: **{audit.v25_20_evidence_disjoint}**",
        f"- Benchmark-content isolation: **{audit.benchmark_content_isolation_passed}**",
        f"- Bridge contract complete: **{audit.bridge_contract_complete}**",
        (
            f"- Verification valid/invalid candidate balance: "
            f"**{audit.verification_candidate_balance_passed}**"
        ),
        f"- Recovery origin-family coverage: **{audit.recovery_cross_family_coverage}**",
        "",
        "## Mechanism/Tier Quotas",
        "",
        "| Mechanism | Easy | Bridge | Frontier | Hard | Depth monotonic |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for mechanism_id in MECHANISM_IDS:
        counts = audit.mechanism_tier_counts[mechanism_id]
        lines.append(
            f"| `{mechanism_id}` | {counts['easy_control']} | {counts['bridge']} | "
            f"{counts['frontier']} | {counts['hard_control']} | "
            f"{audit.mechanism_depth_monotonic[mechanism_id]} |"
        )
    lines.extend(
        (
            "",
            "## Interpretation",
            "",
            "Each group freezes one finance answer, Program, Gold Evidence set, public Corpus, "
            "and output schema across a resolved control and a mechanism-required variant. "
            "Only the public decision dependency changes. Four destructive mutations per group "
            "must independently violate the typed mechanism contract.",
            "",
            "This artifact authorizes Flash Development only when every deterministic gate "
            "passes. It does not authorize Pro, Beneficiary, Exact Target, GP-C, or VTDO updates.",
            "",
        )
    )
    return "\n".join(lines)


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


def _write_text_atomic(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and statically audit the v25.21 capability mechanism population."
    )
    parser.add_argument("--source-artifacts", required=True, type=Path)
    parser.add_argument("--source-v25-20-population", required=True, type=Path)
    parser.add_argument("--source-v25-21-audit", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sampling-salt", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    population = build_capability_mechanism_development_population(
        source_artifacts_path=args.source_artifacts,
        source_v25_20_population_path=args.source_v25_20_population,
        source_v25_21_audit_path=args.source_v25_21_audit,
        output_dir=args.output_dir,
        run_id=args.run_id,
        sampling_salt=args.sampling_salt,
    )
    print(
        json.dumps(
            {
                "population_id": population.population_id,
                "group_count": len(population.groups),
                "development_ready": population.static_audit.development_ready,
                "next_permitted_stage": population.next_permitted_stage,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
