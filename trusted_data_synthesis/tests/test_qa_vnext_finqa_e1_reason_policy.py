"""New reason-contract/layer wiring controls only; no historical response replay."""

import ast
import copy
import inspect
import json
import textwrap
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.runtime import (
    Runtime as OriginalRuntime,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.runtime import (
    REVIEW_KEY,
    REVIEW_TEXT,
    TARGET_ERROR,
    FinalRecoveryRuntime,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.audit import verify_session
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.closeout import collect
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.metrics import (
    action_layers,
    aggregate,
    recovery_trace,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.runtime import (
    ReasonPolicyRuntime,
    action_schema,
    verify_reason_policy,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.stage import (
    LABELS,
    OLD_OUTPUT,
    configuration,
    registrations,
    run_one,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    HTTPResponse,
    HTTPSendError,
)

ROOT = Path(__file__).resolve().parents[2]
LONG = "Constructed local reason. " * 50


@pytest.fixture(scope="module")
def panel():
    return Panel(ROOT)


class Trace:
    def __init__(self, panel, policy="P", sid="offline", h="E"):
        self.runtime = ReasonPolicyRuntime(panel, "E1", h, sid, expression_condition=policy)
        self.requests, self.raws, self.events = [], [], []

    def send_raw(self, raw):
        request = self.runtime.request()
        event = self.runtime.transition(raw, request)
        self.requests.append(request)
        self.raws.append(raw)
        self.events.append(event)
        return event

    def send(self, **fields):
        raw = json.dumps({"state_id": self.runtime.request()["state"]["id"], **fields}).encode()
        return self.send_raw(raw)

    def action(self, operation, inputs, reason="Local control.", accept=True):
        event = self.send(
            kind="action",
            operation=operation,
            inputs=inputs,
            reason=reason,
            subgoal="local control",
            parameters={},
        )
        if not event["admitted"]:
            return event
        if not accept:
            return event["observation"]
        event = self.send(
            kind="update", observation=self.runtime.pending["id"], disposition="accept"
        )
        assert event["admitted"]
        return event["claim"]

    def final(self, claim, value=None):
        return self.send(
            kind="final",
            answer_claim=claim["id"],
            result={"value": value or claim["value"], "unit": "percent"},
            citations=claim["lineage"],
        )

    def wrong(self):
        numerator, denominator = self.runtime.task["target"]["args"][0]["args"]
        n = self.action("read", [numerator])
        d = self.action("read", [denominator["args"][0]])
        ratio = self.action("divide", [n["id"], d["id"]])
        wrong = self.action("multiply", [ratio["id"], "constant:100"])
        assert self.final(wrong)["error"] == TARGET_ERROR
        return n, d, wrong

    def scale_inputs(self, method, n, d, wrong):
        if method == "denominator":
            return "divide", [d["id"], "constant:1000"]
        if method == "numerator":
            return "multiply", [n["id"], "constant:1000"]
        return "multiply", [wrong["id"], "constant:1000"]

    def recover(self, method, n, d, wrong, reason="Local control.", final=True):
        op, inputs = self.scale_inputs(method, n, d, wrong)
        scaled = self.action(op, inputs, reason=reason)
        if method == "denominator":
            ratio = self.action("divide", [n["id"], scaled["id"]])
            answer = self.action("multiply", [ratio["id"], "constant:100"])
        elif method == "numerator":
            ratio = self.action("divide", [scaled["id"], d["id"]])
            answer = self.action("multiply", [ratio["id"], "constant:100"])
        else:
            answer = scaled
        if final:
            assert self.final(answer)["admitted"]
        return answer

    def measure(self):
        result = {"terminal": self.runtime.terminal}
        recovery = recovery_trace(self.events, self.requests, result, self.runtime.task)
        layers = action_layers(
            self.events,
            self.requests,
            self.raws,
            self.runtime.task,
            self.runtime.expression_condition,
            recovery,
        )
        return recovery, layers


class Sender:
    def __init__(self, trace):
        self.trace, self.calls = trace, 0

    def send(self, request, *, api_key):
        body = json.loads(request["body_json"])
        assert json.loads(body["messages"][1]["content"]) == self.trace.requests[self.calls]
        content = self.trace.raws[self.calls].decode()
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
                            "message": {"role": "assistant", "content": content},
                        }
                    ],
                    "usage": {"prompt_tokens": 200, "completion_tokens": 10, "total_tokens": 210},
                }
            ).encode(),
        )


