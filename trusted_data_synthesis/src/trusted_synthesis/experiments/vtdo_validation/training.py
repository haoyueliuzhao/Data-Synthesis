from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.vtdo.materialization import (
    TrajectoryStateMaterializationReport,
)
from trusted_synthesis.experiments.training_utility_mvp import (
    CohortTrainingResult,
    SFTRecord,
    load_agent_artifacts,
    load_sft_records,
    make_sft_record,
    record_from_quality_example,
    train_sft_cohort,
    trajectory_to_response,
)
from trusted_synthesis.experiments.training_utility_v09 import V09RefinementManifest
from trusted_synthesis.hashing import canonical_hash

from .schema import (
    VTDO_TRAINING_ARMS,
    VTDO_VALIDATION_EXPERIMENT_VERSION,
    TrainingArmCapacity,
    TrainingExperimentConfig,
    TrainingExperimentPreflight,
    VTDOStudentTrainingConfig,
    VTDOTrainingArm,
    training_experiment_preflight_hash,
)

_ARMS = VTDO_TRAINING_ARMS


def build_training_experiment_preflight(
    config: TrainingExperimentConfig,
    *,
    agent_artifact_dir: Path,
    real_state_rows: Iterable[Mapping[str, object]],
) -> tuple[TrainingExperimentPreflight, dict[str, tuple[SFTRecord, ...]]]:
    """Compile B1-B5 where evidence exists and fail closed on missing state support."""

    student_config = VTDOStudentTrainingConfig.from_json(config.training_config_path)
    report, critic_dataset = load_agent_artifacts(agent_artifact_dir)
    real_examples = {
        item.task_id: item
        for item in sorted(critic_dataset.examples, key=lambda value: value.example_id)
        if item.candidate_source == "real_agent" and item.domain == "finance"
    }
    samples = {
        item.task_id: item
        for item in report.samples
        if item.domain == "finance" and item.trajectory is not None
    }
    states_by_task: defaultdict[str, set[str]] = defaultdict(set)
    for row in real_state_rows:
        if row.get("variant_kind") != "original":
            continue
        task_id = str(row["task_id"])
        states_by_task[task_id].add(str(row["state_id"]))

    representable: dict[str, SFTRecord] = {}
    representation_failures: Counter[str] = Counter()
    for task_id, example in sorted(real_examples.items()):
        try:
            representable[task_id] = record_from_quality_example(
                example,
                "B1_raw",
                metadata={
                    "vtdo_arm": "B1_raw",
                    "trajectory_state_ids": sorted(states_by_task.get(task_id, ())),
                },
            )
        except (TypeError, ValueError, KeyError) as exc:
            representation_failures[type(exc).__name__] += 1

    accepted_task_ids = {
        task_id
        for task_id, sample in samples.items()
        if sample.contract_assessment is not None
        and sample.contract_assessment.decision == ReleaseDecision.ACCEPTED
    }
    accepted_records = {
        task_id: record for task_id, record in representable.items() if task_id in accepted_task_ids
    }
    arms: dict[str, tuple[SFTRecord, ...]] = {
        "B1_raw": tuple(representable.values()),
        "B2_validity": _copy_records(accepted_records, "B2_validity"),
    }

    ccgr_records, ccgr_blockers = _ccgr_records(
        config.ccgr_manifest_path,
        accepted_records,
        samples,
    )
    arms["B3_ccgr"] = ccgr_records
    arms["B4_random_state"] = _copy_records(accepted_records, "B4_random_state")
    vtdo_records, materialized_states, vtdo_blockers = _vtdo_records(
        config.vtdo_materialization_path
    )
    arms["B5_vtdo"] = vtdo_records

    capacities = []
    global_blockers = [
        f"record_compilation_{key}:{count}"
        for key, count in sorted(representation_failures.items())
    ]
    if student_config.supervised_token_budget != config.target_supervised_tokens:
        global_blockers.append(
            "student_token_budget_mismatch:"
            f"{student_config.supervised_token_budget}!={config.target_supervised_tokens}"
        )
    if "Qwen2.5-7B" not in student_config.base_model:
        global_blockers.append("student_model_is_not_qwen2.5_7b")
    if student_config.seed not in config.seeds:
        global_blockers.append("student_seed_not_in_experiment_seed_contract")
    for arm_id in _ARMS:
        records = arms[arm_id]
        if arm_id == "B5_vtdo":
            state_map = materialized_states
            arm_blockers = list(vtdo_blockers)
        else:
            state_map = {
                record.task_id: set(states_by_task.get(record.task_id, ())) for record in records
            }
            arm_blockers = list(ccgr_blockers if arm_id == "B3_ccgr" else ())
        capacity = _capacity(config, arm_id, records, state_map, arm_blockers)
        capacities.append(capacity)
        global_blockers.extend(f"{arm_id}:{item}" for item in capacity.blockers)

    external_status = _external_benchmark_status(config.external_benchmark_paths)
    if external_status != "ready":
        global_blockers.append(f"external_benchmarks:{external_status}")
    configuration_blocked = any(
        item.startswith(("student_token_budget_", "student_model_", "student_seed_"))
        for item in global_blockers
    )
    formal_ready = (
        all(item.capacity_status == "ready" for item in capacities)
        and not configuration_blocked
        and external_status == "ready"
    )
    pilot_ready = (
        all(item.capacity_status != "blocked" for item in capacities) and not configuration_blocked
    )
    values = {
        "training_config_hash": student_config.config_hash,
        "base_model": student_config.base_model,
        "model_revision": student_config.model_revision,
        "supervised_token_budget": student_config.supervised_token_budget,
        "training_seed": student_config.seed,
        "arms": tuple(capacities),
        "formal_training_ready": formal_ready,
        "pilot_training_ready": pilot_ready,
        "external_benchmark_status": external_status,
        "blockers": tuple(sorted(set(global_blockers))),
        "schema_version": VTDO_VALIDATION_EXPERIMENT_VERSION,
    }
    provisional = TrainingExperimentPreflight.model_construct(
        **values,
        report_hash="pending",
    )
    return (
        TrainingExperimentPreflight(
            **values,
            report_hash=training_experiment_preflight_hash(provisional),
        ),
        arms,
    )


