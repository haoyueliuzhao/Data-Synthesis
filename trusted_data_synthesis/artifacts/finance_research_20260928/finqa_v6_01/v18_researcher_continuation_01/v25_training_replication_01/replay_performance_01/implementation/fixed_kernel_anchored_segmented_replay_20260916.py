"""Exact cached numerical path with response-local block adjoints and pure prefill.

An append-only DynamicLayer cache is stored ONCE; boundaries are immutable prefix
views of that complete cache. A detached boundary is a VJP input, not a constant:
every boundary adjoint propagates through preceding blocks and the prefill.
"""

# ruff: noqa: E501 -- explicit mathematical contract strings
import contextlib
import math
import time

import fixed_kernel_anchored_sources_gpu_gate_20260916 as gate
import torch
from fixed_kernel_anchored_canonical_saves_20260916 import (
    CanonicalSavedTensorStore,
    FrozenLayoutBank,
)
from fixed_kernel_anchored_saved_tensors_20260916 import signature
from torch import nn
from transformers.cache_utils import DynamicCache, DynamicLayer

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


def cache_tensors(cache):
    p.require(
        all(type(layer) is DynamicLayer for layer in cache.layers),
        "adjoint.only_bound_append_only_DynamicLayer",
    )
    return tuple(value for layer in cache.layers for value in (layer.keys, layer.values))


