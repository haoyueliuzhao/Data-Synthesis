from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Final, Literal, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    BoundaryStage,
    CapabilityRolloutOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_runner import (
    CapabilityBoundaryRolloutRecord,
    _run_one,
    _to_outcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    SubmechanismBehaviorObservation,
    _make_terminals,
    make_submechanism_behavior_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    RuntimeTerminalOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_runtime_repair import (  # noqa: E501
    SELECTION_POLICY,
    FinanceStableRuntimeRepairContract,
    FinanceStableRuntimeRepairManifest,
    FrozenArtifactReference,
    RepairReplacement,
    StableRuntimeRepairJob,
    _append_jsonl,
    _job_key,
    _make_partial_terminals,
    _merge_selected_records,
    _outcome_key,
    _record_key,
    _resolve_model_discovery,
    _selected_transport_failures,
    _sha256,
    _terminal_key,
    _write_json_atomic,
    _write_jsonl_atomic,
    _write_text_atomic,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_support import (  # noqa: E501
    EXPECTED_ROLLOUT_COUNT,
    FinanceStableSupportContract,
    FinanceStableSupportReport,
    _render_report,
    _runtime_resolution_stage,
    make_stable_support_report,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import OpenAICompatibleJsonClient

STABLE_RUNTIME_REPAIR_WAVE_CONTRACT_VERSION = (
    "finance_stable_runtime_repair_wave_contract.v2"
)
STABLE_RUNTIME_REPAIR_WAVE_MANIFEST_VERSION = (
    "finance_stable_runtime_repair_manifest.v2"
)
STABLE_RUNTIME_REPAIR_WAVE_RUNNER_VERSION = (
    "finance_stable_runtime_repair_wave_runner.v2"
)
WAVE_REPLACEMENT_POLICY: Final[
    Literal["replace_every_current_wave_job_without_semantic_selection.v2"]
] = "replace_every_current_wave_job_without_semantic_selection.v2"
MAXIMUM_REPAIR_WAVES = 3
SOURCE_ARTIFACT_NAMES = (
    "records",
    "outcomes",
    "terminal_outcomes",
    "behavior_observations",
    "report",
)
OUTPUT_ARTIFACT_NAMES = (
    "repair_records",
    "repair_outcomes",
    "repair_terminal_outcomes",
    "merged_records",
    "merged_outcomes",
    "merged_terminal_outcomes",
    "merged_behavior_observations",
    "repaired_report",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceStableRuntimeRepairWaveContract(FrozenModel):
    wave_contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    wave_index: int = Field(ge=2, le=MAXIMUM_REPAIR_WAVES)
    stable_contract: FrozenArtifactReference
    stable_contract_id: str = Field(min_length=1)
    parent_contract: FrozenArtifactReference
    parent_contract_id: str = Field(min_length=1)
    parent_manifest: FrozenArtifactReference
    parent_manifest_id: str = Field(min_length=1)
    source_report_id: str = Field(min_length=1)
    source_stage: Literal["development", "confirmation"]
    source_artifacts: dict[str, FrozenArtifactReference]
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    selection_policy: Literal[
        "all_frozen_l0_external_transport_failures.v1"
    ] = SELECTION_POLICY
    replacement_policy: Literal[
        "replace_every_current_wave_job_without_semantic_selection.v2"
    ] = WAVE_REPLACEMENT_POLICY
    selected_jobs: tuple[StableRuntimeRepairJob, ...] = Field(min_length=1)
    selected_job_set_hash: str = Field(min_length=1)
    requested_model: str = Field(min_length=1)
    model_arm: Literal["flash"] = "flash"
    source_requested_rollout_count: Literal[480] = 480
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["selective_runtime_repair_wave"] = (
        "selective_runtime_repair_wave"
    )
    schema_version: str = STABLE_RUNTIME_REPAIR_WAVE_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceStableRuntimeRepairWaveContract:
        if set(self.source_artifacts) != set(SOURCE_ARTIFACT_NAMES):
            raise ValueError("Runtime repair wave source artifact set is incomplete")
        keys = [item.key for item in self.selected_jobs]
        if len(set(keys)) != len(keys) or tuple(keys) != tuple(sorted(keys)):
            raise ValueError("Runtime repair wave jobs are duplicated or unordered")
        if self.selected_job_set_hash != canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.selected_jobs),
            prefix="finance_stable_runtime_repair_wave_job_set:",
        ):
            raise ValueError("Runtime repair wave job-set identity is invalid")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stable_runtime_repair_wave_implementation:",
        ):
            raise ValueError("Runtime repair wave implementation identity is invalid")
        if self.wave_contract_id != stable_runtime_repair_wave_contract_id(self):
            raise ValueError("Runtime repair wave contract identity is invalid")
        return self


class FinanceStableRuntimeRepairWaveManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    wave_contract_id: str = Field(min_length=1)
    wave_index: int = Field(ge=2, le=MAXIMUM_REPAIR_WAVES)
    parent_contract_id: str = Field(min_length=1)
    parent_manifest_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    source_report_id: str = Field(min_length=1)
    repaired_report_id: str = Field(min_length=1)
    source_stage: Literal["development", "confirmation"]
    selection_policy: Literal[
        "all_frozen_l0_external_transport_failures.v1"
    ] = SELECTION_POLICY
    replacement_policy: Literal[
        "replace_every_current_wave_job_without_semantic_selection.v2"
    ] = WAVE_REPLACEMENT_POLICY
    selected_job_count: int = Field(ge=1)
    replacement_count: int = Field(ge=1)
    repaired_transport_resolved_count: int = Field(ge=0)
    remaining_transport_unresolved_count: int = Field(ge=0)
    replacements: tuple[RepairReplacement, ...] = Field(min_length=1)
    replacement_set_hash: str = Field(min_length=1)
    artifacts: dict[str, FrozenArtifactReference]
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    discovered_models: tuple[str, ...]
    requested_model: str = Field(min_length=1)
    prior_cumulative_api_call_count: int = Field(ge=0)
    repair_api_call_count: int = Field(ge=0)
    cumulative_api_call_count: int = Field(ge=0)
    prior_cumulative_total_model_tokens: int = Field(ge=0)
    repair_total_model_tokens: int = Field(ge=0)
    cumulative_total_model_tokens: int = Field(ge=0)
    prior_cumulative_estimated_cost_usd: float = Field(ge=0)
    repair_estimated_cost_usd: float = Field(ge=0)
    cumulative_estimated_cost_usd: float = Field(ge=0)
    runtime_measurement_ready: bool
    capability_support_admitted: bool
    fresh_confirmation_authorized: bool
    pro_sparse_anchor_authorized: bool
    next_permitted_stage: str = Field(min_length=1)
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = STABLE_RUNTIME_REPAIR_WAVE_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> FinanceStableRuntimeRepairWaveManifest:
        if set(self.artifacts) != set(OUTPUT_ARTIFACT_NAMES):
            raise ValueError("Runtime repair wave output artifact set is incomplete")
        if not (
            self.selected_job_count
            == self.replacement_count
            == len(self.replacements)
        ):
            raise ValueError("Runtime repair wave did not replace every selected job")
        if (
            self.repaired_transport_resolved_count
            + self.remaining_transport_unresolved_count
            != self.selected_job_count
        ):
            raise ValueError("Runtime repair wave transport denominator is incomplete")
        if self.replacement_set_hash != canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.replacements),
            prefix="finance_stable_runtime_repair_wave_replacement_set:",
        ):
            raise ValueError("Runtime repair wave replacement identity is invalid")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stable_runtime_repair_wave_implementation:",
        ):
            raise ValueError("Runtime repair wave manifest implementation is invalid")
        if self.cumulative_api_call_count != (
            self.prior_cumulative_api_call_count + self.repair_api_call_count
        ):
            raise ValueError("Runtime repair wave API accounting is incomplete")
        if self.cumulative_total_model_tokens != (
            self.prior_cumulative_total_model_tokens + self.repair_total_model_tokens
        ):
            raise ValueError("Runtime repair wave token accounting is incomplete")
        if abs(
            self.cumulative_estimated_cost_usd
            - (
                self.prior_cumulative_estimated_cost_usd
                + self.repair_estimated_cost_usd
            )
        ) > 1e-9:
            raise ValueError("Runtime repair wave cost accounting is incomplete")
        if self.manifest_id != stable_runtime_repair_wave_manifest_id(self):
            raise ValueError("Runtime repair wave manifest identity is invalid")
        return self


