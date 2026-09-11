"""Finite source-class weights and selection; no Teacher or Student execution."""

import ast
import inspect
from fractions import Fraction

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.derive import (
    fixed_selection,
)
from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.plan import (
    CONDITIONS,
    GROUPS,
    SEEDS,
    TASKS,
    X3_KEYS,
    package_mass,
    select_candidate,
    utility,
)


@pytest.mark.parametrize("arm", CONDITIONS)
def test_exact_mass_table_and_six_task_marginals(arm):
    weights = {}
    for task in TASKS:
        routes = ("D", "A") if task == "X3C" else ("control",)
        weights[task] = [package_mass(arm, task, route) for route in routes for _ in range(3)]
        assert sum(weights[task]) == Fraction(1, 6)
    assert sum(map(sum, weights.values())) == 1
    assert sum(map(len, weights.values())) == 21


def test_local_loss_wiring_same_parameter_state():
    losses = {
        "D": [Fraction(2), Fraction(3), Fraction(7)],
        "A": [Fraction(9), Fraction(4), Fraction(8)],
    }
    values = {
        arm: sum(
            package_mass(arm, "X3C", r) * loss for r, group in losses.items() for loss in group
        )
        for arm in CONDITIONS
    }
    delta = (sum(losses["A"]) - sum(losses["D"])) / 3 / 36
    assert values["plus_A"] - values["pi0"] == delta
    assert values["minus_D"] - values["pi0"] == -delta


def matrix(zero, plus, minus):
    return {
        arm: {s: value for s in SEEDS}
        for arm, value in zip(CONDITIONS, (zero, plus, minus), strict=True)
    }


@pytest.mark.parametrize(
    ("values", "chosen"),
    [
        (("1/2", "1/2", "1/2"), "pi0"),
        (("1/2", "1/3", "1/4"), "pi0"),
        (("1/2", "2/3", "2/3"), "plus_A"),
        (("1/2", "2/3", "3/4"), "minus_D"),
        (("1/2", "7/12", "1/2"), "plus_A"),
    ],
)
def test_strict_positive_and_predeclared_ties(values, chosen):
    result = select_candidate(matrix(*values))
    assert result["selected_condition"] == chosen
    assert result["confirmation_required"] == (chosen != "pi0")
    assert result["no_runner_up_after_confirmation"]


def test_unknowns_stay_in_registered_denominator():
    assert utility({g: (1, 4) for g in GROUPS}) == Fraction(1, 4)


def support_rows():
    result = []
    for key in ("X1", "X2", "X3C"):
        for rep in range(1, 9):
            route = "D" if rep in (1, 2, 7, 8) or key != "X3C" else "A"
            result.append(
                {
                    "label": f"N_{key}_{rep:02d}",
                    "task_key": key,
                    "arm": "N",
                    "formula_driven_trace_verified": True,
                    "projection": {"status": "MAPPED", "behavior_key": X3_KEYS[route]},
                    "historical_behavior_label": "PURE_D" if route == "D" else "OTHER_VALID_CLASS",
                }
            )
    return result


def test_fixed_order_not_prose_quality_or_holdout_replacement():
    selection = fixed_selection(list(reversed(support_rows())))
    assert [r["label"] for r in selection["train"]] == [
        "N_X1_01",
        "N_X1_02",
        "N_X1_03",
        "N_X2_01",
        "N_X2_02",
        "N_X2_03",
        "N_X3C_01",
        "N_X3C_02",
        "N_X3C_07",
        "N_X3C_03",
        "N_X3C_04",
        "N_X3C_05",
    ]
    assert [r["label"] for r in selection["heldout"]] == ["N_X3C_08", "N_X3C_06"]
    rows = support_rows()
    rows[-1]["formula_driven_trace_verified"] = False
    assert fixed_selection(rows)["status"] == "INPUT_INADEQUATE"


def test_E_support_never_substitutes_N_support():
    rows = support_rows()
    for row in rows:
        if row["task_key"] == "X3C" and row["label"].endswith("_08"):
            row["arm"] = "E"
    assert fixed_selection(rows)["status"] == "INPUT_INADEQUATE"


