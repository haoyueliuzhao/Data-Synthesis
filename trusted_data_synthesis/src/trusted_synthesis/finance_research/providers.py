"""Explicit eval/feedback providers; only local generation can mint token receipts.

Importing this module does not import torch, load a model, or make a request.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from contextlib import nullcontext
from typing import Any

from .contracts import (
    ContextLimitError,
    ModelIdentity,
    ModelTurn,
    RunConfig,
    TokenReceipt,
    ToolCall,
    digest,
)


def _json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _sha(raw: str | bytes) -> str:
    return hashlib.sha256(raw.encode() if isinstance(raw, str) else raw).hexdigest()


def parse_tool_calls(raw: str, *, call_prefix: str) -> tuple[ToolCall, ...]:
    """Strict JSON parsing only: malformed text remains an ordinary model response."""

    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = item
        return result

    def constant(value):
        raise ValueError("nonfinite JSON constant")

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite JSON number")
        return result

    decoder = json.JSONDecoder(
        object_pairs_hook=pairs, parse_constant=constant, parse_float=finite_float
    )

    def skip(index):
        while index < len(raw) and raw[index].isspace():
            index += 1
        return index

    def members(start):
        fields, index = {}, skip(start + 1)
        while raw[index] != "}":
            key, end = decoder.raw_decode(raw, index)
            value_start = skip(skip(end) + 1)  # The full strict parse verified the colon.
            _, end = decoder.raw_decode(raw, value_start)
            fields[key] = (value_start, end)
            index = skip(end)
            if raw[index] == ",":
                index = skip(index + 1)
        return fields

    try:
        value = decoder.decode(raw)
    except (ValueError, TypeError):
        return ()
    if not isinstance(value, dict):
        return ()
    rows = value.get("tool_calls", [value] if "name" in value else [])
    if not isinstance(rows, list):
        return ()
    fields = members(skip(0))
    if "tool_calls" in value:
        index = skip(fields["tool_calls"][0] + 1)
        starts = []
        while raw[index] != "]":
            starts.append(index)
            _, index = decoder.raw_decode(raw, index)
            index = skip(index)
            if raw[index] == ",":
                index = skip(index + 1)
    else:
        starts = [skip(0)] if rows else []
    calls = []
    for index, (row, start) in enumerate(zip(rows, starts, strict=True)):
        if not isinstance(row, dict):
            return ()
        function = row.get("function", row)
        if not isinstance(function, dict) or not isinstance(function.get("name"), str):
            return ()
        raw_arguments = function.get("arguments", {})
        try:
            arguments = (
                decoder.decode(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            )
        except ValueError:
            return ()
        if not isinstance(arguments, dict):
            return ()
        row_fields = members(start)
        function_fields = members(row_fields["function"][0]) if "function" in row else row_fields
        span = function_fields.get("arguments")
        argument_bytes = raw[span[0] : span[1]] if span else "{}"
        calls.append(
            ToolCall(
                call_id=str(row.get("id", f"{call_prefix}:{index}")),
                name=function["name"],
                raw_arguments=raw_arguments if isinstance(raw_arguments, str) else argument_bytes,
                arguments=arguments,
            )
        )
    return tuple(calls)


class ScriptedProvider:
    """Deterministic test fixture, never admissible as VTDO feedback."""

    def __init__(self, turns: list[ModelTurn | str], *, model_id: str = "scripted-fixture"):
        self.identity = ModelIdentity(backend="scripted", model_id=model_id)
        self._turns = iter(turns)
        self._calls = 0
        self.actual_model_calls = 0

    async def chat(self, messages, tools, config):
        if config.tier != "EVAL_NATIVE":
            raise ValueError("scripted fixtures cannot supply VTDO_FEEDBACK")
        self._calls += 1
        turn = next(self._turns)
        if isinstance(turn, str):
            turn = ModelTurn(
                raw_text=turn,
                tool_calls=parse_tool_calls(turn, call_prefix=f"fixture:{self._calls}"),
            )
        if turn.receipt is not None:
            raise ValueError("scripted fixtures cannot carry a real token receipt")
        return turn.model_copy(
            update={
                "provider_metadata": {
                    **turn.provider_metadata,
                    "fixture": True,
                    "actual_model_generation": False,
                }
            }
        )


def parameter_digest(parameters) -> str:
    """Byte-compatible with the frozen anchored gate's named tensor digest."""
    import torch

    result = hashlib.sha256()
    for name, value in sorted(parameters.items()):
        result.update(_json([name, str(value.dtype), list(value.shape)]).encode())
        result.update(value.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
    return result.hexdigest()


def _parameters(model, supplied=None):
    values = dict(model.named_parameters())
    if supplied is not None:
        supplied = dict(supplied)
        if any(
            name not in values
            or value.data_ptr() != values[name].data_ptr()
            or value.shape != values[name].shape
            or value.dtype != values[name].dtype
            for name, value in supplied.items()
        ):
            raise ValueError("supplied parameter coordinates are not installed in this model")
        return supplied
    adapters = {name: value for name, value in values.items() if ".lora_" in name}
    return adapters or {name: value for name, value in values.items() if value.requires_grad}


def tokenizer_binding(tokenizer) -> tuple[str, str]:
    backend = getattr(tokenizer, "backend_tokenizer", None)
    serial = backend.to_str() if backend is not None else tokenizer.get_vocab()
    return digest({"tokenizer": serial, "special_tokens": tokenizer.special_tokens_map}), digest(
        tokenizer.chat_template
    )


def local_model_identity(model, tokenizer, *, model_id, point_id, parameter_tensors=None):
    parameters = _parameters(model, parameter_tensors)
    if not parameters:
        raise ValueError("explicit LoRA/current parameter coordinates are required")
    tokens, template = tokenizer_binding(tokenizer)
    return ModelIdentity(
        backend="local_torch",
        model_id=model_id,
        point_id=point_id,
        parameter_digest=parameter_digest(parameters),
        tokenizer_digest=tokens,
        chat_template_digest=template,
    )


class LocalTorchProvider:
    """Use an already-loaded Student, preserving actual prompt, sampled tokens and RNG.

    The caller owns checkpoint loading and virtual-point installation. A bound provider
    cannot survive a parameter update: construct another provider for the new point.
    CPU execution exists for small mock tests; admitted production replay requires CUDA
    Qwen2 full attention, enforced by the frozen replay backend.
    """

    def __init__(self, model, tokenizer, identity: ModelIdentity, *, parameter_tensors=None):
        if identity.backend != "local_torch":
            raise ValueError("local provider requires local_torch identity")
        self.model, self.tokenizer, self.identity = model, tokenizer, identity
        self.parameters = _parameters(model, parameter_tensors)
        if identity.parameter_digest is not None:
            if (
                not self.parameters
                or parameter_digest(self.parameters) != identity.parameter_digest
            ):
                raise ValueError("loaded parameter bytes do not match the registered point")
        token_hash, template_hash = tokenizer_binding(tokenizer)
        if identity.tokenizer_digest not in (
            None,
            token_hash,
        ) or identity.chat_template_digest not in (None, template_hash):
            raise ValueError("tokenizer/chat template binding mismatch")
        self._versions = self._storage_versions()
        self._calls = 0
        self.actual_model_calls = 0

    def _storage_versions(self):
        return {
            name: (value.data_ptr(), value._version)
            for name, value in (*self.model.named_parameters(), *self.model.named_buffers())
        }

    async def chat(self, messages, tools, config: RunConfig):
        import torch
        from transformers import GenerationConfig

        if self._storage_versions() != self._versions:
            raise ValueError("provider parameter point changed; rebind before generation")
        if config.tier == "VTDO_FEEDBACK":
            if config.role != "feedback":
                raise ValueError("VTDO_FEEDBACK is restricted to admitted feedback-role data")
            if not all(
                (
                    self.identity.point_id,
                    self.identity.parameter_digest,
                    self.identity.tokenizer_digest,
                    self.identity.chat_template_digest,
                )
            ):
                raise ValueError("VTDO_FEEDBACK requires the complete local point binding")
            if (config.temperature, config.top_p, config.top_k) != (1.0, 1.0, 0):
                raise ValueError("VTDO_FEEDBACK requires unmodified T=1, top_p=1, top_k=0")
            if config.context_limit > 24576 or config.max_new_tokens > 2048:
                raise ValueError("feedback exceeds the admitted replay backend limits")
        actual_messages = copy.deepcopy(messages)
        # Make tool schemas visible even if a tokenizer template ignores its tools kwarg.
        if tools:
            tool_message = "Available tools (JSON schemas):\n" + _json(tools)
            if actual_messages and actual_messages[0].get("role") == "system":
                actual_messages[0]["content"] += "\n" + tool_message
            else:
                actual_messages.insert(0, {"role": "system", "content": tool_message})
        rendered = self.tokenizer.apply_chat_template(
            actual_messages, tools=tools, tokenize=False, add_generation_prompt=True
        )
        prompt = self.tokenizer(
            rendered, add_special_tokens=False, truncation=False, padding=False
        )["input_ids"]
        if len(prompt) + config.max_new_tokens > config.context_limit:
            raise ContextLimitError("full prompt plus output reservation exceeds context_limit")
        if not prompt:
            raise ValueError("empty rendered prompt")
        device = next(self.model.parameters()).device
        cuda = device.type == "cuda"
        devices = (
            [device.index if device.index is not None else torch.cuda.current_device()]
            if cuda
            else []
        )
        eos = getattr(self.model.generation_config, "eos_token_id", None)
        eos = eos if eos is not None else self.tokenizer.eos_token_id
        eos_ids = list(eos) if isinstance(eos, (tuple, list)) else [eos] if eos is not None else []
        request = {
            "messages": actual_messages,
            "tools": copy.deepcopy(tools),
            "config": config.model_dump(mode="json"),
            "rendered_prompt_sha256": _sha(rendered),
        }
        request_hash = digest(request)
        self._calls += 1
        # Request history + registered seed make resume and scheduling order irrelevant.
        seed = int(digest([config.seed, request_hash])[:16], 16) % (2**63)
        sampled = config.temperature > 0
        options = dict(
            do_sample=sampled,
            max_new_tokens=config.max_new_tokens,
            use_cache=True,
            eos_token_id=eos,
            pad_token_id=self.tokenizer.pad_token_id,
            bos_token_id=self.tokenizer.bos_token_id,
            return_dict_in_generate=True,
            output_scores=True,
            num_beams=1,
            num_return_sequences=1,
            repetition_penalty=1.0,
        )
        if sampled:
            options.update(temperature=config.temperature, top_p=config.top_p, top_k=config.top_k)
        generation = GenerationConfig(**options)
        modes = [(module, module.training) for module in self.model.modules()]
        if cuda:
            from torch.nn.attention import SDPBackend, sdpa_kernel

            attention = sdpa_kernel(SDPBackend.FLASH_ATTENTION)
        else:
            attention = nullcontext()

        def rng_hash():
            states = {"cpu": _sha(torch.get_rng_state().numpy().tobytes())}
            if cuda:
                states["cuda"] = _sha(torch.cuda.get_rng_state(device).cpu().numpy().tobytes())
            return digest(states)

        try:
            self.model.eval()
            with torch.random.fork_rng(devices=devices), torch.no_grad(), attention:
                torch.random.default_generator.manual_seed(seed)
                if cuda:
                    torch.cuda.default_generators[devices[0]].manual_seed(seed)
                before = rng_hash()
                cache = getattr(self.model, "_cache", None)
                if cache is not None:
                    if not callable(getattr(cache, "reset", None)):
                        raise ValueError("generation cache is not resettable")
                    cache.reset()
                    delattr(self.model, "_cache")
                ids = torch.tensor([prompt], dtype=torch.long, device=device)
                self.actual_model_calls += 1
                result = self.model.generate(
                    input_ids=ids,
                    attention_mask=torch.ones_like(ids),
                    generation_config=generation,
                    logits_to_keep=1,
                )
                after = rng_hash()
                sequence = result.sequences[0].tolist()
                if sequence[: len(prompt)] != prompt:
                    raise ValueError("generated sequence changed the actual prompt prefix")
                output = sequence[len(prompt) :]
                if not 0 < len(output) <= config.max_new_tokens or len(result.scores) != len(
                    output
                ):
                    raise ValueError("invalid generated token/score count")
                logps = (
                    tuple(
                        torch.stack(
                            [
                                torch.log_softmax(score[0].float(), -1)[token].clone()
                                for token, score in zip(output, result.scores, strict=True)
                            ]
                        )
                        .cpu()
                        .tolist()
                    )
                    if sampled
                    else None
                )
        finally:
            for module, training in modes:
                module.training = training
        if self._storage_versions() != self._versions:
            raise ValueError("model generation mutated bound parameters")
        ended = output[-1] in eos_ids
        raw = self.tokenizer.decode(
            output[:-1] if ended else output,
            skip_special_tokens=False,
            clean_up_tokenization_spaces=False,
        )
        finish = "stop" if ended else "length"
        call_id = "local:" + digest([request_hash, output])
        receipt = TokenReceipt(
            call_id=call_id,
            identity=self.identity,
            request_sha256=request_hash,
            prompt_input_ids=tuple(prompt),
            raw_generated_token_ids=tuple(output),
            sampled_token_logprobs=logps,
            actual_eos=ended,
            finish_reason=finish,
            rng_before_sha256=before,
            rng_after_sha256=after,
            sampling={
                "do_sample": sampled,
                "temperature": config.temperature,
                "top_p": config.top_p,
                "top_k": config.top_k,
                "seed": seed,
                "max_new_tokens": config.max_new_tokens,
                "context_limit": config.context_limit,
                "eos_token_ids": eos_ids,
                "actual_model_generate_calls": 1,
                "context_truncated": False,
                "host_JSON_repair": False,
                "length_normalized": False,
                "SFT_mask_used": False,
            },
            raw_response_sha256=_sha(raw),
        )
        return ModelTurn(
            raw_text=raw,
            tool_calls=parse_tool_calls(raw, call_prefix=call_id),
            finish_reason=finish,
            receipt=receipt,
            usage={"prompt_tokens": len(prompt), "completion_tokens": len(output)},
            provider_metadata={
                "request": request,
                "actual_model_generation": True,
                "attention_backend": "FLASH_ATTENTION" if cuda else "CPU_TEST",
            },
        )


class DeepSeekFlashProvider:
    """API-only evaluation. No token receipts, retry, or model fallback."""

    def __init__(self, *, api_key=None, model="deepseek-flash", client=None, timeout=120.0):
        if model != "deepseek-flash":
            raise ValueError("new research API calls must use deepseek-flash")
        self.identity = ModelIdentity(backend="deepseek_api", model_id=model)
        self._key = api_key if api_key is not None else os.environ.get("DEEPSEEK_API_KEY")
        if not self._key:
            raise ValueError("DEEPSEEK_API_KEY is required")
        self._client, self.timeout = client, timeout
        self.actual_model_calls = 0

    async def chat(self, messages, tools, config: RunConfig):
        if config.tier != "EVAL_NATIVE":
            raise ValueError("API responses cannot supply VTDO_FEEDBACK token gradients")
        if self.identity.model_id != "deepseek-flash" or config.api_model != "deepseek-flash":
            raise ValueError("API model must be exactly deepseek-flash before the request")
        body = {
            "model": "deepseek-flash",
            "messages": copy.deepcopy(messages),
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_new_tokens,
            "stream": False,
        }
        if tools:
            body["tools"] = copy.deepcopy(tools)
        headers = {"Authorization": "Bearer " + self._key}
        if self._client is None:
            import httpx

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                self.actual_model_calls += 1
                response = await client.post(
                    "https://api.deepseek.com/chat/completions", json=body, headers=headers
                )
        else:
            self.actual_model_calls += 1
            response = await self._client.post(
                "https://api.deepseek.com/chat/completions",
                json=body,
                headers=headers,
                timeout=self.timeout,
            )
        response.raise_for_status()
        value = response.json()
        choices = value.get("choices", [])
        if len(choices) != 1:
            raise ValueError("API must return exactly one choice")
        choice, response_model = choices[0], value.get("model")
        if response_model is not None and response_model != "deepseek-flash":
            raise ValueError("API returned a different model; no fallback is allowed")
        message = choice["message"]
        raw = message.get("content") or ""
        calls = parse_tool_calls(
            _json({"tool_calls": message.get("tool_calls", [])}),
            call_prefix=str(value.get("id", "api")),
        )
        if message.get("tool_calls") and not calls:
            raise ValueError("malformed API tool-call arguments; no repair")
        return ModelTurn(
            raw_text=raw,
            tool_calls=calls,
            finish_reason=choice.get("finish_reason") or "unknown",
            usage={key: item for key, item in value.get("usage", {}).items() if type(item) is int},
            provider_metadata={
                "request_sha256": digest(body),
                "api_response": value,
                "local_token_receipt_available": False,
                "context_limit_locally_verified": False,
                "requested_context_limit": config.context_limit,
                "API_and_local_token_budget_equivalence_claimed": False,
                "retries": 0,
            },
        )
