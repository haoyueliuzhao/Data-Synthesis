"""Prospective measurement rules over already known frozen candidates, not data-blind."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from .comparison import comparison_rule_contract
from .inputs import identified, require, sha
from .projection import projection_rule_contract

STAGE = "finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_only"
REVIEW_BYTES = 23_746
REVIEW_SHA256 = "4987d122e9f128db658544b89d46a076133eb8617d1c2c0378492f774c5d0450"
DIRECTIVE = "参照审计继续实验"
DIRECTIVE_SHA256 = "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"


def authorize(review: bytes) -> dict[str, Any]:
    require(
        len(review) == REVIEW_BYTES and sha(review) == REVIEW_SHA256,
        "authorization.review",
        "exact external finite-comparison review differs",
    )
    require(
        len(DIRECTIVE.encode()) == 24 and sha(DIRECTIVE.encode()) == DIRECTIVE_SHA256,
        "authorization.directive",
        "operator directive differs",
    )
    return identified(
        {
            "stage": STAGE,
            "review_byte_count": len(review),
            "review_sha256": sha(review),
            "directive": DIRECTIVE,
            "directive_sha256": DIRECTIVE_SHA256,
            "review_access": (
                "report_and_arithmetic_consistency_no_repository_or_actual_artifact_replay"
            ),
            "closed_predecessor_object": "finite_candidate_source_own_execution_bounded_validation",
            "frozen_trajectories": 6,
            "same_task_unordered_pairs": 6,
            "maximum_read_only_validator_calls_per_build": 6,
            "new_candidate_or_runtime_execution_authorized": False,
            "Provider_or_GPU_authorized": False,
            "second_class_required": False,
            "old_mainline": "remains_paused",
        },
        "authorization",
        "authorization_id",
    )


def measurement_contract(inputs: Mapping[str, Any]) -> dict[str, Any]:
    contracts = inputs["operation_contracts"]
    require(
        contracts["lookup"]["program_role"] == "transparent_projection"
        and contracts["growth"]["input_order_policy"] == "ordered"
        and contracts["signed_percentage_point_gap"]["input_order_policy"] == "ordered",
        "rules.registry",
        "frozen projection or ordered-operand semantics differ",
    )
    design = inputs["design"]
    require(
        design["equivalence_design"]["answer_equality_alone"]
        == "not sufficient for behavior equivalence",
        "rules.design",
        "accepted design differs",
    )
    return identified(
        {
            "stage": STAGE,
            "input_freeze_id": inputs["freeze"]["audit_id"],
            "accepted_design_contract_id": design["contract_id"],
            "measurement_is_on_already_known_candidates": True,
            "data_blind_confirmation_claimed": False,
            "comparison_rules_frozen_before_comparator_calls": True,
            "new_candidate_selection_or_execution": False,
            "retained_fields": {
                "task": (
                    "exact Task, public question, source scope, answer "
                    "Oracle/schema/unit/tolerance/citations"
                ),
                "evidence": (
                    "actual source/version/content/locator/role/period/unit/authority "
                    "and selected value"
                ),
                "basis": (
                    "typed source and verified Claim requires/supports, preserving "
                    "proposition and ordered use"
                ),
                "operation": "exact registered semantic version/hash and ordered operand roles",
                "claim": (
                    "actual production, consumption, selected values/units and source grounding"
                ),
                "observation_update": (
                    "actual Observation-supported acceptance and meaningful "
                    "State/verification effects"
                ),
                "obligations": (
                    "comparability, both growths, ordered signed-and-absolute spread, "
                    "final grounding"
                ),
                "final": "actual final disposition, own grounded result and exact citations",
                "ownership": (
                    "Host comparability/admission remains Host; deterministic "
                    "proposal/update remains Fixture"
                ),
            },
            "transparent_contraction_conditions": [
                "exact contract program_role is transparent_projection, not an operator-name guess",
                (
                    "actual lookup output preserves complete Evidence "
                    "payload/source/unit/locator and value selector"
                ),
                (
                    "each actual producer-consumer reference substitutes same Evidence "
                    "with identical position and role"
                ),
                (
                    "referenced Evidence is already visible and source-admitted at the "
                    "actual pre-action State"
                ),
                (
                    "actual proposal/update/State delta has no additional retained "
                    "verification/rejection/revision effect"
                ),
            ],
            "selector_composition": (
                "Evidence payload -> lookup full payload -> payload.value equals "
                "same Evidence.value"
            ),
            "transparent_registration_is_not_sufficient_by_itself": True,
            "operational_annotations": [
                "runtime IDs",
                "artifact paths",
                "cosmetic route labels",
                "independent schedule indices",
            ],
            "meaningful_basis_or_state_fields_are_never_dropped_by_name": True,
            "numeric_normalization": (
                "finite exact Decimal equality without context rounding or pairwise tolerance"
            ),
            "ordered_signed_roles": (
                "reference=operating_income_growth, observed=revenue_growth; final "
                "abs does not commute roles"
            ),
            "unsupported_or_unexplained_field_result": "undetermined",
            "projection": projection_rule_contract(),
            "comparison": comparison_rule_contract(),
            "operation_contracts": contracts,
            "operation_contract_set_sha256": sha(canonical_json_bytes(contracts)),
            "task_pairs": ["B-C", "B-A", "A-C"],
            "primary": ["B", "A"],
            "schedule_control": ["C"],
            "cross_task_pairs": 0,
            "class_count_requires_all_relations_determined_and_equivalence_consistent": True,
            "unknown_class_count": None,
            "second_class_is_not_a_gate": True,
            "raw_artifacts_are_not_rewritten_by_projection": True,
            "unit_controls_are_not_qualified_semantic_witnesses": True,
        },
        "measurement_contract",
        "contract_id",
    )
