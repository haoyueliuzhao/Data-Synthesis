"""Offline complete-trajectory qualification for the three fixed eval structures.

Arithmetic proof uses free, source-bound symbols, not equality at the observed
answer. Argmax is a different proof domain: every actual-period candidate must
participate in an executed strict comparison/selection, then the secondary
amount must belong to its selected interval. Fine complete classes remain a
separate finite interpretation and may remain pending even when financially valid.
"""

import copy
import json
from fractions import Fraction

from ..finance_qa_vnext_catalog_bridge.assessment import (
    _expression,
    _rounded,
    _witness_expression,
)
from ..finance_qa_vnext_catalog_bridge.worker import UNITS, convert, encode, number, require, sha
from .periods import validate_final_period
from .runtime import actual_period, generate, record


def _body_valid(item):
    body = {key: value for key, value in item.items() if key != "id"}
    require(item["id"].split(":", 1)[1] == sha(encode(body)), "assessment.record_identity")


def replay_session(session, sources):
    _body_valid(session)
    replay = generate(
        session["public_messages"],
        session["identity"],
        sources,
        scripted=[turn["raw_response"] for turn in session["turns"]],
        requested_basis=session["requested_basis"],
        max_responses=session["max_responses"],
        max_tools=session["max_tools"],
    )
    keys = (
        "identity",
        "initial_messages",
        "public_messages",
        "source_descriptors",
        "events",
        "first_final_index",
        "raw_final",
        "max_responses",
        "max_tools",
    )
    require(
        all(replay[key] == session[key] for key in keys), "assessment.full_executed_history_replay"
    )
    require(len(replay["turns"]) == len(session["turns"]), "assessment.first_final_stop")
    for original, repeated in zip(session["turns"], replay["turns"], strict=True):
        require(
            all(
                original[key] == repeated[key]
                for key in (
                    "response_index",
                    "input_messages",
                    "raw_response",
                    "raw_response_sha256",
                )
            ),
            "assessment.raw_public_history_replay",
        )
    if session["terminal"] != "provider_error":
        require(session["terminal"] == replay["terminal"], "assessment.terminal_replay")
    else:
        require(
            session["first_final_index"] is None and session["provider_error"] is not None,
            "assessment.incomplete_provider_failure",
        )
    if session["origin"] == "scripted_evaluation_control":
        require(replay == session, "assessment.entire_saved_script_session_identity")
    return replay


def _native_identity(native):
    return {
        "entity_id": native["entity_id"],
        "metric_id": native["metric_id"],
        "source_definition_id": native["source_definition_id"],
        "native_definition": native["native_definition"],
        "tag": native["tag"],
        "actual_period": actual_period(native["record"]),
        "unit": "USD",
        "exact_value": str(number(native["record"]["val"])),
    }


