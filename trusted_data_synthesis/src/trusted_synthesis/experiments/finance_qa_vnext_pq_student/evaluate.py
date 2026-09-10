"""Frozen offline quantity review and independent audit of local Student transcripts."""

import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import (
    evaluate as reference_value,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    LIMITS,
    strict_json,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.evaluate import (
    parse_math,
    rational,
)

from .plan import OUTPUT, SEEDS, SYSTEM, encode, evaluation_config, read_json, record, require, sha

FIELDS = (
    "formula_applicability",
    "variable_correspondence",
    "unit_handling",
    "publication_alignment",
    "final_answer_consistency",
)
STATUSES = {"PASS", "FAIL", "UNDETERMINED", "NOT_ESTABLISHED"}
NEGATIVE_WORDS = re.compile(r"\b(decreas\w*|declin\w*|reduc\w*|down|loss\w*|fell|fall\w*)\b", re.I)
NUMBER_TOKEN = re.compile(
    r"(?<![\w.+/\-])[+-]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)"
    r"(?:[eE][+-]?\d+)?(?:/[+-]?(?:\d+(?:\.\d+)?|\.\d+))?%?(?![\w/])"
)
MONEY = {
    "USD": Fraction(1),
    "USD_thousand": Fraction(1000),
    "USD_million": Fraction(10**6),
    "USD_billion": Fraction(10**9),
}


def policy():
    return record(
        "frozen_evaluation_policy",
        name="publication_tolerance.v2.new_panel_quantity_adapter",
        primary=(
            "Original first Final.value lexical number has absolute priority; if absent, "
            "offline extraction only from actual first Final; never substitute finer answer prose."
        ),
        primary_tolerance=(
            "Compare in reference unit: min(0.005, max(converted lexical quantum / 2, 1e-12)); "
            "exact fractions use zero tolerance."
        ),
        secondary=(
            "Every reviewed secondary answer quantity is compared to the same reference with "
            "its own converted lexical half-quantum, floored at 1e-12, without the primary cap."
        ),
        units=(
            "Explicit money aliases USD, USD_thousand, USD_million, USD_billion permit exact "
            "powers-of-1000 conversions of number AND display quantum. percent only matches "
            "percent; naked fractions are not implicitly percent. Explicit Final.unit is never "
            "replaced; unknown units remain UNDETERMINED, incompatible known units FAIL."
        ),
        orientation=(
            "Offline exact-quote interpretation only: +1 or -1; -1 requires nonnegative original "
            "magnitude and explicit negative-direction wording in actual Final (calculation: "
            "pre/same-call wording including variable names). Never infer from gold or "
            "double-negate a signed negative number."
        ),
        review=(
            "Explicit offline author; all five semantic fields and exact public assistant "
            "quotes. Ambiguous interpretation remains UNDETERMINED. Numeric extraction requires "
            "complete original lexical tokens; Final consistency quotes are first-Final-only."
        ),
        trace=(
            "All five fields PASS; first three have pre/same-selected-call evidence; independent "
            "original calculation with real prior resultrefs matches interpreted published "
            "quantity at primary tolerance; explicit Final result_id agrees; answer PASS. "
            "No new exact-financial-target gate."
        ),
        delivery=(
            "No Final => answer UNDETERMINED and trace never PASS; empty, context, budget and "
            "truncation are separate terminal/delivery statuses. No retry or fabricated raw "
            "generation."
        ),
        provenance=(
            "Local Student generation is not HTTP or Teacher output; exact full public history, "
            "tool outputs, raw first Final, generation accounting and variant manifests audited "
            "offline."
        ),
        scope=(
            "New 12-question panel only; same frozen adapter for B0 and all P/Q seeds. "
            "No historical rescoring, significance claim, population inference, or "
            "contribution/novelty optimization."
        ),
        route_observations_are_mechanistic_not_utility=True,
    )


def normalize_unit(unit):
    if not isinstance(unit, str):
        return None
    text = " ".join(unit.lower().replace("_", " ").split())
    if text in {"%", "percent", "percentage", "per cent"}:
        return "percent"
    if text in {"usd", "$", "dollar", "dollars", "us dollars"}:
        return "USD"
    for word in ("thousand", "million", "billion"):
        if text in {
            word,
            word + "s",
            "usd " + word,
            "usd " + word + "s",
            word + " usd",
            word + "s usd",
            word + " dollars",
            word + "s dollars",
            word + "s of dollars",
            "$ " + word,
            "$ " + word + "s",
            "in " + word + "s",
        }:
            return "USD_" + word
    return text or None


def unit_factor(actual, target):
    actual, target = normalize_unit(actual), normalize_unit(target)
    if actual is None or target is None:
        return None
    if actual == target:
        return Fraction(1)
    if actual in MONEY and target in MONEY:
        return MONEY[actual] / MONEY[target]
    return None


def displayed_number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("not_a_number")
    text = str(value).strip().replace(",", "").rstrip("%")
    actual = Fraction(text)
    quantum = (
        Fraction(0)
        if "/" in text
        else abs(Fraction(Decimal(1).scaleb(Decimal(text).as_tuple().exponent)))
    )
    return actual, quantum


def score_quantity(value, unit, direction, private, *, secondary=False):
    """Only numeric/unit comparison; public evidence is checked by qualify first."""
    base = {"published_number": value, "published_unit": unit, "direction_multiplier": direction}
    try:
        actual, quantum = displayed_number(value)
        if (
            type(direction) is not int
            or direction not in {-1, 1}
            or (direction == -1 and actual < 0)
        ):
            raise ValueError("ambiguous_or_double_direction")
        factor = unit_factor(unit, private["unit"])
        if factor is None:
            known = normalize_unit(unit) in {*MONEY, "percent"}
            return {
                **base,
                "numeric_correct": None,
                "unit_correct": False if known else None,
                "task_answer_status": "FAIL" if known else "UNDETERMINED",
                "reason": "unresolved_or_incompatible_unit",
            }
        actual, quantum = actual * factor * direction, quantum * factor
        tolerance = Fraction(0) if quantum == 0 else max(quantum / 2, Fraction(1, 10**12))
        if not secondary:
            tolerance = min(Fraction(1, 200), tolerance)
        target = reference_value(private["target"], private["facts"])
        numeric = abs(actual - target) <= tolerance
        return {
            **base,
            "interpreted_reference_unit_value": str(actual),
            "reference_unit": private["unit"],
            "reference_exact_value": str(target),
            "converted_lexical_quantum": str(quantum),
            "rounding_tolerance": str(tolerance),
            "numeric_correct": numeric,
            "unit_correct": True,
            "task_answer_status": "PASS" if numeric else "FAIL",
            "secondary_display_tolerance": secondary,
        }
    except (ValueError, TypeError, ZeroDivisionError, InvalidOperation):
        return {
            **base,
            "numeric_correct": None,
            "unit_correct": None,
            "task_answer_status": "UNDETERMINED",
            "reason": "unsupported_or_unresolved_public_quantity",
        }


def _initial(public):
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": encode({"task": public}).decode()},
    ]


