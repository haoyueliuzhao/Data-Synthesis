from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

from .multistate import FinanceTaskStateArtifact
from .schema import VTDO_EXPERIMENT_VERSION, ExternalBenchmarkSnapshot


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BenchmarkExample(FrozenModel):
    example_id: str = Field(min_length=1)
    benchmark_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    gold_answer: Any
    split: str = "evaluation"
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkPrediction(FrozenModel):
    benchmark_id: str = Field(min_length=1)
    example_id: str = Field(min_length=1)
    prediction: Any
    contract_success: bool = True


class BenchmarkSliceResult(FrozenModel):
    benchmark_id: str = Field(min_length=1)
    example_count: int = Field(ge=1)
    prediction_count: int = Field(ge=0)
    contract_success_count: int = Field(ge=0)
    correct_count: int = Field(ge=0)
    contract_success_rate: float = Field(ge=0, le=1)
    semantic_accuracy_given_valid_contract: float | None = Field(default=None, ge=0, le=1)
    end_to_end_accuracy: float = Field(ge=0, le=1)
    wilson_ci95: tuple[float, float]


class BenchmarkEvaluationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    slices: tuple[BenchmarkSliceResult, ...]
    total_example_count: int = Field(ge=0)
    total_prediction_count: int = Field(ge=0)
    status: str
    blockers: tuple[str, ...]
    schema_version: str = VTDO_EXPERIMENT_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> BenchmarkEvaluationReport:
        if self.status not in {"passed", "blocked"}:
            raise ValueError("unknown benchmark evaluation status")
        if self.report_id != benchmark_evaluation_report_id(self):
            raise ValueError("benchmark evaluation report identity is invalid")
        return self


class BenchmarkLeakageCollision(FrozenModel):
    benchmark_id: str
    example_id: str
    task_id: str
    collision_types: tuple[str, ...]
    text_similarity: float = Field(ge=0, le=1)


class BenchmarkLeakageAudit(FrozenModel):
    report_id: str = Field(min_length=1)
    benchmark_example_count: int = Field(ge=0)
    training_task_count: int = Field(ge=0)
    collision_count: int = Field(ge=0)
    collisions: tuple[BenchmarkLeakageCollision, ...]
    status: str
    blockers: tuple[str, ...] = ()
    schema_version: str = VTDO_EXPERIMENT_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> BenchmarkLeakageAudit:
        if self.status not in {"passed", "failed", "not_configured"}:
            raise ValueError("unknown benchmark leakage status")
        if self.collision_count != len(self.collisions):
            raise ValueError("benchmark leakage collision count is inconsistent")
        if self.report_id != benchmark_leakage_audit_id(self):
            raise ValueError("benchmark leakage audit identity is invalid")
        return self


def load_benchmark_examples(
    snapshots: tuple[ExternalBenchmarkSnapshot, ...],
) -> tuple[BenchmarkExample, ...]:
    examples: list[BenchmarkExample] = []
    for snapshot in snapshots:
        initial_count = len(examples)
        payload = _load_json_or_jsonl(snapshot.path)
        if snapshot.benchmark_id == "finqa":
            examples.extend(_finqa_examples(payload))
        elif snapshot.benchmark_id == "tat_qa":
            examples.extend(_tat_qa_examples(payload))
        elif snapshot.benchmark_id == "financebench":
            examples.extend(_financebench_examples(payload))
        else:  # pragma: no cover - ExternalBenchmarkSnapshot is a closed Literal
            raise ValueError(f"unsupported benchmark adapter: {snapshot.benchmark_id}")
        if len(examples) == initial_count:
            raise ValueError(f"external benchmark snapshot is empty: {snapshot.benchmark_id}")
    identifiers = {(item.benchmark_id, item.example_id) for item in examples}
    if len(identifiers) != len(examples):
        raise ValueError("external benchmark contains duplicate example identities")
    return tuple(sorted(examples, key=lambda item: (item.benchmark_id, item.example_id)))


