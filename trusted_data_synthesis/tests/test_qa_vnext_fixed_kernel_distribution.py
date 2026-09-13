"""Public synthetic controls: no real responses, model loads, or GPU calls."""

import copy
from collections import Counter, defaultdict
from fractions import Fraction

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import distribution as d
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import population as pop
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


def catalog():
    rows = []
    counts = dict(zip(pop.FAMILY_COUNTS, (54, 53, 48, 100), strict=True))
    for family, count in counts.items():
        for i in range(count):
            row = {key: key + "_" + family + "_" + str(i) for key in pop.METADATA_FIELDS}
            row.update(
                task_id=family + "_" + str(i).zfill(3),
                family=family,
                quantity="difference" if i % 3 else "relative_change",
                source_cluster="cluster_" + str(i % 7),
            )
            rows.append(row)
    return {"id": "synthetic_catalog", "tasks": rows}


@pytest.fixture(scope="module")
def population():
    return pop.make_population(catalog())


@pytest.fixture(scope="module")
def registry(population):
    return pop.make_registry(population, "prospective_test_freeze", p.ORDER_SEED)


def outcome(registered, eligible=False, method=None, state=None):
    fields = dict(
        session_id=registered["session_id"],
        registration_id=registered["id"],
        status="finished",
        financial_valid=eligible,
        full_class_valid=eligible,
        consumable=eligible,
        authentic_origin_verified=eligible,
    )
    if eligible:
        length = 1 + registered["replicate"] % 3
        ids = list(range(1, length + 2))
        package = p.record(
            "encoded_original_package",
            consumable=True,
            task_id=registered["task_id"],
            pool=registered["pool"],
            registered_session_id=registered["session_id"],
            actual_method=method,
            full_class={"synthetic_complete_class": state},
            whole_package_target_tokens=length,
            original_all_raw_turns=[{"original": "failure history retained"}],
            rows=[
                {
                    "representation": {
                        "input_ids": ids,
                        "target_mask": [0] + [1] * length,
                        "labels": [-100] + ids[1:],
                        "sequence_length": len(ids),
                        "target_token_count": length,
                    }
                }
            ],
        )
        fields.update(
            actual_method=method,
            state_id=d.canonical_state_id(method, package["full_class"]),
            original_package=package,
        )
    return p.record("material_outcome", **fields)


def outcomes_for(registry, population, dual_count=60):
    targets = [row["task_id"] for row in population["tasks"] if row["family"] != "control"]
    dual = set(targets[:dual_count])
    result = []
    for registered in registry["sessions"]:
        eligible = registered["replicate"] < 3
        if registered["family"] == "control":
            method = "control"
        elif registered["task_id"] in dual:
            method = registered["basis"]
            if method == "movement":
                eligible = registered["replicate"] < (1 if registered["pool"] == "A" else 2)
        else:
            # Movement-guided candidates can actually be endpoint: retain them.
            method = "endpoint"
        state = method + ("_fine_1" if registered["replicate"] == 0 else "_fine_2")
        result.append(outcome(registered, eligible, method, state))
    return result


@pytest.fixture(scope="module")
def supported_kernel(population, registry):
    return d.build_kernel(population, registry, outcomes_for(registry, population))


def rerecord(value, **changes):
    fields = {k: copy.deepcopy(v) for k, v in value.items() if k not in {"id", "schema_version"}}
    fields.update(changes)
    return p.record(value["schema_version"].split(".")[-1], **fields)


def test_population_fixed_metadata_only_and_cluster_round_robin(population):
    assert len(population["tasks"]) == 200
    assert population["family_counts"] == pop.FAMILY_COUNTS
    first = population["tasks"][:7]
    assert [row["source_cluster"] for row in first] == ["cluster_" + str(i) for i in range(7)]
    assert [row["task_id"] for row in first] == ["annual_flow_" + str(i).zfill(3) for i in range(7)]
    assert population["tasks"][7]["task_id"] == "annual_flow_007"
    assert population["policy"]["quantity_quota"] is False
    changed = catalog()
    for row in changed["tasks"]:
        row.update(Probe_success=1000, Student_score=-1, preferred_route="movement")
    changed["tasks"].reverse()
    assert pop.make_population(changed) == population


