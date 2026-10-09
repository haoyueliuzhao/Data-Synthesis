"""Bounded V19 storage adapters and actual ordered response-boundary recovery.

R0 remains the separately imported frozen legacy path.  R1/R2 reuse V19's
fixed-eight arithmetic bytecode and storage implementations; only R1's full KV
destination differs.  The accumulation below is the V19 ordered accumulation
with a cooperative pause boundary, not a new logP/gradient implementation.
"""

from __future__ import annotations

import contextlib
import math
import signal
import sys
import time
from collections import Counter
from pathlib import Path

import finqa_v19_optimized_replay as optimized
import finqa_v19_replay_state as state
import torch

from trusted_synthesis.finance_research.calibration import now, status
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.feedback import episode_key, seal_feedback_cohort
from trusted_synthesis.finance_research.providers import parameter_digest
from trusted_synthesis.finance_research.v6_collection import require
from trusted_synthesis.finance_research.v8_training_driver import _rng, _tree_digest

GIB = 1024**3
BACKEND_VERSION = "v32_v19_storage_adapters_response_boundary.v1"


class PauseRequest:
    """Signal callbacks set flags only; no CUDA, I/O or checkpoint operations."""

    def __init__(self):
        self.requested = False
        self.reason = None

    def request(self, reason="requested"):
        self.reason = reason
        self.requested = True

    def signal_handler(self, signum, _frame):
        self.reason = f"signal:{signum}"
        self.requested = True

    @contextlib.contextmanager
    def signals(self, numbers=(signal.SIGTERM, signal.SIGINT)):
        old = {number: signal.getsignal(number) for number in numbers}
        try:
            for number in numbers:
                signal.signal(number, self.signal_handler)
            yield self
        finally:
            for number, handler in old.items():
                signal.signal(number, handler)


class ReplayPaused(RuntimeError):
    def __init__(self, checkpoint_record, report):
        super().__init__(f"replay paused at complete response {checkpoint_record['cursor']}")
        self.checkpoint_record = checkpoint_record
        self.report = report


def estimate_complete_kv_bytes(model, prompt_length, target_length):
    """Qwen dense DynamicCache estimate, verified against actual returned bytes."""
    config = model.config
    heads = config.num_key_value_heads
    head_dim = getattr(config, "head_dim", None) or config.hidden_size // config.num_attention_heads
    return (
        2
        * config.num_hidden_layers
        * heads
        * head_dim
        * (prompt_length + target_length - 1)
        * next(model.parameters()).element_size()
    )


