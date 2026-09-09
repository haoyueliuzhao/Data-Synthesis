"""Constructed controls only: no provider, real pair measurement, or answer oracle."""

import copy

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_open_materialization.canonical import (
    normalize_expression,
)
from trusted_synthesis.experiments.finance_qa_vnext_open_materialization.measurement import (
    compare,
    measure,
)
from trusted_synthesis.experiments.finance_qa_vnext_open_materialization.plan import (
    TASKS,
    encode,
    record,
    sha,
)


def source(source_id, value="2", **extra):
    return {
        "kind": "source",
        "source_id": source_id,
        "source_exact": value,
        "executed_exact": value,
        "attribution": "reviewer_interpretation",
        "evidence_verified": True,
        **extra,
    }


def constant(value, reason="reviewed structural scalar"):
    return {"kind": "constant", "value": value, "reason": reason, "evidence_verified": True}


def mapped(expression, bindings, previous=None):
    result = normalize_expression(expression, bindings, previous)
    assert result["status"] == "MAPPED", result
    return result


def same(left, right):
    assert left["normal_form"] == right["normal_form"]
    assert left["active_source_ids"] == right["active_source_ids"]


def test_01_alpha_whitespace_order_and_attribution_do_not_create_classes():
    left = mapped("a + b", {"body.left": source("s:a"), "body.right": source("s:b")})
    right = mapped(
        "renamed_b+renamed_a",
        {
            "body.right": source("s:a", attribution="model_claim", mapping_origin="explicit"),
            "body.left": source("s:b"),
        },
    )
    same(left, right)


def test_02_sum_average_and_arithmetic_mean_have_exact_arity():
    average = mapped(
        "avg([a,b,c])",
        {f"body.args.0.elts.{index}": source("s:" + name) for index, name in enumerate("abc")},
    )
    manual = mapped(
        "sum(a,b,c)/3",
        {
            **{f"body.left.args.{index}": source("s:" + name) for index, name in enumerate("abc")},
            "body.right": constant("3", "three observed members"),
        },
    )
    same(average, manual)
    wrong = mapped(
        "(a+b)/3",
        {
            "body.left.left": source("s:a"),
            "body.left.right": source("s:b"),
            "body.right": constant("3"),
        },
    )
    two_member = mapped("avg(a,b)", {"body.args.0": source("s:a"), "body.args.1": source("s:b")})
    assert wrong["normal_form"] != two_member["normal_form"]


def test_03_pure_rational_unit_scale_can_move_across_formula():
    left = mapped(
        "x/(y/1000)*100",
        {
            "body.left.left": source("s:x"),
            "body.left.right.left": source("s:y"),
            "body.left.right.right": constant("1000", "unit scale"),
            "body.right": constant("100", "percent"),
        },
    )
    right = mapped(
        "100000*x/y",
        {
            "body.left.left": constant("100000", "combined unit and percent scale"),
            "body.left.right": source("s:x"),
            "body.right": source("s:y"),
        },
    )
    same(left, right)


def test_04_real_result_reference_expands_symbolically_not_by_result_value():
    previous = mapped("a+b", {"body.left": source("s:a"), "body.right": source("s:b")})
    split = mapped(
        "subtotal-c",
        {
            "body.left": {
                "kind": "result",
                "result_id": "tool:1",
                "executed_exact": "4",
                "evidence_verified": True,
            },
            "body.right": source("s:c"),
        },
        {"tool:1": previous},
    )
    whole = mapped(
        "a+b-c",
        {
            "body.left.left": source("s:a"),
            "body.left.right": source("s:b"),
            "body.right": source("s:c"),
        },
    )
    same(split, whole)
    numeric_only = mapped("4-c", {"body.left": constant("4"), "body.right": source("s:c")})
    assert split["normal_form"] != numeric_only["normal_form"]


def test_05_zero_contribution_sources_remain_in_execution_view_not_active_support():
    plain = mapped("a", {"body": source("s:a")})
    for expression, bindings in (
        (
            "a+0*b",
            {
                "body.left": source("s:a"),
                "body.right.left": constant("0"),
                "body.right.right": source("s:b"),
            },
        ),
        (
            "a+(b-b)",
            {
                "body.left": source("s:a"),
                "body.right.left": source("s:b"),
                "body.right.right": source("s:b"),
            },
        ),
    ):
        extra = mapped(expression, bindings)
        same(plain, extra)
        assert extra["all_source_ids"] == ["s:a", "s:b"]
        assert extra["active_source_ids"] == ["s:a"]