def registration(policy, label="mock", h="F"):
    return {
        "id": label,
        "label": label,
        "task_key": "E1",
        "condition": h,
        "feedback_condition": "R",
        "expression_condition": policy,
        "replicate": 1,
    }


def test_original_transition_body_changes_only_parser_seam():
    old = ast.parse(textwrap.dedent(inspect.getsource(OriginalRuntime.transition)))
    new = ast.parse(textwrap.dedent(inspect.getsource(ReasonPolicyRuntime.transition)))
    changes = 0
    for node in ast.walk(new):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "parse"
        ):
            assert len(node.args) == 2
            node.args = node.args[:1]
            changes += 1
    assert changes == 1
    assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False)


def test_C_exact_previous_R_and_P_only_declared_public_contract_delta(panel):
    c = Trace(panel, "C", "same")
    p = Trace(panel, "P", "same")
    old = FinalRecoveryRuntime(panel, "E1", "E", "same", feedback_condition="R")
    assert c.runtime.request() == old.request()
    cs, ps = c.runtime.request(), p.runtime.request()
    verify_reason_policy(cs, "C")
    verify_reason_policy(ps, "P")
    patched = copy.deepcopy(ps["response_schemas"]["action"])
    patched["properties"]["reason"]["maxLength"] = 480
    assert patched == cs["response_schemas"]["action"]
    assert ps["context"] == cs["context"]
    assert ps["response_schemas"]["final"] == cs["response_schemas"]["final"]
    assert ps["response_schemas"]["update"] == cs["response_schemas"]["update"]
    assert REVIEW_KEY not in cs["rules"] and REVIEW_KEY not in ps["rules"]
    c.wrong()
    for request, raw, event in zip(c.requests, c.raws, c.events, strict=True):
        assert old.request() == request
        assert old.transition(raw, request) == event
    assert old.request() == c.runtime.request()
    p.wrong()
    assert (
        c.runtime.request()["rules"][REVIEW_KEY]
        == p.runtime.request()["rules"][REVIEW_KEY]
        == REVIEW_TEXT
    )


@pytest.mark.parametrize("policy", ["C", "P"])
@pytest.mark.parametrize("length", [1, 480, 481, 4001])
def test_length_boundary_actual_parser_and_original_reason_preserved(panel, policy, length):
    t = Trace(panel, policy)
    source = t.runtime.task["target"]["args"][0]["args"][0]
    reason = "x" * length
    event = t.send(
        kind="action",
        operation="read",
        inputs=[source],
        reason=reason,
        subgoal="local",
        parameters={},
    )
    expected = policy == "P" or length <= 480
    assert event["admitted"] == expected
    if expected:
        assert event["model_submission"]["reason"] == reason
        assert event["observation"]["model_action"]["reason"] == reason
        assert event["observation"]["expression"] == source
        assert event["model_submission"]["inputs"] == [source]
    else:
        assert event["error"] == "schema.invalid_submission"
        assert event["model_submission"] is None and event["observation"] is None
    _, m = t.measure()
    row = m["events"][0]
    assert row["raw_action_shaped"]
    assert (
        row["schema_valid_action"]
        == row["semantic_admitted_action"]
        == row["actual_execution"]
        == expected
    )
    assert row["reason_characters"] == length


@pytest.mark.parametrize("policy", ["C", "P"])
@pytest.mark.parametrize(
    "defect",
    [
        "empty_reason",
        "numeric_reason",
        "long_subgoal",
        "wrong_state",
        "raw_source_arithmetic",
        "bad_source",
        "extra_field",
    ],
)
def test_only_reason_upper_bound_changes_other_contracts_remain(panel, policy, defect):
    t = Trace(panel, policy)
    source = t.runtime.task["target"]["args"][0]["args"][0]
    fields = {
        "kind": "action",
        "operation": "read",
        "inputs": [source],
        "reason": "Local.",
        "subgoal": "local",
        "parameters": {},
    }
    if defect == "empty_reason":
        fields["reason"] = ""
    elif defect == "numeric_reason":
        fields["reason"] = 1
    elif defect == "long_subgoal":
        fields["subgoal"] = "x" * 241
    elif defect == "wrong_state":
        fields["state_id"] = "wrong"
    elif defect == "raw_source_arithmetic":
        fields.update(operation="divide", inputs=[source, "constant:1000"])
    elif defect == "bad_source":
        fields["inputs"] = ["source:missing"]
    else:
        fields["extra"] = "not allowed"
    e = t.send(**fields)
    assert not e["admitted"] and e["observation"] is None and t.runtime.actions == 0
    _, layers = t.measure()
    assert layers["summary"]["raw_action_shaped"] == 1
    assert layers["summary"]["actual_executions"] == 0


