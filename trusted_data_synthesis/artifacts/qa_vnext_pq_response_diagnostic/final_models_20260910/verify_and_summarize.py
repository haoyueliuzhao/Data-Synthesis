"""Read-only release checks and tabular summaries; no model loading or rescoring."""

import math
from collections import Counter
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_directory,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_response_diagnostic.plan import (
    ASSESSMENT_KIND,
    CLOSEOUT_KIND,
    EXECUTION_KIND,
    GENERATION_KIND,
    OUTPUT,
    PREPARATION_KIND,
    SCORE_KIND,
    TRAINED,
    VARIANTS,
    read_json,
    record,
    reference,
    require,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_response_diagnostic.stage import (
    check_preparation,
)


def tsv(header, rows):
    return ("\n".join("\t".join(map(str, row)) for row in [header, *rows]) + "\n").encode()


def main():
    root = Path.cwd().resolve()
    output = root / OUTPUT
    check_preparation(root)
    directories = {
        "preparation": PREPARATION_KIND,
        "execution": EXECUTION_KIND,
        "assessment": ASSESSMENT_KIND,
        "closeout": CLOSEOUT_KIND,
        "manual_review": "pq_response_explicit_review_manifest",
        "side_annotation_correction": "pq_response_side_label_correction_manifest",
        **{f"scoring/{v}": SCORE_KIND for v in VARIANTS},
        **{f"generation/{v}": GENERATION_KIND for v in TRAINED},
    }
    manifests = {}
    for relative, kind in directories.items():
        manifest = verify_directory(output / relative, kind=kind)
        manifests[relative] = {
            "id": manifest["id"],
            "reference": reference(root, f"{OUTPUT}/{relative}/manifest.json"),
            "member_count": len(manifest["members"]),
        }
    comparison = read_json(output / "assessment/score_comparison.json")
    closeout = read_json(output / "closeout/report.json")
    parameters, score_rows, score_targets, score_sequences = [], 0, 0, 0
    for phase, variants in (("scoring", VARIANTS), ("generation", TRAINED)):
        for variant in variants:
            directory = output / phase / variant
            before = read_json(directory / "parameters_before.json")
            after = read_json(directory / "parameters_after.json")
            report = read_json(directory / "report.json")
            guards = read_json(directory / "guard_report.json")
            require(
                before == after and before["sha256"] == report["parameter_sha256"],
                "release.exact_parameter_record_equality",
            )
            require(
                all(
                    not any(guards[k].values())
                    for k in ("artifact_calls", "network_calls", "training_calls")
                ),
                "release.no_forbidden_calls",
            )
            parameters.append(
                {
                    "phase": phase,
                    "variant": variant,
                    "sha256": before["sha256"],
                    "parameters": before["parameter_count"],
                    "bytes": before["parameter_bytes"],
                    "named_tensors": before["named_tensors"],
                    "unchanged_including_versions": True,
                }
            )
            if phase == "scoring":
                rows = [read_json(directory / f"rows/{i:03d}.json") for i in range(36)]
                score_rows += len(rows)
                score_targets += sum(len(row["target_nlls"]) for row in rows)
                score_sequences += sum(row["sequence_length"] for row in rows)
                require(
                    all(math.fsum(row["target_nlls"]) == row["target_nll_sum"] for row in rows),
                    "release.actual_serialized_target_sums",
                )
            else:
                require(
                    before["sha256"] == comparison["models"][variant]["parameter_sha256"],
                    "release.same_fixed_model_across_phases",
                )
    require(
        (score_rows, score_targets, score_sequences) == (252, 33551, 1628221),
        "release.actual_fixed_scoring_workload",
    )
    private = read_json(output / "preparation/private/L1.json")
    session_rows, finish_reasons, response_hashes = [], Counter(), Counter()
    for variant in TRAINED:
        result = read_json(output / f"generation/{variant}/sessions/L1/result.json")
        audit = read_json(output / f"assessment/audits/{variant}.json")
        grade, route = closeout["grades"][variant], closeout["routes"][variant]
        component = route["components"][0]
        args = audit["calculations"][0]["original_arguments"]
        require(
            component["model_declared_sources"] == args["sources"],
            "release.actual_declared_sources_never_repaired",
        )
        numeric_bindings_match = all(
            str(args["variables"][name]) == private["facts"][fact]["value"]
            for name, fact in args["sources"].items()
        )
        require(
            numeric_bindings_match == (component["model_source_binding_status"] == "PASS"),
            "release.factual_source_value_conflict_check",
        )
        require(
            not route["valid_complete_trajectory_route"] or numeric_bindings_match,
            "release.invalid_sources_not_promoted_by_reference_structure",
        )
        require(
            result["origin"] == "local_student_generation"
            and result["model_requests"] == len(result["attempts"]) == 2
            and result["tool_calls"] == 1
            and result["terminal"] == "model_final",
            "release.actual_local_complete_session_counts",
        )
        for attempt in result["attempts"]:
            require(
                attempt["generation_invoked"] is True
                and attempt["generated_token_count"] == len(attempt["generated_token_ids"])
                and attempt["is_HTTP_response"] is False,
                "release.real_local_generation_accounting",
            )
            finish_reasons[attempt["finish_reason"]] += 1
            response_hashes[attempt["raw_response_sha256"]] += 1
        session_rows.append(
            {
                "variant": variant,
                "responses": result["model_requests"],
                "tools": result["tool_calls"],
                "prompt_positions": sum(a["prompt_token_count"] for a in result["attempts"]),
                "generated_tokens": sum(a["generated_token_count"] for a in result["attempts"]),
                "answer": grade["task_answer_status"],
                "trace": grade["trace_status"],
                "actual_expression": audit["calculations"][0]["original_expression"],
                "source_bindings": component["model_source_binding_status"],
                "valid_route": route["valid_complete_trajectory_route"],
            }
        )
    require(not list(output.rglob("*.safetensors")), "release.no_new_adapter_file")
    store = DurableStore(output / "release_summary")
    store.write(
        "common_objectives.tsv",
        tsv(
            ["model", "L_P", "L_Q", "C_whole", "C_calculate", "C_Final"],
            [
                [
                    v,
                    comparison["models"][v]["common_objectives"]["P"],
                    comparison["models"][v]["common_objectives"]["Q"],
                    comparison["models"][v]["C"],
                    comparison["models"][v]["splits"]["calculate"]["C_kind_normalized"],
                    comparison["models"][v]["splits"]["Final"]["C_kind_normalized"],
                ]
                for v in VARIANTS
            ],
        ),
    )
    store.write(
        "L1_package_nll.tsv",
        tsv(
            ["model", "package", "whole_NLL", "calculate_NLL", "Final_NLL", "whole_targets"],
            [
                [
                    v,
                    label,
                    p["whole_mean_nll"],
                    p["split_means"]["calculate"],
                    p["split_means"]["Final"],
                    p["whole_target_count"],
                ]
                for v in VARIANTS
                for label, p in comparison["models"][v]["packages"].items()
                if label.startswith("T_L1_")
            ],
        ),
    )
    store.write(
        "paired_response.tsv",
        tsv(
            [
                "seed",
                "delta_L_P",
                "delta_L_Q",
                "delta_C",
                "delta_C_calculate",
                "delta_C_Final",
                "delta_R",
                "delta_D_mean",
            ],
            [
                [
                    pair["seed"],
                    pair["Q_minus_P_common_objectives"]["P"],
                    pair["Q_minus_P_common_objectives"]["Q"],
                    pair["delta_C"],
                    pair["split_delta_C"]["calculate"],
                    pair["split_delta_C"]["Final"],
                    comparison["models"][f"Q_{pair['seed']}"]["packages"]["T_L1_03"][
                        "whole_mean_nll"
                    ]
                    - comparison["models"][f"P_{pair['seed']}"]["packages"]["T_L1_03"][
                        "whole_mean_nll"
                    ],
                    math.fsum(
                        comparison["models"][f"Q_{pair['seed']}"]["packages"][label][
                            "whole_mean_nll"
                        ]
                        - comparison["models"][f"P_{pair['seed']}"]["packages"][label][
                            "whole_mean_nll"
                        ]
                        for label in ("T_L1_01", "T_L1_04")
                    )
                    / 2,
                ]
                for pair in comparison["pairs"]
            ],
        ),
    )
    store.json("new_L1_sessions.json", session_rows)
    store.json("parameter_integrity.json", parameters)
    report = record(
        "verified_response_release",
        closeout_id=closeout["id"],
        manifests=manifests,
        verified_sealed_directories=len(manifests),
        all_parameter_phase_checks=13,
        before_after_parameter_records=26,
        all_parameter_bytes_and_versions_unchanged=True,
        same_score_and_generation_fixed_parameters=True,
        score_rows=score_rows,
        score_target_positions=score_targets,
        score_sequence_positions=score_sequences,
        new_L1_sessions=len(session_rows),
        local_response_generations=sum(r["responses"] for r in session_rows),
        local_tool_calls=sum(r["tools"] for r in session_rows),
        generation_prompt_positions=sum(r["prompt_positions"] for r in session_rows),
        generated_tokens_including_actual_EOS=sum(r["generated_tokens"] for r in session_rows),
        generation_finish_reasons=dict(finish_reasons),
        distinct_generated_public_texts=len(response_hashes),
        source_value_bindings_PASS=sum(r["source_bindings"] == "PASS" for r in session_rows),
        new_Student_calls_by_this_release_script=0,
        teacher_calls=0,
        new_training_updates=0,
        artifact_scripts={
            name: reference(root, f"{OUTPUT}/{name}")
            for name in (
                "assess_with_side_labels.py",
                "build_explicit_reviews.py",
                "verify_and_summarize.py",
            )
        },
        worker_logs=[
            reference(root, p.relative_to(root).as_posix())
            for p in sorted((output / "worker_logs").iterdir())
            if p.is_file()
        ],
        scientific_result=(
            "All three paired fixed-text relative-fitting contrasts improve under Q; "
            "calculate and Final contrasts both improve. No observed greedy movement-route "
            "switch: all six execute 134-116. Five have explicit source-value conflicts; "
            "only P47 is a complete valid trajectory. No new transfer or class-probability claim."
        ),
    )
    store.json("report.json", report)
    seal_directory(store, kind="pq_response_release_summary_manifest", report_id=report["id"])
    print(report["id"], flush=True)


if __name__ == "__main__":
    main()
