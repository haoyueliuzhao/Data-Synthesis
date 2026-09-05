"""Bind closed assignments and export exact original request-conditioned targets.

Only immutable artifact readers are reused.  No old projection, comparison, QA
qualification, tokenizer, provider, candidate runtime or Student is executed.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_share_quotient_measurement.inputs import (
    load_inputs as load_pilot_inputs,
)

from .models import (
    LABELS,
    PILOT_MANIFEST,
    PILOT_PARENT,
    PILOT_ROOT,
    QUOTIENT_MANIFEST,
    QUOTIENT_PARENT,
    QUOTIENT_ROOT,
    TrainingPreflightError,
    identity,
    record,
    representation_contract,
    require,
    sha,
)

PARENT_GEOMETRY = {"quotient": (51, 1_086_642), "pilot": (785, 8_312_321)}
ROW_FIELDS = {
    "id",
    "schema_version",
    "session_id",
    "session_label",
    "state_id",
    "assignment_id",
    "qualification_id",
    "session_manifest_id",
    "turn_index",
    "kind",
    "messages",
    "target_text",
    "request_id",
    "provider_request_id",
    "provider_response_id",
    "submission_id",
    "receipt_id",
    "event_id",
    "source_state_id",
    "source_body_sha256",
    "target_sha256",
    "target_byte_count",
    "representation_contract_id",
    "source_paths",
}


def _json(files: Mapping[str, bytes], path: str) -> dict[str, Any]:
    require(path in files, "training_inputs.missing_original")
    value = json.loads(files[path])
    require(isinstance(value, dict), "training_inputs.original_record_type")
    require(canonical_json_bytes(value) == files[path], "training_inputs.original_canonical_bytes")
    if "id" in value:
        identity(value)
    return value


def _inventory(files: Mapping[str, bytes]) -> list[dict[str, Any]]:
    return [
        {"relative_path": path, "sha256": sha(data), "byte_count": len(data)}
        for path, data in sorted(files.items())
    ]


def _parent_binding(name: str, files: Mapping[str, bytes]) -> dict[str, Any]:
    directory, manifest_id, root = (
        (QUOTIENT_PARENT, QUOTIENT_MANIFEST, QUOTIENT_ROOT)
        if name == "quotient"
        else (PILOT_PARENT, PILOT_MANIFEST, PILOT_ROOT)
    )
    count, byte_count = PARENT_GEOMETRY[name]
    require(
        len(files) == count and sum(map(len, files.values())) == byte_count,
        "training_inputs." + name + "_geometry",
    )
    manifest = validate_manifest(files, manifest_id, root)
    return {
        "directory": directory,
        "manifest_id": manifest["manifest_id"],
        "artifact_root": manifest["artifact_root"],
        "manifest_sha256": sha(files["artifact_manifest.json"]),
        "manifest_byte_count": len(files["artifact_manifest.json"]),
        "file_count": len(files),
        "total_bytes": sum(map(len, files.values())),
        "members": _inventory(files),
        "includes_original_manifest": True,
    }


def _assignment_index(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Reuse a closed assignment exactly; no graph inspection or relation inference."""
    quotient_files, pilot_files = inputs["quotient_files"], inputs["pilot_files"]
    partition = inputs["partition"]
    require(
        partition == _json(quotient_files, "relation_partition.json")
        and partition["complete"] is True
        and partition["class_count"] == 2
        and partition["unmapped_session_ids"] == [],
        "training_inputs.closed_partition",
    )
    saved_assignments = {item["session_id"]: item for item in partition["assignments"]}
    require(
        len(saved_assignments) == len(partition["assignments"]) == 5,
        "training_inputs.five_assignments",
    )
    actual_states = {}
    for path in sorted(quotient_files):
        if path.startswith("states/") and path.endswith(".json"):
            state = _json(quotient_files, path)
            require(state["id"] not in actual_states, "training_inputs.duplicate_saved_state")
            actual_states[state["id"]] = state
    require(
        len(actual_states) == len(inputs["states"]) == 2
        and {state["id"]: state for state in inputs["states"]} == actual_states,
        "training_inputs.two_original_states",
    )
    assignments = {}
    selected = []
    sessions = inputs["sessions"]
    require(
        [session["label"] for session in sessions] == list(LABELS),
        "training_inputs.six_original_sessions",
    )
    for session in sessions:
        label, declaration, qualification = (
            session["label"],
            session["declaration"],
            session["qualification"],
        )
        records = session["records"]
        require(
            declaration == _json(pilot_files, "declarations/" + label + ".json")
            and qualification == _json(pilot_files, "online_reports/" + label + ".json")
            and records["manifest"]
            == _json(pilot_files, "online/" + label + "/session_manifest.json")
            and declaration["id"]
            == qualification["session_id"]
            == records["manifest"]["session_id"]
            and qualification["session_manifest_id"] == records["manifest"]["id"],
            "training_inputs.session_original_binding",
        )
        if qualification["qualified"] is not True:
            require(
                declaration["id"] not in saved_assignments,
                "training_inputs.failed_session_assigned",
            )
            continue
        assignment = _json(quotient_files, "assignments/" + label + ".json")
        require(
            assignment == saved_assignments[declaration["id"]]
            and assignment["session_id"] == declaration["id"]
            and assignment["qualification_id"] == qualification["id"]
            and assignment["session_manifest_id"] == records["manifest"]["id"]
            and assignment["condition"] == partition["condition"]
            and assignment["state_id"] in actual_states
            and assignment["condition"] == actual_states[assignment["state_id"]]["condition"],
            "training_inputs.assignment_original_binding",
        )
        assignments[declaration["id"]] = assignment
        selected.append(assignment)
    require(inputs["assignments"] == selected, "training_inputs.assignment_collection_changed")
    require(set(assignments) == set(saved_assignments), "training_inputs.assignment_population")
    members = {}
    for group in partition["classes"]:
        require(
            group["state_id"] in actual_states
            and group["state"] == actual_states[group["state_id"]],
            "training_inputs.saved_class_state_binding",
        )
        for identifier in group["members"]:
            require(
                identifier in assignments
                and identifier not in members
                and assignments[identifier]["state_id"] == group["state_id"],
                "training_inputs.saved_membership_binding",
            )
            members[identifier] = group["state_id"]
    require(set(members) == set(assignments), "training_inputs.saved_class_coverage")
    return assignments


