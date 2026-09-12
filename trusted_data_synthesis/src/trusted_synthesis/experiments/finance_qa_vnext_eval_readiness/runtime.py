"""Public-only evaluation conversations, complete snapshots, and exact tools.

The callback boundary deliberately owns no model transport or budget credentials.
Only public source descriptors enter ``SnapshotSources``. Neither the worker nor
its tools receive a TaskBundle, native fact roles, expected answer, or leaf list.
"""

import copy
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.worker import (
    calculate_with_units,
    convert,
    encode,
    number,
    require,
    sha,
    strict_json,
)
from .periods import period_identity

IDENTITY_FIELDS = {
    "task_id",
    "family",
    "surface_version_id",
    "public_messages_sha256",
    "parent_manifest_id",
}
FAMILIES = {"dual_sufficient", "composition_required", "other_financial"}
MAX_RESPONSES = 32
MAX_TOOLS = 32
MAX_PAGE_SIZE = 20
MAX_RESPONSE_BYTES = 65536
SYSTEM = """Use only original public records from the supplied complete source snapshots.
Return exactly one JSON object per response. Tool requests have keys tool and arguments.
query_source arguments: source_id, optional concept (namespace:tag), label_contains,
unit, start, end, offset (default 0), limit (1..20). It returns real original records
with native pointers and actual interval identities; pagination retains full source access.
list_concepts arguments: source_id, offset, limit. read_json arguments: source_id,
pointer, offset, limit; it retrieves any original JSON subtree, with bounded pagination.
read_source arguments: source_id, native_pointer, optional unit. Read a numeric record
at its original pointer; the actual source interval is returned, never invented from fy.
calculate arguments: expression, variables={name:{result_id:'tool:1'}}, unit. Supports
exact +,-,*,/,bounded powers,sum,avg; actual compatible unit conversions are recorded.
Use actual result references, not pasted unsupported financial constants or year numbers.
select_max arguments: result_ids=[...], optionally unit. It compares all referenced
source-supported candidate amounts; equal maxima are rejected. compare arguments:
left_result_id,right_result_id, optionally unit. It compares two candidates, or prior
selection winners, retaining every original compared candidate and its actual interval.
lookup_selected arguments: selection_result_id, source_result_id. It requires the read
secondary source to be in the exact selected interval and records both dependencies.
Final: {'final':{'value':'...', 'unit':'million USD', 'result_id':'tool:N'}}.
For a peak-then-lookup task also supply period_id (the exact period:duration:start:end
identity) or period={start,end,period_type}; include selection_result_id unless the
named result already depends on lookup_selected. A four-digit year alone is insufficient.
The first object containing final stops immediately even when malformed or incorrect.
No financial assessment is returned during the conversation. Failed tools and formatting
errors remain in every later history. Answer any public sufficient relation; no requested
guidance or canonical plan is the actual-method authority."""


