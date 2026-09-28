"""Prospective update-coherence instructions; unchanged finite qualification rules.

This pure helper neither calls a model nor launches a cohort. It adds no source
answers, never rewrites a reviewer label, and does not make a failed old review a
new success. The only motivation is the four pre-Base R5 semantic failures; no
development evaluation results are consumed here.
"""

from __future__ import annotations

from .contracts import digest

POLICY = "existing_substantive_update_cross_field_coherence.v1"

COHERENCE_APPENDIX = """
PROSPECTIVE UPDATE-COHERENCE CLARIFICATION (NO NEW QUALIFICATION CRITERION):
Judge whether each recorded verification/revision is genuinely consequential from
the original public trajectory. Do not manufacture a verification, error, change,
claim, citation or observation to satisfy this schema. A routine calculation or
successful submission is not automatically a substantive verification.

For substantive=true ALL existing conditions must agree in the same update:
1. kind is verification or semantic_revision, and decision_change is not none.
2. prior_proposition and posterior_proposition name existing reviewed propositions.
   The posterior is critical=true and accepted=true; its supported acceptance is
   evidenced by actual later model text, not an imagined consequence.
3. action_doc_id names the actual action, observation_doc_id its actual linked
   observation. evidence includes original fragments for BOTH named action and
   observation. Public sources alone, or an observation alone, do not satisfy this.
4. evidence and nonredundancy_evidence are nonempty and actually establish why
   information changed the subsequent accepted judgment, evidence choice, program
   or submission. A label such as submission_change is not itself evidence.
5. The posterior text follows that action/observation in the original trajectory.
   An accepted verification/revision graph node must bind that same posterior;
   its relation to the accepted answer path must already be supported.

In particular, substantive=true with decision_change=none, a noncritical or
unaccepted posterior, or missing actual action/observation citations is internally
inconsistent. Do not "fix" such a record by changing substantive to false just to
pass validation. Assess the actual evidence. You MAY truthfully report a routine,
redundant or formatting-only step as nonsubstantive when the original record
supports that judgment. You MAY and SHOULD retain substantive=true for a genuine,
fully evidenced consequential verification/revision. Neither label is preferred.
If key evidence is unresolved, retain the appropriate unknown judgment rather
than inventing a consequence or a supporting proposition. A false substantive
flag does not excuse an unresolved critical claim or an unbound accepted graph.

The host only checks these same finite constraints and derives chi from eligible
updates. It never chooses a substantive label for you, supplies missing evidence,
changes unknown to supported, removes an inconvenient update, or forces chi=0/1.
The two reviewers remain isolated; neither sees the other's output.
"""


def coherence_constraints():
    """Registration metadata; not an oracle or an additional paid-work authority."""
    return dict(
        policy=POLICY,
        semantic_baseline="unchanged original semantic_review._validate_slot",
        clarification_only=True,
        derived_from="four pre-Base R5 cross-field semantic failures only",
        uses_Base_or_development_results=False,
        required_if_substantive=[
            "verification_or_semantic_revision",
            "decision_change_not_none",
            "existing_prior_and_posterior",
            "critical_accepted_posterior",
            "actual_linked_action_observation",
            "action_and_observation_cited",
            "nonempty_evidence_and_nonredundancy",
            "later_original_posterior_text",
            "matching_accepted_update_node_and_answer_path",
        ],
        host_semantic_label_changes=False,
        host_evidence_completion=False,
        nonsubstantive_is_not_automatically_valid=True,
        genuine_substantive_updates_remain_allowed=True,
        initial_engineering_scope=dict(
            tasks=6,
            slot_index=0,
            isolated_reviewers=[0, 1],
            maximum_calls=12,
            selection="same preselected capacity tasks, not by result",
            old_success_reuse=False,
        ),
        automatic_paid_calls=False,
        automatic_expansion=False,
        automatic_alignment_or_training=False,
    )


def update_coherence_diagnostics(parsed_slot, document_index):
    """Read-only structural diagnosis of reviewer-authored updates, never a repair.

    This is explanatory evidence, not an alternate admissibility/chi evaluator.
    Original semantic_review remains the only semantic validation authority.
    """
    propositions = {p["proposition_id"]: p for p in parsed_slot["propositions"]}
    nodes = parsed_slot["semantic_graph"]["nodes"]
    rows = []
    for index, update in enumerate(parsed_slot["updates"]):
        violations = []
        posterior = propositions.get(update["posterior_proposition"])
        action = document_index.get(update["action_doc_id"])
        observation = document_index.get(update["observation_doc_id"])
        if update["prior_proposition"] not in propositions or posterior is None:
            violations.append("missing_original_prior_or_posterior_proposition")
        if (
            action is None
            or observation is None
            or observation.get("observes_action_doc_id") != update["action_doc_id"]
        ):
            violations.append("missing_actual_action_observation_link")
        if update["substantive"]:
            if update["kind"] not in {"verification", "semantic_revision"}:
                violations.append("substantive_kind_is_format_or_repetition")
            if update["decision_change"] == "none":
                violations.append("substantive_true_but_decision_change_none")
            if not update["evidence"] or not update["nonredundancy_evidence"]:
                violations.append("missing_evidence_or_nonredundancy_evidence")
            if not posterior or not posterior["critical"]:
                violations.append("substantive_posterior_not_critical")
            if not posterior or not posterior["accepted"]:
                violations.append("substantive_posterior_not_accepted")
            cited = {e["doc_id"] for e in update["evidence"]}
            if not {update["action_doc_id"], update["observation_doc_id"]} <= cited:
                violations.append("substantive_missing_named_action_or_observation_citation")
            if posterior and action is not None:
                following = any(
                    type(document_index.get(e["doc_id"], {}).get("turn_index")) is int
                    and type(action.get("turn_index")) is int
                    and document_index[e["doc_id"]]["turn_index"] > action["turn_index"]
                    for e in posterior["text"]
                )
                if not following:
                    violations.append("posterior_text_not_after_actual_action")
            if not any(
                n["accepted"]
                and n["predicate"] == update["kind"]
                and update["posterior_proposition"] in n["proposition_ids"]
                for n in nodes
            ):
                violations.append("missing_matching_accepted_update_node")
        rows.append(
            dict(
                update_index=index,
                reported_substantive=update["substantive"],
                reported_kind=update["kind"],
                reported_decision_change=update["decision_change"],
                violations=violations,
                original_update_sha256=digest(update),
            )
        )
    return dict(
        policy=POLICY,
        updates=rows,
        diagnostic_only=True,
        semantic_verdict_not_replaced=True,
        chi_not_recomputed_here=True,
        no_model_label_changed=True,
        no_missing_evidence_supplied=True,
    )
