"""Direct boundary counterexamples, using synthetic records and temporary files only.

No acquisition, census writer, historical rescoring, tokenizer, model, GPU, or
git command is invoked. Imported census helpers operate only on supplied values.
"""

import copy
import hashlib
import json
from fractions import Fraction

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation import (
    census,
    core,
    design,
    governance,
    protocol,
    screen,
)

_DEFAULT = object()


def entry(company="A", table=_DEFAULT):
    return {
        "id": f"{company}/2020/page_1.pdf-1",
        "filename": f"{company}/2020/page_1.pdf",
        "table": [
            ["USD millions", "2020"],
            ["Balance at beginning of year", "100"],
            ["Additions charged to expense", "15"],
            ["Settlements", "(5)"],
            ["Balance at end of year", "110"],
        ]
        if table is _DEFAULT
        else copy.deepcopy(table),
        "pre_text": [f"{company} reports the following warranty reserve activity in USD millions."],
        "post_text": [],
        "qa": {"question": "What was the change in the warranty reserve?"},
    }


@pytest.mark.parametrize(
    "question",
    [
        {"text": "What changed?", "gold_answer": "PRIVATE_QUESTION_CANARY"},
        ["What changed?", {"gold_program": "PRIVATE_QUESTION_CANARY"}],
    ],
)
def test_nonstring_question_cannot_export_a_private_subobject(question):
    source = entry()
    source["qa"]["question"] = question
    result = screen.screen_public(source)
    assert "PRIVATE_QUESTION_CANARY" not in json.dumps(result)
    assert result["original_question_identity"]["original_question"] is None
    assert any(
        item["code"].startswith("MALFORMED_ORIGINAL_QUESTION")
        for item in result["source_scope_warnings"]
    )
    assert result["private_answer_or_program_used"] is False
    assert result["relation_certificate_created"] is result["task_created"] is False


def test_private_qa_fields_are_not_read_or_used_in_public_source_hashes():
    class PublicQuestionOnly(dict):
        def get(self, key, default=None):
            assert key == "question", "private QA field was accessed"
            return super().get(key, default)

    source = entry()
    changed = copy.deepcopy(source)
    changed["qa"] = PublicQuestionOnly(
        question=source["qa"]["question"],
        answer="PRIVATE_QA_CANARY",
        program="PRIVATE_QA_CANARY",
        exe_ans="PRIVATE_QA_CANARY",
        gold_inds={"0": "PRIVATE_QA_CANARY"},
    )
    assert screen.screen_public(source) == screen.screen_public(changed)
    assert governance.annotated_governance([source], [], {}) == governance.annotated_governance(
        [changed], [], {}
    )


@pytest.mark.parametrize(
    "table",
    [
        [],
        [[]],
        [["", "  "]],
        [["—", "N/A"], ["-", "null"]],
        None,
        "not a table",
        [{"not": "a row"}],
        [[False]],
        [[float("nan")]],
    ],
)
def test_empty_placeholder_or_malformed_table_cannot_exclude_unrelated_training_source(table):
    first, second = entry("A", table), entry("B", table)
    report = governance.annotated_governance([first], [second], {})
    row = report["rows"][0]
    assert row["table_sha256"] is row["table_ori_sha256"] is None
    assert not row["training_source_excluded"]
    assert row["training_source_exclusion_reasons"] == []
    assert report["overlap"]["table"] == []
    assert row["source_identity_diagnostics"]
    assert all(
        item["used_for_source_equality"] is False for item in row["source_identity_diagnostics"]
    )
    assert row["task_certified"] is row["dual_sufficiency_certified"] is False
    assert report["support_generation_allowed"] is report["training_allowed"] is False
    assert governance._blacklist([second])["table_hashes"] == []
    draft = governance.draft_company_split([first, second])
    assert len(draft["components"]) == 2


