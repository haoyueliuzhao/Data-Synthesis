"""Unequal-count fixed empirical kernels with exact, task-preserving mass.

Every fully certified, consumable train-role original is retained. Requested
basis is never a state label. Fine states remain distinct; only the endpoint /
movement marginal on common A/B support is intervened upon. No model is loaded.
"""

import copy
from collections import Counter, defaultdict
from fractions import Fraction

from . import protocol as p
from .population import METHODS, POOLS, TASK_COUNT, _checked, validate_population, validate_registry

ARMS = p.ARMS
ALPHA = {
    "alpha0": {"endpoint": Fraction(1, 2), "movement": Fraction(1, 2)},
    "plus": {"endpoint": Fraction(1, 3), "movement": Fraction(2, 3)},
    "minus": {"endpoint": Fraction(2, 3), "movement": Fraction(1, 3)},
}
MINIMUM_MASS_MOVEMENT = Fraction(1, 20)


def canonical_state_id(actual_method, full_class):
    """A complete actual class identity; no requested guidance enters the hash."""
    p.require(actual_method in {*METHODS, "control"}, "distribution.actual_state_method")
    p.require(full_class is not None, "distribution.complete_actual_class_required")
    return "fixed_kernel_state:" + p.sha(
        p.encode({"actual_method": actual_method, "full_class": full_class})
    )


def rational(value):
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def fraction(value):
    if isinstance(value, dict):
        p.require(set(value) == {"numerator", "denominator"}, "distribution.rational_fields")
        p.require(
            type(value["numerator"]) is int
            and type(value["denominator"]) is int
            and value["denominator"] > 0,
            "distribution.exact_rational",
        )
        return Fraction(value["numerator"], value["denominator"])
    p.require(
        isinstance(value, (Fraction, int, str)) and not isinstance(value, bool),
        "distribution.no_binary_float",
    )
    return Fraction(value)


def policy():
    return {
        "all_valid_train_originals_retained": True,
        "top_k_or_scoring": False,
        "fine_state_label": "actual certified complete class, never requested basis",
        "within_state_M": "uniform over every valid train original in that pool/task/state",
        "fine_state_pi_on_S": "alpha(method) * n_state / n_method",
        "static_kernel_outside_S": (
            "uniform over every valid train original for that pool/task; pi_state=n_state/n_task"
        ),
        "intervention_set_S": (
            "non-control tasks with both actual endpoint and movement train support in both pools"
        ),
        "single_method_tasks_retained": True,
        "task_mu": rational(Fraction(1, TASK_COUNT)),
        "batch_task_mass": rational(Fraction(1, 5)),
        "minimum_mass_movement": rational(MINIMUM_MASS_MOVEMENT),
        "threshold_is_power_guarantee": False,
        "arms": {
            arm: {method: rational(mass) for method, mass in values.items()}
            for arm, values in ALPHA.items()
        },
        "token_coefficient": "pi_state/(5*n_state*whole_package_target_tokens)",
        "package_count_per_update": (
            "all valid train originals for the five scheduled tasks, variable; never hard-coded 64"
        ),
        "abort_or_zero_task_support": "FAIL, no task replacement, no completed-prefix training",
    }


