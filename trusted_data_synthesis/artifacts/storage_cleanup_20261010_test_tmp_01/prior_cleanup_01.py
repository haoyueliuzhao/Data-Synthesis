"""One-shot, verified recoverable archival of an exact unused test-fixture list.

No experiment/history/model/worktree directory is eligible. Back up and verify
every member before removing a source. The test_tmp parent itself is retained.
"""

import argparse
import gzip
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
OUTPUT = REPO / "trusted_data_synthesis/artifacts/storage_cleanup_20261010_test_tmp_01"
TEMP = REPO / "trusted_data_synthesis/artifacts/test_tmp"
RUFF = REPO / ".ruff_cache"
RUN = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01/production_resume_01"
)


def require(value, message):
    if not value:
        raise RuntimeError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def publish(name, body):
    value = {**body, "id": hashlib.sha256(encode(body)).hexdigest()}
    with (OUTPUT / name).open("xb") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2).encode() + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return value


def identity(path):
    value = Path(path).lstat()
    return [
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
        value.st_nlink,
        value.st_blocks * 512,
    ]


def admitted_root(path):
    path = Path(path)
    require(
        path.is_absolute() and path == path.resolve() and path.is_dir(),
        "candidate must be an existing non-symlink directory",
    )
    require(
        path == RUFF or path.parent == TEMP,
        "only exact test_tmp children or the root Ruff cache are eligible",
    )
    require(path != TEMP and path != REPO and path != OUTPUT, "broad deletion root forbidden")
    cursor = path
    while cursor != REPO:
        require(not cursor.is_symlink(), "redirected candidate ancestor forbidden")
        cursor = cursor.parent


def inventory(root):
    admitted_root(root)
    entries = []

    def visit(path):
        ident = identity(path)
        mode = ident[2]
        kind = (
            "directory"
            if stat.S_ISDIR(mode)
            else "file"
            if stat.S_ISREG(mode)
            else "symlink"
            if stat.S_ISLNK(mode)
            else None
        )
        require(
            kind is not None and ident[0] == REPO.stat().st_dev,
            "special file or mount boundary forbidden",
        )
        require(kind != "file" or ident[6] == 1, "hardlinked test file must be retained")
        item = dict(path=str(path.relative_to(REPO)), kind=kind, identity=ident)
        if kind == "symlink":
            item["target"] = os.readlink(path)
            target = (path.parent / item["target"]).resolve(strict=False)
            require(target.is_relative_to(TEMP), "fixture link escapes protected test_tmp scope")
        entries.append(item)
        if kind == "directory":
            for child in sorted(path.iterdir()):
                visit(child)

    visit(root)
    return entries


