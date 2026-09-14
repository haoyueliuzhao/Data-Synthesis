"""Admitted fixed-kernel production training; unchanged physical Qwen baseline.

The input kernel must be rebuilt from the complete prospectively registered
outcomes and admitted by a separate release record before loading a Student.
Engineering-preflight models and optimizer states are never input arguments.
"""

import argparse
import os
from collections import Counter, defaultdict
from pathlib import Path
from types import FunctionType, SimpleNamespace

import torch

from ..finance_qa_vnext_basis_student.protocol import training_config as original_config
from ..finance_qa_vnext_pq_student import model as model_components
from ..finance_qa_vnext_pq_student.loss import selected_target_loss
from . import consumer, distribution, fast_materials, population
from . import protocol as p


def training_config():
    """Keep all baseline physical settings; replace only old material accounting."""
    previous = original_config()
    fields = {
        key: value
        for key, value in previous.items()
        if key
        not in {
            "id",
            "schema_version",
            "training_packages_per_task_method",
            "heldout_packages_per_task_method",
            "historical_18_or_21_package_administration_reused",
        }
    }
    fields.update(
        baseline_configuration_id=previous["id"],
        task_count=200,
        optimizer_updates=400,
        packages_per_update="all valid train originals for scheduled five tasks; variable",
        token_coefficient="pi(state|task)/(5*n_state*whole_package_target_tokens)",
        update="zero_grad once; all original packages of five tasks; clip once; step once",
        physical_order=(
            "frozen session-id package order restricted to the five scheduled tasks; "
            "original row order"
        ),
        full_supervision_domain="unchanged original public-response target masks",
        production_initialization=(
            "fresh base plus paired seeded LoRA; empty AdamW state; never engineering state"
        ),
        task_schedule="prospective fixed 200-task metadata population; ten visits each",
        admission=(
            "complete 10240 denominator; all 200 tasks supported in each pool; "
            "|S|>=60; separate release"
        ),
        interventions={
            "alpha0": {"endpoint": "1/2", "movement": "1/2"},
            "plus": {"endpoint": "1/3", "movement": "2/3"},
            "minus": {"endpoint": "2/3", "movement": "1/3"},
        },
        old_fixed_64_package_or_8_plus_2_administration=False,
        HierLoss_or_TF_global_scaling=False,
    )
    return p.record("training_configuration", **fields)


def load_registered_student(
    checkpoint_binding,
    seed,
    config=None,
    *,
    trainable=True,
    adapter_path=None,
    adapter_record=None,
):
    config = training_config() if config is None else config
    p.require(
        config == training_config() and seed in p.SEEDS,
        "training.registered_physical_configuration",
    )
    model, _ = model_components.load_student(checkpoint_binding, seed, trainable=False)
    scope = model_components.install_adapters(model, config=config)
    p.require(
        len(scope["target_module_names"]) == 2 * model.config.num_hidden_layers,
        "training.all_q_v_layers",
    )
    p.require(
        all(
            (
                name.endswith((".lora_A", ".lora_B"))
                and parameter.requires_grad
                and parameter.dtype == torch.float32
            )
            or (
                not name.endswith((".lora_A", ".lora_B"))
                and not parameter.requires_grad
                and parameter.dtype == torch.bfloat16
            )
            for name, parameter in model.named_parameters()
        ),
        "training.BF16_base_FP32_qv_adapters",
    )
    if adapter_path is not None:
        p.require(
            not trainable and adapter_record is not None,
            "training.final_adapter_restore_for_evaluation_only",
        )
        model_components.load_adapter(model, Path(adapter_path), adapter_record)
    if trainable:
        model.config.use_cache = False
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.train()
    else:
        model.requires_grad_(False)
        model.eval()
        model.config.use_cache = True
    return model, scope


def optimizer_factory(parameters, config):
    return torch.optim.AdamW(
        parameters,
        lr=config["learning_rate"],
        betas=tuple(config["betas"]),
        eps=config["eps"],
        weight_decay=config["weight_decay"],
    )


