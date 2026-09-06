"""Actual historical rows and local representation corruptions; zero Runtime execution."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.experiments.finance_qa_vnext_length_adaptation import (
    core,
    cpu,
    runner,
    source,
)
from trusted_synthesis.experiments.finance_qa_vnext_length_adaptation.controls import (
    reseal,
    run_controls,
)
from trusted_synthesis.experiments.finance_qa_vnext_length_adaptation.guards import (
    guard_report,
    zero_execution_guard,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import representation as old

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def actual():
    with zero_execution_guard() as counts:
        inputs = source.read_source(ROOT)
        binding_bytes = canonical_json_bytes(inputs["binding"])
        tokenizer = core.assets.load_tokenizer(inputs["binding"])
        condition = core.freeze_condition(inputs)
        tokens, comparison = core.encode(inputs, condition, tokenizer)
        yield inputs, tokenizer, condition, tokens, comparison
        assert canonical_json_bytes(inputs["binding"]) == binding_bytes
    assert guard_report(counts)["all_zero"]


def test_exact_published_source_anchor():
    anchor = source.source_anchor(ROOT)
    assert anchor["commit"] == source.PARENT_COMMIT
    assert anchor["file_count"] == 701
    assert anchor["byte_count"] == 74_982_278


def test_actual_position_authority_and_distinct_new_policy(actual):
    inputs, _, condition, _, _ = actual
    asset = core.asset_binding(inputs["binding"])
    assert asset["actual_max_position_embeddings"] == 32_768
    assert asset["actual_rope_scaling"] is None
    assert asset["tokenizer_declared_length_is_position_authority"] is False
    assert condition["maximum_sequence_length"] == 32_768
    assert inputs["binding"]["maximum_sequence_length"] == 24_576
    assert len(asset["members"]) == 5
    assert len(condition["candidate_ids"]) == 34
    assert len(condition["session_ids"]) == 2
    assert condition["tokenizer_asset_id"] == asset["id"]


def test_all_original_candidates_and_parent_bindings(actual):
    inputs, _, _, _, _ = actual
    checked = source.validate_candidates(inputs, inputs["dataset"]["rows"])
    assert len(checked["rows"]) == 34
    assert checked["qualification_recomputed"] is False
    assert {item["submission_kind"] for item in checked["rows"]} == {"action", "update", "final"}


def test_all_34_encode_with_old_32_arrays_identical_and_two_new_t16_arrays(actual):
    inputs, _, _, tokens, comparison = actual
    assert tokens["fit_count"] == 34 and tokens["not_fit_count"] == 0
    assert tokens["positive_representation_validated"] is True
    assert sum(item["arrays_identical"] is True for item in comparison["rows"]) == 32
    late = [item for item in comparison["rows"] if not item["old_consumable_arrays_existed"]]
    assert [item["sequence_length"] for item in late] == [24_885, 24_924]
    assert [item["new_headroom"] for item in late] == [7_883, 7_844]
    assert all(item["arrays_identical"] is None for item in late)
    assert all(
        item["input_ids"] is None
        for item in inputs["old_tokens"]["records"]
        if item["tokenrepresentation_status"] == "not_fit"
    )


def test_historical_public_api_reproduces_entire_old_dataset_exactly(actual):
    inputs, _, _, _, _ = actual
    recreated = old.tokenize_candidates(inputs["dataset"]["rows"], inputs["binding"])
    assert canonical_json_bytes(recreated) == canonical_json_bytes(inputs["old_tokens"])
    assert recreated["status"] == "contains_not_fit"
    assert recreated["fit_count"] == 32 and recreated["not_fit_count"] == 2


def test_complete_packages_are_17_separate_units_including_t16_and_final(actual):
    inputs, _, _, tokens, _ = actual
    packages = core.session_packages(inputs, tokens)
    assert packages["complete_session_packages"] == 2
    for package in packages["rows"]:
        assert package["expected_units"] == package["consumable_units"] == 17
        assert package["submission_kind_counts"] == {"action": 8, "update": 8, "final": 1}
        assert package["t16_present_and_consumable"] is True
        assert package["concatenated_conversation"] is False
        assert [item["display_turn"] for item in package["units"]] == list(range(1, 18))


@pytest.mark.parametrize("index", [15, 32])
def test_missing_t16_does_not_reduce_package_denominator(actual, index):
    inputs, _, _, tokens, _ = actual
    subset = reseal(
        tokens,
        "token_dataset",
        records=[item for i, item in enumerate(tokens["records"]) if i != index],
    )
    packages = core.session_packages(inputs, subset)
    assert packages["complete_session_packages"] == 1
    affected = next(item for item in packages["rows"] if not item["complete"])
    assert affected["expected_units"] == 17
    assert affected["consumable_units"] == 16
    assert affected["missing_or_nonconsumable_turns"] == [16]
    assert affected["units"][-1]["consumable"] is True


@pytest.mark.parametrize(
    "change", ["same_id_cap", "resealed_cap", "condition_cap", "condition_rope"]
)
def test_historical_identity_and_new_resource_policy_cannot_be_mixed(actual, change):
    inputs, _, condition, _, _ = actual
    changed = dict(inputs)
    if "cap" in change and change != "condition_cap":
        changed["binding"] = {**inputs["binding"], "maximum_sequence_length": 32_768}
        if change == "resealed_cap":
            changed["binding"] = core.assets.record(
                "tokenizer_binding",
                **{
                    k: v for k, v in changed["binding"].items() if k not in {"id", "schema_version"}
                },
            )
    else:
        fields = (
            {"maximum_sequence_length": 131_072}
            if change == "condition_cap"
            else {"rope_scaling": {"factor": 4}}
        )
        condition = reseal(condition, "condition", **fields)
    with pytest.raises(ProtocolError):
        core.validate_condition(condition, changed)


@pytest.mark.parametrize(
    "change", ["lower_position_cap", "rope_extension", "changed_template", "changed_software"]
)
def test_actual_asset_authority_is_checked_not_inferred_from_model_name(
    actual, monkeypatch, change
):
    inputs, _, _, _, _ = actual
    members, contents = core.assets._read_members(Path(inputs["binding"]["directory"]))
    contents = dict(contents)
    if change in {"lower_position_cap", "rope_extension"}:
        config = json.loads(contents["config.json"])
        config["max_position_embeddings" if change == "lower_position_cap" else "rope_scaling"] = (
            24_576 if change == "lower_position_cap" else {"factor": 4}
        )
        contents["config.json"] = canonical_json_bytes(config)
    elif change == "changed_template":
        config = json.loads(contents["tokenizer_config.json"])
        config["chat_template"] += "changed"
        contents["tokenizer_config.json"] = canonical_json_bytes(config)
    else:
        monkeypatch.setattr(core.assets, "_software_versions", lambda: {"changed": "version"})
    monkeypatch.setattr(core.assets, "_read_members", lambda directory: (members, contents))
    with pytest.raises(ProtocolError):
        core.asset_binding(inputs["binding"])


def test_all_registered_local_representation_controls(actual):
    inputs, tokenizer, condition, tokens, _ = actual
    controls = run_controls(inputs, condition, tokens, tokenizer)
    assert controls["control_count"] == 21
    assert controls["all_expected_outcomes"] is True
    assert controls["rows"][-1]["checked_records"] == 32


def test_small_dynamic_cpu_batches_cover_all_34_exactly_once(actual):
    inputs, tokenizer, condition, tokens, _ = actual
    report, binaries = cpu.build_batches(inputs, tokens, condition, tokenizer)
    assert report["batch_count"] == len(binaries) == 18
    assert report["loaded_records"] == 34
    assert report["maximum_observed_batch_sequence_length"] == 24_924
    assert report["all_tensors_cpu"] is True
    assert any(item["batch"]["padding_token_count"] > 0 for item in report["batches"])
    assert all(item["batch"]["shape"][0] <= 2 for item in report["batches"])
    assert report["training_stack_or_gpu_memory_feasibility_validated"] is False


@pytest.mark.parametrize(
    "change",
    [
        "label_suffix",
        "label_prompt",
        "mask_tail",
        "cross_session",
        "null_arrays",
        "wrong_condition",
    ],
)
def test_cpu_loader_rejects_corrupted_new_t16_records(actual, change):
    inputs, tokenizer, condition, tokens, _ = actual
    row = inputs["dataset"]["rows"][15]
    token = copy.deepcopy(tokens["records"][15])
    if change in {"label_suffix", "label_prompt"}:
        index = token["target_token_end"] if change == "label_suffix" else 1
        token["target_mask"][index] = 1
        token["labels"][index] = token["input_ids"][index]
    elif change == "mask_tail":
        token["labels"][token["target_token_end"] - 1] = -100
    elif change == "cross_session":
        token["session_id"] = inputs["sessions"][1]["id"]
    elif change == "null_arrays":
        token["input_ids"] = None
    else:
        token["representation_condition_id"] = "wrong-condition"
    token = reseal(token, "token_record")
    with pytest.raises(ProtocolError):
        cpu.collate([row], [token], condition, inputs["binding"], tokenizer)


def test_cpu_loader_does_not_splice_sessions_or_pad_all_rows_at_once(actual):
    inputs, tokenizer, condition, tokens, _ = actual
    for indices in ([0, 17], [0, 1, 2]):
        with pytest.raises(ProtocolError):
            cpu.collate(
                [inputs["dataset"]["rows"][i] for i in indices],
                [tokens["records"][i] for i in indices],
                condition,
                inputs["binding"],
                tokenizer,
            )


def test_manifest_cannot_ignore_changed_extra_or_missing_files(tmp_path):
    output = tmp_path / "output"
    store = runner.Store(output)
    store.json("record.json", {"value": 1})
    store.seal(test_only=True)
    runner.verify(output)
    (output / "record.json").write_bytes(b"changed")
    with pytest.raises(ProtocolError, match="manifest_bytes"):
        runner.verify(output)
    with pytest.raises(ProtocolError, match="already_exists"):
        runner.Store(output)


def test_actual_cli_prepare_run_and_readback(tmp_path):
    preparation, output = tmp_path / "preparation", tmp_path / "adaptation"
    command = [
        sys.executable,
        "-m",
        "trusted_synthesis.experiments.finance_qa_vnext_length_adaptation",
    ]
    for args in (
        ["prepare", "--root", str(ROOT), "--output", str(preparation)],
        ["run", "--root", str(ROOT), "--preparation", str(preparation), "--output", str(output)],
        ["verify", "--output", str(output)],
    ):
        result = subprocess.run(
            command + args, cwd=ROOT, capture_output=True, text=True, timeout=300
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["id"]
    report = source.load(output / "report.json")
    assert report["status"] == "complete"
    assert report["raw_candidates"] == report["consumable_records"] == 34
    assert report["complete_session_packages"] == 2
    assert report["historical_files_unchanged"] is True
    assert source.load(output / "execution_guards.json")["all_zero"] is True
    assert source.load(preparation / "execution_guards.json")["all_zero"] is True
    repeated = subprocess.run(
        command
        + ["run", "--root", str(ROOT), "--preparation", str(preparation), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert repeated.returncode != 0 and "adaptation_already_exists" in repeated.stderr
