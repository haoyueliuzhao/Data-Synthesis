"""Readonly event/transport verification and preregistered descriptive measurement.

No executor, runtime step, callback or training code is called. The readonly view
shares public language/admission functions; numeric verification uses the
independent operation verifiers, not the producer's executor.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from types import SimpleNamespace

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.protocol import parse, record, require
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    HTTPResponse,
    _extract,
    render_http_request,
)

from .adapters import OpenAdapter
from .interface import References, binding_record, feedback, parse_compact
from .runtime import StudyRuntime

FORBIDDEN_H2_KEYS = {
    "program_skeleton",
    "projection_role_aliases",
    "task_pattern",
    "available_actions",
    "allowed_next_subgoals",
    "newly_enabled_obligation_ids",
    "topology_kind",
    "expected_effect",
    "catalog_resolution",
    "obligations",
    "update_transition_options",
    "system_derived_transition_options",
}
INTERFACE_CODES = {
    "submission.schema",
    "submission.object",
    "submission.kind",
    "submission.byte_bound",
    "json.duplicate_key",
    "json.non_finite_number",
    "admission.current_state",
    "admission.alternative_set",
    "admission.selected_action",
    "admission.selected_action_content",
    "admission.public_judgment",
    "admission.observation_parent",
    "admission.exact_observation_acceptance",
    "admission.observation_assessment",
    "admission.update_effect",
    "reference.exact_current_session_ref",
}


def policy():
    return record(
        "responsibility_measurement_policy",
        version="responsibility_measurement.v1",
        denominator_per_task_condition=2,
        missing_evidence="unknown_without_denominator_removal",
        interface_error_codes=sorted(INTERFACE_CODES),
        other_errors="semantic_or_phase_or_final; unknown codes retain their literal code",
        decision_origin="H0/H1 exact operation+inputs offered before output; H2 proposal recorded "
        "before execution and no host reference-plan keys in actual HTTP request",
        final_support_graph="Accepted producer-consumer ancestry from selected Final Claim only",
        method_signature="Recursively hash operation, ordered actual input subtrees, parameters, "
        "and Evidence identities; collapse transparent lookup, sort relation_sum member pair "
        "only, retain signed-gap direction. Ignore scheduling, wording and unused work ONLY "
        "for this descriptive method signature, not for a full behavior quotient.",
        complete_behavior_quotient="not_defined_or_inherited",
        comparisons="Within task and condition only; no pooling of Gamma_H0/Gamma_H1/Gamma_H2",
        reasoning_text="Short public rationale is evidence of proposed choice, "
        "not private cognition",
        training_value_or_vtdo_weight_updates=False,
    )


def read(path):
    return json.loads(path.read_bytes())


def identity(value):
    prefix = value["id"].rsplit(":", 1)[0] + ":"
    require(
        strict_canonical_hash({k: v for k, v in value.items() if k != "id"}, prefix=prefix)
        == value["id"],
        "audit.identity",
    )


def manifest(directory):
    value = read(directory / "manifest.json")
    identity(value)
    expected = {m["path"]: m for m in value["members"]}
    require(len(expected) == len(value["members"]), "audit.duplicate_manifest_member")
    actual = {
        p.relative_to(directory).as_posix(): p
        for p in directory.rglob("*")
        if p.is_file() and p != directory / "manifest.json"
    }
    require(set(expected) == set(actual), "audit.complete_manifest")
    for name, path in actual.items():
        require(
            not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()),
            "audit.safe_member",
        )
        raw = path.read_bytes()
        require(
            len(raw) == expected[name]["bytes"]
            and hashlib.sha256(raw).hexdigest() == expected[name]["sha256"],
            "audit.manifest_bytes",
        )
    return value


def no_plan(value):
    if isinstance(value, dict):
        require(not set(value) & FORBIDDEN_H2_KEYS, "audit.h2_reference_plan_leak")
        for child in value.values():
            no_plan(child)
    elif isinstance(value, list):
        for child in value:
            no_plan(child)


def readonly_view(base, group, condition, protocol, compact, callback):
    view = object.__new__(StudyRuntime)
    view.base, view.group, view.condition = base, group, condition
    view.adapter = OpenAdapter(base, group) if condition == "H2" else base
    view.refs = References(base, group)
    view.rules, view.compact_contract = protocol, compact
    view.callback = SimpleNamespace(binding=callback)
    view.claims, view.pending = [], None
    view.submissions = view.actions = view.updates = 0
    view.feedback = view.final = view.callback_stop = None
    view.terminal = False
    view.bounds = {"submissions": 32, "actions": 12}
    return view


def audit_runtime(base, group, condition, directory):
    sealed = manifest(directory)
    session = read(directory / "session.json")
    identity(session)
    require(sealed["session_id"] == session["id"], "audit.session_manifest_binding")
    view = readonly_view(
        base,
        group,
        condition,
        read(directory / "protocol.json"),
        read(directory / "study_protocol.json"),
        session["callback_binding"],
    )
    require(
        canonical_json_bytes(read(directory / "context.json"))
        == canonical_json_bytes(view.adapter.context)
        and canonical_json_bytes(read(directory / "base_context.json"))
        == canonical_json_bytes(base.context),
        "audit.source_context",
    )
    request_by_turn, decisions, errors = {}, [], []
    for index, event in enumerate(session["events"]):
        require(event["sequence"] == index and not view.terminal, "audit.event_order")
        prefix = f"turns/{index:03d}_"
        require(read(directory / (prefix + "event.json")) == event, "audit.event_file")
        request = view.request()
        require(
            canonical_json_bytes(request)
            == canonical_json_bytes(event["request"])
            == canonical_json_bytes(read(directory / (prefix + "request.json"))),
            "audit.actual_state_request",
        )
        if condition == "H2":
            no_plan(request)
        request_by_turn[index] = request
        raw = (directory / (prefix + "response.txt")).read_bytes()
        submission = event["submission"]
        identity(submission)
        require(
            submission["raw_sha256"] == hashlib.sha256(raw).hexdigest()
            and submission["raw_bytes"] == len(raw)
            and submission["request_id"] == request["id"]
            and submission["host_repairs"] == []
            and submission["callback_binding"] == session["callback_binding"],
            "audit.original_model_bytes",
        )
        submitted = expanded = admitted = None
        try:
            submitted = parse(raw) if condition == "H0" else parse_compact(raw, condition)
            submitted, expanded, admitted = view.bind_and_admit(raw, request)
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            code = str(error)
        else:
            code = None
        binding = binding_record(condition, raw, submitted, expanded, view.refs)
        require(
            binding
            == event["language_binding"]
            == read(directory / (prefix + "language_binding.json")),
            "audit.language_ownership",
        )
        receipt = event["receipt"]
        identity(receipt)
        require(
            receipt["admitted"] is (admitted is not None)
            and receipt["error_code"] == code
            and receipt["submission_id"] == submission["id"]
            and receipt["request_id"] == request["id"]
            and receipt["language_binding_id"] == binding["id"]
            and receipt == read(directory / (prefix + "receipt.json")),
            "audit.real_admission",
        )
        require(event["parsed"] == submitted, "audit.parsed_original")
        view.submissions += 1
        if admitted is None:
            require(
                not any(k in event for k in ("execution", "observation", "claim", "final")),
                "audit.rejection_is_not_execution",
            )
            errors.append(
                {
                    "turn": index,
                    "code": code,
                    "category": "interface"
                    if code in INTERFACE_CODES
                    else "final"
                    if submitted and submitted["kind"] == "final"
                    else "semantic_or_phase"
                    if code.startswith(("semantic.", "share.", "admission."))
                    else "unclassified",
                }
            )
            view.feedback = feedback(code, request, submitted, group, condition)
        elif submitted["kind"] == "action":
            view.actions += 1
            if "execution_error" in event:
                view.terminal = True
                view.feedback = {"code": "execution_failed", "detail": event["execution_error"]}
            else:
                execution, observation = event["execution"], event["observation"]
                identity(execution)
                identity(observation)
                require(
                    execution["selected_action"] == admitted["option"]
                    and execution["resolved_inputs"]
                    == [x.model_dump(mode="json") for x in admitted["prepared"]["inputs"]]
                    and execution["action_submission_id"] == submission["id"]
                    and execution["receipt_id"] == receipt["id"]
                    and execution == read(directory / (prefix + "execution.json")),
                    "audit.executed_input_binding",
                )
                require(
                    view.adapter.verify_execution(admitted["prepared"], execution["proposition"]),
                    "audit.independent_numeric_and_semantic_verification",
                )
                expected_observation = record(
                    "observation",
                    action_submission_id=submission["id"],
                    execution_id=execution["id"],
                    receipt_id=receipt["id"],
                    obligation_id=admitted["option"]["obligation_id"],
                    selected_action=admitted["option"],
                    proposition=execution["proposition"],
                    independent_output_valid=True,
                )
                require(
                    observation
                    == expected_observation
                    == read(directory / (prefix + "observation.json")),
                    "audit.observation_binding",
                )
                require("claim" not in event, "audit.observation_not_accepted")
                view.pending = observation
                view.feedback = {
                    "code": "pending_observation_requires_callback_update",
                    "admitted": True,
                }
                decisions.append(
                    {
                        "turn": index,
                        "operation": admitted["option"]["operation"],
                        "selected_action_id": admitted["option"]["id"],
                        "full_operation_and_inputs_offered": condition != "H2",
                        "model_proposed_before_execution": condition == "H2",
                        "subgoal": admitted["option"]["subgoal"],
                        "reason": admitted["option"].get("reason"),
                        "actual_inputs": admitted["option"]["inputs"],
                    }
                )
        elif submitted["kind"] == "update":
            view.updates += 1
            if submitted["disposition"] == "accept":
                observation = admitted["observation"]
                claim = record(
                    "claim",
                    observation_id=observation["id"],
                    action_submission_id=observation["action_submission_id"],
                    obligation_id=observation["obligation_id"],
                    proposition=observation["proposition"],
                    status="accepted",
                )
                require(
                    event["claim"] == claim == read(directory / (prefix + "claim.json")),
                    "audit.explicit_accept_entire_observation",
                )
                view.claims.append(claim)
            else:
                require("claim" not in event, "audit.decline_not_accept")
            view.pending = None
            view.feedback = {
                "code": "claim_accepted"
                if submitted["disposition"] == "accept"
                else "observation_declined",
                "admitted": True,
            }
        else:
            view.final = record(
                "final",
                submission_id=submission["id"],
                answer=expanded,
                model_answer=submitted,
                qa_validation=admitted["validation"],
            )
            require(
                view.final == event["final"] == read(directory / (prefix + "final.json")),
                "audit.final_actual_support_and_source_answer",
            )
            view.terminal = True
            view.feedback = {"code": "complete", "admitted": True}
        require(view.state() == event["post_state"], "audit.post_state")
    require(
        view.claims == session["claims"] and view.final == session["final"], "audit.final_state"
    )
    if session.get("callback_stop"):
        request = view.request()
        request_by_turn[view.submissions] = request
        require(
            canonical_json_bytes(read(directory / f"turns/{view.submissions:03d}_request.json"))
            == canonical_json_bytes(request),
            "audit.callback_stop_request",
        )
        if condition == "H2":
            no_plan(request)
        stop = session["callback_stop"]
        identity(stop)
        require(
            not view.terminal
            and stop["sequence"] == view.submissions
            and stop["request_id"] == request["id"]
            and stop["callback_binding_id"] == session["callback_binding"]["id"],
            "audit.callback_stop_binding",
        )
        view.terminal = True
        view.feedback = {"code": "callback_failure", "detail": stop["exception_type"]}
    elif not view.terminal:
        require(view.submissions == 32, "audit.complete_budget_termination")
        view.terminal = True
        view.feedback = {"code": "submission_budget_exhausted"}
    require(view.state() == session["terminal_state"], "audit.terminal_state")
    writes = sealed["write_events"]
    dispatches = [
        (i, e["sequence"]) for i, e in enumerate(writes) if e["kind"] == "execution_dispatch"
    ]
    require(len(dispatches) == view.actions, "audit.dispatch_count")
    for dispatch_index, sequence in dispatches:
        prior = writes[:dispatch_index]
        require(
            prior[-1] == {"kind": "pre_dispatch_readback", "sequence": sequence},
            "audit.readback_before_dispatch",
        )
        for suffix in ("response.txt", "receipt.json", "language_binding.json"):
            require(
                {"kind": "file_fsync", "path": f"turns/{sequence:03d}_{suffix}"} in prior,
                "audit.durable_before_dispatch",
            )
    require(view.actions <= 12 and view.submissions <= 32, "audit.session_bounds")
    return {
        "session": session,
        "requests": request_by_turn,
        "decisions": decisions,
        "errors": errors,
        "actions": view.actions,
        "submissions": view.submissions,
        "method": support_graph(session),
    }


def support_graph(session):
    if session["final"] is None:
        return None
    claims = {c["id"]: c for c in session["claims"]}
    executions = {
        e["execution"]["action_submission_id"]: e["execution"]
        for e in session["events"]
        if "execution" in e
    }
    used, consumers = set(), Counter()

    def visit(key):
        claim = claims[key]
        used.add(key)
        execution = executions[claim["action_submission_id"]]
        option = execution["selected_action"]
        children = []
        for ref in option["inputs"]:
            if ref["kind"] == "evidence":
                children.append({"evidence": ref["ref_id"]})
            else:
                consumers[ref["ref_id"]] += 1
                children.append(visit(ref["ref_id"]))
        if option["operation"] == "lookup":
            return children[0]
        if option["operation"] == "relation_sum":
            children[:2] = sorted(children[:2], key=canonical_json_bytes)
        return {
            "operation": option["operation"],
            "inputs": children,
            "parameters": option["parameters"],
        }

    final = session["final"]["answer"]
    tree = visit(final["answer_claim_id"])
    return {
        "tree": tree,
        "signature": strict_canonical_hash(tree, prefix="finite_method:"),
        "answer_lineage": claims[final["answer_claim_id"]]["proposition"]["lineage"],
        "used_accepted_claim_ids": sorted(used),
        "accepted_claims_consumed_by_operations": sorted(consumers),
        "accepted_but_unused_claim_ids": sorted(set(claims) - used),
        "not_a_complete_behavior_quotient": True,
    }


def audit_transport(directory, runtime_result, config):
    manifest(directory)
    ledger = read(directory / "ledger.json")
    identity(ledger)
    session = runtime_result["session"]
    require(
        ledger["callback_binding_id"] == session["callback_binding"]["id"]
        and session["callback_binding"]["origin"] == "model"
        and session["callback_binding"]["transport_kind"] == "live_http"
        and read(directory / "config.json") == config.as_record(),
        "audit.live_condition_binding",
    )
    require(
        ledger["provider_attempt_count"] == len(ledger["attempts"]) <= 32,
        "audit.provider_attempt_denominator",
    )
    usage, returned_turns, flags = [], [], []
    request_bytes = response_bytes = 0
    outcomes = []
    for index, row in enumerate(ledger["attempts"] + ledger["stops"]):
        paths, turn = row["paths"], row["turn_index"]
        public = runtime_result["requests"][turn]
        expected = render_http_request(
            public,
            config,
            session_id=ledger["session_id"],
            attempt_index=min(index, len(ledger["attempts"])),
        )
        require(
            canonical_json_bytes(read(directory / paths["public_request"]))
            == canonical_json_bytes(public)
            and read(directory / paths["http_request"]) == expected
            and (directory / paths["http_request_body"]).read_bytes()
            == expected["body_json"].encode(),
            "audit.actual_http_payload",
        )
        outcome = read(directory / paths["outcome"])
        identity(outcome)
        outcomes.append(outcome)
        if paths["reservation"]:
            reservation = read(directory / paths["reservation"])
            identity(reservation)
            require(
                reservation["http_request_id"] == expected["id"]
                and reservation["attempt_index"] == index
                and reservation["reserved_before_send"] is True,
                "audit.reserved_attempt",
            )
            request_bytes += expected["body_byte_count"]
            usage.append(outcome["usage"])
        if paths["http_response"]:
            response = read(directory / paths["http_response"])
            identity(response)
            raw = (directory / paths["http_response_body"]).read_bytes()
            extracted = _extract(
                HTTPResponse(response["status_code"], raw, complete=response["complete"]),
                config.as_record(),
            )
            require(
                outcome["usage"] == extracted["usage"]
                and outcome["condition_flags"] == extracted["condition_flags"],
                "audit.provider_response_usage",
            )
            flags.extend(outcome["condition_flags"])
            if outcome["public_content_returned_to_runtime"]:
                require(extracted["return_content"], "audit.returned_content")
                content = extracted["public_content"]
                require(
                    (directory / paths["public_content"]).read_bytes() == content
                    and hashlib.sha256(content).hexdigest()
                    == session["events"][turn]["submission"]["raw_sha256"],
                    "audit.model_origin",
                )
                returned_turns.append(turn)
                response_bytes += len(content)
    require(
        returned_turns == list(range(runtime_result["submissions"])), "audit.every_model_submission"
    )
    require(
        ledger["reserved_tokens"] == len(ledger["attempts"]) * 107520, "audit.token_reservation"
    )
    totals = {}
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "reasoning_tokens",
    ):
        values = [row.get(key) for row in usage]
        complete = all(type(value) is int for value in values)
        totals[key] = {
            "total": sum(values) if complete else None,
            "known_subtotal": sum(v for v in values if type(v) is int),
            "known_rows": sum(type(v) is int for v in values),
            "attempt_rows": len(values),
        }
    return {
        "attempts": len(ledger["attempts"]),
        "usage": totals,
        "actual_request_bytes": request_bytes,
        "model_response_bytes": response_bytes,
        "condition_flags": sorted(set(flags)),
        "outcome_codes": [o["code"] for o in outcomes if o["code"]],
    }


def qualify(base, group, condition, directory, config):
    try:
        runtime_result = audit_runtime(base, group, condition, directory / "runtime")
        transport = audit_transport(directory / "transport", runtime_result, config)
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError) as error:
        return record(
            "responsibility_qualification",
            task=group,
            condition=condition,
            status="unknown",
            reason=str(error),
            known_denominator_preserved=True,
        )
    valid = runtime_result["session"]["final"] is not None and not transport["condition_flags"]
    return record(
        "responsibility_qualification",
        task=group,
        condition=condition,
        status="qualified" if valid else "known_failure",
        readonly_verified=True,
        numeric_executor_calls_during_audit=0,
        runtime_execute_or_step_calls_during_audit=0,
        admission_shared_with_runtime=True,
        numeric_verifier_independent_of_executor=True,
        actions=runtime_result["actions"],
        submissions=runtime_result["submissions"],
        decisions=runtime_result["decisions"],
        errors=runtime_result["errors"],
        method=runtime_result["method"] if valid else None,
        transport=transport,
        terminal_feedback=runtime_result["session"]["terminal_state"]["last_feedback"],
        callback_stop=runtime_result["session"].get("callback_stop"),
    )
