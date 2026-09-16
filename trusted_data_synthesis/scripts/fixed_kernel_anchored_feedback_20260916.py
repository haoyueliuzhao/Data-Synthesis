"""Full registered J_sources trajectories, sealed generation then private scoring.

One response at a time in gJ; zero-reward terms keep their fixed denominator and
authentic sampled-token receipts but need no gradient. No SFT positive mask.
"""

# ruff: noqa: E501 -- explicit provenance and fixed contracts
import argparse
import gzip
import json
import math
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import fixed_kernel_anchored_segmented_replay_20260916 as segmented
import fixed_kernel_anchored_sources_gpu_gate_20260916 as gate
import fixed_kernel_given_sources_execution_20260915 as given
import fixed_kernel_source_view_compact_20260915 as views
import torch
from torch import nn
from torch.nn.attention import SDPBackend, sdpa_kernel
from transformers import GenerationConfig

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import trajectory_training
from trusted_synthesis.experiments.finance_qa_vnext_pq_student import model as components
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
    load_tokenizer,
)

SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_anchored_feedback_20260916.py"


def trajectory_seed(pool, seed, round_index, task_id, repeat):
    return int(p.sha(p.encode([pool, seed, round_index, task_id, repeat]))[:16], 16) % (2**63)


def registration(tasks, *, pool, seed, round_index, stochastic):
    p.require(
        len(tasks) == 180 and len({row["task_id"] for row in tasks}) == 180,
        "feedback.original_fixed180",
    )
    jobs = []
    for row in tasks:
        for repeat in (1, 2) if stochastic else (0,):
            jobs.append(
                dict(
                    index=len(jobs),
                    task=row,
                    repeat=repeat,
                    seed=trajectory_seed(pool, seed, round_index, row["task_id"], repeat),
                )
            )
    return jobs


