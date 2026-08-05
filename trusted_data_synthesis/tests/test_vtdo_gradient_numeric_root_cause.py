from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from torch import nn

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_gradient_numeric_root_cause as root_cause,
)
from trusted_synthesis.hashing import canonical_hash

EXPECTED_PROFILES = {
    "control_bf16_checkpoint_tf32": (None, 1),
    "projection_fp32_only": ("control_bf16_checkpoint_tf32", 1),
    "accumulation_fp64_only": ("control_bf16_checkpoint_tf32", 1),
    "tf32_off_only": ("control_bf16_checkpoint_tf32", 1),
    "checkpoint_on_separate_forward": ("control_bf16_checkpoint_tf32", 1),
    "checkpoint_off_separate_forward": ("checkpoint_on_separate_forward", 3),
    "checkpoint_off_functional_call": ("checkpoint_off_separate_forward", 3),
    "fp32_activation_strict": ("tf32_off_only", 3),
}


def _source() -> dict[str, object]:
    return {
        "plan_hash": "source-plan:1",
        "plan_sha256": "a" * 64,
        "manifest_hash": "source-manifest:1",
        "manifest_sha256": "b" * 64,
        "objective_split": "estimation",
        "objective_record_set_id": "objective-set:1",
        "target_records_sha256": "c" * 64,
        "token_region_manifest_hash": "token-regions:1",
        "beneficiary_adapter_tensor_sha256": "d" * 64,
        "jobs": [],
        "task_distributions": {},
    }


def _plan() -> dict[str, object]:
    implementation_manifest = root_cause._implementation_manifest()
    return {
        "plan_hash": "plan:1",
        "implementation_sha256": root_cause._sha256(Path(root_cause.__file__).resolve()),
        "implementation_manifest": implementation_manifest,
        "implementation_manifest_hash": canonical_hash(
            implementation_manifest,
            prefix="finance_gradient_numeric_root_cause_implementation:",
        ),
        "sources": {
            "development": _source(),
            "validation": _source(),
        },
    }


def _selection(
    *,
    selected_profile_id: str = "control_bf16_checkpoint_tf32",
) -> dict[str, object]:
    value: dict[str, object] = {
        "root_cause_version": root_cause.ROOT_CAUSE_VERSION,
        "plan_hash": "plan:1",
        "profile_manifest_hash": root_cause.PROFILE_MANIFEST_HASH,
        "status": "frozen",
        "selected_profile_id": selected_profile_id,
        "development_result_hashes": tuple(
            f"result:{index}" for index in range(len(root_cause.ROOT_CAUSE_PROFILES))
        ),
        "eligible_profile_ids": (selected_profile_id,),
        "required_profile_failures": (),
        "paired_contrasts": (),
        "selection_policy": root_cause.SELECTION_POLICY,
        "fixed_numeric_thresholds": root_cause.FIXED_NUMERIC_THRESHOLDS,
        "pairwise_uncertainty_envelope": 0.001,
        "selected_resource_contract": root_cause.PROFILE_RESOURCE_CONTRACTS[selected_profile_id],
        "validation_observed": False,
        "sealed_candidate_outcomes_observed": False,
        "claim_boundary": "development only",
    }
    value["selection_hash"] = canonical_hash(
        value,
        prefix="finance_gradient_numeric_root_cause_selection:",
    )
    return value


def _result(
    *,
    split: str = "development",
    profile_id: str = "control_bf16_checkpoint_tf32",
) -> dict[str, object]:
    source = _source()
    profile = root_cause._profile(profile_id)
    gpu_ids = tuple(range(profile.required_gpu_count))
    value: dict[str, object] = {
        "root_cause_version": root_cause.ROOT_CAUSE_VERSION,
        "plan_hash": "plan:1",
        "split": split,
        "implementation_sha256": root_cause._sha256(Path(root_cause.__file__).resolve()),
        "implementation_manifest_hash": _plan()["implementation_manifest_hash"],
        "applied_uncertainty_envelope": None,
        "profile": asdict(profile),
        "profile_algorithm_contract": profile.algorithm_contract,
        "resource_contract": root_cause.PROFILE_RESOURCE_CONTRACTS[profile_id],
        "source_plan_hash": source["plan_hash"],
        "source_manifest_hash": source["manifest_hash"],
        "objective_split": source["objective_split"],
        "objective_record_set_id": source["objective_record_set_id"],
        "requested_cuda_device_ids": gpu_ids,
        "preflight_gpu_memory": {
            str(gpu_id): {"free_bytes": 70 * root_cause.GIB} for gpu_id in gpu_ids
        },
        "status": "execution_failed",
        "error_type": "SyntheticFailure",
        "error": "test-only failure payload",
    }
    value["result_hash"] = canonical_hash(
        value,
        prefix="finance_gradient_numeric_root_cause_result:",
    )
    return value


