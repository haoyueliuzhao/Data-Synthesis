from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FINANCE_SUBMECHANISM_ORACLE_KEY,
    FinanceCapabilitySubmechanismRuntime,
    FinanceSubmechanismScenario,
    SubmechanismKind,
    evidence_roles_from_items,
    make_finance_submechanism_scenario,
    make_submechanism_manifest,
    public_submechanism_contract,
    submechanism_policy_manifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    MAXIMUM_FAILED_TOOL_CALLS,
    MAXIMUM_OBSERVATION_BYTES,
    MAXIMUM_TOOL_CALLS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_development import (
    _candidate_iterator,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_ir import (
    CORE_FAMILY_BY_MECHANISM,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
    RecoveryBranch,
    _CapabilityTaskBuilder,
    _load_evidence_pool,
    _minimum_mismatch_fields,
    capability_sensitive_task_artifact_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_direction_design import (  # noqa: E501
    CapabilitySubmechanismDirectionReport,
    CapabilitySubmechanismSpec,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_capability_population import (  # noqa: E501
    ANSWER_PROJECTION_CONTRACT_VERSION,
    finance_answer_contract_metadata,
    finance_public_calculation_instruction,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import AgentToolCall, AgentToolResult

SUBMECHANISM_POPULATION_VERSION = "finance_capability_submechanism_population.v10"
SUBMECHANISM_TASK_VERSION = "finance_capability_submechanism_task.v9"
SUBMECHANISM_REPLAY_VERSION = "finance_capability_submechanism_runtime_replay.v2"
SUBMECHANISM_AUDIT_VERSION = "finance_capability_submechanism_static_audit.v10"

BOUNDARY_BASE_TIER = DifficultyTier.EASY_CONTROL
PUBLIC_SUBMECHANISM_METADATA_KEY = "capability_decision_contract"
PUBLIC_HOST_EVENTS = ("observe:typed_host_state", "resolve:typed_host_state")

SELECTED_TASK_COUNT = 20
SELECTED_PER_PARENT = 5
PUBLIC_TOOLS = (
    "search_archive",
    "open_document",
    "query_structured_fact",
    "calculator",
    "normalize_metric_unit_period",
    "cross_check_evidence",
)

_RECOVERY_BRANCH_KINDS = frozenset(
    {
        "parameter_field_correction",
        "missing_prerequisite_evidence",
        "tool_switch",
        "operation_reference_repair",
        "selector_scope_correction",
        "retrieval_failure",
        "argument_failure",
        "calculation_prerequisite_failure",
        "evidence_conflict",
        "empty_result_tool_fallback",
        "unresolved_conflict_cannot_stop",
    }
)
_CANDIDATE_TARGET = {
    "unit_error": "unit",
    "source_definition_error": "definition_id",
    "local_calculation_error": "value",
    "entity_scope_error": "entity_scope",
}
_PREFERRED_DISTRACTOR_FIELD = {
    "parameter_field_correction": "predicate",
    "selector_scope_correction": "period",
    "unit_error": "payload_context",
    "source_definition_error": "definition",
    "entity_scope_error": "subject",
    "evidence_conflict": "definition",
    "unresolved_conflict_cannot_stop": "definition",
    "uncertain_source_coverage": "source",
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SubmechanismRuntimeReplay(FrozenModel):
    replay_id: str = Field(min_length=1)
    submechanism_id: str = Field(min_length=1)
    trigger_observed: bool
    resolution_observed: bool
    required_event_log: tuple[str, str]
    observed_event_log: tuple[str, ...]
    wrong_branch_rejected: bool
    final_verification_passed: bool
    post_completion_extra_action_rejected: bool | None = None
    passed: bool
    schema_version: str = SUBMECHANISM_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_replay(self) -> SubmechanismRuntimeReplay:
        expected = (
            self.trigger_observed
            and self.resolution_observed
            and self.wrong_branch_rejected
            and self.final_verification_passed
            and (self.post_completion_extra_action_rejected is not False)
            and tuple(self.observed_event_log) == self.required_event_log
        )
        if self.passed != expected:
            raise ValueError("submechanism Runtime replay decision is inconsistent")
        if self.replay_id != submechanism_replay_id(self):
            raise ValueError("submechanism Runtime replay identity is invalid")
        return self


class CapabilitySubmechanismTask(FrozenModel):
    task_record_id: str = Field(min_length=1)
    submechanism_id: str = Field(min_length=1)
    parent_mechanism_id: str = Field(min_length=1)
    spec_hash: str = Field(min_length=1)
    artifact: CapabilitySensitiveTaskArtifact
    scenario: FinanceSubmechanismScenario
    runtime_replay: SubmechanismRuntimeReplay
    source_semantic_signature: str = Field(min_length=1)
    materializer_hash: str = Field(min_length=1)
    base_tier: DifficultyTier
    schema_version: str = SUBMECHANISM_TASK_VERSION

    @model_validator(mode="after")
    def validate_task(self) -> CapabilitySubmechanismTask:
        if self.base_tier != BOUNDARY_BASE_TIER or self.artifact.tier != self.base_tier:
            raise ValueError("submechanism task does not use the frozen Easy base tier")
        if (
            self.submechanism_id != self.scenario.submechanism_id
            or self.parent_mechanism_id != self.scenario.parent_mechanism_id
        ):
            raise ValueError("submechanism task and Runtime scenario identities differ")
        frozen = self.artifact.task.oracle.selection_contract.get(FINANCE_SUBMECHANISM_ORACLE_KEY)
        if frozen != self.scenario.model_dump(mode="json"):
            raise ValueError("submechanism task did not freeze its Runtime scenario")
        public = self.artifact.task.public.metadata.get(PUBLIC_SUBMECHANISM_METADATA_KEY)
        if public != public_submechanism_contract(self.scenario):
            raise ValueError("submechanism public contract differs from its safe projection")
        if not _answer_contract_ready(self.artifact):
            raise ValueError("submechanism task lacks the projected public answer contract")
        if not self.runtime_replay.passed:
            raise ValueError("submechanism task lacks a passing Host replay")
        if self.task_record_id != submechanism_task_record_id(self):
            raise ValueError("submechanism task identity is invalid")
        return self


class CapabilitySubmechanismStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    selected_task_count: int = Field(ge=1)
    parent_task_counts: dict[str, int]
    operation_replay_pass_rate: float = Field(ge=0, le=1)
    runtime_scenario_coverage_rate: float = Field(ge=0, le=1)
    host_replay_pass_rate: float = Field(ge=0, le=1)
    wrong_branch_rejection_rate: float = Field(ge=0, le=1)
    public_oracle_isolation_rate: float = Field(ge=0, le=1)
    public_mechanism_non_disclosure_rate: float = Field(ge=0, le=1)
    answer_contract_coverage_rate: float = Field(ge=0, le=1)
    within_population_evidence_disjoint: bool
    prior_evidence_disjoint: bool
    prior_evidence_version_disjoint: bool
    distinct_runtime_policy_count: int = Field(ge=1)
    distinct_materializer_count: int = Field(ge=1)
    implementation_coverage_rate: float = Field(ge=0, le=1)
    base_tier: DifficultyTier
    rejection_reasons: tuple[str, ...]
    ready: bool
    next_permitted_stage: Literal[
        "flash_submechanism_development",
        "submechanism_runtime_implementation_only",
    ]
    schema_version: str = SUBMECHANISM_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CapabilitySubmechanismStaticAudit:
        expected = not self.rejection_reasons
        if self.ready != expected:
            raise ValueError("submechanism static readiness is inconsistent")
        stage = (
            "flash_submechanism_development"
            if expected
            else "submechanism_runtime_implementation_only"
        )
        if self.next_permitted_stage != stage:
            raise ValueError("submechanism static transition is not fail-closed")
        if self.audit_id != submechanism_static_audit_id(self):
            raise ValueError("submechanism static audit identity is invalid")
        return self


class CapabilitySubmechanismPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_artifacts_path: str = Field(min_length=1)
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    source_direction_report_path: str = Field(min_length=1)
    source_direction_report_sha256: str = Field(min_length=64, max_length=64)
    source_direction_report_id: str = Field(min_length=1)
    exclusion_paths: tuple[str, ...]
    exclusion_sha256: dict[str, str]
    sampling_salt: str = Field(min_length=1)
    base_tier: DifficultyTier
    tasks: tuple[CapabilitySubmechanismTask, ...] = Field(
        min_length=SELECTED_TASK_COUNT, max_length=SELECTED_TASK_COUNT
    )
    static_audit: CapabilitySubmechanismStaticAudit
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    model_api_calls: Literal[0] = 0
    model_tokens: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "flash_submechanism_development",
        "submechanism_runtime_implementation_only",
    ]
    schema_version: str = SUBMECHANISM_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> CapabilitySubmechanismPopulation:
        if self.base_tier != BOUNDARY_BASE_TIER:
            raise ValueError("submechanism population does not freeze the Easy base tier")
        if any(item.base_tier != self.base_tier for item in self.tasks):
            raise ValueError("submechanism population mixes base tiers")
        excluded_ids, excluded_versions = _collect_excluded_identity(
            tuple(Path(item) for item in self.exclusion_paths)
        )
        if self.static_audit != make_submechanism_static_audit(
            self.tasks,
            excluded_evidence_ids=excluded_ids,
            excluded_evidence_version_ids=excluded_versions,
        ):
            raise ValueError("submechanism population audit differs from frozen tasks")
        if self.next_permitted_stage != self.static_audit.next_permitted_stage:
            raise ValueError("submechanism population transition differs from static audit")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_capability_submechanism_population_implementation:",
        ):
            raise ValueError("submechanism implementation manifest hash is invalid")
        if self.population_id != submechanism_population_id(self):
            raise ValueError("submechanism population identity is invalid")
        return self


def submechanism_replay_id(value: SubmechanismRuntimeReplay) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"replay_id"}),
        prefix="finance_capability_submechanism_runtime_replay:",
    )


