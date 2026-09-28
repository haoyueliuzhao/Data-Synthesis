"""Offline public-only tools; no Python execution, network, files, or oracle access.

The ``prev:<call_id>.<path>`` notation is inspired by FinanceHarness's documented
structured references, not an integration of that project's runtime or code.
"""

from __future__ import annotations

import ast
import copy
import json
import math
import re
from decimal import Decimal, DecimalException, localcontext
from typing import Any

from .contracts import PublicTask, ToolCall, ToolEvent, invocation_identity, invocation_scope

LEGACY_REFERENCE_PROTOCOL = "technical-call-id-v1"
VISIBLE_REFERENCE_PROTOCOL = "visible-result-handle-v2"


class ToolInputError(ValueError):
    """An explicit model-visible argument or execution error."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _strict_object(raw: str) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ToolInputError(f"duplicate argument key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ToolInputError(f"non-finite JSON constant: {value}")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ToolInputError("tool arguments must be a JSON object")
    return value


def _fields(args: dict[str, Any], required: set[str], optional: set[str] = frozenset()):
    missing, extra = required - args.keys(), args.keys() - required - optional
    if missing or extra:
        raise ToolInputError(f"argument fields: missing={sorted(missing)}, extra={sorted(extra)}")


def _number(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ToolInputError("arithmetic values must be finite numbers or decimal strings")
    text = str(value)
    if len(text) > 256:
        raise ToolInputError("numeric literal is too long")
    try:
        number = Decimal(text)
    except DecimalException as error:
        raise ToolInputError(
            "invalid decimal value; units and commas are not auto-converted"
        ) from error
    if not number.is_finite() or abs(number) > Decimal("1e100"):
        raise ToolInputError("arithmetic value must be finite with magnitude <= 1e100")
    return number


def calculate(expression: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate only bounded scalar arithmetic by walking an AST (never eval/exec)."""
    if not isinstance(expression, str) or not expression or len(expression) > 2048:
        raise ToolInputError("expression must be a nonempty string of at most 2048 characters")
    variables = {} if variables is None else variables
    if not isinstance(variables, dict) or len(variables) > 64:
        raise ToolInputError("variables must be an object with at most 64 entries")
    numbers = {}
    for name, value in variables.items():
        if not isinstance(name, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name) is None:
            raise ToolInputError("variable names must be simple non-private identifiers")
        numbers[name] = _number(value)
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as error:
        raise ToolInputError("invalid arithmetic expression") from error
    if sum(1 for _ in ast.walk(tree)) > 128:
        raise ToolInputError("arithmetic expression exceeds 128 AST nodes")

    def evaluate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return _number(ast.get_source_segment(expression, node))
        if isinstance(node, ast.Name) and node.id in numbers:
            return numbers[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            result = evaluate(node.operand)
            return result if isinstance(node.op, ast.UAdd) else -result
        if isinstance(node, ast.BinOp):
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Add):
                result = left + right
            elif isinstance(node.op, ast.Sub):
                result = left - right
            elif isinstance(node.op, ast.Mult):
                result = left * right
            elif isinstance(node.op, ast.Div):
                result = left / right
            elif isinstance(node.op, ast.Pow):
                if abs(right) > 16:
                    raise ToolInputError("power exponent magnitude exceeds 16")
                result = left**right
            else:
                raise ToolInputError("only +, -, *, /, ** and unary +/- are allowed")
            return _number(result)
        raise ToolInputError("unsupported arithmetic syntax or unknown variable")

    try:
        with localcontext() as context:
            context.prec = 34
            result = evaluate(tree.body)
    except DecimalException as error:
        raise ToolInputError(f"arithmetic error: {type(error).__name__}") from error
    return {
        "result": str(result),
        "expression": expression,
        "variables": {name: str(value) for name, value in numbers.items()},
        "decimal_precision": 34,
    }


