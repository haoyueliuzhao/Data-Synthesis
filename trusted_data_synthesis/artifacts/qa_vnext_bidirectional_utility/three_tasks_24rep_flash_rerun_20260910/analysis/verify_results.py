"""Read-only result joins; no generation, requalification, tool replay or tokenization.

Written after closeout, not part of the preregistered decision code. The JSON
printed by this script is a reporting receipt, not a replacement for sealed data.
"""

import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.plan import (
    LABELS,
    OUTPUT,
    PRIOR_OUTPUT,
    history_guard,
    read_json,
    require,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    verify_source_snapshot,
)


def check_quotes(value, originals):
    if isinstance(value, dict):
        if "quote" in value and "response_index" in value:
            require(
                value["quote"] == originals[value["response_index"]],
                "receipt.verbatim_review_quote",
            )
        for child in value.values():
            check_quotes(child, originals)
    elif isinstance(value, list):
        for child in value:
            check_quotes(child, originals)


def main(root):
    out = root / OUTPUT
    phases = {
        name: manifest(out / name)["id"]
        for name in ("preparation", "online", "assessment", "closeout")
    }
    implementation = read_json(out / "preparation/implementation.json")
    verify_source_snapshot(root, implementation)
    historical = history_guard(root)
    tests = read_json(out / "preparation/new_controls.json")
    require(tests["exit_code"] == 0, "receipt.controls_passed")
    for name, expected in tests["test_sha256"].items():
        require(sha((root / name).read_bytes()) == expected, "receipt.tests_unchanged")
    require(
        "44 passed" in (out / "preparation/new_controls_stdout.txt").read_text(),
        "receipt.saved_44_tests",
    )
    summary = read_json(out / "online/summary.json")
    report = read_json(out / "closeout/report.json")
    gate = read_json(out / "closeout/input_gate.json")
    measurement = read_json(out / "closeout/measurement.json")
    materialization = read_json(out / "closeout/materialization/index.json")
    reviews = read_json(out / "review_parts/reviews.json")
    decisions = read_json(out / "review_parts/decisions.json")["rows"]
    decisions = {row["label"]: row for row in decisions}
    rows = {row["label"]: row for row in report["rows"]}
    require(
        set(rows) == set(reviews) == set(decisions) == set(LABELS),
        "receipt.only_all_72_new_labels",
    )
    terminals, models, http, kinds = Counter(), Counter(), Counter(), Counter()
    reservations, outcomes = [], []
    quote_sessions = 0
    for label in LABELS:
        directory = out / "online/sessions" / label
        manifest(directory)
        result = read_json(directory / "result.json")
        terminals[result["terminal"]] += 1
        originals = {}
        for event in result["events"]:
            index = event["response_index"]
            prefix = directory / "turns" / f"{index:03d}"
            raw = Path(str(prefix) + "_assistant.raw").read_bytes()
            originals[index] = raw.decode()
            require(sha(raw) == event["raw_sha256"], "receipt.raw_event_binding")
            require(
                sha(raw) == decisions[label]["all_original_raw_response_sha256"][str(index)],
                "receipt.review_original_binding",
            )
            reservation = read_json(Path(str(prefix) + "_reservation.json"))
            outcome = read_json(Path(str(prefix) + "_outcome.json"))
            request = Path(str(prefix) + "_http_request.body").read_bytes()
            require(
                sha(request) == reservation["request_sha256"] == outcome["request_sha256"],
                "receipt.actual_request_binding",
            )
            require(
                json.loads(request)["model"]
                == reservation["requested_model"]
                == outcome["model"]
                == "deepseek-flash",
                "receipt.exact_Flash_request_response",
            )
            require(
                outcome["error"] is None and outcome["http_status"] == 200,
                "receipt.successful_transport",
            )
            reservations.append(reservation)
            outcomes.append(outcome)
            models[outcome["model"]] += 1
            http[str(outcome["http_status"])] += 1
            call = event["tool_call"]
            kind = (
                "Final"
                if event["final"]
                else "protocol_error"
                if event["protocol_error"]
                else "calculate_ok"
                if call and call["output"]["status"] == "ok"
                else "calculate_error"
                if call
                else "message_only"
            )
            if call:
                require(call["name"] == "calculate", "receipt.only_actual_calculator")
            kinds[kind] += 1
        require(
            reviews[label]["published_value"] == result["final"]["value"]
            and reviews[label]["published_unit"] == result["final"]["unit"],
            "receipt.no_Final_value_or_unit_override",
        )
        check_quotes(reviews[label], originals)
        quote_sessions += 1
        require(
            rows[label]["formula_driven_trace_verified"]
            == decisions[label]["expected_joint_valid_under_frozen_policy"],
            "receipt.author_decisions_match_sealed_qualification",
        )
    require(len(outcomes) == summary["model_requests"] == 167, "receipt.actual_167")
    require(dict(terminals) == {"model_final": 72}, "receipt.actual_72_Final")
    require(
        dict(kinds)
        == {
            "Final": 72,
            "calculate_ok": 76,
            "calculate_error": 6,
            "protocol_error": 2,
            "message_only": 11,
        },
        "receipt.complete_public_event_accounting",
    )
    rejected_unit = sum(row["raw_unit_dictionary_rejection"] for row in decisions.values())
    rejected_scope = sum(row["registered_period_mismatch"] for row in decisions.values())
    require((rejected_unit, rejected_scope) == (23, 22), "receipt.disjoint_exclusions")
    require(
        all(
            not (r["raw_unit_dictionary_rejection"] and r["registered_period_mismatch"])
            for r in decisions.values()
        ),
        "receipt.exclusion_sets_disjoint",
    )
    by_task = {}
    for key, task in measurement["populations"]["T"]["tasks"].items():
        classes = Counter(
            row["target_class"] for row in gate["observations"] if row["task_key"] == key
        )
        by_task[key] = {
            **report["by_task"][key],
            "target_D": classes["D"],
            "target_R": classes["R"],
            "other_valid_complete_classes": classes["OTHER_VALID_CLASS"],
            "mapped_count": task["mapped_count"],
            "mapping_unresolved_count": task["unresolved_count"],
            "observed_complete_class_count": task["known_class_count"],
            "valid_pair_count": task["valid_pair_count"],
            "valid_pair_status_counts": task["valid_pair_status_counts"],
        }
    require(
        [
            (r["target_D"], r["target_R"], r["other_valid_complete_classes"])
            for r in by_task.values()
        ]
        == [(20, 0, 0), (4, 0, 1), (2, 0, 0)],
        "receipt.actual_complete_target_classes",
    )
    require(
        gate["status"] == report["completion_status"] == "INPUT_INADEQUATE"
        and gate["selected_new_training_labels"] == []
        and gate["selected_same_task_diagnostic_labels"] == []
        and gate["would_train_packages"] == 0,
        "receipt.global_gate_closed",
    )
    require(
        not any(report[field] for field in ("downstream_started", "gpu", "student", "training"))
        and report["provider_calls_after_generation"] == 0,
        "receipt.downstream_not_run",
    )
    mat_rows = materialization["rows"]
    token_counts = {
        "valid_whole_packages": len(materialization["packages"]),
        "positive_rows": len(mat_rows),
        "positive_row_kinds": dict(Counter(row["response_kind"] for row in mat_rows)),
        "positive_target_tokens": sum(row["target_token_count"] for row in mat_rows),
        "encoded_sequence_positions": sum(row["sequence_length"] for row in mat_rows),
        "minimum_sequence_length": min(row["sequence_length"] for row in mat_rows),
        "maximum_sequence_length": max(row["sequence_length"] for row in mat_rows),
        "unfit_packages": sum(
            not p["whole_package_token_consumable"] for p in materialization["packages"]
        ),
        "training_weights_assigned": materialization["weights_assigned"],
        "tokenization_only_not_training_budget": True,
    }
    require(
        (
            token_counts["valid_whole_packages"],
            token_counts["positive_rows"],
            token_counts["positive_target_tokens"],
            token_counts["encoded_sequence_positions"],
        )
        == (27, 62, 10854, 349555),
        "receipt.materialization_totals",
    )
    require(
        token_counts["unfit_packages"] == 0
        and not materialization["weights_assigned"]
        and materialization["no_student_or_training"],
        "receipt.retained_packages_not_a_constructed_training_population",
    )
    usage = {
        key: sum(row["usage"][key] for row in outcomes)
        for key in (
            "prompt_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
            "completion_tokens",
            "total_tokens",
        )
    }
    usage["reasoning_tokens"] = sum(
        row["usage"]["completion_tokens_details"]["reasoning_tokens"] for row in outcomes
    )
    for key, total in usage.items():
        require(
            total == report["costs"]["aggregate"]["provider_usage"][key]["complete_sum"],
            "receipt.recorded_usage_join:" + key,
        )
    prior = read_json(root / PRIOR_OUTPUT / "closeout/report.json")
    prior_cost = prior["costs"]["registered_rate_estimate_cny"]
    new_cost = report["costs"]["registered_rate_estimate_cny"]
    receipt = {
        "schema_version": "flash_rerun_posthoc_readonly_result_receipt.v1",
        "decision_policy_changed": False,
        "provider_tool_qualification_or_tokenizer_replayed": False,
        "preregistered_source_commit": implementation["source_commit"],
        "all_frozen_source_members_unchanged": True,
        "phase_manifest_ids": phases,
        "all_72_session_manifests_verified": True,
        "history_guard": historical,
        "saved_new_controls_passed": 44,
        "report_id": report["id"],
        "measurement_id": measurement["id"],
        "input_gate_id": gate["id"],
        "materialization_index_id": materialization["id"],
        "actual_sessions": 72,
        "actual_generation_requests": len(outcomes),
        "separate_live_model_catalog_GET": 1,
        "terminals": dict(terminals),
        "observed_response_models": dict(models),
        "http_status_counts": dict(http),
        "public_event_counts": dict(kinds),
        "parallel_collection_wall_seconds": summary["parallel_collection_wall_seconds"],
        "first_request_reservation_utc": min(r["started_utc"] for r in reservations),
        "last_request_reservation_utc": max(r["started_utc"] for r in reservations),
        "original_quote_verified_sessions": quote_sessions,
        "by_task": by_task,
        "frozen_answer_counts": report["answer_counts"],
        "raw_unit_dictionary_rejections": rejected_unit,
        "registered_interval_mismatches": rejected_scope,
        "qualification_exclusions_not_all_arithmetic_errors": True,
        "primary_pair_status_counts": measurement["primary_pair_status_counts"],
        "missing_target_classes": gate["missing_target_classes"],
        "completion_status": gate["status"],
        "actual_training_runs": 0,
        "actual_Student_sessions": 0,
        "materialization_only": token_counts,
        "provider_usage": usage,
        "current_batch_registered_rate_estimate_CNY": new_cost,
        "previous_batch_registered_rate_estimate_CNY": prior_cost,
        "both_batches_registered_rate_estimate_CNY": str(Decimal(new_cost) + Decimal(prior_cost)),
        "estimates_not_reverified_current_tariff_or_invoice": True,
        "financial_semantic_review_is_not_independent_or_blinded": True,
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main(Path.cwd())
