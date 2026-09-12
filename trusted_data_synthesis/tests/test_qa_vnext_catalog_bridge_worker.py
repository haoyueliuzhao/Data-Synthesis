import copy
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.assessment import assess_session
from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.controls import (
    run_scripted_controls,
    script_for_witness,
)
from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.materials import raw_package
from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.worker import (
    encode,
    generate,
    sha,
)


def fixture(family="annual_flow", quantity="difference", surface="accepted_true_rewrite"):
    facts = {"p": 40, "c": 60, "r0": 100, "k0": 60, "r1": 120, "k1": 60}
    native, sources = {}, []
    for key, value in facts.items():
        data = {
            "val": value * 1000000,
            "end": "2019-12-31" if key in {"p", "r0", "k0"} else "2020-12-31",
        }
        native[key] = {"raw_sha256": "a" * 64, "pointer": "/" + key, "record": data}
        sources.append(
            {
                "source_id": key,
                "original_url": "https://example.test/source",
                "raw_sha256": "a" * 64,
                "native_pointer": "/" + key,
                "record": data,
                "unit": "USD",
            }
        )
    endpoints = {"previous": "p", "current": "c"}
    components = {"a": "r0", "b": "k0", "c": "r1", "d": "k1"}
    e = {
        "step_id": "answer",
        "operator": "difference",
        "inputs": [{"binding": "previous"}, {"binding": "current"}],
    }
    m = {
        "step_id": "answer",
        "operator": "linear_combination",
        "inputs": [{"binding": key} for key in components],
        "params": {"coefficients": [-1, 1, 1, -1]},
    }
    witnesses = []
    for basis, inputs, first in [("endpoint", endpoints, e), ("movement", components, m)]:
        operators = [first]
        if quantity == "relative_change":
            first["step_id"] = "change"
            if basis == "endpoint":
                inputs["positive_base"] = "p"
                base = {"binding": "positive_base"}
            else:
                operators.append(
                    {
                        "step_id": "base",
                        "operator": "linear_combination",
                        "inputs": [{"binding": "a"}, {"binding": "b"}],
                        "params": {"coefficients": [1, -1]},
                    }
                )
                base = {"step": "base"}
            operators.append(
                {
                    "step_id": "answer",
                    "operator": "ratio_percent",
                    "inputs": [{"step": "change"}, base],
                }
            )
        witnesses.append(
            {
                "basis": basis,
                "input_bindings": inputs,
                "operator_dag": {"operators": operators, "output_step": "answer"},
            }
        )
    if family == "control":
        witnesses = witnesses[:1]
        witnesses[0]["basis"] = "fixed_control_reference"
    unit = "million USD" if quantity == "difference" else "percent"
    public = {
        "question": "What was the signed change from 2019 to 2020?"
        if quantity == "difference"
        else "What was the percent change from the 2019 base to 2020?",
        "sources": sources,
        "source_policy": "frozen sources only",
        "tool_contract": {"calculate": "explicit arithmetic", "Final": "requested value and unit"},
        "quantity_contract": {
            "unit": unit,
            "currency": "USD" if quantity == "difference" else None,
            "decimal_places": 2,
            "rounding": "half away from zero",
        },
    }
    bundle = {
        "id": "fixture_bundle",
        "task_id": family + ":" + quantity + ":" + surface,
        "family": family,
        "public": public,
        "surface_realization": {"category": surface},
        "private": {
            "answer_exact": "20" if quantity == "difference" else "50",
            "canonical_target": {"quantity": quantity, "unit": unit},
            "basis_witnesses": witnesses,
            "relation_certificate": {
                "previous_component_fact_ids": ["r0", "k0"],
                "previous_component_coefficients": [1, -1],
            },
        },
    }
    messages = [{"role": "user", "content": encode(public).decode()}]
    if quantity == "relative_change":
        bundle["private"]["relation_certificate"] = {
            "base_relation_certificate": bundle["private"]["relation_certificate"]
        }
    identity = {
        "task_id": bundle["task_id"],
        "family": family,
        "surface_version_id": surface,
        "public_messages_sha256": sha(encode(messages)),
        "parent_manifest_id": "fixture_parent",
    }
    return {"bundle": bundle, "native_bindings": native, "identity": identity, "messages": messages}


