"""Synthetic source metadata and complete fixed-cohort join controls."""

import copy

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_movement_support import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_movement_support import summary as s


def source_signal(*, status="UNIQUE_SOURCE_LOCATOR", closure=False):
    facts = {
        "UNIQUE_SOURCE_LOCATOR": ["private_fact_never_copied"],
        "UNBOUND_SOURCE": [],
        "AMBIGUOUS_SOURCE": ["private_one", "private_two"],
    }[status]
    roles = {"movement_exclusive_input": True}
    return dict(
        all_public_tool_diagnostics=[
            dict(
                result_id="tool:1",
                tool="read_source",
                status="ok",
                source=dict(status=status, fact_ids=facts, roles=roles),
            )
        ],
        first_final_closure_result_ids=["tool:1"] if closure else [],
        closure_source_status_counts={status: 1} if closure else {},
        closure_witness_role_counts=roles if closure and status == "UNIQUE_SOURCE_LOCATOR" else {},
    )


@pytest.mark.parametrize("closure", [False, True])
def test_unique_any_read_is_not_automatically_in_first_Final_closure(closure):
    flags = s._source_flags(source_signal(closure=closure))
    assert flags["unique_movement_exclusive_any_read"] is True
    assert flags["unique_movement_exclusive_first_Final_closure"] is closure
    assert "private_fact_never_copied" not in p.encode(flags).decode()


@pytest.mark.parametrize("status", ["UNBOUND_SOURCE", "AMBIGUOUS_SOURCE"])
def test_unbound_and_multicandidate_never_become_unique_movement(status):
    flags = s._source_flags(source_signal(status=status, closure=True))
    assert flags["unique_movement_exclusive_any_read"] is False
    assert flags["closure_unbound_source"] is (status == "UNBOUND_SOURCE")
    assert flags["closure_ambiguous_source"] is (status == "AMBIGUOUS_SOURCE")


@pytest.mark.parametrize(
    "change", ["unique_two_facts", "false_closure_count", "missing_tool", "duplicate_tool"]
)
def test_source_binding_and_closure_counts_are_checked_not_self_declared(change):
    value = source_signal(closure=True)
    if change == "unique_two_facts":
        value["all_public_tool_diagnostics"][0]["source"]["fact_ids"].append("other")
    elif change == "false_closure_count":
        value["closure_witness_role_counts"] = {}
    elif change == "missing_tool":
        value["first_final_closure_result_ids"].append("tool:missing")
    else:
        value["all_public_tool_diagnostics"] *= 2
    with pytest.raises(ValueError):
        s._source_flags(value)


