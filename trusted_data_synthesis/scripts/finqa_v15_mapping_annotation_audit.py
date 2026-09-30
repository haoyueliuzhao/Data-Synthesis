#!/usr/bin/env python3
"""Read only the sealed V15 mapping matrix; never read Student outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import finqa_v14_annotation_audit as reader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Original V15 experiment root")
    args = parser.parse_args()
    root = args.output.resolve(strict=True)
    destination = root / "report_run_01/mapping_annotations"
    if destination.exists():
        raise ValueError("new report only; never overwrite an existing audit")
    seal_path = root / "completion_seal/record.json"
    seal, seal_ref = reader.read(seal_path)
    assert seal["schema"] == "v15_material_completion_seal.v1"
    assert len(seal["terminals"]) == seal["expected_calls"] == 36
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(reader.inspect, seal["terminals"]))
    assert all(r["purpose"] == "mapping" for r in rows)
    returned = [r for r in rows if r["returned"]]
    failed = [r for r in returned if not r["usable"]]
    unknown = [r for r in rows if not r["returned"]]
    assert len(returned) == seal["actual_returns"]
    assert len(unknown) == seal["network_unknowns"]
    assert len(failed) == seal["failures"]["mapping"].get("annotation_unusable", 0)
    assert len(returned) - len(failed) == seal["mapping_complete_calls"]
    examples = {}
    for row in failed:
        examples.setdefault(row["first_error"], row)
    summary = reader.bound(
        dict(
            schema="v15_sealed_mapping_annotation_audit.v1",
            completion_seal=seal_ref,
            audit_code=[
                dict(path=str(p.resolve()), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                for p in (Path(__file__), Path(reader.__file__))
            ],
            registered_denominator=len(rows),
            actual_return_denominator=len(returned),
            usable=len(returned) - len(failed),
            unusable=len(failed),
            network_unknowns=len(unknown),
            mutually_exclusive_first_diagnostic=reader.counts(
                r["first_error"] or "model_declared_unknown_without_validation_error"
                for r in failed
            ),
            nonexclusive_error_labels=reader.counts(e for r in failed for e in r["error_labels"]),
            saved_error_multiplicity=reader.counts(str(len(r["errors"])) for r in failed),
            finish_reason=reader.counts(r["finish_reason"] for r in returned),
            output_caps=reader.counts(str(r["max_output_tokens"]) for r in returned),
            completion_tokens=reader.distribution(r["completion_tokens"] for r in returned),
            unusable_completion_tokens=reader.distribution(r["completion_tokens"] for r in failed),
            length_count=sum(r["finish_reason"] == "length" for r in returned),
            completion_equal_cap=sum(
                r["completion_tokens"] == r["max_output_tokens"] for r in returned
            ),
            completion_above_cap=sum(
                r["completion_tokens"] > r["max_output_tokens"] for r in returned
            ),
            raw_mapping_status=reader.counts(str(r["raw_mapping_status"]) for r in returned),
            returned_with_nonempty_ambiguity_notes=sum(
                (r["raw_ambiguity_count"] or 0) > 0 for r in returned
            ),
            failed_annotation_records=[
                {k: v for k, v in r.items() if k != "raw_excerpt"} for r in failed
            ],
            examples=list(examples.values()),
            network_unknown_records=unknown,
            source_records_identity_sha256=hashlib.sha256(
                json.dumps(
                    [r["record"] for r in rows], sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
            seal_alignment_passed=True,
            no_rejudgment=True,
            no_JSON_repair=True,
            original_meaning_and_labels_preserved=True,
            no_Student_artifact_read=True,
            no_API_or_wallet_access=True,
            whole_training_material_admission_not_decided_here=True,
            methods=[
                "Read original terminal-bound record and saved inspection only; never run inspector again.",
                "First diagnostics partition unusable returns; multi-label counts can overlap.",
                "Raw complete/unknown is a model claim, not semantic truth or training admission.",
                "Network unknowns never count as returned format failures.",
                "Nearest-rank token quantiles; only this exact new 36-job matrix is the denominator.",
            ],
        )
    )
    assert reader.read(seal_path)[1] == seal_ref, "seal changed while reporting"
    reader.persist(destination, summary)
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "id",
                    "registered_denominator",
                    "actual_return_denominator",
                    "usable",
                    "unusable",
                    "network_unknowns",
                    "mutually_exclusive_first_diagnostic",
                    "finish_reason",
                    "output_caps",
                    "completion_tokens",
                    "length_count",
                    "completion_equal_cap",
                    "raw_mapping_status",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
