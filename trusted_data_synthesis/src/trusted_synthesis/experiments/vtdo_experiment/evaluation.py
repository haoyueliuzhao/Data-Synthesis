from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import string
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

from .multistate import FinanceTaskStateArtifact
from .schema import VTDO_EXPERIMENT_VERSION, ExternalBenchmarkSnapshot

BENCHMARK_ADAPTER_VERSION = "native_financial_benchmark_adapter.v4"
BENCHMARK_METRIC_VERSION = "native_financial_benchmark_metric.v4"
_LEAKAGE_REQUIRED_HARD_CHANNELS = (
    "exact_prompt",
    "question_skeleton",
    "document_hash",
)
_QUESTION_SKELETON_METRICS = tuple(
    sorted(
        {
            "operating cash flow",
            "net income",
            "operating income",
            "gross profit",
            "total assets",
            "total liabilities",
            "shareholders equity",
            "revenue",
            "sales",
            "cash",
            "population",
            "margin",
            "growth rate",
            "return on equity",
        },
        key=len,
        reverse=True,
    )
)
_QUESTION_INITIAL_WORDS = {
    "according",
    "calculate",
    "compare",
    "during",
    "from",
    "how",
    "identify",
    "in",
    "report",
    "use",
    "what",
    "when",
    "which",
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BenchmarkExample(FrozenModel):
    example_id: str = Field(min_length=1)
    benchmark_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    question: str = Field(min_length=1)
    gold_answer: Any
    split: str = "evaluation"
    context_hash: str = Field(min_length=1)
    metric_id: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkPrediction(FrozenModel):
    prediction_id: str = Field(min_length=1)
    prediction_run_id: str = Field(min_length=1)
    benchmark_id: str = Field(min_length=1)
    example_id: str = Field(min_length=1)
    answer: Any
    scale: str = ""
    program: str = ""
    contract_success: bool = True
    raw_response_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity(self) -> BenchmarkPrediction:
        if self.prediction_id != benchmark_prediction_id(self):
            raise ValueError("benchmark prediction identity is invalid")
        return self


class BenchmarkSliceResult(FrozenModel):
    benchmark_id: str = Field(min_length=1)
    example_count: int = Field(ge=1)
    prediction_count: int = Field(ge=0)
    contract_success_count: int = Field(ge=0)
    correct_count: int = Field(ge=0)
    answer_correct_count: int = Field(ge=0)
    answer_accuracy: float = Field(ge=0, le=1)
    contract_success_rate: float = Field(ge=0, le=1)
    semantic_accuracy_given_valid_contract: float | None = Field(default=None, ge=0, le=1)
    end_to_end_accuracy: float = Field(ge=0, le=1)
    mean_native_f1: float = Field(ge=0, le=1)
    program_evaluable_count: int = Field(default=0, ge=0)
    program_execution_correct_count: int = Field(default=0, ge=0)
    program_execution_accuracy: float | None = Field(default=None, ge=0, le=1)
    wilson_ci95: tuple[float, float]


class BenchmarkEvaluationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    prediction_run_id: str | None = None
    evaluation_snapshot_hash: str = Field(min_length=1)
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
    severity: str
    text_similarity: float = Field(ge=0, le=1)


class BenchmarkLeakageChannelCoverage(FrozenModel):
    channel_id: str = Field(min_length=1)
    benchmark_nonempty_count: int = Field(ge=0)
    benchmark_total_count: int = Field(ge=0)
    training_nonempty_count: int = Field(ge=0)
    training_total_count: int = Field(ge=0)
    comparable: bool

    @model_validator(mode="after")
    def validate_coverage(self) -> BenchmarkLeakageChannelCoverage:
        if self.benchmark_nonempty_count > self.benchmark_total_count:
            raise ValueError("benchmark channel coverage exceeds its denominator")
        if self.training_nonempty_count > self.training_total_count:
            raise ValueError("training channel coverage exceeds its denominator")
        expected = bool(self.benchmark_nonempty_count and self.training_nonempty_count)
        if self.comparable != expected:
            raise ValueError("leakage channel comparability is inconsistent")
        return self


class BenchmarkLeakageAudit(FrozenModel):
    report_id: str = Field(min_length=1)
    benchmark_example_count: int = Field(ge=0)
    training_task_count: int = Field(ge=0)
    collision_count: int = Field(ge=0)
    hard_collision_count: int = Field(ge=0)
    soft_collision_count: int = Field(ge=0)
    channel_coverage: tuple[BenchmarkLeakageChannelCoverage, ...]
    required_hard_channels: tuple[str, ...]
    unavailable_required_hard_channels: tuple[str, ...]
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
        if self.hard_collision_count + self.soft_collision_count != self.collision_count:
            raise ValueError("benchmark leakage severity accounting is inconsistent")
        coverage_ids = tuple(item.channel_id for item in self.channel_coverage)
        if len(coverage_ids) != len(set(coverage_ids)):
            raise ValueError("benchmark leakage channel coverage is duplicated")
        expected_unavailable = tuple(
            channel
            for channel in self.required_hard_channels
            if channel not in {item.channel_id for item in self.channel_coverage if item.comparable}
        )
        if self.unavailable_required_hard_channels != expected_unavailable:
            raise ValueError("unavailable hard leakage channels are inconsistent")
        if self.status == "passed" and (
            self.hard_collision_count or self.unavailable_required_hard_channels or self.blockers
        ):
            raise ValueError("passed leakage audit is not fail-closed")
        if self.report_id != benchmark_leakage_audit_id(self):
            raise ValueError("benchmark leakage audit identity is invalid")
        return self


def load_benchmark_examples(
    snapshots: tuple[ExternalBenchmarkSnapshot, ...],
) -> tuple[BenchmarkExample, ...]:
    examples: list[BenchmarkExample] = []
    for snapshot in snapshots:
        initial_count = len(examples)
        if not snapshot.path.is_file():
            raise ValueError(f"external benchmark snapshot is missing: {snapshot.benchmark_id}")
        if _sha256(snapshot.path) != snapshot.sha256:
            raise ValueError(f"external benchmark snapshot hash mismatch: {snapshot.benchmark_id}")
        if snapshot.adapter_version != BENCHMARK_ADAPTER_VERSION:
            raise ValueError(
                f"external benchmark adapter version mismatch: {snapshot.benchmark_id}"
            )
        if snapshot.metric_version != BENCHMARK_METRIC_VERSION:
            raise ValueError(f"external benchmark metric version mismatch: {snapshot.benchmark_id}")
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
        for index in range(initial_count, len(examples)):
            examples[index] = examples[index].model_copy(update={"split": snapshot.split})
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
            skeleton_similarity = _token_jaccard(
                benchmark_signature["question_skeleton"],
                training["question_skeleton"],
            )
            if benchmark_signature["exact_prompt_hash"] == training["exact_prompt_hash"]:
                collision_types.append("exact_prompt")
            if (
                similarity >= 0.92
                and benchmark_signature["operation_available"]
                and training["operation_available"]
                and benchmark_signature["operation_signature"] == training["operation_signature"]
            ):
                collision_types.append("near_prompt_and_operation")
            if skeleton_similarity >= 0.94:
                collision_types.append("slot_normalized_question_skeleton")
            if (
                skeleton_similarity >= 0.85
                and benchmark_signature["operation_available"]
                and training["operation_available"]
                and benchmark_signature["operation_signature"] == training["operation_signature"]
            ):
                collision_types.append("slot_normalized_skeleton_and_operation")
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
                hard_types = {
                    "exact_prompt",
                    "near_prompt_and_operation",
                    "slot_normalized_question_skeleton",
                    "slot_normalized_skeleton_and_operation",
                    "evidence_id_overlap",
                    "source_record_id_overlap",
                    "document_hash_overlap",
                    "binding_id_overlap",
                }
                severity = "hard" if hard_types & set(collision_types) else "soft"
                collisions.append(
                    BenchmarkLeakageCollision(
                        benchmark_id=example.benchmark_id,
                        example_id=example.example_id,
                        task_id=str(training["task_id"]),
                        collision_types=tuple(sorted(set(collision_types))),
                        severity=severity,
                        text_similarity=max(similarity, skeleton_similarity),
                    )
                )
    return _leakage_report(
        examples,
        tasks,
        tuple(collisions),
        status="failed" if any(item.severity == "hard" for item in collisions) else "passed",
    )


def evaluate_external_benchmark_predictions(
    snapshots: tuple[ExternalBenchmarkSnapshot, ...],
    prediction_path: Path,
    prediction_manifest_path: Path,
) -> BenchmarkEvaluationReport:
    from .benchmark_prediction import (
        BenchmarkPredictionRunManifest,
        _directory_manifest_hash,
    )
    from .schema import VTDOTrainingRunResult

    blockers: list[str] = []
    manifest: BenchmarkPredictionRunManifest | None = None
    if not prediction_manifest_path.is_file():
        blockers.append(f"benchmark_prediction_manifest_missing:{prediction_manifest_path}")
    else:
        try:
            manifest = BenchmarkPredictionRunManifest.model_validate_json(
                prediction_manifest_path.read_text(encoding="utf-8")
            )
        except (ValueError, json.JSONDecodeError):
            blockers.append("benchmark_prediction_manifest_invalid_or_incomplete")
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
        if manifest is None or manifest.predictions_sha256 != _sha256(prediction_path):
            blockers.append("benchmark_prediction_file_hash_mismatch")
    run_ids = {item.prediction_run_id for item in predictions}
    if len(run_ids) > 1:
        blockers.append("mixed_benchmark_prediction_runs")
    prediction_run_id = next(iter(run_ids), None)
    if prediction_run_id is not None and (
        manifest is None or manifest.prediction_run_id != prediction_run_id
    ):
        blockers.append("benchmark_prediction_run_identity_mismatch")
    expected_snapshot_hash = benchmark_snapshot_manifest_hash(snapshots)
    if manifest is not None:
        if manifest.evaluation_snapshot_hash != expected_snapshot_hash:
            blockers.append("benchmark_prediction_snapshot_identity_mismatch")
        if Path(manifest.predictions_path).resolve() != prediction_path.resolve():
            blockers.append("benchmark_prediction_path_identity_mismatch")
        if manifest.prediction_count != len(predictions):
            blockers.append("benchmark_prediction_manifest_count_mismatch")
        if manifest.contract_success_count != sum(item.contract_success for item in predictions):
            blockers.append("benchmark_contract_success_count_mismatch")
        expected_benchmarks = tuple(sorted(item.benchmark_id for item in snapshots))
        if manifest.benchmark_ids != expected_benchmarks:
            blockers.append("benchmark_prediction_benchmark_set_mismatch")
        if manifest.status != "completed":
            blockers.append("benchmark_prediction_run_not_completed")
        training_result_path = Path(manifest.training_result_path)
        training_result: VTDOTrainingRunResult | None = None
        if not training_result_path.is_file():
            blockers.append("benchmark_training_result_missing")
        elif _sha256(training_result_path) != manifest.training_result_sha256:
            blockers.append("benchmark_training_result_hash_mismatch")
        else:
            try:
                training_result = VTDOTrainingRunResult.model_validate_json(
                    training_result_path.read_text(encoding="utf-8")
                )
            except (ValueError, json.JSONDecodeError):
                blockers.append("benchmark_training_result_invalid")
        if training_result is not None:
            expected_training_identity = {
                "training_result_id": training_result.result_id,
                "arm_id": training_result.arm_id,
                "training_config_hash": training_result.config_hash,
                "training_dataset_hash": training_result.dataset_hash,
                "training_seed": training_result.training_seed,
                "adapter_dir": str(Path(training_result.adapter_dir).resolve()),
                "base_model_ref": training_result.base_model,
                "adapter_manifest_hash": training_result.adapter_manifest_hash,
                "base_model_manifest_hash": training_result.base_model_manifest_hash,
            }
            observed_training_identity = {
                "training_result_id": manifest.training_result_id,
                "arm_id": manifest.arm_id,
                "training_config_hash": manifest.training_config_hash,
                "training_dataset_hash": manifest.training_dataset_hash,
                "training_seed": manifest.training_seed,
                "adapter_dir": str(Path(manifest.adapter_dir).resolve()),
                "base_model_ref": manifest.base_model_ref,
                "adapter_manifest_hash": manifest.adapter_manifest_hash,
                "base_model_manifest_hash": manifest.base_model_manifest_hash,
            }
            if observed_training_identity != expected_training_identity:
                blockers.append("benchmark_training_identity_mismatch")
            adapter_dir = Path(training_result.adapter_dir)
            if not adapter_dir.is_dir():
                blockers.append("benchmark_adapter_directory_missing")
            elif (
                _directory_manifest_hash(adapter_dir, prefix="adapter_manifest:")
                != training_result.adapter_manifest_hash
            ):
                blockers.append("benchmark_adapter_content_hash_mismatch")
            base_path = Path(training_result.base_model).expanduser()
            base_hash = (
                _directory_manifest_hash(base_path, prefix="base_model_manifest:")
                if base_path.is_dir()
                else canonical_hash(
                    {
                        "repository": training_result.base_model,
                        "revision": training_result.model_revision,
                    },
                    prefix="remote_base_model_manifest:",
                )
            )
            if base_hash != training_result.base_model_manifest_hash:
                blockers.append("benchmark_base_model_content_hash_mismatch")
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
        native_scores = [
            _native_answer_metrics(
                item,
                prediction_map[(benchmark_id, item.example_id)],
            )
            for item in benchmark_examples
            if (benchmark_id, item.example_id) in prediction_map
            and prediction_map[(benchmark_id, item.example_id)].contract_success
        ]
        correct = sum(score[0] for score in native_scores)
        native_f1 = sum(score[1] for score in native_scores)
        answer_correct = sum(score[3] for score in native_scores)
        program_scores = [score[2] for score in native_scores if score[2] is not None]
        program_correct = sum(bool(score) for score in program_scores)
        total = len(benchmark_examples)
        slices.append(
            BenchmarkSliceResult(
                benchmark_id=benchmark_id,
                example_count=total,
                prediction_count=len(observed),
                contract_success_count=len(valid),
                correct_count=correct,
                answer_correct_count=answer_correct,
                answer_accuracy=answer_correct / total,
                contract_success_rate=len(valid) / total,
                semantic_accuracy_given_valid_contract=(correct / len(valid) if valid else None),
                end_to_end_accuracy=correct / total,
                mean_native_f1=native_f1 / total,
                program_evaluable_count=len(program_scores),
                program_execution_correct_count=program_correct,
                program_execution_accuracy=(
                    program_correct / len(program_scores) if program_scores else None
                ),
                wilson_ci95=_wilson_interval(correct, total),
            )
        )
        if len(observed) != total:
            blockers.append(
                f"benchmark_prediction_coverage_incomplete:{benchmark_id}:{len(observed)}!={total}"
            )
    report_values = {
        "prediction_run_id": prediction_run_id,
        "evaluation_snapshot_hash": expected_snapshot_hash,
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


def benchmark_prediction_id(value: BenchmarkPrediction) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"prediction_id"}),
        prefix="benchmark_prediction:",
    )


