"""Interpret seven previously unbound events without deleting the complete 42-event history."""

from __future__ import annotations

import copy
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.measurement import _normalize_refs
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError

from ..finance_qa_vnext_model_execution.models import identity, record, require, sha
from ..finance_qa_vnext_panel_quotient import projection as prior
from ..finance_qa_vnext_support_exploration import quotient as support_links


def equal(left, right):
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def _producers(entry):
    return {
        binding[field]: binding["node_id"]
        for binding in entry["graph"]["event_bindings"]
        for field in ("action_submission_id", "accepted_claim_id", "observation_id")
        if binding.get(field)
    }


def _checked_support(entry):
    proof = entry["old_support"]
    identity(proof, "support_exploration_support")
    require(
        proof["qualified"]
        and proof["proof_verified"]
        and proof["qualification_id"] == entry["qualification"]["id"]
        and proof["session_id"] == entry["session"]["id"]
        and proof["source_actual_graph_id"] == entry["graph"]["id"]
        and proof["projection_id"] == entry["old_projection"]["id"],
        "support_transition.old_support_binding",
    )
    require(
        equal(entry["graph"]["nodes"], entry["old_finite_projection"]["nodes"]),
        "support_transition.actual_graph_base_changed",
    )
    return proof


def _bound_trace(entry, role):
    """Join the existing proof to the needed saved effect records; no support reclassification."""
    saved = entry["old_support"]["trace"][role]
    trace = support_links._node_trace(
        saved["node_id"],
        {n["node_id"]: n for n in entry["graph"]["nodes"]},
        entry["graph"]["event_bindings"],
        entry["session"]["events"],
    )
    require(
        equal(support_links._trace_reference(trace), saved),
        "support_transition.trace_reference_changed",
    )
    return trace


