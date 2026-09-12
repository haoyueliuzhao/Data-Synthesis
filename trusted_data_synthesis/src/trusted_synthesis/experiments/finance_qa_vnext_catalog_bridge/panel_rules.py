"""Bounded evaluation targets and source-sufficiency proofs, fixed before sampling."""

import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from finraw.qa.comparability import comparability_policy
from finraw.qa.graph_patterns import get_pattern

from ..finance_qa_vnext_task_build.archive import record, require
from ..finance_qa_vnext_task_build.factory import round_robin
from ..finance_qa_vnext_task_build.protocol import (
    METRIC_TAGS,
    SPLIT_SALT,
    all_leaf_uses,
    source_split,
)
from ..finance_qa_vnext_task_build.relations import (
    BindingRejected,
    actual_period,
    common_accession,
    consecutive,
    definition_pair,
    endpoint_plan,
    gate,
    relative_certificate,
    target_identity,
    value,
    witness,
)

GROUPS = ("dual_sufficient", "composition_required", "other_financial")
TARGETS = {"dev": dict.fromkeys(GROUPS, 60), "confirm": dict.fromkeys(GROUPS, 240)}
MEAN_METRICS = (
    "revenue",
    "net_income",
    "operating_income",
    "net_cash_provided_by_used_in_operating_activities",
)
FOLLOWUP_PAIRS = (("revenue", "net_income"), ("revenue", "operating_income"))


def policy():
    return record(
        "evaluation_panel_policy",
        source_split_salt=SPLIT_SALT,
        original_source_split_required=True,
        per_group_targets=TARGETS,
        old_confirmation=(
            "exclude every issuer in the frozen old confirmation registration; "
            "archived exact ticker/CIK join"
        ),
        historical_train_dev_issuers_blanket_excluded=False,
        source_scope=(
            "one fixed archived companyfacts snapshot per eligible CIK; "
            "no download or issuer HTML expansion"
        ),
        selection=(
            "source metadata before numeric inspection; latest snapshot, "
            "same native period/tag/vintage policy as training"
        ),
        enumeration=(
            "all eligible finite targets once, round-robin CIK ascending and end-period/task "
            "identity; fixed group cap, no quality-score or Teacher-outcome rank"
        ),
        dual_sufficient=(
            "adjacent annual GrossProfit difference or positive-base growth; "
            "fully disclosed revenue/cost reconstructions in each annual period"
        ),
        composition_required={
            "quantity": "arithmetic mean of exactly three consecutive actual annual flows",
            "metric_ids": list(MEAN_METRICS),
            "proof": (
                "each annual operand has a nonzero 1/3 coefficient; first/last observations "
                "alone leave the middle annual flow free; "
                "no cross-year flow conservation identity is asserted"
            ),
            "complete_material": (
                "all selected native annual observations and all complete original "
                "companyfacts bytes remain publicly retrievable; no endpoint is removed"
            ),
            "scope_limit": (
                "temporal-component integration within the registered native annual-flow "
                "semantics, not a proof over arbitrary unformalized disclosure meanings"
            ),
            "source_screen": (
                "reject a same-concept USD record spanning the entire three-year target "
                "window; never select by equality to an aggregate answer"
            ),
        },
        other_financial={
            "quantity": (
                "argmax on three annual primary observations "
                "then same-period secondary metric lookup"
            ),
            "metric_pairs": [list(pair) for pair in FOLLOWUP_PAIRS],
            "ties": "retained as source rejection, never broken using the secondary value",
        },
        registered_patterns=[
            "pinned_annual_metric_change",
            "pinned_annual_metric_growth",
            "entity_metric_temporal_average",
            "temporal_argmax_then_metric_lookup",
        ],
        public_surface=(
            "existing deterministic registered QA templates; no evaluation rewrite requests"
        ),
        score={
            "primary": "complete source-supported verifiable execution and correct first Final",
            "numeric": "unit-correct Decimal answer rounded to 2 places half away from zero",
            "peak_followup": "both requested period and secondary amount must be correct",
            "reference_program_text_required": False,
            "Teacher_success_selection": False,
            "no_Final_is_failure": True,
        },
        limitations=[
            "three deliberately bounded structures, not broad financial-domain coverage",
            "task counts are not independent source counts",
            "same issuer/snapshot, overlapping windows and paired quantity targets are correlated",
            "no Student outputs, tokenization or evaluation sessions in panel preparation",
        ],
        new_API_requests=0,
    )