def benchmark_snapshot_manifest_hash(
    snapshots: tuple[ExternalBenchmarkSnapshot, ...],
) -> str:
    identity = tuple(
        {
            "benchmark_id": item.benchmark_id,
            "sha256": item.sha256,
            "source_repository": item.source_repository,
            "source_revision": item.source_revision,
            "split": item.split,
            "adapter_version": item.adapter_version,
            "metric_version": item.metric_version,
            "usage": item.usage,
        }
        for item in sorted(snapshots, key=lambda value: value.benchmark_id)
    )
    return canonical_hash(identity, prefix="external_benchmark_snapshot_manifest:")


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
    benchmark_signatures = tuple(_benchmark_signature(item) for item in example_values)
    training_signatures = tuple(_training_signature(item) for item in task_values)
    channels = (
        ("exact_prompt", "exact_prompt_hash"),
        ("question_skeleton", "question_skeleton"),
        ("operation_program", "operation_available"),
        ("subject_id", "subject_ids"),
        ("evidence_id", "evidence_ids"),
        ("source_record_id", "source_record_ids"),
        ("document_hash", "document_hashes"),
        ("binding_id", "binding_ids"),
    )
    coverage = tuple(
        BenchmarkLeakageChannelCoverage(
            channel_id=channel_id,
            benchmark_nonempty_count=sum(
                bool(signature[field]) for signature in benchmark_signatures
            ),
            benchmark_total_count=len(benchmark_signatures),
            training_nonempty_count=sum(
                bool(signature[field]) for signature in training_signatures
            ),
            training_total_count=len(training_signatures),
            comparable=bool(
                any(bool(signature[field]) for signature in benchmark_signatures)
                and any(bool(signature[field]) for signature in training_signatures)
            ),
        )
        for channel_id, field in channels
    )
    required = _LEAKAGE_REQUIRED_HARD_CHANNELS if status != "not_configured" else ()
    comparable = {item.channel_id for item in coverage if item.comparable}
    unavailable = tuple(channel for channel in required if channel not in comparable)
    effective_blockers = tuple(
        sorted(
            set(
                blockers
                + tuple(
                    f"benchmark_leakage_required_channel_unavailable:{channel}"
                    for channel in unavailable
                )
            )
        )
    )
    effective_status = (
        "failed"
        if status != "not_configured"
        and (
            any(item.severity == "hard" for item in collisions) or unavailable or effective_blockers
        )
        else status
    )
    values = {
        "benchmark_example_count": len(example_values),
        "training_task_count": len(task_values),
        "collision_count": len(collisions),
        "hard_collision_count": sum(item.severity == "hard" for item in collisions),
        "soft_collision_count": sum(item.severity == "soft" for item in collisions),
        "channel_coverage": coverage,
        "required_hard_channels": required,
        "unavailable_required_hard_channels": unavailable,
        "collisions": collisions,
        "status": effective_status,
        "blockers": effective_blockers,
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
        _example("financebench", item, index, inherited=item) for index, item in enumerate(records)
    ]


