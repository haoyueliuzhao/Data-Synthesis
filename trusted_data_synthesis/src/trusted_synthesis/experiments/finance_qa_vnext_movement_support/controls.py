"""Offline reference-script interface controls, never authentic Teacher data.

The original live runtime deliberately retains its literal callback origin.
This wrapper records the *actual* scripted provenance separately and never
writes sessions/packages, encodes tokens, calls a model, or admits training.
"""

import copy

from ..finance_qa_vnext_catalog_bridge.assessment import assess_replayed_session
from ..finance_qa_vnext_catalog_bridge.controls import script_for_witness
from ..finance_qa_vnext_catalog_bridge.worker import encode as original_encode
from ..finance_qa_vnext_eval_readiness import training_runtime
from . import protocol as p

PROVENANCE = "test_only_scripted_reference_callback"


def run_fixture_control(fixture, basis):
    """Run one predeclared task/basis control using unchanged original semantics.

    fixture has bundle, native_bindings, messages and identity. A control task
    uses basis='control'; its original witness is fixed_control_reference.
    Expected method is a test expectation, never written into the assessment.
    Failures are returned as rows so callers can retain their whole fixed matrix.
    """
    p.require(
        isinstance(fixture, dict)
        and {"bundle", "native_bindings", "messages", "identity"} <= set(fixture),
        "movement.control_fixture_fields",
    )
    fixture = copy.deepcopy(fixture)
    bundle, native = fixture["bundle"], fixture["native_bindings"]
    family = bundle["family"]
    p.require(
        family in {"annual_flow", "stock_rollforward", "company_defined_metric", "control"},
        "movement.control_registered_training_family",
    )
    p.require(
        basis
        in (
            {"control", "fixed_control_reference"}
            if family == "control"
            else {"endpoint", "movement"}
        ),
        "movement.control_available_basis",
    )
    expected = "control" if family == "control" else basis
    fixture_digest = p.sha(p.encode(fixture))
    registered_id = "offline_reference_control_" + p.sha(p.encode([fixture_digest, basis]))
    script, session, assessment, error = None, None, None, None
    phase, replay_verified, callback_calls = "script_construction", False, 0
    try:
        script = script_for_witness(bundle, native, basis=expected)

        def scripted_callback(messages, context):
            nonlocal callback_calls
            p.require(
                context["response_index"] == callback_calls
                and context["session_id"] == registered_id
                and context["requested_basis"] == expected,
                "movement.control_exact_script_position",
            )
            p.require(callback_calls < len(script), "movement.control_no_response_resampling")
            response = script[callback_calls]
            callback_calls += 1
            return {
                "raw_response": response
                if isinstance(response, str)
                else original_encode(response).decode(),
                "evidence": {
                    "test_only": True,
                    "actual_provenance": PROVENANCE,
                    "model_or_HTTP_call": False,
                },
            }

        phase = "original_runtime"
        session = training_runtime.generate(
            fixture["messages"],
            fixture["identity"],
            provider=scripted_callback,
            session_id=registered_id,
            requested_basis=expected,
        )
        phase = "original_runtime_replay"
        replay_verified = training_runtime.replay(session) == session
        p.require(replay_verified, "movement.control_original_replay")
        phase = "original_semantic_assessment"
        assessment = assess_replayed_session(session, bundle, native)
    except Exception as caught:
        error = {"phase": phase, "type": type(caught).__name__, "reason": str(caught)}
    finally:
        p.require(
            p.sha(p.encode(fixture)) == fixture_digest, "movement.control_fixture_not_rewritten"
        )
    semantic = assessment or {}
    checks = {
        "original_runtime_replay": replay_verified,
        "financial_valid": semantic.get("financial_valid") is True,
        "expected_actual_method": semantic.get("actual_method") == expected,
        "fine_mapping": semantic.get("full_mapping_status") == "MAPPED",
    }
    passed = error is None and all(checks.values())
    tools = (
        [event["tool_call"] for event in session["events"] if event["tool_call"]] if session else []
    )
    return p.record(
        "offline_fixture_control",
        status="PASS_INTERFACE_CONTROL" if passed else "FAIL_INTERFACE_CONTROL",
        task_id=bundle["task_id"],
        family=family,
        quantity=bundle["private"]["canonical_target"].get("quantity"),
        fixture_sha256=fixture_digest,
        original_bundle_id=bundle["id"],
        requested_control_basis=basis,
        expected_method=expected,
        registered_control_session_id=registered_id,
        planned_script_responses=len(script) if script is not None else None,
        reference_script_sha256=p.sha(original_encode(script)) if script is not None else None,
        callback_response_count=callback_calls,
        recorded_response_count=len(session["turns"]) if session else 0,
        executed_tools=len(tools),
        failed_tools=sum(tool["status"] != "ok" for tool in tools),
        runtime_max_responses=training_runtime.MAX_RESPONSES,
        runtime_max_tools=training_runtime.MAX_TOOLS,
        runtime_session_id=session["id"] if session else None,
        runtime_origin_literal=session["origin"] if session else None,
        actual_provenance=PROVENANCE,
        test_only=True,
        first_final_index=session["first_final_index"] if session else None,
        terminal=session["terminal"] if session else None,
        replay_verified=replay_verified,
        checks=checks,
        financial_valid=semantic.get("financial_valid", False),
        quantity_status=semantic.get("quantity_status"),
        support_status=semantic.get("support_status"),
        actual_method=semantic.get("actual_method"),
        full_mapping_status=semantic.get("full_mapping_status"),
        full_class=semantic.get("full_class"),
        full_mapping_pending_reasons=semantic.get("full_mapping_pending_reasons", []),
        semantic_reason=semantic.get("reason"),
        original_assessment=assessment,
        error=error,
        authentic_Teacher_origin_verified=False,
        origin_status="ORIGIN_NOT_VERIFIED_SCRIPTED_REFERENCE_ONLY",
        representation_eligible=False,
        training_eligible=False,
        training_samples=0,
        raw_or_encoded_training_packages_written=0,
        model_calls=0,
        HTTP_requests=0,
        tokenizer_loads=0,
        GPU_operations=0,
        original_methods_or_qualification_rules_changed=False,
        evidence_scope=(
            "offline public-runtime/reference compatibility, not observed Teacher behavior"
        ),
        source_of_reference_is_private_witness=True,
        private_witness_sent_to_external_model=False,
    )
