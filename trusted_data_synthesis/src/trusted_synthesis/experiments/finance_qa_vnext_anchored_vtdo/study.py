"""Evidence-bearing two-round CPU integration, not a live Qwen launcher.

The numerical modules can bind genuine torch parameters and optimizer states.
This orchestration entry deliberately admits CPU controls only: the user asked
for an isolated implementation branch, not the new 16,740-session experiment.
"""

import argparse
import copy
import math
from fractions import Fraction
from pathlib import Path

import torch

from . import (
    distribution,
    feedback,
    gradients,
    isolation,
    optimizer_pullback,
    state_catalog,
    state_materials,
)
from . import protocol as p


def comparison_plan():
    runs = []
    for pool in p.POOLS:
        conditions = p.CONDITIONS if pool == "A" else (p.CONDITIONS[0], p.CONDITIONS[2])
        for condition in conditions:
            for seed in p.SEEDS:
                adaptive = condition != p.CONDITIONS[0]
                runs.append(
                    {
                        "pool": pool,
                        "condition": condition,
                        "seed": seed,
                        "outer_rounds": 2 if adaptive else 0,
                        "feedback_sessions": 720 if adaptive else 0,
                        "final_dev_sessions": 180 if pool == "A" else 0,
                        "final_confirm_sessions": 0 if condition == p.CONDITIONS[1] else 720,
                    }
                )
    return p.record(
        "anchored_comparison_plan",
        algorithm_policy_id=p.policy()["id"],
        runs=runs,
        training_protocols=len(runs),
        feedback_sessions=sum(row["feedback_sessions"] for row in runs),
        final_greedy_sessions=sum(
            row["final_dev_sessions"] + row["final_confirm_sessions"] for row in runs
        ),
        total_local_Student_sessions=sum(
            row["feedback_sessions"] + row["final_dev_sessions"] + row["final_confirm_sessions"]
            for row in runs
        ),
        primary_condition=p.CONDITIONS[2],
        C_only_is_development_diagnostic=True,
        choose_between_C_only_and_full_using_results=False,
        B_runs_own_feedback=True,
        old_B_zero_development_contract_modified=False,
        baseline_reuse_credit=0,
        baseline_reuse_requires_exact_actual_identity=True,
        GPU_execution_authorized=False,
        actual_experiment_started=False,
    )


def _floats(distribution_by_task):
    return {
        task: {state: float(Fraction(str(value))) for state, value in states.items()}
        for task, states in distribution_by_task.items()
    }


def _tensor_payload(tensors):
    return {
        name: {
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "values": value.detach().cpu().tolist(),
        }
        for name, value in tensors.items()
    }


def _check_packages(packages, expected_package_ids, pi, *, pool):
    p.require(
        isinstance(packages, list)
        and [row["package_id"] for row in packages] == list(expected_package_ids),
        "round.exact_all_original_package_order",
    )
    p.require(
        len(set(expected_package_ids)) == len(expected_package_ids),
        "round.unique_original_packages",
    )
    p.require({row["task_id"] for row in packages} == set(pi), "round.full_task_denominator")
    for task, states in pi.items():
        p.require(
            {row["state_id"] for row in packages if row["task_id"] == task} == set(states),
            "round.full_original_state_support",
        )
    p.require(
        all(row["pool"] == pool and row.get("role", "train") == "train" for row in packages),
        "round.no_pool_or_heldout_substitution",
    )


def _cpu_model(model):
    p.require(isinstance(model, torch.nn.Module), "study.torch_CPU_model_required")
    parameters = {name: value for name, value in model.named_parameters() if value.requires_grad}
    p.require(
        parameters
        and all(value.device.type == "cpu" for value in model.parameters())
        and all(value.device.type == "cpu" for value in model.buffers()),
        "study.all_conditions_CPU_only",
    )
    return parameters


def _bound_population(catalog, manifest, prior, mu, controls, pool):
    state_catalog.validate_catalog(catalog, manifest)
    initial = _floats(state_materials.initial_distribution(catalog, pool=pool))
    p.require(_floats(prior) == initial, "study.prior_exact_original_alpha0_pushforward")
    rows = {row["task_id"]: row for row in catalog["task_support"] if row["pool"] == pool}
    p.require(
        set(mu) == set(rows)
        and all(
            math.isclose(float(Fraction(str(value))), 1 / len(rows), rel_tol=0, abs_tol=1e-12)
            for value in mu.values()
        ),
        "study.unchanged_uniform_task_marginal",
    )
    p.require(
        set(controls) == {task for task, row in rows.items() if row["group"] == "control"},
        "study.original_control_set",
    )
    return initial


