from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from finraw.analysis.registry import stable_hash
from finraw.db.client import DBProtocol
from finraw.qa.comparability import annual_duration_valid, fact_frequency, financial_scope_key
from finraw.qa.store import json_value

PEER_SCOPE_ELIGIBILITY_POLICY_VERSION = "1.2.0"
PEER_CURRENT_METRICS = (
    "revenue",
    "net_income",
    "total_assets",
    "total_liabilities",
)


def peer_scope_policy(min_entities: int, max_entities: int) -> dict[str, Any]:
    return {
        "version": PEER_SCOPE_ELIGIBILITY_POLICY_VERSION,
        "entity_type": "company",
        "financial_scope_type": "consolidated_entity",
        "frequency": "annual",
        "fiscal_quarter": "FY",
        "forecast_allowed": False,
        "graph_ready_required": True,
        "current_metrics": list(PEER_CURRENT_METRICS),
        "previous_period_metrics": ["revenue"],
        "nonzero_denominator_slots": [
            "previous_revenue",
            "current_revenue",
            "total_assets",
        ],
        "same_source": True,
        "same_unit": True,
        "same_currency": True,
        "source_definition_required": True,
        "same_source_definition_compatibility_class": True,
        "same_source_definition_within_growth_window": True,
        "membership_precedence": ["sec_sic_major_group", "canonical_industry"],
        "min_entities": int(min_entities),
        "max_entities": int(max_entities),
    }


def peer_scope_policy_hash(min_entities: int, max_entities: int) -> str:
    return stable_hash(peer_scope_policy(min_entities, max_entities))


def build_peer_scope_contract(
    *,
    scope_type: str,
    scope_id: str,
    scope_name: str,
    fiscal_year: int,
    source_id: str,
    normalized_unit: str,
    normalized_currency: str,
    entity_ids: list[str],
    source_definition_compatibility: dict[str, list[str]],
    min_entities: int,
    max_entities: int,
) -> dict[str, Any]:
    policy_hash = peer_scope_policy_hash(min_entities, max_entities)
    contract = {
        "peer_scope_type": scope_type,
        "peer_scope_id": scope_id,
        "peer_scope_name": scope_name,
        "fiscal_year": int(fiscal_year),
        "source_id": source_id,
        "normalized_unit": normalized_unit,
        "normalized_currency": normalized_currency,
        "expected_scope_entity_ids": sorted(set(entity_ids)),
        "source_definition_compatibility": {
            str(metric_id): [str(value) for value in values]
            for metric_id, values in sorted(
                source_definition_compatibility.items()
            )
        },
        "scope_eligibility_policy_hash": policy_hash,
        "scope_eligibility_policy": peer_scope_policy(min_entities, max_entities),
    }
    contract["scope_membership_hash"] = scope_membership_hash(contract)
    return contract


def scope_membership_hash(contract: dict[str, Any]) -> str:
    return stable_hash(
        {
            "peer_scope_type": str(contract.get("peer_scope_type") or ""),
            "peer_scope_id": str(contract.get("peer_scope_id") or ""),
            "fiscal_year": int(contract.get("fiscal_year") or 0),
            "source_id": str(contract.get("source_id") or ""),
            "normalized_unit": str(contract.get("normalized_unit") or ""),
            "normalized_currency": str(contract.get("normalized_currency") or ""),
            "expected_scope_entity_ids": sorted(
                str(value)
                for value in contract.get("expected_scope_entity_ids") or []
            ),
            "source_definition_compatibility": dict(
                contract.get("source_definition_compatibility") or {}
            ),
            "scope_eligibility_policy_hash": str(
                contract.get("scope_eligibility_policy_hash") or ""
            ),
        }
    )


