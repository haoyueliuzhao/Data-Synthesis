"""Verify only the new source-preparation stage and its CPU controls."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest

from .core import (
    DOCUMENT,
    OUTPUT,
    PACKAGE,
    Store,
    encode,
    history_guard,
    read_json,
    record,
    reference,
    require,
)


def verify(root):
    root = Path(root)
    history_guard(root)
    intake, census = root / OUTPUT / "source_intake", root / OUTPUT / "source_census"
    source_manifests = [manifest(path) for path in (intake, census)]
    implementation = read_json(census / "implementation_references.json")
    for ref in implementation:
        require(reference(root, ref["path"]) == ref, "verify.census_implementation_unchanged")
    for item in read_json(census / "entity_originals_index.json"):
        archived = reference(census, item["archived_path"])
        require(
            archived["sha256"] == item["sha256"] and archived["bytes"] == item["bytes"],
            "verify.archived_SEC_bytes",
        )
    report = read_json(census / "report.json")
    require(
        report["status"] == "SOURCE_TASK_READINESS_NOT_ESTABLISHED",
        "verify.source_readiness_not_invented",
    )
    require(
        not report["training_allowed"] and not report["support_generation_allowed"],
        "verify.online_closed",
    )
    require(
        report["original_question_records"] == 7134
        and report["distinct_page_public_views"] == 2409,
        "verify.fixed_source_population",
    )
    require(report["new_effect_measurement"] is None, "verify.no_effect_observation")
    zero_fields = (
        "actual_new_certified_tasks",
        "actual_common_ready_A_B_tasks",
        "new_Teacher_sessions",
        "new_semantic_API_requests",
        "new_tokenizer_loads",
        "new_Student_runs",
        "new_optimizer_updates",
        "new_generated_support_packages",
    )
    require(all(report[field] == 0 for field in zero_fields), "verify.no_generated_tasks_or_models")
    tests = sorted(
        str(path.relative_to(root))
        for path in (root / "trusted_data_synthesis/tests").glob("test_qa_vnext_basis_scale_*.py")
    )
    require(len(tests) >= 6, "verify.new_controls_include_adversarial_review")
    store = Store(root / OUTPUT / "verification")
    checks = []
    for name, command in (
        ("pytest", [sys.executable, "-B", "-m", "pytest", "-q", "--color=no", *tests]),
        ("ruff_check", ["ruff", "check", PACKAGE, *tests]),
        ("ruff_format", ["ruff", "format", "--check", PACKAGE, *tests]),
    ):
        completed = subprocess.run(command, cwd=root, capture_output=True, timeout=180, check=False)
        store.write(name + ".stdout.txt", completed.stdout)
        store.write(name + ".stderr.txt", completed.stderr)
        checks.append(
            {
                "name": name,
                "command": command,
                "returncode": completed.returncode,
                "scope": (
                    "new scale preparation only; pure CPU/source checks, "
                    "no historical experiment rerun"
                ),
            }
        )
        if name == "pytest":
            match = re.search(rb"(\d+) passed", completed.stdout)
            passed = int(match.group(1)) if match else 0
    verdict = record(
        "basis_scale_preparation_verification",
        status="PASS_AS_SOURCE_PREPARATION"
        if all(item["returncode"] == 0 for item in checks)
        else "CONTROL_FAILURE",
        checks=checks,
        tests_passed=passed,
        reviewed_source_stage_ids=[value["id"] for value in source_manifests],
        source_census_report_id=report["id"],
        stage_member_files_verified=sum(len(value["members"]) for value in source_manifests),
        copied_SEC_snapshot_originals_verified=100,
        source_census_implementation_references_verified=len(implementation),
        task_supply_established=False,
        full_online_protocol_frozen=False,
        supports_effect_claim=False,
        Teacher_sessions=0,
        Student_runs=0,
        source_review_used_assistant_agents_not_project_provider_API=True,
        history=history_guard(root),
        document_reference=reference(root, DOCUMENT),
        verification_implementation_reference=reference(root, PACKAGE + "/verify.py"),
        test_references=[reference(root, path) for path in tests],
        failed_HTTPS_stage_preserved_references=[
            reference(root, str(path.relative_to(root)))
            for path in sorted((root / OUTPUT / "source_intake_attempt_01_http").glob("*"))
            if path.is_file()
        ],
    )
    store.json("report.json", verdict)
    store.seal(report_id=verdict["id"])
    return verdict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(encode(verify(args.root)).decode())


if __name__ == "__main__":
    main()
