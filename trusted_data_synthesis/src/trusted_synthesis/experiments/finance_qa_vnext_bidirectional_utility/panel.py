"""Exact source binding and company-disjoint panel registration before generation."""

import ast
import json
from collections import Counter
from fractions import Fraction

from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.census import DATA
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import evaluate
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.sources import catalog, select
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.panel import (
    FROZEN_SOURCE_SHA256,
    node,
)

from .panel_specs import CONFIRM, DEV, REJECTED_SCREEN, TRAIN
from .plan import (
    CONTROL_INDEX_SHA256,
    CONTROL_LABELS,
    CONTROLS,
    PARENT,
    STRUCTURES,
    TASKS,
    TRAIN_TASKS,
    read_json,
    record,
    require,
    sha,
)

GROUPS = ("dual_sufficient", "detail_related", "other_finance")
GOALS = {
    "X1": dict(
        quantity="net_change_company_defined_net_revenue",
        period="2003 minus 2002",
        unit="USD_million",
    ),
    "X2": dict(
        quantity="net_change_product_warranty_reserve", period="2006 minus 2005", unit="USD_million"
    ),
    "X3": dict(
        quantity="net_change_reconciled_unrecognized_tax_benefits",
        period="fiscal 2008 minus fiscal 2007",
        unit="USD_million",
    ),
}


def formula(text, aliases):
    """Parse only a host-reviewed finite expression, never model output."""

    def visit(item):
        if isinstance(item, ast.Name):
            return aliases[item.id]
        if isinstance(item, ast.Constant) and type(item.value) is int:
            require(item.value in {1, 2, 3, 4, 5, 100, 1000, 1000000}, "panel.constant")
            return "constant:" + str(item.value)
        if isinstance(item, ast.BinOp):
            op = {ast.Add: "add", ast.Sub: "subtract", ast.Mult: "multiply", ast.Div: "divide"}[
                type(item.op)
            ]
            return node(op, visit(item.left), visit(item.right))
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and not item.keywords:
            op = {"avg": "average", "abs": "absolute", "sum": "sum"}[item.func.id]
            return node(op, *map(visit, item.args))
        raise ValueError("panel.private_expression_domain")

    return visit(ast.parse(text, mode="eval").body)


def bind_spec(entries, key, spec, panel, group):
    entry = entries[spec["array_index"]]
    require(entry["id"] == spec["qa_id"], "panel.source_index:" + key)
    segments, facts = catalog(entry)
    aliases = {}
    for name, location in spec["bindings"].items():
        segment, token, *ordinal = location
        if ordinal:
            sid = f"source:{segment}n{ordinal[0]}"
            require(
                sid in facts and facts[sid]["token"] == token,
                "panel.exact_source_span:" + key + ":" + name,
            )
        else:
            sid = select(facts, segment, token)
        aliases[name] = sid
    target = formula(spec["expression"], aliases)
    relations = {aliases[name]: formula(text, aliases) for name, text in spec["relations"].items()}
    routes = {"D" if panel == "train" else "primary": target}
    if spec["alternative"]:
        routes["R" if panel == "train" else "alternative"] = formula(spec["alternative"], aliases)
    exact = evaluate(target, facts)
    for name, tree in routes.items():
        require(evaluate(tree, facts) == exact, "panel.sufficient_relation:" + key + ":" + name)
    for sid, tree in relations.items():
        require(evaluate(sid, facts) == evaluate(tree, facts), "panel.financial_identity:" + key)
    factor = Fraction(spec["annotation_factor"])
    require(
        abs(exact / factor - Fraction(str(entry["qa"]["exe_ans"]))) <= Fraction("0.0000051"),
        "panel.annotation_check:" + key,
    )
    context = sorted({facts[sid]["segment"] for sid in aliases.values()})
    return dict(
        key=key,
        panel=panel,
        group=group,
        qa_id=entry["id"],
        entry=entry,
        unit=spec["unit"],
        facts=facts,
        segments=segments,
        target=target,
        relations=relations,
        sufficient_routes=routes,
        selected=list(aliases.values()),
        source_bindings=aliases,
        original_private_spec=spec,
        goal_scope=GOALS[key]
        if key in GOALS
        else dict(
            quantity=spec["interpretation"], source_question_id=entry["id"], unit=spec["unit"]
        ),
        interpretation=spec["interpretation"],
        precision_policy=(
            (
                "Exact source-number arithmetic; unchanged publication_tolerance.v2 and parent "
                "quantity-unit normalization. Original executable annotation retained with "
                "explicit comparison factor "
            )
            + spec["annotation_factor"]
            + "; not a model target or a copied public answer."
        ),
        context_segments=context,
        source_array_index=spec["array_index"],
        structure=STRUCTURES[key] if key in STRUCTURES else group,
        company_cluster=entry["id"].split("/")[0],
        report_cluster="/".join(entry["id"].split("/")[:2]),
    )