def _example(
    benchmark_id: str,
    qa: Mapping[str, Any],
    index: int,
    *,
    inherited: Mapping[str, Any],
) -> BenchmarkExample:
    question = qa.get("question") or qa.get("prompt") or qa.get("instruction")
    answer = qa.get("answer")
    if answer is None or (isinstance(answer, str) and not answer.strip()):
        answer = qa.get(
            "exe_ans",
            qa.get("gold_answer", qa.get("response_reference")),
        )
    if not isinstance(question, str) or not question.strip() or answer is None:
        raise ValueError(f"{benchmark_id} adapter found an incomplete item at index {index}")
    raw_id = (
        qa.get("id")
        or qa.get("uid")
        or qa.get("prompt_id")
        or inherited.get("id")
        or inherited.get("uid")
    )
    prompt, context_hash = _native_prompt(benchmark_id, question.strip(), inherited)
    example_id = (
        str(raw_id)
        if raw_id is not None
        else canonical_hash(
            {"benchmark": benchmark_id, "index": index, "prompt": prompt},
            prefix="benchmark_example:",
        )
    )
    metadata = {
        "program": qa.get("program"),
        "executable_answer": qa.get("exe_ans"),
        "scale": qa.get("scale"),
        "answer_type": qa.get("answer_type"),
        "derivation": qa.get("derivation"),
        "gold_inds": qa.get("gold_inds"),
        "subject_id": qa.get("subject_id") or inherited.get("subject_id"),
        "evidence_id": qa.get("evidence_id") or inherited.get("evidence_id"),
        # Only shared, explicit identities are comparable with training provenance. A
        # benchmark example ID or rendered-context hash is not a source-record/document hash.
        "source_record_id": qa.get("source_record_id") or inherited.get("source_record_id"),
        "document_hash": qa.get("document_hash") or inherited.get("document_hash"),
        "binding_id": qa.get("binding_id") or inherited.get("binding_id"),
        "native_table": inherited.get("table"),
    }
    return BenchmarkExample(
        example_id=example_id,
        benchmark_id=benchmark_id,
        prompt=prompt.strip(),
        question=question.strip(),
        gold_answer=answer,
        split="evaluation",
        context_hash=context_hash,
        metric_id=(
            "finqa_answer_and_program_execution.v2"
            if benchmark_id == "finqa"
            else "tat_qa_em_f1_scale.v1"
            if benchmark_id == "tat_qa"
            else "financebench_answer_accuracy.v1"
        ),
        metadata={key: value for key, value in metadata.items() if value is not None},
    )


