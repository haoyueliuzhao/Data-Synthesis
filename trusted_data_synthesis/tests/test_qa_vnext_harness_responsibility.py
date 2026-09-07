"""Only newly introduced responsibility/interface risks; all controls are zero-call."""

from __future__ import annotations

import copy
import json
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import public_program_answer
from trusted_synthesis.domains.finance.qa_vnext.protocol import record
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import public_share_answer
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import (
    audit_runtime,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.interface import (
    expand_acceptance,
    expand_selection,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.runtime import (
    StudyRuntime,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    HTTPResponse,
    HttpxSender,
    OnlineModelCallback,
    TransportConfig,
    render_http_request,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.plan import load_panel

ROOT = Path(__file__).resolve().parents[2]


class Mock:
    binding = record("callback_binding", origin="adapter_mock", online_calls=0)


@pytest.fixture(scope="module")
def panel():
    return load_panel(ROOT)


def runtime(tmp_path, panel, group="S", condition="H1", name="runtime"):
    return StudyRuntime(panel.adapter(group), group, condition, Mock(), tmp_path / name)


def step(r, body):
    return r.step(canonical_json_bytes(body))


def finish_and_audit(r):
    r.run()  # Already terminal: only seal local fixture artifacts, no callback.
    result = audit_runtime(r.base, r.group, r.condition, r.store.root)
    assert result["session"]["final"] is not None
    return result


def accept(r):
    q = r.request()
    body = (
        expand_acceptance(r.pending, "accept", q)
        if r.condition == "H0"
        else {
            "kind": "update",
            "state_id": q["response_state_id"],
            "observation": q["state"]["pending_observation"]["id"],
            "disposition": "accept",
        }
    )
    event = step(r, body)
    assert event["receipt"]["admitted"], event["receipt"]
    return event


def propose(r, op, keys, goal="a model chosen intermediate"):
    q = r.request()
    body = {
        "kind": "action",
        "state_id": q["response_state_id"],
        "subgoal": goal,
        "reason": "This operation establishes the selected intermediate from these inputs.",
        "operation": op,
        "inputs": keys,
        "parameters": {"method": "sum"} if op == "relation_sum" else {},
    }
    return step(r, body)


@pytest.mark.parametrize("group", ["S", "B"])
def test_h0_h1_exact_selected_action_and_explicit_acceptance(tmp_path, panel, group):
    r0 = runtime(tmp_path, panel, group, "H0", "h0")
    r1 = runtime(tmp_path, panel, group, "H1", "h1")
    q0, q1 = r0.request(), r1.request()
    assert q0["available_actions"] == r1.structured_request()["available_actions"]
    selected = q0["available_actions"][0]["id"]
    b0 = expand_selection(selected, q0)
    e0 = step(r0, b0)
    e1 = step(
        r1,
        {
            "kind": "action",
            "state_id": q1["response_state_id"],
            "action": r1.refs.forward[selected],
        },
    )
    assert e0["execution"]["selected_action"] == e1["execution"]["selected_action"]
    assert e0["execution"]["proposition"] == e1["execution"]["proposition"]
    assert not r0.claims and not r1.claims
    assert len(e1["parsed"]) == 3
    assert e1["language_binding"]["expanded"] == b0
    c0, c1 = accept(r0)["claim"], accept(r1)["claim"]
    assert c0["proposition"] == c1["proposition"]
    assert c0["obligation_id"] == c1["obligation_id"]


@pytest.mark.parametrize("group", ["S", "B"])
def test_h2_actual_http_payload_has_no_reference_plan(tmp_path, panel, group):
    r = runtime(tmp_path, panel, group, "H2")
    q = r.request()
    http = render_http_request(
        q,
        TransportConfig(system_prompt="Follow the declared protocol."),
        session_id="zero_call",
        attempt_index=0,
    )
    body = http["body_json"]
    for forbidden in (
        "program_skeleton",
        "projection_role_aliases",
        "task_pattern",
        "available_actions",
        "allowed_next_subgoals",
        "newly_enabled_obligation_ids",
        "topology_kind",
        "reference_program",
        "obligations",
    ):
        assert forbidden not in body
    assert not r.adapter.offers([])


@pytest.mark.parametrize("bad", ["C99", "C1 ", "O1", "other-task:claim", "E0"])
def test_future_pending_cross_task_and_fuzzy_refs_rejected(tmp_path, panel, bad):
    r = runtime(tmp_path, panel, "B", "H2")
    event = propose(r, "growth", ["E1", bad])
    assert not event["receipt"]["admitted"]
    assert r.actions == 0 and not r.claims


def test_explicit_whole_observation_is_required(tmp_path, panel):
    r = runtime(tmp_path, panel)
    q = r.request()
    step(
        r,
        {
            "kind": "action",
            "state_id": q["response_state_id"],
            "action": q["available_actions"][0]["id"],
        },
    )
    assert r.pending and not r.claims
    q = r.request()
    rejected = step(
        r, {"kind": "update", "state_id": q["response_state_id"], "disposition": "accept"}
    )
    assert not rejected["receipt"]["admitted"] and not r.claims
    accept(r)
    assert len(r.claims) == 1


def test_wrong_units_and_periods_are_not_legal_compositions(tmp_path, panel):
    r = runtime(tmp_path, panel, "B", "H2")
    for op, inputs in (
        ("signed_percentage_point_gap", ["E1", "E2"]),
        ("absolute_percentage_point_gap", ["E1"]),
        ("growth", ["E2", "E1"]),
        ("growth", ["E1", "E4"]),
    ):
        event = propose(r, op, inputs)
        assert not event["receipt"]["admitted"]
    assert r.actions == 0


@pytest.mark.parametrize("mixed_lookup,reverse", [(False, False), (False, True), (True, True)])
def test_h2_b_nonreference_compositions_execute_and_verify_final(
    tmp_path, panel, mixed_lookup, reverse
):
    r = runtime(tmp_path, panel, "B", "H2")
    first = "E1"
    if mixed_lookup:
        assert propose(r, "lookup", [first])["receipt"]["admitted"]
        accept(r)
        first = r.refs.add(r.claims[-1]["id"], "C")
    rates = []
    for pair in ([first, "E2"], ["E3", "E4"]):
        event = propose(r, "growth", pair)
        assert event["receipt"]["admitted"], event["receipt"]
        accept(r)
        rates.append(r.refs.add(r.claims[-1]["id"], "C"))
    if reverse:
        rates.reverse()
    assert propose(r, "signed_percentage_point_gap", rates)["receipt"]["admitted"]
    accept(r)
    gap = r.refs.add(r.claims[-1]["id"], "C")
    assert propose(r, "absolute_percentage_point_gap", [gap])["receipt"]["admitted"]
    accept(r)
    claim = r.claims[-1]
    q = r.request()
    body = {
        "kind": "final",
        "state_id": q["response_state_id"],
        "answer_claim_id": r.refs.forward[claim["id"]],
        "result": claim["proposition"]["output"],
        "citations": r.refs.render(claim["proposition"]["lineage"]),
    }
    wrong = copy.deepcopy(body)
    wrong["citations"] = wrong["citations"][:-1]
    assert not step(r, wrong)["receipt"]["admitted"]
    body["state_id"] = r.request()["response_state_id"]
    event = step(r, body)
    assert event["receipt"]["admitted"], event["receipt"]
    assert r.final["qa_validation"]["qa_valid"]
    assert r.actions == (5 if mixed_lookup else 4)  # Original B graph has eight Actions.
    assert finish_and_audit(r)["method"]["used_accepted_claim_ids"]


@pytest.mark.parametrize("reconstruct", [False, True])
def test_h2_share_actual_support_routes(tmp_path, panel, reconstruct):
    r = runtime(tmp_path, panel, "S", "H2")
    evidence = r.base.context["evidence"]

    def ref(name):
        return r.refs.forward[evidence[name]["id"]]

    denominator = ref("total")
    if reconstruct:
        event = propose(r, "relation_sum", [ref("other"), ref("freight"), ref("part_whole")])
        assert event["receipt"]["admitted"], event["receipt"]
        accept(r)
        denominator = r.refs.add(r.claims[-1]["id"], "C")
    assert propose(r, "share_ratio", [ref("freight"), denominator])["receipt"]["admitted"]
    accept(r)
    ratio = r.refs.add(r.claims[-1]["id"], "C")
    assert propose(r, "scale_percent", [ratio])["receipt"]["admitted"]
    accept(r)
    claim = r.claims[-1]
    q = r.request()
    event = step(
        r,
        {
            "kind": "final",
            "state_id": q["response_state_id"],
            "answer_claim_id": r.refs.forward[claim["id"]],
            "result": public_share_answer(r.base.context, claim),
            "citations": r.refs.render(claim["proposition"]["lineage"]),
        },
    )
    assert event["receipt"]["admitted"], event["receipt"]
    assert (evidence["total"]["id"] in claim["proposition"]["lineage"]) is not reconstruct
    finish_and_audit(r)


@pytest.mark.parametrize("transport_failure", [False, True])
def test_zero_wire_transport_audit_and_readonly_execution_guard(
    tmp_path, panel, monkeypatch, transport_failure
):
    """HTTP sender is mocked in this test process; never a formal model sample."""
    from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import (
        audit_transport,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.stage import (
        configuration,
    )

    calls = []

    def send_mock(sender, request, *, api_key):
        del sender, api_key
        calls.append(request["attempt_index"])
        if transport_failure:
            return HTTPResponse(503, b'{"error":"zero-wire fixture"}')
        q = json.loads(request["body"]["messages"][1]["content"])
        body = {"state_id": q["response_state_id"]}
        if q["state"]["pending_observation"]:
            body.update(
                kind="update",
                disposition="accept",
                observation=q["state"]["pending_observation"]["id"],
            )
        elif q["final_claim_ids"]:
            claim = next(
                c for c in q["state"]["accepted_claims"] if c["id"] == q["final_claim_ids"][0]
            )
            with localcontext() as numeric:
                numeric.prec, numeric.rounding = 50, ROUND_HALF_EVEN
                value = str(
                    Decimal(claim["proposition"]["output"]["value"]).quantize(Decimal("0.000001"))
                )
            body.update(
                kind="final",
                answer_claim_id=claim["id"],
                result={"value": value, "unit": "percent"},
                citations=claim["proposition"]["lineage"],
            )
        else:
            options = q["available_actions"]
            selected = next(
                (o for o in options if o["semantic_choice"] == "disclosed_total"), options[0]
            )
            body.update(kind="action", action=selected["id"])
        envelope = {
            "id": "zero-wire-fixture",
            "object": "chat.completion",
            "model": "deepseek-v4-pro",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(body)},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        return HTTPResponse(200, canonical_json_bytes(envelope))

    monkeypatch.setattr(HttpxSender, "send", send_mock)
    config = configuration()
    callback = OnlineModelCallback(
        config,
        session_id="ZERO_WIRE_FIXTURE_NOT_MODEL_POPULATION",
        evidence_directory=tmp_path / "transport",
        api_key=None,
    )
    r = StudyRuntime(panel.adapter("S"), "S", "H1", callback, tmp_path / "runtime")
    r.run()
    callback.finalize()
    expected_calls = 1 if transport_failure else 5
    assert calls == list(range(expected_calls))

    def forbidden(*args, **kwargs):
        raise AssertionError("readonly audit attempted execution or transport")

    monkeypatch.setattr(StudyRuntime, "run", forbidden)
    monkeypatch.setattr(StudyRuntime, "step", forbidden)
    monkeypatch.setattr(StudyRuntime, "_consume", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    for operation in ("relation_sum", "share_ratio", "scale_percent"):
        monkeypatch.setattr(type(r.base.registry.require(operation).executor), "execute", forbidden)
    measured = audit_runtime(r.base, "S", "H1", tmp_path / "runtime")
    transport = audit_transport(tmp_path / "transport", measured, config)
    assert transport["attempts"] == expected_calls
    assert (measured["session"]["final"] is None) is transport_failure
    assert transport["usage"]["total_tokens"]["total"] == (None if transport_failure else 150)


@pytest.mark.parametrize("group,condition", [(g, h) for g in ("S", "B") for h in ("H0", "H1")])
def test_common_final_full_structured_routes(tmp_path, panel, group, condition):
    r = runtime(tmp_path, panel, group, condition)
    while not r.adapter.final_claims(r.claims):
        q = r.request()
        if r.pending:
            accept(r)
        else:
            offer = r.structured_request()["available_actions"][0]
            body = (
                expand_selection(offer["id"], q)
                if condition == "H0"
                else {
                    "kind": "action",
                    "state_id": q["response_state_id"],
                    "action": r.refs.forward[offer["id"]],
                }
            )
            event = step(r, body)
            assert event["receipt"]["admitted"], event["receipt"]
    claim = r.claims[-1]
    answer = (
        public_share_answer(r.base.context, claim)
        if group == "S"
        else public_program_answer(r.base.context, r.claims)
    )
    q = r.request()
    body = {
        "kind": "final",
        "state_id": q["state"]["id"] if condition == "H0" else q["response_state_id"],
        "answer_claim_id": claim["id"],
        "result": answer,
        "citations": claim["proposition"]["lineage"],
    }
    if condition == "H1":
        body = r.refs.render(body)
    assert step(r, body)["receipt"]["admitted"]
    finish_and_audit(r)
