"""Existing certified states, unequal original counts and a new zero-feedback rule.

No old DAG reclassification, raw package/token scan or probability clipping.
These are new-study adapters, not a switch enabling the old CPU-only launcher.
"""

# ruff: noqa: E501 -- fixed contracts and explicit provenance paths
import argparse
import copy
import json
import math
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import distribution as anchored
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    distribution as original,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

PARENT = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/parallel_tail_execution_20260914"
)
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/anchored_sources_20260916"


def prior_from_headers(headers):
    counts = Counter((r["task_id"], r["state_id"]) for r in headers)
    methods = Counter((r["task_id"], r["method"]) for r in headers)
    membership = {}
    for row in headers:
        key = (row["task_id"], row["state_id"])
        p.require(
            membership.get(key, row["method"]) == row["method"],
            "anchored_sources.state_cannot_mix_methods",
        )
        membership[key] = row["method"]
    prior = defaultdict(dict)
    for (task, state), count in counts.items():
        method = membership[task, state]
        prior[task][state] = str(
            Fraction(count, methods[task, method]) * (1 if method == "control" else Fraction(1, 2))
        )
    p.require(
        all(sum(Fraction(x) for x in states.values()) == 1 for states in prior.values()),
        "anchored_sources.complete_original_method_support",
    )
    return dict(prior), counts, methods


def target_coefficient(probability, n_state, length):
    p.require(n_state > 0 and length > 0, "anchored_sources.original_count_and_length")
    return Fraction(str(probability)) / (5 * n_state * length)


def update_distribution(
    pi, prior, C, mu, rewards, *, control_tasks=(), condition, registered_complete
):
    p.require(condition in {"c_only_anchored", "full_anchored_vtdo"}, "anchored_sources.condition")
    p.require(
        registered_complete is True
        and len(rewards) == 360
        and all(type(x) is int and x in (0, 1) for x in rewards),
        "anchored_sources.complete_fixed360_feedback",
    )
    if not any(rewards):
        zero = {task: dict.fromkeys(states, 0.0) for task, states in pi.items()}
        anchored._inputs(pi, prior, zero, mu, set(control_tasks))
        novelty = {
            task: {
                state: max(
                    0.0,
                    math.log(float(Fraction(str(prior[task][state]))))
                    - math.log(float(Fraction(str(value)))),
                )
                for state, value in states.items()
            }
            for task, states in pi.items()
        }
        return p.record(
            "anchored_sources_distribution_step",
            status="UNINFORMATIVE_FEEDBACK",
            condition=condition,
            pi_next=copy.deepcopy(pi),
            prior_unchanged=True,
            pi_exactly_unchanged=True,
            novelty=novelty,
            novelty_active=any(x > 0 for states in novelty.values() for x in states.values()),
            theoretical_Contribution_zero=False,
            NLL_substituted_for_Contribution=False,
            additional_feedback_calls=0,
            continue_fixed_inner_schedule=True,
        )
    p.require(C is not None, "anchored_sources.real_feedback_Contribution_required")
    update = anchored.anchored_update(
        pi,
        prior,
        C,
        mu,
        control_tasks=control_tasks,
        contribution_only=condition == "c_only_anchored",
    )
    return p.record(
        "anchored_sources_distribution_step",
        status="FEEDBACK_UPDATE_COMPUTED",
        condition=condition,
        pi_next=update["pi_next"],
        numeric_core_update=update,
        novelty_active=any(
            value > 0 for row in update["task_diagnostics"].values() for value in row["N"].values()
        ),
        empirical_one_step_proxy_not_final_greedy_derivative=True,
        additional_feedback_calls=0,
    )