def _native_prompt(
    benchmark_id: str,
    question: str,
    record: Mapping[str, Any],
) -> tuple[str, str]:
    if benchmark_id == "finqa":
        answer_contract = (
            "return a JSON object with keys answer, scale, and program. Program must be a "
            "FinQA operation string that can be executed independently"
        )
        context = "\n\n".join(
            part
            for part in (
                _paragraph_text(record.get("pre_text")),
                _markdown_table(record.get("table")),
                _paragraph_text(record.get("post_text")),
            )
            if part
        )
    elif benchmark_id == "tat_qa":
        answer_contract = (
            "return a JSON object with keys answer and scale. Use an empty scale when none applies"
        )
        table = record.get("table")
        table_rows = table.get("table") if isinstance(table, Mapping) else table
        context = "\n\n".join(
            part
            for part in (
                _markdown_table(table_rows),
                _paragraph_text(record.get("paragraphs")),
            )
            if part
        )
    else:
        answer_contract = (
            "return a JSON object with keys answer and scale. Use an empty scale when none applies"
        )
        context = _paragraph_text(
            record.get("context") or record.get("evidence") or record.get("documents")
        )
    prompt = (
        "Use only the financial report context below. Perform any required arithmetic and "
        f"{answer_contract}.\n\n"
        f"Context:\n{context}\n\nQuestion:\n{question}"
    )
    return prompt, canonical_hash(context, prefix=f"{benchmark_id}_native_context:")


