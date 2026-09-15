"""Independent query revision: explicit null public search metadata means absent.

Only label/description search-text concatenation changes. Raw snapshots, returned
metadata, every other tool, exact filters and pagination remain untouched. This
module does not monkeypatch any existing runtime or launch model evaluation.
"""

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value")
STAGE_A = BASE / "delivery_diagnostic_20260915/stage_A"
DEFAULT_OUTPUT = STAGE_A / "tool_repair"
RUNTIME = Path(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "finance_qa_vnext_eval_readiness/runtime.py"
)
REPAIR_VERSION = "public_query_nullable_metadata:v1:20260915"


def absent_if_null(value):
    """Do not coerce zero/False/lists or any other previously invalid type."""
    return "" if value is None else value


def repaired_snapshot_sources_class(runtime):
    """A separate class, not a global replacement of SnapshotSources.query."""

    class NullSafeQuerySnapshotSources(runtime.SnapshotSources):
        query_repair_version = REPAIR_VERSION

        def query(self, arguments):
            runtime.require(
                isinstance(arguments, dict)
                and set(arguments)
                <= {
                    "source_id",
                    "concept",
                    "label_contains",
                    "unit",
                    "start",
                    "end",
                    "offset",
                    "limit",
                },
                "source.query_arguments",
            )
            source_id = arguments["source_id"]
            payload = self._payload(source_id)
            offset, limit = runtime._page(arguments)
            selected, total = [], 0
            for namespace, concepts in sorted(payload.get("facts", {}).items()):
                for tag, concept in sorted(concepts.items()):
                    if "concept" in arguments and arguments["concept"] != namespace + ":" + tag:
                        continue
                    if (
                        "label_contains" in arguments
                        and str(arguments["label_contains"]).casefold()
                        not in (
                            tag
                            + " "
                            + absent_if_null(concept.get("label", ""))
                            + " "
                            + absent_if_null(concept.get("description", ""))
                        ).casefold()
                    ):
                        continue
                    for unit, rows in sorted(concept.get("units", {}).items()):
                        if "unit" in arguments and unit != arguments["unit"]:
                            continue
                        for index, raw in enumerate(rows):
                            if any(
                                key in arguments and raw.get(key) != arguments[key]
                                for key in ("start", "end")
                            ):
                                continue
                            if offset <= total < offset + limit:
                                selected.append(
                                    self._row(source_id, namespace, tag, unit, index, raw, concept)
                                )
                            total += 1
            return {
                "source_id": source_id,
                "records": selected,
                "offset": offset,
                "total": total,
                "next_offset": offset + len(selected) if offset + len(selected) < total else None,
                "selection_basis": "only_public_source_and_explicit_query_arguments",
                "full_original_snapshot_accessible": True,
            }

    return NullSafeQuerySnapshotSources


