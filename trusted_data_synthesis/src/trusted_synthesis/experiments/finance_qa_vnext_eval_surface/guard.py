"""Public-only protected base questions with a finite positive English grammar.

The original public period/operation explanation is copied byte-for-byte, but
never used to excuse a conflicting rewritten base. Model requests receive only
``model_contract``: no answers, winning periods, source leaves or method labels.
"""

import copy
import hashlib
import json
import re
from datetime import date, timedelta

from ..finance_qa_vnext_task_build.archive import record, require, validate_record

VERSION = "evaluation_surface_rewrite.v1"
SEPARATOR = "\n\nActual comparison periods (inclusive source dates):"
PUBLIC_KEYS = {
    "question",
    "period_contract",
    "source_document",
    "quantity_contract",
    "source_policy",
    "tool_contract",
}
IDENTITY_KEYS = {
    "task_id",
    "family",
    "surface_version_id",
    "public_messages_sha256",
    "parent_manifest_id",
}
METRIC_NAMES = {
    "revenue": "Revenue",
    "gross_profit": "Gross Profit",
    "net_income": "Net Income",
    "operating_income": "Operating Income",
    "net_cash_provided_by_used_in_operating_activities": (
        "Net Cash Provided by Used in Operating Activities"
    ),
    "cash_and_cash_equivalents": "Cash and Cash Equivalents",
    "cash_cash_equivalents_restricted_cash_and_restricted_cash_equivalents": (
        "Cash, Cash Equivalents, Restricted Cash and Restricted Cash Equivalents"
    ),
}
PLACEHOLDER = re.compile(r"<slot_[a-z_]+>")
VERB = r"(?:please\s+)?(?:calculate|compute|determine|report|give|state)"
QUERY = r"(?:what\s+(?:is|was)|" + VERB + ")"
CHOOSE = r"(?:identify|determine|find|select)"
LOOKUP = r"(?:report|give|state|look\s+up)"
THREE_PERIODS = r"(?:exactly|all)\s+three\s+actual\s+(?:annual|reporting)\s+periods\s*:?\s*"


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def messages(public):
    return [{"role": "user", "content": json.dumps(public, ensure_ascii=False, sort_keys=True)}]


def split_question(question):
    require(
        isinstance(question, str) and question.count(SEPARATOR) == 1,
        "surface.exact_original_question_separator",
    )
    base, rest = question.split(SEPARATOR, 1)
    require(bool(base.strip()), "surface.original_base_present")
    return base, SEPARATOR + rest


def _period_text(period):
    if period["period_type"] == "instant":
        return "the instant at " + period["end"]
    return "the period " + period["start"] + " through " + period["end"]