def validate_materials(kernel, selected_population, registry, outcomes, *, verified_inputs=None):
    """One full preflight; only a private byte/code-bound authority may reuse it."""
    if verified_inputs is None:
        p.checked(kernel, "fixed_kernel")
        expected = distribution.build_kernel(selected_population, registry, outcomes)
        p.require(kernel == expected, "training.kernel_exact_complete_registered_outcomes")
    else:
        fast_materials.assert_verified_inputs(
            verified_inputs, kernel, selected_population, registry, outcomes
        )
        verification = getattr(verified_inputs, "verification", None)
        if verification is not None:
            p.checked(verification, "material_input_verification")
            p.require(
                verification["kernel_id"] == kernel["id"]
                and verification["population_id"] == selected_population["id"]
                and verification["registry_id"] == registry["id"],
                "training.exact_preflight_verification_authority",
            )
            return verification
    p.require(
        kernel["training_gate"] == kernel["material_gate"] == kernel["dose_gate"] == "PASS",
        "training.material_and_dose_gates_required",
    )
    p.require(
        kernel["collection_complete"] is True and kernel["registered_session_count"] == 10240,
        "training.no_success_prefix",
    )
    budgets, rows = {}, {}
    tokenizer_ids = set()
    for pool in p.POOLS:
        selected = [item for item in kernel["train_packages"] if item["pool"] == pool]
        budget = dict(
            packages_per_epoch=len(selected),
            rows_per_epoch=0,
            target_tokens_per_epoch=0,
            sequence_tokens_per_epoch=0,
        )
        for item in selected:
            original = item["original_package"]
            p.checked(original, "encoded_original_package")
            p.require(
                item["state_id"]
                == distribution.canonical_state_id(
                    original["actual_method"], original["full_class"]
                ),
                "training.canonical_actual_full_class_binding",
            )
            p.require(
                p.sha(p.encode(original)) == item["original_package_sha256"],
                "training.original_encoded_package_identity",
            )
            p.require(
                original.get("original_request_response_bytes_retained") is True
                and original.get("truncation") is False
                and original.get("errors") == []
                and original.get("maximum_sequence_length") == 24576,
                "training.authentic_full_original_without_truncation",
            )
            token_id = original.get("tokenizer_binding_id")
            p.require(isinstance(token_id, str) and token_id, "training.bound_original_tokenizer")
            tokenizer_ids.add(token_id)
            representations = [consumer.validate_row(row) for row in original["rows"]]
            info = {
                "rows_sha256": p.sha(p.encode(original["rows"])),
                "rows": len(representations),
                "target_tokens": sum(row["target_token_count"] for row in representations),
                "sequence_tokens": sum(row["sequence_length"] for row in representations),
            }
            p.require(
                info["target_tokens"] == item["whole_package_target_tokens"],
                "training.complete_package_target_denominator",
            )
            rows[item["package_id"]] = info
            for field in ("rows", "target_tokens", "sequence_tokens"):
                budget[field + "_per_epoch"] += info[field]
        for field in ("packages", "rows", "target_tokens", "sequence_tokens"):
            budget[field + "_all_epochs"] = 10 * budget[field + "_per_epoch"]
        budgets[pool] = budget
    p.require(len(tokenizer_ids) == 1, "training.one_fixed_tokenizer_across_AB")
    return p.record(
        "material_input_verification",
        kernel_id=kernel["id"],
        population_id=selected_population["id"],
        registry_id=registry["id"],
        tokenizer_binding_id=next(iter(tokenizer_ids)),
        pool_budgets=budgets,
        package_rows=rows,
        fixed_tasks=200,
        training_retokenizations=0,
        all_valid_train_originals_retained=True,
        heldout_NLL_or_generation=False,
        model_loaded=False,
    )


def make_release(
    kernel, *, study_freeze_id, surface_manifest_id, allowed_runs, verified_inputs=None
):
    """Root orchestration calls this after independent material and stage gates.

    This is an explicit prospective run allowance, not a stage-selection routine;
    callers remain responsible for the registered A-dev selection before B.
    """
    if verified_inputs is None:
        p.checked(kernel, "fixed_kernel")
    else:
        p.require(
            fast_materials.checked_kernel(kernel) is kernel
            and fast_materials.owner_for(kernel) is verified_inputs,
            "training.exact_private_kernel_authority",
        )
    p.require(
        kernel["training_gate"] == kernel["material_gate"] == kernel["dose_gate"] == "PASS",
        "training.release_requires_both_gates",
    )
    p.require(
        isinstance(study_freeze_id, str)
        and study_freeze_id
        and isinstance(surface_manifest_id, str)
        and surface_manifest_id,
        "training.release_frozen_study_and_surfaces",
    )
    triples = [(run["pool"], run["arm"], run["seed"]) for run in allowed_runs]
    p.require(
        triples
        and len(set(triples)) == len(triples)
        and all(
            pool in p.POOLS and arm in p.ARMS and type(seed) is int and seed in p.SEEDS
            for pool, arm, seed in triples
        ),
        "training.release_unique_registered_runs",
    )
    return p.record(
        "training_release",
        status="ADMITTED",
        kernel_id=kernel["id"],
        population_id=kernel["population_id"],
        registry_id=kernel["registry_id"],
        training_configuration_id=training_config()["id"],
        study_freeze_id=study_freeze_id,
        surface_manifest_id=surface_manifest_id,
        allowed_runs=allowed_runs,
        material_gate="PASS",
        dose_gate="PASS",
        reuse_engineering_state=False,
    )


