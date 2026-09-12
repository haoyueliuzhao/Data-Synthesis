"""Offline finite-domain qualification over replayed executed support, not labels.

Rational symbolic equivalence admits reassociation, staged calculations, shared
rate bases and alternate equivalent expressions. It is deliberately not an
open-domain financial semantics classifier. Clean understood executions receive
fine event signatures; unresolved recovery or intent remains pending review.
Financial validity is never discarded just because that fine map is missing.
"""

import ast
from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction

from .worker import UNITS, convert, encode, generate, number, record, require


def _locator_key(locator):
    return encode(locator).decode()


def _semantic_source_aliases(fact_ids, native_bindings):
    """Equal values alone never create an alias: company, metric, definition,
    exact period and native definition must also agree. Caller certified these
    native bindings in its source manifest; unresolved sources stay separate.
    """
    representatives, aliases = {}, {}
    fields = ("entity_id", "metric_id", "source_definition_id", "native_definition")
    for fact in fact_ids:
        native = native_bindings.get(fact, {})
        if not all(key in native for key in fields):
            aliases[fact] = fact
            continue
        unit = "million USD" if native.get("source_kind") == "issuer_report_table" else "USD"
        value, _ = convert(number(native["record"]["val"]), unit, "million USD")
        identity = encode(
            {
                **{key: native[key] for key in fields},
                "start": native["record"].get("start"),
                "end": native["record"]["end"],
                "normalized_unit": "million USD",
                "exact_value": str(value),
            }
        )
        aliases[fact] = representatives.setdefault(identity, fact)
    return aliases


def source_fact_bindings(bundle, native_bindings):
    """Offline mapping from native provenance, never matching a fact by its value."""
    sources = {source["source_id"]: source for source in bundle["public"]["sources"]}
    bound = {}
    for identifier, native in native_bindings.items():
        if native.get("source_kind") == "issuer_report_table":
            source_id = native["table_id"]
            if source_id not in sources:
                continue
            source = sources[source_id]
            cells = native["record"]["cell_reference"]["cells"]
            require(source["raw_sha256"] == native["raw_sha256"], "assessment.table_source_hash")
            meaningful = []
            for cell in cells:
                require(
                    source["original_rows"][cell["row"]][cell["cell"]] == cell["text"],
                    "assessment.original_table_cell",
                )
                if cell["text"].strip() not in {"", "$"}:
                    meaningful.append([cell["row"], cell["cell"]])
            locator = {"source_id": source_id, "cells": meaningful}
        else:
            if identifier not in sources:
                continue
            source = sources[identifier]
            require(
                source["raw_sha256"] == native["raw_sha256"]
                and source["native_pointer"] == native["pointer"]
                and source["record"] == native["record"],
                "assessment.original_json_record",
            )
            locator = {"source_id": identifier, "native_pointer": native["pointer"]}
        key = _locator_key(locator)
        bound.setdefault(key, []).append(identifier)
    return bound