def _public_contract(public, identity):
    require(isinstance(public, dict) and set(public) == PUBLIC_KEYS, "surface.closed_public_input")
    require(
        isinstance(identity, dict)
        and set(identity) <= IDENTITY_KEYS
        and {"task_id", "surface_version_id", "public_messages_sha256"} <= set(identity),
        "surface.public_identity_only",
    )
    require(
        sha(encode(messages(public))) == identity["public_messages_sha256"],
        "surface.original_public_identity",
    )
    contract = public["period_contract"]
    require(
        contract["schema"] == "actual_period_contract.v1"
        and contract["task_id"] == identity["task_id"],
        "surface.original_target_contract",
    )
    body = {key: value for key, value in contract.items() if key != "id"}
    require(
        contract["id"]
        == "actual_period_contract:"
        + sha(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()),
        "surface.public_period_contract_identity",
    )
    require(
        re.fullmatch(r"cik:\d{10}", contract["source_cluster"]), "surface.exact_public_company_CIK"
    )
    require(
        contract["period_order"] == "chronological"
        and contract["interval_boundaries"] == "inclusive",
        "surface.actual_period_order",
    )
    operation, periods = contract["operation"], contract["periods"]
    kind = operation["kind"]
    expected_quantity = {
        "difference": "difference",
        "relative_change": "relative_change",
        "arithmetic_mean": "three_annual_flow_mean",
        "argmax_then_lookup": "three_year_peak_then_same_period_metric",
    }
    require(
        kind in expected_quantity and contract["quantity"] == expected_quantity[kind],
        "surface.registered_public_operation",
    )
    require(
        len(periods) == (3 if kind in {"arithmetic_mean", "argmax_then_lookup"} else 2),
        "surface.exact_public_operand_count",
    )
    pairs = []
    for period in periods:
        start, end = period["start"], period["end"]
        last = date.fromisoformat(end)
        first = date.fromisoformat(start) if start is not None else None
        require(first is None or first <= last, "surface.actual_period_not_reversed")
        kind_period = "instant" if start is None else "duration"
        identifier = (
            "period:instant:" + end if start is None else "period:duration:" + start + ":" + end
        )
        require(
            period["period_type"] == kind_period and period["period_id"] == identifier,
            "surface.actual_period_identity",
        )
        require(
            period["label_basis"] in {"actual_interval", "calendar_year"},
            "surface.no_unproven_period_label",
        )
        if period["label_basis"] == "calendar_year":
            require(
                start == end[:4] + "-01-01" and end == start[:4] + "-12-31",
                "surface.true_calendar_year_only",
            )
        pairs.append((first, last))
    require(
        len(set(pairs)) == len(pairs) and pairs == sorted(pairs, key=lambda pair: pair[1]),
        "surface.unique_ordered_actual_periods",
    )
    for previous, current in zip(pairs, pairs[1:], strict=False):
        require((previous[0] is None) == (current[0] is None), "surface.consistent_period_type")
        if previous[0] is not None:
            require(
                current[0] == previous[1] + timedelta(days=1), "surface.consecutive_actual_periods"
            )
    metric_ids = contract["metric_ids"]
    require(
        all(metric in METRIC_NAMES for metric in metric_ids)
        and len(set(metric_ids)) == len(metric_ids),
        "surface.registered_full_metric_labels",
    )
    if kind == "argmax_then_lookup":
        require(
            len(metric_ids) == 2
            and operation["primary_metric_id"] == metric_ids[0]
            and operation["secondary_metric_id"] == metric_ids[1]
            and operation["candidate_count"] == 3
            and operation["same_actual_period_required"] is True,
            "surface.primary_secondary_roles_and_candidate_domain",
        )
    else:
        require(
            len(metric_ids) == 1 and operation["metric_id"] == metric_ids[0],
            "surface.scalar_metric_role",
        )
        if kind == "arithmetic_mean":
            require(operation["operand_count"] == 3, "surface.three_equal_mean_operands")
        else:
            require(operation["direction"] == "current_minus_previous", "surface.forward_delta")
            if kind == "relative_change":
                require(
                    operation["denominator"] == "strictly_positive_previous"
                    and operation["multiplier"] == 100,
                    "surface.positive_previous_percentage_base",
                )
    if kind in {"arithmetic_mean", "argmax_then_lookup"}:
        require(
            all(start is not None and 330 <= (end - start).days + 1 <= 380 for start, end in pairs),
            "surface.three_actual_annual_flows",
        )
    quantity = public["quantity_contract"]
    unit = "percent" if kind == "relative_change" else "million USD"
    require(
        quantity["unit"] == unit
        and quantity["currency"] == (None if unit == "percent" else "USD")
        and quantity["decimal_places"] == 2
        and quantity["rounding"] == "half away from zero"
        and quantity["period_required"] == (kind == "argmax_then_lookup"),
        "surface.exact_public_output_contract",
    )
    return contract


