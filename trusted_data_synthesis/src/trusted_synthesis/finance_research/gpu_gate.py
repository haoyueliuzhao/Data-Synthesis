"""Four-call numerical wiring diagnostic, separate from calibration and training.

Imports do not initialize CUDA. Only ``run_gate`` loads the registered local model.
The virtual point is explicitly a zero-moment AdamW diagnostic, not a training G
or the old optimizer continuation. Original generated IDs are replayed unchanged.
"""

from __future__ import annotations

import copy
import fcntl
import gc
import hashlib
import inspect
import json
import os
import pickle
import random
import time
from contextlib import nullcontext
from pathlib import Path

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from .contracts import ModelTurn, PublicTask, RunConfig, digest
from .harness import SYSTEM_PROMPT
from .profiles import public_run_view
from .providers import (
    LocalTorchProvider,
    canonical_assistant_message,
    local_model_identity,
    parameter_digest,
)
from .tools import TOOL_SPECS, PublicToolSession

DIAGNOSTIC_INSTRUCTION = (
    "This is a protocol-wiring diagnostic, not a financial answer attempt. "
    "Call list_sources exactly once with empty arguments. Do not solve the question "
    "and do not submit final_answer. Use the native tool-call format shown above."
)
ATOL, RTOL = 1e-6, 1e-5


def _read(path):
    return json.loads(Path(path).read_bytes())


def _publish(directory, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode()
    write_immutable_artifact_directory(directory, {"record.json": raw})


def _validated(plan):
    config = RunConfig.model_validate(plan["gate_config"])
    if not (
        config.tier == "EVAL_NATIVE"
        and config.role == "calibration"
        and config.local_tool_protocol == "qwen2.5-native-tool-call-v1"
        and config.submission_profile == "finqa_program_v1"
        and (config.temperature, config.top_p, config.top_k) == (1.0, 1.0, 0)
        and config.max_new_tokens == 256
        and config.context_limit == 24576
    ):
        raise ValueError("gate requires fixed native calibration T=1 / 256 / 24576 config")
    tasks = plan["gate_tasks"]
    if isinstance(tasks, dict):
        if set(tasks) != {"short", "long"}:
            raise ValueError("exact short/long gate task roster required")
        tasks = [tasks["short"], tasks["long"]]
    if not isinstance(tasks, (tuple, list)) or len(tasks) != 2:
        raise ValueError("exactly two gate task lengths are required")
    tasks = [PublicTask.model_validate(task) for task in tasks]
    for task in tasks:
        if task.dataset != "finqa" or "submission_profile" in task.answer_contract:
            raise ValueError("gate tasks must be original public FinQA tasks, not rewritten QA")
    virtual = plan["diagnostic_virtual"]
    fixed = dict(lr=1e-5, gradient=1e-4, betas=[0.9, 0.999], eps=1e-8, weight_decay=0.0)
    if virtual != fixed:
        raise ValueError("diagnostic virtual configuration differs from fixed small perturbation")
    if not Path(plan["static_adapter_path"]).is_absolute():
        raise ValueError("bound static adapter must have an absolute path")
    return config, tasks, fixed


def gate_messages(task: PublicTask, config: RunConfig):
    """Shared with CPU task-length selection; no reference answer enters this input."""
    view = public_run_view(task, config.submission_profile)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                view.model_dump(mode="json"), ensure_ascii=False, allow_nan=False
            ),
        },
        {"role": "user", "content": DIAGNOSTIC_INSTRUCTION},
    ], view


def _case_preflight(output):
    """An intent without its durable generation result is never sampled again."""
    for index in range(4):
        case = output / "cases" / f"{index:02d}"
        if (case / "intent").exists() and not (case / "generation" / "record.json").is_file():
            raise RuntimeError(f"unsettled diagnostic generation at case {index}; no resampling")
    cases = output / "cases"
    if cases.exists() and any(
        path.name not in {f"{i:02d}" for i in range(4)} for path in cases.iterdir()
    ):
        raise ValueError("unregistered case would exceed the four-call diagnostic cap")