def submechanism_task_record_id(value: CapabilitySubmechanismTask) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"task_record_id"}),
        prefix="finance_capability_submechanism_task_record:",
    )


def submechanism_static_audit_id(value: CapabilitySubmechanismStaticAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_capability_submechanism_static_audit:",
    )


def submechanism_population_id(value: CapabilitySubmechanismPopulation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"population_id"}),
        prefix="finance_capability_submechanism_population:",
    )


def build_submechanism_population(
    *,
    source_artifacts_path: Path,
    source_direction_report_path: Path,
    exclusion_paths: tuple[Path, ...],
    output_dir: Path,
    run_id: str,
    sampling_salt: str,
) -> CapabilitySubmechanismPopulation:
    output_path = output_dir / "finance_capability_submechanism_population.json"
    if output_path.exists():
        raise ValueError("submechanism population is immutable")
    source_artifacts_path = source_artifacts_path.resolve()
    source_direction_report_path = source_direction_report_path.resolve()
    exclusions = tuple(sorted((item.resolve() for item in exclusion_paths), key=str))
    direction = CapabilitySubmechanismDirectionReport.model_validate_json(
        source_direction_report_path.read_text(encoding="utf-8")
    )
    if (
        not direction.structural_geometry_ready
        or direction.next_permitted_stage != "submechanism_runtime_implementation_only"
    ):
        raise ValueError("submechanism population lacks its structural design authorization")
    specs = tuple(
        item
        for item in direction.candidate_specs
        if item.submechanism_id in set(direction.selected_submechanism_ids)
    )
    if len(specs) != SELECTED_TASK_COUNT:
        raise ValueError("submechanism direction report has an incomplete selection")
    excluded_ids, excluded_versions = _collect_excluded_identity(exclusions)
    pool = _load_evidence_pool(source_artifacts_path)
    builder = _CapabilityTaskBuilder(pool, sampling_salt=sampling_salt)
    used_ids = set(excluded_ids)
    used_versions = set(excluded_versions)
    tasks: list[CapabilitySubmechanismTask] = []
    for spec in specs:
        artifact, scenario, signature = _materialize_submechanism(
            builder=builder,
            spec=spec,
            evidence_pool=tuple(pool.public.values()),
            used_ids=used_ids,
            used_versions=used_versions,
            sampling_salt=sampling_salt,
        )
        replay = replay_submechanism_runtime(artifact, scenario)
        if not replay.passed:
            raise ValueError(
                "submechanism Host replay failed for "
                f"{spec.submechanism_id}: "
                + json.dumps(replay.model_dump(mode="json"), sort_keys=True)
            )
        materializer_hash = canonical_hash(
            {
                "spec_hash": spec.spec_hash,
                "scenario": scenario,
                "artifact_id": artifact.artifact_id,
                "public_corpus": artifact.public_corpus.corpus_hash,
                "policy": submechanism_policy_manifest()[scenario.intervention_kind],
                "base_tier": BOUNDARY_BASE_TIER,
            },
            prefix="finance_capability_submechanism_materializer:",
        )
        values = {
            "submechanism_id": spec.submechanism_id,
            "parent_mechanism_id": spec.parent_mechanism_id,
            "spec_hash": spec.spec_hash,
            "artifact": artifact,
            "scenario": scenario,
            "runtime_replay": replay,
            "source_semantic_signature": signature,
            "materializer_hash": materializer_hash,
            "base_tier": BOUNDARY_BASE_TIER,
        }
        provisional = CapabilitySubmechanismTask.model_construct(task_record_id="pending", **values)
        tasks.append(
            CapabilitySubmechanismTask(
                task_record_id=submechanism_task_record_id(provisional), **values
            )
        )
        used_ids.update(item.evidence_id for item in artifact.public_corpus.evidence)
        used_versions.update(item.evidence_version_id for item in artifact.public_corpus.evidence)
    frozen_tasks = tuple(tasks)
    static_audit = make_submechanism_static_audit(
        frozen_tasks,
        excluded_evidence_ids=excluded_ids,
        excluded_evidence_version_ids=excluded_versions,
    )
    implementation = _implementation_manifest()
    values = {
        "run_id": run_id,
        "source_artifacts_path": str(source_artifacts_path),
        "source_artifacts_sha256": _sha256(source_artifacts_path),
        "source_direction_report_path": str(source_direction_report_path),
        "source_direction_report_sha256": _sha256(source_direction_report_path),
        "source_direction_report_id": direction.report_id,
        "exclusion_paths": tuple(str(item) for item in exclusions),
        "exclusion_sha256": {str(item): _sha256(item) for item in exclusions},
        "sampling_salt": sampling_salt,
        "base_tier": BOUNDARY_BASE_TIER,
        "tasks": frozen_tasks,
        "static_audit": static_audit,
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_capability_submechanism_population_implementation:",
        ),
        "next_permitted_stage": static_audit.next_permitted_stage,
    }
    provisional = CapabilitySubmechanismPopulation.model_construct(
        population_id="pending", **values
    )
    population = CapabilitySubmechanismPopulation(
        population_id=submechanism_population_id(provisional), **values
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, population.model_dump(mode="json"))
    _write_json(
        output_dir / "finance_capability_submechanism_static_audit.json",
        static_audit.model_dump(mode="json"),
    )
    (output_dir / "finance_capability_submechanism_population_report.md").write_text(
        _render_report(population), encoding="utf-8"
    )
    return population


