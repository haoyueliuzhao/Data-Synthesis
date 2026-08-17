from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.synthesis.schema import CompiledProofCarryingArtifacts
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    BRIDGE_MECHANISMS,
    BridgeMechanism,
)
from trusted_synthesis.hashing import canonical_hash

V26_FRESH_TASK_ROOT_VERSION = "finance_v26_fresh_task_root.v1"
V26_FRESH_TASK_POPULATION_VERSION = "finance_v26_fresh_task_population.v1"
V26_FRESH_TASK_SELECTION_POLICY_VERSION = "finance_v26_bridge_task_selection.v1"

V26FreshPopulationPhase = Literal["development", "fresh_confirmation"]

# These quotas describe capability mechanisms, not broad topic labels. Development and
# confirmation use independently generated source populations and the router rejects task reuse.
MECHANISM_FAMILY_QUOTAS: dict[BridgeMechanism, dict[str, int]] = {
    "context_conditioned_action": {"finance.branching_operation_plan": 8},
    "semantic_reconciliation": {"finance.definition_reconciliation": 8},
    "recovery_and_stopping": {
        "finance.recovery_guided_search": 4,
        "finance.stopping_decision_control": 4,
    },
}
FAMILY_TARGET_CAPABILITY: dict[str, str] = {
    "finance.branching_operation_plan": "planning",
    "finance.definition_reconciliation": "reconciliation",
    "finance.recovery_guided_search": "recovery",
    "finance.stopping_decision_control": "stopping",
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class V26FreshTaskRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    mechanism_id: BridgeMechanism
    target_capability_id: str = Field(min_length=1)
    task_family: str = Field(min_length=1)
    difficulty_tier: DifficultyTier
    task_package_hash: str = Field(min_length=1)
    public_spec_hash: str = Field(min_length=1)
    oracle_contract_hash: str = Field(min_length=1)
    evidence_bundle_hash: str = Field(min_length=1)
    public_corpus_hash: str = Field(min_length=1)
    proof_graph_hash: str = Field(min_length=1)
    allowed_tools: tuple[str, ...] = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    source_task_schema_version: str = Field(min_length=1)
    source_task_content_hash: str = Field(min_length=64, max_length=64)
    schema_version: Literal["finance_v26_fresh_task_root.v1"] = (
        "finance_v26_fresh_task_root.v1"
    )

    @model_validator(mode="after")
    def validate_root(self) -> V26FreshTaskRoot:
        quotas = MECHANISM_FAMILY_QUOTAS[self.mechanism_id]
        if self.task_family not in quotas:
            raise ValueError("v26 task family belongs to another Bridge mechanism")
        if self.target_capability_id != FAMILY_TARGET_CAPABILITY[self.task_family]:
            raise ValueError("v26 task target capability differs from its registered family")
        if self.target_capability_id not in CAPABILITY_AXES:
            raise ValueError("v26 task target capability is not registered")
        if len(set(self.allowed_tools)) != len(self.allowed_tools):
            raise ValueError("v26 task root contains duplicate tool identities")
        if self.root_id != v26_fresh_task_root_id(self):
            raise ValueError("v26 fresh task root identity is invalid")
        return self


class V26FreshTaskPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    phase: V26FreshPopulationPhase
    source_population_id: str = Field(min_length=1)
    source_population_run_id: str = Field(min_length=1)
    source_population_schema_version: str = Field(min_length=1)
    source_population_path: str = Field(min_length=1)
    source_population_sha256: str = Field(min_length=64, max_length=64)
    source_population_content_hash: str = Field(min_length=64, max_length=64)
    selection_policy_version: Literal["finance_v26_bridge_task_selection.v1"] = (
        "finance_v26_bridge_task_selection.v1"
    )
    selection_salt: str = Field(min_length=1)
    tasks: tuple[V26FreshTaskRoot, ...] = Field(min_length=24, max_length=24)
    task_count: Literal[24] = 24
    task_recompilation_before_admission_required: Literal[True] = True
    historical_state_promotion_count: Literal[0] = 0
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_fresh_task_population.v1"] = (
        "finance_v26_fresh_task_population.v1"
    )

    @model_validator(mode="after")
    def validate_population(self) -> V26FreshTaskPopulation:
        if not self.source_population_run_id.startswith("finance_v26_"):
            raise ValueError("historical task populations cannot be promoted into v26")
        if len({item.task_id for item in self.tasks}) != self.task_count:
            raise ValueError("v26 fresh Population task identities are duplicated")
        if len({item.source_task_artifact_id for item in self.tasks}) != self.task_count:
            raise ValueError("v26 fresh Population reuses source task artifacts")
        expected_order = tuple(
            sorted(
                self.tasks,
                key=lambda item: (BRIDGE_MECHANISMS.index(item.mechanism_id), item.task_id),
            )
        )
        if self.tasks != expected_order:
            raise ValueError("v26 fresh Population tasks are not canonically ordered")
        mechanism_counts = Counter(item.mechanism_id for item in self.tasks)
        if mechanism_counts != Counter({mechanism: 8 for mechanism in BRIDGE_MECHANISMS}):
            raise ValueError("v26 fresh Population does not contain eight tasks per mechanism")
        observed_quotas = Counter((item.mechanism_id, item.task_family) for item in self.tasks)
        expected_quotas = Counter(
            {
                (mechanism, family): count
                for mechanism, families in MECHANISM_FAMILY_QUOTAS.items()
                for family, count in families.items()
            }
        )
        if observed_quotas != expected_quotas:
            raise ValueError("v26 fresh Population differs from the frozen family quotas")
        if self.population_id != v26_fresh_task_population_id(self):
            raise ValueError("v26 fresh task Population identity is invalid")
        return self

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(item.task_id for item in self.tasks)

    @property
    def tasks_by_mechanism(self) -> dict[BridgeMechanism, tuple[V26FreshTaskRoot, ...]]:
        return {
            mechanism: tuple(item for item in self.tasks if item.mechanism_id == mechanism)
            for mechanism in BRIDGE_MECHANISMS
        }


