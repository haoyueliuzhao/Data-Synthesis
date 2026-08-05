from __future__ import annotations

import json
import math
from types import SimpleNamespace

import pytest
import torch

import trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient as gradient_module
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
    CALIBRATED_NUMERIC_PROFILE,
    _activate_deterministic_eval_checkpointing,
    _aligned_token_region_partition,
    _attach_centered_signal,
    _current_state_probabilities,
    _gradient_alignment,
    _gradient_norm,
    _load_numeric_contract,
    _load_state_realizations,
    _mean_supervised_nll,
    _normalized_gradient_alignment,
    _numeric_precision_replay,
    _realization_stability_thresholds,
    _selected_gradient_states,
    _state_realization_diagnostics,
    _supervised_causal_projection,
    _support_target_boundary,
    _token_gradient_decomposition_metrics,
    _token_overlap,
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
from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_precision_calibration import (
    _build_numeric_contract,
    _derive_validation_thresholds,
    _distribution_distance,
    _multi_gpu_load_kwargs,
    _rank_agreement,
    _release_multi_gpu_load_cache,
    _softmax_update,
    _strict_max_memory,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_precision_calibration import (
    _summary as _precision_summary,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _strict_cuda_max_memory,
    _validated_hf_device_map,
)
from trusted_synthesis.hashing import canonical_hash


class _RealizationRow:
    @classmethod
    def model_validate(cls, row):
        return SimpleNamespace(
            realization_id=row["realization_id"],
            record=SimpleNamespace(record_id=row["record_id"]),
            trajectory_id=row["trajectory_id"],
            trajectory_hash=row["trajectory_hash"],
            decision_trace_hash=row["decision_trace_hash"],
        )


def test_gradient_loader_accepts_independent_draws_with_shared_decision_trace(
    tmp_path,
    monkeypatch,
) -> None:
    rows = [
        {
            "realization_id": f"realization:{index}",
            "record_id": f"record:{index}",
            "trajectory_id": f"trajectory:{index}",
            "trajectory_hash": f"trajectory_hash:{index}",
            "decision_trace_hash": "decision_trace:shared",
        }
        for index in range(2)
    ]
    path = tmp_path / "realizations.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    monkeypatch.setattr(gradient_module, "GradientStateRealization", _RealizationRow)

    loaded = _load_state_realizations(path)

    assert len(loaded) == 2
    assert len({row.decision_trace_hash for row in loaded}) == 1


def test_gradient_loader_rejects_duplicate_trajectory_payloads(
    tmp_path,
    monkeypatch,
) -> None:
    rows = [
        {
            "realization_id": f"realization:{index}",
            "record_id": f"record:{index}",
            "trajectory_id": f"trajectory:{index}",
            "trajectory_hash": "trajectory_hash:shared",
            "decision_trace_hash": f"decision_trace:{index}",
        }
        for index in range(2)
    ]
    path = tmp_path / "realizations.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    monkeypatch.setattr(gradient_module, "GradientStateRealization", _RealizationRow)

    with pytest.raises(ValueError, match="payloads are duplicated"):
        _load_state_realizations(path)


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
        minimum_replicates=4,
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
            evaluation_record_count=32,
        )
    with pytest.raises(ValueError, match="at least 8 evaluation records"):
        _validate_run_contract(
            run_role="smoke",
            task_count=3,
            evaluation_record_count=6,
        )


def test_gradient_support_boundary_separates_targets_from_exclusions() -> None:
    target_ids = ("target:1", "target:2")
    excluded_ids = ("baseline:1", "support:1")
    support_plan = {
        "gradient_target_contract": {
            "task_ids": target_ids,
            "task_set_id": canonical_hash(
                target_ids,
                prefix="finance_gradient_target_task_set:",
            ),
        },
        "objective_support_exclusion_contract": {
            "task_ids": excluded_ids,
            "task_set_id": canonical_hash(
                excluded_ids,
                prefix="finance_objective_support_excluded_task_set:",
            ),
        },
    }

    targets, exclusions, target_set_id = _support_target_boundary(support_plan)

    assert targets == set(target_ids)
    assert exclusions == set(excluded_ids)
    assert target_set_id == support_plan["gradient_target_contract"]["task_set_id"]