def _unicode_scalars(value):
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            if any(0xD800 <= ord(character) <= 0xDFFF for character in current):
                raise ValueError("response_strings_must_be_unicode_scalars")
        elif isinstance(current, dict):
            pending.extend(current)
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)


def _source_result(args, public):
    catalog = {fact["id"]: fact for fact in public["numeric_catalog"]}
    locators = args["locators"]
    require(isinstance(locators, list) and 1 <= len(locators) <= 32, "audit.source_locators")
    rows = []
    for locator in locators:
        if locator in catalog:
            fact = catalog[locator]
            rows.append({"numeric_record": fact, "segment": public["segments"][fact["segment"]]})
        else:
            rows.append({"segment_id": locator, "segment": public["segments"][locator]})
    result = {"records": rows}
    if len(locators) == 1 and locators[0] in catalog:
        result.update(exact_value=catalog[locators[0]]["value"], numeric_source_id=locators[0])
    return result


def _calculation(call, index, previous, public):
    args, output = call["arguments"], call["output"]["result"]
    variables, sources = args.get("variables", {}), args.get("sources", {})
    facts = {fact["id"]: fact for fact in public["numeric_catalog"]}
    resolved, bindings, refs = {}, [], set()

    def lookup(name):
        if name in resolved:
            return rational(resolved[name]["exact_value"])
        supplied = variables[name]
        if isinstance(supplied, dict) and set(supplied) == {"result_id"}:
            ref = supplied["result_id"]
            require(ref in previous, "audit.real_prior_numeric_result_reference")
            value = previous[ref]
            refs.add(ref)
            resolved[name] = {"exact_value": str(value), "result_id": ref}
            bindings.append(
                {"variable": name, "kind": "actual_tool_result_reference", "result_id": ref}
            )
        else:
            value = rational(supplied.get("value") if isinstance(supplied, dict) else supplied)
            declared = sources.get(name) if isinstance(sources, dict) else None
            if declared is None and isinstance(supplied, dict):
                declared = supplied.get("source", supplied.get("source_id"))
            resolved[name] = {"exact_value": str(value), "result_id": None}
            linked = isinstance(declared, str) and declared in facts
            bindings.append(
                {
                    "variable": name,
                    "kind": "explicit_source" if linked else "unlinked_numeric_constant",
                    "source_id": declared,
                    "numeric_alignment": bool(value == rational(facts[declared]["value"]))
                    if linked
                    else None,
                    "no_numeric_coincidence_source_inference": True,
                }
            )
        return value

    value = parse_math(args["expression"], lookup)
    require(value == rational(output["exact_value"]), "audit.independent_actual_arithmetic")
    require(
        output["expression"] == args["expression"]
        and output["resolved_variables"] == resolved
        and output["used_result_ids"] == sorted(refs)
        and output["model_supplied_sources"] == args.get("sources"),
        "audit.calculation_arguments_and_real_resultrefs",
    )
    require(
        output["financial_meaning_certified"] is False
        and output["source_declarations_validated"] is False,
        "audit.no_oracle_calculator_feedback",
    )
    return value, {
        "call_id": call["id"],
        "response_index": index,
        "original_expression": args["expression"],
        "original_arguments": args,
        "actual_exact_value": str(value),
        "independent_execution_verified": True,
        "variable_bindings": bindings,
        "used_result_ids": sorted(refs),
        "operation_count": output["operation_count"],
        "dependency_depth": output["dependency_depth"],
        "financial_meaning_requires_offline_review": True,
    }


