"""Bound offline diagnostics, deliberately not a new financial qualifier.

The existing assessment only identifies complete financial qualification and
final-support-conditioned subchecks. It does NOT independently grade tool
planning or final-answer ability. The interface for those authorities is
prospective; this module admits synthetic CPU controls only. Content hashes
prove identity, not that a caller ran an authentic model or a sound qualifier.
"""

import copy
import json
import re
from collections import Counter

from .protocol import OBJECTIVES, checked_record, encode, record, require, sha

GROUPS = ("dual_sufficient", "composition_required", "other_financial")
STATUSES = ("PASS", "FAIL", "UNKNOWN")
INDEPENDENT = ("tool_success", "final_success")
METRICS = (
    "CompletePass",
    *INDEPENDENT,
    "observed_support_chain",
    "support_conditioned_final_quantity",
)
TASK_FIELDS = {"task_id", "group", "source_cluster", "surface_version_id", "public_messages_sha256"}
SYNTHETIC = "synthetic_cpu_control"


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def preregister_independent_authority(
    metric, *, criterion_id, criterion_text, implementation_sha256, control_suite_sha256
):
    """Pin a predicate interface, not assert that its implementation is validated.

    A future production adapter must validate the actual independent predicate
    and sealed generation/evaluation lineage before this gate can be opened.
    This function cannot authorize such execution by accepting a success flag.
    """
    require(metric in INDEPENDENT, "diagnostic.independent_metric")
    require(_text(criterion_id) and _text(criterion_text), "diagnostic.explicit_criterion")
    require(
        _digest(implementation_sha256) and _digest(control_suite_sha256),
        "diagnostic.pinned_predicate_and_controls",
    )
    return record(
        "independent_diagnostic_authority",
        metric=metric,
        criterion_id=criterion_id,
        criterion_text=criterion_text,
        implementation_sha256=implementation_sha256,
        control_suite_sha256=control_suite_sha256,
        status="INTERFACE_ONLY_NO_PRODUCTION_QUALIFIER",
        production_validated=False,
        confirmation_used_to_choose_criterion=False,
    )


def _authority(value):
    checked_record(value, "independent_diagnostic_authority")
    require(
        value
        == preregister_independent_authority(
            value["metric"],
            criterion_id=value["criterion_id"],
            criterion_text=value["criterion_text"],
            implementation_sha256=value["implementation_sha256"],
            control_suite_sha256=value["control_suite_sha256"],
        ),
        "diagnostic.authority_semantics",
    )
    return value


def build_registration(
    tasks,
    *,
    pool,
    seed,
    split,
    materials_manifest_id,
    pi_id,
    surface_manifest_id,
    frozen_pair_id,
    independent_authorities=(),
    execution_kind=SYNTHETIC,
):
    """Register one shared Full/Hier task panel before either result is read."""
    require(execution_kind == SYNTHETIC, "diagnostic.production_adapter_not_validated")
    require(pool in ("A", "B"), "diagnostic.pool")
    require(type(seed) is int and seed >= 0, "diagnostic.seed")
    require(split in ("dev", "confirm"), "diagnostic.split")
    require(
        all(_text(x) for x in (materials_manifest_id, pi_id, surface_manifest_id, frozen_pair_id)),
        "diagnostic.frozen_pair_parent_ids",
    )
    tasks = copy.deepcopy(list(tasks))
    require(
        tasks and all(isinstance(x, dict) and set(x) == TASK_FIELDS for x in tasks),
        "diagnostic.exact_public_task_fields",
    )
    require(
        all(
            isinstance(x["task_id"], str)
            and re.fullmatch(r"task_[0-9a-f]{64}", x["task_id"])
            and x["group"] in GROUPS
            and _text(x["source_cluster"])
            and _text(x["surface_version_id"])
            and _digest(x["public_messages_sha256"])
            for x in tasks
        ),
        "diagnostic.public_task_identity",
    )
    require(len({x["task_id"] for x in tasks}) == len(tasks), "diagnostic.duplicate_task")
    counts = Counter(x["group"] for x in tasks)
    require(
        set(counts) == set(GROUPS) and len(set(counts.values())) == 1,
        "diagnostic.three_equal_registered_groups",
    )
    authorities = [copy.deepcopy(_authority(x)) for x in independent_authorities]
    require(
        len({x["metric"] for x in authorities}) == len(authorities),
        "diagnostic.duplicate_authority_metric",
    )
    return record(
        "diagnostic_registration",
        pool=pool,
        seed=seed,
        split=split,
        tasks=tasks,
        task_count=len(tasks),
        group_counts=dict(counts),
        materials_manifest_id=materials_manifest_id,
        pi_id=pi_id,
        surface_manifest_id=surface_manifest_id,
        frozen_pair_id=frozen_pair_id,
        objectives=list(OBJECTIVES),
        independent_authorities=authorities,
        execution_kind=execution_kind,
        actual_financial_results=False,
        fixed_denominator=True,
        confirmation_for_weight_or_candidate_selection=False,
        independent_authorities_registered_before_outputs=True,
        host_enforced_chronological_or_provenance_attestation=False,
    )


