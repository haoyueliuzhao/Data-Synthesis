"""No-network tests: public-rule receiver, frozen admission, and one-call evidence."""

from __future__ import annotations

import copy
import json
import socket
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext import callbacks
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import (
    PublicQARuntime,
    evaluate_update_readonly,
)
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import (
    publish_update_contract,
    reference_update,
    rejection_feedback,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import transport
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import sha
from trusted_synthesis.experiments.finance_qa_vnext_update_calibration import plan, runner
from trusted_synthesis.experiments.finance_qa_vnext_update_calibration.controls import (
    check_public_rules,
    isolated_receiver,
    unchanged_validator,
)
from trusted_synthesis.experiments.finance_qa_vnext_update_calibration.evidence import (
    audit_call,
    summarize,
)
from trusted_synthesis.experiments.finance_qa_vnext_update_calibration.models import (
    configuration,
    record,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def no_network_or_runtime(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("calibration tests must not use sockets, credentials or Runtime execution")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(PublicQARuntime, "__init__", forbidden)
    monkeypatch.setattr(PublicQARuntime, "step", forbidden)
    monkeypatch.setattr(runner, "_credential", forbidden)


@pytest.fixture(scope="module")
def challenges():
    return plan.historical_challenges(ROOT)


def one(challenges, arm="R", index=0):
    challenge = challenges[index]
    condition = record("condition", test_only=True)
    reg = plan._registration(challenge, condition, arm, 0)
    original = challenge["original_request"]
    request = original if arm == "O" else publish_update_contract(original)
    http = transport.render_http_request(
        request, configuration(), session_id=reg["session_id"], attempt_index=0
    )
    return reg, request, http


def envelope(content, *, model="deepseek-v4-pro"):
    return canonical_json_bytes(
        {
            "id": "mock-provider-response",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content},
                }
            ],
            "usage": {"prompt_tokens": 200, "completion_tokens": 10, "total_tokens": 210},
        }
    )


class MockSender:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def send(self, request, *, api_key):
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_actual_selection_and_unchanged_parser_and_admission(challenges):
    assert [c["historical_update_turn"] for c in challenges] == [
        1,
        2,
        7,
        1,
        7,
        1,
        3,
        11,
        7,
        1,
        1,
        11,
    ]
    assert all(c["original_request"]["state"]["accepted_claims"] == [] for c in challenges)
    assert all(row["unchanged"] for row in unchanged_validator(ROOT)["checks"])


