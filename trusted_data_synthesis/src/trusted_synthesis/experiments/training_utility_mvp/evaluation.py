from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import AgentResponseContract

from .data import load_sft_records
from .schema import CohortEvaluationResult, SFTRecord, TrainingUtilityMVPConfig


def evaluate_sft_model(
    config: TrainingUtilityMVPConfig,
    cohort: str,
    evaluation_path: Path,
    output_dir: Path,
    *,
    adapter_dir: Path | None = None,
) -> CohortEvaluationResult:
    """Evaluate the base model or one LoRA adapter on the shared hidden task set."""

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "training dependencies are missing; install the project training extra"
        ) from exc
    if not torch.cuda.is_available():
        raise RuntimeError("the Qwen2.5-7B MVP requires a CUDA device")
    records = load_sft_records(evaluation_path)
    if not records or {item.cohort for item in records} != {"evaluation"}:
        raise ValueError("evaluation file must contain only evaluation records")
    output_dir.mkdir(parents=True, exist_ok=True)
    set_seed(config.seed)
    tokenizer_source = str(adapter_dir) if adapter_dir else config.base_model
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_source,
        revision=None if adapter_dir else config.model_revision,
        use_fast=True,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        config.base_model,
        revision=config.model_revision,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    if adapter_dir is not None:
        model = PeftModel.from_pretrained(model, str(adapter_dir))
    model.to("cuda")
    model.eval()
    model.config.use_cache = True
    outcomes = []
    for record in records:
        prompt = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": record.system_prompt},
                {"role": "user", "content": record.user_prompt},
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        encoded = tokenizer(
            prompt,
            add_special_tokens=False,
            return_tensors="pt",
        )
        encoded = {key: value.to("cuda") for key, value in encoded.items()}
        started = time.monotonic()
        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                max_new_tokens=config.max_new_tokens,
                do_sample=False,
                use_cache=True,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        latency_ms = (time.monotonic() - started) * 1000
        new_tokens = generated[0, encoded["input_ids"].shape[1] :]
        raw_text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        outcomes.append(
            score_generated_response(
                record,
                raw_text,
                generated_tokens=int(new_tokens.numel()),
                latency_ms=latency_ms,
            )
        )
    prediction_path = output_dir / "predictions.jsonl"
    prediction_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in outcomes),
        encoding="utf-8",
    )
    result = aggregate_evaluation_outcomes(
        cohort=cohort,
        adapter_dir=adapter_dir,
        records=records,
        outcomes=tuple(outcomes),
        prediction_path=prediction_path,
    )
    (output_dir / "evaluation_result.json").write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def score_generated_response(
    record: SFTRecord,
    raw_text: str,
    *,
    generated_tokens: int = 0,
    latency_ms: float = 0,
) -> dict[str, Any]:
    gold = json.loads(record.assistant_target)
    valid_json = False
    response_contract = False
    predicted: dict[str, Any] | None = None
    json_error: str | None = None
    contract_error: str | None = None
    try:
        loaded = json.loads(raw_text)
        valid_json = isinstance(loaded, dict)
        if valid_json:
            predicted = loaded
            try:
                AgentResponseContract.model_validate(loaded)
                response_contract = True
            except ValueError as exc:
                contract_error = str(exc)[:4000]
        else:
            contract_error = "top-level JSON value is not an object"
    except json.JSONDecodeError as exc:
        json_error = str(exc)

    expected_evidence = set(gold["selected_evidence_ids"])
    observed_evidence = (
        set(predicted.get("selected_evidence_ids", ()))
        if response_contract and predicted is not None
        else set()
    )
    evidence_recall = (
        len(expected_evidence & observed_evidence) / len(expected_evidence)
        if expected_evidence
        else 1.0
    )
    evidence_precision = (
        len(expected_evidence & observed_evidence) / len(observed_evidence)
        if observed_evidence
        else 0.0
    )
    gold_steps = gold["execution_trace"]["steps"]
    predicted_steps = (
        predicted["execution_trace"]["steps"] if response_contract and predicted is not None else []
    )
    execution_coverage, operation_grounding_score, tool_necessity_score = _execution_alignment(
        predicted_steps, gold_steps
    )
    operation_exact = bool(
        response_contract
        and predicted is not None
        and _execution_signature(predicted_steps) == _execution_signature(gold_steps)
    )
    answer_exact = bool(
        response_contract
        and predicted is not None
        and _equal(
            predicted["final_answer"].get("result"),
            gold["final_answer"].get("result"),
        )
    )
    citation_exact = bool(
        response_contract
        and predicted is not None
        and _citation_signature(predicted["final_answer"].get("citations", ()))
        == _citation_signature(gold["final_answer"].get("citations", ()))
    )
    verification_exact = bool(
        response_contract
        and predicted is not None
        and _equal(predicted.get("verification_result"), gold.get("verification_result"))
    )
    evidence_exact = expected_evidence == observed_evidence
    end_to_end = bool(
        response_contract
        and evidence_exact
        and execution_coverage == 1.0
        and operation_grounding_score == 1.0
        and tool_necessity_score == 1.0
        and operation_exact
        and answer_exact
        and citation_exact
        and verification_exact
    )
    user_payload = json.loads(record.user_prompt)
    has_distractors = len(user_payload["evidence_corpus"]) > len(expected_evidence)
    is_multi_hop = len(gold_steps) > 1
    failures = []
    for label, passed in (
        ("valid_json", valid_json),
        ("response_contract", response_contract),
        ("evidence_exact", evidence_exact),
        ("execution_coverage", execution_coverage == 1.0),
        ("operation_grounding", operation_grounding_score == 1.0),
        ("tool_necessity", tool_necessity_score == 1.0),
        ("operation_exact", operation_exact),
        ("answer_exact", answer_exact),
        ("citation_exact", citation_exact),
        ("verification_exact", verification_exact),
    ):
        if not passed:
            failures.append(label)
    return {
        "record_id": record.record_id,
        "task_id": record.task_id,
        "domain": record.domain,
        "valid_json": valid_json,
        "response_contract": response_contract,
        "evidence_recall": evidence_recall,
        "evidence_precision": evidence_precision,
        "evidence_exact": evidence_exact,
        "execution_coverage": execution_coverage,
        "operation_grounding_score": operation_grounding_score,
        "tool_necessity_score": tool_necessity_score,
        "operation_exact": operation_exact,
        "answer_exact": answer_exact,
        "citation_exact": citation_exact,
        "verification_exact": verification_exact,
        "is_multi_hop": is_multi_hop,
        "multi_hop_exact": end_to_end if is_multi_hop else None,
        "has_distractors": has_distractors,
        "distractor_robust": evidence_exact if has_distractors else None,
        "end_to_end": end_to_end,
        "generated_tokens": generated_tokens,
        "latency_ms": latency_ms,
        "failure_reasons": failures,
        "json_error": json_error,
        "contract_error": contract_error,
        "raw_response": raw_text,
    }


