"""Remove the 2263 explicitly authorized old QA intermediate tensors, not endpoints."""

import argparse
import hashlib
import json
import os
import re
import runpy
import shutil
import stat
from collections import Counter
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE = REPO / "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value"
OUTPUT = REPO / "trusted_data_synthesis/artifacts/storage_cleanup_20261010_qa_01"
HELPER = REPO / "trusted_data_synthesis/artifacts/storage_cleanup_20261010_test_tmp_01/cleanup.py"
H = runpy.run_path(str(HELPER))
require, identity, sha, encode = (H[key] for key in ("require", "identity", "sha", "encode"))
B_ROOT = SOURCE / "delayed_C_B_confirmation_cache_20260922/jobs"
A_ROOT = SOURCE / "delayed_C_recovery_cache_20260921"
N_ROOT = SOURCE / "direction_calibration_cache_20260926/training_stage_20260926/jobs"
GROUPS = {
    "B_non_epoch": [
        B_ROOT / f"B_{arm}_{seed}/updates"
        for arm in ("prefix", "static", "delayed_c")
        for seed in (11, 29, 47)
    ],
    "A_non_epoch": [A_ROOT / f"A_delayed_c_{seed}/updates" for seed in (29, 47)],
    "negative_non_epoch": [N_ROOT / f"B_negative_{seed}/updates" for seed in (11, 29, 47)],
}
POPULATION = A_ROOT / "A_delayed_c_29/population.pt"
EXPECTED = {
    "B_non_epoch": (1755, 53654691840),
    "A_non_epoch": (390, 11923521536),
    "negative_non_epoch": (117, 3576963072),
    "A29_population": (1, 16976003072),
}


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


def admitted(path, group):
    if group == "A29_population":
        require(path == POPULATION, "wrong population target")
    else:
        require(group in GROUPS and path.parent in GROUPS[group], "outside fixed update roots")
        require(re.fullmatch(r"[0-9]{4}\.pt", path.name), "not a four-digit update")
        step = int(path.stem)
        require(step % 40 != 0, "epoch and 0240 checkpoints are protected")
        if group == "negative_non_epoch":
            require(201 <= step <= 239, "outside authorized negative training range")
    require(path.is_relative_to(SOURCE) and path == path.resolve(), "redirected target")
    info = identity(path)
    require(stat.S_ISREG(info[2]) and info[6] == 1, "not a single-link regular file")
    require(info[0] == SOURCE.stat().st_dev, "cross-device target")
    return info


def retained_snapshot(targets):
    excluded = {str(path) for path in targets}
    rows = []
    for path in sorted(SOURCE.rglob("*")):
        if str(path) in excluded:
            continue
        info = identity(path)
        if not stat.S_ISDIR(info[2]):
            rows.append(dict(path=str(path.relative_to(REPO)), identity=info))
    return dict(count=len(rows), metadata_sha256=hashlib.sha256(encode(rows)).hexdigest())


def protected():
    rows = H["protected"]()
    points = SOURCE / "cross_market_calibration_cache_20260926/evaluation_01/points"
    for arm in ("static", "positive", "negative"):
        for seed in (11, 29, 47):
            for name in ("point.json", "adapter.safetensors"):
                path = points / f"{arm}_{seed}" / name
                rows[str(path)] = identity(path)
    for directories in GROUPS.values():
        for directory in directories:
            # Prefix jobs end at 0200; protect every actual epoch checkpoint,
            # without pretending they also produced a nonexistent 0240.
            for path in sorted(directory.iterdir()):
                if re.fullmatch(r"[0-9]{4}\.pt", path.name) and int(path.stem) % 40 == 0:
                    rows[str(path)] = identity(path)
    last_feedback = A_ROOT / "A_delayed_c_29/feedback/0631.pt"
    rows[str(last_feedback)] = identity(last_feedback)
    return rows


