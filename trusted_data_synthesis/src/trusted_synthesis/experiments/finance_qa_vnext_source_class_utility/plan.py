"""New source-class study, never an amendment to a closed Teacher experiment."""

import json
import subprocess
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import (
    evaluation_config as parent_evaluation,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import (
    training_config as parent_training,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import (
    SYSTEMS_NEW,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import (
    public_quantity_context as public_quantity_context,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    encode,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import SYSTEMS

BASELINE = "e18974bce8ffcd036b4c89724e6046f7d71cec06"
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_source_class_utility"
)
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_source_class_utility/N_X3C_3arm3seed_20260911"
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_source_class_utility.md"
NE_SOURCE = (
    "trusted_data_synthesis/artifacts/qa_vnext_soft_detail_exploration/three_tasks_NE_8rep_20260910"
)
PANEL_SOURCE = (
    "trusted_data_synthesis/artifacts/qa_vnext_bidirectional_utility/"
    "three_tasks_24rep_flash_rerun_20260910"
)
CONTROL_SOURCE = (
    "trusted_data_synthesis/artifacts/qa_vnext_pq_student/pq_3seed_20260910/preparation"
)
CONTROL_LABELS = tuple(
    f"T_{task}_{rep:02d}"
    for task, reps in (("G1", (1, 2, 3)), ("G2", (1, 2, 3)), ("F1", (2, 3, 4)))
    for rep in reps
)
TESTS = (
    "trusted_data_synthesis/tests/test_qa_vnext_source_class_quantity.py",
    "trusted_data_synthesis/tests/test_qa_vnext_source_class_workflow.py",
)
AUDIT_PATH = (
    "/home/zhuxinrui/.codex/attachments/d91b0920-f7f9-4978-b406-ac8e972b7e8d/pasted-text.txt"
)
AUDIT_SHA256 = "750484601e1ce70aebc0aa9ea5c3ca21a6cbe3ab98f88f3a73afb9b4459499c0"
CONDITIONS = ("pi0", "plus_A", "minus_D")
SEEDS = (11, 29, 47)
TASKS = ("G1", "G2", "F1", "X1", "X2", "X3C")
GROUPS = ("dual_sufficient", "detail_related", "other_finance")
SYSTEM = SYSTEMS["T"]
TRAIN_SYSTEM = SYSTEMS_NEW["N"]
MAX_PARALLEL_WORKERS = 6
QUANTITY_VERSION = "public_quantity_interpretation.v1.1"
X3_KEYS = {
    "D": "83681c6bcf9405e737f392685adab504c282e860b432643583b8f953390842c3",
    "A": "90fd4e8cd99aaaedece044b94dd0fc4f7ccba122835eabc0d90315be9250ba6b",
}


def record(kind, **fields):
    body = {"schema_version": "source_class_utility.v1." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


def require(value, code):
    if not value:
        raise ValueError(code)


def read_json(path):
    return json.loads(Path(path).read_bytes())


def reference(root, relative):
    path = Path(root) / relative
    require(path.is_file() and not path.is_symlink(), "reference.regular_file")
    raw = path.read_bytes()
    return {"path": str(relative), "bytes": len(raw), "sha256": sha(raw)}


def read_bound(root, ref):
    require(reference(root, ref["path"]) == ref, "reference.immutable_bytes")
    return read_json(Path(root) / ref["path"])


def history_guard(root):
    paths = [
        "trusted_data_synthesis",
        ":(exclude)" + PACKAGE,
        ":(exclude)" + OUTPUT,
        ":(exclude)" + DOCUMENT,
        *[":(exclude)" + path for path in TESTS],
    ]
    require(
        not subprocess.check_output(
            ["git", "diff", "--name-only", BASELINE, "--", *paths], cwd=root
        ),
        "history.previous_experiments_unchanged",
    )
    require(
        not subprocess.check_output(["git", "status", "--porcelain", "--", *paths], cwd=root),
        "history.no_uncommitted_previous_changes",
    )
    return {"baseline": BASELINE, "historical_files_unchanged": True}


def training_config(totals):
    config = {
        k: v
        for k, v in parent_training().items()
        if k
        not in {
            "id",
            "schema_version",
            "Q_is_hand_specified_diagnostic_not_optimized_contribution_or_novelty",
        }
    }
    config.update(
        conditions=list(CONDITIONS),
        train_runs=9,
        packages_per_epoch=21,
        rows_per_epoch=totals["rows"],
        supervised_tokens_per_epoch=totals["target_tokens_per_pass"],
        sequence_tokens_per_epoch=totals["sequence_tokens_per_pass"],
        supervised_tokens_per_run=10 * totals["target_tokens_per_pass"],
        sequence_tokens_per_run=10 * totals["sequence_tokens_per_pass"],
        accumulation="one complete weighted pass over every row of all 21 original packages",
        row_order="same seed, same permutation of all physical rows per epoch in all three arms",
        new_selected_packages_tokenized_once=12,
        old_control_packages_retokenized=0,
        no_retokenization_of_training_rows=True,
        same_physical_data_only_loss_coefficients_differ=True,
        source_class_mass_not_source_ID_only_intervention=True,
    )
    return record("training_configuration", **config)


def evaluation_config():
    config = {
        k: v
        for k, v in parent_evaluation().items()
        if k
        not in {
            "id",
            "schema_version",
            "primary_transfer_tasks",
            "regression_tasks",
            "variants",
            "baseline_once_before_training",
            "same_panel_after_every_final_P_Q_checkpoint",
        }
    }
    config.update(
        tasks=36,
        development_tasks=12,
        confirmation_tasks=24,
        total_sessions=252,
        development_sessions=108,
        maximum_confirmation_sessions=144,
        source_isolation="existing company-disjoint train/dev/confirm; no panel reselection",
        decoder="greedy",
        no_B0=True,
        no_old_L1=True,
        no_same_task_diagnostics=True,
        numeric_policy=QUANTITY_VERSION + ".task_specific_student_adapter",
        panel_groups=list(GROUPS),
        development_group_sizes=[4, 4, 4],
        confirmation_group_sizes=[8, 8, 8],
        main_utility=(
            "one third of each group mean complete-trace PASS; unknowns stay in denominator"
        ),
        tie_priority=list(CONDITIONS),
        positive_mean_paired_gain_required=True,
        no_move_action="stop after development, no identical-baseline confirmation",
        confirmation_only_after_selection_identity_sealed=True,
        stop_on_training_implementation_failure_without_hidden_rerun=True,
    )
    return record("evaluation_configuration", **config)


def package_mass(arm, task, route):
    require(arm in CONDITIONS and task in TASKS, "weights.registered_arm_task")
    if task != "X3C":
        return Fraction(1, 18)
    require(route in {"D", "A"}, "weights.fixed_D_A_not_R")
    a_mass = {"pi0": Fraction(1, 2), "plus_A": Fraction(2, 3), "minus_D": Fraction(1, 3)}[arm]
    return (a_mass if route == "A" else 1 - a_mass) / 18


def utility(group_counts):
    require(set(group_counts) == set(GROUPS), "utility.exact_three_groups")
    require(
        all(
            type(p) is int and type(n) is int and 0 <= p <= n and n > 0
            for p, n in group_counts.values()
        ),
        "utility.actual_registered_denominators",
    )
    return sum((Fraction(p, n) / 3 for p, n in group_counts.values()), Fraction())


def select_candidate(utilities):
    require(set(utilities) == set(CONDITIONS), "selection.all_three_arms")
    require(all(set(rows) == set(SEEDS) for rows in utilities.values()), "selection.paired_seeds")
    gains = {
        arm: sum(
            (Fraction(utilities[arm][s]) - Fraction(utilities["pi0"][s]) for s in SEEDS), Fraction()
        )
        / 3
        for arm in CONDITIONS
    }
    selected = "pi0"
    for arm in CONDITIONS[1:]:
        if gains[arm] > gains[selected]:
            selected = arm
    direction = sum(
        (Fraction(utilities["plus_A"][s]) - Fraction(utilities["minus_D"][s]) for s in SEEDS),
        Fraction(),
    )
    return record(
        "development_selection",
        selected_condition=selected,
        paired_mean_gain={arm: str(gain) for arm, gain in gains.items()},
        finite_delta_directional_utility=str(direction),
        delta="1/6",
        tie_priority=list(CONDITIONS),
        positive_gain_required=True,
        confirmation_required=selected != "pi0",
        no_runner_up_after_confirmation=True,
        theoretical_Contribution_established=False,
    )
