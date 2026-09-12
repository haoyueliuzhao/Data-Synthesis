"""Whole original-response packages and exact CPU-tokenizer materialization.

This interface has no pool selection, quota replacement, weights, model loading,
training or GPU path. Scripted controls never become Teacher training samples.
"""

import copy
from pathlib import Path

from ..finance_qa_vnext_model_execution.representation import encode_original_candidate
from ..qa_reasoning_share_training_preflight import tokenization as assets
from .worker import encode, record, require, sha

MAXIMUM_SEQUENCE_LENGTH = assets.MAX_SEQUENCE_LENGTH


def raw_package(session, assessment):
    require(
        assessment["session_id"] == session["id"] and assessment["raw_history_and_tools_replayed"],
        "materials.replayed_session_join",
    )
    require(
        session["id"]
        == record(
            "session", **{k: v for k, v in session.items() if k not in {"id", "schema_version"}}
        )["id"],
        "materials.session_identity",
    )
    rows = []
    for turn, event in zip(session["turns"], session["events"], strict=True):
        require(
            turn["response_index"] == event["response_index"]
            and sha(turn["raw_response"].encode()) == turn["raw_response_sha256"],
            "materials.original_response_join",
        )
        positive = event["final"] or (
            event["tool_call"] is not None and event["tool_call"]["status"] == "ok"
        )
        if not positive:
            continue
        rows.append(
            record(
                "original_response_candidate",
                task_id=session["identity"]["task_id"],
                session_id=session["id"],
                qualification_id=assessment["id"],
                public_runtime_state_id="history:" + sha(encode(turn["input_messages"])),
                response_index=turn["response_index"],
                messages=copy.deepcopy(turn["input_messages"]),
                target_text=turn["raw_response"],
                target_raw_sha256=turn["raw_response_sha256"],
                response_kind="Final" if event["final"] else event["tool_call"]["tool"],
                requested_basis=session["requested_basis"],
                actual_method=assessment["actual_method"],
                surface_version_id=session["identity"]["surface_version_id"],
                public_messages_sha256=session["identity"]["public_messages_sha256"],
                origin=session["origin"],
                training_sample=False,
                class_weights_assigned=False,
            )
        )
    return record(
        "raw_package",
        task_id=session["identity"]["task_id"],
        session_id=session["id"],
        assessment_id=assessment["id"],
        candidates=rows,
        all_raw_turns_retained=copy.deepcopy(session["turns"]),
        failed_or_format_responses_retained_in_original_later_histories=True,
        financial_valid=assessment["financial_valid"],
        actual_method=assessment["actual_method"],
        full_mapping_status=assessment["full_mapping_status"],
        full_class=assessment["full_class"],
        origin=session["origin"],
        training_eligible=False,
        training_samples=0,
        complete_first_final_package=bool(rows) and rows[-1]["response_kind"] == "Final",
    )


def load_local_tokenizer(root):
    """Validate five pinned assets and construct one tokenizer; never fetch remotely.

    register_tokenizer and load_tokenizer each construct an AutoTokenizer. Reuse
    their shared validated primitive once, preserving its exact binding checks.
    """
    return assets._binding_and_tokenizer(Path(root), assets.MODEL_DIRECTORY)


