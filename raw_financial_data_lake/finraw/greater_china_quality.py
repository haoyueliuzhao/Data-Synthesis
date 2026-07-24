from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.quality import QualityGateError


DISCLOSURE_SOURCES = {
    "cninfo_announcements": "cninfo_pdf_announcement",
    "bse_disclosures": "bse_pdf_announcement",
    "hkex_disclosures": "hkex_pdf_annual_report",
}
DEFAULT_CORE_METRICS = [
    "revenue",
    "net_income",
    "total_assets",
    "total_liabilities",
    "net_cash_provided_by_used_in_operating_activities",
]
FINANCIAL_INDUSTRY_KEYWORDS = {
    "金融",
    "银行",
    "保险",
    "证券",
    "bank",
    "banking",
    "insurance",
    "financial services",
    "securities",
    "brokerage",
}


def _metric_coverage_profiles(
    contract: dict[str, Any], core_metrics: list[str]
) -> list[dict[str, Any]]:
    configured = contract.get("metric_coverage_profiles") or []
    if configured:
        profiles = [dict(item) for item in configured]
    else:
        profiles = [
            {
                "profile_id": "legacy_all_core_metrics",
                "is_default": True,
                "applicable_metric_ids": list(core_metrics),
                "required_metric_groups": [
                    {
                        "group_id": "all_core_metrics",
                        "metric_ids": list(core_metrics),
                        "minimum_metric_count": len(core_metrics),
                    }
                ],
                "minimum_covered_metric_count": len(core_metrics),
            }
        ]
    identifiers = [str(item.get("profile_id") or "") for item in profiles]
    if not all(identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("Metric coverage profile IDs must be non-empty and unique")
    default_id = str(contract.get("default_metric_coverage_profile_id") or "")
    if default_id and default_id not in identifiers:
        raise ValueError(
            f"Unknown default_metric_coverage_profile_id: {default_id}"
        )
    if not default_id:
        defaults = [
            item for item in profiles if bool(item.get("is_default"))
        ]
        if len(defaults) != 1:
            raise ValueError(
                "Exactly one metric coverage profile must be marked is_default"
            )
    return profiles


def _select_metric_coverage_profile(
    company_key: str,
    company: dict[str, Any],
    profiles: list[dict[str, Any]],
    default_profile_id: str | None = None,
) -> tuple[dict[str, Any], str]:
    for profile in profiles:
        match = profile.get("match") or {}
        company_keys = {str(value) for value in match.get("company_keys", [])}
        if company_key in company_keys:
            return profile, "manual_override_profile"
    detected_profile_id = str(
        company.get("statement_schema_detected_profile_id") or ""
    )
    if detected_profile_id:
        for profile in profiles:
            if str(profile.get("profile_id")) == detected_profile_id:
                return profile, "statement_schema_detected_profile"
        raise ValueError(
            "Unknown statement-schema detected profile: "
            + detected_profile_id
        )
    for profile in profiles:
        match = profile.get("match") or {}
        if _profile_matches_industry_ontology(company, match):
            return profile, "industry_ontology_profile"
    for profile in profiles:
        match = profile.get("match") or {}
        if (
            match
            and not _has_industry_profile_match(match)
            and _profile_matches_company(company, match)
        ):
            return profile, "profile_match"
    selected_default = str(default_profile_id or "")
    for profile in profiles:
        if (
            selected_default
            and str(profile.get("profile_id")) == selected_default
        ) or (not selected_default and bool(profile.get("is_default"))):
            return profile, "default_profile"
    raise ValueError("No default metric coverage profile is available")


def _profile_matches_company(
    company: dict[str, Any], match: dict[str, Any]
) -> bool:
    supported_fields = {
        "company_keys",
        "source_ids",
        "source_codes",
        "exchanges",
        "industry_contains_any",
        "industry_ontology_ids",
        "statement_schema_profile_ids",
    }
    unknown_fields = set(match) - supported_fields
    if unknown_fields:
        raise ValueError(
            "Unknown metric coverage profile match fields: "
            + ", ".join(sorted(unknown_fields))
        )
    effective_match = {
        key: value for key, value in match.items() if key != "company_keys"
    }
    if not effective_match:
        return False
    exact_fields = {
        "source_ids": "source_id",
        "source_codes": "source_code",
        "exchanges": "exchange",
    }
    for config_field, company_field in exact_fields.items():
        allowed = {str(value) for value in match.get(config_field, [])}
        if allowed and str(company.get(company_field) or "") not in allowed:
            return False
    fragments = [
        str(value).casefold()
        for value in match.get("industry_contains_any", [])
        if str(value)
    ]
    if fragments:
        industry = str(company.get("industry") or "").casefold()
        if not any(fragment in industry for fragment in fragments):
            return False
    allowed_industry_ids = {
        str(value) for value in match.get("industry_ontology_ids", [])
    }
    company_industry_ids = {
        str(value) for value in company.get("industry_ontology_ids", [])
    }
    if allowed_industry_ids and not (
        allowed_industry_ids & company_industry_ids
    ):
        return False
    allowed_schema_profiles = {
        str(value) for value in match.get("statement_schema_profile_ids", [])
    }
    if allowed_schema_profiles and str(
        company.get("statement_schema_detected_profile_id") or ""
    ) not in allowed_schema_profiles:
        return False
    return True


def _has_industry_profile_match(match: dict[str, Any]) -> bool:
    return bool(
        match.get("industry_ontology_ids")
        or match.get("industry_contains_any")
    )


def _profile_matches_industry_ontology(
    company: dict[str, Any], match: dict[str, Any]
) -> bool:
    if not _has_industry_profile_match(match):
        return False
    return _profile_matches_company(company, match)


def _industry_ontology_ids(company: dict[str, Any]) -> set[str]:
    industry = str(company.get("industry") or "").casefold()
    identifiers = {
        str(value)
        for value in company.get("industry_ontology_ids", [])
        if str(value)
    }
    if any(keyword in industry for keyword in FINANCIAL_INDUSTRY_KEYWORDS):
        identifiers.add("financial_institution")
    return identifiers


def _detect_statement_schema_profile(
    company: dict[str, Any],
    profiles: list[dict[str, Any]],
    candidate_item: dict[str, Any],
    fact_item: dict[str, Any],
) -> str | None:
    fact_metric_ids = {
        str(metric_id)
        for metric_id, years in fact_item.get("metric_years", {}).items()
        if years
    }
    candidate_metric_ids: set[str] = set()
    for metric_ids in candidate_item.get(
        "verified_metric_ids_by_raw_object", {}
    ).values():
        candidate_metric_ids.update(str(value) for value in metric_ids)
    available_metric_ids = fact_metric_ids | candidate_metric_ids
    statement_types = {
        str(value)
        for value in candidate_item.get(
            "verified_statement_raw_object_ids", {}
        )
    }
    matches = []
    for profile in profiles:
        detection = profile.get("statement_schema_detection") or {}
        if detection and _statement_schema_detection_matches(
            company,
            detection,
            available_metric_ids,
            statement_types,
        ):
            matches.append(str(profile["profile_id"]))
    if len(matches) > 1:
        raise ValueError(
            "Ambiguous statement schema profile detection: "
            + ", ".join(matches)
        )
    return matches[0] if matches else None


def _statement_schema_detection_matches(
    company: dict[str, Any],
    detection: dict[str, Any],
    available_metric_ids: set[str],
    statement_types: set[str],
) -> bool:
    supported_fields = {
        "source_ids",
        "exchanges",
        "required_any_metric_ids",
        "required_all_metric_ids",
        "absent_metric_ids",
        "required_statement_types",
    }
    unknown_fields = set(detection) - supported_fields
    if unknown_fields:
        raise ValueError(
            "Unknown statement schema detection fields: "
            + ", ".join(sorted(unknown_fields))
        )
    for config_field, company_field in (
        ("source_ids", "source_id"),
        ("exchanges", "exchange"),
    ):
        allowed = {str(value) for value in detection.get(config_field, [])}
        if allowed and str(company.get(company_field) or "") not in allowed:
            return False
    required_any = {
        str(value) for value in detection.get("required_any_metric_ids", [])
    }
    if required_any and not (required_any & available_metric_ids):
        return False
    required_all = {
        str(value) for value in detection.get("required_all_metric_ids", [])
    }
    if not required_all.issubset(available_metric_ids):
        return False
    absent = {
        str(value) for value in detection.get("absent_metric_ids", [])
    }
    if absent & available_metric_ids:
        return False
    required_statements = {
        str(value) for value in detection.get("required_statement_types", [])
    }
    return required_statements.issubset(statement_types)


def _default_profile_review_risk(company: dict[str, Any]) -> bool:
    if str(company.get("exchange") or "") == "HKEX":
        return True
    if "financial_institution" in _industry_ontology_ids(company):
        return True
    name = str(company.get("company_name") or "").casefold()
    return any(
        keyword in name
        for keyword in {"银行", "保险", "bank", "insurance"}
    )


def _evaluate_metric_coverage_profile(
    profile: dict[str, Any],
    fact_item: dict[str, Any],
    *,
    default_minimum_years: int,
    all_profile_metric_ids: set[str],
) -> dict[str, Any]:
    groups = [dict(item) for item in profile.get("required_metric_groups", [])]
    applicable = {
        str(value) for value in profile.get("applicable_metric_ids", [])
    }
    for group in groups:
        applicable.update(str(value) for value in group.get("metric_ids", []))
    if not applicable:
        raise ValueError(
            f"Metric coverage profile {profile['profile_id']} has no applicable metrics"
        )
    minimum_years = int(
        profile.get("minimum_metric_years", default_minimum_years)
    )
    metric_years = {
        metric_id: sorted(
            fact_item.get("metric_years", {}).get(metric_id, set())
        )
        for metric_id in sorted(applicable)
    }
    covered = {
        metric_id
        for metric_id, years in metric_years.items()
        if len(years) >= minimum_years
    }
    group_results = []
    for group in groups:
        metric_ids = [str(value) for value in group.get("metric_ids", [])]
        required_count = int(
            group.get("minimum_metric_count", len(metric_ids))
        )
        covered_ids = sorted(set(metric_ids) & covered)
        group_results.append(
            {
                "group_id": str(group.get("group_id") or "unnamed"),
                "metric_ids": metric_ids,
                "minimum_metric_count": required_count,
                "covered_metric_ids": covered_ids,
                "passed": len(covered_ids) >= required_count,
            }
        )
    minimum_covered = int(
        profile.get(
            "minimum_covered_metric_count",
            len(applicable) if not groups else 0,
        )
    )
    passed = all(row["passed"] for row in group_results) and (
        len(covered) >= minimum_covered
    )
    return {
        "metric_coverage_profile_id": str(profile["profile_id"]),
        "profile_description": str(profile.get("description") or ""),
        "minimum_metric_years": minimum_years,
        "applicable_core_metric_ids": sorted(applicable),
        "not_applicable_core_metric_ids": sorted(
            all_profile_metric_ids - applicable
        ),
        "core_metric_years": metric_years,
        "covered_core_metric_ids": sorted(covered),
        "missing_core_metrics": sorted(applicable - covered),
        "required_metric_groups": group_results,
        "minimum_covered_metric_count": minimum_covered,
        "core_metric_coverage_passed": passed,
    }


def _document_metric_extraction_complete(
    profile: dict[str, Any], metric_ids: set[str]
) -> bool:
    groups = [dict(item) for item in profile.get("required_metric_groups", [])]
    applicable = {
        str(value) for value in profile.get("applicable_metric_ids", [])
    }
    for group in groups:
        group_metric_ids = {
            str(value) for value in group.get("metric_ids", [])
        }
        required_count = int(
            group.get("minimum_metric_count", len(group_metric_ids))
        )
        if len(metric_ids & group_metric_ids) < required_count:
            return False
        applicable.update(group_metric_ids)
    if not applicable:
        raise ValueError(
            f"Metric coverage profile {profile['profile_id']} has no applicable metrics"
        )
    minimum_covered = int(
        profile.get(
            "minimum_covered_metric_count",
            len(applicable) if not groups else 0,
        )
    )
    return len(metric_ids & applicable) >= minimum_covered


def enforce_greater_china_quality_gates(
    db: DBProtocol,
    config: dict[str, Any],
    output_dir: str | None = None,
) -> dict[str, Any]:
    expansion = config.get("greater_china_expansion", {})
    contract = expansion.get("coverage_contract", {})
    expected = _expected_companies(config)
    aliases = _load_entity_aliases(db)
    raw = _load_raw_annual_coverage(db, expected)
    candidates = _load_candidate_coverage(db)
    facts = _load_fact_coverage(db)
    official = _official_publication_coverage(db, config, contract)

    minimum_annual_years = int(
        contract.get("minimum_annual_years_per_company", 5)
    )
    minimum_metric_years = int(
        contract.get("minimum_core_metric_years_per_company", 5)
    )
    core_metrics = [
        str(metric_id)
        for metric_id in contract.get("core_metric_ids", DEFAULT_CORE_METRICS)
    ]
    coverage_profiles = _metric_coverage_profiles(contract, core_metrics)
    all_profile_metric_ids = set(core_metrics)
    for profile in coverage_profiles:
        all_profile_metric_ids.update(
            str(value) for value in profile.get("applicable_metric_ids", [])
        )
        for group in profile.get("required_metric_groups", []):
            all_profile_metric_ids.update(
                str(value) for value in group.get("metric_ids", [])
            )

    company_rows: list[dict[str, Any]] = []
    graph_ready_count = 0
    scoped_fact_count = 0
    documents_with_verified_fact_ids: set[str] = set()
    income_statement_verified_object_ids: set[str] = set()
    balance_sheet_verified_object_ids: set[str] = set()
    cash_flow_statement_verified_object_ids: set[str] = set()
    required_metric_complete_object_ids: set[str] = set()
    passed_raw_object_ids: set[str] = set()
    for key, company in sorted(expected.items()):
        source_id = company["source_id"]
        code = company["source_code"]
        entity_id = aliases.get(key)
        raw_item = raw.get(key, {})
        candidate_item = candidates.get(entity_id or "", {})
        fact_item = facts.get(entity_id or "", {})
        raw_years = sorted(raw_item.get("years", set()))
        expected_years = sorted(company.get("expected_years", set()))
        company_for_profile = dict(company)
        company_for_profile["industry_ontology_ids"] = sorted(
            _industry_ontology_ids(company)
        )
        detected_schema_profile_id = _detect_statement_schema_profile(
            company_for_profile,
            coverage_profiles,
            candidate_item,
            fact_item,
        )
        company_for_profile["statement_schema_detected_profile_id"] = (
            detected_schema_profile_id
        )
        profile, profile_match_reason = _select_metric_coverage_profile(
            key,
            company_for_profile,
            coverage_profiles,
            str(contract.get("default_metric_coverage_profile_id") or ""),
        )
        metric_coverage = _evaluate_metric_coverage_profile(
            profile,
            fact_item,
            default_minimum_years=minimum_metric_years,
            all_profile_metric_ids=all_profile_metric_ids,
        )
        passed_objects = set(raw_item.get("raw_object_ids", set()))
        verified_objects = set(candidate_item.get("verified_raw_object_ids", set()))
        verified_statement_objects = candidate_item.get(
            "verified_statement_raw_object_ids", {}
        )
        income_objects = passed_objects & set(
            verified_statement_objects.get("income_statement", set())
        )
        balance_objects = passed_objects & set(
            verified_statement_objects.get("balance_sheet", set())
        )
        cash_flow_objects = passed_objects & (
            set(verified_statement_objects.get("cash_flow", set()))
            | set(
                verified_statement_objects.get(
                    "cash_flow_statement", set()
                )
            )
        )
        verified_metrics_by_object = candidate_item.get(
            "verified_metric_ids_by_raw_object", {}
        )
        required_complete_objects = {
            raw_object_id
            for raw_object_id in passed_objects
            if _document_metric_extraction_complete(
                profile,
                set(verified_metrics_by_object.get(raw_object_id, set())),
            )
        }
        passed_raw_object_ids.update(passed_objects)
        documents_with_verified_fact_ids.update(passed_objects & verified_objects)
        income_statement_verified_object_ids.update(income_objects)
        balance_sheet_verified_object_ids.update(balance_objects)
        cash_flow_statement_verified_object_ids.update(cash_flow_objects)
        required_metric_complete_object_ids.update(required_complete_objects)
        entity_fact_count = int(fact_item.get("fact_count", 0))
        entity_ready_count = int(fact_item.get("graph_ready_count", 0))
        scoped_fact_count += entity_fact_count
        graph_ready_count += entity_ready_count
        company_rows.append(
            {
                "company_key": key,
                "source_id": source_id,
                "source_code": code,
                "company_name": company.get("company_name"),
                "exchange": company.get("exchange"),
                "industry": company.get("industry"),
                "industry_ontology_ids": company_for_profile[
                    "industry_ontology_ids"
                ],
                "statement_schema_detected_profile_id": (
                    detected_schema_profile_id
                ),
                "entity_id": entity_id,
                "expected_annual_years": expected_years,
                "raw_annual_years": raw_years,
                "raw_annual_year_count": len(raw_years),
                "raw_annual_coverage_passed": len(raw_years) >= minimum_annual_years,
                "passed_raw_object_count": len(passed_objects),
                "document_with_verified_fact_count": len(
                    passed_objects & verified_objects
                ),
                "income_statement_verified_document_count": len(
                    income_objects
                ),
                "balance_sheet_verified_document_count": len(balance_objects),
                "cash_flow_statement_verified_document_count": len(
                    cash_flow_objects
                ),
                "required_metric_extraction_complete_document_count": len(
                    required_complete_objects
                ),
                "candidate_count": int(candidate_item.get("candidate_count", 0)),
                "approved_or_promoted_candidate_count": int(
                    candidate_item.get("approved_or_promoted_count", 0)
                ),
                **metric_coverage,
                "metric_coverage_profile_match_reason": profile_match_reason,
                "default_profile_review_risk": (
                    profile_match_reason == "default_profile"
                    and _default_profile_review_risk(company_for_profile)
                ),
                "core_metric_coverage_passed": bool(entity_id)
                and bool(metric_coverage["core_metric_coverage_passed"]),
                "standardized_fact_count": entity_fact_count,
                "graph_ready_fact_count": entity_ready_count,
                "graph_ready_ratio": _ratio(
                    entity_ready_count, entity_fact_count
                ),
            }
        )

    source_rows = _source_summary(company_rows)
    a_share_rows = [
        row for row in company_rows if row["exchange"] in {"SSE", "SZSE", "BSE"}
    ]
    hkex_rows = [row for row in company_rows if row["exchange"] == "HKEX"]
    document_with_verified_fact_ratio = _ratio(
        len(documents_with_verified_fact_ids), len(passed_raw_object_ids)
    )
    income_statement_verified_ratio = _ratio(
        len(income_statement_verified_object_ids), len(passed_raw_object_ids)
    )
    balance_sheet_verified_ratio = _ratio(
        len(balance_sheet_verified_object_ids), len(passed_raw_object_ids)
    )
    cash_flow_statement_verified_ratio = _ratio(
        len(cash_flow_statement_verified_object_ids), len(passed_raw_object_ids)
    )
    required_metric_extraction_complete_ratio = _ratio(
        len(required_metric_complete_object_ids), len(passed_raw_object_ids)
    )
    graph_ready_ratio = _ratio(graph_ready_count, scoped_fact_count)
    covered_company_count = sum(
        bool(row["core_metric_coverage_passed"]) for row in company_rows
    )
    metric_profile_coverage_ratio = _ratio(
        covered_company_count, len(company_rows)
    )
    profile_match_reason_counts = Counter(
        str(row["metric_coverage_profile_match_reason"])
        for row in company_rows
    )
    default_profile_rows = [
        row
        for row in company_rows
        if row["metric_coverage_profile_match_reason"] == "default_profile"
    ]
    default_profile_review_risk_rows = [
        row for row in default_profile_rows if row["default_profile_review_risk"]
    ]
    report: dict[str, Any] = {
        "contract": {
            "minimum_annual_years_per_company": minimum_annual_years,
            "minimum_core_metric_years_per_company": minimum_metric_years,
            "core_metric_ids": core_metrics,
            "metric_coverage_profiles": coverage_profiles,
            "default_metric_coverage_profile_id": str(
                contract.get("default_metric_coverage_profile_id") or ""
            ),
            "minimum_company_metric_profile_pass_ratio": float(
                contract.get("minimum_company_metric_profile_pass_ratio", 1.0)
            ),
            "target_company_metric_profile_pass_ratio": float(
                contract.get("target_company_metric_profile_pass_ratio", 1.0)
            ),
            "minimum_graph_ready_ratio": float(
                contract.get("minimum_graph_ready_ratio", 0.9)
            ),
            "minimum_document_with_verified_fact_ratio": float(
                contract.get(
                    "minimum_document_with_verified_fact_ratio",
                    0.9,
                )
            ),
            "minimum_required_metric_extraction_complete_ratio": float(
                contract.get(
                    "minimum_required_metric_extraction_complete_ratio", 0.9
                )
            ),
            "minimum_a_share_companies": int(
                contract.get("minimum_a_share_companies", 100)
            ),
            "minimum_hkex_companies": int(
                contract.get("minimum_hkex_companies", 40)
            ),
            "required_a_share_exchanges": list(
                contract.get("required_a_share_exchanges", ["SSE", "SZSE", "BSE"])
            ),
            "required_official_publication_sources": list(
                contract.get("required_official_publication_sources", [])
            ),
        },
        "regional_scope": {
            "benchmark_market": "greater_china",
            "internal_region_scope": "mainland_hong_kong_macau",
            "taiwan_policy": (
                "excluded_until_authoritative_source_and_entity_contract_are_available"
            ),
        },
        "configured_company_count": len(company_rows),
        "configured_a_share_company_count": len(a_share_rows),
        "configured_hkex_company_count": len(hkex_rows),
        "raw_annual_covered_company_count": sum(
            bool(row["raw_annual_coverage_passed"]) for row in company_rows
        ),
        "raw_annual_covered_a_share_company_count": sum(
            bool(row["raw_annual_coverage_passed"]) for row in a_share_rows
        ),
        "raw_annual_covered_hkex_company_count": sum(
            bool(row["raw_annual_coverage_passed"]) for row in hkex_rows
        ),
        "passed_annual_raw_object_count": len(passed_raw_object_ids),
        "document_with_verified_fact_count": len(
            documents_with_verified_fact_ids
        ),
        "document_with_verified_fact_ratio": document_with_verified_fact_ratio,
        "income_statement_verified_document_count": len(
            income_statement_verified_object_ids
        ),
        "income_statement_verified_ratio": income_statement_verified_ratio,
        "balance_sheet_verified_document_count": len(
            balance_sheet_verified_object_ids
        ),
        "balance_sheet_verified_ratio": balance_sheet_verified_ratio,
        "cash_flow_statement_verified_document_count": len(
            cash_flow_statement_verified_object_ids
        ),
        "cash_flow_statement_verified_ratio": (
            cash_flow_statement_verified_ratio
        ),
        "required_metric_extraction_complete_document_count": len(
            required_metric_complete_object_ids
        ),
        "required_metric_extraction_complete_ratio": (
            required_metric_extraction_complete_ratio
        ),
        "statement_verification_ratio_semantics": (
            "A document counts when it contributes at least one verified and "
            "approved/promoted fact from that statement type."
        ),
        "document_coverage_denominator_definition": (
            "Passed annual-report raw objects in the configured Mainland, "
            "Hong Kong and Macau company scope."
        ),
        "core_metric_covered_company_count": covered_company_count,
        "metric_profile_covered_company_ratio": metric_profile_coverage_ratio,
        "metric_profile_target_gap_company_count": max(
            0, len(company_rows) - covered_company_count
        ),
        "profile_match_reason_counts": dict(
            sorted(profile_match_reason_counts.items())
        ),
        "default_profile_company_count": len(default_profile_rows),
        "default_profile_company_keys": [
            row["company_key"] for row in default_profile_rows
        ],
        "default_profile_review_risk_company_count": len(
            default_profile_review_risk_rows
        ),
        "default_profile_review_risk_company_keys": [
            row["company_key"] for row in default_profile_review_risk_rows
        ],
        "scoped_standardized_fact_count": scoped_fact_count,
        "scoped_graph_ready_fact_count": graph_ready_count,
        "scoped_graph_ready_ratio": graph_ready_ratio,
        "source_summary": source_rows,
        "official_publication_coverage": official,
        "company_coverage": company_rows,
    }
    failures = _quality_failures(report)
    report["greater_china_quality_gate_failures"] = failures
    report["greater_china_quality_gate_status"] = "failed" if failures else "passed"
    if output_dir:
        report["written_files"] = [
            str(path) for path in write_greater_china_quality_report(report, output_dir)
        ]
    if failures and contract.get("raise_on_failure", True):
        raise QualityGateError("; ".join(failures))
    return report


def _expected_companies(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    companies: dict[str, dict[str, Any]] = {}
    source_specs = (
        ("cninfo", "cninfo_announcements", None),
        ("bse", "bse_disclosures", "BSE"),
    )
    for config_key, source_id, forced_exchange in source_specs:
        for item in config.get(config_key, {}).get("stock_pool", []):
            code = _normalize_code(source_id, item.get("stock_code"))
            if not code:
                continue
            exchange = forced_exchange or str(item.get("market") or "")
            key = _company_key(source_id, code)
            companies[key] = {
                "source_id": source_id,
                "source_code": code,
                "company_name": item.get("company_name") or item.get("legal_name"),
                "exchange": exchange,
                    "industry": item.get("industry"),
                    "expected_years": set(),
                    "expected_urls": set(),
            }

    manifests = (
        ("cninfo", "cninfo_announcements"),
        ("bse", "bse_disclosures"),
        ("hkex", "hkex_disclosures"),
    )
    for config_key, source_id in manifests:
        for item in config.get(config_key, {}).get("announcements", []):
            code = _normalize_code(source_id, item.get("stock_code"))
            if not code:
                continue
            key = _company_key(source_id, code)
            if key not in companies:
                pool = item.get("pool_metadata") or {}
                companies[key] = {
                    "source_id": source_id,
                    "source_code": code,
                    "company_name": item.get("company_name")
                    or pool.get("company_name"),
                    "exchange": "HKEX"
                    if source_id == "hkex_disclosures"
                    else item.get("market") or pool.get("market"),
                    "industry": pool.get("industry"),
                    "expected_years": set(),
                    "expected_urls": set(),
                }
            year = _year(item.get("year") or item.get("period_hint"))
            if year is not None:
                companies[key]["expected_years"].add(year)
            if item.get("url"):
                companies[key]["expected_urls"].add(str(item["url"]))
    return companies


def _load_entity_aliases(db: DBProtocol) -> dict[str, str]:
    rows = db.fetchall(
        "SELECT eam.source_id, eam.source_code, eam.entity_id "
        "FROM entity_alias_map eam "
        "JOIN canonical_entities ce ON ce.entity_id = eam.entity_id "
        "WHERE eam.source_id IN (?, ?, ?) "
        "AND COALESCE(eam.is_active, 1) = 1 "
        "AND COALESCE(ce.is_active, 1) = 1 "
        "ORDER BY eam.source_id, eam.source_code, eam.entity_id",
        tuple(DISCLOSURE_SOURCES),
    )
    aliases: dict[str, str] = {}
    for row in rows:
        source_id = str(row["source_id"])
        code = _normalize_code(source_id, row["source_code"])
        if code and row["entity_id"]:
            key = _company_key(source_id, code)
            entity_id = str(row["entity_id"])
            existing = aliases.get(key)
            if existing is not None and existing != entity_id:
                raise QualityGateError(
                    "ambiguous_active_entity_alias="
                    f"{key}:{existing},{entity_id}"
                )
            aliases[key] = entity_id
    return aliases


def _load_raw_annual_coverage(
    db: DBProtocol,
    expected: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    rows = db.fetchall(
        "SELECT rr.source_id, rr.entity_hint, rr.period_hint, rr.raw_object_id, "
        "ro.original_url, ro.retrieval_time "
        "FROM raw_records rr JOIN raw_objects ro "
        "ON ro.raw_object_id = rr.raw_object_id "
        "WHERE rr.record_type IN (?, ?, ?) "
        "AND ro.validation_status = 'passed'",
        tuple(DISCLOSURE_SOURCES.values()),
    )
    selected: dict[str, dict[str, Any]] = {}
    for raw_row in rows:
        row = dict(raw_row)
        source_id = str(row["source_id"])
        code = _normalize_code(source_id, row["entity_hint"])
        if not code:
            continue
        key = _company_key(source_id, code)
        expected_urls = expected.get(key, {}).get("expected_urls", set())
        base_url = _base_url(row["original_url"])
        if expected_urls and base_url not in expected_urls:
            continue
        identity = f"{key}|{base_url}" if base_url else str(row["raw_object_id"])
        previous = selected.get(identity)
        current_rank = (
            str(row.get("retrieval_time") or ""),
            str(row.get("raw_object_id") or ""),
        )
        previous_rank = (
            str(previous.get("retrieval_time") or ""),
            str(previous.get("raw_object_id") or ""),
        ) if previous else ("", "")
        if previous is None or current_rank > previous_rank:
            selected[identity] = row

    coverage: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"years": set(), "raw_object_ids": set()}
    )
    for row in selected.values():
        source_id = str(row["source_id"])
        code = _normalize_code(source_id, row["entity_hint"])
        key = _company_key(source_id, code)
        item = coverage[key]
        year = _year(row["period_hint"])
        if year is not None:
            item["years"].add(year)
        if row["raw_object_id"]:
            item["raw_object_ids"].add(str(row["raw_object_id"]))
    return dict(coverage)


def _load_candidate_coverage(db: DBProtocol) -> dict[str, dict[str, Any]]:
    rows = db.fetchall(
        "SELECT cf.entity_id, cf.raw_object_id, cf.candidate_state, "
        "cf.promotion_status, cf.evidence_status, cf.statement_type, "
        "cf.matched_metric_id "
        "FROM candidate_facts cf JOIN raw_objects ro "
        "ON ro.raw_object_id = cf.raw_object_id "
        "WHERE COALESCE(cf.is_active, 1) = 1 "
        "AND ro.source_id IN (?, ?, ?)",
        tuple(DISCLOSURE_SOURCES),
    )
    coverage: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "candidate_count": 0,
            "approved_or_promoted_count": 0,
            "verified_raw_object_ids": set(),
            "verified_statement_raw_object_ids": defaultdict(set),
            "verified_metric_ids_by_raw_object": defaultdict(set),
        }
    )
    approved = {"approved_for_atomic_fact", "promoted"}
    for row in rows:
        entity_id = str(row["entity_id"] or "")
        if not entity_id:
            continue
        item = coverage[entity_id]
        item["candidate_count"] += 1
        if row["promotion_status"] in approved:
            item["approved_or_promoted_count"] += 1
        if (
            row["evidence_status"] == "verified"
            and row["promotion_status"] in approved
            and row["raw_object_id"]
        ):
            raw_object_id = str(row["raw_object_id"])
            item["verified_raw_object_ids"].add(raw_object_id)
            statement_type = str(row["statement_type"] or "")
            if statement_type:
                item["verified_statement_raw_object_ids"][
                    statement_type
                ].add(raw_object_id)
            metric_id = str(row["matched_metric_id"] or "")
            if metric_id:
                item["verified_metric_ids_by_raw_object"][raw_object_id].add(
                    metric_id
                )
    return dict(coverage)


