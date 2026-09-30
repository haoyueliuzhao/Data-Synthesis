"""Genuine state-free common Static prefix, hard-stopped before any intervention.

Only package counts and whole-package target lengths enter the loss. There is no
temporary partition, VerifiedPool adapter, pi, feedback collector or dev path.
After a complete genuine mapping exists, an explicit no-update migration can
carry the saved model/Adam/RNG/cursor into the existing five-arm shared format.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import io
import json
import math
import os
import re
from collections import Counter
from fractions import Fraction
from importlib.metadata import version
from pathlib import Path

import torch

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import trajectory_consumer

from .calibration import gpu_inventory, now
from .contracts import digest
from .providers import parameter_digest, tokenizer_binding
from .v6_collection import bound, require
from .v7_base_evaluation import ORIGIN
from .v8_training_driver import (
    _json,
    _publish,
    _restore_rng,
    _rng,
    _tree_digest,
    validate_student_adapters,
)
from .v9_conditional_training import build_task_schedule, execution_plan

SEEDS = (11, 29, 47)
STATE_SCHEMA = "v15_state_free_prior_prefix_state.v1"
LAUNCH_SCHEMA = "v15_state_free_prior_prefix_launcher.v1"
LOSS_RULE = "1/(actual_B_j*n_x*whole_package_L_P)"
COMMON_COMPUTATION_FIELDS = (
    "seed",
    "schedule",
    "step",
    "adapter_binding",
    "frozen_base_digest",
    "parameters",
    "buffers",
    "optimizer",
    "rng",
    "model_training",
    "execution_plan",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_bound(path):
    value = json.loads(Path(path).read_bytes())
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "bound V15 prefix record changed",
    )
    return value


def file_ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha(path))


def package_inventory(pool):
    """Canonical state-free package and positive-row order used by both consumers."""
    fields = ("package_id", "task_id", "whole_package_target_tokens", "fused")
    packages, row_hashes = [], {}
    for item in pool.packages:
        package = {k: item[k] for k in fields}
        require(
            package["fused"] is False
            and type(package["whole_package_target_tokens"]) is int
            and package["whole_package_target_tokens"] > 0,
            "unfused original positive package required",
        )
        rows = tuple(pool.row_arrays(package["package_id"]))
        require(
            rows and all(row["target_ids"] for row in rows),
            "same positive-response row consumer order required; skip zero-target forwards",
        )
        require(
            sum(len(row["target_ids"]) for row in rows) == package["whole_package_target_tokens"],
            "complete whole-package supervised-token denominator required",
        )
        row_hashes[package["package_id"]] = [
            row["row_sha256"] if "row_sha256" in row else digest(row) for row in rows
        ]
        packages.append(package)
    require(
        len({p["package_id"] for p in packages}) == len(packages),
        "unique original packages required",
    )
    require(
        set(p["task_id"] for p in packages) == set(pool.task_ids),
        "all original tasks require package support",
    )
    return dict(
        task_ids=list(pool.task_ids), packages=packages, positive_row_sha256_by_package=row_hashes
    )


def direct_batch_examples(pool, task_ids):
    """Compile direct package-mean coefficients, without constructing any state."""
    tasks = list(task_ids)
    require(
        tasks
        and len(tasks) <= 5
        and len(set(tasks)) == len(tasks)
        and set(tasks) <= set(pool.task_ids),
        "registered real complete-task batch required",
    )
    counts = Counter(p["task_id"] for p in pool.packages)
    by_task = {t: [] for t in tasks}
    for item in pool.packages:
        require("state_id" not in item, "state-free prefix cannot accept hidden temporary states")
        if item["task_id"] in by_task:
            by_task[item["task_id"]].append(item)
    result = []
    for draw, task in enumerate(tasks):
        for package in by_task[task]:
            coefficient = Fraction(
                1, len(tasks) * counts[task] * package["whole_package_target_tokens"]
            )
            result.append(
                dict(
                    **package,
                    target_token_coefficient=str(coefficient),
                    coefficient_float=float(coefficient),
                    task_draw_index=draw,
                )
            )
    return result


def memory_snapshot(device):
    if torch.device(device).type != "cuda" or not torch.cuda.is_initialized():
        return dict(
            device=str(device),
            cuda_memory_measured=False,
            peak_allocated_bytes=None,
            peak_reserved_bytes=None,
        )
    try:
        return dict(
            device=str(device),
            cuda_memory_measured=True,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(device),
            peak_reserved_bytes=torch.cuda.max_memory_reserved(device),
            current_allocated_bytes=torch.cuda.memory_allocated(device),
            current_reserved_bytes=torch.cuda.memory_reserved(device),
        )
    except Exception as exc:
        return dict(
            device=str(device),
            cuda_memory_measured=False,
            memory_read_error=f"{type(exc).__name__}: {exc}",
        )


def failure_kind(error):
    message = str(error).lower()
    if isinstance(error, (MemoryError, torch.cuda.OutOfMemoryError)) or "out of memory" in message:
        return "resource_failure"
    if any(
        word in message
        for word in ("nonfinite", "non-finite", "finite_update_loss", "nan", "infinity")
    ):
        return "numerical_failure"
    if isinstance(error, OSError):
        return "checkpoint_or_io_failure"
    return "execution_or_contract_failure"


def _state(path, device="cpu"):
    path = Path(path)
    summary = json.loads((path / "record.json").read_bytes())
    raw = (path / "state.pt").read_bytes()
    require(hashlib.sha256(raw).hexdigest() == summary["state_sha256"], "checkpoint bytes changed")
    state = torch.load(io.BytesIO(raw), map_location=device, weights_only=False)
    require(_tree_digest(state) == summary["actual_state_digest"], "checkpoint content changed")
    return state, summary


def checkpoint_ref(path):
    path = Path(path).resolve()
    summary = json.loads((path / "record.json").read_bytes())
    return dict(
        path=str(path),
        state_sha256=summary["state_sha256"],
        actual_state_digest=summary["actual_state_digest"],
        step=summary["step"],
        phase=summary["phase"],
    )


def latest_checkpoint(directory):
    candidates = []
    for path in Path(directory).glob("step*_*"):
        match = re.fullmatch(r"step([0-9]+)_(initial|step)", path.name)
        require(match is not None and path.is_dir(), "unknown prefix checkpoint coordinate")
        candidates.append((int(match[1]), match[2] == "step", path))
    if not candidates:
        return None
    path = max(candidates, key=lambda row: row[:2])[2]
    summary = json.loads((path / "record.json").read_bytes())
    require(
        sha(path / "state.pt") == summary["state_sha256"], "last committed prefix bytes changed"
    )
    return path


class PrefixDriver:
    """One real update and durable commit per call, with no intervention methods."""

    def __init__(
        self,
        model,
        optimizer,
        pool,
        *,
        root,
        seed,
        device="cpu",
        tokenizer=None,
        adapter_scope=None,
        cpu_control=False,
    ):
        require(
            seed in SEEDS and type(optimizer) is torch.optim.AdamW,
            "fixed seed and real AdamW required",
        )
        require(
            not any(hasattr(pool, k) for k in ("pi", "chi", "prior", "_manifest")),
            "prefix pool must be genuinely state-free, not a fake full training adapter",
        )
        require(all("state_id" not in p for p in pool.packages), "no temporary package states")
        production = bool(pool.production_verified)
        require(
            not production or torch.device(device).type == "cuda",
            "registered production prefix uses the original CUDA Student execution",
        )
        require(
            production or (cpu_control is True and torch.device(device).type == "cpu"),
            "unverified material may only run an explicitly synthetic CPU control",
        )
        require(
            not production
            or (
                pool.prefix_only is True
                and pool.full_training_admitted is False
                and len(pool.task_ids) == 744
                and len(pool.packages) == 2468
            ),
            "production scope is exactly the fixed whole-population prior prefix",
        )
        self.model, self.optimizer, self.pool = model, optimizer, pool
        self.root, self.seed, self.device = Path(root), seed, device
        self.parameters = {n: p for n, p in model.named_parameters() if p.requires_grad}
        require(
            self.parameters
            and {id(p) for g in optimizer.param_groups for p in g["params"]}
            == {id(p) for p in self.parameters.values()},
            "actual trainable optimizer coordinates required",
        )
        self.adapter_binding = None
        if production:
            require(
                tokenizer is not None
                and tokenizer_binding(tokenizer) == tuple(pool.tokenizer_binding),
                "actual tokenizer differs from complete fixed encoding",
            )
            self.adapter_binding = validate_student_adapters(model, adapter_scope)
            for group in optimizer.param_groups:
                require(
                    (group["lr"], group["betas"], group["eps"], group["weight_decay"])
                    == (1e-4, (0.9, 0.999), 1e-8, 0)
                    and not any(
                        group.get(k, False)
                        for k in (
                            "maximize",
                            "amsgrad",
                            "fused",
                            "capturable",
                            "differentiable",
                            "foreach",
                        )
                    ),
                    "original fixed AdamW scalar execution configuration required",
                )
        self.execution_plan = execution_plan(len(pool.task_ids))
        require(
            pool.execution_plan == self.execution_plan, "original dynamic task coordinates changed"
        )
        self.schedule = build_task_schedule(pool.task_ids, seed)
        self.stop_step = self.execution_plan["shared_step"]
        require(not production or self.stop_step == 298, "production prefix must hard-stop at298")
        self.inventory = package_inventory(pool)
        self.execution_order_id = digest(self.inventory)
        self.base_digest = parameter_digest(
            {n: p for n, p in model.named_parameters() if not p.requires_grad}
        )
        self.step_index = self.committed_step = 0
        self.initialized = self.tainted = False
        self.consumption = dict(
            updates=0, packages=0, response_rows=0, supervised_tokens=0, sequence_tokens=0
        )
        self.last_event = {}

    def _payload(self):
        return dict(
            schema=STATE_SCHEMA,
            seed=self.seed,
            pool_id=self.pool.cache_id,
            prefix_binding_ref=self.pool.prefix_binding_ref,
            material_order_id=self.pool.material_order_id,
            execution_order_id=self.execution_order_id,
            schedule=self.schedule,
            execution_plan=self.execution_plan,
            step=self.step_index,
            stop_step=self.stop_step,
            prefix_only=True,
            state_partition_used=False,
            distribution_fields_present=False,
            adapter_binding=self.adapter_binding,
            frozen_base_digest=self.base_digest,
            parameters={n: p.detach().cpu().clone() for n, p in self.parameters.items()},
            buffers={n: p.detach().cpu().clone() for n, p in self.model.named_buffers()},
            optimizer=copy.deepcopy(self.optimizer.state_dict()),
            rng=_rng(),
            model_training=self.model.training,
            consumption=copy.deepcopy(self.consumption),
        )

    def commit(self, phase, evidence=None):
        payload, buffer = self._payload(), io.BytesIO()
        torch.save(payload, buffer)
        raw = buffer.getvalue()
        directory = self.root / f"step{self.step_index:04d}_{phase}"
        summary = dict(
            schema="v15_prior_prefix_checkpoint.v1",
            step=self.step_index,
            phase=phase,
            seed=self.seed,
            pool_id=self.pool.cache_id,
            state_sha256=hashlib.sha256(raw).hexdigest(),
            actual_state_digest=_tree_digest(payload),
            schedule_sha256=self.schedule["schedule_sha256"],
            material_order_id=self.pool.material_order_id,
            execution_order_id=self.execution_order_id,
            contains_actual_theta_Adam_RNG_cursor=True,
            contains_state_or_pi=False,
            evidence=evidence,
        )
        write_immutable_artifact_directory(
            directory, {"state.pt": raw, "record.json": _json(summary)}
        )
        self.committed_step = self.step_index
        return directory

    def restore(self, directory):
        # AdamW's non-capturable step tensors and RNG records remain on CPU;
        # load_state_dict moves parameter moments to each actual parameter device.
        state, _ = _state(directory, "cpu")
        require(
            state["schema"] == STATE_SCHEMA
            and not any(k in state for k in ("pi", "prior", "chi", "outer_done"))
            and state["pool_id"] == self.pool.cache_id
            and state["prefix_binding_ref"] == self.pool.prefix_binding_ref
            and state["material_order_id"] == self.pool.material_order_id
            and state["execution_order_id"] == self.execution_order_id
            and state["seed"] == self.seed
            and state["schedule"] == self.schedule
            and state["execution_plan"] == self.execution_plan
            and state["stop_step"] == self.stop_step
            and state["frozen_base_digest"] == self.base_digest
            and state["adapter_binding"] == self.adapter_binding
            and 0 <= state["step"] <= self.stop_step,
            "prefix checkpoint/material/seed/scope changed",
        )
        with torch.no_grad():
            for name, value in state["parameters"].items():
                self.parameters[name].copy_(value)
            buffers = dict(self.model.named_buffers())
            for name, value in state["buffers"].items():
                buffers[name].copy_(value)
        self.optimizer.load_state_dict(state["optimizer"])
        _restore_rng(state["rng"])
        self.model.train(state["model_training"])
        self.step_index = self.committed_step = state["step"]
        self.consumption = copy.deepcopy(state["consumption"])
        self.initialized, self.tainted = True, False
        return state

    def verify_first_committed_step(self):
        require(
            self.step_index == self.committed_step == 1 and not self.tainted,
            "first-step acceptance uses exactly the saved formal first update",
        )
        require(
            all(torch.isfinite(p).all().item() for p in self.parameters.values()),
            "nonfinite parameters after actual first AdamW update",
        )
        require(
            all(
                torch.isfinite(v).all().item()
                for state in self.optimizer.state.values()
                for v in state.values()
                if isinstance(v, torch.Tensor)
            ),
            "nonfinite Adam state after actual first update",
        )
        before = _tree_digest(self._payload())
        checkpoint = self.root / "step0001_step"
        self.restore(checkpoint)
        after = _tree_digest(self._payload())
        require(before == after, "formal first-step model/Adam/RNG/cursor restore differs")
        evidence = bound(
            dict(
                schema="v15_actual_first_step_acceptance.v1",
                checkpoint=checkpoint_ref(checkpoint),
                seed=self.seed,
                pre_restore_digest=before,
                post_restore_digest=after,
                same_actual_state=True,
                finite_parameters_and_Adam_state=True,
                finite_gradients_checked_by_original_error_if_nonfinite_clip=True,
                first_batch=self.schedule["batches"][0],
                separate_validation_update=False,
                repeat_first_update=False,
                additional_optimizer_steps=0,
                CUDA_acceptance=self.pool.production_verified,
                peak_memory=memory_snapshot(self.device),
            )
        )
        _publish(self.root / "first_step_acceptance", evidence)
        return evidence

    def step(self):
        require(not self.tainted, "uncommitted failure requires explicit committed-state restore")
        require(
            self.step_index < self.stop_step,
            "prior prefix hard stop reached; no branch or outer update",
        )
        if not self.initialized:
            require(
                not self.root.exists(), "existing prefix needs explicit committed-state restore"
            )
            self.commit("initial")
            self.initialized = True
        attempted = self.step_index + 1
        batch = self.schedule["batches"][self.step_index]
        examples = direct_batch_examples(self.pool, batch["task_ids"])
        self.tainted, self.last_event = True, {}
        optimizer_started = False

        def events(event):
            nonlocal optimizer_started
            self.last_event = copy.deepcopy(event)
            optimizer_started = optimizer_started or event["event"] == "before_optimizer_step"

        try:
            self.model.train()
            original = trajectory_consumer.execute_update(
                self.model,
                self.optimizer,
                examples,
                {"tasks": batch["task_ids"]},
                pool="finqa",
                arm="shared_prior_prefix",
                device=self.device,
                trajectory_cache=self.pool,
                event_sink=events,
            )
            require(
                original["optimizer_step_calls"]
                == original["clip_calls"]
                == original["zero_grad_calls"]
                == 1,
                "one real finite-gradient clip and AdamW update per registered batch",
            )
            require(
                math.isfinite(original["weighted_loss"])
                and math.isfinite(original["preclip_gradient_norm"]),
                "nonfinite actual update report",
            )
            report = {
                k: v
                for k, v in original.items()
                if k not in ("id", "schema_version", "loss_rule", "loss_domain", "execution_design")
            }
            report.update(
                schema="v15_actual_state_free_prefix_update.v1",
                loss_rule=LOSS_RULE,
                loss_domain="original approved response rows/actions/EOS; whole-package L_P",
                execution_design="canonical_original_unfused_response_rows",
                underlying_consumer_id=original["id"],
                actual_batch_size=len(batch["task_ids"]),
                task_batch=copy.deepcopy(batch),
                additional_batch_division=False,
                state_or_pi_used=False,
                whole_population_retained=True,
                peak_memory=memory_snapshot(self.device),
                actual_parameter_update=True,
                CPU_control_only=not self.pool.production_verified,
            )
            report = bound(report)
            self.step_index = attempted
            self.consumption["updates"] += 1
            for field, key in (
                ("packages", "packages_completed"),
                ("response_rows", "rows_completed"),
                ("supervised_tokens", "target_tokens"),
                ("sequence_tokens", "sequence_tokens"),
            ):
                self.consumption[field] += report[key]
            self.commit("step", report)
            self.tainted = False
            if self.step_index == 1:
                self.verify_first_committed_step()
            return report
        except BaseException as exc:
            self.tainted = True
            failures = self.root / "failures"
            number = len(list(failures.glob("attempt*"))) + 1
            _publish(
                failures / f"attempt{number:03d}",
                bound(
                    dict(
                        schema="v15_prefix_update_failure.v1",
                        at=now(),
                        seed=self.seed,
                        attempted_step=attempted,
                        last_committed_step=self.committed_step,
                        failure_kind=failure_kind(exc),
                        error_type=type(exc).__name__,
                        error=str(exc),
                        last_consumer_event=self.last_event,
                        optimizer_step_started=optimizer_started,
                        failure_after_durable_update=self.committed_step >= attempted,
                        uncommitted_optimizer_update_possible=optimizer_started
                        and self.committed_step < attempted,
                        failed_update_counted_as_committed=False,
                        retry_performed=False,
                        peak_memory=memory_snapshot(self.device),
                        recovery="explicit restore of last durable checkpoint",
                    )
                ),
            )
            raise

    def run_until(self, stop=None):
        stop = self.stop_step if stop is None else stop
        require(
            type(stop) is int and self.step_index <= stop <= self.stop_step,
            "only the predeclared common prefix interval may execute",
        )
        if self.step_index == 1 and not (self.root / "first_step_acceptance/record.json").exists():
            self.verify_first_committed_step()
        while self.step_index < stop:
            self.step()
        return dict(
            seed=self.seed,
            committed_step=self.committed_step,
            hard_stop=self.stop_step,
            consumption=copy.deepcopy(self.consumption),
            state_or_pi_used=False,
            feedback_calls=0,
            dev_calls=0,
            branches_started=0,
            peak_memory=memory_snapshot(self.device),
        )


def migrate_prefix_checkpoint(
    prefix_checkpoint, prefix_pool, full_pool, output_dir, *, cpu_control=False
):
    """Add genuine completed-mapping prior metadata, preserving every computation tensor."""
    prefix, original_record = _state(prefix_checkpoint)
    require(
        prefix["schema"] == STATE_SCHEMA
        and prefix["pool_id"] == prefix_pool.cache_id
        and prefix["prefix_binding_ref"] == prefix_pool.prefix_binding_ref
        and prefix["step"]
        == prefix["stop_step"]
        == execution_plan(len(prefix_pool.task_ids))["shared_step"],
        "only the unique completed registered prefix may migrate",
    )
    require(
        not any(k in prefix for k in ("pi", "prior", "chi", "outer_done")),
        "prefix must not contain temporary states/distributions",
    )
    require(
        (prefix_pool.production_verified and full_pool.production_verified and not cpu_control)
        or (
            cpu_control is True
            and not prefix_pool.production_verified
            and not full_pool.production_verified
        ),
        "genuine production materials or explicitly separate synthetic CPU control required",
    )
    require(
        full_pool.support_manifest["material_complete"] is True
        and full_pool.support_manifest["exploratory_training_admitted"] is True
        and full_pool.conditional_scope_verified is True,
        "all real mappings and complete five-arm material must be admitted before migration",
    )
    require(
        prefix_pool.material_order_id == full_pool.material_order_id == prefix["material_order_id"]
        and tuple(prefix_pool.tokenizer_binding) == tuple(full_pool.tokenizer_binding)
        and full_pool.prefix_binding_ref == prefix_pool.prefix_binding_ref
        and package_inventory(prefix_pool) == package_inventory(full_pool)
        and prefix["execution_order_id"] == digest(package_inventory(prefix_pool))
        and prefix["schedule"] == build_task_schedule(full_pool.task_ids, prefix["seed"])
        and prefix["execution_plan"] == full_pool.execution_plan,
        "state labels may change, but task/package/row/target/tokenizer/order cannot",
    )
    first = read_bound(Path(prefix_checkpoint).parent / "first_step_acceptance/record.json")
    require(
        first["same_actual_state"] is True
        and first["seed"] == prefix["seed"]
        and first["checkpoint"] == checkpoint_ref(Path(prefix_checkpoint).parent / "step0001_step")
        and first["repeat_first_update"] is False,
        "actual first-update save/restore acceptance required",
    )
    prior = copy.deepcopy(full_pool._manifest.registration.pi0)
    frequencies = {
        task: Counter(p["state_id"] for p in full_pool.packages if p["task_id"] == task)
        for task in full_pool.task_ids
    }
    require(
        all(
            set(prior[task]) == set(counts)
            and all(
                Fraction(str(prior[task][state])) == Fraction(n, sum(counts.values()))
                for state, n in counts.items()
            )
            for task, counts in frequencies.items()
        ),
        "migration requires the exact empirical-frequency prior, not another state prior",
    )
    # These are the first distribution fields, introduced only after genuine mapping admission.
    migrated = {k: copy.deepcopy(prefix[k]) for k in COMMON_COMPUTATION_FIELDS}
    migrated.update(
        schema="v8_committed_training_state.v1",
        arm="shared",
        pool_id=full_pool.cache_id,
        prior=prior,
        pi=copy.deepcopy(prior),
        outer_done=[],
    )
    before = _tree_digest({k: prefix[k] for k in COMMON_COMPUTATION_FIELDS})
    after = _tree_digest({k: migrated[k] for k in COMMON_COMPUTATION_FIELDS})
    require(before == after, "migration altered actual model/Adam/RNG/cursor")
    buffer = io.BytesIO()
    torch.save(migrated, buffer)
    raw = buffer.getvalue()
    proof = bound(
        dict(
            schema="v15_completed_prefix_migration.v1",
            source_prefix=checkpoint_ref(prefix_checkpoint),
            prefix_binding=prefix_pool.prefix_binding_ref,
            full_pool_id=full_pool.cache_id,
            material_order_id=prefix_pool.material_order_id,
            actual_computation_digest=before,
            original_prefix_contained_pi=False,
            genuine_completed_mapping_prior_added=True,
            optimizer_steps_performed=0,
            prefix_retrained=False,
            first_outer_not_executed=True,
        )
    )
    summary = dict(
        step=prefix["step"],
        phase="step",
        arm="shared",
        seed=prefix["seed"],
        state_sha256=hashlib.sha256(raw).hexdigest(),
        actual_state_digest=_tree_digest(migrated),
        pool_id=full_pool.cache_id,
        schedule_sha256=prefix["schedule"]["schedule_sha256"],
        evidence=proof,
        checkpoint_contains_actual_model_Adam_RNG_pi=True,
        source_prefix_checkpoint_schema=original_record["schema"],
    )
    destination = Path(output_dir) / f"step{prefix['step']:04d}_step"
    write_immutable_artifact_directory(
        destination, {"state.pt": raw, "record.json": _json(summary)}
    )
    return proof | dict(migrated_checkpoint=checkpoint_ref(destination))


def source_bindings():
    root = Path(__file__).parent
    names = (
        "v15_prefix_training.py",
        "v15_prefix_material.py",
        "v8_training_driver.py",
        "v9_conditional_training.py",
        "v9_training_launcher.py",
        "v7_base_evaluation.py",
        "providers.py",
        "contracts.py",
    )
    sources = {name: sha(root / name) for name in names}
    sources["trajectory_consumer.py"] = sha(Path(trajectory_consumer.__file__))
    sources["fixed_kernel/protocol.py"] = sha(
        Path(trajectory_consumer.__file__).parent / "protocol.py"
    )
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student import model, plan

    sources["pq_student/model.py"] = sha(Path(model.__file__))
    sources["pq_student/plan.py"] = sha(Path(plan.__file__))
    return sources


def numerical_runtime():
    return {name: version(name) for name in ("torch", "transformers", "tokenizers")}


def register(prefix_binding, output, *, allowed_gpu_indices=(0,), assets_protocol=ORIGIN):
    """Prospective prefix-only launch registration; no GPU query or allocation."""
    from .v15_prefix_material import load_prefix_pool

    output = Path(output).resolve()
    require(
        not (output / "registration/record.json").exists(),
        "prefix launcher registration already exists",
    )
    pool = load_prefix_pool(prefix_binding)
    assets = read_bound(assets_protocol)
    material = read_bound(prefix_binding)
    require(
        material["original_student_assets"] == {**file_ref(assets_protocol), "id": assets["id"]},
        "prefix launcher must use exactly the material-bound original Student assets",
    )
    require(
        pool.production_verified
        and pool.prefix_only
        and not pool.full_training_admitted
        and len(pool.task_ids) == 744
        and len(pool.packages) == 2468,
        "whole fixed prefix-only binding required",
    )
    indices = list(allowed_gpu_indices)
    require(
        indices
        and len(set(indices)) == len(indices)
        and all(type(i) is int and i >= 0 for i in indices),
        "explicit allowed GPU scope required",
    )
    plan = bound(
        dict(
            schema=LAUNCH_SCHEMA,
            at=now(),
            prefix_binding=file_ref(prefix_binding),
            prefix_pool_id=pool.cache_id,
            material_order_id=pool.material_order_id,
            execution_order_id=digest(package_inventory(pool)),
            assets_protocol=file_ref(assets_protocol),
            assets_protocol_id=assets["id"],
            execution_plan=pool.execution_plan,
            source_bindings=source_bindings(),
            numerical_runtime=numerical_runtime(),
            seeds=list(SEEDS),
            stop_step=298,
            student=dict(
                model="Qwen2.5-7B-Instruct",
                base_dtype="bfloat16",
                base_frozen=True,
                adapter="repository.LowRankLinear",
                targets=["q_proj", "v_proj"],
                rank=8,
                alpha=16,
                dropout=0.05,
                adapter_dtype="float32",
                old_adapter_loaded=False,
            ),
            optimizer=dict(
                name="AdamW",
                lr=1e-4,
                betas=[0.9, 0.999],
                eps=1e-8,
                weight_decay=0,
                foreach=False,
                fused=False,
            ),
            loss_coefficient=LOSS_RULE,
            state_or_pi_required=False,
            device_policy=dict(
                allowed_gpu_indices=indices,
                minimum_free_mib=24576,
                free_memory_is_heuristic_not_cuda_acceptance=True,
                no_placeholder=True,
                no_waiting_with_loaded_model=True,
            ),
            first_registered_update_is_formal_step1=True,
            first_step_restore_check=True,
            feedback_calls=0,
            dev_calls=0,
            branch_permission=False,
            full_five_arm_admission=False,
            explicit_resume_required=True,
            API_calls=0,
        )
    )
    _publish(output / "registration", plan)
    return plan


def checked_launch(output):
    from .v15_prefix_material import load_prefix_pool

    plan = read_bound(Path(output) / "registration/record.json")
    require(
        plan["schema"] == LAUNCH_SCHEMA and plan["source_bindings"] == source_bindings(),
        "frozen prefix execution source changed",
    )
    require(
        plan["numerical_runtime"] == numerical_runtime(), "registered numerical runtime changed"
    )
    for key in ("prefix_binding", "assets_protocol"):
        require(sha(plan[key]["path"]) == plan[key]["sha256"], "registered source file changed")
    pool = load_prefix_pool(plan["prefix_binding"]["path"])
    require(
        pool.cache_id == plan["prefix_pool_id"]
        and pool.material_order_id == plan["material_order_id"]
        and digest(package_inventory(pool)) == plan["execution_order_id"],
        "prefix material/order changed",
    )
    assets = read_bound(plan["assets_protocol"]["path"])
    require(assets["id"] == plan["assets_protocol_id"], "original Student asset source changed")
    return plan, pool, assets


def _execute_loaded_seed(output, plan, pool, seed, components, *, resume):
    model, tokenizer, optimizer, scope, fresh = components
    seed_root = Path(output) / f"seed{seed}"
    shared_root = seed_root / "shared"
    checkpoint = latest_checkpoint(shared_root)
    driver = PrefixDriver(
        model,
        optimizer,
        pool,
        root=shared_root,
        seed=seed,
        device="cuda:0",
        tokenizer=tokenizer,
        adapter_scope=scope,
    )
    if checkpoint is None:
        _publish(seed_root / "fresh_initialization", fresh)
    else:
        require(resume, "existing actual prefix requires explicit resume")
        driver.restore(checkpoint)
    actual = driver.run_until()
    require(
        actual["committed_step"] == 298 and actual["consumption"]["updates"] == 298,
        "unique original common prefix must stop after298 committed updates",
    )
    result = bound(
        dict(
            schema="v15_prior_prefix_seed_result.v1",
            protocol_id=plan["id"],
            prefix_pool_id=pool.cache_id,
            seed=seed,
            checkpoint=checkpoint_ref(latest_checkpoint(shared_root)),
            first_step_acceptance=file_ref(shared_root / "first_step_acceptance/record.json"),
            actual=actual,
            complete_prefix=True,
            no_temporary_states=True,
            full_five_arm_started=False,
            feedback_calls=0,
            dev_calls=0,
            GPU_may_be_released_while_mapping_incomplete=True,
        )
    )
    _publish(seed_root / "result", result)
    return result


def run_seed(output, seed, gpu_index, *, resume=False):
    from .v9_training_launcher import _load_components, eligible_gpu

    require(seed in SEEDS, "registered paired seed required")
    output = Path(output).resolve()
    plan, pool, assets = checked_launch(output)
    seed_root = output / f"seed{seed}"
    require(resume or not seed_root.exists(), "existing seed requires explicit resume")
    locks = output / "locks"
    locks.mkdir(exist_ok=True)
    with (locks / f"seed{seed}.lock").open("a") as seed_lock:
        fcntl.flock(seed_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        row = eligible_gpu(plan, gpu_index, gpu_inventory())
        with (locks / ("gpu-" + digest(row["uuid"]) + ".lock")).open("a") as gpu_lock:
            fcntl.flock(gpu_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            current = eligible_gpu(plan, gpu_index, gpu_inventory())
            require(current["uuid"] == row["uuid"], "GPU identity changed before actual load")
            require(
                not torch.cuda.is_initialized()
                or os.environ.get("CUDA_VISIBLE_DEVICES") == row["uuid"],
                "initialized CUDA process cannot remap GPUs",
            )
            os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
            os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
            attempts = seed_root / "launch_attempts"
            attempt = attempts / f"attempt{len(list(attempts.glob('attempt*'))) + 1:03d}"
            _publish(
                attempt / "intent",
                bound(
                    dict(
                        at=now(),
                        protocol_id=plan["id"],
                        seed=seed,
                        explicit_resume=resume,
                        pid=os.getpid(),
                        gpu_observed=current,
                        no_GPU_placeholder=True,
                    )
                ),
            )
            components = None
            try:
                components = _load_components(assets, seed)
                _publish(
                    attempt / "loaded",
                    bound(
                        dict(at=now(), seed=seed, actual_load_peak_memory=memory_snapshot("cuda:0"))
                    ),
                )
                torch.cuda.reset_peak_memory_stats()
                return _execute_loaded_seed(output, plan, pool, seed, components, resume=resume)
            except BaseException as failure:
                _publish(
                    attempt / "stopped",
                    bound(
                        dict(
                            at=now(),
                            error_type=type(failure).__name__,
                            error=str(failure),
                            failure_kind=failure_kind(failure),
                            retry_performed=False,
                            last_committed_checkpoint=(
                                checkpoint_ref(latest_checkpoint(seed_root / "shared"))
                                if latest_checkpoint(seed_root / "shared")
                                else None
                            ),
                            recovery=(
                                "explicit resume restores durable theta/Adam/RNG/cursor; "
                                "never repeat a successful committed update"
                            ),
                            CUDA_acceptance_not_assumed=True,
                            peak_memory=memory_snapshot("cuda:0"),
                        )
                    ),
                )
                raise
            finally:
                if components is not None:
                    del components
                if torch.cuda.is_initialized():
                    torch.cuda.empty_cache()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run-seed", "resume-seed"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prefix-binding", type=Path)
    parser.add_argument("--allowed-gpus", type=int, nargs="+", default=[0])
    parser.add_argument("--seed", type=int, choices=SEEDS)
    parser.add_argument("--gpu-index", type=int)
    args = parser.parse_args(argv)
    if args.action == "register":
        require(args.prefix_binding is not None, "registered prefix material binding required")
        result = register(args.prefix_binding, args.output, allowed_gpu_indices=args.allowed_gpus)
    else:
        require(
            args.seed is not None and args.gpu_index is not None, "one actual seed and GPU required"
        )
        result = run_seed(
            args.output, args.seed, args.gpu_index, resume=args.action == "resume-seed"
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