def _native_check(turn, task, messages, tokenizer):
    canonical = canonical_assistant_message(turn)
    calls = turn.tool_calls
    if len(calls) != 1 or calls[0].name != "list_sources" or calls[0].arguments != {}:
        return {
            "passed": False,
            "reason": "expected_one_native_list_sources_empty_arguments",
            "canonical_message": canonical,
        }
    event = PublicToolSession(task).execute(calls[0])
    history = [
        *messages,
        canonical,
        {"role": "tool", "tool_call_id": calls[0].call_id, "content": event.visible_output},
    ]
    rendered = tokenizer.apply_chat_template(
        history, tools=copy.deepcopy(TOOL_SPECS), tokenize=False, add_generation_prompt=True
    )
    # The final assistant generation marker is empty; isolate the returned turn.
    section = rendered.rsplit("<|im_start|>assistant", 2)[-2].split("<|im_end|>", 1)[0]
    passed = (
        not event.is_error and section.count("<tool_call>") == section.count("</tool_call>") == 1
    )
    return {
        "passed": passed,
        "canonical_message": canonical,
        "tool_event": event.model_dump(mode="json"),
        "next_history_rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        "next_history_prompt_tokens": len(
            tokenizer(rendered, add_special_tokens=False)["input_ids"]
        ),
        "tool_envelope_rendered_once": passed,
        "second_model_call_made": False,
    }


def _rng_digest(torch):
    import numpy as np

    return digest(
        {
            "cpu": hashlib.sha256(torch.get_rng_state().numpy().tobytes()).hexdigest(),
            "cuda": hashlib.sha256(torch.cuda.get_rng_state().cpu().numpy().tobytes()).hexdigest(),
            "python": hashlib.sha256(pickle.dumps(random.getstate())).hexdigest(),
            "numpy": hashlib.sha256(pickle.dumps(np.random.get_state())).hexdigest(),
        }
    )


def _versions(model):
    return {
        name: (value.data_ptr(), value._version)
        for name, value in (*model.named_parameters(), *model.named_buffers())
    }


async def run_gate(plan: dict, output: Path, *, ready_callback=None) -> dict:
    """At most four new calls; persisted original IDs alone may be replayed again.

    ``ready_callback`` is awaited immediately after loading the model, so the
    caller can release its own GPU reservation without an empty-device window.
    No API request, optimizer step, QA scoring, or training occurs here.
    """
    config, tasks, diagnostic = _validated(plan)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "gate.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _case_preflight(output)
        registration = {
            "schema": "finance_research_four_call_gate.v1",
            "plan_sha256": digest(plan),
            "new_generation_cap": 4,
            "cases": [
                {
                    "index": index,
                    "point": point,
                    "length": length,
                    "task_id": tasks[index % 2].task_id,
                }
                for index, (point, length) in enumerate(
                    (
                        ("real", "short"),
                        ("real", "long"),
                        ("virtual", "short"),
                        ("virtual", "long"),
                    )
                )
            ],
            "atol": ATOL,
            "rtol": RTOL,
            "diagnostic_virtual": diagnostic,
            "virtual_is_training_full_G": False,
            "virtual_uses_old_training_Adam_moments": False,
            "real_optimizer_steps": 0,
            "diagnostic_instruction": DIAGNOSTIC_INSTRUCTION,
        }
        registration_path = output / "registration" / "record.json"
        if registration_path.exists():
            if _read(registration_path) != registration:
                raise ValueError(
                    "gate registration changed; never reuse old calls under a new plan"
                )
        else:
            _publish(registration_path.parent, registration)
        return await _run_loaded(
            plan, output, config, tasks, diagnostic, registration, ready_callback
        )