def record(kind, **fields):
    body = {"schema_version": "eval_readiness.v1." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


def actual_period(raw):
    """Native interval identity; fiscal filing labels are deliberately not used."""
    from datetime import date

    end = raw.get("end")
    start = raw.get("start")
    require(isinstance(end, str), "source.actual_end_required")
    date.fromisoformat(end)
    if start is None:
        return {
            "period_id": period_identity(None, end, "instant"),
            "start": None,
            "end": end,
            "period_type": "instant",
        }
    require(isinstance(start, str), "source.actual_start_required")
    require(date.fromisoformat(start) <= date.fromisoformat(end), "source.invalid_interval")
    return {
        "period_id": period_identity(start, end),
        "start": start,
        "end": end,
        "period_type": "duration",
    }


def _escape(value):
    return value.replace("~", "~0").replace("/", "~1")


def _pointer(payload, pointer):
    require(
        isinstance(pointer, str) and (pointer == "" or pointer.startswith("/")),
        "source.exact_json_pointer",
    )
    value = payload
    for token in pointer[1:].split("/") if pointer else []:
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            require(token.isdigit() and str(int(token)) == token, "source.array_index")
            value = value[int(token)]
        else:
            value = value[token]
    return value


def _page(arguments):
    offset, limit = arguments.get("offset", 0), arguments.get("limit", MAX_PAGE_SIZE)
    require(
        type(offset) is int and offset >= 0 and type(limit) is int and 1 <= limit <= MAX_PAGE_SIZE,
        "source.page_limits",
    )
    return offset, limit


class SnapshotSources:
    """Full public snapshots with source-driven filtering, never answer projection.

    ``references`` is a list of public descriptors containing source_id and
    complete_original_snapshot={path,sha256,bytes,...}. The optional in-memory
    constructor is for synthetic controls; both use identical query/read tools.
    """

    def __init__(self, root, references, *, payloads=None):
        self.root = Path(root).resolve() if root is not None else None
        require(isinstance(references, (list, tuple)), "source.reference_list")
        self.references = {}
        self.payloads = {}
        for reference in references:
            identifier = reference["source_id"]
            require(identifier not in self.references, "source.duplicate_snapshot")
            require("complete_original_snapshot" in reference, "source.full_snapshot_required")
            self.references[identifier] = copy.deepcopy(reference)
        if payloads is not None:
            require(set(payloads) == set(self.references), "source.synthetic_snapshot_join")
            for identifier, payload in payloads.items():
                raw = encode(payload)
                metadata = self.references[identifier]["complete_original_snapshot"]
                require(
                    sha(raw) == metadata["sha256"] and len(raw) == metadata["bytes"],
                    "source.synthetic_snapshot_identity",
                )
                self.payloads[identifier] = copy.deepcopy(payload)

    @classmethod
    def synthetic(cls, payloads):
        references = [
            {
                "source_id": identifier,
                "complete_original_snapshot": {
                    "path": f"synthetic/{identifier}.json",
                    "sha256": sha(encode(payload)),
                    "bytes": len(encode(payload)),
                    "original_url": f"https://example.invalid/{identifier}",
                    "all_concepts_units_years_and_occurrences_available": True,
                },
            }
            for identifier, payload in sorted(payloads.items())
        ]
        return cls(None, references, payloads=payloads)

    def descriptors(self):
        return copy.deepcopy(list(self.references.values()))

    def _payload(self, source_id):
        require(source_id in self.references, "source.unknown_public_snapshot")
        if source_id not in self.payloads:
            require(self.root is not None, "source.root_required")
            metadata = self.references[source_id]["complete_original_snapshot"]
            relative = Path(metadata["path"])
            require(
                not relative.is_absolute() and ".." not in relative.parts,
                "source.relative_snapshot_path",
            )
            path = self.root
            for part in relative.parts:
                path = path / part
                require(not path.is_symlink(), "source.snapshot_symlink")
            require(path.resolve().is_relative_to(self.root), "source.snapshot_containment")
            raw = path.read_bytes()
            require(
                len(raw) == metadata["bytes"] and sha(raw) == metadata["sha256"],
                "source.original_snapshot_identity",
            )
            self.payloads[source_id] = strict_json(raw.decode())
        return self.payloads[source_id]

    def _row(self, source_id, namespace, tag, unit, index, raw, concept):
        pointer = f"/facts/{_escape(namespace)}/{_escape(tag)}/units/{_escape(unit)}/{index}"
        metadata = self.references[source_id]["complete_original_snapshot"]
        return {
            "source_id": source_id,
            "native_pointer": pointer,
            "record_id": "native_record:" + sha(encode([source_id, pointer])),
            "source_raw_sha256": metadata["sha256"],
            "concept": namespace + ":" + tag,
            "label": concept.get("label", tag),
            "definition": concept.get("description", ""),
            "source_unit": unit,
            "record": copy.deepcopy(raw),
            "actual_period": actual_period(raw),
        }

    def query(self, arguments):
        require(
            isinstance(arguments, dict)
            and set(arguments)
            <= {
                "source_id",
                "concept",
                "label_contains",
                "unit",
                "start",
                "end",
                "offset",
                "limit",
            },
            "source.query_arguments",
        )
        source_id = arguments["source_id"]
        payload = self._payload(source_id)
        offset, limit = _page(arguments)
        selected, total = [], 0
        for namespace, concepts in sorted(payload.get("facts", {}).items()):
            for tag, concept in sorted(concepts.items()):
                if "concept" in arguments and arguments["concept"] != namespace + ":" + tag:
                    continue
                if (
                    "label_contains" in arguments
                    and str(arguments["label_contains"]).casefold()
                    not in (
                        tag + " " + concept.get("label", "") + " " + concept.get("description", "")
                    ).casefold()
                ):
                    continue
                for unit, rows in sorted(concept.get("units", {}).items()):
                    if "unit" in arguments and unit != arguments["unit"]:
                        continue
                    for index, raw in enumerate(rows):
                        if any(
                            key in arguments and raw.get(key) != arguments[key]
                            for key in ("start", "end")
                        ):
                            continue
                        if offset <= total < offset + limit:
                            selected.append(
                                self._row(source_id, namespace, tag, unit, index, raw, concept)
                            )
                        total += 1
        return {
            "source_id": source_id,
            "records": selected,
            "offset": offset,
            "total": total,
            "next_offset": offset + len(selected) if offset + len(selected) < total else None,
            "selection_basis": "only_public_source_and_explicit_query_arguments",
            "full_original_snapshot_accessible": True,
        }

    def list_concepts(self, arguments):
        require(
            isinstance(arguments, dict) and set(arguments) <= {"source_id", "offset", "limit"},
            "source.list_concepts_arguments",
        )
        payload = self._payload(arguments["source_id"])
        offset, limit = _page(arguments)
        rows = [
            {
                "concept": namespace + ":" + tag,
                "label": concept.get("label", tag),
                "definition": concept.get("description", ""),
                "units": {
                    unit: len(values) for unit, values in sorted(concept.get("units", {}).items())
                },
            }
            for namespace, concepts in sorted(payload.get("facts", {}).items())
            for tag, concept in sorted(concepts.items())
        ]
        return {
            "concepts": rows[offset : offset + limit],
            "offset": offset,
            "total": len(rows),
            "next_offset": offset + limit if offset + limit < len(rows) else None,
        }

    def read_json(self, arguments):
        require(
            isinstance(arguments, dict)
            and set(arguments) <= {"source_id", "pointer", "offset", "limit"},
            "source.read_json_arguments",
        )
        pointer = arguments.get("pointer", "")
        value = _pointer(self._payload(arguments["source_id"]), pointer)
        offset, limit = _page(arguments)
        if isinstance(value, dict):
            keys = sorted(value)
            items = [
                {
                    "key": key,
                    "pointer": pointer + "/" + _escape(key),
                    "value": value[key] if not isinstance(value[key], (dict, list)) else None,
                    "kind": type(value[key]).__name__,
                }
                for key in keys[offset : offset + limit]
            ]
            total = len(keys)
        elif isinstance(value, list):
            items = [
                {
                    "index": index,
                    "pointer": pointer + "/" + str(index),
                    "value": item if not isinstance(item, (dict, list)) else None,
                    "kind": type(item).__name__,
                }
                for index, item in enumerate(value[offset : offset + limit], start=offset)
            ]
            total = len(value)
        else:
            require(offset == 0, "source.scalar_offset")
            items, total = [{"pointer": pointer, "value": value}], 1
        return {
            "pointer": pointer,
            "items": copy.deepcopy(items),
            "offset": offset,
            "total": total,
            "next_offset": offset + len(items) if offset + len(items) < total else None,
            "full_original_snapshot_accessible": True,
        }

    def read_source(self, arguments):
        require(
            isinstance(arguments, dict)
            and set(arguments) <= {"source_id", "native_pointer", "unit"},
            "source.read_arguments",
        )
        source_id, pointer = arguments["source_id"], arguments["native_pointer"]
        parts = pointer.split("/")
        require(
            len(parts) == 7 and parts[1] == "facts" and parts[4] == "units",
            "source.numeric_observation_pointer",
        )
        namespace, tag, unit = [
            value.replace("~1", "/").replace("~0", "~") for value in (parts[2], parts[3], parts[5])
        ]
        require(parts[6].isdigit() and str(int(parts[6])) == parts[6], "source.record_index")
        payload = self._payload(source_id)
        raw = _pointer(payload, pointer)
        require(isinstance(raw, dict) and "val" in raw, "source.original_numeric_record")
        row = self._row(
            source_id, namespace, tag, unit, int(parts[6]), raw, payload["facts"][namespace][tag]
        )
        target_unit = arguments.get("unit", unit)
        value, conversion = convert(number(raw["val"]), unit, target_unit)
        return {
            **row,
            "unit": target_unit,
            "exact_value": str(value),
            "conversion": conversion,
            "used_result_ids": [],
            "source_locator": {"source_id": source_id, "native_pointer": pointer},
            "financial_meaning_certified": False,
        }


def _numeric(identifier, outputs):
    require(
        identifier in outputs and outputs[identifier]["status"] == "ok",
        "tool.successful_prior_result_required",
    )
    result = outputs[identifier]["result"]
    require("exact_value" in result and "unit" in result, "tool.numeric_result_required")
    return result


def _selected(arguments, outputs, *, pairwise=False):
    allowed = {"left_result_id", "right_result_id", "unit"} if pairwise else {"result_ids", "unit"}
    require(isinstance(arguments, dict) and set(arguments) <= allowed, "tool.selection_arguments")
    references = (
        [arguments["left_result_id"], arguments["right_result_id"]]
        if pairwise
        else arguments["result_ids"]
    )
    require(
        isinstance(references, list)
        and 2 <= len(references) <= 20
        and len(set(references)) == len(references),
        "tool.selection_candidates",
    )
    candidates, target_unit = [], arguments.get("unit", "million USD")
    for reference in references:
        result = _numeric(reference, outputs)
        if outputs[reference]["tool"] in {"select_max", "compare"}:
            candidates.extend(copy.deepcopy(result["selection_candidates"]))
        else:
            require(
                result.get("actual_period") is not None, "tool.candidate_actual_period_required"
            )
            value, conversion = convert(number(result["exact_value"]), result["unit"], target_unit)
            candidates.append(
                {
                    "result_id": reference,
                    "exact_value": str(value),
                    "unit": target_unit,
                    "actual_period": result["actual_period"],
                    "conversion": conversion,
                }
            )
    require(
        len({row["result_id"] for row in candidates}) == len(candidates),
        "tool.duplicate_selection_candidate",
    )
    for row in candidates:
        value, conversion = convert(number(row["exact_value"]), row["unit"], target_unit)
        row.update(exact_value=str(value), unit=target_unit, conversion=conversion)
    maximum = max(number(row["exact_value"]) for row in candidates)
    winners = [row for row in candidates if number(row["exact_value"]) == maximum]
    require(len(winners) == 1, "tool.non_unique_peak")
    winner = winners[0]
    return {
        "exact_value": str(maximum),
        "unit": target_unit,
        "actual_period": copy.deepcopy(winner["actual_period"]),
        "selected_result_id": winner["result_id"],
        "selection_candidates": candidates,
        "used_result_ids": references,
        "comparison": "strict_unique_maximum",
        "comparison_evidence": [
            {
                "winner_result_id": winner["result_id"],
                "candidate_result_id": row["result_id"],
                "winner_greater": maximum > number(row["exact_value"]),
            }
            for row in candidates
            if row is not winner
        ],
    }


def execute(tool, arguments, sources, outputs):
    if tool == "query_source":
        return sources.query(arguments)
    if tool == "list_concepts":
        return sources.list_concepts(arguments)
    if tool == "read_json":
        return sources.read_json(arguments)
    if tool == "read_source":
        return sources.read_source(arguments)
    if tool == "calculate":
        result = calculate_with_units(arguments, outputs)
        periods = [
            outputs[reference]["result"].get("actual_period")
            for reference in result["used_result_ids"]
        ]
        if periods and all(period is not None and period == periods[0] for period in periods):
            result["actual_period"] = copy.deepcopy(periods[0])
        return result
    if tool in {"select_max", "compare"}:
        return _selected(arguments, outputs, pairwise=tool == "compare")
    if tool == "lookup_selected":
        require(
            isinstance(arguments, dict)
            and set(arguments) == {"selection_result_id", "source_result_id"},
            "tool.lookup_arguments",
        )
        selection_id, source_id = arguments["selection_result_id"], arguments["source_result_id"]
        selection, source = _numeric(selection_id, outputs), _numeric(source_id, outputs)
        require(
            outputs[selection_id]["tool"] in {"select_max", "compare"},
            "tool.actual_selection_result_required",
        )
        require(
            selection["actual_period"] == source.get("actual_period"),
            "tool.lookup_actual_period_mismatch",
        )
        return {
            "exact_value": source["exact_value"],
            "unit": source["unit"],
            "actual_period": copy.deepcopy(source["actual_period"]),
            "selection_result_id": selection_id,
            "source_result_id": source_id,
            "used_result_ids": [selection_id, source_id],
        }
    raise ValueError("tool.unknown_tool")


def public_document(messages, identity, sources):
    require(
        set(identity) == IDENTITY_FIELDS and identity["family"] in FAMILIES,
        "runtime.public_identity_allowlist",
    )
    require(
        sha(encode(messages)) == identity["public_messages_sha256"], "runtime.public_messages_sha"
    )
    require(
        isinstance(messages, list)
        and len(messages) == 1
        and set(messages[0]) == {"role", "content"}
        and messages[0]["role"] == "user"
        and isinstance(messages[0]["content"], str),
        "runtime.public_messages_shape",
    )
    public = strict_json(messages[0]["content"])
    require(
        isinstance(public, dict)
        and set(public)
        == {
            "question",
            "source_document",
            "quantity_contract",
            "source_policy",
            "tool_contract",
            "period_contract",
        },
        "runtime.public_fields_allowlist",
    )
    require("period_contract" in public, "runtime.actual_period_contract_required")
    require(
        public["period_contract"]["task_id"] == identity["task_id"], "runtime.public_contract_task"
    )
    descriptor = public.get("source_document", public.get("sources"))
    if isinstance(descriptor, dict):
        descriptor = [descriptor]
    require(isinstance(descriptor, list) and descriptor, "runtime.public_source_descriptors")
    visible = {row["source_id"] for row in descriptor}
    require(visible == set(sources.references), "runtime.only_task_public_snapshots")
    for row in descriptor:
        if "complete_original_snapshot" in row:
            require(
                row["complete_original_snapshot"]
                == sources.references[row["source_id"]]["complete_original_snapshot"],
                "runtime.frozen_source_descriptor",
            )
    return public


def generate(
    public_messages,
    identity,
    sources,
    *,
    scripted=None,
    provider=None,
    requested_basis="neutral",
    max_responses=MAX_RESPONSES,
    max_tools=MAX_TOOLS,
):
    """Run scripts or one live callback per response, preserving every public byte.

    A live callback receives ``(messages, context)`` and returns a raw response
    string or ``{raw_response, receipt}``. It must enforce the separately frozen
    model token/context and cumulative budget contract without dropping history.
    No callback retry exists here. A provider exception becomes an incomplete
    session with its already-observed history preserved, never a partial pool.
    """
    public_document(public_messages, identity, sources)
    require((scripted is None) != (provider is None), "runtime.exactly_one_response_source")
    require(scripted is None or isinstance(scripted, (list, tuple)), "runtime.scripted_sequence")
    require(provider is None or callable(provider), "runtime.provider_callback")
    require(requested_basis in {"neutral", "endpoint", "movement"}, "runtime.guidance_label")
    require(
        type(max_responses) is int
        and 1 <= max_responses <= MAX_RESPONSES
        and type(max_tools) is int
        and 0 <= max_tools <= MAX_TOOLS,
        "runtime.session_limits",
    )
    initial = [
        {"role": "system", "content": SYSTEM + "\nRequested guidance: " + requested_basis},
        *copy.deepcopy(public_messages),
    ]
    messages, turns, events, outputs = copy.deepcopy(initial), [], [], {}
    origin = "scripted_evaluation_control" if scripted is not None else "live_evaluation_callback"
    terminal, first_final, final, provider_calls, provider_error = (
        "response_budget_exhausted",
        None,
        None,
        0,
        None,
    )
    for index in range(max_responses):
        if scripted is not None and index >= len(scripted):
            terminal = "script_exhausted_without_final"
            break
        receipt = None
        if scripted is not None:
            supplied = scripted[index]
        else:
            context = {
                "identity": copy.deepcopy(identity),
                "response_index": index,
                "max_responses": max_responses,
                "max_tools": max_tools,
                "remaining_tool_calls": max_tools - len(outputs),
                "history_must_not_be_truncated": True,
            }
            provider_calls += 1
            try:
                supplied = provider(copy.deepcopy(messages), context)
                if isinstance(supplied, dict) and "raw_response" in supplied:
                    require(
                        set(supplied) <= {"raw_response", "receipt"},
                        "runtime.provider_response_fields",
                    )
                    receipt, supplied = (
                        copy.deepcopy(supplied.get("receipt")),
                        supplied["raw_response"],
                    )
                require(isinstance(supplied, str), "runtime.live_raw_response_required")
            except Exception as error:  # Transport is an injected, separately budgeted boundary.
                terminal, provider_error = (
                    "provider_error",
                    type(error).__name__ + ": " + str(error),
                )
                break
        raw = supplied if isinstance(supplied, str) else encode(supplied).decode()
        turns.append(
            {
                "response_index": index,
                "input_messages": copy.deepcopy(messages),
                "raw_response": raw,
                "raw_response_sha256": sha(raw.encode()),
                "origin": origin,
                "provider_receipt": receipt,
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
        if len(raw.encode()) > MAX_RESPONSE_BYTES:
            terminal = "response_byte_limit"
            event["protocol_error"] = "runtime.response_byte_limit"
            events.append(event)
            break
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
            identifier = "tool:" + str(len(outputs) + 1)
            tool = {
                "call_id": identifier,
                "tool": choice["tool"],
                "arguments": choice["arguments"],
                "status": "ok",
                "result": None,
            }
            try:
                tool["result"] = execute(tool["tool"], tool["arguments"], sources, outputs)
            except (
                ValueError,
                TypeError,
                KeyError,
                IndexError,
                ZeroDivisionError,
                SyntaxError,
                RecursionError,
            ) as error:
                tool.update(status="error", error=str(error))
            outputs[identifier], event["tool_call"] = tool, copy.deepcopy(tool)
            feedback = {"tool_observation": tool}
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            event["protocol_error"] = str(error)
            feedback = {
                "protocol_error": (
                    "Return one JSON tool or final object; no financial assessment was performed."
                )
            }
        events.append(event)
        messages.append({"role": "user", "content": encode(feedback).decode()})
    return record(
        "evaluation_session",
        identity=copy.deepcopy(identity),
        initial_messages=initial,
        public_messages=copy.deepcopy(public_messages),
        source_descriptors=sources.descriptors(),
        requested_basis=requested_basis,
        turns=turns,
        events=events,
        terminal=terminal,
        first_final_index=first_final,
        raw_final=final,
        max_responses=max_responses,
        max_tools=max_tools,
        origin=origin,
        provider_calls=provider_calls,
        provider_error=provider_error,
        private_oracle_access=False,
        training_eligible=False,
        training_samples=0,
        model_weight_loads=0,
        gpu_calls=0,
        context_token_enforcement="separately_frozen_provider_callback",
    )
