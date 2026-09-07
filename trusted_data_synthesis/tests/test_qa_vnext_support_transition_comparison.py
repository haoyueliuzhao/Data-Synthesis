"""Read-only comparison controls on copies of the three published valid trajectories.

Synthetic sidecars below isolate comparison behavior, not new model trajectories.
The final integration test also invokes the new read-only projector, without
re-running old support detection, qualification, execution or tokenization.
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
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient import comparison as original
from trusted_synthesis.experiments.finance_qa_vnext_support_exploration import (
    quotient as old_support,
)
from trusted_synthesis.experiments.finance_qa_vnext_support_transition import comparison

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT
    / "trusted_data_synthesis/artifacts/qa_vnext_support_exploration"
    / "share_four_neutral_four_guided_v1_20260907"
)


def forbidden(*args, **kwargs):
    pytest.fail(
        "transition comparison attempted old support detection, audit, qualification or execution"
    )


@pytest.fixture(autouse=True)
def zero_execution_and_no_old_support_recomputation(monkeypatch):
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(ShareTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(domain, "audit_session", forbidden)
    monkeypatch.setattr(domain, "compare_sessions", forbidden)
    monkeypatch.setattr(qualification, "qualify_session", forbidden)
    monkeypatch.setattr(old_support, "actual_support", forbidden)
    monkeypatch.setattr(old_support, "comparison_contract", forbidden)


def reseal(value, kind, **changes):
    return record(
        kind,
        **(
            {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
            | changes
        ),
    )


@pytest.fixture(scope="module")
def saved():
    generation = read_json((SOURCE / "preparation/condition.json").read_bytes())
    registrations = read_json((SOURCE / "preparation/registrations.json").read_bytes())
    quotient = read_json((SOURCE / "execution/analysis/quotient.json").read_bytes())
    report = read_json((SOURCE / "execution/analysis/report.json").read_bytes())
    old_projections = {value["label"]: value for value in quotient["projections"]}
    supports = {value["label"]: value for value in quotient["support_rows"]}
    entries = []
    for registration in registrations:
        label = registration["label"]
        q = read_json((SOURCE / f"execution/sessions/{label}/qualification.json").read_bytes())
        session = read_json(
            (SOURCE / f"execution/sessions/{label}/runtime/session.json").read_bytes()
        )
        audit = q["domain_audit"]
        entries.append(
            {
                "label": label,
                "registration": registration,
                "qualification": q,
                "session": session,
                "audit": audit,
                "graph": audit["actual_decision_graph"],
                "old_projection": old_projections[label],
                "old_behavior": old_projections[label]["behavior_projection"],
                "old_finite_projection": audit["finite_projection"],
                "old_support": supports[label],
            }
        )
    return {
        "generation": generation,
        "entries": entries,
        "old_quotient": quotient,
        "old_report": report,
    }


def measurement_condition(saved, rule):
    entries = saved["entries"]
    return record(
        "support_transition_condition",
        generation_condition_id=saved["generation"]["id"],
        original_generation_rule_id=saved["generation"]["rule_id"],
        rule_id=rule["id"],
        registration_ids=[entry["registration"]["id"] for entry in entries],
        qualification_ids=[entry["qualification"]["id"] for entry in entries],
        session_ids=[entry["session"]["id"] for entry in entries],
        qualified_qualification_ids=[
            entry["qualification"]["id"] for entry in entries if entry["qualification"]["qualified"]
        ],
        old_quotient_id=saved["old_quotient"]["id"],
        old_report_id=saved["old_report"]["id"],
        old_comparison_contract_id=saved["old_quotient"]["comparison_contract_id"],
        source_anchor_id="isolated-original-source-reference",
        source_binding_checks_id="isolated-source-binding-reference",
        implementation_id="isolated-test-implementation-reference",
        frozen_outcomes=[
            {
                "label": entry["label"],
                "registration_id": entry["registration"]["id"],
                "qualification_id": entry["qualification"]["id"],
                "session_id": entry["session"]["id"],
                **{
                    key: entry["qualification"][key]
                    for key in ("qualified", "end_to_end_success", "status")
                },
            }
            for entry in entries
        ],
        synthetic_measurement_control=True,
    )


def controlled_projection(entry, condition, generation, rule, contract):
    old = entry["old_projection"]
    fields = copy.deepcopy(
        {key: item for key, item in old.items() if key not in {"id", "schema_version"}}
    )
    fields.update(
        rule_id=rule["id"],
        generation_condition_id=generation["id"],
        measurement_condition_id=condition["id"],
        comparison_contract_id=contract["id"],
        previous_projection_id=old["id"],
        previous_projection_supported=old["supported"],
        old_support_id=entry["old_support"]["id"],
        synthetic_comparison_control=True,
    )
    if entry["label"] in {"N03", "E02"}:
        relations = [
            {
                "kind": "isolated_support_transition_semantic_control",
                "original_proposal_denominator_kind": "evidence",
                "actual_ratio": {"producer_action": "action:1"},
                "accepted_total": {"producer_action": "action:0"},
            }
        ]
        if entry["label"] == "E02":
            relations.append(
                {
                    "kind": "isolated_grounding_assertion_control",
                    "answer_producer": {"producer_action": "action:2"},
                    "support_assertion_replaced": True,
                }
            )
        fields.update(
            status="supported",
            supported=True,
            behavior_projection={
                **copy.deepcopy(entry["old_finite_projection"]),
                "retained_interactions": relations,
            },
        )
        for row in fields["interpretation_ledger"]:
            if row["disposition"] == "undetermined":
                row["disposition"] = "retained_behavior_relation"
    return record("panel_quotient_projection", **fields)


@pytest.fixture
def prepared(saved):
    rule = record(
        "support_transition_rule",
        extends_rule_id=saved["generation"]["rule_id"],
        scope="isolated comparison controls, not formal interpreted trajectories",
    )
    condition = measurement_condition(saved, rule)
    contract = comparison.comparison_contract(condition, saved["generation"], rule)
    projections = [
        controlled_projection(entry, condition, saved["generation"], rule, contract)
        for entry in saved["entries"]
    ]
    return condition, rule, contract, projections


def compare(saved, prepared, *, entries=None, projections=None):
    condition, rule, contract, original_projections = prepared
    return comparison.compare_all(
        entries or saved["entries"],
        original_projections if projections is None else projections,
        condition,
        saved["generation"],
        rule,
        contract,
    )


def test_new_measurement_contract_does_not_rewrite_original_generation_or_profiles(saved, prepared):
    before = canonical_json_bytes(saved["generation"])
    condition, rule, contract, _ = prepared
    assert contract["measurement_condition_id"] == condition["id"]
    assert contract["rule_id"] == rule["id"] != saved["generation"]["rule_id"]
    assert contract["generation_condition_id"] == saved["generation"]["id"]
    assert contract["original_profiles"] == saved["generation"]["profiles"]
    assert contract["original_configurations"] == saved["generation"]["configurations"]
    assert contract["old_comparison_contract_id"] == saved["old_quotient"]["comparison_contract_id"]
    assert contract["old_generation_rule_replaced"] is False
    assert contract["original_parent_identity_checks_removed"] is False
    assert contract["registered_pairs"] == [
        {"left_label": "N03", "right_label": "E04"},
        {"left_label": "N03", "right_label": "E02"},
        {"left_label": "E02", "right_label": "E04"},
    ]
    assert canonical_json_bytes(saved["generation"]) == before


def test_all_three_pairs_and_specific_actual_denominator_contrasts_are_retained(saved, prepared):
    original_bytes = canonical_json_bytes(saved)
    pairs = compare(saved, prepared)
    assert [(pair["left_label"], pair["right_label"]) for pair in pairs] == list(
        comparison.PAIR_LABELS
    )
    for pair in (pairs[0], pairs[2]):
        assert pair["relation"] == "not_equivalent" and pair["proof_verified"] is True
        contrast = pair["execution_support_contrast"]
        assert contrast["verified"] is contrast["established"] is True
        assert contrast["distinct_support_kinds"] is True
        assert contrast["decisive_input_role"] == "denominator"
        assert contrast["left_support"] == "reconstructed_total"
        assert contrast["right_support"] == "disclosed_total"
        assert contrast["left"]["denominator"] == {
            "kind": "claim",
            "role": "denominator",
            "reference": {"producer_action": "action:0"},
        }
        assert contrast["right"]["denominator"]["kind"] == "evidence"
        assert contrast["left"]["sum_producer"]["operation"] == "relation_sum"
        assert (
            contrast["left"]["sum_producer"]["node_id"]
            in contrast["left"]["actual_input_dependencies"]
        )
        assert contrast["actual_support_detection_reexecuted"] is False
        assert contrast["claimed_rejected_proposal_was_executed"] is False
        assert pair["witness"] == pair["comparison"]["witness"]
    assert canonical_json_bytes(saved) == original_bytes


def test_same_action_count_and_final_do_not_erase_real_D_R_dependency_difference(saved, prepared):
    entries = {entry["label"]: entry for entry in saved["entries"]}
    left, right = entries["N03"]["old_finite_projection"], entries["E04"]["old_finite_projection"]
    assert len(left["nodes"]) == len(right["nodes"]) == 3
    assert left["final"]["result"] == right["final"]["result"]
    pair = compare(saved, prepared)[0]
    assert pair["witness"]["kind"] == "retained_action_semantics"
    assert (
        pair["execution_support_contrast"][
            "difference_is_actual_input_kind_not_profile_or_rejection_count"
        ]
        is True
    )


def test_isolated_identical_behavior_controls_do_not_split_by_original_profile(saved, prepared):
    projections = copy.deepcopy(prepared[3])
    by_label = {projection["label"]: projection for projection in projections}
    left, right = by_label["N03"], by_label["E02"]
    assert (
        left["profile"] != right["profile"]
        and left["model_configuration_id"] != right["model_configuration_id"]
    )
    assert {key: left["behavior_projection"][key] for key in ("nodes", "final")} == {
        key: right["behavior_projection"][key] for key in ("nodes", "final")
    }
    graph = copy.deepcopy(left["behavior_projection"])
    projections[projections.index(right)] = reseal(
        right, "panel_quotient_projection", behavior_projection=graph
    )
    pair = compare(saved, prepared, projections=projections)[1]
    assert pair["relation"] == "equivalent" and pair["correspondence"]
    assert pair["execution_support_contrast"]["distinct_support_kinds"] is False


@pytest.mark.parametrize("labels", [("E02",), ("N03",), ("N03", "E02")])
def test_unsupported_pairs_still_have_all_registered_records(saved, prepared, labels):
    projections = [
        reseal(
            value,
            "panel_quotient_projection",
            status="undetermined",
            supported=False,
            behavior_projection=None,
        )
        if value["label"] in labels
        else value
        for value in prepared[3]
    ]
    pairs = compare(saved, prepared, projections=projections)
    assert len(pairs) == 3
    for pair in pairs:
        if {pair["left_label"], pair["right_label"]} & set(labels):
            assert pair["relation"] == "undetermined" and pair["equivalent"] is None
            assert pair["proof_verified"] is False
            assert pair["execution_support_contrast"]["verified"] is True
            assert pair["execution_support_contrast"]["established"] is False
    if labels == ("E02",):
        assert pairs[0]["execution_support_contrast"]["established"] is True


def test_comparator_equivalence_conflicting_with_preserved_D_R_support_is_rejected(
    saved, prepared, monkeypatch
):
    def forged(left, right):
        return original._result(
            left,
            right,
            correspondence={"action:0": "action:0", "action:1": "action:1", "action:2": "action:2"},
            new_isomorphism_search=True,
        )

    monkeypatch.setattr(comparison, "compare_projections", forged)
    with pytest.raises(ProtocolError, match="denominator_semantics_preservation_violation"):
        compare(saved, prepared)


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "qualification_parent",
        "profile",
        "profile_id",
        "model_configuration_id",
        "generation_condition_id",
        "rule_id",
        "previous_projection_id",
        "old_support_id",
        "old_domain_support_flag",
    ],
)
def test_exact_population_and_new_to_original_identity_chain_are_required(saved, prepared, change):
    projections = copy.deepcopy(prepared[3])
    if change == "missing":
        projections.pop()
    elif change == "duplicate":
        projections[-1] = projections[0]
    else:
        index = next(i for i, value in enumerate(projections) if value["label"] == "N03")
        field = {
            "qualification_parent": "qualification_id",
            "old_domain_support_flag": "old_projection_supported",
        }.get(change, change)
        projections[index] = reseal(
            projections[index],
            "panel_quotient_projection",
            **{field: True if change == "old_domain_support_flag" else "foreign-parent"},
        )
    with pytest.raises(ProtocolError):
        compare(saved, prepared, projections=projections)


@pytest.mark.parametrize(
    "change",
    ["remove_sum", "change_denominator", "e04_extension", "old_disposition", "failed_promotion"],
)
def test_original_graph_and_previous_supported_semantics_cannot_be_rewritten(
    saved, prepared, change
):
    projections = copy.deepcopy(prepared[3])
    label = (
        "N01"
        if change == "failed_promotion"
        else "E04"
        if change in {"e04_extension", "old_disposition"}
        else "N03"
    )
    index = next(i for i, value in enumerate(projections) if value["label"] == label)
    value = projections[index]
    if change == "failed_promotion":
        value = reseal(
            value,
            "panel_quotient_projection",
            status="supported",
            supported=True,
            behavior_projection=copy.deepcopy(
                next(item for item in projections if item["label"] == "E04")["behavior_projection"]
            ),
        )
    elif change == "old_disposition":
        value["interpretation_ledger"][0]["disposition"] = "invented_nonclassifying_alignment"
        value = reseal(value, "panel_quotient_projection")
    else:
        graph = value["behavior_projection"]
        if change == "remove_sum":
            graph["nodes"] = [
                node for node in graph["nodes"] if node["operation"] != "relation_sum"
            ]
        elif change == "change_denominator":
            ratio = next(node for node in graph["nodes"] if node["operation"] == "share_ratio")
            next(ref for ref in ratio["inputs"] if ref["role"] == "denominator")["kind"] = (
                "evidence"
            )
        else:
            graph["retained_interactions"] = []
        value = reseal(value, "panel_quotient_projection", behavior_projection=graph)
    projections[index] = value
    with pytest.raises(ProtocolError):
        compare(saved, prepared, projections=projections)


def test_new_rule_must_explicitly_extend_the_original_generation_rule(saved, prepared):
    condition, rule, _, _ = prepared
    changed_rule = reseal(rule, "support_transition_rule", extends_rule_id="foreign-base-rule")
    changed = reseal(condition, "support_transition_condition", rule_id=changed_rule["id"])
    with pytest.raises(ProtocolError, match="explicit_frozen_rule_extension"):
        comparison.comparison_contract(changed, saved["generation"], changed_rule)
    changed_generation = reseal(
        saved["generation"], "support_exploration_condition", rule_id=rule["id"]
    )
    with pytest.raises(ProtocolError, match="separate_generation_and_measurement_conditions"):
        comparison.comparison_contract(condition, changed_generation, rule)


def test_actual_new_projector_and_three_saved_valid_trajectories_bind_specific_witnesses(saved):
    from trusted_synthesis.experiments.finance_qa_vnext_support_transition.projection import (
        project_entry,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_support_transition.rules import (
        measurement_rule,
    )

    rule = measurement_rule()
    condition = measurement_condition(saved, rule)
    contract = comparison.comparison_contract(condition, saved["generation"], rule)
    projections = [
        project_entry(entry, condition, saved["generation"], rule, contract)
        for entry in saved["entries"]
    ]
    pairs = comparison.compare_all(
        saved["entries"], projections, condition, saved["generation"], rule, contract
    )
    assert len(pairs) == 3
    assert pairs[0]["execution_support_contrast"]["established"] is True
    assert pairs[2]["execution_support_contrast"]["established"] is True
    assert pairs[1]["relation"] in {"equivalent", "not_equivalent", "undetermined"}
    old_e04 = next(entry["old_projection"] for entry in saved["entries"] if entry["label"] == "E04")
    e04 = next(value for value in projections if value["label"] == "E04")
    assert canonical_json_bytes(e04["behavior_projection"]) == canonical_json_bytes(
        old_e04["behavior_projection"]
    )
