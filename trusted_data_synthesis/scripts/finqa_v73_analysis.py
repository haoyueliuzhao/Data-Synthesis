"""Pure JSON summaries for V73's conditional same-context mechanism panels.

Input rows remain 48 F + 48 K, even when a context or observation is unknown.
No native correctness score, model, tool execution or significance gate exists
in this module. Axes compare either model or history while fixing the other.
"""
from __future__ import annotations

from collections import Counter
import math
import statistics

from finqa_v73_measurement import ACTION_CATEGORIES, TOKEN_GROUPS, digest, require


MODELS = ("P", "H", "L")
PAIRS = (("P", "H"), ("P", "L"), ("H", "L"))


def _lookup(records, model, key):
    if key is None:
        return None
    if (model, key) in records:
        return records[(model, key)]
    if model in records and isinstance(records[model], dict):
        return records[model].get(key)
    return records.get(f"{model}:{key}")


def _action(record):
    if record is None or record.get("status") in ("UNKNOWN", "MISSING", "INCOMPLETE", "FAILED"):
        return None
    value = record.get("classification")
    require(isinstance(value, dict), "completed generation lacks saved classification")
    category = value.get("category")
    require(category in ACTION_CATEGORIES, "generation classification outside frozen categories")
    require(value.get("A") == int(category in ACTION_CATEGORIES[:2]), "A is not frozen static-action indicator")
    require(value.get("S") == int(category == ACTION_CATEGORIES[0]), "S is not frozen static-submit indicator")
    return value


def _rate(count, known, total):
    return dict(positive_count=count, known_count=known, unknown_count=total - known,
        denominator=total, complete_panel_rate=count / total if known == total else None,
        observed_subset_rate=count / known if known else None,
        observed_subset_is_explanatory_only=True)


def _cell(records):
    labels = [_action(record) for record in records]
    counts = Counter(label["category"] if label else "UNKNOWN" for label in labels)
    known = sum(label is not None for label in labels)
    return dict(denominator=len(records), known_count=known, unknown_count=len(records) - known,
        categories={name: counts[name] for name in (*ACTION_CATEGORIES, "UNKNOWN")},
        A=_rate(sum(label["A"] for label in labels if label), known, len(records)),
        S=_rate(sum(label["S"] for label in labels if label), known, len(records)),
        plain_no_tool_call=_rate(counts["plain_no_tool_call"], known, len(records)))


def _paired(reference, candidate):
    require(len(reference) == len(candidate), "paired panel denominator differs")
    pairs = list(zip(map(_action, reference), map(_action, candidate), strict=True))
    known = [(left, right) for left, right in pairs if left is not None and right is not None]
    categories = Counter((left["category"] if left else "UNKNOWN") + "->" +
        (right["category"] if right else "UNKNOWN") for left, right in pairs)
    out = dict(denominator=len(pairs), known_pair_count=len(known),
        unknown_pair_count=len(pairs) - len(known), orientation="reference -> candidate; candidate minus reference",
        category_transitions=dict(sorted(categories.items())))
    for metric in ("A", "S"):
        transitions = Counter(f"{left[metric]}->{right[metric]}" for left, right in known)
        gain, loss = transitions["0->1"], transitions["1->0"]
        out[metric] = dict(transitions={key: transitions[key] for key in ("0->0", "0->1", "1->0", "1->1")},
            gained=gain, lost=loss, net_known_pairs=gain - loss,
            complete_panel_net=gain - loss if len(known) == len(pairs) else None,
            complete_panel_difference=(gain - loss) / len(pairs) if len(known) == len(pairs) else None)
    return out