def audit_external_benchmark_leakage(
    snapshots: tuple[ExternalBenchmarkSnapshot, ...],
    artifacts: Iterable[FinanceTaskStateArtifact],
) -> BenchmarkLeakageAudit:
    tasks = tuple(artifacts)
    if not snapshots:
        return _leakage_report((), tasks, (), status="not_configured")
    try:
        examples = load_benchmark_examples(snapshots)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _leakage_report(
            (),
            tasks,
            (),
            status="failed",
            blockers=(f"benchmark_adapter_failed:{type(error).__name__}",),
        )
    training_signatures = tuple(_training_signature(item) for item in tasks)
    collisions: list[BenchmarkLeakageCollision] = []
    for example in examples:
        benchmark_signature = _benchmark_signature(example)
        for training in training_signatures:
            collision_types: list[str] = []
            similarity = _token_jaccard(
                benchmark_signature["normalized_prompt"],
                training["normalized_prompt"],
            )
            if benchmark_signature["exact_prompt_hash"] == training["exact_prompt_hash"]:
                collision_types.append("exact_prompt")
            if (
                similarity >= 0.92
                and benchmark_signature["operation_signature"]
                == training["operation_signature"]
            ):
                collision_types.append("near_prompt_and_operation")
            for key in (
                "subject_ids",
                "evidence_ids",
                "source_record_ids",
                "document_hashes",
                "binding_ids",
            ):
                if benchmark_signature[key] & training[key]:
                    collision_types.append(key.removesuffix("s") + "_overlap")
            if collision_types:
                collisions.append(
                    BenchmarkLeakageCollision(
                        benchmark_id=example.benchmark_id,
                        example_id=example.example_id,
                        task_id=str(training["task_id"]),
                        collision_types=tuple(sorted(set(collision_types))),
                        text_similarity=similarity,
                    )
                )
    return _leakage_report(
        examples,
        tasks,
        tuple(collisions),
        status="failed" if collisions else "passed",
    )


