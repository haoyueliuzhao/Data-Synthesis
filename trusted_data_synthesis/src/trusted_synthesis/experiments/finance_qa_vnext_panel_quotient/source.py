"""Bind the published sixteen-session panel without replaying any prior computation.

Git blob bytes are the historical authority.  Local checks join already accepted
Session/qualification/graph/package records; they neither decide qualification
again nor execute a source scanner, Runtime, Operation, tokenizer or tensor loader.
Original supervision arrays are referenced by exact file hashes, not materialized
as a new dataset by this measurement-only stage.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash

from ..finance_qa_vnext_model_execution.models import identity, read_json, record, require, sha

PARENT_COMMIT = "d64357ec850a98f31c6fe58013a0ad33b77d87f7"
SOURCE_ROOT = (
    "trusted_data_synthesis/artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906"
)
GROUPS = ("F", "C", "G", "A", "D", "R", "B", "S")
LABELS = tuple(f"{group}{round_number:02d}" for round_number in (1, 2) for group in GROUPS)
NEW_INTERPRETATION_LABELS = ("D01", "B01", "S02")
HISTORY_PREFIXES = (
    "qa_vnext_integration",
    "qa_vnext_model_execution",
    "qa_vnext_update_calibration",
    "qa_vnext_repaired_full_task",
    "qa_vnext_action_branch",
    "qa_vnext_length_adaptation",
    "qa_vnext_task_panel",
)
SOURCE_FILE_COUNT = 2771
SOURCE_BYTE_COUNT = 196_734_857
HISTORY_FILE_COUNT = 12_947
HISTORY_BYTE_COUNT = 647_963_136
PREDECESSOR_PYTHON_COUNT = 888
GENERATION_CONDITION_ID = (
    "qa_vnext_model_execution_task_panel_condition:"
    "eef6edd96efb988b605a80108e9331e31d6e6e7c78624bb6bb8d6d2818568355"
)
PANEL_REPORT_ID = (
    "qa_vnext_model_execution_task_panel_report:"
    "3173425beb07bccba47b47aafa53229817bad07c613f9030b6eb140399bb987a"
)


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args])


def _regular_bytes(root: Path, relative: str) -> bytes:
    path = root / relative
    require(
        not Path(relative).is_absolute()
        and ".." not in Path(relative).parts
        and path.resolve().is_relative_to(root.resolve())
        and path.is_file()
        and not path.is_symlink(),
        "quotient_source.regular_file",
    )
    return path.read_bytes()


def _published_files(root: Path, prefix: str, *, python_only: bool = False) -> list[dict[str, Any]]:
    tree = git(root, "ls-tree", "-r", "-z", PARENT_COMMIT, "--", prefix)
    files = []
    for item in tree.split(b"\0"):
        if not item:
            continue
        metadata, relative_bytes = item.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        relative = relative_bytes.decode()
        if python_only and not relative.endswith(".py"):
            continue
        require(mode == "100644" and kind == "blob", "quotient_source.published_regular_blob")
        raw = _regular_bytes(root, relative)
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(actual == oid, "quotient_source.published_bytes_changed")
        files.append(
            {"path": relative, "byte_count": len(raw), "sha256": sha(raw), "git_blob_id": oid}
        )
    require(bool(files), "quotient_source.empty_published_tree")
    return files


def source_anchor(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files = _published_files(root, SOURCE_ROOT)
    directory = root / SOURCE_ROOT
    actual = set()
    for path in directory.rglob("*"):
        require(not path.is_symlink(), "quotient_source.source_symlink")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    require(actual == {item["path"] for item in files}, "quotient_source.exact_source_members")
    require(
        len(files) == SOURCE_FILE_COUNT
        and sum(item["byte_count"] for item in files) == SOURCE_BYTE_COUNT,
        "quotient_source.fixed_source_directory",
    )
    return record(
        "panel_quotient_source_anchor",
        commit=PARENT_COMMIT,
        directory=SOURCE_ROOT,
        files=files,
        file_count=len(files),
        byte_count=sum(item["byte_count"] for item in files),
        all_bytes_match_published_git_blobs=True,
    )


def preserved_sources(root: Path) -> dict[str, Any]:
    """Allow new wrappers while checking all 888 predecessor Python source bytes."""
    files = _published_files(root.resolve(), "trusted_data_synthesis/src", python_only=True)
    require(len(files) == PREDECESSOR_PYTHON_COUNT, "quotient_source.predecessor_python_count")
    return record(
        "panel_quotient_source_preservation",
        predecessor_commit=PARENT_COMMIT,
        files=files,
        file_count=len(files),
        all_predecessor_sources_byte_identical=True,
        old_qualification_projection_or_representation_modified=False,
    )


def _load(root: Path, relative: str, members: dict[str, dict[str, Any]]) -> Any:
    require(relative in members, "quotient_source.unanchored_input")
    raw = _regular_bytes(root, relative)
    member = members[relative]
    require(
        len(raw) == member["byte_count"] and sha(raw) == member["sha256"],
        "quotient_source.changed_after_anchor",
    )
    return read_json(raw)


def history_inventory(root: Path) -> dict[str, Any]:
    """Verify the seven prior artifact prefixes, never rewriting their inventories."""
    root = root.resolve()
    anchor = source_anchor(root)
    members = {item["path"]: item for item in anchor["files"]}
    prior = _load(root, SOURCE_ROOT + "/preparation/history_inventory.json", members)
    identity(prior, "task_panel_history_inventory")
    expected = [
        {"path": item["path"], "byte_count": item["bytes"], "sha256": item["sha256"]}
        for item in prior["members"]
    ] + [{key: item[key] for key in ("path", "byte_count", "sha256")} for item in anchor["files"]]
    indexed = {item["path"]: item for item in expected}
    require(len(indexed) == len(expected), "quotient_source.history_duplicate")
    actual = set()
    for prefix in HISTORY_PREFIXES:
        directory = root / "trusted_data_synthesis/artifacts" / prefix
        require(directory.is_dir(), "quotient_source.history_directory_missing")
        for path in directory.rglob("*"):
            require(not path.is_symlink(), "quotient_source.history_symlink")
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            actual.add(relative)
            require(relative in indexed, "quotient_source.history_unexpected_member")
            # The complete panel was already read against the published commit above.
            if relative in members:
                continue
            raw = _regular_bytes(root, relative)
            require(
                len(raw) == indexed[relative]["byte_count"]
                and sha(raw) == indexed[relative]["sha256"],
                "quotient_source.prior_history_changed",
            )
    require(actual == set(indexed), "quotient_source.history_missing_member")
    require(
        len(expected) == HISTORY_FILE_COUNT
        and sum(item["byte_count"] for item in expected) == HISTORY_BYTE_COUNT,
        "quotient_source.fixed_history_inventory",
    )
    return record(
        "panel_quotient_history_inventory",
        predecessor_commit=PARENT_COMMIT,
        original_panel_anchor_id=anchor["id"],
        earlier_history_inventory_id=prior["id"],
        files=sorted(expected, key=lambda item: item["path"]),
        file_count=len(expected),
        byte_count=sum(item["byte_count"] for item in expected),
        all_historical_bytes_unchanged=True,
    )


def _public_identity(value: dict[str, Any], kind: str) -> None:
    prefix = f"finance_qa_vnext_{kind}:"
    require(
        isinstance(value, dict)
        and value.get("schema_version") == f"finance_qa_vnext_{kind}.v2"
        and value.get("id")
        == strict_canonical_hash(
            {key: item for key, item in value.items() if key != "id"}, prefix=prefix
        ),
        "quotient_source.identity." + kind,
    )


def validate_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Join frozen records only; no numerical, admission, graph or eligibility replay."""
    registrations, entries = inputs["registrations"], inputs["entries"]
    require(
        len(registrations) == len(entries) == 16
        and [item["label"] for item in registrations] == list(LABELS)
        and [item["label"] for item in entries] == list(LABELS),
        "quotient_source.fixed_registered_denominator",
    )
    require(
        len({item["id"] for item in registrations}) == 16
        and len({item["session_id"] for item in registrations}) == 16
        and len({item["qualification"]["id"] for item in entries}) == 16,
        "quotient_source.distinct_original_records",
    )
    condition, report, measured = inputs["condition"], inputs["report"], inputs["measurement"]
    identity(condition, "task_panel_condition")
    identity(report, "task_panel_report")
    identity(measured, "task_panel_measurement")
    require(
        condition["id"] == GENERATION_CONDITION_ID
        and report["id"] == PANEL_REPORT_ID
        and report["condition_id"] == condition["id"]
        and report["measurement"] == measured
        and measured["registered_session_denominator"] == 16
        and measured["fixed_task_denominator"] == 8
        and measured["success_numerator"] == 15
        and measured["qualified_mapped"] == 12,
        "quotient_source.original_condition_and_measurement",
    )
    require(
        len(inputs["coverage"]) == 11
        and sum(row["selected_for_model_population"] for row in inputs["coverage"]) == 8,
        "quotient_source.original_coverage",
    )
    rejected_counts: dict[str, int] = {}
    success_labels, supported_labels, event_counts = [], [], []
    valid_event_count = valid_admitted_count = 0
    report_rows = {row["label"]: row for row in report["session_rows"]}
    for ordinal, (registration, entry) in enumerate(zip(registrations, entries, strict=True)):
        label = entry["label"]
        qualification = entry["qualification"]
        expected_success = label != "S01"
        require(
            qualification["qualified"] is expected_success
            and qualification["end_to_end_success"] is expected_success
            and qualification["status"] == ("success" if expected_success else "known_failure"),
            "quotient_source.original_success_domain",
        )
        identity(registration, "session_registration")
        identity(qualification, "qualification")
        session, audit, graph, package = (
            entry[key] for key in ("session", "audit", "graph", "package")
        )
        _public_identity(session, "session")
        _public_identity(audit, "session_audit")
        _public_identity(graph, "actual_decision_graph")
        identity(package, "task_panel_session_package")
        context = condition["task_contexts"][registration["task_group"]]
        _public_identity(context, "context")
        require(
            entry["registration"] == registration
            and registration["ordinal"] == ordinal
            and registration["run_condition_id"] == condition["id"]
            and registration["context_id"] == context["id"]
            and registration["task_id"] == context["task_id"]
            and qualification["registration_id"] == registration["id"]
            and qualification["registered_session_id"] == registration["session_id"]
            and qualification["id"] == report_rows[label]["qualification_id"]
            and qualification["session_id"] == session["id"] == audit["session_id"]
            and qualification["domain_audit_id"] == audit["id"]
            and qualification["domain_audit"] == audit
            and audit["actual_decision_graph"] == graph
            and audit["finite_projection"] == entry["old_projection"]
            and all(
                qualification[key] == registration[key]
                for key in (
                    "context_id",
                    "task_id",
                    "task_group",
                    "task_type",
                    "protocol_id",
                    "registry_hash",
                    "model_configuration_id",
                )
            )
            and session["context_id"] == registration["context_id"]
            and session["protocol_id"] == registration["protocol_id"]
            and package["registration_id"] == registration["id"]
            and package["registered_session_id"] == registration["session_id"]
            and package["session_id"] == session["id"]
            and package["qualification_id"] == qualification["id"]
            and package["positive_eligible"] is expected_success
            and package["complete"] is expected_success,
            "quotient_source.original_parent_bindings",
        )
        require(
            qualification["evidence_complete"] is True
            and qualification["model_origin_verified"] is True
            and qualification["quotient_assignment_id"] is None,
            "quotient_source.accepted_qualification_reference",
        )
        events = session["events"]
        require(
            [event["sequence"] for event in events] == list(range(len(events)))
            and qualification["runtime_submission_count"]
            == qualification["provider_attempt_count"]
            == len(events)
            and all(event["request"]["context"] == context for event in events),
            "quotient_source.complete_original_events",
        )
        rejected = [event for event in events if event["receipt"]["admitted"] is False]
        ledger = graph["non_accept_event_ledger"]
        require(
            len(ledger) == len(rejected)
            and all(
                row["kind"] == "unadmitted_submission"
                and row["sequence"] == event["sequence"]
                and row["parsed"] == event["parsed"]
                and row["error_code"] == event["receipt"]["error_code"]
                and row["raw_sha256"] == event["submission"]["raw_sha256"]
                for row, event in zip(ledger, rejected, strict=True)
            ),
            "quotient_source.original_nonaccept_ledger",
        )
        admitted_actions = [event for event in events if event.get("execution") is not None]
        require(
            len(graph["nodes"]) == len(graph["event_bindings"]) == len(admitted_actions)
            and {row["sequence"] for row in graph["event_bindings"]}
            == {event["sequence"] for event in admitted_actions},
            "quotient_source.original_graph_event_inventory",
        )
        for binding in graph["event_bindings"]:
            event = events[binding["sequence"]]
            require(
                binding["action_submission_id"] == event["submission"]["id"]
                and binding["receipt_id"] == event["receipt"]["id"]
                and binding["execution_id"] == event["execution"]["id"]
                and binding["observation_id"] == event["observation"]["id"],
                "quotient_source.original_graph_event_binding",
            )
        event_counts.append(len(events))
        if expected_success:
            success_labels.append(label)
            valid_event_count += len(events)
            admitted = [event for event in events if event["receipt"]["admitted"] is True]
            valid_admitted_count += len(admitted)
            require(
                package["expected_units"]
                == package["consumable_units"]
                == len(package["units"])
                == len(admitted)
                and [unit["submission_id"] for unit in package["units"]]
                == [event["submission"]["id"] for event in admitted],
                "quotient_source.original_package_denominator",
            )
            if rejected:
                rejected_counts[label] = len(rejected)
            expected_supported = label not in NEW_INTERPRETATION_LABELS
            require(
                qualification["projection_status"]
                == ("supported" if expected_supported else "undetermined")
                and audit["projection_supported"] is expected_supported,
                "quotient_source.original_projection_domain",
            )
            if expected_supported:
                supported_labels.append(label)
        else:
            require(
                qualification["reason"] == "submission_budget_exhausted"
                and qualification["qa_valid"] is None
                and session["final"] is None
                and len(events) == 32
                and len(rejected) == 30
                and package["units"] == []
                and package["expected_units"] is None,
                "quotient_source.failure_not_promoted",
            )
    require(
        len(success_labels) == 15
        and len(supported_labels) == 12
        and rejected_counts == {"D01": 1, "B01": 1, "S02": 5}
        and valid_event_count == 120
        and valid_admitted_count == 113
        and sum(event_counts) == report["provider_attempt_count"] == 152,
        "quotient_source.original_event_partition",
    )
    pairs = inputs["old_pairs"]
    require(
        len(pairs) == 5
        and {pair["task_group"] for pair in pairs} == {"F", "C", "G", "A", "R"}
        and all(pair["comparison"]["relation"] == "equivalent" for pair in pairs),
        "quotient_source.original_five_pairs",
    )
    for pair in pairs:
        identity(pair, "finite_pair")
        _public_identity(pair["comparison"], "finite_comparison")
        left = next(e for e in entries if e["qualification"]["id"] == pair["left_qualification_id"])
        right = next(
            e for e in entries if e["qualification"]["id"] == pair["right_qualification_id"]
        )
        require(
            pair["comparison"]["left_audit_id"] == left["audit"]["id"]
            and pair["comparison"]["right_audit_id"] == right["audit"]["id"]
            and left["label"] in supported_labels
            and right["label"] in supported_labels,
            "quotient_source.original_pair_parents",
        )
    references = inputs["representation_references"]
    identity(references, "panel_quotient_representation_references")
    require(
        references["candidate_count"] == references["token_record_count"] == 113
        and len(set(references["candidate_ids"])) == 113
        and len(set(references["token_record_ids"])) == 113
        and references["complete_package_count"] == 15
        and references["registered_package_count"] == 16
        and references["generation_condition_id"] == condition["id"]
        and references["token_dataset_id"] == report["token_dataset_id"]
        and references["representation_data_binding_id"] == report["representation_data_binding_id"]
        and references["representation_policy_id"] == report["representation_policy_id"]
        and references["candidate_ids"]
        == [unit["candidate_id"] for entry in entries for unit in entry["package"]["units"]]
        and references["token_record_ids"]
        == [unit["token_record_id"] for entry in entries for unit in entry["package"]["units"]],
        "quotient_source.original_representation_references",
    )
    return record(
        "panel_quotient_source_binding_checks",
        original_generation_condition_id=condition["id"],
        original_panel_report_id=report["id"],
        registration_ids=[item["id"] for item in registrations],
        qualification_ids=[entry["qualification"]["id"] for entry in entries],
        session_ids=[entry["session"]["id"] for entry in entries],
        graph_ids=[entry["graph"]["id"] for entry in entries],
        registered_sessions=16,
        qualified_sessions=15,
        original_supported_projections=12,
        new_interpretation_labels=list(NEW_INTERPRETATION_LABELS),
        qualified_nonaccept_event_counts=rejected_counts,
        qualified_original_event_count=valid_event_count,
        qualified_admitted_event_count=valid_admitted_count,
        all_original_event_count=sum(event_counts),
        representation_references_id=references["id"],
        qualification_recomputed=False,
        graph_rebuilt=False,
        provider_calls=0,
        runtime_executions=0,
        operation_executions=0,
        tokenizer_loads=0,
        tokenizations=0,
    )