def test_gradient_support_boundary_rejects_target_exclusion_overlap() -> None:
    overlapping_ids = ("target:1",)
    support_plan = {
        "gradient_target_contract": {
            "task_ids": overlapping_ids,
            "task_set_id": canonical_hash(
                overlapping_ids,
                prefix="finance_gradient_target_task_set:",
            ),
        },
        "objective_support_exclusion_contract": {
            "task_ids": overlapping_ids,
            "task_set_id": canonical_hash(
                overlapping_ids,
                prefix="finance_objective_support_excluded_task_set:",
            ),
        },
    }

    with pytest.raises(ValueError, match="overlap Objective support exclusions"):
        _support_target_boundary(support_plan)


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
            state("broad_full_lineage", "full"),
            state("compact_output_lineage", "output"),
        )
    )

    selected = _selected_gradient_states(comparison_artifact)

    assert [item.strategy for item in selected] == [
        "compact_direct",
        "broad_direct",
        "broad_full_lineage",
        "compact_verify_frontier",
        "compact_output_lineage",
    ]
    context_artifact = SimpleNamespace(
        accepted_states=(
            state("compact_direct", "compact"),
            state("semantic_direct", "semantic"),
            state("broad_direct", "broad"),
            state("broad_full_lineage", "full"),
            state("compact_output_lineage", "output"),
        )
    )
    context_selected = _selected_gradient_states(context_artifact)
    assert [item.strategy for item in context_selected] == [
        "compact_direct",
        "semantic_direct",
        "broad_direct",
        "broad_full_lineage",
        "compact_output_lineage",
    ]

    with pytest.raises(ValueError, match="complete 3-5-state verified support"):
        _selected_gradient_states(
            SimpleNamespace(
                accepted_states=(
                    state("compact_direct", "compact"),
                    state("broad_direct", "broad"),
                )
            )
        )


def test_gradient_projection_replays_exact_nonuniform_distribution() -> None:
    probabilities = _current_state_probabilities(
        ["state-c", "state-a", "state-b"],
        probabilities={"state-a": 0.15, "state-b": 0.25, "state-c": 0.60},
    )

    assert probabilities == {"state-a": 0.15, "state-b": 0.25, "state-c": 0.60}
    with pytest.raises(ValueError, match="exactly cover"):
        _current_state_probabilities(
            ["state-a", "state-b", "state-c"],
            probabilities={"state-a": 0.5, "state-b": 0.5},
        )


def test_state_realization_diagnostics_measure_stability_and_adamw_saturation() -> None:
    gradients = [
        {"weight": torch.tensor([1.0, 2.0, 1e-10])},
        {"weight": torch.tensor([1.1, 1.9, -1e-10])},
        {"weight": torch.tensor([0.9, 2.1, 0.0])},
    ]
    mean = _weighted_gradient(gradients, [1.0, 1.0, 1.0])

    diagnostics = _state_realization_diagnostics(
        gradients,
        mean,
        learning_rate=2e-4,
        optimizer_epsilon=1e-8,
        maximum_gradient_norm=1.0,
    )

    assert diagnostics["realization_count"] == 3
    assert 0 < diagnostics["gradient_effective_sample_size"] <= 3
    assert diagnostics["mean_pairwise_gradient_cosine"] > 0.99
    assert diagnostics["mean_sign_saturation_ratio"] >= 1 / 3
    assert diagnostics["mean_pairwise_update_vector_cosine"] > 0


def test_target_token_overlap_reports_position_and_vocabulary_overlap() -> None:
    overlap = _token_overlap((1, 2, 3, 4), (1, 2, 8, 4))

    assert overlap["position_overlap"] == pytest.approx(0.75)
    assert overlap["set_jaccard"] == pytest.approx(3 / 5)


