"""Four families of Final-only controls on twelve frozen ready states.

The receiver follows published source paths and projection instructions. Local
control responses are checked by the unchanged strict verifier and original
admission method through a read-only view, never by a constructed Runtime.
They are not model responses and cannot enter an online or supervision cohort.
"""

from __future__ import annotations

import copy
from collections import Counter
from decimal import Decimal, localcontext
from types import SimpleNamespace
from typing import Any

from pydantic import ValidationError

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.final_public_contract import (
    publish_final_contract,
    rejection_feedback,
)
from trusted_synthesis.domains.finance.qa_vnext.protocol import Final, ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime

from ..finance_qa_vnext_model_execution.models import record, require

FAMILIES = (
    "legal_public_result_and_lineage",
    "result_fields_type_quantization_unit",
    "actual_disclosed_reconstructed_citations",
    "current_answer_claim_and_state",
)


def _pointer(value: Any, pointer: str) -> Any:
    require(isinstance(pointer, str) and pointer.startswith("/"), "final_controls.public_pointer")
    current = value
    for component in pointer[1:].split("/"):
        key = component.replace("~1", "/").replace("~0", "~")
        current = current[int(key)] if isinstance(current, list) else current[key]
    return current


def _instructions(request: dict[str, Any]) -> dict[str, Any]:
    publication = request["public_final_contract"]
    fields: dict[str, Any] = {}
    for rule in publication["rules"]:
        for path, instruction in rule["fields"].items():
            require(path not in fields, "final_controls.duplicate_public_field")
            fields[path] = instruction
    require(
        set(fields)
        == {
            "/kind",
            "/state_id",
            "/answer_claim_id",
            "/result",
            "/result/value",
            "/result/unit",
            "/citations",
        },
        "final_controls.complete_published_field_mapping",
    )
    return fields


def public_control_response(request: dict[str, Any]) -> dict[str, Any]:
    """Construct a local control from publication only; no source-answer oracle."""
    instructions = _instructions(request)
    publication = request["public_final_contract"]
    binding = publication["selected_binding"]
    allowed = _pointer(request, instructions["/answer_claim_id"]["choose_id_from"])
    require(
        bool(allowed) and allowed == _pointer(request, binding["allowed_ids_from"]),
        "final_controls.public_answer_choices",
    )
    selected_id = sorted(allowed)[0]
    matches = [
        claim
        for claim in _pointer(request, binding["request_collection"])
        if claim[binding["id_field"]] == selected_id
    ]
    require(len(matches) == 1, "final_controls.selected_current_public_claim")
    selected = matches[0]
    value_instruction = instructions["/result/value"]
    transform = value_instruction["transform"]
    require(
        transform["operation"] == "decimal_quantize"
        and transform["serialization"] == "fixed_six_decimal_string"
        and transform["append_percent_symbol"] is False,
        "final_controls.published_value_transformation",
    )
    with localcontext() as arithmetic:
        arithmetic.prec = _pointer(request, transform["precision_from"])
        arithmetic.rounding = _pointer(request, transform["rounding_from"])
        projected = Decimal(_pointer(selected, value_instruction["from_selected"])).quantize(
            Decimal(_pointer(request, transform["quantum_from"]))
        )
    value = format(projected, "f")
    require(len(value.partition(".")[2]) == 6, "final_controls.published_six_decimal_serialization")
    result = {"value": value, "unit": instructions["/result/unit"]["literal"]}
    require(
        set(result)
        == set(instructions["/result"]["required_fields"])
        == set(instructions["/result"]["allowed_fields"]),
        "final_controls.published_result_boundary",
    )
    citations = instructions["/citations"]
    require(
        citations["unique"] is True and citations["order_significant"] is False,
        "final_controls.public_citation_set",
    )
    return {
        "kind": instructions["/kind"]["literal"],
        "state_id": _pointer(request, instructions["/state_id"]["copy_from"]),
        "answer_claim_id": selected_id,
        "result": result,
        "citations": sorted(set(_pointer(selected, citations["set_from_selected"]))),
    }


class _StrictVerifierView:
    """A counted handle to the actual inherited strict verifier, not an executor."""

    def __init__(self, adapter: Any):
        self.adapter = adapter
        self.calls = 0

    def verify_final(
        self, submitted: dict[str, Any], claims: list[dict[str, Any]]
    ) -> dict[str, Any]:
        self.calls += 1
        return self.adapter.verify_final(submitted, claims)


