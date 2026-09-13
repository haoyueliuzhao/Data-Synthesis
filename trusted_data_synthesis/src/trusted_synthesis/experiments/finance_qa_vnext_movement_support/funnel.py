"""Fixed-denominator metadata funnel; no trajectory replay or new qualification.

UND is an original assessor verdict, not evidence of zero generation probability.
A false financial qualification is not by itself an incorrect numeric answer.
Only immutable metadata is read; this module never opens a session/raw response,
encoded token package, Student output, model, tokenizer or external API.
"""

from collections import Counter, defaultdict
from pathlib import PurePosixPath

from ..finance_qa_vnext_catalog_bridge.worker import FAMILY_TO_SCALE_GROUP
from ..finance_qa_vnext_eval_readiness import collection, training_runtime
from . import protocol as p

STAGES = (
    "registered",
    "first_Final",
    "quantity_PASS",
    "support_PASS",
    "actual_method_determined",
    "financial_valid",
    "MAPPED",
    "representation_eligible",
    "token_consumable",
)
METHODS = {"endpoint", "movement", "control", "HYBRID_UNDETERMINED", "UNDETERMINED"}


def _identity(value, kind):
    p.require(isinstance(value, dict), "funnel.original_record_object")
    expected = training_runtime.record(
        kind, **{key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    )
    p.require(value == expected, "funnel.original_content_identity:" + kind)


def _relative_qualification(path):
    p.require(isinstance(path, str) and "\\" not in path, "funnel.original_qualification_path")
    value = PurePosixPath(path)
    p.require(
        not value.is_absolute() and ".." not in value.parts and value.as_posix() == path,
        "funnel.canonical_qualification_path",
    )
    relative = value.relative_to(p.COLLECTION)
    p.require(
        len(relative.parts) == 3
        and relative.parts[0] == "sessions"
        and relative.parts[-1] == "qualification.json",
        "funnel.only_qualification_metadata_not_session_or_raw",
    )
    return relative.as_posix()


def read_inputs(collection_parent, materials_parent):
    """Caller-owned LinearParents; each read verifies its original SHA, no sweep."""
    p.require(
        collection_parent.relative == p.COLLECTION
        and collection_parent.manifest["id"] == p.COLLECTION_MANIFEST
        and materials_parent.relative == p.MATERIALS
        and materials_parent.manifest["id"] == p.MATERIAL_MANIFEST,
        "funnel.exact_read_only_original_parent_identities",
    )
    report = collection_parent.read("report.json")
    results = collection_parent.read("session_results.json")
    qualifications = {}
    for result in results:
        _identity(result, "collected_original_session")
        relative = _relative_qualification(result["qualification_path"])
        p.require(
            PurePosixPath(relative).parts[1] == result["registered_session"]["session_id"],
            "funnel.qualification_registered_directory_identity",
        )
        qualification = collection_parent.read(relative)
        p.require(
            qualification["id"] == result["qualification_id"]
            and qualification["id"] not in qualifications,
            "funnel.exact_unique_qualification_read",
        )
        qualifications[qualification["id"]] = qualification
    manifest = materials_parent.read("material_manifest.json")
    inventory = materials_parent.read("encoded_package_inventory.json")
    collection_parent.check_manifest()
    materials_parent.check_manifest()
    return dict(
        collection_report=report,
        session_results=results,
        qualifications=qualifications,
        material_manifest=manifest,
        encoded_inventory=inventory,
    )


def _hist(values):
    return dict(sorted(Counter(values).items()))


def _summary(rows):
    cumulative, marginal = Counter(), Counter()
    for row in rows:
        tests = (
            True,
            row["first_Final"],
            row["quantity_status"] == "PASS",
            row["support_status"] == "PASS",
            row["actual_method"] in {"endpoint", "movement", "control"},
            row["financial_valid"],
            row["full_mapping_status"] == "MAPPED",
            row["representation_eligible"],
            row["token_consumable"],
        )
        active = True
        for stage, passed in zip(STAGES, tests, strict=True):
            marginal[stage] += int(passed)
            active = active and passed
            cumulative[stage] += int(active)
    task_flags = {row["task_id"]: row["common_AB_ready"] for row in rows}
    return dict(
        registered_denominator=len(rows),
        stage_cumulative_counts={stage: cumulative[stage] for stage in STAGES},
        stage_marginal_counts={stage: marginal[stage] for stage in STAGES},
        quantity_status_histogram=_hist(row["quantity_status"] for row in rows),
        support_status_histogram=_hist(row["support_status"] for row in rows),
        actual_method_at_original_qualification=_hist(row["actual_method"] for row in rows),
        method_then_old_mapping=[
            {"actual_method": method, "old_mapping_status": mapping, "sessions": count}
            for (method, mapping), count in sorted(
                Counter((row["actual_method"], row["full_mapping_status"]) for row in rows).items()
            )
        ],
        reason_histogram=_hist(
            row["reason"] if row["reason"] is not None else "<none>" for row in rows
        ),
        pending_reason_session_histogram=_hist(
            reason for row in rows for reason in set(row["pending_reasons"])
        ),
        pending_reason_field_missing_sessions=sum(
            not row["pending_reason_field_present"] for row in rows
        ),
        financial_false_by_quantity_status=_hist(
            row["quantity_status"] for row in rows if not row["financial_valid"]
        ),
        terminal_histogram=_hist(row["terminal"] for row in rows),
        authentic_origin_verified=sum(row["authentic_origin_verified"] for row in rows),
        encoding_attempted=sum(row["encoding_attempted"] for row in rows),
        token_nonconsumable=sum(
            row["encoding_attempted"] and not row["token_consumable"] for row in rows
        ),
        common_AB_task_denominator=len(task_flags),
        common_AB_ready_tasks=sum(task_flags.values()),
        registered_sessions_on_common_ready_tasks=sum(row["common_AB_ready"] for row in rows),
    )


def _grouped(rows, keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    return [
        dict(zip(keys, key, strict=True), **_summary(values))
        for key, values in sorted(groups.items())
    ]


def aggregate(
    collection_report,
    session_results,
    qualifications,
    material_manifest,
    encoded_inventory,
    *,
    task_metadata=None,
    expected_session_count=24640,
):
    """Pure complete-cohort aggregation; no inferred actual methods or dropped UND."""
    _identity(collection_report, "fixed_collection_report")
    _identity(material_manifest, "fixed_AB_material_manifest")
    p.require(
        type(expected_session_count) is int
        and expected_session_count > 0
        and isinstance(session_results, list)
        and collection_report["status"] == "COMPLETE_FIXED_COLLECTION"
        and collection_report["collection_complete"] is True
        and collection_report["registered_session_count"]
        == collection_report["recorded_session_count"]
        == collection_report["finished_session_count"]
        == len(session_results)
        == expected_session_count,
        "funnel.complete_fixed_denominator_not_prefix",
    )
    tasks = collection_report["source_task_order"]
    p.require(
        isinstance(tasks, list)
        and tasks
        and len({row["task_id"] for row in tasks}) == len(tasks)
        and all(row["family"] in FAMILY_TO_SCALE_GROUP for row in tasks),
        "funnel.original_public_task_family_inventory",
    )
    by_task = {
        row["task_id"]: {**row, "group": FAMILY_TO_SCALE_GROUP[row["family"]]} for row in tasks
    }
    if task_metadata is not None:
        p.require(
            isinstance(task_metadata, dict)
            and set(task_metadata) == set(by_task)
            and all(
                all(task_metadata[task][key] == value[key] for key in ("family", "group"))
                for task, value in by_task.items()
            ),
            "funnel.caller_task_metadata_must_match_original_family_registration",
        )
    registered = [row["registered_session"] for row in session_results]
    collection._validate_registration(tasks, registered)
    p.require(
        len({row["session_id"] for row in registered}) == len(registered)
        and len({row["session_id"] for row in session_results}) == len(session_results)
        and isinstance(qualifications, dict)
        and set(qualifications) == {row["qualification_id"] for row in session_results}
        and len(qualifications) == len(session_results),
        "funnel.exhaustive_unique_session_and_qualification_joins",
    )
    readiness = material_manifest["common_AB_readiness"]
    p.require(
        material_manifest["collection_id"] == collection_report["id"]
        and material_manifest["collection_complete"] is True
        and material_manifest["all_original_registered_denominators"] == expected_session_count
        and material_manifest["source_task_order"] == [row["task_id"] for row in tasks]
        and len(readiness) == len(tasks)
        and {row["task_id"] for row in readiness} == set(by_task),
        "funnel.exact_material_collection_and_task_population_parent",
    )
    common = {row["task_id"]: row for row in readiness}
    p.require(isinstance(encoded_inventory, list), "funnel.encoded_metadata_inventory")
    encoded = {row["registered_session_id"]: row for row in encoded_inventory}
    p.require(len(encoded) == len(encoded_inventory), "funnel.no_duplicate_encoded_session")
    rows, consumable_counts = [], Counter()
    for result in session_results:
        _identity(result, "collected_original_session")
        reg = result["registered_session"]
        qualification = qualifications[result["qualification_id"]]
        _identity(qualification, "training_assessment")
        task = by_task[reg["task_id"]]
        p.require(
            qualification["id"] == result["qualification_id"]
            and qualification["session_id"] == result["session_id"]
            and qualification["task_id"] == reg["task_id"]
            and qualification["requested_basis"] == reg["basis"]
            and qualification["terminal"] == result["terminal"]
            and all(
                qualification[key] == result[key]
                for key in (
                    "actual_method",
                    "financial_valid",
                    "full_mapping_status",
                    "representation_eligible",
                )
            ),
            "funnel.original_result_qualification_registration_agreement",
        )
        p.require(
            qualification["quantity_status"] in {"PASS", "FAIL", "UNDETERMINED"}
            and qualification["support_status"] in {"PASS", "FAIL", "UNDETERMINED"}
            and qualification["actual_method"] in METHODS
            and qualification["full_mapping_status"] in {"MAPPED", "PENDING_REVIEW"}
            and all(
                type(qualification[key]) is bool
                for key in (
                    "financial_valid",
                    "representation_eligible",
                    "authentic_Teacher_origin_verified",
                )
            ),
            "funnel.original_status_domains_not_inferred",
        )
        index = qualification["first_final_index"]
        p.require(
            (index is None or type(index) is int and index >= 0)
            and (index is not None) == (result["terminal"] == "first_final"),
            "funnel.original_first_Final_boundary",
        )
        pending = qualification.get("full_mapping_pending_reasons", [])
        p.require(
            isinstance(pending, list)
            and all(isinstance(reason, str) for reason in pending)
            and (qualification["reason"] is None or isinstance(qualification["reason"], str)),
            "funnel.original_reason_metadata",
        )
        entry = encoded.get(reg["session_id"])
        if entry is not None:
            p.require(
                qualification["representation_eligible"]
                and entry["task_id"] == reg["task_id"]
                and entry["group"] == task["group"]
                and entry["pool"] == reg["pool"]
                and entry["actual_method"] == qualification["actual_method"]
                and type(entry["consumable"]) is bool,
                "funnel.encoded_metadata_exact_original_stratum",
            )
            if entry["consumable"]:
                consumable_counts[reg["task_id"], reg["pool"], entry["actual_method"]] += 1
        rows.append(
            dict(
                registered_session_id=reg["session_id"],
                session_id=result["session_id"],
                qualification_id=qualification["id"],
                task_id=reg["task_id"],
                family=task["family"],
                group=task["group"],
                pool=reg["pool"],
                requested_basis=reg["basis"],
                replicate=reg["replicate"],
                terminal=result["terminal"],
                first_Final=index is not None,
                first_final_index=index,
                quantity_status=qualification["quantity_status"],
                support_status=qualification["support_status"],
                actual_method=qualification["actual_method"],
                financial_valid=qualification["financial_valid"],
                full_mapping_status=qualification["full_mapping_status"],
                representation_eligible=qualification["representation_eligible"],
                authentic_origin_verified=qualification["authentic_Teacher_origin_verified"],
                encoding_attempted=entry is not None,
                token_consumable=bool(entry and entry["consumable"]),
                common_AB_ready=common[reg["task_id"]]["common_AB_ready"],
                reason=qualification["reason"],
                pending_reasons=list(pending),
                pending_reason_field_present="full_mapping_pending_reasons" in qualification,
            )
        )
    p.require(
        set(encoded)
        == {row["registered_session_id"] for row in rows if row["representation_eligible"]},
        "funnel.every_and_only_representation_eligible_session_has_encoding_metadata",
    )
    common_counts = Counter()
    for task_id, row in common.items():
        group = by_task[task_id]["group"]
        methods = ("control",) if group == "control" else ("endpoint", "movement")
        expected = {
            pool: {method: consumable_counts[task_id, pool, method] for method in methods}
            for pool in ("A", "B")
        }
        ready = all(count >= 10 for values in expected.values() for count in values.values())
        p.require(
            row["group"] == group
            and row["counts_by_pool_actual_method"] == expected
            and type(row["common_AB_ready"]) is bool
            and row["common_AB_ready"] is ready,
            "funnel.exact_original_common_AB_from_all_consumable_actual_methods",
        )
        common_counts[group] += int(ready)
    p.require(
        all(
            material_manifest["population_selection"]["ready_counts"][group] == common_counts[group]
            for group in set(FAMILY_TO_SCALE_GROUP.values())
        )
        and collection_report["financially_valid_sessions"]
        == sum(row["financial_valid"] for row in rows)
        and collection_report["representation_eligible_sessions"]
        == sum(row["representation_eligible"] for row in rows),
        "funnel.original_collection_and_material_aggregate_totals_agree",
    )
    return p.record(
        "phase_zero_funnel",
        collection_report_id=collection_report["id"],
        material_manifest_id=material_manifest["id"],
        session_results_canonical_sha256=p.sha(p.encode(session_results)),
        encoding_inventory_canonical_sha256=p.sha(p.encode(encoded_inventory)),
        declared_expected_session_count=expected_session_count,
        is_original_24640_session_cohort=expected_session_count == 24640,
        stage_order=list(STAGES),
        totals=_summary(rows),
        cohort_rows=_grouped(rows, ("family", "group", "pool", "requested_basis")),
        group_rows=_grouped(rows, ("family", "group")),
        requested_basis_rows=_grouped(rows, ("requested_basis",)),
        all_session_rows=rows,
        common_AB_readiness=readiness,
        selected_task_count=len(material_manifest["population_selection"]["selected"]),
        selected_package_descriptor_count=len(material_manifest["packages"]),
        original_actual_method_counts_precede_old_fine_mapping=True,
        quantity_PASS_is_original_assessment_not_new_numeric_verification=True,
        UNDETERMINED_is_not_proof_of_zero_movement_generation=True,
        financial_false_is_not_equivalent_to_wrong_final_quantity=True,
        pending_reason_histogram_unit="sessions containing each reason; reasons may overlap",
        common_AB_count_unit="unique tasks; never substituted for registered-session denominator",
        hypotheses_about_generation_or_mapper_failures_inferred=False,
        original_thresholds_or_population_changed=False,
        raw_trajectory_or_encoded_token_package_bodies_read=False,
        Student_results_read=False,
        API_calls=0,
        GPU_calls=0,
    )