def test_wholly_empty_sources_cannot_collide_through_the_context_hash_instead():
    first, second = entry("A", []), entry("B", [])
    for source in (first, second):
        source["pre_text"] = source["post_text"] = []
    report = governance.annotated_governance([first], [second], {})
    assert report["rows"][0]["context_sha256"] is None
    assert not report["rows"][0]["training_source_excluded"]
    assert report["overlap"]["table"] == report["overlap"]["context_sha256"] == []
    assert governance._blacklist([second])["context_hashes"] == []
    assert len(governance.draft_company_split([first, second])["components"]) == 2


def test_real_text_context_can_still_establish_overlap_when_table_is_empty():
    first, second = entry("A", []), entry("B", [])
    first["pre_text"] = second["pre_text"] = [
        "Revenue increased from USD 100 million in 2019 to USD 110 million in 2020."
    ]
    report = governance.annotated_governance([first], [second], {})
    reasons = report["rows"][0]["training_source_exclusion_reasons"]
    assert "evaluation_only_context" in reasons
    assert "evaluation_only_table" not in reasons
    assert len(governance.draft_company_split([first, second])["components"]) == 1


def test_original_informative_table_still_blocks_a_redownload_with_empty_cleaned_table():
    protected = entry("A")
    protected["table_ori"] = copy.deepcopy(protected["table"])
    downloaded = entry("B", [])
    downloaded["table_ori"] = copy.deepcopy(protected["table_ori"])
    report = governance.annotated_governance([downloaded], [protected], {})
    assert report["rows"][0]["table_sha256"] is None
    assert (
        report["rows"][0]["table_ori_sha256"] == governance._source(protected)["table_ori_sha256"]
    )
    assert "evaluation_only_table" in report["rows"][0]["training_source_exclusion_reasons"]
    assert len(governance.draft_company_split([downloaded, protected])["components"]) == 1


def test_zero_values_are_real_table_content_not_false_empty_placeholders():
    table = [["Revenue", 0], ["Expenses", "0"]]
    first, second = entry("A", table), entry("B", table)
    report = governance.annotated_governance([first], [second], {})
    assert report["rows"][0]["table_sha256"] is not None
    assert "evaluation_only_table" in report["rows"][0]["training_source_exclusion_reasons"]


def test_evaluation_only_usage_and_historical_freshness_are_distinct_restrictions():
    protected = entry("A")
    redownload = copy.deepcopy(protected)
    redownload["source_split"] = "new_official_train"
    result = governance.annotated_governance([redownload], [protected], {})
    assert result["rows"][0]["training_source_excluded"]
    assert result["rows"][0]["fresh_evaluation_source_excluded"] is False
    assert result["rows"][0]["task_certified"] is False
    known = {"exposure_layers": {"registered": governance._blacklist([protected])}}
    result = governance.annotated_governance([redownload], [], known)
    assert result["rows"][0]["training_source_excluded"] is False
    assert result["rows"][0]["fresh_evaluation_source_excluded"] is True
    assert result["support_generation_allowed"] is False


@pytest.mark.parametrize("absolute", [False, True])
def test_source_reference_cannot_escape_root_by_parent_or_absolute_path(tmp_path, absolute):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("synthetic outside source")
    path = outside if absolute else "../outside.txt"
    with pytest.raises(ValueError, match="reference."):
        core.reference(root, path)


