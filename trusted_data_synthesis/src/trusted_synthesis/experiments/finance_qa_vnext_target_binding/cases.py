"""Exactly eighteen historical cases; no replacement primary score."""

import json
from fractions import Fraction
from pathlib import Path

from .core import (
    CASE_KEYS,
    OLD,
    OUTPUT,
    read_bound,
    read_json,
    read_phase,
    record,
    reference,
    require,
    require_frozen_ledger,
    seal,
    sha,
)
from .policy import source_claim, target_binding


def case_name(task, arm, seed):
    return f"{task}/{arm}_{seed}"


def packet_name(name):
    return "packets/" + name.replace("/", "__") + ".json"


def prepare(root, guard):
    root = Path(root).resolve()
    ledger, ledger_manifest = require_frozen_ledger(root)
    entries = {entry["task_key"]: entry for entry in ledger["entries"]}
    contract = read_json(root / OUTPUT / "ledger/public_contract.json")
    old_report_path = OLD + "/reviewed/confirm/report.json"
    old_report = read_json(root / old_report_path)
    by_key = {(r["task_key"], r["variant"]): r for r in old_report["rows"]}
    payloads, registrations = {}, []
    for task, arm, seed in CASE_KEYS:
        variant = f"{arm}_{seed}"
        name = case_name(task, arm, seed)
        row = by_key[(task, variant)]
        public = read_bound(root, entries[task]["public_document_reference"])
        relative = OLD + f"/generation/confirm/{variant}/sessions/{task}"
        initial = read_json(root / relative / "turns/000_request.json")
        result = read_json(root / relative / "result.json")
        messages = read_json(root / relative / "messages.json")
        require(
            initial["messages"][0]["content"] == contract["system"], "case.actual_public_contract"
        )
        require(
            json.loads(initial["messages"][1]["content"])["task"] == public,
            "case.actual_original_public_task",
        )
        raws, refs = (
            [],
            [
                reference(root, relative + "/result.json"),
                reference(root, relative + "/messages.json"),
                reference(root, relative + "/turns/000_request.json"),
            ],
        )
        for attempt in result["attempts"]:
            if not attempt["generation_invoked"]:
                continue
            index = attempt["response_index"]
            path = relative + f"/turns/{index:03d}_assistant.raw"
            raw = (root / path).read_bytes()
            require(sha(raw) == attempt["raw_response_sha256"], "case.original_raw_byte_binding")
            raws.append({"response_index": index, "content": raw.decode(), "sha256": sha(raw)})
            refs.append(reference(root, path))
        packet = record(
            "bounded_case_packet",
            case_key=name,
            task_key=task,
            variant=variant,
            arm=arm,
            seed=seed,
            original_review_id=row["review_id"],
            target_ledger_entry_id=entries[task]["id"],
            public_document=public,
            recorded_public_system=initial["messages"][0]["content"],
            original_messages=messages,
            all_generated_public_responses=raws,
            original_events=result["events"],
            original_final=result["final"],
            original_terminal=result["terminal"],
            original_review=row,
            original_result_id=result["id"],
            original_file_references=refs,
            original_review_report_reference=reference(root, old_report_path),
            no_tool_replay=True,
            no_new_model_requests=True,
        )
        payloads[packet_name(name)] = packet
        registrations.append(
            {
                "case_key": name,
                "packet_id": packet["id"],
                "packet_path": packet_name(name),
                "original_review_id": row["review_id"],
                "original_generated_responses": len(raws),
            }
        )
    require(len(registrations) == 18, "case.exact_scope")
    report = record(
        "bounded_case_packets",
        registrations=registrations,
        cases=18,
        target_ledger_id=ledger["id"],
        target_ledger_manifest_id=ledger_manifest["id"],
        old_original_responses_copied=sum(r["original_generated_responses"] for r in registrations),
        old_other_234_sessions_not_rejudged=True,
        guard=guard.receipt(),
    )
    payloads["report.json"] = report
    manifest = seal(root, "case_packets", payloads)
    return {"id": report["id"], "manifest_id": manifest["id"], "cases": 18}


