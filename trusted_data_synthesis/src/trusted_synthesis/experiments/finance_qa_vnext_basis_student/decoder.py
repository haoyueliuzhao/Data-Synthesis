"""Bound local public-response decoder; no private task or scoring imports.

No model or tokenizer is loaded at import. Actual execution and CPU controls are
distinct, and the caller's load receipt is separate from generation operations.
"""

import copy
import time
from pathlib import Path

from .protocol import (
    BINDING_FIELDS,
    checked_record,
    path_within,
    record,
    require,
    sha,
    training_config,
    write_once,
)

ACTUAL = "actual_local_model"
CONTROL = "synthetic_cpu_control"


def policy():
    return record(
        "decoder_policy",
        do_sample=False,
        num_beams=1,
        repetition_penalty=1.0,
        max_new_tokens=2048,
        maximum_sequence_length=24576,
        max_responses=32,
        max_tools=32,
        requested_basis="neutral",
        truncation=False,
        padding=False,
        add_special_tokens=False,
        add_generation_prompt=True,
        use_cache=True,
        gradient_enabled=False,
        dropout_enabled=False,
        output="complete generated token IDs and exact decoded text; only final actual EOS removed",
        context_admission="full prompt tokens plus all 2048 reserved new tokens <=24576",
        context_rejection=(
            "persist attempted callback without calling model; terminate this session"
        ),
        JSON_or_length_handling=(
            "unaltered response passed to original runtime; no host continuation"
        ),
        eos_pad_bos_authority="actual bound base generation configuration and tokenizer assets",
        automatic_retry=False,
        dynamic_length_reduction=False,
        runtime_resource_zeroes_are_process_resource_counts=False,
    )


def bind_policy(tokenizer_binding, base_binding):
    generation = base_binding["generation_config"]
    eos = generation.get("eos_token_id", tokenizer_binding["eos_token_id"])
    eos = [eos] if type(eos) is int else eos
    require(
        isinstance(eos, list)
        and bool(eos)
        and len(set(eos)) == len(eos)
        and all(type(value) is int and value >= 0 for value in eos),
        "decoder.bound_EOS_ids",
    )
    pad = generation.get("pad_token_id", tokenizer_binding["pad_token_id"])
    bos = generation.get("bos_token_id", tokenizer_binding["bos_token_id"])
    require(
        type(pad) is int and pad >= 0 and (bos is None or type(bos) is int and bos >= 0),
        "decoder.bound_pad_bos_ids",
    )
    template = tokenizer_binding["chat_template"]
    require(
        isinstance(template, str) and sha(template) == tokenizer_binding["chat_template_sha256"],
        "decoder.bound_template_bytes",
    )
    require(
        tokenizer_binding["eos_token_id"] in eos
        and base_binding["config"]["max_position_embeddings"] >= 24576,
        "decoder.actual_asset_context_and_termination",
    )
    return record(
        "decoder_config",
        policy=policy(),
        base_binding_id=base_binding["id"],
        tokenizer_binding_id=tokenizer_binding["id"],
        eos_token_ids=eos,
        pad_token_id=pad,
        bos_token_id=bos,
        chat_template_sha256=sha(template),
        template_authority="exact tokenizer binding chat_template",
        new_limit_is_2048_not_inherited=True,
    )


def validate_model_identity(identity):
    checked_record(identity, "model_identity")
    required = {
        *BINDING_FIELDS,
        "pool",
        "arm",
        "seed",
        "checkpoint_id",
        "training_report_id",
        "final_adapter",
        "adapter_directory",
        "base_binding_id",
        "tokenizer_binding_id",
        "id",
        "schema_version",
    }
    require(set(identity) == required, "decoder.public_model_identity_closed_fields")
    require(
        identity["pool"] in {"A", "B"}
        and identity["arm"] in {"alpha0", "plus", "minus"}
        and identity["seed"] in {11, 29, 47},
        "decoder.registered_model_variant",
    )
    require(
        all(isinstance(identity[key], str) and identity[key] for key in BINDING_FIELDS),
        "decoder.five_frozen_bindings",
    )
    adapter = identity["final_adapter"]
    require(
        set(adapter) == {"path", "bytes", "sha256", "parameter_digest"}
        and adapter["parameter_digest"] == identity["checkpoint_id"]
        and isinstance(adapter["path"], str)
        and Path(adapter["path"]).name == adapter["path"]
        and isinstance(identity["adapter_directory"], str)
        and not Path(identity["adapter_directory"]).is_absolute()
        and ".." not in Path(identity["adapter_directory"]).parts,
        "decoder.final_adapter_parameter_identity",
    )
    return identity


