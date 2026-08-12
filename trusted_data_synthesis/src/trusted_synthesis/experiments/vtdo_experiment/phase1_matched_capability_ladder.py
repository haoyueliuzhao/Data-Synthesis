from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
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

MATCHED_LADDER_VERSION = "finance_matched_capability_ladder.v1"
MATCHED_LADDER_AUDIT_VERSION = "finance_matched_capability_ladder_audit.v1"
MATCHED_CORE_SIGNATURE_VERSION = "finance_matched_core_semantics.v1"
MATCHED_GROUPS_PER_FAMILY = 3
MATCHED_GROUP_COUNT = len(CAPABILITY_SENSITIVE_FAMILIES) * MATCHED_GROUPS_PER_FAMILY
MATCHED_TASK_COUNT = MATCHED_GROUP_COUNT * len(DifficultyTier)
MATCHED_STATIC_RECORD_COUNT = MATCHED_TASK_COUNT * len(CapabilityRuntimeArm)

MATCHED_STRICT_DIMENSIONS: tuple[str, ...] = (
    "public_source_count",
    "query_decomposition_rounds",
    "reconciliation_count",
    "required_verification_count",
    "required_recovery_count",
    "distractor_branch_count",
    "tool_type_count",
    "minimal_tool_calls",
    "stopping_condition_count",
)

