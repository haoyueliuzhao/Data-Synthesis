"""Exact existing-model cohort admission; reuse qualification without executing QA.

This module reads immutable pilot bytes and the pilot's artifact reader only. It
does not import pilot preflight, invoke its audits, or execute any model/kernel.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    source_group,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot.independent import (
    read_session_records,
)

from .models import (
    LABELS,
    PARENT,
    PARENT_MANIFEST,
    PARENT_ROOT,
    PARENT_SOURCE_COMMIT,
    PARENT_SOURCE_TREE,
    MeasurementError,
    record,
    require,
    sha,
)

PARENT_FILE_COUNT = 785
PARENT_BYTE_COUNT = 8_312_321
EXPECTED_CALLBACK_COUNTS = (12, 7, 12, 6, 9, 5)
# These describe this immutable input snapshot; they are not a new QA rule or
# inferred defaults for other data. Actual outcomes below are copied from audits.
EXPECTED_SAVED_Y = (0, 1, 1, 1, 1, 1)
PILOT_SOURCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_share_model_pilot/"
    + name
    for name in (
        "__init__.py",
        "models.py",
        "adapter.py",
        "engine.py",
        "controls.py",
        "independent.py",
        "preflight.py",
    )
)


def _json(files: Mapping[str, bytes], path: str) -> dict[str, Any]:
    require(path in files, "inputs.missing_record")
    value = json.loads(files[path])
    require(isinstance(value, dict), "inputs.record_object")
    require(canonical_json_bytes(value) == files[path], "inputs.canonical_record")
    return value


def _reference(files: Mapping[str, bytes], path: str) -> dict[str, Any]:
    value = _json(files, path)
    return {
        "relative_path": path,
        "id": value.get("id", value.get("manifest_id")),
        "sha256": sha(files[path]),
        "byte_count": len(files[path]),
    }


def _validate_session(
    session: Mapping[str, Any], registration: Mapping[str, Any], index: int
) -> None:
    """Check saved qualification parents, not the Provider or numerical QA again."""
    label = LABELS[index]
    declaration, qualification, records = (
        session["declaration"],
        session["qualification"],
        session["records"],
    )
    manifest, stop, initial = records["manifest"], records["stop"], records["initial_state"]
    require(
        session["label"] == declaration["label"] == label
        and declaration == registration["sessions"][index]
        and declaration["id"] == registration["session_ids"][index]
        and declaration["ordinal"] == index
        and declaration["generator_origin"] == "model"
        and declaration["neutral_prompt"] is True
        and declaration["reference_route"] is None
        and declaration["independent_initial_state"] is True
        and declaration["reads_other_session_responses"] is False
        and declaration["replacement_allowed"] is False,
        "inputs.registered_model_cohort",
    )
    require(
        qualification["session_label"] == label
        and qualification["session_id"]
        == manifest["session_id"]
        == stop["session_id"]
        == declaration["id"]
        and qualification["origin"] == manifest["origin"] == "model"
        and qualification["session_manifest_id"] == manifest["id"]
        and qualification["session_stop_id"] == stop["id"]
        and qualification["persisted_artifact_validation"] is True,
        "inputs.qualification_parents",
    )
    require(
        declaration["protocol_id"]
        == qualification["protocol_id"]
        == manifest["protocol_id"]
        == initial["protocol_id"]
        == registration["protocol_id"]
        and declaration["model_configuration_id"]
        == qualification["model_configuration_id"]
        == manifest["model_configuration_id"]
        == registration["model_configuration_id"]
        and qualification["adapter_binding_id"]
        == manifest["generator_binding_id"]
        == registration["adapter_binding_id"],
        "inputs.session_condition",
    )
    require(
        qualification["evidence_complete"] is True
        and qualification["protocol_valid"] is True
        and type(qualification["qualified"]) is bool
        and type(qualification["Y"]) is int
        and qualification["Y"] == int(qualification["qualified"])
        and qualification["Y"] == EXPECTED_SAVED_Y[index],
        "inputs.saved_qualification",
    )
    if qualification["qualified"]:
        require(
            qualification["valid_final"] is True
            and qualification["qa_valid"] is True
            and qualification["terminal_reason"] == "final_submitted",
            "inputs.qualified_terminal",
        )
    else:
        require(
            qualification["valid_final"] is False
            and qualification["qa_valid"] is None
            and qualification["terminal_reason"] == "submission_budget_exhausted",
            "inputs.saved_failure",
        )
    count = len(records["events"])
    require(
        count == len(manifest["events"]) == EXPECTED_CALLBACK_COUNTS[index]
        and qualification["callback_attempts"]
        == qualification["provider_attempts"]
        == qualification["public_submission_count"]
        == count
        and manifest["generator_callbacks"]
        == manifest["provider_attempts"]
        == manifest["public_submission_attempts"]
        == count
        and qualification["raw_public_json_response_count"] == count,
        "inputs.complete_saved_interactions",
    )
    for event in records["events"]:
        submission, receipt = event["submission"], event["receipt"]
        require(isinstance(submission, dict) and isinstance(receipt, dict), "inputs.public_record")
        raw_text = submission["raw_public_json"]
        require(
            isinstance(raw_text, str)
            and isinstance(submission["parsed"], dict)
            and submission["field_origin"] == "model"
            and submission["host_repairs"] == [],
            "inputs.original_public_submission",
        )
        raw = raw_text.encode("utf-8")
        require(
            sha(raw) == submission["response_sha256"]
            and len(raw) == submission["response_byte_count"]
            and json.loads(raw_text) == submission["parsed"]
            and receipt["submission_id"] == submission["id"],
            "inputs.original_public_bytes",
        )


def load_inputs(repo_root: Path) -> dict[str, Any]:
    """Admit only the exact historical cohort, with no new model or QA execution."""
    root = repo_root.resolve()
    try:
        parent_files = files_at(root / PARENT)
        require(
            len(parent_files) == PARENT_FILE_COUNT
            and sum(map(len, parent_files.values())) == PARENT_BYTE_COUNT,
            "inputs.parent_geometry",
        )
        parent_manifest = validate_manifest(parent_files, PARENT_MANIFEST, PARENT_ROOT)
        context = _json(parent_files, "public_context.json")
        protocol = _json(parent_files, "protocol_contract.json")
        config = _json(parent_files, "model_config.json")
        registration = _json(parent_files, "pilot_registration.json")
        parent_report = _json(parent_files, "report.json")
        parent_measurement = _json(parent_files, "pilot_measurement.json")
        inherited_freeze = _json(parent_files, "parent_freeze.json")
        authority = _json(parent_files, "source_authority.json")
        source = source_group(root, PARENT_SOURCE_COMMIT, PARENT_SOURCE_TREE, PILOT_SOURCE_PATHS)
        require(source == authority["implementation"], "inputs.parent_source_identity")
        ids = registration["session_ids"]
        require(
            len(ids) == len(set(ids)) == len(registration["sessions"]) == 6
            and ids == [item["id"] for item in registration["sessions"]]
            and registration["fixed_online_denominator"] == 6
            and not set(ids).intersection(registration["control_session_ids"])
            and registration["before_first_online_attempt"] is True
            and registration["never_replace_or_add_sessions"] is True,
            "inputs.exact_six_cohort",
        )
        require(
            protocol["public_context_id"] == context["id"]
            and protocol["task_id"] == context["task"]["id"]
            and protocol["id"] == registration["protocol_id"]
            and protocol["model_configuration_id"]
            == config["id"]
            == registration["model_configuration_id"]
            == parent_report["model_configuration_id"]
            and parent_report["pilot_registration_id"] == registration["id"]
            and parent_report["source_authority_id"]
            == registration["source_authority_id"]
            == authority["id"]
            and parent_report["measurement"] == parent_measurement,
            "inputs.frozen_generation_condition",
        )
        sessions = []
        for index, label in enumerate(LABELS):
            item = {
                "label": label,
                "declaration": _json(parent_files, "declarations/" + label + ".json"),
                "qualification": _json(parent_files, "online_reports/" + label + ".json"),
                "records": read_session_records(root / PARENT / "online" / label),
            }
            _validate_session(item, registration, index)
            sessions.append(item)
        saved_ys = [item["qualification"]["Y"] for item in sessions]
        require(
            sum(len(item["records"]["events"]) for item in sessions) == 51
            and parent_measurement["registered_denominator"] == 6
            and parent_measurement["evidence_complete_count"] == 6
            and parent_measurement["success_count"] == sum(saved_ys)
            and parent_measurement["Y_by_session"]
            == [
                {"session_id": item["declaration"]["id"], "Y": item["qualification"]["Y"]}
                for item in sessions
            ],
            "inputs.saved_outcome_population",
        )
        conditions = (
            "public_context.json",
            "protocol_contract.json",
            "model_config.json",
            "pilot_registration.json",
            "report.json",
            "pilot_measurement.json",
            "source_authority.json",
            "parent_freeze.json",
            "model_adapter_binding.json",
        )
        cohort = []
        for item in sessions:
            label, records = item["label"], item["records"]
            session_path = "online/" + label + "/"
            cohort.append(
                {
                    "label": label,
                    "session_id": item["declaration"]["id"],
                    "declaration": _reference(parent_files, "declarations/" + label + ".json"),
                    "qualification": _reference(parent_files, "online_reports/" + label + ".json"),
                    "session_manifest": _reference(
                        parent_files, session_path + "session_manifest.json"
                    ),
                    "initial_state": _reference(
                        parent_files, session_path + records["manifest"]["initial_state"]
                    ),
                    "stop": _reference(
                        parent_files, session_path + records["manifest"]["stop_record"]
                    ),
                    "saved_Y": item["qualification"]["Y"],
                    "saved_qualified": item["qualification"]["qualified"],
                    "saved_event_count": len(records["events"]),
                }
            )
        parent_freeze = record(
            "parent_freeze",
            parent_directory=PARENT,
            parent_manifest_id=PARENT_MANIFEST,
            parent_artifact_root=PARENT_ROOT,
            parent_manifest_sha256=sha(parent_files["artifact_manifest.json"]),
            parent_manifest_bytes=len(parent_files["artifact_manifest.json"]),
            member_count=len(parent_files),
            member_bytes=sum(map(len, parent_files.values())),
            members=[
                {"relative_path": path, "sha256": sha(payload), "byte_count": len(payload)}
                for path, payload in sorted(parent_files.items())
            ],
            includes_parent_manifest_member=True,
            source_commit=PARENT_SOURCE_COMMIT,
            source_tree=PARENT_SOURCE_TREE,
            source_authority_id=authority["id"],
            inherited_provenance_freeze_id=inherited_freeze["id"],
            condition_references=[_reference(parent_files, path) for path in conditions],
            cohort=cohort,
            outcome_session_ids=ids,
            qualified_session_ids=[
                item["declaration"]["id"] for item in sessions if item["qualification"]["qualified"]
            ],
            original_public_submissions=51,
            qualification_authority="unchanged manifest-bound existing independent pilot audits",
            new_qa_validation=False,
            new_adapter_audit=False,
            excluded_mock_session_ids=registration["control_session_ids"],
            old_fixture_sessions_in_population=0,
            old_quotient_ids_or_support_labels_are_assignments=False,
            original_bytes_retained_in_parent=True,
            copies_of_original_trajectories_are_new_samples=False,
        )
        result = {
            "parent_files": parent_files,
            "context": context,
            "protocol": protocol,
            "model_config": config,
            "pilot_registration": registration,
            "parent_report": parent_report,
            "parent_measurement": parent_measurement,
            "parent_manifest": parent_manifest,
            "parent_freeze": parent_freeze,
            "sessions": sessions,
        }
        assert_unchanged(root, result)
        return result
    except MeasurementError:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError, RecursionError):
        raise MeasurementError("inputs.invalid_frozen_evidence") from None


def assert_unchanged(repo_root: Path, frozen: Mapping[str, Any]) -> None:
    """No projection or reconstruction may mutate its exact historical input bytes."""
    try:
        require(
            files_at(repo_root.resolve() / PARENT) == frozen["parent_files"],
            "inputs.parent_changed",
        )
    except MeasurementError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise MeasurementError("inputs.parent_unavailable") from None