def prepare(root):
    root = Path(root).resolve()
    out = root / OUTPUT / "material_binding"
    p.require(not out.exists(), "anchored_sources.one_metadata_binding")
    frozen = p.read_json(root / PARENT / "preparation/execution_freeze.json")
    cache_root = root / frozen["trajectory_cache"]["cache_root"]
    manifest = p.read_json(cache_root / "manifest.json")
    p.require(
        manifest["id"] == frozen["trajectory_cache"]["manifest_id"],
        "anchored_sources.original_trajectory_cache",
    )
    pools = {}
    for pool in ("A", "B"):
        ref = manifest["pools"][pool]["package_index"]
        raw = (cache_root / ref["path"]).read_bytes()
        p.require(
            len(raw) == ref["bytes"] and p.sha(raw) == ref["sha256"],
            "anchored_sources.bound_headers_only",
        )
        index = json.loads(raw)
        headers = index["packages"]
        p.require(
            all(r["pool"] == pool and r["role"] == "train" for r in headers)
            and len({r["package_id"] for r in headers}) == len(headers),
            "anchored_sources.unique_original_train_packages",
        )
        prior, counts, methods = prior_from_headers(headers)
        p.require(len(prior) == 200, "anchored_sources.uniform200_tasks")
        controls = sorted({r["task_id"] for r in headers if r["method"] == "control"})
        p.require(len(controls) == 80, "anchored_sources.original80_controls")
        mappings = []
        for row in headers:
            task, state, method = row["task_id"], row["state_id"], row["method"]
            coefficient = target_coefficient(
                prior[task][state], counts[task, state], row["whole_package_target_tokens"]
            )
            original_coefficient = (Fraction(1) if method == "control" else Fraction(1, 2)) / (
                5 * methods[task, method] * row["whole_package_target_tokens"]
            )
            p.require(
                coefficient == original_coefficient,
                "anchored_sources.exact_old_alpha0_package_mass",
            )
            mappings.append(
                {
                    key: row[key]
                    for key in (
                        "package_id",
                        "task_id",
                        "state_id",
                        "method",
                        "session_id",
                        "whole_package_target_tokens",
                        "original_package_sha256",
                    )
                }
                | dict(
                    pi0=prior[task][state],
                    n_state=counts[task, state],
                    n_method=methods[task, method],
                    original_alpha0_coefficient=str(coefficient),
                    state_mapping="identity_on_current_certified_executed_complete_state",
                )
            )
        binding = p.record(
            "anchored_sources_material_binding",
            pool=pool,
            cache_id=manifest["id"],
            package_index_id=index["id"],
            state_mapper="existing_fixed_kernel_executed_history_with_explicit_rejections_and_side_calculations.v1",
            changed_mapper=False,
            old_independent_DAG_mapper_not_applied=True,
            prior=prior,
            mu={task: "1/200" for task in prior},
            control_tasks=controls,
            package_mappings=mappings,
            training_packages=len(headers),
            states=sum(len(x) for x in prior.values()),
            all_original_packages_retained=True,
            package_order_sha256=p.sha(p.encode([r["package_id"] for r in headers])),
            numeric_token_arrays_read=0,
            original_raw_packages_read=0,
            sealed_packages_reclassified=False,
            input_cache_budget=manifest["pools"][pool]["actual_budget"],
            old64_package_gate_reused=False,
        )
        p.write_once(out / (pool + ".json"), binding)
        pools[pool] = binding
    old_distribution = p.read_json(root / PARENT / "training/A_alpha0_11/distribution.json")
    old_prior = defaultdict(dict)
    for row in old_distribution["states"]:
        old_prior[row["task_id"]][row["state_id"]] = str(original.fraction(row["pi"]))
    p.require(
        dict(old_prior) == pools["A"]["prior"], "anchored_sources.actual_saved_alpha0_distribution"
    )
    given_plan = p.read_json(
        root
        / "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/given_sources_value_20260915/plan.json"
    )
    given_report = p.read_json(
        root
        / "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/given_sources_value_20260915/report.json"
    )
    identities = {row["key"]: row["original_model_identity"] for row in given_plan["models"]}
    scores = {row["model_key"]: row for row in given_report["models"]}
    reuse = []
    for seed in (11, 29, 47):
        name = f"A_alpha0_{seed}"
        directory = root / PARENT / "training" / name
        report = p.read_json(directory / "report.json")
        schedule = p.read_json(directory / "schedule.json")
        identity = p.read_json(directory / "identity.json")
        config = p.read_json(directory / "configuration.json")
        p.require(
            report["actual_complete"]
            and report["optimizer_updates"] == 400
            and report["epochs_completed"] == 10
            and report["execution_design"] == "trajectory_prefix_union_v1"
            and report["execution_mode"] == "local_CUDA"
            and report["training_configuration_id"]
            == config["id"]
            == frozen["training_configuration"]["id"]
            and report["trajectory_cache_id"] == manifest["id"]
            and report["actual_budget"] == pools["A"]["input_cache_budget"]
            and report["schedule_id"] == identity["schedule_id"] == schedule["id"]
            and len(schedule["batches"]) == 400
            and report["checkpoint_id"]
            == identities[name]["checkpoint_id"]
            == scores[name]["checkpoint_id"],
            "anchored_sources.static_actual_material_schedule_config_checkpoint_match",
        )
        counts = Counter(task for batch in schedule["batches"] for task in batch["task_ids"])
        p.require(
            set(counts) == set(pools["A"]["prior"]) and set(counts.values()) == {10},
            "anchored_sources.original_ten_visits",
        )
        reuse.append(
            dict(
                model=name,
                training_report_id=report["id"],
                schedule_id=schedule["id"],
                initial_adapter_digest=identity["initial_adapter_digest"],
                checkpoint_id=report["checkpoint_id"],
                existing_assessment_report_id=scores[name]["assessment_report_id"],
                static_training_configuration_id=config["id"],
                reuse_scope="unchanged single-GPU Static alpha0 only",
                new_adaptive_training_not_credited=True,
            )
        )
    report = p.record(
        "anchored_sources_material_admission",
        status="PASS_CURRENT_STATES_AND_STATIC_REUSE_AS_SCOPED",
        pools={
            pool: dict(
                binding_id=value["id"],
                training_packages=value["training_packages"],
                states=value["states"],
            )
            for pool, value in pools.items()
        },
        total_train_packages=sum(x["training_packages"] for x in pools.values()),
        existing_sealed2342_role_unchanged=True,
        current_mapper_unchanged=True,
        numeric_arrays_or_masks_rechecked=False,
        static_reuse=reuse,
        static_reused_training_runs=3,
        static_reused_dev_sessions=540,
        reuse_requires_new_Static_spec_to_keep_these_exact_config_and_schedule_ids=True,
        existing_given_sources_view_manifest_id=given_plan["source_view_manifest_id"],
        actual_adaptive_training_runs=0,
        actual_adaptive_feedback_sessions=0,
        full_production_adapter_admitted=False,
        B_or_confirmation_authorized=False,
        at=p.now(),
    )
    p.write_once(out / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    r = prepare(parser.parse_args().root)
    print(json.dumps({k: r[k] for k in ("id", "status", "pools", "static_reused_training_runs")}))
