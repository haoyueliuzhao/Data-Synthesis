from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    RuntimeTaskBinding,
)
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
    FailureLayer,
    RuntimeTerminalOutcome,
    _make_terminal_outcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
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

STABLE_RUNTIME_REPAIR_CONTRACT_VERSION = (
    "finance_stable_runtime_repair_contract.v1"
)
STABLE_RUNTIME_REPAIR_MANIFEST_VERSION = (
    "finance_stable_runtime_repair_manifest.v1"
)
STABLE_RUNTIME_REPAIR_RUNNER_VERSION = "finance_stable_runtime_repair_runner.v1"
SELECTION_POLICY: Final[
    Literal["all_frozen_l0_external_transport_failures.v1"]
] = "all_frozen_l0_external_transport_failures.v1"
REPLACEMENT_POLICY: Final[
    Literal["replace_every_selected_job_with_first_repair_attempt.v1"]
] = "replace_every_selected_job_with_first_repair_attempt.v1"
SOURCE_ARTIFACT_NAMES = (
    "checkpoint",
    "records",
    "outcomes",
    "terminal_outcomes",
    "behavior_observations",
    "report",
    "manifest",
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


class FrozenArtifactReference(FrozenModel):
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)


class StableRuntimeRepairJob(FrozenModel):
    binding_id: str = Field(min_length=1)
    task_artifact_id: str = Field(min_length=1)
    replicate: int = Field(ge=0)
    source_record_id: str = Field(min_length=1)
    source_outcome_id: str = Field(min_length=1)
    source_terminal_outcome_id: str = Field(min_length=1)
    rollout_identity_token: str = Field(min_length=1)
    source_primary_failure_layer: Literal["l0_external_infrastructure"] = (
        "l0_external_infrastructure"
    )
    source_api_transport_resolved: Literal[False] = False

    @property
    def key(self) -> tuple[str, int]:
        return self.binding_id, self.replicate


class FinanceStableRuntimeRepairContract(FrozenModel):
    repair_contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    source_report_id: str = Field(min_length=1)
    source_stage: Literal["development", "confirmation"]
    source_artifacts: dict[str, FrozenArtifactReference]
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    selection_policy: Literal[
        "all_frozen_l0_external_transport_failures.v1"
    ] = SELECTION_POLICY
    replacement_policy: Literal[
        "replace_every_selected_job_with_first_repair_attempt.v1"
    ] = REPLACEMENT_POLICY
    repair_attempt_number: Literal[1] = 1
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
    next_permitted_stage: Literal["selective_runtime_repair"] = (
        "selective_runtime_repair"
    )
    schema_version: str = STABLE_RUNTIME_REPAIR_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceStableRuntimeRepairContract:
        if set(self.source_artifacts) != set(SOURCE_ARTIFACT_NAMES):
            raise ValueError("stable Runtime repair source artifact set is incomplete")
        keys = [item.key for item in self.selected_jobs]
        if len(set(keys)) != len(keys):
            raise ValueError("stable Runtime repair duplicates a selected job")
        if tuple(keys) != tuple(sorted(keys)):
            raise ValueError("stable Runtime repair jobs are not canonically ordered")
        if self.selected_job_set_hash != canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.selected_jobs),
            prefix="finance_stable_runtime_repair_job_set:",
        ):
            raise ValueError("stable Runtime repair job-set identity is invalid")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stable_runtime_repair_implementation:",
        ):
            raise ValueError("stable Runtime repair implementation identity is invalid")
        if self.repair_contract_id != stable_runtime_repair_contract_id(self):
            raise ValueError("stable Runtime repair contract identity is invalid")
        return self


class RepairReplacement(FrozenModel):
    binding_id: str = Field(min_length=1)
    replicate: int = Field(ge=0)
    source_record_id: str = Field(min_length=1)
    repair_record_id: str = Field(min_length=1)
    repair_api_transport_resolved: bool
    repair_semantic_answer_correct: bool


class FinanceStableRuntimeRepairManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    repair_contract_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    source_report_id: str = Field(min_length=1)
    repaired_report_id: str = Field(min_length=1)
    source_stage: Literal["development", "confirmation"]
    selection_policy: Literal[
        "all_frozen_l0_external_transport_failures.v1"
    ] = SELECTION_POLICY
    replacement_policy: Literal[
        "replace_every_selected_job_with_first_repair_attempt.v1"
    ] = REPLACEMENT_POLICY
    selected_job_count: int = Field(ge=1)
    replacement_count: int = Field(ge=1)
    repaired_transport_resolved_count: int = Field(ge=0)
    remaining_transport_unresolved_count: int = Field(ge=0)
    replacements: tuple[RepairReplacement, ...] = Field(min_length=1)
    replacement_set_hash: str = Field(min_length=1)
    execution_implementation_snapshot: FrozenArtifactReference
    finalization_implementation_manifest: dict[str, str]
    finalization_implementation_manifest_hash: str = Field(min_length=1)
    artifacts: dict[str, FrozenArtifactReference]
    discovered_models: tuple[str, ...]
    requested_model: str = Field(min_length=1)
    source_api_call_count: int = Field(ge=0)
    repair_api_call_count: int = Field(ge=0)
    cumulative_api_call_count: int = Field(ge=0)
    source_total_model_tokens: int = Field(ge=0)
    repair_total_model_tokens: int = Field(ge=0)
    cumulative_total_model_tokens: int = Field(ge=0)
    source_estimated_cost_usd: float = Field(ge=0)
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
    schema_version: str = STABLE_RUNTIME_REPAIR_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> FinanceStableRuntimeRepairManifest:
        if set(self.artifacts) != set(OUTPUT_ARTIFACT_NAMES):
            raise ValueError("stable Runtime repair output artifact set is incomplete")
        if not (
            self.selected_job_count
            == self.replacement_count
            == len(self.replacements)
        ):
            raise ValueError("stable Runtime repair did not replace its full selected set")
        if (
            self.repaired_transport_resolved_count
            + self.remaining_transport_unresolved_count
            != self.selected_job_count
        ):
            raise ValueError("stable Runtime repair transport denominator is incomplete")
        if self.replacement_set_hash != canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.replacements),
            prefix="finance_stable_runtime_repair_replacement_set:",
        ):
            raise ValueError("stable Runtime repair replacement identity is invalid")
        if self.finalization_implementation_manifest_hash != canonical_hash(
            self.finalization_implementation_manifest,
            prefix="finance_stable_runtime_repair_finalization_implementation:",
        ):
            raise ValueError("stable Runtime repair finalization identity is invalid")
        if self.cumulative_api_call_count != (
            self.source_api_call_count + self.repair_api_call_count
        ):
            raise ValueError("stable Runtime repair API accounting is incomplete")
        if self.cumulative_total_model_tokens != (
            self.source_total_model_tokens + self.repair_total_model_tokens
        ):
            raise ValueError("stable Runtime repair token accounting is incomplete")
        if abs(
            self.cumulative_estimated_cost_usd
            - (self.source_estimated_cost_usd + self.repair_estimated_cost_usd)
        ) > 1e-9:
            raise ValueError("stable Runtime repair cost accounting is incomplete")
        if self.manifest_id != stable_runtime_repair_manifest_id(self):
            raise ValueError("stable Runtime repair manifest identity is invalid")
        return self


def stable_runtime_repair_contract_id(
    value: FinanceStableRuntimeRepairContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"repair_contract_id"}),
        prefix="finance_stable_runtime_repair_contract:",
    )


def stable_runtime_repair_manifest_id(
    value: FinanceStableRuntimeRepairManifest,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_stable_runtime_repair_manifest:",
    )