def basic(facts, bindings, usage, split):
    identifiers = [fact["fact_id"] for fact in facts]
    gate(split in {"dev", "confirm"}, "panel.evaluation_split_only")
    gate(len(identifiers) == len(set(identifiers)), "binding.duplicate_leaf")
    all_leaf_uses(identifiers, {}, usage, expected=split)
    gate(len({fact["entity_id"] for fact in facts}) == 1, "binding.company_scope_mismatch")
    gate(
        len({(fact["normalized_unit"], fact["normalized_currency"]) for fact in facts}) == 1,
        "binding.unit_mismatch",
    )
    for fact in facts:
        native = bindings[fact["fact_id"]]
        gate(
            source_split(native["source_cluster"]) == split
            and native["split"] == split
            and native["allowed_uses"] == [split],
            "panel.original_salt_split_required",
        )
        gate(
            fact.get("graph_ready") == 1
            and fact["verification_status"] in {"single_source", "cross_verified"},
            "binding.not_graph_ready",
        )
        gate(not fact.get("is_forecast"), "panel.forecast_not_actual")
        gate(
            fact.get("source_definition_id") is not None
            and native.get("native_definition", {}).get("description"),
            "binding.missing_definition",
        )
        gate(
            fact["source_definition_id"] == native["source_definition_id"],
            "binding.wrong_definition_parent",
        )
        gate(native["tag"] in METRIC_TAGS[fact["metric_id"]], "binding.wrong_source_definition")
        gate(
            actual_period(fact) == (native["record"].get("start"), native["record"]["end"]),
            "binding.native_period_mismatch",
        )
        gate(
            value(fact) == Decimal(str(native["record"]["val"])) / Decimal(1000000),
            "binding.normalization_precision_loss",
        )
        gate(
            fact["entity_id"] == native["entity_id"]
            and fact["raw_object_id"] == native["raw_object_id"],
            "binding.native_parent_mismatch",
        )


def dual_certificate(previous, current, lookup, bindings, usage, split):
    consecutive(previous, current)
    definition_pair(previous, current, bindings)
    gate(current["metric_id"] == "gross_profit", "panel.registered_dual_metric")
    native = bindings[current["fact_id"]]
    gate(
        "revenue less cost of goods and services sold"
        in native["native_definition"]["description"].lower(),
        "relation.native_gross_profit_definition_not_supported",
    )
    components, citations = [], []
    for endpoint in (previous, current):
        pair = [
            lookup.get((endpoint["entity_id"], metric, *actual_period(endpoint)))
            for metric in ("revenue", "cost_of_revenue")
        ]
        gate(all(row is not None for row in pair), "relation.missing_annual_component")
        basic([endpoint, *pair], bindings, usage, split)
        gate(
            bindings[pair[1]["fact_id"]]["tag"] in {"CostOfRevenue", "CostOfGoodsAndServicesSold"},
            "relation.cost_scope_not_proven_complete",
        )
        citations.append(common_accession([endpoint, *pair], bindings))
        gate(
            value(endpoint) == value(pair[0]) - value(pair[1]), "relation.revenue_cost_do_not_close"
        )
        components.extend(pair)
    for left, right in ((components[0], components[2]), (components[1], components[3])):
        definition_pair(left, right, bindings)
    leaves = [previous, current, *components]
    basic(leaves, bindings, usage, split)
    endpoint, endpoint_inputs = endpoint_plan(previous, current)
    composition_inputs = {f"component_{i}": row["fact_id"] for i, row in enumerate(components)}
    composition = {
        "operators": [
            {
                "step_id": "answer",
                "operator": "linear_combination",
                "inputs": [{"binding": key} for key in composition_inputs],
                "params": {"coefficients": [-1, 1, 1, -1]},
            }
        ],
        "output_step": "answer",
    }
    witnesses = [
        witness(endpoint, endpoint_inputs, leaves, "endpoint"),
        witness(composition, composition_inputs, leaves, "movement"),
    ]
    gate(
        Decimal(witnesses[0]["output"]["value"]) == Decimal(witnesses[1]["output"]["value"]),
        "panel.dual_witness_agreement",
    )
    return record(
        "financial_relation_certificate",
        family="annual_flow",
        relation_rule="US_GAAP_gross_profit_revenue_less_cost_v1",
        complete=True,
        numeric_closure_is_not_sole_admission_rule=True,
        raw_definition=native["native_definition"],
        source_citations=citations,
        witnesses=witnesses,
        leaf_fact_ids=[row["fact_id"] for row in leaves],
        public_fact_ids=[row["fact_id"] for row in leaves],
        previous_component_fact_ids=[row["fact_id"] for row in components[:2]],
        previous_component_coefficients=[1, -1],
    )