def test_aligned_token_region_partition_separates_shared_and_state_tokens() -> None:
    encoded = {
        record_id: {
            "input_ids": [99, 1, state_token, 3, 4],
            "labels": [-100, 1, state_token, 3, 4],
        }
        for record_id, state_token in (("r1", 7), ("r2", 8), ("r3", 9))
    }

    regions = _aligned_token_region_partition(("r1", "r2", "r3"), encoded)

    assert set(regions) == {"r1", "r2", "r3"}
    assert all(row["common_label_positions"] == (1, 3, 4) for row in regions.values())
    assert all(row["differential_label_positions"] == (2,) for row in regions.values())
    assert all(
        row["differential_supervised_token_fraction"] == pytest.approx(0.25)
        for row in regions.values()
    )


def test_token_region_manifest_gates_task_pooled_coverage_not_each_draw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def region(*, common: int, differential: int) -> dict[str, object]:
        return {
            "common_label_positions": tuple(range(common)),
            "differential_label_positions": tuple(range(common, common + differential)),
            "common_supervised_token_count": common,
            "differential_supervised_token_count": differential,
            "differential_supervised_token_fraction": differential
            / (common + differential),
        }

    regions = {
        "r-low": region(common=99, differential=1),
        "r-high-a": region(common=50, differential=50),
        "r-high-b": region(common=50, differential=50),
    }
    monkeypatch.setattr(
        gradient_module,
        "_aligned_token_region_partition",
        lambda record_ids, _encoded: {record_id: regions[record_id] for record_id in record_ids},
    )
    jobs = [
        {"task_id": "task", "state_id": state_id, "record_id": record_id}
        for state_id, record_id in (
            ("state-low", "r-low"),
            ("state-high-a", "r-high-a"),
            ("state-high-b", "r-high-b"),
        )
    ]

    manifest = gradient_module._build_token_region_manifest(
        jobs,
        {record_id: {} for record_id in regions},
    )

    assert manifest["status"] == "passed"
    assert manifest[
        "minimum_observed_record_differential_supervised_token_fraction"
    ] == pytest.approx(0.01)
    assert manifest[
        "minimum_observed_task_pooled_differential_supervised_token_fraction"
    ] == pytest.approx(101 / 300)


def test_token_region_manifest_rejects_low_task_pooled_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    regions = {
        record_id: {
            "common_label_positions": tuple(range(99)),
            "differential_label_positions": (99,),
            "common_supervised_token_count": 99,
            "differential_supervised_token_count": 1,
            "differential_supervised_token_fraction": 0.01,
        }
        for record_id in ("r1", "r2", "r3")
    }
    monkeypatch.setattr(
        gradient_module,
        "_aligned_token_region_partition",
        lambda record_ids, _encoded: {record_id: regions[record_id] for record_id in record_ids},
    )
    jobs = [
        {"task_id": "task", "state_id": f"state-{index}", "record_id": record_id}
        for index, record_id in enumerate(regions)
    ]

    with pytest.raises(ValueError, match="dominated by common target tokens"):
        gradient_module._build_token_region_manifest(
            jobs,
            {record_id: {} for record_id in regions},
        )


def test_sparse_supervised_causal_projection_is_exact_mean_nll() -> None:
    torch.manual_seed(7)
    logits = torch.randn(1, 6, 11, dtype=torch.float64)
    labels = torch.tensor([[-100, 2, -100, 4, 5, -100]])

    prediction_positions, targets, count = _supervised_causal_projection(labels)
    sparse_loss = torch.nn.functional.cross_entropy(
        logits.index_select(1, prediction_positions).reshape(-1, logits.shape[-1]),
        targets.reshape(-1),
    )
    dense_loss = torch.nn.functional.cross_entropy(
        logits[:, :-1, :].reshape(-1, logits.shape[-1]),
        labels[:, 1:].reshape(-1),
        ignore_index=-100,
    )

    assert prediction_positions.tolist() == [0, 2, 3]
    assert targets.tolist() == [[2, 4, 5]]
    assert count == 3
    assert sparse_loss == pytest.approx(dense_loss)


