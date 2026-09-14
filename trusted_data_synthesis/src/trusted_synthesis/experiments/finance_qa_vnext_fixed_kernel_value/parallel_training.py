"""Eight-rank execution of the sole queued A/minus/47 Student.

The global objective remains the serial weighted SUM. One packed NCCL SUM per
update precedes one global clip and AdamW step on each identical replica. Native
CUDA dropout offsets replay the parent serial trajectory stream; reduction order
can still change floating-point rounding, so no bitwise optimizer claim is made.
"""

import argparse
import json
import os
import tempfile
import time
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from types import FunctionType, SimpleNamespace

import numpy as np
import torch
import torch.distributed as dist
import torch.multiprocessing as multiprocessing
import torch.nn.functional as functional
from torch.nn.attention import SDPBackend, sdpa_kernel

from . import fast_materials, population, trajectory_materials
from . import protocol as p
from . import trajectory_training as serial

EXECUTION_DESIGN = "parallel_tail_sum_v1"
WORLD_SIZE = 8
RUN = {"pool": "A", "arm": "minus", "seed": 47}
HIDDEN_SIZE = 3584
DROPOUT_CALLS = 56
TRAINABLE_PARAMETERS = 2523136
STAT_FIELDS = ("weighted_loss", "target_tokens", "sequence_tokens", "rows", "packages")
_HOST_MINT = object()


def training_config():
    previous = serial.training_config()
    fields = {key: value for key, value in previous.items() if key not in {"id", "schema_version"}}
    fields.update(
        parent_trajectory_training_configuration_id=previous["id"],
        execution_design=EXECUTION_DESIGN,
        parallel_policy={
            "only_run": RUN,
            "world_size": WORLD_SIZE,
            "backend": "nccl",
            "replication": "full BF16 base plus identical FP32 LoRA on every rank",
            "partition": (
                "stable longest-sequence-token-first package assignment; serial order within rank"
            ),
            "gradient_reduction": (
                "one packed FP32 all_reduce(SUM) per global update; never average"
            ),
            "update": (
                "one local zero; local weighted SUM; global SUM; "
                "one clip and AdamW step per replica"
            ),
            "empty_ranks": "zero local gradient contribution; still join the single global SUM",
            "microbatch_rows_per_rank": 1,
            "per_row_DDP_collectives": 0,
            "global_updates": 400,
        },
        parallel_rng_policy={
            "seed": 47,
            "initial_state": (
                "capture native CUDA generator immediately after original seeded LoRA load"
            ),
            "offset_calibration": (
                "one native BF16 dropout for each distinct [1,L,3584] shape; restore state"
            ),
            "calls_per_trajectory_segment": DROPOUT_CALLS,
            "package_offset": (
                "cumulative offsets in parent serial 400-update/package/segment order"
            ),
            "replay": (
                "restore original generator seed and offset before each assigned trajectory segment"
            ),
            "dropout_probability": 0.05,
            "checkpoint_RNG_preservation": True,
            "per_package_reseeding": False,
            "new_dropout_stream_claimed": False,
        },
        floating_point_reduction_order_changed=True,
        bitwise_optimizer_equivalence_claimed=False,
        shared_host_admission=(
            "base checkpoint SHA once and existing numeric cache SHA once; "
            "child private admission plus file stat signatures"
        ),
    )
    return p.record("training_configuration", **fields)


def make_release(
    kernel, *, study_freeze_id, surface_manifest_id, allowed_runs, verified_inputs=None
):
    p.require(allowed_runs == [RUN], "parallel.only_queued_A_minus_47_release")
    old = serial.make_release(
        kernel,
        study_freeze_id=study_freeze_id,
        surface_manifest_id=surface_manifest_id,
        allowed_runs=allowed_runs,
        verified_inputs=verified_inputs,
    )
    fields = {key: value for key, value in old.items() if key not in {"id", "schema_version"}}
    fields.update(
        training_configuration_id=training_config()["id"], execution_design=EXECUTION_DESIGN
    )
    return p.record("training_release", **fields)


def partition_packages(packages, world_size=WORLD_SIZE):
    """Stable LPT balancing, then restore original package order within rank."""
    p.require(type(world_size) is int and world_size > 0, "parallel.positive_world_size")
    assignments, loads = [[] for _ in range(world_size)], [0] * world_size
    for index in sorted(range(len(packages)), key=lambda i: (-packages[i]["sequence_tokens"], i)):
        rank = min(range(world_size), key=lambda value: (loads[value], value))
        assignments[rank].append(index)
        loads[rank] += packages[index]["sequence_tokens"]
    return [sorted(indices) for indices in assignments], loads