def build_spec(public, identity):
    """The only builder input is an already public message and its public ID."""
    contract = _public_contract(public, identity)
    original_base, suffix = split_question(public["question"])
    blocks = re.findall(
        r"BEGIN ACTUAL PERIOD CONTRACT\s*(.*?)\s*END ACTUAL PERIOD CONTRACT", suffix, re.DOTALL
    )
    require(
        len(blocks) == 1 and json.loads(blocks[0]) == contract, "surface.original_suffix_contract"
    )
    operation, kind = contract["operation"], contract["operation"]["kind"]
    output = (
        "Report the result in percent, rounded to two decimal places using half away from zero."
        if kind == "relative_change"
        else (
            "Report the result in million USD, rounded to two decimal places "
            "using half away from zero."
        )
    )
    if kind == "argmax_then_lookup":
        output = (
            "In the first Final, report the selected actual period_id and the secondary amount "
            "in million USD, rounded to two decimal places using half away from zero."
        )
    slots = {
        "entity": "the company with CIK " + contract["source_cluster"].split(":", 1)[1],
        "output_instruction": output,
    }
    if kind in {"difference", "relative_change"}:
        slots.update(
            metric=METRIC_NAMES[contract["metric_ids"][0]],
            previous_period=_period_text(contract["periods"][0]),
            current_period=_period_text(contract["periods"][1]),
        )
        noun = "signed change" if kind == "difference" else "percentage change"
        equation = (
            "current minus previous"
            if kind == "difference"
            else "(current minus previous) divided by the strictly positive previous amount "
            "and multiplied by one hundred"
        )
        template = (
            f"Calculate the {noun} in <slot_metric> for <slot_entity> from <slot_previous_period> "
            f"to <slot_current_period>, defined as {equation}. <slot_output_instruction>"
        )
    else:
        slots["periods"] = "[" + "; ".join(_period_text(row) for row in contract["periods"]) + "]"
        if kind == "arithmetic_mean":
            slots["metric"] = METRIC_NAMES[contract["metric_ids"][0]]
            template = (
                "Calculate the arithmetic mean of <slot_metric> for <slot_entity> across "
                "exactly three actual annual periods: <slot_periods>. <slot_output_instruction>"
            )
        else:
            slots["primary_metric"] = METRIC_NAMES[operation["primary_metric_id"]]
            slots["secondary_metric"] = METRIC_NAMES[operation["secondary_metric_id"]]
            template = (
                "Among all three actual annual periods: <slot_periods>, identify the actual "
                "period with the highest <slot_primary_metric> for <slot_entity>, then report "
                "<slot_secondary_metric> for that same actual period. <slot_output_instruction>"
            )
    placeholders = ["<slot_" + key + ">" for key in sorted(slots)]
    model_contract = {
        "rewrite_version": VERSION,
        "quantity_kind": kind,
        "canonical_template": template,
        "required_placeholders": placeholders,
        "language": "English finite direct questions or requests",
        "output_schema": {"rewrites": [{"rewrite_version": VERSION, "question_template": "..."}]},
        "candidate_count": "one or two, in fixed preference order",
        "immutable_slots": (
            "Every placeholder exactly once; output_instruction last. Never fill placeholders."
        ),
        "semantic_constraints": {
            "difference": (
                "Signed current minus previous; previous_period before current_period; "
                "no magnitude or rate."
            ),
            "relative_change": (
                "Percentage change: (current minus previous) / strictly positive "
                "previous amount, multiplied by one hundred; "
                "no simple ratio or current base."
            ),
            "arithmetic_mean": (
                "Arithmetic mean over exactly/all three actual annual periods; "
                "each period equally weighted, none omitted; "
                "no weighted/geometric mean or extra operations."
            ),
            "argmax_then_lookup": (
                "All three actual annual periods; highest primary_metric first, "
                "then secondary_metric for that same actual period; "
                "no swapped roles, other selected period, "
                "or alternative selection statistic."
            ),
        }[kind],
        "permitted_wording": (
            "Keep the complete objective clauses. You may vary "
            "calculate/compute/determine/report/give/state, what is/what was, for/reported by, "
            "across/over, highest/largest/maximum, identify/find/select, "
            "report/give/state/look up, and move the company or full-period clause to the front. "
            "Keep an explicit same-actual-period lookup and "
            "complete actual-period comparison domain."
        ),
        "forbidden": (
            "No literal numbers, new entity/metric aliases, answers, explanations, "
            "private leaves, basis labels, method routes, negation, "
            "extra constraints or operations."
        ),
    }
    provisional = {
        "quantity_kind": kind,
        "slot_values": slots,
        "required_placeholders": placeholders,
    }
    canonical_base = _render(template, slots)
    require(validate_base(template, provisional)["passed"], "surface.canonical_positive_grammar")
    return record(
        "evaluation_rewrite_spec",
        rewrite_version=VERSION,
        identity=copy.deepcopy(identity),
        task_id=identity["task_id"],
        quantity_kind=kind,
        slot_values=slots,
        required_placeholders=placeholders,
        canonical_template=template,
        canonical_base=canonical_base,
        canonical_base_sha256=sha(canonical_base),
        original_base=original_base,
        original_base_sha256=sha(original_base),
        canonical_preparation_changed_original=canonical_base != original_base,
        canonical_preparation_is_LLM_rewrite=False,
        immutable_suffix=suffix,
        immutable_suffix_sha256=sha(suffix),
        original_public=copy.deepcopy(public),
        unchanged_public_fields_sha256=sha(
            encode({k: v for k, v in public.items() if k != "question"})
        ),
        model_contract=model_contract,
        private_inputs_accepted=False,
    )


