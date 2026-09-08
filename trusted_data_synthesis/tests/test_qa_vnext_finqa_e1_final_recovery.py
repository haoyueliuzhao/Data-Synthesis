"""New feedback/recovery/HTTP/replay/report controls only. No Provider sampling."""

import copy
import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.reference_revision import (
    ReferenceExplicitRuntime,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.audit import verify_session
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.closeout import collect
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.metrics import (
    aggregate,
    recovery_trace,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.runtime import (
    REVIEW_KEY,
    REVIEW_TEXT,
    TARGET_ERROR,
    FinalRecoveryRuntime,
    verify_feedback,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.stage import (
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


@pytest.fixture(scope="module")
def panel():
    return Panel(ROOT)


class Trace:
    def __init__(self, panel, feedback="R", sid="offline", h="E"):
        self.runtime = FinalRecoveryRuntime(panel, "E1", h, sid, feedback_condition=feedback)
        self.events, self.requests, self.proof = [], [], []

    def send(self, **fields):
        request = self.runtime.request()
        raw = json.dumps({"state_id": request["state"]["id"], **fields}).encode()
        event = self.runtime.transition(raw, request)
        self.requests.append(request)
        self.events.append(event)
        self.proof.append({"request": request, "raw": raw.decode()})
        return event

    def action(
        self, operation, inputs, accept=True, reason="Offline adapter mock, not a model sample."
    ):
        event = self.send(
            kind="action",
            operation=operation,
            inputs=inputs,
            parameters={},
            subgoal="offline control",
            reason=reason,
        )
        assert event["admitted"]
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
        target = self.runtime.task["target"]
        num_source, den_scaled = target["args"][0]["args"]
        n = self.action("read", [num_source])
        d = self.action("read", [den_scaled["args"][0]])
        ratio = self.action("divide", [n["id"], d["id"]])
        wrong = self.action("multiply", [ratio["id"], "constant:100"])
        assert self.final(wrong)["error"] == TARGET_ERROR
        return n, d, wrong

    def recover(self, method, n, d, wrong, final=True):
        if method == "denominator":
            scaled = self.action("divide", [d["id"], "constant:1000"])
            ratio = self.action("divide", [n["id"], scaled["id"]])
            answer = self.action("multiply", [ratio["id"], "constant:100"])
        elif method == "numerator":
            scaled = self.action("multiply", [n["id"], "constant:1000"])
            ratio = self.action("divide", [scaled["id"], d["id"]])
            answer = self.action("multiply", [ratio["id"], "constant:100"])
        else:
            answer = self.action("multiply", [wrong["id"], "constant:1000"])
        if final:
            assert self.final(answer)["admitted"]
        return answer

    def metrics(self):
        r = self.runtime
        return recovery_trace(self.events, self.requests, {"terminal": r.terminal}, r.task)


class Sender:
    def __init__(self, proof):
        self.proof, self.calls = proof, 0

    def send(self, request, *, api_key):
        expected = self.proof[self.calls]
        public = json.loads(json.loads(request["body_json"])["messages"][1]["content"])
        assert public == expected["request"]
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
                            "message": {"role": "assistant", "content": expected["raw"]},
                        }
                    ],
                    "usage": {"prompt_tokens": 200, "completion_tokens": 10, "total_tokens": 210},
                }
            ).encode(),
        )


@pytest.mark.parametrize("feedback", ["B", "R"])
@pytest.mark.parametrize("method", ["denominator", "numerator", "existing_percent"])
def test_conditional_entry_raw_http_replay_and_alternative_recovery(
    panel, tmp_path, feedback, method
):
    registration = {
        "id": feedback + method,
        "label": feedback + method,
        "task_key": "E1",
        "condition": "F",
        "feedback_condition": feedback,
        "replicate": 1,
    }
    t = Trace(panel, feedback, registration["id"], "F")
    n, d, wrong = t.wrong()
    t.recover(method, n, d, wrong)
    sender = Sender(t.proof)
    audit = run_one(panel, registration, tmp_path, configuration(), None, sender=sender)
    assert audit["complete_valid"] and not audit["model_origin_verified"]
    m = audit["recovery_trace"]
    assert m["first_target_rejection_submission"] == 9
    assert m["first_new_related_executed_operation"] == 10
    assert m["recovery_status"] == "COMPLETE_RECOVERY"
    assert m["fresh_dependency_recovery_witness"]
    assert audit["review_http_exposures"] == (1 if feedback == "R" else 0)
    assert (
        verify_session(panel, registration, tmp_path / registration["label"], model_required=False)
        == audit
    )
    with pytest.raises(ValueError, match="audit.model_origin"):
        verify_session(panel, registration, tmp_path / registration["label"])
    changed = {**registration, "feedback_condition": "B" if feedback == "R" else "R"}
    with pytest.raises(ValueError, match="audit.transition_replay"):
        verify_session(panel, changed, tmp_path / registration["label"], model_required=False)


