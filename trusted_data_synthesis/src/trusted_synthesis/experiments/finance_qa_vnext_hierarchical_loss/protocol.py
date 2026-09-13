"""Prospective loss-only comparison; no inherited real-study authorization."""

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

PARENT_COMMIT = "bab60b79fdcec2742ee5d88b729c1b50ae3d17a6"
BRANCH = "codex/anchored-vtdo-hierarchical-loss"
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_hierarchical_loss"
)
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_hierarchical_loss"
AUDIT_SHA256 = "4d013d4d443f4d4bb2b4d81b2f903699383707a66890d1dc817cc0241222bad5"
LAYERS = ("reasoning", "tools", "final")
OBJECTIVES = ("full_token_mean", "hierarchical")
PROFILES = ("public_rtf", "public_tf")
WEIGHTS = {
    "public_rtf": {"reasoning": "3/10", "tools": "1/2", "final": "1/5"},
    "public_tf": {"reasoning": "0", "tools": "1/2", "final": "1/5"},
}


def require(value, code):
    if not value:
        raise ValueError(code)


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(value):
    if isinstance(value, Path):
        with value.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def record(kind, **fields):
    body = {"schema_version": "hierarchical_loss.v1." + kind, **copy.deepcopy(fields)}
    return {**body, "id": kind + ":" + sha(encode(body))}


def checked_record(value, kind):
    require(isinstance(value, dict), "hierarchical.record_object")
    fields = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    require(value == record(kind, **fields), "hierarchical.content_identity:" + kind)
    return value


def now():
    return datetime.now(timezone.utc).isoformat()


def write_once(path, value):
    path = Path(path)
    require(
        not any(p.is_symlink() for p in (path, *path.parents)), "hierarchical.no_symlink_output"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    return value


def policy(profile="public_rtf"):
    require(profile in PROFILES, "hierarchical.frozen_availability_profile")
    return record(
        "hierarchical_policy",
        branch=BRANCH,
        parent_commit=PARENT_COMMIT,
        audit_sha256=AUDIT_SHA256,
        profile=profile,
        weights=WEIGHTS[profile],
        weights_learned_or_swept=False,
        missing_reasoning="prospectively select public_tf globally; no hidden-reasoning extraction",
        missing_positive_weight_layer="block common pair; never drop a package or renormalize",
        public_tf_weight_sum="7/10, explicitly not renormalized",
        original_full_baseline="original sum target NLL / original whole-package target count",
        layer_means_with_111_are_original_full_SFT=False,
        hierarchical_package_loss="sum_k lambda_k * sum_original_target_NLL_k / package_count_k",
        within_state_kernel=(
            "mean over all original packages; never pool their tokens into a new kernel"
        ),
        five_task_coefficient="pi(z|x)/(5*n_train(x,z)) * lambda_k/package_count_k",
        full_token_coefficient="pi(z|x)/(5*n_train(x,z)*original_whole_package_target_count)",
        pi_applied_once=True,
        original_context_and_token_order_unchanged=True,
        original_rows_rewritten=False,
        tool_observations_are_targets=False,
        full_trajectory_feedback_probability_unchanged=True,
        primary_metric="CompletePass",
        secondary_metrics=["tool_success", "final_success"],
        reasoning_quality_metric="not scored without independently registered authority",
        first_comparison=list(OBJECTIVES),
        first_comparison_fixed_pi=True,
        same_materials_initial_model_optimizer_seed_schedule=True,
        first_comparison_adaptive_pi_updates=0,
        hierarchical_class_gradient=(
            "different g_xz; unchanged C formula does not imply unchanged C values"
        ),
        hypothesis="unmeasured; tool/final diagnostics do not by themselves prove causation",
        main_or_existing_anchored_branch_modified=False,
        actual_financial_GPU_comparison_admitted=False,
        parent_real_Qwen_feedback_adapter="NOT_VALIDATED_IN_PARENT",
        new_Teacher_or_rewrite_requests_authorized=False,
        only_two_conditions_no_ablation_search=True,
    )