def prepare_plan(examples, cache, schedule, selected_population, world_size=WORLD_SIZE):
    """Bind metadata once; never revalidate original rows in an optimizer step."""
    metadata = {row["package_id"]: row for row in cache.packages}
    by_task = defaultdict(list)
    for index, example in enumerate(examples):
        by_task[example["task_id"]].append((index, example))
    groups = {task["task_id"]: task["family"] for task in selected_population["tasks"]}
    batches, occurrences = [], Counter()
    for batch in schedule["batches"]:
        packages = []
        for _, example in sorted(
            (item for task in batch["task_ids"] for item in by_task[task]), key=lambda item: item[0]
        ):
            original = metadata[example["package_id"]]
            packages.append(
                {
                    **example,
                    "sequence_tokens": original["sequence_tokens"],
                    "rows": original["rows"],
                    "segment_lengths": [item["input_length"] for item in original["segments"]],
                }
            )
        assignments, loads = partition_packages(packages, world_size)
        occurrences.update(row["package_id"] for row in packages)
        batches.append(
            {
                **batch,
                "tasks": [{"task_id": task, "group": groups[task]} for task in batch["task_ids"]],
                "packages": packages,
                "rank_package_indices": assignments,
                "rank_sequence_tokens": loads,
            }
        )
    p.require(
        len(batches) == schedule["total_updates"] == 400
        and occurrences == Counter({item["package_id"]: 10 for item in examples}),
        "parallel.original_400_update_ten_visit_inventory",
    )
    return p.record(
        "parallel_training_plan",
        world_size=world_size,
        run=RUN,
        schedule_id=schedule["id"],
        cache_id=cache.cache_id,
        batches=batches,
        original_package_order_for_RNG=True,
        rank_order_preserves_original_relative_package_order=True,
        per_package_reweighting=False,
    )


def calibrate_dropout_offsets(lengths, *, device=0):
    """Measure the installed native kernel, including its actual GPU grid policy."""
    generator = torch.cuda.default_generators[device]
    saved = generator.get_state()
    seed, initial = generator.initial_seed(), generator.get_offset()
    advances = {}
    try:
        for length in sorted(set(lengths)):
            value = torch.ones(
                (1, length, HIDDEN_SIZE), dtype=torch.bfloat16, device=f"cuda:{device}"
            )
            before = generator.get_offset()
            result = functional.dropout(value, p=0.05, training=True)
            advance = generator.get_offset() - before
            p.require(advance > 0 and advance % 4 == 0, "parallel.native_philox_offset_advance")
            advances[length] = advance
            del result, value
        torch.cuda.synchronize(device)
    finally:
        generator.set_state(saved)
    p.require(
        generator.initial_seed() == seed and generator.get_offset() == initial,
        "parallel.calibration_restores_original_generator",
    )
    return {
        "seed": seed,
        "initial_offset": initial,
        "per_dropout_call_offsets": {str(key): value for key, value in advances.items()},
        "calls_per_segment": DROPOUT_CALLS,
        "hidden_size": HIDDEN_SIZE,
        "dtype": "bfloat16",
        "contiguous": True,
    }


def attach_serial_offsets(plan, calibration):
    """Use original serial order, never partition order, to allocate RNG ranges."""
    offset = calibration["initial_offset"]
    batches = []
    for batch in plan["batches"]:
        packages = []
        for package in batch["packages"]:
            segments = []
            for length in package["segment_lengths"]:
                end = (
                    offset
                    + calibration["calls_per_segment"]
                    * calibration["per_dropout_call_offsets"][str(length)]
                )
                segments.append({"length": length, "offset": offset, "end_offset": end})
                offset = end
            packages.append({**package, "rng_segments": segments})
        batches.append({**batch, "packages": packages, "serial_end_offset": offset})
    return batches, offset


def pack_gradients(parameters, stats, packed=None):
    """One flat SUM payload; missing gradients mean an empty local contribution."""
    count = sum(parameter.numel() for parameter in parameters)
    if packed is None:
        packed = torch.empty(
            count + len(STAT_FIELDS), dtype=torch.float32, device=parameters[0].device
        )
    offset = 0
    for parameter in parameters:
        view = packed[offset : offset + parameter.numel()]
        if parameter.grad is None:
            view.zero_()
        else:
            view.copy_(parameter.grad.detach().reshape(-1))
        offset += parameter.numel()
    packed[count:] = torch.as_tensor(stats, dtype=torch.float32, device=packed.device)
    return packed


def install_sum_and_step(parameters, optimizer, packed):
    """No world-size divisor: restore the global sum, clip once, step once."""
    offset = 0
    for parameter in parameters:
        gradient = packed[offset : offset + parameter.numel()].view_as(parameter)
        if parameter.grad is None:
            parameter.grad = gradient.clone()
        else:
            parameter.grad.copy_(gradient)
        offset += parameter.numel()
    p.require(
        bool(torch.isfinite(packed[offset:]).all()), "parallel.finite_global_update_statistics"
    )
    norm = torch.nn.utils.clip_grad_norm_(parameters, 1.0, error_if_nonfinite=True)
    optimizer.step()
    return float(norm), packed[offset:].detach().cpu().tolist()