def stable_runtime_repair_wave_contract_id(
    value: FinanceStableRuntimeRepairWaveContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"wave_contract_id"}),
        prefix="finance_stable_runtime_repair_wave_contract:",
    )


def stable_runtime_repair_wave_manifest_id(
    value: FinanceStableRuntimeRepairWaveManifest,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_stable_runtime_repair_wave_manifest:",
    )


def prepare_stable_runtime_repair_wave(
    *,
    parent_contract_path: Path,
    parent_manifest_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceStableRuntimeRepairWaveContract:
    if output_path.exists():
        raise ValueError("Runtime repair wave contract is immutable")
    parent_contract_path = parent_contract_path.resolve()
    parent_manifest_path = parent_manifest_path.resolve()
    _, parent_contract_id, stable_contract_path = _load_parent_contract(
        parent_contract_path
    )
    parent_manifest = _load_parent_manifest(parent_manifest_path)
    if _parent_contract_id(parent_manifest) != parent_contract_id:
        raise ValueError("Runtime repair wave parent contract and manifest disagree")
    if parent_manifest.next_permitted_stage != "runtime_measurement_repair_only":
        raise ValueError("Runtime repair wave lacks a frozen Runtime-only parent")
    wave_index = int(getattr(parent_manifest, "wave_index", 1)) + 1
    if wave_index > MAXIMUM_REPAIR_WAVES:
        raise ValueError("Runtime repair wave exceeds the preregistered maximum")
    stable_contract = FinanceStableSupportContract.model_validate_json(
        stable_contract_path.read_text(encoding="utf-8")
    )
    source_paths = _source_paths_from_manifest(parent_manifest)
    source_report = FinanceStableSupportReport.model_validate_json(
        source_paths["report"].read_text(encoding="utf-8")
    )
    source_records = _load_jsonl(
        source_paths["records"],
        CapabilityBoundaryRolloutRecord,
    )
    source_outcomes = _load_jsonl(
        source_paths["outcomes"],
        CapabilityRolloutOutcome,
    )
    source_terminals = _load_jsonl(
        source_paths["terminal_outcomes"],
        RuntimeTerminalOutcome,
    )
    _validate_source(
        stable_contract,
        source_report,
        source_records,
        source_outcomes,
        source_terminals,
    )
    selected_terminals = _selected_transport_failures(source_terminals)
    if not selected_terminals:
        raise ValueError("Runtime repair wave selected no unresolved L0 job")
    records_by_key = {_record_key(item): item for item in source_records}
    outcomes_by_key = {_outcome_key(item): item for item in source_outcomes}
    selected_jobs = tuple(
        StableRuntimeRepairJob(
            binding_id=item.binding_id,
            task_artifact_id=item.task_artifact_id,
            replicate=item.replicate,
            source_record_id=records_by_key[_terminal_key(item)].record_id,
            source_outcome_id=outcomes_by_key[_terminal_key(item)].outcome_id,
            source_terminal_outcome_id=item.terminal_outcome_id,
            rollout_identity_token=stable_contract.rollout_identity_tokens[
                f"{item.binding_id}|{item.replicate}"
            ],
        )
        for item in selected_terminals
    )
    implementation = _implementation_manifest()
    values = {
        "run_id": run_id,
        "wave_index": wave_index,
        "stable_contract": FrozenArtifactReference(
            path=str(stable_contract_path),
            sha256=_sha256(stable_contract_path),
        ),
        "stable_contract_id": stable_contract.contract_id,
        "parent_contract": FrozenArtifactReference(
            path=str(parent_contract_path),
            sha256=_sha256(parent_contract_path),
        ),
        "parent_contract_id": parent_contract_id,
        "parent_manifest": FrozenArtifactReference(
            path=str(parent_manifest_path),
            sha256=_sha256(parent_manifest_path),
        ),
        "parent_manifest_id": parent_manifest.manifest_id,
        "source_report_id": source_report.report_id,
        "source_stage": stable_contract.stage,
        "source_artifacts": {
            name: FrozenArtifactReference(path=str(path), sha256=_sha256(path))
            for name, path in source_paths.items()
        },
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_stable_runtime_repair_wave_implementation:",
        ),
        "selected_jobs": selected_jobs,
        "selected_job_set_hash": canonical_hash(
            tuple(item.model_dump(mode="json") for item in selected_jobs),
            prefix="finance_stable_runtime_repair_wave_job_set:",
        ),
        "requested_model": stable_contract.model_contracts[0].requested_model,
    }
    provisional = FinanceStableRuntimeRepairWaveContract.model_construct(
        wave_contract_id="pending",
        **values,
    )
    contract = FinanceStableRuntimeRepairWaveContract(
        wave_contract_id=stable_runtime_repair_wave_contract_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_stable_runtime_repair_wave(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceStableRuntimeRepairWaveManifest:
    if workers < 1:
        raise ValueError("Runtime repair wave workers must be positive")
    contract = FinanceStableRuntimeRepairWaveContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    stable_contract, parent_manifest, source = _verify_inputs(contract)
    source_records = source["records"]
    tasks = {item.artifact_id: item for item in stable_contract.tasks}
    bindings = {item.binding_id: item for item in stable_contract.bindings}
    selected_keys = {item.key for item in contract.selected_jobs}
    output_dir.mkdir(parents=True, exist_ok=True)
    run_identity = canonical_hash(
        {
            "wave_contract_id": contract.wave_contract_id,
            "runner_version": STABLE_RUNTIME_REPAIR_WAVE_RUNNER_VERSION,
            "selected_job_set_hash": contract.selected_job_set_hash,
            "wave_index": contract.wave_index,
        },
        prefix="finance_stable_runtime_repair_wave_run:",
    )
    checkpoint_path = output_dir / "stable_runtime_repair_wave.checkpoint.jsonl"
    discovery_path = output_dir / "stable_runtime_repair_wave_model_discovery.json"
    repair_records = {
        _record_key(item): item
        for item in _load_checkpoint(
            checkpoint_path,
            contract=contract,
            stable_contract=stable_contract,
            run_identity=run_identity,
        )
    }
    jobs = tuple(
        (bindings[item.binding_id], item.replicate)
        for item in contract.selected_jobs
    )
    pending = tuple(job for job in jobs if _job_key(*job) not in repair_records)
    print(
        f"[stable-runtime-repair-wave-{contract.wave_index}] "
        f"resuming {len(repair_records)}/{len(jobs)}; executing {len(pending)} "
        f"with {min(workers, max(1, len(pending)))} workers",
        flush=True,
    )
    model_contract = stable_contract.model_contracts[0]
    if model_contract.arm != ExplorerArm.FLASH:
        raise ValueError("Runtime repair wave source is not Flash-only")
    if pending:
        client = OpenAICompatibleJsonClient(
            model_contract.config.model_copy(
                update={
                    "contract_repair_attempts": (
                        stable_contract.model_contract_repair_attempts
                    )
                }
            )
        )
        discovered = _resolve_model_discovery(
            client,
            discovery_path,
            run_identity=run_identity,
            requested_model=contract.requested_model,
        )
        with ThreadPoolExecutor(max_workers=min(workers, len(pending))) as executor:
            futures = {
                executor.submit(
                    _run_one,
                    cast(Any, stable_contract),
                    BoundaryStage.TIER_LOCALIZATION,
                    ExplorerArm.FLASH,
                    binding,
                    tasks[binding.task_artifact_id],
                    replicate,
                    run_identity,
                    client,
                ): _job_key(binding, replicate)
                for binding, replicate in pending
            }
            for future in as_completed(futures):
                key = futures[future]
                record = future.result()
                if _record_key(record) != key:
                    raise ValueError("Runtime repair wave worker crossed a frozen job")
                _append_jsonl(checkpoint_path, record.model_dump(mode="json"))
                repair_records[key] = record
                print(
                    f"[stable-runtime-repair-wave-{contract.wave_index}] "
                    f"completed {len(repair_records)}/{len(jobs)}",
                    flush=True,
                )
    else:
        raw = json.loads(discovery_path.read_text(encoding="utf-8"))
        if raw.get("run_identity") != run_identity:
            raise ValueError("Runtime repair wave model discovery changed identity")
        discovered = tuple(str(item) for item in raw.get("discovered_models", ()))
    if set(repair_records) != selected_keys:
        raise ValueError("Runtime repair wave executed outside its frozen set")
    ordered_repair_records = tuple(
        repair_records[_job_key(binding, replicate)]
        for binding, replicate in jobs
    )
    repair_records_path = output_dir / "stable_runtime_repair_wave_records.jsonl"
    repair_outcomes_path = output_dir / "stable_runtime_repair_wave_outcomes.jsonl"
    repair_terminals_path = output_dir / "stable_runtime_repair_wave_terminal_outcomes.jsonl"
    _write_jsonl_atomic(
        repair_records_path,
        (item.model_dump(mode="json") for item in ordered_repair_records),
    )
    repair_outcomes = tuple(
        _to_outcome(item, stable_contract.bindings) for item in ordered_repair_records
    )
    _write_jsonl_atomic(
        repair_outcomes_path,
        (item.model_dump(mode="json") for item in repair_outcomes),
    )
    terminal_contract = stable_contract.model_copy(
        update={"stage": _runtime_resolution_stage(stable_contract.stage)}
    )
    repair_terminals = _make_partial_terminals(
        cast(Any, terminal_contract),
        ordered_repair_records,
        repair_outcomes,
        bindings=stable_contract.bindings,
    )
    _write_jsonl_atomic(
        repair_terminals_path,
        (item.model_dump(mode="json") for item in repair_terminals),
    )
    merged_records = _merge_selected_records(
        source_records,
        ordered_repair_records,
        selected_keys=selected_keys,
    )
    merged_outcomes = tuple(
        _to_outcome(item, stable_contract.bindings) for item in merged_records
    )
    merged_terminals = _make_terminals(
        cast(Any, terminal_contract),
        merged_records,
        merged_outcomes,
    )
    merged_behaviors = make_submechanism_behavior_observations(
        cast(Any, stable_contract),
        merged_records,
        merged_outcomes,
        merged_terminals,
    )
    _validate_merged_denominator(
        stable_contract,
        merged_records,
        merged_outcomes,
        merged_terminals,
        merged_behaviors,
    )
    merged_records_path = output_dir / "stable_support_repaired_records.jsonl"
    merged_outcomes_path = output_dir / "stable_support_repaired_outcomes.jsonl"
    merged_terminals_path = output_dir / "stable_support_repaired_terminal_outcomes.jsonl"
    merged_behaviors_path = output_dir / "stable_support_repaired_behavior_observations.jsonl"
    _write_jsonl_atomic(
        merged_records_path,
        (item.model_dump(mode="json") for item in merged_records),
    )
    _write_jsonl_atomic(
        merged_outcomes_path,
        (item.model_dump(mode="json") for item in merged_outcomes),
    )
    _write_jsonl_atomic(
        merged_terminals_path,
        (item.model_dump(mode="json") for item in merged_terminals),
    )
    _write_jsonl_atomic(
        merged_behaviors_path,
        (item.model_dump(mode="json") for item in merged_behaviors),
    )
    repaired_report = make_stable_support_report(
        stable_contract,
        merged_outcomes,
        merged_terminals,
        merged_behaviors,
    )
    repaired_report_path = output_dir / "finance_stable_support_repaired_report.json"
    _write_json_atomic(repaired_report_path, repaired_report.model_dump(mode="json"))
    replacements = _replacements(
        contract,
        source_records=source_records,
        repair_records=ordered_repair_records,
        repair_terminals=repair_terminals,
    )
    artifact_paths = {
        "repair_records": repair_records_path,
        "repair_outcomes": repair_outcomes_path,
        "repair_terminal_outcomes": repair_terminals_path,
        "merged_records": merged_records_path,
        "merged_outcomes": merged_outcomes_path,
        "merged_terminal_outcomes": merged_terminals_path,
        "merged_behavior_observations": merged_behaviors_path,
        "repaired_report": repaired_report_path,
    }
    repair_resolved = sum(item.api_transport_resolved for item in repair_terminals)
    repair_calls = sum(item.api_call_count for item in repair_outcomes)
    repair_tokens = sum(item.total_model_tokens for item in repair_outcomes)
    repair_cost = sum(item.estimated_cost_usd for item in repair_outcomes)
    prior_calls = parent_manifest.cumulative_api_call_count
    prior_tokens = parent_manifest.cumulative_total_model_tokens
    prior_cost = parent_manifest.cumulative_estimated_cost_usd
    implementation = _implementation_manifest()
    values = {
        "wave_contract_id": contract.wave_contract_id,
        "wave_index": contract.wave_index,
        "parent_contract_id": contract.parent_contract_id,
        "parent_manifest_id": contract.parent_manifest_id,
        "source_contract_id": stable_contract.contract_id,
        "source_report_id": source["report"].report_id,
        "repaired_report_id": repaired_report.report_id,
        "source_stage": stable_contract.stage,
        "selected_job_count": len(contract.selected_jobs),
        "replacement_count": len(replacements),
        "repaired_transport_resolved_count": repair_resolved,
        "remaining_transport_unresolved_count": len(repair_terminals) - repair_resolved,
        "replacements": replacements,
        "replacement_set_hash": canonical_hash(
            tuple(item.model_dump(mode="json") for item in replacements),
            prefix="finance_stable_runtime_repair_wave_replacement_set:",
        ),
        "artifacts": {
            name: FrozenArtifactReference(path=str(path), sha256=_sha256(path))
            for name, path in artifact_paths.items()
        },
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_stable_runtime_repair_wave_implementation:",
        ),
        "discovered_models": tuple(discovered),
        "requested_model": contract.requested_model,
        "prior_cumulative_api_call_count": prior_calls,
        "repair_api_call_count": repair_calls,
        "cumulative_api_call_count": prior_calls + repair_calls,
        "prior_cumulative_total_model_tokens": prior_tokens,
        "repair_total_model_tokens": repair_tokens,
        "cumulative_total_model_tokens": prior_tokens + repair_tokens,
        "prior_cumulative_estimated_cost_usd": prior_cost,
        "repair_estimated_cost_usd": repair_cost,
        "cumulative_estimated_cost_usd": prior_cost + repair_cost,
        "runtime_measurement_ready": repaired_report.runtime_measurement_ready,
        "capability_support_admitted": repaired_report.capability_support_admitted,
        "fresh_confirmation_authorized": repaired_report.fresh_confirmation_authorized,
        "pro_sparse_anchor_authorized": repaired_report.pro_sparse_anchor_authorized,
        "next_permitted_stage": repaired_report.next_permitted_stage,
    }
    provisional = FinanceStableRuntimeRepairWaveManifest.model_construct(
        manifest_id="pending",
        **values,
    )
    manifest = FinanceStableRuntimeRepairWaveManifest(
        manifest_id=stable_runtime_repair_wave_manifest_id(provisional),
        **values,
    )
    manifest_path = output_dir / "finance_stable_runtime_repair_wave_manifest.json"
    _write_json_atomic(manifest_path, manifest.model_dump(mode="json"))
    _write_text_atomic(
        output_dir / "finance_stable_runtime_repair_wave_report.md",
        _render_wave_report(contract, manifest, repaired_report),
    )
    return manifest


ParentManifest: TypeAlias = (
    FinanceStableRuntimeRepairManifest | FinanceStableRuntimeRepairWaveManifest
)


def _load_parent_contract(
    path: Path,
) -> tuple[
    FinanceStableRuntimeRepairContract | FinanceStableRuntimeRepairWaveContract,
    str,
    Path,
]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    schema_version = raw.get("schema_version")
    if schema_version == "finance_stable_runtime_repair_contract.v1":
        contract = FinanceStableRuntimeRepairContract.model_validate(raw)
        source_dir = Path(contract.source_artifacts["report"].path).resolve().parent
        stable_path = source_dir / "finance_stable_support_contract.json"
        return contract, contract.repair_contract_id, stable_path
    if schema_version == STABLE_RUNTIME_REPAIR_WAVE_CONTRACT_VERSION:
        contract = FinanceStableRuntimeRepairWaveContract.model_validate(raw)
        return contract, contract.wave_contract_id, Path(contract.stable_contract.path)
    raise ValueError("Runtime repair wave parent contract version is unsupported")


def _load_parent_manifest(path: Path) -> ParentManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    schema_version = raw.get("schema_version")
    if schema_version == "finance_stable_runtime_repair_manifest.v1":
        return FinanceStableRuntimeRepairManifest.model_validate(raw)
    if schema_version == STABLE_RUNTIME_REPAIR_WAVE_MANIFEST_VERSION:
        return FinanceStableRuntimeRepairWaveManifest.model_validate(raw)
    raise ValueError("Runtime repair wave parent manifest version is unsupported")


def _parent_contract_id(manifest: ParentManifest) -> str:
    if isinstance(manifest, FinanceStableRuntimeRepairManifest):
        return manifest.repair_contract_id
    return manifest.wave_contract_id


def _source_paths_from_manifest(manifest: ParentManifest) -> dict[str, Path]:
    mapping = {
        "records": "merged_records",
        "outcomes": "merged_outcomes",
        "terminal_outcomes": "merged_terminal_outcomes",
        "behavior_observations": "merged_behavior_observations",
        "report": "repaired_report",
    }
    paths = {
        name: Path(manifest.artifacts[key].path).resolve()
        for name, key in mapping.items()
    }
    for name, key in mapping.items():
        if _sha256(paths[name]) != manifest.artifacts[key].sha256:
            raise ValueError(f"Runtime repair wave parent artifact changed:{key}")
    return paths


def _verify_inputs(
    contract: FinanceStableRuntimeRepairWaveContract,
) -> tuple[FinanceStableSupportContract, ParentManifest, dict[str, Any]]:
    if _implementation_manifest() != contract.implementation_manifest:
        raise ValueError("Runtime repair wave implementation changed after freeze")
    for reference in (
        contract.stable_contract,
        contract.parent_contract,
        contract.parent_manifest,
        *contract.source_artifacts.values(),
    ):
        if _sha256(Path(reference.path)) != reference.sha256:
            raise ValueError(f"Runtime repair wave frozen input changed:{reference.path}")
    stable_contract = FinanceStableSupportContract.model_validate_json(
        Path(contract.stable_contract.path).read_text(encoding="utf-8")
    )
    parent_manifest = _load_parent_manifest(Path(contract.parent_manifest.path))
    source = {
        "report": FinanceStableSupportReport.model_validate_json(
            Path(contract.source_artifacts["report"].path).read_text(encoding="utf-8")
        ),
        "records": _load_jsonl(
            Path(contract.source_artifacts["records"].path),
            CapabilityBoundaryRolloutRecord,
        ),
        "outcomes": _load_jsonl(
            Path(contract.source_artifacts["outcomes"].path),
            CapabilityRolloutOutcome,
        ),
        "terminals": _load_jsonl(
            Path(contract.source_artifacts["terminal_outcomes"].path),
            RuntimeTerminalOutcome,
        ),
        "behaviors": _load_jsonl(
            Path(contract.source_artifacts["behavior_observations"].path),
            SubmechanismBehaviorObservation,
        ),
    }
    _validate_source(
        stable_contract,
        source["report"],
        source["records"],
        source["outcomes"],
        source["terminals"],
    )
    if (
        stable_contract.contract_id != contract.stable_contract_id
        or source["report"].report_id != contract.source_report_id
        or parent_manifest.manifest_id != contract.parent_manifest_id
        or _parent_contract_id(parent_manifest) != contract.parent_contract_id
    ):
        raise ValueError("Runtime repair wave source identity changed")
    selected = tuple(
        (item.binding_id, item.replicate)
        for item in _selected_transport_failures(source["terminals"])
    )
    if selected != tuple(item.key for item in contract.selected_jobs):
        raise ValueError("Runtime repair wave selected set changed after freeze")
    return stable_contract, parent_manifest, source


def _validate_source(
    stable_contract: FinanceStableSupportContract,
    report: FinanceStableSupportReport,
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
) -> None:
    if report.contract_id != stable_contract.contract_id:
        raise ValueError("Runtime repair wave report crosses stable contract identity")
    if not (
        len(records)
        == len(outcomes)
        == len(terminals)
        == EXPECTED_ROLLOUT_COUNT
        == report.recorded_rollout_count
    ):
        raise ValueError("Runtime repair wave source denominator is incomplete")
    keys = (
        {_record_key(item) for item in records},
        {_outcome_key(item) for item in outcomes},
        {_terminal_key(item) for item in terminals},
    )
    if any(len(item) != EXPECTED_ROLLOUT_COUNT for item in keys):
        raise ValueError("Runtime repair wave source duplicates jobs")
    if len({frozenset(item) for item in keys}) != 1:
        raise ValueError("Runtime repair wave source artifacts disagree")


def _validate_merged_denominator(
    contract: FinanceStableSupportContract,
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
    behaviors: Sequence[SubmechanismBehaviorObservation],
) -> None:
    if not (
        len(records)
        == len(outcomes)
        == len(terminals)
        == len(behaviors)
        == contract.requested_rollout_count
    ):
        raise ValueError("Runtime repair wave merged denominator is incomplete")
    keys = (
        {_record_key(item) for item in records},
        {_outcome_key(item) for item in outcomes},
        {_terminal_key(item) for item in terminals},
        {(item.binding_id, item.replicate) for item in behaviors},
    )
    if any(len(item) != contract.requested_rollout_count for item in keys):
        raise ValueError("Runtime repair wave merged artifacts duplicate jobs")
    if len({frozenset(item) for item in keys}) != 1:
        raise ValueError("Runtime repair wave merged artifacts disagree")


def _load_checkpoint(
    path: Path,
    *,
    contract: FinanceStableRuntimeRepairWaveContract,
    stable_contract: FinanceStableSupportContract,
    run_identity: str,
) -> tuple[CapabilityBoundaryRolloutRecord, ...]:
    if not path.is_file():
        return ()
    records = _load_jsonl(path, CapabilityBoundaryRolloutRecord)
    selected = {item.key for item in contract.selected_jobs}
    observed: set[tuple[str, int]] = set()
    for record in records:
        key = _record_key(record)
        if key in observed:
            raise ValueError("Runtime repair wave checkpoint duplicates a job")
        observed.add(key)
        if (
            key not in selected
            or record.run_identity != run_identity
            or record.contract_id != stable_contract.contract_id
            or record.model_arm != ExplorerArm.FLASH
        ):
            raise ValueError("Runtime repair wave checkpoint contains another job")
    return records


def _replacements(
    contract: FinanceStableRuntimeRepairWaveContract,
    *,
    source_records: Sequence[CapabilityBoundaryRolloutRecord],
    repair_records: Sequence[CapabilityBoundaryRolloutRecord],
    repair_terminals: Sequence[RuntimeTerminalOutcome],
) -> tuple[RepairReplacement, ...]:
    source = {_record_key(item): item for item in source_records}
    repair = {_record_key(item): item for item in repair_records}
    terminals = {_terminal_key(item): item for item in repair_terminals}
    return tuple(
        RepairReplacement(
            binding_id=item.binding_id,
            replicate=item.replicate,
            source_record_id=source[item.key].record_id,
            repair_record_id=repair[item.key].record_id,
            repair_api_transport_resolved=terminals[item.key].api_transport_resolved,
            repair_semantic_answer_correct=terminals[item.key].semantic_answer_correct,
        )
        for item in contract.selected_jobs
    )


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        Path(__file__).resolve(),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_stable_submechanism_runtime_repair.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_stable_submechanism_support.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_capability_boundary_runner.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_multitier_runtime_resolution.py"
        ),
        root / "src/trusted_synthesis/runtime/agent/client.py",
        root / "src/trusted_synthesis/runtime/agent/iterative.py",
        root / "src/trusted_synthesis/runtime/agent/llm_agent.py",
        root / "src/trusted_synthesis/domains/finance/iterative_agent_verifier.py",
    )
    return {str(path.relative_to(root)): _sha256(path) for path in paths}


