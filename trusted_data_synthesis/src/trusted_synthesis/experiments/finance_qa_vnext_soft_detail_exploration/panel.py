"""Three source-bound tasks only; old development/confirmation data are never selected."""

import copy
import json
from fractions import Fraction

from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.panel import bind_spec
from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.panel_specs import TRAIN
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.census import DATA
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import evaluate
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.panel import FROZEN_SOURCE_SHA256
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.stage import public_document

from .plan import PARENT, TASKS, encode, read_json, record, require, sha

CLARIFIED_TASK_ID = "GRMN/2008/page_85.pdf-1::year_end_change_2007_2008.v2"
CLARIFIED_QUESTION = (
    "What is the net change in the balance of unrecognized tax benefits from the end of the "
    "fiscal year ended December 29, 2007 to the end of the fiscal year ended December 27, 2008, "
    "in millions of U.S. dollars? The requested interval is between these two year ends, not "
    "the cumulative change over both fiscal years."
)


class Panel:
    def __init__(self, root):
        raw = (root / DATA).read_bytes()
        require(sha(raw) == FROZEN_SOURCE_SHA256, "panel.original_source_dataset")
        entries = json.loads(raw)
        self.tasks, self.public, self.private, self.identities = {}, {}, {}, []
        for key, old in zip(TASKS, ("X1", "X2", "X3"), strict=True):
            task = bind_spec(entries, old, TRAIN[old], "train", "exploration_dual_support")
            original = public_document(task)
            prior = read_json(root / PARENT / f"preparation/public/{old}.json")
            require(encode(original) == encode(prior), "panel.original_public_identity:" + old)
            if key == "X3C":
                require(
                    original["source"]["table"][0] == ["", "december 27 2008", "december 29 2007"]
                    and "beginning and ending amount" in original["segments"]["p19"]["text"]
                    and "beginning of fiscal year 2007" in original["segments"]["p16"]["text"],
                    "panel.fiscal_year_end_definition_original_evidence",
                )
                task = copy.deepcopy(task)
                task["key"] = key
                task["qa_id"] = CLARIFIED_TASK_ID
                task["entry"]["qa"]["question"] = CLARIFIED_QUESTION
                task["goal_scope"] = {
                    "quantity": "net_change_reconciled_unrecognized_tax_benefits",
                    "period": "fiscal year end 2008-12-27 minus fiscal year end 2007-12-29",
                    "unit": "USD_million",
                    "task_definition_version": "clarified_year_ends.v2",
                }
                task["interpretation"] = (
                    "Balance change between the two explicitly named fiscal "
                    "year ends, not both fiscal years cumulatively."
                )
            public = public_document(task)
            for field in ("source", "segments", "numeric_catalog", "filename", "indexing"):
                require(
                    public[field] == original[field], "panel.unchanged_complete_source:" + field
                )
            self.tasks[key] = task
            self.public[key] = public
            self.private[key] = {
                field: task[field]
                for field in (
                    "key",
                    "qa_id",
                    "unit",
                    "facts",
                    "target",
                    "relations",
                    "sufficient_routes",
                    "goal_scope",
                    "interpretation",
                    "source_bindings",
                    "original_private_spec",
                )
            }
            self.private[key]["reference_exact_value"] = str(
                evaluate(task["target"], task["facts"])
            )
            self.identities.append(
                {
                    "task_key": key,
                    "original_task_id": original["task_id"],
                    "task_id": public["task_id"],
                    "original_question": original["question"],
                    "question": public["question"],
                    "original_public_id": original["id"],
                    "public_id": public["id"],
                    "complete_source_unchanged": True,
                    "question_unchanged": key != "X3C",
                    "old_results_regraded": False,
                }
            )
        require(
            Fraction(self.private["X3C"]["reference_exact_value"]) == Fraction("87.8"),
            "panel.clarified_registered_exact_relation",
        )

    def design(self):
        return record(
            "precall_three_task_source_design",
            source_path=DATA,
            source_sha256=FROZEN_SOURCE_SHA256,
            tasks=self.identities,
            private=self.private,
            N_and_E_use_same_public_documents=True,
            source_pages_not_replaced_or_abridged=True,
            original_dataset_annotation_not_public_or_used_as_answer_completion=True,
            old_development_confirmation_control_tasks_not_selected_or_retuned=True,
            X3_original_OCR_row_label_retained=True,
            X3_fiscal_context_evidence={
                "column_headers": self.public["X3C"]["source"]["table"][0],
                "period_reconciliation": self.public["X3C"]["segments"]["p19"],
                "fiscal_2007_start": self.public["X3C"]["segments"]["p16"],
            },
        )