def _connect(rank, devices, store):
    os.environ["CUDA_VISIBLE_DEVICES"] = devices[rank]
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    os.environ["OMP_NUM_THREADS"] = "2"
    os.environ["MKL_NUM_THREADS"] = "2"
    torch.set_num_threads(2)
    torch.cuda.set_device(0)
    dist.init_process_group(
        backend="nccl",
        init_method=Path(store).absolute().as_uri(),
        rank=rank,
        world_size=len(devices),
        timeout=timedelta(seconds=180),
    )


def _gather(value):
    values = [None] * dist.get_world_size()
    dist.all_gather_object(values, value)
    return values


def _signature(path):
    value = Path(path).stat()
    return [value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns]


class _HostAdmission:
    """Owned spawn payload minted by the parent after the actual SHA checks."""

    def __init__(self, value, binding, *, mint):
        p.require(mint is _HOST_MINT, "parallel.private_host_admission_constructor")
        self._mint = mint
        self.value = fast_materials.freeze_json(value)
        self.binding = fast_materials.freeze_json(binding)

    def __reduce__(self):
        return _restore_host_admission, (dict(self.value), dict(self.binding))


def _restore_host_admission(value, binding):
    # This constructor is reached by multiprocessing's trusted spawn channel,
    # never from a caller-supplied JSON receipt or command-line admission file.
    p.checked(value, "parallel_host_admission")
    return _HostAdmission(value, binding, mint=_HOST_MINT)


def _host_admission(binding, cache):
    serial.model_components.verify_checkpoint(binding)
    paths = [Path(binding["directory"]) / item["path"] for item in binding["members"]]
    pool = cache.manifest["pools"][RUN["pool"]]
    paths += [
        Path(cache.cache_root) / pool[name]["path"]
        for name in ("input_ids", "target_positions", "package_index")
    ]
    paths += [
        Path(__file__),
        Path(serial.__file__),
        Path(serial.original.__file__),
        Path(serial.model_components.__file__),
        Path(trajectory_materials.__file__),
    ]
    record = p.record(
        "parallel_host_admission",
        base_binding_id=binding["id"],
        trajectory_cache_id=cache.cache_id,
        source_material_verification_id=cache.material_verification_id,
        files=[{"path": str(path.resolve()), "signature": _signature(path)} for path in paths],
        parent_base_checkpoint_verifications=1,
        parent_numeric_pool_loads=1,
        child_repeated_base_or_numeric_SHA_scans=0,
        original_model_loader_bytecode_retained=True,
    )
    return _HostAdmission(record, binding, mint=_HOST_MINT)


def _check_host_admission(admission, binding, manifest):
    p.require(
        type(admission) is _HostAdmission
        and admission._mint is _HOST_MINT
        and admission.binding == binding
        and admission.value["base_binding_id"] == binding["id"]
        and admission.value["trajectory_cache_id"] == manifest["id"]
        and all(_signature(item["path"]) == item["signature"] for item in admission.value["files"]),
        "parallel.private_unchanged_host_admitted_files",
    )


def _load_admitted_student(binding, admission):
    """Original loader/adapter bytecode; reuse the parent's already checked SHA."""
    components = serial.model_components

    def admitted_checkpoint(value):
        p.require(value == admission.binding, "parallel.exact_host_admitted_checkpoint_binding")

    source = components.load_student
    loader = FunctionType(
        source.__code__,
        {**source.__globals__, "verify_checkpoint": admitted_checkpoint},
        source.__name__,
        source.__defaults__,
        source.__closure__,
    )
    loader.__kwdefaults__ = source.__kwdefaults__
    source = serial.original.load_registered_student
    physical = FunctionType(
        source.__code__,
        {
            **source.__globals__,
            "model_components": SimpleNamespace(**{**vars(components), "load_student": loader}),
        },
        source.__name__,
        source.__defaults__,
        source.__closure__,
    )
    physical.__kwdefaults__ = source.__kwdefaults__
    return physical(binding, RUN["seed"], config=serial.original.training_config(), trainable=True)


def _load_admitted_pool(cache_root, manifest):
    """Readonly mmap of the same parent-admitted arrays; no repeated byte scan."""
    root = Path(cache_root)
    pool = manifest["pools"][RUN["pool"]]
    index = json.loads((root / pool["package_index"]["path"]).read_bytes())
    inputs = np.load(root / pool["input_ids"]["path"], mmap_mode="r", allow_pickle=False)
    positions = np.load(root / pool["target_positions"]["path"], mmap_mode="r", allow_pickle=False)
    return trajectory_materials.TrajectoryPool(
        mint=trajectory_materials._MINT,
        root=root,
        manifest=manifest,
        pool=RUN["pool"],
        index=index,
        inputs=inputs,
        positions=positions,
    )


