"""Bounded panel wiring: local source loading, never Runtime or Provider execution."""

from __future__ import annotations

import copy
import socket
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.action_public_contract import public_action_contract
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError, contract
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import public_update_contract
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    identity,
    read_json,
    record,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    SYSTEM_PROMPT,
    HttpxSender,
    TransportConfig,
    render_http_request,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel import plan

ROOT = Path(__file__).resolve().parents[2]


def forbidden(*args, **kwargs):
    pytest.fail("plan tests may not call Provider, Runtime, or financial execution")


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(ProgramTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(ShareTaskAdapter, "execute", forbidden)


@pytest.fixture(scope="module")
def panel():
    return plan.load_panel(ROOT)


@pytest.fixture
def policy():
    return record(
        "task_panel_representation_policy",
        maximum_sequence_length=32_768,
        truncation=False,
        synthetic_unit_test=True,
    )


@pytest.fixture
def frozen(panel, policy, monkeypatch):
    monkeypatch.setattr(plan, "load_panel", lambda root: panel)
    return plan.freeze_condition(
        ROOT,
        plan.configuration().as_record(),
        record("implementation", synthetic_unit_test=True),
        policy,
        run_tag="unit-fixed-panel",
    )


def test_exact_eight_source_contexts_and_three_uninstantiated_types(panel):
    baseline = read_json((ROOT / plan.BASELINE_ENTRY / "report.json").read_bytes())
    assert tuple(plan.TASK_GROUPS) == ("F", "C", "G", "A", "D", "R", "B", "S")
    assert len(panel.cases) == 7 and len(panel.source_bindings) == 8
    assert len(baseline["coverage_rows"]) == 9
    assert len(panel.coverage) == 11
    assert sum(row["registered_model_sessions"] for row in panel.coverage) == 16
    assert {row["task_type"] for row in panel.coverage if not row["source_available"]} == {
        "comparison",
        "derived_growth_comparison",
        "registered_margin_target_gap",
    }
    assert len({row["task_id"] for row in panel.source_bindings.values()}) == 8
    for group, task_type in plan.TASK_GROUPS.items():
        adapter = panel.adapter(group)
        rows = [row for row in baseline["coverage_rows"] if row["task_type"] == task_type]
        assert all(row["context_id"] == adapter.context["id"] for row in rows)
        assert all(row["task_id"] == adapter.context["task_id"] for row in rows)
        assert all(
            row["source_binding_id"] == adapter.context["source_binding"]["id"] for row in rows
        )
        assert panel.source_bindings[group]["existing_case_ids"] == [r["case_id"] for r in rows]
        assert panel.source_bindings[group]["source_usage"] == plan.SOURCE_USAGE
        assert all(
            row["registry_hash"] == strict_canonical_hash(panel.catalog.registry.manifest())
            for row in rows
        )
    assert panel.source_bindings["S"]["existing_case_ids"] == [
        "share_disclosed_total",
        "share_reconstructed_total",
    ]
    assert panel.source_bindings["S"]["distinct_task_count"] == 1
    assert isinstance(panel.adapter("F"), ProgramTaskAdapter)
    assert isinstance(panel.adapter("S"), ShareTaskAdapter)


def test_sixteen_unique_registrations_two_fixed_rounds_and_eight_exact_weights(frozen):
    condition, rows, panel = frozen
    identity(condition, "task_panel_condition")
    assert len(rows) == len({row["session_id"] for row in rows}) == 16
    assert [row["ordinal"] for row in rows] == list(range(16))
    assert [row["label"] for row in rows] == [
        f"{group}{r:02d}" for r in (1, 2) for group in plan.ROUND_TASK_ORDER
    ]
    assert Counter(row["task_group"] for row in rows) == dict.fromkeys(plan.TASK_GROUPS, 2)
    assert Counter(row["round"] for row in rows) == {1: 8, 2: 8}
    assert condition["fixed_round_waves"] == [["F", "C"], ["G", "A"], ["D", "R"], ["B", "S"]]
    assert condition["within_round_wave_barrier"] is True
    assert condition["maximum_parallel_sessions"] == 2
    weights = condition["declared_task_marginal"]
    assert len(weights) == 8
    assert sum(Fraction(row["numerator"], row["denominator"]) for row in weights) == 1
    assert all(type(row["numerator"]) is int and row["numerator"] == 1 for row in weights)
    assert all(type(row["denominator"]) is int and row["denominator"] == 8 for row in weights)
    for row in rows:
        identity(row, "session_registration")
        assert row["run_condition_id"] == condition["id"]
        assert row["context_id"] == panel.adapter(row["task_group"]).context["id"]
        assert row["source_usage"] == "source_development_not_blindtest"
        assert row["replacement_allowed"] is False
        assert row["reference_route"] is None
        assert row["independent_initial_state"] is True
        assert row["reads_other_session_responses"] is False


def test_finite_population_only_transport_override_and_global_allowance(frozen):
    condition, rows, _ = frozen
    config = plan.configuration()
    assert isinstance(config, TransportConfig)
    assert config.system_prompt == SYSTEM_PROMPT
    assert config.attempts_per_session == 32
    assert config.maximum_pilot_attempts == 512
    assert config.as_record()["maximum_pilot_reserved_tokens"] == 512 * 107_520 == 55_050_240
    assert config.as_record()["maximum_session_reserved_tokens"] == 32 * 107_520
    assert condition["maximum_reserved_token_allowance"] == 55_050_240
    assert sum(row["maximum_provider_attempts"] for row in rows) == 512
    assert all(row["maximum_actions"] == 12 and row["maximum_submissions"] == 32 for row in rows)
    assert TransportConfig().maximum_pilot_attempts == 384
    with pytest.raises(ValidationError):
        TransportConfig(maximum_pilot_attempts=512)
    with pytest.raises(ValidationError):
        plan.PanelTransportConfig(maximum_pilot_attempts=513)
    assert condition["maximum_http_body_bytes"] == 98_304
    assert condition["output_token_limit"] == 8192


def test_all_actual_initial_requests_same_publications_neutral_prompt_and_budget(panel):
    config = plan.configuration()
    for group in plan.TASK_GROUPS:
        request = plan.initial_request(panel.adapter(group))
        assert request["protocol_id"] == contract()["id"]
        assert request["public_action_contract"] == public_action_contract()
        assert request["public_update_contract"] == public_update_contract()
        http = render_http_request(request, config, session_id="local-" + group, attempt_index=0)
        body = read_json(http["body_json"].encode())
        assert body["messages"] == [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": canonical_json_bytes(request).decode()},
        ]
        assert body["model"] == "deepseek-v4-pro"
        assert body["thinking"] == {"type": "disabled"}
        assert body["temperature"] == 0.7 and body["top_p"] == 1.0
        assert http["body_byte_count"] <= 98_304
        assert not request["state"]["accepted_claims"]
        assert request["state"]["last_feedback"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("attempts_per_session", 31),
        ("maximum_pilot_attempts", 384),
        ("system_prompt", SYSTEM_PROMPT + " Use disclosed_total."),
        ("automatic_retries", 1),
        ("model_fallbacks", 1),
        ("maximum_serialized_request_bytes", 98_305),
        ("max_tokens", 8193),
        ("thinking", {"type": "enabled"}),
    ],
)
def test_configuration_mutations_fail_before_source_loading(field, value, policy, monkeypatch):
    monkeypatch.setattr(plan, "load_panel", forbidden)
    original = plan.configuration().as_record()
    fields = {key: item for key, item in original.items() if key not in {"id", "schema_version"}}
    fields[field] = value
    changed = record("transport_config", **fields)
    with pytest.raises(ProtocolError, match="task_panel.fixed_configuration"):
        plan.freeze_condition(ROOT, changed, record("implementation"), policy, run_tag="mutated")


