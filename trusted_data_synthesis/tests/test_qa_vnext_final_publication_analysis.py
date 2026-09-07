"""Pure constructed six-session analysis controls; no old sessions or token rows replayed."""

from __future__ import annotations

import copy
import json
import socket

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.final_public_contract import (
    public_final_contract,
    public_final_schema,
)
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError, contract
from trusted_synthesis.domains.finance.qa_vnext.protocol import record as public_record
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding.rules import (
    quotient_rule as prior_rule,
)
from trusted_synthesis.experiments.finance_qa_vnext_final_publication import (
    measurement,
    projection,
    representation,
)
from trusted_synthesis.experiments.finance_qa_vnext_final_publication.plan import (
    configuration,
    profiles,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import qualification
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import (
    representation as original,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record, sha
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HttpxSender


def forbidden(*args, **kwargs):
    pytest.fail(
        "analysis controls attempted a Provider, Runtime, qualification or real tokenization"
    )


@pytest.fixture(autouse=True)
def no_producers(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(PublicQARuntime, "__init__", forbidden)
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(qualification, "qualify_session", forbidden)
    monkeypatch.setattr(representation.panel.assets, "load_tokenizer", forbidden)


def reseal(value, kind, **changes):
    body = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key not in {"id", "schema_version"}
    }
    return record(kind, **{**body, **changes})


def _graph(task, label):
    numerator, total = (task["task_id"] + suffix for suffix in (":target", ":total"))
    ratio, percent = label + ":ratio", label + ":percent"
    denominator = {"role": "denominator", "kind": "evidence", "reference": {"evidence_id": total}}
    nodes = [
        {
            "node_id": ratio,
            "operation": "share_ratio",
            "inputs": [
                {"role": "numerator", "kind": "evidence", "reference": {"evidence_id": numerator}},
                denominator,
            ],
            "input_dependencies": [],
            "decision_dependencies": [],
        },
        {
            "node_id": percent,
            "operation": "scale_percent",
            "inputs": [{"role": "ratio", "kind": "claim", "reference": {"producer_action": ratio}}],
            "input_dependencies": [ratio],
            "decision_dependencies": [ratio],
        },
    ]
    final = {
        "answer_producer": {"producer_action": percent},
        "result": {"value": "60.000000", "unit": "percent"},
        "citations": [numerator, total],
    }
    trace = {
        "ratio": {"node_id": ratio, "operation": "share_ratio"},
        "actual_denominator": denominator,
        "actual_resolved_denominator": {"ref_id": total, "value": {"kind": "evidence"}},
        "disclosed_total_evidence_id": total,
    }
    return {"nodes": nodes, "final": final}, trace


def constructed(*, successes=None, outcomes=None, unmapped=(), policy_id="constructed-policy"):
    """Artificial accounting records, not independently observed model successes."""
    tasks = [
        {
            "task_group": f"T{i:02d}",
            "task_type": "parameterized_part_whole_share",
            "task_id": f"constructed-task-{i}",
            "context_id": f"constructed-context-{i}",
            "protocol_id": contract()["id"],
            "registry_hash": f"constructed-registry-{i}",
            "source_binding_id": f"constructed-source-{i}",
        }
        for i in range(1, 4)
    ]
    labels = [f"{task['task_group']}_{name}01" for task in tasks for name in ("N", "E")]
    successes = set(labels if successes is None else successes)
    outcomes = outcomes or {}
    frozen_profiles = profiles()
    configs = {name: configuration(name).as_record() for name in ("N", "E")}
    rule = prior_rule()
    condition = record(
        "final_publication_condition",
        tasks=tasks,
        task_count=3,
        registered_session_count=6,
        sessions_per_task=2,
        sessions_per_task_profile=1,
        registered_labels=labels,
        profiles=frozen_profiles,
        configurations=configs,
        rule_id=rule["id"],
        final_public_contract_id=public_final_contract()["id"],
        measurement_application_id=measurement.measurement_application()["id"],
        representation_policy_id=policy_id,
        profile_mixture={name: {"numerator": 1, "denominator": 2} for name in ("N", "E")},
        task_marginal=[
            {
                "task_id": task["task_id"],
                "task_group": task["task_group"],
                "numerator": 1,
                "denominator": 3,
            }
            for task in tasks
        ],
        control_evidence=True,
    )
    comparison = measurement.comparison_contract(condition, rule)
    entries, projections = [], []
    for label in labels:
        task = next(task for task in tasks if label.startswith(task["task_group"] + "_"))
        profile = label.split("_")[1][0]
        status = outcomes.get(label, "success" if label in successes else "known_failure")
        valid, absent = status == "success", status in ("unknown", "not_started")
        reg = record(
            "session_registration",
            label=label,
            run_condition_id=condition["id"],
            session_id="constructed-registration-" + label,
            **{key: task[key] for key in measurement.TASK_FIELDS},
            profile=profile,
            profile_id=frozen_profiles[profile]["id"],
            model_configuration_id=configs[profile]["id"],
            control_evidence=True,
        )
        feedback = {
            "code": "admission.final_qa",
            "admitted": False,
            "public_diagnostic": {
                "contract_id": public_final_contract()["id"],
                "violations": [{"category": "result_fields", "extra_fields": ["metric"]}],
            },
        }
        request = public_record(
            "request",
            context={"id": task["context_id"], "task_id": task["task_id"]},
            state={"id": "constructed-state-" + label, "last_feedback": feedback},
            public_final_contract=public_final_contract(),
            response_schemas={"final": public_final_schema()},
        )
        target = '{ "kind": "final", "constructed_original": "中文🙂é" }\n'
        submission = public_record(
            "submission",
            raw_sha256=sha(target.encode()),
            raw_bytes=len(target.encode()),
            label=label,
        )
        receipt = public_record("receipt", admitted=True, submission_id=submission["id"])
        events = [
            {
                "sequence": 0,
                "request": request,
                "submission": submission,
                "receipt": receipt,
                "parsed": {"kind": "final"},
            }
        ]
        session = (
            None
            if absent
            else public_record(
                "session",
                context_id=task["context_id"],
                protocol_id=task["protocol_id"],
                events=events,
                final={"qa_validation": {"qa_valid": valid}},
                callback_binding={
                    "model_configuration_id": configs[profile]["id"],
                    "origin": "constructed_analysis_control",
                },
            )
        )
        base, trace = _graph(task, label)
        graph = (
            None
            if absent
            else public_record("actual_decision_graph", nodes=base["nodes"], control_evidence=True)
        )
        audit = (
            None
            if absent
            else public_record(
                "session_audit",
                session_id=session["id"],
                context_id=task["context_id"],
                protocol_id=task["protocol_id"],
                task_id=task["task_id"],
                actual_decision_graph=graph,
                finite_projection=base,
                projection_supported=valid and label not in unmapped,
                validation_passed=valid,
                qualified=valid,
                evidence_complete=True,
                qa_valid=valid,
                trajectory_valid=valid,
                errors=[],
                control_evidence=True,
            )
        )
        qual = record(
            "qualification",
            registration_id=reg["id"],
            registered_session_id=reg["session_id"],
            session_id=session["id"] if session else None,
            domain_audit=audit,
            domain_audit_id=audit["id"] if audit else None,
            **{key: task[key] for key in measurement.TASK_FIELDS},
            model_configuration_id=reg["model_configuration_id"],
            status=status,
            qualified=None if absent else valid,
            end_to_end_success=None if absent else valid,
            evidence_complete=status != "unknown",
            model_origin_verified=not absent,
            export_eligible=valid,
            qa_valid=valid,
            trajectory_valid=valid,
            projection_status="supported" if valid and label not in unmapped else "undetermined",
            control_evidence=True,
        )
        metadata = {
            **{
                key: reg[key]
                for key in (
                    *measurement.TASK_FIELDS,
                    "profile",
                    "profile_id",
                    "model_configuration_id",
                )
            },
            "rule_id": rule["id"],
            "generation_condition_id": condition["id"],
            "comparison_contract_id": comparison["id"],
            "registration_id": reg["id"],
            "label": label,
            "session_id": qual["session_id"],
            "qualification_id": qual["id"],
            "qualification_status": status,
            "old_domain_audit_id": qual["domain_audit_id"],
            "source_actual_graph_id": graph["id"] if graph else None,
            "old_projection_supported": bool(audit and audit["projection_supported"]),
        }
        anchor = record(
            "cross_binding_actual_base_anchor",
            **metadata,
            finite_projection=base if audit else None,
        )
        support = record(
            "cross_binding_support",
            qualification_id=qual["id"],
            registration_id=reg["id"],
            session_id=qual["session_id"],
            base_anchor_id=anchor["id"],
            task_id=task["task_id"],
            context_id=task["context_id"],
            qualified=qual["qualified"],
            qualification_status=status,
            source_actual_graph_id=graph["id"] if graph else None,
            support="disclosed_total" if valid else "ineligible",
            proof_verified=valid,
            trace=trace if valid else None,
        )
        publication_binding = record(
            "final_publication_projection_binding",
            generation_condition_id=condition["id"],
            measurement_application_id=condition["measurement_application_id"],
            public_final_contract_id=public_final_contract()["id"],
            qualification_id=qual["id"],
            saved_event_request_count=len(events) if session else 0,
            quotient_semantics_changed=False,
        )
        mapped = valid and label not in unmapped
        projections.append(
            record(
                "panel_quotient_projection",
                **metadata,
                base_anchor=anchor,
                actual_support=support,
                supported=mapped,
                status="supported" if mapped else "undetermined" if valid else "ineligible",
                behavior_projection={**base, "retained_interactions": []} if mapped else None,
                final_publication_binding=publication_binding,
                interpretation_ledger=[],
                interpretation_details=[],
            )
        )
        rows = []
        if valid:
            fields = {key: "constructed-" + label + ":" + key for key in original.ROW_IDS}
            fields.update(
                representation_version=original.REPRESENTATION_VERSION,
                task_id=reg["task_id"],
                context_id=reg["context_id"],
                protocol_id=reg["protocol_id"],
                session_id=session["id"],
                registered_session_id=reg["session_id"],
                registration_id=reg["id"],
                qualification_id=qual["id"],
                domain_audit_id=audit["id"],
                turn_index=0,
                public_request_id=request["id"],
                public_runtime_state_id=request["state"]["id"],
                submission_id=submission["id"],
                receipt_id=receipt["id"],
                messages=[
                    {"role": "system", "content": configs[profile]["system_prompt"]},
                    {"role": "user", "content": canonical_json_bytes(request).decode()},
                ],
                target_text=target,
                target_raw_sha256=sha(target.encode()),
                target_raw_byte_count=len(target.encode()),
                submission_kind="final",
                admitted=True,
                qualified=True,
                model_origin_verified=True,
                quotient_assignment_id=None,
                class_weights_assigned=False,
            )
            rows = [record("supervision_candidate", **fields)]
        export = record(
            "supervision_export",
            session_id=qual["session_id"],
            qualification_id=qual["id"],
            rows=rows,
            candidate_count=len(rows),
            session_exclusion_reasons=[] if valid else [status],
        )
        package = record(
            "constructed_session_package",
            registration_id=reg["id"],
            qualification_id=qual["id"],
            session_id=qual["session_id"],
            complete=valid,
        )
        entries.append(
            {
                "label": label,
                "registration": reg,
                "qualification": qual,
                "session": session,
                "export": export,
                "package": package,
                "target_token_count": 20 if valid else 0,
            }
        )
    return dict(
        entries=entries,
        projections=projections,
        condition=condition,
        rule=rule,
        contract=comparison,
    )


def _rows(population):
    return [row for entry in population["entries"] for row in entry["export"]["rows"]]


def test_six_sessions_three_same_task_pairs_and_unchanged_rule():
    population = constructed()
    contract = population["contract"]
    assert contract["registered_session_count"] == 6
    assert contract["maximum_pairs_per_task"] == 1 and contract["maximum_same_task_pairs"] == 3
    assert len(contract["registered_same_task_label_pairs"]) == 3
    assert population["rule"] == prior_rule()
    assert measurement.measurement_application()["new_outcome_specific_quotient_extension"] is False
    result = measurement.analyze(**population)
    assert result["pair_count"] == 3 and result["cross_task_state_comparisons"] == 0
    assert result["qualified_count"] == 6 and len(result["classes"]) == 3
    assert all(row["profile_counts"] == {"N": 1, "E": 1} for row in result["classes"])
    assert result["tasks_with_DR_witness"] == 0
    assert result["panel_success_fraction"] == {"numerator": 6, "denominator": 6}


def test_zero_success_has_no_conditional_distribution_or_positive_export():
    population = constructed(successes=())
    result = measurement.analyze(**population)
    assert result["registered_session_count"] == result["known_failure_count"] == 6
    assert result["qualified_count"] == result["pair_count"] == 0
    assert result["classes"] == result["assignments"] == []
    assert result["panel_success_fraction"] == {"numerator": 0, "denominator": 6}
    assert all(row["conditional_distribution"] is None for row in result["task_rows"])
    assert result["pooled_cross_task_conditional_distribution"] is None
    assert _rows(population) == []


def test_unknown_not_started_and_qualified_undetermined_are_not_removed():
    population = constructed(
        successes=("T01_N01", "T01_E01"),
        outcomes={"T02_N01": "unknown", "T03_E01": "not_started"},
        unmapped=("T01_N01",),
    )
    result = measurement.analyze(**population)
    assert result["registered_session_count"] == 6 and result["qualified_count"] == 2
    assert (
        result["known_failure_count"] == 2
        and result["unknown_count"] == result["not_started_count"] == 1
    )
    assert result["panel_success_fraction"] is None
    assert result["panel_success_fraction_bounds"] == {
        "lower": {"numerator": 2, "denominator": 6},
        "upper": {"numerator": 4, "denominator": 6},
    }
    task = result["task_rows"][0]
    assert task["qualified_count"] == 2 and task["unmapped_qualified_count"] == 1
    assert task["conditional_distribution"] is None
    assert result["pair_count"] == 1 and result["pairs"][0]["relation"] == "undetermined"
    assert result["unmapped_valid_joint_mass"] == {"numerator": 1, "denominator": 6}
    assert len(_rows(population)) == 2


@pytest.mark.parametrize("change", ["drop", "duplicate"])
def test_registered_six_denominator_cannot_be_filtered_or_duplicated(change):
    population = constructed()
    if change == "drop":
        population["entries"].pop()
        population["projections"].pop()
    else:
        population["entries"][1] = copy.deepcopy(population["entries"][0])
    with pytest.raises(ProtocolError, match="registered_denominator|exact_current_population"):
        measurement.analyze(**population)


def test_cross_task_pair_fails_before_graph_comparison(monkeypatch):
    population = constructed()
    monkeypatch.setattr(measurement, "compare_projections", forbidden)
    with pytest.raises(ProtocolError, match="no_cross_task_state_comparison"):
        measurement.compare_within_task(
            population["entries"][0],
            population["entries"][2],
            population["projections"][0],
            population["projections"][2],
            population["condition"],
            population["rule"],
            population["contract"],
        )


def test_projection_checks_real_final_publication_without_changing_frozen_projection(monkeypatch):
    population = constructed()
    entry = population["entries"][0]
    baseline = population["projections"][0]
    baseline = {key: value for key, value in baseline.items() if key != "final_publication_binding"}
    baseline = reseal(baseline, "panel_quotient_projection")
    monkeypatch.setattr(projection, "frozen_project", lambda *args: copy.deepcopy(baseline))
    before = canonical_json_bytes(entry)
    result = projection.project_entry(
        entry, population["condition"], population["rule"], population["contract"]
    )
    assert canonical_json_bytes(entry) == before
    assert result["behavior_projection"] == baseline["behavior_projection"]
    assert result["final_publication_binding"]["source_projection_id"] == baseline["id"]
    assert result["final_publication_binding"]["quotient_semantics_changed"] is False
    for key in ("public_final_contract", "response_schemas"):
        changed = copy.deepcopy(entry)
        if key == "public_final_contract":
            del changed["session"]["events"][0]["request"][key]
        else:
            changed["session"]["events"][0]["request"][key]["final"]["properties"]["result"][
                "additionalProperties"
            ] = True
        with pytest.raises(ProtocolError, match="actual_final_publication_missing_or_changed"):
            projection.project_entry(
                changed, population["condition"], population["rule"], population["contract"]
            )


def test_new_exports_retain_final_contract_exact_feedback_and_both_profile_prompts():
    population = constructed(unmapped=("T01_N01",))
    rows = _rows(population)
    checked = representation.validate_profile_bindings(
        rows, population["entries"], population["condition"]
    )
    assert checked["candidate_count"] == checked["registered_session_count"] == 6
    assert checked["candidate_counts_by_profile"] == {"N": 3, "E": 3}
    for row in rows:
        message = row["messages"][1]["content"]
        assert '"public_final_contract"' in message and '"extra_fields":["metric"]' in message
        assert row["target_text"].endswith("\n")
    entry = population["entries"][0]
    changed = copy.deepcopy(entry["export"]["rows"])
    public_request = json.loads(changed[0]["messages"][1]["content"])
    public_request["state"]["last_feedback"] = None
    messages = copy.deepcopy(changed[0]["messages"])
    messages[1]["content"] = canonical_json_bytes(public_request).decode()
    changed[0] = reseal(changed[0], "supervision_candidate", messages=messages)
    entry["export"] = reseal(entry["export"], "supervision_export", rows=changed)
    with pytest.raises(ProtocolError, match="original_profile_request_and_target"):
        representation.validate_profile_bindings(
            _rows(population), population["entries"], population["condition"]
        )


def test_zero_success_representation_does_not_load_tokenizer_or_invent_fit(monkeypatch):
    panel = representation.panel
    binding = {
        "id": "constructed-asset-reference",
        "chat_template_sha256": "constructed-template",
        "software_versions": {},
    }
    assets = panel.length_core.record("tokenizer_assets", actual_max_position_embeddings=32768)
    monkeypatch.setattr(panel.length_core, "asset_binding", lambda value: assets)
    policy = representation.representation_policy(binding)
    population = constructed(successes=(), policy_id=policy["id"])
    result = representation.analyze_representation(
        [], population["entries"], binding, policy, population["condition"]
    )
    assert result["tokens"]["status"] == "no_positive_candidates"
    assert result["tokens"]["positive_representation_validated"] is False
    assert result["packages"]["registered_session_count"] == 6
    assert result["packages"]["complete_session_packages"] == 0
    assert result["cpu_loading"]["positive_cpu_loading_validated"] is False
    assert result["final_publication"]["candidate_links"] == []
