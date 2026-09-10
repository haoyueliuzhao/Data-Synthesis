"""Public-only standalone configuration and durable original-byte records (stdlib only)."""

import hashlib
import json
import os
from pathlib import Path

VERSION = "autonomous_formula_thinking.v1"
LIMITS = {
    "model_responses": 32,
    "tool_calls": 32,
    "request_bytes": 98304,
    "response_bytes": 2097152,
    "public_content_bytes": 1048576,
    "output_tokens": 16384,
    "connect_seconds": 30,
    "total_seconds": 180,
    "expression_characters": 4096,
    "ast_nodes": 256,
    "ast_depth": 32,
    "integer_bits": 16384,
    "power_exponent": 12,
}
SYSTEM = """Solve the user's question from the supplied complete source document. You decide your
plan, which evidence and quantities to use, the calculation relationship, units, order of work,
checks, revisions, and when to finish. No task-specific formula, selected evidence, next-step menu,
or answer-correctness feedback is supplied.
Return one JSON object per response. You may include a concise public explanation in "message".
To request a tool, include "tool" and "arguments". To finish, include "final" (free text or an
object); this ends the session immediately even if the answer is wrong. A useful final object may
contain answer, value, unit, sources, and result_id, but none is required for termination. A message
without a tool or final is allowed. There is no mandatory planning or Formula stage, and no
accept/Update stage.
Tools:
1. calculate: arguments.expression is an explicit arithmetic expression. Optional
arguments.variables maps names to decimal/fraction numbers (JSON numbers or strings), or
{"value":number,"source":optional_source_id,"unit":optional_text}, or {"result_id":"tool:N"}
for an earlier successful scalar numeric tool result. Decimal numeric text is preserved exactly.
Operators: +, -, *, /, ** (bounded integer power); functions: sum, avg, min, max, abs. Lists are
allowed as aggregate arguments. Optional arguments.sources maps variable names to source IDs from
the complete numeric catalog; this is your provenance declaration, not a requirement for executing
arithmetic. Arithmetic may be a complete formula or a partial calculation. Identify the relationship
and chosen quantities in your public message or calculation request when possible. Values and
source/result associations are your choices: the host will not infer them from matching numbers or
repair signs, years, or units. Literal arithmetic and missing source declarations are executable.
2. read_source: arguments.locators is a list of exact numeric catalog IDs or segment IDs. It returns
the corresponding original records/text, without relevance selection. The entire source is already
visible; reading again is optional.
3. notebook: arguments.operation is "write" or "read", arguments.key is a short name, and
arguments.text is your own text for write. The host never writes or summarizes a plan for you.
Every tool output is accessible immediately. You can use, ignore, question or recalculate it;
numeric execution does not certify financial meaning or source correctness. Tool errors describe
only actual execution or interface problems. There is no online grading of the final answer. Model
responses and tool calls each have a maximum of 32. Input history has a fixed byte limit and is
never silently truncated. Do not emit native tool calls or Markdown outside the JSON object."""


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(kind, **fields):
    body = {"schema_version": VERSION + "." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


def write(directory, name, data):
    path = Path(directory) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(descriptor)
    os.close(descriptor)


def save(directory, name, value):
    write(directory, name, encode(value))


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("non_finite_json_number")

    # Keep decimal numeric lexemes exact, including trailing digits, in derived
    # parsed records. The original assistant bytes/messages remain untouched.
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid, parse_float=str)


def request_body(messages, model="deepseek-v4-flash"):
    return {
        "model": model,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        "max_tokens": LIMITS["output_tokens"],
        "stream": False,
        "messages": messages,
    }


SYSTEM = SYSTEM + '\n\nYour deliverable includes both the answer and an auditable public calculation.\nBefore a relevant calculation, or in the same calculation request, state the relationship you\nchose, the meaning and source of its inputs, and any necessary unit handling. Use the calculate\ntool to produce the result on which your final answer is based. You still choose the plan,\nformula, evidence, calculation granularity, checks, and when to finish. No fixed sequence,\nextra planning turn, lengthy explanation, or repeated calculation is required.'


SYSTEM = SYSTEM + '\n\nShared public quantity and delivery contract for this study:\nThe monetary targets in these tasks are U.S. dollar (USD) amounts; no currency conversion is\nrequested. Dollar-denominated source amounts are interpreted in that same currency unless the\nsource explicitly states otherwise; an explicit conflicting currency must never be silently\nreplaced. Source scales remain as stated, and all source material stays visible.\nFor clear delivery, prefer a final object containing a finite numeric value, a textual unit, an\nanswer, and the actual supporting result_id. The preferred unit spelling for a result expressed\nin millions of U.S. dollars is USD_million. This spelling is a formatting preference, not a\nfinancial-validity requirement. Quantity interpretation and formatting are evaluated separately.\nThe separate canonical-format flag checks only that final.value is a supported scalar and\nfinal.unit is exactly USD_million; it does not certify correctness or source linkage.\nOrdinary compositions of currency and scale words, such as "$ in millions", are interpretable.\n"million" or "millions" alone states scale only: currency can be completed solely when the public\ntarget and relevant source uniquely agree and no contrary currency is stated. Never infer a\nmissing scale from the question or use a correct-looking number to override a unit conflict.\nThe finite numeric interpretation accepts decimal or fractional text up to 256 characters,\nincluding scientific notation with an exponent between -18 and 18.\nUnsupported values stay unresolved.\nAn explicit amount and unit in the actual Final text can also deliver a quantity, even if the\npreferred object fields are absent. No value or unit will be copied from a preceding message,\ntool result, or private reference to complete an uninterpretable Final. Conflicting Final fields\nor unresolved currency/scale keep their own failure or uncertainty status.\nThe first Final still terminates immediately; these evaluation rules do not introduce online\ncorrectness feedback, retries, or a required extra calculation.\n\nFor this solution, give priority to examining sufficient evidence based on period\ncomponents or movements. Determine the items, signs, sources, and expression yourself from the\ncomplete document. If you adopt such evidence, actually execute the calculation supporting your\nfinal answer. If sufficient evidence cannot be established, say so honestly and do not invent it.'
