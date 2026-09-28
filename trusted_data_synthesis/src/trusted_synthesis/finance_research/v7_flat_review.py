"""Prospective flat review wire; no repair or reclassification of old responses.

The registered bijection only moves graph arrays and records explicit keyed-array
IDs. Original v5 semantic validation remains authoritative after exact coverage.
"""

from __future__ import annotations

import copy
import hashlib
import json

from . import v7_mask_review as baseline
from .contracts import digest
from .semantic_review import ReviewError, _strict_json
from .v6_compact_review import _require
from .v6_slot_review import capacity_features
from .v7_review_coherence import COHERENCE_APPENDIX, POLICY, coherence_constraints

WIRE_PROTOCOL = "v6_slot_review.v6"
FLAT_APPENDIX = """
PROSPECTIVE FLAT WIRE (SEMANTICS AND ORIGINAL EVIDENCE UNCHANGED):
Submit exactly ONE JSON object as submit_review arguments; no commentary, note
fields, second object, extra closing brace or trailing data. The ROOT fields are:
terms, nodes, edges, v_trace, reason_codes, coverage_complete, propositions,
actions, updates, mask. There is NO semantic_graph wrapper. Terms, nodes and edges
are separate ROOT arrays; keep terms out of nodes and edges. All fields are
required, using empty arrays only when the original evidence warrants no records.
actions is an array of records with action_id plus label, proposition_ids and
evidence. Include each original action ID exactly once. mask is an array of
records with target_id plus label and proposition_ids. Include each original
public-content/action target ID exactly once. Do not omit, duplicate, invent or
replace IDs. Empty domains require empty arrays. Record order is not semantic.
Typed locator roles, complete original coverage and all existing semantic tests
still apply. This replaces ONLY keyed actions/mask maps and the graph wrapper
described above; it does not authorize a new judgment or supplied evidence.
"""


def _array_schema(original, id_field):
    """Group identical schemas: constant record shape, role-specific ID enums."""
    groups = {}
    for name, item in sorted(original["properties"].items()):
        group = groups.setdefault(digest(item), dict(item=item, ids=[]))
        group["ids"].append(name)
    alternatives = []
    for group in groups.values():
        item = copy.deepcopy(group["item"])
        item["properties"][id_field] = dict(type="string", enum=group["ids"])
        item["required"] = sorted(item["properties"])
        alternatives.append(item)
    # Empty enums/minItems/maxItems are not sent. The host rejects any row when
    # the original domain is empty, without inventing a sentinel document ID.
    if not alternatives:
        alternatives = [
            dict(
                type="object",
                properties={id_field: dict(type="string")},
                required=[id_field],
                additionalProperties=False,
            )
        ]
    return dict(
        type="array", items=alternatives[0] if len(alternatives) == 1 else dict(anyOf=alternatives)
    )