def _verify_frozen_inputs(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    freeze = inputs["parent_freeze"]
    identity(freeze)
    for name in ("quotient", "pilot"):
        require(
            freeze[name] == _parent_binding(name, inputs[name + "_files"]),
            "training_inputs.parent_freeze_binding",
        )
    quotient = inputs["quotient_files"]
    require(
        inputs["quotient_report"] == _json(quotient, "report.json")
        and inputs["empirical_measurement"] == _json(quotient, "empirical_measurement.json")
        and inputs["quotient_report"]["partition_id"] == inputs["partition"]["id"]
        and inputs["quotient_report"]["empirical_measurement"] == inputs["empirical_measurement"]
        and inputs["quotient_report"]["status"]
        == "finite_quotient_measurement_completed_as_scoped",
        "training_inputs.closed_measurement_binding",
    )
    for key, path in (
        ("context", "public_context.json"),
        ("protocol", "protocol_contract.json"),
        ("model_config", "model_config.json"),
        ("pilot_registration", "pilot_registration.json"),
    ):
        require(
            inputs[key] == _json(inputs["pilot_files"], path),
            "training_inputs.fixed_generation_condition",
        )
    assignments = _assignment_index(inputs)
    condition = inputs["partition"]["condition"]
    require(
        condition["task_id"] == inputs["context"]["task"]["id"]
        and condition["public_context_id"] == inputs["context"]["id"]
        and condition["protocol_id"] == inputs["protocol"]["id"]
        and condition["model_configuration_id"] == inputs["model_config"]["id"]
        and condition["pilot_registration_id"] == inputs["pilot_registration"]["id"]
        and freeze["partition_id"] == inputs["partition"]["id"]
        and freeze["assignment_ids"] == [assignment["id"] for assignment in inputs["assignments"]]
        and freeze["state_ids"] == [state["id"] for state in inputs["states"]]
        and freeze["qualification_or_quotient_recomputed"] is False,
        "training_inputs.frozen_authority_condition",
    )
    return assignments


def load_inputs(repo_root: Path) -> dict[str, Any]:
    """Read both complete parents and bind saved outcomes/assignments without rerunning them."""
    root = repo_root.resolve()
    try:
        quotient_files = files_at(root / QUOTIENT_PARENT)
        quotient_binding = _parent_binding("quotient", quotient_files)
        original = load_pilot_inputs(root)
        pilot_files = original["parent_files"]
        pilot_binding = _parent_binding("pilot", pilot_files)
        partition = _json(quotient_files, "relation_partition.json")
        assignments = [
            _json(quotient_files, "assignments/" + session["label"] + ".json")
            for session in original["sessions"]
            if session["qualification"]["qualified"]
        ]
        states = [
            _json(quotient_files, path)
            for path in sorted(quotient_files)
            if path.startswith("states/") and path.endswith(".json")
        ]
        freeze = record(
            "parent_freeze",
            quotient=quotient_binding,
            pilot=pilot_binding,
            quotient_report_id=_json(quotient_files, "report.json")["id"],
            partition_id=partition["id"],
            empirical_measurement_id=_json(quotient_files, "empirical_measurement.json")["id"],
            assignment_ids=[item["id"] for item in assignments],
            state_ids=[state["id"] for state in states],
            pilot_registration_id=original["pilot_registration"]["id"],
            saved_qualification_ids=[
                session["qualification"]["id"] for session in original["sessions"]
            ],
            original_session_count=6,
            original_public_submission_count=51,
            saved_qualified_trajectory_count=5,
            saved_state_count=2,
            qualification_or_quotient_recomputed=False,
            original_failures_retained=True,
            historical_bytes_modified=False,
            provider_calls=0,
            credential_reads=0,
            new_candidate_runtime_executions=0,
            Student_parameter_updates=0,
            GPU_jobs=0,
        )
        result = {
            "quotient_files": quotient_files,
            "pilot_files": pilot_files,
            "parent_freeze": freeze,
            "quotient_report": _json(quotient_files, "report.json"),
            "partition": partition,
            "empirical_measurement": _json(quotient_files, "empirical_measurement.json"),
            "assignments": assignments,
            "states": states,
            "sessions": original["sessions"],
            **{
                key: original[key]
                for key in ("context", "protocol", "model_config", "pilot_registration")
            },
        }
        _verify_frozen_inputs(result)
        assert_unchanged(root, result)
        return result
    except TrainingPreflightError:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError, RecursionError) as error:
        raise TrainingPreflightError("training_inputs.invalid_original_evidence") from error