def test_06_equal_numbers_do_not_merge_sources_or_periods():
    earlier = mapped("2", {"body": source("s:period_1", "2")})
    later = mapped("2", {"body": source("s:period_2", "2")})
    assert earlier["normal_form"] != later["normal_form"]
    unknown = normalize_expression("2", {})
    assert unknown["status"] == "UNDETERMINED"
    assert unknown["reason"].startswith("missing_occurrence_binding")
    conflict = normalize_expression(
        "a-b",
        {"body.left": source("s:same", "2"), "body.right": source("s:same", "3")},
    )
    assert conflict["status"] == "UNDETERMINED"
    assert conflict["reason"] == "inconsistent_source_values:s:same"


@pytest.mark.parametrize(
    "route", ("global_vs_regional", "cashflow_vs_reconstruction", "balances_vs_rollforward")
)
def test_07_alternative_financial_support_is_not_rewritten_by_registered_identities(route):
    direct = mapped(
        "a-b",
        {
            "body.left": source(route + ":reported_end", "10"),
            "body.right": source(route + ":reported_start", "2"),
        },
    )
    rebuilt = mapped(
        "c+d",
        {
            "body.left": source(route + ":component_1", "3"),
            "body.right": source(route + ":component_2", "5"),
        },
    )
    assert direct["normal_form"] != rebuilt["normal_form"]
    assert direct["active_source_ids"] != rebuilt["active_source_ids"]


def test_08_evidenced_literal_and_named_source_match_without_fabricating_claims():
    literal = mapped("8.1", {"body": source("s:quantity", "81/10")})
    named = mapped("floor_area", {"body": source("s:quantity", "8.1", attribution="model_claim")})
    same(literal, named)
    rational_scalar = mapped("81/10", {"body.left": constant("81"), "body.right": constant("10")})
    assert literal["normal_form"] != rational_scalar["normal_form"]
    signed = mapped("-141", {"body": source("s:signed_payment", "-141")})
    named_signed = mapped("payment", {"body": source("s:signed_payment", "-141")})
    same(signed, named_signed)
    doubled = normalize_expression(
        "-141",
        {"body": source("s:signed_payment", "-141"), "body.operand": constant("141")},
    )
    assert doubled["status"] == "UNDETERMINED"
    assert doubled["reason"] == "unused_occurrence_binding"


@pytest.mark.parametrize(
    "mutation",
    ("unverified", "misbound", "literal_mismatch", "no_reason", "unknown_kind", "extra_address"),
)
def test_09_missing_or_conflicting_binding_evidence_is_undetermined(mutation):
    bindings = {"body": source("s:a", "2")}
    if mutation == "unverified":
        bindings["body"]["evidence_verified"] = False
    elif mutation == "misbound":
        bindings["body"]["executed_exact"] = "3"
    elif mutation == "literal_mismatch":
        bindings["body"]["executed_exact"] = bindings["body"]["source_exact"] = "3"
    elif mutation == "no_reason":
        bindings["body"] = constant("2", "")
    elif mutation == "unknown_kind":
        bindings["body"]["kind"] = "numeric_match"
    else:
        bindings["body.unused"] = source("s:b")
    result = normalize_expression("2", bindings)
    assert result["status"] == "UNDETERMINED"
    assert result["normal_form"] is None


@pytest.mark.parametrize("expression", ("abs(a)", "min(a,b)", "max(a,b)", "a**2", "a//b", "a[0]"))
def test_10_unsupported_operations_are_not_surface_text_classes(expression):
    assert normalize_expression(expression, {})["status"] == "UNDETERMINED"


