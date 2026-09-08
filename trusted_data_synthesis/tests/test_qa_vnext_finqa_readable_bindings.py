"""Only new public binding, E1/J2 wiring and quote-grounded measurement controls."""

import copy
import json
from pathlib import Path

import pytest

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_finqa_binding_view.audit import verify_session
from trusted_synthesis.experiments.finance_qa_vnext_finqa_binding_view.closeout import collect
from trusted_synthesis.experiments.finance_qa_vnext_finqa_binding_view.intent import (
    verify_intent_review,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_binding_view.metrics import (
    action_layers,
    aggregate,
    recovery_trace,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_binding_view.runtime import (
    VIEW_KEY,
    ReadableBindingRuntime,
    binding_view,
    verify_binding_view,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_binding_view.stage import (
    LABELS,
    OLD_OUTPUT,
    configuration,
    registrations,
    run_one,
    summarize_groups,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.runtime import TARGET_ERROR
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.runtime import (
    ReasonPolicyRuntime,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import no_plan
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    HTTPResponse,
    HTTPSendError,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def panel():
    return Panel(ROOT)


class Trace:
    def __init__(self, panel, key="E1", view="V1", sid="local"):
        self.runtime = ReadableBindingRuntime(panel, key, "E", sid, view_condition=view)
        self.requests, self.raws, self.events, self.cache = [], [], [], {}

    def send(self, **fields):
        request = self.runtime.request()
        raw = json.dumps({"state_id": request["state"]["id"], **fields}).encode()
        event = self.runtime.transition(raw, request)
        self.requests.append(request)
        self.raws.append(raw)
        self.events.append(event)
        return event

    def action(self, operation, inputs, reason="Local constructed control.", accept=True):
        event = self.send(
            kind="action",
            operation=operation,
            inputs=inputs,
            reason=reason,
            subgoal="local control",
            parameters={},
        )
        assert event["admitted"]
        if not accept:
            return event["observation"]
        event = self.send(
            kind="update", observation=self.runtime.pending["id"], disposition="accept"
        )
        assert event["admitted"]
        return event["claim"]

    def visit(self, tree):
        if isinstance(tree, str) and tree.startswith("constant:"):
            return tree
        key = json.dumps(tree, sort_keys=True)
        if key not in self.cache:
            if isinstance(tree, str):
                claim = self.action("read", [tree])
            else:
                claim = self.action(tree["op"], [self.visit(arg) for arg in tree["args"]])
            self.cache[key] = claim["id"]
        return self.cache[key]

    def final(self, claim_id):
        claim = next(c for c in self.runtime.claims if c["id"] == claim_id)
        return self.send(
            kind="final",
            answer_claim=claim_id,
            result={"value": claim["value"], "unit": self.runtime.task["unit"]},
            citations=claim["lineage"],
        )

    def wrong(self):
        t = self.runtime.task
        if t["key"] == "E1":
            n, d = t["target"]["args"][0]["args"]
            nr, dr = self.visit(n), self.visit(d["args"][0])
            ratio = self.action("divide", [nr, dr])
            wrong = self.action("multiply", [ratio["id"], "constant:100"])
        else:
            first, second = t["target"]["args"]
            q17, p17 = [self.visit(x) for x in first["args"]]
            q16, p16 = [self.visit(x) for x in second["args"]]
            wrong_term = self.action("multiply", [q16, p17])
            term16 = self.action("multiply", [q16, p16])
            self.cache[json.dumps(second, sort_keys=True)] = term16["id"]
            wrong = self.action("subtract", [wrong_term["id"], term16["id"]])
        assert self.final(wrong["id"])["error"] == TARGET_ERROR
        return wrong["id"]

    def complete(self, method="direct", wrong=None):
        task = self.runtime.task
        if method == "existing_percent":
            answer = self.action("multiply", [wrong, "constant:1000"])["id"]
        elif method == "J2_decomposition":
            a, b = task["target"]["args"]
            q17, p17 = [self.visit(x) for x in a["args"]]
            q16, p16 = [self.visit(x) for x in b["args"]]
            pdiff = self.action("subtract", [p17, p16])
            term1 = self.action("multiply", [q17, pdiff["id"]])
            qdiff = self.action("subtract", [q17, q16])
            term2 = self.action("multiply", [qdiff["id"], p16])
            answer = self.action("add", [term1["id"], term2["id"]])["id"]
        else:
            answer = self.visit(task["target"])
        assert self.final(answer)["admitted"]
        return answer

    def measures(self):
        r = self.runtime
        result = {"terminal": r.terminal}
        recovery = recovery_trace(self.events, self.requests, result, r.task)
        layers = action_layers(self.events, self.requests, self.raws, r.task, "P", recovery)
        return recovery, layers


class Sender:
    def __init__(self, trace):
        self.trace, self.calls = trace, 0

    def send(self, request, *, api_key):
        public = json.loads(json.loads(request["body_json"])["messages"][1]["content"])
        assert public == self.trace.requests[self.calls]
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


def registration(key, view, label):
    return {
        "id": label,
        "label": label,
        "task_key": key,
        "condition": "E",
        "view_condition": view,
        "expression_condition": "P",
        "feedback_condition": "R",
        "replicate": 1,
    }


def unknown_checks(layers):
    return [
        {
            "submission": r["submission"],
            "classification": "UNDETERMINABLE",
            "quotes": [],
            "checked_dimensions": [],
            "explanation": "Local mock; no substantive intent judgment claimed.",
        }
        for r in layers["events"]
        if r["raw_action_shaped"]
    ]


@pytest.mark.parametrize("key", ["E1", "J2"])
def test_V0_exact_P_through_complete_session_and_inherited_transition(panel, key):
    t = Trace(panel, key, "V0", "same")
    baseline = ReasonPolicyRuntime(panel, key, "E", "same", expression_condition="P")
    t.complete()
    for request, raw, event in zip(t.requests, t.raws, t.events, strict=True):
        assert request == baseline.request()
        assert baseline.transition(raw, request) == event
        assert VIEW_KEY not in request
    assert ReadableBindingRuntime.transition is ReasonPolicyRuntime.transition


@pytest.mark.parametrize("key", ["E1", "J2"])
def test_V1_additive_all_base_fields_and_no_oracle_or_reason_rendering(panel, key):
    t = Trace(panel, key)
    t.action(
        "read",
        [t.runtime.task["selected"][0]],
        reason="UNIQUE_INTENT_SENTINEL must not become display data.",
    )
    request = t.runtime.request()
    base = ReasonPolicyRuntime.request(t.runtime)
    assert {k: v for k, v in request.items() if k not in {"id", VIEW_KEY}} == {
        k: v for k, v in base.items() if k != "id"
    }
    assert "UNIQUE_INTENT_SENTINEL" not in json.dumps(request[VIEW_KEY])
    t.runtime.task = {"target": "poison", "facts": "poison", "program": "poison", "unit": "poison"}
    assert t.runtime.request() == request
    verify_binding_view(request, t.events, "V1")
    no_plan(request)


def test_actual_input_order_values_and_no_intent_based_correction(panel):
    t = Trace(panel)
    n, d = t.runtime.task["target"]["args"][0]["args"]
    nr, dr = t.visit(n), t.visit(d["args"][0])
    result = t.action(
        "divide",
        [nr, "constant:1000"],
        reason="Convert the denominator to millions by dividing by 1000.",
    )
    view = t.runtime.request()[VIEW_KEY]
    row = view["results"][-1]
    assert row["value"] == result["value"] == "0.0153"
    assert [i["id"] for i in row["execution"]["ordered_inputs"]] == [nr, "constant:1000"]
    assert [i["value"] for i in row["execution"]["ordered_inputs"]] == ["15.3", "1000"]
    assert "divide(15.3, 1000) -> 0.0153" == row["execution"]["numeric_derivation_display"]
    reverse = t.action("divide", ["constant:1000", dr])
    row = t.runtime.request()[VIEW_KEY]["results"][-1]
    assert [i["id"] for i in row["execution"]["ordered_inputs"]] == ["constant:1000", dr]
    assert row["value"] == reverse["value"]
    assert row["sources"][0]["numeric_catalog_record"]["id"] == d["args"][0]


def test_pending_rejected_and_bad_final_do_not_filter_or_promote_claims(panel):
    t = Trace(panel)
    source = t.runtime.task["selected"][0]
    first = t.action("read", [source])
    duplicate = t.action("read", [source])
    before = t.runtime.request()[VIEW_KEY]
    assert len(before["results"]) == 2 and first["id"] != duplicate["id"]
    assert t.final(first["id"])["error"] == TARGET_ERROR
    assert t.runtime.request()[VIEW_KEY] == before
    pending = t.action("read", [source], accept=False)
    assert t.runtime.request()[VIEW_KEY] == before
    assert all(r["claim_id"] != pending["id"] for r in before["results"])
    assert t.send(kind="update", observation=pending["id"], disposition="reject")["admitted"]
    assert t.runtime.request()[VIEW_KEY] == before
    constant = t.action("multiply", ["constant:100", "constant:1"])
    row = t.runtime.request()[VIEW_KEY]["results"][-1]
    assert row["claim_id"] == constant["id"] and row["sources"] == []


def same_value_fixture():
    context = {"numeric_catalog": [], "related_source_fragments": {}}
    events, claims = [], []
    for ordinal, segment in enumerate(("alpha", "beta"), 1):
        sid = "source:" + segment
        context["numeric_catalog"].append(
            {
                "id": sid,
                "segment": segment,
                "index": 0,
                "start": 0,
                "end": 1,
                "token": "7",
                "value": "7",
            }
        )
        context["related_source_fragments"][segment] = {
            "locator": ["table", ordinal, 1],
            "text": "7",
            "row_label": segment,
            "column_label": str(2015 + ordinal),
        }
        obs = {
            "id": "observation:" + segment,
            "model_action": {"operation": "read", "inputs": [sid]},
            "value": "7",
        }
        events.append(
            {
                "admitted": True,
                "observation": obs,
                "claim": None,
                "model_submission": {"kind": "action"},
                "submission_count": 2 * ordinal - 1,
                "request_id": "request:read" + segment,
            }
        )
        claim = {
            "id": "claim:" + segment,
            "value": "7",
            "exact_value": "7",
            "expression": sid,
            "lineage": [sid],
            "observation_id": obs["id"],
        }
        events.append(
            {
                "admitted": True,
                "observation": None,
                "claim": claim,
                "model_submission": {
                    "kind": "update",
                    "observation": obs["id"],
                    "disposition": "accept",
                },
                "submission_count": 2 * ordinal,
                "request_id": "request:accept" + segment,
            }
        )
        claims.append(claim)
    request = {
        "context": context,
        "state": {"claims": claims},
        "protocol": {"constants": ["constant:1"]},
    }
    return request, events


def test_same_value_different_source_never_merged_or_role_labeled():
    request, events = same_value_fixture()
    view = binding_view(request, events)
    request[VIEW_KEY] = view
    assert [r["claim_id"] for r in view["results"]] == ["claim:alpha", "claim:beta"]
    assert [r["sources"][0]["original_fragment"]["row_label"] for r in view["results"]] == [
        "alpha",
        "beta",
    ]
    assert all(r["value"] == "7" for r in view["results"])
    assert all(
        "unit" not in r and "financial_role" not in r and "recommended" not in r
        for r in view["results"]
    )
    verify_binding_view(request, events, "V1")


@pytest.mark.parametrize(
    "tamper", ["value", "source", "input_order", "acceptance", "drop_duplicate"]
)
def test_view_verifier_rejects_distorted_binding(panel, tamper):
    t = Trace(panel)
    n, d = t.runtime.task["target"]["args"][0]["args"]
    nr, dr = t.visit(n), t.visit(d["args"][0])
    t.action("divide", [nr, dr])
    request = copy.deepcopy(t.runtime.request())
    row = request[VIEW_KEY]["results"][-1]
    if tamper == "value":
        row["value"] = "corrected"
    elif tamper == "source":
        row["sources"][0]["original_fragment"]["text"] = "inferred financial role"
    elif tamper == "input_order":
        row["execution"]["ordered_inputs"].reverse()
    elif tamper == "acceptance":
        row["acceptance"]["update_submission"] = 999
    else:
        request[VIEW_KEY]["results"].pop(0)
    with pytest.raises(ValueError):
        verify_binding_view(request, t.events, "V1")


@pytest.mark.parametrize("view", ["V0", "V1"])
@pytest.mark.parametrize(
    "key,method",
    [("E1", "direct"), ("E1", "existing_percent"), ("J2", "direct"), ("J2", "J2_decomposition")],
)
def test_actual_HTTP_two_task_recovery_and_generic_probes(panel, tmp_path, view, key, method):
    label = key + view + method
    reg = registration(key, view, label)
    t = Trace(panel, key, view, label)
    wrong = t.wrong()
    t.complete(method, wrong)
    audit = run_one(panel, reg, tmp_path, configuration(), None, sender=Sender(t))
    assert audit["complete_valid"] and not audit["model_origin_verified"]
    assert audit["recovery_trace"]["fresh_dependency_recovery_witness"]
    assert audit["action_layers"]["summary"]["method_matched_consumed_by_valid_final"] > 0
    assert audit["binding_view_http_exposures"] == (
        audit["provider_attempts"] if view == "V1" else 0
    )
    assert verify_session(panel, reg, tmp_path / label, model_required=False) == audit
    with pytest.raises(ValueError, match="audit.model_origin"):
        verify_session(panel, reg, tmp_path / label)
    with pytest.raises(ValueError, match="audit.transition_replay"):
        verify_session(
            panel,
            {**reg, "view_condition": "V0" if view == "V1" else "V1"},
            tmp_path / label,
            model_required=False,
        )
    if key == "J2" and method == "J2_decomposition":
        assert audit["final_expression"]["op"] == "add"
    if view == "V1":
        final_request = t.runtime.request()
        assert [r["claim_id"] for r in final_request[VIEW_KEY]["results"]] == [
            c["id"] for c in t.runtime.claims
        ]
        assert wrong in [r["claim_id"] for r in final_request[VIEW_KEY]["results"]]


@pytest.mark.parametrize("key", ["E1", "J2"])
def test_direct_success_NA_and_closeout_quote_accounting(panel, tmp_path, key):
    reg = registration(key, "V1", "direct" + key)
    t = Trace(panel, key, "V1", reg["id"])
    t.complete()
    audit = run_one(panel, reg, tmp_path, configuration(), None, sender=Sender(t))
    assert audit["recovery_trace"]["recovery_status"] == "NOT_APPLICABLE"
    assert aggregate([audit])["denominator"] == aggregate([audit])["complete_valid"] == 1
    review = {
        k: "local control"
        for k in (
            "first_error",
            "executed_adjustment",
            "acceptance_and_consumption",
            "terminal_point",
            "binding_view_and_method",
            "interpretation_and_limits",
        )
    }
    review["evidence_submissions"] = [1, audit["submissions"]]
    review["intent_checks"] = unknown_checks(audit["action_layers"])
    report = collect(panel, [reg], tmp_path, [audit], {reg["label"]: review}, model_required=False)
    assert report["total"] == aggregate([audit])
    assert report["intent_by_view"]["V1"]["clear_public_intent_rows"] == 0
    assert report["http_bytes"]["request_body_bytes"] > 0


def test_intent_quote_population_and_unclear_not_automatically_matching(panel, tmp_path):
    t = Trace(panel)
    t.action("read", [t.runtime.task["selected"][0]], reason="Proceed.")
    recovery, layers = t.measures()
    store = DurableStore(tmp_path / "runtime/turns")
    for index, raw in enumerate(t.raws):
        store.write(f"{index:03d}_response.raw", raw)
    audit = {"action_layers": layers, "recovery_trace": recovery}
    checks = unknown_checks(layers)
    result = verify_intent_review(audit, tmp_path, checks)
    assert result["all_raw_action_shapes"]["UNDETERMINABLE"] == 1
    assert result["all_raw_action_shapes"]["mismatch_rate_among_clear"] is None
    with pytest.raises(ValueError, match="intent.every_raw_action_shape"):
        verify_intent_review(audit, tmp_path, [])
    forged = copy.deepcopy(checks)
    forged[0].update(
        classification="MISMATCH",
        quotes=[{"field": "reason", "text": "an invented explicit intent"}],
        checked_dimensions=["source_identity"],
    )
    with pytest.raises(ValueError, match="intent.exact_original_public_quote"):
        verify_intent_review(audit, tmp_path, forged)


def test_no_provider_response_does_not_fabricate_view_results_or_intent(panel, tmp_path):
    class Failed:
        def send(self, request, *, api_key):
            raise HTTPSendError("transport.timeout")

    reg = registration("J2", "V1", "timeout")
    audit = run_one(panel, reg, tmp_path, configuration(), None, sender=Failed())
    assert audit["provider_attempts"] == 1 and audit["submissions"] == 0
    assert (
        audit["binding_view_http_exposures"] == 1
        and audit["nonempty_binding_view_http_exposures"] == 0
    )
    assert audit["usage"]["total_tokens"]["total"] is None
    assert audit["action_layers"]["summary"]["raw_action_shaped"] == 0


def test_fixed_E_two_tasks_eight_population_and_original_P_config():
    assert configuration().as_record() == json.loads(
        (ROOT / OLD_OUTPUT / "preparation/configuration.json").read_bytes()
    )
    rows = registrations()
    assert len(rows) == len(set(LABELS)) == 8
    assert all(
        r["condition"] == "E"
        and r["expression_condition"] == "P"
        and r["feedback_condition"] == "R"
        for r in rows
    )
    fake = [{**r, "complete_valid": False, "status": "local_population_control"} for r in rows]
    groups = summarize_groups(fake)
    assert all(g["denominator"] == 2 for g in groups["by_task_view"].values())
    assert all(
        g["denominator"] == 4 and g["tasks_in_group"] == {"E1": 2, "J2": 2}
        for g in groups["by_view"].values()
    )