def test_sparse_supervised_causal_projection_honors_token_region() -> None:
    labels = torch.tensor([[-100, 2, 3, 4, 5]])

    prediction_positions, targets, count = _supervised_causal_projection(
        labels,
        supervised_label_positions=(2, 4),
    )

    assert prediction_positions.tolist() == [1, 3]
    assert targets.tolist() == [[3, 5]]
    assert count == 2


def test_sharded_cuda_memory_contract_excludes_unselected_devices() -> None:
    assert _strict_cuda_max_memory(8, (4, 5, 6, 7)) == {
        0: 0,
        1: 0,
        2: 0,
        3: 0,
        4: "45GiB",
        5: "45GiB",
        6: "45GiB",
        7: "45GiB",
    }
    with pytest.raises(ValueError, match="invalid sharded CUDA device whitelist"):
        _strict_cuda_max_memory(8, (4, 4))


def test_hf_device_map_fails_closed_on_whitelist_escape() -> None:
    valid = SimpleNamespace(hf_device_map={"model.layers.0": 4, "lm_head": "cuda:7"})
    assert _validated_hf_device_map(valid, allowed_device_ids=(4, 5, 6, 7)) == {
        "lm_head": "cuda:7",
        "model.layers.0": "4",
    }

    escaped = SimpleNamespace(hf_device_map={"model.layers.0": 0, "lm_head": 7})
    with pytest.raises(ValueError, match="escaped its CUDA device whitelist"):
        _validated_hf_device_map(escaped, allowed_device_ids=(4, 5, 6, 7))


def test_objective_checkpointing_preserves_stochastic_eval_mode() -> None:
    checkpoint_layer = torch.nn.Linear(3, 3)
    checkpoint_layer.gradient_checkpointing = True  # type: ignore[attr-defined]
    checkpoint_layer._gradient_checkpointing_func = object()  # type: ignore[attr-defined]
    dropout = torch.nn.Dropout(p=0.5)
    model = torch.nn.Sequential(checkpoint_layer, dropout)
    model.eval()

    activated = _activate_deterministic_eval_checkpointing(model)

    assert activated == 1
    assert checkpoint_layer.training
    assert not dropout.training
    assert not model.training


def test_shared_forward_token_region_gradients_recompose() -> None:
    torch.manual_seed(17)
    weight = torch.nn.Parameter(torch.randn(4, 7))
    features = torch.randn(1, 5, 4)
    targets = torch.tensor([[1, 2, 3, 4, 5]])
    logits = features @ weight
    common_ordinals = torch.tensor([0, 2, 4])
    differential_ordinals = torch.tensor([1, 3])

    full = torch.autograd.grad(
        _mean_supervised_nll(logits, targets),
        weight,
        retain_graph=True,
    )[0]
    common = torch.autograd.grad(
        _mean_supervised_nll(logits, targets, token_ordinals=common_ordinals),
        weight,
        retain_graph=True,
    )[0]
    differential = torch.autograd.grad(
        _mean_supervised_nll(logits, targets, token_ordinals=differential_ordinals),
        weight,
    )[0]

    recomposed = (3 * common + 2 * differential) / 5
    assert torch.allclose(full, recomposed, atol=1e-6, rtol=1e-6)


def test_token_gradient_decomposition_recomposes_full_supervised_gradient() -> None:
    common = {"weight": torch.tensor([2.0, 0.0])}
    differential = {"weight": torch.tensor([0.0, 4.0])}
    full = _weighted_gradient([common, differential], [3.0, 1.0])

    diagnostics = _token_gradient_decomposition_metrics(
        full,
        common,
        differential,
        common_token_count=3,
        differential_token_count=1,
    )

    assert diagnostics["token_gradient_recomposition_relative_error"] == pytest.approx(0.0)
    assert diagnostics["token_gradient_recomposition_cosine"] == pytest.approx(1.0)
    assert diagnostics["differential_gradient_fraction"] == pytest.approx(2 / 3)


def test_precision_calibration_gpu_contract_excludes_unselected_devices() -> None:
    assert _strict_max_memory(4, (1, 3)) == {
        0: 0,
        1: "12GiB",
        2: 0,
        3: "12GiB",
    }
    with pytest.raises(ValueError, match="GPU whitelist"):
        _strict_max_memory(4, (1, 1))