def test_profile_registry_freezes_all_root_cause_factors() -> None:
    assert set(root_cause.PROFILE_BY_ID) == set(EXPECTED_PROFILES)
    assert root_cause.FIXED_NUMERIC_THRESHOLDS == {
        "maximum_loss_identity_absolute_error": 1e-6,
        "minimum_gradient_recomposition_cosine": 0.99967,
        "maximum_gradient_recomposition_relative_error": 0.027,
        "maximum_gp_score_absolute_delta": 0.0023,
        "maximum_update_total_variation": 0.00023,
        "maximum_update_jensen_shannon": 1e-6,
    }
    for profile_id, (baseline_id, gpu_count) in EXPECTED_PROFILES.items():
        profile = root_cause._profile(profile_id)
        assert profile.baseline_profile_id == baseline_id
        assert profile.required_gpu_count == gpu_count
        assert root_cause.PROFILE_RESOURCE_CONTRACTS[profile_id] == {
            "required_gpu_count": gpu_count,
            "minimum_free_memory_bytes_per_gpu": 64 * root_cause.GIB,
        }
        if baseline_id is not None:
            assert root_cause._factor_differences(
                root_cause._profile(baseline_id),
                profile,
            ) == tuple(sorted(root_cause.PROFILE_FACTOR_CHANGES[profile_id]))

    functional = root_cause._profile("checkpoint_off_functional_call")
    assert functional.algorithm_contract["forward_graph_count_per_realization"] == 3
    assert functional.algorithm_contract["saved_tensor_policy"] == root_cause.SAVED_TENSOR_POLICY
    assert functional.algorithm_contract["saved_tensor_restore_non_blocking"] is False
    assert (
        functional.algorithm_contract["model_input_device_policy"]
        == root_cause.MODEL_INPUT_DEVICE_POLICY
    )
    assert functional.algorithm_contract["sdpa_backend_policy"] == root_cause.SDPA_BACKEND_POLICY
    assert functional.algorithm_contract["gqa_execution_policy"] == root_cause.GQA_EXECUTION_POLICY
    activation = root_cause._profile("fp32_activation_strict")
    assert activation.precision.model_dtype == "float32"
    assert activation.algorithm_contract["effective_projection_dtype"] == "bfloat16"


def test_diagnostic_jobs_select_one_lowest_realization_per_task_state() -> None:
    jobs = (
        {"task_id": "task:b", "state_id": "state:1", "job_id": "job:3", "realization_index": 2},
        {"task_id": "task:a", "state_id": "state:1", "job_id": "job:2", "realization_index": 1},
        {"task_id": "task:a", "state_id": "state:1", "job_id": "job:1", "realization_index": 0},
        {"task_id": "task:b", "state_id": "state:1", "job_id": "job:4", "realization_index": 0},
        {"task_id": "task:a", "state_id": "state:2", "job_id": "job:5", "realization_index": 0},
    )

    selected = root_cause._diagnostic_jobs(jobs)

    assert tuple(job["job_id"] for job in selected) == ("job:1", "job:5", "job:4")
    assert all(job["realization_index"] == 0 for job in selected)


def test_batch_is_placed_on_model_input_embedding_device() -> None:
    target_device = "cuda:4"
    calls: list[str] = []

    class TensorProbe:
        def to(self, device: object) -> TensorProbe:
            calls.append(str(device))
            return self

    model = SimpleNamespace(
        get_base_model=lambda: SimpleNamespace(
            get_input_embeddings=lambda: SimpleNamespace(
                weight=SimpleNamespace(device=target_device)
            )
        )
    )
    batch = {"input_ids": TensorProbe(), "attention_mask": TensorProbe(), "labels": TensorProbe()}

    placed = root_cause._place_batch_on_model_input_device(model, batch)

    assert placed == batch
    assert calls == [target_device, target_device, target_device]


def test_attention_policy_forces_explicit_kv_repeat() -> None:
    module = SimpleNamespace(use_gqa_in_sdpa=lambda *_args, **_kwargs: True)

    root_cause._configure_attention_execution_policy(module)

    assert module.use_gqa_in_sdpa(None, object(), object()) is False


def test_saved_tensor_round_trip_preserves_stride_and_values() -> None:
    source = torch.arange(12, dtype=torch.float32).reshape(3, 4).transpose(0, 1)

    packed = root_cause._pack_saved_tensor_to_cpu(torch, source)
    restored = root_cause._unpack_saved_tensor_from_cpu(packed)

    assert packed[1].stride() == source.stride()
    assert restored.stride() == source.stride()
    assert torch.equal(restored, source)


