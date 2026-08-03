from __future__ import annotations

import hashlib
import json
import math
import random
import re
import time
from collections.abc import Iterable, Mapping
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal

from trusted_synthesis.core.vtdo.round import VTDORoundArtifact
from trusted_synthesis.hashing import canonical_hash

from .evaluation import BenchmarkLeakageAudit, audit_external_benchmark_leakage
from .multistate import FinanceTaskStateArtifact
from .round_io import load_vtdo_round_artifacts
from .schema import (
    VTDO_EXPERIMENT_VERSION,
    VTDO_TRAINING_ARMS,
    CCGRTaskDistribution,
    TrainingArmCapacity,
    TrainingExperimentConfig,
    TrainingExperimentPreflight,
    VTDOStudentTrainingConfig,
    VTDOTrainingArm,
    VTDOTrainingRecord,
    VTDOTrainingRunResult,
    training_experiment_preflight_hash,
    vtdo_training_record_id,
    vtdo_training_run_result_id,
)

_SYSTEM_PROMPT = (
    "You are a host-instrumented proof-carrying evidence agent. Use only the supplied public "
    "task and public evidence corpus. Return one host_instrumented_decisions.v1 JSON object "
    "containing model decisions, tool arguments, evidence selections, operation bindings, "
    "and the final answer. The host executes tools and creates observations; never fabricate "
    "host observations, execution results, or hidden Oracle fields."
)
_IMMUTABLE_REVISION = re.compile(r"[0-9a-fA-F]{40,64}")
_PRIMARY_CAUSAL_ARMS: tuple[VTDOTrainingArm, ...] = (
    "B2_validity",
    "B2_contribution_only",
    "B2_novelty_only",
    "B4_random_state",
    "B5_vtdo",
)
_SECONDARY_COMPARISON_ARMS: tuple[VTDOTrainingArm, ...] = ("B1_raw", "B3_ccgr")


