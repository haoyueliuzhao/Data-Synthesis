"""Small CPU-only collector controls: never dispatch real HTTP or 8000 mock runs."""

import asyncio
import copy
import json
from collections import Counter
from dataclasses import asdict
from types import SimpleNamespace

import pytest
from test_finance_public_reasoning import call, mocked_episode
from test_finance_research_datasets import finqa_record
from test_finance_research_probe_budget import sheet, usage
from test_finance_research_probe_provider import Client
from test_finance_semantic_review import fixture_bundle, fixture_review, mechanical
from test_finance_v6_review_provider import response

from trusted_synthesis.finance_research import v6_collection as collector
from trusted_synthesis.finance_research.contracts import invocation_identity
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.probe_budget import V6_PURPOSE, ProbeBudget
from trusted_synthesis.finance_research.semantic_review import review_request
from trusted_synthesis.finance_research.v6_review_provider import _request_body, request_review


def plan_fixture():
    return dict(
        id="v6-controller-control",
        task_ids=[],
        price_sheet=asdict(sheet()),
        budget_limits=dict(collector.LIMITS),
        inventory=dict(slots=[]),
    )


def ledger_fixture(path, plan):
    return ProbeBudget(
        path / "budget.sqlite3",
        run_id=plan["id"],
        price_sheet=plan["price_sheet"],
        max_output_tokens=16384,
        purpose=V6_PURPOSE,
        **plan["budget_limits"],
    )


def test_registered_original_roster_has_eight_equal_candidates_no_hidden_holdout(monkeypatch):
    tasks = [SimpleNamespace(dataset="finqa", task_id=f"original-{i}") for i in range(1000)]
    roles = {f"finqa/{task.task_id}": "sft" for task in tasks}
    previous = dict(
        snapshot="original-public",
        snapshot_id="snapshot",
        assets={},
        role_plan=dict(assignments=roles),
    )
    official = dict(
        documents=[],
        checked_at_utc="fixture",
        CNY_per_million_tokens=dict(
            peak=dict(input_cache_hit="0.04", input_cache_miss="2", output="8")
        ),
    )
    monkeypatch.setattr(
        collector, "read_json", lambda p: official if p == collector.OFFICIAL else previous
    )
    monkeypatch.setattr(
        collector, "load_public_snapshot", lambda p: (dict(id="snapshot"), tasks, [])
    )
    monkeypatch.setattr(collector, "verify_role_plan", lambda *a: None)
    monkeypatch.setattr(collector, "runtime_binding", lambda: {})
    monkeypatch.setattr(collector, "sha", lambda p: "a" * 64)
    plan = collector.build_plan("frozen-source-control")
    slots = plan["inventory"]["slots"]
    assert len(slots) == len({s["slot_id"] for s in slots}) == 8000
    assert set(Counter(s["task_id"] for s in slots).values()) == {8}
    assert {s["purpose"] for s in slots} == {"common_material_candidate"}
    assert plan["inventory"]["sealed_diagnostic_slots_per_task"] == 0
    assert plan["task_ids"] == [task.task_id for task in tasks]
    assert plan["review"]["fixed_requests"] == 2000
    assert plan["budget_limits"]["request_cap"] == 1000 * 8 * 32 + 2000
    by_id = {s["slot_id"]: s for s in slots}
    assert {by_id[sid]["slot_index"] for sid in plan["launch_order"][:1000]} == {0}
    assert not plan["downstream"]["automatic_training_in_this_controller"]