def _authenticated_packages(packages, expected_ids, pi, *, pool, catalog, manifest):
    state_catalog.validate_catalog(catalog, manifest)
    state_materials.validate_distribution(catalog, pi, pool=pool)
    originals = {
        row["package_id"]: row
        for row in catalog["package_mappings"]
        if row["pool"] == pool and row["role"] == "train"
    }
    p.require(set(expected_ids) == set(originals), "round.no_missing_original_training_package")
    _check_packages(packages, expected_ids, pi, pool=pool)
    for package in packages:
        original = originals[package["package_id"]]
        p.require(
            original["status"] == "MAPPED"
            and all(
                package[key] == original[key]
                for key in ("task_id", "pool", "actual_method", "state_id")
            )
            and p.sha(p.encode(package["rows"])) == original["original_rows_sha256"],
            "round.authenticated_original_rows_and_semantic_state",
        )
        p.require(
            package["whole_package_target_tokens"]
            == sum(gradients.validate_row(row)["target_token_count"] for row in package["rows"]),
            "round.authenticated_original_token_denominator",
        )


def compute_round_cpu(
    model,
    optimizer,
    packages,
    *,
    expected_package_ids,
    pool,
    condition,
    training_seed,
    outer_round,
    pi,
    prior,
    mu,
    control_tasks,
    catalog,
    manifest,
    dev_tasks,
    decoder_policy,
    probe_collector,
    probe_qualifier,
):
    """Compute C/N/Phi/pi from the current torch point and all fixed probes.

    No caller-supplied C or gradient replaces actual log-probability backprop.
    Probe collection completes before the offline qualifier callback is invoked.
    The callbacks in this entry are synthetic CPU controls, not a privacy sandbox.
    """
    p.require(
        condition in p.CONDITIONS[1:]
        and pool in p.POOLS
        and training_seed in p.SEEDS
        and outer_round in (0, 1),
        "round.registered_algorithm_slot",
    )
    parameters = _cpu_model(model)
    _bound_population(catalog, manifest, prior, mu, control_tasks, pool)
    probabilities, prior = _floats(pi), _floats(prior)
    mass = {task: float(Fraction(str(value))) for task, value in mu.items()}
    _authenticated_packages(
        packages, expected_package_ids, probabilities, pool=pool, catalog=catalog, manifest=manifest
    )
    bound = optimizer_pullback.bind_adamw(parameters.items(), optimizer, clip_max_norm=1.0)
    class_result = gradients.class_gradients(model, packages)
    G = optimizer_pullback.aggregate_gradient(class_result["gradients"], probabilities, mass)
    virtual_step = optimizer_pullback.virtual_step(bound, G)
    virtual = gradients.FunctionalStudent(model, virtual_step["theta_bar"])
    virtual_identity = feedback.bind_virtual_model(
        virtual,
        base_identity={
            "model_parameter_digest": class_result["artifact"]["model_parameter_digest"],
            "model_buffer_digest": class_result["artifact"]["model_buffer_digest"],
            "scope": "synthetic CPU model, not a Qwen base identity",
        },
        virtual_step_id=virtual_step["diagnostics"]["id"],
    )
    registry = feedback.register_probes(
        dev_tasks, pool=pool, training_seed=training_seed, outer_round=outer_round
    )
    collector_arguments = copy.deepcopy((registry, virtual_identity, decoder_policy))
    collector_argument_hash = p.sha(p.encode(collector_arguments))
    probes = probe_collector(virtual, *collector_arguments)
    p.require(
        p.sha(p.encode(collector_arguments)) == collector_argument_hash,
        "round.collector_must_not_change_frozen_probe_inputs",
    )
    rewards = feedback.qualify_probes(
        probes,
        probe_qualifier,
        registry=registry,
        virtual_identity=virtual_identity,
        policy=decoder_policy,
    )
    derivative = feedback.reward_gradient(
        virtual,
        probes,
        rewards,
        virtual_identity=virtual_identity,
        registry=registry,
        policy=decoder_policy,
    )
    pulled = optimizer_pullback.pullback(
        bound, G, {name: -value for name, value in derivative["gradient"].items()}
    )
    contribution = optimizer_pullback.centered_contributions(
        class_result["gradients"], probabilities, mass, pulled["a"]
    )
    updated = distribution.anchored_update(
        probabilities,
        prior,
        contribution["C"],
        mass,
        control_tasks=control_tasks,
        contribution_only=condition == p.CONDITIONS[1],
    )
    virtual.assert_original_unchanged()
    # Full tensor values here are deliberate small-control artifacts. Production
    # sharded tensor persistence and resource admission are not implied by this.
    tensor_evidence = {
        "theta": _tensor_payload({row.name: row.theta for row in bound.parameters}),
        "Adam_m": _tensor_payload({row.name: row.first for row in bound.parameters}),
        "Adam_v": _tensor_payload({row.name: row.second for row in bound.parameters}),
        "Adam_steps": {row.name: row.step for row in bound.parameters},
        "class_gradients": {
            task: {state: _tensor_payload(value) for state, value in states.items()}
            for task, states in class_result["gradients"].items()
        },
        "aggregate_G": _tensor_payload(G),
        "theta_bar": _tensor_payload(virtual_step["theta_bar"]),
        "reward_gradient": _tensor_payload(derivative["gradient"]),
        "pulled_covector": _tensor_payload(pulled["a"]),
    }
    artifact = p.record(
        "RoundArtifact",
        execution_kind="synthetic_cpu_control",
        actual_financial_VTDO_round=False,
        pool=pool,
        condition=condition,
        training_seed=training_seed,
        outer_round=outer_round,
        epoch_boundary=p.OUTER_EPOCHS[outer_round],
        algorithm_policy_id=p.policy()["id"],
        state_catalog_id=catalog["id"],
        material_manifest_id=manifest["id"],
        original_package_ids=list(expected_package_ids),
        optimizer_binding=bound.snapshot,
        class_gradient_evidence=class_result["artifact"],
        virtual_step=virtual_step["diagnostics"],
        virtual_identity=virtual_identity,
        probe_registry=registry,
        decoder_policy=decoder_policy,
        probe_originals=probes,
        probe_rewards=rewards,
        feedback_gradient_evidence=derivative["artifact"],
        optimizer_pullback=pulled["diagnostics"],
        centered_Contribution=contribution["diagnostics"],
        prior=prior,
        distribution_update=updated,
        tensor_evidence=tensor_evidence,
        work_accounting={
            "class_gradient_forward_backward_rows": class_result["artifact"][
                "forward_backward_rows"
            ],
            "class_gradient_target_tokens": class_result["artifact"]["target_tokens"],
            "class_gradient_sequence_tokens": class_result["artifact"]["sequence_tokens"],
            "registered_probe_sessions": 360,
            "probe_logprob_work": derivative["artifact"],
            "outside_ten_epoch_SFT_token_budget": True,
            "GPU_calls": 0,
        },
        real_model_or_optimizer_changed_by_virtual_feedback=False,
        probe_samples_added_to_SFT=0,
        production_adapter_validated=False,
        exact_multistep_greedy_utility_derivative=False,
    )
    return {"pi_next": copy.deepcopy(updated["pi_next"]), "artifact": artifact}


