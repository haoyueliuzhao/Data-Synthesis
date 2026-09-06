"""Read-only interpretation of saved events, deliberately separate from qualification."""

from __future__ import annotations

import copy
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.measurement import _normalize_refs
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError

from ..finance_qa_vnext_model_execution.models import record, require, sha


def _equal(a, b):
    return canonical_json_bytes(a) == canonical_json_bytes(b)


def _state_semantics(state):
    return {k: v for k, v in state.items() if k not in {"id", "submission_count", "last_feedback"}}


def no_effect_interval(events, start, stop):
    """Prove only saved-data effects; stop must be the nearest admitted event."""
    require(start < stop < len(events), "panel_quotient.interval_bounds")
    anchor = events[start]["request"]
    checks = []
    for index in range(start, stop):
        event = events[index]
        before, after = event["request"]["state"], event["post_state"]
        require(event["receipt"]["admitted"] is False, "panel_quotient.intervening_admission")
        require(
            set(event) <= {"sequence", "request", "submission", "parsed", "receipt", "post_state"},
            "panel_quotient.rejection_has_effect_record",
        )
        require(
            _equal(_state_semantics(before), _state_semantics(after)),
            "panel_quotient.rejection_state_changed",
        )
        require(
            after["submission_count"] == before["submission_count"] + 1,
            "panel_quotient.rejection_budget",
        )
        require(
            after["last_feedback"]["admitted"] is False
            and after["last_feedback"]["code"] == event["receipt"]["error_code"],
            "panel_quotient.rejection_feedback",
        )
        require(_equal(after, events[index + 1]["request"]["state"]), "panel_quotient.state_chain")
        for field in (
            "context",
            "available_actions",
            "final_claim_ids",
            "public_action_contract",
            "public_update_contract",
        ):
            require(
                _equal(anchor[field], events[index + 1]["request"][field]),
                "panel_quotient.public_information_changed",
            )
        checks.append(
            {
                "sequence": event["sequence"],
                "state_before_id": before["id"],
                "state_after_id": after["id"],
                "submission_count_before": before["submission_count"],
                "submission_count_after": after["submission_count"],
                "feedback": after["last_feedback"],
                "no_new_execution_observation_claim_or_final": True,
            }
        )
    require(events[stop]["receipt"]["admitted"] is True, "panel_quotient.successor_not_admitted")
    return checks


def _offer(event):
    selected = event["parsed"]["decision"]["selected_action_id"]
    offered = event["request"]["available_actions"]
    matches = [item for item in offered if item["id"] == selected]
    require(len(matches) == 1, "panel_quotient.selected_offer")
    require(
        set(event["parsed"]["decision"]["candidate_action_ids"]) == {o["id"] for o in offered},
        "panel_quotient.candidate_set",
    )
    return matches[0]


def action_alignment(rejected, successor):
    left, right = copy.deepcopy(rejected["parsed"]), copy.deepcopy(successor["parsed"])
    require(left["kind"] == right["kind"] == "action", "panel_quotient.action_kind")
    require(
        rejected["receipt"]["error_code"] == "admission.public_judgment",
        "panel_quotient.action_error",
    )
    offer = _offer(rejected)
    require(_equal(offer, _offer(successor)), "panel_quotient.changed_selected_support")
    a, b = left["decision"]["basis"], right["decision"]["basis"]
    require(
        set(a["evidence_refs"]) < set(b["evidence_refs"]), "panel_quotient.not_basis_completion"
    )
    require(_equal(b, offer["basis"]), "panel_quotient.basis_not_public_offer")
    diagnostic = rejected["post_state"]["last_feedback"]["public_diagnostic"]
    require(
        diagnostic["response_field_paths"] == ["/decision/basis"], "panel_quotient.basis_feedback"
    )
    a["evidence_refs"] = b["evidence_refs"]
    for value in (left, right):
        value.pop("state_id")
        value["decision"]["candidate_action_ids"].sort()
    require(_equal(left, right), "panel_quotient.action_target_or_actual_support_changed")
    return {
        "rule": "same_action_public_basis_completion",
        "offered_action_id": offer["id"],
        "added_existing_evidence_refs": sorted(
            set(b["evidence_refs"]) - set(rejected["parsed"]["decision"]["basis"]["evidence_refs"])
        ),
        "public_diagnostic": diagnostic,
    }


