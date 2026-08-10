from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.specification import (
    ReferenceExecutionIdentity,
    TrajectoryVerificationContext,
    make_omega_component_manifest,
    make_oracle_execution_specification,
    make_trajectory_verification_context,
)
from trusted_synthesis.domains.finance.agent_tools import (
    FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
    make_finance_archive_agent_tool_manifest,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION,
)
from trusted_synthesis.domains.finance.iterative_agent_verifier import (
    FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION,
    FinanceIterativeAgentVerifier,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import ITERATIVE_AGENT_SOLVER_VERSION
from trusted_synthesis.runtime.agent.schema import AgentModelConfig
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest

PRO_FLASH_PILOT_CONTRACT_VERSION = "finance_pro_flash_paired_pilot_contract.v1"
PRO_FLASH_ROLLOUT_RECORD_VERSION = "finance_pro_flash_rollout_record.v1"
PRO_FLASH_STAGE_REPORT_VERSION = "finance_pro_flash_stage_report.v1"
PRO_FLASH_RUNNER_VERSION = "finance_pro_flash_paired_runner.v1"
PRO_FLASH_REBOUND_CONTEXT_VERSION = "finance_agent_rebound_context.v1"

EXPECTED_FAMILIES = (
    "finance.comparison",
    "finance.derived_growth_comparison",
    "finance.registered_ratio",
    "finance.temporal_absolute_change",
    "finance.temporal_average",
    "finance.temporal_growth",
)
EXPECTED_MODELS = {
    "pro": "deepseek-v4-pro",
    "flash": "deepseek-v4-flash",
}
TOOL_CALL_BUDGET = 12
FAILED_TOOL_CALL_BUDGET = 3
OBSERVATION_BYTE_BUDGET = 1_000_000
MODEL_TOKEN_BUDGET = 90_000


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExplorerArm(str, Enum):
    PRO = "pro"
    FLASH = "flash"


class PilotStage(str, Enum):
    CALIBRATION = "calibration"
    DISCOVERY = "discovery"


class ExplorerModelContract(FrozenModel):
    arm: ExplorerArm
    requested_model: str = Field(min_length=1)
    config_sha256: str = Field(min_length=64, max_length=64)
    public_manifest_hash: str = Field(min_length=1)
    config: AgentModelConfig
    credential_value_recorded: Literal[False] = False

    @model_validator(mode="after")
    def validate_model(self) -> ExplorerModelContract:
        expected = EXPECTED_MODELS[self.arm.value]
        if self.requested_model != expected or self.config.model != expected:
            raise ValueError(f"{self.arm.value} arm must use {expected}")
        if self.config.fallback_models or not self.config.require_requested_model:
            raise ValueError("paired Pilot forbids model fallback")
        if self.config.interaction_protocol != "host_instrumented":
            raise ValueError("paired Pilot requires Host-instrumented interaction")
        if self.config.public_manifest_hash != self.public_manifest_hash:
            raise ValueError("paired Pilot model manifest hash is inconsistent")
        return self


class PairedTaskContract(FrozenModel):
    task_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    source_artifact_id: str = Field(min_length=1)
    source_omega_context_id: str = Field(min_length=1)
    paired_omega_context_id: str = Field(min_length=1)
    paired_omega_manifest_id: str = Field(min_length=1)
    public_corpus_id: str = Field(min_length=1)
    public_corpus_hash: str = Field(min_length=1)
    tool_environment_manifest_id: str = Field(min_length=1)
    gold_evidence_count: int = Field(ge=1)
    public_evidence_count: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_task(self) -> PairedTaskContract:
        if self.family not in EXPECTED_FAMILIES:
            raise ValueError("paired Pilot task has an unknown family")
        if self.public_evidence_count < self.gold_evidence_count:
            raise ValueError("paired Pilot public Corpus is smaller than Gold Evidence")
        return self


class ProFlashPilotThresholds(FrozenModel):
    minimum_flash_validity_rate: float = Field(default=0.70, ge=0, le=1)
    maximum_flash_validity_drop_vs_pro: float = Field(default=0.15, ge=0, le=1)
    minimum_flash_tool_call_success_rate: float = Field(default=0.90, ge=0, le=1)
    minimum_flash_provenance_completeness: float = Field(default=0.98, ge=0, le=1)
    minimum_flash_end_to_end_accuracy: float = Field(default=0.65, ge=0, le=1)
    minimum_paired_diversity_task_fraction: float = Field(default=0.50, ge=0, le=1)
    minimum_mean_state_entropy_gain: float = Field(default=0.05, ge=0)
    minimum_mean_accepted_state_gain: float = Field(default=0.20, ge=0)
    minimum_state_conditioned_on_target_rate: float = Field(default=0.60, ge=0, le=1)
    minimum_meaningful_coordinate_rate_gain: float = Field(default=0.05, ge=0, le=1)
    maximum_within_state_gradient_variance_ratio: float = Field(default=2.0, gt=0)


class FinanceProFlashPilotContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    run_role: Literal["development_explorer_comparison_only"] = (
        "development_explorer_comparison_only"
    )
    source_artifacts_path: str = Field(min_length=1)
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    excluded_artifact_sha256s: tuple[str, ...]
    excluded_task_id_count: int = Field(ge=0)
    excluded_task_id_set_hash: str = Field(min_length=1)
    excluded_evidence_version_count: int = Field(ge=0)
    excluded_evidence_version_set_hash: str = Field(min_length=1)
    calibration_tasks: tuple[PairedTaskContract, ...] = Field(min_length=6, max_length=6)
    discovery_tasks: tuple[PairedTaskContract, ...] = Field(min_length=30, max_length=30)
    exact_target_task_ids: tuple[str, ...] = Field(min_length=18, max_length=18)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(min_length=2, max_length=2)
    paired_sampling_contract_hash: str = Field(min_length=1)
    unconditional_runs_per_task_arm: int = Field(default=10, ge=10, le=10)
    calibration_runs_per_task_arm: int = Field(default=2, ge=1, le=2)
    state_conditioned_attempts_per_state: int = Field(default=5, ge=5, le=5)
    maximum_tool_calls: int = Field(default=TOOL_CALL_BUDGET, ge=1)
    maximum_failed_tool_calls: int = Field(default=FAILED_TOOL_CALL_BUDGET, ge=0)
    maximum_total_observation_bytes: int = Field(default=OBSERVATION_BYTE_BUDGET, ge=1)
    maximum_model_tokens_per_rollout: int = Field(default=MODEL_TOKEN_BUDGET, ge=1)
    random_seed: int
    task_sampling_salt: str = Field(min_length=1)
    exact_target_sampling_salt: str = Field(min_length=1)
    materialization_primary_contract: Literal["flash_discovery_pro_materialization"] = (
        "flash_discovery_pro_materialization"
    )
    materialization_supplement_contract: Literal["flash_discovery_flash_materialization"] = (
        "flash_discovery_flash_materialization"
    )
    toolset_version: str = FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION
    runtime_version: str = FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION
    solver_version: str = ITERATIVE_AGENT_SOLVER_VERSION
    verifier_version: str = FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION
    verifier_manifest_hash: str = Field(min_length=1)
    quotient_mapper_version: str = Field(min_length=1)
    thresholds: ProFlashPilotThresholds
    calibration_outcomes_may_change_thresholds: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    gp_c_evaluated: Literal[False] = False
    contribution_approximation_authorized: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = PRO_FLASH_PILOT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceProFlashPilotContract:
        arms = {item.arm for item in self.model_contracts}
        if arms != set(ExplorerArm) or len(arms) != len(self.model_contracts):
            raise ValueError("paired Pilot requires one Pro and one Flash model contract")
        _validate_family_balance(self.calibration_tasks, expected_per_family=1)
        _validate_family_balance(self.discovery_tasks, expected_per_family=5)
        calibration_ids = {item.task_id for item in self.calibration_tasks}
        discovery_ids = {item.task_id for item in self.discovery_tasks}
        if calibration_ids & discovery_ids:
            raise ValueError("calibration and discovery populations overlap")
        if len(self.exact_target_task_ids) != len(set(self.exact_target_task_ids)):
            raise ValueError("exact-target Pilot tasks are duplicated")
        if not set(self.exact_target_task_ids) <= discovery_ids:
            raise ValueError("exact-target tasks must belong to the discovery population")
        family_by_id = {item.task_id: item.family for item in self.discovery_tasks}
        if Counter(family_by_id[item] for item in self.exact_target_task_ids) != Counter(
            {family: 3 for family in EXPECTED_FAMILIES}
        ):
            raise ValueError("exact-target subset requires three tasks per family")
        if len(self.excluded_artifact_sha256s) != len(set(self.excluded_artifact_sha256s)):
            raise ValueError("paired Pilot exclusion artifacts are duplicated")
        if self.paired_sampling_contract_hash != _paired_sampling_contract_hash(
            self.model_contracts
        ):
            raise ValueError("Pro and Flash sampling/runtime contracts are not paired")
        if self.contract_id != finance_pro_flash_pilot_contract_id(self):
            raise ValueError("paired Pilot contract identity is invalid")
        return self


@dataclass(frozen=True)
class _ArtifactIndexRow:
    task_id: str
    family: str
    artifact_id: str
    source_context_id: str
    evidence_version_ids: frozenset[str]


def prepare_pro_flash_pilot_contract(
    *,
    source_artifacts_path: Path,
    pro_config_path: Path,
    flash_config_path: Path,
    excluded_artifact_paths: tuple[Path, ...],
    output_path: Path,
    run_id: str,
    random_seed: int,
    task_sampling_salt: str,
    exact_target_sampling_salt: str,
    thresholds: ProFlashPilotThresholds | None = None,
) -> FinanceProFlashPilotContract:
    if output_path.exists():
        raise ValueError("paired Pilot contract is immutable and already exists")
    source_artifacts_path = source_artifacts_path.resolve()
    excluded_paths = tuple(path.resolve() for path in excluded_artifact_paths)
    if len(excluded_paths) != len(set(excluded_paths)):
        raise ValueError("paired Pilot exclusion paths are duplicated")
    excluded_artifact_sha256s = tuple(sorted(_sha256(path) for path in excluded_paths))
    if len(excluded_artifact_sha256s) != len(set(excluded_artifact_sha256s)):
        raise ValueError("paired Pilot exclusion contents are duplicated")
    excluded_task_ids, excluded_evidence_versions = _read_exclusion_identities(excluded_paths)
    index = _scan_artifact_index(source_artifacts_path)
    selected_rows, calibration_rows = _select_populations(
        index,
        excluded_task_ids=excluded_task_ids,
        excluded_evidence_versions=excluded_evidence_versions,
        sampling_salt=task_sampling_salt,
    )
    selected_ids = {item.task_id for item in (*selected_rows, *calibration_rows)}
    artifacts = _load_artifacts(source_artifacts_path, selected_ids)
    paired_tasks = {
        task_id: _paired_task_contract(artifacts[task_id]) for task_id in sorted(selected_ids)
    }
    discovery_tasks = tuple(paired_tasks[item.task_id] for item in selected_rows)
    calibration_tasks = tuple(paired_tasks[item.task_id] for item in calibration_rows)
    exact_target_task_ids = tuple(
        row.task_id
        for family in EXPECTED_FAMILIES
        for row in sorted(
            (item for item in selected_rows if item.family == family),
            key=lambda item: _selection_key(
                exact_target_sampling_salt,
                item.task_id,
            ),
        )[:3]
    )
    model_contracts = (
        _load_model_contract(ExplorerArm.PRO, pro_config_path),
        _load_model_contract(ExplorerArm.FLASH, flash_config_path),
    )
    values = {
        "run_id": run_id,
        "run_role": "development_explorer_comparison_only",
        "source_artifacts_path": str(source_artifacts_path),
        "source_artifacts_sha256": _sha256(source_artifacts_path),
        "excluded_artifact_sha256s": excluded_artifact_sha256s,
        "excluded_task_id_count": len(excluded_task_ids),
        "excluded_task_id_set_hash": canonical_hash(
            tuple(sorted(excluded_task_ids)), prefix="pro_flash_excluded_tasks:"
        ),
        "excluded_evidence_version_count": len(excluded_evidence_versions),
        "excluded_evidence_version_set_hash": canonical_hash(
            tuple(sorted(excluded_evidence_versions)),
            prefix="pro_flash_excluded_evidence_versions:",
        ),
        "calibration_tasks": calibration_tasks,
        "discovery_tasks": discovery_tasks,
        "exact_target_task_ids": exact_target_task_ids,
        "model_contracts": model_contracts,
        "paired_sampling_contract_hash": _paired_sampling_contract_hash(model_contracts),
        "unconditional_runs_per_task_arm": 10,
        "calibration_runs_per_task_arm": 2,
        "state_conditioned_attempts_per_state": 5,
        "maximum_tool_calls": TOOL_CALL_BUDGET,
        "maximum_failed_tool_calls": FAILED_TOOL_CALL_BUDGET,
        "maximum_total_observation_bytes": OBSERVATION_BYTE_BUDGET,
        "maximum_model_tokens_per_rollout": MODEL_TOKEN_BUDGET,
        "random_seed": random_seed,
        "task_sampling_salt": task_sampling_salt,
        "exact_target_sampling_salt": exact_target_sampling_salt,
        "materialization_primary_contract": "flash_discovery_pro_materialization",
        "materialization_supplement_contract": "flash_discovery_flash_materialization",
        "toolset_version": FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
        "runtime_version": FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION,
        "solver_version": ITERATIVE_AGENT_SOLVER_VERSION,
        "verifier_version": FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION,
        "verifier_manifest_hash": FinanceIterativeAgentVerifier().manifest_hash,
        "quotient_mapper_version": _quotient_mapper_version(),
        "thresholds": thresholds or ProFlashPilotThresholds(),
        "calibration_outcomes_may_change_thresholds": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "production_contribution": 0.0,
        "schema_version": PRO_FLASH_PILOT_CONTRACT_VERSION,
    }
    provisional = FinanceProFlashPilotContract.model_construct(contract_id="pending", **values)
    contract = FinanceProFlashPilotContract(
        contract_id=finance_pro_flash_pilot_contract_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def finance_pro_flash_pilot_contract_id(value: FinanceProFlashPilotContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_pro_flash_paired_pilot_contract:",
    )


def _paired_task_contract(artifact: FinanceTaskStateArtifact) -> PairedTaskContract:
    context, manifest = _paired_runtime_context(artifact)
    source = artifact.omega
    return PairedTaskContract(
        task_id=context.task.task_id,
        family=artifact.pattern_id,
        source_artifact_id=artifact.artifact_id,
        source_omega_context_id=source.context_id,
        paired_omega_context_id=context.context_id,
        paired_omega_manifest_id=make_omega_component_manifest(context).manifest_id,
        public_corpus_id=context.public_corpus.corpus_id,
        public_corpus_hash=context.public_corpus.corpus_hash,
        tool_environment_manifest_id=manifest.manifest_id,
        gold_evidence_count=len(context.task.oracle.gold_evidence_ids),
        public_evidence_count=len(context.public_corpus.evidence),
    )


def _paired_runtime_context(
    artifact: FinanceTaskStateArtifact,
) -> tuple[TrajectoryVerificationContext, AgentToolEnvironmentManifest]:
    source = artifact.omega
    corpus = source.public_corpus
    snapshot_id = str(corpus.build_id or f"corpus:{corpus.corpus_id}")
    manifest = make_finance_archive_agent_tool_manifest(
        environment_id=f"finance_v23_paired:{source.task.task_id}",
        corpus_id=corpus.corpus_id,
        corpus_hash=corpus.corpus_hash,
        archive_snapshot_id=snapshot_id,
        archive_snapshot_hash=corpus.corpus_hash,
        maximum_tool_calls=TOOL_CALL_BUDGET,
        maximum_failed_tool_calls=FAILED_TOOL_CALL_BUDGET,
        maximum_total_observation_bytes=OBSERVATION_BYTE_BUDGET,
    )
    public = source.task.public.model_copy(
        update={
            "allowed_tools": tuple(item.tool_id for item in manifest.tools),
            "retrieval_scope": {
                **source.task.public.retrieval_scope,
                "corpus_boundary": {
                    "corpus_id": corpus.corpus_id,
                    "corpus_hash": corpus.corpus_hash,
                    "evidence_count": len(corpus.evidence),
                    "snapshot_id": snapshot_id,
                },
            },
            "metadata": {
                **source.task.public.metadata,
                "paired_agent_runtime": {
                    "version": PRO_FLASH_REBOUND_CONTEXT_VERSION,
                    "source_omega_context_id": source.context_id,
                    "tool_environment_manifest_id": manifest.manifest_id,
                    "models_hidden_from_task": True,
                },
            },
        }
    )
    task = source.task.model_copy(update={"public": public})
    references = tuple(
        ReferenceExecutionIdentity(item, digest)
        for item, digest in zip(
            source.oracle_specification.reference_example_ids,
            source.oracle_specification.reference_example_hashes,
            strict=True,
        )
    )
    oracle = make_oracle_execution_specification(
        task,
        source.evidence_bundle,
        corpus,
        source.proof_graph,
        source.quality_contract,
        reference_examples=references,
    )
    context = make_trajectory_verification_context(
        task,
        source.evidence_bundle,
        corpus,
        source.proof_graph,
        source.quality_contract,
        oracle,
    )
    return context, manifest


def _load_model_contract(arm: ExplorerArm, path: Path) -> ExplorerModelContract:
    raw = json.loads(path.read_text(encoding="utf-8"))
    config = AgentModelConfig.model_validate(raw.get("model", raw))
    return ExplorerModelContract(
        arm=arm,
        requested_model=config.model,
        config_sha256=_sha256(path),
        public_manifest_hash=config.public_manifest_hash,
        config=config,
        credential_value_recorded=False,
    )


def _paired_sampling_contract_hash(
    contracts: tuple[ExplorerModelContract, ...],
) -> str:
    payloads = []
    for item in contracts:
        payload = item.config.model_dump(
            mode="json",
            exclude={
                "model",
                "input_cost_per_million",
                "input_cache_hit_cost_per_million",
                "input_cache_miss_cost_per_million",
                "output_cost_per_million",
                "pricing_source_url",
                "pricing_checked_at",
            },
        )
        payloads.append(payload)
    if not payloads or any(item != payloads[0] for item in payloads[1:]):
        raise ValueError("Pro and Flash configs differ outside model identity and pricing")
    return canonical_hash(payloads[0], prefix="pro_flash_paired_sampling_contract:")


def _scan_artifact_index(path: Path) -> tuple[_ArtifactIndexRow, ...]:
    rows: list[_ArtifactIndexRow] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            omega = value["joint_compilation"]["omega"]
            rows.append(
                _ArtifactIndexRow(
                    task_id=str(omega["task"]["task_id"]),
                    family=str(value["pattern_id"]),
                    artifact_id=str(value["artifact_id"]),
                    source_context_id=str(omega["context_id"]),
                    evidence_version_ids=frozenset(
                        str(item["evidence_version_id"])
                        for item in omega["public_corpus"]["evidence"]
                    ),
                )
            )
    task_ids = [item.task_id for item in rows]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("source Agent population contains duplicate task IDs")
    return tuple(rows)


def _select_populations(
    rows: tuple[_ArtifactIndexRow, ...],
    *,
    excluded_task_ids: set[str],
    excluded_evidence_versions: set[str],
    sampling_salt: str,
) -> tuple[tuple[_ArtifactIndexRow, ...], tuple[_ArtifactIndexRow, ...]]:
    selected: list[_ArtifactIndexRow] = []
    calibration: list[_ArtifactIndexRow] = []
    for family in EXPECTED_FAMILIES:
        eligible = sorted(
            (
                item
                for item in rows
                if item.family == family
                and item.task_id not in excluded_task_ids
                and not (item.evidence_version_ids & excluded_evidence_versions)
            ),
            key=lambda item: _selection_key(sampling_salt, item.task_id),
        )
        if len(eligible) < 6:
            raise ValueError(
                f"paired Pilot family {family} has {len(eligible)} fresh tasks; six required"
            )
        calibration.append(eligible[0])
        selected.extend(eligible[1:6])
    return tuple(selected), tuple(calibration)


def _selection_key(salt: str, task_id: str) -> str:
    return canonical_hash(
        {"salt": salt, "task_id": task_id},
        prefix="pro_flash_task_selection:",
    )


def _validate_family_balance(
    tasks: tuple[PairedTaskContract, ...],
    *,
    expected_per_family: int,
) -> None:
    task_ids = [item.task_id for item in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("paired Pilot task population contains duplicate task IDs")
    if Counter(item.family for item in tasks) != Counter(
        {family: expected_per_family for family in EXPECTED_FAMILIES}
    ):
        raise ValueError("paired Pilot task population is not family-balanced")


def _load_artifacts(
    path: Path,
    selected_task_ids: set[str],
) -> dict[str, FinanceTaskStateArtifact]:
    output: dict[str, FinanceTaskStateArtifact] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            task_id = str(value["joint_compilation"]["omega"]["task"]["task_id"])
            if task_id in selected_task_ids:
                output[task_id] = FinanceTaskStateArtifact.model_validate(value)
    if set(output) != selected_task_ids:
        raise ValueError("paired Pilot source population lacks a frozen selected task")
    return output


def _read_exclusion_identities(paths: tuple[Path, ...]) -> tuple[set[str], set[str]]:
    task_ids: set[str] = set()
    evidence_versions: set[str] = set()
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                value = json.loads(line)
                _collect_exclusion_identities(value, task_ids, evidence_versions)
    return task_ids, evidence_versions


def _collect_exclusion_identities(
    value: Any,
    task_ids: set[str],
    evidence_versions: set[str],
) -> None:
    if isinstance(value, dict):
        task_id = value.get("task_id")
        evidence_version = value.get("evidence_version_id")
        if isinstance(task_id, str) and task_id:
            task_ids.add(task_id)
        if isinstance(evidence_version, str) and evidence_version:
            evidence_versions.add(evidence_version)
        for nested in value.values():
            _collect_exclusion_identities(nested, task_ids, evidence_versions)
    elif isinstance(value, list):
        for nested in value:
            _collect_exclusion_identities(nested, task_ids, evidence_versions)


def _quotient_mapper_version() -> str:
    from trusted_synthesis.core.trajectory.state import TRAJECTORY_CANONICALIZER_VERSION

    return TRAJECTORY_CANONICALIZER_VERSION


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