def test_B_exact_v21_and_R_identical_before_error_then_only_current_feedback(panel):
    base = ReferenceExplicitRuntime(panel, "E1", "E", "same")
    b, r = Trace(panel, "B", "same"), Trace(panel, "R", "same")
    b.wrong()
    r.wrong()
    assert b.proof == r.proof
    for step in b.proof:
        assert base.request() == step["request"]
        base.transition(step["raw"].encode(), step["request"])
    assert base.request() == b.runtime.request()
    request = r.runtime.request()
    assert verify_feedback(request, "R")
    assert request["rules"][REVIEW_KEY] == REVIEW_TEXT
    without_review = copy.deepcopy(request)
    without_review["rules"].pop(REVIEW_KEY)
    expected = b.runtime.request()
    assert {k: v for k, v in without_review.items() if k != "id"} == {
        k: v for k, v in expected.items() if k != "id"
    }
    r.send(kind="bad")
    assert REVIEW_KEY not in r.runtime.request()["rules"]
    assert FinalRecoveryRuntime.transition is ReferenceExplicitRuntime.transition


def test_review_does_not_read_private_oracle_or_force_action_or_repair_final(panel):
    t = Trace(panel)
    _, _, wrong = t.wrong()
    request = t.runtime.request()
    original = t.runtime.task
    t.runtime.task = {"target": "poison", "facts": "poison", "value": "poison"}
    assert t.runtime.request() == request
    t.runtime.task = original
    assert t.final(wrong)["error"] == TARGET_ERROR
    assert t.final(wrong, value="10.963890819712072")["error"] == "final.unexecuted_value_change"
    assert REVIEW_KEY not in t.runtime.request()["rules"]
    assert wrong in t.runtime.claims
    assert not any(
        text in REVIEW_TEXT
        for text in ("1000", "15.3", "139549", "E1", "source:", "constant:", "10.963")
    )


def test_reason_change_same_expression_is_not_new_dependency_or_recovery(panel):
    t = Trace(panel)
    _, _, wrong = t.wrong()
    t.final(wrong)
    duplicate = t.action("multiply", [wrong["id"], "constant:1"], reason="Units are now aligned.")
    t.final(duplicate)
    m = t.metrics()
    assert m["old_bad_claim_reuse_submissions"] == [10]
    assert m["bad_expression_reuse_submissions"] == [10, 13]
    assert m["first_new_related_executed_operation"] is None
    assert not m["fresh_dependency_recovery_witness"]
    assert not m["scale_aligned_operations"]


@pytest.mark.parametrize("resolution", ["unresolved", "reject", "accept"])
def test_aligned_but_unconsumed_is_not_complete_recovery(panel, resolution):
    t = Trace(panel)
    _, _, wrong = t.wrong()
    obs = t.action("multiply", [wrong["id"], "constant:1000"], accept=False)
    if resolution != "unresolved":
        t.send(kind="update", observation=obs["id"], disposition=resolution)
        t.final(wrong)
    m = t.metrics()
    assert m["scale_aligned_operations"][0]["resolution"] == resolution
    assert not m["scale_aligned_operations"][0]["consumed_by_valid_final"]
    assert m["recovery_status"] == "NOT_COMPLETED"
    assert not m["fresh_dependency_recovery_witness"]


def test_first_action_proposal_separate_from_execution(panel):
    t = Trace(panel)
    _, _, wrong = t.wrong()
    event = t.send(
        kind="action",
        operation="unsupported",
        inputs=[wrong["id"]],
        parameters={},
        subgoal="offline",
        reason="No actual execution.",
    )
    assert not event["admitted"]
    t.action("multiply", [wrong["id"], "constant:1000"])
    m = t.metrics()
    assert m["first_post_trigger_action_proposal"] == 10
    assert (
        m["first_post_trigger_executed_operation"]
        == m["first_new_related_executed_operation"]
        == 11
    )