def _registration(value):
    checked_record(value, "diagnostic_registration")
    require(
        value
        == build_registration(
            value["tasks"],
            **{
                key: value[key]
                for key in (
                    "pool",
                    "seed",
                    "split",
                    "materials_manifest_id",
                    "pi_id",
                    "surface_manifest_id",
                    "frozen_pair_id",
                    "independent_authorities",
                    "execution_kind",
                )
            },
        ),
        "diagnostic.registration_semantics",
    )
    return value


def _original(value, kind):
    require(isinstance(value, dict), "diagnostic.original_record_object")
    body = {key: item for key, item in value.items() if key != "id"}
    require(
        value.get("schema_version") == "eval_readiness.v1." + kind
        and value.get("id") == kind + ":" + sha(encode(body)),
        "diagnostic.original_content_identity:" + kind,
    )
    return value


def _task(registration, task_id):
    matches = [x for x in registration["tasks"] if x["task_id"] == task_id]
    require(len(matches) == 1, "diagnostic.exact_registered_task")
    return matches[0]


def seal_assessment(registration, *, objective, assessment, session, source_members):
    """Bind exact original byte digests and public task identity in CPU controls.

    source_members is a pair of independently supplied expected canonical JSON
    digests, not a claim to have verified a real filesystem manifest. Actual
    production admission remains closed even when these hashes match.
    """
    registration = _registration(registration)
    require(objective in OBJECTIVES, "diagnostic.only_two_registered_objectives")
    _original(assessment, "evaluation_assessment")
    _original(session, "evaluation_session")
    require(
        isinstance(source_members, dict)
        and set(source_members) == {"assessment", "session"}
        and all(_digest(x) for x in source_members.values()),
        "diagnostic.source_member_set",
    )
    require(
        source_members == {"assessment": sha(encode(assessment)), "session": sha(encode(session))},
        "diagnostic.exact_source_member_bytes",
    )
    task = _task(registration, assessment.get("task_id"))
    identity = session.get("identity", {})
    require(
        assessment.get("session_id") == session["id"]
        and identity.get("task_id") == task["task_id"]
        and identity.get("family") == task["group"]
        and identity.get("surface_version_id") == task["surface_version_id"]
        and identity.get("public_messages_sha256") == task["public_messages_sha256"]
        and sha(encode(session.get("public_messages"))) == task["public_messages_sha256"],
        "diagnostic.exact_assessment_session_public_join",
    )
    messages = session["public_messages"]
    try:
        public = json.loads(messages[0]["content"])
    except (IndexError, KeyError, TypeError, ValueError) as error:
        raise ValueError("diagnostic.public_contract") from error
    require(
        public.get("period_contract", {}).get("source_cluster") == task["source_cluster"],
        "diagnostic.same_source_cluster",
    )
    require(
        type(assessment.get("financial_valid")) is bool
        and assessment.get("complete_trajectory_qualified") is assessment["financial_valid"]
        and assessment.get("is_primary_utility_score") is True
        and assessment.get("raw_history_and_tools_replayed") is True,
        "diagnostic.authoritative_complete_qualification_not_answer_only",
    )
    require(
        assessment.get("first_final_index") == session.get("first_final_index")
        and (
            session.get("first_final_index") is None
            or type(session["first_final_index"]) is int
            and session["first_final_index"] >= 0
        ),
        "diagnostic.first_final_join",
    )
    require(
        assessment.get("support_status") in ("PASS", "UNDETERMINED")
        and assessment.get("quantity_status") in ("PASS", "FAIL", "UNDETERMINED"),
        "diagnostic.original_subcheck_statuses",
    )
    complete = assessment["complete_trajectory_qualified"]
    support = assessment["support_status"]
    quantity = assessment["quantity_status"]
    no_final = session["first_final_index"] is None
    require(
        not no_final
        or (
            not complete
            and assessment.get("reason") == "no_final"
            and support == quantity == "UNDETERMINED"
        ),
        "diagnostic.no_final_not_complete_or_conditionally_scored",
    )
    require(
        not complete or (support == quantity == "PASS" and not no_final),
        "diagnostic.complete_requires_original_full_support",
    )
    require(
        quantity == "UNDETERMINED" or support == "PASS",
        "diagnostic.quantity_is_support_conditioned",
    )
    require(quantity != "PASS" or complete, "diagnostic.original_quantity_complete_consistency")
    return record(
        "diagnostic_assessment_evidence",
        registration_id=registration["id"],
        objective=objective,
        task_id=task["task_id"],
        pool=registration["pool"],
        seed=registration["seed"],
        split=registration["split"],
        surface_manifest_id=registration["surface_manifest_id"],
        assessment=assessment,
        session=session,
        source_members=source_members,
        execution_kind=SYNTHETIC,
        production_manifest_verification=False,
        source_identity_not_qualifier_authenticity=True,
    )