def assert_unchanged(repo_root: Path, inputs: Mapping[str, Any]) -> None:
    for name, path in (("quotient", QUOTIENT_PARENT), ("pilot", PILOT_PARENT)):
        require(
            files_at(repo_root.resolve() / path) == inputs[name + "_files"],
            "training_inputs." + name + "_changed",
        )


def _contract(contract: Mapping[str, Any]) -> None:
    identity(contract)
    require(
        contract == representation_contract({"id": contract["tokenizer_binding_id"]}),
        "text.representation_contract_substitution",
    )


def _paths(
    inputs: Mapping[str, Any],
    session: Mapping[str, Any],
    index: int,
    assignment: Mapping[str, Any] | None,
) -> dict[str, Any]:
    label = session["label"]
    prefix = "online/" + label + "/"
    pilot = {
        **{
            name: prefix + path
            for name, path in session["records"]["manifest"]["events"][index].items()
        },
        "declaration": "declarations/" + label + ".json",
        "qualification": "online_reports/" + label + ".json",
        "session_manifest": prefix + "session_manifest.json",
    }
    quotient = {}
    if assignment is not None:
        quotient["assignment"] = "assignments/" + label + ".json"
        state_paths = [
            path
            for path in sorted(inputs["quotient_files"])
            if path.startswith("states/")
            and path.endswith(".json")
            and _json(inputs["quotient_files"], path)["id"] == assignment["state_id"]
        ]
        require(len(state_paths) == 1, "text.original_state_path")
        quotient["state"] = state_paths[0]
    return {"pilot": pilot, "quotient": quotient}


