from __future__ import annotations

import argparse
import gc
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.phase1_batch_distribution_intervention import (
    BATCH_INTERVENTION_NUMERIC_SEED,
    BATCH_INTERVENTION_VERSION,
    HADAMARD_ORDER,
    _recover_centered_state_values,
    _sylvester_hadamard,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    _gradient_norm,
    _load_jsonl,
    _load_verified_gradient,
    _normalized_gradient_alignment,
    _record_gradient,
    _sha256,
    _weighted_gradient,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_distribution_intervention import (
    _apply_gradient_step,
    _rank_evidence,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_linearization_diagnostic import (
    _pearson,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _adapter_tensor_sha256,
    _baseline_lora_model,
    _evaluate,
    _load_records,
    _load_tokenizer,
    _read_json,
    _seed_everything,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

BATCH_LINEARIZATION_DIAGNOSTIC_VERSION = "finance_batch_linearization_diagnostic.v1"


def run(args: argparse.Namespace) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch
    from safetensors.torch import save_file

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    preflight = _read_json(output_dir / "preflight.json")
    intervention_report = _read_json(output_dir / "report.json")
    if plan.get("experiment_version") != BATCH_INTERVENTION_VERSION:
        raise ValueError("batch diagnostic requires a current intervention plan")
    if preflight.get("plan_hash") != plan.get("plan_hash"):
        raise ValueError("batch diagnostic preflight failed plan replay")
    if intervention_report.get("plan_hash") != plan.get("plan_hash"):
        raise ValueError("batch diagnostic report failed plan replay")
    if intervention_report.get("production_authorized") is not False:
        raise ValueError("batch diagnostic only runs after a rejected production gate")

    started = time.monotonic()
    _seed_everything(BATCH_INTERVENTION_NUMERIC_SEED + 100)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(plan["beneficiary_adapter_dir"]),
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("batch diagnostic loaded another beneficiary Adapter")
    global_artifact = plan["global_gradient_artifact"]
    global_gradient = _load_verified_gradient(
        Path(global_artifact["file"]),
        str(global_artifact["sha256"]),
    )
    learning_rate = float(preflight["selected_learning_rate"])
    _apply_gradient_step(model, global_gradient, learning_rate=learning_rate)

    source_records = _load_records(Path(plan["source_records_path"]))
    final_records = tuple(source_records[value] for value in plan["final_test_record_ids"])
    baseline_performance, baseline_loss, baseline_tokens = _evaluate(
        model,
        tokenizer,
        final_records,
    )
    if not math.isclose(
        baseline_loss,
        float(intervention_report["baseline_loss"]),
        abs_tol=1e-8,
    ) or not math.isclose(
        baseline_performance,
        float(intervention_report["baseline_performance"]),
        abs_tol=1e-8,
    ):
        raise ValueError("batch diagnostic baseline objective failed replay")
    if baseline_tokens != int(intervention_report["final_test_supervised_tokens"]):
        raise ValueError("batch diagnostic final-test token support changed")

    diagnostic_dir = output_dir / "direct_final_gradient_diagnostic"
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    record_gradients = []
    record_weights = []
    record_rows = []
    for index, record in enumerate(final_records):
        gradient, loss, supervised_tokens = _record_gradient(
            model,
            tokenizer,
            record,
            mode="objective_eval",
        )
        path = diagnostic_dir / f"final_record_{index:02d}.safetensors"
        save_file(gradient, path)
        record_gradients.append(gradient)
        record_weights.append(float(supervised_tokens))
        record_rows.append(
            {
                "record_id": record.record_id,
                "file": str(path),
                "sha256": _sha256(path),
                "loss": loss,
                "supervised_tokens": supervised_tokens,
                "gradient_norm": _gradient_norm(gradient),
            }
        )
    final_gradient = _weighted_gradient(record_gradients, record_weights)
    final_gradient_path = diagnostic_dir / "final_test_aggregate.safetensors"
    save_file(final_gradient, final_gradient_path)
    final_gradient_gpu = {
        name: value.to(device="cuda:0") for name, value in final_gradient.items()
    }
    final_gradient_norm = _gradient_norm(final_gradient_gpu)

    coordinate_rows = []
    predicted_coordinates = []
    for artifact in plan["coordinate_artifacts"]:
        coordinate = _load_verified_gradient(
            Path(artifact["file"]),
            str(artifact["sha256"]),
        )
        coordinate_gpu = {
            name: value.to(device="cuda:0") for name, value in coordinate.items()
        }
        coordinate_norm = _gradient_norm(coordinate_gpu)
        dot, cosine = _normalized_gradient_alignment(
            coordinate_gpu,
            final_gradient_gpu,
            left_norm=coordinate_norm,
            right_norm=final_gradient_norm,
        )
        predicted = learning_rate * dot
        predicted_coordinates.append(predicted)
        coordinate_rows.append(
            {
                "coordinate_index": artifact["coordinate_index"],
                "task_id": artifact["task_id"],
                "basis_index": artifact["basis_index"],
                "directional_dot": dot,
                "cosine": cosine,
                "first_order_predicted_coordinate": predicted,
                "observed_coordinate": intervention_report["coordinate_values"][
                    artifact["coordinate_index"]
                ],
            }
        )
        del coordinate, coordinate_gpu

    target_by_state = {
        str(row["state_id"]): row for row in intervention_report["state_rows"]
    }
    state_rows: list[dict[str, Any]] = []
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in plan["task_rows"]:
        first, second = task["coordinate_indices"]
        predicted_states = _recover_centered_state_values(
            predicted_coordinates[first],
            predicted_coordinates[second],
            task_marginal=float(task["task_marginal"]),
        )
        for state, predicted in zip(task["states"], predicted_states, strict=True):
            target = target_by_state[str(state["state_id"])]
            row = {
                "task_id": task["task_id"],
                "task_type": task["task_type"],
                "state_id": state["state_id"],
                "strategy": state["strategy"],
                "direct_final_gradient_contribution": predicted,
                "recovered_centered_contribution": target[
                    "recovered_centered_contribution"
                ],
            }
            state_rows.append(row)
            grouped[str(task["task_id"])].append(row)
    rank_evidence = _rank_evidence(
        grouped,
        estimator_field="direct_final_gradient_contribution",
        target_field="recovered_centered_contribution",
        seed=BATCH_INTERVENTION_NUMERIC_SEED + 110,
    )

    worker_rows = [
        row
        for path in sorted((output_dir / "workers").glob("partition_*.jsonl"))
        for row in _load_jsonl(path)
        if row.get("role") == "orthogonal_design"
    ]
    worker_by_index = {int(row["design_row_index"]): row for row in worker_rows}
    if len(worker_by_index) != HADAMARD_ORDER:
        raise ValueError("batch diagnostic intervention rows are incomplete")
    hadamard = _sylvester_hadamard(HADAMARD_ORDER)
    predicted_design_rows = [
        sum(
            hadamard[row][column] * predicted_coordinates[column]
            for column in range(len(predicted_coordinates))
        )
        for row in range(HADAMARD_ORDER)
    ]
    observed_design_rows = [
        float(worker_by_index[row]["central_directional_derivative"])
        for row in range(HADAMARD_ORDER)
    ]
    mechanism_consistent = bool(rank_evidence["passes_rank_gate"])
    report: dict[str, Any] = {
        "diagnostic_version": BATCH_LINEARIZATION_DIAGNOSTIC_VERSION,
        "role": "post_hoc_direct_final_gradient_mechanism_diagnostic_only",
        "cannot_authorize_production": True,
        "plan_hash": plan["plan_hash"],
        "preflight_hash": preflight["preflight_hash"],
        "intervention_report_hash": intervention_report["report_hash"],
        "selected_learning_rate": learning_rate,
        "baseline_adapter_tensor_sha256": _adapter_tensor_sha256(model),
        "baseline_loss": baseline_loss,
        "baseline_performance": baseline_performance,
        "final_test_supervised_tokens": baseline_tokens,
        "final_test_record_gradients": record_rows,
        "final_test_aggregate_gradient": {
            "file": str(final_gradient_path),
            "sha256": _sha256(final_gradient_path),
            "gradient_norm": final_gradient_norm,
            "weighting": "supervised_token_count",
        },
        "coordinate_count": len(coordinate_rows),
        "state_count": len(state_rows),
        "task_count": len(grouped),
        "coordinate_pearson": _pearson(
            predicted_coordinates,
            [float(row["observed_coordinate"]) for row in coordinate_rows],
        ),
        "design_row_pearson": _pearson(predicted_design_rows, observed_design_rows),
        "rank_evidence": rank_evidence,
        "mechanism_consistent": mechanism_consistent,
        "diagnostic_interpretation": (
            "proxy_validation_support_not_representative_of_final_objective"
            if mechanism_consistent
            else "first_order_gradient_projection_not_predictive_at_identifiable_scale"
        ),
        "coordinate_rows": coordinate_rows,
        "state_rows": state_rows,
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
        "claim_boundary": (
            "This diagnostic directly differentiates the untouched final-test objective after "
            "observing the failed batch intervention. It localizes mechanism error only and "
            "must not serve as an estimator, promotion gate, or scale selector."
        ),
    }
    report["diagnostic_hash"] = canonical_hash(
        report,
        prefix="finance_batch_linearization_diagnostic:",
    )
    _write_json(diagnostic_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    del model, global_gradient, final_gradient, final_gradient_gpu, record_gradients
    gc.collect()
    torch.cuda.empty_cache()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Localize a failed Scheme 3 batch intervention with direct final gradients"
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gpu-id", type=int, default=0)
    return parser


def main() -> None:
    run(_parser().parse_args())


if __name__ == "__main__":
    main()
