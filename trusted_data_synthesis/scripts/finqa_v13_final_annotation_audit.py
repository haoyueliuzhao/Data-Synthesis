#!/usr/bin/env python3
"""Aggregate sealed V13 diagnostics; never re-run a judge, repair, or call a model."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trusted_synthesis.finance_research.v6_collection import bound, persist  # noqa: E402


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def read(path, expected=None):
    path = Path(path)
    raw = path.read_bytes()
    value = json.loads(raw)
    ref = dict(path=str(path), id=value["id"], sha256=sha(raw))
    if expected is not None:
        assert ref == expected, "sealed reference identity/bytes changed"
    return value, ref


def label(error):
    """Reporting label only: preserve the actual saved error separately."""
    if error.startswith("JSONDecodeError:"):
        return error.split(": line ", 1)[0]
    return re.sub(r"\[\d+\]", "[]", error.split("\n", 1)[0])


def primary_group(artifact, errors):
    # Mutually exclusive first diagnostic grouping, not an inferred causal mechanism.
    if artifact["finish_reason"] == "length":
        return "output_length_terminal"
    if artifact["finish_reason"] != "tool_calls" or artifact.get("review_format_error"):
        return "annotation_envelope_failed"
    if not errors:
        return "model_declared_unknown_without_validation_error"
    first = errors[0]
    if first.startswith("JSONDecodeError:"):
        return "raw_JSON_parse_failed"
    if "outside typed enum" in first:
        return "typed_selection_outside_enum"
    if "missing/extra wire field" in first or "wrong wire type" in first:
        return "wire_object_or_type_failed"
    if any(t in first for t in ("partial_quote", "mapping/review locator", "reference_id")):
        return "original_evidence_locator_failed"
    if any(
        t in first
        for t in (
            "one original package",
            "state evidence",
            "state locator",
            "state member",
            "complete mapping must retain",
        )
    ):
        return "partition_membership_or_coverage_failed"
    if "chi " in first:
        return "consequential_chi_evidence_failed"
    return "other_saved_validation_failed"


def inspect_terminal(ref):
    terminal, _ = read(ref["path"], ref)
    saved, record_ref = read(terminal["record"]["path"], terminal["record"])
    role = saved["purpose"]
    base = dict(record=record_ref, terminal=ref, purpose=role, task_id=saved["task_id"])
    if terminal["terminal_kind"] != "paid_model_return":
        assert terminal["terminal_kind"] == "acknowledged_connection_unknown"
        assert saved["inspection"] is None and saved["actual_model_call_receipt_verified"] is False
        return dict(**base, actual_return=False)
    assert saved["actual_model_call_receipt_verified"] is True
    artifact, inspection, request = saved["artifact"], saved["inspection"], saved["request"]
    approved = (
        inspection.get("usable") is True
        if role == "projection"
        else (
            inspection.get("mapping_status") == "complete"
            and inspection.get("mapping_admitted") is True
        )
    )
    errors = inspection.get("errors", [])
    cap = request["max_output_tokens"]
    assert artifact["public_request"]["max_tokens"] == cap
    row = dict(
        **base,
        actual_return=True,
        usable=approved,
        finish_reason=artifact["finish_reason"],
        review_format_error=artifact["review_format_error"],
        max_output_tokens=cap,
        completion_tokens=artifact["usage"]["completion_tokens"],
        prompt_tokens=artifact["usage"]["prompt_tokens"],
        errors=errors,
        error_labels=sorted(set(label(e) for e in errors)),
        primary_group=None if approved else primary_group(artifact, errors),
        primary_error_label=None
        if approved
        else label(errors[0])
        if errors
        else "model_declared_unknown_without_validation_error",
    )
    parsed = inspection.get("raw_wire_annotation")
    if role == "mapping":
        row["raw_mapping_status"] = (
            parsed.get("mapping_status") if isinstance(parsed, dict) else None
        )
        ambiguities = parsed.get("ambiguities") if isinstance(parsed, dict) else None
        row["raw_ambiguity_count"] = len(ambiguities) if isinstance(ambiguities, list) else None
        row["raw_ambiguity_description_excerpts"] = (
            [str(a.get("description", ""))[:240] for a in ambiguities[:2] if isinstance(a, dict)]
            if isinstance(ambiguities, list)
            else []
        )
    if approved:
        return row
    raw = artifact["review_text"]
    row["raw_review_sha256"] = sha(raw.encode()) if isinstance(raw, str) else None
    if "ValueError: $: missing/extra wire field" in errors and isinstance(parsed, dict):
        expected = request["strict_tool"]["function"]["parameters"]["properties"]
        row["root_shape"] = dict(
            missing=sorted(set(expected) - set(parsed)), extra=sorted(set(parsed) - set(expected))
        )
    if isinstance(raw, str):
        match = re.search(r"\(char (\d+)\)", " ".join(errors))
        pos = int(match[1]) if match else max(0, len(raw) - 220)
        left = max(0, pos - 80)
        row["raw_excerpt"] = dict(
            start=left,
            end=min(left + 300, len(raw)),
            text=raw[left : left + 300],
            exact_unchanged_original=True,
        )
    return row


def quantiles(values):
    values = sorted(values)
    return dict(
        n=len(values),
        min=values[0],
        max=values[-1],
        total=sum(values),
        p50=values[math.ceil(len(values) * 0.5) - 1],
        p95=values[math.ceil(len(values) * 0.95) - 1],
        p99=values[math.ceil(len(values) * 0.99) - 1],
    )


def counts(values):
    return dict(sorted(Counter(values).items()))


def summarize(rows, seal, seal_ref):
    result, failures, examples = {}, [], {}
    for role in ("projection", "mapping"):
        attempted = [r for r in rows if r["purpose"] == role]
        returned = [r for r in attempted if r["actual_return"]]
        bad = [r for r in returned if not r["usable"]]
        shapes = Counter(
            (tuple(r["root_shape"]["missing"]), tuple(r["root_shape"]["extra"]))
            for r in bad
            if "root_shape" in r
        )
        result[role] = dict(
            registered_denominator=seal["purpose_expected"][role],
            terminal_count=len(attempted),
            returned_denominator=len(returned),
            network_unknown_count=len(attempted) - len(returned),
            usable_count=len(returned) - len(bad),
            unusable_count=len(bad),
            mutually_exclusive_primary_groups=counts(r["primary_group"] for r in bad),
            mutually_exclusive_first_error_labels=counts(r["primary_error_label"] for r in bad),
            nonexclusive_saved_error_labels=counts(e for r in bad for e in r["error_labels"]),
            saved_error_multiplicity=counts(str(len(r["errors"])) for r in bad),
            raw_top_level_shape_failures=[
                dict(missing=list(k[0]), extra=list(k[1]), count=n)
                for k, n in sorted(shapes.items())
            ],
            finish_reason_counts=counts(r["finish_reason"] for r in returned),
            unusable_finish_reason_counts=counts(r["finish_reason"] for r in bad),
            returned_cap_counts=counts(str(r["max_output_tokens"]) for r in returned),
            unusable_cap_counts=counts(str(r["max_output_tokens"]) for r in bad),
            completion_tokens=quantiles(r["completion_tokens"] for r in returned),
            unusable_completion_tokens=quantiles(r["completion_tokens"] for r in bad),
            prompt_tokens=quantiles(r["prompt_tokens"] for r in returned),
            length_terminal_count=sum(r["finish_reason"] == "length" for r in returned),
            completion_equal_cap=sum(
                r["completion_tokens"] == r["max_output_tokens"] for r in returned
            ),
            completion_exceeds_cap=sum(
                r["completion_tokens"] > r["max_output_tokens"] for r in returned
            ),
        )
        if role == "mapping":
            result[role]["raw_declared_mapping_status"] = counts(
                str(r["raw_mapping_status"]) for r in returned
            )
            result[role]["unusable_raw_declared_mapping_status"] = counts(
                str(r["raw_mapping_status"]) for r in bad
            )
            result[role]["returned_with_nonempty_raw_ambiguities"] = sum(
                (r["raw_ambiguity_count"] or 0) > 0 for r in returned
            )
            result[role]["unusable_with_nonempty_raw_ambiguities"] = sum(
                (r["raw_ambiguity_count"] or 0) > 0 for r in bad
            )
        assert len(attempted) == seal["purpose_expected"][role]
        assert len(returned) == seal["actual_returns_by_purpose"][role]
        assert len(bad) == seal["failures"][role]["annotation_unusable"]
        for row in bad:
            failures.append(
                {
                    k: v
                    for k, v in row.items()
                    if k not in {"raw_excerpt", "terminal", "prompt_tokens"}
                }
            )
            examples.setdefault((role, row["primary_error_label"]), row)
    assert sum(r["actual_return"] for r in rows) == seal["actual_returns"] == 1304
    assert len(rows) == seal["expected_calls"] == 1316
    assert sum(not r["actual_return"] for r in rows) == seal["network_unknowns"] == 12
    assert result["projection"]["usable_count"] == seal["projection_usable_calls"] == 668
    assert result["mapping"]["usable_count"] == seal["mapping_complete_calls"] == 325
    return dict(
        schema="v13_final_annotation_diagnostic_audit.v1",
        completion_seal=seal_ref,
        source_review_seal_id=seal["source_review_seal_id"],
        registered_denominator=1316,
        actual_return_denominator=1304,
        network_unknown_count=12,
        full_registered_matrix_has_terminals=True,
        all_model_responses_returned=False,
        seal_alignment_passed=True,
        by_purpose=result,
        methods=dict(
            source="saved original inspection.errors/status and artifact.finish_reason/usage only",
            primary=(
                "one first saved diagnostic per unusable return; envelope/length take precedence"
            ),
            labels="saved error labels may overlap; array indices normalized only in report labels",
            quantiles="nearest rank ceil(p*n)",
            no_judge_or_projection_reexecution=True,
            no_JSON_repair_or_relabeling=True,
            no_wallet_or_network_access=True,
            no_new_model_calls=True,
            unknowns_excluded_from_annotation_failure_counts=True,
            raw_mapping_status_is_model_claim_not_host_validated_partition=True,
            limitation=(
                "First failure is not an exhaustive diagnosis or a financial-truth judgment; "
                "tool_calls does not prove valid JSON or semantic completeness."
            ),
        ),
        failed_annotation_records=failures,
        examples=list(examples.values()),
        network_unknown_records=[r for r in rows if not r["actual_return"]],
        source_records_identity_sha256=sha(canonical([r["record"] for r in rows])),
        production_admitted=False,
        training_started=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    root = args.experiment.resolve(strict=True)
    output = root / "report_final_01" / "annotation_analysis"
    if output.exists():
        raise ValueError("new audit output only; never overwrite a prior report")
    assert 1 <= args.workers <= 16
    seal_path = root / "completion_seal" / "record.json"
    seal, seal_ref = read(seal_path)
    assert len(seal["terminals"]) == 1316
    expected_records = {
        str(Path(t["path"]).parent.parent / "record/record.json") for t in seal["terminals"]
    }
    assert expected_records == {str(p) for p in (root / "annotations").glob("*/record/record.json")}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(inspect_terminal, seal["terminals"]))
    record = summarize(rows, seal, seal_ref)
    record["audit_script"] = dict(
        path=str(Path(__file__).resolve()), sha256=sha(Path(__file__).read_bytes())
    )
    assert read(seal_path)[1] == seal_ref, "seal changed during report"
    record = bound(record)
    persist(output, record)
    print(
        json.dumps(
            dict(
                output=str(output / "record.json"), id=record["id"], by_purpose=record["by_purpose"]
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
