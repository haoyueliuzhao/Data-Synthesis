"""Persisted panel evidence/CPU readback and publication checks, without re-execution."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import numpy as np
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import (
    runner as online,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    identity,
    read_json,
    record,
    require,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_directory,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.qualification import (
    _Artifacts,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.stage import (
    history_inventory,
    preserved_execution_sources,
)
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.loss import (
    decode_arrays,
)

JUNIT_FILES = {
    "initial_component_66": "/tmp/qa_task_panel_component_tests.xml",
    "final_component_72": "/tmp/qa_task_panel_component_final_tests.xml",
    "initial_runner_share_observer_defect": "/tmp/qa_task_panel_runner_initial_tests.xml",
    "fixed_runner_3": "/tmp/qa_task_panel_runner_fixed_tests.xml",
    "actual_committed_1": "/tmp/qa_task_panel_actual_committed_tests.xml",
}


def load(path):
    return read_json(path.read_bytes())


def inventory(directory):
    return {
        path.relative_to(directory).as_posix(): {"bytes": len(raw), "sha256": sha(raw)}
        for path in sorted(directory.rglob("*"))
        if path.is_file()
        for raw in (path.read_bytes(),)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    base = (
        root
        / "trusted_data_synthesis/artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906"
    )
    preparation, execution = base / "preparation", base / "execution"
    analysis, reanalysis = execution / "analysis", base / "reanalysis"
    with execution_guard(online=False) as calls:
        manifests = []
        for directory, kind in (
            (preparation, "preparation_manifest"),
            (execution, "execution_manifest"),
            (analysis, "analysis_manifest"),
            (reanalysis, "analysis_manifest"),
        ):
            value = verify_directory(directory, kind=kind)
            manifests.append(
                {
                    "path": directory.relative_to(base).as_posix(),
                    "id": value["id"],
                    "files": len(value["members"]) + 1,
                }
            )
        original_files, recreated_files = inventory(analysis), inventory(reanalysis)
        require(original_files == recreated_files, "publication.analysis_not_byte_identical")
        implementation = load(preparation / "implementation.json")
        verify_source_snapshot(root, implementation)
        preservation = preserved_execution_sources(root)
        require(
            preservation == load(preparation / "source_preservation.json"),
            "publication.source_preservation",
        )
        history = history_inventory(root)
        require(
            history == load(preparation / "history_inventory.json"), "publication.history_immutable"
        )
        registrations = load(preparation / "registrations.json")
        condition = load(preparation / "condition.json")
        report = load(analysis / "report.json")
        rows = load(analysis / "supervision_candidates.json")["rows"]
        tokens = load(analysis / "token_representations.json")
        packages = load(analysis / "session_packages.json")
        cpu = load(analysis / "cpu_loading.json")
        rows_by_id = {row["id"]: row for row in rows}
        tokens_by_id = {item["id"]: item for item in tokens["records"]}
        packages_by_label = {item["label"]: item for item in packages["rows"]}
        event_counts, rejected_counts, per_session, actual_times = Counter(), Counter(), [], []
        candidate_expected, call_count, qualified_count = [], 0, 0
        for reg in registrations:
            label = reg["label"]
            directory = execution / "sessions" / label
            value = verify_directory(directory, kind="online_session_manifest")
            manifests.append(
                {
                    "path": directory.relative_to(base).as_posix(),
                    "id": value["id"],
                    "files": len(value["members"]) + 1,
                }
            )
            for component in ("runtime", "transport"):
                files = _Artifacts(directory / component)
                manifests.append(
                    {
                        "path": (directory / component).relative_to(base).as_posix(),
                        "id": files.manifest["id"],
                        "files": len(files.files) + 1,
                    }
                )
            session = load(directory / "runtime/session.json")
            qual = load(directory / "qualification.json")
            require(
                qual == load(analysis / f"qualifications/{label}.json"),
                "publication.qualification_saved_binding",
            )
            identity(qual, "qualification")
            ledger = load(directory / "transport/ledger.json")
            require(
                len(ledger["attempts"]) == qual["provider_attempt_count"] <= 32,
                "publication.session_attempts",
            )
            call_count += len(ledger["attempts"])
            for attempt in ledger["attempts"]:
                reservation = load(directory / "transport" / attempt["paths"]["reservation"])
                actual_times.append(reservation["reserved_at_utc"])
            kinds, rejected = Counter(), Counter()
            for event in session["events"]:
                if event["receipt"]["admitted"]:
                    kinds[event["parsed"]["kind"]] += 1
                else:
                    rejected[event["receipt"]["error_code"]] += 1
            event_counts.update(kinds)
            rejected_counts.update(rejected)
            local_rows = [row for row in rows if row["session_id"] == session["id"]]
            exported = load(analysis / f"exports/{label}.json")
            require(local_rows == exported["rows"], "publication.original_export_rows")
            package = packages_by_label[label]
            if qual["qualified"] is True:
                qualified_count += 1
                admitted = [event for event in session["events"] if event["receipt"]["admitted"]]
                require(
                    len(local_rows) == len(admitted) == package["expected_units"],
                    "publication.actual_package_denominator",
                )
                for row, event in zip(local_rows, admitted, strict=True):
                    require(
                        row["submission_id"] == event["submission"]["id"]
                        and row["turn_index"] == event["sequence"],
                        "publication.original_candidate_event",
                    )
                    candidate_expected.append(row["id"])
            else:
                require(
                    not local_rows
                    and package["complete"] is False
                    and package["positive_eligible"] is False,
                    "publication.failed_prefix_not_exported",
                )
            presentation = load(analysis / f"request_presentation/{label}.json")
            require(
                presentation["verified_actual_http_requests"] == len(ledger["attempts"])
                and presentation["all_full_task_publication"] is True,
                "publication.actual_request_publication",
            )
            per_session.append(
                {
                    "label": label,
                    "task_group": reg["task_group"],
                    "qualification_id": qual["id"],
                    "status": qual["status"],
                    "actual_attempts": len(ledger["attempts"]),
                    "admitted_kinds": dict(kinds),
                    "rejection_counts": dict(rejected),
                    "candidate_rows": len(local_rows),
                    "complete_package": package["complete"],
                    "projection_status": qual["projection_status"],
                    "depth_scope": qual["depth_scope"],
                    "depth_metrics": qual["depth_metrics"],
                }
            )
        require(candidate_expected == [row["id"] for row in rows], "publication.candidate_order")
        require(
            call_count == report["provider_attempt_count"] == 152 <= 512,
            "publication.total_attempts",
        )
        require(qualified_count == 15 and len(registrations) == 16, "publication.outcome_inventory")
        loaded, disk_batches = [], []
        for item in cpu["batches"]:
            batch = item["batch"]
            raw = (analysis / item["path"]).read_bytes()
            require(
                sha(raw) == batch["npz_sha256"] and len(raw) == batch["npz_byte_count"],
                "publication.cpu_file_hash",
            )
            arrays = decode_arrays(raw)
            require(
                set(arrays) == {"input_ids", "labels", "attention_mask", "target_mask"},
                "publication.cpu_array_set",
            )
            require(
                all(
                    value.dtype == np.int64 and list(value.shape) == batch["shape"]
                    for value in arrays.values()
                ),
                "publication.cpu_array_shape_dtype",
            )
            for index, token_id in enumerate(batch["token_record_ids"]):
                token = tokens_by_id[token_id]
                identity(token, "task_panel_token_representation")
                row = rows_by_id[token["row_id"]]
                size = token["sequence_length"]
                require(
                    token["consumable_token_representation"] is True and size <= 32768,
                    "publication.cpu_consumable",
                )
                for name in arrays:
                    require(
                        np.array_equal(arrays[name][index, :size], token[name]),
                        "publication.cpu_exact_record_arrays",
                    )
                mask = arrays["target_mask"][index].astype(bool)
                require(
                    np.all(arrays["labels"][index, ~mask] == -100),
                    "publication.cpu_non_target_labels",
                )
                require(
                    np.array_equal(arrays["labels"][index, mask], arrays["input_ids"][index, mask]),
                    "publication.cpu_target_labels",
                )
                require(
                    not mask[0] and np.all(arrays["attention_mask"][index, :-1][mask[1:]] == 1),
                    "publication.cpu_causal_predecessors",
                )
                require(
                    np.all(arrays["attention_mask"][index, size:] == 0)
                    and np.all(arrays["input_ids"][index, size:] == batch["pad_token_id"]),
                    "publication.cpu_dynamic_padding",
                )
                require(
                    row["session_id"] == token["session_id"] == batch["session_id"]
                    and token["target_raw_sha256"] == row["target_raw_sha256"],
                    "publication.cpu_candidate_parent",
                )
                loaded.append(row["id"])
            disk_batches.append(
                {
                    "path": item["path"],
                    "sha256": sha(raw),
                    "shape": batch["shape"],
                    "actual_arrays_equal_records": True,
                }
            )
        require(
            len(loaded) == len(set(loaded)) == len(rows) == tokens["fit_count"] == 113,
            "publication.all_candidates_loaded",
        )
        require(
            len(disk_batches) == 64 and packages["complete_session_packages"] == 15,
            "publication.cpu_package_counts",
        )
        tests, xml_files = [], {}
        for name, path in JUNIT_FILES.items():
            data = Path(path).read_bytes()
            xml = ET.fromstring(data)
            suites = [xml] if xml.tag == "testsuite" else list(xml.findall("testsuite"))
            totals = {
                key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
                for key in ("tests", "failures", "errors", "skipped")
            }
            tests.append({"name": name, **totals, "sha256": sha(data), "bytes": len(data)})
            xml_files[f"tests/{name}.xml"] = data
        final = [
            item
            for item in tests
            if item["name"] in {"final_component_72", "fixed_runner_3", "actual_committed_1"}
        ]
        require(
            sum(item["tests"] for item in final) == 76
            and all(item["errors"] == item["failures"] == item["skipped"] == 0 for item in final),
            "publication.final_tests",
        )
        for directory in (preparation, execution, analysis, reanalysis):
            guard = load(directory / "execution_guards.json")
            require(
                guard["all_zero"] is True and guard["cuda_initialized"] is False,
                "publication.stage_guards",
            )
        details = dict(
            source_commit=implementation["source_commit"],
            implementation_id=implementation["id"],
            condition_id=condition["id"],
            report_id=report["id"],
            checked_manifests=manifests,
            checked_manifest_count=len(manifests),
            analysis_file_count=len(original_files),
            analysis_byte_count=sum(item["bytes"] for item in original_files.values()),
            reanalysis_all_files_byte_identical=True,
            source_python_file_count=len(implementation["members"]),
            preserved_predecessor_python_file_count=preservation["file_count"],
            source_files_unchanged=True,
            historical_inventory_id=history["id"],
            historical_file_count=history["file_count"],
            historical_byte_count=history["byte_count"],
            historical_files_unchanged=True,
            actual_attempts=call_count,
            admitted_kind_counts=dict(event_counts),
            rejection_counts=dict(rejected_counts),
            session_rows=per_session,
            qualified_count=qualified_count,
            candidate_count=len(rows),
            token_fit_count=tokens["fit_count"],
            token_not_fit_count=tokens["not_fit_count"],
            complete_session_packages=packages["complete_session_packages"],
            cpu_disk_batches=disk_batches,
            earliest_reservation=min(actual_times),
            latest_reservation=max(actual_times),
            reservation_times_are_not_exact_session_end_times=True,
            tests=tests,
            final_distinct_tests=76,
            test_controls_are_not_model_samples=True,
        )
    guarded = guard_report(calls, phase="publication_readback")
    # This optional local credential read only checks for accidental publication;
    # it is outside the zero-execution readback and never transmits or logs the key.
    credential_bytes = online._credential(root / "trusted_data_synthesis/.env").encode()
    matched = [
        path.relative_to(base).as_posix()
        for path in base.rglob("*")
        if path.is_file() and credential_bytes in path.read_bytes()
    ]
    require(not matched, "publication.credential_bytes_found")
    del credential_bytes
    store = DurableStore(args.output.resolve())
    store.json("execution_guards.json", guarded)
    report = record(
        "task_panel_publication_verification",
        **details,
        exact_credential_byte_matches=0,
        credential_read_only_for_local_secret_scan=True,
        credential_published=False,
        new_provider_calls_by_verification=0,
        runtime_or_financial_operation_executions_by_verification=0,
        student_weight_loads=0,
        student_forward_calls=0,
        GPU_jobs=0,
        scope=(
            "persisted records, manifest/byte identity and actual CPU arrays; "
            "no new sampling or qualification execution"
        ),
    )
    for name, data in xml_files.items():
        store.write(name, data)
    store.write("verify.py", Path(__file__).read_bytes())
    store.json("report.json", report)
    seal_directory(store, kind="task_panel_publication_manifest", report_id=report["id"])
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "id",
                    "actual_attempts",
                    "qualified_count",
                    "candidate_count",
                    "complete_session_packages",
                    "checked_manifest_count",
                    "analysis_file_count",
                    "reanalysis_all_files_byte_identical",
                    "historical_file_count",
                    "final_distinct_tests",
                    "exact_credential_byte_matches",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
