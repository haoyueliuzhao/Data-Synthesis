"""Actual-date task contracts and independently parsed public-period admission.

This is a bounded financial-period validator, not a natural-language proof
system. Rendering never supplies reference values, source leaves or the peak.
The admission parser does not call the renderer or pipeline time-label helpers.
"""

import hashlib
import json
import re
from datetime import date, timedelta

SCHEMA = "actual_period_contract.v1"
BEGIN = "BEGIN ACTUAL PERIOD CONTRACT"
END = "END ACTUAL PERIOD CONTRACT"


def period_identity(start, end, period_type="duration"):
    """Public identity shared by source-query records and Final selection."""
    end_date = date.fromisoformat(str(end))
    if period_type == "instant":
        if start is not None:
            raise ValueError("period.instant_has_start")
        return f"period:instant:{end_date.isoformat()}"
    if period_type != "duration" or start is None:
        raise ValueError("period.invalid_type_or_missing_start")
    start_date = date.fromisoformat(str(start))
    if start_date > end_date:
        raise ValueError("period.reversed_interval")
    return f"period:duration:{start_date.isoformat()}:{end_date.isoformat()}"


def _period(start, end):
    kind = "duration" if start is not None else "instant"
    identifier = period_identity(start, end, kind)
    calendar = bool(start and start == end[:4] + "-01-01" and end == start[:4] + "-12-31")
    return {
        "period_id": identifier,
        "start": start,
        "end": end,
        "period_type": kind,
        "label_basis": "calendar_year" if calendar else "actual_interval",
    }


def _target_periods(target):
    raw = target.get("actual_periods")
    if raw is None:
        raw = [target["previous_period"], target["current_period"]]
    return [tuple(value) for value in raw]


def _target_operation(target):
    quantity = target["quantity"]
    metrics = target.get("metric_ids") or [target["metric_id"]]
    if quantity == "three_annual_flow_mean":
        return {"kind": "arithmetic_mean", "metric_id": metrics[0], "operand_count": 3}
    if quantity == "three_year_peak_then_same_period_metric":
        return {
            "kind": "argmax_then_lookup",
            "primary_metric_id": metrics[0],
            "secondary_metric_id": metrics[1],
            "candidate_count": 3,
            "same_actual_period_required": True,
        }
    if quantity not in {"difference", "relative_change"}:
        raise ValueError("period.unsupported_quantity")
    operation = {
        "kind": quantity,
        "metric_id": metrics[0],
        "direction": "current_minus_previous",
    }
    if quantity == "relative_change":
        operation["denominator"] = "strictly_positive_previous"
        operation["multiplier"] = 100
    return operation


def build_contract(item, facts, native_bindings):
    """Bind the canonical target to selected native records without FY guessing.

    SEC ``fy`` identifies a reporting context and is not evidence that an earlier
    comparative observation has that fiscal-year name. Therefore this adapter uses
    actual intervals even when such a field happens to agree with the end year.
    """
    target = item["target"]
    pairs = _target_periods(target)
    metrics = list(target.get("metric_ids") or [target["metric_id"]])
    selected = [facts[key] for key in item["match"]["fact_ids"]]
    for row in selected:
        native = native_bindings[row["fact_id"]]
        record = native["record"]
        if (row.get("period_start"), row["period_end"]) != (record.get("start"), record["end"]):
            raise ValueError("period.fact_native_date_mismatch")
        if row["metric_id"] != native["metric_id"]:
            raise ValueError("period.fact_native_metric_mismatch")
        if native["source_cluster"] != target["source_cluster"]:
            raise ValueError("period.fact_native_cluster_mismatch")
    expected = {(metric, *pair) for metric in metrics for pair in pairs}
    found = {(row["metric_id"], row.get("period_start"), row["period_end"]) for row in selected}
    if not expected.issubset(found):
        raise ValueError("period.metric_exact_period_coverage_missing")
    periods = [_period(*pair) for pair in pairs]
    contract = {
        "schema": SCHEMA,
        "task_id": item["task_id"],
        "source_cluster": target["source_cluster"],
        "quantity": target["quantity"],
        "metric_ids": metrics,
        "periods": periods,
        "operation": _target_operation(target),
        "period_order": "chronological",
        "interval_boundaries": "inclusive",
        "fiscal_year_naming": "not_inferred_from_filing_fy_or_end_year",
    }
    errors = _validate_native_contract(contract, native_bindings, canonical_target=target)
    if errors:
        raise ValueError(";".join(errors))
    raw = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    contract["id"] = "actual_period_contract:" + hashlib.sha256(raw).hexdigest()
    return contract


