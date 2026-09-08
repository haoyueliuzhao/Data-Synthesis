"""Read-only independent arithmetic/lifecycle/origin checks and conservative diagnosis."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from fractions import Fraction

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import (
    equivalent,
    lineage,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.runtime import (
    verify_feedback,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.metrics import (
    financial_trace,
    observation_diagnostics,
    verify_public_reference,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest

from .metrics import action_layers, recovery_trace
from .runtime import VERSION, ReasonPolicyRuntime, parse, verify_reason_policy


def read(path):
    return json.loads(path.read_bytes())


def independent_value(tree, facts):
    """Separate evaluator, never invokes the runtime's numeric executor."""
    if isinstance(tree, str):
        return (
            Fraction(tree[9:]) if tree.startswith("constant:") else Fraction(facts[tree]["value"])
        )
    vals = [independent_value(t, facts) for t in tree["args"]]
    op = tree["op"]
    if op == "add":
        return vals[0] + vals[1]
    if op == "subtract":
        return vals[0] - vals[1]
    if op == "multiply":
        return vals[0] * vals[1]
    if op == "divide":
        return vals[0] / vals[1]
    if op == "sum":
        return sum(vals, Fraction(0))
    if op == "average":
        return sum(vals, Fraction(0)) / len(vals)
    if op == "minimum":
        return sorted(vals)[0]
    if op == "maximum":
        return sorted(vals)[-1]
    if op == "absolute":
        return -vals[0] if vals[0] < 0 else vals[0]
    raise ValueError("audit.unknown_operation")


