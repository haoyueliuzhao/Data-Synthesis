"""Successor semantic rules. They do not replace the closed study's grades."""

from .core import ALIGNMENTS, STATUSES, record, require

VERSION = "public_task_target_binding.v2"
CLAIM_ROLES = frozenset(
    {
        "DIRECT_SOURCE_VALUE",
        "DERIVED_FROM_SOURCES",
        "GENERAL_REFERENCE",
        "UNRESOLVED",
    }
)


def target_binding(
    *,
    local_relation,
    alignment,
    public_scope_match,
    registered_scope_match,
    final_chain_completes_public_target,
):
    for value in (
        local_relation,
        public_scope_match,
        registered_scope_match,
        final_chain_completes_public_target,
    ):
        require(value in STATUSES, "binding.explicit_status")
    require(alignment in ALIGNMENTS, "binding.alignment_status")
    if any(
        s == "FAIL"
        for s in (local_relation, public_scope_match, final_chain_completes_public_target)
    ):
        public = "FAIL"
    elif alignment in {"PUBLIC_UNDERSPECIFIED", "NEED_SOURCE_CHECK"}:
        # A private target must never silently resolve an underspecified public request.
        public = "UNDETERMINED"
    elif all(
        s == "PASS"
        for s in (local_relation, public_scope_match, final_chain_completes_public_target)
    ):
        public = "PASS"
    else:
        public = "UNDETERMINED"
    return {
        "local_relation_validity": local_relation,
        "public_target_alignment": alignment,
        "public_task_applicability": public,
        "public_scope_match": public_scope_match,
        "registered_scope_match_diagnostic_only": registered_scope_match,
        "final_dependency_chain_completes_public_target": final_chain_completes_public_target,
        "private_target_did_not_supply_public_scope": True,
        "registered_reference_eligible_for_prospective_primary_score": alignment == "ALIGNED",
        "not_a_complete_trajectory_grade": True,
    }


def source_claim(
    *,
    role,
    current,
    source_value_equal=None,
    derivation_supported=None,
    reference_relevant=None,
    withdrawal_supported=False,
    consumed=False,
):
    require(role in CLAIM_ROLES and type(current) is bool, "claim.role_and_current")
    require(type(consumed) is bool and type(withdrawal_supported) is bool, "claim.flags")
    for value in (source_value_equal, derivation_supported, reference_relevant):
        require(value is None or type(value) is bool, "claim.three_valued_evidence")
    if not current:
        require(withdrawal_supported, "claim.withdrawal_requires_evidence")
        status = "NOT_CURRENT"
    elif role == "UNRESOLVED":
        status = "UNDETERMINED"
    else:
        supported = {
            "DIRECT_SOURCE_VALUE": source_value_equal,
            "DERIVED_FROM_SOURCES": derivation_supported,
            "GENERAL_REFERENCE": reference_relevant,
        }[role]
        status = "UNDETERMINED" if supported is None else "PASS" if supported else "FAIL"
    return {
        "role": role,
        "current": current,
        "status": status,
        "consumed_by_arithmetic": consumed,
        "source_value_equal": source_value_equal,
        "derivation_supported": derivation_supported,
        "reference_relevant": reference_relevant,
        "withdrawal_supported": withdrawal_supported,
        "nonconsumption_did_not_erase_claim": True,
        "field_adjacency_did_not_determine_claim_role": True,
    }


def policy():
    return record(
        "successor_policy",
        version=VERSION,
        target_alignment={
            "ALIGNED": (
                "Public question and relevant public context support the regi"
                "stered physical target without an unresolved material scope "
                "choice."
            ),
            "PUBLIC_UNDERSPECIFIED": (
                "Multiple materially distinct public scope interpretations re"
                "main; the private reference cannot choose one."
            ),
            "PRIVATE_MISMATCH": (
                "The registered target directly conflicts with the public tas"
                "k; not merely missing evidence."
            ),
            "NEED_SOURCE_CHECK": (
                "The sealed material is insufficient to establish the request"
                "ed public quantity or its registration alignment."
            ),
        },
        formula_rule=(
            "Record local relation validity separately from applicability"
            " to the original public task. "
            "The actual final dependency chain must complete the requeste"
            "d object, interval, sign and unit. "
            "A correct intermediate quantity may be transformed legitimat"
            "ely; not every intermediate must equal the final target. "
            "A model's own restated goal is not a substitute for the original task."
        ),
        source_rule=(
            "Classify a current public statement as direct source-value a"
            "ssertion, supported derivation, "
            "general reference, or unresolved, from the public contract and surrounding text. "
            "The contract defines nested variables.NAME.{value,source,unit} and arguments.sources; "
            "it does not define adjacent flat variables.value/source/unit"
            " as one source-value assertion. "
            "Nonconsumption does not erase an actual false claim. Ambigui"
            "ty does not certify or invalidate a source-value assertion. "
            "Prior errors remain recorded; withdrawal requires an evidenc"
            "ed correction or unambiguous replacement."
        ),
        numeric_ID_only_gate=False,
        no_new_quantity_parser_tolerance_or_Final_selection=True,
        historical_scores_unchanged=True,
        local_cases_cannot_be_spliced_into_a_new_252_session_primary_score=True,
        prospective_primary_panel_requires_resolved_public_targets=True,
        previous_confirmation_tasks_are_now_known_historical_material=True,
        independent_or_blind_confirmation=False,
        E_X2_DR_study_status="PROPOSED_NOT_ACCEPTED_OR_FROZEN",
        new_model_budget=0,
    )
