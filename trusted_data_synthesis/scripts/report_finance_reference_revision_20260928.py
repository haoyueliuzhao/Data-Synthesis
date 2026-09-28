"""Read-only H2/G2 completion report: no model, private gold, or native rescoring.

Aggregates the fixed 480 development-retest sessions and the separate bounded
synthetic G2 diagnostics. Paired counts are descriptive, not significance tests.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

import report_finance_research_audit_20260928 as retained_helpers
from report_finance_research_audit_20260928 import digest, paired, percentile, seconds, write_once

DEFAULT_RUN = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/reference_revision_01"
)
CONDITIONS = {
    "base/Direct-DSL",
    "base/H1-R",
    "static11_step240/Direct-DSL",
    "static11_step240/H1-R",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def reference_values(tool):
    """Eligible resolver fields only; never count prose substrings or DSL program.

    These are reference-bearing arguments, not a claim that every failing call
    reached the resolver, and not evidence of semantic or token-visible support.
    """
    args = tool["normalized_arguments"]
    if tool["name"] == "calculate":
        value = args.get("variables", {})
    elif tool["name"] == "final_answer":
        value = args.get("answer")
    elif tool["name"] == "read_source":
        value = args
    else:
        return []

    def collect(item):
        if isinstance(item, dict):
            return [ref for child in item.values() for ref in collect(child)]
        if isinstance(item, list):
            return [ref for child in item for ref in collect(child)]
        return [item] if isinstance(item, str) and item.startswith("prev:") else []

    return collect(value)


def checked_invocation(identity, *, expected_scope=None, tool_index=None):
    coordinates = {
        key: identity[key] for key in ("run_id", "episode_id", "attempt_index", "turn_index")
    }
    if tool_index is not None:
        coordinates["tool_index"] = tool_index
    require(
        identity["invocation_id"] == "invocation:" + digest(coordinates),
        "invocation identity is not its registered execution coordinates",
    )
    if expected_scope is not None:
        for key in ("run_id", "episode_id"):
            require(coordinates[key] == expected_scope[key], "foreign run/episode invocation")
        attempt = expected_scope.get("attempt_index", expected_scope.get("attempt", 0))
        require(coordinates["attempt_index"] == attempt, "foreign attempt invocation")
    return coordinates


def inspect_episode(episode, *, expected_scope, counters):
    """Audit existing receipts and execution IDs; never call a runtime/scorer."""
    settlements = episode["call_settlements"]
    require(episode["all_provider_calls_settled"] is True, "episode not settled")
    require(episode["provider"]["backend"] == "local_torch", "nonlocal/fixture episode")
    require(episode["provider_attempts"] == len(settlements), "attempt/settlement mismatch")
    require(
        [row["attempt_index"] for row in settlements] == list(range(len(settlements))),
        "unordered settlement attempts",
    )
    require(
        all(row["state"] in {"returned", "pre_call_rejected"} for row in settlements),
        "unknown/infrastructure settlement cannot enter the report denominator",
    )
    require(
        all(
            type(row["actual_model_calls"]) is int and row["actual_model_calls"] >= 0
            for row in settlements
        ),
        "unmetered settlement",
    )
    require(
        all(
            row["actual_model_calls"] == 0
            for row in settlements
            if row["state"] == "pre_call_rejected"
        ),
        "false pre-call rejection",
    )
    require(
        sum(row["actual_model_calls"] for row in settlements) == episode["actual_model_calls"],
        "actual call accounting mismatch",
    )
    returned = [row for row in settlements if row["state"] == "returned"]
    require(
        episode["actual_model_calls"] == len(episode["turns"]) == len(returned),
        "generation without a returned token receipt",
    )
    usage, finish, tool_names, errors = Counter(), Counter(), Counter(), Counter()
    expected_tools = []
    for turn, settlement in zip(episode["turns"], returned, strict=True):
        receipt = turn["receipt"]
        require(
            receipt is not None and receipt["identity"] == episode["provider"],
            "missing/foreign actual token receipt",
        )
        request = turn["provider_metadata"]["request"]
        require(digest(request) == receipt["request_sha256"], "receipt request binding mismatch")
        require(request["config"] == episode["config"], "receipt configuration mismatch")
        require(
            _sha(turn["raw_text"].encode()) == receipt["raw_response_sha256"],
            "receipt raw response binding mismatch",
        )
        prompt = receipt["prompt_input_ids"]
        output = receipt["raw_generated_token_ids"]
        require(
            turn["usage"]["prompt_tokens"] == len(prompt)
            and turn["usage"]["completion_tokens"] == len(output),
            "receipt token count mismatch",
        )
        require(
            prompt and output and len(output) <= episode["config"]["max_new_tokens"],
            "empty/over-budget generated receipt",
        )
        require(
            len(prompt) + episode["config"]["max_new_tokens"] <= episode["config"]["context_limit"],
            "receipt exceeds unchanged context reservation",
        )
        require(
            receipt["actual_eos"] == (output[-1] in receipt["sampling"]["eos_token_ids"]),
            "actual EOS accounting mismatch",
        )
        identity = turn["provider_metadata"]["harness_invocation"]
        coordinates = checked_invocation(identity, expected_scope=expected_scope)
        require(
            coordinates["turn_index"] == settlement["attempt_index"], "turn coordinate mismatch"
        )
        require(
            identity["parameter_digest"] == episode["provider"]["parameter_digest"],
            "invocation parameter point mismatch",
        )
        require(
            settlement["evidence"]["harness_invocation"] == identity,
            "settlement/turn invocation mismatch",
        )
        require(
            settlement["evidence"]["response_sha256"] == digest(turn),
            "settled response content mismatch",
        )
        counters["model_invocation_ids"].update([identity["invocation_id"]])
        counters["receipt_call_ids"].update([receipt["call_id"]])
        counters["point_call_ids"].update(
            [(episode["provider"]["parameter_digest"], receipt["call_id"])]
        )
        usage.update(turn["usage"])
        finish.update([turn["finish_reason"]])
        if len(turn["tool_calls"]) == 1:
            expected_tools.append((turn["tool_calls"][0], coordinates))
    require(
        len(expected_tools) == len(episode["tool_events"]), "tool execution/returned call mismatch"
    )
    ref_values = ref_events = successful_ref_events = successful_ref_values = 0
    for tool, (call, parent) in zip(episode["tool_events"], expected_tools, strict=True):
        require(
            tool["call_id"] == call["call_id"]
            and tool["name"] == call["name"]
            and tool["raw_arguments"] == call["raw_arguments"],
            "foreign tool execution event",
        )
        checked_invocation({**parent, "invocation_id": tool["invocation_id"]}, tool_index=0)
        counters["tool_invocation_ids"].update([tool["invocation_id"]])
        require(
            tool["reference_protocol"] == "visible-result-handle-v2", "wrong reference protocol"
        )
        envelope = json.loads(tool["visible_output"])
        require(
            envelope
            == {
                "result_handle": tool["result_handle"],
                "status": "error" if tool["is_error"] else "ok",
                "output": tool["raw_output"],
            },
            "visible output/raw event mismatch",
        )
        tool_names.update([tool["name"]])
        if tool["is_error"]:
            errors.update([tool["raw_output"].get("message", str(tool["raw_output"]))])
        references = reference_values(tool)
        ref_values += len(references)
        ref_events += bool(references)
        successful_ref_events += bool(references) and not tool["is_error"]
        successful_ref_values += len(references) if not tool["is_error"] else 0
    return dict(
        actual_model_calls=episode["actual_model_calls"],
        provider_attempts=episode["provider_attempts"],
        settlement_states=dict(Counter(row["state"] for row in settlements)),
        tool_calls=len(episode["tool_events"]),
        tool_errors=sum(errors.values()),
        tool_names=dict(tool_names),
        tool_error_messages=dict(errors),
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
        finish_reasons=dict(finish),
        eligible_reference_values=ref_values,
        reference_bearing_tool_calls=ref_events,
        successful_reference_tool_calls=successful_ref_events,
        successful_reference_values=successful_ref_values,
        episodes_with_eligible_reference=int(ref_events > 0),
        episodes_with_successful_reference=int(successful_ref_events > 0),
    )


def identity_summary(counters):
    result = {}
    for key in ("model_invocation_ids", "tool_invocation_ids"):
        values = counters[key]
        result[key] = {
            "count": sum(values.values()),
            "unique": len(values),
            "duplicate_occurrences": sum(count - 1 for count in values.values()),
        }
        require(result[key]["duplicate_occurrences"] == 0, "duplicate actual execution identity")
    require(
        not (counters["model_invocation_ids"].keys() & counters["tool_invocation_ids"].keys()),
        "model/tool invocation identity collision",
    )
    calls, point_calls = counters["receipt_call_ids"], counters["point_call_ids"]
    result["token_receipts"] = dict(
        count=sum(calls.values()),
        unique_technical_call_id_strings=len(calls),
        repeated_technical_call_id_strings=sum(count > 1 for count in calls.values()),
        unique_parameter_digest_and_call_id=len(point_calls),
        duplicate_parameter_digest_and_call_occurrences=sum(
            count - 1 for count in point_calls.values()
        ),
        technical_call_id_not_used_for_execution_deduplication=True,
    )
    return result


def analyze(root):
    root = Path(root).resolve()
    evidence, episode_manifest = [], []

    def read(relative, *, expected_hash=None):
        path = (root / relative).resolve()
        require(path.is_relative_to(root), "report input outside frozen run root")
        require("private.references" not in path.name, "private-reference read forbidden")
        raw = path.read_bytes()
        sha = _sha(raw)
        require(expected_hash is None or sha == expected_hash, "sealed episode bytes changed")
        evidence.append(dict(path=str(path.relative_to(root)), sha256=sha, bytes=len(raw)))
        return json.loads(raw)

    plan, seal, complete, gate = [
        read(path)
        for path in (
            "protocol.json",
            "generation_seal/record.json",
            "complete/record.json",
            "gate_complete/record.json",
        )
    ]
    require(
        seal["complete"] and seal["all_workers_exited"] and complete["complete"], "incomplete run"
    )
    require(
        seal["protocol_id"] == complete["protocol_id"] == plan["id"], "protocol identity mismatch"
    )
    require(plan["denominator"] == seal["denominator"] == 480, "changed 480 denominator")
    require(len(plan["jobs"]) == len(complete["reports"]) == 16, "changed 16-shard design")
    require(
        plan["max_generate_calls_H"] == 7920 and plan["max_generate_calls_G"] == 16,
        "changed H2/G2 budgets",
    )
    require(
        plan["development_retest_not_unseen_confirmation"] is True,
        "wrong experiment interpretation",
    )
    original_reports = {row["job_key"]: row["report"] for row in complete["reports"]}
    rows, shards, identities = [], [], {}
    h_counters, g_counters = defaultdict(Counter), defaultdict(Counter)
    for job in plan["jobs"]:
        key, condition = job["key"], f"{job['model']}/{job['harness']}"
        prefix = f"jobs/{key}"
        require(
            [path.name for path in sorted((root / prefix / "attempts").iterdir())] == ["01"],
            "unexpected worker retry",
        )
        started = read(f"{prefix}/attempts/01/started/record.json")
        outcome = read(f"{prefix}/attempts/01/outcome/record.json")
        require(outcome["status"] == "COMPLETE", "worker did not complete")
        require(
            started["at"] < outcome["at"] < seal["at"] < complete["at"], "invalid completion order"
        )
        run = read(f"{prefix}/generation/run.json")
        shard_seal = read(f"{prefix}/generation/generation_seal/seal.json")
        report = read(f"scoring/{key}/report.json")
        require(report == original_reports[key], "report differs from completion manifest")
        require(run["tasks"] == job["task_keys"], "shard task roster changed")
        require(report["run_id"] == shard_seal["run_id"] == run["id"], "shard run binding mismatch")
        require(report["generation_seal_id"] == shard_seal["id"], "score/seal binding mismatch")
        require(
            shard_seal["complete"] and shard_seal["all_provider_calls_settled"], "unsealed shard"
        )
        require(
            len(report["results"]) == len(shard_seal["episodes"]) == report["denominator"] == 30,
            "changed 30-task shard denominator",
        )
        require(
            not report["fixture_only"] and run["runtime_binding"] == plan["runtime_binding"],
            "fixture or runtime drift",
        )
        require(
            condition not in identities or identities[condition] == run["provider"],
            "condition parameter point changed",
        )
        identities[condition] = run["provider"]
        shard_rows = []
        for result, member in zip(report["results"], shard_seal["episodes"], strict=True):
            relative = f"{prefix}/generation/{member['path']}"
            require(
                (root / relative).resolve().is_relative_to(root / prefix / "generation/episodes"),
                "episode escaped registered shard",
            )
            episode = read(relative, expected_hash=member["sha256"])
            episode_manifest.append(dict(path=relative, sha256=member["sha256"]))
            require(
                result["task_key"] == episode["dataset"] + "/" + episode["task_id"], "task mismatch"
            )
            require(
                episode["provider"] == run["provider"]
                and episode["config"] == run["config"] == job["config"],
                "episode identity/configuration mismatch",
            )
            accounting = inspect_episode(
                episode,
                expected_scope={"run_id": run["id"], "episode_id": member["key"], "attempt": 1},
                counters=h_counters,
            )
            require(
                accounting["actual_model_calls"] == result["trajectory"]["actual_model_calls"],
                "score/episode invocation count mismatch",
            )
            native = result["native"]
            require(
                all(
                    native["native"][metric] in (0, 1)
                    for metric in ("execution_accuracy", "program_accuracy")
                ),
                "native primary score unavailable",
            )
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
                valid_program=int(native["status"] == "scored"),
                exact_final_answer_match=native.get("derived", {}).get("exact_final_answer_match"),
                final_program_consistency=native["final_program_consistency"]["status"],
                consistency_match=native["final_program_consistency"]["match"],
                explicit_final=int(result["trajectory"]["explicit_final"]),
                semantic_support=result["trajectory"]["complete_semantic_support"],
                stop_reason=episode["stop_reason"],
                **accounting,
                elapsed_seconds=episode["elapsed_seconds"],
                final_program_container="absent"
                if episode["final_program"] is None
                else type(episode["final_program"]).__name__,
                final_program_nonempty=bool(episode["final_program"]),
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
                process_identity=started["process_identity"],
                attempts=1,
                status=outcome["status"],
                episodes=len(shard_rows),
                worker_wall_seconds=seconds(started["at"], outcome["at"]),
                model_calls=sum(row["actual_model_calls"] for row in shard_rows),
            )
        )

    require(set(identities) == CONDITIONS, "unexpected four-condition matrix")
    conditions = {}
    for name in sorted(identities):
        cohort = [row for row in rows if row["condition"] == name]
        require(
            len(cohort) == len({row["task_key"] for row in cohort}) == 120,
            "changed 120-task condition denominator",
        )
        require(
            {row["task_key"] for row in cohort} == set(plan["calibration_tasks"]),
            "condition task roster differs from preregistration",
        )
        value = dict(denominator=120, provider_identity=identities[name])
        for field in (
            "execution_accuracy",
            "program_accuracy",
            "explicit_final",
            "valid_program",
            "exact_final_answer_match",
            "actual_model_calls",
            "provider_attempts",
            "tool_calls",
            "tool_errors",
            "prompt_tokens",
            "completion_tokens",
            "elapsed_seconds",
            "final_program_nonempty",
            "eligible_reference_values",
            "reference_bearing_tool_calls",
            "successful_reference_tool_calls",
            "successful_reference_values",
            "episodes_with_eligible_reference",
            "episodes_with_successful_reference",
        ):
            value[field] = sum(row[field] for row in cohort)
        for field in (
            "native_status",
            "native_reason",
            "stop_reason",
            "final_program_consistency",
            "semantic_support",
            "final_program_container",
        ):
            value[field] = dict(Counter(row[field] for row in cohort))
        for field in ("settlement_states", "tool_names", "tool_error_messages", "finish_reasons"):
            counts = Counter()
            for row in cohort:
                counts.update(row[field])
            value[field] = dict(counts.most_common())
        value["episode_time_seconds"] = dict(
            mean=value["elapsed_seconds"] / 120,
            median=percentile([row["elapsed_seconds"] for row in cohort], 0.5),
            p95_nearest_rank=percentile([row["elapsed_seconds"] for row in cohort], 0.95),
        )
        value["worker_wall_seconds"] = sum(
            shard["worker_wall_seconds"] for shard in shards if shard["condition"] == name
        )
        conditions[name] = value

    comparisons = []
    for left, right in (
        ("base/Direct-DSL", "base/H1-R"),
        ("static11_step240/Direct-DSL", "static11_step240/H1-R"),
        ("base/Direct-DSL", "static11_step240/Direct-DSL"),
        ("base/H1-R", "static11_step240/H1-R"),
    ):
        a = {row["task_key"]: row for row in rows if row["condition"] == left}
        b = {row["task_key"]: row for row in rows if row["condition"] == right}
        comparisons.append(
            dict(
                left=left,
                right=right,
                **{
                    metric: paired(a, b, metric)
                    for metric in (
                        "execution_accuracy",
                        "program_accuracy",
                        "explicit_final",
                        "valid_program",
                    )
                },
            )
        )

    gate_start = read("jobs/G2/attempts/01/started/record.json")
    gate_outcome = read("jobs/G2/attempts/01/outcome/record.json")
    require(gate_outcome["status"] == "COMPLETE", "G2 worker incomplete")
    require(len(gate["cases"]) == 4, "changed four-case G2 diagnostic")
    gate_accounting = []
    for case in gate["cases"]:
        record = read(str(Path(case["episode_path"]).resolve().relative_to(root)))
        accounting = inspect_episode(
            record["episode"], expected_scope=record["invocation_context"], counters=g_counters
        )
        require(
            accounting["actual_model_calls"]
            == record["actual_model_calls"]
            == case["actual_model_calls"],
            "G2 actual calls disagree",
        )
        require(
            len(case["replays"]) == accounting["actual_model_calls"], "G2 replay receipt missing"
        )
        gate_accounting.append(
            dict(index=case["index"], kind=case["kind"], point=case["point"], **accounting)
        )
    gate_calls = sum(row["actual_model_calls"] for row in gate_accounting)
    model_calls = sum(row["actual_model_calls"] for row in rows)
    require(
        len(rows) == 480 and model_calls <= 7920 and gate_calls <= 16, "generation cap exceeded"
    )
    require(
        gate_calls == gate["actual_new_generation_calls_this_invocation"], "gate budget mismatch"
    )
    combined = defaultdict(Counter)
    for counters in (h_counters, g_counters):
        for name, values in counters.items():
            combined[name].update(values)
    gpu_last = {}
    for shard in shards:
        gpu_last[shard["gpu"]] = max(gpu_last.get(shard["gpu"], ""), shard["completed_at"])
    first = min(shard["started_at"] for shard in shards)
    summary = dict(
        schema="finance_reference_revision_descriptive_report.v1",
        protocol_id=plan["id"],
        previous_protocol_id=plan["previous_protocol_id"],
        run_root=str(root),
        execution_source_commit=plan["code_commit"],
        analysis_kind="post-completion descriptive aggregation",
        development_retest_not_unseen_confirmation=True,
        equal_compute_comparison=False,
        isolated_ID_visibility_causal_effect_claimed=False,
        new_model_calls=0,
        new_private_reference_reads=0,
        native_rescoring_performed=False,
        no_training_value_claim=True,
        denominator=480,
        conditions=conditions,
        comparisons=comparisons,
        shards=shards,
        gate=gate,
        gate_episode_accounting=gate_accounting,
        timing=dict(
            G2_worker_started_at=gate_start["at"],
            G2_worker_completed_at=gate_outcome["at"],
            first_H_worker_at=first,
            last_H_worker_outcome=max(shard["completed_at"] for shard in shards),
            all_workers_exited_seal_at=seal["at"],
            scoring_complete_at=complete["at"],
            H_elapsed_seconds=seconds(first, seal["at"]),
            scoring_elapsed_seconds=seconds(seal["at"], complete["at"]),
            summed_H_worker_wall_seconds=sum(shard["worker_wall_seconds"] for shard in shards),
            last_worker_outcome_by_gpu=gpu_last,
            all_workers_exited_asserted_by_generation_seal=True,
            outcome_timestamp_is_not_exact_CUDA_release_timestamp=True,
        ),
        budget=dict(
            H_model_calls=model_calls,
            H_call_cap=7920,
            G_model_calls=gate_calls,
            G_call_cap=16,
            total_model_calls=model_calls + gate_calls,
            total_call_cap=7936,
            API_calls=0,
            real_optimizer_steps=0,
        ),
        invocation_identity=dict(
            H2=identity_summary(h_counters),
            G2=identity_summary(g_counters),
            combined=identity_summary(combined),
        ),
        source_evidence=evidence,
        sealed_episode_manifest=episode_manifest,
        sealed_episode_manifest_digest=digest(episode_manifest),
        source_modules={
            str(Path(__file__).name): _sha(Path(__file__).read_bytes()),
            str(Path(retained_helpers.__file__).name): _sha(
                Path(retained_helpers.__file__).read_bytes()
            ),
        },
        percentile_method="nearest rank, ceil(q*N)",
        valid_program_definition="existing native status == scored; no new program execution",
        consistency_definition=(
            "original exact numeric/string diagnostic; not scale-aware financial contradiction"
        ),
        token_accounting="actual TokenReceipt lengths; full prompt history counted per generation",
        reference_counting_definition=(
            "whole strings beginning prev: at normalized calculate.variables, final_answer.answer, "
            "or read_source argument values; excludes expression/prose/DSL program; "
            "only successful ToolEvents count as successful reference use. "
            "Not CompletePass or per-token visibility admission."
        ),
    )
    summary["id"] = digest(summary)
    return summary, rows


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
    table = io.StringIO(newline="")
    fields = [key for key, value in rows[0].items() if not isinstance(value, dict)]
    writer = csv.DictWriter(
        table, fields, extrasaction="ignore", delimiter="\t", lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    write_once(args.output / "per_task.tsv", table.getvalue().encode())
    print(
        json.dumps(
            {
                "id": summary["id"],
                "denominator": len(rows),
                "budget": summary["budget"],
                "conditions": summary["conditions"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
