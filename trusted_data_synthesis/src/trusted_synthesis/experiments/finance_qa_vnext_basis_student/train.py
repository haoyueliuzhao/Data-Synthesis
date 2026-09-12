"""New full-population driver; original-material consumer and unique final adapter.

All physical work is behind ``run``/``load_registered_student``. Imports do not
load weights, a tokenizer, or initialize CUDA. Failed runs cannot be overwritten.
"""

import os
from collections import Counter, defaultdict
from pathlib import Path

import torch

from ..finance_qa_vnext_basis_scale_preparation import design
from ..finance_qa_vnext_eval_readiness import materials
from ..finance_qa_vnext_pq_student import model as model_components
from ..finance_qa_vnext_pq_student.loss import selected_target_loss
from . import kernel
from .protocol import (
    BINDING_FIELDS,
    encode,
    now,
    path_within,
    read_json,
    record,
    require,
    sha,
    training_config,
    write_once,
)


def load_registered_student(
    checkpoint_binding, seed, config=None, *, trainable, adapter_path=None, adapter_record=None
):
    """Reuse the physical loader, explicitly installing this study's q/v scope."""
    config = training_config() if config is None else config
    require(config == training_config() and seed in design.SEEDS, "training.new_configuration")
    model, _ = model_components.load_student(checkpoint_binding, seed, trainable=False)
    scope = model_components.install_adapters(model, config=config)
    require(
        len(scope["target_module_names"]) == 2 * model.config.num_hidden_layers,
        "training.all_q_v_layers",
    )
    require(
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
        "training.frozen_BF16_base_FP32_adapters",
    )
    if adapter_path is not None:
        require(adapter_record is not None, "training.final_adapter_binding_required")
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