def series_contract(rows, bindings, usage, split):
    gate(len(rows) == 3, "panel.exact_three_periods")
    basic(rows, bindings, usage, split)
    for left, right in zip(rows, rows[1:], strict=False):
        consecutive(left, right)
        definition_pair(left, right, bindings)
    gate(all(row.get("period_start") for row in rows), "panel.annual_flows_not_stocks")
    # Registered QA average/argmax uses fiscal-year indices. Require the fiscal
    # year to denote the exact native observation end year, never a filing FY alias.
    gate(
        all(int(row["fiscal_year"]) == int(row["period_end"][:4]) for row in rows),
        "panel.observation_year_not_filing_alias",
    )


def multi_identity(rows, bindings, quantity, metrics):
    target = {
        "source_cluster": bindings[rows[0]["fact_id"]]["source_cluster"],
        "metric_ids": list(metrics),
        "definitions": [
            {
                "metric_id": metric,
                "tag": bindings[next(row["fact_id"] for row in rows if row["metric_id"] == metric)][
                    "tag"
                ],
                "native_definition": bindings[
                    next(row["fact_id"] for row in rows if row["metric_id"] == metric)
                ]["native_definition"],
            }
            for metric in metrics
        ],
        "actual_periods": sorted({actual_period(row) for row in rows}),
        "current_period": list(actual_period(max(rows, key=lambda row: row["period_end"]))),
        "quantity": quantity,
        "unit": "million USD",
        "currency": "USD",
        "source_revision": "as reported in fixed supplied native records",
    }
    raw = json.dumps(target, sort_keys=True, separators=(",", ":")).encode()
    return "task_" + hashlib.sha256(raw).hexdigest(), target


def base_match(rows, bindings, input_bindings):
    return {
        "fact_ids": [row["fact_id"] for row in rows],
        "entity_ids": [rows[0]["entity_id"]],
        "metric_ids": sorted({row["metric_id"] for row in rows}),
        "input_bindings": input_bindings,
        "source_document_ids": sorted({bindings[row["fact_id"]]["document_id"] for row in rows}),
        "frequency": "annual",
        "binding_source": "frozen_panel_actual_period_enumerator_v1",
    }


