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
from typing import Any

from trusted_synthesis.core.vtdo.round import VTDORoundArtifact
from trusted_synthesis.hashing import canonical_hash

from .multistate import FinanceTaskStateArtifact
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
    "You are a proof-carrying evidence agent. Use only the supplied public task and public "
    "evidence corpus. Return one Candidate Trajectory JSON object that selects evidence, "
    "executes the permitted typed operations, verifies the result when required, and cites "
    "every evidence item used. Do not reveal or infer hidden Oracle fields."
)
_IMMUTABLE_REVISION = re.compile(r"[0-9a-fA-F]{40,64}")


def build_training_experiment_preflight(
    config: TrainingExperimentConfig,
    *,
    artifacts: Iterable[FinanceTaskStateArtifact],
    vtdo_round_artifact_paths: tuple[Path, ...],
) -> tuple[TrainingExperimentPreflight, dict[str, tuple[VTDOTrainingRecord, ...]]]:
    """Build the paper's B1-B5 arms without consulting v0.8/v0.9 artifacts."""

    student = VTDOStudentTrainingConfig.from_json(config.training_config_path)
    tasks = tuple(sorted(artifacts, key=lambda item: item.omega.task.task_id))
    task_ids = {item.omega.task.task_id for item in tasks}
    states_by_task = {
        item.omega.task.task_id: {state.assignment.state.state_id for state in item.accepted_states}
        for item in tasks
    }

    b1 = tuple(
        record
        for artifact in tasks
        for record in (
            *(
                _record_from_state(artifact, state, "B1_raw", sampling_weight=1.0)
                for state in artifact.accepted_states
            ),
            *(
                _record_from_rejected(artifact, attempt, "B1_raw")
                for attempt in artifact.rejected_attempts
            ),
        )
    )
    b2 = tuple(
        _record_from_state(artifact, state, "B2_validity", sampling_weight=1.0)
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
    b5, b5_states, b5_blockers = _vtdo_arm(vtdo_round_artifact_paths, tasks)
    arms: dict[str, tuple[VTDOTrainingRecord, ...]] = {
        "B1_raw": b1,
        "B2_validity": b2,
        "B3_ccgr": b3,
        "B4_random_state": b4,
        "B5_vtdo": b5,
    }

    capacities: list[TrainingArmCapacity] = []
    blockers: list[str] = []
    for arm_id in VTDO_TRAINING_ARMS:
        inherited = (
            b3_blockers if arm_id == "B3_ccgr" else b5_blockers if arm_id == "B5_vtdo" else ()
        )
        state_map = b5_states if arm_id == "B5_vtdo" else states_by_task
        capacity = _capacity(config, arm_id, arms[arm_id], state_map, inherited)
        capacities.append(capacity)
        blockers.extend(f"{arm_id}:{item}" for item in capacity.blockers)

    if student.supervised_token_budget != config.target_supervised_tokens:
        blockers.append(
            "student_token_budget_mismatch:"
            f"{student.supervised_token_budget}!={config.target_supervised_tokens}"
        )
    if "Qwen2.5-7B" not in student.base_model:
        blockers.append("student_model_is_not_qwen2.5_7b")
    if student.seed not in config.seeds:
        blockers.append("student_seed_not_in_experiment_seed_contract")
    benchmark_status, benchmark_blockers = _external_benchmark_status(config)
    blockers.extend(benchmark_blockers)
    formal_ready = (
        bool(tasks)
        and bool(task_ids)
        and all(item.capacity_status == "ready" for item in capacities)
        and benchmark_status == "ready"
        and not blockers
    )
    pilot_ready = bool(tasks) and all(
        item.capacity_status != "blocked"
        for item in capacities
        if item.arm_id in {"B1_raw", "B2_validity", "B4_random_state"}
    )
    values = {
        "training_config_hash": student.config_hash,
        "base_model": student.base_model,
        "model_revision": student.model_revision,
        "supervised_token_budget": student.supervised_token_budget,
        "training_seed": student.seed,
        "arms": tuple(capacities),
        "formal_training_ready": formal_ready,
        "pilot_training_ready": pilot_ready,
        "external_benchmark_status": benchmark_status,
        "blockers": tuple(sorted(set(blockers))),
        "schema_version": VTDO_EXPERIMENT_VERSION,
    }
    provisional = TrainingExperimentPreflight.model_construct(**values, report_hash="pending")
    report = TrainingExperimentPreflight(
        **values,
        report_hash=training_experiment_preflight_hash(provisional),
    )
    return report, arms


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
) -> VTDOTrainingRunResult:
    """Train one isolated Qwen2.5-7B LoRA arm after a frozen full preflight."""

    student = VTDOStudentTrainingConfig.from_json(student_config_path)
    preflight = TrainingExperimentPreflight.model_validate_json(
        preflight_path.read_text(encoding="utf-8")
    )
    if student.config_hash != preflight.training_config_hash:
        raise ValueError("VTDO student config differs from the frozen preflight")
    if not preflight.formal_training_ready:
        raise ValueError("VTDO formal training preflight is not ready")
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
    return _train(student, arm_id, records, dataset_hash, output_dir)


