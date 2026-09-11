"""Prospective target-bound qualification, exact public quotes and current-claim roles."""

from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.evaluate import (
    qualify as technical_qualification,
)
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.policy import (
    source_claim,
    target_binding,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.evaluate import REVIEW_FIELDS

from .plan import record, require


def quote_check(items, raw_messages, *, required=None):
    require(isinstance(items, list), "review.evidence_list")
    for item in items:
        index, quote = item["response_index"], item["quote"]
        require(
            type(index) is int
            and index in raw_messages
            and isinstance(quote, str)
            and quote
            and quote in raw_messages[index],
            "review.exact_public_quote",
        )
    if required is not None:
        require(any(e["response_index"] == required for e in items), "review.actual_Final_quote")


def source_quotes(items, public):
    require(isinstance(items, list), "review.public_source_quotes")
    for item in items:
        segment = public["segments"][item["segment_id"]]
        quote = item["quote"]
        require(
            isinstance(quote, str) and quote and quote in segment["text"],
            "review.actual_source_segment",
        )


def semantic_binding(review, raw_messages, public, first_final_index):
    item = review["target_binding"]
    require(isinstance(item["explanation"], str) and item["explanation"], "binding.explanation")
    require(item["source_evidence"], "binding.public_scope_anchors")
    source_quotes(item["source_evidence"], public)
    quote_check(item["evidence"], raw_messages, required=first_final_index)
    params = item["parameters"]
    require("alignment" not in params, "binding.ledger_alignment_not_chosen_by_reviewer")
    bound = target_binding(alignment="ALIGNED", **params)
    if first_final_index is None:
        require(
            params["final_chain_completes_public_target"] != "PASS",
            "binding.absent_Final_not_completed",
        )
    require(
        review["formula_applicability"]["status"] == bound["public_task_applicability"],
        "binding.formula_field_bound_to_original_public_task",
    )
    return {
        **bound,
        "explanation": item["explanation"],
        "evidence": item["evidence"],
        "source_evidence": item["source_evidence"],
    }


def claim_certification(review, raw_messages, public):
    inventory = review["claim_inventory"]
    require(
        inventory["complete"] is True
        and inventory["reviewed_response_indices"] == sorted(raw_messages),
        "claims.whole_public_history_inventory",
    )
    require(
        isinstance(inventory["explanation"], str) and inventory["explanation"],
        "claims.inventory_explanation",
    )
    claims = []
    for item in review["source_claims"]:
        for key in ("location", "explanation"):
            require(
                isinstance(item[key], str) and item[key], "claims.explicit_location_and_role_reason"
            )
        require(item["evidence"], "claims.actual_public_statement")
        quote_check(item["evidence"], raw_messages)
        source_quotes(item.get("source_evidence", []), public)
        params = item["parameters"]
        if not params["current"]:
            require(item.get("withdrawal_evidence"), "claims.actual_withdrawal_required")
            quote_check(item["withdrawal_evidence"], raw_messages)
            require(
                max(e["response_index"] for e in item["withdrawal_evidence"])
                >= max(e["response_index"] for e in item["evidence"]),
                "claims.withdrawal_not_before_claim",
            )
        interpreted = source_claim(**params)
        claims.append({**item, "interpretation": interpreted})
    statuses = [c["interpretation"]["status"] for c in claims if c["interpretation"]["current"]]
    status = (
        "FAIL" if "FAIL" in statuses else "UNDETERMINED" if "UNDETERMINED" in statuses else "PASS"
    )
    return {
        "status": status,
        "claims": claims,
        "inventory": inventory,
        "empty_current_claim_set_is_not_source_correspondence_certification": True,
    }


def qualify(audit, review, raw_messages, public):
    bound = semantic_binding(review, raw_messages, public, audit["first_final_index"])
    claims = claim_certification(review, raw_messages, public)
    technical = technical_qualification(audit, review, raw_messages)
    complete = bool(
        audit.get("raw_model_and_history_verified")
        and technical["formula_driven_trace_verified"]
        and bound["public_task_applicability"] == "PASS"
        and claims["status"] == "PASS"
    )
    failed = (
        technical["trace_status"] == "FAIL"
        or bound["public_task_applicability"] == "FAIL"
        or claims["status"] == "FAIL"
    )
    return record(
        "DR_target_bound_qualification",
        **{
            k: v
            for k, v in technical.items()
            if k
            not in {
                "id",
                "schema_version",
                "trace_status",
                "formula_driven_trace_verified",
                "semantic_review",
                "condition_metadata_hidden_in_packets",
            }
        },
        trace_status="PASS" if complete else "FAIL" if failed else "UNDETERMINED",
        formula_driven_trace_verified=complete,
        technical_qualification_id=technical["id"],
        technical_gate_pass=technical["formula_driven_trace_verified"],
        original_source_history_verified=bool(audit.get("raw_model_and_history_verified")),
        public_target_binding=bound,
        current_source_claim_certification=claims,
        semantic_review={k: v for k, v in review.items() if k != "mapping"},
        batch=audit["batch"],
        historical_qualification_id=audit.get("historical_qualification_id"),
        historical_qualification_not_overwritten=True,
        source_rule="public_task_target_binding.v2",
        quantity_rule="public_quantity_interpretation.v1.1",
        metadata_masking_not_independence_or_blinding=True,
    )


def template(audit, raw_messages):
    interpreted = audit["automatic_quantity"]["interpretation"]
    return {
        "published_value": interpreted.get("published_value"),
        "published_unit": interpreted.get("published_unit"),
        "answer_override_evidence": [],
        "secondary_answer_values": [],
        "answer_calculation_id": None,
        "answer_calculation_unit": None,
        **{
            field: {
                "status": "UNDETERMINED",
                "evidence": [],
                "explanation": "Pending complete public history review.",
            }
            for field in (*REVIEW_FIELDS, "final_answer_consistency")
        },
        "planning_observations": {"text": "", "evidence": []},
        "R_mention": {"status": "UNDETERMINED", "evidence": [], "explanation": ""},
        "R_Final_link": {"status": "UNDETERMINED", "evidence": [], "explanation": ""},
        "call_semantics": {},
        "mapping": {
            "occurrences": {},
            "event_annotations": [],
            "revisions": [],
            "cross_checks": [],
        },
        "claim_inventory": {
            "complete": False,
            "reviewed_response_indices": sorted(raw_messages),
            "explanation": "",
        },
        "source_claims": [],
        "target_binding": {
            "parameters": {
                key: "UNDETERMINED"
                for key in (
                    "local_relation",
                    "public_scope_match",
                    "registered_scope_match",
                    "final_chain_completes_public_target",
                )
            },
            "evidence": [],
            "source_evidence": [],
            "explanation": "",
        },
    }
