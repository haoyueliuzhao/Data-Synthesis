"""Prospective metadata-only population and immutable candidate registration.

The source catalog is the original 255 scientific tasks, not a Probe success
table. Source-cluster round-robin is performed independently within each family;
quantity labels are retained but never used as additional selection quotas.
"""

import random
from collections import Counter, defaultdict, deque

from . import protocol as p

FAMILY_COUNTS = {
    "annual_flow": 40,
    "stock_rollforward": 40,
    "company_defined_metric": 40,
    "control": 80,
}
POOLS = ("A", "B")
METHODS = ("endpoint", "movement")
TASK_COUNT = 200
SESSION_COUNT = 10_240
TRAIN_REPLICATES = 12
CELL_REPLICATES = 16
METADATA_FIELDS = (
    "task_id",
    "family",
    "quantity",
    "source_cluster",
    "bundle_id",
    "bundle_path",
    "public_path",
    "public_messages_sha256",
    "surface_version_id",
    "parent_manifest_id",
    "parent_directory",
    "native_bindings_path",
    "scale_group",
)


def _checked(value, kind):
    expected = p.record(
        kind, **{k: v for k, v in value.items() if k not in {"id", "schema_version"}}
    )
    p.require(value == expected, "population.content_identity:" + kind)


def metadata_rows(catalog):
    p.require(
        isinstance(catalog, dict) and isinstance(catalog.get("tasks"), list), "population.catalog"
    )
    rows = catalog["tasks"]
    p.require(len(rows) == 255, "population.original_255_required")
    p.require(len({r["task_id"] for r in rows}) == 255, "population.unique_catalog_tasks")
    result = []
    for row in rows:
        p.require(
            all(isinstance(row.get(k), str) and row[k] for k in METADATA_FIELDS),
            "population.scientific_metadata",
        )
        p.require(row["family"] in FAMILY_COUNTS, "population.known_family")
        result.append({key: row[key] for key in METADATA_FIELDS})
    return sorted(result, key=lambda row: row["task_id"])


def select_tasks(catalog):
    """Select 40/40/40/80 without observing candidate or Student outcomes."""
    rows = metadata_rows(catalog)
    selected = []
    for family, count in FAMILY_COUNTS.items():
        by_cluster = defaultdict(list)
        for row in rows:
            if row["family"] == family:
                by_cluster[row["source_cluster"]].append(row)
        queues = [deque(by_cluster[cluster]) for cluster in sorted(by_cluster)]
        chosen = []
        while len(chosen) < count and any(queues):
            for queue in queues:
                if queue and len(chosen) < count:
                    chosen.append(queue.popleft())
        p.require(len(chosen) == count, "population.insufficient_family_metadata:" + family)
        selected.extend(chosen)
    p.require(
        len(selected) == len({r["task_id"] for r in selected}) == TASK_COUNT, "population.fixed_200"
    )
    return selected


def selection_policy():
    return {
        "catalog_tasks": 255,
        "family_counts": FAMILY_COUNTS,
        "source_cluster_order": "ascending Unicode string order within family",
        "within_source_cluster_order": "ascending TaskID Unicode string order",
        "selection": "one task per nonempty source cluster in repeated rounds until family quota",
        "quantity_quota": False,
        "Probe_outcomes_used": False,
        "Student_outputs_or_scores_used": False,
        "outcome_based_replacement": False,
        "task_mu": {"numerator": 1, "denominator": TASK_COUNT},
    }


def make_population(catalog):
    tasks = select_tasks(catalog)
    return p.record(
        "population",
        source_catalog_id=catalog.get("id"),
        source_metadata_sha256=p.sha(p.encode(metadata_rows(catalog))),
        policy=selection_policy(),
        tasks=tasks,
        family_counts=dict(Counter(row["family"] for row in tasks)),
        source_cluster_counts={
            family: len({r["source_cluster"] for r in tasks if r["family"] == family})
            for family in FAMILY_COUNTS
        },
    )