def _expression(expression, variables, sympy):
    tree = ast.parse(expression, mode="eval")
    require(sum(1 for _ in ast.walk(tree)) <= 256, "assessment.symbolic_node_limit")

    def visit(node):
        if isinstance(node, ast.Name):
            return variables[node.id]
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            return sympy.Rational(ast.get_source_segment(expression, node))
        if isinstance(node, ast.UnaryOp):
            return visit(node.operand) if isinstance(node.op, ast.UAdd) else -visit(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            require(
                isinstance(node.op, ast.Pow) and right.is_Integer and abs(int(right)) <= 8,
                "assessment.symbolic_power_limit",
            )
            return left ** int(right)
        if isinstance(node, ast.Call):
            children = (
                node.args[0].elts
                if len(node.args) == 1 and isinstance(node.args[0], (ast.List, ast.Tuple))
                else node.args
            )
            values = [visit(child) for child in children]
            if node.func.id == "sum":
                return sum(values)
            if node.func.id == "avg":
                return sum(values) / len(values)
            # Piecewise min/max/abs are not universally equivalent on free facts;
            # keep these valid-looking programs undecided for a later domain proof.
        raise ValueError("assessment.outside_rational_expression_domain")

    return sympy.cancel(visit(tree.body))


def _witness_expression(witness, symbols, sympy):
    outputs = {}
    inputs = witness["input_bindings"]
    for step in witness["operator_dag"]["operators"]:
        values = [
            symbols[inputs[arg["binding"]]] if "binding" in arg else outputs[arg["step"]]
            for arg in step["inputs"]
        ]
        operator = step["operator"]
        if operator == "difference":
            value = values[1] - values[0]
        elif operator == "linear_combination":
            value = sum(
                sympy.Rational(str(c)) * v
                for c, v in zip(step["params"]["coefficients"], values, strict=True)
            )
        elif operator == "ratio_percent":
            value = 100 * values[0] / values[1]
        elif operator == "sum":
            value = sum(values)
        else:
            raise ValueError("assessment.unregistered_oracle_operator:" + operator)
        outputs[step["step_id"]] = sympy.cancel(value)
    return outputs[witness["operator_dag"]["output_step"]], outputs


def _rounded(value, places):
    value = Fraction(value)
    with localcontext() as context:
        context.prec = 100
        return (Decimal(value.numerator) / Decimal(value.denominator)).quantize(
            Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP
        )


def assess_session(session, bundle, native_bindings):
    """Caller binds bundle/native manifest bytes. Online worker never sees these.

    ``native_bindings`` is the corresponding Build's unmodified fact-id keyed
    native_bindings.json, including issuer record.cell_reference.cells when used.
    """
    require(
        bundle["task_id"] == session["identity"]["task_id"]
        and bundle["family"] == session["identity"]["family"],
        "assessment.task_join",
    )
    require(
        bundle["public"] == __import__("json").loads(session["public_messages"][0]["content"]),
        "assessment.frozen_public_join",
    )
    replay = generate(
        session["public_messages"],
        session["identity"],
        scripted=[turn["raw_response"] for turn in session["turns"]],
        requested_basis=session["requested_basis"],
        max_responses=session["max_responses"],
        max_tools=session["max_tools"],
    )
    require(replay == session, "assessment.full_raw_history_and_tool_replay")
    outcome = {
        "session_id": session["id"],
        "task_id": bundle["task_id"],
        "bundle_id": bundle["id"],
        "requested_basis": session["requested_basis"],
        "financial_valid": False,
        "quantity_status": "UNDETERMINED",
        "support_status": "UNDETERMINED",
        "actual_method": "UNDETERMINED",
        "full_mapping_status": "PENDING_REVIEW",
        "full_class": None,
        "first_final_index": session["first_final_index"],
        "terminal": session["terminal"],
        "raw_history_and_tools_replayed": True,
        "origin": session["origin"],
        "training_eligible": False,
        "support_result_ids": [],
        "effective_fact_ids": [],
        "all_executions": [],
        "reason": None,
        "method_from_requested_label": False,
        "method_from_answer_equality": False,
        "method_from_oracle_string_equality": False,
        "finite_symbolic_domain": "+,-,*,/,bounded_integer_power,sum,avg",
    }
    final = session["raw_final"]
    if session["first_final_index"] is None:
        return record("assessment", **{**outcome, "reason": "no_final"})
    if not isinstance(final, dict) or not {"value", "unit", "result_id"} <= set(final):
        return record("assessment", **{**outcome, "reason": "final_shape_or_support_reference"})
    tools = {
        event["tool_call"]["call_id"]: event["tool_call"]
        for event in session["events"]
        if event["tool_call"]
    }
    outcome["all_executions"] = [
        {"result_id": key, "tool": tool["tool"], "status": tool["status"]}
        for key, tool in tools.items()
    ]
    target = bundle["private"]["canonical_target"]
    try:
        submitted, _ = convert(number(final["value"]), final["unit"], target["unit"])
        places = bundle["public"]["quantity_contract"]["decimal_places"]
        correct = _rounded(submitted, places) == _rounded(bundle["private"]["answer_exact"], places)
        outcome["quantity_status"] = "PASS" if correct else "FAIL"
        require(
            final["result_id"] in tools and tools[final["result_id"]]["status"] == "ok",
            "assessment.final_unknown_or_failed_result",
        )
        support = tools[final["result_id"]]["result"]
        supported, _ = convert(number(support["exact_value"]), support["unit"], target["unit"])
        require(
            _rounded(submitted, places) == _rounded(supported, places),
            "assessment.final_not_supported_by_named_result",
        )
        import sympy

        fact_ids = sorted(
            {
                fact
                for witness in bundle["private"]["basis_witnesses"]
                for fact in witness["input_bindings"].values()
            }
            | set(native_bindings)
        )
        aliases = _semantic_source_aliases(fact_ids, native_bindings)
        symbol_ids = {fact: i for i, fact in enumerate(sorted(set(aliases.values())))}
        symbols = {fact: sympy.Symbol("f" + str(symbol_ids[aliases[fact]])) for fact in fact_ids}
        lookup = source_fact_bindings(bundle, native_bindings)
        symbolic, support_ids, resolved_facts = {}, set(), set()

        def resolve(result_id):
            if result_id in symbolic:
                return symbolic[result_id]
            tool = tools[result_id]
            require(tool["status"] == "ok", "assessment.failed_support_result")
            support_ids.add(result_id)
            result = tool["result"]
            if tool["tool"] == "read_source":
                locator = dict(result["source_locator"])
                if "cells" in locator:
                    locator["cells"] = [
                        [cell["row"], cell["cell"]]
                        for cell in result["original_source_fragment"]
                        if cell["text"].strip() not in {"", "$"}
                    ]
                candidates = lookup.get(_locator_key(locator), [])
                require(len(candidates) == 1, "assessment.source_not_uniquely_bound_to_fact")
                # All fact symbols are normalized million USD. Actual tool value
                # is compared to the bound source, independently of Oracle answer.
                fact = candidates[0]
                resolved_facts.add(fact)
                native = native_bindings[fact]
                native_unit = (
                    "million USD" if native.get("source_kind") == "issuer_report_table" else "USD"
                )
                actual, _ = convert(number(native["record"]["val"]), native_unit, result["unit"])
                require(actual == number(result["exact_value"]), "assessment.source_value_replay")
                expr = symbols[fact] * 1000000 / sympy.Rational(str(UNITS[result["unit"]][1]))
            else:
                require(tool["tool"] == "calculate", "assessment.unsupported_numeric_tool")
                variables = {}
                for name, resolved in result["resolved_variables"].items():
                    ref = resolved["result_id"]
                    if ref:
                        variables[name] = resolve(ref) * sympy.Rational(
                            str(UNITS[tools[ref]["result"]["unit"]][1])
                        )
                    else:
                        variables[name] = sympy.Rational(resolved["exact_value"])
                expr = _expression(result["expression"], variables, sympy) / sympy.Rational(
                    str(UNITS[result["unit"]][1])
                )
            symbolic[result_id] = sympy.cancel(expr)
            return symbolic[result_id]

        actual = resolve(final["result_id"]) * sympy.Rational(
            str(UNITS[support["unit"]][1] / UNITS[target["unit"]][1])
        )
        witnesses = {}
        for witness in bundle["private"]["basis_witnesses"]:
            expression, steps = _witness_expression(witness, symbols, sympy)
            witnesses[witness["basis"]] = (witness, expression, steps)
        endpoint = witnesses.get("endpoint", witnesses.get("fixed_control_reference"))
        require(endpoint is not None, "assessment.endpoint_reference_available")
        expected = endpoint[1]
        replacements = {}
        movement = witnesses.get("movement")
        endpoint_inputs = endpoint[0]["input_bindings"]
        previous, current = (symbols[endpoint_inputs[key]] for key in ("previous", "current"))
        if movement:
            delta = movement[2].get("change", movement[1])
            certificate = bundle["private"]["relation_certificate"]
            certificate = certificate.get("base_relation_certificate", certificate)
            base_ids = certificate.get("previous_component_fact_ids")
            if base_ids:
                coefficients = certificate.get("previous_component_coefficients") or [1] * len(
                    base_ids
                )
                base = sum(
                    symbols[fact] * sympy.Rational(str(c))
                    for fact, c in zip(base_ids, coefficients, strict=True)
                )
                replacements[previous] = base
            else:
                base = previous
            replacements[current] = base + delta
        effective = actual.free_symbols
        normalized_actual = sympy.cancel(actual.subs(replacements, simultaneous=True))
        normalized_expected = sympy.cancel(expected.subs(replacements, simultaneous=True))
        require(
            sympy.cancel(normalized_actual - normalized_expected) == 0,
            "assessment.program_not_equivalent_to_financial_target",
        )
        endpoint_symbols = {previous, current}
        if not movement:
            method = "control"
        elif effective <= endpoint_symbols:
            method = "endpoint"
        elif current not in effective:
            method = "movement"
        else:
            method = "HYBRID_UNDETERMINED"
        outcome.update(
            financial_valid=correct,
            support_status="PASS",
            actual_method=method,
            support_result_ids=sorted(support_ids, key=lambda key: int(key.split(":")[1])),
            effective_fact_ids=sorted(
                fact for fact in resolved_facts if symbols[fact] in effective
            ),
            financial_program_equivalence="exact_rational_identity_under_source_bound_relations",
            reason=None if correct else "wrong_final_quantity",
        )
        # This fine executable-event projection is separate from method. Preserve
        # source choices, verification/revision executions and shared bases. The
        # original arithmetic spelling and requested condition are not class keys.
        final_support_ids = set(support_ids)
        signature_events, revision_edges, verification_ids, pending = [], [], [], []
        renamed = {symbol: sympy.Symbol(aliases[fact]) for fact, symbol in symbols.items()}

        def canonical(expr):
            return str(sympy.cancel(expr).xreplace(renamed))

        revised_ids = {
            tool["result"].get("revises_result_id")
            for tool in tools.values()
            if tool["status"] == "ok" and tool["tool"] == "calculate"
        }
        for result_id, tool in tools.items():
            if tool["status"] != "ok":
                pending.append("failed_tool_requires_complete_class_review")
                signature_events.append(
                    {"result_id": result_id, "status": "error", "error": tool.get("error")}
                )
                continue
            try:
                expr = resolve(result_id)
                result = tool["result"]
                role = "final_support" if result_id in final_support_ids else "source_exploration"
                if tool["tool"] == "calculate" and result_id not in final_support_ids:
                    if UNITS[result["unit"]][0] == UNITS[target["unit"]][0]:
                        in_target_unit = expr * sympy.Rational(
                            str(UNITS[result["unit"]][1] / UNITS[target["unit"]][1])
                        )
                        equivalent = (
                            sympy.cancel(
                                in_target_unit.subs(replacements, simultaneous=True)
                                - normalized_expected
                            )
                            == 0
                        )
                    else:
                        equivalent = False
                    if equivalent:
                        role = (
                            "redundant_target_recomputation"
                            if sympy.cancel(in_target_unit - actual) == 0
                            else "alternative_basis_target_cross_check"
                        )
                        verification_ids.append(
                            {
                                "result_id": result_id,
                                "kind": role,
                                "first_final_result_id": final["result_id"],
                            }
                        )
                    elif result_id in revised_ids:
                        role = "explicitly_revised_calculation"
                    else:
                        role = "non_support_calculation_intent_unresolved"
                        pending.append("non_support_calculation_intent_unresolved")
                entry = {
                    "result_id": result_id,
                    "kind": tool["tool"],
                    "role": role,
                    "canonical_program": canonical(expr),
                    "unit": result["unit"],
                    "used_result_ids": result.get("used_result_ids", []),
                    "source_locator": result.get("source_locator"),
                }
                revision = result.get("revises_result_id")
                if revision:
                    old = resolve(revision)
                    old_unit = tools[revision]["result"]["unit"]
                    require(
                        UNITS[old_unit][0] == UNITS[result["unit"]][0],
                        "assessment.revision_unit_conflict",
                    )
                    old = old * sympy.Rational(str(UNITS[old_unit][1] / UNITS[result["unit"]][1]))
                    revision_edges.append(
                        {
                            "from_result_id": revision,
                            "to_result_id": result_id,
                            "substantive_program_change": sympy.cancel(expr - old) != 0,
                            "revised_result_supports_first_final": result_id in final_support_ids,
                        }
                    )
                signature_events.append(entry)
            except (ValueError, TypeError, KeyError, ZeroDivisionError, RecursionError) as error:
                pending.append(str(error))
                signature_events.append(
                    {"result_id": result_id, "mapping_status": "UNDETERMINED", "reason": str(error)}
                )
        if any(event["protocol_error"] for event in session["events"]):
            pending.append("format_recovery_complete_class_review")
        if method == "HYBRID_UNDETERMINED":
            pending.append("hybrid_method_complete_class_review")
        signature = record(
            "finite_complete_signature",
            task_id=bundle["task_id"],
            surface_version_id=session["identity"]["surface_version_id"],
            actual_method=method,
            final_support_program=canonical(actual),
            events=signature_events,
            first_final_result_id=final["result_id"],
            revision_edges=revision_edges,
            target_cross_checks=verification_ids,
            shared_endpoint_base=(
                target["quantity"] == "relative_change"
                and method == "movement"
                and previous in effective
            ),
            requested_basis_omitted=True,
            original_expression_spelling_omitted=True,
            interpretation="bounded executable-event quotient; not inferred cognitive intent",
        )
        outcome.update(
            full_mapping_status="MAPPED" if not pending else "PENDING_REVIEW",
            full_class=signature["id"] if not pending else None,
            full_signature=signature,
            full_mapping_pending_reasons=sorted(set(pending)),
        )
    except (
        ValueError,
        TypeError,
        KeyError,
        ZeroDivisionError,
        SyntaxError,
        RecursionError,
    ) as error:
        outcome.update(reason=str(error), support_status="UNDETERMINED")
    return record("assessment", **outcome)
