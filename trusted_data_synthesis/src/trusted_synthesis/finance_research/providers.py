"""Explicit eval/feedback providers; only local generation can mint token receipts.

Importing this module does not import torch, load a model, or make a request.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from contextlib import nullcontext
from typing import Any

from .contracts import (
    ContextLimitError,
    ModelIdentity,
    ModelTurn,
    ProviderCallError,
    RunConfig,
    TokenReceipt,
    ToolCall,
    digest,
)
from .qwen_protocol import (
    QWEN_TOOL_PROTOCOL,
    parse_qwen_native_response,
    strict_json_decoder,
)


def _json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _sha(raw: str | bytes) -> str:
    return hashlib.sha256(raw.encode() if isinstance(raw, str) else raw).hexdigest()


def parse_tool_calls(raw: str, *, call_prefix: str) -> tuple[ToolCall, ...]:
    """Strict JSON parsing only: malformed text remains an ordinary model response."""

    decoder = strict_json_decoder()

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
        if (
            not isinstance(function, dict)
            or not isinstance(function.get("name"), str)
            or not function["name"]
            or "arguments" not in function
        ):
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


def canonical_assistant_message(turn: ModelTurn) -> dict[str, Any]:
    """Keep raw samples in the turn, not duplicated beside structured tool calls.

    Local Qwen history uses object-valued arguments as its template requires. The
    API transport converts those objects into JSON strings separately. A malformed
    native response keeps its entire raw text and no fabricated structured call.
    """
    protocol = turn.provider_metadata.get("tool_protocol")
    if protocol == QWEN_TOOL_PROTOCOL:
        content, parsed = parse_qwen_native_response(turn.raw_text, call_prefix="history")
        if [(c.name, c.raw_arguments, c.arguments) for c in parsed] != [
            (c.name, c.raw_arguments, c.arguments) for c in turn.tool_calls
        ]:
            raise ValueError("native tool history disagrees with the retained raw response")
    elif protocol == "scripted-json-fixture-v1" and turn.tool_calls:
        content = ""
    else:
        content = turn.raw_text
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if turn.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.call_id,
                "type": "function",
                "function": {"name": call.name, "arguments": copy.deepcopy(call.arguments)},
            }
            for call in turn.tool_calls
        ]
    return message


def _api_messages(messages):
    """Native API arguments are JSON strings; canonical local messages use dicts."""
    actual = copy.deepcopy(messages)
    decoder = strict_json_decoder()
    for message in actual:
        for call in message.get("tool_calls", []):
            function = call["function"]
            arguments = function["arguments"]
            if isinstance(arguments, str):
                arguments = decoder.decode(arguments)
            if not isinstance(arguments, dict):
                raise ValueError("canonical tool arguments must be a JSON object")
            function["arguments"] = _json(arguments)
    return actual


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
                provider_metadata={"tool_protocol": "scripted-json-fixture-v1"},
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
        protocol = config.local_tool_protocol
        if protocol == QWEN_TOOL_PROTOCOL:
            # The native template renders schemas once. Never add another schema prompt.
            for message in actual_messages:
                for call in message.get("tool_calls", []):
                    if not isinstance(call.get("function", {}).get("arguments"), dict):
                        raise ValueError("Qwen canonical history requires object-valued arguments")
            rendered = self.tokenizer.apply_chat_template(
                actual_messages, tools=tools, tokenize=False, add_generation_prompt=True
            )
        elif protocol in {"legacy-json-v1", "direct-json-v1"}:
            if any(
                message.get("tool_calls") or message.get("role") == "tool"
                for message in actual_messages
            ):
                raise ValueError(
                    "plain JSON history cannot contain structured tool calls or tool feedback"
                )
            if protocol == "direct-json-v1" and tools:
                raise ValueError("Direct-DSL permits no tools")
            # H0 owns the complete old JSON grammar and schemas in its system prompt.
            # Supplying tools here would silently inject the incompatible native grammar.
            rendered = self.tokenizer.apply_chat_template(
                actual_messages, tokenize=False, add_generation_prompt=True
            )
        else:
            raise ValueError("unregistered local tool protocol")
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
            "tools": copy.deepcopy(tools) if protocol == QWEN_TOOL_PROTOCOL else [],
            "config": config.model_dump(mode="json"),
            "rendered_prompt_sha256": _sha(rendered),
            "tool_protocol": protocol,
            "template_tools_kwarg_used": protocol == QWEN_TOOL_PROTOCOL,
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
                try:
                    result = self.model.generate(
                        input_ids=ids,
                        attention_mask=torch.ones_like(ids),
                        generation_config=generation,
                        logits_to_keep=1,
                    )
                except Exception as exception:
                    raise ProviderCallError(
                        "local generation started but no token receipt was returned",
                        settlement="unknown",
                        actual_model_calls=1,
                        evidence={
                            "request_sha256": request_hash,
                            "public_request": request,
                            "exception_type": type(exception).__name__,
                            "token_receipt_available": False,
                        },
                    ) from exception
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
        calls = (
            parse_qwen_native_response(raw, call_prefix=call_id)[1]
            if protocol == QWEN_TOOL_PROTOCOL
            else ()
        )
        return ModelTurn(
            raw_text=raw,
            tool_calls=calls,
            finish_reason=finish,
            receipt=receipt,
            usage={"prompt_tokens": len(prompt), "completion_tokens": len(output)},
            provider_metadata={
                "request": request,
                "actual_model_generation": True,
                "attention_backend": "FLASH_ATTENTION" if cuda else "CPU_TEST",
                "tool_protocol": protocol,
                "tool_schemas_rendered_by": (
                    "native_chat_template_only"
                    if protocol == QWEN_TOOL_PROTOCOL
                    else "legacy_system_prompt_only"
                    if protocol == "legacy-json-v1"
                    else "direct_public_submission_prompt_only"
                ),
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
            "messages": _api_messages(messages),
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_new_tokens,
            "stream": False,
        }
        if tools:
            body["tools"] = copy.deepcopy(tools)
        headers = {"Authorization": "Bearer " + self._key}
        request_hash = digest(body)
        try:
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
        except Exception as exception:
            raise ProviderCallError(
                "API request did not return a service response; settlement is unknown",
                settlement="unknown",
                actual_model_calls=1,
                evidence={
                    "request_sha256": request_hash,
                    "public_request": body,
                    "exception_type": type(exception).__name__,
                    "service_response_received": False,
                    "retries": 0,
                },
            ) from exception
        status = getattr(response, "status_code", 200)
        if not 200 <= status < 300:
            raise ProviderCallError(
                f"API returned HTTP {status}; no retry or fallback",
                settlement="service_failure",
                actual_model_calls=1,
                evidence={
                    "request_sha256": request_hash,
                    "public_request": body,
                    "http_status": status,
                    "raw_service_body": response.text,
                    "service_response_received": True,
                    "billing_status": "not_inferred_from_http_status",
                    "retries": 0,
                },
            )
        response.raise_for_status()
        value = None
        try:
            value = response.json()
            # A stored response must itself be strict JSON, including finite values.
            _json(value)
            choices = value.get("choices", [])
            if len(choices) != 1:
                raise ValueError("API must return exactly one choice")
            choice, response_model = choices[0], value.get("model")
            if response_model is not None and response_model != "deepseek-flash":
                raise ValueError("API returned a different model; no fallback is allowed")
            message = choice["message"]
            if not isinstance(message, dict) or not ({"content", "tool_calls"} & set(message)):
                raise ValueError("API response lacks the assistant message fields")
            if not isinstance(choice.get("finish_reason"), str):
                raise ValueError("API response has no completed finish_reason")
            usage = value["usage"]
            if not isinstance(usage, dict) or any(
                type(usage.get(field)) is not int or usage[field] < 0
                for field in ("prompt_tokens", "completion_tokens")
            ):
                raise ValueError("API response lacks complete usage accounting")
            raw = message.get("content") or ""
            if not isinstance(raw, str):
                raise ValueError("API returned non-text assistant content")
            raw_calls = message.get("tool_calls") or []
            parse_error = None
            try:
                calls = parse_tool_calls(
                    _json({"tool_calls": raw_calls}),
                    call_prefix=str(value.get("id", "api")),
                )
            except (ValueError, TypeError, IndexError, RecursionError):
                calls = ()
            if raw_calls and not calls:
                # A fully returned/usage-accounted model format failure is a result,
                # not an unknown network call or an opportunity to regenerate.
                parse_error = "malformed_native_tool_calls_no_repair"
        except Exception as exception:
            evidence = {
                "request_sha256": request_hash,
                "public_request": body,
                "http_status": status,
                "raw_service_body": getattr(response, "text", ""),
                "service_response_received": True,
                "exception_type": type(exception).__name__,
                "valid_turn_returned": False,
                "retries": 0,
            }
            try:
                _json(value)
                evidence["api_response"] = value
            except (ValueError, TypeError):
                pass  # Invalid JSON bytes remain in raw_service_body, never repaired.
            raise ProviderCallError(
                "API response was received but no valid turn could be settled",
                settlement="unknown",
                actual_model_calls=1,
                evidence=evidence,
            ) from exception
        return ModelTurn(
            raw_text=raw,
            tool_calls=calls,
            finish_reason=choice.get("finish_reason") or "unknown",
            usage={key: item for key, item in usage.items() if type(item) is int},
            provider_metadata={
                "request_sha256": digest(body),
                "api_response": value,
                "public_request": body,
                "tool_protocol": "deepseek-native-tool-calls-v1",
                "parse_error": parse_error,
                "model_tool_format_failure": parse_error is not None,
                "local_token_receipt_available": False,
                "context_limit_locally_verified": False,
                "requested_context_limit": config.context_limit,
                "API_and_local_token_budget_equivalence_claimed": False,
                "retries": 0,
            },
        )