def test_precision_calibration_multi_gpu_reserves_first_device_for_activations() -> None:
    assert _multi_gpu_load_kwargs(4, (1, 3)) == {
        "device_map": "balanced",
        "max_memory": {0: 0, 1: "4GiB", 2: 0, 3: "24GiB"},
    }


def test_precision_calibration_releases_only_multi_gpu_load_cache() -> None:
    calls: list[bool] = []
    torch_module = SimpleNamespace(cuda=SimpleNamespace(empty_cache=lambda: calls.append(True)))

    _release_multi_gpu_load_cache(torch_module, (1,))
    assert calls == []
    _release_multi_gpu_load_cache(torch_module, (1, 3))
    assert calls == [True]


def test_precision_calibration_distribution_stability_is_exact() -> None:
    probabilities = {"a": 0.2, "b": 0.3, "c": 0.5}
    scores = {"a": -0.2, "b": 0.1, "c": 0.4}

    updated = _softmax_update(probabilities, scores)
    total_variation, jensen_shannon = _distribution_distance(updated, updated)

    assert sum(updated.values()) == pytest.approx(1.0)
    assert total_variation == pytest.approx(0.0)
    assert jensen_shannon == pytest.approx(0.0)
    assert _rank_agreement(scores, dict(scores)) == 1.0


def test_precision_calibration_summary_is_fail_closed() -> None:
    rows = [
        {
            "task_id": "task-1",
            "state_id": state_id,
            "full_gp_score": score,
            "recomposed_gp_score": score,
            "loss_identity_absolute_error": 0.0,
            "token_gradient_recomposition_cosine": 1.0,
            "token_gradient_recomposition_relative_error": 0.0,
        }
        for state_id, score in (("a", 0.1), ("b", -0.2), ("c", 0.3))
    ]
    distributions = {"task-1": {"probabilities": {"a": 0.2, "b": 0.3, "c": 0.5}}}

    passed = _precision_summary(rows, task_distributions=distributions)
    assert passed["status"] == "passed"

    rows[0]["token_gradient_recomposition_relative_error"] = 0.01
    failed = _precision_summary(rows, task_distributions=distributions)
    assert failed["status"] == "failed"


def test_precision_calibration_freezes_quantized_holdout_thresholds() -> None:
    thresholds = _derive_validation_thresholds(
        {
            "maximum_loss_identity_absolute_error": 0.0,
            "minimum_gradient_recomposition_cosine": 0.9998648,
            "maximum_gradient_recomposition_relative_error": 0.0166871,
            "maximum_gp_score_absolute_delta": 0.0015932,
            "minimum_task_rank_agreement": 1.0,
            "maximum_update_total_variation": 0.00012303,
            "maximum_update_jensen_shannon": 2.3e-8,
        }
    )

    assert thresholds["minimum_gradient_recomposition_cosine"] == pytest.approx(0.99976)
    assert thresholds["maximum_gradient_recomposition_relative_error"] == pytest.approx(0.021)
    assert thresholds["maximum_gp_score_absolute_delta"] == pytest.approx(0.0024)
    assert thresholds["maximum_update_total_variation"] == pytest.approx(0.00019)


def test_precision_numeric_contract_uses_frozen_holdout_thresholds() -> None:
    frozen_thresholds = {
        "maximum_loss_identity_absolute_error": 1e-6,
        "minimum_gradient_recomposition_cosine": 0.99975,
        "maximum_gradient_recomposition_relative_error": 0.022,
        "maximum_gp_score_absolute_delta": 0.0023,
        "minimum_task_rank_agreement": 1.0,
        "maximum_update_total_variation": 0.00027,
        "maximum_update_jensen_shannon": 1e-6,
    }
    profile = {"profile_id": "bf16_checkpoint_strict_accumulation"}
    contract = _build_numeric_contract(
        plan={"plan_hash": "plan:1"},
        selection={
            "status": "frozen",
            "selected_profile_id": profile["profile_id"],
            "selection_hash": "selection:1",
            "frozen_validation_thresholds": frozen_thresholds,
        },
        development={"profile": profile, "result_hash": "development:1"},
        validation={
            "profile": profile,
            "result_hash": "validation:1",
            "summary": {"thresholds": frozen_thresholds},
        },
    )

    assert contract["thresholds"] == frozen_thresholds
    assert contract["thresholds"] != {
        **frozen_thresholds,
        "maximum_gradient_recomposition_relative_error": 1e-4,
    }


