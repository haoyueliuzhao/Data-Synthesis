"""Read-only archive investigation. Never a collection/training entry point."""

import argparse
import json
import subprocess
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from multiprocessing import get_context
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.catalog import IDENTITY_FIELDS
from ..finance_qa_vnext_linear_postprocess.manifest import LinearParent
from ..finance_qa_vnext_task_build.archive import validate_record
from .protocol import (
    BASE_COMMIT,
    BRANCH,
    COLLECTION,
    COLLECTION_MANIFEST,
    MATERIAL_MANIFEST,
    MATERIALS,
    OUTPUT,
    PACKAGE,
    checked_record,
    encode,
    now,
    policy,
    record,
    require,
    sha,
    write_once,
)

REVISION = "trusted_data_synthesis/artifacts/qa_vnext_readiness_revision/revision_20260912"
REVISION_MANIFEST = "manifest:6f646a8e45e4e65bec53fe9b75e5bf04047baae0f4b92cfa307bae90b731b4ec"


def git(root, *arguments):
    return subprocess.check_output(["git", "-C", str(root), *arguments])


def guarded_roots(code_root, data_root):
    code_root, data_root = Path(code_root).resolve(), Path(data_root).resolve()
    require(code_root != data_root, "movement.separate_read_only_data_root")
    require(
        git(code_root, "branch", "--show-current").decode().strip() == BRANCH,
        "movement.independent_branch_required",
    )
    require(
        git(data_root, "rev-parse", "HEAD").decode().strip() == BASE_COMMIT,
        "movement.frozen_main_commit",
    )
    require(Path(__file__).resolve().is_relative_to(code_root), "movement.actual_code_root")
    output = code_root / OUTPUT
    require(
        not any(p.is_symlink() for p in (output, *output.parents)), "movement.no_output_symlink"
    )
    require(
        output.resolve().is_relative_to(code_root)
        and not output.resolve().is_relative_to(data_root),
        "movement.isolated_output",
    )
    return code_root, data_root, output


def source_snapshot(root):
    """Tracked source/config/test/docs bytes; massive raw archives are separate parents."""
    prefixes = [
        "AGENTS.md",
        ".gitignore",
        ".gitattributes",
        "trusted_data_synthesis/src",
        "trusted_data_synthesis/tests",
        "trusted_data_synthesis/config",
        "trusted_data_synthesis/docs",
        "trusted_data_synthesis/scripts",
        "trusted_data_synthesis/pyproject.toml",
        "raw_financial_data_lake/finraw",
    ]
    names = git(root, "ls-files", "-t", "-z", "--", *prefixes).decode().split("\0")
    members = []
    for item in filter(None, names):
        tag, name = item[:1], item[2:]
        path = Path(root) / name
        if path.is_file():
            members.append({"path": name, "sha256": sha(path), "materialized": True})
        else:
            require(tag == "S" and not path.exists(), "movement.only_sparse_absence_allowed")
            members.append({"path": name, "materialized": False, "skip_worktree": True})
    return record(
        "protected_source_snapshot",
        root=str(root),
        commit=git(root, "rev-parse", "HEAD").decode().strip(),
        branch=git(root, "branch", "--show-current").decode().strip(),
        tracked_source_count=len(members),
        members=members,
    )


def diagnostic_code_snapshot(root):
    root = Path(root)
    paths = sorted((root / PACKAGE).glob("*.py"))
    paths += sorted(
        (root / "trusted_data_synthesis/tests").glob("test_qa_vnext_movement_support_*.py")
    )
    require(
        paths and all(p.is_file() and not p.is_symlink() for p in paths),
        "movement.regular_diagnostic_code_files",
    )
    return record(
        "diagnostic_code_snapshot",
        starting_git_commit=git(root, "rev-parse", "HEAD").decode().strip(),
        members=[{"path": str(p.relative_to(root)), "sha256": sha(p)} for p in paths],
        source_bytes_authoritative_even_before_final_commit=True,
    )


def require_task_sets(catalog, public):
    full_ids = [row["task_id"] for row in catalog["tasks"]]
    public_ids = [row["task_id"] for row in public["tasks"]]
    require(
        len(full_ids) == len(set(full_ids)) == len(public_ids) == len(set(public_ids)) == 255
        and set(full_ids) == set(public_ids),
        "movement.unique_exact_full_and_public_task_sets",
    )


def require_qualification_bundle(entry, qualification, fixture):
    require(
        qualification["id"] == entry["qualification_id"]
        and qualification["bundle_id"] == fixture["bundle"]["id"]
        and qualification["task_id"] == fixture["bundle"]["task_id"],
        "movement.original_qualification_private_bundle_join",
    )


