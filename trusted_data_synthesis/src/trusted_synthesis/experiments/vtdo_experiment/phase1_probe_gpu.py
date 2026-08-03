from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    AcceptedFinanceState,
    FinanceTaskStateArtifact,
    LineageStrategy,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import VTDOTrainingRecord
from trusted_synthesis.experiments.vtdo_experiment.training import (
    _encode_record,
    _record_from_state,
)
from trusted_synthesis.hashing import canonical_hash

PHASE1_VERSION = "finance_phase1_mvp.v2"
TARGET_STRATEGIES: tuple[LineageStrategy, ...] = (
    "compact_direct",
    "broad_direct",
    "broad_full_lineage",
)
BASELINE_SEED = 20260801
PROBE_SEEDS = (20260801, 20260802)
MAX_SEQUENCE_LENGTH = 24_576


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _model_manifest(model_dir: Path) -> tuple[dict[str, Any], str]:
    files = tuple(sorted(item for item in model_dir.rglob("*") if item.is_file()))
    if not files:
        raise ValueError(f"model directory is empty: {model_dir}")
    manifest = {
        str(item.relative_to(model_dir)): {
            "size": item.stat().st_size,
            "sha256": _sha256(item),
        }
        for item in files
    }
    return manifest, canonical_hash(manifest, prefix="base_model_content_manifest:")


