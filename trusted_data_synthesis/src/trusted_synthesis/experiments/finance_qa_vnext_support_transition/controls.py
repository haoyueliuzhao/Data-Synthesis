"""Four direct counterexample families plus preservation of prior supported semantics.

Only already loaded objects and isolated copies are used. Counterfactual probes
are not new model trajectories, support proofs or formal Assignments. Unresolved
projections remain unresolved; an inapplicable probe is not a semantic proof.
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Callable
from functools import partial as bind_call
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError

from ..finance_qa_vnext_model_execution.models import record, sha
from ..finance_qa_vnext_panel_quotient import projection as prior
from . import projection
from .comparison import compare_all, compare_projections
from .distribution import build_distribution
from .source import validate_inputs


def _reseal(value: dict[str, Any], kind: str, **changes: Any) -> dict[str, Any]:
    fields = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    return record(kind, **{**fields, **changes})


def _row(name: str, family: str, observed: dict[str, Any], passed: bool):
    return record(
        "support_transition_control",
        name=name,
        family=family,
        observed=observed,
        passed=passed,
        control_evidence=True,
        counterfactual_is_not_qualified_model_trajectory=True,
        formal_counterfactual_assignment_written=False,
    )


def _reject(name: str, family: str, call: Callable[[], Any], **description: Any):
    try:
        result = call()
    except ProtocolError as error:
        return _row(
            name, family, {**description, "outcome": "rejected", "error_code": str(error)}, True
        )
    undetermined = isinstance(result, dict) and result.get("status") == "undetermined"
    return _row(
        name,
        family,
        {**description, "outcome": "undetermined" if undetermined else "unexpected_acceptance"},
        undetermined,
    )


def _inapplicable(name: str, family: str, reason: str, **description: Any):
    return _row(
        name,
        family,
        {
            **description,
            "outcome": "not_applicable_projection_undetermined",
            "reason": reason,
            "test_executed": False,
            "comparison": None,
            "semantic_proof_established": None,
            "unresolved_projection_promoted": False,
        },
        True,
    )


def run_controls(
    inputs: dict[str, Any],
    projections: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    measurement_condition: dict[str, Any],
    rule: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    entries = inputs["entries"]
    generation = inputs["generation_condition"]
    by_entry = {entry["label"]: entry for entry in entries}
    by_projection = {item["label"]: item for item in projections}
    tracked = {
        key: value for key, value in inputs.items() if key not in {"root", "source_directory"}
    }
    before = canonical_json_bytes(
        {
            "inputs": tracked,
            "projections": projections,
            "pairs": pairs,
            "measurement_condition": measurement_condition,
            "rule": rule,
            "contract": contract,
        }
    )
    rows = []

    # Compatibility is exact content preservation, not only the old disposition name.
    old_e04, new_e04 = by_entry["E04"]["old_projection"], by_projection["E04"]
    same_e04 = canonical_json_bytes(old_e04["behavior_projection"]) == canonical_json_bytes(
        new_e04["behavior_projection"]
    )
    same_e04_ledger = canonical_json_bytes(
        old_e04["interpretation_ledger"]
    ) == canonical_json_bytes(new_e04["interpretation_ledger"])
    rows.append(
        _row(
            "E04_supported_behavior_and_eleven_annotations_unchanged",
            "prior_semantics_compatibility",
            {
                "old_projection_id": old_e04["id"],
                "new_projection_id": new_e04["id"],
                "complete_behavior_byte_equal": same_e04,
                "complete_ledger_byte_equal": same_e04_ledger,
                "annotation_count": len(old_e04["interpretation_ledger"]),
            },
            new_e04["supported"]
            and same_e04
            and same_e04_ledger
            and len(old_e04["interpretation_ledger"]) == 11,
        )
    )
    preserved = []
    for entry in entries:
        new_rows = {
            row["sequence"]: row for row in by_projection[entry["label"]]["interpretation_ledger"]
        }
        for old in entry["old_projection"]["interpretation_ledger"]:
            if old["disposition"] == "undetermined":
                continue
            same = old["sequence"] in new_rows and canonical_json_bytes(
                old
            ) == canonical_json_bytes(new_rows[old["sequence"]])
            preserved.append(
                {
                    "label": entry["label"],
                    "sequence": old["sequence"],
                    "old_annotation_sha256": sha(canonical_json_bytes(old)),
                    "byte_equal": same,
                }
            )
    rows.append(
        _row(
            "all_fourteen_previously_resolved_annotations_unchanged",
            "prior_semantics_compatibility",
            {"annotation_count": len(preserved), "rows": preserved},
            len(preserved) == 14 and all(row["byte_equal"] for row in preserved),
        )
    )

    # 1. The rejected D proposal is not an executed D route, and sum is not no-effect.
    for label in ("N03", "E02"):
        for mutation in ("execution_record", "admitted_receipt"):
            changed = copy.deepcopy(by_entry[label])
            if mutation == "execution_record":
                changed["session"]["events"][0]["execution"] = {"isolated_injected_execution": True}
            else:
                changed["session"]["events"][0]["receipt"]["admitted"] = True
            rows.append(
                _reject(
                    label + "_proposal_not_executed_" + mutation,
                    "proposal_and_effect_boundary",
                    bind_call(projection.support_transition, changed, 0),
                    label=label,
                    mutation=mutation,
                )
            )
        original_events = by_entry[label]["session"]["events"]
        ratio_sequence = by_entry[label]["old_support"]["trace"]["ratio"]["action_sequence"]
        rows.append(
            _reject(
                label + "_real_sum_and_accept_are_not_no_effect",
                "proposal_and_effect_boundary",
                bind_call(prior.no_effect_interval, original_events, 0, ratio_sequence),
                label=label,
                attempted_interval_stop=ratio_sequence,
            )
        )

    # 2. Actual reconstruction must exist, be accepted, and match the consumed reference.
    for label in ("N03", "E02"):
        for mutation in (
            "remove_sum_node",
            "remove_accepted_total_from_ratio_state",
            "forge_denominator_reference",
        ):
            changed = copy.deepcopy(by_entry[label])
            trace = changed["old_support"]["trace"]
            if mutation == "remove_sum_node":
                changed["graph"]["nodes"] = [
                    node
                    for node in changed["graph"]["nodes"]
                    if node["node_id"] != trace["total"]["node_id"]
                ]
            else:
                ratio_event = changed["session"]["events"][trace["ratio"]["action_sequence"]]
                if mutation == "remove_accepted_total_from_ratio_state":
                    ratio_event["request"]["state"]["accepted_claims"] = [
                        claim
                        for claim in ratio_event["request"]["state"]["accepted_claims"]
                        if claim["id"] != trace["total"]["accepted_claim_id"]
                    ]
                else:
                    denominator = next(
                        ref
                        for ref in ratio_event["parsed"]["inputs"]
                        if ref["role"] == "denominator"
                    )
                    denominator["ref_id"] = "isolated_unaccepted_different_total_claim"
            rows.append(
                _reject(
                    label + "_dependency_rejects_" + mutation,
                    "actual_reconstruction_dependency",
                    bind_call(projection.support_transition, changed, 0),
                    label=label,
                    mutation=mutation,
                )
            )

    # 3. The original missing/replaced lineage still cannot use the old redundancy reduction.
    original_e02 = by_entry["E02"]
    final_events = original_e02["session"]["events"]
    rows.append(
        _reject(
            "E02_missing_other_and_extra_total_is_not_legacy_redundancy",
            "grounding_assertion_boundary",
            lambda: prior.final_alignment(final_events[8], final_events[15]),
            rejected_sequence=8,
            admitted_final_sequence=15,
        )
    )
    segments = [
        detail
        for detail in by_projection["E02"].get("interpretation_details", [])
        if detail.get("schema_version")
        == "qa_vnext_model_execution_support_transition_grounding_segment.v1"
    ]
    if len(segments) == 1:
        segment = segments[0]
        assertion_rows = segment["original_assertions"]
        context = final_events[8]["request"]["context"]
        other_id, total_id = context["evidence"]["other"]["id"], context["evidence"]["total"]["id"]
        checks = []
        for assertion in assertion_rows:
            event = final_events[assertion["sequence"]]
            declared = set(event["parsed"]["citations"])
            lineage = set(assertion["actual_lineage"])
            checks.append(
                {
                    "sequence": assertion["sequence"],
                    "display_turn": assertion["sequence"] + 1,
                    "raw_citations_preserved": assertion["submitted_citations"]
                    == event["parsed"]["citations"],
                    "raw_result_preserved": assertion["original_result"]
                    == event["parsed"]["result"],
                    "missing_exact": assertion["missing"] == sorted(lineage - declared),
                    "extra_exact": assertion["extra"] == sorted(declared - lineage),
                    "missing": assertion["missing"],
                    "extra": assertion["extra"],
                    "normalization": assertion["normalization"],
                }
            )
        incorrect = [row for row in checks if row["missing"]]
        behavior = by_projection["E02"]["behavior_projection"]
        nodes_equal = (
            canonical_json_bytes(behavior["nodes"])
            == canonical_json_bytes(original_e02["graph"]["nodes"])
            if behavior
            else None
        )
        relation = segment["behavioral_relation"]
        rows.append(
            _row(
                "E02_entire_T9_T16_assertions_retained_without_new_uses_edges",
                "grounding_assertion_boundary",
                {
                    "segment_id": segment["id"],
                    "rows": checks,
                    "source_sequences": segment["all_source_sequences"],
                    "intermediate_legacy_alignment_sequences": [9, 12, 14],
                    "actual_nodes_byte_unchanged": nodes_equal,
                    "assertions_are_not_actual_input_dependencies": relation[
                        "assertions_are_not_actual_input_dependencies"
                    ],
                },
                segment["all_source_sequences"] == list(range(8, 16))
                and len(checks) == 8
                and [row["sequence"] for row in checks] == list(range(8, 16))
                and [row["sequence"] for row in incorrect] == [8, 10, 11, 13]
                and all(
                    other_id in row["missing"] and total_id in row["extra"] for row in incorrect
                )
                and all(
                    row["raw_citations_preserved"]
                    and row["raw_result_preserved"]
                    and row["missing_exact"]
                    and row["extra_exact"]
                    for row in checks
                )
                and relation["assertions_are_not_actual_input_dependencies"] is True
                and (not by_projection["E02"]["supported"] or nodes_equal is True),
            )
        )
    elif (
        by_projection["E02"]["status"] == "undetermined"
        and by_projection["E02"]["supported"] is False
        and by_projection["E02"]["behavior_projection"] is None
        and len(segments) == 0
    ):
        rows.append(
            _inapplicable(
                "E02_entire_T9_T16_assertions_retained_without_new_uses_edges",
                "grounding_assertion_boundary",
                "the new grounding segment remains outside the supported projection domain",
                source_projection_id=by_projection["E02"]["id"],
                segment_count=len(segments),
            )
        )
    else:
        rows.append(
            _row(
                "E02_entire_T9_T16_assertions_retained_without_new_uses_edges",
                "grounding_assertion_boundary",
                {
                    "outcome": "missing_or_duplicate_required_grounding_segment",
                    "source_projection_id": by_projection["E02"]["id"],
                    "source_projection_status": by_projection["E02"]["status"],
                    "segment_count": len(segments),
                },
                False,
            )
        )
    changed = copy.deepcopy(original_e02)
    changed["session"]["events"][8]["parsed"]["result"]["value"] = "93.5084581"
    rows.append(
        _reject(
            "E02_nearby_unregistered_value_is_not_same_existing_result",
            "grounding_assertion_boundary",
            lambda: projection.grounding_assertions(changed),
            mutation="value_not_raw_claim_or_public_quantization",
        )
    )

    # 4. Source invariants reject dropped valid mass, promoted failure and retagged generation.
    changed_inputs = copy.deepcopy(inputs)
    changed_inputs["entries"] = [
        entry for entry in changed_inputs["entries"] if entry["label"] != "E02"
    ]
    changed_inputs["registrations"] = [
        row for row in changed_inputs["registrations"] if row["label"] != "E02"
    ]
    rows.append(
        _reject(
            "E02_unmapped_valid_observation_cannot_be_removed",
            "population_and_profile_boundary",
            lambda: validate_inputs(changed_inputs),
            mutation="drop_valid_entry_and_registration",
        )
    )
    changed_inputs = copy.deepcopy(inputs)
    failed = next(entry for entry in changed_inputs["entries"] if entry["label"] == "N01")
    failed["qualification"] = _reseal(
        failed["qualification"],
        "qualification",
        status="success",
        qualified=True,
        end_to_end_success=True,
    )
    rows.append(
        _reject(
            "N01_failed_outcome_cannot_be_rehashed_as_success",
            "population_and_profile_boundary",
            lambda: validate_inputs(changed_inputs),
            mutation="promote_failed_qualification",
        )
    )
    changed_inputs = copy.deepcopy(inputs)
    changed_inputs["generation_condition"] = _reseal(
        generation,
        "support_exploration_condition",
        rule_id=rule["id"],
        new_post_outcome_quotient_rules_allowed=True,
    )
    rows.append(
        _reject(
            "original_generation_rule_cannot_be_replaced_by_measurement_rule",
            "population_and_profile_boundary",
            lambda: validate_inputs(changed_inputs),
            mutation="rehash_original_generation_with_new_rule",
        )
    )
    n03, e02 = by_projection["N03"], by_projection["E02"]
    if n03["supported"] and e02["supported"]:
        clone = _reseal(
            e02,
            "panel_quotient_projection",
            behavior_projection=copy.deepcopy(n03["behavior_projection"]),
            isolated_counterfactual=True,
            copied_behavior_from_projection_id=n03["id"],
            counterfactual_is_not_a_qualified_trajectory=True,
        )
        compared = compare_projections(n03, clone)
        rows.append(
            _row(
                "profile_names_alone_do_not_split_equal_retained_behavior",
                "population_and_profile_boundary",
                {
                    "N_source_projection_id": n03["id"],
                    "E_metadata_source_projection_id": e02["id"],
                    "isolated_counterfactual_projection_id": clone["id"],
                    "comparison": compared,
                    "actual_E02_behavior_was_not_replaced": True,
                    "formal_counterfactual_assignment_written": False,
                },
                n03["profile"] == "N"
                and clone["profile"] == "E"
                and n03["profile_id"] != clone["profile_id"]
                and n03["model_configuration_id"] != clone["model_configuration_id"]
                and compared["relation"] == "equivalent"
                and compared["proof_verified"] is True,
            )
        )
    else:
        rows.append(
            _inapplicable(
                "profile_names_alone_do_not_split_equal_retained_behavior",
                "population_and_profile_boundary",
                "N03 or E02 lacks a supported complete behavior projection; "
                "no profile-only class is fabricated",
                N03_status=n03["status"],
                E02_status=e02["status"],
            )
        )
    partial_projections = copy.deepcopy(projections)
    index = next(i for i, value in enumerate(partial_projections) if value["label"] == "E02")
    partial_projections[index] = _reseal(
        partial_projections[index],
        "panel_quotient_projection",
        status="undetermined",
        supported=False,
        behavior_projection=None,
        isolated_counterfactual=True,
        errors=[{"reason": "isolated_control_unresolved_E02"}],
    )
    partial_pairs = compare_all(
        entries, partial_projections, measurement_condition, generation, rule, contract
    )
    partial_result = build_distribution(
        entries,
        partial_projections,
        partial_pairs,
        measurement_condition,
        generation,
        rule,
        contract,
    )
    reference = next(
        pair for pair in pairs if pair["left_label"] == "N03" and pair["right_label"] == "E04"
    )
    target_expected = reference["execution_support_contrast"]["established"]
    rows.append(
        _row(
            "unresolved_E02_keeps_mass_and_does_not_erase_independent_DR_witness",
            "population_and_profile_boundary",
            {
                "registered_denominator": partial_result["registered_denominator"],
                "qualified_count": partial_result["qualified_count"],
                "success_fraction": partial_result["success_fraction"],
                "conditional_distribution": partial_result["conditional_distribution"],
                "complete_class_count": partial_result["complete_class_count"],
                "unmapped_qualified_count": partial_result["unmapped_qualified_count"],
                "W_support": partial_result["W_support"],
                "reference_DR_witness_established": target_expected,
                "counterfactual_assignments_written": 0,
            },
            partial_result["registered_denominator"] == 8
            and partial_result["qualified_count"] == 3
            and partial_result["success_fraction"] == {"numerator": 3, "denominator": 8}
            and partial_result["conditional_distribution"] is None
            and partial_result["complete_class_count"] is None
            and partial_result["unmapped_qualified_count"] >= 1
            and partial_result["W_support"] is target_expected,
        )
    )
    unchanged = before == canonical_json_bytes(
        {
            "inputs": tracked,
            "projections": projections,
            "pairs": pairs,
            "measurement_condition": measurement_condition,
            "rule": rule,
            "contract": contract,
        }
    )
    return record(
        "support_transition_controls",
        measurement_condition_id=measurement_condition["id"],
        generation_condition_id=generation["id"],
        rule_id=rule["id"],
        comparison_contract_id=contract["id"],
        rows=rows,
        control_count=len(rows),
        new_risk_family_count=4,
        family_counts=dict(Counter(row["family"] for row in rows)),
        executed_control_count=sum(row["observed"].get("test_executed", True) for row in rows),
        not_applicable_control_count=sum(
            row["observed"].get("test_executed") is False for row in rows
        ),
        all_expected_outcomes=unchanged and all(row["passed"] for row in rows),
        original_inputs_and_sidecars_unmodified=unchanged,
        original_input_sidecar_sha256=sha(before),
        controls_run_in_same_measurement_stage=True,
        independent_repeated_audit_stage=False,
        counterfactual_valid_assignments_written=0,
        additional_model_trajectories=0,
        provider_calls=0,
        historical_input_loads=0,
        runtime_executions=0,
        operation_executions=0,
        qualification_replays=0,
        old_actual_support_reclassifications=0,
        tokenizations=0,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
    )