def test_registry_exact_prospective_roles_and_full_denominator(population, registry):
    assert pop.validate_registry(registry, population) == registry["sessions"]
    counts = Counter((r["pool"], r["role"]) for r in registry["sessions"])
    assert counts == {
        ("A", "train"): 3840,
        ("A", "sealed"): 1280,
        ("B", "train"): 3840,
        ("B", "sealed"): 1280,
    }
    cells = defaultdict(Counter)
    for row in registry["sessions"]:
        cells[(row["pool"], row["task_id"], row["basis"])][row["role"]] += 1
        assert row["role"] == ("train" if row["replicate"] < 12 else "sealed")
        if row["family"] == "control":
            assert row["basis"] == "neutral"
    assert all(count == {"train": 12, "sealed": 4} for count in cells.values())
    assert [row["ordinal"] for row in registry["sessions"]] == list(range(10240))
    assert all(
        row["system_prompt_sha256"] == p.sha(p.system_prompt(row["profile"], row["basis"]))
        for row in registry["sessions"]
    )
    assert all(
        row["profile"] == p.CONTROL_PROFILE
        for row in registry["sessions"]
        if row["family"] == "control"
    )


def test_registrations_cannot_be_reassigned_after_outcomes(population, registry):
    sessions = copy.deepcopy(registry["sessions"])
    sessions[0] = rerecord(
        sessions[0], role="sealed" if sessions[0]["role"] == "train" else "train"
    )
    with pytest.raises(ValueError, match="prospective_registry"):
        pop.validate_registry(rerecord(registry, sessions=sessions), population)


def test_fixed_400_updates_with_five_tasks(population):
    schedule = pop.batch_schedule(population, 11)
    assert schedule["total_updates"] == len(schedule["batches"]) == 400
    task_families = {row["task_id"]: row["family"] for row in population["tasks"]}
    for epoch in range(10):
        rows = schedule["batches"][epoch * 40 : (epoch + 1) * 40]
        assert Counter(task for row in rows for task in row["task_ids"]) == dict.fromkeys(
            task_families, 1
        )
        assert all(
            Counter(task_families[t] for t in row["task_ids"])
            == {"annual_flow": 1, "stock_rollforward": 1, "company_defined_metric": 1, "control": 2}
            for row in rows
        )
    assert schedule == pop.batch_schedule(population, 11)
    assert schedule != pop.batch_schedule(population, 29)


def test_unequal_counts_dose_boundary_and_no_top_k(supported_kernel):
    assert supported_kernel["training_gate"] == "PASS"
    assert len(supported_kernel["common_intervention_task_ids"]) == 60
    assert d.fraction(supported_kernel["global_mass_movement"]) == Fraction(1, 20)
    assert supported_kernel["retained_train_originals"] == len(supported_kernel["train_packages"])
    assert len(supported_kernel["tasks"]) == 200
    assert all(package["role"] == "train" for package in supported_kernel["train_packages"])


@pytest.mark.parametrize("pool", pop.POOLS)
@pytest.mark.parametrize("arm", d.ARMS)
def test_exact_fine_method_task_mass_and_whole_originals(supported_kernel, pool, arm):
    assigned = d.distribution(supported_kernel, pool, arm)
    common = set(supported_kernel["common_intervention_task_ids"])
    totals, method_mass = defaultdict(Fraction), defaultdict(Fraction)
    for state in assigned["states"]:
        mass = d.fraction(state["pi"])
        totals[state["task_id"]] += mass
        method_mass[(state["task_id"], state["method"])] += mass
        assert d.fraction(state["M_each_original"]) * state["n_packages"] == 1
    assert len(totals) == 200 and set(totals.values()) == {Fraction(1)}
    for task in common:
        for method in pop.METHODS:
            assert method_mass[(task, method)] == d.ALPHA[arm][method]
    weighted = d.weighted_packages(supported_kernel, pool, arm)
    batch_totals = defaultdict(Fraction)
    for row in weighted:
        assert row["target_token_coefficient"] == d.rational(
            d.fraction(row["pi"]) / (5 * row["n_state"] * row["whole_package_target_tokens"])
        )
        assert row["original_package"]["original_all_raw_turns"] == [
            {"original": "failure history retained"}
        ]
        batch_totals[row["task_id"]] += (
            d.fraction(row["target_token_coefficient"]) * row["whole_package_target_tokens"]
        )
    assert set(batch_totals.values()) == {Fraction(1, 5)}


def test_three_arms_same_physical_set_and_static_single_method(supported_kernel):
    lists = [d.weighted_packages(supported_kernel, "A", arm) for arm in d.ARMS]
    assert [[row["package_id"] for row in rows] for rows in lists].count(
        [row["package_id"] for row in lists[0]]
    ) == 3
    common = set(supported_kernel["common_intervention_task_ids"])
    for rows in zip(*lists, strict=True):
        assert len({row["original_package_sha256"] for row in rows}) == 1
        if rows[0]["task_id"] not in common:
            assert rows[0] == rows[1] == rows[2]


