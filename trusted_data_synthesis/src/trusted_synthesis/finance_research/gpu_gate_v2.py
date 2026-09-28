"""Bounded visible-reference wiring gate: 2 parameter points x 2 synthetic episodes.

At most four genuine responses per episode; every sampled token, including error
actions and actual EOS, is replayed at its own point. No benchmark scores, private
answers, optimizer updates, retries, or API requests are part of this diagnostic.
"""

from __future__ import annotations

import fcntl
import gc
import hashlib
import inspect
import json
import math
import os
import re
import time
from contextlib import nullcontext
from pathlib import Path

from .contracts import (
    Episode,
    ModelIdentity,
    ModelTurn,
    PublicSource,
    PublicTask,
    RunConfig,
    digest,
)
from .gpu_gate import ATOL, RTOL, _publish, _read, _rng_digest, _versions
from .providers import LocalTorchProvider, local_model_identity, parameter_digest
from .qwen_protocol import QWEN_TOOL_PROTOCOL, parse_qwen_native_response

HARNESS_ID = "bigfinance-derived-vtdo-v3"
PROFILE_ID = "finqa_program_v2"
KINDS = ("normal", "error_recovery")
VIRTUAL = dict(lr=1e-5, gradient=1e-4, betas=[0.9, 0.999], eps=1e-8, weight_decay=0.0)


def synthetic_gate_cases():
    """Freeze these public fixtures in the plan; they are not author FinQA questions."""
    common = (
        "What is the increase in Revenue from prior to current? This is a synthetic "
        "protocol-wiring diagnostic, not a benchmark task. Read table:0 with read_source. "
        "Then call calculate with expression a-b and variables a and b referencing the "
        "current/prior cells of that actual successful read via its observed short result_handle: "
        "prev:<handle>.output.content.1.1 and prev:<handle>.output.content.1.2. "
        "Do not put reference strings in expression or substitute the initial table values "
        "for these variable references. Finally call final_answer with answer referencing "
        "prev:<calculate_handle>.output.result and a linear FinQA program using the observed "
        "numeric values, not tool handles. Use exactly one tool per response; no list_sources."
    )
    tasks = []
    for kind in KINDS:
        instruction = (
            common
            if kind == "normal"
            else (
                "For this error-recovery diagnostic, your FIRST response must call read_source "
                "with source_id table:missing, which does not exist. After observing its error, "
                "do not reference the failed result; correct the request to table:0. " + common
            )
        )
        task = PublicTask(
            dataset="finqa",
            task_id=f"synthetic/G2/{kind}",
            question=instruction,
            sources=(
                PublicSource(
                    source_id="table:0",
                    kind="table",
                    locator="synthetic_table",
                    content=[["metric", "current", "prior"], ["Revenue", "120", "90"]],
                ),
            ),
            version="synthetic-visible-reference-gate-v2",
            answer_contract={},
        )
        tasks.append(
            {"kind": kind, "task": task.model_dump(mode="json"), "instruction": instruction}
        )
    return tasks


def _validate(plan):
    config = RunConfig.model_validate(plan["gate_config"])
    if not (
        config.harness_id == HARNESS_ID
        and config.submission_profile == PROFILE_ID
        and config.local_tool_protocol == QWEN_TOOL_PROTOCOL
        and config.tier == "EVAL_NATIVE"
        and config.role == "calibration"
        and (config.temperature, config.top_p, config.top_k) == (1.0, 1.0, 0)
        and config.max_steps == 4
        and config.max_new_tokens == 256
        and config.context_limit == 24576
    ):
        raise ValueError("G2 requires the fixed H1-R T=1 / 4 responses / 256 output configuration")
    if plan["gate_cases"] != synthetic_gate_cases() or plan["diagnostic_virtual"] != VIRTUAL:
        raise ValueError("G2 synthetic cases or diagnostic virtual point changed")
    if not Path(plan["static_adapter_path"]).is_absolute():
        raise ValueError("G2 requires an absolute bound Static adapter path")
    return config


