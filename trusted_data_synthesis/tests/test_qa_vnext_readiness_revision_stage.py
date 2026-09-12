"""Successor admission is evidence-derived; old failed artifacts are not patched."""

import copy
import hashlib

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_readiness_revision import (
    protocol,
    provenance,
    stage,
)


def inputs():
    prep = {
        "evaluation_tasks": 900,
        "panel_quota_complete": True,
        "evaluation_panel_rebuilds": 0,
        "training_candidates": 243,
        "new_training_candidates": 0,
        "balanced_reference_supply_ceiling": 180,
        "all_new_registered_targets_retained": True,
        "old_243_public_bytes_preserved": True,
        "qualification": {
            "status": "PASS",
            "control_count": 70,
            "passed_count": 70,
            "prior_positive_regressions": [],
            "prior_negative_regressions": [],
            "prior_15_reached_support_assessment": 15,
            "financial_valid_count": 54,
            "inherited_CPU": {
                "verified": True,
                "packages": 39,
                "rows": 253,
                "target_tokens": 13642,
            },
            "incremental_CPU": {
                "financial_complete_packages": 15,
                "status": "PASS_SCRIPTED_REPRESENTATION_ONLY",
                "tokenizer_constructions": 1,
                "rows": 100,
            },
            "token_combined": {
                "all_current_qualified_covered": True,
                "financial_complete_packages": 54,
                "inherited_rows": 253,
                "new_rows": 100,
                "maxseq": 24576,
                "truncation": False,
                "old_rows_reencoded": 0,
            },
        },
    }
    observed = {"panels": {"status": "PASS_AS_SCOPED"}, "increment": {"status": "passed"}}
    frozen = {
        "new_test_result": {"return_code": 0},
        "inherited_transport_and_consumer_control_evidence": {
            "new_test_result": {"return_code": 0},
            "unchanged_implementation_verified": True,
        },
    }
    return prep, observed, frozen


def test_empty_qualified_UNP_increment_not_a_new_hard_gate():
    assert all(stage.admission_checks(*inputs()).values())


@pytest.mark.parametrize(
    "path,value",
    [
        (("evaluation_tasks",), 899),
        (("panel_quota_complete",), False),
        (("evaluation_panel_rebuilds",), 1),
        (("balanced_reference_supply_ceiling",), 175),
        (("all_new_registered_targets_retained",), False),
        (("old_243_public_bytes_preserved",), False),
        (("qualification", "status"), "FAIL"),
        (("qualification", "control_count"), 69),
        (("qualification", "passed_count"), 55),
        (("qualification", "prior_positive_regressions"), ["old_positive"]),
        (("qualification", "prior_negative_regressions"), ["old_negative"]),
        (("qualification", "prior_15_reached_support_assessment"), 14),
        (("qualification", "financial_valid_count"), 39),
        (("qualification", "inherited_CPU", "verified"), False),
        (("qualification", "inherited_CPU", "rows"), 254),
        (("qualification", "inherited_CPU", "target_tokens"), 13643),
        (("qualification", "incremental_CPU", "status"), "FAIL"),
        (("qualification", "incremental_CPU", "tokenizer_constructions"), 2),
        (("qualification", "incremental_CPU", "financial_complete_packages"), 16),
        (("qualification", "token_combined", "all_current_qualified_covered"), False),
        (("qualification", "token_combined", "financial_complete_packages"), 53),
        (("qualification", "token_combined", "inherited_rows"), 0),
        (("qualification", "token_combined", "new_rows"), 99),
        (("qualification", "token_combined", "maxseq"), 49152),
        (("qualification", "token_combined", "truncation"), True),
        (("qualification", "token_combined", "old_rows_reencoded"), 253),
    ],
)
def test_actual_admission_defect_cannot_be_covered_by_PASS_label(path, value):
    prep, observed, frozen = inputs()
    item = prep
    for key in path[:-1]:
        item = item[key]
    item[path[-1]] = value
    assert not all(stage.admission_checks(prep, observed, frozen).values())


