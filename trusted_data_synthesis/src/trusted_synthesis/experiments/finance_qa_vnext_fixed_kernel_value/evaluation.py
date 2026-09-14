"""Protected original 900-task evaluation with explicit new-study identities.

The physical decoder and raw-session verification are deliberately preserved
from the latest baseline, but all model/report/receipt bindings use this study's
new schema. No legacy global is patched and no new report masquerades as old.
"""

import copy
import json
import os
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path

import numpy as np

from ..finance_qa_vnext_basis_scale_preparation import design as original_design
from ..finance_qa_vnext_basis_student.protocol import path_within
from ..finance_qa_vnext_eval_readiness import runtime
from ..finance_qa_vnext_eval_surface.overlay import PublicOverlay
from ..finance_qa_vnext_eval_surface.protocol import OUTPUT as SURFACE_DIRECTORY
from . import parallel_lineage
from .protocol import checked_record, read_json, record, require, sha, write_once
from .trajectory_training import training_config

SURFACE_MANIFEST_ID = "manifest:f29dac61b36396baffd60916bf3b2bdca461a849f0e11bb2d519d54127d2c856"
BINDING_FIELDS = (
    "study_freeze_id",
    "surface_manifest_id",
    "kernel_id",
    "training_configuration_id",
    "decoder_config_id",
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
        unchanged_latest_baseline_2048_limit=True,
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
    require(
        identity["training_configuration_id"]
        == parallel_lineage.expected_training_config(
            identity["pool"], identity["arm"], identity["seed"]
        )["id"],
        "decoder.exact_registered_per_run_training_configuration",
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
    config = parallel_lineage.expected_training_config(
        identity["pool"], identity["arm"], identity["seed"]
    )
    require(
        config["id"] == identity["training_configuration_id"]
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
        from .trajectory_training import load_registered_student

        attempts["model_load_attempts"] += 1
        model, _ = load_registered_student(
            base_binding,
            identity["seed"],
            training_config(),
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


QUOTAS = {
    "dev": {"dual_sufficient": 60, "composition_required": 60, "other_financial": 60},
    "confirm": {"dual_sufficient": 240, "composition_required": 240, "other_financial": 240},
}


def _binding(identity):
    return {
        key: identity[key]
        for key in (*BINDING_FIELDS, "pool", "arm", "seed", "checkpoint_id", "training_report_id")
    }


def _output(root, value, *, absent):
    root = Path(root).resolve()
    value = Path(value)
    relative = value.relative_to(root) if value.is_absolute() else value
    output = path_within(root, relative)
    require(
        output != root and not any(part.is_symlink() for part in (output, *output.parents)),
        "evaluation.dedicated_non_symlink_output",
    )
    require(not absent or not output.exists(), "evaluation.no_reexecution_or_overwrite")
    return output


def seal_output(output, phase, report):
    output = Path(output)
    require(not (output / "manifest.json").exists(), "evaluation.one_manifest")
    files = []
    for path in sorted(output.rglob("*")):
        require(not path.is_symlink(), "evaluation.no_symlink_members")
        if path.is_file():
            files.append(
                {
                    "path": str(path.relative_to(output)),
                    "bytes": path.stat().st_size,
                    "sha256": sha(path),
                }
            )
    manifest = record(
        "evaluation_manifest",
        phase=phase,
        report_id=report["id"],
        members=files,
        self_excluding=True,
    )
    write_once(output / "manifest.json", manifest)
    return manifest


def verify_output(output, expected_manifest_id=None):
    require(
        not any(part.is_symlink() for part in (Path(output), *Path(output).parents)),
        "evaluation.non_symlink_sealed_output",
    )
    output = Path(output).resolve()
    manifest = read_json(output / "manifest.json")
    checked_record(manifest, "evaluation_manifest")
    require(
        expected_manifest_id is None or expected_manifest_id == manifest["id"],
        "evaluation.manifest_identity_pin",
    )
    members = {row["path"]: row for row in manifest["members"]}
    actual = {
        str(path.relative_to(output))
        for path in output.rglob("*")
        if path.is_file() and path != output / "manifest.json"
    }
    require(
        manifest["self_excluding"] is True
        and len(members) == len(manifest["members"])
        and set(members) == actual,
        "evaluation.complete_manifest_members",
    )
    for name, row in members.items():
        path = path_within(output, name)
        require(
            not any(part.is_symlink() for part in (path, *path.parents))
            and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            "evaluation.actual_saved_member_bytes",
        )
    report = read_json(output / "report.json")
    require(report["id"] == manifest["report_id"], "evaluation.sealed_report_identity")
    return manifest


def generate(
    root,
    output,
    *,
    surface_directory,
    surface_manifest_id,
    split,
    model_identity,
    decoder,
    source_root=None,
):
    """One complete original split, no private references, no assessment feedback."""
    validate_model_identity(model_identity)
    require(
        isinstance(decoder, BoundDecoder) and decoder.identity == model_identity,
        "evaluation.bound_decoder_required",
    )
    require(
        split in QUOTAS and (split != "dev" or model_identity["pool"] == "A"),
        "evaluation.registered_split_and_no_B_dev",
    )
    require(
        surface_manifest_id == model_identity["surface_manifest_id"],
        "evaluation.frozen_final_common_surface",
    )
    root = Path(root).resolve()
    output = _output(root, output, absent=True)
    require(decoder.output == output / "decoder", "evaluation.decoder_receipts_in_same_manifest")
    source_root = Path(source_root if source_root is not None else root).resolve()
    require(
        surface_manifest_id == SURFACE_MANIFEST_ID and str(surface_directory) == SURFACE_DIRECTORY,
        "evaluation.original_protected_900_surface_only",
    )
    public = PublicOverlay(source_root, surface_directory, surface_manifest_id)
    tasks = [row for row in public.catalog["tasks"] if row["split"] == split]
    require(
        dict(Counter(row["family"] for row in tasks)) == QUOTAS[split]
        and len({row["task_id"] for row in tasks}) == len(tasks),
        "evaluation.full_fixed_split_denominator",
    )
    write_once(output / "model_identity.json", model_identity)
    write_once(output / "decoder_config.json", decoder.configuration)
    write_once(output / "model_load_receipt.json", decoder.load_receipt)
    write_once(
        output / "registration.json",
        record(
            "generation_registration",
            **_binding(model_identity),
            split=split,
            surface_directory=str(surface_directory),
            source_root=str(source_root),
            surface_manifest_id_authority=surface_manifest_id,
            task_ids=[row["task_id"] for row in tasks],
            quotas=QUOTAS[split],
            public_catalog_id=public.catalog["id"],
            requested_basis="neutral",
            process_id=os.getpid(),
            private_task_bundles_opened=0,
        ),
    )
    results, failure = [], None
    for row in tasks:
        task_id = row["task_id"]
        try:
            envelope = public.public_envelope(task_id)
            visible = json.loads(envelope["messages"][0]["content"])
            descriptors = visible["source_document"]
            descriptors = [descriptors] if isinstance(descriptors, dict) else descriptors
            sources = runtime.SnapshotSources(source_root, descriptors)
            before = decoder.snapshot()
            first_receipt = len(decoder.receipts)
            session = runtime.generate(
                envelope["messages"],
                envelope["identity"],
                sources,
                provider=decoder,
                requested_basis="neutral",
                max_responses=32,
                max_tools=32,
            )
            receipts = decoder.receipts[first_receipt:]
            after = decoder.snapshot()
            require(
                session["provider_calls"]
                == len(receipts)
                == after["callback_attempts"] - before["callback_attempts"],
                "evaluation.all_attempted_callbacks_including_context_rejections",
            )
            path = Path("sessions") / task_id
            write_once(output / path / "runtime_session.json", session)
            result = record(
                "public_generation_result",
                **_binding(model_identity),
                task_id=task_id,
                split=split,
                group=row["family"],
                source_cluster=visible["period_contract"]["source_cluster"],
                surface_version_id=envelope["identity"]["surface_version_id"],
                public_messages_sha256=envelope["identity"]["public_messages_sha256"],
                runtime_session_id=session["id"],
                runtime_session_path=str(path / "runtime_session.json"),
                requested_basis="neutral",
                terminal=session["terminal"],
                context_rejected=after["context_rejections"] > before["context_rejections"],
                decoder_receipts=[
                    {
                        "id": item["id"],
                        "callback_index": item["callback_index"],
                        "path": f"decoder/callback_{item['callback_index']:06d}/receipt.json",
                    }
                    for item in receipts
                ],
                callback_attempts=session["provider_calls"],
                resource_delta={key: after[key] - before[key] for key in decoder.counters},
                runtime_resource_fields_are_runtime_scope_only=True,
                model_identity_id=model_identity["id"],
                execution_kind=decoder.execution_kind,
                private_task_bundles_opened=0,
                assessment_returned_online=False,
                actual_generation_fault=decoder.fatal_error,
            )
            write_once(output / path / "result.json", result)
            results.append(
                {
                    "task_id": task_id,
                    "result_id": result["id"],
                    "result_path": str(path / "result.json"),
                    "terminal": session["terminal"],
                }
            )
            if decoder.fatal_error:
                failure = record(
                    "generation_failure",
                    task_id=task_id,
                    error=decoder.fatal_error,
                    remaining_tasks_not_started=True,
                    retry_performed=False,
                )
                break
        except Exception as error:
            failure = record(
                "generation_failure",
                task_id=task_id,
                error_type=type(error).__name__,
                error=str(error),
                remaining_tasks_not_started=True,
                retry_performed=False,
            )
            break
    if failure:
        write_once(output / "failure.json", failure)
    complete = failure is None and len(results) == len(tasks)
    actual = complete and decoder.execution_kind == ACTUAL
    report = record(
        "generation_report",
        **_binding(model_identity),
        model_identity_id=model_identity["id"],
        split=split,
        status="COMPLETE_FIXED_GENERATION"
        if actual
        else "SYNTHETIC_GENERATION_CONTROL"
        if complete
        else "INCOMPLETE_GENERATION",
        actual_complete=actual,
        complete_registered_denominator=complete,
        requested_task_count=len(tasks),
        completed_task_count=len(results),
        results=results,
        terminal_counts=dict(Counter(row["terminal"] for row in results)),
        execution_kind=decoder.execution_kind,
        resource_usage=decoder.snapshot(),
        failure_id=failure["id"] if failure else None,
        private_task_bundles_opened=0,
        assessment_calls=0,
        training_eligible=False,
        model_weights_updated=False,
        requested_basis="neutral",
        no_private_fixture_constructed=True,
    )
    write_once(output / "report.json", report)
    seal_output(output, "public_generation", report)
    return report


def verify_generation_records(generation, report, identity):
    """Public-only receipt/accounting joins before opening private task data."""
    configuration = read_json(generation / "decoder_config.json")
    checked_record(configuration, "decoder_config")
    require(
        configuration["id"] == identity["decoder_config_id"], "evaluation.decoder_config_identity"
    )
    load = read_json(generation / "model_load_receipt.json")
    checked_record(load, "model_load_receipt")
    require(
        load["model_identity_id"] == identity["id"]
        and load["execution_kind"] == ACTUAL
        and load["restored_checkpoint_id"] == identity["checkpoint_id"]
        and all(
            load[key] == 1
            for key in ("model_weight_loads", "final_adapter_loads", "tokenizer_loads", "GPU_loads")
        ),
        "evaluation.actual_final_model_and_tokenizer_loads",
    )
    aggregate, seen = Counter(), set()
    for item in report["results"]:
        result = read_json(path_within(generation, item["result_path"]))
        checked_record(result, "public_generation_result")
        require(
            result["id"] == item["result_id"]
            and result["model_identity_id"] == identity["id"]
            and result["execution_kind"] == ACTUAL
            and result["actual_generation_fault"] is None
            and all(result[key] == value for key, value in _binding(identity).items()),
            "evaluation.actual_public_model_result",
        )
        session = read_json(path_within(generation, result["runtime_session_path"]))
        require(
            session["id"] == result["runtime_session_id"]
            and session["identity"]["task_id"] == result["task_id"] == item["task_id"]
            and session["origin"] == "live_evaluation_callback"
            and session["requested_basis"] == result["requested_basis"] == "neutral"
            and session["max_responses"] == session["max_tools"] == 32,
            "evaluation.live_neutral_original_runtime_session",
        )
        require(
            len(result["decoder_receipts"])
            == result["callback_attempts"]
            == session["provider_calls"],
            "evaluation.every_callback_has_one_saved_receipt",
        )
        turns = {turn["response_index"]: turn for turn in session["turns"]}
        for response_index, reference in enumerate(result["decoder_receipts"]):
            receipt = read_json(path_within(generation, reference["path"]))
            checked_record(receipt, "decoder_receipt")
            index = receipt["callback_index"]
            require(
                index not in seen
                and reference["id"] == receipt["id"]
                and reference["path"] == f"decoder/callback_{index:06d}/receipt.json"
                and receipt["model_identity_id"] == identity["id"]
                and receipt["checkpoint_id"] == identity["checkpoint_id"]
                and receipt["surface_manifest_id"] == identity["surface_manifest_id"]
                and receipt["decoder_config_id"] == configuration["id"]
                and receipt["execution_kind"] == ACTUAL
                and receipt["context"]["identity"] == session["identity"]
                and receipt["context"]["response_index"] == response_index,
                "evaluation.one_bound_actual_decoder_receipt",
            )
            seen.add(index)
            aggregate["callback_attempts"] += 1
            aggregate["tokenization_calls"] += 1
            request = read_json(generation / f"decoder/callback_{index:06d}/request.json")
            checked_record(request, "decoder_request")
            require(
                request["model_identity"] == identity
                and request["context"] == receipt["context"]
                and len(request["input_token_ids"]) == receipt["prompt_token_count"]
                and sha(request["rendered_prompt"]) == request["rendered_prompt_sha256"],
                "evaluation.actual_public_prompt_receipt_join",
            )
            if receipt["finish_reason"] == "context_rejected_before_model_generate":
                require(
                    not receipt["model_generation_invoked"]
                    and not receipt["GPU_generation_invoked"]
                    and not receipt["model_generation_completed"]
                    and receipt["generated_token_ids"] == []
                    and receipt["prompt_token_count"] + 2048 > 24576
                    and response_index == len(turns) == len(result["decoder_receipts"]) - 1
                    and session["terminal"] == "provider_error",
                    "evaluation.context_rejection_has_no_model_response",
                )
                aggregate["context_rejections"] += 1
                continue
            require(
                receipt["finish_reason"]
                in {"actual_EOS", "new_token_limit", "model_stopped_without_EOS"}
                and receipt["model_generation_invoked"] is True
                and receipt["model_generation_completed"] is True
                and receipt["GPU_generation_invoked"] is True
                and receipt["prompt_token_count"] + 2048 <= 24576
                and response_index in turns,
                "evaluation.actual_bounded_model_generation",
            )
            turn = turns[response_index]
            require(
                turn["provider_receipt"] == receipt
                and turn["raw_response"] == receipt["raw_response"]
                and turn["raw_response_sha256"] == receipt["raw_response_sha256"]
                and request["input_messages"] == turn["input_messages"],
                "evaluation.complete_raw_output_and_original_history",
            )
            generated, content = receipt["generated_token_ids"], receipt["public_content_token_ids"]
            ended = bool(generated) and generated[-1] in configuration["eos_token_ids"]
            require(
                receipt["generated_token_count"] == len(generated) <= 2048
                and receipt["actual_terminating_EOS_removed"] == ended
                and content == (generated[:-1] if ended else generated),
                "evaluation.only_actual_last_EOS_removed",
            )
            for key in (
                "model_generate_api_calls",
                "actual_model_generation_calls",
                "actual_GPU_generation_calls",
                "completed_generation_calls",
            ):
                aggregate[key] += 1
            aggregate["generated_tokens"] += len(generated)
            aggregate["public_content_tokens"] += len(content)
    usage = report["resource_usage"]
    for key in (
        "callback_attempts",
        "tokenization_calls",
        "model_generate_api_calls",
        "actual_model_generation_calls",
        "actual_GPU_generation_calls",
        "completed_generation_calls",
        "context_rejections",
        "generated_tokens",
        "public_content_tokens",
    ):
        require(
            usage[key] == aggregate[key], "evaluation.actual_worker_resource_reconciliation:" + key
        )
    require(
        usage["load_receipt_id"] == load["id"]
        and usage["model_weight_loads"] == 1
        and usage["final_adapter_loads"] == 1
        and usage["tokenizer_loads"] == 1
        and usage["GPU_model_loads"] == 1
        and usage["callback_failures"] == 0
        and usage["synthetic_model_generation_calls"] == 0
        and usage["fatal_error"] is None,
        "evaluation.no_runtime_zeroes_or_mock_counts_as_actual_worker",
    )
    return dict(aggregate)


def score(root, generation_directory, output, *, expected_generation_manifest_id):
    """Separate offline stage; no model/decoder callback occurs at this boundary."""
    # Deliberately local: the public-generation path must never construct this capability.
    from ..finance_qa_vnext_eval_readiness.assessment import assess_session
    from ..finance_qa_vnext_eval_surface.overlay import OfflineOverlay

    root = Path(root).resolve()
    generation = _output(root, generation_directory, absent=False)
    manifest = verify_output(generation, expected_generation_manifest_id)
    require(manifest["phase"] == "public_generation", "evaluation.original_generation_phase")
    before = read_json(generation / "report.json")
    checked_record(before, "generation_report")
    require(
        before["status"] == "COMPLETE_FIXED_GENERATION"
        and before["actual_complete"] is True
        and before["execution_kind"] == ACTUAL
        and before["failure_id"] is None,
        "evaluation.only_complete_actual_generation_scored",
    )
    identity = read_json(generation / "model_identity.json")
    validate_model_identity(identity)
    require(
        before["model_identity_id"] == identity["id"]
        and all(before[key] == value for key, value in _binding(identity).items()),
        "evaluation.exact_final_checkpoint_generation_identity",
    )
    registration = read_json(generation / "registration.json")
    checked_record(registration, "generation_registration")
    require(
        registration["process_id"] != os.getpid(), "evaluation.offline_distinct_from_model_process"
    )
    verify_generation_records(generation, before, identity)
    split = before["split"]
    require(
        split in QUOTAS
        and before["requested_task_count"]
        == before["completed_task_count"]
        == len(before["results"])
        == sum(QUOTAS[split].values()),
        "evaluation.complete_original_scoring_denominator",
    )
    offline = OfflineOverlay(
        Path(registration["source_root"]).resolve(),
        registration["surface_directory"],
        identity["surface_manifest_id"],
    )
    expected = [row["task_id"] for row in offline.public.catalog["tasks"] if row["split"] == split]
    require(
        expected == registration["task_ids"] == [row["task_id"] for row in before["results"]],
        "evaluation.original_complete_task_order",
    )
    output = _output(root, output, absent=True)
    outcomes = []
    for item in before["results"]:
        result = read_json(path_within(generation, item["result_path"]))
        checked_record(result, "public_generation_result")
        require(
            result["id"] == item["result_id"] and result["model_identity_id"] == identity["id"],
            "evaluation.saved_public_result_join",
        )
        session = read_json(path_within(generation, result["runtime_session_path"]))
        require(session["id"] == result["runtime_session_id"], "evaluation.actual_saved_session")
        task_id = item["task_id"]
        # This is the first private bundle construction, after generation was closed.
        fixture = offline.fixture(task_id)
        require(
            session["identity"] == fixture["identity"]
            and result["group"] == fixture["identity"]["family"]
            and result["surface_version_id"] == fixture["identity"]["surface_version_id"]
            and result["public_messages_sha256"] == fixture["identity"]["public_messages_sha256"]
            and result["source_cluster"]
            == fixture["bundle"]["public"]["period_contract"]["source_cluster"],
            "evaluation.same_final_public_surface",
        )
        assessment = assess_session(
            session, fixture["bundle"], fixture["native_bindings"], fixture["sources"]
        )
        path = Path("assessments") / (task_id + ".json")
        write_once(output / path, assessment)
        require(
            assessment["financial_valid"] is assessment["complete_trajectory_qualified"],
            "evaluation.primary_complete_financial_qualification",
        )
        outcomes.append(
            {
                "task_id": task_id,
                "group": result["group"],
                "source_cluster": result["source_cluster"],
                "surface_version_id": result["surface_version_id"],
                "public_messages_sha256": result["public_messages_sha256"],
                "financial_valid": assessment["financial_valid"],
                "complete_trajectory_qualified": assessment["complete_trajectory_qualified"],
                "quantity_status": assessment["quantity_status"],
                "support_status": assessment["support_status"],
                "actual_method": assessment["actual_method"],
                "full_mapping_status": assessment["full_mapping_status"],
                "reason": assessment["reason"],
                "assessment_id": assessment["id"],
                "assessment_path": str(path),
                "generation_result_id": result["id"],
                "runtime_terminal": session["terminal"],
                "context_rejected": result["context_rejected"],
            }
        )
    require(
        dict(Counter(row["group"] for row in outcomes)) == QUOTAS[split],
        "evaluation.all_outcomes_keep_original_groups",
    )
    groups = {
        group: {
            "qualified": sum(row["financial_valid"] for row in outcomes if row["group"] == group),
            "total": count,
        }
        for group, count in QUOTAS[split].items()
    }
    report = record(
        "evaluation_report",
        **_binding(identity),
        status="COMPLETE_FIXED_EVALUATION",
        actual_complete=True,
        split=split,
        model_identity_id=identity["id"],
        generation_manifest_id=manifest["id"],
        generation_report_id=before["id"],
        outcomes=outcomes,
        task_count=len(outcomes),
        group_counts=groups,
        primary_utility=sum(row["qualified"] / row["total"] for row in groups.values()) / 3,
        primary_metric="three equally weighted group means of complete trajectory qualification",
        unknown_missing_Final_and_errors_in_denominator=True,
        fine_mapping_required_for_primary=False,
        actual_model_resource_usage=before["resource_usage"],
        scoring_model_loads=0,
        scoring_GPU_calls=0,
        scoring_provider_calls=0,
        scoring_private_bundles_opened=len(outcomes),
        scoring_process_id=os.getpid(),
        generation_process_id=registration["process_id"],
        private_loaded_only_after_sealed_actual_generation=True,
        training_eligible=False,
    )
    write_once(output / "report.json", report)
    seal_output(output, "offline_score", report)
    return report


# The following statistics retain the baseline task/cluster estimand, while
# validating the new fixed-kernel report schema rather than legacy reports.
GROUPS = ("dual_sufficient", "composition_required", "other_financial")
BINDING_FIELDS = (
    "study_freeze_id",
    "surface_manifest_id",
    "kernel_id",
    "training_configuration_id",
    "decoder_config_id",
)
TASK_FIELDS = ("task_id", "group", "source_cluster", "surface_version_id", "public_messages_sha256")
BOOTSTRAP_REPLICATES = 10000
BOOTSTRAP_SEED = 20260912
MAX_BOOTSTRAP_ATTEMPTS = 1000000


def analysis_policy():
    return record(
        "analysis_policy",
        selection_pool="A",
        arms=list(original_design.ARMS),
        paired_seeds=list(original_design.SEEDS),
        dev_tasks=180,
        dev_group_tasks=60,
        confirm_tasks=720,
        confirm_group_tasks=240,
        primary_utility="financial_valid: full-trajectory financial qualification",
        unknown_errors_no_Final_retained_in_fixed_denominators=True,
        fine_mapping_pending_does_not_negate_financial_valid=True,
        utility_aggregation="task mean within each group, then equal mean of three groups",
        candidate_requires_strictly_positive_seed_mean_paired_gain=True,
        tie_priority=list(original_design.ARMS),
        every_seed_positive_required=False,
        NLL_or_method_yield_used_for_selection=False,
        baseline_stops_B_training_and_confirmation=True,
        runner_up_confirmation_allowed=False,
        primary_confirmation_pool="B",
        auxiliary_confirmation_pool="A",
        B_development_sessions=0,
        confirmation_sessions=8640,
        bootstrap_replicates=BOOTSTRAP_REPLICATES,
        bootstrap_seed=BOOTSTRAP_SEED,
        bootstrap_rng="numpy.random.Generator(PCG64)",
        bootstrap_draw="multinomial(K, uniform probability over sorted unique CIK clusters)",
        bootstrap_shared_weights="all arms, seeds, pools and task groups in the same draw",
        bootstrap_estimand="cluster multiplicity times each task; not equal company means",
        bootstrap_empty_group="reject whole draw and redraw; never drop or renormalize a group",
        bootstrap_max_attempts=MAX_BOOTSTRAP_ATTEMPTS,
        bootstrap_attempt_limit_failure="STOP without a partial interval",
        confidence_level=0.95,
        interval="paired percentile, 0.025 and 0.975 quantiles, linear interpolation",
        interval_endpoint_numeric_rounding_decimal_places=15,
        meaningful_benefit=0.05,
        positive_confirmation="B interval lower bound strictly greater than zero",
        zero_inclusive_interval="not confirmed",
        upper_bound_at_least_5pp="cannot exclude a benefit of at least five percentage points",
        source_inference_conditional_on_fixed_trained_checkpoints=True,
        intervals_estimate_all_training_randomness=False,
        pools_and_seeds_multiply_independent_task_count=False,
    )


def _analysis_fraction(value):
    value = Fraction(value)
    return {"exact": str(value), "value": float(value)}


def _analysis_binding(binding):
    require(isinstance(binding, dict) and set(binding) == set(BINDING_FIELDS), "analysis.binding")
    require(
        all(isinstance(binding[key], str) and binding[key] for key in BINDING_FIELDS),
        "analysis.nonempty_binding_identity",
    )
    parallel_lineage.validate_binding(binding, binding)
    return dict(binding)


def _analysis_check_binding(value, binding):
    parallel_lineage.validate_binding(value, binding)


def _analysis_tasks(tasks, split, groups):
    require(tuple(groups) == GROUPS, "analysis.original_three_groups")
    count = 60 if split == "dev" else 240
    require(isinstance(tasks, list) and len(tasks) == 3 * count, "analysis.fixed_task_denominator")
    rows = []
    for task in tasks:
        require(
            isinstance(task, dict) and all(key in task for key in TASK_FIELDS),
            "analysis.task_fields",
        )
        require(
            all(isinstance(task[key], str) and task[key] for key in TASK_FIELDS),
            "analysis.task_identity_strings",
        )
        cluster = task["source_cluster"]
        require(
            cluster.startswith("cik:") and len(cluster) == 14 and cluster[4:].isdigit(),
            "analysis.CIK_cluster_not_report_or_row",
        )
        rows.append({key: task[key] for key in TASK_FIELDS})
    require(len({row["task_id"] for row in rows}) == len(rows), "analysis.unique_task_ids")
    require(
        Counter(row["group"] for row in rows) == Counter(dict.fromkeys(groups, count)),
        "analysis.complete_equal_group_quotas",
    )
    return sorted(rows, key=lambda row: row["task_id"])


def _analysis_task_manifest(tasks, split):
    return record("analysis_task_manifest", split=split, tasks=tasks)


def _analysis_training(reports, keys, binding):
    require(
        isinstance(reports, list) and len(reports) == len(keys), "analysis.complete_training_runs"
    )
    found = {}
    for report in reports:
        checked_record(report, "training_report")
        _analysis_check_binding(
            report, {key: value for key, value in binding.items() if key != "decoder_config_id"}
        )
        require(
            report.get("status") == "COMPLETE_FINAL_CHECKPOINT"
            and report.get("actual_complete") is True,
            "analysis.actual_final_checkpoint_required",
        )
        key = (report.get("pool"), report.get("arm"), report.get("seed"))
        require(key in keys and key not in found, "analysis.fixed_unique_training_run")
        require(type(key[2]) is int, "analysis.integer_registered_seed")
        require(
            isinstance(report.get("checkpoint_id"), str) and bool(report["checkpoint_id"]),
            "analysis.checkpoint_identity",
        )
        adapter = report.get("final_adapter")
        require(
            isinstance(adapter, dict)
            and adapter.get("parameter_digest") == report["checkpoint_id"]
            and isinstance(adapter.get("path"), str)
            and bool(adapter["path"])
            and isinstance(adapter.get("sha256"), str)
            and len(adapter["sha256"]) == 64
            and type(adapter.get("bytes")) is int
            and adapter["bytes"] > 0
            and report.get("final_adapter_restored_identity_verified") is True,
            "analysis.saved_and_restored_final_adapter_identity",
        )
        found[key] = report
    require(set(found) == set(keys), "analysis.no_missing_training_run")
    return found


def _analysis_scores(reports, training, keys, tasks, split, binding):
    require(
        isinstance(reports, list) and len(reports) == len(keys), "analysis.complete_score_reports"
    )
    expected = {row["task_id"]: row for row in tasks}
    found = {}
    for report in reports:
        checked_record(report, "evaluation_report")
        _analysis_check_binding(report, binding)
        key = (report.get("pool"), report.get("arm"), report.get("seed"))
        require(key in keys and key not in found, "analysis.fixed_unique_evaluation_run")
        require(type(key[2]) is int, "analysis.integer_registered_seed")
        require(
            report.get("actual_complete") is True
            and report.get("status") == "COMPLETE_FIXED_EVALUATION"
            and report.get("split") == split,
            "analysis.actual_complete_fixed_split",
        )
        require(
            report.get("training_report_id") == training[key]["id"]
            and report.get("checkpoint_id") == training[key]["checkpoint_id"],
            "analysis.actual_checkpoint_score_join",
        )
        outcomes = report.get("outcomes")
        require(
            isinstance(outcomes, list) and len(outcomes) == len(tasks),
            "analysis.full_outcome_denominator",
        )
        seen, ordered = set(), {}
        for outcome in outcomes:
            task_id = outcome.get("task_id")
            require(task_id in expected and task_id not in seen, "analysis.unique_original_outcome")
            require(
                all(outcome.get(field) == expected[task_id][field] for field in TASK_FIELDS),
                "analysis.outcome_original_source_surface_group",
            )
            require(
                type(outcome.get("financial_valid")) is bool, "analysis.explicit_financial_boolean"
            )
            seen.add(task_id)
            ordered[task_id] = outcome
        require(seen == set(expected), "analysis.no_dropped_failures_or_unknowns")
        found[key] = (report, [ordered[row["task_id"]] for row in tasks])
    require(set(found) == set(keys), "analysis.complete_model_score_cross_product")
    return found


def _analysis_utility(outcomes, groups=GROUPS):
    means, counts, successes = {}, {}, {}
    for group in groups:
        rows = [row for row in outcomes if row["group"] == group]
        counts[group] = len(rows)
        successes[group] = sum(row["financial_valid"] for row in rows)
        means[group] = Fraction(successes[group], counts[group])
    utility = sum(means.values(), Fraction()) / 3
    return utility, {
        "utility": _analysis_fraction(utility),
        "group_utilities": {group: _analysis_fraction(means[group]) for group in groups},
        "group_denominators": counts,
        "group_financial_valid": successes,
        "fixed_task_denominator": len(outcomes),
    }


def select_actual_direction(training_reports, dev_reports, *, binding, dev_tasks, groups=GROUPS):
    binding = _analysis_binding(binding)
    tasks = _analysis_tasks(dev_tasks, "dev", groups)
    keys = [("A", arm, seed) for arm in original_design.ARMS for seed in original_design.SEEDS]
    training = _analysis_training(training_reports, keys, binding)
    scores = _analysis_scores(dev_reports, training, keys, tasks, "dev", binding)
    utilities = {arm: {} for arm in original_design.ARMS}
    summaries = []
    for key in keys:
        _, arm, seed = key
        value, detail = _analysis_utility(scores[key][1])
        utilities[arm][seed] = value
        summaries.append({"pool": "A", "arm": arm, "seed": seed, **detail})
    mathematical = original_design.select_direction(utilities)
    selected = mathematical["selected_arm"]
    move = selected != "alpha0"
    return record(
        "actual_direction_decision",
        **binding,
        status="MOVE_FIXED_UNIQUE_DIRECTION" if move else "STOP_RETAIN_BASELINE",
        actual_complete=True,
        prospective_not_executed=False,
        analysis_policy_id=analysis_policy()["id"],
        task_manifest_id=_analysis_task_manifest(tasks, "dev")["id"],
        selection_pool="A",
        selected_arm=selected,
        utility_summaries=summaries,
        mean_utility_by_arm={
            arm: _analysis_fraction(sum(utilities[arm].values(), Fraction()) / 3)
            for arm in original_design.ARMS
        },
        paired_mean_gain=mathematical["paired_mean_gain"],
        tie_priority=list(original_design.ARMS),
        strictly_positive_paired_mean_required=True,
        every_seed_positive_required=False,
        primary_metric="financial_valid",
        NLL_or_method_yield_used=False,
        training_report_ids=[training[key]["id"] for key in keys],
        dev_score_report_ids=[scores[key][0]["id"] for key in keys],
        final_checkpoint_ids=[training[key]["checkpoint_id"] for key in keys],
        observed_A_training_runs=len(training),
        observed_A_dev_sessions=sum(len(value[1]) for value in scores.values()),
        fixed_dev_unique_tasks=180,
        source_clusters={
            "unique_CIK_clusters": len({row["source_cluster"] for row in tasks}),
            "group_unique_CIK_clusters": {
                group: len({row["source_cluster"] for row in tasks if row["group"] == group})
                for group in GROUPS
            },
        },
        planned_B_training_runs=6 if move else 0,
        planned_B_arms=["alpha0", selected] if move else [],
        planned_B_dev_sessions=0,
        planned_confirmation_sessions=8640 if move else 0,
        runner_up_after_confirmation_failure_allowed=False,
        prospective_rule_reference_id=mathematical["id"],
        actual_decision_requires_complete_report_bindings=True,
        execution_lineage=parallel_lineage.execution_lineage([training[key] for key in keys]),
    )


def _analysis_bootstrap(tasks, scores, keys):
    clusters = sorted({row["source_cluster"] for row in tasks})
    cluster_index = {cluster: index for index, cluster in enumerate(clusters)}
    counts = np.zeros((3, len(clusters)), dtype=np.int64)
    successes = np.zeros((len(keys), 3, len(clusters)), dtype=np.int64)
    for index, task in enumerate(tasks):
        group, cluster = GROUPS.index(task["group"]), cluster_index[task["source_cluster"]]
        counts[group, cluster] += 1
        for model, key in enumerate(keys):
            successes[model, group, cluster] += scores[key][1][index]["financial_valid"]
    positions = {key: index for index, key in enumerate(keys)}
    candidate = next(key[1] for key in keys if key[1] != "alpha0")
    # Pair integer success counts first. Subtracting separately rounded utility
    # means can turn an exact zero gain into a tiny spurious positive number.
    differences = np.stack(
        [
            sum(
                successes[positions[(pool, candidate, seed)]]
                - successes[positions[(pool, "alpha0", seed)]]
                for seed in original_design.SEEDS
            )
            for pool in ("A", "B")
        ]
    )
    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    retained, attempts, rejected = [], 0, 0
    accepted = 0
    while accepted < BOOTSTRAP_REPLICATES and attempts < MAX_BOOTSTRAP_ATTEMPTS:
        size = min(1000, BOOTSTRAP_REPLICATES - accepted, MAX_BOOTSTRAP_ATTEMPTS - attempts)
        weights = rng.multinomial(
            len(clusters), np.full(len(clusters), 1 / len(clusters)), size=size
        )
        denominators = weights @ counts.T
        usable = np.all(denominators > 0, axis=1)
        attempts += size
        rejected += int((~usable).sum())
        weights, denominators = weights[usable], denominators[usable]
        if len(weights):
            numerators = np.einsum("rk,pgk->rpg", weights, differences)
            means = (numerators / denominators[:, None, :] / 3).mean(axis=2)
            retained.append(means)
            accepted += len(weights)
    require(
        accepted == BOOTSTRAP_REPLICATES,
        "analysis.bootstrap_attempt_limit_no_partial_interval:"
        f"attempts={attempts},accepted={accepted},empty_group_rejected={rejected}",
    )
    return np.concatenate(retained), {
        "replicates": accepted,
        "attempts": attempts,
        "empty_group_rejected_draws": rejected,
        "seed": BOOTSTRAP_SEED,
        "maximum_attempts": MAX_BOOTSTRAP_ATTEMPTS,
        "cluster_count": len(clusters),
        "clusters_sorted": clusters,
        "cluster_task_counts": {
            group: {cluster: int(counts[g, c]) for c, cluster in enumerate(clusters)}
            for g, group in enumerate(GROUPS)
        },
        "all_observations_use_same_draw_weights": True,
        "empty_groups_are_whole_draw_rejections": True,
        "task_weighted_group_means_not_company_means": True,
    }


def _analysis_interval(point, samples):
    lower, upper = (
        round(float(value), 15) for value in np.quantile(samples, [0.025, 0.975], method="linear")
    )
    return {
        "paired_seed_mean_gain": _analysis_fraction(point),
        "lower": lower,
        "upper": upper,
        "confidence_level": 0.95,
        "zero_in_interval": lower <= 0 <= upper,
        "strictly_positive_interval": lower > 0,
        "five_pp_in_interval": lower <= 0.05 <= upper,
        "cannot_exclude_benefit_at_least_five_pp": upper >= 0.05,
        "at_least_five_pp_lower_bound_established": lower >= 0.05,
    }


def confirm_actual(
    decision, training_reports, confirm_reports, *, binding, confirm_tasks, groups=GROUPS
):
    binding = _analysis_binding(binding)
    checked_record(decision, "actual_direction_decision")
    _analysis_check_binding(decision, binding)
    selected = decision.get("selected_arm")
    require(
        decision.get("actual_complete") is True
        and decision.get("prospective_not_executed") is False
        and decision.get("status") == "MOVE_FIXED_UNIQUE_DIRECTION"
        and decision.get("analysis_policy_id") == analysis_policy()["id"]
        and selected in {"plus", "minus"},
        "analysis.actual_unique_positive_direction_before_confirmation",
    )
    tasks = _analysis_tasks(confirm_tasks, "confirm", groups)
    a_keys = [("A", arm, seed) for arm in original_design.ARMS for seed in original_design.SEEDS]
    b_keys = [("B", arm, seed) for arm in ("alpha0", selected) for seed in original_design.SEEDS]
    training = _analysis_training(training_reports, [*a_keys, *b_keys], binding)
    require(
        decision.get("training_report_ids") == [training[key]["id"] for key in a_keys],
        "analysis.same_A_training_as_actual_selection",
    )
    require(
        decision.get("execution_lineage")
        == parallel_lineage.execution_lineage([training[key] for key in a_keys]),
        "analysis.same_heterogeneous_execution_as_selection",
    )
    keys = [
        (pool, arm, seed)
        for pool in ("A", "B")
        for arm in ("alpha0", selected)
        for seed in original_design.SEEDS
    ]
    scores = _analysis_scores(confirm_reports, training, keys, tasks, "confirm", binding)
    utilities, summaries = {}, []
    for key in keys:
        utilities[key], detail = _analysis_utility(scores[key][1])
        summaries.append({"pool": key[0], "arm": key[1], "seed": key[2], **detail})
    samples, bootstrap = _analysis_bootstrap(tasks, scores, keys)
    pools = {}
    for pool in ("B", "A"):
        point = (
            sum(
                (
                    utilities[(pool, selected, seed)] - utilities[(pool, "alpha0", seed)]
                    for seed in original_design.SEEDS
                ),
                Fraction(),
            )
            / 3
        )
        draws = samples[:, ("A", "B").index(pool)]
        pools[pool] = {
            "role": "primary" if pool == "B" else "auxiliary",
            **_analysis_interval(point, draws),
        }
    return record(
        "confirmation_analysis",
        **binding,
        status="CONFIRMED_POSITIVE_AS_SCOPED"
        if pools["B"]["strictly_positive_interval"]
        else "NOT_CONFIRMED",
        actual_complete=True,
        analysis_policy_id=analysis_policy()["id"],
        decision_id=decision["id"],
        execution_lineage=parallel_lineage.execution_lineage(
            [training[key] for key in [*a_keys, *b_keys]]
        ),
        selected_arm=selected,
        primary_pool="B",
        auxiliary_pool="A",
        primary_pool_selected_after_results=False,
        task_manifest_id=_analysis_task_manifest(tasks, "confirm")["id"],
        fixed_confirm_unique_tasks=720,
        observed_confirmation_sessions=sum(len(value[1]) for value in scores.values()),
        training_report_ids=[training[key]["id"] for key in [*a_keys, *b_keys]],
        confirm_score_report_ids=[scores[key][0]["id"] for key in keys],
        utility_summaries=summaries,
        pools=pools,
        bootstrap=bootstrap,
        diagnostics={
            "unique_CIK_clusters": bootstrap["cluster_count"],
            "group_unique_CIK_clusters": {
                group: len({row["source_cluster"] for row in tasks if row["group"] == group})
                for group in GROUPS
            },
            "largest_cluster_task_fraction": max(
                Counter(row["source_cluster"] for row in tasks).values()
            )
            / 720,
            "source_related_tasks_are_not_independent": True,
        },
        limitations=[
            "Inference concerns the prospectively fixed 200-task training population "
            "and fixed A/B material kernels.",
            "The 720 tasks share CIK sources and periods; seeds and pools do not "
            "multiply independent tasks.",
            "The cluster interval conditions on these fixed trained checkpoints "
            "and does not estimate all training randomness.",
            "A development selected the direction; A confirmation is auxiliary "
            "and does not replace primary B.",
            "Positive as-scoped utility does not establish general financial "
            "or unconstrained-language generalization.",
        ],
    )
