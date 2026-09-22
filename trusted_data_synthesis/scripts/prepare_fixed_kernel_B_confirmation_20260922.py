"""Freeze the newly authorized B main comparison before any B GPU work or confirm content."""

# ruff: noqa: E501 -- explicit preregistered scientific and resource contracts
import argparse
import copy
import subprocess
from pathlib import Path

import fixed_kernel_B_common_20260922 as b
import fixed_kernel_B_confirm_views_20260922 as confirm
import fixed_kernel_B_confirmation_statistics_20260922 as statistics
import fixed_kernel_B_materials_20260922 as material

p = b.p
SCRIPT = "trusted_data_synthesis/scripts/prepare_fixed_kernel_B_confirmation_20260922.py"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/199ed60f-ba5d-42e8-8825-84bda226d1f0/pasted-text.txt"
)
NEW_SOURCES = (
    SCRIPT,
    b.SCRIPT,
    "trusted_data_synthesis/scripts/fixed_kernel_B_materials_20260922.py",
    confirm.SCRIPT,
    "trusted_data_synthesis/scripts/fixed_kernel_B_confirmation_statistics_20260922.py",
    "trusted_data_synthesis/scripts/fixed_kernel_B_training_worker_20260922.py",
    "trusted_data_synthesis/scripts/fixed_kernel_B_generation_20260922.py",
    "trusted_data_synthesis/scripts/fixed_kernel_B_outer_worker_20260922.py",
    "trusted_data_synthesis/scripts/fixed_kernel_B_scoring_20260922.py",
    "trusted_data_synthesis/scripts/run_fixed_kernel_B_confirmation_20260922.py",
)