def audit_session(directory, public, expected_identity=None):
    """Replay admitted public history and recompute original arithmetic without model calls."""
    directory = Path(directory)
    result = read_json(directory / "result.json")
    config = evaluation_config()
    require(
        result["origin"] == "local_student_generation"
        and result["no_fake_HTTP_or_teacher_response_projection"] is True,
        "audit.actual_local_origin_not_HTTP",
    )
    require(
        expected_identity is None or result["model_identity"] == expected_identity,
        "audit.expected_checkpoint_identity",
    )
    require(
        result["public_document_id"] == public["id"]
        and result["public_document_sha256"] == sha(encode(public)),
        "audit.exact_public_document",
    )
    messages, notebook, previous, calculations, requests, raw_messages = (
        _initial(public),
        {},
        {},
        [],
        [],
        {},
    )
    require(
        result["initial_request_messages_sha256"] == sha(encode(messages)), "audit.exact_original_T"
    )
    events, attempts = result["events"], result["attempts"]
    require(len(attempts) <= config["maximum_responses"], "audit.fixed_response_budget")
    event_pos, calls, invoked, final, final_index = 0, 0, 0, None, None
    terminal = "response_budget_exhausted"
    for index, outcome in enumerate(attempts):
        prefix = directory / f"turns/{index:03d}"

        def path(suffix, prefix=prefix):
            return prefix.with_name(prefix.name + suffix)

        request_raw = path("_request.json").read_bytes()
        require(
            request_raw == encode({"messages": messages, "decoder_configuration_id": config["id"]})
            and sha(request_raw) == outcome["request_sha256"],
            "audit.full_exact_history",
        )
        require(
            outcome == read_json(path("_outcome.json")) and outcome["response_index"] == index,
            "audit.outcome_binding",
        )
        require(
            outcome["origin"] == "local_student_generation"
            and outcome["is_HTTP_response"] is False
            and outcome["model_identity"] == result["model_identity"]
            and outcome["prompt_truncated"] is False,
            "audit.no_HTTP_or_hidden_history_truncation",
        )
        generated, content_ids = outcome["generated_token_ids"], outcome["public_content_token_ids"]
        require(
            type(outcome["generation_invoked"]) is bool
            and outcome["generated_token_count"] == len(generated)
            and all(type(t) is int and t >= 0 for t in generated),
            "audit.generation_accounting",
        )
        raw = outcome["content"].encode()
        if not outcome["generation_invoked"]:
            require(
                not raw
                and not generated
                and not content_ids
                and outcome["raw_response_sha256"] is None
                and not path("_assistant.raw").exists()
                and outcome["finish_reason"] == "context_token_limit",
                "audit.no_fabricated_noninvoked_generation",
            )
        else:
            invoked += 1
            require(
                path("_assistant.raw").read_bytes() == raw
                and sha(raw) == outcome["raw_response_sha256"],
                "audit.original_generated_public_content",
            )
            ended = bool(generated) and generated[-1] in config["eos_token_ids"]
            require(
                content_ids == (generated[:-1] if ended else generated)
                and (outcome["finish_reason"] == "stop") == ended,
                "audit.only_actual_final_EOS_removed",
            )
        if (
            outcome["finish_reason"] != "stop"
            or not raw
            or len(raw) > LIMITS["public_content_bytes"]
        ):
            terminal = (
                outcome["finish_reason"]
                if outcome["finish_reason"] != "stop"
                else "unknown_empty_public_output"
                if not raw
                else "public_content_byte_limit"
            )
            require(
                index == len(attempts) - 1 and not path("_event.json").exists(),
                "audit.unadmitted_terminal_never_retried",
            )
            break
        event = events[event_pos]
        event_pos += 1
        require(
            event == read_json(path("_event.json"))
            and event["response_index"] == index
            and event["raw_sha256"] == sha(raw)
            and event["oracle_feedback"] is False,
            "audit.event_binding",
        )
        raw_messages[index] = raw.decode()
        messages.append({"role": "assistant", "content": raw.decode()})
        error, model = None, None
        try:
            model = strict_json(raw)
            if not isinstance(model, dict):
                raise ValueError("response_must_be_json_object")
            _unicode_scalars(model)
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            error = str(exc)[:300]
        require(error == event["protocol_error"], "audit.unrepaired_protocol_error")
        if error:
            require(
                not event["final"] and event["tool_call"] is None,
                "audit.protocol_failure_not_final",
            )
            messages.append(
                {"role": "user", "content": encode({"interface_error": error}).decode()}
            )
            continue
        require(event["final"] == ("final" in model), "audit.literal_Final_detection")
        if "final" in model:
            require(
                index == len(attempts) - 1 and event["tool_call"] is None,
                "audit.first_Final_terminal",
            )
            final, final_index, terminal = model["final"], index, "model_final"
            break
        if "tool" not in model:
            require(event["tool_call"] is None, "audit.no_invented_tool")
            messages.append(
                {"role": "user", "content": encode({"receipt": "model_message_recorded"}).decode()}
            )
            continue
        if calls == config["maximum_tool_calls"]:
            require(
                index == len(attempts) - 1 and event["tool_call"] is None, "audit.fixed_tool_budget"
            )
            terminal = "tool_budget_exhausted"
            break
        calls += 1
        call = event["tool_call"]
        require(
            call["id"] == f"tool:{calls}"
            and call["name"] == model["tool"]
            and call["arguments"] == model.get("arguments", {}),
            "audit.original_tool_arguments",
        )
        output, args = call["output"], call["arguments"]
        require(
            output == read_json(path("_tool.json"))
            and output["call_id"] == call["id"]
            and output["tool"] == call["name"]
            and output["status"] in {"ok", "error"},
            "audit.original_tool_output",
        )
        messages.append({"role": "user", "content": encode({"tool_result": output}).decode()})
        if call["name"] == "calculate":
            requests.append(
                {
                    "call_id": call["id"],
                    "response_index": index,
                    "expression": args.get("expression") if isinstance(args, dict) else None,
                    "execution_status": output["status"],
                }
            )
        if output["status"] == "error":
            require(
                output["result"] is None and isinstance(output["error"], dict),
                "audit.tool_error_not_numeric_result",
            )
            continue
        if call["name"] == "read_source":
            expected = _source_result(args, public)
            require(output["result"] == expected, "audit.literal_public_source_retrieval")
            if "exact_value" in expected:
                previous[call["id"]] = rational(expected["exact_value"])
        elif call["name"] == "notebook":
            key, operation = args["key"], args["operation"]
            require(
                isinstance(key, str) and 0 < len(key) <= 80 and operation in {"read", "write"},
                "audit.notebook_arguments",
            )
            if operation == "write":
                require(
                    isinstance(args["text"], str)
                    and len(args["text"]) <= 8192
                    and (key in notebook or len(notebook) < 32),
                    "audit.notebook_limits",
                )
                notebook[key] = args["text"]
            require(
                output["result"]
                == {"key": key, "text": notebook[key], "author": "model", "operation": operation},
                "audit.actual_model_notebook",
            )
        elif call["name"] == "calculate":
            value, calculation = _calculation(call, index, previous, public)
            previous[call["id"]] = value
            calculations.append(calculation)
        else:
            raise ValueError("audit.unknown_successful_tool")
    context_path = directory / "context_limit_request.json"
    if context_path.exists():
        expected_request = encode({"messages": messages, "decoder_configuration_id": config["id"]})
        require(
            terminal == "response_budget_exhausted"
            and len(attempts) < config["maximum_responses"]
            and len(expected_request) > LIMITS["request_bytes"]
            and context_path.read_bytes() == expected_request,
            "audit.context_byte_limit_before_generation",
        )
        terminal = "context_byte_limit"
    require(
        terminal != "response_budget_exhausted" or len(attempts) == config["maximum_responses"],
        "audit.no_early_budget_stop",
    )
    require(
        messages == read_json(directory / "messages.json")
        and notebook == read_json(directory / "notebook.json"),
        "audit.persisted_complete_history_and_notebook",
    )
    require(
        event_pos == len(events) == result["admitted_public_responses"]
        and len(attempts) == result["decoder_requests"]
        and invoked == result["model_requests"]
        and calls == result["tool_calls"],
        "audit.honest_request_event_tool_counts",
    )
    require(
        result["terminal"] == terminal
        and result["final"] == final
        and (terminal == "model_final") == (final_index is not None),
        "audit.original_first_Final_and_terminal",
    )
    require(
        all(
            result[key] is True
            for key in (
                "no_online_answer_feedback",
                "first_Final_stops",
                "no_teacher_provider_calls",
                "original_T_and_public_tool_semantics_preserved",
            )
        )
        and result["history_truncated"] is False,
        "audit.no_online_oracle_or_final_retry",
    )
    return record(
        "local_student_audit",
        result_id=result["id"],
        public_document_id=public["id"],
        origin=result["origin"],
        model_identity=result["model_identity"],
        terminal=terminal,
        raw_final=final,
        first_final_index=final_index,
        raw_messages={str(k): v for k, v in raw_messages.items()},
        calculations=calculations,
        calculation_requests=requests,
        model_requests=invoked,
        decoder_requests=len(attempts),
        tool_calls=calls,
        raw_model_and_history_verified=True,
        independent_arithmetic_verified=True,
        no_online_answer_feedback=True,
        no_final_retry=True,
        no_HTTP_or_teacher_projection=True,
    )


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
        if str(value) not in {match.group() for match in NUMBER_TOKEN.finditer(final_text)}:
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


