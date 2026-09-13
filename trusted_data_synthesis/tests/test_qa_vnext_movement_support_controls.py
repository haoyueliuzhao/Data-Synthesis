"""Bounded scripted fixture controls; no Teacher, tokenizer, GPU or archive reads."""

import copy
from fractions import Fraction

import pytest
from test_qa_vnext_catalog_bridge_worker import fixture

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import assessment
from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.worker import encode, sha
from trusted_synthesis.experiments.finance_qa_vnext_movement_support import controls
from trusted_synthesis.experiments.finance_qa_vnext_movement_support import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_task_build import relations
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import record


@pytest.mark.parametrize("family", ["annual_flow", "stock_rollforward", "company_defined_metric"])
@pytest.mark.parametrize("quantity", ["difference", "relative_change"])
@pytest.mark.parametrize("basis", ["endpoint", "movement"])
def test_existing_public_runtime_fixtures_have_expected_method_without_Teacher_authenticity(
    family, quantity, basis
):
    supplied = fixture(family, quantity)
    before = copy.deepcopy(supplied)
    result = controls.run_fixture_control(supplied, basis)
    assert supplied == before
    p.checked_record(result, "offline_fixture_control")
    assert result["status"] == "PASS_INTERFACE_CONTROL", result
    assert result["replay_verified"] and result["financial_valid"]
    assert result["actual_method"] == result["expected_method"] == basis
    assert result["full_mapping_status"] == "MAPPED"
    assert result["runtime_origin_literal"] == "live_teacher_callback"
    assert result["actual_provenance"] == "test_only_scripted_reference_callback"
    assert result["original_assessment"]["origin"] == "live_teacher_callback"
    assert not result["authentic_Teacher_origin_verified"]
    assert not result["representation_eligible"] and not result["training_eligible"]
    assert result["training_samples"] == result["raw_or_encoded_training_packages_written"] == 0
    assert (
        result["model_calls"]
        == result["HTTP_requests"]
        == result["tokenizer_loads"]
        == result["GPU_operations"]
        == 0
    )
    assert (
        result["callback_response_count"]
        == result["recorded_response_count"]
        == result["planned_script_responses"]
    )


@pytest.mark.parametrize("quantity", ["difference", "relative_change"])
@pytest.mark.parametrize("basis", ["control", "fixed_control_reference"])
def test_fixed_control_reference_uses_neutral_runtime_guidance_and_control_expectation(
    quantity, basis
):
    result = controls.run_fixture_control(fixture("control", quantity), basis)
    assert result["status"] == "PASS_INTERFACE_CONTROL", result
    assert result["actual_method"] == result["expected_method"] == "control"


def test_same_fixture_control_is_deterministic_without_changing_session_origin():
    supplied = fixture()
    left = controls.run_fixture_control(supplied, "movement")
    right = controls.run_fixture_control(supplied, "movement")
    assert left == right


def test_missing_reference_input_retains_failed_control_instead_of_refilling():
    supplied = fixture()
    supplied["native_bindings"].pop("r0")
    result = controls.run_fixture_control(supplied, "movement")
    assert result["status"] == "FAIL_INTERFACE_CONTROL"
    assert result["error"]["phase"] == "script_construction"
    assert result["expected_method"] == "movement" and result["actual_method"] is None
    assert result["callback_response_count"] == 0


def test_a_reference_that_executes_endpoint_is_not_relabelled_as_movement(monkeypatch):
    original = controls.script_for_witness
    monkeypatch.setattr(
        controls,
        "script_for_witness",
        lambda bundle, native, basis: original(bundle, native, basis="endpoint"),
    )
    result = controls.run_fixture_control(fixture(), "movement")
    assert result["status"] == "FAIL_INTERFACE_CONTROL"
    assert result["expected_method"] == "movement" and result["actual_method"] == "endpoint"
    assert result["financial_valid"] and result["full_mapping_status"] == "MAPPED"


