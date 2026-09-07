"""Bind published exploration evidence for a new, measurement-only extension.

Only file bytes, record identities and existing parent links are checked here.
The original qualification, actual-support proof, old projection dispositions,
generation rule and representation remain historical inputs, never recomputed.
Token/CPU arrays are hashed as opaque files and are not decoded or loaded.
"""

from __future__ import annotations

import hashlib
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash

from ..finance_qa_vnext_model_execution.models import identity, read_json, record, require, sha

PARENT_COMMIT = "6d05782ad3e4e47978f2da19ba0bd5e3ac041fc2"
SOURCE_ROOT = (
    "trusted_data_synthesis/artifacts/qa_vnext_support_exploration/"
    "share_four_neutral_four_guided_v1_20260907"
)
LABELS = tuple(f"{profile}{wave:02d}" for wave in range(1, 5) for profile in ("N", "E"))
QUALIFIED_LABELS = ("E02", "N03", "E04")
NEW_UNDETERMINED_SEQUENCES = {"E02": [0, 1, 8, 10, 11, 13], "N03": [0]}
HISTORY_PREFIXES = (
    "qa_vnext_integration",
    "qa_vnext_model_execution",
    "qa_vnext_update_calibration",
    "qa_vnext_repaired_full_task",
    "qa_vnext_action_branch",
    "qa_vnext_length_adaptation",
    "qa_vnext_task_panel",
    "qa_vnext_panel_quotient",
    "qa_vnext_support_exploration",
)
SOURCE_FILE_COUNT = 2893
SOURCE_BYTE_COUNT = 143_825_264
HISTORY_FILE_COUNT = 15_877
HISTORY_BYTE_COUNT = 797_477_854
PREDECESSOR_PYTHON_COUNT = 908
GENERATION_CONDITION_ID = (
    "qa_vnext_model_execution_support_exploration_condition:"
    "1ce7cd127bdabb128949f389ed0f9dd9244a4ff48aa29eb9e61d72c80f89d0ca"
)
OLD_RULE_ID = (
    "qa_vnext_model_execution_panel_quotient_rule:"
    "0af6d8446a28f48387d6ea5697d9284c65907dc633422ee85393699b62d7cfb2"
)
OLD_REPORT_ID = (
    "qa_vnext_model_execution_support_exploration_report:"
    "8cb45bb6748246a185f224d4909992608a0e6017a33401f56557ea1b743463d6"
)
OLD_QUOTIENT_ID = (
    "qa_vnext_model_execution_support_exploration_quotient:"
    "7647fd3699b697bb066e6f741b27806b76bf03819995d1ab1a3f86720e054b4e"
)


def _regular_bytes(root: Path, relative: str) -> bytes:
    path = root / relative
    require(
        not Path(relative).is_absolute()
        and ".." not in Path(relative).parts
        and path.resolve().is_relative_to(root.resolve())
        and path.is_file()
        and not path.is_symlink(),
        "support_transition_source.regular_file",
    )
    return path.read_bytes()


def _git_members(
    root: Path,
    prefixes: tuple[str, ...],
    *,
    python_only: bool = False,
) -> list[dict[str, Any]]:
    tree = subprocess.check_output(
        ["git", "-C", str(root), "ls-tree", "-r", "-z", PARENT_COMMIT, "--", *prefixes]
    )
    members = []
    for item in tree.split(b"\0"):
        if not item:
            continue
        metadata, name_bytes = item.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        name = name_bytes.decode()
        if python_only and not name.endswith(".py"):
            continue
        require(mode == "100644" and kind == "blob", "support_transition_source.published_blob")
        raw = _regular_bytes(root, name)
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(actual == oid, "support_transition_source.published_bytes_changed")
        members.append({"path": name, "bytes": len(raw), "sha256": sha(raw), "git_blob_id": oid})
    require(bool(members), "support_transition_source.empty_tree")
    return members


def _actual_members(root: Path, prefixes: tuple[str, ...]) -> set[str]:
    members = set()
    for prefix in prefixes:
        directory = root / prefix
        require(
            directory.is_dir() and not directory.is_symlink(), "support_transition_source.directory"
        )
        for path in directory.rglob("*"):
            require(not path.is_symlink(), "support_transition_source.symlink")
            if path.is_file():
                members.add(path.relative_to(root).as_posix())
    return members


