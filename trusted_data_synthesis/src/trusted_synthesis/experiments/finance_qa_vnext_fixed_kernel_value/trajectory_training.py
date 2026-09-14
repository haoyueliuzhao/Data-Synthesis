"""Successor execution: prefix-union trajectories, unchanged registered dose.

Fresh paired LoRA/AdamW initialization is required; paused response-row states
are never resumed. The parent's byte-bound material authority is retained and
its frozen implementation files are deliberately not edited.
"""

import os
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from types import FunctionType

import torch

from . import distribution, fast_materials, population
from . import protocol as p
from . import training as original
from . import trajectory_consumer as consumer
from . import trajectory_materials

model_components = original.model_components
optimizer_factory = original.optimizer_factory
selected_target_loss = consumer.selected_target_loss
EXECUTION_DESIGN = "trajectory_prefix_union_v1"


def training_config():
    previous = original.training_config()
    fields = {key: value for key, value in previous.items() if key not in {"id", "schema_version"}}
    fields.update(
        parent_training_configuration_id=previous["id"],
        execution_design=EXECUTION_DESIGN,
        representation=(
            "one longest original causal sequence plus union of every original response target "
            "per exact-prefix package; unchanged original rows on nonprefix packages"
        ),
        physical_order="frozen session-id package order restricted to scheduled tasks; prefix union",
        per_pool_token_budget=(
            "ten times cache forward-segment sequence tokens; original packages and targets unchanged"
        ),
        source_material_budget="retained separately; never relabel original token cost as executed",
        validation=(
            "original file bytes and exact prefix/targets verified once when cache is made; "
            "cache arrays verified once on worker load; no per-update material validation"
        ),
        event_durability="buffered package events; flush+fsync once per optimizer update",
        dropout_probability_unchanged=True,
        dropout_rng_correlation_change=(
            "shared causal prefix uses one dropout realization within each package; "
            "this execution is not bitwise-equivalent to separate response-row forwards"
        ),
        deterministic_no_dropout_objective_equivalence=True,
        resume_paused_response_row_optimizer=False,
    )
    return p.record("training_configuration", **fields)


def load_registered_student(
    checkpoint_binding, seed, config=None, *, trainable=True, adapter_path=None, adapter_record=None
):
    p.require(
        config is None or config == training_config(), "trajectory_training.registered_configuration"
    )
    return original.load_registered_student(
        checkpoint_binding,
        seed,
        config=original.training_config(),
        trainable=trainable,
        adapter_path=adapter_path,
        adapter_record=adapter_record,
    )


def make_release(kernel, *, study_freeze_id, surface_manifest_id, allowed_runs, verified_inputs=None):
    release = original.make_release(
        kernel,
        study_freeze_id=study_freeze_id,
        surface_manifest_id=surface_manifest_id,
        allowed_runs=allowed_runs,
        verified_inputs=verified_inputs,
    )
    fields = {key: value for key, value in release.items() if key not in {"id", "schema_version"}}
    fields["training_configuration_id"] = training_config()["id"]
    fields["execution_design"] = EXECUTION_DESIGN
    return p.record("training_release", **fields)


def validate_release(release, kernel, *, pool, arm, seed, verified_inputs=None):
    p.checked(release, "training_release")
    p.require(
        release == make_release(
            kernel,
            study_freeze_id=release["study_freeze_id"],
            surface_manifest_id=release["surface_manifest_id"],
            allowed_runs=release["allowed_runs"],
            verified_inputs=verified_inputs,
        ),
        "trajectory_training.exact_release_and_configuration",
    )
    p.require(
        {"pool": pool, "arm": arm, "seed": seed} in release["allowed_runs"],
        "trajectory_training.run_explicitly_released",
    )


def validate_materials(kernel, selected_population, registry, outcomes, *, verified_inputs=None):
    p.require(verified_inputs is not None, "trajectory_training.parent_material_authority_required")
    return original.validate_materials(
        kernel, selected_population, registry, outcomes, verified_inputs=verified_inputs
    )