def validate_evidence(packet, evidence):
    require(isinstance(evidence, list) and bool(evidence), "case.nonempty_public_evidence")
    raws = {r["response_index"]: r["content"] for r in packet["all_generated_public_responses"]}
    for item in evidence:
        kind, quote = item.get("kind"), item.get("quote")
        require(isinstance(quote, str) and bool(quote.strip()), "case.exact_nonempty_quote")
        if kind == "response":
            container = raws.get(item.get("response_index"))
        elif kind == "source":
            segment = packet["public_document"]["segments"].get(item.get("segment_id"))
            container = segment["text"] if segment else None
        elif kind == "question":
            container = packet["public_document"]["question"]
        elif kind == "contract":
            container = packet["recorded_public_system"]
        else:
            container = None
        require(
            isinstance(container, str) and quote in container, "case.quote_in_exact_public_record"
        )


def finalize(root, reviews_path, guard):
    root = Path(root).resolve()
    ledger, ledger_manifest = require_frozen_ledger(root)
    packets_report, packets_manifest = read_phase(root, "case_packets")
    entries = {e["task_key"]: e for e in ledger["entries"]}
    reviews_path = Path(reviews_path).resolve()
    require(
        reviews_path.is_relative_to(root / OUTPUT / "manual_reviews"), "case.new_review_input_only"
    )
    reviews = read_json(reviews_path)
    expected = {case_name(*key) for key in CASE_KEYS}
    require(set(reviews) == expected, "case.exact_18_review_keys")
    payloads, cases = {}, []
    for registration in packets_report["registrations"]:
        name = registration["case_key"]
        packet = read_json(root / OUTPUT / "case_packets" / registration["packet_path"])
        require(packet["id"] == registration["packet_id"], "case.packet_identity")
        review = reviews[name]
        require(review["case_key"] == name, "case.review_identity")
        require(
            review["reviewer"] and review["not_independent_or_blind"] is True, "case.reviewer_scope"
        )
        for field in ("formula_explanation", "chain_explanation", "claimed_target_scope"):
            require(
                isinstance(review[field], str) and review[field].strip(),
                "case.semantic_explanation",
            )
        validate_evidence(packet, review["formula_evidence"])
        validate_evidence(packet, review["chain_evidence"])
        finals = [e["response_index"] for e in packet["original_events"] if e["final"]]
        require(len(finals) == 1, "case.actual_first_Final_present")
        require(
            any(
                e.get("kind") == "response" and e.get("response_index") == finals[0]
                for e in review["chain_evidence"]
            ),
            "case.chain_requires_actual_Final",
        )
        calculations = {
            e["tool_call"]["id"]: e
            for e in packet["original_events"]
            if e["tool_call"] is not None
            and e["tool_call"]["name"] == "calculate"
            and e["tool_call"]["output"]["status"] == "ok"
        }
        require(
            review["selected_calculation"] in calculations,
            "case.selected_actual_successful_calculation",
        )
        claims = []
        require(
            isinstance(review["source_claims"], list) and bool(review["source_claims"]),
            "case.explicit_claim_review",
        )
        for claim in review["source_claims"]:
            require(
                claim["explanation"] and claim["location"], "case.claim_explanation_and_location"
            )
            validate_evidence(packet, claim["evidence"])
            if not claim["parameters"]["current"]:
                validate_evidence(packet, claim["withdrawal_evidence"])
            result = source_claim(**claim["parameters"])
            claims.append(
                {
                    **result,
                    "location": claim["location"],
                    "explanation": claim["explanation"],
                    "evidence": claim["evidence"],
                    "withdrawal_evidence": claim.get("withdrawal_evidence", []),
                }
            )
        binding = target_binding(
            alignment=entries[packet["task_key"]]["public_target_review"]["alignment_status"],
            **review["binding_parameters"],
        )
        current = [c["status"] for c in claims if c["current"]]
        claim_status = (
            "FAIL" if "FAIL" in current else "UNDETERMINED" if "UNDETERMINED" in current else "PASS"
        )
        case = record(
            "bounded_target_semantic_review",
            case_key=name,
            original_packet_id=packet["id"],
            original_review_id=packet["original_review_id"],
            target_ledger_entry_id=entries[packet["task_key"]]["id"],
            binding=binding,
            claimed_target_scope=review["claimed_target_scope"],
            formula_explanation=review["formula_explanation"],
            formula_evidence=review["formula_evidence"],
            final_chain_explanation=review["chain_explanation"],
            final_chain_evidence=review["chain_evidence"],
            selected_original_calculation=calculations[review["selected_calculation"]],
            source_claims=claims,
            current_source_claim_certification=claim_status,
            old_quantity_status_unchanged=packet["original_review"]["qualification"][
                "task_answer_status"
            ],
            old_complete_PASS_unchanged=packet["original_review"]["qualification"][
                "complete_verifiable_trajectory"
            ],
            old_semantic_statuses_unchanged={
                k: v["status"] for k, v in packet["original_review"]["semantic_review"].items()
            },
            reviewer=review["reviewer"],
            not_independent_or_blind=True,
            no_new_complete_trajectory_grade=True,
        )
        cases.append(case)
        payloads["reviews/" + name.replace("/", "__") + ".json"] = case
    report = record(
        "bounded_semantic_review_report",
        cases=cases,
        case_count=18,
        target_ledger_id=ledger["id"],
        target_ledger_manifest_id=ledger_manifest["id"],
        case_packets_manifest_id=packets_manifest["id"],
        manual_review_reference=reference(root, reviews_path.relative_to(root)),
        manual_review_frozen_before_this_derivation=True,
        new_complete_trajectory_scores=0,
        no_splicing_local_results_with_other_old_sessions=True,
        old_development_selection_and_confirmation_unchanged=True,
        known_output_measurement_work_not_independent_confirmation=True,
        guard=guard.receipt(),
    )
    payloads["report.json"] = report
    manifest = seal(root, "cases", payloads)
    return {"id": report["id"], "manifest_id": manifest["id"], "case_count": len(cases)}


