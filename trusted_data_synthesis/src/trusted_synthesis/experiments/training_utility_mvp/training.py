from __future__ import annotations

import json
import math
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from trusted_synthesis.core.evaluation.utility import UtilityCohort
from trusted_synthesis.hashing import canonical_hash

from .data import load_sft_records
from .model_security import validate_model_loading_contract
from .schema import (
    CohortTokenBudgetAudit,
    CohortTrainingResult,
    TrainingUtilityMVPConfig,
)


def train_sft_cohort(
    config: TrainingUtilityMVPConfig,
    cohort: UtilityCohort | str,
    dataset_path: Path,
    output_dir: Path,
) -> CohortTrainingResult:
    """Train one isolated BF16 LoRA cohort with a frozen experiment contract."""

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
        from transformers.trainer_utils import get_last_checkpoint
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "training dependencies are missing; install the project training extra"
        ) from exc
    if not torch.cuda.is_available():
        raise RuntimeError("the Qwen2.5-7B MVP requires a CUDA device")
    validate_model_loading_contract(config.base_model, config.model_revision)

    cohort_name = cohort.value if isinstance(cohort, UtilityCohort) else cohort
    records = load_sft_records(dataset_path)
    if not records or {item.cohort for item in records} != {cohort_name}:
        raise ValueError(f"dataset does not contain only {cohort_name}")
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_hash = canonical_hash(
        tuple(item.record_hash for item in records),
        prefix="training_utility_cohort_dataset:",
    )
    completed_result_path = output_dir / "training_result.json"
    adapter_dir = output_dir / "adapter"
    if completed_result_path.is_file() and adapter_dir.is_dir():
        completed = CohortTrainingResult.model_validate_json(
            completed_result_path.read_text(encoding="utf-8")
        )
        if (
            completed.status == "completed"
            and completed.cohort == cohort_name
            and completed.config_hash == config.config_hash
            and completed.dataset_hash == dataset_hash
            and _completed_training_budget_matches(config, completed)
        ):
            return completed
        raise ValueError(
            "output directory contains a completed result for a different "
            "training contract"
        )
    set_seed(config.seed)
    tokenizer = AutoTokenizer.from_pretrained(
        config.base_model,
        revision=config.model_revision,
        use_fast=True,
        trust_remote_code=False,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    encoded, token_audit = _encode_records(
        tokenizer,
        records,
        max_seq_length=config.max_seq_length,
    )
    (
        encoded,
        supervised_token_count,
        deviation_rate,
        effective_max_steps,
        token_audit,
    ) = _prepare_supervised_token_schedule(
        config,
        records,
        encoded,
        token_audit,
        fail_on_blocker=True,
    )
    (output_dir / "token_audit.json").write_text(
        json.dumps(token_audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
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
    trainable_count = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    total_count = sum(parameter.numel() for parameter in model.parameters())
    trainer_state_dir = output_dir / "trainer_state"
    checkpoint_interval = max(1, min(100, effective_max_steps // 6 or 1))
    arguments = TrainingArguments(
        output_dir=str(trainer_state_dir),
        max_steps=effective_max_steps,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        warmup_steps=math.ceil(effective_max_steps * config.warmup_ratio),
        weight_decay=config.weight_decay,
        bf16=True,
        fp16=False,
        gradient_checkpointing=True,
        logging_strategy="steps",
        logging_steps=1,
        save_strategy="steps",
        save_steps=checkpoint_interval,
        save_total_limit=2,
        report_to=[],
        remove_unused_columns=False,
        dataloader_num_workers=2,
        dataloader_pin_memory=True,
        optim="adamw_torch_fused",
        seed=config.seed,
        data_seed=config.seed,
    )
    trainer = Trainer(
        model=model,
        args=arguments,
        train_dataset=encoded,
        data_collator=_causal_collator(tokenizer.pad_token_id),
    )
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    last_checkpoint = (
        get_last_checkpoint(str(trainer_state_dir)) if trainer_state_dir.is_dir() else None
    )
    train_output = trainer.train(
        resume_from_checkpoint=last_checkpoint
    )
    runtime = time.monotonic() - started
    peak_memory = int(torch.cuda.max_memory_allocated())
    trainer.save_model(str(adapter_dir))
    tokenizer.save_pretrained(adapter_dir)
    resolved_revision = (
        getattr(model.config, "_commit_hash", None)
        or tokenizer.init_kwargs.get("_commit_hash")
        or config.model_revision
    )
    identity = {
        "cohort": cohort_name,
        "config_hash": config.config_hash,
        "dataset_hash": dataset_hash,
        "base_model": config.base_model,
        "model_revision": resolved_revision,
        "adapter_dir": str(adapter_dir.resolve()),
        "completed_steps": int(train_output.global_step),
        "final_train_loss": float(train_output.training_loss),
        "supervised_token_count": supervised_token_count,
        "supervised_token_budget": config.supervised_token_budget,
    }
    result = CohortTrainingResult(
        cohort=cohort_name,
        config_hash=config.config_hash,
        dataset_hash=dataset_hash,
        base_model=config.base_model,
        model_revision=resolved_revision,
        adapter_dir=str(adapter_dir.resolve()),
        trainable_parameter_count=trainable_count,
        total_parameter_count=total_count,
        final_train_loss=float(train_output.training_loss),
        train_runtime_seconds=runtime,
        peak_gpu_memory_bytes=peak_memory,
        completed_steps=int(train_output.global_step),
        supervised_token_count=supervised_token_count,
        supervised_token_budget=config.supervised_token_budget,
        token_budget_deviation_rate=deviation_rate,
        micro_batch_count=(
            len(encoded) // config.per_device_train_batch_size
        ),
        dependency_versions=_dependency_versions(),
        status="completed",
        result_hash=canonical_hash(identity, prefix="training_utility_train_result:"),
    )
    (output_dir / "training_result.json").write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def audit_sft_token_budget(
    config: TrainingUtilityMVPConfig,
    cohort: UtilityCohort | str,
    dataset_path: Path,
) -> CohortTokenBudgetAudit:
    """Tokenize on CPU and replay the exact scheduler without loading model weights."""

    try:
        from transformers import AutoTokenizer
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "token-audit dependencies are missing; install the project training extra"
        ) from exc
    validate_model_loading_contract(config.base_model, config.model_revision)
    cohort_name = cohort.value if isinstance(cohort, UtilityCohort) else cohort
    records = load_sft_records(dataset_path)
    if not records or {item.cohort for item in records} != {cohort_name}:
        raise ValueError(f"dataset does not contain only {cohort_name}")
    dataset_hash = canonical_hash(
        tuple(item.record_hash for item in records),
        prefix="training_utility_cohort_dataset:",
    )
    tokenizer = AutoTokenizer.from_pretrained(
        config.base_model,
        revision=config.model_revision,
        use_fast=True,
        trust_remote_code=False,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    encoded, token_audit = _encode_records(
        tokenizer,
        records,
        max_seq_length=config.max_seq_length,
    )
    raw_input_token_count = sum(len(item["input_ids"]) for item in encoded)
    (
        scheduled,
        supervised_token_count,
        deviation_rate,
        effective_max_steps,
        token_audit,
    ) = _prepare_supervised_token_schedule(
        config,
        records,
        encoded,
        token_audit,
        fail_on_blocker=False,
    )
    blockers = tuple(token_audit["blockers"])
    identity = {
        "cohort": cohort_name,
        "config_hash": config.config_hash,
        "dataset_hash": dataset_hash,
        "raw_input_token_count": raw_input_token_count,
        "raw_supervised_token_count": token_audit["raw_supervised_tokens"],
        "scheduled_record_count": len(scheduled),
        "scheduled_supervised_token_count": supervised_token_count,
        "effective_optimizer_steps": effective_max_steps,
        "blockers": blockers,
    }
    return CohortTokenBudgetAudit(
        cohort=cohort_name,
        config_hash=config.config_hash,
        dataset_hash=dataset_hash,
        record_count=len(records),
        raw_input_token_count=raw_input_token_count,
        raw_supervised_token_count=token_audit["raw_supervised_tokens"],
        minimum_record_tokens=token_audit["minimum_tokens"],
        maximum_record_tokens=token_audit["maximum_tokens"],
        maximum_target_tokens=token_audit["maximum_target_tokens"],
        truncated_record_count=token_audit["truncated_record_count"],
        scheduled_record_count=len(scheduled),
        scheduled_supervised_token_count=supervised_token_count,
        supervised_token_budget=config.supervised_token_budget,
        token_budget_deviation_rate=deviation_rate,
        examples_per_optimizer_step=token_audit["examples_per_optimizer_step"],
        effective_optimizer_steps=effective_max_steps,
        maximum_optimizer_steps=config.max_steps,
        training_format_counts=token_audit["training_format_counts"],
        blockers=blockers,
        status="blocked" if blockers else "ready",
        audit_hash=canonical_hash(identity, prefix="training_token_budget_audit:"),
    )


def _completed_training_budget_matches(
    config: TrainingUtilityMVPConfig,
    result: CohortTrainingResult,
) -> bool:
    if config.supervised_token_budget is None:
        return result.completed_steps == config.max_steps
    return bool(
        result.supervised_token_budget == config.supervised_token_budget
        and result.supervised_token_count is not None
        and result.token_budget_deviation_rate is not None
        and result.micro_batch_count is not None
        and result.completed_steps
        == result.micro_batch_count
        // config.gradient_accumulation_steps
        and result.token_budget_deviation_rate
        <= config.maximum_token_budget_deviation_rate
    )


def _prepare_supervised_token_schedule(
    config: TrainingUtilityMVPConfig,
    records: tuple[Any, ...],
    encoded: list[dict[str, list[int]]],
    token_audit: dict[str, Any],
    *,
    fail_on_blocker: bool,
) -> tuple[
    list[dict[str, list[int]]],
    int,
    float | None,
    int,
    dict[str, Any],
]:
    raw_supervised_tokens = sum(
        label != -100 for item in encoded for label in item["labels"]
    )
    scheduled = encoded
    supervised_token_count = raw_supervised_tokens
    effective_max_steps = config.max_steps
    examples_per_step = (
        config.per_device_train_batch_size * config.gradient_accumulation_steps
    )
    if config.supervised_token_budget is not None:
        scheduled, supervised_token_count = _schedule_supervised_token_budget(
            encoded,
            records,
            token_budget=config.supervised_token_budget,
            examples_per_step=examples_per_step,
            seed=config.seed,
        )
        effective_max_steps = len(scheduled) // examples_per_step
    deviation_rate = (
        abs(supervised_token_count - config.supervised_token_budget)
        / config.supervised_token_budget
        if config.supervised_token_budget is not None
        else None
    )
    blockers = []
    if effective_max_steps > config.max_steps:
        blockers.append(
            "supervised token budget requires "
            f"{effective_max_steps} steps, above max_steps={config.max_steps}"
        )
    if (
        deviation_rate is not None
        and deviation_rate > config.maximum_token_budget_deviation_rate
    ):
        blockers.append(
            "supervised token schedule deviation exceeds contract: "
            f"{deviation_rate:.6f} > {config.maximum_token_budget_deviation_rate:.6f}"
        )
    token_audit = dict(token_audit)
    token_audit.update(
        {
            "raw_supervised_tokens": raw_supervised_tokens,
            "scheduled_record_count": len(scheduled),
            "scheduled_supervised_tokens": supervised_token_count,
            "supervised_token_budget": config.supervised_token_budget,
            "token_budget_deviation_rate": deviation_rate,
            "examples_per_optimizer_step": examples_per_step,
            "effective_max_steps": effective_max_steps,
            "blockers": blockers,
        }
    )
    if fail_on_blocker and blockers:
        raise ValueError("; ".join(blockers))
    return (
        scheduled,
        supervised_token_count,
        deviation_rate,
        effective_max_steps,
        token_audit,
    )


def _schedule_supervised_token_budget(
    encoded: list[dict[str, list[int]]],
    records: tuple[Any, ...],
    *,
    token_budget: int,
    examples_per_step: int,
    seed: int,
) -> tuple[list[dict[str, list[int]]], int]:
    """Build complete optimizer-step blocks nearest to the frozen token budget."""

    if not encoded or len(encoded) != len(records):
        raise ValueError("token scheduling requires aligned encoded records")
    if examples_per_step < 1:
        raise ValueError("examples_per_step must be positive")
    target_counts = [
        sum(label != -100 for label in item["labels"])
        for item in encoded
    ]
    scheduled_indices: list[int] = []
    scheduled_tokens = 0
    cycle = 0
    while scheduled_tokens < token_budget:
        order = sorted(
            range(len(records)),
            key=lambda index: canonical_hash(
                {
                    "seed": seed,
                    "cycle": cycle,
                    "record_id": records[index].record_id,
                },
                prefix="training_token_schedule:",
            ),
        )
        cycle += 1
        for offset in range(0, len(order), examples_per_step):
            block = order[offset : offset + examples_per_step]
            if len(block) != examples_per_step:
                continue
            previous_count = len(scheduled_indices)
            previous_tokens = scheduled_tokens
            scheduled_indices.extend(block)
            scheduled_tokens += sum(target_counts[index] for index in block)
            if scheduled_tokens < token_budget:
                continue
            if (
                previous_count
                and abs(previous_tokens - token_budget)
                < abs(scheduled_tokens - token_budget)
            ):
                del scheduled_indices[previous_count:]
                scheduled_tokens = previous_tokens
            return [encoded[index] for index in scheduled_indices], scheduled_tokens
    raise AssertionError("unreachable token schedule state")


def _encode_records(
    tokenizer: Any,
    records: tuple[Any, ...],
    *,
    max_seq_length: int,
) -> tuple[list[dict[str, list[int]]], dict[str, Any]]:
    encoded = []
    token_counts = []
    target_token_counts = []
    for record in records:
        if record.training_format == "host_instrumented_joint":
            full_ids, labels = _encode_host_transcript(tokenizer, record)
            if len(full_ids) > max_seq_length:
                raise ValueError(
                    f"record {record.record_id} requires {len(full_ids)} tokens, "
                    f"above max_seq_length={max_seq_length}"
                )
            supervised_count = sum(item != -100 for item in labels)
            if not supervised_count:
                raise ValueError(f"record {record.record_id} has no supervised target tokens")
            encoded.append(
                {
                    "input_ids": full_ids,
                    "attention_mask": [1] * len(full_ids),
                    "labels": labels,
                }
            )
            token_counts.append(len(full_ids))
            target_token_counts.append(supervised_count)
            continue
        prompt_messages = [
            {"role": "system", "content": record.system_prompt},
            {"role": "user", "content": record.user_prompt},
        ]
        full_messages = [
            *prompt_messages,
            {"role": "assistant", "content": record.assistant_target},
        ]
        prompt_text = tokenizer.apply_chat_template(
            prompt_messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        full_text = tokenizer.apply_chat_template(
            full_messages,
            tokenize=False,
            add_generation_prompt=False,
        )
        prompt_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
        full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]
        if full_ids[: len(prompt_ids)] != prompt_ids:
            raise ValueError("chat template does not preserve the generation prompt prefix")
        if len(full_ids) > max_seq_length:
            raise ValueError(
                f"record {record.record_id} requires {len(full_ids)} tokens, "
                f"above max_seq_length={max_seq_length}"
            )
        labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids) :]
        if not any(item != -100 for item in labels):
            raise ValueError(f"record {record.record_id} has no supervised target tokens")
        encoded.append(
            {
                "input_ids": full_ids,
                "attention_mask": [1] * len(full_ids),
                "labels": labels,
            }
        )
        token_counts.append(len(full_ids))
        target_token_counts.append(len(full_ids) - len(prompt_ids))
    return encoded, {
        "record_count": len(encoded),
        "max_seq_length": max_seq_length,
        "minimum_tokens": min(token_counts),
        "maximum_tokens": max(token_counts),
        "mean_tokens": sum(token_counts) / len(token_counts),
        "maximum_target_tokens": max(target_token_counts),
        "truncated_record_count": 0,
        "training_format_counts": dict(
            sorted(
                {
                    key: sum(item.training_format == key for item in records)
                    for key in {item.training_format for item in records}
                }.items()
            )
        ),
    }


def _encode_host_transcript(tokenizer: Any, record: Any) -> tuple[list[int], list[int]]:
    messages = [
        {"role": item.role, "content": item.content}
        for item in record.messages
    ]
    full_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )
    full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]
    labels = [-100] * len(full_ids)
    for index, message in enumerate(record.messages):
        if not message.supervise:
            continue
        before_text = tokenizer.apply_chat_template(
            messages[:index],
            tokenize=False,
            add_generation_prompt=True,
        )
        through_text = tokenizer.apply_chat_template(
            messages[: index + 1],
            tokenize=False,
            add_generation_prompt=False,
        )
        before_ids = tokenizer(before_text, add_special_tokens=False)["input_ids"]
        through_ids = tokenizer(through_text, add_special_tokens=False)["input_ids"]
        if full_ids[: len(through_ids)] != through_ids:
            raise ValueError(
                "chat template does not preserve the host transcript assistant prefix"
            )
        if through_ids[: len(before_ids)] != before_ids:
            raise ValueError(
                "chat template does not preserve the host transcript generation prefix"
            )
        labels[len(before_ids) : len(through_ids)] = through_ids[len(before_ids) :]
    return full_ids, labels


def _causal_collator(pad_token_id: int):
    def collate(features: list[dict[str, list[int]]]):
        import torch

        maximum = max(len(item["input_ids"]) for item in features)
        input_ids = []
        attention_masks = []
        labels = []
        for item in features:
            padding = maximum - len(item["input_ids"])
            input_ids.append(item["input_ids"] + [pad_token_id] * padding)
            attention_masks.append(item["attention_mask"] + [0] * padding)
            labels.append(item["labels"] + [-100] * padding)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_masks, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }

    return collate


def _dependency_versions() -> dict[str, str]:
    output = {}
    for package in ("torch", "transformers", "peft", "accelerate", "datasets"):
        try:
            output[package] = version(package)
        except PackageNotFoundError:
            output[package] = "missing"
    return output
