"""Post-collection read-only-input diagnosis; never admits, executes or retries a reply."""

from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.plan import (
    LABELS,
    LIMITS,
    MODEL,
    OUTPUT,
    history_guard,
    read_json,
    record,
    require,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)


def main(root):
    output = root / OUTPUT
    with execution_guard(online=False) as counts:
        manifests = {
            part: manifest(output / part)["id"]
            for part in ("preparation", "online", "assessment", "closeout")
        }
        verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
        collection = read_json(output / "online/summary.json")
        closeout = read_json(output / "closeout/report.json")
        require(
            collection["all_workers_terminated"] and collection["registered"] == 72,
            "diagnose.after_all_collection",
        )
        require(
            closeout["completion_status"] == "INPUT_INADEQUATE", "diagnose.original_stop_result"
        )
        destination = output / "condition_diagnostic"
        require(not destination.exists(), "diagnose.no_overwrite")
        rows, started = [], []
        for label in LABELS:
            directory = output / "online/sessions" / label
            result = read_json(directory / "result.json")
            require(
                result["model_requests"]
                == result["model_responses"]
                == result["provider_attempts"]
                == 1,
                "diagnose.one_original_attempt",
            )
            request = read_json(directory / "turns/000_http_request.body")
            projection = read_json(directory / "turns/000_response_projection.json")
            outcome = read_json(directory / "turns/000_outcome.json")
            reservation = read_json(directory / "turns/000_reservation.json")
            raw = (directory / "turns/000_assistant.raw").read_bytes()
            choice = projection["choices"][0]
            message = choice["message"]
            allowed = [MODEL, MODEL + "-0731"]
            predicates = {
                "HTTP_200": outcome["http_status"] == 200,
                "projection_parse_ok": projection["parse_error"] is None,
                "object_chat_completion": projection["object"] == "chat.completion",
                "one_choice_index_zero": len(projection["choices"]) == 1 and choice["index"] == 0,
                "assistant_role": message["role"] == "assistant",
                "no_native_tool_calls": message["native_tool_calls_present"] is False,
                "finish_stop": choice["finish_reason"] == "stop",
                "nonempty_bounded_public_content": isinstance(message["content"], str)
                and 0 < len(raw) <= LIMITS["public_content_bytes"],
                "model_identity_in_frozen_allowed_set": projection["model"] in allowed,
            }
            failed = [name for name, passed in predicates.items() if not passed]
            require(
                failed == ["model_identity_in_frozen_allowed_set"],
                "diagnose.specific_original_predicate",
            )
            require(
                request["model"] == MODEL
                and request["thinking"] == {"type": "enabled"}
                and request["reasoning_effort"] == "high",
                "diagnose.original_requested_condition",
            )
            require(
                message["content"].encode() == raw
                and outcome["public_content_received"]
                and not outcome["public_content_returned"],
                "diagnose.received_not_admitted",
            )
            require(
                result["events"] == [] and result["tool_calls"] == 0 and result["final"] is None,
                "diagnose.no_execution_or_Final",
            )
            require(
                len(read_json(directory / "messages.json")) == 2,
                "diagnose.original_empty_history_not_extended",
            )
            require(
                outcome["error"] == "provider_envelope_or_condition_failure"
                and result["terminal"] == "unknown_transport_or_condition",
                "diagnose.original_unknown_result",
            )
            started.append(reservation["started_utc"])
            rows.append(
                dict(
                    label=label,
                    task_key=label.split("_")[1],
                    requested_model=MODEL,
                    observed_response_model=projection["model"],
                    allowed_response_models=allowed,
                    original_terminal=result["terminal"],
                    original_error=outcome["error"],
                    predicates=predicates,
                    failed_predicates=failed,
                    public_response_received=True,
                    public_response_admitted=False,
                    actual_tool_calls=0,
                    actual_Final=None,
                    original_result_id=result["id"],
                    response_projection_sha256=outcome["response_projection_sha256"],
                    public_raw_sha256=sha(raw),
                    public_raw_bytes=len(raw),
                    private_reasoning_body_read_or_stored=False,
                    session_path=str(directory.relative_to(root)),
                )
            )
        require(
            len(rows) == 72 and {r["observed_response_model"] for r in rows} == {"deepseek-flash"},
            "diagnose.actual_complete_population",
        )
        store = DurableStore(destination)
        store.json("rows.json", rows)
        documentation = {
            "lookup_date_UTC": "2026-09-10",
            "lookup_method": (
                "read-only public official-documentation search after all Teacher sessions; no "
                "inference call"
            ),
            "sources": [
                {
                    "url": "https://api-docs.deepseek.com/",
                    "title": "Your First API Call",
                    "observation": (
                        "Consulted page still documents caller model deepseek-v4-flash and "
                        "version DeepSeek-V4-Flash-0731. It does not establish that this "
                        "batch's response model deepseek-flash identifies those same weights."
                    ),
                },
                {
                    "url": "https://api-docs.deepseek.com/updates/",
                    "title": "Change Log",
                    "observation": (
                        "Consulted July 31 Flash entry describes an unchanged caller name "
                        "deepseek-v4-flash. This is not a provider confirmation of the observed "
                        "shortened response identifier."
                    ),
                },
            ],
            "underlying_response_model_equivalence_verified": False,
            "alias_change_is_a_possible_explanation_not_a_confirmed_fact": True,
            "metadata_only_cannot_identify_underlying_weights": True,
        }
        store.json("official_documentation_lookup.json", documentation)
        costs = closeout["costs"]
        report = record(
            "identity_failure_input_closeout",
            original_stage_manifest_ids=manifests,
            original_closeout_id=closeout["id"],
            completion_status="INPUT_INADEQUATE",
            more_specific_observed_cause="RESPONSE_MODEL_IDENTITY_UNCONFIRMED",
            original_terminal_category_unchanged=True,
            rows=rows,
            first_reservation_UTC=min(started),
            last_reservation_UTC=max(started),
            collection_wall_seconds=collection["parallel_collection_wall_seconds"],
            teacher_registered_sessions=72,
            actual_HTTP_requests=72,
            HTTP_200_responses=72,
            provider_public_responses_received=72,
            admitted_responses=0,
            actual_tool_calls=0,
            actual_first_Final_count=0,
            answer_status_counts=closeout["answer_counts"],
            original_full_trace_confirmed_count=closeout["valid_count"],
            by_task={
                key: dict(
                    registered=24,
                    answer_UNDETERMINED=24,
                    confirmed_valid=0,
                    target_D_eligible=0,
                    target_R_eligible=0,
                )
                for key in ("X1", "X2", "X3")
            },
            no_financial_failure_or_natural_D_R_probability_inference=True,
            frozen_worker_sha256=sha((output / "preparation/worker_code/worker.py").read_bytes()),
            new_training_runs=0,
            Student_evaluation_sessions=0,
            GPU_model_loads=0,
            new_valid_packages=0,
            positive_training_rows=0,
            target_token_arrays=0,
            provider_usage=costs["aggregate"]["provider_usage"],
            estimated_CNY_under_requested_model_registered_table=costs[
                "registered_rate_estimate_cny"
            ],
            observed_response_model_billing_identity_verified=False,
            actual_account_bill=None,
            actual_tokenizer_only_load_during_empty_materialization=True,
            provider_aliases_changed=False,
            rejected_texts_executed_or_replayed=False,
            post_collection_inference_requests=0,
            private_reasoning_text_stored=False,
            source_bound_39_questions_and_all_future_conditions_retained=True,
            assessment_and_closeout_financial_rows_not_regraded=True,
            diagnostic_scope=(
                "same-author artifact and frozen-predicate inspection; not independent provider "
                "or financial certification"
            ),
        )
        store.json("report.json", report)
        store.json("history_after.json", history_guard(root))
        store.json(
            "execution_guards.json",
            guard_report(counts, phase="post_collection_model_identity_inspection"),
        )
        seal_directory(store, kind="identity_diagnostic_manifest", report_id=report["id"])
        print(report["id"], flush=True)


if __name__ == "__main__":
    main(Path.cwd())
