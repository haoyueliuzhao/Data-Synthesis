"""Post-completion descriptive report; no generation, rescoring, or training.

Reads the frozen run, existing native scores and sealed episodes once. The only
writes are compact report outputs in the explicitly selected output directory.
No private-reference file is opened and no inferential significance is claimed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DEFAULT_RUN = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/audit_followup_01"
)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def seconds(start, end):
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def percentile(values, q):
    return sorted(values)[max(0, math.ceil(len(values) * q) - 1)]


def paired(left, right, metric):
    assert left.keys() == right.keys()
    pairs = Counter((left[k][metric], right[k][metric]) for k in left)
    assert all(a in (0, 1) and b in (0, 1) for a, b in pairs)
    return dict(
        denominator=len(left),
        both_positive=pairs[1, 1],
        left_only=pairs[1, 0],
        right_only=pairs[0, 1],
        neither=pairs[0, 0],
        right_minus_left_percentage_points=100 * (pairs[0, 1] - pairs[1, 0]) / len(left),
        interpretation="descriptive same-task comparison; no significance test or causal claim",
    )


def analyze(root):
    root = Path(root).resolve()
    evidence = []

    def read(relative):
        path = root / relative
        raw = path.read_bytes()
        evidence.append(dict(path=relative, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)))
        return json.loads(raw)

    plan = read("protocol.json")
    seal = read("generation_seal/record.json")
    complete = read("complete/record.json")
    gate = read("gate_complete/record.json")
    correction = read("registration_correction/record.json")
    assert seal["complete"] and seal["all_workers_exited"] and complete["complete"]
    assert seal["protocol_id"] == complete["protocol_id"] == plan["id"]
    assert seal["denominator"] == plan["denominator"] == 480
    assert len(plan["jobs"]) == len(complete["reports"]) == 16
    original_reports = {row["job_key"]: row["report"] for row in complete["reports"]}
    rows, shards, episode_evidence, identities = [], [], [], defaultdict(dict)
    call_ids, point_call_ids = Counter(), Counter()
    for job in plan["jobs"]:
        key = job["key"]
        prefix = f"jobs/{key}"
        attempts = sorted((root / prefix / "attempts").iterdir())
        assert [p.name for p in attempts] == ["01"]
        started = read(f"{prefix}/attempts/01/started/record.json")
        outcome = read(f"{prefix}/attempts/01/outcome/record.json")
        assert outcome["status"] == "COMPLETE"
        assert outcome["at"] < seal["at"] < complete["at"]
        run = read(f"{prefix}/generation/run.json")
        shard_seal = read(f"{prefix}/generation/generation_seal/seal.json")
        report = read(f"scoring/{key}/report.json")
        assert report == original_reports[key]
        assert run["tasks"] == job["task_keys"]
        assert report["run_id"] == shard_seal["run_id"] == run["id"]
        assert report["generation_seal_id"] == shard_seal["id"]
        assert shard_seal["complete"] and shard_seal["all_provider_calls_settled"]
        assert len(report["results"]) == len(shard_seal["episodes"]) == 30
        assert report["denominator"] == 30 and not report["fixture_only"]
        assert run["runtime_binding"] == plan["runtime_binding"]
        condition = f"{job['model']}/{job['harness']}"
        assert not identities[condition] or identities[condition] == run["provider"]
        identities[condition] = run["provider"]
        shard_rows = []
        for result, member in zip(report["results"], shard_seal["episodes"], strict=True):
            relative = f"{prefix}/generation/{member['path']}"
            path = (root / relative).resolve()
            assert path.is_relative_to(root / prefix / "generation/episodes")
            raw = path.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == member["sha256"]
            episode = json.loads(raw)
            episode_evidence.append(dict(path=relative, sha256=member["sha256"]))
            assert result["task_key"] == episode["dataset"] + "/" + episode["task_id"]
            assert episode["all_provider_calls_settled"] is True
            assert episode["provider"] == run["provider"]
            assert episode["config"] == run["config"] == job["config"]
            assert episode["provider_attempts"] == len(episode["call_settlements"])
            settlements = Counter(x["state"] for x in episode["call_settlements"])
            assert not (set(settlements) - {"returned", "pre_call_rejected"})
            assert (
                sum(x["actual_model_calls"] for x in episode["call_settlements"])
                == episode["actual_model_calls"]
            )
            assert episode["actual_model_calls"] == len(episode["turns"])
            assert episode["actual_model_calls"] == result["trajectory"]["actual_model_calls"]
            native = result["native"]
            assert all(
                native["native"][m] in (0, 1) for m in ("execution_accuracy", "program_accuracy")
            )
            usage = Counter()
            finish = Counter()
            for turn in episode["turns"]:
                receipt = turn["receipt"]
                assert receipt is not None
                call_ids.update([receipt["call_id"]])
                point_call_ids.update(
                    [(episode["provider"]["parameter_digest"], receipt["call_id"])]
                )
                assert turn["usage"]["prompt_tokens"] == len(receipt["prompt_input_ids"])
                assert turn["usage"]["completion_tokens"] == len(receipt["raw_generated_token_ids"])
                usage.update(turn["usage"])
                finish.update([turn["finish_reason"]])
            tool_errors = Counter()
            tool_names = Counter()
            for tool in episode["tool_events"]:
                tool_names.update([tool["name"]])
                if tool["is_error"]:
                    tool_errors.update([tool["raw_output"].get("message", str(tool["raw_output"]))])
            program = episode["final_program"]
            row = dict(
                condition=condition,
                model=job["model"],
                harness=job["harness"],
                shard=key,
                task_key=result["task_key"],
                execution_accuracy=native["native"]["execution_accuracy"],
                program_accuracy=native["native"]["program_accuracy"],
                native_status=native["status"],
                native_reason=native.get("reason", ""),
                exact_final_answer_match=native.get("derived", {}).get("exact_final_answer_match"),
                final_program_consistency=native["final_program_consistency"]["status"],
                consistency_match=native["final_program_consistency"]["match"],
                explicit_final=int(result["trajectory"]["explicit_final"]),
                semantic_support=result["trajectory"]["complete_semantic_support"],
                stop_reason=episode["stop_reason"],
                actual_model_calls=episode["actual_model_calls"],
                provider_attempts=episode["provider_attempts"],
                settlement_states=dict(settlements),
                tool_calls=len(episode["tool_events"]),
                tool_errors=sum(tool_errors.values()),
                tool_error_messages=dict(tool_errors),
                tool_names=dict(tool_names),
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                finish_reasons=dict(finish),
                elapsed_seconds=episode["elapsed_seconds"],
                final_program_container="absent" if program is None else type(program).__name__,
                final_program_nonempty=bool(program),
                episode_sha256=member["sha256"],
            )
            rows.append(row)
            shard_rows.append(row)
        shards.append(
            dict(
                key=key,
                condition=condition,
                started_at=started["at"],
                completed_at=outcome["at"],
                gpu=started["gpu"],
                pid=started["pid"],
                worker_wall_seconds=seconds(started["at"], outcome["at"]),
                episodes=len(shard_rows),
                model_calls=sum(r["actual_model_calls"] for r in shard_rows),
            )
        )
    conditions = {}
    for name in sorted(identities):
        cohort = [r for r in rows if r["condition"] == name]
        assert len(cohort) == len({r["task_key"] for r in cohort}) == 120
        assert {r["task_key"] for r in cohort} == set(plan["calibration_tasks"])
        summary = dict(denominator=120, provider_identity=identities[name])
        for field in (
            "execution_accuracy",
            "program_accuracy",
            "explicit_final",
            "exact_final_answer_match",
            "actual_model_calls",
            "provider_attempts",
            "tool_calls",
            "tool_errors",
            "prompt_tokens",
            "completion_tokens",
            "elapsed_seconds",
            "final_program_nonempty",
        ):
            summary[field] = sum(r[field] for r in cohort)
        for field in (
            "native_status",
            "native_reason",
            "stop_reason",
            "final_program_consistency",
            "semantic_support",
            "final_program_container",
        ):
            summary[field] = dict(Counter(r[field] for r in cohort))
        for field in ("settlement_states", "tool_names", "tool_error_messages", "finish_reasons"):
            counts = Counter()
            for row in cohort:
                counts.update(row[field])
            summary[field] = dict(counts.most_common())
        summary["episode_time_seconds"] = dict(
            mean=summary["elapsed_seconds"] / 120,
            median=percentile([r["elapsed_seconds"] for r in cohort], 0.5),
            p95_nearest_rank=percentile([r["elapsed_seconds"] for r in cohort], 0.95),
        )
        summary["worker_wall_seconds"] = sum(
            s["worker_wall_seconds"] for s in shards if s["condition"] == name
        )
        conditions[name] = summary
    comparisons = []
    for left, right in (
        ("base/H0", "base/H1"),
        ("static11_step240/H0", "static11_step240/H1"),
        ("base/H0", "static11_step240/H0"),
        ("base/H1", "static11_step240/H1"),
    ):
        a = {r["task_key"]: r for r in rows if r["condition"] == left}
        b = {r["task_key"]: r for r in rows if r["condition"] == right}
        comparisons.append(
            dict(
                left=left,
                right=right,
                **{
                    metric: paired(a, b, metric)
                    for metric in ("execution_accuracy", "program_accuracy", "explicit_final")
                },
            )
        )
    gpu_last = {}
    for shard in shards:
        gpu_last[shard["gpu"]] = max(gpu_last.get(shard["gpu"], ""), shard["completed_at"])
    model_calls = sum(r["actual_model_calls"] for r in rows)
    assert len(rows) == 480 and model_calls <= plan["max_generate_calls_H"]
    started = min(s["started_at"] for s in shards)
    summary = dict(
        schema="finance_research_audit_descriptive_report.v1",
        protocol_id=plan["id"],
        run_root=str(root),
        execution_source_commit=plan["code_commit"],
        analysis_kind=(
            "post-completion descriptive aggregation, not a new preregistered hypothesis test"
        ),
        new_model_calls=0,
        new_private_reference_reads=0,
        native_rescoring_performed=False,
        no_training_value_claim=True,
        denominator=480,
        conditions=conditions,
        comparisons=comparisons,
        shards=shards,
        gate=gate,
        registration_correction=correction,
        timing=dict(
            first_H_worker_at=started,
            last_H_worker_outcome=max(s["completed_at"] for s in shards),
            all_workers_exited_seal_at=seal["at"],
            scoring_complete_at=complete["at"],
            H_elapsed_seconds=seconds(started, seal["at"]),
            scoring_elapsed_seconds=seconds(seal["at"], complete["at"]),
            summed_H_worker_wall_seconds=sum(s["worker_wall_seconds"] for s in shards),
            last_worker_outcome_by_gpu=gpu_last,
            outcome_timestamp_is_not_exact_CUDA_release_timestamp=True,
        ),
        budget=dict(
            H_model_calls=model_calls,
            H_call_cap=plan["max_generate_calls_H"],
            G_model_calls=gate["completed_original_generation_cases"],
            G_call_cap=plan["max_generate_calls_G"],
            API_calls=0,
            real_optimizer_steps=0,
        ),
        source_evidence=evidence,
        sealed_episode_manifest=episode_evidence,
        sealed_episode_manifest_digest=digest(episode_evidence),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        percentile_method="nearest rank, ceil(q*N)",
        token_accounting=(
            "sum of actual per-call TokenReceipt lengths; "
            "prompt histories counted on every generation"
        ),
        receipt_identity=dict(
            total_recorded_calls=sum(call_ids.values()),
            unique_call_id_strings=len(call_ids),
            repeated_call_id_strings=sum(n > 1 for n in call_ids.values()),
            unique_parameter_digest_and_call_id=len(point_call_ids),
            duplicate_point_call_identity=sum(n - 1 for n in point_call_ids.values()),
            call_id_alone_is_not_global_identity=True,
        ),
    )
    summary["id"] = digest(summary)
    return summary, rows


def write_once(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"refuse to overwrite different report bytes: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary, rows = analyze(args.run)
    write_once(
        args.output / "summary.json",
        (
            json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            + "\n"
        ).encode(),
    )
    import io

    table = io.StringIO(newline="")
    fields = [k for k, v in rows[0].items() if not isinstance(v, dict)]
    writer = csv.DictWriter(
        table, fields, extrasaction="ignore", delimiter="\t", lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    write_once(args.output / "per_task.tsv", table.getvalue().encode())
    print(
        json.dumps(
            dict(
                id=summary["id"],
                denominator=480,
                budget=summary["budget"],
                timing=summary["timing"],
                conditions=summary["conditions"],
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
