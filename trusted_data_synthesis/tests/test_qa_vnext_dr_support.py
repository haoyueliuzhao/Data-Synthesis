"""New bounded-batch controls; no real Provider, Student or tokenizer execution."""

import json
import subprocess
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_dr_support.core import Store, credential
from trusted_synthesis.experiments.finance_qa_vnext_dr_support.plan import (
    CONDITIONS,
    LABELS,
    MODEL,
    OLD,
    OLD_LABELS,
    SYSTEM,
    WORKER_PYTHON,
    package_mass,
    registrations,
    sampling_policy,
    select_support,
    target_ledger,
)
from trusted_synthesis.experiments.finance_qa_vnext_dr_support.review import (
    claim_certification,
    quote_check,
    semantic_binding,
)
from trusted_synthesis.experiments.finance_qa_vnext_dr_support.source import batch_path
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.capsule import (
    capsule_files,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import condition
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    encode,
    write,
)

ROOT = Path(__file__).resolve().parents[2]


def public():
    return json.loads((ROOT / OLD / "preparation/public/X2.json").read_bytes())


def row(label, route, valid=True):
    return {"label": label, "behavior": route, "formula_driven_trace_verified": valid}


def test_exact_fixed_registrations_and_separate_identity():
    rows = registrations(public())
    assert len(rows) == len({r["label"] for r in rows}) == 32
    assert set(r["label"] for r in rows).isdisjoint(OLD_LABELS)
    assert [r["replicate"] for r in rows] == list(range(1, 33))
    assert Counter(r["wave"] for r in rows) == {1: 24, 2: 8}
    assert len({r["review_id"] for r in rows}) == 32
    assert {r["requested_model"] for r in rows} == {MODEL}
    assert {r["generative_condition_id"] for r in rows} == {condition("E")["id"]}


@pytest.mark.parametrize(
    "key,value",
    [
        ("new_sessions", 32),
        ("maximum_generation_requests", 1024),
        ("network_retries_fallbacks_replacement_sessions_or_topups", 0),
        ("model_catalog_or_calibration_requests", 0),
        ("minimum_per_class", 4),
        ("this_stage_Student_training_or_evaluation", 0),
        ("historical_8_and_new_32_denominators_separate", True),
        ("same_provider_weights_dates_or_natural_sampling_law_claimed", False),
        ("no_replacement_after_selected_token_failure", True),
        ("heldout_training_greedy_and_NLL", 0),
        ("numeric_ID_only_gate", False),
        ("stop_regardless_of_support_count", True),
    ],
)
def test_frozen_budget_and_claim_limits(key, value):
    assert sampling_policy()[key] == value


def test_source_identity_and_public_target_ledger():
    private = json.loads((ROOT / OLD / "preparation/private/evaluation_targets.json").read_bytes())[
        "X2"
    ]
    ledger = target_ledger(public(), private)
    assert ledger["alignment"] == "ALIGNED"
    assert "December 31, 2006" in ledger["interval"]
    assert set(ledger["source_anchors"]) == {"q9", "q10", "q11", "q12", "q13", "q14"}
    with pytest.raises(ValueError):
        target_ledger({**public(), "question": "What is the percentage change?"}, private)


@pytest.mark.parametrize("arm", CONDITIONS)
def test_exact_weights_and_all_task_marginals(arm):
    items = [(task, "control") for task in ("G1", "G2", "F1", "X1") for _ in range(3)]
    items += [("X3C", route) for route in ("D", "A") for _ in range(3)]
    items += [("X2", route) for route in ("D", "R") for _ in range(3)]
    assert len(items) == 24
    assert sum(package_mass(arm, task, route) for task, route in items) == 1
    for task in {task for task, _ in items}:
        assert sum(
            package_mass(arm, key, route) for key, route in items if key == task
        ) == Fraction(1, 6)
    assert package_mass(arm, "X3C", "D") == package_mass(arm, "X3C", "A") == Fraction(1, 36)


@pytest.mark.parametrize("arm,delta", [("plus_R", Fraction(1, 36)), ("minus_R", Fraction(-1, 36))])
def test_global_target_class_mass_move(arm, delta):
    assert 3 * (package_mass(arm, "X2", "R") - package_mass("pi0", "X2", "R")) == delta
    assert 3 * (package_mass(arm, "X2", "D") - package_mass("pi0", "X2", "D")) == -delta


@pytest.mark.parametrize(
    "arm,task,route",
    [
        ("unregistered", "X2", "D"),
        ("pi0", "X2", "A"),
        ("plus_R", "X3C", "R"),
        ("pi0", "other", "D"),
    ],
)
def test_no_wrong_axis_or_new_class(arm, task, route):
    with pytest.raises(ValueError):
        package_mass(arm, task, route)