class Support:
    def __init__(self, bundle, native_bindings, tools):
        import sympy

        self.sympy, self.tools, self.bindings = sympy, tools, native_bindings
        self.symbols, self.values, self.lookup = {}, {}, {}
        self.symbolic, self.dependencies, self.fact_uses = {}, {}, {}
        cluster = bundle["source_cluster"]
        for identifier, native in sorted(native_bindings.items()):
            if native.get("source_cluster") != cluster:
                continue
            identity = _native_identity(native)
            symbol = sympy.Symbol("native_" + sha(encode(identity)))
            self.symbols[identifier] = symbol
            self.values[symbol] = sympy.Rational(str(number(native["record"]["val"])))
            key = (native["raw_object_id"], native["pointer"], native["raw_sha256"])
            self.lookup.setdefault(key, {})[identifier] = native["record"]
            # The source registry already preserves explicit equal occurrences.
            # Only the same original concept/USD/actual interval/exact amount in
            # an annual filing can alias this fact. No scan by observed amount,
            # end-year label, or unregistered cross-snapshot source is performed.
            prefix = (
                "/facts/us-gaap/"
                + native["tag"].replace("~", "~0").replace("/", "~1")
                + "/units/USD/"
            )
            for occurrence in native.get("all_equal_source_occurrences", []):
                pointer, raw = occurrence.get("pointer"), occurrence.get("record")
                if not isinstance(pointer, str) or not isinstance(raw, dict):
                    continue
                if any(
                    occurrence.get(key, expected) != expected
                    for key, expected in {
                        "raw_object_id": native["raw_object_id"],
                        "raw_sha256": native["raw_sha256"],
                        "source_unit": "USD",
                        "unit": "USD",
                    }.items()
                ):
                    continue
                suffix = pointer[len(prefix) :] if pointer.startswith(prefix) else ""
                if (
                    not suffix.isdigit()
                    or suffix != str(int(suffix))
                    or raw.get("form") not in {"10-K", "10-K/A"}
                    or raw.get("start") != native["record"].get("start")
                    or raw.get("end") != native["record"].get("end")
                ):
                    continue
                try:
                    equivalent_amount = number(raw["val"]) == number(native["record"]["val"])
                except (KeyError, TypeError, ValueError):
                    continue
                if not equivalent_amount:
                    continue
                occurrence_key = (native["raw_object_id"], pointer, native["raw_sha256"])
                registered = self.lookup.setdefault(occurrence_key, {})
                require(
                    identifier not in registered or registered[identifier] == raw,
                    "assessment.conflicting_registered_source_occurrence",
                )
                registered[identifier] = raw

    def tool(self, identifier):
        require(
            identifier in self.tools and self.tools[identifier]["status"] == "ok",
            "assessment.successful_support_result_required",
        )
        return self.tools[identifier]

    def resolve(self, identifier):
        """Return an exact expression in canonical USD / dimensionless ratio."""
        if identifier in self.symbolic:
            return self.symbolic[identifier]
        tool = self.tool(identifier)
        result = tool["result"]
        used, facts = {identifier}, set()
        if tool["tool"] == "read_source":
            key = (result["source_id"], result["native_pointer"], result["source_raw_sha256"])
            candidates = self.lookup.get(key, {})
            require(candidates, "assessment.source_not_bound_to_native_fact")
            symbols = {self.symbols[candidate] for candidate in candidates}
            require(len(symbols) == 1, "assessment.ambiguous_native_record")
            for candidate in candidates:
                native = self.bindings[candidate]
                require(
                    candidates[candidate] == result["record"]
                    and actual_period(native["record"]) == result["actual_period"]
                    and result["concept"] == "us-gaap:" + native["tag"]
                    and result["source_unit"] == "USD",
                    "assessment.original_record_identity",
                )
                value, _ = convert(number(native["record"]["val"]), "USD", result["unit"])
                require(value == number(result["exact_value"]), "assessment.source_unit_value")
            facts.update(candidates)
            expression = next(iter(symbols))
        elif tool["tool"] == "calculate":
            variables = {}
            for name, resolved in result["resolved_variables"].items():
                reference = resolved["result_id"]
                if reference is None:
                    variables[name] = self.sympy.Rational(resolved["exact_value"])
                else:
                    variables[name] = self.resolve(reference)
                    used.update(self.dependencies[reference])
                    facts.update(self.fact_uses[reference])
            expression = _expression(result["expression"], variables, self.sympy)
        elif tool["tool"] == "lookup_selected":
            reference = result["source_result_id"]
            expression = self.resolve(reference)
            used.update(self.dependencies[reference])
            facts.update(self.fact_uses[reference])
            # Selection has its own proof domain, verified separately below.
            used.add(result["selection_result_id"])
        else:
            raise ValueError("assessment.not_a_financial_arithmetic_result")
        expression = self.sympy.cancel(expression)
        # The runtime executed the same source and unit conversion. Recheck the
        # source-substituted program, not only the target answer.
        exact = expression.subs(self.values)
        require(not exact.free_symbols, "assessment.unresolved_native_value")
        canonical, _ = convert(
            number(result["exact_value"]),
            result["unit"],
            "USD" if UNITS[result["unit"]][0] == "currency:USD" else "ratio",
        )
        require(exact == self.sympy.Rational(str(canonical)), "assessment.executed_symbolic_value")
        self.symbolic[identifier], self.dependencies[identifier], self.fact_uses[identifier] = (
            expression,
            used,
            facts,
        )
        return expression

    def equivalent(self, left, right):
        return self.sympy.cancel(left - right) == 0

    def period_metric_symbol(self, facts, metric, period):
        matching = [
            identifier
            for identifier in facts
            if self.bindings[identifier]["metric_id"] == metric
            and actual_period(self.bindings[identifier]["record"])["period_id"] == period
        ]
        symbols = {self.symbols[identifier] for identifier in matching}
        require(len(symbols) == 1, "assessment.unique_metric_actual_period_source")
        return next(iter(symbols))

    def selection(self, identifier, primary_symbols):
        tool = self.tool(identifier)
        require(tool["tool"] in {"select_max", "compare"}, "assessment.explicit_selection_required")
        result, represented, dependencies, fact_uses = tool["result"], {}, {identifier}, set()
        for input_id in result["used_result_ids"]:
            input_tool = self.tool(input_id)
            if input_tool["tool"] in {"select_max", "compare"}:
                _, _, subdependencies, subfacts = self.selection(input_id, primary_symbols)
                dependencies.update(subdependencies)
                fact_uses.update(subfacts)
        for candidate in result["selection_candidates"]:
            reference, period = candidate["result_id"], candidate["actual_period"]["period_id"]
            require(
                period in primary_symbols and period not in represented,
                "assessment.selection_unique_public_candidate_period",
            )
            expression = self.resolve(reference)
            require(
                self.equivalent(expression, primary_symbols[period]),
                "assessment.selection_candidate_not_primary_metric",
            )
            require(
                self.tools[reference]["result"].get("actual_period", {}).get("period_id") == period,
                "assessment.selection_candidate_interval",
            )
            represented[period] = expression
            dependencies.update(self.dependencies[reference])
            fact_uses.update(self.fact_uses[reference])
        require(len(represented) >= 2, "assessment.comparison_needs_candidates")
        numeric = {
            period: expression.subs(self.values) for period, expression in represented.items()
        }
        maximum = max(numeric.values())
        winners = [period for period, value in numeric.items() if value == maximum]
        require(
            len(winners) == 1 and result["actual_period"]["period_id"] == winners[0],
            "assessment.actual_unique_peak",
        )
        self.dependencies[identifier], self.fact_uses[identifier] = dependencies, fact_uses
        return winners[0], set(represented), dependencies, fact_uses