def run(f, script, requested="neutral"):
    session = generate(f["messages"], f["identity"], scripted=script, requested_basis=requested)
    return session, assess_session(session, f["bundle"], f["native_bindings"])


@pytest.mark.parametrize(
    "family", ["annual_flow", "stock_rollforward", "company_defined_metric", "control"]
)
@pytest.mark.parametrize("quantity", ["difference", "relative_change"])
@pytest.mark.parametrize("surface", ["accepted_true_rewrite", "canonical_fallback"])
def test_four_groups_quantities_and_surfaces(family, quantity, surface):
    f = fixture(family, quantity, surface)
    for basis in ["endpoint"] if family == "control" else ["endpoint", "movement"]:
        script = script_for_witness(f["bundle"], f["native_bindings"], basis, alternative=True)
        session, assessment = run(f, script, "movement" if basis == "endpoint" else "endpoint")
        assert assessment["financial_valid"], assessment
        assert assessment["actual_method"] == ("control" if family == "control" else basis)
        assert assessment["full_mapping_status"] == "MAPPED"
        assert assessment["full_class"].startswith("finite_complete_signature:")
        assert not assessment["training_eligible"]
        package = raw_package(session, assessment)
        assert package["complete_first_final_package"]
        assert package["training_samples"] == 0


def test_registered_controls_keep_every_denominator():
    report = run_scripted_controls([fixture()], Path("."))
    assert report["status"] == "PASS", report["rows"]
    assert report["registered"] == 14
    assert len(report["sessions"]) == len(report["assessments"]) == 14
    assert report["training_samples"] == report["provider_calls"] == 0


def test_online_rejects_private_identity_or_mutated_public():
    f = fixture()
    with pytest.raises(ValueError, match="public_only"):
        generate(f["messages"], {**f["identity"], "bundle_path": "/private/bundle"}, scripted=[])
    changed = copy.deepcopy(f["messages"])
    changed[0]["content"] += " "
    with pytest.raises(ValueError, match="messages_hash"):
        generate(changed, f["identity"], scripted=[])


def test_actual_unit_conversion_and_tampered_tool_rejected():
    f = fixture()
    session, assessment = run(f, script_for_witness(f["bundle"], f["native_bindings"]))
    tool = session["events"][0]["tool_call"]["result"]
    assert tool["conversion"]["factor"] == "1/1000000"
    assert tool["conversion"]["input_exact_value"] == "40000000"
    assert tool["exact_value"] == "40"
    changed = copy.deepcopy(session)
    changed["events"][0]["tool_call"]["result"]["exact_value"] = "40.0"
    with pytest.raises(ValueError, match="replay"):
        assess_session(changed, f["bundle"], f["native_bindings"])


def test_same_value_wrong_financial_source_not_qualified():
    f = fixture()
    script = script_for_witness(f["bundle"], f["native_bindings"])
    # k0 equals c numerically, but is a prior-period expense rather than endpoint.
    script[1]["arguments"]["source_id"] = "k0"
    _, assessed = run(f, script)
    assert assessed["quantity_status"] == "PASS"
    assert not assessed["financial_valid"]
    assert assessed["actual_method"] == "UNDETERMINED"


def test_original_format_error_stays_in_later_input():
    f = fixture()
    session, assessed = run(f, ["bad\r\n", *script_for_witness(f["bundle"], f["native_bindings"])])
    package = raw_package(session, assessed)
    assert package["candidates"][0]["messages"][2]["content"] == "bad\r\n"
    assert package["all_raw_turns_retained"][0]["raw_response"] == "bad\r\n"
    assert all(row["target_text"] != "bad\r\n" for row in package["candidates"])