def weighted_inputs(verified_inputs, pool, arm, trajectory_cache):
    """One startup inventory/weight binding; original distribution bytecode.

    Only its full-kernel content check is replaced by the privately minted
    authority. The original state-count, intervention and rational math run as-is.
    """
    fast_materials.require_verified(verified_inputs)
    trajectory_materials.require_pool(trajectory_cache)
    kernel = verified_inputs["kernel"]
    p.require(
        trajectory_cache.kernel_id == kernel["id"]
        and trajectory_cache.material_verification_id == verified_inputs.verification["id"]
        and trajectory_cache.source_material_budget == verified_inputs.verification["pool_budgets"][pool],
        "trajectory_training.cache_bound_to_original_materials",
    )

    def checked(value, kind):
        p.require(value is kernel and kind == "fixed_kernel", "trajectory_training.private_kernel")
        return value

    function = distribution.distribution
    assigned = FunctionType(
        function.__code__,
        {**function.__globals__, "_checked": checked},
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )(kernel, pool, arm)
    states = {(item["task_id"], item["state_id"]): item for item in assigned["states"]}
    headers = [item for item in kernel["train_packages"] if item["pool"] == pool]
    cached = trajectory_cache.packages
    p.require(
        [item["package_id"] for item in cached] == [item["package_id"] for item in headers],
        "trajectory_training.exact_original_package_order",
    )
    examples, mass = [], defaultdict(Fraction)
    for source, item in zip(headers, cached, strict=True):
        p.require(
            all(item[key] == source[key] for key in (
                "package_id", "task_id", "pool", "state_id", "method", "whole_package_target_tokens"
            )),
            "trajectory_training.exact_original_package_metadata",
        )
        state = states[item["task_id"], item["state_id"]]
        pi = distribution.fraction(state["pi"])
        coefficient = pi / (5 * state["n_packages"] * item["whole_package_target_tokens"])
        examples.append(
            {
                "package_id": item["package_id"],
                "task_id": item["task_id"],
                "state_id": item["state_id"],
                "method": item["method"],
                "pool": pool,
                "n_state": state["n_packages"],
                "pi": str(pi),
                "whole_package_target_tokens": item["whole_package_target_tokens"],
                "target_token_coefficient": str(coefficient),
                "coefficient_float": float(coefficient),
                "fused": item["fused"],
            }
        )
        mass[item["task_id"]] += coefficient * item["whole_package_target_tokens"]
    p.require(
        len(mass) == 200 and all(value == Fraction(1, 5) for value in mass.values()),
        "trajectory_training.exact_one_fifth_mass_all_200_tasks",
    )
    return examples, assigned


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
    trajectory_cache,
    verified_inputs,
    model_loader=load_registered_student,
    optimizer_builder=optimizer_factory,
    loss_fn=selected_target_loss,
):
    """400 freshly initialized paired updates; no response-row state resume."""
    root, output = Path(root).resolve(), Path(output).resolve()
    p.require(
        output.is_relative_to(root) and output != root and not output.exists(),
        "trajectory_training.exclusive_contained_output_no_retry",
    )
    p.require(
        pool in p.POOLS and arm in p.ARMS and type(seed) is int and seed in p.SEEDS,
        "trajectory_training.registered_run",
    )
    output.mkdir(parents=True)
    p.write_once(
        output / "started.json",
        p.record(
            "training_started", time=p.now(), pool=pool, arm=arm, seed=seed,
            release_id=release.get("id"), automatic_retry=False, execution_design=EXECUTION_DESIGN,
        ),
    )
    updates, current_batch = [], None
    try:
        config = training_config()
        validate_release(release, kernel, pool=pool, arm=arm, seed=seed, verified_inputs=verified_inputs)
        verification = validate_materials(
            kernel, selected_population, registry, outcomes, verified_inputs=verified_inputs
        )
        examples, assigned = weighted_inputs(verified_inputs, pool, arm, trajectory_cache)
        schedule = population.batch_schedule(selected_population, seed)
        p.require(
            schedule["total_updates"] == 400 and len(schedule["batches"]) == 400,
            "trajectory_training.exact_400_update_schedule",
        )
        for name, value in (
            ("configuration", config), ("material_verification", verification),
            ("schedule", schedule), ("distribution", assigned),
        ):
            p.write_once(output / (name + ".json"), value)
        budget = trajectory_cache.actual_budget
        p.write_once(
            output / "trajectory_binding.json",
            p.record(
                "training_trajectory_binding", cache_id=trajectory_cache.cache_id,
                kernel_id=kernel["id"], material_verification_id=verification["id"],
                actual_budget=budget, source_material_budget=trajectory_cache.source_material_budget,
                execution_design=EXECUTION_DESIGN,
            ),
        )
        by_task = defaultdict(list)
        for index, example in enumerate(examples):
            by_task[example["task_id"]].append((index, example))
        groups = {task["task_id"]: task["family"] for task in selected_population["tasks"]}
        # Resolve all 400 inventories once. Updates never reconstruct or validate materials.
        batches = []
        for raw_batch in schedule["batches"]:
            selected = [
                item for _, item in sorted(
                    (item for task in raw_batch["task_ids"] for item in by_task[task]),
                    key=lambda item: item[0],
                )
            ]
            batches.append((
                {**raw_batch, "tasks": [
                    {"task_id": task, "group": groups[task]} for task in raw_batch["task_ids"]
                ]}, selected,
            ))
        model, scope = model_loader(checkpoint_binding, seed, config=config, trainable=True)
        parameters = [value for value in model.parameters() if value.requires_grad]
        p.require(
            parameters and all(value.dtype == torch.float32 for value in parameters),
            "trajectory_training.FP32_trainables",
        )
        device = parameters[0].device
        p.require(all(value.device == device for value in parameters), "trajectory_training.single_device")
        optimizer = optimizer_builder(parameters, config)
        p.require(not optimizer.state, "trajectory_training.fresh_empty_optimizer")
        model.train()
        actual = (
            device.type == "cuda" and model_loader is load_registered_student
            and optimizer_builder is optimizer_factory and loss_fn is selected_target_loss
        )
        identity = p.record(
            "training_run_identity", pool=pool, arm=arm, seed=seed, kernel_id=kernel["id"],
            population_id=selected_population["id"], release_id=release["id"],
            training_configuration_id=config["id"], schedule_id=schedule["id"],
            distribution_id=assigned["id"], base_binding_id=checkpoint_binding["id"],
            tokenizer_binding_id=verification["tokenizer_binding_id"], scope=scope,
            initial_adapter_digest=model_components.adapter_digest(model),
            physical_originals_sha256=kernel["physical_originals_sha256"],
            execution_mode="local_CUDA" if actual else "synthetic_injected", device=str(device),
            fresh_initialization=True, unique_final_checkpoint=True,
            study_freeze_id=release["study_freeze_id"], surface_manifest_id=release["surface_manifest_id"],
            execution_design=EXECUTION_DESIGN, trajectory_cache_id=trajectory_cache.cache_id,
        )
        p.write_once(output / "identity.json", identity)
        seen, epoch_totals = Counter(), Counter()
        for batch, selected in batches:
            current_batch = batch
            expected = [item["package_id"] for item in selected]
            directory = output / "updates" / f"{batch['step'] + 1:04d}"
            p.write_once(
                directory / "started.json",
                p.record(
                    "optimizer_update_started", time=p.now(), batch=batch,
                    expected_package_ids=expected, pool=pool, arm=arm,
                ),
            )
            with (directory / "events.jsonl").open("xb") as stream:
                def persist(event, update_index=batch["step"] + 1):
                    stream.write(p.encode(p.record(
                        "optimizer_update_event", time=p.now(), optimizer_update=update_index, **event
                    )) + b"\n")

                try:
                    result = consumer.execute_update(
                        model, optimizer, selected, batch, pool=pool, arm=arm, device=device,
                        trajectory_cache=trajectory_cache, loss_fn=loss_fn, event_sink=persist,
                    )
                finally:
                    stream.flush()
                    os.fsync(stream.fileno())
            p.write_once(directory / "report.json", result)
            summary = {
                "id": result["id"], "path": str((directory / "report.json").relative_to(root)),
                "sha256": p.sha(directory / "report.json"), "target_tokens": result["target_tokens"],
                "sequence_tokens": result["sequence_tokens"], "rows": result["rows_completed"],
                "packages": result["packages_completed"],
            }
            updates.append(summary)
            seen.update(expected)
            epoch_totals.update({key: summary[key] for key in (
                "packages", "rows", "target_tokens", "sequence_tokens"
            )})
            if (batch["step"] + 1) % 40 == 0:
                p.write_once(
                    output / "epochs" / f"{batch['epoch'] + 1:02d}.json",
                    p.record("epoch_complete", epoch=batch["epoch"] + 1, **epoch_totals),
                )
                epoch_totals = Counter()
        p.require(
            len(updates) == 400
            and seen == Counter({item["package_id"]: 10 for item in examples})
            and all(sum(item[key] for item in updates) == budget[key + "_all_epochs"] for key in (
                "packages", "rows", "target_tokens", "sequence_tokens"
            )),
            "trajectory_training.complete_400_update_ten_pass_accounting",
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
            actual_complete=actual, pool=pool, arm=arm, seed=seed, kernel_id=kernel["id"],
            release_id=release["id"], identity_id=identity["id"], training_configuration_id=config["id"],
            final_adapter=adapter, checkpoint_id=adapter["parameter_digest"],
            adapter_directory=str(output.relative_to(root)),
            initial_adapter_digest=identity["initial_adapter_digest"],
            base_binding_id=checkpoint_binding["id"], tokenizer_binding_id=verification["tokenizer_binding_id"],
            final_adapter_restored_identity_verified=True, optimizer_updates=400, epochs_completed=10,
            physical_originals_sha256=kernel["physical_originals_sha256"], actual_budget=budget,
            source_material_budget=trajectory_cache.source_material_budget,
            material_verification_id=verification["id"], schedule_id=schedule["id"], updates=updates,
            training_retokenizations=0, intermediate_checkpoints=0, automatic_retries=0,
            finish_time=p.now(), execution_mode=identity["execution_mode"],
            study_freeze_id=release["study_freeze_id"], surface_manifest_id=release["surface_manifest_id"],
            trajectory_cache_id=trajectory_cache.cache_id, execution_design=EXECUTION_DESIGN,
        )
        p.write_once(output / "report.json", report)
        return report
    except BaseException as error:
        p.write_once(
            output / "failure.json",
            p.record(
                "training_failure", time=p.now(), error_type=type(error).__name__, error=str(error),
                pool=pool, arm=arm, seed=seed, current_batch=current_batch, completed_updates=updates,
                actual_complete=False, failed_run_retained=True, automatic_retry=False,
                execution_design=EXECUTION_DESIGN,
            ),
        )
        raise
