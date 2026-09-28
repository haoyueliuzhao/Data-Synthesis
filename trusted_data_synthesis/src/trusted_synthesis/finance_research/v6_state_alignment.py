"""Finite task-local semantic alignment after sealed per-trajectory judgments.

Each request sees one reviewer's own eight judgments only. Two agreed partitions
are not statistical independence or proof. No calls, data writes or training here.
"""

from __future__ import annotations

import copy
import hashlib
import json
from itertools import combinations
from typing import Literal

from .contracts import digest
from .semantic_review import (
    MaskSpan,
    NonassertiveMaskSpan,
    NonassertiveSlotReview,
    ReviewError,
    SlotReview,
    _canonical_mask,
    _encoding_manifest,
    _reaches_answer,
    _Record,
    _strict_json,
    document_index,
)
from .v6_strict_review import _catalog as _flat_catalog

WIRE_PROTOCOL = "v6_alignment_review.v3"
PAIR_KEYS = tuple(f"s{i}_s{j}" for i, j in combinations(range(8), 2))
REQUIRED_CHECKS = (
    "sealed",
    "history_complete",
    "calls_settled",
    "actions_observations_bound",
    "private_reference_isolated",
)


class PairJudgment(_Record):
    relation: Literal["equivalent", "distinct", "unknown", "not_applicable"]
    basis: Literal[
        "same_semantic_process",
        "source_selection",
        "verification",
        "semantic_revision",
        "derivation",
        "unresolved",
        "not_applicable",
    ]
    left_nodes: list[str]
    right_nodes: list[str]
    evidence: list[str]
    semantic_basis: str
    accepted_answer_path_relation: Literal["same", "substantively_different", "unknown"]
    surface_or_redundant_only: Literal["yes", "no", "unknown"]


def _require(condition, message):
    if not condition:
        raise ReviewError(message)


def _slot_order(prepared):
    slots = [slot["slot_id"] for slot in prepared["bundle"]["slots"]]
    _require(len(slots) == len(set(slots)) == 8, "all eight original slots required")
    return slots


def _slot_inputs(prepared, reviews, reviewer, *, allow_nonassertive_context=False):
    _require(type(reviewer) is int and reviewer in (0, 1), "invalid reviewer coordinate")
    slots = _slot_order(prepared)
    _require(
        isinstance(reviews, dict) and set(reviews) == set(slots),
        "all eight slot judgments required",
    )
    bundle_hash = digest(prepared["bundle"])
    for sid in slots:
        item = reviews[sid]
        _require(
            item.get("reviewer") == reviewer
            and type(item.get("reviewer")) is int
            and item.get("slot_id") == sid
            and item.get("task_id") == prepared["bundle"]["task_id"]
            and item.get("task_bundle_sha256") == bundle_hash
            and item.get("v_trace") in {"valid", "invalid", "unknown"},
            "slot judgment is not this reviewer's bound original slot",
        )
        if item["v_trace"] == "valid":
            _require(
                isinstance(item.get("derived"), dict)
                and isinstance(item.get("parsed", {}).get("slot"), dict),
                "effective valid slot requires its validated original graph",
            )
        _validate_slot_shape(item, allow_nonassertive_context=allow_nonassertive_context)
        checks = prepared["mechanical"][sid]
        _require(
            all(
                type(checks.get(k)) is bool or checks.get(k) is None
                for k in (*REQUIRED_CHECKS, "native_correct")
            )
            and all(k in checks for k in (*REQUIRED_CHECKS, "native_correct")),
            "mechanical checks must explicitly retain unknown values",
        )
    return slots


def _validate_slot_shape(item, *, allow_nonassertive_context=False):
    parsed = (item.get("parsed") or {}).get("slot")
    if parsed is not None:
        model = NonassertiveSlotReview if allow_nonassertive_context is True else SlotReview
        try:
            model.model_validate(parsed)
        except ValueError as error:
            raise ReviewError("sealed slot shape is outside this alignment version") from error


def _own_eligible(prepared, reviews, slots):
    return [
        sid
        for sid in slots
        if reviews[sid]["v_trace"] == "valid"
        and prepared["mechanical"][sid]["native_correct"] is True
        and all(prepared["mechanical"][sid][key] is True for key in REQUIRED_CHECKS)
    ]


