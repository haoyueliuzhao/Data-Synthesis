"""Integrated frozen language/real provider accounting mock/qualification controls."""

import asyncio
import copy
import json

import pytest
from test_finance_research_probe_budget import sheet
from test_finance_research_probe_provider import Client, value
from test_finance_research_qualification import actions, source_fixture

from trusted_synthesis.finance_research.contracts import RunConfig
from trusted_synthesis.finance_research.harness import run_episode, system_message
from trusted_synthesis.finance_research.probe_budget import ProbeBudget
from trusted_synthesis.finance_research.probe_provider import BudgetedDeepSeekFlashProvider
from trusted_synthesis.finance_research.qualification import qualification_rules, qualify_episode
from trusted_synthesis.finance_research.state_mapping import mapper_rules
from trusted_synthesis.finance_research.structured_probe_collection import (
    BUDGET,
    NEW_HARNESS,
    NEW_PROFILE,
    continued_scope,
    register,
)


def generated(tmp_path, *, prose="", alternate=False):
    bundle = source_fixture()
    sequence = actions(bundle)
    if alternate:
        sequence[-1][1]["program"] = "divide(120, 90), subtract(#0, const_1)"

    class Sequence(Client):
        async def post(self, url, **kwargs):
            index = len(self.calls)
            name, arguments = sequence[index]
            self.response = value(id=f"mock-{index}")
            message = self.response["choices"][0]["message"]
            message["content"] = prose
            call = message["tool_calls"][0]
            call.update(
                id=f"mock-call-{index}", function={"name": name, "arguments": json.dumps(arguments)}
            )
            return await super().post(url, **kwargs)

    ledger = ProbeBudget(
        tmp_path / "budget.sqlite3",
        run_id="structured-test",
        price_sheet=sheet(),
        max_output_tokens=2048,
        **BUDGET,
    )
    client = Sequence()
    api = BudgetedDeepSeekFlashProvider(
        ledger=ledger, api_key="synthetic-no-key", episode_id="slot", client=client
    )
    config = RunConfig(
        harness_id=NEW_HARNESS,
        submission_profile=NEW_PROFILE,
        role="sft",
        temperature=1,
        context_limit=1048576,
    )
    episode = asyncio.run(
        run_episode(
            bundle.public,
            api,
            config,
            invocation_context={"run_id": ledger.run_id, "episode_id": "slot", "attempt_index": 1},
        )
    )
    return bundle, episode, ledger, client


def test_actual_new_request_and_replay_have_identical_context_and_qualify(tmp_path):
    bundle, episode, ledger, client = generated(tmp_path)
    rule = qualification_rules(harness_id=NEW_HARNESS)
    result = qualify_episode(
        bundle, episode, qualification_rule_id=rule["id"], mapper_rule_id=mapper_rules()["id"]
    )
    assert result["decision"]["verdict"] == "CompletePass", result["decision"]
    assert len(client.calls) == ledger.snapshot()["requests_dispatched"] == 3
    assert json.loads(client.calls[0][1]["content"])["messages"][0] == system_message(
        episode.config
    )
    assert len(result["evidence"]["checks"]["replay"]["tool_events"]) == 3
    assert not ledger.snapshot()["pending_requests"]
    assert not ledger.snapshot()["unknown_requests"]


def test_nonempty_public_text_is_preserved_not_filtered_or_relabelled(tmp_path):
    bundle, episode, ledger, client = generated(tmp_path, prose="I will read the source.")
    result = qualify_episode(bundle, episode)
    assert result["decision"]["verdict"] == "unknown"
    assert result["decision"]["reason"] == "additional_free_text_claims_not_semantically_verified"
    assert episode.turns[0].raw_text == "I will read the source."
    history = json.loads(client.calls[1][1]["content"])["messages"]
    assert any(
        m.get("role") == "assistant" and m.get("content") == episode.turns[0].raw_text
        for m in history
    )
    assert len(client.calls) == ledger.snapshot()["requests_dispatched"] == 3


def test_new_contract_does_not_relax_author_DAG_and_old_rule_cannot_be_substituted(tmp_path):
    bundle, episode, _, _ = generated(tmp_path, alternate=True)
    result = qualify_episode(bundle, episode)
    assert result["decision"]["verdict"] == "unknown"
    assert result["decision"]["reason"] == "unproved_alternative_or_extra_program_dependency"
    with pytest.raises(ValueError, match="differs from frozen"):
        qualify_episode(bundle, episode, qualification_rule_id=qualification_rules()["id"])
    old = qualification_rules()
    new = qualification_rules(harness_id=NEW_HARNESS)
    assert new["previous_financial_rule_id"] == old["id"]
    assert {
        k: v
        for k, v in new.items()
        if k not in {"id", "previous_financial_rule_id", "execution_protocol_binding"}
    } == {k: v for k, v in old.items() if k != "id"}


def test_new_scope_reuses_all_165_without_outcome_reselection(monkeypatch):
    from trusted_synthesis.finance_research import structured_probe_collection as module

    original = {
        "task_ids": [f"task{i}" for i in range(165)],
        "qualification_rule_id": "old",
        "mapper_rule_id": "mapper",
        "scope_id": "oldscope",
        "coverage_rows": [{"included": True}] * 165,
    }
    # Full 1000-row structural validation has its own tests; this isolates identity rebinding.
    monkeypatch.setattr(
        module, "validate_conditional_scope", lambda scope, *_: copy.deepcopy(scope)
    )
    result = continued_scope({"conditional_scope": original}, {"id": "new"}, {"id": "mapper"})
    assert result["task_ids"] == original["task_ids"]
    assert result["coverage_rows"] == original["coverage_rows"]
    assert result["static_qualification_rule_id"] == "old"
    assert result["static_selection_reused_from_scope_id"] == "oldscope"
    assert original["qualification_rule_id"] == "old"


def test_new_batch_cannot_inherit_old_budget_without_authorization(tmp_path):
    with pytest.raises(ValueError, match="100 CNY authorization"):
        register(tmp_path / "new-run", authorized_CNY=None)
