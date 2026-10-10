"""Fixed-scope lossless cold storage; verify all backups before any source unlink.

Restore into a new empty directory, then review before moving files back.
Git-tracked files, small audit records, models and live FinQA inputs stay in place.
"""

import argparse
import gzip
import hashlib
import json
import os
import runpy
import shutil
import stat
import subprocess
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
ART = REPO / "trusted_data_synthesis/artifacts"
OUTPUT = ART / "storage_cleanup_20261010_cold_archive_01"
BACKUP = ART / "cold_archive_20261010_01"
HELPER = ART / "storage_cleanup_20261010_test_tmp_01/cleanup.py"
ZSTD = "/home/zhuxinrui/datatmp/miniconda3/bin/zstd"
H = runpy.run_path(str(HELPER))
require, identity, sha, encode = (H[key] for key in ("require", "identity", "sha", "encode"))
VTDO = ART / "vtdo_experiment"
FINANCE = ART / "finance_research_20260928"
WALLETS = [
    FINANCE / "finqa_v6_01" / name
    for name in ("v10_wallet_prelaunch_AalG7W", "v10_funding_backup_2mcs6281")
]
JOBS = [FINANCE / name / "jobs" for name in ("audit_followup_01", "reference_revision_01")]
RUNTIMES = [
    ART / name / "runtime_20260912"
    for name in (
        "qa_vnext_readiness_revision",
        "qa_vnext_eval_readiness",
        "qa_vnext_catalog_bridge",
    )
]
PUBLICATIONS = [
    ART / "qa_vnext_eval_readiness/eval_readiness_20260912",
    ART / "qa_vnext_catalog_bridge/catalog_bridge_20260912",
]
SCOPES = [VTDO, *WALLETS, *JOBS, *RUNTIMES]
GROUPS = ("vtdo_text", "finance_payloads", "qa_databases")
EXPECTED = {
    "vtdo_text": (978, 14666502144),
    "finance_payloads": (50342, 8148070400),
    "qa_databases": (12, 2875015168),
    "existing_gzip": (4, 1107484672),
}


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


def write_manifest(name, rows):
    path = OUTPUT / name
    with path.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as packed:
            packed.write(encode(rows))
        raw.flush()
        os.fsync(raw.fileno())
    sync_directory(OUTPUT)
    return sha(path)


def load_manifest(name, expected_hash):
    path = OUTPUT / name
    require(path.parent == OUTPUT and sha(path) == expected_hash, "member manifest changed")
    with gzip.open(path, "rb") as stream:
        return json.load(stream)