def qualify(audit, review, public, private, raw_messages=None):
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


def _prepared(root):
    output = Path(root) / OUTPUT
    prep = output / "preparation"
    manifest(prep)
    verify_source_snapshot(Path(root), read_json(prep / "implementation.json"))
    require(
        read_json(prep / "evaluation_policy.json") == policy()
        and read_json(prep / "evaluation_configuration.json") == evaluation_config(),
        "assessment.frozen_policy_and_decoder",
    )
    registrations = read_json(prep / "evaluation_registrations.json")
    require(
        len(registrations) == 12 and len({r["task_key"] for r in registrations}) == 12,
        "assessment.fixed_twelve_tasks",
    )
    return output, prep, registrations, read_json(prep / "private/evaluation_targets.json")


def assess(root):
    output, prep, registrations, private = _prepared(root)
    require(not (output / "assessment").exists(), "assessment.no_overwrite")
    store = DurableStore(output / "assessment")
    templates, rows = {}, []
    for variant in evaluation_config()["variants"]:
        directory = output / "evaluation" / variant
        manifest(directory)
        identity = read_json(directory / "identity.json")
        require(
            read_json(directory / "configuration.json") == evaluation_config(),
            "assessment.same_decoder_every_variant",
        )
        report = read_json(directory / "report.json")
        require(
            report["variant"] == variant
            and report["model_identity"] == identity
            and len(report["rows"]) == 12
            and report["teacher_calls"] == 0,
            "assessment.variant_report",
        )
        for registration in registrations:
            key = registration["task_key"]
            review_key = f"{variant}/{key}"
            public = read_json(prep / f"public/{key}.json")
            audit = audit_session(directory / "sessions" / key, public, identity)
            require(
                sum(
                    r["task_key"] == key and r["result_id"] == audit["result_id"]
                    for r in report["rows"]
                )
                == 1,
                "assessment.variant_session_join",
            )
            store.json(f"audits/{review_key}.json", audit)
            store.json(
                f"packets/{review_key}.json",
                {
                    "public": public,
                    "private_reference_for_offline_review_only": private[key],
                    "audit": audit,
                },
            )
            templates[review_key] = review_template(audit, public, private[key])
            rows.append(
                {
                    "key": review_key,
                    "variant": variant,
                    "task_key": key,
                    "group": registration["group"],
                    "audit_id": audit["id"],
                    "terminal": audit["terminal"],
                }
            )
    store.json("review_templates.json", {"reviews": templates})
    report = record(
        "offline_assessment",
        rows=rows,
        sessions=len(rows),
        policy_id=policy()["id"],
        no_scores_before_explicit_offline_review=True,
        teacher_calls=0,
        student_generation_calls=0,
    )
    store.json("report.json", report)
    seal_directory(store, kind="pq_student_assessment_manifest", report_id=report["id"])
    return report


