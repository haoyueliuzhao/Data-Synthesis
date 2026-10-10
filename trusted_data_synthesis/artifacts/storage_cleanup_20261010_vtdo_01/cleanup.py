"""Delete only the explicitly authorized, fixed 1242 old VTDO non-adapter tensors."""

import argparse
import hashlib
import json
import os
import runpy
import shutil
import stat
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE = REPO / "trusted_data_synthesis/artifacts/vtdo_experiment"
ADAPTER = SOURCE / "finance_phase1_mvp_v1/beneficiary_adapter/adapter_model.safetensors"
OUTPUT = REPO / "trusted_data_synthesis/artifacts/storage_cleanup_20261010_vtdo_01"
HELPER = REPO / "trusted_data_synthesis/artifacts/storage_cleanup_20261010_test_tmp_01/cleanup.py"
H = runpy.run_path(str(HELPER))
require, identity, sha, encode = (H[key] for key in ("require", "identity", "sha", "encode"))


def publish(name, body):
    value = {**body, "id": hashlib.sha256(encode(body)).hexdigest()}
    with (OUTPUT / name).open("xb") as stream:
        stream.write(encode(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(OUTPUT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return value


def admitted(path):
    require(path.is_relative_to(SOURCE) and path != ADAPTER, "outside exact tensor scope")
    require(
        path == path.resolve() and path.suffix == ".safetensors", "redirected or non-tensor path"
    )
    info = identity(path)
    require(stat.S_ISREG(info[2]) and info[6] == 1, "not a single-link regular file")
    require(info[0] == SOURCE.stat().st_dev, "mount boundary forbidden")
    return info


def retained_snapshot(targets):
    excluded = {str(path) for path in targets}
    rows = []
    for path in sorted(SOURCE.rglob("*")):
        if str(path) in excluded:
            continue
        info = identity(path)
        if stat.S_ISDIR(info[2]):
            continue  # Removing a child legitimately changes directory mtime.
        rows.append(dict(path=str(path.relative_to(REPO)), identity=info))
    return dict(count=len(rows), metadata_sha256=hashlib.sha256(encode(rows)).hexdigest())


def protected():
    return {**H["protected"](), str(ADAPTER): identity(ADAPTER)}


def prepare():
    require(not (OUTPUT / "plan.json").exists(), "fixed plan already exists")
    require(SOURCE == SOURCE.resolve() and SOURCE.is_dir(), "unsafe VTDO root")
    all_tensors = sorted(SOURCE.rglob("*.safetensors"))
    require(ADAPTER in all_tensors and len(all_tensors) == 1243, "audited tensor set changed")
    targets = [path for path in all_tensors if path != ADAPTER]
    rows = [dict(path=str(path), identity=admitted(path)) for path in targets]
    require(len(rows) == 1242, "authorized file count changed")
    allocated = sum(row["identity"][7] for row in rows)
    require(allocated == 100350738432, "authorized allocated size changed")
    H["tracked_guard"](targets)
    process = H["process_guard"]([SOURCE])
    return publish(
        "plan.json",
        dict(
            at=H["now"](),
            source=str(SOURCE),
            files=rows,
            allocated_bytes=allocated,
            script_sha256=sha(__file__),
            helper_sha256=sha(HELPER),
            authorization_sha256=sha(OUTPUT / "authorization_and_dependencies.json"),
            protected_files=protected(),
            retained_files=retained_snapshot(targets),
            process_guard=process,
            runtime=H["runtime"](),
            no_content_backup=True,
            unrecoverable_from_git=True,
            preserve_all_non_target_files_and_directories=True,
            excludes_entire_QA_and_current_FinQA=True,
        ),
    )


def apply():
    plan = json.loads((OUTPUT / "plan.json").read_text())
    require(
        plan["id"]
        == hashlib.sha256(encode({k: v for k, v in plan.items() if k != "id"})).hexdigest(),
        "plan changed",
    )
    require(
        sha(__file__) == plan["script_sha256"] and sha(HELPER) == plan["helper_sha256"],
        "implementation changed",
    )
    require(
        sha(OUTPUT / "authorization_and_dependencies.json") == plan["authorization_sha256"],
        "scope evidence changed",
    )
    require(not (OUTPUT / "execution_intent.json").exists(), "no automatic retry")
    require(
        len(plan["files"]) == 1242 and plan["allocated_bytes"] == 100350738432,
        "wrong authorized scope",
    )
    targets = [Path(row["path"]) for row in plan["files"]]
    require(len(set(targets)) == len(targets), "duplicate targets")
    H["tracked_guard"](targets)
    process = H["process_guard"]([SOURCE])
    require(protected() == plan["protected_files"], "protected files changed")
    require(retained_snapshot(targets) == plan["retained_files"], "retained VTDO files changed")
    for path, row in zip(targets, plan["files"], strict=True):
        require(admitted(path) == row["identity"], "candidate changed since plan")
    free_before = shutil.disk_usage(REPO).free
    publish(
        "execution_intent.json",
        dict(
            at=H["now"](),
            plan_id=plan["id"],
            process_guard=process,
            runtime=H["runtime"](),
            free_bytes=free_before,
            irreversible_unique_tensor_deletion_explicitly_authorized=True,
        ),
    )
    removed, success, failure = [], False, None
    protected_unchanged, retained_unchanged = None, None
    try:
        for path, row in zip(targets, plan["files"], strict=True):
            require(admitted(path) == row["identity"], "candidate changed before unlink")
            path.unlink()
            removed.append(row)
        require(all(not os.path.lexists(path) for path in targets), "target still exists")
        protected_unchanged = protected() == plan["protected_files"]
        retained_unchanged = retained_snapshot(targets) == plan["retained_files"]
        require(protected_unchanged and retained_unchanged, "protected or retained files changed")
        success = True
    except BaseException as exc:
        failure = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        publish(
            "result.json",
            dict(
                at=H["now"](),
                plan_id=plan["id"],
                status="COMPLETE" if success else "PARTIAL_STOPPED_NO_RETRY",
                failure=failure,
                removed_files=len(removed),
                removed_paths=[row["path"] for row in removed],
                removed_allocated_bytes=sum(row["identity"][7] for row in removed),
                protected_files_unchanged=protected_unchanged,
                all_retained_VTDO_files_metadata_unchanged=retained_unchanged,
                retained_files_checked=plan["retained_files"]["count"],
                no_content_backup=True,
                unrecoverable_from_git=True,
                free_bytes_before=free_before,
                free_bytes_after=shutil.disk_usage(REPO).free,
                disk_delta_not_attributed_only_to_cleanup=True,
                runtime_after=H["runtime"](),
                no_signals_GPU_API_or_training_changes=True,
                QA_and_current_FinQA_not_in_scope=True,
            ),
        )
    return json.loads((OUTPUT / "result.json").read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "apply"])
    args = parser.parse_args()
    result = prepare() if args.action == "prepare" else apply()
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "id",
                    "status",
                    "allocated_bytes",
                    "removed_files",
                    "removed_allocated_bytes",
                )
                if key in result
            }
        )
    )
