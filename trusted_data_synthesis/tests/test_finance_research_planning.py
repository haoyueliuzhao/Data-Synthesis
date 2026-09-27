"""Task/source role isolation checks; no model outcome participates in selection."""

from __future__ import annotations

import copy

import pytest

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.datasets import adapt_finqa, adapt_tatqa
from trusted_synthesis.finance_research.planning import (
    build_role_plan,
    task_key,
    validate_roles,
    verify_role_plan,
)


def finqa_bundles(group_count=3, pages=2, *, split="train"):
    records = []
    for group in range(group_count):
        for page in range(pages):
            records.append(
                {
                    "id": f"PLANNING_{group}/2020/page_{page}.pdf-1",
                    "filename": f"PLANNING_{group}/2020/page_{page}.pdf",
                    "pre_text": [f"Report group {group}, page {page}."],
                    "post_text": [],
                    "table": [["Year", "Revenue"], ["2020", str(8 + group)]],
                    "qa": {
                        "question": f"What is revenue on page {page} for group {group}?",
                        "exe_ans": 8 + group,
                        "program": f"add({8 + group}, const_0)",
                    },
                }
            )
    return adapt_finqa(records, split=split, revision="synthetic-planning-v1")


def public_and_lineage(bundles):
    return [bundle.public for bundle in bundles], [bundle.lineage for bundle in bundles]


def test_source_groups_are_role_disjoint_and_selection_is_deterministic():
    tasks, lineages = public_and_lineage(finqa_bundles())
    plan = build_role_plan(tasks, lineages, sft_tasks=2, feedback_tasks=2, calibration_tasks=2)
    assert plan == build_role_plan(
        tasks, lineages, sft_tasks=2, feedback_tasks=2, calibration_tasks=2
    )
    assert plan["actual_counts"] == {"calibration": 2, "sft": 2, "feedback": 2}
    by_source = {}
    for task, lineage in zip(tasks, lineages, strict=True):
        by_source.setdefault(lineage.source_group, set()).add(plan["assignments"][task_key(task)])
    assert all(len(roles) == 1 for roles in by_source.values())
    assert verify_role_plan(plan, tasks, lineages)["passed"]
    assert not plan["strict_exact_requested_counts_claimed"]
    assert not plan["expensive_experiment_authorized"]


def test_source_group_is_never_split_to_fill_an_exact_target():
    tasks, lineages = public_and_lineage(finqa_bundles(group_count=1, pages=2))
    plan = build_role_plan(tasks, lineages, sft_tasks=1, feedback_tasks=1, calibration_tasks=1)
    assert set(plan["assignments"].values()) == {"reserve"}


def test_same_source_or_parent_task_cannot_span_learning_roles():
    tasks, lineages = public_and_lineage(finqa_bundles(group_count=1))
    assignments = {task_key(tasks[0]): "sft", task_key(tasks[1]): "feedback"}
    audit = validate_roles(tasks, lineages, assignments)
    assert not audit["passed"]
    assert any(row["relation"] == "training_source_group" for row in audit["conflicts"])
    tasks, lineages = public_and_lineage(finqa_bundles(group_count=2, pages=1))
    lineages = [
        row.model_copy(update={"parent_ids": ("shared-ancestral-task",)}) for row in lineages
    ]
    audit = validate_roles(
        tasks, lineages, {task_key(tasks[0]): "sft", task_key(tasks[1]): "calibration"}
    )
    assert any(row["relation"] == "parent_task" for row in audit["conflicts"])


def test_official_source_overlap_is_disclosed_not_falsely_report_disjoint():
    train = finqa_bundles(group_count=1, pages=1)[0]
    test = train.model_copy(
        update={
            "public": train.public.model_copy(
                update={"task_id": "test-other-question", "question": "Different question"}
            ),
            "lineage": train.lineage.model_copy(
                update={
                    "original_split": "test",
                    "original_id": "test-other-question",
                    "question_fingerprint": digest("different question"),
                }
            ),
        }
    )
    tasks, lineages = public_and_lineage([train, test])
    plan = build_role_plan(tasks, lineages, calibration_tasks=1, sft_tasks=0, feedback_tasks=0)
    assert plan["assignments"][task_key(test.public)] == "test"
    assert plan["audit"]["official_split_source_overlaps"]
    assert plan["audit"]["report_disjoint_test_claimed"] is False
    assert plan["audit"]["cross_dataset_independence_confirmed"] is False