class ReplaySession(optimized.ReplaySession):
    """R1 CPU-KV reuse; R2 bounded full/saved-KV residency; identical arithmetic.

    ``resident_kv_budget_bytes`` bounds saved-KV copies only.  It does not bound
    full KV, layout banks, adjoints, activations, gradients, or allocator cache.
    Full KV has its own admission cap.  CUDA allocation/free checks are response
    boundary admission and observed-peak checks, not a guaranteed total-memory
    upper bound during a response; an OOM is an experiment failure, never Q=0.
    """

    def __init__(
        self,
        model,
        theta,
        *,
        variant,
        profile_id,
        cpu_test=False,
        resident_kv_budget_bytes=2 * GIB,
        full_kv_budget_bytes=8 * GIB,
        allocated_memory_limit_bytes=76 * GIB,
        free_memory_reserve_bytes=2 * GIB,
        response_monitor=None,
    ):
        require(variant in ("R1", "R2"), "R0 must use the frozen reference directly")
        require(
            type(full_kv_budget_bytes) is int and 0 <= full_kv_budget_bytes <= 8 * GIB,
            "registered finite full-KV budget required",
        )
        require(
            type(allocated_memory_limit_bytes) is int
            and allocated_memory_limit_bytes > 0
            and type(free_memory_reserve_bytes) is int
            and free_memory_reserve_bytes >= 0,
            "explicit allocated-memory admission and free-memory reserve required",
        )
        self.variant = variant
        self.cpu_test = cpu_test
        self.full_kv_budget_bytes = full_kv_budget_bytes
        self.allocated_memory_limit_bytes = allocated_memory_limit_bytes
        self.free_memory_reserve_bytes = free_memory_reserve_bytes
        self.response_monitor = response_monitor
        super().__init__(
            model,
            theta,
            profile_id=profile_id,
            cpu_test=cpu_test,
            resident_kv_budget_bytes=0 if variant == "R1" else resident_kv_budget_bytes,
        )
        if variant == "R1":
            # This class is session-local (V19 creates it inside __init__); no
            # frozen module or process-global numeric implementation is edited.
            self.operation.forward = optimized.bind_dependencies(
                self.operation.forward,
                forward_saved_tokens=optimized.legacy.forward_saved_tokens,
            )

    def memory_snapshot(self):
        if self.cpu_test:
            return {"cpu_test_only": True}
        device = next(self.model.parameters()).device
        free, total = torch.cuda.mem_get_info(device)
        return dict(
            torch_allocated_bytes=torch.cuda.memory_allocated(device),
            torch_reserved_bytes=torch.cuda.memory_reserved(device),
            torch_peak_allocated_bytes=torch.cuda.max_memory_allocated(device),
            torch_peak_reserved_bytes=torch.cuda.max_memory_reserved(device),
            device_used_bytes_at_response_boundary=total - free,
            device_free_bytes_at_response_boundary=free,
            device_total_bytes=total,
        )

    def __call__(self, model, theta, prompt, targets, *, expected, block_size=8):
        estimate = estimate_complete_kv_bytes(model, len(prompt), len(targets))
        if self.variant == "R2":
            require(estimate <= self.full_kv_budget_bytes, "full-KV residency budget exceeded")
        before = self.memory_snapshot()
        if not self.cpu_test:
            require(
                before["torch_allocated_bytes"] < self.allocated_memory_limit_bytes,
                "allocated-memory admission limit reached",
            )
            incremental = estimate + self.bank.resident_limit if self.variant == "R2" else 0
            require(
                before["device_free_bytes_at_response_boundary"]
                >= self.free_memory_reserve_bytes + incremental,
                "insufficient free memory for registered residency plus reserve",
            )
        if self.response_monitor:
            self.response_monitor(dict(phase="before_response", variant=self.variant, **before))
        values, gradient, report = super().__call__(
            model, theta, prompt, targets, expected=expected, block_size=block_size
        )
        if self.variant == "R1":
            # V19's common call reports a device cache; restore truthful R1 labels.
            report["single_complete_CPU_KV_bytes"] = report["single_complete_GPU_KV_bytes"]
            report["single_complete_GPU_KV_bytes"] = 0
        else:
            require(
                report["single_complete_GPU_KV_bytes"] == estimate
                and report["single_complete_GPU_KV_bytes"] <= self.full_kv_budget_bytes,
                "actual complete KV differs from registered memory estimate/budget",
            )
        after = self.memory_snapshot()
        if self.response_monitor:
            self.response_monitor(dict(phase="after_response", variant=self.variant, **after))
        if not self.cpu_test:
            require(
                after["torch_peak_allocated_bytes"] <= self.allocated_memory_limit_bytes,
                "observed allocated peak exceeded registered resource cap",
            )
            require(
                after["device_free_bytes_at_response_boundary"] >= self.free_memory_reserve_bytes,
                "free memory reserve exhausted at response boundary",
            )
        report.update(
            replay_variant=self.variant,
            replay_backend_version=BACKEND_VERSION,
            full_kv_budget_bytes=self.full_kv_budget_bytes if self.variant == "R2" else 0,
            saved_kv_budget_is_not_total_memory_cap=True,
            full_kv_estimate_bytes=estimate,
            allocated_memory_limit_bytes=self.allocated_memory_limit_bytes,
            free_memory_reserve_bytes=self.free_memory_reserve_bytes,
            memory_before=before,
            memory_after=after,
        )
        return values, gradient, report


