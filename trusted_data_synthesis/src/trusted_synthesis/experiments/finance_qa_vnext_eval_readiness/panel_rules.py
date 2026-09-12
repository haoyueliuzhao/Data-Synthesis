"""One finite, pre-registered actual-period panel candidate universe."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from finraw.qa.graph_patterns import get_pattern

from ..finance_qa_vnext_catalog_bridge import panel_rules as old
from ..finance_qa_vnext_task_build.archive import record, require
from ..finance_qa_vnext_task_build.factory import round_robin
from ..finance_qa_vnext_task_build.protocol import CASH, FLOW_METRICS, RESTRICTED
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

GROUPS, TARGETS = old.GROUPS, old.TARGETS


def policy():
    return record(
        "actual_period_panel_policy",
        version=2,
        source_rule_id=old.policy()["id"],
        source_scope=(
            "same frozen 84 companyfacts snapshots; original 12 dev / 72 confirm eligible issuers"
        ),
        new_downloads=0,
        split_changes=0,
        historical_confirmation_reuse=False,
        registered_structures={
            "dual_sufficient": [
                "GrossProfit revenue-minus-cost adjacent annual change/growth",
                "typed cash or cash-including-restricted balance change/growth "
                "with complete CFO+CFI+CFF+matching FX bridge",
            ],
            "composition_required": (
                "same four registered metrics: exactly three actual consecutive annual flows"
            ),
            "other_financial": (
                "same revenue->net-income / revenue->operating-income three-period argmax followup"
            ),
        },
        quantities=(
            "difference and positive-base relative_change for dual; "
            "unchanged mean and peak semantics"
        ),
        cash_admission=(
            "exact native registered account tags and definitions, same-account FX/change tags, "
            "exact current flow dates, common 10-K accession, explicit reported aggregate "
            "reconciles; closure alone insufficient"
        ),
        candidate_enumeration=(
            "all finite native-qualified targets once; no new structures after results"
        ),
        selection=(
            "old registered targets in their original target_bindings order first "
            "(874 exports + 12 prior compiler rejections), then CIK/end-period/task-id "
            "round robin; successful source/QA/period-qualified candidates only"
        ),
        compile_reserve_per_group=8,
        compile_continuation=(
            "next eight from the same pre-enumerated order only, until quota or finite exhaustion"
        ),
        quotas=TARGETS,
        preserve_all_candidates_rejections_overflow=True,
        previous_export_impact_rows=874,
        previous_registered_impact_rows=886,
        Teacher_outcome_selection=False,
        model_requests=0,
        shortage_action="STOP; no additional sources, structure changes, or quota changes",
        canonical_identity=(
            "preserve target ID iff source actual periods, metrics, quantity, and direction "
            "unchanged; new QA/surface versions and real parents"
        ),
    )


def cash_certificate(previous, current, lookup, bindings, usage, split):
    consecutive(previous, current)
    definition_pair(previous, current, bindings)
    metric = current["metric_id"]
    gate(metric in {CASH, RESTRICTED}, "readiness.registered_cash_account")
    included = metric == RESTRICTED
    fx = (
        "effect_of_exchange_rate_on_cash_including_restricted"
        if included
        else "effect_of_exchange_rate_on_cash_and_cash_equivalents"
    )
    change = (
        "change_in_cash_including_restricted_and_exchange_rate_effect"
        if included
        else "change_in_cash_including_exchange_rate_effect"
    )
    interval = (
        (date.fromisoformat(previous["period_end"]) + timedelta(days=1)).isoformat(),
        current["period_end"],
    )
    components = [
        lookup.get((current["entity_id"], component, *interval))
        for component in [*FLOW_METRICS, fx, change]
    ]
    gate(
        all(row is not None for row in components), "readiness.cash_bridge_missing_typed_component"
    )
    rows = [previous, current, *components]
    old.basic(rows, bindings, usage, split)
    citation = common_accession(rows, bindings)
    gate(
        value(current) - value(previous)
        == sum((value(row) for row in components[:4]), Decimal(0))
        == value(components[4]),
        "readiness.cash_bridge_does_not_close",
    )
    plan, inputs = endpoint_plan(previous, current)
    endpoint = witness(plan, inputs, rows, "endpoint")
    movement_inputs = {
        f"component_{index}": row["fact_id"] for index, row in enumerate(components[:4])
    }
    movement_plan = {
        "operators": [
            {
                "step_id": "answer",
                "operator": "linear_combination",
                "inputs": [{"binding": key} for key in movement_inputs],
                "params": {"coefficients": [1, 1, 1, 1]},
            }
        ],
        "output_step": "answer",
    }
    return record(
        "financial_relation_certificate",
        family="stock_rollforward",
        complete=True,
        relation_rule="US_GAAP_cash_flow_complete_bridge_v1",
        account_scope="including_restricted" if included else "cash_only",
        numeric_closure_is_not_sole_admission_rule=True,
        leaf_fact_ids=[row["fact_id"] for row in rows],
        public_fact_ids=[row["fact_id"] for row in rows],
        complete_original_snapshot_available=True,
        source_citations=[citation],
        witnesses=[endpoint, witness(movement_plan, movement_inputs, rows, "movement")],
    )


def _scope(rows):
    return {
        "basis": "actual_period_set",
        "frequency": "annual",
        "actual_periods": [
            {
                "period_start": start,
                "period_end": end,
                "period_type": "duration" if start else "instant",
            }
            for start, end in sorted(
                {actual_period(row) for row in rows}, key=lambda pair: (pair[1], pair[0] or "")
            )
        ],
    }


def enumerate_all(facts, bindings, usage, split, raw_payloads, prior_order):
    accepted, failures = defaultdict(list), []
    lookup = {
        (row["entity_id"], row["metric_id"], *actual_period(row)): row for row in facts.values()
    }
    require(len(lookup) == len(facts), "readiness.unique_native_period_metric")
    series = defaultdict(list)
    for row in facts.values():
        if row["metric_id"] in {"gross_profit", CASH, RESTRICTED, *old.MEAN_METRICS}:
            series[row["entity_id"], row["metric_id"]].append(row)

    def reject(group, rows, exc):
        failures.append(
            {
                "family": group,
                "source_cluster": bindings[rows[0]["fact_id"]]["source_cluster"],
                "fact_ids": [row["fact_id"] for row in rows],
                "reason": getattr(exc, "code", str(exc)),
                "details": getattr(exc, "details", {}),
            }
        )

    for (entity, metric), unordered in sorted(series.items()):
        ordered = sorted(unordered, key=lambda row: (row["period_end"], row["fact_id"]))
        if metric in {"gross_profit", CASH, RESTRICTED}:
            for previous, current in zip(ordered, ordered[1:], strict=False):
                try:
                    certificate = (
                        old.dual_certificate if metric == "gross_profit" else cash_certificate
                    )(previous, current, lookup, bindings, usage, split)
                    for quantity in ("difference", "relative_change"):
                        if quantity == "relative_change" and value(previous) <= 0:
                            reject(
                                "dual_sufficient",
                                [previous, current],
                                BindingRejected("quantity.relative_change_requires_positive_base"),
                            )
                            continue
                        identifier, target = target_identity(previous, current, bindings, quantity)
                        match = old.base_match(
                            [previous, current],
                            bindings,
                            {"previous": previous["fact_id"], "current": current["fact_id"]},
                        )
                        # Existing explicit-source change templates already render exact
                        # endpoints; they remain unchanged for old dual questions.
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
                                "certificate": certificate
                                if quantity == "difference"
                                else relative_certificate(certificate, previous, facts),
                            }
                        )
                except (BindingRejected, ValueError) as exc:
                    reject("dual_sufficient", [previous, current], exc)
        if metric not in old.MEAN_METRICS:
            continue
        for start in range(max(0, len(ordered) - 2)):
            rows = ordered[start : start + 3]
            try:
                old.series_contract(rows, bindings, usage, split)
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
                identifier, target = old.multi_identity(
                    rows, bindings, "three_annual_flow_mean", [metric]
                )
                match = old.base_match(rows, bindings, {"series": [row["fact_id"] for row in rows]})
                match.update(
                    start_period=rows[0]["fiscal_year"],
                    end_period=rows[-1]["fiscal_year"],
                    observation_count=3,
                    target_time_scope=_scope(rows),
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
                    target_coefficients=["1/3"] * 3,
                    endpoints_only_sufficient=False,
                    complete_original_snapshot_available=True,
                    countermodel={
                        "change_only_middle_annual_flow_by": "1 million USD",
                        "target_mean_changes_by": "1/3 million USD",
                        "first_and_last_annual_flows_unchanged": True,
                    },
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
                reject("composition_required", rows, exc)
            if metric != "revenue":
                continue
            for _, secondary in old.FOLLOWUP_PAIRS:
                try:
                    old.series_contract(rows, bindings, usage, split)
                    following = [
                        lookup.get((entity, secondary, *actual_period(row))) for row in rows
                    ]
                    gate(
                        all(row is not None for row in following),
                        "panel.followup_missing_same_actual_period",
                    )
                    old.series_contract(following, bindings, usage, split)
                    old.basic([*rows, *following], bindings, usage, split)
                    gate(
                        sum(value(row) == max(value(item) for item in rows) for row in rows) == 1,
                        "panel.ambiguous_primary_peak",
                    )
                    all_rows = [*rows, *following]
                    identifier, target = old.multi_identity(
                        all_rows,
                        bindings,
                        "three_year_peak_then_same_period_metric",
                        [metric, secondary],
                    )
                    match = old.base_match(
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
                        target_time_scope=_scope(rows),
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
                        unique_primary_peak=True,
                        operation_structure="argmax -> same-actual-period select",
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
                    reject("other_financial", rows, exc)
    identifiers = [row["task_id"] for values in accepted.values() for row in values]
    require(len(identifiers) == len(set(identifiers)), "readiness.unique_canonical_targets")
    ranks = {identifier: index for index, identifier in enumerate(prior_order)}
    result = {}
    for group in GROUPS:
        previous = sorted(
            (row for row in accepted[group] if row["task_id"] in ranks),
            key=lambda row: ranks[row["task_id"]],
        )
        fresh = round_robin([row for row in accepted[group] if row["task_id"] not in ranks])
        result[group] = [*previous, *fresh]
    return result, failures