def _counts(rows):
    answers = Counter(row["task_answer_status"] for row in rows)
    return {
        "sessions": len(rows),
        "answer_PASS": answers["PASS"],
        "answer_FAIL": answers["FAIL"],
        "answer_UNDETERMINED": answers["UNDETERMINED"],
        "complete_trace_PASS": sum(row["complete_verifiable_trajectory"] for row in rows),
        "terminal_counts": dict(Counter(row["terminal"] for row in rows)),
    }


def finalize(root, reviews_path):
    output, prep, registrations, private = _prepared(root)
    manifest(output / "assessment")
    assessment = read_json(output / "assessment/report.json")
    submitted = read_json(reviews_path)
    reviews = submitted.get("reviews", submitted)
    require(
        set(reviews) == {row["key"] for row in assessment["rows"]},
        "finalize.exact_84_review_population",
    )
    require(not (output / "closeout").exists(), "finalize.no_overwrite")
    store = DurableStore(output / "closeout")
    grades = []
    for row in assessment["rows"]:
        key, task = row["key"], row["task_key"]
        audit = read_json(output / f"assessment/audits/{key}.json")
        public = read_json(prep / f"public/{task}.json")
        grade = {
            **qualify(audit, reviews[key], public, private[task]),
            "key": key,
            "variant": row["variant"],
            "task_key": task,
            "group": row["group"],
        }
        store.json(f"grades/{key}.json", grade)
        grades.append(grade)
    groups = {
        "all12": lambda r: True,
        "transfer6": lambda r: r["task_key"].startswith("T"),
        "regression6": lambda r: r["task_key"].startswith("R"),
    }
    summaries = {
        variant: {
            name: _counts([r for r in grades if r["variant"] == variant and accept(r)])
            for name, accept in groups.items()
        }
        for variant in evaluation_config()["variants"]
    }
    paired = []
    for seed in SEEDS:
        for name in groups:
            p, q = summaries[f"P_{seed}"][name], summaries[f"Q_{seed}"][name]
            paired.append(
                {
                    "seed": seed,
                    "panel": name,
                    "P": p,
                    "Q": q,
                    "Q_minus_P_answer_PASS": q["answer_PASS"] - p["answer_PASS"],
                    "Q_minus_P_complete_trace_PASS": q["complete_trace_PASS"]
                    - p["complete_trace_PASS"],
                }
            )
    store.json("reviews.json", submitted)
    report = record(
        "pq_student_closeout",
        assessment_id=assessment["id"],
        policy_id=policy()["id"],
        sessions=84,
        grades=grades,
        by_variant=summaries,
        paired_seed_differences=paired,
        no_statistical_significance_claim=True,
        no_population_inference=True,
        no_contribution_or_novelty_optimization_claim=True,
        route_choices_are_mechanistic_observations_only=True,
        historical_scores_unchanged=True,
    )
    store.json("report.json", report)
    seal_directory(store, kind="pq_student_closeout_manifest", report_id=report["id"])
    return report
