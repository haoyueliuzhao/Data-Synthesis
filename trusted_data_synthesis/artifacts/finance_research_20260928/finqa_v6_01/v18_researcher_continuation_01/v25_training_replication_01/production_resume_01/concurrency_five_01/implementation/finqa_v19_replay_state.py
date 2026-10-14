"""Exact ordered feedback accumulation with immutable response-boundary checkpoints."""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import sys
import time
from collections import Counter
from contextlib import nullcontext
from pathlib import Path

import torch

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.finance_research.calibration import now, status
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.feedback import episode_key, seal_feedback_cohort
from trusted_synthesis.finance_research.providers import parameter_digest
from trusted_synthesis.finance_research.v6_collection import bound, require
from trusted_synthesis.finance_research.v8_training_driver import _rng, _tree_digest


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


class ReplayCheckpoints:
    def __init__(self, root, binding, theta):
        self.root, self.binding, self.theta = Path(root), binding, theta

    def save(self, cursor, total, accounting, *, complete=False):
        directory = self.root / f"response{cursor:06d}"
        state = dict(
            total={name: value.detach().cpu().clone() for name, value in total.items()},
            accounting=dict(accounting),
            cursor=cursor,
            binding=self.binding,
            rng_digest=_tree_digest(_rng()),
        )
        stream = io.BytesIO()
        torch.save(state, stream)
        raw = stream.getvalue()
        record = bound(
            dict(
                schema="v19_response_boundary_checkpoint.v1",
                at=now(),
                cursor=cursor,
                binding=self.binding,
                state_sha256=hashlib.sha256(raw).hexdigest(),
                state_digest=_tree_digest(state),
                response_prefix_complete=True,
                full_replay_complete=complete,
                optimizer_steps_performed=0,
                no_feedback_generation=True,
            )
        )
        if directory.exists():
            old, _ = self.read(directory)
            require(
                old["cursor"] == cursor and old["state_digest"] == record["state_digest"],
                "an existing response checkpoint cannot be overwritten",
            )
            return old
        write_immutable_artifact_directory(
            directory, {"state.pt": raw, "record.json": encode(record)}
        )
        return record

    def read(self, directory):
        directory = Path(directory)
        record = json.loads((directory / "record.json").read_bytes())
        require(
            record["id"] == digest({k: v for k, v in record.items() if k != "id"})
            and record["binding"] == self.binding,
            "checkpoint belongs to another profile, point, cohort or reward order",
        )
        raw = (directory / "state.pt").read_bytes()
        require(
            hashlib.sha256(raw).hexdigest() == record["state_sha256"],
            "replay checkpoint bytes changed",
        )
        state = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
        require(
            _tree_digest(state) == record["state_digest"]
            and state["binding"] == self.binding
            and state["cursor"] == record["cursor"]
            and directory.name == f"response{state['cursor']:06d}"
            and 0 <= state["cursor"] <= self.binding["response_count"]
            and state["accounting"].get("responses_replayed", 0) == state["cursor"]
            and state["rng_digest"] == _tree_digest(_rng()),
            "response checkpoint state, cursor or restored RNG differs",
        )
        require(set(state["total"]) == set(self.theta), "checkpoint gradient coordinates differ")
        for name, value in state["total"].items():
            require(
                value.shape == self.theta[name].shape
                and value.dtype == self.theta[name].dtype
                and bool(torch.isfinite(value).all()),
                "invalid checkpoint gradient tensor",
            )
        return record, state

    def restore(self):
        candidates = sorted(
            p
            for p in self.root.glob("response*")
            if re.fullmatch(r"response\d{6}", p.name) and (p / "record.json").is_file()
        )
        if not candidates:
            return None
        return self.read(candidates[-1])[1]


def feedback_gradient(
    cohort,
    rewards,
    model,
    theta,
    *,
    root,
    profile_id,
    backend_factory,
    checkpoint_every=16,
    event_sink=None,
    replay=None,
    block_size=8,
    cpu_test=False,
):
    """No subset or Q0 imputation; same response order and add_ coefficients."""
    require(
        replay is None and block_size == 8 and checkpoint_every == 16,
        "no callback replacement or unregistered replay/checkpoint configuration",
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
        and all(
            type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
            for value in rewards
        ),
        "complete finite registered rewards required; Unknown is not zero",
    )
    require(
        theta and parameter_digest(theta) == cohort.identity.parameter_digest,
        "replay theta differs from actual sampled point",
    )
    require(
        all(
            ep.stop_reason == "final_answer" or reward == 0
            for ep, reward in zip(cohort.episodes, rewards, strict=True)
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
    binding = dict(
        schema="v19_fixed_replay_point_binding.v1",
        execution_profile_id=profile_id,
        cohort_seal_sha256=cohort.seal_sha256,
        reward_sha256=digest(rewards),
        point_id=cohort.identity.point_id,
        parameter_digest=cohort.identity.parameter_digest,
        response_order_sha256=digest([(i, j, r.call_id) for i, j, _, r in work]),
        response_count=len(work),
        denominator=cohort.denominator,
        block_size=8,
        gradient_length_normalized=False,
        checkpoint_every_responses=16,
    )
    points = ReplayCheckpoints(root, binding, theta)
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
    session = None

    def progress(done, **extra):
        status(
            Path(root) / "progress",
            dict(
                schema="v19_live_replay_progress.v1",
                at=now(),
                binding=binding,
                completed_responses=done,
                total_responses=len(work),
                restored_completed_responses=cursor,
                elapsed_seconds_this_process=time.monotonic() - started,
                accounting=dict(accounting),
                **extra,
            ),
        )

    progress(cursor, phase="RESTORED" if restored else "STARTED")
    try:
        if cursor < len(work):
            session = backend_factory(model, theta)
        for index in range(cursor, len(work)):
            trajectory, _turn, reward, receipt = work[index]
            if cpu_test:
                context = nullcontext()
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
            if done % checkpoint_every == 0 or done == len(work):
                points.save(done, total, accounting, complete=done == len(work))
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
                session.close(aborted=active_error is not None)
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
        points.save(0, total, accounting, complete=True)
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
        SFT_mask_used=False,
        all_sampled_error_and_EOS_tokens_included=True,
        source_manifest_sha256=cohort.source_manifest_sha256,
        native_reward_not_trajectory_validity=True,
        replay_backend="v19_fixed8_resident_KV_ordered_checkpointed",
    )