@pytest.mark.parametrize("policy", ["C", "P"])
@pytest.mark.parametrize(
    "raw",
    [
        b'{"kind":"action","operation":"read",broken}',
        b'{"kind":"action","kind":"final"}',
        b'{"kind":"action","parameters":{"bad":NaN}}',
        b"[]",
    ],
)
def test_invalid_or_ambiguous_json_not_salvaged(panel, policy, raw):
    t = Trace(panel, policy)
    e = t.send_raw(raw)
    assert not e["admitted"] and e["model_submission"] is None
    _, layers = t.measure()
    assert not layers["events"][0]["valid_unambiguous_json_object"]
    assert layers["summary"]["raw_action_shaped"] == layers["summary"]["actual_executions"] == 0


@pytest.mark.parametrize("policy", ["C", "P"])
def test_unaccepted_observation_and_wrong_update_reference_still_rejected(panel, policy):
    t = Trace(panel, policy)
    source = t.runtime.task["target"]["args"][0]["args"][0]
    obs = t.action("read", [source], accept=False)
    assert (
        t.send(kind="update", observation="wrong", disposition="accept")["error"]
        == "lifecycle.observation_binding"
    )
    assert t.send(kind="update", observation=obs["id"], disposition="reject")["admitted"]
    e = t.send(
        kind="action",
        operation="divide",
        inputs=[obs["id"], "constant:1000"],
        reason="Local.",
        subgoal="local",
        parameters={},
    )
    assert e["error"] == "lifecycle.accepted_claim_input_only"
    assert not t.runtime.claims


@pytest.mark.parametrize("policy", ["C", "P"])
@pytest.mark.parametrize("method", ["denominator", "numerator", "existing_percent"])
def test_mock_http_complete_recovery_and_layered_long_proposals(panel, tmp_path, policy, method):
    reg = registration(policy, policy + method)
    t = Trace(panel, policy, reg["id"], reg["condition"])
    n, d, wrong = t.wrong()
    if policy == "C":
        op, inputs = t.scale_inputs(method, n, d, wrong)
        rejected = t.action(op, inputs, reason=LONG)
        assert rejected["error"] == "schema.invalid_submission"
        t.recover(method, n, d, wrong)
    else:
        t.recover(method, n, d, wrong, reason=LONG)
    audit = run_one(panel, reg, tmp_path, configuration(), None, sender=Sender(t))
    assert audit["complete_valid"] and not audit["model_origin_verified"]
    assert audit["recovery_trace"]["fresh_dependency_recovery_witness"]
    assert audit["recovery_trace"]["remaining_after_first_target_rejection"] == {
        "actions": 8,
        "submissions": 23,
    }
    layer = audit["action_layers"]
    assert layer["first_post_trigger_by_layer"]["raw_action_shaped"] == 10
    assert layer["first_post_trigger_by_layer"]["schema_valid_action"] == (
        11 if policy == "C" else 10
    )
    long = next(r for r in layer["events"] if r["reason_over_480"])
    assert long["proposed_core_alignment_probes"]
    assert long["actual_execution"] == (policy == "P")
    if policy == "P":
        assert long["observation_resolution"] == "accept" and long["consumed_by_valid_final"]
    assert verify_session(panel, reg, tmp_path / reg["label"], model_required=False) == audit
    with pytest.raises(ValueError, match="audit.model_origin"):
        verify_session(panel, reg, tmp_path / reg["label"])
    with pytest.raises(ValueError, match="audit.transition_replay"):
        verify_session(
            panel,
            {**reg, "expression_condition": "P" if policy == "C" else "C"},
            tmp_path / reg["label"],
            model_required=False,
        )


def test_new_scale_accepted_and_used_in_arithmetic_but_old_final_not_recovery(panel):
    t = Trace(panel)
    n, d, wrong = t.wrong()
    t.recover("denominator", n, d, wrong, reason=LONG, final=False)
    assert t.final(wrong)["error"] == TARGET_ERROR
    recovery, layers = t.measure()
    assert recovery["recovery_status"] == "NOT_COMPLETED"
    assert layers["summary"]["aligned_accepted_observations"] == 3
    assert layers["summary"]["aligned_observations_with_later_action_consumer"] == 2
    assert layers["summary"]["aligned_consumed_by_valid_final"] == 0


