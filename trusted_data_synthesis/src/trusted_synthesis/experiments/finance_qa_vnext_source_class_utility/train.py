"""Nine fixed full-pass runs and, only if selected, confirmation from saved adapters."""

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
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.guards import (
    offline_guard,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.guards import (
    report as guard_report,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.loss import selected_target_loss
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.model import (
    adapter_digest,
    load_student,
    save_adapter,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import save

from .inference import evaluate_model
from .plan import (
    CONDITIONS,
    OUTPUT,
    PANEL_SOURCE,
    SEEDS,
    evaluation_config,
    read_json,
    record,
    require,
    sha,
    training_config,
)
from .weights import load_rows


def row_orders(seed, count):
    generator, result = random.Random(seed), []
    for _ in range(10):
        order = list(range(count))
        generator.shuffle(order)
        result.append(order)
    return result


def verify_preparation(root):
    prep = root / OUTPUT / "preparation"
    verify_source_snapshot(root, read_json(prep / "implementation.json"))
    view = read_json(root / OUTPUT / "materialization/weight_view.json")
    config = read_json(prep / "training_configuration.json")
    require(config == training_config(view["totals"]), "training.actual_frozen_token_budget")
    require(
        read_json(prep / "evaluation_configuration.json") == evaluation_config(),
        "training.evaluation_policy_frozen_before_training",
    )
    binding = read_json(prep / "inputs.json")
    require(binding["weight_view_id"] == view["id"], "training.frozen_physical_input")
    return prep, view, config


def run_training(root, arm, seed):
    require(arm in CONDITIONS and seed in SEEDS, "training.nine_registered_runs")
    prep, view, config = verify_preparation(root)
    variant = f"{arm}_{seed}"
    directory = root / OUTPUT / "training" / variant
    require(not directory.exists(), "training.no_retry_or_overwrite")
    rows = load_rows(root, view)
    totals = view["totals"]
    require(
        len(rows) == totals["rows"]
        and sum(len(r["target_ids"]) for r in rows) == totals["target_tokens_per_pass"]
        and sum(r["sequence_length"] for r in rows) == totals["sequence_tokens_per_pass"],
        "training.identical_complete_physical_data",
    )
    store = DurableStore(directory)
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
        physical_row_reference_sha256=view["physical_row_reference_sha256"],
    )
    store.json("identity.json", identity)
    started, token_count, sequence_count, records = time.perf_counter(), 0, 0, []
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
            if position % 10 == 0:
                print(
                    "training",
                    variant,
                    "epoch",
                    epoch,
                    "rows",
                    position,
                    "/",
                    len(rows),
                    flush=True,
                )
        require(
            len(package_tokens) == 21
            and sum(package_tokens.values()) == totals["target_tokens_per_pass"],
            "training.complete_21_package_accumulation",
        )
        norm = torch.nn.utils.clip_grad_norm_(
            parameters,
            config["maximum_gradient_norm"],
            error_if_nonfinite=True,
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
            supervised_tokens_this_pass=totals["target_tokens_per_pass"],
            sequence_tokens_this_pass=totals["sequence_tokens_per_pass"],
            cumulative_supervised_tokens=token_count,
            cumulative_sequence_tokens=sequence_count,
            elapsed_seconds=time.perf_counter() - epoch_started,
            no_microbatch_mean_or_second_global_normalization=True,
            training_objective_accounting_not_auxiliary_NLL_evaluation=True,
        )
        store.json(f"updates/{epoch:02d}.json", item)
        records.append(item)
        print("training", variant, "update", epoch, "completed", flush=True)
    require(
        token_count == config["supervised_tokens_per_run"]
        and sequence_count == config["sequence_tokens_per_run"]
        and len(records) == 10,
        "training.exact_completed_budget",
    )
    optimizer.zero_grad(set_to_none=True)
    adapter = save_adapter(model, directory / "adapter.safetensors")
    require(adapter["parameter_digest"] != initial_digest, "training.actual_parameter_update")
    report = record(
        "completed_student_training",
        variant=variant,
        arm=arm,
        seed=seed,
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
        Teacher_requests=0,
        evaluation_based_checkpoint_selection=False,
    )
    store.json("report.json", report)
    seal_directory(store, kind="source_class_training_manifest", report_id=report["id"])
    del optimizer, parameters
    identity = record(
        "evaluated_student_identity",
        variant=variant,
        checkpoint_binding_id=checkpoint["id"],
        training_report_id=report["id"],
        adapter=adapter,
        phase="dev",
    )
    evaluate_model(root, variant, model, identity, "dev")
    return report


def run_confirmation(root, arm, seed):
    require(arm in CONDITIONS and seed in SEEDS, "confirm.registered_run")
    prep, _, _ = verify_preparation(root)
    variant = f"{arm}_{seed}"
    authorization = read_json(root / OUTPUT / "selection/confirmation_authorization.json")
    require(variant in authorization["variants"], "confirm.sealed_candidate_and_baseline_only")
    training = read_json(root / OUTPUT / f"training/{variant}/report.json")
    require(
        training["id"] == authorization["training_report_ids"][variant],
        "confirm.exact_final_checkpoint",
    )
    checkpoint = read_json(prep / "checkpoint_binding.json")
    model, _ = load_student(
        checkpoint,
        seed,
        trainable=False,
        adapter_path=root / OUTPUT / f"training/{variant}/adapter.safetensors",
        adapter_record=training["final_adapter"],
    )
    identity = record(
        "evaluated_student_identity",
        variant=variant,
        checkpoint_binding_id=checkpoint["id"],
        training_report_id=training["id"],
        adapter=training["final_adapter"],
        phase="confirm",
    )
    return evaluate_model(root, variant, model, identity, "confirm")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("train", "confirm"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--arm", choices=CONDITIONS, required=True)
    parser.add_argument("--seed", type=int, choices=SEEDS, required=True)
    args = parser.parse_args()
    forbidden = [
        args.root / OUTPUT / "preparation/private/evaluation_targets.json",
        args.root / PANEL_SOURCE / "preparation/private/evaluation_targets.json",
        args.root / OUTPUT / "preparation/private/dev_review_identity_map.json",
        args.root / OUTPUT / "selection/private/confirm_review_identity_map.json",
    ]
    with offline_guard(forbidden) as counts:
        result = (run_training if args.mode == "train" else run_confirmation)(
            args.root, args.arm, args.seed
        )
        guard = guard_report(counts, phase="source_class_" + args.mode)
        save(
            args.root / OUTPUT / "worker_guards", f"{args.mode}_{args.arm}_{args.seed}.json", guard
        )
        print("completed", args.mode, args.arm, args.seed, result["id"], flush=True)


if __name__ == "__main__":
    main()