def tracked_paths():
    roots = [*SCOPES, *PUBLICATIONS]
    raw = subprocess.check_output(
        [
            "git",
            "-C",
            str(REPO),
            "ls-files",
            "-z",
            "--",
            *[str(p.relative_to(REPO)) for p in roots],
        ],
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    return {str(REPO / os.fsdecode(path)) for path in raw.split(b"\0") if path}


def ordinary(path):
    require(path.is_relative_to(REPO) and path == path.resolve(), "redirected source")
    info = identity(path)
    require(
        stat.S_ISREG(info[2]) and info[6] == 1 and info[0] == REPO.stat().st_dev,
        "not an ordinary single-link source",
    )
    return info


def validate_record(value, kind):
    body = {k: v for k, v in value.items() if k != "id"}
    require(
        body["schema_version"] == "finance_qa_vnext_task_build.v1." + kind, "record schema mismatch"
    )
    require(
        value["id"] == kind + ":" + hashlib.sha256(encode(body)).hexdigest(), "record id mismatch"
    )


def publication_rows():
    rows = []
    for root in PUBLICATIONS:
        directory = root.with_name(root.name + "_publication")
        index = json.loads((directory / "index.json").read_text())
        manifest = json.loads((root / "manifest.json").read_text())
        validate_record(index, "lossless_publication")
        validate_record(manifest, "manifest")
        require(index["artifact"] == str(root.relative_to(REPO)), "wrong publication root")
        require(
            index["parent"]
            == dict(
                directory=str(root.relative_to(REPO)),
                manifest_id=manifest["id"],
                manifest_sha256=sha(root / "manifest.json"),
            ),
            "publication parent mismatch",
        )
        members = {item["path"]: item for item in manifest["members"]}
        require(len(index["members"]) == 2, "publication scope changed")
        for item in index["members"]:
            member = item["original"]
            require(
                member["path"]
                in {
                    "panels/confirm/parents/qa_candidates/0000.json",
                    "panels/confirm/parents/qa_candidates/0001.json",
                },
                "unexpected original",
            )
            require(members[member["path"]] == member, "original manifest mismatch")
            path, compressed = root / member["path"], directory / item["gzip_path"]
            require(
                compressed.parent == directory and compressed == compressed.resolve(),
                "redirected gzip",
            )
            rows.append(
                dict(
                    group="existing_gzip",
                    path=str(path.relative_to(REPO)),
                    identity=ordinary(path),
                    content_sha256=member["sha256"],
                    logical_bytes=member["bytes"],
                    gzip_path=str(compressed),
                    gzip_identity=identity(compressed),
                    gzip_sha256=item["gzip_sha256"],
                    gzip_bytes=item["gzip_bytes"],
                )
            )
    return rows


def selected():
    tracked, rows = tracked_paths(), []

    def add(path, group):
        require(str(path) not in tracked, "tracked content must remain in place")
        rows.append(dict(path=str(path.relative_to(REPO)), group=group, identity=ordinary(path)))

    for path in sorted(VTDO.rglob("*")):
        if (
            path.suffix in {".json", ".jsonl"}
            and path.lstat().st_size >= 1024**2
            and "report" not in path.name.lower()
            and str(path) not in tracked
        ):
            add(path, "vtdo_text")
    for root in WALLETS:
        for path in sorted(root.glob("wallet.sqlite3*")):
            require(
                path.name in {"wallet.sqlite3", "wallet.sqlite3-wal", "wallet.sqlite3-shm"},
                "unexpected wallet sidecar",
            )
            add(path, "finance_payloads")
    for root, variants in zip(JOBS, (("H0", "H1"), ("Direct-DSL", "H1-R")), strict=True):
        for model in ("base", "static11_step240"):
            for variant in variants:
                for offset in ("000", "030", "060", "090"):
                    job = root / f"{model}_{variant}_{offset}"
                    for kind in ("episodes", "events"):
                        payload = job / "generation" / kind
                        require(
                            payload.is_dir() and payload == payload.resolve(),
                            "unexpected job payload path",
                        )
                        for path in sorted(payload.rglob("*")):
                            if not path.is_dir():
                                add(path, "finance_payloads")
    for root in RUNTIMES:
        for path in sorted(root.rglob("*")):
            if ".sqlite3" in path.name:
                require(
                    path.name.endswith((".sqlite3", ".sqlite3-wal", ".sqlite3-shm")),
                    "unexpected database sidecar",
                )
                add(path, "qa_databases")
    rows.extend(publication_rows())
    require(len({row["path"] for row in rows}) == len(rows), "duplicate source")
    require(
        all(str(REPO / row["path"]) not in tracked for row in rows), "tracked original forbidden"
    )
    for group, (count, size) in EXPECTED.items():
        subset = [row for row in rows if row["group"] == group]
        require(
            len(subset) == count and sum(row["identity"][7] for row in subset) == size,
            f"audited {group} changed",
        )
    return rows


def preserved(rows):
    excluded = {row["path"] for row in rows}
    entries = []
    for root in SCOPES:
        for path in sorted(root.rglob("*")):
            relative = str(path.relative_to(REPO))
            info = identity(path)
            if relative not in excluded and not stat.S_ISDIR(info[2]):
                entries.append([relative, info])
    return dict(count=len(entries), metadata_sha256=hashlib.sha256(encode(entries)).hexdigest())


def protected():
    result = H["protected"]()
    adapter = VTDO / "finance_phase1_mvp_v1/beneficiary_adapter"
    for path in adapter.iterdir():
        if path.is_file():
            result[str(path)] = identity(path)
    for root in PUBLICATIONS:
        result[str(root / "manifest.json")] = identity(root / "manifest.json")
        for path in root.with_name(root.name + "_publication").iterdir():
            if path.is_file():
                result[str(path)] = identity(path)
    return result


def prepare():
    require(
        not (OUTPUT / "plan.json").exists() and not os.path.lexists(BACKUP),
        "new plan and backup directory required",
    )
    rows = selected()
    guard = H["process_guard"]([*SCOPES, *PUBLICATIONS])
    member_hash = write_manifest("plan_members.json.gz", rows)
    return publish(
        "plan.json",
        dict(
            at=H["now"](),
            script_sha256=sha(__file__),
            helper_sha256=sha(HELPER),
            zstd_sha256=sha(ZSTD),
            member_manifest_sha256=member_hash,
            groups=EXPECTED,
            source_allocated_bytes=sum(row["identity"][7] for row in rows),
            preserved_files=preserved(rows),
            protected_files=protected(),
            process_guard=guard,
            runtime=H["runtime"](),
            max_parallel_packers=3,
            zstd_threads_per_packer=2,
            zstd_level=6,
            preserve_all_directories=True,
            content_backups_required_before_any_unlink=True,
            git_tracked_files_excluded=True,
            authorization="继续释放空间，此外一些目前不用的数据也可以考虑做无损压缩处理",
        ),
    )


def verify_existing(rows):
    checked = []
    for row in rows:
        if row["group"] != "existing_gzip":
            continue
        path, compressed = REPO / row["path"], Path(row["gzip_path"])
        require(
            ordinary(path) == row["identity"] and identity(compressed) == row["gzip_identity"],
            "publication files changed",
        )
        require(
            compressed.stat().st_size == row["gzip_bytes"]
            and sha(compressed) == row["gzip_sha256"],
            "gzip identity mismatch",
        )
        require(
            path.stat().st_size == row["logical_bytes"] and sha(path) == row["content_sha256"],
            "original no longer matches science manifest",
        )
        with gzip.open(compressed, "rb") as stream:
            count, digest = 0, hashlib.sha256()
            for block in iter(lambda: stream.read(1024**2), b""):
                count += len(block)
                require(count <= row["logical_bytes"], "unexpected gzip expansion")
                digest.update(block)
        require(
            count == row["logical_bytes"] and digest.hexdigest() == row["content_sha256"],
            "gzip does not reproduce original",
        )
        require(
            ordinary(path) == row["identity"] and identity(compressed) == row["gzip_identity"],
            "publication changed during check",
        )
        with compressed.open("rb") as stream:
            os.fsync(stream.fileno())
        sync_directory(compressed.parent)
        checked.append(
            dict(path=row["path"], gzip_path=str(compressed), sha256=row["content_sha256"])
        )
    return checked


def pack(group, rows):
    archive = BACKUP / (group + ".tar.zst")
    temporary = BACKUP / (group + ".tar.zst.partial")
    manifest = []
    with temporary.open("xb") as raw:
        process = subprocess.Popen(
            [ZSTD, "-q", "-T2", "-6", "-c"],
            stdin=subprocess.PIPE,
            stdout=raw,
            stderr=subprocess.PIPE,
        )
        try:
            with tarfile.open(fileobj=process.stdin, mode="w|") as tar:
                for row in rows:
                    path = REPO / row["path"]
                    require(ordinary(path) == row["identity"], "source changed before pack")
                    info = tar.gettarinfo(str(path), arcname=row["path"])
                    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
                        reader = H["HashingReader"](stream)
                        tar.addfile(info, reader)
                    require(ordinary(path) == row["identity"], "source changed during pack")
                    manifest.append(
                        dict(
                            path=row["path"],
                            size=row["identity"][3],
                            mode=stat.S_IMODE(row["identity"][2]),
                            mtime_ns=row["identity"][4],
                            sha256=reader.hash.hexdigest(),
                        )
                    )
            process.stdin.close()
            require(
                process.wait() == 0,
                "zstd pack failed: " + process.stderr.read().decode(errors="replace"),
            )
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()
        raw.flush()
        os.fsync(raw.fileno())
    verify_tar(temporary, manifest)
    os.rename(temporary, archive)
    sync_directory(BACKUP)
    manifest_name = group + "_members.json.gz"
    manifest_hash = write_manifest(manifest_name, manifest)
    result = dict(
        group=group,
        archive=str(archive),
        archive_bytes=archive.stat().st_size,
        archive_sha256=sha(archive),
        member_manifest=manifest_name,
        member_manifest_sha256=manifest_hash,
        verified_members=len(manifest),
        source_allocated_bytes=sum(row["identity"][7] for row in rows),
    )
    publish(group + "_verified.json", dict(at=H["now"](), **result))
    print(
        json.dumps(
            dict(
                group=group,
                status="BACKUP_VERIFIED",
                members=len(manifest),
                archive_bytes=result["archive_bytes"],
            )
        ),
        flush=True,
    )
    return result


def verify_tar(archive, manifest, destination=None):
    process = subprocess.Popen(
        [ZSTD, "-q", "-d", "-c", str(archive)], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as tar:
            for member, row in zip(tar, manifest, strict=True):
                relative = Path(row["path"])
                require(
                    not relative.is_absolute() and ".." not in relative.parts, "unsafe archive path"
                )
                require(
                    member.isfile() and member.name == row["path"] and member.size == row["size"],
                    "archive membership mismatch",
                )
                sink = None
                target = None
                try:
                    if destination is not None:
                        target = destination / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        require(
                            target.parent.resolve().is_relative_to(destination),
                            "restore parent redirected",
                        )
                        sink = os.fdopen(
                            os.open(
                                target,
                                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                row["mode"] & 0o777,
                            ),
                            "wb",
                        )
                    with tar.extractfile(member) as stream:
                        digest = hashlib.sha256()
                        for block in iter(lambda: stream.read(1024**2), b""):
                            digest.update(block)
                            if sink is not None:
                                sink.write(block)
                    require(digest.hexdigest() == row["sha256"], "archive content mismatch")
                    if sink is not None:
                        sink.flush()
                        os.fsync(sink.fileno())
                finally:
                    if sink is not None:
                        sink.close()
                if target is not None:
                    os.chmod(target, row["mode"] & 0o777)
                    os.utime(target, ns=(row["mtime_ns"], row["mtime_ns"]))
        for _ in iter(lambda: process.stdout.read(1024**2), b""):
            pass
        require(
            process.wait() == 0,
            "zstd verification failed: " + process.stderr.read().decode(errors="replace"),
        )
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()


def apply():
    plan = json.loads((OUTPUT / "plan.json").read_text())
    require(
        plan["id"]
        == hashlib.sha256(encode({k: v for k, v in plan.items() if k != "id"})).hexdigest(),
        "plan changed",
    )
    require(
        sha(__file__) == plan["script_sha256"]
        and sha(HELPER) == plan["helper_sha256"]
        and sha(ZSTD) == plan["zstd_sha256"],
        "implementation changed",
    )
    require(
        not (OUTPUT / "execution_intent.json").exists() and not os.path.lexists(BACKUP),
        "no automatic retry or backup overwrite",
    )
    rows = load_manifest("plan_members.json.gz", plan["member_manifest_sha256"])
    require(selected() == rows, "candidate inventory changed")
    require(
        protected() == plan["protected_files"] and preserved(rows) == plan["preserved_files"],
        "protected files changed",
    )
    guard = H["process_guard"]([*SCOPES, *PUBLICATIONS])
    free_before = shutil.disk_usage(REPO).free
    require(
        free_before > 2 * plan["source_allocated_bytes"] + 4 * 1024**3, "insufficient staging room"
    )
    publish(
        "execution_intent.json",
        dict(
            at=H["now"](),
            plan_id=plan["id"],
            process_guard=guard,
            free_bytes=free_before,
            runtime=H["runtime"](),
        ),
    )
    BACKUP.mkdir()
    sync_directory(BACKUP.parent)
    existing = verify_existing(rows)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(pack, group, [row for row in rows if row["group"] == group])
            for group in GROUPS
        ]
        receipts = [future.result() for future in futures]
    publish(
        "backup_verified.json",
        dict(
            at=H["now"](),
            plan_id=plan["id"],
            archives=receipts,
            existing_publications=existing,
            all_contents_verified_before_any_source_unlink=True,
        ),
    )
    require(selected() == rows, "source changed after verified backup")
    require(
        protected() == plan["protected_files"] and preserved(rows) == plan["preserved_files"],
        "protected files changed before removal",
    )
    guard = H["process_guard"]([*SCOPES, *PUBLICATIONS])
    removed, success, failure = [], False, None
    protected_same, preserved_same = None, None
    try:
        for row in rows:
            path = REPO / row["path"]
            require(ordinary(path) == row["identity"], "source changed before unlink")
            path.unlink()
            removed.append(row)
        require(
            all(not os.path.lexists(REPO / row["path"]) for row in rows),
            "source unexpectedly reappeared",
        )
        protected_same = protected() == plan["protected_files"]
        preserved_same = preserved(rows) == plan["preserved_files"]
        require(protected_same and preserved_same, "protected or preserved files changed")
        success = True
    except BaseException as exc:
        failure = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        archive_bytes = sum(p.stat().st_blocks * 512 for p in BACKUP.iterdir())
        audit_bytes = sum(p.stat().st_blocks * 512 for p in OUTPUT.iterdir() if p.is_file())
        publish(
            "result.json",
            dict(
                at=H["now"](),
                plan_id=plan["id"],
                status="COMPLETE" if success else "PARTIAL_STOPPED_NO_RETRY",
                failure=failure,
                removed_files=len(removed),
                removed_source_allocated_bytes=sum(row["identity"][7] for row in removed),
                new_archive_allocated_bytes=archive_bytes,
                audit_allocated_bytes_before_result=audit_bytes,
                estimated_net_reclaimed_bytes=sum(row["identity"][7] for row in removed)
                - archive_bytes
                - audit_bytes,
                protected_files_unchanged=protected_same,
                all_non_target_scoped_files_metadata_unchanged=preserved_same,
                retained_files_checked=plan["preserved_files"]["count"],
                directories_preserved=True,
                backups_local_only=True,
                free_bytes_before=free_before,
                free_bytes_after=shutil.disk_usage(REPO).free,
                disk_delta_not_attributed_only_to_cleanup=True,
                process_guard=guard,
                runtime_after=H["runtime"](),
                no_GPU_API_or_experiment_process_signals=True,
                content_recoverable_but_original_inode_ctime_ACL_not_promised=True,
            ),
        )
    return json.loads((OUTPUT / "result.json").read_text())


def restore(group, destination):
    require(group in GROUPS, "use the existing publication restore helper for existing_gzip")
    destination = Path(destination)
    require(
        destination.is_absolute()
        and destination == destination.resolve()
        and destination.is_dir()
        and not any(destination.iterdir()),
        "restore destination must be an existing empty canonical directory",
    )
    receipt = json.loads((OUTPUT / (group + "_verified.json")).read_text())
    require(
        receipt["id"]
        == hashlib.sha256(encode({k: v for k, v in receipt.items() if k != "id"})).hexdigest(),
        "receipt changed",
    )
    archive = Path(receipt["archive"])
    require(
        archive == BACKUP / (group + ".tar.zst") and sha(archive) == receipt["archive_sha256"],
        "archive identity changed",
    )
    members = load_manifest(receipt["member_manifest"], receipt["member_manifest_sha256"])
    verify_tar(archive, members, destination)
    sync_directory(destination)
    return dict(
        status="RESTORED_TO_ISOLATED_DIRECTORY",
        group=group,
        files=len(members),
        destination=str(destination),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "apply", "restore"])
    parser.add_argument("--group", choices=GROUPS)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    if args.action == "restore":
        require(args.group and args.destination, "restore requires --group and --destination")
        result = restore(args.group, args.destination)
    else:
        result = prepare() if args.action == "prepare" else apply()
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "id",
                    "status",
                    "source_allocated_bytes",
                    "removed_files",
                    "estimated_net_reclaimed_bytes",
                    "destination",
                )
                if key in result
            }
        ),
        flush=True,
    )