def _diagonal(tasks, source, logical, generation_results):
    rows = []
    for task in tasks:
        task_key = task["task_key"]
        context = logical.get((task_key, source), {})
        result = _lookup(generation_results, source, context.get("context_id"))
        label = _action(result)
        new_raw = result.get("raw_response_sha256", label.get("raw_response_sha256") if label else None) if result else None
        new_ids = result.get("response_token_ids_sha256") if result else None
        if new_ids is None and result and result.get("raw_generated_token_ids") is not None:
            new_ids = digest(result["raw_generated_token_ids"])
        old_raw, old_ids = context.get("old_response_sha256"), context.get("old_response_token_ids_sha256")
        rows.append(dict(task_key=task_key,
            raw_identical=None if label is None or not old_raw or not new_raw else old_raw == new_raw,
            token_ids_identical=None if label is None or not old_ids or not new_ids else old_ids == new_ids))
    return dict(denominator=len(tasks), rows=rows,
        raw_identical=sum(row["raw_identical"] is True for row in rows),
        raw_different=sum(row["raw_identical"] is False for row in rows),
        raw_unknown=sum(row["raw_identical"] is None for row in rows),
        token_ids_identical=sum(row["token_ids_identical"] is True for row in rows),
        token_ids_different=sum(row["token_ids_identical"] is False for row in rows),
        token_ids_unknown=sum(row["token_ids_identical"] is None for row in rows),
        historical_diagonal_is_selection_evidence_not_new_discovery=True,
        mismatch_is_reported_not_retried_or_selected_away=True,
        large_mismatch_threshold=None)


def _probability(record):
    if record is None or record.get("status") in ("UNKNOWN", "MISSING", "INCOMPLETE", "FAILED"):
        return None
    value = record.get("measurement")
    require(isinstance(value, dict), "completed probability sequence lacks grouped measurement")
    require(set(value["groups"]) == set(TOKEN_GROUPS), "probability groups changed")
    for group in value["groups"].values():
        count = group["token_count"]
        require(type(count) is int and count >= 0, "invalid probability group target count")
        if count == 0:
            require(group["mean_nll"] is None and group["nll_sum"] is None, "empty probability group was zero filled")
        else:
            require(all(isinstance(group[k], (float, int)) and math.isfinite(group[k]) for k in ("mean_nll", "nll_sum")), "nonfinite measured group NLL")
            require(math.isclose(group["mean_nll"] * count, group["nll_sum"], rel_tol=1e-9, abs_tol=1e-8), "group NLL mean/count/sum inconsistent")
    return value


def _stats(values):
    return dict(n=len(values), mean=statistics.fmean(values) if values else None,
        median=statistics.median(values) if values else None,
        minimum=min(values) if values else None, maximum=max(values) if values else None)


def _probability_cell(records):
    values = [_probability(record) for record in records]
    output = {}
    for name in TOKEN_GROUPS:
        valid = [value["groups"][name] for value in values if value is not None]
        measured = [value for value in valid if value["token_count"] > 0]
        count = sum(value["token_count"] for value in measured)
        output[name] = dict(sequence_denominator=len(records), measured_sequences=len(measured),
            NA_empty_group_sequences=sum(value["token_count"] == 0 for value in valid),
            UNKNOWN_sequences=sum(value is None for value in values),
            per_sequence_mean_nll=_stats([value["mean_nll"] for value in measured]),
            measured_target_token_count=count,
            pooled_token_mean_nll=math.fsum(value["nll_sum"] for value in measured) / count if count else None,
            no_NA_or_UNKNOWN_zero_fill=True)
    return output


def _paired_probabilities(reference, candidate):
    require(len(reference) == len(candidate), "probability pair task count differs")
    pairs = list(zip(map(_probability, reference), map(_probability, candidate), strict=True))
    output = {}
    for name in TOKEN_GROUPS:
        deltas, NA, unknown = [], 0, 0
        for left, right in pairs:
            if left is None or right is None:
                unknown += 1
                continue
            require(left["grouping_id"] == right["grouping_id"], "probability pair uses different original target grouping")
            a, b = left["groups"][name], right["groups"][name]
            require(a["token_count"] == b["token_count"], "probability pair target token count differs")
            if a["token_count"] == 0:
                NA += 1
            else:
                deltas.append(b["mean_nll"] - a["mean_nll"])
        output[name] = dict(sequence_denominator=len(pairs), measured_pairs=len(deltas),
            NA_empty_group_pairs=NA, UNKNOWN_pairs=unknown,
            candidate_minus_reference_mean_nll=_stats(deltas),
            positive_delta_count=sum(value > 0 for value in deltas),
            negative_delta_count=sum(value < 0 for value in deltas),
            exact_zero_delta_count=sum(value == 0 for value in deltas),
            positive_means_worse_fit_to_this_fixed_parent_expression=True,
            tolerance_or_significance_threshold=None)
    return output


