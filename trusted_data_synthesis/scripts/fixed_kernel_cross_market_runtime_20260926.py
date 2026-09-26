"""PDF-native given-sources runtime for the independent cross-market calibration.

The five actions, prompt and complete-trajectory proof rule are retained. Native
currency conversion, multi-document provenance and PDF fact binding are new and
are explicitly versioned; this is not an unchanged SEC/US-GAAP scorer. No source
selection, private answer, filesystem reads or model transport enter online tools.
"""

from __future__ import annotations

import ast
import copy
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import fixed_kernel_source_view_runtime_20260915 as prior

from trusted_synthesis.experiments.finance_qa_vnext_autonomous_formula.online.calculator import (
    calculate,
)

p, runtime, assessment = prior.p, prior.runtime, prior.assessment
number, require = prior.training.number, prior.training.require
SYSTEM = prior.SYSTEM
PUBLIC_FIELDS = prior.PUBLIC_FIELDS | {"source_documents"}
CURRENCIES = ("CNY", "HKD", "USD")
UNITS = {"ratio": ("dimensionless", Fraction(1)), "percent": ("dimensionless", Fraction(1, 100))}
for _currency in CURRENCIES:
    for _prefix, _scale in (("", 1), ("thousand ", 1000), ("million ", 1000000)):
        UNITS[_prefix + _currency] = ("currency:" + _currency, Fraction(_scale))


def convert(value, source_unit, target_unit):
    require(source_unit in UNITS and target_unit in UNITS, "cross_market.known_native_unit")
    left, right = UNITS[source_unit], UNITS[target_unit]
    require(left[0] == right[0], "cross_market.no_cross_currency_conversion")
    factor = left[1] / right[1]
    return value * factor, {
        "from_unit": source_unit,
        "to_unit": target_unit,
        "factor": str(factor),
        "input_exact_value": str(value),
        "output_exact_value": str(value * factor),
    }


def canonical_unit(unit):
    require(unit in UNITS, "cross_market.known_native_unit")
    dimension = UNITS[unit][0]
    return dimension.split(":", 1)[1] if dimension.startswith("currency:") else "ratio"