def test_all_four_shapes_public_controls(challenges, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("isolated controls may not call the old fixture helper")

    monkeypatch.setattr(callbacks, "update_response", forbidden)
    controls = check_public_rules(
        {c["label"]: publish_update_contract(c["original_request"]) for c in challenges}
    )
    assert controls["passed"] and len(controls["rows"]) >= 84
    assert (
        controls["provider_calls"]
        == controls["action_executions"]
        == controls["update_commits"]
        == 0
    )


@pytest.mark.parametrize("index", range(12))
@pytest.mark.parametrize("disposition", ["accept", "reject"])
def test_same_admission_both_arms_and_public_only_receivers(challenges, index, disposition):
    _, repaired, _ = one(challenges, index=index)
    original = challenges[index]["original_request"]
    before = canonical_json_bytes(original)
    assert {k: v for k, v in repaired.items() if k not in {"id", "public_update_contract"}} == {
        k: v for k, v in original.items() if k != "id"
    }
    response = isolated_receiver(repaired, disposition)
    assert response == reference_update(repaired, disposition) or (
        response["next_subgoal"] != reference_update(repaired, disposition)["next_subgoal"]
    )
    for request in (original, repaired):
        score = evaluate_update_readonly(canonical_json_bytes(response), request)
        assert score["update_admitted"] is True
        assert score["complete_accept"] is (disposition == "accept")
        assert score["new_claims"] == score["update_commits"] == score["action_executions"] == 0
    assert canonical_json_bytes(original) == before


def test_model_supplied_rules_cannot_weaken_actual_admission(challenges):
    _, request, _ = one(challenges)
    response = isolated_receiver(request, "accept")
    response["proposed_claim"] = None
    request["public_update_contract"]["rules"][5]["fields"]["/proposed_claim"] = {"literal": None}
    assert not evaluate_update_readonly(canonical_json_bytes(response), request)["complete_accept"]


@pytest.mark.parametrize("pending", [True, False])
def test_schema_feedback_is_update_scoped(challenges, pending):
    _, request, _ = one(challenges)
    if not pending:
        request["state"]["pending_observation"] = None
    feedback = rejection_feedback("submission.schema", request, None)
    assert feedback["code"] == "submission.schema" and feedback["admitted"] is False
    assert ("public_diagnostic" in feedback) is pending


def test_config_budget_and_overlong_request_are_not_silently_truncated(challenges):
    cfg = configuration()
    assert cfg.as_record()["maximum_pilot_reserved_tokens"] == 2580480
    assert cfg.as_record()["maximum_session_reserved_tokens"] == 107520
    _, request, http = one(challenges)
    assert http["body_byte_count"] <= 98304
    request["extra_text"] = "x" * 100000
    rendered = transport.render_http_request(request, cfg, session_id="local", attempt_index=0)
    assert rendered["body_byte_count"] > 98304
    assert rendered["body"]["messages"][1]["content"] == canonical_json_bytes(request).decode()


@pytest.mark.parametrize(
    "case", ["accept", "reject", "schema", "semantic", "timeout", "http", "empty", "model"]
)
@pytest.mark.parametrize("arm", ["O", "R"])
def test_one_attempt_raw_evidence_roundtrip(challenges, tmp_path, case, arm):
    reg, request, http = one(challenges, arm=arm)
    repaired = request if arm == "R" else publish_update_contract(request)
    response = isolated_receiver(repaired, "reject" if case == "reject" else "accept")
    if case == "semantic":
        response["proposed_claim"] = None
    content = "not JSON" if case == "schema" else canonical_json_bytes(response).decode()
    if case == "empty":
        content = None
    result = (
        transport.HTTPSendError("transport.timeout")
        if case == "timeout"
        else transport.HTTPResponse(
            503 if case == "http" else 200,
            envelope(content, model="different" if case == "model" else "deepseek-v4-pro"),
        )
    )
    sender = MockSender(result)
    callback = transport.OnlineModelCallback(
        configuration(),
        session_id=reg["session_id"],
        evidence_directory=tmp_path / "transport",
        sender=sender,
    )
    try:
        callback.generate(request)
    except transport.OnlineTransportError:
        pass
    callback.finalize()
    audit = audit_call(ROOT, tmp_path / "transport", reg, request, http, require_live=False)
    assert sender.calls == audit["provider_attempts"] == 1
    assert audit["evidence_complete"] and not audit["model_sample"]
    assert audit["Y"] is (case == "accept")
    with pytest.raises(ProtocolError, match="live_http_required"):
        audit_call(ROOT, tmp_path / "transport", reg, request, http)
    with pytest.raises(transport.OnlineTransportError):
        callback.generate(request)
    assert sender.calls == 1


def test_tampered_http_bytes_are_unknown_not_scored(challenges, tmp_path):
    reg, request, http = one(challenges)
    sender = MockSender(transport.HTTPResponse(200, envelope("{}")))
    callback = transport.OnlineModelCallback(
        configuration(),
        session_id=reg["session_id"],
        evidence_directory=tmp_path / "transport",
        sender=sender,
    )
    callback.generate(request)
    callback.finalize()
    path = tmp_path / "transport/attempts/000_http_response.body"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ProtocolError, match="member_bytes"):
        audit_call(ROOT, tmp_path / "transport", reg, request, http, require_live=False)


def population(challenges):
    condition = record("condition", test_only=True)
    regs = []
    for challenge in challenges:
        order = ["O", "R"] if challenge["round"] % 2 else ["R", "O"]
        regs.extend(
            plan._registration(challenge, condition, arm, pos) for pos, arm in enumerate(order)
        )
    return regs