def _load_fact_coverage(db: DBProtocol) -> dict[str, dict[str, Any]]:
    rows = db.fetchall(
        "SELECT entity_id, metric_id, fiscal_year, period_end, graph_ready "
        "FROM standardized_facts "
        "WHERE COALESCE(is_active, 1) = 1 "
        "AND source_id IN (?, ?, ?)",
        tuple(DISCLOSURE_SOURCES),
    )
    coverage: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "fact_count": 0,
            "graph_ready_count": 0,
            "metric_years": defaultdict(set),
        }
    )
    for row in rows:
        entity_id = str(row["entity_id"] or "")
        metric_id = str(row["metric_id"] or "")
        if not entity_id or not metric_id:
            continue
        item = coverage[entity_id]
        item["fact_count"] += 1
        ready = bool(row["graph_ready"])
        if ready:
            item["graph_ready_count"] += 1
            year = _year(row["fiscal_year"] or row["period_end"])
            if year is not None:
                item["metric_years"][metric_id].add(year)
    return dict(coverage)


def _official_publication_coverage(
    db: DBProtocol,
    config: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    required_sources = [
        str(value)
        for value in contract.get("required_official_publication_sources", [])
    ]
    targets_by_source: dict[str, set[str]] = defaultdict(set)
    for target in config.get("official_publications", {}).get("targets", []):
        source_id = str(target.get("source_id") or "")
        url = str(target.get("url") or "")
        if source_id and url:
            targets_by_source[source_id].add(url)
    rows = db.fetchall(
        "SELECT source_id, original_url FROM raw_objects "
        "WHERE validation_status = 'passed' AND source_id IN ("
        + ",".join("?" for _ in required_sources)
        + ")",
        required_sources,
    ) if required_sources else []
    passed_by_source: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        passed_by_source[str(row["source_id"])].add(str(row["original_url"] or ""))
    report: dict[str, dict[str, Any]] = {}
    for source_id in required_sources:
        expected_urls = targets_by_source.get(source_id, set())
        passed_urls = passed_by_source.get(source_id, set())
        matched = expected_urls & passed_urls
        report[source_id] = {
            "expected_target_count": len(expected_urls),
            "passed_target_count": len(matched),
            "target_coverage_ratio": _ratio(len(matched), len(expected_urls)),
            "missing_urls": sorted(expected_urls - passed_urls),
        }
    return report


def _source_summary(company_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in company_rows:
        grouped[str(row["source_id"])].append(row)
    output = []
    for source_id, rows in sorted(grouped.items()):
        fact_count = sum(int(row["standardized_fact_count"]) for row in rows)
        ready_count = sum(int(row["graph_ready_fact_count"]) for row in rows)
        output.append(
            {
                "source_id": source_id,
                "configured_company_count": len(rows),
                "raw_annual_covered_company_count": sum(
                    bool(row["raw_annual_coverage_passed"]) for row in rows
                ),
                "core_metric_covered_company_count": sum(
                    bool(row["core_metric_coverage_passed"]) for row in rows
                ),
                "standardized_fact_count": fact_count,
                "graph_ready_fact_count": ready_count,
                "graph_ready_ratio": _ratio(ready_count, fact_count),
            }
        )
    return output


def _quality_failures(report: dict[str, Any]) -> list[str]:
    contract = report["contract"]
    rows = report["company_coverage"]
    failures: list[str] = []
    minimum_a_share = int(contract["minimum_a_share_companies"])
    minimum_hkex = int(contract["minimum_hkex_companies"])
    covered_a = int(report["raw_annual_covered_a_share_company_count"])
    covered_hk = int(report["raw_annual_covered_hkex_company_count"])
    if covered_a < minimum_a_share:
        failures.append(
            f"raw_annual_covered_a_share_company_count={covered_a} < {minimum_a_share}"
        )
    if covered_hk < minimum_hkex:
        failures.append(
            f"raw_annual_covered_hkex_company_count={covered_hk} < {minimum_hkex}"
        )
    missing_exchanges = []
    for exchange in contract["required_a_share_exchanges"]:
        expected_exchange = [row for row in rows if row["exchange"] == exchange]
        if not expected_exchange or not all(
            row["raw_annual_coverage_passed"] for row in expected_exchange
        ):
            missing_exchanges.append(exchange)
    if missing_exchanges:
        failures.append(
            "incomplete_required_a_share_exchanges=" + ",".join(missing_exchanges)
        )
    annual_failures = [
        row["company_key"] for row in rows if not row["raw_annual_coverage_passed"]
    ]
    if annual_failures:
        failures.append(
            f"company_annual_coverage_failures={len(annual_failures)} "
            f"examples={','.join(annual_failures[:10])}"
        )
    verified_ratio = float(report["document_with_verified_fact_ratio"])
    minimum_verified = float(
        contract["minimum_document_with_verified_fact_ratio"]
    )
    if verified_ratio < minimum_verified:
        failures.append(
            "document_with_verified_fact_ratio="
            f"{verified_ratio:.6f} < {minimum_verified:.6f}"
        )
    extraction_complete_ratio = float(
        report["required_metric_extraction_complete_ratio"]
    )
    minimum_extraction_complete = float(
        contract["minimum_required_metric_extraction_complete_ratio"]
    )
    if extraction_complete_ratio < minimum_extraction_complete:
        failures.append(
            "required_metric_extraction_complete_ratio="
            f"{extraction_complete_ratio:.6f} < "
            f"{minimum_extraction_complete:.6f}"
        )
    core_failures = [
        row["company_key"] for row in rows if not row["core_metric_coverage_passed"]
    ]
    metric_profile_ratio = float(
        report.get(
            "metric_profile_covered_company_ratio",
            _ratio(len(rows) - len(core_failures), len(rows)),
        )
    )
    minimum_metric_profile_ratio = float(
        contract.get("minimum_company_metric_profile_pass_ratio", 1.0)
    )
    if metric_profile_ratio < minimum_metric_profile_ratio:
        failures.append(
            "company_metric_profile_coverage_ratio="
            f"{metric_profile_ratio:.6f} < {minimum_metric_profile_ratio:.6f}; "
            f"company_core_metric_coverage_failures={len(core_failures)} "
            f"examples={','.join(core_failures[:10])}"
        )
    graph_ready_ratio = float(report["scoped_graph_ready_ratio"])
    minimum_ready = float(contract["minimum_graph_ready_ratio"])
    if graph_ready_ratio < minimum_ready:
        failures.append(
            f"scoped_graph_ready_ratio={graph_ready_ratio:.6f} < {minimum_ready:.6f}"
        )
    for source_id, item in report["official_publication_coverage"].items():
        expected = int(item["expected_target_count"])
        passed = int(item["passed_target_count"])
        if not expected or passed != expected:
            failures.append(
                f"official_publication_coverage[{source_id}]={passed}/{expected}"
            )
    return failures


def write_greater_china_quality_report(
    report: dict[str, Any], output_dir: str
) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "greater_china_quality_report.json"
    md_path = output / "greater_china_quality_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return [json_path, md_path]


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Greater China Quality Report",
        "",
        f"- status: {report['greater_china_quality_gate_status']}",
        "- benchmark_market: `greater_china`",
        "- internal_region_scope: `mainland_hong_kong_macau`",
        "- Taiwan: excluded pending authoritative sources and an entity contract",
        f"- configured companies: {report['configured_company_count']}",
        "- raw annual covered companies: "
        f"{report['raw_annual_covered_company_count']}",
        "- document with verified fact ratio: "
        f"{report['document_with_verified_fact_ratio']:.6f}",
        "- income statement verified ratio: "
        f"{report['income_statement_verified_ratio']:.6f}",
        "- balance sheet verified ratio: "
        f"{report['balance_sheet_verified_ratio']:.6f}",
        "- cash flow statement verified ratio: "
        f"{report['cash_flow_statement_verified_ratio']:.6f}",
        "- required metric extraction complete ratio: "
        f"{report['required_metric_extraction_complete_ratio']:.6f}",
        "- core metric covered companies: "
        f"{report['core_metric_covered_company_count']}",
        "- metric-profile covered company ratio: "
        f"{report['metric_profile_covered_company_ratio']:.6f}",
        "- metric-profile target gap companies: "
        f"{report['metric_profile_target_gap_company_count']}",
        "- profile match reasons: "
        + json.dumps(
            report["profile_match_reason_counts"],
            ensure_ascii=False,
            sort_keys=True,
        ),
        "- default-profile review risks: "
        f"{report['default_profile_review_risk_company_count']}",
        f"- scoped graph-ready ratio: {report['scoped_graph_ready_ratio']:.6f}",
        "",
        "## Failures",
        "",
    ]
    failures = report.get("greater_china_quality_gate_failures", [])
    lines.extend(f"- {failure}" for failure in failures)
    if not failures:
        lines.append("- none")
    lines.extend(["", "## Source Summary", ""])
    for row in report.get("source_summary", []):
        lines.append(
            f"- {row['source_id']}: raw companies "
            f"{row['raw_annual_covered_company_count']}/"
            f"{row['configured_company_count']}; core-metric companies "
            f"{row['core_metric_covered_company_count']}/"
            f"{row['configured_company_count']}; graph-ready "
            f"{row['graph_ready_ratio']:.6f}"
        )
    lines.extend(["", "## Official Publications", ""])
    for source_id, item in report.get("official_publication_coverage", {}).items():
        lines.append(
            f"- {source_id}: {item['passed_target_count']}/"
            f"{item['expected_target_count']}"
        )
    lines.extend(["", "## Incomplete Companies", ""])
    incomplete = [
        row
        for row in report.get("company_coverage", [])
        if not row["raw_annual_coverage_passed"]
        or not row["core_metric_coverage_passed"]
    ]
    for row in incomplete:
        lines.append(
            f"- {row['company_key']}: raw_years={row['raw_annual_year_count']}; "
            f"profile={row['metric_coverage_profile_id']}; "
            f"missing_core_metrics={','.join(row['missing_core_metrics']) or 'none'}; "
            "not_applicable="
            f"{','.join(row['not_applicable_core_metric_ids']) or 'none'}"
        )
    if not incomplete:
        lines.append("- none")
    lines.extend(["", "## Default Profile Review Risks", ""])
    risks = report.get("default_profile_review_risk_company_keys", [])
    lines.extend(f"- {company_key}" for company_key in risks)
    if not risks:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _normalize_code(source_id: str, value: Any) -> str:
    code = str(value or "").strip()
    if not code:
        return ""
    if source_id == "hkex_disclosures":
        return code.zfill(5)
    if source_id in {"cninfo_announcements", "bse_disclosures"}:
        return code.zfill(6)
    return code


def _company_key(source_id: str, source_code: str) -> str:
    return f"{source_id}:{source_code}"


def _base_url(value: Any) -> str:
    return str(value or "").partition("?")[0]


def _year(value: Any) -> int | None:
    text = str(value or "").strip()
    if len(text) < 4 or not text[:4].isdigit():
        return None
    year = int(text[:4])
    return year if 1900 <= year <= 2100 else None


def _ratio(numerator: Any, denominator: Any) -> float:
    denominator_value = int(denominator or 0)
    if not denominator_value:
        return 0.0
    return float(numerator or 0) / denominator_value
