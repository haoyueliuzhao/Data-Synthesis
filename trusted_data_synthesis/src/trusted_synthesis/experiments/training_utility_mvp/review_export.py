from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.core.evaluation.utility import UtilityCohort
from trusted_synthesis.hashing import canonical_hash

from .data import load_sft_records
from .schema import SFTRecord

QA_REVIEW_SCHEMA_VERSION = "training_utility_qa_review.v1"
QA_REVIEW_EXPORT_VERSION = "training_utility_qa_review_export.v1"
TargetInterpretation = Literal[
    "gold_reference",
    "quality_accepted_candidate",
    "quality_rejected_candidate",
    "intentionally_faulty_counterfactual",
    "counterfactual_repair_target",
]


class QAReviewEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    selected: bool
    subject: str | None = None
    predicate: str | None = None
    period: str | None = None
    scope: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None
    source_uri: str | None = None
    definition: str | None = None


class QAReviewRecord(BaseModel):
    """Oracle-bearing, human-review projection of one immutable SFT record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    review_id: str
    source_record_id: str
    source_record_hash: str
    source_dataset_file: str
    cohort: str
    task_id: str
    domain: str
    source_kind: str
    contract_label: str | None = None
    counterfactual_repair: bool
    mode: str
    question: str
    task_type: str | None = None
    pattern_id: str | None = None
    answer_type: str | None = None
    answer_schema: dict[str, Any] = Field(default_factory=dict)
    target_interpretation: TargetInterpretation
    is_gold_reference: bool
    is_quality_approved: bool
    assistant_target_answer: Any
    assistant_target_answer_text: str
    selected_evidence_ids: tuple[str, ...]
    available_evidence_ids: tuple[str, ...]
    evidence: tuple[QAReviewEvidence, ...]
    operation_sequence: tuple[str, ...]
    execution_steps: tuple[dict[str, Any], ...]
    verification_result: dict[str, Any] | None = None
    citations: tuple[dict[str, Any], ...]
    candidate_attempt_to_repair: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = QA_REVIEW_SCHEMA_VERSION


class QAReviewExportManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    export_id: str
    input_directory: str
    input_files: tuple[str, ...]
    record_count: int = Field(ge=1)
    cohort_counts: dict[str, int]
    domain_counts: dict[str, int]
    source_kind_counts: dict[str, int]
    selected_evidence_count: int = Field(ge=0)
    available_evidence_count: int = Field(ge=0)
    counterfactual_repair_count: int = Field(ge=0)
    source_dataset_hash: str
    review_dataset_hash: str
    jsonl_file: str
    markdown_index_file: str
    markdown_files: dict[str, str]
    markdown_record_counts: dict[str, int]
    markdown_limit_per_cohort: int = Field(ge=0)
    version: str = QA_REVIEW_EXPORT_VERSION


def export_training_utility_review(
    input_dir: Path,
    output_dir: Path,
    *,
    markdown_limit_per_cohort: int = 0,
) -> QAReviewExportManifest:
    """Export D1-D5 records into flat JSONL and per-cohort Markdown views."""

    if markdown_limit_per_cohort < 0:
        raise ValueError("markdown_limit_per_cohort must be non-negative")
    input_paths = _discover_dataset_paths(input_dir)
    source_records: list[tuple[Path, SFTRecord]] = []
    seen_ids: set[str] = set()
    for path in input_paths:
        for record in load_sft_records(path):
            if record.record_id in seen_ids:
                raise ValueError(f"duplicate SFT record_id across inputs: {record.record_id}")
            seen_ids.add(record.record_id)
            source_records.append((path, record))
    if not source_records:
        raise ValueError(f"no SFT records found in {input_dir}")

    reviews = tuple(
        build_qa_review_record(record, source_dataset_file=path.name)
        for path, record in source_records
    )
    grouped: dict[str, list[QAReviewRecord]] = defaultdict(list)
    for review in reviews:
        grouped[review.cohort].append(review)

    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir = output_dir / "markdown"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "qa_review.jsonl"
    _write_jsonl(jsonl_path, reviews)

    markdown_files: dict[str, str] = {}
    markdown_counts: dict[str, int] = {}
    for cohort in _ordered_cohorts(grouped):
        records = grouped[cohort]
        rendered = (
            records if markdown_limit_per_cohort == 0 else records[:markdown_limit_per_cohort]
        )
        path = markdown_dir / f"{cohort}.md"
        path.write_text(_render_cohort(cohort, records, rendered), encoding="utf-8")
        markdown_files[cohort] = str(path.relative_to(output_dir))
        markdown_counts[cohort] = len(rendered)

    source_hash = canonical_hash(
        tuple((path.name, record.record_hash) for path, record in source_records),
        prefix="training_utility_review_source_dataset:",
    )
    review_hash = canonical_hash(
        tuple(record.review_id for record in reviews),
        prefix="training_utility_review_dataset:",
    )
    manifest = QAReviewExportManifest(
        export_id=canonical_hash(
            {
                "version": QA_REVIEW_EXPORT_VERSION,
                "source_dataset_hash": source_hash,
                "review_dataset_hash": review_hash,
                "markdown_limit_per_cohort": markdown_limit_per_cohort,
            },
            prefix="training_utility_review_export:",
        ),
        input_directory=str(input_dir.resolve()),
        input_files=tuple(path.name for path in input_paths),
        record_count=len(reviews),
        cohort_counts=dict(sorted(Counter(record.cohort for record in reviews).items())),
        domain_counts=dict(sorted(Counter(record.domain for record in reviews).items())),
        source_kind_counts=dict(sorted(Counter(record.source_kind for record in reviews).items())),
        selected_evidence_count=sum(len(record.selected_evidence_ids) for record in reviews),
        available_evidence_count=sum(len(record.available_evidence_ids) for record in reviews),
        counterfactual_repair_count=sum(record.counterfactual_repair for record in reviews),
        source_dataset_hash=source_hash,
        review_dataset_hash=review_hash,
        jsonl_file=jsonl_path.name,
        markdown_index_file="qa_review.md",
        markdown_files=dict(sorted(markdown_files.items())),
        markdown_record_counts=dict(sorted(markdown_counts.items())),
        markdown_limit_per_cohort=markdown_limit_per_cohort,
    )
    (output_dir / "qa_review_manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / manifest.markdown_index_file).write_text(
        _render_index(manifest), encoding="utf-8"
    )
    return manifest


def build_qa_review_record(
    record: SFTRecord,
    *,
    source_dataset_file: str,
) -> QAReviewRecord:
    user = _parse_object(record.user_prompt, record.record_id, "user_prompt")
    target = _parse_object(record.assistant_target, record.record_id, "assistant_target")
    task = _mapping(user.get("public_task"), record.record_id, "public_task")
    question = task.get("instruction")
    if not isinstance(question, str) or not question.strip():
        raise ValueError(f"{record.record_id}: public_task.instruction must be non-empty")
    corpus = user.get("evidence_corpus")
    if not isinstance(corpus, list):
        raise ValueError(f"{record.record_id}: evidence_corpus must be an array")

    if record.training_format == "host_instrumented_joint":
        action_plan = _mapping(target.get("action_plan"), record.record_id, "action_plan")
        answer_decision = _mapping(
            target.get("answer_decision"),
            record.record_id,
            "answer_decision",
        )
        host = _parse_object(
            record.messages[3].content,
            record.record_id,
            "host_execution",
        )
        final_answer = {
            "result": answer_decision.get("result"),
            "citations": [
                {"evidence_id": item}
                for item in answer_decision.get("cited_evidence_ids", ())
            ],
            **({"status": answer_decision["status"]} if "status" in answer_decision else {}),
            **({"claims": answer_decision["claims"]} if "claims" in answer_decision else {}),
        }
        selected_raw = action_plan.get("selected_evidence_ids")
        trace = _mapping(host.get("execution_trace"), record.record_id, "execution_trace")
        verification = host.get("output_result")
    else:
        final_answer = _mapping(target.get("final_answer"), record.record_id, "final_answer")
        selected_raw = target.get("selected_evidence_ids")
        trace = _mapping(target.get("execution_trace"), record.record_id, "execution_trace")
        verification = target.get("verification_result")
    if "result" not in final_answer or final_answer["result"] is None:
        raise ValueError(f"{record.record_id}: final answer result is required")
    if not isinstance(selected_raw, list) or not all(
        isinstance(item, str) and item for item in selected_raw
    ):
        raise ValueError(f"{record.record_id}: selected_evidence_ids must be strings")
    selected = tuple(selected_raw)

    evidence_ids: list[str] = []
    evidence_rows: list[QAReviewEvidence] = []
    for ordinal, value in enumerate(corpus):
        evidence = _mapping(value, record.record_id, f"evidence_corpus[{ordinal}]")
        evidence_id = evidence.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id:
            raise ValueError(f"{record.record_id}: evidence item lacks evidence_id")
        if evidence_id in evidence_ids:
            raise ValueError(f"{record.record_id}: duplicate evidence_id {evidence_id}")
        evidence_ids.append(evidence_id)
        evidence_rows.append(_compact_evidence(evidence, evidence_id in selected))
    missing = sorted(set(selected) - set(evidence_ids))
    if missing:
        raise ValueError(f"{record.record_id}: selected evidence absent from corpus: {missing}")

    steps_raw = trace.get("steps")
    if not isinstance(steps_raw, list) or not all(isinstance(item, dict) for item in steps_raw):
        raise ValueError(f"{record.record_id}: execution_trace.steps must be objects")
    steps = tuple(dict(item) for item in steps_raw)
    operations = record.metadata.get("operation_sequence")
    operation_sequence = (
        tuple(operations)
        if isinstance(operations, (list, tuple))
        and all(isinstance(item, str) for item in operations)
        else tuple(str(step["operator_id"]) for step in steps if step.get("operator_id"))
    )
    citations_raw = final_answer.get("citations", [])
    if not isinstance(citations_raw, list) or not all(
        isinstance(item, dict) for item in citations_raw
    ):
        raise ValueError(f"{record.record_id}: final_answer.citations must be objects")
    if verification is not None and not isinstance(verification, dict):
        raise ValueError(f"{record.record_id}: host replay result must be an object or null")
    repair = user.get("candidate_attempt_to_repair")
    if repair is not None and not isinstance(repair, dict):
        raise ValueError(f"{record.record_id}: candidate_attempt_to_repair must be an object")
    answer_schema = task.get("answer_schema") or {}
    if not isinstance(answer_schema, dict):
        raise ValueError(f"{record.record_id}: public_task.answer_schema must be an object")
    cohort = record.cohort.value if isinstance(record.cohort, UtilityCohort) else record.cohort
    identity = {
        "schema_version": QA_REVIEW_SCHEMA_VERSION,
        "source_record_id": record.record_id,
        "source_record_hash": record.record_hash,
    }
    answer = final_answer["result"]
    return QAReviewRecord(
        review_id=canonical_hash(identity, prefix="training_utility_qa_review:"),
        source_record_id=record.record_id,
        source_record_hash=record.record_hash,
        source_dataset_file=source_dataset_file,
        cohort=str(cohort),
        task_id=record.task_id,
        domain=record.domain,
        source_kind=record.source_kind,
        contract_label=record.contract_label,
        counterfactual_repair=record.counterfactual_repair,
        mode=str(user.get("mode") or "unknown"),
        question=question.strip(),
        task_type=_text(task.get("task_type")),
        pattern_id=_text(record.metadata.get("pattern_id")),
        answer_type=_text(record.metadata.get("answer_type")),
        answer_schema=dict(answer_schema),
        target_interpretation=_target_interpretation(record),
        is_gold_reference=record.source_kind == "deterministic_reference_workflow",
        is_quality_approved=record.contract_label == "accept",
        assistant_target_answer=answer,
        assistant_target_answer_text=_answer_text(answer),
        selected_evidence_ids=selected,
        available_evidence_ids=tuple(evidence_ids),
        evidence=tuple(evidence_rows),
        operation_sequence=operation_sequence,
        execution_steps=steps,
        verification_result=dict(verification) if verification is not None else None,
        citations=tuple(dict(item) for item in citations_raw),
        candidate_attempt_to_repair=dict(repair) if repair is not None else None,
        metadata=dict(record.metadata),
    )


def _discover_dataset_paths(input_dir: Path) -> tuple[Path, ...]:
    if not input_dir.is_dir():
        raise ValueError(f"training utility input directory does not exist: {input_dir}")
    names = (*(f"{cohort.value}.jsonl" for cohort in UtilityCohort), "evaluation.jsonl")
    paths = tuple(input_dir / name for name in names if (input_dir / name).is_file())
    if not paths:
        raise ValueError(f"no recognized training utility JSONL files found in {input_dir}")
    return paths


def _parse_object(text: str, record_id: str, field: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{record_id}: invalid JSON in {field}: {exc.msg}") from exc
    return _mapping(value, record_id, field)


def _mapping(value: Any, record_id: str, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{record_id}: {field} must be an object")
    return value


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _target_interpretation(record: SFTRecord) -> TargetInterpretation:
    if record.source_kind == "deterministic_reference_workflow":
        return "gold_reference"
    if record.counterfactual_repair:
        return "counterfactual_repair_target"
    if record.source_kind == "typed_counterfactual":
        return "intentionally_faulty_counterfactual"
    if record.contract_label == "accept":
        return "quality_accepted_candidate"
    return "quality_rejected_candidate"


def _compact_evidence(evidence: dict[str, Any], selected: bool) -> QAReviewEvidence:
    subject = _optional_mapping(evidence.get("subject"))
    temporal = _optional_mapping(evidence.get("temporal_context"))
    scope = _optional_mapping(evidence.get("scope"))
    source = _optional_mapping(evidence.get("source"))
    locator = _optional_mapping(evidence.get("source_locator"))
    definition = _optional_mapping(evidence.get("definition"))
    payload = _optional_mapping(evidence.get("payload"))
    return QAReviewEvidence(
        evidence_id=str(evidence["evidence_id"]),
        selected=selected,
        subject=_text(subject.get("name") or subject.get("subject_id")),
        predicate=_text(evidence.get("predicate")),
        period=_text(temporal.get("label")),
        scope=_text(scope.get("label")),
        payload=dict(payload),
        source=_text(source.get("name") or source.get("source_id")),
        source_uri=_text(locator.get("uri")),
        definition=_text(definition.get("text") or definition.get("definition_id")),
    )


def _optional_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _answer_text(answer: Any) -> str:
    if isinstance(answer, str):
        return answer
    if isinstance(answer, (int, float, bool)) or answer is None:
        return str(answer)
    if isinstance(answer, dict) and isinstance(answer.get("payload"), dict):
        payload = answer["payload"]
        if "value" in payload:
            parts = [str(payload["value"])]
            unit = _text(payload.get("unit"))
            currency = _text(payload.get("currency"))
            if unit:
                parts.append(unit)
            if currency and (not unit or currency.lower() not in unit.lower()):
                parts.append(f"({currency})")
            if source := _text(answer.get("source_id")):
                parts.append(f"source: {source}")
            return " ".join(parts)
    return _short_json(answer, limit=10_000)


def _ordered_cohorts(grouped: dict[str, list[QAReviewRecord]]) -> tuple[str, ...]:
    preferred = tuple(cohort.value for cohort in UtilityCohort) + ("evaluation",)
    return tuple(name for name in preferred if name in grouped) + tuple(
        sorted(set(grouped) - set(preferred))
    )


def _write_jsonl(path: Path, records: tuple[QAReviewRecord, ...]) -> None:
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(record.model_dump_json() + "\n")


def _render_index(manifest: QAReviewExportManifest) -> str:
    lines = [
        "# Training Utility QA Review",
        "",
        "> Oracle-bearing review artifact. Do not expose evaluation answers to a model.",
        "",
        f"- Export ID: `{manifest.export_id}`",
        f"- Records: {manifest.record_count:,}",
        f"- Flat JSONL: [`{manifest.jsonl_file}`]({manifest.jsonl_file})",
        "",
        "| Cohort | Total | Rendered | Review file |",
        "| --- | ---: | ---: | --- |",
    ]
    for cohort, count in manifest.cohort_counts.items():
        path = manifest.markdown_files[cohort]
        rendered = manifest.markdown_record_counts[cohort]
        lines.append(f"| `{cohort}` | {count:,} | {rendered:,} | [{path}]({path}) |")
    return "\n".join(lines) + "\n"


def _render_cohort(
    cohort: str,
    all_records: list[QAReviewRecord],
    rendered: list[QAReviewRecord],
) -> str:
    lines = [
        f"# {cohort} QA Review",
        "",
        f"Rendered {len(rendered):,} of {len(all_records):,} records.",
        "",
    ]
    for ordinal, record in enumerate(rendered, start=1):
        lines.extend(_render_record(ordinal, record))
    return "\n".join(lines).rstrip() + "\n"


def _render_record(ordinal: int, record: QAReviewRecord) -> list[str]:
    lines = [
        f"## {ordinal}. {record.domain} / {record.task_type or 'unknown'}",
        "",
        f"- Record: `{record.source_record_id}`",
        f"- Pattern: `{record.pattern_id or 'unknown'}`",
        f"- Mode: `{record.mode}`",
        f"- Operations: `{', '.join(record.operation_sequence) or 'none'}`",
        "",
        "### Question",
        "",
        record.question,
        "",
        f"- Target interpretation: `{record.target_interpretation}`",
        f"- Gold reference: `{'yes' if record.is_gold_reference else 'no'}`",
        f"- Quality approved: `{'yes' if record.is_quality_approved else 'no'}`",
        "",
        "### Assistant Target Answer",
        "",
        record.assistant_target_answer_text,
        "",
        "```json",
        json.dumps(record.assistant_target_answer, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "### Evidence",
        "",
        "| Used | Evidence ID | Subject | Predicate | Period | Payload | Source |",
        "| :---: | --- | --- | --- | --- | --- | --- |",
    ]
    for evidence in record.evidence:
        lines.append(
            f"| {'yes' if evidence.selected else 'no'} | `{_cell(evidence.evidence_id)}` | "
            f"{_cell(evidence.subject or '')} | `{_cell(evidence.predicate or '')}` | "
            f"{_cell(evidence.period or '')} | `{_cell(_short_json(evidence.payload))}` | "
            f"{_cell(evidence.source or '')} |"
        )
    lines.extend(
        [
            "",
            "### Operation Trace",
            "",
            "| Step | Operator | Evidence | Status | Result |",
            "| ---: | --- | --- | --- | --- |",
        ]
    )
    for number, step in enumerate(record.execution_steps, start=1):
        observation = step.get("observation")
        result = observation.get("result") if isinstance(observation, dict) else observation
        evidence_ids = step.get("evidence_ids")
        evidence_text = ", ".join(map(str, evidence_ids)) if isinstance(evidence_ids, list) else ""
        lines.append(
            f"| {number} | `{_cell(str(step.get('operator_id') or ''))}` | "
            f"{_cell(evidence_text)} | `{_cell(str(step.get('status') or ''))}` | "
            f"`{_cell(_short_json(result))}` |"
        )
    lines.extend(["", "### Citations", ""])
    lines.extend(f"- `{_cell(_short_json(citation, limit=500))}`" for citation in record.citations)
    if not record.citations:
        lines.append("- None")
    if record.candidate_attempt_to_repair is not None:
        lines.extend(
            [
                "",
                "### Candidate Attempt To Repair",
                "",
                "```json",
                json.dumps(
                    record.candidate_attempt_to_repair,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                "```",
            ]
        )
    lines.extend(["", "---", ""])
    return lines


def _short_json(value: Any, *, limit: int = 220) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