def _load_records(path: Path) -> dict[str, VTDOTrainingRecord]:
    records = tuple(
        VTDOTrainingRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    result = {item.record_id: item for item in records}
    if len(result) != len(records):
        raise ValueError("phase-one records contain duplicate identities")
    return result


def _load_target_artifact(
    artifacts_path: Path,
    task_id: str,
) -> FinanceTaskStateArtifact:
    artifacts = load_finance_multi_state_artifacts(artifacts_path)
    matches = tuple(item for item in artifacts if item.omega.task.task_id == task_id)
    if len(matches) != 1:
        raise ValueError(f"expected one target task, found {len(matches)}")
    return matches[0]


def _selected_states(
    artifact: FinanceTaskStateArtifact,
) -> tuple[AcceptedFinanceState, ...]:
    by_strategy = {item.strategy: item for item in artifact.accepted_states}
    missing = tuple(strategy for strategy in TARGET_STRATEGIES if strategy not in by_strategy)
    if missing:
        raise ValueError(f"target task is missing required phase-one states: {missing}")
    return tuple(by_strategy[strategy] for strategy in TARGET_STRATEGIES)


def prepare_probe(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts_path = Path(args.artifacts_path).resolve()
    model_dir = Path(args.model_dir).resolve()
    all_artifacts = load_finance_multi_state_artifacts(artifacts_path)
    target = next(
        (item for item in all_artifacts if item.omega.task.task_id == args.task_id),
        None,
    )
    if target is None:
        raise ValueError(f"target task was not found: {args.task_id}")
    target_states = _selected_states(target)

    candidates: list[tuple[int, FinanceTaskStateArtifact, VTDOTrainingRecord]] = []
    for artifact in all_artifacts:
        if artifact.omega.task.task_id == args.task_id:
            continue
        state = artifact.accepted_states[0]
        record = _record_from_state(
            artifact,
            state,
            "B2_validity",
            sampling_weight=1.0,
        )
        surface_size = len(record.user_prompt) + len(record.assistant_target)
        candidates.append((surface_size, artifact, record))
    candidates.sort(key=lambda item: (item[0], item[2].record_id))
    protected = candidates[:8]
    if len(protected) != 8:
        raise ValueError("at least eight non-target tasks are required for Probe isolation")

    baseline_records = tuple(item[2] for item in protected[:4])
    validation_records = tuple(item[2] for item in protected[4:6])
    final_test_records = tuple(item[2] for item in protected[6:8])
    update_records = {
        state.assignment.state.state_id: _record_from_state(
            target,
            state,
            "B2_validity",
            sampling_weight=1.0,
        )
        for state in target_states
    }
    records = (
        *baseline_records,
        *validation_records,
        *final_test_records,
        *update_records.values(),
    )
    if len({item.record_id for item in records}) != len(records):
        raise ValueError("Probe train/validation/test/update records overlap")

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    token_audit: dict[str, dict[str, int]] = {}
    for record in records:
        encoded = _encode_record(tokenizer, record, MAX_SEQUENCE_LENGTH)
        token_audit[record.record_id] = {
            "processed_tokens": len(encoded["input_ids"]),
            "prompt_tokens": int(encoded["prompt_tokens"]),
            "supervised_tokens": int(encoded["supervised_tokens"]),
        }

    model_files, model_manifest_hash = _model_manifest(model_dir)
    model_manifest_path = output_dir / "base_model_content_manifest.json"
    _write_json(
        model_manifest_path,
        {
            "model_dir": str(model_dir),
            "files": model_files,
            "manifest_hash": model_manifest_hash,
        },
    )
    records_path = output_dir / "probe_records.jsonl"
    records_path.write_text(
        "".join(item.model_dump_json() + "\n" for item in records),
        encoding="utf-8",
    )
    update_metadata = {
        state.assignment.state.state_id: {
            "strategy": state.strategy,
            "record_id": update_records[state.assignment.state.state_id].record_id,
            "fixture_trajectory_id": state.trajectory.trajectory_id,
        }
        for state in target_states
    }
    values = {
        "experiment_version": PHASE1_VERSION,
        "task_id": args.task_id,
        "task_instruction": target.omega.task.public.instruction,
        "artifacts_path": str(artifacts_path),
        "target_artifact_id": target.artifact_id,
        "target_catalog_id": target.state_catalog.catalog_id,
        "model_dir": str(model_dir),
        "base_model_manifest_hash": model_manifest_hash,
        "base_model_manifest_path": str(model_manifest_path),
        "records_path": str(records_path),
        "baseline_record_ids": [item.record_id for item in baseline_records],
        "internal_validation_record_ids": [item.record_id for item in validation_records],
        "final_test_record_ids": [item.record_id for item in final_test_records],
        "probe_update_records_by_state": update_metadata,
        "probe_seeds": list(PROBE_SEEDS),
        "baseline_seed": BASELINE_SEED,
        "baseline_step_count": 4,
        "probe_step_count": 3,
        "probe_optimizer": "cold_start_sgd",
        "probe_uncertainty_statistic": "sample_standard_deviation",
        "probe_uncertainty_penalty_coefficient": 1.0,
        "probe_centering_policy": "pi_weighted_after_uncertainty_penalty",
        "learning_rate": 0.0002,
        "maximum_sequence_length": MAX_SEQUENCE_LENGTH,
        "token_audit": token_audit,
        "data_isolation": {
            "baseline_task_ids": [item[1].omega.task.task_id for item in protected[:4]],
            "internal_validation_task_ids": [item[1].omega.task.task_id for item in protected[4:6]],
            "final_test_task_ids": [item[1].omega.task.task_id for item in protected[6:8]],
            "probe_task_id": args.task_id,
        },
    }
    values["plan_hash"] = canonical_hash(values, prefix="finance_phase1_probe_plan:")
    _write_json(output_dir / "probe_plan.json", values)
    print(json.dumps(values, indent=2, sort_keys=True))


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    import torch

    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.set_float32_matmul_precision("high")
    torch.backends.cuda.matmul.allow_tf32 = True


def _load_tokenizer(model_dir: Path):
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def _load_base_model(model_dir: Path):
    import torch
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(
        model_dir,
        local_files_only=True,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
        low_cpu_mem_usage=True,
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    return model.to("cuda")


def _new_lora_model(model_dir: Path):
    from peft import LoraConfig, get_peft_model

    base = _load_base_model(model_dir)
    config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.0,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=(
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ),
    )
    return get_peft_model(base, config)


def _baseline_lora_model(model_dir: Path, adapter_dir: Path):
    from peft import PeftModel

    base = _load_base_model(model_dir)
    model = PeftModel.from_pretrained(base, adapter_dir, is_trainable=True)
    model.config.use_cache = False
    return model


def _adapter_tensor_sha256(model: Any) -> str:
    import torch
    from peft import get_peft_model_state_dict

    digest = hashlib.sha256()
    state = get_peft_model_state_dict(model)
    for name, tensor in sorted(state.items()):
        value = tensor.detach().to("cpu").contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(json.dumps(list(value.shape)).encode("ascii"))
        digest.update(value.view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def _batch(tokenizer: Any, record: VTDOTrainingRecord) -> tuple[dict[str, Any], int]:
    import torch

    encoded = _encode_record(tokenizer, record, MAX_SEQUENCE_LENGTH)
    batch = {
        "input_ids": torch.tensor([encoded["input_ids"]], device="cuda"),
        "attention_mask": torch.tensor(
            [encoded["attention_mask"]],
            device="cuda",
        ),
        "labels": torch.tensor([encoded["labels"]], device="cuda"),
    }
    supervised = sum(item != -100 for item in encoded["labels"][1:])
    return batch, supervised


def _evaluate(
    model: Any,
    tokenizer: Any,
    records: Iterable[VTDOTrainingRecord],
) -> tuple[float, float, int]:
    import torch

    model.eval()
    weighted_loss = 0.0
    token_count = 0
    with torch.inference_mode():
        for record in records:
            batch, supervised = _batch(tokenizer, record)
            output = model(**batch)
            weighted_loss += float(output.loss.detach().float().cpu()) * supervised
            token_count += supervised
            del output, batch
    if token_count == 0:
        raise ValueError("evaluation has no supervised tokens")
    loss = weighted_loss / token_count
    return -loss, loss, token_count


def _train_steps(
    model: Any,
    tokenizer: Any,
    records: tuple[VTDOTrainingRecord, ...],
    *,
    step_count: int,
    learning_rate: float,
) -> list[float]:
    import torch

    parameters = tuple(item for item in model.parameters() if item.requires_grad)
    optimizer = torch.optim.AdamW(parameters, lr=learning_rate, weight_decay=0.0)
    if optimizer.state:
        raise ValueError("Contribution optimizer did not start from an empty state")
    losses: list[float] = []
    model.train()
    for index in range(step_count):
        record = records[index % len(records)]
        batch, _ = _batch(tokenizer, record)
        optimizer.zero_grad(set_to_none=True)
        output = model(**batch)
        loss = output.loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters, 1.0)
        optimizer.step()
        losses.append(float(loss.detach().float().cpu()))
        del output, loss, batch
    return losses


def _probe_sgd_steps(
    model: Any,
    tokenizer: Any,
    records: tuple[VTDOTrainingRecord, ...],
    *,
    step_count: int,
    learning_rate: float,
) -> list[float]:
    """Apply an optimizer-state-free SGD perturbation in the trainable parameter space."""

    import torch

    if not 1 <= step_count <= 5:
        raise ValueError("Probe SGD supports one to five diagnostic steps")
    parameters = tuple(item for item in model.parameters() if item.requires_grad)
    if not parameters:
        raise ValueError("Probe SGD has no trainable parameters")
    losses: list[float] = []
    model.train()
    for index in range(step_count):
        record = records[index % len(records)]
        batch, _ = _batch(tokenizer, record)
        model.zero_grad(set_to_none=True)
        output = model(**batch)
        loss = output.loss
        if not torch.isfinite(loss):
            raise ValueError("Probe SGD produced a non-finite loss")
        loss.backward()
        gradients = tuple(parameter.grad for parameter in parameters)
        if any(gradient is None for gradient in gradients):
            raise ValueError("Probe SGD produced a missing trainable gradient")
        if any(
            not torch.isfinite(gradient).all() for gradient in gradients if gradient is not None
        ):
            raise ValueError("Probe SGD produced a non-finite gradient")
        with torch.no_grad():
            for parameter, gradient in zip(parameters, gradients, strict=True):
                if gradient is None:
                    raise ValueError("Probe SGD gradient disappeared before update")
                parameter.add_(gradient, alpha=-learning_rate)
        losses.append(float(loss.detach().float().cpu()))
        del output, loss, batch, gradients
    return losses


def train_baseline(args: argparse.Namespace) -> None:
    import torch

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "probe_plan.json")
    records = _load_records(Path(plan["records_path"]))
    adapter_dir = output_dir / "beneficiary_adapter"
    if adapter_dir.exists():
        raise ValueError(f"baseline adapter already exists: {adapter_dir}")
    _seed_everything(int(plan["baseline_seed"]))
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _new_lora_model(Path(plan["model_dir"]))
    train_records = tuple(records[item] for item in plan["baseline_record_ids"])
    losses = _train_steps(
        model,
        tokenizer,
        train_records,
        step_count=int(plan["baseline_step_count"]),
        learning_rate=float(plan["learning_rate"]),
    )
    validation_records = tuple(records[item] for item in plan["internal_validation_record_ids"])
    performance, validation_loss, validation_tokens = _evaluate(
        model,
        tokenizer,
        validation_records,
    )
    adapter_tensor_sha256 = _adapter_tensor_sha256(model)
    model.save_pretrained(adapter_dir, safe_serialization=True)
    adapter_files = {
        str(item.relative_to(adapter_dir)): {
            "size": item.stat().st_size,
            "sha256": _sha256(item),
        }
        for item in sorted(adapter_dir.rglob("*"))
        if item.is_file()
    }
    checkpoint_hash = canonical_hash(
        {
            "base_model_manifest_hash": plan["base_model_manifest_hash"],
            "adapter_tensor_sha256": adapter_tensor_sha256,
            "adapter_files": adapter_files,
        },
        prefix="qwen_beneficiary_checkpoint:",
    )
    model_state_id = canonical_hash(
        {
            "checkpoint_hash": checkpoint_hash,
            "role": "vtdo_beneficiary",
            "task_family": "finance_phase1",
        },
        prefix="beneficiary_model_state:",
    )
    report = {
        "experiment_version": PHASE1_VERSION,
        "plan_hash": plan["plan_hash"],
        "model_state_id": model_state_id,
        "checkpoint_hash": checkpoint_hash,
        "base_model_manifest_hash": plan["base_model_manifest_hash"],
        "adapter_dir": str(adapter_dir),
        "adapter_tensor_sha256": adapter_tensor_sha256,
        "adapter_files": adapter_files,
        "training_record_ids": plan["baseline_record_ids"],
        "training_losses": losses,
        "internal_validation_record_ids": plan["internal_validation_record_ids"],
        "validation_performance": performance,
        "validation_negative_log_likelihood": validation_loss,
        "validation_supervised_tokens": validation_tokens,
        "completed_steps": int(plan["baseline_step_count"]),
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
        "gpu_name": torch.cuda.get_device_name(0),
        "torch_version": torch.__version__,
    }
    report["report_hash"] = canonical_hash(report, prefix="finance_phase1_beneficiary:")
    _write_json(output_dir / "beneficiary_training_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))


def run_probe_worker(args: argparse.Namespace) -> None:
    import torch

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "probe_plan.json")
    if (
        plan.get("experiment_version") != PHASE1_VERSION
        or plan.get("probe_optimizer") != "cold_start_sgd"
        or plan.get("probe_centering_policy") != "pi_weighted_after_uncertainty_penalty"
    ):
        raise ValueError("Probe worker requires the v2 first-order Probe contract")
    baseline = _read_json(output_dir / "beneficiary_training_report.json")
    state = plan["probe_update_records_by_state"].get(args.state_id)
    if not isinstance(state, dict):
        raise ValueError(f"unknown Probe state: {args.state_id}")
    if args.seed not in plan["probe_seeds"]:
        raise ValueError(f"seed is outside the frozen Probe contract: {args.seed}")
    records = _load_records(Path(plan["records_path"]))
    _seed_everything(args.seed)
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(baseline["adapter_dir"]),
    )
    loaded_hash = _adapter_tensor_sha256(model)
    if loaded_hash != baseline["adapter_tensor_sha256"]:
        raise ValueError("loaded baseline Adapter differs from the frozen beneficiary")
    validation_records = tuple(records[item] for item in plan["internal_validation_record_ids"])
    loaded_performance, loaded_loss, _ = _evaluate(model, tokenizer, validation_records)
    if not math.isclose(
        loaded_performance,
        float(baseline["validation_performance"]),
        rel_tol=0.0,
        abs_tol=5e-7,
    ):
        raise ValueError("worker did not reproduce the frozen beneficiary metric")
    update_record = records[str(state["record_id"])]
    losses = _probe_sgd_steps(
        model,
        tokenizer,
        (update_record,),
        step_count=int(plan["probe_step_count"]),
        learning_rate=float(plan["learning_rate"]),
    )
    adapted_performance, adapted_loss, validation_tokens = _evaluate(
        model,
        tokenizer,
        validation_records,
    )
    adapted_tensor_sha256 = _adapter_tensor_sha256(model)
    adapted_checkpoint_hash = canonical_hash(
        {
            "base_checkpoint_hash": baseline["checkpoint_hash"],
            "adapter_tensor_sha256": adapted_tensor_sha256,
            "state_id": args.state_id,
            "seed": args.seed,
            "step_count": plan["probe_step_count"],
        },
        prefix="qwen_probe_adapted_checkpoint:",
    )
    adapted_model_state_id = canonical_hash(
        {
            "checkpoint_hash": adapted_checkpoint_hash,
            "role": "contribution_probe_adaptation",
        },
        prefix="probe_model_state:",
    )
    result = {
        "experiment_version": PHASE1_VERSION,
        "plan_hash": plan["plan_hash"],
        "beneficiary_report_hash": baseline["report_hash"],
        "base_model_state_id": baseline["model_state_id"],
        "base_checkpoint_hash": baseline["checkpoint_hash"],
        "state_id": args.state_id,
        "strategy": state["strategy"],
        "seed": args.seed,
        "update_record_id": update_record.record_id,
        "step_count": int(plan["probe_step_count"]),
        "training_losses": losses,
        "loaded_baseline_performance": loaded_performance,
        "loaded_baseline_loss": loaded_loss,
        "adapted_performance": adapted_performance,
        "adapted_loss": adapted_loss,
        "performance_gain": adapted_performance - float(baseline["validation_performance"]),
        "validation_supervised_tokens": validation_tokens,
        "adapted_adapter_tensor_sha256": adapted_tensor_sha256,
        "adapted_checkpoint_hash": adapted_checkpoint_hash,
        "adapted_model_state_id": adapted_model_state_id,
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
        "gpu_name": torch.cuda.get_device_name(0),
        "torch_version": torch.__version__,
    }
    result["report_hash"] = canonical_hash(result, prefix="finance_phase1_probe_worker:")
    worker_dir = output_dir / "probe_workers"
    worker_path = worker_dir / f"{args.state_id.rsplit(':', 1)[-1]}_{args.seed}.json"
    _write_json(worker_path, result)
    print(json.dumps(result, indent=2, sort_keys=True))
