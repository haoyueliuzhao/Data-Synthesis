"""Post-run read-only verification; never regenerates, regrades, normalizes or tokenizes."""

import json
from collections import Counter
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import (
    ARMS,
    LABELS,
    MODEL,
    OUTPUT,
    SYSTEMS_NEW,
    TASKS,
    encode,
    history_guard,
    read_json,
    require,
    sha,
)


def verify_quotes(value, originals):
    if isinstance(value, dict):
        if "quote" in value and "response_index" in value:
            require(
                value["quote"] in originals[value["response_index"]],
                "receipt.exact_original_public_quote",
            )
        for child in value.values():
            verify_quotes(child, originals)
    elif isinstance(value, list):
        for child in value:
            verify_quotes(child, originals)


def main(root):
    out = root / OUTPUT
    phases = {
        name: manifest(out / name)["id"]
        for name in ("preparation", "online", "assessment", "closeout")
    }
    implementation = read_json(out / "preparation/implementation.json")
    verify_source_snapshot(root, implementation)
    guard = history_guard(root)
    controls = read_json(out / "preparation/new_controls.json")
    require(controls["exit_code"] == 0, "receipt.pre_call_controls_pass")
    for path, digest in controls["test_sha256"].items():
        require(sha((root / path).read_bytes()) == digest, "receipt.frozen_test_bytes")
    require(
        "85 passed" in (out / "preparation/new_controls_stdout.txt").read_text(),
        "receipt.recorded_85_controls",
    )
    report = read_json(out / "closeout/report.json")
    measurement = read_json(out / "closeout/measurement.json")
    archive = read_json(out / "closeout/raw_packages/index.json")
    summary = read_json(out / "online/summary.json")
    registrations = read_json(out / "preparation/registrations.json")
    regs = {r["label"]: r for r in registrations}
    rows = {r["label"]: r for r in report["rows"]}
    reviews = read_json(out / "review_parts/reviews.json")
    decisions = {r["review_id"]: r for r in read_json(out / "review_parts/decisions.json")["rows"]}
    require(
        (out / "review_parts/reviews.json").read_bytes()
        == (out / "closeout/posthoc_reviews.original.json").read_bytes(),
        "receipt.review_parts_match_sealed_closeout_copy",
    )
    require(set(rows) == set(regs) == set(LABELS), "receipt.exact_48_new_registrations")
    counters, models, status_codes = Counter(), Counter(), Counter()
    outcomes, reservations, positive_kinds = [], [], Counter()
    for label in LABELS:
        registration, row = regs[label], rows[label]
        rid, arm, key = registration["review_id"], registration["arm"], registration["task_key"]
        require(row["review_id"] == rid, "receipt.pre_registered_mask_identity")
        require(
            row["formula_driven_trace_verified"]
            == decisions[rid]["expected_joint_valid_under_frozen_implementation"],
            "receipt.sealed_author_decision_join",
        )
        directory = out / "online/sessions" / label
        manifest(directory)
        result = read_json(directory / "result.json")
        require(
            result["terminal"] == "model_final"
            and result["origin"] == "live_http"
            and result["requested_model"] == MODEL,
            "receipt.all_real_first_Final",
        )
        public = read_json(out / f"preparation/public/{key}.json")
        originals = {}
        for event in result["events"]:
            index = event["response_index"]
            prefix = directory / f"turns/{index:03d}"

            def file(suffix, *, base=prefix):
                return base.with_name(base.name + suffix)

            raw = file("_assistant.raw").read_bytes()
            originals[index] = raw.decode()
            request = file("_http_request.body").read_bytes()
            decoded = json.loads(request)
            reservation = read_json(file("_reservation.json"))
            outcome = read_json(file("_outcome.json"))
            projection = read_json(file("_response_projection.json"))
            require(
                decoded["model"] == reservation["requested_model"] == outcome["model"] == MODEL
                and outcome["http_status"] == 200
                and outcome["error"] is None
                and sha(request) == reservation["request_sha256"] == outcome["request_sha256"]
                and reservation["id"] == outcome["reservation_id"]
                and sha(raw) == event["raw_sha256"]
                and sha(raw) == decisions[rid]["all_original_public_response_sha256"][str(index)]
                and projection["choices"][0]["message"]["content"].encode() == raw,
                "receipt.original_request_response_event_join",
            )
            require(
                decoded["messages"][0] == {"role": "system", "content": SYSTEMS_NEW[arm]}
                and decoded["messages"][1]
                == {"role": "user", "content": encode({"task": public}).decode()},
                "receipt.exact_conditional_SYSTEM_and_common_public_task",
            )
            require(
                "reasoning_content" not in projection["choices"][0]["message"],
                "receipt.dedicated_private_reasoning_field_not_stored",
            )
            if index == 0:
                require(len(decoded["messages"]) == 2, "receipt.empty_independent_history")
            call = event["tool_call"]
            if call:
                require(call["name"] == "calculate", "receipt.only_observed_calculate_tool")
                counters["calculate_" + call["output"]["status"]] += 1
            elif event["final"]:
                counters["Final"] += 1
            elif event["protocol_error"] is not None:
                counters["protocol_error"] += 1
            else:
                counters["message_only"] += 1
            status_codes[str(outcome["http_status"])] += 1
            models[outcome["model"]] += 1
            reservations.append(reservation)
            outcomes.append(outcome)
        verify_quotes(reviews[rid], originals)
        require(
            str(reviews[rid]["published_value"]) == str(result["final"]["value"])
            and reviews[rid]["published_unit"] == result["final"]["unit"] == "USD_million",
            "receipt.original_explicit_Final_fields_not_replaced",
        )
    require(len(outcomes) == summary["model_requests"] == 116, "receipt.actual_116")
    require(
        counters
        == {
            "calculate_ok": 48,
            "calculate_error": 3,
            "Final": 48,
            "protocol_error": 3,
            "message_only": 14,
        },
        "receipt.every_public_response_accounted",
    )
    cells = {}
    expected = {
        ("N", "X1"): (7, 7, 0, 0),
        ("E", "X1"): (8, 8, 0, 0),
        ("N", "X2"): (8, 8, 0, 0),
        ("E", "X2"): (8, 7, 1, 0),
        ("N", "X3C"): (8, 4, 0, 4),
        ("E", "X3C"): (8, 5, 0, 3),
    }
    for arm in ARMS:
        cells[arm] = {}
        for key in TASKS:
            task = measurement["populations"][arm]["tasks"][key]
            counts = task["complete_behavior_counts"]
            require(
                (
                    task["valid_count"],
                    task["pure_D_count"],
                    task["pure_R_count"],
                    counts.get("OTHER_VALID_CLASS", 0),
                )
                == expected[(arm, key)]
                and task["registered"] == 8
                and task["mapping_unresolved_labels"] == []
                and task["historical_four_per_class_count_threshold_met"] is False,
                "receipt.condition_cell_counts_and_no_training_gate",
            )
            cells[arm][key] = {
                name: task[name]
                for name in (
                    "registered",
                    "valid_count",
                    "valid_yield",
                    "quantity_counts",
                    "format_counts",
                    "R_mention_status_counts",
                    "R_execution_status_counts",
                    "R_source_relation_status_counts",
                    "R_Final_support_status_counts",
                    "confirmed_R_execution_yield",
                    "valid_pure_R_yield",
                    "complete_behavior_counts",
                    "within_condition_valid_pair_status_counts",
                )
            }
    require(
        archive["registered_original_archives"] == 48
        and archive["valid_original_packages"] == 47
        and archive["positive_response_count"] == 107
        and archive["tokenizer_loaded"] is False
        and archive["token_consumability"] == "NOT_MEASURED",
        "receipt.only_unweighted_original_packages_no_tokenizer",
    )
    for package in archive["packages"]:
        label = package["label"]
        require(
            package["actual_condition_prefix_removed_or_rewritten"] is False
            and package["training_weights_assigned"] is False,
            "receipt.no_prefix_removal_or_weights",
        )
        for positive in package["positive_responses"]:
            prefix = out / "closeout" / positive["path_prefix"]
            candidate = read_json(Path(str(prefix) + ".candidate.json"))
            target = Path(str(prefix) + ".target.raw").read_bytes()
            turn_prefix = (
                out / "online/sessions" / label / "turns" / f"{positive['response_index']:03d}"
            )
            actual = Path(str(turn_prefix) + "_assistant.raw").read_bytes()
            request = read_json(Path(str(turn_prefix) + "_http_request.body"))
            require(
                target == actual == candidate["target_response"].encode()
                and candidate["input_messages"] == request["messages"]
                and candidate["input_messages"][0]["content"] == SYSTEMS_NEW[package["arm"]],
                "receipt.each_original_conditional_prefix_and_target_preserved",
            )
            positive_kinds[candidate["response_kind"]] += 1
    require(
        positive_kinds == {"calculate": 47, "Final": 47, "message": 13},
        "receipt.107_original_positive_rows",
    )
    pairs = Counter(p["status"] for p in measurement["within_condition_valid_pairs"])
    require(pairs == {"EQUIVALENT": 123, "DISTINCT": 38}, "receipt.161_within_condition_pairs")
    witness = read_json(out / "closeout/R_chain/E_X2_01.json")
    require(
        witness["R_execution_status"] == "CONFIRMED"
        and witness["R_source_relation_status"] == "PASS"
        and witness["R_Final_support_status"] == "CONFIRMED"
        and witness["valid_pure_R"] is True
        and witness["actual_R_calculation_ids"] == ["tool:1"],
        "receipt.real_E_X2_01_R_witness",
    )
    affected = rows["N_X1_03"]
    interpretation = affected["answer"]["interpretation"]
    conflict = interpretation["conflicts"][0]
    final = interpretation["raw_Final"]
    require(
        affected["review_id"] == "review_018"
        and affected["trace_status"] == "FAIL"
        and final["unit"] == "USD_million"
        and Fraction(str(final["value"])) == Fraction("46.4")
        and conflict["quote"] == "$46.4"
        and conflict["interpretation"]["scale"] == "1"
        and final["answer"][conflict["span"][1]] == "M"
        and affected["semantic_review"]["quantity_policy_limitation"][
            "frozen_score_retained_without_regrading"
        ],
        "receipt.known_partial_M_parser_failure_retained_not_financial_error",
    )
    usage = {
        key: sum(o["usage"][key] for o in outcomes)
        for key in (
            "prompt_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
            "completion_tokens",
            "total_tokens",
        )
    }
    usage["reasoning_tokens"] = sum(
        o["usage"]["completion_tokens_details"]["reasoning_tokens"] for o in outcomes
    )
    for field, value in usage.items():
        require(
            value == report["costs"]["aggregate"]["provider_usage"][field]["complete_sum"],
            "receipt.complete_usage_sum",
        )
    prices = {}
    for arm in ARMS:
        prices[arm] = str(
            sum(
                (
                    Decimal(row["registered_rate_estimate_cny"])
                    for row in report["costs"]["rows"]
                    if row["arm"] == arm
                ),
                Decimal(0),
            )
        )
    require(
        sum(map(Decimal, prices.values())) == Decimal("0.5005188"),
        "receipt.registered_conditional_cost_sum",
    )
    require(
        report["actual_training_runs"]
        == report["actual_Student_sessions"]
        == report["auxiliary_NLL"]
        == report["provider_calls_after_collection"]
        == 0
        and report["tokenizer_loaded"] is False
        and report["training_selection"] == [],
        "receipt.all_downstream_work_not_run",
    )
    receipt = {
        "schema": "NE_posthoc_readonly_verification.v1",
        "freeze_commit": implementation["source_commit"],
        "phase_manifests": phases,
        "all_48_session_manifests_verified": True,
        "frozen_source_and_test_bytes_unchanged": True,
        "history_guard": guard,
        "saved_pre_call_controls_passed": 85,
        "new_models_or_scores_or_tokens_replayed": False,
        "report_id": report["id"],
        "measurement_id": measurement["id"],
        "raw_package_index_id": archive["id"],
        "actual_sessions": 48,
        "actual_generation_requests": 116,
        "observed_response_models": dict(models),
        "http_status_counts": dict(status_codes),
        "public_event_counts": dict(counters),
        "positive_row_kind_counts": dict(positive_kinds),
        "cells": cells,
        "within_condition_pair_counts": dict(pairs),
        "actual_R_witness_label": "E_X2_01",
        "actual_R_witness_review_id": "review_014",
        "known_quantity_parser_defect": {
            "label": "N_X1_03",
            "review_id": "review_018",
            "raw_Final_value": final["value"],
            "raw_Final_unit": final["unit"],
            "raw_Final_answer": final["answer"],
            "partially_matched_quote": conflict["quote"],
            "matched_span": conflict["span"],
            "ignored_following_character": "M",
            "misinterpreted_scale": "1",
            "explicit_primary_scale": "1000000",
            "frozen_FAIL_not_overridden": True,
            "not_a_confirmed_model_financial_or_arithmetic_error": True,
            "operational_scope_status_does_not_certify_quantity_parser_conformance": True,
            "not_evidence_of_E_financial_quality_advantage": True,
        },
        "provider_usage": usage,
        "registered_rate_estimated_CNY_by_condition": prices,
        "registered_rate_estimated_CNY_total": "0.5005188",
        "estimate_not_reverified_current_price_or_invoice": True,
        "first_reservation_utc": min(r["started_utc"] for r in reservations),
        "last_reservation_utc": max(r["started_utc"] for r in reservations),
        "collection_wall_seconds": summary["parallel_collection_wall_seconds"],
        "Student_status": "NOT_RUN",
        "training_input_status": "NOT_INSTANTIATED",
        "token_consumability": "NOT_MEASURED",
        "original_N_E_prefixes_kept_in_all_positive_candidates": True,
        "review_quotes_match_original_public_content": True,
        "reviewer_not_independent_or_guaranteed_fully_blinded": True,
    }
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main(Path.cwd())
