"""One-shot cleanup of four audited historical gradient directories."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo


AUDIT = Path(__file__).resolve().parent
REPO = AUDIT.parents[2]
ART = REPO / "trusted_data_synthesis/artifacts"
VTDO = ART / "vtdo_experiment"
V13 = "finance_v13_gradient_projection_dev30_k3_v12_production_candidate_v14_20260804"
V22 = "finance_v22_development_exact_target_v1_20260808"
SCOPES = (
    VTDO / V13 / "state_gradients",
    VTDO / V13 / "common_token_gradients",
    VTDO / V13 / "differential_token_gradients",
    VTDO / V22 / "state_gradients",
)
STATUS = ART / "finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/six_gpu_queue_01/queue/status.json"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(name, value):
    with (AUDIT / name).open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def identity(path):
    assert path.is_relative_to(ART) and path.resolve() == path, str(path)
    s = path.lstat()
    assert stat.S_ISREG(s.st_mode), str(path)
    return dict(path=str(path.relative_to(REPO)), device=s.st_dev, inode=s.st_ino,
                size=s.st_size, allocated_bytes=s.st_blocks * 512, links=s.st_nlink,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns)


def discover():
    rows, retained = [], []
    for scope in SCOPES:
        assert scope.resolve() == scope and scope.is_dir(), str(scope)
        selected = sorted(scope.glob("*.safetensors"))
        assert selected, str(scope)
        chosen = set(selected)
        for path in selected:
            row = identity(path)
            assert row["links"] == 1, row
            rows.append(dict(group=str(scope.relative_to(VTDO)), **row))
        for path in sorted(scope.rglob("*")):
            assert not path.is_symlink(), str(path)
            if path.is_file() and path not in chosen:
                retained.append(identity(path))
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--", *[str(p.relative_to(REPO)) for p in SCOPES]],
        cwd=REPO,
    ).decode().split("\0")
    assert not {r["path"] for r in rows}.intersection(tracked), "tracked target"
    assert len({r["path"] for r in rows}) == len(rows)
    assert len(rows) == 1400, "audited target count changed"
    assert sum(r["allocated_bytes"] for r in rows) == 113116774400, "audited allocation changed"
    return rows, retained


def protected_points():
    root = ART / "qa_vnext_fixed_kernel_value/cross_market_calibration_cache_20260926/evaluation_01/points"
    metadata = sorted(root.glob("*/point.json"))
    assert len(metadata) == 9
    records = []
    for path in metadata:
        obj = json.loads(path.read_text())
        records.append(dict(kind="point_metadata", **identity(path)))
        for key in ("adapter", "origin_checkpoint"):
            value = Path(obj[key]["path"])
            if not value.is_absolute():
                value = path.parent / value
            records.append(dict(kind=key, **identity(value.resolve())))
    return records


def no_process_users():
    hits = []
    prefixes = tuple(str(scope) for scope in SCOPES)
    alias = "/home/zhuxinrui/datatmp/projects/Data-Synthesis"
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            values = [os.readlink(proc / "cwd"), os.readlink(proc / "exe")]
            values.extend(proc.joinpath("cmdline").read_bytes().decode(errors="replace").split("\0"))
            values.extend(line.split(None, 5)[-1] for line in proc.joinpath("maps").read_text().splitlines())
            for link in proc.joinpath("fd").iterdir():
                try:
                    values.append(os.readlink(link))
                except OSError:
                    pass
            for value in values:
                value = value.replace(alias, str(REPO))
                if any(prefix in value for prefix in prefixes):
                    hits.append(dict(pid=int(proc.name), candidate_reference=value))
        except (OSError, ProcessLookupError):
            continue
    assert not hits, hits


def runtime():
    status = json.loads(STATUS.read_text())
    assert not status["failures"], status["failures"]
    workers = []
    for row in status["active_children"]:
        fields = Path(f"/proc/{row['pid']}/stat").read_text().rsplit(")", 1)[1].split()
        assert fields[19] == str(row["birth"]) and fields[0] != "Z", row
        workers.append({key: row[key] for key in ("job_key", "pid", "birth", "gpu")})
    return dict(at=now(), heartbeat_at=status["at"], phase=status["phase"],
                workers=workers, queued=status["queued"], failures=status["failures"],
                disk_free_bytes=shutil.disk_usage(REPO).free)


def summary(rows):
    return {str(scope.relative_to(VTDO)): dict(
        files=sum(r["group"] == str(scope.relative_to(VTDO)) for r in rows),
        allocated_bytes=sum(r["allocated_bytes"] for r in rows if r["group"] == str(scope.relative_to(VTDO))),
    ) for scope in SCOPES}


def main():
    if sys.argv[1:] == ["plan"]:
        rows, retained = discover()
        protected = protected_points()
        assert not {r["path"] for r in rows}.intersection(r["path"] for r in protected)
        no_process_users()
        plan = dict(schema="historical_gradient_cleanup.v1", at=now(),
                    script_sha256=digest(Path(__file__)), files=rows,
                    retained_files=retained, protected_points=protected,
                    groups=summary(rows), before=runtime())
        write_new("plan.json", plan)
        print(json.dumps(dict(plan_sha256=digest(AUDIT / "plan.json"), groups=plan["groups"],
                              files=len(rows), retained_files=len(retained), protected_points=len(protected),
                              before=plan["before"]), ensure_ascii=False), flush=True)
        return
    assert len(sys.argv) == 3 and sys.argv[1] == "execute"
    assert not (AUDIT / "execution_intent.json").exists()
    assert not (AUDIT / "result.json").exists()
    assert digest(AUDIT / "plan.json") == sys.argv[2], "plan changed"
    plan = json.loads((AUDIT / "plan.json").read_text())
    assert digest(Path(__file__)) == plan["script_sha256"], "script changed"
    rows, retained = discover()
    assert rows == plan["files"] and retained == plan["retained_files"], "inventory changed"
    assert protected_points() == plan["protected_points"], "protected point changed"
    no_process_users()
    before = runtime()
    write_new("execution_intent.json", dict(at=now(), plan_sha256=sys.argv[2], before=before))
    deleted = []
    try:
        for row in rows:
            path = REPO / row["path"]
            assert identity(path) == {k: v for k, v in row.items() if k != "group"}, row["path"]
            path.unlink()
            deleted.append(row["path"])
        assert all(not (REPO / row["path"]).exists() for row in rows)
        assert [identity(REPO / r["path"]) for r in retained] == retained
        assert protected_points() == plan["protected_points"]
        after = runtime()
        result = dict(status="complete", at=now(), plan_sha256=sys.argv[2],
                      deleted_file_count=len(deleted), groups=summary(rows),
                      deleted_allocated_bytes=sum(r["allocated_bytes"] for r in rows),
                      retained_files_unchanged=len(retained), protected_files_unchanged=len(plan["protected_points"]),
                      before=before, after=after,
                      net_free_increase_bytes=after["disk_free_bytes"] - before["disk_free_bytes"],
                      backup_created=False, git_recovery_available=False)
    except BaseException as exc:
        write_new("result.json", dict(status="partial_failure", at=now(), deleted_paths=deleted,
                                       error=f"{type(exc).__name__}: {exc}"))
        raise
    write_new("result.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
