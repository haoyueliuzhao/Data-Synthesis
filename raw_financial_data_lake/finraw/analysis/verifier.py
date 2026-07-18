from __future__ import annotations

import re
from collections import Counter
from typing import Any

from finraw.analysis.registry import (
    CLAIM_SCHEMA_VERSION,
    CONCLUSION_POLICY_VERSION,
    analysis_pattern_manifest,
    signal_registry,
    signal_registry_manifest,
    stable_hash,
)
from finraw.analysis.semantic_constraints import (
    ANALYSIS_SEMANTIC_GATE_VERSION,
    validate_signal_semantics,
)
from finraw.analysis.signals import (
    SIGNAL_EXECUTOR_VERSION,
    execute_signal,
    signal_result_hash,
)
from finraw.analysis.text_semantics import (
    ANALYSIS_TEXT_PARSER_VERSION,
    validate_numeric_grounding,
    validate_stance,
)
from finraw.analysis.claims import CLAIM_PLANNER_VERSION
from finraw.analysis.generator import ANALYSIS_GENERATOR_VERSION
from finraw.db.client import DBProtocol
from finraw.qa.store import insert_rows, json_value

ANALYSIS_VERIFIER_VERSION = "1.1.0"
_FORBIDDEN_PATTERNS = {
    "investment_recommendation": re.compile(
        r"\b(?:buy|sell|hold recommendation|invest in)\b", re.I
    ),
    "target_price": re.compile(r"\btarget price\b", re.I),
    "future_forecast": re.compile(
        r"\b(?:will|guaranteed|certain to|must rise|must fall)\b", re.I
    ),
    "causal_claim": re.compile(
        r"\b(?:caused by|because management|proves that)\b", re.I
    ),
}


def validate_analysis_samples(db: DBProtocol, analysis_build_id: str) -> dict[str, Any]:
    build_row = db.fetchone(
        "SELECT * FROM analysis_builds WHERE analysis_build_id = ?",
        (analysis_build_id,),
    )
    if not build_row:
        raise ValueError(f"Unknown analysis build: {analysis_build_id}")
    build = dict(build_row)
    kg_build_id = str(build["kg_build_id"])
    contract_checks = _build_contract_checks(build)
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
        str(row["signal_id"]): _validate_signal(db, row) for row in signals
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
            contract_checks,
            build,
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
        "build_contracts": contract_checks,
    }


def _build_contract_checks(build: dict[str, Any]) -> dict[str, dict[str, Any]]:
    expected = {
        "signal_registry_contract": stable_hash(
            {
                "registry": signal_registry_manifest(),
                "signal_executor_version": SIGNAL_EXECUTOR_VERSION,
                "semantic_gate_version": ANALYSIS_SEMANTIC_GATE_VERSION,
            }
        ),
        "analysis_pattern_contract": stable_hash(analysis_pattern_manifest()),
        "claim_schema_contract": stable_hash(
            {
                "version": CLAIM_SCHEMA_VERSION,
                "claim_planner_version": CLAIM_PLANNER_VERSION,
                "analysis_generator_version": ANALYSIS_GENERATOR_VERSION,
            }
        ),
        "conclusion_policy_contract": stable_hash(
            {"version": CONCLUSION_POLICY_VERSION}
        ),
        "analysis_verifier_contract": stable_hash(
            {
                "version": ANALYSIS_VERIFIER_VERSION,
                "text_parser_version": ANALYSIS_TEXT_PARSER_VERSION,
            }
        ),
    }
    columns = {
        "signal_registry_contract": "signal_registry_manifest_hash",
        "analysis_pattern_contract": "analysis_pattern_manifest_hash",
        "claim_schema_contract": "claim_schema_manifest_hash",
        "conclusion_policy_contract": "conclusion_policy_manifest_hash",
        "analysis_verifier_contract": "analysis_verifier_manifest_hash",
    }
    return {
        name: _check(
            str(build.get(columns[name]) or "") == value,
            build.get(columns[name]),
            value,
        )
        for name, value in expected.items()
    }


