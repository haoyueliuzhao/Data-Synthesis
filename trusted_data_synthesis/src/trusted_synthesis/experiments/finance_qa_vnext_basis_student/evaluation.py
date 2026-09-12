"""Public generation first; separate offline scoring of sealed original sessions.

The generation branch opens PublicOverlay only. OfflineOverlay and assessment
are imported and instantiated exclusively inside score(), after generation is
complete and manifest-bound. No private fixture is ever prepared for generation.
"""

import json
import os
from collections import Counter
from pathlib import Path

from ..finance_qa_vnext_eval_readiness import runtime
from ..finance_qa_vnext_eval_surface.overlay import PublicOverlay
from .decoder import ACTUAL, BoundDecoder, validate_model_identity
from .protocol import (
    BINDING_FIELDS,
    checked_record,
    path_within,
    read_json,
    record,
    require,
    sha,
    write_once,
)

QUOTAS = {
    "dev": {"dual_sufficient": 60, "composition_required": 60, "other_financial": 60},
    "confirm": {"dual_sufficient": 240, "composition_required": 240, "other_financial": 240},
}


def _binding(identity):
    return {
        key: identity[key]
        for key in (*BINDING_FIELDS, "pool", "arm", "seed", "checkpoint_id", "training_report_id")
    }


def _output(root, value, *, absent):
    root = Path(root).resolve()
    value = Path(value)
    relative = value.relative_to(root) if value.is_absolute() else value
    output = path_within(root, relative)
    require(
        output != root and not any(part.is_symlink() for part in (output, *output.parents)),
        "evaluation.dedicated_non_symlink_output",
    )
    require(not absent or not output.exists(), "evaluation.no_reexecution_or_overwrite")
    return output


def seal_output(output, phase, report):
    output = Path(output)
    require(not (output / "manifest.json").exists(), "evaluation.one_manifest")
    files = []
    for path in sorted(output.rglob("*")):
        require(not path.is_symlink(), "evaluation.no_symlink_members")
        if path.is_file():
            files.append(
                {
                    "path": str(path.relative_to(output)),
                    "bytes": path.stat().st_size,
                    "sha256": sha(path),
                }
            )
    manifest = record(
        "evaluation_manifest",
        phase=phase,
        report_id=report["id"],
        members=files,
        self_excluding=True,
    )
    write_once(output / "manifest.json", manifest)
    return manifest


def verify_output(output, expected_manifest_id=None):
    require(
        not any(part.is_symlink() for part in (Path(output), *Path(output).parents)),
        "evaluation.non_symlink_sealed_output",
    )
    output = Path(output).resolve()
    manifest = read_json(output / "manifest.json")
    checked_record(manifest, "evaluation_manifest")
    require(
        expected_manifest_id is None or expected_manifest_id == manifest["id"],
        "evaluation.manifest_identity_pin",
    )
    members = {row["path"]: row for row in manifest["members"]}
    actual = {
        str(path.relative_to(output))
        for path in output.rglob("*")
        if path.is_file() and path != output / "manifest.json"
    }
    require(
        manifest["self_excluding"] is True
        and len(members) == len(manifest["members"])
        and set(members) == actual,
        "evaluation.complete_manifest_members",
    )
    for name, row in members.items():
        path = path_within(output, name)
        require(
            not any(part.is_symlink() for part in (path, *path.parents))
            and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            "evaluation.actual_saved_member_bytes",
        )
    report = read_json(output / "report.json")
    require(report["id"] == manifest["report_id"], "evaluation.sealed_report_identity")
    return manifest