def _catalog(prepared):
    docs = document_index(prepared["bundle"])
    public, local = _flat_catalog(docs)
    ordered = {f"s{i}": sid for i, sid in enumerate(_slot_order(prepared))}
    reverse = {sid: alias for alias, sid in ordered.items()}
    old_aliases = local["slot_aliases"]
    for item in public.values():
        if item["slot_id"] is not None:
            item["slot_id"] = reverse[old_aliases[item["slot_id"]]]
    local["slot_aliases"] = ordered
    return docs, public, local


def alignment_rubric(reviewer):
    return (
        "Align semantic states within this one task, using only the supplied original public "
        "trajectories and YOUR OWN already sealed per-slot judgments. Do not rejudge V_trace, "
        "native correctness or positive masks. No other reviewer's judgments are shown. "
        "Call submit_review exactly once. Return only pairs with ALL 28 fixed keys "
        "s0_s1,...,s6_s7; "
        "do not repeat trajectories, propositions, masks, terms, or graph definitions. "
        "Aliases and eIDs are locators, never semantic identities. Node IDs must name actual "
        "accepted nodes in your own corresponding slot graph. Evidence eIDs must quote both "
        "original trajectories, not just shared sources or another slot. Only pairs whose "
        "two slots are in own_eligible_ids are applicable; all other pairs are not_applicable. "
        "For equivalent, affirm BOTH finite criteria: the accepted financial reasoning/process "
        "path to the answer is the same, and any differences are only surface or redundant. "
        "Wording, term aliases, graph node labels, tool order/count, repeated reads/calculations, "
        "and response length alone never define a different state. Exact equality of free-form "
        "graph descriptions is NOT required for equivalence. For distinct, identify a material "
        "source_selection, verification, semantic_revision or derivation difference that "
        "actually contributes to the accepted answer path. Cite accepted nodes reaching an "
        "answer on both sides, both original trajectories, and explain the semantic difference. "
        "A verification/revision requires the actual information-changing action/observation "
        "and accepted consequence already established in your slot judgment; format repair or "
        "redundancy is insufficient. Choose unknown when either criterion or evidence is "
        "insufficient; never drop a hard-to-map eligible package. Equivalence must be transitive. "
        "This is a finite model-assisted semantic judgment, not proof or an independence claim. "
        f"Review context index: {reviewer}; only that context's judgments are available."
    )


def _strict_tool(catalog):
    properties = PairJudgment.model_json_schema()["properties"]
    pair = {
        "type": "object",
        "properties": {},
        "required": list(properties),
        "additionalProperties": False,
    }
    for key, original in properties.items():
        value = {
            name: copy.deepcopy(original[name])
            for name in ("type", "enum", "items")
            if name in original
        }
        if key == "evidence":
            value["items"] = {
                "type": "string",
                "enum": sorted(catalog, key=lambda eid: int(eid[1:])),
            }
        pair["properties"][key] = value
    pairs = {
        "type": "object",
        "properties": {key: copy.deepcopy(pair) for key in PAIR_KEYS},
        "required": list(PAIR_KEYS),
        "additionalProperties": False,
    }
    return {
        "type": "function",
        "function": {
            "name": "submit_review",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {"pairs": pairs},
                "required": ["pairs"],
                "additionalProperties": False,
            },
        },
    }


