"""Read-only admission of exact B step240 reuse and equal-TV reflection.

No training, feedback generation, financial scoring or GPU initialization occurs.
Reuse credit exists only if the complete admission returns successfully. The
reflection is specific to this saved current=prior, C-only dual-KL update; it is
not a claim about arbitrary VTDO updates or equality of forward/reverse KL.
"""

import math
import random
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import fixed_kernel_B_common_20260922 as b
import fixed_kernel_B_materials_20260922 as materials
import numpy as np
import torch

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.distribution import _scalar
from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.protocol import checked_record

p = b.p
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_direction_calibration_materials_20260926.py"
SEEDS = (11, 29, 47)
NUMERIC_ATOL = 1e-12
RATIO_UPPER = 19**0.16
RATIO_LOWER = 1 / RATIO_UPPER
REVERSE_RATIO_LOWER = 2 - RATIO_UPPER
REVISION = "revisions/control_guard_20260924"
ORIGINAL_PROTOCOL_ID = (
    "B_confirm_protocol:0dba5b5625fbf37d7e4f93fc0b7636cba1df66a1fec611e6af67d6a5710bbe1a"
)


def _close(first, second):
    return math.isclose(first, second, rel_tol=0, abs_tol=NUMERIC_ATOL)


def _ref(path, **extra):
    path = Path(path)
    return dict(path=str(path), sha256=p.sha(path), bytes=path.stat().st_size, **extra)