def _validate_package(package, outcome, registered):
    p.require(
        isinstance(package, dict) and isinstance(package.get("id"), str),
        "distribution.original_package_identity",
    )
    p.checked(package, "encoded_original_package")
    p.require(package.get("consumable") is True, "distribution.package_consumable")
    p.require(
        package.get("task_id") == registered["task_id"]
        and package.get("pool") == registered["pool"],
        "distribution.package_task_pool_binding",
    )
    p.require(
        package.get("registered_session_id") == registered["session_id"],
        "distribution.package_registered_session_binding",
    )
    p.require(
        package.get("actual_method") == outcome["actual_method"],
        "distribution.actual_method_binding",
    )
    p.require(
        outcome["state_id"]
        == canonical_state_id(package["actual_method"], package.get("full_class")),
        "distribution.canonical_complete_actual_class_binding",
    )
    if "state_id" in package:
        p.require(
            package["state_id"] == outcome["state_id"],
            "distribution.original_canonical_state_matches_outcome",
        )
    if "full_class" in outcome:
        p.require(
            outcome["full_class"] == package["full_class"],
            "distribution.outcome_full_class_matches_original",
        )
    rows = package.get("rows")
    p.require(isinstance(rows, list) and rows, "distribution.original_response_rows")
    length = 0
    for row in rows:
        representation = row["representation"]
        ids, mask, labels = (representation[key] for key in ("input_ids", "target_mask", "labels"))
        p.require(
            all(isinstance(value, list) for value in (ids, mask, labels)),
            "distribution.original_list_representation",
        )
        p.require(
            all(type(token) is int and token >= 0 for token in ids),
            "distribution.integer_input_token_ids",
        )
        p.require(
            type(representation["sequence_length"]) is int
            and type(representation["target_token_count"]) is int,
            "distribution.integer_token_counts",
        )
        p.require(
            len(ids) == len(mask) == len(labels) == representation["sequence_length"]
            and 1 < len(ids) <= 24576,
            "distribution.untruncated_sequence",
        )
        p.require(
            mask[0] == 0 and all(type(active) is int and active in {0, 1} for active in mask),
            "distribution.target_mask",
        )
        p.require(
            all(
                type(label) is int and label == (token if active else -100)
                for token, active, label in zip(ids, mask, labels, strict=True)
            ),
            "distribution.target_labels",
        )
        p.require(
            representation.get("attention_mask", [1] * len(ids)) == [1] * len(ids),
            "distribution.original_unpadded_attention",
        )
        p.require(
            representation.get("consumable_token_representation", True) is True
            and representation.get("truncation", False) is False,
            "distribution.no_truncation_or_representation_repair",
        )
        count = sum(mask[1:])
        p.require(
            count == representation["target_token_count"] and count > 0,
            "distribution.positive_causal_target_tokens",
        )
        length += count
    p.require(
        type(package.get("whole_package_target_tokens")) is int
        and package["whole_package_target_tokens"] == length,
        "distribution.whole_package_denominator",
    )
    return length


