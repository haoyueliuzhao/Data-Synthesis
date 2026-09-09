"""Three known mechanism anchors and three newly selected real-source questions."""

import json
from fractions import Fraction

from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.census import DATA
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import evaluate
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.sources import catalog, select
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.panel import (
    FROZEN_SOURCE_SHA256,
    financial_relations,
    formula,
    node,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.panel import (
    SPECS as ANCHOR_SPECS,
)

from .plan import ANCHORS, BASELINE, STRUCTURES, TASKS, record, require, sha

NEW_SPECS = {
    "G2": {
        "qa_id": "GS/2015/page_188.pdf-2",
        "array_index": 7,
        "unit": "percent",
        "selectors": [("t3c1", "301"), ("t7c1", "2575")],
        "exact": "1204/103",
        "interpretation": (
            "Percentage of future minimum net rental payments due in 2018, from one December 2015"
            " disclosure snapshot. Six mutually exclusive maturity buckets cover the total; this "
            "is not six asset snapshots summed over time."
        ),
        "precision_policy": (
            "Use disclosed integer USD millions. The complete components sum to 2575 exactly. The"
            " original 12% is coarse; the exact target is 1204/103 percent under unchanged "
            "publication tolerance v2. The unrelated 2015 rent expense 249 is not the "
            "denominator."
        ),
        "context_segments": [
            "p23",
            "p25",
            "p26",
            "t0c0",
            "t0c1",
            *[f"t{r}c0" for r in range(1, 8)],
        ],
        "sufficient_expressions": ["301 / 2575 * 100", "301 / (317+313+301+258+226+1160) * 100"],
        "goal_scope": {
            "quantity": "2018_due_share_of_all_future_minimum_net_rental_payments",
            "period": "December 2015 disclosure; maturity year 2018",
            "unit": "percent",
        },
    },
    "F2": {
        "qa_id": "UNP/2007/page_25.pdf-4",
        "array_index": 1109,
        "unit": "USD_million",
        "selectors": [("t4c2", "516"), ("t4c3", "234")],
        "exact": "282",
        "interpretation": (
            "Increase from 2005 to 2006 in Union Pacific's explicitly defined non-GAAP free cash "
            "flow. Its definition includes all cash used in investing AND dividends, not an "
            "assumed generic CFO-minus-capex metric."
        ),
        "precision_policy": (
            "Integer USD millions. 2880-2042-322=516 and 2595-2047-314=234 exactly. Accounting "
            "negative and parenthetic OCR repeat are one disclosure, not two facts. Prose 3.3 "
            "billion describes 2007, not a competing precision for the target years. Adjacent "
            "question -3 was rejected for inconsistent year/program annotation; selected -4 "
            "agrees."
        ),
        "context_segments": [
            "p6",
            "p7",
            "p10",
            "t0c0",
            "t0c2",
            "t0c3",
            "t1c0",
            "t2c0",
            "t3c0",
            "t4c0",
        ],
        "sufficient_expressions": ["516 - 234", "(2880-2042-322) - (2595-2047-314)"],
        "goal_scope": {
            "quantity": "change_in_company_defined_free_cash_flow",
            "period": "2006 minus 2005",
            "unit": "USD_million",
        },
    },
    "L2": {
        "qa_id": "AAPL/2003/page_48.pdf-2",
        "array_index": 202,
        "unit": "USD_million",
        "selectors": [("t3c1", "7.2"), ("t0c1", "5.5")],
        "exact": "17/10",
        "interpretation": (
            "Net increase in fiscal 2003 asset retirement liability: September 27 2003 closing "
            "less September 29 2002 opening, or additional obligations plus accretion. Both "
            "routes require just one arithmetic operation."
        ),
        "precision_policy": (
            "One-decimal USD millions. Full roll-forward 5.5+0.5+1.2=7.2. The approximately 2 "
            "million income adjustment in adoption prose is not an extra roll-forward movement. "
            "Table row zero is the opening balance, not a removable header; catalog column labels"
            " mechanically repeat that first row."
        ),
        "context_segments": ["p0", "p1", "p2", "p3", "t0c0", "t1c0", "t2c0", "t3c0"],
        "sufficient_expressions": ["7.2 - 5.5", "0.5 + 1.2"],
        "goal_scope": {
            "quantity": "net_change_asset_retirement_liability",
            "period": "fiscal year ended September 27 2003",
            "unit": "USD_million",
        },
    },
}
ANCHOR_GOALS = {
    "G1": {
        "quantity": "global_leased_facility_area_share",
        "period": "2015 disclosed snapshot",
        "unit": "percent",
    },
    "F1": {
        "quantity": "average_company_defined_cash_flow",
        "period": "2004-2006",
        "unit": "USD_million",
    },
    "L1": {
        "quantity": "net_change_unpaid_restructuring_liability",
        "period": "2006",
        "unit": "USD_million",
    },
}


def cell(row, column):
    return f"source:t{row}c{column}n0"


def new_relations(key):
    if key == "G2":
        return {cell(7, 1): node("sum", *[cell(r, 1) for r in range(1, 7)])}
    if key == "F2":
        return {cell(4, col): node("sum", *[cell(r, col) for r in (1, 2, 3)]) for col in (2, 3)}
    return {cell(3, 1): node("sum", *[cell(r, 1) for r in (0, 1, 2)])}


def routes(key, target):
    if key == "G1":
        alternative = node(
            "multiply",
            node(
                "divide", node("sum", cell(2, 1), cell(2, 2)), node("sum", cell(3, 1), cell(3, 2))
            ),
            "constant:100",
        )
    elif key == "G2":
        alternative = node(
            "multiply",
            node("divide", cell(3, 1), node("sum", *[cell(r, 1) for r in range(1, 7)])),
            "constant:100",
        )
    elif key == "F1":
        alternative = node("average", *[node("add", cell(1, c), cell(2, c)) for c in (1, 2, 3)])
    elif key == "F2":
        alternative = node(
            "subtract", *[node("sum", *[cell(r, c) for r in (1, 2, 3)]) for c in (2, 3)]
        )
    elif key == "L1":
        # Historical target is already the movements route; disclose both without
        # privileging the order in online input (neither is shown to the worker).
        return {"balances": node("subtract", cell(8, 1), cell(4, 1)), "movements": target}
    else:
        alternative = node("add", cell(1, 1), cell(2, 1))
    return {"disclosed_or_balances": target, "reconstructed_or_movements": alternative}


def history_selection_record():
    return {
        "baseline": BASELINE,
        "checked_pages": [v["qa_id"].rsplit("-", 1)[0] for v in NEW_SPECS.values()],
        "scope": (
            "current src/tests/docs plus saved registrations/task/panel/context/public and actual"
            " HTTP request artifacts, by full page name; not all git history or model training "
            "data"
        ),
        "new_pages_previously_sampled_in_checked_scope": False,
        "GS_old_census_catalog_mentions_not_sampled_sessions": True,
        "excluded_other_candidate": "UNP/2015/page_56.pdf had historical C2 sampling",
        "source_census_or_old_controls_repeated": False,
        "mechanism_selected_development_panel_not_natural_frequency_or_blind_test": True,
    }


class Panel:
    def __init__(self, root):
        raw = (root / DATA).read_bytes()
        require(sha(raw) == FROZEN_SOURCE_SHA256, "panel.frozen_source")
        entries = json.loads(raw)
        self.tasks = {}
        for key in TASKS:
            anchor = ANCHORS.get(key)
            spec = ANCHOR_SPECS[anchor] if anchor else NEW_SPECS[key]
            entry = entries[spec["array_index"]]
            require(entry["id"] == spec["qa_id"], "panel.source_index")
            segments, facts = catalog(entry)
            selected = [select(facts, *s) for s in spec["selectors"]]
            target = (
                formula(anchor, selected)
                if anchor
                else (
                    node("multiply", node("divide", *selected), "constant:100")
                    if key == "G2"
                    else node("subtract", *selected)
                )
            )
            relations = financial_relations(anchor, target) if anchor else new_relations(key)
            sufficient = routes(key, target)
            exact = evaluate(target, facts)
            require(exact == Fraction(spec["exact"]), "panel.exact_target")
            for name, tree in sufficient.items():
                require(evaluate(tree, facts) == exact, "panel.sufficient_route:" + name)
            for sid, tree in relations.items():
                require(evaluate(sid, facts) == evaluate(tree, facts), "panel.financial_identity")
            scale = 100 if spec["unit"] == "percent" else 1
            require(
                abs(exact / scale - Fraction(str(entry["qa"]["exe_ans"]))) <= Fraction("0.0000051"),
                "panel.original_answer_annotation",
            )
            self.tasks[key] = {
                "key": key,
                "qa_id": entry["id"],
                "entry": entry,
                "unit": spec["unit"],
                "facts": facts,
                "segments": segments,
                "target": target,
                "relations": relations,
                "selected": selected,
                "sufficient_routes": sufficient,
                "goal_scope": ANCHOR_GOALS[key] if anchor else spec["goal_scope"],
                "interpretation": spec["interpretation"],
                "precision_policy": spec["precision_policy"],
                "context_segments": spec["context_segments"],
                "source_array_index": spec["array_index"],
                "structure": STRUCTURES[key],
                "anchor_from_old_panel": anchor,
            }

    def design(self):
        return record(
            "six_task_support_panel",
            source_path=DATA,
            source_sha256=FROZEN_SOURCE_SHA256,
            original_source_questions_not_rewritten=True,
            new_population_not_deletion_of_old_N3=True,
            task_marginal={key: "1/6" for key in TASKS},
            selection_check=history_selection_record(),
            tasks=[
                {
                    **{
                        k: v
                        for k, v in task.items()
                        if k not in {"facts", "segments", "entry", "selected"}
                    },
                    "original_question": task["entry"]["qa"]["question"],
                    "filename": task["entry"]["filename"],
                    "original_qa_annotation": task["entry"]["qa"],
                    "exact_target": str(evaluate(task["target"], task["facts"])),
                    "necessary_context": {
                        key: task["segments"][key] for key in task["context_segments"]
                    },
                    "source_facts_for_all_sufficient_relations": task["facts"],
                    "all_sufficient_routes_and_identities_exactly_checked": True,
                    "route_menu_is_private_not_part_of_public_document": True,
                    "routes_are_sufficient_not_exhaustive_or_required": True,
                }
                for task in self.tasks.values()
            ],
        )