def test_private_reference_and_review_preparation_cannot_precede_full_generation_seal(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(collector, "validate_recovery", lambda *args: ({}, {}))
    touched = []
    monkeypatch.setattr(collector, "load_public_snapshot", lambda *args: touched.append("source"))
    monkeypatch.setattr(collector, "read_json", lambda *args: touched.append("private-or-seal"))
    with pytest.raises(ValueError, match="full seal"):
        collector.prepare_reviews(tmp_path, plan_fixture())
    assert touched == []


@pytest.mark.parametrize(
    "artifact",
    ["slots", "generation_seal", "reviews", "assessment", "review_seal", "inventory_complete"],
)
def test_missing_paid_ledger_is_never_recreated_from_artifact_tree(tmp_path, artifact):
    (tmp_path / artifact).mkdir()
    plan = plan_fixture()
    with pytest.raises(ValueError, match="ledger|paid evidence"):
        collector.validate_recovery(tmp_path, plan)
    with pytest.raises(ValueError, match="ledger"):
        collector.ledger_for(tmp_path, plan)
    assert not (tmp_path / "budget.sqlite3").exists()


def test_unknown_request_retains_cost_reservation_and_blocks_resume(tmp_path):
    plan = plan_fixture()
    ledger = ledger_fixture(tmp_path, plan)
    coordinates = invocation_identity(
        dict(run_id=plan["id"], episode_id="unsettled", attempt_index=1), turn_index=0
    )
    body = dict(model="deepseek-flash", max_tokens=2048, thinking={"type": "disabled"})
    ledger.reserve(
        coordinates["invocation_id"],
        coordinates=coordinates,
        request=body,
        request_body=json.dumps(body).encode(),
    )
    ledger.mark_dispatched(coordinates["invocation_id"])
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="unsettled|unknown"):
        collector.validate_recovery(tmp_path, plan)
    assert ledger.snapshot() == before and before["held_microcny"] > 0


def test_settled_orphan_call_does_not_disappear_or_reset_cost(tmp_path):
    plan = plan_fixture()
    ledger = ledger_fixture(tmp_path, plan)
    coordinates = invocation_identity(
        dict(run_id=plan["id"], episode_id="orphan", attempt_index=1), turn_index=0
    )
    body = dict(model="deepseek-flash", max_tokens=2048, thinking={"type": "disabled"})
    ledger.reserve(
        coordinates["invocation_id"],
        coordinates=coordinates,
        request=body,
        request_body=json.dumps(body).encode(),
    )
    ledger.mark_dispatched(coordinates["invocation_id"])
    ledger.settle(
        coordinates["invocation_id"],
        usage=usage(),
        http_status=200,
        response_classification="model_response",
        response_body=b"{}",
    )
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="orphan|missing paid"):
        collector.validate_recovery(tmp_path, plan)
    assert ledger.snapshot() == before and before["settled_tariff_microcny"] > 0


def test_public_action_observation_replay_preserves_actual_error_and_catches_history_change():
    bundle = adapt_finqa([finqa_record()], split="train", revision="collector-control")[0]
    episode, _ = mocked_episode(
        bundle,
        [
            ("R: Try divisor.", [call("run_program", {"program": "divide(8, 0)"})]),
            (
                "U: It failed. R: Submit difference.",
                [call("submit_program", {"program": "subtract(8, 2)"})],
            ),
        ],
    )
    checks = collector.mechanical_check(
        bundle.public, episode, {"slot_id": "chain"}, {"id": "V6-CPU"}
    )
    assert all(
        checks[k] is True
        for k in (
            "history_complete",
            "actions_observations_bound",
            "private_reference_isolated",
            "calls_settled",
        )
    )
    assert checks["native_correct"] is None and episode.tool_events[0].is_error
    changed = copy.deepcopy(episode.turns[1].provider_metadata)
    changed["public_request"]["messages"][2]["content"] = "silently removed failed history"
    altered = episode.model_copy(
        update={
            "turns": (
                episode.turns[0],
                episode.turns[1].model_copy(update={"provider_metadata": changed}),
            )
        }
    )
    assert not collector.mechanical_check(
        bundle.public, altered, {"slot_id": "chain"}, {"id": "V6-CPU"}
    )["history_complete"]


def test_fixed_group_review_request_enters_real_paid_body_contract(tmp_path):
    plan = plan_fixture()
    ledger = ledger_fixture(tmp_path, plan)
    request = review_request(fixture_bundle(), dict(program="add(120, 0)", answer=120), 1)
    actual, reviewer = _request_body(ledger, request)
    assert reviewer == 1
    assert actual["messages"] == request["messages"]
    assert actual["max_tokens"] == 16384 and actual["thinking"] == {"type": "disabled"}
    assert actual["temperature"] == 0 and actual["model"] == "deepseek-flash"


def test_unknown_resolution_retains_each_native_outcome_and_all_candidate_ids():
    checks = mechanical()
    checks["s0"]["native_correct"] = False
    checks["s1"]["native_correct"] = None
    resolution = collector.unknown_resolution(
        dict(mechanical=checks), [dict(reviewer=1, reason="length")]
    )
    assert set(resolution["slots"]) == set(checks)
    assert resolution["slots"]["s0"]["q_native"] is False
    assert resolution["slots"]["s1"]["q_native"] is None
    assert all(
        slot["v_trace"] == "unknown" and slot["encoding_manifest"] is None
        for slot in resolution["slots"].values()
    )
    assert resolution["task_mapping"] == "incomplete"


