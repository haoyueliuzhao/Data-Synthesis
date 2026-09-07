"""Twelve pre-call independently reviewed ORIGINAL questions, not generated variants."""

from __future__ import annotations

import json
from fractions import Fraction

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require

from .census import DATA, digest, structure
from .sources import catalog, select, view


def node(op, *args):
    return {"op": op, "args": list(args)}


# Source selector order is PRIVATE verification/build order, never a public plan.
SPECS = {
    "C1": (
        "control",
        "ETR/2016/page_23.pdf-2",
        "USD_million",
        [("t8c1", "5829"), ("t1c1", "5735")],
        "Direct two-year net-revenue difference; source table states millions.",
        ["p9", "p10"],
    ),
    "C2": (
        "control",
        "UNP/2015/page_56.pdf-1",
        "percent",
        [("t1c1", "3581"), ("t9c1", "21813")],
        "Agricultural products / operating revenue, 2015; NOT the old freight-share task.",
        ["t0c0", "p10"],
    ),
    "C3": (
        "control",
        "GS/2017/page_132.pdf-2",
        "USD_million",
        [("t1c1", "15395"), ("t1c2", "18035")],
        "Minimum of two explicitly named years, one metric; compare both values.",
        ["t0c0", "p0", "p1"],
    ),
    "E1": (
        "evidence",
        "ADBE/2008/page_89.pdf-3",
        "percent",
        [("t6c1", "139549"), ("q2", "15.3")],
        (
            "Table ending liability and text interest/penalties. Text q0 discloses "
            "the same ending liability rounded to 139.5 million, supporting the "
            "table's thousand scale; use unrounded table amount."
        ),
        ["p0", "q0"],
    ),
    "E2": (
        "evidence",
        "STT/2009/page_127.pdf-4",
        "USD",
        [("q10", "5576208"), ("q10", "53.80")],
        (
            "Warrant shares times exercise price, not preferred shares, liquidation "
            "preference, or allocated warrant fair value."
        ),
        [],
    ),
    "E3": (
        "evidence",
        "BKR/2017/page_56.pdf-2",
        "percent",
        [("p1", "7.0"), ("p2", "997")],
        (
            "GE cash in millions divided by 2017 cash/equivalents in billions; "
            "source-bound 7.0 is NOT a free const_7."
        ),
        [],
    ),
    "M1": (
        "method",
        "MRO/2011/page_108.pdf-1",
        "USD_million",
        [("t11c1", "4648"), ("t11c2", "3625"), ("t11c3", "1620")],
        (
            "Average of all three net annual changes, not beginning/ending balances; "
            "one aggregate annotation has three operands."
        ),
        ["p0", "t0c0"],
    ),
    "M2": (
        "method",
        "ETR/2017/page_143.pdf-1",
        "USD_thousand",
        [
            (f"t{i}c1", v)
            for i, v in enumerate(["760000", "857679", "898500", "960764", "1304431"], 1)
        ],
        (
            "Sum five annual maturities 2018-2022. Four annotation adds can legally "
            "be one selected-member sum."
        ),
        ["t0c1"],
    ),
    "M3": (
        "method",
        "UNP/2016/page_52.pdf-3",
        "percent",
        [
            (f"t{r}c{c}", v)
            for r, vals in [(4, ["2440", "3237", "4127"]), (9, ["19941", "21813", "23988"])]
            for c, v in enumerate(vals, 1)
        ],
        (
            "Ratio of three-year aggregate coal revenues to aggregate operating "
            "revenues, not average annual ratios or freight total."
        ),
        ["t0c0", "p10"],
    ),
    "J1": (
        "joint",
        "GPN/2010/page_87.pdf-2",
        "percent",
        [("t1c1", "18.1"), ("t2c1", "-6.3"), ("t1c2", "14.6"), ("t2c2", "-5.2")],
        (
            "After-tax costs are cost PLUS signed negative tax benefit for each year; "
            "relative change uses 2009 net base. Annotation uses positive magnitudes "
            "with subtraction, algebraically consistent."
        ),
        ["p18", "p19"],
    ),
    "J2": (
        "joint",
        "HWM/2018/page_96.pdf-2",
        "USD_million",
        [("t3c2", "11"), ("q0", "33.32"), ("t3c3", "13"), ("q0", "26.93")],
        (
            "Million option shares times dollars/share in 2017 and 2016, then 2017 "
            "minus 2016; NOT diluted incremental option shares in other paragraphs."
        ),
        ["p0"],
    ),
    "J3": (
        "joint",
        "ETR/2016/page_150.pdf-1",
        "USD_million",
        [("p1", v) for v in ["21.7", "22.3", "22.7", "23.2", "11"]],
        (
            "Five Louisiana investment-recovery payments, excluding same-year New "
            "Orleans storm payments and unrelated Texas table; text aggregation."
        ),
        [],
    ),
}