def render_public_periods(contract):
    """Deterministic public explanation; no values or selected-period hint."""
    lines = ["Actual comparison periods (inclusive source dates):"]
    for period in contract["periods"]:
        interval = (
            f"{period['start']} through {period['end']}"
            if period["period_type"] == "duration"
            else f"instant at {period['end']}"
        )
        lines.append(f"Period {period['period_id']}: {interval}.")
    operation = contract["operation"]
    if operation["kind"] == "arithmetic_mean":
        instruction = "Compute the arithmetic mean of the metric over all three listed periods."
    elif operation["kind"] == "argmax_then_lookup":
        instruction = (
            "Select the largest primary-metric observation among all three listed periods, "
            "then report the secondary metric from that same actual period. "
            "In Final identify the selected period_id or its complete start/end interval; "
            "a four-digit year alone does not identify the period."
        )
    elif operation["kind"] == "relative_change":
        instruction = (
            "Compute (current minus previous) divided by the strictly positive previous "
            "amount, multiplied by 100. Current is the later listed period."
        )
    else:
        instruction = "Compute current minus previous. Current is the later listed period."
    lines.extend([instruction, BEGIN, json.dumps(contract, sort_keys=True), END])
    return "\n".join(lines)


def _validate_native_contract(contract, native_bindings, *, canonical_target=None):
    """Independently inspect ISO dates, date adjacency and raw record coverage."""
    errors = []
    if contract.get("schema") != SCHEMA:
        errors.append("period.wrong_contract_schema")
    periods = contract.get("periods") or []
    parsed = []
    for period in periods:
        try:
            start_text, end_text = period["start"], period["end"]
            start = None if start_text is None else date.fromisoformat(start_text)
            end = date.fromisoformat(end_text)
            kind = period["period_type"]
            # Intentionally reconstruct the identifier here rather than invoke
            # period_identity, _period or any renderer/time-label helper.
            if start is None:
                expected_id = "period:instant:" + end.isoformat()
                valid = kind == "instant"
            else:
                expected_id = "period:duration:" + start.isoformat() + ":" + end.isoformat()
                valid = kind == "duration" and start <= end
            if not valid or period["period_id"] != expected_id:
                errors.append("period.invalid_identity")
            calendar = start == date(end.year, 1, 1) and end == date(end.year, 12, 31)
            if period["label_basis"] == "calendar_year" and not calendar:
                errors.append("period.false_calendar_year")
            if period["label_basis"] not in {"calendar_year", "actual_interval"}:
                errors.append("period.unsupported_unproven_label")
            parsed.append((start, end))
        except (KeyError, TypeError, ValueError):
            errors.append("period.invalid_date_structure")
    if len(parsed) != len(periods) or not parsed:
        errors.append("period.missing_or_invalid_set")
    if len(set(parsed)) != len(parsed):
        errors.append("period.duplicate_interval")
    if parsed != sorted(parsed, key=lambda pair: (pair[1], pair[0] or pair[1])):
        errors.append("period.nonchronological_order")
    operation = contract.get("operation") or {}
    kind = operation.get("kind")
    if kind in {"arithmetic_mean", "argmax_then_lookup"}:
        if len(parsed) != 3 or any(start is None for start, _ in parsed):
            errors.append("period.expected_three_durations")
        for start, end in parsed:
            if start is not None and not 350 <= (end - start).days + 1 <= 380:
                errors.append("period.not_actual_annual_duration")
    elif kind in {"difference", "relative_change"}:
        if len(parsed) != 2:
            errors.append("period.expected_two_endpoints")
        if operation.get("direction") != "current_minus_previous":
            errors.append("period.wrong_operation_direction")
        if kind == "relative_change" and (
            operation.get("denominator") != "strictly_positive_previous"
            or operation.get("multiplier") != 100
        ):
            errors.append("period.wrong_growth_denominator")
    else:
        errors.append("period.unsupported_operation")
    # Annual durations must touch exactly; an index sequence cannot conceal a
    # gap/overlap. Instant stock endpoints have no asserted duration adjacency.
    for left, right in zip(parsed, parsed[1:], strict=False):
        if left[0] is not None and right[0] is not None:
            if right[0] != left[1] + timedelta(days=1):
                errors.append("period.duration_gap_or_overlap")
        elif (left[0] is None) != (right[0] is None):
            errors.append("period.mixed_instant_duration_target")
        elif right[1] <= left[1]:
            errors.append("period.nonincreasing_instant_endpoints")
    expected = {
        (metric, start.isoformat() if start else None, end.isoformat())
        for metric in contract.get("metric_ids") or []
        for start, end in parsed
    }
    found = set()
    for native in native_bindings.values():
        if native.get("source_cluster") != contract.get("source_cluster"):
            continue
        raw = native.get("record") or {}
        found.add((native.get("metric_id"), raw.get("start"), raw.get("end")))
    if not expected or not expected.issubset(found):
        errors.append("period.native_metric_interval_not_found")
    if canonical_target is not None:
        raw_pairs = canonical_target.get("actual_periods")
        if raw_pairs is None:
            raw_pairs = [
                canonical_target.get("previous_period"),
                canonical_target.get("current_period"),
            ]
        actual_pairs = [[p.get("start"), p.get("end")] for p in periods]
        if actual_pairs != [list(pair) if pair is not None else None for pair in raw_pairs]:
            errors.append("period.canonical_target_period_set_changed")
        if contract.get("quantity") != canonical_target.get("quantity"):
            errors.append("period.canonical_target_quantity_changed")
        metrics = canonical_target.get("metric_ids") or [canonical_target.get("metric_id")]
        if contract.get("metric_ids") != metrics:
            errors.append("period.canonical_target_metrics_changed")
        expected_kinds = {
            "three_annual_flow_mean": "arithmetic_mean",
            "three_year_peak_then_same_period_metric": "argmax_then_lookup",
            "difference": "difference",
            "relative_change": "relative_change",
        }
        if kind != expected_kinds.get(canonical_target.get("quantity")):
            errors.append("period.canonical_target_operation_changed")
        if kind == "arithmetic_mean" and (
            operation.get("metric_id") != metrics[0] or operation.get("operand_count") != 3
        ):
            errors.append("period.mean_operand_contract_changed")
        if kind == "argmax_then_lookup" and (
            operation.get("primary_metric_id") != metrics[0]
            or operation.get("secondary_metric_id") != metrics[1]
            or operation.get("candidate_count") != 3
            or operation.get("same_actual_period_required") is not True
        ):
            errors.append("period.peak_lookup_contract_changed")
    return sorted(set(errors))


