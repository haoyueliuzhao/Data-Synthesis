"""Offline original qualification plus separately named structural/token diagnostics."""

from ..finance_qa_vnext_catalog_bridge.assessment import assess_replayed_session
from ..finance_qa_vnext_catalog_bridge.materials import load_local_tokenizer
from ..finance_qa_vnext_model_execution.representation import encode_original_candidate
from ..finance_qa_vnext_movement_support.signals import build_support_index, public_trace_signals
from . import protocol as p
from . import runtime


def assess(session, fixture, origin):
    runtime.replay(session)
    p.require(
        session["identity"] == fixture["identity"]
        and session["public_messages"] == fixture["messages"]
        and origin["session_id"] == session["id"],
        "offline_fixture_and_origin_join",
    )
    original = assess_replayed_session(session, fixture["bundle"], fixture["native_bindings"])
    complete_origin = origin["status"] == "PASS_AUTHENTIC_PROBE_PUBLIC_CHAIN"
    preeligible = bool(
        complete_origin
        and original["financial_valid"]
        and original["full_mapping_status"] == "MAPPED"
        and session["first_final_index"] is not None
    )
    signals = public_trace_signals(
        session, build_support_index(fixture["bundle"], fixture["native_bindings"])
    )
    return p.record(
        "probe_qualification",
        session_id=session["id"],
        registered_session_id=session["registered_session_id"],
        task_id=session["identity"]["task_id"],
        bundle_id=fixture["bundle"]["id"],
        profile=session["protocol_profile"],
        requested_basis=session["requested_basis"],
        original_semantic_assessment=original,
        origin_verification=origin,
        actual_method=original["actual_method"],
        financial_valid=original["financial_valid"],
        quantity_status=original["quantity_status"],
        support_status=original["support_status"],
        full_mapping_status=original["full_mapping_status"],
        full_class=original["full_class"],
        reason=original["reason"],
        authentic_complete_Probe_origin_verified=complete_origin,
        token_diagnostic_eligible=preeligible,
        structural_signals=signals,
        financial_or_fine_mapping_rule_changed=False,
        actual_method_from_requested_basis=False,
        mapper="original catalog_bridge finite executable-event mapper, not anchored state catalog",
        original_AB_material_eligible=False,
        training_eligible=False,
        training_samples=0,
    )


def candidates(session, qualification):
    p.checked(session, "probe_session")
    p.checked(qualification, "probe_qualification")
    p.require(
        qualification["session_id"] == session["id"] and qualification["token_diagnostic_eligible"],
        "authentic_financial_MAPPED_token_diagnostic_only",
    )
    rows = []
    for turn, event in zip(session["turns"], session["events"], strict=True):
        p.require(
            turn["response_index"] == event["response_index"]
            and turn["raw_response_sha256"] == p.sha(turn["raw_response"]),
            "original_public_row",
        )
        if not (event["final"] or event["tool_call"] and event["tool_call"]["status"] == "ok"):
            continue
        rows.append(
            p.record(
                "original_probe_response",
                session_id=session["id"],
                task_id=session["identity"]["task_id"],
                qualification_id=qualification["id"],
                public_runtime_state_id="history:" + p.sha(p.encode(turn["input_messages"])),
                response_index=turn["response_index"],
                messages=turn["input_messages"],
                target_text=turn["raw_response"],
                target_raw_sha256=turn["raw_response_sha256"],
                response_kind="Final" if event["final"] else event["tool_call"]["tool"],
                protocol_profile=session["protocol_profile"],
                training_sample=False,
            )
        )
    p.require(
        rows and rows[-1]["response_kind"] == "Final", "complete_original_first_Final_package"
    )
    return rows


def token_diagnostics(
    pairs,
    root,
    *,
    complete_registry,
    loader=load_local_tokenizer,
    encoder=encode_original_candidate,
):
    """No weights/training; retain compact reproducible evidence, never truncate."""
    p.require(type(complete_registry) is bool, "explicit_complete_registry_status")
    if not complete_registry:
        return p.record(
            "probe_token_diagnostics",
            status="SKIPPED_INCOMPLETE_REGISTRY",
            packages=[],
            tokenizer_loads=0,
            model_weight_loads=0,
            GPU_operations=0,
            training_samples=0,
        )
    eligible = [(s, q) for s, q in pairs if q["token_diagnostic_eligible"]]
    p.require(len({s["id"] for s, _ in pairs}) == len(pairs), "token_unique_original_sessions")
    binding, tokenizer = loader(root) if eligible else (None, None)
    if binding:
        p.require(
            binding.get("model_max_position_embeddings", 0) >= p.SEQUENCE_CAP,
            "original_tokenizer_model_context_supports_registered_cap",
        )
    packages = []
    for session, qualification in eligible:
        originals = candidates(session, qualification)
        checks, errors = [], []
        for candidate in originals:
            try:
                encoded = encoder(
                    candidate, binding, tokenizer, maximum_sequence_length=p.SEQUENCE_CAP
                )
                check = {
                    key: encoded[key]
                    for key in (
                        "id",
                        "sequence_length",
                        "target_token_count",
                        "consumable_token_representation",
                        "reason",
                    )
                }
                checks.append(
                    {
                        "candidate_id": candidate["id"],
                        "response_index": candidate["response_index"],
                        "original_target_sha256": candidate["target_raw_sha256"],
                        **check,
                    }
                )
                if not encoded["consumable_token_representation"]:
                    errors.append(
                        {"response_index": candidate["response_index"], "reason": encoded["reason"]}
                    )
            except (ValueError, TypeError, KeyError, UnicodeError, RuntimeError) as error:
                errors.append({"response_index": candidate["response_index"], "reason": str(error)})
        packages.append(
            p.record(
                "probe_token_package_diagnostic",
                registered_session_id=session["registered_session_id"],
                session_id=session["id"],
                qualification_id=qualification["id"],
                actual_method=qualification["actual_method"],
                complete_candidate_count=len(originals),
                checks=checks,
                errors=errors,
                consumable=not errors and len(checks) == len(originals),
                whole_package_target_tokens=sum(row["target_token_count"] for row in checks),
                maximum_sequence_length=p.SEQUENCE_CAP,
                truncation=False,
                original_positive_responses_in_original_full_histories=True,
                encoded_arrays_not_exported_as_training_material=True,
                training_eligible=False,
            )
        )
    return p.record(
        "probe_token_diagnostics",
        status="COMPLETE_DIAGNOSTIC",
        packages=packages,
        tokenizer_binding=binding,
        tokenizer_loads=int(bool(eligible)),
        model_weight_loads=0,
        GPU_operations=0,
        training_samples=0,
        maximum_sequence_length=p.SEQUENCE_CAP,
        entire_eligible_original_package_required=True,
        failed_or_not_fit_packages_not_replaced=True,
    )