async def _run_loaded(plan, output, config, tasks, diagnostic, registration, ready_callback):
    import torch
    from torch.nn.attention import SDPBackend, sdpa_kernel
    from torch.nn.utils.stateless import _reparametrize_module

    from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import (
        optimizer_pullback as adam,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student import model as components
    from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
        load_tokenizer,
    )

    from .feedback import _segmented_backend

    if not torch.cuda.is_available() or os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8":
        raise RuntimeError("registered CUDA/CUBLAS configuration is required")
    started = time.monotonic()
    model, _ = components.load_student(
        plan["assets"]["base_binding"],
        11,
        trainable=True,
        adapter_path=Path(plan["static_adapter_path"]),
        adapter_record=plan["static_point"]["adapter"],
    )
    if ready_callback is not None:
        returned = ready_callback()
        if inspect.isawaitable(returned):
            await returned
    tokenizer = load_tokenizer(plan["assets"]["tokenizer_binding"])
    real = {name: value for name, value in model.named_parameters() if value.requires_grad}
    before = dict(
        parameters=parameter_digest(real),
        versions=_versions(model),
        rng=_rng_digest(torch),
        modes=[module.training for module in model.modules()],
    )
    optimizer = torch.optim.AdamW(
        list(real.values()),
        lr=diagnostic["lr"],
        betas=tuple(diagnostic["betas"]),
        eps=diagnostic["eps"],
        weight_decay=diagnostic["weight_decay"],
        foreach=False,
    )
    binding = adam.bind_adamw(real, optimizer, clip_max_norm=1.0)
    gradients = {
        name: torch.full_like(value, diagnostic["gradient"]) for name, value in real.items()
    }
    virtual = adam.virtual_step(binding, gradients)
    del gradients
    if parameter_digest(virtual["theta_bar"]) == before["parameters"]:
        raise ValueError("diagnostic virtual point did not differ from the real point")
    replay = _segmented_backend()
    summaries, actual_new_calls, error = [], 0, None
    provider, point, install = None, None, None
    try:
        for row in registration["cases"]:
            index = row["index"]
            case = output / "cases" / f"{index:02d}"
            task = tasks[index % 2]
            messages, view = gate_messages(task, config)
            point = real if row["point"] == "real" else virtual["theta_bar"]
            point_id = f"finance_native_gate:{row['point']}:{parameter_digest(point)}"
            install = (
                nullcontext()
                if row["point"] == "real"
                else _reparametrize_module(model, point, strict=False)
            )
            with install:
                identity = local_model_identity(
                    model, tokenizer, model_id="Qwen2.5-7B-Instruct", point_id=point_id
                )
                provider = LocalTorchProvider(model, tokenizer, identity)
                generation_file = case / "generation" / "record.json"
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
                if generation_file.exists():
                    generated = _read(generation_file)
                    if "turn" not in generated:
                        raise RuntimeError("diagnostic generation previously failed; no resampling")
                    turn = ModelTurn.model_validate(generated["turn"])
                    if turn.receipt is None or turn.receipt.identity != identity:
                        raise ValueError(
                            "saved diagnostic token receipt differs from current point"
                        )
                else:
                    if actual_new_calls >= 4:
                        raise RuntimeError("four-call diagnostic cap reached")
                    _publish(
                        case / "intent",
                        {
                            **row,
                            "identity": identity.model_dump(mode="json"),
                            "messages": messages,
                            "tools": TOOL_SPECS,
                            "config": config.model_dump(mode="json"),
                            "at_unix": time.time(),
                        },
                    )
                    try:
                        turn = await provider.chat(messages, copy.deepcopy(TOOL_SPECS), config)
                    except BaseException as failure:
                        actual_new_calls += provider.actual_model_calls
                        _publish(
                            case / "generation",
                            {
                                "failure": {
                                    "type": type(failure).__name__,
                                    "message": str(failure),
                                },
                                "actual_model_calls": provider.actual_model_calls,
                            },
                        )
                        raise
                    actual_new_calls += provider.actual_model_calls
                    _publish(
                        case / "generation",
                        {
                            "turn": turn.model_dump(mode="json"),
                            "actual_model_calls": provider.actual_model_calls,
                        },
                    )
                native = _native_check(turn, view, messages, tokenizer)
                receipt = turn.receipt
                if receipt is None or receipt.sampled_token_logprobs is None:
                    raise ValueError(
                        "diagnostic requires real original-token log-probability receipts"
                    )
                replay_file = case / "replay" / "record.json"
                if replay_file.exists():
                    replay_report = _read(replay_file)
                else:
                    try:
                        with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                            # Do not fail before recording numerical differences. The
                            # unchanged strict comparison is applied below; backend
                            # full-cache derivative and recomputation checks remain on.
                            values, gradient, accounting = replay(
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
                        difference = float((values - expected).abs().max())
                        replay_report = {
                            "passed": bool(torch.allclose(values, expected, atol=ATOL, rtol=RTOL))
                            and finite
                            and accounting.get("complete_prefix_adjoint_included") is True
                            and accounting.get("sampling_calls") == 0,
                            "atol": ATOL,
                            "rtol": RTOL,
                            "logP_max_absolute_error": difference,
                            "replayed_logprobs": values.detach().cpu().tolist(),
                            "gradient_finite": finite,
                            "gradient_sha256": parameter_digest(gradient),
                            "gradient_l2": float(
                                torch.linalg.vector_norm(
                                    torch.stack(
                                        [
                                            torch.linalg.vector_norm(value.double())
                                            for value in gradient.values()
                                        ]
                                    )
                                )
                            ),
                            "gradient_coordinates": len(gradient),
                            "accounting": accounting,
                            "complete_prefix_adjoint_required": True,
                            "all_actual_tokens_including_EOS": True,
                            "original_tokens_not_retokenized": True,
                            "replay_sampling_calls": 0,
                        }
                        del values, gradient
                    except Exception as failure:
                        replay_report = {
                            "passed": False,
                            "atol": ATOL,
                            "rtol": RTOL,
                            "error": {"type": type(failure).__name__, "message": str(failure)},
                            "replay_sampling_calls": 0,
                        }
                    _publish(replay_file.parent, replay_report)
                summaries.append(
                    {
                        **row,
                        "call_id": receipt.call_id,
                        "prompt_tokens": len(receipt.prompt_input_ids),
                        "actual_output_tokens": len(receipt.raw_generated_token_ids),
                        "actual_eos": receipt.actual_eos,
                        "native": native,
                        "replay": replay_report,
                        "max_memory_allocated_bytes": torch.cuda.max_memory_allocated(),
                        "max_memory_reserved_bytes": torch.cuda.max_memory_reserved(),
                        "rng_unchanged": _rng_digest(torch) == before["rng"],
                    }
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
        and [module.training for module in model.modules()] == before["modes"]
        and not optimizer.state
        and all(value.grad is None for value in real.values())
    )
    report = {
        "schema": "finance_research_four_call_gate_result.v1",
        "plan_sha256": digest(plan),
        "eval_native_passed": error is None
        and len(summaries) == 4
        and all(case["native"]["passed"] for case in summaries)
        and isolation,
        "feedback_replay_passed": error is None
        and len(summaries) == 4
        and all(case["replay"]["passed"] for case in summaries)
        and isolation,
        "cases": summaries,
        "error": error,
        "real_state_and_RNG_unchanged": isolation,
        "actual_new_generation_calls_this_invocation": actual_new_calls,
        "registered_generation_cap": 4,
        "completed_original_generation_cases": len(summaries),
        "virtual_diagnostics": virtual["diagnostics"],
        "diagnostic_virtual": diagnostic,
        "virtual_is_training_full_G": False,
        "virtual_uses_old_training_Adam_moments": False,
        "real_optimizer_steps": 0,
        "calibration_matrix_sessions": 0,
        "API_calls": 0,
        "elapsed_seconds": time.monotonic() - started,
    }
    del model, provider, optimizer, real, point, virtual, binding, install
    gc.collect()
    torch.cuda.empty_cache()
    return report
