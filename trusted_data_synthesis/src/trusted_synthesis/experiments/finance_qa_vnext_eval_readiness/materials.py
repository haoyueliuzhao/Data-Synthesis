"""Authenticated whole-original packages, one CPU encoding pass, and exact loss input.

Nothing here starts a Student or loads weights. Every frozen registered session
must be terminal before representation/material selection; an incomplete prefix
can never supply a seemingly adequate population.
"""

import copy
import json
from collections import Counter, defaultdict
from pathlib import Path

from ..finance_qa_vnext_basis_scale_preparation import design
from ..finance_qa_vnext_catalog_bridge.materials import load_local_tokenizer
from ..finance_qa_vnext_catalog_bridge.worker import FAMILY_TO_SCALE_GROUP, encode, require, sha
from ..finance_qa_vnext_model_execution.representation import encode_original_candidate
from ..finance_qa_vnext_task_build.archive import write_json
from . import training_runtime

MAX_SEQUENCE_LENGTH = 24_576


def policy():
    return training_runtime.record(
        "original_package_consumer_policy",
        maximum_sequence_length=MAX_SEQUENCE_LENGTH,
        tokenizer_constructions=1,
        model_weight_loads=0,
        truncation=False,
        only_after_complete_fixed_collection=True,
        authenticated_model_returns_required=True,
        financially_valid_and_fine_mapped_required=True,
        all_target_response_tokens=(
            "successful tool responses and first Final, each in its original full request history"
        ),
        failed_format_and_tool_responses=(
            "retained in every original later input history and full raw package"
        ),
        per_pool_per_actual_method_train=8,
        per_pool_per_actual_method_heldout=2,
        material_order="registered session order, no length/score/fine-class sorting",
        actual_method_not_guidance_label=True,
        exact_update_coefficient="alpha(method|task)/(40*whole_package_target_tokens)",
        global_N_microbatch_or_total_token_divisor=False,
        pool_A_B_mixed=False,
        Student_calls=0,
    )