def test_shared_endpoint_base_is_valid_movement_rate():
    f = fixture(quantity="relative_change")
    script = script_for_witness(f["bundle"], f["native_bindings"], "movement")
    # Replace component-base computation with an explicit endpoint read.
    base_index = next(
        i
        for i, row in enumerate(script)
        if row.get("tool") == "calculate"
        and row["arguments"]["expression"] == "sum([(1)*v0,(-1)*v1])"
    )
    script[base_index] = {
        "tool": "read_source",
        "arguments": {"source_id": "p", "unit": "million USD"},
    }
    _, assessed = run(f, script)
    assert assessed["financial_valid"], assessed
    assert assessed["actual_method"] == "movement"
    assert assessed["full_signature"]["shared_endpoint_base"]


def test_fine_class_normalizes_spelling_but_retains_verification_and_revision():
    f = fixture()
    script = script_for_witness(f["bundle"], f["native_bindings"])
    _, plain = run(f, script)
    _, equivalent = run(
        f, script_for_witness(f["bundle"], f["native_bindings"], alternative=True), "movement"
    )
    assert plain["full_class"] == equivalent["full_class"]
    verify = copy.deepcopy(script)
    verify.insert(-1, copy.deepcopy(script[-2]))
    _, verification = run(f, verify)
    assert verification["financial_valid"] and verification["actual_method"] == "endpoint"
    assert verification["full_mapping_status"] == "MAPPED"
    assert verification["full_class"] != plain["full_class"]
    assert verification["full_signature"]["target_cross_checks"] == [
        {
            "result_id": "tool:4",
            "kind": "redundant_target_recomputation",
            "first_final_result_id": "tool:3",
        }
    ]
    revised = copy.deepcopy(script)
    revised[-2]["arguments"]["expression"] = "v0-v1"
    correction = copy.deepcopy(script[-2])
    correction["arguments"]["revises_result_id"] = "tool:3"
    revised.insert(-1, correction)
    revised[-1]["final"]["result_id"] = "tool:4"
    _, revision = run(f, revised)
    assert revision["financial_valid"] and revision["actual_method"] == "endpoint"
    assert revision["full_mapping_status"] == "MAPPED"
    assert revision["full_class"] not in {plain["full_class"], verification["full_class"]}
    assert revision["full_signature"]["revision_edges"] == [
        {
            "from_result_id": "tool:3",
            "to_result_id": "tool:4",
            "substantive_program_change": True,
            "revised_result_supports_first_final": True,
        }
    ]


def test_unexplained_extra_calculation_kept_without_forced_full_class():
    f = fixture()
    script = script_for_witness(f["bundle"], f["native_bindings"])
    extra = copy.deepcopy(script[-2])
    extra["arguments"]["expression"] = "v0+v1"
    script.insert(-1, extra)
    _, assessed = run(f, script)
    assert assessed["financial_valid"] and assessed["actual_method"] == "endpoint"
    assert assessed["full_mapping_status"] == "PENDING_REVIEW" and assessed["full_class"] is None
    assert "non_support_calculation_intent_unresolved" in assessed["full_mapping_pending_reasons"]


def test_source_selection_and_order_retained_in_complete_signature():
    f = fixture()
    script = script_for_witness(f["bundle"], f["native_bindings"])
    _, plain = run(f, script)
    swapped = copy.deepcopy(script)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    swapped[2]["arguments"]["variables"] = {
        "v0": {"result_id": "tool:2"},
        "v1": {"result_id": "tool:1"},
    }
    _, alternative = run(f, swapped)
    assert alternative["financial_valid"] and alternative["actual_method"] == "endpoint"
    assert alternative["full_class"] != plain["full_class"]
    assert (
        alternative["full_signature"]["final_support_program"]
        == plain["full_signature"]["final_support_program"]
    )