def build_training_experiment_preflight(
    config: TrainingExperimentConfig,
    *,
    artifacts: Iterable[FinanceTaskStateArtifact],
    vtdo_round_artifact_paths: tuple[Path, ...],
    primary_training_round: int,
) -> tuple[
    TrainingExperimentPreflight,
    dict[str, tuple[VTDOTrainingRecord, ...]],
    BenchmarkLeakageAudit,
]:
    """Build the frozen causal and secondary arms without legacy artifacts."""

    student = VTDOStudentTrainingConfig.from_json(config.training_config_path)
    tasks = tuple(sorted(artifacts, key=lambda item: item.omega.task.task_id))
    task_ids = {item.omega.task.task_id for item in tasks}
    b1_records: list[VTDOTrainingRecord] = []
    for artifact in tasks:
        count = len(artifact.accepted_states) + len(artifact.rejected_attempts)
        task_weight = 1.0 / count
        b1_records.extend(
            _record_from_state(artifact, state, "B1_raw", sampling_weight=task_weight)
            for state in artifact.accepted_states
        )
        b1_records.extend(
            _record_from_rejected(
                artifact,
                attempt,
                "B1_raw",
                sampling_weight=task_weight,
            )
            for attempt in artifact.rejected_attempts
        )
    b1 = tuple(b1_records)
    b2 = tuple(
        _record_from_state(
            artifact,
            state,
            "B2_validity",
            sampling_weight=1.0 / len(artifact.accepted_states),
        )
        for artifact in tasks
        for state in artifact.accepted_states
    )
    b4 = tuple(
        _record_from_state(
            artifact,
            _random_state(artifact, seed=config.seeds[0]),
            "B4_random_state",
            sampling_weight=1.0,
        )
        for artifact in tasks
    )

    b3, b3_blockers = _ccgr_arm(config.ccgr_task_distribution_path, tasks)
    contribution_only, contribution_blockers = _component_arm(
        vtdo_round_artifact_paths,
        tasks,
        selected_round=primary_training_round,
        arm_id="B2_contribution_only",
        component="contribution",
    )
    novelty_only, novelty_blockers = _component_arm(
        vtdo_round_artifact_paths,
        tasks,
        selected_round=primary_training_round,
        arm_id="B2_novelty_only",
        component="novelty",
    )
    b5, b5_blockers = _vtdo_arm(
        vtdo_round_artifact_paths,
        tasks,
        selected_round=primary_training_round,
    )
    arms: dict[str, tuple[VTDOTrainingRecord, ...]] = {
        "B1_raw": b1,
        "B2_validity": b2,
        "B2_contribution_only": contribution_only,
        "B2_novelty_only": novelty_only,
        "B3_ccgr": b3,
        "B4_random_state": b4,
        "B5_vtdo": b5,
    }

    capacities: list[TrainingArmCapacity] = []
    capacity_blockers: list[str] = []
    inherited_by_arm = {
        "B2_contribution_only": contribution_blockers,
        "B2_novelty_only": novelty_blockers,
        "B3_ccgr": b3_blockers,
        "B5_vtdo": b5_blockers,
    }
    for arm_id in VTDO_TRAINING_ARMS:
        inherited = inherited_by_arm.get(arm_id, ())
        capacity = _capacity(config, arm_id, arms[arm_id], inherited)
        capacities.append(capacity)
        capacity_blockers.extend(f"{arm_id}:{item}" for item in capacity.blockers)

    shared_blockers: list[str] = []
    if student.supervised_token_budget != config.target_supervised_tokens:
        shared_blockers.append(
            "student_token_budget_mismatch:"
            f"{student.supervised_token_budget}!={config.target_supervised_tokens}"
        )
    if "Qwen2.5-7B" not in student.base_model:
        shared_blockers.append("student_model_is_not_qwen2.5_7b")
    if student.seed not in config.seeds:
        shared_blockers.append("student_seed_not_in_experiment_seed_contract")
    benchmark_status, benchmark_blockers = _external_benchmark_status(config)
    shared_blockers.extend(benchmark_blockers)
    leakage = audit_external_benchmark_leakage(
        config.external_benchmarks if benchmark_status == "ready" else (),
        tasks,
    )
    leakage_status = (
        "failed" if config.external_benchmarks and benchmark_status != "ready" else leakage.status
    )
    if leakage_status == "failed":
        shared_blockers.append(f"external_benchmark_leakage:{leakage.collision_count}")
        shared_blockers.extend(leakage.blockers)
    if not tasks or not task_ids:
        shared_blockers.append("finance_task_state_artifacts_empty")
    capacity_by_arm = {item.arm_id: item for item in capacities}
    primary_blockers = [
        f"{arm_id}:{blocker}"
        for arm_id in _PRIMARY_CAUSAL_ARMS
        for blocker in capacity_by_arm[arm_id].blockers
    ]
    secondary_blockers = [
        f"{arm_id}:{blocker}"
        for arm_id in _SECONDARY_COMPARISON_ARMS
        for blocker in capacity_by_arm[arm_id].blockers
    ]
    primary_marginal_verified = all(
        capacity_by_arm[arm_id].task_marginal_verified for arm_id in _PRIMARY_CAUSAL_ARMS
    )
    shared_blocker_tuple = tuple(sorted(set(shared_blockers)))
    primary_blocker_tuple = tuple(sorted(set(primary_blockers)))
    secondary_blocker_tuple = tuple(sorted(set(secondary_blockers)))
    primary_ready = not shared_blocker_tuple and not primary_blocker_tuple
    full_matrix_ready = primary_ready and not secondary_blocker_tuple
    permitted_arm_ids = (
        tuple(item.arm_id for item in capacities if item.capacity_status == "ready")
        if not shared_blocker_tuple
        else ()
    )
    values = {
        "training_config_hash": student.config_hash,
        "base_model": student.base_model,
        "model_revision": student.model_revision,
        "supervised_token_budget": student.supervised_token_budget,
        "training_seeds": config.seeds,
        "arms": tuple(capacities),
        "primary_causal_arms": _PRIMARY_CAUSAL_ARMS,
        "secondary_comparison_arms": _SECONDARY_COMPARISON_ARMS,
        "primary_task_marginal_contract_verified": primary_marginal_verified,
        "primary_causal_training_ready": primary_ready,
        "full_comparison_matrix_ready": full_matrix_ready,
        "permitted_arm_ids": permitted_arm_ids,
        "external_benchmark_status": benchmark_status,
        "benchmark_leakage_status": leakage_status,
        "benchmark_leakage_count": leakage.collision_count,
        "benchmark_leakage_report_hash": leakage.report_id,
        "shared_training_blockers": shared_blocker_tuple,
        "primary_causal_blockers": primary_blocker_tuple,
        "secondary_comparison_blockers": secondary_blocker_tuple,
        "blockers": tuple(
            sorted(
                set(
                    capacity_blockers
                    + list(shared_blocker_tuple)
                    + list(primary_blocker_tuple)
                    + list(secondary_blocker_tuple)
                )
            )
        ),
        "schema_version": VTDO_EXPERIMENT_VERSION,
    }
    provisional = TrainingExperimentPreflight.model_construct(**values, report_hash="pending")
    report = TrainingExperimentPreflight(
        **values,
        report_hash=training_experiment_preflight_hash(provisional),
    )
    return report, arms, leakage