def test_support_order_is_batch_then_replicate_not_quality_or_completion():
    rows = [row(label, "PURE_D") for label in OLD_LABELS[:4]]
    rows += [row(OLD_LABELS[7], "PURE_R")]
    rows += [row(label, "PURE_R") for label in LABELS[:4]]
    selected = select_support(list(reversed(rows)))
    assert selected["status"] == "RAW_SUPPORT_ESTABLISHED"
    assert selected["train"]["D"] == list(OLD_LABELS[:3])
    assert selected["heldout"]["D"] == OLD_LABELS[3]
    assert selected["train"]["R"] == [OLD_LABELS[7], *LABELS[:2]]
    assert selected["heldout"]["R"] == LABELS[2]
    assert selected["training_allowed"] is False
    assert len(selected["token_check"]["R"]) == 4


@pytest.mark.parametrize(
    "bad",
    [
        "R_WITH_CROSS_CHECK",
        "R_WITH_SUBSTANTIVE_REVISION",
        "OTHER_VALID_CLASS",
        "UNDETERMINED",
        "NOT_JOINT_VALID",
    ],
)
def test_other_valid_or_unknown_class_is_not_pure_R(bad):
    rows = [row(label, "PURE_D") for label in OLD_LABELS[:4]]
    rows += [row(label, "PURE_R") for label in LABELS[:3]] + [row(LABELS[3], bad)]
    selected = select_support(rows)
    assert selected["status"] == "INPUT_INADEQUATE"
    assert selected["train"] == selected["heldout"] == selected["token_check"] == {}


def test_invalid_original_R_does_not_fill_support():
    rows = [row(label, "PURE_D") for label in OLD_LABELS[:4]]
    rows += [row(label, "PURE_R", i < 3) for i, label in enumerate(LABELS[:4])]
    assert select_support(rows)["status"] == "INPUT_INADEQUATE"


def test_duplicate_or_unregistered_candidate_rejected():
    with pytest.raises(ValueError):
        select_support([row(OLD_LABELS[0], "PURE_D")] * 2)
    with pytest.raises(ValueError):
        select_support([row("N_X2_01", "PURE_D")])
    with pytest.raises(ValueError):
        batch_path("E_X2_B2_33")


def binding_review(*, local="PASS", scope="PASS", final="PASS", status="PASS"):
    return {
        "formula_applicability": {"status": status},
        "target_binding": {
            "parameters": {
                "local_relation": local,
                "public_scope_match": scope,
                "registered_scope_match": "PASS",
                "final_chain_completes_public_target": final,
            },
            "evidence": [{"response_index": 1, "quote": "Final six million"}],
            "source_evidence": [{"segment_id": "q", "quote": "year ends"}],
            "explanation": "The declared period and actual final chain are assessed separately.",
        },
    }


def test_local_correctness_cannot_supply_public_target_applicability():
    raw = {1: "Final six million"}
    doc = {"segments": {"q": {"text": "two named year ends"}}}
    with pytest.raises(ValueError, match="formula_field_bound"):
        semantic_binding(binding_review(scope="FAIL"), raw, doc, 1)
    actual = semantic_binding(binding_review(scope="FAIL", status="FAIL"), raw, doc, 1)
    assert actual["local_relation_validity"] == "PASS"
    assert actual["public_task_applicability"] == "FAIL"


def claim_review(params, **extras):
    return {
        "claim_inventory": {
            "complete": True,
            "reviewed_response_indices": [0, 1],
            "explanation": "Both public responses read.",
        },
        "source_claims": [
            {
                "parameters": params,
                "evidence": [{"response_index": 0, "quote": "value source"}],
                "source_evidence": [],
                "location": "arguments",
                "explanation": "Actual public contract and context, not adjacency alone.",
                **extras,
            }
        ],
    }


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
        (
            {
                "role": "DIRECT_SOURCE_VALUE",
                "current": True,
                "source_value_equal": True,
                "consumed": False,
            },
            "PASS",
        ),
        ({"role": "UNRESOLVED", "current": True, "source_value_equal": False}, "UNDETERMINED"),
        (
            {
                "role": "DERIVED_FROM_SOURCES",
                "current": True,
                "derivation_supported": True,
                "source_value_equal": False,
            },
            "PASS",
        ),
        (
            {"role": "GENERAL_REFERENCE", "current": True, "reference_relevant": None},
            "UNDETERMINED",
        ),
    ],
)
def test_current_claim_roles_not_consumption_or_equal_number_gate(params, status):
    observed = claim_certification(
        claim_review(params), {0: "value source", 1: "correct Final"}, {"segments": {}}
    )
    assert observed["status"] == status


def test_later_good_Final_does_not_withdraw_old_claim():
    review = claim_review(
        {"role": "DIRECT_SOURCE_VALUE", "current": False, "withdrawal_supported": True}
    )
    with pytest.raises(ValueError, match="actual_withdrawal"):
        claim_certification(review, {0: "value source", 1: "correct Final"}, {"segments": {}})


