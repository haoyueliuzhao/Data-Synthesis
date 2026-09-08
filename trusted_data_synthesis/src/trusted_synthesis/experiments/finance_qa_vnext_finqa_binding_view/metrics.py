"""Preregistered raw/structural/admission/execution/acceptance/consumption layers."""

from collections import Counter

from pydantic import ValidationError

from trusted_synthesis.domains.finance.qa_vnext.protocol import require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import (
    TOOLS,
    equivalent,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.metrics import (
    aggregate as original_aggregate,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.runtime import (
    action_schema,
    decode,
    parse,
)

from .recovery import method_probes
from .recovery import recovery_trace as original_recovery_trace


def recovery_trace(events, requests, result, task):
    trace = original_recovery_trace(events, requests, result, task)
    trace["first_post_trigger_schema_valid_action_proposal"] = trace.pop(
        "first_post_trigger_action_proposal"
    )
    trigger = trace["first_target_rejection_submission"]
    event = next((e for e in events if e["submission_count"] == trigger), None)
    trace["remaining_after_first_target_rejection"] = (
        {
            "actions": 12 - event["action_count"],
            "submissions": 32 - event["submission_count"],
        }
        if event is not None
        else None
    )
    return trace


def proposed_core(value, request, task):
    """Inspect original ordered inputs only. This does not execute or repair anything."""
    op, inputs = value.get("operation"), value.get("inputs")
    if not (
        isinstance(op, str)
        and op in TOOLS
        and isinstance(inputs, list)
        and all(isinstance(ref, str) for ref in inputs)
        and value.get("parameters") == {}
        and value.get("state_id") == request["state"]["id"]
        and request["state"]["pending_observation"] is None
        and request["state"]["remaining_actions"] > 0
    ):
        return None, []
    arity = 1 if op in {"read", "absolute"} else 2
    if not (
        len(inputs) == arity
        if op in {"read", "absolute", "add", "subtract", "multiply", "divide"}
        else 2 <= len(inputs) <= 8
    ):
        return None, []
    claims = {c["id"]: c for c in request["state"]["claims"]}
    constants = set(request["protocol"]["constants"])
    sources = {f["id"] for f in request["context"]["numeric_catalog"]}
    if op == "read":
        tree = inputs[0] if inputs[0] in sources else None
    elif all(ref in claims or ref in constants for ref in inputs):
        tree = {
            "op": op,
            "args": [ref if ref in constants else claims[ref]["expression"] for ref in inputs],
        }
    else:
        tree = None
    matches = []
    if tree is not None:
        try:
            matches = [
                key
                for key, probe in method_probes(task).items()
                if equivalent(tree, probe, task["facts"], task["relations"])
            ]
        except (ValueError, TypeError, KeyError, ZeroDivisionError):
            matches = []
    return tree, matches


def summarize_layers(rows):
    return {
        "model_submissions": len(rows),
        "invalid_json_or_nonobject": sum(not r["valid_unambiguous_json_object"] for r in rows),
        "raw_action_shaped": sum(r["raw_action_shaped"] for r in rows),
        "schema_valid_actions": sum(r["schema_valid_action"] for r in rows),
        "semantic_admitted_actions": sum(r["semantic_admitted_action"] for r in rows),
        "actual_executions": sum(r["actual_execution"] for r in rows),
        "accepted_observations": sum(r["observation_resolution"] == "accept" for r in rows),
        "rejected_observations": sum(r["observation_resolution"] == "reject" for r in rows),
        "unresolved_observations": sum(r["observation_resolution"] == "unresolved" for r in rows),
        "raw_long_reason_actions": sum(
            r["raw_action_shaped"] and r["reason_over_480"] for r in rows
        ),
        "schema_valid_long_reason_actions": sum(
            r["schema_valid_action"] and r["reason_over_480"] for r in rows
        ),
        "executed_long_reason_actions": sum(
            r["actual_execution"] and r["reason_over_480"] for r in rows
        ),
        "only_reason_length_schema_rejections": sum(
            r["schema_rejected_only_reason_length"] for r in rows
        ),
        "raw_source_symbolic_method_core_proposals": sum(
            bool(r["proposed_core_method_probes"]) for r in rows
        ),
        "method_matched_actual_executions": sum(bool(r["actual_method_probes"]) for r in rows),
        "method_matched_accepted_observations": sum(
            bool(r["actual_method_probes"]) and r["observation_resolution"] == "accept"
            for r in rows
        ),
        "method_matched_with_later_action_consumer": sum(
            bool(r["actual_method_probes"]) and bool(r["later_direct_action_consumers"])
            for r in rows
        ),
        "method_matched_consumed_by_valid_final": sum(
            bool(r["actual_method_probes"]) and r["consumed_by_valid_final"] for r in rows
        ),
        "raw_action_reason_characters": sum(
            r["reason_characters"] or 0 for r in rows if r["raw_action_shaped"]
        ),
        "maximum_raw_action_reason_characters": max(
            (r["reason_characters"] or 0 for r in rows if r["raw_action_shaped"]), default=0
        ),
    }


def action_layers(events, requests, raw_responses, task, expression_condition, recovery):
    trigger = recovery["first_target_rejection_submission"]
    actual_operations = {r["submission"]: r for r in recovery["operations"]}
    consumers, selections = {}, {}
    for event in events:
        model = event["model_submission"] or {}
        if event["admitted"] and model.get("kind") == "action":
            for ref in model["inputs"]:
                consumers.setdefault(ref, []).append(event["submission_count"])
        elif model.get("kind") == "final":
            selections.setdefault(model["answer_claim"], []).append(event["submission_count"])
    rows = []
    for event, request, raw in zip(events, requests, raw_responses, strict=True):
        index = event["submission_count"]
        after = trigger is not None and index > trigger
        value, json_error, schema_error = None, None, None
        schema_errors, parsed = [], None
        try:
            value = decode(raw)
        except (ValueError, TypeError, KeyError) as exc:
            json_error = str(exc)
        raw_action = value is not None and value.get("kind") == "action"
        if value is not None:
            try:
                parsed = parse(raw, expression_condition)
            except (ValueError, TypeError, KeyError) as exc:
                schema_error = str(exc)
            if raw_action:
                try:
                    action_schema(expression_condition).model_validate(value)
                except ValidationError as exc:
                    schema_errors = [
                        {"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()
                    ]
        require(parsed == event["model_submission"], "metrics.parser_and_record_agree")
        schema_valid = raw_action and parsed is not None
        semantic_admitted = bool(schema_valid and event["admitted"])
        actual = event["observation"] is not None
        require(semantic_admitted == actual, "metrics.admission_execution_split")
        operation = actual_operations.get(index)
        claim_id = operation["accepted_claim_id"] if operation else None
        reason_chars = (
            len(value["reason"]) if raw_action and isinstance(value.get("reason"), str) else None
        )
        core, probes = proposed_core(value, request, task) if raw_action else (None, [])
        row = {
            "submission": index,
            "after_first_target_rejection": after,
            "raw_sha256": event["raw_sha256"],
            "valid_unambiguous_json_object": value is not None,
            "json_error": json_error,
            "raw_kind": value.get("kind") if value else None,
            "raw_action_shaped": raw_action,
            "schema_valid_action": schema_valid,
            "schema_error": schema_error,
            "schema_field_errors": schema_errors,
            "semantic_admitted_action": semantic_admitted,
            "actual_execution": actual,
            "transition_error": event["error"],
            "raw_operation": value.get("operation") if raw_action else None,
            "raw_inputs": value.get("inputs") if raw_action else None,
            "reason_characters": reason_chars,
            "reason_over_480": reason_chars is not None and reason_chars > 480,
            "schema_rejected_only_reason_length": schema_errors
            == [{"location": ["reason"], "type": "string_too_long"}],
            "proposed_core_expression": core,
            "proposed_core_method_probes": probes,
            "core_inspection_is_not_execution_or_repair": True,
            "actual_expression": event["observation"]["expression"] if actual else None,
            "actual_method_probes": operation["method_probe_matches"] if actual else [],
            "observation_id": event["observation"]["id"] if actual else None,
            "observation_resolution": operation["resolution"] if actual else None,
            "resolved_at_submission": operation["resolved_at_submission"] if actual else None,
            "accepted_claim_id": claim_id,
            "later_direct_action_consumers": consumers.get(claim_id, []) if claim_id else [],
            "selected_by_final_submissions": selections.get(claim_id, []) if claim_id else [],
            "consumed_by_valid_final": operation["consumed_by_valid_final"] if actual else False,
        }
        rows.append(row)
    first = {
        key: next(
            (r["submission"] for r in rows if r["after_first_target_rejection"] and r[key]), None
        )
        for key in (
            "raw_action_shaped",
            "schema_valid_action",
            "semantic_admitted_action",
            "actual_execution",
        )
    }
    require(
        first["schema_valid_action"] == recovery["first_post_trigger_schema_valid_action_proposal"],
        "metrics.first_parsed_layer",
    )
    return {
        "events": rows,
        "summary": summarize_layers(rows),
        "after_first_target_rejection_summary": summarize_layers(
            [r for r in rows if r["after_first_target_rejection"]]
        ),
        "first_post_trigger_by_layer": first,
        "non_json_not_promoted_to_action": True,
        "reason_length_is_a_measure_not_reward": True,
    }


def aggregate(rows):
    total = original_aggregate(rows)
    if all("action_layers" in r for r in rows):
        layers = [e for r in rows for e in r["action_layers"]["events"]]
        total["action_layers"] = summarize_layers(layers)
        total["post_trigger_action_layers"] = summarize_layers(
            [e for e in layers if e["after_first_target_rejection"]]
        )
    else:
        total["action_layers"], total["post_trigger_action_layers"] = None, None
    total["tasks_in_group"] = dict(Counter(r["task_key"] for r in rows))
    total["view_conditions_in_group"] = dict(Counter(r["view_condition"] for r in rows))
    for key in (
        "binding_view_http_exposures",
        "nonempty_binding_view_http_exposures",
        "binding_view_content_bytes",
    ):
        total[key] = sum(r[key] for r in rows) if all(key in r for r in rows) else None
    return total