def show(root, first, last):
    root = Path(root).resolve()
    require_frozen_ledger(root)
    report, _ = read_phase(root, "case_packets")
    require(1 <= first <= last <= 18, "case.viewer_registered_range")
    for number in range(first, last + 1):
        registration = report["registrations"][number - 1]
        packet = read_json(root / OUTPUT / "case_packets" / registration["packet_path"])
        old = packet["original_review"]
        print(
            json.dumps(
                {
                    "case_number": number,
                    "case_key": packet["case_key"],
                    "old_review_id": packet["original_review_id"],
                    "question": packet["public_document"]["question"],
                    "all_generated_public_responses": packet["all_generated_public_responses"],
                    "all_actual_events": packet["original_events"],
                    "original_semantic_review": old["semantic_review"],
                    "original_quantity": old["qualification"]["answer"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )


def closeout(root, guard, historical_integrity):
    root = Path(root).resolve()
    ledger, lm = require_frozen_ledger(root)
    failure, fm = read_phase(root, "failure_structure")
    cases, cm = read_phase(root, "cases")
    require(
        len(cases["cases"]) == 18 and failure["all_sessions"]["registered_sessions"] == 252,
        "closeout.bounded_counts",
    )
    old = read_json(root / OLD / "closeout/report.json")
    base = old["confirmation_by_arm"]["pi0"]["complete_trace_PASS"]
    candidate = old["confirmation_by_arm"]["minus_D"]["complete_trace_PASS"]
    denominator = old["confirmation_by_arm"]["pi0"]["sessions"]
    require((base, candidate, denominator) == (20, 19, 72), "closeout.preserved_original_result")
    report = record(
        "target_binding_closeout",
        target_ledger_id=ledger["id"],
        failure_structure_id=failure["id"],
        bounded_case_report_id=cases["id"],
        phase_manifest_ids={"ledger": lm["id"], "failure_structure": fm["id"], "cases": cm["id"]},
        historical_integrity=historical_integrity,
        original_closeout_reference=reference(root, OLD + "/closeout/report.json"),
        preserved_original_confirmation={
            "pi0": "20/72",
            "minus_D": "19/72",
            "paired_mean_gain": "-1/72",
        },
        C04_single_flip_sensitivity={
            "type": "EXPLICIT_COUNTERFACTUAL_SCORE_ILLUSTRATION_NOT_REGRADING",
            "assumption": (
                "Only original confirm_126 complete-PASS indicator changed to"
                " PASS; all other old indicators fixed."
            ),
            "pi0": str(Fraction(base, denominator)),
            "minus_D": str(Fraction(candidate + 1, denominator)),
            "paired_mean_gain": str(Fraction(candidate + 1 - base, denominator)),
            "is_observed_new_score": False,
            "is_model_repair_or_causal_effect": False,
            "does_not_establish_positive_gain": True,
        },
        original_24_confirm_tasks_not_fresh_confirmation_anymore=True,
        E_X2_DR_next_study_status="PROPOSED_NOT_ACCEPTED_OR_FROZEN_NO_CALLS",
        guard=guard.receipt(),
    )
    manifest = seal(root, "closeout", {"report.json": report})
    return {"id": report["id"], "manifest_id": manifest["id"]}