class ContextRejected(RuntimeError):
    """Expected no-generation terminal, with its receipt persisted independently."""


class DecoderFailure(RuntimeError):
    """Implementation/model fault: retained evidence; never auto-retried."""


class BoundDecoder:
    def __init__(
        self,
        model,
        tokenizer,
        tokenizer_binding,
        model_identity,
        output,
        *,
        base_binding,
        configuration=None,
        execution_kind,
        load_receipt,
    ):
        validate_model_identity(model_identity)
        require(execution_kind in {ACTUAL, CONTROL}, "decoder.explicit_execution_kind")
        self.identity, self.model, self.tokenizer = copy.deepcopy(model_identity), model, tokenizer
        self.output, self.execution_kind = Path(output).absolute(), execution_kind
        require(
            not any(path.is_symlink() for path in (self.output, *self.output.parents)),
            "decoder.no_symlink_output",
        )
        self.configuration = bind_policy(tokenizer_binding, base_binding)
        require(
            configuration is None or configuration == self.configuration, "decoder.frozen_config"
        )
        require(
            model_identity["decoder_config_id"] == self.configuration["id"]
            and model_identity["base_binding_id"] == base_binding["id"]
            and model_identity["tokenizer_binding_id"] == tokenizer_binding["id"],
            "decoder.model_asset_config_join",
        )
        require(
            tokenizer.chat_template == tokenizer_binding["chat_template"]
            and all(
                getattr(tokenizer, key) == tokenizer_binding[key]
                for key in ("eos_token_id", "pad_token_id", "bos_token_id")
            ),
            "decoder.actual_loaded_tokenizer_binding",
        )
        checked_record(load_receipt, "model_load_receipt")
        require(
            load_receipt["model_identity_id"] == model_identity["id"]
            and load_receipt["execution_kind"] == execution_kind
            and load_receipt["restored_checkpoint_id"] == model_identity["checkpoint_id"],
            "decoder.actual_restore_receipt",
        )
        self.load_receipt = copy.deepcopy(load_receipt)
        if execution_kind == ACTUAL:
            import torch

            from ..finance_qa_vnext_pq_student.model import adapter_digest

            require(
                isinstance(model, torch.nn.Module)
                and all(parameter.device.type == "cuda" for parameter in model.parameters())
                and adapter_digest(model) == model_identity["checkpoint_id"],
                "decoder.actual_loaded_final_GPU_adapter",
            )
            require(
                all(
                    load_receipt[key] == 1
                    for key in (
                        "model_weight_loads",
                        "final_adapter_loads",
                        "tokenizer_loads",
                        "GPU_loads",
                    )
                ),
                "decoder.actual_worker_load_counts",
            )
        else:
            require(
                all(
                    load_receipt[key] == 0
                    for key in (
                        "model_weight_loads",
                        "final_adapter_loads",
                        "tokenizer_loads",
                        "GPU_loads",
                    )
                ),
                "decoder.synthetic_never_actual_loads",
            )
        model.requires_grad_(False)
        model.eval()
        self.receipts = []
        self.fatal_error = None
        self.counters = {
            key: 0
            for key in (
                "callback_attempts",
                "tokenization_calls",
                "model_generate_api_calls",
                "actual_model_generation_calls",
                "synthetic_model_generation_calls",
                "actual_GPU_generation_calls",
                "completed_generation_calls",
                "context_rejections",
                "generated_tokens",
                "public_content_tokens",
                "callback_failures",
            )
        }

    def snapshot(self):
        return {
            **self.counters,
            "execution_kind": self.execution_kind,
            "model_weight_loads": self.load_receipt["model_weight_loads"],
            "final_adapter_loads": self.load_receipt["final_adapter_loads"],
            "tokenizer_loads": self.load_receipt["tokenizer_loads"],
            "GPU_model_loads": self.load_receipt["GPU_loads"],
            "load_receipt_id": self.load_receipt["id"],
            "fatal_error": self.fatal_error,
            "GPU_count_unit": "instrumented model-load and generate API invocations, not kernels",
            "runtime_zero_resource_fields_scope": "runtime module only, not this model process",
            "actual_model_and_tokenizer_loads_from_worker_receipt": True,
        }

    def _generate(self, input_ids, attention_mask):
        options = {
            "do_sample": False,
            "num_beams": 1,
            "num_return_sequences": 1,
            "max_new_tokens": 2048,
            "repetition_penalty": 1.0,
            "eos_token_id": self.configuration["eos_token_ids"],
            "pad_token_id": self.configuration["pad_token_id"],
            "bos_token_id": self.configuration["bos_token_id"],
            "use_cache": True,
        }
        if self.execution_kind == CONTROL:
            return self.model.generate(
                input_ids=[input_ids], attention_mask=[attention_mask], **options
            )
        import torch
        from torch.nn.attention import SDPBackend, sdpa_kernel
        from transformers import GenerationConfig

        device = next(self.model.parameters()).device
        with torch.inference_mode(), sdpa_kernel(SDPBackend.FLASH_ATTENTION):
            result = self.model.generate(
                input_ids=torch.tensor([input_ids], dtype=torch.long, device=device),
                attention_mask=torch.tensor([attention_mask], dtype=torch.long, device=device),
                generation_config=GenerationConfig(**options),
                logits_to_keep=1,
            )
        return result.detach().cpu().tolist()

    def __call__(self, messages, context):
        require(self.fatal_error is None, "decoder.no_callbacks_after_model_fault")
        self.counters["callback_attempts"] += 1
        index = self.counters["callback_attempts"]
        folder = self.output / f"callback_{index:06d}"
        started = time.perf_counter()
        state = {
            "callback_index": index,
            "model_identity_id": self.identity["id"],
            "checkpoint_id": self.identity["checkpoint_id"],
            "surface_manifest_id": self.identity["surface_manifest_id"],
            "decoder_config_id": self.configuration["id"],
            "execution_kind": self.execution_kind,
            "context": copy.deepcopy(context),
            "model_generation_invoked": False,
            "model_generation_completed": False,
            "GPU_generation_invoked": False,
            "prompt_token_count": None,
            "generated_token_ids": [],
            "public_content_token_ids": [],
            "generated_token_count": 0,
            "raw_generated_text": None,
            "raw_response": None,
            "actual_terminating_EOS_removed": False,
            "prompt_truncated": False,
            "automatic_continuation": False,
            "host_JSON_repair": False,
        }
        caught = None
        try:
            require(
                set(context)
                == {
                    "identity",
                    "response_index",
                    "max_responses",
                    "max_tools",
                    "remaining_tool_calls",
                    "history_must_not_be_truncated",
                }
                and context["identity"]["parent_manifest_id"]
                == self.identity["surface_manifest_id"]
                and context["max_responses"] == context["max_tools"] == 32
                and context["history_must_not_be_truncated"] is True,
                "decoder.public_runtime_context",
            )
            require(
                isinstance(messages, list)
                and messages
                and messages[0]["role"] == "system"
                and messages[0]["content"].endswith("\nRequested guidance: neutral")
                and all(
                    set(row) == {"role", "content"} and isinstance(row["content"], str)
                    for row in messages
                ),
                "decoder.original_public_messages",
            )
            rendered = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            self.counters["tokenization_calls"] += 1
            encoded = self.tokenizer(
                rendered, add_special_tokens=False, truncation=False, padding=False
            )
            input_ids = encoded["input_ids"]
            mask = encoded.get("attention_mask", [1] * len(input_ids))
            require(
                isinstance(input_ids, list)
                and input_ids
                and all(type(token) is int and token >= 0 for token in input_ids)
                and len(mask) == len(input_ids)
                and all(value == 1 for value in mask),
                "decoder.complete_unpadded_prompt_tokens",
            )
            state["prompt_token_count"] = len(input_ids)
            write_once(
                folder / "request.json",
                record(
                    "decoder_request",
                    model_identity=self.identity,
                    context=context,
                    decoder_config_id=self.configuration["id"],
                    input_messages=messages,
                    rendered_prompt=rendered,
                    rendered_prompt_sha256=sha(rendered),
                    input_token_ids=input_ids,
                    attention_mask=mask,
                    full_public_history_preserved=True,
                    execution_kind=self.execution_kind,
                ),
            )
            if len(input_ids) + 2048 > 24576:
                self.counters["context_rejections"] += 1
                state["finish_reason"] = "context_rejected_before_model_generate"
                raise ContextRejected("decoder.full_context_plus_2048_exceeds_24576")
            require(not self.model.training, "decoder.dropout_disabled")
            state["model_generation_invoked"] = True
            self.counters["model_generate_api_calls"] += 1
            key = (
                "actual_model_generation_calls"
                if self.execution_kind == ACTUAL
                else "synthetic_model_generation_calls"
            )
            self.counters[key] += 1
            if self.execution_kind == ACTUAL:
                state["GPU_generation_invoked"] = True
                self.counters["actual_GPU_generation_calls"] += 1
            sequence = self._generate(input_ids, mask)
            require(
                isinstance(sequence, list)
                and len(sequence) == 1
                and sequence[0][: len(input_ids)] == input_ids,
                "decoder.model_returned_original_prompt_prefix",
            )
            generated = sequence[0][len(input_ids) :]
            require(
                len(generated) <= 2048
                and all(type(token) is int and token >= 0 for token in generated),
                "decoder.model_new_token_limit",
            )
            ended = bool(generated) and generated[-1] in self.configuration["eos_token_ids"]
            content_ids = generated[:-1] if ended else generated
            # A later detokenization failure must not erase an already completed
            # generation or pretend that its observed output tokens were zero.
            self.counters["completed_generation_calls"] += 1
            self.counters["generated_tokens"] += len(generated)
            self.counters["public_content_tokens"] += len(content_ids)
            state.update(
                model_generation_completed=True,
                generated_token_ids=generated,
                public_content_token_ids=content_ids,
                generated_token_count=len(generated),
                actual_terminating_EOS_removed=ended,
            )
            raw_text = self.tokenizer.decode(
                generated, skip_special_tokens=False, clean_up_tokenization_spaces=False
            )
            content = self.tokenizer.decode(
                content_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False
            )
            state.update(
                model_generation_completed=True,
                generated_token_ids=generated,
                public_content_token_ids=content_ids,
                generated_token_count=len(generated),
                raw_generated_text=raw_text,
                raw_response=content,
                raw_response_sha256=sha(content),
                actual_terminating_EOS_removed=ended,
                finish_reason="actual_EOS"
                if ended
                else "new_token_limit"
                if len(generated) == 2048
                else "model_stopped_without_EOS",
            )
        except ContextRejected as error:
            caught = error
        except Exception as error:
            self.counters["callback_failures"] += 1
            self.fatal_error = type(error).__name__ + ": " + str(error)
            state.update(finish_reason="decoder_fault", error=self.fatal_error)
            caught = DecoderFailure(self.fatal_error)
        state["elapsed_seconds"] = time.perf_counter() - started
        receipt = record("decoder_receipt", **state)
        self.receipts.append(receipt)
        try:
            write_once(folder / "receipt.json", receipt)
            if self.fatal_error:
                write_once(
                    folder / "failure.json",
                    record(
                        "decoder_failure",
                        receipt_id=receipt["id"],
                        error=self.fatal_error,
                        retry_performed=False,
                        next_task_must_not_start=True,
                    ),
                )
        except Exception as error:
            self.fatal_error = "decoder.receipt_write_failed:" + type(error).__name__
            raise DecoderFailure(self.fatal_error) from error
        if caught is not None:
            raise caught
        return {"raw_response": state["raw_response"], "receipt": receipt}


