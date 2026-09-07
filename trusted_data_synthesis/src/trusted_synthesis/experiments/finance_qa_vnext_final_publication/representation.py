"""Six-session exact exports retain Final publication, feedback and real N/E prompts."""

from __future__ import annotations

from collections import Counter

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.final_public_contract import (
    public_final_contract,
    public_final_schema,
)

from ..finance_qa_vnext_model_execution import representation as original
from ..finance_qa_vnext_model_execution.models import identity, record, require, sha
from ..finance_qa_vnext_model_execution.transport import SYSTEM_PROMPT
from ..finance_qa_vnext_task_panel import representation as panel

PROFILES = ("N", "E")
representation_policy = panel.representation_policy


def validate_profile_bindings(rows, entries, condition):
    identity(condition, "final_publication_condition")
    tasks = {task["task_group"]: task for task in condition["tasks"]}
    profiles, configs = condition["profiles"], condition["configurations"]
    require(
        set(profiles) == set(configs) == set(PROFILES)
        and condition["registered_session_count"] == len(entries) == len(tasks) * 2
        and condition["registered_labels"] == [entry["label"] for entry in entries]
        and len({entry["registration"]["id"] for entry in entries}) == len(entries)
        and len({entry["registration"]["session_id"] for entry in entries}) == len(entries),
        "final_representation.frozen_population",
    )
    require(
        profiles["N"]["system_prompt"] == SYSTEM_PROMPT
        and profiles["E"]["system_prompt"].startswith(SYSTEM_PROMPT + "\n\n")
        and len(profiles["E"]["system_prompt"]) > len(SYSTEM_PROMPT) + 2
        and all(
            profiles[name]["system_prompt"] == configs[name]["system_prompt"] for name in PROFILES
        ),
        "final_representation.frozen_profile_prompts",
    )
    require(
        Counter(
            (entry["registration"]["task_group"], entry["registration"]["profile"])
            for entry in entries
        )
        == Counter({(task, name): 1 for task in tasks for name in PROFILES}),
        "final_representation.per_task_profile_denominators",
    )
    session_links, candidate_links, expected = [], [], []
    for entry in entries:
        reg, q, session, export = (
            entry[k] for k in ("registration", "qualification", "session", "export")
        )
        identity(reg, "session_registration")
        identity(q, "qualification")
        identity(export, "supervision_export")
        task, profile = tasks[reg["task_group"]], reg["profile"]
        require(
            reg["run_condition_id"] == condition["id"]
            and reg["profile_id"] == profiles[profile]["id"]
            and reg["model_configuration_id"]
            == q["model_configuration_id"]
            == configs[profile]["id"]
            and q["registration_id"] == reg["id"]
            and q["registered_session_id"] == reg["session_id"]
            and q["session_id"] == (session["id"] if session else None)
            and export["qualification_id"] == q["id"]
            and export["session_id"] == q["session_id"]
            and all(
                reg[key] == q[key] == task[key]
                for key in (
                    "task_id",
                    "context_id",
                    "protocol_id",
                    "registry_hash",
                    "task_group",
                    "task_type",
                )
            ),
            "final_representation.new_task_profile_parents",
        )
        require(panel._eligible(q) or not export["rows"], "final_representation.failed_positive")
        if session is not None:
            require(
                session["callback_binding"]["model_configuration_id"] == configs[profile]["id"],
                "final_representation.actual_callback_configuration",
            )
        session_links.append(
            {
                "label": entry["label"],
                "task_id": task["task_id"],
                "context_id": task["context_id"],
                "task_group": task["task_group"],
                "profile": profile,
                "profile_id": reg["profile_id"],
                "model_configuration_id": reg["model_configuration_id"],
                "registration_id": reg["id"],
                "session_id": q["session_id"],
                "qualification_id": q["id"],
                "qualification_status": q["status"],
                "export_id": export["id"],
                "candidate_ids": [row["id"] for row in export["rows"]],
            }
        )
        for row in export["rows"]:
            original._candidate(row)
            messages = original._messages(row["messages"])
            require(session is not None, "final_representation.missing_original_session")
            event = session["events"][row["turn_index"]]
            require(
                event["request"].get("public_final_contract") == public_final_contract()
                and event["request"]["response_schemas"]["final"] == public_final_schema(),
                "final_representation.actual_final_rules_not_preserved",
            )
            require(
                messages[0] == {"role": "system", "content": configs[profile]["system_prompt"]}
                and messages[1]["content"].encode("utf-8") == canonical_json_bytes(event["request"])
                and row["registration_id"] == reg["id"]
                and row["qualification_id"] == q["id"]
                and row["public_request_id"] == event["request"]["id"]
                and row["target_raw_sha256"] == event["submission"]["raw_sha256"]
                and row["target_raw_byte_count"] == event["submission"]["raw_bytes"],
                "final_representation.original_profile_request_and_target",
            )
            candidate_links.append(
                {
                    "candidate_id": row["id"],
                    "label": entry["label"],
                    "profile": profile,
                    "task_id": task["task_id"],
                    "context_id": task["context_id"],
                    "profile_id": reg["profile_id"],
                    "model_configuration_id": reg["model_configuration_id"],
                    "registration_id": reg["id"],
                    "qualification_id": q["id"],
                    "session_id": q["session_id"],
                    "turn_index": row["turn_index"],
                    "public_request_id": row["public_request_id"],
                    "messages_sha256": sha(canonical_json_bytes(messages)),
                    "system_prompt_sha256": sha(messages[0]["content"].encode()),
                    "target_raw_sha256": row["target_raw_sha256"],
                    "target_raw_byte_count": row["target_raw_byte_count"],
                    "actual_profile_prompt_preserved": True,
                }
            )
        expected.extend(export["rows"])
    require(
        canonical_json_bytes(rows) == canonical_json_bytes(expected)
        and len({row["id"] for row in rows}) == len(rows),
        "final_representation.complete_original_exports",
    )
    return record(
        "final_publication_representation_profile_checks",
        generation_condition_id=condition["id"],
        registered_session_count=len(entries),
        task_count=len(tasks),
        session_rows=session_links,
        candidate_rows=candidate_links,
        candidate_count=len(rows),
        profile_ids={name: profiles[name]["id"] for name in PROFILES},
        model_configuration_ids={name: configs[name]["id"] for name in PROFILES},
        candidate_counts_by_profile={
            name: sum(c["profile"] == name for c in candidate_links) for name in PROFILES
        },
        all_original_exported_system_messages_match_frozen_profiles=True,
        historical_candidates_imported=False,
        qualifications_recomputed=False,
        failed_unknown_and_not_started_have_no_positive_rows=True,
    )