def test_fixed_denominator_unknown_and_gate(challenges):
    regs = population(challenges)
    audits = {r["label"]: {"Y": r["arm"] == "R", "evidence_complete": True} for r in regs}
    summary = summarize(regs, audits)
    assert summary["overall"]["R"]["rate"] == summary["overall"]["delta_R_minus_O"] == 1
    assert summary["paired_cells"]["R_only"] == 12 and summary["engineering_gate_passed"]
    audits["C01_R"] = {"Y": None, "evidence_complete": False}
    summary = summarize(regs, audits)
    assert summary["overall"]["R"]["denominator"] == 12
    assert summary["overall"]["R"]["rate"] is None
    assert summary["overall"]["delta_R_minus_O"] is None
    assert not summary["engineering_gate_passed"]
    audits["C01_R"] = {"Y": False, "evidence_complete": True}
    audits["C02_R"] = {"Y": False, "evidence_complete": True}
    summary = summarize(regs, audits)
    assert summary["overall"]["R"]["successes"] == 10
    assert not summary["engineering_gate_passed"]  # C has only 2/4, not 3/4.


@pytest.mark.parametrize("failure", ["none", "known", "unknown"])
def test_actual_orchestration_fixed_pairs_no_retries(challenges, tmp_path, monkeypatch, failure):
    regs = population(challenges)
    prep = tmp_path / "preparation"
    prep.mkdir()
    for reg in regs:
        challenge = next(c for c in challenges if c["label"] == reg["pair_label"])
        request = challenge["original_request"]
        if reg["arm"] == "R":
            request = publish_update_contract(request)
        http = transport.render_http_request(
            request, configuration(), session_id=reg["session_id"], attempt_index=0
        )
        for folder, value in (("requests", request), ("http", http)):
            (prep / folder).mkdir(exist_ok=True)
            (prep / folder / (reg["label"] + ".json")).write_bytes(canonical_json_bytes(value))
    frozen = {
        "registrations": regs,
        "condition": {"id": "test-condition"},
        "implementation": {"id": "test-implementation"},
        "manifest": {"id": "test-preparation"},
    }
    monkeypatch.setattr(runner, "prepared", lambda root, directory: copy.deepcopy(frozen))
    monkeypatch.setattr(runner, "_credential", lambda path: "never-sent-test-placeholder")
    calls = []
    original_callback = runner.OnlineModelCallback

    def make_callback(config, **kwargs):
        session_id = kwargs["session_id"]
        reg = next(r for r in regs if r["session_id"] == session_id)

        class Sender:
            def send(self, http, *, api_key):
                calls.append(reg["label"])
                if failure == "known" and reg["label"] == "C01_O":
                    raise transport.HTTPSendError("transport.timeout")
                public = json.loads(http["messages"][1]["content"])
                if "public_update_contract" not in public:
                    public = publish_update_contract(public)
                return transport.HTTPResponse(
                    200,
                    envelope(canonical_json_bytes(isolated_receiver(public, "accept")).decode()),
                )

        return original_callback(config, **kwargs, sender=Sender())

    monkeypatch.setattr(runner, "OnlineModelCallback", make_callback)

    def local_audit(root, directory, reg, public, http):
        if failure == "unknown" and reg["label"] == "C01_O":
            raise ProtocolError("test.unknown_evidence")
        return audit_call(root, directory, reg, public, http, require_live=False)

    monkeypatch.setattr(runner, "audit_call", local_audit)
    report = runner.run(ROOT, prep)
    assert len(calls) == len(set(calls))
    assert len(calls) == (5 if failure == "unknown" else 24)
    if failure == "unknown":
        assert "C01_R" not in calls
        assert report["overall"]["R"]["denominator"] == 12
        assert report["overall"]["R"]["rate"] is None
    else:
        assert report["execution_evidence_complete"]
        assert report["overall"]["O"]["successes"] == (11 if failure == "known" else 12)
        assert report["overall"]["R"]["successes"] == 12
        for pair_label in {r["pair_label"] for r in regs}:
            pair = [r for r in regs if r["pair_label"] == pair_label]
            assert calls.index(pair[0]["label"]) < calls.index(pair[1]["label"])
    replay = runner.analyze(ROOT, prep, tmp_path / "reanalysis")
    assert replay == report
    assert sha((tmp_path / "execution/report.json").read_bytes()) == sha(
        (tmp_path / "reanalysis/report.json").read_bytes()
    )
    with pytest.raises(ProtocolError, match="no_resume_or_replacement"):
        runner.run(ROOT, prep)
