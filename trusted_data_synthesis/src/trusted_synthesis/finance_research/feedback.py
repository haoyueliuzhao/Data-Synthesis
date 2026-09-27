"""Full-cohort score-function replay, without retokenization or SFT masks.

Original dataset/split admission belongs to the bound source manifest; role
labels alone never authorize private external-test data as feedback.
"""

from __future__ import annotations

import importlib
import math
import sys
from collections import Counter
from pathlib import Path

from .contracts import Episode, ModelIdentity, Record, digest
from .providers import _sha, parameter_digest


class SealedFeedbackCohort(Record):
    seal_sha256: str
    identity: ModelIdentity
    denominator: int
    episodes: tuple[Episode, ...]
    episode_sha256: tuple[str, ...]
    source_manifest_sha256: str
    registered_episode_keys: tuple[str, ...]
    generation_complete: bool = True


def episode_key(episode):
    return digest(
        {
            "dataset": episode.dataset,
            "task_id": episode.task_id,
            "seed": episode.config.seed,
            "point_id": episode.provider.point_id,
        }
    )


def _validate_episode(episode: Episode, identity: ModelIdentity):
    config = episode.config
    if config.tier != "VTDO_FEEDBACK" or config.role != "feedback":
        raise ValueError("feedback requires VTDO_FEEDBACK and admitted feedback-role data")
    if identity.backend != "local_torch" or episode.provider != identity:
        raise ValueError("feedback requires the same real local Student point")
    if not all(
        (
            identity.point_id,
            identity.parameter_digest,
            identity.tokenizer_digest,
            identity.chat_template_digest,
        )
    ):
        raise ValueError("complete model/tokenizer/point identity is required")
    if (config.temperature, config.top_p, config.top_k) != (1.0, 1.0, 0):
        raise ValueError("feedback requires unmodified stochastic sampling")
    if config.context_limit > 24576 or config.max_new_tokens > 2048:
        raise ValueError("feedback exceeds the admitted replay backend limits")
    if episode.actual_model_calls != len(episode.turns):
        raise ValueError("every actual generation must have a complete returned turn receipt")
    if episode.stop_reason not in {
        "final_answer",
        "max_steps",
        "context_exceeded",
        "no_tool_call",
        "multiple_tool_calls",
    }:
        raise ValueError("infrastructure/provider failures cannot become zero-reward samples")
    seen = set()
    for turn in episode.turns:
        receipt = turn.receipt
        if receipt is None or receipt.identity != identity:
            raise ValueError("missing receipt or receipt point mismatch")
        if receipt.call_id in seen:
            raise ValueError("duplicate generation receipt")
        seen.add(receipt.call_id)
        if receipt.raw_response_sha256 != _sha(turn.raw_text):
            raise ValueError("receipt raw-response binding mismatch")
        request = turn.provider_metadata.get("request")
        if request is None or digest(request) != receipt.request_sha256:
            raise ValueError("receipt request/messages/tools binding mismatch")
        if request.get("config") != config.model_dump(mode="json"):
            raise ValueError("receipt generation configuration mismatch")
        sampling = receipt.sampling
        if not (
            sampling.get("do_sample") is True
            and sampling.get("temperature") == 1.0
            and sampling.get("top_p") == 1.0
            and sampling.get("top_k") == 0
            and sampling.get("actual_model_generate_calls") == 1
            and sampling.get("max_new_tokens") == config.max_new_tokens
            and sampling.get("context_limit") == config.context_limit
            and all(
                sampling.get(key) is False
                for key in (
                    "context_truncated",
                    "host_JSON_repair",
                    "length_normalized",
                    "SFT_mask_used",
                )
            )
        ):
            raise ValueError("receipt is not unmodified full-token generation")
        prompt, targets, logps = (
            receipt.prompt_input_ids,
            receipt.raw_generated_token_ids,
            receipt.sampled_token_logprobs,
        )
        if not prompt or not targets or len(targets) > config.max_new_tokens:
            raise ValueError("empty or over-budget token receipt")
        if any(type(value) is not int or value < 0 for value in (*prompt, *targets)):
            raise ValueError("invalid actual token ids")
        if len(prompt) + config.max_new_tokens > config.context_limit:
            raise ValueError("token receipt violates untruncated context reservation")
        if (
            logps is None
            or len(logps) != len(targets)
            or not all(math.isfinite(value) and value <= 1e-6 for value in logps)
        ):
            raise ValueError("missing or nonfinite real sampling probabilities")
        ended = targets[-1] in sampling.get("eos_token_ids", [])
        if ended != receipt.actual_eos or receipt.finish_reason != turn.finish_reason:
            raise ValueError("EOS/finish-reason receipt mismatch")
        if not receipt.rng_before_sha256 or not receipt.rng_after_sha256:
            raise ValueError("actual RNG-state bindings are required")