def _patterns(kind):
    e, m, previous, current = map(
        re.escape,
        ("<slot_entity>", "<slot_metric>", "<slot_previous_period>", "<slot_current_period>"),
    )
    p, primary, secondary = map(
        re.escape, ("<slot_periods>", "<slot_primary_metric>", "<slot_secondary_metric>")
    )
    if kind in {"difference", "relative_change"}:
        noun = (
            r"signed\s+(?:change|difference)"
            if kind == "difference"
            else r"(?:year(?:-|\s+)over(?:-|\s+)year\s+)?percentage\s+change"
        )
        target = r"(?:the\s+)?" + noun + r"\s+in\s+" + m
        scope = r"from\s+" + previous + r"\s+to\s+" + current
        bodies = [
            QUERY + r"\s+" + target + r"\s+for\s+" + e + r"\s+" + scope,
            r"for\s+" + e + r",\s*" + QUERY + r"\s+" + target + r"\s+" + scope,
            scope + r",\s*" + QUERY + r"\s+" + target + r"\s+for\s+" + e,
        ]
        equation = (
            r"(?:current\s+minus\s+previous|later\s+minus\s+earlier)"
            if kind == "difference"
            else (
                r"\((?:current\s+minus\s+previous|later\s+minus\s+earlier)\)\s+"
                r"divided\s+by\s+the\s+strictly\s+positive\s+(?:previous|earlier)\s+amount\s+"
                r"(?:and\s+)?multiplied\s+by\s+one\s+hundred"
            )
        )
        return [body + r",\s*(?:defined|calculated)\s+as\s+" + equation for body in bodies]
    if kind == "arithmetic_mean":
        noun = r"(?:the\s+)?(?:unweighted\s+)?arithmetic\s+mean\s+of\s+" + m
        scope = r"(?:across|over)\s+" + THREE_PERIODS + p
        company = r"(?:for|reported\s+by)\s+" + e
        return [
            QUERY + r"\s+" + noun + r"\s+" + company + r"\s+" + scope,
            r"for\s+" + e + r",\s*" + QUERY + r"\s+" + noun + r"\s+" + scope,
            scope + r",\s*" + QUERY + r"\s+" + noun + r"\s+" + company,
        ]
    if kind == "argmax_then_lookup":
        scope = (
            r"(?:among|across)\s+all\s+three\s+actual\s+(?:annual|reporting)\s+periods\s*:?\s*" + p
        )
        peak = (
            CHOOSE + r"\s+the\s+actual\s+period\s+(?:with|having)\s+(?:the\s+)?"
            r"(?:highest|largest|maximum)\s+" + primary + r"\s+(?:for|reported\s+by)\s+" + e
        )
        same = LOOKUP + r"\s+" + secondary + r"\s+(?:for|from|in)\s+that\s+same\s+actual\s+period"
        return [
            scope + r",\s*" + peak + r",\s*then\s+" + same,
            peak + r"\s+" + scope + r",\s*then\s+" + same,
            r"for\s+"
            + e
            + r",\s*"
            + scope
            + r",\s*"
            + CHOOSE
            + r"\s+the\s+actual\s+period\s+(?:with|having)\s+(?:the\s+)?"
            r"(?:highest|largest|maximum)\s+" + primary + r",\s*then\s+" + same,
            r"which\s+of\s+(?:the\s+)?three\s+actual\s+(?:annual|reporting)\s+periods\s*:?\s*"
            + p
            + r"\s+(?:had|has)\s+(?:the\s+)?(?:highest|largest|maximum)\s+"
            + primary
            + r"\s+for\s+"
            + e
            + r",\s*and\s+what\s+(?:was|is)\s+"
            + secondary
            + r"\s+(?:for|in)\s+that\s+same\s+actual\s+period",
        ]
    return []