def _record_from_state(
    artifact: FinanceTaskStateArtifact,
    state,
    arm_id: VTDOTrainingArm,
    *,
    sampling_weight: float,
    source_distribution_id: str | None = None,
) -> VTDOTrainingRecord:
    return _make_record(
        artifact=artifact,
        trajectory=state.trajectory,
        state_id=state.assignment.state.state_id,
        arm_id=arm_id,
        accepted_target=True,
        sampling_weight=sampling_weight,
        source_distribution_id=source_distribution_id,
        metadata={"lineage_strategy": state.strategy},
    )


def _record_from_rejected(
    artifact: FinanceTaskStateArtifact,
    attempt,
    arm_id: VTDOTrainingArm,
) -> VTDOTrainingRecord:
    return _make_record(
        artifact=artifact,
        trajectory=attempt.trajectory,
        state_id=None,
        arm_id=arm_id,
        accepted_target=False,
        sampling_weight=1.0,
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
) -> VTDOTrainingRecord:
    user_payload = {
        "public_task": artifact.omega.task.public.model_dump(mode="json"),
        "public_evidence_corpus": artifact.omega.public_corpus.model_dump(mode="json"),
        "output_contract": "candidate_trajectory.v1",
    }
    values = {
        "arm_id": arm_id,
        "task_id": artifact.omega.task.task_id,
        "trajectory_state_id": state_id,
        "accepted_target": accepted_target,
        "system_prompt": _SYSTEM_PROMPT,
        "user_prompt": json.dumps(user_payload, ensure_ascii=False, sort_keys=True),
        "assistant_target": trajectory.model_dump_json(),
        "sampling_weight": sampling_weight,
        "source_artifact_id": artifact.artifact_id,
        "source_distribution_id": source_distribution_id,
        "metadata": metadata,
        "schema_version": "vtdo_training_record.v1",
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
) -> tuple[
    tuple[VTDOTrainingRecord, ...],
    dict[str, set[str]],
    tuple[str, ...],
]:
    if not paths:
        return (), {}, ("vtdo_round_artifacts_not_configured",)
    rounds, blockers = _load_rounds(paths)
    if blockers:
        return (), {}, blockers
    latest: dict[str, VTDORoundArtifact] = {}
    for item in rounds:
        previous = latest.get(item.task_condition_id)
        if previous is None or item.round_index > previous.round_index:
            latest[item.task_condition_id] = item
    records: list[VTDOTrainingRecord] = []
    states_by_task: dict[str, set[str]] = {}
    for artifact in artifacts:
        condition_id = artifact.state_catalog.task_condition_id
        round_artifact = latest.get(condition_id)
        if round_artifact is None:
            return (), {}, (f"vtdo_round_missing_task_condition:{condition_id}",)
        probabilities = round_artifact.update.next_distribution.probabilities
        accepted = {item.assignment.state.state_id: item for item in artifact.accepted_states}
        if set(probabilities) != set(accepted):
            return (), {}, (f"vtdo_round_state_support_mismatch:{condition_id}",)
        task_id = artifact.omega.task.task_id
        states_by_task[task_id] = set(probabilities)
        for state_id in sorted(probabilities):
            records.append(
                _record_from_state(
                    artifact,
                    accepted[state_id],
                    "B5_vtdo",
                    sampling_weight=probabilities[state_id],
                    source_distribution_id=round_artifact.update.next_distribution.distribution_id,
                )
            )
    return tuple(records), states_by_task, ()


