from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.domains.legal.operations import legal_operation_registry
from trusted_synthesis.domains.science.operations import science_operation_registry
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.host_execution import (
    ActionPlanExecutionError,
    execute_action_plan,
    make_host_execution_feedback,
)
from trusted_synthesis.runtime.agent.schema import (
    AgentActionPlanContract,
    AgentAnswerDecisionContract,
    AgentResponseContract,
)

from .data import load_sft_records
from .model_security import validate_adapter_artifact, validate_model_loading_contract
from .schema import CohortEvaluationResult, SFTRecord, TrainingUtilityMVPConfig

TRAINING_UTILITY_EVALUATOR_VERSION = "training_utility_evaluator.v2"


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
    validate_model_loading_contract(config.base_model, config.model_revision)
    if adapter_dir is not None:
        validate_adapter_artifact(adapter_dir)
    records = load_sft_records(evaluation_path)
    if not records or {item.cohort for item in records} != {"evaluation"}:
        raise ValueError("evaluation file must contain only evaluation records")
    output_dir.mkdir(parents=True, exist_ok=True)
    evaluation_hash = canonical_hash(
        tuple(item.record_hash for item in records),
        prefix="training_utility_evaluation_dataset:",
    )
    resolved_adapter_dir = str(adapter_dir.resolve()) if adapter_dir else None
    evaluation_contract = {
        "cohort": cohort,
        "config_hash": config.config_hash,
        "evaluation_dataset_hash": evaluation_hash,
        "adapter_dir": resolved_adapter_dir,
        "evaluator_version": TRAINING_UTILITY_EVALUATOR_VERSION,
    }
    _ensure_evaluation_contract(
        output_dir / "evaluation_contract.json",
        evaluation_contract,
    )
    prediction_path = output_dir / "predictions.jsonl"
    result_path = output_dir / "evaluation_result.json"
    if result_path.is_file() and prediction_path.is_file():
        completed = CohortEvaluationResult.model_validate_json(
            result_path.read_text(encoding="utf-8")
        )
        if (
            completed.status == "completed"
            and completed.cohort == cohort
            and completed.adapter_dir == resolved_adapter_dir
            and completed.evaluation_dataset_hash == evaluation_hash
            and completed.sample_count == len(records)
        ):
            return completed
        raise ValueError(
            "output directory contains a completed result for a different evaluation contract"
        )
    checkpoint_dir = output_dir / "prediction_checkpoints"
    outcomes_by_record_id = _load_evaluation_checkpoints(records, checkpoint_dir)
    shard_index, shard_count = _evaluation_shard_from_environment()
    set_seed(config.seed)
    tokenizer_source = str(adapter_dir) if adapter_dir else config.base_model
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_source,
        revision=None if adapter_dir else config.model_revision,
        use_fast=True,
        trust_remote_code=False,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        config.base_model,
        revision=config.model_revision,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
        trust_remote_code=False,
        use_safetensors=True,
    )
    if adapter_dir is not None:
        model = PeftModel.from_pretrained(model, str(adapter_dir))
    model.to("cuda")
    model.eval()
    model.config.use_cache = True
    model.generation_config.temperature = None
    model.generation_config.top_p = None
    model.generation_config.top_k = None
    for index, record in enumerate(records):
        if index % shard_count != shard_index:
            continue
        if record.record_id in outcomes_by_record_id:
            continue
        if record.training_format == "host_instrumented_joint":
            action_messages = [
                {"role": item.role, "content": item.content} for item in record.messages[:2]
            ]
            action_text, action_tokens, action_latency = _generate_turn(
                tokenizer,
                model,
                torch,
                action_messages,
                max_new_tokens=config.max_new_tokens,
            )
            answer_text = ""
            answer_tokens = 0
            answer_latency = 0.0
            try:
                action = AgentActionPlanContract.model_validate_json(action_text)
                task, evidence = _host_evaluation_context(record)
                trace = execute_action_plan(
                    task,
                    evidence,
                    action,
                    _operation_registry(record.domain),
                )
            except (ValueError, ActionPlanExecutionError):
                pass
            else:
                host_feedback = make_host_execution_feedback(trace)
                answer_messages = [
                    *action_messages,
                    {"role": "assistant", "content": action_text},
                    {
                        "role": "tool",
                        "content": host_feedback.model_dump_json(),
                    },
                ]
                answer_text, answer_tokens, answer_latency = _generate_turn(
                    tokenizer,
                    model,
                    torch,
                    answer_messages,
                    max_new_tokens=config.max_new_tokens,
                )
            outcome = score_host_instrumented_response(
                record,
                action_text,
                answer_text,
                generated_tokens=action_tokens + answer_tokens,
                latency_ms=action_latency + answer_latency,
            )
        else:
            raw_text, generated_tokens, latency_ms = _generate_turn(
                tokenizer,
                model,
                torch,
                [
                    {"role": "system", "content": record.system_prompt},
                    {"role": "user", "content": record.user_prompt},
                ],
                max_new_tokens=config.max_new_tokens,
            )
            outcome = score_generated_response(
                record,
                raw_text,
                generated_tokens=generated_tokens,
                latency_ms=latency_ms,
            )
        outcomes_by_record_id[record.record_id] = outcome
        _write_evaluation_checkpoint(
            checkpoint_dir / f"{index:06d}.json",
            outcome,
        )
    if shard_count > 1:
        if shard_index:
            return _wait_for_sharded_evaluation_result(
                result_path,
                cohort=cohort,
                adapter_dir=resolved_adapter_dir,
                evaluation_hash=evaluation_hash,
                sample_count=len(records),
            )
        outcomes_by_record_id = _wait_for_all_evaluation_checkpoints(
            records,
            checkpoint_dir,
        )
    outcomes = tuple(outcomes_by_record_id[item.record_id] for item in records)
    prediction_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in outcomes),
        encoding="utf-8",
    )
    result = aggregate_evaluation_outcomes(
        cohort=cohort,
        adapter_dir=adapter_dir,
        records=records,
        outcomes=outcomes,
        prediction_path=prediction_path,
    )
    _atomic_write_json(
        result_path,
        result.model_dump(mode="json"),
        indent=2,
    )
    return result


