"""Bounded real-Qwen engineering checks, explicitly not scientific training.

Synthetic token controls are never formal material. No adapter or optimizer
checkpoint is written, and this process exits before any production run starts.
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import torch
import torch.nn.functional as functional

from ..finance_qa_vnext_basis_student.protocol import training_config as baseline_config
from ..finance_qa_vnext_basis_student.train import _optimizer, load_registered_student
from ..finance_qa_vnext_pq_student import model as model_components
from . import consumer
from .protocol import encode, record, require, sha, write_once


def controls(sequence_length, first_row_target_tokens=8):
    """Five synthetic task identities, heterogeneous state and package counts."""
    require(
        type(sequence_length) is int and 64 <= sequence_length <= 24576,
        "gpu_preflight.bounded_sequence_length",
    )
    require(
        type(first_row_target_tokens) is int and 0 < first_row_target_tokens < sequence_length,
        "gpu_preflight.bounded_positive_target_length",
    )
    tasks = [
        {"task_id": "synthetic-" + str(i), "group": group}
        for i, group in enumerate((*consumer.GROUPS[:3], "control", "control"))
    ]
    examples = []
    for task_index, task in enumerate(tasks):
        specifications = (
            (("endpoint", 1, Fraction(1, 3)), ("movement", 2 + task_index, Fraction(2, 3)))
            if task_index < 3
            else (("control", task_index - 2, Fraction(1)),)
        )
        for method, n, pi in specifications:
            state_id = task["task_id"] + ":" + method
            for package_index in range(n):
                # Only one row reaches the requested maximum. The others are
                # short, so the check measures boundary memory without burning
                # an entire synthetic epoch at the maximum context length.
                length = sequence_length if not examples else 128 + 16 * package_index
                target_count = (
                    first_row_target_tokens if not examples else 8 + package_index + task_index
                )
                ids = [20 + (index % 70) for index in range(length)]
                mask = [0] * (length - target_count) + [1] * target_count
                representation = {
                    "input_ids": ids,
                    "target_mask": mask,
                    "labels": [
                        token if active else -100 for token, active in zip(ids, mask, strict=True)
                    ],
                    "sequence_length": length,
                    "target_token_count": target_count,
                }
                examples.append(
                    {
                        "package_id": state_id + ":" + str(package_index),
                        "task_id": task["task_id"],
                        "state_id": state_id,
                        "method": method,
                        "pool": "A",
                        "role": "train",
                        "rows": [{"representation": representation}],
                        "whole_package_target_tokens": target_count,
                        "n_state": n,
                        "pi": str(pi),
                        "target_token_coefficient": str(pi / (5 * n * target_count)),
                    }
                )
    return {"tasks": tasks}, examples


def run(output, *, sequence_length=512, seed=11, first_row_target_tokens=8):
    output = Path(output).resolve()
    require(not output.exists(), "gpu_preflight.exclusive_new_output")
    batch, examples = controls(sequence_length, first_row_target_tokens)
    output.mkdir(parents=True)
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    write_once(
        output / "started.json",
        record(
            "gpu_engineering_started",
            started_at=started_at,
            pid=os.getpid(),
            seed=seed,
            cuda_visible_devices=os.environ.get("CUDA_VISIBLE_DEVICES"),
            scientific_training=False,
            new_formal_materials=False,
            external_model_API_calls=0,
            save_adapter_or_optimizer=False,
            sequence_length=sequence_length,
            first_row_target_tokens=first_row_target_tokens,
            source_code_sha256={
                name: sha(Path(__file__).with_name(name))
                for name in ("consumer.py", "gpu_preflight.py", "protocol.py")
            },
            synthetic_optimizer_updates=1,
            reused_for_production=False,
        ),
    )
    print(
        json.dumps(
            {
                "event": "binding_checkpoint",
                "pid": os.getpid(),
                "started_at": started_at,
                "output": str(output),
            }
        ),
        flush=True,
    )
    try:
        binding = model_components.bind_checkpoint()
        write_once(output / "checkpoint_binding.json", binding)
        print(
            json.dumps(
                {"event": "loading_real_qwen", "elapsed_seconds": time.monotonic() - started}
            ),
            flush=True,
        )
        model, scope = load_registered_student(binding, seed, trainable=True)
        torch.cuda.synchronize()
        loaded_at = datetime.now(timezone.utc).isoformat()
        initial_digest = model_components.adapter_digest(model)
        write_once(
            output / "loaded.json",
            record(
                "gpu_engineering_loaded",
                time=loaded_at,
                pid=os.getpid(),
                scope=scope,
                model="Qwen2.5-7B-Instruct",
                base_binding_id=binding["id"],
                initial_adapter_digest=initial_digest,
                allocated_bytes=torch.cuda.memory_allocated(),
                reserved_bytes=torch.cuda.memory_reserved(),
                baseline_configuration=baseline_config(),
            ),
        )
        print(
            json.dumps(
                {
                    "event": "real_qwen_loaded",
                    "time": loaded_at,
                    "elapsed_seconds": time.monotonic() - started,
                }
            ),
            flush=True,
        )
        parameters = [p for p in model.parameters() if p.requires_grad]
        optimizer = _optimizer(parameters, baseline_config())
        require(not optimizer.state, "gpu_preflight.fresh_optimizer")
        write_once(
            output / "synthetic_control_identity.json",
            record(
                "synthetic_controls",
                package_count=len(examples),
                examples_sha256=sha(encode(examples)),
                package_ids=[p["package_id"] for p in examples],
                scientific_training=False,
                no_financial_qualification_claim=True,
            ),
        )
        observed_nll = []

        def measured_loss(logits, targets, coefficient):
            # Record unscaled NLL independently, then use the production loss.
            raw = functional.cross_entropy(
                logits[0].float(), torch.tensor(targets, device=logits.device), reduction="sum"
            )
            observed_nll.append(float(raw.detach()))
            return consumer.selected_target_loss(logits, targets, coefficient)

        torch.cuda.reset_peak_memory_stats()
        update_start = time.monotonic()
        with (output / "events.jsonl").open("xb") as stream:

            def emit(event):
                stream.write(encode(event) + b"\n")
                stream.flush()
                if event["event"] in ("row_backward_completed", "before_optimizer_step"):
                    print(
                        json.dumps(
                            {
                                **{k: v for k, v in event.items() if k != "packages"},
                                "elapsed_seconds": time.monotonic() - update_start,
                            }
                        ),
                        flush=True,
                    )

            result = consumer.execute_update(
                model,
                optimizer,
                examples,
                batch,
                pool="A",
                arm="plus",
                device="cuda:0",
                loss_fn=measured_loss,
                event_sink=emit,
                expected_package_ids=[p["package_id"] for p in examples],
                engineering_only=True,
            )
        torch.cuda.synchronize()
        elapsed = time.monotonic() - update_start
        require(len(observed_nll) == len(examples), "gpu_preflight.all_control_raw_losses")
        # Independent grouped task/state/package-mean form, not the consumer's
        # token coefficient expression. Package counts deliberately differ.
        grouped = {}
        for package, nll in zip(examples, observed_nll, strict=True):
            key = package["task_id"], package["state_id"]
            entry = grouped.setdefault(key, {"pi": Fraction(package["pi"]), "means": []})
            entry["means"].append(nll / package["whole_package_target_tokens"])
        reference = (
            sum(
                float(item["pi"]) * sum(item["means"]) / len(item["means"])
                for item in grouped.values()
            )
            / 5
        )
        absolute_error = abs(reference - result["weighted_loss"])
        require(
            absolute_error <= 1e-5 * max(1.0, abs(reference)),
            "gpu_preflight.grouped_reference_loss_matches",
        )
        final_digest = model_components.adapter_digest(model)
        require(final_digest != initial_digest, "gpu_preflight.actual_nonzero_update")
        require(
            all(
                v.dtype == torch.float32
                for state in optimizer.state.values()
                for key, v in state.items()
                if key in ("exp_avg", "exp_avg_sq")
            ),
            "gpu_preflight_FP32_optimizer_moments",
        )
        report = record(
            "gpu_engineering_report",
            status="PASS_ENGINEERING_ONLY",
            scientific_training=False,
            formal_materials_consumed=0,
            scientific_student_updates=0,
            synthetic_optimizer_updates=1,
            pid=os.getpid(),
            started_at=started_at,
            model_loaded_at=loaded_at,
            cuda_visible_devices=os.environ.get("CUDA_VISIBLE_DEVICES"),
            gpu_name=torch.cuda.get_device_name(),
            checkpoint_binding_id=binding["id"],
            trainable_scope=scope,
            baseline_configuration=baseline_config(),
            actual_sequence_length_max=max(
                row["representation"]["sequence_length"]
                for package in examples
                for row in package["rows"]
            ),
            first_row_target_tokens=first_row_target_tokens,
            update_report=result,
            independent_grouped_loss=reference,
            weighted_loss_absolute_error=absolute_error,
            initial_adapter_digest=initial_digest,
            discarded_final_adapter_digest=final_digest,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            update_seconds=elapsed,
            sequence_tokens_per_second=result["sequence_tokens"] / elapsed,
            target_tokens_per_second=result["target_tokens"] / elapsed,
            total_seconds=time.monotonic() - started,
            adapter_or_optimizer_checkpoint_saved=False,
            production_initialization_reused=False,
            external_model_API_calls=0,
        )
        write_once(output / "report.json", report)
        print(
            json.dumps(
                {
                    "event": "PASS_ENGINEERING_ONLY",
                    "report": str(output / "report.json"),
                    "update_seconds": elapsed,
                    "peak_allocated_bytes": report["peak_allocated_bytes"],
                    "reference_error": absolute_error,
                }
            ),
            flush=True,
        )
        del optimizer, model
        torch.cuda.empty_cache()
        return report
    except BaseException as error:
        write_once(
            output / "failure.json",
            record(
                "gpu_engineering_failure",
                error_type=type(error).__name__,
                error=str(error),
                scientific_training=False,
                elapsed_seconds=time.monotonic() - started,
                automatic_retry=False,
            ),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sequence-length", type=int, default=512)
    parser.add_argument("--seed", type=int, choices=(11, 29, 47), default=11)
    parser.add_argument("--first-row-target-tokens", type=int, default=8)
    args = parser.parse_args()
    run(
        args.output,
        sequence_length=args.sequence_length,
        seed=args.seed,
        first_row_target_tokens=args.first_row_target_tokens,
    )