def prepare_stable_runtime_repair(
    *,
    source_dir: Path,
    output_path: Path,
    run_id: str,
) -> FinanceStableRuntimeRepairContract:
    if output_path.exists():
        raise ValueError("stable Runtime repair contract is immutable")
    source_dir = source_dir.resolve()
    source = _load_source_bundle(source_dir)
    stable_contract = source["contract"]
    report = source["report"]
    records = source["records"]
    outcomes = source["outcomes"]
    terminals = source["terminals"]
    _validate_source_bundle(stable_contract, report, records, outcomes, terminals)
    if (
        report.runtime_measurement_ready
        or report.next_permitted_stage != "runtime_measurement_repair_only"
    ):
        raise ValueError("stable Runtime repair lacks a frozen Runtime-only failure")
    record_by_key = {_record_key(item): item for item in records}
    outcome_by_key = {_outcome_key(item): item for item in outcomes}
    selected_terminals = _selected_transport_failures(terminals)
    selected_jobs = tuple(
        StableRuntimeRepairJob(
            binding_id=item.binding_id,
            task_artifact_id=item.task_artifact_id,
            replicate=item.replicate,
            source_record_id=record_by_key[_terminal_key(item)].record_id,
            source_outcome_id=outcome_by_key[_terminal_key(item)].outcome_id,
            source_terminal_outcome_id=item.terminal_outcome_id,
            rollout_identity_token=stable_contract.rollout_identity_tokens[
                f"{item.binding_id}|{item.replicate}"
            ],
        )
        for item in selected_terminals
    )
    if not selected_jobs:
        raise ValueError("stable Runtime repair selected no L0 transport failure")
    implementation = _implementation_manifest()
    values = {
        "run_id": run_id,
        "source_contract_id": stable_contract.contract_id,
        "source_report_id": report.report_id,
        "source_stage": stable_contract.stage,
        "source_artifacts": source["references"],
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_stable_runtime_repair_implementation:",
        ),
        "selected_jobs": selected_jobs,
        "selected_job_set_hash": canonical_hash(
            tuple(item.model_dump(mode="json") for item in selected_jobs),
            prefix="finance_stable_runtime_repair_job_set:",
        ),
        "requested_model": stable_contract.model_contracts[0].requested_model,
    }
    provisional = FinanceStableRuntimeRepairContract.model_construct(
        repair_contract_id="pending",
        **values,
    )
    contract = FinanceStableRuntimeRepairContract(
        repair_contract_id=stable_runtime_repair_contract_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_stable_runtime_repair(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
    execution_implementation_snapshot_path: Path | None = None,
) -> FinanceStableRuntimeRepairManifest:
    if workers < 1:
        raise ValueError("stable Runtime repair workers must be positive")
    contract = FinanceStableRuntimeRepairContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    source, execution_snapshot = _verify_repair_inputs(
        contract,
        execution_implementation_snapshot_path=execution_implementation_snapshot_path,
    )
    stable_contract = source["contract"]
    source_report = source["report"]
    source_records = source["records"]
    tasks = {item.artifact_id: item for item in stable_contract.tasks}
    bindings = {item.binding_id: item for item in stable_contract.bindings}
    selected = {item.key: item for item in contract.selected_jobs}
    output_dir.mkdir(parents=True, exist_ok=True)
    run_identity = canonical_hash(
        {
            "repair_contract_id": contract.repair_contract_id,
            "runner_version": STABLE_RUNTIME_REPAIR_RUNNER_VERSION,
            "selected_job_set_hash": contract.selected_job_set_hash,
            "repair_attempt_number": contract.repair_attempt_number,
        },
        prefix="finance_stable_runtime_repair_run:",
    )
    checkpoint_path = output_dir / "stable_runtime_repair.checkpoint.jsonl"
    repair_records_path = output_dir / "stable_runtime_repair_records.jsonl"
    repair_outcomes_path = output_dir / "stable_runtime_repair_outcomes.jsonl"
    repair_terminals_path = output_dir / "stable_runtime_repair_terminal_outcomes.jsonl"
    discovery_path = output_dir / "stable_runtime_repair_model_discovery.json"
    repair_records = {
        _record_key(item): item
        for item in _load_repair_checkpoint(
            checkpoint_path,
            contract=contract,
            source_contract=stable_contract,
            run_identity=run_identity,
        )
    }
    jobs = tuple(
        (bindings[item.binding_id], item.replicate)
        for item in contract.selected_jobs
    )
    pending = tuple(job for job in jobs if _job_key(*job) not in repair_records)
    if execution_snapshot.path != str(Path(__file__).resolve()) and pending:
        raise ValueError(
            "stable Runtime repair historical execution may only finalize a complete checkpoint"
        )
    print(
        f"[stable-runtime-repair] resuming {len(repair_records)}/{len(jobs)}; "
        f"executing {len(pending)} with {min(workers, max(1, len(pending)))} workers",
        flush=True,
    )
    model_contract = stable_contract.model_contracts[0]
    if model_contract.arm != ExplorerArm.FLASH:
        raise ValueError("stable Runtime repair source is not Flash-only")
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
            for index, future in enumerate(as_completed(futures), start=1):
                key = futures[future]
                record = future.result()
                if _record_key(record) != key:
                    raise ValueError("stable Runtime repair worker crossed a frozen job")
                _append_jsonl(checkpoint_path, record.model_dump(mode="json"))
                repair_records[key] = record
                if index % 4 == 0 or index == len(futures):
                    print(
                        f"[stable-runtime-repair] completed "
                        f"{len(repair_records)}/{len(jobs)}",
                        flush=True,
                    )
    else:
        discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
        if discovery.get("run_identity") != run_identity:
            raise ValueError("stable Runtime repair model discovery changed identity")
        discovered = tuple(str(item) for item in discovery.get("discovered_models", ()))
    ordered_repair_records = tuple(
        repair_records[_job_key(binding, replicate)]
        for binding, replicate in jobs
    )
    if set(repair_records) != set(selected):
        raise ValueError("stable Runtime repair executed outside its selected job set")
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
        selected_keys=set(selected),
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
    replacements = _make_replacements(
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
    repair_api_calls = sum(item.api_call_count for item in repair_outcomes)
    repair_tokens = sum(item.total_model_tokens for item in repair_outcomes)
    repair_cost = sum(item.estimated_cost_usd for item in repair_outcomes)
    manifest_values = {
        "repair_contract_id": contract.repair_contract_id,
        "source_contract_id": stable_contract.contract_id,
        "source_report_id": source_report.report_id,
        "repaired_report_id": repaired_report.report_id,
        "source_stage": stable_contract.stage,
        "selected_job_count": len(contract.selected_jobs),
        "replacement_count": len(replacements),
        "repaired_transport_resolved_count": repair_resolved,
        "remaining_transport_unresolved_count": len(repair_terminals) - repair_resolved,
        "replacements": replacements,
        "replacement_set_hash": canonical_hash(
            tuple(item.model_dump(mode="json") for item in replacements),
            prefix="finance_stable_runtime_repair_replacement_set:",
        ),
        "execution_implementation_snapshot": execution_snapshot,
        "finalization_implementation_manifest": _implementation_manifest(),
        "finalization_implementation_manifest_hash": canonical_hash(
            _implementation_manifest(),
            prefix="finance_stable_runtime_repair_finalization_implementation:",
        ),
        "artifacts": {
            name: FrozenArtifactReference(path=str(path), sha256=_sha256(path))
            for name, path in artifact_paths.items()
        },
        "discovered_models": tuple(discovered),
        "requested_model": contract.requested_model,
        "source_api_call_count": source_report.api_call_count,
        "repair_api_call_count": repair_api_calls,
        "cumulative_api_call_count": source_report.api_call_count + repair_api_calls,
        "source_total_model_tokens": source_report.total_model_tokens,
        "repair_total_model_tokens": repair_tokens,
        "cumulative_total_model_tokens": source_report.total_model_tokens + repair_tokens,
        "source_estimated_cost_usd": source_report.estimated_cost_usd,
        "repair_estimated_cost_usd": repair_cost,
        "cumulative_estimated_cost_usd": source_report.estimated_cost_usd + repair_cost,
        "runtime_measurement_ready": repaired_report.runtime_measurement_ready,
        "capability_support_admitted": repaired_report.capability_support_admitted,
        "fresh_confirmation_authorized": repaired_report.fresh_confirmation_authorized,
        "pro_sparse_anchor_authorized": repaired_report.pro_sparse_anchor_authorized,
        "next_permitted_stage": repaired_report.next_permitted_stage,
    }
    provisional = FinanceStableRuntimeRepairManifest.model_construct(
        manifest_id="pending",
        **manifest_values,
    )
    manifest = FinanceStableRuntimeRepairManifest(
        manifest_id=stable_runtime_repair_manifest_id(provisional),
        **manifest_values,
    )
    manifest_path = output_dir / "finance_stable_runtime_repair_manifest.json"
    _write_json_atomic(manifest_path, manifest.model_dump(mode="json"))
    _write_text_atomic(
        output_dir / "finance_stable_runtime_repair_report.md",
        _render_repair_report(contract, manifest, repaired_report),
    )
    return manifest


def _selected_transport_failures(
    terminals: Sequence[RuntimeTerminalOutcome],
) -> tuple[RuntimeTerminalOutcome, ...]:
    selected = tuple(
        sorted(
            (
                item
                for item in terminals
                if item.primary_failure_layer == FailureLayer.L0_EXTERNAL_INFRASTRUCTURE
                and not item.api_transport_resolved
            ),
            key=_terminal_key,
        )
    )
    if any(
        item.runtime_eligible_for_capability_denominator
        or item.semantic_answer_correct
        or item.valid_success
        for item in selected
    ):
        raise ValueError("stable Runtime repair selected a capability outcome")
    return selected


def _make_partial_terminals(
    contract: Any,
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
    *,
    bindings: Sequence[RuntimeTaskBinding],
) -> tuple[RuntimeTerminalOutcome, ...]:
    if not records or len(records) != len(outcomes):
        raise ValueError("stable Runtime repair terminal subset is incomplete")
    record_by_key = {_record_key(item): item for item in records}
    outcome_by_key = {_outcome_key(item): item for item in outcomes}
    binding_by_id = {item.binding_id: item for item in bindings}
    if (
        len(record_by_key) != len(records)
        or len(outcome_by_key) != len(outcomes)
        or set(record_by_key) != set(outcome_by_key)
    ):
        raise ValueError("stable Runtime repair terminal subset differs across artifacts")
    if any(key[0] not in binding_by_id for key in record_by_key):
        raise ValueError("stable Runtime repair terminal subset contains another binding")
    return tuple(
        _make_terminal_outcome(
            cast(Any, contract),
            record_by_key[key],
            outcome_by_key[key],
            binding_by_id[key[0]],
        )
        for key in sorted(record_by_key)
    )


def _merge_selected_records(
    source_records: Sequence[CapabilityBoundaryRolloutRecord],
    repair_records: Sequence[CapabilityBoundaryRolloutRecord],
    *,
    selected_keys: set[tuple[str, int]],
) -> tuple[CapabilityBoundaryRolloutRecord, ...]:
    source_by_key = {_record_key(item): item for item in source_records}
    repair_by_key = {_record_key(item): item for item in repair_records}
    if len(source_by_key) != len(source_records):
        raise ValueError("stable Runtime repair source records duplicate a job")
    if set(repair_by_key) != selected_keys:
        raise ValueError("stable Runtime repair attempts differ from frozen selection")
    if not selected_keys <= set(source_by_key):
        raise ValueError("stable Runtime repair selection is absent from source records")
    return tuple(
        repair_by_key.get(_record_key(item), item)
        for item in source_records
    )


def _make_replacements(
    contract: FinanceStableRuntimeRepairContract,
    *,
    source_records: Sequence[CapabilityBoundaryRolloutRecord],
    repair_records: Sequence[CapabilityBoundaryRolloutRecord],
    repair_terminals: Sequence[RuntimeTerminalOutcome],
) -> tuple[RepairReplacement, ...]:
    source_by_key = {_record_key(item): item for item in source_records}
    repair_by_key = {_record_key(item): item for item in repair_records}
    terminal_by_key = {_terminal_key(item): item for item in repair_terminals}
    replacements = tuple(
        RepairReplacement(
            binding_id=item.binding_id,
            replicate=item.replicate,
            source_record_id=source_by_key[item.key].record_id,
            repair_record_id=repair_by_key[item.key].record_id,
            repair_api_transport_resolved=terminal_by_key[item.key].api_transport_resolved,
            repair_semantic_answer_correct=terminal_by_key[item.key].semantic_answer_correct,
        )
        for item in contract.selected_jobs
    )
    if any(
        item.source_record_id != source_by_key[(item.binding_id, item.replicate)].record_id
        for item in replacements
    ):
        raise ValueError("stable Runtime repair replacement changed source identity")
    return replacements


def _load_source_bundle(source_dir: Path) -> dict[str, Any]:
    contract_path = source_dir / "finance_stable_support_contract.json"
    stable_contract = FinanceStableSupportContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    prefix = f"stable_support_{stable_contract.stage}"
    paths = {
        "checkpoint": source_dir / f"{prefix}.checkpoint.jsonl",
        "records": source_dir / f"{prefix}_records.jsonl",
        "outcomes": source_dir / f"{prefix}_outcomes.jsonl",
        "terminal_outcomes": source_dir / f"{prefix}_terminal_outcomes.jsonl",
        "behavior_observations": source_dir / f"{prefix}_behavior_observations.jsonl",
        "report": source_dir / "finance_stable_support_report.json",
        "manifest": source_dir / "finance_stable_support_manifest.json",
    }
    for path in (contract_path, *paths.values()):
        if not path.is_file():
            raise ValueError(f"stable Runtime repair source artifact is missing:{path}")
    return {
        "contract_path": contract_path,
        "contract": stable_contract,
        "report": FinanceStableSupportReport.model_validate_json(
            paths["report"].read_text(encoding="utf-8")
        ),
        "records": _load_jsonl(paths["records"], CapabilityBoundaryRolloutRecord),
        "outcomes": _load_jsonl(paths["outcomes"], CapabilityRolloutOutcome),
        "terminals": _load_jsonl(paths["terminal_outcomes"], RuntimeTerminalOutcome),
        "behaviors": _load_jsonl(
            paths["behavior_observations"],
            SubmechanismBehaviorObservation,
        ),
        "manifest_raw": json.loads(paths["manifest"].read_text(encoding="utf-8")),
        "references": {
            name: FrozenArtifactReference(path=str(path), sha256=_sha256(path))
            for name, path in paths.items()
        },
    }


def _verify_repair_inputs(
    contract: FinanceStableRuntimeRepairContract,
    *,
    execution_implementation_snapshot_path: Path | None,
) -> tuple[dict[str, Any], FrozenArtifactReference]:
    current = _implementation_manifest()
    module_key = str(Path(__file__).resolve().relative_to(Path(__file__).resolve().parents[4]))
    changed = {
        key
        for key, expected in contract.implementation_manifest.items()
        if current.get(key) != expected
    }
    if changed:
        if changed != {module_key} or execution_implementation_snapshot_path is None:
            raise ValueError("stable Runtime repair implementation changed after freeze")
        snapshot_path = execution_implementation_snapshot_path.resolve()
        expected_hash = contract.implementation_manifest[module_key]
        if _sha256(snapshot_path) != expected_hash:
            raise ValueError("stable Runtime repair execution snapshot is not frozen code")
        execution_snapshot = FrozenArtifactReference(
            path=str(snapshot_path),
            sha256=expected_hash,
        )
    else:
        module_path = Path(__file__).resolve()
        execution_snapshot = FrozenArtifactReference(
            path=str(module_path),
            sha256=_sha256(module_path),
        )
    source_dir = Path(contract.source_artifacts["report"].path).resolve().parent
    source = _load_source_bundle(source_dir)
    for name, reference in contract.source_artifacts.items():
        observed = source["references"][name]
        if observed.path != reference.path or observed.sha256 != reference.sha256:
            raise ValueError(f"stable Runtime repair source changed:{name}")
    stable_contract = source["contract"]
    report = source["report"]
    _validate_source_bundle(
        stable_contract,
        report,
        source["records"],
        source["outcomes"],
        source["terminals"],
    )
    if (
        stable_contract.contract_id != contract.source_contract_id
        or report.report_id != contract.source_report_id
    ):
        raise ValueError("stable Runtime repair source identity changed")
    selected = _selected_transport_failures(source["terminals"])
    expected = tuple((item.binding_id, item.replicate) for item in selected)
    observed = tuple(item.key for item in contract.selected_jobs)
    if observed != expected:
        raise ValueError("stable Runtime repair selection changed after freeze")
    return source, execution_snapshot


def _validate_source_bundle(
    contract: FinanceStableSupportContract,
    report: FinanceStableSupportReport,
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
) -> None:
    if report.contract_id != contract.contract_id:
        raise ValueError("stable Runtime repair report crosses contract identity")
    if not (
        len(records)
        == len(outcomes)
        == len(terminals)
        == EXPECTED_ROLLOUT_COUNT
        == report.recorded_rollout_count
    ):
        raise ValueError("stable Runtime repair source denominator is incomplete")
    keys = {
        "records": {_record_key(item) for item in records},
        "outcomes": {_outcome_key(item) for item in outcomes},
        "terminals": {_terminal_key(item) for item in terminals},
    }
    if any(len(value) != EXPECTED_ROLLOUT_COUNT for value in keys.values()):
        raise ValueError("stable Runtime repair source duplicates rollout identity")
    if len({frozenset(value) for value in keys.values()}) != 1:
        raise ValueError("stable Runtime repair source artifacts disagree on jobs")


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
        raise ValueError("stable Runtime repair merged denominator is incomplete")
    key_sets = (
        {_record_key(item) for item in records},
        {_outcome_key(item) for item in outcomes},
        {_terminal_key(item) for item in terminals},
        {(item.binding_id, item.replicate) for item in behaviors},
    )
    if any(len(value) != contract.requested_rollout_count for value in key_sets):
        raise ValueError("stable Runtime repair merged artifacts duplicate jobs")
    if len({frozenset(value) for value in key_sets}) != 1:
        raise ValueError("stable Runtime repair merged artifacts disagree on jobs")


def _load_repair_checkpoint(
    path: Path,
    *,
    contract: FinanceStableRuntimeRepairContract,
    source_contract: FinanceStableSupportContract,
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
            raise ValueError("stable Runtime repair checkpoint duplicates a job")
        observed.add(key)
        if (
            key not in selected
            or record.run_identity != run_identity
            or record.contract_id != source_contract.contract_id
            or record.model_arm != ExplorerArm.FLASH
        ):
            raise ValueError("stable Runtime repair checkpoint contains another job")
    return records


def _resolve_model_discovery(
    client: OpenAICompatibleJsonClient,
    path: Path,
    *,
    run_identity: str,
    requested_model: str,
) -> tuple[str, ...]:
    if path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if (
            raw.get("run_identity") != run_identity
            or raw.get("requested_model") != requested_model
        ):
            raise ValueError("stable Runtime repair discovery identity changed")
        discovered = tuple(str(item) for item in raw.get("discovered_models", ()))
    else:
        discovered = tuple(client.discover_models())
        _write_json_atomic(
            path,
            {
                "run_identity": run_identity,
                "requested_model": requested_model,
                "discovered_models": discovered,
            },
        )
    if requested_model not in discovered:
        raise ValueError("stable Runtime repair provider lacks the frozen Flash model")
    return discovered


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        Path(__file__).resolve(),
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
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_capability_submechanism_flash_development.py"
        ),
        root / "src/trusted_synthesis/runtime/agent/client.py",
        root / "src/trusted_synthesis/runtime/agent/iterative.py",
        root / "src/trusted_synthesis/runtime/agent/llm_agent.py",
        root / "src/trusted_synthesis/domains/finance/iterative_agent_verifier.py",
    )
    return {str(path.relative_to(root)): _sha256(path) for path in paths}


def _record_key(item: CapabilityBoundaryRolloutRecord) -> tuple[str, int]:
    return item.binding_id, item.replicate


def _outcome_key(item: CapabilityRolloutOutcome) -> tuple[str, int]:
    return item.binding_id, item.replicate


def _terminal_key(item: RuntimeTerminalOutcome) -> tuple[str, int]:
    return item.binding_id, item.replicate


def _job_key(binding: RuntimeTaskBinding, replicate: int) -> tuple[str, int]:
    return binding.binding_id, replicate


def _load_jsonl(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    return tuple(
        model.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def _write_json_atomic(path: Path, value: object) -> None:
    _write_text_atomic(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl_atomic(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    _write_text_atomic(
        path,
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in values),
    )


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _render_repair_report(
    contract: FinanceStableRuntimeRepairContract,
    manifest: FinanceStableRuntimeRepairManifest,
    report: FinanceStableSupportReport,
) -> str:
    return "\n".join(
        (
            "# Finance v25.30 Selective Runtime Repair",
            "",
            "## Repair Contract",
            "",
            f"- Repair contract: `{contract.repair_contract_id}`",
            f"- Frozen source report: `{manifest.source_report_id}`",
            f"- Selected L0 transport failures: **{manifest.selected_job_count}**",
            (
                "- Repaired transport resolutions: "
                f"**{manifest.repaired_transport_resolved_count}/"
                f"{manifest.selected_job_count}**"
            ),
            (
                "- Replacement policy: every frozen selected job is replaced by its "
                "first repair attempt, regardless of semantic success."
            ),
            f"- Runtime ready after repair: **{manifest.runtime_measurement_ready}**",
            f"- Capability support admitted: **{manifest.capability_support_admitted}**",
            f"- Next permitted stage: `{manifest.next_permitted_stage}`",
            "",
            "## Resource Accounting",
            "",
            f"- Source API calls: **{manifest.source_api_call_count:,}**",
            f"- Repair API calls: **{manifest.repair_api_call_count:,}**",
            f"- Cumulative tokens: **{manifest.cumulative_total_model_tokens:,}**",
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
        description="Repair only frozen L0 transport failures in stable support"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--source-dir", required=True, type=Path)
    prepare.add_argument("--output-path", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    run = commands.add_parser("run")
    run.add_argument("--contract", required=True, type=Path)
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--workers", type=int, default=4)
    run.add_argument("--execution-implementation-snapshot", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "prepare":
        result: Any = prepare_stable_runtime_repair(
            source_dir=args.source_dir,
            output_path=args.output_path,
            run_id=args.run_id,
        )
        summary = {
            "repair_contract_id": result.repair_contract_id,
            "selected_job_count": len(result.selected_jobs),
            "next_permitted_stage": result.next_permitted_stage,
        }
    else:
        result = run_stable_runtime_repair(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
            execution_implementation_snapshot_path=(
                args.execution_implementation_snapshot
            ),
        )
        summary = {
            "manifest_id": result.manifest_id,
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
