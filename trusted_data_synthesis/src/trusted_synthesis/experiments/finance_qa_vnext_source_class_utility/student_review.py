"""Original Final priority and semantic review with task-specific quantity checks."""

import json
from decimal import InvalidOperation
from fractions import Fraction

from trusted_synthesis.experiments.finance_qa_vnext_pq_student.evaluate import (
    FIELDS,
    NEGATIVE_WORDS,
    NUMBER_TOKEN,
    STATUSES,
    displayed_number,
)

from .plan import encode, record, require
from .student_quantity import explicit_amounts, final_amount_check, score_quantity, unit_factor


def _lexical_final(audit):
    if audit["first_final_index"] is None:
        return None
    raw = audit["raw_messages"][str(audit["first_final_index"])]
    return json.loads(raw, parse_int=str, parse_float=str)["final"]


def review_template(audit, public, private):
    final = _lexical_final(audit)
    publication = {
        "value": final.get("value") if isinstance(final, dict) else None,
        "unit": final.get("unit") if isinstance(final, dict) else None,
        "direction_multiplier": None,
        "evidence": [],
        "explanation": "",
    }
    return {
        "audit_id": audit["id"],
        "author": "",
        "offline_post_generation": True,
        "publication": publication,
        "calculation": {
            "call_id": None,
            "unit": None,
            "direction_multiplier": None,
            "evidence": [],
            "explanation": "",
        },
        **{
            field: {"status": "UNDETERMINED", "evidence": [], "explanation": ""} for field in FIELDS
        },
        "secondary": [],
        "route_observation": {"description": "", "evidence": [], "mechanistic_not_utility": True},
    }


def _evidence(review, raw_messages):
    require(
        isinstance(review.get("author"), str)
        and bool(review["author"].strip())
        and review.get("offline_post_generation") is True,
        "review.explicit_offline_author",
    )
    groups = [
        review["publication"],
        review["calculation"],
        *[review[field] for field in FIELDS],
        *review["secondary"],
        review["route_observation"],
    ]
    for group in groups:
        for item in group["evidence"]:
            index, quote = item["response_index"], item["quote"]
            require(
                type(index) is int
                and index in raw_messages
                and isinstance(quote, str)
                and bool(quote)
                and quote in raw_messages[index],
                "review.actual_public_assistant_quote",
            )
    for field in FIELDS:
        item = review[field]
        require(
            item["status"] in STATUSES
            and (item["status"] not in {"PASS", "FAIL"} or bool(item["evidence"])),
            "review.semantic_claim_requires_evidence",
        )
    require(
        review["route_observation"].get("mechanistic_not_utility") is True,
        "review.route_not_utility",
    )
    require(
        not review["route_observation"].get("description")
        or bool(review["route_observation"]["evidence"]),
        "review.route_observation_requires_public_evidence",
    )


def _quantity_evidence(quantity, audit, *, calculation=None):
    value, direction = quantity["value"], quantity["direction_multiplier"]
    if value is None or direction is None or quantity["unit"] is None:
        return False
    evidence = quantity["evidence"]
    cutoff = audit["first_final_index"] if calculation is None else calculation["response_index"]
    scoped = (
        [e for e in evidence if e["response_index"] == cutoff]
        if calculation is None
        else [e for e in evidence if e["response_index"] <= cutoff]
    )
    if not scoped:
        return False
    if calculation is None:
        final_text = encode(_lexical_final(audit)).decode()
        # The publication number must itself occur in the actual Final, not in a prior calculation.
        lexical = {match.group() for match in NUMBER_TOKEN.finditer(final_text)}
        lexical.update(
            mention["value"]
            for mention in explicit_amounts(
                final_text, {"public_target_currencies": [], "relevant_source_currencies": []}
            )
            if mention["complete_token_consumed"]
        )
        if str(value) not in lexical:
            return False
    if direction == -1:
        try:
            nonnegative = displayed_number(value)[0] >= 0
        except (ValueError, TypeError, InvalidOperation, ZeroDivisionError):
            return False
        negative_quote = any(NEGATIVE_WORDS.search(e["quote"].replace("_", " ")) for e in scoped)
        if calculation is None:
            negative_quote = negative_quote and bool(
                NEGATIVE_WORDS.search(final_text.replace("_", " "))
            )
        return nonnegative and negative_quote
    return type(direction) is int and direction == 1


