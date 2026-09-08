"""Post-generation only: independent arithmetic, provenance and quote-grounded semantic review."""

import ast
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from fractions import Fraction

import sympy as sp

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import (
    expression as reference_expression,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_source_snapshot,
)

from .online.common import SYSTEM, encode, record, request_body, sha, strict_json
from .plan import OUTPUT, TASKS, history_guard, read_json, require

REVIEW_FIELDS = (
    "formula_applicability",
    "variable_correspondence",
    "unit_handling",
    "publication_alignment",
)


def rational(value):
    f = Fraction(str(value))
    return sp.Rational(f.numerator, f.denominator)


def parse_math(text, lookup):
    """Independent SymPy-number walker; never calls the online calculator or sympifies text."""
    tree = ast.parse(text, mode="eval")

    def walk(node):
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            return rational(ast.get_source_segment(text, node))
        if isinstance(node, ast.Name):
            return lookup(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = walk(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            a, b = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                if b == 0:
                    raise ZeroDivisionError()
                return a / b
            if isinstance(node.op, ast.Pow):
                return a**b
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            children = node.args
            if len(children) == 1 and isinstance(children[0], (ast.List, ast.Tuple)):
                children = children[0].elts
            args = [walk(child) for child in children]
            name = node.func.id
            if name == "sum":
                return sp.Add(*args)
            if name == "avg":
                return sp.Add(*args) / len(args)
            if name == "min":
                return sp.Min(*args)
            if name == "max":
                return sp.Max(*args)
            if name == "abs" and len(args) == 1:
                return sp.Abs(args[0])
        raise ValueError("independent.unsupported_expression")

    return walk(tree.body)


def symbolic_match(actual, private):
    if actual is None:
        return None
    facts = private["facts"]
    expected = reference_expression(private["target"], facts)
    changes = {
        reference_expression(k, facts): reference_expression(v, facts)
        for k, v in private["relations"].items()
    }
    for _ in range(len(changes) + 1):
        actual, expected = actual.xreplace(changes), expected.xreplace(changes)
    return sp.simplify(actual - expected) == 0


def audit_session(directory, public, private, *, model_required=True):
    manifest(directory)
    result = read_json(directory / "result.json")
    require(
        result["origin"] == "live_http"
        or (not model_required and result["origin"] == "scripted_control"),
        "audit.actual_model_origin",
    )
    expected_messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": encode({"task": public}).decode()},
    ]
    numeric_results, symbolic_results, calculations, citations = {}, {}, [], []
    calculation_requests = []
    finals, usages = [], []
    for index, outcome in enumerate(result["attempts"]):
        prefix = directory / f"turns/{index:03d}"
        request_raw = prefix.with_name(prefix.name + "_http_request.body").read_bytes()
        require(request_raw == encode(request_body(expected_messages)), "audit.full_exact_history")
        require(sha(request_raw) == outcome["request_sha256"], "audit.request_binding")
        response_raw = prefix.with_name(prefix.name + "_http_response.body").read_bytes()
        require(sha(response_raw) == outcome["response_sha256"], "audit.response_binding")
        try:
            envelope = json.loads(response_raw) if response_raw else {}
        except (ValueError, TypeError):
            envelope = {}
        if not isinstance(envelope, dict):
            envelope = {}
        usages.append(envelope.get("usage"))
        if not outcome["public_content_returned"]:
            require(index == len(result["attempts"]) - 1, "audit.unknown_not_retried")
            continue
        raw = prefix.with_name(prefix.name + "_assistant.raw").read_bytes()
        require(
            envelope["choices"][0]["message"]["content"].encode() == raw,
            "audit.exact_model_content",
        )
        event = result["events"][index]
        require(
            event == read_json(prefix.with_name(prefix.name + "_event.json"))
            and sha(raw) == event["raw_sha256"],
            "audit.event_binding",
        )
        expected_messages.append({"role": "assistant", "content": raw.decode()})
        if event["protocol_error"]:
            expected_messages.append(
                {
                    "role": "user",
                    "content": encode({"interface_error": event["protocol_error"]}).decode(),
                }
            )
            continue
        model = strict_json(raw)
        if event["final"]:
            require(
                "final" in model and index == len(result["attempts"]) - 1,
                "audit.first_final_terminal",
            )
            require(model["final"] == result["final"], "audit.raw_final_not_rewritten")
            finals.append(index)
            break
        call = event["tool_call"]
        if call is None:
            expected_messages.append(
                {"role": "user", "content": encode({"receipt": "model_message_recorded"}).decode()}
            )
            continue
        require(
            call["name"] == model["tool"] and call["arguments"] == model.get("arguments", {}),
            "audit.explicit_arguments_not_repaired",
        )
        require(
            call["output"] == read_json(prefix.with_name(prefix.name + "_tool.json")),
            "audit.original_tool_output",
        )
        output = call["output"]
        expected_messages.append(
            {"role": "user", "content": encode({"tool_result": output}).decode()}
        )
        if call["name"] == "calculate":
            calculation_requests.append(
                {
                    "response_index": index,
                    "call_id": call["id"],
                    "expression": call["arguments"].get("expression")
                    if isinstance(call["arguments"], dict)
                    else None,
                    "execution_status": output["status"],
                }
            )
        if output["status"] != "ok":
            continue
        if call["name"] == "read_source" and "exact_value" in output["result"]:
            sid = output["result"]["numeric_source_id"]
            require(
                sid in call["arguments"]["locators"]
                and output["result"]["exact_value"] == private["facts"][sid]["value"],
                "audit.literal_source_retrieval",
            )
            numeric_results[call["id"]] = rational(output["result"]["exact_value"])
            symbolic_results[call["id"]] = reference_expression(sid, private["facts"])
        if call["name"] != "calculate":
            continue
        args = call["arguments"]
        variables = args.get("variables", {})
        declarations = args.get("sources", {})
        issues, bindings, num_env, sym_env = [], [], {}, {}

        def resolve(
            name,
            num_env=num_env,
            sym_env=sym_env,
            variables=variables,
            declarations=declarations,
            bindings=bindings,
            issues=issues,
        ):
            if name in num_env:
                return num_env[name]
            supplied = variables[name]
            if isinstance(supplied, dict) and set(supplied) == {"result_id"}:
                ref = supplied["result_id"]
                num_env[name] = numeric_results[ref]
                sym_env[name] = symbolic_results.get(ref)
                bindings.append(
                    {"variable": name, "kind": "actual_tool_result_reference", "result_id": ref}
                )
                return num_env[name]
            value = supplied.get("value") if isinstance(supplied, dict) else supplied
            num_env[name] = rational(value)
            declared = declarations.get(name) if isinstance(declarations, dict) else None
            if declared is None and isinstance(supplied, dict):
                declared = supplied.get("source", supplied.get("source_id"))
            if isinstance(declared, str) and declared in private["facts"]:
                fact = private["facts"][declared]
                aligned = num_env[name] == rational(fact["value"])
                bindings.append(
                    {
                        "variable": name,
                        "kind": "explicit_source",
                        "source_id": declared,
                        "provided_exact_value": str(num_env[name]),
                        "source_value": fact["value"],
                        "numeric_alignment": bool(aligned),
                    }
                )
                if not aligned:
                    issues.append(
                        "value_differs_from_source_literal_requires_transformation_review:" + name
                    )
                sym_env[name] = reference_expression(declared, private["facts"])
            else:
                bindings.append(
                    {
                        "variable": name,
                        "kind": "unlinked_numeric_constant",
                        "model_declaration": declared,
                    }
                )
                # No same-number source matching. A true arithmetic constant can
                # still appear in a source-symbolically established full expression.
                sym_env[name] = num_env[name]
            return num_env[name]

        value = parse_math(args["expression"], resolve)
        require(
            value == rational(output["result"]["exact_value"]),
            "audit.independent_actual_arithmetic",
        )
        numeric_results[call["id"]] = value
        try:
            symbolic = parse_math(args["expression"], lambda name, env=sym_env: env[name])
            match = symbolic_match(symbolic, private)
        except (ValueError, TypeError, KeyError):
            symbolic, match = None, None
        symbolic_results[call["id"]] = symbolic
        calculations.append(
            {
                "response_index": index,
                "call_id": call["id"],
                "original_expression": args["expression"],
                "pre_execution_relationship_observed": True,
                "actual_exact_value": str(value),
                "independent_execution_verified": True,
                "operation_count": output["result"]["operation_count"],
                "dependency_depth": output["result"]["dependency_depth"],
                "used_result_ids": output["result"]["used_result_ids"],
                "variable_bindings": bindings,
                "binding_issues": issues,
                "source_symbolic_target_match": match,
                "symbolic_nonmatch_is_not_automatic_task_failure": True,
                "original_public_message": model.get("message"),
                "actual_expression_not_host_rewritten_as_model_formula": True,
            }
        )
        citations.extend(b["source_id"] for b in bindings if b["kind"] == "explicit_source")
    require(
        expected_messages == read_json(directory / "messages.json"),
        "audit.persisted_complete_history",
    )
    require(
        len(finals) <= 1 and (result["terminal"] == "model_final") == bool(finals),
        "audit.final_stop_contract",
    )
    return record(
        "post_generation_audit",
        task_id=public["task_id"],
        origin=result["origin"],
        terminal=result["terminal"],
        result_id=result["id"],
        model_requests=result["model_requests"],
        tool_calls=result["tool_calls"],
        raw_model_and_history_verified=True,
        calculations=calculations,
        first_final_index=finals[0] if finals else None,
        raw_final=result["final"],
        source_ids_explicitly_used=sorted(set(citations)),
        pre_execution_formula_observed=any(
            isinstance(r["expression"], str) and r["expression"] for r in calculation_requests
        ),
        formula_detection_scope="original calculator requests; public prose is reviewed separately",
        calculation_requests=calculation_requests,
        tool_errors=sum(
            e["tool_call"] is not None and e["tool_call"]["output"]["status"] == "error"
            for e in result["events"]
        ),
        public_messages_without_tool=sum(
            e["tool_call"] is None and not e["final"] for e in result["events"]
        ),
        usages=usages,
        no_online_answer_feedback=True,
        no_final_retry=True,
    )


def cost_summary(online_directory):
    """Account from durable files, including unknown sessions without a result.json."""
    rows = []
    for registration in read_json(online_directory / "launch.json")["registrations"]:
        directory = online_directory / "sessions" / registration["label"]
        turns = directory / "turns"
        reservations = [read_json(p) for p in sorted(turns.glob("*_reservation.json"))]
        outcomes = [read_json(p) for p in sorted(turns.glob("*_outcome.json"))]
        outputs = [read_json(p) for p in sorted(turns.glob("*_tool.json"))]
        numeric = [o["result"] for o in outputs if o["tool"] == "calculate" and o["status"] == "ok"]
        usage_rows = [o.get("usage") for o in outcomes]
        usage_fields = (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        )
        usage = {}
        for field in usage_fields:
            values = [
                u[field] for u in usage_rows if isinstance(u, dict) and type(u.get(field)) is int
            ]
            usage[field] = {
                "observed_sum": sum(values),
                "observed_attempts": len(values),
                "missing_attempts": len(reservations) - len(values),
                "complete_sum": sum(values) if len(values) == len(reservations) else None,
            }
        rows.append(
            {
                "label": registration["label"],
                "task_key": registration["task_key"],
                "reserved_attempts": len(reservations),
                "recorded_outcomes": len(outcomes),
                "public_model_responses": len(list(turns.glob("*_assistant.raw"))),
                "tool_calls": len(outputs),
                "tool_errors": sum(o["status"] != "ok" for o in outputs),
                "successful_calculations": len(numeric),
                "successful_expression_operations": sum(n["operation_count"] for n in numeric),
                "maximum_expression_dependency_depth": max(
                    (n["dependency_depth"] for n in numeric), default=0
                ),
                "http_request_bytes": sum(r["request_bytes"] for r in reservations),
                "maximum_http_request_bytes": max(
                    (r["request_bytes"] for r in reservations), default=0
                ),
                "http_response_bytes": sum(
                    p.stat().st_size for p in turns.glob("*_http_response.body")
                ),
                "raw_assistant_bytes": sum(p.stat().st_size for p in turns.glob("*_assistant.raw")),
                "summed_request_elapsed_ns": sum(o["elapsed_ns"] for o in outcomes),
                "reserved_token_allowance": sum(
                    r["reserved_token_allowance"] for r in reservations
                ),
                "provider_usage": usage,
            }
        )
    additive = (
        "reserved_attempts",
        "recorded_outcomes",
        "public_model_responses",
        "tool_calls",
        "tool_errors",
        "successful_calculations",
        "successful_expression_operations",
        "http_request_bytes",
        "http_response_bytes",
        "raw_assistant_bytes",
        "summed_request_elapsed_ns",
        "reserved_token_allowance",
    )
    aggregate = {field: sum(r[field] for r in rows) for field in additive}
    aggregate["maximum_http_request_bytes"] = max(r["maximum_http_request_bytes"] for r in rows)
    aggregate["provider_usage"] = {}
    for field in usage_fields:
        metrics = [r["provider_usage"][field] for r in rows]
        known = sum(m["observed_sum"] for m in metrics)
        missing = sum(m["missing_attempts"] for m in metrics)
        aggregate["provider_usage"][field] = {
            "observed_sum": known,
            "observed_attempts": sum(m["observed_attempts"] for m in metrics),
            "missing_attempts": missing,
            "complete_sum": None if missing else known,
        }
    return {
        "rows": rows,
        "aggregate": aggregate,
        "all_registered_sessions_included": True,
        "summed_latency_is_not_parallel_wall_clock": True,
        "usage_missing_is_not_zero": True,
        "expression_operations_are_not_old_atomic_actions": True,
    }


def final_number_and_unit(final, question):
    value = final.get("value") if isinstance(final, dict) else None
    unit = final.get("unit") if isinstance(final, dict) else None
    if unit is None:
        unit = (
            "percent"
            if "percent" in question.lower()
            else "USD_million"
            if "millions of dollars" in question.lower()
            else None
        )
    return value, unit


def normalize_unit(unit):
    if not isinstance(unit, str):
        return None
    text = unit.lower().strip().replace("_", " ")
    if text in {"%", "percent", "percentage", "per cent"}:
        return "percent"
    if text in {
        "usd million",
        "usd millions",
        "million usd",
        "millions usd",
        "million dollars",
        "millions of dollars",
        "$ million",
        "$ millions",
    }:
        return "USD_million"
    return text


def answer_score(value, unit, private):
    if value is None:
        return {
            "numeric_correct": None,
            "unit_correct": None,
            "task_answer_status": "UNDETERMINED",
            "reason": "no_unambiguous_published_number",
        }
    try:
        actual = Fraction(str(value).replace(",", "").rstrip("%"))
        target = reference_expression(private["target"], private["facts"])
        target = target.subs(
            {
                reference_expression(sid, private["facts"]): rational(f["value"])
                for sid, f in private["facts"].items()
            }
        )
        target = Fraction(int(sp.numer(target)), int(sp.denom(target)))
        if "/" in str(value):
            tolerance = Fraction(0)
        else:
            decimal = Decimal(str(value).replace(",", "").rstrip("%"))
            quantum = Fraction(Decimal(1).scaleb(decimal.as_tuple().exponent))
            tolerance = min(abs(quantum), Fraction(1, 100)) / 2
        numeric = abs(actual - target) <= tolerance
    except (ValueError, ZeroDivisionError, InvalidOperation, TypeError):
        return {
            "numeric_correct": None,
            "unit_correct": None,
            "task_answer_status": "UNDETERMINED",
            "reason": "unsupported_public_number",
        }
    unit_match = normalize_unit(unit) == private["unit"]
    return {
        "published_value": str(value),
        "canonical_unit": normalize_unit(unit),
        "numeric_correct": numeric,
        "unit_correct": unit_match,
        "task_answer_status": "PASS" if numeric and unit_match else "FAIL",
        "reference_exact_value": str(target),
        "rounding_tolerance": str(tolerance),
        "lack_of_formula_does_not_change_numeric_score": True,
    }


def assess(root):
    output = root / OUTPUT
    manifest(output / "online")
    summary = read_json(output / "online/summary.json")
    require(summary["all_workers_terminated"], "assessment.only_after_generation")
    verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
    private = read_json(output / "preparation/private/evaluation_targets.json")
    store = DurableStore(output / "assessment")
    audits, templates = [], {}
    for row in summary["rows"]:
        label, key = row["label"], row["task_key"]
        public = read_json(output / f"preparation/public/{key}.json")
        if "result_id" not in row:
            audit = record(
                "post_generation_audit",
                label=label,
                terminal=row["terminal"],
                raw_final=None,
                calculations=[],
                first_final_index=None,
                pre_execution_formula_observed=False,
                usages=[],
            )
        else:
            audit = audit_session(output / "online/sessions" / label, public, private[key])
        value, unit = final_number_and_unit(audit["raw_final"], public["question"])
        audit = record(
            "session_assessment",
            label=label,
            task_key=key,
            **{k: v for k, v in audit.items() if k not in {"id", "schema_version", "label"}},
            automatic_answer_score=answer_score(value, unit, private[key]),
        )
        store.json("sessions/" + label + ".json", audit)
        audits.append(audit)
        templates[label] = {
            "published_value": value,
            "published_unit": unit,
            "answer_override_evidence": [],
            "answer_calculation_id": None,
            "final_answer_consistency": {
                "status": "UNDETERMINED",
                "evidence": [],
                "explanation": "Check actual Final prose, direction, numeric fields and units "
                "together.",
            },
            **{
                field: {
                    "status": "UNDETERMINED",
                    "evidence": [],
                    "explanation": "Awaiting finite independent semantic review.",
                }
                for field in REVIEW_FIELDS
            },
            "planning_observations": {"text": "", "evidence": []},
        }
    store.json("review_template.json", templates)
    report = record(
        "assessment_report",
        rows=audits,
        all_generation_finished_before_assessment=True,
        costs=cost_summary(output / "online"),
        provider_calls=0,
        student=False,
        tokenizer=False,
        quotient=False,
    )
    store.json("report.json", report)
    seal_directory(store, kind="autonomous_assessment_manifest", report_id=report["id"])
    return report


def verify_quotes(review, raw_messages):
    evidence = list(review["answer_override_evidence"])
    for field in (*REVIEW_FIELDS, "final_answer_consistency"):
        require(
            review[field]["status"] in {"PASS", "FAIL", "UNDETERMINED", "NOT_ESTABLISHED"},
            "review.status",
        )
        require(
            review[field]["status"] not in {"PASS", "FAIL"} or review[field]["evidence"],
            "review.semantic_claim_has_evidence",
        )
        evidence.extend(review[field]["evidence"])
    evidence.extend(review["planning_observations"]["evidence"])
    for item in evidence:
        index, quote = item["response_index"], item["quote"]
        require(
            isinstance(index, int)
            and index in raw_messages
            and isinstance(quote, str)
            and quote
            and quote in raw_messages[index],
            "review.actual_model_quote",
        )


def reviewed_answer_score(numeric_score, review):
    """A correct numeric field cannot cancel contradictory final-answer prose or direction."""
    status = review["final_answer_consistency"]["status"]
    result = {**numeric_score, "final_answer_consistency": status}
    if status == "FAIL":
        result.update(
            task_answer_status="FAIL", reason="contradictory_or_inapplicable_final_answer"
        )
    elif status != "PASS" and numeric_score["task_answer_status"] == "PASS":
        result.update(
            task_answer_status="UNDETERMINED", reason="final_answer_interpretation_unresolved"
        )
    return result


def trace_checks(audit, review, score):
    """Evidence-time and publication constraints, separate from manual financial judgment."""
    selected = next(
        (c for c in audit["calculations"] if c["call_id"] == review.get("answer_calculation_id")),
        None,
    )
    temporal = bool(selected) and all(
        any(e["response_index"] <= selected["response_index"] for e in review[field]["evidence"])
        for field in REVIEW_FIELDS[:3]
    )
    numeric = (
        bool(selected)
        and score.get("numeric_correct") is True
        and abs(
            Fraction(str(review["published_value"]).replace(",", "").rstrip("%"))
            - Fraction(selected["actual_exact_value"])
        )
        <= Fraction(score["rounding_tolerance"])
    )
    final = audit["raw_final"]
    explicit = final.get("result_id") if isinstance(final, dict) else None
    reference = explicit is None or (bool(selected) and explicit == selected["call_id"])
    semantic = all(review[field]["status"] == "PASS" for field in REVIEW_FIELDS)
    return {
        "formula_driven_trace_verified": bool(
            selected
            and temporal
            and numeric
            and reference
            and semantic
            and score["task_answer_status"] == "PASS"
        ),
        "reviewed_formula_data_units_precede_selected_execution": temporal,
        "selected_tool_result_numerically_matches_publication": numeric,
        "explicit_final_result_reference_consistent": reference,
    }


def closeout(root, reviews_path):
    require(reviews_path is not None, "closeout.reviews_required")
    output = root / OUTPUT
    manifest(output / "assessment")
    history_guard(root)
    verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
    reviews = read_json(reviews_path)
    assessments = read_json(output / "assessment/report.json")["rows"]
    private = read_json(output / "preparation/private/evaluation_targets.json")
    require(set(reviews) == {r["label"] for r in assessments}, "review.every_registered_session")
    store = DurableStore(output / "closeout")
    store.write("posthoc_reviews.json", reviews_path.read_bytes())
    rows = []
    for audit in assessments:
        label, review = audit["label"], reviews[audit["label"]]
        directory = output / "online/sessions" / label
        raw_messages = {
            int(p.name[:3]): p.read_text() for p in (directory / "turns").glob("*_assistant.raw")
        }
        verify_quotes(review, raw_messages)
        require(
            all(
                e["response_index"] == audit["first_final_index"]
                for e in review["final_answer_consistency"]["evidence"]
            ),
            "review.final_answer_consistency_uses_actual_final",
        )
        inferred_value, inferred_unit = final_number_and_unit(
            audit["raw_final"],
            read_json(output / f"preparation/public/{audit['task_key']}.json")["question"],
        )
        if (
            str(inferred_value) != str(review["published_value"])
            or normalize_unit(inferred_unit) != normalize_unit(review["published_unit"])
        ) and review["published_value"] is not None:
            require(
                bool(review["answer_override_evidence"])
                and all(
                    e["response_index"] == audit["first_final_index"]
                    for e in review["answer_override_evidence"]
                ),
                "review.answer_from_actual_final",
            )
            require(
                str(review["published_value"]).replace(",", "").replace(" ", "")
                in " ".join(e["quote"] for e in review["answer_override_evidence"])
                .replace(",", "")
                .replace(" ", ""),
                "review.published_number_is_quoted_not_reference_filled",
            )
        score = reviewed_answer_score(
            answer_score(
                review["published_value"], review["published_unit"], private[audit["task_key"]]
            ),
            review,
        )
        if audit["terminal"] != "model_final":
            score = {
                **score,
                "task_answer_status": "UNDETERMINED"
                if audit["terminal"].startswith("unknown")
                else "FAIL",
                "reason": "no_model_final",
            }
        row = record(
            "reviewed_session",
            label=label,
            task_key=audit["task_key"],
            assessment_id=audit["id"],
            answer=score,
            **trace_checks(audit, review, score),
            pre_execution_relation=audit["pre_execution_formula_observed"],
            semantic_review=review,
            reviewer_is_unblinded=True,
            quote_checker_certifies_semantics=False,
            answer_calculation_id=review.get("answer_calculation_id"),
            execution_checks_are_independent=True,
            final_without_calculation_not_promoted=True,
        )
        store.json("sessions/" + label + ".json", row)
        rows.append(row)
    counts = Counter(r["answer"]["task_answer_status"] for r in rows)
    report = record(
        "final_report",
        registered=12,
        task_weights={key: "1/6" for key in TASKS},
        costs=read_json(output / "assessment/report.json")["costs"],
        rows=rows,
        answer_counts=dict(counts),
        formula_driven_verified=sum(r["formula_driven_trace_verified"] for r in rows),
        by_task={
            key: {
                "registered": 2,
                "answer_counts": dict(
                    Counter(r["answer"]["task_answer_status"] for r in rows if r["task_key"] == key)
                ),
                "formula_driven_verified": sum(
                    r["formula_driven_trace_verified"] for r in rows if r["task_key"] == key
                ),
            }
            for key in TASKS
        },
        provider_calls_after_generation=0,
        no_new_quotient=True,
        no_token_export=True,
        student=False,
        gpu=False,
        vtdo=False,
        old_outcomes_unchanged=True,
        different_architecture_not_single_factor_effect=True,
    )
    store.json("report.json", report)
    seal_directory(store, kind="autonomous_closeout_manifest", report_id=report["id"])
    return report
