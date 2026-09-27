"""Lossless source adapters: raw labels never enter model-visible task objects.

No network access, answer-dependent context selection, HTML flattening, or QA
generation occurs here. A snapshot revision is mandatory and original splits
are retained verbatim. Annotated strata live only in private lineage/reference.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .catalog import canonical_dataset
from .contracts import Lineage, PrivateReference, PublicSource, PublicTask, TaskBundle, digest


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an original string")
    return value


def _table(value: Any) -> list[list[str]]:
    if not isinstance(value, list) or any(
        not isinstance(row, list) or any(not isinstance(cell, str) for cell in row) for row in value
    ):
        raise ValueError("table must be the original list of string rows")
    return value


def _parents(raw: dict[str, Any]) -> tuple[str, ...]:
    values = raw.get("parent_ids", ())
    if isinstance(values, str):
        values = [values]
    parent = raw.get("parent_id")
    return tuple(dict.fromkeys(str(x) for x in [*values, *([parent] if parent else [])]))


def _bundle(
    dataset: str,
    raw: Any,
    task_id: str,
    question: str,
    sources: list[PublicSource],
    reference: PrivateReference,
    split: str,
    revision: str,
    *,
    source_group: str,
    source_group_level: str,
    company: str | None = None,
    report: str | None = None,
    year: str | None = None,
    parents: tuple[str, ...] = (),
    strata: dict | None = None,
) -> TaskBundle:
    if not revision.strip() or not split.strip() or not task_id.strip():
        raise ValueError("revision, original split and original ID are required")
    contract = {
        "answer": "number, string, or list of strings; retain the task's natural semantics",
        "scale": "return a scale separately when applicable",
    }
    if dataset == "finqa":
        contract["program"] = "optional FinQA DSL program for official program/execution metrics"
    return TaskBundle(
        public=PublicTask(
            dataset=dataset,
            task_id=task_id,
            question=question,
            sources=tuple(sources),
            version=revision,
            answer_contract=contract,
        ),
        reference=reference,
        lineage=Lineage(
            dataset=dataset,
            original_split=split,
            original_id=task_id,
            parent_ids=parents,
            source_group=source_group,
            source_group_level=source_group_level,
            company=company,
            report=report,
            year=year,
            context_fingerprint=digest([{"kind": s.kind, "content": s.content} for s in sources]),
            question_fingerprint=digest(" ".join(question.casefold().split())),
            raw_sha256=digest(raw),
            revision=revision,
            strata=strata or {},
        ),
    )


def adapt_finqa(records: list[dict], *, split: str, revision: str) -> list[TaskBundle]:
    """Use complete pre_text/table/post_text, never qa.model_input or gold_inds.

    FinQA's company/year report key groups all page PDFs of that annual report;
    unknown path layouts fall back to context rather than inventing report IDs.
    Both normalized ``table`` (public) and original ``table_ori`` (audit) survive.
    """
    result = []
    for record in records:
        qa = record["qa"]
        if "exe_ans" not in qa or "program" not in qa:
            raise ValueError("FinQA private_test/unlabelled data cannot create a scored TaskBundle")
        task_id = _string(record["id"], "id")
        sources = [
            PublicSource(
                source_id=f"pre_text:{i}",
                kind="text",
                content=_string(text, "pre_text"),
                locator=f"pre_text[{i}]",
            )
            for i, text in enumerate(record["pre_text"])
        ]
        sources.append(
            PublicSource(
                source_id="table:0", kind="table", content=_table(record["table"]), locator="table"
            )
        )
        sources.extend(
            PublicSource(
                source_id=f"post_text:{i}",
                kind="text",
                content=_string(text, "post_text"),
                locator=f"post_text[{i}]",
            )
            for i, text in enumerate(record["post_text"])
        )
        filename = str(record.get("filename", task_id.rsplit("-", 1)[0]))
        match = re.match(r"^([^/]+)/(\d{4})/", filename)
        report = f"{match[1]}/{match[2]}" if match else None
        labels = {key: value for key, value in qa.items() if key != "question"}
        # Retrieval outputs are audit-only, even when upstream includes them.
        labels["source_metadata"] = {
            key: value
            for key, value in record.items()
            if key not in {"pre_text", "post_text", "table", "qa", "id"}
        }
        program = _string(qa["program"], "qa.program")
        gold = qa.get("gold_inds", {})
        strata = {
            "reference_program_steps": program.count("("),
            "gold_evidence_kinds": sorted({str(k).split("_")[0] for k in gold}),
        }
        result.append(
            _bundle(
                "finqa",
                record,
                task_id,
                _string(qa["question"], "qa.question"),
                sources,
                PrivateReference(
                    dataset="finqa",
                    task_id=task_id,
                    answer=qa["exe_ans"],
                    program=program,
                    annotations=labels,
                ),
                split,
                revision,
                source_group=f"finqa:report:{report}" if report else f"finqa:context:{filename}",
                source_group_level="report" if report else "context",
                company=match[1] if match else None,
                report=report,
                year=match[2] if match else None,
                parents=_parents(record),
                strata=strata,
            )
        )
    return _unique(result)


def adapt_tatqa(contexts: list[dict], *, split: str, revision: str) -> list[TaskBundle]:
    """Expand every question with its full context, without revealing type/source labels."""
    result = []
    for context in contexts:
        table = context["table"]
        context_id = _string(table["uid"], "table.uid")
        sources = [
            PublicSource(
                source_id="table:0",
                kind="table",
                content=_table(table["table"]),
                locator=f"table/{context_id}",
            )
        ]
        sources.extend(
            PublicSource(
                source_id=f"paragraph:{i}",
                kind="text",
                content=_string(p["text"], "paragraph.text"),
                locator=f"paragraphs[{i}]/{p['uid']}",
            )
            for i, p in enumerate(context["paragraphs"])
        )
        for question in context["questions"]:
            if "answer" not in question or "answer_type" not in question:
                raise ValueError(
                    "TAT-QA labelled snapshot required; select test_gold, not blind test"
                )
            task_id = _string(question["uid"], "question.uid")
            labels = {key: value for key, value in question.items() if key != "question"}
            labels["context_metadata"] = {
                "table_metadata": {k: v for k, v in table.items() if k != "table"},
                "paragraph_metadata": [
                    {k: v for k, v in p.items() if k != "text"} for p in context["paragraphs"]
                ],
                **{
                    k: v
                    for k, v in context.items()
                    if k not in {"table", "paragraphs", "questions"}
                },
            }
            strata = {
                key: question[key]
                for key in ("answer_type", "answer_from", "scale", "req_comparison")
                if key in question
            }
            result.append(
                _bundle(
                    "tatqa",
                    {"context": context, "selected_question_uid": task_id},
                    task_id,
                    _string(question["question"], "question.question"),
                    sources,
                    PrivateReference(
                        dataset="tatqa",
                        task_id=task_id,
                        answer=question["answer"],
                        scale=question.get("scale", ""),
                        program=question.get("derivation"),
                        annotations=labels,
                    ),
                    split,
                    revision,
                    source_group=f"tatqa:context:{context_id}",
                    source_group_level="context",
                    parents=_parents(question),
                    strata=strata,
                )
            )
    return _unique(result)


def adapt_financemath(records: list[dict], *, split: str, revision: str) -> list[TaskBundle]:
    """Read an already-lawfully-obtained local JSON snapshot; never download gated files.

    Official schema: question_id, question, tables (Markdown strings),
    python_solution, ground_truth, topic. Markdown tables remain verbatim.
    """
    if split not in {"test", "validation"}:
        raise ValueError("FinanceMath has validation/test only, not a training split")
    result = []
    for record in records:
        task_id = _string(record["question_id"], "question_id")
        if "ground_truth" not in record or "python_solution" not in record:
            raise ValueError("FinanceMath scored snapshot requires released references")
        sources = [
            PublicSource(
                source_id=f"table:{i}",
                kind="table",
                content=_string(table, "tables[]"),
                locator=f"tables[{i}]",
            )
            for i, table in enumerate(record["tables"])
        ]
        labels = {
            key: value
            for key, value in record.items()
            if key not in {"question", "tables", "ground_truth", "python_solution"}
        }
        result.append(
            _bundle(
                "financemath",
                record,
                task_id,
                _string(record["question"], "question"),
                sources,
                PrivateReference(
                    dataset="financemath",
                    task_id=task_id,
                    answer=record["ground_truth"],
                    program=record["python_solution"],
                    annotations=labels,
                ),
                split,
                revision,
                source_group=f"financemath:question:{task_id}",
                source_group_level="question",
                parents=_parents(record),
                strata={"topic": record.get("topic")},
            )
        )
    return _unique(result)


def _unique(bundles: list[TaskBundle]) -> list[TaskBundle]:
    ids = [bundle.public.task_id for bundle in bundles]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate original task IDs within snapshot")
    return bundles


def load_snapshot(dataset: str, path: str | Path, split: str, revision: str) -> list[TaskBundle]:
    """Import a JSON array or JSONL snapshot. No implicit splits or network calls."""
    dataset = canonical_dataset(dataset)
    adapter = {"finqa": adapt_finqa, "tatqa": adapt_tatqa, "financemath": adapt_financemath}.get(
        dataset
    )
    if adapter is None:
        raise ValueError(f"dataset adapter not admitted: {dataset}")
    path = Path(path)
    if path.suffix == ".jsonl":
        records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    else:
        records = json.loads(path.read_text())
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("snapshot must contain original records, not a repackaged example dataset")
    return adapter(records, split=split, revision=revision)