def test_final_rejection_at_budget_has_no_imaginary_feedback_response(panel, tmp_path):
    registration = {
        "id": "last-turn",
        "label": "last-turn",
        "task_key": "E1",
        "condition": "E",
        "feedback_condition": "R",
        "replicate": 1,
    }
    t = Trace(panel, sid=registration["id"])
    for _ in range(23):
        t.send(kind="bad")
    t.wrong()
    assert t.runtime.submissions == 32
    audit = run_one(panel, registration, tmp_path, configuration(), None, sender=Sender(t.proof))
    assert audit["recovery_trace"]["triggered"]
    assert audit["recovery_trace"]["post_trigger_model_submissions"] == 0
    assert audit["review_http_exposures"] == 0
    assert audit["status"] == "budget_exhausted" and audit["provider_attempts"] == 32


def test_direct_success_stays_in_full_denominator_recovery_NA_and_report_bytes(panel, tmp_path):
    registration = {
        "id": "direct",
        "label": "direct",
        "task_key": "E1",
        "condition": "E",
        "feedback_condition": "R",
        "replicate": 1,
    }
    t = Trace(panel, sid=registration["id"])
    target = t.runtime.task["target"]
    n_source, d_scaled = target["args"][0]["args"]
    n, d = t.action("read", [n_source]), t.action("read", [d_scaled["args"][0]])
    t.recover("denominator", n, d, None)
    audit = run_one(panel, registration, tmp_path, configuration(), None, sender=Sender(t.proof))
    m = audit["recovery_trace"]
    assert audit["complete_valid"] and m["recovery_status"] == "NOT_APPLICABLE"
    assert not m["fresh_dependency_recovery_witness"]
    total = aggregate([audit])
    assert total["denominator"] == total["complete_valid"] == total["recovery_not_applicable"] == 1
    assert total["triggered_sessions"] == total["complete_recoveries"] == 0
    review = {
        key: "offline control"
        for key in (
            "first_error",
            "executed_adjustment",
            "acceptance_and_consumption",
            "terminal_point",
            "interpretation_and_limits",
        )
    }
    review["evidence_submissions"] = [1, audit["submissions"]]
    report = collect(
        panel, [registration], tmp_path, [audit], {"direct": review}, model_required=False
    )
    assert report["http_bytes"]["request_body_bytes"] > 0
    assert report["http_bytes"]["response_body_bytes"] > 0
    assert report["total"] == total
    assert report["by_success_status"]["not_complete"]["denominator"] == 0


def test_transport_failure_retains_unknown_cost_without_fabricated_submission(panel, tmp_path):
    class FailSender:
        def send(self, request, *, api_key):
            raise HTTPSendError("transport.timeout")

    registration = {
        "id": "timeout",
        "label": "timeout",
        "task_key": "E1",
        "condition": "F",
        "feedback_condition": "R",
        "replicate": 2,
    }
    audit = run_one(panel, registration, tmp_path, configuration(), None, sender=FailSender())
    assert audit["status"] == "unknown" and audit["provider_attempts"] == 1
    assert audit["submissions"] == 0 and audit["usage"]["total_tokens"]["total"] is None
    assert audit["recovery_trace"]["recovery_status"] == "NOT_APPLICABLE"
    assert aggregate([audit])["usage"]["total_tokens"]["unknown_attempts"] == 1


def test_fixed_eight_registrations_and_original_model_except_global_cap():
    previous = json.loads((ROOT / OLD_OUTPUT / "preparation/configuration.json").read_bytes())
    current = configuration().as_record()
    ignored = {"id", "maximum_pilot_attempts", "maximum_pilot_reserved_tokens"}
    assert {k: v for k, v in previous.items() if k not in ignored} == {
        k: v for k, v in current.items() if k not in ignored
    }
    assert current["maximum_pilot_attempts"] == 256
    assert current["maximum_pilot_reserved_tokens"] == 27525120
    rows = registrations()
    assert len(rows) == len(set(LABELS)) == 8
    for h in ("E", "F"):
        for b in ("B", "R"):
            assert (
                len([r for r in rows if r["condition"] == h and r["feedback_condition"] == b]) == 2
            )