def support_transition(entry, index):
    """No-effect applies to rejected proposals only; subsequent sum and Claim are real changes."""
    proof = _checked_support(entry)
    require(
        proof["support"] == "reconstructed_total",
        "support_transition.requires_reconstructed_actual_support",
    )
    events = entry["session"]["events"]
    event = events[index]
    successor_index = next(
        j for j in range(index + 1, len(events)) if events[j]["receipt"]["admitted"]
    )
    interval = prior.no_effect_interval(events, index, successor_index)
    producers = _producers(entry)
    proposal = prior.retained_proposal(event, events[successor_index], producers)
    selected = prior._offer(event)
    total, ratio, percent = (_bound_trace(entry, role) for role in ("total", "ratio", "percent"))
    require(
        total["action"]["sequence"] == successor_index
        and total["node"]["operation"] == "relation_sum"
        and ratio["node"]["operation"] == selected["operation"] == "share_ratio"
        and percent["node"]["operation"] == "scale_percent",
        "support_transition.actual_successor_chain",
    )
    support_links._consume(ratio, "denominator", total)
    support_links._consume(percent, "ratio", ratio)
    actual = ratio["action"]["parsed"]
    offered_actual = prior._offer(ratio["action"])
    context = event["request"]["context"]
    disclosed = context["evidence"]["total"]["id"]
    before = next(r for r in event["parsed"]["inputs"] if r["role"] == "denominator")
    after = next(r for r in actual["inputs"] if r["role"] == "denominator")
    require(
        before == {"kind": "evidence", "ref_id": disclosed, "role": "denominator"}
        and after == {"kind": "claim", "ref_id": total["claim"]["id"], "role": "denominator"},
        "support_transition.denominator_input_binding",
    )
    require(
        selected["semantic_choice"] == "disclosed_total"
        and offered_actual["semantic_choice"] == "reconstructed_total"
        and selected["obligation_id"] == offered_actual["obligation_id"] == "ratio"
        and selected["operation_contract_id"] == offered_actual["operation_contract_id"]
        and equal(event["parsed"]["parameters"], actual["parameters"])
        and equal(
            next(r for r in event["parsed"]["inputs"] if r["role"] == "numerator"),
            next(r for r in actual["inputs"] if r["role"] == "numerator"),
        ),
        "support_transition.same_goal_not_equal_denominator",
    )
    require(
        equal(support_links._input(ratio, "denominator"), proof["trace"]["actual_denominator"])
        and equal(
            support_links._resolved(ratio, "denominator"),
            proof["trace"]["actual_resolved_denominator"],
        ),
        "support_transition.resolved_support_binding",
    )
    final = events[-1]
    require(
        final["receipt"]["admitted"]
        and final["parsed"]["kind"] == "final"
        and final["parsed"]["answer_claim_id"] == percent["claim"]["id"]
        and final["submission"]["id"] == proof["trace"]["final_submission_id"]
        and percent["update"]["sequence"] < final["sequence"]
        and any(c == percent["claim"] for c in final["request"]["state"]["accepted_claims"]),
        "support_transition.final_consumption_binding",
    )
    total_ref, ratio_ref, percent_ref = (
        {"producer_action": t["node"]["node_id"]} for t in (total, ratio, percent)
    )
    relation = {
        "kind": "support_choice_transition_after_unadmitted_proposal",
        "public_information": proposal["public_information"],
        "proposal": proposal["proposal"],
        "rejection_relation": proposal["feedback_relation"],
        "unadmitted_proposal_was_executed": False,
        "ordered_phases": [
            {"phase": "unadmitted_disclosed_proposal_and_feedback"},
            {"phase": "actual_sum", "producer": total_ref},
            {"phase": "independent_accept_update_and_new_claim", "producer": total_ref},
            {"phase": "actual_reconstructed_ratio", "producer": ratio_ref},
            {"phase": "accepted_ratio_then_percent", "producer": percent_ref},
        ],
        "order_relation_is_not_causal_or_data_dependency": True,
        "reconstruction_changes_execution_state": True,
        "rejected_interval_has_no_new_execution_or_accepted_claim": True,
        "proposed_inputs": _normalize_refs(event["parsed"]["inputs"], producers),
        "actual_ratio_inputs": copy.deepcopy(ratio["node"]["inputs"]),
        "denominator_transition": {
            "role": "denominator",
            "before": {"kind": "evidence", "reference": {"evidence_id": disclosed}},
            "after": {"kind": "claim", "reference": total_ref},
            "inputs_are_equal": False,
        },
        "real_input_dependency": {
            "consumer": ratio_ref,
            "role": "denominator",
            "producer": total_ref,
            "claim_accepted_before_consumption": True,
        },
        "new_accepted_total_proposition": _normalize_refs(total["claim"]["proposition"], producers),
        "final_answer_producer": percent_ref,
        "accepted_knowledge_retracted": False,
    }
    details = {
        "old_support_proof_id": proof["id"],
        "no_effect_interval_checks": interval,
        "no_effect_interval_end_exclusive": successor_index,
        "actual_total": proof["trace"]["total"],
        "actual_ratio": proof["trace"]["ratio"],
        "actual_percent": proof["trace"]["percent"],
        "actual_resolved_denominator": proof["trace"]["actual_resolved_denominator"],
        "subsequent_actual_effects_are_not_called_no_effect": True,
    }
    return relation, details


