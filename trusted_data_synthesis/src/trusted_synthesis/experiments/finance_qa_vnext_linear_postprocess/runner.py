"""Reviewed handoff of an exclusively read-only old supervisor, never collection.

`inspect` is read-only. `execute` requires a saved reviewed plan, an explicit
authorization record, unchanged committed source registration, old-process
absence and still-absent material/Student outputs. This module never signals or
stops a process, never starts collect, and never changes scientific functions.
"""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import adapter
from .manifest import LinearParent
from .protocol import (
    BASE_COMMIT,
    OPERATION,
    PACKAGE,
    checked,
    encode,
    policy,
    record,
    require,
    sha,
    write_once,
)

SCOPES = (
    "trusted_data_synthesis/src",
    "trusted_data_synthesis/tests",
    "trusted_data_synthesis/scripts",
    "trusted_data_synthesis/config",
    "raw_financial_data_lake/finraw",
    "raw_financial_data_lake/tests",
    "trusted_data_synthesis/pyproject.toml",
    "raw_financial_data_lake/pyproject.toml",
)
COLLECT_MODULE = "trusted_synthesis.experiments.finance_qa_vnext_eval_surface.stage"
STUDENT_MODULE = "trusted_synthesis.experiments.finance_qa_vnext_basis_student.stage"
WORKER_MODULE = "trusted_synthesis.experiments.finance_qa_vnext_basis_student.worker"
RUNNER_MODULE = "trusted_synthesis.experiments.finance_qa_vnext_linear_postprocess.runner"
PROCESS_IDENTITY_FIELDS = ("pid", "start_ticks", "uid", "command_sha256")


def code_root():
    return Path(__file__).resolve().parents[5]


def _tree(root, revision):
    raw = subprocess.check_output(["git", "ls-tree", "-r", "-z", revision, "--", *SCOPES], cwd=root)
    result = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        header, path = entry.split(b"\t", 1)
        mode, kind, digest = header.decode().split()
        require(
            kind == "blob" and mode in {"100644", "100755"}, "linear.original_regular_code_blob"
        )
        result[path.decode()] = digest
    return result