MATCHED_FIXED_DIMENSIONS: tuple[str, ...] = (
    "gold_evidence_count",
    "gold_subject_count",
    "operation_count",
    "operation_dag_depth",
    "operation_branch_count",
    "evidence_hop_count",
    "minimum_evidence_selection_calls",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MatchedLadderGroup(FrozenModel):
    group_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    core_semantic_signature: str = Field(min_length=1)
    core_instruction: str = Field(min_length=1)
    variants: tuple[CapabilitySensitiveTaskArtifact, ...] = Field(
        min_length=3,
        max_length=3,
    )
    group_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_group(self) -> MatchedLadderGroup:
        if self.family not in CAPABILITY_SENSITIVE_FAMILIES:
            raise ValueError("matched ladder group uses an unknown family")
        failures = matched_group_invariant_failures(self.variants)
        if failures:
            raise ValueError(f"matched ladder group violates:{','.join(failures)}")
        if {item.family for item in self.variants} != {self.family}:
            raise ValueError("matched ladder group crosses capability families")
        expected_signature = core_task_semantic_signature(self.variants[0])
        if self.core_semantic_signature != expected_signature:
            raise ValueError("matched ladder core semantic identity is invalid")
        if any(
            core_task_semantic_signature(item) != self.core_semantic_signature
            for item in self.variants
        ):
            raise ValueError("matched ladder variants do not share core semantics")
        if self.group_id != matched_ladder_group_id(self):
            raise ValueError("matched ladder group identity is invalid")
        if self.group_hash != matched_ladder_group_hash(self):
            raise ValueError("matched ladder group hash is invalid")
        return self


class MatchedLadderAudit(FrozenModel):
    group_count: int = Field(ge=1)
    task_count: int = Field(ge=1)
    family_group_counts: dict[str, int]
    excluded_core_signature_count: int = Field(ge=1)
    excluded_core_signature_set_hash: str = Field(min_length=1)
    selected_core_signature_count: int = Field(ge=1)
    selected_core_signature_set_hash: str = Field(min_length=1)
    fresh_core_semantics: bool
    group_invariant_pass_count: int = Field(ge=0)
    group_failure_codes: dict[str, tuple[str, ...]]
    cross_group_gold_disjoint: bool
    cross_group_public_corpus_disjoint: bool
    program_replay_pass_rate: float = Field(ge=0, le=1)
    public_contract_audit_id: str = Field(min_length=1)
    public_contract_record_count: int = Field(ge=1)
    public_contract_pass_rate: float = Field(ge=0, le=1)
    matched_ladder_ready: bool
    next_permitted_stage: str = Field(min_length=1)
    audit_hash: str = Field(min_length=1)
    schema_version: str = MATCHED_LADDER_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> MatchedLadderAudit:
        if self.schema_version != MATCHED_LADDER_AUDIT_VERSION:
            raise ValueError("matched ladder audit version is unsupported")
        if self.group_count != MATCHED_GROUP_COUNT or self.task_count != MATCHED_TASK_COUNT:
            raise ValueError("matched ladder audit denominator is incomplete")
        if self.family_group_counts != {
            family: MATCHED_GROUPS_PER_FAMILY for family in CAPABILITY_SENSITIVE_FAMILIES
        }:
            raise ValueError("matched ladder is not balanced by family")
        if self.selected_core_signature_count != self.group_count:
            raise ValueError("matched ladder selected signature count is inconsistent")
        expected_ready = (
            self.fresh_core_semantics
            and self.group_invariant_pass_count == self.group_count
            and not any(self.group_failure_codes.values())
            and self.cross_group_gold_disjoint
            and self.cross_group_public_corpus_disjoint
            and self.program_replay_pass_rate == 1.0
            and self.public_contract_record_count == MATCHED_STATIC_RECORD_COUNT
            and self.public_contract_pass_rate == 1.0
        )
        if self.matched_ladder_ready != expected_ready:
            raise ValueError("matched ladder readiness is inconsistent")
        expected_stage = (
            "matched_tier_localization"
            if expected_ready
            else "matched_ladder_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("matched ladder stage transition is not fail-closed")
        if self.audit_hash != matched_ladder_audit_hash(self):
            raise ValueError("matched ladder audit identity is invalid")
        return self


class MatchedCapabilityLadderPopulation(FrozenModel):
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
    additional_exposure_contract_references: tuple[
        ExposureContractReference, ...
    ] = ()
    excluded_core_signatures: tuple[str, ...] = Field(min_length=1)
    excluded_core_signature_set_hash: str = Field(min_length=1)
    sampling_salt: str = Field(min_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    groups: tuple[MatchedLadderGroup, ...] = Field(
        min_length=MATCHED_GROUP_COUNT,
        max_length=MATCHED_GROUP_COUNT,
    )
    public_contract_audit: PublicContractSatisfiabilityAudit
    audit: MatchedLadderAudit
    model_api_calls: int = Field(default=0, ge=0, le=0)
    validation_objective_access: str = "forbidden"
    authorization_objective_access: str = "forbidden"
    exact_target_evaluated: bool = False
    gp_c_evaluated: bool = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = MATCHED_LADDER_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> MatchedCapabilityLadderPopulation:
        if self.schema_version != MATCHED_LADDER_VERSION:
            raise ValueError("matched ladder population version is unsupported")
        if tuple(sorted(set(self.excluded_core_signatures))) != self.excluded_core_signatures:
            raise ValueError("matched ladder exclusion signatures are not canonical")
        reference_paths = tuple(
            item.contract_path for item in self.additional_exposure_contract_references
        )
        if len(reference_paths) != len(set(reference_paths)):
            raise ValueError("matched ladder additional exposures are duplicated")
        if self.additional_exposure_contract_references:
            exposed = load_exposed_tasks_from_references(
                self.additional_exposure_contract_references
            )
            if not {
                core_task_semantic_signature(item) for item in exposed
            } <= set(self.excluded_core_signatures):
                raise ValueError("matched ladder omitted an additional exposure")
        if self.excluded_core_signature_set_hash != signature_set_hash(
            self.excluded_core_signatures,
            prefix="finance_matched_excluded_core_signatures:",
        ):
            raise ValueError("matched ladder exclusion signature hash is invalid")
        if len({item.group_id for item in self.groups}) != len(self.groups):
            raise ValueError("matched ladder duplicates group identities")
        if len({item.core_semantic_signature for item in self.groups}) != len(self.groups):
            raise ValueError("matched ladder duplicates core semantics")
        if self.public_contract_audit.population_id != self.population_id:
            raise ValueError("matched static audit belongs to another population")
        expected = make_matched_ladder_audit(
            self.groups,
            excluded_core_signatures=self.excluded_core_signatures,
            public_contract_audit=self.public_contract_audit,
        )
        if self.audit != expected:
            raise ValueError("matched ladder audit differs from frozen groups")
        if self.population_id != matched_ladder_population_id(self):
            raise ValueError("matched ladder population identity is invalid")
        return self

    @property
    def tasks(self) -> tuple[CapabilitySensitiveTaskArtifact, ...]:
        return tuple(
            sorted(
                (task for group in self.groups for task in group.variants),
                key=lambda item: (item.family, item.artifact_id),
            )
        )


def build_matched_capability_ladder_population(
    *,
    source_artifacts_path: Path,
    regression_contract_path: Path,
    regression_report_path: Path,
    output_path: Path,
    run_id: str,
    sampling_salt: str,
    additional_exposure_contract_paths: tuple[Path, ...] = (),
) -> MatchedCapabilityLadderPopulation:
    if output_path.exists():
        raise ValueError("matched ladder population is immutable and exists")
    source_artifacts_path = source_artifacts_path.resolve()
    regression_contract_path = regression_contract_path.resolve()
    regression_report_path = regression_report_path.resolve()
    additional_exposure_contract_paths = tuple(
        item.resolve() for item in additional_exposure_contract_paths
    )
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
        raise ValueError("matched ladder lacks a passing public-contract regression")
    regression_population_path = resolve_regression_population_path(regression)
    source_population = CapabilitySensitiveFrontierPopulation.model_validate_json(
        regression_population_path.read_text(encoding="utf-8")
    )
    if Path(source_population.source_artifacts_path).resolve() != source_artifacts_path:
        raise ValueError("matched ladder source artifacts differ from the regression population")
    if _sha256(source_artifacts_path) != source_population.source_artifacts_sha256:
        raise ValueError("matched ladder source artifacts changed after regression")

    additional_exposure_references = tuple(
        _make_exposure_contract_reference(item)
        for item in additional_exposure_contract_paths
    )
    exposed_tasks = tuple(
        (
            *load_exposed_tasks(regression),
            *load_exposed_tasks_from_references(additional_exposure_references),
        )
    )
    excluded_signatures = tuple(
        sorted({core_task_semantic_signature(item) for item in exposed_tasks})
    )
    pool = _load_evidence_pool(source_artifacts_path)
    builder = _CapabilityTaskBuilder(pool, sampling_salt=sampling_salt)
    groups = _build_matched_groups(
        builder,
        excluded_signatures=set(excluded_signatures),
    )
    protocol = regression.protocol_profile
    identity_values = {
        "run_id": run_id,
        "source_artifacts_path": str(source_artifacts_path),
        "source_artifacts_sha256": _sha256(source_artifacts_path),
        "regression_contract_id": regression.contract_id,
        "regression_report_id": regression_report.report_id,
        "excluded_core_signature_set_hash": signature_set_hash(
            excluded_signatures,
            prefix="finance_matched_excluded_core_signatures:",
        ),
        "sampling_salt": sampling_salt,
        "protocol_profile_hash": protocol.profile_hash,
        "group_hashes": tuple(item.group_hash for item in groups),
    }
    population_id = canonical_hash(
        identity_values,
        prefix="finance_matched_capability_ladder_population:",
    )
    records = []
    for group in groups:
        for task in group.variants:
            for runtime in CapabilityRuntimeArm:
                context, manifest, _ = make_v25_native_runtime_context(
                    task,
                    runtime,
                    protocol,
                )
                records.append(
                    make_public_contract_record(
                        task=task,
                        runtime_arm=cast(Any, runtime.value),
                        runtime_task=context.task,
                        manifest=manifest,
                        maximum_required_tool_calls=MAXIMUM_REQUIRED_TOOL_CALLS,
                    )
                )
    static_audit = make_public_contract_audit(
        population_id=population_id,
        records=tuple(records),
    )
    audit = make_matched_ladder_audit(
        groups,
        excluded_core_signatures=excluded_signatures,
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
        "additional_exposure_contract_references": additional_exposure_references,
        "excluded_core_signatures": excluded_signatures,
        "excluded_core_signature_set_hash": signature_set_hash(
            excluded_signatures,
            prefix="finance_matched_excluded_core_signatures:",
        ),
        "sampling_salt": sampling_salt,
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
    population = MatchedCapabilityLadderPopulation(
        population_id=population_id,
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, population.model_dump(mode="json"))
    return population


def _build_matched_groups(
    builder: _CapabilityTaskBuilder,
    *,
    excluded_signatures: set[str],
) -> tuple[MatchedLadderGroup, ...]:
    groups: list[MatchedLadderGroup] = []
    used_core_signatures: set[str] = set()
    used_public_evidence_ids: set[str] = set()
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        built = 0
        candidates = (
            builder._cross_candidates(family, DifficultyTier.EASY_CONTROL)
            if family == "finance.branching_operation_plan"
            else builder._temporal_candidates(family, DifficultyTier.EASY_CONTROL)
        )
        for gold, program, original_instruction, answer_projection in candidates:
            gold_ids = {item.evidence_id for item in gold}
            if gold_ids & used_public_evidence_ids:
                continue
            selected = builder._select_distractors(
                family,
                gold,
                DifficultyTier.HARD_CONTROL,
            )
            if selected is None:
                continue
            hard_distractors, hard_recovery = selected
            if len(hard_distractors) != 6 or len(hard_recovery) < 2:
                continue
            if any(_public_selector_collision(item, gold) for item in hard_distractors):
                continue
            if {item.evidence_id for item in hard_distractors} & used_public_evidence_ids:
                continue
            frontier_distractors = _frontier_subset(
                gold,
                hard_distractors,
                required_recovery_id=hard_recovery[0].distractor_evidence_id,
            )
            if frontier_distractors is None:
                continue
            frontier_recovery = (
                RecoveryBranch(
                    distractor_evidence_id=hard_recovery[0].distractor_evidence_id,
                    mismatch_fields=hard_recovery[0].mismatch_fields,
                ),
            )
            hard_recovery_pair = tuple(hard_recovery[:2])
            core_instruction = _core_instruction(original_instruction)
            easy = builder._materialize(
                family=family,
                tier=DifficultyTier.EASY_CONTROL,
                gold=gold,
                distractors=(),
                recovery_branches=(),
                program=program,
                instruction=_tier_instruction(core_instruction, DifficultyTier.EASY_CONTROL),
                answer_projection=answer_projection,
            )
            signature = core_task_semantic_signature(easy)
            if signature in excluded_signatures or signature in used_core_signatures:
                continue
            frontier = builder._materialize(
                family=family,
                tier=DifficultyTier.FRONTIER,
                gold=gold,
                distractors=frontier_distractors,
                recovery_branches=frontier_recovery,
                program=program,
                instruction=_tier_instruction(core_instruction, DifficultyTier.FRONTIER),
                answer_projection=answer_projection,
            )
            hard = builder._materialize(
                family=family,
                tier=DifficultyTier.HARD_CONTROL,
                gold=gold,
                distractors=hard_distractors,
                recovery_branches=hard_recovery_pair,
                program=program,
                instruction=_tier_instruction(core_instruction, DifficultyTier.HARD_CONTROL),
                answer_projection=answer_projection,
            )
            variants = (easy, frontier, hard)
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
            used_core_signatures.add(signature)
            hard_public_ids = {item.evidence_id for item in hard.public_corpus.evidence}
            used_public_evidence_ids.update(hard_public_ids)
            builder._used_evidence_ids.update(hard_public_ids)
            built += 1
            if built == MATCHED_GROUPS_PER_FAMILY:
                break
        if built != MATCHED_GROUPS_PER_FAMILY:
            raise ValueError(
                f"real Finance Evidence supports only {built} fresh matched groups for {family}"
            )
    return tuple(
        sorted(groups, key=lambda item: (item.family, item.core_semantic_signature))
    )


def _frontier_subset(
    gold: tuple[EvidenceItem, ...],
    hard_distractors: tuple[EvidenceItem, ...],
    *,
    required_recovery_id: str,
) -> tuple[EvidenceItem, ...] | None:
    gold_sources = {item.source.source_id for item in gold}
    if len(gold_sources) != 1:
        return None
    candidates = []
    for subset in itertools.combinations(hard_distractors, 3):
        if required_recovery_id not in {item.evidence_id for item in subset}:
            continue
        if len(gold_sources | {item.source.source_id for item in subset}) != 2:
            continue
        candidates.append(subset)
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda values: canonical_hash(
            tuple(item.evidence_version_id for item in values),
            prefix="finance_matched_frontier_subset:",
        ),
    )


def _public_selector_collision(
    candidate: EvidenceItem,
    gold: tuple[EvidenceItem, ...],
) -> bool:
    return any(
        candidate.subject.name == item.subject.name
        and candidate.predicate == item.predicate
        and candidate.temporal_context.label == item.temporal_context.label
        for item in gold
    )


def _core_instruction(value: str) -> str:
    normalized = value.strip()
    lower = normalized.casefold()
    marker = "determine whether"
    if lower.startswith("discard the near-match") and marker in lower:
        start = lower.index(marker)
        normalized = normalized[start:]
        normalized = normalized[:1].upper() + normalized[1:]
    if "; stop only" in normalized.casefold():
        index = normalized.casefold().index("; stop only")
        normalized = normalized[:index].rstrip() + "."
    return normalized


def _tier_instruction(core: str, tier: DifficultyTier) -> str:
    if tier == DifficultyTier.EASY_CONTROL:
        return core
    if tier == DifficultyTier.FRONTIER:
        return (
            f"{core} Use the public archive to resolve one registered near-match branch, "
            "reconcile metric definition and period, and verify every selected observation "
            "before returning the same requested result."
        )
    return (
        f"{core} Use staged archive search to resolve two registered near-match branches; "
        "reconcile metric definition, period, and source or scope; independently verify "
        "intermediate operations and the final result; stop only after every required role "
        "and ambiguity has been resolved."
    )


def core_task_semantic_signature(
    task: CapabilitySensitiveTaskArtifact | Mapping[str, Any],
) -> str:
    raw = (
        task.model_dump(mode="json")
        if isinstance(task, CapabilitySensitiveTaskArtifact)
        else dict(task)
    )
    evidence = cast(Sequence[Mapping[str, Any]], raw["evidence_bundle"]["evidence"])
    program = cast(Mapping[str, Any], raw["task"]["oracle"]["task_program"])
    nodes = cast(Sequence[Mapping[str, Any]], program["nodes"])
    evidence_order = {
        str(item["evidence_id"]): index for index, item in enumerate(evidence)
    }
    node_order = {str(item["node_id"]): index for index, item in enumerate(nodes)}
    program_semantics = tuple(
        (
            str(node["operator_id"]),
            tuple(
                (
                    str(ref["kind"]),
                    (
                        evidence_order[str(ref["ref_id"])]
                        if str(ref["kind"]) == "evidence"
                        else node_order[str(ref["ref_id"])]
                    ),
                    ref.get("selector"),
                    ref.get("role_id"),
                )
                for ref in cast(Sequence[Mapping[str, Any]], node["input_refs"])
            ),
            cast(Mapping[str, Any], node.get("parameters", {})),
        )
        for node in nodes
    )
    evidence_semantics = tuple(
        (
            str(item["subject"]["subject_id"]),
            str(item["predicate"]),
            str(item["temporal_context"].get("label") or ""),
            str(item["definition"]["definition_id"]),
            str(item["source"]["source_id"]),
        )
        for item in evidence
    )
    return canonical_hash(
        {
            "version": MATCHED_CORE_SIGNATURE_VERSION,
            "family": str(raw["family"]),
            "evidence_semantics": evidence_semantics,
            "program_semantics": program_semantics,
            "answer_projection": raw.get("answer_projection", {}),
            "projected_expected_output": raw["projected_expected_output"],
        },
        prefix="finance_matched_core_semantics:",
    )


def matched_group_invariant_failures(
    variants: Sequence[CapabilitySensitiveTaskArtifact | Mapping[str, Any]],
) -> tuple[str, ...]:
    if len(variants) != 3:
        return ("tier_count",)
    raw = [
        item.model_dump(mode="json")
        if isinstance(item, CapabilitySensitiveTaskArtifact)
        else dict(item)
        for item in variants
    ]
    by_tier = {str(item["tier"]): item for item in raw}
    if set(by_tier) != {item.value for item in DifficultyTier}:
        return ("tier_identity",)
    ordered = [by_tier[item.value] for item in DifficultyTier]
    failures = []
    if len({str(item["family"]) for item in ordered}) != 1:
        failures.append("family")
    if len({core_task_semantic_signature(item) for item in ordered}) != 1:
        failures.append("core_semantics")

    def gold_versions(item: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(
            str(value["evidence_version_id"])
            for value in item["evidence_bundle"]["evidence"]
        )

    def gold_ids(item: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(
            str(value["evidence_id"]) for value in item["evidence_bundle"]["evidence"]
        )

    def corpus_ids(item: Mapping[str, Any]) -> set[str]:
        return {
            str(value["evidence_id"]) for value in item["public_corpus"]["evidence"]
        }

    if len({gold_versions(item) for item in ordered}) != 1:
        failures.append("gold_evidence_versions")
    if len({gold_ids(item) for item in ordered}) != 1:
        failures.append("gold_evidence_ids")
    if len(
        {
            canonical_hash(item["task"]["oracle"]["task_program"], prefix="matched_program:")
            for item in ordered
        }
    ) != 1:
        failures.append("operation_program")
    if len(
        {
            canonical_hash(item["task"]["public"]["answer_schema"], prefix="matched_answer_schema:")
            for item in ordered
        }
    ) != 1:
        failures.append("answer_schema")
    if len(
        {
            canonical_hash(item["answer_projection"], prefix="matched_answer_projection:")
            for item in ordered
        }
    ) != 1:
        failures.append("answer_projection")
    if len(
        {
            canonical_hash(item["projected_expected_output"], prefix="matched_output:")
            for item in ordered
        }
    ) != 1:
        failures.append("projected_output")
    easy_ids, frontier_ids, hard_ids = (corpus_ids(item) for item in ordered)
    if not easy_ids < frontier_ids < hard_ids:
        failures.append("public_corpus_nesting")
    distractor_counts = tuple(
        len(corpus_ids(item) - set(gold_ids(item))) for item in ordered
    )
    if distractor_counts != (0, 3, 6):
        failures.append("distractor_counts")
    for dimension in MATCHED_FIXED_DIMENSIONS:
        fixed_values = tuple(int(item["structure"][dimension]) for item in ordered)
        if len(set(fixed_values)) != 1:
            failures.append(f"fixed:{dimension}")
    for dimension in MATCHED_STRICT_DIMENSIONS:
        strict_values = tuple(float(item["structure"][dimension]) for item in ordered)
        if not strict_values[0] < strict_values[1] < strict_values[2]:
            failures.append(f"strict:{dimension}")
    if tuple(bool(item["structure"]["single_retrieval_solvable"]) for item in ordered) != (
        True,
        False,
        False,
    ):
        failures.append("single_retrieval_transition")
    if any(not bool(item["verification"]["passed"]) for item in ordered):
        failures.append("program_replay")
    return tuple(sorted(set(failures)))


def load_exposed_tasks(
    regression: FinancePublicContractRegressionContract,
) -> tuple[Mapping[str, Any], ...]:
    current_population = json.loads(
        resolve_regression_population_path(regression).read_text(encoding="utf-8")
    )
    current_by_id = {
        str(item["artifact_id"]): item for item in current_population["tasks"]
    }
    current_ids = {item.task_artifact_id for item in regression.bindings}
    if not current_ids <= set(current_by_id):
        raise ValueError("matched ladder cannot reconstruct regression tasks")
    prior = load_exposed_tasks_from_references(regression.exposure_contract_references)
    return tuple((*prior, *(current_by_id[item] for item in sorted(current_ids))))


def make_matched_ladder_audit(
    groups: tuple[MatchedLadderGroup, ...],
    *,
    excluded_core_signatures: Iterable[str],
    public_contract_audit: PublicContractSatisfiabilityAudit,
) -> MatchedLadderAudit:
    excluded = tuple(sorted(set(excluded_core_signatures)))
    selected = tuple(sorted(item.core_semantic_signature for item in groups))
    failures = {
        item.group_id: matched_group_invariant_failures(item.variants) for item in groups
    }
    family_counts = Counter(item.family for item in groups)
    gold_sets = [
        {item.evidence_id for item in group.variants[0].evidence_bundle.evidence}
        for group in groups
    ]
    public_sets = [
        {item.evidence_id for item in group.variants[-1].public_corpus.evidence}
        for group in groups
    ]
    cross_gold = _pairwise_disjoint(gold_sets)
    cross_public = _pairwise_disjoint(public_sets)
    task_count = sum(len(item.variants) for item in groups)
    replay_count = sum(
        task.verification.passed for group in groups for task in group.variants
    )
    values = {
        "group_count": len(groups),
        "task_count": task_count,
        "family_group_counts": {
            family: family_counts[family] for family in CAPABILITY_SENSITIVE_FAMILIES
        },
        "excluded_core_signature_count": len(excluded),
        "excluded_core_signature_set_hash": signature_set_hash(
            excluded,
            prefix="finance_matched_excluded_core_signatures:",
        ),
        "selected_core_signature_count": len(selected),
        "selected_core_signature_set_hash": signature_set_hash(
            selected,
            prefix="finance_matched_selected_core_signatures:",
        ),
        "fresh_core_semantics": not bool(set(excluded) & set(selected)),
        "group_invariant_pass_count": sum(not value for value in failures.values()),
        "group_failure_codes": failures,
        "cross_group_gold_disjoint": cross_gold,
        "cross_group_public_corpus_disjoint": cross_public,
        "program_replay_pass_rate": replay_count / task_count if task_count else 0.0,
        "public_contract_audit_id": public_contract_audit.audit_id,
        "public_contract_record_count": len(public_contract_audit.records),
        "public_contract_pass_rate": (
            public_contract_audit.passed_record_count
            / len(public_contract_audit.records)
        ),
    }
    ready = (
        len(groups) == MATCHED_GROUP_COUNT
        and values["family_group_counts"]
        == {family: MATCHED_GROUPS_PER_FAMILY for family in CAPABILITY_SENSITIVE_FAMILIES}
        and values["fresh_core_semantics"]
        and values["group_invariant_pass_count"] == len(groups)
        and not any(failures.values())
        and cross_gold
        and cross_public
        and values["program_replay_pass_rate"] == 1.0
        and len(public_contract_audit.records) == MATCHED_STATIC_RECORD_COUNT
        and public_contract_audit.all_public_contracts_satisfiable
    )
    values["matched_ladder_ready"] = ready
    values["next_permitted_stage"] = (
        "matched_tier_localization" if ready else "matched_ladder_repair_only"
    )
    provisional = MatchedLadderAudit.model_construct(audit_hash="pending", **values)
    return MatchedLadderAudit(
        audit_hash=matched_ladder_audit_hash(provisional),
        **values,
    )


def _pairwise_disjoint(values: Sequence[set[str]]) -> bool:
    seen: set[str] = set()
    for current in values:
        if seen & current:
            return False
        seen.update(current)
    return True


def matched_ladder_group_id(value: MatchedLadderGroup) -> str:
    return canonical_hash(
        {
            "family": value.family,
            "core_semantic_signature": value.core_semantic_signature,
            "variant_ids": tuple(item.artifact_id for item in value.variants),
        },
        prefix="finance_matched_ladder_group:",
    )


def matched_ladder_group_hash(value: MatchedLadderGroup) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"group_hash"}),
        prefix="finance_matched_ladder_group_hash:",
    )


def matched_ladder_audit_hash(value: MatchedLadderAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_hash"}),
        prefix="finance_matched_ladder_audit:",
    )


def matched_ladder_population_id(value: MatchedCapabilityLadderPopulation) -> str:
    return canonical_hash(
        {
            "run_id": value.run_id,
            "source_artifacts_path": value.source_artifacts_path,
            "source_artifacts_sha256": value.source_artifacts_sha256,
            "regression_contract_id": value.regression_contract_id,
            "regression_report_id": value.regression_report_id,
            "excluded_core_signature_set_hash": value.excluded_core_signature_set_hash,
            "sampling_salt": value.sampling_salt,
            "protocol_profile_hash": value.protocol_profile.profile_hash,
            "group_hashes": tuple(item.group_hash for item in value.groups),
        },
        prefix="finance_matched_capability_ladder_population:",
    )


def signature_set_hash(values: Iterable[str], *, prefix: str) -> str:
    return canonical_hash(tuple(sorted(set(values))), prefix=prefix)


def render_matched_ladder_report(
    population: MatchedCapabilityLadderPopulation,
) -> str:
    audit = population.audit
    lines = [
        "# Finance v25.9 Matched Capability Ladder",
        "",
        "## Authorization",
        "",
        f"- Population: {population.population_id}",
        f"- Matched groups: {audit.group_count}",
        f"- Task variants: {audit.task_count}",
        f"- Historical exposed core signatures excluded: {audit.excluded_core_signature_count}",
        "- Additional immutable exposure contracts: "
        f"{len(population.additional_exposure_contract_references)}",
        f"- Fresh core semantics: {audit.fresh_core_semantics}",
        f"- Group invariants passed: {audit.group_invariant_pass_count}/{audit.group_count}",
        f"- Cross-group Gold disjoint: {audit.cross_group_gold_disjoint}",
        f"- Cross-group public Corpus disjoint: {audit.cross_group_public_corpus_disjoint}",
        f"- Program replay pass rate: {audit.program_replay_pass_rate:.2%}",
        "- Static public contract: "
        f"{population.public_contract_audit.passed_record_count}/"
        f"{len(population.public_contract_audit.records)}",
        f"- Matched ladder ready: {audit.matched_ladder_ready}",
        f"- Next permitted stage: {audit.next_permitted_stage}",
        "- API calls in construction: 0",
        "- Pro/Flash ranking, Exact Target, GP-C, and Contribution remain unauthorized.",
        "",
        "## Matched Identity Contract",
        "",
        "Within each group, Easy, Frontier, and Hard share the exact Gold Evidence versions, "
        "entity/metric/period semantics, Operation Program, answer schema, answer projection, "
        "and projected output. Only public distractors and Agent workflow requirements change.",
        "",
        "| Family | Groups |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {family} | {audit.family_group_counts[family]} |"
        for family in CAPABILITY_SENSITIVE_FAMILIES
    )
    lines.extend(
        [
            "",
            "## Tier Contract",
            "",
            "| Dimension | Easy | Frontier | Hard |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    representative = population.groups[0]
    by_tier = {item.tier: item for item in representative.variants}
    for dimension in (*MATCHED_FIXED_DIMENSIONS, *MATCHED_STRICT_DIMENSIONS):
        lines.append(
            f"| {dimension} | "
            f"{getattr(by_tier[DifficultyTier.EASY_CONTROL].structure, dimension)} | "
            f"{getattr(by_tier[DifficultyTier.FRONTIER].structure, dimension)} | "
            f"{getattr(by_tier[DifficultyTier.HARD_CONTROL].structure, dimension)} |"
        )
    return "\n".join(lines) + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a fresh, semantically matched Finance capability ladder"
    )
    parser.add_argument("--source-artifacts", type=Path, required=True)
    parser.add_argument("--regression-contract", type=Path, required=True)
    parser.add_argument("--regression-report", type=Path, required=True)
    parser.add_argument(
        "--additional-exposure-contract",
        type=Path,
        action="append",
        default=[],
        dest="additional_exposure_contracts",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sampling-salt", required=True)
    args = parser.parse_args(argv)
    population = build_matched_capability_ladder_population(
        source_artifacts_path=args.source_artifacts,
        regression_contract_path=args.regression_contract,
        regression_report_path=args.regression_report,
        output_path=args.output,
        run_id=args.run_id,
        sampling_salt=args.sampling_salt,
        additional_exposure_contract_paths=tuple(args.additional_exposure_contracts),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_matched_ladder_report(population), encoding="utf-8")
    print(
        json.dumps(
            {
                "population_id": population.population_id,
                "group_count": population.audit.group_count,
                "task_count": population.audit.task_count,
                "static_contract_pass_count": (
                    population.public_contract_audit.passed_record_count
                ),
                "static_contract_record_count": len(
                    population.public_contract_audit.records
                ),
                "matched_ladder_ready": population.audit.matched_ladder_ready,
                "next_permitted_stage": population.audit.next_permitted_stage,
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
