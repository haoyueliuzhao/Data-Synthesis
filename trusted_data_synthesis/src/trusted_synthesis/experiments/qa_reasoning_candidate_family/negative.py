"""Bounded direct controls against isolated, actually persisted candidate artifacts.

No controller or executor is imported.  Each control starts from the same fixed
F1/B execution, after the unmodified files independently qualify.  Mutation
records and candidate declarations receive their own valid content identities;
downstream commitments are never globally rewritten to fabricate an execution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.task.program import InputRefKind, ProgramInputRef, make_program
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter

from .models import CandidateRoute
from .validation import validate_candidate


def _rehash_record(value: dict[str, Any]) -> bytes:
    kind = value["schema_version"].removeprefix("typed_candidate_").removesuffix(".v1")
    value["id"] = strict_canonical_hash(
        {key: item for key, item in value.items() if key != "id"},
        prefix=f"typed_candidate_{kind}:",
    )
    return canonical_json_bytes(value)


def _candidate_program(
    candidate: Mapping[str, Any], node_id: str, input_refs: tuple[ProgramInputRef, ...]
) -> dict[str, Any]:
    value = deepcopy(dict(candidate))
    program = value["program"]
    dependencies = tuple(
        dict.fromkeys(ref.ref_id for ref in input_refs if ref.kind == InputRefKind.OPERATION)
    )
    nodes = tuple(
        node.model_copy(update={"input_refs": input_refs, "dependencies": dependencies})
        if node.node_id == node_id
        else node
        for node in program.nodes
    )
    value["program"] = make_program(nodes, program.output_node_id)
    value["program_json"] = value["program"].model_dump(mode="json")
    value["candidate_id"] = strict_canonical_hash(
        {key: item for key, item in value.items() if key != "candidate_id"},
        prefix="qa_reasoning_candidate_route:",
    )
    # Type/model rejection is not counted as an independent semantic rejection.
    CandidateRoute.model_validate(value)
    return value


def _runtime_files(writer: Any, result: Mapping[str, Any]) -> dict[str, bytes]:
    prefix = result["runtime_prefix"]
    paths = {
        result["final_path"],
        result["events_path"],
        *(f"{prefix}/state_{index:02d}.json" for index in range(len(result["schedule"]) + 1)),
        *(path for step in result["step_paths"] for path in step.values()),
    }
    return {path: writer.read_bytes(path) for path in sorted(paths)}


def _binding(files: Mapping[str, bytes]) -> str:
    return strict_canonical_hash(
        [
            {"path": path, "sha256": hashlib.sha256(data).hexdigest(), "byte_count": len(data)}
            for path, data in sorted(files.items())
        ],
        prefix="typed_candidate_negative_source:",
    )


def _proposal_for_node(result: Mapping[str, Any], node_id: str) -> str:
    return result["step_paths"][tuple(result["schedule"]).index(node_id)]["proposal"]


def _mutate(
    name: str,
    files: dict[str, bytes],
    candidate: dict[str, Any],
    result: dict[str, Any],
    foreign_evidence_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Mutate one source declaration or runtime object, not the whole chain."""
    details: dict[str, Any] = {"mutated_runtime_paths": [], "globally_rechained": False}

    def edit(path: str, change: Any) -> None:
        value = json.loads(files[path])
        original_id = value["id"]
        change(value)
        files[path] = _rehash_record(value)
        details["mutated_runtime_paths"].append(path)
        details["mutated_object_identity"] = value["id"]
        details["mutated_object_identity_changed"] = original_id != value["id"]
        details["mutated_object_identity_valid"] = True

    if name in {"reversed_growth_periods", "reversed_signed_operand_roles"}:
        operator = "growth" if name == "reversed_growth_periods" else "signed_percentage_point_gap"
        node = next(item for item in candidate["program"].nodes if item.operator_id == operator)
        before = candidate["candidate_id"]
        candidate = _candidate_program(candidate, node.node_id, tuple(reversed(node.input_refs)))

        def reverse_operands(value: dict[str, Any]) -> None:
            role_names = [operand["operand_role"] for operand in value["operands"]]
            value["operands"] = list(reversed(value["operands"]))
            for operand, role_name in zip(value["operands"], role_names, strict=True):
                operand["operand_role"] = role_name

        edit(_proposal_for_node(result, node.node_id), reverse_operands)
        details.update(
            {
                "source_program_mutated": True,
                "candidate_identity_changed": before != candidate["candidate_id"],
                "candidate_schema_and_content_identity_valid": True,
                "program_content_identity_valid": True,
                "mutated_node_id": node.node_id,
                "ordered_operand_roles_preserved_by_position": True,
                "final_answer_bytes_unchanged": True,
            }
        )
        if name == "reversed_signed_operand_roles":
            details["same_absolute_answer_does_not_validate_reversed_signed_roles"] = True
    elif name in {"future_evidence", "cross_task_evidence"}:
        node = next(
            item
            for item in candidate["program"].nodes
            if any(ref.kind == InputRefKind.EVIDENCE for ref in item.input_refs)
        )
        position = next(
            index for index, ref in enumerate(node.input_refs) if ref.kind == InputRefKind.EVIDENCE
        )
        replacement = (
            foreign_evidence_id
            if name == "cross_task_evidence"
            else ("evidence:unavailable_future_evidence_negative_control")
        )
        refs = list(node.input_refs)
        refs[position] = refs[position].model_copy(update={"ref_id": replacement})
        candidate = _candidate_program(candidate, node.node_id, tuple(refs))

        def replace_evidence(value: dict[str, Any]) -> None:
            value["operands"][position]["ref_id"] = replacement

        edit(_proposal_for_node(result, node.node_id), replace_evidence)
        details.update(
            {
                "source_program_mutated": True,
                "candidate_schema_and_content_identity_valid": True,
                "program_content_identity_valid": True,
                "injected_evidence_ref": replacement,
                "reference_exists_in_other_frozen_task": name == "cross_task_evidence",
                "future_reference_is_unavailable_sentinel": name == "future_evidence",
            }
        )
    elif name == "unverified_claim":
        edit(
            result["step_paths"][0]["update"],
            lambda value: value["accepted_claim"].update(status="tentative"),
        )
        details["unchanged_next_state_still_claims_success"] = True
    elif name == "missing_actual_observation":
        path = result["step_paths"][0]["observation"]
        del files[path]
        details.update(
            {
                "mutated_runtime_paths": [path],
                "actual_file_removed_from_isolated_copy": True,
                "successful_execution_and_update_files_preserved": True,
            }
        )
    elif name == "comparison_only_final":
        edit(
            result["final_path"],
            lambda value: value["answer"].update(
                result={"relation": "revenue_growth_greater_than_income_growth"}
            ),
        )
        details["frozen_citations_preserved"] = True
    elif name == "caller_qualified_true":
        result["qualified"] = True
        details["mutated_result_fields"] = ["qualified"]
    elif name == "fabricated_model_ownership":
        edit(
            result["step_paths"][0]["proposal"],
            lambda value: value.update(field_origin="model_proposed"),
        )
    elif name == "route_label_only":
        result["display_label"] = "a-new-name-for-the-identical-persisted-route"
        details["mutated_result_fields"] = ["display_label"]
        details["runtime_artifact_bytes_unchanged"] = True
    else:
        raise ValueError(f"unknown negative control: {name}")
    return candidate, result, details