def _exchange(
    inputs: Mapping[str, Any],
    session: Mapping[str, Any],
    index: int,
) -> tuple[dict[str, Any], list[dict[str, str]], str]:
    events, manifest = session["records"]["events"], session["records"]["manifest"]
    event = events[index]
    paths = manifest["events"][index]
    prefix = "online/" + session["label"] + "/"
    for name, path in paths.items():
        require(
            event[name] == _json(inputs["pilot_files"], prefix + path),
            "text.original_event_changed",
        )
    request, provider_request, response, submission, receipt, turn = (
        event["request"],
        event["provider_request"],
        event["provider_response"],
        event["submission"],
        event["receipt"],
        event["generator_turn"],
    )
    source_state = request["state_id"]
    sid = session["declaration"]["id"]
    body_text = provider_request["body_json"]
    body = json.loads(body_text)
    messages = body["messages"]
    target = submission["raw_public_json"]
    require(
        isinstance(messages, list)
        and len(messages) == 2
        and all(set(message) == {"role", "content"} for message in messages)
        and [message["role"] for message in messages] == ["system", "user"]
        and all(isinstance(message["content"], str) for message in messages)
        and messages[1]["content"] == canonical_json_bytes(request).decode("utf-8")
        and sha(body_text.encode("utf-8")) == provider_request["body_sha256"]
        and len(body_text.encode("utf-8")) == provider_request["body_byte_count"],
        "text.exact_original_http_messages",
    )
    require(
        isinstance(target, str)
        and json.loads(target) == submission["parsed"]
        and submission["field_origin"] == turn["origin"] == response["generator_origin"] == "model"
        and submission["host_repairs"] == []
        and receipt["response_rewritten"] is False
        and receipt["missing_fields_filled"] is False
        and response["status"] == "received"
        and response["parser_status"] == "valid",
        "text.original_model_public_content",
    )
    encoded = target.encode("utf-8")
    require(
        sha(encoded)
        == submission["response_sha256"]
        == turn["response_sha256"]
        == response["public_content_sha256"]
        and len(encoded)
        == submission["response_byte_count"]
        == turn["response_byte_count"]
        == response["public_content_bytes"],
        "text.original_target_hash_binding",
    )
    require(
        provider_request["session_id"] == response["session_id"] == turn["session_id"] == sid
        and provider_request["public_request_id"]
        == response["public_request_id"]
        == submission["request_id"]
        == receipt["request_id"]
        == turn["request_id"]
        == request["id"]
        and response["request_id"] == provider_request["id"]
        and turn["provider_response_id"] == response["id"]
        and submission["generator_turn_id"] == turn["id"]
        and provider_request["state_id"]
        == response["state_id"]
        == turn["state_id"]
        == submission["state_id"]
        == submission["parsed"]["state_id"]
        == receipt["pre_state_id"]
        == request["state"]["id"]
        == source_state
        and receipt["submission_id"] == submission["id"]
        and receipt["submission_sha256"] == sha(canonical_json_bytes(submission))
        and receipt["submission_byte_count"] == len(canonical_json_bytes(submission)),
        "text.original_request_response_parent_joins",
    )
    for name in ("request", "generator_turn", "submission", "receipt"):
        require(event["event"][name + "_id"] == event[name]["id"], "text.original_event_parent")
    return event, messages, target


