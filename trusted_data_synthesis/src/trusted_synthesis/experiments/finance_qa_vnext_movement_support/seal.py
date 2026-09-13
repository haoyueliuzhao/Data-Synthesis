"""Lossless compact publication of the independent diagnostic evidence."""

import argparse
import gzip
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .protocol import checked_record, encode, record, require, sha, write_once
from .run import diagnostic_code_snapshot, guarded_roots

JSON_FILES = (
    "policy.json",
    "archive_preflight.json",
    "protected_sources_before.json",
    "protected_sources_after.json",
    "diagnostic_code_before.json",
    "diagnostic_code_after.json",
    "fixture_dependencies.json",
    "scripted_control_plan.json",
    "original_witness_diagnostics.json",
    "qualification_funnel.json",
    "public_execution_signals.json",
    "scripted_interface_controls.json",
    "phase_zero_summary.json",
    "cohort_report.json",
)
COMPRESS = {
    "qualification_funnel.json",
    "public_execution_signals.json",
    "protected_sources_before.json",
    "protected_sources_after.json",
}


def compress_once(source, target):
    """Exclusive deterministic gzip, retaining the original; verify round trip."""
    source, target = Path(source), Path(target)
    require(
        not any(p.is_symlink() for p in (source, target, *source.parents, *target.parents)),
        "movement.compression_no_symlink",
    )
    raw = source.read_bytes()
    with target.open("xb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
            compressed.write(raw)
    require(gzip.decompress(target.read_bytes()) == raw, "movement.lossless_gzip_round_trip")
    return {
        "published_path": target.name,
        "published_bytes": target.stat().st_size,
        "published_sha256": sha(target),
        "canonical_path": source.name,
        "canonical_bytes": len(raw),
        "canonical_sha256": sha(raw),
        "compression": "gzip, mtime=0, empty filename; exact original decompression",
        "uncompressed_original_retained_locally": True,
    }


def seal(code_root, data_root):
    code_root, _, output = guarded_roots(code_root, data_root)
    report = checked_record(
        json.loads((output / "cohort_report.json").read_bytes()), "cohort_report"
    )
    before = checked_record(
        json.loads((output / "diagnostic_code_before.json").read_bytes()),
        "diagnostic_code_snapshot",
    )
    require(
        before == diagnostic_code_snapshot(code_root), "movement.executed_code_matches_publication"
    )
    plan = checked_record(
        json.loads((output / "scripted_control_plan.json").read_bytes()), "scripted_control_plan"
    )
    controls = checked_record(
        json.loads((output / "scripted_interface_controls.json").read_bytes()),
        "scripted_interface_controls",
    )
    require(
        controls["plan_id"] == plan["id"]
        and plan["case_count"] == controls["case_count"] == 410
        and plan["task_and_basis_order"]
        == [
            {"task_id": row["task_id"], "basis": row["requested_control_basis"]}
            for row in controls["cases"]
        ],
        "movement.scripted_controls_exact_frozen_plan_order",
    )
    members = []
    for name in JSON_FILES:
        source = output / name
        raw = source.read_bytes()
        require(encode(json.loads(raw)) == raw, "movement.canonical_JSON_evidence:" + name)
        if name in COMPRESS:
            member = compress_once(source, output / (name + ".gz"))
        else:
            member = {
                "published_path": name,
                "published_bytes": len(raw),
                "published_sha256": sha(raw),
                "canonical_path": name,
                "canonical_bytes": len(raw),
                "canonical_sha256": sha(raw),
                "compression": None,
            }
        members.append(member)
    junit = output / "cpu_tests.xml"
    require(junit.is_file(), "movement.final_CPU_tests_required")
    test_result = validate_junit(junit.read_bytes())
    members.append(
        {
            "published_path": junit.name,
            "published_bytes": junit.stat().st_size,
            "published_sha256": sha(junit),
            "compression": None,
        }
    )
    manifest = record(
        "phase_zero_artifact_manifest",
        cohort_report_id=report["id"],
        diagnostic_code_snapshot_id=before["id"],
        CPU_test_result=test_result,
        members=members,
        old_experiment_files_changed=0,
        excluded_local_draft="diagnosis_20260913",
        draft_is_not_added_to_registered_scientific_denominator=True,
        compressed_files_are_lossless_evidence_not_new_scientific_tasks=True,
    )
    write_once(output / "artifact_manifest.json", manifest)
    return manifest


def validate_junit(raw):
    suites = list(ET.fromstring(raw).iter("testsuite"))
    require(bool(suites), "movement.junit_test_suites")
    totals = {
        key: sum(int(suite.attrib.get(key, "0")) for suite in suites)
        for key in ["tests", "failures", "errors", "skipped"]
    }
    require(
        totals["tests"] > 0 and all(totals[key] == 0 for key in ["failures", "errors", "skipped"]),
        "movement.complete_passing_CPU_tests",
    )
    return {
        **totals,
        "junit_seconds": sum(float(suite.attrib.get("time", "0")) for suite in suites),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    result = seal(args.code_root, args.data_root)
    print(
        json.dumps(
            {
                "id": result["id"],
                "published_files": len(result["members"]) + 1,
                "published_bytes": sum(x["published_bytes"] for x in result["members"]),
            }
        )
    )


if __name__ == "__main__":
    main()
