"""Fixed finite observation rules; existing outcomes are input, never relabelled here."""

import json
import subprocess
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    encode,
    sha,
)

BASELINE = "37ebb3b62887b2bbe3470421bb81ea0cf8e36395"
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_open_materialization"
)
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_open_materialization/fixed_t_20260909"
SOURCE = "trusted_data_synthesis/artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909"
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_open_materialization.md"
TESTS = (
    "trusted_data_synthesis/tests/test_qa_vnext_open_materialization.py",
    "trusted_data_synthesis/tests/test_qa_vnext_open_relations.py",
    "trusted_data_synthesis/tests/test_qa_vnext_open_tokens.py",
)
MAX_SEQUENCE_LENGTH = 32768
TASKS = ("N1", "N2", "N3", "N4", "N5", "N6")
AUDIT_PATH = (
    "/home/zhuxinrui/.codex/attachments/dbd7b221-282a-43e2-9555-14ff882163ae/pasted-text.txt"
)
AUDIT_SHA256 = "b0f0617f561d314da78ff2acaf011803320e78c17a2d4e2f04b5d4ae68392525"


def record(kind, **fields):
    body = {"schema_version": "open_trajectory_materialization.v1." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


def require(value, code):
    if not value:
        raise ValueError(code)


def read_json(path):
    return json.loads(Path(path).read_bytes())


def history_guard(root):
    paths = [
        "trusted_data_synthesis",
        ":(exclude)" + PACKAGE,
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_open_materialization",
        ":(exclude)" + DOCUMENT,
        *[":(exclude)" + path for path in TESTS],
    ]
    require(
        not subprocess.check_output(
            ["git", "diff", "--name-only", BASELINE, "--", *paths], cwd=root
        ),
        "history.changed",
    )
    require(
        not subprocess.check_output(["git", "status", "--porcelain", "--", *paths], cwd=root),
        "history.uncommitted",
    )
    return {"baseline": BASELINE, "all_historical_files_unchanged": True}


def rules():
    return record(
        "finite_open_relation_rules",
        source_commit=BASELINE,
        source_population="fixed Flash/high T; A separately retained",
        primary_population="T",
        tasks=list(TASKS),
        original_task_marginal={key: "1/6" for key in TASKS},
        validity="use immutable parent formula_driven_trace_verified; no rescoring",
        three_views=[
            "original_public_sequence",
            "model_public_relations_and_attributed_review",
            "actual_execution_and_support",
        ],
        signature=[
            "population",
            "task_version",
            "source_document_id",
            "goal_scope",
            "active_source_support",
            "answer_connected_source_rational_form",
            "substantive_public_revision_path",
        ],
        source_atoms="original source-document-specific numeric spans; never match numbers alone",
        literal_binding=(
            "explicit AST occurrence ledger plus authentic pre/same-call public role/source/unit "
            "evidence; attribution model_declaration or reviewer_interpretation kept separate "
            "from execution facts"
        ),
        mathematical_scope=(
            "finite explicit AST rational +,-,*,/,sum,avg; rational constants and signed scalar "
            "literals; unsupported or source-domain cancellations are UNDETERMINED"
        ),
        do_not_expand_panel_financial_identities=True,
        preserve_support_differences=[
            "disclosed global total versus regional reconstruction",
            "reported cash-flow metric versus CFO/capex establishment",
            "balance difference versus roll-forward movements",
        ],
        quotient_nuisance=[
            "variable names",
            "whitespace",
            "JSON field order",
            "equivalent algebra over the same sources",
            "unnecessary zero-contribution terms",
            "pure tool granularity after real dependency unfolding",
            "proven equivalent JSON-format recovery",
        ],
        raw_execution_DAG_and_all_events_always_preserved=True,
        substantive_revisions=(
            "preserve evidence-grounded changes of relation, source/period pairing, unit meaning, "
            "target scope or source reading; do not erase because the final expression agrees"
        ),
        unclear_revision_semantics="UNDETERMINED, not assumed cosmetic or a new method",
        pair_scope=(
            "five T within-task pairs if both qualified records map; no A/T pair comparisons"
        ),
        no_required_class_count=True,
        empirical_distribution=(
            "counts divided by all valid source trajectories for that task; unresolved mass "
            "retained, complete distribution null until all map; no valid support => null"
        ),
        positive_target_policy=(
            "original structurally legal successful calculate requests and actual Final "
            "responses from valid sessions; no JSON-error positive targets; all error history "
            "remains in subsequent actual inputs"
        ),
        materialization=(
            "same original HTTP request.messages and same original assistant.raw; do not "
            "reserialize the model JSON or insert offline annotations into targets"
        ),
        bundle_unit="whole valid session, not independent uniform row mixing",
        weighting=(
            "no training weights assigned; task/class/trajectory/package/row indices explicit; "
            "observed pi conditional on validity is not implemented training marginal"
        ),
        tokenizer_length_policy=(
            "inherit existing 32768 policy without changing original 24576 binding field; "
            "no truncation, target-content-only labels"
        ),
        original_trajectories_previously_seen=True,
        rules_frozen_before_new_pair_comparison_results=True,
        relation_claim=(
            "finite observable partial equivalence, not complete hidden-reasoning or universal "
            "behavioral equivalence"
        ),
        provider_calls=0,
        student=False,
        gpu=False,
        training=False,
        N3_regraded=False,
        no_new_question_prospectively_validated=True,
    )
