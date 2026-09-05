"""Independent mask/mass controls; all producers are forbidden during each audit."""

from __future__ import annotations

import ast
import copy
from collections.abc import Iterator
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import adapter, engine
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import independent as pilot_audit
from trusted_synthesis.experiments.qa_reasoning_share_quotient_measurement import (
    independent as quotient_audit,
)
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import (
    independent,
    inputs,
    loss,
    models,
    tokenization,
    weights,
)
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.safety import (
    offline_cpu_guard,
)

ROOT = Path(__file__).resolve().parents[2]


def _forbidden(*args: Any, **kwargs: Any) -> None:
    raise AssertionError("the independent audit must not invoke a training-package producer")


@pytest.fixture(scope="module")
def package() -> Iterator[dict[str, Any]]:
    with offline_cpu_guard(), pytest.MonkeyPatch.context() as guard:
        guard.setattr(engine.ModelProtocolEngine, "__init__", _forbidden)
        guard.setattr(engine.ModelProtocolEngine, "exchange", _forbidden)
        guard.setattr(adapter.DeepSeekAdapter, "perform", _forbidden)
        guard.setattr(adapter.CurlTransport, "send", _forbidden)
        guard.setattr(adapter.MockTransport, "send", _forbidden)
        for executor in (
            engine.RelationSumExecutor,
            engine.ShareRatioExecutor,
            engine.ScalePercentExecutor,
        ):
            guard.setattr(executor, "execute", _forbidden)
        guard.setattr(pilot_audit, "audit_session", _forbidden)
        guard.setattr(pilot_audit, "audit_records", _forbidden)
        guard.setattr(quotient_audit, "audit_measurement", _forbidden)
        original = inputs.load_inputs(ROOT)
        binding = tokenization.register_tokenizer(ROOT)
        contract = models.representation_contract(binding)
        dataset = inputs.export_rows(original, contract)
        tokens = models.record(
            "tokenized_dataset",
            dataset_id=dataset["id"],
            tokenizer_binding_id=binding["id"],
            representation_contract_id=contract["id"],
            rows=tokenization.tokenize_rows(dataset["rows"], binding),
            truncated=False,
            target_mask_policy="exact original assistant content only",
        )
        kernel = weights.build_kernel(original, dataset, tokens)
        batch, arrays, _ = loss.collate(tokens, binding["pad_token_id"])
        views = weights.build_views(original, dataset, tokens, kernel, batch)
        yield {
            "inputs": original,
            "contract": contract,
            "dataset": dataset,
            "tokens": tokens,
            "kernel": kernel,
            "batch": batch,
            "arrays": arrays,
            "views": views,
        }
        inputs.assert_unchanged(ROOT, original)


@pytest.fixture(autouse=True)
def forbid_every_package_producer(
    monkeypatch: pytest.MonkeyPatch,
    package: dict[str, Any],
) -> None:
    monkeypatch.setattr(inputs, "export_rows", _forbidden)
    for module in (tokenization, weights, loss):
        for name, value in tuple(vars(module).items()):
            if callable(value) and getattr(value, "__module__", None) == module.__name__:
                monkeypatch.setattr(module, name, _forbidden)


def _renew(obj: dict[str, Any], **changes: Any) -> dict[str, Any]:
    kind = obj["schema_version"].removeprefix("share_training_").removesuffix(".v1")
    return models.record(
        kind,
        **(
            {key: value for key, value in obj.items() if key not in {"id", "schema_version"}}
            | changes
        ),
    )


def _audit(package: dict[str, Any]) -> dict[str, Any]:
    return independent.audit_training(**package)


def test_actual_tokenized_package_masses_and_no_producer_calls(package: dict[str, Any]) -> None:
    result = _audit(package)
    assert result["passed"] is True
    assert len(result["checks"]) == 5
    assert result["actual_target_token_count"] == 15_939
    assert [item["target_token_count"] for item in result["trajectory_target_token_counts"]] == [
        2812,
        4691,
        2793,
        2817,
        2826,
    ]
    p, q = result["independently_recomputed_masses"]
    assert [models.as_fraction(item["mass"]) for item in p["trajectory_masses"]] == [
        Fraction(1, 5)
    ] * 5
    assert [models.as_fraction(item["mass"]) for item in q["trajectory_masses"]] == [
        Fraction(1, 8),
        Fraction(1, 2),
        Fraction(1, 8),
        Fraction(1, 8),
        Fraction(1, 8),
    ]
    assert result["independent_retokenization_or_decode"] is False
    assert result["loss_implementation_executed_by_this_audit"] is False
    assert result["NPZ_container_bytes_reencoded"] is False
    syntax = ast.parse(Path(independent.__file__).read_text(encoding="utf-8"))
    imports = [node.module or "" for node in ast.walk(syntax) if isinstance(node, ast.ImportFrom)]
    assert not any(
        name in module
        for module in imports
        for name in (
            "tokenization",
            "weights",
            "loss",
            "projection",
            "comparison",
            "adapter",
            "engine",
        )
    )


