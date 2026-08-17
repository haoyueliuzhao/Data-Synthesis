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
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_capability_ladder import (
    core_task_semantic_signature,
)
from trusted_synthesis.hashing import canonical_hash

V26_FRESH_TASK_ROOT_VERSION = "finance_v26_fresh_task_root.v1"
V26_FRESH_TASK_POPULATION_VERSION = "finance_v26_fresh_task_population.v1"
V26_FRESH_TASK_SELECTION_POLICY_VERSION = "finance_v26_bridge_task_selection.v1"
V26_CROSS_POPULATION_FRESHNESS_AUDIT_VERSION = (
    "finance_v26_cross_population_freshness_audit.v1"
)

FreshnessChannel = Literal[
    "task_id",
    "source_task_id",
    "evidence_id",
    "evidence_version_id",
    "core_semantic_signature",
    "task_signature",
    "mechanism_instance_signature",
    "source_record_id",
]
FRESHNESS_CHANNELS: tuple[FreshnessChannel, ...] = (
    "task_id",
    "source_task_id",
    "evidence_id",
    "evidence_version_id",
    "core_semantic_signature",
    "task_signature",
    "mechanism_instance_signature",
    "source_record_id",
)

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


class V26FreshnessChannelAudit(FrozenModel):
    channel: FreshnessChannel
    development_values: tuple[str, ...] = Field(min_length=1)
    confirmation_values: tuple[str, ...] = Field(min_length=1)
    development_set_hash: str = Field(min_length=1)
    confirmation_set_hash: str = Field(min_length=1)
    overlap_values: tuple[str, ...] = ()
    overlap_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_channel(self) -> V26FreshnessChannelAudit:
        if self.development_values != tuple(sorted(set(self.development_values))):
            raise ValueError("v26 Development freshness identities are not canonical")
        if self.confirmation_values != tuple(sorted(set(self.confirmation_values))):
            raise ValueError("v26 Confirmation freshness identities are not canonical")
        expected_overlap = tuple(
            sorted(set(self.development_values) & set(self.confirmation_values))
        )
        if self.overlap_values != expected_overlap or self.overlap_count != len(expected_overlap):
            raise ValueError("v26 freshness overlap result is inconsistent")
        if self.development_set_hash != _freshness_set_hash(
            self.channel, self.development_values
        ):
            raise ValueError("v26 Development freshness set hash is invalid")
        if self.confirmation_set_hash != _freshness_set_hash(
            self.channel, self.confirmation_values
        ):
            raise ValueError("v26 Confirmation freshness set hash is invalid")
        return self


class V26CrossPopulationFreshnessAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    development_population_id: str = Field(min_length=1)
    confirmation_population_id: str = Field(min_length=1)
    development_population: V26FreshTaskPopulation
    confirmation_population: V26FreshTaskPopulation
    development_source_population_id: str = Field(min_length=1)
    confirmation_source_population_id: str = Field(min_length=1)
    development_source_population_content_hash: str = Field(min_length=1)
    confirmation_source_population_content_hash: str = Field(min_length=1)
    channels: tuple[V26FreshnessChannelAudit, ...] = Field(min_length=8, max_length=8)
    status: Literal["passed"] = "passed"
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_cross_population_freshness_audit.v1"] = (
        "finance_v26_cross_population_freshness_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> V26CrossPopulationFreshnessAudit:
        if tuple(item.channel for item in self.channels) != FRESHNESS_CHANNELS:
            raise ValueError("v26 freshness channels are incomplete or reordered")
        if any(item.overlap_count for item in self.channels):
            raise ValueError("v26 cross-population freshness is not disjoint")
        if (
            self.development_population.population_id != self.development_population_id
            or self.confirmation_population.population_id != self.confirmation_population_id
            or self.development_population.protocol_id != self.protocol_id
            or self.confirmation_population.protocol_id != self.protocol_id
        ):
            raise ValueError("v26 freshness audit embeds detached typed Populations")
        if self.development_population_id == self.confirmation_population_id:
            raise ValueError("v26 freshness audit reuses one typed Population")
        if self.development_source_population_id == self.confirmation_source_population_id:
            raise ValueError("v26 freshness audit reuses one source Population")
        if self.audit_id != v26_cross_population_freshness_audit_id(self):
            raise ValueError("v26 cross-population freshness audit identity is invalid")
        return self


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


def build_v26_cross_population_freshness_audit(
    development: V26FreshTaskPopulation,
    confirmation: V26FreshTaskPopulation,
) -> V26CrossPopulationFreshnessAudit:
    if (
        development.phase != "development"
        or confirmation.phase != "fresh_confirmation"
        or development.protocol_id != confirmation.protocol_id
    ):
        raise ValueError("v26 freshness audit crosses protocol or phase identities")
    development_tasks = load_v26_selected_source_tasks(development)
    confirmation_tasks = load_v26_selected_source_tasks(confirmation)
    development_values = v26_freshness_channel_values(development, development_tasks)
    confirmation_values = v26_freshness_channel_values(confirmation, confirmation_tasks)
    channels = tuple(
        _make_freshness_channel_audit(
            channel,
            development_values[channel],
            confirmation_values[channel],
        )
        for channel in FRESHNESS_CHANNELS
    )
    values = {
        "protocol_id": development.protocol_id,
        "development_population_id": development.population_id,
        "confirmation_population_id": confirmation.population_id,
        "development_population": development,
        "confirmation_population": confirmation,
        "development_source_population_id": development.source_population_id,
        "confirmation_source_population_id": confirmation.source_population_id,
        "development_source_population_content_hash": (
            development.source_population_content_hash
        ),
        "confirmation_source_population_content_hash": (
            confirmation.source_population_content_hash
        ),
        "channels": channels,
        "status": "passed",
        "model_api_calls": 0,
        "gpu_jobs": 0,
        "schema_version": V26_CROSS_POPULATION_FRESHNESS_AUDIT_VERSION,
    }
    provisional = V26CrossPopulationFreshnessAudit.model_construct(
        audit_id="pending", **values
    )
    return V26CrossPopulationFreshnessAudit(
        audit_id=v26_cross_population_freshness_audit_id(provisional),
        **values,
    )