def generate(
    root, output, *, surface_directory, surface_manifest_id, split, model_identity, decoder
):
    """One complete original split, no private references, no assessment feedback."""
    validate_model_identity(model_identity)
    require(
        isinstance(decoder, BoundDecoder) and decoder.identity == model_identity,
        "evaluation.bound_decoder_required",
    )
    require(
        split in QUOTAS and (split != "dev" or model_identity["pool"] == "A"),
        "evaluation.registered_split_and_no_B_dev",
    )
    require(
        surface_manifest_id == model_identity["surface_manifest_id"],
        "evaluation.frozen_final_common_surface",
    )
    root = Path(root).resolve()
    output = _output(root, output, absent=True)
    require(decoder.output == output / "decoder", "evaluation.decoder_receipts_in_same_manifest")
    public = PublicOverlay(root, surface_directory, surface_manifest_id)
    tasks = [row for row in public.catalog["tasks"] if row["split"] == split]
    require(
        dict(Counter(row["family"] for row in tasks)) == QUOTAS[split]
        and len({row["task_id"] for row in tasks}) == len(tasks),
        "evaluation.full_fixed_split_denominator",
    )
    write_once(output / "model_identity.json", model_identity)
    write_once(output / "decoder_config.json", decoder.configuration)
    write_once(output / "model_load_receipt.json", decoder.load_receipt)
    write_once(
        output / "registration.json",
        record(
            "generation_registration",
            **_binding(model_identity),
            split=split,
            surface_directory=str(surface_directory),
            surface_manifest_id_authority=surface_manifest_id,
            task_ids=[row["task_id"] for row in tasks],
            quotas=QUOTAS[split],
            public_catalog_id=public.catalog["id"],
            requested_basis="neutral",
            process_id=os.getpid(),
            private_task_bundles_opened=0,
        ),
    )
    results, failure = [], None
    for row in tasks:
        task_id = row["task_id"]
        try:
            envelope = public.public_envelope(task_id)
            visible = json.loads(envelope["messages"][0]["content"])
            descriptors = visible["source_document"]
            descriptors = [descriptors] if isinstance(descriptors, dict) else descriptors
            sources = runtime.SnapshotSources(root, descriptors)
            before = decoder.snapshot()
            first_receipt = len(decoder.receipts)
            session = runtime.generate(
                envelope["messages"],
                envelope["identity"],
                sources,
                provider=decoder,
                requested_basis="neutral",
                max_responses=32,
                max_tools=32,
            )
            receipts = decoder.receipts[first_receipt:]
            after = decoder.snapshot()
            require(
                session["provider_calls"]
                == len(receipts)
                == after["callback_attempts"] - before["callback_attempts"],
                "evaluation.all_attempted_callbacks_including_context_rejections",
            )
            path = Path("sessions") / task_id
            write_once(output / path / "runtime_session.json", session)
            result = record(
                "public_generation_result",
                **_binding(model_identity),
                task_id=task_id,
                split=split,
                group=row["family"],
                source_cluster=visible["period_contract"]["source_cluster"],
                surface_version_id=envelope["identity"]["surface_version_id"],
                public_messages_sha256=envelope["identity"]["public_messages_sha256"],
                runtime_session_id=session["id"],
                runtime_session_path=str(path / "runtime_session.json"),
                requested_basis="neutral",
                terminal=session["terminal"],
                context_rejected=after["context_rejections"] > before["context_rejections"],
                decoder_receipts=[
                    {
                        "id": item["id"],
                        "callback_index": item["callback_index"],
                        "path": f"decoder/callback_{item['callback_index']:06d}/receipt.json",
                    }
                    for item in receipts
                ],
                callback_attempts=session["provider_calls"],
                resource_delta={key: after[key] - before[key] for key in decoder.counters},
                runtime_resource_fields_are_runtime_scope_only=True,
                model_identity_id=model_identity["id"],
                execution_kind=decoder.execution_kind,
                private_task_bundles_opened=0,
                assessment_returned_online=False,
                actual_generation_fault=decoder.fatal_error,
            )
            write_once(output / path / "result.json", result)
            results.append(
                {
                    "task_id": task_id,
                    "result_id": result["id"],
                    "result_path": str(path / "result.json"),
                    "terminal": session["terminal"],
                }
            )
            if decoder.fatal_error:
                failure = record(
                    "generation_failure",
                    task_id=task_id,
                    error=decoder.fatal_error,
                    remaining_tasks_not_started=True,
                    retry_performed=False,
                )
                break
        except Exception as error:
            failure = record(
                "generation_failure",
                task_id=task_id,
                error_type=type(error).__name__,
                error=str(error),
                remaining_tasks_not_started=True,
                retry_performed=False,
            )
            break
    if failure:
        write_once(output / "failure.json", failure)
    complete = failure is None and len(results) == len(tasks)
    actual = complete and decoder.execution_kind == ACTUAL
    report = record(
        "generation_report",
        **_binding(model_identity),
        model_identity_id=model_identity["id"],
        split=split,
        status="COMPLETE_FIXED_GENERATION"
        if actual
        else "SYNTHETIC_GENERATION_CONTROL"
        if complete
        else "INCOMPLETE_GENERATION",
        actual_complete=actual,
        complete_registered_denominator=complete,
        requested_task_count=len(tasks),
        completed_task_count=len(results),
        results=results,
        terminal_counts=dict(Counter(row["terminal"] for row in results)),
        execution_kind=decoder.execution_kind,
        resource_usage=decoder.snapshot(),
        failure_id=failure["id"] if failure else None,
        private_task_bundles_opened=0,
        assessment_calls=0,
        training_eligible=False,
        model_weights_updated=False,
        requested_basis="neutral",
        no_private_fixture_constructed=True,
    )
    write_once(output / "report.json", report)
    seal_output(output, "public_generation", report)
    return report


