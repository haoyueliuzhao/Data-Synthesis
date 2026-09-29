"""CPU-only fixed-support cardinality controls; no semantic remapping."""

import copy
import hashlib
import json
from collections import Counter

import pytest

from trusted_synthesis.finance_research import v11_mapping_bound as bound


def seal(value):
    body = {key: item for key, item in value.items() if key != "id"}
    return {**body, "id": bound._digest(body)}


def fixture():
    support, mappings, blockers, slots, tasks = {}, {}, [], [], []
    for i in range(44):
        task = f"task:{i}"
        tasks.append(task)
        n = 1 if i < 13 or i >= 22 else 2 if i < 21 else 3
        ids = [f"slot:{i}:{j}" for j in range(n)]
        slots.extend(ids)
        complete = i < 22
        assignment = dict.fromkeys(ids, "state:one") if complete else {}
        chi = {"state:one": i % 2} if complete else {}
        mappings[task] = seal(
            dict(
                schema="v10_paid_task_mapping.v1",
                task_id=task,
                protocol_id="protocol:synthetic",
                mapping_status="complete" if complete else "unknown",
                mapping_admitted=complete,
                joint_bindings=[{"slot_id": sid} for sid in ids],
                state_by_slot=assignment,
                chi_by_state=chi,
            )
        )
        if complete:
            support[task] = dict(joint_valid_slot_ids=ids, n_x=n, states={"state:one": n}, chi=chi)
        else:
            blockers.append(
                dict(task_id=task, reason="joint_originals_mapping_unresolved", slot_ids=ids)
            )
    profile = seal(
        dict(
            schema="v10_conditional_capability_profile.v1",
            N=44,
            package_count=54,
            D_pi=None,
            blockers=blockers,
            state_package_histogram={"1": 13, "2": 8, "3": 1},
        )
    )
    return seal(
        dict(
            schema="v10_conditional_support_manifest.v1",
            N=44,
            original_task_denominator=1000,
            original_slot_denominator=8000,
            training_task_ids=tasks,
            joint_valid_slot_ids=slots,
            task_support=support,
            capability_profile=profile,
            all_originals_retained=True,
            no_valid_package_or_task_dropped=True,
        )
    ), mappings


def test_exact_current_shape_proves_only_conditional_zero_without_modifying_null():
    support, mappings = fixture()
    before = copy.deepcopy((support, mappings))
    result = bound.derive_bound(support, mappings)
    assert result["status"] == "CONDITIONAL_ZERO_BOUND_PROVED"
    assert result["conditional_D_pi_upper_bound"] == 0
    assert result["original_support_D_pi"] is None
    assert result["denominators"] == dict(
        original_tasks=1000,
        original_slots=8000,
        admitted_tasks=44,
        admitted_packages=54,
        complete_tasks=22,
        unresolved_tasks=22,
        complete_packages=32,
        unresolved_packages=22,
        multiple_package_tasks=9,
    )
    assert result["complete_state_package_histogram"] == {"1": 13, "2": 8, "3": 1}
    assert result["training_admitted"] is False and result["semantic_mapping_performed"] is False
    assert result["unresolved_tasks_declared_complete"] is False
    assert (support, mappings) == before


@pytest.mark.parametrize("scenario", ["unknown_multiple_packages", "complete_multiple_states"])
def test_nonzero_possibility_does_not_emit_zero(scenario):
    support, mappings = fixture()
    if scenario == "unknown_multiple_packages":
        task, sid = "task:22", "slot:22:extra"
        support["joint_valid_slot_ids"].append(sid)
        support["capability_profile"]["package_count"] += 1
        support["capability_profile"]["blockers"][0]["slot_ids"].append(sid)
        mappings[task]["joint_bindings"].append({"slot_id": sid})
    else:
        task = "task:13"
        part = support["task_support"][task]
        mappings[task]["state_by_slot"][part["joint_valid_slot_ids"][0]] = "state:two"
        mappings[task]["chi_by_state"]["state:two"] = 1
        part["states"] = {"state:one": 1, "state:two": 1}
        part["chi"] = dict(mappings[task]["chi_by_state"])
        support["capability_profile"]["state_package_histogram"] = {"1": 15, "2": 7, "3": 1}
    mappings[task] = seal(mappings[task])
    support["capability_profile"] = seal(support["capability_profile"])
    result = bound.derive_bound(seal(support), mappings)
    assert result["status"] == "NOT_ESTABLISHED"
    assert result["conditional_D_pi_upper_bound"] is None
    assert result["failed_preconditions"]
    assert result["training_admitted"] is False


def test_file_audit_checks_exact_source_SHA_and_rejects_same_identity_different_bytes(tmp_path):
    support, mappings = fixture()

    def put(relative, value):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
        path.write_bytes(raw)
        return dict(path=str(path), id=value["id"], sha256=hashlib.sha256(raw).hexdigest())

    descriptor = put("material/support/record.json", support)
    put(
        "material/result/record.json",
        seal(
            dict(
                schema="v10_material_freeze_result.v1",
                N=44,
                protocol_id="protocol:synthetic",
                support=descriptor,
            )
        ),
    )
    terminals = [
        dict(
            task_id=task,
            record=put("mapping/" + bound._digest(task) + "/record/record.json", mapping),
        )
        for task, mapping in mappings.items()
    ]
    put(
        "mapping_seal/record.json",
        seal(
            dict(
                schema="v10_complete_task_mapping_seal.v1",
                protocol_id="protocol:synthetic",
                all_registered_jobs_terminal=True,
                hard_packages_deleted=False,
                expected_tasks=44,
                terminals=terminals,
                mapping_status_counts=dict(Counter(m["mapping_status"] for m in mappings.values())),
            )
        ),
    )
    result = bound.audit_paths(tmp_path)
    assert result["conditional_D_pi_upper_bound"] == 0 and len(result["source_bindings"]) == 47
    assert result["original_support_D_pi"] is None
    path = tmp_path / "mapping" / bound._digest("task:0") / "record/record.json"
    path.write_bytes(path.read_bytes() + b"\n")
    rejected = bound.audit_paths(tmp_path)
    assert rejected["status"] == "NOT_ESTABLISHED"
    assert rejected["conditional_D_pi_upper_bound"] is None
    assert rejected["failed_preconditions"] == ["sealed_source_SHA_ID_or_path_mismatch"]