def test_table_split_parenthesis_and_cross_year_rejection():
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.worker import read_source

    public = {
        "sources": [
            {
                "source_id": "table",
                "original_url": "https://example.test/report",
                "raw_sha256": "b" * 64,
                "unit": "million USD",
                "original_rows": [["Capex", "(2,135", ")", "2,136", "%", "—"]],
            }
        ]
    }
    value = read_source({"source_id": "table", "cells": [[0, 1], [0, 2]], "unit": "USD"}, public)
    assert value["exact_value"] == "-2135000000"
    assert value["conversion"]["factor"] == "1000000"
    assert value["original_source_fragment"] == [
        {"row": 0, "cell": 1, "text": "(2,135"},
        {"row": 0, "cell": 2, "text": ")"},
    ]
    with pytest.raises(ValueError, match="numeric_bodies"):
        read_source({"source_id": "table", "cells": [[0, 1], [0, 2], [0, 3]]}, public)
    with pytest.raises(ValueError, match="incomplete"):
        read_source({"source_id": "table", "cells": [[0, 1]]}, public)
    with pytest.raises(ValueError, match="numeric_bodies"):
        read_source({"source_id": "table", "cells": [[0, 5]]}, public)


def test_equal_semantics_alternative_source_is_valid_but_distinct_full_class():
    f = fixture()
    for key, native in f["native_bindings"].items():
        native.update(
            entity_id="issuer",
            metric_id="gross_profit" if key in {"p", "c"} else key,
            source_definition_id="definition:" + ("gross_profit" if key in {"p", "c"} else key),
            native_definition={"description": "gross profit is revenue less cost"},
        )
    f["native_bindings"]["c_alt"] = {
        **copy.deepcopy(f["native_bindings"]["c"]),
        "pointer": "/c_alt",
    }
    source = next(
        source for source in f["bundle"]["public"]["sources"] if source["source_id"] == "c"
    )
    f["bundle"]["public"]["sources"].append(
        {**copy.deepcopy(source), "source_id": "c_alt", "native_pointer": "/c_alt"}
    )
    f["messages"][0]["content"] = encode(f["bundle"]["public"]).decode()
    f["identity"]["public_messages_sha256"] = sha(encode(f["messages"]))
    script = script_for_witness(f["bundle"], f["native_bindings"])
    _, plain = run(f, script)
    script[1]["arguments"]["source_id"] = "c_alt"
    _, alternate = run(f, script)
    assert plain["financial_valid"] and alternate["financial_valid"]
    assert alternate["actual_method"] == "endpoint"
    assert alternate["full_class"] != plain["full_class"]
    assert (
        alternate["full_signature"]["final_support_program"]
        == plain["full_signature"]["final_support_program"]
    )
    assert "c_alt" in alternate["effective_fact_ids"] and "c" not in alternate["effective_fact_ids"]


def test_materialization_rejects_mutated_or_duplicate_package_before_loading():
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.materials import (
        materialize_packages,
    )

    f = fixture()
    session, assessed = run(f, script_for_witness(f["bundle"], f["native_bindings"]))
    package = raw_package(session, assessed)

    def forbidden_loader(root):
        raise AssertionError("tokenizer must not load")

    with pytest.raises(ValueError, match="unique_original_sessions"):
        materialize_packages([package, package], Path("."), loader=forbidden_loader)
    corrupted = copy.deepcopy(package)
    corrupted["candidates"][0]["target_text"] += " "
    with pytest.raises(ValueError, match="package_identity"):
        materialize_packages([corrupted], Path("."), loader=forbidden_loader)
    empty = materialize_packages([], Path("."), loader=forbidden_loader)
    assert empty["tokenizer_loads"] == 0 and empty["status"] == "NO_PACKAGES"