def _period_contract(bundle):
    public = bundle["public"]
    contract = public["period_contract"]
    require(contract["task_id"] == bundle["task_id"], "assessment.period_contract_task")
    periods = contract["periods"]
    identities = []
    for period in periods:
        native = actual_period(period)
        require(
            native["period_id"] == period["period_id"]
            and native["period_type"] == period["period_type"],
            "assessment.period_identity",
        )
        identities.append(period["period_id"])
    require(len(identities) == len(set(identities)), "assessment.unique_public_periods")
    target = bundle["private"]["canonical_target"]
    pairs = target.get("actual_periods")
    if pairs is None:
        pairs = [target["previous_period"], target["current_period"]]
    expected = {actual_period({"start": pair[0], "end": pair[1]})["period_id"] for pair in pairs}
    require(set(identities) == expected, "assessment.public_periods_match_canonical_target")
    require(
        contract["quantity"] == target["quantity"]
        and contract["metric_ids"] == (target.get("metric_ids") or [target["metric_id"]]),
        "assessment.public_quantity_metric_target",
    )
    expected_kind = {
        "three_annual_flow_mean": "arithmetic_mean",
        "three_year_peak_then_same_period_metric": "argmax_then_lookup",
        "difference": "difference",
        "relative_change": "relative_change",
    }[target["quantity"]]
    require(contract["operation"]["kind"] == expected_kind, "assessment.public_operation_target")
    if expected_kind in {"difference", "relative_change"}:
        require(
            contract["operation"].get("direction") == "current_minus_previous",
            "assessment.public_operation_direction",
        )
    return contract, identities