def _materialize_submechanism(
    *,
    builder: _CapabilityTaskBuilder,
    spec: CapabilitySubmechanismSpec,
    evidence_pool: tuple[EvidenceItem, ...],
    used_ids: set[str],
    used_versions: set[str],
    sampling_salt: str,
) -> tuple[CapabilitySensitiveTaskArtifact, FinanceSubmechanismScenario, str]:
    family = CORE_FAMILY_BY_MECHANISM[spec.parent_mechanism_id]
    for candidate in _candidate_iterator(builder, family, BOUNDARY_BASE_TIER):
        gold, program, source_instruction, projection = candidate
        gold_ids = {item.evidence_id for item in gold}
        gold_versions = {item.evidence_version_id for item in gold}
        if gold_ids & used_ids or gold_versions & used_versions:
            continue
        distractor = _select_distractor(
            spec,
            gold,
            evidence_pool,
            used_ids | gold_ids,
            used_versions | gold_versions,
            sampling_salt,
        )
        if distractor is None:
            continue
        recovery = (
            (
                RecoveryBranch(
                    distractor_evidence_id=distractor.evidence_id,
                    mismatch_fields=_minimum_mismatch_fields(distractor, gold),
                ),
            )
            if spec.runtime_contract.intervention_kind in _RECOVERY_BRANCH_KINDS
            else ()
        )
        artifact = builder._materialize(
            family=family,
            tier=BOUNDARY_BASE_TIER,
            gold=gold,
            distractors=(distractor,),
            recovery_branches=recovery,
            program=program,
            instruction=source_instruction,
            answer_projection=projection,
        )
        scenario = _make_scenario(
            spec,
            gold,
            distractor,
            artifact.projected_expected_output,
        )
        artifact = _freeze_scenario(
            artifact,
            scenario,
            source_instruction=source_instruction,
            projection=projection,
        )
        signature = canonical_hash(
            {
                "family": family,
                "gold_versions": tuple(item.evidence_version_id for item in gold),
                "program": program,
                "projection": projection,
                "submechanism": spec.submechanism_id,
            },
            prefix="finance_capability_submechanism_semantics:",
        )
        return artifact, scenario, signature
    raise ValueError(
        f"real Finance Evidence cannot support fresh submechanism: {spec.submechanism_id}"
    )


def _select_distractor(
    spec: CapabilitySubmechanismSpec,
    gold: tuple[EvidenceItem, ...],
    evidence_pool: Iterable[EvidenceItem],
    reserved_ids: set[str],
    reserved_versions: set[str],
    sampling_salt: str,
) -> EvidenceItem | None:
    preferred = _PREFERRED_DISTRACTOR_FIELD.get(spec.runtime_contract.intervention_kind)
    ranked: list[tuple[int, str, EvidenceItem]] = []
    allowed_sources = {item.source.source_id for item in gold}
    for item in evidence_pool:
        if item.evidence_id in reserved_ids or item.evidence_version_id in reserved_versions:
            continue
        mismatches = _minimum_mismatch_fields(item, gold)
        if len(mismatches) != 1:
            continue
        preference = int(mismatches[0] != preferred) if preferred else 0
        if (
            spec.runtime_contract.intervention_kind
            not in {
                "evidence_conflict",
                "source_definition_error",
                "uncertain_source_coverage",
                "unresolved_conflict_cannot_stop",
            }
            and item.source.source_id not in allowed_sources
        ):
            preference += 1
        rank = canonical_hash(
            {
                "salt": sampling_salt,
                "submechanism": spec.submechanism_id,
                "candidate": item.evidence_version_id,
            },
            prefix="finance_capability_submechanism_distractor:",
        )
        ranked.append((preference, rank, item))
    return min(ranked, key=lambda row: (row[0], row[1]))[2] if ranked else None


def _make_scenario(
    spec: CapabilitySubmechanismSpec,
    gold: tuple[EvidenceItem, ...],
    distractor: EvidenceItem,
    expected_output: Mapping[str, Any],
) -> FinanceSubmechanismScenario:
    kind = cast(SubmechanismKind, spec.runtime_contract.intervention_kind)
    canonical: dict[str, Any] | None = None
    untrusted: dict[str, Any] | None = None
    target = _CANDIDATE_TARGET.get(kind)
    if target is not None:
        canonical = _canonical_candidate(kind, gold, expected_output)
        untrusted = dict(canonical)
        untrusted[target] = _candidate_replacement(target, canonical[target], distractor)
    return make_finance_submechanism_scenario(
        submechanism_id=spec.submechanism_id,
        parent_mechanism_id=spec.parent_mechanism_id,
        intervention_kind=kind,
        expected_host_events=PUBLIC_HOST_EVENTS,
        evidence_roles=evidence_roles_from_items(gold),
        public_resolution_hint=_resolution_hint(kind),
        untrusted_candidate=untrusted,
        canonical_candidate=canonical,
        repair_target_field=target,
    )


