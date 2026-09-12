"""Public-only base-question guards; no model, private reference or real rewrite."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import periods
from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import guard
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import record

KINDS = ("difference", "relative_change", "arithmetic_mean", "argmax_then_lookup")


def fixture(kind="arithmetic_mean", *, instant=False, noncalendar=False, metric="revenue"):
    dates = (
        [("2019-09-30", "2020-09-27"), ("2020-09-28", "2021-10-03"), ("2021-10-04", "2022-10-02")]
        if noncalendar
        else [(f"{year}-01-01", f"{year}-12-31") for year in (2019, 2020, 2021)]
    )
    if kind in {"difference", "relative_change"}:
        dates = dates[:2]
    if instant:
        dates = [(None, end) for _, end in dates]
    rows = [
        {
            "start": start,
            "end": end,
            "period_type": "duration" if start else "instant",
            "period_id": periods.period_identity(start, end, "duration" if start else "instant"),
            "label_basis": "actual_interval" if noncalendar or instant else "calendar_year",
        }
        for start, end in dates
    ]
    operation = {"kind": kind, "metric_id": metric}
    metrics = [metric]
    if kind == "argmax_then_lookup":
        metrics = ["revenue", "net_income"]
        operation = {
            "kind": kind,
            "primary_metric_id": "revenue",
            "secondary_metric_id": "net_income",
            "candidate_count": 3,
            "same_actual_period_required": True,
        }
    elif kind == "arithmetic_mean":
        operation["operand_count"] = 3
    else:
        operation["direction"] = "current_minus_previous"
        if kind == "relative_change":
            operation.update(denominator="strictly_positive_previous", multiplier=100)
    body = {
        "schema": "actual_period_contract.v1",
        "task_id": "task_test",
        "source_cluster": "cik:0000012345",
        "quantity": {
            "arithmetic_mean": "three_annual_flow_mean",
            "argmax_then_lookup": "three_year_peak_then_same_period_metric",
        }.get(kind, kind),
        "metric_ids": metrics,
        "operation": operation,
        "periods": rows,
        "period_order": "chronological",
        "interval_boundaries": "inclusive",
        "fiscal_year_naming": "not_inferred_from_filing_fy_or_end_year",
    }
    contract = {
        **body,
        "id": "actual_period_contract:"
        + guard.sha(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()),
    }
    public = {
        "question": "Original public task wording."
        + "\n\n"
        + periods.render_public_periods(contract),
        "period_contract": contract,
        "quantity_contract": {
            "unit": "percent" if kind == "relative_change" else "million USD",
            "currency": None if kind == "relative_change" else "USD",
            "decimal_places": 2,
            "rounding": "half away from zero",
            "period_required": kind == "argmax_then_lookup",
        },
        "source_document": {
            "source_id": "public-original",
            "original_record_values_not_loaded": True,
        },
        "source_policy": "Complete original source remains available.",
        "tool_contract": {"Final": "First Final with actual period_id when required."},
    }
    identity = {
        "task_id": "task_test",
        "family": "public_family",
        "surface_version_id": "old_surface",
        "public_messages_sha256": guard.sha(guard.encode(guard.messages(public))),
        "parent_manifest_id": "old_manifest",
    }
    return public, identity


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("noncalendar", [False, True])
def test_selfcontained_canonical_protects_all_periods_and_original_suffix(kind, noncalendar):
    public, identity = fixture(kind, noncalendar=noncalendar)
    original = copy.deepcopy(public)
    spec = guard.build_spec(public, identity)
    value = guard.render_and_validate(spec["canonical_template"], spec)
    assert value["passed"]
    assert public == original
    for period in public["period_contract"]["periods"]:
        assert period["start"] in value["base_question"] and period["end"] in value["base_question"]
    assert guard.split_question(value["question"])[1] == guard.split_question(public["question"])[1]
    assert {key: val for key, val in value["public"].items() if key != "question"} == {
        key: val for key, val in public.items() if key != "question"
    }
    assert value["change_classification"]["category"] == "unchanged_or_format_only"
    assert spec["canonical_preparation_changed_original"]
    assert not spec["canonical_preparation_is_LLM_rewrite"]


@pytest.mark.parametrize("kind", ["difference", "relative_change"])
@pytest.mark.parametrize(
    "metric",
    [
        "cash_and_cash_equivalents",
        "cash_cash_equivalents_restricted_cash_and_restricted_cash_equivalents",
    ],
)
def test_stock_instant_and_account_scope_are_literal_slots(kind, metric):
    public, identity = fixture(kind, instant=True, metric=metric)
    spec = guard.build_spec(public, identity)
    result = guard.render_and_validate(spec["canonical_template"], spec)
    assert result["passed"] and "instant at" in result["base_question"]
    assert guard.METRIC_NAMES[metric] in result["base_question"]


@pytest.mark.parametrize("kind", KINDS)
def test_valid_lexical_variation_is_not_the_local_canonical_preparation(kind):
    spec = guard.build_spec(*fixture(kind))
    template = (
        spec["canonical_template"].replace("highest", "largest")
        if kind == "argmax_then_lookup"
        else spec["canonical_template"].replace("Calculate", "Determine")
    )
    result = guard.render_and_validate(template, spec)
    assert result["passed"]
    assert result["change_classification"]["category"] == "accepted_true_rewrite"


@pytest.mark.parametrize(
    "template",
    [
        "For <slot_entity>, compute the arithmetic mean of <slot_metric> over all three "
        "actual reporting periods <slot_periods>. <slot_output_instruction>",
        "Across exactly three actual annual periods: <slot_periods>, what was the "
        "arithmetic mean of <slot_metric> reported by <slot_entity>? <slot_output_instruction>",
    ],
)
def test_mean_affirmative_clause_reordering(template):
    assert guard.validate_base(template, guard.build_spec(*fixture()))["passed"]


@pytest.mark.parametrize(
    "template",
    [
        "For <slot_entity>, among all three actual annual periods: <slot_periods>, select "
        "the actual period having the maximum <slot_primary_metric>, then state "
        "<slot_secondary_metric> in that same actual period. <slot_output_instruction>",
        "Which of the three actual annual periods <slot_periods> had the highest "
        "<slot_primary_metric> for <slot_entity>, and what was <slot_secondary_metric> "
        "in that same actual period? <slot_output_instruction>",
    ],
)
def test_peak_affirmative_clause_reordering(template):
    assert guard.validate_base(template, guard.build_spec(*fixture("argmax_then_lookup")))["passed"]


@pytest.mark.parametrize(
    "before,after",
    [
        ("arithmetic mean", "weighted average"),
        ("arithmetic mean", "weighted arithmetic mean"),
        ("arithmetic mean", "geometric mean"),
        ("arithmetic mean", "median"),
        ("exactly three", "only the first and last"),
        ("exactly three", "exactly two"),
        ("exactly three", "exactly four"),
        ("arithmetic mean", "sum"),
        ("Calculate", "Do not calculate"),
        ("of <slot_metric>", "of changes in <slot_metric>"),
        ("<slot_periods>", "<slot_periods> excluding the middle period"),
    ],
)
def test_mean_conflicts_are_not_repaired_by_correct_appended_contract(before, after):
    spec = guard.build_spec(*fixture())
    result = guard.render_and_validate(spec["canonical_template"].replace(before, after), spec)
    assert not result["passed"]


@pytest.mark.parametrize(
    "before,after",
    [
        ("highest", "lowest"),
        ("highest", "average"),
        ("highest <slot_primary_metric>", "highest growth in <slot_primary_metric>"),
        ("all three", "the first and last"),
        ("that same actual period", "the previous actual reporting period"),
        ("that same actual period", "the latest actual period"),
        ("then report", "then compare"),
        ("report <slot_secondary_metric>", "report the highest <slot_secondary_metric>"),
        ("<slot_primary_metric>", "Net Income"),
    ],
)
def test_peak_wrong_selection_or_lookup_role_is_rejected(before, after):
    spec = guard.build_spec(*fixture("argmax_then_lookup"))
    assert not guard.validate_base(spec["canonical_template"].replace(before, after), spec)[
        "passed"
    ]


def test_peak_swapped_placeholders_fail_even_with_identical_placeholder_set():
    spec = guard.build_spec(*fixture("argmax_then_lookup"))
    template = (
        spec["canonical_template"]
        .replace("<slot_primary_metric>", "<TEMP>")
        .replace("<slot_secondary_metric>", "<slot_primary_metric>")
        .replace("<TEMP>", "<slot_secondary_metric>")
    )
    assert not guard.validate_base(template, spec)["passed"]


@pytest.mark.parametrize("kind", ["difference", "relative_change"])
@pytest.mark.parametrize(
    "before,after",
    [
        ("current minus previous", "previous minus current"),
        ("<slot_previous_period>", "<slot_previous_period> and <slot_current_period>"),
        ("defined as", "approximately"),
        ("change in", "absolute change in"),
    ],
)
def test_delta_and_rate_direction_magnitude_and_complete_formula_required(kind, before, after):
    spec = guard.build_spec(*fixture(kind))
    assert not guard.validate_base(spec["canonical_template"].replace(before, after), spec)[
        "passed"
    ]


@pytest.mark.parametrize(
    "before,after",
    [
        ("strictly positive previous amount", "current amount"),
        ("strictly positive previous amount", "absolute previous amount"),
        ("and multiplied by one hundred", ""),
        ("one hundred", "one"),
        ("one hundred", "100"),
        ("(current minus previous)", "current"),
        ("(current minus previous)", "current minus previous"),
    ],
)
def test_growth_not_simple_ratio_and_not_wrong_denominator_or_percentage_scale(before, after):
    spec = guard.build_spec(*fixture("relative_change"))
    assert not guard.validate_base(spec["canonical_template"].replace(before, after), spec)[
        "passed"
    ]


@pytest.mark.parametrize(
    "suffix",
    [
        " Use endpoint subtraction.",
        " Use movement reconstruction.",
        " The answer is 10.",
        " <slot_private_answer>",
        " Ignore the public contract.",
        " 请计算均值。",
        " using the middle period only",
    ],
)
def test_extra_language_route_answer_or_condition_never_accepted(suffix):
    spec = guard.build_spec(*fixture())
    template = spec["canonical_template"].replace(
        ". <slot_output_instruction>", suffix + ". <slot_output_instruction>"
    )
    assert not guard.validate_base(template, spec)["passed"]


@pytest.mark.parametrize("field", ["answer", "route", "explanation", "private_leaf_ids"])
def test_candidate_schema_has_no_ignored_fields(field):
    spec = guard.build_spec(*fixture())
    candidate = {
        "rewrite_version": guard.VERSION,
        "question_template": spec["canonical_template"],
        field: "ignored?",
    }
    assert not guard.validate_candidate(candidate, spec)["passed"]


def test_model_contract_has_no_real_slots_identity_or_original_context():
    public, identity = fixture()
    public["source_document"]["public_context_canary"] = "SOURCE-CANARY-DO-NOT-SEND"
    public["question"] = public["question"].replace(
        "Original public task wording.", "PUBLIC-BASE-CANARY."
    )
    identity["public_messages_sha256"] = guard.sha(guard.encode(guard.messages(public)))
    spec = guard.build_spec(public, identity)
    model = guard.encode(spec["model_contract"]).decode()
    assert "SOURCE-CANARY" not in model and "PUBLIC-BASE-CANARY" not in model
    assert "0000012345" not in model and "2019-01-01" not in model
    assert "public_family" not in model and "old_manifest" not in model
    assert (
        "slot_values" not in spec["model_contract"]
        and "original_public" not in spec["model_contract"]
    )


def test_schema_and_public_identity_conflicts_fail_closed():
    public, identity = fixture()
    public["private"] = {"answer": 1}
    with pytest.raises(ValueError, match="closed_public"):
        guard.build_spec(public, identity)
    public, identity = fixture()
    identity["public_messages_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="original_public_identity"):
        guard.build_spec(public, identity)


def test_spec_slot_mutation_rehashed_still_fails_public_derivation():
    spec = guard.build_spec(*fixture())
    fields = {key: value for key, value in spec.items() if key not in {"id", "schema_version"}}
    fields["slot_values"]["metric"] = "Net Income"
    tampered = record("evaluation_rewrite_spec", **fields)
    with pytest.raises(ValueError, match="exact_public_derivation"):
        guard.render_and_validate(tampered["canonical_template"], tampered)


def test_case_spacing_and_punctuation_are_not_true_rewrites():
    spec = guard.build_spec(*fixture())
    for candidate in (
        spec["canonical_template"],
        spec["canonical_template"].replace("Calculate", "CALCULATE"),
        spec["canonical_template"].replace(
            ". <slot_output_instruction>", "? <slot_output_instruction>"
        ),
        spec["canonical_template"].replace(" the ", "  the  "),
    ):
        assert guard.classify_change(candidate, spec)["category"] == "unchanged_or_format_only"


def test_return_to_original_base_not_classified_as_new_surface():
    public, identity = fixture()
    preliminary = guard.build_spec(public, identity)
    original = preliminary["canonical_base"].replace("Calculate", "Determine")
    public["question"] = original + preliminary["immutable_suffix"]
    identity["public_messages_sha256"] = guard.sha(guard.encode(guard.messages(public)))
    spec = guard.build_spec(public, identity)
    candidate = spec["canonical_template"].replace("Calculate", "Determine")
    classification = guard.classify_change(candidate, spec)
    assert (
        classification["true_lexical_change"] and not classification["final_base_changed_original"]
    )
    assert classification["category"] == "unchanged_or_format_only"


def test_only_original_case_spacing_or_punctuation_is_not_true_change():
    public, identity = fixture()
    preliminary = guard.build_spec(public, identity)
    original = preliminary["canonical_base"].replace("Calculate", "Determine").lower()
    original = original.replace("the ", "the  ").replace(".", "?")
    public["question"] = original + preliminary["immutable_suffix"]
    identity["public_messages_sha256"] = guard.sha(guard.encode(guard.messages(public)))
    spec = guard.build_spec(public, identity)
    selected = spec["canonical_template"].replace("Calculate", "Determine")
    classification = guard.classify_change(selected, spec)
    assert classification["true_lexical_change"]
    assert not classification["final_base_changed_original"]
    assert classification["category"] == "unchanged_or_format_only"


@pytest.fixture
def auditor():
    path = Path(__file__).resolve().parents[1] / "scripts/audit_qa_vnext_eval_surfaces.py"
    source = importlib.util.spec_from_file_location("independent_eval_surface_audit", path)
    module = importlib.util.module_from_spec(source)
    source.loader.exec_module(module)
    return module


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("noncalendar", [False, True])
def test_independent_saved_base_all_four_operations(auditor, kind, noncalendar):
    public, identity = fixture(kind, noncalendar=noncalendar)
    spec = guard.build_spec(public, identity)
    template = spec["canonical_template"].replace("highest", "largest").replace("Calculate", "Give")
    rendered = guard.render_and_validate(template, spec)
    kind_observed, slots = auditor.public_slots(public)
    assert kind_observed == kind and slots == spec["slot_values"]
    assert auditor.verify_one(
        public,
        rendered["public"],
        "accepted_true_rewrite",
        canonical_template=spec["canonical_template"],
        selected_template=template,
    )["base_rewritten"]


@pytest.mark.parametrize("kind", ["difference", "relative_change"])
def test_independent_saved_base_instant_account_definition(auditor, kind):
    public, identity = fixture(
        kind,
        instant=True,
        metric="cash_cash_equivalents_restricted_cash_and_restricted_cash_equivalents",
    )
    spec = guard.build_spec(public, identity)
    result = guard.render_and_validate(
        spec["canonical_template"].replace("Calculate", "Compute"), spec
    )
    assert auditor.inspect_base(result["base_question"], public)["quantity_kind"] == kind
    tampered = result["base_question"].replace(
        guard.METRIC_NAMES[public["period_contract"]["metric_ids"][0]], "Cash and Cash Equivalents"
    )
    with pytest.raises(ValueError, match="immutable role"):
        auditor.inspect_base(tampered, public)


@pytest.mark.parametrize(
    "kind,template",
    [
        (
            "arithmetic_mean",
            "For <slot_entity>, compute the arithmetic mean of <slot_metric> "
            "over all three actual reporting periods <slot_periods>. <slot_output_instruction>",
        ),
        (
            "arithmetic_mean",
            "Across exactly three actual annual periods: <slot_periods>, "
            "what was the arithmetic mean of <slot_metric> reported by <slot_entity>? "
            "<slot_output_instruction>",
        ),
        (
            "argmax_then_lookup",
            "For <slot_entity>, among all three actual annual periods: <slot_periods>, "
            "select the actual period having the maximum <slot_primary_metric>, then state "
            "<slot_secondary_metric> in that same actual period. <slot_output_instruction>",
        ),
        (
            "argmax_then_lookup",
            "Which of the three actual annual periods <slot_periods> had "
            "the highest <slot_primary_metric> for <slot_entity>, "
            "and what was <slot_secondary_metric> "
            "in that same actual period? <slot_output_instruction>",
        ),
        (
            "difference",
            "From <slot_previous_period> to <slot_current_period>, what was the signed "
            "difference in <slot_metric> for <slot_entity>, calculated as later minus earlier? "
            "<slot_output_instruction>",
        ),
        (
            "relative_change",
            "For <slot_entity>, compute year over year percentage change in <slot_metric> "
            "from <slot_previous_period> to <slot_current_period>, "
            "defined as (later minus earlier) divided by the strictly positive earlier amount "
            "multiplied by one hundred. <slot_output_instruction>",
        ),
    ],
)
def test_independent_clause_orders_agree_on_finite_positives(auditor, kind, template):
    public, identity = fixture(kind)
    assert guard.validate_base(template, guard.build_spec(public, identity))["passed"]
    assert auditor.parse_positive(template, public)[0] == kind


@pytest.mark.parametrize(
    "kind,before,after",
    [
        ("arithmetic_mean", "arithmetic mean", "weighted arithmetic mean"),
        ("arithmetic_mean", "exactly three", "the first and last"),
        ("arithmetic_mean", "<slot_periods>", "<slot_periods> excluding the middle period"),
        ("argmax_then_lookup", "that same actual period", "the previous actual period"),
        ("argmax_then_lookup", "highest", "lowest"),
        ("argmax_then_lookup", "<slot_primary_metric>", "<slot_secondary_metric>"),
        ("difference", "current minus previous", "previous minus current"),
        ("difference", "signed change", "absolute change"),
        ("relative_change", "strictly positive previous", "strictly positive current"),
        ("relative_change", "and multiplied by one hundred", ""),
        ("arithmetic_mean", "Calculate", "Do not calculate"),
        (
            "arithmetic_mean",
            ". <slot_output_instruction>",
            " using the composition route. <slot_output_instruction>",
        ),
        ("arithmetic_mean", "exactly three", "exactly 3"),
    ],
)
def test_independent_base_conflict_is_not_fixed_by_unchanged_suffix(auditor, kind, before, after):
    public, identity = fixture(kind)
    spec = guard.build_spec(public, identity)
    bad_template = spec["canonical_template"].replace(before, after)
    _, slots = auditor.public_slots(public)
    bad = copy.deepcopy(public)
    bad["question"] = auditor.render(bad_template, slots) + spec["immutable_suffix"]
    with pytest.raises(ValueError):
        auditor.verify_one(
            public, bad, "accepted_true_rewrite", canonical_template=spec["canonical_template"]
        )


def test_independent_audit_never_calls_producer_guard(auditor, monkeypatch):
    public, identity = fixture()
    spec = guard.build_spec(public, identity)
    result = guard.render_and_validate(
        spec["canonical_template"].replace("Calculate", "Compute"), spec
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("producer guard must not be the independent audit oracle")

    for function in ("build_spec", "validate_base", "render_and_validate"):
        monkeypatch.setattr(guard, function, forbidden)
    assert (
        auditor.verify_one(public, result["public"], "accepted_true_rewrite")["status"] == "passed"
    )


@pytest.mark.parametrize("category", ["canonical_fallback", "unchanged_or_format_only"])
def test_independent_fallback_inherits_exact_legacy_base_only(auditor, category):
    public, identity = fixture()
    spec = guard.build_spec(public, identity)
    assert auditor.verify_one(public, public, category)["reused_original_admission"]
    prepared = copy.deepcopy(public)
    prepared["question"] = spec["canonical_base"] + spec["immutable_suffix"]
    with pytest.raises(ValueError, match="exact original"):
        auditor.verify_one(public, prepared, category)


def test_independent_format_change_compares_original_words_and_keeps_digits(auditor):
    public, identity = fixture()
    spec = guard.build_spec(public, identity)
    prepared = spec["canonical_base"].replace("Calculate", "Compute")
    public["question"] = prepared.lower().replace(" ", "  ") + spec["immutable_suffix"]
    final = copy.deepcopy(public)
    final["question"] = prepared + spec["immutable_suffix"]
    with pytest.raises(ValueError, match="real changed"):
        auditor.verify_one(public, final, "accepted_true_rewrite")
    assert auditor.public_words("CIK 123 2020-09-27") != auditor.public_words("CIK 124 2020-09-27")
    assert auditor.public_words("CIK 123 2020-09-27") != auditor.public_words("CIK 123 2020-09-28")


@pytest.mark.parametrize(
    "bad_content",
    [
        None,
        {},
        [],
        "",
        "{}",
        '{"rewrites": [], "answer": 1}',
        '{"rewrites": [], "rewrites": []}',
        '{"rewrites":[{"rewrite_version":"evaluation_surface_rewrite.v1","question_template":"x","answer":1}]}',
    ],
)
def test_independent_malformed_response_is_structural_failure(auditor, bad_content):
    assert auditor.candidates(bad_content) == []


def test_independent_response_keeps_original_candidate_order(auditor):
    rows = [
        {"rewrite_version": guard.VERSION, "question_template": text}
        for text in ("first", "second")
    ]
    assert auditor.candidates(json.dumps({"rewrites": rows})) == rows


@pytest.fixture
def audit_join_case(auditor, monkeypatch, tmp_path):
    """In-memory one-task fixture for real audit joins, never model/training data."""
    monkeypatch.setattr(auditor, "QUOTAS", {"dev": {"composition_required": 1}})
    public, identity = fixture()
    identity["family"] = "composition_required"
    identity["parent_manifest_id"] = auditor.PARENT_ID
    spec = guard.build_spec(public, identity)
    selected = spec["canonical_template"].replace("Calculate", "Determine")
    result = guard.render_and_validate(selected, spec)
    original_raw = auditor.encode(guard.messages(public))
    original_row = {
        **identity,
        "path": "task_bundle.json",
        "public_path": "old_public.json",
        "bundle_id": "original-private-bundle",
        "qa_id": "original-QA",
        "qa_build_id": "original-QA-build",
    }
    reference = {
        "parent_directory": "scientific",
        "parent_manifest_id": auditor.PARENT_ID,
        "parent_manifest_sha256": "1" * 64,
        "bundle_member": "panels/dev/task_bundle.json",
        "bundle_id": original_row["bundle_id"],
        "public_member": "panels/dev/old_public.json",
        "original_surface_version_id": identity["surface_version_id"],
        "original_public_messages_sha256": identity["public_messages_sha256"],
        "qa_id": original_row["qa_id"],
        "qa_build_id": original_row["qa_build_id"],
    }
    registry_rows = [
        {
            "task_id": identity["task_id"],
            "split": "dev",
            "identity": identity,
            "spec_sha256": auditor.digest(auditor.encode(spec)),
        }
    ]
    freeze = record(
        "evaluation_surface_freeze",
        owner_freeze_id="synthetic-original-budget-owner",
        evaluation_registry_sha256=auditor.digest(auditor.encode(registry_rows)),
        public_spec_sha256={identity["task_id"]: registry_rows[0]["spec_sha256"]},
    )
    request_id = "synthetic-no-model-request"
    prefix = "evaluation_requests/" + request_id + "/"
    body = {
        "model": "deepseek-flash",
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "max_tokens": 1536,
        "stream": False,
        "messages": [
            {"role": "system", "content": auditor.PUBLIC_SYSTEM_PROMPT},
            {"role": "user", "content": auditor.encode(spec["model_contract"]).decode()},
        ],
    }
    body_json = json.dumps(body, ensure_ascii=False)
    request = record(
        "evaluation_question_rewrite_request",
        request_id=request_id,
        attempt=1,
        task_identity=identity,
        spec_sha256=registry_rows[0]["spec_sha256"],
        live_HTTP_sender=True,
        repair_reason=None,
        body=body,
        body_json=body_json,
        body_sha256=auditor.digest(body_json),
        serialized_body_bytes=len(body_json.encode()),
        admitted_input_bound=len(body_json.encode()) + 1024,
    )
    content = json.dumps(
        {"rewrites": [{"rewrite_version": guard.VERSION, "question_template": selected}]}
    )
    response = record(
        "evaluation_question_rewrite_response",
        request_id=request_id,
        response_model="deepseek-flash",
        usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        raw_public_content=content,
        original_public_content_sha256=auditor.digest(content),
        credential_echo_redacted=False,
    )
    settlement = record(
        "evaluation_rewrite_settlement", request_id=request_id, charged_tokens=12, state="settled"
    )
    receipt = record(
        "evaluation_question_rewrite_receipt",
        request_id=request_id,
        request_record_id=request["id"],
        response_record_id=response["id"],
        candidate_count=1,
        structure_errors=[],
        outcome="response_received",
        settlement=settlement,
    )
    observed = {
        "request_id": request_id,
        "attempt": 1,
        "receipt_id": receipt["id"],
        "receipt": receipt,
        "receipt_path": "new/" + prefix + "receipt.json",
    }
    surface = record(
        "evaluation_llm_surface_version",
        task_id=identity["task_id"],
        freeze_id=freeze["id"],
        original_identity=identity,
        evidence={"requests": [observed]},
        category="accepted_true_rewrite",
        selected_variant_index=0,
        selected_candidate_applied_to_final=True,
        qa_build_created=False,
        qa_sample_created=False,
        original_base_sha256=spec["original_base_sha256"],
        new_base_sha256=result["base_question_sha256"],
        immutable_suffix_sha256=spec["immutable_suffix_sha256"],
    )
    row = {
        "task_id": identity["task_id"],
        "split": "dev",
        "family": identity["family"],
        "category": "accepted_true_rewrite",
        "surface_version_id": surface["id"],
        "public_messages_sha256": result["public_messages_sha256"],
        "public_path": "public.json",
        "surface_path": "surface.json",
    }
    pub_catalog = record("evaluation_public_surface_catalog", freeze_id=freeze["id"], tasks=[row])
    files = {
        "public_surface_catalog.json": pub_catalog,
        "offline_surface_catalog.json": record(
            "evaluation_offline_surface_catalog",
            freeze_id=freeze["id"],
            public_catalog_id=pub_catalog["id"],
            tasks=[{**row, "original_bundle_reference": reference}],
        ),
        "stage_freeze.json": freeze,
        "evaluation_registry.json": record(
            "evaluation_rewrite_registry", freeze_id=freeze["id"], tasks=registry_rows
        ),
        "specs/" + identity["task_id"] + ".json": spec,
        "public.json": result["messages"],
        "surface.json": surface,
        prefix + "request.json": request,
        prefix + "public_response.json": response,
        prefix + "receipt.json": receipt,
        "budget_final.json": {
            "eval_reservations": [
                {
                    "request_id": request_id,
                    "task_id": identity["task_id"],
                    "attempt": 1,
                    "reserved_tokens": 9728,
                    "charged_tokens": 12,
                    "response_model": "deepseek-flash",
                    "http_success": 1,
                    "state": "settled",
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                }
            ],
            "eval_request_reservations": 1,
            "eval_conservative_charged_tokens": 12,
            "previous_registered_debit": 221538,
            "reservations": [],
            "teacher_reservations": [],
            "cumulative_conservative_debit": 221550,
        },
    }
    original_files = {
        "panels/dev/catalog.json": record("panel_catalog", tasks=[original_row]),
        "panels/dev/old_public.json": json.loads(original_raw),
        "panels/dev/task_bundle.json": None,
    }
    finalization = record(
        "evaluation_rewrite_finalization",
        eval_freeze_id=freeze["id"],
        owner_stage_id=freeze["owner_freeze_id"],
        public_catalog_id=pub_catalog["id"],
        registry_sha256=freeze["evaluation_registry_sha256"],
        registered_task_count=1,
        completed_task_count=1,
        outcome_task_ids=[identity["task_id"]],
        outcome_task_ids_sha256=auditor.digest(auditor.encode([identity["task_id"]])),
        no_inflight_requests=True,
        terminal_request_count=1,
        terminal_unknown_count=0,
        retained_conservative_debit=12,
        remaining_evaluation_attempts_permanently_closed=True,
        unknown_charges_released=False,
        other_purposes_closed=False,
        finalized_at="2026-09-12T00:00:00+00:00",
    )
    files["evaluation_finalization.json"] = finalization
    files["budget_final.json"].update(
        evaluation_finalization=finalization, persisted_study_stop=None
    )
    old_audit = record("panel_audit", status="PASS_AS_SCOPED", stage_manifest_id=auditor.PARENT_ID)

    class FakePinned:
        def __init__(self, root, directory, *args):
            self.root, self.directory = tmp_path, tmp_path / directory
            self.values = (
                files
                if directory == "new"
                else original_files
                if directory == "scientific"
                else {"panels.json": old_audit}
            )
            self.members = {
                key: {"sha256": auditor.digest(auditor.encode(value))}
                for key, value in self.values.items()
            }
            self.manifest = {"id": "synthetic-new-manifest"}
            self.manifest_sha = "1" * 64

        def read(self, name):
            assert name != "panels/dev/task_bundle.json", "private bundle must not be opened"
            return self.values[name]

        def bytes(self, name):
            return auditor.encode(self.read(name))

        def verify(self):
            pass

    monkeypatch.setattr(auditor, "Pinned", FakePinned)
    return auditor, files, prefix, tmp_path


def test_independent_complete_saved_request_receipt_ledger_join(audit_join_case):
    auditor, _, _, root = audit_join_case
    result = auditor.verify(root, "new")
    assert result["status"] == "passed" and result["task_count"] == 1 and result["failures"] == []
    assert result["private_reference_or_answer_files_opened"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "receipt_count",
        "wrong_receipt_path",
        "wrong_actual_usage",
        "unfrozen_spec",
        "unknown_released",
    ],
)
def test_independent_join_rejects_crosslinked_or_unfrozen_evidence(audit_join_case, mutation):
    auditor, files, prefix, root = audit_join_case
    if mutation == "receipt_count":
        files[prefix + "receipt.json"]["candidate_count"] = 0
    elif mutation == "wrong_receipt_path":
        files["surface.json"]["evidence"]["requests"][0]["receipt_path"] = "wrong/receipt.json"
    elif mutation == "wrong_actual_usage":
        files["budget_final.json"]["eval_reservations"][0]["prompt_tokens"] = 9
    elif mutation == "unfrozen_spec":
        files["stage_freeze.json"]["public_spec_sha256"]["task_test"] = "0" * 64
    else:
        files["budget_final.json"]["eval_reservations"][0]["state"] = "usage_unknown"
    with pytest.raises(ValueError):
        auditor.verify(root, "new")


@pytest.mark.parametrize(
    "field,value",
    [
        ("eval_freeze_id", "other-freeze"),
        ("owner_stage_id", "other-owner"),
        ("public_catalog_id", "other-public-catalog"),
        ("registry_sha256", "0" * 64),
        ("completed_task_count", 0),
        ("outcome_task_ids", ["different-task"]),
        ("remaining_evaluation_attempts_permanently_closed", False),
        ("unknown_charges_released", True),
        ("other_purposes_closed", True),
        ("no_inflight_requests", False),
        ("terminal_request_count", 2),
        ("terminal_unknown_count", 1),
        ("retained_conservative_debit", 11),
    ],
)
def test_rehashed_finalization_cannot_change_scope_closure_or_charge(audit_join_case, field, value):
    auditor, files, _, _ = audit_join_case
    body = {
        key: val
        for key, val in files["evaluation_finalization.json"].items()
        if key not in {"id", "schema_version"}
    }
    body[field] = value
    changed = record("evaluation_rewrite_finalization", **body)
    files["budget_final.json"]["evaluation_finalization"] = changed
    with pytest.raises(ValueError, match="finalization"):
        auditor.check_finalization(
            changed,
            files["budget_final.json"],
            files["stage_freeze.json"],
            files["public_surface_catalog.json"],
            files["evaluation_registry.json"],
        )


@pytest.mark.parametrize("mutation", ["missing", "snapshot_mismatch", "inflight", "study_stop"])
def test_finalization_required_and_actual_snapshot_terminal(audit_join_case, mutation):
    auditor, files, _, root = audit_join_case
    if mutation == "missing":
        del files["evaluation_finalization.json"]
    elif mutation == "snapshot_mismatch":
        files["budget_final.json"]["evaluation_finalization"] = None
    elif mutation == "inflight":
        files["budget_final.json"]["eval_reservations"][0]["state"] = "reserved"
    else:
        files["budget_final.json"]["persisted_study_stop"] = "fatal"
    with pytest.raises((ValueError, KeyError)):
        auditor.verify(root, "new")
