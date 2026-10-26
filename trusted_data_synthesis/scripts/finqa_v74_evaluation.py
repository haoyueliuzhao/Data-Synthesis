"""One all-exits-gated native evaluation of the 192 mixed-source V74 paths.

The native tool's submit_program records a prediction without executing it.
Executability, EA and PA are assessed here with the original pinned scorer,
only after every condition has a terminal record and the worker actually exits.
No model, API, training, or old-score recomputation is performed in this module.
"""
from __future__ import annotations

from collections import Counter
import importlib
from pathlib import Path

DIRECTIONS = ("L_from_P", "P_from_L")
GROUPS = ("F", "K")
CATEGORIES = ("compliant_submit_candidate", "compliant_nonterminal_candidate", "plain_no_tool_call")
EXPECTED = {("L_from_P", "F"): (45, 0, 3), ("L_from_P", "K"): (48, 0, 0),
            ("P_from_L", "F"): (12, 26, 10), ("P_from_L", "K"): (42, 5, 1)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _binding():
    return importlib.import_module("finqa_v74_binding")


def _original():
    return _binding().source_module("finqa_v63_evaluation")


def evaluation_contract():
    return dict(schema="v74_hybrid_native_evaluation_contract.v1", distinct_tasks=96,
        conditional_trajectories=192, groups={"F": 48, "K": 48}, directions=list(DIRECTIONS),
        reused_first_responses=192, first_response_submit=147,
        first_response_nonterminal=31, first_response_no_call=14,
        new_first_response_generations=0, maximum_new_model_calls_conservative=961,
        exact_new_model_call_limit_source="frozen inputs, sum max(0,32-b-1) over 31 nonterminal conditions",
        new_native_logical_scores=192, before_private_scoring="all192 terminal records and accepted actual worker exit0",
        homogeneous_model_trajectory=False, old_scores_rescored=False, old_L_dev431_of883_changed=False,
        UNKNOWN_as_zero=False, full_denominators=True, native_scorer_unchanged=True,
        native_submit_program_executes_prediction=False,
        prediction_executability_assessed_by_original_offline_native_scorer=True,
        hypothesis="conditional continuation on explicitly identified foreign-model history",
        overall_dev_accuracy_or_causal_fraction=False, corrective_witness_training_effect_proved=False,
        development_conditions_enter_training=False, automatic_training_gate=False,
        automatic_Full_resume=False, automatic_followup=False,
        new_NLL=0, new_backpropagation=0, new_optimizer=0, new_outer=0, new_class=0, new_VJP=0, external_API=0)


def validate_panel(bundle):
    tasks, conditions = bundle["tasks"], bundle["conditions"]
    require(len(tasks) == 96 and len({t["task_key"] for t in tasks}) == 96,
            "V74 requires exactly the fixed96 distinct tasks")
    require(Counter(t["group"] for t in tasks) == {"F": 48, "K": 48}, "fixed F/K48 groups changed")
    task_map = {t["task_key"]: t for t in tasks}
    require(len(conditions) == 192 and len({c["condition_id"] for c in conditions}) == 192,
            "V74 requires exactly192 unique conditional trajectories")
    require({(c["direction"], c["task_key"]) for c in conditions}
            == {(d, key) for d in DIRECTIONS for key in task_map}, "cross-direction task coverage changed")
    for c in conditions:
        require(c["group"] == task_map[c["task_key"]]["group"]
                and c["first_action_category"] in CATEGORIES, "condition group or first action changed")
    for key, counts in EXPECTED.items():
        rows = [c for c in conditions if (c["direction"], c["group"]) == key]
        require(tuple(sum(c["first_action_category"] == name for c in rows) for name in CATEGORIES) == counts,
                "V73 reused first-action counts changed")
    return conditions


def _state(row, stats):
    return stats.native_state(row)


def _metrics(rows, stats):
    if not rows:
        return dict(denominator=0, status="NA_EMPTY_PREDECLARED_SUBGROUP", execution_accuracy=None,
                    program_accuracy=None, states={s: 0 for s in ("I", "W", "R", "UNKNOWN")})
    return stats.native_metrics(rows, len(rows))


def _costs(rows):
    names = ("new_model_calls", "new_tool_calls", "reconstruction_tool_calls", "reused_first_response_tool_calls")
    sums = {name: sum(row[name] for row in rows) for name in names}
    return dict(**sums, reused_first_responses=len(rows),
        historical_model_calls_in_prefix=sum(row["source_model_calls_before_first"] for row in rows),
        inherited_model_calls_not_new_compute=True,
        total_path_model_calls_including_prefix_and_reused=sum(row["actual_path_model_calls"] for row in rows),
        budget_exhausted=sum(row["budget_exhausted"] for row in rows),
        context_exceeded=sum(row["stop_reason"] == "context_exceeded" for row in rows),
        unknown_new_calls=sum(row.get("unknown_new_calls", 0) for row in rows))


def _subgroup(rows, stats):
    states = Counter(_state(row, stats) for row in rows)
    return dict(denominator=len(rows), metrics=_metrics(rows, stats),
        states={name: states[name] for name in ("I", "W", "R", "UNKNOWN")},
        correct_terminal_results=states["R"], known_not_correct_terminal_results=states["I"] + states["W"],
        unknown_results=states["UNKNOWN"], stop_reasons=dict(sorted(Counter(row["stop_reason"] for row in rows).items())),
        costs=_costs(rows),
        valid_terminal_submit_count=sum(row["valid_terminal_submit"] for row in rows),
        native_invalid_reasons=dict(sorted(Counter(row["native"].get("reason", "unspecified") for row in rows
            if row["native"]["status"] == "invalid_prediction").items())))


def _paired(candidate, reference, stats):
    require([r["task_key"] for r in candidate] == [r["task_key"] for r in reference],
            "paired old score task order differs")
    value = stats.paired_transitions(candidate, reference, len(candidate))
    transitions = value["transitions"]
    value.update(orientation="old original trajectory -> mixed continuation; mixed minus old",
        new_correct_known_pairs=transitions["I->R"] + transitions["W->R"],
        lost_correct_known_pairs=transitions["R->I"] + transitions["R->W"],
        conditional_selected_panel_only=True, overall_development_effect=False)
    p_pairs = [(old["native"]["native"]["program_accuracy"], new["native"]["native"]["program_accuracy"])
               for old, new in zip(reference, candidate, strict=True)]
    known = [(old, new) for old, new in p_pairs if old is not None and new is not None]
    gain = sum(old == 0 and new == 1 for old, new in known)
    loss = sum(old == 1 and new == 0 for old, new in known)
    value["program_accuracy"] = dict(denominator=len(p_pairs), unknown_pairs=len(p_pairs)-len(known),
        new_correct_known_pairs=gain, lost_correct_known_pairs=loss,
        complete_panel_net=gain-loss if len(known) == len(p_pairs) else None,
        complete_panel_difference=(gain-loss)/len(p_pairs) if len(known) == len(p_pairs) else None)
    return value


def summarize(bundle, rows, old_scores, *, stats=None):
    """Pure description; UNKNOWN remains in the complete preselected denominator."""
    conditions = validate_panel(bundle)
    stats = _original().stats if stats is None else stats
    require(len(rows) == 192 and [r["condition_id"] for r in rows] == [c["condition_id"] for c in conditions],
            "native result roster or registered ordering changed")
    old_by_model = {name: {r["task_key"]: r for r in old_scores[name]["results"]} for name in ("P", "L")}
    panels = {}
    for group in GROUPS:
        panels[group] = {}
        for direction in DIRECTIONS:
            selected = [r for r in rows if r["group"] == group and r["direction"] == direction]
            require(len(selected) == 48, "each conditional panel retains denominator48")
            candidate_rows = [r for r in selected if r["first_action_category"] == CATEGORIES[0]]
            candidate_states = Counter(_state(r, stats) for r in candidate_rows)
            report = _subgroup(selected, stats)
            report["by_first_response"] = {category: _subgroup(
                [r for r in selected if r["first_action_category"] == category], stats) for category in CATEGORIES}
            report["original_submit_candidates"] = dict(denominator=len(candidate_rows),
                native_nonexecutable=sum(r["native"].get("reason") == "nonexecutable_submission" for r in candidate_rows),
                native_missing_or_invalid_submission=sum(r["native"].get("reason") == "missing_or_invalid_submission" for r in candidate_rows),
                executable_wrong=candidate_states["W"], executable_correct=candidate_states["R"],
                unknown=candidate_states["UNKNOWN"],
                static_legality_is_not_native_correctness=True)
            report["paired_to_old_original"] = {name: _paired(selected,
                [old_by_model[name][r["task_key"]] for r in selected], stats) for name in ("P", "L")}
            report["old_original_metrics"] = {name: _metrics(
                [old_by_model[name][r["task_key"]] for r in selected], stats) for name in ("P", "L")}
            panels[group][direction] = report
    unknown = sum(_state(row, stats) == "UNKNOWN" for row in rows)
    return dict(schema="v74_conditional_complete_trajectory_summary.v1",
        status="COMPLETE_WITH_UNKNOWN" if unknown else "COMPLETE", distinct_tasks=96,
        conditional_trajectory_denominator=192, logical_native_scores=192, unknown_native_results=unknown,
        panels=panels, costs=_costs(rows), results=rows,
        context_structure=bundle.get("context_structure"),
        old_scores_rescored=False, old_L_dev431_of883_changed=False, full_denominators=True,
        UNKNOWN_as_zero=False, mixed_source_trajectories=True, parent_future_answer_injected=False,
        original_first_responses_regenerated=False, homogeneous_model_trajectory=False,
        overall_dev_accuracy_estimated=False, history_causal_share_identified=False,
        corrective_witnesses_are_training_effect_proof=False, development_conditions_enter_training=False,
        automatic_training_gate=False, automatic_Full_resume=False, automatic_followup=False,
        native_submit_program_records_without_execution=True,
        program_executability_first_assessed_by_native_offline_scorer=True,
        new_NLL=0, new_backpropagation=0, new_optimizer=0, new_outer=0, new_class=0, new_VJP=0, external_API=0)


def _runtime():
    binding = _binding()
    binding.install_scientific_paths()
    binding.install_registered_auxiliary()
    original = _original()
    final = original._runtime()
    contracts = importlib.import_module("trusted_synthesis.finance_research.contracts")
    return original, final, contracts


def _load_bundles(bundle, final, original):
    plan = bundle["generation_registrations"]["P"]
    other = bundle["generation_registrations"]["L"]
    require(plan["snapshot"] == other["snapshot"] and plan["snapshot_id"] == other["snapshot_id"],
            "source P/L public snapshots differ")
    manifest, public, lineages = final.load_public_snapshot(plan["snapshot"])
    require(manifest["id"] == plan["snapshot_id"], "frozen public scoring snapshot changed")
    wanted = {c["original_task_key"] for c in bundle["conditions"]}
    require(len(wanted) == 96, "private scorer must open only fixed96 task references")
    return original._panel_private_bundles(final, plan, manifest, public, lineages, wanted)


def _validated_terminal_rows(protocol, bundle, outcomes):
    conditions = validate_panel(bundle)
    require(set(outcomes) == {c["condition_id"] for c in conditions}, "all192 terminal outcomes required before private scoring")
    for condition in conditions:
        outcome = outcomes[condition["condition_id"]]
        require(outcome["status"] == "COMPLETE" and outcome["protocol_id"] == protocol["id"]
                and outcome["inputs_id"] == bundle["id"] and outcome["condition_id"] == condition["condition_id"],
                "conditional terminal protocol or input binding changed")
        require(outcome["episode"]["all_provider_calls_settled"] is True,
                "unsettled conditional path cannot enter scoring")
    return conditions


def _check_stop(root):
    require(not (Path(root)/"STOP").exists() and not (Path(root)/"control/stop_requested/record.json").exists(),
            "explicit STOP forbids continuing native evaluation")


def _row(condition, outcome, native):
    episode = outcome["episode"]
    events = episode["tool_events"]
    valid_terminal_submit = bool(episode["stop_reason"] == "final_answer" and events
        and events[-1]["name"] == "submit_program" and not events[-1]["is_error"]
        and events[-1]["raw_output"].get("program") == episode["final_program"])
    names = ("new_model_calls", "new_tool_calls", "reconstruction_tool_calls", "reused_first_response_tool_calls")
    costs = {name: outcome[name] for name in names}
    require(all(type(v) is int and v >= 0 for v in costs.values()), "actual costs must be known nonnegative counts")
    before = condition["source_turn_index"]
    require(episode["actual_model_calls"] == before + 1 + costs["new_model_calls"],
            "path calls must include unchanged prefix and reused first response")
    require(costs["new_model_calls"] <= condition["remaining_model_calls"], "frozen residual model-call budget exceeded")
    require(condition["first_action_category"] == CATEGORIES[1] or costs["new_model_calls"] == 0,
            "direct submit and no-call conditions cannot receive new model calls")
    return dict(condition_id=condition["condition_id"], task_key=condition["task_key"],
        original_task_key=condition["original_task_key"], group=condition["group"],
        direction=condition["direction"], source_group=condition["source_group"],
        first_action_category=condition["first_action_category"], native=native,
        stop_reason=episode["stop_reason"], valid_terminal_submit=valid_terminal_submit,
        source_model_calls_before_first=before, actual_path_model_calls=episode["actual_model_calls"],
        **costs, budget_exhausted=outcome["budget_exhausted"], unknown_new_calls=0,
        maximum_new_model_calls=condition["remaining_model_calls"],
        program_executable=native["program_executable"], mixed_source_trajectory=True)


def evaluate(protocol, bundle, outcomes, *, all_jobs_exit_barrier, root=None, guard=None):
    """Caller verifies bound real exits; this function checks full coverage first.

    Durable row publication ensures a settled native score is never recomputed on
    a later CPU resumption. No private reference is opened before the full-roster
    terminal and explicit all-exits checks. Root owns final-summary publication.
    """
    binding = _binding()
    root = binding.ROOT if root is None else Path(root)
    require(Path(root).resolve() == binding.ROOT.resolve(), "scoring escaped independent V74 root")
    require(isinstance(all_jobs_exit_barrier, dict) and all_jobs_exit_barrier.get("path")
            and all_jobs_exit_barrier.get("sha256"), "bound all-jobs actual-exit barrier required")
    barrier = binding.read_ref(all_jobs_exit_barrier)
    require(barrier["protocol_id"] == protocol["id"] and barrier.get("active_workers") == []
            and set(barrier.get("accepted_jobs", {})) == {"P.continuation"},
            "single continuation worker must be accepted and actually exited before scoring")
    conditions = _validated_terminal_rows(protocol, bundle, outcomes)
    _check_stop(root)
    original, final, contracts = _runtime()
    # Episode parsing and native completeness never rewrite original receipt IDs.
    settlement = importlib.import_module("trusted_synthesis.finance_research.settlement")
    episodes = {c["condition_id"]: contracts.Episode.model_validate(outcomes[c["condition_id"]]["episode"])
                for c in conditions}
    require(all(settlement.episode_is_complete(e) for e in episodes.values()),
            "all192 native settled terminal episodes required before reference access")
    bundles = None  # Open private rows only when a not-yet-scored condition actually needs them.
    old = {name: binding.read_ref(bundle["old_scores"][name]) for name in ("P", "L")}
    rows, refs = [], {}
    for condition in conditions:
        _check_stop(root)
        if guard is not None:
            guard() if callable(guard) else guard.check("before_v74_native_score", boundary=True)
        key = condition["condition_id"]
        path = root/"evaluations/native_rows"/key/"record.json"
        episode_hash = binding.digest(outcomes[key]["episode"])
        if path.exists():
            saved = binding.checked(path)
            require(saved["protocol_id"] == protocol["id"] and saved["inputs_id"] == bundle["id"]
                    and saved["condition_id"] == key and saved["episode_sha256"] == episode_hash
                    and saved["all_jobs_exit_barrier"] == all_jobs_exit_barrier,
                    "durable native score binding changed; never rescore")
            row = saved["row"]
        else:
            if bundles is None:
                bundles = _load_bundles(bundle, final, original)
            native = final.score_public_reasoning_program(bundles[condition["original_task_key"]], episodes[key])
            row = _row(condition, outcomes[key], native)
            binding.publish(path, dict(schema="v74_durable_hybrid_native_score.v1", protocol_id=protocol["id"],
                inputs_id=bundle["id"], condition_id=key, episode_sha256=episode_hash,
                all_jobs_exit_barrier=all_jobs_exit_barrier, row=row))
        rows.append(row)
        refs[key] = binding.entry(path)
    summary = summarize(bundle, rows, old, stats=original.stats)
    summary.update(protocol_id=protocol["id"], inputs_id=bundle["id"],
        all_jobs_exit_barrier=all_jobs_exit_barrier, native_score_rows=refs, old_score_references=bundle["old_scores"],
        evaluation_contract=evaluation_contract())
    return summary
