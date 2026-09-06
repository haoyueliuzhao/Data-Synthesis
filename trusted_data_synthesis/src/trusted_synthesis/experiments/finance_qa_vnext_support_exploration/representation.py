"""Represent new N/E exploration evidence without replacing its actual prompts.

The old panel encoder and its 32,768 policy are reused unchanged.  This wrapper
adds the eight-session exploration/profile bindings and checks the system message
that the original-HTTP exporter actually retained.  It never manufactures a
neutral request for an E response, changes qualification, or imports old rows.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from ..finance_qa_vnext_model_execution import representation as original
from ..finance_qa_vnext_model_execution.models import identity, record, require, sha
from ..finance_qa_vnext_model_execution.transport import SYSTEM_PROMPT
from ..finance_qa_vnext_task_panel import representation as panel

PROFILES = ("N", "E")
LABELS = tuple(f"{profile}{wave:02d}" for wave in range(1, 5) for profile in PROFILES)
SHARE_TASK_TYPE = "source_explicit_part_whole_share"


def representation_policy(binding: dict[str, Any]) -> dict[str, Any]:
    """Reuse the existing asset/policy identity, never an old candidate dataset."""
    return panel.representation_policy(binding)


def validate_profile_bindings(
    rows: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    condition: dict[str, Any],
) -> dict[str, Any]:
    """Check frozen profile versus original exported HTTP messages before encoding."""
    identity(condition, "support_exploration_condition")
    profiles, configurations = condition["profiles"], condition["configurations"]
    require(
        set(profiles) == set(configurations) == set(PROFILES), "exploration_representation.profiles"
    )
    require(
        condition["registered_session_count"] == len(entries) == 8
        and condition["sessions_per_profile"] == 4
        and condition["registered_labels"] == list(LABELS)
        and [entry["label"] for entry in entries] == list(LABELS)
        and condition["profile_mixture"]
        == {profile: {"numerator": 1, "denominator": 2} for profile in PROFILES},
        "exploration_representation.fixed_population",
    )
    require(
        condition["task_group"] == "S" and condition["task_type"] == SHARE_TASK_TYPE,
        "exploration_representation.fixed_share_task",
    )
    for name in PROFILES:
        profile, config = profiles[name], configurations[name]
        identity(profile, "support_exploration_profile")
        identity(config, "transport_config")
        require(
            profile["profile"] == config["profile"] == name
            and isinstance(profile["system_prompt"], str)
            and profile["system_prompt"] == config["system_prompt"],
            "exploration_representation.profile_configuration",
        )
    neutral, guided = (profiles[name]["system_prompt"] for name in PROFILES)
    require(
        neutral == SYSTEM_PROMPT
        and guided.startswith(neutral + "\n\n")
        and len(guided) > len(neutral) + 2,
        "exploration_representation.frozen_neutral_and_guided_prompts",
    )
    require(
        len({entry["registration"]["id"] for entry in entries}) == 8
        and len({entry["registration"]["session_id"] for entry in entries}) == 8
        and len({entry["qualification"]["id"] for entry in entries}) == 8
        and Counter(entry["registration"]["profile"] for entry in entries)
        == Counter({"N": 4, "E": 4}),
        "exploration_representation.unique_profile_population",
    )
    expected, sessions, candidates = [], [], []
    for entry in entries:
        registration, qualification, session, export = (
            entry[key] for key in ("registration", "qualification", "session", "export")
        )
        identity(registration, "session_registration")
        identity(qualification, "qualification")
        identity(export, "supervision_export")
        name = registration["profile"]
        profile, config = profiles[name], configurations[name]
        require(
            entry["label"] == registration["label"]
            and registration["label"].startswith(name)
            and registration["profile_id"] == profile["id"]
            and registration["model_configuration_id"]
            == qualification["model_configuration_id"]
            == config["id"]
            and registration["run_condition_id"] == condition["id"]
            and qualification["registration_id"] == registration["id"]
            and qualification["registered_session_id"] == registration["session_id"]
            and qualification["session_id"] == (session["id"] if session is not None else None)
            and export["session_id"] == qualification["session_id"]
            and export["qualification_id"] == qualification["id"]
            and all(
                registration[key] == qualification[key] == condition[key]
                for key in (
                    "task_id",
                    "context_id",
                    "protocol_id",
                    "registry_hash",
                    "task_group",
                    "task_type",
                )
            ),
            "exploration_representation.profile_parent_binding",
        )
        require(
            qualification["status"] in {"success", "known_failure", "unknown", "not_started"}
            and export["candidate_count"] == len(export["rows"]),
            "exploration_representation.original_outcome_and_export_count",
        )
        if session is not None:
            require(
                session["callback_binding"]["model_configuration_id"] == config["id"],
                "exploration_representation.actual_callback_configuration",
            )
        eligible = panel._eligible(qualification)
        require(
            eligible or not export["rows"], "exploration_representation.ineligible_positive_rows"
        )
        sessions.append(
            {
                "label": entry["label"],
                "profile": name,
                "profile_id": profile["id"],
                "model_configuration_id": config["id"],
                "registration_id": registration["id"],
                "registered_session_id": registration["session_id"],
                "session_id": qualification["session_id"],
                "qualification_id": qualification["id"],
                "qualification_status": qualification["status"],
                "positive_eligible": eligible,
                "export_id": export["id"],
                "candidate_ids": [row["id"] for row in export["rows"]],
            }
        )
        for row in export["rows"]:
            original._candidate(row)
            messages = original._messages(row["messages"])
            require(
                messages[0] == {"role": "system", "content": config["system_prompt"]},
                "exploration_representation.actual_profile_prompt_not_preserved",
            )
            require(session is not None, "exploration_representation.positive_session_missing")
            assert session is not None
            index = row["turn_index"]
            require(
                type(index) is int and 0 <= index < len(session["events"]),
                "exploration_representation.original_turn_index",
            )
            event = session["events"][index]
            require(
                row["registration_id"] == registration["id"]
                and row["registered_session_id"] == registration["session_id"]
                and row["qualification_id"] == qualification["id"]
                and row["session_id"] == session["id"]
                and row["public_request_id"] == event["request"]["id"]
                and messages[1]["content"].encode("utf-8") == canonical_json_bytes(event["request"])
                and all(
                    isinstance(row.get(key), str) and len(row[key]) == 64
                    for key in (
                        "http_request_sha256",
                        "http_response_sha256",
                    )
                ),
                "exploration_representation.original_request_profile_binding",
            )
            candidates.append(
                {
                    "candidate_id": row["id"],
                    "label": entry["label"],
                    "profile": name,
                    "profile_id": profile["id"],
                    "model_configuration_id": config["id"],
                    "registration_id": registration["id"],
                    "qualification_id": qualification["id"],
                    "session_id": session["id"],
                    "turn_index": index,
                    "public_request_id": row["public_request_id"],
                    "http_request_id": row["request_id"],
                    "http_response_id": row["response_id"],
                    "http_request_sha256": row["http_request_sha256"],
                    "http_response_sha256": row["http_response_sha256"],
                    "messages_sha256": sha(canonical_json_bytes(messages)),
                    "system_prompt_sha256": sha(messages[0]["content"].encode("utf-8")),
                    "system_prompt_byte_count": len(messages[0]["content"].encode("utf-8")),
                    "target_raw_sha256": row["target_raw_sha256"],
                    "target_raw_byte_count": row["target_raw_byte_count"],
                    "actual_profile_prompt_preserved": True,
                    "neutral_request_substituted_for_guided_response": False,
                }
            )
        expected.extend(export["rows"])
    require(
        canonical_json_bytes(rows) == canonical_json_bytes(expected)
        and len({row["id"] for row in rows}) == len(rows),
        "exploration_representation.complete_original_export_set",
    )
    return record(
        "support_exploration_representation_profile_checks",
        generation_condition_id=condition["id"],
        registered_session_count=8,
        sessions_per_profile={"N": 4, "E": 4},
        session_rows=sessions,
        candidate_rows=candidates,
        candidate_count=len(rows),
        candidate_counts_by_profile={
            name: sum(row["profile"] == name for row in candidates) for name in PROFILES
        },
        profile_ids={name: profiles[name]["id"] for name in PROFILES},
        model_configuration_ids={name: configurations[name]["id"] for name in PROFILES},
        all_original_exported_system_messages_match_frozen_profiles=True,
        source_authority="original-HTTP export bound by existing independent qualification",
        wrapper_replaced_or_reconstructed_messages=False,
        historical_candidates_imported=False,
        qualifications_recomputed=False,
        failed_unknown_and_not_started_have_no_positive_rows=True,
    )


def analyze_representation(
    rows: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    binding: dict[str, Any],
    policy: dict[str, Any],
    condition: dict[str, Any],
) -> dict[str, Any]:
    """Reuse exact encoding and CPU packaging, adding exploration-source traceability."""
    checks = validate_profile_bindings(rows, entries, condition)
    identity(policy, "task_panel_representation_policy")
    require(
        policy["maximum_sequence_length"] == 32_768
        and policy["truncation"] is False
        and condition["representation_policy_id"] == policy["id"],
        "exploration_representation.frozen_representation_policy",
    )
    original_rows = canonical_json_bytes(rows)
    result = panel.analyze_representation(rows, entries, binding, policy, condition["id"])
    require(
        canonical_json_bytes(rows) == original_rows,
        "exploration_representation.original_rows_mutated",
    )
    identity(result["binding"], "task_panel_representation_data_binding")
    identity(result["tokens"], "task_panel_token_representation_dataset")
    identity(result["packages"], "task_panel_session_packages")
    by_candidate = {token["row_id"]: token for token in result["tokens"]["records"]}
    by_registration = {
        package["registration_id"]: package for package in result["packages"]["rows"]
    }
    require(
        result["binding"]["generation_condition_id"] == condition["id"]
        and result["binding"]["original_candidate_rows_sha256"] == sha(original_rows)
        and result["binding"]["candidate_ids"] == [row["id"] for row in rows]
        and len(by_candidate) == len(rows)
        and set(by_candidate) == {row["id"] for row in rows}
        and len(by_registration) == result["packages"]["registered_session_count"] == 8
        and set(by_registration) == {entry["registration"]["id"] for entry in entries},
        "exploration_representation.new_data_binding_and_packages",
    )
    session_links = [
        {
            **session,
            "package_id": by_registration[session["registration_id"]]["id"],
            "complete_package": by_registration[session["registration_id"]]["complete"],
        }
        for session in checks["session_rows"]
    ]
    candidate_links = [
        {
            **candidate,
            "token_record_id": by_candidate[candidate["candidate_id"]]["id"],
            "tokenrepresentation_status": by_candidate[candidate["candidate_id"]][
                "tokenrepresentation_status"
            ],
            "package_id": by_registration[candidate["registration_id"]]["id"],
        }
        for candidate in checks["candidate_rows"]
    ]
    exploration_binding = record(
        "support_exploration_representation_binding",
        generation_condition_id=condition["id"],
        profile_check_id=checks["id"],
        representation_policy_id=policy["id"],
        representation_data_binding_id=result["binding"]["id"],
        token_dataset_id=result["tokens"]["id"],
        session_packages_id=result["packages"]["id"],
        cpu_loading_id=result["cpu_loading"]["id"],
        profile_ids=checks["profile_ids"],
        model_configuration_ids=checks["model_configuration_ids"],
        session_links=session_links,
        candidate_links=candidate_links,
        registered_session_count=8,
        candidate_count=len(rows),
        complete_session_packages=result["packages"]["complete_session_packages"],
        all_registered_outcomes_bound=True,
        original_profile_prompts_retained=True,
        guided_responses_relabelled_as_neutral=False,
        raw_messages_and_targets_modified=False,
        historical_supervision_or_token_rows_imported=False,
        exploration_profile_is_semantic_class_label=False,
        profile_mixture_is_optimal_training_weight=False,
        training_weights_materialized=False,
        qualifications_recomputed=False,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
    )
    return {**result, "exploration_binding": exploration_binding, "profile_checks": checks}
