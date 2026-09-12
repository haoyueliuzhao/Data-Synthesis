"""One consistent reassessment of frozen scripts; only newly qualified rows encode.

No scripts, TaskBundles, public versions, old qualifications or old token arrays
are regenerated. The changed assessor replays each saved public session exactly
once; all expectations remain the previously registered expectations. This is
scripted interface evidence and can never enter a Teacher training material pool.
"""

from collections import Counter
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.catalog import Parent, safe_path
from ..finance_qa_vnext_eval_readiness import assessment, controls, token_controls
from ..finance_qa_vnext_eval_readiness.runtime import SnapshotSources, encode
from ..finance_qa_vnext_eval_readiness.runtime import sha as bytes_sha
from ..finance_qa_vnext_task_build.archive import record, require, sha, write_json

WRAPPER_GATE = "assessment.source_relation_certificate_required"


def _token_parent_matches(row, package, candidate):
    try:
        representation = row["representation"]
        assessment._body_valid(representation)
        return (
            row["package_id"] == package["id"]
            and representation["row_id"] == candidate["id"]
            and representation["session_id"] == package["session_id"]
            and representation["qualification_id"] == package["assessment_id"]
            and representation["target_raw_sha256"] == candidate["target_raw_sha256"]
            and representation["maximum_sequence_length"] == 24576
            and not representation["truncated"]
            and representation["consumable_token_representation"]
            and representation["sequence_length"] <= 24576
        )
    except (KeyError, TypeError, ValueError):
        return False


def saved_control_reassessments(prior_report, resolver):
    """Pure control loop; the production caller supplies manifest-bound fixtures.

    ``resolver(old_control)`` returns the original bundle/messages/identity,
    original native bindings and public SnapshotSources. No provider callback
    or script builder is accepted. Exceptions are evidence, never a retry.
    """
    assessment._body_valid(prior_report)
    original_rows = prior_report["controls"]
    require(
        len({row["name"] for row in original_rows}) == len(original_rows),
        "revision.unique_original_control_names",
    )
    require(
        len({row["session"]["id"] for row in original_rows}) == len(original_rows),
        "revision.unique_original_sessions",
    )
    rows, new_packages = [], []
    positive_regressions, negative_regressions, mapping_changes, exceptions = [], [], [], []
    for old in original_rows:
        session, previous = old["session"], old["assessment"]
        assessment._body_valid(session)
        assessment._body_valid(previous)
        require(
            previous["session_id"] == session["id"], "revision.original_assessment_session_join"
        )
        require(
            session["origin"] == "scripted_evaluation_control" and session["provider_calls"] == 0,
            "revision.frozen_scripted_sessions_only",
        )
        current, error = None, None
        try:
            fixture = resolver(old)
            require(
                fixture["messages"] == session["public_messages"]
                and fixture["identity"] == session["identity"],
                "revision.original_public_session_identity",
            )
            # This is the sole replay call. assess_session internally regenerates
            # deterministic tool observations from the original raw responses and
            # requires equality of the entire saved scripted session.
            current = assessment.assess_session(
                session, fixture["bundle"], fixture["native_bindings"], fixture["sources"]
            )
            assessment._body_valid(current)
            require(
                current["session_id"] == session["id"] and current["id"] != previous["id"],
                "revision.new_qualification_original_session_parent",
            )
        except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
            error = type(exc).__name__ + ": " + str(exc)
            exceptions.append({"name": old["name"], "error": error})
        valid = (
            error is None
            and current is not None
            and current["financial_valid"]
            and current["complete_trajectory_qualified"]
        )
        if previous["financial_valid"] and not valid:
            positive_regressions.append(old["name"])
        if not old["expected_financial_valid"] and valid:
            negative_regressions.append(old["name"])
        if (
            previous["financial_valid"]
            and current is not None
            and (
                previous["full_mapping_status"] != current["full_mapping_status"]
                or previous["full_class"] != current["full_class"]
            )
        ):
            mapping_changes.append(old["name"])
        passed = bool(
            current is not None
            and error is None
            and current["financial_valid"] == old["expected_financial_valid"]
            and current["full_mapping_status"] == old["expected_full_mapping_status"]
        )
        reached = bool(
            previous["reason"] == WRAPPER_GATE
            and old["expected_financial_valid"]
            and current is not None
            and error is None
            and current["support_assessment_entered"]
            and current["reason"] != WRAPPER_GATE
        )
        newly_qualified = bool(valid and not previous["financial_valid"])
        if newly_qualified:
            package = controls.raw_package(session, current)
            assessment._body_valid(package)
            require(
                package["complete_first_final_package"],
                "revision.newly_qualified_first_Final_package",
            )
            new_packages.append(package)
        rows.append(
            record(
                "fixed_control_reassessment",
                name=old["name"],
                original_session_id=session["id"],
                original_assessment_id=previous["id"],
                original_public_messages_sha256=session["identity"]["public_messages_sha256"],
                original_surface_version_id=session["identity"]["surface_version_id"],
                original_task_id=session["identity"]["task_id"],
                expected_financial_valid=old["expected_financial_valid"],
                expected_full_mapping_status=old["expected_full_mapping_status"],
                original_financial_valid=previous["financial_valid"],
                original_reason=previous["reason"],
                passed=passed,
                newly_qualified=newly_qualified,
                old_wrapper_failure_reached_support_assessment=reached,
                reassessment=current,
                exception=error,
                original_expectations_unchanged=True,
                original_raw_responses_not_regenerated=True,
                training_eligible=False,
            )
        )
    return (
        rows,
        new_packages,
        {
            "prior_positive_regressions": positive_regressions,
            "prior_negative_regressions": negative_regressions,
            "prior_fine_mapping_changes": mapping_changes,
            "reassessment_exceptions": exceptions,
        },
    )


