"""Pure CPU semantics for one response after a frozen public Probe prefix.

No file reader, model, tokenizer, API, evaluator R1, or private answer is used.
The original training read_source/calculate functions rebuild the small public
tool state and execute the prediction. Exact rational source expressions admit
algebraically equivalent calculations without accepting numeric coincidence or
unsupported pasted answers. Unproved alternative source relations stay unknown.
This is conditional capability, never autonomous task financial qualification.
"""

import ast
import copy
from fractions import Fraction

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import worker as training
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

CONTRACT = "original_training_read_source_calculate_public_prefix_semantics.v1"
ERRORS = (ValueError, TypeError, KeyError, ZeroDivisionError, SyntaxError, RecursionError)


class EquivalenceUnresolved(ValueError):
    """Bounded symbolic analysis may abstain; abstention is not model failure."""


def _poly_add(left, right):
    result = dict(left)
    for key, value in right.items():
        result[key] = result.get(key, Fraction()) + value
        if not result[key]:
            del result[key]
    if len(result) > 2048:
        raise EquivalenceUnresolved("polynomial_term_limit")
    return result


def _poly_multiply(left, right):
    if len(left) * len(right) > 65536:
        raise EquivalenceUnresolved("polynomial_product_limit")
    result = {}
    for a, x in left.items():
        for b, y in right.items():
            key = tuple(sorted(a + b))
            if len(key) > 64:
                raise EquivalenceUnresolved("polynomial_degree_limit")
            result[key] = result.get(key, Fraction()) + x * y
    return _poly_add({}, {key: value for key, value in result.items() if value})


class RationalExpression:
    def __init__(self, numerator, denominator=None):
        self.n = numerator
        self.d = {(): Fraction(1)} if denominator is None else denominator

    @staticmethod
    def constant(value):
        value = Fraction(value)
        return RationalExpression({(): value} if value else {})

    @staticmethod
    def symbol(name):
        return RationalExpression({(name,): Fraction(1)})

    def add(self, other):
        return RationalExpression(
            _poly_add(_poly_multiply(self.n, other.d), _poly_multiply(other.n, self.d)),
            _poly_multiply(self.d, other.d),
        )

    def negate(self):
        return RationalExpression({key: -value for key, value in self.n.items()}, self.d)

    def multiply(self, other):
        return RationalExpression(_poly_multiply(self.n, other.n), _poly_multiply(self.d, other.d))

    def divide(self, other):
        if not other.n:
            raise EquivalenceUnresolved("symbolic_zero_denominator")
        return RationalExpression(_poly_multiply(self.n, other.d), _poly_multiply(self.d, other.n))

    def power(self, exponent):
        if type(exponent) is not int or abs(exponent) > 16:
            raise EquivalenceUnresolved("symbolic_power_limit")
        result = RationalExpression.constant(1)
        for _ in range(abs(exponent)):
            result = result.multiply(self)
        return RationalExpression.constant(1).divide(result) if exponent < 0 else result

    def equals(self, other):
        return _poly_multiply(self.n, other.d) == _poly_multiply(other.n, self.d)

    def leaves(self):
        return {name for poly in (self.n, self.d) for monomial in poly for name in monomial}


