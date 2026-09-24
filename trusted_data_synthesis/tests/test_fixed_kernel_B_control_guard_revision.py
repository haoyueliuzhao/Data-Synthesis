"""CPU-only admission tests; no material, model, or distribution recomputation."""

import copy
import importlib
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
revision = importlib.import_module("fixed_kernel_B_control_guard_20260924")
original = importlib.import_module("fixed_kernel_B_training_worker_20260922")
p = revision.p


@pytest.fixture
def case(tmp_path, monkeypatch):
    prior = {"control": {"x": "2/5", "y": "3/5"}, "target": {"x": "1/2", "y": "1/2"}}
    plan = dict(
        id="registered_B", materials=dict(binding=dict(prior=prior, control_tasks=["control"]))
    )
    job = dict(key="B_delayed_c_11", condition="delayed_c")
    prefix = dict(prefix_checkpoint_sha256="prefix_sha", prefix_snapshot_id="prefix_snapshot")
    updated = p.record(
        "anchored_sources_distribution_step",
        pi_next={"control": {"x": 0.4, "y": 0.6}, "target": {"x": 0.7, "y": 0.3}},
    )
    report = dict(
        plan_id=plan["id"],
        job_key=job["key"],
        **prefix,
        numeric_guard_passed=True,
        distribution_update_id=updated["id"],
    )
    directory = tmp_path / "outer" / job["key"]
    p.write_once(directory / "numeric_guard.json", dict(passed=True))
    records = {
        "report.json": report,
        "distribution_update.json": updated,
        "numeric_guard.json": dict(passed=True),
    }
    monkeypatch.setattr(p, "read_json", lambda path: records[Path(path).name])
    return SimpleNamespace(RAW=tmp_path), plan, job, prefix, records


def replace_pi(case, pi):
    records = case[-1]
    updated = p.record("anchored_sources_distribution_step", pi_next=pi)
    records["distribution_update.json"] = updated
    records["report.json"]["distribution_update_id"] = updated["id"]
    return updated


def test_original_failure_and_corrected_exact_scalar_match(case):
    with pytest.raises(ValueError, match="control_prior_unchanged"):
        original._distribution(*case[:4])
    before = copy.deepcopy(case[1])
    updated = case[-1]["distribution_update.json"]
    saved = copy.deepcopy(updated)
    pi = revision.revised_distribution(*case[:4])
    assert pi is updated["pi_next"]
    assert updated == saved and case[1] == before
    assert pi["target"] == {"x": 0.7, "y": 0.3}
    assert pi["control"] == {"x": 0.4, "y": 0.6}


@pytest.mark.parametrize("value", ["2/5", "0.4", 0.4])
def test_equivalent_scalar_representations(case, value):
    pi = copy.deepcopy(case[-1]["distribution_update.json"]["pi_next"])
    pi["control"]["x"] = value
    updated = replace_pi(case, pi)
    assert revision.revised_distribution(*case[:4]) is updated["pi_next"]


def test_one_ulp_real_difference_is_not_tolerated(case):
    pi = copy.deepcopy(case[-1]["distribution_update.json"]["pi_next"])
    pi["control"]["x"] = math.nextafter(0.4, math.inf)
    replace_pi(case, pi)
    with pytest.raises(ValueError, match="control_prior_unchanged"):
        revision.revised_distribution(*case[:4])


@pytest.mark.parametrize("damage", ["missing_task", "extra_task", "missing_state", "extra_state"])
def test_original_task_and_state_support_guard_remains(case, damage):
    pi = copy.deepcopy(case[-1]["distribution_update.json"]["pi_next"])
    if damage == "missing_task":
        del pi["target"]
    elif damage == "extra_task":
        pi["foreign"] = {"x": 1.0}
    elif damage == "missing_state":
        del pi["control"]["y"]
    else:
        pi["control"]["foreign"] = 0.0
    replace_pi(case, pi)
    with pytest.raises(ValueError, match="updated_B_support_only"):
        revision.revised_distribution(*case[:4])


@pytest.mark.parametrize("location", ["prior", "pi"])
@pytest.mark.parametrize(
    "value", [True, False, None, "not_a_number", "1/0", "NaN", "Infinity", [], {}]
)
def test_invalid_control_scalar_rejected(case, location, value):
    if location == "prior":
        case[1]["materials"]["binding"]["prior"]["control"]["x"] = value
    else:
        pi = copy.deepcopy(case[-1]["distribution_update.json"]["pi_next"])
        pi["control"]["x"] = value
        replace_pi(case, pi)
    with pytest.raises(ValueError, match=r"distribution\.(finite_scalar|boolean_not_scalar)"):
        revision.revised_distribution(*case[:4])


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_prior_rejected_by_frozen_scalar(case, value):
    case[1]["materials"]["binding"]["prior"]["control"]["x"] = value
    with pytest.raises(ValueError, match="distribution.finite_scalar"):
        revision.revised_distribution(*case[:4])


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_saved_pi_rejected_by_record_identity(case, value):
    # Nonfinite floats cannot form a canonical record; the unchanged checked()
    # guard rejects them even before the revised scalar comparison is reached.
    case[-1]["distribution_update.json"]["pi_next"]["control"]["x"] = value
    with pytest.raises(ValueError):
        revision.revised_distribution(*case[:4])


@pytest.mark.parametrize(
    "field,value",
    [
        ("plan_id", "another_plan"),
        ("job_key", "B_delayed_c_29"),
        ("prefix_checkpoint_sha256", "other_checkpoint"),
        ("prefix_snapshot_id", "other_snapshot"),
        ("numeric_guard_passed", False),
        ("numeric_guard_passed", 1),
        ("distribution_update_id", "other_update"),
    ],
)
def test_original_completed_outer_identity_guards_remain(case, field, value):
    case[-1]["report.json"][field] = value
    with pytest.raises(ValueError, match="only_bound_completed_outer_with_passed_guard"):
        revision.revised_distribution(*case[:4])


def test_original_update_content_identity_guard_remains(case):
    case[-1]["distribution_update.json"]["pi_next"]["target"]["x"] = 0.71
    with pytest.raises(ValueError, match="content_identity"):
        revision.revised_distribution(*case[:4])


def test_original_numeric_guard_file_remains_blocking(case):
    case[-1]["numeric_guard.json"]["passed"] = False
    with pytest.raises(ValueError, match="numeric_guard_failed"):
        revision.revised_distribution(*case[:4])


@pytest.mark.parametrize("condition", ["prefix", "static"])
def test_prefix_and_static_return_unchanged_deep_copied_prior(case, condition):
    case[2]["condition"] = condition
    prior = case[1]["materials"]["binding"]["prior"]
    pi = revision.revised_distribution(*case[:4])
    assert pi == prior == original._distribution(*case[:4])
    assert pi is not prior and pi["control"] is not prior["control"]
    assert pi["control"]["x"] == "2/5"