def test_profile_registry_survives_json_plan_round_trip() -> None:
    plan = {
        "profiles": tuple(asdict(value) for value in root_cause.ROOT_CAUSE_PROFILES),
        "profile_manifest_hash": root_cause.PROFILE_MANIFEST_HASH,
        "profile_factor_changes": root_cause._serialized_factor_changes(),
        "profile_resource_contracts": root_cause.PROFILE_RESOURCE_CONTRACTS,
        "fixed_numeric_thresholds": root_cause.FIXED_NUMERIC_THRESHOLDS,
        "selection_policy": root_cause.SELECTION_POLICY,
    }

    root_cause._verify_profile_registry(json.loads(json.dumps(plan)))


def test_resource_contract_is_exact_and_fail_closed() -> None:
    profile = root_cause._profile("checkpoint_off_separate_forward")
    sufficient = {
        "0": {"free_bytes": 70 * root_cause.GIB},
        "1": {"free_bytes": 70 * root_cause.GIB},
        "2": {"free_bytes": 70 * root_cause.GIB},
    }
    assert (
        root_cause._verify_resource_contract(profile, (0, 1, 2), sufficient)
        == (root_cause.PROFILE_RESOURCE_CONTRACTS[profile.profile_id])
    )

    with pytest.raises(ValueError, match="requires 3 GPU"):
        root_cause._verify_resource_contract(profile, (0,), {"0": sufficient["0"]})
    with pytest.raises(ValueError, match="duplicated"):
        root_cause._verify_resource_contract(profile, (0, 1, 1), sufficient)
    insufficient = {**sufficient, "2": {"free_bytes": 63 * root_cause.GIB}}
    with pytest.raises(ValueError, match="free-memory preflight"):
        root_cause._verify_resource_contract(profile, (0, 1, 2), insufficient)


def test_checkpoint_replay_binds_plan_source_profile_and_job() -> None:
    source = _source()
    job = {
        "job_id": "job:1",
        "task_id": "task:1",
        "task_type": "comparison",
        "state_id": "state:1",
        "record_id": "record:1",
        "gradient_seed": 11,
    }
    source["jobs"] = [job]
    plan = {"plan_hash": "plan:1"}
    profile = root_cause._profile("control_bf16_checkpoint_tf32")
    checkpoint = root_cause._build_checkpoint(
        plan=plan,
        source=source,
        split="development",
        profile=profile,
        job=job,
        row={**job, "full_gp_score": 0.2},
    )
    root_cause._verify_checkpoint(
        checkpoint,
        plan=plan,
        source=source,
        split="development",
        profile=profile,
        job=job,
    )

    checkpoint["row"]["record_id"] = "record:other"
    with pytest.raises(ValueError, match="immutable identity replay"):
        root_cause._verify_checkpoint(
            checkpoint,
            plan=plan,
            source=source,
            split="development",
            profile=profile,
            job=job,
        )


def test_result_and_selection_replay_reject_tampering() -> None:
    plan = _plan()
    result = _result()
    root_cause._verify_result(
        result,
        plan,
        split="development",
        profile_id="control_bf16_checkpoint_tf32",
    )
    result["source_plan_hash"] = "source-plan:other"
    with pytest.raises(ValueError, match="source differs"):
        root_cause._verify_result(
            result,
            plan,
            split="development",
            profile_id="control_bf16_checkpoint_tf32",
        )

    selection = _selection()
    root_cause._verify_selection(selection, plan)
    selection["pairwise_uncertainty_envelope"] = 0.004
    with pytest.raises(ValueError, match="immutable identity replay"):
        root_cause._verify_selection(selection, plan)


