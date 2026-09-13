"""New purpose and identities for the externally requested fixed-kernel study."""

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ..finance_qa_vnext_basis_scale_preparation import design as original_design
from ..finance_qa_vnext_eval_readiness import training_runtime as original_runtime
from ..finance_qa_vnext_probe_coverage import protocol as coverage

BRANCH = "codex/fixed-kernel-value-20260913"
BASE_COMMIT = "4733ad057e19c2aaf5ed25bcad2f87e78e821047"
MAIN_COMMIT = coverage.MAIN_COMMIT
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_fixed_kernel_value"
)
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/study_20260913"
RUNTIME = "trusted_data_synthesis/runtime/fixed_kernel_value_20260913"
WALLET = coverage.WALLET
OWNER = coverage.OWNER
REVISION, REVISION_MANIFEST = coverage.REVISION, coverage.REVISION_MANIFEST
AUDIT_PATH = (
    "/home/zhuxinrui/.codex/attachments/7585560f-eae8-49d0-b6c8-32d12aaee0c0/pasted-text.txt"
)
DIRECTIVE = "参照审计继续实验，当前GPU空闲，尽快使用，避免资源浪费"
MODEL, ENDPOINT = coverage.MODEL, coverage.ENDPOINT
SEEDS, ARMS, POOLS = original_design.SEEDS, original_design.ARMS, original_design.POOLS
FAMILIES = ("annual_flow", "stock_rollforward", "company_defined_metric", "control")
TASK_COUNTS = dict(zip(FAMILIES, (40, 40, 40, 80), strict=True))
TASK_CAP, SESSION_CAP = 200, 10240
REPLICATES, TRAIN_REPLICATES, SEALED_REPLICATES = 16, 12, 4
ORDER_SEED = 20260914
MAX_RESPONSES, MAX_TOOLS = 32, 32
WORKERS, CPU_WORKERS = 128, 24
INPUT_ALLOWANCE, OUTPUT_ALLOWANCE = 99328, 16384
REQUEST_RESERVATION = INPUT_ALLOWANCE + OUTPUT_ALLOWANCE
REQUEST_CAP, TOKEN_CAP, COMMON_CAP = SESSION_CAP * MAX_RESPONSES, 250000000, 1000000000
MAX_BODY_BYTES, PUBLIC_RESPONSE_BYTES, SEQUENCE_CAP = 98304, 65536, 24576
PROTOCOL = "fixed_kernel_material_runtime.v1"
TARGET_PROFILE, CONTROL_PROFILE = "P2_method_delivery", "delivery_neutral_control"
PROFILES = (TARGET_PROFILE, CONTROL_PROFILE)
BASES = ("endpoint", "movement", "neutral")


def require(value, code):
    if not value:
        raise ValueError("fixed_kernel." + code)


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
    require(not {"id", "schema_version"} & set(fields), "reserved_record_fields")
    body = {"schema_version": "fixed_kernel_value.v1." + kind, **copy.deepcopy(fields)}
    return {**body, "id": kind + ":" + sha(encode(body))}


def checked(value, kind):
    require(isinstance(value, dict), "record_object")
    expected = record(kind, **{k: v for k, v in value.items() if k not in {"id", "schema_version"}})
    require(value == expected, "content_identity:" + kind)
    return value


def checked_record(value, kind):
    return checked(value, kind)


def read_json(path):
    return json.loads(Path(path).read_bytes())


def now():
    return datetime.now(timezone.utc).isoformat()