def _source_fields(
    inputs: Mapping[str, Any],
    session: Mapping[str, Any],
    index: int,
    assignment: Mapping[str, Any] | None,
    contract: Mapping[str, Any],
    event: Mapping[str, Any],
) -> dict[str, Any]:
    submission = event["submission"]
    return {
        "session_id": session["declaration"]["id"],
        "session_label": session["label"],
        "state_id": assignment["state_id"] if assignment is not None else None,
        "assignment_id": assignment["id"] if assignment is not None else None,
        "qualification_id": session["qualification"]["id"],
        "session_manifest_id": session["records"]["manifest"]["id"],
        "turn_index": index,
        "kind": submission["parsed"]["kind"],
        "request_id": event["request"]["id"],
        "provider_request_id": event["provider_request"]["id"],
        "provider_response_id": event["provider_response"]["id"],
        "submission_id": submission["id"],
        "receipt_id": event["receipt"]["id"],
        "event_id": event["event"]["id"],
        "source_state_id": event["request"]["state_id"],
        "source_body_sha256": event["provider_request"]["body_sha256"],
        "target_sha256": submission["response_sha256"],
        "target_byte_count": submission["response_byte_count"],
        "representation_contract_id": contract["id"],
        "source_paths": _paths(inputs, session, index, assignment),
    }


def _counts(
    rows: list[dict[str, Any]], exclusions: list[dict[str, Any]], inputs: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "original_sessions": len(inputs["sessions"]),
        "qualified_trajectories": len(inputs["assignments"]),
        "fixed_state_count": len(inputs["states"]),
        "original_public_submissions": sum(len(s["records"]["events"]) for s in inputs["sessions"]),
        "positive_units": len(rows),
        "positive_kind_counts": dict(Counter(row["kind"] for row in rows)),
        "positive_units_by_session": {
            session["label"]: sum(row["session_id"] == session["declaration"]["id"] for row in rows)
            for session in inputs["sessions"]
        },
        "positive_target_utf8_bytes": sum(row["target_byte_count"] for row in rows),
        "excluded_units": len(exclusions),
        "excluded_nonqualified_units": sum(
            row["reason"] == "nonqualified_trajectory" for row in exclusions
        ),
        "excluded_rejected_qualified_units": sum(
            row["reason"] == "rejected_submission" for row in exclusions
        ),
    }


