"""Second fixed-scope cold-storage pass using the hash-pinned, verified engine.

No old plan is resumed. Content is backed up and verified before source removal.
"""

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
ART = REPO / "trusted_data_synthesis/artifacts"
ENGINE_PATH = ART / "storage_cleanup_20261010_cold_archive_01/archive.py"
ENGINE_SHA256 = "ee61e44d33c7c7f9fbe51d2d5a4239d953eb73a79f55d5e2ab552a551493318e"
with ENGINE_PATH.open("rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != ENGINE_SHA256:
        raise RuntimeError("frozen archival engine changed")
spec = importlib.util.spec_from_file_location("fixed_cold_storage_engine", ENGINE_PATH)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

engine.OUTPUT = ART / "storage_cleanup_20261010_cold_archive_02"
engine.BACKUP = ART / "cold_archive_20261010_02"
engine.__file__ = str(Path(__file__).resolve())  # Bind this scope wrapper into its new plan.
engine.PUBLICATIONS = []  # The four earlier gzip originals were already cleared.
FINQA = ART / "finance_research_20260928/finqa_v6_01"
INPUT_ROOTS = [
    FINQA / path
    for path in (
        "review_revision_01/inputs",
        "review_revision_02/inputs",
        "review_revision_03/slot_inputs",
        "v12_rereview_01/requests",
    )
]
QA_RUNTIME_ROOTS = [
    ART / path
    for path in (
        "qa_vnext_task_build/runtime_20260911",
        "qa_vnext_surface_build/runtime_20260912",
    )
]
QA_DATABASES = [
    ART / path
    for path in (
        "qa_vnext_task_build/runtime_20260911/qa_build.sqlite3",
        "qa_vnext_task_build/runtime_20260911/native_fact_qa.sqlite3",
        "qa_vnext_surface_build/runtime_20260912/native_fact_qa.sqlite3",
        "qa_vnext_surface_build/runtime_20260912/rewrite_budget.sqlite3",
    )
]
INTENTS = ART / "qa_vnext_fixed_kernel_value/delayed_C_B_confirmation_cache_20260922/budget/intents"
RAW = REPO / "raw_financial_data_lake"
TRUSTED = REPO / "trusted_data_synthesis"
TOOL_CACHE_ROOTS = [
    root / name
    for root in (RAW, TRUSTED)
    for name in (".mypy_cache", ".pytest_cache", ".ruff_cache")
    if (root / name).is_dir()
]
BYTECODE_ROOTS = sorted(
    {
        path
        for root in (RAW, TRUSTED / "src", TRUSTED / "scripts", TRUSTED / "tests")
        for path in root.rglob("__pycache__")
        if path.is_dir()
    }
)
CACHE_SOURCE_FILES = set()
engine.SCOPES = [
    engine.VTDO,
    *[root.parent for root in INPUT_ROOTS],
    *QA_RUNTIME_ROOTS,
    INTENTS.parent,
    *TOOL_CACHE_ROOTS,
    *BYTECODE_ROOTS,
]
engine.EXPECTED = {
    "retired_review_inputs": (14438, 5064216576),
    "legacy_qa_databases_and_intents": (89152, 2186137600),
    "vtdo_small_text": (14904, 1253564416),
    "rebuildable_caches": (3635, 269164544),
}
engine.GROUPS = tuple(engine.EXPECTED)
require = engine.require


def selected():
    tracked, rows = engine.tracked_paths(), []

    def add(path, group):
        require(str(path) not in tracked, "tracked file must remain in place")
        rows.append(
            dict(path=str(path.relative_to(REPO)), group=group, identity=engine.ordinary(path))
        )

    for root in INPUT_ROOTS:
        require(root == root.resolve() and root.is_dir(), "redirected review input root")
        for path in sorted(root.rglob("*.json")):
            add(path, "retired_review_inputs")
    for path in QA_DATABASES:
        require(
            not any(path.parent.glob(path.name + "-*")),
            "database sidecar appeared; re-audit required",
        )
        add(path, "legacy_qa_databases_and_intents")
    for path in sorted(INTENTS.rglob("*.json")):
        add(path, "legacy_qa_databases_and_intents")
    adapter = engine.VTDO / "finance_phase1_mvp_v1/beneficiary_adapter"
    for path in sorted(engine.VTDO.rglob("*")):
        relative = str(path.relative_to(engine.VTDO))
        if path.suffix not in {".json", ".jsonl"} or path.is_relative_to(adapter):
            continue
        if re.search("report|manifest|index", relative, re.IGNORECASE) or str(path) in tracked:
            continue
        require(path.lstat().st_size < 1024**2, "large VTDO payload unexpectedly appeared")
        add(path, "vtdo_small_text")
    for root in TOOL_CACHE_ROOTS:
        require(root == root.resolve(), "redirected tool cache")
        for path in sorted(root.rglob("*")):
            if not path.is_dir():
                add(path, "rebuildable_caches")
    for root in BYTECODE_ROOTS:
        require(root == root.resolve(), "redirected bytecode cache")
        for path in sorted(root.glob("*.pyc")):
            try:
                source = Path(importlib.util.source_from_cache(str(path)))
            except ValueError:
                match = re.fullmatch(
                    r"(.+)\.cpython-[0-9]+-pytest-[0-9]+(?:\.[0-9]+)*\.pyc", path.name
                )
                if match is None:
                    continue
                source = root.parent / (match.group(1) + ".py")
            if not source.is_file():
                continue  # Retain bytecode without an available source file.
            require(
                source == source.resolve() and source.is_relative_to(REPO),
                "redirected bytecode source",
            )
            CACHE_SOURCE_FILES.add(source)
            add(path, "rebuildable_caches")
    require(len({row["path"] for row in rows}) == len(rows), "duplicate source")
    for group, (count, size) in engine.EXPECTED.items():
        subset = [row for row in rows if row["group"] == group]
        require(
            len(subset) == count and sum(row["identity"][7] for row in subset) == size,
            f"audited {group} changed",
        )
    return rows


original_protected = engine.protected


def protected():
    result = original_protected()
    for path in sorted(CACHE_SOURCE_FILES):
        result[str(path)] = engine.identity(path)
    return result


original_publish = engine.publish


def publish(name, body):
    if name == "plan.json":
        body = {
            **body,
            "authorization": "继续审计数据构成，清理或者压缩历史数据",
            "frozen_engine_path": str(ENGINE_PATH),
            "frozen_engine_sha256": ENGINE_SHA256,
            "scope_audit_sha256": engine.sha(engine.OUTPUT / "scope_and_dependencies.json"),
            "no_prior_cleanup_plan_resumed": True,
        }
    return original_publish(name, body)


engine.selected = selected
engine.protected = protected
engine.publish = publish


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "apply", "restore"])
    parser.add_argument("--group", choices=engine.GROUPS)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    if args.action == "restore":
        require(args.group and args.destination, "restore requires group and empty destination")
        result = engine.restore(args.group, args.destination)
    else:
        if args.action == "apply":
            plan = json.loads((engine.OUTPUT / "plan.json").read_text())
            require(
                plan["frozen_engine_sha256"] == ENGINE_SHA256
                and engine.sha(engine.OUTPUT / "scope_and_dependencies.json")
                == plan["scope_audit_sha256"],
                "frozen dependency or scope audit changed",
            )
        result = engine.prepare() if args.action == "prepare" else engine.apply()
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