def make_v26_fresh_task_root(
    *,
    task_id: str,
    mechanism_id: BridgeMechanism,
    target_capability_id: str,
    task_family: str,
    difficulty_tier: DifficultyTier,
    task_package_hash: str,
    public_spec_hash: str,
    oracle_contract_hash: str,
    evidence_bundle_hash: str,
    public_corpus_hash: str,
    proof_graph_hash: str,
    allowed_tools: tuple[str, ...],
    source_task_artifact_id: str,
    source_task_schema_version: str,
    source_task_content_hash: str,
) -> V26FreshTaskRoot:
    values = {
        "task_id": task_id,
        "mechanism_id": mechanism_id,
        "target_capability_id": target_capability_id,
        "task_family": task_family,
        "difficulty_tier": difficulty_tier,
        "task_package_hash": task_package_hash,
        "public_spec_hash": public_spec_hash,
        "oracle_contract_hash": oracle_contract_hash,
        "evidence_bundle_hash": evidence_bundle_hash,
        "public_corpus_hash": public_corpus_hash,
        "proof_graph_hash": proof_graph_hash,
        "allowed_tools": allowed_tools,
        "source_task_artifact_id": source_task_artifact_id,
        "source_task_schema_version": source_task_schema_version,
        "source_task_content_hash": source_task_content_hash,
        "schema_version": V26_FRESH_TASK_ROOT_VERSION,
    }
    provisional = V26FreshTaskRoot.model_construct(root_id="pending", **values)
    return V26FreshTaskRoot(root_id=v26_fresh_task_root_id(provisional), **values)


def make_v26_fresh_task_population(
    *,
    protocol_id: str,
    phase: V26FreshPopulationPhase,
    source_population_id: str,
    source_population_run_id: str,
    source_population_schema_version: str,
    source_population_path: str,
    source_population_sha256: str,
    source_population_content_hash: str,
    selection_salt: str,
    tasks: Sequence[V26FreshTaskRoot],
) -> V26FreshTaskPopulation:
    ordered = tuple(
        sorted(tasks, key=lambda item: (BRIDGE_MECHANISMS.index(item.mechanism_id), item.task_id))
    )
    values = {
        "protocol_id": protocol_id,
        "phase": phase,
        "source_population_id": source_population_id,
        "source_population_run_id": source_population_run_id,
        "source_population_schema_version": source_population_schema_version,
        "source_population_path": source_population_path,
        "source_population_sha256": source_population_sha256,
        "source_population_content_hash": source_population_content_hash,
        "selection_policy_version": V26_FRESH_TASK_SELECTION_POLICY_VERSION,
        "selection_salt": selection_salt,
        "tasks": ordered,
        "task_count": 24,
        "task_recompilation_before_admission_required": True,
        "historical_state_promotion_count": 0,
        "model_api_calls": 0,
        "gpu_jobs": 0,
        "schema_version": V26_FRESH_TASK_POPULATION_VERSION,
    }
    provisional = V26FreshTaskPopulation.model_construct(population_id="pending", **values)
    return V26FreshTaskPopulation(
        population_id=v26_fresh_task_population_id(provisional),
        **values,
    )


