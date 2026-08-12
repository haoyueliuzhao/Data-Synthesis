from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.program import InputRefKind
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    MAXIMUM_REQUIRED_TOOL_CALLS,
    CapabilityRuntimeArm,
    make_v25_native_runtime_context,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
    _CapabilityTaskBuilder,
    _cross_entity_program,
    _load_evidence_pool,
    _temporal_program,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_regression import (
    FinancePublicContractRegressionContract,
    FinancePublicContractRegressionReport,
    public_task_exposure_signature,
    resolve_regression_population_path,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_satisfiability import (
    PublicContractSatisfiabilityRecord,
    make_public_contract_record,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

STRUCTURAL_LADDER_VERSION = "finance_structural_capability_ladder.v1"
STRUCTURAL_LADDER_AUDIT_VERSION = "finance_structural_capability_ladder_audit.v1"
STRUCTURAL_ANCHOR_VERSION = "finance_structural_ladder_anchor.v1"

# Direct Runtime exposes calculation, reconciliation, and verification. Retrieval recovery
# and stopping remain in the workflow ladder because Direct fixes those decisions in Host code.
STRUCTURAL_FAMILIES: tuple[str, ...] = (
    "finance.branching_operation_plan",
    "finance.multi_hop_retrieval_join",
    "finance.calculation_chain",
    "finance.definition_reconciliation",
    "finance.verification_sensitive_selection",
)
STRUCTURAL_GROUPS_PER_FAMILY = 3
STRUCTURAL_GROUP_COUNT = len(STRUCTURAL_FAMILIES) * STRUCTURAL_GROUPS_PER_FAMILY
STRUCTURAL_TASK_COUNT = STRUCTURAL_GROUP_COUNT * len(DifficultyTier)
STRUCTURAL_STATIC_RECORD_COUNT = STRUCTURAL_TASK_COUNT


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StructuralLadderGroup(FrozenModel):
    group_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    anchor_signature: str = Field(min_length=1)
    variants: tuple[CapabilitySensitiveTaskArtifact, ...] = Field(
        min_length=3,
        max_length=3,
    )
    group_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_group(self) -> StructuralLadderGroup:
        if self.family not in STRUCTURAL_FAMILIES:
            raise ValueError("structural ladder uses a non-Direct capability family")
        failures = structural_group_invariant_failures(self.variants)
        if failures:
            raise ValueError(f"structural ladder violates:{','.join(failures)}")
        if {item.family for item in self.variants} != {self.family}:
            raise ValueError("structural ladder group crosses families")
        if self.anchor_signature != structural_anchor_signature(self.variants):
            raise ValueError("structural ladder anchor identity is invalid")
        if self.group_id != structural_group_id(self):
            raise ValueError("structural ladder group identity is invalid")
        if self.group_hash != structural_group_hash(self):
            raise ValueError("structural ladder group hash is invalid")
        return self


class StructuralLadderAudit(FrozenModel):
    group_count: int = Field(ge=1)
    task_count: int = Field(ge=1)
    family_group_counts: dict[str, int]
    excluded_exposure_signature_count: int = Field(ge=1)
    excluded_exposure_signature_set_hash: str = Field(min_length=1)
    selected_exposure_signature_count: int = Field(ge=1)
    selected_exposure_signature_set_hash: str = Field(min_length=1)
    fresh_task_semantics: bool
    group_invariant_pass_count: int = Field(ge=0)
    group_failure_codes: dict[str, tuple[str, ...]]
    cross_group_gold_disjoint: bool
    public_corpus_equals_gold: bool
    nested_gold_rate: float = Field(ge=0, le=1)
    operation_depth_monotonic_rate: float = Field(ge=0, le=1)
    evidence_reference_coverage_rate: float = Field(ge=0, le=1)
    program_replay_pass_rate: float = Field(ge=0, le=1)
    public_contract_record_count: int = Field(ge=1)
    public_contract_pass_rate: float = Field(ge=0, le=1)
    structural_ladder_ready: bool
    next_permitted_stage: str = Field(min_length=1)
    audit_hash: str = Field(min_length=1)
    schema_version: str = STRUCTURAL_LADDER_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StructuralLadderAudit:
        if self.schema_version != STRUCTURAL_LADDER_AUDIT_VERSION:
            raise ValueError("structural ladder audit version is unsupported")
        if self.group_count != STRUCTURAL_GROUP_COUNT:
            raise ValueError("structural ladder group denominator is incomplete")
        if self.task_count != STRUCTURAL_TASK_COUNT:
            raise ValueError("structural ladder task denominator is incomplete")
        expected_family_counts = {
            family: STRUCTURAL_GROUPS_PER_FAMILY for family in STRUCTURAL_FAMILIES
        }
        if self.family_group_counts != expected_family_counts:
            raise ValueError("structural ladder is not balanced by family")
        expected_ready = (
            self.fresh_task_semantics
            and self.group_invariant_pass_count == self.group_count
            and not any(self.group_failure_codes.values())
            and self.cross_group_gold_disjoint
            and self.public_corpus_equals_gold
            and self.nested_gold_rate == 1.0
            and self.operation_depth_monotonic_rate == 1.0
            and self.evidence_reference_coverage_rate == 1.0
            and self.program_replay_pass_rate == 1.0
            and self.public_contract_record_count == STRUCTURAL_STATIC_RECORD_COUNT
            and self.public_contract_pass_rate == 1.0
        )
        if self.structural_ladder_ready != expected_ready:
            raise ValueError("structural ladder readiness is inconsistent")
        expected_stage = (
            "direct_structural_tier_localization"
            if expected_ready
            else "structural_ladder_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("structural ladder transition is not fail-closed")
        if self.audit_hash != structural_ladder_audit_hash(self):
            raise ValueError("structural ladder audit identity is invalid")
        return self


class StructuralCapabilityLadderPopulation(FrozenModel):
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
    excluded_exposure_signatures: tuple[str, ...] = Field(min_length=1)
    excluded_exposure_signature_set_hash: str = Field(min_length=1)
    sampling_salt: str = Field(min_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    groups: tuple[StructuralLadderGroup, ...] = Field(
        min_length=STRUCTURAL_GROUP_COUNT,
        max_length=STRUCTURAL_GROUP_COUNT,
    )
    public_contract_records: tuple[PublicContractSatisfiabilityRecord, ...] = Field(
        min_length=STRUCTURAL_STATIC_RECORD_COUNT,
        max_length=STRUCTURAL_STATIC_RECORD_COUNT,
    )
    audit: StructuralLadderAudit
    model_api_calls: int = Field(default=0, ge=0, le=0)
    validation_objective_access: str = "forbidden"
    authorization_objective_access: str = "forbidden"
    exact_target_evaluated: bool = False
    gp_c_evaluated: bool = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = STRUCTURAL_LADDER_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> StructuralCapabilityLadderPopulation:
        if self.schema_version != STRUCTURAL_LADDER_VERSION:
            raise ValueError("structural ladder population version is unsupported")
        if tuple(sorted(set(self.excluded_exposure_signatures))) != (
            self.excluded_exposure_signatures
        ):
            raise ValueError("structural exposure exclusions are not canonical")
        if self.excluded_exposure_signature_set_hash != signature_set_hash(
            self.excluded_exposure_signatures,
            prefix="finance_structural_excluded_exposures:",
        ):
            raise ValueError("structural exposure exclusion hash is invalid")
        if len({item.group_id for item in self.groups}) != len(self.groups):
            raise ValueError("structural ladder duplicates group identities")
        if len({item.anchor_signature for item in self.groups}) != len(self.groups):
            raise ValueError("structural ladder duplicates anchors")
        if {item.runtime_arm for item in self.public_contract_records} != {
            CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL.value
        }:
            raise ValueError("structural static audit includes a non-Direct Runtime")
        expected = make_structural_ladder_audit(
            self.groups,
            excluded_exposure_signatures=self.excluded_exposure_signatures,
            public_contract_records=self.public_contract_records,
        )
        if self.audit != expected:
            raise ValueError("structural ladder audit differs from frozen groups")
        if self.population_id != structural_population_id(self):
            raise ValueError("structural ladder population identity is invalid")
        return self

    @property
    def tasks(self) -> tuple[CapabilitySensitiveTaskArtifact, ...]:
        return tuple(
            sorted(
                (task for group in self.groups for task in group.variants),
                key=lambda item: (item.family, item.tier.value, item.artifact_id),
            )
        )


def build_structural_capability_ladder_population(
    *,
    source_artifacts_path: Path,
    regression_contract_path: Path,
    regression_report_path: Path,
    output_path: Path,
    run_id: str,
    sampling_salt: str,
) -> StructuralCapabilityLadderPopulation:
    if output_path.exists():
        raise ValueError("structural ladder population is immutable and exists")
    source_artifacts_path = source_artifacts_path.resolve()
    regression_contract_path = regression_contract_path.resolve()
    regression_report_path = regression_report_path.resolve()
    regression = FinancePublicContractRegressionContract.model_validate_json(
        regression_contract_path.read_text(encoding="utf-8")
    )
    regression_report = FinancePublicContractRegressionReport.model_validate_json(
        regression_report_path.read_text(encoding="utf-8")
    )
    if (
        regression_report.contract_id != regression.contract_id
        or regression_report.status != "passed"
        or regression_report.next_permitted_stage
        != "matched_ladder_construction_only"
    ):
        raise ValueError("structural ladder lacks a passing fresh regression")
    source_population = CapabilitySensitiveFrontierPopulation.model_validate_json(
        resolve_regression_population_path(regression).read_text(encoding="utf-8")
    )
    if Path(source_population.source_artifacts_path).resolve() != source_artifacts_path:
        raise ValueError("structural ladder source differs from regression source")
    if _sha256(source_artifacts_path) != source_population.source_artifacts_sha256:
        raise ValueError("structural ladder source artifacts changed")
    excluded_signatures = tuple(
        sorted(
            set(regression.excluded_task_signatures)
            | set(regression.selected_task_signatures)
        )
    )
    pool = _load_evidence_pool(source_artifacts_path)
    builder = _CapabilityTaskBuilder(pool, sampling_salt=sampling_salt)
    groups = _build_structural_groups(
        builder,
        excluded_signatures=set(excluded_signatures),
    )
    protocol = regression.protocol_profile
    records = []
    for group in groups:
        for task in group.variants:
            context, manifest, _ = make_v25_native_runtime_context(
                task,
                CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL,
                protocol,
            )
            records.append(
                make_public_contract_record(
                    task=task,
                    runtime_arm=CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL.value,
                    runtime_task=context.task,
                    manifest=manifest,
                    maximum_required_tool_calls=MAXIMUM_REQUIRED_TOOL_CALLS,
                )
            )
    frozen_records = tuple(records)
    audit = make_structural_ladder_audit(
        groups,
        excluded_exposure_signatures=excluded_signatures,
        public_contract_records=frozen_records,
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
        "excluded_exposure_signatures": excluded_signatures,
        "excluded_exposure_signature_set_hash": signature_set_hash(
            excluded_signatures,
            prefix="finance_structural_excluded_exposures:",
        ),
        "sampling_salt": sampling_salt,
        "protocol_profile": protocol,
        "groups": groups,
        "public_contract_records": frozen_records,
        "audit": audit,
        "model_api_calls": 0,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = StructuralCapabilityLadderPopulation.model_construct(
        population_id="pending",
        **values,
    )
    population = StructuralCapabilityLadderPopulation(
        population_id=structural_population_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, population.model_dump(mode="json"))
    return population


def _build_structural_groups(
    builder: _CapabilityTaskBuilder,
    *,
    excluded_signatures: set[str],
) -> tuple[StructuralLadderGroup, ...]:
    groups = []
    used_gold_ids: set[str] = set()
    used_task_signatures: set[str] = set()
    for family in STRUCTURAL_FAMILIES:
        built = 0
        candidates = (
            builder._cross_candidates(family, DifficultyTier.HARD_CONTROL)
            if family == "finance.branching_operation_plan"
            else builder._temporal_candidates(family, DifficultyTier.HARD_CONTROL)
        )
        for hard_gold, _, _, _ in candidates:
            hard_ids = {item.evidence_id for item in hard_gold}
            if hard_ids & used_gold_ids:
                continue
            specs = _nested_program_specs(builder, family, hard_gold)
            variants = tuple(
                builder._materialize(
                    family=family,
                    tier=tier,
                    gold=gold,
                    distractors=(),
                    recovery_branches=(),
                    program=program,
                    instruction=instruction,
                    answer_projection=projection,
                )
                for tier, (gold, program, instruction, projection) in zip(
                    DifficultyTier,
                    specs,
                    strict=True,
                )
            )
            signatures = {
                public_task_exposure_signature(item) for item in variants
            }
            if signatures & (excluded_signatures | used_task_signatures):
                continue
            if structural_group_invariant_failures(variants):
                continue
            anchor = structural_anchor_signature(variants)
            group_values = {
                "family": family,
                "anchor_signature": anchor,
                "variants": variants,
            }
            provisional = StructuralLadderGroup.model_construct(
                group_id="pending",
                group_hash="pending",
                **group_values,
            )
            group_id = structural_group_id(provisional)
            with_id = StructuralLadderGroup.model_construct(
                group_id=group_id,
                group_hash="pending",
                **group_values,
            )
            group = StructuralLadderGroup(
                group_id=group_id,
                group_hash=structural_group_hash(with_id),
                **group_values,
            )
            groups.append(group)
            used_gold_ids.update(hard_ids)
            used_task_signatures.update(signatures)
            built += 1
            if built == STRUCTURAL_GROUPS_PER_FAMILY:
                break
        if built != STRUCTURAL_GROUPS_PER_FAMILY:
            raise ValueError(
                f"real Finance Evidence supports only {built} structural groups for {family}"
            )
    return tuple(sorted(groups, key=lambda item: (item.family, item.anchor_signature)))


def _nested_program_specs(
    builder: _CapabilityTaskBuilder,
    family: str,
    hard_gold: tuple[Any, ...],
) -> tuple[tuple[Any, ...], ...]:
    if family == "finance.branching_operation_plan":
        pairs = tuple(
            (hard_gold[index], hard_gold[index + 1])
            for index in range(0, len(hard_gold), 2)
        )
        return cast(
            tuple[tuple[Any, ...], ...],
            (
                _cross_entity_program(
                    builder._registry,
                    family,
                    DifficultyTier.EASY_CONTROL,
                    pairs[:2],
                ),
                _cross_entity_program(
                    builder._registry,
                    family,
                    DifficultyTier.FRONTIER,
                    pairs[:2],
                ),
                _cross_entity_program(
                    builder._registry,
                    family,
                    DifficultyTier.HARD_CONTROL,
                    pairs,
                ),
            ),
        )
    return cast(
        tuple[tuple[Any, ...], ...],
        tuple(
            _temporal_program(builder._registry, family, tier, hard_gold[:length])
            for tier, length in zip(DifficultyTier, (2, 3, 4), strict=True)
        ),
    )


def structural_anchor_signature(
    variants: Sequence[CapabilitySensitiveTaskArtifact | Mapping[str, Any]],
) -> str:
    raw = [
        item.model_dump(mode="json")
        if isinstance(item, CapabilitySensitiveTaskArtifact)
        else dict(item)
        for item in variants
    ]
    by_tier = {str(item["tier"]): item for item in raw}
    hard = by_tier[DifficultyTier.HARD_CONTROL.value]
    evidence = hard["evidence_bundle"]["evidence"]
    return canonical_hash(
        {
            "version": STRUCTURAL_ANCHOR_VERSION,
            "family": hard["family"],
            "subjects": tuple(
                sorted({str(item["subject"]["subject_id"]) for item in evidence})
            ),
            "predicates": tuple(sorted({str(item["predicate"]) for item in evidence})),
            "periods": tuple(
                sorted(
                    {
                        str(item["temporal_context"].get("label") or "")
                        for item in evidence
                    }
                )
            ),
            "definitions": tuple(
                sorted(
                    {str(item["definition"]["definition_id"]) for item in evidence}
                )
            ),
            "sources": tuple(
                sorted({str(item["source"]["source_id"]) for item in evidence})
            ),
        },
        prefix="finance_structural_ladder_anchor:",
    )


def structural_group_invariant_failures(
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

    def gold_ids(item: Mapping[str, Any]) -> set[str]:
        return {
            str(value["evidence_id"])
            for value in item["evidence_bundle"]["evidence"]
        }

    def corpus_ids(item: Mapping[str, Any]) -> set[str]:
        return {
            str(value["evidence_id"])
            for value in item["public_corpus"]["evidence"]
        }

    easy_ids, frontier_ids, hard_ids = (gold_ids(item) for item in ordered)
    if not easy_ids < frontier_ids < hard_ids:
        failures.append("nested_gold")
    if any(corpus_ids(item) != gold_ids(item) for item in ordered):
        failures.append("public_corpus_not_gold")
    expected_counts = (
        (2, 4, 6)
        if str(ordered[0]["family"]) == "finance.branching_operation_plan"
        else (2, 3, 4)
    )
    if tuple(len(gold_ids(item)) for item in ordered) != expected_counts:
        failures.append("gold_count")
    operation_counts = tuple(int(item["structure"]["operation_count"]) for item in ordered)
    if not operation_counts[0] < operation_counts[1] < operation_counts[2]:
        failures.append("operation_count")
    depths = tuple(int(item["structure"]["operation_dag_depth"]) for item in ordered)
    if not depths[0] < depths[1] < depths[2]:
        failures.append("operation_dag_depth")
    if any(not bool(item["verification"]["passed"]) for item in ordered):
        failures.append("program_replay")
    for item in ordered:
        referenced = {
            str(ref["ref_id"])
            for node in item["task"]["oracle"]["task_program"]["nodes"]
            for ref in node["input_refs"]
            if str(ref["kind"]) == InputRefKind.EVIDENCE.value
        }
        if referenced != gold_ids(item):
            failures.append("evidence_reference_coverage")
    return tuple(sorted(set(failures)))


def make_structural_ladder_audit(
    groups: tuple[StructuralLadderGroup, ...],
    *,
    excluded_exposure_signatures: Iterable[str],
    public_contract_records: tuple[PublicContractSatisfiabilityRecord, ...],
) -> StructuralLadderAudit:
    excluded = tuple(sorted(set(excluded_exposure_signatures)))
    selected = tuple(
        sorted(
            public_task_exposure_signature(task)
            for group in groups
            for task in group.variants
        )
    )
    failures = {
        group.group_id: structural_group_invariant_failures(group.variants)
        for group in groups
    }
    family_counts = Counter(item.family for item in groups)
    hard_gold_sets = [
        {item.evidence_id for item in group.variants[-1].evidence_bundle.evidence}
        for group in groups
    ]
    task_count = sum(len(item.variants) for item in groups)
    nested_count = sum(
        "nested_gold" not in value for value in failures.values()
    )
    depth_count = sum(
        "operation_dag_depth" not in value and "operation_count" not in value
        for value in failures.values()
    )
    reference_count = sum(
        "evidence_reference_coverage" not in value for value in failures.values()
    )
    replay_count = sum(
        task.verification.passed for group in groups for task in group.variants
    )
    values = {
        "group_count": len(groups),
        "task_count": task_count,
        "family_group_counts": {
            family: family_counts[family] for family in STRUCTURAL_FAMILIES
        },
        "excluded_exposure_signature_count": len(excluded),
        "excluded_exposure_signature_set_hash": signature_set_hash(
            excluded,
            prefix="finance_structural_excluded_exposures:",
        ),
        "selected_exposure_signature_count": len(selected),
        "selected_exposure_signature_set_hash": signature_set_hash(
            selected,
            prefix="finance_structural_selected_exposures:",
        ),
        "fresh_task_semantics": not bool(set(excluded) & set(selected)),
        "group_invariant_pass_count": sum(not value for value in failures.values()),
        "group_failure_codes": failures,
        "cross_group_gold_disjoint": _pairwise_disjoint(hard_gold_sets),
        "public_corpus_equals_gold": all(
            {item.evidence_id for item in task.public_corpus.evidence}
            == {item.evidence_id for item in task.evidence_bundle.evidence}
            for group in groups
            for task in group.variants
        ),
        "nested_gold_rate": nested_count / len(groups) if groups else 0.0,
        "operation_depth_monotonic_rate": depth_count / len(groups) if groups else 0.0,
        "evidence_reference_coverage_rate": (
            reference_count / len(groups) if groups else 0.0
        ),
        "program_replay_pass_rate": replay_count / task_count if task_count else 0.0,
        "public_contract_record_count": len(public_contract_records),
        "public_contract_pass_rate": (
            sum(item.passed for item in public_contract_records)
            / len(public_contract_records)
            if public_contract_records
            else 0.0
        ),
    }
    ready = (
        len(groups) == STRUCTURAL_GROUP_COUNT
        and values["family_group_counts"]
        == {family: STRUCTURAL_GROUPS_PER_FAMILY for family in STRUCTURAL_FAMILIES}
        and values["fresh_task_semantics"]
        and values["group_invariant_pass_count"] == len(groups)
        and not any(failures.values())
        and values["cross_group_gold_disjoint"]
        and values["public_corpus_equals_gold"]
        and values["nested_gold_rate"] == 1.0
        and values["operation_depth_monotonic_rate"] == 1.0
        and values["evidence_reference_coverage_rate"] == 1.0
        and values["program_replay_pass_rate"] == 1.0
        and len(public_contract_records) == STRUCTURAL_STATIC_RECORD_COUNT
        and values["public_contract_pass_rate"] == 1.0
    )
    values["structural_ladder_ready"] = ready
    values["next_permitted_stage"] = (
        "direct_structural_tier_localization"
        if ready
        else "structural_ladder_repair_only"
    )
    provisional = StructuralLadderAudit.model_construct(
        audit_hash="pending",
        **values,
    )
    return StructuralLadderAudit(
        audit_hash=structural_ladder_audit_hash(provisional),
        **values,
    )


def _pairwise_disjoint(values: Sequence[set[str]]) -> bool:
    seen: set[str] = set()
    for current in values:
        if seen & current:
            return False
        seen.update(current)
    return True


def structural_group_id(value: StructuralLadderGroup) -> str:
    return canonical_hash(
        {
            "family": value.family,
            "anchor_signature": value.anchor_signature,
            "variant_ids": tuple(item.artifact_id for item in value.variants),
        },
        prefix="finance_structural_ladder_group:",
    )


def structural_group_hash(value: StructuralLadderGroup) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"group_hash"}),
        prefix="finance_structural_ladder_group_hash:",
    )


def structural_ladder_audit_hash(value: StructuralLadderAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_hash"}),
        prefix="finance_structural_ladder_audit:",
    )


def structural_population_id(value: StructuralCapabilityLadderPopulation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"population_id"}),
        prefix="finance_structural_capability_ladder_population:",
    )


def signature_set_hash(values: Iterable[str], *, prefix: str) -> str:
    return canonical_hash(tuple(sorted(values)), prefix=prefix)


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
    parser = argparse.ArgumentParser(description="Build the Finance Direct structural ladder")
    parser.add_argument("--source-artifacts", type=Path, required=True)
    parser.add_argument("--regression-contract", type=Path, required=True)
    parser.add_argument("--regression-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sampling-salt", default="finance-v25.10-structural-ladder")
    args = parser.parse_args(argv)
    population = build_structural_capability_ladder_population(
        source_artifacts_path=args.source_artifacts,
        regression_contract_path=args.regression_contract,
        regression_report_path=args.regression_report,
        output_path=args.output,
        run_id=args.run_id,
        sampling_salt=args.sampling_salt,
    )
    print(
        json.dumps(
            {
                "population_id": population.population_id,
                "group_count": len(population.groups),
                "task_count": len(population.tasks),
                "audit_id": population.audit.audit_hash,
                "ready": population.audit.structural_ladder_ready,
                "next_permitted_stage": population.audit.next_permitted_stage,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