def verify_generation_records(generation, report, identity):
    """Public-only receipt/accounting joins before opening private task data."""
    configuration = read_json(generation / "decoder_config.json")
    checked_record(configuration, "decoder_config")
    require(
        configuration["id"] == identity["decoder_config_id"], "evaluation.decoder_config_identity"
    )
    load = read_json(generation / "model_load_receipt.json")
    checked_record(load, "model_load_receipt")
    require(
        load["model_identity_id"] == identity["id"]
        and load["execution_kind"] == ACTUAL
        and load["restored_checkpoint_id"] == identity["checkpoint_id"]
        and all(
            load[key] == 1
            for key in ("model_weight_loads", "final_adapter_loads", "tokenizer_loads", "GPU_loads")
        ),
        "evaluation.actual_final_model_and_tokenizer_loads",
    )
    aggregate, seen = Counter(), set()
    for item in report["results"]:
        result = read_json(path_within(generation, item["result_path"]))
        checked_record(result, "public_generation_result")
        require(
            result["id"] == item["result_id"]
            and result["model_identity_id"] == identity["id"]
            and result["execution_kind"] == ACTUAL
            and result["actual_generation_fault"] is None
            and all(result[key] == value for key, value in _binding(identity).items()),
            "evaluation.actual_public_model_result",
        )
        session = read_json(path_within(generation, result["runtime_session_path"]))
        require(
            session["id"] == result["runtime_session_id"]
            and session["identity"]["task_id"] == result["task_id"] == item["task_id"]
            and session["origin"] == "live_evaluation_callback"
            and session["requested_basis"] == result["requested_basis"] == "neutral"
            and session["max_responses"] == session["max_tools"] == 32,
            "evaluation.live_neutral_original_runtime_session",
        )
        require(
            len(result["decoder_receipts"])
            == result["callback_attempts"]
            == session["provider_calls"],
            "evaluation.every_callback_has_one_saved_receipt",
        )
        turns = {turn["response_index"]: turn for turn in session["turns"]}
        for response_index, reference in enumerate(result["decoder_receipts"]):
            receipt = read_json(path_within(generation, reference["path"]))
            checked_record(receipt, "decoder_receipt")
            index = receipt["callback_index"]
            require(
                index not in seen
                and reference["id"] == receipt["id"]
                and reference["path"] == f"decoder/callback_{index:06d}/receipt.json"
                and receipt["model_identity_id"] == identity["id"]
                and receipt["checkpoint_id"] == identity["checkpoint_id"]
                and receipt["surface_manifest_id"] == identity["surface_manifest_id"]
                and receipt["decoder_config_id"] == configuration["id"]
                and receipt["execution_kind"] == ACTUAL
                and receipt["context"]["identity"] == session["identity"]
                and receipt["context"]["response_index"] == response_index,
                "evaluation.one_bound_actual_decoder_receipt",
            )
            seen.add(index)
            aggregate["callback_attempts"] += 1
            aggregate["tokenization_calls"] += 1
            request = read_json(generation / f"decoder/callback_{index:06d}/request.json")
            checked_record(request, "decoder_request")
            require(
                request["model_identity"] == identity
                and request["context"] == receipt["context"]
                and len(request["input_token_ids"]) == receipt["prompt_token_count"]
                and sha(request["rendered_prompt"]) == request["rendered_prompt_sha256"],
                "evaluation.actual_public_prompt_receipt_join",
            )
            if receipt["finish_reason"] == "context_rejected_before_model_generate":
                require(
                    not receipt["model_generation_invoked"]
                    and not receipt["GPU_generation_invoked"]
                    and not receipt["model_generation_completed"]
                    and receipt["generated_token_ids"] == []
                    and receipt["prompt_token_count"] + 2048 > 24576
                    and response_index == len(turns) == len(result["decoder_receipts"]) - 1
                    and session["terminal"] == "provider_error",
                    "evaluation.context_rejection_has_no_model_response",
                )
                aggregate["context_rejections"] += 1
                continue
            require(
                receipt["finish_reason"]
                in {"actual_EOS", "new_token_limit", "model_stopped_without_EOS"}
                and receipt["model_generation_invoked"] is True
                and receipt["model_generation_completed"] is True
                and receipt["GPU_generation_invoked"] is True
                and receipt["prompt_token_count"] + 2048 <= 24576
                and response_index in turns,
                "evaluation.actual_bounded_model_generation",
            )
            turn = turns[response_index]
            require(
                turn["provider_receipt"] == receipt
                and turn["raw_response"] == receipt["raw_response"]
                and turn["raw_response_sha256"] == receipt["raw_response_sha256"]
                and request["input_messages"] == turn["input_messages"],
                "evaluation.complete_raw_output_and_original_history",
            )
            generated, content = receipt["generated_token_ids"], receipt["public_content_token_ids"]
            ended = bool(generated) and generated[-1] in configuration["eos_token_ids"]
            require(
                receipt["generated_token_count"] == len(generated) <= 2048
                and receipt["actual_terminating_EOS_removed"] == ended
                and content == (generated[:-1] if ended else generated),
                "evaluation.only_actual_last_EOS_removed",
            )
            for key in (
                "model_generate_api_calls",
                "actual_model_generation_calls",
                "actual_GPU_generation_calls",
                "completed_generation_calls",
            ):
                aggregate[key] += 1
            aggregate["generated_tokens"] += len(generated)
            aggregate["public_content_tokens"] += len(content)
    usage = report["resource_usage"]
    for key in (
        "callback_attempts",
        "tokenization_calls",
        "model_generate_api_calls",
        "actual_model_generation_calls",
        "actual_GPU_generation_calls",
        "completed_generation_calls",
        "context_rejections",
        "generated_tokens",
        "public_content_tokens",
    ):
        require(
            usage[key] == aggregate[key], "evaluation.actual_worker_resource_reconciliation:" + key
        )
    require(
        usage["load_receipt_id"] == load["id"]
        and usage["model_weight_loads"] == 1
        and usage["final_adapter_loads"] == 1
        and usage["tokenizer_loads"] == 1
        and usage["GPU_model_loads"] == 1
        and usage["callback_failures"] == 0
        and usage["synthetic_model_generation_calls"] == 0
        and usage["fatal_error"] is None,
        "evaluation.no_runtime_zeroes_or_mock_counts_as_actual_worker",
    )
    return dict(aggregate)


