"""Inference-only V73 generation and fixed-parent-response probability calls.

The caller owns leases, the immutable per-call intent/result journal and UNKNOWN
handling. This adapter never executes a tool, runs a scorer, creates an optimizer
or starts a second assistant turn. Imports do not load weights or initialize CUDA.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from contextlib import nullcontext
import copy
import gc
import importlib
import json
from pathlib import Path


LOG_SOFTMAX_CHUNK = 64


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _modules():
    binding = importlib.import_module("finqa_v73_binding")
    binding.install_scientific_paths()
    binding.install_registered_auxiliary()
    final = binding.source_v72("finqa_v72_evaluation")._runtime()
    model_impl = importlib.import_module(
        "trusted_synthesis.experiments.finance_qa_vnext_pq_student.model")
    measurement = importlib.import_module("finqa_v73_measurement")
    return binding, final, model_impl, measurement


def read_checkpoint(reference, binding, final):
    """Read the complete saved payload on CPU, without creating Adam/RNG objects."""
    directory = Path(reference["path"])
    record_path, state_path = directory / "record.json", directory / "state.pt"
    require(not directory.is_symlink() and not state_path.is_symlink(),
            "registered checkpoint must not be redirected through a symlink")
    require(binding.sha(record_path) == reference["record_sha256"]
            and binding.sha(state_path) == reference["state_sha256"],
            "registered checkpoint bytes changed")
    record = json.loads(record_path.read_bytes())
    require(record["state_sha256"] == reference["state_sha256"]
            and record["actual_state_digest"] == reference["actual_state_digest"]
            and record["step"] == reference["step"], "checkpoint coordinate changed")
    state = final.torch.load(state_path, map_location="cpu", weights_only=False)
    require(final._tree_digest(state) == reference["actual_state_digest"],
            "actual saved checkpoint state digest changed")
    require(state["step"] == reference["step"], "payload step differs from checkpoint")
    return state


def install_saved_adapters(model, state, model_impl, final):
    """Use original LowRankLinear.forward with saved A/B and no random init.

    Calling the original constructor would initialize fresh LoRA A. Instead build
    that exact class as an nn.Module and attach the already saved tensors. All
    parameters stay frozen, and the original architecture/scope digest is checked.
    """
    torch, nn = final.torch, final.torch.nn
    require(not any(p.requires_grad for p in model.parameters()),
            "inference base must already have every parameter frozen")
    targets = [(name, module) for name, module in model.named_modules()
               if isinstance(module, nn.Linear) and name.rsplit(".", 1)[-1]
               in ("q_proj", "v_proj")]
    require(len(targets) == 2 * model.config.num_hidden_layers,
            "all original q/v adapter targets are required")
    expected = {name + suffix for name, _ in targets for suffix in (".lora_A", ".lora_B")}
    require(set(state["parameters"]) == expected, "saved adapter parameter set changed")
    for name, original in targets:
        a, b = state["parameters"][name + ".lora_A"], state["parameters"][name + ".lora_B"]
        require(tuple(a.shape) == (8, original.in_features)
                and tuple(b.shape) == (original.out_features, 8)
                and a.dtype == b.dtype == torch.float32,
                "saved rank8 FP32 adapter shape/dtype changed")
        adapter = model_impl.LowRankLinear.__new__(model_impl.LowRankLinear)
        nn.Module.__init__(adapter)
        adapter.base = original
        adapter.scaling = 2.0
        adapter.dropout = nn.Dropout(0.05)
        adapter.lora_A = nn.Parameter(a.to(original.weight.device).clone(), requires_grad=False)
        adapter.lora_B = nn.Parameter(b.to(original.weight.device).clone(), requires_grad=False)
        adapter.eval()
        parent, attribute = name.rsplit(".", 1)
        setattr(model.get_submodule(parent), attribute, adapter)
    parameters = {name: value for name, value in model.named_parameters() if name in expected}
    shapes = {name: list(value.shape) for name, value in parameters.items()}
    count = sum(value.numel() for value in parameters.values())
    scope = model_impl.record("trainable_adapter_scope",
        target_module_names=[name for name, _ in targets], trainable_shapes=shapes,
        trainable_parameter_count=count, base_weights_frozen=True,
        input_output_embeddings_frozen=True,
        implementation="base(x)+(alpha/rank)*B(A(dropout(x))); A/B fp32, residual cast to base dtype")
    architecture = dict(implementation="repository.LowRankLinear",
        target_module_names=sorted(name for name, _ in targets), trainable_shapes=shapes,
        trainable_parameter_count=count, rank=8, scaling=2.0, dropout=0.05,
        base_dtype="bfloat16", adapter_dtype="float32", loader_scope_id=scope["id"])
    require(architecture == state["adapter_binding"], "saved adapter architecture/scope changed")
    frozen = {name: value for name, value in model.named_parameters() if name not in expected}
    require(all(value.dtype == torch.bfloat16 for value in frozen.values())
            and final.parameter_digest(frozen) == state["frozen_base_digest"],
            "actual frozen base parameter bytes changed")
    buffers = dict(model.named_buffers())
    require(set(buffers) == set(state["buffers"]), "saved buffer coordinates changed")
    with torch.no_grad():
        for name, saved in state["buffers"].items():
            actual = buffers[name]
            require(actual.shape == saved.shape and actual.dtype == saved.dtype,
                    "saved buffer shape/dtype changed")
            actual.copy_(saved.to(actual.device))
    require(final.parameter_digest(parameters) == final.parameter_digest(state["parameters"])
            and final._tree_digest(buffers) == final._tree_digest(state["buffers"]),
            "actual installed parameters/buffers differ from saved point")
    model.requires_grad_(False)
    model.eval()
    if hasattr(model, "gradient_checkpointing_disable"):
        model.gradient_checkpointing_disable()
    model.config.use_cache = True
    return parameters, dict(adapter_scope=scope, architecture=architecture,
        saved_A_B_installed_directly=True, random_LoRA_initialization_calls=0,
        optimizer_objects_created=0, backward_calls=0,
        all_parameters_require_grad_false=not any(p.requires_grad for p in model.parameters()))


def validate_generation_context(context, tokenizer, RunConfig):
    from finqa_v73_inputs import restore_request_tool_order
    request = restore_request_tool_order(context["request"])
    config = RunConfig.model_validate(request["config"])
    require((config.temperature, config.top_p, config.top_k, config.max_new_tokens,
             config.context_limit, config.seed, config.local_tool_protocol,
             config.tier, config.role) ==
            (0.0, 1.0, 0, 2048, 24576, 20260928, "qwen2.5-native-tool-call-v1",
             "EVAL_NATIVE", "development"), "registered greedy context configuration changed")
    rendered = tokenizer.apply_chat_template(copy.deepcopy(request["messages"]),
        tools=copy.deepcopy(request["tools"]), tokenize=False, add_generation_prompt=True)
    ids = tokenizer(rendered, add_special_tokens=False, truncation=False, padding=False)["input_ids"]
    require(ids == list(context["prompt_input_ids"]),
            "request rendering differs from the actual saved prompt token IDs")
    require(ids and len(ids) + config.max_new_tokens <= config.context_limit,
            "exact full prompt exceeds the registered output reservation")
    return config


def teacher_forced_logps(model, prompt_ids, target_ids, torch, measurement):
    """One causal forward; keep only response predecessor logits, including EOS."""
    require(prompt_ids and target_ids and len(target_ids) <= 2048,
            "fixed parent prompt and nonempty original response up to2048 are required")
    require(len(prompt_ids) + len(target_ids) <= 24576, "fixed sequence exceeds original context")
    require(not model.training and not any(p.requires_grad for p in model.parameters()),
            "probability channel must remain inference-only")
    device = next(model.parameters()).device
    ids = torch.tensor([list(prompt_ids) + list(target_ids[:-1])], dtype=torch.long, device=device)
    if device.type == "cuda":
        from torch.nn.attention import SDPBackend, sdpa_kernel
        attention = sdpa_kernel(SDPBackend.FLASH_ATTENTION)
    else:
        attention = nullcontext()
    with torch.no_grad(), attention:
        output = model(input_ids=ids, attention_mask=torch.ones_like(ids), use_cache=False,
            logits_to_keep=len(target_ids), return_dict=True)
        require(tuple(output.logits.shape[:2]) == (1, len(target_ids)),
                "Qwen must return exactly the target predecessor positions")
        # Original raw logits, full vocabulary; never a filtered generation score.
        logps = measurement.target_logps_from_logits(output.logits[0], target_ids,
            position_chunk_size=LOG_SOFTMAX_CHUNK)
    del output, ids
    return logps


class Predictor:
    def __init__(self, checkpoint_ref, model_label, guard, bindings):
        require(model_label in ("P", "H", "L"), "only the three registered saved models")
        self.binding, self.final, model_impl, self.measurement = _modules()
        self.guard, self.model_label = guard, model_label
        self.checkpoint_ref, self.bindings = copy.deepcopy(checkpoint_ref), copy.deepcopy(bindings)
        self._hooks, self._counts, self.closed = [], Counter(), False
        guard.check("before_probe_checkpoint_CPU_read", boundary=True)
        state = read_checkpoint(checkpoint_ref, self.binding, self.final)
        require(self.final.parameter_digest(state["parameters"]) == bindings["model_identity"]["parameter_digest"],
                "saved state differs from the registered original inference point")
        guard.check("before_probe_inference_model_load", boundary=True)
        tokenizer = self.final.base.load_tokenizer(bindings["assets"])
        model, scope = model_impl.load_student(bindings["assets"]["base_binding"],
            20260928, trainable=False)
        require(scope is None, "inference base unexpectedly initialized adapters")
        parameters, load_evidence = install_saved_adapters(model, state, model_impl, self.final)
        del state
        gc.collect()
        identity = self.final.local_model_identity(model, tokenizer,
            model_id=bindings["model_identity"]["model_id"],
            point_id=bindings["model_identity"]["point_id"], parameter_tensors=parameters)
        require(identity.model_dump(mode="json") == bindings["model_identity"],
                "actual inference model/tokenizer/template identity differs")
        self.provider = self.final.LocalTorchProvider(model, tokenizer, identity,
            parameter_tensors=parameters)
        self.model, self.tokenizer = model, tokenizer
        self.load_evidence = dict(load_evidence, checkpoint=checkpoint_ref,
            model_identity=identity.model_dump(mode="json"), model_label=model_label,
            base_dtype="bfloat16", adapter_dtype="float32", attention_backend="FLASH_ATTENTION",
            teacher_forcing_log_softmax_position_chunk=LOG_SOFTMAX_CHUNK)
        self._install_counters()
        guard.check("after_probe_inference_model_load", boundary=True)

    def _install_counters(self):
        def counted(label):
            def hook(module, args, kwargs):
                self._counts[label + "_forward_calls"] += 1
                value = kwargs.get("input_ids") if label != "lm_head" else (args[0] if args else None)
                if value is None and args and label != "lm_head":
                    value = args[0]
                if value is not None:
                    amount = value.numel() if label != "lm_head" else value.numel() // value.shape[-1]
                    self._counts[label + "_input_positions"] += int(amount)
                if label == "model" and getattr(getattr(self.guard, "stop", None), "requested", False):
                    # Calling the existing guard preserves its exact explicit-stop type.
                    self.guard.check("explicit_stop_at_probe_forward", boundary=False)
            return hook
        for label, module in (("model", self.model), ("transformer", self.model.model),
                              ("lm_head", self.model.lm_head)):
            self._hooks.append(module.register_forward_pre_hook(counted(label), with_kwargs=True))

    def _delta(self, before):
        return {key: value - before.get(key, 0) for key, value in sorted(self._counts.items())}

    def generate(self, context):
        require(not self.closed, "predictor is closed")
        config = validate_generation_context(context, self.tokenizer, self.final.RunConfig)
        self.guard.check("before_single_probe_response", boundary=True)
        before, before_calls = dict(self._counts), self.provider.actual_model_calls
        from finqa_v73_inputs import restore_request_tool_order
        request = restore_request_tool_order(context["request"])
        turn = asyncio.run(self.provider.chat(copy.deepcopy(request["messages"]),
            copy.deepcopy(request["tools"]), config))
        value = turn.model_dump(mode="json")
        require(value["receipt"]["prompt_input_ids"] == list(context["prompt_input_ids"]),
                "actual generated prompt differs from frozen context")
        require(self.provider.actual_model_calls - before_calls == 1, "probe must make one model.generate call")
        return dict(turn=value, counters_delta=self._delta(before), model_label=self.model_label,
            actual_model_generate_calls=1, input_tokens=len(context["prompt_input_ids"]),
            generated_tokens=len(value["receipt"]["raw_generated_token_ids"]),
            tools_executed=0, next_assistant_turns=0, native_scoring_calls=0, external_API_calls=0)

    def measure(self, target):
        require(not self.closed, "predictor is closed")
        self.guard.check("before_fixed_parent_response_probability", boundary=True)
        before, versions = dict(self._counts), self.provider._storage_versions()
        logps = teacher_forced_logps(self.model, target["prompt_input_ids"],
            target["raw_generated_token_ids"], self.final.torch, self.measurement)
        require(self.provider._storage_versions() == versions, "probability measurement changed model bytes")
        grouping = target.get("grouping", target)
        grouped = self.measurement.summarize_token_logps(logps, grouping)
        return dict(model_label=self.model_label, target_id=target["target_id"],
            token_logps=logps, groups=grouped["groups"],
            probability_summary={k: v for k, v in grouped.items() if k not in ("groups", "token_logps")},
            counters_delta=self._delta(before),
            prompt_tokens=len(target["prompt_input_ids"]),
            fixed_response_tokens=len(target["raw_generated_token_ids"]),
            probability_sequences=1, newly_generated_responses=0,
            raw_logits_full_vocabulary=True, logits_to_keep=len(target["raw_generated_token_ids"]),
            log_softmax_dtype="float32", log_softmax_position_chunk=LOG_SOFTMAX_CHUNK,
            teacher_forced_causal_shift="input=prompt+target[:-1]; last len(target) logits predict target",
            tools_executed=0, native_scoring_calls=0, optimizer_updates=0, backward_calls=0,
            external_API_calls=0)

    def close(self):
        if self.closed:
            return
        for hook in self._hooks:
            hook.remove()
        self._hooks.clear()
        del self.provider, self.model, self.tokenizer
        gc.collect()
        self.final.torch.cuda.empty_cache()
        self.closed = True
        self.guard.check("after_probe_model_release", boundary=True)

    @property
    def counters(self):
        return dict(self._counts)
