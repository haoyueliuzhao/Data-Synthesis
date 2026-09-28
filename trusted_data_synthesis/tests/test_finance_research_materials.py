"""Qualified mock-token packages; no real qualification, model load, or GPU."""

import asyncio
import json
from collections import defaultdict
from fractions import Fraction
from types import SimpleNamespace

import pytest
from test_finance_research_providers import provider

from trusted_synthesis.finance_research.contracts import (
    CallSettlement,
    Episode,
    RunConfig,
    ToolEvent,
    digest,
)
from trusted_synthesis.finance_research.materials import (
    MaterialRegistration,
    QualificationDecision,
    TaskBatch,
    build_material_pool,
    execute_task_batch_update,
    execute_training_update,
    task_batch_examples,
    weighted_examples,
)
from trusted_synthesis.finance_research.providers import canonical_assistant_message


def episode(local, task, seed, turns=1, failed=()):
    config = RunConfig(role="sft", max_new_tokens=8, seed=seed)
    replies, events, settlements = [], [], []
    messages = [{"role": "user", "content": task}]
    for index in range(turns):
        name = "final_answer" if index == turns - 1 else "read_source"
        raw = (
            "<tool_call>\n"
            + json.dumps({"name": name, "arguments": {"answer": "3", "fixture_turn": index}})
            + "\n</tool_call>"
        )
        local.tokenizer.decode = lambda ids, _raw=raw, **kwargs: _raw
        reply = asyncio.run(local.chat(messages, [], config))
        replies.append(reply)
        call = reply.tool_calls[0]
        event = ToolEvent(
            call_id=call.call_id,
            name=call.name,
            raw_arguments=call.raw_arguments,
            normalized_arguments=call.arguments,
            executed_arguments=call.arguments,
            raw_output={"answer": "3"},
            visible_output="mock tool result",
            is_error=index in failed,
        )
        events.append(event)
        settlements.append(
            CallSettlement(
                attempt_index=index,
                state="returned",
                actual_model_calls=1,
                request_sha256=reply.receipt.request_sha256,
            )
        )
        messages += [
            canonical_assistant_message(reply),
            {"role": "tool", "tool_call_id": call.call_id, "content": event.visible_output},
        ]
    return Episode(
        task_id=task,
        dataset="finqa",
        public_task_sha256=digest(task),
        config=config,
        provider=local.identity,
        turns=tuple(replies),
        tool_events=tuple(events),
        messages=tuple(messages),
        final_answer="3",
        stop_reason="final_answer",
        actual_model_calls=turns,
        provider_attempts=turns,
        call_settlements=tuple(settlements),
        all_provider_calls_settled=True,
        elapsed_seconds=0.01,
    )


def decision(ep, state=None, verdict="CompletePass"):
    return QualificationDecision(
        episode_sha256=digest(ep),
        task_id=ep.task_id,
        verdict=verdict,
        state_id=state,
        evidence_sha256="e" * 64,
        reason="explicit mock validator decision, not real certification",
    )


def registration(decisions, *, support=None, mu=None, pi0=None):
    return MaterialRegistration(
        source_manifest_sha256="a" * 64,
        validator_binding_id="registered-validator",
        qualification_registration_id="registered-qualification",
        decisions=tuple(decisions),
        state_support=support or {"q": ("a", "b")},
        mu=mu or {"q": "1"},
        pi0=pi0 or {"q": {"a": "1/2", "b": "1/2"}},
    )


def test_real_original_prompt_positive_responses_and_eos_retained():
    local = provider()
    a, b = episode(local, "q", 1, turns=2), episode(local, "q", 2)
    pool = build_material_pool([a, b], registration([decision(a, "a"), decision(b, "b")]))
    assert pool.admitted and not pool.manifest.state_semantics_independently_proven
    first = pool.packages[0]
    assert first["whole_package_target_tokens"] == 4 and first["fused"] is False
    rows = pool.row_arrays(first["package_id"])
    assert len(rows) == 2
    assert rows[0]["input_ids"] == (1, 1, 1, 3, 2)
    assert rows[0]["target_positions"] == (3, 4)
    assert rows[0]["target_ids"] == (3, 2)


def test_general_task_mass_state_count_length_and_static_control():
    local = provider()
    a, aa, b, c = [
        episode(local, task, seed) for task, seed in (("q", 1), ("q", 2), ("q", 3), ("control", 4))
    ]
    reg = registration(
        [decision(a, "a"), decision(aa, "a"), decision(b, "b"), decision(c, "c")],
        support={"q": ("a", "b"), "control": ("c",)},
        mu={"q": "3/4", "control": "1/4"},
        pi0={"q": {"a": "1/2", "b": "1/2"}, "control": {"c": "1"}},
    )
    pool = build_material_pool([a, aa, b, c], reg)
    rows = weighted_examples(pool, reg.pi0)
    assert rows[0]["target_token_coefficient"] == "3/32"  # 3/4 * 1/2 / (2 * 2)
    mass = defaultdict(Fraction)
    for row in rows:
        mass[row["task_id"]] += (
            Fraction(row["target_token_coefficient"]) * row["whole_package_target_tokens"]
        )
    assert dict(mass) == {"q": Fraction(3, 4), "control": Fraction(1, 4)}
    assert pool.manifest.static_control_tasks == ("control",)
    with pytest.raises(ValueError):
        weighted_examples(pool, {"q": reg.pi0["q"], "control": {"c": 0.9}})


