"""Read-only B metadata admission for the newly authorized paired experiment.

This module does not acquire training authority from any historical A/B record.
It neither opens original/sealed packages, numeric arrays, task bodies or private
labels nor loads a tokenizer/model. Workers authenticate numeric arrays once via
trajectory_materials.load_pool when a separate new plan authorizes execution.
"""

import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

import fixed_kernel_anchored_sources_state_20260916 as original

p = original.p
BASE = original.OUTPUT
PARENT = original.PARENT
GIVEN = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/given_sources_value_20260915"
SEEDS = (11, 29, 47)
B_COUNTS = dict(tasks=200, controls=80, packages=3529, states=1645)
B_PER_EPOCH = dict(packages=3529, rows=3529, sequence_tokens=17811694, target_tokens=982088)


def _path(root, relative):
    relative = Path(relative)
    p.require(
        not relative.is_absolute() and ".." not in relative.parts, "B_materials.relative_path"
    )
    value = (root / relative).resolve()
    p.require(value.is_relative_to(root), "B_materials.path_within_root")
    return value


def _bound_json(root, reference):
    raw = _path(root, reference["path"]).read_bytes()
    p.require(
        len(raw) == reference["bytes"] and p.sha(raw) == reference["sha256"],
        "B_materials.bound_metadata_bytes",
    )
    return json.loads(raw)


def _validate_B_support(binding, index, groups):
    """Check B's own frequencies and package order; never reclassify a state."""
    headers = index["packages"]
    p.require(binding["pool"] == index["pool"] == "B", "B_materials.B_pool_only")
    p.require(
        len(headers) == len({row["package_id"] for row in headers}) == B_COUNTS["packages"]
        and all(row["pool"] == "B" and row["role"] == "train" for row in headers),
        "B_materials.unique_original_B_train_packages",
    )
    tasks = {row["task_id"] for row in headers}
    p.require(
        len(tasks) == B_COUNTS["tasks"]
        and tasks == set(groups)
        and Counter(groups.values()) == p.TASK_COUNTS,
        "B_materials.original200_task_roster",
    )
    p.require(
        all(row["family"] == groups[row["task_id"]] for row in headers),
        "B_materials.original_task_family",
    )
    methods = {}
    for row in headers:
        methods.setdefault(row["task_id"], set()).add(row["method"])
    p.require(
        all(
            methods[task]
            == ({"control"} if groups[task] == "control" else {"endpoint", "movement"})
            for task in tasks
        ),
        "B_materials.original_method_support",
    )
    prior, counts, method_counts = original.prior_from_headers(headers)
    controls = sorted(task for task in tasks if groups[task] == "control")
    p.require(
        len(counts) == binding["states"] == B_COUNTS["states"]
        and binding["training_packages"] == B_COUNTS["packages"]
        and len(controls) == B_COUNTS["controls"]
        and binding["control_tasks"] == controls,
        "B_materials.exact_state_package_control_counts",
    )
    p.require(
        binding["prior"] == prior and binding["mu"] == dict.fromkeys(sorted(tasks), "1/200"),
        "B_materials.prior_from_B_frequencies_only",
    )
    mappings = binding["package_mappings"]
    p.require(
        len(mappings) == len(headers)
        and binding["package_order_sha256"] == p.sha(p.encode([r["package_id"] for r in headers])),
        "B_materials.original_package_order",
    )
    fields = (
        "package_id",
        "task_id",
        "state_id",
        "method",
        "session_id",
        "whole_package_target_tokens",
        "original_package_sha256",
    )
    for row, mapped in zip(headers, mappings, strict=True):
        task, state, method = row["task_id"], row["state_id"], row["method"]
        coefficient = original.target_coefficient(
            prior[task][state], counts[task, state], row["whole_package_target_tokens"]
        )
        p.require(
            all(mapped[key] == row[key] for key in fields)
            and mapped["pi0"] == prior[task][state]
            and mapped["n_state"] == counts[task, state]
            and mapped["n_method"] == method_counts[task, method]
            and Fraction(mapped["original_alpha0_coefficient"]) == coefficient,
            "B_materials.exact_B_package_mass_and_identity",
        )
    p.require(
        binding["all_original_packages_retained"] is True
        and binding["sealed_packages_reclassified"] is False
        and binding["changed_mapper"] is False,
        "B_materials.original_train_sealed_roles_and_mapper",
    )
    actual = {
        "packages": len(headers),
        "rows": sum(r["rows"] for r in headers),
        "sequence_tokens": sum(r["sequence_tokens"] for r in headers),
        "target_tokens": sum(r["whole_package_target_tokens"] for r in headers),
    }
    p.require(actual == B_PER_EPOCH, "B_materials.exact_effective_token_budget")
    budget = {
        key + suffix: factor * value
        for key, value in actual.items()
        for suffix, factor in (("_per_epoch", 1), ("_all_epochs", 10))
    }
    p.require(
        index["actual_budget"] == binding["input_cache_budget"] == budget,
        "B_materials.bound_ten_epoch_budget",
    )
    return budget


