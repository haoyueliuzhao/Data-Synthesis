"""Prospective identity, method-level quota and unchanged target/claim boundaries."""

from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.assess import (
    population_summary,
    raw_messages,
    scope_status,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.core import Store
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.plan import (
    BASIS_INSTRUCTIONS,
    COMMON_SYSTEM,
    GENERATION_CONDITIONS,
    LABELS,
    SOURCE,
    SYSTEMS,
    TASKS,
    condition,
    fixed_selection,
    policy,
    read_json,
    registrations,
    target_ledgers,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.review import (
    claim_certification,
    quote_check,
    semantic_binding,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.source import (
    batch_path,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import SYSTEMS_NEW

ROOT = Path(__file__).resolve().parents[2]


def public():
    return {key: read_json(ROOT / SOURCE / f"preparation/public/{key}.json") for key in TASKS}


def rows():
    return [
        {
            **registration,
            "formula_driven_trace_verified": True,
            "full_mapping_status": "MAPPED",
            "method_stratum": registration["arm"],
            "class_id": "fixture_class:" + registration["label"],
            "projection_id": "fixture_projection:" + registration["label"],
            "method_record_id": "fixture_method:" + registration["label"],
        }
        for registration in registrations(public())
    ]


def test_exact_two_task_two_guidance_fixed_empty_history_batch():
    registered = registrations(public())
    assert len(registered) == len({r["review_id"] for r in registered}) == 32
    assert tuple(r["label"] for r in registered) == LABELS
    assert Counter((r["task_key"], r["arm"]) for r in registered) == {
        (key, g): 8 for key in TASKS for g in GENERATION_CONDITIONS
    }
    for wave, n in ((1, 6), (2, 2)):
        assert Counter((r["task_key"], r["arm"]) for r in registered if r["wave"] == wave) == {
            (key, g): n for key in TASKS for g in GENERATION_CONDITIONS
        }
    assert all(r["condition_id"] == condition(r["arm"])["id"] for r in registered)
    assert all(r["response_budget"] == r["tool_budget"] == 32 for r in registered)
    assert all(r["new_independent_empty_history"] for r in registered)


def test_common_contract_only_adds_one_basis_instruction():
    assert COMMON_SYSTEM == SYSTEMS_NEW["N"]
    assert COMMON_SYSTEM != SYSTEMS_NEW["E"]
    assert {SYSTEMS[g] for g in GENERATION_CONDITIONS}.isdisjoint(SYSTEMS_NEW.values())
    for g in GENERATION_CONDITIONS:
        assert SYSTEMS[g] == COMMON_SYSTEM + "\n\n" + BASIS_INSTRUCTIONS[g]
        assert not any(
            token in BASIS_INSTRUCTIONS[g]
            for token in ("X1", "X2", "source:", "426.6", "48.3", "10-4")
        )


@pytest.mark.parametrize(
    "key,value",
    [
        ("new_Teacher_sessions", 32),
        ("maximum_generation_requests", 1024),
        ("training_allowed_even_if_consumability_passes", False),
        ("Student_generations_training_B0_same_question_greedy_and_NLL", 0),
        ("training_weights_or_27_package_training_population_instantiated", False),
        ("Final_multi_amount_extraction_not_extended", True),
        ("old_35D_1R_and_old_X1_examples_not_new_target_data", True),
        ("requested_labels_never_used_as_actual_method", True),
        ("method_is_not_a_new_equivalence_relation", True),
        ("no_replacement_after_selected_token_failure", True),
    ],
)
def test_support_scope_not_a_default_utility_authorization(key, value):
    assert policy()[key] == value


def test_public_objects_are_not_both_stock_rollforwards():
    private = read_json(ROOT / SOURCE / "preparation/private/evaluation_targets.json")
    ledgers = target_ledgers(public(), private)
    assert "gross margin" in ledgers["X1"]["object"]
    assert "not net income" in ledgers["X1"]["object"]
    assert "2003" in ledgers["X1"]["comparison"] and "2002" in ledgers["X1"]["comparison"]
    assert "product-warranty reserve" in ledgers["X2"]["object"]
    assert all(ledgers[key]["alignment"] == "ALIGNED" for key in TASKS)


def test_selection_uses_first_four_actual_method_not_completion_or_class_identity():
    selected = fixed_selection(list(reversed(rows())))
    assert selected["status"] == "RAW_METHOD_SUPPORT_ESTABLISHED"
    assert len(selected["selected"]) == 16
    assert Counter(r["role"] for r in selected["selected"]) == {"future_train": 12, "heldout": 4}
    assert selected["training_allowed"] is False
    for key in TASKS:
        for method in GENERATION_CONDITIONS:
            chosen = [
                r
                for r in selected["selected"]
                if r["task_key"] == key and r["actual_method"] == method
            ]
            assert [r["label"] for r in chosen] == [f"{method}_{key}_{i:02d}" for i in range(1, 5)]


def test_requested_guidance_can_cross_actual_method_strata_with_frozen_tie_order():
    data = rows()
    for row in data:
        row["method_stratum"] = "endpoint" if row["replicate"] <= 4 else "movement"
    selection = fixed_selection(data)
    assert selection["eligible"]["X1"]["endpoint"][:4] == [
        "endpoint_X1_01",
        "movement_X1_01",
        "endpoint_X1_02",
        "movement_X1_02",
    ]
    assert selection["eligible"]["X1"]["movement"][:4] == [
        "endpoint_X1_05",
        "movement_X1_05",
        "endpoint_X1_06",
        "movement_X1_06",
    ]
    assert selection["status"] == "RAW_METHOD_SUPPORT_ESTABLISHED"


@pytest.mark.parametrize(
    "feature", ["financial_invalid", "valid_unmapped", "MIXED", "UNDETERMINED"]
)
def test_any_stratum_shortfall_empties_all_selection(feature):
    data = rows()
    for row in data:
        if row["task_key"] == "X2" and row["arm"] == "movement" and row["replicate"] >= 4:
            if feature == "financial_invalid":
                row.update(
                    formula_driven_trace_verified=False,
                    full_mapping_status="NOT_MEASURED",
                    class_id=None,
                    projection_id=None,
                )
            elif feature == "valid_unmapped":
                row.update(full_mapping_status="UNDETERMINED", class_id=None)
            else:
                row["method_stratum"] = feature
    selection = fixed_selection(data)
    assert selection["status"] == "INPUT_INADEQUATE"
    assert selection["selected"] == []
    assert len(selection["eligible"]["X1"]["endpoint"]) == 8


@pytest.mark.parametrize(
    "key,value",
    [
        ("replicate", 2),
        ("replicate", True),
        ("task_key", "X2"),
        ("arm", "movement"),
        ("condition_id", "E"),
        ("class_id", None),
        ("projection_id", None),
        ("method_record_id", None),
        ("formula_driven_trace_verified", "True"),
    ],
)
def test_review_metadata_cannot_reshuffle_or_invent_admission(key, value):
    data = rows()
    data[0][key] = value
    with pytest.raises(ValueError):
        fixed_selection(data)


def test_exact_32_unique_registered_originals_only():
    data = rows()
    with pytest.raises(ValueError):
        fixed_selection(data[:-1])
    with pytest.raises(ValueError):
        fixed_selection([*data[:-1], data[0]])
    with pytest.raises(ValueError):
        batch_path("E_X2_B2_07")


def test_valid_unmapped_mass_is_not_dropped_from_summary():
    data = rows()[:2]
    for row in data:
        row.update(
            answer={"V_quantity": "PASS"}, trace_status="PASS", guidance_compliance="COMPLIANT"
        )
    data[1].update(full_mapping_status="UNDETERMINED", class_id=None)
    summary = population_summary(data)
    assert summary["complete_valid"] == 2
    assert summary["complete_valid_full_mapped"] == 1
    assert summary["unmapped_valid_mass"] == "1/2"
    assert summary["mapped_mass_among_all_valid_denominator"] == 2
    assert summary["unmapped_valid_mass_dropped_or_renormalized"] is False


def binding_review():
    return {
        "formula_applicability": {"status": "PASS"},
        "target_binding": {
            "parameters": {
                key: "PASS"
                for key in (
                    "local_relation",
                    "public_scope_match",
                    "registered_scope_match",
                    "final_chain_completes_public_target",
                )
            },
            "evidence": [{"response_index": 1, "quote": "actual Final"}],
            "source_evidence": [{"segment_id": "q", "quote": "comparison periods"}],
            "explanation": "The public target and original Final link are checked separately.",
        },
    }


def test_public_target_failure_is_not_repaired_by_local_relation():
    review = binding_review()
    review["target_binding"]["parameters"]["public_scope_match"] = "FAIL"
    raw, doc = {1: "actual Final"}, {"segments": {"q": {"text": "comparison periods"}}}
    with pytest.raises(ValueError, match="formula_field_bound"):
        semantic_binding(review, raw, doc, 1)
    review["formula_applicability"]["status"] = "FAIL"
    result = semantic_binding(review, raw, doc, 1)
    assert result["local_relation_validity"] == "PASS"
    assert result["public_task_applicability"] == "FAIL"


@pytest.mark.parametrize(
    "params,status",
    [
        (
            {
                "role": "DIRECT_SOURCE_VALUE",
                "current": True,
                "source_value_equal": False,
                "consumed": False,
            },
            "FAIL",
        ),
        ({"role": "DIRECT_SOURCE_VALUE", "current": True, "source_value_equal": True}, "PASS"),
        (
            {
                "role": "DERIVED_FROM_SOURCES",
                "current": True,
                "derivation_supported": True,
                "source_value_equal": False,
            },
            "PASS",
        ),
        ({"role": "UNRESOLVED", "current": True, "source_value_equal": False}, "UNDETERMINED"),
    ],
)
def test_current_source_claim_roles_not_consumption_or_numeric_id_only(params, status):
    review = {
        "claim_inventory": {
            "complete": True,
            "reviewed_response_indices": [0, 1],
            "explanation": "Both complete original messages inspected.",
        },
        "source_claims": [
            {
                "parameters": params,
                "evidence": [{"response_index": 0, "quote": "source claim"}],
                "source_evidence": [],
                "location": "arguments",
                "explanation": "Role from actual structure and public context.",
            }
        ],
    }
    result = claim_certification(review, {0: "source claim", 1: "actual Final"}, {"segments": {}})
    assert result["status"] == status
    modified = deepcopy(review)
    modified["claim_inventory"]["reviewed_response_indices"] = [0]
    with pytest.raises(ValueError, match="whole_public_history"):
        claim_certification(modified, {0: "source claim", 1: "actual Final"}, {"segments": {}})


@pytest.mark.parametrize(
    "evidence",
    [
        [{"response_index": 2, "quote": "x"}],
        [{"response_index": 0, "quote": "invented"}],
        [{"response_index": 0, "quote": ""}],
    ],
)
def test_review_cannot_invent_public_evidence(evidence):
    with pytest.raises(ValueError):
        quote_check(evidence, {0: "actual"})


def test_selected_identity_store_is_write_once_and_sealed(tmp_path):
    selection = fixed_selection(rows())
    store = Store(tmp_path / "selection")
    store.json("support_selection.json", selection)
    with pytest.raises(FileExistsError):
        store.json("support_selection.json", selection)
    store.seal(selection_id=selection["id"])
    with pytest.raises(ValueError):
        store.json("replacement.json", {})
    with pytest.raises(ValueError):
        Store(tmp_path / "selection")


def test_raw_review_quotes_preserve_original_crlf_and_cr(tmp_path):
    store = Store(tmp_path / "fixture")
    store.write("turns/000_assistant.raw", b"first\r\nsecond\rthird")
    raw = raw_messages(store.root)
    assert raw == {0: "first\r\nsecond\rthird"}
    quote_check([{"response_index": 0, "quote": "first\r\nsecond"}], raw)
    with pytest.raises(ValueError, match="exact_public_quote"):
        quote_check([{"response_index": 0, "quote": "first\nsecond"}], raw)


@pytest.mark.parametrize("phase", ["original_source_validation", "tokenizer_loading"])
def test_source_or_asset_failures_are_not_scoped_success(phase):
    assert scope_status({"failures": [{"phase": phase}]}) == "STOPPED_SOURCE_OR_ASSET_NOT_CERTIFIED"
    assert scope_status({"failures": []}) == "PASS_AS_SCOPED"