def export_rows(inputs: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Select admitted targets without rewriting a single original message or response."""
    try:
        _contract(contract)
        assignments = _verify_frozen_inputs(inputs)
        rows, exclusions = [], []
        for session in inputs["sessions"]:
            assignment = assignments.get(session["declaration"]["id"])
            for index in range(len(session["records"]["events"])):
                event, messages, target = _exchange(inputs, session, index)
                fields = _source_fields(inputs, session, index, assignment, contract, event)
                if assignment is not None and event["receipt"]["admitted"] is True:
                    rows.append(
                        record("training_row", **fields, messages=messages, target_text=target)
                    )
                else:
                    exclusions.append(
                        record(
                            "excluded_submission",
                            **fields,
                            receipt_admitted=event["receipt"]["admitted"],
                            reason="nonqualified_trajectory"
                            if assignment is None
                            else "rejected_submission",
                            positive_imitation_loss_weight=0,
                            original_target_retained_in_parent=True,
                        )
                    )
        dataset = record(
            "text_dataset",
            representation_contract_id=contract["id"],
            parent_freeze_id=inputs["parent_freeze"]["id"],
            rows=rows,
            exclusions=exclusions,
            counts=_counts(rows, exclusions, inputs),
            original_messages_and_public_targets_preserved=True,
            cleaned_counterfactual_trajectory=False,
            tokenization_performed=False,
            qualification_or_quotient_recomputed=False,
            preflight_only_not_training_release=True,
        )
        validate_text_dataset(inputs, contract, dataset)
        return dataset
    except TrainingPreflightError:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError, RecursionError) as error:
        raise TrainingPreflightError("text.export_invalid_source") from error


def validate_text_dataset(
    inputs: dict[str, Any],
    contract: dict[str, Any],
    dataset: dict[str, Any],
) -> dict[str, Any]:
    """Check actual source membership and bytes independently of any tokenizer."""
    try:
        _contract(contract)
        assignments = _verify_frozen_inputs(inputs)
        identity(dataset)
        require(
            dataset["schema_version"] == "share_training_text_dataset.v1"
            and dataset["representation_contract_id"] == contract["id"]
            and dataset["parent_freeze_id"] == inputs["parent_freeze"]["id"]
            and dataset["original_messages_and_public_targets_preserved"] is True
            and dataset["cleaned_counterfactual_trajectory"] is False
            and dataset["tokenization_performed"] is False
            and dataset["qualification_or_quotient_recomputed"] is False
            and dataset["preflight_only_not_training_release"] is True,
            "text.dataset_condition",
        )
        expected_positive: list[tuple[str, int]] = []
        expected_excluded: list[tuple[str, int]] = []
        source = {}
        for session in inputs["sessions"]:
            sid = session["declaration"]["id"]
            assignment = assignments.get(sid)
            for index in range(len(session["records"]["events"])):
                event, messages, target = _exchange(inputs, session, index)
                key = (sid, index)
                source[key] = (session, assignment, event, messages, target)
                (
                    expected_positive
                    if assignment is not None and event["receipt"]["admitted"] is True
                    else expected_excluded
                ).append(key)
        require(
            [(row["session_id"], row["turn_index"]) for row in dataset["rows"]]
            == expected_positive,
            "text.positive_membership_order",
        )
        require(
            [(row["session_id"], row["turn_index"]) for row in dataset["exclusions"]]
            == expected_excluded,
            "text.complete_exclusion_coverage",
        )
        for positive, entries in ((True, dataset["rows"]), (False, dataset["exclusions"])):
            for row in entries:
                identity(row)
                key = (row["session_id"], row["turn_index"])
                session, assignment, event, messages, target = source[key]
                expected = _source_fields(
                    inputs, session, row["turn_index"], assignment, contract, event
                )
                require(
                    all(row.get(field) == value for field, value in expected.items()),
                    "text.exact_source_field_binding",
                )
                if positive:
                    require(
                        set(row) == ROW_FIELDS
                        and row["schema_version"] == "share_training_training_row.v1"
                        and row["messages"] == messages
                        and row["target_text"] == target,
                        "text.exact_original_input_and_target",
                    )
                else:
                    reason = (
                        "nonqualified_trajectory" if assignment is None else "rejected_submission"
                    )
                    require(
                        row["schema_version"] == "share_training_excluded_submission.v1"
                        and row["reason"] == reason
                        and row["positive_imitation_loss_weight"] == 0
                        and row["receipt_admitted"] is event["receipt"]["admitted"]
                        and row["original_target_retained_in_parent"] is True
                        and "target_text" not in row
                        and "messages" not in row,
                        "text.excluded_submission_no_positive_loss",
                    )
        counts = _counts(dataset["rows"], dataset["exclusions"], inputs)
        require(dataset["counts"] == counts, "text.derived_counts")
        require(
            counts["positive_units"] == contract["expected_positive_units"] == 27
            and counts["positive_kind_counts"]
            == contract["expected_supervision_unit_counts"]
            == {"action": 11, "update": 11, "final": 5}
            and counts["original_public_submissions"] == 51
            and counts["excluded_units"] == 24
            and counts["excluded_nonqualified_units"]
            == counts["excluded_rejected_qualified_units"]
            == 12,
            "text.finite_original_scope",
        )
        return record(
            "text_dataset_validation",
            passed=True,
            text_dataset_id=dataset["id"],
            representation_contract_id=contract["id"],
            parent_freeze_id=inputs["parent_freeze"]["id"],
            counts=counts,
            exact_original_messages_and_targets=True,
            fixed_assignments_reused=True,
            tokenization_or_mask_claimed=False,
            provider_calls=0,
            credential_reads=0,
            old_qualification_or_quotient_calls=0,
            new_candidate_runtime_executions=0,
            Student_parameter_updates=0,
            GPU_jobs=0,
        )
    except TrainingPreflightError:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError, RecursionError) as error:
        raise TrainingPreflightError("text.validation_invalid_source_or_dataset") from error
