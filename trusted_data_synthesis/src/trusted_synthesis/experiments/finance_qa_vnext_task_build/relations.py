"""Typed finite financial relation compiler, distinct from reference arithmetic."""

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal

from finraw.qa.plans import execute_plan, materialize_plan

from .archive import record
from .protocol import CASH, FLOW_METRICS, METRIC_TAGS, RESTRICTED, all_leaf_uses


class BindingRejected(ValueError):
    def __init__(self, code, **details):
        self.code, self.details = code, details
        super().__init__(code)


def gate(condition, code, **details):
    if not condition:
        raise BindingRejected(code, **details)


def actual_period(fact):
    return fact.get("period_start"), fact["period_end"]


def consecutive(previous, current):
    left, right = (
        date.fromisoformat(previous["period_end"]),
        date.fromisoformat(current["period_end"]),
    )
    gate(
        330 <= (right - left).days <= 380,
        "periods.not_adjacent_annual_endpoints",
        previous=actual_period(previous),
        current=actual_period(current),
    )
    gate(
        bool(previous.get("period_start")) == bool(current.get("period_start")),
        "periods.stock_flow_mismatch",
    )
    if current.get("period_start"):
        gate(
            date.fromisoformat(current["period_start"]) == left + timedelta(days=1),
            "periods.flow_gap_or_overlap",
            previous=actual_period(previous),
            current=actual_period(current),
        )
        for fact in (previous, current):
            gate(
                330
                <= (
                    date.fromisoformat(fact["period_end"])
                    - date.fromisoformat(fact["period_start"])
                ).days
                + 1
                <= 380,
                "periods.not_annual_duration",
                fact_id=fact["fact_id"],
                period=actual_period(fact),
            )


def value(fact):
    return Decimal(str(fact["normalized_value"]))


def common_accession(facts, bindings):
    possibilities = []
    for fact in facts:
        native = bindings[fact["fact_id"]]
        possibilities.append(
            {
                str(row["record"]["accn"])
                for row in native["all_equal_source_occurrences"]
                if row["record"].get("form") in {"10-K", "10-K/A"} and row["record"].get("accn")
            }
        )
    common = set.intersection(*possibilities)
    gate(
        bool(common),
        "relation.no_common_filing_accession",
        facts=[fact["fact_id"] for fact in facts],
    )
    # Lexical selection is over accession identity, not values or closure.
    selected = sorted(common)[-1]
    return {
        "accession": selected,
        "source_occurrences": [
            {
                "fact_id": fact["fact_id"],
                **next(
                    row
                    for row in bindings[fact["fact_id"]]["all_equal_source_occurrences"]
                    if row["record"].get("accn") == selected
                ),
            }
            for fact in facts
        ],
    }


def basic(facts, bindings, usage):
    identifiers = [fact["fact_id"] for fact in facts]
    gate(len(identifiers) == len(set(identifiers)), "binding.duplicate_leaf")
    all_leaf_uses(identifiers, {}, usage)
    gate(len({fact["entity_id"] for fact in facts}) == 1, "binding.company_scope_mismatch")
    gate(
        len({(fact["normalized_unit"], fact["normalized_currency"]) for fact in facts}) == 1,
        "binding.unit_mismatch",
    )
    for fact in facts:
        gate(
            fact.get("graph_ready") == 1
            and fact["verification_status"] in {"single_source", "cross_verified"},
            "binding.not_graph_ready",
            fact_id=fact["fact_id"],
        )
        native = bindings[fact["fact_id"]]
        if native.get("source_kind") == "issuer_report_table":
            from .issuer_tables import validate_binding

            validate_binding(fact, native)
            continue
        gate(
            fact.get("source_definition_id") is not None
            and native.get("native_definition", {}).get("description"),
            "binding.missing_definition",
            fact_id=fact["fact_id"],
        )
        gate(
            fact["source_definition_id"] == native["source_definition_id"],
            "binding.wrong_definition_parent",
            fact_id=fact["fact_id"],
        )
        gate(
            native["tag"] in METRIC_TAGS[fact["metric_id"]],
            "binding.wrong_source_definition",
            fact_id=fact["fact_id"],
        )
        gate(
            actual_period(fact) == (native["record"].get("start"), native["record"]["end"]),
            "binding.native_period_mismatch",
            fact_id=fact["fact_id"],
        )
        gate(
            value(fact) == Decimal(str(native["record"]["val"])) / Decimal(1000000),
            "binding.normalization_precision_loss",
            fact_id=fact["fact_id"],
        )
        gate(
            fact["entity_id"] == native["entity_id"]
            and fact["raw_object_id"] == native["raw_object_id"],
            "binding.native_parent_mismatch",
            fact_id=fact["fact_id"],
        )


def definition_pair(previous, current, bindings):
    gate(previous["metric_id"] == current["metric_id"], "binding.target_metric_mismatch")
    gate(
        previous["source_definition_id"] == current["source_definition_id"],
        "relation.definition_changed_between_periods",
        previous=previous["source_definition_id"],
        current=current["source_definition_id"],
    )
    gate(
        bindings[previous["fact_id"]]["native_definition"]
        == bindings[current["fact_id"]]["native_definition"],
        "relation.native_definition_changed",
    )