def validate_population(population):
    _checked(population, "population")
    p.require(population["policy"] == selection_policy(), "population.frozen_policy")
    tasks = population["tasks"]
    p.require(
        len(tasks) == len({r["task_id"] for r in tasks}) == TASK_COUNT, "population.fixed_200"
    )
    p.require(
        Counter(r["family"] for r in tasks) == FAMILY_COUNTS == population["family_counts"],
        "population.fixed_family_counts",
    )
    p.require(all(set(r) == set(METADATA_FIELDS) for r in tasks), "population.metadata_only_rows")
    return tasks


def make_registry(population, freeze_id, order_seed):
    """Assign roles and shuffle a full 10,240 registry before any output exists."""
    tasks = validate_population(population)
    p.require(isinstance(freeze_id, str) and freeze_id, "population.freeze_identity")
    p.require(type(order_seed) is int, "population.explicit_precommitted_order_seed")
    sessions = []
    for pool in POOLS:
        for task in tasks:
            bases = ("neutral",) if task["family"] == "control" else METHODS
            for basis in bases:
                for replicate in range(CELL_REPLICATES):
                    session_id = "kernel_material_session_" + p.sha(
                        p.encode(
                            [freeze_id, population["id"], pool, task["task_id"], basis, replicate]
                        )
                    )
                    profile = p.CONTROL_PROFILE if basis == "neutral" else p.TARGET_PROFILE
                    sessions.append(
                        dict(
                            session_id=session_id,
                            freeze_id=freeze_id,
                            population_id=population["id"],
                            pool=pool,
                            task_id=task["task_id"],
                            family=task["family"],
                            quantity=task["quantity"],
                            profile=profile,
                            basis=basis,
                            system_prompt_sha256=p.sha(p.system_prompt(profile, basis)),
                            replicate=replicate,
                            role="train" if replicate < TRAIN_REPLICATES else "sealed",
                            identity={
                                key: task[key]
                                for key in (
                                    "task_id",
                                    "family",
                                    "surface_version_id",
                                    "public_messages_sha256",
                                    "parent_manifest_id",
                                )
                            },
                        )
                    )
    random.Random(order_seed).shuffle(sessions)
    sessions = [
        p.record("session_registration", ordinal=ordinal, **row)
        for ordinal, row in enumerate(sessions)
    ]
    p.require(
        len(sessions) == len({s["session_id"] for s in sessions}) == SESSION_COUNT,
        "population.full_10240_registry",
    )
    return p.record(
        "material_registry",
        freeze_id=freeze_id,
        population_id=population["id"],
        order_seed=order_seed,
        role_policy="replicate 0..11 train; 12..15 sealed, assigned before collection",
        sessions=sessions,
        session_count=SESSION_COUNT,
        per_pool_train_candidates=3840,
        per_pool_sealed_candidates=1280,
        training_role_reassignment=False,
    )


def validate_registry(registry, population):
    _checked(registry, "material_registry")
    expected = make_registry(population, registry["freeze_id"], registry["order_seed"])
    p.require(registry == expected, "population.exact_prospective_registry_roles_and_order")
    return registry["sessions"]


def batch_schedule(population, seed):
    """Ten epochs, 40 updates each; every task has exactly one visit per epoch."""
    tasks = validate_population(population)
    p.require(type(seed) is int, "population.explicit_training_order_seed")
    batches = []
    rng = random.Random(seed)
    for epoch in range(10):
        groups = {
            family: [r["task_id"] for r in tasks if r["family"] == family]
            for family in FAMILY_COUNTS
        }
        for family in FAMILY_COUNTS:
            rng.shuffle(groups[family])
        for step in range(40):
            task_ids = [
                groups[family][step] for family in FAMILY_COUNTS if family != "control"
            ] + groups["control"][2 * step : 2 * step + 2]
            batches.append({"epoch": epoch, "step": epoch * 40 + step, "task_ids": task_ids})
    return p.record(
        "batch_schedule",
        population_id=population["id"],
        seed=seed,
        epochs=10,
        updates_per_epoch=40,
        total_updates=400,
        batches=batches,
    )