def reflect(binding, updated):
    """Return unchanged q0/qplus and unmodified floating qminus=2r-qplus."""
    p.checked(updated, "anchored_sources_distribution_step")
    core = checked_record(updated["numeric_core_update"], "anchored_distribution_update")
    expected = dict(
        epsilon=0.05,
        contribution_exponent=0.8,
        effective_novelty_exponent=0.0,
        contribution_only=True,
        lambda_current=4.0,
        lambda_prior=1.0,
        prior_is_fixed_pi0=True,
        controls_exactly_preserved=True,
        probability_clipping_or_repair=False,
    )
    p.require(all(core[key] == value for key, value in expected.items()), "calibration.formula")
    p.require(updated["pi_next"] == core["pi_next"], "calibration.saved_numeric_core_pi")
    prior = binding["prior"]
    plus = updated["pi_next"]
    controls = set(binding["control_tasks"])
    p.require(
        set(prior) == set(plus) == set(binding["mu"]) == set(core["task_diagnostics"])
        and controls == set(core["control_tasks"]),
        "calibration.same_task_support",
    )
    q0, qplus, qminus, diagnostics = {}, {}, {}, {}
    all_plus_ratios, all_minus_ratios = [], []
    for task in sorted(prior):
        q0[task] = {state: _scalar(value) for state, value in prior[task].items()}
        p.require(set(q0[task]) == set(plus[task]), "calibration.same_state_support")
        qplus[task] = {state: _scalar(value) for state, value in plus[task].items()}
        original = core["task_diagnostics"][task]
        p.require(
            original["pi_current"] == original["r_pi0"] == q0[task]
            and original["pi_next"] == qplus[task]
            and original["optimized"] is (task not in controls),
            "calibration.current_equals_original_prior",
        )
        qminus[task] = {state: 2 * r - qplus[task][state] for state, r in q0[task].items()}
        for values in (q0[task], qplus[task], qminus[task]):
            p.require(
                all(math.isfinite(value) and value > 0 for value in values.values())
                and _close(math.fsum(values.values()), 1),
                "calibration.positive_simplex_no_repair",
            )
        if task in controls:
            p.require(q0[task] == qplus[task] == qminus[task], "calibration.exact_controls")
        ratios = [qplus[task][state] / r for state, r in q0[task].items()]
        reversed_ratios = [qminus[task][state] / r for state, r in q0[task].items()]
        p.require(
            all(RATIO_LOWER - NUMERIC_ATOL <= x <= RATIO_UPPER + NUMERIC_ATOL for x in ratios)
            and min(reversed_ratios) >= REVERSE_RATIO_LOWER - NUMERIC_ATOL,
            "calibration.saved_ratios_within_formula_bound",
        )
        all_plus_ratios.extend(ratios)
        all_minus_ratios.extend(reversed_ratios)
        row = {}
        for name, values in (("plus", qplus[task]), ("minus", qminus[task])):
            row["TV_" + name] = 0.5 * math.fsum(
                abs(values[state] - r) for state, r in q0[task].items()
            )
            row["KL_" + name + "_to_prior"] = math.fsum(
                value * (math.log(value) - math.log(q0[task][state]))
                for state, value in values.items()
            )
        p.require(_close(row["TV_plus"], row["TV_minus"]), "calibration.task_equal_TV")
        diagnostics[task] = row
    mu = {task: _scalar(value) for task, value in binding["mu"].items()}
    p.require(
        all(value > 0 for value in mu.values()) and _close(math.fsum(mu.values()), 1),
        "calibration.unchanged_positive_task_marginal",
    )
    global_diagnostics = {
        field: math.fsum(mu[task] * row[field] for task, row in diagnostics.items())
        for field in next(iter(diagnostics.values()))
    }
    p.require(
        _close(global_diagnostics["TV_plus"], global_diagnostics["TV_minus"]),
        "calibration.global_equal_TV",
    )
    return p.record(
        "direction_calibration_reflection",
        original_distribution_update_id=updated["id"],
        numeric_core_update_id=core["id"],
        binding_id=binding["id"],
        distributions={"static": q0, "positive": qplus, "negative": qminus},
        distribution_sha256={
            name: p.sha(p.encode(value))
            for name, value in (("static", q0), ("positive", qplus), ("negative", qminus))
        },
        task_marginal=binding["mu"],
        controls=binding["control_tasks"],
        numerical_absolute_tolerance=NUMERIC_ATOL,
        numerical_relative_tolerance=0,
        probability_clipping_or_repair=False,
        KL_symmetry_claimed=False,
        theoretical_ratio_bounds=dict(
            positive_lower=RATIO_LOWER,
            positive_upper=RATIO_UPPER,
            negative_lower=REVERSE_RATIO_LOWER,
            negative_upper=2 - RATIO_LOWER,
            only_saved_current_equals_prior_C_only_formula=True,
        ),
        actual_ratio_bounds=dict(
            positive_lower=min(all_plus_ratios),
            positive_upper=max(all_plus_ratios),
            negative_lower=min(all_minus_ratios),
            negative_upper=max(all_minus_ratios),
        ),
        per_task=diagnostics,
        global_diagnostics=global_diagnostics,
    )


def _rng_binding(rng, step):
    p.require(
        set(rng) == {"cpu", "cuda", "python", "numpy", "schedule_cursor"}, "calibration.RNG_fields"
    )
    p.require(rng["schedule_cursor"] == step and len(rng["cuda"]) == 1, "calibration.RNG_cursor")
    tensors = [rng["cpu"], *rng["cuda"]]
    p.require(
        all(
            x.device.type == "cpu" and x.dtype == torch.uint8 and x.ndim == 1 and x.numel() > 0
            for x in tensors
        ),
        "calibration.CPU_saved_RNG_tensors",
    )
    torch.Generator(device="cpu").set_state(rng["cpu"])
    random.Random().setstate(rng["python"])
    np.random.RandomState().set_state(rng["numpy"])
    numpy_state = rng["numpy"]
    return p.record(
        "direction_calibration_RNG_binding",
        schedule_cursor=step,
        cpu_sha256=p.sha(rng["cpu"].numpy().tobytes()),
        cuda_sha256=[p.sha(x.numpy().tobytes()) for x in rng["cuda"]],
        python_sha256=p.sha(p.encode(rng["python"])),
        numpy_sha256=p.sha(p.encode([numpy_state[0], numpy_state[1].tolist(), *numpy_state[2:]])),
    )


