"""CPU-only B role/frequency/schedule controls; no original task contents."""

import copy
import importlib
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
m = importlib.import_module("fixed_kernel_B_materials_20260922")
p = m.p


def support():
    groups = {
        f"task_{family}_{i}": family
        for family, count in p.TASK_COUNTS.items()
        for i in range(count)
    }
    states, extra = [], 5
    for task, family in groups.items():
        count = 1 if family == "control" else 13 + int(extra > 0)
        if family != "control" and extra:
            extra -= 1
        states.extend(
            (
                task,
                f"{task}_state_{j}",
                "control" if family == "control" else ("endpoint" if j % 2 else "movement"),
            )
            for j in range(count)
        )
    assert len(states) == 1645
    headers = []
    for i in range(3529):
        task, state, method = states[i % len(states)]
        headers.append(
            dict(
                package_id=f"package_{i}",
                task_id=task,
                state_id=state,
                method=method,
                session_id=f"session_{i}",
                pool="B",
                role="train",
                family=groups[task],
                rows=1,
                sequence_tokens=17811694 // 3529 + int(i < 17811694 % 3529),
                whole_package_target_tokens=982088 // 3529 + int(i < 982088 % 3529),
                original_package_sha256=f"synthetic_package_digest_{i}",
            )
        )
    prior, counts, methods = m.original.prior_from_headers(headers)
    budget = {
        key + suffix: value * factor
        for key, value in m.B_PER_EPOCH.items()
        for suffix, factor in (("_per_epoch", 1), ("_all_epochs", 10))
    }
    fields = (
        "package_id",
        "task_id",
        "state_id",
        "method",
        "session_id",
        "whole_package_target_tokens",
        "original_package_sha256",
    )
    mappings = []
    for row in headers:
        task, state, method = row["task_id"], row["state_id"], row["method"]
        mappings.append(
            {key: row[key] for key in fields}
            | dict(
                pi0=prior[task][state],
                n_state=counts[task, state],
                n_method=methods[task, method],
                original_alpha0_coefficient=str(
                    m.original.target_coefficient(
                        prior[task][state], counts[task, state], row["whole_package_target_tokens"]
                    )
                ),
            )
        )
    binding = dict(
        pool="B",
        prior=prior,
        mu=dict.fromkeys(groups, "1/200"),
        states=1645,
        training_packages=3529,
        control_tasks=sorted(t for t in groups if groups[t] == "control"),
        package_mappings=mappings,
        input_cache_budget=budget,
        package_order_sha256=p.sha(p.encode([r["package_id"] for r in headers])),
        all_original_packages_retained=True,
        sealed_packages_reclassified=False,
        changed_mapper=False,
    )
    return binding, dict(pool="B", packages=headers, actual_budget=budget), groups


def schedules(groups):
    families = {
        family: sorted(t for t, f in groups.items() if f == family) for family in p.TASK_COUNTS
    }
    batches = [
        dict(
            epoch=step // 40,
            step=step,
            task_ids=[
                families[family][step % 40] for family in p.TASK_COUNTS if family != "control"
            ]
            + families["control"][2 * (step % 40) : 2 * (step % 40) + 2],
        )
        for step in range(400)
    ]
    return {
        str(seed): p.record(
            "batch_schedule",
            seed=seed,
            epochs=10,
            total_updates=400,
            updates_per_epoch=40,
            batches=batches,
        )
        for seed in m.SEEDS
    }


def test_B_prior_uses_unequal_local_frequencies_and_exact_budget():
    binding, index, groups = support()
    assert m._validate_B_support(binding, index, groups) == binding["input_cache_budget"]
    assert set(Counter((r["task_id"], r["state_id"]) for r in index["packages"]).values()) == {2, 3}
    m._validate_schedules(schedules(groups), groups)


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("pool", "A", "unique_original_B_train_packages"),
        ("role", "sealed", "unique_original_B_train_packages"),
        ("task_id", "foreign_task", "original200_task_roster"),
    ],
)
def test_rejects_A_sealed_or_foreign_task_header(field, value, code):
    binding, index, groups = support()
    index["packages"][0][field] = value
    with pytest.raises(ValueError, match=code):
        m._validate_B_support(binding, index, groups)


def test_rejects_prior_copied_from_other_material_frequencies():
    binding, index, groups = support()
    task = next(task for task in binding["prior"] if len(binding["prior"][task]) > 1)
    one, two = list(binding["prior"][task])[:2]
    binding["prior"][task][one], binding["prior"][task][two] = "1/3", "1/3"
    with pytest.raises(ValueError, match="prior_from_B_frequencies_only"):
        m._validate_B_support(binding, index, groups)


def test_rejects_misaligned_schedule_and_B_numeric_path_escape(tmp_path):
    _, _, groups = support()
    records = schedules(groups)
    body = {
        k: copy.deepcopy(v) for k, v in records["11"].items() if k not in {"id", "schema_version"}
    }
    body["batches"][200]["task_ids"][0] = "foreign_task"
    records["11"] = p.record("batch_schedule", **body)
    with pytest.raises(ValueError, match="fixed_five_task_update"):
        m._validate_schedules(records, groups)
    with pytest.raises(ValueError, match="relative_path"):
        m._path(tmp_path, "../private.json")