def inherited_token_evidence(prior_packages, token_report, prior_controls):
    """Inspect saved identities and arrays only; never invoke an encoder here."""
    assessment._body_valid(token_report)
    require(
        token_report["status"] == "PASS_SCRIPTED_REPRESENTATION_ONLY"
        and token_report["maximum_sequence_length"] == 24576
        and not token_report["truncation"],
        "revision.prior_exact_representation_contract",
    )
    sessions = {row["session"]["id"]: row for row in prior_controls}
    require(
        len({package["session_id"] for package in prior_packages}) == len(prior_packages),
        "revision.unique_prior_packages",
    )
    eligible, candidates = [], {}
    for package in prior_packages:
        assessment._body_valid(package)
        require(
            package["origin"] == "scripted_evaluation_control"
            and not package["training_eligible"]
            and package["training_samples"] == 0,
            "revision.old_packages_remain_nontraining",
        )
        old = sessions[package["session_id"]]
        require(
            package["assessment_id"] == old["assessment"]["id"]
            and package["financial_valid"] == old["assessment"]["financial_valid"],
            "revision.old_package_exact_qualification_parent",
        )
        if not (package["financial_valid"] and package["complete_first_final_package"]):
            continue
        eligible.append(package)
        for candidate in package["candidates"]:
            assessment._body_valid(candidate)
            turn = old["session"]["turns"][candidate["response_index"]]
            require(
                candidate["messages"] == turn["input_messages"]
                and candidate["target_text"] == turn["raw_response"]
                and candidate["target_raw_sha256"] == turn["raw_response_sha256"]
                and candidate["id"] not in candidates,
                "revision.original_candidate_bytes_and_unique_identity",
            )
            candidates[candidate["id"]] = (package, candidate)
    actual = token_report["rows"]
    require(
        len(actual) == len(candidates)
        and {row["candidate_id"] for row in actual} == set(candidates),
        "revision.all_and_only_original_qualified_arrays",
    )
    for row in actual:
        package, candidate = candidates[row["candidate_id"]]
        require(
            _token_parent_matches(row, package, candidate),
            "revision.original_array_package_and_length",
        )
    require(
        len(eligible) == token_report["financial_complete_packages"]
        and len(actual) == token_report["encoded_rows"]
        and sum(row["representation"]["target_token_count"] for row in actual)
        == token_report["target_tokens"],
        "revision.original_array_count_and_token_totals",
    )
    return {
        "verified": True,
        "packages": len(eligible),
        "rows": len(actual),
        "target_tokens": token_report["target_tokens"],
        "sequence_tokens": token_report["sequence_tokens"],
        "session_ids": [package["session_id"] for package in eligible],
        "old_rows_reencoded": 0,
        "tokenizer_constructions": 0,
    }