def preflight(code_root, data_root):
    code_root, data_root, output = guarded_roots(code_root, data_root)
    if (output / "policy.json").exists():
        require(
            (output / "policy.json").read_bytes() == encode(policy()), "movement.same_frozen_policy"
        )
    else:
        write_once(output / "policy.json", policy())
    protected = [source_snapshot(data_root)]
    for name in [
        "/tmp/data-synthesis-anchored-vtdo-MaNMFd",
        "/tmp/data-synthesis-hierarchical-loss-yvab69o2",
    ]:
        require(Path(name).is_dir(), "movement.protected_worktree_present")
        protected.append(source_snapshot(Path(name)))
    write_once(output / "protected_sources_before.json", protected)
    results = []
    for relative, identity in [
        (COLLECTION, COLLECTION_MANIFEST),
        (MATERIALS, MATERIAL_MANIFEST),
        (REVISION, REVISION_MANIFEST),
    ]:
        start = time.monotonic()
        reader = LinearParent(data_root, relative, identity)
        try:
            reader.verify_all()
            result = record(
                "archive_preflight",
                verification=reader.last_verification,
                elapsed_seconds=time.monotonic() - start,
                finished_utc=now(),
            )
            results.append(result)
            print(
                json.dumps(
                    {
                        "preflight": relative,
                        "members": len(reader.members),
                        "seconds": result["elapsed_seconds"],
                    }
                ),
                flush=True,
            )
        finally:
            reader.close()
    result = record(
        "phase_zero_preflight",
        policy_id=policy()["id"],
        archives=results,
        protected_source_ids=[row["id"] for row in protected],
        finished_utc=now(),
        archive_verification_is_not_trajectory_qualification=True,
        API_calls=0,
        GPU_calls=0,
        Student_outputs_read=False,
    )
    write_once(output / "archive_preflight.json", result)
    return result


def open_parent(stack, root, relative, identity):
    reader = LinearParent(root, relative, identity)
    stack.callback(reader.close)
    return reader


def load_fixtures(stack, root):
    """Manifest/byte-pinned private fixtures, exclusively for offline diagnosis."""
    revision = open_parent(stack, root, REVISION, REVISION_MANIFEST)
    catalog = revision.read("catalog.json")
    public = revision.read("public_catalog.json")
    validate_record(catalog, "composed_task_catalog")
    validate_record(public, "public_task_catalog")
    require(public["source_catalog_id"] == catalog["id"], "movement.public_catalog_join")
    require_task_sets(catalog, public)
    public_by_task = {row["task_id"]: row for row in public["tasks"]}
    require(
        len(public_by_task) == len(public["tasks"]) == len(catalog["tasks"]) == 255,
        "movement.complete_255_fixture_catalog",
    )
    readers, bindings, dependency_members = {}, {}, []
    for row in catalog["parents"]:
        reader = open_parent(stack, root, row["directory"], row["manifest_id"])
        require(reader.descriptor() == row, "movement.original_fixture_parent_pin")
        readers[row["manifest_id"]] = reader
        bindings[row["manifest_id"]] = reader.read("native_bindings.json")
        dependency_members.append(
            {"parent_manifest_id": row["manifest_id"], **reader.members["native_bindings.json"]}
        )
    fixtures = []
    for row in catalog["tasks"]:
        reader = readers[row["parent_manifest_id"]]
        prefix = reader.relative + "/"
        require(
            row["bundle_path"].startswith(prefix)
            and row["public_path"].startswith(prefix)
            and row["native_bindings_path"] == prefix + "native_bindings.json",
            "movement.fixture_paths_match_parent",
        )
        bundle_relative, public_relative = (
            row["bundle_path"][len(prefix) :],
            row["public_path"][len(prefix) :],
        )
        bundle = reader.read(bundle_relative)
        validate_record(bundle, "TaskBundle")
        raw_messages = reader.bytes(public_relative)
        messages = json.loads(raw_messages)
        identity = {key: row[key] for key in IDENTITY_FIELDS}
        require(
            bundle["id"] == row["bundle_id"]
            and bundle["task_id"] == row["task_id"]
            and sha(raw_messages) == row["public_messages_sha256"]
            and public_by_task[row["task_id"]] == {**identity, "public_path": row["public_path"]}
            and bundle["public"] == json.loads(messages[0]["content"]),
            "movement.original_bundle_and_public_bytes_join",
        )
        fixtures.append(
            {
                "bundle": bundle,
                "native_bindings": bindings[row["parent_manifest_id"]],
                "messages": messages,
                "identity": identity,
            }
        )
        dependency_members.extend(
            {"parent_manifest_id": row["parent_manifest_id"], **reader.members[name]}
            for name in [bundle_relative, public_relative]
        )
    dependencies = record(
        "fixture_dependencies",
        catalog_id=catalog["id"],
        public_catalog_id=public["id"],
        parents=catalog["parents"],
        member_count=len(dependency_members),
        members=dependency_members,
        all_read_members_byte_SHA_verified=True,
        whole_dependency_archives_rescanned=False,
        private_inputs_used_only_by_offline_diagnosis=True,
    )
    return fixtures, dependencies


