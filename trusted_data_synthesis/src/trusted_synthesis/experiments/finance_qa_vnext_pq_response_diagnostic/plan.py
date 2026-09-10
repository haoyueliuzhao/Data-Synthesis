"""One bounded follow-up: seven fixed scores and six original-task sessions."""

import hashlib
import subprocess
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import (
    OUTPUT as PARENT,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import (
    SEEDS,
    SOURCE,
    encode,
    evaluation_config,
    read_json,
    require,
    sha,
)

__all__ = ["PARENT", "SOURCE"]

BASELINE = "3cf054dcaf89d147eade9ba09385cd4fcfc371eb"
NAME = "finance_qa_vnext_pq_response_diagnostic"
PACKAGE = "trusted_data_synthesis/src/trusted_synthesis/experiments/" + NAME
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_pq_response_diagnostic/final_models_20260910"
DOCUMENT = "trusted_data_synthesis/docs/" + NAME + ".md"
TESTS = (
    "trusted_data_synthesis/tests/test_qa_vnext_pq_response_diagnostic.py",
    "trusted_data_synthesis/tests/test_qa_vnext_pq_response_boundaries.py",
)
VARIANTS = ("B0", *[f"{arm}_{seed}" for seed in SEEDS for arm in ("P", "Q")])
TRAINED = VARIANTS[1:]
AUDIT_PATH = (
    "/home/zhuxinrui/.codex/attachments/b46d1709-8f08-484f-85fb-84611bd931dd/pasted-text.txt"
)
AUDIT_SHA256 = "f5fc1f705ed3d8b209ec2e2916e4ba6de7587d4e20d34d90e1239b4acb1bae1f"
PREPARATION_KIND = "pq_response_preparation_manifest"
SCORE_KIND = "pq_response_score_manifest"
GENERATION_KIND = "pq_response_generation_manifest"
EXECUTION_KIND = "pq_response_execution_manifest"
ASSESSMENT_KIND = "pq_response_assessment_manifest"
CLOSEOUT_KIND = "pq_response_closeout_manifest"


def record(kind, **fields):
    body = {"schema_version": "fixed_student_response.v1." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


def configuration():
    return record(
        "diagnostic_configuration",
        parent_release=BASELINE,
        score_variants=list(VARIANTS),
        generation_variants=list(TRAINED),
        score_rows_per_model=36,
        score_rows_total=252,
        score_sequence_positions=1628221,
        score_target_positions=33551,
        row_order=list(range(36)),
        sequence_positions_per_model=232603,
        target_positions_per_model=4793,
        generation_sessions=6,
        generation_task="L1",
        maximum_generation_responses=192,
        parent_decoder_configuration_id=evaluation_config()["id"],
        inherited_decoder_administrative_counts_are_not_this_study_denominators=True,
        decoder_unchanged=True,
        eval_mode=True,
        dropout_enabled=False,
        autograd_enabled=False,
        new_training_updates=0,
        optimizer_constructions=0,
        teacher_calls=0,
        adapter_saves=0,
        original_training_arrays_retokenized=False,
        logits="stored target positions minus one, exactly one causal shift",
        target_nll="one float32 cross_entropy(reduction=none) per original row",
        aggregation="math.fsum of serialized FP32 target NLLs in Python float64",
        package_loss="whole-package target NLL sum / original package target count",
        common_objectives=["P", "Q"],
        C="ell(T_L1_03) - (ell(T_L1_01) + ell(T_L1_04))/2",
        delta_C="C(Q_s) - C(P_s); negative means fixed-text relative fitting only",
        split_kinds=["calculate", "Final"],
        split_normalization=(
            "report per-kind package means AND original-package-normalized kind "
            "contributions; only the contributions add to original whole loss"
        ),
        identity_absolute_tolerance=1e-10,
        probability_estimate_from_NLL=False,
        phases="all seven scoring processes finish, then six fresh generation processes",
        outcome_adaptive_order_or_repeats=False,
        maximum_parallel_workers=4,
        eligible_gpu="free >=70000 MiB, NVIDIA A100-SXM4-80GB, index 0..7",
        failure_policy=(
            "preserve partial files; stop new jobs, drain active jobs; no implicit retry"
        ),
        new_L1_sessions_are_training_task_diagnostics_not_generalization=True,
        old_84_session_scores_and_denominator_unchanged=True,
        full_parameter_bytes_hashed_before_and_after_each_phase=True,
        no_Q_favored_route_required_for_completion=True,
    )


def history_guard(root):
    paths = [
        "trusted_data_synthesis",
        ":(exclude)" + PACKAGE,
        ":(exclude)" + OUTPUT,
        ":(exclude)" + DOCUMENT,
        *[":(exclude)" + p for p in TESTS],
    ]
    for command in (
        ["git", "diff", "--name-only", BASELINE, "--", *paths],
        ["git", "status", "--porcelain", "--", *paths],
    ):
        require(not subprocess.check_output(command, cwd=root), "diagnostic.history_changed")
    return {"baseline": BASELINE, "all_prior_project_files_unchanged": True}


def reference(root, relative):
    path = Path(root) / relative
    require(path.is_file() and not path.is_symlink(), "diagnostic.regular_reference")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(relative), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def check_reference(root, expected):
    require(reference(root, expected["path"]) == expected, "diagnostic.reference_changed")


def worker_inputs(root, variant):
    """Only neutral shared metadata, never scoring results or review targets."""
    require(variant in VARIANTS, "diagnostic.registered_variant")
    prep = Path(root) / OUTPUT / "preparation"
    config = read_json(prep / "configuration.json")
    require(config == configuration(), "diagnostic.configuration_changed")
    model = read_json(prep / "models.json")[variant]
    binding = read_json(prep / "checkpoint_binding.json")
    require(model["checkpoint_binding_id"] == binding["id"], "diagnostic.model_binding")
    return config, model, binding
