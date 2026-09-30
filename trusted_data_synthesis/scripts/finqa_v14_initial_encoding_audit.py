"""Read saved initial V14 encodings once; no tokenizer, model or source mutation."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from trusted_synthesis.finance_research.contracts import digest

DEFAULT_ROOT = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01/v14_representation_01"
)


def read_ref(ref):
    raw = Path(ref["path"]).read_bytes()
    value = json.loads(raw)
    if (
        hashlib.sha256(raw).hexdigest() != ref["sha256"]
        or value.get("id", value.get("encoding_id")) != ref["id"]
    ):
        raise ValueError("referenced saved bytes/identity changed: " + ref["path"])
    return value


def entry(path):
    raw = Path(path).read_bytes()
    value = json.loads(raw)
    return dict(
        path=str(Path(path).resolve()),
        sha256=hashlib.sha256(raw).hexdigest(),
        id=value.get("id", value.get("encoding_id")),
    )


def summarize(root=DEFAULT_ROOT):
    root = Path(root).resolve()
    marker_ref = entry(root / "workflow/initial_encoding/record.json")
    marker = read_ref(marker_ref)
    registration_ref = entry(root / "encoding_cache/registration/record.json")
    registration = read_ref(registration_ref)
    run_ref = marker["cache_run"]
    run = read_ref(run_ref)
    revision = read_ref(run["authority_revision"])
    if (
        marker["schema"] != "v14_initial_encoding_job.v1"
        or run["schema"] != "v14_encoding_cache_run.v1"
        or revision["index"] != 0
        or run["registration_id"] != registration["id"]
        or revision["registration_id"] != registration["id"]
        or marker["known_authority_count"] != run["known_authority_count"]
        or len(run["encoding_refs"]) != 2465
        or registration["fixed_packages"] != 2468
        or marker["pending_authority_slot_ids"] != revision["pending_slot_ids"]
    ):
        raise ValueError("not the complete frozen initial 2465-of-2468 cache run")
    admitted = started = sequence_total = supervised_total = rows_total = 0
    schemas, layers, failure_packages, failure_events = Counter(), Counter(), Counter(), Counter()
    failures, longest, unknown_length, reason_zero, overflow, truncated = [], [], [], [], [], []
    sources = {a["slot_id"]: a for a in revision["added_authorities"]}
    if set(sources) != set(run["encoding_refs"]):
        raise ValueError("encoding outcomes must cover every registered initial authority")
    for sid in registration["candidate_slot_ids"]:
        if sid not in run["encoding_refs"]:
            continue
        ref = run["encoding_refs"][sid]
        value = read_ref(ref)
        schemas[value["schema"]] += 1
        started += int(value.get("encoding_started") is True)
        admitted += int(value.get("encoding_admitted") is True)
        reasons = [f["reason"] for f in value.get("failures", [])]
        if value.get("encoding_admitted") is not True:
            failure_packages.update(set(reasons))
            failure_events.update(reasons)
            failures.append(
                dict(
                    slot_id=sid,
                    task_id=sources[sid]["task_id"],
                    encoding=ref,
                    schema=value["schema"],
                    encoding_started=value.get("encoding_started"),
                    failures=value.get("failures", []),
                )
            )
        if value.get("schema") == "v14_student_encoding.v1":
            if (
                value["slot_id"] != sid
                or value["task_id"] != sources[sid]["task_id"]
                or value["L_P"] != value["total_supervised_tokens"]
                or value["L_P"] != sum(value["layer_target_counts"].values())
                or value["context_limit"] != 24576
                or value.get("state_or_chi_used") is not False
            ):
                raise ValueError("saved encoding counters/source boundary differ: " + sid)
            layers.update(value["layer_target_counts"])
            supervised_total += value["total_supervised_tokens"]
            sequence_total += value["total_sequence_tokens"]
            rows_total += len(value["rows"])
            longest.append(
                dict(
                    slot_id=sid,
                    task_id=value["task_id"],
                    max_sequence_tokens=value["max_sequence_tokens"],
                    encoding=ref,
                )
            )
            if value["public_content_without_positive_reason_targets"]:
                reason_zero.append(sid)
            if value["context_truncated"]:
                truncated.append(sid)
        else:
            unknown_length.append(sid)
        if "untruncated_context_overflow" in reasons:
            overflow.append(sid)
    longest.sort(key=lambda row: (-row["max_sequence_tokens"], row["slot_id"]))
    body = dict(
        schema="v14_initial_encoding_audit.v1",
        source_run=run_ref,
        source_workflow_marker=marker_ref,
        source_registration=registration_ref,
        source_authority_revision=run["authority_revision"],
        fixed_population=dict(packages=2468, tasks=744),
        initial_encoding_denominator=2465,
        source_complete_scope=(
            "All 2465 outcomes in initial authority revision 0000, not a success-only subset."
        ),
        source_schema_counts=dict(schemas),
        encoding_started_packages=started,
        encoding_admitted_packages=admitted,
        encoding_failed_packages=len(failures),
        encoding_not_started_within_initial_denominator=2465 - started,
        pending_authority_packages_outside_initial_denominator=len(revision["pending_slot_ids"]),
        pending_authority_slot_ids=revision["pending_slot_ids"],
        failure_package_counts_by_reason=dict(failure_packages),
        failure_event_counts_by_reason=dict(failure_events),
        failed_slots=failures,
        context_limit=24576,
        context_overflow_packages=len(overflow),
        context_overflow_slot_ids=overflow,
        context_truncated_packages=len(truncated),
        context_truncated_slot_ids=truncated,
        length_unavailable_packages=len(unknown_length),
        length_unavailable_slot_ids=unknown_length,
        observed_initial_max_sequence_tokens=longest[0]["max_sequence_tokens"] if longest else None,
        longest_initial_packages=longest[:5],
        observed_initial_response_rows=rows_total,
        observed_initial_total_sequence_tokens=sequence_total,
        sequence_total_includes_repeated_complete_history_prefixes=True,
        observed_initial_total_supervised_tokens=supervised_total,
        observed_initial_layer_target_counts=dict(layers),
        package_public_content_but_zero_positive_reason_tokens=len(reason_zero),
        public_content_zero_reason_slot_ids=reason_zero,
        full_2468_supervised_tokens=None,
        full_2468_layer_target_counts=None,
        unresolved_authority_is_not_an_encoding_failure=True,
        observed_encoding_failure_is_not_reported_as_not_started=True,
        state_mapping_was_not_required_for_this_encoding=True,
        counts_do_not_establish_semantic_quality_or_training_effect=True,
        training_authorized=False,
        API_calls=0,
        GPU_used=False,
        retokenization_calls=0,
        source_files_modified=False,
        audit_script=dict(
            repository_path="trusted_data_synthesis/scripts/finqa_v14_initial_encoding_audit.py",
            sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        ),
    )
    return body | dict(id=digest(body))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    print(json.dumps(summarize(args.root), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
