"""Publish existing Action set and selected-offer constraints without changing admission."""

from __future__ import annotations

import copy
from collections import Counter
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from .protocol import record, require
from .update_public_contract import pointer
from .update_public_contract import rejection_feedback as update_rejection_feedback

VERSION = "finance_qa_action_public_contract.v1"


def public_action_contract() -> dict[str, Any]:
    rules = []

    def add(code: str, fields: dict[str, Any], requirement: str) -> None:
        rules.append(
            {
                "rule_id": VERSION + ":" + code.removeprefix("admission."),
                "error_code": code,
                "fields": fields,
                "requirement": requirement,
            }
        )

    add(
        "submission.schema",
        {"/kind": {"literal": "action"}},
        "Return one Action matching /response_schemas/action, without extra fields.",
    )
    add(
        "admission.current_state",
        {"/state_id": {"copy_from": "/state/id"}},
        "Use this current Request's State id, not any previous State.",
    )
    add(
        "admission.action_phase_budget",
        {},
        "Action requires pending_observation=null, terminal=false, and the Runtime's "
        "preregistered Action budget not exhausted. This publication does not change that budget.",
    )
    add(
        "admission.alternative_set",
        {
            "/decision/candidate_action_ids": {
                "all_ids_from": "/available_actions",
                "id_field": "id",
                "comparison": "set_equal_and_unique",
                "order_significant": False,
            },
        },
        "List EVERY id in the CURRENT Request's /available_actions, exactly once: "
        "set(candidate_action_ids) equals the set of all current available Action ids, "
        "and len(candidate_action_ids) equals len(set(candidate_action_ids)). "
        "This is the full available list, NOT just the selected Action, your considered subset, "
        "or one obligation's alternatives. Do not use an initial or previous State's list. "
        "Newly enabled Actions may appear after Claim acceptance; the list need not only shrink. "
        "Any permutation of this ID list is permitted. "
        "Only this field uses unordered set equality.",
    )
    add(
        "admission.selected_action",
        {
            "/decision/selected_action_id": {
                "choose_id_from": "/available_actions",
                "id_field": "id",
            },
        },
        "Choose ONE current available Action id yourself; "
        "this choice is separate from listing all ids.",
    )
    add(
        "admission.selected_action_content",
        {
            "/" + name: {"copy_from_selected": "/" + name}
            for name in ("operation", "inputs", "parameters")
        },
        "operation, inputs and parameters must equal the complete corresponding fields of the "
        "SAME selected Action, using existing canonical JSON equality. Preserve types, all fields, "
        "array order, roles, selectors and numeric precision; "
        "do not mix another candidate's content.",
    )
    add(
        "admission.public_judgment",
        {
            **{
                "/decision/" + name: {"copy_from_selected": "/" + name}
                for name in ("obligation_id", "subgoal", "basis", "expected_effect")
            },
            "/decision/selection_rule": {"choose_from_selected": "/selection_rules"},
            "/decision/unresolved_uncertainty_refs": {"literal": []},
        },
        "obligation_id, subgoal, basis and expected_effect must come from "
        "that SAME selected Action. "
        "Use one of its selection_rules; unresolved_uncertainty_refs must be []. "
        "basis and expected_effect use canonical JSON equality "
        "including all arrays in their given order.",
    )
    add(
        "admission.input_kind",
        {},
        "Each submitted input kind must be claim or evidence, "
        "while still matching the selected Action.",
    )
    add(
        "admission.previously_accepted_dependency",
        {},
        "Every Claim id in /decision/basis/claim_refs and in inputs with kind=claim must identify "
        "a status=accepted Claim in THIS Request's /state/accepted_claims. Pending Observations "
        "and future or other-session Claims are not accepted dependencies. Original adapter and "
        "Operation input/semantic preconditions still apply; "
        "no execution occurs during this check.",
    )
    return record(
        "action_public_contract",
        version=VERSION,
        submission_schema_unchanged=True,
        scope=(
            "existing candidate full-set, selected-offer correspondence and accepted dependencies"
        ),
        selected_binding={
            "request_collection": "/available_actions",
            "id_field": "id",
            "response_selector": "/decision/selected_action_id",
            "match_count": 1,
        },
        expression_sources={
            "copy_from": "JSON pointer in current Request",
            "all_ids_from": "id_field of every member of current Request collection",
            "choose_id_from": "one id_field value chosen by callback",
            "copy_from_selected": "JSON pointer in the selected_binding object",
            "choose_from_selected": "one member of that selected object's array",
        },
        rules=rules,
        host_fills_response_fields=False,
        host_selects_action=False,
        available_actions_filtered_by_publication=False,
        final_contract_changed=False,
        candidate_enumeration_is_evidence_of_internal_reasoning=False,
    )