def summarize(protocol, inputs, generation_results, probability_results):
    """Use frozen tasks plus flat logical rows; duplicate contexts share results.

    tasks: [{task_key, group: F|K}]. logical_rows: [{task_key, source: P|H|L,
    context_id|null, old_response_sha256, old_response_token_ids_sha256}].
    Result maps use (model, context_id) and (model, task_key), or nested model
    maps. Generation rows contain classification and the actual response hash
    and/or raw_generated_token_ids. Probability rows contain measurement.
    """
    tasks = inputs["tasks"]
    require(len(tasks) == 96 and len({task["task_key"] for task in tasks}) == 96, "frozen 96-task panel changed")
    require(Counter(task["group"] for task in tasks) == {"F": 48, "K": 48}, "frozen group denominator changed")
    logical = {}
    keys = {task["task_key"] for task in tasks}
    for row in inputs["logical_rows"]:
        key = (row["task_key"], row["source"])
        require(row["task_key"] in keys and row["source"] in MODELS, "logical row outside frozen panel")
        require(key not in logical, "duplicate logical context source")
        logical[key] = row
    panels = {}
    for group in ("F", "K"):
        selected = [task for task in tasks if task["group"] == group]
        matrix_records = {model: {source: [_lookup(generation_results, model,
            logical.get((task["task_key"], source), {}).get("context_id")) for task in selected]
            for source in MODELS} for model in MODELS}
        by_context = {source: {f"{candidate}_minus_{reference}": _paired(
            matrix_records[reference][source], matrix_records[candidate][source])
            for reference, candidate in PAIRS} for source in MODELS}
        by_model = {model: {f"h{candidate}_minus_h{reference}": _paired(
            matrix_records[model][reference], matrix_records[model][candidate])
            for reference, candidate in PAIRS} for model in MODELS}
        probabilities = {model: [_lookup(probability_results, model, task["task_key"])
            for task in selected] for model in MODELS}
        panels[group] = dict(denominator=48, task_keys=[task["task_key"] for task in selected],
            single_response_action_matrix={model: {source: _cell(matrix_records[model][source]) for source in MODELS} for model in MODELS},
            primary_hP_paired_models=by_context["P"],
            paired_models_at_fixed_history=by_context,
            paired_histories_at_fixed_model=by_model,
            source_model_source_history_reproduction={source: _diagonal(selected, source, logical, generation_results) for source in MODELS},
            fixed_parent_response_probability={model: _probability_cell(probabilities[model]) for model in MODELS},
            paired_probability_changes={f"{candidate}_minus_{reference}": _paired_probabilities(
                probabilities[reference], probabilities[candidate]) for reference, candidate in PAIRS})
    all_action_known = all(cell["unknown_count"] == 0 for panel in panels.values()
        for row in panel["single_response_action_matrix"].values() for cell in row.values())
    all_probability_known = all(group["UNKNOWN_sequences"] == 0 for panel in panels.values()
        for model in panel["fixed_parent_response_probability"].values() for group in model.values())
    output = dict(schema="v73_same_context_action_probability_summary.v1", protocol_id=protocol["id"],
        status="COMPLETE" if all_action_known and all_probability_known else "COMPLETE_WITH_UNKNOWN",
        panel_denominator=96, group_denominators={"F": 48, "K": 48},
        model_order=list(MODELS), history_order=list(MODELS), panels=panels,
        complete_action_matrix=all_action_known, complete_probability_matrix=all_probability_known,
        conditional_selected_panels_not_representative_dev_accuracy=True,
        new_execution_accuracy_or_program_accuracy_computed=False,
        source_diagonals_are_reproduction_checks=True,
        cross_history_difference_is_not_history_causal_share=True,
        reference_expression_NLL_does_not_cover_all_legal_expressions=True,
        fixed_parent_target_never_fed_to_free_generation=True,
        UNKNOWN_is_not_no_tool_call_or_zero=True, empty_probability_group_is_NA=True,
        independent_training_replications=0, bootstrap_or_significance_gate=False,
        automatic_followup_authorized=False, training_or_Full_resume_authorized=False)
    output["id"] = digest(output)
    return output