def write_session(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = gzip.compress(p.encode(value), compresslevel=1, mtime=0)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return dict(bytes=len(raw), sha256=p.sha(raw), session_id=value["id"])


def read_session(root, row):
    raw = (Path(root) / row["path"]).read_bytes()
    p.require(
        len(raw) == row["bytes"] and p.sha(raw) == row["sha256"], "feedback.sealed_session_bytes"
    )
    value = json.loads(gzip.decompress(raw))
    p.require(value["id"] == row["session_id"], "feedback.sealed_session_identity")
    return value


class Decoder:
    def __init__(self, model, tokenizer, point, assets, stochastic):
        self.model, self.tokenizer, self.point = model, tokenizer, point
        self.stochastic = stochastic
        bound = given.original.bind_policy(assets["tokenizer_binding"], assets["base_binding"])
        self.greedy = SimpleNamespace(
            model=model, configuration=bound, execution_kind=given.original.ACTUAL
        )
        self.eos = bound["eos_token_ids"]
        self.config = GenerationConfig(
            do_sample=True,
            temperature=1.0,
            top_p=1.0,
            top_k=0,
            num_beams=1,
            num_return_sequences=1,
            max_new_tokens=2048,
            repetition_penalty=1.0,
            use_cache=True,
            eos_token_id=self.eos,
            pad_token_id=bound["pad_token_id"],
            bos_token_id=bound["bos_token_id"],
            return_dict_in_generate=True,
            output_scores=True,
        )
        self.calls = self.generated_tokens = 0
        self.context_rejected = False
        self.fatal = None

    def __call__(self, messages, context):
        p.require(
            self.fatal is None
            and messages[0]["content"] == views.SYSTEM + "\nRequested guidance: neutral",
            "feedback.exact_public_SYSTEM_and_no_retry",
        )
        p.require(
            context["max_responses"] == context["max_tools"] == 32
            and context["history_must_not_be_truncated"] is True,
            "feedback.fixed_runtime_limits",
        )
        rendered = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        prompt = self.tokenizer(
            rendered, add_special_tokens=False, truncation=False, padding=False
        )["input_ids"]
        if len(prompt) + 2048 > 24576:
            self.context_rejected = True
            raise given.original.ContextRejected("anchored.full_prompt_plus2048_exceeds24576")
        try:
            cached = getattr(self.model, "_cache", None)
            if cached is not None:
                p.require(
                    callable(getattr(cached, "reset", None)), "feedback.resettable_generation_cache"
                )
                cached.reset()
                delattr(self.model, "_cache")
            self.calls += 1
            p.require(self.calls <= 32, "feedback.no_extra_generate")
            if self.stochastic:
                ids = torch.tensor([prompt], dtype=torch.long, device="cuda:0")
                with torch.no_grad(), sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                    result = self.model.generate(
                        input_ids=ids,
                        attention_mask=torch.ones_like(ids),
                        generation_config=self.config,
                        logits_to_keep=1,
                    )
                p.require(
                    result.sequences[0, : len(prompt)].tolist() == prompt,
                    "feedback.original_prompt_prefix",
                )
                output = result.sequences[0, len(prompt) :].tolist()
                p.require(
                    len(output) == len(result.scores), "feedback.one_real_sampling_score_per_token"
                )
                logps = [
                    float(torch.log_softmax(score[0].float(), -1)[token])
                    for token, score in zip(output, result.scores, strict=True)
                ]
                del result, ids
            else:
                sequences = given.original.BoundDecoder._generate(
                    self.greedy, prompt, [1] * len(prompt)
                )
                p.require(sequences[0][: len(prompt)] == prompt, "feedback.greedy_original_prefix")
                output, logps = sequences[0][len(prompt) :], None
            p.require(0 < len(output) <= 2048, "feedback.actual_nonempty_bounded_output")
            ended = output[-1] in self.eos
            content_ids = output[:-1] if ended else output
            raw = self.tokenizer.decode(
                content_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False
            )
            self.generated_tokens += len(output)
            receipt = p.record(
                "anchored_actual_callback",
                point_id=self.point["id"],
                virtual_or_final_parameter_digest=self.point["parameter_digest"],
                identity=context["identity"],
                response_index=context["response_index"],
                prompt_input_ids=prompt,
                generated_token_ids=output,
                sampled_token_logprobs=logps,
                raw_response_sha256=p.sha(raw),
                actual_terminating_EOS_included=ended,
                actual_GPU_model_generate_calls=1,
                stochastic=self.stochastic,
                original_greedy_backend=not self.stochastic,
                SFT_mask_used=False,
                length_normalized=False,
                context_truncated=False,
                host_JSON_repair=False,
            )
            return dict(raw_response=raw, receipt=receipt)
        except Exception as failure:
            self.fatal = type(failure).__name__ + ": " + str(failure)
            raise


class VirtualTaskOperation(nn.Module):
    def __init__(self, model, function):
        super().__init__()
        self.model, self.function = model, function

    def forward(self):
        return self.function(self.model)


def at_point(model, theta, function):
    operation = VirtualTaskOperation(model, function)
    overrides = {"model." + name: value for name, value in theta.items()}
    overrides.update(
        {"model." + name: value.detach().clone() for name, value in model.named_buffers()}
    )
    with gate.proxy_mode(model, gradient=False):
        return torch.func.functional_call(operation, overrides, (), strict=False)


def generate_jobs(
    root, directory, jobs, point, assets, model, tokenizer, *, theta=None, stochastic
):
    root, directory = Path(root).resolve(), Path(directory)
    runtime, cached_views, results = views.build_runtime(), {}, []
    before_rng = gate.rng_digest()
    for job in jobs:
        row = job["task"]
        if row["task_id"] not in cached_views:
            cached_views[row["task_id"]] = given.load_view(root, row, point["source_manifest_id"])
        view, identity = cached_views[row["task_id"]]
        sources = views.SourceViewSources(json.loads(view["public_messages"][0]["content"]))
        decoder = Decoder(model, tokenizer, point, assets, stochastic)

        def invoke(_model, view=view, identity=identity, sources=sources, decoder=decoder):
            return runtime.generate(
                view["public_messages"],
                identity,
                sources,
                provider=decoder,
                requested_basis="neutral",
            )

        started = time.monotonic()
        with torch.random.fork_rng(devices=[0]):
            torch.manual_seed(job["seed"])
            session = at_point(model, theta, invoke) if theta is not None else invoke(model)
        p.require(
            decoder.fatal is None, "feedback.decoder_fault_not_zero_reward:" + str(decoder.fatal)
        )
        p.require(
            session["terminal"] != "provider_error" or decoder.context_rejected,
            "feedback.only_legal_context_rejection_not_resource_failure",
        )
        path = directory / "sessions" / (f"{job['index']:04d}.json.gz")
        reference = write_session(path, session)
        item = p.record(
            "anchored_generated_trajectory",
            job=job,
            point_id=point["id"],
            path=str(path.relative_to(root)),
            **reference,
            actual_generate_calls=decoder.calls,
            generated_tokens=decoder.generated_tokens,
            legal_context_rejection=decoder.context_rejected,
            elapsed_seconds=time.monotonic() - started,
            private_assessment_performed=False,
        )
        p.write_once(directory / "completed" / (f"{job['index']:04d}.json"), item)
        results.append(item)
        print(
            json.dumps(
                dict(
                    event="trajectory_complete",
                    index=job["index"],
                    calls=decoder.calls,
                    point=point["id"],
                    at=p.now(),
                )
            ),
            flush=True,
        )
    p.require(gate.rng_digest() == before_rng, "feedback.trajectory_RNG_isolation")
    return results


def validate_receipts(session, item, point_id, stochastic):
    p.require(
        item["point_id"] == point_id
        and item["job"]["task"]["task_id"] == session["identity"]["task_id"],
        "feedback.registered_task_and_point",
    )
    count = tokens = 0
    for turn in session["turns"]:
        receipt = p.checked(turn["provider_receipt"], "anchored_actual_callback")
        generated, prompt = receipt["generated_token_ids"], receipt["prompt_input_ids"]
        p.require(
            receipt["point_id"] == point_id
            and receipt["identity"] == session["identity"]
            and receipt["response_index"] == turn["response_index"]
            and receipt["raw_response_sha256"] == p.sha(turn["raw_response"])
            and receipt["actual_GPU_model_generate_calls"] == 1
            and not receipt["SFT_mask_used"]
            and not receipt["context_truncated"]
            and not receipt["host_JSON_repair"]
            and receipt["stochastic"] == stochastic
            and len(prompt) + 2048 <= 24576
            and 0 < len(generated) <= 2048,
            "feedback.authentic_complete_token_receipt",
        )
        if stochastic:
            logps = receipt["sampled_token_logprobs"]
            p.require(
                len(logps) == len(generated) and all(math.isfinite(x) and x <= 1e-6 for x in logps),
                "feedback.finite_unmodified_sampling_probabilities",
            )
        count += 1
        tokens += len(generated)
    p.require(
        count == item["actual_generate_calls"] and tokens == item["generated_tokens"],
        "feedback.actual_call_token_accounting",
    )


_SCORING = None


def initialize_scoring(root, source_root, tasks, manifest_id, point_id, stochastic):
    global _SCORING
    private = given.offline_assets(Path(root), Path(source_root), tasks)
    _SCORING = (Path(root), private, manifest_id, point_id, stochastic, views.build_runtime(), {})


def score_one(item):
    root, private, manifest_id, point_id, stochastic, runtime, fixtures = _SCORING
    row = item["job"]["task"]
    if row["task_id"] not in fixtures:
        fixtures[row["task_id"]] = given.fixture(root, row, manifest_id, private)
    fixture = fixtures[row["task_id"]]
    session = read_session(root, item)
    validate_receipts(session, item, point_id, stochastic)
    result = runtime.assess_session(
        session, fixture["bundle"], fixture["native_bindings"], fixture["sources"]
    )
    return dict(
        index=item["job"]["index"],
        task_id=row["task_id"],
        repeat=item["job"]["repeat"],
        group=row["group"],
        session_id=session["id"],
        assessment=result,
        Q=int(result["financial_valid"]),
    )


def score_directory(root, directory, source_root, *, workers=12):
    root, directory = Path(root).resolve(), Path(directory)
    frozen = p.checked(
        p.read_json(directory / "generation_manifest.json"), "anchored_generation_manifest"
    )
    p.require(
        frozen["complete"]
        and len(frozen["trajectories"]) == (360 if frozen["stochastic"] else 180),
        "feedback.all_generation_sealed_before_private_scoring",
    )
    args = (
        str(root),
        str(source_root),
        frozen["tasks"],
        frozen["source_manifest_id"],
        frozen["point_id"],
        frozen["stochastic"],
    )
    with ProcessPoolExecutor(
        max_workers=workers, initializer=initialize_scoring, initargs=args
    ) as executor:
        values = list(executor.map(score_one, frozen["trajectories"], chunksize=1))
    for value in values:
        p.write_once(
            directory / "assessments" / (f"{value['index']:04d}.json"), value["assessment"]
        )
    results = [{key: value for key, value in row.items() if key != "assessment"} for row in values]
    report = p.record(
        "anchored_independent_scoring",
        generation_manifest_id=frozen["id"],
        point_id=frozen["point_id"],
        complete=True,
        denominator=len(values),
        scores=results,
        qualified=sum(row["Q"] for row in values),
        source_manifest_id=frozen["source_manifest_id"],
        private_references_never_sent_to_generator=True,
        financial_rule_unchanged=True,
        scoring_after_all_generation_complete=True,
        confirm_tasks_opened=0,
        finished_at=p.now(),
    )
    p.write_once(directory / "scoring_report.json", report)
    return report


def feedback_gradient(root, directory, model, theta, *, event_sink=None):
    root, directory = Path(root).resolve(), Path(directory)
    manifest = p.checked(
        p.read_json(directory / "generation_manifest.json"), "anchored_generation_manifest"
    )
    scored = p.checked(
        p.read_json(directory / "scoring_report.json"), "anchored_independent_scoring"
    )
    p.require(
        manifest["stochastic"]
        and scored["complete"]
        and scored["denominator"] == 360
        and scored["generation_manifest_id"] == manifest["id"],
        "feedback.exact360_complete_fixed_denominator",
    )
    by_index = {row["index"]: row for row in scored["scores"]}
    p.require(
        set(by_index) == set(range(360)) and len(manifest["trajectories"]) == 360,
        "feedback.no_missing_or_selected_trajectories",
    )
    total = {name: torch.zeros_like(value) for name, value in theta.items()}
    accounting = Counter()
    emit = event_sink or (lambda item: None)
    for item in manifest["trajectories"]:
        index = item["job"]["index"]
        score = by_index[index]
        p.require(
            score["session_id"] == item["session_id"] and score["Q"] in (0, 1),
            "feedback.exact_binary_reward_binding",
        )
        if score["Q"] == 0:
            accounting["zero_reward_gradient_terms_skipped"] += 1
            continue  # Full sealed receipt validation already ran in the separate scoring process.
        session = read_session(root, item)
        for turn in session["turns"]:
            receipt = turn["provider_receipt"]
            with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                values, gradient, used = segmented.segmented_logp(
                    model,
                    theta,
                    receipt["prompt_input_ids"],
                    receipt["generated_token_ids"],
                    expected=receipt["sampled_token_logprobs"],
                    block_size=8,
                )
            for name in total:
                total[name].add_(gradient[name], alpha=1 / 360)
            accounting["responses_replayed"] += 1
            accounting["sampled_tokens_with_parameter_derivative"] += len(
                receipt["generated_token_ids"]
            )
            accounting["cached_forward_target_positions"] += used["cached_forward_target_positions"]
            emit(
                dict(
                    event="feedback_response_backward",
                    trajectory=index,
                    response=turn["response_index"],
                    **dict(accounting),
                )
            )
            del values, gradient
        accounting["positive_reward_trajectories"] += 1
    p.require(
        all(bool(torch.isfinite(value).all()) for value in total.values()), "feedback.finite_gJ"
    )
    return total, p.record(
        "anchored_full_trajectory_feedback_gradient",
        point_id=manifest["point_id"],
        scoring_report_id=scored["id"],
        denominator=360,
        accounting=dict(accounting),
        zero_reward_authentic_receipts_validated=True,
        zero_reward_GPU_replay_not_claimed=True,
        all_sampled_error_and_EOS_tokens_of_positive_trajectories_included=True,
        cross_response_graph_not_required_by_score_function_sum=True,
        prefix_derivatives_within_each_response_preserved=True,
        length_normalization=False,
        gJ_digest=gate.tensor_digest(total),
        theoretical_zero_Contribution_claimed=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("score", "generate"), required=True)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--job", type=Path)
    args = parser.parse_args()
    if args.mode == "score":
        print(score_directory(args.root, args.directory, args.source_root)["id"])
    else:
        job = p.read_json(args.job)
        for path, expected in job["code_sources"].items():
            p.require(
                p.sha(args.root / path) == expected, "feedback.frozen_public_worker_implementation"
            )
        p.require(
            views.binding()["id"] == job["runtime_binding_id"], "feedback.frozen_public_runtime"
        )
        model, _ = trajectory_training.load_registered_student(
            job["assets"]["base_binding"],
            job["training_seed"],
            trainable=False,
            adapter_path=args.root
            / job["point"]["adapter_directory"]
            / job["point"]["adapter"]["path"],
            adapter_record=job["point"]["adapter"],
        )
        p.require(
            components.adapter_digest(model) == job["point"]["adapter"]["parameter_digest"],
            "feedback.loaded_exact_parameter_point",
        )
        actual = {
            name: value
            for name, value in model.named_parameters()
            if name.endswith((".lora_A", ".lora_B"))
        }
        p.require(
            gate.tensor_digest(actual) == job["point"]["parameter_digest"],
            "feedback.same_virtual_tensor_digest_in_sampler",
        )
        tokenizer = load_tokenizer(job["assets"]["tokenizer_binding"])
        generate_jobs(
            args.root,
            args.root / job["directory"],
            job["jobs"],
            job["point"],
            job["assets"],
            model,
            tokenizer,
            stochastic=job["stochastic"],
        )