def _checkpoint(raw, plan, key, step):
    path = raw / "jobs" / key / "updates" / f"{step:04d}.pt"
    saved = b.load_training(path, plan["id"], [key], step=step)
    snapshot = checked_record(saved["snapshot"], "optimizer_binding")
    report = p.checked(saved["update_report"], "optimizer_update")
    p.require(
        report == p.read_json(path.with_suffix(".json")),
        "calibration.checkpoint_embedded_update_identity",
    )
    rng = _rng_binding(saved["rng"], step)
    reference = _ref(
        path,
        job_key=key,
        step=step,
        snapshot_id=snapshot["id"],
        update_report_id=report["id"],
        RNG_binding=rng,
        parameters_Adam_and_RNG_verified=True,
    )
    del saved
    return reference, snapshot


def _history(raw, plan, seed, condition, expected_packages, job_report):
    key = f"B_{condition}_{seed}"
    by_task = {}
    for index, row in enumerate(expected_packages):
        by_task.setdefault(row["task_id"], []).append((index, row))
    visits, ids = Counter(), []
    for step in range(201, 241):
        report = p.checked(
            p.read_json(raw / "jobs" / key / "updates" / f"{step:04d}.json"), "optimizer_update"
        )
        batch = plan["materials"]["schedules"][str(seed)]["batches"][step - 1]
        expected = [
            row for _, row in sorted(pair for task in batch["task_ids"] for pair in by_task[task])
        ]
        p.require(
            report["id"] == job_report["update_report_ids"][step - 1]
            and report["pool"] == "B"
            and report["arm"] == condition
            and report["cache_id"] == plan["materials"]["trajectory_cache"]["manifest_id"]
            and report["tasks"]
            == [
                dict(task_id=task, group=plan["materials"]["training_groups"][task])
                for task in batch["task_ids"]
            ]
            and report["packages"] == expected,
            "calibration.original_schedule_packages_and_exact_coefficients",
        )
        p.require(
            report["optimizer_step_calls"] == report["clip_calls"] == report["zero_grad_calls"] == 1
            and report["additional_loss_scaling"] is False
            and report["loss_rule"] == "pi(state|task)/(5*n_state*whole_package_target_tokens)"
            and report["execution_design"] == "trajectory_prefix_union_v1",
            "calibration.original_inner_update_rule",
        )
        visits.update(row["package_id"] for row in report["packages"])
        ids.append(report["id"])
    p.require(
        visits == Counter(dict.fromkeys((row["package_id"] for row in expected_packages), 1)),
        "calibration.full_original_epoch",
    )
    return dict(updates=40, update_report_ids=ids, update_report_ids_sha256=p.sha(p.encode(ids)))


def _completed_plan(root, raw):
    plan = p.checked(p.read_json(raw / "protocol.json"), "B_confirm_protocol")
    p.require(
        plan["id"] == ORIGINAL_PROTOCOL_ID
        and plan["frozen"] is True
        and plan["seeds"] == list(SEEDS)
        and plan["pool"] == "B",
        "calibration.original_B_protocol",
    )
    completion = p.checked(p.read_json(raw / "complete.json"), "B_confirm_completed_study")
    p.require(
        completion == p.read_json(raw / "report.json")
        and completion["protocol_id"] == plan["id"]
        and completion["status"] == "COMPLETE_B_MAIN_CONFIRMATION"
        and completion["confirmation_sessions"] == 4320
        and {(row["seed"], row["condition"]) for row in completion["models"]}
        == {(seed, arm) for seed in SEEDS for arm in ("static", "delayed_c")}
        and len(completion["models"]) == 6,
        "calibration.original_B_completed",
    )
    revision = p.checked(
        p.read_json(raw / REVISION / "registration.json"), "B_control_guard_execution_revision"
    )
    implementation = p.checked(
        p.read_json(raw / "implementation.json"), "B_execution_implementation"
    )
    link = p.checked(
        p.read_json(raw / REVISION / "completion_link.json"),
        "B_control_guard_completed_report_link",
    )
    applied = p.checked(
        p.read_json(raw / REVISION / "resume_applied.json"), "B_control_guard_resume_applied"
    )
    p.require(
        revision["protocol_id"] == link["protocol_id"] == plan["id"]
        and revision["protocol_sha256"] == p.sha(raw / "protocol.json")
        and revision["original_implementation_id"] == implementation["id"]
        and implementation["protocol_id"] == plan["id"]
        and revision["original_implementation_sha256"] == p.sha(raw / "implementation.json")
        and link["revision_id"] == applied["revision_id"] == revision["id"]
        and link["scientific_report_id"] == completion["id"]
        and link["original_report_and_scientific_conclusions_not_modified"] is True
        and revision["physical_budget"] == plan["physical_budget"]
        and revision["effective_budget"] == plan["effective_budget"],
        "calibration.original_B_revision_and_completion_binding",
    )
    for sources in (plan["scientific_sources"], revision["new_sources"], implementation["sources"]):
        for name, digest in sources.items():
            p.require(p.sha(root / name) == digest, "calibration.original_frozen_source:" + name)
    failed = revision["failed_attempt"]
    p.require(
        p.sha(raw / failed["path"]) == failed["sha256"], "calibration.original_failure_preserved"
    )
    return plan, completion, revision


