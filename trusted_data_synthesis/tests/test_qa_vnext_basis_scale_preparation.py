"""Offline budget, original-source provenance and fail-closed census controls."""

from copy import deepcopy

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation import census
from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation.core import (
    Store,
    reference,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation.examples import (
    SPECS,
    reviewed_examples,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation.governance import (
    draft_company_split,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation.protocol import (
    TEACHER_TOKEN_CAP,
    TokenReservationControl,
    preparation_protocol,
    require_online_authority,
)


def source(number=1):
    return {
        "id": f"FIXTURE/2020/page_1.pdf-{number}",
        "filename": "FIXTURE/2020/page_1.pdf",
        "table_ori": [["dollars in millions", "2020"], ["amount", "12"]],
        "table": [["dollars in millions", "2020"], ["amount", "12"]],
        "pre_text": ["Fixture public disclosure."],
        "post_text": [],
        "qa": {
            "question": "Fixture question",
            "exe_ans": "PRIVATE_CANARY",
            "program": "PRIVATE_CANARY",
        },
        "source_split": "train",
        "source_file_sha256": "fixture_sha",
        "source_record_index": number,
    }


def test_amount_cap_is_frozen_but_never_execution_authority():
    plan = preparation_protocol()
    assert TEACHER_TOKEN_CAP == 1_000_000_000
    assert (
        plan["resource_stop"]["maximum_cumulative_Teacher_input_plus_output_tokens"]
        == TEACHER_TOKEN_CAP
    )
    assert not plan["support_generation_allowed"] and not plan["training_allowed"]
    assert not plan["full_collection_protocol_frozen"]
    with pytest.raises(ValueError, match="not_ready_STOP"):
        require_online_authority()


def test_concurrent_reservations_cannot_oversubscribe_budget():
    ledger = TokenReservationControl(100)
    ledger.reserve("a", 60)
    ledger.reserve("b", 40)
    with pytest.raises(ValueError, match="token_stop"):
        ledger.reserve("c", 1)
    ledger.finish("a", prompt_tokens=20, completion_tokens=10)
    ledger.reserve("c", 30)
    assert ledger.consumed + sum(ledger.reservations.values()) == 100


@pytest.mark.parametrize("usage", [{}, {"prompt_tokens": 0}, {"completion_tokens": 0}])
def test_failed_or_incomplete_usage_keeps_full_reservation(usage):
    ledger = TokenReservationControl(100)
    ledger.reserve("a", 100)
    ledger.finish("a", **usage)
    assert ledger.consumed == 100
    with pytest.raises(ValueError, match="token_stop"):
        ledger.reserve("b", 1)


@pytest.mark.parametrize("value", [True, 0, -1, 10.0, "10", None])
def test_budget_requires_positive_exact_integer_bound(value):
    ledger = TokenReservationControl(100)
    with pytest.raises(ValueError, match="positive_bound"):
        ledger.reserve("a", value)


def test_provider_overrun_keeps_actual_usage_and_permanently_stops_new_requests():
    ledger = TokenReservationControl(100)
    ledger.reserve("a", 30)
    with pytest.raises(ValueError, match="bound_violated_STOP"):
        ledger.finish("a", prompt_tokens=30, completion_tokens=1)
    assert ledger.consumed == 31 and "a" in ledger.closed
    with pytest.raises(ValueError, match="accounting_failed_STOP"):
        ledger.reserve("b", 1)


def test_attempt_ids_cannot_be_reused_after_failures():
    ledger = TokenReservationControl(100)
    ledger.reserve("a", 1)
    with pytest.raises(ValueError, match="unique_attempt"):
        ledger.reserve("a", 1)
    ledger.finish("a")
    with pytest.raises(ValueError, match="unique_attempt"):
        ledger.reserve("a", 1)


def test_source_question_repetition_does_not_expand_source_supply():
    a, b = source(), source(2)
    b["qa"]["question"] = "Paraphrase not an additional source"
    rows = [a, b]
    views = census.source_views(rows, draft_company_split(rows))
    assert len(views) == 1 and len(views[0]["original_question_ids"]) == 2
    assert "PRIVATE_CANARY" not in str(views)
    assert not views[0]["physical_task_identity_or_sufficient_relation_certified"]


def test_distinct_public_views_on_same_page_are_retained_not_overwritten():
    a, b = source(), source(2)
    b["pre_text"].append("Second source projection.")
    views = census.source_views([a, b], draft_company_split([a, b]))
    assert len(views) == 2 and len({row["draft_split"] for row in views}) == 1


def test_protected_table_exclusion_survives_new_original_question_id():
    a = source()
    old = deepcopy(a)
    old.update(id="OLD/2019/page_2.pdf-1", filename="OLD/2019/page_2.pdf")
    draft = draft_company_split([a], evaluation_rows=[old])
    views = census.source_views([a], draft)
    assert views[0]["training_source_excluded"]
    assert not views[0]["physical_task_identity_or_sufficient_relation_certified"]


def test_source_screen_summary_zero_is_not_no_possible_relation():
    rows = [source()]
    summary = census.summarize_views(census.source_views(rows, draft_company_split(rows)))
    assert sum(item["source_views"] for item in summary.values()) == 1
    assert all(item["certified_distinct_tasks"] == 0 for item in summary.values())
    assert all(
        item["no_lead_is_not_proof_of_absent_sufficient_relation"] for item in summary.values()
    )


def test_store_does_not_overwrite_or_mutate_after_seal(tmp_path):
    directory = tmp_path / "phase"
    store = Store(directory)
    store.json("record.json", {"source": "original"})
    with pytest.raises(FileExistsError):
        store.json("record.json", {"source": "replacement"})
    store.seal()
    with pytest.raises(ValueError, match="sealed"):
        store.json("later.json", {})
    with pytest.raises(ValueError, match="new_phase_only"):
        Store(directory)


def test_references_reject_parent_absolute_and_symlink_traversal(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "source.txt"
    outside.write_text("original")
    for relative in ("../source.txt", str(outside)):
        with pytest.raises(ValueError, match="relative_path"):
            reference(root, relative)
    (root / "escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="inside_root"):
        reference(root, "escape/source.txt")


def example_rows():
    rows = []
    assignments = []
    for spec in SPECS:
        table = [["millions", *spec["years"]]]
        amounts = dict(
            zip([spec["metric_row"], *spec["components"]], spec["expected_values"], strict=True)
        )
        table.extend([["fixture label", *amounts[index]] for index in range(1, len(amounts) + 1)])
        pre_text = ["fixture context"] * 13
        pre_text[spec["definition_pointer"][1]] = spec["definition"]
        row = {
            "id": spec["original_id"],
            "source_split": "train",
            "source_record_index": spec["index"],
            "source_file_sha256": "fixture_original",
            "pre_text": pre_text,
            "table_ori": table,
        }
        rows.append(row)
        assignments.append({"entry_id": row["id"], "draft_split": "confirm"})
    return rows, {"rows": assignments}


def test_reviewed_examples_keep_different_definitions_and_do_not_certify_tasks():
    rows, draft = example_rows()
    result = reviewed_examples(rows, draft)
    assert [r["endpoint_difference"] for r in result["examples"]] == ["224", "960", "-91"]
    assert result["actual_new_certified_tasks"] == 0
    assert all(
        not r["contributes_to_training_dev_or_confirm_task_quota"] for r in result["examples"]
    )
    assert all(r["draft_split"] == "confirm" for r in result["examples"])
    assert len(result["examples"][2]["signed_component_differences"]) == 3


@pytest.mark.parametrize("change", ["definition", "value", "year", "index"])
def test_reviewed_relation_record_is_not_created_from_changed_source(change):
    rows, draft = example_rows()
    if change == "definition":
        rows[0]["pre_text"][0] = "Replacement definition"
    elif change == "value":
        rows[0]["table_ori"][1][1] = "1759"
    elif change == "year":
        rows[0]["table_ori"][0][1] = "2013"
    else:
        rows[0]["source_record_index"] = 310
    with pytest.raises(ValueError, match="examples"):
        reviewed_examples(rows, draft)