def train_vtdo_arm(
    *,
    student_config_path: Path,
    preflight_path: Path,
    arm_manifest_path: Path,
    arm_id: VTDOTrainingArm,
    dataset_path: Path,
    output_dir: Path,
) -> CohortTrainingResult:
    """Train one arm only after the complete frozen experiment is formally ready."""

    student_config = VTDOStudentTrainingConfig.from_json(student_config_path)
    preflight = TrainingExperimentPreflight.model_validate_json(
        preflight_path.read_text(encoding="utf-8")
    )
    expected_preflight_hash = training_experiment_preflight_hash(preflight)
    if preflight.report_hash != expected_preflight_hash:
        raise ValueError("VTDO training preflight identity is invalid")
    if student_config.config_hash != preflight.training_config_hash:
        raise ValueError("VTDO student config differs from the frozen preflight")
    if not preflight.formal_training_ready:
        raise ValueError("VTDO formal training preflight is not ready")
    capacity = next((item for item in preflight.arms if item.arm_id == arm_id), None)
    if capacity is None or capacity.capacity_status != "ready":
        raise ValueError(f"VTDO arm is not formally ready: {arm_id}")

    records = load_sft_records(dataset_path)
    if not records:
        raise ValueError("VTDO arm dataset is empty")
    if any(record.cohort != arm_id for record in records):
        raise ValueError("VTDO arm dataset contains records from another arm")
    if len({record.record_id for record in records}) != len(records):
        raise ValueError("VTDO arm dataset contains duplicate record identities")
    if len(records) != capacity.source_record_count:
        raise ValueError("VTDO arm record count differs from the frozen preflight")
    observed_tasks = {record.task_id for record in records}
    if len(observed_tasks) != capacity.unique_task_count:
        raise ValueError("VTDO arm task count differs from the frozen preflight")

    manifest = json.loads(arm_manifest_path.read_text(encoding="utf-8"))
    expected_dataset_hash = manifest.get(arm_id)
    observed_dataset_hash = canonical_hash(records, prefix="vtdo_training_arm:")
    if expected_dataset_hash != observed_dataset_hash:
        raise ValueError("VTDO arm dataset hash differs from the frozen manifest")
    return train_sft_cohort(student_config, arm_id, dataset_path, output_dir)


def _copy_records(records: Mapping[str, SFTRecord], arm_id: str) -> tuple[SFTRecord, ...]:
    return tuple(
        record.model_copy(
            update={
                "cohort": arm_id,
                "record_id": canonical_hash(
                    {"source_record_id": record.record_id, "arm_id": arm_id},
                    prefix="vtdo_training_record:",
                ),
                "metadata": {**record.metadata, "vtdo_arm": arm_id},
                "sampling_weight": 1.0,
            }
        )
        for _, record in sorted(records.items())
    )


def _ccgr_records(
    path: Path | None,
    accepted_records: Mapping[str, SFTRecord],
    samples,
) -> tuple[tuple[SFTRecord, ...], tuple[str, ...]]:
    if path is None:
        return (), ("ccgr_manifest_not_configured",)
    if not path.is_file():
        return (), ("ccgr_manifest_missing",)
    manifest = V09RefinementManifest.model_validate_json(path.read_text(encoding="utf-8"))
    update = next(item for item in manifest.ccgr_updates if item.ablation_id == "full_ccgr")
    probabilities = update.next_policy.probabilities
    task_cells = {
        task_id: sample.synthesis_cell.cell_id
        for task_id, sample in samples.items()
        if sample.synthesis_cell is not None and task_id in accepted_records
    }
    cell_counts = Counter(task_cells.values())
    missing = sorted(
        task_id for task_id in accepted_records if task_cells.get(task_id) not in probabilities
    )
    records = []
    for task_id, source in sorted(accepted_records.items()):
        cell_id = task_cells.get(task_id)
        if cell_id not in probabilities:
            continue
        weight = probabilities[cell_id] / cell_counts[cell_id]
        records.append(
            source.model_copy(
                update={
                    "cohort": "B3_ccgr",
                    "record_id": canonical_hash(
                        {
                            "source_record_id": source.record_id,
                            "arm_id": "B3_ccgr",
                            "policy_update_id": update.update_id,
                        },
                        prefix="vtdo_training_record:",
                    ),
                    "metadata": {
                        **source.metadata,
                        "vtdo_arm": "B3_ccgr",
                        "ccgr_update_id": update.update_id,
                        "synthesis_cell_id": cell_id,
                    },
                    "sampling_weight": weight,
                }
            )
        )
    blockers = (f"ccgr_policy_missing_task_cells:{len(missing)}",) if missing else ()
    return tuple(records), blockers