def validate_materials(root, manifest):
    """Verify READY population, complete two-pool 8/2 strata and every bound row.

    No re-tokenization and no loss/generation on heldout data occurs here. The
    collection's authentication/qualification authority is the sealed manifest;
    this validates the concrete representations and denominators it selected.
    """
    root = Path(root).resolve()
    materials.checked_record(manifest, "fixed_AB_material_manifest")
    require(
        manifest["status"] == "FIXED_AB_MATERIALS_READY"
        and manifest["collection_complete"] is True
        and manifest["all_original_registered_denominators"] == 24640
        and manifest["policy_id"] == materials.policy()["id"]
        and manifest["loss_rule"] == "alpha(method|task)/(40*whole_package_target_tokens)",
        "training.complete_fixed_material_manifest",
    )
    selection = manifest["population_selection"]
    require(
        selection == design.choose_population(selection["ready_lists"])
        and selection["status"] == "PROSPECTIVE_POPULATION_SELECTED",
        "training.frozen_common_population_180_to_200",
    )
    token_binding = manifest["tokenizer_binding"]
    require(token_binding["maximum_sequence_length"] == 24576, "training.original_tokenizer_24576")
    readiness = manifest["common_AB_readiness"]
    require(
        [row["task_id"] for row in readiness] == manifest["source_task_order"]
        and len(set(manifest["source_task_order"])) == len(readiness),
        "training.original_catalog_readiness_order",
    )
    ready = {group: [] for group in design.GROUPS}
    for row in readiness:
        group = row["group"]
        require(group in design.GROUPS, "training.registered_readiness_group")
        methods = ("control",) if group == "control" else design.METHODS
        counts = row["counts_by_pool_actual_method"]
        require(
            set(counts) == set(design.POOLS)
            and all(set(counts[pool]) == set(methods) for pool in design.POOLS)
            and all(
                type(value) is int and value >= 0
                for pool in counts.values()
                for value in pool.values()
            ),
            "training.exact_readiness_strata",
        )
        common = all(value >= 10 for pool in counts.values() for value in pool.values())
        require(row["common_AB_ready"] is common, "training.true_common_AB_readiness")
        if common:
            ready[group].append(row["task_id"])
    require(ready == selection["ready_lists"], "training.original_ready_population_no_ranking")
    task_groups = {row["task_id"]: row["group"] for row in selection["selected"]}
    expected_strata = {
        (pool, task["task_id"], method)
        for task in selection["selected"]
        for pool in design.POOLS
        for method in (("control",) if task["group"] == "control" else design.METHODS)
    }
    strata, ids, sessions, package_rows = defaultdict(list), set(), set(), {}
    budgets = {
        pool: {
            "training_packages": 0,
            "heldout_packages": 0,
            "rows_per_epoch": 0,
            "target_tokens_per_epoch": 0,
            "sequence_tokens_per_epoch": 0,
        }
        for pool in design.POOLS
    }
    for descriptor in manifest["packages"]:
        key = descriptor["pool"], descriptor["task_id"], descriptor["actual_method"]
        require(
            key in expected_strata and descriptor["group"] == task_groups[key[1]],
            "training.no_foreign_pool_task_method",
        )
        require(
            descriptor["id"] not in ids and descriptor["registered_session_id"] not in sessions,
            "training.unique_original_packages_and_sessions",
        )
        ids.add(descriptor["id"])
        sessions.add(descriptor["registered_session_id"])
        strata[key].append(descriptor)
        path = path_within(root, descriptor["path"])
        require(sha(path) == descriptor["sha256"], "training.original_encoded_package_bytes")
        package = read_json(path)
        materials.checked_record(package, "encoded_original_package")
        require(
            all(
                package[field] == descriptor[field]
                for field in (
                    "id",
                    "registered_session_id",
                    "task_id",
                    "pool",
                    "group",
                    "actual_method",
                    "whole_package_target_tokens",
                )
            )
            and descriptor["consumable"] is True
            and package["consumable"] is True
            and package["errors"] == []
            and package["maximum_sequence_length"] == 24576
            and package["tokenizer_binding_id"] == token_binding["id"]
            and package["original_request_response_bytes_retained"] is True
            and package["truncation"] is False,
            "training.whole_original_consumable_package",
        )
        require(package["rows"], "training.nonempty_original_package")
        rows = [kernel.validate_row(row) for row in package["rows"]]
        require(
            sum(row["target_token_count"] for row in rows)
            == package["whole_package_target_tokens"],
            "training.true_package_denominator",
        )
        package_rows[package["id"]] = {
            "rows_sha256": sha(encode(package["rows"])),
            "rows": len(rows),
            "target_tokens": package["whole_package_target_tokens"],
            "sequence_tokens": sum(row["sequence_length"] for row in rows),
        }
        require(descriptor["role"] in {"train", "heldout"}, "training.registered_package_role")
        budget = budgets[key[0]]
        budget["training_packages" if descriptor["role"] == "train" else "heldout_packages"] += 1
        if descriptor["role"] == "train":
            budget["rows_per_epoch"] += len(rows)
            budget["target_tokens_per_epoch"] += package["whole_package_target_tokens"]
            budget["sequence_tokens_per_epoch"] += package_rows[package["id"]]["sequence_tokens"]
    require(set(strata) == expected_strata, "training.all_AB_selected_strata_present")
    for descriptors in strata.values():
        require(
            len(descriptors) == 10
            and [row["within_stratum_index"] for row in descriptors] == list(range(10))
            and [row["role"] for row in descriptors] == ["train"] * 8 + ["heldout"] * 2,
            "training.original_eight_train_two_heldout_order",
        )
    for budget in budgets.values():
        require(
            budget["training_packages"] == 64 * selection["tasks"] // 5
            and budget["heldout_packages"] == 16 * selection["tasks"] // 5,
            "training.population_package_denominators",
        )
        for kind in ("rows", "target_tokens", "sequence_tokens"):
            budget[kind + "_all_epochs"] = 10 * budget[kind + "_per_epoch"]
    return record(
        "material_input_verification",
        materials_manifest_id=manifest["id"],
        population_selection_id=selection["id"],
        tasks=selection["tasks"],
        pool_budgets=budgets,
        package_rows=package_rows,
        validated_packages=len(ids),
        tokenizer_loads=0,
        retokenization=False,
        heldout_NLL_or_generation=False,
    )


def _expected_packages(manifest, batch, pool):
    return [
        descriptor["id"]
        for task in batch["tasks"]
        for method in (("control",) if task["group"] == "control" else design.METHODS)
        for descriptor in manifest["packages"]
        if descriptor["pool"] == pool
        and descriptor["task_id"] == task["task_id"]
        and descriptor["actual_method"] == method
        and descriptor["role"] == "train"
    ]


def _optimizer(parameters, config):
    return torch.optim.AdamW(
        parameters,
        lr=config["learning_rate"],
        betas=tuple(config["betas"]),
        eps=config["eps"],
        weight_decay=config["weight_decay"],
    )