def _visible_results(rendered):
    """Read only the actual template-visible tool contents, never the session table."""
    values = []
    # Qwen's native template renders tool-role results in a dedicated user turn.
    # Ignore generic examples in system/task instructions when proving visibility.
    for section in re.finditer(
        r"<\|im_start\|>user\n(<tool_response>[\s\S]*?)<\|im_end\|>", rendered
    ):
        for match in re.finditer(
            r"<tool_response>\s*([\s\S]*?)\s*</tool_response>", section.group(1)
        ):
            try:
                value = json.loads(match.group(1))
            except ValueError:
                continue
            if isinstance(value, dict) and isinstance(value.get("result_handle"), str):
                values.append(value)
    return values


def _receipt_rendered(turn, tokenizer):
    receipt = turn.receipt
    if receipt is None:
        return None
    return tokenizer.decode(
        list(receipt.prompt_input_ids),
        skip_special_tokens=False,
        clean_up_tokenization_spaces=False,
    )


def reference_chain_report(episode, tokenizer, kind, *, scripted_prompts=None):
    """Success requires the executed chain AND references visible in original inputs."""
    events = list(episode.tool_events)
    expected = ["read_source", "calculate", "final_answer"]
    errors = [False, False, False]
    if kind == "error_recovery":
        expected.insert(0, "read_source")
        errors.insert(0, True)
    result = {
        "passed": False,
        "kind": kind,
        "stop_reason": episode.stop_reason,
        "tool_sequence": [e.name for e in events],
        "tool_error_flags": [e.is_error for e in events],
        "observed_prev_reference_used": False,
        "calculate_handle_visible_in_final_prompt": False,
        "read_handle_visible_in_calculate_prompt": False,
    }
    if result["tool_sequence"] != expected or result["tool_error_flags"] != errors:
        result["reason"] = "model_did_not_execute_the_registered_chain"
        return result
    read, calculate, final = events[-3:]
    handle = getattr(read, "result_handle", None)
    calculated_handle = getattr(calculate, "result_handle", None)
    if not handle or not calculated_handle:
        result["reason"] = "executed_events_have_no_visible_result_handles"
        return result
    expected_variables = {
        "a": f"prev:{handle}.output.content.1.1",
        "b": f"prev:{handle}.output.content.1.2",
    }
    raw_calc = calculate.normalized_arguments
    raw_final = final.normalized_arguments
    result["observed_prev_reference_used"] = (
        raw_calc.get("expression") == "a-b"
        and raw_calc.get("variables") == expected_variables
        and raw_final.get("answer") == f"prev:{calculated_handle}.output.result"
    )
    indexes = {
        call.call_id: index for index, turn in enumerate(episode.turns) for call in turn.tool_calls
    }
    for event, target, key in (
        (calculate, read, "read_handle_visible_in_calculate_prompt"),
        (final, calculate, "calculate_handle_visible_in_final_prompt"),
    ):
        index = indexes.get(event.call_id)
        if index is None:
            continue
        rendered = (
            scripted_prompts[index]
            if scripted_prompts is not None
            else _receipt_rendered(episode.turns[index], tokenizer)
        )
        if rendered is not None:
            result[key] = any(
                value.get("result_handle") == getattr(target, "result_handle", None)
                and value.get("status") == "ok"
                and value.get("output") == target.raw_output
                for value in _visible_results(rendered)
            )
    result["passed"] = (
        episode.stop_reason == "final_answer"
        and result["observed_prev_reference_used"]
        and result["read_handle_visible_in_calculate_prompt"]
        and result["calculate_handle_visible_in_final_prompt"]
        and read.executed_arguments.get("source_id") == "table:0"
        and calculate.executed_arguments.get("variables") == {"a": "120", "b": "90"}
        and final.executed_arguments.get("answer") == calculate.raw_output.get("result")
    )
    if kind == "error_recovery":
        result["failed_handle_not_used"] = (
            events[0].executed_arguments.get("source_id") == "table:missing"
            and getattr(events[0], "result_handle", None) != handle
        )
        result["passed"] = result["passed"] and result["failed_handle_not_used"]
    return result