def _canonical_candidate(
    kind: SubmechanismKind,
    gold: tuple[EvidenceItem, ...],
    expected_output: Mapping[str, Any],
) -> dict[str, Any]:
    if kind == "unit_error":
        values = sorted(
            {
                str(getattr(item.payload, "unit", ""))
                for item in gold
                if getattr(item.payload, "unit", None)
            }
        )
        return {"unit": values[0] if len(values) == 1 else values}
    if kind == "source_definition_error":
        values = sorted(
            {
                item.definition.definition_id
                for item in gold
                if item.definition.definition_id is not None
            }
        )
        if not values:
            raise ValueError("source definition repair requires a non-empty definition ID")
        return {"definition_id": values[0] if len(values) == 1 else values}
    if kind == "entity_scope_error":
        return {"entity_scope": sorted({item.subject.subject_id for item in gold})}
    if not expected_output:
        raise ValueError("local calculation repair requires a replayed expected output")
    first_key = sorted(expected_output)[0]
    return {"value": expected_output[first_key]}


def _candidate_replacement(
    target: str,
    canonical: Any,
    distractor: EvidenceItem,
) -> Any:
    if target == "unit":
        value = getattr(distractor.payload, "unit", None)
    elif target == "definition_id":
        value = distractor.definition.definition_id
    elif target == "entity_scope":
        current = list(canonical) if isinstance(canonical, list) else [str(canonical)]
        value = sorted({*current[:-1], distractor.subject.subject_id})
    else:
        try:
            numeric = Decimal(str(canonical))
        except (InvalidOperation, ValueError):
            numeric = None
        if numeric is not None and numeric.is_finite():
            delta = max(abs(numeric) * Decimal("0.03"), Decimal("0.01"))
            direction_token = distractor.provenance.content_hash or canonical_hash(
                distractor.evidence_id,
                prefix="finance_capability_submechanism_direction_fallback:",
            )
            direction_hex = direction_token.rsplit(":", 1)[-1][:2]
            direction = (
                Decimal("1")
                if int(direction_hex, 16) % 2 == 0
                else Decimal("-1")
            )
            value = format(numeric + direction * delta, "f")
        else:
            value = getattr(distractor.payload, "value", None)
    if value == canonical or value in (None, ""):
        return f"incompatible:{canonical}"
    return value


def _answer_contract_ready(artifact: CapabilitySensitiveTaskArtifact) -> bool:
    metadata = artifact.task.public.metadata
    guidance = metadata.get("agent_contract_guidance")
    if (
        metadata.get("answer_projection_contract_version")
        != ANSWER_PROJECTION_CONTRACT_VERSION
        or not isinstance(guidance, Mapping)
        or artifact.task.oracle.selection_contract.get("answer_projection")
        != artifact.answer_projection
        or "The final output rule is:" not in artifact.task.public.instruction
    ):
        return False
    reference = guidance.get("answer_reference_contract")
    operation = guidance.get("operation_execution_contract")
    observation = guidance.get("answer_observation_constraints")
    if (
        not isinstance(reference, Mapping)
        or not isinstance(operation, Mapping)
        or not isinstance(observation, Mapping)
    ):
        return False
    allowed_labels = tuple(sorted(set(artifact.answer_projection.values())))
    if tuple(reference.get("allowed_reference_labels") or ()) != allowed_labels:
        return False
    if allowed_labels:
        constraints = guidance.get("answer_field_constraints")
        if not isinstance(constraints, Mapping):
            return False
        higher_ref = constraints.get("higher_ref")
        if (
            not isinstance(higher_ref, Mapping)
            or tuple(higher_ref.get("allowed_values") or ())
            != (*allowed_labels, None)
        ):
            return False
    expected_ref = artifact.projected_expected_output.get("higher_ref")
    return expected_ref is None or str(expected_ref) in allowed_labels


def _freeze_scenario(
    artifact: CapabilitySensitiveTaskArtifact,
    scenario: FinanceSubmechanismScenario,
    *,
    source_instruction: str,
    projection: Mapping[str, str],
) -> CapabilitySensitiveTaskArtifact:
    public = artifact.task.public
    allowed = tuple(dict.fromkeys((*public.allowed_tools, *PUBLIC_TOOLS)))
    gold = tuple(artifact.evidence_bundle.evidence)
    program = artifact.task.oracle.task_program
    metadata = dict(public.metadata)
    metadata.update(
        finance_answer_contract_metadata(
            family=artifact.family,
            tier=artifact.tier,
            gold=gold,
            program=program,
            answer_projection=projection,
        )
    )
    metadata[PUBLIC_SUBMECHANISM_METADATA_KEY] = public_submechanism_contract(scenario)
    instruction = finance_public_calculation_instruction(
        _submechanism_instruction(scenario, source_instruction, projection),
        family=artifact.family,
        tier=artifact.tier,
        gold=gold,
        program=program,
    )
    updated_public = public.model_copy(
        update={
            "allowed_tools": allowed,
            "instruction": instruction,
            "metadata": metadata,
        }
    )
    oracle = artifact.task.oracle
    selection = dict(oracle.selection_contract)
    selection[FINANCE_SUBMECHANISM_ORACLE_KEY] = scenario.model_dump(mode="json")
    updated_oracle = oracle.model_copy(update={"selection_contract": selection})
    task = artifact.task.model_copy(update={"public": updated_public, "oracle": updated_oracle})
    provisional = artifact.model_copy(update={"artifact_id": "pending", "task": task})
    return artifact.model_copy(
        update={
            "artifact_id": capability_sensitive_task_artifact_id(provisional),
            "task": task,
        }
    )


def _submechanism_instruction(
    scenario: FinanceSubmechanismScenario,
    source_instruction: str,
    projection: Mapping[str, str],
) -> str:
    candidate = ""
    if scenario.untrusted_candidate is not None:
        fields = sorted(scenario.untrusted_candidate)
        candidate = (
            " The public untrusted candidate is "
            + json.dumps(scenario.untrusted_candidate, sort_keys=True)
            + "; before finalizing, audit it with cross_check_evidence. Independently derive "
            + "and validate any localized correction. If the Host requests a candidate "
            + "submission, place it only at "
            + "claim_or_result.candidate_payload with "
            + f"exactly these fields: {fields}. Do not substitute the final-answer object for "
            + "the candidate payload."
        )
    return (
        "Use the frozen Archive tools to solve the financial task from public evidence and "
        "typed Host observations. Do not assume a hidden intervention label or a preselected "
        "repair branch. Treat observed completion, conflict, and retry state as authoritative; "
        "when no executable prerequisite is supplied, select the next action from the public "
        "tool schemas. Finalize only when the observed state supports it."
        f"{candidate} "
        f"{source_instruction} The final answer uses the public labels "
        f"{sorted(set(projection.values())) or ['value']}."
    )