def _summary(item, local):
    """One side's necessary accepted graph context, using the same flat evidence IDs."""
    parsed = item.get("parsed") or {}
    slot = parsed.get("slot") or {}
    graph = slot.get("semantic_graph", {"nodes": [], "edges": []})
    accepted = [node for node in graph["nodes"] if node["accepted"]]
    nodes = {node["node_id"] for node in accepted}
    updates = slot.get("updates", [])
    needed_props = {key for node in accepted for key in node["proposition_ids"]}
    needed_props.update(
        update[key] for update in updates for key in ("prior_proposition", "posterior_proposition")
    )
    needed_terms = {key for node in accepted for key in node["term_ids"]}
    by_doc, by_span = {}, {}
    for eid in sorted(local["spans"], key=lambda value: int(value[1:])):
        span = local["spans"][eid]
        by_doc.setdefault(span["doc_id"], []).append(eid)
        by_span[digest(span)] = eid

    def project(value, key=None):
        if isinstance(value, dict):
            if set(value) == {"doc_id", "start", "end", "quote"}:
                _require(digest(value) in by_span, "sealed slot evidence lost original fragment")
                return by_span[digest(value)]
            return {name: project(child, name) for name, child in value.items()}
        if isinstance(value, list):
            if key == "source_doc_ids":
                return [eid for doc in value for eid in by_doc[doc]]
            return [project(child) for child in value]
        if key in {"action_doc_id", "observation_doc_id"}:
            return by_doc[value][0]
        return value

    return project(
        {
            "effective_v_trace": item["v_trace"],
            "reported_v_trace": item.get("reported_v_trace", slot.get("v_trace")),
            "semantic_validation_error": item.get("semantic_validation_error"),
            "terms": [term for term in parsed.get("terms", []) if term["term_id"] in needed_terms],
            "propositions": [
                prop
                for prop in slot.get("propositions", [])
                if prop["proposition_id"] in needed_props
            ],
            "semantic_graph": {
                "nodes": accepted,
                "edges": [
                    edge
                    for edge in graph["edges"]
                    if edge["from_node"] in nodes and edge["to_node"] in nodes
                ],
            },
            "updates": updates,
            "chi": (item.get("derived") or {}).get("chi"),
        }
    )