def _validate_signal(db: DBProtocol, row: dict[str, Any]) -> dict[str, Any]:
    plan = json_value(row.get("operator_plan"), {})
    role_fact_ids = dict(plan.get("role_fact_ids") or {})
    all_ids = sorted(
        {str(fact_id) for fact_ids in role_fact_ids.values() for fact_id in fact_ids}
    )
    facts = _load_facts(db, all_ids)
    complete = len(facts) == len(all_ids)
    roles = {
        role: [facts[str(fact_id)] for fact_id in fact_ids]
        for role, fact_ids in role_fact_ids.items()
        if all(str(fact_id) in facts for fact_id in fact_ids)
    }
    spec = signal_registry().get(str(row["signal_spec_id"]))
    semantic = (
        validate_signal_semantics(
            spec, roles, target_entity_id=plan.get("target_entity_id")
        )
        if spec
        else {"passed": False, "errors": ["unknown_signal_spec"], "checks": {}}
    )
    try:
        result = execute_signal(
            str(row["signal_spec_id"]),
            roles,
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
        "semantic_passed": bool(semantic["passed"]),
        "semantic": semantic,
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
    contract_checks: dict[str, dict[str, Any]],
    build: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    signal_ids = set(json_value(candidate.get("signal_ids"), []))
    fact_ids = set(json_value(bundle.get("fact_ids"), []))
    evidence_nodes = set(json_value(bundle.get("evidence_node_ids"), []))
    expected_fact_nodes = {f"fact:{fact_id}@@{kg_build_id}" for fact_id in fact_ids}
    claims = json_value(plan.get("claim_graph"), [])
    claim_by_id = {str(claim.get("claim_id")): claim for claim in claims}
    alignment = json_value(sample.get("claim_alignment"), [])
    generated_claim_ids = {str(item.get("claim_id")) for item in alignment}
    mandatory_claim_ids = set(json_value(plan.get("mandatory_claim_ids"), []))
    alignment_claim_ids_valid = generated_claim_ids.issubset(set(claim_by_id))
    alignment_evidence_exact = all(
        set(item.get("evidence_ids") or [])
        == set(
            (claim_by_id.get(str(item.get("claim_id"))) or {}).get("support_signal_ids")
            or []
        )
        for item in alignment
    )
    conclusion_rows = {
        str(item.get("conclusion_id")): item
        for item in json_value(plan.get("valid_conclusion_set"), [])
    }
    selected = str(sample.get("selected_conclusion_id") or "")
    risk_claims = [claim for claim in claims if claim.get("claim_role") == "risk"]
    aligned_signal_ids = {
        str(signal_id)
        for item in alignment
        for signal_id in item.get("evidence_ids") or []
    }
    text = str(sample.get("analysis_text") or "")
    forbidden = sorted(
        name for name, pattern in _FORBIDDEN_PATTERNS.items() if pattern.search(text)
    )
    supported_claims = all(
        set(claim.get("support_signal_ids") or []).issubset(signal_ids)
        and set(claim.get("support_fact_ids") or []).issubset(fact_ids)
        for claim in claims
    )
    claim_semantics = {}
    for item in alignment:
        claim_id = str(item.get("claim_id") or "")
        claim = claim_by_id.get(claim_id) or {}
        expected_stance = str(
            (claim.get("semantic_contract") or {}).get("expected_stance") or ""
        )
        claim_semantics[claim_id] = validate_stance(
            str(item.get("sentence") or ""), expected_stance
        )
    conclusion = conclusion_rows.get(selected) or {}
    conclusion_semantics = validate_stance(
        str(sample.get("conclusion_text") or ""),
        str((conclusion.get("semantic_contract") or {}).get("expected_stance") or ""),
    )
    sample_numeric_slots = json_value(sample.get("numeric_slots"), [])
    rubric_numeric_slots = json_value(sample.get("rubric"), {}).get("numeric_slots", [])
    numeric_slot_contract = stable_hash(sample_numeric_slots) == stable_hash(
        rubric_numeric_slots
    )
    numeric = validate_numeric_grounding(
        text,
        sample_numeric_slots if numeric_slot_contract else [],
        [
            int(value)
            for value in json_value(candidate.get("period_scope"), {}).get("years", [])
        ],
    )
    generation_metadata = json_value(sample.get("generation_metadata"), {})
    generation_policy = (
        json_value(build.get("notes"), {}).get("policy", {}).get("generation", {})
    )
    generation_contract = _generation_contract(
        sample, generation_metadata, generation_policy
    )
    graph_relations = _claim_graph_relations(claims)
    conclusion_predicate = _conclusion_predicate_check(conclusion, claims)
    checks = {
        **contract_checks,
        "signal_input_complete": _check(
            all(signal_checks[sid]["input_complete"] for sid in signal_ids),
            {sid: signal_checks[sid]["input_complete"] for sid in sorted(signal_ids)},
            "all true",
        ),
        "analysis_signal_semantic_gate": _check(
            all(signal_checks[sid]["semantic_passed"] for sid in signal_ids),
            {sid: signal_checks[sid]["semantic"] for sid in sorted(signal_ids)},
            "all semantic gates pass",
        ),
        "signal_operator_recompute": _check(
            all(signal_checks[sid]["recompute_passed"] for sid in signal_ids),
            {sid: signal_checks[sid]["observed"] for sid in sorted(signal_ids)},
            {sid: signal_checks[sid]["expected"] for sid in sorted(signal_ids)},
        ),
        "signal_hash_match": _check(
            all(signal_checks[sid]["hash_passed"] for sid in signal_ids),
            {sid: signal_checks[sid]["hash_passed"] for sid in sorted(signal_ids)},
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
            "all references in evidence bundle",
        ),
        "claim_graph_relations": _check(
            graph_relations["passed"],
            graph_relations,
            "valid nonempty synthesis dependencies and risk contradictions",
        ),
        "claim_id_valid": _check(
            alignment_claim_ids_valid, sorted(generated_claim_ids), sorted(claim_by_id)
        ),
        "mandatory_claim_coverage": _check(
            mandatory_claim_ids == generated_claim_ids,
            sorted(generated_claim_ids),
            sorted(mandatory_claim_ids),
        ),
        "claim_alignment_evidence_exact": _check(
            alignment_evidence_exact,
            alignment,
            "each claim uses its exact support_signal_ids",
        ),
        "claim_sentence_semantics": _check(
            bool(claim_semantics)
            and all(item["passed"] for item in claim_semantics.values()),
            claim_semantics,
            "all claim stances match claim graph",
        ),
        "claim_counterevidence_acknowledged": _check(
            not risk_claims
            or all(
                set(claim.get("counter_signal_ids") or []).issubset(aligned_signal_ids)
                and claim_semantics.get(str(claim["claim_id"]), {}).get("passed")
                for claim in risk_claims
            ),
            {
                "aligned_signal_ids": sorted(aligned_signal_ids),
                "claim_semantics": claim_semantics,
            },
            "all risk signals grounded and expressed as risk",
        ),
        "numeric_slot_contract": _check(
            numeric_slot_contract, sample_numeric_slots, rubric_numeric_slots
        ),
        "unsupported_numeric_count": _check(
            not numeric["unsupported"], numeric["unsupported"], []
        ),
        "numeric_slot_mismatch_count": _check(
            numeric["passed"], numeric, "all numeric mentions map to allowed slots"
        ),
        "numeric_unit_mismatch_count": _check(
            not numeric["unit_mismatches"], numeric["unit_mismatches"], []
        ),
        "forbidden_claim_count": _check(not forbidden, forbidden, []),
        "valid_conclusion": _check(
            selected in conclusion_rows, selected, sorted(conclusion_rows)
        ),
        "conclusion_predicate": _check(
            conclusion_predicate["passed"],
            conclusion_predicate,
            "stored predicate matches current claim state",
        ),
        "conclusion_sentence_semantics": _check(
            conclusion_semantics["passed"],
            conclusion_semantics,
            "conclusion sentence matches selected conclusion",
        ),
        "claim_alignment_signal_grounding": _check(
            aligned_signal_ids.issubset(signal_ids),
            sorted(aligned_signal_ids),
            sorted(signal_ids),
        ),
        "analysis_generation_contract": _check(
            generation_contract["passed"],
            generation_contract,
            "generation metadata is internally consistent",
        ),
    }
    return checks


def _generation_contract(
    sample: dict[str, Any], metadata: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    mode = str(policy.get("mode") or "deterministic_claim_plan")
    method = str(sample.get("generation_method") or "")
    fallback = metadata.get("fallback_reason")
    if mode == "controlled_llm" and method == "controlled_llm_claim_generation":
        passed = metadata.get("schema_valid") is True and not fallback
    elif mode == "controlled_llm" and "fallback" in method:
        passed = metadata.get("schema_valid") is False and bool(fallback)
    else:
        passed = mode != "controlled_llm" and method.startswith(
            "deterministic_claim_plan"
        )
    return {
        "passed": passed,
        "mode": mode,
        "generation_method": method,
        "schema_valid": metadata.get("schema_valid"),
        "fallback_reason": fallback,
    }


def _claim_graph_relations(claims: list[dict[str, Any]]) -> dict[str, Any]:
    ids = {str(claim.get("claim_id")) for claim in claims}
    synthesis = [claim for claim in claims if claim.get("claim_role") == "synthesis"]
    invalid_refs = []
    for claim in claims:
        for field in ("depends_on_claim_ids", "contradicts_claim_ids"):
            for ref in claim.get(field) or []:
                if str(ref) not in ids:
                    invalid_refs.append(
                        {"claim_id": claim.get("claim_id"), "field": field, "ref": ref}
                    )
    risk = [claim for claim in claims if claim.get("claim_role") == "risk"]
    passed = (
        len(synthesis) == 1
        and bool(synthesis[0].get("depends_on_claim_ids"))
        and all(claim.get("contradicts_claim_ids") for claim in risk)
        and not invalid_refs
    )
    return {
        "passed": passed,
        "synthesis_count": len(synthesis),
        "synthesis_dependencies": synthesis[0].get("depends_on_claim_ids")
        if synthesis
        else [],
        "risk_relation_count": sum(
            bool(claim.get("contradicts_claim_ids")) for claim in risk
        ),
        "invalid_refs": invalid_refs,
    }


def _conclusion_predicate_check(
    conclusion: dict[str, Any], claims: list[dict[str, Any]]
) -> dict[str, Any]:
    stored = dict(conclusion.get("conditions") or {})
    base = [claim for claim in claims if claim.get("claim_role") != "synthesis"]
    observed = {
        "positive_claims": sum(c.get("claim_polarity") == "positive" for c in base),
        "negative_claims": sum(c.get("claim_polarity") == "negative" for c in base),
        "neutral_claims": sum(c.get("claim_polarity") == "neutral" for c in base),
        "risk_claims": sum(c.get("claim_role") == "risk" for c in base),
        "cash_risk": any(
            c.get("claim_type") == "cash_quality" and c.get("claim_role") == "risk"
            for c in base
        ),
        "leverage_risk": any(
            c.get("claim_type") == "relative_leverage" and c.get("claim_role") == "risk"
            for c in base
        ),
    }
    return {
        "passed": bool(conclusion) and stored == observed,
        "stored": stored,
        "observed": observed,
    }


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
