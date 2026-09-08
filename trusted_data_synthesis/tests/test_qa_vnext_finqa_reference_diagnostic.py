"""Only new v2.1 online/replay wiring and event-denominator controls; zero Provider."""

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.controls import witness
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.reference_revision import (
    ReferenceExplicitRuntime,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.audit import (
    verify_session,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.metrics import (
    financial_trace,
    observation_diagnostics,
    verify_public_reference,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.stage import (
    LABELS,
    OLD_OUTPUT,
    configuration,
    run_one,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    HTTPResponse,
    HTTPSendError,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def panel():
    return Panel(ROOT)


class WitnessSender:
    def __init__(self, proof):
        self.proof, self.calls = proof, 0

    def send(self, request, *, api_key):
        turn = self.proof["events"][self.calls]
        public = json.loads(json.loads(request["body_json"])["messages"][1]["content"])
        assert public == turn["request"]
        verify_public_reference(public)
        self.calls += 1
        return HTTPResponse(
            200,
            json.dumps(
                {
                    "id": f"mock-{self.calls}",
                    "model": "deepseek-v4-pro",
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": turn["raw_response"],
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 200, "completion_tokens": 10, "total_tokens": 210},
                }
            ).encode(),
        )


@pytest.mark.parametrize("key,condition", [("C1", "E"), ("E1", "F")])
def test_actual_entry_http_exact_const_and_v21_raw_replay(panel, tmp_path, key, condition):
    registration = {
        "id": "wiring:" + key + condition,
        "task_key": key,
        "condition": condition,
        "label": f"{key}_{condition}_v21_mock",
    }
    runtime = ReferenceExplicitRuntime(panel, key, condition, registration["id"])
    sender = WitnessSender(witness(runtime))
    audit = run_one(panel, registration, tmp_path, configuration(), None, sender=sender)
    assert audit["complete_valid"] and not audit["model_origin_verified"]
    assert audit["runtime_version"] == "finqa_source_numeric_h2.v2.1"
    assert audit["observation_diagnostics"]["summary"]["reference_rejections"] == 0
    assert audit["observation_diagnostics"]["summary"]["first_legal_accept"] == audit["actions"]
    directory = tmp_path / registration["label"]
    assert verify_session(panel, registration, directory, model_required=False) == audit
    with pytest.raises(ValueError, match="audit.model_origin"):
        verify_session(panel, registration, directory)


def trace(panel, key="C1"):
    return ReferenceExplicitRuntime(panel, key, "E", "measure-control"), [], []


def submit(runtime, requests, events, **fields):
    request = runtime.request()
    requests.append(request)
    raw = json.dumps({"state_id": request["state"]["id"], **fields}).encode()
    events.append(runtime.transition(raw, request))
    return events[-1]


def read_source(runtime, requests, events):
    return submit(
        runtime,
        requests,
        events,
        kind="action",
        operation="read",
        inputs=[runtime.task["selected"][0]],
        parameters={},
        subgoal="offline",
        reason="Read source.",
    )


def result(runtime, status="budget_exhausted"):
    return {
        "actions": runtime.actions,
        "status": status,
        "final_state": runtime.request()["state"],
        "termination": None,
    }


@pytest.mark.parametrize("disposition", ["accept", "reject"])
def test_first_legal_update_allows_either_judgment(panel, disposition):
    r, requests, events = trace(panel)
    read_source(r, requests, events)
    submit(r, requests, events, kind="update", observation=r.pending["id"], disposition=disposition)
    m = observation_diagnostics(events, requests, result(r))
    assert m["summary"]["first_legal_" + disposition] == 1
    assert m["summary"]["first_legal_update_rate_among_observed"] == 1.0
    assert m["events"][0]["resolution"] == disposition


def test_reference_runs_interrupt_and_final_reject_recovery(panel):
    r, requests, events = trace(panel)
    read_source(r, requests, events)
    for _ in range(2):
        submit(r, requests, events, kind="update", observation="prose", disposition="accept")
    submit(r, requests, events, kind="bad")
    submit(r, requests, events, kind="update", observation="prose", disposition="accept")
    submit(r, requests, events, kind="update", observation=r.pending["id"], disposition="reject")
    m = observation_diagnostics(events, requests, result(r))
    row = m["events"][0]
    assert row["reference_rejection_runs"] == [[2, 3], [5]]
    assert row["resolution"] == "reject" and row["resolved_at_submission"] == 6
    assert m["summary"]["first_illegal"] == 1
    assert m["summary"]["maximum_consecutive_reference_rejections"] == 2


@pytest.mark.parametrize("status", ["budget_exhausted", "unknown"])
def test_no_following_model_decision_retained(panel, status):
    r, requests, events = trace(panel)
    read_source(r, requests, events)
    m = observation_diagnostics(events, requests, result(r, status))
    assert m["summary"]["total_observations"] == m["summary"]["no_following_submission"] == 1
    assert m["summary"]["first_legal_update_rate_among_observed"] is None
    assert m["events"][0]["budget_exhausted_on_pending"] == (status == "budget_exhausted")


def test_observation_created_at_submission_32_is_not_first_illegal(panel):
    r, requests, events = trace(panel)
    for _ in range(31):
        submit(r, requests, events, kind="bad")
    read_source(r, requests, events)
    m = observation_diagnostics(events, requests, result(r))
    assert m["events"][0]["created_at_submission"] == 32
    assert m["summary"]["no_following_submission"] == 1
    assert m["summary"]["first_illegal"] == 0


def test_zero_observations_retains_zero_event_denominator(panel):
    r, requests, events = trace(panel)
    submit(r, requests, events, kind="bad")
    m = observation_diagnostics(events, requests, result(r))
    assert m["summary"]["total_observations"] == 0
    assert m["summary"]["first_legal_update_rate_among_observed"] is None


def test_transport_no_response_is_not_synthetic_model_submission(panel, tmp_path):
    class FailSender:
        def send(self, request, *, api_key):
            raise HTTPSendError("transport.timeout")

    registration = {"id": "transport-fail", "task_key": "C1", "condition": "E", "label": "fail"}
    audit = run_one(panel, registration, tmp_path, configuration(), None, sender=FailSender())
    assert audit["status"] == "unknown" and audit["denominator"] == 1
    assert audit["provider_attempts"] == 1 and audit["submissions"] == 0
    assert audit["usage"]["total_tokens"]["total"] is None


@pytest.mark.parametrize("key", ["E1", "M3", "J1", "J2"])
def test_read_only_is_not_reached_and_no_automatic_financial_error(panel, key):
    r, requests, events = trace(panel, key)
    read_source(r, requests, events)
    f = financial_trace(events, requests, result(r), r.task)
    assert f["inspection_status"] == "NOT_REACHED"
    assert not f["substantive_error_automatically_inferred"]


def test_same_frozen_configuration_new_full_population():
    previous = json.loads((ROOT / OLD_OUTPUT / "preparation/configuration.json").read_bytes())
    assert previous == configuration().as_record()
    assert len(LABELS) == len(set(LABELS)) == 24
    assert all(label.endswith("_v21_01") for label in LABELS)