def validate_release(release, kernel, *, pool, arm, seed, verified_inputs=None):
    p.checked(release, "training_release")
    p.require(
        release
        == make_release(
            kernel,
            study_freeze_id=release["study_freeze_id"],
            surface_manifest_id=release["surface_manifest_id"],
            allowed_runs=release["allowed_runs"],
            verified_inputs=verified_inputs,
        ),
        "training.exact_release_and_current_configuration",
    )
    p.require(
        {"pool": pool, "arm": arm, "seed": seed} in release["allowed_runs"],
        "training.run_explicitly_released",
    )


def weighted_inputs(verified_inputs, pool, arm):
    """Original weighting bytecode over a privately verified immutable pool view.

    Only full-kernel identity and already verified canonical-package SHA checks
    use the minted authority. Formulae, physical order and mass checks execute
    unchanged. Frozen originals make the old deepcopy calls constant-time.
    """
    fast_materials.require_verified(verified_inputs)
    kernel = fast_materials.checked_kernel(verified_inputs["kernel"])

    def checked(value, kind):
        p.require(value is kernel and kind == "fixed_kernel", "training.private_pool_kernel")
        return value

    original_distribution = distribution.distribution
    assigned_function = FunctionType(
        original_distribution.__code__,
        {**original_distribution.__globals__, "_checked": checked},
        original_distribution.__name__,
        original_distribution.__defaults__,
        original_distribution.__closure__,
    )
    assigned = assigned_function(kernel, pool, arm)
    known = {
        id(item["original_package"]): (item["original_package"], item["original_package_sha256"])
        for item in kernel["train_packages"]
        if item["pool"] == pool
    }

    class CanonicalPackageSHA:
        def __init__(self, digest):
            self.digest = digest

    def encoded(value):
        saved = known.get(id(value))
        if saved is not None and saved[0] is value:
            return CanonicalPackageSHA(saved[1])
        return p.encode(value)

    def sha(value):
        return value.digest if isinstance(value, CanonicalPackageSHA) else p.sha(value)

    def same_distribution(value, wanted_pool, wanted_arm):
        p.require(
            value is kernel and (wanted_pool, wanted_arm) == (pool, arm),
            "training.same_verified_weighting_scope",
        )
        return assigned

    original_weighting = distribution.weighted_packages
    weighted_function = FunctionType(
        original_weighting.__code__,
        {
            **original_weighting.__globals__,
            "distribution": same_distribution,
            "p": SimpleNamespace(require=p.require, encode=encoded, sha=sha),
        },
        original_weighting.__name__,
        original_weighting.__defaults__,
        original_weighting.__closure__,
    )
    return weighted_function(kernel, pool, arm), assigned


