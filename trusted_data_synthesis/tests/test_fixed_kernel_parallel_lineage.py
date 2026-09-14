"""Small metadata-only mixed-backend controls; no files or model execution."""

import copy

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import evaluation as e
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    parallel_lineage as lineage,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


@pytest.fixture
def binding(monkeypatch):
    base = lineage._base_training_config()
    fields = {key: value for key, value in base.items() if key not in {"id", "schema_version"}}
    tail = p.record(
        "training_configuration",
        **{
            **fields,
            "execution_design": "synthetic_parallel_tail",
            "parent_trajectory_training_configuration_id": base["id"],
        },
    )
    monkeypatch.setattr(lineage, "_base_training_config", lambda: base)
    monkeypatch.setattr(lineage, "_tail_training_config", lambda: tail)
    return {
        "study_freeze_id": "synthetic_original_study",
        "surface_manifest_id": "synthetic_unchanged_surface",
        "kernel_id": "synthetic_original_kernel",
        "training_configuration_id": base["id"],
        "decoder_config_id": "synthetic_unchanged_decoder",
    }


def report(binding, key):
    checkpoint = "synthetic_checkpoint_" + "_".join(map(str, key))
    return p.record(
        "training_report",
        **{
            name: value
            for name, value in binding.items()
            if name not in {"decoder_config_id", "training_configuration_id"}
        },
        training_configuration_id=lineage.expected_training_config(*key)["id"],
        pool=key[0],
        arm=key[1],
        seed=key[2],
        status="COMPLETE_FINAL_CHECKPOINT",
        actual_complete=True,
        checkpoint_id=checkpoint,
        final_adapter={
            "path": "final_adapter.safetensors",
            "bytes": 128,
            "sha256": "a" * 64,
            "parameter_digest": checkpoint,
        },
        final_adapter_restored_identity_verified=True,
        adapter_directory="historical_source/training/" + "_".join(map(str, key)),
    )


def replace_record(value, **changes):
    return p.record(
        value["schema_version"].split(".")[-1],
        **{
            **{key: item for key, item in value.items() if key not in {"id", "schema_version"}},
            **changes,
        },
    )


def test_mixed_expected_configs_keep_eight_original_reports_and_aggregate_binding(binding):
    keys = [("A", arm, seed) for arm in p.ARMS for seed in p.SEEDS]
    reports = [report(binding, key) for key in keys]
    original_bytes = [p.encode(value) for value in reports]
    found = e._analysis_training(reports, keys, binding)
    assert [p.encode(value) for value in reports] == original_bytes
    assert all(found[key] is value for key, value in zip(keys, reports, strict=True))
    assert len({value["training_configuration_id"] for value in reports}) == 2
    actual = lineage.execution_lineage(reports)
    assert actual["scientific_training_configuration_id"] == binding["training_configuration_id"]
    assert actual["heterogeneous_execution"]
    assert not actual["old_training_report_bytes_rewritten"]
    assert not actual["bitwise_gradient_or_optimizer_equivalence_claimed"]
    assert sum(row["parallel_tail"] for row in actual["actual_training_reports"]) == 1
    ids = lineage.configuration_ids()
    assert ids["A_minus_47"] != ids["B_minus_47"] == binding["training_configuration_id"]


def test_mislabeled_tail_foreign_config_and_wrong_run_are_rejected(binding):
    base_id = binding["training_configuration_id"]
    tail_id = lineage.expected_training_config(*lineage.TAIL)["id"]
    for key, wrong_config in (
        (lineage.TAIL, base_id),
        (("B", "minus", 47), tail_id),
        (("A", "plus", 11), "foreign_configuration"),
    ):
        wrong = replace_record(report(binding, key), training_configuration_id=wrong_config)
        with pytest.raises(ValueError, match="exact_actual_configuration"):
            e._analysis_training([wrong], [key], binding)
    with pytest.raises(ValueError, match="explicit_run"):
        lineage.validate_binding(
            report(binding, lineage.TAIL), binding, pool="B", arm="minus", seed=47
        )


def test_tail_model_identity_and_score_join_use_true_config_and_original_report_id(binding):
    training = report(binding, lineage.TAIL)
    identity = p.record(
        "model_identity",
        **{**binding, "training_configuration_id": training["training_configuration_id"]},
        pool="A",
        arm="minus",
        seed=47,
        checkpoint_id=training["checkpoint_id"],
        training_report_id=training["id"],
        final_adapter=training["final_adapter"],
        adapter_directory="copied_output/training/A_minus_47",
        base_binding_id="synthetic_base",
        tokenizer_binding_id="synthetic_tokenizer",
    )
    assert e.validate_model_identity(identity) is identity
    assert identity["adapter_directory"] != training["adapter_directory"]
    task = {
        "task_id": "synthetic_task",
        "group": "dual_sufficient",
        "source_cluster": "cik:0000000001",
        "surface_version_id": "synthetic_surface",
        "public_messages_sha256": "b" * 64,
    }
    score = p.record(
        "evaluation_report",
        **e._binding(identity),
        model_identity_id=identity["id"],
        actual_complete=True,
        status="COMPLETE_FIXED_EVALUATION",
        split="dev",
        outcomes=[{**task, "financial_valid": True}],
    )
    result = e._analysis_scores(
        [score], {lineage.TAIL: training}, [lineage.TAIL], [task], "dev", binding
    )
    assert result[lineage.TAIL][0]["training_report_id"] == training["id"]
    before = copy.deepcopy(training)
    for field, value in (
        ("training_configuration_id", binding["training_configuration_id"]),
        ("kernel_id", "foreign_kernel"),
    ):
        altered = replace_record(score, **{field: value})
        with pytest.raises(ValueError, match="exact_actual_configuration"):
            e._analysis_scores(
                [altered], {lineage.TAIL: training}, [lineage.TAIL], [task], "dev", binding
            )
    assert training == before