@pytest.fixture(scope="module")
def complete_inputs():
    originals, observations, cases, witnesses = [], [], [], []
    for task_number in range(255):
        family = "annual_flow" if task_number < 155 else "control"
        task_id, group = "task:" + str(task_number), s.FAMILY_TO_SCALE_GROUP[family]
        bases = ("endpoint", "movement") if task_number < 155 else ("control",)
        witnesses.append(
            p.record(
                "growth_delta_hazard",
                task_id=task_id,
                structural_only=True,
                percentage_output_used_as_currency_delta=False,
                private_payload="private_witness_never_copied",
            )
        )
        for basis in bases:
            cases.append(
                p.record(
                    "offline_fixture_control",
                    task_id=task_id,
                    family=family,
                    requested_control_basis=basis,
                    expected_method=basis,
                    actual_method=basis,
                    actual_provenance="test_only_scripted_reference_callback",
                    test_only=True,
                    authentic_Teacher_origin_verified=False,
                    representation_eligible=False,
                    training_eligible=False,
                    training_samples=0,
                    model_calls=0,
                    HTTP_requests=0,
                    GPU_operations=0,
                    replay_verified=True,
                    financial_valid=True,
                    full_mapping_status="MAPPED",
                    error=None,
                    status="PASS_INTERFACE_CONTROL",
                    checks=dict(
                        original_runtime_replay=True,
                        financial_valid=True,
                        expected_actual_method=True,
                        fine_mapping=True,
                    ),
                    original_assessment={"private": "private_assessment_never_copied"},
                )
            )
        for pool in ("A", "B"):
            for basis in bases:
                for replicate in range(24 if basis == "control" else 32):
                    index = len(originals)
                    old = dict(
                        registered_session_id="registered:" + str(index),
                        session_id="session:" + str(index),
                        qualification_id="qualification:" + str(index),
                        task_id=task_id,
                        family=family,
                        group=group,
                        pool=pool,
                        requested_basis=basis,
                        replicate=replicate,
                        actual_method="UNDETERMINED",
                        representation_eligible=False,
                        first_final_index=3,
                        reason="support_not_proven",
                        quantity_status="PASS",
                        support_status="UNDETERMINED",
                        financial_valid=False,
                        full_mapping_status="PENDING_REVIEW",
                    )
                    detail = (
                        source_signal()
                        if index in (1, 129)
                        else dict(
                            all_public_tool_diagnostics=[],
                            first_final_closure_result_ids=[],
                            closure_source_status_counts={},
                            closure_witness_role_counts={},
                        )
                    )
                    signal = p.record(
                        "public_structural_signals",
                        **detail,
                        task_id=task_id,
                        session_id=old["session_id"],
                        first_final_index=3,
                        first_final_status="FINAL_WITH_RESULT_REFERENCE",
                        structural_shape="NO_REFERENCED_SOURCE_IN_SYNTACTIC_CLOSURE",
                        actual_method_inferred=False,
                        financial_qualification_performed=False,
                        units_values_periods_or_algebraic_sufficiency_verified=False,
                    )
                    originals.append(old)
                    observations.append(
                        dict(
                            **{
                                key: old[key]
                                for key in [
                                    "registered_session_id",
                                    "qualification_id",
                                    "task_id",
                                    "family",
                                    "pool",
                                    "requested_basis",
                                ]
                            },
                            registry_index=index,
                            original_actual_method=old["actual_method"],
                            original_representation_eligible=False,
                            signals=signal,
                        )
                    )
    return (
        p.record(
            "phase_zero_funnel",
            all_session_rows=originals,
            declared_expected_session_count=24640,
            is_original_24640_session_cohort=True,
        ),
        p.record(
            "public_execution_signals",
            rows=observations,
            registered_sessions=24640,
            all_original_registry_order_preserved=True,
            finance_or_method_qualification=False,
            reasoning_content_inspected=False,
        ),
        p.record(
            "scripted_interface_controls",
            cases=list(reversed(cases)),
            case_count=410,
            actual_generation_distribution_not_measured_by_scripts=True,
            training_material=False,
        ),
        p.record(
            "original_witness_diagnostics",
            rows=list(reversed(witnesses)),
            task_count=255,
            not_observed_Teacher_requalification=True,
            source_locator_ambiguities=[],
        ),
    )


def test_complete_410_controls_and_two_cases_are_not_real_movement_generation(complete_inputs):
    result = s.summarize(*complete_inputs)
    assert result["control_summary"]["cases_by_expected_method"] == {
        "endpoint": 155,
        "movement": 155,
        "control": 100,
    }
    assert result["control_summary"]["passed"] == 410
    assert result["control_summary"]["measures_real_generation"] is False
    assert result["totals"]["registered_sessions"] == 24640
    assert result["totals"]["unique_movement_exclusive_any_read_sessions"] == 2
    assert result["totals"]["unique_movement_exclusive_first_Final_closure_sessions"] == 0
    assert [
        row["registry_index"] for row in result["unique_movement_any_read_cases_in_registry_order"]
    ] == [1, 129]
    assert (
        "private_"
        not in p.encode(result["unique_movement_any_read_cases_in_registry_order"]).decode()
    )
    assert "private_witness_never_copied" not in p.encode(result).decode()
    assert "private_assessment_never_copied" not in p.encode(result).decode()
    assert sum(row["sessions"] for row in result["shape_reason_method_cross"]) == 24640


def resign(value, kind):
    return p.record(
        kind, **{key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    )


@pytest.mark.parametrize(
    "change",
    ["bad_id", "cohort_join", "duplicate_control", "scripted_as_authentic", "false_control_pass"],
)
def test_changed_ids_cohort_or_control_authority_never_gets_a_summary(complete_inputs, change):
    values = list(copy.deepcopy(complete_inputs))
    if change == "bad_id":
        values[0]["id"] = "phase_zero_funnel:tampered"
    elif change == "cohort_join":
        values[1]["rows"][0]["qualification_id"] = "qualification:other"
        values[1] = resign(values[1], "public_execution_signals")
    else:
        case = values[2]["cases"][0]
        if change == "duplicate_control":
            values[2]["cases"][0] = copy.deepcopy(values[2]["cases"][1])
        else:
            if change == "scripted_as_authentic":
                case["authentic_Teacher_origin_verified"] = True
            else:
                case["financial_valid"] = False
            values[2]["cases"][0] = resign(case, "offline_fixture_control")
        values[2] = resign(values[2], "scripted_interface_controls")
    with pytest.raises(ValueError):
        s.summarize(*values)