def _resolution_hint(kind: SubmechanismKind) -> str:
    hints = {
        "parameter_field_correction": (
            "Inspect the typed field error and patch one public selector field."
        ),
        "missing_prerequisite_evidence": (
            "Retrieve the missing public Evidence operand before recalculating."
        ),
        "tool_switch": ("Switch from broad Archive search to the typed structured-fact route."),
        "operation_reference_repair": (
            "Copy the current operation_ref and use selector=payload.value for scalar output."
        ),
        "selector_scope_correction": (
            "Patch the period or public scope filter using the observed fact labels."
        ),
        "unit_error": ("Derive the unit from selected Evidence and repair only the unit field."),
        "source_definition_error": (
            "Compare definitions and retain only the compatible SourceDefinition."
        ),
        "local_calculation_error": ("Replay the calculation and repair only the candidate value."),
        "insufficient_evidence": ("Retrieve every missing required role before re-verification."),
        "entity_scope_error": (
            "Rebuild the entity scope from selected Evidence and repair only that field."
        ),
        "retrieval_failure": (
            "Reformulate with Archive search after the typed route returns no result."
        ),
        "argument_failure": ("Patch the rejected typed argument using public selector labels."),
        "calculation_prerequisite_failure": (
            "Retrieve the missing operand before retrying calculation."
        ),
        "evidence_conflict": (
            "Normalize source definitions before resolving the Evidence conflict."
        ),
        "empty_result_tool_fallback": (
            "Switch to Archive search and inspect the returned alternative route."
        ),
        "incomplete_continue": (
            "The observed completion state is incomplete; select the next action from the "
            "public missing-role state and tool schemas."
        ),
        "post_complete_error_risk": (
            "The Host reports verified completion and an elevated integrity risk for an "
            "additional action."
        ),
        "post_complete_cost": (
            "The Host reports verified completion and a positive marginal cost for an "
            "additional action."
        ),
        "unresolved_conflict_cannot_stop": (
            "The observed evidence state remains conflicted and does not support finalization."
        ),
        "uncertain_source_coverage": (
            "Inspect provenance for the selected source before final verification."
        ),
    }
    return hints[kind]


def replay_submechanism_runtime(
    artifact: CapabilitySensitiveTaskArtifact,
    scenario: FinanceSubmechanismScenario,
) -> SubmechanismRuntimeReplay:
    manifest = make_submechanism_manifest(
        corpus=artifact.public_corpus,
        scenario=scenario,
        environment_id=f"finance_v25_25:replay:{artifact.artifact_id}",
        maximum_tool_calls=MAXIMUM_TOOL_CALLS,
        maximum_failed_tool_calls=MAXIMUM_FAILED_TOOL_CALLS,
        maximum_total_observation_bytes=MAXIMUM_OBSERVATION_BYTES,
    )
    runtime = FinanceCapabilitySubmechanismRuntime(
        artifact.public_corpus, manifest, scenario=scenario
    )
    calls = _ReplayCalls(runtime)
    kind = scenario.intervention_kind
    wrong_rejected = replay_wrong_branch_rejection(artifact, scenario)
    post_rejected: bool | None = None
    if kind in {
        "parameter_field_correction",
        "selector_scope_correction",
        "argument_failure",
        "retrieval_failure",
        "empty_result_tool_fallback",
        "tool_switch",
    }:
        calls.trigger_and_resolve_selector(kind)
    elif kind in {
        "missing_prerequisite_evidence",
        "calculation_prerequisite_failure",
    }:
        calls.trigger_calculator_then_retrieve()
    elif kind == "operation_reference_repair":
        calls.trigger_and_repair_operation_reference()
    elif kind in _CANDIDATE_TARGET:
        calls.verify_and_repair_candidate()
    elif kind in {"evidence_conflict", "unresolved_conflict_cannot_stop"}:
        calls.resolve_conflict()
    elif kind in {"insufficient_evidence", "incomplete_continue"}:
        calls.complete_missing_roles()
    elif kind == "uncertain_source_coverage":
        calls.complete_source_coverage()
    else:
        calls.verify_complete()
        post_rejected = calls.extra_action_rejected()
    final_verified = calls.ensure_final_verification()
    values = {
        "submechanism_id": scenario.submechanism_id,
        "trigger_observed": scenario.expected_host_events[0] in runtime.event_log,
        "resolution_observed": scenario.expected_host_events[1] in runtime.event_log,
        "required_event_log": scenario.expected_host_events,
        "observed_event_log": runtime.event_log,
        "wrong_branch_rejected": wrong_rejected,
        "final_verification_passed": final_verified,
        "post_completion_extra_action_rejected": post_rejected,
    }
    provisional = SubmechanismRuntimeReplay.model_construct(
        replay_id="pending", passed=False, **values
    )
    passed = (
        values["trigger_observed"]
        and values["resolution_observed"]
        and values["wrong_branch_rejected"]
        and values["final_verification_passed"]
        and values["post_completion_extra_action_rejected"] is not False
        and values["observed_event_log"] == values["required_event_log"]
    )
    provisional = provisional.model_copy(update={"passed": passed})
    return SubmechanismRuntimeReplay(
        replay_id=submechanism_replay_id(provisional),
        passed=passed,
        **values,
    )


