#!/usr/bin/env python3
"""Observed V12 sealed-pair statistics; never a new training population.

Reads only the 5719 thin pair cores and registration/seal metadata. It does not
open raw A/B reviews, a wallet, a model client or a GPU. Every common process
candidate remains in candidates.jsonl, including unavailable projections.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trusted_synthesis.core.immutable_artifacts import (  # noqa: E402
    write_immutable_artifact_directory,
)

DEFAULT_ROOT = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01/v12_rereview_02"
)
EXPECTED_SEAL = "2562d617f4741a14f1fd635ab557ff1ce58a6c71dff7b95a014949a6d5f0a3a5"
PAIR_COUNT = 5719
SIDE_COUNT = 11438


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bound(value):
    return {**value, "id": sha(canonical(value))}


def read_bound(path, *, reference=None, expected_path=None):
    path = Path(path).resolve()
    require(expected_path is None or path == Path(expected_path).resolve(), "pair path redirected")
    raw = path.read_bytes()
    value = json.loads(raw)
    require(
        value.get("id") == sha(canonical({k: v for k, v in value.items() if k != "id"})),
        "source content identity changed: " + str(path),
    )
    ref = dict(path=str(path), id=value["id"], sha256=sha(raw))
    if reference is not None:
        require(ref == reference, "sealed byte SHA/content reference changed: " + str(path))
    return value, ref


def projection_fields(core):
    usable = core["A_projection_usable"]
    require(type(usable) is bool or usable is None, "projection usability must retain unknown")
    effective, offline = core["A_reason_projection"], core["offline_A_reason_projection"]
    if effective is None:
        require(usable is not True, "usable projection cannot lack its effective counts")
        raw = positive = masked = None
    else:
        raw = effective["raw_public_characters"]
        positive = effective["positive_public_characters"]
        masked = effective["all_public_reasoning_masked"]
        require(type(raw) is int and raw >= 0, "raw character count invalid")
        if usable is True:
            require(
                type(positive) is int
                and 0 <= positive <= raw
                and type(masked) is bool
                and masked == (raw > 0 and positive == 0),
                "effective usable projection count/flag inconsistent",
            )
        else:
            require(
                positive is None and masked is None, "unavailable projection was counted as usable"
            )
    if offline is not None:
        require(
            effective is None or offline["raw_public_characters"] == raw,
            "offline/effective raw original size changed",
        )
        offline_positive = offline["positive_public_characters"]
        require(
            offline_positive is None or type(offline_positive) is int and offline_positive >= 0,
            "offline unknown must not become zero",
        )
    else:
        offline_positive = None
    return dict(
        A_projection_usable=usable,
        effective_reason_projection=effective,
        offline_reason_projection=offline,
        effective_reason0=(positive == 0) if usable is True else None,
        offline_reason0=(offline_positive == 0) if offline_positive is not None else None,
        offline_known_positive_but_effective_unavailable=(
            usable is not True and offline_positive is not None and offline_positive > 0
        ),
    )


def projection_summary(rows):
    usable = [r for r in rows if r["A_projection_usable"] is True]
    blocked = [r for r in rows if r["A_projection_usable"] is not True]

    def total(values):
        return sum(values) if all(v is not None for v in values) else None

    raw = [
        r["effective_reason_projection"]["raw_public_characters"]
        if r["effective_reason_projection"] is not None
        else None
        for r in rows
    ]
    effective = [
        r["effective_reason_projection"]["positive_public_characters"]
        if r["effective_reason_projection"] is not None
        else None
        for r in rows
    ]
    offline = [
        r["offline_reason_projection"]["positive_public_characters"]
        if r["offline_reason_projection"] is not None
        else None
        for r in rows
    ]
    return dict(
        packages=len(rows),
        usable_projection_packages=len(usable),
        blocked_projection_packages=len(blocked),
        projection_explicit_false_packages=sum(r["A_projection_usable"] is False for r in rows),
        projection_unknown_packages=sum(r["A_projection_usable"] is None for r in rows),
        effective_raw_public_characters=total(raw),
        effective_positive_public_characters=total(effective),
        usable_projection_raw_public_characters_subtotal=sum(
            r["effective_reason_projection"]["raw_public_characters"] for r in usable
        ),
        usable_projection_positive_public_characters_subtotal=sum(
            r["effective_reason_projection"]["positive_public_characters"] for r in usable
        ),
        effective_positive_count_known_packages=sum(v is not None for v in effective),
        effective_positive_count_unknown_packages=sum(v is None for v in effective),
        usable_reason0_packages=sum(r["effective_reason0"] is True for r in usable),
        usable_reason0_with_nonempty_original_packages=sum(
            r["effective_reason0"] is True
            and r["effective_reason_projection"]["raw_public_characters"] > 0
            for r in usable
        ),
        usable_empty_original_public_content_packages=sum(
            r["effective_reason_projection"]["raw_public_characters"] == 0 for r in usable
        ),
        offline_positive_public_characters=total(offline),
        offline_known_positive_public_characters_subtotal=sum(v for v in offline if v is not None),
        offline_positive_count_known_packages=sum(v is not None for v in offline),
        offline_positive_count_unknown_packages=sum(v is None for v in offline),
        blocked_with_known_positive_offline_count=sum(
            r["offline_known_positive_but_effective_unavailable"] for r in blocked
        ),
        known_subtotals_are_not_complete_pool_totals=True,
    )


def task_record(task_id, source_pairs, candidates):
    usable = [r for r in candidates if r["A_projection_usable"] is True]
    blocked = [r for r in candidates if r["A_projection_usable"] is not True]
    return dict(
        task_id=task_id,
        native_correct_pair_count=source_pairs,
        common_process_candidate_count=len(candidates),
        projection_usable_candidate_count=len(usable),
        projection_blocked_candidate_count=len(blocked),
        projection_unknown_candidate_count=sum(
            r["A_projection_usable"] is None for r in candidates
        ),
        all_common_candidates_projection_unusable=bool(candidates) and not usable,
        mixed_usable_and_blocked_projection=bool(usable) and bool(blocked),
        at_least_two_common_packages=len(candidates) >= 2,
        single_candidate_effective_reason0=(
            candidates[0]["effective_reason0"] if len(candidates) == 1 else None
        ),
        common_candidate_slot_ids=[r["slot_id"] for r in candidates],
        candidate_effective_positive_public_characters=(
            sum(r["effective_reason_projection"]["positive_public_characters"] for r in candidates)
            if candidates and not blocked
            else None
        ),
        usable_positive_public_characters_subtotal=sum(
            r["effective_reason_projection"]["positive_public_characters"] for r in usable
        ),
        observed_statistics_only=True,
        new_training_subpopulation=False,
    )


def histogram(rows, field):
    counts = Counter(row[field] for row in rows)
    return {str(k): counts[k] for k in sorted(counts)}


def audit(root=DEFAULT_ROOT, output=None, expected_seal_id=EXPECTED_SEAL):
    root = Path(root).resolve()
    output = Path(output).resolve() if output else root / "report_audit_01/pair_analysis"
    require(
        output != root and root / "report_audit_01" in output.parents,
        "only a new report_audit_01 subdirectory may be written",
    )
    require(not output.exists(), "audit artifact already exists; never overwrite")
    script_sha = sha(Path(__file__).read_bytes())
    seal, seal_ref = read_bound(root / "review_seal/record.json")
    plan, plan_ref = read_bound(root / "registration/record.json")
    source, source_ref = read_bound(Path(plan["source_root"]) / "registration/protocol.json")
    task_ids = source["task_ids"]
    require(
        seal["id"] == expected_seal_id
        and seal["schema"] == "v12_complete_rereview_seal.v1"
        and seal["registration_id"] == plan["id"]
        and seal["protocol_id"] == plan["protocol_identity"]
        and source["id"] == plan["source_protocol_id"]
        and len(task_ids) == len(set(task_ids)) == 1000
        and seal["expected_pairs"] == len(seal["paired_cores"]) == PAIR_COUNT
        and seal["expected_reviews"] == len(plan["jobs"]) == SIDE_COUNT
        and seal["actual_returns"] == SIDE_COUNT
        and seal["network_unknowns"] == 0
        and seal["all_registered_jobs_have_authentic_terminals"] is True,
        "sealed population/protocol/denominator mismatch",
    )
    flags = ("production_admitted", "mapping_started", "training_started")
    require(all(seal[k] is False for k in flags), "seal unexpectedly admits downstream work")
    all_pairs, candidates, native_counts = [], [], Counter()
    by_task = {task: [] for task in task_ids}
    seen = set()
    for index, reference in enumerate(seal["paired_cores"]):
        a, b = plan["jobs"][2 * index : 2 * index + 2]
        core, ref = read_bound(
            reference["path"],
            reference=reference,
            expected_path=root / "pairs" / a["slot_id"].split(":", 1)[1] / "record.json",
        )
        require(
            core["schema"] == "v12_paired_process_core.v1"
            and core["registration_id"] == plan["id"]
            and core["protocol_id"] == plan["protocol_identity"]
            and a["role"] == "A"
            and b["role"] == "B"
            and core["slot_id"] == a["slot_id"] == b["slot_id"]
            and core["task_id"] == a["task_id"] == b["task_id"]
            and core["slot_id"] not in seen
            and core["task_id"] in by_task
            and core["Q_native_as_registered"] is True
            and core["both_actual_responses_returned"] is True
            and core["projection_does_not_filter_process_candidates"] is True
            and all(core[k] is False for k in flags),
            "pair order/identity/downstream flags changed",
        )
        require(
            type(core["joint_process_candidate"]) is bool,
            "completed original pair must retain an explicit observed candidate flag",
        )
        seen.add(core["slot_id"])
        native_counts[core["task_id"]] += 1
        row = dict(
            pair_index=index,
            task_id=core["task_id"],
            slot_id=core["slot_id"],
            pair=ref,
            joint_process_candidate_as_sealed=core["joint_process_candidate"],
            offline_joint_process_candidate=core["offline_joint_process_candidate"],
            offline_candidate_gate=core["offline_candidate_gate"],
            **projection_fields(core),
            production_admitted=False,
            mapping_started=False,
            training_started=False,
            observed_statistics_only=True,
            new_training_subpopulation=False,
        )
        all_pairs.append(row)
        if core["joint_process_candidate"] is True:
            candidates.append(row)
            by_task[core["task_id"]].append(row)
    blocked = [r for r in candidates if r["A_projection_usable"] is not True]
    require(
        [r["slot_id"] for r in candidates] == seal["joint_process_candidate_slot_ids"]
        and len(candidates) == seal["joint_process_candidate_count"]
        and [r["slot_id"] for r in blocked] == seal["projection_blocked_candidate_slot_ids"],
        "statistics must retain exactly all sealed common candidates and blocked projections",
    )
    tasks = [task_record(t, native_counts[t], by_task[t]) for t in task_ids]
    supported_tasks = [t for t in tasks if t["common_process_candidate_count"]]
    candidate_projection = projection_summary(candidates)
    require(
        candidate_projection["effective_raw_public_characters"]
        == seal["candidate_raw_public_characters"]
        and candidate_projection["effective_positive_public_characters"]
        == seal["candidate_positive_public_characters"],
        "effective character totals differ from the original seal",
    )
    summary = bound(
        dict(
            schema="v12_sealed_pair_observation_audit.v1",
            at=datetime.now(timezone.utc).isoformat(),
            complete=True,
            source_seal=seal_ref,
            source_registration=plan_ref,
            original_task_registration=source_ref,
            script=dict(path=str(Path(__file__).resolve()), sha256=script_sha),
            original_tasks=1000,
            original_native_correct_pairs=PAIR_COUNT,
            native_correct_task_coverage=sum(t["native_correct_pair_count"] > 0 for t in tasks),
            common_candidate_packages=len(candidates),
            common_candidate_task_coverage=len(supported_tasks),
            usable_projection_candidate_task_coverage=sum(
                t["projection_usable_candidate_count"] > 0 for t in tasks
            ),
            blocked_projection_candidate_task_coverage=sum(
                t["projection_blocked_candidate_count"] > 0 for t in tasks
            ),
            all_candidates_projection_unusable_task_count=sum(
                t["all_common_candidates_projection_unusable"] for t in tasks
            ),
            mixed_usable_and_blocked_task_count=sum(
                t["mixed_usable_and_blocked_projection"] for t in tasks
            ),
            all_candidates_projection_usable_task_count=sum(
                t["common_process_candidate_count"] > 0
                and t["projection_blocked_candidate_count"] == 0
                for t in tasks
            ),
            at_least_two_common_packages_task_count=sum(
                t["at_least_two_common_packages"] for t in tasks
            ),
            single_common_candidate_tasks=sum(
                t["common_process_candidate_count"] == 1 for t in tasks
            ),
            single_candidate_task_known_reason0_count=sum(
                t["single_candidate_effective_reason0"] is True for t in tasks
            ),
            single_candidate_task_unknown_reason_count=sum(
                t["common_process_candidate_count"] == 1
                and t["single_candidate_effective_reason0"] is None
                for t in tasks
            ),
            common_candidate_count_histogram_original1000=histogram(
                tasks, "common_process_candidate_count"
            ),
            common_candidate_count_histogram_supported_tasks=histogram(
                supported_tasks, "common_process_candidate_count"
            ),
            usable_projection_count_histogram_supported_tasks=histogram(
                supported_tasks, "projection_usable_candidate_count"
            ),
            native_correct_pair_count_histogram_original1000=histogram(
                tasks, "native_correct_pair_count"
            ),
            common_candidate_projection=candidate_projection,
            all_pair_projection_observations=projection_summary(all_pairs),
            all_pair_production_admitted_false=True,
            all_pair_mapping_started_false=True,
            all_pair_training_started_false=True,
            seal_downstream_flags_false=True,
            candidates_file_includes_every_blocked_package=True,
            observed_statistics_only=True,
            new_training_subpopulation=False,
            unknown_counts_are_null_not_zero=True,
            no_judgment_recomputed=True,
            raw_reviews_opened=False,
            wallet_opened=False,
            API_calls=0,
            GPU_used=False,
            production_sources_or_original_artifacts_changed=False,
            interpretation=(
                "Usable/blocked coverage and character subtotals are observations "
                "of the sealed pool, "
                "not authorization to drop blocked packages or train on a filtered subset. Offline "
                "projection counts do not certify an effective projection; unknown stays null. "
                "At least two packages does not establish distinct semantic states or nonzero D_pi."
            ),
        )
    )
    payloads = dict(
        **{
            "summary.json": json.dumps(
                summary, ensure_ascii=False, sort_keys=True, indent=2
            ).encode()
            + b"\n",
            "candidates.jsonl": b"".join(canonical(r) + b"\n" for r in candidates),
            "tasks.jsonl": b"".join(canonical(r) + b"\n" for r in tasks),
        }
    )
    manifest = bound(
        dict(
            schema="v12_pair_observation_audit_manifest.v1",
            summary_id=summary["id"],
            source_seal=seal_ref,
            script_sha256=script_sha,
            files={name: dict(sha256=sha(raw), bytes=len(raw)) for name, raw in payloads.items()},
            candidate_rows=len(candidates),
            task_rows=len(tasks),
            not_training_inputs=True,
        )
    )
    payloads["manifest.json"] = canonical(manifest) + b"\n"
    require(sha(Path(__file__).read_bytes()) == script_sha, "audit script changed during scan")
    write_immutable_artifact_directory(output, payloads)
    return summary


def self_test():
    blocked = projection_fields(
        dict(
            A_projection_usable=False,
            A_reason_projection=dict(
                raw_public_characters=12,
                positive_public_characters=None,
                all_public_reasoning_masked=None,
            ),
            offline_A_reason_projection=dict(
                raw_public_characters=12,
                positive_public_characters=12,
                all_public_reasoning_masked=False,
            ),
        )
    )
    usable = projection_fields(
        dict(
            A_projection_usable=True,
            A_reason_projection=dict(
                raw_public_characters=12,
                positive_public_characters=0,
                all_public_reasoning_masked=True,
            ),
            offline_A_reason_projection=dict(
                raw_public_characters=12,
                positive_public_characters=0,
                all_public_reasoning_masked=True,
            ),
        )
    )
    blocked["slot_id"], usable["slot_id"] = "blocked", "usable"
    result = projection_summary([blocked, usable])
    assert result["effective_positive_public_characters"] is None
    assert result["usable_projection_positive_public_characters_subtotal"] == 0
    assert (
        result["usable_reason0_packages"] == 1
        and result["blocked_with_known_positive_offline_count"] == 1
    )
    task = task_record("test", 2, [blocked, usable])
    assert (
        task["common_process_candidate_count"] == 2 and task["mixed_usable_and_blocked_projection"]
    )
    assert task["candidate_effective_positive_public_characters"] is None
    assert task_record("blocked-only", 1, [blocked])["all_common_candidates_projection_unusable"]
    assert task_record("reason0", 1, [usable])["single_candidate_effective_reason0"] is True
    print("projection/unknown/candidate-retention self-test passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--expected-seal-id", default=EXPECTED_SEAL)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    summary = audit(args.root, args.out, args.expected_seal_id)
    print(
        json.dumps(
            dict(
                summary_id=summary["id"],
                common_candidate_packages=summary["common_candidate_packages"],
                common_candidate_task_coverage=summary["common_candidate_task_coverage"],
                usable_projection_candidate_task_coverage=summary[
                    "usable_projection_candidate_task_coverage"
                ],
                blocked_projection_candidate_task_coverage=summary[
                    "blocked_projection_candidate_task_coverage"
                ],
                all_candidates_projection_unusable_task_count=summary[
                    "all_candidates_projection_unusable_task_count"
                ],
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
