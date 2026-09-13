"""Synthetic JSON protocol controls; no real Student or private reference opened."""

import copy
import json

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss import diagnostics as d
from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss.protocol import (
    encode,
    record,
    sha,
)


def original(kind, **fields):
    body = {"schema_version": "eval_readiness.v1." + kind, **copy.deepcopy(fields)}
    return {**body, "id": kind + ":" + sha(encode(body))}


def resign(value):
    kind = value["id"].split(":")[0]
    return record(kind, **{k: v for k, v in value.items() if k not in {"id", "schema_version"}})


def resign_original(value):
    kind = value["id"].split(":")[0]
    return original(kind, **{k: v for k, v in value.items() if k not in {"id", "schema_version"}})


def messages(i):
    return [
        {
            "role": "user",
            "content": json.dumps({"period_contract": {"source_cluster": f"source-{i}"}}),
        }
    ]


def tasks():
    return [
        {
            "task_id": "task_" + f"{i + 1:064x}",
            "group": group,
            "source_cluster": f"source-{i}",
            "surface_version_id": f"surface-{i}",
            "public_messages_sha256": sha(encode(messages(i))),
        }
        for i, group in enumerate(d.GROUPS)
    ]


def registration(**overrides):
    kwargs = {
        "pool": "A",
        "seed": 11,
        "split": "dev",
        "materials_manifest_id": "materials:test",
        "pi_id": "pi:fixed",
        "surface_manifest_id": "surface:shared",
        "frozen_pair_id": "pair:test",
    }
    kwargs.update(overrides)
    return d.build_registration(tasks(), **kwargs)


def original_inputs(i, status="pass"):
    task = tasks()[i]
    no_final = status == "no_final"
    session = original(
        "evaluation_session",
        identity={
            "task_id": task["task_id"],
            "family": task["group"],
            "surface_version_id": task["surface_version_id"],
            "public_messages_sha256": task["public_messages_sha256"],
        },
        public_messages=messages(i),
        first_final_index=None if no_final else 2,
        raw_final=None if no_final else {"value": "1", "unit": "USD", "result_id": "call-1"},
        origin="SYNTHETIC_CPU_NOT_REAL_QUALIFICATION",
        events=[],
    )
    assessment = original(
        "evaluation_assessment",
        task_id=task["task_id"],
        session_id=session["id"],
        financial_valid=status == "pass",
        complete_trajectory_qualified=status == "pass",
        is_primary_utility_score=True,
        raw_history_and_tools_replayed=True,
        first_final_index=session["first_final_index"],
        quantity_status={"pass": "PASS", "wrong": "FAIL"}.get(status, "UNDETERMINED"),
        support_status="PASS" if status in ("pass", "wrong") else "UNDETERMINED",
        reason={
            "pass": None,
            "wrong": "wrong_final_quantity",
            "no_final": "no_final",
            "unknown": "unsupported",
        }[status],
    )
    return assessment, session


def seal(reg, i, status="pass", objective="full_token_mean"):
    assessment, session = original_inputs(i, status)
    return d.seal_assessment(
        reg,
        objective=objective,
        assessment=assessment,
        session=session,
        source_members={"assessment": sha(encode(assessment)), "session": sha(encode(session))},
    )


def report(reg, statuses, objective="full_token_mean"):
    return d.summarize(
        reg,
        [
            d.adapt_assessment(reg, seal(reg, i, status, objective))
            for i, status in enumerate(statuses)
        ],
        objective=objective,
    )


def authority(metric="tool_success"):
    return d.preregister_independent_authority(
        metric,
        criterion_id="cpu-fixture-only-v1",
        criterion_text="Synthetic criterion, no real financial grading.",
        implementation_sha256="a" * 64,
        control_suite_sha256="b" * 64,
    )