def birth(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def process_guard(roots):
    hits, inaccessible, inspected = [], [], 0
    candidates = [str(path) for path in roots]

    def inspect_value(pid, channel, value):
        for root in candidates:
            if root in value:
                hits.append(dict(pid=pid, channel=channel, candidate=root))

    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or proc.name == str(os.getpid()):
            continue
        comm = None
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            pid = int(proc.name)
            comm = (proc / "comm").read_text().strip()
            inspect_value(pid, "cwd", os.readlink(proc / "cwd"))
            for value in (proc / "cmdline").read_bytes().split(b"\0"):
                inspect_value(pid, "argv", value.decode(errors="replace"))
            for item in (proc / "environ").read_bytes().split(b"\0"):
                key, _, value = item.partition(b"=")
                if key in {
                    b"PYTHONPATH",
                    b"VIRTUAL_ENV",
                    b"HF_HOME",
                    b"TRANSFORMERS_CACHE",
                    b"TMPDIR",
                    b"TMP",
                    b"TEMP",
                    b"PYTEST_ADDOPTS",
                    b"RUFF_CACHE_DIR",
                }:
                    inspect_value(pid, "selected_environment", value.decode(errors="replace"))
            for fd in (proc / "fd").iterdir():
                try:
                    inspect_value(pid, "fd", os.readlink(fd))
                except (FileNotFoundError, ProcessLookupError):
                    pass
            for line in (proc / "maps").read_text().splitlines():
                if "/" in line:
                    inspect_value(pid, "maps", "/" + line.split("/", 1)[1])
            inspected += 1
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            inaccessible.append(dict(pid=int(proc.name), comm=comm))
    result = dict(
        inspected_same_account_processes=inspected,
        hits=hits,
        inaccessible_same_account_processes=inaccessible,
        other_accounts_not_claimed_audited=True,
    )
    require(not hits, "a candidate is in use; keep it")
    require(
        all(item["comm"] in {"sshd", "systemd", "(sd-pam)"} for item in inaccessible),
        "unknown inaccessible process; cannot safely clear tests",
    )
    return result


def tracked_guard(roots):
    tracked = subprocess.check_output(
        [
            "git",
            "-C",
            str(REPO),
            "ls-files",
            "-z",
            "--",
            *[str(path.relative_to(REPO)) for path in roots],
        ],
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    require(not tracked, "Git-tracked content must be retained")


def protected():
    context = RUN / "contexts/seed137/c_only/step1192_outer/context/record.json"
    value = json.loads(context.read_text())
    paths = [
        REPO / "AGENTS.md",
        RUN / "protocol/record.json",
        RUN / "implementation/record.json",
        context,
        Path(value["checkpoint"]["record"]["path"]),
        Path(value["checkpoint"]["state"]["path"]),
    ]
    paths.extend((RUN / "implementation").glob("*.py"))
    paths.extend(Path(value["feedback"]["root"]).glob("*/record.json"))
    return {str(path): identity(path) for path in paths}


def runtime():
    queue = json.loads((RUN / "queue/status.json").read_text())
    controller = json.loads((RUN / "launch_01/record.json").read_text())
    workers = [controller, *queue["active_children"]]
    return dict(
        phase=queue["phase"],
        queue_at=queue["at"],
        processes=[
            dict(pid=item["pid"], expected_birth=item["birth"], observed_birth=birth(item["pid"]))
            for item in workers
        ],
    )


def prepare():
    require(not (OUTPUT / "plan.json").exists(), "one fixed plan only")
    roots = sorted(path for path in TEMP.iterdir() if path.is_dir() and not path.is_symlink())
    require(len(roots) == 132, "audited 132 test directories changed; re-audit first")
    if RUFF.exists():
        roots.append(RUFF)
    tracked_guard(roots)
    before = process_guard(roots)
    rows = []
    for root in roots:
        entries = inventory(root)
        rows.append(
            dict(
                path=str(root),
                allocated_bytes=sum(x["identity"][7] for x in entries),
                entry_count=len(entries),
                metadata_sha256=hashlib.sha256(encode(entries)).hexdigest(),
            )
        )
    return publish(
        "plan.json",
        dict(
            schema="unused_tests_recoverable_archive_plan.v1",
            at=now(),
            script_sha256=sha(__file__),
            roots=rows,
            process_guard=before,
            source_allocated_bytes=sum(row["allocated_bytes"] for row in rows),
            protected_files=protected(),
            runtime=runtime(),
            protected_scopes=[
                "all formal experiments",
                "all worktrees",
                "all model assets",
                ".venv",
                ".git",
            ],
            preserve_test_tmp_parent=True,
            backup_must_verify_before_any_source_removal=True,
        ),
    )


class HashingReader:
    def __init__(self, stream):
        self.stream, self.hash = stream, hashlib.sha256()

    def read(self, size):
        result = self.stream.read(size)
        self.hash.update(result)
        return result


def apply():
    plan = json.loads((OUTPUT / "plan.json").read_text())
    require(
        plan["id"]
        == hashlib.sha256(encode({k: v for k, v in plan.items() if k != "id"})).hexdigest(),
        "plan changed",
    )
    require(sha(__file__) == plan["script_sha256"], "cleanup implementation changed after planning")
    require(not (OUTPUT / "execution_intent.json").exists(), "no automatic retry of cleanup")
    roots = [Path(row["path"]) for row in plan["roots"]]
    tracked_guard(roots)
    before_process = process_guard(roots)
    require(
        protected() == plan["protected_files"], "protected experiment source changed before cleanup"
    )
    entries = []
    for root, row in zip(roots, plan["roots"], strict=True):
        current = inventory(root)
        require(
            hashlib.sha256(encode(current)).hexdigest() == row["metadata_sha256"],
            "candidate changed after planning",
        )
        entries.extend(current)
    free_before = shutil.disk_usage(REPO).free
    require(
        free_before > 2 * plan["source_allocated_bytes"] + 4 * 1024**3,
        "not enough room for verified reversible archival",
    )
    publish(
        "execution_intent.json",
        dict(
            at=now(),
            plan_id=plan["id"],
            process_guard=before_process,
            runtime=runtime(),
            free_bytes=free_before,
        ),
    )
    archive = OUTPUT / "test_fixtures.tar.gz"
    temporary = OUTPUT / "test_fixtures.tar.gz.partial"
    manifest = []
    with temporary.open("xb") as output:
        with gzip.GzipFile(fileobj=output, mode="wb", compresslevel=6, mtime=0) as packed:
            with tarfile.open(fileobj=packed, mode="w|") as tar:
                for item in entries:
                    path = REPO / item["path"]
                    require(
                        identity(path) == item["identity"], "candidate changed while backing up"
                    )
                    info = tarfile.TarInfo(item["path"])
                    info.mode = stat.S_IMODE(item["identity"][2])
                    info.mtime = item["identity"][4] / 10**9
                    row = dict(item)
                    if item["kind"] == "directory":
                        info.type = tarfile.DIRTYPE
                        tar.addfile(info)
                    elif item["kind"] == "symlink":
                        info.type, info.linkname = tarfile.SYMTYPE, item["target"]
                        tar.addfile(info)
                    else:
                        info.size = item["identity"][3]
                        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                        with os.fdopen(fd, "rb") as source:
                            reader = HashingReader(source)
                            tar.addfile(info, reader)
                            row["content_sha256"] = reader.hash.hexdigest()
                    require(identity(path) == item["identity"], "source changed during backup")
                    manifest.append(row)
        output.flush()
        os.fsync(output.fileno())
    # Re-read the completed compressed archive and compare every source member.
    with tarfile.open(temporary, "r|gz") as tar:
        count = 0
        for member, item in zip(tar, manifest, strict=True):
            require(member.name == item["path"], "backup member order/name differs")
            if item["kind"] == "file":
                require(
                    member.isfile() and member.size == item["identity"][3],
                    "backup file shape differs",
                )
                with tar.extractfile(member) as stream:
                    value = hashlib.sha256()
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        value.update(chunk)
                require(value.hexdigest() == item["content_sha256"], "backup content differs")
            elif item["kind"] == "directory":
                require(member.isdir(), "backup directory missing")
            else:
                require(member.issym() and member.linkname == item["target"], "backup link differs")
            count += 1
        require(count == len(manifest), "incomplete archive verification")
    os.rename(temporary, archive)
    with (OUTPUT / "member_manifest.json.gz").open("xb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as packed:
            packed.write(encode(manifest))
        stream.flush()
        os.fsync(stream.fileno())
    archive_hash = sha(archive)
    publish(
        "backup_verified.json",
        dict(
            at=now(),
            plan_id=plan["id"],
            archive=str(archive),
            archive_sha256=archive_hash,
            archive_bytes=archive.stat().st_size,
            verified_members=len(manifest),
            all_regular_files_content_verified=True,
            member_manifest_sha256=sha(OUTPUT / "member_manifest.json.gz"),
        ),
    )
    tracked_guard(roots)
    last_process_guard = process_guard(roots)
    require(protected() == plan["protected_files"], "protected sources changed before removal")
    require(shutil.rmtree.avoids_symlink_attacks, "descriptor-safe tree removal unavailable")
    removed = []
    try:
        for root, row in zip(roots, plan["roots"], strict=True):
            current = inventory(root)
            require(
                hashlib.sha256(encode(current)).hexdigest() == row["metadata_sha256"],
                "source changed after archive verification; retain it",
            )
            # Root is one explicit, validated test directory, never the parent.
            shutil.rmtree(root)
            require(not os.path.lexists(root), "test directory still exists after cleanup")
            removed.append(row)
        require(protected() == plan["protected_files"], "protected sources changed during cleanup")
    finally:
        after_free = shutil.disk_usage(REPO).free
        evidence_bytes = sum(p.stat().st_blocks * 512 for p in OUTPUT.iterdir() if p.is_file())
        publish(
            "result.json",
            dict(
                at=now(),
                plan_id=plan["id"],
                status="COMPLETE" if len(removed) == len(roots) else "PARTIAL_STOPPED_NO_RETRY",
                removed_roots=removed,
                removed_source_allocated_bytes=sum(r["allocated_bytes"] for r in removed),
                archive=str(archive),
                archive_sha256=archive_hash,
                archive_retained=True,
                evidence_and_backup_allocated_bytes=evidence_bytes,
                estimated_net_reclaimed_bytes=sum(r["allocated_bytes"] for r in removed)
                - evidence_bytes,
                free_bytes_before=free_before,
                free_bytes_after=after_free,
                disk_free_delta_not_attributed_only_to_cleanup=True,
                protected_files_unchanged=protected() == plan["protected_files"],
                final_process_guard=last_process_guard,
                runtime_after=runtime(),
                no_process_signals=True,
                no_GPU_or_API_calls=True,
                backup_fixture_payload_not_for_git_commit=True,
                restore_requires_review_then_extraction_to_original_paths_without_overwriting_new_files=True,
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
                for key in [
                    "id",
                    "status",
                    "source_allocated_bytes",
                    "removed_source_allocated_bytes",
                    "estimated_net_reclaimed_bytes",
                ]
                if key in result
            }
        )
    )
