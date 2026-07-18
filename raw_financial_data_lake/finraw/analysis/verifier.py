from __future__ import annotations

import re
from collections import Counter
from typing import Any

from finraw.analysis.signals import execute_signal, signal_result_hash
from finraw.db.client import DBProtocol
from finraw.qa.store import insert_rows, json_value

ANALYSIS_VERIFIER_VERSION = "1.0.0"
_FORBIDDEN_PATTERNS = {
    "investment_recommendation": re.compile(r"\b(?:buy|sell|hold recommendation|invest in)\b", re.I),
    "target_price": re.compile(r"\btarget price\b", re.I),
    "future_forecast": re.compile(r"\b(?:will|guaranteed|certain to|must rise|must fall)\b", re.I),
    "causal_claim": re.compile(r"\b(?:caused by|because management|proves that)\b", re.I),
}
_NUMERIC_PATTERN = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?%?")


def validate_analysis_samples(
    db: DBProtocol,
    analysis_build_id: str,
) -> dict[str, Any]:
    build = db.fetchone(
        "SELECT * FROM analysis_builds WHERE analysis_build_id = ?",
        (analysis_build_id,),
    )
    if not build:
        raise ValueError(f"Unknown analysis build: {analysis_build_id}")
    kg_build_id = str(build["kg_build_id"])
    candidates = {
        str(row["candidate_id"]): dict(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_candidates WHERE analysis_build_id = ?",
            (analysis_build_id,),
        )
    }
    bundles = {
        str(row["evidence_bundle_id"]): dict(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_evidence_bundles WHERE analysis_build_id = ?",
            (analysis_build_id,),
        )
    }
    plans = {
        str(row["claim_plan_id"]): dict(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_claim_plans WHERE analysis_build_id = ?",
            (analysis_build_id,),
        )
    }
    signals = [
        dict(row)
        for row in db.fetchall(
            "SELECT * FROM financial_signal_instances WHERE analysis_build_id = ?",
            (analysis_build_id,),
        )
    ]
    signals_by_id = {str(row["signal_id"]): row for row in signals}
    signal_checks = {
        str(row["signal_id"]): _validate_signal(db, row)
        for row in signals
    }
    samples = [
        dict(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_samples WHERE analysis_build_id = ? ORDER BY analysis_sample_id",
            (analysis_build_id,),
        )
    ]
    check_rows: list[dict[str, Any]] = []
    passed = 0
    failures: Counter[str] = Counter()
    for sample in samples:
        candidate = candidates[str(sample["candidate_id"])]
        bundle = bundles[str(candidate["evidence_bundle_id"])]
        plan = plans[str(candidate["claim_plan_id"])]
        results = _sample_checks(
            sample,
            candidate,
            bundle,
            plan,
            signals_by_id,
            signal_checks,
            kg_build_id,
        )
        sample_passed = all(value["passed"] for value in results.values())
        status = "passed" if sample_passed else "rejected"
        db.execute(
            "UPDATE analysis_samples SET validation_status = ? WHERE analysis_sample_id = ?",
            (status, sample["analysis_sample_id"]),
        )
        if sample_passed:
            passed += 1
        for name, result in results.items():
            if not result["passed"]:
                failures[name] += 1
            check_rows.append(
                {
                    "check_id": f"analysis_check_{sample['analysis_sample_id']}_{name}",
                    "analysis_sample_id": sample["analysis_sample_id"],
                    "analysis_build_id": analysis_build_id,
                    "check_name": name,
                    "check_status": "passed" if result["passed"] else "failed",
                    "observed_value": result["observed"],
                    "expected_value": result["expected"],
                    "message": result.get("message"),
                }
            )
    insert_rows(
        db,
        "analysis_quality_checks",
        check_rows,
        [
            "check_id",
            "analysis_sample_id",
            "analysis_build_id",
            "check_name",
            "check_status",
            "observed_value",
            "expected_value",
            "message",
        ],
        {"observed_value", "expected_value"},
    )
    total = len(samples)
    return {
        "analysis_build_id": analysis_build_id,
        "sample_count": total,
        "passed_count": passed,
        "rejected_count": total - passed,
        "pass_rate": passed / total if total else 0.0,
        "failure_counts": dict(sorted(failures.items())),
        "quality_status": "passed" if total and passed == total else "failed",
    }


def _validate_signal(db: DBProtocol, row: dict[str, Any]) -> dict[str, Any]:
    plan = json_value(row.get("operator_plan"), {})
    role_fact_ids = dict(plan.get("role_fact_ids") or {})
    all_ids = sorted(
        {
            str(fact_id)
            for fact_ids in role_fact_ids.values()
            for fact_id in fact_ids
        }
    )
    facts = _load_facts(db, all_ids)
    complete = len(facts) == len(all_ids)
    try:
        result = execute_signal(
            str(row["signal_spec_id"]),
            {
                role: [facts[str(fact_id)] for fact_id in fact_ids]
                for role, fact_ids in role_fact_ids.items()
                if all(str(fact_id) in facts for fact_id in fact_ids)
            },
            target_entity_id=plan.get("target_entity_id"),
        )
        recomputed = {
            "payload": result.payload,
            "direction": result.direction,
            "strength": result.strength,
        }
        expected = {
            "payload": json_value(row.get("signal_payload"), {}),
            "direction": row.get("direction"),
            "strength": row.get("strength"),
        }
        recompute_passed = complete and recomputed == expected
        expected_hash = signal_result_hash(
            str(row["signal_spec_id"]),
            all_ids,
            result.payload,
            result.direction,
            result.strength,
        )
        hash_passed = expected_hash == str(row.get("signal_hash"))
    except Exception as exc:
        recomputed = {"error": str(exc)}
        expected = {
            "payload": json_value(row.get("signal_payload"), {}),
            "direction": row.get("direction"),
            "strength": row.get("strength"),
        }
        recompute_passed = False
        hash_passed = False
    return {
        "input_complete": complete,
        "recompute_passed": recompute_passed,
        "hash_passed": hash_passed,
        "observed": recomputed,
        "expected": expected,
    }