def target_identity(previous, current, bindings, quantity="difference"):
    native = bindings[current["fact_id"]]
    target = {
        "source_cluster": native["source_cluster"],
        "metric_id": current["metric_id"],
        "definition": {"tag": native["tag"], **native["native_definition"]},
        "previous_period": list(actual_period(previous)),
        "current_period": list(actual_period(current)),
        "quantity": quantity,
        "unit": "million USD" if quantity == "difference" else "percent",
        "currency": "USD" if quantity == "difference" else None,
        "source_revision": "as reported in the fixed supplied native records",
    }
    raw = json.dumps(target, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "task_" + hashlib.sha256(raw).hexdigest(), target


def endpoint_plan(previous, current):
    inputs = {"previous": previous["fact_id"], "current": current["fact_id"]}
    plan = materialize_plan(
        {
            "operators": [
                {
                    "step_id": "answer",
                    "operator": "difference",
                    "inputs": [{"binding": "previous"}, {"binding": "current"}],
                }
            ],
            "output_step": "answer",
        },
        {},
    )
    return plan, inputs


def witness(plan, inputs, facts, label):
    execution = execute_plan(plan, inputs, {fact["fact_id"]: fact for fact in facts})
    gate(execution.status == "passed", "oracle.plan_execution_failed", errors=execution.errors)
    return record(
        "oracle_basis_witness",
        basis=label,
        operator_dag=plan,
        input_bindings=inputs,
        output=execution.output,
        intermediate_results=execution.intermediate_results,
        execution_status=execution.status,
        origin="deterministic_QA_reference_executor",
        is_Teacher_trajectory=False,
        model_session_id=None,
    )


def annual_relation(previous, current, lookup, bindings, usage):
    consecutive(previous, current)
    definition_pair(previous, current, bindings)
    gate(current["metric_id"] == "gross_profit", "relation.not_registered_annual_target")
    native = bindings[current["fact_id"]]
    gate(
        "revenue less cost of goods and services sold"
        in native["native_definition"]["description"].lower(),
        "relation.native_gross_profit_definition_not_supported",
    )
    components, citations = [], []
    for endpoint in (previous, current):
        period = actual_period(endpoint)
        pair = []
        for metric in ("revenue", "cost_of_revenue"):
            fact = lookup.get((endpoint["entity_id"], metric, *period))
            gate(
                fact is not None,
                "relation.missing_annual_component",
                entity_id=endpoint["entity_id"],
                metric_id=metric,
                period=period,
            )
            pair.append(fact)
        basic([endpoint, *pair], bindings, usage)
        gate(
            bindings[pair[1]["fact_id"]]["tag"] in {"CostOfRevenue", "CostOfGoodsAndServicesSold"},
            "relation.cost_scope_not_proven_complete",
            fact_id=pair[1]["fact_id"],
            tag=bindings[pair[1]["fact_id"]]["tag"],
        )
        citations.append(common_accession([endpoint, *pair], bindings))
        gate(
            value(endpoint) == value(pair[0]) - value(pair[1]),
            "relation.annual_definition_does_not_close",
            endpoint=endpoint["fact_id"],
            components=[fact["fact_id"] for fact in pair],
        )
        components.extend(pair)
    for left, right in ((components[0], components[2]), (components[1], components[3])):
        definition_pair(left, right, bindings)
    facts = [previous, current, *components]
    basic(facts, bindings, usage)
    plan, inputs = endpoint_plan(previous, current)
    e = witness(plan, inputs, facts, "endpoint")
    m_inputs = {f"component_{index}": fact["fact_id"] for index, fact in enumerate(components)}
    m_plan = {
        "operators": [
            {
                "step_id": "answer",
                "operator": "linear_combination",
                "inputs": [{"binding": key} for key in m_inputs],
                "params": {"coefficients": [-1, 1, 1, -1]},
            }
        ],
        "output_step": "answer",
    }
    m = witness(m_plan, m_inputs, facts, "movement")
    gate(
        Decimal(e["output"]["value"]) == Decimal(m["output"]["value"]),
        "relation.oracle_route_disagreement",
    )
    return record(
        "financial_relation_certificate",
        relation_rule="US_GAAP_gross_profit_revenue_less_cost_v1",
        family="annual_flow",
        semantic_basis=(
            "native GrossProfit definition, full revenue/cost concepts, "
            "same-period consolidated records and common filing per period"
        ),
        complete=True,
        numeric_closure_is_not_sole_admission_rule=True,
        public_fact_ids=[fact["fact_id"] for fact in facts],
        leaf_fact_ids=[fact["fact_id"] for fact in facts],
        raw_definition=native["native_definition"],
        source_citations=citations,
        witnesses=[e, m],
        previous_component_fact_ids=[row["fact_id"] for row in components[:2]],
        previous_component_coefficients=[1, -1],
    )


def relative_certificate(certificate, previous, facts):
    """Two actual quantity targets share a source cluster, not a task identity."""
    from copy import deepcopy

    gate(value(previous) > 0, "quantity.relative_change_requires_positive_base")
    witnesses = []
    for source_witness in certificate["witnesses"]:
        plan = deepcopy(source_witness["operator_dag"])
        inputs = deepcopy(source_witness["input_bindings"])
        gate(len(plan["operators"]) == 1, "quantity.registered_single_delta_plan")
        plan["operators"][0]["step_id"] = "change"
        if source_witness["basis"] == "movement" and certificate.get("previous_component_fact_ids"):
            identifiers = certificate["previous_component_fact_ids"]
            coefficients = certificate.get("previous_component_coefficients") or [1] * len(
                identifiers
            )
            names = [f"base_component_{index}" for index in range(len(identifiers))]
            inputs.update(zip(names, identifiers, strict=True))
            plan["operators"].append(
                {
                    "step_id": "base",
                    "operator": "linear_combination",
                    "inputs": [{"binding": name} for name in names],
                    "params": {"coefficients": coefficients},
                }
            )
            denominator = {"step": "base"}
        else:
            inputs["positive_base"] = previous["fact_id"]
            denominator = {"binding": "positive_base"}
        plan["operators"].append(
            {
                "step_id": "answer",
                "operator": "ratio_percent",
                "inputs": [{"step": "change"}, denominator],
            }
        )
        plan["output_step"] = "answer"
        witnesses.append(witness(plan, inputs, list(facts.values()), source_witness["basis"]))
    gate(
        len({Decimal(row["output"]["value"]) for row in witnesses}) == 1,
        "quantity.relative_oracles_agree",
    )
    return record(
        "relative_quantity_certificate",
        family=certificate["family"],
        quantity="relative_change",
        base_relation_certificate=certificate,
        leaf_fact_ids=certificate["leaf_fact_ids"],
        public_fact_ids=certificate["public_fact_ids"],
        witnesses=witnesses,
        source_cluster_is_shared_not_an_independent_sample=True,
    )


def stock_relation(previous, current, lookup, bindings, usage):
    consecutive(previous, current)
    definition_pair(previous, current, bindings)
    gate(current["metric_id"] in {CASH, RESTRICTED}, "relation.not_registered_stock_account")
    scope = "including_restricted" if current["metric_id"] == RESTRICTED else "cash_only"
    fx = (
        "effect_of_exchange_rate_on_cash_including_restricted"
        if scope == "including_restricted"
        else "effect_of_exchange_rate_on_cash_and_cash_equivalents"
    )
    change = (
        "change_in_cash_including_restricted_and_exchange_rate_effect"
        if scope == "including_restricted"
        else "change_in_cash_including_exchange_rate_effect"
    )
    period = (
        (date.fromisoformat(previous["period_end"]) + timedelta(days=1)).isoformat(),
        current["period_end"],
    )
    components = []
    for metric in [*FLOW_METRICS, fx, change]:
        fact = lookup.get((current["entity_id"], metric, *period))
        gate(
            fact is not None,
            "relation.missing_cash_bridge_component",
            entity_id=current["entity_id"],
            account=current["metric_id"],
            metric_id=metric,
            period=period,
        )
        components.append(fact)
    facts = [previous, current, *components]
    basic(facts, bindings, usage)
    citation = common_accession(facts, bindings)
    gate(
        value(current) - value(previous)
        == sum((value(fact) for fact in components[:4]), Decimal(0))
        == value(components[4]),
        "relation.cash_bridge_not_complete_or_does_not_close",
        facts=[fact["fact_id"] for fact in facts],
    )
    plan, inputs = endpoint_plan(previous, current)
    e = witness(plan, inputs, facts, "endpoint")
    m_inputs = {f"component_{index}": fact["fact_id"] for index, fact in enumerate(components[:4])}
    m_plan = {
        "operators": [
            {
                "step_id": "answer",
                "operator": "linear_combination",
                "inputs": [{"binding": key} for key in m_inputs],
                "params": {"coefficients": [1, 1, 1, 1]},
            }
        ],
        "output_step": "answer",
    }
    m = witness(m_plan, m_inputs, facts, "movement")
    return record(
        "financial_relation_certificate",
        relation_rule="US_GAAP_cash_flow_complete_bridge_v1",
        family="stock_rollforward",
        semantic_basis=(
            "same filing cash-flow statement account and explicit "
            "operating/investing/financing/FX totals; matching reported aggregate change "
            "used only for private completeness validation"
        ),
        complete=True,
        account_scope=scope,
        numeric_closure_is_not_sole_admission_rule=True,
        public_fact_ids=[fact["fact_id"] for fact in facts[:-1]],
        leaf_fact_ids=[fact["fact_id"] for fact in facts],
        private_validation_only_fact_ids=[components[4]["fact_id"]],
        source_citations=[citation],
        witnesses=[e, m],
    )
