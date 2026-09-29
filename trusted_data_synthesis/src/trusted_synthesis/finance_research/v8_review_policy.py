"""Frozen prospective single-target review policy, independent of execution code.

Register this policy before any new-batch generation. Its definition does not
read generated trajectories, native scores, Base/dev results, or API responses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from .contracts import digest

POLICY_VERSION = "v8_single_target_policy.v1"
REVIEW_WIRE = "v8_single_target_review.v1"
ALIGNMENT_WIRE = "v8_alignment_review.v1"
NONASSERTIVE_POLICY = "v8_model_labelled_empty_or_procedural_context.v1"
ACTION_FIELDS = {
    "list_sources": [],
    "read_source": ["source_id"],
    "run_program": ["program"],
    "submit_program": ["program"],
}
EMPTY_OPTIONAL_PATTERN = r"(?:Q|U)\s*:\s*(?:None|N/A)\s*[.;]?"
PROCEDURAL_PATTERN = (
    r"(?:(?:R|U|Q)\s*:\s*)?"
    r"(?:(?:I(?:'ll| will)|We(?:'ll| will)|Let(?:'s| us))\s+)?"
    r"(?:now\s+)?(?:start\s+by\s+)?"
    r"(?:read|reading|inspect|inspecting|open|opening|list|listing|submit|submitting|"
    r"return|returning|execute|executing|run|running|calculate|calculating|compute|computing)\s+"
    r"(?:the\s+|a\s+)?(?:(?:original|public|relevant|predicted)\s+)?"
    r"(?:source|sources|table|tables|text|program|result|calculation)\s*[.;]?"
)


def nonassertive_fragment_kind(text):
    """Validate a model-selected zero-target class, never select that class for it."""
    if not isinstance(text, str):
        return None
    value = text.strip()
    if re.fullmatch(EMPTY_OPTIONAL_PATTERN, value, flags=re.IGNORECASE):
        return "empty_optional_field"
    if re.fullmatch(PROCEDURAL_PATTERN, value, flags=re.IGNORECASE):
        return "ordinary_procedural_intent"
    return None


def policy_definition():
    body = dict(
        schema=POLICY_VERSION,
        review_wire=REVIEW_WIRE,
        alignment_wire=ALIGNMENT_WIRE,
        model="deepseek-flash",
        model_fallback=False,
        thinking="disabled",
        single_authority="one required keyed targets table; every original target exactly once",
        targets="all public R/U/content fragments and each original action argument string",
        granularity=dict(
            original_coordinates="Unicode codepoint [start,end), immutable original strings",
            content_boundaries=(
                "sentence whitespace, newline and semicolon; approximately200 characters"
            ),
            every_original_character_retained=True,
            original_history_not_rewritten=True,
            action_arguments="atomic only under the frozen exact tool-field contract",
            action_fields={name: list(fields) for name, fields in ACTION_FIELDS.items()},
            unregistered_extra_reason_or_rationale_fields="never approved through an atomic action",
        ),
        target_record_fields=["label", "proposition_ids", "evidence"],
        labels=["approved", "retracted", "unknown", "nonassertive_context"],
        model_obligations=[
            "critical propositions and their evidence",
            "withdrawals and hypotheses",
            "action grounding",
            "consequential updates",
            "semantic graph",
            "target judgment",
        ],
        mechanical_projection=dict(
            action_judgments_and_supervision_mask=(
                "derived from the SAME target judgment, no second model copy"
            ),
            tool_success_automatically_approves=False,
            action_approval_approves_other_assistant_text=False,
            model_label_or_evidence_repair=False,
            missing_targets_filled=False,
        ),
        nonassertive=dict(
            policy=NONASSERTIVE_POLICY,
            model_must_choose_label=True,
            zero_target_loss=True,
            proposition_ids_must_be_empty=True,
            public_content_only=True,
            empty_optional_pattern=EMPTY_OPTIONAL_PATTERN,
            procedural_intent_pattern=PROCEDURAL_PATTERN,
            full_fragment_match=True,
            excluded=(
                "financial facts/amounts/periods/formulas/source judgments, "
                "verified/correctness claims, mixed ambiguity"
            ),
            unrecognized_or_mixed="unknown, not automatically approved or shortened",
        ),
        unchanged_semantics=dict(
            common_material="Q_native true AND both effective finite V_trace valid",
            meaningful_chi=(
                "actual linked action/observation and evidenced consequential "
                "later accepted judgment"
            ),
            ordinary_submission_or_tool_count_not_chi=True,
            no_forced_errors_or_verification=True,
            all_jointly_qualified_packages_mapped_together=True,
            no_mask_intersection_or_hard_case_deletion=True,
            native_correctness_not_trace_proof=True,
        ),
        review_context=dict(
            one_original_slot_plus_shared_sources=True,
            offline_reference_only=True,
            other_slot_reviews_visible=False,
            other_reviewer_visible=False,
            alignment_only_own_eight_sealed_judgments=True,
            same_model_reviews_statistically_independent=False,
        ),
        technical_validation=dict(
            tasks=6,
            original_slots_per_task=8,
            reviewers=2,
            slot_calls=96,
            alignment_calls=12,
            maximum_new_calls=108,
            original_preselected_six=True,
            fresh_calls_only=True,
            twelve_call_pilot=False,
            percentage_perfection_gate=False,
            at_least_one_real_complete_native_trace_pair_mapping_encoding_path=True,
            negative_controls_must_not_false_pass=True,
            malformed_returns=(
                "retain unknown and continue fixed scope unless billing/resource safety stops"
            ),
            no_real_complete_path="not production ready",
            automatic_R8_R9=False,
            automatic_production_review_or_training=False,
        ),
        production_review_resource_policy=dict(
            after_all8000_generation_sealed=True,
            native_all_slots_before_semantic_review=True,
            any_task_with_zero_native_support=(
                "stop original1000 training and expensive full production review"
            ),
            every_native_correct_candidate_reviewed_without_selection=True,
            native_false_or_unknown_trace_status="not_assessed_native_ineligible",
            all8000_originals_retained=True,
        ),
        budget=dict(
            shared_review_partition_requests=18108,
            technical_calls=108,
            production_upper_bound=18000,
            technical_namespace="v8review:",
            production_namespace="v8prod:",
            original800CNY_and_UNKNOWN_hold_unchanged=True,
        ),
        freeze=dict(
            before_new_generation=True,
            new_generation_results_used_for_policy_choice=False,
            Base_development_results_used=False,
            old_R6_false_unchanged=True,
        ),
        policy_is_new_granularity_and_supervision_rule_not_just_field_rename=True,
    )
    return body | {"id": digest(body)}


def register_policy(output):
    source = Path(__file__).resolve()
    root = source.parents[4]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    committed = subprocess.check_output(
        ["git", "show", f"{head}:{source.relative_to(root)}"], cwd=root
    )
    if committed != source.read_bytes():
        raise ValueError("commit exact policy source before registration")
    body = dict(
        schema="v8_review_policy_registration.v1",
        at=datetime.now(timezone.utc).isoformat(),
        definition=policy_definition(),
        source_commit=head,
        policy_source_sha256=hashlib.sha256(committed).hexdigest(),
        policy_source_path=str(source.relative_to(root)),
        generated_results_read=False,
        model_calls=0,
        validation_execution_not_claimed=True,
    )
    record = body | {"id": digest(body)}
    write_immutable_artifact_directory(
        output,
        {
            "record.json": json.dumps(
                record, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
            ).encode()
        },
    )
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("show", "register"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.action == "show":
        print(json.dumps(policy_definition(), ensure_ascii=False))
    else:
        if args.output is None:
            parser.error("register requires --output")
        result = register_policy(args.output)
        print(json.dumps(dict(registration_id=result["id"], policy_id=result["definition"]["id"])))


if __name__ == "__main__":
    main()