def _evidence(registration, evidence):
    checked_record(evidence, "diagnostic_assessment_evidence")
    expected = seal_assessment(
        registration,
        **{key: evidence[key] for key in ("objective", "assessment", "session", "source_members")},
    )
    require(evidence == expected, "diagnostic.evidence_registration_join")
    return evidence


def seal_independent_verdict(registration, evidence, *, authority, status, reason):
    """Explicit predicate-result interchange for synthetic tests; no fake qualifier."""
    _registration(registration)
    _evidence(registration, evidence)
    _authority(authority)
    require(
        authority in registration["independent_authorities"],
        "diagnostic.authority_not_preregistered",
    )
    require(status in STATUSES and _text(reason), "diagnostic.independent_verdict_status_reason")
    return record(
        "independent_diagnostic_verdict",
        registration_id=registration["id"],
        evidence_id=evidence["id"],
        authority_id=authority["id"],
        metric=authority["metric"],
        status=status,
        reason=reason,
        execution_kind=SYNTHETIC,
        actual_predicate_execution_attested=False,
    )


def adapt_assessment(registration, evidence, *, independent_verdicts=()):
    """Consume complete qualification unchanged; never upgrade its proxy fields."""
    registration = _registration(registration)
    evidence = _evidence(registration, evidence)
    assessment = evidence["assessment"]
    no_final = evidence["session"]["first_final_index"] is None
    metrics = {
        "CompletePass": "PASS" if assessment["complete_trajectory_qualified"] else "FAIL",
        "tool_success": "UNKNOWN",
        "final_success": "FAIL" if no_final else "UNKNOWN",
        "observed_support_chain": "PASS" if assessment["support_status"] == "PASS" else "UNKNOWN",
        "support_conditioned_final_quantity": {
            "PASS": "PASS",
            "FAIL": "FAIL",
            "UNDETERMINED": "UNKNOWN",
        }[assessment["quantity_status"]],
    }
    authorities = {x["id"]: x for x in registration["independent_authorities"]}
    verdicts = copy.deepcopy(list(independent_verdicts))
    used = set()
    for verdict in verdicts:
        checked_record(verdict, "independent_diagnostic_verdict")
        require(verdict.get("authority_id") in authorities, "diagnostic.unknown_authority")
        authority = authorities[verdict["authority_id"]]
        expected = seal_independent_verdict(
            registration,
            evidence,
            authority=authority,
            status=verdict["status"],
            reason=verdict["reason"],
        )
        require(verdict == expected, "diagnostic.independent_verdict_exact_parent")
        metric = authority["metric"]
        require(metric not in used, "diagnostic.duplicate_independent_verdict")
        used.add(metric)
        require(
            not (metric == "final_success" and no_final) or verdict["status"] == "FAIL",
            "diagnostic.no_final_cannot_pass_or_become_unknown",
        )
        metrics[metric] = verdict["status"]
    return record(
        "task_diagnostic_verdict",
        registration_id=registration["id"],
        objective=evidence["objective"],
        task=copy.deepcopy(_task(registration, evidence["task_id"])),
        metrics=metrics,
        reasoning_quality="UNKNOWN_NO_REGISTERED_AUTHORITY",
        no_final=no_final,
        original_reason=assessment.get("reason"),
        evidence=evidence,
        independent_verdicts=verdicts,
        actual_financial_results=False,
        primary_rule_unchanged=True,
        proxies_are_independent_ability_metrics=False,
    )


def _rates(rows, metric):
    counts = Counter(row["metrics"][metric] for row in rows)
    total = len(rows)
    require(total > 0, "diagnostic.nonempty_registered_denominator")
    return {
        "registered_total": total,
        "pass": counts["PASS"],
        "fail": counts["FAIL"],
        "unknown": counts["UNKNOWN"],
        "known_verdicts": total - counts["UNKNOWN"],
        "credited_success_rate": counts["PASS"] / total,
        "identified_success_rate_bounds": [
            counts["PASS"] / total,
            (counts["PASS"] + counts["UNKNOWN"]) / total,
        ],
        "unknown_zero_credit_is_not_observed_failure": True,
    }