def run(
    root,
    output,
    kernel,
    selected_population,
    registry,
    outcomes,
    checkpoint_binding,
    release,
    *,
    pool,
    arm,
    seed,
    model_loader=load_registered_student,
    optimizer_builder=optimizer_factory,
    loss_fn=selected_target_loss,
    verified_inputs=None,
):
    """400 paired updates and only the final adapter; failed runs never resume."""
    root, output = Path(root).resolve(), Path(output).resolve()
    p.require(
        output.is_relative_to(root) and output != root and not output.exists(),
        "training.exclusive_contained_output_no_retry",
    )
    p.require(
        pool in p.POOLS and arm in p.ARMS and type(seed) is int and seed in p.SEEDS,
        "training.registered_run",
    )
    output.mkdir(parents=True)
    p.write_once(
        output / "started.json",
        p.record(
            "training_started",
            time=p.now(),
            pool=pool,
            arm=arm,
            seed=seed,
            release_id=release.get("id"),
            automatic_retry=False,
        ),
    )
    updates, current_batch = [], None
    try:
        config = training_config()
        validate_release(
            release, kernel, pool=pool, arm=arm, seed=seed, verified_inputs=verified_inputs
        )
        verification = validate_materials(
            kernel, selected_population, registry, outcomes, verified_inputs=verified_inputs
        )
        schedule = population.batch_schedule(selected_population, seed)
        p.require(
            schedule["total_updates"] == 400 and len(schedule["batches"]) == 400,
            "training.exact_400_update_schedule",
        )
        p.write_once(output / "configuration.json", config)
        p.write_once(output / "material_verification.json", verification)
        p.write_once(output / "schedule.json", schedule)
        # Hash/validate the entire immutable kernel once, then retain the same
        # physical package rows in memory. Avoid re-hashing gigabytes 400 times.
        if verified_inputs is None:
            examples = distribution.weighted_packages(kernel, pool, arm)
            assigned = distribution.distribution(kernel, pool, arm)
        else:
            examples, assigned = weighted_inputs(verified_inputs, pool, arm)
        p.write_once(output / "distribution.json", assigned)
        by_task = defaultdict(list)
        for index, example in enumerate(examples):
            by_task[example["task_id"]].append((index, example))
        frozen_ids = [
            item["package_id"] for item in kernel["train_packages"] if item["pool"] == pool
        ]
        p.require(
            [item["package_id"] for item in examples] == frozen_ids,
            "training.all_original_packages_fixed_physical_order",
        )
        groups = {task["task_id"]: task["family"] for task in selected_population["tasks"]}
        model, scope = model_loader(checkpoint_binding, seed, config=config, trainable=True)
        parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
        p.require(
            parameters and all(parameter.dtype == torch.float32 for parameter in parameters),
            "training.FP32_trainables",
        )
        device = parameters[0].device
        p.require(
            all(parameter.device == device for parameter in parameters), "training.single_device"
        )
        optimizer = optimizer_builder(parameters, config)
        p.require(not optimizer.state, "training.fresh_empty_optimizer_no_engineering_resume")
        model.train()
        actual = (
            device.type == "cuda"
            and model_loader is load_registered_student
            and optimizer_builder is optimizer_factory
            and loss_fn is selected_target_loss
        )
        identity = p.record(
            "training_run_identity",
            pool=pool,
            arm=arm,
            seed=seed,
            kernel_id=kernel["id"],
            population_id=selected_population["id"],
            release_id=release["id"],
            training_configuration_id=config["id"],
            schedule_id=schedule["id"],
            distribution_id=assigned["id"],
            base_binding_id=checkpoint_binding["id"],
            tokenizer_binding_id=verification["tokenizer_binding_id"],
            scope=scope,
            initial_adapter_digest=model_components.adapter_digest(model),
            physical_originals_sha256=kernel["physical_originals_sha256"],
            execution_mode="local_CUDA" if actual else "synthetic_injected",
            device=str(device),
            fresh_initialization=True,
            unique_final_checkpoint=True,
            study_freeze_id=release["study_freeze_id"],
            surface_manifest_id=release["surface_manifest_id"],
        )
        p.write_once(output / "identity.json", identity)
        budget = verification["pool_budgets"][pool]
        epoch_seen, epoch_target, epoch_sequence, epoch_rows = Counter(), 0, 0, 0
        for raw_batch in schedule["batches"]:
            current_batch = raw_batch
            task_ids = raw_batch["task_ids"]
            batch = {
                **raw_batch,
                "tasks": [{"task_id": task, "group": groups[task]} for task in task_ids],
            }
            selected = [
                example
                for _, example in sorted(
                    [item for task in task_ids for item in by_task[task]], key=lambda item: item[0]
                )
            ]
            expected = [
                item["package_id"]
                for item in kernel["train_packages"]
                if item["pool"] == pool and item["task_id"] in set(task_ids)
            ]
            metadata = consumer.validate_update(
                selected, batch, pool=pool, arm=arm, expected_package_ids=expected
            )
            for item in metadata:
                original = verification["package_rows"][item["package_id"]]
                p.require(
                    item["original_rows_sha256"] == original["rows_sha256"]
                    and item["whole_package_target_tokens"] == original["target_tokens"],
                    "training.immutable_full_original_response_rows",
                )
            directory = output / "updates" / f"{raw_batch['step'] + 1:04d}"
            p.write_once(
                directory / "started.json",
                p.record(
                    "optimizer_update_started",
                    time=p.now(),
                    batch=batch,
                    expected_package_ids=expected,
                    pool=pool,
                    arm=arm,
                ),
            )
            with (directory / "events.jsonl").open("xb") as stream:

                def persist(event, update_index=raw_batch["step"] + 1):
                    value = p.record(
                        "optimizer_update_event",
                        time=p.now(),
                        optimizer_update=update_index,
                        **event,
                    )
                    stream.write(p.encode(value) + b"\n")
                    stream.flush()
                    os.fsync(stream.fileno())

                result = consumer.execute_update(
                    model,
                    optimizer,
                    selected,
                    batch,
                    pool=pool,
                    arm=arm,
                    device=device,
                    loss_fn=loss_fn,
                    event_sink=persist,
                    expected_package_ids=expected,
                )
            p.write_once(directory / "report.json", result)
            updates.append(
                {
                    "id": result["id"],
                    "path": str((directory / "report.json").relative_to(root)),
                    "sha256": p.sha(directory / "report.json"),
                    "target_tokens": result["target_tokens"],
                    "sequence_tokens": result["sequence_tokens"],
                    "rows": result["rows_completed"],
                    "packages": result["packages_completed"],
                }
            )
            epoch_seen.update(expected)
            epoch_target += result["target_tokens"]
            epoch_sequence += result["sequence_tokens"]
            epoch_rows += result["rows_completed"]
            if (raw_batch["step"] + 1) % 40 == 0:
                p.require(
                    epoch_seen == Counter(dict.fromkeys(frozen_ids, 1))
                    and epoch_target == budget["target_tokens_per_epoch"]
                    and epoch_sequence == budget["sequence_tokens_per_epoch"]
                    and epoch_rows == budget["rows_per_epoch"],
                    "training.exact_original_package_token_budget_each_epoch",
                )
                p.write_once(
                    output / "epochs" / f"{raw_batch['epoch'] + 1:02d}.json",
                    p.record(
                        "epoch_complete",
                        epoch=raw_batch["epoch"] + 1,
                        packages=len(epoch_seen),
                        target_tokens=epoch_target,
                        sequence_tokens=epoch_sequence,
                        rows=epoch_rows,
                    ),
                )
                epoch_seen, epoch_target, epoch_sequence, epoch_rows = Counter(), 0, 0, 0
        p.require(
            len(updates) == 400
            and all(
                sum(item[field] for item in updates) == budget[field + "_all_epochs"]
                for field in ("packages", "rows", "target_tokens", "sequence_tokens")
            ),
            "training.complete_400_update_ten_pass_accounting",
        )
        adapter_path = output / "final_adapter.safetensors"
        adapter = model_components.save_adapter(model, adapter_path)
        with adapter_path.open("rb") as stream:
            os.fsync(stream.fileno())
        model_components.load_adapter(model, adapter_path, adapter)
        model.requires_grad_(False)
        model.eval()
        report = p.record(
            "training_report",
            status="COMPLETE_FINAL_CHECKPOINT" if actual else "COMPLETE_SYNTHETIC_CHECKPOINT",
            actual_complete=actual,
            pool=pool,
            arm=arm,
            seed=seed,
            kernel_id=kernel["id"],
            release_id=release["id"],
            identity_id=identity["id"],
            training_configuration_id=config["id"],
            final_adapter=adapter,
            checkpoint_id=adapter["parameter_digest"],
            adapter_directory=str(output.relative_to(root)),
            initial_adapter_digest=identity["initial_adapter_digest"],
            base_binding_id=checkpoint_binding["id"],
            tokenizer_binding_id=verification["tokenizer_binding_id"],
            final_adapter_restored_identity_verified=True,
            optimizer_updates=400,
            epochs_completed=10,
            physical_originals_sha256=kernel["physical_originals_sha256"],
            actual_budget=budget,
            material_verification_id=verification["id"],
            schedule_id=schedule["id"],
            updates=updates,
            training_retokenizations=0,
            intermediate_checkpoints=0,
            automatic_retries=0,
            finish_time=p.now(),
            execution_mode=identity["execution_mode"],
            study_freeze_id=release["study_freeze_id"],
            surface_manifest_id=release["surface_manifest_id"],
        )
        p.write_once(output / "report.json", report)
        return report
    except BaseException as error:
        p.write_once(
            output / "failure.json",
            p.record(
                "training_failure",
                time=p.now(),
                error_type=type(error).__name__,
                error=str(error),
                pool=pool,
                arm=arm,
                seed=seed,
                current_batch=current_batch,
                completed_updates=updates,
                actual_complete=False,
                failed_run_retained=True,
                automatic_retry=False,
            ),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in (
        "root",
        "output",
        "kernel",
        "population",
        "registry",
        "outcomes",
        "checkpoint-binding",
        "release",
    ):
        parser.add_argument("--" + argument, required=True)
    parser.add_argument("--pool", choices=p.POOLS, required=True)
    parser.add_argument("--arm", choices=p.ARMS, required=True)
    parser.add_argument("--seed", choices=p.SEEDS, type=int, required=True)
    args = parser.parse_args()
    run(
        args.root,
        args.output,
        p.read_json(args.kernel),
        p.read_json(args.population),
        p.read_json(args.registry),
        p.read_json(args.outcomes),
        p.read_json(args.checkpoint_binding),
        p.read_json(args.release),
        pool=args.pool,
        arm=args.arm,
        seed=args.seed,
    )