def build_v26_fresh_task_population(
    *,
    protocol_id: str,
    phase: V26FreshPopulationPhase,
    source_population_path: Path,
    selection_salt: str,
    output_path: Path,
) -> V26FreshTaskPopulation:
    if output_path.exists():
        raise ValueError("v26 fresh task Population is immutable")
    source_path = source_population_path.resolve()
    source_payload = json.loads(source_path.read_text(encoding="utf-8"))
    source = CapabilitySensitiveFrontierPopulation.model_validate(source_payload)
    selected = _select_source_tasks(
        source.tasks,
        source_population_id=source.population_id,
        phase=phase,
        selection_salt=selection_salt,
    )
    population = make_v26_fresh_task_population(
        protocol_id=protocol_id,
        phase=phase,
        source_population_id=source.population_id,
        source_population_run_id=source.run_id,
        source_population_schema_version=source.schema_version,
        source_population_path=str(source_path),
        source_population_sha256=_sha256(source_path),
        source_population_content_hash=canonical_hash(source_payload),
        selection_salt=selection_salt,
        tasks=tuple(
            _root_from_source_task(task, mechanism_id=mechanism_id)
            for mechanism_id, task in selected
        ),
    )
    _write_json_atomic(output_path, population.model_dump(mode="json"))
    return population


def validate_population_compilation(
    population: V26FreshTaskPopulation,
    compiled: Sequence[CompiledProofCarryingArtifacts],
) -> None:
    compiled_by_task = {item.task.task_id: item for item in compiled}
    if len(compiled_by_task) != len(compiled) or set(compiled_by_task) != set(population.task_ids):
        raise ValueError("Joint Compilation task identities differ from the fresh Population")
    for root in population.tasks:
        item = compiled_by_task[root.task_id]
        observed_family = item.task.public.task_type
        if not observed_family.startswith("finance."):
            observed_family = f"finance.{observed_family}"
        checks = (
            root.task_package_hash == item.task.task_hash,
            root.public_spec_hash == canonical_hash(item.task.public, prefix="task_public:"),
            root.oracle_contract_hash
            == canonical_hash(item.task.oracle, prefix="task_oracle:"),
            root.evidence_bundle_hash == item.evidence_bundle.bundle_hash,
            root.public_corpus_hash == item.public_corpus.corpus_hash,
            root.proof_graph_hash == item.proof_graph.graph_hash,
            root.allowed_tools == item.task.public.allowed_tools,
            root.task_family == observed_family,
        )
        if not all(checks):
            raise ValueError("Joint Compilation semantic roots differ from the fresh Population")


def v26_fresh_task_root_id(value: V26FreshTaskRoot) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"root_id"}),
        prefix="finance_v26_fresh_task_root:",
    )


def v26_fresh_task_population_id(value: V26FreshTaskPopulation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"population_id"}),
        prefix="finance_v26_fresh_task_population:",
    )


def _select_source_tasks(
    tasks: Sequence[CapabilitySensitiveTaskArtifact],
    *,
    source_population_id: str,
    phase: V26FreshPopulationPhase,
    selection_salt: str,
) -> tuple[tuple[BridgeMechanism, CapabilitySensitiveTaskArtifact], ...]:
    selected: list[tuple[BridgeMechanism, CapabilitySensitiveTaskArtifact]] = []
    for mechanism_id in BRIDGE_MECHANISMS:
        for family, quota in MECHANISM_FAMILY_QUOTAS[mechanism_id].items():
            candidates = [item for item in tasks if item.family == family]
            candidates.sort(
                key=lambda item: canonical_hash(
                    {
                        "source_population_id": source_population_id,
                        "phase": phase,
                        "selection_salt": selection_salt,
                        "task_artifact_id": item.artifact_id,
                    },
                    prefix="finance_v26_bridge_task_rank:",
                )
            )
            if len(candidates) < quota:
                raise ValueError(f"source Population lacks v26 Bridge capacity for {family}")
            selected.extend((mechanism_id, item) for item in candidates[:quota])
    return tuple(selected)


def _root_from_source_task(
    task: CapabilitySensitiveTaskArtifact,
    *,
    mechanism_id: BridgeMechanism,
) -> V26FreshTaskRoot:
    return make_v26_fresh_task_root(
        task_id=task.task.task_id,
        mechanism_id=mechanism_id,
        target_capability_id=FAMILY_TARGET_CAPABILITY[task.family],
        task_family=task.family,
        difficulty_tier=task.tier,
        task_package_hash=task.task.task_hash,
        public_spec_hash=canonical_hash(task.task.public, prefix="task_public:"),
        oracle_contract_hash=canonical_hash(task.task.oracle, prefix="task_oracle:"),
        evidence_bundle_hash=task.evidence_bundle.bundle_hash,
        public_corpus_hash=task.public_corpus.corpus_hash,
        proof_graph_hash=task.proof_graph.graph_hash,
        allowed_tools=task.task.public.allowed_tools,
        source_task_artifact_id=task.artifact_id,
        source_task_schema_version=task.schema_version,
        source_task_content_hash=canonical_hash(task.model_dump(mode="json")),
    )


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