def run(
    root,
    output,
    parent_directory,
    *,
    expected_parent_manifest_id,
    freeze_id,
    materializer=token_controls.materialize,
):
    """Execute once after the caller's new source/code freeze; no live API path."""
    root = Path(root).resolve()
    output = Path(output)
    output = output if output.is_absolute() else root / output
    output = safe_path(root, output.relative_to(root))
    parent = Parent(root, parent_directory, expected_parent_manifest_id)
    require(
        freeze_id and not output.exists() and not output.is_relative_to(parent.directory),
        "revision.new_frozen_control_output_only",
    )
    prior_report = parent.read("controls/source_bound_report.json")
    old_packages = parent.read("controls/original_packages.json")
    old_tokens = parent.read("controls/token_report.json")
    selection = parent.read("controls/fixture_selection.json")
    prior_freeze = parent.read("stage_freeze.json")
    assessment._body_valid(selection)
    assessment._body_valid(prior_report)
    require(
        prior_report["control_count"] == len(prior_report["controls"]) == 70
        and prior_report["passed_count"] == 55,
        "revision.exact_original_seventy_control_denominator",
    )
    inherited = inherited_token_evidence(old_packages, old_tokens, prior_report["controls"])
    require(
        inherited["packages"] == 39 and inherited["rows"] == 253,
        "revision.exact_original_39_package_253_row_parent",
    )
    source_failures = [
        row
        for row in prior_report["controls"]
        if row["expected_financial_valid"] and row["assessment"]["reason"] == WRAPPER_GATE
    ]
    require(len(source_failures) == 15, "revision.exact_original_fifteen_wrapper_rejections")
    selected = {row["task_id"]: row["cell"][0] for row in selection["rows"]}
    require(
        len(selected) == len(selection["rows"])
        and {row["session"]["identity"]["task_id"] for row in prior_report["controls"]}
        == set(selected),
        "revision.original_fixed_fixture_selection",
    )
    catalogs, bindings, fixtures = {}, {}, {}
    for split in sorted(set(selected.values())):
        catalog = parent.read(f"panels/{split}/catalog.json")
        assessment._body_valid(catalog)
        catalogs[split] = {row["task_id"]: row for row in catalog["tasks"]}
        bindings[split] = parent.read(f"panels/{split}/native_bindings.json")

    def resolve(old):
        session = old["session"]
        task = session["identity"]["task_id"]
        if task not in fixtures:
            split = selected[task]
            row = catalogs[split][task]
            bundle = parent.read(f"panels/{split}/" + row["path"])
            assessment._body_valid(bundle)
            raw = parent.bytes(f"panels/{split}/" + row["public_path"])
            messages = parent.read(f"panels/{split}/" + row["public_path"])
            require(
                encode(messages) == raw
                and bytes_sha(raw) == row["public_messages_sha256"]
                and bundle["id"] == row["bundle_id"],
                "revision.original_public_bytes_and_TaskBundle",
            )
            identity = {
                key: row[key]
                for key in ("task_id", "family", "surface_version_id", "public_messages_sha256")
            }
            identity["parent_manifest_id"] = prior_freeze["id"]
            fixtures[task] = {
                "bundle": bundle,
                "messages": messages,
                "identity": identity,
                "native_bindings": bindings[split],
                "sources": SnapshotSources(root, [bundle["public"]["source_document"]]),
            }
        return fixtures[task]

    output.mkdir(parents=True)
    write_json(
        output / "run_started.json",
        record(
            "fixed_control_reassessment_start",
            freeze_id=freeze_id,
            parent=parent.descriptor(),
            control_count=70,
            expectations_changed=False,
        ),
    )
    rows, new_packages, regressions = saved_control_reassessments(prior_report, resolve)
    assessments = record(
        "fixed_control_reassessment_rows",
        freeze_id=freeze_id,
        original_report_id=prior_report["id"],
        rows=rows,
        no_new_raw_responses=True,
    )
    write_json(output / "reassessments.json", assessments)
    packages_record = record(
        "newly_qualified_script_packages",
        freeze_id=freeze_id,
        packages=new_packages,
        old_packages_reencoded=False,
        training_eligible=False,
    )
    write_json(output / "newly_qualified_packages.json", packages_record)
    incremental = materializer(new_packages, root)
    assessment._body_valid(incremental)
    write_json(output / "incremental_CPU.json", incremental)

    def relative(path):
        return str(path.relative_to(root))

    parent_paths = {
        "original_report": "controls/source_bound_report.json",
        "original_packages": "controls/original_packages.json",
        "token_report": "controls/token_report.json",
        "fixture_selection": "controls/fixture_selection.json",
    }
    inherited_refs = {
        name: {
            "path": str(Path(parent.relative) / path),
            "sha256": parent.members[path]["sha256"],
            "bytes": parent.members[path]["bytes"],
        }
        for name, path in parent_paths.items()
    }
    current_valid = [
        row
        for row in rows
        if row["reassessment"] is not None and row["reassessment"]["financial_valid"]
    ]
    covered = set(inherited["session_ids"]) | {package["session_id"] for package in new_packages}
    coverage = covered == {row["original_session_id"] for row in current_valid}
    passed = sum(row["passed"] for row in rows)
    reached = sum(row["old_wrapper_failure_reached_support_assessment"] for row in rows)
    new_candidates = {
        candidate["id"]: (package, candidate)
        for package in new_packages
        for candidate in package["candidates"]
    }
    new_rows = incremental["rows"]
    incremental_coverage = (
        len(new_rows) == len(new_candidates)
        and {row["candidate_id"] for row in new_rows} == set(new_candidates)
        and all(
            _token_parent_matches(row, *new_candidates[row["candidate_id"]]) for row in new_rows
        )
        and incremental["financial_complete_packages"] == len(new_packages)
        and incremental["maximum_sequence_length"] == 24576
        and not incremental["truncation"]
        and incremental["tokenizer_constructions"] == (1 if new_packages else 0)
    )
    token_ok = (
        incremental["status"]
        in {"PASS_SCRIPTED_REPRESENTATION_ONLY", "NO_FINANCIAL_COMPLETE_PACKAGES"}
        and incremental_coverage
    )
    summary = record(
        "fixed_control_reassessment_report",
        status="PASS"
        if passed == 70
        and reached == 15
        and not any(regressions.values())
        and coverage
        and token_ok
        else "FAIL",
        freeze_id=freeze_id,
        parent=parent.descriptor(),
        original_report_id=prior_report["id"],
        original_expectations_unchanged=True,
        original_sessions_replayed_once=True,
        control_count=len(rows),
        passed_count=passed,
        prior_15_reached_support_assessment=reached,
        financial_valid_count=len(current_valid),
        full_mapping_counts=dict(
            Counter(
                row["reassessment"]["full_mapping_status"]
                for row in rows
                if row["reassessment"] is not None
            )
        ),
        **regressions,
        inherited_CPU={
            **inherited,
            "parent_directory": parent.relative,
            "parent_manifest_id": parent.manifest["id"],
            "parent_references": inherited_refs,
            "token_report_path": inherited_refs["token_report"]["path"],
            "token_report_sha256": inherited_refs["token_report"]["sha256"],
            "original_packages_path": inherited_refs["original_packages"]["path"],
            "original_packages_sha256": inherited_refs["original_packages"]["sha256"],
        },
        incremental_CPU={
            "status": incremental["status"],
            "all_new_qualified_candidates_encoded": incremental_coverage,
            "financial_complete_packages": incremental["financial_complete_packages"],
            "rows": len(incremental["rows"]),
            "target_tokens": incremental.get("target_tokens", 0),
            "sequence_tokens": incremental.get("sequence_tokens", 0),
            "tokenizer_constructions": incremental["tokenizer_constructions"],
            "report_path": relative(output / "incremental_CPU.json"),
            "report_sha256": sha(output / "incremental_CPU.json"),
        },
        token_combined={
            "all_current_qualified_covered": coverage and token_ok,
            "financial_complete_packages": len(covered),
            "inherited_rows": inherited["rows"],
            "new_rows": len(incremental["rows"]),
            "maxseq": 24576,
            "truncation": False,
            "old_rows_reencoded": 0,
        },
        reassessments_path=relative(output / "reassessments.json"),
        reassessments_sha256=sha(output / "reassessments.json"),
        newly_qualified_packages_path=relative(output / "newly_qualified_packages.json"),
        newly_qualified_packages_sha256=sha(output / "newly_qualified_packages.json"),
        training_eligible=False,
        training_samples=0,
        API_requests=0,
        Teacher_sessions=0,
        Student_runs=0,
        GPU_runs=0,
        original_70_assessments_modified=False,
        original_39_token_arrays_modified=False,
    )
    assessment._body_valid(summary)
    parent.check_manifest()
    write_json(output / "report.json", summary)
    return summary