def feedback_gradient(
    cohort,
    rewards,
    model,
    theta,
    *,
    root,
    profile_id,
    backend_factory,
    backend_identity,
    rng_restore_source,
    pause_request=None,
    pause_after_response=None,
    checkpoint_every=16,
    event_sink=None,
    replay=None,
    block_size=8,
    cpu_test=False,
):
    """V19 ordered H_k accumulation with an additional durable pause boundary.

    Caller restores the registered source RNG before entry, as in V19.  Its
    digest is verified at every response and restore; the source and backend
    version are bound inside every immutable checkpoint.  Resume requires the
    same backend identity and reward/response order, and never creates feedback.
    """
    require(
        replay is None and block_size == 8 and checkpoint_every == 16,
        "no replacement or unregistered replay/checkpoint configuration",
    )
    require(isinstance(backend_identity, dict) and backend_identity, "backend identity required")
    require(
        isinstance(rng_restore_source, dict) and rng_restore_source, "RNG restore source required"
    )
    require(
        pause_after_response is None
        or type(pause_after_response) is int
        and pause_after_response >= 0,
        "pause boundary must be a nonnegative complete response cursor",
    )
    checked = seal_feedback_cohort(
        cohort.episodes,
        denominator=cohort.denominator,
        identity=cohort.identity,
        source_manifest_sha256=cohort.source_manifest_sha256,
        registered_episode_keys=[episode_key(ep) for ep in cohort.episodes],
    )
    require(checked == cohort and cohort.generation_complete, "feedback seal changed")
    rewards = tuple(rewards)
    require(
        len(rewards) == cohort.denominator
        and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in rewards),
        "complete finite registered rewards required; Unknown is not zero",
    )
    require(
        theta and parameter_digest(theta) == cohort.identity.parameter_digest,
        "replay theta differs from actual sampled point",
    )
    require(
        all(
            ep.stop_reason == "final_answer" or r == 0
            for ep, r in zip(cohort.episodes, rewards, strict=True)
        ),
        "unsubmitted episodes cannot have positive reward",
    )
    if not cpu_test:
        require(
            cohort.denominator == 700 and all(v.device.type == "cuda" for v in theta.values()),
            "production requires actual fixed700 CUDA replay",
        )
    work = [
        (i, j, reward, turn.receipt)
        for i, (ep, reward) in enumerate(zip(cohort.episodes, rewards, strict=True))
        if reward != 0
        for j, turn in enumerate(ep.turns)
    ]
    order = [(i, j, receipt.call_id) for i, j, _, receipt in work]
    binding = dict(
        schema="v32_fixed_replay_point_binding.v1",
        execution_profile_id=profile_id,
        cohort_seal_sha256=cohort.seal_sha256,
        reward_sha256=digest(rewards),
        reward_vector=list(rewards),
        point_id=cohort.identity.point_id,
        parameter_digest=cohort.identity.parameter_digest,
        response_order_sha256=digest(order),
        response_order=[list(row) for row in order],
        response_count=len(work),
        denominator=cohort.denominator,
        block_size=8,
        gradient_length_normalized=False,
        checkpoint_every_responses=16,
        rng_restore_source=rng_restore_source,
        backend_identity=backend_identity,
        replay_state_adapter=BACKEND_VERSION,
    )
    points = state.ReplayCheckpoints(root, binding, theta)
    restored = points.restore()
    cursor = restored["cursor"] if restored else 0
    total = (
        {name: value.to(theta[name].device) for name, value in restored["total"].items()}
        if restored
        else {name: torch.zeros_like(value) for name, value in theta.items()}
    )
    accounting = Counter(restored["accounting"] if restored else {})
    accounting["zero_reward_trajectories_skipped"] = sum(r == 0 for r in rewards)
    started, rng_before = time.monotonic(), _tree_digest(_rng())
    emit = event_sink or (lambda event: None)
    stop = pause_request if pause_request is not None else PauseRequest()
    session = None
    checkpoint_seconds, checkpoint_count = 0.0, 0

    def commit(done, *, complete=False):
        nonlocal checkpoint_seconds, checkpoint_count
        checkpoint_started = time.monotonic()
        record = points.save(done, total, accounting, complete=complete)
        elapsed = time.monotonic() - checkpoint_started
        checkpoint_seconds += elapsed
        checkpoint_count += 1
        emit(
            dict(
                event="feedback_checkpoint_committed",
                completed_responses=done,
                checkpoint_id=record["id"],
                checkpoint_wall_seconds=elapsed,
                checkpoint_wall_seconds_this_process=checkpoint_seconds,
                checkpoint_commits_this_process=checkpoint_count,
            )
        )
        return record

    def progress(done, **extra):
        status(
            Path(root) / "progress",
            dict(
                schema="v32_live_replay_progress.v1",
                at=now(),
                binding=binding,
                completed_responses=done,
                total_responses=len(work),
                restored_completed_responses=cursor,
                elapsed_seconds_this_process=time.monotonic() - started,
                checkpoint_wall_seconds_this_process=checkpoint_seconds,
                checkpoint_commits_this_process=checkpoint_count,
                accounting=dict(accounting),
                **extra,
            ),
        )

    def pause(done):
        record = commit(done, complete=done == len(work))
        progress(
            done,
            phase="PAUSED",
            pause_reason=stop.reason or "registered_boundary",
            complete_replay=done == len(work),
        )
        raise ReplayPaused(
            record,
            dict(
                complete_replay=done == len(work),
                completed_responses=done,
                restored_completed_responses=cursor,
                response_checkpoint_binding=binding,
                gJ_prefix_digest=parameter_digest(total),
                accounting=dict(accounting),
                pause_reason=stop.reason or "registered_boundary",
                new_sampling_calls=0,
                optimizer_steps_performed=0,
                checkpoint_wall_seconds_this_process=checkpoint_seconds,
                checkpoint_commits_this_process=checkpoint_count,
            ),
        )

    progress(cursor, phase="RESTORED" if restored else "STARTED")
    try:
        if stop.requested or pause_after_response == cursor:
            pause(cursor)
        if cursor < len(work):
            session = backend_factory(model, theta)
        for index in range(cursor, len(work)):
            if stop.requested:
                pause(index)
            trajectory, _turn, reward, receipt = work[index]
            if cpu_test:
                context = contextlib.nullcontext()
            else:
                from torch.nn.attention import SDPBackend, sdpa_kernel

                context = sdpa_kernel(SDPBackend.FLASH_ATTENTION)
            with context:
                values, gradient, used = session(
                    model,
                    theta,
                    list(receipt.prompt_input_ids),
                    list(receipt.raw_generated_token_ids),
                    expected=list(receipt.sampled_token_logprobs),
                    block_size=8,
                )
            expected = torch.tensor(
                receipt.sampled_token_logprobs, dtype=values.dtype, device=values.device
            )
            require(
                values.shape == expected.shape
                and torch.allclose(values, expected, atol=1e-6, rtol=1e-5),
                "replayed probabilities differ from original sampling",
            )
            require(set(gradient) == set(total), "every actual parameter coordinate required")
            for name, value in gradient.items():
                require(
                    value.shape == total[name].shape
                    and value.dtype == total[name].dtype
                    and value.device == total[name].device
                    and bool(torch.isfinite(value).all()),
                    "invalid or nonfinite replay gradient",
                )
                total[name].add_(value, alpha=float(reward) / cohort.denominator)
            accounting["responses_replayed"] += 1
            accounting["sampled_tokens_with_parameter_derivative"] += len(
                receipt.raw_generated_token_ids
            )
            accounting["cached_forward_target_positions"] += used.get(
                "cached_forward_target_positions", 0
            )
            done = index + 1
            emit(
                dict(
                    event="feedback_response_backward",
                    trajectory=trajectory,
                    call_id=receipt.call_id,
                    **dict(accounting),
                )
            )
            require(_tree_digest(_rng()) == rng_before, "replay changed the registered RNG")
            # This is the first legal commit boundary: every gradient coordinate
            # was validated and added exactly once and the response logP matched.
            if stop.requested or pause_after_response == done:
                pause(done)
            if done % checkpoint_every == 0 or done == len(work):
                commit(done, complete=done == len(work))
            progress(
                done,
                phase="REPLAYING",
                last_call_id=receipt.call_id,
                last_response_diagnostics=used,
            )
            del values, gradient
    finally:
        if session is not None and hasattr(session, "close"):
            active_error = sys.exc_info()[1]
            try:
                session.close(
                    aborted=active_error is not None and not isinstance(active_error, ReplayPaused)
                )
            except Exception as cleanup_error:
                if active_error is None:
                    raise
                active_error.add_note(
                    f"replay cleanup: {type(cleanup_error).__name__}: {cleanup_error}"
                )
    require(
        all(bool(torch.isfinite(value).all()) for value in total.values()),
        "nonfinite complete feedback gradient",
    )
    if not work:
        commit(0, complete=True)
    progress(len(work), phase="COMPLETE", complete_replay=True)
    return total, dict(
        cohort_seal_sha256=cohort.seal_sha256,
        denominator=cohort.denominator,
        reward_sha256=digest(rewards),
        point_id=cohort.identity.point_id,
        parameter_digest=cohort.identity.parameter_digest,
        gJ_digest=parameter_digest(total),
        accounting=dict(accounting),
        all_receipts_validated=True,
        zero_reward_GPU_replay_claimed=False,
        complete_prefix_adjoint_required=True,
        length_normalized=False,
        execution_profile_id=profile_id,
        response_checkpoint_binding=binding,
        restored_completed_responses=cursor,
        new_sampling_calls=0,
        optimizer_steps_performed=0,
        checkpoint_wall_seconds_this_process=checkpoint_seconds,
        checkpoint_commits_this_process=checkpoint_count,
        SFT_mask_used=False,
        all_sampled_error_and_EOS_tokens_included=True,
        source_manifest_sha256=cohort.source_manifest_sha256,
        native_reward_not_trajectory_validity=True,
        replay_backend=BACKEND_VERSION,
        backend_identity=backend_identity,
        complete_replay=True,
    )