def final_alignment(rejected, successor):
    a, b = rejected["parsed"], successor["parsed"]
    require(a["kind"] == b["kind"] == "final", "panel_quotient.final_kind")
    require(rejected["receipt"]["error_code"] == "admission.final_qa", "panel_quotient.final_error")
    require(a["answer_claim_id"] == b["answer_claim_id"], "panel_quotient.answer_claim_changed")
    require(
        set(a) == set(b) == {"kind", "state_id", "answer_claim_id", "citations", "result"},
        "panel_quotient.final_fields",
    )
    request = rejected["request"]
    claims = {c["id"]: c for c in request["state"]["accepted_claims"]}
    require(
        a["answer_claim_id"] in claims and a["answer_claim_id"] in request["final_claim_ids"],
        "panel_quotient.answer_not_existing",
    )
    claim = claims[a["answer_claim_id"]]
    output, context = claim["proposition"]["output"], request["context"]
    extras = set(a["result"]) - set(b["result"])
    require(set(b["result"]) <= set(a["result"]), "panel_quotient.missing_result_core")
    lineage = set(claim["proposition"]["lineage"])
    require(set(b["citations"]) == lineage, "panel_quotient.final_support_changed")
    if context["final_projection"] == "public_program_answer":
        schema = context["public_task"]["answer_schema"]
        require(
            schema["additional_result_properties"] is False and _equal(b["result"], output),
            "panel_quotient.program_answer_projection",
        )
        require(
            set(a["citations"]) == set(b["citations"]), "panel_quotient.program_citations_changed"
        )
        for key in extras:
            require(
                key in schema["result_context"]
                and _equal(a["result"][key], schema["result_context"][key]),
                "panel_quotient.extra_metadata_not_context",
            )
        require(
            _equal({k: a["result"][k] for k in b["result"]}, b["result"]),
            "panel_quotient.program_value_changed",
        )
        basis = {
            "projection": context["final_projection"],
            "answer_schema": schema,
            "numeric_string_unchanged": True,
        }
    elif context["final_projection"] == "share_percent_quantized":
        numeric = context["numeric"]
        require(
            numeric["rounding"] == "ROUND_HALF_EVEN" and numeric["final_quantum"] == "0.000001",
            "panel_quotient.unregistered_quantization",
        )
        with localcontext() as decimal_context:
            decimal_context.prec = numeric["precision"]
            projected = format(
                Decimal(output["value"]).quantize(
                    Decimal(numeric["final_quantum"]), rounding=ROUND_HALF_EVEN
                ),
                "f",
            )
        require(
            _equal(b["result"], {"value": projected, "unit": "percent"}),
            "panel_quotient.quantized_final",
        )
        require(
            a["result"]["value"] in {output["value"], projected}
            and a["result"]["unit"] == output["unit"] == "percent",
            "panel_quotient.not_same_claim_representation",
        )
        for key in extras:
            require(
                key in output and _equal(a["result"][key], output[key]),
                "panel_quotient.extra_metadata_not_claim",
            )
        evidence = {e["id"] for e in context["evidence"].values()}
        require(
            lineage <= set(a["citations"]) <= evidence | set(claims),
            "panel_quotient.new_or_replaced_citation_support",
        )
        basis = {
            "projection": context["final_projection"],
            "numeric_contract": numeric,
            "exact_existing_value": output["value"],
            "projected_value": projected,
            "numeric_strings_equal": a["result"]["value"] == b["result"]["value"],
            "reason": (
                "same existing Claim under explicit public projection, "
                "not relaxed numerical validity"
            ),
        }
    else:
        require(False, "panel_quotient.final_projection_not_supported")
    return {
        "rule": "same_claim_public_final_alignment",
        "answer_claim_id": claim["id"],
        "removed_result_fields": sorted(extras),
        "existing_support_lineage": sorted(lineage),
        "removed_citation_refs": sorted(set(a["citations"]) - set(b["citations"])),
        **basis,
    }