def _control_job(job):
    from .controls import run_fixture_control

    fixture, basis, root, expected = job
    require(diagnostic_code_snapshot(root) == expected, "movement.child_code_before")
    result = run_fixture_control(fixture, basis)
    require(diagnostic_code_snapshot(root) == expected, "movement.child_code_after")
    return {"control": result, "code_before_and_after_id": expected["id"]}


def cohort(code_root, data_root):
    """All denominators; deterministic reference controls never enter training."""
    from ..finance_qa_vnext_eval_readiness.materials import checked_record as checked_original
    from .funnel import aggregate, read_inputs
    from .signals import build_support_index, growth_delta_hazard, public_trace_signals
    from .summary import summarize

    code_root, data_root, output = guarded_roots(code_root, data_root)
    checked_record(
        json.loads((output / "archive_preflight.json").read_bytes()), "phase_zero_preflight"
    )
    require(
        (output / "policy.json").read_bytes() == encode(policy()), "movement.same_frozen_policy"
    )
    require(not (output / "cohort_report.json").exists(), "movement.no_completed_run_overwrite")
    started = time.monotonic()
    code_before = diagnostic_code_snapshot(code_root)
    write_once(output / "diagnostic_code_before.json", code_before)
    with ExitStack() as stack:
        collection = open_parent(stack, data_root, COLLECTION, COLLECTION_MANIFEST)
        materials = open_parent(stack, data_root, MATERIALS, MATERIAL_MANIFEST)
        fixtures, dependencies = load_fixtures(stack, data_root)
        fixture_by_task = {f["identity"]["task_id"]: f for f in fixtures}
        support = {
            key: build_support_index(f["bundle"], f["native_bindings"])
            for key, f in fixture_by_task.items()
        }
        witness_diagnostics = record(
            "original_witness_diagnostics",
            task_count=255,
            rows=[growth_delta_hazard(f["bundle"]) for f in fixtures],
            source_locator_ambiguities=[
                {
                    "task_id": key,
                    "ambiguous_locators": {
                        locator: facts
                        for locator, facts in value["locator_facts"].items()
                        if len(facts) != 1
                    },
                }
                for key, value in support.items()
                if any(len(facts) != 1 for facts in value["locator_facts"].values())
            ],
            not_observed_Teacher_requalification=True,
        )
        jobs = [
            (fixture, basis)
            for fixture in fixtures
            for basis in (
                ["control"]
                if fixture["bundle"]["family"] == "control"
                else ["endpoint", "movement"]
            )
        ]
        require(len(jobs) == 410, "movement.all_410_registered_interface_controls")
        control_plan = record(
            "scripted_control_plan",
            policy_id=policy()["id"],
            task_count=255,
            case_count=410,
            workers=8,
            task_and_basis_order=[
                {"task_id": f["identity"]["task_id"], "basis": b} for f, b in jobs
            ],
            actual_provenance="test_only_scripted_reference_callback",
            script_is_not_Teacher_training_data=True,
            all_tasks_without_outcome_selection=True,
            purpose="test original interface and assessor support, not actual generation frequency",
            new_API_calls=0,
            tokenizer_loads=0,
            GPU_operations=0,
            training_material_writes=0,
        )
        write_once(output / "scripted_control_plan.json", control_plan)
        write_once(output / "fixture_dependencies.json", dependencies)
        write_once(output / "original_witness_diagnostics.json", witness_diagnostics)
        with ProcessPoolExecutor(max_workers=8, mp_context=get_context("spawn")) as pool:
            pending = [pool.submit(_control_job, (*job, code_root, code_before)) for job in jobs]
            inputs = read_inputs(collection, materials)
            entries = inputs["session_results"]
            registry = collection.read("final_session_registry.json")
            require(
                set(fixture_by_task) == {row["task_id"] for row in registry},
                "movement.collection_exact_fixture_task_set",
            )
            identity_fields = ("session_id", "task_id", "pool", "basis", "replicate")
            require(
                len(registry) == len(entries) == 24640
                and all(row["state"] == "finished" for row in registry)
                and [[row[k] for k in identity_fields] for row in registry]
                == [[row["registered_session"][k] for k in identity_fields] for row in entries],
                "movement.original_complete_registry_order",
            )
            result = aggregate(**inputs)
            write_once(output / "qualification_funnel.json", result)
            print(
                json.dumps({"phase": "qualification_funnel", "sessions": len(entries)}), flush=True
            )
            signal_rows = []
            for index, entry in enumerate(entries):
                prefix = COLLECTION + "/"
                require(
                    entry["session_path"].startswith(prefix), "movement.original_session_parent"
                )
                session = collection.read(entry["session_path"][len(prefix) :])
                checked_original(session, "training_session")
                reg = entry["registered_session"]
                fixture = fixture_by_task[reg["task_id"]]
                require_qualification_bundle(
                    entry, inputs["qualifications"][entry["qualification_id"]], fixture
                )
                require(
                    session["id"] == entry["session_id"]
                    and session["registered_session_id"] == reg["session_id"]
                    and session["requested_basis"] == reg["basis"]
                    and session["identity"] == fixture["identity"]
                    and session["public_messages"] == fixture["messages"],
                    "movement.exact_original_session_fixture_join",
                )
                row = public_trace_signals(session, support[reg["task_id"]])
                signal_rows.append(
                    {
                        "registry_index": index,
                        "registered_session_id": reg["session_id"],
                        "task_id": reg["task_id"],
                        "family": fixture["bundle"]["family"],
                        "pool": reg["pool"],
                        "requested_basis": reg["basis"],
                        "qualification_id": entry["qualification_id"],
                        "original_actual_method": entry["actual_method"],
                        "original_representation_eligible": entry["representation_eligible"],
                        "signals": row,
                    }
                )
                if (index + 1) % 4000 == 0:
                    print(
                        json.dumps({"phase": "public_execution_signals", "sessions": index + 1}),
                        flush=True,
                    )
            control_results = [future.result() for future in pending]
            controls = [row["control"] for row in control_results]
        write_once(
            output / "public_execution_signals.json",
            record(
                "public_execution_signals",
                policy_id=policy()["id"],
                registered_sessions=24640,
                all_original_registry_order_preserved=True,
                finance_or_method_qualification=False,
                reasoning_content_inspected=False,
                rows=signal_rows,
            ),
        )
        write_once(
            output / "scripted_interface_controls.json",
            record(
                "scripted_interface_controls",
                plan_id=control_plan["id"],
                cases=controls,
                case_count=len(controls),
                actual_generation_distribution_not_measured_by_scripts=True,
                training_material=False,
            ),
        )
        read_evidence = [
            record(
                "cohort_read_binding", parent=p.descriptor(), counters=dict(p.verification_stats)
            )
            for p in [collection, materials]
        ]
    code_after = diagnostic_code_snapshot(code_root)
    require(code_before == code_after, "movement.diagnostic_code_unchanged_through_all_reads")
    write_once(output / "diagnostic_code_after.json", code_after)
    signal_record = json.loads((output / "public_execution_signals.json").read_bytes())
    controls_record = json.loads((output / "scripted_interface_controls.json").read_bytes())
    summary = summarize(result, signal_record, controls_record, witness_diagnostics)
    write_once(output / "phase_zero_summary.json", summary)
    before = json.loads((output / "protected_sources_before.json").read_bytes())
    after = [source_snapshot(Path(row["root"])) for row in before]
    require(before == after, "movement.all_three_existing_source_trees_unchanged")
    write_once(output / "protected_sources_after.json", after)
    report = record(
        "cohort_report",
        policy_id=policy()["id"],
        qualification_funnel_id=result["id"],
        public_execution_signals_id=signal_record["id"],
        scripted_interface_controls_id=controls_record["id"],
        summary_id=summary["id"],
        diagnostic_code_snapshot_id=code_before["id"],
        child_control_code_attestations=len(control_results),
        all_child_code_before_after_ids_equal=all(
            row["code_before_and_after_id"] == code_before["id"] for row in control_results
        ),
        registered_session_count=24640,
        original_actual_method_counts=dict(Counter(row["actual_method"] for row in entries)),
        raw_execution_signal_count=len(signal_rows),
        scripted_control_count=len(controls),
        read_bindings=read_evidence,
        elapsed_seconds=time.monotonic() - started,
        finished_utc=now(),
        original_main_anchored_and_hierarchical_sources_unchanged=True,
        original_archive_files_overwritten=0,
        corrected_qualifications_written=0,
        new_Teacher_requests=0,
        new_Student_or_GPU_runs=0,
        Student_outputs_read=False,
        original_material_status=inputs["material_manifest"]["status"],
        training_admission_changed=False,
        scientific_HierLoss_or_VTDO_benefit_established=False,
    )
    write_once(output / "cohort_report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--phase", choices=["preflight", "cohort"], required=True)
    args = parser.parse_args()
    result = {"preflight": preflight, "cohort": cohort}[args.phase](args.code_root, args.data_root)
    print(
        json.dumps({"id": result["id"], "status": "READ_ONLY_" + args.phase.upper() + "_COMPLETE"})
    )


if __name__ == "__main__":
    main()