def write_training_arms(
    output_dir: Path,
    arms: Mapping[str, tuple[VTDOTrainingRecord, ...]],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for arm_id in VTDO_TRAINING_ARMS:
        records = arms.get(arm_id, ())
        path = output_dir / f"{arm_id}.jsonl"
        path.write_text(
            "".join(record.model_dump_json() + "\n" for record in records),
            encoding="utf-8",
        )
        paths[arm_id] = str(path)
        hashes[arm_id] = canonical_hash(records, prefix="vtdo_training_arm:")
    manifest_path = output_dir / "arm_dataset_hashes.json"
    manifest_path.write_text(
        json.dumps(hashes, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["arm_dataset_hashes"] = str(manifest_path)
    return paths


def build_refinement_checkpoint_training_arms(
    paths: tuple[Path, ...],
    artifacts: Iterable[FinanceTaskStateArtifact],
    checkpoint_rounds: tuple[int, ...],
) -> tuple[dict[int, tuple[VTDOTrainingRecord, ...]], tuple[str, ...]]:
    """Materialize one-based VTDO round checkpoints for one-shot/iterative training."""

    if not paths:
        return {}, ("vtdo_round_artifacts_not_configured",)
    rounds, load_blockers = load_vtdo_round_artifacts(paths)
    if load_blockers:
        return {}, load_blockers
    tasks = tuple(sorted(artifacts, key=lambda item: item.omega.task.task_id))
    if not tasks:
        return {}, ("finance_task_state_artifacts_empty",)
    by_condition_round: dict[tuple[str, int], VTDORoundArtifact] = {}
    blockers: list[str] = []
    for round_artifact in rounds:
        key = (round_artifact.task_condition_id, round_artifact.round_index)
        if key in by_condition_round:
            blockers.append(
                "duplicate_vtdo_round_artifact:"
                f"{round_artifact.task_condition_id}:{round_artifact.round_index}"
            )
        by_condition_round[key] = round_artifact
    maximum_round_index = max(checkpoint_rounds) - 1
    for artifact in tasks:
        condition_id = artifact.state_catalog.task_condition_id
        sequence: list[VTDORoundArtifact] = []
        for round_index in range(maximum_round_index + 1):
            selected_round = by_condition_round.get((condition_id, round_index))
            if selected_round is None:
                blockers.append(
                    f"vtdo_checkpoint_sequence_missing:{condition_id}:{round_index + 1}"
                )
                continue
            sequence.append(selected_round)
        for previous, current in zip(sequence, sequence[1:], strict=False):
            if (
                current.exploration.training_distribution.distribution_id
                != previous.update.next_distribution.distribution_id
            ):
                blockers.append(
                    f"vtdo_checkpoint_sequence_link_failure:{condition_id}:"
                    f"{previous.round_index + 1}->{current.round_index + 1}"
                )
    if blockers:
        return {}, tuple(sorted(set(blockers)))

    output: dict[int, tuple[VTDOTrainingRecord, ...]] = {}
    for checkpoint_round in checkpoint_rounds:
        records: list[VTDOTrainingRecord] = []
        round_index = checkpoint_round - 1
        for artifact in tasks:
            condition_id = artifact.state_catalog.task_condition_id
            round_artifact = by_condition_round[(condition_id, round_index)]
            probabilities = round_artifact.update.next_distribution.probabilities
            accepted = {item.assignment.state.state_id: item for item in artifact.accepted_states}
            if set(probabilities) != set(accepted):
                return {}, (
                    f"vtdo_checkpoint_state_support_mismatch:{condition_id}:{checkpoint_round}",
                )
            for state_id in sorted(probabilities):
                records.append(
                    _record_from_state(
                        artifact,
                        accepted[state_id],
                        "B5_vtdo",
                        sampling_weight=probabilities[state_id],
                        source_distribution_id=(
                            round_artifact.update.next_distribution.distribution_id
                        ),
                        extra_metadata={
                            "refinement_checkpoint_round": checkpoint_round,
                            "refinement_round_id": round_artifact.round_id,
                        },
                    )
                )
        output[checkpoint_round] = tuple(records)
    return output, ()


def write_refinement_checkpoint_training_arms(
    output_dir: Path,
    arms: Mapping[int, tuple[VTDOTrainingRecord, ...]],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for checkpoint_round, records in sorted(arms.items()):
        round_dir = output_dir / f"round_{checkpoint_round:02d}"
        round_dir.mkdir(parents=True, exist_ok=True)
        dataset_path = round_dir / "B5_vtdo.jsonl"
        dataset_path.write_text(
            "".join(record.model_dump_json() + "\n" for record in records),
            encoding="utf-8",
        )
        dataset_hash = canonical_hash(records, prefix="vtdo_training_arm:")
        manifest_path = round_dir / "arm_dataset_hashes.json"
        manifest_path.write_text(
            json.dumps({"B5_vtdo": dataset_hash}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        paths[f"round_{checkpoint_round}_dataset"] = str(dataset_path)
        paths[f"round_{checkpoint_round}_manifest"] = str(manifest_path)
    return paths


def load_training_records(path: Path) -> tuple[VTDOTrainingRecord, ...]:
    return tuple(
        VTDOTrainingRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def train_vtdo_arm(
    *,
    student_config_path: Path,
    preflight_path: Path,
    arm_manifest_path: Path,
    arm_id: VTDOTrainingArm,
    dataset_path: Path,
    output_dir: Path,
    training_seed: int,
) -> VTDOTrainingRunResult:
    """Train one isolated Qwen2.5-7B LoRA arm for an explicitly frozen seed."""

    student = VTDOStudentTrainingConfig.from_json(student_config_path)
    preflight = TrainingExperimentPreflight.model_validate_json(
        preflight_path.read_text(encoding="utf-8")
    )
    if student.config_hash != preflight.training_config_hash:
        raise ValueError("VTDO student config differs from the frozen preflight")
    if training_seed not in preflight.training_seeds:
        raise ValueError("training seed is outside the frozen experiment contract")
    if arm_id not in preflight.permitted_arm_ids:
        raise ValueError(f"VTDO arm is not permitted by the frozen preflight: {arm_id}")
    capacity = next((item for item in preflight.arms if item.arm_id == arm_id), None)
    if capacity is None or capacity.capacity_status != "ready":
        raise ValueError(f"VTDO arm is not formally ready: {arm_id}")
    records = load_training_records(dataset_path)
    if not records or {item.arm_id for item in records} != {arm_id}:
        raise ValueError(f"dataset does not contain only {arm_id}")
    manifest = json.loads(arm_manifest_path.read_text(encoding="utf-8"))
    dataset_hash = canonical_hash(records, prefix="vtdo_training_arm:")
    if manifest.get(arm_id) != dataset_hash:
        raise ValueError("VTDO arm dataset hash differs from the frozen manifest")
    training_input_sha256 = {
        "student_config": _sha256(student_config_path),
        "preflight": _sha256(preflight_path),
        "arm_manifest": _sha256(arm_manifest_path),
        "dataset": _sha256(dataset_path),
    }
    training_input_manifest_hash = canonical_hash(
        training_input_sha256,
        prefix="vtdo_training_input_manifest:",
    )
    effective_student = student.model_copy(update={"seed": training_seed})
    return _train(
        effective_student,
        arm_id,
        records,
        dataset_hash,
        output_dir,
        frozen_config_hash=student.config_hash,
        training_input_sha256=training_input_sha256,
        training_input_manifest_hash=training_input_manifest_hash,
    )


def _record_from_state(
    artifact: FinanceTaskStateArtifact,
    state,
    arm_id: VTDOTrainingArm,
    *,
    sampling_weight: float,
    source_distribution_id: str | None = None,
    extra_metadata: Mapping[str, Any] | None = None,
) -> VTDOTrainingRecord:
    return _make_record(
        artifact=artifact,
        trajectory=state.trajectory,
        state_id=state.assignment.state.state_id,
        arm_id=arm_id,
        accepted_target=True,
        sampling_weight=sampling_weight,
        source_distribution_id=source_distribution_id,
        metadata={"lineage_strategy": state.strategy, **dict(extra_metadata or {})},
    )


def _record_from_rejected(
    artifact: FinanceTaskStateArtifact,
    attempt,
    arm_id: VTDOTrainingArm,
    *,
    sampling_weight: float,
) -> VTDOTrainingRecord:
    return _make_record(
        artifact=artifact,
        trajectory=attempt.trajectory,
        state_id=None,
        arm_id=arm_id,
        accepted_target=False,
        sampling_weight=sampling_weight,
        source_distribution_id=None,
        metadata={"mutation_id": attempt.mutation_id},
    )


def _make_record(
    *,
    artifact: FinanceTaskStateArtifact,
    trajectory,
    state_id: str | None,
    arm_id: VTDOTrainingArm,
    accepted_target: bool,
    sampling_weight: float,
    source_distribution_id: str | None,
    metadata: dict[str, Any],
    source_artifact_id: str | None = None,
) -> VTDOTrainingRecord:
    user_payload = {
        "public_task": artifact.omega.task.public.model_dump(mode="json"),
        "public_evidence_corpus": artifact.omega.public_corpus.model_dump(mode="json"),
        "output_contract": "host_instrumented_decisions.v1",
    }
    values = {
        "arm_id": arm_id,
        "task_id": artifact.omega.task.task_id,
        "trajectory_state_id": state_id,
        "accepted_target": accepted_target,
        "system_prompt": _SYSTEM_PROMPT,
        "user_prompt": json.dumps(user_payload, ensure_ascii=False, sort_keys=True),
        "assistant_target": _host_instrumented_target(trajectory),
        "target_contract": "host_instrumented_decisions.v1",
        "sampling_weight": sampling_weight,
        "source_artifact_id": source_artifact_id or artifact.artifact_id,
        "source_distribution_id": source_distribution_id,
        "metadata": metadata,
        "schema_version": "vtdo_training_record.v2",
    }
    provisional = VTDOTrainingRecord.model_construct(record_id="pending", **values)
    return VTDOTrainingRecord(record_id=vtdo_training_record_id(provisional), **values)


def _random_state(artifact: FinanceTaskStateArtifact, *, seed: int):
    digest = canonical_hash(
        {"seed": seed, "task_id": artifact.omega.task.task_id},
        prefix="vtdo_random_state_arm:",
    )
    index = int(digest.rsplit(":", 1)[-1][:16], 16) % len(artifact.accepted_states)
    return artifact.accepted_states[index]


def _ccgr_arm(
    path: Path | None,
    artifacts: tuple[FinanceTaskStateArtifact, ...],
) -> tuple[tuple[VTDOTrainingRecord, ...], tuple[str, ...]]:
    if path is None:
        return (), ("ccgr_task_distribution_not_configured",)
    if not path.is_file():
        return (), (f"ccgr_task_distribution_missing:{path}",)
    distribution = CCGRTaskDistribution.model_validate_json(path.read_text(encoding="utf-8"))
    task_ids = {item.omega.task.task_id for item in artifacts}
    if set(distribution.task_probabilities) != task_ids:
        return (), ("ccgr_task_distribution_support_mismatch",)
    records = tuple(
        _record_from_state(
            artifact,
            artifact.accepted_states[0],
            "B3_ccgr",
            sampling_weight=distribution.task_probabilities[artifact.omega.task.task_id],
            source_distribution_id=distribution.distribution_id,
        )
        for artifact in artifacts
    )
    return records, ()


def _vtdo_arm(
    paths: tuple[Path, ...],
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    *,
    selected_round: int,
) -> tuple[tuple[VTDOTrainingRecord, ...], tuple[str, ...]]:
    selected, blockers = _selected_vtdo_rounds(paths, artifacts, selected_round)
    if blockers:
        return (), blockers
    records: list[VTDOTrainingRecord] = []
    for artifact, round_artifact in selected:
        condition_id = artifact.state_catalog.task_condition_id
        probabilities = round_artifact.update.next_distribution.probabilities
        accepted = {item.assignment.state.state_id: item for item in artifact.accepted_states}
        if set(probabilities) != set(accepted):
            return (), (f"vtdo_round_state_support_mismatch:{condition_id}",)
        for state_id in sorted(probabilities):
            records.append(
                _record_from_state(
                    artifact,
                    accepted[state_id],
                    "B5_vtdo",
                    sampling_weight=probabilities[state_id],
                    source_distribution_id=round_artifact.update.next_distribution.distribution_id,
                    extra_metadata={
                        "selected_training_round": selected_round,
                        "refinement_round_id": round_artifact.round_id,
                    },
                )
            )
    return tuple(records), ()


def _component_arm(
    paths: tuple[Path, ...],
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    *,
    selected_round: int,
    arm_id: Literal["B2_contribution_only", "B2_novelty_only"],
    component: Literal["contribution", "novelty"],
) -> tuple[tuple[VTDOTrainingRecord, ...], tuple[str, ...]]:
    selected, blockers = _selected_vtdo_rounds(paths, artifacts, selected_round)
    if blockers:
        return (), blockers
    records: list[VTDOTrainingRecord] = []
    for artifact, round_artifact in selected:
        update = round_artifact.update
        potentials = {item.state_id: item for item in update.state_potentials}
        accepted = {item.assignment.state.state_id: item for item in artifact.accepted_states}
        if set(potentials) != set(accepted):
            return (), (
                f"vtdo_component_state_support_mismatch:"
                f"{artifact.state_catalog.task_condition_id}:{component}",
            )
        log_weights = {
            state_id: (
                update.history_exponent * math.log(potential.current_probability)
                + (1.0 - update.history_exponent) * math.log(potential.coverage_probability)
                + update.energy_exponent
                * math.log(
                    potential.normalized_contribution
                    if component == "contribution"
                    else potential.normalized_novelty
                )
            )
            for state_id, potential in potentials.items()
        }
        maximum = max(log_weights.values())
        raw_weights = {
            state_id: math.exp(value - maximum) for state_id, value in log_weights.items()
        }
        total = sum(raw_weights.values())
        probabilities = {
            state_id: raw_weights[state_id] / total for state_id in sorted(raw_weights)
        }
        distribution_id = canonical_hash(
            {
                "round_id": round_artifact.round_id,
                "component": component,
                "probabilities": probabilities,
            },
            prefix="vtdo_component_training_distribution:",
        )
        for state_id, probability in probabilities.items():
            records.append(
                _record_from_state(
                    artifact,
                    accepted[state_id],
                    arm_id,
                    sampling_weight=probability,
                    source_distribution_id=distribution_id,
                    extra_metadata={
                        "selected_training_round": selected_round,
                        "refinement_round_id": round_artifact.round_id,
                        "isolated_potential_component": component,
                    },
                )
            )
    return tuple(records), ()


def _selected_vtdo_rounds(
    paths: tuple[Path, ...],
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    selected_round: int,
) -> tuple[
    tuple[tuple[FinanceTaskStateArtifact, VTDORoundArtifact], ...],
    tuple[str, ...],
]:
    if not paths:
        return (), ("vtdo_round_artifacts_not_configured",)
    rounds, blockers = load_vtdo_round_artifacts(paths)
    if blockers:
        return (), blockers
    by_condition_round: dict[tuple[str, int], VTDORoundArtifact] = {}
    for item in rounds:
        key = (item.task_condition_id, item.round_index)
        if key in by_condition_round:
            return (), (
                f"duplicate_vtdo_round_artifact:{item.task_condition_id}:{item.round_index}",
            )
        by_condition_round[key] = item
    selected: list[tuple[FinanceTaskStateArtifact, VTDORoundArtifact]] = []
    target_round_index = selected_round - 1
    for artifact in artifacts:
        condition_id = artifact.state_catalog.task_condition_id
        sequence = tuple(
            by_condition_round.get((condition_id, round_index))
            for round_index in range(target_round_index + 1)
        )
        if any(item is None for item in sequence):
            return (), (f"vtdo_round_sequence_missing:{condition_id}:{selected_round}",)
        typed_sequence = tuple(item for item in sequence if item is not None)
        if any(
            current.exploration.training_distribution.distribution_id
            != previous.update.next_distribution.distribution_id
            for previous, current in zip(typed_sequence, typed_sequence[1:], strict=False)
        ):
            return (), (f"vtdo_round_sequence_link_failure:{condition_id}",)
        if not typed_sequence:
            return (), (f"vtdo_round_missing_task_condition:{condition_id}",)
        selected.append((artifact, typed_sequence[-1]))
    return tuple(selected), ()


def _capacity(
    config: TrainingExperimentConfig,
    arm_id: VTDOTrainingArm,
    records: tuple[VTDOTrainingRecord, ...],
    inherited_blockers: tuple[str, ...],
) -> TrainingArmCapacity:
    task_ids = {item.task_id for item in records}
    state_ids = {
        item.trajectory_state_id for item in records if item.trajectory_state_id is not None
    }
    used_states_by_task = {
        task_id: {
            item.trajectory_state_id
            for item in records
            if item.task_id == task_id and item.trajectory_state_id is not None
        }
        for task_id in task_ids
    }
    state_counts = [len(used_states_by_task[task_id]) for task_id in task_ids]
    task_weights = {
        task_id: sum(item.sampling_weight for item in records if item.task_id == task_id)
        for task_id in task_ids
    }
    marginal_policy = "ccgr_nonuniform" if arm_id == "B3_ccgr" else "uniform_fixed"
    if marginal_policy == "uniform_fixed":
        maximum_deviation = max(
            (abs(value - 1.0) for value in task_weights.values()),
            default=0.0,
        )
        marginal_verified = bool(task_weights) and maximum_deviation <= 1e-12
    else:
        maximum_deviation = 0.0
        marginal_verified = bool(task_weights) and math.isclose(
            sum(task_weights.values()),
            1.0,
            abs_tol=1e-12,
        )
    blockers = list(inherited_blockers)
    if not records:
        blockers.append("no_materializable_records")
    if not marginal_verified:
        blockers.append("task_marginal_contract_failed")
    if len(task_ids) < config.minimum_unique_tasks_per_arm:
        blockers.append(
            f"unique_tasks_below_formal_minimum:{len(task_ids)}<"
            f"{config.minimum_unique_tasks_per_arm}"
        )
    if len(state_ids) < config.minimum_unique_states_per_arm:
        blockers.append(
            f"unique_states_below_formal_minimum:{len(state_ids)}<"
            f"{config.minimum_unique_states_per_arm}"
        )
    hard_blocked = bool(inherited_blockers) or not records or not marginal_verified
    status = (
        "blocked"
        if hard_blocked
        else "pilot_only"
        if any("below_formal_minimum" in item for item in blockers)
        else "ready"
    )
    return TrainingArmCapacity(
        arm_id=arm_id,
        source_record_count=len(records),
        unique_task_count=len(task_ids),
        unique_state_count=len(state_ids),
        multi_state_task_count=sum(value >= 2 for value in state_counts),
        maximum_states_per_task=max(state_counts, default=0),
        accepted_only=arm_id != "B1_raw",
        comparison_role=(
            "controlled_quality_lower_bound"
            if arm_id == "B1_raw"
            else "secondary_task_marginal_baseline"
            if arm_id == "B3_ccgr"
            else "primary_fixed_task_marginal"
        ),
        task_marginal_policy=marginal_policy,
        minimum_task_weight=min(task_weights.values(), default=0.0),
        maximum_task_weight=max(task_weights.values(), default=0.0),
        maximum_task_weight_deviation=maximum_deviation,
        task_marginal_verified=marginal_verified,
        requested_supervised_tokens=config.target_supervised_tokens,
        capacity_status=status,
        blockers=tuple(sorted(set(blockers))),
    )


def _external_benchmark_status(
    config: TrainingExperimentConfig,
) -> tuple[str, tuple[str, ...]]:
    required = {"finqa", "tat_qa"}
    observed = {item.benchmark_id for item in config.external_benchmarks}
    if not observed:
        return "not_configured", ("external_benchmarks:not_configured",)
    blockers: list[str] = []
    if not required.issubset(observed):
        blockers.append(
            "required_external_benchmark_missing:"
            f"observed={sorted(observed)},required={sorted(required)}"
        )
    for snapshot in config.external_benchmarks:
        if not snapshot.path.is_file():
            blockers.append(f"external_benchmark_missing:{snapshot.benchmark_id}")
        elif _sha256(snapshot.path) != snapshot.sha256:
            blockers.append(f"external_benchmark_hash_mismatch:{snapshot.benchmark_id}")
    return ("not_available", tuple(blockers)) if blockers else ("ready", ())


def _train(
    config: VTDOStudentTrainingConfig,
    arm_id: VTDOTrainingArm,
    records: tuple[VTDOTrainingRecord, ...],
    dataset_hash: str,
    output_dir: Path,
    *,
    frozen_config_hash: str,
    training_input_sha256: dict[str, str],
    training_input_manifest_hash: str,
) -> VTDOTrainingRunResult:
    try:
        import torch
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
            set_seed,
        )
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("training dependencies are missing") from exc
    if not torch.cuda.is_available():
        raise RuntimeError("VTDO Qwen2.5-7B training requires CUDA")
    _validate_model_loading(config.base_model, config.model_revision)
    base_model_path = Path(config.base_model).expanduser()
    base_model_manifest_hash = (
        _directory_manifest_hash(base_model_path, prefix="base_model_manifest:")
        if base_model_path.is_dir()
        else canonical_hash(
            {"repository": config.base_model, "revision": config.model_revision},
            prefix="remote_base_model_manifest:",
        )
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    set_seed(config.seed)
    tokenizer = AutoTokenizer.from_pretrained(
        config.base_model,
        revision=config.model_revision,
        use_fast=True,
        trust_remote_code=False,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    encoded = tuple(_encode_record(tokenizer, record, config.max_seq_length) for record in records)
    scheduled, supervised_tokens, schedule_audit = _schedule_records(
        records,
        encoded,
        token_budget=config.supervised_token_budget,
        seed=config.seed,
    )
    deviation = (
        abs(supervised_tokens - config.supervised_token_budget) / config.supervised_token_budget
    )
    if deviation > config.maximum_token_budget_deviation_rate:
        raise ValueError("unable to satisfy the frozen supervised-token budget")
    examples_per_step = config.per_device_train_batch_size * config.gradient_accumulation_steps
    steps = math.ceil(len(scheduled) / examples_per_step)
    if steps > config.max_steps:
        raise ValueError(
            f"token schedule requires {steps} steps, above max_steps={config.max_steps}"
        )
    model = AutoModelForCausalLM.from_pretrained(
        config.base_model,
        revision=config.model_revision,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
        trust_remote_code=False,
        use_safetensors=True,
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(
        model,
        LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=config.lora_rank,
            lora_alpha=config.lora_alpha,
            lora_dropout=config.lora_dropout,
            target_modules=list(config.lora_target_modules),
            bias="none",
        ),
    )
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(output_dir / "trainer_state"),
            max_steps=steps,
            per_device_train_batch_size=config.per_device_train_batch_size,
            gradient_accumulation_steps=config.gradient_accumulation_steps,
            learning_rate=config.learning_rate,
            warmup_steps=math.ceil(steps * config.warmup_ratio),
            weight_decay=config.weight_decay,
            bf16=True,
            fp16=False,
            gradient_checkpointing=True,
            logging_steps=1,
            save_strategy="steps",
            save_steps=max(1, steps // 3),
            save_total_limit=2,
            report_to=[],
            remove_unused_columns=False,
            optim="adamw_torch_fused",
            seed=config.seed,
            data_seed=config.seed,
        ),
        train_dataset=list(scheduled),
        data_collator=_collator(tokenizer.pad_token_id),
    )
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    output = trainer.train()
    runtime = time.monotonic() - started
    adapter_dir = output_dir / "adapter"
    trainer.save_model(str(adapter_dir))
    tokenizer.save_pretrained(adapter_dir)
    adapter_manifest_hash = _directory_manifest_hash(
        adapter_dir,
        prefix="adapter_manifest:",
    )
    values = {
        "arm_id": arm_id,
        "config_hash": frozen_config_hash,
        "dataset_hash": dataset_hash,
        "training_input_sha256": training_input_sha256,
        "training_input_manifest_hash": training_input_manifest_hash,
        "base_model": (
            str(base_model_path.resolve()) if base_model_path.is_dir() else config.base_model
        ),
        "base_model_manifest_hash": base_model_manifest_hash,
        "adapter_manifest_hash": adapter_manifest_hash,
        "model_revision": config.model_revision,
        "training_seed": config.seed,
        "adapter_dir": str(adapter_dir.resolve()),
        "completed_steps": int(output.global_step),
        "final_train_loss": float(output.training_loss),
        "supervised_token_count": supervised_tokens,
        "supervised_token_budget": config.supervised_token_budget,
        "prompt_token_count": schedule_audit["prompt_token_count"],
        "processed_token_count": schedule_audit["processed_token_count"],
        "scheduled_example_count": schedule_audit["scheduled_example_count"],
        "unique_scheduled_record_count": schedule_audit["unique_scheduled_record_count"],
        "repeated_example_rate": schedule_audit["repeated_example_rate"],
        "budget_contract": config.budget_contract,
        "token_budget_deviation_rate": deviation,
        "train_runtime_seconds": runtime,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
        "dependency_versions": _dependency_versions(),
        "status": "completed",
        "schema_version": "vtdo_training_run.v4",
    }
    provisional = VTDOTrainingRunResult.model_construct(result_id="pending", **values)
    result = VTDOTrainingRunResult(
        result_id=vtdo_training_run_result_id(provisional),
        **values,
    )
    (output_dir / "training_result.json").write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def _encode_record(tokenizer: Any, record: VTDOTrainingRecord, maximum: int) -> dict[str, Any]:
    prompt = [
        {"role": "system", "content": record.system_prompt},
        {"role": "user", "content": record.user_prompt},
    ]
    complete = [*prompt, {"role": "assistant", "content": record.assistant_target}]
    prompt_ids = tokenizer(
        tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True),
        add_special_tokens=False,
    )["input_ids"]
    input_ids = tokenizer(
        tokenizer.apply_chat_template(complete, tokenize=False, add_generation_prompt=False),
        add_special_tokens=False,
    )["input_ids"]
    if input_ids[: len(prompt_ids)] != prompt_ids:
        raise ValueError("chat template does not preserve the generation prefix")
    if len(input_ids) > maximum:
        raise ValueError(f"record {record.record_id} exceeds max_seq_length={maximum}")
    labels = [-100] * len(prompt_ids) + input_ids[len(prompt_ids) :]
    return {
        "record_id": record.record_id,
        "input_ids": input_ids,
        "attention_mask": [1] * len(input_ids),
        "labels": labels,
        "supervised_tokens": sum(item != -100 for item in labels),
        "prompt_tokens": len(prompt_ids),
        "processed_tokens": len(input_ids),
    }


def _schedule_records(
    records: tuple[VTDOTrainingRecord, ...],
    encoded: tuple[dict[str, Any], ...],
    *,
    token_budget: int,
    seed: int,
) -> tuple[tuple[dict[str, Any], ...], int, dict[str, Any]]:
    rng = random.Random(seed)
    weights = [item.sampling_weight for item in records]
    scheduled: list[dict[str, Any]] = []
    scheduled_record_ids: list[str] = []
    prompt_tokens = 0
    processed_tokens = 0
    total = 0
    lower = token_budget * 0.999
    upper = token_budget * 1.001
    while total < lower:
        index = rng.choices(range(len(records)), weights=weights, k=1)[0]
        candidate = encoded[index]
        next_total = total + int(candidate["supervised_tokens"])
        if next_total > upper:
            alternatives = sorted(
                encoded,
                key=lambda item: abs(token_budget - (total + int(item["supervised_tokens"]))),
            )
            candidate = alternatives[0]
            next_total = total + int(candidate["supervised_tokens"])
            if abs(token_budget - next_total) > abs(token_budget - total):
                break
        scheduled.append({key: value for key, value in candidate.items() if key != "record_id"})
        scheduled_record_ids.append(str(candidate["record_id"]))
        prompt_tokens += int(candidate["prompt_tokens"])
        processed_tokens += int(candidate["processed_tokens"])
        total = next_total
    unique_count = len(set(scheduled_record_ids))
    audit = {
        "prompt_token_count": prompt_tokens,
        "processed_token_count": processed_tokens,
        "scheduled_example_count": len(scheduled),
        "unique_scheduled_record_count": unique_count,
        "repeated_example_rate": (1.0 - unique_count / len(scheduled) if scheduled else 0.0),
    }
    return tuple(scheduled), total, audit


def _host_instrumented_target(trajectory: Any) -> str:
    decisions = []
    for step in trajectory.steps:
        decisions.append(
            {
                "step_index": step.step_index,
                "action": step.action.value,
                "tool_name": step.tool_name,
                "tool_input": step.tool_input,
                "evidence_ids": list(step.evidence_ids),
                "program_node_id": step.program_node_id,
                "operator_id": step.operator_id,
                "input_refs": list(step.input_refs),
                "output_ref": step.output_ref,
            }
        )
    return json.dumps(
        {
            "contract": "host_instrumented_decisions.v1",
            "model_decisions": decisions,
            "final_answer": trajectory.final_answer,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _collator(pad_token_id: int):
    def collate(features: list[dict[str, Any]]):
        import torch

        maximum = max(len(item["input_ids"]) for item in features)
        return {
            "input_ids": torch.tensor(
                [
                    item["input_ids"] + [pad_token_id] * (maximum - len(item["input_ids"]))
                    for item in features
                ]
            ),
            "attention_mask": torch.tensor(
                [
                    item["attention_mask"] + [0] * (maximum - len(item["input_ids"]))
                    for item in features
                ]
            ),
            "labels": torch.tensor(
                [item["labels"] + [-100] * (maximum - len(item["input_ids"])) for item in features]
            ),
        }

    return collate


def _validate_model_loading(base_model: str, revision: str | None) -> None:
    path = Path(base_model).expanduser()
    if path.exists():
        if not path.is_dir():
            raise ValueError("local base_model must be a directory")
        return
    if revision is None or _IMMUTABLE_REVISION.fullmatch(revision) is None:
        raise ValueError("remote model loading requires an immutable commit revision")


def _dependency_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for package in ("torch", "transformers", "peft", "accelerate"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "missing"
    return result


def _directory_manifest_hash(path: Path, *, prefix: str) -> str:
    files = tuple(sorted(item for item in path.rglob("*") if item.is_file()))
    if not files:
        raise ValueError(f"model directory has no files: {path}")
    identity = {
        str(item.relative_to(path)): {
            "size": item.stat().st_size,
            "sha256": _sha256(item),
        }
        for item in files
    }
    return canonical_hash(identity, prefix=prefix)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
