"""Content-addressed original new-session references and exact positive packages.

All registered online directories remain in this experiment's tree. A missing or
unsealed unknown-session artifact is explicitly recorded, never completed by a
Host-created response. Only joint-valid new sessions are converted to targets.
"""

from collections import Counter
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    save,
    write,
)

from .plan import OUTPUT, record, require, sha
from .plan import policy as study_policy
from .source import content_identity, positive_candidate
from .tokens import assets, encode_candidate, load_bound_assets


def archive_reference(root, row):
    """Inventory available bytes, including partial unknown sessions, without copying them."""
    root = Path(root)
    label = row["label"]
    require(
        isinstance(label, str)
        and label == Path(label).name
        and label not in {".", ".."}
        and row["arm"] == "T",
        "new_archive.registration_path",
    )
    content_identity(row, "new_archive.source_row_identity")
    relative = Path(OUTPUT) / "online/sessions" / label
    directory = root / relative
    require(not directory.is_symlink(), "new_archive.no_directory_symlink")
    members = []
    if directory.exists():
        require(directory.is_dir(), "new_archive.source_directory")
        for path in sorted(directory.rglob("*")):
            require(not path.is_symlink(), "new_archive.no_member_symlink")
            if not path.is_file():
                continue
            require(path.resolve().is_relative_to(directory.resolve()), "new_archive.member_scope")
            raw = path.read_bytes()
            members.append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "bytes": len(raw),
                    "sha256": sha(raw),
                }
            )
    sealed = manifest(directory) if (directory / "manifest.json").is_file() else None
    require(
        not row["formula_driven_trace_verified"] or sealed is not None,
        "new_archive.valid_session_must_have_original_manifest",
    )
    return record(
        "new_support_session_archive_reference",
        population="T",
        task_key=row["task_key"],
        session_label=label,
        source_directory=relative.as_posix(),
        original_closeout_row=row,
        source_session_manifest_id=sealed["id"] if sealed else None,
        source_session_manifest_verified=sealed is not None,
        directory_present=directory.is_dir(),
        available_members=members,
        available_member_count=len(members),
        available_bytes=sum(member["bytes"] for member in members),
        archive_status="sealed_original_session" if sealed else "partial_or_not_started_unsealed",
        retained_in_same_experiment_online_tree=True,
        source_bytes_not_copied_or_rewritten=True,
        missing_response_or_event_fabricated=False,
        source_validity_unchanged=True,
    )


def _nonpositive(turn):
    event = turn["event"]
    if event["protocol_error"] is not None:
        reason = "protocol_or_json_error"
    elif event["tool_call"] is not None and event["tool_call"]["output"]["status"] != "ok":
        reason = "failed_tool_request"
    else:
        reason = "outside_frozen_positive_response_types"
    return {
        "response_index": turn["binding"]["response_index"],
        "interaction_binding_id": turn["binding"]["id"],
        "raw_response_sha256": turn["binding"]["raw_response_sha256"],
        "reason": reason,
        "original_protocol_error": event["protocol_error"],
        "tool_call_id": event["tool_call"]["id"] if event["tool_call"] else None,
        "original_bytes_and_later_input_history_retained": True,
        "positive_loss_assigned": False,
    }


