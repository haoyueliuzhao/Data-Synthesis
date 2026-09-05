"""Closed historical inputs, content identities and the new supervision contract."""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping
from fractions import Fraction
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash

STAGE = (
    "finance_qa_vnext_finite_support_training_representation_"
    "and_class_weight_intervention_preflight_only"
)
DIRECTIVE = "参照审计继续实验"
REVIEW_BYTES = 24_437
REVIEW_SHA256 = "4df85efb69a45d5fafb6c93a74b077682da9fd1130e0d16ca2ebb28af110a339"
MAX_SEQUENCE_LENGTH = 24_576
LABEL_IGNORE_INDEX = -100
QUOTIENT_PARENT = (
    "trusted_data_synthesis/artifacts/qa_reasoning_share_quotient_measurement/"
    "finance_qa_vnext_six_session_model_trajectory_finite_quotient_measurement_v1_20260906"
)
QUOTIENT_MANIFEST = (
    "share_quotient_manifest:cb6731e6dcbc39e37d148e09836b709b4a6b182f0d487a37662474982944531c"
)
QUOTIENT_ROOT = (
    "share_quotient_root:57452a01a2aa34be08ae0244bc602410468a62fe03aa8eda2e215274395a8cde"
)
PILOT_PARENT = (
    "trusted_data_synthesis/artifacts/qa_reasoning_share_model_pilot/"
    "finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905"
)
PILOT_MANIFEST = (
    "share_model_pilot_manifest:73dbba1f2af7cfb26fe1092fe5a6716b3b58df061a965244c10b615c6401af62"
)
PILOT_ROOT = (
    "share_model_pilot_root:fcc52ce717a9de0e764a6a4feca1f96f367e3f974595a0678ce609f07c3d5ae6"
)
QUOTIENT_SOURCE_COMMIT = "aa1451ae261b47218b2a5887f6fbe8f7f01ff871"
QUOTIENT_SOURCE_TREE = "3ae1cc3639bec151a6f81850aa8f3de7c4ede016"
LABELS = tuple(f"M{index:02d}" for index in range(1, 7))


class TrainingPreflightError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(condition: bool, code: str) -> None:
    if not condition:
        raise TrainingPreflightError(code)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record(record_type: str, **fields: Any) -> dict[str, Any]:
    require("id" not in fields and "schema_version" not in fields, "training.identity_input")
    body = {"schema_version": f"share_training_{record_type}.v1", **copy.deepcopy(fields)}
    return {**body, "id": strict_canonical_hash(body, prefix=f"share_training_{record_type}:")}


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    require(
        type(numerator) is int and type(denominator) is int and numerator >= 0 and denominator > 0,
        "training.rational_domain",
    )
    value = Fraction(numerator, denominator)
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
    }


def as_fraction(value: Mapping[str, Any]) -> Fraction:
    require(set(value) == {"numerator", "denominator", "exact"}, "training.rational_fields")
    require(ratio(value["numerator"], value["denominator"]) == value, "training.rational_identity")
    return Fraction(value["numerator"], value["denominator"])


def fraction_record(value: Fraction) -> dict[str, Any]:
    return ratio(value.numerator, value.denominator)


def identity(obj: Mapping[str, Any]) -> None:
    identifier = obj.get("id")
    require(isinstance(identifier, str) and ":" in identifier, "training.missing_identity")
    assert isinstance(identifier, str)
    require(
        strict_canonical_hash(
            {key: value for key, value in obj.items() if key != "id"},
            prefix=identifier.split(":")[0] + ":",
        )
        == identifier,
        "training.content_identity",
    )


def representation_contract(tokenizer_binding: Mapping[str, Any]) -> dict[str, Any]:
    return record(
        "representation_contract",
        stage=STAGE,
        tokenizer_binding_id=tokenizer_binding["id"],
        domain="the five previously Qualified and assigned model trajectories; no new sampling",
        source_selection="one row for each actual admitted model submission in a Qualified session",
        original_request_messages="exact messages from the corresponding saved HTTP body_json",
        original_target=(
            "exact raw_public_json string from the corresponding original model submission"
        ),
        expected_supervision_unit_counts={"action": 11, "update": 11, "final": 5},
        expected_positive_units=27,
        row_order="original cohort registration order, then actual turn order",
        rejected_submissions=(
            "zero positive imitation loss; preserve all source references and feedback"
        ),
        nonqualified_sessions=(
            "all M01 submissions excluded, including its admitted intermediate steps"
        ),
        qualification_and_assignment=(
            "reuse frozen original authorities; no new validity or quotient computation"
        ),
        cleaned_counterfactual_trajectory_claimed=False,
        feedback_counters_and_parent_state_rewritten=False,
        target_json_reserialized_or_repaired=False,
        private_reasoning_requested_or_supervised=False,
        template_policy=(
            "the frozen local Student chat_template applied to actual messages "
            "and raw assistant content"
        ),
        target_mask_policy="only tokens wholly inside the exact original assistant content span",
        boundary_policy=(
            "exact rendered prefix and content, exact token prefix, offsets and raw-content decode"
        ),
        boundary_straddling_token_policy=(
            "reject; never silently include prompt or drop target bytes"
        ),
        supervise_prompt_or_host=False,
        supervise_assistant_header=False,
        supervise_template_eos_or_suffix=False,
        supervise_padding=False,
        label_ignore_index=LABEL_IGNORE_INDEX,
        maximum_sequence_length=MAX_SEQUENCE_LENGTH,
        truncation=False,
        padding_side="right",
        causal_label_shift=1,
        loss_normalization=(
            "sum target-token losses within each original trajectory / its total target tokens"
        ),
        token_coefficient=(
            "pi(state) * M(trajectory|state) / total supervised tokens in that trajectory"
        ),
        batch_reduction=(
            "sum fixed token-weighted contributions; no row/batch/token-count renormalization"
        ),
        materialization=(
            "one finite original trajectory pool with uniform within-state trajectory kernel"
        ),
        views_share=(
            "same text rows, row order, tokenizer, template, input_ids, labels, "
            "attention and target masks"
        ),
        only_intervened_quantity="class probability mass pi(z|x)",
        baseline_P=(
            "explicitly choose measured empirical conditional frequencies, not an optimality claim"
        ),
        control_Q="uniform two-class mass, not coverage prior r, Novelty, or utility evidence",
        stochastic_optimizer_equivalence_claimed=False,
        status="preflight_only_not_a_training_release",
        provider_calls=0,
        credential_reads=0,
        new_candidate_runtime_executions=0,
        new_model_sessions=0,
        Student_parameter_loads=0,
        Student_forward_passes=0,
        Student_parameter_updates=0,
        GPU_jobs=0,
        Contribution_or_utility_evaluated=False,
        training_or_production_release=False,
        old_mainline="remains_paused",
    )