def score(root, generation_directory, output, *, expected_generation_manifest_id):
    """Separate offline stage; no model/decoder callback occurs at this boundary."""
    # Deliberately local: the public-generation path must never construct this capability.
    from ..finance_qa_vnext_eval_readiness.assessment import assess_session
    from ..finance_qa_vnext_eval_surface.overlay import OfflineOverlay

    root = Path(root).resolve()
    generation = _output(root, generation_directory, absent=False)
    manifest = verify_output(generation, expected_generation_manifest_id)
    require(manifest["phase"] == "public_generation", "evaluation.original_generation_phase")
    before = read_json(generation / "report.json")
    checked_record(before, "generation_report")
    require(
        before["status"] == "COMPLETE_FIXED_GENERATION"
        and before["actual_complete"] is True
        and before["execution_kind"] == ACTUAL
        and before["failure_id"] is None,
        "evaluation.only_complete_actual_generation_scored",
    )
    identity = read_json(generation / "model_identity.json")
    validate_model_identity(identity)
    require(
        before["model_identity_id"] == identity["id"]
        and all(before[key] == value for key, value in _binding(identity).items()),
        "evaluation.exact_final_checkpoint_generation_identity",
    )
    registration = read_json(generation / "registration.json")
    checked_record(registration, "generation_registration")
    require(
        registration["process_id"] != os.getpid(), "evaluation.offline_distinct_from_model_process"
    )
    verify_generation_records(generation, before, identity)
    split = before["split"]
    require(
        split in QUOTAS
        and before["requested_task_count"]
        == before["completed_task_count"]
        == len(before["results"])
        == sum(QUOTAS[split].values()),
        "evaluation.complete_original_scoring_denominator",
    )
    offline = OfflineOverlay(
        root, registration["surface_directory"], identity["surface_manifest_id"]
    )
    expected = [row["task_id"] for row in offline.public.catalog["tasks"] if row["split"] == split]
    require(
        expected == registration["task_ids"] == [row["task_id"] for row in before["results"]],
        "evaluation.original_complete_task_order",
    )
    output = _output(root, output, absent=True)
    outcomes = []
    for item in before["results"]:
        result = read_json(path_within(generation, item["result_path"]))
        checked_record(result, "public_generation_result")
        require(
            result["id"] == item["result_id"] and result["model_identity_id"] == identity["id"],
            "evaluation.saved_public_result_join",
        )
        session = read_json(path_within(generation, result["runtime_session_path"]))
        require(session["id"] == result["runtime_session_id"], "evaluation.actual_saved_session")
        task_id = item["task_id"]
        # This is the first private bundle construction, after generation was closed.
        fixture = offline.fixture(task_id)
        require(
            session["identity"] == fixture["identity"]
            and result["group"] == fixture["identity"]["family"]
            and result["surface_version_id"] == fixture["identity"]["surface_version_id"]
            and result["public_messages_sha256"] == fixture["identity"]["public_messages_sha256"]
            and result["source_cluster"]
            == fixture["bundle"]["public"]["period_contract"]["source_cluster"],
            "evaluation.same_final_public_surface",
        )
        assessment = assess_session(
            session, fixture["bundle"], fixture["native_bindings"], fixture["sources"]
        )
        path = Path("assessments") / (task_id + ".json")
        write_once(output / path, assessment)
        require(
            assessment["financial_valid"] is assessment["complete_trajectory_qualified"],
            "evaluation.primary_complete_financial_qualification",
        )
        outcomes.append(
            {
                "task_id": task_id,
                "group": result["group"],
                "source_cluster": result["source_cluster"],
                "surface_version_id": result["surface_version_id"],
                "public_messages_sha256": result["public_messages_sha256"],
                "financial_valid": assessment["financial_valid"],
                "complete_trajectory_qualified": assessment["complete_trajectory_qualified"],
                "quantity_status": assessment["quantity_status"],
                "support_status": assessment["support_status"],
                "actual_method": assessment["actual_method"],
                "full_mapping_status": assessment["full_mapping_status"],
                "reason": assessment["reason"],
                "assessment_id": assessment["id"],
                "assessment_path": str(path),
                "generation_result_id": result["id"],
                "runtime_terminal": session["terminal"],
                "context_rejected": result["context_rejected"],
            }
        )
    require(
        dict(Counter(row["group"] for row in outcomes)) == QUOTAS[split],
        "evaluation.all_outcomes_keep_original_groups",
    )
    groups = {
        group: {
            "qualified": sum(row["financial_valid"] for row in outcomes if row["group"] == group),
            "total": count,
        }
        for group, count in QUOTAS[split].items()
    }
    report = record(
        "evaluation_report",
        **_binding(identity),
        status="COMPLETE_FIXED_EVALUATION",
        actual_complete=True,
        split=split,
        model_identity_id=identity["id"],
        generation_manifest_id=manifest["id"],
        generation_report_id=before["id"],
        outcomes=outcomes,
        task_count=len(outcomes),
        group_counts=groups,
        primary_utility=sum(row["qualified"] / row["total"] for row in groups.values()) / 3,
        primary_metric="three equally weighted group means of complete trajectory qualification",
        unknown_missing_Final_and_errors_in_denominator=True,
        fine_mapping_required_for_primary=False,
        actual_model_resource_usage=before["resource_usage"],
        scoring_model_loads=0,
        scoring_GPU_calls=0,
        scoring_provider_calls=0,
        scoring_private_bundles_opened=len(outcomes),
        scoring_process_id=os.getpid(),
        generation_process_id=registration["process_id"],
        private_loaded_only_after_sealed_actual_generation=True,
        training_eligible=False,
    )
    write_once(output / "report.json", report)
    seal_output(output, "offline_score", report)
    return report