def publish_action_contract(request: dict[str, Any]) -> dict[str, Any]:
    require("public_action_contract" not in request, "action_publication.already_present")
    return record(
        "request",
        **{k: v for k, v in request.items() if k not in {"id", "schema_version"}},
        public_action_contract=public_action_contract(),
    )


def _selected(request: dict[str, Any], submitted: dict[str, Any]) -> dict[str, Any]:
    binding = request["public_action_contract"]["selected_binding"]
    choice = pointer(submitted, binding["response_selector"])
    matches = [
        a
        for a in pointer(request, binding["request_collection"])
        if a[binding["id_field"]] == choice
    ]
    require(len(matches) == 1, "action_publication.selected_binding")
    return matches[0]


def _matches(
    value: Any, spec: dict[str, Any], request: dict[str, Any], submitted: dict[str, Any]
) -> bool:
    if "literal" in spec:
        return canonical_json_bytes(value) == canonical_json_bytes(spec["literal"])
    if "copy_from" in spec:
        return canonical_json_bytes(value) == canonical_json_bytes(
            pointer(request, spec["copy_from"])
        )
    if "all_ids_from" in spec:
        expected = {a[spec["id_field"]] for a in pointer(request, spec["all_ids_from"])}
        return isinstance(value, list) and len(value) == len(set(value)) and set(value) == expected
    if "choose_id_from" in spec:
        return value in {a[spec["id_field"]] for a in pointer(request, spec["choose_id_from"])}
    if "copy_from_selected" in spec:
        return canonical_json_bytes(value) == canonical_json_bytes(
            pointer(_selected(request, submitted), spec["copy_from_selected"])
        )
    if "choose_from_selected" in spec:
        return value in pointer(_selected(request, submitted), spec["choose_from_selected"])
    raise ValueError("action_publication.expression")


def rejection_feedback(
    code: str | None, request: dict[str, Any], submitted: dict[str, Any] | None
) -> dict[str, Any]:
    """Current public constraints only; never return a corrected Submission or choose an Action."""
    if (
        submitted is None
        or submitted.get("kind") != "action"
        or "public_action_contract" not in request
    ):
        return update_rejection_feedback(code, request, submitted)
    publication = request["public_action_contract"]
    matches = [r for r in publication["rules"] if r["error_code"] == code]
    if not matches:
        return {"code": code, "admitted": False}
    rule = matches[0]
    mismatches = []
    for path, spec in rule["fields"].items():
        try:
            valid = _matches(pointer(submitted, path), spec, request, submitted)
        except (ValueError, KeyError, TypeError, IndexError):
            valid = False
        if not valid:
            mismatches.append(path)
    diagnostic = {
        "contract_id": publication["id"],
        "version": publication["version"],
        "rule_id": rule["rule_id"],
        "response_field_paths": mismatches or list(rule["fields"]),
        "public_source_mapping": copy.deepcopy(rule["fields"]),
        "selected_binding": copy.deepcopy(publication["selected_binding"]),
        "requirement": rule["requirement"],
        "response_rewritten": False,
        "action_selected_by_host": False,
    }
    if code == "admission.alternative_set":
        expected = {a["id"] for a in request["available_actions"]}
        observed = submitted["decision"]["candidate_action_ids"]
        counts = Counter(observed)
        diagnostic.update(
            available_ids_source={"collection": "/available_actions", "id_field": "id"},
            missing_ids=sorted(expected - set(observed)),
            extra_ids=sorted(set(observed) - expected),
            duplicate_ids=sorted(k for k, n in counts.items() if n > 1),
        )
    return {"code": code, "admitted": False, "public_diagnostic": diagnostic}
