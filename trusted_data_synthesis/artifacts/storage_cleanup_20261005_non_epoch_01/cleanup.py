"""One-shot, explicitly authorized V18 non-epoch tensor cleanup.

`plan` is read-only toward experiment data. `execute --plan-sha256 SHA` is
irreversible, cannot be retried automatically, and unlinks only the fixed list.
No model tensor is loaded or hashed. Every other experiment file is retained.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
from datetime import datetime, timezone


REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
FINQA = REPO / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01"
V18 = FINQA / "v18_researcher_continuation_01"
ROOT = V18 / "training/five_arm_training"
OUT = REPO / "trusted_data_synthesis/artifacts/storage_cleanup_20261005_non_epoch_01"
SCRIPT = OUT / "cleanup.py"
SEEDS = (11, 29, 47)
ARMS = ("static", "manual_plus", "manual_minus", "c_only", "full")
EPOCHS = tuple(range(447, 1491, 149))
AUTHORIZATION = "同意，清理完成后继续本轮实验"
EXPECTED_COUNT = 17760
EXPECTED_LOGICAL_BYTES = 544159723424


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return str(path.relative_to(REPO))


def no_symlink_ancestors(path, checked=None):
    for ancestor in reversed(path.parents):
        if checked is not None and ancestor in checked:
            continue
        info = ancestor.lstat()
        require(stat.S_ISDIR(info.st_mode), f"non-directory or symlink ancestor: {ancestor}")
        if checked is not None:
            checked.add(ancestor)


def identity(path, checked=None):
    no_symlink_ancestors(path, checked)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), f"not a regular, non-symlink file: {path}")
    return dict(
        path=relative(path), dev=info.st_dev, inode=info.st_ino,
        size=info.st_size, st_blocks=info.st_blocks,
        allocated_bytes=info.st_blocks * 512, nlink=info.st_nlink,
        mode=info.st_mode, mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
    )


def fixed_targets():
    return sorted(
        ROOT / f"seed{seed}/arms/{arm}/training/step{step:04d}_step/state.pt"
        for seed in SEEDS for arm in ARMS for step in range(299, 1491)
        if step % 149 != 0
    )


def target_inventory():
    paths = fixed_targets()
    require(len(paths) == EXPECTED_COUNT, "fixed scope count changed")
    tracked = set(subprocess.check_output(
        ["git", "ls-files", "-z", "--", relative(ROOT)], cwd=REPO,
    ).decode().split("\0"))
    checked, rows = set(), []
    for path in paths:
        require(relative(path) not in tracked, f"tracked tensor: {path}")
        row = identity(path, checked)
        require(row["nlink"] == 1, f"multiple links: {path}")
        rows.append(row)
    require(sum(row["size"] for row in rows) == EXPECTED_LOGICAL_BYTES,
            "fixed target logical size differs from authorized proposal")
    return rows


def protection_inventory():
    """Metadata-only protection for scientific checkpoints and adjacent evidence."""
    selected = set(fixed_targets())
    groups = {}

    def add(path, kind):
        require(path not in selected, f"protected point intersects targets: {path}")
        groups.setdefault(path, set()).add(kind)

    for seed in SEEDS:
        for arm in ARMS:
            base = ROOT / f"seed{seed}/arms/{arm}/training"
            for epoch in EPOCHS:
                path = base / f"step{epoch:04d}_step/state.pt"
                add(path, "epoch_tensor")
                if arm == "c_only" and epoch == 1490:
                    add(path, "explicit_C_only_test_extension_endpoint")
            for checkpoint in base.glob("step*_*"):
                add(checkpoint / "record.json", "all_main_checkpoint_records")
                if checkpoint.name.endswith(("_initial", "_branch", "_outer")):
                    add(checkpoint / "state.pt", "initial_branch_outer_tensor")
                if (checkpoint / "outer_inputs.pt").exists():
                    add(checkpoint / "outer_inputs.pt", "outer_inputs")
            for replay in base.glob("replay_checkpoints/**/state.pt"):
                add(replay, "feedback_replay_tensor")
            add(base.parent / "result/record.json", "main_arm_result")
        for path in (ROOT / f"seed{seed}/shared").rglob("*"):
            if path.is_file():
                add(path, "all_shared_files")
        add(ROOT / f"seed{seed}/result/record.json", "main_seed_result")
    for subtree, kind in (
        (FINQA / "v15_prefix_completion_01/prefix_training", "all_V15_prefix_tensors"),
        (V18 / "mechanisms", "all_V18_mechanism_tensors"),
        (V18 / "v23_confirmation_shrink_01", "all_V23_tensors"),
    ):
        for path in subtree.rglob("state.pt"):
            add(path, kind)
    for suffix in (
        "final_evaluation/paired_summary/record.json",
        "mechanisms/evaluation_result/record.json",
        "evaluation_continuation_01/queue/result/record.json",
        "material/result/record.json",
        "v23_confirmation_shrink_01/result/record.json",
        "v23_confirmation_shrink_01/test_confirmation/summary/record.json",
        "v23_confirmation_shrink_01/shrink_control/evaluation_result/record.json",
    ):
        add(V18 / suffix, "authoritative_summary")
    checked, rows, counts = set(), [], {}
    for path, kinds in sorted(groups.items()):
        row = identity(path, checked)
        row["kinds"] = sorted(kinds)
        if "authoritative_summary" in kinds:
            row["sha256"] = digest(path)
        rows.append(row)
        for kind in kinds:
            counts[kind] = counts.get(kind, 0) + 1
    require(counts["epoch_tensor"] == 120, "epoch protection count changed")
    require(counts["explicit_C_only_test_extension_endpoint"] == 3,
            "C-only endpoint protection count changed")
    return rows, counts


def process_audit(rows):
    """Fail closed for this account's relevant workers and target open FDs."""
    target_inodes = {(row["dev"], row["inode"]) for row in rows}
    result = dict(at=now(), own_uid=os.getuid(), own_uid_processes_checked=0,
                  other_uid_processes_not_inspected=0, vanished_processes=0,
                  privileged_system_daemon_fd_tables_not_inspected=[],
                  paused_historical_controllers=[], target_open_fds=[],
                  active_relevant_workers=[], limitation=(
                      "FD audit covers readable processes of this account; other users and "
                      "protected FD tables of explicitly identified sshd/systemd/PAM daemons are "
                      "not claimed to have been inspected. No process is signaled."))
    ancestors, cursor = {os.getpid()}, os.getppid()
    while cursor > 1 and cursor not in ancestors:
        ancestors.add(cursor)
        try:
            fields = (Path("/proc") / str(cursor) / "stat").read_text().rsplit(")", 1)[1].split()
            cursor = int(fields[1])
        except (OSError, ValueError, IndexError):
            break
    for proc in sorted(Path("/proc").iterdir()):
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                result["other_uid_processes_not_inspected"] += 1
                continue
            fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            status, birth = fields[0], fields[19]
            args = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
            pid = int(proc.name)
            result["own_uid_processes_checked"] += 1
            relevant = (str(V18) in args or "finqa_v" in args)
            executable = args.split(" ", 1)[0]
            python_worker = any(word in Path(executable).name for word in ("python", "torchrun"))
            if pid not in ancestors and relevant and python_worker:
                row = dict(pid=pid, birth=birth, state=status, command=args)
                historical = any(name in args for name in (
                    "finqa_v18_four_gpu_queue_recovery.py", "finqa_v19_queued_scheduler.py"))
                if historical and status in ("T", "t"):
                    result["paused_historical_controllers"].append(row)
                elif status != "Z":
                    result["active_relevant_workers"].append(row)
            for fd in (proc / "fd").iterdir():
                try:
                    info = fd.stat()
                    if (info.st_dev, info.st_ino) in target_inodes:
                        result["target_open_fds"].append(dict(pid=pid, fd=fd.name))
                except FileNotFoundError:
                    continue
        except (FileNotFoundError, ProcessLookupError):
            result["vanished_processes"] += 1
            continue
        except PermissionError as exc:
            # System privilege boundaries may hide daemon FDs even with the
            # account UID. Never silently skip a Python/experiment process.
            comm = (proc / "comm").read_text().strip()
            privileged_sshd = (comm == "sshd"
                    and args.startswith("sshd:")
                    and (proc / "fd").stat().st_uid == 0)
            user_systemd = comm == "systemd" and args == "/usr/lib/systemd/systemd --user"
            user_pam = comm == "(sd-pam)" and args == "(sd-pam)"
            if privileged_sshd or user_systemd or user_pam:
                result["privileged_system_daemon_fd_tables_not_inspected"].append(
                    dict(pid=int(proc.name), command=args, reason="protected system daemon FD table"))
                continue
            raise RuntimeError(f"cannot inspect own-account process: {proc}") from exc
    require(not result["target_open_fds"], f"target tensor has open FD: {result['target_open_fds']}")
    require(not result["active_relevant_workers"],
            f"active relevant worker: {result['active_relevant_workers']}")
    return result