def write_once(path, value):
    path = Path(path)
    require(
        ".." not in path.parts and not any(x.is_symlink() for x in (path, *path.parents)),
        "safe_exclusive_path",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return value


def system_prompt(profile, basis):
    if profile == TARGET_PROFILE:
        require(basis in ("endpoint", "movement"), "target_guidance")
        return coverage.system_prompt(TARGET_PROFILE, basis)
    require(profile == CONTROL_PROFILE and basis == "neutral", "neutral_control_protocol")
    return original_runtime.SYSTEM + "\n\n" + coverage.DELIVERY


def validate_registry(registry, population, freeze_id):
    from .population import make_registry

    checked(registry, "material_registry")
    checked(population, "population")
    require(
        registry == make_registry(population, freeze_id, order_seed=ORDER_SEED),
        "exact_full_preregistered_material_matrix",
    )
    return registry


def policy():
    return record(
        "fixed_kernel_policy",
        branch=BRANCH,
        parent_commit=BASE_COMMIT,
        experiment="finite method-mass training value on a fixed empirical original-package kernel",
        new_independent_experiment_not_reopening_old_AB=True,
        design_adopted_prospectively_under_current_audit_directive_and_resource_authorization=True,
        source_boundary_and_executable_mapping_new_version_frozen_before_generation=True,
        public_tasks_sources_unchanged_and_not_restricted_to_oracle_locators=True,
        old_144_development_only_not_mixed_into_formal_materials=True,
        scientific_task_count=TASK_CAP,
        task_family_counts=TASK_COUNTS,
        task_selection="family-specific sorted source-cluster round robin; sorted TaskID inside cluster; metadata only",
        task_mass="1/200",
        pools=list(POOLS),
        target_generation_protocol=TARGET_PROFILE,
        target_protocol_byte_identical_to_previous_P2=True,
        control_generation_protocol=CONTROL_PROFILE,
        control_has_no_route_guidance=True,
        replicates_per_pool_task_guidance=REPLICATES,
        train_replicates_before_outcomes=list(range(TRAIN_REPLICATES)),
        sealed_replicates_before_outcomes=list(range(TRAIN_REPLICATES, REPLICATES)),
        registered_sessions=SESSION_CAP,
        assignment_order_seed=ORDER_SEED,
        assignment_seed_is_not_model_generation_seed=True,
        generation_workers=WORKERS,
        CPU_assessment_workers=CPU_WORKERS,
        maximum_responses=MAX_RESPONSES,
        maximum_tools=MAX_TOOLS,
        model=MODEL,
        endpoint=ENDPOINT,
        thinking={"type": "enabled"},
        reasoning_effort="high",
        response_format={"type": "json_object"},
        output_cap=OUTPUT_ALLOWANCE,
        stream=False,
        temperature_top_p_generation_seed_omitted=True,
        maximum_serialized_body_bytes=MAX_BODY_BYTES,
        maximum_public_response_bytes=PUBLIC_RESPONSE_BYTES,
        input_reservation=INPUT_ALLOWANCE,
        request_reservation=REQUEST_RESERVATION,
        request_cap=REQUEST_CAP,
        purpose_token_cap=TOKEN_CAP,
        common_token_cap=COMMON_CAP,
        same_existing_wallet_fifth_purpose=True,
        old_charges_and_unknown_leases_not_reset=True,
        unsent_cancellation="only reserved before sender starts may become not_sent at known zero cost; original lease retained",
        sent_or_unknown_reservations_never_cancelled_or_refunded=True,
        budget_cap_does_not_guarantee_all_maximum_response_budgets=True,
        HTTP_retries=0,
        rollout_resampling=0,
        full_registered_collection_required_before_material_admission=True,
        failed_or_unknown_or_unrequested_remain_in_fixed_denominator=True,
        all_qualified_consumable_train_packages_retained=True,
        sealed_candidates_never_backfilled_into_training=True,
        old_top8_or_8_plus_2_gate_not_reinterpreted=True,
        maximum_sequence_length=SEQUENCE_CAP,
        no_truncation_or_replacement=True,
        supervision="original successful public tool/Final targets in complete original input histories; no private CoT",
        task_without_material_in_either_pool="FAIL_INPUT_SUPPORT; no replacement or task-mass redistribution",
        single_state_tasks="remain in all arms with fixed task mass",
        intervention_set="tasks with both actual endpoint and movement train support in both pools",
        within_state_material_kernel="uniform over all actual eligible original train packages",
        outside_intervention_static_kernel="uniform over all eligible original train packages for that task and pool",
        method_mass={"alpha0": ["1/2", "1/2"], "plus": ["1/3", "2/3"], "minus": ["2/3", "1/3"]},
        fine_class_mass_within_method="method_mass * n_state / n_method",
        token_coefficient="pi(state|task)/(5*n_state*whole_package_target_tokens)",
        minimum_global_mass_shift="1/20",
        measured_global_mass_shift="|shared_intervention_tasks|/(6*200)",
        minimum_shared_intervention_tasks=60,
        dose_gate_is_design_not_VTDO_theorem_or_power_guarantee=True,
        no_threshold_step_size_or_population_changes_after_outcomes=True,
        physical_materials_order_and_processing_amount_same_across_arms=True,
        tasks_per_update=5,
        batch_composition={
            "annual_flow": 1,
            "stock_rollforward": 1,
            "company_defined_metric": 1,
            "control": 2,
        },
        epochs=10,
        optimizer_updates=400,
        packages_per_update="all eligible packages of the five tasks, variable count",
        update="zero_grad once; all physical packages backward; clip once; step once",
        seeds=list(SEEDS),
        arms=list(ARMS),
        existing_model_LoRA_optimizer_Full_domain_preserved=True,
        maximum_parallel_GPU_workers=8,
        maximum_training_runs=15,
        A_development_sessions=1620,
        maximum_confirmation_sessions=8640,
        maximum_Student_evaluation_sessions=10260,
        selection="paired mean complete-trajectory dev gain strictly positive; tie priority alpha0,plus,minus",
        no_move="retain baseline; no B duplicate training or candidate confirmation",
        independent_protected_evaluation_surfaces="same original 900; 180 dev and 720 confirm; no movement guidance",
        evaluation_primary="three benchmark groups equally weighted complete-trajectory qualification",
        seed_repeats_not_independent_questions=True,
        preliminary_GPU_use="bounded engineering checks only; discard temporary state; no scientific effect claims",
        scientific_training_requires_closed_full_collection_and_all_task_support_and_registered_dose=True,
        anchored_real_distribution_updates_not_claimed_from_this_method_direction_test=True,
        Hierarchical_Loss_experiments_not_in_this_study=True,
    )