def _load_rounds(paths: tuple[Path, ...]) -> tuple[tuple[VTDORoundArtifact, ...], tuple[str, ...]]:
    rounds: list[VTDORoundArtifact] = []
    blockers: list[str] = []
    for path in paths:
        if not path.is_file():
            blockers.append(f"vtdo_round_artifact_missing:{path}")
            continue
        try:
            payload = path.read_text(encoding="utf-8")
            for line in payload.splitlines():
                if line.strip():
                    rounds.append(VTDORoundArtifact.model_validate_json(line))
        except (ValueError, json.JSONDecodeError) as exc:
            blockers.append(f"vtdo_round_artifact_invalid:{path}:{type(exc).__name__}")
    if not rounds and not blockers:
        blockers.append("vtdo_round_artifacts_empty")
    return tuple(rounds), tuple(blockers)


def _capacity(
    config: TrainingExperimentConfig,
    arm_id: VTDOTrainingArm,
    records: tuple[VTDOTrainingRecord, ...],
    states_by_task: Mapping[str, set[str]],
    inherited_blockers: tuple[str, ...],
) -> TrainingArmCapacity:
    task_ids = {item.task_id for item in records}
    state_ids = {
        item.trajectory_state_id for item in records if item.trajectory_state_id is not None
    }
    state_counts = [len(states_by_task.get(task_id, ())) for task_id in task_ids]
    blockers = list(inherited_blockers)
    if not records:
        blockers.append("no_materializable_records")
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
    hard_blocked = bool(inherited_blockers) or not records
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
        requested_supervised_tokens=config.target_supervised_tokens,
        capacity_status=status,
        blockers=tuple(sorted(set(blockers))),
    )


def _external_benchmark_status(
    config: TrainingExperimentConfig,
) -> tuple[str, tuple[str, ...]]:
    required = {"finqa", "tat_qa", "financebench"}
    observed = {item.benchmark_id for item in config.external_benchmarks}
    if not observed:
        return "not_configured", ("external_benchmarks:not_configured",)
    blockers: list[str] = []
    if observed != required:
        blockers.append(
            "external_benchmark_set_mismatch:"
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
    scheduled, supervised_tokens = _schedule_records(
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
    values = {
        "arm_id": arm_id,
        "config_hash": config.config_hash,
        "dataset_hash": dataset_hash,
        "base_model": config.base_model,
        "model_revision": config.model_revision,
        "adapter_dir": str(adapter_dir.resolve()),
        "completed_steps": int(output.global_step),
        "final_train_loss": float(output.training_loss),
        "supervised_token_count": supervised_tokens,
        "supervised_token_budget": config.supervised_token_budget,
        "token_budget_deviation_rate": deviation,
        "train_runtime_seconds": runtime,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
        "dependency_versions": _dependency_versions(),
        "status": "completed",
        "schema_version": "vtdo_training_run.v1",
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
    }


def _schedule_records(
    records: tuple[VTDOTrainingRecord, ...],
    encoded: tuple[dict[str, Any], ...],
    *,
    token_budget: int,
    seed: int,
) -> tuple[tuple[dict[str, Any], ...], int]:
    rng = random.Random(seed)
    weights = [item.sampling_weight for item in records]
    scheduled: list[dict[str, Any]] = []
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
        total = next_total
    return tuple(scheduled), total


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