def load_decoder(root, output, identity, base_binding, tokenizer_binding, decoder_config):
    """Actual production-only asset load; never reads training or material reports.

    The parent scheduler verifies the training report before creating its closed
    public job. This process restores only that bound final adapter and public
    base/tokenizer assets, and independently verifies the restored parameters.
    """
    validate_model_identity(identity)
    root, output = Path(root).resolve(), Path(output).absolute()
    require(not output.exists(), "decoder.no_repeat_model_worker")
    config = training_config()
    require(
        config["id"] == identity["training_config_id"]
        and base_binding["id"] == identity["base_binding_id"]
        and tokenizer_binding["id"] == identity["tokenizer_binding_id"]
        and decoder_config == bind_policy(tokenizer_binding, base_binding)
        and decoder_config["id"] == identity["decoder_config_id"],
        "decoder.actual_frozen_training_and_decode_configuration",
    )
    adapter = identity["final_adapter"]
    path = path_within(root, Path(identity["adapter_directory"]) / adapter["path"])
    require(
        not any(part.is_symlink() for part in (path, *path.parents))
        and path.stat().st_size == adapter["bytes"]
        and sha(path) == adapter["sha256"],
        "decoder.actual_registered_sole_final_adapter_bytes",
    )
    counts = {
        "model_weight_loads": 0,
        "final_adapter_loads": 0,
        "tokenizer_loads": 0,
        "GPU_loads": 0,
    }
    attempts = {"model_load_attempts": 0, "tokenizer_load_attempts": 0}
    try:
        from ..finance_qa_vnext_pq_student.model import adapter_digest
        from ..qa_reasoning_share_training_preflight.tokenization import load_tokenizer
        from .train import load_registered_student

        attempts["model_load_attempts"] += 1
        model, _ = load_registered_student(
            base_binding,
            identity["seed"],
            config,
            trainable=False,
            adapter_path=path,
            adapter_record=adapter,
        )
        counts.update(model_weight_loads=1, final_adapter_loads=1, GPU_loads=1)
        attempts["tokenizer_load_attempts"] += 1
        tokenizer = load_tokenizer(tokenizer_binding)
        counts["tokenizer_loads"] = 1
        restored = adapter_digest(model)
        require(restored == identity["checkpoint_id"], "decoder.restored_final_parameter_digest")
        receipt = record(
            "model_load_receipt",
            model_identity_id=identity["id"],
            execution_kind=ACTUAL,
            restored_checkpoint_id=restored,
            **counts,
            **attempts,
            base_binding_id=base_binding["id"],
            tokenizer_binding_id=tokenizer_binding["id"],
            private_material_or_evaluation_bundle_opened=False,
            training_report_verified_by_parent_before_public_job=True,
        )
        return BoundDecoder(
            model,
            tokenizer,
            tokenizer_binding,
            identity,
            output,
            base_binding=base_binding,
            configuration=decoder_config,
            execution_kind=ACTUAL,
            load_receipt=receipt,
        )
    except Exception as error:
        write_once(
            output / "load_failure.json",
            record(
                "model_load_failure",
                model_identity_id=identity["id"],
                execution_kind=ACTUAL,
                completed_load_counts=counts,
                attempted_load_counts=attempts,
                error_type=type(error).__name__,
                error=str(error),
                actual_complete=False,
                automatic_retry=False,
                partial_model_load_resource_usage_may_be_unknown=True,
            ),
        )
        raise
