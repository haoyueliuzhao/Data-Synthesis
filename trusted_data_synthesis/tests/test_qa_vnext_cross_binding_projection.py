"""Fresh constructed new-source sessions; no historical trajectory or model sample replay."""

from __future__ import annotations

import copy
import json
import socket
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.bound_share_adapter import BoundShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.callbacks import (
    PublicFixtureCallback,
    action_response,
)
from trusted_synthesis.domains.finance.qa_vnext.measurement import audit_session
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding.projection import project_entry
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding.rules import quotient_rule
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding.source import load_sources
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.comparison import (
    compare_projections,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def no_provider(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("constructed projection control attempted network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture(scope="module")
def sources():
    return load_sources(ROOT)


class CorrectionFixture(PublicFixtureCallback):
    def __init__(self, *, route, proposal=False, assertion_history=False, novel=False):
        super().__init__(support_preference=route)
        self.proposal = proposal
        self.assertion_history = assertion_history
        self.novel = novel
        self.final_attempt = 0

    def generate(self, request):
        if self.proposal and request["state"]["submission_count"] == 0:
            offer = next(
                o
                for o in request["available_actions"]
                if o["operation"] == "share_ratio" and o["semantic_choice"] == "disclosed_total"
            )
            response = action_response(request, offer)
            response["decision"]["obligation_id"] = "total"
            return canonical_json_bytes(response)
        response = json.loads(super().generate(request))
        if response["kind"] == "final":
            attempt = self.final_attempt
            self.final_attempt += 1
            claim = next(
                c
                for c in request["state"]["accepted_claims"]
                if c["id"] == response["answer_claim_id"]
            )
            if self.assertion_history and attempt < 4:
                if attempt % 2 == 0:
                    evidence = request["context"]["evidence"]
                    response["citations"] = [
                        evidence[role]["id"]
                        for role in ("target_component", "disclosed_total", "composition_relation")
                    ]
                else:
                    response["result"] = copy.deepcopy(claim["proposition"]["output"])
            elif self.novel and attempt == 0:
                response["result"]["value"] = "99.000000"
        return canonical_json_bytes(response)


def constructed_entry(
    tmp_path,
    source,
    *,
    route="reconstructed_total",
    proposal=False,
    assertion_history=False,
    novel=False,
):
    adapter = BoundShareTaskAdapter(source)
    callback = CorrectionFixture(
        route=route, proposal=proposal, assertion_history=assertion_history, novel=novel
    )
    directory = tmp_path / "fresh_runtime"
    session = PublicQARuntime(
        adapter, callback, directory, max_submissions=32, max_actions=12
    ).run()
    audit = audit_session(adapter, session, directory)
    assert audit["qualified"], audit.get("errors")
    rule = quotient_rule()
    condition = record("cross_binding_condition", rule_id=rule["id"], synthetic_test_only=True)
    contract = record(
        "cross_binding_comparison_contract",
        rule_id=rule["id"],
        generation_condition_id=condition["id"],
        synthetic_test_only=True,
    )
    registration = record(
        "session_registration",
        label="T99_N01",
        profile="N",
        profile_id="synthetic:N",
        model_configuration_id="synthetic:config",
        run_condition_id=condition["id"],
        session_id="synthetic:registered",
        task_group="T99",
        task_type=adapter.context["task_type"],
        task_id=adapter.context["task_id"],
        context_id=adapter.context["id"],
        protocol_id=session["protocol_id"],
        registry_hash=session["registry_hash"],
        synthetic_test_only=True,
    )
    qualification = record(
        "qualification",
        status="success",
        qualified=True,
        model_origin_verified=False,
        synthetic_test_only=True,
        model_sample=False,
        session_id=session["id"],
        registered_session_id=registration["session_id"],
        registration_id=registration["id"],
        domain_audit=audit,
        domain_audit_id=audit["id"],
        **{
            key: registration[key]
            for key in (
                "task_group",
                "task_type",
                "task_id",
                "context_id",
                "protocol_id",
                "registry_hash",
                "model_configuration_id",
            )
        },
    )
    entry = {
        "label": registration["label"],
        "registration": registration,
        "qualification": qualification,
        "session": session,
    }
    return entry, condition, rule, contract


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("route", ["disclosed_total", "reconstructed_total"])
def test_role_bound_actual_support_on_every_new_instance(tmp_path, sources, index, route):
    entry, condition, rule, contract = constructed_entry(tmp_path, sources[index], route=route)
    before = canonical_json_bytes(entry)
    projection = project_entry(entry, condition, rule, contract)
    assert projection["supported"]
    assert projection["actual_support"]["proof_verified"]
    assert projection["actual_support"]["support"] == route
    assert projection["actual_support"]["base_anchor_id"] == projection["base_anchor"]["id"]
    assert projection["actual_support"]["task_id"] == sources[index].task_id
    assert projection["base_nodes_and_final_unchanged"]
    assert canonical_json_bytes(entry) == before
    assert projection["new_outcome_specific_rule_extension"] is False


@pytest.mark.parametrize("index", range(3))
def test_parameterized_transition_and_complete_grounding_segment(tmp_path, sources, index):
    entry, condition, rule, contract = constructed_entry(
        tmp_path, sources[index], proposal=True, assertion_history=True
    )
    before = canonical_json_bytes(entry)
    projection = project_entry(entry, condition, rule, contract)
    assert projection["supported"], projection["errors"]
    relations = projection["behavior_projection"]["retained_interactions"]
    assert len(relations) == 2
    transition, assertions = relations
    assert transition["kind"] == "support_choice_transition_after_unadmitted_proposal"
    assert transition["denominator_transition"]["inputs_are_equal"] is False
    assert transition["unadmitted_proposal_was_executed"] is False
    assert transition["reconstruction_changes_execution_state"] is True
    assert transition["denominator_transition"]["before"]["reference"] == {
        "evidence_id": sources[index].evidence["disclosed_total"]["id"]
    }
    assert [row["assertion_kind"] for row in assertions["assertion_sequence"]] == [
        "incorrect_support_assertion",
        "actual_lineage_assertion",
        "incorrect_support_assertion",
        "actual_lineage_assertion",
    ]
    detail = next(d for d in projection["interpretation_details"] if "original_assertions" in d)
    assert len(detail["original_assertions"]) == 5
    assert len(projection["interpretation_ledger"]) == 5
    assert len(projection["behavior_projection"]["nodes"]) == 3
    assert projection["actual_uses_edges_from_erroneous_assertions_added"] is False
    assert canonical_json_bytes(entry) == before


def test_new_result_value_remains_qualified_but_projection_undetermined(tmp_path, sources):
    entry, condition, rule, contract = constructed_entry(tmp_path, sources[0], novel=True)
    projection = project_entry(entry, condition, rule, contract)
    assert entry["qualification"]["qualified"]
    assert projection["actual_support"]["proof_verified"]
    assert projection["status"] == "undetermined" and projection["behavior_projection"] is None
    assert any(row["disposition"] == "undetermined" for row in projection["interpretation_ledger"])


def test_rejected_proposal_and_plain_disclosed_execution_keep_baseline_relation(tmp_path, sources):
    entry, condition, rule, contract = constructed_entry(
        tmp_path, sources[0], route="disclosed_total", proposal=True
    )
    # This rejected proposal repeats the same next support with an unregistered judgment
    # change, which is outside same-action basis-completion. It must not be deleted.
    projection = project_entry(entry, condition, rule, contract)
    assert projection["actual_support"]["support"] == "disclosed_total"
    assert projection["status"] == "undetermined"


def test_profile_label_is_not_a_class(tmp_path, sources):
    entry, condition, rule, contract = constructed_entry(tmp_path, sources[1])
    projection = project_entry(entry, condition, rule, contract)
    fields = {k: v for k, v in projection.items() if k not in {"id", "schema_version"}}
    changed = record(
        "panel_quotient_projection",
        **{
            **fields,
            "label": "T99_E02",
            "profile": "E",
            "profile_id": "synthetic:E",
            "registration_id": "synthetic:other",
            "qualification_id": "synthetic:other:q",
            "session_id": "synthetic:other:s",
        },
    )
    pair = compare_projections(projection, changed)
    assert pair["relation"] == "equivalent" and pair["proof_verified"]


def test_frozen_rule_drift_is_rejected_before_projection(tmp_path, sources):
    entry, condition, rule, contract = constructed_entry(tmp_path, sources[2])
    changed = copy.deepcopy(rule)
    changed["new_outcome_specific_rule_extension_allowed"] = True
    with pytest.raises(ValueError, match="projection_rule_drift"):
        project_entry(entry, condition, changed, contract)
