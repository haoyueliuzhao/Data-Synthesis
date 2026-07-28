from __future__ import annotations

import json
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from trusted_synthesis.core.evaluation.utility import UtilityCohort
from trusted_synthesis.hashing import canonical_hash

from .data import load_sft_records
from .schema import CohortTrainingResult, TrainingUtilityMVPConfig


def train_sft_cohort(
    config: TrainingUtilityMVPConfig,
    cohort: UtilityCohort,
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

    records = load_sft_records(dataset_path)
    if not records or {item.cohort for item in records} != {cohort}:
        raise ValueError(f"dataset does not contain only {cohort.value}")
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
            and completed.cohort == cohort
            and completed.config_hash == config.config_hash
            and completed.dataset_hash == dataset_hash
            and completed.completed_steps == config.max_steps
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
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    encoded, token_audit = _encode_records(
        tokenizer,
        records,
        max_seq_length=config.max_seq_length,
    )
    (output_dir / "token_audit.json").write_text(
        json.dumps(token_audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    model = AutoModelForCausalLM.from_pretrained(
        config.base_model,
        revision=config.model_revision,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
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
    checkpoint_interval = max(1, min(100, config.max_steps // 6 or 1))
    arguments = TrainingArguments(
        output_dir=str(trainer_state_dir),
        max_steps=config.max_steps,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        warmup_ratio=config.warmup_ratio,
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
    train_output = trainer.train(  # type: ignore[attr-defined]
        resume_from_checkpoint=last_checkpoint
    )
    runtime = time.monotonic() - started
    peak_memory = int(torch.cuda.max_memory_allocated())
    trainer.save_model(str(adapter_dir))  # type: ignore[attr-defined]
    tokenizer.save_pretrained(adapter_dir)
    resolved_revision = (
        getattr(model.config, "_commit_hash", None)
        or tokenizer.init_kwargs.get("_commit_hash")
        or config.model_revision
    )
    identity = {
        "cohort": cohort.value,
        "config_hash": config.config_hash,
        "dataset_hash": dataset_hash,
        "base_model": config.base_model,
        "model_revision": resolved_revision,
        "adapter_dir": str(adapter_dir.resolve()),
        "completed_steps": int(train_output.global_step),
        "final_train_loss": float(train_output.training_loss),
    }
    result = CohortTrainingResult(
        cohort=cohort,
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
        dependency_versions=_dependency_versions(),
        status="completed",
        result_hash=canonical_hash(identity, prefix="training_utility_train_result:"),
    )
    (output_dir / "training_result.json").write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


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
    }


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
