"""Actual fixed-budget Student runs: one full weighted pass per optimizer update."""

import argparse
import os
import random
import time
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import save

from .guards import offline_guard
from .guards import report as guard_report
from .inference import evaluate_model
from .loss import selected_target_loss
from .model import adapter_digest, load_student, save_adapter
from .plan import OUTPUT, SEEDS, evaluation_config, read_json, record, require, sha, training_config
from .weights import load_rows


def row_orders(seed, row_count=36):
    result = []
    generator = random.Random(seed)
    for _ in range(training_config()["epochs"]):
        order = list(range(row_count))
        generator.shuffle(order)
        result.append(order)
    return result


def run_training(root, arm, seed):
    require(arm in {"P", "Q"} and seed in SEEDS, "training.registered_run")
    output = root / OUTPUT
    prep = output / "preparation"
    config = read_json(prep / "training_configuration.json")
    require(config == training_config(), "training.frozen_configuration")
    require(
        read_json(prep / "evaluation_configuration.json") == evaluation_config(),
        "training.evaluation_frozen_before_updates",
    )
    verify_source_snapshot(root, read_json(prep / "implementation.json"))
    view = read_json(prep / "weight_view.json")
    rows = load_rows(root, view)
    require(
        len(rows) == 36
        and sum(len(row["target_ids"]) for row in rows) == 4793
        and sum(row["sequence_length"] for row in rows) == 232603,
        "training.exact_physical_epoch",
    )
    variant = f"{arm}_{seed}"
    store = DurableStore(output / "training" / variant)
    checkpoint = read_json(prep / "checkpoint_binding.json")
    model, scope = load_student(checkpoint, seed, trainable=True)
    initial_digest = adapter_digest(model)
    orders = row_orders(seed, len(rows))
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(
        parameters,
        lr=config["learning_rate"],
        betas=tuple(config["betas"]),
        eps=config["eps"],
        weight_decay=config["weight_decay"],
    )
    identity = record(
        "training_run_identity",
        variant=variant,
        arm=arm,
        seed=seed,
        checkpoint_binding_id=checkpoint["id"],
        weight_view_id=view["id"],
        configuration_id=config["id"],
        scope=scope,
        initial_adapter_parameter_sha256=initial_digest,
        orders=orders,
        initial_CPU_rng_sha256=sha(torch.get_rng_state().numpy().tobytes()),
        initial_CUDA_rng_sha256=sha(torch.cuda.get_rng_state().cpu().numpy().tobytes()),
        device=torch.cuda.get_device_name(0),
        visible_device=os.environ.get("CUDA_VISIBLE_DEVICES"),
        optimizer_initial_state_empty=not optimizer.state,
        actual_base_weights_loaded=True,
        all_original_training_targets_unchanged=True,
    )
    store.json("identity.json", identity)
    started = time.perf_counter()
    token_count, sequence_count, records = 0, 0, []
    for epoch, order in enumerate(orders, 1):
        optimizer.zero_grad(set_to_none=True)
        total_loss, package_nll, package_tokens = 0.0, defaultdict(float), defaultdict(int)
        epoch_started = time.perf_counter()
        for position, index in enumerate(order, 1):
            row = rows[index]
            ids = torch.tensor([row["input_ids"]], dtype=torch.long, device="cuda:0")
            attention = torch.tensor([row["attention_mask"]], dtype=torch.long, device="cuda:0")
            positions = torch.tensor(row["logit_positions"], dtype=torch.long, device="cuda:0")
            coefficient = row["coefficient"][arm]
            with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                logits = model(
                    input_ids=ids,
                    attention_mask=attention,
                    use_cache=False,
                    logits_to_keep=positions,
                ).logits
                loss = selected_target_loss(logits, row["target_ids"], coefficient)
                require(bool(torch.isfinite(loss)), "training.finite_loss")
                loss.backward()
            value = float(loss.detach())
            total_loss += value
            package_nll[row["session_label"]] += value / float(Fraction(coefficient))
            package_tokens[row["session_label"]] += len(row["target_ids"])
            token_count += len(row["target_ids"])
            sequence_count += row["sequence_length"]
            del logits, loss, ids, attention, positions
            if position % 6 == 0:
                print(
                    "training",
                    variant,
                    "epoch",
                    epoch,
                    "rows",
                    position,
                    "/36",
                    "weighted_loss_sum",
                    round(total_loss, 6),
                    flush=True,
                )
        require(
            len(package_tokens) == 18 and sum(package_tokens.values()) == 4793,
            "training.complete_package_accumulation",
        )
        norm = torch.nn.utils.clip_grad_norm_(
            parameters, config["maximum_gradient_norm"], error_if_nonfinite=True
        )
        optimizer.step()
        item = record(
            "full_pass_update",
            variant=variant,
            epoch=epoch,
            optimizer_update=epoch,
            full_pass_weighted_loss=total_loss,
            gradient_norm_before_clipping=float(norm),
            package_mean_nll={
                label: package_nll[label] / package_tokens[label] for label in package_tokens
            },
            package_target_token_counts=dict(package_tokens),
            row_order=order,
            supervised_tokens_this_pass=4793,
            sequence_tokens_this_pass=232603,
            cumulative_supervised_tokens=token_count,
            cumulative_sequence_tokens=sequence_count,
            elapsed_seconds=time.perf_counter() - epoch_started,
            no_microbatch_mean_or_second_global_normalization=True,
        )
        store.json(f"updates/{epoch:02d}.json", item)
        records.append(item)
    require(
        token_count == config["supervised_tokens_per_run"]
        and sequence_count == config["sequence_tokens_per_run"]
        and len(records) == 10,
        "training.fixed_completed_budget",
    )
    optimizer.zero_grad(set_to_none=True)
    adapter = save_adapter(model, store.root / "adapter.safetensors")
    require(adapter["parameter_digest"] != initial_digest, "training.actual_parameter_update")
    report = record(
        "completed_student_training",
        variant=variant,
        seed=seed,
        arm=arm,
        identity_id=identity["id"],
        initial_adapter_parameter_sha256=initial_digest,
        final_adapter=adapter,
        optimizer_updates=10,
        full_passes=10,
        actual_supervised_tokens=token_count,
        actual_sequence_tokens=sequence_count,
        scope=scope,
        records=records,
        elapsed_seconds=time.perf_counter() - started,
        peak_GPU_allocated_bytes=torch.cuda.max_memory_allocated(),
        peak_GPU_reserved_bytes=torch.cuda.max_memory_reserved(),
        teacher_calls=0,
        evaluation_based_checkpoint_selection=False,
    )
    store.json("report.json", report)
    seal_directory(store, kind="pq_training_manifest", report_id=report["id"])
    del optimizer, parameters
    evaluation_identity = record(
        "evaluated_student_identity",
        variant=variant,
        checkpoint_binding_id=checkpoint["id"],
        training_report_id=report["id"],
        adapter=adapter,
    )
    evaluate_model(root, variant, model, evaluation_identity)
    return report


def run_baseline(root):
    prep = root / OUTPUT / "preparation"
    verify_source_snapshot(root, read_json(prep / "implementation.json"))
    checkpoint = read_json(prep / "checkpoint_binding.json")
    model, _ = load_student(checkpoint, 0, trainable=False)
    identity = record(
        "evaluated_student_identity",
        variant="B0",
        checkpoint_binding_id=checkpoint["id"],
        training_report_id=None,
        adapter=None,
        no_updates=True,
    )
    return evaluate_model(root, "B0", model, identity)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("baseline", "train"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--arm", choices=("P", "Q"))
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    forbidden = [args.root / OUTPUT / "preparation/private/evaluation_targets.json"]
    with offline_guard(forbidden) as counts:
        result = (
            run_baseline(args.root)
            if args.mode == "baseline"
            else run_training(args.root, args.arm, args.seed)
        )
        guard = guard_report(counts, phase=args.mode)
        variant = "B0" if args.mode == "baseline" else f"{args.arm}_{args.seed}"
        save(args.root / OUTPUT / "worker_guards", variant + ".json", guard)
        print("completed", result["id"], guard, flush=True)


if __name__ == "__main__":
    main()