def _paragraph_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        if isinstance(value.get("text"), str):
            return str(value["text"]).strip()
        return "\n".join(_paragraph_text(item) for item in value.values()).strip()
    if isinstance(value, (list, tuple)):
        return "\n".join(part for item in value if (part := _paragraph_text(item))).strip()
    return str(value).strip()


def _markdown_table(value: Any) -> str:
    if not isinstance(value, (list, tuple)) or not value:
        return ""
    rows = [list(row) for row in value if isinstance(row, (list, tuple))]
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    rendered = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in normalized]
    rendered.insert(1, "| " + " | ".join("---" for _ in range(width)) + " |")
    return "\n".join(rendered)


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
        "question_skeleton": _question_skeleton(
            _slot_normalized_instruction(public.instruction, public.retrieval_scope)
        ),
        "operation_signature": canonical_hash(operators, prefix="operation_signature:"),
        "operation_available": bool(operators),
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
            _normalize_text(example.question),
            prefix="benchmark_prompt:",
        ),
        "normalized_prompt": _number_normalized_text(example.question),
        "question_skeleton": _question_skeleton(example.question),
        "operation_signature": operation_signature,
        "operation_available": bool(_normalize_program(program)),
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


def _native_answer_metrics(
    example: BenchmarkExample,
    prediction: BenchmarkPrediction,
) -> tuple[bool, float, bool | None, bool]:
    if example.benchmark_id == "finqa":
        prediction_text = str(prediction.answer).strip()
        gold_text = str(example.gold_answer).strip()
        predicted_number = _to_number(prediction_text)
        gold_number = _to_number(gold_text)
        if predicted_number is not None and gold_number is not None:
            answer_exact = math.isclose(predicted_number, gold_number, abs_tol=1e-4, rel_tol=0.0)
        else:
            answer_exact = _normalize_text(prediction_text) == _normalize_text(gold_text)
        program_correct = _finqa_program_execution_correct(
            prediction.program,
            example.metadata.get("executable_answer", example.gold_answer),
            example.metadata.get("native_table"),
        )
        return bool(program_correct), float(answer_exact), program_correct, answer_exact
    if example.benchmark_id == "tat_qa":
        gold_scale = str(example.metadata.get("scale", "")).casefold()
        prediction_scale = prediction.scale.casefold()
        gold = _tatqa_answer_string(example.gold_answer, gold_scale)
        predicted = _tatqa_answer_string(prediction.answer, prediction_scale)
        gold_tokens = set(_tatqa_normalize(gold).split())
        predicted_tokens = set(_tatqa_normalize(predicted).split())
        exact = gold_tokens == predicted_tokens
        intersection = len(gold_tokens & predicted_tokens)
        precision = intersection / len(predicted_tokens) if predicted_tokens else 1.0
        recall = intersection / len(gold_tokens) if gold_tokens else 1.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision or recall else 0.0
        return exact, f1, None, exact
    if isinstance(example.gold_answer, (dict, list)):
        exact = canonical_hash(prediction.answer, prefix="answer:") == canonical_hash(
            example.gold_answer,
            prefix="answer:",
        )
    else:
        exact = _normalize_text(str(prediction.answer)) == _normalize_text(str(example.gold_answer))
    return exact, float(exact), None, exact


