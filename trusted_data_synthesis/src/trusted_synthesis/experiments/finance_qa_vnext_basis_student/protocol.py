"""New execution identities; no inherited small-study administrative settings."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ..finance_qa_vnext_basis_scale_preparation import design
from ..finance_qa_vnext_eval_surface import protocol as surface_protocol
from ..finance_qa_vnext_eval_surface.protocol import LEDGER
from ..finance_qa_vnext_readiness_revision.protocol import COLLECTION

OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_basis_student/study_20260912"
SURFACES = surface_protocol.OUTPUT
MATERIALS = COLLECTION + "_materials"
SURFACE_MANIFEST_ID = "manifest:f29dac61b36396baffd60916bf3b2bdca461a849f0e11bb2d519d54127d2c856"
PARENT_COMMIT = "0b14b68c240fb197eff7cb0a9d71faee6dc04567"
PACKAGE = "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_basis_student"
TEST_GLOB = "test_qa_vnext_basis_student_*.py"
BINDING_FIELDS = (
    "study_freeze_id",
    "surface_manifest_id",
    "materials_manifest_id",
    "training_config_id",
    "decoder_config_id",
)
SEEDS = design.SEEDS
ARMS = design.ARMS
POOLS = design.POOLS


def require(condition, code):
    if not condition:
        raise ValueError(code)


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha(value):
    if isinstance(value, Path):
        with value.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def record(kind, **fields):
    body = {"schema_version": "basis_student.v1." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


def checked_record(value, kind):
    require(isinstance(value, dict), "basis_student.record_object")
    body = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    require(value == record(kind, **body), "basis_student.content_identity:" + kind)
    return value


def read_json(path):
    return json.loads(Path(path).read_bytes())


def write_once(path, value):
    """Durable exclusive record. A failed partial write is retained, never replaced."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return value


def now():
    return datetime.now(timezone.utc).isoformat()


def path_within(root, relative):
    root, relative = Path(root).resolve(), Path(relative)
    path = root / relative
    require(
        not relative.is_absolute()
        and ".." not in relative.parts
        and path.resolve().is_relative_to(root)
        and not path.is_symlink(),
        "basis_student.relative_contained_path",
    )
    for ancestor in path.parents:
        if ancestor == root:
            break
        require(not ancestor.is_symlink(), "basis_student.no_symlink_parent")
    return path


def training_config():
    return record(
        "training_configuration",
        model="Qwen2.5-7B-Instruct",
        base_dtype="bfloat16",
        adapter_dtype="float32",
        optimizer_state_dtype="float32",
        lora_rank=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj"],
        bias_training=False,
        embedding_or_lm_head_training=False,
        optimizer="AdamW",
        learning_rate=1e-4,
        betas=[0.9, 0.999],
        eps=1e-8,
        weight_decay=0.0,
        maximum_gradient_norm=1.0,
        scheduler="constant",
        warmup_steps=0,
        seeds=list(SEEDS),
        arms=list(ARMS),
        pools=list(POOLS),
        epochs=10,
        task_count="actual frozen common N=5k, k in 36..40",
        optimizer_updates="10*N/5",
        tasks_per_update=5,
        packages_per_update=64,
        training_packages_per_task_method=8,
        heldout_packages_per_task_method=2,
        microbatch_rows=1,
        token_coefficient="alpha(method|task)/(40*whole_package_target_tokens)",
        extra_global_N_or_token_or_microbatch_divisor=False,
        update="zero_grad once; all 64 original packages; clip once; step once",
        physical_order="frozen task_batches order, update_examples original package and row order",
        paired_initialization_and_schedule=True,
        original_A_B_materials_never_mixed=True,
        maximum_sequence_length=24576,
        truncation=False,
        training_retokenization=False,
        attention_implementation="sdpa",
        sdpa_backend="FLASH_ATTENTION",
        gradient_checkpointing=True,
        use_reentrant=False,
        training_use_cache=False,
        causal_shift=1,
        loss_dtype="float32 sum cross entropy",
        allow_tf32=False,
        deterministic_algorithms=True,
        checkpoint_selection="unique final update only",
        runtime_failure="retain records, fail closed, no automatic seed/hyperparameter rerun",
        per_pool_token_budget="10 times actual frozen train target and original sequence tokens",
        historical_18_or_21_package_administration_reused=False,
    )


def execution_policy():
    return record(
        "execution_policy",
        material_admission="COMPLETE_FIXED_COLLECTION then existing one-time materializer; N>=180",
        existing_collection_restarted=False,
        source_or_prompt_or_qualification_changes=False,
        surface_manifest_id=SURFACE_MANIFEST_ID,
        evaluation_rewrite_reopened=False,
        phase_order=[
            "A 3 arms x 3 seeds train",
            "A 9 final checkpoints x 180 dev",
            "one strict-positive paired mean decision or no move",
            "if move B baseline+selected x 3 seeds train",
            "A and B baseline+selected x 3 seeds x 720 confirm",
        ],
        maximum_training_runs=15,
        maximum_evaluation_sessions=10260,
        B_development_sessions=0,
        evaluation_repeats=1,
        no_move="stop candidate confirmation; no duplicate baseline training",
        primary_confirmation_pool="B",
        auxiliary_confirmation_pool="A",
        decision_tie_priority=list(ARMS),
        checkpoint_NLL_selection=False,
        maximum_parallel_GPU_workers=8,
        one_worker_per_GPU=True,
        minimum_free_GPU_memory_MiB=76000,
        required_GPU_utilization_percent=0,
        resource_shortage="wait without changing model, sequence, seed or batch",
        GPU_allocation="ascending currently free physical index; UUID recorded before spawn",
        worker_environment={"CUBLAS_WORKSPACE_CONFIG": ":4096:8", "OMP_NUM_THREADS": "2"},
        worker_failure=(
            "stop launching; retain in-flight workers and all failure evidence; no retry"
        ),
        bootstrap_seed=20260912,
        bootstrap_replicates=10000,
        bootstrap_scope="paired CIK source sampling conditional on fixed trained checkpoints",
        GPU_or_Student_outputs_before_data_admission=False,
        formal_collection_and_API_budget_ledger=LEDGER,
        API_budget_reset=False,
        new_Teacher_or_rewrite_requests=0,
        new_2048_decoder_limit_is_prospective_not_inherited=True,
        audit_reference_zip_available=False,
        audit_attachment_sha256="5d972ec199c2a2cacdc816a53b2fd8da606df1a843a3375dc7122ecfc22902d4",
    )