def _semantic(value, producers):
    value = _normalize_refs(value, producers)
    if isinstance(value, dict):
        return {k: _semantic(v, {}) for k, v in value.items() if k not in {"id", "schema_version"}}
    if isinstance(value, list):
        return [_semantic(v, {}) for v in value]
    return value


def _sorted(values):
    return sorted(values, key=canonical_json_bytes)


def retained_proposal(event, successor, producers):
    """Finite public-judgment proposal episode, not an accepted or executed Action."""
    a, b = event["parsed"], successor["parsed"]
    require(
        a["kind"] == b["kind"] == "action" and not event["receipt"]["admitted"],
        "panel_quotient.retained_action_kind",
    )
    selected, next_selected = _offer(event), _offer(successor)
    require(
        selected["id"] != next_selected["id"],
        "panel_quotient.retained_requires_different_successor",
    )
    require(
        event["receipt"]["error_code"] == "admission.public_judgment",
        "panel_quotient.retained_error",
    )
    diagnostic = event["post_state"]["last_feedback"]["public_diagnostic"]
    require(
        diagnostic["contract_id"] == event["request"]["public_action_contract"]["id"],
        "panel_quotient.retained_contract",
    )
    require(
        a["operation"] == selected["operation"]
        and _equal(a["inputs"], selected["inputs"])
        and _equal(a["parameters"], selected["parameters"]),
        "panel_quotient.retained_actual_inputs",
    )
    decision = copy.deepcopy(a["decision"])
    decision.pop("candidate_action_ids")
    decision.pop("selected_action_id")
    decision["basis"]["evidence_refs"].sort()
    decision["basis"]["claim_refs"].sort()
    return {
        "kind": "unadmitted_proposal_before_different_actual_action",
        "public_information": {
            "accepted_claims": _sorted(
                [
                    {
                        "producer": _normalize_refs(c["id"], producers),
                        "obligation_id": c["obligation_id"],
                        "proposition": _normalize_refs(c["proposition"], producers),
                    }
                    for c in event["request"]["state"]["accepted_claims"]
                ]
            ),
            "available_actions": _sorted(
                [_semantic(o, producers) for o in event["request"]["available_actions"]]
            ),
            "unresolved_uncertainties": event["request"]["state"]["unresolved_uncertainties"],
        },
        "proposal": {
            "operation": a["operation"],
            "inputs": _normalize_refs(a["inputs"], producers),
            "parameters": _normalize_refs(a["parameters"], producers),
            "public_judgment": _normalize_refs(decision, producers),
            "selected_offer": _semantic(selected, producers),
        },
        "feedback_relation": {
            "admitted": False,
            "execution_occurred": False,
            "rule_id": diagnostic["rule_id"],
            "violated_field_paths": sorted(diagnostic["response_field_paths"]),
            "contract_id": diagnostic["contract_id"],
        },
        "next_actual_action": _normalize_refs(successor["submission"]["id"], producers),
        "successor_relationship": (
            "nearest admitted action; actual observation/update/claim retained in graph"
        ),
    }