def _request(base):
    _require(base.get("wire_protocol") == "v6_slot_review.v5", "flat wire needs v5 baseline")
    typed = base["typed_baseline_request"]
    _require(digest(typed) == base["typed_baseline_request_sha256"], "v5 baseline changed")
    _require(
        all(base.get(k) == v for k, v in baseline._request(typed).items()),
        "flat semantic baseline request differs",
    )
    result = copy.deepcopy(base)
    tool = result["strict_tool"]
    parameters = tool["function"]["parameters"]
    props = parameters["properties"]
    graph = props.pop("semantic_graph")
    props.update(nodes=graph["properties"]["nodes"], edges=graph["properties"]["edges"])
    props["actions"] = _array_schema(props["actions"], "action_id")
    props["mask"] = _array_schema(props["mask"], "target_id")
    parameters["required"] = sorted(props)
    payload = _strict_json(base["messages"][1]["content"])
    payload.update(wire_protocol=WIRE_PROTOCOL, coherence_policy=POLICY)
    rubric = base["messages"][0]["content"] + FLAT_APPENDIX + COHERENCE_APPENDIX
    messages = [
        dict(role="system", content=rubric),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    result.update(
        wire_protocol=WIRE_PROTOCOL,
        messages=messages,
        strict_tool_sha256=digest(tool),
        rubric_sha256=digest(rubric),
        messages_model_sha256=digest(dict(model="deepseek-flash", messages=messages)),
        flat_baseline_request=copy.deepcopy(base),
        flat_baseline_request_sha256=digest(base),
        coherence_policy=POLICY,
        coherence_constraints_sha256=digest(coherence_constraints()),
        wire_adaptation="registered graph flattening and exact-cover keyed-array bijection",
        semantic_baseline_wire_protocol="v6_slot_review.v5",
        host_semantic_repair=False,
        old_reviews_reclassified=False,
    )
    return result


def slot_review_request(prepared, slot_id, reference, reviewer=0):
    return _request(baseline.slot_review_request(prepared, slot_id, reference, reviewer))


def flat_request(v5_registered_request):
    """Derive a new request; preserve its independently registered capacity fields."""
    return _request(v5_registered_request)


def _checked_request(request):
    _require(request.get("wire_protocol") == WIRE_PROTOCOL, "wrong flat review wire")
    base = request["flat_baseline_request"]
    _require(digest(base) == request["flat_baseline_request_sha256"], "flat baseline changed")
    _require(
        all(request.get(k) == v for k, v in _request(base).items()),
        "flat request schema/catalog/rubric binding differs",
    )
    return base


def _keyed_records(rows, old_schema, id_field):
    _require(isinstance(rows, list), f"{id_field} records must be an array")
    expected, result = old_schema["properties"], {}
    for row in rows:
        _require(isinstance(row, dict), f"{id_field} record must be an object")
        name = row.get(id_field)
        _require(isinstance(name, str) and name in expected, f"unknown/wrong-kind {id_field}")
        _require(name not in result, f"duplicate {id_field}: {name}")
        props = expected[name]["properties"]
        _require(set(row) == {*props, id_field}, f"missing/extra {id_field} record fields")
        _require(row["label"] in props["label"]["enum"], f"wrong-kind {id_field} label")
        result[name] = {k: copy.deepcopy(v) for k, v in row.items() if k != id_field}
    _require(set(result) == set(expected), f"missing original {id_field} coverage")
    return result


def _mapped_arguments(raw, base):
    value = _strict_json(raw)
    old = base["strict_tool"]["function"]["parameters"]["properties"]
    _require(isinstance(value, dict), "flat review must be one JSON object")
    _require(
        set(value) == (set(old) - {"semantic_graph"}) | {"nodes", "edges"},
        "flat root missing/extra fields; no graph wrapper or notes",
    )
    value["actions"] = _keyed_records(value["actions"], old["actions"], "action_id")
    value["mask"] = _keyed_records(value["mask"], old["mask"], "target_id")
    value["semantic_graph"] = dict(nodes=value.pop("nodes"), edges=value.pop("edges"))
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def validate_slot_review(raw_arguments, request):
    try:
        base = _checked_request(request)
        mapped = _mapped_arguments(raw_arguments, base)
        result = baseline.validate_slot_review(mapped, base)
    except ReviewError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise ReviewError(f"flat interface {type(error).__name__}: {error}") from error
    result.update(
        schema=WIRE_PROTOCOL,
        wire_protocol=WIRE_PROTOCOL,
        raw_review_sha256=hashlib.sha256(raw_arguments.encode()).hexdigest(),
        flat_mapped_review_sha256=hashlib.sha256(mapped.encode()).hexdigest(),
        flat_request_sha256=digest(request),
        flat_baseline_request_sha256=request["flat_baseline_request_sha256"],
        semantic_baseline_wire_protocol="v6_slot_review.v5",
        coherence_policy=POLICY,
        original_review_reclassified=False,
        host_semantic_repair=False,
        keyed_array_mapping_is_another_model_response=False,
    )
    return result


def inspect_slot_review(raw_arguments, request):
    try:
        result = validate_slot_review(raw_arguments, request)
    except ReviewError as failure:
        return dict(
            interface_admitted=False,
            semantic_consistent=False,
            validation=None,
            v_trace="unknown",
            derived=None,
            error=str(failure),
            error_kind="mechanical_interface",
            wire_protocol=WIRE_PROTOCOL,
        )
    return dict(
        interface_admitted=True,
        semantic_consistent=result["semantic_consistent"],
        validation=result,
        error=result["semantic_validation_error"],
        error_kind=None if result["semantic_consistent"] else "semantic_inconsistency",
        wire_protocol=WIRE_PROTOCOL,
    )


__all__ = [
    "WIRE_PROTOCOL",
    "capacity_features",
    "slot_review_request",
    "flat_request",
    "validate_slot_review",
    "inspect_slot_review",
]
