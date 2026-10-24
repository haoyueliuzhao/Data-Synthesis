"""Saved-output explanation only: no scoring, model forward or old artifact writes.

The existing V54 parser-return labeling method is applied to the same frozen
native parser. Terminal outcome and the earliest observed failure stay separate;
an earlier recoverable tool error is never promoted to a terminal cause.
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import textwrap

import finqa_v71_binding as binding

require = binding.require
PARSER_BRANCHES = (
    "A_no_opening_envelope", "B_malformed_tag_in_prose_prefix",
    "C_non_envelope_between_or_after_envelopes", "D_invalid_call_object_schema",
    "E_missing_closing_envelope", "F_strict_JSON_or_argument_extraction_exception",
    "G_accepted_tool_envelopes",
)
CATEGORIES = ("invalid_envelope_or_arguments", "missing_terminal_submission",
              "program_nonexecutable", "tool_execution_failure",
              "truncation_or_interaction_budget", "undetermined")
_PARSER = None


def policy():
    return dict(schema="v71_saved_native_failure_explanation_policy.v1",
        native_scores_changed=False, private_reference_read=False, new_forward_or_backward=False,
        categories=list(CATEGORIES), terminal_and_first_failure_separate=True,
        parser_method="V54 AST labels on original parser tuple returns; predicates unchanged",
        terminal_priority=["native_nonexecutable", "explicit_budget_or_length_without_EOS",
                           "invalid_envelope_or_argument", "last_failed_tool", "missing_submission", "undetermined"],
        earliest_order="turn order; parser/one-call contract, then executed tool events, then length boundary",
        no_opening_envelope="missing_terminal_submission; not assumed malformed JSON",
        episode_final_score_never_changed=True,
        example_rule=dict(transitions=["R->I", "W->I", "I->I", "R->R"],
                          per_transition=6, order="ascending full task_key", maximum_pairs=24,
                          selection_before_raw_reading=True, population_rate_estimate=False),
        Full_and_Fixed894_same_rule=True, causal_claim=False)


def _parser():
    global _PARSER
    if _PARSER is not None:
        return _PARSER
    binding.install_scientific_paths()
    module = importlib.import_module("trusted_synthesis.finance_research.qwen_protocol")
    original = module.parse_qwen_native_response
    source = textwrap.dedent(inspect.getsource(original))
    tree = ast.parse(source)
    returns = sorted((node for node in ast.walk(tree) if isinstance(node, ast.Return)
                      and isinstance(node.value, ast.Tuple)), key=lambda node: node.lineno)
    require(len(returns) == len(PARSER_BRANCHES), "frozen native parser return structure changed")
    for node, label in zip(returns, PARSER_BRANCHES, strict=True):
        node.value = ast.Tuple(elts=[ast.Constant(label), node.value], ctx=ast.Load())
    ast.fix_missing_locations(tree)
    namespace = dict(original.__globals__)
    exec(compile(tree, __file__ + "::label_original_parser_returns", "exec"), namespace)
    _PARSER = namespace[original.__name__]
    return _PARSER


def classify_response(raw, prefix):
    label, (_, calls) = _parser()(raw, call_prefix=prefix)
    return label, [call.model_dump(mode="json") for call in calls]


def native_state(row):
    # Read the already accepted scorer's classification, never execute a program.
    value = row["native"]
    if value["status"] == "unknown":
        return "UNKNOWN"
    if value["status"] == "invalid_prediction":
        require(value["program_executable"] is False, "invalid native row is contradictory")
        return "I"
    require(value["status"] == "scored" and value["program_executable"] is True,
            "unrecognized saved native outcome")
    execution = value["native"]["execution_accuracy"]
    require(execution in (0, 1), "saved native execution must be binary")
    return "R" if execution == 1 else "W"


def _tool_failure(event):
    output = event.get("raw_output") or {}
    message = str(output.get("message", ""))
    if message in ("invalid linear FinQA program syntax",
                    "FinQA program did not execute to a finite number or yes/no"):
        category = "program_nonexecutable"
    elif output.get("error") in ("ToolInputError", "ValidationError", "JSONDecodeError"):
        category = "invalid_envelope_or_arguments"
    else:
        category = "tool_execution_failure"
    return dict(category=category, tool_name=event.get("name"), call_id=event.get("call_id"),
                recorded_error=output)


def inspect_episode(row, episode, *, parse=classify_response):
    task = row.get("original_task_key", row["task_key"].split("/", 1)[1])
    require(f"{episode['dataset']}/{episode['task_id']}" == task,
            "saved episode and score task changed")
    require(episode["stop_reason"] == row["stop_reason"]
            and episode["actual_model_calls"] == row["actual_model_calls"]
            and episode.get("all_provider_calls_settled") is True,
            "episode termination or settled-return binding changed")
    events_by_call = defaultdict(list)
    for index, event in enumerate(episode["tool_events"]):
        events_by_call[event["call_id"]].append((index, event))
    turns, failures, observed_events = [], [], set()
    for ordinal, turn in enumerate(episode["turns"]):
        receipt = turn.get("receipt")
        require(isinstance(receipt, dict), "saved native turn has no original receipt")
        require(hashlib.sha256(turn["raw_text"].encode()).hexdigest() == receipt["raw_response_sha256"],
                "raw response no longer matches receipt")
        label, parsed = parse(turn["raw_text"], receipt["call_id"])
        require(parsed == turn["tool_calls"], "explanation parser disagrees with saved native parser")
        info = dict(turn_index=ordinal, parser_category=label, tool_call_count=len(parsed),
                    generated_tokens=len(receipt["raw_generated_token_ids"]),
                    raw_response_sha256=receipt["raw_response_sha256"],
                    finish_reason=receipt["finish_reason"], actual_EOS=receipt["actual_eos"])
        turns.append(info)
        if label != "G_accepted_tool_envelopes":
            failures.append(dict(turn_index=ordinal, event="native_parser_or_missing_envelope",
                category="missing_terminal_submission" if label == PARSER_BRANCHES[0]
                else "invalid_envelope_or_arguments", parser_category=label))
        elif len(parsed) != 1:
            failures.append(dict(turn_index=ordinal, event="one_tool_call_contract",
                category="invalid_envelope_or_arguments", actual_call_count=len(parsed)))
        for call in parsed:
            for event_index, event in events_by_call[call["call_id"]]:
                observed_events.add(event_index)
                if event["is_error"]:
                    failures.append(dict(turn_index=ordinal, event="tool_error", event_index=event_index,
                                         **_tool_failure(event)))
        if receipt["finish_reason"] == "length" and not receipt["actual_eos"]:
            failures.append(dict(turn_index=ordinal, event="model_generation_length_limit",
                                 category="truncation_or_interaction_budget"))
    require(observed_events == set(range(len(episode["tool_events"]))),
            "saved tool event has no matching original model call")
    if episode["stop_reason"] in ("max_steps", "context_exceeded"):
        failures.append(dict(turn_index=len(turns), event=episode["stop_reason"],
                             category="truncation_or_interaction_budget"))
    state, terminal = native_state(row), "not_invalid"
    last = turns[-1] if turns else {}
    last_failures = [event for event in failures if event["turn_index"] == len(turns) - 1]
    if state == "I":
        if row["native"].get("reason") == "nonexecutable_submission":
            terminal = "program_nonexecutable"
        elif episode["stop_reason"] in ("max_steps", "context_exceeded") or (
                last.get("finish_reason") == "length" and last.get("actual_EOS") is False):
            terminal = "truncation_or_interaction_budget"
        elif any(event["category"] == "invalid_envelope_or_arguments" for event in last_failures):
            terminal = "invalid_envelope_or_arguments"
        elif last_failures and last_failures[-1]["event"] == "tool_error":
            terminal = last_failures[-1]["category"]
        elif row["native"].get("reason") == "missing_or_invalid_submission":
            terminal = "missing_terminal_submission"
        else:
            terminal = "undetermined"
    return dict(task_key=row["task_key"], native_state=state, native_reason=row["native"].get("reason"),
        stop_reason=episode["stop_reason"], actual_model_calls=episode["actual_model_calls"],
        terminal_category=terminal, terminal_turn=last, first_failure_event=failures[0] if failures else None,
        all_observed_failures=failures, turns=turns,
        earlier_failure_does_not_imply_terminal_cause=True)


def select_pairs(baseline_rows, full_rows):
    require([row["task_key"] for row in baseline_rows] == [row["task_key"] for row in full_rows],
            "mechanism paired task order differs")
    grouped = defaultdict(list)
    for baseline, full in zip(baseline_rows, full_rows, strict=True):
        grouped[f"{native_state(baseline)}->{native_state(full)}"].append(full["task_key"])
    return [dict(transition=transition, task_key=task) for transition in policy()["example_rule"]["transitions"]
            for task in sorted(grouped[transition])[:6]]


def _read_plain(reference):
    raw = Path(reference["path"]).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == reference["sha256"], "saved source bytes changed")
    return json.loads(raw)


def _generation_index(generation, seal_reference, rows, canonical=None):
    generation = Path(generation).resolve()
    seal = _read_plain(seal_reference)
    run = json.loads((generation / "run.json").read_bytes())
    require(seal["complete"] and seal["all_provider_calls_settled"]
            and seal["run_id"] == run["id"]
            and run["episode_keys"] == [entry["key"] for entry in seal["episodes"]]
            and [f"draw20260928/{task}" for task in run["tasks"]] == [row["task_key"] for row in rows],
            "saved generation roster differs from accepted native scores")
    require(len(rows) == len(seal["episodes"]), "complete saved output denominator required")
    if canonical is not None:
        require(len(canonical) == len(rows), "canonical score-to-episode bindings incomplete")
    result = {}
    for ordinal, (row, entry) in enumerate(zip(rows, seal["episodes"], strict=True)):
        path = (generation / entry["path"]).resolve()
        require(path.is_relative_to(generation), "saved episode path escaped generation")
        result[row["task_key"]] = dict(path=str(path), sha256=entry["sha256"],
            canonical_sha256=None if canonical is None else canonical[ordinal])
    return result


def _load_episode(reference):
    episode = _read_plain(reference)
    if reference.get("canonical_sha256") is not None:
        require(binding.digest(episode) == reference["canonical_sha256"], "score-to-episode canonical identity changed")
    return episode


def _baseline_index(report):
    require(len(report["job_score_refs"]) == 1, "single greedy baseline job required")
    scored = binding.read_ref(next(iter(report["job_score_refs"].values())))
    proof = scored["source_job_proof"]
    require(scored["results"] == report["results"], "baseline panel and job scores differ")
    return _generation_index(proof["generation_root"], proof["source_refs"]["native_seal"],
                             report["results"], proof["canonical_episode_sha256"])


def _endpoint_index(root, job_id, report):
    directory = Path(root) / "evaluations/jobs" / job_id
    whole = binding.checked(directory / "whole_queue_seal/record.json")
    require(whole["generation_seal_id"] == report["generation_seal_id"], "native score seal differs")
    generation = directory / "shards" / job_id / "generation"
    return _generation_index(generation, whole["generation_seal"], report["results"], whole["episode_sha256"])


def _aggregate(rows):
    invalid = [row for row in rows if row["native_state"] == "I"]
    return dict(invalid_count=len(invalid),
        terminal_counts=dict(Counter(row["terminal_category"] for row in invalid)),
        first_failure_counts=dict(Counter((row["first_failure_event"] or {}).get("category", "none_observed")
                                         for row in invalid)),
        source_transition_counts=dict(Counter(row.get("from_baseline", "unbound") + "->I" for row in invalid)),
        terminal_by_source={source: dict(Counter(row["terminal_category"] for row in invalid
                                               if row.get("from_baseline") == source)) for source in ("I", "W", "R")})


def _stop(root, guard):
    require(not (Path(root) / "STOP").exists()
            and not (Path(root) / "control/stop_requested/record.json").exists(), "explicit STOP before mechanism analysis")
    if guard is not None:
        guard.check("before_saved_episode_analysis", boundary=True)


def existing(root, guard=None):
    """May run beside new training; reads old scores/episodes only."""
    root = Path(root)
    require(root.resolve() == binding.ROOT.resolve(), "foreign V71 mechanism output root")
    output = root / "mechanism_analysis/existing_invalid/record.json"
    if output.exists():
        saved = binding.checked(output)
        require(saved["policy"] == policy(), "saved explanation rule changed")
        return saved
    old_root = binding.V70_ROOT
    protocol = binding.checked(old_root / "protocol/record.json")
    baseline_ref = protocol["baseline_evaluation"]["model_reports"]["development"]
    full_ref = binding.entry(old_root / "evaluations/jobs/step1490.dev_greedy/native_scores/record.json")
    baseline, full = binding.read_ref(baseline_ref), binding.read_ref(full_ref)
    require(baseline["denominator"] == full["denominator"] == 883
            and full["status"] == "COMPLETE" and full["metrics"]["states"]["I"] == 325,
            "expected complete V70 development comparator")
    selected = select_pairs(baseline["results"], full["results"])
    require(len(selected) == 24, "fixed four-by-six saved-output sample unavailable")
    selection = binding.publish(root / "mechanism_analysis/example_selection/record.json",
        dict(schema="v71_predeclared_saved_output_pairs.v1", policy=policy()["example_rule"],
             baseline=baseline_ref, Full=full_ref, selected=selected, count=24))
    full_index, baseline_index = _endpoint_index(old_root, "step1490.dev_greedy", full), _baseline_index(baseline)
    baseline_rows = {row["task_key"]: row for row in baseline["results"]}
    full_rows = {row["task_key"]: row for row in full["results"]}
    wanted = {row["task_key"] for row in full["results"] if native_state(row) == "I"}
    wanted.update(row["task_key"] for row in selected)
    inspected, raw_samples = {}, {}
    sample_tasks = {row["task_key"] for row in selected}
    for task in sorted(wanted):
        _stop(root, guard)
        episode = _load_episode(full_index[task])
        inspected[task] = dict(inspect_episode(full_rows[task], episode), episode=full_index[task],
                               from_baseline=native_state(baseline_rows[task]))
        if task in sample_tasks:
            raw_samples[task] = episode
    readings = []
    for item in selected:
        task = item["task_key"]
        _stop(root, guard)
        before, after = _load_episode(baseline_index[task]), raw_samples[task]
        readings.append(dict(**item,
            baseline=dict(analysis=inspect_episode(baseline_rows[task], before), episode=baseline_index[task],
                          raw_turns=[turn["raw_text"] for turn in before["turns"]], tool_events=before["tool_events"]),
            Full=dict(analysis=inspected[task], episode=full_index[task],
                      raw_turns=[turn["raw_text"] for turn in after["turns"]], tool_events=after["tool_events"]),
            interpretive_scope="descriptive selected case, not population frequency or causal attribution"))
    packet = binding.publish(root / "mechanism_analysis/example_reading_packet/record.json",
        dict(schema="v71_fixed_24_pair_original_output_reading_packet.v1", selection_id=selection["id"],
             pairs=readings, count=24, raw_outputs_unchanged=True, no_repair_or_rescore=True))
    rows = [inspected[task] for task in sorted(inspected) if inspected[task]["native_state"] == "I"]
    summary = _aggregate(rows)
    require(summary["source_transition_counts"] == {"R->I": 179, "W->I": 81, "I->I": 65},
            "V70 invalid origin counts changed")
    return binding.publish(output, dict(schema="v71_existing_Full_invalid_explanation.v1", status="COMPLETE",
        policy=policy(), baseline=baseline_ref, Full=full_ref, rows=rows, **summary,
        example_selection=binding.entry(root / "mechanism_analysis/example_selection/record.json"),
        reading_packet=binding.entry(root / "mechanism_analysis/example_reading_packet/record.json"),
        reading_packet_id=packet["id"], new_scoring_calls=0, new_model_calls=0,
        old_artifacts_modified=False, first_failure_is_not_cause_proof=True))


run_existing = existing


def finish(root, model_reports, guard=None):
    root = Path(root)
    output = root / "mechanism_analysis/paired_invalid/record.json"
    if output.exists():
        saved = binding.checked(output)
        require(saved["policy"] == policy() and saved["Fixed894"] == model_reports["step1490.dev_greedy"],
                "saved fixed-output explanation binding changed")
        return saved
    previous = existing(root, guard)
    protocol = binding.checked(root / "protocol/record.json")
    require(previous["baseline"] == protocol["baseline_evaluation"]["model_reports"]["development"]
            and previous["Full"] == protocol["full_evaluation"]["model_reports"]["step1490.dev_greedy"],
            "mechanism report differs from the registered paired comparator")
    observations_path = root / "mechanism_analysis/example_reading_observations/record.json"
    observations = binding.checked(observations_path)
    require(observations["reading_packet"] == previous["reading_packet"]
            and observations["example_selection"] == previous["example_selection"],
            "qualitative reading observations need the preselected original 24 pairs")
    fixed_ref = model_reports["step1490.dev_greedy"]
    fixed, full, baseline = (binding.read_ref(ref) for ref in
                            (fixed_ref, previous["Full"], previous["baseline"]))
    require([row["task_key"] for row in fixed["results"]] == [row["task_key"] for row in full["results"]],
            "fixed and Full native outputs are not the same ordered panel")
    index = _endpoint_index(root, "step1490.dev_greedy", fixed)
    baseline_rows = {row["task_key"]: row for row in baseline["results"]}
    rows = []
    for row in fixed["results"]:
        if native_state(row) != "I":
            continue
        _stop(root, guard)
        task = row["task_key"]
        rows.append(dict(inspect_episode(row, _load_episode(index[task])), episode=index[task],
                         from_baseline=native_state(baseline_rows[task])))
    left, right = {row["task_key"]: row for row in previous["rows"]}, {row["task_key"]: row for row in rows}
    shared = sorted(set(left) & set(right))
    return binding.publish(output, dict(schema="v71_Full_fixed_invalid_comparison.v1", status="COMPLETE",
        policy=policy(), existing_Full=binding.entry(root / "mechanism_analysis/existing_invalid/record.json"),
        example_reading_observations=binding.entry(observations_path),
        Fixed894=fixed_ref, fixed_rows=rows, fixed_summary=_aggregate(rows),
        Full_summary={key: previous[key] for key in _aggregate([])},
        invalid_overlap=dict(both=len(shared), Full_only=len(set(left) - set(right)),
                             Fixed894_only=len(set(right) - set(left)), both_task_keys=shared,
                             same_terminal_category=sum(left[key]["terminal_category"] == right[key]["terminal_category"] for key in shared),
                             terminal_category_pairs=dict(Counter(left[key]["terminal_category"] + "->" +
                                right[key]["terminal_category"] for key in shared))),
        new_scoring_calls=0, new_model_calls=0, native_scores_unchanged=True,
        same_failure_in_fixed_not_unique_to_Full=True, subtype_causality_identified=False))
