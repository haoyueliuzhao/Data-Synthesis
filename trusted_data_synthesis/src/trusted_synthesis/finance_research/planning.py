"""Assign original task roles before collection; never select by model outcome."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .contracts import Lineage, PublicTask, digest


def task_key(task: PublicTask) -> str:
    return f"{task.dataset}/{task.task_id}"


def validate_roles(
    tasks: list[PublicTask],
    lineages: list[Lineage],
    assignments: dict[str, str],
    *,
    separate_tatqa_training: bool = False,
) -> dict[str, Any]:
    from .catalog import validate_dataset_role

    if len(tasks) != len(lineages) or set(assignments) != {task_key(task) for task in tasks}:
        raise ValueError("role plan must cover each original task exactly once")
    exact: dict[str, list[tuple[str, str]]] = defaultdict(list)
    sources: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    parents: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for task, lineage in zip(tasks, lineages, strict=True):
        key, role = task_key(task), assignments[task_key(task)]
        if task.dataset != lineage.dataset or task.task_id != lineage.original_id:
            raise ValueError("lineage and public task identities differ")
        validate_dataset_role(
            task.dataset, lineage.original_split, role, separate_training=separate_tatqa_training
        )
        if role == "reserve":
            continue
        exact[digest([lineage.context_fingerprint, lineage.question_fingerprint])].append(
            (key, role)
        )
        sources[f"{task.dataset}/{lineage.source_group}"].append(
            (key, role, lineage.original_split)
        )
        for parent in {f"{task.dataset}:{lineage.original_id}", *lineage.parent_ids}:
            parents[parent].append((key, role))
    conflicts = []
    training_datasets = {
        task.dataset
        for task in tasks
        if assignments[task_key(task)] in {"sft", "feedback", "calibration"}
    }
    if len(training_datasets) > 1:
        conflicts.append(
            dict(relation="mixed_training_datasets", datasets=sorted(training_datasets))
        )
    for relation, groups in (("same_original_QA", exact), ("parent_task", parents)):
        for identity, members in groups.items():
            if len({role for _, role in members}) > 1:
                conflicts.append(dict(relation=relation, identity=identity, members=members))
    official_source_overlaps = []
    learning_roles = {"sft", "feedback", "calibration"}
    for group, members in sources.items():
        learning = {role for _, role, _ in members if role in learning_roles}
        if len(learning) > 1:
            conflicts.append(
                dict(relation="training_source_group", identity=group, members=members)
            )
        if len({split for _, _, split in members}) > 1:
            official_source_overlaps.append(dict(source_group=group, members=members))
    return dict(
        passed=not conflicts,
        conflicts=conflicts,
        official_split_source_overlaps=official_source_overlaps,
        official_splits_preserved=True,
        report_disjoint_test_claimed=False,
        cross_dataset_independence_confirmed=False,
        pretraining_contamination_absence_claimed=False,
    )


def build_role_plan(
    tasks: list[PublicTask],
    lineages: list[Lineage],
    *,
    seed: int = 20260928,
    sft_tasks: int = 1000,
    feedback_tasks: int = 350,
    calibration_tasks: int = 120,
    separate_tatqa_training: bool = False,
) -> dict[str, Any]:
    if len(tasks) != len(lineages) or len({task_key(x) for x in tasks}) != len(tasks):
        raise ValueError("unique public tasks and corresponding lineage rows are required")
    targets = dict(calibration=calibration_tasks, sft=sft_tasks, feedback=feedback_tasks)
    if any(type(n) is not int or n < 0 for n in targets.values()):
        raise ValueError("role target counts must be nonnegative integers")
    assignments, groups = {}, defaultdict(list)
    for task, lineage in zip(tasks, lineages, strict=True):
        key = task_key(task)
        if lineage.original_split == "train":
            if task.dataset != "finqa" and not (
                task.dataset == "tatqa" and separate_tatqa_training
            ):
                raise ValueError("only the registered FinQA-first training path is enabled")
            groups[f"{task.dataset}/{lineage.source_group}"].append(key)
            assignments[key] = "reserve"
        elif lineage.original_split in {"dev", "validation"}:
            assignments[key] = "development"
        elif lineage.original_split in {"test", "public_test", "publictest", "test_gold"}:
            assignments[key] = "test"
        else:
            raise ValueError("unknown official split; do not infer training permission")
    ordered = sorted(groups, key=lambda group: digest([seed, group]))
    selected = set()
    for role, limit in targets.items():
        count = 0
        for group in ordered:
            if group in selected or count + len(groups[group]) > limit:
                continue
            for key in groups[group]:
                assignments[key] = role
            selected.add(group)
            count += len(groups[group])
    audit = validate_roles(
        tasks, lineages, assignments, separate_tatqa_training=separate_tatqa_training
    )
    if not audit["passed"]:
        raise ValueError(f"role contamination: {audit['conflicts'][:3]}")
    value = dict(
        schema="finance_research_role_plan.v1",
        seed=seed,
        selection_basis="seeded source-group hashes, never model success or reference values",
        requested_training_counts=targets,
        actual_counts=dict(Counter(assignments.values())),
        assignments=assignments,
        task_order=[task_key(task) for task in tasks],
        public_sha256=digest([task.model_dump(mode="json") for task in tasks]),
        lineage_sha256=digest([row.model_dump(mode="json") for row in lineages]),
        source_groups_are_never_split=True,
        strict_exact_requested_counts_claimed=False,
        separate_tatqa_training=separate_tatqa_training,
        audit=audit,
        expensive_experiment_authorized=False,
    )
    return {**value, "id": digest(value)}


def verify_role_plan(plan, tasks, lineages):
    if plan.get("id") != digest({k: v for k, v in plan.items() if k != "id"}):
        raise ValueError("role plan bytes/identity mismatch")
    if plan["public_sha256"] != digest([task.model_dump(mode="json") for task in tasks]) or (
        plan["lineage_sha256"] != digest([row.model_dump(mode="json") for row in lineages])
    ):
        raise ValueError("role plan belongs to a different snapshot")
    audit = validate_roles(
        tasks,
        lineages,
        plan["assignments"],
        separate_tatqa_training=plan["separate_tatqa_training"],
    )
    if not audit["passed"]:
        raise ValueError("role plan has a cross-role contamination conflict")
    return audit