def prepare(root):
    root = Path(root).resolve()
    p.require(not (b.RAW / "protocol.json").exists(), "B.one_scientific_registration")
    materials = material.load_B_materials(root)
    registry = confirm.registry(root)
    p.require(
        not {row["task_id"] for row in registry} & {row["task_id"] for row in materials["tasks"]}
        and not {row["source_cluster"] for row in registry}
        & {row["source_cluster"] for row in materials["tasks"]},
        "B.confirm_task_and_CIK_disjoint_from_dev_metadata",
    )
    previous = p.read_json(root / b.d.inputs.BASE / "delayed_C_recovery_20260921/report.json")
    p.require(
        previous["status"] == "COMPLETE_THREE_DELAYED_C_RUNS_AFTER_RECOVERY"
        and previous["primary_mean_difference"] > 0,
        "B.frozen_positive_candidate_without_new_per_seed_gate",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    parent = p.read_json(root / b.d.OUTPUT / "plan.json")
    paths = sorted(
        set(parent["sources"])
        | set(NEW_SOURCES)
        | set(confirm.CODE_PATHS)
        | {
            "trusted_data_synthesis/scripts/fixed_kernel_delayed_C_recovery_state_20260921.py",
            "trusted_data_synthesis/scripts/fixed_kernel_delayed_C_autorun_state_20260921.py",
        }
    )
    sources = {}
    for name in paths:
        payload = (root / name).read_bytes()
        p.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "B.committed_code_before_registration:" + name,
        )
        sources[name] = p.sha(payload)
    dev_tasks = copy.deepcopy(materials["tasks"])
    for row in dev_tasks:
        row["path"] = str((root / row["path"]).resolve())
    jobs = []
    for seed in (11, 29, 47):
        prefix_key = f"B_prefix_{seed}"
        jobs.append(
            dict(
                key=prefix_key,
                seed=seed,
                condition="prefix",
                pool="B",
                start=0,
                stop=200,
                prefix_key=prefix_key,
            )
        )
        for condition in ("static", "delayed_c"):
            jobs.append(
                dict(
                    key=f"B_{condition}_{seed}",
                    seed=seed,
                    condition=condition,
                    pool="B",
                    start=200,
                    stop=400,
                    prefix_key=prefix_key,
                )
            )
    compiler_sources = {name: sources[name] for name in confirm.CODE_PATHS}
    plan = p.record(
        "B_confirm_protocol",
        frozen=True,
        authorization="2026-09-22 user: 参照审计继续实验",
        audit_attachment_sha256=p.sha(AUDIT),
        previous_completion_id=previous["id"],
        previous_scope_status="PASS_AS_SCOPED",
        code_commit=head,
        repository_root=str(root),
        new_B_training_and_confirmation_authorized=True,
        candidate="Delayed-C",
        baseline="Static",
        split="confirm",
        confirm_tasks=720,
        tasks_per_group=240,
        seeds=[11, 29, 47],
        models_count=6,
        pool="B",
        B_is_same_training_tasks_new_material_kernel=True,
        training_jobs=jobs,
        materials=materials,
        dev_tasks=dev_tasks,
        confirm_registry=registry,
        confirm_registry_sha256=p.sha(p.encode(registry)),
        confirm_CIK_count=len({row["source_cluster"] for row in registry}),
        dev_CIK_count=len({row["source_cluster"] for row in materials["tasks"]}),
        confirm_task_and_CIK_disjoint_from_dev=True,
        confirm_CIK_count_by_group={
            group: len({row["source_cluster"] for row in registry if row["group"] == group})
            for group in statistics.GROUPS
        },
        all_generation_before_private_scoring=True,
        B_final_development_evaluations=0,
        A_auxiliary_confirmation=False,
        mechanism_ablation=False,
        no_candidate_selection_from_B_or_confirm=True,
        no_changes_to_C_N_loss_temperature_tasks_or_decoding=True,
        numeric_limits=parent["numeric_limits"],
        scientific_sources=sources,
        confirm_views=dict(
            output_directory=str(b.RAW / "confirm_views"),
            source_root=materials["private_scoring_source_root"],
            registry_path=confirm.REGISTRY,
            protocol_path=str(b.RAW / "protocol.json"),
            code_commit=head,
            code_sources=compiler_sources,
        ),
        statistical_contract=dict(
            primary="B Delayed-C minus B Static",
            groups=list(statistics.GROUPS),
            effect="equal mean over 3 groups; within group equal tasks, within task paired mean over 3 fixed training seeds",
            resampling="71 CIK clusters with common multiplicities across all arms/seeds/groups; weighted within-group denominators",
            replicates=statistics.BOOTSTRAP_REPLICATES,
            maximum_draws=statistics.BOOTSTRAP_MAX_DRAWS,
            random_seed=statistics.BOOTSTRAP_RANDOM_SEED,
            interval="95% percentile, exact rational linear interpolation (n-1)p",
            empty_group="reject draw independent of outcome and count it; hard maximum draws; otherwise INCOMPLETE",
            positive_rule="exact lower endpoint > 0",
            crosses_zero="not confirmed; not equivalence; no extra data or seeds",
            training_randomness_covered=False,
        ),
        effective_budget=dict(
            final_models=6,
            model_updates_each=400,
            model_updates_total=2400,
            shared_prefix_updates=600,
            tail_updates=1200,
            physical_updates_base=1800,
            feedback_sessions=1080,
            confirmation_sessions=4320,
            new_sessions=5400,
            committed_generate_call_cap=172800,
            B_final_dev_sessions=0,
            A_auxiliary_sessions=0,
            physical_SFT_sequence_tokens_base=801526230,
            physical_SFT_target_tokens_base=44193960,
            effective_model_sequence_tokens=1068701640,
            effective_model_target_tokens=58925280,
            required_population_passes=3,
            required_population_sequence_tokens=53435082,
        ),
        physical_budget=dict(
            optimizer_cap=1980,
            population_cap=6,
            feedback_response_cap=34944,
            extra_replayed_responses_per_seed=128,
            generate_call_cap=190080,
            incomplete_generate_call_cap=17280,
            score_case_cap=6480,
            worker_start_cap=512,
            maximum_attempts_per_job=8,
            registered_single_call_output_cap=2048,
            all_partial_attempts_charged_before_work=True,
            SFT_partial_attempts_count_towards_optimizer_cap=True,
        ),
        resources=dict(
            own_capacity_MiB=b.FLOORS,
            cold_start_extra_MiB=1024,
            maximum_parallel_GPU_workers=8,
            maximum_parallel_population_workers=1,
            maximum_parallel_replay_workers=1,
            CPU_score_workers=12,
            host_free_for_SFT_bytes=64 * 2**30,
            host_free_for_outer_bytes=128 * 2**30,
            resource_only_retry=True,
            numerical_material_or_score_identity_errors="STOP_REQUIRES_REVIEW",
            state_storage=str(b.RAW),
            final_32GiB_not_universally_admitted=True,
            boot_service_installed=False,
        ),
        implementation_admission="only stages with a committed implementation manifest may run; no automatic start by protocol creation",
        at=p.now(),
    )
    b.RAW.mkdir(parents=True, exist_ok=True)
    b.durable.atomic_bytes(b.RAW / "audit_directive.txt", AUDIT.read_bytes(), immutable=True)
    b.write(b.RAW / "protocol.json", plan)
    b.write(
        b.RAW / "public_registration.json",
        p.record(
            "B_confirm_public_registration",
            protocol_id=plan["id"],
            code_commit=head,
            audit_sha256=plan["audit_attachment_sha256"],
            candidate=plan["candidate"],
            baseline=plan["baseline"],
            seeds=plan["seeds"],
            effective_budget=plan["effective_budget"],
            physical_budget=plan["physical_budget"],
            statistical_contract=plan["statistical_contract"],
            confirm_registry_sha256=plan["confirm_registry_sha256"],
            confirm_CIK_count=plan["confirm_CIK_count"],
            no_confirm_contents_or_scores_opened_before_registration=True,
            at=p.now(),
        ),
    )
    b.emit(
        dict(
            event="B_scientific_protocol_frozen",
            id=plan["id"],
            code_commit=head,
            confirm_CIKs=plan["confirm_CIK_count"],
            budget=plan["effective_budget"],
        )
    )
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    prepare(args.root)