class Panel:
    def __init__(self, root):
        raw = (root / DATA).read_bytes()
        require(sha(raw) == FROZEN_SOURCE_SHA256, "panel.frozen_dataset_bytes")
        entries = json.loads(raw)
        self.tasks = {}
        self.panels = {}
        for panel, specs, per_group in (
            ("train", TRAIN, None),
            ("dev", DEV, 4),
            ("confirm", CONFIRM, 8),
        ):
            keys = []
            for i, (key, spec) in enumerate(specs.items()):
                group = "training_dual_support" if per_group is None else GROUPS[i // per_group]
                self.tasks[key] = bind_spec(entries, key, spec, panel, group)
                keys.append(key)
            self.panels[panel] = keys
        require(
            len(self.tasks) == 39 and len({t["qa_id"] for t in self.tasks.values()}) == 39,
            "panel.unique_questions",
        )
        require(tuple(self.panels["train"]) == TASKS, "panel.three_training_tasks")
        require(
            all(set(self.tasks[key]["sufficient_routes"]) == {"D", "R"} for key in TASKS),
            "panel.two_real_training_routes",
        )
        self.control_sources = {}
        for key in CONTROLS:
            path = root / PARENT / f"preparation/public/{key}.json"
            public = read_json(path)
            self.control_sources[key] = dict(
                qa_id=public["task_id"],
                public_document_id=public["id"],
                file_sha256=sha(path.read_bytes()),
                company_cluster=public["filename"].split("/")[0],
            )
        self.companies = {
            panel: sorted({self.tasks[key]["company_cluster"] for key in keys})
            for panel, keys in self.panels.items()
        }
        self.companies["train"] = sorted(
            set(self.companies["train"])
            | {r["company_cluster"] for r in self.control_sources.values()}
        )
        for left, right in (("train", "dev"), ("train", "confirm"), ("dev", "confirm")):
            require(
                set(self.companies[left]).isdisjoint(self.companies[right]),
                "panel.company_isolation:" + left + ":" + right,
            )
        for panel, size in (("dev", 4), ("confirm", 8)):
            require(
                Counter(self.tasks[key]["group"] for key in self.panels[panel])
                == {group: size for group in GROUPS},
                "panel.group_sizes",
            )

    def design(self):
        return record(
            "precall_source_bound_panel",
            source_path=DATA,
            source_sha256=FROZEN_SOURCE_SHA256,
            panels=self.panels,
            company_clusters=self.companies,
            company_disjoint=True,
            eventual_task_marginal={key: "1/6" for key in TRAIN_TASKS},
            old_control_sources=self.control_sources,
            old_control_labels=list(CONTROL_LABELS),
            old_control_materialization_index_sha256=CONTROL_INDEX_SHA256,
            old_controls_requalified_or_retokenized=False,
            original_source_questions_not_rewritten=True,
            no_original_source_numeric_tokens_hidden_or_corrected=True,
            purposefully_source_selected_not_random_population=True,
            pretraining_visibility_unknown=True,
            within_panel_repeated_company_reports=True,
            independent_confirmation_means_not_used_in_this_experiment_candidate_selection=True,
            no_claim_every_confirmation_question_is_new_to_prior_research=True,
            source_screen_rejections=REJECTED_SCREEN,
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
                    "source_entry_sha256": sha(
                        json.dumps(task["entry"], sort_keys=True, ensure_ascii=False).encode()
                    ),
                    "source_numeric_catalog": task["facts"],
                    "all_sufficient_routes_and_identities_exactly_checked": True,
                    "route_menu_is_private_not_part_of_public_document": True,
                    "sufficient_routes_not_exhaustive_or_required": True,
                }
                for task in self.tasks.values()
            ],
        )