def evaluate_external_benchmark_predictions(
    snapshots: tuple[ExternalBenchmarkSnapshot, ...],
    prediction_path: Path,
) -> BenchmarkEvaluationReport:
    blockers: list[str] = []
    try:
        examples = load_benchmark_examples(snapshots)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        examples = ()
        blockers.append(f"benchmark_adapter_failed:{type(error).__name__}")
    predictions: tuple[BenchmarkPrediction, ...] = ()
    if not prediction_path.is_file():
        blockers.append(f"benchmark_prediction_file_missing:{prediction_path}")
    else:
        predictions = tuple(
            BenchmarkPrediction.model_validate_json(line)
            for line in prediction_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    prediction_map = {(item.benchmark_id, item.example_id): item for item in predictions}
    if len(prediction_map) != len(predictions):
        blockers.append("duplicate_benchmark_prediction")
    example_keys = {(item.benchmark_id, item.example_id) for item in examples}
    unknown = set(prediction_map) - example_keys
    if unknown:
        blockers.append(f"unknown_benchmark_predictions:{len(unknown)}")

    by_benchmark: defaultdict[str, list[BenchmarkExample]] = defaultdict(list)
    for example in examples:
        by_benchmark[example.benchmark_id].append(example)
    slices: list[BenchmarkSliceResult] = []
    for benchmark_id, benchmark_examples in sorted(by_benchmark.items()):
        observed = [
            prediction_map[(benchmark_id, item.example_id)]
            for item in benchmark_examples
            if (benchmark_id, item.example_id) in prediction_map
        ]
        valid = [item for item in observed if item.contract_success]
        correct = sum(
            _answer_matches(
                prediction_map[(benchmark_id, item.example_id)].prediction,
                item.gold_answer,
                item.metadata,
            )
            for item in benchmark_examples
            if (benchmark_id, item.example_id) in prediction_map
            and prediction_map[(benchmark_id, item.example_id)].contract_success
        )
        total = len(benchmark_examples)
        slices.append(
            BenchmarkSliceResult(
                benchmark_id=benchmark_id,
                example_count=total,
                prediction_count=len(observed),
                contract_success_count=len(valid),
                correct_count=correct,
                contract_success_rate=len(valid) / total,
                semantic_accuracy_given_valid_contract=(
                    correct / len(valid) if valid else None
                ),
                end_to_end_accuracy=correct / total,
                wilson_ci95=_wilson_interval(correct, total),
            )
        )
        if len(observed) != total:
            blockers.append(
                f"benchmark_prediction_coverage_incomplete:{benchmark_id}:"
                f"{len(observed)}!={total}"
            )
    report_values = {
        "slices": tuple(slices),
        "total_example_count": len(examples),
        "total_prediction_count": len(predictions),
        "status": "blocked" if blockers else "passed",
        "blockers": tuple(sorted(set(blockers))),
        "schema_version": VTDO_EXPERIMENT_VERSION,
    }
    provisional = BenchmarkEvaluationReport.model_construct(
        report_id="pending",
        **report_values,
    )
    return BenchmarkEvaluationReport(
        report_id=benchmark_evaluation_report_id(provisional),
        **report_values,
    )


def benchmark_evaluation_report_id(value: BenchmarkEvaluationReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="benchmark_evaluation_report:",
    )


def benchmark_leakage_audit_id(value: BenchmarkLeakageAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="benchmark_leakage_audit:",
    )


def _leakage_report(
    examples: Iterable[BenchmarkExample],
    tasks: Iterable[FinanceTaskStateArtifact],
    collisions: tuple[BenchmarkLeakageCollision, ...],
    *,
    status: str,
    blockers: tuple[str, ...] = (),
) -> BenchmarkLeakageAudit:
    example_values = tuple(examples)
    task_values = tuple(tasks)
    values = {
        "benchmark_example_count": len(example_values),
        "training_task_count": len(task_values),
        "collision_count": len(collisions),
        "collisions": collisions,
        "status": status,
        "blockers": blockers,
        "schema_version": VTDO_EXPERIMENT_VERSION,
    }
    provisional = BenchmarkLeakageAudit.model_construct(report_id="pending", **values)
    return BenchmarkLeakageAudit(
        report_id=benchmark_leakage_audit_id(provisional),
        **values,
    )


def _finqa_examples(payload: Any) -> list[BenchmarkExample]:
    records = payload if isinstance(payload, list) else payload.get("data", [])
    output = []
    for index, item in enumerate(records):
        qa = item.get("qa", item)
        output.append(_example("finqa", qa, index, inherited=item))
    return output


def _tat_qa_examples(payload: Any) -> list[BenchmarkExample]:
    records = payload if isinstance(payload, list) else payload.get("data", [])
    output = []
    for document_index, item in enumerate(records):
        questions = item.get("questions") or item.get("qa") or ()
        if isinstance(questions, Mapping):
            questions = (questions,)
        for question_index, question in enumerate(questions):
            output.append(
                _example(
                    "tat_qa",
                    question,
                    document_index * 1_000_000 + question_index,
                    inherited=item,
                )
            )
    return output


def _financebench_examples(payload: Any) -> list[BenchmarkExample]:
    records = payload if isinstance(payload, list) else payload.get("data", [])
    return [
        _example("financebench", item, index, inherited=item)
        for index, item in enumerate(records)
    ]


def _example(
    benchmark_id: str,
    qa: Mapping[str, Any],
    index: int,
    *,
    inherited: Mapping[str, Any],
) -> BenchmarkExample:
    prompt = qa.get("question") or qa.get("prompt") or qa.get("instruction")
    answer = qa.get("answer")
    if answer is None:
        answer = qa.get("gold_answer", qa.get("response_reference"))
    if not isinstance(prompt, str) or not prompt.strip() or answer is None:
        raise ValueError(f"{benchmark_id} adapter found an incomplete item at index {index}")
    raw_id = qa.get("id") or qa.get("uid") or qa.get("prompt_id")
    example_id = str(raw_id) if raw_id is not None else canonical_hash(
        {"benchmark": benchmark_id, "index": index, "prompt": prompt},
        prefix="benchmark_example:",
    )
    metadata = {
        "program": qa.get("program"),
        "scale": qa.get("scale"),
        "subject_id": qa.get("subject_id") or inherited.get("subject_id"),
        "evidence_id": qa.get("evidence_id") or inherited.get("evidence_id"),
        "source_record_id": qa.get("source_record_id")
        or inherited.get("source_record_id"),
        "document_hash": qa.get("document_hash") or inherited.get("document_hash"),
        "binding_id": qa.get("binding_id") or inherited.get("binding_id"),
    }
    return BenchmarkExample(
        example_id=example_id,
        benchmark_id=benchmark_id,
        prompt=prompt.strip(),
        gold_answer=answer,
        split="evaluation",
        metadata={key: value for key, value in metadata.items() if value is not None},
    )


def _load_json_or_jsonl(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def _training_signature(artifact: FinanceTaskStateArtifact) -> dict[str, Any]:
    public = artifact.omega.task.public
    operators = (
        tuple(node.operator_id for node in public.program_skeleton.nodes)
        if public.program_skeleton is not None
        else ()
    )
    evidence = artifact.omega.public_corpus.evidence
    return {
        "task_id": public.task_id,
        "exact_prompt_hash": canonical_hash(
            _normalize_text(public.instruction),
            prefix="benchmark_prompt:",
        ),
        "normalized_prompt": _slot_normalized_instruction(
            public.instruction,
            public.retrieval_scope,
        ),
        "operation_signature": canonical_hash(operators, prefix="operation_signature:"),
        "subject_ids": {item.subject.subject_id for item in evidence},
        "evidence_ids": {item.evidence_id for item in evidence},
        "source_record_ids": {item.provenance.source_record_id for item in evidence},
        "document_hashes": {
            item.provenance.content_hash for item in evidence if item.provenance.content_hash
        },
        "binding_ids": {artifact.binding_id},
    }


def _benchmark_signature(example: BenchmarkExample) -> dict[str, Any]:
    program = example.metadata.get("program")
    operation_signature = canonical_hash(
        _normalize_program(program),
        prefix="operation_signature:",
    )
    return {
        "exact_prompt_hash": canonical_hash(
            _normalize_text(example.prompt),
            prefix="benchmark_prompt:",
        ),
        "normalized_prompt": _number_normalized_text(example.prompt),
        "operation_signature": operation_signature,
        "subject_ids": _metadata_set(example.metadata, "subject_id"),
        "evidence_ids": _metadata_set(example.metadata, "evidence_id"),
        "source_record_ids": _metadata_set(example.metadata, "source_record_id"),
        "document_hashes": _metadata_set(example.metadata, "document_hash"),
        "binding_ids": _metadata_set(example.metadata, "binding_id"),
    }


def _slot_normalized_instruction(instruction: str, scope: Mapping[str, Any]) -> str:
    normalized = _normalize_text(instruction)
    slots = sorted(
        {
            _normalize_text(value)
            for value in _walk_strings(scope)
            if len(_normalize_text(value)) >= 2
        },
        key=len,
        reverse=True,
    )
    for value in slots:
        normalized = normalized.replace(value, " <slot> ")
    return _number_normalized_text(normalized)


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _walk_strings(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _walk_strings(nested)


def _normalize_program(program: Any) -> tuple[str, ...]:
    if program is None:
        return ()
    if isinstance(program, str):
        return tuple(re.findall(r"[a-zA-Z_]+", program.lower()))
    if isinstance(program, (list, tuple)):
        return tuple(str(item).lower() for item in program)
    return (str(program).lower(),)


def _metadata_set(metadata: Mapping[str, Any], key: str) -> set[str]:
    value = metadata.get(key)
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value}
    return {str(value)}


def _answer_matches(prediction: Any, gold: Any, metadata: Mapping[str, Any]) -> bool:
    if isinstance(gold, (dict, list)):
        return canonical_hash(prediction, prefix="answer:") == canonical_hash(
            gold,
            prefix="answer:",
        )
    prediction_text = str(prediction).strip()
    gold_text = str(gold).strip()
    prediction_numbers = _numbers(prediction_text)
    gold_numbers = _numbers(gold_text)
    if len(prediction_numbers) == len(gold_numbers) == 1:
        tolerance = float(metadata.get("relative_tolerance", 0.01))
        denominator = max(abs(gold_numbers[0]), 1e-12)
        return abs(prediction_numbers[0] - gold_numbers[0]) / denominator <= tolerance
    return _normalize_text(prediction_text) == _normalize_text(gold_text)


def _numbers(value: str) -> tuple[float, ...]:
    return tuple(
        float(item.replace(",", ""))
        for item in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", value)
    )


def _normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[\w%]+", value.casefold()))


def _number_normalized_text(value: str) -> str:
    return re.sub(r"\b\d+(?:\.\d+)?\b", "<number>", _normalize_text(value))


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 1.0


def _wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    z = 1.96
    probability = successes / total
    denominator = 1.0 + z * z / total
    center = (probability + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt(
        probability * (1.0 - probability) / total + z * z / (4.0 * total * total)
    ) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))