def export(root, destination, sessions, source_rows, projections, measurement):
    """Materialize only this batch, grouping every positive row by whole original session.

    ``sessions`` contains the result of bind_session for every joint-valid new row,
    including behavior-UNDETERMINED sessions. ``source_rows`` contains all registered
    new outcomes. No original failure or unknown needs a fictitious bound turn.
    """
    root, destination = Path(root), Path(destination)
    require(
        destination.resolve().is_relative_to((root / OUTPUT).resolve()),
        "new_export.destination_is_new_experiment",
    )
    require(isinstance(source_rows, list) and bool(source_rows), "new_export.all_source_rows")
    by_label = {row["label"]: row for row in source_rows}
    require(len(by_label) == len(source_rows), "new_export.unique_registrations")
    valid_labels = {
        label for label, row in by_label.items() if row["formula_driven_trace_verified"]
    }
    require(set(sessions) == valid_labels, "new_export.exact_valid_session_population")
    projection_rows = list(projections.values()) if isinstance(projections, dict) else projections
    projection_by_label = {
        projection["session_label"]: projection for projection in projection_rows
    }
    require(
        len(projection_by_label) == len(projection_rows)
        and valid_labels.issubset(projection_by_label)
        and valid_labels.issubset(measurement["session_class_ids"]),
        "new_export.projection_and_class_indices",
    )
    archives = {label: archive_reference(root, row) for label, row in by_label.items()}
    save(
        destination,
        "archives.json",
        record(
            "new_support_archive_index",
            original_registration_count=len(source_rows),
            sessions=archives,
            online_source_root=OUTPUT + "/online",
            all_registration_outcomes_retained=True,
        ),
    )
    binding, policy, tokenizer = load_bound_assets(root)
    save(destination, "tokenizer_binding.json", binding)
    save(destination, "representation_policy.json", policy)
    bundles, rows = [], []
    for label in by_label:
        if label not in sessions:
            continue
        session = sessions[label]
        require(session["row"] == by_label[label], "new_export.original_source_row")
        require(
            session["session_manifest_id"] == archives[label]["source_session_manifest_id"],
            "new_export.bound_archive",
        )
        projection = projection_by_label[label]
        content_identity(projection, "new_export.projection_identity")
        require(
            projection["source_closeout_id"] == session["row"]["id"]
            and projection["task_key"] == session["row"]["task_key"]
            and projection["population"] == "T",
            "new_export.same_behavior_source",
        )
        candidates, representations, row_paths, nonpositive = [], [], [], []
        for turn in session["turns"]:
            index = turn["binding"]["response_index"]
            save(destination, f"interactions/{label}/{index:03d}.json", turn["binding"])
            candidate = positive_candidate(session, turn)
            if candidate is None:
                nonpositive.append(_nonpositive(turn))
                continue
            representation = encode_candidate(candidate, binding, policy, tokenizer)
            prefix = f"positive/{label}/{index:03d}"
            save(destination, prefix + ".candidate.json", candidate)
            write(destination, prefix + ".target.raw", turn["raw"])
            save(destination, prefix + ".tokens.json", representation)
            require(
                (destination / (prefix + ".target.raw")).read_bytes() == turn["raw"],
                "new_export.exact_target_bytes",
            )
            candidates.append(candidate)
            representations.append(representation)
            row_paths.append(prefix)
        positive_indices = [candidate["response_index"] for candidate in candidates]
        nonpositive_indices = [item["response_index"] for item in nonpositive]
        require(
            sorted(positive_indices + nonpositive_indices) == list(range(len(session["turns"])))
            and set(positive_indices).isdisjoint(nonpositive_indices),
            "new_export.complete_response_partition",
        )
        class_id = measurement["session_class_ids"][label]
        require(
            projection["status"] == "MAPPED" or class_id is None, "new_export.unmapped_not_assigned"
        )
        package = record(
            "new_support_whole_session_package",
            population="T",
            task_key=session["row"]["task_key"],
            session_label=label,
            source_closeout_id=session["row"]["id"],
            original_archive_reference_id=archives[label]["id"],
            original_source_directory=archives[label]["source_directory"],
            behavior_projection_id=projection["id"],
            behavior_mapping_status=projection["status"],
            behavior_key=projection.get("behavior_key"),
            class_id=class_id,
            all_interaction_binding_ids=[turn["binding"]["id"] for turn in session["turns"]],
            positive_candidate_ids=[candidate["id"] for candidate in candidates],
            token_representation_ids=[representation["id"] for representation in representations],
            positive_response_indices=positive_indices,
            positive_response_kinds=dict(
                sorted(Counter(candidate["response_kind"] for candidate in candidates).items())
            ),
            positive_row_paths=row_paths,
            original_response_count=len(session["turns"]),
            nonpositive_responses=nonpositive,
            positive_target_policy=study_policy()["positive_targets"],
            all_later_inputs_retain_original_errors_and_failed_tools=True,
            independent_public_explanations_preserved_as_original_targets=True,
            whole_package_token_consumable=bool(representations)
            and all(
                representation["consumable_token_representation"]
                for representation in representations
            ),
            unfit_response_indices=[
                representation["response_index"]
                for representation in representations
                if not representation["consumable_token_representation"]
            ],
            original_validity_unchanged=True,
            package_weight=None,
            class_weight=None,
            task_weight=None,
            training_distribution_implemented=False,
        )
        save(destination, f"packages/{label}.json", package)
        bundles.append(package)
        for candidate, representation, prefix in zip(
            candidates, representations, row_paths, strict=True
        ):
            rows.append(
                {
                    "population": "T",
                    "task_key": package["task_key"],
                    "session_label": label,
                    "class_id": class_id,
                    "behavior_projection_id": projection["id"],
                    "package_id": package["id"],
                    "candidate_id": candidate["id"],
                    "representation_id": representation["id"],
                    "path_prefix": prefix,
                    "response_index": representation["response_index"],
                    "response_kind": candidate["response_kind"],
                    "sequence_length": representation["sequence_length"],
                    "prompt_token_count": representation["prompt_token_count"],
                    "target_token_count": representation["target_token_count"],
                    "consumable": representation["consumable_token_representation"],
                    "weight": None,
                }
            )
    require(
        tokenizer.chat_template == binding["chat_template"]
        and assets._read_members(Path(binding["directory"]))[0] == binding["members"],
        "new_export.tokenizer_assets_unchanged",
    )
    require(
        {label: archive_reference(root, by_label[label]) for label in by_label} == archives,
        "new_export.online_source_bytes_unchanged",
    )
    lengths = [row["sequence_length"] for row in rows]
    totals = {
        "registered_archives": len(archives),
        "sealed_original_session_archives": sum(
            archive["source_session_manifest_verified"] for archive in archives.values()
        ),
        "partial_or_not_started_archives": sum(
            not archive["source_session_manifest_verified"] for archive in archives.values()
        ),
        "valid_packages": len(bundles),
        "positive_rows": len(rows),
        "positive_rows_by_response_kind": dict(
            sorted(Counter(row["response_kind"] for row in rows).items())
        ),
        "consumable_rows": sum(row["consumable"] for row in rows),
        "unfit_rows": sum(not row["consumable"] for row in rows),
        "consumable_whole_packages": sum(
            package["whole_package_token_consumable"] for package in bundles
        ),
        "nonpositive_responses_retained": sum(
            len(package["nonpositive_responses"]) for package in bundles
        ),
        "nonpositive_by_reason": dict(
            sorted(
                Counter(
                    item["reason"]
                    for package in bundles
                    for item in package["nonpositive_responses"]
                ).items()
            )
        ),
        "sequence_length_min": min(lengths) if lengths else None,
        "sequence_length_max": max(lengths) if lengths else None,
        "sequence_tokens_total": sum(lengths),
        "positive_target_tokens_total": sum(row["target_token_count"] for row in rows),
        "packages_by_task": dict(
            sorted(Counter(package["task_key"] for package in bundles).items())
        ),
    }
    index = record(
        "new_support_materialization_index",
        original_registration_count=len(archives),
        valid_package_count=len(bundles),
        positive_row_count=len(rows),
        by_population={"T": totals},
        packages=[
            {
                key: package[key]
                for key in (
                    "id",
                    "population",
                    "task_key",
                    "session_label",
                    "class_id",
                    "whole_package_token_consumable",
                )
            }
            for package in bundles
        ],
        rows=rows,
        excluded_sessions=[row for row in source_rows if not row["formula_driven_trace_verified"]],
        all_new_registrations_and_available_raw_bytes_retained=True,
        new_batch_only=True,
        old_trajectories_retokenized=False,
        tokenizer_loaded=True,
        weights_assigned=False,
        task_marginal_implemented=False,
        no_resampling_for_missing_or_unfit_support=True,
        no_student_or_training=True,
    )
    save(destination, "index.json", index)
    return index