def test_complete_preserved_but_subchecks_not_relabelled_as_independent_ability():
    reg = registration()
    result = report(reg, ["pass", "wrong", "unknown"])
    assert result["primary_utility"] == pytest.approx(1 / 3)
    assert result["metrics"]["CompletePass"]["fail"] == 2
    assert result["metrics"]["observed_support_chain"]["pass"] == 2
    assert result["metrics"]["support_conditioned_final_quantity"]["fail"] == 1
    assert result["metrics"]["tool_success"]["unknown"] == 3
    assert result["metrics"]["final_success"]["unknown"] == 3
    assert result["metrics"]["tool_success"]["identified_success_rate_bounds"] == [0, 1]
    assert result["confirmation_may_choose_loss_weights_or_candidates"] is False


def test_no_final_and_unknown_preserve_fixed_denominator_without_unknown_as_failure():
    result = report(registration(), ["pass", "no_final", "unknown"])
    assert result["registered_total"] == 3
    assert result["no_final_count"] == 1
    assert result["metrics"]["final_success"]["fail"] == 1
    assert result["metrics"]["final_success"]["unknown"] == 2
    assert result["metrics"]["tool_success"]["fail"] == 0
    assert result["metrics"]["tool_success"]["credited_success_rate"] == 0
    assert result["metrics"]["tool_success"]["unknown_zero_credit_is_not_observed_failure"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("pool", "C"),
        ("seed", True),
        ("seed", -1),
        ("split", "train"),
        ("execution_kind", "actual"),
        ("materials_manifest_id", ""),
        ("pi_id", None),
    ],
)
def test_registration_invalid_admission(field, value):
    with pytest.raises(ValueError):
        registration(**{field: value})


@pytest.mark.parametrize(
    "mutation", ["duplicate", "missing_group", "bad_hash", "bad_task", "extra_private"]
)
def test_registration_rejects_bad_panel(mutation):
    rows = tasks()
    if mutation == "duplicate":
        rows[1]["task_id"] = rows[0]["task_id"]
    elif mutation == "missing_group":
        rows[1]["group"] = rows[0]["group"]
    elif mutation == "bad_hash":
        rows[0]["public_messages_sha256"] = "not-a-hash"
    elif mutation == "bad_task":
        rows[0]["task_id"] = "other"
    else:
        rows[0]["answer"] = 7
    base = registration()
    with pytest.raises(ValueError):
        d.build_registration(
            rows,
            **{
                key: base[key]
                for key in (
                    "pool",
                    "seed",
                    "split",
                    "materials_manifest_id",
                    "pi_id",
                    "surface_manifest_id",
                    "frozen_pair_id",
                )
            },
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("financial_valid", 1),
        ("complete_trajectory_qualified", False),
        ("is_primary_utility_score", False),
        ("raw_history_and_tools_replayed", False),
        ("support_status", "FAIL"),
        ("support_status", "UNDETERMINED"),
        ("quantity_status", "UNDETERMINED"),
        ("first_final_index", 10),
        ("session_id", "evaluation_session:other"),
    ],
)
def test_assessment_must_be_authoritative_consistent_full_qualification(field, value):
    reg = registration()
    assessment, session = original_inputs(0)
    assessment[field] = value
    assessment = resign_original(assessment)
    with pytest.raises(ValueError):
        d.seal_assessment(
            reg,
            objective="full_token_mean",
            assessment=assessment,
            session=session,
            source_members={"assessment": sha(encode(assessment)), "session": sha(encode(session))},
        )


def test_generic_success_or_answer_only_flag_never_counts_as_complete():
    reg = registration()
    assessment, session = original_inputs(0, "unknown")
    assessment.update(success=True, answer_only=True)
    evidence = d.seal_assessment(
        reg,
        objective="full_token_mean",
        assessment=resign_original(assessment),
        session=session,
        source_members={
            "assessment": sha(encode(resign_original(assessment))),
            "session": sha(encode(session)),
        },
    )
    verdict = d.adapt_assessment(reg, evidence)
    assert verdict["metrics"]["CompletePass"] == "FAIL"
    assert verdict["metrics"]["tool_success"] == "UNKNOWN"