class _VisibleFixture:
    """Scripted positive control obtains handles from actual rendered input tokens."""

    def __init__(self, tokenizer, kind):
        self.tokenizer, self.kind = tokenizer, kind
        self.identity = ModelIdentity(backend="scripted", model_id="visible-G2-positive-control")
        self.actual_model_calls, self.calls, self.prompts = 0, 0, []

    async def chat(self, messages, tools, config):
        rendered = self.tokenizer.apply_chat_template(
            messages, tools=tools, tokenize=False, add_generation_prompt=True
        )
        ids = self.tokenizer(rendered, add_special_tokens=False)["input_ids"]
        decoded = self.tokenizer.decode(
            ids, skip_special_tokens=False, clean_up_tokenization_spaces=False
        )
        if self.tokenizer(decoded, add_special_tokens=False)["input_ids"] != ids:
            raise ValueError("scripted control actual template tokens do not round-trip")
        self.prompts.append(decoded)
        self.calls += 1
        step = self.calls - (1 if self.kind == "error_recovery" else 0)
        if step <= 1:
            source = "table:missing" if step == 0 else "table:0"
            name, arguments = "read_source", {"source_id": source}
        else:
            visible = [v for v in _visible_results(decoded) if v.get("status") == "ok"]
            if not visible:
                raise ValueError("no successful handle is visible in actual template input")
            handle = visible[-1]["result_handle"]
            if step == 2:
                name, arguments = (
                    "calculate",
                    {
                        "expression": "a-b",
                        "variables": {
                            "a": f"prev:{handle}.output.content.1.1",
                            "b": f"prev:{handle}.output.content.1.2",
                        },
                    },
                )
            else:
                name, arguments = (
                    "final_answer",
                    {
                        "answer": f"prev:{handle}.output.result",
                        "scale": "",
                        "program": "subtract(120, 90)",
                    },
                )
        raw = (
            "<tool_call>\n" + json.dumps({"name": name, "arguments": arguments}) + "\n</tool_call>"
        )
        calls = parse_qwen_native_response(raw, call_prefix=f"fixture:{self.kind}:{self.calls}")[1]
        return ModelTurn(
            raw_text=raw,
            tool_calls=calls,
            provider_metadata={"fixture": True, "tool_protocol": QWEN_TOOL_PROTOCOL},
        )


async def scripted_controls(tokenizer, config):
    from .harness import run_episode

    rows = []
    for case in synthetic_gate_cases():
        provider = _VisibleFixture(tokenizer, case["kind"])
        episode = await run_episode(
            PublicTask.model_validate(case["task"]),
            provider,
            config,
            invocation_context={
                "run_id": "G2-scripted-control",
                "episode_id": case["kind"],
                "attempt": 1,
            },
        )
        chain = reference_chain_report(
            episode, tokenizer, case["kind"], scripted_prompts=provider.prompts
        )
        rows.append(
            {
                "kind": case["kind"],
                "passed": chain["passed"],
                "chain": chain,
                "episode": episode.model_dump(mode="json"),
                "actual_decoded_prompts": provider.prompts,
            }
        )
    return {
        "passed": all(row["passed"] for row in rows),
        "cases": rows,
        "actual_model_calls": 0,
        "handles_read_from_actual_rendered_tokens": True,
        "internal_result_table_used_for_actions": False,
    }


def _preflight(output):
    cases = output / "cases"
    if not cases.exists():
        return
    for case in cases.iterdir():
        if case.name not in {f"{i:02d}" for i in range(4)}:
            raise ValueError("G2 has exactly four registered episodes")
        events = case / "events"
        if (
            events.exists()
            and any(events.iterdir())
            and not (case / "generation" / "record.json").is_file()
        ):
            raise RuntimeError("unfinished G2 episode has persisted intents; no hidden resampling")
        if (case / "generation" / "record.json").is_file():
            saved = _read(case / "generation" / "record.json")
            if "episode" not in saved or not saved["episode"].get("all_provider_calls_settled"):
                raise RuntimeError("unsettled G2 generation requires explicit disposition")


class _CallCap:
    def __init__(self, provider, budget):
        self.provider, self.budget = provider, budget
        self.identity = provider.identity

    @property
    def actual_model_calls(self):
        return self.provider.actual_model_calls

    async def chat(self, messages, tools, config):
        if self.actual_model_calls >= 4 or self.budget[0] >= 16:
            raise RuntimeError("registered G2 generation cap exhausted; no extra response")
        before = self.actual_model_calls
        try:
            return await self.provider.chat(messages, tools, config)
        finally:
            self.budget[0] += self.actual_model_calls - before