def test_actual_mass_move_matches_registered_dose(supported_kernel):
    baseline = d.distribution(supported_kernel, "A", "alpha0")["states"]
    plus = d.distribution(supported_kernel, "A", "plus")["states"]
    variation = sum(
        abs(d.fraction(a["pi"]) - d.fraction(b["pi"])) for a, b in zip(baseline, plus, strict=True)
    ) / (2 * 200)
    assert variation == d.fraction(supported_kernel["global_mass_movement"])


def test_five_task_consumer_gets_all_originals_and_unit_update_mass(supported_kernel, population):
    batch = pop.batch_schedule(population, 11)["batches"][0]
    selected = set(batch["task_ids"])
    expected = [
        row["package_id"]
        for row in supported_kernel["train_packages"]
        if row["pool"] == "A" and row["task_id"] in selected
    ]
    for arm in d.ARMS:
        rows = d.weighted_packages(supported_kernel, "A", arm, batch["task_ids"])
        assert [row["package_id"] for row in rows] == expected
        assert len(rows) != 64
        assert (
            sum(
                d.fraction(row["target_token_coefficient"]) * row["whole_package_target_tokens"]
                for row in rows
            )
            == 1
        )


@pytest.mark.parametrize("kind", ["duplicate", "wrong_composition"])
def test_wrong_five_task_update_rejected(supported_kernel, population, kind):
    task_ids = pop.batch_schedule(population, 11)["batches"][0]["task_ids"]
    if kind == "duplicate":
        task_ids[-1] = task_ids[0]
    else:
        task_ids = [row["task_id"] for row in population["tasks"][:5]]
    with pytest.raises(ValueError):
        d.weighted_packages(supported_kernel, "A", "alpha0", task_ids)


def test_below_dose_does_not_delete_tasks_or_raise_step_size(population, registry):
    kernel = d.build_kernel(population, registry, outcomes_for(registry, population, 59))
    assert kernel["material_gate"] == "PASS"
    assert kernel["dose_gate"] == kernel["training_gate"] == "FAIL"
    assert d.fraction(kernel["global_mass_movement"]) == Fraction(59, 1200)
    assert len({row["task_id"] for row in d.distribution(kernel, "A", "plus")["states"]}) == 200


def test_one_empty_pool_task_fails_material_gate(population, registry):
    outcomes = outcomes_for(registry, population)
    target = population["tasks"][0]["task_id"]
    reg_by_id = {row["session_id"]: row for row in registry["sessions"]}
    for i, row in enumerate(outcomes):
        reg = reg_by_id[row["session_id"]]
        if reg["pool"] == "B" and reg["task_id"] == target:
            outcomes[i] = outcome(reg)
    kernel = d.build_kernel(population, registry, outcomes)
    assert kernel["training_gate"] == kernel["material_gate"] == "FAIL"
    assert kernel["empty_pool_task_support"] == [{"pool": "B", "task_id": target}]
    with pytest.raises(ValueError, match="material_gate"):
        d.distribution(kernel, "A", "alpha0")


def test_budget_aborted_complete_registration_cannot_train_prefix(population, registry):
    outcomes = outcomes_for(registry, population)
    outcomes[0] = rerecord(outcomes[0], status="budget_aborted")
    kernel = d.build_kernel(population, registry, outcomes)
    assert kernel["registered_session_count"] == 10240
    assert not kernel["collection_complete"] and kernel["training_gate"] == "FAIL"


def test_sealed_success_never_moves_to_train(population, registry):
    outcomes = outcomes_for(registry, population)
    i = next(i for i, row in enumerate(registry["sessions"]) if row["role"] == "sealed")
    registered = registry["sessions"][i]
    method = "control" if registered["family"] == "control" else "movement"
    outcomes[i] = outcome(registered, True, method, "sealed_fine")
    kernel = d.build_kernel(population, registry, outcomes)
    assert len(kernel["valid_sealed_packages"]) == 1
    assert all(row["session_id"] != registered["session_id"] for row in kernel["train_packages"])
    outcomes[i] = rerecord(outcomes[i], role="train")
    with pytest.raises(ValueError, match="postoutcome_role"):
        d.build_kernel(population, registry, outcomes)


def test_missing_denominator_or_rebound_outcomes_rejected(population, registry):
    outcomes = outcomes_for(registry, population)
    with pytest.raises(ValueError, match="denominator"):
        d.build_kernel(population, registry, outcomes[:-1])
    outcomes[0] = rerecord(outcomes[0], registration_id=outcomes[1]["registration_id"])
    with pytest.raises(ValueError, match="registration_binding"):
        d.build_kernel(population, registry, outcomes)