def _finqa_program_execution_correct(
    program: str,
    gold_answer: Any,
    table: Any,
) -> bool:
    result = _execute_finqa_program(program, table)
    if result is None:
        return False
    predicted_number = _numeric_value(result)
    gold_number = _numeric_value(gold_answer)
    if predicted_number is not None and gold_number is not None:
        return math.isclose(predicted_number, gold_number, abs_tol=1e-4, rel_tol=0.0)
    return _normalize_text(str(result)) == _normalize_text(str(gold_answer))


def _execute_finqa_program(program: str, table: Any) -> float | str | None:
    operations = re.findall(r"([a-z_]+)\(([^()]*)\)", program.casefold())
    if not operations:
        return None
    outputs: list[float | str] = []
    for operator, raw_arguments in operations:
        arguments = [item.strip() for item in raw_arguments.split(",")]
        if operator.startswith("table_"):
            values = _finqa_table_row_values(table, arguments[0] if arguments else "")
            if not values:
                return None
            if operator == "table_sum":
                output: float | str = sum(values)
            elif operator == "table_average":
                output = statistics.fmean(values)
            elif operator == "table_max":
                output = max(values)
            elif operator == "table_min":
                output = min(values)
            else:
                return None
            outputs.append(output)
            continue
        resolved = [_finqa_argument(item, outputs) for item in arguments]
        if len(resolved) != 2 or any(item is None for item in resolved):
            return None
        left, right = resolved
        if not isinstance(left, float) or not isinstance(right, float):
            return None
        if operator == "add":
            output = left + right
        elif operator == "subtract":
            output = left - right
        elif operator == "multiply":
            output = left * right
        elif operator == "divide":
            if right == 0:
                return None
            output = left / right
        elif operator == "exp":
            output = left**right
        elif operator == "greater":
            output = "yes" if left > right else "no"
        else:
            return None
        outputs.append(output)
    return outputs[-1]


