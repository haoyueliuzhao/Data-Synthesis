"""Retain exact original conditional packages; no tokenizer, weights or Student representation."""

from collections import Counter

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest

from .plan import OUTPUT, record, require, sha
from .source import positive_candidate


def export(root, store, rows, sessions, measurement):
    packages, archives = [], []
    for row in rows:
        label = row["label"]
        directory = root / OUTPUT / "online/sessions" / label
        members = []
        for path in sorted(directory.rglob("*")) if directory.exists() else []:
            require(not path.is_symlink(), "archive.no_symlink")
            if path.is_file():
                raw = path.read_bytes()
                members.append(
                    {
                        "path": path.relative_to(directory).as_posix(),
                        "bytes": len(raw),
                        "sha256": sha(raw),
                    }
                )
        sealed = manifest(directory) if (directory / "manifest.json").is_file() else None
        archive = record(
            "original_conditional_session_archive",
            label=label,
            arm=row["arm"],
            task_key=row["task_key"],
            source_directory=str(directory.relative_to(root)),
            members=members,
            session_manifest_id=sealed["id"] if sealed else None,
            missing_data_or_response_not_fabricated=True,
            original_qualification=row["trace_status"],
        )
        archives.append(archive)
        store.json(f"raw_packages/archives/{label}.json", archive)
        if not row["formula_driven_trace_verified"]:
            continue
        session = sessions[label]
        candidates, nonpositive = [], []
        for turn in session["turns"]:
            candidate = positive_candidate(session, turn)
            if candidate is None:
                nonpositive.append(
                    {
                        "response_index": turn["event"]["response_index"],
                        "raw_sha256": sha(turn["raw"]),
                        "reason": "original_protocol_error_or_failed_tool",
                        "retained_in_later_original_history": True,
                    }
                )
                continue
            prefix = f"raw_packages/positive/{label}/{candidate['response_index']:03d}"
            store.json(prefix + ".candidate.json", candidate)
            store.write(prefix + ".target.raw", turn["raw"])
            candidates.append(
                {
                    "candidate_id": candidate["id"],
                    "path_prefix": prefix,
                    "response_index": candidate["response_index"],
                    "response_kind": candidate["response_kind"],
                    "original_request_sha256": candidate["request_sha256"],
                    "raw_target_sha256": candidate["raw_response_sha256"],
                    "prefix_has_original_condition_instruction": True,
                }
            )
        require(
            len(candidates) + len(nonpositive) == len(session["turns"]),
            "archive.every_original_response_accounted",
        )
        package = record(
            "unweighted_original_conditional_package",
            label=label,
            arm=row["arm"],
            task_key=row["task_key"],
            archive_id=archive["id"],
            class_id=measurement["session_class_ids"][label],
            positive_responses=candidates,
            nonpositive_responses=nonpositive,
            actual_condition_prefix_removed_or_rewritten=False,
            original_session_and_final_unchanged=True,
            positive_kind_counts=dict(Counter(c["response_kind"] for c in candidates)),
            token_consumability="NOT_MEASURED",
            tokenizer_loaded=False,
            training_weights_assigned=False,
            training_distribution_instantiated=False,
        )
        packages.append(package)
        store.json(f"raw_packages/packages/{label}.json", package)
    index = record(
        "original_conditional_package_index",
        registered_original_archives=len(archives),
        valid_original_packages=len(packages),
        positive_response_count=sum(len(p["positive_responses"]) for p in packages),
        packages=packages,
        archive_ids=[a["id"] for a in archives],
        tokenizer_loaded=False,
        Student_or_training=False,
        conditions_not_pooled=True,
        selection_not_performed=True,
        token_consumability="NOT_MEASURED",
        original_conditional_prefixes_preserved=True,
    )
    store.json("raw_packages/index.json", index)
    return index
