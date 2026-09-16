"""Prospective algorithm scope and strict separation from the live three-arm study."""

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

BASE_COMMIT = "fcb0607b81709479285e30f4e42a8e9f53094647"
BRANCH = "codex/anchored-vtdo-20260913"
PACKAGE = "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_anchored_vtdo"
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_anchored_vtdo"
AUDIT_SHA256 = "a3cd378ed11fc646be48fca14d524f8fadd932931f5c44c9ede120ffddbeddbe"
SEEDS = (11, 29, 47)
CONDITIONS = ("static_alpha0", "c_only_anchored", "full_anchored_vtdo")
POOLS = ("A", "B")
OUTER_EPOCHS = (0, 5)
OUTER_ROUNDS = 2
EPOCHS = 10
EPSILON = 0.05
CONTRIBUTION_EXPONENT = 0.8
NOVELTY_EXPONENT = 0.2
LAMBDA_CURRENT = 4.0
LAMBDA_PRIOR = 1.0
NOVELTY_TEMPERATURE = 1.0
RMS_FLOOR = 1e-8
PROTECTED_STUDY = "trusted_data_synthesis/artifacts/qa_vnext_basis_student/study_20260912"
MATERIALS = (
    "trusted_data_synthesis/artifacts/qa_vnext_readiness_revision/fixed_AB_20260912_materials"
)
SURFACES = "trusted_data_synthesis/artifacts/qa_vnext_eval_surface/surface_20260912"
SURFACE_MANIFEST_ID = "manifest:f29dac61b36396baffd60916bf3b2bdca461a849f0e11bb2d519d54127d2c856"


def require(value, code):
    if not value:
        raise ValueError(code)


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha(value):
    if isinstance(value, Path):
        with value.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def record(kind, **fields):
    body = {"schema_version": "anchored_vtdo.v1." + kind, **copy.deepcopy(fields)}
    return {**body, "id": kind + ":" + sha(encode(body))}


def checked_record(value, kind):
    require(isinstance(value, dict), "anchored.record_object")
    body = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    require(value == record(kind, **body), "anchored.content_identity:" + kind)
    return value


def read_json(path):
    return json.loads(Path(path).read_bytes())


def write_once(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(
        not any(item.is_symlink() for item in (path, *path.parents)), "anchored.no_symlink_output"
    )
    with path.open("xb") as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    return value


def now():
    return datetime.now(timezone.utc).isoformat()


def policy():
    return record(
        "anchored_policy",
        branch=BRANCH,
        base_commit=BASE_COMMIT,
        audit_sha256=AUDIT_SHA256,
        current_scope="independent implementation and CPU validation only",
        new_GPU_or_Student_execution_authorized=False,
        new_Teacher_or_rewrite_or_source_requests_authorized=False,
        live_three_arm_follow_modified=False,
        main_merge_authorized=False,
        finite_support=True,
        original_material_kernel_fixed=True,
        state_catalog="new evidence-bound semantic DAG classes; old signatures retained",
        unresolved_training_states="retain all original packages; block whole new-kernel admission",
        heldout_not_in_state_counts=True,
        actual_method_not_guidance=True,
        initial_distribution="pushforward of original alpha0: dual n/16, control n/8",
        prior="r_h=pi_0,h; not a Teacher natural generation probability",
        independent_pool_supports=True,
        task_marginal="uniform on actual frozen common N",
        contribution="one-step stochastic full-trajectory-feedback Contribution proxy",
        aggregate_virtual_step="all-population G=sum_x mu sum_z pi*g_xz; not next five-task step",
        optimizer="read actual AdamW theta/m/v/step/config; clip and VJP at aggregate G",
        class_gradients="mean original package NLL; model.eval/dropout off for this proxy",
        real_SFT_dropout_unchanged=0.05,
        virtual_step_mutates_real_optimizer=False,
        contribution_sign="a=DU(G)^T(-g_J); C=mu*dot(a,g_xz-E_pi[g_xz])",
        centered_under_current_pi=True,
        probe_feedback="actual complete trajectory qualification",
        probe_temperature=1.0,
        probe_top_p=1.0,
        probe_top_k=0,
        probe_repeats_per_dev_task=2,
        dev_tasks=180,
        confirm_tasks=720,
        probe_max_new_tokens=2048,
        probe_context_tokens=24576,
        probe_max_responses=32,
        probe_max_tools=32,
        probe_guidance="neutral",
        probe_decoder_dropout=False,
        probe_full_denominator=True,
        probe_probability=(
            "all actual sampled tokens including errors and terminating EOS; no tool tokens"
        ),
        probe_probability_length_normalization=False,
        probe_probability_parameter_point="same virtual theta",
        probe_seed_key=["pool", "training_seed", "outer_round", "task_id", "repeat"],
        probe_seed_omits_condition_for_common_random_numbers=True,
        successful_probes_only_normalization=False,
        probe_becomes_SFT_material=False,
        reward_gradient_updates_real_Student_directly=False,
        all_zero_rewards="uninformative feedback, not proof of zero theoretical Contribution",
        novelty="positive part log(r/pi), same task/support",
        epsilon=EPSILON,
        contribution_exponent=CONTRIBUTION_EXPONENT,
        novelty_exponent=NOVELTY_EXPONENT,
        c_only_contribution_exponent_unchanged=CONTRIBUTION_EXPONENT,
        novelty_temperature=NOVELTY_TEMPERATURE,
        contribution_temperature="mu(x)*max(RMS(C/mu over noncontrol, mu*pi normalized),1e-8)",
        contribution_RMS_floor=RMS_FLOOR,
        lambda_current=LAMBDA_CURRENT,
        lambda_prior=LAMBDA_PRIOR,
        controls="current pi must equal r; unchanged in both updates",
        update="exact log-space dual-KL proximal softmax; no probability clipping",
        rounds=OUTER_ROUNDS,
        outer_epoch_boundaries=list(OUTER_EPOCHS),
        inner_epochs=EPOCHS,
        inner_coefficient="pi_t(z|x)/(5*n_hxz*whole_package_target_tokens)",
        physical_training_packages_per_update=64,
        unique_final_epoch=10,
        conditions=list(CONDITIONS),
        primary_algorithm="full_anchored_vtdo",
        A_conditions=list(CONDITIONS),
        B_conditions=[CONDITIONS[0], CONDITIONS[2]],
        B_uses_dev_for_its_own_full_VTDO_feedback=True,
        A_distribution_copied_to_B=False,
        plus_minus_selector_used=False,
        C_only_may_replace_primary_after_results=False,
        maximum_training_protocols=15,
        feedback_runs=9,
        conditional_feedback_sessions=6480,
        conditional_final_greedy_sessions=10260,
        conditional_total_local_Student_sessions=16740,
        budget_is_new_proposal_not_inherited_authorization=True,
        feedback_work_separate_from_ten_pass_SFT_budget=True,
        baseline_reuse=(
            "only exact actual material/config/initialization/trajectory/checkpoint identity; "
            "no name-based credit"
        ),
        confirmation=(
            "must freeze algorithm and comparison before using old confirmation outcomes "
            "for new design"
        ),
        prior_confirmation_outcomes_read_by_new_branch=False,
        no_confirmation_results_visibility_assumption_from_git_publication=True,
        kernel_tests_are_real_Qwen_or_utility_results=False,
        unprovided_reference_zip_used=False,
    )
