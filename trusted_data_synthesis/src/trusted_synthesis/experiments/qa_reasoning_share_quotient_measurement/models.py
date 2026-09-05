"""Known-data finite measurement rules, identities and exact structural equality."""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash

STAGE = "finance_qa_vnext_six_session_model_trajectory_finite_quotient_measurement_only"
DIRECTIVE = "参照审计继续实验"
REVIEW_BYTES = 24_120
REVIEW_SHA256 = "d5d64a7acf39a0400773d8d1cd8db012f3846597d29d038edfce83b2f010d743"
PARENT = (
    "trusted_data_synthesis/artifacts/qa_reasoning_share_model_pilot/"
    "finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905"
)
PARENT_MANIFEST = (
    "share_model_pilot_manifest:73dbba1f2af7cfb26fe1092fe5a6716b3b58df061a965244c10b615c6401af62"
)
PARENT_ROOT = (
    "share_model_pilot_root:fcc52ce717a9de0e764a6a4feca1f96f367e3f974595a0678ce609f07c3d5ae6"
)
PARENT_SOURCE_COMMIT = "55fb6aab8d7122b4d930d1c31843e7d3653ccd19"
PARENT_SOURCE_TREE = "dc9c8c59c7e9b96e1cf0033d6aa9563faa06ce44"
LABELS = tuple(f"M{i:02d}" for i in range(1, 7))
EQUIVALENT = "equivalent"
DIFFERENT = "different_retained_semantics"
UNDETERMINED = "undetermined"
SCALAR_FIELDS = {
    "value",
    "metric",
    "definition",
    "subject",
    "scope",
    "period",
    "unit",
    "currency",
    "lineage",
}
NONSEMANTIC_STATE_FIELDS = {"id", "last_feedback", "submission_count", "remaining_bounds"}


class MeasurementError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(condition: bool, code: str) -> None:
    if not condition:
        raise MeasurementError(code)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record(record_type: str, **fields: Any) -> dict[str, Any]:
    require("id" not in fields and "schema_version" not in fields, "measurement.identity_input")
    body = {"schema_version": f"share_quotient_{record_type}.v1", **copy.deepcopy(fields)}
    return {**body, "id": strict_canonical_hash(body, prefix=f"share_quotient_{record_type}:")}


def number(value: Any) -> str:
    require(isinstance(value, str), "measurement.nonstring_decimal")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise MeasurementError("measurement.invalid_decimal") from error
    require(result.is_finite(), "measurement.nonfinite_decimal")
    if result.is_zero():
        return "0"
    rendered = format(result, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def structural_key(value: Any) -> tuple[Any, ...]:
    """Typed equality: neither hashes nor tolerance-based closeness are authorities."""
    if isinstance(value, Mapping):
        require(all(isinstance(key, str) for key in value), "measurement.nonstring_key")
        return ("object", tuple((key, structural_key(value[key])) for key in sorted(value)))
    if isinstance(value, (list, tuple)):
        return ("array", tuple(structural_key(item) for item in value))
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, str):
        return ("str", value)
    raise MeasurementError("measurement.unsupported_semantic_scalar")