def _consume_certificate(bundle, native_bindings):
    """Consume exactly the registered growth wrapper without unwrapping its target.

    Completeness belongs to the base financial relation. The returned object is
    still the outer certificate, whose percentage witnesses and bindings remain
    authoritative inputs to the executed-support checks below. Unknown/nested
    wrappers cannot obtain admission by carrying a convenient complete flag.
    """
    certificate = bundle["private"]["relation_certificate"]
    schema = certificate.get("schema_version")
    prefix = "finance_qa_vnext_task_build.v1."
    if schema != prefix + "relative_quantity_certificate":
        require(
            "base_relation_certificate" not in certificate, "assessment.unknown_certificate_wrapper"
        )
        expected_kind = {
            "dual_sufficient": "financial_relation_certificate",
            "composition_required": "panel_composition_certificate",
            "other_financial": "panel_other_financial_certificate",
        }.get(bundle["family"])
        require(
            expected_kind is not None and schema == prefix + expected_kind,
            "assessment.unregistered_certificate_type",
        )
        require(
            bundle["private"]["canonical_target"]["quantity"] != "relative_change",
            "assessment.relative_registered_wrapper_required",
        )
        _body_valid(certificate)
        require(
            certificate.get("complete") is True, "assessment.source_relation_certificate_required"
        )
        return certificate
    import sympy

    _body_valid(certificate)
    target = bundle["private"]["canonical_target"]
    public = bundle["public"]
    operation = public["period_contract"]["operation"]
    require(
        bundle["family"] == "dual_sufficient"
        and target["quantity"] == certificate["quantity"] == "relative_change",
        "assessment.relative_wrapper_target_type",
    )
    require(
        target["unit"] == public["quantity_contract"]["unit"] == "percent"
        and operation.get("kind") == "relative_change"
        and operation.get("direction") == "current_minus_previous"
        and operation.get("denominator") == "strictly_positive_previous"
        and operation.get("multiplier") == 100,
        "assessment.relative_wrapper_quantity_contract",
    )
    base = certificate.get("base_relation_certificate")
    require(
        isinstance(base, dict)
        and base.get("schema_version") == prefix + "financial_relation_certificate"
        and "base_relation_certificate" not in base,
        "assessment.relative_registered_base_type",
    )
    _body_valid(base)
    require(base.get("complete") is True, "assessment.source_relation_certificate_required")
    require(
        certificate["family"] == base["family"]
        and base["family"] in {"annual_flow", "stock_rollforward"},
        "assessment.relative_wrapper_base_family",
    )
    for field in ("leaf_fact_ids", "public_fact_ids"):
        require(
            certificate[field] == base[field]
            and len(set(certificate[field])) == len(certificate[field]),
            "assessment.relative_wrapper_source_bindings",
        )
    require(
        set(base["public_fact_ids"]) <= set(base["leaf_fact_ids"]),
        "assessment.relative_public_leaf_subset",
    )
    require(
        all(
            identifier in native_bindings
            and native_bindings[identifier]["source_cluster"] == target["source_cluster"]
            for identifier in certificate["leaf_fact_ids"]
        ),
        "assessment.relative_native_source_cluster",
    )
    base_witnesses = {witness["basis"]: witness for witness in base["witnesses"]}
    outer_witnesses = {witness["basis"]: witness for witness in certificate["witnesses"]}
    require(
        len(base["witnesses"]) == len(certificate["witnesses"]) == 2
        and set(base_witnesses) == set(outer_witnesses) == {"endpoint", "movement"},
        "assessment.relative_both_registered_witnesses",
    )
    endpoints = base_witnesses["endpoint"]["input_bindings"]
    previous, current = endpoints["previous"], endpoints["current"]
    require(
        previous != current and target["previous_period"][1] < target["current_period"][1],
        "assessment.relative_forward_actual_periods",
    )
    for role, identifier in (("previous", previous), ("current", current)):
        native = native_bindings[identifier]
        require(
            native["metric_id"] == target["metric_id"]
            and [native["record"].get("start"), native["record"]["end"]]
            == list(target[role + "_period"]),
            "assessment.relative_endpoint_actual_metric_period",
        )
    require(
        number(native_bindings[previous]["record"]["val"]) > 0,
        "assessment.relative_strictly_positive_previous",
    )
    symbols = {identifier: sympy.Symbol(identifier) for identifier in certificate["leaf_fact_ids"]}
    previous_base = symbols[previous]
    components = base.get("previous_component_fact_ids")
    if components:
        coefficients = base.get("previous_component_coefficients") or [1] * len(components)
        previous_base = sum(
            symbols[identifier] * sympy.Rational(str(coefficient))
            for identifier, coefficient in zip(components, coefficients, strict=True)
        )
        substitutions = {
            symbols[key]: sympy.Rational(str(number(native_bindings[key]["record"]["val"])))
            for key in certificate["leaf_fact_ids"]
        }
        require(
            previous_base.subs(substitutions) == substitutions[symbols[previous]],
            "assessment.relative_reconstructed_previous_base",
        )
    for basis, outer in outer_witnesses.items():
        original = base_witnesses[basis]
        _body_valid(original)
        _body_valid(outer)
        require(
            all(
                outer["input_bindings"].get(name) == identifier
                for name, identifier in original["input_bindings"].items()
            )
            and set(outer["input_bindings"].values()) <= set(symbols),
            "assessment.relative_original_witness_bindings_preserved",
        )
        delta, _ = _witness_expression(original, symbols, sympy)
        if basis == "endpoint":
            require(
                sympy.cancel(delta - (symbols[current] - symbols[previous])) == 0,
                "assessment.relative_base_delta_direction",
            )
        denominator = previous_base if basis == "movement" else symbols[previous]
        expression, steps = _witness_expression(outer, symbols, sympy)
        require(
            "change" in steps
            and sympy.cancel(steps["change"] - delta) == 0
            and sympy.cancel(expression - 100 * delta / denominator) == 0,
            "assessment.relative_outer_percentage_witness",
        )
        final_step = next(
            step
            for step in outer["operator_dag"]["operators"]
            if step["step_id"] == outer["operator_dag"]["output_step"]
        )
        require(
            final_step["operator"] == "ratio_percent",
            "assessment.relative_percentage_output_operator",
        )
    return certificate