def write_new(path, value):
    no_symlink_ancestors(path)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def storage():
    usage = os.statvfs(ROOT)
    return dict(available_bytes=usage.f_bavail * usage.f_frsize,
                free_bytes=usage.f_bfree * usage.f_frsize)


def plan():
    require(not (OUT / "plan.json").exists(), "existing plan is immutable; do not overwrite")
    require(not (OUT / "execution_intent.json").exists(), "previous execution forbids replan")
    targets = target_inventory()
    protection, counts = protection_inventory()
    body = dict(
        schema="finqa_v18_non_epoch_cleanup_plan.v1", at=now(),
        authorization_exact=AUTHORIZATION, scope_root=relative(ROOT),
        seeds=list(SEEDS), arms=list(ARMS), steps="299..1490 inclusive, step % 149 != 0",
        target_basename="state.pt", script_sha256=digest(SCRIPT),
        destructive=True, tensor_hashing_performed=False,
        recoverability="Not recoverable from Git or retained JSON; no tensor backup is asserted.",
        only_unlink_fixed_targets=True, directories_and_all_other_files_retained=True,
        no_retry_or_resume=True, candidates=targets, candidate_count=len(targets),
        candidate_logical_bytes=sum(row["size"] for row in targets),
        candidate_allocated_bytes=sum(row["allocated_bytes"] for row in targets),
        protected=protection, protected_count=len(protection), protection_counts=counts,
        process_audit=process_audit(targets), filesystem_before=storage(),
        git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip(),
    )
    write_new(OUT / "plan.json", body)
    print(json.dumps(dict(plan=relative(OUT / "plan.json"),
                         plan_sha256=digest(OUT / "plan.json"),
                         script_sha256=body["script_sha256"],
                         candidate_count=len(targets),
                         candidate_allocated_bytes=body["candidate_allocated_bytes"],
                         candidate_logical_bytes=body["candidate_logical_bytes"],
                         protected_count=len(protection), protection_counts=counts,
                         execution_performed=False), ensure_ascii=False, indent=2))


