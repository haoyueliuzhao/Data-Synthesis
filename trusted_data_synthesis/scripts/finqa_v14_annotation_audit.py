#!/usr/bin/env python3
"""Report sealed V14 saved diagnostics only: no judgment replay, repair or API."""

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


def read(path, expected=None):
    path = Path(path)
    raw = path.read_bytes()
    value = json.loads(raw)
    ref = dict(path=str(path.resolve()), id=value["id"], sha256=hashlib.sha256(raw).hexdigest())
    assert expected is None or ref == expected, "sealed record reference changed"
    return value, ref


def label(error):
    if error.startswith("JSONDecodeError:"):
        return error.split(": line ", 1)[0]
    return re.sub(r"\[\d+\]", "[]", error.split("\n", 1)[0])


def inspect(ref):
    terminal, _ = read(ref["path"], ref)
    saved, original = read(terminal["record"]["path"], terminal["record"])
    row = dict(
        record=original,
        purpose=saved["purpose"],
        task_id=saved["task_id"],
        returned=terminal["terminal_kind"] == "paid_model_return",
    )
    if not row["returned"]:
        assert saved["inspection"] is None and not saved["actual_model_call_receipt_verified"]
        return row
    assert saved["actual_model_call_receipt_verified"] is True
    a, i, req = saved["artifact"], saved["inspection"], saved["request"]
    usable = (
        i["usable"]
        if row["purpose"] == "projection"
        else (i["mapping_status"] == "complete" and i["mapping_admitted"] is True)
    )
    errors = i["errors"]
    row.update(
        usable=usable,
        errors=errors,
        first_error=label(errors[0]) if errors else None,
        error_labels=sorted(set(map(label, errors))),
        finish_reason=a["finish_reason"],
        completion_tokens=a["usage"]["completion_tokens"],
        max_output_tokens=req["max_output_tokens"],
        review_format_error=a["review_format_error"],
    )
    assert a["public_request"]["max_tokens"] == row["max_output_tokens"]
    raw = i["raw_wire_annotation"]
    if row["purpose"] == "mapping":
        notes = raw.get("ambiguity_notes") if isinstance(raw, dict) else None
        row["raw_mapping_status"] = raw.get("mapping_status") if isinstance(raw, dict) else None
        row["raw_ambiguity_count"] = len(notes) if isinstance(notes, list) else None
    if not usable:
        text = a["review_text"]
        row["raw_review_sha256"] = (
            hashlib.sha256(text.encode()).hexdigest() if isinstance(text, str) else None
        )
        if isinstance(text, str):
            match = re.search(r"\(char (\d+)\)", " ".join(errors))
            start = max(0, (int(match[1]) - 80) if match else len(text) - 240)
            row["raw_excerpt"] = dict(
                start=start,
                end=min(start + 300, len(text)),
                text=text[start : start + 300],
                unchanged=True,
            )
    return row


def counts(values):
    return dict(sorted(Counter(values).items()))


def distribution(values):
    values = sorted(values)
    if not values:
        return dict(n=0)
    return dict(
        n=len(values),
        min=values[0],
        max=values[-1],
        total=sum(values),
        p50=values[math.ceil(0.5 * len(values)) - 1],
        p95=values[math.ceil(0.95 * len(values)) - 1],
        p99=values[math.ceil(0.99 * len(values)) - 1],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Original V14 experiment root")
    args = parser.parse_args()
    root = args.output.resolve(strict=True)
    destination = root / "report_run_01/annotations"
    if destination.exists():
        raise ValueError("new report directory only; never overwrite existing audit")
    seal, seal_ref = read(root / "completion_seal/record.json")
    assert seal["schema"] == "v14_material_completion_seal.v1"
    assert len(seal["terminals"]) == seal["expected_calls"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(inspect, seal["terminals"]))
    roles, failures, examples = {}, [], {}
    for role, denominator in seal["purpose_expected"].items():
        whole = [r for r in rows if r["purpose"] == role]
        returned = [r for r in whole if r["returned"]]
        bad = [r for r in returned if not r["usable"]]
        assert len(whole) == denominator
        assert len(returned) == seal["actual_returns_by_purpose"].get(role, 0)
        assert len(bad) == seal["failures"][role].get("annotation_unusable", 0)
        roles[role] = dict(
            registered=denominator,
            returned=len(returned),
            network_unknown=len(whole) - len(returned),
            usable=len(returned) - len(bad),
            unusable=len(bad),
            mutually_exclusive_first_diagnostic=counts(
                r["first_error"] or "model_declared_unknown_without_validation_error" for r in bad
            ),
            nonexclusive_error_labels=counts(e for r in bad for e in r["error_labels"]),
            saved_error_multiplicity=counts(str(len(r["errors"])) for r in bad),
            finish_reason=counts(r["finish_reason"] for r in returned),
            caps=counts(str(r["max_output_tokens"]) for r in returned),
            completion_tokens=distribution(r["completion_tokens"] for r in returned),
            unusable_completion_tokens=distribution(r["completion_tokens"] for r in bad),
            length_count=sum(r["finish_reason"] == "length" for r in returned),
            completion_equal_cap=sum(
                r["completion_tokens"] == r["max_output_tokens"] for r in returned
            ),
            completion_above_cap=sum(
                r["completion_tokens"] > r["max_output_tokens"] for r in returned
            ),
        )
        if role == "mapping":
            roles[role]["raw_mapping_status"] = counts(
                str(r["raw_mapping_status"]) for r in returned
            )
            roles[role]["returned_with_nonempty_ambiguity_notes"] = sum(
                (r["raw_ambiguity_count"] or 0) > 0 for r in returned
            )
        for row in bad:
            failures.append({k: v for k, v in row.items() if k != "raw_excerpt"})
            examples.setdefault((role, row["first_error"]), row)
    assert sum(r["returned"] for r in rows) == seal["actual_returns"]
    assert sum(not r["returned"] for r in rows) == seal["network_unknowns"]
    assert roles["projection"]["usable"] == seal["projection_usable_calls"]
    assert roles["mapping"]["usable"] == seal["mapping_complete_calls"]
    result = bound(
        dict(
            schema="v14_sealed_annotation_report.v1",
            completion_seal=seal_ref,
            script=dict(
                path=str(Path(__file__).resolve()),
                sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            ),
            registered=seal["expected_calls"],
            actual_returns=seal["actual_returns"],
            network_unknowns=seal["network_unknowns"],
            by_purpose=roles,
            failed_annotation_records=failures,
            examples=list(examples.values()),
            source_records_identity_sha256=hashlib.sha256(
                json.dumps(
                    [r["record"] for r in rows], sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
            seal_alignment_passed=True,
            no_rejudgment=True,
            no_JSON_repair=True,
            original_meaning_and_labels_preserved=True,
            no_API_or_wallet_access=True,
            notes=[
                (
                    "Whole newly registered matrix, not all historical mappings "
                    "or a causal before/after comparison."
                ),
                "First diagnostics are mutually exclusive; all-error labels may overlap.",
                (
                    "Raw complete/unknown is the saved model claim, "
                    "not a host semantic truth certificate."
                ),
                "Missing model responses are excluded from format/annotation failures.",
                (
                    "Quantiles use nearest rank ceil(p*n); "
                    "no output-limit inference from response content."
                ),
            ],
        )
    )
    assert read(root / "completion_seal/record.json")[1] == seal_ref
    persist(destination, result)
    print(
        json.dumps(
            dict(id=result["id"], path=str(destination / "record.json"), by_purpose=roles),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