def load_inputs(root: Path) -> dict[str, Any]:
    root = root.resolve()
    anchor = source_anchor(root)
    members = {item["path"]: item for item in anchor["files"]}

    def load(relative: str) -> Any:
        return _load(root, SOURCE_ROOT + "/" + relative, members)

    registrations = load("preparation/registrations.json")
    require(registrations == load("execution/registrations.json"), "quotient_source.registrations")
    report = load("execution/report.json")
    require(
        report == load("execution/analysis/report.json"), "quotient_source.original_report_copies"
    )
    packages = load("execution/analysis/session_packages.json")
    identity(packages, "task_panel_session_packages")
    by_label = {row["label"]: row for row in packages["rows"]}
    entries = []
    for registration in registrations:
        label = registration["label"]
        require(label in LABELS and label in by_label, "quotient_source.original_session_label")
        session = load(f"execution/sessions/{label}/runtime/session.json")
        qualification = load(f"execution/sessions/{label}/qualification.json")
        require(
            qualification == load(f"execution/analysis/qualifications/{label}.json")
            and registration == load(f"execution/sessions/{label}/registration.json"),
            "quotient_source.original_session_copies",
        )
        audit = qualification["domain_audit"]
        entries.append(
            {
                "label": label,
                "registration": registration,
                "session": session,
                "qualification": qualification,
                "audit": audit,
                "graph": audit["actual_decision_graph"],
                "old_projection": audit["finite_projection"],
                "package": by_label[label],
            }
        )
    # Read existing JSON metadata, not tokenize or construct model-consumption tensors.
    original = {
        name: load("execution/analysis/" + filename)
        for name, filename in {
            "candidates": "supervision_candidates.json",
            "tokens": "token_representations.json",
            "binding": "representation_binding.json",
            "cpu": "cpu_loading.json",
        }.items()
    }
    candidates, tokens, binding, cpu = (
        original[key] for key in ("candidates", "tokens", "binding", "cpu")
    )
    identity(binding, "task_panel_representation_data_binding")
    candidate_ids = [row["id"] for row in candidates["rows"]]
    token_ids = [row["id"] for row in tokens["records"]]
    require(
        len(candidate_ids) == candidates["candidate_count"] == tokens["candidate_count"] == 113
        and tokens["fit_count"] == 113
        and tokens["not_fit_count"] == 0
        and tokens["id"] == report["token_dataset_id"]
        and binding["id"] == report["representation_data_binding_id"]
        and candidates["generation_condition_id"] == report["condition_id"]
        and candidate_ids == binding["candidate_ids"]
        and [row["row_id"] for row in tokens["records"]] == candidate_ids
        and cpu["id"] == report["cpu_loading_id"]
        and cpu["batch_count"] == 64,
        "quotient_source.original_representation_metadata",
    )
    artifact_ids = {
        "supervision_candidates.json": candidates["id"],
        "token_representations.json": tokens["id"],
        "representation_binding.json": binding["id"],
        "session_packages.json": packages["id"],
        "cpu_loading.json": cpu["id"],
    }
    artifact_refs = []
    analysis_prefix = SOURCE_ROOT + "/execution/analysis/"
    for name, value in artifact_ids.items():
        item = members[analysis_prefix + name]
        artifact_refs.append({**item, "id": value})
    cpu_files = [
        item
        for item in anchor["files"]
        if item["path"].startswith(analysis_prefix + "cpu_batches/")
    ]
    references = record(
        "panel_quotient_representation_references",
        generation_condition_id=report["condition_id"],
        representation_policy_id=report["representation_policy_id"],
        representation_data_binding_id=binding["id"],
        candidate_dataset_id=candidates["id"],
        token_dataset_id=tokens["id"],
        session_packages_id=packages["id"],
        cpu_loading_id=cpu["id"],
        candidate_ids=candidate_ids,
        token_record_ids=token_ids,
        package_ids=[row["id"] for row in packages["rows"]],
        candidate_count=113,
        token_record_count=113,
        registered_package_count=16,
        complete_package_count=15,
        cpu_batch_count=64,
        artifact_files=artifact_refs,
        cpu_binary_files=cpu_files,
        original_arrays_bound_by_published_file_bytes=True,
        tokenization_performed=False,
        tokenizer_loaded=False,
        cpu_batches_loaded=False,
        new_supervision_dataset_created=False,
    )
    pair_record = load("execution/analysis/finite_comparisons.json")
    identity(pair_record, "task_panel_finite_comparisons")
    inputs = {
        "root": root,
        "source_directory": root / SOURCE_ROOT,
        "source_anchor": anchor,
        "registrations": registrations,
        "condition": load("preparation/condition.json"),
        "report": report,
        "measurement": load("execution/analysis/measurement.json"),
        "coverage": load("preparation/coverage.json"),
        "entries": entries,
        "old_pairs": pair_record["pairs"],
        "old_pair_record": pair_record,
        "representation_references": references,
    }
    inputs["source_binding_checks"] = validate_inputs(inputs)
    return inputs