def build_kernel(population, registry, outcomes):
    """Close the full register and keep all valid train originals, without quotas.

    Outcomes are new ``material_outcome`` records. Required fields are
    session_id, registration_id, status (finished/budget_aborted/failed/not_run),
    financial_valid, full_class_valid, consumable, authentic_origin_verified.
    A valid outcome also supplies actual_method, state_id, original_package.
    Every registered session has an outcome, including budget-aborted rows.
    """
    tasks = validate_population(population)
    sessions = validate_registry(registry, population)
    p.require(
        isinstance(outcomes, list) and len(outcomes) == len(sessions),
        "distribution.complete_registered_denominator",
    )
    by_session = {row["session_id"]: row for row in outcomes}
    p.require(
        len(by_session) == len(sessions) and set(by_session) == {s["session_id"] for s in sessions},
        "distribution.no_missing_duplicate_or_foreign_outcome",
    )
    packages, terminal = [], Counter()
    exclusions, heldout = Counter(), []
    registered_ids = []
    for registered in sessions:
        outcome = by_session[registered["session_id"]]
        _checked(outcome, "material_outcome")
        p.require(
            outcome["registration_id"] == registered["id"],
            "distribution.prospective_registration_binding",
        )
        if "role" in outcome:
            p.require(
                outcome["role"] == registered["role"], "distribution.no_postoutcome_role_change"
            )
        p.require(
            outcome["status"] in {"finished", "budget_aborted", "failed", "not_run"},
            "distribution.terminal_status",
        )
        terminal[outcome["status"]] += 1
        registered_ids.append(outcome["id"])
        flags = ("financial_valid", "full_class_valid", "consumable", "authentic_origin_verified")
        p.require(
            all(type(outcome.get(key)) is bool for key in flags),
            "distribution.explicit_eligibility_flags",
        )
        eligible = outcome["status"] == "finished" and all(outcome[key] for key in flags)
        if not eligible:
            exclusions["invalid_or_incomplete_" + registered["role"]] += 1
            continue
        method, state = outcome["actual_method"], outcome["state_id"]
        expected_methods = {"control"} if registered["family"] == "control" else set(METHODS)
        p.require(
            method in expected_methods and isinstance(state, str) and state,
            "distribution.actual_method_and_fine_state",
        )
        original = outcome["original_package"]
        length = _validate_package(original, outcome, registered)
        if registered["role"] == "sealed":
            heldout.append(
                {
                    "session_id": registered["session_id"],
                    "outcome_id": outcome["id"],
                    "package_id": original["id"],
                }
            )
            continue
        packages.append(
            {
                "package_id": original["id"],
                "session_id": registered["session_id"],
                "registration_id": registered["id"],
                "outcome_id": outcome["id"],
                "pool": registered["pool"],
                "task_id": registered["task_id"],
                "family": registered["family"],
                "role": registered["role"],
                "state_id": state,
                "method": method,
                "whole_package_target_tokens": length,
                "original_package_sha256": p.sha(p.encode(original)),
                "original_package": copy.deepcopy(original),
            }
        )
    p.require(
        len({row["package_id"] for row in packages}) == len(packages),
        "distribution.unique_physical_originals",
    )
    packages.sort(key=lambda row: row["session_id"])
    support = defaultdict(set)
    states = defaultdict(list)
    for package in packages:
        support[(package["pool"], package["task_id"])].add(package["method"])
        states[(package["pool"], package["task_id"], package["state_id"])].append(package)
    for members in states.values():
        p.require(
            len({row["method"] for row in members}) == 1,
            "distribution.fine_class_has_one_actual_method",
        )
    common = sorted(
        task["task_id"]
        for task in tasks
        if task["family"] != "control"
        and all(set(METHODS) <= support[(pool, task["task_id"])] for pool in POOLS)
    )
    empty = [
        {"pool": pool, "task_id": task["task_id"]}
        for pool in POOLS
        for task in tasks
        if not support[(pool, task["task_id"])]
    ]
    movement = Fraction(len(common), 6 * TASK_COUNT)
    complete = terminal == {"finished": len(sessions)}
    material_pass = complete and not empty
    dose_pass = movement >= MINIMUM_MASS_MOVEMENT
    return p.record(
        "fixed_kernel",
        population_id=population["id"],
        registry_id=registry["id"],
        tasks=copy.deepcopy(tasks),
        policy=policy(),
        registered_session_count=len(sessions),
        outcome_ids=registered_ids,
        terminal_counts=dict(terminal),
        collection_complete=complete,
        train_packages=packages,
        retained_train_originals=len(packages),
        valid_sealed_packages=heldout,
        exclusions=dict(exclusions),
        common_intervention_task_ids=common,
        common_intervention_counts_by_family=dict(
            Counter(task["family"] for task in tasks if task["task_id"] in common)
        ),
        empty_pool_task_support=empty,
        global_mass_movement=rational(movement),
        material_gate="PASS" if material_pass else "FAIL",
        dose_gate="PASS" if dose_pass else "FAIL",
        training_gate="PASS" if material_pass and dose_pass else "FAIL",
        physical_originals_sha256=p.sha(
            p.encode(
                [
                    {
                        key: row[key]
                        for key in ("package_id", "session_id", "original_package_sha256")
                    }
                    for row in packages
                ]
            )
        ),
    )


