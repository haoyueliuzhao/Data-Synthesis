"""Same frozen native explanation rules for parent, high-LR and low-LR dev.

Old high-LR labels are inherited read-only. New parent/low-LR raw episodes are
classified only after their native scores are sealed; no answer is repaired,
program rescored, training target edited, or extra qualitative sample selected.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import finqa_v72_binding as binding

require = binding.require


def _original():
    return binding.source_v71("finqa_v71_failure_analysis")


def policy():
    inherited = dict(_original().policy())
    inherited.pop("example_rule")
    inherited.pop("Full_and_Fixed894_same_rule")
    inherited.pop("schema")
    return dict(schema="v72_same_native_terminal_and_first_failure_policy.v1",
        inherited_V71_classification_rules=inherited,
        original_parent_high_lr_low_lr_same_rule=True,
        high_lr1490_labels_reused_without_reopening_old_episodes=True,
        new_qualitative_pairs_selected=0,
        report_parent1192_R_to_I_and_missing_valid_terminal_submission=True,
        episode_final_score_never_changed=True,new_model_calls=0,new_scoring_calls=0)


def native_state(row):
    return _original().native_state(row)


def inspect_episode(row, episode, **kwargs):
    return _original().inspect_episode(row, episode, **kwargs)


def _stop(root, guard):
    require(not (Path(root) / "STOP").exists()
            and not (Path(root) / "control/stop_requested/record.json").exists(),
            "explicit STOP before native failure explanation")
    if guard is not None:
        guard.check("before_saved_episode_failure_analysis", boundary=True)


def summarize_invalid(rows, *, source_field):
    require(all(row["native_state"] == "I" for row in rows), "only saved invalid rows belong in this table")
    by_source = {source:dict(Counter(row["terminal_category"] for row in rows
        if row[source_field] == source)) for source in ("I","W","R")}
    r_to_i = [row for row in rows if row[source_field] == "R"]
    return dict(invalid_count=len(rows),source_state_field=source_field,
        terminal_counts=dict(Counter(row["terminal_category"] for row in rows)),
        first_failure_counts=dict(Counter((row["first_failure_event"] or {}).get("category","none_observed")
                                          for row in rows)),
        source_transition_counts=dict(Counter(row[source_field]+"->I" for row in rows)),
        terminal_by_source=by_source,R_to_I_count=len(r_to_i),
        R_to_I_missing_valid_submission=sum(row["terminal_category"] == "missing_terminal_submission"
                                           for row in r_to_i),
        unobserved_first_failure_is_not_UNKNOWN=True)


def _annotate(rows, source_rows, *, source_field):
    by_key = {row["task_key"]:row for row in source_rows}
    require(len(by_key) == len(source_rows), "duplicate source task in native scores")
    return [dict(row, **{source_field:native_state(by_key[row["task_key"]])}) for row in rows]


def _new_invalid(root, job_id, report, guard):
    original = _original()
    index = original._endpoint_index(root,job_id,report)
    rows = []
    for row in report["results"]:
        if native_state(row) != "I":
            continue
        _stop(root,guard)
        reference = index[row["task_key"]]
        rows.append(dict(inspect_episode(row,original._load_episode(reference)),episode=reference))
    require(len(rows) == report["metrics"]["states"]["I"], "incomplete native invalid classification")
    return rows


def invalid_overlap(left_rows, right_rows):
    left = {row["task_key"]:row for row in left_rows}
    right = {row["task_key"]:row for row in right_rows}
    require(len(left) == len(left_rows) and len(right) == len(right_rows), "duplicate invalid task")
    shared = sorted(set(left)&set(right))
    return dict(both=len(shared),HighLR_only=len(set(left)-set(right)),
        LowLR_only=len(set(right)-set(left)),both_task_keys=shared,
        same_terminal_category=sum(left[key]["terminal_category"] == right[key]["terminal_category"]
                                   for key in shared),
        terminal_category_pairs=dict(Counter(left[key]["terminal_category"]+"->"+
            right[key]["terminal_category"] for key in shared)),
        category_pair_orientation="HighLR1490 -> LowLR1490")


def validate_comparison_reports(parent, low, high, baseline):
    """V68 baseline panels have complete metrics but no top-level status field."""
    keys = [row["task_key"] for row in parent["results"]]
    require(len(keys) == 883 and len(set(keys)) == 883
            and all(report["status"] == "COMPLETE" for report in (parent,low,high))
            and baseline["coordinate"] == "seed137/C1" and baseline["feedback_batch"] == 1
            and all(report["denominator"] == 883 and report["metrics"]["states"]["UNKNOWN"] == 0
                    and [row["task_key"] for row in report["results"]] == keys
                    for report in (parent,low,high,baseline)),
            "complete development cohort order or baseline native metrics changed")
    return keys


def finish(root, model_reports, guard=None):
    root = Path(root)
    require(root.resolve() == binding.ROOT.resolve(), "foreign low-LR failure analysis root")
    _stop(root,guard)
    protocol = binding.checked(root / "protocol/record.json")
    require(protocol["failure_analysis_policy"] == policy(), "native explanation policy changed")
    output = root / "mechanism_analysis/paired_invalid/record.json"
    parent_ref,low_ref = model_reports["step1192.dev_greedy"],model_reports["step1490.dev_greedy"]
    high_ref = protocol["high_lr_evaluation"]["model_reports"]["step1490.dev_greedy"]
    inherited_ref = protocol["high_lr_evaluation"]["failure_analysis"]
    if output.exists():
        value = binding.checked(output)
        require(value["protocol_id"] == protocol["id"] and value["policy"] == policy()
                and value["parent1192"] == parent_ref and value["LowLR1490"] == low_ref
                and value["HighLR1490"] == high_ref and value["inherited_high_lr_classification"] == inherited_ref,
                "saved failure analysis state or comparator changed")
        return value
    parent,low,high = [binding.read_ref(ref) for ref in (parent_ref,low_ref,high_ref)]
    baseline_ref = protocol["baseline_evaluation"]["model_reports"]["development"]
    baseline = binding.read_ref(baseline_ref)
    validate_comparison_reports(parent,low,high,baseline)
    inherited = binding.read_ref(inherited_ref)
    require(inherited["Fixed894"] == high_ref
            and inherited["policy"] == _original().policy(), "inherited high-LR failure rules or scores changed")
    high_rows = inherited["fixed_rows"]
    require({row["task_key"] for row in high_rows} == {row["task_key"] for row in high["results"]
            if native_state(row) == "I"}, "inherited high-LR invalid labels incomplete")
    high_rows = _annotate(high_rows,parent["results"],source_field="from_parent1192")
    low_rows = _annotate(_new_invalid(root,"step1490.dev_greedy",low,guard),
                         parent["results"],source_field="from_parent1192")
    parent_rows = _annotate(_new_invalid(root,"step1192.dev_greedy",parent,guard),
                            baseline["results"],source_field="from_baseline894")
    return binding.publish(output,dict(schema="v72_parent_high_low_LR_invalid_comparison.v1",status="COMPLETE",
        protocol_id=protocol["id"],policy=policy(),parent1192=parent_ref,LowLR1490=low_ref,HighLR1490=high_ref,
        baseline894=baseline_ref,inherited_high_lr_classification=inherited_ref,
        parent_rows=parent_rows,low_lr_rows=low_rows,high_lr_rows=high_rows,
        parent_summary=summarize_invalid(parent_rows,source_field="from_baseline894"),
        low_lr_summary=summarize_invalid(low_rows,source_field="from_parent1192"),
        high_lr_summary=summarize_invalid(high_rows,source_field="from_parent1192"),
        endpoint_invalid_overlap=invalid_overlap(high_rows,low_rows),
        new_scoring_calls=0,new_model_calls=0,old_episodes_reopened_for_high_lr=False,
        native_scores_unchanged=True,first_failure_is_not_terminal_cause_proof=True,
        learning_rate_is_unique_internal_root_cause_identified=False))