def test_unambiguous_replacement_must_have_actual_quote():
    review = claim_review(
        {"role": "DIRECT_SOURCE_VALUE", "current": False, "withdrawal_supported": True},
        withdrawal_evidence=[{"response_index": 1, "quote": "replace previous source"}],
    )
    result = claim_certification(
        review, {0: "value source", 1: "replace previous source"}, {"segments": {}}
    )
    assert result["claims"][0]["interpretation"]["status"] == "NOT_CURRENT"


def test_withdrawal_cannot_precede_the_statement():
    review = claim_review(
        {"role": "DIRECT_SOURCE_VALUE", "current": False, "withdrawal_supported": True},
        withdrawal_evidence=[{"response_index": 0, "quote": "earlier sentence"}],
    )
    review["source_claims"][0]["evidence"] = [{"response_index": 1, "quote": "later claim"}]
    with pytest.raises(ValueError, match="withdrawal_not_before"):
        claim_certification(review, {0: "earlier sentence", 1: "later claim"}, {"segments": {}})


def test_absent_Final_cannot_be_completed_by_private_target():
    doc = {"segments": {"q": {"text": "two named year ends"}}}
    with pytest.raises(ValueError, match="absent_Final"):
        semantic_binding(binding_review(), {1: "Final six million"}, doc, None)


@pytest.mark.parametrize(
    "items",
    [
        [{"response_index": 3, "quote": "x"}],
        [{"response_index": 0, "quote": ""}],
        [{"response_index": 0, "quote": "invented"}],
    ],
)
def test_no_invented_response_evidence(items):
    with pytest.raises(ValueError):
        quote_check(items, {0: "actual"})


def test_stage_write_once_and_sealed_member_set(tmp_path):
    store = Store(tmp_path / "stage")
    store.json("report.json", {"status": "fixture"})
    with pytest.raises(FileExistsError):
        store.json("report.json", {"status": "overwrite"})
    store.seal()
    with pytest.raises(ValueError):
        store.json("later.json", {})
    with pytest.raises(ValueError):
        Store(tmp_path / "stage")


def test_literal_credential_reader_never_sources_shell(tmp_path):
    path = tmp_path / "fixture.env"
    write(tmp_path, "fixture.env", b"export DEEPSEEK_API_KEY='fixture_literal_123'\n")
    assert credential(path) == "fixture_literal_123"


@pytest.mark.parametrize("kind", ["first_Final", "unconsumed_metadata", "response_cap"])
def test_unchanged_isolated_worker_scripted_only(tmp_path, kind):
    code = tmp_path / "code"
    for name, raw in capsule_files(ROOT, "E").items():
        assert raw == (ROOT / OLD / "preparation/worker_code/E" / name).read_bytes()
        write(code, name, raw)
    write(tmp_path, "public.json", encode(public()))
    write(tmp_path, "private.json", b'{"fixture_private":"forbidden"}')
    if kind == "first_Final":
        script = [{"final": "ungraded"}, {"tool": "calculate", "arguments": {"expression": "1+1"}}]
    elif kind == "unconsumed_metadata":
        script = [
            {
                "tool": "calculate",
                "arguments": {
                    "expression": "10-4",
                    "variables": {
                        "value": 6,
                        "source": "not a consumed scalar",
                        "unit": "millions",
                    },
                },
            },
            {"final": {"value": 6, "unit": "USD_million", "result_id": "tool:1"}},
        ]
    else:
        script = [{"message": "fixture message"}] * 33
    write(tmp_path, "script.json", encode(script))
    completed = subprocess.run(
        [
            WORKER_PYTHON,
            "-I",
            "-S",
            "-B",
            str(code / "worker.py"),
            "--public",
            str(tmp_path / "public.json"),
            "--output",
            str(tmp_path / "result"),
            "--forbidden",
            str(tmp_path / "private.json"),
            "--script",
            str(tmp_path / "script.json"),
            "--model",
            MODEL,
        ],
        cwd=code,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode()
    result = json.loads((tmp_path / "result/result.json").read_bytes())
    isolation = json.loads((tmp_path / "result/isolation.json").read_bytes())
    assert result["provider_attempts"] == 0
    assert isolation["private_read_denied_before_provider"]
    assert not isolation["repository_modules_loaded"]
    assert (
        json.loads((tmp_path / "result/turns/000_http_request.body").read_bytes())["messages"][0][
            "content"
        ]
        == SYSTEM
    )
    if kind == "first_Final":
        assert result["model_requests"] == 1 and result["tool_calls"] == 0
    elif kind == "unconsumed_metadata":
        calculation = result["events"][0]["tool_call"]["output"]["result"]
        assert calculation["exact_value"] == "6" and calculation["resolved_variables"] == {}
    else:
        assert result["model_requests"] == 32 and result["terminal"] == "response_budget_exhausted"