def test_completed_result_replays_jobs_summary_and_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = {
        "job_id": "job:1",
        "task_id": "task:1",
        "task_type": "comparison",
        "state_id": "state:1",
        "record_id": "record:1",
        "gradient_seed": 11,
    }
    source = _source()
    source["jobs"] = [job]
    plan = _plan()
    plan["sources"]["development"] = source
    profile = root_cause._profile("control_bf16_checkpoint_tf32")
    expected_summary = {"status": "passed", "proof": "recomputed"}
    monkeypatch.setattr(
        root_cause,
        "_combined_summary",
        lambda *args, **kwargs: expected_summary,
    )

    def make_result() -> dict[str, object]:
        value: dict[str, object] = {
            "root_cause_version": root_cause.ROOT_CAUSE_VERSION,
            "plan_hash": "plan:1",
            "split": "development",
            "implementation_sha256": plan["implementation_sha256"],
            "implementation_manifest_hash": plan["implementation_manifest_hash"],
            "applied_uncertainty_envelope": None,
            "profile": asdict(profile),
            "profile_algorithm_contract": profile.algorithm_contract,
            "resource_contract": root_cause.PROFILE_RESOURCE_CONTRACTS[profile.profile_id],
            "source_plan_hash": source["plan_hash"],
            "source_manifest_hash": source["manifest_hash"],
            "objective_split": source["objective_split"],
            "objective_record_set_id": source["objective_record_set_id"],
            "requested_cuda_device_ids": (0,),
            "preflight_gpu_memory": {"0": {"free_bytes": 70 * root_cause.GIB}},
            "status": "completed",
            "rows": [{**job, "full_gp_score": 0.2, "recomposed_gp_score": 0.2}],
            "checkpoint_version": root_cause.CHECKPOINT_VERSION,
            "checkpoint_hashes": ("checkpoint:1",),
            "summary": expected_summary,
        }
        value["result_hash"] = canonical_hash(
            value,
            prefix="finance_gradient_numeric_root_cause_result:",
        )
        return value

    result = make_result()
    root_cause._verify_result(
        result,
        plan,
        split="development",
        profile_id=profile.profile_id,
    )

    result = make_result()
    result["rows"][0]["record_id"] = "record:other"
    result["result_hash"] = canonical_hash(
        result,
        prefix="finance_gradient_numeric_root_cause_result:",
    )
    with pytest.raises(ValueError, match="row identity differs"):
        root_cause._verify_result(
            result,
            plan,
            split="development",
            profile_id=profile.profile_id,
        )

    result = make_result()
    result["summary"] = {"status": "passed", "proof": "forged"}
    result["result_hash"] = canonical_hash(
        result,
        prefix="finance_gradient_numeric_root_cause_result:",
    )
    with pytest.raises(ValueError, match="summary replay differs"):
        root_cause._verify_result(
            result,
            plan,
            split="development",
            profile_id=profile.profile_id,
        )

    result = make_result()
    result["implementation_sha256"] = "f" * 64
    result["result_hash"] = canonical_hash(
        result,
        prefix="finance_gradient_numeric_root_cause_result:",
    )
    with pytest.raises(ValueError, match="implementation differs"):
        root_cause._verify_result(
            result,
            plan,
            split="development",
            profile_id=profile.profile_id,
        )


def test_validation_is_blinded_until_development_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_cause._write_json(tmp_path / "plan.json", {"plan_hash": "plan:1"})
    monkeypatch.setattr(root_cause, "_verify_plan", lambda plan: None)

    with pytest.raises(ValueError, match="cannot run before selection"):
        root_cause.run_profile(
            argparse.Namespace(
                output_dir=str(tmp_path),
                split="validation",
                profile_id="control_bf16_checkpoint_tf32",
                gpu_ids=(0,),
            )
        )

    root_cause._write_json(tmp_path / "selection.json", _selection())
    monkeypatch.setattr(root_cause, "_verify_selection", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="profile differs from selection"):
        root_cause.run_profile(
            argparse.Namespace(
                output_dir=str(tmp_path),
                split="validation",
                profile_id="projection_fp32_only",
                gpu_ids=(0,),
            )
        )