def bind_retained_order(entry, episode, proposal, successor_index, producers):
    """Retain observed proposal/successor/Claim/later-execution order, not a causal edge."""
    events = entry["session"]["events"]
    graph = entry["graph"]
    successor = events[successor_index]
    binding = next(
        b
        for b in graph["event_bindings"]
        if b["action_submission_id"] == successor["submission"]["id"]
    )
    update_index = next(
        i for i, e in enumerate(events) if e["submission"]["id"] == binding["update_submission_id"]
    )
    require(
        update_index > successor_index
        and events[update_index]["receipt"]["admitted"] is True
        and events[update_index]["parsed"]["kind"] == "update"
        and events[update_index]["parsed"]["disposition"] == "accept",
        "panel_quotient.retained_successor_claim",
    )
    proposed = proposal["parsed"]
    matches = [
        i
        for i in range(update_index + 1, len(events))
        if events[i]["receipt"]["admitted"]
        and events[i]["parsed"]["kind"] == "action"
        and all(
            _equal(events[i]["parsed"][k], proposed[k])
            for k in ("operation", "inputs", "parameters")
        )
    ]
    require(bool(matches), "panel_quotient.retained_later_proposal_execution_not_identified")
    later_index = matches[0]
    later = events[later_index]
    later_binding = next(
        b for b in graph["event_bindings"] if b["action_submission_id"] == later["submission"]["id"]
    )
    nodes = {n["node_id"]: n for n in graph["nodes"]}
    node = nodes[binding["node_id"]]
    later_node = nodes[later_binding["node_id"]]
    claim = next(
        c
        for c in events[later_index]["request"]["state"]["accepted_claims"]
        if c["id"] == binding["accepted_claim_id"]
    )
    require(
        claim["proposition"] == successor["observation"]["proposition"],
        "panel_quotient.retained_claim_content",
    )
    episode["observed_order"] = [
        {"event_role": "unadmitted_proposal_and_feedback"},
        {
            "event_role": "different_admitted_action",
            "producer": {"producer_action": node["node_id"]},
        },
        {
            "event_role": "explicit_accept_update_and_claim",
            "producer": {"producer_action": node["node_id"]},
        },
        {
            "event_role": "later_actual_execution_of_proposed_operation_and_inputs",
            "producer": {"producer_action": later_node["node_id"]},
        },
    ]
    episode["next_accepted_claim"] = {
        "producer": {"producer_action": node["node_id"]},
        "proposition": _normalize_refs(claim["proposition"], producers),
    }
    episode["later_actual_action"] = {"producer_action": later_node["node_id"]}
    episode["later_actual_inputs"] = copy.deepcopy(later_node["inputs"])
    episode["next_claim_actual_input_consumers"] = _sorted(
        [
            {"producer_action": n["node_id"]}
            for n in graph["nodes"]
            if node["node_id"] in n["input_dependencies"]
        ]
    )
    episode["next_claim_actual_judgment_consumers"] = _sorted(
        [
            {"producer_action": n["node_id"]}
            for n in graph["nodes"]
            if node["node_id"] in n["decision_dependencies"]
        ]
    )
    episode["next_claim_is_final_answer"] = entry["old_projection"]["final"]["answer_producer"] == {
        "producer_action": node["node_id"]
    }
    episode["order_is_observation_not_data_dependency_or_causal_explanation"] = True
    return episode