def run(
    root,
    output,
    manifest,
    checkpoint_binding,
    *,
    pool,
    arm,
    seed,
    binding,
    model_loader=load_registered_student,
    example_loader=materials.update_examples,
    loss_fn=selected_target_loss,
    optimizer_factory=None,
):
    """Run the registered ten-pass schedule, or retain failure and raise once.

    The caller must first verify/seal the study freeze and manifest file. This
    function binds the exact content identities and verifies every package SHA.
    Injected CPU models exercise this same schedule and original consumer without
    invoking any real assets; reports mark that execution mode explicitly.
    """
    root, output = Path(root).resolve(), Path(output).resolve()
    require(
        output.is_relative_to(root) and output != root and not output.exists(),
        "training.new_contained_run_output_no_retry",
    )
    output.mkdir(parents=True)
    write_once(
        output / "started.json",
        record(
            "training_started",
            time=now(),
            pool=pool,
            arm=arm,
            seed=seed,
            binding=binding,
            automatic_retry=False,
        ),
    )
    updates, model, current_batch = [], None, None
    try:
        config = training_config()
        require(
            pool in design.POOLS
            and arm in design.ARMS
            and type(seed) is int
            and seed in design.SEEDS,
            "training.registered_run",
        )
        require(
            set(binding) == set(BINDING_FIELDS)
            and all(isinstance(value, str) and value for value in binding.values())
            and binding["materials_manifest_id"] == manifest["id"]
            and binding["training_config_id"] == config["id"],
            "training.exact_five_bindings",
        )
        verification = validate_materials(root, manifest)
        write_once(output / "material_verification.json", verification)
        schedule = design.task_batches(manifest["population_selection"], seed)
        write_once(output / "schedule.json", schedule)
        write_once(output / "configuration.json", config)
        model, scope = model_loader(checkpoint_binding, seed, config=config, trainable=True)
        parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
        require(
            parameters and all(parameter.dtype == torch.float32 for parameter in parameters),
            "training.actual_FP32_trainables",
        )
        device = parameters[0].device
        require(
            all(parameter.device == device for parameter in parameters),
            "training.single_model_device",
        )
        model.train()
        optimizer = (optimizer_factory or _optimizer)(parameters, config)
        require(not optimizer.state, "training.empty_optimizer_state_no_resume")
        identity = record(
            "training_run_identity",
            pool=pool,
            arm=arm,
            seed=seed,
            base_binding_id=checkpoint_binding["id"],
            tokenizer_binding_id=manifest["tokenizer_binding"]["id"],
            schedule_id=schedule["id"],
            scope=scope,
            initial_adapter_digest=model_components.adapter_digest(model),
            execution_mode=(
                "local_CUDA"
                if device.type == "cuda"
                and model_loader is load_registered_student
                and example_loader is materials.update_examples
                and loss_fn is selected_target_loss
                and optimizer_factory is None
                else "synthetic_injected"
            ),
            device=str(device),
            unique_final_checkpoint=True,
            **binding,
        )
        write_once(output / "identity.json", identity)
        expected_train = {
            row["id"]
            for row in manifest["packages"]
            if row["pool"] == pool and row["role"] == "train"
        }
        epoch_seen, epoch_target, epoch_sequence = Counter(), 0, 0
        budget = verification["pool_budgets"][pool]
        for batch in schedule["batches"]:
            current_batch = batch
            expected = _expected_packages(manifest, batch, pool)
            directory = output / "updates" / f"{batch['optimizer_update']:04d}"
            write_once(
                directory / "started.json",
                record(
                    "optimizer_update_started",
                    time=now(),
                    batch=batch,
                    expected_package_ids=expected,
                    pool=pool,
                    arm=arm,
                ),
            )
            examples = example_loader(root, manifest, batch, pool=pool, arm=arm)
            metadata = kernel.validate_update(
                examples, batch, pool=pool, arm=arm, expected_package_ids=expected
            )
            for package in metadata:
                original = verification["package_rows"][package["package_id"]]
                require(
                    package["original_rows_sha256"] == original["rows_sha256"]
                    and package["whole_package_target_tokens"] == original["target_tokens"],
                    "training.exact_preflight_original_rows_no_reencoding",
                )
            with (directory / "events.jsonl").open("xb") as stream:
                event_index = 0

                def persist(event, update_index=batch["optimizer_update"]):
                    nonlocal event_index
                    event_index += 1
                    value = record(
                        "optimizer_update_event",
                        index=event_index,
                        time=now(),
                        optimizer_update=update_index,
                        **event,
                    )
                    stream.write(encode(value) + b"\n")
                    stream.flush()
                    os.fsync(stream.fileno())

                result = kernel.execute_update(
                    model,
                    optimizer,
                    examples,
                    batch,
                    pool=pool,
                    arm=arm,
                    device=device,
                    loss_fn=loss_fn,
                    event_sink=persist,
                    expected_package_ids=expected,
                )
            write_once(directory / "report.json", result)
            updates.append(
                {
                    "id": result["id"],
                    "path": str((directory / "report.json").relative_to(root)),
                    "sha256": sha(directory / "report.json"),
                    "target_tokens": result["target_tokens"],
                    "sequence_tokens": result["sequence_tokens"],
                    "rows": result["rows_completed"],
                }
            )
            epoch_seen.update(expected)
            epoch_target += result["target_tokens"]
            epoch_sequence += result["sequence_tokens"]
            if batch["batch_within_epoch"] == schedule["updates_per_epoch"]:
                require(
                    epoch_seen == Counter(dict.fromkeys(expected_train, 1))
                    and epoch_target == budget["target_tokens_per_epoch"]
                    and epoch_sequence == budget["sequence_tokens_per_epoch"],
                    "training.each_epoch_exact_all_selected_original_train_packages",
                )
                write_once(
                    output / "epochs" / f"{batch['epoch']:02d}.json",
                    record(
                        "epoch_complete",
                        epoch=batch["epoch"],
                        package_count=len(epoch_seen),
                        target_tokens=epoch_target,
                        sequence_tokens=epoch_sequence,
                    ),
                )
                epoch_seen, epoch_target, epoch_sequence = Counter(), 0, 0
        require(
            len(updates)
            == 10 * manifest["population_selection"]["tasks"] // 5
            == schedule["optimizer_updates"]
            and sum(row["target_tokens"] for row in updates) == budget["target_tokens_all_epochs"]
            and sum(row["sequence_tokens"] for row in updates)
            == budget["sequence_tokens_all_epochs"]
            and sum(row["rows"] for row in updates) == budget["rows_all_epochs"],
            "training.actual_complete_ten_pass_token_and_update_budget",
        )
        adapter_path = output / "final_adapter.safetensors"
        adapter = model_components.save_adapter(model, adapter_path)
        with adapter_path.open("rb") as stream:
            os.fsync(stream.fileno())
        model_components.load_adapter(model, adapter_path, adapter)
        model.requires_grad_(False)
        model.eval()
        actual = identity["execution_mode"] == "local_CUDA"
        result = record(
            "training_report",
            status=("COMPLETE_FINAL_CHECKPOINT" if actual else "COMPLETE_SYNTHETIC_CHECKPOINT"),
            actual_complete=actual,
            pool=pool,
            arm=arm,
            seed=seed,
            checkpoint_id=adapter["parameter_digest"],
            adapter_directory=str(output.relative_to(root)),
            final_adapter=adapter,
            final_adapter_restored_identity_verified=True,
            training_identity_id=identity["id"],
            base_binding_id=checkpoint_binding["id"],
            tokenizer_binding_id=manifest["tokenizer_binding"]["id"],
            execution_mode=identity["execution_mode"],
            schedule_id=schedule["id"],
            initial_adapter_digest=identity["initial_adapter_digest"],
            material_verification_id=verification["id"],
            optimizer_updates=len(updates),
            target_tokens=sum(row["target_tokens"] for row in updates),
            sequence_tokens=sum(row["sequence_tokens"] for row in updates),
            epochs_completed=10,
            actual_budget=budget,
            updates=updates,
            intermediate_checkpoints=0,
            automatic_retries=0,
            training_retokenizations=0,
            finish_time=now(),
            **binding,
        )
        write_once(output / "report.json", result)
        return result
    except BaseException as error:
        write_once(
            output / "failure.json",
            record(
                "training_failure",
                time=now(),
                error_type=type(error).__name__,
                error=str(error),
                pool=pool,
                arm=arm,
                seed=seed,
                binding=binding,
                current_batch=current_batch,
                completed_updates=updates,
                actual_complete=False,
                failed_run_retained=True,
                automatic_retry=False,
            ),
        )
        raise
