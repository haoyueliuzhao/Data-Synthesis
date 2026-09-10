"""Pre-Student data, loss, checkpoint, training and evaluation commitments."""

import json
import subprocess
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    encode,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import SYSTEMS

BASELINE = "f7af54f4bf2633036c2aca96d198212de512c1bd"
PACKAGE = "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_pq_student"
SOURCE = (
    "trusted_data_synthesis/artifacts/qa_vnext_open_support_exploration/"
    "three_structures_4rep_20260909"
)
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_pq_student/pq_3seed_20260910"
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_pq_student.md"
TESTS = (
    "trusted_data_synthesis/tests/test_qa_vnext_pq_weights_loss.py",
    "trusted_data_synthesis/tests/test_qa_vnext_pq_student.py",
    "trusted_data_synthesis/tests/test_qa_vnext_pq_evaluation.py",
    "trusted_data_synthesis/tests/test_qa_vnext_pq_stage.py",
)
MODEL_DIRECTORY = Path(
    "/data1/zhuxinrui/models/Qwen2.5-7B-Instruct-a09a35458c702b33eeacc393d103063234e8bc28"
)
MODEL_REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"
TASKS = ("G1", "G2", "F1", "F2", "L1", "L2")
SYSTEM = SYSTEMS["T"]
SEEDS = (11, 29, 47)
EPOCHS = 10
ALLOWED_GPUS = tuple(range(8))
MAX_PARALLEL_WORKERS = 2
AUDIT_PATH = (
    "/home/zhuxinrui/.codex/attachments/eb1c192d-e14c-43b9-907f-f2fd75273757/pasted-text.txt"
)
AUDIT_SHA256 = "30758445df231f9f9c26c15a0573cfd33659873a6295ec9ebf7a6d5e10898d87"


def record(kind, **fields):
    body = {"schema_version": "fixed_support_pq_student.v1." + kind, **fields}
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
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_pq_student",
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
    return {"baseline": BASELINE, "historical_files_unchanged": True}


def training_config():
    return record(
        "fixed_training_configuration",
        model="Qwen2.5-7B-Instruct",
        local_directory=str(MODEL_DIRECTORY),
        revision=MODEL_REVISION,
        base_dtype="bfloat16",
        adapter_dtype="float32",
        optimizer_state_dtype="float32",
        method="explicit low-rank additive adapters; original base weights frozen",
        lora_rank=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj"],
        bias_training=False,
        embedding_or_lm_head_training=False,
        adapter_initialization="A Kaiming-uniform(a=sqrt(5)); B zeros; paired seed identical",
        optimizer="AdamW",
        learning_rate=0.0001,
        betas=[0.9, 0.999],
        eps=1e-8,
        weight_decay=0.0,
        warmup_steps=0,
        scheduler="constant",
        maximum_gradient_norm=1.0,
        seeds=list(SEEDS),
        paired_seeds=True,
        conditions=["P", "Q"],
        train_runs=6,
        epochs=EPOCHS,
        optimizer_updates=EPOCHS,
        rows_per_epoch=36,
        packages_per_epoch=18,
        accumulation=(
            "one full weighted 36-row pass at fixed parameters before each optimizer update"
        ),
        microbatch_rows=1,
        row_order="seeded permutation of all 36 original row IDs per epoch, shared P/Q",
        supervised_tokens_per_epoch=4793,
        sequence_tokens_per_epoch=232603,
        supervised_tokens_per_run=47930,
        sequence_tokens_per_run=2326030,
        package_loss="mean over all positive target tokens in the entire original package",
        token_coefficient="exact package weight / total package target-token count",
        objective="sum of per-token NLL times fixed token coefficients; no subsequent mean",
        row_uniform_or_global_token_mean=False,
        resampling=False,
        truncation=False,
        attention_implementation="sdpa",
        sdpa_backend="FLASH_ATTENTION",
        gradient_checkpointing=True,
        use_reentrant=False,
        training_use_cache=False,
        logits="only causal predecessor positions of stored supervised labels",
        loss_dtype="float32 cross entropy, sum reduction",
        allow_tf32=False,
        deterministic_algorithms=True,
        cudnn_deterministic=True,
        maximum_sequence_length=32768,
        checkpoint_selection="final update 10 only; no validation-based selection",
        no_teacher_sampling=True,
        no_retokenization_of_training_rows=True,
        Q_is_hand_specified_diagnostic_not_optimized_contribution_or_novelty=True,
        no_hyperparameter_search_or_post_result_budget_change=True,
    )


def evaluation_config():
    return record(
        "fixed_evaluation_configuration",
        tasks=12,
        primary_transfer_tasks=6,
        regression_tasks=6,
        variants=["B0", *[f"{arm}_{seed}" for seed in SEEDS for arm in ("P", "Q")]],
        total_sessions=84,
        repeats_per_variant_task=1,
        source_isolation="12 distinct evaluation pages, disjoint from all six training pages",
        questions_original_and_source_complete=True,
        model_system=SYSTEM,
        system_sha256=sha(SYSTEM.encode()),
        transport="local causal-LM generation, not HTTP and not teacher response replay",
        decoder="greedy",
        do_sample=False,
        num_beams=1,
        repetition_penalty=1.0,
        attention_implementation="sdpa",
        sdpa_backend="FLASH_ATTENTION",
        max_new_tokens_per_response=1024,
        maximum_responses=32,
        maximum_tool_calls=32,
        maximum_sequence_length=32768,
        prompt_plus_generation_reservation_must_fit=True,
        eos_token_ids=[151645, 151643],
        pad_token_id=151643,
        output_projection=(
            "remove at most the actual final EOS token; preserve other generated "
            "special-token spellings and all public text"
        ),
        no_json_grammar_constraint_or_response_repair=True,
        tool_semantics=(
            "same unchanged calculate/read_source/notebook functions and public feedback"
        ),
        first_Final_always_terminal=True,
        no_online_gold_or_answer_feedback=True,
        no_retry_after_context_length_or_empty_generation=True,
        numeric_policy=(
            "publication_tolerance.v2; predeclared new-task unit aliases; original "
            "Final-only priority and secondary-display checks"
        ),
        primary_outcomes=["task answer status", "complete verifiable trajectory"],
        mechanism_route_choice_is_not_itself_utility=True,
        baseline_once_before_training=True,
        same_panel_after_every_final_P_Q_checkpoint=True,
        no_eval_set_replacement_after_baseline_or_training=True,
        no_claim_of_pretraining_unseen_or_random_population_panel=True,
    )