def admit(root, raw):
    """Admit all fixed seeds atomically; any discrepancy raises without reuse credit."""
    root, raw = Path(root).resolve(), Path(raw).resolve()
    plan, completion, revision = _completed_plan(root, raw)
    current = materials.load_B_materials(root)
    for field in (
        "binding",
        "trajectory_cache",
        "training_configuration",
        "schedules",
        "training_groups",
    ):
        p.require(
            current[field] == plan["materials"][field], "calibration.original_material:" + field
        )
    cache_root = root / current["trajectory_cache"]["cache_root"]
    manifest = p.read_json(cache_root / "manifest.json")
    package_index = materials._bound_json(cache_root, manifest["pools"]["B"]["package_index"])
    cache = SimpleNamespace(packages=package_index["packages"])
    distributions, references = {}, []
    for seed in SEEDS:
        prefix_key = f"B_prefix_{seed}"
        prefix, prefix_snapshot = _checkpoint(raw, plan, prefix_key, 200)
        prefix_report = p.checked(
            p.read_json(raw / "jobs" / prefix_key / "report.json"), "B_training_job_report"
        )
        p.require(
            prefix_report["plan_id"] == plan["id"]
            and prefix_report["complete"] is True
            and prefix_report["job_key"] == prefix_key
            and prefix_report["completed_updates"] == 200
            and prefix_report["condition"] == "prefix"
            and prefix_report["seed"] == seed
            and prefix_report["pool"] == "B"
            and prefix_report["checkpoint_path"] == prefix["path"]
            and prefix_report["checkpoint_sha256"] == prefix["sha256"]
            and prefix_report["snapshot_id"] == prefix["snapshot_id"]
            and prefix_report["rng_complete"] is True,
            "calibration.complete_exact_prefix200",
        )
        references.append(prefix)
        outer = raw / "outer" / f"B_delayed_c_{seed}"
        outer_report = p.checked(p.read_json(outer / "report.json"), "B_completed_outer")
        updated = p.checked(
            p.read_json(outer / "distribution_update.json"), "anchored_sources_distribution_step"
        )
        p.require(
            outer_report["plan_id"] == plan["id"]
            and outer_report["job_key"] == f"B_delayed_c_{seed}"
            and outer_report["prefix_checkpoint_sha256"] == prefix["sha256"]
            and outer_report["prefix_snapshot_id"] == prefix["snapshot_id"]
            and outer_report["distribution_update_id"] == updated["id"]
            and outer_report["numeric_guard_passed"] is True,
            "calibration.same_real_point_direction",
        )
        reflected = reflect(current["binding"], updated)
        distributions[str(seed)] = reflected
        for condition, direction in (("static", "static"), ("delayed_c", "positive")):
            key = f"B_{condition}_{seed}"
            report = p.checked(
                p.read_json(raw / "jobs" / key / "report.json"), "B_training_job_report"
            )
            branch = p.checked(
                p.read_json(raw / "jobs" / key / "branch_binding.json"),
                "B_shared_prefix_branch_binding",
            )
            bound = report["prefix_binding"]
            p.require(
                report["complete"] is True
                and report["completed_updates"] == 400
                and report["plan_id"] == branch["plan_id"] == plan["id"]
                and report["job_key"] == branch["job_key"] == key
                and report["seed"] == branch["seed"] == seed
                and report["condition"] == branch["condition"] == condition
                and report["pool"] == branch["pool"] == "B"
                and report["binding_id"] == current["binding"]["id"]
                and report["cache_id"] == current["trajectory_cache"]["manifest_id"]
                and all(branch[field] == value for field, value in bound.items())
                and bound["prefix_checkpoint_sha256"] == prefix["sha256"]
                and bound["prefix_snapshot_id"] == prefix["snapshot_id"]
                and bound["prefix_key"] == prefix_key
                and bound["prefix_checkpoint_path"] == prefix["path"]
                and bound["prefix_completed_updates"] == 200
                and bound["rng_complete"] is True
                and branch["starts_from_real_model_Adam_and_RNG"] is True
                and branch["virtual_point_used_for_SFT"] is False
                and report["update_report_ids"][:200] == prefix_report["update_report_ids"],
                "calibration.common_real_prefix_branch_binding",
            )
            # Preserve the original scalar representation when reproducing coefficients.
            pi = current["binding"]["prior"] if condition == "static" else updated["pi_next"]
            packages = b.old.examples_at_pi(cache, pi)
            history = _history(raw, plan, seed, condition, packages, report)
            checkpoint, snapshot = _checkpoint(raw, plan, key, 240)

            def parameter_layout(value):
                return [
                    (row["name"], row["parameter"]["shape"], row["parameter"]["dtype"])
                    for row in value["parameters"]
                ]

            p.require(
                snapshot["groups"] == prefix_snapshot["groups"]
                and snapshot["clip"] == prefix_snapshot["clip"]
                and parameter_layout(snapshot) == parameter_layout(prefix_snapshot)
                and checkpoint["update_report_id"] == history["update_report_ids"][-1],
                "calibration.original_optimizer_and_history",
            )
            checkpoint.update(
                seed=seed,
                condition=direction,
                prefix_sha256=prefix["sha256"],
                prefix_snapshot_id=prefix["snapshot_id"],
                prefix_RNG_binding_id=prefix["RNG_binding"]["id"],
                branch_binding_id=branch["id"],
                original_final_report_id=report["id"],
                distribution_sha256=reflected["distribution_sha256"][direction],
                history=history,
            )
            references.append(checkpoint)
    return p.record(
        "direction_calibration_material_admission",
        passed=True,
        original_protocol_id=plan["id"],
        original_completion_id=completion["id"],
        original_execution_revision_id=revision["id"],
        seeds=list(SEEDS),
        materials=current,
        distributions=distributions,
        reusable_refs=references,
        reuse_credit_before_full_admission=0,
        accounting=dict(
            reused_model_prefix_updates=9 * 200,
            reused_positive_and_static_tail_updates=6 * 40,
            reused_effective_model_updates=2040,
            new_negative_tail_updates=3 * 40,
            final_effective_model_updates=9 * 240,
            unique_historical_updates_referenced=3 * 200 + 6 * 40,
            newly_executed_updates_during_admission=0,
            additional_new_training_updates_if_admitted=120,
            full_no_reuse_short_tail_updates=360,
            newly_required_sequence_tokens=3 * materials.B_PER_EPOCH["sequence_tokens"],
            newly_required_target_tokens=3 * materials.B_PER_EPOCH["target_tokens"],
        ),
        checkpoints_CPU_loaded=9,
        GPU_calls=0,
        original_feedback_generated=0,
        population_files_read=0,
        trajectory_sessions_read=0,
        no_automatic_retraining_or_admission_relaxation=True,
    )