def verify_protection(plan_body):
    current, counts = protection_inventory()
    require(current == plan_body["protected"], "protected file metadata or summary changed")
    require(counts == plan_body["protection_counts"], "protected set changed")
    return dict(protected_count=len(current), protection_counts=counts,
                unchanged=True, compared_fields="all recorded metadata and summary SHA256")


def execute(expected_sha):
    require(expected_sha, "execute requires --plan-sha256")
    require(digest(OUT / "plan.json") == expected_sha, "plan SHA mismatch")
    body = json.loads((OUT / "plan.json").read_text())
    require(body["script_sha256"] == digest(SCRIPT), "cleanup implementation changed")
    require(body["authorization_exact"] == AUTHORIZATION, "authorization binding changed")
    require(body["scope_root"] == relative(ROOT), "scope root changed")
    require(body["candidate_count"] == EXPECTED_COUNT, "candidate count changed")
    require(not (OUT / "execution_intent.json").exists(),
            "previous execution intent exists; NO automatic rerun or resume")
    require(not (OUT / "result.json").exists(), "previous result exists")
    rows = target_inventory()
    require(rows == body["candidates"], "target metadata changed since plan")
    before = verify_protection(body)
    audit = process_audit(rows)
    write_new(OUT / "execution_intent.json", dict(
        at=now(), plan_sha256=expected_sha, script_sha256=digest(SCRIPT),
        authorization_exact=AUTHORIZATION, process_audit=audit,
        protected_before=before, filesystem_before=storage(), no_retry_or_resume=True,
    ))
    def terminate_with_partial_result(signum, frame):
        raise SystemExit(f"termination signal {signum}; stop without retry")

    signal.signal(signal.SIGTERM, terminate_with_partial_result)
    deleted, completed, error = [], False, None
    protection_after = None
    try:
        for row in rows:
            path = REPO / row["path"]
            # Recheck every ancestor and file immediately before its sole unlink.
            require(identity(path) == row, f"target identity changed before unlink: {path}")
            parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                info = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
                require((info.st_dev, info.st_ino, info.st_nlink, info.st_size,
                         info.st_blocks, info.st_mtime_ns, info.st_ctime_ns, info.st_mode)
                        == (row["dev"], row["inode"], 1, row["size"], row["st_blocks"],
                            row["mtime_ns"], row["ctime_ns"], row["mode"]),
                        f"final dirfd identity check failed: {path}")
                os.unlink(path.name, dir_fd=parent_fd)
                deleted.append(row["path"])
            finally:
                os.close(parent_fd)
        protection_after = verify_protection(body)
        require(all(not (REPO / row["path"]).exists() for row in rows),
                "a deleted target reappeared")
        completed = True
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc))
        try:
            protection_after = verify_protection(body)
        except BaseException as protected_exc:
            protection_after = dict(unchanged=False, error=str(protected_exc))
    finally:
        write_new(OUT / "result.json", dict(
            schema="finqa_v18_non_epoch_cleanup_result.v1", at=now(),
            plan_sha256=expected_sha, script_sha256=digest(SCRIPT),
            status="COMPLETE" if completed else "PARTIAL_FAILURE_NO_AUTOMATIC_RETRY",
            target_count=len(rows), deleted_count=len(deleted), deleted_paths=deleted,
            deleted_logical_bytes=sum(row["size"] for row in rows[:len(deleted)]),
            deleted_allocated_bytes=sum(row["allocated_bytes"] for row in rows[:len(deleted)]),
            protected_after=protection_after, filesystem_after=storage(), error=error,
            no_tensor_hashes_computed=True, no_directory_removed=True,
            no_process_signaled=True, automatic_resume_forbidden=True,
        ))
    print(json.dumps(dict(status="COMPLETE" if completed else "PARTIAL_FAILURE",
                         deleted_count=len(deleted), result=relative(OUT / "result.json")), indent=2))
    if not completed:
        sys.exit(1)


def main():
    require(Path(__file__).absolute() == SCRIPT, "unexpected script location")
    no_symlink_ancestors(SCRIPT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "execute"))
    parser.add_argument("--plan-sha256")
    args = parser.parse_args()
    if args.action == "plan":
        require(args.plan_sha256 is None, "plan does not take a SHA")
        plan()
    else:
        execute(args.plan_sha256)


if __name__ == "__main__":
    main()
