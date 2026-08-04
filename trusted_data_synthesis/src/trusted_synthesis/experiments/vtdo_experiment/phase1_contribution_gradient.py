from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import multiprocessing
import os
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from trusted_synthesis.core.vtdo import (
    ConditionalTrajectoryDistribution,
    contribution_current_distribution_hash,
    contribution_distribution_contract_hash,
)
from trusted_synthesis.experiments.vtdo_experiment.contribution_validation import (
    _cluster_bootstrap_interval,
    _spearman,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    AcceptedFinanceState,
    FinanceTaskStateArtifact,
    LineageStrategy,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_population import (
    PENALTY_SENSITIVITY_GRID,
    _pairwise_concordance,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    MAX_SEQUENCE_LENGTH,
    _adapter_tensor_sha256,
    _baseline_lora_model,
    _batch,
    _encode_record,
    _load_records,
    _load_tokenizer,
    _read_json,
    _record_from_state,
    _seed_everything,
    _sharded_baseline_lora_model,
    _validated_hf_device_map,
    _write_json,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import (
    GradientStateRealization,
    VTDOTrainingRecord,
)
from trusted_synthesis.hashing import canonical_hash

if TYPE_CHECKING:
    from trusted_synthesis.experiments.vtdo_experiment.phase1_state_realizations import (
        FinanceStateRealizationReport,
    )

GRADIENT_ALIGNMENT_VERSION = "finance_contribution_gradient_projection.v14"
REQUIRED_OBJECTIVE_SUPPORT_VERSION = "finance_contribution_evaluation_support.v6"
NUMERIC_CALIBRATION_VERSION = "finance_gradient_finite_precision_calibration.v3"
NUMERIC_CONTRACT_RUN_ROLE = "independent_30_task_production_candidate"
CALIBRATED_NUMERIC_PROFILE = {
    "profile_id": "bf16_checkpoint_strict_accumulation",
    "model_dtype": "bfloat16",
    "sparse_projection_dtype": "float32",
    "loss_accumulator_dtype": "float64",
    "gradient_checkpointing": True,
    "cuda_matmul_allow_tf32": False,
    "float32_matmul_precision": "highest",
}
NUMERIC_THRESHOLD_KEYS = {
    "maximum_loss_identity_absolute_error",
    "minimum_gradient_recomposition_cosine",
    "maximum_gradient_recomposition_relative_error",
    "maximum_gp_score_absolute_delta",
    "minimum_task_rank_agreement",
    "maximum_update_total_variation",
    "maximum_update_jensen_shannon",
}
GRADIENT_PARAMETER_SPACE = "beneficiary_trainable_lora_parameters"
GRADIENT_SIGNAL = "objective_update_cosine_alignment"
GRADIENT_REPLICATE_KIND = "independent_state_realization_and_objective_record"
MINIMUM_STATE_COUNT = 3
MAXIMUM_STATE_COUNT = 5
PRODUCTION_MINIMUM_REALIZATIONS_PER_STATE = 3
PRODUCTION_MAXIMUM_REALIZATIONS_PER_STATE = 5
GRADIENT_STATE_STRATEGY_PRIORITY: tuple[LineageStrategy, ...] = (
    "compact_direct",
    "compact_projection",
    "semantic_direct",
    "semantic_projection",
    "broad_direct",
    "broad_full_lineage",
    "compact_verify_frontier",
    "compact_output_lineage",
)
STATE_PROBABILITY_POLICY = "exact_frozen_task_round_distribution_over_3_to_5_states_v3"
SMOKE_STATE_PROBABILITY_POLICY = "explicit_uniform_smoke_only_v1"
TASK_SAMPLING_CONTRACT_VERSION = "finance_gradient_task_sampling.v4"
SPARSE_CAUSAL_LOSS_CONTRACT = {
    "version": "exact_sparse_supervised_causal_loss.v2",
    "forward_path": "decoder_hidden_states_then_sparse_output_projection",
    "prediction_position": "supervised_label_position_minus_one",
    "target_position": "supervised_label_position",
    "index_device_policy": "final_hidden_state_device",
    "reduction": "mean_over_supervised_tokens",
    "ignored_positions_materialized": False,
    "mathematical_contract": "equivalent_to_full_causal_lm_loss_with_ignore_index_minus_100",
    "projection_and_reduction_precision": "frozen_numeric_calibration_contract",
}
GRADIENT_MODE_CONTRACT = {
    "state_gradient_mode": "train",
    "objective_gradient_mode": "deterministic_eval_with_checkpoint_wrappers",
    "dropout_realization_policy": "independent_seed_per_realization",
    "objective_checkpoint_policy": (
        "stochastic_children_remain_eval_while_gradient_checkpoint_layers_recompute"
    ),
    "token_region_gradient_policy": "single_forward_shared_activation_graph",
    "loss_materialization": SPARSE_CAUSAL_LOSS_CONTRACT,
    "numeric_contract_required": True,
}
PRODUCTION_MINIMUM_TASK_COUNT = 30
PRODUCTION_MINIMUM_RECORDS_PER_SPLIT = 16
SMOKE_MINIMUM_RECORDS_PER_SPLIT = 4
RUN_ROLES = ("smoke", "production_candidate")
TOKEN_REGION_DECOMPOSITION_VERSION = "aligned_common_subsequence_token_gradient.v2"
MINIMUM_TASK_POOLED_DIFFERENTIAL_SUPERVISED_TOKEN_FRACTION = 0.05
REALIZATION_STABILITY_THRESHOLDS = {
    "maximum_mean_within_state_gradient_variance_ratio": 1.0,
    "minimum_mean_gradient_effective_sample_size": 1.5,
    "minimum_mean_pairwise_gradient_cosine": 0.25,
    "minimum_mean_split_half_gradient_cosine": 0.25,
    "minimum_mean_pairwise_gradient_sign_agreement": 0.55,
    "maximum_mean_sign_saturation_ratio": 0.995,
    "minimum_mean_pairwise_update_vector_cosine": 0.25,
    "minimum_mean_state_differential_gradient_ratio": 0.01,
    "minimum_task_pooled_differential_supervised_token_fraction": 0.05,
    "minimum_differential_gradient_fraction": 0.05,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_numeric_contract(path: Path) -> dict[str, Any]:
    contract = _read_json(path)
    expected_hash = contract.get("contract_hash")
    if not isinstance(expected_hash, str) or not expected_hash:
        raise ValueError("Gradient Projection numeric contract has no identity")
    payload = dict(contract)
    payload.pop("contract_hash", None)
    if canonical_hash(payload, prefix="finance_gradient_precision_contract:") != expected_hash:
        raise ValueError("Gradient Projection numeric contract failed identity replay")
    if contract.get("calibration_version") != NUMERIC_CALIBRATION_VERSION:
        raise ValueError("Gradient Projection numeric contract uses another calibration")
    if contract.get("allowed_next_run_role") != NUMERIC_CONTRACT_RUN_ROLE:
        raise ValueError("Gradient Projection numeric contract is not production eligible")
    if contract.get("selected_profile") != CALIBRATED_NUMERIC_PROFILE:
        raise ValueError("Gradient Projection numeric profile differs from the frozen profile")
    thresholds = contract.get("thresholds")
    if not isinstance(thresholds, dict) or set(thresholds) != NUMERIC_THRESHOLD_KEYS:
        raise ValueError("Gradient Projection numeric thresholds are incomplete")
    if any(not math.isfinite(float(value)) for value in thresholds.values()):
        raise ValueError("Gradient Projection numeric thresholds are non-finite")
    return contract


def _replay_numeric_contract(plan: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(plan["numeric_contract_path"]))
    if not path.is_file() or _sha256(path) != plan["numeric_contract_sha256"]:
        raise ValueError("Gradient Projection numeric contract changed after planning")
    contract = _load_numeric_contract(path)
    if contract != plan.get("numeric_contract"):
        raise ValueError("Gradient Projection plan embeds another numeric contract")
    if contract["contract_hash"] != plan.get("numeric_contract_hash"):
        raise ValueError("Gradient Projection numeric contract identity changed")
    return contract


def _configure_numeric_policy(profile: dict[str, Any]) -> None:
    import torch

    if profile != CALIBRATED_NUMERIC_PROFILE:
        raise ValueError("Gradient Projection attempted an uncalibrated numeric profile")
    torch.set_float32_matmul_precision(str(profile["float32_matmul_precision"]))
    allow_tf32 = bool(profile["cuda_matmul_allow_tf32"])
    torch.backends.cuda.matmul.allow_tf32 = allow_tf32
    torch.backends.cudnn.allow_tf32 = allow_tf32


def _assert_trainable_parameter_precision(manifest: dict[str, Any]) -> None:
    dtypes = {str(value.get("dtype")) for value in manifest.values()}
    if dtypes != {"torch.float32"}:
        raise ValueError("Gradient Projection requires FP32 trainable Adapter parameters")


def _realization_stability_thresholds(plan: dict[str, Any]) -> dict[str, float]:
    numeric = plan["numeric_contract"]["thresholds"]
    return {
        **REALIZATION_STABILITY_THRESHOLDS,
        "maximum_loss_identity_absolute_error": float(
            numeric["maximum_loss_identity_absolute_error"]
        ),
        "maximum_token_gradient_recomposition_relative_error": float(
            numeric["maximum_gradient_recomposition_relative_error"]
        ),
        "minimum_token_gradient_recomposition_cosine": float(
            numeric["minimum_gradient_recomposition_cosine"]
        ),
        "maximum_gp_score_absolute_delta": float(numeric["maximum_gp_score_absolute_delta"]),
        "minimum_task_rank_agreement": float(numeric["minimum_task_rank_agreement"]),
        "maximum_update_total_variation": float(numeric["maximum_update_total_variation"]),
        "maximum_update_jensen_shannon": float(numeric["maximum_update_jensen_shannon"]),
    }


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        sink.flush()
        os.fsync(sink.fileno())


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _valid_hashed_row(row: dict[str, Any], *, prefix: str) -> bool:
    expected = row.get("result_hash")
    if not isinstance(expected, str) or not expected:
        return False
    payload = dict(row)
    payload.pop("result_hash", None)
    return canonical_hash(payload, prefix=prefix) == expected


def _validate_run_contract(
    *,
    run_role: str,
    task_count: int,
    evaluation_record_count: int,
) -> None:
    if run_role not in RUN_ROLES:
        raise ValueError("unknown Gradient Projection run role")
    if task_count < 1:
        raise ValueError("Gradient Projection requires at least one task")
    minimum_per_split = (
        PRODUCTION_MINIMUM_RECORDS_PER_SPLIT
        if run_role == "production_candidate"
        else SMOKE_MINIMUM_RECORDS_PER_SPLIT
    )
    if evaluation_record_count < 2 * minimum_per_split:
        raise ValueError(
            f"{run_role} Gradient Projection requires at least "
            f"{2 * minimum_per_split} evaluation records"
        )
    if evaluation_record_count % 2:
        raise ValueError("Gradient Projection evaluation support must split evenly")
    if run_role == "production_candidate" and task_count < PRODUCTION_MINIMUM_TASK_COUNT:
        raise ValueError("production Gradient Projection requires at least 30 tasks")


def _support_target_boundary(
    support_plan: dict[str, Any],
) -> tuple[set[str], set[str], str]:
    target_contract = support_plan.get("gradient_target_contract")
    exclusion_contract = support_plan.get("objective_support_exclusion_contract")
    if not isinstance(target_contract, dict) or not isinstance(exclusion_contract, dict):
        raise ValueError("Gradient Projection support boundary contracts are missing")
    target_task_ids = {str(value) for value in target_contract.get("task_ids", ())}
    excluded_task_ids = {str(value) for value in exclusion_contract.get("task_ids", ())}
    if not target_task_ids:
        raise ValueError("Gradient Projection target task contract is empty")
    target_set_id = canonical_hash(
        tuple(sorted(target_task_ids)),
        prefix="finance_gradient_target_task_set:",
    )
    if target_contract.get("task_set_id") != target_set_id:
        raise ValueError("Gradient Projection target task contract hash is invalid")
    if exclusion_contract.get("task_set_id") != canonical_hash(
        tuple(sorted(excluded_task_ids)),
        prefix="finance_objective_support_excluded_task_set:",
    ):
        raise ValueError("Gradient Projection exclusion task contract hash is invalid")
    if target_task_ids & excluded_task_ids:
        raise ValueError("Gradient target tasks overlap Objective support exclusions")
    return target_task_ids, excluded_task_ids, target_set_id


def _selected_gradient_states(
    artifact: FinanceTaskStateArtifact,
) -> tuple[AcceptedFinanceState, ...]:
    """Freeze the complete verified 3-5-state quotient support without truncation."""

    by_strategy = {item.strategy: item for item in artifact.accepted_states}
    if len(by_strategy) != len(artifact.accepted_states):
        raise ValueError("Gradient Projection state strategies are not unique")
    selected = tuple(
        by_strategy[strategy]
        for strategy in GRADIENT_STATE_STRATEGY_PRIORITY
        if strategy in by_strategy
    )
    if {item.assignment.state.state_id for item in selected} != {
        item.assignment.state.state_id for item in artifact.accepted_states
    }:
        raise ValueError("Gradient Projection encountered an unregistered state strategy")
    if not MINIMUM_STATE_COUNT <= len(selected) <= MAXIMUM_STATE_COUNT:
        raise ValueError("Gradient Projection requires the complete 3-5-state verified support")
    state_ids = tuple(item.assignment.state.state_id for item in selected)
    if len(set(state_ids)) != len(state_ids):
        raise ValueError("Gradient Projection selected duplicate quotient states")
    return selected


def _bucket(value: int, boundaries: tuple[int, ...]) -> str:
    for boundary in boundaries:
        if value <= boundary:
            return f"le_{boundary}"
    return f"gt_{boundaries[-1]}"


def _program_depth(artifact: FinanceTaskStateArtifact) -> int:
    depths: dict[str, int] = {}
    for node in artifact.omega.task.oracle.task_program.nodes:
        depths[node.node_id] = 1 + max(
            (depths[dependency] for dependency in node.dependencies),
            default=0,
        )
    return max(depths.values())


def _task_sampling_stratum(artifact: FinanceTaskStateArtifact) -> tuple[str, ...]:
    states = _selected_gradient_states(artifact)
    trajectory_length = sum(len(state.trajectory.model_dump_json()) for state in states)
    evidence_count = len(artifact.omega.public_corpus.evidence)
    program_depth = _program_depth(artifact)
    state_family = "+".join(sorted(state.strategy for state in states))
    return (
        artifact.omega.task.public.task_type,
        _bucket(trajectory_length, (20_000, 60_000, 120_000)),
        _bucket(evidence_count, (2, 5, 10)),
        _bucket(program_depth, (1, 2, 4)),
        state_family,
    )


def select_gradient_tasks(
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    *,
    count: int,
    excluded_task_ids: set[str],
    sampling_salt: str,
    eligible_task_ids: set[str] | None = None,
) -> tuple[FinanceTaskStateArtifact, ...]:
    if not sampling_salt.strip():
        raise ValueError("Gradient Projection requires a preregistered sampling salt")
    groups: defaultdict[tuple[str, ...], list[FinanceTaskStateArtifact]] = defaultdict(list)
    for artifact in artifacts:
        if artifact.omega.task.task_id in excluded_task_ids:
            continue
        if eligible_task_ids is not None and artifact.omega.task.task_id not in eligible_task_ids:
            continue
        try:
            _selected_gradient_states(artifact)
        except ValueError:
            continue
        groups[_task_sampling_stratum(artifact)].append(artifact)
    for stratum, values in groups.items():
        values.sort(
            key=lambda item: (
                canonical_hash(
                    {
                        "sampling_salt": sampling_salt,
                        "stratum": stratum,
                        "artifact_id": item.artifact_id,
                    },
                    prefix="finance_gradient_task_order:",
                ),
                item.artifact_id,
            )
        )
    selected: list[FinanceTaskStateArtifact] = []
    cursor = 0
    group_names = tuple(
        sorted(
            groups,
            key=lambda stratum: canonical_hash(
                {"sampling_salt": sampling_salt, "stratum": stratum},
                prefix="finance_gradient_stratum_order:",
            ),
        )
    )
    while len(selected) < count:
        progressed = False
        for name in group_names:
            values = groups[name]
            if cursor >= len(values):
                continue
            selected.append(values[cursor])
            progressed = True
            if len(selected) == count:
                break
        if not progressed:
            break
        cursor += 1
    if len(selected) < count:
        raise ValueError(f"only {len(selected)} eligible target tasks for requested {count}")
    return tuple(selected)


def _select_gradient_tasks(
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    *,
    count: int,
    excluded_task_ids: set[str],
    sampling_salt: str,
    eligible_task_ids: set[str] | None = None,
) -> tuple[FinanceTaskStateArtifact, ...]:
    return select_gradient_tasks(
        artifacts,
        count=count,
        excluded_task_ids=excluded_task_ids,
        sampling_salt=sampling_salt,
        eligible_task_ids=eligible_task_ids,
    )


def _gradient_parameter_manifest(model: Any) -> tuple[dict[str, Any], str]:
    parameters = {
        name: parameter
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    }
    if not parameters:
        raise ValueError("Gradient Projection found no trainable beneficiary parameters")
    manifest = {
        name: {
            "shape": list(parameter.shape),
            "dtype": str(parameter.dtype),
            "numel": parameter.numel(),
        }
        for name, parameter in parameters.items()
    }
    return manifest, canonical_hash(manifest, prefix="gradient_parameter_manifest:")


def _record_gradient(
    model: Any,
    tokenizer: Any,
    record: VTDOTrainingRecord,
    *,
    mode: Literal["train", "objective_eval"],
    supervised_label_positions: tuple[int, ...] | None = None,
) -> tuple[dict[str, Any], float, int]:
    import torch

    _configure_numeric_policy(CALIBRATED_NUMERIC_PROFILE)
    if mode == "train":
        model.train()
    elif mode == "objective_eval":
        model.eval()
        _activate_deterministic_eval_checkpointing(model)
    else:
        raise ValueError(f"unknown Gradient Projection model mode:{mode}")
    model.zero_grad(set_to_none=True)
    batch, supervised_tokens = _batch(tokenizer, record)
    labels = batch.pop("labels")
    prediction_positions, target_labels, supervised_tokens = _supervised_causal_projection(
        labels,
        supervised_label_positions=supervised_label_positions,
    )
    logits = _sparse_causal_logits(
        model,
        batch,
        prediction_positions,
        projection_dtype="float32",
    )
    if logits.ndim != 3 or logits.shape[:2] != target_labels.shape:
        raise ValueError("Gradient Projection sparse logits do not match supervised targets")
    loss = _mean_supervised_nll(logits, target_labels)
    if not torch.isfinite(loss):
        raise ValueError("Gradient Projection produced a non-finite loss")
    loss.backward()
    gradients = _collect_trainable_gradients(model)
    loss_value = float(loss.detach().double().cpu())
    del loss, logits, batch, labels, prediction_positions, target_labels
    return gradients, loss_value, supervised_tokens


def _collect_trainable_gradients(model: Any) -> dict[str, Any]:
    import torch

    gradients: dict[str, Any] = {}
    for name, parameter in sorted(model.named_parameters()):
        if not parameter.requires_grad:
            continue
        if parameter.grad is None:
            raise ValueError(f"Gradient Projection produced a missing gradient:{name}")
        gradient = parameter.grad.detach().float().cpu().contiguous()
        if not torch.isfinite(gradient).all():
            raise ValueError(f"Gradient Projection produced a non-finite gradient:{name}")
        gradients[name] = gradient
    return gradients


def _mean_supervised_nll(
    logits: Any,
    target_labels: Any,
    *,
    token_ordinals: Any | None = None,
    accumulator_dtype: Literal["float32", "float64"] = "float64",
) -> Any:
    import torch

    if token_ordinals is not None:
        logits = logits.index_select(1, token_ordinals.to(logits.device))
        target_labels = target_labels.index_select(
            1,
            token_ordinals.to(target_labels.device),
        )
    losses = torch.nn.functional.cross_entropy(
        logits.float().reshape(-1, logits.shape[-1]),
        target_labels.to(logits.device).reshape(-1),
        reduction="none",
    )
    if accumulator_dtype == "float64":
        return losses.double().mean()
    if accumulator_dtype == "float32":
        return losses.mean()
    raise ValueError("Gradient Projection loss accumulator dtype is not registered")


def _record_gradient_decomposition(
    model: Any,
    tokenizer: Any,
    record: VTDOTrainingRecord,
    *,
    common_label_positions: tuple[int, ...],
    differential_label_positions: tuple[int, ...],
) -> tuple[
    tuple[dict[str, Any], float, int],
    tuple[dict[str, Any], float, int],
    tuple[dict[str, Any], float, int],
]:
    import torch

    _configure_numeric_policy(CALIBRATED_NUMERIC_PROFILE)
    model.train()
    model.zero_grad(set_to_none=True)
    batch, _ = _batch(tokenizer, record)
    labels = batch.pop("labels")
    prediction_positions, target_labels, supervised_tokens = _supervised_causal_projection(labels)
    all_label_positions = tuple(
        int(value) + 1 for value in prediction_positions.detach().cpu().tolist()
    )
    if (
        set(common_label_positions) & set(differential_label_positions)
        or tuple(sorted((*common_label_positions, *differential_label_positions)))
        != all_label_positions
    ):
        raise ValueError("token-gradient regions do not partition supervised support")
    ordinal_by_position = {
        position: ordinal for ordinal, position in enumerate(all_label_positions)
    }
    common_ordinals = torch.tensor(
        [ordinal_by_position[position] for position in common_label_positions],
        dtype=torch.long,
        device=target_labels.device,
    )
    differential_ordinals = torch.tensor(
        [ordinal_by_position[position] for position in differential_label_positions],
        dtype=torch.long,
        device=target_labels.device,
    )
    logits = _sparse_causal_logits(
        model,
        batch,
        prediction_positions,
        projection_dtype="float32",
    )
    losses = (
        _mean_supervised_nll(logits, target_labels),
        _mean_supervised_nll(
            logits,
            target_labels,
            token_ordinals=common_ordinals,
        ),
        _mean_supervised_nll(
            logits,
            target_labels,
            token_ordinals=differential_ordinals,
        ),
    )
    counts = (
        supervised_tokens,
        len(common_label_positions),
        len(differential_label_positions),
    )
    results = []
    for index, (loss, count) in enumerate(zip(losses, counts, strict=True)):
        if not torch.isfinite(loss):
            raise ValueError("Gradient Projection produced a non-finite regional loss")
        model.zero_grad(set_to_none=True)
        loss.backward(retain_graph=index < len(losses) - 1)
        results.append(
            (
                _collect_trainable_gradients(model),
                float(loss.detach().double().cpu()),
                count,
            )
        )
    del batch, labels, logits, losses, prediction_positions, target_labels
    return results[0], results[1], results[2]


def _activate_deterministic_eval_checkpointing(model: Any) -> int:
    """Enable checkpoint wrappers without re-enabling stochastic child modules."""

    import torch

    activated = 0
    for module in model.modules():
        if bool(getattr(module, "gradient_checkpointing", False)) and hasattr(
            module,
            "_gradient_checkpointing_func",
        ):
            module.training = True
            activated += 1
    stochastic_types = (
        torch.nn.Dropout,
        torch.nn.Dropout1d,
        torch.nn.Dropout2d,
        torch.nn.Dropout3d,
        torch.nn.AlphaDropout,
        torch.nn.FeatureAlphaDropout,
    )
    if activated == 0:
        raise ValueError("objective gradients require active gradient checkpoint wrappers")
    if any(isinstance(module, stochastic_types) and module.training for module in model.modules()):
        raise ValueError("objective gradient checkpointing re-enabled stochastic modules")
    return activated


def _sparse_causal_logits(
    model: Any,
    batch: dict[str, Any],
    prediction_positions: Any,
    *,
    projection_dtype: Literal["model", "float32"] = "float32",
) -> Any:
    """Run the full decoder while materializing vocabulary logits only where needed."""

    import torch

    causal_model = model.get_base_model() if hasattr(model, "get_base_model") else model
    if not hasattr(causal_model, "get_decoder"):
        raise ValueError("Gradient Projection model does not expose a causal decoder")
    decoder = causal_model.get_decoder()
    decoder_output = decoder(**batch, use_cache=False)
    hidden_states = decoder_output.last_hidden_state
    selected_hidden_states = hidden_states.index_select(
        1,
        prediction_positions.to(hidden_states.device),
    )
    output_embedding = causal_model.get_output_embeddings()
    if output_embedding is None:
        raise ValueError("Gradient Projection model has no output embedding")
    selected_hidden_states = selected_hidden_states.to(output_embedding.weight.device)
    if projection_dtype == "model":
        return output_embedding(selected_hidden_states)
    if projection_dtype != "float32":
        raise ValueError("Gradient Projection sparse projection dtype is not registered")
    bias = getattr(output_embedding, "bias", None)
    return torch.nn.functional.linear(
        selected_hidden_states.float(),
        output_embedding.weight.float(),
        None if bias is None else bias.float(),
    )


def _supervised_causal_projection(
    labels: Any,
    *,
    supervised_label_positions: tuple[int, ...] | None = None,
) -> tuple[Any, Any, int]:
    """Project causal logits to exactly the labels participating in mean NLL."""

    import torch

    if labels.ndim != 2 or labels.shape[0] != 1:
        raise ValueError("Gradient Projection requires a single-record label batch")
    if supervised_label_positions is None:
        positions = tuple(
            index
            for index, value in enumerate(labels[0].detach().cpu().tolist())
            if index > 0 and int(value) != -100
        )
    else:
        positions = tuple(sorted(set(supervised_label_positions)))
        if positions != supervised_label_positions:
            raise ValueError("Gradient Projection supervised token mask is invalid")
    if not positions or any(
        position <= 0 or position >= labels.shape[1] or int(labels[0, position]) == -100
        for position in positions
    ):
        raise ValueError("Gradient Projection supervised token mask is invalid")
    label_indices = torch.tensor(positions, dtype=torch.long, device=labels.device)
    prediction_positions = label_indices - 1
    targets = labels.index_select(1, label_indices)
    return prediction_positions, targets, len(positions)


def _gradient_norm(gradients: dict[str, Any]) -> float:
    import torch

    reference = next(iter(gradients.values()))
    squared = torch.zeros((), dtype=torch.float64, device=reference.device)
    for gradient in gradients.values():
        squared += torch.sum(gradient.double() * gradient.double())
    value = math.sqrt(float(squared))
    if not value > 0 or not math.isfinite(value):
        raise ValueError("Gradient Projection encountered a zero or non-finite gradient norm")
    return value


def _gradient_distance_norm(gradients: dict[str, Any]) -> float:
    import torch

    reference = next(iter(gradients.values()))
    squared = torch.zeros((), dtype=torch.float64, device=reference.device)
    for gradient in gradients.values():
        squared += torch.sum(gradient.double() * gradient.double())
    value = math.sqrt(float(squared))
    if value < 0 or not math.isfinite(value):
        raise ValueError("Gradient Projection encountered a non-finite gradient distance")
    return value


def _weighted_gradient(
    gradients: list[dict[str, Any]],
    weights: list[float],
) -> dict[str, Any]:
    if not gradients or len(gradients) != len(weights):
        raise ValueError("weighted gradient inputs are incomplete")
    if any(weight <= 0 or not math.isfinite(weight) for weight in weights):
        raise ValueError("weighted gradient requires finite positive weights")
    normalizer = sum(weights)
    names = tuple(gradients[0])
    if any(tuple(item) != names for item in gradients):
        raise ValueError("gradient parameter manifests do not align")
    values: dict[str, Any] = {}
    for name in names:
        aggregate = gradients[0][name].new_zeros(gradients[0][name].shape)
        for gradient, weight in zip(gradients, weights, strict=True):
            aggregate.add_(gradient[name], alpha=weight / normalizer)
        values[name] = aggregate.contiguous()
    return values


def _token_gradient_decomposition_metrics(
    full_gradient: dict[str, Any],
    common_gradient: dict[str, Any],
    differential_gradient: dict[str, Any],
    *,
    common_token_count: int,
    differential_token_count: int,
) -> dict[str, float]:
    if common_token_count <= 0 or differential_token_count <= 0:
        raise ValueError("token-gradient decomposition requires both supervised regions")
    recomposed = _weighted_gradient(
        [common_gradient, differential_gradient],
        [float(common_token_count), float(differential_token_count)],
    )
    difference = _gradient_difference(full_gradient, recomposed)
    full_norm = _gradient_norm(full_gradient)
    common_norm = _gradient_norm(common_gradient)
    differential_norm = _gradient_norm(differential_gradient)
    recomposed_norm = _gradient_norm(recomposed)
    _, cosine = _normalized_gradient_alignment(
        full_gradient,
        recomposed,
        left_norm=full_norm,
        right_norm=recomposed_norm,
    )
    total_component_norm = common_norm + differential_norm
    return {
        "common_gradient_norm_ratio": common_norm / full_norm,
        "differential_gradient_norm_ratio": differential_norm / full_norm,
        "differential_gradient_fraction": differential_norm / total_component_norm,
        "token_gradient_recomposition_relative_error": (
            _gradient_distance_norm(difference) / full_norm
        ),
        "token_gradient_recomposition_cosine": cosine,
    }


def _gradient_dot(
    left: dict[str, Any],
    right: dict[str, Any],
) -> float:
    import torch

    if tuple(left) != tuple(right):
        raise ValueError("gradient projection parameter manifests differ")
    reference = next(iter(left.values()))
    dot = torch.zeros((), dtype=torch.float64, device=reference.device)
    for name in left:
        if left[name].device != right[name].device:
            raise ValueError("gradient projection tensors must share a device")
        left_value = left[name].double()
        right_value = right[name].double()
        dot += torch.sum(left_value * right_value)
    return float(dot)


def _normalized_gradient_alignment(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    left_norm: float,
    right_norm: float,
) -> tuple[float, float]:
    if not left_norm > 0 or not right_norm > 0:
        raise ValueError("gradient projection requires nonzero gradients")
    dot_value = _gradient_dot(left, right)
    cosine = dot_value / (left_norm * right_norm)
    if not -1.000001 <= cosine <= 1.000001 or not math.isfinite(cosine):
        raise ValueError("gradient cosine is outside its numeric contract")
    return dot_value, max(-1.0, min(1.0, cosine))


def _gradient_alignment(
    left: dict[str, Any],
    right: dict[str, Any],
) -> tuple[float, float, float, float]:
    left_norm = _gradient_norm(left)
    right_norm = _gradient_norm(right)
    dot, cosine = _normalized_gradient_alignment(
        left,
        right,
        left_norm=left_norm,
        right_norm=right_norm,
    )
    return dot, cosine, left_norm, right_norm


def _current_state_probabilities(
    state_ids: list[str],
    *,
    probabilities: dict[str, float],
) -> dict[str, float]:
    if not state_ids or len(state_ids) != len(set(state_ids)):
        raise ValueError("Gradient Projection requires unique non-empty states")
    expected = set(state_ids)
    if set(probabilities) != expected:
        raise ValueError("Gradient Projection distribution does not exactly cover its states")
    ordered = {state_id: float(probabilities[state_id]) for state_id in sorted(expected)}
    if any(value <= 0 or not math.isfinite(value) for value in ordered.values()):
        raise ValueError("Gradient Projection probabilities must be positive and finite")
    if not math.isclose(sum(ordered.values()), 1.0, abs_tol=1e-9):
        raise ValueError("Gradient Projection probabilities must sum to one")
    return ordered


def _uniform_smoke_probabilities(state_ids: list[str]) -> dict[str, float]:
    if not state_ids or len(state_ids) != len(set(state_ids)):
        raise ValueError("Gradient Projection smoke support must be unique and non-empty")
    probability = 1.0 / len(state_ids)
    return {state_id: probability for state_id in sorted(state_ids)}


def _load_conditional_distributions(
    path: Path,
) -> dict[str, ConditionalTrajectoryDistribution]:
    rows = [ConditionalTrajectoryDistribution.model_validate(row) for row in _load_jsonl(path)]
    by_task = {row.task_condition_id: row for row in rows}
    if not rows or len(by_task) != len(rows):
        raise ValueError("Gradient Projection distributions are empty or duplicate a task")
    return by_task


def _load_state_realizations(path: Path) -> tuple[GradientStateRealization, ...]:
    rows = tuple(GradientStateRealization.model_validate(row) for row in _load_jsonl(path))
    if not rows:
        raise ValueError("Gradient Projection state realizations are empty")
    if len({row.realization_id for row in rows}) != len(rows):
        raise ValueError("Gradient Projection realization identities are duplicated")
    if len({row.record.record_id for row in rows}) != len(rows):
        raise ValueError("Gradient Projection realization records are duplicated")
    if len({row.trajectory_id for row in rows}) != len(rows):
        raise ValueError("Gradient Projection realization trajectories are duplicated")
    if len({row.trajectory_hash for row in rows}) != len(rows):
        raise ValueError("Gradient Projection realization payloads are duplicated")
    return rows


def _load_state_realization_report(
    path: Path,
    *,
    artifacts_path: Path,
    distributions_path: Path,
    realizations_path: Path,
) -> FinanceStateRealizationReport:
    from trusted_synthesis.experiments.vtdo_experiment.phase1_state_realizations import (
        FINANCE_REALIZATION_UNIQUENESS_POLICY,
        FinanceStateRealizationReport,
    )

    report = FinanceStateRealizationReport.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if report.status != "passed":
        raise ValueError("Gradient Projection requires a passed state realization report")
    if report.artifact_sha256 != _sha256(artifacts_path):
        raise ValueError("Gradient Projection realization report uses another task population")
    if report.distribution_sha256 != _sha256(distributions_path):
        raise ValueError("Gradient Projection realization report uses another distribution")
    if report.realizations_sha256 != _sha256(realizations_path):
        raise ValueError("Gradient Projection realization report uses another realization payload")
    if report.realization_uniqueness_policy != FINANCE_REALIZATION_UNIQUENESS_POLICY:
        raise ValueError("Gradient Projection requires independent trajectory draws")
    return report


def _state_realization_support(
    selected: tuple[FinanceTaskStateArtifact, ...],
    realizations: tuple[GradientStateRealization, ...],
    *,
    run_role: str,
) -> dict[tuple[str, str], tuple[GradientStateRealization, ...]]:
    grouped: defaultdict[tuple[str, str], list[GradientStateRealization]] = defaultdict(list)
    for realization in realizations:
        grouped[(realization.task_condition_id, realization.state_id)].append(realization)
    expected: dict[tuple[str, str], FinanceTaskStateArtifact] = {}
    for artifact in selected:
        for state in _selected_gradient_states(artifact):
            expected[(artifact.omega.task.task_id, state.assignment.state.state_id)] = artifact
    if set(grouped) != set(expected):
        raise ValueError("Gradient Projection realizations do not exactly cover selected states")
    minimum = PRODUCTION_MINIMUM_REALIZATIONS_PER_STATE if run_role == "production_candidate" else 1
    maximum = PRODUCTION_MAXIMUM_REALIZATIONS_PER_STATE
    frozen: dict[tuple[str, str], tuple[GradientStateRealization, ...]] = {}
    for key, values in grouped.items():
        artifact = expected[key]
        values.sort(
            key=lambda item: (
                item.generation_seed,
                item.generation_ordinal,
                item.realization_id,
            )
        )
        if not minimum <= len(values) <= maximum:
            raise ValueError(
                f"Gradient Projection state realization count must lie in [{minimum}, {maximum}]"
            )
        if any(item.source_task_artifact_id != artifact.artifact_id for item in values):
            raise ValueError("Gradient Projection realization crosses task artifacts")
        if len({item.generation_seed for item in values}) != len(values):
            raise ValueError("Gradient Projection state realizations require independent seeds")
        frozen[key] = tuple(values)
    return frozen


def _supervised_token_ids(encoded: dict[str, Any]) -> tuple[int, ...]:
    return tuple(
        int(token_id)
        for token_id, label in zip(encoded["input_ids"], encoded["labels"], strict=True)
        if int(label) != -100
    )


def _supervised_label_positions(encoded: dict[str, Any]) -> tuple[int, ...]:
    return tuple(
        index for index, label in enumerate(encoded["labels"]) if index > 0 and int(label) != -100
    )


def _aligned_token_region_partition(
    record_ids: tuple[str, ...],
    encoded_by_record: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if len(record_ids) < 2 or len(set(record_ids)) != len(record_ids):
        raise ValueError("token-region decomposition requires distinct task realizations")
    ordered = tuple(sorted(record_ids))
    reference_id = ordered[0]
    reference_positions = _supervised_label_positions(encoded_by_record[reference_id])
    reference_tokens = tuple(
        int(encoded_by_record[reference_id]["input_ids"][position])
        for position in reference_positions
    )
    if not reference_tokens:
        raise ValueError("token-region decomposition has no supervised reference tokens")
    mappings: dict[str, dict[int, int]] = {
        reference_id: {index: position for index, position in enumerate(reference_positions)}
    }
    common_reference_indices = set(range(len(reference_tokens)))
    for record_id in ordered[1:]:
        positions = _supervised_label_positions(encoded_by_record[record_id])
        tokens = tuple(
            int(encoded_by_record[record_id]["input_ids"][position]) for position in positions
        )
        matcher = SequenceMatcher(None, reference_tokens, tokens, autojunk=False)
        mapping: dict[int, int] = {}
        for block in matcher.get_matching_blocks():
            for offset in range(block.size):
                mapping[block.a + offset] = positions[block.b + offset]
        mappings[record_id] = mapping
        common_reference_indices.intersection_update(mapping)
    common_reference = tuple(sorted(common_reference_indices))
    regions: dict[str, dict[str, Any]] = {}
    for record_id in ordered:
        all_positions = _supervised_label_positions(encoded_by_record[record_id])
        common_positions = tuple(mappings[record_id][index] for index in common_reference)
        common_set = set(common_positions)
        differential_positions = tuple(
            position for position in all_positions if position not in common_set
        )
        if not common_positions or not differential_positions:
            raise ValueError(
                "token-region decomposition requires non-empty common and differential regions"
            )
        regions[record_id] = {
            "common_label_positions": common_positions,
            "differential_label_positions": differential_positions,
            "common_supervised_token_count": len(common_positions),
            "differential_supervised_token_count": len(differential_positions),
            "differential_supervised_token_fraction": (
                len(differential_positions) / len(all_positions)
            ),
        }
    return regions


def _build_token_region_manifest(
    jobs: list[dict[str, Any]],
    encoded_by_record: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records_by_task: defaultdict[str, list[str]] = defaultdict(list)
    records_by_state: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    observed_record_ids: set[str] = set()
    for job in jobs:
        task_id = str(job["task_id"])
        state_id = str(job["state_id"])
        record_id = str(job["record_id"])
        if record_id in observed_record_ids:
            raise ValueError("token-region decomposition received a duplicate target record")
        observed_record_ids.add(record_id)
        records_by_task[task_id].append(record_id)
        records_by_state[(task_id, state_id)].append(record_id)
    records: dict[str, dict[str, Any]] = {}
    task_rows: list[dict[str, Any]] = []

    def summarize(record_ids: list[str]) -> dict[str, int | float]:
        rows = [records[record_id] for record_id in record_ids]
        fractions = [
            float(row["differential_supervised_token_fraction"]) for row in rows
        ]
        differential_count = sum(
            int(row["differential_supervised_token_count"]) for row in rows
        )
        supervised_count = sum(
            int(row["common_supervised_token_count"])
            + int(row["differential_supervised_token_count"])
            for row in rows
        )
        return {
            "record_count": len(rows),
            "minimum_record_differential_supervised_token_fraction": min(fractions),
            "mean_record_differential_supervised_token_fraction": statistics.fmean(
                fractions
            ),
            "pooled_differential_supervised_token_fraction": (
                differential_count / supervised_count
            ),
        }

    for task_id, record_ids in sorted(records_by_task.items()):
        task_regions = _aligned_token_region_partition(
            tuple(record_ids),
            encoded_by_record,
        )
        records.update(task_regions)
        task_rows.append(
            {
                "task_id": task_id,
                **summarize(record_ids),
            }
        )
    if set(records) != set(encoded_by_record):
        raise ValueError("token-region decomposition did not cover every target record")
    state_rows = [
        {
            "task_id": task_id,
            "state_id": state_id,
            **summarize(record_ids),
        }
        for (task_id, state_id), record_ids in sorted(records_by_state.items())
    ]
    minimum_record_fraction = min(
        float(value["differential_supervised_token_fraction"]) for value in records.values()
    )
    minimum_state_pooled_fraction = min(
        float(row["pooled_differential_supervised_token_fraction"])
        for row in state_rows
    )
    minimum_task_pooled_fraction = min(
        float(row["pooled_differential_supervised_token_fraction"])
        for row in task_rows
    )
    if (
        minimum_task_pooled_fraction
        < MINIMUM_TASK_POOLED_DIFFERENTIAL_SUPERVISED_TOKEN_FRACTION
    ):
        raise ValueError("token-region decomposition is dominated by common target tokens")
    manifest: dict[str, Any] = {
        "version": TOKEN_REGION_DECOMPOSITION_VERSION,
        "alignment_policy": (
            "canonical_record_sequence_matcher_intersection_over_supervised_targets"
        ),
        "coverage_gate_policy": "minimum_task_pooled_differential_supervised_tokens",
        "record_level_policy": "non_empty_regions_required_fraction_is_diagnostic",
        "minimum_task_pooled_differential_supervised_token_fraction_threshold": (
            MINIMUM_TASK_POOLED_DIFFERENTIAL_SUPERVISED_TOKEN_FRACTION
        ),
        "minimum_observed_record_differential_supervised_token_fraction": (
            minimum_record_fraction
        ),
        "minimum_observed_state_pooled_differential_supervised_token_fraction": (
            minimum_state_pooled_fraction
        ),
        "minimum_observed_task_pooled_differential_supervised_token_fraction": (
            minimum_task_pooled_fraction
        ),
        "records": records,
        "state_rows": tuple(state_rows),
        "task_rows": tuple(task_rows),
        "status": "passed",
    }
    manifest["manifest_hash"] = canonical_hash(
        manifest,
        prefix="finance_gradient_token_region_manifest:",
    )
    return manifest


def _token_overlap(left: tuple[int, ...], right: tuple[int, ...]) -> dict[str, float]:
    if not left or not right:
        raise ValueError("Gradient Projection token overlap requires supervised targets")
    aligned = sum(a == b for a, b in zip(left, right, strict=False))
    left_set = set(left)
    right_set = set(right)
    return {
        "position_overlap": aligned / max(len(left), len(right)),
        "set_jaccard": len(left_set & right_set) / len(left_set | right_set),
    }


def _pairwise_token_diagnostics(
    records: list[VTDOTrainingRecord],
    encoded_by_record: dict[str, dict[str, Any]],
) -> dict[str, float]:
    vectors = [_supervised_token_ids(encoded_by_record[record.record_id]) for record in records]
    pairs = [_token_overlap(left, right) for left, right in combinations(vectors, 2)]
    if not pairs:
        return {"mean_position_overlap": 1.0, "mean_set_jaccard": 1.0}
    return {
        "mean_position_overlap": statistics.fmean(row["position_overlap"] for row in pairs),
        "mean_set_jaccard": statistics.fmean(row["set_jaccard"] for row in pairs),
    }


def _attach_centered_signal(
    rows: list[dict[str, Any]],
    *,
    split: str,
    penalty_coefficient: float,
    probabilities: dict[str, float],
    minimum_replicates: int = PRODUCTION_MINIMUM_RECORDS_PER_SPLIT,
) -> None:
    signal_field = f"{split}_aggregate_alignment"
    replicates_field = f"{split}_record_alignments"
    raw_centered_field = f"{split}_centered_contribution"
    deviation_field = f"{split}_sample_standard_deviation"
    conservative_raw_field = f"{split}_conservative_raw_contribution"
    conservative_centered_field = f"{split}_conservative_centered_contribution"
    raw_mean = sum(probabilities[str(row["state_id"])] * float(row[signal_field]) for row in rows)
    for row in rows:
        replicates = [float(value) for value in row[replicates_field]]
        if len(replicates) < minimum_replicates:
            raise ValueError("Gradient Projection has too few evaluation replicates")
        deviation = statistics.stdev(replicates)
        row["current_probability"] = probabilities[str(row["state_id"])]
        row[deviation_field] = deviation
        row[raw_centered_field] = float(row[signal_field]) - raw_mean
        row[conservative_raw_field] = float(row[signal_field]) - penalty_coefficient * deviation
    conservative_mean = sum(
        probabilities[str(row["state_id"])] * float(row[conservative_raw_field]) for row in rows
    )
    for row in rows:
        row[conservative_centered_field] = float(row[conservative_raw_field]) - conservative_mean
    for field in (raw_centered_field, conservative_centered_field):
        weighted_mean = sum(probabilities[str(row["state_id"])] * float(row[field]) for row in rows)
        if not math.isclose(weighted_mean, 0.0, abs_tol=1e-12):
            raise ValueError(f"Gradient Projection signal is not pi_t centered:{field}")


def _winner(values: list[float], state_ids: list[str]) -> str:
    if len(values) != len(state_ids) or not values:
        raise ValueError("winner calculation received incomplete states")
    return max(zip(values, state_ids, strict=True), key=lambda item: (item[0], item[1]))[1]


def _permutation_p_value(
    vectors: list[tuple[list[float], list[float]]],
    *,
    statistic: str,
    iterations: int,
    seed: int,
) -> float:
    import random

    if statistic not in {"spearman", "concordance"}:
        raise ValueError("unknown permutation statistic")
    observed = statistics.fmean(
        _spearman(left, right) if statistic == "spearman" else _pairwise_concordance(left, right)
        for left, right in vectors
    )
    rng = random.Random(seed)
    exceed = 0
    for _ in range(iterations):
        values = []
        for left, right in vectors:
            shuffled = list(left)
            rng.shuffle(shuffled)
            values.append(
                _spearman(shuffled, right)
                if statistic == "spearman"
                else _pairwise_concordance(shuffled, right)
            )
        exceed += int(statistics.fmean(values) >= observed)
    return (1 + exceed) / (iterations + 1)


def prepare(args: argparse.Namespace) -> None:
    numeric_contract_path = Path(args.numeric_contract_path).resolve()
    numeric_contract = _load_numeric_contract(numeric_contract_path)
    support_dir = Path(args.source_support_dir).resolve()
    support_plan_path = support_dir / "plan.json"
    support_report_path = support_dir / "beneficiary_evaluation_report.json"
    support_plan = _read_json(support_plan_path)
    support_report = _read_json(support_report_path)
    if support_plan.get("experiment_version") != REQUIRED_OBJECTIVE_SUPPORT_VERSION:
        raise ValueError("Gradient Projection requires explicit Objective Support v6")
    if support_report.get("plan_hash") != support_plan.get("plan_hash"):
        raise ValueError("Gradient Projection support report does not replay its plan")
    if (
        support_plan.get("numeric_contract_hash") != numeric_contract["contract_hash"]
        or support_report.get("numeric_contract_hash") != numeric_contract["contract_hash"]
    ):
        raise ValueError("Gradient Projection and Objective Support numeric contracts differ")
    target_task_ids, excluded_task_ids, target_task_set_id = _support_target_boundary(support_plan)
    if support_report.get("gradient_target_task_set_id") != target_task_set_id:
        raise ValueError("Gradient Projection support report targets another task set")
    partitions = support_plan.get("objective_partitions")
    if not isinstance(partitions, dict) or set(partitions) != {
        "estimation",
        "validation",
        "authorization",
    }:
        raise ValueError("Gradient Projection requires three explicit Objective partitions")
    estimation_ids = tuple(str(value) for value in partitions["estimation"]["record_ids"])
    validation_ids = tuple(str(value) for value in partitions["validation"]["record_ids"])
    authorization_ids = tuple(str(value) for value in partitions["authorization"]["record_ids"])
    evaluation_ids = (*estimation_ids, *validation_ids)
    _validate_run_contract(
        run_role=args.run_role,
        task_count=args.task_count,
        evaluation_record_count=len(evaluation_ids),
    )
    minimum_authorization_records = (
        PRODUCTION_MINIMUM_RECORDS_PER_SPLIT
        if args.run_role == "production_candidate"
        else SMOKE_MINIMUM_RECORDS_PER_SPLIT
    )
    if len(authorization_ids) < minimum_authorization_records:
        raise ValueError(
            f"{args.run_role} Gradient Projection requires at least "
            f"{minimum_authorization_records} untouched authorization records"
        )
    if set(evaluation_ids) & set(authorization_ids):
        raise ValueError("Gradient Projection objective partitions are not disjoint")
    if args.uncertainty_penalty_coefficient <= 0:
        raise ValueError("Gradient Projection uncertainty penalty must be positive")
    if (
        args.local_learning_rate <= 0
        or args.optimizer_epsilon <= 0
        or args.maximum_gradient_norm <= 0
    ):
        raise ValueError("Gradient Projection local optimizer parameters must be positive")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts_path = Path(args.artifacts_path).resolve()
    disjoint_paths = tuple(
        Path(value).resolve() for value in support_plan["disjoint_artifact_paths"]
    )
    if artifacts_path not in disjoint_paths:
        raise ValueError("Gradient Projection Artifact is outside its frozen target contract")
    target_path_index = disjoint_paths.index(artifacts_path)
    if _sha256(artifacts_path) != support_plan["disjoint_artifact_sha256"][target_path_index]:
        raise ValueError("Gradient Projection target Artifact changed after support planning")
    artifacts = load_finance_multi_state_artifacts(artifacts_path)
    artifact_task_ids = {artifact.omega.task.task_id for artifact in artifacts}
    if not artifact_task_ids or not artifact_task_ids <= target_task_ids:
        raise ValueError("Gradient Projection Artifact contains tasks outside its target set")
    distributions_path = (
        Path(args.current_distributions_path).resolve()
        if args.current_distributions_path is not None
        else None
    )
    distributions = (
        _load_conditional_distributions(distributions_path)
        if distributions_path is not None
        else {}
    )
    if args.run_role == "production_candidate" and distributions_path is None:
        raise ValueError("production Gradient Projection requires frozen current distributions")
    if distributions_path is None and not args.allow_uniform_smoke_distribution:
        raise ValueError("uniform state probabilities require --allow-uniform-smoke-distribution")
    if args.allow_uniform_smoke_distribution and args.run_role != "smoke":
        raise ValueError("uniform smoke distributions cannot enter production")
    selected = _select_gradient_tasks(
        artifacts,
        count=args.task_count,
        excluded_task_ids=excluded_task_ids,
        sampling_salt=args.task_sampling_salt,
        eligible_task_ids=(
            artifact_task_ids & set(distributions) if distributions else artifact_task_ids
        ),
    )
    selected_by_task = {item.omega.task.task_id: item for item in selected}
    if len(selected_by_task) != len(selected):
        raise ValueError("Gradient Projection selected duplicate task conditions")

    task_distributions: dict[str, dict[str, Any]] = {}
    for task_id, artifact in selected_by_task.items():
        state_ids = [
            state.assignment.state.state_id for state in _selected_gradient_states(artifact)
        ]
        if distributions:
            distribution = distributions[task_id]
            probabilities = _current_state_probabilities(
                state_ids,
                probabilities=distribution.probabilities,
            )
            task_distributions[task_id] = {
                "distribution_id": distribution.distribution_id,
                "round_index": distribution.round_index,
                "source_distribution_id": distribution.source_distribution_id,
                "distribution": distribution.model_dump(mode="json"),
                "probabilities": probabilities,
                "distribution_hash": contribution_current_distribution_hash(
                    task_id,
                    probabilities,
                ),
            }
        else:
            probabilities = _uniform_smoke_probabilities(state_ids)
            task_distributions[task_id] = {
                "distribution_id": canonical_hash(
                    {
                        "task_id": task_id,
                        "probabilities": probabilities,
                        "run_role": "smoke",
                    },
                    prefix="gradient_uniform_smoke_distribution:",
                ),
                "round_index": 0,
                "source_distribution_id": None,
                "distribution": None,
                "probabilities": probabilities,
                "distribution_hash": contribution_current_distribution_hash(
                    task_id,
                    probabilities,
                ),
            }
    if len({int(value["round_index"]) for value in task_distributions.values()}) != 1:
        raise ValueError("Gradient Projection current distributions cross rounds")

    realizations_path = (
        Path(args.state_realizations_path).resolve()
        if args.state_realizations_path is not None
        else None
    )
    realization_report_path = (
        Path(args.state_realization_report_path).resolve()
        if args.state_realization_report_path is not None
        else None
    )
    realization_report: FinanceStateRealizationReport | None = None
    realization_support: dict[tuple[str, str], tuple[GradientStateRealization, ...]] = {}
    if realizations_path is not None:
        if distributions_path is None:
            raise ValueError("state realizations require frozen current distributions")
        if realization_report_path is None and args.run_role == "production_candidate":
            raise ValueError(
                "production Gradient Projection requires a state realization report"
            )
        if realization_report_path is not None:
            realization_report = _load_state_realization_report(
                realization_report_path,
                artifacts_path=artifacts_path,
                distributions_path=distributions_path,
                realizations_path=realizations_path,
            )
        realization_pool = _load_state_realizations(realizations_path)
        selected_realizations = tuple(
            item for item in realization_pool if item.task_condition_id in selected_by_task
        )
        realization_support = _state_realization_support(
            selected,
            selected_realizations,
            run_role=args.run_role,
        )
        for (task_id, _), state_realizations in realization_support.items():
            if any(
                item.source_distribution_id != task_distributions[task_id]["distribution_id"]
                for item in state_realizations
            ):
                raise ValueError("Gradient realization uses another current distribution")
    elif args.run_role == "production_candidate":
        raise ValueError("production Gradient Projection requires state realizations")

    jobs: list[dict[str, Any]] = []
    target_records: list[VTDOTrainingRecord] = []
    for artifact in selected:
        task_id = artifact.omega.task.task_id
        distribution_id = str(task_distributions[task_id]["distribution_id"])
        for state in _selected_gradient_states(artifact):
            state_id = state.assignment.state.state_id
            realized = realization_support.get((task_id, state_id), ())
            if realized:
                record_rows = tuple(
                    (
                        item.record,
                        item.realization_id,
                        item.generation_seed,
                        item.decision_trace_hash,
                        "fresh_independently_verified",
                    )
                    for item in realized
                )
            else:
                record = _record_from_state(
                    artifact,
                    state,
                    "B2_validity",
                    sampling_weight=1.0,
                    source_distribution_id=distribution_id,
                    extra_metadata={"fixture_diagnostic_only": True},
                )
                record_rows = (
                    (
                        record,
                        canonical_hash(
                            {
                                "record_id": record.record_id,
                                "run_role": "smoke",
                            },
                            prefix="gradient_fixture_realization:",
                        ),
                        args.numeric_seed,
                        canonical_hash(
                            state.trajectory,
                            prefix="gradient_fixture_decision_trace:",
                        ),
                        "deterministic_fixture_smoke_only",
                    ),
                )
            for realization_index, (
                record,
                realization_id,
                realization_seed,
                decision_trace_hash,
                realization_role,
            ) in enumerate(record_rows):
                target_records.append(record)
                jobs.append(
                    {
                        "job_id": canonical_hash(
                            {
                                "task_id": task_id,
                                "state_id": state_id,
                                "realization_id": realization_id,
                                "record_id": record.record_id,
                                "distribution_id": distribution_id,
                            },
                            prefix="gradient_projection_job:",
                        ),
                        "task_id": task_id,
                        "task_type": artifact.omega.task.public.task_type,
                        "state_id": state_id,
                        "strategy": state.strategy,
                        "record_id": record.record_id,
                        "realization_id": realization_id,
                        "realization_index": realization_index,
                        "realization_seed": realization_seed,
                        "gradient_seed": int(
                            canonical_hash(
                                {
                                    "numeric_seed": args.numeric_seed,
                                    "realization_id": realization_id,
                                },
                                prefix="gradient_realization_seed:",
                            ).rsplit(":", 1)[-1][:8],
                            16,
                        ),
                        "decision_trace_hash": decision_trace_hash,
                        "realization_role": realization_role,
                        "source_distribution_id": distribution_id,
                    }
                )
    if len({record.record_id for record in target_records}) != len(target_records):
        raise ValueError("Gradient Projection target realization records overlap")
    if {record.record_id for record in target_records} & (
        set(evaluation_ids) | set(authorization_ids)
    ):
        raise ValueError("Gradient Projection state and objective records overlap")
    target_records_path = output_dir / "target_records.jsonl"
    target_records_path.write_text(
        "".join(record.model_dump_json() + "\n" for record in target_records),
        encoding="utf-8",
    )
    source_records_path = Path(support_plan["records_path"]).resolve()
    source_records = _load_records(source_records_path)
    tokenizer = _load_tokenizer(Path(support_plan["model_dir"]))
    token_audit: dict[str, dict[str, int]] = {}
    encoded_target_records: dict[str, dict[str, Any]] = {}
    for record in target_records:
        encoded = _encode_record(tokenizer, record, MAX_SEQUENCE_LENGTH)
        encoded_target_records[record.record_id] = encoded
        token_audit[record.record_id] = {
            "processed_tokens": len(encoded["input_ids"]),
            "prompt_tokens": int(encoded["prompt_tokens"]),
            "supervised_tokens": int(encoded["supervised_tokens"]),
        }
    for record_id in (*evaluation_ids, *authorization_ids):
        encoded = _encode_record(tokenizer, source_records[record_id], MAX_SEQUENCE_LENGTH)
        token_audit[record_id] = {
            "processed_tokens": len(encoded["input_ids"]),
            "prompt_tokens": int(encoded["prompt_tokens"]),
            "supervised_tokens": int(encoded["supervised_tokens"]),
        }
    token_region_manifest = _build_token_region_manifest(
        jobs,
        encoded_target_records,
    )
    records_by_state: defaultdict[tuple[str, str], list[VTDOTrainingRecord]] = defaultdict(list)
    for record in target_records:
        if record.trajectory_state_id is None:
            raise ValueError("Gradient Projection target record lacks a quotient state")
        records_by_state[(record.task_id, record.trajectory_state_id)].append(record)
    within_state_token_overlap = {
        f"{task_id}|{state_id}": _pairwise_token_diagnostics(
            records,
            encoded_target_records,
        )
        for (task_id, state_id), records in sorted(records_by_state.items())
    }
    cross_state_token_overlap = {}
    for task_id in sorted(selected_by_task):
        representatives = [
            sorted(records_by_state[(task_id, state_id)], key=lambda item: item.record_id)[0]
            for state_id in sorted(task_distributions[task_id]["probabilities"])
        ]
        cross_state_token_overlap[task_id] = _pairwise_token_diagnostics(
            representatives,
            encoded_target_records,
        )
    stratum_counts = Counter("|".join(_task_sampling_stratum(item)) for item in selected)
    realization_counts = Counter((job["task_id"], job["state_id"]) for job in jobs)
    task_distribution_hashes = {
        task_id: str(value["distribution_hash"])
        for task_id, value in sorted(task_distributions.items())
    }
    current_distribution_contract_hash = contribution_distribution_contract_hash(
        task_distribution_hashes
    )
    state_realization_manifest = {
        "source_path": str(realizations_path) if realizations_path is not None else None,
        "source_sha256": _sha256(realizations_path) if realizations_path is not None else None,
        "source_report_path": (
            str(realization_report_path) if realization_report_path is not None else None
        ),
        "source_report_sha256": (
            _sha256(realization_report_path)
            if realization_report_path is not None
            else None
        ),
        "source_report_id": (
            realization_report.report_id if realization_report is not None else None
        ),
        "realization_uniqueness_policy": (
            realization_report.realization_uniqueness_policy
            if realization_report is not None
            else "deterministic_fixture_smoke_only"
        ),
        "realization_ids": tuple(sorted(str(job["realization_id"]) for job in jobs)),
        "unique_trajectory_hash_count": (
            len({item.trajectory_hash for item in selected_realizations})
            if realizations_path is not None
            else len(jobs)
        ),
        "unique_decision_trace_count": len(
            {str(job["decision_trace_hash"]) for job in jobs}
        ),
        "decision_trace_diversity_rate": (
            len({str(job["decision_trace_hash"]) for job in jobs}) / len(jobs)
        ),
        "realization_counts": tuple(
            (task_id, state_id, count)
            for (task_id, state_id), count in sorted(realization_counts.items())
        ),
        "all_fresh_independently_verified": all(
            job["realization_role"] == "fresh_independently_verified" for job in jobs
        ),
    }
    state_realization_manifest_hash = canonical_hash(
        state_realization_manifest,
        prefix="finance_gradient_state_realization_manifest:",
    )
    task_sampling_contract = {
        "version": TASK_SAMPLING_CONTRACT_VERSION,
        "salt_hash": canonical_hash(args.task_sampling_salt, prefix="task_sampling_salt:"),
        "stratum_fields": (
            "task_type",
            "trajectory_length_bucket",
            "evidence_count_bucket",
            "program_depth_bucket",
            "state_family",
        ),
        "stratum_counts": dict(sorted(stratum_counts.items())),
        "selection": "salted_hash_round_robin_across_strata",
    }
    gradient_mode_contract = {
        **GRADIENT_MODE_CONTRACT,
        "numeric_profile": numeric_contract["selected_profile"],
        "numeric_contract_hash": numeric_contract["contract_hash"],
    }
    values: dict[str, Any] = {
        "experiment_version": GRADIENT_ALIGNMENT_VERSION,
        "run_role": args.run_role,
        "artifacts_path": str(artifacts_path),
        "source_support_plan_path": str(support_plan_path),
        "source_support_plan_hash": support_plan["plan_hash"],
        "source_support_report_path": str(support_report_path),
        "source_support_report_hash": support_report["report_hash"],
        "source_records_path": str(source_records_path),
        "source_records_sha256": _sha256(source_records_path),
        "target_records_path": str(target_records_path),
        "target_records_sha256": _sha256(target_records_path),
        "current_distributions_path": (
            str(distributions_path) if distributions_path is not None else None
        ),
        "current_distributions_sha256": (
            _sha256(distributions_path) if distributions_path is not None else None
        ),
        "task_distributions": task_distributions,
        "task_distribution_hashes": task_distribution_hashes,
        "current_distribution_contract_hash": current_distribution_contract_hash,
        "state_realization_manifest": state_realization_manifest,
        "state_realization_manifest_hash": state_realization_manifest_hash,
        "task_sampling_contract": task_sampling_contract,
        "task_sampling_contract_hash": canonical_hash(
            task_sampling_contract,
            prefix="finance_gradient_task_sampling_contract:",
        ),
        "model_dir": support_plan["model_dir"],
        "base_model_manifest_hash": support_plan["base_model_manifest_hash"],
        "beneficiary_adapter_dir": support_plan["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": support_plan["beneficiary_adapter_tensor_sha256"],
        "beneficiary_model_state_id": support_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": support_plan["beneficiary_checkpoint_hash"],
        "selected_task_ids": tuple(item.omega.task.task_id for item in selected),
        "excluded_task_ids": tuple(sorted(excluded_task_ids)),
        "task_count": len(selected),
        "jobs": jobs,
        "state_count": len(realization_counts),
        "state_realization_count": len(jobs),
        "gradient_estimation_record_ids": estimation_ids,
        "gradient_validation_record_ids": validation_ids,
        "final_test_record_ids": authorization_ids,
        "gradient_estimation_set_id": canonical_hash(
            estimation_ids,
            prefix="gradient_projection_estimation_set:",
        ),
        "gradient_validation_set_id": canonical_hash(
            validation_ids,
            prefix="gradient_projection_validation_set:",
        ),
        "final_test_set_id": partitions["authorization"]["set_id"],
        "gradient_parameter_space": GRADIENT_PARAMETER_SPACE,
        "gradient_signal": GRADIENT_SIGNAL,
        "gradient_replicate_kind": GRADIENT_REPLICATE_KIND,
        "gradient_mode_contract": gradient_mode_contract,
        "gradient_mode_contract_id": canonical_hash(
            gradient_mode_contract,
            prefix="finance_gradient_mode_contract:",
        ),
        "numeric_contract_path": str(numeric_contract_path),
        "numeric_contract_sha256": _sha256(numeric_contract_path),
        "numeric_contract": numeric_contract,
        "numeric_contract_hash": numeric_contract["contract_hash"],
        "local_optimizer_contract": {
            "optimizer_name": "adamw",
            "estimator_scope": "local_distribution_update_only",
            "step_count": 1,
            "cold_start": True,
            "reuse_main_optimizer_state": False,
            "learning_rate": args.local_learning_rate,
            "betas": (0.9, 0.999),
            "epsilon": args.optimizer_epsilon,
            "weight_decay": 0.0,
            "maximum_gradient_norm": args.maximum_gradient_norm,
            "gradient_accumulation_steps": 1,
            "mixed_state_batches_allowed": False,
            "state_gradient_mode": "train",
            "objective_gradient_mode": gradient_mode_contract["objective_gradient_mode"],
            "objective_gradient_point": "post_global_update",
        },
        "internal_objective_gradient_role": ("pre_global_update_diagnostic_for_gp_a_and_gp_b_only"),
        "gp_c_objective_gradient_requirement": "post_global_update_at_authorization_stage",
        "loss_function": "supervised_token_mean_nll",
        "objective_function": "negative_supervised_token_nll",
        "update_direction": "negative_training_loss_gradient",
        "sign_convention": (
            "cos(-grad_train_loss, grad(-validation_loss)) equals "
            "cos(grad_train_loss, grad_validation_loss); positive predicts improvement"
        ),
        "aggregate_gradient_weighting": "supervised_token_count",
        "uncertainty_statistic": "sample_standard_deviation_across_evaluation_records",
        "uncertainty_penalty_coefficient": args.uncertainty_penalty_coefficient,
        "centering_policy": "pi_weighted_after_uncertainty_penalty",
        "state_probability_policy": (
            STATE_PROBABILITY_POLICY
            if distributions_path is not None
            else SMOKE_STATE_PROBABILITY_POLICY
        ),
        "selected_state_count_range": (MINIMUM_STATE_COUNT, MAXIMUM_STATE_COUNT),
        "selected_state_strategy_priority": GRADIENT_STATE_STRATEGY_PRIORITY,
        "maximum_sequence_length": MAX_SEQUENCE_LENGTH,
        "token_audit": token_audit,
        "within_state_target_token_overlap": within_state_token_overlap,
        "cross_state_target_token_overlap": cross_state_token_overlap,
        "token_region_decomposition": token_region_manifest,
        "numeric_policy": {
            "source_support_numeric_contract_hash": support_plan["numeric_contract_hash"],
            "source_support_numeric_profile": support_plan["numeric_profile"],
            "gradient_precision_contract_hash": numeric_contract["contract_hash"],
            "gradient_precision_profile": numeric_contract["selected_profile"],
        },
        "claim_boundary": (
            "Gradient Projection estimates one local, state-homogeneous cold-start AdamW "
            "distribution update. It does not approximate the full Student optimizer path and "
            "cannot influence VTDO until independent rank and distribution gates pass."
        ),
    }
    values["gradient_estimand_id"] = canonical_hash(
        {
            "beneficiary_checkpoint_hash": values["beneficiary_checkpoint_hash"],
            "gradient_estimation_set_id": values["gradient_estimation_set_id"],
            "gradient_validation_set_id": values["gradient_validation_set_id"],
            "gradient_parameter_space": values["gradient_parameter_space"],
            "gradient_signal": values["gradient_signal"],
            "loss_function": values["loss_function"],
            "objective_function": values["objective_function"],
            "aggregate_gradient_weighting": values["aggregate_gradient_weighting"],
            "uncertainty_penalty_coefficient": values["uncertainty_penalty_coefficient"],
            "state_probability_policy": values["state_probability_policy"],
            "selected_state_strategy_priority": values["selected_state_strategy_priority"],
            "current_distribution_contract_hash": values["current_distribution_contract_hash"],
            "state_realization_manifest_hash": values["state_realization_manifest_hash"],
            "task_sampling_contract_hash": values["task_sampling_contract_hash"],
            "gradient_mode_contract_id": values["gradient_mode_contract_id"],
            "local_optimizer_contract": values["local_optimizer_contract"],
            "token_region_manifest_hash": values["token_region_decomposition"]["manifest_hash"],
            "gp_c_objective_gradient_requirement": values["gp_c_objective_gradient_requirement"],
            "numeric_contract_hash": values["numeric_contract_hash"],
        },
        prefix="finance_contribution_gradient_estimand:",
    )
    values["plan_hash"] = canonical_hash(
        values,
        prefix="finance_contribution_gradient_plan:",
    )
    _write_json(output_dir / "plan.json", values)
    print(json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True))


def build_evaluation_gradients(args: argparse.Namespace) -> None:
    gpu_ids = tuple(args.gpu_ids)
    if not gpu_ids or any(gpu_id < 0 for gpu_id in gpu_ids):
        raise ValueError("evaluation gradients require non-negative GPU ids")
    if len(set(gpu_ids)) != len(gpu_ids):
        raise ValueError("evaluation gradients require unique GPU ids")
    import torch
    from safetensors.torch import save_file

    if any(gpu_id >= torch.cuda.device_count() for gpu_id in gpu_ids):
        raise ValueError("evaluation gradient GPU id is not visible to this process")
    torch.cuda.set_device(gpu_ids[0])

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    if plan.get("experiment_version") != GRADIENT_ALIGNMENT_VERSION:
        raise ValueError("evaluation gradients require a current Gradient Projection plan")
    numeric_contract = _replay_numeric_contract(plan)
    if _sha256(Path(plan["source_records_path"])) != plan["source_records_sha256"]:
        raise ValueError("evaluation records changed after Gradient Projection planning")
    if (
        plan["current_distributions_path"] is not None
        and _sha256(Path(plan["current_distributions_path"]))
        != plan["current_distributions_sha256"]
    ):
        raise ValueError("current distributions changed after Gradient Projection planning")
    realization_source = plan["state_realization_manifest"]["source_path"]
    if (
        realization_source is not None
        and _sha256(Path(realization_source)) != plan["state_realization_manifest"]["source_sha256"]
    ):
        raise ValueError("state realizations changed after Gradient Projection planning")
    realization_report_source = plan["state_realization_manifest"]["source_report_path"]
    if (
        realization_report_source is not None
        and _sha256(Path(realization_report_source))
        != plan["state_realization_manifest"]["source_report_sha256"]
    ):
        raise ValueError("state realization report changed after Gradient Projection planning")
    _seed_everything(args.numeric_seed)
    _configure_numeric_policy(numeric_contract["selected_profile"])
    for gpu_id in gpu_ids:
        torch.cuda.reset_peak_memory_stats(gpu_id)
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = (
        _sharded_baseline_lora_model(
            Path(plan["model_dir"]),
            Path(plan["beneficiary_adapter_dir"]),
            device_ids=gpu_ids,
        )
        if len(gpu_ids) > 1
        else _baseline_lora_model(
            Path(plan["model_dir"]),
            Path(plan["beneficiary_adapter_dir"]),
        )
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("Gradient Projection loaded another beneficiary Adapter")
    parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
    _assert_trainable_parameter_precision(parameter_manifest)
    resolved_device_map = (
        _validated_hf_device_map(
            model.get_base_model(),
            allowed_device_ids=gpu_ids,
        )
        if len(gpu_ids) > 1
        else {"": str(gpu_ids[0])}
    )
    source_records = _load_records(Path(plan["source_records_path"]))
    gradient_dir = output_dir / "evaluation_gradients"
    gradient_dir.mkdir(parents=True, exist_ok=True)
    all_record_ids = (
        *plan["gradient_estimation_record_ids"],
        *plan["gradient_validation_record_ids"],
    )
    record_rows: list[dict[str, Any]] = []
    gradients_by_id: dict[str, dict[str, Any]] = {}
    started = time.monotonic()
    for index, record_id in enumerate(all_record_ids):
        gradients, loss, supervised_tokens = _record_gradient(
            model,
            tokenizer,
            source_records[record_id],
            mode="objective_eval",
        )
        path = gradient_dir / f"record_{index:02d}.safetensors"
        save_file(gradients, path)
        gradients_by_id[record_id] = gradients
        record_rows.append(
            {
                "record_id": record_id,
                "file": str(path),
                "sha256": _sha256(path),
                "loss": loss,
                "supervised_tokens": supervised_tokens,
                "gradient_norm": _gradient_norm(gradients),
            }
        )
    aggregate_rows = []
    rows_by_id = {row["record_id"]: row for row in record_rows}
    for split in ("estimation", "validation"):
        record_ids = tuple(plan[f"gradient_{split}_record_ids"])
        weights = [float(rows_by_id[record_id]["supervised_tokens"]) for record_id in record_ids]
        aggregate = _weighted_gradient(
            [gradients_by_id[record_id] for record_id in record_ids],
            weights,
        )
        path = gradient_dir / f"{split}_aggregate.safetensors"
        save_file(aggregate, path)
        aggregate_rows.append(
            {
                "split": split,
                "record_ids": record_ids,
                "weights": weights,
                "file": str(path),
                "sha256": _sha256(path),
                "gradient_norm": _gradient_norm(aggregate),
            }
        )
    peak_memory_by_device = {
        str(gpu_id): int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids
    }
    manifest: dict[str, Any] = {
        "experiment_version": GRADIENT_ALIGNMENT_VERSION,
        "plan_hash": plan["plan_hash"],
        "beneficiary_checkpoint_hash": plan["beneficiary_checkpoint_hash"],
        "beneficiary_adapter_tensor_sha256": plan["beneficiary_adapter_tensor_sha256"],
        "gradient_parameter_space": plan["gradient_parameter_space"],
        "gradient_mode_contract": plan["gradient_mode_contract"],
        "gradient_mode_contract_id": plan["gradient_mode_contract_id"],
        "numeric_contract_hash": plan["numeric_contract_hash"],
        "numeric_profile": numeric_contract["selected_profile"],
        "objective_gradient_mode": plan["gradient_mode_contract"]["objective_gradient_mode"],
        "objective_gradient_evaluation_point": "beneficiary_before_global_pi_update",
        "objective_gradient_role": plan["internal_objective_gradient_role"],
        "parameter_manifest": parameter_manifest,
        "parameter_manifest_hash": parameter_manifest_hash,
        "record_gradients": record_rows,
        "aggregate_gradients": aggregate_rows,
        "numeric_seed": args.numeric_seed,
        "runtime_seconds": time.monotonic() - started,
        "requested_cuda_device_ids": gpu_ids,
        "cuda_visible_devices_env": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "device_placement": ("balanced_sharded" if len(gpu_ids) > 1 else "single_device"),
        "peak_gpu_memory_bytes": max(peak_memory_by_device.values()),
        "peak_gpu_memory_bytes_by_requested_device": peak_memory_by_device,
        "resolved_hf_device_map": resolved_device_map,
        "resolved_hf_device_map_hash": canonical_hash(
            resolved_device_map,
            prefix="finance_gradient_hf_device_map:",
        ),
        "gpu_names": tuple(torch.cuda.get_device_name(gpu_id) for gpu_id in gpu_ids),
        "torch_version": torch.__version__,
    }
    manifest["manifest_hash"] = canonical_hash(
        manifest,
        prefix="finance_contribution_evaluation_gradient_manifest:",
    )
    _write_json(output_dir / "evaluation_gradient_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    del model, gradients_by_id
    gc.collect()
    torch.cuda.empty_cache()


def _load_verified_gradient(path: Path, sha256: str) -> dict[str, Any]:
    from safetensors.torch import load_file

    if not path.is_file() or _sha256(path) != sha256:
        raise ValueError(f"frozen gradient artifact failed integrity replay:{path}")
    return load_file(path, device="cpu")


def _gradient_difference(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    if tuple(left) != tuple(right):
        raise ValueError("gradient difference parameter manifests differ")
    return {name: (left[name] - right[name]).contiguous() for name in left}


def _pairwise_gradient_cosines(gradients: list[dict[str, Any]]) -> list[float]:
    return [_gradient_alignment(left, right)[1] for left, right in combinations(gradients, 2)]


def _numeric_softmax_update(
    probabilities: dict[str, float],
    scores: dict[str, float],
) -> dict[str, float]:
    if not probabilities or set(probabilities) != set(scores):
        raise ValueError("numeric replay update support differs")
    center = sum(probabilities[state_id] * scores[state_id] for state_id in probabilities)
    weights = {
        state_id: probabilities[state_id] * math.exp(scores[state_id] - center)
        for state_id in probabilities
    }
    normalizer = sum(weights.values())
    return {state_id: weights[state_id] / normalizer for state_id in sorted(weights)}


def _numeric_distribution_distance(
    left: dict[str, float],
    right: dict[str, float],
) -> tuple[float, float]:
    if not left or set(left) != set(right):
        raise ValueError("numeric replay distributions differ in support")
    total_variation = 0.5 * sum(abs(left[key] - right[key]) for key in left)
    midpoint = {key: 0.5 * (left[key] + right[key]) for key in left}

    def kl(values: dict[str, float]) -> float:
        return sum(
            values[key] * math.log(values[key] / midpoint[key]) for key in values if values[key] > 0
        )

    return total_variation, 0.5 * (kl(left) + kl(right))


def _numeric_precision_replay(
    rows: list[dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any]:
    if not rows:
        raise ValueError("numeric precision replay requires worker rows")
    by_task_state: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task_state[(str(row["task_id"]), str(row["state_id"]))].append(row)
    task_rows: list[dict[str, Any]] = []
    for task_id in sorted({key[0] for key in by_task_state}):
        probabilities = {
            str(key): float(value)
            for key, value in plan["task_distributions"][task_id]["probabilities"].items()
        }
        full_scores = {
            state_id: statistics.fmean(
                float(row["numeric_full_gp_score"]) for row in by_task_state[(task_id, state_id)]
            )
            for state_id in probabilities
        }
        recomposed_scores = {
            state_id: statistics.fmean(
                float(row["numeric_recomposed_gp_score"])
                for row in by_task_state[(task_id, state_id)]
            )
            for state_id in probabilities
        }
        full_order = tuple(sorted(full_scores, key=lambda key: (-full_scores[key], key)))
        recomposed_order = tuple(
            sorted(recomposed_scores, key=lambda key: (-recomposed_scores[key], key))
        )
        full_update = _numeric_softmax_update(probabilities, full_scores)
        recomposed_update = _numeric_softmax_update(probabilities, recomposed_scores)
        total_variation, jensen_shannon = _numeric_distribution_distance(
            full_update,
            recomposed_update,
        )
        task_rows.append(
            {
                "task_id": task_id,
                "state_count": len(probabilities),
                "rank_agreement": float(full_order == recomposed_order),
                "update_total_variation": total_variation,
                "update_jensen_shannon": jensen_shannon,
            }
        )
    return {
        "maximum_loss_identity_absolute_error": max(
            float(row["loss_identity_absolute_error"]) for row in rows
        ),
        "maximum_gp_score_absolute_delta": max(
            float(row["numeric_gp_score_absolute_delta"]) for row in rows
        ),
        "minimum_task_rank_agreement": min(float(row["rank_agreement"]) for row in task_rows),
        "maximum_update_total_variation": max(
            float(row["update_total_variation"]) for row in task_rows
        ),
        "maximum_update_jensen_shannon": max(
            float(row["update_jensen_shannon"]) for row in task_rows
        ),
        "task_rows": task_rows,
    }


def _gradient_sign_agreement(
    left: dict[str, Any],
    right: dict[str, Any],
) -> float:
    import torch

    if tuple(left) != tuple(right):
        raise ValueError("gradient sign comparison parameter manifests differ")
    matches = 0
    support = 0
    for name in left:
        left_value = left[name]
        right_value = right[name]
        active = (left_value != 0) | (right_value != 0)
        matches += int(torch.sum((torch.sign(left_value) == torch.sign(right_value)) & active))
        support += int(torch.sum(active))
    return matches / support if support else 1.0


def _gradient_sign_saturation_ratio(
    gradient: dict[str, Any],
    *,
    optimizer_epsilon: float,
) -> float:
    import torch

    threshold = 10.0 * optimizer_epsilon
    saturated = 0
    total = 0
    for value in gradient.values():
        saturated += int(torch.sum(torch.abs(value) <= threshold))
        total += value.numel()
    if total == 0:
        raise ValueError("Gradient Projection saturation diagnostic has no parameters")
    return saturated / total


def _cold_start_adamw_update(
    gradient: dict[str, Any],
    *,
    learning_rate: float,
    optimizer_epsilon: float,
    maximum_gradient_norm: float,
) -> dict[str, Any]:
    norm = _gradient_norm(gradient)
    scale = min(1.0, maximum_gradient_norm / norm)
    return {
        name: (
            learning_rate * (value * scale) / (value.abs() * scale + optimizer_epsilon)
        ).contiguous()
        for name, value in gradient.items()
    }


def _state_realization_diagnostics(
    gradients: list[dict[str, Any]],
    mean_gradient: dict[str, Any],
    *,
    learning_rate: float,
    optimizer_epsilon: float,
    maximum_gradient_norm: float,
) -> dict[str, Any]:
    if not gradients:
        raise ValueError("state gradient diagnostics require realizations")
    mean_norm = _gradient_norm(mean_gradient)
    squared_deviations = [
        _gradient_distance_norm(_gradient_difference(value, mean_gradient)) ** 2
        for value in gradients
    ]
    gradient_norms = [_gradient_norm(value) for value in gradients]
    pairwise_cosines = _pairwise_gradient_cosines(gradients)
    sign_agreements = [
        _gradient_sign_agreement(left, right) for left, right in combinations(gradients, 2)
    ]
    updates = [
        _cold_start_adamw_update(
            value,
            learning_rate=learning_rate,
            optimizer_epsilon=optimizer_epsilon,
            maximum_gradient_norm=maximum_gradient_norm,
        )
        for value in gradients
    ]
    update_cosines = _pairwise_gradient_cosines(updates)
    sum_norm_squared = (len(gradients) * mean_norm) ** 2
    sum_individual_norm_squared = sum(value * value for value in gradient_norms)
    gradient_ess = (
        sum_norm_squared / sum_individual_norm_squared if sum_individual_norm_squared > 0 else 0.0
    )
    if len(gradients) >= 2:
        ordered = list(gradients)
        left = _weighted_gradient(ordered[::2], [1.0] * len(ordered[::2]))
        right = _weighted_gradient(ordered[1::2], [1.0] * len(ordered[1::2]))
        split_half_cosine = _gradient_alignment(left, right)[1]
    else:
        split_half_cosine = 1.0
    return {
        "realization_count": len(gradients),
        "within_state_gradient_variance_ratio": (
            statistics.fmean(squared_deviations) / (mean_norm * mean_norm)
        ),
        "gradient_effective_sample_size": gradient_ess,
        "mean_pairwise_gradient_cosine": (
            statistics.fmean(pairwise_cosines) if pairwise_cosines else 1.0
        ),
        "minimum_pairwise_gradient_cosine": min(pairwise_cosines, default=1.0),
        "split_half_mean_gradient_cosine": split_half_cosine,
        "mean_pairwise_gradient_sign_agreement": (
            statistics.fmean(sign_agreements) if sign_agreements else 1.0
        ),
        "mean_sign_saturation_ratio": statistics.fmean(
            _gradient_sign_saturation_ratio(
                value,
                optimizer_epsilon=optimizer_epsilon,
            )
            for value in gradients
        ),
        "mean_pairwise_update_vector_cosine": (
            statistics.fmean(update_cosines) if update_cosines else 1.0
        ),
        "minimum_pairwise_update_vector_cosine": min(update_cosines, default=1.0),
    }


def _aggregate_state_realizations(
    output_dir: Path,
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    from safetensors.torch import save_file

    by_state: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_state[(str(row["task_id"]), str(row["state_id"]))].append(row)
    expected_counts = {
        (str(task_id), str(state_id)): int(count)
        for task_id, state_id, count in plan["state_realization_manifest"]["realization_counts"]
    }
    if set(by_state) != set(expected_counts) or any(
        len(values) != expected_counts[key] for key, values in by_state.items()
    ):
        raise ValueError("Gradient Projection realization rows changed support")
    record_gradients, aggregate_gradients = _load_gradient_artifacts(manifest)
    record_gradient_norms = {
        str(row["record_id"]): float(row["gradient_norm"]) for row in manifest["record_gradients"]
    }
    aggregate_gradient_norms = {
        str(row["split"]): float(row["gradient_norm"]) for row in manifest["aggregate_gradients"]
    }
    mean_dir = output_dir / "state_mean_gradients"
    mean_dir.mkdir(parents=True, exist_ok=True)
    state_rows: list[dict[str, Any]] = []
    optimizer = plan["local_optimizer_contract"]
    for (task_id, state_id), values in sorted(by_state.items()):
        values.sort(key=lambda row: str(row["realization_id"]))
        gradients = [
            _load_verified_gradient(
                Path(str(row["state_gradient_file"])),
                str(row["state_gradient_sha256"]),
            )
            for row in values
        ]
        mean_gradient = _weighted_gradient(gradients, [1.0] * len(gradients))
        key = hashlib.sha256(f"{task_id}|{state_id}".encode()).hexdigest()[:24]
        mean_path = mean_dir / f"state_{key}.safetensors"
        save_file(mean_gradient, mean_path)
        mean_sha256 = _sha256(mean_path)
        state_artifact_id = canonical_hash(
            {
                "task_id": task_id,
                "state_id": state_id,
                "realization_ids": tuple(str(row["realization_id"]) for row in values),
                "mean_gradient_sha256": mean_sha256,
                "gradient_mode_contract_id": plan["gradient_mode_contract_id"],
            },
            prefix="finance_state_mean_gradient_artifact:",
        )
        diagnostics = _state_realization_diagnostics(
            gradients,
            mean_gradient,
            learning_rate=float(optimizer["learning_rate"]),
            optimizer_epsilon=float(optimizer["epsilon"]),
            maximum_gradient_norm=float(optimizer["maximum_gradient_norm"]),
        )
        state_norm = _gradient_norm(mean_gradient)
        split_values: dict[str, dict[str, Any]] = {}
        for split in ("estimation", "validation"):
            record_ids = tuple(str(value) for value in plan[f"gradient_{split}_record_ids"])
            alignments = []
            directional_dots = []
            for record_id in record_ids:
                dot, cosine = _normalized_gradient_alignment(
                    mean_gradient,
                    record_gradients[record_id],
                    left_norm=state_norm,
                    right_norm=record_gradient_norms[record_id],
                )
                alignments.append(cosine)
                directional_dots.append(dot)
            aggregate_dot, aggregate_cosine = _normalized_gradient_alignment(
                mean_gradient,
                aggregate_gradients[split],
                left_norm=state_norm,
                right_norm=aggregate_gradient_norms[split],
            )
            split_values[split] = {
                "record_ids": record_ids,
                "record_alignments": alignments,
                "record_directional_dots": directional_dots,
                "aggregate_alignment": aggregate_cosine,
                "aggregate_directional_dot": aggregate_dot,
                "objective_gradient_norm": aggregate_gradient_norms[split],
            }
        state_rows.append(
            {
                "task_id": task_id,
                "task_type": values[0]["task_type"],
                "state_id": state_id,
                "state_artifact_id": state_artifact_id,
                "strategy": values[0]["strategy"],
                "source_distribution_id": values[0]["source_distribution_id"],
                "realization_ids": tuple(str(row["realization_id"]) for row in values),
                "realization_job_ids": tuple(str(row["job_id"]) for row in values),
                "realization_result_hashes": tuple(str(row["result_hash"]) for row in values),
                "realization_gradient_artifacts": tuple(
                    {
                        "realization_id": str(row["realization_id"]),
                        "file": str(row["state_gradient_file"]),
                        "sha256": str(row["state_gradient_sha256"]),
                        "loss": float(row["state_loss"]),
                        "supervised_tokens": int(row["state_supervised_tokens"]),
                        "common_token_gradient": {
                            "file": str(row["common_token_gradient_file"]),
                            "sha256": str(row["common_token_gradient_sha256"]),
                            "loss": float(row["common_token_loss"]),
                            "supervised_tokens": int(row["common_token_supervised_tokens"]),
                        },
                        "differential_token_gradient": {
                            "file": str(row["differential_token_gradient_file"]),
                            "sha256": str(row["differential_token_gradient_sha256"]),
                            "loss": float(row["differential_token_loss"]),
                            "supervised_tokens": int(row["differential_token_supervised_tokens"]),
                        },
                    }
                    for row in values
                ),
                "state_loss_mean": statistics.fmean(float(row["state_loss"]) for row in values),
                "state_supervised_tokens_mean": statistics.fmean(
                    float(row["state_supervised_tokens"]) for row in values
                ),
                "state_gradient_file": str(mean_path),
                "state_gradient_sha256": mean_sha256,
                "state_gradient_norm": state_norm,
                "minimum_record_differential_supervised_token_fraction": min(
                    float(row["differential_supervised_token_fraction"]) for row in values
                ),
                "mean_common_token_gradient_norm_ratio": statistics.fmean(
                    float(row["common_gradient_norm_ratio"]) for row in values
                ),
                "mean_differential_token_gradient_norm_ratio": statistics.fmean(
                    float(row["differential_gradient_norm_ratio"]) for row in values
                ),
                "minimum_differential_token_gradient_fraction": min(
                    float(row["differential_gradient_fraction"]) for row in values
                ),
                "maximum_token_gradient_recomposition_relative_error": max(
                    float(row["token_gradient_recomposition_relative_error"]) for row in values
                ),
                "minimum_token_gradient_recomposition_cosine": min(
                    float(row["token_gradient_recomposition_cosine"]) for row in values
                ),
                **diagnostics,
                "estimation_record_ids": split_values["estimation"]["record_ids"],
                "estimation_record_alignments": split_values["estimation"]["record_alignments"],
                "estimation_record_directional_dots": split_values["estimation"][
                    "record_directional_dots"
                ],
                "estimation_aggregate_alignment": split_values["estimation"]["aggregate_alignment"],
                "estimation_aggregate_directional_dot": split_values["estimation"][
                    "aggregate_directional_dot"
                ],
                "estimation_objective_gradient_norm": split_values["estimation"][
                    "objective_gradient_norm"
                ],
                "validation_record_ids": split_values["validation"]["record_ids"],
                "validation_record_alignments": split_values["validation"]["record_alignments"],
                "validation_record_directional_dots": split_values["validation"][
                    "record_directional_dots"
                ],
                "validation_aggregate_alignment": split_values["validation"]["aggregate_alignment"],
                "validation_aggregate_directional_dot": split_values["validation"][
                    "aggregate_directional_dot"
                ],
                "validation_objective_gradient_norm": split_values["validation"][
                    "objective_gradient_norm"
                ],
            }
        )
    return state_rows


def _freeze_distribution_gradient_artifacts(
    output_dir: Path,
    grouped: dict[str, list[dict[str, Any]]],
    task_distributions: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, float]]:
    from safetensors.torch import save_file

    if not grouped:
        raise ValueError("cannot freeze an empty distribution gradient")
    task_dir = output_dir / "task_gradients"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_marginal = 1.0 / len(grouped)
    task_marginals = {task_id: task_marginal for task_id in sorted(grouped)}
    task_artifacts: list[dict[str, Any]] = []
    global_gradient: dict[str, Any] | None = None
    for task_id, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: str(row["state_id"]))
        probabilities = _current_state_probabilities(
            [str(row["state_id"]) for row in ordered],
            probabilities={
                str(key): float(value)
                for key, value in task_distributions[task_id]["probabilities"].items()
            },
        )
        state_gradients = [
            _load_verified_gradient(
                Path(str(row["state_gradient_file"])),
                str(row["state_gradient_sha256"]),
            )
            for row in ordered
        ]
        task_gradient = _weighted_gradient(
            state_gradients,
            [probabilities[str(row["state_id"])] for row in ordered],
        )
        for row, state_gradient in zip(ordered, state_gradients, strict=True):
            difference = _gradient_difference(state_gradient, task_gradient)
            row["state_vs_task_mean_differential_gradient_ratio"] = _gradient_distance_norm(
                difference
            ) / _gradient_norm(state_gradient)
        task_key = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:24]
        path = task_dir / f"task_{task_key}.safetensors"
        save_file(task_gradient, path)
        task_artifacts.append(
            {
                "task_id": task_id,
                "current_probabilities": probabilities,
                "file": str(path),
                "sha256": _sha256(path),
                "gradient_norm": _gradient_norm(task_gradient),
            }
        )
        if global_gradient is None:
            global_gradient = {
                name: value.new_zeros(value.shape) for name, value in task_gradient.items()
            }
        for name, value in task_gradient.items():
            global_gradient[name].add_(value, alpha=task_marginal)
        del state_gradients, task_gradient
    if global_gradient is None:
        raise ValueError("global distribution gradient was not constructed")
    global_path = output_dir / "global_distribution_gradient.safetensors"
    save_file(global_gradient, global_path)
    global_artifact = {
        "task_marginal_policy": "uniform_over_selected_tasks",
        "task_marginals": task_marginals,
        "file": str(global_path),
        "sha256": _sha256(global_path),
        "gradient_norm": _gradient_norm(global_gradient),
    }
    return task_artifacts, global_artifact, task_marginals


def _load_gradient_artifacts(
    manifest: dict[str, Any],
    *,
    device: str = "cpu",
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    from safetensors.torch import load_file

    record_gradients = {}
    for row in manifest["record_gradients"]:
        path = Path(row["file"])
        if _sha256(path) != row["sha256"]:
            raise ValueError("evaluation record gradient changed after freezing")
        record_gradients[str(row["record_id"])] = load_file(path, device=device)
    aggregate_gradients = {}
    for row in manifest["aggregate_gradients"]:
        path = Path(row["file"])
        if _sha256(path) != row["sha256"]:
            raise ValueError("aggregate evaluation gradient changed after freezing")
        aggregate_gradients[str(row["split"])] = load_file(path, device=device)
    return record_gradients, aggregate_gradients


def _worker(
    plan_path: str,
    *,
    gpu_id: int,
    partition_index: int,
    partition_count: int,
) -> dict[str, Any]:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    import torch
    from safetensors.torch import save_file

    plan = _read_json(Path(plan_path))
    if plan.get("experiment_version") != GRADIENT_ALIGNMENT_VERSION:
        raise ValueError("Gradient Projection worker requires a current plan")
    numeric_contract = _replay_numeric_contract(plan)
    output_dir = Path(plan_path).parent
    manifest = _read_json(output_dir / "evaluation_gradient_manifest.json")
    if manifest.get("plan_hash") != plan["plan_hash"]:
        raise ValueError("evaluation gradients belong to another plan")
    if _sha256(Path(plan["target_records_path"])) != plan["target_records_sha256"]:
        raise ValueError("target records changed after Gradient Projection planning")
    if manifest.get("gradient_mode_contract_id") != plan["gradient_mode_contract_id"]:
        raise ValueError("Gradient Projection mode contract changed after freezing")
    worker_path = output_dir / "workers" / f"partition_{partition_index}.jsonl"
    completed: set[str] = set()
    for row in _load_jsonl(worker_path):
        if row.get("status") != "passed":
            continue
        gradient_file = row.get("state_gradient_file")
        gradient_sha256 = row.get("state_gradient_sha256")
        region_artifacts = tuple(
            (row.get(f"{region}_gradient_file"), row.get(f"{region}_gradient_sha256"))
            for region in ("common_token", "differential_token")
        )
        valid = (
            isinstance(gradient_file, str)
            and isinstance(gradient_sha256, str)
            and _valid_hashed_row(row, prefix="finance_contribution_gradient_result:")
            and Path(gradient_file).is_file()
            and _sha256(Path(gradient_file)) == gradient_sha256
            and all(
                isinstance(path, str)
                and isinstance(sha256, str)
                and Path(path).is_file()
                and _sha256(Path(path)) == sha256
                for path, sha256 in region_artifacts
            )
        )
        if not valid:
            raise ValueError("Gradient Projection resume artifact failed integrity replay")
        completed.add(str(row["job_id"]))
    jobs = [
        job for index, job in enumerate(plan["jobs"]) if index % partition_count == partition_index
    ]
    state_gradient_dir = output_dir / "state_gradients"
    state_gradient_dir.mkdir(parents=True, exist_ok=True)
    common_gradient_dir = output_dir / "common_token_gradients"
    common_gradient_dir.mkdir(parents=True, exist_ok=True)
    differential_gradient_dir = output_dir / "differential_token_gradients"
    differential_gradient_dir.mkdir(parents=True, exist_ok=True)
    records = _load_records(Path(plan["target_records_path"]))
    _seed_everything(20260840 + partition_index)
    _configure_numeric_policy(numeric_contract["selected_profile"])
    torch.cuda.reset_peak_memory_stats()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(plan["beneficiary_adapter_dir"]),
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("Gradient Projection worker loaded another beneficiary Adapter")
    parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
    _assert_trainable_parameter_precision(parameter_manifest)
    if parameter_manifest_hash != manifest["parameter_manifest_hash"]:
        raise ValueError("Gradient Projection parameter space changed after freezing")
    if parameter_manifest != manifest["parameter_manifest"]:
        raise ValueError("Gradient Projection parameter manifest failed exact replay")
    validation_aggregate_rows = [
        row
        for row in manifest["aggregate_gradients"]
        if str(row.get("split")) == "validation"
    ]
    if len(validation_aggregate_rows) != 1:
        raise ValueError("Gradient Projection requires one validation aggregate gradient")
    validation_aggregate_row = validation_aggregate_rows[0]
    numeric_objective_gradient = _load_verified_gradient(
        Path(str(validation_aggregate_row["file"])),
        str(validation_aggregate_row["sha256"]),
    )
    numeric_objective_gradient_norm = _gradient_norm(numeric_objective_gradient)
    completed_now = 0
    started = time.monotonic()
    for job in jobs:
        if job["job_id"] in completed:
            continue
        gradient_seed = int(job["gradient_seed"])
        token_regions = plan["token_region_decomposition"]["records"][job["record_id"]]
        common_positions = tuple(int(value) for value in token_regions["common_label_positions"])
        differential_positions = tuple(
            int(value) for value in token_regions["differential_label_positions"]
        )
        _seed_everything(gradient_seed)
        _configure_numeric_policy(numeric_contract["selected_profile"])
        (
            (state_gradient, state_loss, supervised_tokens),
            (common_gradient, common_loss, common_tokens),
            (differential_gradient, differential_loss, differential_tokens),
        ) = _record_gradient_decomposition(
            model,
            tokenizer,
            records[job["record_id"]],
            common_label_positions=common_positions,
            differential_label_positions=differential_positions,
        )
        if common_tokens + differential_tokens != supervised_tokens:
            raise ValueError("token-gradient decomposition changed supervised support")
        decomposition = _token_gradient_decomposition_metrics(
            state_gradient,
            common_gradient,
            differential_gradient,
            common_token_count=common_tokens,
            differential_token_count=differential_tokens,
        )
        recomposed_gradient = _weighted_gradient(
            [common_gradient, differential_gradient],
            [float(common_tokens), float(differential_tokens)],
        )
        _, full_gp_score = _normalized_gradient_alignment(
            state_gradient,
            numeric_objective_gradient,
            left_norm=_gradient_norm(state_gradient),
            right_norm=numeric_objective_gradient_norm,
        )
        _, recomposed_gp_score = _normalized_gradient_alignment(
            recomposed_gradient,
            numeric_objective_gradient,
            left_norm=_gradient_norm(recomposed_gradient),
            right_norm=numeric_objective_gradient_norm,
        )
        recomposed_loss = (
            common_tokens * common_loss + differential_tokens * differential_loss
        ) / supervised_tokens
        state_gradient_path = state_gradient_dir / f"{job['job_id']}.safetensors"
        save_file(state_gradient, state_gradient_path)
        state_gradient_sha256 = _sha256(state_gradient_path)
        state_gradient_norm = _gradient_norm(state_gradient)
        common_gradient_path = common_gradient_dir / f"{job['job_id']}.safetensors"
        differential_gradient_path = differential_gradient_dir / f"{job['job_id']}.safetensors"
        save_file(common_gradient, common_gradient_path)
        save_file(differential_gradient, differential_gradient_path)
        result = {
            **job,
            "experiment_version": GRADIENT_ALIGNMENT_VERSION,
            "plan_hash": plan["plan_hash"],
            "evaluation_gradient_manifest_hash": manifest["manifest_hash"],
            "gradient_mode_contract_id": plan["gradient_mode_contract_id"],
            "numeric_contract_hash": plan["numeric_contract_hash"],
            "state_gradient_mode": "train",
            "gpu_id": gpu_id,
            "partition_index": partition_index,
            "partition_count": partition_count,
            "status": "passed",
            "state_loss": state_loss,
            "state_gradient_file": str(state_gradient_path),
            "state_gradient_sha256": state_gradient_sha256,
            "state_gradient_norm": state_gradient_norm,
            "state_supervised_tokens": supervised_tokens,
            "common_token_loss": common_loss,
            "common_token_supervised_tokens": common_tokens,
            "common_token_gradient_file": str(common_gradient_path),
            "common_token_gradient_sha256": _sha256(common_gradient_path),
            "differential_token_loss": differential_loss,
            "differential_token_supervised_tokens": differential_tokens,
            "differential_supervised_token_fraction": (differential_tokens / supervised_tokens),
            "differential_token_gradient_file": str(differential_gradient_path),
            "differential_token_gradient_sha256": _sha256(differential_gradient_path),
            "loss_identity_absolute_error": abs(state_loss - recomposed_loss),
            "numeric_full_gp_score": full_gp_score,
            "numeric_recomposed_gp_score": recomposed_gp_score,
            "numeric_gp_score_absolute_delta": abs(full_gp_score - recomposed_gp_score),
            **decomposition,
        }
        result["result_hash"] = canonical_hash(
            result,
            prefix="finance_contribution_gradient_result:",
        )
        _append_jsonl(worker_path, result)
        del state_gradient, common_gradient, differential_gradient, recomposed_gradient
        completed_now += 1
    report = {
        "gpu_id": gpu_id,
        "partition_index": partition_index,
        "partition_count": partition_count,
        "job_count": len(jobs),
        "completed_before_resume": len(completed),
        "completed_now": completed_now,
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
    }
    del model, numeric_objective_gradient
    gc.collect()
    torch.cuda.empty_cache()
    return report


def run(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan_path = output_dir / "plan.json"
    plan = _read_json(plan_path)
    if not args.gpu_ids or len(set(args.gpu_ids)) != len(args.gpu_ids):
        raise ValueError("Gradient Projection requires unique GPU ids")
    partition_count = min(len(args.gpu_ids), len(plan["jobs"]))
    context = multiprocessing.get_context("spawn")
    reports = []
    with ProcessPoolExecutor(max_workers=partition_count, mp_context=context) as executor:
        futures = {
            executor.submit(
                _worker,
                str(plan_path),
                gpu_id=gpu_id,
                partition_index=index,
                partition_count=partition_count,
            ): (gpu_id, index)
            for index, gpu_id in enumerate(args.gpu_ids[:partition_count])
        }
        for future in as_completed(futures):
            reports.append(future.result())
    summary = {
        "plan_hash": plan["plan_hash"],
        "workers": sorted(reports, key=lambda item: item["partition_index"]),
    }
    _write_json(output_dir / "worker_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    numeric_contract = _replay_numeric_contract(plan)
    manifest = _read_json(output_dir / "evaluation_gradient_manifest.json")
    if manifest.get("numeric_contract_hash") != numeric_contract["contract_hash"]:
        raise ValueError("evaluation gradients use another numeric contract")
    rows = [
        row
        for path in sorted((output_dir / "workers").glob("*.jsonl"))
        for row in _load_jsonl(path)
    ]
    if len(rows) != len(plan["jobs"]):
        raise ValueError(f"Gradient Projection matrix is incomplete:{len(rows)}")
    if any(
        not _valid_hashed_row(row, prefix="finance_contribution_gradient_result:") for row in rows
    ):
        raise ValueError("Gradient Projection result identity failed replay")
    if any(
        not Path(str(row["state_gradient_file"])).is_file()
        or _sha256(Path(str(row["state_gradient_file"]))) != str(row["state_gradient_sha256"])
        for row in rows
    ):
        raise ValueError("Gradient Projection state gradient failed integrity replay")
    if any(
        not Path(str(row[f"{region}_gradient_file"])).is_file()
        or _sha256(Path(str(row[f"{region}_gradient_file"])))
        != str(row[f"{region}_gradient_sha256"])
        for row in rows
        for region in ("common_token", "differential_token")
    ):
        raise ValueError("Gradient Projection token-region gradient failed integrity replay")
    if {row["plan_hash"] for row in rows} != {plan["plan_hash"]}:
        raise ValueError("Gradient Projection rows cross plans")
    if {row["evaluation_gradient_manifest_hash"] for row in rows} != {manifest["manifest_hash"]}:
        raise ValueError("Gradient Projection rows cross evaluation gradients")
    if {row.get("numeric_contract_hash") for row in rows} != {numeric_contract["contract_hash"]}:
        raise ValueError("Gradient Projection rows cross numeric contracts")
    if len({str(row["job_id"]) for row in rows}) != len(rows):
        raise ValueError("Gradient Projection matrix contains duplicate jobs")
    if len({str(row["realization_id"]) for row in rows}) != len(rows):
        raise ValueError("Gradient Projection matrix contains duplicate realizations")
    state_rows = _aggregate_state_realizations(output_dir, rows, manifest, plan)
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in state_rows:
        grouped[str(row["task_id"])].append(row)
    task_rows = []
    task_vectors = []
    task_distribution_hashes = {}
    penalty = float(plan["uncertainty_penalty_coefficient"])
    minimum_replicates = (
        PRODUCTION_MINIMUM_RECORDS_PER_SPLIT
        if plan["run_role"] == "production_candidate"
        else SMOKE_MINIMUM_RECORDS_PER_SPLIT
    )
    for task_id, values in sorted(grouped.items()):
        values.sort(key=lambda row: str(row["state_id"]))
        probabilities = _current_state_probabilities(
            [str(row["state_id"]) for row in values],
            probabilities={
                str(key): float(value)
                for key, value in plan["task_distributions"][task_id]["probabilities"].items()
            },
        )
        _attach_centered_signal(
            values,
            split="estimation",
            penalty_coefficient=penalty,
            probabilities=probabilities,
            minimum_replicates=minimum_replicates,
        )
        _attach_centered_signal(
            values,
            split="validation",
            penalty_coefficient=penalty,
            probabilities=probabilities,
            minimum_replicates=minimum_replicates,
        )
        estimation = [float(row["estimation_conservative_centered_contribution"]) for row in values]
        validation = [float(row["validation_conservative_centered_contribution"]) for row in values]
        state_ids = [str(row["state_id"]) for row in values]
        distribution_hash = contribution_current_distribution_hash(task_id, probabilities)
        if distribution_hash != plan["task_distribution_hashes"][task_id]:
            raise ValueError("Gradient Projection task distribution changed during aggregation")
        task_distribution_hashes[task_id] = distribution_hash
        task_rows.append(
            {
                "task_id": task_id,
                "task_type": values[0]["task_type"],
                "state_count": len(values),
                "current_distribution_hash": distribution_hash,
                "spearman": _spearman(estimation, validation),
                "pairwise_concordance": _pairwise_concordance(estimation, validation),
                "winner_agreement": float(
                    _winner(estimation, state_ids) == _winner(validation, state_ids)
                ),
            }
        )
        task_vectors.append((estimation, validation))
    task_gradient_artifacts, global_gradient_artifact, task_marginals = (
        _freeze_distribution_gradient_artifacts(
            output_dir,
            grouped,
            plan["task_distributions"],
        )
    )
    distribution_gradient_manifest_hash = canonical_hash(
        {"tasks": task_gradient_artifacts, "global": global_gradient_artifact},
        prefix="finance_distribution_gradient_manifest:",
    )
    spearman_values = [float(row["spearman"]) for row in task_rows]
    concordance_values = [float(row["pairwise_concordance"]) for row in task_rows]
    winner_values = [float(row["winner_agreement"]) for row in task_rows]
    sensitivity_rows = []
    for coefficient in PENALTY_SENSITIVITY_GRID:
        task_spearman = []
        task_concordance = []
        for values in grouped.values():
            estimation = [
                float(row["estimation_aggregate_alignment"])
                - coefficient * statistics.stdev(row["estimation_record_alignments"])
                for row in values
            ]
            validation = [
                float(row["validation_aggregate_alignment"])
                - coefficient * statistics.stdev(row["validation_record_alignments"])
                for row in values
            ]
            task_spearman.append(_spearman(estimation, validation))
            task_concordance.append(_pairwise_concordance(estimation, validation))
        sensitivity_rows.append(
            {
                "penalty_coefficient": coefficient,
                "macro_task_spearman": statistics.fmean(task_spearman),
                "macro_pairwise_concordance": statistics.fmean(task_concordance),
            }
        )
    numeric_replay = _numeric_precision_replay(rows, plan)
    realization_diagnostics = {
        "mean_within_state_gradient_variance_ratio": statistics.fmean(
            float(row["within_state_gradient_variance_ratio"]) for row in state_rows
        ),
        "mean_gradient_effective_sample_size": statistics.fmean(
            float(row["gradient_effective_sample_size"]) for row in state_rows
        ),
        "mean_pairwise_gradient_cosine": statistics.fmean(
            float(row["mean_pairwise_gradient_cosine"]) for row in state_rows
        ),
        "mean_split_half_gradient_cosine": statistics.fmean(
            float(row["split_half_mean_gradient_cosine"]) for row in state_rows
        ),
        "mean_pairwise_gradient_sign_agreement": statistics.fmean(
            float(row["mean_pairwise_gradient_sign_agreement"]) for row in state_rows
        ),
        "mean_sign_saturation_ratio": statistics.fmean(
            float(row["mean_sign_saturation_ratio"]) for row in state_rows
        ),
        "mean_pairwise_update_vector_cosine": statistics.fmean(
            float(row["mean_pairwise_update_vector_cosine"]) for row in state_rows
        ),
        "mean_state_differential_gradient_ratio": statistics.fmean(
            float(row["state_vs_task_mean_differential_gradient_ratio"]) for row in state_rows
        ),
        "minimum_record_differential_supervised_token_fraction": min(
            float(row["minimum_record_differential_supervised_token_fraction"])
            for row in state_rows
        ),
        "minimum_task_pooled_differential_supervised_token_fraction": float(
            plan["token_region_decomposition"][
                "minimum_observed_task_pooled_differential_supervised_token_fraction"
            ]
        ),
        "mean_common_token_gradient_norm_ratio": statistics.fmean(
            float(row["mean_common_token_gradient_norm_ratio"]) for row in state_rows
        ),
        "mean_differential_token_gradient_norm_ratio": statistics.fmean(
            float(row["mean_differential_token_gradient_norm_ratio"]) for row in state_rows
        ),
        "minimum_differential_gradient_fraction": min(
            float(row["minimum_differential_token_gradient_fraction"]) for row in state_rows
        ),
        "maximum_token_gradient_recomposition_relative_error": max(
            float(row["maximum_token_gradient_recomposition_relative_error"]) for row in state_rows
        ),
        "minimum_token_gradient_recomposition_cosine": min(
            float(row["minimum_token_gradient_recomposition_cosine"]) for row in state_rows
        ),
        **{key: float(value) for key, value in numeric_replay.items() if key != "task_rows"},
    }
    realization_thresholds = _realization_stability_thresholds(plan)
    numeric_threshold_names = {
        "maximum_loss_identity_absolute_error",
        "maximum_token_gradient_recomposition_relative_error",
        "minimum_token_gradient_recomposition_cosine",
        "maximum_gp_score_absolute_delta",
        "minimum_task_rank_agreement",
        "maximum_update_total_variation",
        "maximum_update_jensen_shannon",
    }
    numeric_thresholds = {
        name: value
        for name, value in realization_thresholds.items()
        if name in numeric_threshold_names
    }
    sampling_thresholds = {
        name: value
        for name, value in realization_thresholds.items()
        if name not in numeric_threshold_names
    }

    def thresholds_pass(thresholds: dict[str, float]) -> bool:
        passed = True
        for name, threshold in thresholds.items():
            metric_name = name
            if metric_name not in realization_diagnostics:
                metric_name = name.removeprefix("minimum_").removeprefix("maximum_")
            value = realization_diagnostics[metric_name]
            passed = passed and (
                value >= threshold if name.startswith("minimum_") else value <= threshold
            )
        return passed

    numeric_precision_passed = thresholds_pass(numeric_thresholds)
    realization_sampling_passed = thresholds_pass(sampling_thresholds)
    realization_stability_passed = numeric_precision_passed and realization_sampling_passed
    numeric_precision_evidence = {
        "numeric_contract_hash": numeric_contract["contract_hash"],
        "thresholds": numeric_thresholds,
        "metrics": {name: realization_diagnostics[name] for name in numeric_threshold_names},
        "task_rows": numeric_replay["task_rows"],
        "status": "passed" if numeric_precision_passed else "failed",
    }
    numeric_precision_evidence["evidence_hash"] = canonical_hash(
        numeric_precision_evidence,
        prefix="finance_gradient_numeric_precision_replay:",
    )
    sampling_stability_evidence = {
        "thresholds": sampling_thresholds,
        "metrics": realization_diagnostics,
        "status": "passed" if realization_sampling_passed else "failed",
    }
    sampling_stability_evidence["evidence_hash"] = canonical_hash(
        sampling_stability_evidence,
        prefix="finance_gradient_realization_sampling_stability:",
    )
    realization_stability_evidence = {
        "numeric_contract_hash": numeric_contract["contract_hash"],
        "thresholds": realization_thresholds,
        "metrics": realization_diagnostics,
        "numeric_task_rows": numeric_replay["task_rows"],
        "status": "passed" if realization_stability_passed else "failed",
    }
    realization_stability_evidence["evidence_hash"] = canonical_hash(
        realization_stability_evidence,
        prefix="finance_gradient_realization_stability:",
    )
    report: dict[str, Any] = {
        "experiment_version": GRADIENT_ALIGNMENT_VERSION,
        "plan_hash": plan["plan_hash"],
        "gradient_estimand_id": plan["gradient_estimand_id"],
        "evaluation_gradient_manifest_hash": manifest["manifest_hash"],
        "run_role": plan["run_role"],
        "gradient_parameter_space": plan["gradient_parameter_space"],
        "gradient_signal": plan["gradient_signal"],
        "gradient_replicate_kind": plan["gradient_replicate_kind"],
        "sign_convention": plan["sign_convention"],
        "gradient_estimation_set_id": plan["gradient_estimation_set_id"],
        "gradient_validation_set_id": plan["gradient_validation_set_id"],
        "final_test_set_id": plan["final_test_set_id"],
        "task_count": len(task_rows),
        "state_count": len(state_rows),
        "state_realization_count": len(rows),
        "state_realization_manifest_hash": plan["state_realization_manifest_hash"],
        "token_region_manifest_hash": plan["token_region_decomposition"]["manifest_hash"],
        "all_state_realizations_fresh_and_verified": plan["state_realization_manifest"][
            "all_fresh_independently_verified"
        ],
        "evaluation_records_per_split": len(plan["gradient_estimation_record_ids"]),
        "uncertainty_penalty_coefficient": penalty,
        "state_probability_policy": plan["state_probability_policy"],
        "gradient_mode_contract_id": plan["gradient_mode_contract_id"],
        "numeric_contract_hash": numeric_contract["contract_hash"],
        "numeric_profile": numeric_contract["selected_profile"],
        "task_sampling_contract_hash": plan["task_sampling_contract_hash"],
        "local_optimizer_contract": plan["local_optimizer_contract"],
        "internal_objective_gradient_role": plan["internal_objective_gradient_role"],
        "gp_c_objective_gradient_requirement": plan["gp_c_objective_gradient_requirement"],
        "task_distribution_hashes": task_distribution_hashes,
        "task_marginal_policy": "uniform_over_selected_tasks",
        "task_marginals": task_marginals,
        "task_gradient_artifacts": task_gradient_artifacts,
        "global_gradient_artifact": global_gradient_artifact,
        "distribution_gradient_manifest_hash": distribution_gradient_manifest_hash,
        "distribution_gradient_role": "exact_one_step_full_distribution_intervention_input",
        "current_distribution_contract_hash": contribution_distribution_contract_hash(
            task_distribution_hashes
        ),
        "macro_task_spearman": statistics.fmean(spearman_values),
        "macro_task_spearman_ci95": _cluster_bootstrap_interval(
            spearman_values,
            samples=5000,
            seed=20260841,
        ),
        "macro_pairwise_concordance": statistics.fmean(concordance_values),
        "macro_pairwise_concordance_ci95": _cluster_bootstrap_interval(
            concordance_values,
            samples=5000,
            seed=20260842,
        ),
        "winner_agreement_rate": statistics.fmean(winner_values),
        "macro_spearman_p_value": _permutation_p_value(
            task_vectors,
            statistic="spearman",
            iterations=10000,
            seed=20260843,
        ),
        "macro_pairwise_concordance_p_value": _permutation_p_value(
            task_vectors,
            statistic="concordance",
            iterations=10000,
            seed=20260844,
        ),
        "penalty_sensitivity_role": "diagnostic_only",
        "penalty_sensitivity_rows": sensitivity_rows,
        "state_realization_diagnostics": realization_diagnostics,
        "gradient_numeric_precision": numeric_precision_evidence,
        "gradient_realization_sampling_stability": sampling_stability_evidence,
        "gradient_realization_stability": realization_stability_evidence,
        "gradient_diagnostics_hash": realization_stability_evidence["evidence_hash"],
        "target_token_overlap_diagnostics": {
            "within_state": plan["within_state_target_token_overlap"],
            "cross_state": plan["cross_state_target_token_overlap"],
        },
        "task_rows": task_rows,
        "state_rows": state_rows,
        "status": "partial",
        "production_authorized": False,
        "blockers": [
            *(
                []
                if plan["state_realization_manifest"]["all_fresh_independently_verified"]
                else ["fresh_state_realizations_not_used"]
            ),
            *([] if numeric_precision_passed else ["gradient_numeric_precision_failed"]),
            *([] if realization_sampling_passed else ["gradient_realization_sampling_instability"]),
            "post_global_update_gp_c_not_run",
            "independent_local_distribution_intervention_not_run",
        ],
        "claim_boundary": plan["claim_boundary"],
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_contribution_gradient_report:",
    )
    _write_json(output_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate VTDO Contribution with first-order Gradient Projection"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--artifacts-path", required=True)
    prepare_parser.add_argument("--source-support-dir", required=True)
    prepare_parser.add_argument("--numeric-contract-path", required=True)
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument("--current-distributions-path")
    prepare_parser.add_argument("--state-realizations-path")
    prepare_parser.add_argument("--state-realization-report-path")
    prepare_parser.add_argument("--task-sampling-salt", required=True)
    prepare_parser.add_argument("--task-count", type=int, default=30)
    prepare_parser.add_argument("--run-role", choices=RUN_ROLES, required=True)
    prepare_parser.add_argument(
        "--allow-uniform-smoke-distribution",
        action="store_true",
    )
    prepare_parser.add_argument("--numeric-seed", type=int, default=20260840)
    prepare_parser.add_argument("--local-learning-rate", type=float, default=2e-4)
    prepare_parser.add_argument("--optimizer-epsilon", type=float, default=1e-8)
    prepare_parser.add_argument("--maximum-gradient-norm", type=float, default=1.0)
    prepare_parser.add_argument("--uncertainty-penalty-coefficient", type=float, default=1.0)
    prepare_parser.set_defaults(handler=prepare)
    gradients_parser = subparsers.add_parser("build-evaluation-gradients")
    gradients_parser.add_argument("--output-dir", required=True)
    gradients_parser.add_argument("--gpu-ids", type=int, nargs="+", required=True)
    gradients_parser.add_argument("--numeric-seed", type=int, default=20260840)
    gradients_parser.set_defaults(handler=build_evaluation_gradients)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--gpu-ids", type=int, nargs="+", default=(0, 3, 4, 5, 6, 7))
    run_parser.set_defaults(handler=run)
    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("--output-dir", required=True)
    aggregate_parser.set_defaults(handler=aggregate)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
