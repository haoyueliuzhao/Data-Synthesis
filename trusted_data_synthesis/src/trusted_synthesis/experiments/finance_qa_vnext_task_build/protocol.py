"""Prospective bounded task-factory policy; no model generation is authorized here."""

import hashlib

from .archive import record, require

BASELINE = "459e6d66d11ca48244d61a4375e7092220ef47c6"
SPLIT_SALT = "basis_task_factory_sources_20260911.v1:"
METRIC_TAGS = {
    "gross_profit": ["GrossProfit"],
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "Revenues",
    ],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "cash_and_cash_equivalents": ["CashAndCashEquivalentsAtCarryingValue"],
    "cash_cash_equivalents_restricted_cash_and_restricted_cash_equivalents": [
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    ],
    "net_cash_provided_by_used_in_operating_activities": [
        "NetCashProvidedByUsedInOperatingActivities"
    ],
    "net_cash_provided_by_used_in_investing_activities": [
        "NetCashProvidedByUsedInInvestingActivities"
    ],
    "net_cash_provided_by_used_in_financing_activities": [
        "NetCashProvidedByUsedInFinancingActivities"
    ],
    "capital_expenditures": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "effect_of_exchange_rate_on_cash_and_cash_equivalents": [
        "EffectOfExchangeRateOnCashAndCashEquivalents"
    ],
    "effect_of_exchange_rate_on_cash_including_restricted": [
        "EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    ],
    "change_in_cash_including_exchange_rate_effect": [
        "CashAndCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect"
    ],
    "change_in_cash_including_restricted_and_exchange_rate_effect": [
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect"
    ],
}
CASH = "cash_and_cash_equivalents"
RESTRICTED = "cash_cash_equivalents_restricted_cash_and_restricted_cash_equivalents"
FLOW_METRICS = [
    "net_cash_provided_by_used_in_" + x + "_activities"
    for x in ("operating", "investing", "financing")
]
NEW_FLOW_METRICS = list(METRIC_TAGS)[-4:]
CAPS = {"annual_flow": 54, "stock_rollforward": 53, "company_defined_metric": 53, "control": 100}


def source_identity(entity):
    cik = str(entity.get("cik") or "")
    require(cik.isdigit() and len(cik) <= 10, "source.canonical_CIK_required")
    return "cik:" + cik.zfill(10)


def source_split(identity):
    bucket = int(hashlib.sha256((SPLIT_SALT + identity).encode()).hexdigest(), 16) % 55
    return "train" if bucket < 10 else "dev" if bucket < 19 else "confirm"


def policy():
    return record(
        "task_synthesis_protocol",
        baseline_commit=BASELINE,
        source_scope=(
            "pinned KG US companies; their existing SEC companyfacts and indexed 10-K bytes"
        ),
        source_split={
            "identity": "canonical 10-digit CIK",
            "salt": SPLIT_SALT,
            "buckets": 55,
            "train": [0, 9],
            "dev": [10, 18],
            "confirm": [19, 54],
            "new_split_not_inherited_from_FinQA": True,
        },
        allowed_current_use="train",
        all_leaf_usage_required=True,
        metrics_and_tag_priority=METRIC_TAGS,
        observation_end_years=[2010, 2025],
        observation_filter={
            "currency": "USD",
            "forms": ["10-K", "10-K/A"],
            "filing_fp": "FY",
            "duration_days_inclusive": [330, 380],
            "filing_fy_equals_observation_end_year": True,
        },
        observation_selection=(
            "per company/metric/actual period: first available registered tag; "
            "then latest filed/accession; never choose by numeric closure"
        ),
        source_occurrences=(
            "all original rows with same tag, unit, actual period and exact amount "
            "retained for common-accession relation checks"
        ),
        target_periods=(
            "explicit original observation dates; filing FY is never the public period contract"
        ),
        task_identity=(
            "entity source cluster + target metric/definition + actual two periods + quantity; "
            "no wording or route identity"
        ),
        relation_rules=[
            "US_GAAP_gross_profit_revenue_less_cost_v1",
            "US_GAAP_cash_flow_complete_bridge_v1",
            "issuer_full_signed_FCF_reconciliation_v1",
        ],
        quantities=["difference", "relative_change_when_previous_amount_positive"],
        issuer_table_policy={
            "source_scope": "only archived 10-K documents of the same fixed training CIKs",
            "observation_end_year_max": 2025,
            "document_period_metadata": (
                "native DEI value and same-accession filed date; archived dates remain diagnostics"
            ),
            "target": "reported issuer-defined free cash flow",
            "semantic_proof": (
                "explicit issuer definition plus complete signed table, "
                "same-filing native USD CFO anchor"
            ),
            "layout": (
                "one CFO anchor, one reported FCF total, 2..9 signed component rows, "
                "explicit annual date headers"
            ),
            "untagged_dashes": "unresolved; never silently replaced by zero",
            "selection": (
                "latest fully qualified source period, not necessarily latest available; "
                "all newer failures retained"
            ),
            "definition_change": "no mixing across compared periods",
            "source_cluster_count_not_multiplied_by_quantity_variants": True,
        },
        company_defined_metric_rule=(
            "requires an issuer-specific definition and independently reported two-period metric; "
            "generic GAAP gross profit is NOT this group"
        ),
        candidate_caps=CAPS,
        first_delivery={"dual": 12, "control": 8},
        enumeration=(
            "round-robin company CIK ascending, period ascending, target identity; "
            "group order stock, annual, defined; no score ranking"
        ),
        final_design={
            "per_dual_group": 40,
            "controls": 80,
            "target_total": 200,
            "ready_intersection_total_range": [180, 200],
            "final_task_selection_done": False,
        },
        actual_task_build_required=True,
        first_20_is_not_a_utility_experiment=True,
        public_export=(
            "question, native source records/definitions, physical quantity contract, "
            "common tools only"
        ),
        oracle_executions_are_Teacher_trajectories=False,
        new_task_LLM_calls=0,
        new_Teacher_sessions=0,
        new_Student_sessions=0,
        tokenizer_loading_allowed=False,
        GPU_allowed_in_this_stage=False,
        future_limits={
            "Teacher_sessions": 25280,
            "Teacher_requests": 808960,
            "cumulative_Teacher_input_output_tokens": 1000000000,
            "Student_dev_sessions": 1620,
            "Student_confirm_sessions": 8640,
        },
        future_materials_or_training_authorized_by_this_stage=False,
    )


def all_leaf_uses(leaf_ids, lineage, usage, expected="train"):
    """Expand every DerivedFact edge, including indirect and cyclic misuse."""
    visited, leaves = set(), set()

    def walk(identifier, active):
        require(identifier not in active, "usage.cyclic_lineage")
        if identifier in visited:
            return
        if identifier in lineage:
            require(bool(lineage[identifier]), "usage.empty_derived_lineage")
            for child in lineage[identifier]:
                walk(child, active | {identifier})
        else:
            require(identifier in usage, "usage.missing_leaf_authority")
            entry = usage[identifier]
            require(
                entry["split"] == expected and expected in entry["allowed_uses"],
                "usage.forbidden_leaf",
            )
            leaves.add(identifier)
        visited.add(identifier)

    for identifier in leaf_ids:
        walk(identifier, set())
    require(bool(leaves), "usage.nonempty_leaves")
    return sorted(leaves)