def materialize_packages(
    packages, root, *, loader=load_local_tokenizer, maximum_sequence_length=MAXIMUM_SEQUENCE_LENGTH
):
    """Attempt every selected control row; retain not-fit/error rows, no replacement."""
    require(
        type(maximum_sequence_length) is int
        and 1 <= maximum_sequence_length <= MAXIMUM_SEQUENCE_LENGTH,
        "materials.frozen_sequence_cap",
    )
    require(isinstance(packages, list), "materials.package_list")
    require(
        len({package["session_id"] for package in packages}) == len(packages),
        "materials.unique_original_sessions",
    )
    policy = record(
        "representation_policy",
        maximum_sequence_length=maximum_sequence_length,
        truncation=False,
        mask_policy=assets.MASK_POLICY,
        exact_encoder="model_execution.encode_original_candidate",
        original_public_surface_and_guidance_preserved=True,
        origin="scripted_interface_control",
        training_allowed=False,
    )
    checks, failures = [], []
    for package in packages:
        require(
            package["id"]
            == record(
                "raw_package",
                **{k: v for k, v in package.items() if k not in {"id", "schema_version"}},
            )["id"],
            "materials.package_identity",
        )
        require(
            package["origin"] == "scripted_interface_control" and package["training_samples"] == 0,
            "materials.control_only_stage",
        )
        require(
            package["financial_valid"] and package["complete_first_final_package"],
            "materials.qualified_complete_control_fixture",
        )
        previous_index = -1
        raw = {turn["response_index"]: turn for turn in package["all_raw_turns_retained"]}
        for row in package["candidates"]:
            require(
                row["id"]
                == record(
                    "original_response_candidate",
                    **{k: v for k, v in row.items() if k not in {"id", "schema_version"}},
                )["id"],
                "materials.candidate_identity",
            )
            require(
                row["session_id"] == package["session_id"]
                and row["qualification_id"] == package["assessment_id"]
                and row["response_index"] > previous_index,
                "materials.whole_session_package",
            )
            turn = raw[row["response_index"]]
            require(
                row["messages"] == turn["input_messages"]
                and row["target_text"] == turn["raw_response"]
                and row["target_raw_sha256"] == sha(turn["raw_response"].encode()),
                "materials.original_bytes",
            )
            previous_index = row["response_index"]
    if not packages:
        return record(
            "materialization",
            status="NO_PACKAGES",
            policy=policy,
            packages=0,
            checks=[],
            failures=[],
            tokenizer_loads=0,
            training_samples=0,
            model_weight_loads=0,
            gpu_calls=0,
            provider_calls=0,
        )
    phase = "tokenizer_loading"
    try:
        binding, tokenizer = loader(root)
        phase = "tokenizer_binding_limits"
        require(
            type(binding.get("maximum_sequence_length")) is int
            and maximum_sequence_length
            <= binding["maximum_sequence_length"]
            <= MAXIMUM_SEQUENCE_LENGTH,
            "materials.bound_sequence_cap",
        )
        require(
            type(binding.get("model_max_position_embeddings")) is int
            and maximum_sequence_length <= binding["model_max_position_embeddings"],
            "materials.bound_model_context_limit",
        )
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, ImportError) as error:
        return record(
            "materialization",
            status=(
                "TOKENIZER_UNAVAILABLE"
                if phase == "tokenizer_loading"
                else "TOKENIZER_BINDING_REJECTED"
            ),
            policy=policy,
            packages=len(packages),
            checks=[],
            failures=[{"phase": phase, "reason": str(error)}],
            tokenizer_loads=1,
            training_samples=0,
            model_weight_loads=0,
            gpu_calls=0,
            provider_calls=0,
        )
    for package in packages:
        for row in package["candidates"]:
            try:
                encoded = encode_original_candidate(
                    row, binding, tokenizer, maximum_sequence_length=maximum_sequence_length
                )
                checks.append(
                    record(
                        "token_check",
                        package_id=package["id"],
                        candidate_id=row["id"],
                        policy_id=policy["id"],
                        representation=encoded,
                        status="PASS" if encoded["consumable_token_representation"] else "FAIL",
                    )
                )
                if not encoded["consumable_token_representation"]:
                    failures.append({"candidate_id": row["id"], "reason": encoded["reason"]})
            except (ValueError, TypeError, KeyError, UnicodeError, RuntimeError) as error:
                checks.append(
                    record(
                        "token_check",
                        package_id=package["id"],
                        candidate_id=row["id"],
                        policy_id=policy["id"],
                        representation=None,
                        status="FAIL",
                    )
                )
                failures.append({"candidate_id": row["id"], "reason": str(error)})
    return record(
        "materialization",
        status="PASS_SCRIPTED_REPRESENTATION_ONLY" if not failures else "REPRESENTATION_FAILED",
        policy=policy,
        binding=binding,
        packages=len(packages),
        checks=checks,
        failures=failures,
        tokenizer_loads=1,
        encoded_rows=len(checks),
        training_samples=0,
        model_weight_loads=0,
        gpu_calls=0,
        provider_calls=0,
        target_tokens=sum(
            check["representation"]["target_token_count"]
            for check in checks
            if check["representation"]
        ),
        no_truncation_rewrite_prefix_substitution_or_package_replacement=True,
    )