def source_anchor(root: Path) -> dict[str, Any]:
    root = root.resolve()
    members = _git_members(root, (SOURCE_ROOT,))
    require(
        _actual_members(root, (SOURCE_ROOT,)) == {item["path"] for item in members}
        and len(members) == SOURCE_FILE_COUNT
        and sum(item["bytes"] for item in members) == SOURCE_BYTE_COUNT,
        "support_transition_source.fixed_published_directory",
    )
    return record(
        "support_transition_source_anchor",
        predecessor_commit=PARENT_COMMIT,
        directory=SOURCE_ROOT,
        members=members,
        file_count=len(members),
        byte_count=sum(item["bytes"] for item in members),
        all_bytes_match_published_git_blobs=True,
    )


def history_inventory(root: Path) -> dict[str, Any]:
    root = root.resolve()
    prefixes = tuple("trusted_data_synthesis/artifacts/" + name for name in HISTORY_PREFIXES)
    members = _git_members(root, prefixes)
    require(
        _actual_members(root, prefixes) == {item["path"] for item in members}
        and len(members) == HISTORY_FILE_COUNT
        and sum(item["bytes"] for item in members) == HISTORY_BYTE_COUNT,
        "support_transition_source.fixed_history",
    )
    return record(
        "support_transition_history_inventory",
        predecessor_commit=PARENT_COMMIT,
        members=members,
        file_count=len(members),
        byte_count=sum(item["bytes"] for item in members),
        all_historical_bytes_unchanged=True,
    )


def preserved_sources(root: Path) -> dict[str, Any]:
    members = _git_members(root.resolve(), ("trusted_data_synthesis/src",), python_only=True)
    require(len(members) == PREDECESSOR_PYTHON_COUNT, "support_transition_source.old_python_count")
    return record(
        "support_transition_source_preservation",
        predecessor_commit=PARENT_COMMIT,
        members=members,
        file_count=len(members),
        all_predecessor_python_bytes_unchanged=True,
        original_generation_qualification_support_quotient_representation_modified=False,
    )


def _load(root: Path, relative: str, members: dict[str, dict[str, Any]]) -> Any:
    require(relative in members, "support_transition_source.unanchored_input")
    raw = _regular_bytes(root, relative)
    member = members[relative]
    require(
        len(raw) == member["bytes"] and sha(raw) == member["sha256"],
        "support_transition_source.changed_after_anchor",
    )
    return read_json(raw)


def _public_identity(value: dict[str, Any], kind: str) -> None:
    require(
        value.get("schema_version") == f"finance_qa_vnext_{kind}.v2"
        and value.get("id")
        == strict_canonical_hash(
            {key: item for key, item in value.items() if key != "id"},
            prefix=f"finance_qa_vnext_{kind}:",
        ),
        "support_transition_source.identity." + kind,
    )