def seal_feedback_cohort(
    episodes,
    *,
    denominator: int,
    identity: ModelIdentity,
    source_manifest_sha256: str,
    registered_episode_keys,
) -> SealedFeedbackCohort:
    """Seal all registered generation before rewards; references are not accepted."""
    episodes, registered = tuple(episodes), tuple(registered_episode_keys)
    if type(denominator) is not int or denominator <= 0 or len(episodes) != denominator:
        raise ValueError("complete registered cohort and unchanged denominator are required")
    if not isinstance(source_manifest_sha256, str) or len(source_manifest_sha256) != 64:
        raise ValueError("a bound admitted source manifest is required")
    if len(registered) != denominator or len(set(registered)) != denominator:
        raise ValueError("complete distinct episode keys must be registered before generation")
    if tuple(episode_key(episode) for episode in episodes) != registered:
        raise ValueError("feedback episodes differ from the registered task/seed/point roster")
    for episode in episodes:
        _validate_episode(episode, identity)
    hashes = tuple(digest(episode) for episode in episodes)
    if len(set(hashes)) != len(hashes):
        raise ValueError("duplicate episodes cannot fill a feedback denominator")
    all_calls = [turn.receipt.call_id for episode in episodes for turn in episode.turns]
    if len(set(all_calls)) != len(all_calls):
        raise ValueError("one sampled response cannot be counted as multiple trajectories")
    body = dict(
        identity=identity.model_dump(mode="json"),
        denominator=denominator,
        episode_sha256=hashes,
        source_manifest_sha256=source_manifest_sha256,
        registered_episode_keys=registered,
        generation_complete=True,
    )
    return SealedFeedbackCohort(seal_sha256=digest(body), episodes=episodes, **body)


def _segmented_backend():
    """Lazy source-checkout bridge; frozen implementation files remain untouched."""
    name = "fixed_kernel_anchored_segmented_replay_20260916"
    try:
        return importlib.import_module(name).segmented_logp
    except ModuleNotFoundError as error:
        if error.name != name:
            raise
        scripts = Path(__file__).resolve().parents[3] / "scripts"
        if not (scripts / (name + ".py")).is_file():
            raise RuntimeError(
                "frozen segmented replay requires the research source checkout"
            ) from error
        sys.path.insert(0, str(scripts))
        try:
            return importlib.import_module(name).segmented_logp
        finally:
            sys.path.remove(str(scripts))


