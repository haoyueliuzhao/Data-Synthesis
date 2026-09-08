"""Posthoc intent annotations checked against raw quotes; no intent is inferred here."""

from collections import Counter

from trusted_synthesis.domains.finance.qa_vnext.protocol import require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.runtime import decode


def summarize_intent(rows):
    counts = Counter(r["classification"] for r in rows)
    clear = counts["MATCH"] + counts["MISMATCH"]
    return {
        "raw_action_rows": len(rows),
        "MATCH": counts["MATCH"],
        "MISMATCH": counts["MISMATCH"],
        "UNDETERMINABLE": counts["UNDETERMINABLE"],
        "clear_public_intent_rows": clear,
        "mismatch_rate_among_clear": counts["MISMATCH"] / clear if clear else None,
        "posthoc_unblinded_descriptive_not_independent_task_rate": True,
    }


def verify_intent_review(audit, directory, checks):
    layers = {
        r["submission"]: r for r in audit["action_layers"]["events"] if r["raw_action_shaped"]
    }
    require(len(checks) == len(layers), "intent.every_raw_action_shape")
    require(
        len({r["submission"] for r in checks}) == len(checks)
        and {r["submission"] for r in checks} == set(layers),
        "intent.exact_unique_submission_population",
    )
    rows = []
    for check in sorted(checks, key=lambda r: r["submission"]):
        index, classification = check["submission"], check["classification"]
        require(classification in {"MATCH", "MISMATCH", "UNDETERMINABLE"}, "intent.classification")
        require(
            isinstance(check.get("explanation"), str) and bool(check["explanation"]),
            "intent.explanation",
        )
        require(isinstance(check.get("quotes"), list), "intent.quote_list")
        raw = (directory / f"runtime/turns/{index - 1:03d}_response.raw").read_bytes()
        model = decode(raw)
        require(model["kind"] == "action", "intent.raw_action_shape_not_salvage")
        for quote in check["quotes"]:
            require(quote["field"] in {"reason", "subgoal"}, "intent.public_quote_field")
            require(
                isinstance(model.get(quote["field"]), str)
                and isinstance(quote["text"], str)
                and bool(quote["text"])
                and quote["text"] in model[quote["field"]],
                "intent.exact_original_public_quote",
            )
        require(
            classification == "UNDETERMINABLE" or bool(check["quotes"]),
            "intent.clear_label_requires_quote",
        )
        require(
            isinstance(check.get("checked_dimensions"), list)
            and set(check["checked_dimensions"])
            <= {"operation", "ordered_values", "source_identity", "stated_period"},
            "intent.dimensions",
        )
        require(
            classification == "UNDETERMINABLE" or bool(check["checked_dimensions"]),
            "intent.clear_label_requires_dimension",
        )
        layer = layers[index]
        rows.append(
            {
                **check,
                "raw_sha256": layer["raw_sha256"],
                "raw_operation": layer["raw_operation"],
                "raw_inputs": layer["raw_inputs"],
                "schema_valid_action": layer["schema_valid_action"],
                "actual_execution": layer["actual_execution"],
                "transition_error": layer["transition_error"],
                "after_first_target_rejection": layer["after_first_target_rejection"],
                "annotation_not_used_for_admission_or_feedback": True,
            }
        )
    return {
        "events": rows,
        "all_raw_action_shapes": summarize_intent(rows),
        "actually_executed_actions": summarize_intent([r for r in rows if r["actual_execution"]]),
        "post_target_rejection_raw_actions": summarize_intent(
            [r for r in rows if r["after_first_target_rejection"]]
        ),
    }