@pytest.mark.parametrize("length,truncation", [(24_576, False), (32_769, False), (32_768, True)])
def test_changed_representation_policy_is_not_silently_accepted(length, truncation, monkeypatch):
    monkeypatch.setattr(plan, "load_panel", forbidden)
    policy = record(
        "task_panel_representation_policy", maximum_sequence_length=length, truncation=truncation
    )
    with pytest.raises(ProtocolError, match="task_panel.fixed_representation_policy"):
        plan.freeze_condition(
            ROOT, plan.configuration().as_record(), record("implementation"), policy, run_tag="bad"
        )


def test_mutated_context_is_not_silently_replaced(monkeypatch):
    original = plan.ProgramTaskAdapter

    def changed(case, registry):
        adapter = original(case, registry)
        adapter.context = {**adapter.context, "id": "mutated-context"}
        return adapter

    monkeypatch.setattr(plan, "ProgramTaskAdapter", changed)
    with pytest.raises(ProtocolError, match="task_panel.fixed_source_context"):
        plan.load_panel(ROOT)


def test_missing_exact_case_is_not_replaced_by_same_type(panel, monkeypatch):
    catalog = panel.catalog
    actual = catalog.frozen_source_cases

    def changed(*args, **kwargs):
        cases, coverage = actual(*args, **kwargs)
        cases = tuple(
            replace(case, case_id=case.case_id + "_replacement")
            if case.task_type == "fact_retrieval"
            else case
            for case in cases
        )
        return cases, coverage

    monkeypatch.setattr(catalog, "frozen_source_cases", changed)
    monkeypatch.setattr(plan, "build_catalog", lambda root: catalog)
    with pytest.raises(ProtocolError, match="task_panel.exact_source_case_unavailable"):
        plan.load_panel(ROOT)


