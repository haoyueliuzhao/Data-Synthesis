"""Bounded, CPU-only diagnostics of sealed B predictions and 24 old outers.

No model loading, generation, rescoring, gradient recovery, or old-file writes.
The parser classifier labels the first return of the *actual original parser*
without changing any branch predicate or accepting a formerly rejected prefix.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import math
import textwrap
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.finance_research import qwen_protocol
from trusted_synthesis.finance_research.contracts import digest

REPO = Path(__file__).resolve().parents[2]
V18 = REPO / ("trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
              "v18_researcher_continuation_01")
V25 = V18 / "v25_training_replication_01"
OUTPUT = V25 / "v54_historical_diagnostics_01"
SEEDS, ARMS, STEPS = (137, 251, 389), ("static", "c_only", "full"), (298, 596, 894, 1192)
PARSER_BRANCHES = (
    "A_no_opening_envelope",
    "B_malformed_tag_in_prose_prefix",
    "C_non_envelope_between_or_after_envelopes",
    "D_invalid_call_object_schema",
    "E_missing_closing_envelope",
    "F_strict_JSON_or_argument_extraction_exception",
    "G_accepted_tool_envelopes",
)
SELECTION_RULE = {
    "maximum_per_model": 10, "maximum_total": 90,
    "population": "all old B invalid_prediction episodes with available original bytes",
    "categories": list(PARSER_BRANCHES),
    "order": "round robin through alphabetical first-rejection categories; within each category ascending episode SHA256",
    "full_population_classification_is_automatic": True,
    "manual_reading_is_limited_to_selected_episodes": True,
    "no_repair_no_rescore_no_regeneration": True,
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path, expected=None):
    path = Path(path).resolve()
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    require(expected is None or sha == expected, "source bytes differ from seal: " + str(path))
    return json.loads(raw), {"path": str(path), "sha256": sha, "bytes": len(raw)}


def publish(directory, body):
    value = {**body, "id": digest(body)}
    path = Path(directory)
    if path.exists():
        require(json.loads((path / "record.json").read_bytes()) == value,
                "diagnostic output is immutable: " + str(path))
    else:
        raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                          allow_nan=False) + "\n").encode()
        write_immutable_artifact_directory(path, {"record.json": raw})
    return value


def _classified_original_parser():
    source = textwrap.dedent(inspect.getsource(qwen_protocol.parse_qwen_native_response))
    tree = ast.parse(source)
    returns = sorted((node for node in ast.walk(tree) if isinstance(node, ast.Return)),
                     key=lambda node: node.lineno)
    # One nested skip() return is not a rejection branch.
    returns = [node for node in returns if isinstance(node.value, ast.Tuple)]
    require(len(returns) == 7, "original parser return structure changed")
    for node, label in zip(returns, PARSER_BRANCHES, strict=True):
        node.value = ast.Tuple(elts=[ast.Constant(label), node.value], ctx=ast.Load())
    ast.fix_missing_locations(tree)
    namespace = dict(qwen_protocol.parse_qwen_native_response.__globals__)
    exec(compile(tree, __file__ + "::label_original_parser_returns", "exec"), namespace)
    return namespace["parse_qwen_native_response"]


_PARSER = _classified_original_parser()


def classify_response(raw, *, call_prefix="diagnostic"):
    category, (prefix, calls) = _PARSER(raw, call_prefix=call_prefix)
    return {"category": category, "accepted": bool(calls),
            "accepted_call_count": len(calls), "canonical_prefix": prefix,
            "calls": [call.model_dump(mode="json") for call in calls]}


def quantiles(values):
    values = sorted(values)
    if not values:
        return None
    result = {}
    for fraction in (0, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1):
        position = fraction * (len(values) - 1)
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        result[str(fraction)] = values[lower] + (values[upper] - values[lower]) * (position - lower)
    return result


def select_examples(rows, maximum=10):
    groups = defaultdict(list)
    for row in rows:
        if row.get("available"):
            groups[row["category"]].append(row)
    groups = {label: sorted(values, key=lambda row: (row["episode"]["sha256"], row["task_key"]))
              for label, values in groups.items()}
    selected, ordinal = [], 0
    while len(selected) < maximum:
        chosen = [groups[label][ordinal] for label in sorted(groups) if ordinal < len(groups[label])]
        if not chosen:
            break
        selected.extend(chosen[:maximum - len(selected)])
        ordinal += 1
    return selected


def inspect_invalid(row, generation, entry):
    path = (generation / entry["path"]).resolve()
    try:
        episode, binding = read(path, entry["sha256"])
    except (FileNotFoundError, ValueError) as error:
        return dict(task_key=row["task_key"], available=False, category="NA_original_archive_unavailable",
                    reason=str(error), expected_episode=entry)
    require(f"{episode['dataset']}/{episode['task_id']}" == row["task_key"],
            "score and original episode task differ")
    require(episode["stop_reason"] == row["stop_reason"]
            and episode["actual_model_calls"] == row["actual_model_calls"],
            "score and original episode termination differ")
    turns = []
    previous_ids = set()
    for index, turn in enumerate(episode["turns"]):
        receipt = turn.get("receipt")
        if receipt is None:
            turns.append(dict(call_index=index + 1, category="NA_missing_receipt"))
            continue
        require(hashlib.sha256(turn["raw_text"].encode()).hexdigest()
                == receipt["raw_response_sha256"], "response bytes differ from original receipt")
        parsed = classify_response(turn["raw_text"], call_prefix=receipt["call_id"])
        before = [event for event in episode["tool_events"] if event["call_id"] in previous_ids]
        raw = turn["raw_text"]
        turns.append(dict(
            call_index=index + 1, category=parsed["category"],
            parsed_call_count=parsed["accepted_call_count"],
            saved_parser_result_matches=parsed["calls"] == turn["tool_calls"],
            raw_response_sha256=receipt["raw_response_sha256"],
            raw_characters=len(raw), raw_utf8_bytes=len(raw.encode()),
            generated_tokens=len(receipt["raw_generated_token_ids"]),
            prompt_tokens=len(receipt["prompt_input_ids"]),
            actual_EOS=receipt["actual_eos"], finish_reason=receipt["finish_reason"],
            earlier_tool_event_count=len(before),
            earlier_tool_error_count=sum(bool(event["is_error"]) for event in before),
            earlier_tool_names=dict(Counter(event["name"] for event in before)),
            has_opening_tag="<tool_call>" in raw, has_closing_tag="</tool_call>" in raw,
            has_markdown_fence="```" in raw,
            receipt_sha256=digest(receipt),
        ))
        previous_ids.update(call["call_id"] for call in turn["tool_calls"])
    terminal = turns[-1] if turns else {"category": "NA_no_returned_turn"}
    return dict(task_key=row["task_key"], source_group=row["source_group"], available=True,
                episode=binding, stop_reason=row["stop_reason"], native_reason=row["native"].get("reason"),
                category=terminal["category"], terminal_call=terminal, turns=turns,
                any_saved_parser_mismatch=any(t.get("saved_parser_result_matches") is False for t in turns),
                actual_model_calls=row["actual_model_calls"])


def model_diagnostic(v25, seed, arm):
    root = Path(v25) / f"replication_evaluation/models/seed{seed}/{arm}"
    score, source = read(root / "scores/record.json")
    whole, whole_source = read(root / "whole_test_seal/record.json")
    sealed, seal_source = read(whole["generation_seal"]["path"], whole["generation_seal"]["sha256"])
    generation = Path(seal_source["path"]).parent.parent
    run, run_source = read(generation / "run.json")
    require(score["denominator"] == 1147 and len(score["results"]) == 1147,
            "old score is not complete test1147")
    require(run["episode_keys"] == [entry["key"] for entry in sealed["episodes"]],
            "run/seal ordered episode roster differs")
    index = dict(zip(run["tasks"], sealed["episodes"], strict=True))
    invalid = [row for row in score["results"] if row["native"]["status"] == "invalid_prediction"]
    rows = [inspect_invalid(row, generation, index[row["task_key"]]) for row in invalid]
    rows.sort(key=lambda row: row["task_key"])
    missing_no_tool = [row for row in invalid if row["native"].get("reason") == "missing_or_invalid_submission"
                       and row["stop_reason"] == "no_tool_call"]
    terminal = [row["terminal_call"] for row in rows if row["available"]]
    return dict(
        coordinate=f"seed{seed}/{arm}", seed=seed, arm=arm, denominator=1147,
        source_score=source, source_whole_seal=whole_source, source_generation_seal=seal_source,
        source_run=run_source, invalid_count=len(invalid),
        missing_submission_and_no_tool_call=len(missing_no_tool),
        missing_submission_no_tool_call_at_call1_or2=sum(row["actual_model_calls"] in (1, 2)
                                                       for row in missing_no_tool),
        invalid_reason_counts=dict(Counter(row["native"].get("reason", "NA") for row in invalid)),
        terminal_category_counts=dict(Counter(row["category"] for row in rows)),
        invalid_no_tool_category_counts=dict(Counter(row["category"] for row in rows
                                                     if row.get("stop_reason") == "no_tool_call")),
        overlapping_terminal_features={
            "finish_reason_length": sum(row.get("finish_reason") == "length" for row in terminal),
            "actual_EOS": sum(row.get("actual_EOS") is True for row in terminal),
            "call1_or2": sum(row.get("call_index") in (1, 2) for row in terminal),
            "prior_tool_event": sum(row.get("earlier_tool_event_count", 0) > 0 for row in terminal),
            "prior_tool_error": sum(row.get("earlier_tool_error_count", 0) > 0 for row in terminal),
            "markdown_fence": sum(row.get("has_markdown_fence") is True for row in terminal),
        },
        terminal_generated_token_quantiles=quantiles([row["generated_tokens"] for row in terminal
                                                     if "generated_tokens" in row]),
        original_archive_unavailable=sum(not row["available"] for row in rows),
        parser_disagreement_count=sum(row.get("any_saved_parser_mismatch", False) for row in rows),
        rows=rows,
    )


def invalid_diagnostics(v25, output):
    coordinates = [(seed, arm) for seed in SEEDS for arm in ARMS]
    with ThreadPoolExecutor(max_workers=4) as pool:
        models = list(pool.map(lambda pair: model_diagnostic(v25, *pair), coordinates))
    examples = []
    for model in models:
        selected = select_examples(model["rows"])
        examples.extend(dict(coordinate=model["coordinate"], **row) for row in selected)
        publish(Path(output) / "invalid/models" / model["coordinate"], model)
    selection = publish(Path(output) / "invalid/selection", dict(
        schema="v54_bounded_old_response_selection.v1", rule=SELECTION_RULE,
        selected=[{k: row[k] for k in ("coordinate", "task_key", "category", "episode")}
                  for row in examples], count=len(examples),
        selection_precedes_qualitative_reading=True,
    ))
    # Only registered examples have raw response text copied into the reading packet.
    samples = []
    for row in examples:
        episode, _ = read(row["episode"]["path"], row["episode"]["sha256"])
        samples.append(dict(
            coordinate=row["coordinate"], task_key=row["task_key"], category=row["category"],
            original_episode=row["episode"], terminal_call=row["terminal_call"],
            native_reason=row["native_reason"], stop_reason=row["stop_reason"],
            raw_turns=[turn["raw_text"] for turn in episode["turns"]],
            tool_events=episode["tool_events"], final_answer=episode["final_answer"],
        ))
    publish(Path(output) / "invalid/reading_packet", dict(
        schema="v54_bounded_old_response_reading_packet.v1", selection_id=selection["id"],
        examples=samples, manual_reading_completed=False,
    ))
    fields = ("denominator", "invalid_count", "missing_submission_and_no_tool_call",
              "missing_submission_no_tool_call_at_call1_or2", "original_archive_unavailable",
              "parser_disagreement_count")
    summary = {key: sum(model[key] for model in models) for key in fields}
    counts = Counter()
    for model in models:
        counts.update(model["terminal_category_counts"])
    return publish(Path(output) / "invalid/summary", dict(
        schema="v54_old_B_invalid_diagnostics.v1", **summary,
        prior_reported_counts={"invalid": 2979, "missing_submission_no_tool_call": 2842,
                               "at_call1_or2": 2818},
        prior_reported_counts_reproduced=(summary["invalid_count"],
            summary["missing_submission_and_no_tool_call"],
            summary["missing_submission_no_tool_call_at_call1_or2"]) == (2979, 2842, 2818),
        parser_source={"path": str(Path(qwen_protocol.__file__).resolve()),
                       "sha256": hashlib.sha256(Path(qwen_protocol.__file__).read_bytes()).hexdigest()},
        terminal_category_counts=dict(counts),
        models=[{key: value for key, value in model.items() if key != "rows"} for model in models],
        selection_id=selection["id"], selected_reading_count=len(examples),
        native_scores_changed=False, parser_changed=False, new_generation=0,
        length_limit_is_not_proof_longer_output_would_fix=True,
        accepted_prefix_is_not_proof_full_trajectory_would_succeed=True,
    ))


def outer_statistics(record):
    evidence = record["evidence"]
    distribution = evidence["distribution"]
    temperature = distribution["temperature"]
    diagnostics = distribution["task_diagnostics"]
    selected = [row for row in diagnostics.values() if row["optimized"]]
    normalized, raw, weights = [], [], []
    for row in selected:
        for state, value in row["C"].items():
            raw.append(value)
            normalized.append(value / row["T_C"])
            weights.append(row["mu"] * row["pi_current"][state])
    total = math.fsum(weights)
    cutoff = math.log(99)  # Predefined sigmoid saturation: <=.01 or >=.99 before epsilon map.
    return dict(
        global_weighted_RMS_C_over_mu=temperature["global_weighted_RMS"],
        RMS_floor=temperature["RMS_floor"],
        floor_active=temperature["global_weighted_RMS"] < temperature["RMS_floor"],
        scale_after_floor=temperature["global_scale_after_floor"],
        raw_C_RMS_unweighted_active_states=math.sqrt(math.fsum(v*v for v in raw)/len(raw)),
        raw_C_quantiles_active_states=quantiles(raw),
        normalized_C_over_T_C_quantiles_active_states=quantiles(normalized),
        quantiles_weighting="unweighted over optimized (task,state) support; singleton controls excluded",
        sigmoid_saturation={
            "definition": "sigmoid(C/T_C)<=0.01 or >=0.99, before epsilon map",
            "normalized_threshold_absolute": cutoff,
            "active_state_count": len(normalized),
            "saturated_state_count": sum(abs(value) >= cutoff for value in normalized),
            "noncontrol_mu_pi_weighted_mass": math.fsum(
                weight for weight, value in zip(weights, normalized, strict=True)
                if abs(value) >= cutoff) / total,
        },
        weighted_TV=distribution["weighted_TV"],
        weighted_KL_next_current=distribution["weighted_KL_next_current"],
        weighted_KL_next_prior=distribution["weighted_KL_next_prior"],
        weighted_entropy=distribution["weighted_entropy"],
        contribution_exponent=distribution["contribution_exponent"],
        effective_novelty_exponent=distribution["effective_novelty_exponent"],
        lambda_current=distribution["lambda_current"], lambda_prior=distribution["lambda_prior"],
    )


def old_outer_diagnostics(v25, output):
    from trusted_synthesis.finance_research.storage import load_public_snapshot

    reward_sources = {}
    for path in sorted((Path(v25) / "training_replication").glob(
            "seed*/arms/*/feedback/*/native_rewards/record.json")):
        value, source = read(path)
        reward_sources[value["cohort_seal_sha256"]] = (value, source, path.parent.parent)
    lineage_by_snapshot, rows = {}, []
    for seed in SEEDS:
        for arm in ("c_only", "full"):
            for step in STEPS:
                path = Path(v25) / f"training_replication/seed{seed}/arms/{arm}/training/step{step:04d}_outer/record.json"
                record, source = read(path)
                evidence = record["evidence"]
                report = evidence["feedback_report"]
                require(report["denominator"] == 700, "old feedback denominator changed")
                item = dict(seed=seed, arm=arm, step=step, source=source,
                            point_id=report["point_id"], cohort_seal_sha256=report["cohort_seal_sha256"],
                            statistics=outer_statistics(record),
                            successful_feedback_sessions=700-report["accounting"]["zero_reward_trajectories_skipped"],
                            draw_gradient_direction={"status": "NA", "reason": "no separately saved draw gJ/C in committed outer payload; no new backward authorized here"},
                            supervised_coefficient_mass={"status": "NA", "reason": "outer record has distributions but no token-segment coefficient attribution"},
                            actual_segment_loss_or_gradient={"status": "NA", "reason": "no saved per-segment NLL or gradient attribution; weights are not losses or gradients"})
                pair = reward_sources.get(report["cohort_seal_sha256"])
                if pair is None:
                    item["success_coverage"] = {"status": "NA", "reason": "original native reward archive unavailable"}
                else:
                    rewards, reward_source, feedback_root = pair
                    require(len(rewards["rewards"]) == len(rewards["scores"]) == 700,
                            "incomplete historical feedback archive")
                    successful = [score["task_id"] for reward, score in
                                  zip(rewards["rewards"], rewards["scores"], strict=True) if reward == 1]
                    require(len(successful) == item["successful_feedback_sessions"],
                            "old feedback report/reward vector mismatch")
                    run, run_source = read(feedback_root / "draw0/run.json")
                    snapshot = run["snapshot"]
                    if snapshot not in lineage_by_snapshot:
                        _, public, lineages = load_public_snapshot(snapshot)
                        lineage_by_snapshot[snapshot] = {
                            task.task_id: dict(group=lineage.source_group, level=lineage.source_group_level)
                            for task, lineage in zip(public, lineages, strict=True)
                        }
                    source_map = lineage_by_snapshot[snapshot]
                    groups = Counter(source_map[task]["group"] for task in successful)
                    item["success_coverage"] = dict(
                        status="AVAILABLE", reward_source=reward_source, source_roster=run_source,
                        successful_sessions=len(successful), unique_successful_tasks=len(set(successful)),
                        unique_successful_source_groups=len(groups), source_group_session_counts=dict(groups),
                        unique_successful_tasks_by_draw=[len({score["task_id"] for reward, score in
                            zip(rewards["rewards"][start:start+350], rewards["scores"][start:start+350], strict=True)
                            if reward == 1}) for start in (0,350)],
                        successful_sessions_by_draw=[sum(rewards["rewards"][start:start+350])
                                                     for start in (0,350)],
                    )
                rows.append(item)
    return publish(Path(output) / "outer_signals", dict(
        schema="v54_existing_B_24_outer_signals.v1", expected_outer_count=24,
        observed_outer_count=len(rows), rows=rows,
        new_gradient_backwards=0, new_feedback=0, new_scoring=0,
        floor_active_count=sum(row["statistics"]["floor_active"] for row in rows),
        original_RMS_definition="sqrt(sum_noncontrol mu*pi*(C/mu)^2/sum_noncontrol mu)",
        C_already_contains_mu=True,
        missing_optional_fields_are_NA_not_zero=True,
    ))


def existing_mechanisms(v18, output):
    points = []
    for seed in (11, 29, 47):
        build, binding = read(Path(v18) / f"mechanisms/seed{seed}/N_same_point/result/record.json")
        arithmetic = build["arithmetic"]
        outer, outer_binding = read(Path(build["source_outer"]["path"]) / "record.json")
        point_valid = (arithmetic["genuine_theta_Adam_RNG_G_feedback_identity_verified"] is True
                       and arithmetic["actual_outer_inputs_digest"] == outer["outer_inputs_digest"]
                       and outer["actual_state_digest"] == build["source_outer"]["actual_state_digest"])
        require(point_valid, "same-point C/N source binding is not established")
        C, qc, qn = outer["evidence"]["C"], arithmetic["C_only"], arithmetic["Full"]
        direction = math.fsum(C[task][state] * (qn[task][state]-qc[task][state])
                              for task in C for state in C[task])
        shrink, shrink_binding = read(Path(v18) / f"v23_confirmation_shrink_01/shrink_control/seed{seed}/result/record.json")
        require(shrink["actual_outer_inputs_digest"] == outer["outer_inputs_digest"],
                "shrink does not share the saved C/parameter point")
        points.append(dict(seed=seed, N_build=binding, source_outer=outer_binding,
                           same_point_binding_verified=True,
                           sum_C_times_qN_minus_qC=direction, extra_mu_factor_applied=False,
                           shrink_build=shrink_binding, shrink_gamma=shrink["gamma"],
                           sum_C_times_qShrink_minus_qC=math.fsum(
                               C[task][state]*(shrink["q_shrink"][task][state]-qc[task][state])
                               for task in C for state in C[task])))
    shrink, shrink_source = read(Path(v18) / "v23_confirmation_shrink_01/shrink_control/evaluation_result/record.json")
    C_results = []
    for seed in (11,29,47):
        values, sources = {}, []
        for condition in ("Static", "positive", "reverse"):
            root = Path(v18) / f"mechanisms/seed{seed}/evaluation/C_direction/{condition}"
            score, source = read(root / "scores/record.json")
            sources.append(source)
            by_mode = defaultdict(list)
            for draw in (0,1,2):
                run, _ = read(root / f"draw{draw}/run.json")
                mode = "greedy" if run["config"]["temperature"] == 0 else "stochastic_T1"
                require(run["config"]["temperature"] in (0,1), "unregistered old diagnostic temperature")
                by_mode[mode].extend(row["native"]["native"]["execution_accuracy"]
                                     for row in score["rows"] if row["draw"] == draw)
            values[condition] = {mode: sum(rows)/len(rows) for mode, rows in by_mode.items()}
        C_results.append(dict(seed=seed, sources=sources, means=values,
                              positive_minus_Static={mode: values["positive"][mode]-values["Static"][mode]
                                                     for mode in values["Static"]}))
    return publish(Path(output) / "existing_mechanisms", dict(
        schema="v54_read_only_existing_C_N_shrink.v1", old_seed_scope=[11,29,47],
        points=points, C_direction=C_results,
        C_positive_minus_Static_means={mode: math.fsum(row["positive_minus_Static"][mode]
                                                      for row in C_results)/3
                                      for mode in ("greedy", "stochastic_T1")},
        N_shrink_evaluation_source=shrink_source,
        N_shrink_mean_differences=shrink["mean_differences"],
        new_training_or_feedback_or_scoring=0,
        known_calibration_diagnostics_not_new_unseen_confirmation=True,
    ))


def run(v25=V25, output=OUTPUT):
    v25, output = Path(v25).resolve(), Path(output).resolve()
    require(output != v25 and output.is_relative_to(v25), "diagnostics need an independent V25 child")
    publish(output / "registration", dict(
        schema="v54_bounded_historical_diagnostics_registration.v1", source=str(v25),
        selection_rule=SELECTION_RULE, models=9, scored_episodes=10323, outers=24,
        CPU_only=True, GPU_backward=False, new_feedback=0, scoring_calls=0,
        source_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        sigmoid_saturation_cutoff=math.log(99),
    ))
    invalid = invalid_diagnostics(v25, output)
    print(json.dumps({"stage":"invalid_complete", "invalid":invalid["invalid_count"],
                      "parser_disagreements":invalid["parser_disagreement_count"]}), flush=True)
    outers = old_outer_diagnostics(v25, output)
    print(json.dumps({"stage":"outer_complete", "outers":outers["observed_outer_count"]}), flush=True)
    mechanisms = existing_mechanisms(v25.parent, output)
    return publish(output / "summary", dict(
        schema="v54_bounded_historical_diagnostics_complete.v1", invalid_summary_id=invalid["id"],
        outer_summary_id=outers["id"], mechanisms_summary_id=mechanisms["id"],
        original_scores_and_records_unchanged=True, new_GPU_or_provider_calls=0,
        manual_reading_pending=True,
        gaps=["No per-draw saved C/gJ inspected; direction agreement NA without added backward.",
              "No token-segment coefficient attribution in committed outer records.",
              "No per-segment NLL/gradient attribution; probability mass is not actual loss/gradient."],
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=V25)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    result = run(arguments.source, arguments.output)
    print(json.dumps({"output":str(arguments.output), "id":result["id"]}), flush=True)