def feedback_gradient(cohort, rewards, model, theta, *, replay=None, block_size=8, event_sink=None):
    """Replay complete native rewards in [0,1] at the sealed sampled point.

    Rewards align exactly to the seal. Zero rewards retain their denominator.
    Callers may load private references only after the generation seal exists.
    """
    import torch

    checked = seal_feedback_cohort(
        cohort.episodes,
        denominator=cohort.denominator,
        identity=cohort.identity,
        source_manifest_sha256=cohort.source_manifest_sha256,
        registered_episode_keys=cohort.registered_episode_keys,
    )
    if checked != cohort or not cohort.generation_complete:
        raise ValueError("feedback cohort seal was modified")
    rewards = tuple(rewards)
    if len(rewards) != cohort.denominator or any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
        for value in rewards
    ):
        raise ValueError("complete finite registered native rewards in [0,1] are required")
    if not theta or parameter_digest(theta) != cohort.identity.parameter_digest:
        raise ValueError("gradient replay theta differs from the sampled parameter point")
    if any(
        episode.stop_reason != "final_answer" and reward != 0
        for episode, reward in zip(cohort.episodes, rewards, strict=True)
    ):
        raise ValueError("episodes without a submitted native answer must retain zero reward")
    total = {name: torch.zeros_like(value) for name, value in theta.items()}
    accounting = Counter()
    backend = replay
    emit = event_sink or (lambda event: None)
    for index, (episode, reward) in enumerate(zip(cohort.episodes, rewards, strict=True)):
        if reward == 0:
            accounting["zero_reward_trajectories_skipped"] += 1
            continue
        for turn in episode.turns:
            receipt = turn.receipt
            if backend is None:
                backend = _segmented_backend()
            if replay is None:
                from torch.nn.attention import SDPBackend, sdpa_kernel

                context = sdpa_kernel(SDPBackend.FLASH_ATTENTION)
            else:
                from contextlib import nullcontext

                context = nullcontext()
            with context:
                values, gradient, used = backend(
                    model,
                    theta,
                    list(receipt.prompt_input_ids),
                    list(receipt.raw_generated_token_ids),
                    expected=list(receipt.sampled_token_logprobs),
                    block_size=block_size,
                )
            if set(gradient) != set(total):
                raise ValueError("replay must return every sampled-point parameter coordinate")
            expected = torch.tensor(
                receipt.sampled_token_logprobs, dtype=values.dtype, device=values.device
            )
            if values.shape != expected.shape or not torch.allclose(
                values, expected, atol=1e-6, rtol=1e-5
            ):
                raise ValueError("replayed probabilities differ from actual sampling receipts")
            for name, value in gradient.items():
                if (
                    value.shape != total[name].shape
                    or value.dtype != total[name].dtype
                    or value.device != total[name].device
                    or not bool(torch.isfinite(value).all())
                ):
                    raise ValueError("invalid replay gradient shape or finite value")
                total[name].add_(value, alpha=float(reward) / cohort.denominator)
            accounting["responses_replayed"] += 1
            accounting["sampled_tokens_with_parameter_derivative"] += len(
                receipt.raw_generated_token_ids
            )
            accounting["cached_forward_target_positions"] += used.get(
                "cached_forward_target_positions", 0
            )
            emit(
                {
                    "event": "feedback_response_backward",
                    "trajectory": index,
                    "call_id": receipt.call_id,
                    **dict(accounting),
                }
            )
            del values, gradient
    if any(not bool(torch.isfinite(value).all()) for value in total.values()):
        raise ValueError("nonfinite complete feedback gradient")
    return total, {
        "cohort_seal_sha256": cohort.seal_sha256,
        "denominator": cohort.denominator,
        "reward_sha256": digest(rewards),
        "point_id": cohort.identity.point_id,
        "parameter_digest": cohort.identity.parameter_digest,
        "gJ_digest": parameter_digest(total),
        "accounting": dict(accounting),
        "all_receipts_validated": True,
        "zero_reward_GPU_replay_claimed": False,
        "complete_prefix_adjoint_required": True,
        "length_normalized": False,
        "SFT_mask_used": False,
        "all_sampled_error_and_EOS_tokens_included": True,
        "source_manifest_sha256": cohort.source_manifest_sha256,
        "native_reward_not_trajectory_validity": True,
        "replay_backend": "frozen_segmented_logp" if replay is None else "injected_test_backend",
    }
