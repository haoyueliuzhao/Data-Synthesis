"""Pilot conditions and record identities, separate from frozen historical evidence."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import (
    record as core_record,
)
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import require

STAGE = "finance_qa_vnext_share_public_protocol_model_adapter_and_six_session_engineering_pilot"
REVIEW_BYTES = 27_072
REVIEW_SHA256 = "1fc713f450529c16094ca7ff63c69b2d6b5f2342908151c0bf3f678c6d590b0f"
DIRECTIVE = "参照审计开展后续实验"
PARENT = (
    "trusted_data_synthesis/artifacts/qa_reasoning_share_public_protocol/"
    "finance_qa_vnext_share_public_state_proposal_action_observation_update_protocol_"
    "preflight_v1_20260905"
)
PARENT_MANIFEST = (
    "public_share_protocol_manifest:"
    "8935da52f4f8146c290a5f9875e1e319b4e9f3d7d347efe4dec07aed163dbb66"
)
PARENT_ROOT = (
    "public_share_protocol_root:69c83461068a0ff5c583e93b05b7dab59455d92e12606c389f2105ba075100de"
)
PARENT_SOURCE_COMMIT = "606b13c35cb3aca4107ee5497451ba51378bb843"
PARENT_SOURCE_TREE = "6736228347d4d8519c7ac099378a409dc45b8053"


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def record(record_type: str, **fields: Any) -> dict[str, Any]:
    require("id" not in fields and "schema_version" not in fields, "pilot.identity_input")
    body = {"schema_version": f"share_model_pilot_{record_type}.v1", **copy.deepcopy(fields)}
    return {**body, "id": strict_canonical_hash(body, prefix=f"share_model_pilot_{record_type}:")}


def model_config() -> dict[str, Any]:
    return record(
        "model_config",
        endpoint="https://api.deepseek.com/chat/completions",
        model="deepseek-v4-pro",
        documented_version="DeepSeek-V4-Pro-0813",
        documented_version_is_requestable_immutable_snapshot=False,
        model_identity_policy=(
            "require registered response model; retain actual optional fingerprint"
        ),
        allowed_response_models=["deepseek-v4-pro", "deepseek-v4-pro-0813"],
        response_model_mismatch_rule=(
            "terminal provider.model_identity_mismatch; no parser or fallback"
        ),
        thinking={"type": "disabled"},
        temperature=0.7,
        top_p=1.0,
        max_tokens=8192,
        response_format={"type": "json_object"},
        stream=False,
        native_tool_calls=False,
        timeout_seconds=180,
        connect_timeout_seconds=30,
        maximum_serialized_request_bytes=65_536,
        maximum_input_tokens=66_560,
        input_token_admission_rule="UTF-8 serialized body bytes plus 1024 conservative allowance",
        exact_offline_model_tokenization_claimed=False,
        actual_tokens_authority="Provider response usage; missing usage remains unknown",
        maximum_request_reserved_tokens=74_752,
        maximum_session_reserved_tokens=897_024,
        maximum_pilot_reserved_tokens=5_382_144,
        maximum_public_response_bytes=32_768,
        maximum_http_response_bytes=2_097_152,
        attempts_per_session=12,
        total_online_attempts=72,
        online_sessions=6,
        session_parallelism=6,
        automatic_retries=0,
        redirects=0,
        model_fallbacks=0,
        session_replacements=0,
        messages_policy="neutral system and canonical current public request only; stateless turns",
        raw_private_reasoning_persisted=False,
        raw_private_reasoning_hashed=False,
        schema_authority="actual request_for(State).response_schema; no approximate second schema",
        official_configuration_sources=[
            "https://api-docs.deepseek.com/quick_start/pricing/",
            "https://api-docs.deepseek.com/api/create-chat-completion/",
            "https://api-docs.deepseek.com/guides/thinking_mode/",
            "https://api-docs.deepseek.com/quick_start/token_usage/",
        ],
        official_sources_checked_date="2026-09-05",
    )


def protocol_contract(parent: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """New condition identity; same public grammar, Task semantics and action/update limits."""
    fields = {k: copy.deepcopy(v) for k, v in parent.items() if k not in {"id", "schema_version"}}
    for key in (
        "generator_response_origin",
        "provider_adapter_implemented",
        "model_reachability_measured",
        "positive_protocol_sessions",
        "direct_controls_are_model_or_runtime_evidence",
        "provider_credential_gpu_limits",
        "failed_callback_rule",
    ):
        fields.pop(key)
    fields.update(
        stage=STAGE,
        parent_protocol_id=parent["id"],
        model_configuration_id=config["id"],
        generator_response_origin="registered_model_adapter_or_separately_registered_adapter_mock",
        provider_adapter_implemented=True,
        model_reachability_measured="bounded_six_session_engineering_observation_only",
        registered_online_sessions=6,
        separate_local_mock_sessions=2,
        direct_controls_are_model_evidence=False,
        provider_attempt_limits={"per_session": 12, "pilot": 72},
        gpu_jobs=0,
        failed_callback_rule=(
            "consume Provider attempt, no synthetic public submission, terminal without retry"
        ),
        malformed_public_response_rule=(
            "hash and byte count plus receiver diagnosis only; typed rejection may use remaining "
            "submission budget; no repair, raw malformed text or private reasoning persistence"
        ),
        session_initial_state_rule="independent state copies; equal public contents may share IDs",
        class_mapping_or_new_quotient_comparison=False,
    )
    return core_record("contract", **fields)


def session_declarations(protocol: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        record(
            "session_declaration",
            label=f"M{index + 1:02d}",
            ordinal=index,
            protocol_id=protocol["id"],
            model_configuration_id=config["id"],
            generator_origin="model",
            neutral_prompt=True,
            reference_route=None,
            independent_initial_state=True,
            reads_other_session_responses=False,
            maximum_provider_attempts=12,
            replacement_allowed=False,
        )
        for index in range(6)
    ]


def source_binding(
    module_name: str, class_name: str, method_name: str, path: Path
) -> dict[str, Any]:
    return {
        "module": module_name,
        "class_name": class_name,
        "method_name": method_name,
        "source_path": path.as_posix().split("/Data-Synthesis/")[-1],
        "source_sha256": sha(path.read_bytes()),
    }
