"""New instance wiring and raw compact representation only; zero Provider calls."""

import copy
import json
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import public_program_answer
from trusted_synthesis.domains.finance.qa_vnext.protocol import record
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import public_share_answer
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import (
    audit_runtime,
    no_plan,
    qualify,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.runtime import (
    StudyRuntime,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_transfer import representation
from trusted_synthesis.experiments.finance_qa_vnext_harness_transfer.panel import TASKS, Panel
from trusted_synthesis.experiments.finance_qa_vnext_harness_transfer.stage import (
    LABELS,
    configuration,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    HTTPResponse,
    HttpxSender,
    OnlineModelCallback,
    render_http_request,
)
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import (
    tokenization as assets,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def panel():
    return Panel(ROOT)


def make(panel, tmp_path, task, h):
    callback = type(
        "FixtureOnly", (), {"binding": record("callback_binding", origin="adapter_mock")}
    )()
    return StudyRuntime(panel.adapter(task), TASKS[task][0], h, callback, tmp_path / "runtime")


def step(r, body):
    body = {"state_id": r.request()["response_state_id"], **body}
    return r.step(canonical_json_bytes(body))


def accept(r):
    q = r.request()
    e = step(
        r,
        {
            "kind": "update",
            "observation": q["state"]["pending_observation"]["id"],
            "disposition": "accept",
        },
    )
    assert e["receipt"]["admitted"], e["receipt"]
    return r.refs.add(r.claims[-1]["id"], "C")


def action(r, op, refs):
    e = step(
        r,
        {
            "kind": "action",
            "subgoal": "user-chosen goal, not a reference node",
            "reason": "Use these selected inputs to establish this intermediate.",
            "operation": op,
            "inputs": refs,
            "parameters": {"method": "sum"} if op == "relation_sum" else {},
        },
    )
    assert e["receipt"]["admitted"], e["receipt"]
    return accept(r)


def final(r, expected):
    q = r.request()
    claim = r.claims[-1]
    body = {
        "kind": "final",
        "answer_claim_id": q["final_claim_ids"][-1],
        "result": expected,
        "citations": r.refs.render(claim["proposition"]["lineage"]),
    }
    wrong = copy.deepcopy(body)
    wrong["result"]["unit"] = "incorrect_unit"
    assert not step(r, wrong)["receipt"]["admitted"]
    assert step(r, body)["receipt"]["admitted"]
    r.run()
    return audit_runtime(r.base, r.group, r.condition, r.store.root)


@pytest.mark.parametrize("task,h", [(t, h) for t in TASKS for h in ("H1", "H2")])
def test_exact_instance_requests_and_no_h2_plan(panel, tmp_path, task, h):
    r = make(panel, tmp_path, task, h)
    request = r.request()
    body = render_http_request(request, configuration(), session_id="zero-call", attempt_index=0)
    assert body["body_byte_count"] <= 98304
    if h == "H2":
        no_plan(json.loads(body["body"]["messages"][1]["content"]))
        assert not r.adapter.offers([])
    else:
        assert request["available_actions"]
    assert len(LABELS) == 16 and configuration().maximum_pilot_attempts == 512


@pytest.mark.parametrize("task,route", [(t, route) for t in ("U16", "J15") for route in ("D", "R")])
def test_new_share_h2_both_actual_supports(panel, tmp_path, task, route):
    r = make(panel, tmp_path, task, "H2")
    evidence = r.base.source.evidence

    def ref(key):
        return r.refs.forward[evidence[key]["id"]]

    denominator = ref("disclosed_total")
    if route == "R":
        denominator = action(
            r,
            "relation_sum",
            [ref("other_component"), ref("target_component"), ref("composition_relation")],
        )
    ratio = action(r, "share_ratio", [ref("target_component"), denominator])
    action(r, "scale_percent", [ratio])
    audit = final(r, public_share_answer(r.base.context, r.claims[-1]))
    assert (evidence["disclosed_total"]["id"] in audit["method"]["answer_lineage"]) is (
        route == "D"
    )


@pytest.mark.parametrize(
    "task,mixed,reverse",
    [(t, m, v) for t in ("H24", "H13") for m, v in ((False, False), (True, True))],
)
def test_hii_direct_mixed_and_direction_preserve_original_semantics(
    panel, tmp_path, task, mixed, reverse
):
    r = make(panel, tmp_path, task, "H2")
    first = action(r, "lookup", ["E1"]) if mixed else "E1"
    c1 = action(r, "growth", [first, "E2"])
    c2 = action(r, "growth", ["E3", "E4"])
    if task == "H24":
        assert Decimal(r.claims[-2]["proposition"]["output"]["value"]) > 0
        assert Decimal(r.claims[-1]["proposition"]["output"]["value"]) < 0
    gap = action(r, "signed_percentage_point_gap", [c2, c1] if reverse else [c1, c2])
    action(r, "absolute_percentage_point_gap", [gap])
    expected = r.claims[-1]["proposition"]["output"]
    assert expected["value"] == panel.references[task]["absolute_growth_spread"]
    final(r, expected)


@pytest.mark.parametrize("task", list(TASKS))
def test_new_h1_complete_original_plan(panel, tmp_path, task):
    r = make(panel, tmp_path, task, "H1")
    while not r.adapter.final_claims(r.claims):
        q = r.request()
        if r.pending:
            accept(r)
        else:
            assert step(r, {"kind": "action", "action": q["available_actions"][0]["id"]})[
                "receipt"
            ]["admitted"]
    result = (
        public_share_answer(r.base.context, r.claims[-1])
        if r.group == "S"
        else public_program_answer(r.base.context, r.claims)
    )
    final(r, result)


@pytest.mark.parametrize("task", list(TASKS))
def test_new_bindings_invalid_alias_future_and_units(panel, tmp_path, task):
    r = make(panel, tmp_path, task, "H2")
    op = "share_ratio" if r.group == "S" else "growth"
    for refs in (["E1", "C99"], ["E1", "C1 "], ["E1", "foreign:claim"], ["E1", "O1"]):
        e = step(
            r,
            {
                "kind": "action",
                "subgoal": "test",
                "reason": "test",
                "operation": op,
                "inputs": refs,
                "parameters": {},
            },
        )
        assert not e["receipt"]["admitted"]
    if r.group == "B":
        for op, refs in (
            ("growth", ["E2", "E1"]),
            ("growth", ["E1", "E4"]),
            ("signed_percentage_point_gap", ["E1", "E2"]),
        ):
            e = step(
                r,
                {
                    "kind": "action",
                    "subgoal": "test",
                    "reason": "test",
                    "operation": op,
                    "inputs": refs,
                    "parameters": {},
                },
            )
            assert not e["receipt"]["admitted"]
    assert not r.claims and r.actions == 0


def test_compact_raw_export_and_existing_token_policy(panel, tmp_path, monkeypatch):
    def send(sender, request, *, api_key):
        del sender, api_key
        q = json.loads(request["body"]["messages"][1]["content"])
        response = {"state_id": q["response_state_id"]}
        if request["attempt_index"] == 0:
            response.update(kind="action", action="A999")
        elif q["state"]["pending_observation"]:
            response.update(
                kind="update",
                observation=q["state"]["pending_observation"]["id"],
                disposition="accept",
            )
        elif q["final_claim_ids"]:
            c = next(c for c in q["state"]["accepted_claims"] if c["id"] == q["final_claim_ids"][0])
            with localcontext() as numeric:
                numeric.prec = 50
                value = str(
                    Decimal(c["proposition"]["output"]["value"]).quantize(Decimal("0.000001"))
                )
            response.update(
                kind="final",
                answer_claim_id=c["id"],
                result={"value": value, "unit": "percent"},
                citations=c["proposition"]["lineage"],
            )
        else:
            response.update(kind="action", action=q["available_actions"][-1]["id"])
        return HTTPResponse(
            200,
            canonical_json_bytes(
                {
                    "id": "zero-wire-control",
                    "object": "chat.completion",
                    "model": "deepseek-v4-pro",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(response, indent=2),
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }
            ),
        )

    monkeypatch.setattr(HttpxSender, "send", send)
    child = DurableStore(tmp_path / "session")
    callback = OnlineModelCallback(
        configuration(),
        session_id="ZERO_WIRE_NOT_POPULATION",
        evidence_directory=child.root / "transport",
    )
    StudyRuntime(panel.adapter("U16"), "S", "H1", callback, child.root / "runtime").run()
    callback.finalize()
    q = qualify(panel.adapter("U16"), "S", "H1", child.root, configuration())
    assert q["status"] == "qualified", q
    child.json("qualification.json", q)
    seal_directory(child, kind="transfer_session_manifest")
    rows, excluded = representation.export_session(
        child.root,
        q,
        {
            "label": "U16_H1_01",
            "condition": "H1",
            "task_key": "U16",
            "task_id": panel.adapter("U16").context["task_id"],
        },
    )
    assert len(rows) == 5 and len(excluded) == 1
    assert rows[0]["turn_index"] == 1
    assert (
        json.loads(rows[0]["messages"][1]["content"])["state"]["last_feedback"]["admitted"] is False
    )
    binding = assets.register_tokenizer(ROOT)
    tokenizer = assets.load_tokenizer(binding)
    for row in rows:
        raw = (child.root / "runtime/turns" / f"{row['turn_index']:03d}_response.txt").read_bytes()
        assert row["target_text"].encode() == raw
        if row["submission_kind"] == "update":
            assert "proposed_claim" not in row["target_text"]
        token = representation.encode(row, binding, tokenizer, representation.policy(binding))
        assert (
            token["consumable_token_representation"] and token["maximum_sequence_length"] == 32768
        )
        assert all(token["boundary_checks"].values())


@pytest.mark.parametrize("status", ["known_failure", "unknown"])
def test_nonqualified_never_exports_positive_targets(tmp_path, status):
    rows, excluded = representation.export_session(
        tmp_path / "missing", {"status": status}, {"label": "not_a_model_sample"}
    )
    assert not rows and excluded[0]["reason"] == status