def test_all_twelve_valid_train_originals_retained_not_top_eight(population, registry):
    values = outcomes_for(registry, population)
    target = population["tasks"][0]["task_id"]
    for i, reg in enumerate(registry["sessions"]):
        if reg["task_id"] == target:
            values[i] = outcome(reg, True, reg["basis"], reg["basis"] + "_fine")
    kernel = d.build_kernel(population, registry, values)
    assert Counter(
        (row["pool"], row["method"]) for row in kernel["train_packages"] if row["task_id"] == target
    ) == {
        ("A", "endpoint"): 12,
        ("A", "movement"): 12,
        ("B", "endpoint"): 12,
        ("B", "movement"): 12,
    }
    assert len(kernel["valid_sealed_packages"]) == 16


def test_dual_support_only_one_pool_is_static_not_deleted(population, registry):
    values = outcomes_for(registry, population, 61)
    targets = [row["task_id"] for row in population["tasks"] if row["family"] != "control"]
    target = targets[60]
    for i, reg in enumerate(registry["sessions"]):
        if reg["task_id"] == target and reg["pool"] == "B":
            values[i] = outcome(reg, reg["replicate"] < 3, "endpoint", "endpoint_fine")
    kernel = d.build_kernel(population, registry, values)
    assert target not in kernel["common_intervention_task_ids"]
    assert kernel["training_gate"] == "PASS"
    states = [
        [row for row in d.distribution(kernel, "A", arm)["states"] if row["task_id"] == target]
        for arm in d.ARMS
    ]
    assert states[0] == states[1] == states[2]
    assert {row["method"] for row in states[0]} == {"endpoint", "movement"}


@pytest.mark.parametrize(
    "mutation",
    [
        "mask",
        "labels",
        "count",
        "fractional_id",
        "truncation",
        "attention",
        "pool",
        "session",
        "method",
    ],
)
def test_corrupted_original_package_is_not_eligible(population, registry, mutation):
    values = outcomes_for(registry, population)
    i = next(i for i, row in enumerate(values) if row["financial_valid"])
    value = copy.deepcopy(values[i])
    package = value["original_package"]
    rep = package["rows"][0]["representation"]
    if mutation == "mask":
        rep["target_mask"][0] = 1
    elif mutation == "labels":
        rep["labels"][-1] = -100
    elif mutation == "count":
        package["whole_package_target_tokens"] += 1
    elif mutation == "fractional_id":
        rep["input_ids"][0] = 1.5
    elif mutation == "truncation":
        rep["truncation"] = True
    elif mutation == "attention":
        rep["attention_mask"] = [0] * len(rep["input_ids"])
    elif mutation == "pool":
        package["pool"] = "B" if package["pool"] == "A" else "A"
    elif mutation == "session":
        package["registered_session_id"] = "old_probe_development_session"
    else:
        package["actual_method"] = "invented_guidance_class"
    value["original_package"] = rerecord(package)
    values[i] = rerecord(value)
    with pytest.raises(ValueError):
        d.build_kernel(population, registry, values)


@pytest.mark.parametrize(
    "value", [0.5, True, {"numerator": 1, "denominator": 0}, {"numerator": 1.0, "denominator": 2}]
)
def test_inexact_or_invalid_rational_rejected(value):
    with pytest.raises(ValueError):
        d.fraction(value)


@pytest.mark.parametrize(
    "attack",
    [
        "unsigned_original",
        "legacy_schema",
        "invented_state",
        "changed_class",
        "guidance_method",
        "changed_original_state",
    ],
)
def test_canonical_complete_state_and_new_original_identity_required(population, registry, attack):
    values = outcomes_for(registry, population)
    index = next(i for i, row in enumerate(values) if row["financial_valid"])
    value = copy.deepcopy(values[index])
    original = value["original_package"]
    if attack == "unsigned_original":
        original["id"] = "user_asserted_package"
    elif attack == "legacy_schema":
        original["schema_version"] = "old_runtime.v1.encoded_original_package"
    elif attack == "invented_state":
        value["state_id"] = "movement_guidance_assigned_state"
    elif attack == "changed_class":
        value["original_package"] = rerecord(original, full_class={"invented": "other_class"})
    elif attack == "changed_original_state":
        value["original_package"] = rerecord(original, state_id="invented_original_state")
    else:
        value["actual_method"] = "movement" if value["actual_method"] != "movement" else "endpoint"
    values[index] = rerecord(value)
    with pytest.raises(ValueError):
        d.build_kernel(population, registry, values)


def test_canonical_state_hash_uses_complete_actual_class_not_requested_basis():
    actual = {"retained_errors": ["format_failure"], "actual_nodes": ["tool_1", "tool_2"]}
    value = d.canonical_state_id("movement", actual)
    assert value == "fixed_kernel_state:" + p.sha(
        p.encode({"actual_method": "movement", "full_class": actual})
    )
    assert value != d.canonical_state_id("endpoint", actual)
    assert value != d.canonical_state_id("movement", {**actual, "retained_errors": []})