def summarize(registration, verdicts, *, objective):
    registration = _registration(registration)
    require(objective in OBJECTIVES, "diagnostic.only_two_registered_objectives")
    rows = copy.deepcopy(list(verdicts))
    for row in rows:
        checked_record(row, "task_diagnostic_verdict")
        expected = adapt_assessment(
            registration, row["evidence"], independent_verdicts=row["independent_verdicts"]
        )
        require(
            row == expected and row["objective"] == objective,
            "diagnostic.verdict_exact_registered_semantics",
        )
    ids = [row["task"]["task_id"] for row in rows]
    require(len(set(ids)) == len(ids), "diagnostic.duplicate_result")
    expected_ids = [task["task_id"] for task in registration["tasks"]]
    require(
        set(ids) == set(expected_ids) and len(rows) == registration["task_count"],
        "diagnostic.missing_extra_or_unregistered_result",
    )
    by_id = {row["task"]["task_id"]: row for row in rows}
    rows = [by_id[task_id] for task_id in expected_ids]
    groups = {
        group: {
            metric: _rates([r for r in rows if r["task"]["group"] == group], metric)
            for metric in METRICS
        }
        for group in GROUPS
    }
    overall = {metric: _rates(rows, metric) for metric in METRICS}
    return record(
        "diagnostic_summary",
        registration_id=registration["id"],
        objective=objective,
        pool=registration["pool"],
        seed=registration["seed"],
        split=registration["split"],
        registered_total=len(rows),
        groups=groups,
        metrics=overall,
        verdicts=rows,
        primary_metric="CompletePass",
        primary_utility=sum(groups[g]["CompletePass"]["credited_success_rate"] for g in GROUPS) / 3,
        no_final_count=sum(row["no_final"] for row in rows),
        unknown_missing_final_errors_retained_in_registered_denominator=True,
        all_missing_evidence_must_be_explicit_unknown_not_silently_omitted=True,
        independent_qualifier_production_gate="NOT_IMPLEMENTED_OR_VALIDATED",
        actual_financial_results=False,
        selection_recommendation=None,
        confirmation_may_choose_loss_weights_or_candidates=False,
    )


def paired_compare(registration, full, hierarchical):
    """Same-task differences, with partial-identification bounds for UNKNOWNs."""
    registration = _registration(registration)
    for report, objective in zip((full, hierarchical), OBJECTIVES, strict=True):
        checked_record(report, "diagnostic_summary")
        require(
            report == summarize(registration, report["verdicts"], objective=objective),
            "diagnostic.pair_same_registration_and_objective",
        )
    paired = []
    for left, right in zip(full["verdicts"], hierarchical["verdicts"], strict=True):
        require(left["task"] == right["task"], "diagnostic.paired_task_surface_source")
        metric_rows = {}
        for metric in METRICS:
            a, b = left["metrics"][metric], right["metrics"][metric]
            metric_rows[metric] = {
                "full": a,
                "hierarchical": b,
                "credit_delta": int(b == "PASS") - int(a == "PASS"),
                "observed_delta": None
                if "UNKNOWN" in (a, b)
                else int(b == "PASS") - int(a == "PASS"),
                "effect_bounds": [
                    int(b == "PASS") - int(a != "FAIL"),
                    int(b != "FAIL") - int(a == "PASS"),
                ],
            }
        paired.append({"task": left["task"], "metrics": metric_rows})
    total = registration["task_count"]
    effects = {
        metric: {
            "registered_pairs": total,
            "fully_observed_pairs": sum(
                row["metrics"][metric]["observed_delta"] is not None for row in paired
            ),
            "mean_credit_delta": sum(row["metrics"][metric]["credit_delta"] for row in paired)
            / total,
            "identified_mean_effect_bounds": [
                sum(row["metrics"][metric]["effect_bounds"][j] for row in paired) / total
                for j in (0, 1)
            ],
            "bounds_are_not_confidence_intervals": True,
        }
        for metric in METRICS
    }
    return record(
        "paired_loss_diagnostics",
        registration_id=registration["id"],
        full_summary_id=full["id"],
        hierarchical_summary_id=hierarchical["id"],
        paired_tasks=paired,
        metrics=effects,
        primary_metric="CompletePass",
        same_materials_pi_seed_surfaces=True,
        actual_financial_results=False,
        unknown_credit_differences_are_not_identified_ability_effects=True,
        supports_causal_efficacy_claim=False,
        selected_objective=None,
        confirmation_used_for_loss_weight_or_candidate_selection=False,
    )
