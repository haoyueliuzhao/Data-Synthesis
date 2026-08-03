from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
import torch

from trusted_synthesis.experiments.vtdo_experiment.phase1_batch_distribution_intervention import (
    _contrast_weights,
    _recover_centered_state_values,
    _sylvester_hadamard,
    _symmetric_probabilities,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_authorization import (
    _assert_canonical_artifact,
    _distribution_evidence,
    _next_distribution,
    _robust_positive_scale,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    _attach_centered_signal,
    _gradient_alignment,
    _gradient_norm,
    _normalized_gradient_alignment,
    _selected_gradient_states,
    _validate_run_contract,
    _weighted_gradient,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_distribution_intervention import (
    _apply_gradient_step,
    _conditional_distribution_gradient,
    _gradient_artifact_map,
    _perturbed_distribution,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gp_abc_validation import (
    _adamw_descent_direction,
    _center,
    _distribution_contract_replay,
    _sgd_equivalence_audit,
    _vector_fidelity,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_linearization_diagnostic import (
    _parameter_step_fidelity,
)
from trusted_synthesis.hashing import canonical_hash


def test_authorization_artifact_replay_rejects_payload_tampering() -> None:
    payload = {"status": "passed", "value": 1}
    payload["artifact_hash"] = canonical_hash(payload, prefix="test_authorization_artifact:")
    _assert_canonical_artifact(
        payload,
        hash_field="artifact_hash",
        prefix="test_authorization_artifact:",
        artifact_name="test artifact",
    )

    payload["value"] = 2
    with pytest.raises(ValueError, match="canonical identity changed"):
        _assert_canonical_artifact(
            payload,
            hash_field="artifact_hash",
            prefix="test_authorization_artifact:",
            artifact_name="test artifact",
        )


def test_gradient_projection_sign_matches_one_step_objective_improvement() -> None:
    state_loss_gradient = {"weight": torch.tensor([2.0, 0.0])}
    validation_loss_gradient = {"weight": torch.tensor([4.0, 0.0])}
    opposite_gradient = {"weight": torch.tensor([-4.0, 0.0])}

    _, helpful_alignment, _, _ = _gradient_alignment(
        state_loss_gradient,
        validation_loss_gradient,
    )
    _, harmful_alignment, _, _ = _gradient_alignment(
        state_loss_gradient,
        opposite_gradient,
    )

    # SGD follows -grad(train loss). For J=-validation loss, the first-order
    # utility gain is proportional to <grad(train loss), grad(validation loss)>.
    assert helpful_alignment == pytest.approx(1.0)
    assert harmful_alignment == pytest.approx(-1.0)


def test_precomputed_norm_alignment_matches_full_alignment() -> None:
    left = {
        "a": torch.tensor([1.0, 2.0]),
        "b": torch.tensor([-3.0]),
    }
    right = {
        "a": torch.tensor([4.0, -1.0]),
        "b": torch.tensor([2.0]),
    }

    full_dot, full_cosine, left_norm, right_norm = _gradient_alignment(left, right)
    cached_dot, cached_cosine = _normalized_gradient_alignment(
        left,
        right,
        left_norm=_gradient_norm(left),
        right_norm=_gradient_norm(right),
    )

    assert (cached_dot, cached_cosine) == pytest.approx((full_dot, full_cosine))
    assert left_norm == pytest.approx(_gradient_norm(left))
    assert right_norm == pytest.approx(_gradient_norm(right))


def test_weighted_gradient_uses_normalized_positive_weights() -> None:
    gradients = [
        {"weight": torch.tensor([1.0, 3.0])},
        {"weight": torch.tensor([5.0, 7.0])},
    ]

    result = _weighted_gradient(gradients, [1.0, 3.0])

    assert torch.equal(result["weight"], torch.tensor([4.0, 6.0]))
    with pytest.raises(ValueError, match="positive weights"):
        _weighted_gradient(gradients, [1.0, 0.0])


def test_gradient_signal_is_centered_under_frozen_distribution() -> None:
    rows = [
        {
            "state_id": "a",
            "estimation_aggregate_alignment": 0.8,
            "estimation_record_alignments": [0.7, 0.8, 0.9, 0.8],
        },
        {
            "state_id": "b",
            "estimation_aggregate_alignment": 0.2,
            "estimation_record_alignments": [0.1, 0.2, 0.3, 0.2],
        },
    ]
    probabilities = {"a": 0.25, "b": 0.75}

    _attach_centered_signal(
        rows,
        split="estimation",
        penalty_coefficient=1.0,
        probabilities=probabilities,
    )

    for field in (
        "estimation_centered_contribution",
        "estimation_conservative_centered_contribution",
    ):
        weighted_mean = sum(probabilities[row["state_id"]] * float(row[field]) for row in rows)
        assert weighted_mean == pytest.approx(0.0, abs=1e-12)


def test_production_gradient_projection_contract_is_fail_closed() -> None:
    with pytest.raises(ValueError, match="at least 30 tasks"):
        _validate_run_contract(
            run_role="production_candidate",
            task_count=29,
            evaluation_record_count=8,
        )
    with pytest.raises(ValueError, match="at least eight evaluation records"):
        _validate_run_contract(
            run_role="smoke",
            task_count=3,
            evaluation_record_count=6,
        )


def test_gradient_projection_uses_task_adaptive_verified_state_support() -> None:
    def state(strategy: str, state_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            strategy=strategy,
            assignment=SimpleNamespace(state=SimpleNamespace(state_id=state_id)),
        )

    comparison_artifact = SimpleNamespace(
        accepted_states=(
            state("compact_direct", "compact"),
            state("broad_direct", "broad"),
            state("compact_verify_frontier", "verify"),
        )
    )

    selected = _selected_gradient_states(comparison_artifact)

    assert [item.strategy for item in selected] == [
        "compact_direct",
        "broad_direct",
        "compact_verify_frontier",
    ]
    with pytest.raises(ValueError, match="three independently verified states"):
        _selected_gradient_states(
            SimpleNamespace(
                accepted_states=(
                    state("compact_direct", "compact"),
                    state("broad_direct", "broad"),
                )
            )
        )


def test_conditional_distribution_perturbation_preserves_support_and_mass() -> None:
    probabilities = {"a": 0.2, "b": 0.3, "c": 0.5}

    perturbed = _perturbed_distribution(
        probabilities,
        target_state_id="b",
        epsilon=0.1,
    )

    assert set(perturbed) == set(probabilities)
    assert sum(perturbed.values()) == pytest.approx(1.0)
    assert perturbed == pytest.approx({"a": 0.18, "b": 0.37, "c": 0.45})
    with pytest.raises(ValueError, match="outside pi_t"):
        _perturbed_distribution(probabilities, target_state_id="missing", epsilon=0.1)


def test_full_distribution_gradient_keeps_task_marginal_fixed() -> None:
    global_gradient = {"weight": torch.tensor([10.0, 20.0])}
    task_gradient = {"weight": torch.tensor([2.0, 6.0])}
    state_gradient = {"weight": torch.tensor([6.0, 2.0])}

    result = _conditional_distribution_gradient(
        global_gradient,
        task_gradient,
        state_gradient,
        task_marginal=0.25,
        epsilon=0.2,
    )

    # g' = g + mu(x) * epsilon * (g_z - E_pi[g_z]).
    assert torch.equal(result["weight"], torch.tensor([10.2, 19.8]))
    assert math.isclose(0.25 * 0.2, 0.05)


def test_cached_gradient_step_rejects_parameter_space_mismatch() -> None:
    model = torch.nn.Linear(2, 1, bias=False)
    model.weight.data.copy_(torch.tensor([[1.0, 2.0]]))

    _apply_gradient_step(
        model,
        {"weight": torch.tensor([[0.5, -0.5]])},
        learning_rate=0.1,
    )

    assert torch.equal(model.weight.data, torch.tensor([[0.95, 2.05]]))
    with pytest.raises(ValueError, match="parameter space changed"):
        _apply_gradient_step(
            model,
            {"another_weight": torch.tensor([[0.5, -0.5]])},
            learning_rate=0.1,
        )


def test_gradient_artifact_identity_is_unique_and_nonempty() -> None:
    rows = [{"task_id": "task-a"}, {"task_id": "task-b"}]
    assert set(_gradient_artifact_map(rows, key="task_id")) == {"task-a", "task-b"}
    with pytest.raises(ValueError, match="duplicate"):
        _gradient_artifact_map([rows[0], rows[0]], key="task_id")
    with pytest.raises(ValueError, match="no frozen gradients"):
        _gradient_artifact_map([], key="task_id")


def test_parameter_step_fidelity_detects_representable_and_rounded_steps() -> None:
    initial = {"weight": torch.tensor([1.0, -2.0], dtype=torch.float32)}
    global_gradient = {"weight": torch.tensor([0.5, -0.25], dtype=torch.float32)}
    direction = {"weight": torch.tensor([2.0, -4.0], dtype=torch.float32)}
    learning_rate = 0.1
    baseline = {"weight": initial["weight"].clone()}
    baseline["weight"].add_(global_gradient["weight"], alpha=-learning_rate)

    representable = _parameter_step_fidelity(
        initial,
        baseline,
        global_gradient,
        direction,
        learning_rate=learning_rate,
        directional_scale=0.25,
    )

    assert representable["parameter_step_cosine"] == pytest.approx(1.0, abs=1e-6)
    assert representable["parameter_step_norm_ratio"] == pytest.approx(1.0, rel=1e-5)
    assert representable["parameter_step_relative_error"] < 1e-5
    assert representable["parameter_step_nonzero_recovery"] == 1.0
    assert representable["parameter_step_energy_recovery"] == 1.0

    tiny_learning_rate = 1e-12
    tiny_baseline = {"weight": initial["weight"].clone()}
    tiny_baseline["weight"].add_(global_gradient["weight"], alpha=-tiny_learning_rate)
    rounded = _parameter_step_fidelity(
        initial,
        tiny_baseline,
        global_gradient,
        direction,
        learning_rate=tiny_learning_rate,
        directional_scale=1e-6,
    )

    assert rounded["actual_step_norm"] == 0.0
    assert rounded["parameter_step_cosine"] == 0.0
    assert rounded["parameter_step_nonzero_recovery"] == 0.0
    assert rounded["parameter_step_energy_recovery"] == 0.0
    with pytest.raises(ValueError, match="baseline replay mismatch"):
        _parameter_step_fidelity(
            initial,
            baseline,
            global_gradient,
            direction,
            learning_rate=tiny_learning_rate,
            directional_scale=1e-6,
        )


def test_batch_intervention_design_is_orthogonal_and_mass_preserving() -> None:
    hadamard = _sylvester_hadamard(64)

    assert len(hadamard) == 64
    assert all(len(row) == 64 for row in hadamard)
    for left in range(64):
        for right in range(64):
            dot = sum(hadamard[row][left] * hadamard[row][right] for row in range(64))
            assert dot == (64 if left == right else 0)

    weights = _contrast_weights(1, -1)
    plus, minus = _symmetric_probabilities(
        (1.0 / 3.0,) * 3,
        weights,
        epsilon=0.4,
    )
    assert sum(weights) == pytest.approx(0.0)
    assert sum(plus) == pytest.approx(1.0)
    assert sum(minus) == pytest.approx(1.0)
    assert min(plus + minus) > 0


def test_batch_intervention_recovers_centered_three_state_values() -> None:
    expected = (3.0, -1.0, -2.0)
    task_marginal = 0.2
    coordinate_a = task_marginal * 0.5 * (expected[0] - expected[1])
    coordinate_b = task_marginal * (0.25 * expected[0] + 0.25 * expected[1] - 0.5 * expected[2])

    recovered = _recover_centered_state_values(
        coordinate_a,
        coordinate_b,
        task_marginal=task_marginal,
    )

    assert recovered == pytest.approx(expected)


def test_gp_abc_estimators_are_centered_under_the_frozen_distribution() -> None:
    probabilities = [0.2, 0.3, 0.5]

    centered = _center([7.0, -2.0, 4.0], probabilities)

    assert sum(
        probability * value for probability, value in zip(probabilities, centered, strict=True)
    ) == pytest.approx(0.0, abs=1e-12)
    with pytest.raises(ValueError, match="support is incomplete"):
        _center([1.0], [0.5, 0.5])


def test_contribution_authorization_robust_scale_is_positive_and_estimation_only() -> None:
    scale = _robust_positive_scale(
        [-0.5, 0.0, 0.5, -1.0, 1.0],
        [-1.0, 0.0, 1.0, -2.0, 2.0],
    )

    assert scale == pytest.approx(2.0)
    with pytest.raises(ValueError, match="degenerate robust scale"):
        _robust_positive_scale([0.0, 0.0], [1.0, -1.0])


def test_contribution_authorization_distribution_is_exact_for_calibrated_proxy() -> None:
    grouped = {
        "task:a": [
            {
                "state_id": "a",
                "current_probability": 1.0 / 3.0,
                "proxy": -1.0,
                "target": -2.0,
            },
            {
                "state_id": "b",
                "current_probability": 1.0 / 3.0,
                "proxy": 0.0,
                "target": 0.0,
            },
            {
                "state_id": "c",
                "current_probability": 1.0 / 3.0,
                "proxy": 1.0,
                "target": 2.0,
            },
        ]
    }

    evidence = _distribution_evidence(
        grouped,
        proxy_field="proxy",
        target_field="target",
        proxy_scale=2.0,
        temperature=1.0,
    )

    assert evidence["mean_total_variation"] == pytest.approx(0.0)
    assert evidence["mean_jensen_shannon"] == pytest.approx(0.0)
    assert evidence["mean_update_direction_agreement"] == pytest.approx(1.0)
    assert evidence["mean_normalized_target_regret"] == pytest.approx(0.0)
    assert evidence["passes_distribution_gate"] is True


def test_contribution_authorization_distribution_gate_rejects_reversed_updates() -> None:
    grouped = {
        "task:a": [
            {
                "state_id": "a",
                "current_probability": 1.0 / 3.0,
                "proxy": 1.0,
                "target": -1.0,
            },
            {
                "state_id": "b",
                "current_probability": 1.0 / 3.0,
                "proxy": 0.0,
                "target": 0.0,
            },
            {
                "state_id": "c",
                "current_probability": 1.0 / 3.0,
                "proxy": -1.0,
                "target": 1.0,
            },
        ]
    }

    evidence = _distribution_evidence(
        grouped,
        proxy_field="proxy",
        target_field="target",
        proxy_scale=1.0,
        temperature=0.25,
    )

    assert evidence["mean_update_direction_agreement"] < 0.75
    assert evidence["passes_distribution_gate"] is False


def test_contribution_authorization_update_preserves_probability_support() -> None:
    probabilities, normalized = _next_distribution(
        [0.2, 0.3, 0.5],
        [-20.0, 0.0, 20.0],
        temperature=1.0,
    )

    assert sum(probabilities) == pytest.approx(1.0)
    assert min(probabilities) > 0
    assert all(0 < value < 1 for value in normalized)


def test_gp_c_formula_replays_one_cold_start_adamw_step() -> None:
    learning_rate = 2e-4
    epsilon = 1e-8
    maximum_gradient_norm = 1.0
    parameter = torch.nn.Parameter(torch.tensor([0.5, -0.75], dtype=torch.float64))
    initial = parameter.detach().clone()
    gradient = {"weight": torch.tensor([3.0, -4.0], dtype=torch.float64)}
    expected = _adamw_descent_direction(
        gradient,
        learning_rate=learning_rate,
        epsilon=epsilon,
        maximum_gradient_norm=maximum_gradient_norm,
    )

    parameter.grad = gradient["weight"].clone()
    torch.nn.utils.clip_grad_norm_((parameter,), maximum_gradient_norm)
    optimizer = torch.optim.AdamW(
        (parameter,),
        lr=learning_rate,
        betas=(0.9, 0.999),
        eps=epsilon,
        weight_decay=0.0,
        foreach=False,
    )
    optimizer.step()
    actual = {"weight": initial - parameter.detach()}

    fidelity = _vector_fidelity(expected, actual)
    assert fidelity["cosine"] == pytest.approx(1.0, abs=1e-7)
    assert fidelity["relative_error"] < 1e-5
    assert fidelity["norm_ratio"] == pytest.approx(1.0, rel=1e-5)


def test_gp_c_sgd_ranking_is_a_positive_rescaling_of_gp_b() -> None:
    objective = torch.tensor([2.0, -1.0], dtype=torch.float64)
    gradients = (
        torch.tensor([1.0, 0.0], dtype=torch.float64),
        torch.tensor([0.0, 1.0], dtype=torch.float64),
        torch.tensor([-1.0, -1.0], dtype=torch.float64),
    )
    probabilities = [0.2, 0.3, 0.5]
    learning_rate = 5e-5
    gp_b = _center(
        [float(torch.dot(objective, gradient)) for gradient in gradients],
        probabilities,
    )
    gp_c_sgd = _center(
        [float(torch.dot(objective, learning_rate * gradient)) for gradient in gradients],
        probabilities,
    )

    assert gp_c_sgd == pytest.approx(
        [learning_rate * value for value in gp_b],
        abs=1e-12,
    )
    assert sorted(range(3), key=gp_b.__getitem__) == sorted(
        range(3),
        key=gp_c_sgd.__getitem__,
    )

    audit = _sgd_equivalence_audit(
        [
            {
                "states": [
                    {
                        "state_id": str(index),
                        "estimation_gp_b_centered_dot": gp_b[index],
                        "validation_gp_b_centered_dot": gp_b[index],
                        "estimation_gp_c_sgd_equivalent": gp_c_sgd[index],
                        "validation_gp_c_sgd_equivalent": gp_c_sgd[index],
                    }
                    for index in range(3)
                ]
            }
        ],
        learning_rate=learning_rate,
    )
    assert audit["comparison_count"] == 6
    assert audit["maximum_absolute_scaling_error"] == pytest.approx(0.0)
    assert audit["all_task_split_rankings_identical"] is True


def test_gp_c_distribution_contract_replay_preserves_support_and_mass() -> None:
    plan = {
        "distribution_epsilon": 0.4,
        "task_rows": [
            {
                "coordinate_indices": [0, 1],
                "probabilities": [1.0 / 3.0] * 3,
            }
        ],
        "design_rows": [{"signs": [1, -1]}],
    }

    replay = _distribution_contract_replay(plan)

    assert replay["task_design_evaluation_count"] == 1
    assert replay["support_preserved"] is True
    assert replay["minimum_perturbed_probability"] > 0
    assert replay["maximum_probability_mass_error"] == pytest.approx(0.0)