def validate_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Check immutable identities and joins; do not rerun any prior measurement producer."""
    generation = inputs["generation_condition"]
    contract, report, quotient, measured = (
        inputs[key]
        for key in ("old_comparison_contract", "old_report", "old_quotient", "old_measurement")
    )
    for value, kind in (
        (generation, "support_exploration_condition"),
        (contract, "support_exploration_comparison_contract"),
        (report, "support_exploration_report"),
        (quotient, "support_exploration_quotient"),
        (measured, "support_exploration_measurement"),
    ):
        identity(value, kind)
    require(
        generation["id"] == GENERATION_CONDITION_ID
        and generation["rule_id"] == OLD_RULE_ID
        and generation["new_post_outcome_quotient_rules_allowed"] is False
        and report["id"] == OLD_REPORT_ID
        and quotient["id"] == OLD_QUOTIENT_ID
        and report["condition_id"]
        == contract["generation_condition_id"]
        == contract["exploration_condition_id"]
        == quotient["exploration_condition_id"]
        == measured["exploration_condition_id"]
        == generation["id"]
        and report["rule_id"]
        == contract["rule_id"]
        == quotient["rule_id"]
        == measured["rule_id"]
        == OLD_RULE_ID
        and report["comparison_contract_id"] == quotient["comparison_contract_id"] == contract["id"]
        and quotient["comparison_contract"] == contract
        and report["quotient_id"] == quotient["id"]
        and report["measurement"] == measured,
        "support_transition_source.original_generation_and_measurement",
    )
    registrations, entries = inputs["registrations"], inputs["entries"]
    require(
        len(registrations) == len(entries) == generation["registered_session_count"] == 8
        and generation["registered_labels"]
        == [row["label"] for row in registrations]
        == [entry["label"] for entry in entries]
        == list(LABELS)
        and registrations == report["registrations"]
        and len({row["id"] for row in registrations})
        == len({row["session_id"] for row in registrations})
        == 8
        and len({entry["qualification"]["id"] for entry in entries}) == 8
        and Counter(row["profile"] for row in registrations) == {"N": 4, "E": 4},
        "support_transition_source.original_eight_population",
    )
    require(
        measured["registered_denominator"] == 8
        and measured["qualified_count"] == 3
        and measured["known_failure_count"] == 5
        and measured["success_fraction"] == {"numerator": 3, "denominator": 8}
        and measured["conditional_distribution"] is None
        and measured["target_support_witness_established"] is False
        and quotient["qualified_count"] == 3
        and quotient["supported_projection_count"] == 1
        and quotient["assignment_count"] == 1
        and quotient["complete_class_count"] is None
        and quotient["pairs"] == []
        and quotient["all_valid_mapped"] is False
        and quotient["target_witness"]["established"] is False,
        "support_transition_source.old_unresolved_result_preserved",
    )
    old_projections = {row["label"]: row for row in quotient["projections"]}
    old_supports = {row["label"]: row for row in quotient["support_rows"]}
    require(
        len(old_projections) == len(old_supports) == 8,
        "support_transition_source.original_sidecar_inventory",
    )
    new_positions: dict[str, list[int]] = {}
    reused_count = valid_events = valid_admitted = all_events = 0
    qualified_ids, qualified_labels, original_outcomes = [], [], []
    task_fields = (
        "task_group",
        "task_type",
        "task_id",
        "context_id",
        "protocol_id",
        "registry_hash",
    )
    for registration, entry in zip(registrations, entries, strict=True):
        label = entry["label"]
        expected_success = label in QUALIFIED_LABELS
        qualification = entry["qualification"]
        require(
            qualification["qualified"] is expected_success
            and qualification["end_to_end_success"] is expected_success
            and qualification["status"] == ("success" if expected_success else "known_failure"),
            "support_transition_source.original_qualified_domain",
        )
        session, audit, graph, old, support, package = (
            entry[key]
            for key in ("session", "audit", "graph", "old_projection", "old_support", "package")
        )
        for value, kind in (
            (registration, "session_registration"),
            (qualification, "qualification"),
            (old, "panel_quotient_projection"),
            (support, "support_exploration_support"),
            (package, "task_panel_session_package"),
        ):
            identity(value, kind)
        for value, kind in (
            (session, "session"),
            (audit, "session_audit"),
            (graph, "actual_decision_graph"),
        ):
            _public_identity(value, kind)
        profile = registration["profile"]
        require(
            entry["registration"] == registration
            and registration["run_condition_id"] == generation["id"]
            and registration["profile_id"] == generation["profiles"][profile]["id"]
            and registration["model_configuration_id"]
            == qualification["model_configuration_id"]
            == generation["configurations"][profile]["id"]
            and qualification["registration_id"] == registration["id"]
            and qualification["registered_session_id"] == registration["session_id"]
            and qualification["session_id"] == session["id"] == audit["session_id"]
            and qualification["domain_audit_id"] == audit["id"]
            and qualification["domain_audit"] == audit
            and audit["actual_decision_graph"] == graph
            and entry["old_finite_projection"] == audit["finite_projection"]
            and old == old_projections[label]
            and support == old_supports[label]
            and entry["old_behavior"] == old["behavior_projection"]
            and old["qualification_id"] == support["qualification_id"] == qualification["id"]
            and old["registration_id"] == support["registration_id"] == registration["id"]
            and old["session_id"] == support["session_id"] == session["id"]
            and old["generation_condition_id"] == generation["id"]
            and old["rule_id"] == OLD_RULE_ID
            and old["source_domain_audit"] == audit
            and old["source_actual_graph_id"] == graph["id"]
            and old["source_non_accept_ledger"] == graph["non_accept_event_ledger"]
            and support["projection_id"] == old["id"]
            and support["source_actual_graph_id"] == graph["id"]
            and support["qualified"] is expected_success
            and package["qualification_id"] == qualification["id"]
            and package["registration_id"] == registration["id"]
            and package["session_id"] == session["id"]
            and package["positive_eligible"] is expected_success
            and package["complete"] is expected_success
            and all(
                registration[key] == qualification[key] == generation[key] for key in task_fields
            ),
            "support_transition_source.original_parent_bindings",
        )
        require(
            qualification["evidence_complete"] is True
            and qualification["model_origin_verified"] is True,
            "support_transition_source.original_complete_model_evidence",
        )
        events = session["events"]
        require(
            [event["sequence"] for event in events] == list(range(len(events)))
            and len(events)
            == qualification["provider_attempt_count"]
            == qualification["runtime_submission_count"]
            and all(
                event["request"]["context"] == generation["original_context"] for event in events
            ),
            "support_transition_source.original_event_inventory",
        )
        rejected = [event for event in events if event["receipt"]["admitted"] is False]
        ledger = graph["non_accept_event_ledger"]
        require(
            len(ledger) == len(rejected)
            and all(
                row["sequence"] == event["sequence"]
                and row["parsed"] == event["parsed"]
                and row["error_code"] == event["receipt"]["error_code"]
                and row["raw_sha256"] == event["submission"]["raw_sha256"]
                for row, event in zip(ledger, rejected, strict=True)
            ),
            "support_transition_source.original_nonaccept_ledger",
        )
        all_events += len(events)
        if expected_success:
            qualified_ids.append(qualification["id"])
            qualified_labels.append(label)
            admitted = [event for event in events if event["receipt"]["admitted"] is True]
            valid_events += len(events)
            valid_admitted += len(admitted)
            require(
                len(admitted) == package["expected_units"] == package["consumable_units"] == 7
                and [unit["submission_id"] for unit in package["units"]]
                == [event["submission"]["id"] for event in admitted]
                and support["proof_verified"] is True
                and support["support"]
                == ("disclosed_total" if label == "E04" else "reconstructed_total")
                and old["status"] == ("supported" if label == "E04" else "undetermined")
                and old["supported"] is (label == "E04"),
                "support_transition_source.original_valid_support_and_packages",
            )
            annotations = old["interpretation_ledger"]
            require(
                [row["sequence"] for row in annotations]
                == [event["sequence"] for event in rejected],
                "support_transition_source.complete_old_interpretation_ledger",
            )
            unresolved = [
                row["sequence"] for row in annotations if row["disposition"] == "undetermined"
            ]
            if unresolved:
                new_positions[label] = unresolved
            reused_count += sum(row["disposition"] != "undetermined" for row in annotations)
        else:
            require(
                len(events) == 32
                and qualification["reason"] == "submission_budget_exhausted"
                and session["final"] is None
                and old["status"] == "ineligible"
                and old["supported"] is False
                and old["behavior_projection"] is None
                and support["support"] == "ineligible"
                and package["units"] == [],
                "support_transition_source.failed_not_promoted",
            )
        original_outcomes.append(
            {
                "label": label,
                "profile": profile,
                "profile_id": registration["profile_id"],
                "model_configuration_id": registration["model_configuration_id"],
                "registration_id": registration["id"],
                "qualification_id": qualification["id"],
                "session_id": session["id"],
                "qualified": qualification["qualified"],
                "status": qualification["status"],
                "end_to_end_success": qualification["end_to_end_success"],
                "old_projection_id": old["id"],
                "old_projection_status": old["status"],
                "old_support_id": support["id"],
                "package_id": package["id"],
            }
        )
    require(
        tuple(qualified_labels) == QUALIFIED_LABELS
        and new_positions == NEW_UNDETERMINED_SEQUENCES
        and valid_events == 42
        and valid_admitted == 21
        and reused_count == 14
        and all_events == report["provider_attempt_count"] == 202,
        "support_transition_source.fixed_original_partition",
    )
    refs = inputs["representation_references"]
    identity(refs, "support_transition_representation_references")
    require(
        refs["generation_condition_id"] == generation["id"]
        and refs["candidate_count"] == refs["token_record_count"] == 21
        and len(set(refs["candidate_ids"])) == len(set(refs["token_record_ids"])) == 21
        and refs["registered_package_count"] == 8
        and refs["complete_package_count"] == 3
        and refs["candidate_ids"]
        == [unit["candidate_id"] for entry in entries for unit in entry["package"]["units"]]
        and refs["token_record_ids"]
        == [unit["token_record_id"] for entry in entries for unit in entry["package"]["units"]],
        "support_transition_source.original_representation_references",
    )
    return record(
        "support_transition_source_binding_checks",
        original_generation_condition_id=generation["id"],
        original_generation_rule_id=OLD_RULE_ID,
        original_report_id=report["id"],
        original_quotient_id=quotient["id"],
        original_measurement_id=measured["id"],
        old_comparison_contract_id=contract["id"],
        registration_ids=[row["id"] for row in registrations],
        qualification_ids=[entry["qualification"]["id"] for entry in entries],
        qualified_qualification_ids=qualified_ids,
        qualified_labels=qualified_labels,
        session_ids=[entry["session"]["id"] for entry in entries],
        graph_ids=[entry["graph"]["id"] for entry in entries],
        old_projection_ids=[entry["old_projection"]["id"] for entry in entries],
        old_support_ids=[entry["old_support"]["id"] for entry in entries],
        package_ids=[entry["package"]["id"] for entry in entries],
        frozen_outcomes=original_outcomes,
        profile_ids={name: profile["id"] for name, profile in generation["profiles"].items()},
        model_configuration_ids={
            name: config["id"] for name, config in generation["configurations"].items()
        },
        registered_session_count=8,
        qualified_session_count=3,
        known_failure_count=5,
        qualified_original_event_count=42,
        qualified_admitted_event_count=21,
        qualified_unadmitted_event_count=21,
        all_original_event_count=202,
        original_supported_projection_count=1,
        newly_interpreted_sequences=new_positions,
        newly_interpreted_display_turns={
            label: [index + 1 for index in indices] for label, indices in new_positions.items()
        },
        newly_interpreted_event_count=7,
        already_interpreted_event_count=14,
        new_interpretation_positions_are_requested_scope_not_results=True,
        new_event_interpretation_performed=False,
        representation_references_id=refs["id"],
        generation_condition_modified=False,
        qualifications_recomputed=False,
        actual_support_recomputed=False,
        old_projection_recomputed=False,
        provider_calls=0,
        runtime_executions=0,
        operation_executions=0,
        tokenizer_loads=0,
        tokenizations=0,
        token_arrays_decoded=False,
        cpu_arrays_loaded=False,
    )


def load_inputs(root: Path) -> dict[str, Any]:
    root = root.resolve()
    anchor = source_anchor(root)
    members = {item["path"]: item for item in anchor["members"]}

    def load(relative: str) -> Any:
        return _load(root, SOURCE_ROOT + "/" + relative, members)

    generation = load("preparation/condition.json")
    registrations = load("preparation/registrations.json")
    require(
        registrations == load("execution/registrations.json"),
        "support_transition_source.registration_copies",
    )
    report = load("execution/report.json")
    require(
        report == load("execution/analysis/report.json"), "support_transition_source.report_copies"
    )
    quotient = load("execution/analysis/quotient.json")
    packages = load("execution/analysis/session_packages.json")
    old_projections = {row["label"]: row for row in quotient["projections"]}
    old_supports = {row["label"]: row for row in quotient["support_rows"]}
    by_package = {row["label"]: row for row in packages["rows"]}
    qualified_inventory = load("execution/qualifications.json")
    entries = []
    for registration in registrations:
        label = registration["label"]
        require(label in LABELS, "support_transition_source.fixed_label")
        qualification = load(f"execution/sessions/{label}/qualification.json")
        require(
            qualification in qualified_inventory
            and registration == load(f"execution/sessions/{label}/registration.json"),
            "support_transition_source.original_session_copies",
        )
        session = load(f"execution/sessions/{label}/runtime/session.json")
        audit = qualification["domain_audit"]
        old = old_projections[label]
        entries.append(
            {
                "label": label,
                "registration": registration,
                "qualification": qualification,
                "session": session,
                "audit": audit,
                "graph": audit["actual_decision_graph"],
                "old_projection": old,
                "old_behavior": old["behavior_projection"],
                "old_finite_projection": audit["finite_projection"],
                "old_support": old_supports[label],
                "package": by_package[label],
            }
        )
    # These are small metadata/identity sidecars. Do not parse raw candidates or token arrays.
    data = load("execution/analysis/representation_data_binding.json")
    exploration = load("execution/analysis/exploration_representation_binding.json")
    profile_checks = load("execution/analysis/representation_profile_checks.json")
    cpu = load("execution/analysis/cpu_loading.json")
    for value, kind in (
        (packages, "task_panel_session_packages"),
        (data, "task_panel_representation_data_binding"),
        (exploration, "support_exploration_representation_binding"),
        (profile_checks, "support_exploration_representation_profile_checks"),
        (cpu, "task_panel_cpu_loading"),
    ):
        identity(value, kind)
    links = exploration["candidate_links"]
    require(
        data["generation_condition_id"]
        == exploration["generation_condition_id"]
        == generation["id"]
        and exploration["representation_data_binding_id"] == data["id"]
        and exploration["profile_check_id"] == profile_checks["id"]
        and exploration["id"] == report["representation_binding_id"]
        and exploration["session_packages_id"] == packages["id"] == report["packages_id"]
        and exploration["cpu_loading_id"] == cpu["id"] == report["cpu_loading_id"]
        and exploration["candidate_count"]
        == profile_checks["candidate_count"]
        == report["candidate_count"]
        == 21
        and report["token_fit_count"] == cpu["fit_count"] == cpu["loaded_records"] == 21
        and report["token_not_fit_count"] == cpu["not_fit_count"] == 0
        and packages["complete_session_packages"] == exploration["complete_session_packages"] == 3
        and packages["registered_session_count"] == exploration["registered_session_count"] == 8
        and cpu["batch_count"] == 12
        and len(links) == 21
        and data["candidate_ids"] == [link["candidate_id"] for link in links]
        and all(link["actual_profile_prompt_preserved"] is True for link in links),
        "support_transition_source.original_representation_metadata",
    )
    analysis_prefix = SOURCE_ROOT + "/execution/analysis/"
    artifact_ids = {
        "supervision_candidates.json": None,  # Original list has no dataset record identity.
        "token_representations.json": exploration["token_dataset_id"],
        "representation_data_binding.json": data["id"],
        "exploration_representation_binding.json": exploration["id"],
        "representation_profile_checks.json": profile_checks["id"],
        "session_packages.json": packages["id"],
        "cpu_loading.json": cpu["id"],
    }
    refs = record(
        "support_transition_representation_references",
        generation_condition_id=generation["id"],
        original_representation_binding_id=exploration["id"],
        representation_data_binding_id=data["id"],
        representation_policy_id=data["representation_policy_id"],
        token_dataset_id=exploration["token_dataset_id"],
        session_packages_id=packages["id"],
        cpu_loading_id=cpu["id"],
        profile_check_id=profile_checks["id"],
        candidate_ids=data["candidate_ids"],
        token_record_ids=[link["token_record_id"] for link in links],
        package_ids=[row["id"] for row in packages["rows"]],
        candidate_profile_links=links,
        candidate_count=21,
        token_record_count=21,
        registered_package_count=8,
        complete_package_count=3,
        cpu_batch_count=12,
        artifact_files=[
            {**members[analysis_prefix + name], "record_id": ref_id}
            for name, ref_id in artifact_ids.items()
        ],
        cpu_binary_files=[
            item
            for item in anchor["members"]
            if item["path"].startswith(analysis_prefix + "cpu_batches/")
        ],
        original_raw_candidate_file_is_json_list=True,
        original_arrays_bound_by_published_blob_and_sha256=True,
        raw_candidate_records_parsed=False,
        token_arrays_decoded=False,
        cpu_arrays_loaded=False,
        tokenizer_loaded=False,
        new_tokenization=False,
        old_prompt_profile_provenance_preserved=True,
    )
    inputs = {
        "root": root,
        "source_directory": root / SOURCE_ROOT,
        "source_anchor": anchor,
        "generation_condition": generation,
        "old_comparison_contract": load("preparation/comparison_contract.json"),
        "old_report": report,
        "old_quotient": quotient,
        "old_measurement": load("execution/analysis/measurement.json"),
        "registrations": registrations,
        "entries": entries,
        "representation_references": refs,
    }
    inputs["source_binding_checks"] = validate_inputs(inputs)
    return inputs