def _dropout_layout_hooks(model):
    modules = [
        (name, module)
        for name, module in model.named_modules()
        if isinstance(module, torch.nn.Dropout)
    ]
    p.require(
        model.config.num_hidden_layers == 28
        and model.config.hidden_size == HIDDEN_SIZE
        and model.config.attention_dropout == 0.0
        and len(modules) == DROPOUT_CALLS
        and all(
            name.endswith(("q_proj.dropout", "v_proj.dropout")) and module.p == 0.05
            for name, module in modules
        ),
        "parallel.only_56_native_qv_dropout_sites_attention_dropout_zero",
    )
    observed = []

    def inspect(module, args):
        value = args[0]
        p.require(
            value.dtype == torch.bfloat16
            and value.ndim == 3
            and value.shape[0] == 1
            and value.shape[2] == HIDDEN_SIZE
            and value.is_contiguous(),
            "parallel.actual_LoRA_native_dropout_BF16_contiguous_layout",
        )
        observed.append(tuple(value.shape))

    return [module.register_forward_pre_hook(inspect) for _, module in modules], observed


def _rank_worker(rank, devices, payload):
    output = Path(payload["output"])
    rank_output = output / "ranks" / str(rank)
    rank_output.mkdir(parents=True, exist_ok=False)
    updates_completed = 0
    try:
        _connect(rank, devices, payload["store"])
        _check_host_admission(
            payload["host_admission"], payload["base_binding"], payload["cache_manifest"]
        )
        model, scope = _load_admitted_student(payload["base_binding"], payload["host_admission"])
        parameters = [value for value in model.parameters() if value.requires_grad]
        p.require(
            sum(value.numel() for value in parameters) == TRAINABLE_PARAMETERS
            and all(
                value.dtype == torch.float32 and value.device.type == "cuda" for value in parameters
            ),
            "parallel.original_FP32_qv_LoRA_parameter_scope",
        )
        optimizer = serial.optimizer_factory(parameters, serial.training_config())
        p.require(not optimizer.state, "parallel.fresh_empty_AdamW")
        generator = torch.cuda.default_generators[0]
        initial_digest = serial.model_components.adapter_digest(model)
        p.require(
            initial_digest == payload["expected_initial_adapter_digest"],
            "parallel.initial_adapter_identical_to_completed_paired_seed47_Students",
        )
        hooks, observed = _dropout_layout_hooks(model)
        lengths = [
            length
            for batch in payload["plan"]["batches"]
            for item in batch["packages"]
            for length in item["segment_lengths"]
        ]
        initial_seed, initial_offset = generator.initial_seed(), generator.get_offset()
        calibration_box = [calibrate_dropout_offsets(lengths) if rank == 0 else None]
        dist.broadcast_object_list(calibration_box, src=0)
        calibration = calibration_box[0]
        p.require(
            calibration["seed"] == initial_seed and calibration["initial_offset"] == initial_offset,
            "parallel.same_native_seed_offset_before_calibration_all_ranks",
        )
        if rank != 0:
            representative = calibrate_dropout_offsets([min(lengths), max(lengths)])
            p.require(
                all(
                    calibration["per_dropout_call_offsets"][key] == value
                    for key, value in representative["per_dropout_call_offsets"].items()
                ),
                "parallel.other_rank_two_shape_native_offset_agreement",
            )
        p.require(
            calibration["seed"] == RUN["seed"],
            "parallel.original_seed_after_adapter_initialization",
        )
        initial = {
            "rank": rank,
            "gpu_uuid": devices[rank],
            "initial_adapter_digest": initial_digest,
            "calibration": calibration,
            "calibration_sha256": p.sha(p.encode(calibration)),
            "GPU_name": torch.cuda.get_device_name(0),
            "GPU_multiprocessors": torch.cuda.get_device_properties(0).multi_processor_count,
        }
        initial_ranks = _gather(initial)
        p.require(
            len({item["initial_adapter_digest"] for item in initial_ranks}) == 1
            and len({item["calibration_sha256"] for item in initial_ranks}) == 1
            and len({(item["GPU_name"], item["GPU_multiprocessors"]) for item in initial_ranks})
            == 1,
            "parallel.identical_initial_Student_and_native_RNG_offsets_all_ranks",
        )
        p.write_once(rank_output / "started.json", p.record("parallel_rank_started", **initial))
        cache = _load_admitted_pool(payload["cache_root"], payload["cache_manifest"])
        batches, final_serial_offset = attach_serial_offsets(payload["plan"], calibration)
        if rank == 0:
            identity = p.record(
                "training_run_identity",
                **RUN,
                kernel_id=payload["kernel_id"],
                population_id=payload["population_id"],
                release_id=payload["release"]["id"],
                training_configuration_id=training_config()["id"],
                schedule_id=payload["schedule"]["id"],
                distribution_id=payload["assigned"]["id"],
                base_binding_id=payload["base_binding"]["id"],
                tokenizer_binding_id=payload["verification"]["tokenizer_binding_id"],
                scope=scope,
                initial_adapter_digest=initial_digest,
                physical_originals_sha256=payload["physical_originals_sha256"],
                execution_mode="local_CUDA",
                device="8xCUDA_NCCL",
                fresh_initialization=True,
                unique_final_checkpoint=True,
                study_freeze_id=payload["release"]["study_freeze_id"],
                surface_manifest_id=payload["release"]["surface_manifest_id"],
                execution_design=EXECUTION_DESIGN,
                trajectory_cache_id=cache.cache_id,
                parent_trajectory_training_configuration_id=serial.training_config()["id"],
                parallel_backend="nccl",
                world_size=len(devices),
                initial_ranks=initial_ranks,
                dropout_stream="original_single_GPU_serial_native_Philox_offsets",
                bitwise_optimizer_equivalence_claimed=False,
            )
            p.write_once(output / "identity.json", identity)
            p.write_once(
                output / "rng_plan.json",
                p.record(
                    "parallel_serial_rng_plan",
                    calibration=calibration,
                    plan_id=payload["plan"]["id"],
                    final_serial_offset=final_serial_offset,
                    original_serial_order=True,
                    generator_state_restored_after_calibration=True,
                ),
            )
        all_updates, local_totals = [], Counter()
        packed = None
        for batch in batches:
            step = batch["step"] + 1
            started_at, started_clock = p.now(), time.perf_counter()
            if rank == 0:
                p.write_once(
                    output / "updates" / f"{step:04d}" / "started.json",
                    p.record(
                        "optimizer_update_started",
                        time=started_at,
                        optimizer_update=step,
                        tasks=batch["tasks"],
                        expected_package_ids=[item["package_id"] for item in batch["packages"]],
                        rank_sequence_tokens=batch["rank_sequence_tokens"],
                        execution_design=EXECUTION_DESIGN,
                    ),
                )
            directory = rank_output / "updates" / f"{step:04d}"
            directory.mkdir(parents=True)
            optimizer.zero_grad(set_to_none=True)
            local = [0.0] * len(STAT_FIELDS)
            with (directory / "events.jsonl").open("xb") as stream:

                def emit(event, update_step=step):
                    stream.write(
                        p.encode(
                            p.record(
                                "parallel_rank_event",
                                time=p.now(),
                                rank=rank,
                                optimizer_update=update_step,
                                **event,
                            )
                        )
                        + b"\n"
                    )

                emit(
                    {
                        "event": "update_started",
                        "assigned_package_indices": batch["rank_package_indices"][rank],
                    }
                )
                for package_index in batch["rank_package_indices"][rank]:
                    package = batch["packages"][package_index]
                    package_loss = torch.zeros((), dtype=torch.float32, device="cuda:0")
                    for row, rng in zip(
                        cache.row_arrays(package["package_id"]),
                        package["rng_segments"],
                        strict=True,
                    ):
                        # Only offsets change. The original initial seed stays fixed.
                        generator.set_offset(rng["offset"])
                        ids = torch.tensor(
                            row["input_ids"], dtype=torch.long, device="cuda:0"
                        ).unsqueeze(0)
                        positions = (
                            torch.tensor(row["target_positions"], dtype=torch.long, device="cuda:0")
                            - 1
                        )
                        targets = torch.tensor(row["target_ids"], dtype=torch.long, device="cuda:0")
                        with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                            logits = model(
                                input_ids=ids,
                                attention_mask=torch.ones_like(ids),
                                use_cache=False,
                                logits_to_keep=positions,
                            ).logits
                            if hooks:
                                p.require(
                                    len(observed) == DROPOUT_CALLS,
                                    "parallel.actual_first_forward_56_dropout_calls",
                                )
                                for hook in hooks:
                                    hook.remove()
                                hooks = []
                            loss = serial.selected_target_loss(
                                logits, targets, package["coefficient_float"]
                            )
                            loss.backward()
                        # This O(1) runtime cursor check is essential to RNG replay,
                        # not another material/token validation pass.
                        p.require(
                            generator.get_offset() == rng["end_offset"],
                            "parallel.native_dropout_and_checkpoint_exact_serial_RNG_progress",
                        )
                        package_loss += loss.detach()
                        local[1] += targets.numel()
                        local[2] += ids.shape[1]
                        local[3] += 1
                        del ids, positions, targets, logits, loss
                    value = float(package_loss)
                    local[0] += value
                    local[4] += 1
                    emit(
                        {
                            "event": "package_backward_completed",
                            "package_id": package["package_id"],
                            "weighted_loss": value,
                            "serial_rng_end_offset": package["rng_segments"][-1]["end_offset"],
                        }
                    )
                generator.set_offset(batch["serial_end_offset"])
                p.require(
                    not batch["rank_package_indices"][rank]
                    or all(parameter.grad is not None for parameter in parameters),
                    "parallel.nonempty_rank_all_trainable_gradients_connected",
                )
                packed = pack_gradients(parameters, local, packed)
                dist.all_reduce(packed, op=dist.ReduceOp.SUM)
                norm, global_values = install_sum_and_step(parameters, optimizer, packed)
                updates_completed = step
                emit(
                    {
                        "event": "global_update_complete",
                        "preclip_gradient_norm": norm,
                        "local_statistics": dict(zip(STAT_FIELDS, local, strict=True)),
                        "global_statistics": dict(zip(STAT_FIELDS, global_values, strict=True)),
                        "gradient_SUM_collectives": 1,
                        "optimizer_step_calls": 1,
                    }
                )
                stream.flush()
                os.fsync(stream.fileno())
            local_totals.update(
                {key: int(local[index]) for index, key in enumerate(STAT_FIELDS) if index}
            )
            if rank == 0:
                stats = {
                    key: int(global_values[index]) for index, key in enumerate(STAT_FIELDS) if index
                }
                result = p.record(
                    "optimizer_update",
                    **RUN,
                    tasks=batch["tasks"],
                    packages=batch["packages"],
                    weighted_loss=global_values[0],
                    target_tokens=stats["target_tokens"],
                    sequence_tokens=stats["sequence_tokens"],
                    rows_completed=stats["rows"],
                    packages_completed=stats["packages"],
                    preclip_gradient_norm=norm,
                    loss_rule="pi(state|task)/(5*n_state*whole_package_target_tokens)",
                    additional_loss_scaling=False,
                    zero_grad_calls=1,
                    clip_calls=1,
                    optimizer_step_calls=1,
                    replica_count=len(devices),
                    gradient_SUM_collectives=1,
                    world_size_divisor=False,
                    physical_package_count=len(batch["packages"]),
                    cache_id=cache.cache_id,
                    execution_design=EXECUTION_DESIGN,
                    rank_package_indices=batch["rank_package_indices"],
                    rank_sequence_tokens=batch["rank_sequence_tokens"],
                    serial_rng_end_offset=batch["serial_end_offset"],
                    started_at=started_at,
                    finished_at=p.now(),
                    elapsed_seconds=time.perf_counter() - started_clock,
                )
                path = output / "updates" / f"{step:04d}" / "report.json"
                p.write_once(path, result)
                all_updates.append(
                    {
                        "id": result["id"],
                        "path": str(path.relative_to(Path(payload["root"]))),
                        "sha256": p.sha(path),
                        **stats,
                    }
                )
        final_digest = serial.model_components.adapter_digest(model)
        completed = p.record(
            "parallel_rank_complete",
            rank=rank,
            gpu_uuid=devices[rank],
            optimizer_updates=updates_completed,
            initial_adapter_digest=initial_digest,
            final_adapter_digest=final_digest,
            serial_rng_final_offset=generator.get_offset(),
            expected_serial_rng_final_offset=final_serial_offset,
            calibration_sha256=initial["calibration_sha256"],
            local_actual_totals=dict(local_totals),
            actual_complete=True,
            finished_at=p.now(),
        )
        completed_ranks = _gather(completed)
        p.require(
            all(
                item["optimizer_updates"] == 400
                and item["final_adapter_digest"] == final_digest
                and item["serial_rng_final_offset"] == final_serial_offset
                for item in completed_ranks
            ),
            "parallel.all_replicas_identical_final_adapter_and_400_updates",
        )
        p.write_once(rank_output / "complete.json", completed)
        if rank == 0:
            budget = cache.actual_budget
            p.require(
                len(all_updates) == 400
                and all(
                    sum(item[key] for item in all_updates) == budget[key + "_all_epochs"]
                    for key in ("packages", "rows", "target_tokens", "sequence_tokens")
                ),
                "parallel.complete_actual_global_ten_pass_budget",
            )
            adapter_path = output / "final_adapter.safetensors"
            adapter = serial.model_components.save_adapter(model, adapter_path)
            with adapter_path.open("rb") as stream:
                os.fsync(stream.fileno())
            serial.model_components.load_adapter(model, adapter_path, adapter)
            candidate = p.record(
                "parallel_training_candidate",
                status="COMPLETE_FINAL_CHECKPOINT",
                actual_complete=True,
                **RUN,
                kernel_id=payload["kernel_id"],
                release_id=payload["release"]["id"],
                identity_id=identity["id"],
                training_configuration_id=training_config()["id"],
                final_adapter=adapter,
                checkpoint_id=adapter["parameter_digest"],
                adapter_directory=str(output.relative_to(Path(payload["root"]))),
                initial_adapter_digest=initial_digest,
                base_binding_id=payload["base_binding"]["id"],
                tokenizer_binding_id=payload["verification"]["tokenizer_binding_id"],
                final_adapter_restored_identity_verified=True,
                optimizer_updates=400,
                epochs_completed=10,
                physical_originals_sha256=payload["physical_originals_sha256"],
                actual_budget=budget,
                source_material_budget=cache.source_material_budget,
                material_verification_id=payload["verification"]["id"],
                schedule_id=payload["schedule"]["id"],
                updates=all_updates,
                training_retokenizations=0,
                intermediate_checkpoints=0,
                automatic_retries=0,
                finish_time=p.now(),
                execution_mode="local_CUDA",
                study_freeze_id=payload["release"]["study_freeze_id"],
                surface_manifest_id=payload["release"]["surface_manifest_id"],
                trajectory_cache_id=cache.cache_id,
                execution_design=EXECUTION_DESIGN,
                parent_trajectory_training_configuration_id=serial.training_config()["id"],
                parallel_backend="nccl",
                world_size=len(devices),
                rank_completions=completed_ranks,
                gradient_reduction="SUM",
                gradient_collectives=400,
                world_size_divisor=False,
                dropout_stream="original_single_GPU_serial_native_Philox_offsets",
                dropout_masks_replayed_from_parent_serial_stream=True,
                floating_point_reduction_order_changed=True,
                bitwise_optimizer_equivalence_claimed=False,
            )
            p.write_once(output / "candidate.json", candidate)
        dist.destroy_process_group()
    except BaseException as error:
        p.write_once(
            rank_output / "failure.json",
            p.record(
                "parallel_rank_failure",
                rank=rank,
                error_type=type(error).__name__,
                error=str(error),
                optimizer_updates_completed=updates_completed,
                automatic_retry=False,
                time=p.now(),
            ),
        )
        raise