def existing_result_alignment(event, accepted_final, claim):
    """The old Share numeric/metadata predicate, factored from citation admissibility."""
    a, b = event["parsed"], accepted_final["parsed"]
    require(
        a["kind"] == b["kind"] == "final"
        and a["answer_claim_id"] == b["answer_claim_id"] == claim["id"],
        "support_transition.same_existing_answer_claim",
    )
    require(
        set(a) == set(b) == {"kind", "state_id", "answer_claim_id", "citations", "result"},
        "support_transition.final_fields",
    )
    context = event["request"]["context"]
    numeric, output = context["numeric"], claim["proposition"]["output"]
    require(
        context["final_projection"] == "share_percent_quantized"
        and numeric["rounding"] == "ROUND_HALF_EVEN"
        and numeric["final_quantum"] == "0.000001",
        "support_transition.same_public_numeric_projection",
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
        equal(b["result"], {"unit": "percent", "value": projected})
        and set(b["result"]) <= set(a["result"])
        and a["result"]["value"] in {output["value"], projected}
        and a["result"]["unit"] == output["unit"] == "percent",
        "support_transition.result_not_existing_projection",
    )
    extras = set(a["result"]) - set(b["result"])
    require(
        all(k in output and equal(a["result"][k], output[k]) for k in extras),
        "support_transition.extra_result_metadata_not_existing_claim",
    )
    return {
        "numeric_contract": numeric,
        "exact_existing_value": output["value"],
        "projected_value": projected,
        "numeric_strings_equal": a["result"]["value"] == b["result"]["value"],
        "extra_result_fields": sorted(extras),
        "citation_values_not_rewritten_for_this_check": True,
        "finance_operation_or_qa_verifier_executed": False,
    }


def grounding_assertions(entry):
    """Retain the entire Final assertion segment, including its ordinary alignment context."""
    proof = _checked_support(entry)
    events = entry["session"]["events"]
    final_index = len(events) - 1
    start = next(i for i, e in enumerate(events) if (e.get("parsed") or {}).get("kind") == "final")
    final = events[final_index]
    require(
        final["receipt"]["admitted"]
        and final["parsed"]["kind"] == "final"
        and final["submission"]["id"] == proof["trace"]["final_submission_id"],
        "support_transition.admitted_final_anchor",
    )
    interval = prior.no_effect_interval(events, start, final_index)
    claims = {c["id"]: c for c in events[start]["request"]["state"]["accepted_claims"]}
    claim = claims[final["parsed"]["answer_claim_id"]]
    lineage = set(claim["proposition"]["lineage"])
    require(set(final["parsed"]["citations"]) == lineage, "support_transition.final_actual_lineage")
    producers = _producers(entry)
    old_rows = {row["sequence"]: row for row in entry["old_projection"]["interpretation_ledger"]}
    raw_assertions: list[dict[str, Any]] = []
    sequence: list[dict[str, Any]] = []
    unbound: list[int] = []
    for index in range(start, final_index + 1):
        event = events[index]
        parsed, request = event["parsed"], event["request"]
        require(
            parsed["answer_claim_id"] in request["final_claim_ids"]
            and any(c == claim for c in request["state"]["accepted_claims"]),
            "support_transition.final_existing_claim_available",
        )
        result_check = existing_result_alignment(event, final, claim)
        citations = set(parsed["citations"])
        public = {e["id"] for e in request["context"]["evidence"].values()} | set(claims)
        require(citations <= public, "support_transition.assertion_has_unbound_reference")
        missing, extra = sorted(lineage - citations), sorted(citations - lineage)
        old = old_rows.get(event["sequence"])
        if missing:
            require(
                not event["receipt"]["admitted"]
                and event["receipt"]["error_code"] == "admission.final_qa"
                and old is not None
                and old["disposition"] == "undetermined",
                "support_transition.incorrect_assertion_not_rejected_or_new",
            )
            # Bind the observed Evidence substitution, not arbitrary claims about another task.
            require(
                set(missing) <= {e["id"] for e in request["context"]["evidence"].values()}
                and bool(extra),
                "support_transition.assertion_substitution_domain",
            )
            state = {
                "assertion_kind": "incorrect_support_assertion",
                "citations": prior._sorted(_normalize_refs(sorted(citations), producers)),
                "missing_actual_evidence": missing,
                "extra_asserted_references": prior._sorted(_normalize_refs(extra, producers)),
                "rejected": True,
                "feedback_code": event["post_state"]["last_feedback"]["code"],
            }
            unbound.append(event["sequence"])
            normalization = "incorrect_support_assertion_retained_not_uses_edge"
        else:
            require(
                index == final_index
                or (old is not None and old["disposition"] == "protocol_alignment_nonclassifying"),
                "support_transition.ordinary_alignment_not_previously_proved",
            )
            state = {
                "assertion_kind": "actual_lineage_assertion",
                "citations": sorted(lineage),
                "missing_actual_evidence": [],
                "extra_asserted_references": [],
            }
            normalization = (
                "existing_nonclassifying_redundant_citation_alignment"
                if index != final_index
                else "admitted_final"
            )
        if not sequence or not equal(sequence[-1], state):
            sequence.append(state)
        raw_assertions.append(
            {
                "sequence": event["sequence"],
                "source_event_sha256": sha(canonical_json_bytes(event)),
                "request_id": request["id"],
                "submission_id": event["submission"]["id"],
                "answer_claim_id": parsed["answer_claim_id"],
                "original_result": parsed["result"],
                "submitted_citations": parsed["citations"],
                "actual_lineage": sorted(lineage),
                "missing": missing,
                "extra": extra,
                "receipt": event["receipt"],
                "feedback": event["post_state"]["last_feedback"],
                "state_before": request["state"],
                "state_after": event["post_state"],
                "result_alignment": result_check,
                "prior_interpretation": old,
                "normalization": normalization,
                "normalized_assertion_index": len(sequence) - 1,
            }
        )
    require(bool(unbound), "support_transition.no_new_grounding_assertion")
    relation = {
        "kind": "same_answer_grounding_assertion_correction",
        "answer_producer": _normalize_refs(claim["id"], producers),
        "actual_lineage": sorted(lineage),
        "assertion_sequence": sequence,
        "final_admitted_assertion": {
            "answer_producer": _normalize_refs(claim["id"], producers),
            "citations": sorted(lineage),
        },
        "assertions_are_not_actual_input_dependencies": True,
        "accepted_claim_and_actual_derivation_unchanged_during_segment": True,
        "raw_segment_includes_all_intermediate_rejections_and_terminal_final": True,
        "ordinary_representation_rejections_not_claimed_admitted": True,
        "feedback_is_observed_not_a_claim_of_understanding": True,
    }
    detail = record(
        "support_transition_grounding_segment",
        source_session_id=entry["session"]["id"],
        old_support_proof_id=proof["id"],
        first_sequence=start,
        final_sequence=final_index,
        all_source_sequences=[e["sequence"] for e in events[start:]],
        original_assertions=raw_assertions,
        new_event_sequences=unbound,
        no_effect_interval_checks=interval,
        behavioral_relation=relation,
    )
    return relation, detail