def _validate_schedules(schedules, groups):
    p.require(set(schedules) == {str(seed) for seed in SEEDS}, "B_materials.three_fixed_seeds")
    for seed in SEEDS:
        schedule = p.checked(schedules[str(seed)], "batch_schedule")
        batches = schedule["batches"]
        p.require(
            schedule["seed"] == seed
            and schedule["epochs"] == 10
            and schedule["total_updates"] == len(batches) == 400
            and schedule["updates_per_epoch"] == 40,
            "B_materials.fixed400_schedule",
        )
        for step, batch in enumerate(batches):
            task_ids = batch["task_ids"]
            p.require(
                batch["step"] == step
                and batch["epoch"] == step // 40
                and len(task_ids) == len(set(task_ids)) == 5
                and set(task_ids) <= set(groups),
                "B_materials.fixed_five_task_update",
            )
            p.require(
                Counter(groups[task] for task in task_ids)
                == dict(annual_flow=1, stock_rollforward=1, company_defined_metric=1, control=2),
                "B_materials.fixed_batch_families",
            )
        for epoch in range(10):
            visits = Counter(
                task
                for batch in batches[epoch * 40 : (epoch + 1) * 40]
                for task in batch["task_ids"]
            )
            p.require(
                visits == Counter(dict.fromkeys(groups, 1)), "B_materials.one_visit_per_epoch"
            )


def load_B_materials(root):
    """Return metadata for a new B plan; no historical run release is inherited."""
    root = Path(root).resolve()
    frozen = p.checked(
        p.read_json(root / PARENT / "preparation/execution_freeze.json"), "execution_freeze"
    )
    parent = p.checked(
        p.read_json(root / BASE / "registered_A/plan.json"), "anchored_registered_A_plan"
    )
    binding = p.checked(
        p.read_json(root / BASE / "material_binding/B.json"), "anchored_sources_material_binding"
    )
    reference = frozen["trajectory_cache"]
    manifest = _bound_json(root, reference["manifest"])
    p.checked(manifest, "trajectory_material_cache")
    p.require(
        manifest["id"] == reference["manifest_id"] == binding["cache_id"]
        and reference == parent["trajectory_cache"],
        "B_materials.original_cache_binding",
    )
    cache_root = _path(root, reference["cache_root"])
    selected = manifest["pools"]["B"]
    p.require(selected["package_index"]["path"] == "B/packages.json", "B_materials.B_index_path")
    index = _bound_json(cache_root, selected["package_index"])
    p.require(
        index["id"] == selected["package_index_id"] == binding["package_index_id"],
        "B_materials.original_index_identity",
    )
    groups = parent["training_groups"]
    budget = _validate_B_support(binding, index, groups)
    p.require(
        budget == manifest["pool_budgets"]["B"] == selected["actual_budget"]
        and index["source_material_budget"] == manifest["source_material_budgets"]["B"],
        "B_materials.cache_budget_binding",
    )
    # Presence/size only: load_pool does the numeric hashes once in each worker.
    for field in ("input_ids", "target_positions"):
        member = selected[field]
        p.require(member["path"] == "B/" + field + ".npy", "B_materials.B_numeric_path")
        p.require(
            _path(cache_root, member["path"]).stat().st_size == member["bytes"],
            "B_materials.numeric_file_present_with_expected_size",
        )
    assets = {key: frozen[key] for key in ("base_binding", "tokenizer_binding")}
    p.require(
        assets == parent["assets"]
        and frozen["training_configuration"] == parent["training_configuration"],
        "B_materials.unchanged_assets_and_training_configuration",
    )
    _validate_schedules(parent["schedules"], groups)
    p.require(
        set(parent["initial_adapter_digests"]) == {str(seed) for seed in SEEDS},
        "B_materials.paired_initialization_metadata",
    )
    public = p.checked(
        p.read_json(root / GIVEN / "inputs_v2/manifest.json"), "source_view_manifest_v2"
    )
    admission = p.checked(
        p.read_json(root / GIVEN / "inputs_v2/admission.json"), "source_view_input_admission_v2"
    )
    p.require(
        public["id"] == parent["source_manifest_id"] == admission["manifest_id"]
        and admission["passed"] is True
        and public["tasks"] == parent["tasks"]
        and admission["runtime_binding"] == parent["runtime_binding"],
        "B_materials.frozen_dev_public_runtime",
    )
    dev_tasks = {row["task_id"] for row in public["tasks"]}
    p.require(
        len(public["tasks"]) == len(dev_tasks) == 180
        and not dev_tasks & set(groups)
        and Counter(row["group"] for row in public["tasks"])
        == dict(composition_required=60, dual_sufficient=60, other_financial=60),
        "B_materials.disjoint_existing_dev180",
    )
    return dict(
        pool="B",
        binding=binding,
        binding_id=binding["id"],
        trajectory_cache=reference,
        actual_budget=budget,
        source_material_budget=index["source_material_budget"],
        assets=assets,
        training_configuration=frozen["training_configuration"],
        initial_adapter_digests=parent["initial_adapter_digests"],
        schedules=parent["schedules"],
        training_groups=groups,
        source_manifest_id=public["id"],
        tasks=public["tasks"],
        runtime_binding=parent["runtime_binding"],
        private_scoring_source_root=parent["private_scoring_source_root"],
        provenance=dict(
            parent_execution_freeze_id=frozen["id"],
            metadata_reference_A_plan_id=parent["id"],
            existing_B_binding_id=binding["id"],
        ),
        execution_authorized=False,
        execution_authority="new_B_plan_required; historical_records_are_material_metadata_only",
        numeric_arrays_read=0,
        original_or_sealed_packages_read=0,
        task_bodies_read=0,
        private_labels_read=0,
        new_materials_generated=0,
    )