def checked_record(value, kind):
    expected = training_runtime.record(
        kind, **{key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    )
    require(value == expected, "materials.content_identity:" + kind)


def raw_package(session, qualification, registered):
    training_runtime.replay(session)
    checked_record(qualification, "training_assessment")
    require(
        qualification["session_id"] == session["id"]
        and registered["session_id"] == session["registered_session_id"]
        and registered["task_id"] == session["identity"]["task_id"],
        "materials.exact_session_join",
    )
    require(
        session["origin"] == "live_teacher_callback"
        and qualification["origin"] == session["origin"],
        "materials.scripted_origin_never_trainable",
    )
    require(
        qualification["authentic_Teacher_origin_verified"]
        and qualification["representation_eligible"]
        and qualification["financial_valid"]
        and qualification["full_mapping_status"] == "MAPPED",
        "materials.authentic_financial_full_mapping_required",
    )
    candidates = []
    for turn, event in zip(session["turns"], session["events"], strict=True):
        positive = (
            event["final"]
            or event["tool_call"] is not None
            and event["tool_call"]["status"] == "ok"
        )
        if not positive:
            continue
        candidates.append(
            training_runtime.record(
                "original_Teacher_response",
                task_id=session["identity"]["task_id"],
                session_id=session["id"],
                qualification_id=qualification["id"],
                response_index=turn["response_index"],
                public_runtime_state_id="history:" + sha(encode(turn["input_messages"])),
                messages=copy.deepcopy(turn["input_messages"]),
                target_text=turn["raw_response"],
                target_raw_sha256=turn["raw_response_sha256"],
                response_kind="Final" if event["final"] else event["tool_call"]["tool"],
                actual_method=qualification["actual_method"],
                requested_basis=session["requested_basis"],
                transport_evidence=turn["transport_evidence"],
                origin=session["origin"],
                training_sample=False,
            )
        )
    require(
        candidates and candidates[-1]["response_kind"] == "Final",
        "materials.complete_first_Final_package",
    )
    return training_runtime.record(
        "authentic_original_package",
        task_id=session["identity"]["task_id"],
        session_id=session["id"],
        registered_session_id=registered["session_id"],
        pool=registered["pool"],
        family=session["identity"]["family"],
        group=FAMILY_TO_SCALE_GROUP[session["identity"]["family"]],
        actual_method=qualification["actual_method"],
        requested_basis=session["requested_basis"],
        full_class=qualification["full_class"],
        qualification_id=qualification["id"],
        original_all_raw_turns=copy.deepcopy(session["turns"]),
        candidates=candidates,
        origin=session["origin"],
        authentic_Teacher_origin_verified=True,
        financial_valid=True,
        full_mapping_status="MAPPED",
        training_eligible=False,
        training_samples=0,
        complete_first_final_package=True,
    )


def _read(root, relative):
    path = Path(root) / relative
    require(
        not Path(relative).is_absolute()
        and ".." not in Path(relative).parts
        and path.resolve().is_relative_to(root)
        and not path.is_symlink(),
        "materials.relative_bound_path",
    )
    return json.loads(path.read_bytes())


def run(
    root,
    output,
    collection_directory,
    tasks,
    *,
    expected_collection_id,
    ledger,
    receipt_verifier,
    loader=load_local_tokenizer,
    encoder=encode_original_candidate,
):
    root, output, collection_directory = (
        Path(root).resolve(),
        Path(output).resolve(),
        Path(collection_directory).resolve(),
    )
    require(
        output.is_relative_to(root)
        and collection_directory.is_relative_to(root)
        and not output.exists(),
        "materials.new_contained_output",
    )
    report = json.loads((collection_directory / "report.json").read_bytes())
    checked_record(report, "fixed_collection_report")
    require(
        report["id"] == expected_collection_id
        and report["collection_complete"]
        and report["status"] == "COMPLETE_FIXED_COLLECTION",
        "materials.complete_collection_required",
    )
    registry = ledger.sessions()
    require(
        len(registry) == report["registered_session_count"]
        and all(row["state"] == "finished" for row in registry),
        "materials.no_partial_registry_population",
    )
    entries = json.loads((collection_directory / "session_results.json").read_bytes())
    require(
        len(entries) == len(registry)
        and {row["registered_session"]["session_id"] for row in entries}
        == {row["session_id"] for row in registry},
        "materials.all_registered_session_denominators",
    )
    fields = ("session_id", "task_id", "pool", "basis", "replicate")
    require(
        [tuple(entry["registered_session"][key] for key in fields) for entry in entries]
        == [tuple(row[key] for key in fields) for row in registry],
        "materials.unchanged_registered_session_order_and_pool",
    )
    require(
        len({row["task_id"] for row in tasks}) == len(tasks), "materials.fixed_unique_task_order"
    )
    require(
        [{"task_id": row["task_id"], "family": row["family"]} for row in tasks]
        == report["source_task_order"]
        and {row["task_id"] for row in tasks} == {row["task_id"] for row in registry},
        "materials.complete_unchanged_source_catalog_order",
    )
    output.mkdir(parents=True)
    write_json(output / "policy.json", policy())
    write_json(
        output / "materialization_started.json",
        training_runtime.record(
            "materialization_started", collection_id=report["id"], tokenizer_loads_permitted=1
        ),
    )
    packages, exclusions = [], []
    for entry in entries:
        checked_record(entry, "collected_original_session")
        if not entry["representation_eligible"]:
            exclusions.append(
                {
                    "registered_session_id": entry["registered_session"]["session_id"],
                    "phase": "financial_full_mapping_or_origin",
                    "reason": "not_representation_eligible",
                }
            )
            continue
        session = _read(root, entry["session_path"])
        qualification = _read(root, entry["qualification_path"])
        require(
            session["id"] == entry["session_id"]
            and qualification["id"] == entry["qualification_id"],
            "materials.original_session_qualification_ids",
        )
        origin = receipt_verifier(session, ledger)
        require(
            origin == qualification["origin_evidence"], "materials.authentic_receipt_reverification"
        )
        package = raw_package(session, qualification, entry["registered_session"])
        write_json(
            output / "packages" / package["registered_session_id"] / "raw_package.json", package
        )
        packages.append(package)
    encoded_packages, failures, binding = [], [], None
    tokenizer_loads = int(bool(packages))
    if packages:
        binding, tokenizer = loader(root)
        require(
            type(binding.get("maximum_sequence_length")) is int
            and MAX_SEQUENCE_LENGTH <= binding["maximum_sequence_length"] <= MAX_SEQUENCE_LENGTH
            and binding.get("model_max_position_embeddings", 0) >= MAX_SEQUENCE_LENGTH,
            "materials.frozen_24576_tokenizer_binding",
        )
        for package in packages:
            rows, errors = [], []
            for candidate in package["candidates"]:
                try:
                    encoded = encoder(
                        candidate, binding, tokenizer, maximum_sequence_length=MAX_SEQUENCE_LENGTH
                    )
                    rows.append({"candidate_id": candidate["id"], "representation": encoded})
                    if not encoded["consumable_token_representation"]:
                        errors.append(
                            {"candidate_id": candidate["id"], "reason": encoded["reason"]}
                        )
                except (ValueError, TypeError, KeyError, UnicodeError, RuntimeError) as error:
                    errors.append({"candidate_id": candidate["id"], "reason": str(error)})
            encoded_package = training_runtime.record(
                "encoded_original_package",
                raw_package_id=package["id"],
                registered_session_id=package["registered_session_id"],
                task_id=package["task_id"],
                pool=package["pool"],
                group=package["group"],
                actual_method=package["actual_method"],
                full_class=package["full_class"],
                rows=rows,
                errors=errors,
                consumable=not errors and len(rows) == len(package["candidates"]),
                whole_package_target_tokens=sum(
                    row["representation"]["target_token_count"] for row in rows
                ),
                maximum_sequence_length=MAX_SEQUENCE_LENGTH,
                tokenizer_binding_id=binding["id"],
                original_request_response_bytes_retained=True,
                truncation=False,
                training_eligible=False,
            )
            path = output / "packages" / package["registered_session_id"] / "encoded_package.json"
            write_json(path, encoded_package)
            descriptor = {
                key: encoded_package[key]
                for key in (
                    "registered_session_id",
                    "task_id",
                    "pool",
                    "group",
                    "actual_method",
                    "consumable",
                    "whole_package_target_tokens",
                )
            }
            descriptor.update(
                id=encoded_package["id"],
                path=str(path.relative_to(root)),
                sha256=sha(path.read_bytes()),
            )
            encoded_packages.append(descriptor)
            failures.extend(
                {"registered_session_id": package["registered_session_id"], **error}
                for error in errors
            )
    by_stratum = defaultdict(list)
    for package in encoded_packages:
        if package["consumable"]:
            by_stratum[package["pool"], package["task_id"], package["actual_method"]].append(
                package
            )
    ready = {group: [] for group in design.GROUPS}
    readiness = []
    for task in tasks:
        group = FAMILY_TO_SCALE_GROUP[task["family"]]
        methods = ("control",) if group == "control" else design.METHODS
        counts = {
            pool: {method: len(by_stratum[pool, task["task_id"], method]) for method in methods}
            for pool in design.POOLS
        }
        common = all(count >= 10 for pool in counts.values() for count in pool.values())
        readiness.append(
            {
                "task_id": task["task_id"],
                "group": group,
                "counts_by_pool_actual_method": counts,
                "common_AB_ready": common,
            }
        )
        if common:
            ready[group].append(task["task_id"])
    selection = design.choose_population(ready)
    chosen = []
    for task in selection["selected"]:
        methods = ("control",) if task["group"] == "control" else design.METHODS
        for pool in design.POOLS:
            for method in methods:
                rows = by_stratum[pool, task["task_id"], method][:10]
                chosen.extend(
                    {
                        **row,
                        "role": "train" if index < 8 else "heldout",
                        "within_stratum_index": index,
                    }
                    for index, row in enumerate(rows)
                )
    complete = selection["status"] == "PROSPECTIVE_POPULATION_SELECTED"
    manifest = training_runtime.record(
        "fixed_AB_material_manifest",
        status="FIXED_AB_MATERIALS_READY" if complete else "STOP_INSUFFICIENT_COMMON_AB_MATERIALS",
        collection_id=report["id"],
        collection_complete=True,
        policy_id=policy()["id"],
        source_task_order=[task["task_id"] for task in tasks],
        common_AB_readiness=readiness,
        population_selection=selection,
        packages=chosen,
        tokenizer_binding=binding,
        tokenizer_loads=tokenizer_loads,
        all_original_registered_denominators=len(entries),
        original_package_consumer_registered=True,
        loss_rule="alpha(method|task)/(40*whole_package_target_tokens)",
        Student_sessions=0,
        GPU_operations=0,
        training_started=False,
    )
    write_json(output / "representation_exclusions.json", exclusions)
    write_json(output / "representation_failures.json", failures)
    write_json(output / "encoded_package_inventory.json", encoded_packages)
    write_json(output / "material_manifest.json", manifest)
    return manifest


def update_examples(root, manifest, batch, *, pool, arm):
    """Load the exact 64 original packages for one five-task optimizer update.

    Returned coefficients multiply each target-token NLL directly. No padding,
    microbatch accumulation, package row count or global N adds another divisor.
    Heldout packages cannot enter this consumer.
    """
    checked_record(manifest, "fixed_AB_material_manifest")
    require(
        manifest["status"] == "FIXED_AB_MATERIALS_READY" and manifest["collection_complete"],
        "consumer.complete_fixed_materials",
    )
    require(pool in design.POOLS and arm in design.ARMS, "consumer.registered_pool_arm")
    require(
        len(batch["tasks"]) == 5 and len({row["task_id"] for row in batch["tasks"]}) == 5,
        "consumer.five_unique_tasks",
    )
    require(
        Counter(row["group"] for row in batch["tasks"])
        == Counter({**dict.fromkeys(design.DUAL_GROUPS, 1), "control": 2}),
        "consumer.three_distinct_dual_groups_and_two_controls",
    )
    selected = {
        (row["task_id"], row["group"]) for row in manifest["population_selection"]["selected"]
    }
    require(
        all((row["task_id"], row["group"]) in selected for row in batch["tasks"]),
        "consumer.frozen_selected_task_membership",
    )
    examples = []
    for task in batch["tasks"]:
        rows = [
            row
            for row in manifest["packages"]
            if row["pool"] == pool and row["task_id"] == task["task_id"] and row["role"] == "train"
        ]
        methods = ("control",) if task["group"] == "control" else design.METHODS
        for method in methods:
            stratum = [row for row in rows if row["actual_method"] == method]
            require(len(stratum) == 8, "consumer.eight_original_packages_per_actual_method")
            for descriptor in stratum:
                path = Path(root) / descriptor["path"]
                require(
                    sha(path.read_bytes()) == descriptor["sha256"],
                    "consumer.original_encoded_package_hash",
                )
                package = _read(Path(root).resolve(), descriptor["path"])
                checked_record(package, "encoded_original_package")
                require(
                    package["id"] == descriptor["id"]
                    and package["consumable"]
                    and package["maximum_sequence_length"] == MAX_SEQUENCE_LENGTH
                    and package["task_id"] == task["task_id"]
                    and package["group"] == task["group"]
                    and package["pool"] == pool
                    and package["actual_method"] == method,
                    "consumer.whole_consumable_original_package",
                )
                for row in package["rows"]:
                    representation = row["representation"]
                    ids = representation["input_ids"]
                    mask = representation["target_mask"]
                    labels = representation["labels"]
                    require(
                        len(ids) == len(mask) == len(labels)
                        and 0 < len(ids) <= MAX_SEQUENCE_LENGTH
                        and representation["sequence_length"] == len(ids)
                        and all(type(active) is int and active in {0, 1} for active in mask)
                        and representation["target_token_count"] > 0
                        and mask[0] == 0
                        and sum(mask[1:]) == representation["target_token_count"]
                        and all(
                            label == (token if active else -100)
                            for token, active, label in zip(ids, mask, labels, strict=True)
                        ),
                        "consumer.original_token_mask_and_labels",
                    )
                length = sum(row["representation"]["target_token_count"] for row in package["rows"])
                require(
                    length == package["whole_package_target_tokens"] and length > 0,
                    "consumer.whole_package_token_denominator",
                )
                examples.append(
                    {
                        "package_id": package["id"],
                        "task_id": task["task_id"],
                        "pool": pool,
                        "actual_method": method,
                        "whole_package_target_tokens": length,
                        "target_token_coefficient": str(
                            design.update_token_coefficient(arm, task["group"], method, length)
                        ),
                        "rows": package["rows"],
                    }
                )
    require(len(examples) == 64, "consumer.exact_64_package_update")
    return examples