def test_materialization_retains_all_not_fit_rows_without_replacement(monkeypatch):
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import materials

    f = fixture()
    session, assessed = run(f, script_for_witness(f["bundle"], f["native_bindings"]))
    package = raw_package(session, assessed)
    calls = []

    def not_fit(row, binding, tokenizer, *, maximum_sequence_length):
        calls.append(row["id"])
        return {
            "consumable_token_representation": False,
            "reason": "maximum_sequence_length_exceeded",
            "target_token_count": 9,
        }

    monkeypatch.setattr(materials, "encode_original_candidate", not_fit)
    report = materials.materialize_packages(
        [package],
        Path("."),
        loader=lambda root: (
            {
                "id": "fixture",
                "maximum_sequence_length": 24576,
                "model_max_position_embeddings": 32768,
            },
            object(),
        ),
    )
    assert report["status"] == "REPRESENTATION_FAILED"
    assert len(calls) == len(package["candidates"]) == len(report["checks"])
    assert len(report["failures"]) == len(calls)
    assert report["training_samples"] == report["model_weight_loads"] == report["gpu_calls"] == 0


def test_worker_scale_mapping_matches_catalog_and_registered_loss_groups():
    from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation.design import GROUPS
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.catalog import (
        FAMILY_TO_SCALE,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.worker import (
        FAMILY_TO_SCALE_GROUP,
    )

    assert (
        FAMILY_TO_SCALE_GROUP
        == FAMILY_TO_SCALE
        == {
            "stock_rollforward": "stock_rollforward",
            "annual_flow": "annual_flow_components",
            "company_defined_metric": "defined_metric_reconstruction",
            "control": "control",
        }
    )
    assert set(FAMILY_TO_SCALE_GROUP.values()) == set(GROUPS)


def test_local_tokenizer_constructed_once_with_validated_shared_primitive(monkeypatch):
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import materials

    calls = []
    tokenizer = object()
    binding = {"id": "validated_fixture"}

    def validate_and_construct(root, directory):
        calls.append((root, directory))
        return binding, tokenizer

    def forbidden(*args, **kwargs):
        raise AssertionError("separate register/load would construct twice")

    monkeypatch.setattr(materials.assets, "_binding_and_tokenizer", validate_and_construct)
    monkeypatch.setattr(materials.assets, "register_tokenizer", forbidden)
    monkeypatch.setattr(materials.assets, "load_tokenizer", forbidden)
    assert materials.load_local_tokenizer(".") == (binding, tokenizer)
    assert calls == [(Path("."), materials.assets.MODEL_DIRECTORY)]


def test_materialization_inherits_24576_and_rejects_extension_before_loading():
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import materials

    assert materials.MAXIMUM_SEQUENCE_LENGTH == materials.assets.MAX_SEQUENCE_LENGTH == 24576

    def forbidden_loader(root):
        raise AssertionError("overlength policy must fail before loading")

    for cap in (24577, 32768, 49152):
        with pytest.raises(ValueError, match="frozen_sequence_cap"):
            materials.materialize_packages(
                [], Path("."), loader=forbidden_loader, maximum_sequence_length=cap
            )


@pytest.mark.parametrize(
    "binding, reason",
    [
        (
            {"maximum_sequence_length": 24575, "model_max_position_embeddings": 32768},
            "bound_sequence_cap",
        ),
        (
            {"maximum_sequence_length": 24576, "model_max_position_embeddings": 24575},
            "bound_model_context_limit",
        ),
        (
            {"maximum_sequence_length": 24576, "model_max_length_declared": 131072},
            "bound_model_context_limit",
        ),
    ],
)
def test_materialization_checks_binding_policy_and_actual_model_context(
    monkeypatch, binding, reason
):
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import materials

    f = fixture()
    session, assessed = run(f, script_for_witness(f["bundle"], f["native_bindings"]))
    package = raw_package(session, assessed)

    def forbidden_encoder(*args, **kwargs):
        raise AssertionError("invalid binding must fail before row encoding")

    monkeypatch.setattr(materials, "encode_original_candidate", forbidden_encoder)
    report = materials.materialize_packages(
        [package], Path("."), loader=lambda root: (binding, object())
    )
    assert report["status"] == "TOKENIZER_BINDING_REJECTED"
    assert report["checks"] == []
    assert report["failures"] == [
        {"phase": "tokenizer_binding_limits", "reason": "materials." + reason}
    ]