def enumerate_targets(facts, bindings, usage, split, raw_payloads):
    """Finite source-driven enumeration; failures/overflow preserved without retries."""
    accepted, failures = defaultdict(list), []
    lookup = {
        (row["entity_id"], row["metric_id"], *actual_period(row)): row for row in facts.values()
    }
    require(len(lookup) == len(facts), "panel.unique_native_fact_period")
    series = defaultdict(list)
    for row in facts.values():
        if row["metric_id"] in {"gross_profit", *MEAN_METRICS}:
            series[row["entity_id"], row["metric_id"]].append(row)

    def failure(group, rows, exc):
        failures.append(
            {
                "group": group,
                "fact_ids": [row["fact_id"] for row in rows],
                "source_cluster": bindings[rows[0]["fact_id"]]["source_cluster"],
                "reason": getattr(exc, "code", str(exc)),
                "details": getattr(exc, "details", {}),
            }
        )

    for (entity, metric), unordered in sorted(series.items()):
        ordered = sorted(unordered, key=lambda row: (row["period_end"], row["fact_id"]))
        if metric == "gross_profit":
            for previous, current in zip(ordered, ordered[1:], strict=False):
                try:
                    certificate = dual_certificate(
                        previous, current, lookup, bindings, usage, split
                    )
                    for quantity in ("difference", "relative_change"):
                        if quantity == "relative_change" and value(previous) <= 0:
                            failures.append(
                                {
                                    "group": "dual_sufficient",
                                    "fact_ids": [previous["fact_id"], current["fact_id"]],
                                    "reason": "quantity.relative_change_requires_positive_base",
                                }
                            )
                            continue
                        identifier, target = target_identity(previous, current, bindings, quantity)
                        cert = (
                            certificate
                            if quantity == "difference"
                            else relative_certificate(certificate, previous, facts)
                        )
                        match = base_match(
                            [previous, current],
                            bindings,
                            {"previous": previous["fact_id"], "current": current["fact_id"]},
                        )
                        match["target_time_scope"] = {
                            "basis": "explicit_source_periods",
                            "frequency": "annual",
                            "previous_period_start": previous.get("period_start"),
                            "previous_period_end": previous["period_end"],
                            "period_start": current.get("period_start"),
                            "period_end": current["period_end"],
                        }
                        accepted["dual_sufficient"].append(
                            {
                                "task_id": identifier,
                                "target": target,
                                "family": "dual_sufficient",
                                "pattern_id": "pinned_annual_metric_change"
                                if quantity == "difference"
                                else "pinned_annual_metric_growth",
                                "match": match,
                                "certificate": cert,
                            }
                        )
                except (BindingRejected, ValueError) as exc:
                    failure("dual_sufficient", [previous, current], exc)
        if metric not in MEAN_METRICS:
            continue
        for start in range(max(0, len(ordered) - 2)):
            rows = ordered[start : start + 3]
            try:
                series_contract(rows, bindings, usage, split)
                native = bindings[rows[0]["fact_id"]]
                concept = raw_payloads[native["raw_object_id"]]["facts"]["us-gaap"][native["tag"]]
                gate(
                    not any(
                        item.get("start") == rows[0]["period_start"]
                        and item.get("end") == rows[-1]["period_end"]
                        for item in concept.get("units", {}).get("USD", [])
                    ),
                    "panel.full_source_contains_same_concept_window_aggregate",
                )
                identifier, target = multi_identity(
                    rows, bindings, "three_annual_flow_mean", [metric]
                )
                match = base_match(rows, bindings, {"series": [row["fact_id"] for row in rows]})
                match.update(
                    start_period=rows[0]["fiscal_year"],
                    end_period=rows[-1]["fiscal_year"],
                    observation_count=3,
                )
                oracle = witness(
                    get_pattern("entity_metric_temporal_average").operator_template,
                    match["input_bindings"],
                    rows,
                    "temporal_component_integration",
                )
                certificate = record(
                    "panel_composition_certificate",
                    complete=True,
                    leaf_fact_ids=match["fact_ids"],
                    public_fact_ids=match["fact_ids"],
                    witnesses=[oracle],
                    target_coefficients=["1/3", "1/3", "1/3"],
                    endpoints_only_sufficient=False,
                    countermodel={
                        "change_only_middle_annual_flow_by": "1 million USD",
                        "target_mean_changes_by": "1/3 million USD",
                        "first_and_last_annual_flows_unchanged": True,
                    },
                    complete_original_snapshot_available=True,
                    source_scope=(
                        "registered annual-flow semantics; no claim of arbitrary "
                        "natural-language sufficiency decision"
                    ),
                )
                accepted["composition_required"].append(
                    {
                        "task_id": identifier,
                        "target": target,
                        "family": "composition_required",
                        "pattern_id": "entity_metric_temporal_average",
                        "match": match,
                        "certificate": certificate,
                    }
                )
            except (BindingRejected, ValueError) as exc:
                failure("composition_required", rows, exc)
            if metric != "revenue":
                continue
            for _, secondary in FOLLOWUP_PAIRS:
                try:
                    series_contract(rows, bindings, usage, split)
                    following = [
                        lookup.get((entity, secondary, *actual_period(row))) for row in rows
                    ]
                    gate(
                        all(row is not None for row in following),
                        "panel.followup_missing_same_actual_period",
                    )
                    series_contract(following, bindings, usage, split)
                    basic([*rows, *following], bindings, usage, split)
                    gate(
                        sum(value(row) == max(value(item) for item in rows) for row in rows) == 1,
                        "panel.ambiguous_primary_peak",
                    )
                    all_rows = [*rows, *following]
                    identifier, target = multi_identity(
                        all_rows,
                        bindings,
                        "three_year_peak_then_same_period_metric",
                        [metric, secondary],
                    )
                    match = base_match(
                        all_rows,
                        bindings,
                        {
                            "primary_series": [row["fact_id"] for row in rows],
                            "secondary_series": [row["fact_id"] for row in following],
                        },
                    )
                    match.update(
                        start_period=rows[0]["fiscal_year"],
                        end_period=rows[-1]["fiscal_year"],
                        observation_count=3,
                        primary_metric_id=metric,
                        secondary_metric_id=secondary,
                    )
                    oracle = witness(
                        get_pattern("temporal_argmax_then_metric_lookup").operator_template,
                        match["input_bindings"],
                        all_rows,
                        "peak_selection_then_metric_lookup",
                    )
                    certificate = record(
                        "panel_other_financial_certificate",
                        complete=True,
                        leaf_fact_ids=match["fact_ids"],
                        public_fact_ids=match["fact_ids"],
                        witnesses=[oracle],
                        operation_structure="argmax -> same-period select",
                        unique_primary_peak=True,
                    )
                    accepted["other_financial"].append(
                        {
                            "task_id": identifier,
                            "target": target,
                            "family": "other_financial",
                            "pattern_id": "temporal_argmax_then_metric_lookup",
                            "match": match,
                            "certificate": certificate,
                        }
                    )
                except (BindingRejected, ValueError) as exc:
                    failure("other_financial", rows, exc)
    all_ids = [row["task_id"] for rows in accepted.values() for row in rows]
    require(len(set(all_ids)) == len(all_ids), "panel.semantic_targets_unique")
    selected, overflow = {}, {}
    for group in GROUPS:
        ordered = round_robin(accepted[group])
        selected[group] = ordered[: TARGETS[split][group]]
        overflow[group] = [row["task_id"] for row in ordered[TARGETS[split][group] :]]
    return (
        selected,
        failures,
        {
            "qualified_counts": {group: len(accepted[group]) for group in GROUPS},
            "cap_excluded_target_ids": overflow,
            "fixed_targets": TARGETS[split],
        },
    )


def semantic_policy():
    return comparability_policy({"followup_metric_pairs": [list(pair) for pair in FOLLOWUP_PAIRS]})


def independent_answer(item, facts):
    inputs = item["match"]["input_bindings"]
    if item["family"] == "dual_sufficient":
        result = value(facts[inputs["current"]]) - value(facts[inputs["previous"]])
        if item["target"]["quantity"] == "relative_change":
            result = 100 * result / value(facts[inputs["previous"]])
        return {"value": str(result)}
    if item["family"] == "composition_required":
        return {"value": str(sum(value(facts[key]) for key in inputs["series"]) / 3)}
    primary = [facts[key] for key in inputs["primary_series"]]
    chosen = max(primary, key=value)
    secondary = next(
        facts[key]
        for key in inputs["secondary_series"]
        if actual_period(facts[key]) == actual_period(chosen)
    )
    return {"period": str(chosen["fiscal_year"]), "value": str(value(secondary))}