@pytest.mark.parametrize("change", ["prompt", "suffix", "padding", "double_shift"])
def test_masks_and_labels_cannot_supervise_host_or_shift_twice(
    package: dict[str, Any],
    change: str,
) -> None:
    changed = copy.deepcopy(package)
    token = changed["tokens"]["rows"][0]
    if change == "padding":
        position = token["sequence_length"]
        assert position < changed["arrays"]["labels"].shape[1]
        changed["arrays"]["labels"][0, position] = changed["arrays"]["input_ids"][0, position]
        changed["arrays"]["target_mask"][0, position] = 1
        code = "independent.zero_loss_right_padding"
    elif change == "double_shift":
        position = token["target_token_start"]
        token["labels"][position] = token["input_ids"][position + 1]
        changed["arrays"]["labels"][0, position] = token["labels"][position]
        code = "independent.unshifted_causal_labels"
    else:
        position = (
            token["target_token_start"] - 1 if change == "prompt" else token["target_token_end"]
        )
        token["target_mask"][position] = 1
        token["labels"][position] = token["input_ids"][position]
        changed["arrays"]["target_mask"][0, position] = 1
        changed["arrays"]["labels"][0, position] = token["labels"][position]
        code = "independent.exact_content_only_mask"
    changed["tokens"]["rows"][0] = _renew(token)
    changed["tokens"] = _renew(changed["tokens"])
    with pytest.raises(models.TrainingPreflightError, match=code):
        _audit(changed)


def test_cpu_tensors_must_match_the_bound_tokenized_rows(package: dict[str, Any]) -> None:
    changed = copy.deepcopy(package)
    changed["arrays"]["input_ids"][0, 0] += 1
    with pytest.raises(
        models.TrainingPreflightError, match="independent.base_array_original_tokens"
    ):
        _audit(changed)


def test_trajectory_token_denominator_comes_from_all_actual_masks(package: dict[str, Any]) -> None:
    changed = copy.deepcopy(package)
    changed["kernel"]["trajectories"][0]["target_token_count"] += 1
    changed["kernel"] = _renew(changed["kernel"])
    with pytest.raises(
        models.TrainingPreflightError, match="independent.kernel_complete_trajectory_tokens"
    ):
        _audit(changed)


def test_within_class_total_one_is_not_enough_to_preserve_the_kernel(
    package: dict[str, Any],
) -> None:
    changed = copy.deepcopy(package)
    selected = [
        item
        for item in changed["kernel"]["trajectories"]
        if models.as_fraction(item["within_state_probability"]) == Fraction(1, 4)
    ]
    selected[0]["within_state_probability"] = models.ratio(1, 2)
    for item in selected[1:]:
        item["within_state_probability"] = models.ratio(1, 6)
    assert sum(models.as_fraction(item["within_state_probability"]) for item in selected) == 1
    changed["kernel"] = _renew(changed["kernel"])
    with pytest.raises(
        models.TrainingPreflightError, match="independent.fixed_uniform_within_state_kernel"
    ):
        _audit(changed)


def test_same_class_mass_cannot_hide_changed_within_trajectory_token_weights(
    package: dict[str, Any],
) -> None:
    changed = copy.deepcopy(package)
    view = changed["views"][0]
    first, second = view["row_weights"][:2]
    original = models.as_fraction(first["token_coefficient"])
    t0, t1 = (row["target_token_count"] for row in package["tokens"]["rows"][:2])
    delta = original / 100
    first["token_coefficient"] = models.fraction_record(original + delta)
    second["token_coefficient"] = models.fraction_record(original - delta * Fraction(t0, t1))
    assert (
        models.as_fraction(first["token_coefficient"]) * t0
        + models.as_fraction(second["token_coefficient"]) * t1
    ) == original * (t0 + t1)
    changed["views"][0] = _renew(view)
    with pytest.raises(
        models.TrainingPreflightError, match="independent.fixed_per_target_token_coefficient"
    ):
        _audit(changed)


@pytest.mark.parametrize("normalization", ["equal_rows", "global_tokens"])
def test_unit_total_mass_does_not_justify_row_or_global_token_mean(
    package: dict[str, Any],
    normalization: str,
) -> None:
    changed = copy.deepcopy(package)
    token_counts = [row["target_token_count"] for row in package["tokens"]["rows"]]
    view = changed["views"][0]
    for row, count in zip(view["row_weights"], token_counts, strict=True):
        row["token_coefficient"] = (
            models.ratio(1, len(token_counts) * count)
            if normalization == "equal_rows"
            else models.ratio(1, sum(token_counts))
        )
    assert (
        sum(
            models.as_fraction(row["token_coefficient"]) * count
            for row, count in zip(view["row_weights"], token_counts, strict=True)
        )
        == 1
    )
    changed["views"][0] = _renew(view)
    with pytest.raises(
        models.TrainingPreflightError, match="independent.fixed_per_target_token_coefficient"
    ):
        _audit(changed)


def test_Q_must_share_exact_text_tokenizer_batch_and_row_order(package: dict[str, Any]) -> None:
    for field in ("dataset_id", "tokenizer_binding_id", "base_batch_id", "row_ids"):
        changed = copy.deepcopy(package)
        view = changed["views"][1]
        replacement = (
            list(reversed(view[field])) if field == "row_ids" else "counterfactual:changed"
        )
        changed["views"][1] = _renew(view, **{field: replacement})
        with pytest.raises(
            models.TrainingPreflightError,
            match="independent.shared_representation_only_class_intervention",
        ):
            _audit(changed)
