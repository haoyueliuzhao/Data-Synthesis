"""Public-only, bounded catalog conversation and real deterministic tools.

No TaskBundle reader, oracle import, filesystem access or provider transport lives
here. This stage enables scripted interface controls only. Frozen public messages
remain byte-for-byte intact as a suffix of the separately frozen guidance prefix.
"""

import ast
import copy
import hashlib
import json
import re
from fractions import Fraction

from ..finance_qa_vnext_autonomous_formula.online.calculator import calculate, number

IDENTITY_FIELDS = {
    "task_id",
    "family",
    "surface_version_id",
    "public_messages_sha256",
    "parent_manifest_id",
}
FAMILY_TO_SCALE_GROUP = {
    "annual_flow": "annual_flow_components",
    "stock_rollforward": "stock_rollforward",
    "company_defined_metric": "defined_metric_reconstruction",
    "control": "control",
}
UNITS = {
    "USD": ("currency:USD", Fraction(1)),
    "million USD": ("currency:USD", Fraction(1000000)),
    "percent": ("dimensionless", Fraction(1, 100)),
    "ratio": ("dimensionless", Fraction(1)),
}
SYSTEM = """Execute only against the supplied frozen public sources.
Return one JSON object per response. calculate may include "revises_result_id":"tool:3"
to explicitly replace a prior calculation. This checks reference existence only,
not financial correctness.
Tools: {"tool":"read_source","arguments":{"source_id":"...","unit":"million USD"}}
reads a JSON numeric record; for a table also provide "cells":[[row_index,cell_index],...]
using zero-based original_rows coordinates. A table amount may occupy adjacent
currency/sign/number cells; cite the complete amount and never another year's number.
Tool output states the actual source and conversion.
{"tool":"calculate","arguments":{"expression":"current-previous","variables":{
"current":{"result_id":"tool:2"},"previous":{"result_id":"tool:1"}},"unit":"million USD"}}
evaluates explicit arithmetic. Reference actual numeric tool outputs, not undocumented
values. Scalar constants are dimensionless. Compatible currency units convert explicitly;
percent is 100 times a ratio. No year is a source amount.
{"final":{"value":"...","unit":"million USD","result_id":"tool:3"}} publishes the answer
supported by the named executed result. The first object containing final ends the session,
including malformed or incorrect Finals. Formatting errors before Final may be corrected
without financial feedback. Follow the quantity requested in the question: a signed difference
is later minus earlier; a relative change uses the specified earlier base and percent.
Do not substitute net-change guidance for a rate task."""
GUIDANCE = {
    "neutral": "Choose any financially sufficient support from the supplied original records.",
    "endpoint": (
        "When sufficient, use reported endpoint values for the requested quantity and base."
    ),
    "movement": (
        "When sufficient, integrate disclosed components or movements for the requested quantity; "
        "retain the requested earlier base for a rate."
    ),
}


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def record(kind, **fields):
    row = {"schema_version": "catalog_bridge.v1." + kind, **fields}
    return {**row, "id": kind + ":" + sha(encode(row))}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    return json.loads(
        raw,
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")),
    )


def public_document(messages, identity):
    require(set(identity) == IDENTITY_FIELDS, "worker.identity_is_public_only")
    require(identity["family"] in FAMILY_TO_SCALE_GROUP, "worker.explicit_family_map")
    require(
        sha(encode(messages)) == identity["public_messages_sha256"], "worker.frozen_messages_hash"
    )
    require(
        isinstance(messages, list)
        and len(messages) == 1
        and set(messages[0]) == {"role", "content"}
        and messages[0]["role"] == "user"
        and isinstance(messages[0]["content"], str),
        "worker.public_message_shape",
    )
    public = strict_json(messages[0]["content"])
    require(
        set(public)
        == {"question", "sources", "quantity_contract", "source_policy", "tool_contract"},
        "worker.public_field_allowlist",
    )
    require(isinstance(public["sources"], list), "worker.public_sources")
    require(
        len({source["source_id"] for source in public["sources"]}) == len(public["sources"]),
        "worker.unique_source_ids",
    )
    return public


def convert(value, source_unit, target_unit):
    require(source_unit in UNITS and target_unit in UNITS, "tool.unknown_unit")
    left, right = UNITS[source_unit], UNITS[target_unit]
    require(left[0] == right[0], "tool.unit_dimension_conflict")
    factor = left[1] / right[1]
    return value * factor, {
        "from_unit": source_unit,
        "to_unit": target_unit,
        "factor": str(factor),
        "input_exact_value": str(value),
        "output_exact_value": str(value * factor),
    }