def replay_wrong_branch_rejection(
    artifact: CapabilitySensitiveTaskArtifact,
    scenario: FinanceSubmechanismScenario,
) -> bool:
    manifest = make_submechanism_manifest(
        corpus=artifact.public_corpus,
        scenario=scenario,
        environment_id=f"finance_v25_25:negative_replay:{artifact.artifact_id}",
        maximum_tool_calls=MAXIMUM_TOOL_CALLS,
        maximum_failed_tool_calls=MAXIMUM_FAILED_TOOL_CALLS,
        maximum_total_observation_bytes=MAXIMUM_OBSERVATION_BYTES,
    )
    runtime = FinanceCapabilitySubmechanismRuntime(
        artifact.public_corpus,
        manifest,
        scenario=scenario,
    )
    calls = _ReplayCalls(runtime)
    kind = scenario.intervention_kind
    if kind in {"post_complete_error_risk", "post_complete_cost"}:
        calls.verify_complete()
        return calls.extra_action_rejected()
    if kind == "operation_reference_repair":
        calls.select_all()
        calls.calculate()
        calls.verify()
    elif kind in {"missing_prerequisite_evidence", "calculation_prerequisite_failure"}:
        calls.call(
            "calculator",
            {
                "operator": "lookup",
                "operands": [{"value": "0"}],
                "parameters": {},
            },
        )
    elif kind == "tool_switch":
        calls.call("search_archive", {"query": "financial fact", "limit": 6})
    elif kind in {
        "parameter_field_correction",
        "selector_scope_correction",
        "argument_failure",
        "retrieval_failure",
        "empty_result_tool_fallback",
    }:
        calls.query_role(0)
    elif kind in _CANDIDATE_TARGET:
        calls.select_all()
        calls.calculate()
        calls.verify(scenario.untrusted_candidate)
    elif kind in {"evidence_conflict", "unresolved_conflict_cannot_stop"}:
        calls.select_all()
        calls.calculate()
        calls.verify()
    elif kind in {"insufficient_evidence", "incomplete_continue"}:
        calls.query_role(0, add_filter=True)
        calls.verify()
    elif kind == "uncertain_source_coverage":
        calls.select_all()
        calls.calculate()
        calls.verify()
    else:
        raise ValueError(f"no negative replay for Finance submechanism: {kind}")
    if scenario.expected_host_events[0] not in runtime.event_log:
        return False
    policy = submechanism_policy_manifest()[kind]
    resolution_tools = set(policy["resolution_tools"])
    wrong_calls = (
        ("search_archive", {"query": "wrong branch", "limit": 1}),
        (
            "calculator",
            {
                "operator": "lookup",
                "operands": [{"value": "0"}],
                "parameters": {},
            },
        ),
        (
            "query_structured_fact",
            {
                "subject_alias": scenario.evidence_roles[0].subject_alias,
                "metric_alias": scenario.evidence_roles[0].metric_alias,
                "period_label": scenario.evidence_roles[0].period_label,
                "public_filters": {},
            },
        ),
    )
    wrong_tool, arguments = next(
        (tool, arguments) for tool, arguments in wrong_calls if tool not in resolution_tools
    )
    result = calls.call(wrong_tool, arguments)
    return (
        result.status == "failed" and result.error_code == "submechanism_resolution_action_required"
    )


class _ReplayCalls:
    def __init__(self, runtime: FinanceCapabilitySubmechanismRuntime) -> None:
        self.runtime = runtime
        self.scenario = runtime.scenario
        self.index = 0
        self.operation_ref: str | None = None
        self.last_verification: AgentToolResult | None = None

    def call(self, tool: str, arguments: dict[str, Any]) -> AgentToolResult:
        self.index += 1
        return self.runtime.execute(
            AgentToolCall(call_index=self.index, tool_id=tool, arguments=arguments)
        )

    def query_role(self, index: int, *, add_filter: bool = False) -> AgentToolResult:
        role = self.scenario.evidence_roles[index]
        filters = {"source_id": self._item(role.evidence_id).source.source_id} if add_filter else {}
        return self.call(
            "query_structured_fact",
            {
                "subject_alias": role.subject_alias,
                "metric_alias": role.metric_alias,
                "period_label": role.period_label,
                "public_filters": filters,
            },
        )

    def select_all(self) -> None:
        selected = set(self.runtime.selected_evidence_ids)
        for index, role in enumerate(self.scenario.evidence_roles):
            if role.evidence_id not in selected:
                result = self.query_role(index, add_filter=True)
                if result.status != "succeeded":
                    raise ValueError("submechanism replay could not select required Evidence")
                selected.update(result.evidence_ids)

    def calculate(self, *, from_operation: bool = False, selector: bool = True) -> AgentToolResult:
        if from_operation:
            operand: dict[str, Any] = {"operation_ref": self.operation_ref}
            if selector:
                operand["selector"] = "payload.value"
        else:
            evidence_id = self.runtime.selected_evidence_ids[0]
            operand = {"evidence_id": evidence_id}
        result = self.call(
            "calculator",
            {"operator": "lookup", "operands": [operand], "parameters": {}},
        )
        if result.status == "succeeded":
            self.operation_ref = str(result.result["result"]["operation_ref"])
        return result

    def verify(self, candidate: dict[str, Any] | None = None) -> AgentToolResult:
        claim: dict[str, Any] = {"operation_ref": self.operation_ref or "operation:pending"}
        if candidate is not None:
            claim["candidate_payload"] = candidate
        result = self.call(
            "cross_check_evidence",
            {
                "evidence_ids": list(self.runtime.selected_evidence_ids),
                "claim_or_result": claim,
            },
        )
        self.last_verification = result
        return result

    def normalize(self) -> AgentToolResult:
        item = self._item(self.scenario.evidence_roles[0].evidence_id)
        return self.call(
            "normalize_metric_unit_period",
            {
                "evidence_ids": list(self.runtime.selected_evidence_ids),
                "target_definition": {
                    "definition_id": item.definition.definition_id,
                    "time_basis": item.temporal_context.basis,
                    "frequency": item.temporal_context.frequency,
                },
            },
        )

    def trigger_and_resolve_selector(self, kind: SubmechanismKind) -> None:
        if kind in {"tool_switch"}:
            first = self.call("search_archive", {"query": "financial fact", "limit": 6})
            if first.status != "failed":
                raise ValueError("tool-switch trigger did not fail")
            self.query_role(0, add_filter=True)
        elif kind in {"retrieval_failure", "empty_result_tool_fallback"}:
            first = self.query_role(0)
            if first.status != "failed":
                raise ValueError("retrieval trigger did not fail")
            self.call(
                "search_archive",
                {
                    "query": " ".join(
                        (
                            self.scenario.evidence_roles[0].subject_alias,
                            self.scenario.evidence_roles[0].metric_alias,
                        )
                    ),
                    "limit": 6,
                },
            )
        else:
            first = self.query_role(0)
            if first.status != "failed":
                raise ValueError("selector trigger did not fail")
            self.query_role(0, add_filter=True)
        self.select_all()
        self.calculate()

    def trigger_calculator_then_retrieve(self) -> None:
        first = self.call(
            "calculator",
            {
                "operator": "lookup",
                "operands": [{"value": "0"}],
                "parameters": {},
            },
        )
        if first.status != "failed":
            raise ValueError("missing-prerequisite trigger did not fail")
        self.query_role(0, add_filter=True)
        self.select_all()
        self.calculate()

    def trigger_and_repair_operation_reference(self) -> None:
        self.select_all()
        self.calculate()
        failed = self.verify()
        if failed.status != "failed":
            raise ValueError("operation-reference trigger did not fail")
        repaired = self.verify()
        if repaired.status != "succeeded":
            raise ValueError("operation-reference repair did not succeed")

    def verify_and_repair_candidate(self) -> None:
        self.select_all()
        self.calculate()
        first = self.verify(self.scenario.untrusted_candidate)
        if first.status != "succeeded":
            raise ValueError("candidate trigger did not produce a replayable observation")
        result = self.verify(self.scenario.canonical_candidate)
        if not bool(result.result.get("verified")):
            raise ValueError("candidate repair did not verify")

    def resolve_conflict(self) -> None:
        self.select_all()
        self.calculate()
        first = self.verify()
        if bool(first.result.get("verified")):
            raise ValueError("conflict trigger unexpectedly verified")
        self.normalize()
        result = self.verify()
        if not bool(result.result.get("verified")):
            raise ValueError("conflict resolution did not verify")

    def complete_missing_roles(self) -> None:
        self.query_role(0, add_filter=True)
        first = self.verify()
        if bool(first.result.get("verified")):
            raise ValueError("incomplete role trigger unexpectedly verified")
        self.select_all()
        self.calculate()
        self.verify()

    def complete_source_coverage(self) -> None:
        item = self._item(self.scenario.evidence_roles[0].evidence_id)
        search = self.call(
            "search_archive",
            {
                "query": " ".join(
                    (
                        item.subject.name,
                        item.predicate,
                        str(item.temporal_context.label),
                    )
                ),
                "subject_aliases": [item.subject.name],
                "period_labels": [str(item.temporal_context.label)],
                "source_filters": [item.source.source_id],
                "limit": 6,
            },
        )
        matches = search.result.get("matches") or []
        locator = next(
            (
                match["public_locator"]
                for match in matches
                if self.scenario.evidence_roles[0].evidence_id == match.get("evidence_id")
            ),
            matches[0]["public_locator"] if matches else None,
        )
        if locator is None:
            raise ValueError("source coverage replay could not discover a public locator")
        self.select_all()
        self.calculate()
        first = self.verify()
        if bool(first.result.get("verified")):
            raise ValueError("source coverage trigger unexpectedly verified")
        opened = self.call("open_document", {"public_locator": locator})
        if opened.status != "succeeded":
            raise ValueError("source coverage resolution did not open the public document")
        self.verify()

    def verify_complete(self) -> None:
        self.select_all()
        self.calculate()
        self.verify()

    def extra_action_rejected(self) -> bool:
        result = self.call("search_archive", {"query": "redundant", "limit": 1})
        return result.status == "failed" and bool(result.error_code)

    def ensure_final_verification(self) -> bool:
        if self.last_verification is None or not bool(
            self.last_verification.result.get("verified")
        ):
            if self.runtime.verification_complete:
                return True
            self.select_all()
            if self.operation_ref is None:
                self.calculate()
            self.verify(self.scenario.canonical_candidate)
        return bool(
            self.last_verification
            and self.last_verification.status == "succeeded"
            and self.last_verification.result.get("verified")
        )

    def _item(self, evidence_id: str) -> EvidenceItem:
        return self.runtime.evidence_item(evidence_id)