def _blob(raw, expected):
    algorithm = "sha1" if len(expected) == 40 else "sha256"
    return hashlib.new(algorithm, b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def source_registration(root=None):
    """Code-only checks, not live artifacts or model data; new files must be committed."""
    root = Path(root or code_root()).resolve()
    old = _tree(root, BASE_COMMIT)
    current_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    current = _tree(root, current_head)
    originals = []
    for name, expected in sorted(old.items()):
        path = root / name
        require(path.is_file() and not path.is_symlink(), "linear.original_code_file_present")
        raw = path.read_bytes()
        require(
            _blob(raw, expected) == expected and current.get(name) == expected,
            "linear.no_historical_code_or_test_changes:" + name,
        )
        originals.append({"path": name, "git_blob": expected, "sha256": sha(raw)})
    sources = sorted((root / PACKAGE).glob("*.py"))
    tests = sorted((root / "trusted_data_synthesis/tests").glob("test_qa_vnext_linear_*.py"))
    require(sources and tests, "linear.adapter_sources_and_controls_present")
    supplementary = {
        root / PACKAGE / "README.md": "adapter_documentation",
        root / PACKAGE / "preflight_evidence.json": "read_only_preflight_evidence",
    }
    roles = {
        **dict.fromkeys(sources, "adapter_source"),
        **dict.fromkeys(tests, "adapter_CPU_test"),
        **supplementary,
    }
    added = []
    for path, role in roles.items():
        name = str(path.relative_to(root))
        require(name not in old and name in current, "linear.new_adapter_must_be_committed:" + name)
        require(path.is_file() and not path.is_symlink(), "linear.regular_adapter_binding_file")
        raw = path.read_bytes()
        require(_blob(raw, current[name]) == current[name], "linear.no_uncommitted_adapter_drift")
        added.append(
            {
                "path": name,
                "sha256": sha(raw),
                "role": role,
            }
        )
    return record(
        "linear_source_registration",
        base_commit=BASE_COMMIT,
        implementation_commit=current_head,
        historical_source_file_count=len(originals),
        historical_source_snapshot_sha256=sha(encode(originals)),
        adapter_code=added,
        existing_files_changed=0,
    )


def _process(pid):
    location = Path("/proc") / str(pid)
    try:
        fields = (location / "stat").read_text().rsplit(") ", 1)[1].split()
        raw = (location / "cmdline").read_bytes()
        argv = [part.decode(errors="replace") for part in raw.split(b"\0") if part]
        return {
            "pid": pid,
            "parent_pid": int(fields[1]),
            "start_ticks": int(fields[19]),
            "state": fields[0],
            "alive": fields[0] != "Z",
            "command_sha256": sha(raw),
            "argv": argv,
            "uid": location.stat().st_uid,
        }
    except (FileNotFoundError, ProcessLookupError):
        return {"pid": pid, "alive": False, "argv": []}


def process_kind(argv, *, pid=None):
    """Recognize all supported competing writer entrypoints, not arbitrary Python."""

    def action(module):
        if module not in argv:
            return None
        # argparse accepts options before the positional action. Skip their
        # values too: a --root value named "run" is not itself an action.
        remaining = iter(argv[argv.index(module) + 1 :])
        for token in remaining:
            if token in {"--root", "--reviewed-plan", "--authorization", "--job"}:
                next(remaining, None)
            elif not token.startswith("-"):
                return token
        return None

    if WORKER_MODULE in argv:
        return "worker"
    student = action(STUDENT_MODULE)
    if student == "follow":
        return "follow"
    if student in {"advance", "freeze", "run"}:
        return "postprocessor"
    surface = action(COLLECT_MODULE)
    if surface == "collect":
        return "collector"
    if surface == "materialize":
        return "postprocessor"
    if action(RUNNER_MODULE) == "execute" and pid != os.getpid():
        return "postprocessor"
    return None


def _managed_processes():
    result = []
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            if path.stat().st_uid != os.getuid():
                continue
            value = _process(int(path.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
        if value["alive"] and process_kind(value["argv"], pid=value["pid"]) is not None:
            result.append(value)
    return result


def _open_collection_access(processes, collection):
    writers, writable_mappings, readers = [], [], []
    # Examine only managed processes and only path/flags, never messages/results.
    for process in processes:
        location = Path("/proc") / str(process["pid"])
        try:
            for fd in (location / "fd").iterdir():
                try:
                    target = str(fd.readlink())
                    if not target.startswith(str(collection) + "/"):
                        continue
                    fields = dict(
                        line.split(":", 1)
                        for line in (location / "fdinfo" / fd.name).read_text().splitlines()
                        if ":" in line
                    )
                    flags = int(fields["flags"].strip(), 8)
                    row = {
                        "pid": process["pid"],
                        "path": target,
                        "access_mode": flags & os.O_ACCMODE,
                    }
                    (
                        writers if flags & os.O_ACCMODE in {os.O_WRONLY, os.O_RDWR} else readers
                    ).append(row)
                except (FileNotFoundError, ProcessLookupError):
                    continue
            for line in (location / "maps").read_text().splitlines():
                parts = line.split(maxsplit=5)
                if (
                    len(parts) == 6
                    and parts[5].startswith(str(collection) + "/")
                    and "w" in parts[1]
                ):
                    writable_mappings.append(
                        {"pid": process["pid"], "path": parts[5], "permissions": parts[1]}
                    )
        except (FileNotFoundError, ProcessLookupError):
            continue
    return writers, writable_mappings, readers


def inspect(root):
    """No materialization, ledger constructor, model, signal, or source edit."""
    from ..finance_qa_vnext_basis_student import protocol as original
    from ..finance_qa_vnext_eval_readiness import materials

    root = Path(root).resolve()
    runtime = root / "trusted_data_synthesis/artifacts/qa_vnext_basis_student/runtime_20260912"
    started_path = runtime / "follow_started.json"
    started = original.checked_record(json.loads(started_path.read_bytes()), "follow_started")
    collected = LinearParent(root, original.COLLECTION)
    try:
        report = collected.read("report.json")
        materials.checked_record(report, "fixed_collection_report")
        collection_parent = collected.descriptor()
        require(
            report["status"] == "COMPLETE_FIXED_COLLECTION"
            and report["collection_complete"] is True
            and report["registered_session_count"]
            == report["recorded_session_count"]
            == report["finished_session_count"]
            == 24640,
            "linear.original_full_collection_closed",
        )
        manifest_size, member_count = collected._manifest_stamp[3], len(collected.members)
    finally:
        collected.close()
    processes = _managed_processes()
    writers, mappings, readers = _open_collection_access(processes, root / original.COLLECTION)
    classified = {
        kind: [row for row in processes if process_kind(row["argv"], pid=row["pid"]) == kind]
        for kind in ("collector", "follow", "worker", "postprocessor")
    }

    def public_process(row):
        return {key: value for key, value in row.items() if key != "argv"}

    return record(
        "linear_handoff_plan",
        observed_at=datetime.now(timezone.utc).isoformat(),
        data_root=str(root),
        adapter_policy_id=policy()["id"],
        original_follow_started_id=started["id"],
        original_follow_started_sha256=sha(started_path),
        original_follow_pid=started["pid"],
        original_follow_identity=public_process(_process(started["pid"])),
        collection_parent=collection_parent,
        collection_report_id=report["id"],
        collection_manifest_bytes=manifest_size,
        collection_members=member_count,
        active_collectors=[public_process(row) for row in classified["collector"]],
        active_old_followers=[public_process(row) for row in classified["follow"]],
        active_student_workers=[public_process(row) for row in classified["worker"]],
        active_other_postprocessors=[public_process(row) for row in classified["postprocessor"]],
        managed_collection_writers=writers,
        managed_writable_collection_mappings=mappings,
        observed_collection_readers=readers,
        material_output_absent=not (root / original.MATERIALS).exists(),
        Student_output_absent=not (root / original.OUTPUT).exists(),
        old_follow_failure_exists=(runtime / "follow_failed.json").exists(),
        old_follow_completion_exists=(runtime / "follow_completed.json").exists(),
        process_visibility_scope=(
            "same-UID supported collect/materialize, Student follow/advance/freeze/run/worker, "
            "other linear execute; excludes this execute; "
            "operator must exclude arbitrary other writers"
        ),
        read_only=True,
        read_only_hash_work_may_be_abandoned=True,
        original_data_would_be_discarded=False,
        metrics_or_confirm_scores_read=False,
    )


def process_identity(value):
    require(
        all(
            type(value.get(key)) is int and value[key] >= 0 for key in ("pid", "start_ticks", "uid")
        )
        and value["pid"] > 0
        and value["start_ticks"] > 0
        and isinstance(value.get("command_sha256"), str)
        and len(value["command_sha256"]) == 64
        and all(char in "0123456789abcdef" for char in value["command_sha256"]),
        "linear.complete_process_identity",
    )
    return {key: value[key] for key in PROCESS_IDENTITY_FIELDS}


def guard_reviewed(reviewed):
    """Shared pre-stop guard: only one identified live reader may be abandoned."""
    checked(reviewed, "linear_handoff_plan")
    identity = process_identity(reviewed["original_follow_identity"])
    require(
        reviewed["original_follow_identity"]["alive"] is True
        and identity["pid"] == reviewed["original_follow_pid"]
        and len(reviewed["active_old_followers"]) == 1
        and reviewed["active_old_followers"][0]["alive"] is True
        and process_identity(reviewed["active_old_followers"][0]) == identity,
        "linear.exact_unique_live_original_follow_identity",
    )
    require(
        reviewed["read_only"]
        and reviewed["material_output_absent"]
        and reviewed["Student_output_absent"]
        and reviewed["active_collectors"]
        == reviewed["active_student_workers"]
        == reviewed["active_other_postprocessors"]
        == []
        and reviewed["managed_collection_writers"]
        == reviewed["managed_writable_collection_mappings"]
        == []
        and not reviewed["old_follow_failure_exists"]
        and not reviewed["old_follow_completion_exists"],
        "linear.reviewed_only_read_only_preprocessing_stage",
    )
    return identity


def guard_handoff(reviewed, current, authorization):
    identity = guard_reviewed(reviewed)
    checked(current, "linear_handoff_plan")
    checked(authorization, "linear_handoff_authorization")
    require(
        authorization["reviewed_plan_id"] == reviewed["id"]
        and authorization["operator_approved"] is True
        and authorization["scope"] == "replace_only_read_only_postprocessing_supervisor"
        and authorization["no_other_source_writers_confirmed"] is True
        and authorization["verified_stopped_process_identity"] == identity,
        "linear.explicit_reviewed_operator_authorization",
    )
    require(
        all(
            current[key] == reviewed[key]
            for key in (
                "data_root",
                "adapter_policy_id",
                "original_follow_started_id",
                "original_follow_started_sha256",
                "original_follow_pid",
                "collection_parent",
                "collection_report_id",
            )
        ),
        "linear.original_collection_and_supervisor_lineage_unchanged",
    )
    require(
        current["active_collectors"]
        == current["active_old_followers"]
        == current["active_student_workers"]
        == current["active_other_postprocessors"]
        == []
        and current["original_follow_identity"]["pid"] == identity["pid"]
        and current["original_follow_identity"]["alive"] is False
        and current["managed_collection_writers"]
        == current["managed_writable_collection_mappings"]
        == []
        and current["material_output_absent"]
        and current["Student_output_absent"]
        and not current["old_follow_failure_exists"]
        and not current["old_follow_completion_exists"],
        "linear.no_duplicate_or_partially_started_postprocessing",
    )
    return True


def execution_root(root):
    """Do not run worktree-imported code against a different live data tree."""
    supplied = Path(os.path.abspath(root))
    require(
        supplied == supplied.resolve() == code_root().resolve(),
        "linear.execute_only_in_own_non_symlink_code_root",
    )
    branch = subprocess.check_output(
        ["git", "symbolic-ref", "--short", "HEAD"], cwd=supplied, text=True
    ).strip()
    require(branch == "main", "linear.execute_only_main_branch")
    return supplied


def execute(root, reviewed_plan, authorization):
    """Future reviewed entry. This function does not stop the old supervisor."""
    from ..finance_qa_vnext_basis_student import stage as original
    from ..finance_qa_vnext_catalog_bridge.stage import seal

    root = execution_root(root)
    sources = source_registration(root)
    require(
        authorization["source_registration_id"] == sources["id"],
        "linear.reviewed_committed_adapter_code",
    )
    current = inspect(root)
    guard_handoff(reviewed_plan, current, authorization)
    output = root / OPERATION
    require(not output.exists(), "linear.one_supervisor_handoff_no_retry")
    adapter_binding = adapter.binding(sources, reviewed_plan, authorization)
    write_once(output / "source_registration.json", sources)
    write_once(output / "reviewed_plan.json", reviewed_plan)
    write_once(output / "handoff_authorization.json", authorization)
    write_once(output / "pre_start_state.json", current)
    write_once(output / "reader_adapter_binding.json", adapter_binding)
    write_once(
        output / "handoff_started.json",
        record(
            "linear_handoff_started",
            pid=os.getpid(),
            started_at=datetime.now(timezone.utc).isoformat(),
            original_follow_started_id=reviewed_plan["original_follow_started_id"],
            adapter_binding_id=adapter_binding["id"],
            only_repeated_read_only_hashes_abandoned=True,
            original_collection_or_material_records_deleted=0,
        ),
    )
    observed = []
    try:
        with adapter.installed(adapter_binding) as installed:
            observed = installed["verifications"]
            # Re-use every registered original scientific stage; never invoke collect.
            result = original.advance(root)
            closed = [
                name
                for name in (original.p.COLLECTION, original.p.MATERIALS, original.p.OUTPUT)
                if (root / name / "manifest.json").is_file()
            ]
            publication = original.try_publish(
                root,
                closed,
                "Publish original fixed-material Student terminal "
                "via audited linear reader handoff",
            )
            report = record(
                "linear_supervisor_completed",
                adapter_binding_id=adapter_binding["id"],
                completed_at=datetime.now(timezone.utc).isoformat(),
                original_terminal_record_id=result.get("id"),
                publication_record_id=publication.get("id"),
                scientific_result_values_not_copied_here=True,
                collection_restarted=False,
                old_financial_or_budget_code_modified=False,
            )
    except BaseException as error:
        write_once(output / "linear_verifications.json", observed)
        write_once(
            output / "handoff_failed.json",
            record(
                "linear_supervisor_failed",
                error_type=type(error).__name__,
                reason=str(error),
                adapter_binding_id=adapter_binding["id"],
                automatic_retry=False,
                original_collection_untouched=True,
                retained_partial_outputs=True,
            ),
        )
        raise
    write_once(output / "linear_verifications.json", observed)
    write_once(output / "report.json", report)
    seal(
        output, scope="read-only verification adapter and explicitly authorized supervisor handoff"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inspect", "source-registration", "execute"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--reviewed-plan", type=Path)
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args()
    if args.action == "inspect":
        result = inspect(args.root)
    elif args.action == "source-registration":
        result = source_registration()
    else:
        require(
            args.reviewed_plan is not None and args.authorization is not None,
            "linear.reviewed_plan_and_authorization_files_required",
        )
        result = execute(
            args.root,
            json.loads(args.reviewed_plan.read_bytes()),
            json.loads(args.authorization.read_bytes()),
        )
    print(encode(result).decode(), flush=True)


if __name__ == "__main__":
    main()