def test_unknown_and_invalid_retained_without_minting_missing_state():
    local = provider()
    a, unknown, invalid = [episode(local, "q", seed) for seed in (1, 2, 3)]
    reg = registration(
        [
            decision(a, "a"),
            decision(unknown, verdict="unknown"),
            decision(invalid, verdict="invalid"),
        ]
    )
    pool = build_material_pool([a, unknown, invalid], reg)
    assert len(pool.manifest.inventory) == 3 and len(pool.packages) == 1
    assert not pool.admitted and pool.manifest.missing_support == (("q", "b"),)
    with pytest.raises(ValueError, match="qualified"):
        weighted_examples(pool, reg.pi0)
    with pytest.raises(ValueError, match="incomplete"):
        pool.row_arrays(pool.packages[0]["package_id"])


def test_success_or_wording_never_creates_state_or_completes_registration():
    local = provider()
    a = episode(local, "q", 1)
    with pytest.raises(ValueError, match="undeclared"):
        registration([decision(a, "invented-from-tool-order")])
    with pytest.raises(ValueError, match="cannot mint"):
        decision(a, state="a", verdict="unknown")
    with pytest.raises(ValueError, match="explicit decision"):
        build_material_pool([a], registration([]))


def test_test_split_label_and_missing_real_receipt_cannot_be_training():
    local = provider()
    a = episode(local, "q", 1)
    test = a.model_copy(update={"config": a.config.model_copy(update={"role": "test"})})
    with pytest.raises(ValueError, match="SFT-role"):
        build_material_pool([test], registration([decision(test, "a")]))
    missing = a.model_copy(update={"turns": (a.turns[0].model_copy(update={"receipt": None}),)})
    with pytest.raises(ValueError, match="receipt"):
        build_material_pool([missing], registration([decision(missing, "a")]))


def test_consumer_bridge_receives_general_weights_and_no_legacy_loss_label(monkeypatch):
    from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
        trajectory_consumer,
    )

    local = provider()
    a, b = episode(local, "q", 1), episode(local, "q", 2)
    reg = registration([decision(a, "a"), decision(b, "b")])
    pool = build_material_pool([a, b], reg)
    captured = {}

    def consume(model, optimizer, examples, batch, **kwargs):
        captured.update(examples=examples, batch=batch, **kwargs)
        return {
            "id": "mock-original",
            "schema_version": "old",
            "loss_rule": "old fixed5",
            "optimizer_step_calls": 1,
            "execution_design": "old prefix union",
        }

    monkeypatch.setattr(trajectory_consumer, "execute_update", consume)
    result = execute_training_update(object(), object(), pool, reg.pi0, device="cpu")
    assert captured["examples"][0]["coefficient_float"] == 0.25
    assert captured["batch"]["tasks"] == ["q"] and captured["trajectory_cache"] is pool
    assert result["loss_rule"] == "mu(task)*pi(state|task)/(n_state*whole_package_target_tokens)"
    assert result["execution_design"] == "positive_response_rows_v2"
    assert result["optimizer_step_calls"] == 1 and result["full_pool_update"]


def test_manifest_public_copy_cannot_mutate_frozen_internal_weights():
    local = provider()
    a, b = episode(local, "q", 1), episode(local, "q", 2)
    reg = registration([decision(a, "a"), decision(b, "b")])
    pool = build_material_pool([a, b], reg)
    copy = pool.manifest
    copy.registration.mu["q"] = "999"
    assert weighted_examples(pool, reg.pi0)[0]["coefficient_float"] == 0.25


def test_frozen_consumer_executes_one_synthetic_cpu_update():
    torch = pytest.importorskip("torch")
    local = provider()
    a, b = episode(local, "q", 1), episode(local, "q", 2)
    reg = registration([decision(a, "a"), decision(b, "b")])
    pool = build_material_pool([a, b], reg)

    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(4, 4))

        def forward(self, *, input_ids, attention_mask, use_cache, logits_to_keep):
            assert not use_cache
            return SimpleNamespace(logits=self.weight[input_ids][:, logits_to_keep, :])

    model = Tiny()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01)
    result = execute_training_update(model, optimizer, pool, reg.pi0, device="cpu")
    assert result["optimizer_step_calls"] == 1
    assert result["target_tokens"] == 4 and result["sequence_tokens"] == 10
    assert not torch.equal(model.weight, torch.zeros_like(model.weight))
    assert optimizer.state[model.weight]["step"].item() == 1


