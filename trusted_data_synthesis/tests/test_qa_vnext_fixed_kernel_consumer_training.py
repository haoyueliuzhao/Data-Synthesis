"""Complete 400-update CPU integration on explicitly synthetic original rows."""

from collections import Counter

import pytest
import torch
from test_qa_vnext_fixed_kernel_consumer import TinyStudent
from test_qa_vnext_fixed_kernel_distribution import catalog, outcomes_for

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import distribution as d
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import population as pop
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import training as t


@pytest.fixture(scope="module")
def admitted_inputs():
    selected = pop.make_population(catalog())
    registry = pop.make_registry(selected, "synthetic_precommitted_freeze", p.ORDER_SEED)
    outcomes = []
    for item in outcomes_for(registry, selected, dual_count=60):
        fields = {key: value for key, value in item.items() if key not in ("id", "schema_version")}
        if "original_package" in fields:
            original_fields = {
                key: value
                for key, value in fields["original_package"].items()
                if key not in ("id", "schema_version")
            }
            original_fields.update(
                original_request_response_bytes_retained=True,
                errors=[],
                truncation=False,
                maximum_sequence_length=24576,
                tokenizer_binding_id="synthetic_tokenizer",
            )
            fields["original_package"] = p.record("encoded_original_package", **original_fields)
            fields["state_id"] = d.canonical_state_id(
                fields["actual_method"], original_fields["full_class"]
            )
        outcomes.append(p.record("material_outcome", **fields))
    kernel = d.build_kernel(selected, registry, outcomes)
    return selected, registry, outcomes, kernel


def test_complete_material_verification_retains_unequal_original_budgets(admitted_inputs):
    selected, registry, outcomes, kernel = admitted_inputs
    result = t.validate_materials(kernel, selected, registry, outcomes)
    assert result["fixed_tasks"] == 200
    assert result["training_retokenizations"] == 0
    assert result["heldout_NLL_or_generation"] is False
    for pool in p.POOLS:
        budget = result["pool_budgets"][pool]
        assert budget["packages_per_epoch"] != 40 * 64
        assert budget["packages_all_epochs"] == 10 * budget["packages_per_epoch"]
        assert budget["target_tokens_all_epochs"] == 10 * budget["target_tokens_per_epoch"]


def test_all_arms_have_identical_original_bytes_and_physical_order(admitted_inputs):
    selected, registry, outcomes, kernel = admitted_inputs
    physical = []
    coefficients = []
    for arm in p.ARMS:
        examples = d.weighted_packages(kernel, "A", arm)
        physical.append(
            [
                (
                    item["package_id"],
                    item["original_package_sha256"],
                    p.sha(p.encode(item["rows"])),
                    item["whole_package_target_tokens"],
                )
                for item in examples
            ]
        )
        coefficients.append([item["target_token_coefficient"] for item in examples])
    assert physical[0] == physical[1] == physical[2]
    assert coefficients[0] != coefficients[1] != coefficients[2]


def test_complete_400_update_cpu_run_uses_every_package_ten_times(admitted_inputs, tmp_path):
    selected, registry, outcomes, kernel = admitted_inputs
    release = t.make_release(
        kernel,
        study_freeze_id="synthetic_freeze",
        surface_manifest_id="synthetic_surface",
        allowed_runs=[{"pool": "A", "arm": "plus", "seed": 11}],
    )

    def synthetic_loader(binding, seed, config, trainable):
        assert config == t.training_config() and trainable is True and seed == 11
        return TinyStudent(), {"synthetic_only": True}

    threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        report = t.run(
            tmp_path,
            tmp_path / "cpu_run",
            kernel,
            selected,
            registry,
            outcomes,
            {"id": "synthetic_checkpoint_binding"},
            release,
            pool="A",
            arm="plus",
            seed=11,
            model_loader=synthetic_loader,
        )
    finally:
        torch.set_num_threads(threads)
    assert report["status"] == "COMPLETE_SYNTHETIC_CHECKPOINT"
    assert report["actual_complete"] is False
    assert report["optimizer_updates"] == len(report["updates"]) == 400
    assert report["epochs_completed"] == 10
    assert report["intermediate_checkpoints"] == 0
    assert report["training_retokenizations"] == 0
    assert report["final_adapter_restored_identity_verified"] is True
    seen = Counter()
    package_counts = set()
    for update in report["updates"]:
        value = p.read_json(tmp_path / update["path"])
        seen.update(row["package_id"] for row in value["packages"])
        package_counts.add(value["physical_package_count"])
        assert value["optimizer_step_calls"] == value["clip_calls"] == value["zero_grad_calls"] == 1
    assert set(seen) == {
        item["package_id"] for item in kernel["train_packages"] if item["pool"] == "A"
    }
    assert set(seen.values()) == {10}
    assert len(package_counts) > 1 and 64 not in package_counts


def test_release_cannot_add_an_unselected_run(admitted_inputs):
    *_, kernel = admitted_inputs
    release = t.make_release(
        kernel,
        study_freeze_id="test",
        surface_manifest_id="surface",
        allowed_runs=[{"pool": "A", "arm": "alpha0", "seed": 11}],
    )
    with pytest.raises(ValueError, match="explicitly_released"):
        t.validate_release(release, kernel, pool="B", arm="plus", seed=11)


def test_kernel_gate_cannot_be_forged_by_rehashing_truncated_outcomes(admitted_inputs):
    selected, registry, outcomes, kernel = admitted_inputs
    with pytest.raises(ValueError, match="denominator"):
        t.validate_materials(kernel, selected, registry, outcomes[:-1])