def test_source_reference_rejects_parent_symlink_escape_but_accepts_internal_bytes(tmp_path):
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "source.txt").write_text("synthetic external source")
    (root / "bridge").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="reference."):
        core.reference(root, "bridge/source.txt")
    data = b"synthetic internal source"
    (root / "source.txt").write_bytes(data)
    assert core.reference(root, "source.txt") == {
        "path": "source.txt",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def test_source_census_cannot_turn_duplicate_questions_or_numeric_closure_into_task_certificates():
    first = entry()
    first.update(source_split="train", source_record_index=0, source_file_sha256="a" * 64)
    second = copy.deepcopy(first)
    second.update(id="A/2020/page_1.pdf-2", source_record_index=1)
    second["qa"].update(
        question="A second original question on the same source.",
        gold_inds={"0": "PRIVATE_CENSUS_CANARY"},
    )
    rows = [first, second]
    draft = governance.draft_company_split(rows)
    views = census.source_views(rows, draft)
    assert len(views) == 1
    assert len(views[0]["original_question_ids"]) == 2
    assert views[0]["screening"]["status"] == "SCREENED_LEAD"
    assert views[0]["physical_task_identity_or_sufficient_relation_certified"] is False
    assert views[0]["screening"]["relation_certificate_created"] is False
    assert "PRIVATE_CENSUS_CANARY" not in json.dumps(views)
    assert all(
        item["certified_distinct_tasks"] == 0 for item in census.summarize_views(views).values()
    )
    assert draft["support_generation_allowed"] is draft["training_allowed"] is False


def test_unsubstantiated_ready_names_and_positive_A_utilities_never_authorize_execution():
    ready = {
        group: [f"UNCERTIFIED:{group}:{index}" for index in range(72 if group == "control" else 36)]
        for group in design.GROUPS
    }
    selection = design.choose_population(ready)
    schedule = design.task_batches(selection, 11)
    assert selection["status"] == "PROSPECTIVE_POPULATION_SELECTED"
    assert selection["prospective_not_executed"] is True
    assert selection["training_allowed_by_this_preparation"] is False
    assert selection["independent_financial_task_identity_verified_here"] is False
    assert schedule["optimizer_or_trainer_constructed"] is False
    values = {
        arm: {seed: Fraction(3, 5) if arm == "plus" else Fraction(1, 2) for seed in design.SEEDS}
        for arm in design.ARMS
    }
    selected = design.select_direction(values)
    assert selected["planned_B_train_runs"] == 6
    assert selected["planned_B_development_sessions"] == 0
    assert selected["execution_authorized_by_this_record"] is False
    frozen = protocol.preparation_protocol()
    assert (
        frozen["resource_stop"]["maximum_cumulative_Teacher_input_plus_output_tokens"]
        == 1_000_000_000
    )
    assert frozen["resource_stop"]["current_phase_model_requests_authorized"] == 0
    assert frozen["full_collection_protocol_frozen"] is False
    assert frozen["support_generation_allowed"] is frozen["training_allowed"] is False
    with pytest.raises(ValueError, match="source_tasks_and_full_protocol_not_ready_STOP"):
        protocol.require_online_authority()


def test_offline_token_control_cannot_oversubscribe_or_refund_unknown_usage():
    ledger = protocol.TokenReservationControl(100)
    ledger.reserve("a", 90)
    with pytest.raises(ValueError, match="budget.token_stop"):
        ledger.reserve("b", 11)
    ledger.finish("a", prompt_tokens=50, completion_tokens=10)
    assert ledger.consumed == 60
    with pytest.raises(ValueError, match="budget.token_stop"):
        ledger.reserve("b", 41)
    ledger.reserve("b", 40)
    ledger.finish("b", prompt_tokens=None, completion_tokens=0)
    assert ledger.consumed == 100
    with pytest.raises(ValueError, match="budget.token_stop"):
        ledger.reserve("c", 1)
    with pytest.raises(ValueError, match="budget.unique_attempt"):
        ledger.reserve("a", 1)


def test_invalid_usage_keeps_reservation_and_bound_violation_permanently_stops_new_requests():
    ledger = protocol.TokenReservationControl(100)
    ledger.reserve("a", 10)
    with pytest.raises(ValueError, match="budget.valid_provider_usage"):
        ledger.finish("a", prompt_tokens=True, completion_tokens=0)
    assert ledger.reservations == {"a": 10} and ledger.consumed == 0
    with pytest.raises(ValueError, match="budget.reservation_bound_violated_STOP"):
        ledger.finish("a", prompt_tokens=8, completion_tokens=5)
    assert ledger.accounting_failed is True
    assert ledger.consumed == 13
    assert "a" in ledger.closed
    with pytest.raises(ValueError, match="budget.accounting_failed_STOP"):
        ledger.reserve("b", 1)