def aggregate_evaluation_outcomes(
    *,
    cohort: str,
    adapter_dir: Path | None,
    records: tuple[SFTRecord, ...],
    outcomes: tuple[dict[str, Any], ...],
    prediction_path: Path,
) -> CohortEvaluationResult:
    if len(records) != len(outcomes):
        raise ValueError("evaluation records and outcomes do not align")
    evaluation_hash = canonical_hash(
        tuple(item.record_hash for item in records),
        prefix="training_utility_evaluation_dataset:",
    )
    failure_counts = Counter(reason for item in outcomes for reason in item["failure_reasons"])
    domain_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in outcomes:
        domain_rows[item["domain"]].append(item)
    domain_metrics = {
        domain: _outcome_metrics(tuple(rows)) for domain, rows in sorted(domain_rows.items())
    }
    metrics = _outcome_metrics(outcomes)
    identity = {
        "cohort": cohort,
        "adapter_dir": str(adapter_dir.resolve()) if adapter_dir else None,
        "evaluation_dataset_hash": evaluation_hash,
        "prediction_hash": canonical_hash(outcomes, prefix="training_utility_predictions:"),
        "metrics": metrics,
    }
    return CohortEvaluationResult(
        cohort=cohort,
        adapter_dir=str(adapter_dir.resolve()) if adapter_dir else None,
        evaluation_dataset_hash=evaluation_hash,
        sample_count=len(outcomes),
        valid_json_rate=metrics["valid_json_rate"],
        response_contract_rate=metrics["response_contract_rate"],
        evidence_recall=metrics["evidence_recall"],
        evidence_precision=metrics["evidence_precision"],
        execution_coverage=metrics["execution_coverage"],
        operation_grounding_score=metrics["operation_grounding_score"],
        tool_necessity_score=metrics["tool_necessity_score"],
        operation_exact_rate=metrics["operation_exact_rate"],
        answer_exact_rate=metrics["answer_exact_rate"],
        citation_exact_rate=metrics["citation_exact_rate"],
        verification_exact_rate=metrics["verification_exact_rate"],
        tool_success_rate=None,
        multi_hop_exact_rate=metrics["multi_hop_exact_rate"],
        distractor_robustness_rate=metrics["distractor_robustness_rate"],
        end_to_end_rate=metrics["end_to_end_rate"],
        mean_latency_ms=metrics["mean_latency_ms"],
        generated_token_count=sum(item["generated_tokens"] for item in outcomes),
        failure_counts=dict(sorted(failure_counts.items())),
        domain_metrics=domain_metrics,
        prediction_artifact=str(prediction_path.resolve()),
        status="completed",
        result_hash=canonical_hash(identity, prefix="training_utility_eval_result:"),
    )