def _expression(arguments, symbolic):
    """Build only bounded rational arithmetic after the real tool accepted it."""
    expression = arguments["expression"]
    variables = arguments.get("variables", {})

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            return RationalExpression.constant(
                training.number(ast.get_source_segment(expression, node))
            )
        if isinstance(node, ast.Name):
            value = variables[node.id]
            if isinstance(value, dict) and set(value) == {"result_id"}:
                result = symbolic.get(value["result_id"])
                if result is None:
                    raise EquivalenceUnresolved("prior_symbolic_support_unavailable")
                return result
            if isinstance(value, dict) and "value" in value:
                value = value["value"]
            return RationalExpression.constant(training.number(value))
        if isinstance(node, ast.UnaryOp):
            child = visit(node.operand)
            return child.negate() if isinstance(node.op, ast.USub) else child
        if isinstance(node, ast.BinOp):
            left = visit(node.left)
            if isinstance(node.op, ast.Pow):
                if not isinstance(node.right, ast.Constant):
                    raise EquivalenceUnresolved("nonliteral_power")
                return left.power(node.right.value)
            right = visit(node.right)
            if isinstance(node.op, ast.Add):
                return left.add(right)
            if isinstance(node.op, ast.Sub):
                return left.add(right.negate())
            if isinstance(node.op, ast.Mult):
                return left.multiply(right)
            if isinstance(node.op, ast.Div):
                return left.divide(right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            children = node.args
            if len(children) == 1 and isinstance(children[0], (ast.List, ast.Tuple)):
                children = children[0].elts
            if node.func.id in {"sum", "avg"}:
                result = RationalExpression.constant(0)
                for child in children:
                    result = result.add(visit(child))
                if node.func.id == "avg":
                    result = result.divide(RationalExpression.constant(len(children)))
                return result
        raise EquivalenceUnresolved("accepted_tool_expression_outside_bounded_rational_subset")

    return visit(ast.parse(expression, mode="eval").body)


def _execute(choice, public, previous, symbolic):
    """Original training contract only; final parsing is handled separately."""
    training.require(
        isinstance(choice, dict) and set(choice) == {"tool", "arguments"}, "expected_tool_or_final"
    )
    call = {
        "call_id": "tool:" + str(len(previous) + 1),
        "tool": choice["tool"],
        "arguments": copy.deepcopy(choice["arguments"]),
        "status": "ok",
        "result": None,
    }
    support, symbolic_error = None, None
    try:
        if choice["tool"] == "read_source":
            call["result"] = training.read_source(choice["arguments"], public)
            locator = call["result"]["source_locator"]
            source = {"source_locator": locator, "raw_sha256": call["result"]["source_raw_sha256"]}
            support = RationalExpression.symbol(p.sha(p.encode(source)))
        elif choice["tool"] == "calculate":
            call["result"] = training.calculate_with_units(choice["arguments"], previous)
            try:
                support = _expression(choice["arguments"], symbolic)
            except EquivalenceUnresolved as error:
                symbolic_error = str(error)
        else:
            raise ValueError("tool.unknown_tool")
    except ERRORS as error:
        call.update(status="error", error=str(error))
    return call, support, symbolic_error


def _history(prefix):
    messages = prefix["input_messages"]
    p.require(
        messages[0]["role"] == "system" and messages[1]["role"] == "user",
        "prefix_semantics.original_training_public_history",
    )
    public = training.strict_json(messages[1]["content"])
    p.require(
        set(public)
        == {"question", "sources", "quantity_contract", "source_policy", "tool_contract"},
        "prefix_semantics.original_public_source_document",
    )
    previous, symbolic = {}, {}
    # This is a few public-history tools, not a repeat audit of encoded packages.
    for index in range(2, len(messages), 2):
        assistant, feedback = messages[index : index + 2]
        p.require(
            assistant["role"] == "assistant" and feedback["role"] == "user",
            "prefix_semantics.complete_public_tool_feedback_pair",
        )
        observation = training.strict_json(feedback["content"])
        if "tool_observation" not in observation:
            continue  # Earlier formatting failures provide no numeric tool result.
        call, support, _ = _execute(
            training.strict_json(assistant["content"]), public, previous, symbolic
        )
        p.require(
            call == observation["tool_observation"],
            "prefix_semantics.original_tool_feedback_replay",
        )
        previous[call["call_id"]] = call
        symbolic[call["call_id"]] = support
    return public, previous, symbolic


def _canonical(result):
    dimension, factor = training.UNITS[result["unit"]]
    return dimension, training.number(result["exact_value"]) * factor


def _rounded(value, decimal_places):
    p.require(
        type(decimal_places) is int and 0 <= decimal_places <= 12,
        "prefix_semantics.public_rounding_precision",
    )
    scale = 10**decimal_places
    scaled = abs(value) * scale
    magnitude = (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)
    return Fraction(magnitude if value >= 0 else -magnitude, scale)


def _reference(prefix, public, previous, symbolic):
    reference = training.strict_json(prefix["reference_response"])
    if prefix["boundary"] == "calculate":
        call, support, unresolved = _execute(reference, public, previous, symbolic)
        p.require(
            call["status"] == "ok" and call["tool"] == "calculate",
            "prefix_semantics.public_reference_calculation_executable",
        )
        return call, support, unresolved
    result_id = reference["final"]["result_id"]
    p.require(
        result_id in previous and previous[result_id]["status"] == "ok",
        "prefix_semantics.public_reference_Final_existing_result",
    )
    return previous[result_id], symbolic[result_id], None


def _compare(call, support, reference, reference_support):
    numeric_match = _canonical(call["result"]) == _canonical(reference["result"])
    equal, reason = None, None
    if support is not None and reference_support is not None:
        try:
            equal = support.equals(reference_support)
        except EquivalenceUnresolved as error:
            reason = str(error)
    else:
        reason = "source_expression_unavailable"
    if not numeric_match:
        quantity = False
    elif equal is True:
        quantity = True
    elif (
        equal is False
        and support is not None
        and reference_support is not None
        and support.leaves() == reference_support.leaves()
    ):
        quantity = False  # Same source leaves, different algebra, coincident numeric value.
    else:
        quantity = None  # Could be another public relation; no private oracle is consulted.
        reason = reason or "numeric_match_but_alternative_public_support_relation_not_proven"
    return {
        "numeric_quantity_matches_public_reference": numeric_match,
        "source_expression_equivalent_to_public_reference": equal,
        "requested_quantity_matches_public_reference": quantity,
        "quantity_analysis_unresolved_reason": reason,
    }


def grade_prefix(prefix_record, prediction_record):
    """Consume records only; return semantics.json contents without any IO."""
    for record in (prefix_record, prediction_record):
        p.checked_record(record, record["schema_version"].rsplit(".", 1)[-1])
    p.require(
        prediction_record["prefix_record_id"] == prefix_record["id"]
        and prediction_record["prefix_record_sha256"] == p.sha(p.encode(prefix_record))
        and prediction_record["boundary"] == prefix_record["boundary"],
        "prefix_semantics.exact_prediction_prefix_binding",
    )
    public, previous, symbolic = _history(prefix_record)
    reference, reference_support, reference_unresolved = _reference(
        prefix_record, public, previous, symbolic
    )
    raw = prediction_record["raw_response"]
    parsed, parse_error = None, None
    if raw is not None:
        try:
            parsed = training.strict_json(raw)
        except ERRORS as error:
            parse_error = str(error)
    fields = {
        "strict_json_object": isinstance(parsed, dict),
        "parse_error": parse_error,
        "immediate_final": isinstance(parsed, dict) and "final" in parsed,
        "predicted_tool": parsed.get("tool") if isinstance(parsed, dict) else None,
        "tool_executable": None,
        "referenced_results_supported": None,
        "source_expression_equivalent_to_public_reference": None,
        "numeric_quantity_matches_public_reference": None,
        "requested_quantity_matches_public_reference": None,
        "final_unit_matches_request": None,
        "final_value_matches_supported_result": None,
        "final_quantity_matches_public_reference": None,
        "semantic_calculation_success": False,
        "semantic_immediate_final_success": False,
        "quantity_analysis_unresolved_reason": reference_unresolved,
        "executed_tool": None,
        "execution_or_final_error": None,
    }
    call, support = None, None
    if not isinstance(parsed, dict):
        status = "NO_MODEL_RESPONSE" if raw is None else "INVALID_JSON_OBJECT"
    elif fields["immediate_final"]:
        status = "IMMEDIATE_FINAL_SEMANTIC_FAIL_OR_UNDETERMINED"
        final = parsed["final"]
        try:
            p.require(isinstance(final, dict), "prefix_semantics.final_object")
            result_id = final.get("result_id")
            p.require(isinstance(result_id, str), "prefix_semantics.final_result_id")
            call = previous.get(result_id)
            fields["referenced_results_supported"] = bool(call and call["status"] == "ok")
            p.require(
                fields["referenced_results_supported"], "prefix_semantics.Final_supported_reference"
            )
            support = symbolic.get(result_id)
            fields.update(_compare(call, support, reference, reference_support))
            contract = public["quantity_contract"]
            p.require(
                contract["rounding"] == "half away from zero",
                "prefix_semantics.registered_rounding",
            )
            fields["final_unit_matches_request"] = final.get("unit") == contract["unit"]
            quantity = training.number(final.get("value"))
            supported, _ = training.convert(
                training.number(call["result"]["exact_value"]),
                call["result"]["unit"],
                final.get("unit"),
            )
            expected, _ = training.convert(
                training.number(reference["result"]["exact_value"]),
                reference["result"]["unit"],
                final.get("unit"),
            )
            fields["final_value_matches_supported_result"] = quantity == _rounded(
                supported, contract["decimal_places"]
            )
            fields["final_quantity_matches_public_reference"] = quantity == _rounded(
                expected, contract["decimal_places"]
            )
            fields["semantic_immediate_final_success"] = all(
                fields[key] is True
                for key in (
                    "referenced_results_supported",
                    "requested_quantity_matches_public_reference",
                    "final_unit_matches_request",
                    "final_value_matches_supported_result",
                    "final_quantity_matches_public_reference",
                )
            )
            if fields["semantic_immediate_final_success"]:
                status = "IMMEDIATE_FINAL_SEMANTIC_PASS"
        except ERRORS as error:
            fields["execution_or_final_error"] = str(error)
    else:
        try:
            call, support, symbolic_error = _execute(parsed, public, previous, symbolic)
            fields["executed_tool"] = call
            fields["tool_executable"] = call["status"] == "ok"
            fields["execution_or_final_error"] = call.get("error")
            if call["status"] == "ok":
                result = call["result"]
                refs = result.get("used_result_ids", [])
                fields["referenced_results_supported"] = (
                    bool(refs) and all(previous[ref]["status"] == "ok" for ref in refs)
                    if call["tool"] == "calculate"
                    else bool(result.get("source_locator"))
                )
                fields.update(_compare(call, support, reference, reference_support))
                if symbolic_error:
                    fields["quantity_analysis_unresolved_reason"] = symbolic_error
                fields["semantic_calculation_success"] = (
                    call["tool"] == "calculate"
                    and fields["referenced_results_supported"] is True
                    and fields["requested_quantity_matches_public_reference"] is True
                )
            if prefix_record["boundary"] == "final":
                status = "CONTINUED_TOOL_NOT_IMMEDIATE_FINAL"
            else:
                status = (
                    "CALCULATION_SEMANTIC_PASS"
                    if fields["semantic_calculation_success"]
                    else "TOOL_RESPONSE_SEMANTIC_FAIL_OR_UNDETERMINED"
                )
        except ERRORS as error:
            fields["tool_executable"] = False
            fields["execution_or_final_error"] = str(error)
            status = "INVALID_TOOL_PROTOCOL"
    return p.record(
        "delivery_prefix_semantics",
        contract=CONTRACT,
        status=status,
        **fields,
        prefix_record_id=prefix_record["id"],
        prediction_record_id=prediction_record["id"],
        boundary=prefix_record["boundary"],
        task_id=prefix_record["task_id"],
        source_package_id=prefix_record.get("source_package_id"),
        model_identity_id=prediction_record.get("model_identity_id"),
        diagnostic_scope=prefix_record.get("diagnostic_scope"),
        public_reference_source=(
            "frozen qualified Probe public next response and public tool history"
        ),
        final_referenced_result=call if fields["immediate_final"] else None,
        original_training_tools_used=True,
        evaluation_R1_tools_used=False,
        private_or_sealed_material_opened=False,
        model_calls=0,
        tokenizer_calls=0,
        reference_response_sent_to_model=False,
        exact_text_match_is_semantic_criterion=False,
        never_final_inferred=False,
        autonomous_task_success_claimed=False,
        financial_qualification_score=None,
        Probe_prefix_counted_as_Student_generation=False,
        limitations=[
            "conditional one-step diagnosis after Probe history; not autonomous completion",
            "quantity/support compare to public reference; not a fresh private financial audit",
            "rational source-equivalence accepts reordering, renaming, and unit conversion",
            "other public-support relations and nonrational expressions can remain undetermined",
            "continuing a tool means no immediate Final; never inability to deliver later",
        ],
    )
