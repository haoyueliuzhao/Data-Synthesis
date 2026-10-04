"""Second audited historical cleanup, reusing immutable first-pass safety guards."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
AUDIT = Path(__file__).resolve().parent
REPO = AUDIT.parents[2]
EVIDENCE_SHA256 = "511a23386bb80641634e49da33d8e1bf309764fd83c3ce1aa10e1ce7e866c0b4"
HELPER_SHA256 = "1e6af39b698fac1a9c9a6a5f3e1d2b19b6d9bc4e637f86fbc33745f2cfe040ab"
HELPER = REPO / "trusted_data_synthesis/artifacts/storage_cleanup_20261004_gradients_01/cleanup.py"
assert hashlib.sha256(HELPER.read_bytes()).hexdigest() == HELPER_SHA256, "safety helper changed"
assert hashlib.sha256((AUDIT / "audit.json").read_bytes()).hexdigest() == EVIDENCE_SHA256, "audit changed"
EVIDENCE = json.loads((AUDIT / "audit.json").read_text())
SCOPES = tuple(REPO / row["scope"] for row in EVIDENCE["groups"])
QA = REPO / "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/delayed_C_recovery_cache_20260921/A_delayed_c_29"
assert len(SCOPES) == 15 and len(set(SCOPES)) == 15
assert len(EVIDENCE["files"]) == 1542
assert sum(r["allocated_bytes"] for r in EVIDENCE["files"]) == 80069025792

spec = importlib.util.spec_from_file_location("audited_cleanup_guards", HELPER)
guards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guards)
guards.AUDIT = AUDIT
guards.__file__ = __file__
guards.SCOPES = SCOPES
original_protected_points = guards.protected_points


def expected_identity(row):
    return dict(path=row["path"], device=row["device"], inode=row["inode"],
                size=row["size"], allocated_bytes=row["allocated_bytes"], links=row["nlink"],
                mtime_ns=row["mtime_ns"], ctime_ns=row["ctime_ns"])


def discover():
    rows = []
    for source in EVIDENCE["files"]:
        path = REPO / source["path"]
        assert path.parent in SCOPES
        if path.parent == QA / "feedback":
            assert path.suffix == ".pt" and len(path.stem) == 4 and path.stem.isdigit()
            assert 1 <= int(path.stem) <= 630
        else:
            assert path.is_relative_to(guards.VTDO) and path.suffix == ".safetensors"
        actual = guards.identity(path)
        assert actual == expected_identity(source), str(path)
        assert actual["links"] == 1, str(path)
        rows.append(dict(group=str(path.parent.relative_to(REPO)), **actual))
    assert len({r["path"] for r in rows}) == len(rows)
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--", *[str(p.relative_to(REPO)) for p in SCOPES]],
        cwd=REPO).decode().split("\0")
    selected = {REPO / row["path"] for row in rows}
    assert not {r["path"] for r in rows}.intersection(tracked), "tracked target"
    retained = []
    for scope in SCOPES:
        assert scope.resolve() == scope and scope.is_dir()
        for path in sorted(scope.rglob("*")):
            assert not path.is_symlink(), str(path)
            if path.is_file() and path not in selected:
                retained.append(guards.identity(path))
    return rows, retained


def protected_points():
    result = original_protected_points()
    assert len(result) == 27
    for row in EVIDENCE["protected_qa"]:
        path = REPO / row["path"]
        assert path in (QA / "feedback/0631.pt", QA / "population.pt")
        actual = guards.identity(path)
        assert actual == expected_identity(row), str(path)
        result.append(dict(kind="qa_final_cumulative_or_population", **actual))
    assert len(result) == 29
    return result


def summary(rows):
    result = {}
    for scope in SCOPES:
        name = str(scope.relative_to(REPO))
        subset = [r for r in rows if r["group"] == name]
        result[name] = dict(files=len(subset), allocated_bytes=sum(r["allocated_bytes"] for r in subset))
    return result


guards.discover = discover
guards.protected_points = protected_points
guards.summary = summary
if __name__ == "__main__":
    guards.main()