def _load_jsonl(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    return tuple(
        model.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _render_wave_report(
    contract: FinanceStableRuntimeRepairWaveContract,
    manifest: FinanceStableRuntimeRepairWaveManifest,
    report: FinanceStableSupportReport,
) -> str:
    return "\n".join(
        (
            f"# Finance v25.30 Selective Runtime Repair Wave {contract.wave_index}",
            "",
            f"- Wave contract: `{contract.wave_contract_id}`",
            f"- Parent manifest: `{contract.parent_manifest_id}`",
            f"- Frozen unresolved L0 jobs: **{manifest.selected_job_count}**",
            (
                "- Transport resolved in this wave: "
                f"**{manifest.repaired_transport_resolved_count}/"
                f"{manifest.selected_job_count}**"
            ),
            (
                "- Every selected job was replaced regardless of semantic success; "
                "no resolved or semantic result from prior waves was resampled."
            ),
            f"- Runtime ready: **{manifest.runtime_measurement_ready}**",
            f"- Capability support admitted: **{manifest.capability_support_admitted}**",
            f"- Next permitted stage: `{manifest.next_permitted_stage}`",
            (
                "- Cumulative telemetry cost estimate: "
                f"**US${manifest.cumulative_estimated_cost_usd:.6f}** "
                "(provider invoice may differ)"
            ),
            "",
            _render_report(report),
        )
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded follow-up wave for unresolved L0 transport jobs"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--parent-contract", required=True, type=Path)
    prepare.add_argument("--parent-manifest", required=True, type=Path)
    prepare.add_argument("--output-path", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    run = commands.add_parser("run")
    run.add_argument("--contract", required=True, type=Path)
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--workers", type=int, default=2)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "prepare":
        result: Any = prepare_stable_runtime_repair_wave(
            parent_contract_path=args.parent_contract,
            parent_manifest_path=args.parent_manifest,
            output_path=args.output_path,
            run_id=args.run_id,
        )
        summary = {
            "wave_contract_id": result.wave_contract_id,
            "wave_index": result.wave_index,
            "selected_job_count": len(result.selected_jobs),
        }
    else:
        result = run_stable_runtime_repair_wave(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        summary = {
            "manifest_id": result.manifest_id,
            "wave_index": result.wave_index,
            "selected_job_count": result.selected_job_count,
            "repaired_transport_resolved_count": result.repaired_transport_resolved_count,
            "runtime_measurement_ready": result.runtime_measurement_ready,
            "capability_support_admitted": result.capability_support_admitted,
            "next_permitted_stage": result.next_permitted_stage,
        }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