def _qualify_existing(audit, review, public, private, raw_messages=None):
    raw_messages = {
        int(k): v
        for k, v in (audit["raw_messages"] if raw_messages is None else raw_messages).items()
    }
    require(review["audit_id"] == audit["id"], "review.audit_binding")
    _evidence(review, raw_messages)
    if audit["first_final_index"] is not None:
        require(
            all(
                e["response_index"] == audit["first_final_index"]
                for e in review["final_answer_consistency"]["evidence"]
            ),
            "review.Final_consistency_requires_actual_first_Final_evidence",
        )
    publication = review["publication"]
    final = _lexical_final(audit)
    if isinstance(final, dict) and "value" in final:
        require(
            publication["value"] == final["value"]
            and type(publication["value"]) is type(final["value"]),
            "review.original_Final_value_absolute_priority",
        )
    if isinstance(final, dict) and "unit" in final:
        require(
            publication["unit"] == final["unit"]
            and type(publication["unit"]) is type(final["unit"]),
            "review.original_Final_unit_absolute_priority",
        )
    quantity_clear = audit["first_final_index"] is not None and _quantity_evidence(
        publication, audit
    )
    if quantity_clear:
        score = score_quantity(
            publication["value"], publication["unit"], publication["direction_multiplier"], private
        )
    else:
        score = {
            "task_answer_status": "UNDETERMINED",
            "numeric_correct": None,
            "unit_correct": None,
            "reason": "no_Final_or_unresolved_original_quantity",
        }
    secondary = []
    for item in review["secondary"]:
        clear = audit["first_final_index"] is not None and _quantity_evidence(item, audit)
        secondary.append(
            score_quantity(
                item["value"], item["unit"], item["direction_multiplier"], private, secondary=True
            )
            if clear
            else {"task_answer_status": "UNDETERMINED", "reason": "secondary_quantity_unresolved"}
        )
    consistency = review["final_answer_consistency"]["status"]
    if audit["first_final_index"] is not None:
        if consistency == "FAIL" or any(s["task_answer_status"] == "FAIL" for s in secondary):
            score.update(
                task_answer_status="FAIL", reason="contradictory_or_inapplicable_Final_or_secondary"
            )
        elif score["task_answer_status"] == "PASS" and (
            consistency != "PASS" or any(s["task_answer_status"] != "PASS" for s in secondary)
        ):
            score.update(
                task_answer_status="UNDETERMINED",
                reason="Final_consistency_or_secondary_unresolved",
            )
    selected = next(
        (c for c in audit["calculations"] if c["call_id"] == review["calculation"]["call_id"]), None
    )
    temporal = bool(selected) and all(
        any(e["response_index"] <= selected["response_index"] for e in review[field]["evidence"])
        for field in FIELDS[:3]
    )
    calc_quantity = {
        **review["calculation"],
        "value": selected["actual_exact_value"] if selected else None,
    }
    calc_clear = bool(selected) and _quantity_evidence(calc_quantity, audit, calculation=selected)
    calculation_match, interpreted_calculation = False, None
    if calc_clear and quantity_clear and "rounding_tolerance" in score:
        factor = unit_factor(calc_quantity["unit"], private["unit"])
        if factor is not None:
            interpreted_calculation = (
                Fraction(selected["actual_exact_value"])
                * factor
                * calc_quantity["direction_multiplier"]
            )
            calculation_match = abs(
                interpreted_calculation - Fraction(score["interpreted_reference_unit_value"])
            ) <= Fraction(score["rounding_tolerance"])
    explicit = final.get("result_id") if isinstance(final, dict) else None
    reference_match = explicit is None or (bool(selected) and explicit == selected["call_id"])
    semantic = all(review[field]["status"] == "PASS" for field in FIELDS)
    trace = bool(
        audit["raw_model_and_history_verified"]
        and selected
        and temporal
        and calc_clear
        and calculation_match
        and reference_match
        and semantic
        and score["task_answer_status"] == "PASS"
    )
    return record(
        "qualified_student_session",
        audit_id=audit["id"],
        review_author=review["author"],
        delivery_status="FINAL_DELIVERED" if audit["first_final_index"] is not None else "NO_FINAL",
        terminal=audit["terminal"],
        answer=score,
        task_answer_status=score["task_answer_status"],
        secondary=secondary,
        complete_verifiable_trajectory=trace,
        trace_status="PASS"
        if trace
        else "FAIL"
        if score["task_answer_status"] == "FAIL"
        or any(review[f]["status"] == "FAIL" for f in FIELDS)
        else "NOT_ESTABLISHED",
        trace_checks={
            "five_semantic_fields_PASS": semantic,
            "first_three_have_pre_or_same_call_evidence": temporal,
            "calculation_quantity_interpretation_established": bool(calc_clear),
            "selected_tool_result_matches_publication": bool(calculation_match),
            "explicit_Final_result_reference_consistent": bool(reference_match),
            "interpreted_calculation_reference_unit_value": str(interpreted_calculation)
            if interpreted_calculation is not None
            else None,
            "no_additional_exact_financial_target_gate": True,
        },
        model_requests=audit["model_requests"],
        tool_calls=audit["tool_calls"],
        original_published_quantity=publication,
        original_calculation_quantity=review["calculation"],
        route_observation=review["route_observation"],
        no_route_choice_equals_utility=True,
    )


def qualify(audit, review, public, private, raw_messages=None):
    result = _qualify_existing(audit, review, public, private, raw_messages)
    check = final_amount_check(_lexical_final(audit), review["publication"], private)
    answer = dict(result["answer"])
    status = result["task_answer_status"]
    if check["status"] == "FAIL":
        status = "FAIL"
    elif check["status"] != "PASS" and status == "PASS":
        status = "UNDETERMINED"
    if status != result["task_answer_status"]:
        answer.update(task_answer_status=status, reason=check["reason"])
    complete = result["complete_verifiable_trajectory"] and check["status"] == "PASS"
    fields = {k: v for k, v in result.items() if k not in {"id", "schema_version"}}
    fields.update(
        answer=answer,
        task_answer_status=status,
        complete_verifiable_trajectory=complete,
        trace_status="PASS"
        if complete
        else "FAIL"
        if status == "FAIL" or result["trace_status"] == "FAIL"
        else "NOT_ESTABLISHED",
        actual_Final_amount_consistency=check,
        original_five_field_source_execution_and_Final_rules_reused=True,
        reviewer_is_independent=False,
        reviewer_is_fully_blinded=False,
        condition_inferred_from_self_description=review.get(
            "condition_inferred_from_self_description", False
        ),
    )
    return record("source_class_qualified_student_session", **fields)