def test_P_direct_success_recovery_NA_and_closeout_layers_bytes(panel, tmp_path):
    reg = registration("P", "direct", "E")
    t = Trace(panel, "P", reg["id"], "E")
    numerator, denominator = t.runtime.task["target"]["args"][0]["args"]
    n, d = t.action("read", [numerator]), t.action("read", [denominator["args"][0]])
    t.recover("denominator", n, d, None, reason=LONG)
    audit = run_one(panel, reg, tmp_path, configuration(), None, sender=Sender(t))
    assert (
        audit["complete_valid"] and audit["recovery_trace"]["recovery_status"] == "NOT_APPLICABLE"
    )
    assert aggregate([audit])["recovery_not_applicable"] == 1
    assert aggregate([audit])["complete_recoveries"] == 0
    review = {
        key: "local mock"
        for key in (
            "first_error",
            "executed_adjustment",
            "acceptance_and_consumption",
            "terminal_point",
            "interpretation_and_limits",
            "reason_contract_layers",
        )
    }
    review["evidence_submissions"] = [1, audit["submissions"]]
    report = collect(panel, [reg], tmp_path, [audit], {reg["label"]: review}, model_required=False)
    assert report["total"] == aggregate([audit])
    assert (
        report["http_bytes"]["request_body_bytes"] > 0
        and report["http_bytes"]["response_body_bytes"] > 0
    )


def test_P_global_request_budget_still_stops_no_second_provider_attempt(panel, tmp_path):
    reg = registration("P", "resource", "E")
    t = Trace(panel, "P", reg["id"], "E")
    source = t.runtime.task["target"]["args"][0]["args"][0]
    # Deliberately artificial oversized mock, not a sampled model output or token estimate.
    t.action("read", [source], reason="x" * 120000, accept=False)
    sender = Sender(t)
    audit = run_one(panel, reg, tmp_path, configuration(), None, sender=sender)
    assert (
        sender.calls == audit["provider_attempts"] == audit["submissions"] == audit["actions"] == 1
    )
    assert audit["status"] == "unknown" and not audit["complete_valid"]
    assert audit["resource_stops"][0]["code"] == "resource.input_budget"
    assert audit["resource_stops"][0]["not_provider_attempt"]
    assert audit["action_layers"]["summary"]["executed_long_reason_actions"] == 1
    assert audit["observation_diagnostics"]["summary"]["no_following_submission"] == 1


def test_P_transport_failure_no_fabricated_raw_action(panel, tmp_path):
    class Failed:
        def send(self, request, *, api_key):
            raise HTTPSendError("transport.timeout")

    reg = registration("P", "timeout")
    audit = run_one(panel, reg, tmp_path, configuration(), None, sender=Failed())
    assert audit["provider_attempts"] == 1 and audit["submissions"] == 0
    assert audit["usage"]["total_tokens"]["total"] is None
    assert audit["action_layers"]["summary"]["raw_action_shaped"] == 0


def test_identical_R_config_and_only_eight_CP_sessions():
    prior = json.loads((ROOT / OLD_OUTPUT / "preparation/configuration.json").read_bytes())
    assert configuration().as_record() == prior
    assert configuration().as_record()["maximum_pilot_reserved_tokens"] == 27525120
    rows = registrations()
    assert len(rows) == len(set(LABELS)) == 8 and all(r["feedback_condition"] == "R" for r in rows)
    assert all(
        len([r for r in rows if r["condition"] == h and r["expression_condition"] == p]) == 2
        for h in ("E", "F")
        for p in ("C", "P")
    )
    assert "maxLength" not in action_schema("P").model_json_schema()["properties"]["reason"]


def test_population_grouping_uses_expression_policy_not_fixed_R_feedback():
    from trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.stage import (
        summarize_groups,
    )

    rows = [
        {**r, "complete_valid": False, "status": "local_structure_control"} for r in registrations()
    ]
    groups = summarize_groups(rows)
    assert set(groups["by_policy"]) == {"C", "P"}
    assert all(group["denominator"] == 4 for group in groups["by_policy"].values())
    assert set(groups["by_cell"]) == {"E_C", "E_P", "F_C", "F_P"}
    assert all(group["denominator"] == 2 for group in groups["by_cell"].values())
    assert groups["by_policy"]["P"]["by_expression_condition_in_group"] == {"P": 4}