def _encoded(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _read(root, path, maximum):
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ValueError("repair.input_containment")
    before = path.stat()
    if not 0 < before.st_size <= maximum:
        raise ValueError("repair.bounded_input")
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("repair.stable_input")
    return json.loads(raw), {
        "path": str(path.relative_to(root)),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _metadata_examples(payload, arguments, source):
    def escape(item):
        return item.replace("~", "~0").replace("/", "~1")

    examples = []
    for namespace, concepts in sorted(payload.get("facts", {}).items()):
        for tag, concept in sorted(concepts.items()):
            if "concept" in arguments and arguments["concept"] != namespace + ":" + tag:
                continue
            for field in ("label", "description"):
                if field in concept and concept[field] is None:
                    examples.append(
                        {
                            "source": source,
                            "public_metadata_pointer": (
                                f"/facts/{escape(namespace)}/{escape(tag)}/{field}"
                            ),
                            "raw_value": None,
                            "field": field,
                            "first_example_is_first_null_encountered_by_exact_query_order": (
                                not examples
                            ),
                        }
                    )
                    if len(examples) == 2:
                        return examples
    return examples


def reproduce(root, output, source_root=None):
    root, output = root.resolve(), output.resolve()
    source_root = root if source_root is None else source_root.resolve()
    if not output.is_relative_to(root / STAGE_A) or output.exists():
        raise ValueError("repair.new_stage_A_output_only")
    sys.path.insert(0, str(root / "trusted_data_synthesis/src"))
    runtime = importlib.import_module(
        "trusted_synthesis.experiments.finance_qa_vnext_eval_readiness.runtime"
    )
    runtime_raw_before = (root / RUNTIME).read_bytes()
    tracked_blob = subprocess.check_output(
        ["git", "rev-parse", "HEAD:" + str(RUNTIME)], cwd=root, text=True
    ).strip()
    blob_raw = b"blob " + str(len(runtime_raw_before)).encode() + b"\0" + runtime_raw_before
    runtime.require(
        hashlib.sha1(blob_raw).hexdigest() == tracked_blob, "repair.old_src_matches_HEAD"
    )
    report, report_reference = _read(root, root / STAGE_A / "report.json", 4 * 1024 * 1024)
    case = next(
        row
        for row in report["cases"]
        if row["flags"]["query_source_string_concatenation_NoneType_error_observed"]
    )
    ledger, ledger_reference = _read(root, root / STAGE_A / case["ledger_path"], 128 * 1024)
    example = ledger["nullable_query_error_examples"][0]
    arguments, descriptor = example["arguments"], example["source_descriptor"]
    metadata = descriptor["complete_original_snapshot"]
    public_path = source_root / metadata["path"]
    payload, source_reference = _read(source_root, public_path, 16 * 1024 * 1024)
    runtime.require(
        source_reference["bytes"] == metadata["bytes"]
        and source_reference["sha256"] == metadata["sha256"],
        "repair.actual_original_public_snapshot_identity",
    )
    original = runtime.SnapshotSources(root, [descriptor])
    repaired = repaired_snapshot_sources_class(runtime)(root, [descriptor])
    # Identity was verified above from actual file bytes. Both calls only read
    # this same in-memory payload; neither _payload needs to reopen the file.
    original.payloads[descriptor["source_id"]] = payload
    repaired.payloads[descriptor["source_id"]] = payload
    old_error = None
    try:
        original.query(arguments)
    except TypeError as error:
        old_error = str(error)
    runtime.require(old_error == example["observed_error"], "repair.exact_saved_error_reproduced")
    actual = repaired.query(arguments)
    nulls = _metadata_examples(payload, arguments, source_reference)
    runtime.require(bool(nulls), "repair.actual_explicit_null_public_metadata")
    runtime_raw_after = (root / RUNTIME).read_bytes()
    runtime.require(runtime_raw_before == runtime_raw_after, "repair.old_runtime_not_modified")
    body = {
        "schema_version": "delivery_diagnostic.v1.public_query_repair_receipt",
        "repair_version": REPAIR_VERSION,
        "status": "EXACT_PUBLIC_TOOL_DEFECT_REPRODUCED_AND_REPAIRED",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "repair_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "original_runtime_source": {
            "path": str(RUNTIME),
            "sha256_before": hashlib.sha256(runtime_raw_before).hexdigest(),
            "sha256_after": hashlib.sha256(runtime_raw_after).hexdigest(),
            "tracked_git_blob": tracked_blob,
            "unchanged_and_matches_HEAD": True,
        },
        "existing_ledger": ledger_reference,
        "existing_stage_A_report": report_reference,
        "recorded_model": ledger["model"],
        "recorded_task_id": ledger["task_id"],
        "recorded_step_one_based": example["step"],
        "query_arguments_unchanged": arguments,
        "public_source": source_reference,
        "public_source_root": str(source_root),
        "explicit_null_metadata_examples": nulls,
        "old_tool": {"status": "error", "type": "TypeError", "error": old_error},
        "new_tool": {
            "status": "ok",
            "total": actual["total"],
            "returned_records": len(actual["records"]),
            "offset": actual["offset"],
            "next_offset": actual["next_offset"],
            "result_sha256": hashlib.sha256(_encoded(actual)).hexdigest(),
        },
        "intervention": (
            "only explicit None label/description in query search text becomes empty string; "
            "raw source and returned metadata unchanged"
        ),
        "query_matches_correct_financial_answer": "NOT_ASSESSED",
        "source_snapshot_files_read": 1,
        "runtime_sessions_reread": 0,
        "callback_files_read": 0,
        "model_generation_calls": 0,
        "model_reevaluation_performed": False,
        "old_runtime_globally_patched": False,
        "old_results_modified": False,
        "sufficient_to_explain_all_no_Final": False,
        "causal_limit": (
            "A tool-only counterexample proves this request's exception was caused by nullable "
            "public metadata. It neither establishes model recovery nor explains all no-Final "
            "sessions. Legitimate empty results remain possible."
        ),
    }
    receipt = {
        **body,
        "id": "public_query_repair_receipt:" + hashlib.sha256(_encoded(body)).hexdigest(),
    }
    output.mkdir(parents=True)
    with (output / "receipt.json").open("xb") as handle:
        handle.write(_encoded(receipt) + b"\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    receipt = reproduce(root, output, args.source_root)
    print(json.dumps({"id": receipt["id"], "new_tool": receipt["new_tool"]}, sort_keys=True))


if __name__ == "__main__":
    main()
