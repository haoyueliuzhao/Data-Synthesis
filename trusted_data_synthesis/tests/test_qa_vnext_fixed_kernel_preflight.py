"""Metadata-first preflight and explicitly non-empirical script boundaries."""

import copy
import json
from collections import Counter

import pytest
from test_qa_vnext_catalog_bridge_worker import fixture
from test_qa_vnext_fixed_kernel_distribution import catalog as synthetic_catalog

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import materials
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import preflight as pf
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.source_boundary import (
    prepare_fixture,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import (
    record as archive_record,
)


@pytest.fixture
def mock_inputs(monkeypatch):
    catalog, originals = synthetic_catalog(), []
    for row in catalog["tasks"]:
        f = fixture(row["family"], row["quantity"])
        row["public_messages_sha256"] = f["identity"]["public_messages_sha256"]
        f["identity"] = {key: row[key] for key in f["identity"]}
        f["bundle"]["task_id"] = row["task_id"]
        f["bundle"]["id"] = row["bundle_id"]
        originals.append(f)
    catalog = archive_record("composed_task_catalog", tasks=catalog["tasks"], parents=[])
    events = []

    class Parent:
        def __init__(self, *_):
            self.closed = False

        def read(self, name):
            assert name == "catalog.json"
            return catalog

        def close(self):
            events.append("closed")
            self.closed = True

    original_select = pf.population.make_population

    def select(value):
        events.append("metadata_selected")
        return original_select(value)

    def load(*_):
        assert events == ["metadata_selected"]
        events.append("original_255_loaded")
        return originals, p.record(
            "synthetic_source_dependencies", catalog_id=catalog["id"], parents=[]
        )

    def sources(*_):
        assert events == ["metadata_selected", "original_255_loaded"]
        events.append("sources_checked")
        return p.record(
            "source_evidence", table_proofs={}, CFO_occurrence_proofs={}, test_only=True
        )

    monkeypatch.setattr(pf, "LinearParent", Parent)
    monkeypatch.setattr(pf.population, "make_population", select)
    monkeypatch.setattr(pf, "load_fixtures", load)
    monkeypatch.setattr(pf, "load_source_evidence", sources)
    result = pf.load_inputs("unused_synthetic_data_root")
    return result, events, originals


def test_load_inputs_selects_population_before_coverage_and_closes_every_handle(mock_inputs):
    inputs, events, originals = mock_inputs
    assert events == ["metadata_selected", "original_255_loaded", "sources_checked", "closed"]
    assert len(inputs["fixtures"]) == inputs["boundary_manifest"]["selected_task_count"] == 200
    assert inputs["boundary_manifest"]["metadata_selection_preceded_source_coverage"]
    assert not inputs["boundary_manifest"]["coverage_based_replacement"]
    assert json.loads(p.encode(inputs)) == inputs
    by_task = {row["identity"]["task_id"]: row for row in originals}
    for identifier, prepared in inputs["fixtures"].items():
        assert all(
            prepared[key] == by_task[identifier][key]
            for key in ("messages", "bundle", "identity", "native_bindings")
        )
    assert {row["task_id"] for row in inputs["boundary_manifest"]["tasks"]} == set(
        inputs["fixtures"]
    )


def test_control_matrix_has_exact_560_predeclared_jobs_and_both_opposite_guidances(mock_inputs):
    inputs = mock_inputs[0]
    jobs = pf._control_plan(inputs)
    counts = Counter(inputs["fixtures"][row["task_id"]]["identity"]["family"] for row in jobs)
    assert counts == {
        "annual_flow": 160,
        "stock_rollforward": 160,
        "company_defined_metric": 160,
        "control": 80,
    }
    assert [row["ordinal"] for row in jobs] == list(range(560))
    first = inputs["population"]["tasks"][0]["task_id"]
    assert {
        (row["guidance"], row["expected_actual_method"]) for row in jobs if row["task_id"] == first
    } == {
        ("endpoint", "endpoint"),
        ("endpoint", "movement"),
        ("movement", "endpoint"),
        ("movement", "movement"),
    }


@pytest.mark.parametrize(
    "family,guidance,actual",
    [
        ("annual_flow", "endpoint", "movement"),
        ("annual_flow", "movement", "endpoint"),
        ("company_defined_metric", "endpoint", "movement"),
        ("control", "neutral", "control"),
    ],
)
def test_actual_scripted_method_not_requested_label_and_never_empirical(family, guidance, actual):
    f = prepare_fixture(fixture(family))
    job = {
        "ordinal": 0,
        "task_id": f["identity"]["task_id"],
        "guidance": guidance,
        "expected_actual_method": actual,
    }
    result = pf._run_control(f, job)
    assert result["passed"] and result["actual_method"] == actual
    assert result["origin"] == "ENGINEERING_SYNTHETIC"
    assert result["script_accesses_private_witness_and_reference_answer"]
    assert result["runtime_private_oracle_access_flag_is_not_a_claim_about_script_construction"]
    assert not result["authentic_origin_verified"]
    assert not result["formal_10240_registration_member"] and not result["training_eligible"]
    assert result["API_calls"] == result["GPU_operations"] == result["training_samples"] == 0
    assert result["public_messages_unchanged"] and result["registered_system_unchanged"]


def test_bad_reference_control_is_reported_not_repaired():
    f = prepare_fixture(fixture())
    f["bundle"]["private"]["answer_exact"] = "99999999"
    job = {
        "ordinal": 0,
        "task_id": f["identity"]["task_id"],
        "guidance": "endpoint",
        "expected_actual_method": "movement",
    }
    result = pf._run_control(f, job)
    assert not result["passed"]
    assert result["reason"] == "assessment.final_not_supported_by_named_result"
    assert f["bundle"]["private"]["answer_exact"] == "99999999"


def test_control_registration_schema_cannot_enter_material_consumer(monkeypatch):
    f = prepare_fixture(fixture())
    registrations = []
    generate = pf.runtime.generate

    def capture(*args, **kwargs):
        registrations.append(copy.deepcopy(kwargs["registered"]))
        return generate(*args, **kwargs)

    monkeypatch.setattr(pf.runtime, "generate", capture)
    result = pf._run_control(
        f,
        {
            "ordinal": 0,
            "task_id": f["identity"]["task_id"],
            "guidance": "movement",
            "expected_actual_method": "endpoint",
        },
    )
    assert result["passed"]
    with pytest.raises(ValueError):
        materials._registration(registrations[0])


def test_one_failed_control_preserves_full_plan_and_blocks_engineering_pass(
    mock_inputs, monkeypatch
):
    inputs = mock_inputs[0]

    def control(f, job):
        return p.record(
            "engineering_scripted_control",
            **job,
            family=f["identity"]["family"],
            passed=job["ordinal"] != 17,
            responses=3,
            tool_calls=2,
            maximum_request_body_bytes=222,
            origin="ENGINEERING_SYNTHETIC",
        )

    monkeypatch.setattr(pf, "_run_control", control)
    result = pf.scripted_controls(inputs, workers=1)
    assert result["status"] == "FAIL_ENGINEERING_CONTROLS"
    assert result["completed_control_count"] == 560 and result["passed_control_count"] == 559
    assert len(result["failed_control_ids"]) == 1
    assert result["maximum_request_body_bytes"] == 222
    assert result["formal_material_sessions_created"] == 0