def readonly_final_admission(
    adapter: Any, request: dict[str, Any], response: dict[str, Any]
) -> dict[str, Any]:
    """Call the original Final gate on a plain view; no Runtime object is created."""
    require(response.get("kind") == "final", "final_controls.final_only_no_action_or_update")
    local_request, submitted = copy.deepcopy(request), copy.deepcopy(response)
    verifier = _StrictVerifierView(adapter)
    view: Any = SimpleNamespace(
        adapter=verifier,
        terminal=local_request["state"]["terminal"],
        pending=copy.deepcopy(local_request["state"]["pending_observation"]),
        claims=copy.deepcopy(local_request["state"]["accepted_claims"]),
    )
    before = canonical_json_bytes(
        {
            "request": local_request,
            "response": submitted,
            "claims": view.claims,
            "pending": view.pending,
            "terminal": view.terminal,
        }
    )
    validation, error_code = None, None
    try:
        parsed = Final.model_validate(submitted).model_dump(mode="json")
        decision = PublicQARuntime._admit(view, parsed, local_request)
        validation = decision["validation"]
        admitted = True
    except ValidationError:
        admitted, error_code = False, "submission.schema"
    except ProtocolError as error:
        admitted, error_code = False, str(error)
    after = canonical_json_bytes(
        {
            "request": local_request,
            "response": submitted,
            "claims": view.claims,
            "pending": view.pending,
            "terminal": view.terminal,
        }
    )
    require(before == after, "final_controls.readonly_admission_mutated_input")
    return {
        "admitted": admitted,
        "error_code": error_code,
        "qa_validation": validation,
        "strict_verifier_calls": verifier.calls,
        "runtime_constructed": False,
        "runtime_or_operation_executed": False,
        "request_response_and_state_unchanged": True,
    }


def _variants(ready: dict[str, Any], request: dict[str, Any], positive: dict[str, Any]):
    selected = next(
        claim
        for claim in request["state"]["accepted_claims"]
        if claim["id"] == positive["answer_claim_id"]
    )
    output = selected["proposition"]["output"]
    values = []

    def add(name, family, response, accepted, error_code=None, categories=()):
        values.append(
            {
                "case": name,
                "family": family,
                "response": response,
                "expected_admitted": accepted,
                "expected_error_code": error_code,
                "expected_feedback_categories": list(categories),
            }
        )

    add("legal_exact_projection", FAMILIES[0], copy.deepcopy(positive), True)
    reversed_citations = copy.deepcopy(positive)
    reversed_citations["citations"].reverse()
    add("legal_citation_set_order", FAMILIES[0], reversed_citations, True)
    extra = copy.deepcopy(positive)
    extra["result"].update({key: output[key] for key in ("metric", "period", "subject")})
    add(
        "result_copied_metadata",
        FAMILIES[1],
        extra,
        False,
        "admission.final_qa",
        ("result_fields",),
    )
    missing_unit = copy.deepcopy(positive)
    del missing_unit["result"]["unit"]
    add(
        "result_missing_unit",
        FAMILIES[1],
        missing_unit,
        False,
        "admission.final_qa",
        ("result_fields",),
    )
    number = copy.deepcopy(positive)
    number["result"]["value"] = float(positive["result"]["value"])
    add(
        "json_number_not_string",
        FAMILIES[1],
        number,
        False,
        "admission.final_qa",
        ("value_projection",),
    )
    unquantized = copy.deepcopy(positive)
    unquantized["result"]["value"] = _pointer(
        selected, _instructions(request)["/result/value"]["from_selected"]
    )
    require(
        unquantized["result"]["value"] != positive["result"]["value"],
        "final_controls.nonquantized_negative_is_distinct",
    )
    add(
        "unquantized_claim_value",
        FAMILIES[1],
        unquantized,
        False,
        "admission.final_qa",
        ("value_projection",),
    )
    unit = copy.deepcopy(positive)
    unit["result"]["unit"] = "%"
    add("wrong_unit_form", FAMILIES[1], unit, False, "admission.final_qa", ("unit",))
    evidence = request["context"]["evidence"]
    disclosed = {evidence[key]["id"] for key in ("target_component", "disclosed_total")}
    reconstructed = {
        evidence[key]["id"]
        for key in ("target_component", "other_component", "composition_relation")
    }
    actual = set(positive["citations"])
    require(actual in (disclosed, reconstructed), "final_controls.actual_public_lineage_shape")
    swapped = copy.deepcopy(positive)
    swapped["citations"] = sorted(reconstructed if actual == disclosed else disclosed)
    add(
        "disclosed_reconstructed_support_replacement",
        FAMILIES[2],
        swapped,
        False,
        "admission.final_qa",
        ("actual_lineage",),
    )
    missing = copy.deepcopy(positive)
    missing["citations"] = positive["citations"][1:]
    add(
        "missing_actual_evidence",
        FAMILIES[2],
        missing,
        False,
        "admission.final_qa",
        ("actual_lineage",),
    )
    extra_citation = copy.deepcopy(positive)
    unused = sorted({item["id"] for item in evidence.values()} - actual)
    require(bool(unused), "final_controls.visible_but_unused_evidence_exists")
    extra_citation["citations"].append(unused[0])
    add(
        "extra_visible_unused_evidence",
        FAMILIES[2],
        extra_citation,
        False,
        "admission.final_qa",
        ("actual_lineage",),
    )
    duplicate = copy.deepcopy(positive)
    duplicate["citations"].append(positive["citations"][0])
    add(
        "duplicate_actual_citation",
        FAMILIES[2],
        duplicate,
        False,
        "admission.final_qa",
        ("actual_lineage",),
    )
    wrong_claim = copy.deepcopy(positive)
    other = [
        claim["id"]
        for claim in request["state"]["accepted_claims"]
        if claim["id"] not in request["final_claim_ids"]
    ]
    require(bool(other), "final_controls.accepted_intermediate_claim_exists")
    wrong_claim["answer_claim_id"] = other[0]
    add(
        "accepted_intermediate_not_answer",
        FAMILIES[3],
        wrong_claim,
        False,
        "admission.final_accepted_claim",
        ("accepted_answer",),
    )
    stale = copy.deepcopy(positive)
    stale["state_id"] = ready["before_accept_state_id"]
    require(stale["state_id"] != request["state"]["id"], "final_controls.stale_state_is_distinct")
    add(
        "previous_state_not_current",
        FAMILIES[3],
        stale,
        False,
        "admission.current_state",
        ("current_state",),
    )
    return values