def measurement_contract() -> dict[str, Any]:
    return record(
        "measurement_contract",
        stage=STAGE,
        design_status="rule instantiation on already observed trajectories; not data-blind",
        input_domain="exact six saved model sessions, five saved Qualified candidates",
        original_qualification_authority="unchanged manifest-bound independent pilot audits",
        qualification_reexecuted=False,
        new_task_or_verification_semantics=False,
        representation="typed directed public causal multigraph plus complete correction ledger",
        node_kinds=["evidence", "action", "execution", "observation", "update", "claim", "final"],
        retained_semantics=[
            "exact task, public context, numeric and verification contract",
            "actual evidence source, authority, content, locator, metric and relation",
            "pre-action typed basis and actual ordered operand roles",
            "registered operation contract, parameters and resolved input contents",
            "actual execution, Observation and complete explicitly proposed accepted Claim",
            "Observation-to-Update-to-Claim and actual producer-consumer edges",
            "grounding, accepted status, model/host field ownership and Final citations",
            "terminal answer and disposition, meaningful state or support changes",
        ],
        set_order_fields=[
            "evidence_refs",
            "claim_refs",
            "observation_refs",
            "lineage",
            "grounding",
            "citations",
        ],
        numeric_rule="finite Decimal exact equality only, preserving all typed proposition fields",
        operation_order_rule=(
            "ordered input slots retained; only relation_sum's two same-role member slots commute"
        ),
        runtime_names="consistent bijection of graph keys and all edges; source identity retained",
        nonauthoritative_metadata=["session label", "turn ordinal", "runtime IDs", "display label"],
        raw_interactions=(
            "all 51 immutable submissions, receipts, feedback and order remain in parent"
        ),
        correction_rules={
            "C0": "only rejected proposals with no execution/Observation/Claim/Final effects",
            "C1": "knowledge state unchanged through the nearest next admitted submission",
            "C2": "same proposal kind and semantic target; no intermediate admitted event",
            "C3_action": (
                "only public_basis alignment; operation/ordered inputs/parameters unchanged"
            ),
            "C3_update": (
                "same pending Observation, accept disposition, basis, lineage and typed context; "
                "only value/definition adjusted to the existing complete observed proposition"
            ),
            "C3_final": (
                "same accepted answer Claim and answer; only citations/public_basis align to "
                "that Claim's already existing grounding"
            ),
            "C4": "exact deltas, parent IDs, following admission, counters and costs retained",
            "failure": (
                "unexplained effects or semantic target changes -> undetermined, never erased"
            ),
        },
        reducible_receipt_codes={
            "action": ["admission.public_basis"],
            "update": ["admission.observed_claim_content"],
            "final": ["admission.final_grounding"],
        },
        meaningful_revision_rule=(
            "admitted reject/retraction, accepted-Claim replacement, new "
            "verification, actual support "
            "switch or dependency changes are never C0-C4 reductions; "
            "outside this finite accept-only "
            "projection they stay undetermined with complete original event evidence"
        ),
        projection_domain=(
            "the registered three operations with explicit accept "
            "Updates; all executed and accepted "
            "objects retained, including non-final ancestors; unsupported "
            "event semantics undetermined"
        ),
        comparison_results=[EQUIVALENT, DIFFERENT, UNDETERMINED],
        comparison_authority=(
            "exact semantic-label-preserving graph isomorphism; explicit "
            "full bijection or retained "
            "label/edge discrepancy; neither route labels, graph hashes nor Final alone"
        ),
        canonical_permutation_limit=4096,
        finite_relation_checks=[
            "complete ten unordered pairs",
            "reflexive",
            "symmetric",
            "transitive",
        ],
        assignment_rule=(
            "only saved Qualified and fully determined projections, complete determinate relation; "
            "state identities bind task/protocol/generation/rules and actual semantic graph"
        ),
        partial_mapping_rule=(
            "if any Qualified projection or necessary pair is undetermined, do not fabricate the "
            "complete partition; preserve unmapped Qualified count and denominator five"
        ),
        denominators={"end_to_end": 6, "joint_state_frequency": 6, "success_conditioned": 5},
        distribution_interpretation=(
            "empirical push-forward of frozen executions; not population "
            "probability or training pi_t"
        ),
        class_count_pass_requirement=None,
        expected_two_classes_is_a_gate=False,
        old_quotient_state_ids_reused=False,
        provider_calls=0,
        credential_reads=0,
        GPU_jobs=0,
        new_model_sessions=0,
        new_candidate_runtime_executions=0,
        archive_rescans=0,
        contribution_or_training_authorized=False,
        old_mainline="remains_paused",
    )


def condition_binding(inputs: Mapping[str, Any], rules: Mapping[str, Any]) -> dict[str, Any]:
    context = inputs["context"]
    return {
        "task_id": context["task"]["id"],
        "public_context_id": context["id"],
        "protocol_id": inputs["protocol"]["id"],
        "model_configuration_id": inputs["model_config"]["id"],
        "pilot_registration_id": inputs["pilot_registration"]["id"],
        "measurement_contract_id": rules["id"],
        "numeric": copy.deepcopy(context["numeric"]),
        "answer_schema": copy.deepcopy(context["answer_schema"]),
        "shared_obligations": copy.deepcopy(context["shared_obligations"]),
        "generation_record_is_frozen_not_an_immutable_remote_weight_claim": True,
    }