def _spawn_and_join(worker, devices, payload):
    # Rendezvous bytes are runtime machinery, never a published scientific file.
    payload = {
        **payload,
        "store": str(Path(tempfile.mkdtemp(prefix="fixed-kernel-parallel-nccl-")) / "store"),
    }
    context = multiprocessing.start_processes(
        worker,
        args=(devices, payload),
        nprocs=len(devices),
        join=False,
        daemon=False,
        start_method="spawn",
    )
    while not context.join(timeout=1):
        pass
    return [
        {"rank": rank, "pid": process.pid, "exit_code": process.exitcode, "gpu_uuid": devices[rank]}
        for rank, process in enumerate(context.processes)
    ]


def launch(
    root,
    output,
    *,
    input_root,
    material_input_receipt,
    input_files,
    expected_kernel_id,
    trajectory_cache,
    base_binding,
    release,
    devices,
    expected_initial_adapter_digest,
    expected_schedule_id,
):
    """Launch only the queued ninth Student; controller owns GPU availability."""
    root, output = Path(root).resolve(), Path(output).resolve()
    p.require(
        output.is_relative_to(root) and output != root and not output.exists(),
        "parallel.exclusive_new_training_output",
    )
    p.require(
        len(devices) == WORLD_SIZE
        and len(set(devices)) == WORLD_SIZE
        and all(isinstance(value, str) and value.startswith("GPU-") for value in devices),
        "parallel.exact_eight_unique_physical_GPU_UUIDs",
    )
    authority = fast_materials.load_authority(
        input_root, material_input_receipt, input_files, expected_kernel_id=expected_kernel_id
    )
    p.require(
        release
        == make_release(
            authority["kernel"],
            study_freeze_id=release["study_freeze_id"],
            surface_manifest_id=release["surface_manifest_id"],
            allowed_runs=[RUN],
            verified_inputs=authority,
        ),
        "parallel.actual_new_tail_release",
    )
    cache_root = root / trajectory_cache["cache_root"]
    manifest_path = root / trajectory_cache["manifest"]["path"]
    p.require(
        manifest_path.resolve().is_relative_to(cache_root.resolve())
        and p.sha(manifest_path) == trajectory_cache["manifest"]["sha256"],
        "parallel.bound_cache_manifest",
    )
    manifest = p.checked(p.read_json(manifest_path), "trajectory_material_cache")
    p.require(
        manifest["id"] == trajectory_cache["manifest_id"],
        "parallel.original_trajectory_cache_identity",
    )
    cache = trajectory_materials.load_pool(cache_root, manifest, RUN["pool"])
    examples, assigned = serial.weighted_inputs(authority, RUN["pool"], RUN["arm"], cache)
    schedule = population.batch_schedule(authority["population"], RUN["seed"])
    p.require(
        schedule["id"] == expected_schedule_id
        and isinstance(expected_initial_adapter_digest, str)
        and len(expected_initial_adapter_digest) == 64,
        "parallel.same_completed_paired_seed47_schedule_and_initial_adapter",
    )
    plan = prepare_plan(examples, cache, schedule, authority["population"])
    admission = _host_admission(base_binding, cache)
    output.mkdir(parents=True)
    started = p.record(
        "training_started",
        **RUN,
        time=p.now(),
        release_id=release["id"],
        automatic_retry=False,
        execution_design=EXECUTION_DESIGN,
        devices=devices,
    )
    p.write_once(output / "started.json", started)
    p.write_once(output / "host_admission.json", admission.value)
    for name, value in (
        ("configuration", training_config()),
        ("schedule", schedule),
        ("distribution", assigned),
        ("material_verification", authority.verification),
        ("parallel_plan", plan),
    ):
        p.write_once(output / (name + ".json"), value)
    payload = {
        "root": str(root),
        "output": str(output),
        "kernel_id": expected_kernel_id,
        "population_id": authority["population"]["id"],
        "release": release,
        "base_binding": base_binding,
        "verification": authority.verification,
        "physical_originals_sha256": authority["kernel"]["physical_originals_sha256"],
        "cache_root": str(cache_root),
        "cache_manifest": manifest,
        "plan": plan,
        "schedule": schedule,
        "assigned": assigned,
        "host_admission": admission,
        "expected_initial_adapter_digest": expected_initial_adapter_digest,
    }
    try:
        exits = _spawn_and_join(_rank_worker, devices, payload)
        p.require(
            all(item["exit_code"] == 0 for item in exits), "parallel.every_rank_exited_successfully"
        )
        candidate = p.checked(p.read_json(output / "candidate.json"), "parallel_training_candidate")
        report = p.record(
            "training_report",
            **{
                key: value
                for key, value in candidate.items()
                if key not in {"id", "schema_version"}
            },
            rank_process_exits=exits,
            all_rank_processes_exited_before_publication=True,
        )
        p.write_once(output / "report.json", report)
        return report
    except BaseException as error:
        p.write_once(
            output / "failure.json",
            p.record(
                "training_failure",
                **RUN,
                time=p.now(),
                started_id=started["id"],
                error_type=type(error).__name__,
                error=str(error),
                actual_complete=False,
                failed_run_retained=True,
                automatic_retry=False,
                execution_design=EXECUTION_DESIGN,
            ),
        )
        raise