@pytest.mark.parametrize(
    "dataset,split",
    [
        ("finqa", "test"),
        ("financemath", "test"),
        ("financemath", "validation"),
        ("openenv290", "test"),
    ],
)
def test_heldout_or_eval_only_tasks_cannot_be_feedback(dataset, split):
    bundle = finqa_bundles(group_count=1, pages=1)[0]
    task = bundle.public.model_copy(update={"dataset": dataset})
    lineage = bundle.lineage.model_copy(update={"dataset": dataset, "original_split": split})
    with pytest.raises(ValueError, match="forbidden"):
        validate_roles([task], [lineage], {task_key(task): "feedback"})


def tatqa_train_bundle():
    return adapt_tatqa(
        [
            {
                "table": {"uid": "synthetic-tatqa-context", "table": [["Country"], ["China"]]},
                "paragraphs": [{"uid": "paragraph", "text": "A separate TAT-QA context."}],
                "questions": [
                    {
                        "uid": "synthetic-tatqa-q",
                        "question": "What country?",
                        "answer_type": "span",
                        "answer": "China",
                        "scale": "",
                    }
                ],
            }
        ],
        split="train",
        revision="synthetic-planning-v1",
    )[0]


def test_tatqa_training_needs_separate_protocol_and_cannot_mix_with_finqa_training():
    tatqa = tatqa_train_bundle()
    tasks, lineages = public_and_lineage([tatqa])
    with pytest.raises(ValueError):
        build_role_plan(tasks, lineages, calibration_tasks=0, sft_tasks=1, feedback_tasks=0)
    separate = build_role_plan(
        tasks,
        lineages,
        calibration_tasks=0,
        sft_tasks=1,
        feedback_tasks=0,
        separate_tatqa_training=True,
    )
    assert separate["assignments"][task_key(tatqa.public)] == "sft"
    mixed = public_and_lineage([finqa_bundles(group_count=1, pages=1)[0], tatqa])
    with pytest.raises(ValueError, match="mix|separate|dataset"):
        build_role_plan(
            *mixed, calibration_tasks=0, sft_tasks=2, feedback_tasks=0, separate_tatqa_training=True
        )


def test_role_plan_hash_public_source_and_lineage_tampering_are_rejected():
    tasks, lineages = public_and_lineage(finqa_bundles(group_count=1, pages=1))
    plan = build_role_plan(tasks, lineages, calibration_tasks=1, sft_tasks=0, feedback_tasks=0)
    changed_plan = copy.deepcopy(plan)
    changed_plan["assignments"][task_key(tasks[0])] = "sft"
    with pytest.raises(ValueError, match="identity"):
        verify_role_plan(changed_plan, tasks, lineages)
    with pytest.raises(ValueError, match="different snapshot"):
        verify_role_plan(
            plan, [tasks[0].model_copy(update={"question": "tampered source task"})], lineages
        )
    with pytest.raises(ValueError, match="different snapshot"):
        verify_role_plan(
            plan, tasks, [lineages[0].model_copy(update={"source_group": "changed-source"})]
        )


def test_original_task_and_lineage_identity_cannot_be_swapped():
    tasks, lineages = public_and_lineage(finqa_bundles(group_count=2, pages=1))
    with pytest.raises(ValueError, match="identity|original|lineage"):
        build_role_plan(
            tasks, list(reversed(lineages)), calibration_tasks=1, sft_tasks=1, feedback_tasks=0
        )


def test_plan_does_not_accept_duplicate_tasks_or_missing_assignments():
    tasks, lineages = public_and_lineage(finqa_bundles(group_count=1, pages=1))
    with pytest.raises(ValueError, match="unique"):
        build_role_plan(tasks * 2, lineages * 2)
    with pytest.raises(ValueError, match="exactly once"):
        validate_roles(tasks, lineages, {})