def replay_v26_cross_population_freshness_audit(
    audit: V26CrossPopulationFreshnessAudit,
    development: V26FreshTaskPopulation,
    confirmation: V26FreshTaskPopulation,
) -> None:
    replay = build_v26_cross_population_freshness_audit(development, confirmation)
    if replay != audit:
        raise ValueError("v26 cross-population freshness audit replay failed")


def v26_cross_population_freshness_audit_id(
    value: V26CrossPopulationFreshnessAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_cross_population_freshness_audit:",
    )


def _make_freshness_channel_audit(
    channel: FreshnessChannel,
    development_values: set[str],
    confirmation_values: set[str],
) -> V26FreshnessChannelAudit:
    development = tuple(sorted(development_values))
    confirmation = tuple(sorted(confirmation_values))
    overlap = tuple(sorted(development_values & confirmation_values))
    if overlap:
        raise ValueError(f"v26 freshness channel {channel} is not disjoint")
    return V26FreshnessChannelAudit(
        channel=channel,
        development_values=development,
        confirmation_values=confirmation,
        development_set_hash=_freshness_set_hash(channel, development),
        confirmation_set_hash=_freshness_set_hash(channel, confirmation),
        overlap_values=overlap,
        overlap_count=0,
    )


def _freshness_set_hash(channel: FreshnessChannel, values: Sequence[str]) -> str:
    return canonical_hash(
        {"channel": channel, "values": tuple(values)},
        prefix="finance_v26_freshness_identity_set:",
    )


def load_v26_selected_source_tasks(
    population: V26FreshTaskPopulation,
) -> tuple[CapabilitySensitiveTaskArtifact, ...]:
    source_path = Path(population.source_population_path)
    if not source_path.is_file() or _sha256(source_path) != population.source_population_sha256:
        raise ValueError("v26 source Population byte replay failed")
    source_payload = json.loads(source_path.read_text(encoding="utf-8"))
    if canonical_hash(source_payload) != population.source_population_content_hash:
        raise ValueError("v26 source Population canonical replay failed")
    source = CapabilitySensitiveFrontierPopulation.model_validate(source_payload)
    if (
        source.population_id != population.source_population_id
        or source.run_id != population.source_population_run_id
        or source.schema_version != population.source_population_schema_version
    ):
        raise ValueError("v26 source Population identity replay failed")
    by_id = {item.artifact_id: item for item in source.tasks}
    selected = []
    for root in population.tasks:
        task = by_id.get(root.source_task_artifact_id)
        if (
            task is None
            or canonical_hash(task.model_dump(mode="json"))
            != root.source_task_content_hash
        ):
            raise ValueError("v26 source task content replay failed")
        if _root_from_source_task(task, mechanism_id=root.mechanism_id) != root:
            raise ValueError("v26 source task semantic-root replay failed")
        selected.append(task)
    return tuple(selected)


def v26_freshness_channel_values(
    population: V26FreshTaskPopulation,
    tasks: Sequence[CapabilitySensitiveTaskArtifact],
) -> dict[FreshnessChannel, set[str]]:
    mechanism_by_source = {
        item.source_task_artifact_id: item.mechanism_id for item in population.tasks
    }
    core_by_source = {item.artifact_id: core_task_semantic_signature(item) for item in tasks}
    return {
        "task_id": {item.task.task_id for item in tasks},
        "source_task_id": {item.artifact_id for item in tasks},
        "evidence_id": {
            evidence.evidence_id
            for item in tasks
            for evidence in item.public_corpus.evidence
        },
        "evidence_version_id": {
            evidence.evidence_version_id
            for item in tasks
            for evidence in item.public_corpus.evidence
        },
        "core_semantic_signature": set(core_by_source.values()),
        "task_signature": {item.task.task_hash for item in tasks},
        "mechanism_instance_signature": {
            canonical_hash(
                {
                    "mechanism_id": mechanism_by_source[item.artifact_id],
                    "task_family": item.family,
                    "difficulty_tier": item.tier.value,
                    "core_semantic_signature": core_by_source[item.artifact_id],
                    "structure": item.structure.model_dump(mode="json"),
                },
                prefix="finance_v26_mechanism_instance:",
            )
            for item in tasks
        },
        "source_record_id": {
            evidence.provenance.source_record_id
            for item in tasks
            for evidence in item.public_corpus.evidence
        },
    }


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