def calculate_with_units(arguments, previous):
    require(isinstance(arguments, dict), "tool.calculate_arguments")
    revision = arguments.get("revises_result_id")
    require(
        revision is None or (revision in previous and previous[revision]["tool"] == "calculate"),
        "tool.revision_requires_prior_calculation",
    )
    computed = calculate(arguments, previous)
    normalized, dimensions, conversions, currencies = {}, {}, [], set()
    for name, resolved in computed["resolved_variables"].items():
        reference = resolved["result_id"]
        if reference is None:
            normalized[name], dimensions[name] = resolved["exact_value"], 0
            continue
        result = previous[reference]["result"]
        canonical = canonical_unit(result["unit"])
        if canonical != "ratio":
            currencies.add(canonical)
        value, conversion = convert(number(result["exact_value"]), result["unit"], canonical)
        normalized[name], dimensions[name] = str(value), int(canonical != "ratio")
        conversions.append({"variable": name, "result_id": reference, **conversion})
    require(len(currencies) <= 1, "cross_market.no_cross_currency_arithmetic")

    def dimension(node):
        if isinstance(node, ast.Constant):
            return 0
        if isinstance(node, ast.Name):
            return dimensions[node.id]
        if isinstance(node, ast.UnaryOp):
            return dimension(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = dimension(node.left), dimension(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                require(left == right, "tool.unit_addition_conflict")
                return left
            if isinstance(node.op, ast.Mult):
                return left + right
            if isinstance(node.op, ast.Div):
                return left - right
            require(
                right == 0
                and isinstance(node.right, ast.Constant)
                and type(node.right.value) is int,
                "tool.unit_power_exponent",
            )
            return left * node.right.value
        if isinstance(node, ast.Call):
            children = (
                node.args[0].elts
                if len(node.args) == 1 and isinstance(node.args[0], (ast.List, ast.Tuple))
                else node.args
            )
            values = [dimension(child) for child in children]
            require(len(set(values)) == 1, "tool.unit_function_conflict")
            return values[0]
        raise ValueError("tool.unsupported_unit_expression")

    dim = dimension(ast.parse(arguments["expression"], mode="eval").body)
    require(dim in {0, 1}, "tool.unsupported_result_dimension")
    require(not dim or len(currencies) == 1, "cross_market.currency_amount_requires_source")
    canonical = next(iter(currencies)) if dim else "ratio"
    normalized_result = calculate(
        {"expression": arguments["expression"], "variables": normalized}, {}
    )
    target = arguments.get("unit", canonical)
    value, final_conversion = convert(number(normalized_result["exact_value"]), canonical, target)
    return {
        **computed,
        "exact_value": str(value),
        "value": str(value),
        "unit": target,
        "canonical_expression_value": normalized_result["exact_value"],
        "operand_conversions": conversions,
        "conversion": final_conversion,
        "source_declarations_validated": False,
        "revises_result_id": revision,
    }


class SourceViewSources:
    def __init__(self, public):
        self.public = copy.deepcopy(public)
        self.references = {row["source_id"]: row for row in self.public["sources"]}
        require(len(self.references) == len(public["sources"]), "cross_market.unique_source_ids")
        documents = {row["raw_object_id"]: row for row in public["source_documents"]}
        require(len(documents) == len(public["source_documents"]), "cross_market.unique_documents")
        for source in self.references.values():
            require(
                source["source_kind"] == "official_report_pdf_numeric_record"
                and source["unit"] in CURRENCIES
                and source["raw_object_id"] in documents
                and source["native_pointer"].startswith("pdf://" + source["raw_sha256"] + "#"),
                "cross_market.real_pdf_native_source",
            )
            document = documents[source["raw_object_id"]]
            require(
                document["raw_sha256"] == source["raw_sha256"]
                and document["original_url"] == source["original_url"],
                "cross_market.exact_original_document_join",
            )
            runtime.actual_period(source["record"])
            number(source["record"]["val"])

    def descriptors(self):
        return copy.deepcopy(self.public["sources"])

    def read_source(self, arguments):
        require(
            isinstance(arguments, dict) and set(arguments) <= {"source_id", "unit"},
            "cross_market.numeric_pdf_read_arguments",
        )
        require(arguments.get("source_id") in self.references, "tool.unknown_public_source")
        source = self.references[arguments["source_id"]]
        target = arguments.get("unit", source["unit"])
        value, conversion = convert(number(source["record"]["val"]), source["unit"], target)
        return {
            "exact_value": str(value),
            "unit": target,
            "source_id": source["raw_object_id"],
            "source_view_id": source["source_id"],
            "native_pointer": source["native_pointer"],
            "concept": source["concept"],
            "source_locator": {
                "source_id": source["source_id"],
                "native_pointer": source["native_pointer"],
            },
            "source_raw_sha256": source["raw_sha256"],
            "source_url": source["original_url"],
            "source_unit": source["unit"],
            "record": copy.deepcopy(source["record"]),
            "original_source_fragment": copy.deepcopy(source["evidence"]),
            "actual_period": runtime.actual_period(source["record"]),
            "conversion": conversion,
            "used_result_ids": [],
            "financial_meaning_certified": False,
            "source_mapping_is_mechanical_not_a_private_fact_lookup": True,
        }


def _selected(arguments, outputs, *, pairwise=False):
    arguments = copy.deepcopy(arguments)
    if "unit" not in arguments:
        reference = arguments["left_result_id"] if pairwise else arguments["result_ids"][0]
        arguments["unit"] = runtime._numeric(reference, outputs)["unit"]
    selected = prior.isolation.clone_function(
        runtime._selected, {**vars(runtime), "convert": convert}
    )
    return selected(arguments, outputs, pairwise=pairwise)


def execute(tool, arguments, sources, outputs):
    require(tool in prior.TOOLS, "source_view.unknown_tool")
    invoke = prior.isolation.clone_function(
        runtime.execute,
        {**vars(runtime), "calculate_with_units": calculate_with_units, "_selected": _selected},
    )
    return invoke(tool, arguments, sources, outputs)


def _native_identity(native):
    return {
        key: native[key]
        for key in (
            "entity_id",
            "metric_id",
            "source_definition_id",
            "native_definition",
            "currency",
            "statement_scope",
        )
    } | {
        "actual_period": runtime.actual_period(native["record"]),
        "exact_value": str(number(native["record"]["val"])),
    }


class Support(assessment.Support):
    """Same free-symbol proof domain; only exact PDF bindings can supply symbols."""

    def __init__(self, bundle, native_bindings, tools):
        import sympy

        self.sympy, self.tools, self.bindings = sympy, tools, native_bindings
        self.symbols, self.values, self.lookup = {}, {}, {}
        self.symbolic, self.dependencies, self.fact_uses = {}, {}, {}
        for identifier, native in sorted(native_bindings.items()):
            if native.get("source_cluster") != bundle["source_cluster"]:
                continue
            require(native["currency"] in CURRENCIES, "cross_market.native_currency_binding")
            symbol = sympy.Symbol("native_" + p.sha(p.encode(_native_identity(native))))
            self.symbols[identifier] = symbol
            self.values[symbol] = sympy.Rational(str(number(native["record"]["val"])))
            key = native["raw_object_id"], native["native_pointer"], native["raw_sha256"]
            self.lookup.setdefault(key, {})[identifier] = native["record"]

    def resolve(self, identifier):
        if identifier in self.symbolic:
            return self.symbolic[identifier]
        tool = self.tool(identifier)
        result = tool["result"]
        used, facts = {identifier}, set()
        if tool["tool"] == "read_source":
            candidates = self.lookup.get(
                (result["source_id"], result["native_pointer"], result["source_raw_sha256"]), {}
            )
            require(candidates, "assessment.source_not_bound_to_native_fact")
            symbols = {self.symbols[candidate] for candidate in candidates}
            require(len(symbols) == 1, "assessment.ambiguous_native_record")
            for candidate in candidates:
                native = self.bindings[candidate]
                require(
                    candidates[candidate] == result["record"]
                    and runtime.actual_period(native["record"]) == result["actual_period"]
                    and result["concept"] == "pdf-financial:" + native["metric_id"]
                    and result["source_unit"] == native["currency"],
                    "cross_market.original_pdf_record_identity",
                )
                value, _ = convert(
                    number(native["record"]["val"]), native["currency"], result["unit"]
                )
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
            expression = assessment._expression(result["expression"], variables, self.sympy)
        elif tool["tool"] == "lookup_selected":
            reference = result["source_result_id"]
            expression = self.resolve(reference)
            used.update(self.dependencies[reference])
            facts.update(self.fact_uses[reference])
            used.add(result["selection_result_id"])
        else:
            raise ValueError("assessment.not_a_financial_arithmetic_result")
        expression = self.sympy.cancel(expression)
        exact = expression.subs(self.values)
        require(not exact.free_symbols, "assessment.unresolved_native_value")
        canonical, _ = convert(
            number(result["exact_value"]), result["unit"], canonical_unit(result["unit"])
        )
        require(exact == self.sympy.Rational(str(canonical)), "assessment.executed_symbolic_value")
        self.symbolic[identifier], self.dependencies[identifier], self.fact_uses[identifier] = (
            expression,
            used,
            facts,
        )
        return expression


def binding():
    return p.record(
        "cross_market_source_runtime_binding",
        version="pdf_native_currency_given_sources.v1:20260926",
        source_sha256=p.sha(Path(__file__)),
        SYSTEM_sha256=p.sha(SYSTEM),
        original_runtime_sha256=p.sha(Path(runtime.__file__)),
        original_assessment_sha256=p.sha(Path(assessment.__file__)),
        original_training_tools_sha256=p.sha(Path(prior.training.__file__)),
        tools=sorted(prior.TOOLS),
        currencies=list(CURRENCIES),
        no_cross_currency_arithmetic=True,
        online_and_replay_same_runtime=True,
        source_currency_adapter_changed=True,
        financial_support_principle=(
            "first Final plus executed free-symbol source/units/actual-period proof"
        ),
        source_kind="official_report_pdf_numeric_record",
        complete_PDF_and_page_text_audit_references_not_new_model_tools=True,
    )


def build_runtime():
    registered = binding()
    public_document = prior.isolation.clone_function(
        prior.public_document, {**vars(prior), "PUBLIC_FIELDS": PUBLIC_FIELDS}
    )

    def record(kind, **fields):
        if kind == "evaluation_session":
            fields.update(
                source_view_runtime_binding_id=registered["id"],
                utility_environment="J_sources_cross_market_PDF_not_SEC_snapshot",
                starts_without_Probe_history=True,
            )
        return runtime.record(kind, **fields)

    namespace = {
        **vars(runtime),
        "SYSTEM": SYSTEM,
        "public_document": public_document,
        "execute": execute,
        "record": record,
    }
    generate = prior.isolation.clone_function(runtime.generate, namespace)
    offline = {
        **vars(assessment),
        "generate": generate,
        "Support": Support,
        "convert": convert,
        "UNITS": UNITS,
    }
    replay = prior.isolation.clone_function(assessment.replay_session, offline)
    offline["replay_session"] = replay
    assess = prior.isolation.clone_function(assessment.assess_session, offline)

    def checked_assess(session, bundle, native_bindings, sources):
        # Broken private preparation is an execution failure, never a model Q=0.
        # Only a valid, pre-admitted task reaches the scorer's response-error domain.
        assessment._period_contract(bundle)
        certificate = assessment._consume_certificate(bundle, native_bindings)
        require(
            all(key in native_bindings for key in certificate["leaf_fact_ids"]),
            "cross_market.complete_private_native_bindings",
        )
        Support(bundle, native_bindings, {})
        return assess(session, bundle, native_bindings, sources)

    return SimpleNamespace(
        generate=generate,
        replay_session=replay,
        assess_session=checked_assess,
        Sources=SourceViewSources,
        SYSTEM=SYSTEM,
        binding=registered,
    )
