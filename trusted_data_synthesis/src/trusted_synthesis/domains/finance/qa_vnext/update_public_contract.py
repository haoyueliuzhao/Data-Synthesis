"""Versioned publication of existing Update rules, never a replacement validator.

The response remains callback-owned. References describe public JSON pointers;
they do not contain a pre-filled response or change the submission language.
"""

from __future__ import annotations

import copy
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from .protocol import record, require

VERSION = "finance_qa_update_public_contract.v1"


def public_update_contract() -> dict[str, Any]:
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

    def ref(path: str, mode: str = "copy_from") -> dict[str, str]:
        return {mode: path}

    pending = "/state/pending_observation"
    add(
        "submission.schema",
        {
            "/kind": {"literal": "update"},
            "/disposition": {"choose_from_literal": ["accept", "reject"]},
        },
        "Return one complete Update object satisfying /response_schemas/update; no extra fields.",
    )
    add(
        "admission.current_state",
        {"/state_id": ref("/state/id")},
        "state_id must identify this current public State.",
    )
    add("admission.terminal", {}, "Update requires /state/terminal=false.")
    add(
        "admission.pending_observation",
        {},
        "Update requires a non-null /state/pending_observation.",
    )
    add(
        "admission.observation_parent",
        {"/observation_id": ref(pending + "/id")},
        "observation_id must identify the current pending Observation.",
    )
    add(
        "admission.exact_observation_acceptance",
        {
            "/proposed_claim": {
                "by_disposition": {
                    "accept": ref(pending + "/proposition"),
                    "reject": {"literal": None},
                }
            },
        },
        "For accept, proposed_claim must equal the ENTIRE pending Observation proposition, "
        "including all outer fields, output, lineage, operation and contract fields present. "
        "Do not substitute a number, output alone, a flat Claim, the Observation wrapper, "
        "or a future Host accepted-Claim wrapper. For reject it must be null. "
        "Equality is canonical_json_bytes equality: JSON whitespace and object key order "
        "may differ; preserve all fields, JSON types, strings, array order and exact numeric "
        "content. No rounding, tolerance, coercion, omitted fields or extra fields.",
    )
    add(
        "admission.observation_assessment",
        {
            "/assessment/relation": {
                "by_disposition": {
                    "accept": {"literal": "accepts_observed_proposition"},
                    "reject": {"literal": "declines_observation"},
                }
            },
            "/assessment/observation_refs": ref(pending + "/id", "wrap_in_list_from"),
            "/assessment/evidence_refs": ref(pending + "/proposition/lineage"),
            "/assessment/fulfills_obligation": {
                "by_disposition": {
                    "accept": ref(pending + "/obligation_id"),
                    "reject": {"literal": None},
                }
            },
        },
        "assessment must have exactly these four fields with canonical JSON equality; "
        "observation_refs is the singleton current Observation id; evidence_refs is the "
        "complete ordered lineage array, not a subset or reordered set.",
    )
    fields = {}
    for field in ("remaining_uncertainty_refs", "newly_enabled_obligation_ids", "next_subgoal"):
        source = "allowed_next_subgoals" if field == "next_subgoal" else field
        mode = "choose_from" if field == "next_subgoal" else "copy_from"
        fields["/" + field] = {
            "by_disposition": {
                disposition: ref(f"/update_transition_options/{disposition}/{source}", mode)
                for disposition in ("accept", "reject")
            }
        }
    add(
        "admission.update_effect",
        fields,
        "Use the transition branch matching disposition. The two reference arrays must "
        "equal the provided ordered arrays exactly. next_subgoal must be one member of "
        "allowed_next_subgoals (a string, not the whole array).",
    )
    return record(
        "update_public_contract",
        version=VERSION,
        submission_schema_unchanged=True,
        applies_when={"kind": "update", "terminal": False, "pending_observation": "non-null"},
        path_notation="RFC 6901 JSON pointers; source paths start at this public Request",
        equality="existing canonical_json_bytes equality; not raw response string equality",
        rules=rules,
        host_fills_response_fields=False,
        host_commits_during_calibration=False,
        choices_are_callback_owned=True,
    )


def publish_update_contract(request: dict[str, Any]) -> dict[str, Any]:
    """Add only the publication and recompute Request identity, preserving all old fields."""
    require("public_update_contract" not in request, "publication.already_present")
    return record(
        "request",
        **{key: value for key, value in request.items() if key not in {"id", "schema_version"}},
        public_update_contract=public_update_contract(),
    )


def pointer(document: Any, path: str) -> Any:
    require(path.startswith("/"), "publication.pointer")
    for segment in path[1:].split("/"):
        key = segment.replace("~1", "/").replace("~0", "~")
        document = document[int(key)] if isinstance(document, list) else document[key]
    return document


def resolve_rule(spec: dict[str, Any], request: dict[str, Any], disposition: str) -> Any:
    """Reference-client decoding only; admission never trusts or invokes this decoder."""
    if "by_disposition" in spec:
        return resolve_rule(spec["by_disposition"][disposition], request, disposition)
    if "literal" in spec:
        return copy.deepcopy(spec["literal"])
    if "choose_from_literal" in spec:
        require(disposition in spec["choose_from_literal"], "publication.disposition")
        return disposition
    mode, path = next(iter(spec.items()))
    value = copy.deepcopy(pointer(request, path))
    if mode == "wrap_in_list_from":
        return [value]
    if mode == "choose_from":
        require(bool(value), "publication.empty_choice")
        return "submit_final" if "submit_final" in value else value[0]
    require(mode == "copy_from", "publication.expression")
    return value


def reference_update(request: dict[str, Any], disposition: str) -> dict[str, Any]:
    """Fixture receiver reads the published rules, not private pending-state knowledge."""
    publication = request["public_update_contract"]
    require(publication["version"] == VERSION, "publication.version")
    response: dict[str, Any] = {}
    for rule in publication["rules"]:
        for path, spec in rule["fields"].items():
            target = response
            parts = path[1:].split("/")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = resolve_rule(spec, request, disposition)
    return response


def rejection_feedback(
    code: str | None,
    request: dict[str, Any],
    submitted: dict[str, Any] | None,
) -> dict[str, Any]:
    """Finite diagnostics only: no corrected response and no additional model submission."""
    feedback: dict[str, Any] = {"code": code, "admitted": False}
    publication = request.get("public_update_contract")
    if (
        publication is None
        or (submitted is not None and submitted.get("kind") != "update")
        or (submitted is None and request["state"]["pending_observation"] is None)
    ):
        return feedback
    matching = [rule for rule in publication["rules"] if rule["error_code"] == code]
    if not matching:
        return feedback
    rule = matching[0]
    fields = rule["fields"]
    mismatches = []
    if submitted is not None:
        for path, spec in fields.items():
            try:
                selected = spec.get("by_disposition", {}).get(submitted["disposition"], spec)
                value = pointer(submitted, path)
                valid = (
                    value in pointer(request, selected["choose_from"])
                    if "choose_from" in selected
                    else canonical_json_bytes(value)
                    == canonical_json_bytes(resolve_rule(spec, request, submitted["disposition"]))
                )
            except (KeyError, TypeError, ValueError):
                valid = False
            if not valid:
                mismatches.append(path)
    feedback["public_diagnostic"] = {
        "contract_id": publication["id"],
        "version": publication["version"],
        "rule_id": rule["rule_id"],
        "response_field_paths": mismatches or list(fields),
        "public_source_mapping": copy.deepcopy(fields),
        "requirement": rule["requirement"],
        "response_rewritten": False,
    }
    return feedback