def distribution(kernel, pool, arm):
    """Return exact pi on every retained fine state, including static tasks."""
    _checked(kernel, "fixed_kernel")
    p.require(kernel["policy"] == policy(), "distribution.frozen_policy")
    p.require(kernel["material_gate"] == "PASS", "distribution.full_material_gate_required")
    p.require(pool in POOLS and arm in ARMS, "distribution.known_pool_and_arm")
    by_state, by_method, by_task = defaultdict(list), Counter(), Counter()
    for package in kernel["train_packages"]:
        if package["pool"] == pool:
            by_state[(package["task_id"], package["state_id"])].append(package)
            by_method[(package["task_id"], package["method"])] += 1
            by_task[package["task_id"]] += 1
    common = set(kernel["common_intervention_task_ids"])
    states = []
    totals = defaultdict(Fraction)
    for (task_id, state_id), packages in sorted(by_state.items()):
        method = packages[0]["method"]
        mass = (
            ALPHA[arm][method] * Fraction(len(packages), by_method[(task_id, method)])
            if task_id in common
            else Fraction(len(packages), by_task[task_id])
        )
        totals[task_id] += mass
        states.append(
            {
                "task_id": task_id,
                "state_id": state_id,
                "method": method,
                "n_packages": len(packages),
                "n_method": by_method[(task_id, method)],
                "pi": rational(mass),
                "M_each_original": rational(Fraction(1, len(packages))),
                "package_ids": [row["package_id"] for row in packages],
            }
        )
    p.require(
        len(totals) == TASK_COUNT and all(total == 1 for total in totals.values()),
        "distribution.every_task_unit_mass",
    )
    return p.record(
        "distribution",
        kernel_id=kernel["id"],
        pool=pool,
        arm=arm,
        states=states,
        physical_originals_sha256=kernel["physical_originals_sha256"],
        task_mu=rational(Fraction(1, TASK_COUNT)),
        global_mass_movement=kernel["global_mass_movement"],
    )


def weighted_packages(kernel, pool, arm, task_ids=None):
    """All physical originals and full response histories; only weights differ."""
    assigned = distribution(kernel, pool, arm)
    state_map = {(row["task_id"], row["state_id"]): row for row in assigned["states"]}
    selected = None if task_ids is None else set(task_ids)
    if selected is not None:
        p.require(len(task_ids) == len(selected) == 5, "distribution.five_unique_update_tasks")
        families = {task["task_id"]: task["family"] for task in kernel["tasks"]}
        p.require(selected <= set(families), "distribution.known_update_tasks")
        p.require(
            Counter(families[task_id] for task_id in selected)
            == {
                "annual_flow": 1,
                "stock_rollforward": 1,
                "company_defined_metric": 1,
                "control": 2,
            },
            "distribution.fixed_five_task_composition",
        )
    result = []
    for package in kernel["train_packages"]:
        if package["pool"] != pool or selected is not None and package["task_id"] not in selected:
            continue
        state = state_map[(package["task_id"], package["state_id"])]
        original = package["original_package"]
        p.require(
            p.sha(p.encode(original)) == package["original_package_sha256"],
            "distribution.unchanged_whole_original_bytes",
        )
        coefficient = fraction(state["pi"]) / (
            5 * state["n_packages"] * package["whole_package_target_tokens"]
        )
        result.append(
            {
                **copy.deepcopy(package),
                "rows": copy.deepcopy(original["rows"]),
                "pi": state["pi"],
                "n_state": state["n_packages"],
                "target_token_coefficient": rational(coefficient),
            }
        )
    totals = defaultdict(Fraction)
    for row in result:
        totals[row["task_id"]] += (
            fraction(row["target_token_coefficient"]) * row["whole_package_target_tokens"]
        )
    p.require(
        len(totals) == (TASK_COUNT if selected is None else 5)
        and all(mass == Fraction(1, 5) for mass in totals.values()),
        "distribution.exact_one_fifth_per_task",
    )
    return result
