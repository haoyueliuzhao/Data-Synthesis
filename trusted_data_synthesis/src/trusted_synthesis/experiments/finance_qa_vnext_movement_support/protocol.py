"""Separate diagnosis/revision lineage; original experiments remain unchanged."""

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

BASE_COMMIT = "30284a2f139b7981bc96413646459c51b76e57d5"
BRANCH = "codex/movement-support-20260913"
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_movement_support"
)
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_movement_support/diagnosis_20260913_final"
COLLECTION = "trusted_data_synthesis/artifacts/qa_vnext_readiness_revision/fixed_AB_20260912"
COLLECTION_MANIFEST = "manifest:97e3df4ec4728be4169f80abb3b1f1c7d535fefb4b115d9015e507034311dbd8"
MATERIALS = COLLECTION + "_materials"
MATERIAL_MANIFEST = "manifest:1f3a4056e2caefb89c7b4b34a392321a788a48e374f433b1cf406ea76ffbceba"
AUDIT_SHA256 = "9ab9d290a74db96925c1da57fcb41c71a882c304d6f48bb6a0590f7a6fc8c3e8"


def require(value, code):
    if not value:
        raise ValueError(code)


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(value):
    if isinstance(value, Path):
        with value.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def record(kind, **fields):
    body = {"schema_version": "movement_support.v1." + kind, **copy.deepcopy(fields)}
    return {**body, "id": kind + ":" + sha(encode(body))}


def checked_record(value, kind):
    require(isinstance(value, dict), "movement.record_object")
    fields = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    require(value == record(kind, **fields), "movement.content_identity:" + kind)
    return value


def now():
    return datetime.now(timezone.utc).isoformat()


def write_once(path, value):
    path = Path(path)
    require(
        ".." not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
        "movement.safe_exclusive_output",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    return value


def policy():
    return record(
        "phase_zero_policy",
        branch=BRANCH,
        base_commit=BASE_COMMIT,
        audit_sha256=AUDIT_SHA256,
        registered_sessions=24640,
        original_archive_and_rows_unchanged=True,
        stage_order=[
            "registered_generation",
            "executed_support",
            "financial_and_method_proof",
            "old_fine_mapping",
            "authentic_representation_eligibility",
            "token_encoding",
            "common_AB_selection",
        ],
        final_zero_does_not_prove_generation_probability_zero=True,
        requested_basis_is_not_actual_method=True,
        structural_signal_is_not_financial_qualification=True,
        old_fine_mapper_is_not_new_anchored_state_catalog=True,
        no_partial_population_or_success_ranking=True,
        original_32_per_guidance_and_8_plus_2_rules_unchanged=True,
        new_Teacher_source_or_rewrite_requests=0,
        Student_or_GPU_calls=0,
        Student_development_or_confirmation_outputs_read=False,
        no_automatic_topup_or_training=True,
        corrected_assessments_if_proven=(
            "new isolated derivative only; never overwrite original evidence"
        ),
    )
