"""Greedy local Student evaluation; no evaluator or private reference is imported."""

import time

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel
from transformers import GenerationConfig

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration.tokens import (
    load_bound_assets,
)

from .plan import OUTPUT, evaluation_config, read_json, record, require, sha
from .runtime import run_session


class LocalDecoder:
    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer
        self.config = evaluation_config()
        self.generation = GenerationConfig(
            do_sample=False,
            num_beams=1,
            max_new_tokens=self.config["max_new_tokens_per_response"],
            eos_token_id=self.config["eos_token_ids"],
            pad_token_id=self.config["pad_token_id"],
            bos_token_id=151643,
            repetition_penalty=self.config["repetition_penalty"],
            use_cache=True,
        )

    def __call__(self, messages):
        started = time.perf_counter()
        rendered = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        encoded = self.tokenizer(
            rendered, add_special_tokens=False, return_tensors="pt", truncation=False
        )
        n_prompt = encoded["input_ids"].shape[-1]
        if (
            n_prompt + self.config["max_new_tokens_per_response"]
            > self.config["maximum_sequence_length"]
        ):
            return {
                "content": "",
                "finish_reason": "context_token_limit",
                "prompt_token_count": n_prompt,
                "generation_invoked": False,
                "generated_token_ids": [],
                "public_content_token_ids": [],
                "generated_token_count": 0,
                "elapsed_seconds": time.perf_counter() - started,
                "rendered_prompt_sha256": sha(rendered.encode()),
                "prompt_truncated": False,
            }
        encoded = {key: tensor.to("cuda:0") for key, tensor in encoded.items()}
        with torch.inference_mode(), sdpa_kernel(SDPBackend.FLASH_ATTENTION):
            sequence = self.model.generate(
                **encoded, generation_config=self.generation, logits_to_keep=1
            )
        generated = sequence[0, n_prompt:].detach().cpu().tolist()
        ended = bool(generated) and generated[-1] in self.config["eos_token_ids"]
        content_ids = generated[:-1] if ended else generated
        text = self.tokenizer.decode(
            content_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False
        )
        return {
            "content": text,
            "finish_reason": "stop" if ended else "generation_truncated_length",
            "generation_invoked": True,
            "prompt_token_count": n_prompt,
            "generated_token_count": len(generated),
            "generated_token_ids": generated,
            "public_content_token_ids": content_ids,
            "elapsed_seconds": time.perf_counter() - started,
            "rendered_prompt_sha256": sha(rendered.encode()),
            "prompt_truncated": False,
            "only_final_actual_EOS_removed_from_public_text": ended,
        }


def evaluate_model(root, variant, model, model_identity):
    output = root / OUTPUT
    binding, _, tokenizer = load_bound_assets(root)
    config = read_json(output / "preparation/evaluation_configuration.json")
    require(config == evaluation_config(), "evaluation.frozen_configuration")
    registrations = read_json(output / "preparation/evaluation_registrations.json")
    require(
        len(registrations) == 12 and variant in config["variants"], "evaluation.fixed_panel_variant"
    )
    model.eval()
    model.requires_grad_(False)
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    decoder = LocalDecoder(model, tokenizer)
    store = DurableStore(output / "evaluation" / variant)
    store.json("identity.json", model_identity)
    store.json("configuration.json", config)
    started = time.perf_counter()
    rows = []
    for registration in registrations:
        key = registration["task_key"]
        public = read_json(output / f"preparation/public/{key}.json")
        require(
            public["id"] == registration["public_document_id"],
            "evaluation.public_registration_join",
        )
        directory = store.root / "sessions" / key
        result = run_session(public, directory, decoder, model_identity)
        row = {
            "variant": variant,
            "task_key": key,
            "group": registration["group"],
            "result_id": result["id"],
            "terminal": result["terminal"],
            "model_requests": result["model_requests"],
            "tool_calls": result["tool_calls"],
            "initial_messages_sha256": result["initial_request_messages_sha256"],
        }
        rows.append(row)
        print("evaluation", variant, key, row["terminal"], row["model_requests"], flush=True)
    report = record(
        "student_generation_report",
        variant=variant,
        rows=rows,
        sessions=12,
        model_identity=model_identity,
        tokenizer_binding_id=binding["id"],
        elapsed_seconds=time.perf_counter() - started,
        no_gold_evaluation_or_feedback_in_this_process=True,
        teacher_calls=0,
        decoder_configuration_id=config["id"],
    )
    store.json("report.json", report)
    seal_directory(store, kind="pq_student_generation_manifest", report_id=report["id"])
    return report
