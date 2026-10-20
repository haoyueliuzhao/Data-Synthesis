"""Diagnostic draw accumulators committed atomically with the formal R3 sum.

The formal sum is owned exclusively by the unchanged V32 replay function.
This module observes its real per-response derivatives, accumulates two CPU
diagnostics, and stores all three tensors at the same durable response cursor.
"""
from __future__ import annotations

import hashlib
import io
import json
import time
from pathlib import Path

import finqa_v63_binding as binding

binding.install_scientific_paths()

import torch
import finqa_v19_replay_state as original

DRAW_SEEDS = binding.DRAW_SEEDS
MEAN_TOLERANCES = {
    "atol": 1e-7,
    "rtol": 2e-4,
    "source": "V54_CPU_full_autograd_gradient_comparison",
}
VERSION = "v63_atomic_formal_and_draw_response_checkpoint.v1"


class DrawDiagnosticError(ValueError):
    """A diagnostic math/state failure never permits resource retry."""
    automatic_recovery_allowed = False


def require(ok, message):
    if not ok:
        raise DrawDiagnosticError(message)


def checked_tolerances(value):
    require(value == MEAN_TOLERANCES,
            "draw mean tolerances must match the separately registered V54 gradient comparison")
    return dict(value)


class DrawAccumulator:
    """CPU-only diagnostics; never modifies the returned backend gradient."""

    def __init__(self, theta, work, *, condition_id, denominator, mean_tolerances,
                 monitor=None, cpu_test=False):
        require(cpu_test or callable(monitor), "production draw diagnostics require resource monitor")
        require(denominator > 0 and denominator % 2 == 0
                and (cpu_test or denominator == 700), "registered even feedback denominator required")
        self.theta, self.work = theta, tuple(work)
        self.condition_id, self.denominator = condition_id, denominator
        self.tolerances = checked_tolerances(mean_tolerances)
        self.monitor = monitor or (lambda _event: None)
        self.cursor = 0
        self.counts = {seed: 0 for seed in DRAW_SEEDS}
        self.accumulation_seconds = 0.0
        self.serialization_seconds_this_process = 0.0
        self.serialization_bytes_this_process = 0
        self.mean_check_seconds_this_process = 0.0
        self.observe("before_draw_component_initialization")
        self.draws = {
            seed: {name: torch.zeros(value.shape, dtype=value.dtype, device="cpu")
                   for name, value in theta.items()} for seed in DRAW_SEEDS
        }
        self.component_bytes = sum(v.numel() * v.element_size()
                                   for draw in self.draws.values() for v in draw.values())
        self.observe("after_draw_component_initialization")

    def observe(self, phase, **extra):
        self.monitor(dict(phase=phase, completed_responses=self.cursor,
                          diagnostic_component_bytes=getattr(self, "component_bytes", 0),
                          diagnostic_CPU_memory_is_in_same_worker_RSS=True, **extra))

    def accumulate(self, gradient, *, prompt, targets, expected):
        require(self.cursor < len(self.work), "extra unregistered diagnostic response")
        row = self.work[self.cursor]
        receipt = row["receipt"]
        require(list(prompt) == list(receipt.prompt_input_ids)
                and list(targets) == list(receipt.raw_generated_token_ids)
                and list(expected) == list(receipt.sampled_token_logprobs),
                "draw diagnostic response order differs from formal replay")
        require(set(gradient) == set(self.theta), "draw diagnostic parameter coordinates differ")
        self.observe("before_draw_component_accumulation")
        began = time.monotonic()
        target = self.draws[row["draw_seed"]]
        for name, value in gradient.items():
            require(value.shape == self.theta[name].shape and value.dtype == self.theta[name].dtype
                    and value.device == self.theta[name].device
                    and bool(torch.isfinite(value).all()), "invalid draw diagnostic derivative")
            # This is independent of, and cannot mutate, formal total.add_.
            target[name].add_(value.detach().to("cpu"),
                              alpha=float(row["reward"]) / (self.denominator // 2))
        self.cursor += 1
        self.counts[row["draw_seed"]] += 1
        self.accumulation_seconds += time.monotonic() - began
        self.observe("after_draw_component_accumulation")

    def state(self):
        return dict(
            schema=VERSION, condition_id=self.condition_id, cursor=self.cursor,
            draw_seeds=list(DRAW_SEEDS), formal_denominator=self.denominator,
            draw_denominator=self.denominator // 2,
            response_counts=dict(self.counts), mean_tolerances=self.tolerances,
            accumulation_seconds=self.accumulation_seconds,
            draws={seed: {name: value.detach().clone() for name, value in draw.items()}
                   for seed, draw in self.draws.items()},
        )

    def restore(self, value, cursor):
        require(isinstance(value, dict) and value.get("schema") == VERSION
                and value.get("condition_id") == self.condition_id
                and value.get("cursor") == cursor
                and value.get("draw_seeds") == list(DRAW_SEEDS)
                and value.get("formal_denominator") == self.denominator
                and value.get("draw_denominator") == self.denominator // 2
                and value.get("mean_tolerances") == self.tolerances
                and set(value.get("draws", {})) == set(DRAW_SEEDS),
                "checkpoint draw components are missing or belong to another condition")
        expected_counts = {
            seed: sum(row["draw_seed"] == seed for row in self.work[:cursor])
            for seed in DRAW_SEEDS
        }
        require(value.get("response_counts") == expected_counts,
                "checkpoint draw counts differ from the actual ordered response prefix")
        require(type(value.get("accumulation_seconds")) in (int, float)
                and 0 <= value["accumulation_seconds"] < float("inf"),
                "invalid diagnostic cost history")
        for draw in value["draws"].values():
            require(set(draw) == set(self.theta), "checkpoint draw coordinates differ")
            for name, tensor in draw.items():
                require(tensor.device.type == "cpu"
                        and tensor.shape == self.theta[name].shape
                        and tensor.dtype == self.theta[name].dtype
                        and bool(torch.isfinite(tensor).all()),
                        "invalid saved diagnostic draw tensor")
        self.draws = value["draws"]
        self.cursor, self.counts = cursor, expected_counts
        self.accumulation_seconds = value["accumulation_seconds"]
        self.observe("after_atomic_draw_checkpoint_restore")

    def compare(self, formal):
        """New diagnostic gate, not the historical bitwise formal-gJ gate."""
        self.observe("before_draw_component_mean_check")
        began = time.monotonic()
        passed, maximum, squared, reference_squared = True, 0.0, 0.0, 0.0
        for name, tensor in formal.items():
            reference = tensor.detach().to("cpu")
            mean = (self.draws[DRAW_SEEDS[0]][name] + self.draws[DRAW_SEEDS[1]][name]) * 0.5
            delta = mean.to(torch.float64) - reference.to(torch.float64)
            maximum = max(maximum, float(delta.abs().max()) if delta.numel() else 0.0)
            squared += float(delta.square().sum())
            reference_squared += float(reference.to(torch.float64).square().sum())
            passed &= bool(torch.allclose(mean, reference, atol=self.tolerances["atol"],
                                          rtol=self.tolerances["rtol"]))
        elapsed = time.monotonic() - began
        self.mean_check_seconds_this_process += elapsed
        self.observe("after_draw_component_mean_check")
        report = dict(
            passed=passed, **self.tolerances, maximum_absolute_error=maximum,
            L2_error=squared ** 0.5,
            relative_L2_error=(squared / reference_squared) ** 0.5 if reference_squared else None,
            reference_L2_norm=reference_squared ** 0.5,
            source_is_CPU_gradient_comparison_not_old_production_bitwise_gate=True,
            formal_gradient_replaced_by_component_mean=False,
        )
        require(passed, "diagnostic draw mean failed its registered numerical gate; no tolerance retry")
        return report

    def report(self, formal):
        mean = self.compare(formal)
        return dict(
            schema="v63_complete_draw_gradient_diagnostics.v1",
            condition_id=self.condition_id, completed_responses=self.cursor,
            draw_seeds=list(DRAW_SEEDS), formal_denominator=self.denominator,
            draw_denominator=self.denominator // 2, response_counts=dict(self.counts),
            draw_gradient_digests={str(seed): original.parameter_digest(self.draws[seed])
                                   for seed in DRAW_SEEDS},
            mean_check=mean, component_bytes=self.component_bytes,
            accumulation_wall_seconds_including_previous_attempts=self.accumulation_seconds,
            checkpoint_serialization_seconds_this_process=self.serialization_seconds_this_process,
            checkpoint_serialization_bytes_this_process=self.serialization_bytes_this_process,
            serialization_counts_whole_atomic_payload_not_only_components=True,
            mean_check_seconds_this_process=self.mean_check_seconds_this_process,
            CPU_components_and_serialization_count_toward_worker_RSS=True,
            formal_response_arithmetic_unchanged=True, old_gJ_replayed_for_diagnostics=False,
        )


class ComponentCheckpoints(original.ReplayCheckpoints):
    """One immutable state.pt holds total, diagnostics, cursor, RNG and binding."""

    def __init__(self, root, scientific_binding, theta, *, accumulator):
        super().__init__(root, scientific_binding, theta)
        self.accumulator = accumulator

    def save(self, cursor, total, accounting, *, complete=False):
        require(cursor == self.accumulator.cursor
                and accounting.get("responses_replayed", 0) == cursor,
                "formal and diagnostic cursors differ; refusing a split checkpoint")
        self.accumulator.observe("before_atomic_draw_checkpoint")
        began = time.monotonic()
        state = dict(
            total={name: value.detach().cpu().clone() for name, value in total.items()},
            accounting=dict(accounting), cursor=cursor, binding=self.binding,
            rng_digest=original._tree_digest(original._rng()),
            draw_components=self.accumulator.state(),
        )
        stream = io.BytesIO()
        torch.save(state, stream)
        raw = stream.getvalue()
        record = original.bound(dict(
            schema="v19_response_boundary_checkpoint.v1", at=original.now(),
            cursor=cursor, binding=self.binding,
            state_sha256=hashlib.sha256(raw).hexdigest(),
            state_digest=original._tree_digest(state),
            response_prefix_complete=True, full_replay_complete=complete,
            optimizer_steps_performed=0, no_feedback_generation=True,
            draw_components_schema=VERSION, formal_and_draws_atomically_committed=True,
            draw_response_counts={str(seed): count for seed, count in self.accumulator.counts.items()},
        ))
        self.accumulator.serialization_seconds_this_process += time.monotonic() - began
        self.accumulator.serialization_bytes_this_process += len(raw)
        self.accumulator.observe("after_atomic_draw_checkpoint_serialization",
                                 serialized_state_bytes=len(raw))
        directory = self.root / f"response{cursor:06d}"
        if directory.exists():
            old, _state = self.read(directory)
            require(old["cursor"] == cursor and old["state_digest"] == record["state_digest"],
                    "an existing joint replay checkpoint cannot be overwritten")
            return old
        original.write_immutable_artifact_directory(
            directory, {"state.pt": raw, "record.json": original.encode(record)})
        return record

    def read(self, directory):
        record, state = super().read(directory)
        require(record.get("draw_components_schema") == VERSION
                and record.get("formal_and_draws_atomically_committed") is True,
                "formal-only historical checkpoint cannot restore V63 draw diagnostics")
        self.accumulator.restore(state.get("draw_components"), state["cursor"])
        require(record.get("draw_response_counts") ==
                {str(seed): count for seed, count in self.accumulator.counts.items()},
                "atomic draw checkpoint metadata differs from actual tensors")
        self.accumulator.compare(state["total"])
        return record, state