def read_source(arguments, public):
    require(
        isinstance(arguments, dict) and set(arguments) <= {"source_id", "cells", "unit"},
        "tool.read_arguments",
    )
    source = next(
        (row for row in public["sources"] if row["source_id"] == arguments.get("source_id")), None
    )
    require(source is not None, "tool.unknown_public_source")
    cells = arguments.get("cells")
    if "record" in source:
        require(cells is None, "tool.json_record_has_no_cells")
        value, raw = number(source["record"]["val"]), copy.deepcopy(source["record"])
        locator = {"source_id": source["source_id"], "native_pointer": source["native_pointer"]}
    else:
        require(
            isinstance(cells, list)
            and 1 <= len(cells) <= 12
            and all(
                isinstance(cell, list)
                and len(cell) == 2
                and all(type(i) is int and i >= 0 for i in cell)
                for cell in cells
            ),
            "tool.table_cell_coordinates",
        )
        require(
            cells == sorted(cells)
            and len({tuple(c) for c in cells}) == len(cells)
            and len({c[0] for c in cells}) == 1
            and [c[1] for c in cells] == list(range(cells[0][1], cells[-1][1] + 1)),
            "tool.adjacent_single_row_amount",
        )
        try:
            raw = [{"row": r, "cell": c, "text": source["original_rows"][r][c]} for r, c in cells]
        except IndexError:
            raise ValueError("tool.table_cell_out_of_range") from None
        require(
            sum(bool(re.search(r"\d", cell["text"])) for cell in raw) == 1,
            "tool.multiple_or_missing_numeric_bodies",
        )
        printed = " ".join(cell["text"] for cell in raw if cell["text"])
        clean = printed.replace("$", "").replace(",", "").replace(" ", "").replace("\u2212", "-")
        require(
            bool(re.fullmatch(r"(?:-?\d+(?:\.\d+)?|\(\d+(?:\.\d+)?\))", clean)),
            "tool.incomplete_or_nonnumeric_amount",
        )
        value = number("-" + clean[1:-1] if clean.startswith("(") else clean)
        locator = {"source_id": source["source_id"], "cells": copy.deepcopy(cells)}
    target = arguments.get("unit", source["unit"])
    normalized, conversion = convert(value, source["unit"], target)
    return {
        "exact_value": str(normalized),
        "unit": target,
        "source_locator": locator,
        "source_raw_sha256": source["raw_sha256"],
        "source_url": source["original_url"],
        "original_source_fragment": raw,
        "source_unit": source["unit"],
        "conversion": conversion,
        "used_result_ids": [],
        "financial_meaning_certified": False,
    }


