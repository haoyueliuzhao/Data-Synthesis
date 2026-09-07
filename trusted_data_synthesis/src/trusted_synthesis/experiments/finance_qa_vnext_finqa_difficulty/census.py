"""Read-only annotation census. Metadata proxies are NOT semantic certification."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore

DATA = "trusted_data_synthesis/benchmarks/finqa/frozen/test.json"
OPS = r"table_average|table_sum|table_max|table_min|add|subtract|multiply|divide|greater|exp"
CALL = re.compile(rf"({OPS})\(([^()]*)\)")
NUMBER = re.compile(r"(?<![\w.])-?(?:\d[\d,]*\.?\d*|\.\d+)%?")


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def program(text):
    calls = [(m[1], [a.strip() for a in m[2].split(", ")]) for m in CALL.finditer(text)]
    residue = CALL.sub("", text).replace(",", "").strip()
    if residue or not calls or any(len(args) != 2 for _, args in calls):
        raise ValueError(f"Unparsed annotation: {text}")
    return calls


def structure(text):
    calls = program(text)
    depth, ancestors, uses, merges = [], [], Counter(), 0
    for index, (_, args) in enumerate(calls):
        refs = [int(a[1:]) for a in args if a.startswith("#")]
        if any(r >= index for r in refs):
            raise ValueError("forward reference")
        uses.update(refs)
        depth.append(1 + max((depth[r] for r in refs), default=0))
        ancestry = set(refs)
        for r in refs:
            ancestry.update(ancestors[r])
        unique = set(refs)
        merges += int(
            len(unique) == 2
            and not any(a in ancestors[b] for a in unique for b in unique if a != b)
        )
        ancestors.append(ancestry)
    return {
        "program_ops": len(calls),
        "dag_depth": max(depth),
        "final_dag_depth": depth[-1],
        "branch_merge_nodes": merges,
        "reused_intermediates": sum(n > 1 for n in uses.values()),
        "dead_intermediates": sorted(set(range(len(calls) - 1)) - ancestors[-1]),
        "operator_sequence": [op for op, _ in calls],
    }


def nesting(text):
    level = high = 0
    for char in text:
        if char == "(":
            level += 1
            high = max(high, level)
        elif char == ")":
            level -= 1
        if level < 0:
            raise ValueError("unbalanced nested program")
    if level:
        raise ValueError("unbalanced nested program")
    return high


def census(root):
    path = root / DATA
    data = json.loads(path.read_bytes())
    rows = []
    for entry in data:
        qa, table = entry["qa"], entry["table"]
        texts = entry["pre_text"] + entry["post_text"]
        source = entry.get("filename", entry["id"].rsplit("-", 1)[0])
        kinds = {key.split("_")[0] for key in qa["gold_inds"]}
        aggregates = []
        for op, args in program(qa["program"]):
            if op.startswith("table_"):
                matches = [(i, row) for i, row in enumerate(table) if row[0].strip() == args[0]]
                aggregates.append(
                    {
                        "operator": op,
                        "row_name": args[0],
                        "matching_rows": [i for i, _ in matches],
                        "nonlabel_cell_counts": [len(row) - 1 for _, row in matches],
                        "numeric_cell_counts": [
                            sum(bool(NUMBER.search(c)) for c in row[1:]) for _, row in matches
                        ],
                        "counts_are_candidates_not_verified_operands": True,
                    }
                )
        alltext = " ".join(texts + [" ".join(row) for row in table])
        rows.append(
            {
                "qa_id": entry["id"],
                "document": source,
                "report": "/".join(source.split("/")[:2]),
                "subject_proxy": source.split("/")[0],
                "table_sha256": digest(table),
                "context_sha256": digest([table, texts]),
                "question": qa["question"],
                "original_program": qa["program"],
                "original_program_re": qa.get("program_re"),
                **structure(qa["program"]),
                "program_re_depth": nesting(qa["program_re"]),
                "support_type": "mixed"
                if kinds == {"table", "text"}
                else next(iter(kinds))
                if len(kinds) == 1
                else "unknown",
                "gold_support_count": len(qa["gold_inds"]),
                "gold_support_ids": list(qa["gold_inds"]),
                "table_rows": len(table),
                "table_cells": sum(map(len, table)),
                "text_paragraphs": len(texts),
                "candidate_context_characters": len(alltext),
                "candidate_numeric_spans": len(NUMBER.findall(alltext)),
                "year_mentions_proxy": sorted(set(re.findall(r"\b(?:19|20)\d{2}\b", alltext))),
                "scale_mentions_proxy": sorted(
                    set(
                        re.findall(
                            r"\b(?:thousands?|millions?|billions?|percent|percentage)\b", alltext
                        )
                    )
                ),
                "metric_labels_proxy": [row[0] for row in table],
                "semantic_definition_status": "not_independently_certified",
                "aggregate_inputs": aggregates,
                "annotation_correctness": "not_certified",
                "current_H2_original_question_coverage": "undetermined",
            }
        )

    def hist(key):
        return {str(k): v for k, v in sorted(Counter(row[key] for row in rows).items())}

    operator_counts = Counter(op for row in rows for op in row["operator_sequence"])
    operator_questions = Counter(op for row in rows for op in set(row["operator_sequence"]))
    context_distribution = {}
    for key in (
        "table_rows",
        "table_cells",
        "text_paragraphs",
        "candidate_context_characters",
        "candidate_numeric_spans",
    ):
        values = sorted(row[key] for row in rows)
        context_distribution[key] = {
            "minimum": values[0],
            "median": values[len(values) // 2],
            "p95_nearest_rank": values[(95 * len(values) + 99) // 100 - 1],
            "maximum": values[-1],
        }
    aggregate_candidates = Counter(
        count
        for row in rows
        for item in row["aggregate_inputs"]
        for count in item["numeric_cell_counts"]
    )
    overlap = {}
    for key in ("document", "report", "subject_proxy", "table_sha256", "context_sha256"):
        groups = Counter(row[key] for row in rows)
        overlap[key] = {
            "distinct": len(groups),
            "groups_with_multiple_questions": sum(n > 1 for n in groups.values()),
            "questions_in_repeated_groups": sum(n for n in groups.values() if n > 1),
            "maximum_questions": max(groups.values()),
        }
    summary = {
        "file": DATA,
        "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "questions": len(rows),
        "provider_calls": 0,
        "scope": "repository frozen public test split only; inspected development data",
        "candidate_context_distribution": context_distribution,
        "aggregation_numeric_candidate_cell_histogram": {
            str(k): v for k, v in sorted(aggregate_candidates.items())
        },
        "histograms": {
            key: hist(key)
            for key in (
                "program_ops",
                "dag_depth",
                "final_dag_depth",
                "program_re_depth",
                "support_type",
                "gold_support_count",
            )
        },
        "total_annotated_operations": sum(operator_counts.values()),
        "operator_occurrences": dict(operator_counts),
        "operator_question_counts": dict(operator_questions),
        "operator_sequences": dict(
            Counter("→".join(r["operator_sequence"]) for r in rows).most_common()
        ),
        "branch_merge_questions": sum(r["branch_merge_nodes"] > 0 for r in rows),
        "intermediate_reuse_questions": sum(r["reused_intermediates"] > 0 for r in rows),
        "dead_intermediate_questions": sum(bool(r["dead_intermediates"]) for r in rows),
        "aggregate_questions": sum(bool(r["aggregate_inputs"]) for r in rows),
        "overlap": overlap,
        "metadata_caveat": (
            "Year/scale/metric fields are lexical proxies, not certified task "
            "semantics; aggregate cells can include duplicated totals or nonnumeric "
            "cells."
        ),
        "coverage_caveat": (
            "No all-question execution claim: original-question status remains "
            "undetermined until independently instantiated. Old S/B are "
            "source-derived different questions, not benchmark passes."
        ),
        "grain_comparison": {
            "S_direct": {"domain_ops": 2, "expanded_ops": 2, "expanded_depth": 2},
            "S_rebuilt": {"domain_ops": 3, "expanded_ops": 3, "expanded_depth": 3},
            "B_positive_base": {
                "domain_ops": 4,
                "domain_depth": 3,
                "expanded_binary_ops": 7,
                "expanded_abs_ops": 1,
                "expanded_depth": 5,
            },
            "lookup_adds_arithmetic_depth": False,
        },
    }
    return rows, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows, summary = census(args.root)
    store = DurableStore(args.output)
    store.json("rows.json", rows)
    store.json("summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