@pytest.mark.parametrize("kind", ["assessment", "session"])
def test_source_bytes_and_original_content_identity_are_checked(kind):
    reg = registration()
    evidence = seal(reg, 0)
    original_id = evidence[kind]["id"]
    evidence[kind]["untrusted_extra"] = True
    with pytest.raises(ValueError, match="original_content_identity"):
        d.adapt_assessment(reg, resign(evidence))
    evidence[kind] = resign_original(evidence[kind])
    assert evidence[kind]["id"] != original_id
    with pytest.raises(ValueError, match="exact_source_member_bytes"):
        d.adapt_assessment(reg, resign(evidence))


@pytest.mark.parametrize(
    "field,value",
    [
        ("pool", "B"),
        ("seed", 29),
        ("split", "confirm"),
        ("surface_manifest_id", "surface:other"),
        ("registration_id", "other"),
    ],
)
def test_sealed_result_wrong_run_binding_hard_rejected_even_after_rehash(field, value):
    reg = registration()
    evidence = seal(reg, 0)
    evidence[field] = value
    with pytest.raises(ValueError, match="evidence_registration_join"):
        d.adapt_assessment(reg, resign(evidence))


@pytest.mark.parametrize(
    "key,value",
    [
        ("task_id", "task_" + "f" * 64),
        ("family", "other_financial"),
        ("surface_version_id", "surface:wrong"),
        ("public_messages_sha256", "d" * 64),
    ],
)
def test_original_runtime_public_join_cannot_change(key, value):
    reg = registration()
    assessment, session = original_inputs(0)
    session["identity"][key] = value
    session = resign_original(session)
    assessment["session_id"] = session["id"]
    assessment = resign_original(assessment)
    with pytest.raises(ValueError, match="exact_assessment_session_public_join"):
        d.seal_assessment(
            reg,
            objective="full_token_mean",
            assessment=assessment,
            session=session,
            source_members={"assessment": sha(encode(assessment)), "session": sha(encode(session))},
        )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "wrong_objective", "tampered_metric"])
def test_fixed_denominator_result_set_hard_gates(mutation):
    reg = registration()
    rows = [d.adapt_assessment(reg, seal(reg, i)) for i in range(3)]
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[1] = rows[0]
    elif mutation == "wrong_objective":
        rows[0] = d.adapt_assessment(reg, seal(reg, 0, objective="hierarchical"))
    else:
        rows[0]["metrics"]["tool_success"] = "PASS"
        rows[0] = resign(rows[0])
    with pytest.raises(ValueError):
        d.summarize(reg, rows, objective="full_token_mean")


def test_reordered_outputs_are_exactly_rejoined_not_silently_reweighted():
    reg = registration()
    rows = [
        d.adapt_assessment(reg, seal(reg, i, status))
        for i, status in enumerate(["pass", "wrong", "unknown"])
    ]
    assert d.summarize(reg, rows, objective="full_token_mean") == d.summarize(
        reg, rows[::-1], objective="full_token_mean"
    )


def test_pair_identifies_complete_effect_but_unknown_tool_effect_remains_unidentified():
    reg = registration()
    full = report(reg, ["pass", "no_final", "unknown"])
    hierarchical = report(reg, ["pass", "pass", "unknown"], "hierarchical")
    pair = d.paired_compare(reg, full, hierarchical)
    assert pair["metrics"]["CompletePass"]["mean_credit_delta"] == pytest.approx(1 / 3)
    assert pair["metrics"]["CompletePass"]["identified_mean_effect_bounds"] == [1 / 3, 1 / 3]
    assert pair["metrics"]["tool_success"]["fully_observed_pairs"] == 0
    assert pair["metrics"]["tool_success"]["identified_mean_effect_bounds"] == [-1, 1]
    assert pair["metrics"]["tool_success"]["mean_credit_delta"] == 0
    assert pair["paired_tasks"][0]["metrics"]["tool_success"]["observed_delta"] is None
    assert pair["supports_causal_efficacy_claim"] is False
    assert pair["selected_objective"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("pool", "B"),
        ("seed", 29),
        ("split", "confirm"),
        ("materials_manifest_id", "materials:other"),
        ("pi_id", "pi:changed"),
        ("surface_manifest_id", "surface:other"),
        ("frozen_pair_id", "pair:other"),
    ],
)
def test_pair_rejects_different_registration(field, value):
    reg = registration()
    other = registration(**{field: value})
    with pytest.raises(ValueError):
        d.paired_compare(
            reg, report(reg, ["pass"] * 3), report(other, ["pass"] * 3, "hierarchical")
        )


