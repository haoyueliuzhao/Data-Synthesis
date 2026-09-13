"""Tiny CPU controls, not Qwen/financial utility or production execution results."""

import copy
import json
from types import SimpleNamespace

import pytest
import torch

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import feedback as f
from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.protocol import record, sha
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import runtime


class TinyStudent(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weights = torch.nn.Parameter(torch.tensor([1.1, -0.3], dtype=torch.float64))
        self.forward_calls = 0
        self.eval()

    def forward(self, input_ids, attention_mask, use_cache):
        assert input_ids.device.type == "cpu" and not use_cache
        assert torch.equal(attention_mask, torch.ones_like(input_ids))
        self.forward_calls += 1
        return SimpleNamespace(logits=self.weights.expand(1, input_ids.shape[1], 2))


class MockTokenizer:
    chat_template = "synthetic exact public chat template"

    def __init__(self, responses=None):
        self.responses = list(responses or [json.dumps({"final": {"answer": "1"}})])
        self.render_count = 0
        self.encode_count = 0

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        assert not tokenize and add_generation_prompt
        self.render_count += 1
        return json.dumps(messages, sort_keys=True)

    def __call__(self, rendered, add_special_tokens, truncation, padding):
        assert not add_special_tokens and not truncation and not padding
        self.encode_count += 1
        # Deliberately a mock, not a claim of text/token fidelity for Qwen.
        return {"input_ids": [1, 1], "attention_mask": [1, 1]}

    def decode(self, content, skip_special_tokens, clean_up_tokenization_spaces):
        assert not skip_special_tokens and not clean_up_tokenization_spaces
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


def setup():
    model, tokenizer = TinyStudent(), MockTokenizer()
    point = f.bind_virtual_model(
        model,
        base_identity={"synthetic_base": "tiny_cpu_only"},
        virtual_step_id="synthetic_virtual_step:0",
    )
    policy = f.decoder_policy(
        eos_token_ids=[0],
        pad_token_id=0,
        tokenizer_binding_id="mock_only",
        chat_template_sha256=sha(tokenizer.chat_template),
    )
    tasks = [
        {"task_id": "task_" + f"{index:064x}", "group": group}
        for index, group in enumerate(group for group in f.GROUPS for _ in range(60))
    ]
    registry = f.register_probes(tasks, pool="A", training_seed=11, outer_round=0)
    return model, tokenizer, point, policy, registry


def make_probe(
    model, tokenizer, point, policy, registration, *, responses=1, terminal="first_final"
):
    decoder = f.BoundProbeDecoder(
        model, tokenizer, registration, policy=policy, virtual_identity=point
    )
    identity = {"task_id": registration["task_id"]}
    messages = [
        {"role": "system", "content": runtime.SYSTEM + "\nRequested guidance: neutral"},
        {"role": "user", "content": "synthetic public question; no private answer"},
    ]
    turns = []
    for index in range(responses):
        context = {
            "identity": identity,
            "response_index": index,
            "max_responses": 32,
            "max_tools": 32,
            "remaining_tool_calls": 32,
            "history_must_not_be_truncated": True,
        }
        reply = decoder(copy.deepcopy(messages), context)
        turns.append(
            {
                "response_index": index,
                "input_messages": copy.deepcopy(messages),
                "raw_response": reply["raw_response"],
                "raw_response_sha256": sha(reply["raw_response"]),
                "provider_receipt": reply["receipt"],
            }
        )
        messages.extend(
            [
                {"role": "assistant", "content": reply["raw_response"]},
                {"role": "user", "content": "tool observation: external numbers 999 888"},
            ]
        )
    transcript = {
        "identity": identity,
        "terminal": terminal,
        "turns": turns,
        "provider_calls": responses,
        "first_final_index": responses - 1 if terminal == "first_final" else None,
    }
    return f.seal_probe(
        registration,
        decoder.attempts,
        terminal=terminal,
        transcript=transcript,
        virtual_identity=point,
        policy=policy,
    )


def reseal(kind, value, **changes):
    return record(
        kind,
        **{
            key: item
            for key, item in {**value, **changes}.items()
            if key not in {"id", "schema_version"}
        },
    )


def test_registry_exact_denominator_groups_and_common_random_numbers():
    _, _, _, _, registry = setup()
    assert registry["probe_count"] == 360
    assert len({p["id"] for p in registry["probes"]}) == 360
    assert all(sum(p["group"] == group for p in registry["probes"]) == 120 for group in f.GROUPS)
    assert registry == f.validate_registry(registry)
    p = registry["probes"][0]
    key = {key: p[key] for key in ("pool", "training_seed", "outer_round", "task_id", "repeat")}
    assert p["rng_seed"] == f.probe_seed(**key)
    assert f.probe_seed(**{**key, "pool": "B"}) != p["rng_seed"]
    assert f.probe_seed(**{**key, "repeat": 2}) != p["rng_seed"]
    assert f.probe_seed(**{**key, "outer_round": 1}) != p["rng_seed"]
    with pytest.raises(TypeError):
        f.probe_seed(**key, condition="full_anchored_vtdo")
    with pytest.raises(ValueError, match="180"):
        f.register_probes(registry["dev_tasks"][:-1], pool="A", training_seed=11, outer_round=0)
    altered = copy.deepcopy(registry["dev_tasks"])
    altered[0]["group"] = f.GROUPS[1]
    with pytest.raises(ValueError, match="60"):
        f.register_probes(altered, pool="A", training_seed=11, outer_round=0)


def test_sampling_full_softmax_and_real_eos_probability_replay():
    model, _, point, policy, _ = setup()
    # Find a deterministic seed yielding at least one non-EOS token; no greedy substitute.
    samples = [
        f.sample_tokens(
            model,
            [1, 1],
            generator=torch.Generator().manual_seed(seed),
            policy=policy,
            virtual_identity=point,
        )
        for seed in range(10)
    ]
    assert any(len(sample["generated_token_ids"]) > 1 for sample in samples)
    assert all(sample["generated_token_ids"][-1] == 0 for sample in samples)
    logp = torch.log_softmax(model.weights, -1).detach()
    for sample in samples:
        assert sample["includes_actual_eos"]
        assert sample["sampled_token_logprobs"] == [
            float(logp[token]) for token in sample["generated_token_ids"]
        ]
    changed_policy = reseal("probe_decoder_policy", policy, top_k=1)
    with pytest.raises(ValueError, match="exact_random_decoder"):
        f.sample_tokens(
            model, [1], generator=torch.Generator(), policy=changed_policy, virtual_identity=point
        )


def test_full_trajectory_errors_and_eos_not_SFT_or_length_normalized():
    model, _, point, policy, registry = setup()
    tokenizer = MockTokenizer(["THIS IS INVALID JSON", '{"final":{"answer":"1"}}'])
    probe = make_probe(model, tokenizer, point, policy, registry["probes"][0], responses=2)
    target = [
        token
        for attempt in probe["attempts"]
        for token in attempt["sampled"]["generated_token_ids"]
    ]
    assert probe["attempts"][0]["raw_response"] == "THIS IS INVALID JSON"
    assert "999 888" in probe["attempts"][1]["input_messages"][-1]["content"]
    counts = (tokenizer.encode_count, tokenizer.render_count)
    replay = f.recompute_trajectory_logprob(model, probe, virtual_identity=point, policy=policy)
    assert (tokenizer.encode_count, tokenizer.render_count) == counts
    expected = torch.log_softmax(model.weights, -1)[target].sum()
    assert replay["sampled_token_count"] == len(target) >= 2
    assert torch.equal(replay["logprob"], expected)
    assert not torch.equal(replay["logprob"], expected / len(target))
    assert target.count(0) == 2  # Both actual EOS, including the invalid response.
    gradient = torch.autograd.grad(replay["logprob"], model.weights)[0]
    reference = torch.bincount(torch.tensor(target), minlength=2) - len(
        target
    ) * model.weights.softmax(-1)
    assert torch.allclose(gradient, reference)


def test_parameter_dropout_identity_and_record_tampering_fail_closed():
    model, tokenizer, point, policy, registry = setup()
    probe = make_probe(model, tokenizer, point, policy, registry["probes"][0])
    with torch.no_grad():
        model.weights[0] += 0.01
    with pytest.raises(ValueError, match="parameter_bytes_changed"):
        f.recompute_trajectory_logprob(model, probe, virtual_identity=point, policy=policy)
    model, tokenizer, point, policy, registry = setup()
    probe = make_probe(model, tokenizer, point, policy, registry["probes"][0])
    model.train()
    with pytest.raises(ValueError, match="dropout"):
        f.recompute_trajectory_logprob(model, probe, virtual_identity=point, policy=policy)
    model.eval()
    altered = copy.deepcopy(probe)
    altered["attempts"][0]["sampled"]["generated_token_ids"][0] = 1
    with pytest.raises(ValueError, match="content_identity"):
        f.recompute_trajectory_logprob(model, altered, virtual_identity=point, policy=policy)
    swapped = reseal("probe_virtual_identity", point, virtual_step_id="other_step")
    with pytest.raises(ValueError, match="sample_identity"):
        f.recompute_trajectory_logprob(model, probe, virtual_identity=swapped, policy=policy)


def test_context_rejection_and_partial_failure_keep_actual_sampled_tokens():
    model, _, point, policy, _ = setup()
    sample = f.sample_tokens(
        model,
        [1] * (24576 - 2048 + 1),
        generator=torch.Generator(),
        policy=policy,
        virtual_identity=point,
    )
    assert sample["finish_reason"] == "context_rejected"
    assert sample["generated_token_ids"] == [] and model.forward_calls == 0
    assert not sample["model_generation_invoked"]
    f._validate_sample(sample, point, policy)

    class Broken(TinyStudent):
        def forward(self, **kwargs):
            if self.forward_calls:
                raise RuntimeError("synthetic forward failure")
            return super().forward(**kwargs)

    broken = Broken()
    with torch.no_grad():
        broken.weights[:] = torch.tensor([-20.0, 20.0])
    bound = f.bind_virtual_model(broken, base_identity="CPU-only", virtual_step_id="v0")
    partial = f.sample_tokens(
        broken, [1], generator=torch.Generator(), policy=policy, virtual_identity=bound
    )
    assert partial["finish_reason"] == "generation_error"
    assert partial["generated_token_ids"] == [1]
    assert len(partial["sampled_token_logprobs"]) == 1
    f._validate_sample(partial, bound, policy)


def test_fixed_reward_gradient_matches_analytic_and_does_not_mutate_real_grad():
    model, tokenizer, point, policy, registry = setup()
    probes = [
        make_probe(model, tokenizer, point, policy, registration)
        for registration in registry["probes"]
    ]
    rewards = {
        probe["id"]: {
            "qualification_id": "synthetic_complete_qualification:" + str(index),
            "status": "PASS" if index == 0 else ("UNDETERMINED" if index % 2 else "FAIL"),
        }
        for index, probe in enumerate(probes)
    }
    before = model.weights.detach().clone()
    model.weights.grad = torch.tensor([3.0, 4.0], dtype=torch.float64)
    result = f.reward_gradient(
        model, probes, rewards, virtual_identity=point, registry=registry, policy=policy
    )
    target = probes[0]["attempts"][0]["sampled"]["generated_token_ids"]
    expected = (
        torch.bincount(torch.tensor(target), minlength=2) - len(target) * model.weights.softmax(-1)
    ) / 360
    assert torch.allclose(result["gradient"]["weights"], expected)
    assert torch.equal(model.weights, before)
    assert torch.equal(model.weights.grad, torch.tensor([3.0, 4.0], dtype=torch.float64))
    artifact = result["artifact"]
    assert artifact["fixed_denominator"] == 360 and artifact["utility"] == 1 / 360
    assert artifact["sampled_token_count"] == sum(
        len(a["sampled"]["generated_token_ids"]) for p in probes for a in p["attempts"]
    )
    assert not artifact["actual_round"] and artifact["optimizer_steps"] == 0
    with pytest.raises(ValueError, match="fixed_360"):
        f.reward_gradient(
            model, probes[:1], rewards, virtual_identity=point, registry=registry, policy=policy
        )
    with pytest.raises(ValueError, match="every_failure"):
        f.reward_gradient(
            model,
            probes,
            {probes[0]["id"]: rewards[probes[0]["id"]]},
            virtual_identity=point,
            registry=registry,
            policy=policy,
        )
    all_zero = {key: {**value, "status": "FAIL"} for key, value in rewards.items()}
    zero = f.reward_gradient(
        model, probes, all_zero, virtual_identity=point, registry=registry, policy=policy
    )
    assert torch.equal(zero["gradient"]["weights"], torch.zeros_like(model.weights))
    assert zero["artifact"]["status"] == "UNINFORMATIVE_FEEDBACK"
    assert zero["artifact"]["theoretical_Contribution_zero"] is False


def test_no_final_and_qualification_missing_failures_are_not_success():
    model, tokenizer, point, policy, registry = setup()
    probe = make_probe(
        model, tokenizer, point, policy, registry["probes"][0], terminal="response_limit"
    )
    with pytest.raises(ValueError, match="no_success_without_final"):
        f._rewards([probe], {probe["id"]: {"qualification_id": "q", "status": "PASS"}})
    f._rewards([probe], {probe["id"]: {"qualification_id": "q", "status": "NO_FINAL"}})


def test_production_is_hard_gate_not_a_boolean_claim():
    status = f.production_adapter_status()
    assert not status["actual_round"] and not status["new_student_sessions_authorized"]
    with pytest.raises(ValueError, match="PRODUCTION_ADAPTER_NOT_VALIDATED"):
        f.require_production_adapter()
    model, _, point, _, _ = setup()
    spoof = reseal("probe_virtual_identity", point, actual_round=True)
    with pytest.raises(ValueError, match="PRODUCTION_ADAPTER_NOT_VALIDATED"):
        f.validate_virtual_model(model, spoof)


def test_private_fields_not_accepted_in_public_registration_and_neutral_prefix_enforced():
    model, tokenizer, point, policy, registry = setup()
    tasks = copy.deepcopy(registry["dev_tasks"])
    tasks[0]["qa.gold"] = "private scorer material"
    with pytest.raises(ValueError, match="public_dev_fields_only"):
        f.register_probes(tasks, pool="A", training_seed=11, outer_round=0)
    decoder = f.BoundProbeDecoder(
        model, tokenizer, registry["probes"][0], policy=policy, virtual_identity=point
    )
    with pytest.raises(ValueError, match="original_neutral_system"):
        decoder([{"role": "system", "content": "other instruction"}], {})
    assert model.forward_calls == 0


def test_online_public_runtime_then_offline_qualification_keeps_all_360():
    model, tokenizer, point, policy, registry = setup()
    sources = runtime.SnapshotSources.synthetic({"snapshot": {"synthetic": True}})
    seen, qualified = [], []
    groups = {row["task_id"]: row["group"] for row in registry["dev_tasks"]}

    class PublicOnly:
        def public_envelope(self, task_id):
            seen.append(task_id)
            public = {
                "question": "synthetic public question",
                "source_document": sources.descriptors(),
                "quantity_contract": {},
                "source_policy": {},
                "tool_contract": {},
                "period_contract": {"task_id": task_id},
            }
            messages = [{"role": "user", "content": runtime.encode(public).decode()}]
            identity = {
                "task_id": task_id,
                "family": groups[task_id],
                "surface_version_id": "synthetic",
                "public_messages_sha256": runtime.sha(runtime.encode(messages)),
                "parent_manifest_id": "synthetic_public_parent",
            }
            return {"messages": messages, "identity": identity}

        @property
        def private(self):
            pytest.fail("private qualifier data reached online generation")

    probes = f.collect_probes(
        registry,
        PublicOnly(),
        lambda envelope: sources,
        model=model,
        tokenizer=tokenizer,
        policy=policy,
        virtual_identity=point,
    )
    assert len(seen) == len(probes) == 360 and qualified == []
    assert all(p["transcript"]["private_oracle_access"] is False for p in probes)

    def offline_qualifier(transcript):
        assert len(seen) == 360  # No interleaved oracle feedback.
        qualified.append(transcript["identity"]["task_id"])
        return {
            "qualification_id": "synthetic_undetermined:" + str(len(qualified)),
            "status": "UNDETERMINED",
        }

    rewards = f.qualify_probes(
        probes, offline_qualifier, registry=registry, virtual_identity=point, policy=policy
    )
    assert len(rewards) == len(qualified) == 360
    assert all(value["status"] == "UNDETERMINED" for value in rewards.values())


def test_tokenizer_fault_is_retained_but_cannot_supply_gJ():
    model, _, point, policy, registry = setup()

    class BrokenTokenizer(MockTokenizer):
        def __call__(self, *args, **kwargs):
            raise RuntimeError("synthetic tokenization failure before sampling")

    registration = registry["probes"][0]
    decoder = f.BoundProbeDecoder(
        model, BrokenTokenizer(), registration, policy=policy, virtual_identity=point
    )
    context = {
        "identity": {"task_id": registration["task_id"]},
        "response_index": 0,
        "max_responses": 32,
        "max_tools": 32,
        "remaining_tool_calls": 32,
        "history_must_not_be_truncated": True,
    }
    messages = [{"role": "system", "content": runtime.SYSTEM + "\nRequested guidance: neutral"}]
    with pytest.raises(RuntimeError, match="tokenization failure"):
        decoder(messages, context)
    assert len(decoder.attempts) == 1 and model.forward_calls == 0
    transcript = {
        "identity": context["identity"],
        "terminal": "provider_error",
        "turns": [],
        "provider_calls": 1,
        "first_final_index": None,
    }
    probe = f.seal_probe(
        registration,
        decoder.attempts,
        terminal="provider_error",
        transcript=transcript,
        virtual_identity=point,
        policy=policy,
    )
    assert not probe["complete_sampling_record"] and probe["all_failures_retained"]
    with pytest.raises(ValueError, match="incomplete_sampling_record_no_gJ"):
        f.recompute_trajectory_logprob(model, probe, virtual_identity=point, policy=policy)


def test_length_limit_keeps_all_2048_without_fabricating_eos_or_cropping():
    model, _, _, policy, _ = setup()
    with torch.no_grad():
        model.weights[:] = torch.tensor([-100.0, 100.0])
    point = f.bind_virtual_model(model, base_identity="synthetic_no_eos", virtual_step_id="v0")
    sample = f.sample_tokens(
        model,
        [1],
        generator=torch.Generator().manual_seed(7),
        policy=policy,
        virtual_identity=point,
    )
    assert sample["finish_reason"] == "length"
    assert sample["generated_token_ids"] == [1] * 2048
    assert not sample["includes_actual_eos"]
    f._validate_sample(sample, point, policy)
    overlength = reseal(
        "sampled_generation",
        sample,
        generated_token_ids=[1] * 2049,
        generated_ids_sha256=sha(f.encode([1] * 2049)),
        sampled_token_logprobs=[0.0] * 2049,
    )
    with pytest.raises(ValueError, match="no_cropping_or_overlength"):
        f._validate_sample(overlength, point, policy)


def test_score_gradient_finite_difference_and_resealed_probability_tamper():
    model, tokenizer, point, policy, registry = setup()
    probe = make_probe(model, tokenizer, point, policy, registry["probes"][0], responses=2)
    replay = f.recompute_trajectory_logprob(model, probe, virtual_identity=point, policy=policy)
    gradient = torch.autograd.grad(replay["logprob"] / 360, model.weights)[0]
    target = [
        token
        for attempt in probe["attempts"]
        for token in attempt["sampled"]["generated_token_ids"]
    ]
    theta = model.weights.detach()
    epsilon = 1e-6
    differences = []
    for index in range(theta.numel()):
        direction = torch.zeros_like(theta)
        direction[index] = epsilon
        upper = torch.log_softmax(theta + direction, -1)[target].sum() / 360
        lower = torch.log_softmax(theta - direction, -1)[target].sum() / 360
        differences.append((upper - lower) / (2 * epsilon))
    assert torch.allclose(gradient, torch.stack(differences), atol=1e-10, rtol=1e-7)

    attempt = copy.deepcopy(probe["attempts"][0])
    probabilities = list(attempt["sampled"]["sampled_token_logprobs"])
    probabilities[0] -= 0.1
    attempt["sampled"] = reseal(
        "sampled_generation", attempt["sampled"], sampled_token_logprobs=probabilities
    )
    attempt = reseal("probe_attempt", attempt)
    transcript = copy.deepcopy(probe["transcript"])
    transcript["turns"][0]["provider_receipt"] = attempt["id"]
    tampered = f.seal_probe(
        probe["registration"],
        [attempt, probe["attempts"][1]],
        terminal=probe["terminal"],
        transcript=transcript,
        virtual_identity=point,
        policy=policy,
    )
    with pytest.raises(ValueError, match="replayed_sampling_probabilities_mismatch"):
        f.recompute_trajectory_logprob(model, tampered, virtual_identity=point, policy=policy)