def calculate_with_units(arguments, previous):
    require(isinstance(arguments, dict), "tool.calculate_arguments")
    revision = arguments.get("revises_result_id")
    require(
        revision is None
        or (
            isinstance(revision, str)
            and revision in previous
            and previous[revision]["tool"] == "calculate"
        ),
        "tool.revision_requires_prior_calculation",
    )
    computed = calculate(arguments, previous)
    normalized = {}
    conversions = []
    dimensions = {}
    for name, resolved in computed["resolved_variables"].items():
        ref = resolved["result_id"]
        if ref is None:
            normalized[name] = resolved["exact_value"]
            dimensions[name] = 0
        else:
            result = previous[ref]["result"]
            require(result.get("unit") in UNITS, "tool.prior_result_unit")
            unit = result["unit"]
            canonical = "USD" if UNITS[unit][0] == "currency:USD" else "ratio"
            value, conversion = convert(number(result["exact_value"]), unit, canonical)
            normalized[name] = str(value)
            dimensions[name] = int(canonical == "USD")
            conversions.append({"variable": name, "result_id": ref, **conversion})
    tree = ast.parse(arguments["expression"], mode="eval")

    def dimension(node):
        if isinstance(node, ast.Constant):
            return 0
        if isinstance(node, ast.Name):
            return dimensions[node.id]
        if isinstance(node, ast.UnaryOp):
            return dimension(node.operand)
        if isinstance(node, ast.BinOp):
            a, b = dimension(node.left), dimension(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                require(a == b, "tool.unit_addition_conflict")
                return a
            if isinstance(node.op, ast.Mult):
                return a + b
            if isinstance(node.op, ast.Div):
                return a - b
            require(
                b == 0 and isinstance(node.right, ast.Constant) and type(node.right.value) is int,
                "tool.unit_power_exponent",
            )
            return a * node.right.value
        if isinstance(node, ast.Call):
            children = (
                node.args[0].elts
                if len(node.args) == 1 and isinstance(node.args[0], (ast.List, ast.Tuple))
                else node.args
            )
            dims = [dimension(child) for child in children]
            require(len(set(dims)) == 1, "tool.unit_function_conflict")
            return dims[0]
        raise ValueError("tool.unsupported_unit_expression")

    dim = dimension(tree.body)
    require(dim in {0, 1}, "tool.unsupported_result_dimension")
    canonical = "USD" if dim else "ratio"
    # Re-execute actual normalized arithmetic: do not merely relabel old values.
    normalized_result = calculate(
        {"expression": arguments["expression"], "variables": normalized}, {}
    )
    target = arguments.get("unit", canonical)
    value, final_conversion = convert(number(normalized_result["exact_value"]), canonical, target)
    return {
        **computed,
        "exact_value": str(value),
        "value": str(value),
        "unit": target,
        "canonical_expression_value": normalized_result["exact_value"],
        "operand_conversions": conversions,
        "conversion": final_conversion,
        "source_declarations_validated": False,
        "revises_result_id": revision,
    }


def generate(
    public_messages,
    identity,
    *,
    scripted,
    requested_basis="neutral",
    max_responses=32,
    max_tools=24,
):
    """No live transport exists in this preparation stage; all returns are controls."""
    public = public_document(public_messages, identity)
    require(requested_basis in GUIDANCE, "worker.guidance")
    require(
        type(max_responses) is int
        and 1 <= max_responses <= 32
        and type(max_tools) is int
        and 0 <= max_tools <= 24,
        "worker.session_limits",
    )
    require(isinstance(scripted, (list, tuple)), "worker.scripted_only_no_live_provider")
    initial = [
        {"role": "system", "content": SYSTEM + "\n" + GUIDANCE[requested_basis]},
        *copy.deepcopy(public_messages),
    ]
    messages, events, turns, outputs = copy.deepcopy(initial), [], [], {}
    terminal, first_final, final = "script_exhausted_without_final", None, None
    for index, supplied in enumerate(scripted[:max_responses]):
        raw = supplied if isinstance(supplied, str) else encode(supplied).decode()
        require(len(raw.encode()) <= 65536, "worker.response_byte_limit")
        turns.append(
            {
                "response_index": index,
                "input_messages": copy.deepcopy(messages),
                "raw_response": raw,
                "raw_response_sha256": sha(raw.encode()),
                "origin": "scripted_interface_control",
            }
        )
        messages.append({"role": "assistant", "content": raw})
        event = {
            "response_index": index,
            "tool_call": None,
            "final": False,
            "protocol_error": None,
            "oracle_feedback": False,
        }
        feedback = None
        try:
            choice = strict_json(raw)
            require(isinstance(choice, dict), "response_must_be_object")
            if "final" in choice:
                terminal, first_final, final = "first_final", index, choice["final"]
                event["final"] = True
                events.append(event)
                break
            require(set(choice) == {"tool", "arguments"}, "expected_tool_or_final")
            if len(outputs) >= max_tools:
                terminal = "tool_budget_exhausted"
                events.append(event)
                break
            call_id = "tool:" + str(len(outputs) + 1)
            tool = {
                "call_id": call_id,
                "tool": choice["tool"],
                "arguments": choice["arguments"],
                "status": "ok",
                "result": None,
            }
            try:
                if tool["tool"] == "read_source":
                    tool["result"] = read_source(tool["arguments"], public)
                elif tool["tool"] == "calculate":
                    tool["result"] = calculate_with_units(tool["arguments"], outputs)
                else:
                    raise ValueError("tool.unknown_tool")
            except (
                ValueError,
                TypeError,
                KeyError,
                ZeroDivisionError,
                SyntaxError,
                RecursionError,
            ) as error:
                tool.update(status="error", error=str(error))
            outputs[call_id], event["tool_call"] = tool, copy.deepcopy(tool)
            feedback = {"tool_observation": tool}
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            event["protocol_error"] = str(error)
            feedback = {
                "protocol_error": (
                    "Return one JSON tool or final object. No financial assessment was performed."
                )
            }
        events.append(event)
        messages.append({"role": "user", "content": encode(feedback).decode()})
    else:
        if len(scripted) >= max_responses:
            terminal = "response_budget_exhausted"
    return record(
        "session",
        identity=copy.deepcopy(identity),
        initial_messages=initial,
        public_messages=copy.deepcopy(public_messages),
        requested_basis=requested_basis,
        turns=turns,
        events=events,
        terminal=terminal,
        first_final_index=first_final,
        raw_final=final,
        max_responses=max_responses,
        max_tools=max_tools,
        origin="scripted_interface_control",
        provider_calls=0,
        teacher_sessions=0,
        training_samples=0,
        model_weight_loads=0,
        gpu_calls=0,
        private_oracle_access=False,
    )