def run_negative_controls(
    *,
    writer: Any,
    fixtures: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Run nine invalid controls and one label-only acceptance, using no executions."""
    fixture = next(item for item in fixtures if item["fixture_id"] == "F1")
    candidate = next(
        item for item in candidates if item["fixture_id"] == "F1" and item["group"] == "B"
    )
    result = next(item for item in results if item["candidate_id"] == candidate["candidate_id"])
    baseline = validate_candidate(
        writer=writer, fixture=fixture, candidate=candidate, result=result
    )
    audit: dict[str, Any] = {
        "schema_version": "typed_candidate_negative_controls.v1",
        "attempted": 0,
        "rejected": 0,
        "accepted": 0,
        "passed": False,
        "controls": [],
        "base_candidate_id": candidate["candidate_id"],
        "base_selection": "fixed_F1_B_before_outcome_inspection",
        "base_replay_qualified": baseline["qualified"],
        "base_first_failure": baseline["first_failure"],
        "baseline_independent_replay_count": 1,
        "negative_independent_replay_count": 0,
        "positive_runtime_executions": 0,
        "provider_calls": 0,
        "formal_quotient_class_count": None,
        "all_controls_use_isolated_actual_files": True,
        "field_origin": "host_derived",
    }
    if not baseline["qualified"]:
        audit["not_attempted_reason"] = "fixed_baseline_did_not_independently_qualify"
        return audit
    original_files = _runtime_files(writer, result)
    original_binding = _binding(original_files)
    evidence_ids = {item.evidence_id for item in fixture["bundle"].evidence}
    foreign_evidence_id = next(
        item.evidence_id
        for other in fixtures
        if other["fixture_id"] != "F1"
        for item in other["bundle"].evidence
        if item.evidence_id not in evidence_ids
    )
    names = (
        "reversed_growth_periods",
        "reversed_signed_operand_roles",
        "future_evidence",
        "cross_task_evidence",
        "unverified_claim",
        "missing_actual_observation",
        "comparison_only_final",
        "caller_qualified_true",
        "fabricated_model_ownership",
        "route_label_only",
    )
    expected_stages = {
        "reversed_growth_periods": "replay.growth_roles",
        "reversed_signed_operand_roles": "replay.signed_operand_roles",
        "future_evidence": "replay.visible_evidence",
        "cross_task_evidence": "replay.visible_evidence",
        "unverified_claim": "replay.observation_update",
        "missing_actual_observation": "replay.missing_or_invalid_artifact",
        "comparison_only_final": "replay.final_grounding",
        "caller_qualified_true": "replay.caller_authority",
        "fabricated_model_ownership": "replay.field_provenance",
        "route_label_only": None,
    }
    for name in names:
        files = dict(original_files)
        changed_candidate, changed_result, details = _mutate(
            name, files, deepcopy(dict(candidate)), deepcopy(dict(result)), foreign_evidence_id
        )
        # Declaration and result mutations also pass through actual saved bytes.
        files["control_inputs/candidate.json"] = canonical_json_bytes(changed_candidate)
        files["control_inputs/result.json"] = canonical_json_bytes(changed_result)
        with TemporaryDirectory(prefix="typed-candidate-negative-") as temporary:
            isolated = DurableArtifactWriter(Path(temporary))
            for path, data in sorted(files.items()):
                isolated.write_bytes(path, data)
            declared = CandidateRoute.model_validate(
                json.loads(isolated.read_bytes("control_inputs/candidate.json"))
            )
            persisted_candidate = declared.model_dump(mode="python")
            persisted_candidate["program"] = declared.program
            persisted_result = json.loads(isolated.read_bytes("control_inputs/result.json"))
            observed = validate_candidate(
                writer=isolated,
                fixture=fixture,
                candidate=persisted_candidate,
                result=persisted_result,
            )
            if observed["first_failure"] is not None:
                observed["first_failure"]["reason"] = observed["first_failure"]["reason"].replace(
                    str(isolated.root), "<isolated_root>"
                )
        expected_qualified = name == "route_label_only"
        passed = observed["qualified"] is expected_qualified
        if expected_qualified:
            passed = passed and (
                observed["actual_retained_typed_structure"]
                == baseline["actual_retained_typed_structure"]
                and observed["quotient_class_count"] is None
                and observed["formal_projection_created"] is False
            )
        else:
            passed = passed and (
                observed["first_failure"] is not None
                and observed["first_failure"]["stage"] == expected_stages[name]
            )
        audit["controls"].append(
            {
                "name": name,
                "expected_qualified": expected_qualified,
                "expected_first_failure_stage": expected_stages[name],
                "qualified": observed["qualified"],
                "qa_valid": observed["qa_valid"],
                "trajectory_valid": observed["trajectory_valid"],
                "first_failure": observed["first_failure"],
                "passed": passed,
                "baseline_qualified_before_mutation": True,
                "actual_saved_artifact_replay": True,
                "counted_as_new_positive_execution": False,
                "counted_as_new_semantic_class": False,
                **details,
            }
        )
    audit["attempted"] = len(audit["controls"])
    audit["negative_independent_replay_count"] = audit["attempted"]
    audit["invalid_control_count"] = 9
    audit["label_only_acceptance_control_count"] = 1
    audit["rejected"] = sum(not item["qualified"] for item in audit["controls"])
    audit["accepted"] = sum(item["qualified"] for item in audit["controls"])
    audit["source_file_binding_before"] = original_binding
    audit["source_file_binding_after"] = _binding(_runtime_files(writer, result))
    audit["formal_artifact_bytes_unchanged"] = (
        audit["source_file_binding_after"] == original_binding
    )
    audit["passed"] = (
        all(item["passed"] for item in audit["controls"])
        and audit["formal_artifact_bytes_unchanged"]
    )
    return audit
