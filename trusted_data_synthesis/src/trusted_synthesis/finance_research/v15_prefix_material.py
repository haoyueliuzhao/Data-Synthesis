"""A genuine state-free all-package prior-prefix binding, not a five-arm pool.

This consumes the completed V14 authority/encoding cache without re-tokenizing
or changing masks. No state, chi, prior or pi is invented for unresolved tasks.
The fixed mapping adjudication contract must precede any Student execution.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .contracts import digest
from .storage import snapshot_manifest
from .v6_collection import bound, persist, require, sha
from .v9_conditional_training import build_task_schedule, execution_plan
from .v13_material_registration import checked, entry, read_ref
from .v14_encoding_cache import load_cache

STUDY = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01"
)
SOURCE = STUDY / "v14_representation_01"
OUTPUT = STUDY / "v15_prefix_completion_01"
BINDING_SCHEMA = "v15_prior_prefix_binding.v1"
SOURCES = (
    "v15_prefix_material.py",
    "v14_encoding_cache.py",
    "v14_student_encoding.py",
    "v9_conditional_training.py",
    "v6_task.py",
    "contracts.py",
)


def source_bindings():
    return {name: sha(Path(__file__).parent / name) for name in SOURCES}


def material_order_identity(task_ids, packages, encodings):
    """All original rows are bound even when zero targets skip actual forward."""
    return digest(
        dict(
            task_ids=list(task_ids),
            packages=list(packages),
            row_sha256_by_package={
                p["package_id"]: [r["row_sha256"] for r in encodings[p["package_id"]]["rows"]]
                for p in packages
            },
        )
    )


class PrefixPool:
    """Dedicated no-state consumer for 1/(actual_B*n_x*L_P), never arbitrary pi."""

    def __init__(
        self,
        *,
        task_ids,
        packages,
        encodings,
        binding_ref,
        token_binding,
        material_order_id,
        production=True,
    ):
        self.task_ids, self._packages = tuple(task_ids), tuple(packages)
        require(len(set(self.task_ids)) == len(self.task_ids), "unique complete tasks required")
        require(
            all(
                set(p) == {"package_id", "task_id", "whole_package_target_tokens", "fused"}
                and p["fused"] is False
                for p in self._packages
            ),
            "prefix packages contain no fabricated state or altered fused target",
        )
        require(
            set(encodings) == {p["package_id"] for p in self._packages},
            "all original rows required",
        )
        require(set(p["task_id"] for p in self._packages) == set(self.task_ids), "no removed task")
        require(
            material_order_identity(self.task_ids, self._packages, encodings) == material_order_id,
            "canonical package/row execution order changed",
        )
        self._encodings = encodings
        self.cache_id = binding_ref["id"]
        self.prefix_binding_ref = binding_ref
        self.tokenizer_binding = tuple(token_binding)
        self.material_order_id = material_order_id
        self.production_verified = production
        self.prefix_only, self.prefix_scope_verified = True, production
        self.conditional_scope_verified = self.full_training_admitted = False
        self.execution_plan = execution_plan(len(self.task_ids))
        self.dataset = "finqa"
        self.package_count_by_task = dict(Counter(p["task_id"] for p in self._packages))

    @property
    def packages(self):
        return self._packages

    def row_arrays(self, package_id):
        return tuple(r for r in self._encodings[package_id]["rows"] if r["target_ids"])


def _source_material(source):
    """Inherited fixed qualifications and complete immutable cache, not mapping admission."""
    source = Path(source).resolve()
    source_plan = checked(source / "registration/record.json")
    definition = read_ref(source_plan["definition"])
    prior_support = checked(source / "material/support/record.json")
    prior_result = checked(source / "material/result/record.json")
    seal = checked(source / "completion_seal/record.json")
    require(
        definition["schema"] == "v14_fixed_residual_definition.v1"
        and source_plan["protocol_identity"] == definition["id"]
        and seal["registration_id"] == prior_result["registration_id"] == source_plan["id"]
        and seal["all_registered_jobs_have_authentic_terminals"] is True
        and prior_support["N"] == 744
        and prior_support["package_count"] == 2468,
        "complete frozen V14 source and unchanged full common material required",
    )
    task_slots, task_ids = definition["fixed_task_slots"], prior_support["training_task_ids"]
    require(task_ids == list(task_slots), "same canonical future full-pool task order required")
    cache = load_cache(source / "encoding_cache", require_complete=True)
    require(
        len(cache["encodings"]) == 2468
        and set(cache["encodings"]) == set(definition["candidate_slot_ids"])
        and cache["registration"]["population_id"] == definition["parent_fixed_population_id"]
        and cache["registration"]["fixed_task_slots"] == task_slots
        and cache["pending_slot_ids"] == cache["failed_encoding_slot_ids"] == [],
        "full 2468/744 already-authoritative masks and encodings, never resolved690 only",
    )
    parent = read_ref(definition["source_v13_definition"])
    require(definition["pairs"] == parent["pairs"], "original qualification roster changed")
    for pair in parent["pairs"]:
        core = read_ref(pair["pair"])
        require(
            core["joint_process_candidate"] is True
            and core["slot_id"] == pair["slot_id"]
            and core["task_id"] == pair["task_id"]
            and cache["authorities"][pair["slot_id"]]["original_episode"]
            == pair["original_episode"],
            "original process qualification or episode source changed",
        )
    packages = [
        dict(
            package_id=sid,
            task_id=task,
            whole_package_target_tokens=cache["encodings"][sid]["L_P"],
            fused=False,
        )
        for task in task_ids
        for sid in task_slots[task]
    ]
    original_plan = read_ref(parent["inputs"]["source_v10_plan"])
    snapshot = snapshot_manifest(original_plan["snapshot"])
    require(
        snapshot["id"] == original_plan["snapshot_id"], "unchanged original public inputs required"
    )
    return dict(
        source_plan=source_plan,
        definition=definition,
        support=prior_support,
        result=prior_result,
        seal=seal,
        cache=cache,
        task_ids=task_ids,
        packages=packages,
        original_plan=original_plan,
        snapshot=snapshot,
    )


def _mapping_gate(mapping_plan):
    """Require the prospective scope before Student; never consume Student outcomes."""
    from .v15_mapping_registration import checked_plan

    path = Path(mapping_plan).resolve()
    require(
        path.name == "record.json" and path.parent.name == "registration",
        "registered finite mapping plan required",
    )
    plan = checked_plan(path.parent.parent)
    require(plan.get("model") == "deepseek-flash", "mapping model unchanged")
    return plan


def prepare(output=OUTPUT, *, mapping_plan, source_v14=SOURCE):
    output, source = Path(output).resolve(), Path(source_v14).resolve()
    plan = _mapping_gate(mapping_plan)
    require(
        Path(plan["source_root"]).resolve() == source,
        "prefix and adjudication must share the same completed V14 source",
    )
    require(0 <= plan["expected_requests"] <= 54, "one finite adjudication matrix only")
    material = _source_material(source)
    cache, packages, tasks = material["cache"], material["packages"], material["task_ids"]
    layers = cache["full_population_layer_target_counts"]
    total_targets = sum(p["whole_package_target_tokens"] for p in packages)
    require(
        total_targets == sum(layers.values()) == 504276,
        "same complete already-frozen target set and whole-package loss lengths required",
    )
    all_rows = [r for p in packages for r in cache["encodings"][p["package_id"]]["rows"]]
    forward_rows = [r for r in all_rows if r["target_ids"]]
    schedule_refs = {}
    for seed in (11, 29, 47):
        schedule = bound(build_task_schedule(tasks, seed))
        persist(output / "prefix_material/schedules" / f"seed{seed}", schedule)
        schedule_refs[str(seed)] = entry(
            output / "prefix_material/schedules" / f"seed{seed}/record.json"
        )
    binding = bound(
        dict(
            schema=BINDING_SCHEMA,
            material_root=str(output / "prefix_material"),
            source_root=str(source),
            mapping_plan=entry(mapping_plan),
            mapping_plan_id=plan["id"],
            source_v14_plan=entry(source / "registration/record.json"),
            source_v14_definition=entry(source / "definition/record.json"),
            source_v14_completion_seal=entry(source / "completion_seal/record.json"),
            source_v14_support=entry(source / "material/support/record.json"),
            source_v14_blocked_result=entry(source / "material/result/record.json"),
            source_qualification=material["definition"]["source_v13_definition"],
            encoding_cache_registration=entry(source / "encoding_cache/registration/record.json"),
            encoding_cache_run=cache["run_ref"],
            supervision_manifests=cache["manifest_entries"],
            encodings=cache["encoding_entries"],
            task_ids=tasks,
            packages=packages,
            fixed_tasks=744,
            fixed_packages=2468,
            tokenizer_binding=list(cache["tokenizer_binding"]),
            original_student_assets=cache["registration"]["original_student_assets"],
            material_order_id=material_order_identity(tasks, packages, cache["encodings"]),
            execution_plan=execution_plan(744),
            schedules=schedule_refs,
            seeds=[11, 29, 47],
            prefix_steps_per_seed=298,
            physical_prefix_updates=894,
            loss_coefficient="1/(actual_B_j*n_x*L_P)",
            empirical_frequency_prior_cancellation=True,
            no_states_or_chi_created=True,
            no_arbitrary_pi_accepted=True,
            first_step_is_formal_first_update=True,
            hard_stop_before_step298_outer=True,
            mapping_does_not_consume_student_results=True,
            supervision_layers=layers,
            unique_supervised_tokens=total_targets,
            per_seed_target_token_presentations=2 * total_targets,
            total_prefix_target_token_presentations=6 * total_targets,
            per_seed_package_presentations=2 * len(packages),
            total_prefix_package_presentations=6 * len(packages),
            all_original_rows_per_epoch=len(all_rows),
            forward_rows_per_epoch=len(forward_rows),
            full_cache_sequence_tokens_per_epoch=sum(len(r["input_ids"]) for r in all_rows),
            actual_forward_sequence_tokens_per_epoch=sum(len(r["input_ids"]) for r in forward_rows),
            maximum_sequence_tokens=max(len(r["input_ids"]) for r in all_rows),
            source_snapshot_sha256=digest(material["snapshot"]),
            prefix_only_admitted=True,
            full_five_arm_admitted=False,
            feedback_calls_authorized=0,
            dev_calls_authorized=0,
            API_calls=0,
            GPU_used=False,
            source_bindings=source_bindings(),
        )
    )
    persist(output / "prefix_material/binding", binding)
    return binding


def load_prefix_pool(binding_path):
    path = Path(binding_path).resolve()
    binding = checked(path)
    require(
        binding["schema"] == BINDING_SCHEMA
        and binding["prefix_only_admitted"] is True
        and binding["full_five_arm_admitted"] is False
        and path == Path(binding["material_root"]) / "binding/record.json"
        and binding["source_bindings"] == source_bindings(),
        "registered prefix-only source required",
    )
    plan = _mapping_gate(binding["mapping_plan"]["path"])
    require(
        entry(binding["mapping_plan"]["path"]) == binding["mapping_plan"]
        and plan["id"] == binding["mapping_plan_id"],
        "mapping policy changed after prefix registration",
    )
    for key in (
        "source_v14_plan",
        "source_v14_definition",
        "source_v14_completion_seal",
        "source_v14_support",
        "source_v14_blocked_result",
        "source_qualification",
        "encoding_cache_registration",
        "encoding_cache_run",
        "original_student_assets",
    ):
        read_ref(binding[key])
    material = _source_material(binding["source_root"])
    cache = material["cache"]
    require(
        binding["task_ids"] == material["task_ids"]
        and binding["packages"] == material["packages"]
        and binding["encodings"] == cache["encoding_entries"]
        and binding["supervision_manifests"] == cache["manifest_entries"]
        and tuple(binding["tokenizer_binding"]) == cache["tokenizer_binding"]
        and binding["execution_plan"] == execution_plan(744)
        and binding["prefix_steps_per_seed"] == 298,
        "all original package targets, authority, order and prefix dose must remain unchanged",
    )
    for seed in (11, 29, 47):
        require(
            read_ref(binding["schedules"][str(seed)])
            == bound(build_task_schedule(material["task_ids"], seed)),
            "original task schedule differs",
        )
    pool = PrefixPool(
        task_ids=material["task_ids"],
        packages=material["packages"],
        encodings=cache["encodings"],
        binding_ref=entry(path),
        token_binding=cache["tokenizer_binding"],
        material_order_id=binding["material_order_id"],
    )
    pool.supervision_manifest_refs = cache["manifest_entries"]
    pool.encoding_refs = cache["encoding_entries"]
    pool.original_student_assets = binding["original_student_assets"]
    pool.source_snapshot_sha256 = binding["source_snapshot_sha256"]
    pool.public_input_parent_id = material["original_plan"]["original"]["id"]
    return pool


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--mapping-plan", type=Path, required=True)
    parser.add_argument("--source-v14", type=Path, default=SOURCE)
    args = parser.parse_args()
    result = prepare(args.output, mapping_plan=args.mapping_plan, source_v14=args.source_v14)
    print(
        dict(id=result["id"], prefix_only_admitted=True, full_five_arm_admitted=False, API_calls=0)
    )


if __name__ == "__main__":
    main()