def _final_answer(args: dict[str, Any]) -> dict[str, Any]:
    _fields(args, {"answer"}, {"scale", "program"})
    answer, scale = args["answer"], args.get("scale", "")

    def scalar(value):
        return (isinstance(value, str) and bool(value.strip())) or (
            type(value) in (int, float) and math.isfinite(value)
        )

    if not (scalar(answer) or (isinstance(answer, list) and answer and all(map(scalar, answer)))):
        raise ToolInputError("answer must be a number, nonempty span, or nonempty list of these")
    if not isinstance(scale, str) or len(scale) > 128:
        raise ToolInputError("scale must be a string of at most 128 characters")
    program = args.get("program")
    if program is not None and not isinstance(program, (str, list)):
        raise ToolInputError("optional program must be a string or list")
    # A submitted FinQA DSL program is recorded, never executed by this tool.
    return {"answer": answer, "scale": scale, "program": program}


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_sources",
            "description": "List the task's public source IDs and locations.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_source",
            "description": "Read a complete original public text or table; no truncation.",
            "parameters": {
                "type": "object",
                "properties": {"source_id": {"type": "string"}},
                "required": ["source_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Bounded decimal arithmetic (+ - * / **, parentheses, variables), precision 34. "
                "No code/functions, files or network. Returns result as a decimal string. "
                "Variables may reference successful prior output via prev:<call_id>.<dot.path>, "
                "including list indices. No implicit unit/scale/comma conversion."
            ),
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}, "variables": {"type": "object"}},
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "final_answer",
            "description": (
                "Submit the final answer and terminate. Numeric, span and multi-span/list "
                "answers are allowed; scale is separate. Calculation is optional. Values may "
                "reference successful prior output with prev:<call_id>.<dot.path>. "
                "This tool never returns expected answers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "anyOf": [
                            {"type": "number"},
                            {"type": "string"},
                            {
                                "type": "array",
                                "items": {"anyOf": [{"type": "number"}, {"type": "string"}]},
                            },
                        ]
                    },
                    "scale": {"type": "string"},
                    "program": {"anyOf": [{"type": "string"}, {"type": "array"}]},
                },
                "required": ["answer"],
                "additionalProperties": False,
            },
        },
    },
]


def tool_specs(reference_protocol=LEGACY_REFERENCE_PROTOCOL):
    """New model-facing grammar is versioned; the legacy specifications stay intact."""
    if reference_protocol not in {LEGACY_REFERENCE_PROTOCOL, VISIBLE_REFERENCE_PROTOCOL}:
        raise ValueError("unknown tool reference protocol")
    specs = copy.deepcopy(TOOL_SPECS)
    if reference_protocol == VISIBLE_REFERENCE_PROTOCOL:
        for tool in specs:
            name = tool["function"]["name"]
            if name == "calculate":
                tool["function"]["description"] = (
                    "Bounded decimal scalar arithmetic: +, -, *, /, **, parentheses and variables. "
                    "Place a complete prev:rN.output.<path> reference only in variables values, "
                    "never inside expression. rN must name a previous successful tool result "
                    "visible in this session. No functions, table operators, unit/comma repair "
                    "or FinQA #k notation are accepted here."
                )
            elif name == "final_answer":
                tool["function"]["description"] = (
                    "Submit answer and predicted FinQA program and terminate. Answer may be a "
                    "complete prev:rN.output.<path> reference to a successful result in this "
                    "session. FinQA program is a separate linear DSL: never use tool handles "
                    "inside program. Scale is separate. No expected answer is returned."
                )
    return specs