def _eval_receipts(episode, identity):
    basic = (
        episode.all_provider_calls_settled
        and episode.actual_model_calls == len(episode.turns)
        and 0 < len(episode.turns) <= 4
        and episode.provider_attempts <= 4
        and episode.stop_reason
        in {"final_answer", "no_tool_call", "multiple_tool_calls", "max_steps", "context_exceeded"}
        and all(
            turn.receipt is not None
            and turn.receipt.identity == identity
            and turn.receipt.sampled_token_logprobs is not None
            and len(turn.receipt.raw_generated_token_ids)
            == len(turn.receipt.sampled_token_logprobs)
            for turn in episode.turns
        )
    )
    if not basic:
        return False
    seen = set()
    for index, turn in enumerate(episode.turns):
        receipt = turn.receipt
        request = turn.provider_metadata.get("request")
        invocation = turn.provider_metadata.get("harness_invocation", {})
        sampling = receipt.sampling
        if not (
            isinstance(request, dict)
            and digest(request) == receipt.request_sha256
            and request.get("config") == episode.config.model_dump(mode="json")
            and hashlib.sha256(turn.raw_text.encode()).hexdigest() == receipt.raw_response_sha256
            and invocation.get("invocation_id") not in seen
            and isinstance(invocation.get("invocation_id"), str)
            and invocation.get("turn_index") == index
            and invocation.get("parameter_digest") == identity.parameter_digest
            and 0 < len(receipt.raw_generated_token_ids) <= episode.config.max_new_tokens
            and len(receipt.prompt_input_ids) + episode.config.max_new_tokens
            <= episode.config.context_limit
            and all(math.isfinite(value) for value in receipt.sampled_token_logprobs)
            and sampling.get("do_sample") is True
            and (sampling.get("temperature"), sampling.get("top_p"), sampling.get("top_k"))
            == (1.0, 1.0, 0)
            and sampling.get("actual_model_generate_calls") == 1
            and all(
                sampling.get(field) is False
                for field in (
                    "SFT_mask_used",
                    "host_JSON_repair",
                    "context_truncated",
                    "length_normalized",
                )
            )
            and receipt.actual_eos
            == (receipt.raw_generated_token_ids[-1] in sampling.get("eos_token_ids", []))
        ):
            return False
        seen.add(invocation["invocation_id"])
    return True


def _replay_turn(model, point, receipt, backend):
    import torch
    from torch.nn.attention import SDPBackend, sdpa_kernel

    with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
        values, gradient, accounting = backend(
            model,
            point,
            list(receipt.prompt_input_ids),
            list(receipt.raw_generated_token_ids),
            expected=None,
            block_size=8,
        )
    expected = torch.tensor(
        receipt.sampled_token_logprobs, dtype=values.dtype, device=values.device
    )
    finite = set(gradient) == set(point) and all(
        value.shape == point[name].shape
        and value.dtype == point[name].dtype
        and value.device == point[name].device
        and bool(torch.isfinite(value).all())
        for name, value in gradient.items()
    )
    report = {
        "passed": bool(torch.allclose(values, expected, atol=ATOL, rtol=RTOL))
        and finite
        and accounting.get("complete_prefix_adjoint_included") is True
        and accounting.get("sampling_calls") == 0,
        "atol": ATOL,
        "rtol": RTOL,
        "logP_max_absolute_error": float((values - expected).abs().max()),
        "replayed_logprobs": values.detach().cpu().tolist(),
        "gradient_finite": finite,
        "gradient_sha256": parameter_digest(gradient),
        "gradient_coordinates": len(gradient),
        "gradient_l2": float(
            torch.linalg.vector_norm(
                torch.stack(
                    [torch.linalg.vector_norm(value.double()) for value in gradient.values()]
                )
            )
        ),
        "accounting": accounting,
        "replay_sampling_calls": 0,
        "all_actual_tokens_including_EOS": True,
        "SFT_mask_used": False,
        "error_action_tokens_excluded": False,
        "actual_eos": receipt.actual_eos,
        "prompt_tokens": len(receipt.prompt_input_ids),
        "output_tokens": len(receipt.raw_generated_token_ids),
    }
    return report


