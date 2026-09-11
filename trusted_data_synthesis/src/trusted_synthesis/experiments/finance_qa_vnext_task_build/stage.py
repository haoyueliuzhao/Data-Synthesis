"""One zero-model task-build stage, with genuine first-20 and catalog batches."""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..finance_qa_vnext_task_panel.guards import execution_guard, guard_report
from . import factory, native_facts
from .archive import (
    OUTPUT,
    WORK,
    record,
    require,
    sha,
    validate_archive,
    validate_record,
    write_json,
)
from .protocol import policy

PACKAGE = "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_task_build"
CODE_FILES = [
    "raw_financial_data_lake/finraw/qa/semantic_constraints.py",
    "raw_financial_data_lake/finraw/db/client.py",
    "raw_financial_data_lake/finraw/qa/plans.py",
    "raw_financial_data_lake/finraw/qa/operators.py",
    "raw_financial_data_lake/finraw/qa/graph_patterns.py",
    "raw_financial_data_lake/finraw/qa/pipeline.py",
]


def freeze(root):
    root = Path(root).resolve()
    output = root / OUTPUT
    files = sorted(
        [*CODE_FILES, *[str(path.relative_to(root)) for path in (root / PACKAGE).glob("*.py")]]
    )
    require(not (output / "stage_freeze.json").exists(), "stage.new_freeze_only")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    members = []
    for relative in files:
        original = subprocess.check_output(["git", "show", head + ":" + relative], cwd=root)
        require(
            original == (root / relative).read_bytes(),
            "stage.code_committed_before_task_generation",
        )
        members.append({"path": relative, "sha256": sha(root / relative)})
    archived, refs = validate_archive(root)
    value = record(
        "stage_freeze",
        git_commit=head,
        rule=policy(),
        code=members,
        archived_kg_id=archived["kg_build_id"],
        archived_input_references=refs,
        scope="one new task factory stage, two QA Build batches sharing the same source/rules",
        created_at=datetime.now(timezone.utc).isoformat(),
        prior_source_diagnostics_known=True,
        production_task_outputs_observed_before_freeze=False,
    )
    write_json(output / "stage_freeze.json", value)
    return value


def run(root):
    root = Path(root).resolve()
    output = root / OUTPUT
    frozen = json.loads((output / "stage_freeze.json").read_bytes())
    validate_record(frozen, "stage_freeze")
    require(not (output / "run_started.json").exists(), "stage.one_run_per_frozen_revision")
    for member in frozen["code"]:
        require(sha(root / member["path"]) == member["sha256"], "stage.code_still_frozen")
    require(frozen["rule"] == policy(), "stage.rules_unchanged")
    write_json(
        output / "run_started.json",
        record(
            "run_start",
            stage_freeze_id=frozen["id"],
            started_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
    with execution_guard(online=False) as counters:
        native = native_facts.run(root, output)
        print(
            json.dumps(
                {
                    "native_fact_build": native["id"],
                    "kg_build_id": native["kg_build"]["kg_build_id"],
                    "source_observation_count": native["source_observation_count"],
                }
            ),
            flush=True,
        )
        report = factory.run(root, output, native)
    guards = guard_report(counters, phase="native_fact_QA_task_factory_zero_model")
    write_json(output / "execution_guards.json", guards)
    _, after = validate_archive(root)
    require(after == frozen["archived_input_references"], "stage.original_archive_unchanged")
    write_json(
        output / "run_completed.json",
        record(
            "run_completion",
            stage_freeze_id=frozen["id"],
            report_id=report["id"],
            completed_at=datetime.now(timezone.utc).isoformat(),
            guard_report_id=guards["id"],
            original_archive_unchanged=True,
        ),
    )
    seal(root)
    return report


def seal(root):
    output = Path(root).resolve() / OUTPUT
    members = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path != output / "manifest.json":
            require(not path.is_symlink(), "manifest.no_symlinks")
            members.append(
                {
                    "path": str(path.relative_to(output)),
                    "sha256": sha(path),
                    "bytes": path.stat().st_size,
                }
            )
    value = record(
        "manifest",
        members=members,
        runtime_SQLite_excluded=WORK,
        database_exports_are_actual_parent_rows=True,
    )
    write_json(output / "manifest.json", value)
    return value


def verify(root):
    root = Path(root).resolve()
    output = root / OUTPUT
    manifest = json.loads((output / "manifest.json").read_bytes())
    validate_record(manifest, "manifest")
    for member in manifest["members"]:
        path = output / member["path"]
        require(
            path.stat().st_size == member["bytes"] and sha(path) == member["sha256"],
            "verify.member_byte_identity",
        )
    actual = {
        str(path.relative_to(output))
        for path in output.rglob("*")
        if path.is_file() and path != output / "manifest.json"
    }
    require(actual == {row["path"] for row in manifest["members"]}, "verify.member_set_complete")
    catalog = json.loads((output / "catalog.json").read_bytes())
    validate_record(catalog, "fixed_task_catalog")
    identities = set()
    for item in catalog["tasks"]:
        bundle_path = output / item["path"]
        bundle = json.loads(bundle_path.read_bytes())
        validate_record(bundle, "TaskBundle")
        require(
            bundle["id"] == item["bundle_id"] and bundle["task_id"] == item["task_id"],
            "verify.catalog_task_parent",
        )
        require(item["task_id"] not in identities, "verify.no_duplicate_target")
        identities.add(item["task_id"])
        visible = json.loads((bundle_path.parent / "teacher_visible.json").read_bytes())
        require(
            visible == factory.teacher_messages(bundle), "verify.exact_whitelisted_public_messages"
        )
    return {
        "manifest_id": manifest["id"],
        "members": len(manifest["members"]),
        "tasks": len(identities),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["freeze", "run", "verify"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = {"freeze": freeze, "run": run, "verify": verify}[args.phase](args.root)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