def _snapshot(inputs):
    return canonical_json_bytes(
        {
            "condition": inputs["old_condition"],
            "registrations": inputs["old_registrations"],
            "qualifications": inputs["old_qualifications"],
            "ready_states": inputs["ready_states"],
            "source_checks": inputs["source_checks"],
            "source_report": inputs["source_report"],
            "evaluation_policy": inputs["evaluation_policy"],
            "adapter_semantics": {
                key: {
                    "context": adapter.context,
                    "registry": adapter.registry.manifest(),
                    "evidence": adapter.evidence,
                    "semantic_contract": adapter.semantic_contract,
                }
                for key, adapter in inputs["adapters"].items()
            },
        }
    )


def run_controls(inputs: dict[str, Any]) -> dict[str, Any]:
    """Run the four requested local control families, never an online continuation."""
    require(len(inputs["ready_states"]) == 12, "final_controls.twelve_frozen_ready_states")
    before = _snapshot(inputs)
    rows = []
    publications = set()
    for ready in inputs["ready_states"]:
        old_request = ready["request"]
        require(
            "public_final_contract" not in old_request,
            "final_controls.historical_request_unchanged",
        )
        published = publish_final_contract(old_request)
        publications.add(published["public_final_contract"]["id"])
        require(
            published["state"] == old_request["state"]
            and published["context"] == old_request["context"]
            and published["final_claim_ids"] == old_request["final_claim_ids"],
            "final_controls.publication_preserves_state_context_choices",
        )
        positive = public_control_response(published)
        adapter = inputs["adapters"][ready["task_group"]]
        for variant in _variants(ready, published, positive):
            response = variant["response"]
            original = readonly_final_admission(adapter, old_request, response)
            current = readonly_final_admission(adapter, published, response)
            require(
                original == current
                and current["admitted"] is variant["expected_admitted"]
                and current["error_code"] == variant["expected_error_code"],
                "final_controls.original_acceptance_boundary_changed",
            )
            feedback = None
            if not current["admitted"]:
                response_before = canonical_json_bytes(response)
                feedback = rejection_feedback(current["error_code"], published, response)
                diagnostic = feedback["public_diagnostic"]
                require(
                    feedback["code"] == current["error_code"]
                    and {item["category"] for item in diagnostic["violations"]}
                    == set(variant["expected_feedback_categories"])
                    and diagnostic["response_rewritten"] is False
                    and diagnostic["replacement_answer_supplied"] is False
                    and diagnostic["financial_operations_executed"] is False
                    and diagnostic["source_answer_verifier_called"] is False
                    and response_before == canonical_json_bytes(response),
                    "final_controls.diagnostic_not_repair_or_gate_change",
                )
                if variant["family"] == FAMILIES[3]:
                    require(
                        current["strict_verifier_calls"] == 0,
                        "final_controls.early_gate_does_not_run_final_qa",
                    )
            rows.append(
                record(
                    "final_publication_control",
                    label=ready["label"],
                    task_group=ready["task_group"],
                    profile=ready["profile"],
                    case=variant["case"],
                    family=variant["family"],
                    ready_state_id=ready["id"],
                    old_qualification_id=ready["old_qualification_id"],
                    old_session_id=ready["old_session_id"],
                    source_event_sequence=ready["source_event_sequence"],
                    source_event_sha256=ready["source_event_sha256"],
                    source_state_id=ready["source_state_id"],
                    source_state_sha256=ready["source_state_sha256"],
                    prefix_support=ready["prefix_support"],
                    publication_id=published["public_final_contract"]["id"],
                    old_request_id=old_request["id"],
                    control_request_id=published["id"],
                    control_response=response,
                    expected_admitted=variant["expected_admitted"],
                    original_admission=original,
                    published_admission=current,
                    feedback=feedback,
                    acceptance_unchanged=True,
                    expected_outcome_observed=True,
                    control_evidence=True,
                    generated_model_sample=False,
                    old_session_appended=False,
                    positive_training_candidate=False,
                )
            )
    after = _snapshot(inputs)
    require(before == after and len(publications) == 1, "final_controls.original_inputs_changed")
    families = Counter(row["family"] for row in rows)
    require(
        set(families) == set(FAMILIES) and len(rows) == 156, "final_controls.four_families_complete"
    )
    return record(
        "final_publication_controls",
        passed=True,
        all_expected_outcomes=True,
        read_only=True,
        ready_state_ids=[ready["id"] for ready in inputs["ready_states"]],
        control_count=len(rows),
        family_count=4,
        family_counts=dict(families),
        rows=rows,
        public_final_contract_id=next(iter(publications)),
        source_checks_id=inputs["source_checks"]["id"],
        ready_state_count=12,
        original_failed_prefix_support_counts=inputs["source_checks"][
            "actual_failed_prefix_support_counts"
        ],
        controls_by_task=dict(Counter(row["task_group"] for row in rows)),
        positive_control_count=sum(row["expected_admitted"] for row in rows),
        negative_control_count=sum(not row["expected_admitted"] for row in rows),
        readonly_admission_evaluations=2 * len(rows),
        local_original_strict_verifier_calls=sum(
            row[side]["strict_verifier_calls"]
            for row in rows
            for side in ("original_admission", "published_admission")
        ),
        input_snapshot_hash=strict_canonical_hash(read_json_snapshot(before)),
        original_inputs_and_states_unchanged=True,
        provenance_unchanged=True,
        old_outcomes_unchanged=True,
        old_qualified_count_before=0,
        old_qualified_count_after=0,
        old_registered_denominator=12,
        positive_control_responses_are_online_examples=False,
        public_receiver_uses_only_published_paths_and_transform=True,
        independent_source_oracle_used_to_construct_controls=False,
        runtime_constructions=0,
        runtime_executions=0,
        operation_executions=0,
        qualifier_calls=0,
        quotient_calls=0,
        archive_scans=0,
        provider_calls=0,
        tokenizer_calls=0,
        old_sessions_resumed=0,
        old_finals_appended=0,
        new_model_samples=0,
        training_rows_created=0,
    )


def read_json_snapshot(raw: bytes) -> Any:
    """Decode an in-memory snapshot only, not another artifact or source file."""
    import json

    return json.loads(raw)