def test_failed_response_and_eos_have_zero_targets_but_history_is_retained():
    local = provider()
    ep = episode(local, "q", 1, turns=3, failed=(0,))
    reg = registration([decision(ep, "a")], support={"q": ("a",)}, pi0={"q": {"a": "1"}})
    pool = build_material_pool([ep], reg)
    frozen = pool.manifest.packages[0]
    assert len(frozen.rows) == 3
    assert frozen.rows[0].input_ids[-2:] == (3, 2)
    assert frozen.rows[0].target_ids == frozen.rows[0].target_positions == ()
    assert frozen.whole_package_target_tokens == 4
    assert len(pool.row_arrays(frozen.package_id)) == 2
    later_request = ep.turns[1].provider_metadata["request"]["messages"]
    assert later_request[1]["tool_calls"][0]["function"]["arguments"]["fixture_turn"] == 0
    assert later_request[2]["content"] == "mock tool result"


def test_task_batch_uniform_1000_five_tasks_matches_pi_over_5nL():
    # A CPU manifest fixture isolates the arithmetic: no 1,000 model calls.
    from trusted_synthesis.finance_research.materials import MaterialPool, MaterialPoolManifest

    ep = episode(provider(), "q", 1)
    tasks = [f"q{i}" for i in range(1000)]
    reg = registration(
        [],
        support={task: ("a",) for task in tasks},
        mu={task: "1/1000" for task in tasks},
        pi0={task: {"a": "1"} for task in tasks},
    )
    single = build_material_pool(
        [ep], registration([decision(ep, "a")], support={"q": ("a",)}, pi0={"q": {"a": "1"}})
    )
    prototype = single.manifest.packages[0]
    packages = tuple(
        prototype.model_copy(update={"task_id": task, "package_id": f"mock:{task}"})
        for task in tasks
    )
    initial = MaterialPoolManifest(
        cache_id="pending",
        registration=reg,
        inventory=(),
        packages=packages,
        admitted=True,
        missing_support=(),
        static_control_tasks=tuple(tasks),
    )
    pool = MaterialPool(
        initial.model_copy(
            update={
                "cache_id": "finance_materials:"
                + digest(initial.model_dump(mode="json", exclude={"cache_id"}))
            }
        )
    )
    batch = TaskBatch(
        task_ids=tuple(tasks[:5]),
        sampling_probability=reg.mu,
        sampling_design="uniform_epoch_permutation",
        schedule_id="mock",
        step=0,
    )
    rows = task_batch_examples(pool, reg.pi0, batch)
    assert len(rows) == 5
    assert {row["target_token_coefficient"] for row in rows} == {"1/10"}  # 1/(5*1*2)
    assert (
        sum(
            Fraction(row["target_token_coefficient"]) * row["whole_package_target_tokens"]
            for row in rows
        )
        == 1
    )
    assert weighted_examples(pool, reg.pi0)[0]["target_token_coefficient"] == "1/2000"


def test_task_batch_original_consumer_tiny_cpu_update_without_second_division():
    torch = pytest.importorskip("torch")
    local = provider()
    a, b = episode(local, "q", 1), episode(local, "q", 2)
    reg = registration([decision(a, "a"), decision(b, "b")])
    pool = build_material_pool([a, b], reg)
    batch = TaskBatch(
        task_ids=("q",) * 5,
        sampling_probability={"q": "1"},
        sampling_design="iid_with_replacement",
        schedule_id="tiny",
        step=0,
    )
    rows = task_batch_examples(pool, reg.pi0, batch)
    assert len(rows) == 10 and rows[0]["target_token_coefficient"] == "1/20"

    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(4, 4))

        def forward(self, *, input_ids, attention_mask, use_cache, logits_to_keep):
            return SimpleNamespace(logits=self.weight[input_ids][:, logits_to_keep, :])

    model = Tiny()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    result = execute_task_batch_update(model, optimizer, pool, reg.pi0, batch, device="cpu")
    assert result["optimizer_step_calls"] == 1 and result["target_tokens"] == 20
    assert result["batch_size"] == 5 and result["additional_batch_division"] is False
    assert result["full_pool_update"] is False
    assert model.weight.abs().sum() > 0


def test_task_batch_cannot_drop_registered_tasks_or_claim_nonuniform_permutation():
    with pytest.raises(ValueError, match="uniform"):
        TaskBatch(
            task_ids=("q",),
            sampling_probability={"q": "3/4", "r": "1/4"},
            sampling_design="uniform_epoch_permutation",
            schedule_id="x",
            step=0,
        )
    ep = episode(provider(), "q", 1)
    reg = registration([decision(ep, "a")], support={"q": ("a",)}, pi0={"q": {"a": "1"}})
    pool = build_material_pool([ep], reg)
    batch = TaskBatch(
        task_ids=("q",),
        sampling_probability={"q": "1/2", "r": "1/2"},
        sampling_design="iid_with_replacement",
        schedule_id="x",
        step=0,
    )
    with pytest.raises(ValueError, match="registered task"):
        task_batch_examples(pool, reg.pi0, batch)