def test_selection_requires_the_complete_development_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "plan.json").write_text("{}\n", encoding="utf-8")
    development = tmp_path / "development"
    development.mkdir()
    for profile in root_cause.ROOT_CAUSE_PROFILES[:-1]:
        (development / f"{profile.profile_id}.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(root_cause, "_verify_plan", lambda plan: None)
    monkeypatch.setattr(root_cause, "_verify_result", lambda *args, **kwargs: None)

    with pytest.raises(ValueError, match="matrix is incomplete"):
        root_cause.freeze_selection(argparse.Namespace(output_dir=str(tmp_path)))


def test_failed_validation_cannot_leave_a_stale_numeric_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "plan.json").write_text("{}\n", encoding="utf-8")
    root_cause._write_json(tmp_path / "selection.json", _selection())
    profile_id = "control_bf16_checkpoint_tf32"
    (tmp_path / "development").mkdir()
    (tmp_path / "validation").mkdir()
    development = {
        "result_hash": "result:1",
        "summary": {"status": "passed"},
    }
    validation = {
        "result_hash": "result:2",
        "status": "completed",
        "summary": {"status": "failed"},
    }
    root_cause._write_json(tmp_path / "development" / f"{profile_id}.json", development)
    root_cause._write_json(tmp_path / "validation" / f"{profile_id}.json", validation)
    (tmp_path / "frozen_numeric_contract.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(root_cause, "_verify_plan", lambda plan: None)
    monkeypatch.setattr(root_cause, "_verify_selection", lambda *args, **kwargs: None)
    monkeypatch.setattr(root_cause, "_verify_result", lambda *args, **kwargs: None)

    with pytest.raises(ValueError, match="stale contract"):
        root_cause.aggregate(argparse.Namespace(output_dir=str(tmp_path)))


def test_paired_contrast_reports_improvement_in_correct_direction() -> None:
    identity = {
        "job_id": "job:1",
        "task_id": "task:1",
        "task_type": "comparison",
        "state_id": "state:1",
        "record_id": "record:1",
        "gradient_seed": 7,
    }
    baseline = {
        "profile": {"profile_id": "control"},
        "rows": [
            {
                **identity,
                "full_gp_score": 0.2,
                "recomposed_gp_score": 0.196,
                "token_gradient_recomposition_relative_error": 0.04,
                "token_gradient_recomposition_cosine": 0.999,
            }
        ],
    }
    variant = {
        "profile": {"profile_id": "variant"},
        "rows": [
            {
                **identity,
                "full_gp_score": 0.2,
                "recomposed_gp_score": 0.199,
                "token_gradient_recomposition_relative_error": 0.01,
                "token_gradient_recomposition_cosine": 0.9999,
            }
        ],
    }

    contrast = root_cause._contrast_rows(baseline, variant, seed=3, replicates=20)

    assert contrast["paired_job_count"] == 1
    assert contrast["metrics"]["relative_error_reduction"]["mean"] > 0
    assert contrast["metrics"]["cosine_improvement"]["mean"] > 0
    assert contrast["metrics"]["gp_delta_reduction"]["mean"] > 0


class _ToyDecoder(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.embedding = nn.Embedding(7, 4)

    def forward(
        self,
        *,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        use_cache: bool,
    ) -> SimpleNamespace:
        del attention_mask, use_cache
        return SimpleNamespace(last_hidden_state=self.embedding(input_ids))


class _ToyCausalModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.decoder = _ToyDecoder()
        self.output = nn.Linear(4, 7, bias=False)

    def get_decoder(self) -> nn.Module:
        return self.decoder

    def get_output_embeddings(self) -> nn.Module:
        return self.output


def test_functional_call_path_preserves_trainable_gradient_flow() -> None:
    model = _ToyCausalModel()
    logits = root_cause._functional_sparse_logits(
        model,
        {
            "input_ids": torch.tensor([[1, 2, 3]], dtype=torch.long),
            "attention_mask": torch.ones((1, 3), dtype=torch.long),
        },
        torch.tensor([0, 2], dtype=torch.long),
        projection_dtype="float32",
    )
    assert logits.shape == (1, 2, 7)

    gradients = root_cause._autograd_gradients(model, logits.sum(), retain_graph=False)
    assert set(gradients) == {"decoder.embedding.weight", "output.weight"}
    assert all(torch.isfinite(value).all() for value in gradients.values())


def test_separate_forward_mode_uses_three_independent_forwards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def losses(*args: object, **kwargs: object) -> tuple[tuple[torch.Tensor, ...], tuple[int, ...]]:
        nonlocal calls
        calls += 1
        return (
            (
                torch.tensor(3.0, requires_grad=True),
                torch.tensor(2.0, requires_grad=True),
                torch.tensor(1.0, requires_grad=True),
            ),
            (2, 1, 1),
        )

    monkeypatch.setattr(root_cause, "_losses_for_record", losses)
    monkeypatch.setattr(
        root_cause,
        "_collect_trainable_gradients",
        lambda model: {"p": torch.tensor([float(calls)])},
    )

    class Model:
        def eval(self) -> None:
            return None

        def zero_grad(self, *, set_to_none: bool) -> None:
            assert set_to_none

    activated: list[object] = []

    def activate(model: object) -> int:
        activated.append(model)
        return 1

    monkeypatch.setattr(
        root_cause,
        "_activate_deterministic_eval_checkpointing",
        activate,
    )
    model = Model()
    output = root_cause._root_cause_decomposition(
        model,
        object(),
        object(),
        profile=root_cause._profile("checkpoint_on_separate_forward"),
        common_label_positions=(1,),
        differential_label_positions=(2,),
    )

    assert calls == 3
    assert activated == [model]
    assert output["full_loss"] == 3.0
    assert output["common_loss"] == 2.0
    assert output["differential_loss"] == 1.0
