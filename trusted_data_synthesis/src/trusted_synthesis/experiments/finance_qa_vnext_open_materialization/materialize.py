"""Original complete-session archives and positive same-interaction representations."""

from collections import Counter

from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    save,
    write,
)

from .plan import SOURCE, record, require, sha
from .source import positive_candidate
from .tokens import encode_candidate


def copy_original(source, destination, relative):
    require(source.is_file() and not source.is_symlink(), "archive.original_regular_file")
    raw = source.read_bytes()
    write(destination, relative, raw)
    require((destination / relative).read_bytes() == raw, "archive.byte_identity")
    return {"path": relative, "bytes": len(raw), "sha256": sha(raw)}


def export(
    root, destination, sessions, valid, projections, measurement, binding, policy, tokenizer
):
    public_members = []
    for path in sorted((root / SOURCE / "preparation/public").glob("*.json")):
        public_members.append(copy_original(path, destination, "public/" + path.name))
    archives = {}
    # Preserve every original registration, including invalid/undetermined ones.
    for label, session in sorted(sessions.items()):
        members = []
        for source in sorted(session["directory"].rglob("*")):
            if source.is_file():
                name = source.relative_to(session["directory"]).as_posix()
                members.append(copy_original(source, destination, f"sessions/{label}/{name}"))
        archives[label] = record(
            "original_session_archive",
            session_label=label,
            population=session["row"]["arm"],
            task_key=session["row"]["task_key"],
            original_closeout_row=session["row"],
            source_session_manifest_id=session["session_manifest_id"],
            members=members,
            original_bytes_preserved=True,
        )
    save(
        destination,
        "archives.json",
        record("original_archives", public_members=public_members, sessions=archives),
    )
    projection_by_label = {p["session_label"]: p for p in projections}
    bundles, rows = [], []
    for label, session in sorted(valid.items()):
        candidates, representations, row_paths = [], [], []
        for turn in session["turns"]:
            candidate = positive_candidate(session, turn)
            if candidate is None:
                continue
            index = candidate["response_index"]
            representation = encode_candidate(candidate, binding, policy, tokenizer)
            prefix = f"positive/{label}/{index:03d}"
            save(destination, prefix + ".candidate.json", candidate)
            write(destination, prefix + ".target.raw", turn["raw"])
            save(destination, prefix + ".tokens.json", representation)
            require(
                (destination / (prefix + ".target.raw")).read_bytes() == turn["raw"],
                "export.target_byte_identity",
            )
            candidates.append(candidate["id"])
            representations.append(representation)
            row_paths.append(prefix)
        projection = projection_by_label[label]
        package = record(
            "whole_session_supervision_package",
            population=session["row"]["arm"],
            task_key=session["row"]["task_key"],
            session_label=label,
            source_closeout_id=session["row"]["id"],
            original_archive_id=archives[label]["id"],
            behavior_projection_id=projection["id"],
            behavior_mapping_status=projection["status"],
            behavior_key=projection["behavior_key"],
            class_id=measurement["session_class_ids"][label],
            positive_candidate_ids=candidates,
            token_representation_ids=[r["id"] for r in representations],
            positive_row_paths=row_paths,
            original_response_count=len(session["turns"]),
            excluded_error_response_indices=[
                t["binding"]["response_index"]
                for t in session["turns"]
                if t["event"]["protocol_error"]
            ],
            all_later_inputs_retain_original_errors=True,
            whole_package_token_consumable=bool(representations)
            and all(r["consumable_token_representation"] for r in representations),
            package_weight=None,
            class_weight=None,
            task_weight=None,
            training_distribution_implemented=False,
        )
        save(destination, f"packages/{label}.json", package)
        bundles.append(package)
        for candidate_id, representation, prefix in zip(
            candidates, representations, row_paths, strict=True
        ):
            rows.append(
                {
                    "population": package["population"],
                    "task_key": package["task_key"],
                    "session_label": label,
                    "class_id": package["class_id"],
                    "behavior_projection_id": projection["id"],
                    "package_id": package["id"],
                    "candidate_id": candidate_id,
                    "representation_id": representation["id"],
                    "path_prefix": prefix,
                    "response_index": representation["response_index"],
                    "sequence_length": representation["sequence_length"],
                    "prompt_token_count": representation["prompt_token_count"],
                    "target_token_count": representation["target_token_count"],
                    "consumable": representation["consumable_token_representation"],
                    "weight": None,
                }
            )
    totals = {}
    for population in ("T", "A"):
        package_subset = [p for p in bundles if p["population"] == population]
        row_subset = [r for r in rows if r["population"] == population]
        lengths = [r["sequence_length"] for r in row_subset]
        totals[population] = {
            "registered_archives": sum(a["population"] == population for a in archives.values()),
            "valid_packages": len(package_subset),
            "positive_rows": len(row_subset),
            "consumable_rows": sum(r["consumable"] for r in row_subset),
            "consumable_whole_packages": sum(
                p["whole_package_token_consumable"] for p in package_subset
            ),
            "error_responses_retained_not_positive": sum(
                len(p["excluded_error_response_indices"]) for p in package_subset
            ),
            "sequence_length_min": min(lengths) if lengths else None,
            "sequence_length_max": max(lengths) if lengths else None,
            "sequence_tokens_total": sum(lengths),
            "positive_target_tokens_total": sum(r["target_token_count"] for r in row_subset),
            "packages_by_task": dict(
                sorted(Counter(p["task_key"] for p in package_subset).items())
            ),
        }
    require(
        totals["T"]["positive_rows"] == 20 and totals["A"]["positive_rows"] == 4,
        "export.fixed_positive_count",
    )
    require(totals["T"]["error_responses_retained_not_positive"] == 2, "export.original_T_errors")
    index = record(
        "open_materialization_index",
        original_registration_count=len(archives),
        valid_package_count=len(bundles),
        positive_row_count=len(rows),
        by_population=totals,
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
        excluded_sessions=[
            s["row"] for s in sessions.values() if not s["row"]["formula_driven_trace_verified"]
        ],
        weights_assigned=False,
        task_marginal_implemented=False,
        no_resampling_for_missing_or_unfit_support=True,
    )
    save(destination, "index.json", index)
    return index