def test_native_incorrect_process_valid_is_not_in_material_counts(tmp_path, monkeypatch):
    bundle = fixture_bundle()
    prepared = dict(
        bundle=bundle,
        mechanical=mechanical(),
        requests=[
            review_request(bundle, dict(answer=120, program="add(120, 0)"), i) for i in (0, 1)
        ],
    )
    prepared["mechanical"]["s0"]["native_correct"] = False
    prepared = collector.bound(prepared)
    plan = dict(
        id="controller-summary", task_ids=[bundle["task_id"]], review=dict(human_audit_task_ids=[])
    )

    class CompleteReviewMap(dict):
        def __len__(self):
            return 2000  # Bypass scale only; both real schema reviews below are parsed/resolved.

    reviews = CompleteReviewMap(
        {
            collector.review_id(plan, bundle["task_id"], i): dict(
                content=json.dumps(fixture_review(bundle, i)), finish_reason="stop"
            )
            for i in (0, 1)
        }
    )
    (tmp_path / "review_seal").mkdir()
    (tmp_path / "review_seal/record.json").write_text("{}")
    monkeypatch.setattr(collector, "validate_recovery", lambda *args: ({}, reviews))
    monkeypatch.setattr(collector, "read_json", lambda *args: prepared)
    monkeypatch.setattr(collector, "persist", lambda *args: None)
    monkeypatch.setattr(collector, "status", lambda *args: None)
    result = collector.finalize(tmp_path, plan, SimpleNamespace(snapshot=lambda: {}))
    assert result["tasks"][0]["n_x"] == 7
    assert sum(result["tasks"][0]["states"].values()) == 7


@pytest.mark.parametrize(
    "field,replacement", [("content", "fabricated derived content"), ("finish_reason", "length")]
)
def test_recovery_binds_review_derived_content_and_finish_to_actual_paid_response(
    tmp_path, field, replacement
):
    plan = plan_fixture()
    bundle = fixture_bundle()
    task_id = bundle["task_id"]
    plan["task_ids"] = [task_id]
    ledger = ledger_fixture(tmp_path, plan)
    request = review_request(fixture_bundle(), dict(program="add(120, 0)", answer=120), 0)
    rid = collector.review_id(plan, task_id, 0)
    artifact = asyncio.run(
        request_review(
            ledger=ledger,
            api_key="cpu-mocked-not-real-secret",
            episode_id=rid,
            request=request,
            client=Client(response()),
        )
    )
    artifact[field] = replacement
    collector.persist(collector.review_directory(tmp_path, rid) / "response", artifact)
    prepared = collector.bound(
        dict(bundle=bundle, requests=[request, review_request(bundle, dict(answer=120), 1)])
    )
    collector.persist(collector.task_directory(tmp_path, task_id) / "prepared", prepared)
    # The expected response-binding rejection occurs before the final generation-seal barrier.
    with pytest.raises(ValueError, match="content|finish|derived|binding|response"):
        collector.validate_recovery(tmp_path, plan)


def test_complete_http_null_review_keeps_settlement_and_original_none_content(tmp_path):
    plan = plan_fixture()
    bundle = fixture_bundle()
    task_id = bundle["task_id"]
    plan["task_ids"] = [task_id]
    ledger = ledger_fixture(tmp_path, plan)
    request = review_request(bundle, dict(program="add(120, 0)", answer=120), 0)
    rid = collector.review_id(plan, task_id, 0)
    artifact = asyncio.run(
        request_review(
            ledger=ledger,
            api_key="cpu-mocked-not-real-secret",
            episode_id=rid,
            request=request,
            client=Client(response(None)),
        )
    )
    assert artifact["content"] is None and not ledger.unsettled()
    collector.persist(collector.review_directory(tmp_path, rid) / "response", artifact)
    prepared = collector.bound(
        dict(bundle=bundle, requests=[request, review_request(bundle, dict(answer=120), 1)])
    )
    collector.persist(collector.task_directory(tmp_path, task_id) / "prepared", prepared)
    # Null isn't changed to ''. Only the deliberately absent 8000-generation barrier blocks.
    with pytest.raises(ValueError, match="reviews cannot precede full generation seal"):
        collector.validate_recovery(tmp_path, plan)