@pytest.mark.parametrize("which", ["panels", "increment"])
def test_source_or_inherited_panel_failure_blocks(which):
    prep, observed, frozen = inputs()
    observed[which]["status"] = "FAIL"
    assert not all(stage.admission_checks(prep, observed, frozen).values())


def test_no_new_CPU_packages_can_pass_representation_but_not_fixed_qualification():
    prep, observed, frozen = inputs()
    q = prep["qualification"]
    q["financial_valid_count"] = 39
    q["passed_count"] = 55
    q["prior_15_reached_support_assessment"] = 0
    q["incremental_CPU"].update(
        financial_complete_packages=0,
        status="NO_FINANCIAL_COMPLETE_PACKAGES",
        tokenizer_constructions=0,
        rows=0,
    )
    q["token_combined"].update(financial_complete_packages=39, new_rows=0)
    checks = stage.admission_checks(prep, observed, frozen)
    assert checks["new_original_CPU_representation_passed"]
    assert not checks["complete_trajectory_qualification_passed"]


def old_code_fixture(tmp_path):
    originals, pins = {}, []
    for index, name in enumerate((*protocol.CHANGED_PARENT_CODE, "unrelated/unchanged.py")):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        original = ("original " + str(index)).encode()
        path.write_bytes(original)
        originals[name] = original
        pins.append({"path": name, "sha256": hashlib.sha256(original).hexdigest()})
    return {"git_commit": protocol.PARENT_CODE, "code": pins}, originals


def test_old_code_verified_at_original_commit_only_for_registered_changes(tmp_path):
    frozen, originals = old_code_fixture(tmp_path)
    changed = protocol.CHANGED_PARENT_CODE[0]
    (tmp_path / changed).write_bytes(b"corrected consumer")
    requests = []

    def reader(commit, name):
        requests.append((commit, name))
        return originals[name]

    proof = provenance.check_original_code(tmp_path, frozen, git_reader=reader)
    assert requests == [(protocol.PARENT_CODE, changed)]
    assert proof["original_dependency_hash_checks_disabled"] is False
    assert len(proof["changed_registered_consumers"]) == 1


def test_unregistered_old_dependency_change_rejected(tmp_path):
    frozen, originals = old_code_fixture(tmp_path)
    (tmp_path / "unrelated/unchanged.py").write_bytes(b"not permitted")
    with pytest.raises(ValueError, match="unregistered_old_dependency_change"):
        provenance.check_original_code(tmp_path, frozen, git_reader=lambda _, p: originals[p])


def test_wrong_historical_Git_bytes_rejected(tmp_path):
    frozen, _ = old_code_fixture(tmp_path)
    (tmp_path / protocol.CHANGED_PARENT_CODE[0]).write_bytes(b"new consumer")
    with pytest.raises(ValueError, match="original_Git_blob_matches_old_freeze"):
        provenance.check_original_code(tmp_path, frozen, git_reader=lambda *_: b"wrong old bytes")


def test_finite_policy_keeps_old_scientific_denominators_and_common_caps():
    rule = protocol.policy()
    assert rule["panel_rebuilds"] == rule["original_rows_reencoded"] == 0
    assert rule["fixed_prior_source_controls"] == 70
    assert rule["unchanged_expected_positive_controls"] == 54
    assert rule["unchanged_expected_negative_controls"] == 16
    assert rule["source_increment"]["new_task_cap"] == 17
    assert rule["shared_new_rewrite_requests"] == 34
    assert rule["shared_new_rewrite_token_cap"] == 330752
    assert rule["global_token_cap"] == 1000000000
    assert rule["no_UNP_positive_yield_hard_gate"]


def test_failed_new_or_inherited_contract_tests_block_transport_and_consumer():
    for location in ("new", "inherited"):
        prep, observed, frozen = copy.deepcopy(inputs())
        target = (
            frozen
            if location == "new"
            else frozen["inherited_transport_and_consumer_control_evidence"]
        )
        target["new_test_result"]["return_code"] = 1
        checks = stage.admission_checks(prep, observed, frozen)
        assert not checks["live_transport_controls_passed"]
        assert not checks["original_package_consumer_registered"]
        assert not checks["complete_trajectory_qualification_passed"]
