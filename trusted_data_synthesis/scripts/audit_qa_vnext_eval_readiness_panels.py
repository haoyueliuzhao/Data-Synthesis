"""Independent read-only audit of actual-period evaluation panel versions.

Only the standard library is imported: no renderer, period-label function,
native adapter, QA executor, model, or tokenizer can self-certify this audit.
The optional sidecar is created outside the sealed production stage directory.
"""

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

SALT = "basis_task_factory_sources_20260911.v1:"
GROUPS = ("dual_sufficient", "composition_required", "other_financial")
QUOTAS = {"dev": dict.fromkeys(GROUPS, 60), "confirm": dict.fromkeys(GROUPS, 240)}
BEGIN, END = "BEGIN ACTUAL PERIOD CONTRACT", "END ACTUAL PERIOD CONTRACT"
CASH = "cash_and_cash_equivalents"
RESTRICTED = "cash_cash_equivalents_restricted_cash_and_restricted_cash_equivalents"
FLOW_METRICS = tuple(
    "net_cash_provided_by_used_in_" + part + "_activities"
    for part in ("operating", "investing", "financing")
)
METRIC_NAMES = {
    "revenue": "Revenue",
    "gross_profit": "Gross Profit",
    "net_income": "Net Income",
    "operating_income": "Operating Income",
    FLOW_METRICS[0]: "Net Cash Provided by Used in Operating Activities",
    CASH: "Cash and Cash Equivalents",
    RESTRICTED: "Cash, Cash Equivalents, Restricted Cash and Restricted Cash Equivalents",
}
TAGS = {
    "gross_profit": {"GrossProfit"},
    "revenue": {
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "Revenues",
    },
    "cost_of_revenue": {"CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"},
    "net_income": {"NetIncomeLoss"},
    "operating_income": {"OperatingIncomeLoss"},
    CASH: {"CashAndCashEquivalentsAtCarryingValue"},
    RESTRICTED: {"CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"},
    FLOW_METRICS[0]: {"NetCashProvidedByUsedInOperatingActivities"},
    FLOW_METRICS[1]: {"NetCashProvidedByUsedInInvestingActivities"},
    FLOW_METRICS[2]: {"NetCashProvidedByUsedInFinancingActivities"},
    "effect_of_exchange_rate_on_cash_and_cash_equivalents": {
        "EffectOfExchangeRateOnCashAndCashEquivalents"
    },
    "effect_of_exchange_rate_on_cash_including_restricted": {
        "EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    },
    "change_in_cash_including_exchange_rate_effect": {
        "CashAndCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect"
    },
    "change_in_cash_including_restricted_and_exchange_rate_effect": {
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect"
    },
}


def encode(value, *, ensure_ascii=False):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=ensure_ascii, separators=(",", ":"), allow_nan=False
    ).encode()


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value, *, ensure_ascii=False):
    return hashlib.sha256(encode(value, ensure_ascii=ensure_ascii)).hexdigest()


def unpack(value):
    return json.loads(value) if isinstance(value, str) else value


def period_id(start, end):
    date.fromisoformat(end)
    if start is None:
        return "period:instant:" + end
    date.fromisoformat(start)
    return "period:duration:" + start + ":" + end


def target_periods(target):
    return [
        tuple(pair)
        for pair in target.get("actual_periods")
        or [target["previous_period"], target["current_period"]]
    ]


def original_split(cluster):
    bucket = int(hashlib.sha256((SALT + cluster).encode()).hexdigest(), 16) % 55
    return "train" if bucket < 10 else "dev" if bucket < 19 else "confirm"