def recompute_peer_universe(
    db: DBProtocol,
    kg: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Rebuild the complete eligible peer universe from pinned data, without scan limits."""
    policy = dict(contract.get("scope_eligibility_policy") or {})
    min_entities = int(policy.get("min_entities") or 0)
    max_entities = int(policy.get("max_entities") or 0)
    expected_policy_hash = peer_scope_policy_hash(min_entities, max_entities)
    year = int(contract.get("fiscal_year") or 0)
    source_id = str(contract.get("source_id") or "")
    unit = str(contract.get("normalized_unit") or "")
    currency = str(contract.get("normalized_currency") or "")
    scope_type = str(contract.get("peer_scope_type") or "")
    scope_id = str(contract.get("peer_scope_id") or "")
    errors = []
    if str(contract.get("scope_eligibility_policy_hash") or "") != expected_policy_hash:
        errors.append("peer_scope_policy_hash_mismatch")
    if not all((year, source_id, unit, currency, scope_type, scope_id)):
        errors.append("peer_scope_contract_incomplete")

    placeholders = ",".join("?" for _ in PEER_CURRENT_METRICS)
    rows = db.fetchall(
        f"""
        SELECT sf.*, ce.canonical_name AS entity_name, ce.entity_type,
               ce.industry, ce.market, ce.country, ce.cik,
               smd.metric_id AS source_definition_metric_id,
               smd.comparable_to_metric_id AS source_definition_comparable_metric_id,
               smd.comparability_level AS source_definition_comparability_level,
               smd.frequency AS source_definition_frequency,
               smd.vintage_policy AS source_definition_vintage_policy
        FROM standardized_facts sf
        JOIN kg_nodes fact_node
          ON fact_node.kg_build_id = ? AND fact_node.node_type = 'Fact'
         AND fact_node.source_pk = sf.fact_id
        JOIN canonical_entities ce
          ON ce.build_id = ? AND ce.entity_id = sf.entity_id
        LEFT JOIN source_metric_definitions smd
          ON smd.definition_id = sf.source_definition_id
        WHERE sf.build_id = ? AND sf.source_id = ?
          AND sf.normalized_unit = ? AND sf.normalized_currency = ?
          AND sf.metric_id IN ({placeholders})
          AND sf.fiscal_year IN (?, ?)
          AND sf.graph_ready = 1 AND COALESCE(sf.is_forecast, 0) = 0
          AND sf.normalized_value IS NOT NULL
          AND UPPER(COALESCE(sf.fiscal_quarter, '')) = 'FY'
          AND ce.entity_type = 'company'
        ORDER BY sf.entity_id, sf.metric_id, sf.fiscal_year, sf.fact_id
        """,
        [
            kg["kg_build_id"],
            kg["input_entity_build_id"],
            kg["input_fact_build_id"],
            source_id,
            unit,
            currency,
            *PEER_CURRENT_METRICS,
            year - 1,
            year,
        ],
    )
    sic_groups = _load_sec_sic_major_groups(db)
    definition_contract = {
        str(metric_id): tuple(str(value) for value in values)
        for metric_id, values in dict(
            contract.get("source_definition_compatibility") or {}
        ).items()
    }
    slot_candidates: dict[
        str, dict[tuple[str, int], list[dict[str, Any]]]
    ] = defaultdict(lambda: defaultdict(list))
    rejection_counts: dict[str, int] = defaultdict(int)
    for raw_row in rows:
        row = dict(raw_row)
        if fact_frequency(row) != "annual" or not annual_duration_valid(row):
            rejection_counts["invalid_annual_period"] += 1
            continue
        entity_id = str(row.get("entity_id") or "")
        if financial_scope_key(row) != (entity_id, "consolidated_entity"):
            rejection_counts["nonconsolidated_financial_scope"] += 1
            continue
        if not str(row.get("source_definition_id") or ""):
            rejection_counts["missing_source_definition"] += 1
            continue
        metric_id = str(row.get("metric_id") or "")
        if source_definition_compatibility_class(row) != definition_contract.get(
            metric_id
        ):
            rejection_counts["incompatible_source_definition"] += 1
            continue
        membership = _peer_membership(row, sic_groups)
        if membership[:2] != (scope_type, scope_id):
            rejection_counts["outside_peer_scope"] += 1
            continue
        slot = (metric_id, int(row["fiscal_year"]))
        slot_candidates[entity_id][slot].append(row)

    slots = {
        entity_id: selected
        for entity_id, candidates in slot_candidates.items()
        if (selected := _select_peer_slots(candidates, year)) is not None
    }
    required_slots = {
        *((metric_id, year) for metric_id in PEER_CURRENT_METRICS),
        ("revenue", year - 1),
    }
    entity_ids = sorted(
        entity_id
        for entity_id, entity_slots in slots.items()
        if required_slots.issubset(entity_slots)
        and _peer_denominators_nonzero(entity_slots, year)
    )
    if not min_entities <= len(entity_ids) <= max_entities:
        errors.append("peer_scope_entity_count_outside_policy")
    recomputed_contract = dict(contract)
    recomputed_contract["expected_scope_entity_ids"] = entity_ids
    recomputed_contract["scope_eligibility_policy_hash"] = expected_policy_hash
    recomputed_hash = scope_membership_hash(recomputed_contract)
    slot_labels = {
        ("revenue", year): "current_revenue",
        ("revenue", year - 1): "previous_revenue",
        ("net_income", year): "net_income",
        ("total_assets", year): "total_assets",
        ("total_liabilities", year): "total_liabilities",
    }
    selected_fact_ids_by_entity = {
        entity_id: {
            label: str(slots[entity_id][slot]["fact_id"])
            for slot, label in slot_labels.items()
        }
        for entity_id in entity_ids
    }
    return {
        "entity_ids": entity_ids,
        "selected_fact_ids_by_entity": selected_fact_ids_by_entity,
        "scope_membership_hash": recomputed_hash,
        "scope_eligibility_policy_hash": expected_policy_hash,
        "eligible_entity_count": len(entity_ids),
        "candidate_entity_count": len(slot_candidates),
        "required_slots": sorted([list(value) for value in required_slots]),
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "errors": errors,
        "passed": not errors,
    }




def _select_peer_slots(
    candidates: dict[tuple[str, int], list[dict[str, Any]]],
    year: int,
) -> dict[tuple[str, int], dict[str, Any]] | None:
    current_revenue = candidates.get(("revenue", year), [])
    previous_revenue = candidates.get(("revenue", year - 1), [])
    current_by_definition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    previous_by_definition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in current_revenue:
        current_by_definition[str(row["source_definition_id"])].append(row)
    for row in previous_revenue:
        previous_by_definition[str(row["source_definition_id"])].append(row)
    common_definitions = sorted(
        set(current_by_definition) & set(previous_by_definition)
    )
    if not common_definitions:
        return None
    pairs = []
    for definition_id in common_definitions:
        current = max(current_by_definition[definition_id], key=_fact_score)
        previous = max(previous_by_definition[definition_id], key=_fact_score)
        pair_score = (
            min(_fact_score(current), _fact_score(previous)),
            max(_fact_score(current), _fact_score(previous)),
            definition_id,
        )
        pairs.append((pair_score, current, previous))
    _, current, previous = max(pairs, key=lambda item: item[0])
    selected = {
        ("revenue", year): current,
        ("revenue", year - 1): previous,
    }
    for metric_id in ("net_income", "total_assets", "total_liabilities"):
        rows = candidates.get((metric_id, year), [])
        if not rows:
            return None
        selected[(metric_id, year)] = max(rows, key=_fact_score)
    return selected


def _fact_score(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        1 if row.get("verification_status") == "cross_verified" else 0,
        float(row.get("confidence_score") or 0),
        str(row.get("report_date") or ""),
        str(row.get("fact_id") or ""),
    )


def _peer_denominators_nonzero(
    slots: dict[tuple[str, int], dict[str, Any]], year: int
) -> bool:
    try:
        values = (
            Decimal(str(slots[("revenue", year - 1)]["normalized_value"])),
            Decimal(str(slots[("revenue", year)]["normalized_value"])),
            Decimal(str(slots[("total_assets", year)]["normalized_value"])),
        )
    except (InvalidOperation, KeyError, TypeError, ValueError):
        return False
    return all(value.is_finite() and value != 0 for value in values)


def source_definition_compatibility_class(row: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("source_id") or ""),
        str(
            row.get("source_definition_comparable_metric_id")
            or row.get("source_definition_metric_id")
            or row.get("metric_id")
            or ""
        ),
        str(
            row.get("source_definition_comparability_level")
            or row.get("comparability_level")
            or ""
        ),
        str(
            row.get("source_definition_frequency")
            or row.get("frequency")
            or ""
        ),
        str(
            row.get("source_definition_vintage_policy")
            or row.get("vintage_policy")
            or ""
        ),
    )

def _load_sec_sic_major_groups(db: DBProtocol) -> dict[str, str]:
    rows = db.fetchall(
        "SELECT record_json FROM raw_records WHERE source_id = ? AND record_type = ?",
        ("sec_submissions", "sec_submissions_json"),
    )
    groups: dict[str, str] = {}
    for row in rows:
        payload = json_value(row.get("record_json"), {})
        cik = str(payload.get("cik") or "").strip()
        sic = str(payload.get("sic") or "").strip().zfill(4)
        if cik and len(sic) == 4 and sic.isdigit():
            groups[cik.zfill(10)] = sic[:2]
    return groups


def _peer_membership(
    row: dict[str, Any], sic_groups: dict[str, str]
) -> tuple[str, str, str]:
    cik = str(row.get("cik") or "").strip().zfill(10)
    sic_group = sic_groups.get(cik)
    if sic_group:
        return (
            "sec_sic_major_group",
            f"SEC_SIC_MAJOR_{sic_group}",
            f"SEC SIC major group {sic_group}",
        )
    industry = str(row.get("industry") or "").strip()
    return "canonical_industry", industry, industry
