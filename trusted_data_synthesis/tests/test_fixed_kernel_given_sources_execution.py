"""New decoder-interface, matrix and descriptive-utility controls only."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
execution = importlib.import_module("fixed_kernel_given_sources_execution_20260915")
coordinator = importlib.import_module("run_fixed_kernel_given_sources_20260915")
p = execution.p


def test_same_callback_path_is_explicitly_synthetic_in_CPU_control(tmp_path):
    text = '{"final":{"value":"5","unit":"USD","result_id":"tool:1"}}'

    class Model:
        training = False

        def requires_grad_(self, enabled):
            assert enabled is False

        def eval(self):
            self.training = False

        def generate(self, **kwargs):
            assert kwargs["max_new_tokens"] == 2048 and kwargs["do_sample"] is False
            assert "past_key_values" not in kwargs
            return [kwargs["input_ids"][0] + [8, 99]]

    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            assert (
                messages[0]["content"] == execution.views.SYSTEM + "\nRequested guidance: neutral"
            )
            return "synthetic"

        def __call__(self, text, **kwargs):
            assert kwargs["truncation"] is False
            return {"input_ids": [1, 2], "attention_mask": [1, 1]}

        def decode(self, tokens, **kwargs):
            return text + ("<eos>" if tokens[-1] == 99 else "")

    config = p.record(
        "given_sources_decoder_config",
        source_view_manifest_id="synthetic_view",
        eos_token_ids=[99],
        pad_token_id=0,
        bos_token_id=None,
    )
    identity = p.record(
        "given_sources_model_identity",
        model_kind="unfinetuned_base",
        checkpoint_id="synthetic_base",
        decoder_config_id=config["id"],
        surface_manifest_id="synthetic_view",
    )
    receipt = p.record(
        "model_load_receipt",
        model_identity_id=identity["id"],
        restored_checkpoint_id="synthetic_base",
        execution_kind=execution.original.CONTROL,
        model_weight_loads=0,
        tokenizer_loads=0,
        final_adapter_loads=0,
        GPU_loads=0,
    )
    decoder = execution.Decoder(
        Model(), Tokenizer(), identity, tmp_path / "decoder", config, receipt, control=True
    )
    context = {
        "identity": {"parent_manifest_id": "synthetic_view"},
        "response_index": 0,
        "max_responses": 32,
        "max_tools": 32,
        "remaining_tool_calls": 32,
        "history_must_not_be_truncated": True,
    }
    result = decoder(
        [
            {"role": "system", "content": execution.views.SYSTEM + "\nRequested guidance: neutral"},
            {"role": "user", "content": "synthetic public task"},
        ],
        context,
    )
    assert result["raw_response"] == text
    assert decoder.counters["synthetic_model_generation_calls"] == 1
    assert (
        decoder.counters["actual_model_generation_calls"]
        == decoder.counters["actual_GPU_generation_calls"]
        == 0
    )


def test_resource_admission_and_strict_direction_rules():
    rows = coordinator.available(
        "0, a, 61440, 100\n1, b, 61439, 0\n2, c, 80000, 0", ("a", "b", "c"), used=("c",)
    )
    assert [row["uuid"] for row in rows] == ["a"]
    assert coordinator.MAX_CALLS == 10 * 180 * 32 == 57600
    assert (
        coordinator.choose_direction({"alpha0": "1/3", "plus": "1/3", "minus": "1/4"}) == "alpha0"
    )
    assert (
        coordinator.choose_direction({"alpha0": "0", "plus": "1/180", "minus": "1/180"}) == "plus"
    )
    assert (
        coordinator.choose_direction({"alpha0": "0", "plus": "1/180", "minus": "1/90"}) == "minus"
    )


def test_full_fixed_denominator_reporting_and_missing_cell_rejection(tmp_path):
    tasks = [
        {"task_id": group + str(index), "group": group, "source_cluster": "synthetic_source"}
        for group in coordinator.GROUPS
        for index in range(60)
    ]
    models = [
        {
            "key": "unfinetuned_base",
            "model_kind": "unfinetuned_base",
            "checkpoint_id": "synthetic_base",
            "original_model_identity": None,
        }
    ]
    models += [
        {
            "key": f"A_{arm}_{seed}",
            "model_kind": "finetuned",
            "checkpoint_id": f"synthetic_{arm}_{seed}",
            "original_model_identity": {"arm": arm, "seed": seed},
        }
        for seed in (11, 29, 47)
        for arm in ("alpha0", "plus", "minus")
    ]
    plan = p.record(
        "given_sources_value_plan",
        models=models,
        tasks=tasks,
        source_view_manifest_id="synthetic_view",
        training_lineage_note="synthetic report-only CPU control, no models executed",
    )
    p.write_once(tmp_path / coordinator.OUTPUT / "started.json", {"at": "synthetic"})
    (tmp_path / coordinator.SUMMARY).parent.mkdir(parents=True)
    for index, model in enumerate(models):
        old = model["original_model_identity"]
        outcomes = []
        for task in tasks:
            valid = bool(old and old["arm"] in {"plus", "minus"} and task["task_id"].endswith("0"))
            outcomes.append(
                {
                    **task,
                    "financial_valid": valid,
                    "quantity_status": "PASS" if valid else "UNDETERMINED",
                    "support_status": "PASS" if valid else "UNDETERMINED",
                    "actual_method": "synthetic",
                    "reason": None if valid else "no_final",
                    "diagnostics": dict.fromkeys(
                        (
                            "numeric_read",
                            "successful_calculation",
                            "recognized_Final",
                            "tool_error",
                            "context_rejected",
                        ),
                        valid,
                    ),
                }
            )
        generated = p.record(
            "given_sources_generation_report",
            actual_complete=True,
            plan_id=plan["id"],
            checkpoint_id=model["checkpoint_id"],
            process_id=index,
            elapsed_seconds=0,
            GPU_peak_memory={"reserved_bytes": 0},
            resource_usage=dict.fromkeys(
                (
                    "actual_model_generation_calls",
                    "generated_tokens",
                    "context_rejections",
                    "model_weight_loads",
                    "final_adapter_loads",
                ),
                0,
            ),
            synthetic_reporting_control=True,
        )
        score = p.record(
            "given_sources_assessment_report",
            actual_complete=True,
            plan_id=plan["id"],
            generation_report_id=generated["id"],
            process_id=index + 100,
            outcomes=outcomes,
            synthetic_reporting_control=True,
        )
        folder = tmp_path / coordinator.OUTPUT / "workers" / model["key"]
        p.write_once(folder / "report.json", generated)
        p.write_once(folder / "assessment.json", score)
    report = coordinator.summarize(tmp_path, plan, p)
    assert report["full_sessions"] == 1800 and report["unique_tasks"] == 180
    assert report["selected_direction"] == "plus"
    assert report["effects"]["SFT_alpha0_minus_base"] == "0"
    assert report["effects"]["pi_plus_minus_alpha0"] == "1/10"
    assert report["B_training_authorized_or_started"] is False
    assert all(row["total"] == 180 for row in report["models"])
    # A missing registered model receipt is an error, not a smaller zero-scored panel.
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    with pytest.raises(FileNotFoundError):
        coordinator.summarize(incomplete, plan, p)