def validate_base(template, spec):
    """Accept complete affirmative objective grammar, not keyword coincidence."""
    errors = []
    if not isinstance(template, str) or not template.strip() or len(template) > 6000:
        return {"passed": False, "errors": ["surface.bounded_nonempty_base_template"]}
    observed = PLACEHOLDER.findall(template)
    if sorted(observed) != sorted(spec["required_placeholders"]) or len(set(observed)) != len(
        observed
    ):
        errors.append("surface.exact_once_role_placeholders")
    masked = PLACEHOLDER.sub("", template)
    if re.search(r"\d", masked):
        errors.append("surface.no_unprotected_literal_numbers")
    if "<" in masked or ">" in masked:
        errors.append("surface.no_unknown_placeholder_or_markup")
    if not template.rstrip().endswith("<slot_output_instruction>"):
        errors.append("surface.output_instruction_must_be_last")
    core = re.sub(r"\s*<slot_output_instruction>\s*$", "", template).strip()
    if not core or core[-1:] not in {".", "?"}:
        errors.append("surface.single_complete_base_request")
    else:
        core = core[:-1].strip()
    if not any(
        re.fullmatch(pattern, core, re.IGNORECASE) for pattern in _patterns(spec["quantity_kind"])
    ):
        errors.append("surface.base_positive_objective_grammar")
    return {
        "passed": not errors,
        "errors": sorted(set(errors)),
        "parsed_operation": spec["quantity_kind"] if not errors else None,
        "question_template": template,
        "grammar": "protected_base_affirmative_roles.v1",
        "appended_contract_used_to_repair_base": False,
        "arbitrary_language_equivalence_claimed": False,
    }


def validate_candidate(candidate, spec):
    if (
        not isinstance(candidate, dict)
        or set(candidate) != {"rewrite_version", "question_template"}
        or candidate.get("rewrite_version") != VERSION
    ):
        return {"passed": False, "errors": ["surface.closed_rewrite_candidate_schema"]}
    return validate_base(candidate["question_template"], spec)


def classify_change(template, spec):
    """Diversity is measured against the model's prompt, never local preparation."""
    require(validate_base(template, spec)["passed"], "surface.classification_after_semantics")

    def words(value):
        return re.findall(r"<slot_[a-z_]+>|[a-z]+", value.casefold())

    changed = words(template) != words(spec["canonical_template"])

    def public_words(value):
        return re.findall(r"\d+(?:\.\d+)?|[^\W\d_]+", value.casefold())

    actual_changed = public_words(_render(template, spec["slot_values"])) != public_words(
        spec["original_base"]
    )
    accepted = changed and actual_changed
    return {
        "comparison_origin": "canonical_prompt_template",
        "category": "accepted_true_rewrite" if accepted else "unchanged_or_format_only",
        "true_lexical_change": changed,
        "final_base_changed_original": actual_changed,
        "unchanged_or_format_only": not accepted,
        "canonical_preparation_changed_original": spec["canonical_preparation_changed_original"],
        "local_preparation_counted_as_LLM_rewrite": False,
    }


def _render(template, slots):
    value = template
    for key, replacement in slots.items():
        value = value.replace("<slot_" + key + ">", replacement)
    return value


def render_and_validate(template, spec):
    validate_record(spec, "evaluation_rewrite_spec")
    require(
        build_spec(spec["original_public"], spec["identity"]) == spec,
        "surface.spec_is_exact_public_derivation",
    )
    validation = validate_base(template, spec)
    if not validation["passed"]:
        return {"passed": False, "errors": validation["errors"], "validation": validation}
    base = _render(template, spec["slot_values"])
    # Independently re-mask local rendering by immutable, role-specific values;
    # a changed slot or extra character cannot become an accepted surface.
    remasked = base
    for key, value in sorted(
        spec["slot_values"].items(), key=lambda item: len(item[1]), reverse=True
    ):
        require(remasked.count(value) == 1, "surface.rendered_slot_exactly_once")
        remasked = remasked.replace(value, "<slot_" + key + ">", 1)
    require(remasked == template, "surface.rendered_base_exact_roundtrip")
    public = copy.deepcopy(spec["original_public"])
    public["question"] = base + spec["immutable_suffix"]
    require(
        sha(encode({key: value for key, value in public.items() if key != "question"}))
        == spec["unchanged_public_fields_sha256"],
        "surface.only_base_mutation",
    )
    require(
        split_question(public["question"])[1] == spec["immutable_suffix"],
        "surface.original_suffix_literal_bytes",
    )
    payload = messages(public)
    return {
        "passed": True,
        "errors": [],
        "base_question": base,
        "question": public["question"],
        "public": public,
        "messages": payload,
        "public_messages_sha256": sha(encode(payload)),
        "base_question_sha256": sha(base),
        "immutable_suffix_sha256": spec["immutable_suffix_sha256"],
        "validation": validation,
        "change_classification": classify_change(template, spec),
        "spec_id": spec["id"],
        "fallback_selected_here": False,
    }