EXCLUSIONS = [
    {
        "qa_id": "ETR/2017/page_372.pdf-1",
        "reason": (
            "(703.1+705.4)/2 is 704.25. Program inserts add(#0,const_2); exe_ans "
            "becomes 705.25, but steps omit that addition. Not a real extra reasoning "
            "step."
        ),
    },
    {
        "qa_id": "GPN/2010/page_89.pdf-4",
        "reason": (
            "Program uses 41 for 2009 non-vested fair value, but table row5 col2 is "
            "42; 41 belongs to vested row7. Independent original-question answer is "
            "(713*42-762*42)/(762*42), not annotated -0.04148. Excluded before "
            "Provider, not silently corrected."
        ),
    },
    {
        "qa_id": "MRK/2013/page_125.pdf-4",
        "reason": (
            "Decrease wording and positive answer conflict with negative "
            "signed-change program/exe_ans; avoid changing requested direction or "
            "gold convention in this first panel."
        ),
    },
    {
        "qa_id": "MSI/2008/page_69.pdf-1",
        "reason": (
            "Text describes segment / consolidated proportions; reconstructing "
            "consolidated requires division, not annotated multiplication, and answer "
            "sign conflicts with exe_ans. Excluded before Provider."
        ),
    },
    {
        "qa_id": "HWM/2015/page_173.pdf-2",
        "reason": (
            "Denominator definition 'tax liabilities' is not clearly established by "
            "summing only two reduction rows; semantic ambiguity, not certified."
        ),
    },
    {
        "qa_id": "GRMN/2008/page_85.pdf-2",
        "reason": (
            "Difference direction insufficiently explicit; not used to impose "
            "reference-program sign as unique original-question meaning."
        ),
    },
]


def formula(key, f):
    a = node

    def percent(x):
        return a("multiply", x, "constant:100")

    if key == "C1":
        return a("subtract", *f)
    if key == "C2":
        return percent(a("divide", *f))
    if key == "C3":
        return a("minimum", *f)
    if key == "E1":
        return percent(a("divide", f[1], a("divide", f[0], "constant:1000")))
    if key == "E2":
        return a("multiply", *f)
    if key == "E3":
        return percent(a("divide", f[1], a("multiply", f[0], "constant:1000")))
    if key == "M1":
        return a("average", *f)
    if key in {"M2", "J3"}:
        return a("sum", *f)
    if key == "M3":
        return percent(a("divide", a("sum", *f[:3]), a("sum", *f[3:])))
    if key == "J1":
        end, base = a("add", *f[:2]), a("add", *f[2:])
        return percent(a("divide", a("subtract", end, base), base))
    if key == "J2":
        return a("subtract", a("multiply", *f[:2]), a("multiply", *f[2:]))
    raise KeyError(key)


class Panel:
    def __init__(self, root):
        self.entries = {row["id"]: row for row in json.loads((root / DATA).read_bytes())}
        self.tasks = {}
        for key, (
            stratum,
            qa_id,
            unit,
            selectors,
            interpretation,
            context_segments,
        ) in SPECS.items():
            entry = self.entries[qa_id]
            segments, facts = catalog(entry)
            chosen = [select(facts, *selector) for selector in selectors]
            self.tasks[key] = {
                "key": key,
                "stratum": stratum,
                "qa_id": qa_id,
                "unit": unit,
                "entry": entry,
                "facts": facts,
                "selected": chosen,
                "target": formula(key, chosen),
                "interpretation": interpretation,
                "context_segments": context_segments,
            }
            relations = {}

            def cell(r, c):
                return f"source:t{r}c{c}n0"

            if key == "C1":
                relations[cell(8, 1)] = node(
                    "add", cell(1, 1), node("sum", *(cell(r, 1) for r in range(2, 8)))
                )
            elif key in {"C2", "M3"}:
                for c in range(1, 4):
                    relations[cell(7, c)] = node("sum", *(cell(r, c) for r in range(1, 7)))
                    relations[cell(9, c)] = node("add", cell(7, c), cell(8, c))
            elif key == "M1":
                for c in range(1, 4):
                    relations[cell(11, c)] = node("subtract", cell(13, c), cell(12, c))
            from .semantics import evaluate

            for fact, derived in relations.items():
                require(
                    evaluate(fact, facts) == evaluate(derived, facts),
                    "panel.financial_identity_numeric_check",
                )
            self.tasks[key]["relations"] = relations

    def public(self, key, condition):
        task = self.tasks[key]
        source = view(task["entry"], task["selected"], condition)
        if condition == "E":
            segments, _ = catalog(task["entry"])
            source["necessary_context"] = {k: segments[k] for k in task["context_segments"]}
        return record(
            "context",
            task_id=task["qa_id"],
            question=task["entry"]["qa"]["question"],
            answer_unit=task["unit"],
            source_document=task["entry"]["filename"],
            source_digest=digest([task["entry"][k] for k in ("table", "pre_text", "post_text")]),
            information_condition=condition,
            **source,
        )

    def bindings(self):
        from .semantics import decimal, evaluate, expression

        bindings = []
        for key, task in self.tasks.items():
            value = evaluate(task["target"], task["facts"])
            scale = 100 if task["unit"] == "percent" else 1
            original = Fraction(str(task["entry"]["qa"]["exe_ans"]))
            require(
                abs(value / scale - original) <= Fraction("0.0000051"),
                "panel.original_numeric_disagreement",
            )
            bindings.append(
                record(
                    "finqa_binding",
                    task_key=key,
                    stratum=task["stratum"],
                    qa_id=task["qa_id"],
                    original_qa=task["entry"]["qa"],
                    original_source={
                        k: task["entry"][k] for k in ("table", "pre_text", "post_text")
                    },
                    selected_facts=[task["facts"][f] for f in task["selected"]],
                    independently_reviewed_target=task["target"],
                    unit=task["unit"],
                    exact_value=str(value),
                    display_value=decimal(value),
                    interpretation=task["interpretation"],
                    original_annotations_preserved=True,
                    semantic_question_changed=False,
                    gold_numeric_check=(
                        "independent source calculation agrees with exe_ans rounded to 5 decimals"
                    ),
                    grain=structure(task["entry"]["qa"]["program"]),
                    symbolic_target=str(expression(task["target"], task["facts"])),
                    reviewed_source_identities=task["relations"],
                )
            )
        return bindings