def run_two_round_cpu(
    model,
    optimizer,
    *,
    pool,
    condition,
    training_seed,
    prior,
    mu,
    control_tasks,
    catalog,
    manifest,
    package_loader,
    train_epoch,
    dev_tasks,
    decoder_policy,
    probe_collector,
    probe_qualifier,
    expected_package_ids,
):
    """Execute epoch 0/5 feedback and 5+5 real CPU training callback epochs.

    The production material consumer is separately validated. This integration
    seam explicitly cannot authorize a reduced real experiment or a GPU worker.
    """
    p.require(condition in p.CONDITIONS, "study.new_algorithm_condition_not_old_arm")
    p.require(
        pool in p.POOLS
        and training_seed in p.SEEDS
        and not (pool == "B" and condition == p.CONDITIONS[1]),
        "study.registered_pool_condition",
    )
    parameters = _cpu_model(model)
    _bound_population(catalog, manifest, prior, mu, control_tasks, pool)
    incoming = (
        prior,
        mu,
        control_tasks,
        catalog,
        manifest,
        dev_tasks,
        decoder_policy,
        expected_package_ids,
    )
    incoming_hash = p.sha(p.encode(incoming))
    fixed = copy.deepcopy(incoming)
    (
        prior,
        mu,
        control_tasks,
        catalog,
        manifest,
        dev_tasks,
        decoder_policy,
        expected_package_ids,
    ) = fixed
    fixed_hash = p.sha(p.encode(fixed))
    pi = _floats(prior)
    rounds = []
    training = []
    for epoch in range(10):
        p.require(
            p.sha(p.encode(incoming)) == incoming_hash and p.sha(p.encode(fixed)) == fixed_hash,
            "study.fixed_prior_kernel_or_protocol_changed",
        )
        loader_pi = copy.deepcopy(pi)
        loader_pi_hash = p.sha(p.encode(loader_pi))
        packages = copy.deepcopy(package_loader(loader_pi))
        p.require(p.sha(p.encode(loader_pi)) == loader_pi_hash, "study.loader_changed_distribution")
        _authenticated_packages(
            packages, expected_package_ids, pi, pool=pool, catalog=catalog, manifest=manifest
        )
        if epoch in p.OUTER_EPOCHS and condition != p.CONDITIONS[0]:
            result = compute_round_cpu(
                model,
                optimizer,
                packages,
                expected_package_ids=expected_package_ids,
                pool=pool,
                condition=condition,
                training_seed=training_seed,
                outer_round=p.OUTER_EPOCHS.index(epoch),
                pi=pi,
                prior=prior,
                mu=mu,
                control_tasks=control_tasks,
                catalog=catalog,
                manifest=manifest,
                dev_tasks=dev_tasks,
                decoder_policy=decoder_policy,
                probe_collector=probe_collector,
                probe_qualifier=probe_qualifier,
            )
            p.checked_record(result["artifact"], "RoundArtifact")
            pi = copy.deepcopy(result["pi_next"])
            rounds.append(copy.deepcopy(result["artifact"]))
        p.require(
            p.sha(p.encode(incoming)) == incoming_hash and p.sha(p.encode(fixed)) == fixed_hash,
            "study.fixed_prior_kernel_or_protocol_changed",
        )
        before = optimizer_pullback.bind_adamw(parameters.items(), optimizer, clip_max_norm=1.0)
        training_pi = copy.deepcopy(pi)
        training_pi_hash = p.sha(p.encode(training_pi))
        result = train_epoch(model, optimizer, training_pi, epoch + 1)
        p.require(
            p.sha(p.encode(training_pi)) == training_pi_hash,
            "study.training_callback_changed_distribution",
        )
        p.require(
            p.sha(p.encode(incoming)) == incoming_hash and p.sha(p.encode(fixed)) == fixed_hash,
            "study.fixed_prior_kernel_or_protocol_changed",
        )
        after = optimizer_pullback.bind_adamw(parameters.items(), optimizer, clip_max_norm=1.0)
        p.require(
            len(mu) % 5 == 0
            and all(
                new.step - old.step == len(mu) // 5
                for old, new in zip(before.parameters, after.parameters, strict=True)
            ),
            "study.actual_epoch_optimizer_steps_not_self_attestation",
        )
        p.require(
            isinstance(result, dict)
            and result.get("epoch") == epoch + 1
            and result.get("execution_kind") == "synthetic_cpu_control",
            "study.synthetic_epoch_evidence_required",
        )
        training.append(
            copy.deepcopy(
                {
                    **result,
                    "verified_optimizer_updates": len(mu) // 5,
                    "before_optimizer_binding_id": before.snapshot["id"],
                    "after_optimizer_binding_id": after.snapshot["id"],
                }
            )
        )
        for previous in rounds:
            p.checked_record(previous, "RoundArtifact")
    return p.record(
        "CPU_two_round_execution",
        condition=condition,
        pool=pool,
        training_seed=training_seed,
        algorithm_policy_id=p.policy()["id"],
        rounds=rounds,
        inner_epoch_records=training,
        outer_updates=len(rounds),
        inner_epochs=10,
        final_distribution=pi,
        final_parameter_digest=gradients.tensor_digest(dict(model.named_parameters())),
        actual_Qwen_or_financial_utility_run=False,
        CPU_control_only=True,
        final_model_is_epoch_10_not_score_selected=True,
        formal_population_or_token_budget_claimed=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("spec", "run"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.phase == "run":
        isolation.require_production_authorization()
    result = comparison_plan()
    if args.output:
        root = Path.cwd().resolve()
        target = isolation.new_output(root, args.output)
        p.write_once(target, result)
    print(p.encode(result).decode())


if __name__ == "__main__":
    main()