def assess_session(session, bundle, native_bindings, sources):
    """Private contract/native bindings enter only this offline replay boundary."""
    require(
        bundle["task_id"] == session["identity"]["task_id"]
        and bundle["family"] == session["identity"]["family"],
        "assessment.task_identity",
    )
    require(
        bundle["public"] == json.loads(session["public_messages"][0]["content"]),
        "assessment.frozen_public_join",
    )
    replay_session(session, sources)
    outcome = {
        "task_id": bundle["task_id"],
        "bundle_id": bundle.get("id"),
        "session_id": session["id"],
        "financial_valid": False,
        "complete_trajectory_qualified": False,
        "is_primary_utility_score": True,
        "quantity_status": "UNDETERMINED",
        "support_status": "UNDETERMINED",
        "actual_method": "UNDETERMINED",
        "full_mapping_status": "PENDING_REVIEW",
        "full_class": None,
        "first_final_index": session["first_final_index"],
        "reason": None,
        "requested_basis": session["requested_basis"],
        "origin": session["origin"],
        "training_eligible": False,
        "raw_history_and_tools_replayed": True,
        "method_from_requested_label": False,
        "method_from_answer_equality": False,
        "method_from_oracle_string_equality": False,
        "argmax_proof_domain": "executed_complete_actual_period_comparison_then_same_period_lookup",
        "financial_and_complete_class_separate": True,
        "primary_qualification_requires_fine_class_mapping": False,
        "primary_qualification_rule": (
            "correct first Final plus complete executed source/unit/actual-period/support proof"
        ),
        "fine_mapping_required_for_training_stratification": True,
        "pending_fine_classes_retained_without_filling_training_quotas": True,
        "certificate_consumer_revision": (
            "registered_relative_wrapper.v1.base_complete_outer_target"
        ),
        "support_assessment_entered": False,
    }
    if session["first_final_index"] is None:
        return record("evaluation_assessment", **{**outcome, "reason": "no_final"})
    final = session["raw_final"]
    if not isinstance(final, dict) or not {"value", "unit", "result_id"} <= set(final):
        return record("evaluation_assessment", **{**outcome, "reason": "final_shape_or_reference"})
    tools = {
        event["tool_call"]["call_id"]: event["tool_call"]
        for event in session["events"]
        if event["tool_call"]
    }
    try:
        contract, periods = _period_contract(bundle)
        certificate = _consume_certificate(bundle, native_bindings)
        facts = certificate["leaf_fact_ids"]
        require(
            all(identifier in native_bindings for identifier in facts),
            "assessment.native_certificate_join",
        )
        outcome["support_assessment_entered"] = True
        support = Support(bundle, native_bindings, tools)
        expression = support.resolve(final["result_id"])
        target = bundle["private"]["canonical_target"]
        target_unit = target["unit"]
        submitted, _ = convert(number(final["value"]), final["unit"], target_unit)
        supported, _ = convert(
            number(tools[final["result_id"]]["result"]["exact_value"]),
            tools[final["result_id"]]["result"]["unit"],
            target_unit,
        )
        places = bundle["public"]["quantity_contract"]["decimal_places"]
        require(
            _rounded(submitted, places) == _rounded(supported, places),
            "assessment.final_not_supported_by_result",
        )
        dependencies = set(support.dependencies[final["result_id"]])
        replacements, selected_period = {}, None
        if bundle["family"] == "composition_required":
            require(len(periods) == 3, "assessment.exact_three_mean_periods")
            metric = target["metric_ids"][0]
            components = [support.period_metric_symbol(facts, metric, period) for period in periods]
            expected = sum(components) / 3
            require(
                support.equivalent(expression, expected),
                "assessment.mean_requires_all_three_actual_interval_amounts",
            )
            method = "temporal_component_integration"
        elif bundle["family"] == "other_financial":
            require(len(periods) == 3, "assessment.exact_three_peak_periods")
            primary, secondary = target["metric_ids"]
            primary_symbols = {
                period: support.period_metric_symbol(facts, primary, period) for period in periods
            }
            selection_id = final.get("selection_result_id")
            support_selections = {
                tools[identifier]["result"]["selection_result_id"]
                for identifier in dependencies
                if tools[identifier]["tool"] == "lookup_selected"
            }
            if selection_id is not None:
                support_selections.add(selection_id)
            require(
                len(support_selections) == 1, "assessment.one_actual_selection_support_required"
            )
            selection_id = next(iter(support_selections))
            selected_period, represented, selection_dependencies, _ = support.selection(
                selection_id, primary_symbols
            )
            require(
                represented == set(periods), "assessment.peak_requires_all_three_candidate_periods"
            )
            require(
                validate_final_period(final, contract, selected_period)["passed"],
                "assessment.final_selected_actual_period",
            )
            expected = support.period_metric_symbol(facts, secondary, selected_period)
            require(
                support.equivalent(expression, expected),
                "assessment.secondary_not_supported_in_selected_actual_period",
            )
            dependencies.update(selection_dependencies)
            method = "peak_selection_then_metric_lookup"
        elif bundle["family"] == "dual_sufficient":
            # Witnesses describe admitted public relations, not mandatory program strings.
            # Normalize all native symbols to the witnesses' million-USD convention.
            million_symbols = {
                identifier: symbol / 1000000 for identifier, symbol in support.symbols.items()
            }
            witnesses = {
                witness["basis"]: (
                    witness,
                    *_witness_expression(witness, million_symbols, support.sympy),
                )
                for witness in certificate["witnesses"]
            }
            endpoint, movement = witnesses.get("endpoint"), witnesses.get("movement")
            require(
                endpoint is not None and movement is not None,
                "assessment.dual_sufficient_relations",
            )
            factor = support.sympy.Rational(str(UNITS[target_unit][1]))
            expected = endpoint[1] * factor
            direct_matches = [
                basis
                for basis, (_, expr, _) in witnesses.items()
                if support.equivalent(expression, expr * factor)
            ]
            if direct_matches:
                method = direct_matches[0]
            else:
                endpoint_inputs = endpoint[0]["input_bindings"]
                previous = million_symbols[endpoint_inputs["previous"]]
                base_certificate = certificate.get("base_relation_certificate", certificate)
                base_ids = base_certificate.get("previous_component_fact_ids")
                base = previous
                if base_ids:
                    coefficients = base_certificate.get("previous_component_coefficients") or [
                        1
                    ] * len(base_ids)
                    base = sum(
                        million_symbols[identifier] * support.sympy.Rational(str(coefficient))
                        for identifier, coefficient in zip(base_ids, coefficients, strict=True)
                    )
                    replacements[support.symbols[endpoint_inputs["previous"]]] = base * 1000000
                delta = movement[2].get("change", movement[1])
                replacements[support.symbols[endpoint_inputs["current"]]] = (base + delta) * 1000000
                require(
                    support.equivalent(
                        expression.subs(replacements, simultaneous=True),
                        expected.subs(replacements, simultaneous=True),
                    ),
                    "assessment.not_equivalent_under_admitted_public_relations",
                )
                method = "hybrid_public_sufficient_relation"
        else:
            raise ValueError("assessment.unregistered_evaluation_structure")
        exact_expected = expected.subs(support.values)
        require(not exact_expected.free_symbols, "assessment.target_native_values")
        expected_in_unit = Fraction(str(exact_expected)) / UNITS[target_unit][1]
        correct = _rounded(submitted, places) == _rounded(expected_in_unit, places)
        outcome.update(
            financial_valid=correct,
            complete_trajectory_qualified=correct,
            quantity_status="PASS" if correct else "FAIL",
            support_status="PASS",
            actual_method=method,
            support_result_ids=sorted(dependencies),
            selected_actual_period=selected_period,
            reason=None if correct else "wrong_final_quantity",
        )
        pending, signature_events, revisions = [], [], []
        revised = {
            tool["result"].get("revises_result_id")
            for tool in tools.values()
            if tool["status"] == "ok" and tool["tool"] == "calculate"
        }
        for identifier, tool in tools.items():
            entry = {
                "result_id": identifier,
                "tool": tool["tool"],
                "status": tool["status"],
                "role": "final_support" if identifier in dependencies else "source_exploration",
            }
            if tool["status"] != "ok":
                pending.append("failed_tool_complete_class_review")
                entry["error"] = tool.get("error")
                signature_events.append(entry)
                continue
            result = tool["result"]
            if tool["tool"] in {"read_source", "calculate", "lookup_selected"}:
                try:
                    expr = support.resolve(identifier)
                    entry.update(
                        canonical_program=str(expr),
                        unit=result["unit"],
                        used_result_ids=sorted(result.get("used_result_ids", [])),
                        source_locator=result.get("source_locator"),
                    )
                    if tool["tool"] == "calculate" and identifier not in dependencies:
                        if support.equivalent(expr, expression):
                            entry["role"] = "redundant_target_recomputation"
                        elif support.equivalent(
                            expr.subs(replacements, simultaneous=True),
                            expected.subs(replacements, simultaneous=True),
                        ):
                            entry["role"] = "alternative_basis_target_cross_check"
                        elif identifier in revised:
                            entry["role"] = "explicitly_revised_calculation"
                        else:
                            pending.append("non_support_calculation_intent_unresolved")
                    if result.get("revises_result_id"):
                        revisions.append(
                            {
                                "from_result_id": result["revises_result_id"],
                                "to_result_id": identifier,
                                "substantive_program_change": not support.equivalent(
                                    expr, support.resolve(result["revises_result_id"])
                                ),
                            }
                        )
                except (ValueError, KeyError, TypeError) as error:
                    pending.append(str(error))
                    entry["mapping_reason"] = str(error)
            elif tool["tool"] in {"select_max", "compare"}:
                entry.update(
                    selected_actual_period=result["actual_period"],
                    selection_candidates=copy.deepcopy(result["selection_candidates"]),
                    used_result_ids=result["used_result_ids"],
                    comparison=result["comparison"],
                )
            else:
                entry["source_query"] = copy.deepcopy(tool["arguments"])
            signature_events.append(entry)
        if any(event["protocol_error"] for event in session["events"]):
            pending.append("format_recovery_complete_class_review")
        if method == "hybrid_public_sufficient_relation":
            pending.append("hybrid_method_complete_class_review")
        signature = record(
            "evaluation_complete_signature",
            task_id=bundle["task_id"],
            surface_version_id=session["identity"]["surface_version_id"],
            actual_method=method,
            canonical_final_program=str(expression),
            selected_actual_period=selected_period,
            events=signature_events,
            revision_edges=revisions,
            first_final_result_id=final["result_id"],
            requested_basis_omitted=True,
            original_expression_spelling_omitted=True,
        )
        outcome.update(
            full_mapping_status="MAPPED" if not pending else "PENDING_REVIEW",
            full_class=signature["id"] if not pending else None,
            full_signature=signature,
            full_mapping_pending_reasons=sorted(set(pending)),
        )
    except (
        ValueError,
        TypeError,
        KeyError,
        ZeroDivisionError,
        SyntaxError,
        RecursionError,
    ) as error:
        outcome.update(reason=str(error), support_status="UNDETERMINED")
    return record("evaluation_assessment", **outcome)