def _vtdo_records(
    path: Path | None,
) -> tuple[tuple[SFTRecord, ...], dict[str, set[str]], tuple[str, ...]]:
    if path is None:
        return (), {}, ("state_conditioned_materialization_not_configured",)
    if not path.is_file():
        return (), {}, ("state_conditioned_materialization_missing",)
    reports = tuple(
        TrajectoryStateMaterializationReport.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not reports:
        return (), {}, ("state_conditioned_materialization_empty",)
    records = []
    states_by_task: defaultdict[str, set[str]] = defaultdict(set)
    blocked_report_count = 0
    for report in reports:
        blocked_report_count += int(report.status != "passed")
        for artifact in report.artifacts:
            task = artifact.context.task.public.model_dump(mode="json")
            evidence = [
                item.model_dump(mode="json") for item in artifact.context.public_corpus.evidence
            ]
            state_id = artifact.target_state.state_id
            task_id = artifact.context.task.task_id
            states_by_task[task_id].add(state_id)
            records.append(
                make_sft_record(
                    cohort="B5_vtdo",
                    task=task,
                    evidence=evidence,
                    target=trajectory_to_response(artifact.trajectory),
                    source_kind="vtdo_state_materialization",
                    contract_label="accept",
                    metadata={
                        "vtdo_arm": "B5_vtdo",
                        "trajectory_state_id": state_id,
                        "source_distribution_id": artifact.source_distribution_id,
                        "materialization_report_id": report.report_id,
                    },
                )
            )
    blockers = (
        (f"blocked_materialization_reports:{blocked_report_count}",) if blocked_report_count else ()
    )
    return tuple(records), dict(states_by_task), blockers


def _capacity(
    config: TrainingExperimentConfig,
    arm_id: str,
    records: tuple[SFTRecord, ...],
    states_by_task: Mapping[str, set[str]],
    inherited_blockers: list[str],
) -> TrainingArmCapacity:
    task_ids = {item.task_id for item in records}
    state_ids = {state_id for values in states_by_task.values() for state_id in values}
    state_counts = [len(states_by_task.get(task_id, ())) for task_id in task_ids]
    multi_state_tasks = sum(value >= 2 for value in state_counts)
    maximum_states = max(state_counts, default=0)
    blockers = list(inherited_blockers)
    if not records:
        blockers.append("no_materializable_records")
    if arm_id == "B5_vtdo" and multi_state_tasks == 0:
        blockers.append("no_task_condition_has_multiple_real_accepted_states")
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
    hard_blocked = not records or (arm_id == "B5_vtdo" and multi_state_tasks == 0)
    if inherited_blockers:
        hard_blocked = True
    if hard_blocked:
        status = "blocked"
    elif any("below_formal_minimum" in item for item in blockers):
        status = "pilot_only"
    else:
        status = "ready"
    return TrainingArmCapacity(
        arm_id=arm_id,
        source_record_count=len(records),
        unique_task_count=len(task_ids),
        unique_state_count=len(state_ids),
        multi_state_task_count=multi_state_tasks,
        maximum_states_per_task=maximum_states,
        accepted_only=arm_id != "B1_raw",
        requested_supervised_tokens=config.target_supervised_tokens,
        capacity_status=status,
        blockers=tuple(blockers),
    )


def _external_benchmark_status(paths: tuple[Path, ...]) -> str:
    if not paths:
        return "not_configured"
    if all(path.is_file() for path in paths):
        return "ready"
    return "not_available"


def write_training_arms(
    output_dir: Path,
    arms: Mapping[str, tuple[SFTRecord, ...]],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for arm_id, records in sorted(arms.items()):
        path = output_dir / f"{arm_id}.jsonl"
        with path.open("w", encoding="utf-8") as output:
            for record in records:
                output.write(record.model_dump_json() + "\n")
        paths[arm_id] = str(path)
    manifest_path = output_dir / "arm_dataset_hashes.json"
    manifest_path.write_text(
        json.dumps(
            {
                arm_id: canonical_hash(records, prefix="vtdo_training_arm:")
                for arm_id, records in sorted(arms.items())
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["arm_dataset_hashes"] = str(manifest_path)
    return paths