def _finqa_argument(value: str, outputs: list[float | str]) -> float | str | None:
    if value.startswith("#") and value[1:].isdigit():
        index = int(value[1:])
        return outputs[index] if index < len(outputs) else None
    if value.startswith("const_m") and value.removeprefix("const_m").isdigit():
        return -float(value.removeprefix("const_m"))
    if value.startswith("const_") and value.removeprefix("const_").isdigit():
        return float(value.removeprefix("const_"))
    return _to_number(value)


def _finqa_table_row_values(table: Any, row_label: str) -> list[float]:
    if not isinstance(table, (list, tuple)):
        return []
    target = _normalize_text(row_label)
    for row in table:
        if not isinstance(row, (list, tuple)) or not row:
            continue
        if _normalize_text(str(row[0])) != target:
            continue
        values = [number for cell in row[1:] if (number := _to_number(str(cell))) is not None]
        return values
    return []


def _tatqa_answer_string(answer: Any, scale: str) -> str:
    values = list(answer) if isinstance(answer, (list, tuple)) else [answer]
    scale_factor = {
        "": 1.0,
        "hundred": 100.0,
        "thousand": 1_000.0,
        "million": 1_000_000.0,
        "billion": 1_000_000_000.0,
        "percent": 0.01,
    }.get(scale, 1.0)
    rendered: list[str] = []
    for value in sorted(str(item) for item in values):
        number = _to_number(value)
        if number is None:
            rendered.append(f"{value} {scale}".strip())
        elif "%" in value:
            rendered.append(f"{number:.4f}")
        else:
            rendered.append(f"{round(number, 2) * scale_factor:.4f}")
    return " ".join(rendered)


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return _to_number(str(value))


