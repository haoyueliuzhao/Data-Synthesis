"""One no-gradient forward per stored row; no tokenizer or free generation."""

import argparse
import math
import time
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.model import load_student
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.weights import load_rows

from .guards import (
    artifact_guard,
    assert_unchanged,
    guard_record,
    inference_only,
    parameter_fingerprint,
)
from .plan import OUTPUT, SCORE_KIND, read_json, record, require, worker_inputs


def summarize(view, scored_rows):
    require(
        [r["row_index"] for r in scored_rows] == list(range(len(view["rows"]))),
        "diagnostic.complete_ordered_rows",
    )
    groups = defaultdict(list)
    for original, scored in zip(view["rows"], scored_rows, strict=True):
        require(
            all(
                scored[k] == original[k]
                for k in (
                    "row_index",
                    "session_label",
                    "response_kind",
                    "target_token_count",
                    "token_reference",
                )
            ),
            "diagnostic.scored_row_binding",
        )
        nlls = scored["target_nlls"]
        require(
            len(nlls) == original["target_token_count"]
            and all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0 for v in nlls),
            "diagnostic.finite_original_target_NLL",
        )
        groups[original["session_label"]].append(scored)
    packages = {}
    for package in view["packages"]:
        label = package["session_label"]
        rows = groups[label]
        require(
            {r["response_kind"] for r in rows} == {"calculate", "Final"},
            "diagnostic.exact_response_kinds",
        )
        total = sum(r["target_token_count"] for r in rows)
        require(total == package["target_token_count"], "diagnostic.original_package_normalization")
        sums = {
            kind: math.fsum(v for r in rows if r["response_kind"] == kind for v in r["target_nlls"])
            for kind in ("calculate", "Final")
        }
        counts = {
            kind: sum(r["target_token_count"] for r in rows if r["response_kind"] == kind)
            for kind in sums
        }
        packages[label] = {
            "whole_mean_nll": math.fsum(v for r in rows for v in r["target_nlls"]) / total,
            "whole_target_count": total,
            "split_means": {kind: sums[kind] / counts[kind] for kind in sums},
            "split_original_package_contributions": {kind: sums[kind] / total for kind in sums},
            "split_target_counts": counts,
            "package_id": package["package_id"],
            "class_id": package["class_id"],
        }

    def weighted(arm, field, kind=None):
        return math.fsum(
            float(Fraction(p["mass"][arm]))
            * (
                packages[p["session_label"]][field]
                if kind is None
                else packages[p["session_label"]][field][kind]
            )
            for p in view["packages"]
        )

    def contrast(field, kind=None):
        vals = {
            label: (p[field] if kind is None else p[field][kind]) for label, p in packages.items()
        }
        return vals["T_L1_03"] - (vals["T_L1_01"] + vals["T_L1_04"]) / 2

    objectives = {arm: weighted(arm, "whole_mean_nll") for arm in ("P", "Q")}
    c = contrast("whole_mean_nll")
    error = abs(objectives["Q"] - objectives["P"] - c / 36)
    require(error <= 1e-10, "diagnostic.common_objective_identity")
    splits = {
        kind: {
            "common_kind_normalized_objectives": {
                arm: weighted(arm, "split_means", kind) for arm in ("P", "Q")
            },
            "original_package_normalized_objective_contributions": {
                arm: weighted(arm, "split_original_package_contributions", kind)
                for arm in ("P", "Q")
            },
            "C_kind_normalized": contrast("split_means", kind),
            "C_original_package_contribution": contrast(
                "split_original_package_contributions", kind
            ),
        }
        for kind in ("calculate", "Final")
    }
    for arm in ("P", "Q"):
        require(
            abs(
                objectives[arm]
                - math.fsum(
                    s["original_package_normalized_objective_contributions"][arm]
                    for s in splits.values()
                )
            )
            <= 1e-10,
            "diagnostic.split_reconstructs_whole",
        )
    return {
        "packages": packages,
        "common_objectives": objectives,
        "C": c,
        "identity_absolute_error": error,
        "splits": splits,
    }


def run(root, variant):
    import torch
    import torch.nn.functional as F
    from torch.nn.attention import SDPBackend, sdpa_kernel

    started = time.perf_counter()
    with artifact_guard(root, "scoring", variant) as (access, network):
        config, identity, binding = worker_inputs(root, variant)
        prep = root / OUTPUT / "preparation"
        verify_source_snapshot(root, read_json(prep / "implementation.json"))
        view = read_json(prep / "weight_view.json")
        rows = load_rows(root, view)
        require(
            len(rows) == 36
            and sum(r["sequence_length"] for r in rows) == 232603
            and sum(r["target_token_count"] for r in rows) == 4793,
            "diagnostic.fixed_pass",
        )
        store = DurableStore(root / OUTPUT / "scoring" / variant)
        store.json("identity.json", identity)
        model, _ = load_student(
            binding,
            identity["seed"],
            trainable=False,
            adapter_path=root / identity["adapter_path"] if identity["adapter_path"] else None,
            adapter_record=identity["adapter_record"],
        )
        model.gradient_checkpointing_disable()
        before = parameter_fingerprint(model)
        store.json("parameters_before.json", before)
        scored = []
        with inference_only() as updates:
            for row in rows:
                inputs = torch.tensor([row["input_ids"]], dtype=torch.long, device="cuda:0")
                mask = torch.tensor([row["attention_mask"]], dtype=torch.long, device="cuda:0")
                positions = torch.tensor(row["logit_positions"], dtype=torch.long, device="cuda:0")
                targets = torch.tensor(row["target_ids"], dtype=torch.long, device="cuda:0")
                with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                    logits = model(
                        input_ids=inputs,
                        attention_mask=mask,
                        use_cache=False,
                        logits_to_keep=positions,
                    ).logits[0]
                require(logits.shape[0] == len(row["target_ids"]), "diagnostic.single_causal_shift")
                nlls = F.cross_entropy(logits.float(), targets, reduction="none").cpu().tolist()
                result = record(
                    "scored_original_row",
                    **{
                        k: row[k]
                        for k in (
                            "row_index",
                            "session_label",
                            "response_kind",
                            "sequence_length",
                            "target_token_count",
                            "token_reference",
                        )
                    },
                    target_nlls=nlls,
                    target_nll_sum=math.fsum(nlls),
                    configuration_id=config["id"],
                )
                store.json(f"rows/{row['row_index']:03d}.json", result)
                scored.append(result)
                print(
                    "score",
                    variant,
                    row["row_index"],
                    row["session_label"],
                    row["response_kind"],
                    flush=True,
                )
                del inputs, mask, positions, targets, logits
        after = parameter_fingerprint(model)
        assert_unchanged(before, after)
        store.json("parameters_after.json", after)
        report = record(
            "fixed_model_score",
            variant=variant,
            configuration_id=config["id"],
            weight_view_id=view["id"],
            model_identity_id=identity["id"],
            rows=36,
            target_positions=4793,
            sequence_positions=232603,
            parameter_sha256=before["sha256"],
            parameters_unchanged=True,
            **summarize(view, scored),
            elapsed_seconds=time.perf_counter() - started,
            peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),
            new_training_updates=0,
            teacher_calls=0,
            tokenizer_calls=0,
        )
        store.json("guard_report.json", guard_record("scoring", access, network, updates))
        store.json("report.json", report)
        seal_directory(store, kind=SCORE_KIND, report_id=report["id"])
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--variant", required=True)
    args = parser.parse_args()
    run(args.root.resolve(), args.variant)
