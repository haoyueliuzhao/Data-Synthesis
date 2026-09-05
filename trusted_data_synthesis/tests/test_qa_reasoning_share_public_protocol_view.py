"""Public-view tests only: reuse frozen JSON and never execute a financial action."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_share_public_protocol import models, public_view

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def frozen() -> dict[str, Any]:
    directory = ROOT / models.PARENT
    # Exact files from the already completed stage; no source builder or Archive access.
    source = json.loads((directory / "source_binding.json").read_bytes())
    contract = json.loads((directory / "contract.json").read_bytes())
    context = public_view.public_context(source, contract)
    protocol = models.protocol_contract(context)
    return {"source": source, "contract": contract, "context": context, "protocol": protocol}


def initial_state(frozen: dict[str, Any]) -> dict[str, Any]:
    return public_view.make_state(frozen["context"], frozen["protocol"], models.initial_dynamic())


def test_context_is_exact_public_projection_of_the_same_frozen_universe(
    frozen: dict[str, Any],
) -> None:
    context, source, contract = frozen["context"], frozen["source"], frozen["contract"]
    assert set(context) == {
        "id",
        "schema_version",
        "task",
        "evidence",
        "operations",
        "numeric",
        "shared_obligations",
        "answer_schema",
        "actual_support_citations_required",
        "all_visible_evidence_citations_required",
    }
    assert context["task"] == contract["task"]
    assert context["evidence"] == source["evidence"]
    assert context["operations"] == contract["operations"]
    assert context["numeric"] == contract["numeric"]
    assert set(context["evidence"]) == {"freight", "other", "total", "part_whole"}
    assert context["evidence"]["total"]["value"] == "21813"
    relation = context["evidence"]["part_whole"]
    assert any(ref["json_pointer"] == "/30/table_ori/9" for ref in relation["source_references"])
    assert (
        sorted(item["id"] for item in context["evidence"].values())
        == (contract["task"]["evidence_universe_ids"])
    )
    for key in ("measurement", "route_specific_preconditions", "maximum_candidate_executions"):
        assert key in contract and key not in context


def test_private_outer_host_fields_do_not_enter_the_public_context(
    frozen: dict[str, Any],
) -> None:
    source, contract = deepcopy(frozen["source"]), deepcopy(frozen["contract"])
    source["answer_oracle"] = {"expected_answer": "PRIVATE_GOLD_CANARY"}
    source["candidate_family"] = {"route": "PRIVATE_ROUTE_CANARY", "nodes": ["PRIVATE_PLAN"]}
    contract["oracle"] = {"expected_answer": "PRIVATE_GOLD_CANARY"}
    contract["next_operation"] = "PRIVATE_PLAN"
    assert public_view.public_context(source, contract) == frozen["context"]


def test_initial_state_has_only_public_context_dynamic_fields_and_remaining_bounds(
    frozen: dict[str, Any],
) -> None:
    state = initial_state(frozen)
    assert set(state) == {
        "id",
        "schema_version",
        "context_id",
        "protocol_id",
        "remaining_bounds",
        *public_view.CONTEXT_VIEW_FIELDS,
        *models.DYNAMIC_FIELDS,
    }
    assert state["phase"] == "action"
    assert state["accepted_claims"] == []
    assert state["pending_observation"] is None
    assert state["terminal"] is None
    assert state["last_feedback"] is None
    assert state["remaining_bounds"] == {"actions": 3, "updates": 3, "submissions": 12}
    for key in public_view.CONTEXT_VIEW_FIELDS:
        assert state[key] == frozen["context"][key]
    request = public_view.request_for(state, frozen["protocol"])
    assert request["allowed_submission_kinds"] == ["action", "final"]
    assert set(request["response_schema"]) == {"action", "final"}
    assert "generator_kind" not in request and "generator_response_origin" not in request
    assert "route" not in request and "nodes" not in request


def test_views_and_requests_do_not_alias_private_or_previous_nested_objects(
    frozen: dict[str, Any],
) -> None:
    source, contract = deepcopy(frozen["source"]), deepcopy(frozen["contract"])
    context = public_view.public_context(source, contract)
    protocol = models.protocol_contract(context)
    state = public_view.make_state(context, protocol, models.initial_dynamic())
    request = public_view.request_for(state, protocol)
    request["state"]["evidence"]["total"]["value"] = "CHANGED_BY_CONSUMER"
    request["state"]["operations"]["relation_sum"]["parameters"]["method"] = "mean"
    request["response_schema"]["action"]["properties"]["kind"]["const"] = "CHANGED_KIND"
    assert state["evidence"]["total"]["value"] == "21813"
    assert context["evidence"]["total"]["value"] == source["evidence"]["total"]["value"]
    assert protocol["submission_schemas"]["action"]["properties"]["kind"]["const"] == "action"
    state["evidence"]["freight"]["source_references"][0]["source_value"] = "CHANGED_REFERENCE"
    assert (
        context["evidence"]["freight"]["source_references"]
        == (source["evidence"]["freight"]["source_references"])
    )
    context["task"]["question"] = "CHANGED_QUESTION"
    assert contract["task"] == frozen["contract"]["task"]


def test_pending_observation_exposes_update_schema_without_accepting_a_claim(
    frozen: dict[str, Any],
) -> None:
    # Synthetic record for projection testing, not a tool execution or scientific result.
    observation = models.record(
        "observation",
        action_id="synthetic-action",
        success=True,
        output={"value": "20397", "metric": "synthetic_projection_only"},
    )
    dynamic = models.initial_dynamic()
    dynamic.update(
        phase="update", pending_observation=observation, action_count=1, submission_count=1
    )
    state = public_view.make_state(frozen["context"], frozen["protocol"], dynamic)
    assert state["pending_observation"] == observation
    assert state["accepted_claims"] == [] and dynamic["accepted_claims"] == []
    request = public_view.request_for(state, frozen["protocol"])
    assert request["allowed_submission_kinds"] == ["update"]
    assert request["response_schema"] == {
        "update": frozen["protocol"]["submission_schemas"]["update"]
    }
    request["state"]["pending_observation"]["output"]["value"] = "CHANGED"
    assert observation["output"]["value"] == "20397"


def test_exhausted_action_budget_exposes_only_final(frozen: dict[str, Any]) -> None:
    dynamic = models.initial_dynamic()
    dynamic.update(action_count=3, update_count=3, submission_count=6)
    state = public_view.make_state(frozen["context"], frozen["protocol"], dynamic)
    request = public_view.request_for(state, frozen["protocol"])
    assert state["remaining_bounds"] == {"actions": 0, "updates": 0, "submissions": 6}
    assert request["allowed_submission_kinds"] == ["final"]
    assert set(request["response_schema"]) == {"final"}


@pytest.mark.parametrize("ended", [True, False])
def test_no_generator_request_after_terminal_or_submission_budget_exhaustion(
    frozen: dict[str, Any],
    ended: bool,
) -> None:
    dynamic = models.initial_dynamic()
    if ended:
        dynamic.update(phase="terminal", terminal="completed")
        error = "public_view.terminal_request"
    else:
        dynamic["submission_count"] = 12
        error = "public_view.submission_budget"
    state = public_view.make_state(frozen["context"], frozen["protocol"], dynamic)
    with pytest.raises(models.ProtocolError, match=error):
        public_view.request_for(state, frozen["protocol"])


@pytest.mark.parametrize("private_key", ["expected_answer", "route", "next_operation"])
def test_dynamic_input_rejects_unlisted_host_fields(
    frozen: dict[str, Any],
    private_key: str,
) -> None:
    dynamic = models.initial_dynamic()
    dynamic[private_key] = "PRIVATE_CANARY"
    with pytest.raises(models.ProtocolError, match="public_view.dynamic_fields"):
        public_view.make_state(frozen["context"], frozen["protocol"], dynamic)


def test_feedback_is_stage_code_only_and_nested_oracle_cannot_be_rehashed_in(
    frozen: dict[str, Any],
) -> None:
    dynamic = models.initial_dynamic()
    dynamic["last_feedback"] = {"code": "admission.parameters", "expected_answer": "PRIVATE"}
    with pytest.raises(models.ProtocolError, match="public_view.feedback_fields"):
        public_view.make_state(frozen["context"], frozen["protocol"], dynamic)
    dynamic["last_feedback"] = {"code": "admission.parameters"}
    state = public_view.make_state(frozen["context"], frozen["protocol"], dynamic)
    assert state["last_feedback"] == {"code": "admission.parameters"}
    # Identity is internally valid, so rejection is the public-field boundary.
    observation = models.record("observation", output={"oracle": "PRIVATE_GOLD"})
    dynamic.update(
        phase="update", pending_observation=observation, action_count=1, submission_count=1
    )
    with pytest.raises(models.ProtocolError, match="public_view.private_field"):
        public_view.make_state(frozen["context"], frozen["protocol"], dynamic)


def test_retained_original_objects_keep_content_identity(frozen: dict[str, Any]) -> None:
    source = deepcopy(frozen["source"])
    source["evidence"]["freight"]["value"] = "CHANGED_WITH_OLD_ID"
    with pytest.raises(models.ProtocolError, match="public_view.record_identity"):
        public_view.public_context(source, frozen["contract"])