def test_first_malformed_Final_keeps_original_stop_and_UNDETERMINED(monkeypatch):
    monkeypatch.setattr(
        controls,
        "script_for_witness",
        lambda *args, **kwargs: [
            {"final": "bad"},
            {"final": {"value": "20", "unit": "million USD", "result_id": "never"}},
        ],
    )
    result = controls.run_fixture_control(fixture(), "movement")
    assert result["status"] == "FAIL_INTERFACE_CONTROL"
    assert result["terminal"] == "first_final" and result["first_final_index"] == 0
    assert result["planned_script_responses"] == 2 and result["callback_response_count"] == 1
    assert result["actual_method"] == "UNDETERMINED"
    assert result["semantic_reason"] == "final_shape_or_support_reference"


def test_overlength_reference_does_not_override_original_32_response_budget(monkeypatch):
    action = {"tool": "read_source", "arguments": {"source_id": "p", "unit": "million USD"}}
    monkeypatch.setattr(controls, "script_for_witness", lambda *args, **kwargs: [action] * 33)
    result = controls.run_fixture_control(fixture(), "endpoint")
    assert result["status"] == "FAIL_INTERFACE_CONTROL"
    assert result["terminal"] == "response_budget_exhausted"
    assert result["callback_response_count"] == result["executed_tools"] == 32
    assert result["planned_script_responses"] == 33 and result["first_final_index"] is None
    assert result["replay_verified"]


def test_replay_failure_is_retained_before_semantic_assessment(monkeypatch):
    def broken(_):
        raise ValueError("synthetic replay corruption")

    monkeypatch.setattr(controls.training_runtime, "replay", broken)
    result = controls.run_fixture_control(fixture(), "movement")
    assert result["status"] == "FAIL_INTERFACE_CONTROL"
    assert result["error"]["phase"] == "original_runtime_replay"
    assert result["original_assessment"] is None and not result["replay_verified"]


def factory_growth_fixture():
    """Actual relative_certificate producer over strictly synthetic fixture facts."""
    base_fixture = fixture("annual_flow", "difference")
    facts = {}
    for identifier, native in base_fixture["native_bindings"].items():
        raw = native["record"]
        facts[identifier] = {
            "fact_id": identifier,
            "entity_id": "synthetic-issuer",
            "metric_id": identifier,
            "period_start": raw.get("start"),
            "period_end": raw["end"],
            "normalized_value": str(Fraction(raw["val"], 1000000)),
            "normalized_unit": "million USD",
            "normalized_currency": "USD",
            "fiscal_year": int(raw["end"][:4]),
            "frequency": "annual",
        }
    witnesses = [
        relations.witness(w["operator_dag"], w["input_bindings"], list(facts.values()), w["basis"])
        for w in base_fixture["bundle"]["private"]["basis_witnesses"]
    ]
    base = record(
        "financial_relation_certificate",
        family="annual_flow",
        complete=True,
        leaf_fact_ids=list(facts),
        public_fact_ids=list(facts),
        witnesses=witnesses,
        previous_component_fact_ids=["r0", "k0"],
        previous_component_coefficients=[1, -1],
    )
    certificate = relations.relative_certificate(base, facts["p"], facts)
    supplied = fixture("annual_flow", "relative_change")
    supplied["bundle"]["private"]["relation_certificate"] = certificate
    supplied["bundle"]["private"]["basis_witnesses"] = certificate["witnesses"]
    return supplied


@pytest.mark.parametrize("basis", ["endpoint", "movement"])
def test_actual_factory_growth_wrapper_has_change_and_old_training_consumer_accepts(basis):
    supplied = factory_growth_fixture()
    certificate = supplied["bundle"]["private"]["relation_certificate"]
    assert "complete" not in certificate and certificate["base_relation_certificate"]["complete"]
    for witness in certificate["witnesses"]:
        assert witness["operator_dag"]["operators"][0]["step_id"] == "change"
        assert witness["operator_dag"]["operators"][-1]["operator"] == "ratio_percent"
    result = controls.run_fixture_control(supplied, basis)
    assert result["status"] == "PASS_INTERFACE_CONTROL", result
    assert result["actual_method"] == basis and result["quantity_status"] == "PASS"