def _sample_checks(
    sample: dict[str, Any],
    candidate: dict[str, Any],
    bundle: dict[str, Any],
    plan: dict[str, Any],
    signals_by_id: dict[str, dict[str, Any]],
    signal_checks: dict[str, dict[str, Any]],
    kg_build_id: str,
) -> dict[str, dict[str, Any]]:
    signal_ids = set(json_value(candidate.get("signal_ids"), []))
    fact_ids = set(json_value(bundle.get("fact_ids"), []))
    evidence_nodes = set(json_value(bundle.get("evidence_node_ids"), []))
    expected_fact_nodes = {f"fact:{fact_id}@@{kg_build_id}" for fact_id in fact_ids}
    claims = json_value(plan.get("claim_graph"), [])
    alignment = json_value(sample.get("claim_alignment"), [])
    generated_claim_ids = {str(item.get("claim_id")) for item in alignment}
    mandatory_claim_ids = set(json_value(plan.get("mandatory_claim_ids"), []))
    valid_conclusions = {
        str(item.get("conclusion_id"))
        for item in json_value(plan.get("valid_conclusion_set"), [])
    }
    risk_claims = [claim for claim in claims if claim.get("claim_role") == "risk"]
    aligned_signal_ids = {
        str(signal_id)
        for item in alignment
        for signal_id in item.get("evidence_ids") or []
    }
    unsupported_numbers = _NUMERIC_PATTERN.findall(str(sample.get("analysis_text") or ""))
    forbidden = sorted(
        name
        for name, pattern in _FORBIDDEN_PATTERNS.items()
        if pattern.search(str(sample.get("analysis_text") or ""))
    )
    supported_claims = all(
        set(claim.get("support_signal_ids") or []).issubset(signal_ids)
        and set(claim.get("support_fact_ids") or []).issubset(fact_ids)
        for claim in claims
    )
    checks = {
        "signal_input_complete": _check(
            all(signal_checks[signal_id]["input_complete"] for signal_id in signal_ids),
            {signal_id: signal_checks[signal_id]["input_complete"] for signal_id in sorted(signal_ids)},
            "all true",
        ),
        "signal_operator_recompute": _check(
            all(signal_checks[signal_id]["recompute_passed"] for signal_id in signal_ids),
            {signal_id: signal_checks[signal_id]["observed"] for signal_id in sorted(signal_ids)},
            {signal_id: signal_checks[signal_id]["expected"] for signal_id in sorted(signal_ids)},
        ),
        "signal_hash_match": _check(
            all(signal_checks[signal_id]["hash_passed"] for signal_id in signal_ids),
            {signal_id: signal_checks[signal_id]["hash_passed"] for signal_id in sorted(signal_ids)},
            "all true",
        ),
        "bundle_fact_coverage": _check(
            expected_fact_nodes.issubset(evidence_nodes),
            sorted(expected_fact_nodes & evidence_nodes),
            sorted(expected_fact_nodes),
        ),
        "bundle_signal_coverage": _check(
            signal_ids == set(json_value(bundle.get("signal_ids"), [])),
            sorted(json_value(bundle.get("signal_ids"), [])),
            sorted(signal_ids),
        ),
        "bundle_scope_completeness": _check(
            set(json_value(candidate.get("entity_ids"), []))
            == set(json_value(bundle.get("entity_ids"), [])),
            sorted(json_value(bundle.get("entity_ids"), [])),
            sorted(json_value(candidate.get("entity_ids"), [])),
        ),
        "claim_support_complete": _check(
            supported_claims,
            {claim["claim_id"]: claim.get("support_signal_ids") for claim in claims},
            "all claim signal/fact references are in the evidence bundle",
        ),
        "mandatory_claim_coverage": _check(
            mandatory_claim_ids.issubset(generated_claim_ids),
            sorted(generated_claim_ids),
            sorted(mandatory_claim_ids),
        ),
        "claim_counterevidence_acknowledged": _check(
            not risk_claims
            or all(
                set(claim.get("counter_signal_ids") or []).issubset(aligned_signal_ids)
                for claim in risk_claims
            ),
            sorted(aligned_signal_ids),
            sorted(
                {
                    str(signal_id)
                    for claim in risk_claims
                    for signal_id in claim.get("counter_signal_ids") or []
                }
            ),
        ),
        "unsupported_numeric_count": _check(
            not unsupported_numbers,
            unsupported_numbers,
            [],
        ),
        "forbidden_claim_count": _check(not forbidden, forbidden, []),
        "valid_conclusion": _check(
            str(sample.get("selected_conclusion_id")) in valid_conclusions,
            sample.get("selected_conclusion_id"),
            sorted(valid_conclusions),
        ),
        "claim_alignment_signal_grounding": _check(
            aligned_signal_ids.issubset(signal_ids),
            sorted(aligned_signal_ids),
            sorted(signal_ids),
        ),
    }
    return checks


def _load_facts(db: DBProtocol, fact_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not fact_ids:
        return {}
    placeholders = ",".join("?" for _ in fact_ids)
    return {
        str(row["fact_id"]): dict(row)
        for row in db.fetchall(
            f"SELECT * FROM standardized_facts WHERE fact_id IN ({placeholders})",
            fact_ids,
        )
    }


def _check(passed: bool, observed: Any, expected: Any) -> dict[str, Any]:
    return {"passed": bool(passed), "observed": observed, "expected": expected}