def validate_groups(rows):
    counts, amounts = Counter(), Counter()
    for row in rows:
        counts[row["group"]] += 1
        amounts[row["group"]] += row["identity"][7]
    require(
        {key: (counts[key], amounts[key]) for key in counts} == EXPECTED, "audited groups changed"
    )
    require(len({row["path"] for row in rows}) == 2263, "duplicate or missing targets")


def prepare():
    require(not (OUTPUT / "plan.json").exists(), "fixed plan already exists")
    require(SOURCE == SOURCE.resolve() and SOURCE.is_dir(), "unsafe source root")
    rows = []
    for group, directories in GROUPS.items():
        for directory in directories:
            for path in sorted(directory.iterdir()):
                if not re.fullmatch(r"[0-9]{4}\.pt", path.name) or int(path.stem) % 40 == 0:
                    continue
                rows.append(dict(path=str(path), group=group, identity=admitted(path, group)))
    rows.append(
        dict(
            path=str(POPULATION),
            group="A29_population",
            identity=admitted(POPULATION, "A29_population"),
        )
    )
    validate_groups(rows)
    targets = [Path(row["path"]) for row in rows]
    H["tracked_guard"](targets)
    process = H["process_guard"]([SOURCE])
    return publish(
        "plan.json",
        dict(
            at=H["now"](),
            files=rows,
            allocated_bytes=sum(row["identity"][7] for row in rows),
            script_sha256=sha(__file__),
            helper_sha256=sha(HELPER),
            authorization_sha256=sha(OUTPUT / "authorization_and_dependencies.json"),
            protected_files=protected(),
            retained_files=retained_snapshot(targets),
            process_guard=process,
            runtime=H["runtime"](),
            no_content_backup=True,
            unrecoverable_from_git=True,
            original_continuous_resume_will_no_longer_work=True,
            V18_fifteen_model_baseline_and_current_FinQA_excluded=True,
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
        "authorization changed",
    )
    require(not (OUTPUT / "execution_intent.json").exists(), "no automatic retry")
    validate_groups(plan["files"])
    targets = [Path(row["path"]) for row in plan["files"]]
    H["tracked_guard"](targets)
    process = H["process_guard"]([SOURCE])
    require(protected() == plan["protected_files"], "protected files changed")
    require(retained_snapshot(targets) == plan["retained_files"], "non-target QA files changed")
    for path, row in zip(targets, plan["files"], strict=True):
        require(admitted(path, row["group"]) == row["identity"], "target changed")
    free_before = shutil.disk_usage(REPO).free
    publish(
        "execution_intent.json",
        dict(
            at=H["now"](),
            plan_id=plan["id"],
            process_guard=process,
            runtime=H["runtime"](),
            free_bytes=free_before,
            irreversible_deletion_explicitly_authorized=True,
        ),
    )
    removed, success, failure = [], False, None
    protected_unchanged, retained_unchanged = None, None
    try:
        for path, row in zip(targets, plan["files"], strict=True):
            require(admitted(path, row["group"]) == row["identity"], "target changed before unlink")
            path.unlink()
            removed.append(row)
        require(all(not os.path.lexists(path) for path in targets), "target still exists")
        protected_unchanged = protected() == plan["protected_files"]
        retained_unchanged = retained_snapshot(targets) == plan["retained_files"]
        require(protected_unchanged and retained_unchanged, "retained or protected files changed")
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
                all_retained_QA_files_metadata_unchanged=retained_unchanged,
                retained_files_checked=plan["retained_files"]["count"],
                no_content_backup=True,
                unrecoverable_from_git=True,
                original_continuous_resume_no_longer_supported=True,
                free_bytes_before=free_before,
                free_bytes_after=shutil.disk_usage(REPO).free,
                disk_delta_not_attributed_only_to_cleanup=True,
                runtime_after=H["runtime"](),
                no_signals_GPU_API_or_training_changes=True,
                V18_fifteen_model_baseline_and_current_FinQA_excluded=True,
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
