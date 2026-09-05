"""Freeze and persist one zero-Provider measurement of the existing six sessions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    source_group,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter

from .comparison import compare_all
from .controls import run_controls
from .independent import audit_measurement
from .inputs import assert_unchanged, load_inputs
from .measurement import build_partition, measure_empirical
from .models import (
    DIRECTIVE,
    LABELS,
    REVIEW_BYTES,
    REVIEW_SHA256,
    STAGE,
    measurement_contract,
    record,
    require,
    sha,
)
from .projection import project_session

SOURCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_share_quotient_measurement/"
    + name
    for name in (
        "__init__.py",
        "models.py",
        "inputs.py",
        "projection.py",
        "comparison.py",
        "measurement.py",
        "controls.py",
        "independent.py",
        "preflight.py",
    )
)
REFERENCE_PATHS = (
    "trusted_data_synthesis/src/trusted_synthesis/canonical_json.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_finite_comparison/inputs.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_fixed_fixture/runtime.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_share_model_pilot/independent.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_part_whole_share/comparison.py",
    "trusted_data_synthesis/docs/finance_qa_vnext_public_reasoning_semantics_allowed_behavior_and_quotient_contract_design.md",
)
DEFAULT_DIRECTORY = (
    "trusted_data_synthesis/artifacts/qa_reasoning_share_quotient_measurement/"
    "finance_qa_vnext_six_session_model_trajectory_finite_quotient_measurement_v1_20260906"
)


def _authority(root: Path, commit: str, tree: str) -> dict[str, Any]:
    return record(
        "source_authority",
        implementation=source_group(root, commit, tree, SOURCE_PATHS),
        references=source_group(root, commit, tree, REFERENCE_PATHS),
        declared_source_members_only=True,
        full_transitive_runtime_closure_claimed=False,
        source_freeze_precedes_formal_artifact_materialization=True,
        known_data_development_probes_are_blind_confirmation=False,
        previous_runtime_comparison_or_adapter_executed=False,
    )


def _authorization(review: bytes, rules: dict[str, Any]) -> dict[str, Any]:
    require(
        len(review) == REVIEW_BYTES and sha(review) == REVIEW_SHA256, "preflight.review_authority"
    )
    return record(
        "authorization",
        stage=STAGE,
        current_operator_directive=DIRECTIVE,
        current_operator_directive_bytes=len(DIRECTIVE.encode()),
        current_operator_directive_sha256=sha(DIRECTIVE.encode()),
        external_review_bytes=len(review),
        external_review_sha256=sha(review),
        predecessor_audit="PASS_AS_SCOPED",
        mandatory_revision=False,
        authority=(
            "current operator instruction to conduct the recommended zero-execution measurement"
        ),
        external_review_itself_is_online_authorization=False,
        measurement_contract_id=rules["id"],
        existing_model_sessions=6,
        qualified_projection_candidates=5,
        same_task_unordered_pairs=10,
        provider_calls=0,
        credential_reads=0,
        new_model_sessions=0,
        new_candidate_runtime_executions=0,
        new_source_or_task=0,
        GPU_jobs=0,
        old_mainline="remains_paused",
        contribution_or_training_authorized=False,
    )


def _cohort(inputs: dict[str, Any]) -> dict[str, Any]:
    return record(
        "cohort",
        parent_freeze_id=inputs["parent_freeze"]["id"],
        pilot_registration_id=inputs["pilot_registration"]["id"],
        sessions=[
            {
                "label": session["label"],
                "session_id": session["declaration"]["id"],
                "qualification_id": session["qualification"]["id"],
                "session_manifest_id": session["records"]["manifest"]["id"],
                "session_stop_id": session["records"]["stop"]["id"],
                "evidence_complete": session["qualification"]["evidence_complete"],
                "protocol_valid": session["qualification"]["protocol_valid"],
                "qa_valid": session["qualification"]["qa_valid"],
                "Y": session["qualification"]["Y"],
                "qualified": session["qualification"]["qualified"],
                "terminal_reason": session["qualification"]["terminal_reason"],
                "historical_provider_attempts": session["qualification"]["provider_attempts"],
                "original_submission_count": len(session["records"]["events"]),
            }
            for session in inputs["sessions"]
        ],
        original_qualification_reused_not_reexecuted=True,
        failures_remain_in_six_denominator=True,
        mocks_old_fixtures_and_new_controls_are_excluded=True,
    )


def _ledger(projections: list[dict[str, Any]]) -> dict[str, Any]:
    return record(
        "correction_ledger",
        sessions=[
            {
                "label": projection["label"],
                "session_id": projection["session_id"],
                "projection_id": projection["id"],
                "status": projection["status"],
                "corrections": projection["corrections"],
                "event_decisions": projection["event_decisions"],
                "statistics": projection["statistics"],
            }
            for projection in projections
        ],
        original_submissions=sum(
            projection["statistics"]["original_submissions"] for projection in projections
        ),
        all_rejections=sum(len(projection["corrections"]) for projection in projections),
        reduced_qualified_corrections=sum(
            projection["statistics"]["reduced_corrections"] for projection in projections
        ),
        original_records_deleted_or_rewritten=0,
        rejected_proposed_values_are_not_accepted_claim_revisions=True,
        budget_and_cost_effects_survive_quotient_reduction=True,
    )


def _gates(
    projections: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    partition: dict[str, Any],
    measurement: dict[str, Any],
    controls: dict[str, Any],
    independent: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        (
            "G0",
            "exact historical population and qualification",
            len(projections) == 6
            and measurement["registered_denominator"] == 6
            and measurement["qualified_denominator"] == 5,
        ),
        (
            "G1",
            "finite projection and explicit correction decisions",
            all(projection["status"] in {"mapped", "not_qualified"} for projection in projections)
            and sum(projection["status"] == "mapped" for projection in projections) == 5,
        ),
        (
            "G2",
            "ten comparisons, relation consistency and Assignment",
            len(pairs) == 10
            and partition["complete"]
            and all(partition["relation_checks"].values()),
        ),
        (
            "G3",
            "empirical denominators and isolated measurement validation",
            measurement["complete"]
            and controls["failed"] == 0
            and controls["passed"] == 12
            and independent["passed"],
        ),
    ]
    return record(
        "gate_evaluation",
        gates=[
            {"gate": name, "object": title, "passed": bool(passed)}
            for name, title, passed in checks
        ],
        passed=sum(bool(passed) for _, _, passed in checks),
        failed=sum(not passed for _, _, passed in checks),
        class_count_or_two_routes_is_a_pass_requirement=False,
        all_model_sessions_success_is_a_pass_requirement=False,
    )


def _report(
    inputs: dict[str, Any],
    rules: dict[str, Any],
    authority: dict[str, Any],
    projections: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    partition: dict[str, Any],
    measurement: dict[str, Any],
    controls: dict[str, Any],
    independent: dict[str, Any],
    gates: dict[str, Any],
) -> dict[str, Any]:
    labels = {projection["session_id"]: projection["label"] for projection in projections}
    return record(
        "report",
        stage=STAGE,
        status="finite_quotient_measurement_completed_as_scoped"
        if gates["failed"] == 0
        else "bounded_measurement_undetermined",
        design_status=(
            "measurement-rule instantiation on known frozen trajectories, "
            "not data-blind confirmation"
        ),
        parent_freeze_id=inputs["parent_freeze"]["id"],
        parent_report_id=inputs["parent_report"]["id"],
        source_authority_id=authority["id"],
        measurement_contract_id=rules["id"],
        projection_ids=[projection["id"] for projection in projections],
        pair_ids=[pair["id"] for pair in pairs],
        partition_id=partition["id"],
        empirical_measurement=measurement,
        classes=[
            {
                "state_id": row["state_id"],
                "member_labels": [labels[sid] for sid in row["members"]],
                "member_session_ids": row["members"],
            }
            for row in partition["classes"]
        ],
        observed_finite_quotient_class_count=partition["class_count"],
        pair_results={
            relation: sum(pair["relation"] == relation for pair in pairs)
            for relation in ("equivalent", "different_retained_semantics", "undetermined")
        },
        controls_id=controls["id"],
        independent_validation_id=independent["id"],
        gate_evaluation_id=gates["id"],
        new_provider_calls=0,
        new_model_sessions=0,
        credential_reads=0,
        new_candidate_runtime_executions=0,
        new_source_or_task=0,
        GPU_jobs=0,
        original_qualification_reexecuted=False,
        previous_adapter_audit_rerun=False,
        original_public_submissions=51,
        old_fixture_or_mock_samples_in_denominator=0,
        old_quotient_state_ids_reused=False,
        old_W_share=inputs["parent_report"]["old_W_share"],
        older_compound_task_W=inputs["parent_report"]["older_compound_task_W"],
        new_W_measurement=None,
        population_probabilities=None,
        training_target_pi_t=None,
        contribution_coverage_prior_training_or_student_comparison=None,
        old_mainline="remains_paused",
        next_stage_authorized=False,
    )


def _manifest(writer: DurableArtifactWriter, report: dict[str, Any]) -> dict[str, Any]:
    files = files_at(writer.root)
    members = [
        {"relative_path": path, "sha256": sha(data), "byte_count": len(data)}
        for path, data in sorted(files.items())
    ]
    body = {
        "schema_version": "share_quotient_manifest.v1",
        "members": members,
        "member_count": len(members),
        "member_bytes": sum(member["byte_count"] for member in members),
        "report_id": report["id"],
        "self_excluding": True,
        "artifact_root": strict_canonical_hash(members, prefix="share_quotient_root:"),
    }
    manifest = {
        **body,
        "manifest_id": strict_canonical_hash(body, prefix="share_quotient_manifest:"),
    }
    writer.write_json("artifact_manifest.json", manifest)
    validate_manifest(files_at(writer.root), manifest["manifest_id"], manifest["artifact_root"])
    return manifest


def build_measurement(
    *,
    repo_root: Path,
    external_audit: Path,
    source_commit: str,
    source_tree: str,
    output_directory: Path,
) -> dict[str, Any]:
    root = repo_root.resolve()
    require(not output_directory.exists(), "preflight.output_no_replace")
    inputs = load_inputs(root)
    rules = measurement_contract()
    review = external_audit.read_bytes()
    authorization = _authorization(review, rules)
    authority = _authority(root, source_commit, source_tree)
    writer = DurableArtifactWriter(output_directory)
    writer.create_root()
    writer.write_bytes("external_review.txt", review)
    writer.write_bytes("operator_directive.txt", DIRECTIVE.encode())
    for name, value in (
        ("authorization", authorization),
        ("source_authority", authority),
        ("parent_freeze", inputs["parent_freeze"]),
        ("measurement_contract", rules),
        ("cohort", _cohort(inputs)),
    ):
        writer.write_json(name + ".json", value)
    # Source/rules/input bindings are durable before formal projection materialization.
    projections = [project_session(inputs, session, rules) for session in inputs["sessions"]]
    for projection in projections:
        writer.write_json("projections/" + projection["label"] + ".json", projection)
    writer.write_json("correction_ledger.json", _ledger(projections))
    pairs = compare_all(projections, rules)
    labels = {projection["session_id"]: projection["label"] for projection in projections}
    for index, pair in enumerate(pairs, 1):
        writer.write_json(
            f"pairs/{index:02d}_"
            + labels[pair["left_session_id"]]
            + "_"
            + labels[pair["right_session_id"]]
            + ".json",
            pair,
        )
    partition = build_partition(inputs, rules, projections, pairs)
    writer.write_json("relation_partition.json", partition)
    for index, row in enumerate(partition["classes"], 1):
        writer.write_json(f"states/{index:02d}.json", row["state"])
    for assignment in partition["assignments"]:
        writer.write_json("assignments/" + labels[assignment["session_id"]] + ".json", assignment)
    measurement = measure_empirical(inputs, rules, partition)
    writer.write_json("empirical_measurement.json", measurement)
    controls = run_controls(inputs, rules, projections, pairs, partition)
    for index, control in enumerate(controls["controls"], 1):
        writer.write_json(f"controls/{index:02d}_" + control["name"] + ".json", control)
    writer.write_json("controls.json", controls)
    independent = audit_measurement(inputs, rules, projections, pairs, partition, measurement)
    writer.write_json("independent_validation.json", independent)
    gates = _gates(projections, pairs, partition, measurement, controls, independent)
    writer.write_json("gate_evaluation.json", gates)
    report = _report(
        inputs,
        rules,
        authority,
        projections,
        pairs,
        partition,
        measurement,
        controls,
        independent,
        gates,
    )
    writer.write_json("report.json", report)
    written = files_at(writer.root)
    writer.write_json(
        "persistence.json",
        record(
            "persistence",
            covered_members=[
                {"relative_path": path, "sha256": sha(data), "byte_count": len(data)}
                for path, data in sorted(written.items())
            ],
            write_events=writer.events,
            self_and_manifest_excluded=True,
            create_root_and_files_no_replace=True,
            file_then_directory_fsync=True,
            source_and_rules_written_before_projections=True,
        ),
    )
    manifest = _manifest(writer, report)
    assert_unchanged(root, inputs)
    validation = validate_artifacts(repo_root=root, artifact_directory=writer.root)
    require(validation["passed"], "preflight.persisted_validation")
    files = files_at(writer.root)
    return {
        "report": report,
        "manifest": manifest,
        "artifact_file_count": len(files),
        "artifact_total_bytes": sum(map(len, files.values())),
        "validation": validation,
    }


def validate_artifacts(*, repo_root: Path, artifact_directory: Path) -> dict[str, Any]:
    """Independently verify formal objects and recompute only isolated measurement controls."""
    files = files_at(artifact_directory)
    manifest = json.loads(files["artifact_manifest.json"])
    validate_manifest(files, manifest["manifest_id"], manifest["artifact_root"])

    def read(path: str) -> dict[str, Any]:
        require(path in files, "validation.missing_artifact")
        result = json.loads(files[path])
        require(canonical_json_bytes(result) == files[path], "validation.noncanonical_record")
        if "id" in result:
            identifier = result["id"]
            require(
                strict_canonical_hash(
                    {key: value for key, value in result.items() if key != "id"},
                    prefix=identifier.split(":")[0] + ":",
                )
                == identifier,
                "validation.content_identity",
            )
        return result

    inputs = load_inputs(repo_root)
    rules = read("measurement_contract.json")
    require(rules == measurement_contract(), "validation.rule_substitution")
    require(read("parent_freeze.json") == inputs["parent_freeze"], "validation.parent_freeze")
    require(files["operator_directive.txt"] == DIRECTIVE.encode(), "validation.directive")
    require(
        read("authorization.json") == _authorization(files["external_review.txt"], rules),
        "validation.authorization",
    )
    authority = read("source_authority.json")
    implementation = authority["implementation"]
    require(
        authority == _authority(repo_root, implementation["commit"], implementation["tree"]),
        "validation.source_authority",
    )
    require(read("cohort.json") == _cohort(inputs), "validation.cohort")
    projections = [read("projections/" + label + ".json") for label in LABELS]
    pair_paths = sorted(path for path in files if path.startswith("pairs/"))
    pairs = [read(path) for path in pair_paths]
    partition, measurement = read("relation_partition.json"), read("empirical_measurement.json")
    controls, independent = read("controls.json"), read("independent_validation.json")
    actual_independent = audit_measurement(
        inputs, rules, projections, pairs, partition, measurement
    )
    require(
        actual_independent == independent and independent["passed"],
        "validation.independent_measurement",
    )
    require(read("correction_ledger.json") == _ledger(projections), "validation.correction_ledger")
    states = [read(path) for path in sorted(files) if path.startswith("states/")]
    assignments = [read(path) for path in sorted(files) if path.startswith("assignments/")]
    require(states == [row["state"] for row in partition["classes"]], "validation.state_inventory")
    require(
        sorted(assignments, key=lambda item: item["session_id"])
        == sorted(partition["assignments"], key=lambda item: item["session_id"]),
        "validation.assignment_inventory",
    )
    saved_controls = [read(path) for path in sorted(files) if path.startswith("controls/")]
    require(
        saved_controls == controls["controls"] and len(saved_controls) == 12,
        "validation.control_inventory",
    )
    require(
        controls == run_controls(inputs, rules, projections, pairs, partition),
        "validation.control_recomputation",
    )
    require(
        all(
            control["qualified_scientific_sample"] is False
            and control["provider_calls"]
            == control["candidate_runtime_executions"]
            == control["assignments_added_to_formal_partition"]
            == 0
            for control in saved_controls
        ),
        "validation.control_scope",
    )
    gates = _gates(projections, pairs, partition, measurement, controls, independent)
    require(read("gate_evaluation.json") == gates, "validation.gates")
    report = _report(
        inputs,
        rules,
        authority,
        projections,
        pairs,
        partition,
        measurement,
        controls,
        independent,
        gates,
    )
    require(
        read("report.json") == report and manifest["report_id"] == report["id"], "validation.report"
    )
    persistence = read("persistence.json")
    covered = {
        path: data
        for path, data in files.items()
        if path not in {"persistence.json", "artifact_manifest.json"}
    }
    require(
        persistence["covered_members"]
        == [
            {"relative_path": path, "sha256": sha(data), "byte_count": len(data)}
            for path, data in sorted(covered.items())
        ],
        "validation.persistence_members",
    )
    events = persistence["write_events"]
    order = [event["relative_path"] for event in events[::2]]
    require(
        len(order) == len(set(order)) == len(covered) and set(order) == set(covered),
        "validation.write_totality",
    )
    require(
        events
        == [
            {"event_ordinal": 2 * index + offset + 1, "kind": kind, "relative_path": path}
            for index, path in enumerate(order)
            for offset, kind in enumerate(("file_fsync", "directory_fsync"))
        ],
        "validation.file_directory_order",
    )
    require(
        order.index("source_authority.json")
        < min(order.index("projections/" + label + ".json") for label in LABELS)
        and order.index("measurement_contract.json") < order.index("projections/M01.json"),
        "validation.freeze_before_projection",
    )
    expected_top = {
        "external_review.txt",
        "operator_directive.txt",
        "authorization.json",
        "source_authority.json",
        "parent_freeze.json",
        "measurement_contract.json",
        "cohort.json",
        "correction_ledger.json",
        "relation_partition.json",
        "empirical_measurement.json",
        "controls.json",
        "independent_validation.json",
        "gate_evaluation.json",
        "report.json",
        "persistence.json",
        "artifact_manifest.json",
    }
    labels = {projection["session_id"]: projection["label"] for projection in projections}
    expected_pair_paths = [
        f"pairs/{index:02d}_"
        + labels[pair["left_session_id"]]
        + "_"
        + labels[pair["right_session_id"]]
        + ".json"
        for index, pair in enumerate(pairs, 1)
    ]
    require(pair_paths == expected_pair_paths, "validation.pair_paths")
    expected_nested = (
        {"projections/" + label + ".json" for label in LABELS}
        | set(expected_pair_paths)
        | {f"states/{index:02d}.json" for index in range(1, len(states) + 1)}
        | {"assignments/" + labels[item["session_id"]] + ".json" for item in assignments}
        | {
            f"controls/{index:02d}_" + control["name"] + ".json"
            for index, control in enumerate(saved_controls, 1)
        }
    )
    require(set(files) == expected_top | expected_nested, "validation.no_unaccounted_artifact")
    assert_unchanged(repo_root, inputs)
    return {
        "passed": True,
        "independent_validation_id": independent["id"],
        "new_provider_calls": 0,
        "new_candidate_runtime_executions": 0,
    }


def replay_measurement(
    *, repo_root: Path, replay_from: Path, output_directory: Path
) -> dict[str, Any]:
    """Recompute the same finite measurement in a new directory; no new model sample."""
    original = files_at(replay_from)
    validate_artifacts(repo_root=repo_root, artifact_directory=replay_from)
    authority = json.loads(original["source_authority.json"])["implementation"]
    result = build_measurement(
        repo_root=repo_root,
        external_audit=replay_from / "external_review.txt",
        source_commit=authority["commit"],
        source_tree=authority["tree"],
        output_directory=output_directory,
    )
    require(files_at(replay_from) == original, "replay.original_changed")
    require(files_at(output_directory) == original, "replay.byte_reconstruction")
    return {
        **result,
        "all_files_byte_identical": True,
        "recomputed_pairs_refer_to_same_ten_frozen_pairs": True,
        "new_statistical_samples": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("measure", "replay", "validate"), required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--external-audit", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--source-tree")
    parser.add_argument("--replay-from", type=Path)
    args = parser.parse_args()
    if args.mode == "measure":
        require(
            all((args.output_directory, args.external_audit, args.source_commit, args.source_tree)),
            "cli.measure_arguments",
        )
        result = build_measurement(
            repo_root=args.repo_root,
            external_audit=args.external_audit,
            source_commit=args.source_commit,
            source_tree=args.source_tree,
            output_directory=args.output_directory,
        )
    elif args.mode == "replay":
        require(
            args.output_directory is not None and args.replay_from is not None,
            "cli.replay_arguments",
        )
        result = replay_measurement(
            repo_root=args.repo_root,
            replay_from=args.replay_from,
            output_directory=args.output_directory,
        )
    else:
        require(args.replay_from is not None, "cli.validate_arguments")
        result = validate_artifacts(repo_root=args.repo_root, artifact_directory=args.replay_from)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
