"""Finite, offline source-and-execution qualification; never a native-score alias.

The public-only applicability path covers an explicit metric and two annual
periods. A separate finite author-anchored path can prove single-period and
original-text derivations. Rules freeze before Probe generation; unsupported
meanings remain unknown, not intrinsically invalid or unsolvable.
No prompt, raw episode, reference, scorer, or model is changed by this module.
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any

from .contracts import Episode, PublicTask, TaskBundle, digest

RULE_VERSION = "finqa_table_grounded_qualification_v1"


class _Unknown(ValueError):
    pass


class _Invalid(ValueError):
    pass


def qualification_rules(*, harness_id="bigfinance-derived-vtdo-v3") -> dict[str, Any]:
    body = {
        "version": RULE_VERSION,
        "scope": (
            "public explicit-period applicability or uniquely source-bound "
            "author-anchored derivation"
        ),
        "supported_question_relations": ["from YEAR to YEAR", "ratio ... YEAR to ... YEAR"],
        "supported_program_ops": ["add", "subtract", "multiply", "divide"],
        "source_policy": (
            "Unique exact normalized metric row and year columns; numeric period values distinct; "
            "currency/scale explicit in table header, row or global public amounts declaration. "
            "This narrow public-only applicability path does not infer text evidence or periods. "
            "The separate author-anchored path below may prove original text sources."
        ),
        "private_reference_policy": (
            "Author table_i anchor plus program must agree with independently bound question/table "
            "dependency, OR an author-anchored derivation must bind every data leaf uniquely to "
            "original table/text with explicit metric, period and compatible unit evidence. "
            "Author labels are trusted task-semantics evidence, not universal proof of all legal "
            "solutions. Reference disagreement or unsupported alternatives remain unknown."
        ),
        "actual_history_policy": (
            "SFT role only; complete original public request/response history and settled real "
            "provenance; replay every original tool call, including errors, byte-for-byte. "
            "No removed prefix, inferred call, replacement output or extra prose claims."
        ),
        "numerical_policy": (
            "Program must have the proved source dependency; Final and actual calculation must "
            "be compatible after explicit declared scale conversion and official five-place "
            "rounding, not an adjustable tolerance. Native metrics are not rewritten."
        ),
        "delivery_policy": (
            "A source-proved declarative Final program may pass without online calculate. "
            "Offline program execution is explicitly separate from actual tool execution."
        ),
        "outside_scope": "unknown, never an inferred CompletePass",
        "known_contradiction": "invalid, retained in the original inventory",
        "collection_policy": (
            "Freeze rules first; only after all slots in the explicitly preregistered study "
            "scope (8 per task) complete does the inventory "
            "controller assess the whole batch. "
            "Six train and two sealed slots never exchange roles. "
            "Single-episode output is a candidate decision, not material-pool admission."
        ),
        "no_LLM_judge_or_gold_to_prompt": True,
        "no_outcome_based_rule_selection": True,
        "author_path_unit_policy": (
            "An unlabelled same-metric table row may carry one shared opaque unit, cancellable "
            "only in a same-unit ratio. No guessed USD, amount Final, cross-metric cancellation "
            "or conflicting column/text scales. Percent/currency/count conversions are explicit."
        ),
        "source_equivalence": (
            "same bound numeric leaves and canonical dependency DAG, not merely equal_program "
            "or equal final value; commutative and associative add/multiply order ignored"
        ),
        "author_path_operations": [
            "add",
            "subtract",
            "multiply",
            "divide",
            "table_sum",
            "table_average",
            "table_max",
            "table_min",
        ],
        "author_path_limits": (
            "32 linear steps; exact author evidence text/row binding; unique data leaf match"
        ),
    }
    if harness_id == "bigfinance-derived-vtdo-v4":
        body.update(
            previous_financial_rule_id="finqa_qualification:" + digest(body),
            execution_protocol_binding={
                "harness_id": harness_id,
                "submission_profile": "finqa_program_v3_structured",
                "system_and_tools": "same shared selectors as live execution",
                "public_content": "empty/null; noncompliance retained, never removed",
                "financial_DAG_source_unit_Final_and_Mapper_rules_changed": False,
            },
        )
    elif harness_id != "bigfinance-derived-vtdo-v3":
        raise ValueError("unsupported material execution protocol")
    return {**body, "id": "finqa_qualification:" + digest(body)}


def _norm(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _numeric(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise _Unknown("non_numeric_value")
    text = str(value).strip().replace("−", "-")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    text = text.replace("$", "").strip()
    if re.fullmatch(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", text):
        text = text.replace(",", "")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise _Unknown("non_numeric_value") from exc
    if not number.is_finite():
        raise _Unknown("non_finite_number")
    return number


def _currency_declaration(text: str) -> tuple[str, int] | None:
    lowered = text.casefold()
    if re.search(r"\b(?:EUR|GBP|JPY|CNY|CAD|AUD|HKD|euros?|pounds?|yen|yuan)\b", text, re.I):
        raise _Unknown("unsupported_currency_conversion_or_currency_ambiguity")
    if not re.search(r"\busd\b|\bu\.?s\.? dollars?\b|\bdollars?\b|\$", lowered):
        return None
    scales = [
        power
        for word, power in (("thousand", 3), ("million", 6), ("billion", 9))
        if re.search(r"\b" + word + r"s?\b", lowered)
    ]
    if len(scales) > 1:
        raise _Unknown("ambiguous_source_scale")
    # Non-USD dollar currencies and per-share quantities need a separate rule.
    if re.search(r"\b(?:canadian|australian|hong kong|singapore)\b|per share", lowered):
        raise _Unknown("unsupported_currency_or_per_share_unit")
    currency = "USD" if re.search(r"\busd\b|\bu\.?s\.? dollars?\b", lowered) else "declared_dollar"
    return currency, scales[0] if scales else 0


def _public_basis(task: PublicTask) -> dict[str, Any]:
    if task.dataset != "finqa":
        raise _Unknown("unsupported_dataset")
    tables = [source for source in task.sources if source.kind == "table"]
    if len(tables) != 1 or tables[0].locator != "table":
        raise _Unknown("requires_one_original_table")
    source, question = tables[0], task.question
    table = source.content
    if not isinstance(table, list) or len(table) < 2:
        raise _Unknown("empty_or_unsupported_table")
    years = re.findall(r"\b(?:19|20)\d{2}\b", question)
    if len(years) != 2 or len(set(years)) != 2:
        raise _Unknown("requires_two_explicit_distinct_question_years")
    if re.search(r"\bquarter|\bmonths?\b|\bq[1-4]\b", question, re.I):
        raise _Unknown("subannual_period_not_proved")
    lower = question.casefold()
    if "ratio" in lower and re.search(
        r"\b" + years[0] + r"\b.+?\bto\b.+?\b" + years[1] + r"\b", lower
    ):
        relation, mode = "ratio", "ratio"
    elif re.search(r"\bfrom\s+" + years[0] + r"\s+to\s+" + years[1] + r"\b", lower):
        relation = "from_to"
        if not re.search(r"\b(?:change|increase|decrease|difference)\b", lower):
            raise _Unknown("question_operation_not_explicit")
        mode = "decrease" if re.search(r"\bdecrease\b", lower) else "change"
        if re.search(r"\b(?:percentage|percent|relative)\b", lower):
            mode = "relative_" + mode
    else:
        raise _Unknown("question_period_relation_outside_finite_grammar")
    columns = []
    for year in years:
        matching = [index for index, cell in enumerate(table[0]) if cell.strip() == year]
        if len(matching) != 1:
            raise _Unknown("annual_header_not_unique_exact_year")
        columns.append(matching[0])
    question_words = " " + _norm(question) + " "
    matching_rows = []
    for index, row in enumerate(table[1:], start=1):
        if not row:
            continue
        label = re.sub(
            r"\([^)]*(?:million|thousand|billion|usd|dollar)[^)]*\)", "", row[0], flags=re.I
        )
        metric = _norm(label)
        if metric and " " + metric + " " in question_words:
            matching_rows.append((index, metric))
    if len(matching_rows) != 1:
        raise _Unknown("question_metric_row_not_unique_exact_match")
    row, metric = matching_rows[0]
    if any(column == 0 or column >= len(table[row]) for column in columns):
        raise _Unknown("target_table_cell_missing")
    values = [_numeric(table[row][column]) for column in columns]
    if values[0] == values[1]:
        raise _Unknown("equal_period_values_have_ambiguous_bare_numeric_binding")
    declarations = [("table_header", str(table[0][0])), ("metric_row", str(table[row][0]))]
    for item in task.sources:
        if item.kind == "text" and re.search(
            r"\b(?:all amounts|all figures|all values|amounts)\s+(?:are\s+)?(?:stated\s+)?in\b",
            item.content,
            re.I,
        ):
            declarations.append((item.source_id, item.content))
    declared = [(where, text, _currency_declaration(text)) for where, text in declarations]
    declared = [item for item in declared if item[2] is not None]
    units = {unit for _, _, unit in declared}
    if not units and all("$" in table[row][column] for column in columns):
        units = {("USD", 0)}
        declared = [("target_cells", "explicit dollar symbols", ("USD", 0))]
    if len(units) != 1:
        raise _Unknown("source_currency_scale_not_uniquely_declared")
    currency, power = units.pop()
    output_unit = _currency_declaration(question)
    if output_unit is not None and output_unit != (currency, power):
        raise _Unknown("question_requests_different_currency_scale")
    return {
        "source_id": source.source_id,
        "source_sha256": digest(source),
        "metric": metric,
        "row": row,
        "row_label": table[row][0],
        "years": years,
        "columns": columns,
        "cells": [
            {
                "source_id": source.source_id,
                "row": row,
                "column": column,
                "year": year,
                "raw": table[row][column],
                "numeric": str(value),
            }
            for year, column, value in zip(years, columns, values, strict=True)
        ],
        "relation": relation,
        "operation": mode,
        "source_unit": {"currency": currency, "power10": power},
        "unit_declarations": [{"location": where, "text": text} for where, text, _ in declared],
        "support_is_proved_public_availability_not_a_claim_about_model_mental_origin": True,
    }


def task_support_check(value: TaskBundle | PublicTask) -> dict[str, Any]:
    """Static applicability only: never reads or selects Probe outcomes or drops tasks."""
    task = value.public if isinstance(value, TaskBundle) else value
    if not isinstance(task, PublicTask):
        raise TypeError("task_support_check requires an original PublicTask or TaskBundle")
    public = {}
    try:
        public.update(status="public_potential", basis=_public_basis(task))
    except _Unknown as error:
        public.update(status="private_evidence_required", reason=str(error))
    result = {
        "task_id": task.task_id,
        "public_structure": public,
        "qualification_rule_id": qualification_rules()["id"],
        "no_probe_outcome_examined": True,
        "material_admission": False,
    }
    if not isinstance(value, TaskBundle):
        return {**result, "status": public["status"], "private_reference_check_pending": True}
    try:
        basis = _author_basis(value)
    except (_Unknown, _Invalid) as error:
        return {
            **result,
            "status": "unknown",
            "reason": str(error),
            "private_reference_check_pending": False,
        }
    return {
        **result,
        "status": "author_anchored_supported",
        "basis": basis,
        "private_reference_check_pending": False,
    }


def _unit(task, row_label, header, raw):
    if re.search(r"\bper share\b", row_label, re.I):
        raise _Unknown("per_share_unit_outside_finite_domain")
    if (raw.strip().endswith("%") or re.search(r"\bpercent(?:age)?\b|%", row_label)) and "$" in raw:
        raise _Unknown("source_cell_has_conflicting_percent_and_currency")
    if raw.strip().endswith("%") or re.search(r"\bpercent(?:age)?\b|%", row_label):
        return {"kind": "percent", "power10": -2}
    declarations = [header, row_label]
    declarations += [
        s.content
        for s in task.sources
        if s.kind == "text"
        and (
            (_norm(row_label) and _norm(row_label) in _norm(s.content))
            or re.search(
                r"\b(?:all amounts|all figures|all values|amounts)\s+(?:are\s+)?(?:stated\s+)?in\b",
                s.content,
                re.I,
            )
        )
    ]
    scales = {
        power
        for text in declarations
        for word, power in (("thousand", 3), ("million", 6), ("billion", 9))
        if re.search(r"\b" + word + r"s?\b", text, re.I)
    }
    if len(scales) > 1:
        raise _Unknown("mixed_public_source_scales_not_proved")
    power = next(iter(scales)) if scales else 0
    if re.search(
        r"\bnumber of shares\b|\bshares outstanding\b|\bweighted.*\bshares\b", row_label, re.I
    ):
        if "$" in raw:
            raise _Unknown("share_count_conflicts_with_currency_cell")
        return {"kind": "count:shares", "power10": power}
    units = {_currency_declaration(text) for text in declarations}
    units.discard(None)
    if len(units) > 1:
        raise _Unknown("ambiguous_source_unit_or_scale")
    if units:
        currency, power = units.pop()
        return {"kind": "currency:" + currency, "power10": power}
    if "$" in raw:
        return {"kind": "currency:declared_dollar", "power10": 0}
    if re.search(r"\b(?:number of|employees|headcount)\b", row_label, re.I):
        return {"kind": "count:" + _norm(row_label), "power10": power}
    # Same-row ratios can cancel this unknown common unit. It cannot certify a
    # monetary/amount Final or cross-metric addition/ratio by mere numeric match.
    return {"kind": "opaque_metric:" + _norm(row_label), "power10": power}


def _canon(op, *args):
    if op in {"add", "multiply", "min", "max"}:
        flat = []
        for arg in args:
            flat.extend(arg[1:] if arg[0] == op else [arg])
        args = tuple(sorted(flat, key=repr))
    return (op, *args)


def _source_bindings(bundle):
    task = bundle.public
    gold = bundle.reference.annotations.get("gold_inds")
    if not isinstance(gold, dict) or not gold:
        raise _Unknown("author_evidence_anchors_missing")
    tables = [s for s in task.sources if s.kind == "table" and s.locator == "table"]
    if len(tables) != 1:
        raise _Unknown("original_table_not_unique")
    table_source, bindings, rows = tables[0], {}, {}
    table = table_source.content
    anchors = []
    for key, text in gold.items():
        if not isinstance(text, str) or not text.strip():
            raise _Unknown("author_evidence_text_missing")
        table_match = re.fullmatch(r"table_(\d+)", key)
        if table_match:
            row_index = int(table_match[1])
            if (
                not 0 < row_index < len(table)
                or not table[row_index]
                or not _norm(table[row_index][0])
            ):
                raise _Unknown("author_table_anchor_outside_original_table")
            label = table[row_index][0]
            if _norm(label) not in _norm(text):
                raise _Unknown("author_table_anchor_text_does_not_bind_row_label")
            ids = []
            for col, raw in enumerate(table[row_index][1:], start=1):
                if col >= len(table[0]) or not table[0][col].strip():
                    continue
                try:
                    value = _numeric(raw.rstrip("%"))
                except _Unknown:
                    continue
                period = table[0][col]
                if not re.search(r"\b(?:19|20)\d{2}\b", period):
                    continue
                binding = {
                    "source_id": table_source.source_id,
                    "source_sha256": digest(table_source),
                    "row": row_index,
                    "column": col,
                    "metric": label,
                    "period": period,
                    "raw": raw,
                    "numeric": str(value),
                    "unit": _unit(task, label, table[0][0] + " " + period, raw),
                    "anchor": key,
                    "source_type": "table",
                }
                ident = digest(binding)
                bindings[ident] = binding
                ids.append(ident)
            # Aggregates cover the *whole* original numeric row. A nonannual or
            # unparseable cell may not silently disappear from its dependency.
            rows[label] = (
                ids
                if (
                    len(ids) == len(table[row_index]) - 1
                    and sum(bool(row) and row[0] == label for row in table[1:]) == 1
                )
                else []
            )
            anchors.append(
                {"anchor": key, "public_source_id": table_source.source_id, "row": row_index}
            )
        elif key.startswith("text_"):
            matches = [
                s
                for s in task.sources
                if s.kind == "text" and " ".join(s.content.split()) == " ".join(text.split())
            ]
            if len(matches) != 1:
                raise _Unknown("author_text_anchor_not_unique_exact_public_text")
            source = matches[0]
            has_currency = _currency_declaration(source.content) is not None
            has_percent = bool(re.search(r"%|\bpercent(?:age)?\b", source.content, re.I))
            has_count = bool(
                re.search(
                    r"\b\d+(?:\.\d+)?\s+(?:days?|months?|years?|shares?|employees|people|units?)\b",
                    source.content,
                    re.I,
                )
            )
            if sum((has_currency, has_percent, has_count)) > 1:
                raise _Unknown("mixed_text_units_require_finer_author_evidence")
            years = set(re.findall(r"\b(?:19|20)\d{2}\b", source.content))
            if len(years) != 1:
                raise _Unknown("text_evidence_period_not_unique")
            period = next(iter(years))
            for match in re.finditer(
                r"(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?", source.content
            ):
                raw = match.group()
                if raw == period:
                    continue
                value = _numeric(raw.rstrip("%"))
                local = source.content[max(0, match.start() - 1) : match.end() + 1]
                unit = _unit(task, source.content, source.content, raw if "%" in raw else local)
                if unit["kind"].startswith("opaque_metric:"):
                    raise _Unknown("text_numeric_unit_not_explicit")
                binding = {
                    "source_id": source.source_id,
                    "source_sha256": digest(source),
                    "row": -1,
                    "column": match.start(),
                    "metric": source.content,
                    "period": period,
                    "raw": raw,
                    "numeric": str(value),
                    "unit": unit,
                    "anchor": key,
                    "source_type": "text",
                    "span": [match.start(), match.end()],
                }
                bindings[digest(binding)] = binding
            anchors.append({"anchor": key, "public_source_id": source.source_id})
        else:
            raise _Unknown("unsupported_author_evidence_anchor_kind")
    if not bindings:
        raise _Unknown("no_source_bound_numeric_leaf")
    return bindings, rows, anchors


def _operand(value, bindings, previous):
    if value.startswith("#"):
        try:
            index = int(value[1:])
            if index < 0:
                raise ValueError()
            return previous[index]
        except (ValueError, IndexError) as exc:
            raise _Invalid("invalid_program_step_reference") from exc
    if value.startswith("const_"):
        number = _numeric("-1" if value == "const_m1" else value[6:])
        return ("constant", str(Fraction(number)))
    number = _numeric(value.rstrip("%")) / (100 if value.endswith("%") else 1)
    matches = []
    for key, binding in bindings.items():
        if _numeric(binding["numeric"]) == number:
            matches.append(("leaf", key))
        if binding["unit"]["kind"] == "percent" and _numeric(binding["numeric"]) / 100 == number:
            matches.append(("percent_as_ratio", ("leaf", key)))
    if len(matches) != 1:
        raise _Unknown("numeric_leaf_missing_or_ambiguous_in_author_sources")
    return matches[0]


def _program_dag(program, bindings, rows):
    from .native_metrics import _load_finqa_scorer, _program_tokens

    scorer = _load_finqa_scorer()
    tokens = _program_tokens(program, scorer)
    if tokens is None:
        raise _Invalid("invalid_program_structure")
    if (len(tokens) - 1) // 4 > 32:
        raise _Unknown("qualification_program_step_limit")
    steps = []
    for offset in range(0, len(tokens) - 1, 4):
        op, left, right, _ = tokens[offset : offset + 4]
        op = op[:-1]
        if op in {"add", "subtract", "multiply", "divide"}:
            steps.append(
                _canon(op, _operand(left, bindings, steps), _operand(right, bindings, steps))
            )
        elif op in {"table_sum", "table_average", "table_min", "table_max"}:
            cells = rows.get(left, [])
            if not cells:
                raise _Unknown("table_aggregate_not_bound_to_author_row")
            leaves = [("leaf", key) for key in cells]
            leaves = [
                ("percent_as_ratio", node)
                if bindings[node[1]]["unit"]["kind"] == "percent"
                else node
                for node in leaves
            ]
            operation = {
                "table_sum": "add",
                "table_average": "add",
                "table_min": "min",
                "table_max": "max",
            }[op]
            node = _canon(operation, *leaves)
            if op == "table_average":
                node = _canon("divide", node, ("constant", str(len(leaves))))
            steps.append(node)
        else:
            raise _Unknown("program_operation_outside_registered_qualification_scope")
    return steps[-1], steps


def _leaves(node):
    if node[0] == "leaf":
        return {node[1]}
    if node[0] == "constant":
        return set()
    return set().union(*(_leaves(child) for child in node[1:]))


def _dag_unit(node, bindings, question):
    if node[0] == "leaf":
        return bindings[node[1]]["unit"]
    if node[0] in {"constant", "percent_as_ratio"}:
        return {"kind": "ratio", "power10": 0}
    units = [_dag_unit(child, bindings, question) for child in node[1:]]
    if node[0] in {"add", "subtract", "min", "max"}:
        if node[0] in {"add", "subtract"}:
            units = [
                unit
                for child, unit in zip(node[1:], units, strict=True)
                if child != ("constant", "0")
            ]
            if not units:
                return {"kind": "ratio", "power10": 0}
        if any(unit != units[0] for unit in units):
            raise _Unknown("incompatible_or_unproved_operand_units")
        return units[0]
    if node[0] == "divide":
        if node[2][0] == "constant":
            if units[0]["kind"] == "percent" and Fraction(node[2][1]) == 100:
                return {"kind": "ratio", "power10": 0}
            return units[0]
        if units[0] == units[1]:
            return {"kind": "ratio", "power10": 0}
        raise _Unknown("unproved_ratio_dimension_or_scale")
    nonconstant = [
        (child, unit) for child, unit in zip(node[1:], units, strict=True) if child[0] != "constant"
    ]
    if len(nonconstant) == 1:
        unit = nonconstant[0][1]
        constants = [Fraction(child[1]) for child in node[1:] if child[0] == "constant"]
        if (
            unit["kind"] == "ratio"
            and constants == [Fraction(100)]
            and re.search(r"\bpercent(?:age)?\b", question, re.I)
        ):
            return {"kind": "percent", "power10": -2}
        return unit
    raise _Unknown("compound_product_unit_outside_finite_domain")


def _author_basis(bundle):
    from .native_metrics import _load_finqa_scorer, _program_tokens, metric_provenance

    if bundle.public.dataset != "finqa":
        raise _Unknown("unsupported_dataset")
    metric_provenance()
    bindings, rows, anchors = _source_bindings(bundle)
    dag, steps = _program_dag(bundle.reference.program, bindings, rows)
    used = _leaves(dag)
    if not used:
        raise _Unknown("constant_only_author_program_has_no_source_proof")
    selected = {key: bindings[key] for key in sorted(used)}
    question_terms = set(_norm(bundle.public.question).split()) - {
        "what",
        "was",
        "were",
        "is",
        "the",
        "of",
        "in",
        "and",
        "to",
        "a",
        "for",
        "from",
        "total",
        "net",
        "other",
        "year",
        "years",
        "amount",
        "percentage",
        "percent",
        "change",
    }
    metric_terms = set().union(*(set(_norm(b["metric"]).split()) for b in selected.values()))
    shared = sorted(
        (question_terms & metric_terms) - set(re.findall(r"\d+", bundle.public.question))
    )
    if not shared:
        raise _Unknown("question_metric_not_corroborated_in_author_source_context")
    question_years = set(re.findall(r"\b(?:19|20)\d{2}\b", bundle.public.question))
    source_years = set().union(
        *(set(re.findall(r"\b(?:19|20)\d{2}\b", b["period"])) for b in selected.values())
    )
    if not question_years <= source_years:
        raise _Unknown("explicit_question_period_not_in_bound_evidence")
    unit = _dag_unit(dag, bindings, bundle.public.question)
    if unit["kind"].startswith("opaque_metric:"):
        raise _Unknown("final_quantity_unit_or_scale_not_proved")
    scorer = _load_finqa_scorer()
    table = next(s.content for s in bundle.public.sources if s.locator == "table")
    invalid, result = scorer.eval_program(_program_tokens(bundle.reference.program, scorer), table)
    if invalid or result != bundle.reference.answer:
        raise _Unknown("reference_program_public_execution_contradicts_author_answer")
    return {
        "bindings": bindings,
        "rows": rows,
        "anchors": anchors,
        "used_bindings": selected,
        "dependency_DAG": dag,
        "program_steps": steps,
        "program_result": result,
        "result_unit": unit,
        "question_metric_terms": shared,
        "question_years": sorted(question_years),
        "source_years": sorted(source_years),
        "author_program_sha256": digest(bundle.reference.program),
        "author_task_semantics_trusted_but_extra_source_period_unit_proofs_required": True,
    }


def _replay_episode(bundle, episode):
    from .contracts import invocation_identity, invocation_scope
    from .encoding import probe_generation_record
    from .harness import episode_tool_specs, system_message
    from .materials import _training_rows
    from .profiles import public_run_view
    from .providers import _api_messages, canonical_assistant_message
    from .settlement import episode_is_complete
    from .tools import VISIBLE_REFERENCE_PROTOCOL, PublicToolSession

    if episode.config.role != "sft" or bundle.lineage.original_split != "train":
        raise _Unknown("qualification_requires_original_train_SFT_role")
    if (episode.config.harness_id, episode.config.submission_profile) not in {
        ("bigfinance-derived-vtdo-v3", "finqa_program_v2"),
        ("bigfinance-derived-vtdo-v4", "finqa_program_v3_structured"),
    }:
        raise _Unknown("unsupported_frozen_material_execution_protocol")
    if not episode_is_complete(episode):
        raise _Unknown("generation_or_call_settlement_incomplete")
    if episode.stop_reason != "final_answer" or episode.final_answer is None:
        raise _Invalid("normal_terminal_has_no_completed_Final")
    task = public_run_view(bundle.public, episode.config.submission_profile)
    if (episode.dataset, episode.task_id, episode.public_task_sha256) != (
        task.dataset,
        task.task_id,
        digest(task),
    ):
        raise _Invalid("episode_original_public_task_binding_mismatch")
    if episode.provider.backend == "deepseek_api":
        try:
            origin = probe_generation_record(episode)
        except ValueError as exc:
            if any(word in str(exc) for word in ("mismatch", "dropped, altered", "disagree")):
                raise _Invalid("original_API_response_or_failure_history_contradiction") from exc
            raise _Unknown("real_API_provenance_or_full_history_not_validated") from exc
        requests = origin.public_requests
        provenance = {"kind": "API_Probe", "record_id": origin.generation_record_id}
    elif episode.provider.backend == "local_torch":
        try:
            _training_rows(episode)
        except ValueError as exc:
            raise _Unknown("real_local_token_or_full_history_not_validated") from exc
        requests = [turn.provider_metadata.get("request", {}) for turn in episode.turns]
        provenance = {
            "kind": "actual_local_tokens",
            "turn_receipt_sha256": [digest(t.receipt) for t in episode.turns],
        }
    else:
        raise _Unknown("non_real_Probe_backend_cannot_mint_training_material")
    if len(episode.turns) != len(episode.tool_events):
        raise _Invalid("actual_tool_event_sequence_is_incomplete")
    scope = invocation_scope(episode.turns[0].provider_metadata.get("harness_invocation"))
    session = PublicToolSession(
        task, reference_protocol=VISIBLE_REFERENCE_PROTOCOL, invocation_context=scope
    )
    history = [
        system_message(episode.config),
        {
            "role": "user",
            "content": json.dumps(
                task.model_dump(mode="json"), ensure_ascii=False, allow_nan=False
            ),
        },
    ]
    replay = []
    expected_tools = episode_tool_specs(episode.config)
    for index, (turn, event, request) in enumerate(
        zip(episode.turns, episode.tool_events, requests, strict=True)
    ):
        if len(turn.tool_calls) != 1:
            raise _Invalid("completed_SFT_turn_does_not_have_one_actual_tool_action")
        if request.get("tools") != expected_tools:
            raise _Invalid("registered_public_tool_schema_changed")
        if request.get("messages") != (
            _api_messages(history) if episode.provider.backend == "deepseek_api" else history
        ):
            raise _Invalid("original_initial_context_or_failure_history_changed")
        invocation = turn.provider_metadata.get("harness_invocation", {})
        expected = invocation_identity(scope, turn_index=index)
        if any(invocation.get(key) != value for key, value in expected.items()):
            raise _Invalid("model_invocation_coordinates_changed")
        actual_call = turn.tool_calls[0]
        if episode.provider.backend == "deepseek_api":
            raw_call = turn.provider_metadata["api_response"]["choices"][0]["message"][
                "tool_calls"
            ][0]
            if raw_call.get("id") != actual_call.call_id:
                raise _Invalid("raw_API_tool_identity_mismatch")
        tool_id = invocation_identity(scope, turn_index=index, tool_index=0)["invocation_id"]
        rebuilt = session.execute(actual_call, invocation_id=tool_id)
        if rebuilt.model_dump(mode="json") != event.model_dump(mode="json"):
            raise _Invalid("actual_tool_execution_does_not_replay_byte_for_byte")
        assistant = canonical_assistant_message(turn)
        if assistant.get("content", "").strip():
            raise _Unknown("additional_free_text_claims_not_semantically_verified")
        if actual_call.name == "final_answer" and not event.is_error:
            if index != len(episode.turns) - 1 or event.raw_output != {
                "answer": episode.final_answer,
                "scale": episode.final_scale,
                "program": episode.final_program,
            }:
                raise _Invalid("first_successful_Final_or_episode_delivery_changed")
        history += [
            assistant,
            {"role": "tool", "tool_call_id": actual_call.call_id, "content": event.visible_output},
        ]
        replay.append(
            {
                "turn_index": index,
                "call_id": actual_call.call_id,
                "tool_invocation_id": tool_id,
                "event_sha256": digest(event),
                "raw_arguments_sha256": digest(actual_call.raw_arguments),
                "input_output_visible_bytes_identical": True,
                "is_error": event.is_error,
            }
        )
    if list(episode.messages) != history:
        raise _Invalid("final_full_original_history_mismatch")
    return {
        "provenance": provenance,
        "tool_events": replay,
        "full_failed_prefix_retained": True,
        "online_calls_added": 0,
        "replay_is_offline_deterministic_not_new_Student_execution": True,
    }


def _descendants(node):
    result = {node}
    if node[0] not in {"constant", "leaf"}:
        for child in node[1:]:
            result.update(_descendants(child))
    return result


def _necessary_dependency(node, root):
    for ancestor in _descendants(root):
        if node == ancestor:
            return True
        if node[0] in {"add", "multiply"} and ancestor[0] == node[0]:
            if not (Counter(node[1:]) - Counter(ancestor[1:])):
                return True
    return False


def _calc_dag(event, basis, previous, calc_nodes):
    original = event.normalized_arguments

    def bind(value):
        if isinstance(value, str) and value.startswith("prev:"):
            parts = value[5:].split(".")
            source = previous.get(parts[0])
            if source is None or source.is_error:
                raise _Invalid("successful_calculation_depends_on_unavailable_result")
            if source.name == "calculate" and parts[1:] == ["output", "result"]:
                if parts[0] not in calc_nodes:
                    raise _Unknown("calculation_depends_on_unproved_calculation")
                return calc_nodes[parts[0]]
            if (
                source.name == "read_source"
                and len(parts) == 5
                and parts[1:3] == ["output", "content"]
            ):
                try:
                    row, col = int(parts[3]), int(parts[4])
                except ValueError as exc:
                    raise _Unknown("unsupported_non_numeric_source_path") from exc
                matches = [
                    key
                    for key, binding in basis["bindings"].items()
                    if (
                        binding["source_type"] == "table"
                        and binding["source_id"] == source.raw_output["source_id"]
                        and binding["row"] == row
                        and binding["column"] == col
                    )
                ]
                if len(matches) != 1:
                    raise _Unknown("actual_source_path_outside_proved_author_evidence")
                return ("leaf", matches[0])
            raise _Unknown("source_reference_not_in_finite_numeric_binding_domain")
        text = str(value)
        try:
            return _operand(text, basis["bindings"], [])
        except _Unknown:
            number = _numeric(value)
            source_matches = [
                b
                for b in basis["bindings"].values()
                if _numeric(b["numeric"]) == number
                or (b["unit"]["kind"] == "percent" and _numeric(b["numeric"]) / 100 == number)
            ]
            if not source_matches and number in {
                Decimal(0),
                Decimal(1),
                Decimal(-1),
                Decimal(100),
                Decimal(1000),
            }:
                return ("constant", str(Fraction(_numeric(value))))
            raise

    names = {name: bind(value) for name, value in original.get("variables", {}).items()}
    expression = original["expression"]
    ops = {ast.Add: "add", ast.Sub: "subtract", ast.Mult: "multiply", ast.Div: "divide"}

    def walk(node):
        if isinstance(node, ast.Name) and node.id in names:
            return names[node.id]
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return bind(ast.get_source_segment(expression, node))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return _canon("multiply", ("constant", "-1"), walk(node.operand))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
            return walk(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return _canon(ops[type(node.op)], walk(node.left), walk(node.right))
        raise _Unknown("actual_calculation_outside_finite_dependency_domain")

    return walk(ast.parse(expression, mode="eval").body)


def _expression_shape(expression):
    try:
        tree = ast.parse(expression, mode="eval")
    except (TypeError, ValueError, SyntaxError):
        return None
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.setdefault(node.id, "v" + str(len(names)))
            node.id = names[node.id]
    return ast.dump(tree, include_attributes=False)


def _compatible_final(episode, basis):
    value = episode.final_answer
    if isinstance(value, (dict, list, bool)):
        raise _Unknown("non_scalar_Final_outside_numerical_qualification")
    embedded_percent = isinstance(value, str) and value.strip().endswith("%")
    embedded_currency = isinstance(value, str) and "$" in value
    if embedded_percent:
        value = value.strip()[:-1]
    number = _numeric(value)
    unit = basis["result_unit"]
    scale = episode.final_scale.strip().casefold()
    if embedded_currency and not unit["kind"].startswith("currency:"):
        raise _Invalid("Final_currency_symbol_conflicts_with_proved_quantity_dimension")
    if embedded_currency and not scale and unit["power10"] != 0:
        raise _Unknown("Final_currency_symbol_has_unstated_magnitude_scale")
    if unit["kind"] in {"ratio", "percent"}:
        if scale not in {"", "1", "ratio", "percent", "percentage", "%"}:
            raise _Unknown("undeclared_Final_dimensionless_scale")
        final_percent = embedded_percent or scale in {"percent", "percentage", "%"}
        if embedded_percent and scale in {"ratio", "1"}:
            raise _Invalid("Final_percent_symbol_conflicts_with_explicit_ratio_scale")
        if not scale and not embedded_percent:
            final_percent = unit["kind"] == "percent"
        converted = number * (Decimal("0.01") if final_percent else 1)
        converted /= Decimal(10) ** unit["power10"]
    elif unit["kind"].startswith("currency:"):
        if embedded_percent:
            raise _Invalid("monetary_Final_claims_percent")
        powers = {
            "": unit["power10"],
            "usd": 0,
            "dollar": 0,
            "dollars": 0,
            "thousand": 3,
            "thousands": 3,
            "million": 6,
            "millions": 6,
            "billion": 9,
            "billions": 9,
        }
        if scale not in powers:
            raise _Unknown("Final_currency_scale_outside_finite_policy")
        if scale == "usd" and unit["kind"] != "currency:USD":
            raise _Unknown("Final_USD_not_proved_by_generic_dollar_source")
        converted = number * Decimal(10) ** (powers[scale] - unit["power10"])
    elif unit["kind"].startswith("count:") and not embedded_percent:
        if scale == "shares" and unit["kind"] != "count:shares":
            raise _Invalid("Final_share_unit_conflicts_with_other_count")
        powers = {
            "": unit["power10"],
            "1": 0,
            "shares": 0,
            "thousand": 3,
            "thousands": 3,
            "million": 6,
            "millions": 6,
            "billion": 9,
            "billions": 9,
        }
        if scale not in powers:
            raise _Unknown("Final_count_scale_outside_finite_policy")
        converted = number * Decimal(10) ** (powers[scale] - unit["power10"])
    else:
        raise _Unknown("Final_unit_not_in_finite_proved_policy")
    # Same finite five-place rounding convention, fixed before collection;
    # this never changes native score or the original raw-exact diagnostic.
    rounded = Decimal(str(round(float(converted), 5)))
    if rounded != Decimal(str(basis["program_result"])):
        raise _Invalid("Final_value_or_declared_scale_contradicts_source_bound_program")
    return {
        "raw_answer": episode.final_answer,
        "raw_scale": episode.final_scale,
        "converted_into_program_units": str(converted),
        "rounded_five_places": str(rounded),
        "raw_native_diagnostic_not_modified": True,
    }


def qualify_episode(
    bundle: TaskBundle, episode: Episode, *, qualification_rule_id=None, mapper_rule_id=None
) -> dict[str, Any]:
    """Return one candidate decision; the inventory enforces the fixed-slot barrier.

    The caller passes registered rule IDs to prevent a rule-version substitution.
    This function does not select slots, freeze supports, normalize task mass,
    publish a material pool or make a model call.
    """
    from .materials import QualificationDecision
    from .native_metrics import _load_finqa_scorer, _program_tokens
    from .state_mapping import map_proved_state, mapper_rules

    rules = qualification_rules(harness_id=episode.config.harness_id)
    mapping = mapper_rules()
    if qualification_rule_id not in (None, rules["id"]) or mapper_rule_id not in (
        None,
        mapping["id"],
    ):
        raise ValueError("qualification/Mapper differs from frozen registration")
    evidence = {
        "schema": "finqa_source_execution_qualification.v1",
        "episode_sha256": digest(episode),
        "task_key": "finqa/" + bundle.public.task_id,
        "public_source_sha256": digest(bundle.public),
        "private_reference_sha256": digest(bundle.reference),
        "qualification_rule_id": rules["id"],
        "mapper_rule_id": mapping["id"],
        "candidate_only_not_material_pool_admission": True,
        "requires_external_whole_collection_barrier": True,
        "checks": {},
    }
    state_id, verdict, reason = None, "unknown", "not_assessed"
    try:
        evidence["checks"]["replay"] = _replay_episode(bundle, episode)
        basis = _author_basis(bundle)
        evidence["checks"]["source_and_author_derivation"] = basis
        scorer = _load_finqa_scorer()
        tokens = _program_tokens(episode.final_program, scorer)
        if tokens is None:
            raise _Invalid("submitted_program_structure_invalid")
        table = next(s.content for s in bundle.public.sources if s.locator == "table")
        invalid, result = scorer.eval_program(tokens, table)
        if invalid:
            raise _Invalid("submitted_program_does_not_execute")
        if result != basis["program_result"]:
            raise _Invalid("submitted_program_result_contradicts_anchored_task")
        dag, steps = _program_dag(episode.final_program, basis["bindings"], basis["rows"])
        if dag != basis["dependency_DAG"] or any(
            not _necessary_dependency(step, dag) for step in steps
        ):
            raise _Unknown("unproved_alternative_or_extra_program_dependency")
        evidence["checks"]["program"] = {
            "actual_submitted_program_sha256": digest(episode.final_program),
            "dependency_DAG": dag,
            "execution_result": result,
            "offline_execution_is_not_online_calculate": True,
        }
        evidence["checks"]["Final"] = _compatible_final(episode, basis)
        previous, calc_nodes, failed_shapes, calc_proof = {}, {}, set(), []
        recovered, executed = False, False
        for event in episode.tool_events:
            if event.name == "calculate":
                shape = _expression_shape(event.normalized_arguments.get("expression"))
                if event.is_error:
                    if shape is not None:
                        failed_shapes.add(shape)
                else:
                    node = _calc_dag(event, basis, previous, calc_nodes)
                    if not _necessary_dependency(node, dag):
                        raise _Unknown("actual_calculation_not_a_proved_required_dependency")
                    calc_nodes[event.result_handle] = node
                    final_node = node == dag
                    executed |= final_node
                    recovered |= node[0] not in {"leaf", "constant"} and shape in failed_shapes
                    calc_proof.append(
                        {
                            "event_sha256": digest(event),
                            "result_handle": event.result_handle,
                            "dependency_DAG": node,
                            "necessary": True,
                            "final_dependency_executed": final_node,
                        }
                    )
            previous[event.result_handle] = event
        evidence["checks"]["actual_calculations"] = calc_proof
        proof = {
            "semantic_obligations_passed": True,
            "source_cells": [
                {"source_id": item["source_id"], "row": item["row"], "column": item["column"]}
                for item in basis["used_bindings"].values()
            ],
            "dependency_DAG": dag,
            "executed_dependency_DAGs": sorted(
                {
                    item["dependency_DAG"]
                    for item in calc_proof
                    if item["dependency_DAG"][0] not in {"leaf", "constant"}
                },
                key=repr,
            ),
            "necessary_recovery": recovered,
            "delivery_mode": "actually_executed_calculation" if executed else "declarative_program",
        }
        state = map_proved_state(episode.task_id, proof)
        evidence["proved_state"] = state
        state_id, verdict, reason = (
            state["state_id"],
            "CompletePass",
            "finite_author_anchored_source_execution_delivery_proved",
        )
    except _Invalid as error:
        verdict, reason = "invalid", str(error)
    except _Unknown as error:
        verdict, reason = "unknown", str(error)
    except (
        ImportError,
        RuntimeError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        OverflowError,
    ) as error:
        verdict, reason = (
            "unknown",
            "qualification_dependency_or_unhandled_evidence: " + type(error).__name__,
        )
    evidence.update(verdict=verdict, reason=reason)
    decision = QualificationDecision(
        episode_sha256=digest(episode),
        task_id=episode.task_id,
        verdict=verdict,
        state_id=state_id,
        evidence_sha256=digest(evidence),
        reason=reason,
    )
    return {
        "decision": decision.model_dump(mode="json"),
        "evidence": evidence,
        "qualification_rule_id": rules["id"],
        "mapper_rule_id": mapping["id"],
    }