def test_hypothetical_renamed_growth_step_exposes_fallback_but_is_not_actual_factory_output():
    supplied = fixture("annual_flow", "relative_change")
    witness = next(
        w for w in supplied["bundle"]["private"]["basis_witnesses"] if w["basis"] == "movement"
    )
    for operator in witness["operator_dag"]["operators"]:
        if operator["step_id"] == "change":
            operator["step_id"] = "renamed_change"
        for item in operator["inputs"]:
            if item.get("step") == "change":
                item["step"] = "renamed_change"
    result = controls.run_fixture_control(supplied, "movement")
    assert result["quantity_status"] == "PASS"
    assert result["status"] == "FAIL_INTERFACE_CONTROL"
    assert result["semantic_reason"] == "assessment.program_not_equivalent_to_financial_target"
    assert result["actual_method"] == "UNDETERMINED"


def table_alias_fixture(*, duplicate=False, unequal_semantics=False):
    supplied = fixture("annual_flow", "relative_change")
    native = copy.deepcopy(supplied["native_bindings"]["r0"])
    native.update(
        source_kind="issuer_report_table",
        table_id="synthetic-table",
        entity_id="synthetic-issuer",
        metric_id="revenue",
        source_definition_id="synthetic-definition",
        native_definition={"description": "same financial meaning"},
    )
    native["record"].update(
        val=100, cell_reference={"cells": [{"row": 0, "cell": 0, "text": "100"}]}
    )
    supplied["native_bindings"]["r0"] = native
    if duplicate:
        supplied["native_bindings"]["r0_alias"] = copy.deepcopy(native)
        if unequal_semantics:
            supplied["native_bindings"]["r0_alias"]["metric_id"] = "different-quantity"
    supplied["bundle"]["public"]["sources"] = [
        source for source in supplied["bundle"]["public"]["sources"] if source["source_id"] != "r0"
    ] + [
        {
            "source_id": "synthetic-table",
            "raw_sha256": "a" * 64,
            "original_url": "https://example.invalid/synthetic-table",
            "unit": "million USD",
            "original_rows": [["100"]],
        }
    ]
    supplied["messages"] = [
        {
            "role": "user",
            "content": encode(supplied["bundle"]["public"]).decode(),
        }
    ]
    supplied["identity"]["public_messages_sha256"] = sha(encode(supplied["messages"]))
    return supplied


@pytest.mark.parametrize(
    "duplicate,unequal,expected", [(False, False, 1), (True, False, 1), (True, True, 2)]
)
def test_same_cell_candidates_are_not_deduplicated_by_semantic_alias(duplicate, unequal, expected):
    supplied = table_alias_fixture(duplicate=duplicate, unequal_semantics=unequal)
    lookup = assessment.source_fact_bindings(supplied["bundle"], supplied["native_bindings"])
    key = encode({"source_id": "synthetic-table", "cells": [[0, 0]]}).decode()
    candidates = lookup[key]
    aliases = assessment._semantic_source_aliases(
        sorted(supplied["native_bindings"]), supplied["native_bindings"]
    )
    assert len(candidates) == (2 if duplicate else 1)
    assert len({aliases[item] for item in candidates}) == expected
    result = controls.run_fixture_control(supplied, "movement")
    assert result["quantity_status"] == "PASS"
    if duplicate:
        assert result["status"] == "FAIL_INTERFACE_CONTROL"
        assert result["semantic_reason"] == "assessment.source_not_uniquely_bound_to_fact"
        assert result["actual_method"] == "UNDETERMINED"
    else:
        assert result["status"] == "PASS_INTERFACE_CONTROL"


@pytest.mark.parametrize("basis", ["endpoint", "movement", "other"])
def test_invalid_control_basis_is_not_silently_filled_from_another_stratum(basis):
    with pytest.raises(ValueError, match="available_basis"):
        controls.run_fixture_control(fixture("control"), basis)