def verify_session(panel, registration, directory, *, model_required=True):
    """Complete transition replay + independently reconstructed executed dependencies."""
    result = read(directory / "runtime/result.json")
    runtime = ReasonPolicyRuntime(
        panel,
        registration["task_key"],
        registration["condition"],
        registration["id"],
        expression_condition=registration["expression_condition"],
    )
    task = panel.tasks[registration["task_key"]]
    accepted, pending, counts, selected = {}, None, Counter(), []
    final = None
    events, requests, raw_responses = [], [], []
    for index in range(result["submissions"]):
        prefix = directory / f"runtime/turns/{index:03d}"
        request = read(prefix.with_name(prefix.name + "_request.json"))
        raw = prefix.with_name(prefix.name + "_response.raw").read_bytes()
        event = read(prefix.with_name(prefix.name + "_transition.json"))
        require(
            runtime.request() == request and runtime.transition(raw, request) == event,
            "audit.transition_replay",
        )
        verify_public_reference(request)
        verify_reason_policy(request, registration["expression_condition"])
        events.append(event)
        requests.append(request)
        raw_responses.append(raw)
        counts["submissions"] += 1
        if not event["admitted"]:
            counts["rejections"] += 1
            counts[event["error"]] += 1
            continue
        submission = parse(raw, registration["expression_condition"])
        counts[submission["kind"]] += 1
        if submission["kind"] == "action":
            require(pending is None, "audit.pending_execution")
            if submission["operation"] == "read":
                tree = submission["inputs"][0]
                require(tree in runtime.allowed_sources, "audit.source_visibility")
                selected.append(tree)
            else:
                args = []
                for ref in submission["inputs"]:
                    if ref.startswith("constant:"):
                        args.append(ref)
                    else:
                        require(ref in accepted, "audit.accepted_before_consumption")
                        args.append(accepted[ref]["expression"])
                tree = {"op": submission["operation"], "args": args}
            pending = event["observation"]
            require(pending["expression"] == tree, "audit.actual_tree_not_reference_substitution")
            require(
                Fraction(pending["exact_value"]) == independent_value(tree, task["facts"]),
                "audit.independent_arithmetic",
            )
            require(pending["lineage"] == sorted(lineage(tree)), "audit.actual_lineage")
        elif submission["kind"] == "update":
            require(
                pending is not None and pending["id"] == submission["observation"],
                "audit.explicit_acceptance",
            )
            if submission["disposition"] == "accept":
                claim = event["claim"]
                require(
                    claim["expression"] == pending["expression"]
                    and claim["exact_value"] == pending["exact_value"],
                    "audit.claim_output",
                )
                accepted[claim["id"]] = claim
            pending = None
        else:
            require(
                pending is None and submission["answer_claim"] in accepted, "audit.final_lifecycle"
            )
            final = accepted[submission["answer_claim"]]
            require(
                equivalent(final["expression"], task["target"], task["facts"], task["relations"]),
                "audit.final_symbolic_target",
            )
            require(
                independent_value(final["expression"], task["facts"])
                == independent_value(task["target"], task["facts"]),
                "audit.final_numeric_target",
            )
            require(submission["result"]["unit"] == task["unit"], "audit.final_unit")
    require(runtime.request()["state"] == result["final_state"], "audit.final_state")
    require((final is not None) == result["terminal"], "audit.terminal_status")
    transport = directory / "transport"
    manifest(transport)
    ledger = read(transport / "ledger.json")
    if model_required:
        require(ledger["transport_kind"] == "live_http", "audit.model_origin")
    usage_rows, outcomes, response_models, origin_turns = [], [], Counter(), []
    review_http_exposures = 0
    for attempt in ledger["attempts"]:
        paths = attempt["paths"]
        outcome = read(transport / paths["outcome"])
        http = read(transport / paths["http_request"])
        body = (transport / paths["http_request_body"]).read_bytes()
        request = read(transport / paths["public_request"])
        require(hashlib.sha256(body).hexdigest() == http["body_sha256"], "audit.actual_http_bytes")
        require(
            json.loads(json.loads(body)["messages"][1]["content"]) == request,
            "audit.actual_model_input",
        )
        require(http["public_request_id"] == request["id"], "audit.public_request_id")
        verify_public_reference(request)
        verify_reason_policy(request, registration["expression_condition"])
        require(request["protocol_id"] == runtime.protocol["id"], "audit.v21_http_protocol")
        review_http_exposures += verify_feedback(request, "R")
        reservation = read(transport / paths["reservation"])
        require(reservation["id"] == outcome["reservation_id"], "audit.attempt_reservation")
        if outcome["public_content_returned_to_runtime"]:
            content = (transport / paths["public_content"]).read_bytes()
            envelope = read(transport / paths["http_response_body"])
            require(
                envelope["choices"][0]["message"]["content"].encode() == content,
                "audit.original_provider_content",
            )
            turn = outcome["turn_index"]
            require(
                (directory / f"runtime/turns/{turn:03d}_response.raw").read_bytes() == content,
                "audit.raw_response_unchanged",
            )
            require(
                read(directory / f"runtime/turns/{turn:03d}_request.json") == request,
                "audit.origin_request",
            )
            origin_turns.append(turn)
        usage_rows.append(outcome["usage"])
        response_models[outcome["observed_model"] or "unknown"] += 1
        outcomes.append(outcome)
    require(
        origin_turns == list(range(result["submissions"])), "audit.every_submission_model_origin"
    )
    require(ledger["provider_attempt_count"] <= 32, "audit.fixed_attempt_budget")
    usage = {
        k: {
            "total": sum(r[k] for r in usage_rows)
            if all(r.get(k) is not None for r in usage_rows)
            else None,
            "observed_subtotal": sum(r.get(k) or 0 for r in usage_rows),
            "unknown_attempts": sum(r.get(k) is None for r in usage_rows),
        }
        for k in sorted({k for r in usage_rows for k in r})
    }
    resource_stops = []
    for stop in ledger["stops"]:
        paths = stop["paths"]
        request = read(transport / paths["public_request"])
        http = read(transport / paths["http_request"])
        body = (transport / paths["http_request_body"]).read_bytes()
        outcome = read(transport / paths["outcome"])
        require(runtime.request() == request, "audit.resource_stop_current_request")
        verify_reason_policy(request, registration["expression_condition"])
        require(
            hashlib.sha256(body).hexdigest() == http["body_sha256"], "audit.resource_stop_bytes"
        )
        require(
            json.loads(json.loads(body)["messages"][1]["content"]) == request,
            "audit.resource_stop_input",
        )
        require(
            not outcome["public_content_returned_to_runtime"] and paths["reservation"] is None,
            "audit.resource_stop_not_attempt",
        )
        resource_stops.append(
            {"code": outcome["code"], "request_body_bytes": len(body), "not_provider_attempt": True}
        )
    trace = recovery_trace(events, requests, result, task)
    layers = action_layers(
        events, requests, raw_responses, task, registration["expression_condition"], trace
    )
    off_target = sorted(set(selected) - set(task["selected"]))
    # Off-target reads are diagnostic candidates, NOT automatically errors: exploration
    # and alternative sources can be legitimate. Per-trajectory review resolves this.
    return record(
        "e1_reason_policy_session_audit",
        expression_contract_version=VERSION,
        feedback_condition="R",
        expression_condition=registration["expression_condition"],
        action_layers=layers,
        resource_stops=resource_stops,
        replicate=registration["replicate"],
        review_http_exposures=review_http_exposures,
        recovery_trace=trace,
        runtime_version=runtime.protocol["version"],
        public_exact_pending_reference_verified=True,
        observation_diagnostics=observation_diagnostics(events, requests, result),
        financial_trace=financial_trace(events, requests, result, task),
        label=registration["label"],
        task_key=registration["task_key"],
        stratum=task["stratum"],
        condition=registration["condition"],
        denominator=1,
        complete_valid=result["terminal"],
        status=result["status"],
        model_origin_verified=ledger["transport_kind"] == "live_http",
        transition_replay_verified=True,
        independent_arithmetic_verified=True,
        counts=dict(counts),
        actions=result["actions"],
        submissions=result["submissions"],
        provider_attempts=ledger["provider_attempt_count"],
        unused_attempts=32 - ledger["provider_attempt_count"],
        unused_actions=12 - result["actions"],
        usage=usage,
        observed_models=dict(response_models),
        condition_flags=sorted({flag for o in outcomes for flag in o["condition_flags"]}),
        selected_source_ids=selected,
        off_reference_source_ids=off_target,
        evidence_error_automatic_claim=False,
        final_expression=final["expression"] if final else None,
        terminal_target_rejections=counts["final.target_not_established"],
        causal_attribution="requires trajectory review; E/F contrast alone insufficient",
    )
