"""Twelve fixed page-isolated questions; all target/route metadata remains private.

This is a purposively selected development evaluation panel, not a claim about
model pretraining novelty, a company-level holdout, or blind task selection.
"""

import json
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import (
    evaluate,
    lineage,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.sources import catalog, select

from .plan import BASELINE, SOURCE, read_json, record, require, sha
from .plan import TASKS as TRAINING_TASKS

DATA = "trusted_data_synthesis/benchmarks/finqa/frozen/test.json"
FROZEN_SOURCE_SHA256 = "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
TRANSFER_TASKS = tuple(f"T{i}" for i in range(1, 7))
REGRESSION_TASKS = tuple(f"R{i}" for i in range(1, 7))
EVAL_TASKS = TRANSFER_TASKS + REGRESSION_TASKS
TRAINING_PAGES = frozenset(
    {
        "INTC/2015/page_41.pdf",
        "GS/2015/page_188.pdf",
        "K/2006/page_52.pdf",
        "UNP/2007/page_25.pdf",
        "AON/2007/page_175.pdf",
        "AAPL/2003/page_48.pdf",
    }
)
ANNOTATION_TOLERANCE = Fraction(5, 1_000_000)


def node(op, *args):
    return {"op": op, "args": list(args)}


def cell(row, column):
    return f"source:t{row}c{column}n0"


def percentage(part, whole):
    return node("multiply", node("divide", part, whole), "constant:100")


def percentage_change(current, previous):
    return percentage(node("subtract", current, previous), previous)


SPECS = {
    "T1": {
        "array_index": 549,
        "qa_id": "IPG/2008/page_72.pdf-2",
        "question": (
            "what is the net change in the balance of unrecognized tax benefits during 2008?"
        ),
        "operation": "difference",
        "unit": "USD_million",
        "exact": "14",
        "selectors": [("t7c1", "148.8"), ("t1c1", "134.8")],
        "period": "calendar year 2008",
        "quantity": "net_change_unrecognized_tax_benefits",
        "context_segments": [
            "p0",
            "p3",
            "t0c1",
            "t0c2",
            *[f"t{r}c0" for r in range(1, 8)],
            "q0",
            "q1",
        ],
        "interpretation": (
            "The 2008 ending less opening balance, 148.8-134.8, equals complete signed "
            "movements 22.8-21.3-4.5-1.7+18.7. The 2007 ending balance also opens 2008. "
            "Interest/penalties and prospective future changes are separate quantities."
        ),
        "precision_policy": (
            "P0 explicitly states amounts in millions. One-decimal balances and all "
            "movements reconcile exactly; negative OCR repeats are not extra positive "
            "amounts. Do not replace 148.8 by rounded explanatory components 131.8+17.1, "
            "which sum to 148.9."
        ),
    },
    "T2": {
        "array_index": 1106,
        "qa_id": "PPG/2008/page_52.pdf-3",
        "question": (
            "what was the net change in the accrued liability for unrecognized tax "
            "benefits from 2007 to 2008?"
        ),
        "operation": "difference",
        "unit": "USD_million",
        "exact": "-11",
        "selectors": [("t9c1", "99"), ("t9c2", "110")],
        "period": "December 31 2008 minus December 31 2007",
        "quantity": "net_change_accrued_unrecognized_tax_benefit_liability",
        "context_segments": [
            "p0",
            "t0c0",
            "t0c1",
            "t0c2",
            *[f"t{r}c0" for r in range(1, 10)],
            "q0",
            "q2",
            "q3",
        ],
        "interpretation": (
            "Compare the two December 31 balances: 99-110. The 2007 ending balance equals "
            "the 2008 opening balance; complete 2008 movements are 12+5-17+20-6-21-4. "
            "Interest and penalties are disclosed separately."
        ),
        "precision_policy": (
            "Table/p0/q0 establish dollar millions. Current-year integer movements "
            "reconcile exactly. The 2007 pre-acquisition '2014' is an OCR dash artifact "
            "outside both selected target and 2008 movement route; no zero is silently "
            "assigned to that cell."
        ),
    },
    "T3": {
        "array_index": 419,
        "qa_id": "AMT/2006/page_113.pdf-2",
        "question": (
            "what is the net change in the balance of employee separations liability during 2004?"
        ),
        "operation": "difference",
        "unit": "USD_thousand",
        "exact": "-1574",
        "selectors": [("t1c4", "665"), ("t1c1", "2239")],
        "period": "calendar year 2004",
        "quantity": "net_change_employee_separation_liability",
        "context_segments": ["p15", "t0c1", "t0c2", "t0c3", "t0c4", "t1c0", "t2c0", "t3c0", "q0"],
        "interpretation": (
            "Use employee separations and 2004 only: December 31 balance 665 minus January "
            "1 balance 2239, or expense 823 plus signed cash payments -2397. "
            "Lease-termination costs, total restructuring and later periods are different "
            "targets."
        ),
        "precision_policy": (
            "P15 explicitly states in thousands and the monetary cells use dollar symbols. "
            "Exact target -1574 is USD_thousand, not USD_million. New unit aliases must be "
            "frozen before evaluation; panel construction does not convert or rewrite "
            "model publications."
        ),
    },
    "T4": {
        "array_index": 1061,
        "qa_id": "ABMD/2008/page_86.pdf-3",
        "question": (
            "what is the percentage change in the balance of unrecognized tax benefits "
            "from 2007 to 2008?"
        ),
        "operation": "percentage_change",
        "unit": "percent",
        "exact": "-25",
        "selectors": [("t2c1", "168"), ("t0c1", "224")],
        "period": "April 1 2007 through March 31 2008",
        "quantity": "percentage_change_unrecognized_tax_benefit_balance",
        "context_segments": ["p11", "p13", "t0c0", "t1c0", "t2c0"],
        "interpretation": (
            "The formal reconciliation supplies beginning 224 and ending 168: "
            "(168-224)/224*100. Its sole signed movement -56 gives the equivalent "
            "-56/224*100. The opening balance is the percentage denominator."
        ),
        "precision_policy": (
            "Exact disclosed dollar thousands cancel in the percentage. P13 excludes "
            "accrued interest; p11's rounded 0.2-million liability includes interest and "
            "is not a competing precise balance. The 0.3-million adoption adjustment is "
            "another object."
        ),
    },
    "T5": {
        "array_index": 585,
        "qa_id": "AON/2007/page_188.pdf-3",
        "question": (
            "what is the net change amount of unrecognized tax benefits during 2007 , ( in "
            "millions ) ?"
        ),
        "operation": "difference",
        "unit": "USD_million",
        "exact": "17",
        "selectors": [("t5c1", "70"), ("t0c1", "53")],
        "period": "calendar year 2007",
        "quantity": "net_change_unrecognized_tax_benefits",
        "context_segments": ["p0", "p1", "p2", *[f"t{r}c0" for r in range(6)], "q0", "q3", "q4"],
        "interpretation": (
            "During 2007 is bounded explicitly by January 1 and December 31 in this table. "
            "Net increase 70-53 equals 4+24-6-5. Interest, penalties and the 57-million "
            "effective-tax-rate subset are not additional total-balance movements."
        ),
        "precision_policy": (
            "Question and p2 explicitly state millions, with dollar-marked balances. All "
            "integers reconcile exactly. Evaluation page_188 is a different page/account "
            "from training AON/2007/page_175, but company and annual-report year are "
            "shared, not held out."
        ),
    },
    "T6": {
        "array_index": 40,
        "qa_id": "ETR/2013/page_21.pdf-3",
        "question": (
            "what is the net change in net revenue for entergy wholesale commodities during 2012?"
        ),
        "operation": "difference",
        "unit": "USD_million",
        "exact": "-191",
        "selectors": [("t5c1", "1854"), ("t1c1", "2045")],
        "period": "2012 minus 2011",
        "quantity": "net_change_wholesale_commodities_net_revenue",
        "context_segments": ["p12", "p13", "t0c1", *[f"t{r}c0" for r in range(1, 6)], "q0"],
        "interpretation": (
            "P12/question identify the Wholesale Commodities segment. Annual net-revenue "
            "change 1854-2045 equals signed drivers -194-33+36. This is a bridge between "
            "annual flows, not a stock-balance roll-forward."
        ),
        "precision_policy": (
            "P13/table explicitly state dollar millions and integers reconcile. Q0 also "
            "discloses a positive 191-million decrease magnitude, not a positive signed "
            "net change. Its presence may make this question easy; no non-saturated "
            "baseline is assumed."
        ),
    },
    "R1": {
        "array_index": 125,
        "qa_id": "AMT/2012/page_50.pdf-1",
        "question": (
            "for the quarter december 31 , 2012 what was the percent of the total number "
            "of shares purchased in december"
        ),
        "operation": "percentage_share",
        "unit": "percent",
        "exact": "5120000/309657",
        "selectors": [("t3c1", "102400"), ("t4c1", "619314")],
        "period": "fourth quarter 2012",
        "quantity": "December_share_of_quarter_repurchased_share_count",
        "context_segments": ["p0", "t0c1", "t1c0", "t2c0", "t3c0", "t4c0", "q0"],
        "interpretation": (
            "December repurchased share count 102400 divided by full-quarter count 619314, "
            "also reconstructable from October-November-December. Not a spending, "
            "average-price or remaining-authorization share."
        ),
        "precision_policy": (
            "Integer counts cancel their common unit. Original 16.5% is coarse, not the "
            "exact source ratio. P0 establishes all quarter repurchases as program "
            "repurchases, allowing duplicate program-share columns. January 2013 "
            "subsequent purchases are excluded."
        ),
    },
    "R2": {
        "array_index": 147,
        "qa_id": "PNC/2012/page_174.pdf-5",
        "question": (
            "in 2012 what was the percent of the total tdrs that was associated with "
            "commercial loans"
        ),
        "operation": "percentage_share",
        "unit": "percent",
        "exact": "54100/2859",
        "selectors": [("t2c1", "541"), ("t3c1", "2859")],
        "period": "December 31 2012",
        "quantity": "commercial_lending_share_of_total_TDR_amount",
        "context_segments": [
            "p0",
            "p7",
            "t0c0",
            "t0c1",
            "t1c0",
            "t2c0",
            "t3c0",
            "t7c0",
            "q4",
            "q5",
            "q6",
        ],
        "interpretation": (
            "The monetary 2012 TDR summary gives 541/2859*100, not loan counts. "
            "Consumer/commercial and nonperforming/accruing/credit-card are two complete "
            "partitions of the same total and cannot be added together."
        ),
        "precision_policy": (
            "Explicit dollar-million scale cancels. 2859=2318+541=1589+1037+233. Original "
            "18.9% is coarse. The joined OCR date in the 2012 heading does not make 312012 "
            "an input amount."
        ),
    },
    "R3": {
        "array_index": 608,
        "qa_id": "UAA/2016/page_42.pdf-4",
        "question": "what was the percentage change in working capital from 2015 to 2016?",
        "operation": "percentage_change",
        "unit": "percent",
        "exact": "25938400/1019953",
        "selectors": [("t2c1", "1279337"), ("t2c2", "1019953")],
        "period": "2016 minus 2015",
        "quantity": "percentage_change_company_defined_working_capital",
        "context_segments": ["q0", "t0c0", "t0c1", "t0c2", "t2c0"],
        "interpretation": (
            "Q0 defines working capital as current assets minus current liabilities. Use "
            "reported metric change (1279337-1019953)/1019953*100; total assets minus "
            "total debt is not this definition."
        ),
        "precision_policy": (
            "Exact reported dollar thousands cancel. Complete separate "
            "current-asset/current-liability inputs are absent, so no numerical "
            "definition-reconstruction route is fabricated. Original 25% is coarse, not "
            "the precise reference."
        ),
    },
    "R4": {
        "array_index": 1117,
        "qa_id": "UNP/2011/page_24.pdf-3",
        "question": "what was the percentage change in free cash flow from 2009 to 2010?",
        "operation": "percentage_change",
        "unit": "percent",
        "exact": "71600/699",
        "selectors": [("t6c2", "1415"), ("t6c3", "699")],
        "period": "2010 minus 2009",
        "quantity": "percentage_change_company_defined_free_cash_flow",
        "context_segments": [
            "p2",
            "p7",
            "q0",
            "q1",
            "t0c0",
            "t0c2",
            "t0c3",
            *[f"t{r}c0" for r in range(1, 7)],
        ],
        "interpretation": (
            "Company FCF uses CFO adjusted for receivables-securitization reclassification "
            "less investing cash use and dividends. (1415-699)/699*100 agrees with "
            "reconstructing both years using this definition, not generic CFO-minus-capex."
        ),
        "precision_policy": (
            "Integer dollar millions reconcile: 4105+400=4505; 4505-2488-602=1415; "
            "3204+184=3388; 3388-2145-544=699. Signed OCR repeats are not extra inputs. "
            "Approximate 2011 billion amounts and 2012 capex plans are outside scope; 102% "
            "is coarse."
        ),
    },
    "R5": {
        "array_index": 189,
        "qa_id": "LMT/2016/page_49.pdf-4",
        "question": "what were average operating profit for mfc in millions between 2014 and 2016?",
        "operation": "average",
        "unit": "USD_million",
        "exact": "3644/3",
        "selectors": [("t2c1", "1018"), ("t2c2", "1282"), ("t2c3", "1344")],
        "period": "annual 2014, 2015 and 2016 results",
        "quantity": "average_MFC_operating_profit",
        "context_segments": ["p10", "p11", "p14", "t0c1", "t0c2", "t0c3", "t2c0"],
        "interpretation": (
            "Average MFC operating-profit flows (1018+1282+1344)/3 for 2016/2015/2014. "
            "Preceding Aeronautics discussion and MFC sales/margins/backlog are other "
            "quantities, not inputs to this mean."
        ),
        "precision_policy": (
            "Original question and p14 explicitly specify millions. Use exact 3644/3, not "
            "rounded qa.answer=1215. Exe_ans=1214.66667 is within 5e-6 of exact "
            "arithmetic. Rounded margins are not used to reverse-engineer profit."
        ),
    },
    "R6": {
        "array_index": 493,
        "qa_id": "CB/2008/page_229.pdf-2",
        "question": "what was the average amortization expense from 2006 to 2008",
        "operation": "average",
        "unit": "USD_million",
        "exact": "77",
        "selectors": [("q8", "90"), ("q8", "77"), ("q8", "64")],
        "period": "years ended December 31 2006, 2007 and 2008",
        "quantity": "average_tangible_property_amortization_expense",
        "context_segments": ["q8", "t0c0"],
        "interpretation": (
            "Q8 explicitly pairs tangible-property amortization expense of 90, 77 and 64 "
            "million with 2008/2007/2006 respectively. Average these annual expenses, not "
            "unrelated statutory income/capital or insurance values."
        ),
        "precision_policy": (
            "The sentence explicitly gives dollars and millions for the annual amounts; "
            "the mean is exactly 77. This is an annual-flow average, not an ambiguous "
            "cross-snapshot asset aggregation."
        ),
    },
}


def _target(operation, selected):
    if operation == "difference":
        return node("subtract", *selected)
    if operation == "percentage_share":
        return percentage(*selected)
    if operation == "percentage_change":
        return percentage_change(*selected)
    require(operation == "average", "panel.known_target_operation")
    return node("average", *selected)


def _relations_and_routes(key, target, facts):
    relations, routes = {}, {"reported_balances_or_metric": target}
    if key == "T1":
        movements = node("sum", *[cell(r, 1) for r in range(2, 7)])
        relations = {cell(7, 1): node("add", cell(1, 1), movements), cell(1, 1): cell(7, 2)}
        routes["complete_signed_period_movements"] = movements
    elif key == "T2":
        movements = node("sum", *[cell(r, 1) for r in range(2, 9)])
        relations = {cell(9, 1): node("add", cell(1, 1), movements), cell(1, 1): cell(9, 2)}
        routes["complete_signed_2008_movements"] = movements
    elif key == "T3":
        movements = node("add", cell(1, 2), cell(1, 3))
        relations = {cell(1, 4): node("add", cell(1, 1), movements)}
        routes["complete_signed_2004_employee_movements"] = movements
    elif key == "T4":
        relations = {cell(2, 1): node("add", cell(0, 1), cell(1, 1))}
        routes["signed_movement_over_opening_balance"] = percentage(cell(1, 1), cell(0, 1))
    elif key == "T5":
        movements = node("sum", *[cell(r, 1) for r in range(1, 5)])
        relations = {cell(5, 1): node("add", cell(0, 1), movements)}
        routes["complete_signed_2007_movements"] = movements
    elif key == "T6":
        movements = node("sum", *[cell(r, 1) for r in range(2, 5)])
        relations = {
            cell(5, 1): node("add", cell(1, 1), movements),
            select(facts, "q0", "191"): node("subtract", cell(1, 1), cell(5, 1)),
        }
        routes["complete_signed_net_revenue_drivers"] = movements
    elif key == "R1":
        total = node("sum", *[cell(r, 1) for r in range(1, 4)])
        relations = {
            cell(4, 1): total,
            cell(3, 3): cell(3, 1),
            cell(4, 3): cell(4, 1),
            select(facts, "p0", "619314"): cell(4, 1),
        }
        routes["complete_monthly_quarter_total"] = percentage(cell(3, 1), total)
        routes["same_all_program_repurchase_column"] = percentage(cell(3, 3), cell(4, 3))
    elif key == "R2":
        lending = node("add", cell(1, 1), cell(2, 1))
        status_total = node("sum", *[cell(r, 1) for r in range(4, 7)])
        relations = {
            cell(3, 1): lending,
            cell(7, 1): cell(3, 1),
            # Acyclic encoding of the complete, separately disclosed status
            # partition, not a numeric-equality guess or an online route hint.
            cell(4, 1): node("subtract", cell(7, 1), node("add", cell(5, 1), cell(6, 1))),
        }
        routes["consumer_plus_commercial_total"] = percentage(cell(2, 1), lending)
        routes["complete_status_partition_total"] = percentage(cell(2, 1), status_total)
    elif key == "R4":
        for col in (2, 3):
            relations[cell(3, col)] = node("add", cell(1, col), cell(2, col))
            relations[cell(6, col)] = node("sum", cell(3, col), cell(4, col), cell(5, col))
        reconstructed = [node("sum", *[cell(r, col) for r in (1, 2, 4, 5)]) for col in (2, 3)]
        routes["complete_company_definition_both_years"] = percentage_change(*reconstructed)
    return relations, routes


def selection_record():
    return {
        "baseline": BASELINE,
        "questions_selected_before_any_Student_run": True,
        "source_isolation_level": "page, not company, annual report, or pretraining data",
        "all_12_pages_distinct_and_disjoint_from_6_training_pages": True,
        "bounded_prior_use_check": (
            "Full page-name search in baseline src/tests/docs and saved "
            "registrations/task/panel/context/public and HTTP-request artifacts; no "
            "collected-session matches found in that scope. Not all git history, research "
            "reads, or pretraining."
        ),
        "previous_source_only_mentions_or_reads": [
            {
                "filename": "LMT/2016/page_49.pdf",
                "path": (
                    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_"
                    "source_distinct_support/source.py"
                ),
                "line_at_baseline": 97,
                "kind": "source-only catalog; not a sampled-session record",
            },
            {
                "kind": (
                    "Some transfer questions, including IPG and AON, were inspected as "
                    "unused candidates in earlier source selection; this is not blind or "
                    "previously-unread task selection."
                )
            },
        ],
        "shared_training_company_or_report": {
            "T5": (
                "AON/2007: evaluation page_188, training page_175; different account/page, "
                "same company/report year."
            ),
            "R4": (
                "UNP: evaluation 2011/page_24, training 2007/page_25; same company, "
                "different year/page."
            ),
        },
        "selection_exclusions": [
            {
                "qa_id": "KHC/2018/page_132.pdf-3",
                "array_index": 283,
                "reason": (
                    "'During the period of 2016 to 2018' did not uniquely select January "
                    "2016 rather than December 2016 as the starting balance; both exist. "
                    "Rejected before Student runs, not resolved by exe_ans=6. Replaced by "
                    "explicit-year AON T5."
                ),
            },
            {
                "filename": "APD/2016/page_40.pdf",
                "reason": (
                    "Rejected regression-average candidate because the closed page did not "
                    "clearly establish the proposed dollar-million table scale; R5 "
                    "explicitly does."
                ),
            },
        ],
        "purposive_development_panel_not_natural_frequency": True,
        "no_pretraining_unseen_company_holdout_or_blind_selection_claim": True,
        "baseline_saturation_not_assumed_absent": True,
        "candidate_search_closed_before_baseline_and_P_Q_runs": True,
        "provider_calls": 0,
    }


class Panel:
    def __init__(self, root):
        root = Path(root)
        raw = (root / DATA).read_bytes()
        require(sha(raw) == FROZEN_SOURCE_SHA256, "panel.frozen_FinQA_source")
        entries = json.loads(raw)
        require(tuple(SPECS) == EVAL_TASKS, "panel.fixed_twelve_task_order")
        training_pages = {
            read_json(root / SOURCE / f"preparation/public/{key}.json")["filename"]
            for key in TRAINING_TASKS
        }
        require(training_pages == TRAINING_PAGES, "panel.actual_six_training_pages")
        self.tasks = {}
        for key, spec in SPECS.items():
            entry = entries[spec["array_index"]]
            require(entry["id"] == spec["qa_id"], "panel.fixed_source_index_and_id")
            require(
                entry["qa"]["question"] == spec["question"], "panel.original_question_unchanged"
            )
            require(entry["filename"] not in training_pages, "panel.no_training_page_overlap")
            segments, facts = catalog(entry)
            selected = [select(facts, *selector) for selector in spec["selectors"]]
            target = _target(spec["operation"], selected)
            relations, routes = _relations_and_routes(key, target, facts)
            exact = evaluate(target, facts)
            require(exact == Fraction(spec["exact"]), "panel.independent_exact_target")
            for name, route in routes.items():
                require(evaluate(route, facts) == exact, "panel.sufficient_route:" + name)
            for sid, expression in relations.items():
                require(
                    evaluate(sid, facts) == evaluate(expression, facts),
                    "panel.exact_financial_identity",
                )
            scale = 100 if spec["unit"] == "percent" else 1
            annotation_error = abs(exact / scale - Fraction(str(entry["qa"]["exe_ans"])))
            require(annotation_error <= ANNOTATION_TOLERANCE, "panel.original_exe_ans_consistency")
            require(
                all(segment in segments for segment in spec["context_segments"]),
                "panel.actual_context_segments",
            )
            self.tasks[key] = {
                "key": key,
                "qa_id": entry["id"],
                "entry": entry,
                "segments": segments,
                "facts": facts,
                "target": target,
                "relations": relations,
                "unit": spec["unit"],
                "interpretation": spec["interpretation"],
                "precision_policy": spec["precision_policy"],
                "group": "transfer" if key in TRANSFER_TASKS else "regression",
                "context_segments": spec["context_segments"],
                "selected": selected,
                "source_array_index": spec["array_index"],
                "source_selectors": spec["selectors"],
                "sufficient_routes": routes,
                "exact_target": str(exact),
                "goal_scope": {
                    "quantity": spec["quantity"],
                    "period": spec["period"],
                    "unit": spec["unit"],
                },
                "original_exe_ans_absolute_error": str(annotation_error),
            }
        pages = [task["entry"]["filename"] for task in self.tasks.values()]
        require(len(pages) == len(set(pages)) == 12, "panel.twelve_distinct_evaluation_pages")

    def design(self):
        rows = []
        for task in self.tasks.values():
            included = lineage(task["target"])
            for sid, expression in task["relations"].items():
                included.add(sid)
                included.update(lineage(expression))
            for expression in task["sufficient_routes"].values():
                included.update(lineage(expression))
            rows.append(
                {
                    **{
                        key: value
                        for key, value in task.items()
                        if key not in {"entry", "segments", "facts", "selected"}
                    },
                    "filename": task["entry"]["filename"],
                    "original_question": task["entry"]["qa"]["question"],
                    "original_qa_annotation": task["entry"]["qa"],
                    "primary_source_bindings": [
                        {
                            "selector": list(selector),
                            "source_id": sid,
                            "fact": task["facts"][sid],
                            "source_segment": task["segments"][task["facts"][sid]["segment"]],
                        }
                        for selector, sid in zip(
                            task["source_selectors"], task["selected"], strict=True
                        )
                    ],
                    "facts_in_registered_targets_routes_or_identities": {
                        sid: task["facts"][sid] for sid in sorted(included)
                    },
                    "necessary_context": {
                        segment: task["segments"][segment] for segment in task["context_segments"]
                    },
                    "sufficient_routes_not_exhaustive_or_required": True,
                    "financial_identities_are_private_not_online_route_instructions": True,
                    "original_question_and_full_source_preserved": True,
                }
            )
        return record(
            "fixed_twelve_question_evaluation_panel",
            source_path=DATA,
            source_sha256=FROZEN_SOURCE_SHA256,
            training_source_root=SOURCE,
            training_pages=sorted(TRAINING_PAGES),
            evaluation_task_order=list(EVAL_TASKS),
            transfer_tasks=list(TRANSFER_TASKS),
            regression_tasks=list(REGRESSION_TASKS),
            tasks=rows,
            selection=selection_record(),
            all_target_routes_and_financial_identities_exactly_checked=True,
            original_exe_ans_check=(
                "percent targets divided by 100; absolute error <= 5e-6; annotation sanity "
                "check is not the model publication tolerance"
            ),
            source_reporting_units_preserved=True,
            new_canonical_units=["USD_thousand"],
            original_rounded_answer_strings_not_used_as_exact_targets=True,
            no_Student_Teacher_or_GPU_needed_for_panel_construction=True,
            provider_calls=0,
        )


def build(root):
    return Panel(root)
