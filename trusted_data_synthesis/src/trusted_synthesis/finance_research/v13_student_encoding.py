"""Lossless V13 SFT encoding from the predeclared field-level authority.

This material is not an API or feedback TokenReceipt. Qualification, mapping and
projection are separate inputs; encoding neither rejudges nor filters a package.
"""

from .contracts import digest
from .v6_encoding import CONTEXT_LIMIT
from .v6_task import public_trajectory_view
from .v10_student_encoding import _encode_original_spans_for_student

ENCODING_POLICY = "v13_fixed_authority_original_spans.v1"
MANIFEST_SCHEMA = "v13_frozen_package_supervision.v1"


def validate_manifest(episode, manifest):
    if (
        manifest.get("schema") != MANIFEST_SCHEMA
        or manifest.get("id") != digest({k: v for k, v in manifest.items() if k != "id"})
        or manifest.get("episode_sha256") != digest(episode)
        or manifest.get("task_id") != episode.task_id
        or manifest.get("projection_authority") not in {"V12_A_original", "V13_completion_only"}
        or not isinstance(manifest.get("authority_record"), dict)
        or not manifest.get("protocol_id")
        or not isinstance(manifest.get("positive_content_spans"), list)
        or not isinstance(manifest.get("positive_action_ids"), list)
    ):
        raise ValueError("V13 immutable supervision authority/episode binding required")
    view = public_trajectory_view(episode, slot_id=manifest["slot_id"])
    if manifest.get("view_id") != view["view_id"]:
        raise ValueError("V13 original public view changed")


def encode_for_student(episode, manifest, tokenizer, *, context_limit=CONTEXT_LIMIT):
    return _encode_original_spans_for_student(
        episode,
        manifest,
        tokenizer,
        context_limit=context_limit,
        validate_manifest=validate_manifest,
        schema="v13_student_encoding.v1",
        encoding_policy=ENCODING_POLICY,
        encoding_id_prefix="v13_student_encoding:",
    )


def validate_encoding(encoding, episode, manifest, tokenizer):
    """Replay deterministic encoding, including complete prompt/response/EOS bytes."""
    if encoding != encode_for_student(episode, manifest, tokenizer):
        raise ValueError("V13 encoding differs from original history and frozen projection")
    return encoding


encode_process_review_for_student = encode_for_student