def _public_oracle_isolated(task: CapabilitySubmechanismTask) -> bool:
    public_payload = task.artifact.task.public.model_dump(mode="json")
    public_text = json.dumps(public_payload, ensure_ascii=False, sort_keys=True)
    public_keys = _collect_mapping_keys(public_payload)
    forbidden_keys = {
        "scenario_id",
        "evidence_roles",
        "canonical_candidate",
        "repair_target_field",
    }
    forbidden_values = {
        task.scenario.scenario_id,
        *(item.evidence_id for item in task.artifact.public_corpus.evidence),
        *(item.evidence_version_id for item in task.artifact.public_corpus.evidence),
    }
    return (
        FINANCE_SUBMECHANISM_ORACLE_KEY in task.artifact.task.oracle.selection_contract
        and FINANCE_SUBMECHANISM_ORACLE_KEY not in public_text
        and not (public_keys & forbidden_keys)
        and not any(value in public_text for value in forbidden_values)
    )


def _public_mechanism_nondisclosed(task: CapabilitySubmechanismTask) -> bool:
    public_payload = task.artifact.task.public.model_dump(mode="json")
    public_text = json.dumps(public_payload, ensure_ascii=False, sort_keys=True)
    public_keys = _collect_mapping_keys(public_payload)
    forbidden_keys = {
        "submechanism_id",
        "parent_mechanism_id",
        "intervention_kind",
        "trigger_tools",
        "resolution_tools",
        "public_resolution_hint",
    }
    forbidden_values = {
        task.submechanism_id,
        task.parent_mechanism_id,
        task.scenario.intervention_kind,
        task.scenario.public_resolution_hint,
    }
    return not (public_keys & forbidden_keys) and not any(
        value in public_text for value in forbidden_values
    )


def _collect_mapping_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return {
            *(str(key) for key in value),
            *(key for nested in value.values() for key in _collect_mapping_keys(nested)),
        }
    if isinstance(value, (list, tuple)):
        return {key for nested in value for key in _collect_mapping_keys(nested)}
    return set()