def _smoke_rank(rank, devices, payload):
    output = Path(payload["output"])
    _connect(rank, devices, payload["store"])
    torch.cuda.manual_seed(47)
    generator = torch.cuda.default_generators[0]
    calibration = calibrate_dropout_offsets([31, 1024])
    starts, saved, serial_end = [], [], calibration["initial_offset"]
    for length in (31, 1024):
        starts.append(generator.get_offset())
        value = torch.ones((1, length, HIDDEN_SIZE), device="cuda:0", dtype=torch.bfloat16)
        saved.append(
            [functional.dropout(value, p=0.05, training=True) for _ in range(DROPOUT_CALLS)]
        )
        serial_end = generator.get_offset()
    for index in (1, 0):
        generator.set_offset(starts[index])
        value = torch.ones(
            (1, (31, 1024)[index], HIDDEN_SIZE), device="cuda:0", dtype=torch.bfloat16
        )
        for expected in saved[index]:
            actual = functional.dropout(value, p=0.05, training=True)
            p.require(
                torch.equal(actual, expected),
                "parallel.smoke_native_dropout_masks_exact_after_reorder",
            )
        wanted = (
            starts[index]
            + DROPOUT_CALLS * calibration["per_dropout_call_offsets"][str((31, 1024)[index])]
        )
        p.require(
            generator.get_offset() == wanted, "parallel.smoke_native_generator_progress_exact"
        )
    generator.set_offset(serial_end)
    packed = torch.full((TRAINABLE_PARAMETERS + len(STAT_FIELDS),), rank + 1.0, device="cuda:0")
    dist.all_reduce(packed, op=dist.ReduceOp.SUM)
    p.require(
        bool((packed == sum(range(1, len(devices) + 1))).all()),
        "parallel.smoke_NCCL_SUM_not_average",
    )
    p.write_once(
        output / f"rank_{rank}.json",
        p.record(
            "parallel_smoke_rank",
            rank=rank,
            GPU_UUID=devices[rank],
            native_dropout_masks_match=True,
            original_seed=47,
            hidden_size=HIDDEN_SIZE,
            dtype="bfloat16",
            lengths=[31, 1024],
            dropout_calls_per_shape=DROPOUT_CALLS,
            serial_rng_final_offset=serial_end,
            NCCL_gradient_sized_SUM_pass=True,
            model_loads=0,
            actual_training=False,
        ),
    )
    dist.destroy_process_group()