def _outcome_metrics(outcomes: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    count = len(outcomes)
    multi_hop = tuple(item for item in outcomes if item["is_multi_hop"])
    distractors = tuple(item for item in outcomes if item["has_distractors"])
    return {
        "sample_count": count,
        "valid_json_rate": _mean_bool(outcomes, "valid_json"),
        "response_contract_rate": _mean_bool(outcomes, "response_contract"),
        "evidence_recall": sum(item["evidence_recall"] for item in outcomes) / count,
        "evidence_precision": sum(item["evidence_precision"] for item in outcomes) / count,
        "execution_coverage": sum(item["execution_coverage"] for item in outcomes) / count,
        "operation_grounding_score": sum(item["operation_grounding_score"] for item in outcomes)
        / count,
        "tool_necessity_score": sum(item["tool_necessity_score"] for item in outcomes) / count,
        "operation_exact_rate": _mean_bool(outcomes, "operation_exact"),
        "answer_exact_rate": _mean_bool(outcomes, "answer_exact"),
        "citation_exact_rate": _mean_bool(outcomes, "citation_exact"),
        "verification_exact_rate": _mean_bool(outcomes, "verification_exact"),
        "multi_hop_exact_rate": (
            None if not multi_hop else _mean_bool(multi_hop, "multi_hop_exact")
        ),
        "distractor_robustness_rate": (
            None if not distractors else _mean_bool(distractors, "distractor_robust")
        ),
        "end_to_end_rate": _mean_bool(outcomes, "end_to_end"),
        "mean_latency_ms": sum(item["latency_ms"] for item in outcomes) / count,
    }


def _mean_bool(rows: tuple[dict[str, Any], ...], key: str) -> float:
    return sum(bool(item[key]) for item in rows) / len(rows)


def _execution_alignment(
    observed_steps: Any,
    expected_steps: Any,
) -> tuple[float, float, float]:
    expected = tuple(expected_steps)
    observed = tuple(observed_steps)
    if not expected:
        return 1.0, 1.0, 1.0
    observed_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in observed:
        node_id = item.get("planned_node_id")
        if isinstance(node_id, str):
            observed_by_node[node_id].append(item)
    expected_execution_ids = {
        item.get("execution_id"): item.get("planned_node_id") for item in expected
    }
    observed_execution_ids = {
        item.get("execution_id"): item.get("planned_node_id") for item in observed
    }
    covered = 0
    grounded = 0
    tool_bound = 0
    for expected_step in expected:
        node_id = expected_step.get("planned_node_id")
        matches = observed_by_node.get(node_id, [])
        if len(matches) != 1:
            continue
        observed_step = matches[0]
        succeeded = observed_step.get("status") == "succeeded"
        covered += int(succeeded)
        expected_grounding = _execution_grounding_signature(
            expected_step,
            expected_execution_ids,
        )
        observed_grounding = _execution_grounding_signature(
            observed_step,
            observed_execution_ids,
        )
        grounded += int(succeeded and observed_grounding == expected_grounding)
        tool_bound += int(
            succeeded and observed_step.get("tool_name") == expected_step.get("tool_name")
        )
    denominator = len(expected)
    return covered / denominator, grounded / denominator, tool_bound / denominator


def _execution_signature(steps: Any) -> str:
    observed = tuple(steps)
    execution_ids = {item.get("execution_id"): item.get("planned_node_id") for item in observed}
    normalized = [
        {
            **_execution_grounding_signature(item, execution_ids),
            "observation": item.get("observation"),
            "status": item.get("status"),
        }
        for item in observed
    ]
    return canonical_hash(normalized, prefix="training_utility_execution_signature:")


def _execution_grounding_signature(
    step: dict[str, Any],
    execution_ids: dict[Any, Any],
) -> dict[str, Any]:
    return {
        "planned_node_id": step.get("planned_node_id"),
        "operator_id": step.get("operator_id"),
        "tool_name": step.get("tool_name"),
        "input_refs": [
            _normalize_execution_ref(ref, execution_ids) for ref in step.get("input_refs", ())
        ],
        "parameters": step.get("parameters"),
        "evidence_ids": step.get("evidence_ids"),
    }


def _normalize_execution_ref(ref: Any, execution_ids: dict[Any, Any]) -> Any:
    if not isinstance(ref, str) or not ref.startswith("execution:"):
        return ref
    execution_id, separator, selector = ref.removeprefix("execution:").partition("#")
    node_id = execution_ids.get(execution_id, execution_id)
    suffix = f"#{selector}" if separator else ""
    return f"operation:{node_id}{suffix}"


def _citation_signature(citations: Any) -> str:
    return canonical_hash(
        tuple(
            sorted(
                (dict(item) for item in citations),
                key=lambda item: canonical_hash(item, prefix="citation_order:"),
            )
        ),
        prefix="training_utility_citation_signature:",
    )


def _equal(left: Any, right: Any) -> bool:
    return canonical_hash(left, prefix="value:") == canonical_hash(right, prefix="value:")