def make_submechanism_static_audit(
    tasks: tuple[CapabilitySubmechanismTask, ...],
    *,
    excluded_evidence_ids: set[str],
    excluded_evidence_version_ids: set[str],
) -> CapabilitySubmechanismStaticAudit:
    parents = Counter(item.parent_mechanism_id for item in tasks)
    evidence = [item for task in tasks for item in task.artifact.public_corpus.evidence]
    public_isolation = [_public_oracle_isolated(task) for task in tasks]
    public_mechanism_nondisclosure = [
        _public_mechanism_nondisclosed(task) for task in tasks
    ]
    checks = {
        "selected_task_count": len(tasks) == SELECTED_TASK_COUNT,
        "balanced_parent_coverage": bool(parents)
        and all(value == SELECTED_PER_PARENT for value in parents.values())
        and len(parents) == 4,
        "operation_replay": all(item.artifact.verification.passed for item in tasks),
        "runtime_scenario_coverage": all(
            item.scenario.submechanism_id == item.submechanism_id for item in tasks
        ),
        "host_replay": all(item.runtime_replay.passed for item in tasks),
        "wrong_branch_rejection": all(item.runtime_replay.wrong_branch_rejected for item in tasks),
        "public_oracle_isolation": all(public_isolation),
        "public_mechanism_non_disclosure": all(public_mechanism_nondisclosure),
        "answer_contract": all(_answer_contract_ready(item.artifact) for item in tasks),
        "within_population_evidence_disjoint": len(evidence)
        == len({item.evidence_id for item in evidence}),
        "prior_evidence_disjoint": not {item.evidence_id for item in evidence}
        & excluded_evidence_ids,
        "prior_evidence_version_disjoint": not {item.evidence_version_id for item in evidence}
        & excluded_evidence_version_ids,
        "distinct_runtime_policy": len({item.scenario.intervention_kind for item in tasks})
        == SELECTED_TASK_COUNT,
        "distinct_materializer": len({item.materializer_hash for item in tasks})
        == SELECTED_TASK_COUNT,
        "base_tier": all(
            item.base_tier == BOUNDARY_BASE_TIER and item.artifact.tier == BOUNDARY_BASE_TIER
            for item in tasks
        ),
    }
    rejections = tuple(sorted(key for key, passed in checks.items() if not passed))
    values = {
        "selected_task_count": len(tasks),
        "parent_task_counts": dict(sorted(parents.items())),
        "operation_replay_pass_rate": _rate(item.artifact.verification.passed for item in tasks),
        "runtime_scenario_coverage_rate": _rate(
            item.scenario.submechanism_id == item.submechanism_id for item in tasks
        ),
        "host_replay_pass_rate": _rate(item.runtime_replay.passed for item in tasks),
        "wrong_branch_rejection_rate": _rate(
            item.runtime_replay.wrong_branch_rejected for item in tasks
        ),
        "public_oracle_isolation_rate": _rate(public_isolation),
        "public_mechanism_non_disclosure_rate": _rate(public_mechanism_nondisclosure),
        "answer_contract_coverage_rate": _rate(
            _answer_contract_ready(item.artifact) for item in tasks
        ),
        "within_population_evidence_disjoint": checks["within_population_evidence_disjoint"],
        "prior_evidence_disjoint": checks["prior_evidence_disjoint"],
        "prior_evidence_version_disjoint": checks["prior_evidence_version_disjoint"],
        "distinct_runtime_policy_count": len({item.scenario.intervention_kind for item in tasks}),
        "distinct_materializer_count": len({item.materializer_hash for item in tasks}),
        "implementation_coverage_rate": len(tasks) / SELECTED_TASK_COUNT,
        "base_tier": BOUNDARY_BASE_TIER,
        "rejection_reasons": rejections,
        "ready": not rejections,
        "next_permitted_stage": (
            "flash_submechanism_development"
            if not rejections
            else "submechanism_runtime_implementation_only"
        ),
    }
    provisional = CapabilitySubmechanismStaticAudit.model_construct(audit_id="pending", **values)
    return CapabilitySubmechanismStaticAudit(
        audit_id=submechanism_static_audit_id(provisional), **values
    )


def _collect_excluded_identity(paths: tuple[Path, ...]) -> tuple[set[str], set[str]]:
    evidence_ids: set[str] = set()
    version_ids: set[str] = set()
    for path in paths:
        if not path.is_file():
            raise ValueError(f"submechanism exclusion path does not exist: {path}")
        _collect_identity(json.loads(path.read_text(encoding="utf-8")), evidence_ids, version_ids)
    return evidence_ids, version_ids


def _collect_identity(value: Any, evidence_ids: set[str], version_ids: set[str]) -> None:
    if isinstance(value, Mapping):
        if isinstance(value.get("evidence_id"), str):
            evidence_ids.add(str(value["evidence_id"]))
        if isinstance(value.get("evidence_version_id"), str):
            version_ids.add(str(value["evidence_version_id"]))
        for item in value.values():
            _collect_identity(item, evidence_ids, version_ids)
    elif isinstance(value, list):
        for item in value:
            _collect_identity(item, evidence_ids, version_ids)


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        Path(__file__).resolve(),
        root / "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        root / "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_boundary.py",
        root
        / "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_boundary_runner.py",
        root
        / "src/trusted_synthesis/experiments/vtdo_experiment"
        / "phase1_multitier_capability_population.py",
        root
        / "src/trusted_synthesis/experiments/vtdo_experiment"
        / "phase1_capability_submechanism_direction_design.py",
        root
        / "src/trusted_synthesis/experiments/vtdo_experiment"
        / "phase1_capability_submechanism_catalog.py",
    )
    return {str(path.relative_to(root)): _sha256(path) for path in sorted(paths)}


def _rate(values: Iterable[bool]) -> float:
    rows = tuple(values)
    return sum(rows) / len(rows) if rows else 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    if path.exists():
        raise ValueError(f"immutable output exists: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _render_report(population: CapabilitySubmechanismPopulation) -> str:
    audit = population.static_audit
    return "\n".join(
        (
            "# Finance Capability Submechanism Population",
            "",
            "## Decision",
            "",
            f"- Population ID: `{population.population_id}`",
            f"- Tasks: **{audit.selected_task_count}/{SELECTED_TASK_COUNT}**",
            f"- Frozen base tier: **{population.base_tier.value}**",
            f"- Static Runtime ready: **{audit.ready}**",
            f"- Next permitted stage: `{audit.next_permitted_stage}`",
            "- API calls: **0**",
            "- Pro / Beneficiary / Exact Target / GP-C: **blocked**",
            "",
            "## Hard Gates",
            "",
            f"- Operation replay: **{audit.operation_replay_pass_rate:.2%}**",
            f"- Scenario coverage: **{audit.runtime_scenario_coverage_rate:.2%}**",
            f"- Host trigger/resolution replay: **{audit.host_replay_pass_rate:.2%}**",
            f"- Wrong-branch rejection: **{audit.wrong_branch_rejection_rate:.2%}**",
            f"- Public/Oracle isolation: **{audit.public_oracle_isolation_rate:.2%}**",
            "- Public mechanism non-disclosure: "
            f"**{audit.public_mechanism_non_disclosure_rate:.2%}**",
            f"- Answer contract coverage: **{audit.answer_contract_coverage_rate:.2%}**",
            (
                "- Within-population Evidence disjoint: "
                f"**{audit.within_population_evidence_disjoint}**"
            ),
            f"- Prior Evidence disjoint: **{audit.prior_evidence_disjoint}**",
            f"- Prior Evidence Version disjoint: **{audit.prior_evidence_version_disjoint}**",
            f"- Distinct Runtime policies: **{audit.distinct_runtime_policy_count}**",
            f"- Distinct Materializers: **{audit.distinct_materializer_count}**",
            "",
            "This artifact validates the measurement instrument and fresh Finance support. "
            "It does not authorize API use; only a separately frozen Flash stable-support "
            "stage may consume it.",
            "",
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a fresh Finance capability-submechanism population"
    )
    parser.add_argument("--source-artifacts", type=Path, required=True)
    parser.add_argument("--direction-report", type=Path, required=True)
    parser.add_argument("--exclude", action="append", type=Path, default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sampling-salt", required=True)
    args = parser.parse_args(argv)
    population = build_submechanism_population(
        source_artifacts_path=args.source_artifacts,
        source_direction_report_path=args.direction_report,
        exclusion_paths=tuple(args.exclude),
        output_dir=args.output_dir,
        run_id=args.run_id,
        sampling_salt=args.sampling_salt,
    )
    print(
        json.dumps(
            {
                "population_id": population.population_id,
                "task_count": len(population.tasks),
                "ready": population.static_audit.ready,
                "next_permitted_stage": population.next_permitted_stage,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