def test_pair_rejects_swapped_conditions_or_rehashed_score():
    reg = registration()
    full = report(reg, ["pass"] * 3)
    hierarchical = report(reg, ["pass"] * 3, "hierarchical")
    with pytest.raises(ValueError):
        d.paired_compare(reg, hierarchical, full)
    full["primary_utility"] = 0
    with pytest.raises(ValueError, match="pair_same_registration"):
        d.paired_compare(reg, resign(full), hierarchical)


def test_preregistered_predicate_interface_is_not_production_authorization():
    auth = authority()
    reg = registration(independent_authorities=[auth])
    evidence = seal(reg, 0, "unknown")
    verdict = d.seal_independent_verdict(
        reg, evidence, authority=auth, status="PASS", reason="synthetic predicate output"
    )
    output = d.adapt_assessment(reg, evidence, independent_verdicts=[verdict])
    assert output["metrics"]["tool_success"] == "PASS"
    assert output["metrics"]["CompletePass"] == "FAIL"
    assert auth["production_validated"] is False
    assert verdict["actual_predicate_execution_attested"] is False
    with pytest.raises(ValueError, match="production_adapter_not_validated"):
        registration(independent_authorities=[auth], execution_kind="actual_financial")


def test_unregistered_independent_authority_and_duplicate_predicate_rejected():
    auth = authority()
    reg = registration()
    with pytest.raises(ValueError, match="authority_not_preregistered"):
        d.seal_independent_verdict(
            reg, seal(reg, 0), authority=auth, status="PASS", reason="fixture"
        )
    reg = registration(independent_authorities=[auth])
    evidence = seal(reg, 0)
    verdict = d.seal_independent_verdict(
        reg, evidence, authority=auth, status="PASS", reason="fixture"
    )
    with pytest.raises(ValueError, match="duplicate_independent_verdict"):
        d.adapt_assessment(reg, evidence, independent_verdicts=[verdict, verdict])


def test_independent_predicate_cannot_be_replayed_for_other_task():
    auth = authority()
    reg = registration(independent_authorities=[auth])
    evidence = seal(reg, 0)
    verdict = d.seal_independent_verdict(
        reg, evidence, authority=auth, status="PASS", reason="fixture"
    )
    with pytest.raises(ValueError, match="independent_verdict_exact_parent"):
        d.adapt_assessment(reg, seal(reg, 1), independent_verdicts=[verdict])


@pytest.mark.parametrize("status", ["PASS", "UNKNOWN"])
def test_no_final_logically_fails_final_even_with_conflicting_independent_verdict(status):
    auth = authority("final_success")
    reg = registration(independent_authorities=[auth])
    evidence = seal(reg, 0, "no_final")
    verdict = d.seal_independent_verdict(
        reg, evidence, authority=auth, status=status, reason="fixture"
    )
    with pytest.raises(ValueError, match="no_final_cannot_pass_or_become_unknown"):
        d.adapt_assessment(reg, evidence, independent_verdicts=[verdict])


def test_authority_cannot_just_claim_production_validated():
    auth = authority()
    auth["production_validated"] = True
    with pytest.raises(ValueError, match="authority_semantics"):
        registration(independent_authorities=[resign(auth)])


def test_output_owns_deep_copied_input_data():
    reg = registration()
    evidence = seal(reg, 0)
    result = d.adapt_assessment(reg, evidence)
    saved = copy.deepcopy(result)
    evidence["assessment"]["financial_valid"] = False
    reg["tasks"][0]["source_cluster"] = "mutated"
    assert result == saved
