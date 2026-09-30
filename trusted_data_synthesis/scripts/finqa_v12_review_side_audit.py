#!/usr/bin/env python3
"""Read saved V12 reviews once; report, never judge, repair, or contact a service."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def categories(error):
    """Keep invariant messages; group Pydantic failures by saved type, not guesses."""
    if not error:
        return []
    types = re.findall(r"\[type=([^,\]]+)", error)
    return sorted(set("pydantic:" + t for t in types)) if types else [error.split("\n", 1)[0]]


def snippet(text, position=0, width=320):
    left = max(0, position - 100)
    right = min(len(text), left + width)
    return dict(
        start_character=left,
        end_character=right,
        text=text[left:right],
        full_text_characters=len(text),
        excerpt_is_exact=True,
        repaired=False,
    )


def inspect(path_string):
    path = Path(path_string)
    raw = path.read_bytes()
    saved = json.loads(raw)
    artifact, inner, outer = saved["artifact"], saved["inspection"], saved["new_pipeline_outcomes"]
    role = saved["role"]
    assert role in {"A", "B"} and saved["actual_model_call_receipt_verified"] is True
    assert artifact["role"] == role and artifact["public_request"]["model"] == "deepseek-flash"
    assert artifact["finish_reason"] == outer["finish_reason"]
    request = saved["request"]
    assert (
        artifact["public_request"]["max_tokens"]
        == outer["max_output_tokens"]
        == request["max_output_tokens"]
    )
    usage = artifact["usage"]
    assert usage["completion_tokens"] == outer["completion_tokens"]
    process = inner["process_evidence_binding"]
    projection = inner["auxiliary"]["supervision"]
    wire = outer["wire_schema_failures"]
    raw_wire = outer.get("raw_wire_annotation")
    raw_checks = raw_wire.get("process", {}) if isinstance(raw_wire, dict) else {}
    raw_statuses = (
        {k: v.get("status") if isinstance(v, dict) else None for k, v in raw_checks.items()}
        if isinstance(raw_checks, dict)
        else {}
    )
    parse_error = outer["raw_JSON_error"]
    parse_category = parse_error.split(": line ", 1)[0] if parse_error else None
    dimension_errors = {
        k: categories(v.get("error")) for k, v in process["dimensions"].items() if v.get("error")
    }
    projection_labels = []
    if role == "A" and outer["projection_usable"] is not True:
        if not outer["envelope_complete"]:
            projection_labels.append("annotation_envelope_incomplete")
        if parse_error:
            projection_labels.append("raw_JSON_parse_failed")
        projection_labels.extend(
            "wire:" + e["reason"] for e in wire if e["scope"] in {"projection", "envelope"}
        )
        projection_labels.extend("inner:" + e for e in categories(projection.get("error")))
        if projection.get("status") != "complete":
            projection_labels.append("inner_status:" + str(projection.get("status")))
    row = dict(
        record_path=str(path),
        record_sha256=sha(raw),
        record_id=saved["id"],
        slot_id=saved["slot_id"],
        task_id=saved["task_id"],
        role=role,
        protocol_id=saved["protocol_id"],
        raw_review_sha256=sha(artifact["review_text"].encode()),
        raw_wire_statuses=raw_statuses,
        stored_materialized_declared_outcome=inner["raw_process_claims"]["declared_outcome"],
        evidence_bound_process_outcome=process["validated_process_outcome"],
        all_critical_evidence_bound=process["all_critical_evidence_bound"],
        process_validity=outer["process_validity"],
        process_candidate_usable=outer["process_candidate_usable"],
        projection_usable=outer["projection_usable"],
        projection_status=projection.get("status"),
        projection_error_categories=categories(projection.get("error")) if role == "A" else [],
        projection_failure_labels=sorted(set(projection_labels)),
        offline_reason_projection=inner["reason_projection"],
        finish_reason=outer["finish_reason"],
        max_output_tokens=outer["max_output_tokens"],
        usage={
            k: usage.get(k)
            for k in (
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "prompt_cache_hit_tokens",
                "prompt_cache_miss_tokens",
            )
        },
        http_status=artifact["http_status"],
        response_model=artifact["api_response"]["model"],
        JSON_parse_error_category=parse_category,
        failure_codes=outer["failure_codes"],
        wire_failures=wire,
        dimension_error_categories=dimension_errors,
        q_native_registered=request["candidate_request"]["native_result"]["native"][
            "execution_accuracy"
        ],
    )
    examples = []
    text = artifact["review_text"]
    common = dict(
        record_path=str(path),
        record_id=saved["id"],
        record_sha256=row["record_sha256"],
        role=role,
        slot_id=row["slot_id"],
        raw_review_sha256=row["raw_review_sha256"],
    )
    if parse_error:
        match = re.search(r"\(char (\d+)\)", parse_error)
        examples.append(
            {
                **common,
                "category": "parse:" + parse_category,
                "saved_error": parse_error,
                "raw_excerpt": snippet(text, int(match[1]) if match else 0),
            }
        )
    if wire:
        examples.append(
            {
                **common,
                "category": "wire:" + wire[0]["scope"] + ":" + wire[0]["reason"],
                "saved_error": wire[0],
                "raw_excerpt": snippet(text, max(0, text.find('"supervision"'))),
            }
        )
    if role == "A" and projection.get("error"):
        examples.append(
            {
                **common,
                "category": "projection:" + categories(projection["error"])[0],
                "saved_error": projection["error"][:700],
                "raw_excerpt": snippet(text, max(0, text.find('"supervision"'))),
            }
        )
    if dimension_errors:
        key = sorted(dimension_errors)[0]
        examples.append(
            {
                **common,
                "category": "process:" + dimension_errors[key][0],
                "saved_error": process["dimensions"][key]["error"][:700],
                "raw_excerpt": snippet(text, max(0, text.find('"' + key + '"'))),
            }
        )
    return row, examples


def histogram(values):
    return dict(sorted(Counter(str(v) for v in values).items()))


def quantiles(values):
    values = sorted(x for x in values if x is not None)
    if not values:
        return dict(n=0)
    return dict(
        n=len(values),
        total=sum(values),
        min=values[0],
        max=values[-1],
        p50=values[math.ceil(0.50 * len(values)) - 1],
        p95=values[math.ceil(0.95 * len(values)) - 1],
        p99=values[math.ceil(0.99 * len(values)) - 1],
    )


def labelled(rows, field):
    return dict(sorted(Counter(label for r in rows for label in set(r[field])).items()))


def summarize(rows, seal, source_bindings, examples):
    by_role = {role: [r for r in rows if r["role"] == role] for role in ("A", "B")}
    sides = {}
    for role, rr in by_role.items():

        def wire_labels(r):
            return {e["scope"] + ":" + e["reason"] for e in r["wire_failures"]}

        sides[role] = dict(
            denominator=len(rr),
            process_validity=histogram(r["process_validity"] for r in rr),
            materialized_declared_outcome=histogram(
                r["stored_materialized_declared_outcome"] for r in rr
            ),
            evidence_bound_process_outcome=histogram(
                r["evidence_bound_process_outcome"] for r in rr
            ),
            declaration_to_effective_process=histogram(
                str(r["stored_materialized_declared_outcome"]) + " -> " + r["process_validity"]
                for r in rr
            ),
            raw_wire_statuses={
                dim: histogram(r["raw_wire_statuses"].get(dim) for r in rr)
                for dim in (
                    "evidence_and_operations",
                    "observation_interpretation",
                    "actual_revisions",
                    "unwithdrawn_critical_contradictions",
                )
            },
            finish_reasons=histogram(r["finish_reason"] for r in rr),
            max_output_token_caps=histogram(r["max_output_tokens"] for r in rr),
            token_statistics={k: quantiles(r["usage"][k] for r in rr) for k in rr[0]["usage"]},
            cap_statistics=quantiles(r["max_output_tokens"] for r in rr),
            completion_equal_cap=sum(
                r["usage"]["completion_tokens"] == r["max_output_tokens"] for r in rr
            ),
            completion_exceeds_cap=sum(
                r["usage"]["completion_tokens"] > r["max_output_tokens"] for r in rr
            ),
            JSON_parse_failures=sum(r["JSON_parse_error_category"] is not None for r in rr),
            JSON_parse_error_categories=histogram(
                r["JSON_parse_error_category"] for r in rr if r["JSON_parse_error_category"]
            ),
            layered_failure_counts=labelled(rr, "failure_codes"),
            wire_failed_records=sum(bool(r["wire_failures"]) for r in rr),
            wire_failure_record_labels=dict(
                sorted(Counter(k for r in rr for k in wire_labels(r)).items())
            ),
            wire_failure_event_labels=dict(
                sorted(
                    Counter(
                        e["scope"] + ":" + e["reason"] for r in rr for e in r["wire_failures"]
                    ).items()
                )
            ),
            process_binding_failure_record_labels=dict(
                sorted(
                    Counter(
                        k
                        for r in rr
                        for k in {x for v in r["dimension_error_categories"].values() for x in v}
                    ).items()
                )
            ),
            projection_usable=histogram(r["projection_usable"] for r in rr),
            projection_failure_labels=labelled(rr, "projection_failure_labels"),
            projection_failed_but_process_valid=sum(
                r["projection_usable"] is False and r["process_validity"] == "valid" for r in rr
            ),
            http_status=histogram(r["http_status"] for r in rr),
            response_models=histogram(r["response_model"] for r in rr),
        )
    pairs = defaultdict(dict)
    for row in rows:
        assert row["role"] not in pairs[row["slot_id"]], "duplicate side"
        pairs[row["slot_id"]][row["role"]] = row
    assert all(set(p) == {"A", "B"} for p in pairs.values())
    assert all(r["q_native_registered"] == 1 for r in rows), "native registered pool changed"
    joint = {
        slot
        for slot, p in pairs.items()
        if all(p[k]["process_candidate_usable"] is True for k in ("A", "B"))
    }
    blocked = {slot for slot in joint if pairs[slot]["A"]["projection_usable"] is not True}
    cross = Counter(
        (p["A"]["process_validity"], p["B"]["process_validity"]) for p in pairs.values()
    )
    assert len(rows) == seal["expected_reviews"] == seal["actual_returns"] == 11438
    assert len(pairs) == seal["expected_pairs"] == len(seal["paired_cores"]) == 5719
    assert {
        str(Path(t["path"]).parent.parent / "record" / "record.json") for t in seal["terminals"]
    } == {r["record_path"] for r in rows}
    assert joint == set(seal["joint_process_candidate_slot_ids"])
    assert blocked == set(seal["projection_blocked_candidate_slot_ids"])
    for role in ("A", "B"):
        assert len(by_role[role]) == 5719
        assert sides[role]["process_validity"] == seal["process_outcome_counts"][role]
        assert sides[role]["layered_failure_counts"] == seal["layered_failure_counts"][role]
    raw_chars = sum(
        pairs[s]["A"]["offline_reason_projection"]["raw_public_characters"] for s in joint
    )
    assert raw_chars == seal["candidate_raw_public_characters"]
    selected_examples = {}
    for example in examples:
        selected_examples.setdefault(example["category"], example)
    return dict(
        schema="finqa_v12_review_side_report_audit.v1",
        source_bindings=source_bindings,
        scope="saved-record aggregation only; no judge rerun, no JSON repair, no API/wallet access",
        definitions={
            "quantiles": "nearest rank ceil(p*n), across all returned reviews on that side",
            "failure_counts": (
                "record labels are non-mutually-exclusive; "
                "event labels count repeated failure events separately"
            ),
            "process": (
                "original stored effective process outcome, "
                "not a new financial or semantic truth judgment"
            ),
            "raw": (
                "raw_wire_statuses from original parsed wire; "
                "materialized_declared_outcome from saved deterministic V11 inspection, "
                "not repaired model JSON"
            ),
            "parse": "saved raw_JSON_error; no partial JSON recovery or relabeling",
            "projection": (
                "A only; B None is not a failure; parse/envelope and auxiliary failures may overlap"
            ),
            "inner_errors": (
                "first saved failure for a layer may hide additional failures; "
                "frequency is not causal attribution"
            ),
            "examples": (
                "first lexicographic record per error category, "
                "exact bounded raw excerpt; not prevalence-weighted"
            ),
            "binding": (
                "original record SHA and seal counter/set reconciliation; "
                "not a repeat of original full receipt/source audit"
            ),
        },
        sides=sides,
        AB_process_cross_table=[
            dict(A=a, B=b, count=cross.get((a, b), 0))
            for a in ("valid", "invalid", "unknown")
            for b in ("valid", "invalid", "unknown")
        ],
        pair_denominator=len(pairs),
        joint_process_candidates=len(joint),
        joint_projection_usable=len(joint - blocked),
        joint_projection_blocked=len(blocked),
        joint_candidate_raw_public_characters=raw_chars,
        seal_alignment_passed=True,
        production_admitted=False,
        training_started=False,
        examples=list(selected_examples.values()),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    experiment = args.experiment.resolve(strict=True)
    expected = experiment / "report_audit_01" / "side_analysis"
    if args.output.resolve() != expected or args.output.exists():
        raise ValueError("new report_audit_01/side_analysis only; never overwrite outputs")
    seal_path = experiment / "review_seal" / "record.json"
    seal_bytes = seal_path.read_bytes()
    seal = json.loads(seal_bytes)
    paths = sorted((experiment / "reviews").glob("*/record/record.json"))
    assert len(paths) == 11438, "complete fixed 11438 records required"
    rows, examples = [], []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for row, sampled in executor.map(inspect, map(str, paths), chunksize=16):
            rows.append(row)
            examples.extend(sampled)
    bindings = dict(
        experiment=str(experiment),
        seal_path=str(seal_path),
        seal_id=seal["id"],
        seal_sha256=sha(seal_bytes),
        audit_script_path=str(Path(__file__).resolve()),
        audit_script_sha256=sha(Path(__file__).read_bytes()),
        records_count=len(rows),
        records_identity_sha256=sha(
            encode(
                [
                    dict(path=r["record_path"], sha256=r["record_sha256"], id=r["record_id"])
                    for r in rows
                ]
            )
        ),
    )
    assert {r["protocol_id"] for r in rows} == {seal["protocol_id"]}
    summary = summarize(rows, seal, bindings, examples)
    assert seal_path.read_bytes() == seal_bytes, "seal changed during audit"
    payload = b"".join(encode(row) + b"\n" for row in rows)
    summary["sides_jsonl_sha256"] = sha(payload)
    summary["id"] = sha(encode(summary))
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "sides.jsonl").open("xb") as stream:
        stream.write(payload)
    with (args.output / "summary.json").open("xb") as stream:
        stream.write(
            json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
        )
    print(
        json.dumps(
            dict(
                id=summary["id"],
                output=str(args.output),
                records=len(rows),
                seal_alignment_passed=True,
                sides={k: v["process_validity"] for k, v in summary["sides"].items()},
                AB_process_cross_table=summary["AB_process_cross_table"],
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
