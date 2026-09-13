"""New-purpose public execution and HTTP controls, never authentic Teacher samples."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from test_qa_vnext_catalog_bridge_worker import fixture

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.assessment import (
    assess_replayed_session,
)
from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.controls import (
    script_for_witness,
)
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import (
    training_runtime as original,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import runtime, transport
from trusted_synthesis.experiments.finance_qa_vnext_probe_coverage import protocol as prior
from trusted_synthesis.experiments.finance_qa_vnext_probe_coverage import runtime as prior_runtime


def registration(f, *, basis="endpoint", role="train", pool="A"):
    profile = p.CONTROL_PROFILE if basis == "neutral" else p.TARGET_PROFILE
    return p.record(
        "session_registration",
        session_id="synthetic_session",
        task_id=f["identity"]["task_id"],
        family=f["identity"]["family"],
        identity=f["identity"],
        quantity=f["bundle"]["private"]["canonical_target"]["quantity"],
        pool=pool,
        role=role,
        basis=basis,
        profile=profile,
        replicate=0,
        ordinal=0,
        system_prompt_sha256=p.sha(p.system_prompt(profile, basis)),
    )


def scripted(queue):
    return lambda *_: value if isinstance(value := next(queue), str) else p.encode(value).decode()


@pytest.mark.parametrize("basis", ("endpoint", "movement"))
@pytest.mark.parametrize("actual", ("endpoint", "movement"))
@pytest.mark.parametrize("quantity", ("difference", "relative_change"))
def test_new_targets_retain_P2_exact_public_history_and_actual_method(basis, actual, quantity):
    f = fixture("annual_flow", quantity)
    reg = registration(f, basis=basis)
    choices = script_for_witness(f["bundle"], f["native_bindings"], actual)
    current = runtime.generate(
        f["messages"], f["identity"], registered=reg, provider=scripted(iter(choices))
    )
    old = prior_runtime.generate(
        f["messages"], f["identity"], registered=reg, provider=scripted(iter(choices))
    )
    assert runtime.replay(current) == current
    assert current["initial_messages"] == old["initial_messages"]
    assert current["events"] == old["events"]
    assert [x["input_messages"] for x in current["turns"]] == [
        x["input_messages"] for x in old["turns"]
    ]
    q = assess_replayed_session(current, f["bundle"], f["native_bindings"])
    assert q["financial_valid"] and q["actual_method"] == actual
    assert current["training_eligible"] is False


def test_control_neutral_keeps_delivery_without_route_guidance():
    system = p.system_prompt(p.CONTROL_PROFILE, "neutral")
    assert system == original.SYSTEM + "\n\n" + prior.DELIVERY
    assert all(x not in system for x in prior.ADOPTION.values())
    f = fixture("control", "difference")
    choices = script_for_witness(f["bundle"], f["native_bindings"], "control")
    s = runtime.generate(
        f["messages"],
        f["identity"],
        registered=registration(f, basis="neutral"),
        provider=scripted(iter(choices)),
    )
    assert runtime.replay(s) == s
    q = assess_replayed_session(s, f["bundle"], f["native_bindings"])
    assert q["financial_valid"] and q["actual_method"] == "control"


@pytest.mark.parametrize(
    "profile,basis",
    [
        (p.TARGET_PROFILE, "neutral"),
        (p.CONTROL_PROFILE, "endpoint"),
        (p.CONTROL_PROFILE, "movement"),
        ("P3", "movement"),
    ],
)
def test_no_unregistered_generation_protocol(profile, basis):
    with pytest.raises(ValueError):
        p.system_prompt(profile, basis)


def test_first_final_stops_even_malformed_and_replay_preserves_errors():
    f = fixture()
    s = runtime.generate(
        f["messages"],
        f["identity"],
        registered=registration(f),
        provider=lambda *_: '{"final":"invalid"}',
    )
    assert s["provider_calls"] == 1 and s["first_final_index"] == 0
    assert runtime.replay(s) == s
    choices = ["not JSON", {"tool": "calculate", "arguments": {}}] + script_for_witness(
        f["bundle"], f["native_bindings"], "endpoint"
    )
    s = runtime.generate(
        f["messages"], f["identity"], registered=registration(f), provider=scripted(iter(choices))
    )
    assert s["events"][0]["protocol_error"] and s["events"][1]["tool_call"]["status"] == "error"
    assert runtime.replay(s) == s


def test_parallel_protocols_do_not_mutate_original_globals():
    before = original.SYSTEM
    choices = [
        (p.TARGET_PROFILE, "endpoint"),
        (p.TARGET_PROFILE, "movement"),
        (p.CONTROL_PROFILE, "neutral"),
    ] * 12
    with ThreadPoolExecutor(max_workers=12) as pool:
        values = list(pool.map(lambda x: p.system_prompt(*x), choices))
    assert values == [p.system_prompt(*x) for x in choices]
    assert original.SYSTEM == before


class Ledger:
    freeze_id = "synthetic_freeze"

    def __init__(self, reg):
        self.reg, self.rows, self.stops = reg, [], []

    def registered(self, sid):
        assert sid == self.reg["session_id"]
        return copy.deepcopy(self.reg)

    def reserve(self, sid):
        row = {
            "request_id": "synthetic_request",
            "session_id": sid,
            "attempt": 1,
            "input_reservation": p.INPUT_ALLOWANCE,
            "output_cap": p.OUTPUT_ALLOWANCE,
            "reserved_tokens": p.REQUEST_RESERVATION,
        }
        self.rows.append({**row, "state": "reserved", "charged_tokens": p.REQUEST_RESERVATION})
        return row

    def mark_sent(self, rid):
        assert self.rows[-1]["request_id"] == rid
        self.rows[-1]["state"] = "sent"

    def settle(self, rid, *, usage, http_success, response_model, outcome):
        known = isinstance(usage, dict) and all(
            type(usage.get(k)) is int
            for k in ("prompt_tokens", "completion_tokens", "total_tokens")
        )
        self.rows[-1].update(
            state="settled" if known else "usage_unknown",
            http_success=int(http_success),
            response_model=response_model,
            outcome=outcome,
        )
        if known:
            self.rows[-1].update(
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                reported_total_tokens=usage["total_tokens"],
                charged_tokens=usage["total_tokens"],
            )
        return known

    def halt(self, reason):
        self.stops.append(reason)

    def cancel_unsent(self, rid, reason):
        assert self.rows[-1]["request_id"] == rid and self.rows[-1]["state"] == "reserved"
        self.rows[-1].update(state="not_sent", charged_tokens=0)
        return p.record("unsent_reservation_cancellation", request_id=rid, reason=reason)

    def requests(self, sid):
        return copy.deepcopy(self.rows)


class Sender:
    def __init__(self, content, *, model=p.MODEL, usage=None, status=200):
        self.content, self.model, self.usage, self.status = content, model, usage, status
        self.calls = 0

    def send(self, request, *, api_key):
        self.calls += 1
        body = {
            "model": self.model,
            "usage": self.usage,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": self.content,
                        "reasoning_content": "synthetic private text must not be stored",
                    },
                }
            ],
        }
        return SimpleNamespace(status_code=self.status, complete=True, body=p.encode(body))


@pytest.mark.parametrize(
    "content,model,usage,status",
    [
        (
            '{"final":{}}',
            p.MODEL,
            {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            200,
        ),
        ("", p.MODEL, {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}, 200),
        (None, p.MODEL, {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}, 200),
        (
            '{"final":{}}',
            "wrong-model",
            {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            200,
        ),
        ('{"final":{}}', p.MODEL, None, 200),
        ("", p.MODEL, None, 401),
    ],
)
def test_new_transport_retains_usage_failures_and_refuses_synthetic_origin(
    tmp_path, content, model, usage, status
):
    f = fixture()
    reg = registration(f)
    ledger = Ledger(reg)
    sender = Sender(content, model=model, usage=usage, status=status)
    provider = transport.Provider(ledger, reg, tmp_path, "synthetic_credential", sender=sender)
    session = runtime.generate(f["messages"], f["identity"], registered=reg, provider=provider)
    assert sender.calls == 1 and len(ledger.rows) == 1
    assert runtime.replay(session) == session
    for path in tmp_path.rglob("*.json"):
        assert b"synthetic private text must not be stored" not in path.read_bytes()
    if session["turns"]:
        with pytest.raises(ValueError, match="authentic_exact_request_response_chain"):
            transport.verify_origin(session, ledger, tmp_path)
    else:
        assert session["first_final_index"] is None
    if usage and status == 200:
        assert ledger.rows[0]["charged_tokens"] == 3
    else:
        assert ledger.rows[0]["charged_tokens"] == p.REQUEST_RESERVATION
    if content in ("", None) and status == 200:
        value = json.loads((tmp_path / "synthetic_request" / "public_response.json").read_bytes())
        assert not value["original_public_content_nonempty"]
    if status == 401 or model != p.MODEL or usage is None:
        assert session["global_fatal"]


def test_wire_caps_admit_before_budget_and_keep_same_model_parameters():
    messages = [
        {"role": "system", "content": p.system_prompt(p.TARGET_PROFILE, "movement")},
        {"role": "user", "content": "json"},
    ]
    assert transport.render(messages) == __import__(
        "trusted_synthesis.experiments.finance_qa_vnext_probe_coverage.transport",
        fromlist=["render"],
    ).render(messages)
    with pytest.raises(ValueError):
        transport.render([{"role": "user", "content": "x" * p.MAX_BODY_BYTES}])


@pytest.mark.parametrize("where", ["persistence", "mark_sent"])
def test_fail_before_sender_cancels_only_unsent_lease(tmp_path, monkeypatch, where):
    f = fixture()
    reg = registration(f)
    ledger = Ledger(reg)
    sender = Sender('{"final":{}}')
    provider = transport.Provider(ledger, reg, tmp_path, "synthetic_credential", sender=sender)
    write = p.write_once

    def fail(*_):
        raise OSError("synthetic pre-send failure")

    def maybe_write(path, value):
        if path.name == "request.json":
            fail()
        return write(path, value)

    if where == "persistence":
        monkeypatch.setattr(p, "write_once", maybe_write)
    else:
        monkeypatch.setattr(ledger, "mark_sent", fail)
    session = runtime.generate(f["messages"], f["identity"], registered=reg, provider=provider)
    assert sender.calls == 0 and ledger.rows[0]["state"] == "not_sent"
    assert ledger.rows[0]["charged_tokens"] == 0
    assert ledger.rows[0]["reserved_tokens"] == p.REQUEST_RESERVATION
    assert session["global_fatal"] and session["first_final_index"] is None
    assert runtime.replay(session) == session