def validate_public_periods(
    messages, contract, native_bindings, final=None, *, canonical_target=None
):
    """Parse saved public bytes/contract separately and compare to native dates.

    This checks the bounded date/operation grammar. It does not certify arbitrary
    free prose, the source values, or a trajectory's mathematical sufficiency.
    """
    errors = _validate_native_contract(contract, native_bindings, canonical_target=canonical_target)
    if isinstance(messages, str):
        text = messages
    else:
        parts = []
        for row in messages:
            content = str(row.get("content") or "")
            try:
                public = json.loads(content)
            except (TypeError, ValueError):
                public = None
            if isinstance(public, dict) and isinstance(public.get("question"), str):
                if public.get("period_contract") != contract:
                    errors.append("period.saved_public_envelope_contract_mismatch")
                parts.append(public["question"])
            else:
                parts.append(content)
        text = "\n".join(parts)
    blocks = re.findall(re.escape(BEGIN) + r"\s*(.*?)\s*" + re.escape(END), text, re.S)
    if len(blocks) != 1:
        errors.append("period.public_contract_count")
    else:
        try:
            saved = json.loads(blocks[0])
            if saved != contract:
                errors.append("period.saved_public_contract_mismatch")
            if saved.get("id"):
                body = {key: value for key, value in saved.items() if key != "id"}
                digest = hashlib.sha256(
                    json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                if saved["id"] != "actual_period_contract:" + digest:
                    errors.append("period.contract_identity_mismatch")
        except (TypeError, ValueError):
            errors.append("period.public_contract_not_json")
    human = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), "", text, flags=re.S)
    observed = re.findall(
        r"^Period (period:(?:duration:\d{4}-\d{2}-\d{2}:|instant:)\d{4}-\d{2}-\d{2}): "
        r"(?:(\d{4}-\d{2}-\d{2}) through (\d{4}-\d{2}-\d{2})|instant at (\d{4}-\d{2}-\d{2}))\.$",
        human,
        re.M,
    )
    parsed_lines = [
        (identifier, start or None, end or instant) for identifier, start, end, instant in observed
    ]
    expected_lines = [(row["period_id"], row["start"], row["end"]) for row in contract["periods"]]
    if parsed_lines != expected_lines:
        errors.append("period.public_human_interval_set_mismatch")
    allowed_dates = {
        value for row in contract["periods"] for value in (row["start"], row["end"]) if value
    }
    stated_dates = set(re.findall(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", human))
    if not stated_dates.issubset(allowed_dates):
        errors.append("period.public_question_contains_other_actual_dates")
    for left, right in re.findall(
        r"(\d{4}-\d{2}-\d{2})\s*(?:through|to|至|/|→)\s*(\d{4}-\d{2}-\d{2})", human, re.IGNORECASE
    ):
        if left > right:
            errors.append("period.public_question_interval_reversed")
    calendar_claim = re.search(r"calendar\s+year|自然年", human, re.I)
    if calendar_claim and any(row["label_basis"] != "calendar_year" for row in contract["periods"]):
        errors.append("period.public_false_calendar_claim")
    if re.search(r"\bFY\s*\d{4}\b|fiscal\s+year\s+\d{4}", human, re.I):
        errors.append("period.public_unproven_fiscal_year_name")
    kind = contract["operation"]["kind"]
    if kind in {"difference", "relative_change"}:
        if not re.search(r"current\s+minus\s+previous", human, re.I):
            errors.append("period.public_direction_missing")
        if re.search(
            r"previous\s+minus\s+current|current\s+(?:is\s+)?(?:the\s+)?earlier", human, re.I
        ):
            errors.append("period.public_direction_reversed")
    if kind == "arithmetic_mean" and not re.search(
        r"arithmetic mean.*all three listed periods", human, re.I
    ):
        errors.append("period.public_mean_set_missing")
    if kind == "argmax_then_lookup":
        if not re.search(r"largest primary-metric.*all three listed periods", human, re.I):
            errors.append("period.public_peak_selection_missing")
        if not re.search(r"secondary metric from that same actual period", human, re.I):
            errors.append("period.public_same_period_lookup_missing")
        if re.search(
            r"lowest|smallest|argmin|minimum|前一期|previous period.*secondary", human, re.I
        ):
            errors.append("period.public_peak_direction_conflict")
    if final is not None:
        errors.extend(validate_final_period(final, contract)["errors"])
    return {
        "passed": not errors,
        "errors": sorted(set(errors)),
        "validator": "independent_saved_public_date_contract.v1",
        "arbitrary_natural_language_certified": False,
        "numeric_or_trajectory_qualification": False,
    }


def validate_final_period(final, contract, expected_period=None):
    """Require exact date identity for peak Final, not a year-index match."""
    if contract["operation"]["kind"] != "argmax_then_lookup":
        return {"passed": True, "applicable": False, "errors": []}
    errors = []
    identifiers = {row["period_id"] for row in contract["periods"]}
    supplied = final.get("period_id")
    actual = final.get("actual_period", final.get("period"))
    if isinstance(actual, dict):
        try:
            full_id = period_identity(
                actual.get("start"), actual["end"], actual.get("period_type", "duration")
            )
            if supplied is not None and supplied != full_id:
                errors.append("period.Final_conflicting_id_and_dates")
            supplied = full_id
        except (KeyError, TypeError, ValueError):
            errors.append("period.Final_invalid_interval")
    elif isinstance(actual, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}", actual):
        try:
            full_id = period_identity(*actual.split("/"))
            if supplied is not None and supplied != full_id:
                errors.append("period.Final_conflicting_id_and_dates")
            supplied = full_id
        except ValueError:
            errors.append("period.Final_invalid_interval")
    elif actual is not None:
        errors.append("period.Final_ambiguous_year_or_period")
    if supplied not in identifiers:
        errors.append("period.Final_not_member_of_public_set")
    if expected_period is not None:
        if isinstance(expected_period, dict):
            expected_period = expected_period.get("period_id") or period_identity(
                expected_period.get("start"),
                expected_period["end"],
                expected_period.get("period_type", "duration"),
            )
        if supplied != expected_period:
            errors.append("period.Final_not_supported_selected_interval")
    return {
        "passed": not errors,
        "applicable": True,
        "errors": sorted(set(errors)),
        "period_id": supplied,
    }