def test_11_source_factor_cancellation_and_lost_domain_are_not_asserted_equivalent():
    cancellation = normalize_expression(
        "a/a", {"body.left": source("s:a"), "body.right": source("s:a")}
    )
    assert cancellation["status"] == "UNDETERMINED"
    assert cancellation["reason"] == "source_dependent_cancellation"
    nested = normalize_expression(
        "x/(y/z)",
        {
            "body.left": source("s:x"),
            "body.right.left": source("s:y"),
            "body.right.right": source("s:z"),
        },
    )
    assert nested["status"] == "UNDETERMINED"
    assert nested["reason"] == "source_domain_elimination"
    left = mapped(
        "x/y+z/y",
        {
            "body.left.left": source("s:x"),
            "body.left.right": source("s:y"),
            "body.right.left": source("s:z"),
            "body.right.right": source("s:y"),
        },
    )
    right = mapped(
        "(x+z)/y",
        {
            "body.left.left": source("s:x"),
            "body.left.right": source("s:z"),
            "body.right": source("s:y"),
        },
    )
    same(left, right)


def test_12_reference_must_be_previously_mapped_and_structurally_canonical():
    binding = {
        "body": {
            "kind": "result",
            "result_id": "tool:1",
            "executed_exact": "2",
            "evidence_verified": True,
        }
    }
    assert normalize_expression("prior", binding)["status"] == "UNDETERMINED"
    valid = mapped("a", {"body": source("s:a")})
    forged = copy.deepcopy(valid)
    forged["normal_form"]["numerator"][0]["powers"][0][1] = -1
    assert normalize_expression("prior", binding, {"tool:1": forged})["status"] == "UNDETERMINED"
    failed = {**valid, "status": "UNDETERMINED"}
    assert normalize_expression("prior", binding, {"tool:1": failed})["status"] == "UNDETERMINED"
    same(mapped("prior", binding, {"tool:1": valid}), valid)


def toy_row(label, arm="T", task="N1", valid=True):
    return {
        "id": "constructed-source-row:" + label,
        "label": label,
        "arm": arm,
        "task_key": task,
        "formula_driven_trace_verified": valid,
    }


def toy_projection(row, revision_path=None, status="MAPPED"):
    signature = {
        "population": row["arm"],
        "task_version": "constructed-task:" + row["task_key"],
        "source_document_id": "constructed-document:" + row["task_key"],
        "goal_scope": {"quantity": "constructed_amount", "period": "period_1", "unit": "unit"},
        "active_source_support": ["constructed:source"],
        "answer_connected_source_rational_form": mapped(
            "a", {"body": source("constructed:source")}
        )["normal_form"],
        "substantive_public_revision_path": revision_path or [],
    }
    return record(
        "constructed_open_projection",
        population=row["arm"],
        task_key=row["task_key"],
        task_version=signature["task_version"],
        source_document_id=signature["source_document_id"],
        session_label=row["label"],
        source_closeout_id=row["id"],
        status=status,
        reason="constructed_unresolved_mapping" if status == "UNDETERMINED" else None,
        behavior_signature=signature if status == "MAPPED" else None,
        behavior_key=sha(encode(signature)) if status == "MAPPED" else None,
    )


def test_13_complete_signature_preserves_substantive_revisions_not_format_noise():
    left = toy_projection(toy_row("constructed-T-1"))
    right = toy_projection(toy_row("constructed-T-2"))
    right["raw_interface_recoveries"] = [{"before": "81/10", "after": "8.1"}]
    assert compare(left, right) == "EQUIVALENT"
    revised = toy_projection(
        toy_row("constructed-T-3"),
        revision_path=[
            {"before": "period_0", "after": "period_1", "kind": "period_pairing_change"}
        ],
    )
    assert (
        left["behavior_signature"]["answer_connected_source_rational_form"]
        == revised["behavior_signature"]["answer_connected_source_rational_form"]
    )
    assert compare(left, revised) == "DISTINCT"
    assert compare(left, toy_projection(toy_row("constructed-A-1", arm="A"))) == "NOT_COMPARABLE"
    assert compare(left, toy_projection(toy_row("constructed-N2-1", task="N2"))) == "NOT_COMPARABLE"
    assert (
        compare(left, toy_projection(toy_row("constructed-unknown"), status="UNDETERMINED"))
        == "UNDETERMINED"
    )