class PublicToolSession:
    """Per-episode state containing ONLY public sources and real successful outputs."""

    def __init__(
        self,
        task: PublicTask,
        *,
        reference_protocol=LEGACY_REFERENCE_PROTOCOL,
        invocation_context=None,
    ):
        if not isinstance(task, PublicTask):
            raise TypeError("PublicToolSession requires a PublicTask, not a bundle/reference")
        self.sources = {source.source_id: source for source in task.sources}
        if len(self.sources) != len(task.sources):
            raise ValueError("public source IDs must be unique")
        self.outputs: dict[str, Any] = {}
        self.seen_call_ids: set[str] = set()
        if reference_protocol not in {LEGACY_REFERENCE_PROTOCOL, VISIBLE_REFERENCE_PROTOCOL}:
            raise ValueError("unknown tool reference protocol")
        self.reference_protocol = reference_protocol
        self.invocation_scope = invocation_scope(invocation_context)
        self.events_by_handle: dict[str, ToolEvent] = {}
        self._invocation_ids: set[str] = set()
        self._tool_attempts = 0

    def _resolve(self, value: Any, depth: int = 0) -> Any:
        if depth > 32:
            raise ToolInputError("arguments exceed maximum nesting depth")
        if isinstance(value, dict):
            return {key: self._resolve(item, depth + 1) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve(item, depth + 1) for item in value]
        if not isinstance(value, str) or not value.startswith("prev:"):
            return value
        target = value[5:]
        call_id, separator, path = target.partition(".")
        if self.reference_protocol == VISIBLE_REFERENCE_PROTOCOL and (
            re.fullmatch(r"r[1-9][0-9]*", call_id) is None or not path.startswith("output.")
        ):
            raise ToolInputError("reference must use prev:rN.output.<path> in this session")
        if not separator or not path or call_id not in self.outputs:
            raise ToolInputError(
                "reference must identify a previous successful call and output path"
            )
        result = self.outputs[call_id]
        for part in path.split("."):
            if isinstance(result, dict) and part in result:
                result = result[part]
            elif isinstance(result, list) and part.isdecimal() and int(part) < len(result):
                result = result[int(part)]
            else:
                raise ToolInputError("reference path does not exist in the actual previous output")
        return copy.deepcopy(result)

    def execute(self, call: ToolCall, *, invocation_id: str | None = None) -> ToolEvent:
        new_protocol = self.reference_protocol == VISIBLE_REFERENCE_PROTOCOL
        result_handle = f"r{self._tool_attempts + 1}" if new_protocol else None
        actual_invocation = (
            invocation_id
            or invocation_identity(
                self.invocation_scope, turn_index=self._tool_attempts, tool_index=0
            )["invocation_id"]
        )
        if new_protocol and (
            not isinstance(actual_invocation, str)
            or not actual_invocation
            or actual_invocation in self._invocation_ids
        ):
            raise ValueError("one invocation identity cannot execute twice in a tool session")
        self._invocation_ids.add(actual_invocation)
        self._tool_attempts += 1
        normalized: dict[str, Any] = {}
        executed: dict[str, Any] = {}
        try:
            if not call.call_id or (
                not new_protocol and ("." in call.call_id or call.call_id in self.seen_call_ids)
            ):
                raise ToolInputError("tool call ID must be nonempty, dot-free, and unique")
            self.seen_call_ids.add(call.call_id)
            normalized = _strict_object(call.raw_arguments)
            if _json(normalized) != _json(call.arguments):
                raise ToolInputError("raw and provider-parsed arguments disagree")
            if new_protocol:
                # Only the declared argument positions accept tool references.
                # The linear FinQA DSL is recorded literally, never substituted.
                if call.name == "calculate":
                    executed = copy.deepcopy(normalized)
                    if (
                        isinstance(normalized.get("expression"), str)
                        and "prev:" in normalized["expression"]
                    ):
                        raise ToolInputError("put result references in variables, not expression")
                    if "variables" in normalized:
                        executed["variables"] = self._resolve(normalized["variables"])
                elif call.name == "final_answer":
                    executed = copy.deepcopy(normalized)
                    if "answer" in normalized:
                        executed["answer"] = self._resolve(normalized["answer"])
                else:
                    executed = self._resolve(normalized)
            else:
                executed = self._resolve(normalized)
            if call.name == "list_sources":
                _fields(executed, set())
                output = {
                    "sources": [
                        source.model_dump(exclude={"content"}, mode="json")
                        for source in self.sources.values()
                    ]
                }
            elif call.name == "read_source":
                _fields(executed, {"source_id"})
                source_id = executed["source_id"]
                if not isinstance(source_id, str) or source_id not in self.sources:
                    raise ToolInputError("unknown public source_id")
                output = self.sources[source_id].model_dump(mode="json")
            elif call.name == "calculate":
                _fields(executed, {"expression"}, {"variables"})
                output = calculate(**executed)
            elif call.name == "final_answer":
                output = _final_answer(executed)
            else:
                raise ToolInputError(f"unknown tool: {call.name}")
            if new_protocol:
                self.outputs[result_handle] = {
                    "result_handle": result_handle,
                    "status": "ok",
                    "output": copy.deepcopy(output),
                }
            else:
                self.outputs[call.call_id] = copy.deepcopy(output)
            is_error = False
        except (ToolInputError, ValueError, TypeError, OverflowError, RecursionError) as error:
            output = {"error": type(error).__name__, "message": str(error)}
            is_error = True
        envelope = (
            {
                "result_handle": result_handle,
                "status": "error" if is_error else "ok",
                "output": output,
            }
            if new_protocol
            else output
        )
        event = ToolEvent(
            call_id=call.call_id,
            name=call.name,
            raw_arguments=call.raw_arguments,
            normalized_arguments=normalized,
            executed_arguments=executed,
            raw_output=output,
            visible_output=_json(envelope),
            is_error=is_error,
            result_handle=result_handle,
            invocation_id=actual_invocation if new_protocol else None,
            reference_protocol=self.reference_protocol,
        )
        if new_protocol:
            self.events_by_handle[result_handle] = event
        return event