def alignment_request(
    prepared, slot_reviews_for_one_reviewer, reviewer=0, *, allow_nonassertive_context=False
):
    """No joint-valid roster or other-reviewer result is read or placed in this request."""
    reviews = slot_reviews_for_one_reviewer
    slots = _slot_inputs(
        prepared, reviews, reviewer, allow_nonassertive_context=allow_nonassertive_context
    )
    docs, public, local = _catalog(prepared)
    reverse = {sid: alias for alias, sid in local["slot_aliases"].items()}
    judgments = {}
    for sid in slots:
        judgments[reverse[sid]] = _summary(reviews[sid], local)
    rubric, tool = alignment_rubric(reviewer), _strict_tool(public)
    own_eligible = _own_eligible(prepared, reviews, slots)
    payload = {
        "wire_protocol": WIRE_PROTOCOL,
        "task_id": prepared["bundle"]["task_id"],
        "task_bundle_sha256": digest(prepared["bundle"]),
        "reviewer": reviewer,
        "document_catalog": public,
        "own_slot_judgments": judgments,
        "own_eligible_ids": [reverse[sid] for sid in own_eligible],
        "pair_keys": list(PAIR_KEYS),
    }
    messages = [
        dict(role="system", content=rubric),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    return {
        "wire_protocol": WIRE_PROTOCOL,
        "model": "deepseek-flash",
        "task_id": prepared["bundle"]["task_id"],
        "reviewer": reviewer,
        "messages": messages,
        "task_bundle_sha256": digest(prepared["bundle"]),
        "document_index": docs,
        "document_catalog": public,
        "compact_catalog": local,
        "catalog_sha256": digest(public),
        "compact_catalog_sha256": digest(local),
        "strict_tool": tool,
        "strict_tool_sha256": digest(tool),
        "rubric_sha256": digest(rubric),
        "messages_model_sha256": digest(dict(model="deepseek-flash", messages=messages)),
        "private_reference_for_review_only": True,
        "private_reference_in_alignment": False,
        "other_reviewer_output_visible": False,
        "own_eligible_slot_ids": own_eligible,
        "slot_review_bindings": {sid: digest(reviews[sid]) for sid in slots},
        "own_slot_reviews": copy.deepcopy(reviews),
    }


def _checked_request(request, *, allow_nonassertive_context=False):
    _require(
        request.get("wire_protocol") == WIRE_PROTOCOL
        and request.get("model") == "deepseek-flash"
        and request.get("other_reviewer_output_visible") is False,
        "alignment protocol/model/isolated context mismatch",
    )
    messages = request["messages"]
    _require(
        len(messages) == 2
        and messages[0] == {"role": "system", "content": alignment_rubric(request["reviewer"])}
        and digest(messages[0]["content"]) == request["rubric_sha256"]
        and digest(dict(model="deepseek-flash", messages=messages))
        == request["messages_model_sha256"],
        "alignment messages or rubric changed",
    )
    payload = _strict_json(messages[1]["content"])
    _require(
        payload["wire_protocol"] == WIRE_PROTOCOL
        and payload["reviewer"] == request["reviewer"]
        and payload["task_bundle_sha256"] == request["task_bundle_sha256"]
        and payload["document_catalog"] == request["document_catalog"]
        and digest(request["document_catalog"]) == request["catalog_sha256"]
        and digest(request["compact_catalog"]) == request["compact_catalog_sha256"]
        and request["strict_tool"] == _strict_tool(request["document_catalog"])
        and digest(request["strict_tool"]) == request["strict_tool_sha256"],
        "alignment request/catalog/schema binding changed",
    )
    aliases = request["compact_catalog"]["slot_aliases"]
    _require(
        set(aliases) == {f"s{i}" for i in range(8)}
        and len(set(aliases.values())) == 8
        and set(request["own_slot_reviews"]) == set(aliases.values()),
        "alignment slot aliases changed",
    )
    for alias, sid in aliases.items():
        item = request["own_slot_reviews"][sid]
        _validate_slot_shape(item, allow_nonassertive_context=allow_nonassertive_context)
        _require(
            digest(item) == request["slot_review_bindings"][sid]
            and item["reviewer"] == request["reviewer"]
            and item["slot_id"] == sid
            and item["task_bundle_sha256"] == request["task_bundle_sha256"]
            and payload["own_slot_judgments"][alias] == _summary(item, request["compact_catalog"]),
            "alignment is not bound to this side's sealed judgments",
        )
    _require(
        payload["own_eligible_ids"]
        == [alias for alias, sid in aliases.items() if sid in request["own_eligible_slot_ids"]],
        "own eligibility changed",
    )
    for eid, span in request["compact_catalog"]["spans"].items():
        doc = request["document_index"][span["doc_id"]]
        _require(
            doc["text"][span["start"] : span["end"]]
            == span["quote"]
            == request["document_catalog"][eid]["text"],
            "catalog no longer quotes original",
        )
    return payload


def _semantic_pair(pair, left, right, request, evidence, *, allow_nonassertive_context=False):
    own = set(request["own_eligible_slot_ids"])
    applicable = left in own and right in own
    if not applicable:
        return (
            None
            if pair.relation == "not_applicable" and pair.basis == "not_applicable"
            else "inapplicable_pair_must_not_define_state"
        )
    if pair.relation == "unknown":
        return None
    if pair.relation == "not_applicable":
        return "eligible_pair_cannot_be_dropped"
    if not pair.semantic_basis.strip():
        return "missing_substantive_semantic_basis"
    if {request["document_index"][span["doc_id"]]["slot_id"] for span in evidence} - {None} != {
        left,
        right,
    }:
        return "substantive_judgment_needs_both_original_trajectories"
    graphs, named = [], []
    for sid, names in ((left, pair.left_nodes), (right, pair.right_nodes)):
        model = NonassertiveSlotReview if allow_nonassertive_context is True else SlotReview
        slot = model.model_validate(request["own_slot_reviews"][sid]["parsed"]["slot"])
        nodes = {node.node_id: node for node in slot.semantic_graph.nodes}
        if not names or any(
            not nodes[name].accepted or not _reaches_answer(slot.semantic_graph, name)
            for name in names
        ):
            return "distinction_or_equivalence_lacks_accepted_answer_path"
        graphs.append(slot)
        named.append([nodes[name] for name in names])
    if pair.relation == "equivalent":
        if (
            pair.basis != "same_semantic_process"
            or pair.accepted_answer_path_relation != "same"
            or pair.surface_or_redundant_only != "yes"
        ):
            return "equivalence_finite_criteria_not_established"
        return None
    if (
        pair.basis not in {"source_selection", "verification", "semantic_revision", "derivation"}
        or pair.accepted_answer_path_relation != "substantively_different"
        or pair.surface_or_redundant_only != "no"
    ):
        return "surface_redundancy_cannot_define_state"
    if not any(node.predicate == pair.basis for nodes in named for node in nodes):
        return "material_basis_absent_from_named_accepted_graph_nodes"
    if pair.basis in {"verification", "semantic_revision"}:
        if not any(
            update["kind"] == pair.basis
            for sid in (left, right)
            for update in request["own_slot_reviews"][sid]["derived"]["chi_evidence"]
        ):
            return "information_changing_update_not_established"
    return None


def _validate_alignment(raw, request, *, allow_nonassertive_context=False):
    """Bad shape/IDs raise; finite semantic contradictions remain reported + unknown."""
    _checked_request(request, allow_nonassertive_context=allow_nonassertive_context)
    value = _strict_json(raw)
    _require(
        isinstance(value, dict)
        and set(value) == {"pairs"}
        and isinstance(value["pairs"], dict)
        and set(value["pairs"]) == set(PAIR_KEYS),
        "exact fixed 28-pair object required",
    )
    aliases, spans = request["compact_catalog"]["slot_aliases"], request["compact_catalog"]["spans"]
    result = {}
    for key in PAIR_KEYS:
        pair = PairJudgment.model_validate(value["pairs"][key])
        left_alias, right_alias = key.split("_")
        left, right = aliases[left_alias], aliases[right_alias]
        for sid, names in ((left, pair.left_nodes), (right, pair.right_nodes)):
            slot = (request["own_slot_reviews"][sid].get("parsed") or {}).get("slot") or {}
            node_ids = {node["node_id"] for node in slot.get("semantic_graph", {}).get("nodes", [])}
            _require(
                len(set(names)) == len(names) and set(names) <= node_ids,
                "pair cites nonexistent actual slot graph node",
            )
        _require(
            len(set(pair.evidence)) == len(pair.evidence) and set(pair.evidence) <= set(spans),
            "pair cites missing/duplicate original evidence ID",
        )
        evidence = [copy.deepcopy(spans[eid]) for eid in pair.evidence]
        _require(
            all(
                request["document_index"][span["doc_id"]]["slot_id"] in {None, left, right}
                for span in evidence
            ),
            "pair evidence belongs to another slot",
        )
        semantic_error = _semantic_pair(
            pair,
            left,
            right,
            request,
            evidence,
            allow_nonassertive_context=allow_nonassertive_context,
        )
        result[key] = {
            **pair.model_dump(),
            "left": left,
            "right": right,
            "reported_relation": pair.relation,
            "relation": "unknown" if semantic_error else pair.relation,
            "semantic_validation_error": semantic_error,
            "expanded_evidence": evidence,
        }
    return {
        "schema": "v6_state_alignment.v3",
        "wire_protocol": WIRE_PROTOCOL,
        "reviewer": request["reviewer"],
        "task_bundle_sha256": request["task_bundle_sha256"],
        "interface_valid": True,
        "interface_admitted": True,
        "semantic_consistent": not any(row["semantic_validation_error"] for row in result.values()),
        "task_id": request["task_id"],
        "pairs": result,
        "own_eligible_slot_ids": request["own_eligible_slot_ids"],
        "slot_review_bindings": request["slot_review_bindings"],
        "catalog_sha256": request["catalog_sha256"],
        "raw_review_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "alignment_request_sha256": digest(request),
        "semantic_repair_performed": False,
        "other_reviewer_output_visible": False,
        "strict_format_is_semantic_correctness": False,
    }


def validate_alignment(raw, request, *, allow_nonassertive_context=False):
    """Only shape/coordinate errors raise; semantic inconsistency is retained unknown."""
    try:
        return _validate_alignment(
            raw, request, allow_nonassertive_context=allow_nonassertive_context
        )
    except ReviewError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError) as failure:
        raise ReviewError(f"alignment interface {type(failure).__name__}: {failure}") from failure