def test_exact_encoder_body_is_unchanged_from_existing_representation():
    from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.tokens import (
        encode_candidate as original,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.tokens import (
        encode_candidate as current,
    )

    assert ast.dump(ast.parse(inspect.getsource(current))) == ast.dump(
        ast.parse(inspect.getsource(original))
    )


def test_whole_package_coefficients_not_row_or_global_token_mean():
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.plan import record
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.weights import (
        build_view,
        validate_view,
    )

    packages, rows = [], []
    for task in TASKS:
        routes = ("D", "A") if task == "X3C" else ("D",) if task in {"X1", "X2"} else ("control",)
        for route in routes:
            for rep in range(3):
                label = f"{task}_{route}_{rep}"
                packages.append(dict(session_label=label, task_key=task, route=route))
                for index, length in enumerate((rep + 2, rep + 5)):
                    rows.append(
                        dict(
                            session_label=label,
                            task_key=task,
                            response_index=index,
                            target_token_count=length,
                            sequence_length=100 + length,
                            token_reference={"path": f"{label}/{index}.json"},
                        )
                    )
    view = build_view(packages, rows)
    assert view["totals"]["packages"] == 21
    assert view["totals"]["rows"] == 42
    row = view["rows"][-1]
    assert Fraction(row["coefficient"]["pi0"]) * row["package_target_token_count"] == Fraction(
        1, 36
    )
    row["coefficient"]["plus_A"] = row["coefficient"]["pi0"]
    changed = record(
        "source_class_weight_view",
        **{k: v for k, v in view.items() if k not in {"id", "schema_version"}},
    )
    with pytest.raises(ValueError, match="coefficients"):
        validate_view(changed)


def test_local_generation_and_audit_algorithms_not_changed():
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student import evaluate as original_audit
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student import (
        runtime as original_runtime,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility import (
        runtime,
        student_audit,
    )

    for old, new in ((original_runtime, runtime), (original_audit, student_audit)):
        names = (
            ("initial_messages", "_require_unicode_scalars", "run_session")
            if old is original_runtime
            else ("_initial", "_unicode_scalars", "_source_result", "_calculation", "audit_session")
        )
        for name in names:
            assert ast.dump(ast.parse(inspect.getsource(getattr(old, name)))) == ast.dump(
                ast.parse(inspect.getsource(getattr(new, name)))
            )


def test_mask_registration_counts_fixed_and_reproducible():
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.stage import (
        masked_registrations,
        variant_order,
    )

    registrations = [{"task_key": f"D{i:02d}", "group": GROUPS[(i - 1) // 4]} for i in range(1, 13)]
    first = masked_registrations("dev", variant_order(), registrations)
    assert len(first) == 108
    assert first == masked_registrations("dev", variant_order(), registrations)
    assert len({(r["variant"], r["task_key"]) for r in first.values()}) == 108


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("$6M", "PASS"),
        ("$6K", "UNDETERMINED"),
        ("$6", "FAIL"),
    ],
)
def test_synthetic_local_tool_Final_to_full_trace(tmp_path, answer, expected):
    """Synthetic calculator fixtures, not Teacher replay or real Student sessions."""
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.plan import (
        encode,
        record,
        sha,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.runtime import (
        run_session,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.student_audit import (
        audit_session,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.student_review import (
        qualify,
        review_template,
    )

    facts = {
        sid: {"id": sid, "value": value} for sid, value in (("source:e", "10"), ("source:b", "4"))
    }
    public = record(
        "synthetic_public",
        task_id="synthetic",
        numeric_catalog=list(facts.values()),
        segments={},
        question="What is the change in millions of USD?",
    )
    private = {
        "unit": "USD_million",
        "facts": facts,
        "target": {"op": "subtract", "args": ["source:e", "source:b"]},
    }
    script = [
        {
            "message": "Net change in millions of USD = ending source:e minus beginning source:b.",
            "tool": "calculate",
            "arguments": {
                "expression": "e-b",
                "variables": {"e": "10", "b": "4"},
                "sources": {"e": "source:e", "b": "source:b"},
            },
        },
        {"final": {"value": "6", "unit": "USD_million", "answer": answer, "result_id": "tool:1"}},
    ]
    sequence = iter(script)

    def decoder(messages):
        content = encode(next(sequence)).decode()
        return dict(
            content=content,
            finish_reason="stop",
            generation_invoked=True,
            prompt_token_count=1,
            generated_token_count=2,
            generated_token_ids=[100, 151645],
            public_content_token_ids=[100],
            elapsed_seconds=0,
            rendered_prompt_sha256=sha(encode(messages)),
            prompt_truncated=False,
            only_final_actual_EOS_removed_from_public_text=True,
        )

    identity = record("synthetic_model_not_Student", synthetic_control=True)
    result = run_session(public, tmp_path, decoder, identity)
    assert result["tool_calls"] == 1 and result["terminal"] == "model_final"
    audit = audit_session(tmp_path, public, identity)
    review = review_template(audit, public, private)
    review["author"] = "synthetic-control"
    before = {"response_index": 0, "quote": encode(script[0]).decode()}
    final = {"response_index": 1, "quote": encode(script[1]).decode()}
    for field in (
        "formula_applicability",
        "variable_correspondence",
        "unit_handling",
        "publication_alignment",
        "final_answer_consistency",
    ):
        review[field] = {
            "status": "PASS",
            "evidence": [
                final if field in {"publication_alignment", "final_answer_consistency"} else before
            ],
            "explanation": "Synthetic correct source and financial-unit fixture.",
        }
    review["publication"].update(direction_multiplier=1, evidence=[final])
    review["calculation"].update(
        call_id="tool:1", unit="USD_million", direction_multiplier=1, evidence=[before]
    )
    qualified = qualify(audit, review, public, private)
    assert qualified["task_answer_status"] == expected
    assert qualified["complete_verifiable_trajectory"] == (expected == "PASS")


def test_complete_trajectory_utility_not_replaced_by_answer_or_route():
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.evaluate import (
        summarize,
    )

    rows = [
        {
            "variant": "pi0_11",
            "group": group,
            "qualification": {
                "complete_verifiable_trajectory": False,
                "task_answer_status": "PASS",
                "delivery_status": "FINAL_DELIVERED",
                "trace_status": "NOT_ESTABLISHED",
            },
            "semantic_review": {"variable_correspondence": {"status": "UNDETERMINED"}},
            "actual_calculations": 1,
        }
        for group in GROUPS
        for _ in range(4)
    ]
    summary = summarize(rows, ["pi0_11"], 4)["pi0_11"]
    assert summary["utility"] == "0" and summary["answer_counts"] == {"PASS": 12}


def test_original_greedy_decoder_body_is_unchanged():
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student.inference import (
        LocalDecoder as Original,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.inference import (
        LocalDecoder,
    )

    assert ast.dump(ast.parse(inspect.getsource(Original))) == ast.dump(
        ast.parse(inspect.getsource(LocalDecoder))
    )


def test_original_training_hyperparameters_and_paired_orders():
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import (
        training_config as original_config,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student.train import (
        row_orders as original_orders,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.plan import (
        training_config,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.train import row_orders

    totals = {
        "packages": 21,
        "rows": 46,
        "target_tokens_per_pass": 6819,
        "sequence_tokens_per_pass": 348419,
    }
    config, old = training_config(totals), original_config()
    for key in (
        "revision",
        "base_dtype",
        "adapter_dtype",
        "lora_rank",
        "lora_alpha",
        "lora_dropout",
        "target_modules",
        "optimizer",
        "learning_rate",
        "betas",
        "eps",
        "weight_decay",
        "maximum_gradient_norm",
        "epochs",
        "optimizer_updates",
        "attention_implementation",
        "sdpa_backend",
        "gradient_checkpointing",
        "use_reentrant",
        "loss_dtype",
        "allow_tf32",
        "deterministic_algorithms",
        "maximum_sequence_length",
    ):
        assert config[key] == old[key]
    assert config["supervised_tokens_per_run"] == 68190
    assert config["sequence_tokens_per_run"] == 3484190
    for seed in SEEDS:
        assert row_orders(seed, 46) == original_orders(seed, 46)


def test_no_Final_student_publication_cannot_be_completed_from_tool():
    from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility import (
        student_quantity,
    )

    assert (
        student_quantity.final_amount_check(
            None, {"value": "6", "unit": "USD_million"}, {"unit": "USD_million"}
        )[
            "status"
        ]
        == "UNDETERMINED"
    )