def test_14_synthetic_full_cohort_keeps_five_t_pairs_and_a_separate():
    rows = [
        toy_row(
            f"constructed-{arm}-{task}-{repeat}",
            arm=arm,
            task=task,
            valid=(task != "N3" if arm == "T" else task == "N1"),
        )
        for arm in ("T", "A")
        for task in TASKS
        for repeat in (1, 2)
    ]
    projections = [toy_projection(row) for row in rows if row["formula_driven_trace_verified"]]
    original_rows, original_projections = copy.deepcopy(rows), copy.deepcopy(projections)
    result = measure(projections, rows)
    assert rows == original_rows and projections == original_projections
    assert len(result["primary_pairs"]) == 5
    assert result["primary_pair_status_counts"] == {"EQUIVALENT": 5}
    assert all(pair["population"] == "T" for pair in result["primary_pairs"])
    assert result["unavailable_primary_pairs"] == []
    assert result["populations"]["T"]["original_full_trajectory_yield"]["fraction"] == "5/6"
    assert result["populations"]["A"]["original_full_trajectory_yield"]["fraction"] == "1/6"
    t_task = result["populations"]["T"]["tasks"]["N1"]
    a_task = result["populations"]["A"]["tasks"]["N1"]
    assert t_task["known_classes"][0]["class_id"] != a_task["known_classes"][0]["class_id"]
    assert t_task["known_classes"][0]["count"] == 2
    assert list(t_task["conditional_distribution"].values()) == ["1"]
    assert len(result["session_class_ids"]) == 12
    assert result["source_row_count"] == 24
    assert result["training_weights_assigned"] is False
    assert result["six_task_training_distribution_implemented"] is False


@pytest.mark.parametrize("missing", (False, True))
def test_15_unresolved_or_missing_mapping_keeps_original_valid_mass(missing):
    rows = [toy_row("constructed-known"), toy_row("constructed-unresolved")]
    projections = [toy_projection(rows[0])]
    if not missing:
        projections.append(toy_projection(rows[1], status="UNDETERMINED"))
    result = measure(projections, rows)
    task = result["populations"]["T"]["tasks"]["N1"]
    assert task["valid_denominator"] == 2
    assert task["mapped_count"] == task["unresolved_count"] == 1
    assert list(task["known_class_masses"].values()) == ["1/2"]
    assert task["unresolved_mass"] == "1/2"
    assert task["conditional_distribution"] is None
    assert result["primary_pairs"][0]["status"] == "UNDETERMINED"
    assert result["session_class_ids"]["constructed-unresolved"] is None


def test_16_no_valid_support_is_null_not_a_zero_behavior_or_deleted_task():
    rows = [toy_row("constructed-N3-1", task="N3", valid=False)]
    result = measure([], rows)
    assert result["original_task_marginal"] == {task: "1/6" for task in TASKS}
    for population in ("T", "A"):
        assert tuple(result["populations"][population]["tasks"]) == TASKS
        n3 = result["populations"][population]["tasks"]["N3"]
        assert n3["conditional_distribution"] is None
        assert n3["unresolved_mass"] is None
        assert n3["no_valid_support_does_not_establish_no_behavior"] is True
    assert result["N3_regraded"] is False


@pytest.mark.parametrize(
    "mutation", ("omitted_revision", "stale_key", "duplicate", "invalid_source", "reassigned_arm")
)
def test_17_measurement_rejects_broken_signature_or_population_integrity(mutation):
    rows = [toy_row("constructed-integrity")]
    projections = [toy_projection(rows[0])]
    if mutation == "omitted_revision":
        del projections[0]["behavior_signature"]["substantive_public_revision_path"]
        projections[0]["behavior_key"] = sha(encode(projections[0]["behavior_signature"]))
    elif mutation == "stale_key":
        projections[0]["behavior_signature"]["substantive_public_revision_path"] = [
            {"changed": "source"}
        ]
    elif mutation == "duplicate":
        projections.append(copy.deepcopy(projections[0]))
    elif mutation == "invalid_source":
        rows[0]["formula_driven_trace_verified"] = False
    else:
        projections[0]["population"] = "A"
    with pytest.raises(ValueError, match="measurement\\."):
        measure(projections, rows)
