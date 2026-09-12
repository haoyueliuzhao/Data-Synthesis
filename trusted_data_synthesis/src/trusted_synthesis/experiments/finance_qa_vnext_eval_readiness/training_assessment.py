"""Live trace replay plus the archived finite financial semantics, without drift."""

from ..finance_qa_vnext_catalog_bridge.assessment import assess_replayed_session
from ..finance_qa_vnext_catalog_bridge.worker import require
from .training_runtime import record, replay


def assess_session(session, bundle, native_bindings, *, origin_evidence):
    replay(session)
    require(isinstance(origin_evidence, dict), "training.authentic_origin_evidence_required")
    require(
        origin_evidence.get("registered_session_id", origin_evidence.get("session_id"))
        == session["registered_session_id"],
        "training.origin_registered_session_join",
    )
    outcome = assess_replayed_session(session, bundle, native_bindings)
    verified = origin_evidence.get("status") == "PASS_AUTHENTIC_PUBLIC_REQUEST_CHAIN"
    full = outcome["financial_valid"] and outcome["full_mapping_status"] == "MAPPED"
    return record(
        "training_assessment",
        **{key: value for key, value in outcome.items() if key not in {"id", "schema_version"}},
        underlying_semantic_assessment_id=outcome["id"],
        protocol_replay="fixed_AB_training_runtime.v2",
        origin_evidence=origin_evidence,
        authentic_Teacher_origin_verified=verified,
        representation_eligible=bool(
            verified and full and session["first_final_index"] is not None
        ),
        requires_complete_fixed_collection_before_material_selection=True,
    )