def inspect_alignment(raw, request, *, allow_nonassertive_context=False):
    """Mechanical capacity gate independent of successful material/state yield."""
    try:
        result = validate_alignment(
            raw, request, allow_nonassertive_context=allow_nonassertive_context
        )
    except ReviewError as failure:
        return {
            "interface_admitted": False,
            "semantic_consistent": False,
            "validation": None,
            "error": str(failure),
            "error_kind": "mechanical_interface",
            "reviewer": request.get("reviewer"),
            "task_id": request.get("task_id"),
            "task_bundle_sha256": request.get("task_bundle_sha256"),
            "slot_review_bindings": request.get("slot_review_bindings"),
            "raw_review_sha256": hashlib.sha256(raw.encode()).hexdigest()
            if isinstance(raw, str)
            else None,
            "pairs": None,
        }
    errors = [
        row["semantic_validation_error"]
        for row in result["pairs"].values()
        if row["semantic_validation_error"]
    ]
    return {
        "interface_admitted": True,
        "semantic_consistent": result["semantic_consistent"],
        "validation": result,
        "error": errors or None,
        "error_kind": "semantic_inconsistency" if errors else None,
    }


def resolve_decomposed_pair(
    prepared,
    slot_reviews0,
    slot_reviews1,
    alignment0,
    alignment1,
    *,
    allow_nonassertive_context=False,
):
    """Classify every jointly eligible original package together or leave all unmapped."""
    sides = (slot_reviews0, slot_reviews1)
    slots = _slot_inputs(
        prepared, slot_reviews0, 0, allow_nonassertive_context=allow_nonassertive_context
    )
    _slot_inputs(prepared, slot_reviews1, 1, allow_nonassertive_context=allow_nonassertive_context)
    docs = document_index(prepared["bundle"])
    results, mapping_errors = {}, []
    for sid in slots:
        a, b = sides[0][sid], sides[1][sid]
        checks = prepared["mechanical"][sid]
        clean = all(checks[name] is True for name in REQUIRED_CHECKS)
        v_trace = a["v_trace"] if a["v_trace"] == b["v_trace"] and clean else "unknown"
        eligible = checks["native_correct"] is True and v_trace == "valid"
        da, db = a.get("derived"), b.get("derived")
        mask_model = NonassertiveMaskSpan if allow_nonassertive_context is True else MaskSpan
        mask_a = (
            _canonical_mask([mask_model.model_validate(m) for m in a["parsed"]["slot"]["mask"]])
            if da
            else None
        )
        mask_b = (
            _canonical_mask([mask_model.model_validate(m) for m in b["parsed"]["slot"]["mask"]])
            if db
            else None
        )
        mask_agreement = bool(
            da and db and da["mask_complete"] and db["mask_complete"] and mask_a == mask_b
        )
        chi_agreed = bool(
            da and db and type(da["chi"]) is int and da["chi"] in (0, 1) and da["chi"] == db["chi"]
        )
        if eligible and (
            not chi_agreed or not da["mapping_established"] or not db["mapping_established"]
        ):
            mapping_errors.append(
                {"slot_id": sid, "reason": "unestablished_graph_or_chi_disagreement"}
            )
        encoded = (
            _encoding_manifest(sid, a["parsed"]["slot"], b["parsed"]["slot"], mask_a, docs)
            if mask_agreement and eligible
            else None
        )
        if encoded is not None:
            encoded["consensus_sha256"] = digest(
                dict(
                    slot_id=sid,
                    mask=mask_a,
                    reviews=[a["raw_review_sha256"], b["raw_review_sha256"]],
                )
            )
        results[sid] = {
            "q_native": checks["native_correct"],
            "v_trace": v_trace,
            "per_reviewer_v_trace": [a["v_trace"], b["v_trace"]],
            "common_material_valid": eligible,
            "common_material_exclusion": None
            if eligible
            else "native_incorrect"
            if checks["native_correct"] is False
            else "native_unknown"
            if checks["native_correct"] is None
            else "process_" + v_trace,
            "mapper": "pending" if eligible else "not_applicable",
            "state_id": None,
            "chi": da["chi"] if eligible and chi_agreed else None,
            "semantic_graph": None,
            "semantic_graphs": [
                copy.deepcopy((r.get("parsed") or {}).get("slot", {}).get("semantic_graph"))
                for r in (a, b)
            ],
            "chi_evidence": [
                copy.deepcopy(r["derived"]["chi_evidence"]) if r.get("derived") else []
                for r in (a, b)
            ],
            "mask_status": "agreed" if mask_agreement else "unknown",
            "positive_target_mask": mask_a if mask_agreement else None,
            "encoding_manifest": encoded,
        }
    eligible = [sid for sid in slots if results[sid]["common_material_valid"]]
    parents = {sid: sid for sid in eligible}

    def find(sid):
        while parents[sid] != sid:
            sid = parents[sid]
        return sid

    alignments = (alignment0, alignment1)
    usable_alignments = []
    for reviewer, alignment in enumerate(alignments):
        if alignment is None:
            if len(eligible) > 1:
                mapping_errors.append({"reviewer": reviewer, "reason": "missing_alignment"})
            continue
        _require(
            alignment.get("reviewer") == reviewer
            and alignment.get("task_bundle_sha256") == digest(prepared["bundle"])
            and alignment.get("slot_review_bindings")
            == {sid: digest(sides[reviewer][sid]) for sid in slots},
            "alignment is bound to different slot judgments",
        )
        if alignment.get("interface_admitted") is not True:
            if len(eligible) > 1:
                mapping_errors.append(
                    {"reviewer": reviewer, "reason": "alignment_interface_unknown"}
                )
            continue
        _require(set(alignment["pairs"]) == set(PAIR_KEYS), "validated alignment lost pairs")
        usable_alignments.append(alignment)
    pair_decisions = []
    if len(usable_alignments) == 2:
        for i, j in combinations(range(8), 2):
            left, right, key = slots[i], slots[j], f"s{i}_s{j}"
            if left not in parents or right not in parents:
                continue
            a, b = alignment0["pairs"][key], alignment1["pairs"][key]
            agreed = a["relation"] == b["relation"] and a["relation"] in {"equivalent", "distinct"}
            pair_decisions.append(
                {
                    "pair_key": key,
                    "left": left,
                    "right": right,
                    "reviewer_judgments": [a, b],
                    "agreed": agreed,
                }
            )
            if not agreed:
                mapping_errors.append({"pair_key": key, "reason": "pair_unknown_or_disagreement"})
            elif a["relation"] == "equivalent":
                parents[find(right)] = find(left)
        for row in pair_decisions:
            if (
                row["agreed"]
                and row["reviewer_judgments"][0]["relation"] == "distinct"
                and find(row["left"]) == find(row["right"])
            ):
                mapping_errors.append(
                    {"pair_key": row["pair_key"], "reason": "nontransitive_equivalence"}
                )
    groups = {}
    for sid in eligible:
        groups.setdefault(find(sid), []).append(sid)
    for members in groups.values():
        if len({results[sid]["chi"] for sid in members}) != 1:
            mapping_errors.append(
                {"slot_ids": members, "reason": "chi_inconsistent_in_equivalence_class"}
            )
    complete = bool(eligible) and not mapping_errors
    definitions = {}
    if complete:
        for index, members in enumerate(
            sorted(groups.values(), key=lambda group: slots.index(group[0]))
        ):
            state_id = f"z{index}"
            definitions[state_id] = {
                "slot_ids": members,
                "chi": results[members[0]]["chi"],
                "definition": (
                    "finite dual semantic pair judgments and accepted answer-path evidence; "
                    "label is only task-local"
                ),
                "per_slot_review_graphs": {sid: results[sid]["semantic_graphs"] for sid in members},
                "per_slot_review_terms": {
                    sid: [copy.deepcopy(side[sid]["parsed"]["terms"]) for side in sides]
                    for sid in members
                },
                "pair_judgments": [
                    row
                    for row in pair_decisions
                    if row["left"] in members or row["right"] in members
                ],
            }
            for sid in members:
                results[sid].update(mapper="mapped", state_id=state_id)
    else:
        for sid in eligible:
            results[sid].update(mapper="unknown", chi=None)
    return {
        "schema": "v6_decomposed_pair_resolution.v3",
        "task_id": prepared["bundle"]["task_id"],
        "slots": results,
        "task_mapping": "complete" if complete else "incomplete",
        "mapping_errors": mapping_errors,
        "state_definitions": definitions,
        "valid_slots_retained": eligible,
        "process_valid_slots_retained": [
            sid for sid in slots if results[sid]["v_trace"] == "valid"
        ],
        "common_valid_definition": (
            "native correctness true AND both effective finite process judgments valid"
        ),
        "all_eight_candidates_retained": True,
        "no_dropping_hard_to_map_valid_packages": True,
        "human_reviewed": False,
        "mathematical_proof": False,
        "same_model_reviews_statistically_independent": False,
        "alignment_called": [alignment is not None for alignment in alignments],
        "review_hashes": [[side[sid]["raw_review_sha256"] for sid in slots] for side in sides],
        "alignment_hashes": [
            alignment["raw_review_sha256"] if alignment else None for alignment in alignments
        ],
    }