async def run_gate(plan, output, *, ready_callback=None):
    """Execute at most 16 newly sampled turns, with immutable per-turn intent receipts."""
    config = _validate(plan)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "gate.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _preflight(output)
        registration = {
            "schema": "finance_research_G2_registration.v1",
            "plan_sha256": digest(plan),
            "new_generation_cap": 16,
            "episode_response_cap": 4,
            "cases": [
                {"index": i, "point": p, "kind": k}
                for i, (p, k) in enumerate(
                    (
                        ("real", "normal"),
                        ("real", "error_recovery"),
                        ("virtual", "normal"),
                        ("virtual", "error_recovery"),
                    )
                )
            ],
            "virtual_is_training_full_G": False,
            "virtual_uses_old_training_Adam_moments": False,
        }
        path = output / "registration" / "record.json"
        if path.exists():
            if _read(path) != registration:
                raise ValueError("G2 immutable registration changed")
        else:
            _publish(path.parent, registration)
        return await _run_loaded(plan, output, config, registration, ready_callback)


async def _run_loaded(plan, output, config, registration, ready_callback):
    import torch
    from torch.nn.utils.stateless import _reparametrize_module

    from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import (
        optimizer_pullback as adam,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student import model as components
    from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
        load_tokenizer,
    )

    from .feedback import _segmented_backend
    from .harness import run_episode

    if not torch.cuda.is_available() or os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8":
        raise RuntimeError("G2 requires the frozen CUDA/CUBLAS launch configuration")
    started = time.monotonic()
    model, _ = components.load_student(
        plan["assets"]["base_binding"],
        11,
        trainable=True,
        adapter_path=Path(plan["static_adapter_path"]),
        adapter_record=plan["static_point"]["adapter"],
    )
    if ready_callback is not None:
        result = ready_callback()
        if inspect.isawaitable(result):
            await result
    tokenizer = load_tokenizer(plan["assets"]["tokenizer_binding"])
    controls_path = output / "scripted_controls" / "record.json"
    if controls_path.exists():
        controls = _read(controls_path)
    else:
        controls = await scripted_controls(tokenizer, config)
        _publish(controls_path.parent, controls)
    if not controls["passed"]:
        return {
            "eval_native_passed": False,
            "feedback_replay_passed": False,
            "real_reference_chain_passed": False,
            "scripted_controls_passed": False,
            "actual_new_generation_calls_this_invocation": 0,
            "cases": [],
            "error": "scripted_controls_failed",
        }
    real = {name: value for name, value in model.named_parameters() if value.requires_grad}
    before = dict(
        parameters=parameter_digest(real),
        versions=_versions(model),
        rng=_rng_digest(torch),
        modes=[m.training for m in model.modules()],
    )
    optimizer = torch.optim.AdamW(
        list(real.values()),
        lr=VIRTUAL["lr"],
        betas=tuple(VIRTUAL["betas"]),
        eps=VIRTUAL["eps"],
        weight_decay=0.0,
        foreach=False,
    )
    binding = adam.bind_adamw(real, optimizer, clip_max_norm=1.0)
    virtual = adam.virtual_step(
        binding, {name: torch.full_like(value, VIRTUAL["gradient"]) for name, value in real.items()}
    )
    if parameter_digest(virtual["theta_bar"]) == before["parameters"]:
        raise ValueError("diagnostic virtual point equals real point")
    backend = _segmented_backend()
    summaries, budget, error = [], [0], None
    provider, point, install = None, None, None
    try:
        for row in registration["cases"]:
            case = output / "cases" / f"{row['index']:02d}"
            point = real if row["point"] == "real" else virtual["theta_bar"]
            install = (
                nullcontext()
                if row["point"] == "real"
                else _reparametrize_module(model, point, strict=False)
            )
            with install:
                identity = local_model_identity(
                    model,
                    tokenizer,
                    model_id="Qwen2.5-7B-Instruct",
                    point_id=f"finance_G2:{row['point']}:{parameter_digest(point)}",
                )
                provider = _CallCap(LocalTorchProvider(model, tokenizer, identity), budget)
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
                generation = case / "generation" / "record.json"
                invocation = {
                    "run_id": str(plan.get("id", digest(plan))),
                    "episode_id": f"G2:{row['point']}:{row['kind']}",
                    "attempt": 1,
                }
                if generation.exists():
                    episode = Episode.model_validate(_read(generation)["episode"])
                    if episode.provider != identity:
                        raise ValueError("saved G2 episode parameter point changed")
                else:
                    event_index = [0]

                    def sink(event, case=case, event_index=event_index):
                        _publish(
                            case / "events" / f"{event_index[0]:03d}_{event['kind']}",
                            {**event, "at_unix": time.time()},
                        )
                        event_index[0] += 1

                    try:
                        task = PublicTask.model_validate(
                            plan["gate_cases"][row["index"] % 2]["task"]
                        )
                        episode = await run_episode(
                            task, provider, config, sink=sink, invocation_context=invocation
                        )
                    except BaseException as failure:
                        _publish(
                            generation.parent,
                            {
                                "failure": {
                                    "type": type(failure).__name__,
                                    "message": str(failure),
                                },
                                "actual_model_calls": provider.actual_model_calls,
                            },
                        )
                        raise
                    _publish(
                        generation.parent,
                        {
                            "episode": episode.model_dump(mode="json"),
                            "actual_model_calls": provider.actual_model_calls,
                            "invocation_context": invocation,
                        },
                    )
                eval_passed = _eval_receipts(episode, identity)
                chain = reference_chain_report(episode, tokenizer, row["kind"])
                replays = []
                for turn_index, turn in enumerate(episode.turns):
                    path = case / "replays" / f"{turn_index:02d}" / "record.json"
                    if path.exists():
                        replay = _read(path)
                    else:
                        try:
                            if not eval_passed:
                                raise ValueError(
                                    "receipt validation failed; replay is not admitted"
                                )
                            replay = _replay_turn(model, point, turn.receipt, backend)
                        except Exception as failure:
                            replay = {
                                "passed": False,
                                "error": {"type": type(failure).__name__, "message": str(failure)},
                                "atol": ATOL,
                                "rtol": RTOL,
                                "replay_sampling_calls": 0,
                            }
                        _publish(path.parent, replay)
                    replays.append(replay)
                    gc.collect()
                    torch.cuda.empty_cache()
                summaries.append(
                    {
                        **row,
                        "episode_path": str(generation),
                        "actual_model_calls": episode.actual_model_calls,
                        "all_provider_calls_settled": episode.all_provider_calls_settled,
                        "stop_reason": episode.stop_reason,
                        "eval_native_passed": eval_passed,
                        "reference_chain": chain,
                        "replays": replays,
                        "feedback_replay_passed": eval_passed
                        and bool(replays)
                        and all(r["passed"] for r in replays),
                        "rng_unchanged": _rng_digest(torch) == before["rng"],
                        "max_memory_allocated_bytes": torch.cuda.max_memory_allocated(),
                        "max_memory_reserved_bytes": torch.cuda.max_memory_reserved(),
                    }
                )
                if not eval_passed:
                    raise RuntimeError(
                        "G2 infrastructure or unsettled receipt prevents further generation"
                    )
            gc.collect()
            torch.cuda.empty_cache()
        adam._verify(binding)
    except BaseException as failure:
        error = {"type": type(failure).__name__, "message": str(failure)}
    isolation = (
        parameter_digest(real) == before["parameters"]
        and _versions(model) == before["versions"]
        and _rng_digest(torch) == before["rng"]
        and [m.training for m in model.modules()] == before["modes"]
        and not optimizer.state
        and all(value.grad is None for value in real.values())
    )
    all_cases = error is None and len(summaries) == 4 and isolation
    report = {
        "schema": "finance_research_G2_result.v1",
        "plan_sha256": digest(plan),
        "scripted_controls_passed": controls["passed"],
        "scripted_controls_path": str(controls_path),
        "eval_native_passed": all_cases and all(s["eval_native_passed"] for s in summaries),
        "feedback_replay_passed": all_cases and all(s["feedback_replay_passed"] for s in summaries),
        "real_reference_chain_passed": all_cases
        and all(s["reference_chain"]["passed"] for s in summaries),
        "cases": summaries,
        "error": error,
        "actual_new_generation_calls_this_invocation": budget[0],
        "registered_generation_cap": 16,
        "real_state_and_RNG_unchanged": isolation,
        "virtual_is_training_full_G": False,
        "virtual_uses_old_training_Adam_moments": False,
        "diagnostic_virtual": VIRTUAL,
        "training_admitted": False,
        "real_optimizer_steps": 0,
        "API_calls": 0,
        "benchmark_sessions": 0,
        "elapsed_seconds": time.monotonic() - started,
    }
    del model, provider, optimizer, real, point, virtual, binding, install
    gc.collect()
    torch.cuda.empty_cache()
    return report