def resolve_pointer(payload, pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("native pointer must be an absolute JSON pointer")
    value = payload
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not token.isdigit() or token != str(int(token)):
                raise ValueError("noncanonical original array index")
            value = value[int(token)]
        else:
            value = value[token]
    return value


def public_period_errors(public, target, native_rows, *, final=None):
    """Independently parse saved prose and JSON, never regenerate either one.

    The base question is checked separately from the appended contract. A correct
    appended date block cannot conceal a conflicting calendar label, date, year,
    arithmetic operation, or direction in the original question.
    """
    errors = []

    def check(condition, code):
        if not condition:
            errors.append(code)

    try:
        contract, question = public["period_contract"], public["question"]
        pairs = target_periods(target)
        metrics = target.get("metric_ids") or [target["metric_id"]]
        periods = contract["periods"]
        kind = {
            "three_annual_flow_mean": "arithmetic_mean",
            "three_year_peak_then_same_period_metric": "argmax_then_lookup",
            "difference": "difference",
            "relative_change": "relative_change",
        }[target["quantity"]]
        check(contract["schema"] == "actual_period_contract.v1", "contract_schema")
        check(
            contract["quantity"] == target["quantity"] and contract["metric_ids"] == metrics,
            "contract_quantity_and_metric_identity",
        )
        check(contract["source_cluster"] == target["source_cluster"], "contract_source_identity")
        check(contract["operation"]["kind"] == kind, "contract_operation_identity")
        actual = [(row["start"], row["end"]) for row in periods]
        check(actual == pairs, "contract_exact_ordered_target_intervals")
        check(len(set(actual)) == len(actual), "no_actual_interval_collapse")
        check(
            actual == sorted(actual, key=lambda pair: (pair[1], pair[0] or "")),
            "chronological_actual_intervals",
        )
        check(
            len(pairs) == (3 if kind in {"arithmetic_mean", "argmax_then_lookup"} else 2),
            "registered_actual_period_count",
        )
        for row in periods:
            start, end = row["start"], row["end"]
            check(row["period_id"] == period_id(start, end), "source_date_period_identity")
            check(row["period_type"] == ("duration" if start else "instant"), "actual_period_type")
            full_calendar = bool(
                start and start == end[:4] + "-01-01" and end == start[:4] + "-12-31"
            )
            check(
                row["label_basis"] in {"actual_interval", "calendar_year"}
                and (row["label_basis"] != "calendar_year" or full_calendar),
                "no_unproven_calendar_or_fiscal_label",
            )
            if start:
                check(
                    330 <= (date.fromisoformat(end) - date.fromisoformat(start)).days + 1 <= 380,
                    "native_annual_duration_52_53_weeks_allowed",
                )
        for left, right in zip(actual, actual[1:], strict=False):
            check((left[0] is None) == (right[0] is None), "no_mixed_stock_flow_periods")
            if left[0] is not None and right[0] is not None:
                check(
                    date.fromisoformat(right[0]) == date.fromisoformat(left[1]) + timedelta(days=1),
                    "no_actual_period_gap_or_overlap",
                )
        expected = {(metric, *pair) for metric in metrics for pair in pairs}
        found = {
            (row["metric_id"], row["record"].get("start"), row["record"]["end"])
            for row in native_rows
            if row["source_cluster"] == target["source_cluster"]
        }
        check(expected <= found, "every_metric_in_every_exact_native_interval")
        body = {key: value for key, value in contract.items() if key != "id"}
        check(
            contract["id"] == "actual_period_contract:" + digest(body, ensure_ascii=True),
            "persisted_period_contract_identity",
        )
        blocks = re.findall(re.escape(BEGIN) + r"\s*(.*?)\s*" + re.escape(END), question, re.S)
        check(len(blocks) == 1, "one_saved_period_contract_block")
        if len(blocks) == 1:
            check(json.loads(blocks[0]) == contract, "question_block_equals_public_contract")
        human = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), "", question, flags=re.S)
        # Parse native interval lines literally, independently of the generator.
        found_lines = []
        for line in human.splitlines():
            if not line.startswith("Period period:"):
                continue
            matched = re.fullmatch(
                r"Period (period:duration:(\d{4}-\d{2}-\d{2}):(\d{4}-\d{2}-\d{2})): "
                r"(\d{4}-\d{2}-\d{2}) through (\d{4}-\d{2}-\d{2})\.",
                line,
            )
            instant = re.fullmatch(
                r"Period (period:instant:(\d{4}-\d{2}-\d{2})): instant at (\d{4}-\d{2}-\d{2})\.",
                line,
            )
            check(bool(matched or instant), "saved_human_period_line_parse")
            if matched:
                check(matched.group(2, 3) == matched.group(4, 5), "human_period_id_dates_match")
                found_lines.append((matched[1], matched[4], matched[5]))
            elif instant:
                check(instant[2] == instant[3], "human_instant_id_date_matches")
                found_lines.append((instant[1], None, instant[3]))
        check(
            found_lines == [(row["period_id"], row["start"], row["end"]) for row in periods],
            "saved_human_exact_ordered_period_set",
        )
        base = question.split("\n\nActual comparison periods (inclusive source dates):", 1)[0]
        check(base != question, "separate_original_question_and_actual_period_explanation")
        check(
            all(METRIC_NAMES[metric].casefold() in base.casefold() for metric in metrics),
            "base_question_registered_target_metrics",
        )
        if metrics == [CASH]:
            check(
                "restricted cash" not in base.casefold(), "public_cash_account_scope_matches_target"
            )
        if metrics == [RESTRICTED]:
            check("restricted cash" in base.casefold(), "public_cash_account_scope_matches_target")
        all_dates = {value for pair in pairs for value in pair if value}
        check(
            set(re.findall(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", human)) <= all_dates,
            "no_conflicting_date_hidden_by_correct_contract",
        )
        end_years = {end[:4] for _, end in pairs}
        check(
            set(re.findall(r"(?<![\d-])(?:19|20)\d{2}(?![\d-])", base)) <= end_years,
            "base_question_year_indices_match_actual_intervals",
        )
        noncalendar = any(
            start != end[:4] + "-01-01" or end != end[:4] + "-12-31" for start, end in pairs
        )
        check(
            not noncalendar or re.search(r"\bcalendar[ -]+years?\b|自然年", human, re.I) is None,
            "no_calendar_label_for_noncalendar_actual_target",
        )
        mentioned_intervals = re.findall(
            r"(\d{4}-\d{2}-\d{2})\s*(?:through|to|至|/|→)\s*(\d{4}-\d{2}-\d{2})", base, re.I
        )
        allowed_intervals = set(pairs)
        if kind in {"arithmetic_mean", "argmax_then_lookup"}:
            # A question may describe the complete comparison window while its
            # separate public set explicitly identifies every annual operand.
            allowed_intervals.add((pairs[0][0], pairs[-1][1]))
        check(
            all(tuple(pair) in allowed_intervals for pair in mentioned_intervals),
            "base_question_complete_intervals_not_mixed",
        )
        operation = contract["operation"]
        if kind == "arithmetic_mean":
            check(
                operation.get("metric_id") == metrics[0] and operation.get("operand_count") == 3,
                "mean_exact_metric_and_three_operands",
            )
            check(
                re.search(r"\b(?:average|mean)\b|平均", base, re.I) is not None,
                "base_question_requests_mean_not_other_operation",
            )
            check(
                re.search(
                    r"\b(?:sum|total|median|maximum|minimum|difference)\b|总和|中位数|最大值|最小值|差额",
                    base,
                    re.I,
                )
                is None,
                "base_question_has_no_conflicting_mean_operation",
            )
        elif kind == "argmax_then_lookup":
            check(
                operation.get("primary_metric_id") == metrics[0]
                and operation.get("secondary_metric_id") == metrics[1]
                and operation.get("candidate_count") == 3
                and operation.get("same_actual_period_required") is True,
                "argmax_three_candidates_and_same_period_lookup",
            )
            check(
                re.search(r"\b(?:peak|highest|largest|maximum)\b|最高|最大", base, re.I)
                is not None,
                "base_question_requests_peak",
            )
            check(
                re.search(
                    r"(?:peak[- ]|highest\s+)" + re.escape(METRIC_NAMES[metrics[0]]) + r"\b",
                    base,
                    re.I,
                )
                is not None,
                "base_question_primary_selection_metric_role",
            )
            check(
                re.search(
                    r"\b(?:lowest|smallest|minimum|average|mean)\b|最低|最小|平均", base, re.I
                )
                is None,
                "base_question_has_no_conflicting_peak_operation",
            )
            final_rule = public.get("tool_contract", {}).get("Final", "")
            check(
                "period_id" in final_rule and "first" in final_rule.lower(),
                "public_final_requires_actual_selected_period_and_first_stop",
            )
            if final is not None:
                chosen = final.get("period_id")
                raw = final.get("actual_period")
                check(
                    isinstance(raw, dict) and chosen == period_id(raw.get("start"), raw["end"]),
                    "reference_final_exact_interval_identity",
                )
                check(
                    chosen in {row["period_id"] for row in periods},
                    "reference_final_in_public_actual_set",
                )
        else:
            check(
                operation.get("direction") == "current_minus_previous",
                "public_forward_difference_direction",
            )
            check(
                re.search(r"(?:previous|earlier)\s*(?:minus|-)\s*(?:current|later)", human, re.I)
                is None,
                "question_no_reversed_difference_direction",
            )
            if len(mentioned_intervals) == 2:
                check(
                    [tuple(pair) for pair in mentioned_intervals] == pairs,
                    "base_question_two_intervals_forward_order",
                )
            if kind == "relative_change":
                check(
                    operation.get("denominator") == "strictly_positive_previous"
                    and operation.get("multiplier") == 100,
                    "public_previous_positive_growth_base",
                )
                check(
                    re.search(
                        r"\b(?:growth|percentage|percent|rate|yoy)\b|增长率|变化率", base, re.I
                    )
                    is not None,
                    "base_question_requests_rate",
                )
            else:
                check(
                    re.search(r"\b(?:change|difference)\b|变化额|差额", base, re.I) is not None,
                    "base_question_requests_difference",
                )
        expected_unit = "percent" if kind == "relative_change" else "million USD"
        check(
            public["quantity_contract"]["unit"] == target["unit"] == expected_unit,
            "public_target_unit_identity",
        )
    except (KeyError, TypeError, ValueError, IndexError) as error:
        errors.append("malformed_public_period_contract:" + str(error))
    return sorted(set(errors))


def account_scope_errors(target, certificate, bindings):
    """Native account types, not matching values, admit a cash reconciliation."""
    metric = target.get("metric_id")
    if metric not in {CASH, RESTRICTED}:
        return []
    errors, included = [], metric == RESTRICTED
    base = certificate.get("base_relation_certificate", certificate)
    if base.get("account_scope") != ("including_restricted" if included else "cash_only"):
        errors.append("cash_certificate_account_scope")
    previous, current = target["previous_period"], target["current_period"]
    interval = ((date.fromisoformat(previous[1]) + timedelta(days=1)).isoformat(), current[1])
    expected_metrics = [
        metric,
        *FLOW_METRICS,
        "effect_of_exchange_rate_on_cash_including_restricted"
        if included
        else "effect_of_exchange_rate_on_cash_and_cash_equivalents",
        "change_in_cash_including_restricted_and_exchange_rate_effect"
        if included
        else "change_in_cash_including_exchange_rate_effect",
    ]
    seen = Counter()
    for identifier in certificate["leaf_fact_ids"]:
        native = bindings[identifier]
        native_metric = native["metric_id"]
        seen[native_metric] += 1
        if native_metric not in expected_metrics or native["tag"] not in TAGS.get(
            native_metric, set()
        ):
            errors.append("cash_native_account_or_component_tag_mismatch")
        pair = (native["record"].get("start"), native["record"]["end"])
        if native_metric == metric:
            if pair not in [tuple(previous), tuple(current)] or pair[0] is not None:
                errors.append("cash_native_stock_endpoint_identity")
        elif pair != interval:
            errors.append("cash_native_component_actual_interval")
    if seen != Counter({metric: 2, **dict.fromkeys(expected_metrics[1:], 1)}):
        errors.append("cash_complete_typed_bridge_source_set")
    if not base.get("source_citations"):
        errors.append("cash_common_original_filing_required")
    return sorted(set(errors))


class Audit:
    def __init__(self, root, directory):
        self.root, self.directory = Path(root).resolve(), Path(directory).resolve()
        if not self.directory.is_relative_to(self.root):
            raise ValueError("panel directory must be inside the explicit project root")
        self.stage = self.directory.parent
        self.failures, self.checks = [], Counter()
        self.task_ids, self.exported_ids, self.source_refs = set(), set(), {}
        self.old_directory = None
        self.bundles = {}

    def check(self, condition, code, *, task=None, detail=None):
        self.checks[code] += 1
        if not condition:
            self.failures.append({"code": code, "task_id": task, "detail": detail})

    def path(self, base, relative):
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe relative audit input path")
        path = Path(base)
        for part in relative.parts:
            path = path / part
            if path.is_symlink():
                raise ValueError("audit input symlink")
        if not path.resolve().is_relative_to(Path(base).resolve()):
            raise ValueError("audit input path escapes declared base")
        return path

    def identity(self, value):
        body = {key: item for key, item in value.items() if key != "id"}
        expected = value["schema_version"].rsplit(".", 1)[-1] + ":" + digest(body)
        self.check(value["id"] == expected, "content_addressed_record", task=value.get("task_id"))

    @lru_cache(maxsize=2)  # noqa: B019 -- short-lived auditor and bounded original-snapshot cache.
    def payload(self, relative):
        reference = self.source_refs[relative]
        path = self.path(self.root, relative)
        self.check(
            path.stat().st_size == reference["bytes"] and sha(path) == reference["sha256"],
            "full_original_snapshot_hash_and_size",
        )
        return read(path)

    def tables(self, directory, name):
        return [
            row
            for path in sorted((directory / "parents" / name).glob("*.json"))
            for row in read(self.path(directory, path.relative_to(directory)))
        ]

    def native(self, identifier, bindings, facts, source, task):
        native = bindings[identifier]
        reference = source["complete_original_snapshot"]
        payload = self.payload(reference["path"])
        raw = resolve_pointer(payload, native["pointer"])
        self.check(raw == native["record"], "native_pointer_original_record", task=task)
        self.check(
            native["pointer"].startswith("/facts/us-gaap/" + native["tag"] + "/units/USD/")
            and native["tag"] in TAGS.get(native["metric_id"], set()),
            "native_original_concept_metric_and_USD_unit",
            task=task,
        )
        self.check(
            native["raw_sha256"] == reference["sha256"]
            and "cik:" + str(payload["cik"]).zfill(10) == native["source_cluster"],
            "native_snapshot_CIK_and_hash",
            task=task,
        )
        fact = facts[identifier]
        self.check(
            (fact.get("period_start"), fact["period_end"]) == (raw.get("start"), raw["end"])
            and fact["metric_id"] == native["metric_id"],
            "native_fact_actual_metric_interval",
            task=task,
        )
        self.check(
            payload["facts"]["us-gaap"][native["tag"]]["description"]
            == native["native_definition"]["description"],
            "original_native_definition",
            task=task,
        )
        value = Fraction(str(raw["val"])) / 1000000
        self.check(
            value == Fraction(str(fact["normalized_value"])), "native_exact_million_USD", task=task
        )
        return value

    def interpret(self, witness, values):
        outputs = {}
        for step in witness["operator_dag"]["operators"]:
            arguments = [
                values[witness["input_bindings"][arg["binding"]]]
                if "binding" in arg
                else outputs[arg["step"]]
                for arg in step["inputs"]
            ]
            operator = step["operator"]
            if operator == "difference":
                value = arguments[1] - arguments[0]
            elif operator == "sum":
                value = sum(arguments)
            elif operator == "linear_combination":
                value = sum(
                    Fraction(str(coefficient)) * amount
                    for coefficient, amount in zip(
                        step["params"]["coefficients"], arguments, strict=True
                    )
                )
            elif operator == "ratio_percent":
                value = 100 * arguments[0] / arguments[1]
            else:
                raise ValueError("unregistered independent witness operator: " + operator)
            outputs[step["step_id"]] = value
        return outputs[witness["operator_dag"]["output_step"]]

    def task(
        self,
        directory,
        row,
        sources,
        bindings,
        tables,
        compilations,
        split,
        old_clusters,
        *,
        selected=True,
    ):
        task = row["task_id"]
        bundle = read(self.path(directory, row["path"]))
        self.identity(bundle)
        self.identity(bundle["surface"])
        self.check(
            bundle["id"] == row["bundle_id"] and bundle["task_id"] == task,
            "catalog_bundle_task_join",
            task=task,
        )
        self.check(task not in self.exported_ids, "exported_task_identity_unique", task=task)
        self.exported_ids.add(task)
        if selected:
            self.task_ids.add(task)
        public_path = self.path(directory, row["public_path"])
        messages = read(public_path)
        self.check(
            sha(public_path)
            == row["public_messages_sha256"]
            == bundle["surface"]["public_messages_sha256"],
            "saved_public_file_sha",
            task=task,
        )
        self.check(
            len(messages) == 1
            and messages[0]["role"] == "user"
            and json.loads(messages[0]["content"]) == bundle["public"],
            "saved_public_envelope_join",
            task=task,
        )
        target, parent, public = (
            bundle["private"]["canonical_target"],
            bundle["parents"],
            bundle["public"],
        )
        self.check(
            public["period_contract"]["task_id"] == task
            and bundle["surface"]["period_contract_id"] == public["period_contract"]["id"],
            "public_period_contract_and_surface_task_join",
            task=task,
        )
        cluster, family = bundle["source_cluster"], bundle["family"]
        self.check(
            "task_" + digest(target, ensure_ascii=family != "dual_sufficient") == task,
            "canonical_target_identity_recomputed",
            task=task,
        )
        self.check(
            original_split(cluster) == split == bundle["split"]
            and bundle["allowed_uses"] == [split],
            "original_salt_task_split",
            task=task,
        )
        self.check(cluster not in old_clusters, "old_confirmation_CIK_not_reused", task=task)
        source = sources[cluster]
        self.check(
            public["source_document"] == source,
            "complete_public_snapshot_not_leaf_projection",
            task=task,
        )
        facts, leaves = tables["standardized_facts"], parent["all_leaf_fact_ids"]
        certificate = bundle["private"]["relation_certificate"]
        self.identity(certificate)
        self.check(
            set(leaves) == set(certificate["leaf_fact_ids"]),
            "full_certificate_leaf_ancestry",
            task=task,
        )
        values = {}
        for identifier in leaves:
            native, fact = bindings[identifier], facts[identifier]
            self.check(
                native["source_cluster"] == cluster
                and native["split"] == split
                and native["allowed_uses"] == [split],
                "all_leaf_original_split",
                task=task,
            )
            self.check(
                fact["build_id"] == parent["fact_build_id"]
                and fact["graph_ready"] == 1
                and not fact["is_forecast"],
                "actual_source_Fact_build",
                task=task,
            )
            values[identifier] = self.native(identifier, bindings, facts, source, task)
        errors = public_period_errors(
            public, target, [bindings[key] for key in leaves], final=bundle["private"]["answer"]
        )
        for error in errors:
            self.check(False, "public_period:" + error, task=task)
        self.check(not errors, "independent_saved_public_period_admission", task=task)
        candidate, sample, plan = (
            tables["qa_candidates"][parent["candidate_id"]],
            tables["qa_samples"][parent["qa_id"]],
            tables["qa_operation_plans"][parent["operation_plan_id"]],
        )
        compiled = compilations[parent["compilation_id"]]
        self.identity(compiled)
        self.check(
            compiled["task_id"] == task
            and compiled["qa_build_id"] == parent["qa_build_id"]
            and compiled["candidate_id"] == parent["candidate_id"]
            and compiled["operation_plan_id"] == parent["operation_plan_id"]
            and set(compiled["source_leaf_ids"]) == set(leaves),
            "exact_task_compilation_and_complete_leaf_parent_join",
            task=task,
        )
        self.check(
            bundle["surface"]["qa_build_id"] == parent["qa_build_id"]
            and bundle["surface"]["qa_id"] == parent["qa_id"],
            "new_surface_real_QA_identity",
            task=task,
        )
        base_question = public["question"].split(
            "\n\nActual comparison periods (inclusive source dates):", 1
        )[0]
        self.check(
            sample["candidate_id"] == candidate["candidate_id"]
            and sample["qa_build_id"] == parent["qa_build_id"]
            and sample["question"] == base_question
            and hashlib.sha256(base_question.encode()).hexdigest()
            == bundle["surface"]["base_qa_question_sha256"],
            "real_QA_parent_and_saved_base_question",
            task=task,
        )
        self.check(
            sample["validation_status"] == bundle["validation"]["status"] == "passed"
            and candidate["eligibility_status"] == "eligible",
            "actual_qualified_QA_sample",
            task=task,
        )
        self.check(
            sample["generation_method"] == "deterministic_template",
            "no_evaluation_LLM_rewrite",
            task=task,
        )
        self.check(
            parent["pattern_id"]
            == candidate["pattern_id"]
            == plan["pattern_id"]
            == compiled["pattern_id"]
            and parent["pattern_hash"] == candidate["pattern_hash"] == compiled["pattern_hash"],
            "actual_registered_pattern_lineage",
            task=task,
        )
        self.check(
            plan["candidate_id"] == candidate["candidate_id"]
            and plan["qa_build_id"] == parent["qa_build_id"],
            "actual_plan_candidate_QA_build",
            task=task,
        )
        kg = tables["kg_builds"][parent["kg_build_id"]]
        self.check(
            kg["status"] == "success"
            and kg["quality_status"] == "passed"
            and tables["qa_builds"][parent["qa_build_id"]]["quality_status"] == "passed",
            "actual_successful_KG_and_QA_builds",
            task=task,
        )
        self.check(
            bool(bundle["validation"]["qa_check_ids"])
            and all(
                tables["qa_quality_checks"][key]["qa_id"] == sample["qa_id"]
                and tables["qa_quality_checks"][key]["check_status"] == "passed"
                for key in bundle["validation"]["qa_check_ids"]
            ),
            "actual_all_QA_checks",
            task=task,
        )
        inputs = unpack(plan["input_bindings"])
        self.check(
            unpack(candidate["answer_payload"]) == bundle["private"]["answer_payload"],
            "actual_candidate_answer_payload_not_replaced",
            task=task,
        )
        if family == "dual_sufficient":
            previous, current = inputs["previous"], inputs["current"]
            self.check(
                bindings[previous]["metric_id"]
                == bindings[current]["metric_id"]
                == target["metric_id"],
                "dual_endpoint_target_metric_identity",
                task=task,
            )
            self.check(
                (facts[previous].get("period_start"), facts[previous]["period_end"])
                == tuple(target["previous_period"])
                and (facts[current].get("period_start"), facts[current]["period_end"])
                == tuple(target["current_period"]),
                "dual_actual_period_direction",
                task=task,
            )
            derived = [tables["derived_facts"][key] for key in parent["source_derived_ids"]]
            self.check(
                len(derived) == 1
                and derived[0]["build_id"] == kg["input_qa_build_id"]
                and set(unpack(derived[0]["input_fact_ids"])) == {previous, current},
                "unique_real_current_build_DerivedFact_exact_parents",
                task=task,
            )
            expected = values[current] - values[previous]
            if target["quantity"] == "relative_change":
                self.check(values[previous] > 0, "growth_positive_actual_previous_base", task=task)
                expected = expected / values[previous] * 100
            witnesses = certificate["witnesses"]
            self.check(
                {witness["basis"] for witness in witnesses} == {"endpoint", "movement"},
                "two_public_sufficient_relations",
                task=task,
            )
            for witness in witnesses:
                self.check(
                    self.interpret(witness, values) == expected,
                    "independent_dual_exact_arithmetic",
                    task=task,
                )
            for error in account_scope_errors(target, certificate, bindings):
                self.check(False, error, task=task)
            base = certificate.get("base_relation_certificate", certificate)
            if target["metric_id"] == "gross_profit":
                for endpoint in (previous, current):
                    pair = (facts[endpoint].get("period_start"), facts[endpoint]["period_end"])
                    parts = {
                        facts[key]["metric_id"]: key
                        for key in leaves
                        if (facts[key].get("period_start"), facts[key]["period_end"]) == pair
                    }
                    self.check(
                        values[endpoint]
                        == values[parts["revenue"]] - values[parts["cost_of_revenue"]]
                        and bindings[parts["cost_of_revenue"]]["tag"]
                        in {"CostOfRevenue", "CostOfGoodsAndServicesSold"},
                        "gross_profit_complete_typed_revenue_minus_cost",
                        task=task,
                    )
            for citation in base["source_citations"]:
                for occurrence in citation["source_occurrences"]:
                    original = resolve_pointer(
                        self.payload(source["complete_original_snapshot"]["path"]),
                        occurrence["pointer"],
                    )
                    self.check(
                        original == occurrence["record"]
                        and original["accn"] == citation["accession"]
                        and original.get("form") in {"10-K", "10-K/A"},
                        "original_common_annual_filing_occurrence",
                        task=task,
                    )
        elif family == "composition_required":
            series = inputs["series"]
            self.check(
                {bindings[key]["metric_id"] for key in series} == set(target["metric_ids"]),
                "mean_plan_native_target_metric",
                task=task,
            )
            self.check(
                len(series) == len(set(series)) == 3
                and {
                    (bindings[key]["record"].get("start"), bindings[key]["record"]["end"])
                    for key in series
                }
                == set(target_periods(target)),
                "mean_three_exact_native_operands",
                task=task,
            )
            self.check(
                len({bindings[key]["source_definition_id"] for key in series}) == 1,
                "mean_unchanged_native_definition",
                task=task,
            )
            expected = sum(values[key] for key in series) / 3
            native = bindings[series[0]]
            concept = self.payload(source["complete_original_snapshot"]["path"])["facts"][
                "us-gaap"
            ][native["tag"]]
            pairs = target_periods(target)
            self.check(
                not any(
                    raw.get("start") == pairs[0][0] and raw["end"] == pairs[-1][1]
                    for raw in concept["units"].get("USD", [])
                ),
                "no_same_concept_full_window_aggregate_hidden",
                task=task,
            )
        else:
            primary, secondary = inputs["primary_series"], inputs["secondary_series"]
            for series, metric in zip((primary, secondary), target["metric_ids"], strict=True):
                self.check(
                    {bindings[key]["metric_id"] for key in series} == {metric}
                    and {
                        (bindings[key]["record"].get("start"), bindings[key]["record"]["end"])
                        for key in series
                    }
                    == set(target_periods(target)),
                    "argmax_plan_metric_roles_and_exact_intervals",
                    task=task,
                )
            self.check(
                len(primary) == len(secondary) == 3,
                "argmax_all_primary_and_secondary_periods",
                task=task,
            )
            peak = max(primary, key=values.__getitem__)
            self.check(
                sum(values[key] == values[peak] for key in primary) == 1,
                "unique_native_primary_peak",
                task=task,
            )
            pair = (bindings[peak]["record"].get("start"), bindings[peak]["record"]["end"])
            selected = [
                key
                for key in secondary
                if (bindings[key]["record"].get("start"), bindings[key]["record"]["end"]) == pair
            ]
            self.check(
                len(selected) == 1,
                "secondary_lookup_same_actual_interval_not_year_index",
                task=task,
            )
            expected = values[selected[0]]
            candidate_period = unpack(candidate["answer_payload"]).get("actual_period") or {}
            self.check(
                (
                    candidate_period.get("start", candidate_period.get("period_start")),
                    candidate_period.get("end", candidate_period.get("period_end")),
                )
                == pair,
                "actual_QA_candidate_selected_interval_not_year_alias",
                task=task,
            )
            self.check(
                bundle["private"]["answer"]["period_id"] == period_id(*pair),
                "argmax_reference_Final_actual_selected_interval",
                task=task,
            )
            for series in (primary, secondary):
                self.check(
                    len({bindings[key]["source_definition_id"] for key in series}) == 1,
                    "argmax_unchanged_metric_series_definition",
                    task=task,
                )
        actual_answer = Fraction(str(bundle["private"]["answer"]["value"]))
        self.check(
            abs(expected - actual_answer) <= Fraction(1, 10**18)
            and Fraction(str(unpack(candidate["answer_payload"])["value"])) == actual_answer,
            "independent_exact_amount_after_scope_admission",
            task=task,
        )
        self.check(
            bundle["Teacher_sessions"] == bundle["Student_sessions"] == 0,
            "panel_build_not_model_output",
            task=task,
        )
        self.bundles[task] = bundle
        return bundle

    def panel(self, split, metadata):
        directory = self.directory / split
        catalog, sources = (
            read(directory / "catalog.json"),
            read(directory / "public_source_index.json"),
        )
        self.identity(catalog)
        expected_sources = {
            row["source_cluster"]: row["raw_object"]
            for row in metadata["rows"]
            if row["split"] == split
            and row["raw_object"]
            and not row["historical_confirmation_issuer"]
        }
        self.check(
            set(sources) == set(expected_sources), "all_and_only_frozen_panel_snapshots_public"
        )
        for cluster, source in sources.items():
            reference = source["complete_original_snapshot"]
            original = expected_sources.get(cluster, {})
            self.check(
                source["source_id"] == original.get("raw_object_id")
                and reference["sha256"] == original.get("content_sha256")
                and reference["bytes"] == original.get("content_size_bytes")
                and reference["original_url"] == original.get("original_url"),
                "public_snapshot_matches_frozen_source_identity",
            )
            self.source_refs[reference["path"]] = reference
            path = self.path(directory, source["path"])
            document = read(path)
            self.identity(document)
            self.check(
                sha(path) == source["sha256"]
                and path.stat().st_size == source["bytes"]
                and document["id"] == source["document_id"],
                "public_source_document_bytes",
            )
            self.check(
                document["source_cluster"] == cluster
                and document["complete_original_snapshot"] == reference
                and document.get("omitted_source_numeric_records") is False,
                "public_original_snapshot_accessibility",
            )
        bindings = read(directory / "native_bindings.json")
        names = {
            "standardized_facts": "fact_id",
            "derived_facts": "derived_id",
            "qa_candidates": "candidate_id",
            "qa_samples": "qa_id",
            "qa_operation_plans": "plan_id",
            "kg_builds": "kg_build_id",
            "qa_builds": "qa_build_id",
            "qa_quality_checks": "check_id",
        }
        tables = {
            name: {row[key]: row for row in self.tables(directory, name)}
            for name, key in names.items()
        }
        compilations = {
            row["id"]: row
            for path in sorted((directory / "QA").glob("batch_*/pattern_compilations.json"))
            for row in read(path)
        }
        targets = [
            row
            for path in sorted((directory / "QA").glob("batch_*/target_bindings.json"))
            for row in read(path)
        ]
        selected = catalog["tasks"]
        overflow = read(directory / "compiled_overflow.json")
        rejections = read(directory / "compiler_rejections.json")
        remaining = read(directory / "uncompiled_overflow.json")
        qualified = read(directory / "all_source_qualified_candidates.json")
        source_rejections = read(directory / "source_rejections.json")
        selected_ids = {row["task_id"] for row in selected}
        exported_ids = {row["task_id"] for row in [*selected, *overflow]}
        rejected_ids = {row["task_id"] for row in rejections}
        attempted_ids = {row["task_id"] for row in targets}
        all_qualified = [row for group in GROUPS for row in qualified[group]]
        qualified_ids = {row["task_id"] for row in all_qualified}
        remaining_ids = {row["task_id"] for group in GROUPS for row in remaining[group]}
        self.check(
            len(selected_ids) == len(selected)
            and len(exported_ids) == len(selected) + len(overflow),
            "selected_and_compiled_overflow_unique_partition",
        )
        self.check(
            len(attempted_ids) == len(targets)
            and attempted_ids == exported_ids | rejected_ids
            and not exported_ids & rejected_ids,
            "all_compiler_attempts_exported_or_retained_rejection",
        )
        self.check(
            len(qualified_ids) == len(all_qualified)
            and qualified_ids == attempted_ids | remaining_ids
            and not attempted_ids & remaining_ids,
            "entire_finite_candidate_universe_retained",
        )
        self.check(
            all(row.get("reason") for row in [*rejections, *source_rejections]),
            "all_rejection_reasons_retained",
        )
        for group in GROUPS:
            ordered = [row["task_id"] for row in qualified[group]]
            attempted_group = [row["task_id"] for row in targets if row["family"] == group]
            selected_group = [row["task_id"] for row in selected if row["family"] == group]
            self.check(
                attempted_group == ordered[: len(attempted_group)],
                "fixed_candidate_order_compiler_prefix",
                detail=group,
            )
            admitted_order = [identifier for identifier in ordered if identifier in exported_ids]
            self.check(
                selected_group == admitted_order[: QUOTAS[split][group]],
                "fixed_order_first_qualified_quota_without_model_selection",
                detail=group,
            )
        counts = Counter(row["family"] for row in selected)
        shortages = {group: QUOTAS[split][group] - counts[group] for group in GROUPS}
        self.check(
            catalog["requested_counts"] == QUOTAS[split]
            and catalog["realized_counts"] == dict(counts)
            and catalog["shortages"] == shortages,
            "exact_registered_group_denominators",
        )
        self.check(
            dict(counts) == QUOTAS[split],
            "registered_panel_quota_complete",
            detail={"split": split, "counts": dict(counts)},
        )
        self.check(
            catalog.get("Teacher_outcome_selection") is False,
            "panel_selection_not_Teacher_outcomes",
        )
        old_clusters = {
            row["source_cluster"] for row in metadata["historical_confirmation_cik_bindings"]
        }
        clusters, snapshots, end_membership, exact_membership = (
            Counter(),
            Counter(),
            Counter(),
            Counter(),
        )
        group_clusters, cluster_tasks, windows = defaultdict(set), defaultdict(list), []
        for row in [*selected, *overflow]:
            chosen = row["task_id"] in selected_ids
            try:
                bundle = self.task(
                    directory,
                    row,
                    sources,
                    bindings,
                    tables,
                    compilations,
                    split,
                    old_clusters,
                    selected=chosen,
                )
            except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError) as error:
                self.check(False, "task_audit_exception", task=row["task_id"], detail=str(error))
                continue
            if not chosen:
                continue
            cluster = bundle["source_cluster"]
            clusters[cluster] += 1
            snapshots[row["raw_snapshot_sha256"]] += 1
            group_clusters[row["family"]].add(cluster)
            cluster_tasks[cluster].append(row["task_id"])
            for end in set(row["periods"]):
                end_membership[cluster, end] += 1
            pairs = target_periods(bundle["private"]["canonical_target"])
            for start, end in set(pairs):
                exact_membership[cluster, start, end] += 1
            windows.append(
                {
                    "task_id": row["task_id"],
                    "family": row["family"],
                    "source_cluster": cluster,
                    "actual_target_periods": pairs,
                    "snapshot_sha256": row["raw_snapshot_sha256"],
                }
            )
        saved = read(directory / "source_correlation_report.json")
        overlap = sum(count * (count - 1) // 2 for count in end_membership.values())
        self.check(
            saved["task_count"] == len(selected)
            and saved["tasks_per_CIK_cluster"] == dict(clusters)
            and saved["source_CIK_cluster_count"] == len(clusters),
            "independent_source_CIK_correlation",
        )
        self.check(
            saved["tasks_per_original_snapshot"] == dict(snapshots)
            and saved["original_snapshot_count"] == len(snapshots),
            "independent_source_snapshot_correlation",
        )
        self.check(
            saved["overlapping_issuer_period_pairs"] == overlap,
            "independent_original_overlap_pair_count",
        )
        impacts = self.impact(split, catalog, qualified, rejections, overflow, remaining)
        return {
            "catalog_id": catalog["id"],
            "task_count": len(selected),
            "group_counts": dict(counts),
            "shortages": shortages,
            "compiled_overflow_count": len(overflow),
            "uncompiled_overflow_count": len(remaining_ids),
            "compiler_rejection_count": len(rejections),
            "source_rejection_counts": dict(Counter(row["reason"] for row in source_rejections)),
            "source_CIK_clusters": dict(clusters),
            "source_CIK_count": len(clusters),
            "source_CIK_count_by_group": {group: len(group_clusters[group]) for group in GROUPS},
            "source_snapshot_count": len(snapshots),
            "source_cluster_task_ids": dict(cluster_tasks),
            "original_shared_enddate_pair_sum": overlap,
            "shared_exact_target_interval_pair_sum": sum(
                count * (count - 1) // 2 for count in exact_membership.values()
            ),
            "actual_target_windows": windows,
            "effective_independent_sample_size_inferred": False,
            "impact": impacts,
        }

    def old_file(self, path):
        relative = str(path.relative_to(self.old_directory.parent))
        member = self.old_manifest_members.get(relative)
        self.check(
            member is not None
            and path.stat().st_size == member["bytes"]
            and sha(path) == member["sha256"],
            "preserved_old_artifact_manifest_bytes",
            detail=relative,
        )
        return read(path)

    def impact(self, split, catalog, qualified, rejections, overflow, remaining):
        directory = self.directory / split
        old_directory = self.old_directory / split
        old_catalog = self.old_file(old_directory / "catalog.json")
        old_targets = self.old_file(old_directory / "QA/target_bindings.json")
        old_entries = {row["task_id"]: row for row in old_catalog["tasks"]}
        old_target_map = {row["task_id"]: row for row in old_targets}
        original_bindings = self.old_file(old_directory / "native_bindings.json")
        current_bindings = read(directory / "native_bindings.json")
        current_targets = {row["task_id"]: row for group in GROUPS for row in qualified[group]}
        rows = read(directory / "version_impact.json")
        self.check(
            len(rows) == len(old_targets)
            and {row["task_id"] for row in rows} == set(old_target_map),
            "all_prior_registered_targets_have_one_impact_row",
        )
        self.check(
            sum(row["prior_exported"] for row in rows) == len(old_entries),
            "all_prior_exports_in_impact_ledger",
        )
        all_entries = {row["task_id"]: row for row in [*catalog["tasks"], *overflow]}
        selected = {row["task_id"] for row in catalog["tasks"]}
        qualified_ids = {row["task_id"] for group in GROUPS for row in qualified[group]}
        uncompiled = {row["task_id"] for group in GROUPS for row in remaining[group]}
        rejected = {row["task_id"] for row in rejections}
        statuses, conflicts, checks = Counter(), 0, []
        for row in rows:
            self.identity(row)
            task = row["task_id"]
            target = old_target_map[task]["target"]
            original_evidence = [
                {
                    "fact_id": key,
                    "raw_sha256": original_bindings[key]["raw_sha256"],
                    "pointer": original_bindings[key]["pointer"],
                    "record": original_bindings[key]["record"],
                }
                for key in old_target_map[task]["match"]["fact_ids"]
            ]
            self.check(
                row["original_actual_period_evidence"] == original_evidence,
                "impact_original_exact_native_period_evidence",
                task=task,
            )
            current_item = current_targets.get(task)
            current_evidence = (
                None
                if current_item is None
                else [
                    {
                        "fact_id": key,
                        "raw_sha256": current_bindings[key]["raw_sha256"],
                        "pointer": current_bindings[key]["pointer"],
                        "record": current_bindings[key]["record"],
                    }
                    for key in current_item["match"]["fact_ids"]
                ]
            )
            self.check(
                row["actual_period_evidence"] == current_evidence,
                "impact_new_exact_native_period_evidence",
                task=task,
            )
            self.check(
                row["canonical_target"] == target and row["canonical_target_changed"] is False,
                "impact_old_canonical_scope_not_relabelled",
                task=task,
            )
            self.check(
                row["selected_in_new_panel"] == (task in selected)
                and row["original_record_preserved"] is True,
                "impact_selected_and_preservation_status",
                task=task,
            )
            prior = None
            if task in old_entries:
                old_path = self.path(old_directory, old_entries[task]["path"])
                prior = self.old_file(old_path)
                self.check(
                    row["prior_exported"]
                    and row["prior_bundle_id"] == prior["id"]
                    and row["prior_public"] == prior["public"]
                    and row["prior_public_sha256"] == digest(prior["public"]),
                    "impact_exact_old_bundle_and_public_SHA",
                    task=task,
                )
                conflict = bool(
                    re.search(r"\bcalendar[ -]+years?\b", prior["public"]["question"], re.I)
                ) and any(
                    start != end[:4] + "-01-01" or end != end[:4] + "-12-31"
                    for start, end in target_periods(target)
                )
                conflicts += conflict
                self.check(
                    row["prior_public_calendar_label_conflict"] == conflict,
                    "old_calendar_counterexample_preserved",
                    task=task,
                )
            else:
                self.check(
                    not row["prior_exported"] and row["prior_bundle_id"] is None,
                    "unexported_old_target_not_fabricated",
                    task=task,
                )
            new = all_entries.get(task)
            if new is not None:
                self.check(
                    row["new_public_identity"] == new, "impact_new_catalog_surface_link", task=task
                )
                new_bundle = self.bundles.get(task)
                self.check(
                    new_bundle is not None and new_bundle["private"]["canonical_target"] == target,
                    "unchanged_scope_under_preserved_task_ID",
                    task=task,
                )
                if prior and new_bundle:
                    self.check(
                        new_bundle["parents"]["prior_bundle_id"] == prior["id"]
                        and new_bundle["surface"]["prior_bundle_id"] == prior["id"]
                        and new_bundle["parents"]["qa_id"] != prior["parents"]["qa_id"]
                        and new_bundle["parents"]["qa_build_id"] != prior["parents"]["qa_build_id"],
                        "new_QA_surface_version_has_real_prior_parent",
                        task=task,
                    )
                status = (
                    "selected_new_version" if task in selected else "compiled_overflow_new_version"
                )
            elif task in rejected:
                status = "retained_compiler_rejection"
            elif task in uncompiled:
                status = "retained_uncompiled_overflow"
            else:
                status = "not_source_qualified_in_new_version"
                self.check(
                    task not in qualified_ids, "unexported_qualified_target_accounted", task=task
                )
            statuses[status] += 1
            checks.append(
                {
                    "task_id": task,
                    "prior_exported": prior is not None,
                    "prior_bundle_file_sha256": sha(old_path) if prior is not None else None,
                    "prior_public_sha256": row["prior_public_sha256"],
                    "new_status": status,
                    "new_surface_id": new["surface_version_id"] if new else None,
                    "canonical_scope_changed": False,
                }
            )
        return {
            "prior_registered_count": len(rows),
            "prior_exported_count": len(old_entries),
            "old_calendar_counterexample_count": conflicts,
            "statuses": dict(statuses),
            "tasks": checks,
        }

    def gap_cases(self, panels, diagnosis):
        original_rejections = self.old_file(
            self.old_directory / "confirm/QA_export_rejections.json"
        )
        old_targets = {
            row["task_id"]: row
            for row in self.old_file(self.old_directory / "confirm/QA/target_bindings.json")
        }
        original_compilations = {
            row["task_id"]: row
            for row in self.old_file(self.old_directory / "confirm/QA/pattern_compilations.json")
        }
        cases = diagnosis["cases"]
        self.check(
            len(cases) == diagnosis["case_count"] == len(original_rejections) == 12
            and {row["task_id"] for row in cases}
            == {row["task_id"] for row in original_rejections},
            "all_twelve_original_confirmation_gaps_exactly_once",
        )
        rejected = {row["task_id"]: row for row in original_rejections}
        impact = {row["task_id"]: row for row in panels["confirm"]["impact"]["tasks"]}
        result = []
        for row in cases:
            self.identity(row)
            task = row["task_id"]
            self.check(
                row["original_rejection"] == rejected[task]
                and row["canonical_target"] == old_targets[task]["target"]
                and row["original_compilation"] == original_compilations[task],
                "gap_case_exact_original_target_and_compiler_evidence",
                task=task,
            )
            new = self.bundles.get(task)
            result.append(
                {
                    "case_id": "confirm_original_target:" + task,
                    "old_task_id": task,
                    "kind": "old_registered_target_compiler_gap",
                    "original_rejection": rejected[task],
                    "original_exact_parent_count": len(row["exact_input_set_parents"]),
                    "new_status": impact[task]["new_status"],
                    "new_task_id": task if new else None,
                    "new_real_qa_parent": new["parents"] if new else None,
                    "equal_numeric_parent_substitution_allowed": False,
                }
            )
        old_dev = self.old_file(self.old_directory / "dev/catalog.json")
        old_dev_targets = self.old_file(self.old_directory / "dev/QA/target_bindings.json")
        old_dual = {row["task_id"] for row in old_dev_targets if row["family"] == "dual_sufficient"}
        deficit = 60 - sum(row["family"] == "dual_sufficient" for row in old_dev["tasks"])
        self.check(
            deficit == 14 and len(old_dual) == 46,
            "old_dev_fourteen_enumeration_slots_not_compiler_failures",
        )
        new_dev = read(self.directory / "dev/catalog.json")
        additions = [
            row
            for row in new_dev["tasks"]
            if row["family"] == "dual_sufficient" and row["task_id"] not in old_dual
        ]
        for index in range(deficit):
            new = additions[index] if index < len(additions) else None
            result.append(
                {
                    "case_id": f"dev_original_unenumerated_slot:{index + 1:02d}",
                    "kind": "old_enumeration_shortfall_no_prior_task_identity",
                    "old_task_id": None,
                    "original_target_did_not_exist": True,
                    "new_task_id": new["task_id"] if new else None,
                    "new_status": "new_legal_dual_supply_selected"
                    if new
                    else "unfilled_source_shortfall",
                    "binding_rule": (
                        "new selected catalog order among true dual tasks absent from old targets"
                    ),
                }
            )
        self.check(len(result) == 26, "twenty_six_distinct_old_gap_cases_preserved")
        return result

    def run(self):
        report, metadata = (
            read(self.directory / "report.json"),
            read(self.directory / "source_metadata.json"),
        )
        self.identity(report)
        self.identity(metadata)
        frozen = read(self.stage / "stage_freeze.json")
        self.check(metadata == frozen["panel_source_metadata"], "frozen_public_source_metadata")
        self.check(report["parent_freeze_id"] == frozen["id"], "frozen_panel_version_parent")
        policy = read(self.directory / "policy.json")
        self.identity(policy)
        self.check(
            policy["quotas"] == QUOTAS
            and policy["new_downloads"] == policy["model_requests"] == 0
            and policy["historical_confirmation_reuse"] is False,
            "fixed_panel_source_and_quota_policy",
        )
        historical = metadata["historical_confirmation_authority"]
        historical_path = self.path(self.root, historical["path"])
        self.check(sha(historical_path) == historical["sha256"], "old_confirmation_authority_hash")
        old_tickers = set(read(historical_path)["company_clusters"]["confirm"])
        old_clusters = {
            "cik:" + str(row["entity"]["cik"]).zfill(10)
            for row in metadata["rows"]
            if row["entity"]["ticker"] in old_tickers
        }
        self.check(
            old_clusters
            == {row["source_cluster"] for row in metadata["historical_confirmation_cik_bindings"]},
            "independent_original_confirmation_CIK_join",
        )
        eligible = Counter(
            row["split"]
            for row in metadata["rows"]
            if row["raw_object"]
            and row["split"] != "train"
            and row["source_cluster"] not in old_clusters
        )
        self.check(
            dict(eligible) == {"dev": 12, "confirm": 72}, "original_84_eligible_source_scope"
        )
        self.check(
            all(original_split(row["source_cluster"]) == row["split"] for row in metadata["rows"]),
            "independent_original_salt_for_all_source_metadata",
        )
        diagnosis = read(self.directory / "archived_twelve_gap_diagnosis.json")
        self.identity(diagnosis)
        old_rejections = self.path(self.root, diagnosis["original_rejections_path"])
        self.old_directory = old_rejections.parent.parent
        self.check(
            sha(old_rejections) == diagnosis["original_rejections_sha256"],
            "archived_gap_authority_hash",
        )
        old_manifest = read(self.old_directory.parent / "manifest.json")
        self.identity(old_manifest)
        parent = frozen["parent_bridge"]
        self.check(
            self.path(self.root, parent["directory"]) == self.old_directory.parent
            and parent["manifest_id"] == old_manifest["id"]
            and parent["manifest_sha256"] == sha(self.old_directory.parent / "manifest.json"),
            "old_bridge_parent_manifest_frozen_identity",
        )
        self.old_manifest_members = {row["path"]: row for row in old_manifest["members"]}
        panels = {split: self.panel(split, metadata) for split in ("dev", "confirm")}
        self.check(
            set(panels["dev"]["source_CIK_clusters"]).isdisjoint(
                panels["confirm"]["source_CIK_clusters"]
            ),
            "development_confirmation_source_clusters_disjoint",
        )
        self.check(
            len(self.task_ids) == report["unique_task_count"] == 900,
            "registered_total_900_selected_tasks",
        )
        prior_exports = sum(panel["impact"]["prior_exported_count"] for panel in panels.values())
        prior_registered = sum(
            panel["impact"]["prior_registered_count"] for panel in panels.values()
        )
        old_counterexamples = sum(
            panel["impact"]["old_calendar_counterexample_count"] for panel in panels.values()
        )
        self.check(
            prior_exports == 874 and prior_registered == 886,
            "all_874_old_exports_and_12_registered_rejections_preserved",
        )
        self.check(old_counterexamples == 96, "all_96_original_calendar_counterexamples_retained")
        gaps = self.gap_cases(panels, diagnosis)
        return {
            "schema": "independent_eval_readiness_panel_audit.v1",
            "status": "PASS_AS_SCOPED" if not self.failures else "BLOCKED_PANEL_ADMISSION",
            "production_panel_report_id": report["id"],
            "production_panel_report_sha256": sha(self.directory / "report.json"),
            "panel_directory": str(self.directory.relative_to(self.root)),
            "panels": panels,
            "unique_tasks": len(self.task_ids),
            "all_exported_versions_audited": len(self.exported_ids),
            "prior_export_impact_count": prior_exports,
            "prior_registered_impact_count": prior_registered,
            "retained_original_calendar_counterexamples": old_counterexamples,
            "original_gap_reconciliation": gaps,
            "checks": dict(self.checks),
            "check_count": sum(self.checks.values()),
            "failures": self.failures,
            "no_generator_renderer_label_or_QA_executor_imported": True,
            "target_scope_not_decided_by_answer_equality": True,
            "old_243_training_catalog_source_audits_reexecuted": False,
            "old_36_scripts_reexecuted": False,
            "tokenizer_constructions": 0,
            "model_calls": 0,
            "GPU_calls": 0,
            "primary_worker_validation_performed": False,
            "limitations": [
                "Bounded registered wording and financial structures; not general language proof.",
                "Panel admission is separate from trajectory-worker and formal material gates.",
                "CIK/snapshot/windows remain correlated; no independent sample size inferred.",
            ],
        }


def verify(root, directory):
    return Audit(root, directory).run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--directory",
        type=Path,
        required=True,
        help="New panel directory containing dev, confirm, and report.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    audit = Audit(args.root, args.directory)
    result = audit.run()
    if args.output:
        path = args.output.resolve()
        if path.is_relative_to(audit.stage):
            raise ValueError("audit sidecar must be outside the sealed production stage")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
    print(
        json.dumps(
            {
                "status": result["status"],
                "unique_tasks": result["unique_tasks"],
                "check_count": result["check_count"],
                "failure_count": len(result["failures"]),
                "failure_codes": dict(Counter(row["code"] for row in result["failures"])),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
