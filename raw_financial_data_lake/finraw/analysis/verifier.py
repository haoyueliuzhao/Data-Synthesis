from __future__ import annotations

import re
from collections import Counter
from typing import Any

from finraw.analysis.peer_scope import (
    PEER_SCOPE_ELIGIBILITY_POLICY_VERSION,
    recompute_peer_universe,
    scope_membership_hash,
)
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
from finraw.analysis.semantic_frames import (
    FORBIDDEN_CLAIM_EXTENSIONS,
    SEMANTIC_FRAME_VERSION,
    build_claim_semantic_frame,
    build_conclusion_semantic_frame,
    render_semantic_frame,
    semantic_frame_manifest,
    validate_semantic_frame,
)
from finraw.analysis.text_semantics import (
    ANALYSIS_TEXT_PARSER_VERSION,
    validate_numeric_grounding,
)
from finraw.analysis.claims import CLAIM_PLANNER_VERSION
from finraw.analysis.generator import ANALYSIS_GENERATOR_VERSION
from finraw.db.client import DBProtocol
from finraw.qa.store import insert_rows, json_value

ANALYSIS_VERIFIER_VERSION = "2.1.0"
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
    kg_row = db.fetchone(
        "SELECT * FROM kg_builds WHERE kg_build_id = ?", (kg_build_id,)
    )
    if not kg_row:
        raise ValueError(f"Unknown pinned KG build: {kg_build_id}")
    kg = dict(kg_row)
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
    peer_scope_cache: dict[str, dict[str, Any]] = {}
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
            db,
            kg,
            peer_scope_cache,
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
                "semantic_frame_manifest": semantic_frame_manifest(),
            }
        ),
        "conclusion_policy_contract": stable_hash(
            {"version": CONCLUSION_POLICY_VERSION}
        ),
        "analysis_verifier_contract": stable_hash(
            {
                "version": ANALYSIS_VERIFIER_VERSION,
                "text_parser_version": ANALYSIS_TEXT_PARSER_VERSION,
                "semantic_frame_version": SEMANTIC_FRAME_VERSION,
                "peer_scope_eligibility_policy_version": (
                    PEER_SCOPE_ELIGIBILITY_POLICY_VERSION
                ),
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
        "input_entity_ids": sorted(
            {str(fact.get("entity_id") or "") for fact in facts.values()}
        ),
        "role_entity_ids": {
            role: sorted(
                {
                    str(facts[str(fact_id)].get("entity_id") or "")
                    for fact_id in fact_ids
                    if str(fact_id) in facts
                }
            )
            for role, fact_ids in role_fact_ids.items()
        },
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
    db: DBProtocol,
    kg: dict[str, Any],
    peer_scope_cache: dict[str, dict[str, Any]],
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
    claim_frame_checks = {}
    for item in alignment:
        claim_id = str(item.get("claim_id") or "")
        claim = claim_by_id.get(claim_id) or {}
        try:
            expected_frame = build_claim_semantic_frame(
                str(claim.get("claim_type") or ""),
                str(claim.get("claim_role") or ""),
                str(claim.get("claim_polarity") or ""),
            )
            rebuild_errors = []
        except ValueError as exc:
            expected_frame = {}
            rebuild_errors = [type(exc).__name__]
        stored_frame = dict(claim.get("semantic_frame") or {})
        observed_frame = dict(item.get("semantic_frame") or {})
        surface_form_id = str(item.get("surface_form_id") or "")
        frame_errors = rebuild_errors + validate_semantic_frame(
            observed_frame, expected_frame, kind="claim"
        )
        stored_errors = validate_semantic_frame(
            stored_frame, expected_frame, kind="claim"
        )
        try:
            rendered = render_semantic_frame(
                expected_frame, surface_form_id, kind="claim"
            )
        except ValueError as exc:
            rendered = ""
            frame_errors.append(type(exc).__name__)
        sentence = str(item.get("sentence") or "")
        claim_frame_checks[claim_id] = {
            "passed": not frame_errors and not stored_errors and sentence == rendered,
            "expected_frame": expected_frame,
            "stored_frame": stored_frame,
            "observed_frame": observed_frame,
            "surface_form_id": surface_form_id,
            "rendered_sentence": rendered,
            "observed_sentence": sentence,
            "frame_errors": frame_errors,
            "stored_frame_errors": stored_errors,
            "frame_version": SEMANTIC_FRAME_VERSION,
        }
    claim_context_checks = {
        str(item.get("claim_id") or ""): _claim_context_contract(
            claim_by_id.get(str(item.get("claim_id") or "")) or {},
            item,
            signals_by_id,
        )
        for item in alignment
    }
    unknown_entities = sorted(
        {
            value
            for result in claim_context_checks.values()
            for value in result["unknown_entity_ids"]
        }
    )
    unknown_metrics = sorted(
        {
            value
            for result in claim_context_checks.values()
            for value in result["unknown_metric_ids"]
        }
    )
    unknown_periods = sorted(
        {
            value
            for result in claim_context_checks.values()
            for value in result["unknown_periods"]
        }
    )
    unknown_predicates = sorted(
        {
            value
            for result in claim_context_checks.values()
            for value in result["unknown_predicates"]
        }
    )
    unknown_numeric_slots = sorted(
        {
            value
            for result in claim_context_checks.values()
            for value in result["unknown_numeric_slot_ids"]
        }
    )
    forbidden_extensions = sorted(
        {
            value
            for result in claim_context_checks.values()
            for value in result["forbidden_extensions"]
        }
    )
    required_caveat_ids = sorted(
        str(value) for value in json_value(plan.get("required_caveat_ids"), [])
    )
    observed_caveat_ids = [
        str(item.get("caveat_id") or "")
        for item in json_value(sample.get("caveats"), [])
        if isinstance(item, dict)
    ]
    caveat_ids_exact = sorted(observed_caveat_ids) == required_caveat_ids and len(
        observed_caveat_ids
    ) == len(set(observed_caveat_ids))
    conclusion = conclusion_rows.get(selected) or {}
    expected_conclusion_frame = build_conclusion_semantic_frame(
        selected,
        str((conclusion.get("semantic_contract") or {}).get("expected_stance") or ""),
    )
    stored_conclusion_frame = dict(conclusion.get("semantic_frame") or {})
    observed_conclusion_frame = json_value(sample.get("conclusion_semantic_frame"), {})
    conclusion_surface = str(sample.get("conclusion_surface_form_id") or "")
    conclusion_frame_errors = validate_semantic_frame(
        observed_conclusion_frame, expected_conclusion_frame, kind="conclusion"
    )
    stored_conclusion_errors = validate_semantic_frame(
        stored_conclusion_frame, expected_conclusion_frame, kind="conclusion"
    )
    try:
        rendered_conclusion = render_semantic_frame(
            expected_conclusion_frame, conclusion_surface, kind="conclusion"
        )
    except ValueError as exc:
        rendered_conclusion = ""
        conclusion_frame_errors.append(type(exc).__name__)
    conclusion_frame_check = {
        "passed": not conclusion_frame_errors
        and not stored_conclusion_errors
        and str(sample.get("conclusion_text") or "") == rendered_conclusion,
        "expected_frame": expected_conclusion_frame,
        "stored_frame": stored_conclusion_frame,
        "observed_frame": observed_conclusion_frame,
        "surface_form_id": conclusion_surface,
        "rendered_sentence": rendered_conclusion,
        "observed_sentence": str(sample.get("conclusion_text") or ""),
        "frame_errors": conclusion_frame_errors,
        "stored_frame_errors": stored_conclusion_errors,
        "frame_version": SEMANTIC_FRAME_VERSION,
    }
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
    rendered_analysis_text = " ".join(
        [str(item.get("sentence") or "") for item in alignment]
        + [str(sample.get("conclusion_text") or "")]
        + [
            str(item.get("sentence") or "")
            for item in json_value(sample.get("caveats"), [])
        ]
    )
    graph_relations = _claim_graph_relations(claims)
    conclusion_predicate = _conclusion_predicate_check(conclusion, claims)
    peer_scope_checks = _peer_scope_checks(
        db,
        kg,
        candidate,
        bundle,
        signal_ids,
        signal_checks,
        peer_scope_cache,
    )
    checks = {
        **contract_checks,
        **peer_scope_checks,
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
        "claim_semantic_frame_contract": _check(
            bool(claim_frame_checks)
            and all(item["passed"] for item in claim_frame_checks.values()),
            claim_frame_checks,
            "all claim frames are rebuilt from the claim graph and render exactly",
        ),
        "claim_counterevidence_acknowledged": _check(
            not risk_claims
            or all(
                set(claim.get("counter_signal_ids") or []).issubset(aligned_signal_ids)
                and claim_frame_checks.get(str(claim["claim_id"]), {}).get("passed")
                and claim_frame_checks.get(str(claim["claim_id"]), {})
                .get("expected_frame", {})
                .get("predicate")
                == "constrains"
                for claim in risk_claims
            ),
            {
                "aligned_signal_ids": sorted(aligned_signal_ids),
                "claim_frame_checks": claim_frame_checks,
            },
            "all risk signals are grounded in exact constraining semantic frames",
        ),
        "claim_context_contract": _check(
            bool(claim_context_checks)
            and all(item["passed"] for item in claim_context_checks.values()),
            claim_context_checks,
            "stored and observed Claim context equals Signal-derived allowlists",
        ),
        "unknown_entity_count": _check(not unknown_entities, unknown_entities, []),
        "unknown_metric_count": _check(not unknown_metrics, unknown_metrics, []),
        "unknown_period_count": _check(not unknown_periods, unknown_periods, []),
        "unknown_predicate_count": _check(
            not unknown_predicates, unknown_predicates, []
        ),
        "unknown_numeric_slot_count": _check(
            not unknown_numeric_slots, unknown_numeric_slots, []
        ),
        "forbidden_claim_extension_count": _check(
            not forbidden_extensions, forbidden_extensions, []
        ),
        "caveat_id_exact_match": _check(
            caveat_ids_exact,
            sorted(observed_caveat_ids),
            required_caveat_ids,
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
        "analysis_text_render_contract": _check(
            text == rendered_analysis_text,
            text,
            rendered_analysis_text,
        ),
        "valid_conclusion": _check(
            selected in conclusion_rows, selected, sorted(conclusion_rows)
        ),
        "conclusion_predicate": _check(
            conclusion_predicate["passed"],
            conclusion_predicate,
            "stored predicate matches current claim state",
        ),
        "conclusion_semantic_frame_contract": _check(
            conclusion_frame_check["passed"],
            conclusion_frame_check,
            "conclusion frame is rebuilt from the selected predicate and renders exactly",
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


def _peer_scope_checks(
    db: DBProtocol,
    kg: dict[str, Any],
    candidate: dict[str, Any],
    bundle: dict[str, Any],
    signal_ids: set[str],
    signal_checks: dict[str, dict[str, Any]],
    cache: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    is_peer = str(candidate.get("analysis_pattern_id") or "") == "peer_positioning_v1"
    candidate_contract = json_value(candidate.get("peer_scope_contract"), {})
    bundle_contract = json_value(bundle.get("peer_scope_contract"), {})
    candidate_expected = sorted(
        str(value)
        for value in json_value(candidate.get("expected_scope_entity_ids"), [])
    )
    bundle_expected = sorted(
        str(value)
        for value in json_value(bundle.get("expected_scope_entity_ids"), [])
    )
    candidate_entities = sorted(
        str(value) for value in json_value(candidate.get("entity_ids"), [])
    )
    bundle_entities = sorted(
        str(value) for value in json_value(bundle.get("entity_ids"), [])
    )
    if not is_peer:
        empty = (
            not candidate_contract
            and not bundle_contract
            and not candidate_expected
            and not bundle_expected
            and not candidate.get("peer_scope_type")
            and not bundle.get("peer_scope_type")
            and not candidate.get("peer_scope_id")
            and not bundle.get("peer_scope_id")
            and not candidate.get("scope_membership_hash")
            and not bundle.get("scope_membership_hash")
            and not candidate.get("scope_eligibility_policy_hash")
            and not bundle.get("scope_eligibility_policy_hash")
        )
        return {
            "peer_scope_contract": _check(empty, "not_applicable", "empty"),
            "peer_scope_policy_hash": _check(empty, "not_applicable", "empty"),
            "peer_scope_membership_hash": _check(empty, "not_applicable", "empty"),
            "peer_scope_recomputed_universe": _check(
                empty, "not_applicable", "not_applicable"
            ),
            "peer_scope_fact_representation": _check(
                empty, "not_applicable", "not_applicable"
            ),
        }

    cache_key = stable_hash(
        {
            "kg_build_id": kg["kg_build_id"],
            "contract": candidate_contract,
        }
    )
    if cache_key not in cache:
        cache[cache_key] = recompute_peer_universe(db, kg, candidate_contract)
    recomputed = cache[cache_key]
    recomputed_entities = sorted(
        str(value) for value in recomputed.get("entity_ids") or []
    )
    role_entities = {
        f"{signal_id}:{role}": sorted(str(value) for value in values)
        for signal_id in sorted(signal_ids)
        for role, values in signal_checks[signal_id].get("role_entity_ids", {}).items()
    }
    role_sets_exact = bool(role_entities) and all(
        values == recomputed_entities for values in role_entities.values()
    )
    contract_fields = (
        "peer_scope_type",
        "peer_scope_id",
        "scope_membership_hash",
        "scope_eligibility_policy_hash",
    )
    top_level_contract_match = all(
        str(candidate.get(field) or "")
        == str(bundle.get(field) or "")
        == str(candidate_contract.get(field) or "")
        for field in contract_fields
    )
    contract_complete = all(
        candidate_contract.get(field) not in (None, "", [])
        for field in (
            "peer_scope_type",
            "peer_scope_id",
            "fiscal_year",
            "source_id",
            "normalized_unit",
            "normalized_currency",
            "source_definition_compatibility",
            "scope_eligibility_policy",
            "scope_eligibility_policy_hash",
            "scope_membership_hash",
            "expected_scope_entity_ids",
        )
    )
    observed_policy_hashes = {
        "candidate": str(candidate.get("scope_eligibility_policy_hash") or ""),
        "bundle": str(bundle.get("scope_eligibility_policy_hash") or ""),
        "contract": str(
            candidate_contract.get("scope_eligibility_policy_hash") or ""
        ),
    }
    expected_policy_hash = str(
        recomputed.get("scope_eligibility_policy_hash") or ""
    )
    observed_membership_hashes = {
        "candidate": str(candidate.get("scope_membership_hash") or ""),
        "bundle": str(bundle.get("scope_membership_hash") or ""),
        "contract": str(candidate_contract.get("scope_membership_hash") or ""),
        "contract_rebuilt": scope_membership_hash(candidate_contract),
    }
    expected_membership_hash = str(recomputed.get("scope_membership_hash") or "")
    stored_sets = {
        "candidate_expected": candidate_expected,
        "bundle_expected": bundle_expected,
        "contract_expected": sorted(
            str(value)
            for value in candidate_contract.get("expected_scope_entity_ids") or []
        ),
        "candidate_entities": candidate_entities,
        "bundle_entities": bundle_entities,
    }
    return {
        "peer_scope_contract": _check(
            contract_complete
            and candidate_contract == bundle_contract
            and top_level_contract_match,
            {
                "candidate_contract": candidate_contract,
                "bundle_contract": bundle_contract,
                "top_level_contract_match": top_level_contract_match,
            },
            "complete and identical Candidate/Bundle peer scope contract",
        ),
        "peer_scope_policy_hash": _check(
            recomputed.get("passed") is True
            and all(value == expected_policy_hash for value in observed_policy_hashes.values()),
            {
                "observed": observed_policy_hashes,
                "recompute_errors": recomputed.get("errors") or [],
            },
            expected_policy_hash,
        ),
        "peer_scope_membership_hash": _check(
            all(
                value == expected_membership_hash
                for value in observed_membership_hashes.values()
            ),
            observed_membership_hashes,
            expected_membership_hash,
        ),
        "peer_scope_recomputed_universe": _check(
            bool(recomputed_entities)
            and all(values == recomputed_entities for values in stored_sets.values()),
            stored_sets,
            recomputed_entities,
        ),
        "peer_scope_fact_representation": _check(
            role_sets_exact,
            role_entities,
            recomputed_entities,
        ),
    }


def _claim_context_contract(
    claim: dict[str, Any],
    alignment: dict[str, Any],
    signals_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    signal_rows = [
        signals_by_id[str(signal_id)]
        for signal_id in claim.get("support_signal_ids") or []
        if str(signal_id) in signals_by_id
    ]
    expected = {
        "entity_ids": sorted(
            {
                str(value)
                for row in signal_rows
                for value in json_value(row.get("entity_ids"), [])
            }
        ),
        "metric_ids": sorted(
            {
                str(value)
                for row in signal_rows
                for value in json_value(row.get("metric_ids"), [])
            }
        ),
        "periods": sorted(
            {
                int(value)
                for row in signal_rows
                for value in json_value(row.get("period_scope"), {}).get("years", [])
            }
        ),
        "predicates": [str((claim.get("semantic_frame") or {}).get("predicate") or "")],
        "numeric_slot_ids": sorted(
            str(slot.get("slot_id") or "")
            for slot in claim.get("required_numeric_slots") or []
        ),
    }
    stored = {
        "entity_ids": sorted(
            str(value) for value in claim.get("allowed_entity_ids") or []
        ),
        "metric_ids": sorted(
            str(value) for value in claim.get("allowed_metric_ids") or []
        ),
        "periods": sorted(int(value) for value in claim.get("allowed_periods") or []),
        "predicates": sorted(
            str(value) for value in claim.get("allowed_predicates") or []
        ),
        "numeric_slot_ids": sorted(
            str(value) for value in claim.get("allowed_numeric_slot_ids") or []
        ),
    }
    observed_raw = alignment.get("context_bindings") or {}
    observed = {
        "entity_ids": sorted(
            str(value) for value in observed_raw.get("entity_ids") or []
        ),
        "metric_ids": sorted(
            str(value) for value in observed_raw.get("metric_ids") or []
        ),
        "periods": sorted(int(value) for value in observed_raw.get("periods") or []),
        "predicates": sorted(
            str(value) for value in observed_raw.get("predicates") or []
        ),
        "numeric_slot_ids": sorted(
            str(value) for value in observed_raw.get("numeric_slot_ids") or []
        ),
    }
    extensions = sorted(str(value) for value in alignment.get("claim_extensions") or [])
    forbidden_contract = sorted(
        str(value) for value in claim.get("forbidden_claim_extensions") or []
    )
    required_slots_match = (
        sorted(str(value) for value in claim.get("required_entity_slots") or [])
        == expected["entity_ids"]
        and sorted(int(value) for value in claim.get("required_period_slots") or [])
        == expected["periods"]
    )
    return {
        "passed": stored == expected
        and observed == expected
        and forbidden_contract == sorted(FORBIDDEN_CLAIM_EXTENSIONS)
        and required_slots_match
        and not extensions,
        "expected": expected,
        "stored": stored,
        "observed": observed,
        "required_slots_match": required_slots_match,
        "forbidden_contract": forbidden_contract,
        "unknown_entity_ids": sorted(
            set(observed["entity_ids"]) - set(expected["entity_ids"])
        ),
        "unknown_metric_ids": sorted(
            set(observed["metric_ids"]) - set(expected["metric_ids"])
        ),
        "unknown_periods": sorted(set(observed["periods"]) - set(expected["periods"])),
        "unknown_predicates": sorted(
            set(observed["predicates"]) - set(expected["predicates"])
        ),
        "unknown_numeric_slot_ids": sorted(
            set(observed["numeric_slot_ids"]) - set(expected["numeric_slot_ids"])
        ),
        "forbidden_extensions": extensions,
    }


def _generation_contract(
    sample: dict[str, Any], metadata: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    mode = str(policy.get("mode") or "deterministic_claim_plan")
    method = str(sample.get("generation_method") or "")
    fallback = metadata.get("fallback_reason")
    if mode == "controlled_llm" and method == "controlled_llm_semantic_frame":
        passed = metadata.get("schema_valid") is True and not fallback
    elif mode == "controlled_llm" and "fallback" in method:
        passed = metadata.get("schema_valid") is False and bool(fallback)
    else:
        passed = mode != "controlled_llm" and method.startswith(
            "deterministic_semantic_frame"
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
