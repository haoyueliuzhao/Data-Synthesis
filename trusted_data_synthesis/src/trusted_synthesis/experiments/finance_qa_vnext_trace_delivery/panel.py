"""Six pre-generation migration tasks; all targets and selectors remain private.

The source file is reused, not rescanned for census statistics.  These instances
were selected and checked before any A/T response was collected.  The recorded
history search is a bounded check for current prompt/run development use, not a
claim about model training data or every historical research read.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

from ..finance_qa_vnext_finqa_difficulty.census import DATA
from ..finance_qa_vnext_finqa_difficulty.semantics import decimal, evaluate
from ..finance_qa_vnext_finqa_difficulty.sources import catalog, select

FROZEN_SOURCE_SHA256 = "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
SELECTION_BASELINE = "1282a57e255211ddf86ffc9bbfa016b23c573798"


def node(op, *args):
    return {"op": op, "args": list(args)}


SPECS = {
    "N1": {
        "category": "ratio_and_scale",
        "qa_id": "INTC/2015/page_41.pdf-4",
        "array_index": 1,
        "unit": "percent",
        "selectors": [("t2c3", "8.1"), ("t3c3", "56.0")],
        "input_meanings": [
            "Global leased facilities, million square feet.",
            "Global total facilities, million square feet.",
        ],
        "context_segments": ["t0c0", "t0c3", "t2c0", "t3c0", "p3"],
        "exact": "405/28",
        "independent_expression": "8.1 / 56.0 * 100",
        "interpretation": (
            "Worldwide leased floor area divided by worldwide total floor area; "
            "the common million-square-feet scale cancels. Region sums are valid "
            "alternatives, not mandatory extra computation."
        ),
        "precision_policy": (
            "Use the disclosed source values 8.1 and 56.0 exactly. Repeated prose "
            "agrees with the table; no finer same-quantity source was identified. "
            "The original answer 14% is coarse and is not the numerical target. "
            "Published percentage values remain subject to frozen evaluation v2."
        ),
    },
    "N2": {
        "category": "ratio_and_scale",
        "qa_id": "ETR/2004/page_281.pdf-1",
        "array_index": 304,
        "unit": "percent",
        "selectors": [("q0", "42.5"), ("t2c0", "61592")],
        "input_meanings": [
            "2004 money-pool use of operating cash flows, positive use magnitude, USD million.",
            "2004 year-end money-pool receivables, USD thousand.",
        ],
        "context_segments": ["p13", "q0", "t0c0", "t1c0"],
        "exact": "531250/7699",
        "independent_expression": "42.5 / (61592 / 1000) * 100",
        "interpretation": (
            "Money-pool cash use as a positive amount divided by same-year "
            "receivables, converting thousand dollars to million dollars. "
            "The question asks the magnitude of use, not a signed CFO contribution. "
            "The 2004 value is table column zero, not column one."
        ),
        "precision_policy": (
            "Treat disclosed 42.5 million and 61592 thousand as source values; "
            "no competing finer or rounded disclosure of either selected quantity "
            "was found in the complete entry. Exact arithmetic does not claim "
            "unrounded underlying economic values."
        ),
    },
    "N3": {
        "category": "multi_period_aggregation",
        "qa_id": "JPM/2010/page_273.pdf-2",
        "array_index": 19,
        "unit": "USD_billion",
        "selectors": [("q16", "25.0"), ("q16", "24.0"), ("q16", "9.7"), ("q16", "10.2")],
        "input_meanings": [
            "2010 segregated customer cash, USD billion.",
            "2009 segregated customer cash, USD billion.",
            "2010 segregated customer securities fair value, USD billion.",
            "2009 segregated customer securities fair value, USD billion.",
        ],
        "context_segments": ["q16"],
        "exact": "689/10",
        "independent_expression": "25.0 + 24.0 + 9.7 + 10.2",
        "interpretation": (
            "Sum both cash and securities for the two explicitly requested years. "
            "Two respectively clauses establish the year-category pairings. "
            "Grouping by year, by asset type, or using one expression is valid. "
            "This is the requested sum of disclosed balances, not a time-weighted "
            "economic stock. The unrelated income-tax table uses millions."
        ),
        "precision_policy": (
            "All four selected disclosures use billions and no finer same-quantity "
            "table appears. Preserve the original question's explicit in-billions "
            "unit: the target is 68.9 USD_billion, not 68.9 USD_million."
        ),
    },
    "N4": {
        "category": "multi_period_aggregation",
        "qa_id": "K/2006/page_52.pdf-2",
        "array_index": 44,
        "unit": "USD_million",
        "selectors": [("t3c1", "957.4"), ("t3c2", "769.1"), ("t3c3", "950.4")],
        "input_meanings": [
            "2006 company-defined cash flow, USD million.",
            "2005 company-defined cash flow, USD million.",
            "2004 company-defined cash flow, USD million.",
        ],
        "context_segments": ["p20", "p21", "p22", "t0c0", "t3c0"],
        "exact": "8923/10",
        "independent_expression": "(957.4 + 769.1 + 950.4) / 3",
        "interpretation": (
            "Arithmetic average of all three company-defined cash-flow values. "
            "Prose defines cash flow as operating cash flow less property additions; "
            "the operating-CFO row and annual percentage-change row are not targets. "
            "Each reported cash flow can instead be reconstructed from signed capex."
        ),
        "precision_policy": (
            "Table dollar amounts are in millions. The reported cash-flow row "
            "and CFO plus signed property-additions row agree exactly in each year. "
            "No finer same-quantity source competes with the selected row. The "
            "OCR-corrupted annual-change percentage is irrelevant to the target. "
            "The original hand-written steps[0].res is 1276.5, but 957.4+769.1 "
            "equals 1726.5; this intermediate annotation is erroneous and is not "
            "used as a target or required step. The original program, final sum "
            "2676.9 and final answer 892.3 agree with independent source arithmetic."
        ),
    },
    "N5": {
        "category": "composite_amount_change",
        "qa_id": "AON/2007/page_175.pdf-2",
        "array_index": 63,
        "unit": "USD_million",
        "selectors": [("t5c1", "155"), ("t6c1", "-141"), ("t7c1", "4")],
        "input_meanings": [
            "Restructuring expense in 2006, increasing liability, USD million.",
            "Cash payments in 2006, decreasing liability, signed USD million.",
            "Foreign-currency revaluation in the 2006 roll-forward, USD million.",
        ],
        "context_segments": ["p0", "p1", "t4c0", "t8c0", "q0"],
        "exact": "18",
        "independent_expression": "155 + (-141) + 4",
        "interpretation": (
            "2006 net change is expense plus signed cash payments plus currency "
            "revaluation. Equivalently, 2006 closing balance 134 minus 2005 closing "
            "balance 116 is 18; that shorter source-grounded route is fully valid. "
            "The task is not guaranteed to induce multiple computational steps."
        ),
        "precision_policy": (
            "Prose labels the table millions. The -141 (141) text is one accounting "
            "negative and its normalized repeat, not two independent inputs. "
            "Ignore the unrelated first-row OCR token $2014 when identifying the "
            "2006 opening balance. Selected changes and balances agree exactly."
        ),
    },
    "N6": {
        "category": "composite_amount_change",
        "qa_id": "JPM/2009/page_175.pdf-5",
        "array_index": 281,
        "unit": "USD_million",
        "selectors": [
            ("t1c2", "384102"),
            ("t2c2", "121417"),
            ("t1c3", "381415"),
            ("t2c3", "65439"),
        ],
        "input_meanings": [
            "2008 average trading debt/equity assets, USD million.",
            "2008 average trading derivative receivables, USD million.",
            "2007 average trading debt/equity assets, USD million.",
            "2007 average trading derivative receivables, USD million.",
        ],
        "context_segments": ["p0", "t0c0", "t0c2", "t0c3", "t1c0", "t2c0"],
        "exact": "58665",
        "independent_expression": "(384102 + 121417) - (381415 + 65439)",
        "interpretation": (
            "Sum the two asset categories in 2008 and subtract their 2007 sum. "
            "Do not use the 2009 column or subtract trading liabilities. Prose "
            "describes annual average balances, so do not relabel them year-end "
            "balances. The requested increase has an explicit positive direction."
        ),
        "precision_policy": (
            "The original question and table both specify million dollars. "
            "Selected integer amounts have no competing rounded/finer disclosure "
            "in the entry; exact sums are 505519 and 446854, a difference of 58665."
        ),
    },
}


def formula(key, selected):
    if key == "N1":
        return node("multiply", node("divide", *selected), "constant:100")
    if key == "N2":
        return node(
            "multiply",
            node("divide", selected[0], node("divide", selected[1], "constant:1000")),
            "constant:100",
        )
    if key in {"N3", "N5"}:
        return node("sum", *selected)
    if key == "N4":
        return node("average", *selected)
    if key == "N6":
        return node("subtract", node("sum", *selected[:2]), node("sum", *selected[2:]))
    raise KeyError(key)


def financial_relations(key, target):
    def cell(row, col):
        return f"source:t{row}c{col}n0"

    if key == "N1":
        # Acyclic regional identities also establish owned + leased global totals.
        relations = {cell(row, 3): node("add", cell(row, 1), cell(row, 2)) for row in (1, 2, 3)}
        relations.update({cell(3, col): node("add", cell(1, col), cell(2, col)) for col in (1, 2)})
        return relations
    if key == "N4":
        return {cell(3, col): node("add", cell(1, col), cell(2, col)) for col in (1, 2, 3)}
    if key == "N5":
        return {cell(8, 1): node("add", cell(4, 1), target)}
    return {}


def historical_selection_check():
    return {
        "baseline": SELECTION_BASELINE,
        "recorded_before_new_panel_source_creation": True,
        "method": "Read-only rg -l -F using each selected full filename, not only qa_id.",
        "patterns": [spec["qa_id"].rsplit("-", 1)[0] for spec in SPECS.values()],
        "checks": [
            {
                "paths": [
                    "trusted_data_synthesis/src",
                    "trusted_data_synthesis/tests",
                    "trusted_data_synthesis/docs",
                ],
                "matching_files": 0,
            },
            {
                "paths": ["trusted_data_synthesis/artifacts"],
                "globs": ["*registr*.json", "*task*.json", "*panel*.json"],
                "matching_files": 0,
            },
            {
                "paths": ["trusted_data_synthesis/artifacts"],
                "globs": ["**/public/*.json", "*context*.json"],
                "matching_files": 0,
            },
        ],
        "additional_check": (
            "Read the old twelve-task SPECS/exclusion list and current six-task "
            "autonomous plan; no selected page or original question is reused."
        ),
        "independent_root_baseline_recheck": {
            "baseline": SELECTION_BASELINE,
            "method": "git grep -l -F of the six exact full filenames in the fixed baseline commit",
            "pathspec_scope": [
                "trusted_data_synthesis/src",
                "trusted_data_synthesis/tests",
                "trusted_data_synthesis/docs",
                "artifact **/*registr*.json",
                "artifact **/*task*.json",
                "artifact **/*panel*.json",
                "artifact **/*context*.json",
                "artifact **/public/*.json",
                "artifact **/*_http_request.body",
            ],
            "matching_files": 0,
            "exit_code": 1,
            "reported_by": "root independent read-only check before new generation",
            "includes_saved_http_request_bodies": True,
            "new_source_self_matches_precluded_by_fixed_commit": True,
        },
        "limitations": [
            "The old mechanical census covered the frozen source; this is not a claim "
            "of no prior research scan.",
            "Checks cover current implementation, documents and specified run/public-task "
            "artifacts, not all git history or unregistered temporary/external conversations.",
            "No model-training-unseen or formal blind-test claim is made.",
            "Five companies and six company-year report groups; JPM repeats across 2009 and "
            "2010 with distinct pages, sources and financial questions.",
            "These are recorded pre-creation zero-hit observations, not a new search that "
            "excludes this file's self-matches.",
        ],
    }


class Panel:
    def __init__(self, root):
        raw = (Path(root) / DATA).read_bytes()
        self.source_sha256 = hashlib.sha256(raw).hexdigest()
        if self.source_sha256 != FROZEN_SOURCE_SHA256:
            raise ValueError("trace_panel.frozen_source_changed")
        rows = json.loads(raw)
        self.entries = {entry["id"]: entry for entry in rows}
        self.tasks = {}
        for key, spec in SPECS.items():
            entry = self.entries[spec["qa_id"]]
            if rows[spec["array_index"]]["id"] != spec["qa_id"]:
                raise ValueError("trace_panel.source_array_index_changed")
            segments, facts = catalog(entry)
            selected = [select(facts, *pair) for pair in spec["selectors"]]
            target = formula(key, selected)
            relations = financial_relations(key, target)
            exact = evaluate(target, facts)
            if exact != Fraction(spec["exact"]):
                raise ValueError("trace_panel.independent_target_disagreement")
            scale = 100 if spec["unit"] == "percent" else 1
            if abs(exact / scale - Fraction(str(entry["qa"]["exe_ans"]))) > Fraction("0.0000051"):
                raise ValueError("trace_panel.original_exe_ans_disagreement")
            for fact, derived in relations.items():
                if evaluate(fact, facts) != evaluate(derived, facts):
                    raise ValueError("trace_panel.financial_identity_disagreement")
            self.tasks[key] = {
                "key": key,
                "qa_id": spec["qa_id"],
                "unit": spec["unit"],
                "entry": entry,
                "facts": facts,
                "segments": segments,
                "selected": selected,
                "target": target,
                "relations": relations,
                "interpretation": spec["interpretation"],
                "precision_policy": spec["precision_policy"],
                "category": spec["category"],
                "context_segments": spec["context_segments"],
            }

    def design(self):
        tasks = []
        for key, task in self.tasks.items():
            spec, entry = SPECS[key], task["entry"]
            exact = evaluate(task["target"], task["facts"])
            tasks.append(
                {
                    "key": key,
                    "category": spec["category"],
                    "qa_id": task["qa_id"],
                    "filename": entry["filename"],
                    "company_year_report": entry["filename"].rsplit("/", 1)[0],
                    "source_array_index": spec["array_index"],
                    "question": entry["qa"]["question"],
                    "unit": task["unit"],
                    "original_program": entry["qa"]["program"],
                    "original_answer": entry["qa"]["answer"],
                    "original_exe_ans": entry["qa"]["exe_ans"],
                    "original_steps_preserved": entry["qa"].get("steps", []),
                    "original_gold_inds": entry["qa"]["gold_inds"],
                    "independent_expression": spec["independent_expression"],
                    "independent_exact_value": str(exact),
                    "independent_display_value": decimal(exact),
                    "reference_comparison": (
                        "Exact independent source arithmetic agrees with exe_ans at its "
                        "five-decimal annotation precision after percent scaling; original "
                        "coarse answer is preserved, not used as an exact target."
                    ),
                    "selected_inputs": [
                        {
                            **task["facts"][source_id],
                            "meaning": meaning,
                            "source_segment": task["segments"][task["facts"][source_id]["segment"]],
                        }
                        for source_id, meaning in zip(
                            task["selected"], spec["input_meanings"], strict=False
                        )
                    ],
                    "necessary_context": {
                        segment: task["segments"][segment] for segment in spec["context_segments"]
                    },
                    "target": task["target"],
                    "financial_relations": task["relations"],
                    "financial_relations_exact_check": True,
                    "interpretation": task["interpretation"],
                    "precision_policy": task["precision_policy"],
                    "no_question_rewrite": True,
                    "selectors_and_targets_private": True,
                }
            )
        return {
            "schema": "trace_delivery_migration_panel_selection_v1",
            "source_path": DATA,
            "source_sha256": self.source_sha256,
            "source_is_frozen_existing_test_file": True,
            "census_not_rerun": True,
            "tasks": tasks,
            "task_count": 6,
            "task_weights": {key: "1/6" for key in self.tasks},
            "category_counts": {
                category: 2
                for category in (
                    "ratio_and_scale",
                    "multi_period_aggregation",
                    "composite_amount_change",
                )
            },
            "distinct_company_year_reports": 6,
            "distinct_companies": 5,
            "selection_frozen_before_generation": True,
            "no_post_response_task_replacement": True,
            "history_search": historical_selection_check(),
            "alternatives_not_registered": [
                {
                    "qa_id": "BDX/2018/page_106.pdf-3",
                    "independent_expression": "(318 - 57 + 11) / 3",
                    "exact": "272/3",
                    "unit": "USD_million",
                    "reason_not_selected": (
                        "Valid signed three-year average; retaining JPM preserves a two-year "
                        "by two-asset aggregation rather than duplicating N4's average structure."
                    ),
                },
                {
                    "qa_id": "CME/2010/page_69.pdf-2",
                    "independent_expression": "945.5 / (1.4 * 1000) * 100",
                    "exact": "1891/28",
                    "unit": "percent",
                    "reason_not_selected": (
                        "Original estimated-total question uses disclosed 1.4 billion, whereas "
                        "420.5+945.5 million is 1366 million; prefer N2 to avoid this additional "
                        "rounding/source-precision ambiguity."
                    ),
                },
            ],
            "pre_generation_exclusions": [
                {
                    "qa_id": "DG/2005/page_44.pdf-2",
                    "reason": (
                        "Program includes 4.7 incurred prior to 2003 in a 2003-2005 total and "
                        "omits corresponding store impairments; original-question semantics "
                        "not certified."
                    ),
                },
                {
                    "qa_id": "GPN/2013/page_87.pdf-3",
                    "reason": (
                        "Arithmetic is valid but non-vested share-value topic is close to an "
                        "older development candidate and introduces a thousand-dollar output; "
                        "not selected."
                    ),
                },
            ],
            "unit_note": (
                "N3's original question explicitly requests billions; support that unit without "
                "converting or injecting a new requested unit into the original question."
            ),
            "public_information": (
                "Complete original table/pre_text/post_text and all numeric spans; private "
                "selections, targets, relations and interpretations never enter model requests."
            ),
        }