def smoke(root, output, *, devices):
    """Only two native dropout shapes and one 10 MB NCCL SUM; no Student."""
    root, output = Path(root).resolve(), Path(output).resolve()
    p.require(
        output.is_relative_to(root) and output != root and not output.exists(),
        "parallel.exclusive_smoke_output",
    )
    p.require(
        len(devices) == WORLD_SIZE and len(set(devices)) == WORLD_SIZE,
        "parallel.smoke_eight_devices",
    )
    output.mkdir(parents=True)
    exits = _spawn_and_join(_smoke_rank, devices, {"output": str(output)})
    p.require(all(item["exit_code"] == 0 for item in exits), "parallel.smoke_all_ranks_exited")
    result = p.record(
        "parallel_smoke_report",
        status="PASS",
        rank_process_exits=exits,
        Student_models_loaded=0,
        actual_training=False,
        native_rng_replay=True,
        gradient_sized_NCCL_SUM=True,
    )
    p.write_once(output / "report.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("smoke")
    command.add_argument("--root", required=True)
    command.add_argument("--output", required=True)
    command.add_argument("--devices", required=True, help="eight comma-separated GPU UUIDs")
    args = parser.parse_args()
    result = smoke(args.root, args.output, devices=args.devices.split(","))
    print(p.encode(result).decode(), flush=True)


if __name__ == "__main__":
    main()