def test_precision_numeric_contract_rejects_threshold_replay_mismatch() -> None:
    profile = {"profile_id": "bf16_checkpoint_strict_accumulation"}
    with pytest.raises(ValueError, match="frozen threshold contract"):
        _build_numeric_contract(
            plan={"plan_hash": "plan:1"},
            selection={
                "status": "frozen",
                "selected_profile_id": profile["profile_id"],
                "selection_hash": "selection:1",
                "frozen_validation_thresholds": {
                    "maximum_gradient_recomposition_relative_error": 0.022
                },
            },
            development={"profile": profile, "result_hash": "development:1"},
            validation={
                "profile": profile,
                "result_hash": "validation:1",
                "summary": {"thresholds": {"maximum_gradient_recomposition_relative_error": 1e-4}},
            },
        )


def test_gradient_v12_replays_frozen_numeric_contract(tmp_path) -> None:
    thresholds = {
        "maximum_loss_identity_absolute_error": 1e-6,
        "minimum_gradient_recomposition_cosine": 0.99975,
        "maximum_gradient_recomposition_relative_error": 0.022,
        "maximum_gp_score_absolute_delta": 0.0023,
        "minimum_task_rank_agreement": 1.0,
        "maximum_update_total_variation": 0.00027,
        "maximum_update_jensen_shannon": 1e-6,
    }
    contract = {
        "calibration_version": "finance_gradient_finite_precision_calibration.v3",
        "plan_hash": "precision-plan:1",
        "selection_hash": "precision-selection:1",
        "selected_profile": CALIBRATED_NUMERIC_PROFILE,
        "thresholds": thresholds,
        "development_result_hash": "development:1",
        "validation_result_hash": "validation:1",
        "allowed_next_run_role": "independent_30_task_production_candidate",
    }
    contract["contract_hash"] = canonical_hash(
        contract,
        prefix="finance_gradient_precision_contract:",
    )
    path = tmp_path / "numeric_contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    assert _load_numeric_contract(path) == contract
    assert _realization_stability_thresholds({"numeric_contract": contract})[
        "maximum_token_gradient_recomposition_relative_error"
    ] == pytest.approx(0.022)

    contract["thresholds"]["maximum_gp_score_absolute_delta"] = 1.0
    path.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(ValueError, match="identity replay"):
        _load_numeric_contract(path)


def test_gradient_v12_numeric_replay_tracks_rank_and_distribution() -> None:
    rows = []
    for state_id, full_score, recomposed_score in (
        ("state-a", 0.4, 0.4001),
        ("state-b", 0.2, 0.2001),
        ("state-c", -0.1, -0.1001),
    ):
        rows.append(
            {
                "task_id": "task-1",
                "state_id": state_id,
                "numeric_full_gp_score": full_score,
                "numeric_recomposed_gp_score": recomposed_score,
                "numeric_gp_score_absolute_delta": abs(full_score - recomposed_score),
                "loss_identity_absolute_error": 0.0,
            }
        )
    replay = _numeric_precision_replay(
        rows,
        {
            "task_distributions": {
                "task-1": {
                    "probabilities": {
                        "state-a": 0.2,
                        "state-b": 0.3,
                        "state-c": 0.5,
                    }
                }
            }
        },
    )

    assert replay["minimum_task_rank_agreement"] == 1.0
    assert replay["maximum_gp_score_absolute_delta"] == pytest.approx(0.0001)
    assert replay["maximum_update_total_variation"] < 0.0001
    assert replay["maximum_update_jensen_shannon"] < 1e-6


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
