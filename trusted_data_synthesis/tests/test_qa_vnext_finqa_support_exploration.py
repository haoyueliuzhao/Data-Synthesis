"""Only new J1/J2 strata, finite operators, actual support and raw-materialization seams."""

import copy
from fractions import Fraction
from pathlib import Path

import pytest

from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.experiments.finance_qa_vnext_finqa_binding_view.runtime import (
    ReadableBindingRuntime,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import (
    equivalent,
    evaluate,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_quotient.stage import zero_execution
from trusted_synthesis.experiments.finance_qa_vnext_finqa_support_exploration import (
    controls,
    distribution,
    judgments,
    materialize,
    plan,
    projection,
    stage,
    support,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.stage import SYSTEM
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    render_http_request,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def panel():
    return Panel(ROOT)


@pytest.fixture(scope="module")
def mock_runs(panel, tmp_path_factory):
    directory = tmp_path_factory.mktemp("new_support_mock")
    out = {}
    for key in ("J1", "J2"):
        for alternative in (False, True):
            for stratum in ("N", "D"):
                r = next(
                    r
                    for r in plan.registrations()
                    if r["task_key"] == key
                    and r["exploration_stratum"] == stratum
                    and r["replicate"] == (2 if alternative else 1)
                )
                sender = controls.Sender(panel.tasks[key], alternative, insert_error=stratum == "D")
                audit = stage.run_one(
                    panel, r, directory, plan.configuration(stratum), None, sender=sender
                )
                session = materialize.load_session(
                    directory / r["label"], r, audit, model_required=False
                )
                review = judgments.template(session)
                for annotation in review["annotations"]:
                    annotation["status"] = "REVIEWED"
                    annotation["public_commitments"] = ["constructed_control_only"]
                p = projection.project(session, review)
                assert p["status"] == "MAPPED"
                out[key, alternative, stratum] = (r, audit, session, review, p)
    return out


def test_fixed_twelve_and_generic_D_only(panel):
    rows = plan.registrations()
    assert len(rows) == len({r["id"] for r in rows}) == 12
    assert [r["label"] for r in rows] == list(plan.LABELS)
    for key in ("J1", "J2"):
        for s in ("N", "D"):
            assert (
                len([r for r in rows if r["task_key"] == key and r["exploration_stratum"] == s])
                == 3
            )
    n, d = plan.configuration("N"), plan.configuration("D")
    assert n.system_prompt == SYSTEM and d.system_prompt == SYSTEM + "\n\n" + plan.D_GUIDANCE
    assert not any(
        x in plan.D_GUIDANCE
        for x in ["2017", "2016", "33.32", "18.1", "Claim", "multiply", "divide"]
    )
    r = ReadableBindingRuntime(panel, "J1", "E", "same_id", view_condition="V1").request()
    hn, hd = (render_http_request(r, c, session_id="same_id", attempt_index=0) for c in (n, d))
    assert hn["messages"][1] == hd["messages"][1]
    assert n.as_record()["maximum_pilot_reserved_tokens"] == 41287680
    assert "decomposition exploration" in d.as_record()["messages_policy"]


@pytest.mark.parametrize(
    "key,alternative,count,value",
    [
        ("J1", False, 9, Fraction(1200, 47)),
        ("J1", True, 10, Fraction(1200, 47)),
        ("J2", False, 7, Fraction(1643, 100)),
        ("J2", True, 9, Fraction(1643, 100)),
    ],
)
def test_two_route_math_exact_execution_and_consumption(
    panel, mock_runs, key, alternative, count, value
):
    task = panel.tasks[key]
    tree = controls.route(task, alternative)
    assert evaluate(tree, task["facts"]) == value
    assert equivalent(tree, task["target"], task["facts"], task["relations"])
    if key == "J1":
        assert [Fraction(task["facts"][s]["value"]) for s in task["selected"]] == [
            Fraction("18.1"),
            Fraction("-6.3"),
            Fraction("14.6"),
            Fraction("-5.2"),
        ]
    for stratum in ("N", "D"):
        _, audit, session, _, p = mock_runs[key, alternative, stratum]
        assert audit["complete_valid"] and audit["actions"] == count
        assert audit["submissions"] == 2 * count + 1 + (stratum == "D")
        assert p["final_support_operations"] == count
        assert not audit["model_origin_verified"]
        assert (
            projection.compare(p["support_graph"], support.support_graph(session))["relation"]
            == "EQUIVALENT"
        )
        w = support.witnesses(audit)
        expected = (
            ("signed_component_changes" if alternative else "annual_net_costs")
            if key == "J1"
            else ("quantity_base_price_plus_price_new_quantity" if alternative else "annual_totals")
        )
        assert next(row for row in w["routes"] if row["name"] == expected)["established"]


@pytest.mark.parametrize("key", ["J1", "J2"])
def test_new_support_differs_and_prompt_label_alone_does_not(mock_runs, key):
    a = mock_runs[key, False, "N"][4]
    b = mock_runs[key, True, "N"][4]
    assert projection.compare(a["support_graph"], b["support_graph"])["relation"] == "DIFFERENT"
    d = mock_runs[key, False, "D"][4]
    assert projection.compare(a["support_graph"], d["support_graph"])["relation"] == "EQUIVALENT"
    assert (
        projection.compare(a["graph"], d["graph"])["relation"] == "DIFFERENT"
    )  # inserted raw rejection


def test_add_commutes_divide_does_not_and_constant_is_not_source(mock_runs):
    for op, equal in (("add", True), ("multiply", True), ("divide", False), ("subtract", False)):
        left = projection.expression({"op": op, "args": ["constant:100", "source:x"]})
        right = projection.expression({"op": op, "args": ["source:x", "constant:100"]})
        assert (left == right) == equal
    g = mock_runs["J1", True, "N"][4]["graph"]
    assert g["nodes"]["constant:100"]["kind"] == "constant"
    bad = copy.deepcopy(g)
    bad["nodes"]["constant:100"]["kind"] = "source"
    assert projection.compare(g, bad)["relation"] == "DIFFERENT"


def test_unknown_public_mapping_keeps_actual_support_and_raw_targets(mock_runs):
    _, audit, session, review, _ = mock_runs["J1", True, "D"]
    review = copy.deepcopy(review)
    review["annotations"][0]["status"] = "UNDETERMINED"
    p = projection.project(session, review)
    assert p["status"] == "UNDETERMINED"
    assert support.support_graph(session)["nodes"]
    rows = [materialize.candidate(session, t) for t in session["turns"] if t["event"]["admitted"]]
    assert len(rows) == 21 and all(r["task_key"] == "J1" for r in rows)
    assert all(plan.D_GUIDANCE in r["messages"][0]["content"] for r in rows)
    for row in rows:
        turn = session["turns"][row["submission"] - 1]
        assert row["target_text"].encode() == turn["raw"]
        assert not row["host_display_is_target"]
    assert len(session["turns"]) == 22 and not session["turns"][0]["event"]["admitted"]


def test_unadmitted_or_failed_samples_do_not_become_targets(mock_runs):
    r, audit, session, _, _ = mock_runs["J2", False, "D"]
    with pytest.raises(ProtocolError, match="admitted_only"):
        materialize.candidate(session, session["turns"][0])
    with pytest.raises(ProtocolError, match="complete_valid_only"):
        materialize.load_session(Path("/does_not_exist"), r, {**audit, "complete_valid": False})


def test_unused_intermediates_do_not_prove_decomposition(mock_runs):
    audit = copy.deepcopy(mock_runs["J2", True, "N"][1])
    for row in audit["recovery_trace"]["operations"]:
        row["consumed_by_valid_final"] = False
    assert all(not r["established"] for r in support.witnesses(audit)["routes"])


def synthetic_population(mock_runs):
    rows = plan.registrations()
    audits, projections = [], {}
    for row in rows:
        valid = row["exploration_stratum"] == "N" or row["replicate"] == 1
        p = copy.deepcopy(mock_runs[row["task_key"], row["exploration_stratum"] == "D", "N"][4])
        projections[row["label"]] = p
        audits.append({**row, "complete_valid": valid})
    return rows, audits, projections


def test_equal_source_mixture_is_not_equal_success_conditionals(mock_runs):
    rows, audits, projections = synthetic_population(mock_runs)
    m = distribution.measure(rows, audits, projections)
    for task in m["tasks"].values():
        assert task["complete_valid"] == 4 and task["mixture_success_fraction"] == "2/3"
        assert sorted(r["mass"] for r in task["graph"]["pi"]) == ["1/4", "3/4"]
        assert (
            task["strata"]["N"]["complete_valid"] == 3
            and task["strata"]["D"]["complete_valid"] == 1
        )


def test_unknown_valid_mass_not_dropped_and_same_graph_can_cross_strata(mock_runs):
    rows, audits, ps = synthetic_population(mock_runs)
    ps["J2_D_01"]["graph"] = None
    m = distribution.measure(rows, audits, ps)
    assert m["tasks"]["J2"]["graph"]["pi"] is None
    assert m["tasks"]["J2"]["graph"]["unknown_valid_mass"] == "1/4"
    ps["J2_D_01"]["graph"] = ps["J2_N_01"]["graph"]
    m = distribution.measure(rows, audits, ps)
    law = m["tasks"]["J2"]["graph"]
    assert len(law["states"]) == 1 and law["pi"][0]["mass"] == "1"
    assert law["states"][0]["origin_given_class"] == {"N": "3/4", "D": "1/4"}


def test_posthoc_quote_changes_fail_and_unsupported_lifecycle_stays_unknown(mock_runs):
    _, _, session, review, _ = mock_runs["J2", False, "N"]
    changed = copy.deepcopy(review)
    changed["annotations"][0]["reason_quote"] = "invented"
    with pytest.raises(ProtocolError, match="original_quotes"):
        projection.project(session, changed)
    changed_session = copy.deepcopy(session)
    changed_session["turns"][1]["event"]["model_submission"]["kind"] = "action"
    assert projection.project(changed_session, review)["status"] == "UNDETERMINED"


def test_closeout_guard_forbids_runtime_and_student():
    with zero_execution() as counts:
        with pytest.raises(RuntimeError):
            ReadableBindingRuntime(None, "J1", "E", "forbidden", view_condition="V1")
        assert counts["numeric_runtime_construction"] == 1


def test_zero_success_and_unknown_outcome_do_not_get_complete_laws(mock_runs):
    rows, audits, ps = synthetic_population(mock_runs)
    for audit in audits:
        if audit["task_key"] == "J1":
            audit["complete_valid"] = False
        if audit["label"] == "J2_D_03":
            audit["status"] = "unknown"
    result = distribution.measure(rows, audits, ps)
    assert result["tasks"]["J1"]["graph"]["pi"] is None
    assert result["tasks"]["J1"]["complete_valid"] == 0
    assert result["tasks"]["J2"]["mixture_success_fraction"] is None
    assert result["tasks"]["J2"]["graph"]["pi"] is None
    assert result["tasks"]["J2"]["unknown_outcomes"] == ["J2_D_03"]


def test_named_probe_requires_actual_publication_cut(mock_runs):
    audit = copy.deepcopy(mock_runs["J2", True, "N"][1])
    for final in audit["recovery_trace"]["final_attempts"]:
        final["answer_claim_id"] = "different_occurrence_control"
    assert all(not row["established"] for row in support.witnesses(audit)["routes"])
