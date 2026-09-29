"""Conditional cardinality proof; no semantic remapping, wallet, model or writes."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

SCHEMA = "v11_fixed_mapping_structural_bound.v1"
ASSUMPTIONS = [
    "Keep the same original admitted packages and tasks; no additions or deletions.",
    "Freeze all already-complete partitions; never split or merge their package membership.",
    "Only fill missing mappings; every whole original package belongs to one nonempty state.",
    "The conclusion assumes every missing semantic mapping eventually becomes valid and complete.",
]


def _digest(value):
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _require(value, reason):
    if not value:
        raise ValueError(reason)


def _checked(value, schema=None):
    _require(
        isinstance(value, dict)
        and value.get("id") == _digest({k: v for k, v in value.items() if k != "id"})
        and (schema is None or value.get("schema") == schema),
        "record_identity_or_schema_mismatch",
    )


def _result(**fields):
    body = dict(
        schema=SCHEMA,
        conditional_assumptions=ASSUMPTIONS,
        formula="D_pi = sum_x (number_of_nonempty_states_x - 1)",
        semantic_mapping_performed=False,
        unresolved_tasks_declared_complete=False,
        original_support_modified=False,
        original_support_null_replaced=False,
        artificial_state_splitting=False,
        training_admitted=False,
        wallet_opened=False,
        API_calls=0,
        model_or_tokenizer_loads=0,
        **fields,
    )
    return {**body, "id": _digest(body)}


def derive_bound(support, mapping_records, *, source_bindings=None):
    """Pure record proof. audit_paths additionally checks original file SHA.

    Missing evidence, multi-state complete tasks or multi-package unknown tasks
    return NOT_ESTABLISHED with a null bound, never a guessed zero.
    """
    sources = [] if source_bindings is None else source_bindings
    try:
        _checked(support, "v10_conditional_support_manifest.v1")
        profile = support["capability_profile"]
        _checked(profile, "v10_conditional_capability_profile.v1")
        task_order, all_slots = support["training_task_ids"], support["joint_valid_slot_ids"]
        _require(
            task_order
            and len(task_order) == len(set(task_order)) == support["N"]
            and all_slots
            and len(all_slots) == len(set(all_slots)) == profile["package_count"]
            and profile["N"] == support["N"]
            and support["all_originals_retained"] is True
            and support["no_valid_package_or_task_dropped"] is True,
            "exact_original_task_and_package_denominators_required",
        )
        _require(
            isinstance(mapping_records, dict) and set(mapping_records) == set(task_order),
            "complete_mapping_record_task_inventory_required",
        )
        complete, unresolved = support["task_support"], {}
        for blocker in profile["blockers"]:
            _require(
                blocker.get("reason") == "joint_originals_mapping_unresolved",
                "other_material_blocker_not_resolved_by_this_bound",
            )
            task = blocker["task_id"]
            _require(task not in unresolved, "duplicate_unresolved_task")
            unresolved[task] = blocker["slot_ids"]
        _require(
            not set(complete) & set(unresolved)
            and set(complete) | set(unresolved) == set(task_order),
            "complete_and_missing_partitions_must_cover_all_original_tasks",
        )
        inventory, evidence, histogram = [], [], Counter()
        complete_single_state, missing_single_package = True, True
        for task in task_order:
            mapping = mapping_records[task]
            _checked(mapping, "v10_paid_task_mapping.v1")
            _require(mapping["task_id"] == task, "mapping_task_join_mismatch")
            slots = complete[task]["joint_valid_slot_ids"] if task in complete else unresolved[task]
            _require(
                isinstance(slots, list) and slots and len(slots) == len(set(slots)),
                "distinct_nonempty_original_whole_packages_required",
            )
            bindings = mapping["joint_bindings"]
            _require(
                len(bindings) == len(slots)
                and {item["slot_id"] for item in bindings} == set(slots),
                "mapping_original_joint_membership_mismatch",
            )
            inventory.extend(slots)
            if task in complete:
                part, assignment = complete[task], mapping["state_by_slot"]
                _require(
                    mapping["mapping_status"] == "complete"
                    and mapping["mapping_admitted"] is True
                    and set(assignment) == set(slots)
                    and all(isinstance(state, str) and state for state in assignment.values())
                    and part["n_x"] == len(slots)
                    and dict(Counter(assignment.values())) == part["states"]
                    and mapping["chi_by_state"] == part["chi"],
                    "already_complete_original_partition_changed",
                )
                state_count = len(part["states"])
                complete_single_state &= state_count == 1
                histogram.update(str(count) for count in part["states"].values())
            else:
                _require(
                    mapping["mapping_status"] == "unknown"
                    and mapping["mapping_admitted"] is False
                    and mapping["state_by_slot"] == {}
                    and mapping["chi_by_state"] == {},
                    "missing_mapping_must_remain_original_unknown",
                )
                state_count = None
                missing_single_package &= len(slots) == 1
            evidence.append(
                dict(
                    task_id=task,
                    mapping_record_id=mapping["id"],
                    original_mapping_status=mapping["mapping_status"],
                    package_count=len(slots),
                    current_complete_state_count=state_count,
                    maximum_states_under_fixed_partition_and_missing_only_completion=(
                        state_count if state_count is not None else len(slots)
                    ),
                )
            )
        _require(
            len(inventory) == len(set(inventory)) == len(all_slots)
            and set(inventory) == set(all_slots),
            "original_package_partition_is_not_exact",
        )
        _require(
            dict(histogram) == profile["state_package_histogram"],
            "original_completed_state_histogram_disagrees",
        )
        multiple = [row for row in evidence if row["package_count"] > 1]
        premises = dict(
            original_task_package_and_mapping_identities_join=True,
            every_complete_task_has_one_state=bool(complete_single_state),
            every_unresolved_task_has_one_package=bool(missing_single_package),
            all_multiple_package_tasks_already_complete=all(
                row["original_mapping_status"] == "complete" for row in multiple
            ),
        )
        proved = all(premises.values())
        return _result(
            status="CONDITIONAL_ZERO_BOUND_PROVED" if proved else "NOT_ESTABLISHED",
            conditional_D_pi_upper_bound=0 if proved else None,
            conditional_D_pi_if_all_missing_mappings_complete=0 if proved else None,
            original_support_D_pi=profile["D_pi"],
            support_record_id=support["id"],
            fixed_complete_partition_sha256=_digest(complete),
            source_bindings=sources,
            verified_preconditions=premises,
            failed_preconditions=[key for key, valid in premises.items() if not valid],
            denominators=dict(
                original_tasks=support["original_task_denominator"],
                original_slots=support["original_slot_denominator"],
                admitted_tasks=len(task_order),
                admitted_packages=len(all_slots),
                complete_tasks=len(complete),
                unresolved_tasks=len(unresolved),
                complete_packages=sum(
                    r["package_count"]
                    for r in evidence
                    if r["original_mapping_status"] == "complete"
                ),
                unresolved_packages=sum(
                    r["package_count"]
                    for r in evidence
                    if r["original_mapping_status"] == "unknown"
                ),
                multiple_package_tasks=len(multiple),
            ),
            complete_state_package_histogram=dict(sorted(histogram.items())),
            task_cardinality_evidence=evidence,
            consequences_if_condition_met=(
                dict(
                    pi_equals_r_equals_one=True,
                    centered_state_gradient_zero=True,
                    distribution_N_zero=True,
                    normalized_Manual_plus_minus_distribution_unchanged=True,
                )
                if proved
                else None
            ),
            proof_scope="cardinality only, not semantic completion or five-arm admission",
        )
    except (ValueError, KeyError, TypeError) as error:
        return _result(
            status="NOT_ESTABLISHED",
            conditional_D_pi_upper_bound=None,
            conditional_D_pi_if_all_missing_mappings_complete=None,
            failed_preconditions=[str(error)],
            source_bindings=sources,
        )


def audit_paths(artifact_root):
    """Verify the original current 54/44 file references; only reads files."""
    root, sources = Path(artifact_root).absolute(), []
    try:
        _require(
            root == root.resolve() and ".." not in root.parts, "canonical_artifact_root_required"
        )

        def read(relative, *, descriptor=None):
            path = root / relative
            _require(
                path.is_relative_to(root)
                and ".." not in path.parts
                and not any(item.is_symlink() for item in (path, *path.parents)),
                "source_path_redirect_or_symlink",
            )
            raw = path.read_bytes()
            value = json.loads(raw)
            _checked(value)
            file_hash = hashlib.sha256(raw).hexdigest()
            if descriptor is not None:
                _require(
                    Path(descriptor["path"]) == path
                    and descriptor["sha256"] == file_hash
                    and descriptor["id"] == value["id"],
                    "sealed_source_SHA_ID_or_path_mismatch",
                )
            sources.append(dict(path=str(path), sha256=file_hash, id=value["id"], bytes=len(raw)))
            return value

        material = read(Path("material/result/record.json"))
        _checked(material, "v10_material_freeze_result.v1")
        support = read(Path("material/support/record.json"), descriptor=material["support"])
        seal = read(Path("mapping_seal/record.json"))
        _checked(seal, "v10_complete_task_mapping_seal.v1")
        _require(
            seal["protocol_id"] == material["protocol_id"]
            and seal["all_registered_jobs_terminal"] is True
            and seal["hard_packages_deleted"] is False
            and seal["expected_tasks"] == material["N"] == support["N"] == 44
            and len(support["joint_valid_slot_ids"]) == 54
            and len(seal["terminals"]) == 44,
            "current_54_package_44_task_scope_not_verified",
        )
        mappings = {}
        for terminal in seal["terminals"]:
            task = terminal["task_id"]
            _require(task not in mappings, "duplicate_mapping_terminal_task")
            mappings[task] = read(
                Path("mapping") / _digest(task) / "record/record.json",
                descriptor=terminal["record"],
            )
        _require(
            dict(Counter(row["mapping_status"] for row in mappings.values()))
            == seal["mapping_status_counts"],
            "sealed_mapping_status_counts_disagree",
        )
        return derive_bound(support, mappings, source_bindings=sources)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return _result(
            status="NOT_ESTABLISHED",
            conditional_D_pi_upper_bound=None,
            conditional_D_pi_if_all_missing_mappings_complete=None,
            failed_preconditions=[str(error)],
            source_bindings=sources,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, required=True, help="Original V10 artifact root; read-only"
    )
    result = audit_paths(parser.parse_args().root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "CONDITIONAL_ZERO_BOUND_PROVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
