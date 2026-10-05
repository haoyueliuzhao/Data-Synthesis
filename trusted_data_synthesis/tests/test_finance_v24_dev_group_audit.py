"""CPU/mock coverage for outcome encoding, complete groups and standardization."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/finqa_v24_dev_group_audit.py"
SPEC = importlib.util.spec_from_file_location("v24_dev_group_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def mock_evidence():
    models = {}
    for seed in audit.SEEDS:
        for arm in audit.ARMS:
            codes = "0123" if arm == "full" else "0000"
            models[f"seed{seed}/{arm}"] = {
                "outcome_codes": codes,
                "metrics": {
                    name: {
                        "unknown": 0,
                        "correct": 2 if arm == "full" else 0,
                        "complete_dataset_mean": 0.5 if arm == "full" else 0.0,
                    }
                    for name in audit.METRICS
                },
            }
    return {"dev_task_keys": ["a", "b", "c", "d"], "models": models}


def test_decode_two_bit_codes_and_reject_changed_code_or_missing_question():
    evidence = mock_evidence()
    _, decoded = audit.decode_evidence(evidence, list("abcd"), 4)
    assert decoded["seed11/full"]["execution_accuracy"] == [0, 1, 0, 1]
    assert decoded["seed11/full"]["program_accuracy"] == [0, 0, 1, 1]
    evidence["models"]["seed11/full"]["outcome_codes"] = "0124"
    with pytest.raises(ValueError, match="invalid outcome code"):
        audit.decode_evidence(evidence, list("abcd"), 4)
    evidence = mock_evidence()
    evidence["dev_task_keys"] = list("abc")
    with pytest.raises(ValueError, match="roster"):
        audit.decode_evidence(evidence, list("abcd"), 4)


def test_reject_tampered_aggregate_and_public_roster():
    evidence = mock_evidence()
    evidence["models"]["seed29/full"]["outcome_codes"] = "0000"
    with pytest.raises(ValueError, match="aggregate changed"):
        audit.decode_evidence(evidence, list("abcd"), 4)
    with pytest.raises(ValueError, match="roster mismatch"):
        audit.decode_evidence(mock_evidence(), list("abcx"), 4)


def test_paired_counts_equal_seed_mean_do_not_inflate_question_denominator():
    vectors = {"11": [1, 0, -1], "29": [1, 1, 0], "47": [-1, -1, 0]}
    result = audit.paired_summary(vectors, [0, 1, 2])
    assert result["n_questions"] == 3
    assert result["by_seed"]["11"] == {
        "n": 3,
        "wins": 1,
        "losses": 1,
        "ties": 1,
        "mean_difference": 0,
    }
    assert result["equal_seed_mean_difference"] == 0
    assert result["pooled_repeated_pairs"] == {
        "n": 9,
        "wins": 3,
        "losses": 3,
        "ties": 3,
        "independent_question_count": 3,
    }


def test_leave_large_report_uses_actual_remaining_denominator_and_all_groups():
    vectors = {str(seed): [-1] * 8 + [1, 1] for seed in audit.SEEDS}
    result = audit.leave_one_group(vectors, {"large": list(range(8)), "small": [8, 9]}, 10)
    assert result["all_leave_one_groups"]["large"]["remaining_n"] == 2
    assert result["all_leave_one_groups"]["large"]["mean_difference"]["11"] == 1
    assert result["summary"]["equal_seed_mean"]["range"] == [-1, 1]
    assert result["summary"]["equal_seed_mean"]["sign_flip_groups"] == ["large"]
    assert result["summary"]["equal_seed_mean"]["max_absolute_change"] == pytest.approx(1.6)
    singleton = audit.leave_one_group(vectors, {"all": list(range(10))}, 10)
    assert singleton["summary"]["11"]["range"] is None
    assert singleton["summary"]["11"]["undefined_groups"] == ["all"]


def test_common_support_reweights_target_mass_never_zero_fills_unseen_cells():
    vectors = {str(seed): [1, 1, -1] for seed in audit.SEEDS}
    features = {
        "ta": {"intent_proxy": "A"},
        "tb": {"intent_proxy": "B"},
        "tz": {"intent_proxy": "Z"},
    }
    result = audit.standardize(
        vectors, {"A": [0, 1], "B": [2]}, ["ta", "tb", "tb", "tz"], features, "intent_proxy"
    )
    assert result["target_coverage_fraction"] == 0.75
    assert result["dev_coverage_fraction"] == 1
    assert result["target_missing_in_dev_categories"] == ["Z"]
    assert result["normalized_target_weights_on_H"] == {"A": 1 / 3, "B": 2 / 3}
    assert result["by_seed"]["equal_seed_mean"][
        "standardized_mean_difference_on_H"
    ] == pytest.approx(-1 / 3)
    assert result["by_seed"]["equal_seed_mean"][
        "unweighted_dev_mean_difference_on_H"
    ] == pytest.approx(1 / 3)
    assert result["target_n_records"] == 4 and result["target_unique_task_keys"] == 3
    missing = audit.standardize(vectors, {"A": [0, 1], "B": [2]}, ["tz"], features, "intent_proxy")
    assert missing["target_coverage_fraction"] == 0
    assert missing["by_seed"]["equal_seed_mean"]["standardized_mean_difference_on_H"] is None
    assert missing["by_seed"]["11"]["unweighted_full_dev_mean_difference"] == pytest.approx(1 / 3)


def test_all_fixed_dimensions_categories_metrics_comparisons_retained():
    features = {
        key: {dimension: ("A" if key in "ab" else "unknown") for dimension in audit.DIMENSIONS}
        for key in "abcd"
    }
    result = audit.analyze(
        mock_evidence(), features, {"dev883": list("abcd"), "train744": list("abc")}, expected_n=4
    )
    assert result["confidence_intervals"] is None and result["p_values"] is None
    for metric in audit.METRICS:
        assert set(result["metric_results"][metric]) == set(audit.COMPARISONS)
        for comparison in result["metric_results"][metric].values():
            assert set(comparison["groups"]) == set(audit.DIMENSIONS)
            assert set(comparison["groups"]["intent_proxy"]) == {"A", "unknown"}
    assert result["grouping_size_diagnostics"]["intent_proxy"]["unknown_category_counts"] == {
        "unknown": 2
    }


def test_frozen_minimum_counts_flag_small_group_effects_and_restrict_support():
    features = {
        key: {dimension: ("A" if key in "abc" else "B") for dimension in audit.DIMENSIONS}
        for key in "abcd"
    }
    result = audit.analyze(
        mock_evidence(),
        features,
        {"dev883": list("abcd"), "train744": list("abcd")},
        expected_n=4,
        minimum_support_tasks=2,
    )
    comparison = result["metric_results"]["execution_accuracy"]["Full-Static"]
    assert comparison["groups"]["intent_proxy"]["B"]["n_questions"] == 1
    assert (
        comparison["groups"]["intent_proxy"]["B"]["descriptive_small_group_no_efficacy_claim"]
        is True
    )
    assert "by_seed" in comparison["groups"]["intent_proxy"]["B"]
    assert comparison["groups"]["intent_proxy"]["A"]["n_questions"] == 3
    standardized = comparison["common_support_standardization"]["intent_proxy"]["train744"]
    assert standardized["common_support_H"] == ["A"]
    assert standardized["target_categories_below_minimum_dev_group_tasks"] == ["B"]
    assert standardized["target_coverage_fraction"] == 0.75
    assert standardized["dev_coverage_fraction"] == 0.75
    assert standardized["mathematical_positive_common_support"]["dev_coverage_fraction"] == 1


def test_persist_refuses_overwrite(tmp_path):
    path = tmp_path / "audit.json"
    audit.persist(path, {"frozen": True})
    audit.persist(path, {"frozen": True})
    with pytest.raises(ValueError, match="immutable"):
        audit.persist(path, {"frozen": False})


def test_invalid_protocol_blocks_first_outcome_access(monkeypatch, tmp_path):
    calls = []

    def reader(path):
        calls.append(Path(path).name)
        assert Path(path).name == "grouping_protocol.json", (
            "must not read outcomes or features after invalid freeze"
        )
        return {"id": "tampered"}, {}

    monkeypatch.setattr(audit, "read_json", reader)
    monkeypatch.setattr("sys.argv", ["audit", "--audit-root", str(tmp_path)])
    with pytest.raises(ValueError, match="protocol content ID"):
        audit.main()
    assert calls == ["grouping_protocol.json"]