def _to_number(value: str) -> float | None:
    cleaned = value.strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    scale = 1.0
    lowered = cleaned.casefold()
    for label, factor in (
        ("billion", 1_000_000_000.0),
        ("million", 1_000_000.0),
        ("thousand", 1_000.0),
        ("hundred", 100.0),
    ):
        if label in lowered:
            scale = factor
            break
    if "%" in cleaned:
        scale *= 0.01
    values = _numbers(cleaned)
    if not values:
        return None
    return values[0] * scale * (-1.0 if negative else 1.0)


def _tatqa_normalize(value: str) -> str:
    tokens = []
    for token in value.casefold().split():
        number = _to_number(token)
        if number is not None:
            tokens.append(str(number))
            continue
        stripped = "".join(character for character in token if character not in string.punctuation)
        if stripped not in {"", "a", "an", "the"}:
            tokens.append(stripped)
    return " ".join(tokens)


def _numbers(value: str) -> tuple[float, ...]:
    return tuple(
        float(item.replace(",", ""))
        for item in re.findall(r"[-+]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?", value)
    )


def _normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[\w%]+", value.casefold()))


def _number_normalized_text(value: str) -> str:
    return re.sub(r"\b\d+(?:\.\d+)?\b", "<number>", _normalize_text(value))


def _question_skeleton(value: str) -> str:
    named = re.sub(
        r"\b(?:[A-Z][A-Za-z&.-]*)(?:\s+[A-Z][A-Za-z&.-]*)+\b",
        " <slot> ",
        value,
    )
    named = re.sub(
        r"\b[A-Z][A-Za-z&.-]{2,}\b",
        lambda match: (
            match.group(0) if match.group(0).casefold() in _QUESTION_INITIAL_WORDS else " <slot> "
        ),
        named,
    )
    named = re.sub(r"\b[A-Z]{2,8}\b", " <slot> ", named)
    for metric in _QUESTION_SKELETON_METRICS:
        named = re.sub(
            rf"\b{re.escape(metric)}\b",
            " <slot> ",
            named,
            flags=re.IGNORECASE,
        )
    normalized = _number_normalized_text(named)
    return re.sub(r"(?:\bslot\b\s*)+", "slot ", normalized).strip()


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
    margin = (
        z
        * math.sqrt(probability * (1.0 - probability) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return (max(0.0, center - margin), min(1.0, center + margin))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