def analyze_representation(rows, entries, binding, policy, condition):
    checks = validate_profile_bindings(rows, entries, condition)
    require(
        policy["maximum_sequence_length"] == 32_768
        and policy["truncation"] is False
        and condition["representation_policy_id"] == policy["id"],
        "final_representation.frozen_policy",
    )
    before = canonical_json_bytes(rows)
    result = panel.analyze_representation(rows, entries, binding, policy, condition["id"])
    require(canonical_json_bytes(rows) == before, "final_representation.rows_mutated")
    tokens = {token["row_id"]: token for token in result["tokens"]["records"]}
    packages = {package["registration_id"]: package for package in result["packages"]["rows"]}
    require(
        set(tokens) == {row["id"] for row in rows}
        and set(packages) == {entry["registration"]["id"] for entry in entries}
        and result["binding"]["generation_condition_id"] == condition["id"],
        "final_representation.new_data_binding",
    )
    linked = record(
        "final_publication_representation_binding",
        generation_condition_id=condition["id"],
        profile_check_id=checks["id"],
        representation_policy_id=policy["id"],
        representation_data_binding_id=result["binding"]["id"],
        token_dataset_id=result["tokens"]["id"],
        session_packages_id=result["packages"]["id"],
        cpu_loading_id=result["cpu_loading"]["id"],
        session_links=[
            {
                **row,
                "package_id": packages[row["registration_id"]]["id"],
                "complete_package": packages[row["registration_id"]]["complete"],
            }
            for row in checks["session_rows"]
        ],
        candidate_links=[
            {
                **row,
                "token_record_id": tokens[row["candidate_id"]]["id"],
                "tokenrepresentation_status": tokens[row["candidate_id"]][
                    "tokenrepresentation_status"
                ],
                "package_id": packages[row["registration_id"]]["id"],
            }
            for row in checks["candidate_rows"]
        ],
        registered_session_count=len(entries),
        candidate_count=len(rows),
        complete_session_packages=result["packages"]["complete_session_packages"],
        original_profile_prompts_retained=True,
        raw_messages_and_targets_modified=False,
        final_public_contract_and_actual_feedback_preserved=True,
        historical_supervision_or_token_rows_imported=False,
        training_weights_materialized=False,
        profile_composition_may_change_under_future_class_reweighting=True,
        independent_samples_added_by_copying=False,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
    )
    return {**result, "final_publication": linked, "profile_checks": checks}