def test_changed_baseline_report_fails_identity(monkeypatch):
    baseline = read_json((ROOT / plan.BASELINE_ENTRY / "report.json").read_bytes())
    changed = copy.deepcopy(baseline)
    changed["coverage_rows"][0]["context_id"] = "different-source-context"
    monkeypatch.setattr(plan, "read_json", lambda data: changed)
    with pytest.raises(ProtocolError, match="task_panel.baseline_report_identity"):
        plan.load_panel(ROOT)


def test_new_condition_and_registration_identities_do_not_reuse_old_B(frozen, policy, monkeypatch):
    condition, rows, panel = frozen
    monkeypatch.setattr(plan, "load_panel", lambda root: panel)
    other, other_rows, _ = plan.freeze_condition(
        ROOT,
        plan.configuration().as_record(),
        record("implementation", synthetic_unit_test=True),
        policy,
        run_tag="another-fresh-population",
    )
    assert condition["id"] != other["id"]
    assert not {row["session_id"] for row in rows} & {row["session_id"] for row in other_rows}
    assert condition["representation_policy_id"] == policy["id"]
    assert condition["historical_length_condition_or_dataset_identity_reused"] is False
    assert condition["new_candidate_dataset_and_token_dataset_identities_required"] is True
    assert condition["historical_response_examples_in_prompt"] is False
    assert condition["share_route_preassignment"] is None
    assert condition["no_cross_condition_success_pooling"] is True


def test_failures_unknowns_projection_and_representation_are_independent(frozen):
    condition, _, _ = frozen
    assert condition["registered_denominator"] == 16
    assert condition["model_failures_remain_in_registered_population"] is True
    assert condition["unknown_and_not_started_have_null_success_indicator"] is True
    assert condition["halt_future_launches_on_integrity_failure"] is True
    assert condition["scientific_success_is_not_workflow_gate"] is True
    assert condition["minimum_success_count_for_workflow_completion"] is None
    assert condition["minimum_quotient_class_count_for_workflow_completion"] is None
    assert condition["qualified_but_projection_undetermined_is_allowed"] is True
    assert condition["successful_pool_task_marginal_is_separate"] is True
    assert condition["token_fit_and_complete_package_task_marginals_are_separate"] is True
    assert condition["task_marginal_redefined_after_failure_or_filtering"] is False
    assert condition["overlength_does_not_change_model_qualification"] is True
    assert condition["package_denominator"] == "all admitted session events, never the fit subset"
    assert condition["maximum_same_task_comparison_pairs"] == 8
    assert condition["student_parameter_loads"] == condition["student_forward_calls"] == 0
    assert condition["student_updates"] == condition["gpu_jobs"] == 0
    assert condition["old_mainline"] == "remains_paused"
