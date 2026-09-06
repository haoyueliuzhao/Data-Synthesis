"""Read back persisted CPU data and publication bindings; no encoding or qualification."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.finance_qa_vnext_length_adaptation import (
    core,
    runner,
    source,
)
from trusted_synthesis.experiments.finance_qa_vnext_length_adaptation.guards import (
    guard_report,
    zero_execution_guard,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    require,
    sha,
)
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.loss import (
    decode_arrays,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    base = (
        root
        / "trusted_data_synthesis/artifacts/qa_vnext_length_adaptation/original_32768_v1_20260906"
    )
    with zero_execution_guard() as counts:
        prep_manifest = runner.verify(base / "preparation")
        manifest = runner.verify(base / "adaptation")
        condition = source.load(base / "preparation/condition.json")
        report = source.load(base / "adaptation/report.json")
        dataset = source.load(base / "adaptation/token_representations.json")
        packages = source.load(base / "adaptation/session_packages.json")
        cpu = source.load(base / "adaptation/cpu_loading.json")
        original_dataset = source.load(
            root
            / source.HISTORICAL_ROOT
            / "execution/analysis/supervision_candidates.json"
        )
        originals = {row["id"]: row for row in original_dataset["rows"]}
        records = {item["id"]: item for item in dataset["records"]}
        require(
            len(records) == dataset["fit_count"] == report["consumable_records"] == 34,
            "publication.record_count",
        )
        require(
            report["status"] == "complete"
            and packages["complete_session_packages"] == 2,
            "publication.complete",
        )
        require(
            {item["row_id"] for item in records.values()}
            == set(condition["candidate_ids"])
            == set(originals),
            "publication.candidate_set",
        )
        batches, seen = [], []
        for item in cpu["batches"]:
            summary = item["batch"]
            raw = (base / "adaptation" / item["path"]).read_bytes()
            require(sha(raw) == summary["npz_sha256"], "publication.npz_sha")
            arrays = decode_arrays(raw)
            require(set(arrays) == set(core.ARRAYS), "publication.npz_arrays")
            for i, token_id in enumerate(summary["token_record_ids"]):
                token = records[token_id]
                core.identity(token, "token_record")
                length = token["sequence_length"]
                for name in core.ARRAYS:
                    require(
                        np.array_equal(
                            arrays[name][i, :length],
                            np.asarray(token[name], dtype=np.int64),
                        ),
                        "publication.disk_token_array_mismatch",
                    )
                require(
                    summary["candidate_ids"][i] == token["row_id"],
                    "publication.batch_candidate_parent",
                )
                require(
                    token["target_raw_sha256"]
                    == originals[token["row_id"]]["target_raw_sha256"],
                    "publication.target_parent",
                )
                require(
                    np.all(arrays["labels"][i, length:] == -100)
                    and np.all(arrays["attention_mask"][i, length:] == 0),
                    "publication.disk_padding",
                )
                seen.append(token["row_id"])
            batches.append(
                {
                    "path": item["path"],
                    "sha256": sha(raw),
                    "shape": summary["shape"],
                    "disk_arrays_equal_token_records": True,
                }
            )
        require(len(seen) == len(set(seen)) == 34, "publication.exhaustive_cpu_rows")
        require(len(batches) == 18, "publication.batch_count")
        for package in packages["rows"]:
            require(
                package["expected_units"] == package["consumable_units"] == 17,
                "publication.package_units",
            )
            require(
                package["submission_kind_counts"]
                == {"action": 8, "update": 8, "final": 1},
                "publication.package_kinds",
            )
            require(
                package["t16_present_and_consumable"] is True
                and package["units"][-1]["display_turn"] == 17,
                "publication.late_steps",
            )
            for unit in package["units"]:
                token = records[unit["token_record_id"]]
                row = originals[unit["candidate_id"]]
                require(
                    token["session_id"] == row["session_id"] == package["session_id"]
                    and unit["display_turn"] == row["turn_index"] + 1,
                    "publication.package_source_parent",
                )
        implementation = source.load(base / "preparation/implementation.json")
        current_source = source.source_snapshot(root)
        require(
            current_source["files"] == implementation["files"],
            "publication.source_changed",
        )
        history = source.load(base / "preparation/history_inventory.json")
        require(
            source.history_inventory(root) == history, "publication.history_changed"
        )
        historical_binding = (
            root / source.HISTORICAL_ROOT / "preparation/tokenizer_binding.json"
        )
        require(
            historical_binding.read_bytes()
            == (base / "preparation/historical_tokenizer_binding.json").read_bytes(),
            "publication.old_binding_bytes",
        )
        protected_paths = [
            "trusted_data_synthesis/config/vtdo_qwen2_5_7b_500k.json",
            "trusted_data_synthesis/src/trusted_synthesis/canonical_json.py",
            *[
                "trusted_data_synthesis/src/trusted_synthesis/domains/finance/qa_vnext/"
                + name
                for name in (
                    "protocol.py",
                    "runtime.py",
                    "measurement.py",
                    "action_public_contract.py",
                    "update_public_contract.py",
                    "program_adapter.py",
                    "share_adapter.py",
                )
            ],
            "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_share_training_preflight/tokenization.py",
        ]
        protected = []
        for path in protected_paths:
            before = source.git(root, "show", source.PARENT_COMMIT + ":" + path)
            after = (root / path).read_bytes()
            require(before == after, "publication.protected_source_changed")
            protected.append(
                {"path": path, "sha256": sha(after), "identical_to_parent_commit": True}
            )
        tests_raw = args.junit.read_bytes()
        tests = ET.fromstring(tests_raw)
        suites = (
            [tests] if tests.tag == "testsuite" else list(tests.findall("testsuite"))
        )
        totals = {
            key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
            for key in ("tests", "errors", "failures", "skipped")
        }
        require(
            totals == {"tests": 27, "errors": 0, "failures": 0, "skipped": 0},
            "publication.test_results",
        )
        case_names = [
            case.attrib["name"]
            for suite in suites
            for case in suite.findall("testcase")
        ]
        require(
            "test_historical_public_api_reproduces_entire_old_dataset_exactly"
            in case_names
            and "test_actual_cli_prepare_run_and_readback" in case_names,
            "publication.required_tests",
        )
        for directory in ("preparation", "adaptation"):
            guarded = source.load(base / directory / "execution_guards.json")
            require(
                guarded["all_zero"] and not guarded["cuda_initialized"],
                "publication.execution_guards",
            )
        new_files = sorted(
            path
            for name in ("preparation", "adaptation")
            for path in (base / name).rglob("*")
            if path.is_file()
        )
        require(
            all(
                path.suffix in {".json", ".npz"} and not path.is_symlink()
                for path in new_files
            ),
            "publication.output_allowlist",
        )
        result = core.record(
            "publication_verification",
            preparation_manifest_id=prep_manifest["id"],
            adaptation_manifest_id=manifest["id"],
            adaptation_report_id=report["id"],
            representation_condition_id=condition["id"],
            source_commit=implementation["git_commit"],
            source_file_count=implementation["file_count"],
            source_files_unchanged=True,
            historical_inventory_id=history["id"],
            historical_file_count=history["file_count"],
            historical_byte_count=history["byte_count"],
            historical_files_unchanged=True,
            protected_source_checks=protected,
            old_binding_copy_byte_exact=True,
            tests=totals,
            junit_sha256=sha(tests_raw),
            cpu_disk_batches=batches,
            original_candidates=34,
            consumable_cpu_records=34,
            complete_session_packages=2,
            before_publication_file_count=len(new_files),
            before_publication_byte_count=sum(
                path.stat().st_size for path in new_files
            ),
            source_inputs_already_published=True,
            raw_content_rewritten=False,
            credential_files_opened=False,
            student_weights_in_output=False,
            verification_scope="persisted byte/array/source bindings only; no re-tokenization, qualification or model execution",
        )
    guards = guard_report(counts)
    require(
        guards["all_zero"] and not guards["cuda_initialized"],
        "publication.zero_execution",
    )
    store = runner.Store(args.output.resolve())
    store.json("report.json", result)
    store.json("execution_guards.json", guards)
    store.bytes("tests.xml", tests_raw)
    store.bytes("verify.py", Path(__file__).read_bytes())
    store.seal(phase="publication_verification", condition_id=condition["id"])
    print(canonical_json_bytes(result).decode())


if __name__ == "__main__":
    main()