def _generate_turn(
    tokenizer: Any,
    model: Any,
    torch: Any,
    messages: list[dict[str, str]],
    *,
    max_new_tokens: int,
) -> tuple[str, int, float]:
    prompt = tokenizer.apply_chat_template(
        messages,
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
            max_new_tokens=max_new_tokens,
            do_sample=False,
            use_cache=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    latency_ms = (time.monotonic() - started) * 1000
    new_tokens = generated[0, encoded["input_ids"].shape[1] :]
    return (
        tokenizer.decode(new_tokens, skip_special_tokens=True).strip(),
        int(new_tokens.numel()),
        latency_ms,
    )


def _evaluation_shard_from_environment() -> tuple[int, int]:
    try:
        shard_count = int(os.environ.get("TRAINING_UTILITY_EVAL_SHARD_COUNT", "1"))
        shard_index = int(os.environ.get("TRAINING_UTILITY_EVAL_SHARD_INDEX", "0"))
    except ValueError as exc:
        raise ValueError("evaluation shard index and count must be integers") from exc
    if shard_count < 1:
        raise ValueError("evaluation shard count must be at least one")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("evaluation shard index must be within the shard count")
    return shard_index, shard_count


def _wait_for_all_evaluation_checkpoints(
    records: tuple[SFTRecord, ...],
    checkpoint_dir: Path,
    *,
    timeout_seconds: float = 12 * 60 * 60,
) -> dict[str, dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        outcomes = _load_evaluation_checkpoints(records, checkpoint_dir)
        if len(outcomes) == len(records):
            return outcomes
        if time.monotonic() >= deadline:
            raise TimeoutError("timed out waiting for evaluation shards")
        time.sleep(2)


def _wait_for_sharded_evaluation_result(
    result_path: Path,
    *,
    cohort: str,
    adapter_dir: str | None,
    evaluation_hash: str,
    sample_count: int,
    timeout_seconds: float = 12 * 60 * 60,
) -> CohortEvaluationResult:
    deadline = time.monotonic() + timeout_seconds
    while True:
        if result_path.is_file():
            result = CohortEvaluationResult.model_validate_json(
                result_path.read_text(encoding="utf-8")
            )
            if (
                result.status != "completed"
                or result.cohort != cohort
                or result.adapter_dir != adapter_dir
                or result.evaluation_dataset_hash != evaluation_hash
                or result.sample_count != sample_count
            ):
                raise ValueError("primary shard wrote an incompatible evaluation result")
            return result
        if time.monotonic() >= deadline:
            raise TimeoutError("timed out waiting for the primary evaluation shard")
        time.sleep(2)


def _ensure_evaluation_contract(path: Path, expected: dict[str, Any]) -> None:
    if path.is_file():
        observed = json.loads(path.read_text(encoding="utf-8"))
        if observed != expected:
            raise ValueError(
                "output directory contains checkpoints for a different evaluation contract"
            )
        return
    _atomic_write_json(path, expected, indent=2)


def _load_evaluation_checkpoints(
    records: tuple[SFTRecord, ...],
    checkpoint_dir: Path,
) -> dict[str, dict[str, Any]]:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    expected_names = {f"{index:06d}.json" for index in range(len(records))}
    unexpected = sorted(
        item.name for item in checkpoint_dir.glob("*.json") if item.name not in expected_names
    )
    if unexpected:
        raise ValueError(f"unexpected evaluation checkpoint files: {unexpected[:5]}")
    output: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        path = checkpoint_dir / f"{index:06d}.json"
        if not path.is_file():
            continue
        outcome = json.loads(path.read_text(encoding="utf-8"))
        if (
            outcome.get("record_id") != record.record_id
            or outcome.get("task_id") != record.task_id
            or outcome.get("domain") != record.domain
        ):
            raise ValueError(f"evaluation checkpoint {path} does not match its record")
        if record.record_id in output:
            raise ValueError(f"duplicate evaluation checkpoint for {record.record_id}")
        output[record.record_id] = outcome
    return output


def _write_evaluation_checkpoint(path: Path, outcome: dict[str, Any]) -> None:
    _atomic_write_json(path, outcome)


def _atomic_write_json(path: Path, payload: Any, *, indent: int | None = None) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def score_generated_response(
    record: SFTRecord,
    raw_text: str,
    *,
    generated_tokens: int = 0,
    latency_ms: float = 0,
) -> dict[str, Any]:
    if record.training_format == "host_instrumented_joint":
        try:
            payload = json.loads(raw_text)
            action_text = json.dumps(payload["action_plan"], sort_keys=True)
            answer_text = json.dumps(payload["answer_decision"], sort_keys=True)
        except (json.JSONDecodeError, KeyError, TypeError):
            action_text = raw_text
            answer_text = ""
        return score_host_instrumented_response(
            record,
            action_text,
            answer_text,
            generated_tokens=generated_tokens,
            latency_ms=latency_ms,
        )
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
        and _answer_equal(
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
        "action_plan_contract": response_contract,
        "answer_decision_contract": response_contract,
        "host_execution_success": False,
        "host_replay_available": False,
        "execution_replay_valid": False,
    }


def score_host_instrumented_response(
    record: SFTRecord,
    action_text: str,
    answer_text: str,
    *,
    generated_tokens: int = 0,
    latency_ms: float = 0,
) -> dict[str, Any]:
    gold = json.loads(record.assistant_target)
    gold_action = AgentActionPlanContract.model_validate(gold["action_plan"])
    gold_answer = AgentAnswerDecisionContract.model_validate(gold["answer_decision"])
    action_valid_json = False
    answer_valid_json = False
    action_contract = False
    answer_contract = False
    predicted_action: AgentActionPlanContract | None = None
    predicted_answer: AgentAnswerDecisionContract | None = None
    json_errors: list[str] = []
    contract_errors: list[str] = []
    host_error_code: str | None = None
    try:
        action_payload = json.loads(action_text)
        action_valid_json = isinstance(action_payload, dict)
        if action_valid_json:
            predicted_action = AgentActionPlanContract.model_validate(action_payload)
            action_contract = True
    except json.JSONDecodeError as exc:
        json_errors.append(f"action:{exc}")
    except ValueError as exc:
        contract_errors.append(f"action:{str(exc)[:2000]}")
    try:
        answer_payload = json.loads(answer_text)
        answer_valid_json = isinstance(answer_payload, dict)
        if answer_valid_json:
            predicted_answer = AgentAnswerDecisionContract.model_validate(answer_payload)
            answer_contract = True
    except json.JSONDecodeError as exc:
        json_errors.append(f"answer:{exc}")
    except ValueError as exc:
        contract_errors.append(f"answer:{str(exc)[:2000]}")

    host_execution_success = False
    execution_replay_valid = False
    if predicted_action is not None:
        task, evidence = _host_evaluation_context(record)
        try:
            trace = execute_action_plan(
                task,
                evidence,
                predicted_action,
                _operation_registry(record.domain),
            )
        except ActionPlanExecutionError as exc:
            host_error_code = exc.error_code
            contract_errors.append(f"host:{exc.error_code}:{exc}")
        else:
            host_execution_success = True
            actual_feedback = make_host_execution_feedback(trace)
            gold_feedback = json.loads(record.messages[3].content)
            execution_replay_valid = _equal(
                actual_feedback.output_result,
                gold_feedback["output_result"],
            )

    expected_evidence = set(gold_action.selected_evidence_ids)
    observed_evidence = (
        set(predicted_action.selected_evidence_ids) if predicted_action is not None else set()
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
    evidence_exact = expected_evidence == observed_evidence
    execution_coverage, operation_grounding_score = _action_alignment(
        predicted_action,
        gold_action,
    )
    operation_exact = bool(
        predicted_action is not None
        and _action_signature(predicted_action) == _action_signature(gold_action)
    )
    answer_exact = bool(
        predicted_answer is not None and _answer_equal(predicted_answer.result, gold_answer.result)
    )
    citation_exact = bool(
        predicted_answer is not None
        and set(predicted_answer.cited_evidence_ids) == set(gold_answer.cited_evidence_ids)
    )
    response_contract = action_contract and answer_contract
    end_to_end = bool(
        response_contract
        and host_execution_success
        and execution_replay_valid
        and evidence_exact
        and operation_exact
        and answer_exact
        and citation_exact
    )
    user_payload = json.loads(record.user_prompt)
    has_distractors = len(user_payload["evidence_corpus"]) > len(expected_evidence)
    is_multi_hop = len(gold_action.executions) > 1
    failures = []
    for label, passed in (
        ("action_valid_json", action_valid_json),
        ("action_plan_contract", action_contract),
        ("host_execution_success", host_execution_success),
        ("execution_replay_valid", execution_replay_valid),
        ("answer_valid_json", answer_valid_json),
        ("answer_decision_contract", answer_contract),
        ("evidence_exact", evidence_exact),
        ("operation_exact", operation_exact),
        ("answer_exact", answer_exact),
        ("citation_exact", citation_exact),
    ):
        if not passed:
            failures.append(label)
    return {
        "record_id": record.record_id,
        "task_id": record.task_id,
        "domain": record.domain,
        "valid_json": action_valid_json and answer_valid_json,
        "response_contract": response_contract,
        "action_plan_contract": action_contract,
        "answer_decision_contract": answer_contract,
        "host_execution_success": host_execution_success,
        "host_replay_available": host_execution_success,
        "execution_replay_valid": execution_replay_valid,
        "evidence_recall": evidence_recall,
        "evidence_precision": evidence_precision,
        "evidence_exact": evidence_exact,
        "execution_coverage": execution_coverage,
        "operation_grounding_score": operation_grounding_score,
        "tool_necessity_score": 1.0 if host_execution_success else 0.0,
        "operation_exact": operation_exact,
        "answer_exact": answer_exact,
        "citation_exact": citation_exact,
        "verification_exact": execution_replay_valid,
        "is_multi_hop": is_multi_hop,
        "multi_hop_exact": end_to_end if is_multi_hop else None,
        "has_distractors": has_distractors,
        "distractor_robust": evidence_exact if has_distractors else None,
        "end_to_end": end_to_end,
        "generated_tokens": generated_tokens,
        "latency_ms": latency_ms,
        "failure_reasons": failures,
        "json_error": "; ".join(json_errors) or None,
        "contract_error": "; ".join(contract_errors) or None,
        "host_error_code": host_error_code,
        "raw_response": {
            "action_plan": action_text,
            "answer_decision": answer_text,
        },
    }


def _host_evaluation_context(
    record: SFTRecord,
) -> tuple[TaskPublicSpec, tuple[EvidenceItem, ...]]:
    payload = json.loads(record.user_prompt)
    return (
        TaskPublicSpec.model_validate(payload["public_task"]),
        tuple(EvidenceItem.model_validate(item) for item in payload["evidence_corpus"]),
    )


def _operation_registry(domain: str) -> OperationRegistry:
    if domain == "legal":
        return legal_operation_registry()
    if domain == "science":
        return science_operation_registry()
    return default_registry()


def _action_alignment(
    observed: AgentActionPlanContract | None,
    expected: AgentActionPlanContract,
) -> tuple[float, float]:
    if observed is None:
        return 0.0, 0.0
    expected_steps = expected.executions
    observed_steps = observed.executions
    covered = min(len(observed_steps), len(expected_steps)) / len(expected_steps)
    matched = sum(
        _decision_signature(left) == _decision_signature(right)
        for left, right in zip(observed_steps, expected_steps, strict=False)
    )
    return covered, matched / len(expected_steps)


def _action_signature(plan: AgentActionPlanContract) -> str:
    return canonical_hash(
        {
            "selected_evidence_ids": sorted(plan.selected_evidence_ids),
            "executions": [_decision_signature(item) for item in plan.executions],
            "output_step_index": plan.output_step_index,
        },
        prefix="training_utility_action_plan_signature:",
    )


def _decision_signature(value: Any) -> dict[str, Any]:
    return {
        "operator_id": value.operator_id,
        "inputs": [item.model_dump(mode="json") for item in value.inputs],
        "parameters": value.parameters,
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
        "evaluator_version": TRAINING_UTILITY_EVALUATOR_VERSION,
    }
    return CohortEvaluationResult(
        cohort=cohort,
        evaluator_version=TRAINING_UTILITY_EVALUATOR_VERSION,
        adapter_dir=str(adapter_dir.resolve()) if adapter_dir else None,
        evaluation_dataset_hash=evaluation_hash,
        sample_count=len(outcomes),
        valid_json_rate=metrics["valid_json_rate"],
        response_contract_rate=metrics["response_contract_rate"],
        action_plan_contract_rate=metrics["action_plan_contract_rate"],
        answer_decision_contract_rate=metrics["answer_decision_contract_rate"],
        host_execution_success_rate=metrics["host_execution_success_rate"],
        host_replay_available_rate=metrics["host_replay_available_rate"],
        execution_replay_valid_rate=metrics["execution_replay_valid_rate"],
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
        "action_plan_contract_rate": _mean_bool(outcomes, "action_plan_contract"),
        "answer_decision_contract_rate": _mean_bool(
            outcomes,
            "answer_decision_contract",
        ),
        "host_execution_success_rate": _mean_bool(outcomes, "host_execution_success"),
        "host_replay_available_rate": _mean_bool(outcomes, "host_replay_available"),
        "execution_replay_valid_rate": _mean_bool(outcomes, "execution_replay_valid"),
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


def _answer_equal(left: Any, right: Any) -> bool:
    return CandidateAnswerNormalizer().equivalent(left, right)
