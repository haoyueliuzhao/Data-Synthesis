"""Isolated dictionary controls using saved Share graphs, never new model evidence.

Fixtures explicitly rebind copied graph dictionaries to synthetic qualifications
and profiles. They are not new Runtime executions or model samples and cannot
enter the formal exploration population. No old source file is changed.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext import measurement as domain
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import qualification
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import read_json, record
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.rules import quotient_rule
from trusted_synthesis.experiments.finance_qa_vnext_support_exploration import quotient

ROOT = Path(__file__).resolve().parents[2]
BASE = (
    ROOT
    / "trusted_data_synthesis/artifacts/qa_vnext_integration"
    / "finance_qa_vnext_unified_entry_v2_20260906/entry"
)
PANEL = (
    ROOT
    / "trusted_data_synthesis/artifacts/qa_vnext_task_panel"
    / "fixed_eight_task_panel_v1_20260906/execution"
)


def forbidden(*args, **kwargs):
    pytest.fail(
        "support quotient tests may not execute, qualify, audit or invoke the old audit comparator"
    )


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(ShareTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(domain, "audit_session", forbidden)
    monkeypatch.setattr(domain, "compare_sessions", forbidden)
    monkeypatch.setattr(qualification, "qualify_session", forbidden)


def reseal(value, kind, *, public=False, **changes):
    fields = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    return (domain.record if public else record)(kind, **(fields | changes))


@pytest.fixture(scope="module")
def source():
    values = {}
    for route, case in (("D", "share_disclosed_total"), ("R", "share_reconstructed_total")):
        values[route] = {
            "session": read_json((BASE / f"sessions/{case}/session.json").read_bytes()),
            "audit": read_json((BASE / f"validations/{case}.json").read_bytes()),
        }
    values["unused"] = {
        "session": read_json((PANEL / "sessions/S02/runtime/session.json").read_bytes()),
        "audit": read_json((PANEL / "analysis/qualifications/S02.json").read_bytes())[
            "domain_audit"
        ],
    }
    return values


@pytest.fixture
def setup(source):
    audit = source["D"]["audit"]
    rule = quotient_rule()
    condition = record(
        "support_exploration_condition",
        **{key: audit[key] for key in quotient.TASK_FIELDS if key != "task_group"},
        task_group="S",
        rule_id=rule["id"],
        registered_session_count=8,
        sessions_per_profile=4,
        registered_labels=quotient.LABELS,
        profiles={
            name: record(
                "support_exploration_profile", profile=name, system_prompt="synthetic test " + name
            )
            for name in quotient.PROFILES
        },
        configurations={
            name: record("transport_config", profile=name, system_prompt="synthetic test " + name)
            for name in quotient.PROFILES
        },
        profile_mixture={name: {"numerator": 1, "denominator": 2} for name in quotient.PROFILES},
        synthetic_dictionary_control=True,
    )
    return source, condition, rule, quotient.comparison_contract(condition, rule)


def entry(setup, label, route="D", status="success"):
    source, condition, _, _ = setup
    profile = label[0]
    registration = record(
        "session_registration",
        label=label,
        profile=profile,
        profile_id=condition["profiles"][profile]["id"],
        model_configuration_id=condition["configurations"][profile]["id"],
        run_condition_id=condition["id"],
        session_id="synthetic-registered:" + label,
        **{key: condition[key] for key in quotient.TASK_FIELDS},
    )
    session = audit = None
    if status in {"success", "known_failure"}:
        original = copy.deepcopy(source[route])
        callback = domain.record(
            "callback_binding", origin="model", synthetic_dictionary_control=label
        )
        session = reseal(original["session"], "session", public=True, callback_binding=callback)
        audit = reseal(
            original["audit"],
            "session_audit",
            public=True,
            session_id=session["id"],
            origin="synthetic_dictionary_control",
            qualified=status == "success",
        )
    success = status == "success"
    known = status in {"success", "known_failure"}
    q = record(
        "qualification",
        registration_id=registration["id"],
        registered_session_id=registration["session_id"],
        session_id=session["id"] if session else None,
        model_configuration_id=registration["model_configuration_id"],
        **{key: condition[key] for key in quotient.TASK_FIELDS},
        status=status,
        qualified=success if known else None,
        end_to_end_success=success if known else None,
        model_origin_verified=known,
        evidence_complete=status != "unknown",
        qa_valid=success,
        trajectory_valid=known,
        export_eligible=success,
        domain_audit=audit,
        domain_audit_id=audit["id"] if audit else None,
        reason=None,
        synthetic_dictionary_control=True,
    )
    export = record(
        "supervision_export",
        qualification_id=q["id"],
        session_id=q["session_id"],
        rows=[],
        candidate_count=0,
    )
    return {
        "label": label,
        "registration": registration,
        "qualification": q,
        "session": session,
        "export": export,
    }


def analyze(setup, entries):
    return quotient.analyze_quotient(entries, setup[1], setup[2], setup[3])


def population(setup, routes=None, statuses=None):
    return [
        entry(setup, label, (routes or {}).get(label, "D"), (statuses or {}).get(label, "success"))
        for label in quotient.LABELS
    ]


def rebind_changed_source(item, *, session=None, audit=None):
    """Reseal test-only dictionary mutations, never qualify them as actual trajectories."""
    changed = copy.deepcopy(item)
    if session is not None:
        changed["session"] = reseal(session, "session", public=True)
    audit = copy.deepcopy(audit if audit is not None else changed["qualification"]["domain_audit"])
    audit = reseal(audit, "session_audit", public=True, session_id=changed["session"]["id"])
    changed["qualification"] = reseal(
        changed["qualification"],
        "qualification",
        session_id=changed["session"]["id"],
        domain_audit=audit,
        domain_audit_id=audit["id"],
    )
    return changed


def test_predeclared_contract_keeps_both_profile_and_configuration_identities(setup):
    contract = setup[3]
    assert contract["maximum_pairs"] == 28 and contract["registered_session_count"] == 8
    assert contract["exploration_condition_id"] == setup[1]["id"]
    assert contract["cross_profile_comparison_predeclared"] is True
    assert contract["profile_names_are_behavior_labels"] is False
    assert contract["profile_config_identity_checks_removed"] is False
    assert contract["exact_profiles"] == setup[1]["profiles"]
    assert contract["exact_configurations"] == setup[1]["configurations"]


def test_same_actual_disclosed_support_in_both_profiles_is_one_class(setup):
    entries = population(setup)
    before = canonical_json_bytes(entries)
    result = analyze(setup, entries)
    assert len(result["pairs"]) == 28 and all(
        pair["relation"] == "equivalent" for pair in result["pairs"]
    )
    assert sum(pair["cross_profile"] for pair in result["pairs"]) == 16
    assert result["class_count"] == 1 and result["assignment_count"] == 8
    assert {row["support"] for row in result["support_rows"]} == {"disclosed_total"}
    assert not result["target_witness"]["established"]
    assert result["all_valid_mapped"] is True
    assert len({item["class_ref_id"] for item in result["assignments"]}) == 1
    assert {item["profile"] for item in result["assignments"]} == {"N", "E"}
    assert canonical_json_bytes(entries) == before


def test_final_denominator_production_and_consumption_give_two_proved_supports(setup):
    routes = {label: "R" for label in quotient.LABELS if label.startswith("E")}
    result = analyze(setup, population(setup, routes))
    assert result["class_count"] == 2 and result["assignment_count"] == 8
    assert result["target_witness"]["established"] is True
    assert len(result["target_witness"]["proof_pairs"]) == 16
    assert sum(pair["relation"] == "not_equivalent" for pair in result["pairs"]) == 16
    for row in result["support_rows"]:
        assert row["proof_verified"] is True
        if row["profile"] == "E":
            assert row["support"] == "reconstructed_total"
            trace = row["trace"]
            assert trace["accepted_total_claim_actually_consumed_by_ratio"] is True
            assert trace["total"]["operation"] == "relation_sum"
            assert trace["total"]["update_sequence"] < trace["ratio"]["action_sequence"]
            assert trace["ratio"]["update_sequence"] < trace["percent"]["action_sequence"]
    assert all(
        pair["comparison"]["generation_condition_id"] == setup[1]["id"] for pair in result["pairs"]
    )


def test_sum_called_but_not_consumed_is_still_disclosed_and_not_target_witness(setup):
    result = analyze(
        setup,
        population(setup, {label: "unused" for label in quotient.LABELS if label.startswith("E")}),
    )
    assert result["class_count"] == 2
    assert {row["support"] for row in result["support_rows"]} == {"disclosed_total"}
    assert result["target_witness"]["established"] is False
    assert any(
        proj["behavior_projection"]["retained_interactions"] for proj in result["projections"]
    )


@pytest.mark.parametrize(
    "change",
    [
        "missing_accept",
        "wrong_raw_denominator",
        "wrong_resolved_denominator",
        "new_claim_not_accepted",
        "final_wrong_claim",
    ],
)
def test_reconstructed_support_requires_actual_accepted_claim_consumption(setup, change):
    entries = population(setup, {"E01": "R"})
    item = entries[1]
    session = copy.deepcopy(item["session"])
    actions = {
        event["parsed"].get("operation"): event
        for event in session["events"]
        if event["parsed"]["kind"] == "action"
    }
    ratio, total = actions["share_ratio"], actions["relation_sum"]
    total_claim = next(
        event["claim"]
        for event in session["events"]
        if event.get("claim") and event["claim"]["observation_id"] == total["observation"]["id"]
    )
    if change == "missing_accept":
        update = next(
            event
            for event in session["events"]
            if event.get("claim", {}).get("id") == total_claim["id"]
        )
        update["parsed"]["disposition"] = "defer"
    elif change == "wrong_raw_denominator":
        next(ref for ref in ratio["parsed"]["inputs"] if ref["role"] == "denominator")["ref_id"] = (
            "invented-claim"
        )
    elif change == "wrong_resolved_denominator":
        next(
            ref
            for ref in ratio["execution"]["resolved_inputs"]
            if ref["value"]["role"] == "denominator"
        )["ref_id"] = "wrong-resolved-claim"
    elif change == "new_claim_not_accepted":
        ratio["request"]["state"]["accepted_claims"] = []
    else:
        session["final"]["answer"]["answer_claim_id"] = total_claim["id"]
    entries[1] = rebind_changed_source(item, session=session)
    result = analyze(setup, entries)
    support = result["support_rows"][1]
    assert support["support"] == "other_or_undetermined" and support["proof_verified"] is False
    assert result["target_witness"]["established"] is False
    assert entries[1]["qualification"]["qualified"] is True


def test_existing_definite_dual_support_survives_unrelated_unknowns(setup):
    statuses = {label: "unknown" for label in quotient.LABELS[2:]}
    result = analyze(setup, population(setup, {"E01": "R"}, statuses))
    assert result["target_witness"]["established"] is True
    assert result["assignment_count"] == 2 and len(result["pairs"]) == 1
    assert len(result["projections"]) == len(result["support_rows"]) == 8
    assert all(
        row["status"] == "ineligible" and row["session_id"] is None
        for row in result["projections"][2:]
    )
    assert all(row["qualification_status"] == "unknown" for row in result["support_rows"][2:])


def test_new_uninterpretable_event_stays_undetermined_without_rule_extension(setup):
    entries = population(setup, {"E01": "R"})
    audit = copy.deepcopy(entries[2]["qualification"]["domain_audit"])
    graph = copy.deepcopy(audit["actual_decision_graph"])
    graph["non_accept_event_ledger"] = [{"sequence": 0, "kind": "new_unknown_effect"}]
    audit["actual_decision_graph"] = reseal(graph, "actual_decision_graph", public=True)
    audit["projection_supported"] = False
    entries[2] = rebind_changed_source(entries[2], audit=audit)
    rule_before = canonical_json_bytes(setup[2])
    result = analyze(setup, entries)
    assert result["projections"][2]["status"] == "undetermined"
    assert result["all_valid_mapped"] is False and len(result["unmapped_qualification_ids"]) == 1
    assert result["target_witness"]["established"] is True
    assert result["complete_class_count"] is None
    assert canonical_json_bytes(setup[2]) == rule_before == canonical_json_bytes(quotient_rule())


def test_undetermined_pair_does_not_create_two_formal_singleton_classes(setup, monkeypatch):
    def unknown(left, right):
        return quotient.frozen_comparison._result(
            left, right, reason="isolated_search_bound_control", new_isomorphism_search=True
        )

    monkeypatch.setattr(quotient.frozen_comparison, "compare_projections", unknown)
    statuses = {label: "known_failure" for label in quotient.LABELS[2:]}
    result = analyze(setup, population(setup, {"E01": "R"}, statuses))
    assert len(result["pairs"]) == 1 and result["pairs"][0]["relation"] == "undetermined"
    assert result["assignments"] == result["classes"] == []
    assert result["all_valid_mapped"] is False and result["target_witness"]["established"] is False


@pytest.mark.parametrize("status", ["known_failure", "unknown", "not_started"])
def test_zero_qualified_preserves_all_eight_without_positive_witness(setup, status):
    result = analyze(
        setup, population(setup, statuses={label: status for label in quotient.LABELS})
    )
    assert len(result["projections"]) == len(result["qualification_ids"]) == 8
    assert (
        result["qualified_count"] == 0
        and result["classes"] == result["assignments"] == result["pairs"] == []
    )
    assert result["target_witness"]["established"] is False
    assert {row["support"] for row in result["support_rows"]} == {"ineligible"}


@pytest.mark.parametrize(
    "field",
    [
        "profile_id",
        "model_configuration_id",
        "run_condition_id",
        "task_id",
        "context_id",
        "protocol_id",
        "registry_hash",
    ],
)
def test_profile_or_generation_parent_mismatch_cannot_be_erased_for_cross_profile_comparison(
    setup, field
):
    entries = population(setup)
    entries[1]["registration"] = reseal(
        entries[1]["registration"], "session_registration", **{field: "foreign-source"}
    )
    with pytest.raises(ProtocolError):
        analyze(setup, entries)


def test_rule_cannot_be_expanded_after_observing_new_corrections(setup):
    changed = reseal(setup[2], "panel_quotient_rule", fallback="accept all new errors")
    condition = reseal(setup[1], "support_exploration_condition", rule_id=changed["id"])
    with pytest.raises(ProtocolError, match="frozen_rule"):
        quotient.comparison_contract(condition, changed)


def test_duplicate_or_missing_new_registration_and_fixture_origin_are_rejected(setup):
    entries = population(setup)
    with pytest.raises(ProtocolError):
        analyze(setup, entries[:-1])
    repeated = copy.deepcopy(entries)
    repeated[-1] = repeated[0]
    with pytest.raises(ProtocolError):
        analyze(setup, repeated)
    session = copy.deepcopy(entries[0]["session"])
    session["callback_binding"]["origin"] = "fixture"
    entries[0] = rebind_changed_source(entries[0], session=session)
    with pytest.raises(ProtocolError, match="independently_qualified_model_source"):
        analyze(setup, entries)


@pytest.mark.parametrize("unknown", [False, True])
def test_exact_quotient_outputs_integrate_with_stratified_measurement(setup, unknown):
    from trusted_synthesis.experiments.finance_qa_vnext_support_exploration.measurement import (
        summarize,
    )

    statuses = {label: "unknown" for label in quotient.LABELS[2:]} if unknown else {}
    entries = population(setup, {"E01": "R"}, statuses)
    result = analyze(setup, entries)
    measured = summarize([item["registration"] for item in entries], entries, result, setup[1])
    assert measured["target_support_witness_established"] is True
    assert measured["registered_denominator"] == 8
    assert measured["qualified_count"] == (2 if unknown else 8)
    if unknown:
        assert measured["conditional_distribution"] is None
        assert measured["success_fraction"] is None
    else:
        assert measured["conditional_distribution"] is not None
        assert measured["success_fraction"] == {"numerator": 8, "denominator": 8}
