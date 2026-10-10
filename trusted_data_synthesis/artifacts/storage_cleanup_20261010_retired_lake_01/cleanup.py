"""One-shot verified archival of the retired data lake's remaining data only."""

import argparse
import gzip
import hashlib
import json
import os
import runpy
import shutil
import stat
import tarfile
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE = REPO / "raw_financial_data_lake/data"
OUTPUT = REPO / "trusted_data_synthesis/artifacts/storage_cleanup_20261010_retired_lake_01"
BACKUP = REPO / "trusted_data_synthesis/artifacts/retired_data_archive_20261010_01"
HELPER = REPO / "trusted_data_synthesis/artifacts/storage_cleanup_20261010_test_tmp_01/cleanup.py"
H = runpy.run_path(str(HELPER))
require, identity, sha, encode = (H[key] for key in ("require", "identity", "sha", "encode"))


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(name, body):
    value = {**body, "id": hashlib.sha256(encode(body)).hexdigest()}
    with (OUTPUT / name).open("xb") as stream:
        stream.write(encode(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(OUTPUT)
    return value


def inventory():
    require(SOURCE == SOURCE.resolve() and SOURCE.is_dir(), "redirected or missing data root")
    require(
        {p.name for p in SOURCE.iterdir()}
        == {"audit", "metadata.sqlite3", "test_metadata.sqlite3"},
        "data scope changed; re-audit required",
    )
    rows = []
    for path in sorted(SOURCE.rglob("*")):
        info = identity(path)
        regular, directory = stat.S_ISREG(info[2]), stat.S_ISDIR(info[2])
        require(regular or directory, "links and special files are not eligible")
        require(info[0] == SOURCE.stat().st_dev, "mount boundary forbidden")
        require(not regular or info[6] == 1, "hardlinked data must be retained")
        rows.append(
            dict(
                path=str(path.relative_to(REPO)),
                identity=info,
                kind="file" if regular else "directory",
            )
        )
    return rows


def prepare():
    require(not (OUTPUT / "plan.json").exists(), "plan already exists")
    require(not os.path.lexists(BACKUP), "backup destination already exists")
    H["tracked_guard"]([SOURCE])
    process = H["process_guard"]([SOURCE])
    members = inventory()
    return publish(
        "plan.json",
        dict(
            at=H["now"](),
            source=str(SOURCE),
            backup=str(BACKUP),
            user_scope="raw_financial_data_lake下的数据均不再使用",
            script_sha256=sha(__file__),
            helper_sha256=sha(HELPER),
            members=members,
            source_allocated_bytes=sum(row["identity"][7] for row in members),
            process_guard=process,
            protected_files=H["protected"](),
            runtime=H["runtime"](),
            preserve_source_parent=True,
            preserve_code_config_benchmarks_and_docs=True,
            old_experiment_archives_not_deleted=True,
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
    require(not (OUTPUT / "execution_intent.json").exists(), "no automatic retry")
    require(
        not os.path.lexists(BACKUP) and BACKUP.parent == BACKUP.parent.resolve(),
        "unsafe backup destination",
    )
    require(inventory() == plan["members"], "source metadata changed")
    H["tracked_guard"]([SOURCE])
    process = H["process_guard"]([SOURCE])
    require(H["protected"]() == plan["protected_files"], "protected experiment state changed")
    free_before = shutil.disk_usage(REPO).free
    require(
        free_before > 2 * plan["source_allocated_bytes"] + 4 * 1024**3, "insufficient backup space"
    )
    publish(
        "execution_intent.json",
        dict(at=H["now"](), plan_id=plan["id"], process_guard=process, free_bytes=free_before),
    )
    BACKUP.mkdir()
    archive = BACKUP / "data_lake.tar.gz"
    temporary = BACKUP / "data_lake.tar.gz.partial"
    manifest = []
    with temporary.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=3, mtime=0) as packed:
            with tarfile.open(fileobj=packed, mode="w|") as tar:
                for row in plan["members"]:
                    path = REPO / row["path"]
                    require(identity(path) == row["identity"], "source changed during backup")
                    info = tar.gettarinfo(str(path), arcname=row["path"])
                    saved = dict(row)
                    if row["kind"] == "file":
                        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
                            reader = H["HashingReader"](stream)
                            tar.addfile(info, reader)
                            saved["content_sha256"] = reader.hash.hexdigest()
                    else:
                        tar.addfile(info)
                    require(identity(path) == row["identity"], "source changed while reading")
                    manifest.append(saved)
        raw.flush()
        os.fsync(raw.fileno())
    with tarfile.open(temporary, "r|gz") as tar:
        for member, row in zip(tar, manifest, strict=True):
            require(member.name == row["path"], "backup path or order mismatch")
            if row["kind"] == "file":
                require(
                    member.isfile() and member.size == row["identity"][3], "backup file mismatch"
                )
                with tar.extractfile(member) as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                require(digest == row["content_sha256"], "backup content mismatch")
            else:
                require(member.isdir(), "backup directory mismatch")
    os.rename(temporary, archive)
    manifest_path = BACKUP / "member_manifest.json.gz"
    with manifest_path.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as packed:
            packed.write(encode(manifest))
        raw.flush()
        os.fsync(raw.fileno())
    sync_directory(BACKUP)
    sync_directory(BACKUP.parent)
    archive_hash = sha(archive)
    publish(
        "backup_verified.json",
        dict(
            at=H["now"](),
            plan_id=plan["id"],
            archive=str(archive),
            archive_sha256=archive_hash,
            archive_bytes=archive.stat().st_size,
            verified_members=len(manifest),
            member_manifest=str(manifest_path),
            member_manifest_sha256=sha(manifest_path),
            all_regular_files_content_verified=True,
            backup_local_only=True,
        ),
    )
    require(inventory() == plan["members"], "source changed after backup")
    H["tracked_guard"]([SOURCE])
    process = H["process_guard"]([SOURCE])
    require(H["protected"]() == plan["protected_files"], "protected source changed before removal")
    removed, success, failure = [], False, None
    protected_unchanged = None
    try:
        for row in manifest:
            if row["kind"] != "file":
                continue
            path = REPO / row["path"]
            require(identity(path) == row["identity"], "file changed before unlink")
            path.unlink()
            removed.append(row)
        directories = sorted(
            (r for r in manifest if r["kind"] == "directory"),
            key=lambda r: len(Path(r["path"]).parts),
            reverse=True,
        )
        for row in directories:
            path = REPO / row["path"]
            require(identity(path)[:3] == row["identity"][:3], "directory identity changed")
            path.rmdir()
            removed.append(row)
        require(not any(SOURCE.iterdir()), "new data appeared; leave it untouched")
        protected_unchanged = H["protected"]() == plan["protected_files"]
        require(protected_unchanged, "protected source changed during cleanup")
        success = True
    except BaseException as exc:
        failure = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        backup_bytes = (
            sum(p.stat().st_blocks * 512 for p in BACKUP.iterdir()) + BACKUP.stat().st_blocks * 512
        )
        publish(
            "result.json",
            dict(
                at=H["now"](),
                plan_id=plan["id"],
                status="COMPLETE" if success else "PARTIAL_STOPPED_NO_RETRY",
                failure=failure,
                removed_members=len(removed),
                removed_source_allocated_bytes=sum(row["identity"][7] for row in removed),
                retained_backup_allocated_bytes=backup_bytes,
                archive=str(archive),
                archive_sha256=archive_hash,
                protected_files_unchanged=protected_unchanged,
                runtime_after=H["runtime"](),
                process_guard=process,
                free_bytes_before=free_before,
                free_bytes_after=shutil.disk_usage(REPO).free,
                disk_delta_not_attributed_only_to_cleanup=True,
                no_signals_GPU_API_or_training_changes=True,
                source_parent_retained=True,
                backup_local_only=True,
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
                    "source_allocated_bytes",
                    "removed_source_allocated_bytes",
                    "retained_backup_allocated_bytes",
                )
                if key in result
            }
        )
    )