def project_entry(entry: dict[str, Any], rule: dict[str, Any], generation_condition_id: str):
    qualification, audit, graph = entry["qualification"], entry["audit"], entry["graph"]
    events = entry["session"]["events"]
    ledger = graph["non_accept_event_ledger"]
    old = entry["old_projection"]
    annotations: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    base = dict(
        rule_id=rule["id"],
        generation_condition_id=generation_condition_id,
        registration_id=entry["registration"]["id"],
        label=entry["label"],
        task_group=qualification["task_group"],
        task_id=qualification["task_id"],
        context_id=qualification["context_id"],
        protocol_id=qualification["protocol_id"],
        registry_hash=qualification["registry_hash"],
        session_id=entry["session"]["id"],
        qualification_id=qualification["id"],
        old_domain_audit_id=audit["id"],
        source_actual_graph_id=graph["id"],
        old_projection_supported=audit["projection_supported"],
        source_domain_audit=copy.deepcopy(audit),
    )
    if qualification["qualified"] is not True:
        return record(
            "panel_quotient_projection",
            **base,
            status="ineligible",
            supported=False,
            behavior_projection=None,
            interpretation_ledger=[],
            source_non_accept_ledger=ledger,
            reason="original unqualified session retained in denominator, no valid Assignment",
        )
    producers = {
        binding[field]: binding["node_id"]
        for binding in graph["event_bindings"]
        for field in ("action_submission_id", "accepted_claim_id", "observation_id")
        if binding.get(field)
    }
    rejected = [i for i, e in enumerate(events) if not e["receipt"]["admitted"]]
    try:
        require(
            {row["sequence"] for row in ledger} == {events[i]["sequence"] for i in rejected},
            "panel_quotient.ledger_coverage",
        )
        require(
            all(row["kind"] == "unadmitted_submission" for row in ledger),
            "panel_quotient.other_ledger_kind",
        )
        for index in rejected:
            event = events[index]
            successor_index = next(
                (j for j in range(index + 1, len(events)) if events[j]["receipt"]["admitted"]), None
            )
            require(successor_index is not None, "panel_quotient.no_nearest_admitted_successor")
            successor = events[successor_index]
            row = {
                "sequence": event["sequence"],
                "source_event_sha256": sha(canonical_json_bytes(event)),
                "request_id": event["request"]["id"],
                "submission": event["submission"],
                "original_parsed_submission": event["parsed"],
                "receipt": event["receipt"],
                "state_before": event["request"]["state"],
                "state_after": event["post_state"],
                "nearest_admitted_successor_sequence": successor["sequence"],
                "nearest_admitted_successor_submission_id": successor["submission"]["id"],
            }
            try:
                row["interval_checks"] = no_effect_interval(events, index, successor_index)
                if event["parsed"]["kind"] == "final":
                    row["interpretation"] = final_alignment(event, successor)
                    row["disposition"] = "protocol_alignment_nonclassifying"
                elif (
                    event["parsed"]["kind"] == "action"
                    and _offer(event)["id"] == _offer(successor)["id"]
                ):
                    row["interpretation"] = action_alignment(event, successor)
                    row["disposition"] = "protocol_alignment_nonclassifying"
                else:
                    episode = bind_retained_order(
                        entry,
                        retained_proposal(event, successor, producers),
                        event,
                        successor_index,
                        producers,
                    )
                    if not retained or not _equal(retained[-1], episode):
                        retained.append(episode)
                    row["interpretation"] = {
                        "rule": "retained_proposal_to_different_successor",
                        "retained_episode_index": len(retained) - 1,
                    }
                    row["disposition"] = "retained_behavior_relation"
            except (
                ProtocolError,
                KeyError,
                TypeError,
                ValueError,
                StopIteration,
                ArithmeticError,
            ) as exc:
                row["disposition"] = "undetermined"
                row["reason"] = str(exc)
                errors.append({"sequence": event["sequence"], "reason": str(exc)})
            annotations.append(row)
    except (ProtocolError, KeyError, TypeError, ValueError, StopIteration, ArithmeticError) as exc:
        errors.append({"reason": str(exc)})
    supported = not errors
    behavior = {**copy.deepcopy(old), "retained_interactions": retained} if supported else None
    return record(
        "panel_quotient_projection",
        **base,
        status="supported" if supported else "undetermined",
        supported=supported,
        behavior_projection=behavior,
        interpretation_ledger=annotations,
        source_non_accept_ledger=ledger,
        errors=errors,
        base_projection_unchanged=behavior is not None
        and _equal({k: behavior[k] for k in old}, old),
        original_qualification_reused=True,
        raw_interactions_modified=False,
        feedback_causally_ineffective_claimed=False,
    )