def project_entry(entry, measurement_condition, generation_condition, rule, contract):
    old = entry["old_projection"]
    identity(old, "panel_quotient_projection")
    q = entry["qualification"]
    metadata = {
        key: old[key]
        for key in (
            "registration_id",
            "label",
            "task_group",
            "task_id",
            "context_id",
            "protocol_id",
            "registry_hash",
            "session_id",
            "qualification_id",
            "old_domain_audit_id",
            "source_actual_graph_id",
            "old_projection_supported",
            "source_domain_audit",
            "profile",
            "profile_id",
            "model_configuration_id",
        )
    }
    metadata.update(
        rule_id=rule["id"],
        generation_condition_id=generation_condition["id"],
        measurement_condition_id=measurement_condition["id"],
        comparison_contract_id=contract["id"],
        previous_projection_id=old["id"],
        previous_projection_supported=old["supported"],
        old_support_id=entry["old_support"]["id"],
        original_qualification_reused=True,
    )
    ledger = copy.deepcopy(old.get("interpretation_ledger", []))
    if q["qualified"] is not True:
        return record(
            "panel_quotient_projection",
            **metadata,
            status="ineligible",
            supported=False,
            behavior_projection=None,
            interpretation_ledger=ledger,
            source_non_accept_ledger=copy.deepcopy(old.get("source_non_accept_ledger", [])),
            newly_interpreted_event_count=0,
            reused_interpretation_count=0,
            reason="original failed outcome remains ineligible",
        )
    relations = (
        copy.deepcopy(old["behavior_projection"]["retained_interactions"])
        if old["supported"]
        else []
    )
    details, errors, new_count = [], [], 0
    unresolved = [r for r in ledger if r["disposition"] == "undetermined"]
    grounding = None
    try:
        require(
            equal(entry["graph"]["nodes"], entry["old_finite_projection"]["nodes"]),
            "support_transition.unchanged_actual_base",
        )
        for row in unresolved:
            index = row["sequence"]
            event = entry["session"]["events"][index]
            require(
                row["source_event_sha256"] == sha(canonical_json_bytes(event)),
                "support_transition.event_source_changed",
            )
            previous = copy.deepcopy(row)
            try:
                if event["parsed"]["kind"] == "action":
                    relation, evidence = support_transition(entry, index)
                    if not relations or not equal(relations[-1], relation):
                        relations.append(relation)
                    detail = record(
                        "support_transition_event_interpretation",
                        source_sequence=index,
                        source_submission_id=event["submission"]["id"],
                        previous_interpretation=previous,
                        behavioral_relation_index=len(relations) - 1,
                        evidence=evidence,
                        interpretation_type="retained_support_choice_transition",
                    )
                elif event["parsed"]["kind"] == "final":
                    if grounding is None:
                        relation, grounding = grounding_assertions(entry)
                        relations.append(relation)
                        details.append(grounding)
                    detail = record(
                        "support_transition_event_interpretation",
                        source_sequence=index,
                        source_submission_id=event["submission"]["id"],
                        previous_interpretation=previous,
                        grounding_segment_id=grounding["id"],
                        interpretation_type="retained_grounding_assertion_correction",
                    )
                else:
                    raise ProtocolError("support_transition.unsupported_new_event_kind")
                details.append(detail)
                row.update(
                    previous_disposition=previous["disposition"],
                    previous_reason=previous.get("reason"),
                    disposition="retained_behavior_relation",
                    reason=None,
                    interpretation={
                        "rule_id": rule["id"],
                        "type": detail["interpretation_type"],
                        "detail_id": detail["id"],
                    },
                )
                new_count += 1
            except (
                ProtocolError,
                KeyError,
                TypeError,
                ValueError,
                StopIteration,
                ArithmeticError,
            ) as exc:
                errors.append({"sequence": index, "reason": str(exc) or type(exc).__name__})
    except (ProtocolError, KeyError, TypeError, ValueError, StopIteration, ArithmeticError) as exc:
        errors.append({"reason": str(exc) or type(exc).__name__})
    supported = not errors and all(row["disposition"] != "undetermined" for row in ledger)
    behavior = (
        {**copy.deepcopy(entry["old_finite_projection"]), "retained_interactions": relations}
        if supported
        else None
    )
    if old["supported"]:
        require(
            equal(behavior, old["behavior_projection"])
            and equal(ledger, old["interpretation_ledger"]),
            "support_transition.old_supported_semantics_changed",
        )
    return record(
        "panel_quotient_projection",
        **metadata,
        status="supported" if supported else "undetermined",
        supported=supported,
        behavior_projection=behavior,
        interpretation_ledger=ledger,
        interpretation_details=details,
        source_non_accept_ledger=copy.deepcopy(old["source_non_accept_ledger"]),
        errors=errors,
        newly_interpreted_event_count=new_count,
        reused_interpretation_count=sum(
            r["disposition"] != "undetermined" for r in old["interpretation_ledger"]
        ),
        complete_source_event_count=len(entry["session"]["events"]),
        complete_source_events_sha256=sha(canonical_json_bytes(entry["session"]["events"])),
        base_nodes_and_final_unchanged=behavior is not None
        and equal({k: behavior[k] for k in ("nodes", "final")}, entry["old_finite_projection"]),
        original_raw_events_or_qualification_modified=False,
        actual_uses_edges_from_erroneous_assertions_added=False,
    )