def cache_from_prefix(model, complete, length, *, gradient):
    device = next(model.parameters()).device
    leaves = tuple(
        value[:, :, :length, :].contiguous().to(device).detach().requires_grad_(gradient)
        for value in complete
    )
    cache = DynamicCache(config=model.config)
    for index in range(len(leaves) // 2):
        cache.update(leaves[2 * index], leaves[2 * index + 1], index)
    return cache, leaves


@contextlib.contextmanager
def pure_prefill_checkpoints(model, enabled=True, *, bank=None, offload=True):
    """Every recomputation owns a fresh local cache; never mutates live history twice."""
    if not enabled:
        yield
        return
    restored = []
    for index, layer in enumerate(model.model.layers):
        old = layer.forward
        had_own = "forward" in layer.__dict__
        old_attribute = layer.__dict__.get("forward")

        def forward(hidden_states, _index=index, _old=old, **kwargs):
            destination = kwargs["past_key_values"]
            p.require(
                destination is not None and destination.layers[_index].get_seq_length() == 0,
                "adjoint.prefill_destination_empty_per_layer",
            )
            local_kwargs = {key: value for key, value in kwargs.items() if key != "past_key_values"}

            parameters = tuple(value for value in model.parameters() if value.requires_grad)

            class PureLayer(torch.autograd.Function):
                @staticmethod
                def forward(ctx, hidden, *theta):
                    ctx.set_materialize_grads(False)
                    ctx.save_for_backward(hidden)
                    ctx.theta = theta
                    ctx.versions = tuple(signature(value) for value in theta)
                    isolated = DynamicCache(config=model.config)
                    output = _old(hidden, **local_kwargs, past_key_values=isolated)
                    row = isolated.layers[_index]
                    return output, row.keys, row.values

                @staticmethod
                def backward(ctx, *cotangents):
                    p.require(
                        tuple(signature(value) for value in ctx.theta) == ctx.versions,
                        "adjoint.same_virtual_parameters_during_prefill_recompute",
                    )
                    hidden = ctx.saved_tensors[0].detach().requires_grad_(True)
                    storage = CanonicalSavedTensorStore(model, bank=bank) if offload else None
                    saving = storage.context() if storage else contextlib.nullcontext()
                    with torch.enable_grad(), saving:
                        isolated = DynamicCache(config=model.config)
                        output = _old(hidden, **local_kwargs, past_key_values=isolated)
                        row = isolated.layers[_index]
                        active = [
                            (value, grad)
                            for value, grad in zip(
                                (output, row.keys, row.values), cotangents, strict=True
                            )
                            if grad is not None and value.requires_grad
                        ]
                        result = torch.autograd.grad(
                            tuple(value for value, _ in active),
                            (hidden, *ctx.theta),
                            grad_outputs=tuple(grad for _, grad in active),
                            allow_unused=True,
                        )
                    return result

            output, key, value = PureLayer.apply(hidden_states, *parameters)
            destination.update(key, value, _index)
            return output

        layer.forward = forward
        restored.append((layer, had_own, old_attribute))
    try:
        yield
    finally:
        for layer, had_own, old_attribute in restored:
            if had_own:
                layer.forward = old_attribute
            else:
                delattr(layer, "forward")


def _call(model, ids, length, cache):
    return model(
        input_ids=ids,
        attention_mask=torch.ones((1, length), dtype=torch.long, device=ids.device),
        use_cache=True,
        past_key_values=cache,
        logits_to_keep=1,
    )


def _vjp(outputs, inputs, covectors):
    # Constant cache fields have exactly zero parameter derivative. This does
    # not remove any differentiable boundary or its incoming adjoint.
    active = [
        (value, cotangent)
        for value, cotangent in zip(outputs, covectors, strict=True)
        if value.requires_grad
    ]
    if not active:
        return (None,) * len(inputs)
    return torch.autograd.grad(
        tuple(value for value, _ in active),
        inputs,
        grad_outputs=tuple(value for _, value in active),
        allow_unused=True,
    )


def forward_saved_tokens(model, prompt, targets):
    """No sampling; reproduce cached probabilities and retain one final KV snapshot."""
    device = next(model.parameters()).device
    cache, values = None, []
    ids = torch.tensor([prompt], dtype=torch.long, device=device)
    with torch.no_grad():
        for index, target in enumerate(targets):
            output = _call(model, ids, len(prompt) + index, cache)
            cache = output.past_key_values
            values.append(torch.log_softmax(output.logits[0, -1].float(), -1)[target].detach())
            ids = torch.tensor([[target]], dtype=torch.long, device=device)
        state = cache_tensors(cache)
        p.require(
            all(value.shape[-2] == len(prompt) + len(targets) - 1 for value in state),
            "adjoint.exact_complete_cache_length",
        )
        complete = tuple(value.detach().to("cpu").contiguous() for value in state)
    return torch.stack(values), complete


class SegmentedOperation(nn.Module):
    def __init__(self, model, names, block_size, prefill_checkpoint, offload, event_sink):
        super().__init__()
        self.model, self.names = model, tuple(names)
        self.block_size, self.prefill_checkpoint = block_size, prefill_checkpoint
        self.offload, self.emit = offload, event_sink or (lambda event: None)

    def forward(self, prompt, targets, expected):
        parameters = dict(self.model.named_parameters())
        leaves = [parameters[name] for name in self.names]
        device = leaves[0].device
        scores, complete = forward_saved_tokens(self.model, prompt, targets)
        if expected is not None:
            reference = torch.tensor(expected, dtype=scores.dtype, device=device)
            p.require(
                torch.allclose(scores, reference, atol=gate.ATOL, rtol=gate.RTOL),
                "adjoint.saved_sampling_probability_mismatch",
            )
        gradient = {
            name: torch.zeros_like(value) for name, value in zip(self.names, leaves, strict=True)
        }
        adjoint = None
        replayed = torch.empty_like(scores)
        maximum_host = 0
        forward_tokens = len(targets)
        block_count = 0
        bank = FrozenLayoutBank(self.model) if self.offload else None
        ranges = [
            (start, min(start + self.block_size, len(targets)))
            for start in range(1, len(targets), self.block_size)
        ]
        for start, end in reversed(ranges):
            store = CanonicalSavedTensorStore(self.model, bank=bank) if self.offload else None
            context = store.context() if store else contextlib.nullcontext()
            with context:
                cache, incoming = cache_from_prefix(
                    self.model, complete, len(prompt) + start - 1, gradient=True
                )
                logps = []
                for index in range(start, end):
                    ids = torch.tensor([[targets[index - 1]]], dtype=torch.long, device=device)
                    output = _call(self.model, ids, len(prompt) + index, cache)
                    cache = output.past_key_values
                    logps.append(
                        torch.log_softmax(output.logits[0, -1].float(), -1)[targets[index]]
                    )
                values = torch.stack(logps)
                p.require(
                    torch.allclose(
                        values.detach(), scores[start:end], atol=gate.ATOL, rtol=gate.RTOL
                    ),
                    "adjoint.block_recompute_probability_mismatch",
                )
                outgoing = cache_tensors(cache)
                outputs = (values.sum(), *outgoing) if adjoint is not None else (values.sum(),)
                covectors = (
                    (torch.ones((), device=device), *adjoint)
                    if adjoint is not None
                    else (torch.ones((), device=device),)
                )
                derivatives = _vjp(outputs, (*leaves, *incoming), covectors)
                for name, value in zip(self.names, derivatives[: len(leaves)], strict=True):
                    if value is not None:
                        gradient[name].add_(value.detach())
                adjoint = tuple(
                    torch.zeros_like(value) if derivative is None else derivative.detach()
                    for value, derivative in zip(incoming, derivatives[len(leaves) :], strict=True)
                )
                replayed[start:end] = values.detach()
                del (
                    derivatives,
                    outputs,
                    covectors,
                    outgoing,
                    values,
                    logps,
                    output,
                    cache,
                    incoming,
                )
            block_count += 1
            forward_tokens += end - start
            if store:
                measurement = store.report()
                maximum_host = max(maximum_host, measurement["maximum_total_live_host_bytes"])
                p.require(
                    sum(measurement["live_host_bytes_after_response"].values()) == 0,
                    "adjoint.block_saved_tensor_release",
                )
            self.emit(
                dict(
                    event="decode_block_backward",
                    start=start,
                    end=end,
                    blocks_completed=block_count,
                )
            )

        store = CanonicalSavedTensorStore(self.model, bank=bank) if self.offload else None
        context = store.context() if store else contextlib.nullcontext()
        with (
            context,
            pure_prefill_checkpoints(
                self.model, self.prefill_checkpoint, bank=bank, offload=self.offload
            ),
        ):
            cache = DynamicCache(config=self.model.config)
            ids = torch.tensor([prompt], dtype=torch.long, device=device)
            output = _call(self.model, ids, len(prompt), cache)
            value = torch.log_softmax(output.logits[0, -1].float(), -1)[targets[0]]
            p.require(
                torch.allclose(value.detach(), scores[0], atol=gate.ATOL, rtol=gate.RTOL),
                "adjoint.prefill_recompute_probability_mismatch",
            )
            outgoing = cache_tensors(output.past_key_values)
            outputs = (value, *outgoing) if adjoint is not None else (value,)
            covectors = (
                (torch.ones_like(value), *adjoint)
                if adjoint is not None
                else (torch.ones_like(value),)
            )
            derivatives = _vjp(outputs, leaves, covectors)
            for name, derivative in zip(self.names, derivatives, strict=True):
                if derivative is not None:
                    gradient[name].add_(derivative.detach())
            replayed[0] = value.detach()
            del derivatives, outputs, covectors, outgoing, value, output, cache
        if store:
            measurement = store.report()
            maximum_host = max(maximum_host, measurement["maximum_total_live_host_bytes"])
            p.require(
                sum(measurement["live_host_bytes_after_response"].values()) == 0,
                "adjoint.prefill_saved_tensor_release",
            )
        p.require(
            all(bool(torch.isfinite(value).all()) for value in gradient.values()),
            "adjoint.finite_complete_parameter_gradient",
        )
        self.emit(dict(event="prefill_adjoint_complete", prefix_gradient_included=True))
        p.require(
            bank is None or (bank.live_host == bank.live_pinned == 0),
            "adjoint.all_nested_saved_tensor_release",
        )
        return (
            replayed,
            gradient,
            dict(
                block_size=self.block_size,
                decode_blocks=block_count,
                single_complete_CPU_KV_bytes=sum(
                    value.numel() * value.element_size() for value in complete
                ),
                maximum_live_offloaded_tensor_bytes=maximum_host,
                all_nested_maximum_live_host_bytes=bank.peak_host if bank else 0,
                all_nested_maximum_live_pinned_bytes=bank.peak_pinned if bank else 0,
                all_nested_live_saved_bytes_after_response=bank.live_host if bank else 0,
                extra_resident_canonical_weight_bytes=bank.extra_bytes if bank else 0,
                cached_forward_target_positions=forward_tokens + 1,
                prefill_forward_passes=2,
                prefill_layer_recomputation=self.prefill_checkpoint,
                complete_prefix_adjoint_included=True,
                dense_Jacobian_materialized=False,
                sampling_calls=0,
                output_tokens=len(targets),
            ),
        )


def segmented_logp(
    model,
    theta,
    prompt,
    targets,
    *,
    expected=None,
    block_size=8,
    prefill_checkpoint=True,
    offload=True,
    event_sink=None,
):
    p.require(
        prompt
        and targets
        and len(prompt) + len(targets) <= 24576
        and len(targets) <= 2048
        and type(block_size) is int
        and 1 <= block_size <= 64,
        "adjoint.exact_response_contract",
    )
    p.require(
        getattr(model.config, "model_type", None) == "qwen2"
        and all(kind == "full_attention" for kind in model.config.layer_types),
        "adjoint.registered_Qwen_full_attention_cache",
    )
    started = time.monotonic()
    operation = SegmentedOperation(
        model, theta, block_size, prefill_checkpoint, offload, event_sink
    )
    overrides = {"model." + name: value for name, value in theta.items()}
    overrides.update(
        {"model." + name: value.detach().clone() for name, value in model.named_buffers()}
    )
    with gate.proxy_mode(model, gradient=False):
        values, gradient, accounting = torch.func.functional_call(
            operation, overrides, (prompt, targets, expected), strict=False
        )
    accounting["elapsed_seconds"] = time.monotonic() - started
    p.require(math.isfinite(accounting["elapsed_seconds"]), "adjoint.valid_duration")
    return values, gradient, accounting
