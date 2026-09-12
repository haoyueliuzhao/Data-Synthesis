"""New evaluation-structure controls only; no historic script re-materialization.

Fixtures below are synthetic, while the same public runtime and offline assessor
are called by the production control dispatcher with manifest-bound panel bundles.
No tokenizer, model, API sender, GPU, or training material writer is imported.
"""

import copy
from pathlib import Path

from .assessment import assess_session
from .periods import build_contract
from .runtime import SnapshotSources, actual_period, encode, generate, number, record, require, sha


def read(tag, index, *, unit="million USD", source_id="snapshot"):
    return {
        "tool": "read_source",
        "arguments": {
            "source_id": source_id,
            "native_pointer": f"/facts/us-gaap/{tag}/units/USD/{index}",
            "unit": unit,
        },
    }


def calculate(expression, **references):
    return {
        "tool": "calculate",
        "arguments": {
            "expression": expression,
            "variables": {name: {"result_id": reference} for name, reference in references.items()},
            "unit": "million USD",
        },
    }


def final(value, result_id, **fields):
    return {"final": {"value": str(value), "unit": "million USD", "result_id": result_id, **fields}}


def synthetic_fixture(family="composition_required", *, fiscal=True, quantity=None):
    if fiscal:
        pairs = [
            ("2019-09-30", "2020-09-27"),
            ("2020-09-28", "2021-09-26"),
            ("2021-09-27", "2022-09-25"),
        ]
    else:
        pairs = [(f"{year}-01-01", f"{year}-12-31") for year in (2020, 2021, 2022)]
    definitions = {
        "Revenue": ("revenue", [100, 300, 200] if family == "other_financial" else [100, 200, 300]),
        "NetIncomeLoss": ("net_income", [9, 9, 13]),
        "GrossProfit": ("gross_profit", [40, 70, 100]),
        "CostOfRevenue": ("cost_of_revenue", [60, 130, 200]),
    }
    if family == "dual_sufficient":
        definitions["Revenue"] = ("revenue", [100, 200, 300])
    payload = {"cik": 42, "entityName": "Synthetic Financial Control", "facts": {"us-gaap": {}}}
    facts, native = {}, {}
    for tag, (metric, values) in definitions.items():
        description = (
            "revenue less cost of goods and services sold"
            if tag == "GrossProfit"
            else "Synthetic " + metric
        )
        concept = {"label": metric, "description": description, "units": {"USD": []}}
        payload["facts"]["us-gaap"][tag] = concept
        for index, (pair, amount) in enumerate(zip(pairs, values, strict=True)):
            raw = {
                "start": pair[0],
                "end": pair[1],
                "val": amount * 1000000,
                "accn": "synthetic-annual-report",
                "fy": 2022,
                "form": "10-K",
                "filed": "2023-02-01",
            }
            concept["units"]["USD"].append(raw)
            identifier = f"fact:{metric}:{index}"
            facts[identifier] = {
                "fact_id": identifier,
                "entity_id": "entity:42",
                "metric_id": metric,
                "period_start": pair[0],
                "period_end": pair[1],
            }
            native[identifier] = {
                "entity_id": "entity:42",
                "source_cluster": "cik:0000000042",
                "metric_id": metric,
                "source_definition_id": "definition:" + tag,
                "native_definition": {"label": metric, "description": description},
                "tag": tag,
                "raw_object_id": "snapshot",
                "pointer": f"/facts/us-gaap/{tag}/units/USD/{index}",
                "record": copy.deepcopy(raw),
            }
    # An unselected concept and a different unit remain publicly accessible.
    payload["facts"]["us-gaap"]["UnselectedControl"] = {
        "label": "Unselected public evidence",
        "description": "Not a target leaf.",
        "units": {
            "USD": [{"start": "2001-01-01", "end": "2001-12-31", "val": 777}],
            "shares": [{"end": "2022-09-25", "val": 42}],
        },
    }
    sources = SnapshotSources.synthetic({"snapshot": payload})
    for bound in native.values():
        bound["raw_sha256"] = sources.references["snapshot"]["complete_original_snapshot"]["sha256"]
    task_id = "synthetic_eval:" + family + (":" + str(quantity) if quantity else "")
    target = {
        "source_cluster": "cik:0000000042",
        "actual_periods": pairs,
        "current_period": pairs[-1],
        "unit": "million USD",
        "currency": "USD",
    }
    witnesses = []
    if family == "composition_required":
        target.update(quantity="three_annual_flow_mean", metric_ids=["revenue"])
        leaves = [f"fact:revenue:{index}" for index in range(3)]
    elif family == "other_financial":
        target.update(
            quantity="three_year_peak_then_same_period_metric", metric_ids=["revenue", "net_income"]
        )
        leaves = [
            f"fact:{metric}:{index}" for metric in ("revenue", "net_income") for index in range(3)
        ]
    else:
        target.update(
            quantity=quantity or "difference",
            metric_id="gross_profit",
            previous_period=pairs[0],
            current_period=pairs[1],
            actual_periods=pairs[:2],
        )
        if quantity == "relative_change":
            target["unit"] = "percent"
        leaves = [
            f"fact:{metric}:{index}"
            for metric in ("gross_profit", "revenue", "cost_of_revenue")
            for index in range(2)
        ]
        endpoint = {
            "basis": "endpoint",
            "input_bindings": {"previous": "fact:gross_profit:0", "current": "fact:gross_profit:1"},
            "operator_dag": {
                "operators": [
                    {
                        "step_id": "change",
                        "operator": "difference",
                        "inputs": [{"binding": "previous"}, {"binding": "current"}],
                    }
                ],
                "output_step": "change",
            },
        }
        movement = {
            "basis": "movement",
            "input_bindings": {
                "r0": "fact:revenue:0",
                "c0": "fact:cost_of_revenue:0",
                "r1": "fact:revenue:1",
                "c1": "fact:cost_of_revenue:1",
            },
            "operator_dag": {
                "operators": [
                    {
                        "step_id": "change",
                        "operator": "linear_combination",
                        "inputs": [{"binding": key} for key in ("r0", "c0", "r1", "c1")],
                        "params": {"coefficients": [-1, 1, 1, -1]},
                    }
                ],
                "output_step": "change",
            },
        }
        if quantity == "relative_change":
            for witness in (endpoint, movement):
                witness["input_bindings"]["base"] = "fact:gross_profit:0"
                witness["operator_dag"]["operators"].append(
                    {
                        "step_id": "answer",
                        "operator": "ratio_percent",
                        "inputs": [{"step": "change"}, {"binding": "base"}],
                    }
                )
                witness["operator_dag"]["output_step"] = "answer"
        witnesses = [endpoint, movement]
    item = {"task_id": task_id, "target": target, "match": {"fact_ids": leaves}}
    contract = build_contract(item, facts, native)
    public = {
        "question": "Synthetic exact-source trajectory control.",
        "source_document": sources.descriptors()[0],
        "period_contract": contract,
        "quantity_contract": {"unit": target["unit"], "decimal_places": 2},
        "source_policy": "All original concepts and observations remain available.",
        "tool_contract": {"first_final": "stop"},
    }
    certificate = {"complete": True, "leaf_fact_ids": leaves, "witnesses": witnesses}
    if family == "dual_sufficient":
        certificate.update(
            previous_component_fact_ids=["fact:revenue:0", "fact:cost_of_revenue:0"],
            previous_component_coefficients=[1, -1],
        )
    bundle = record(
        "synthetic_evaluation_bundle",
        task_id=task_id,
        family=family,
        source_cluster="cik:0000000042",
        public=public,
        private={"canonical_target": target, "relation_certificate": certificate},
    )
    messages = [{"role": "user", "content": encode(public).decode()}]
    identity = {
        "task_id": task_id,
        "family": family,
        "surface_version_id": "surface:synthetic",
        "public_messages_sha256": sha(encode(messages)),
        "parent_manifest_id": "manifest:synthetic",
    }
    return {
        "bundle": bundle,
        "native_bindings": native,
        "sources": sources,
        "messages": messages,
        "identity": identity,
    }


def synthetic_cases():
    mean = synthetic_fixture()
    base_mean = [read("Revenue", index) for index in range(3)]
    mean_avg = [
        *base_mean,
        calculate("avg(a,b,c)", a="tool:1", b="tool:2", c="tool:3"),
        final(200, "tool:4"),
    ]
    peak = synthetic_fixture("other_financial")
    periods = peak["bundle"]["public"]["period_contract"]["periods"]
    peak_base = [
        *[read("Revenue", index) for index in range(3)],
        {"tool": "select_max", "arguments": {"result_ids": ["tool:1", "tool:2", "tool:3"]}},
        read("NetIncomeLoss", 1),
    ]
    peak_final = final(9, "tool:5", selection_result_id="tool:4", period_id=periods[1]["period_id"])
    dual = synthetic_fixture("dual_sufficient")
    endpoint = [
        read("GrossProfit", 0),
        read("GrossProfit", 1),
        calculate("b-a", a="tool:1", b="tool:2"),
        final(30, "tool:3"),
    ]
    movement = [
        read("Revenue", 0),
        read("CostOfRevenue", 0),
        read("Revenue", 1),
        read("CostOfRevenue", 1),
        calculate("(r1-c1)-(r0-c0)", r0="tool:1", c0="tool:2", r1="tool:3", c1="tool:4"),
        final(30, "tool:5"),
    ]
    cases = [
        ("mean_avg", mean, mean_avg, True, "MAPPED"),
        (
            "mean_equivalent_multistep",
            mean,
            [
                *base_mean,
                calculate("a+b", a="tool:1", b="tool:2"),
                calculate("(ab+c)/3", ab="tool:4", c="tool:3"),
                final(200, "tool:5"),
            ],
            True,
            "MAPPED",
        ),
        (
            "mean_omitted_middle_coincidental_equal",
            mean,
            [
                read("Revenue", 0),
                read("Revenue", 2),
                calculate("avg(a,c)", a="tool:1", c="tool:2"),
                final(200, "tool:3"),
            ],
            False,
            "PENDING_REVIEW",
        ),
        (
            "mean_unsupported_amount_literal",
            mean,
            [
                *base_mean[:2],
                calculate("(a+b+300000000)/3", a="tool:1", b="tool:2"),
                final(200, "tool:3"),
            ],
            False,
            "PENDING_REVIEW",
        ),
        (
            "mean_year_as_source_amount",
            mean,
            [calculate("2021"), final("0.002021", "tool:1")],
            False,
            "PENDING_REVIEW",
        ),
        (
            "mean_format_recovery_retained",
            mean,
            ["not valid JSON", *mean_avg],
            True,
            "PENDING_REVIEW",
        ),
        (
            "mean_failed_tool_retained",
            mean,
            [
                {
                    "tool": "read_source",
                    "arguments": {
                        "source_id": "absent",
                        "native_pointer": "/facts/us-gaap/Revenue/units/USD/0",
                    },
                },
                *[read("Revenue", index) for index in range(3)],
                calculate("avg(a,b,c)", a="tool:2", b="tool:3", c="tool:4"),
                final(200, "tool:5"),
            ],
            True,
            "PENDING_REVIEW",
        ),
        ("peak_array_selection", peak, [*peak_base, peak_final], True, "MAPPED"),
        (
            "peak_equivalent_pairwise_selection",
            peak,
            [
                *[read("Revenue", index) for index in range(3)],
                {
                    "tool": "compare",
                    "arguments": {"left_result_id": "tool:1", "right_result_id": "tool:2"},
                },
                {
                    "tool": "compare",
                    "arguments": {"left_result_id": "tool:4", "right_result_id": "tool:3"},
                },
                read("NetIncomeLoss", 1),
                final(9, "tool:6", selection_result_id="tool:5", period_id=periods[1]["period_id"]),
            ],
            True,
            "MAPPED",
        ),
        (
            "peak_lookup_dependency",
            peak,
            [
                *peak_base,
                {
                    "tool": "lookup_selected",
                    "arguments": {"selection_result_id": "tool:4", "source_result_id": "tool:5"},
                },
                final(9, "tool:6", period_id=periods[1]["period_id"]),
            ],
            True,
            "MAPPED",
        ),
        (
            "peak_only_secondary_hit",
            peak,
            [read("NetIncomeLoss", 1), final(9, "tool:1", period_id=periods[1]["period_id"])],
            False,
            "PENDING_REVIEW",
        ),
        (
            "peak_wrong_period_same_value",
            peak,
            [*peak_base[:-1], read("NetIncomeLoss", 0), peak_final],
            False,
            "PENDING_REVIEW",
        ),
        (
            "peak_missing_candidate",
            peak,
            [
                read("Revenue", 0),
                read("Revenue", 1),
                {"tool": "select_max", "arguments": {"result_ids": ["tool:1", "tool:2"]}},
                read("NetIncomeLoss", 1),
                final(9, "tool:4", selection_result_id="tool:3", period_id=periods[1]["period_id"]),
            ],
            False,
            "PENDING_REVIEW",
        ),
        (
            "peak_bare_year_final",
            peak,
            [*peak_base, final(9, "tool:5", selection_result_id="tool:4", period=2021)],
            False,
            "PENDING_REVIEW",
        ),
        (
            "peak_wrong_actual_period_final",
            peak,
            [
                *peak_base,
                final(9, "tool:5", selection_result_id="tool:4", period_id=periods[0]["period_id"]),
            ],
            False,
            "PENDING_REVIEW",
        ),
        ("dual_endpoint", dual, endpoint, True, "MAPPED"),
        ("dual_movement", dual, movement, True, "MAPPED"),
        (
            "dual_equivalent_expression",
            dual,
            [*endpoint[:2], calculate("-a+b", a="tool:1", b="tool:2"), endpoint[-1]],
            True,
            "MAPPED",
        ),
        (
            "dual_wrong_direction",
            dual,
            [*endpoint[:2], calculate("a-b", a="tool:1", b="tool:2"), final(-30, "tool:3")],
            False,
            "PENDING_REVIEW",
        ),
        (
            "first_final_cannot_be_repaired",
            mean,
            [final(200, "missing"), *mean_avg],
            False,
            "PENDING_REVIEW",
        ),
    ]
    return [
        {
            "name": name,
            "fixture": fixture,
            "scripted": script,
            "expected_financial_valid": valid,
            "expected_full_mapping_status": mapped,
        }
        for name, fixture, script, valid, mapped in cases
    ]


def run_controls(cases=None, output=None):
    """Execute new synthetic or source-bound cases without tokenization/training."""
    cases = synthetic_cases() if cases is None else cases
    rows = []
    for case in cases:
        fixture = case["fixture"]
        session = generate(
            fixture["messages"],
            fixture["identity"],
            fixture["sources"],
            scripted=case["scripted"],
            requested_basis=case.get("requested_basis", "neutral"),
        )
        assessment = assess_session(
            session, fixture["bundle"], fixture["native_bindings"], fixture["sources"]
        )
        passed = (
            assessment["financial_valid"] == case["expected_financial_valid"]
            and assessment["full_mapping_status"] == case["expected_full_mapping_status"]
        )
        rows.append(
            {
                "name": case["name"],
                "passed": passed,
                "session": session,
                "assessment": assessment,
                "expected_financial_valid": case["expected_financial_valid"],
                "expected_full_mapping_status": case["expected_full_mapping_status"],
                "source_bound": case.get("source_bound", False),
                "control_notes": case.get("control_notes", {}),
            }
        )
    report = record(
        "new_evaluation_controls",
        status="PASS" if all(row["passed"] for row in rows) else "FAIL",
        control_count=len(rows),
        passed_count=sum(row["passed"] for row in rows),
        controls=rows,
        Teacher_sessions=0,
        Student_sessions=0,
        API_requests=0,
        tokenizer_constructions=0,
        training_samples=0,
        model_weight_loads=0,
        gpu_calls=0,
        historical_controls_rerun=False,
        historic_material_rows_reencoded=0,
        source_bound_control_count=sum(row["source_bound"] for row in rows),
        primary_qualification_requires_fine_class_mapping=False,
        fine_mapping_required_for_training_stratification=True,
        pending_fine_classes_retained_without_filling_training_quotas=True,
    )
    if output is not None:
        from ..finance_qa_vnext_task_build.archive import write_json

        write_json(Path(output), report)
    return report


class _Script:
    """Offline script construction is explicitly not a model solving the task."""

    def __init__(self, fixture):
        self.fixture, self.rows, self.reads = fixture, [], {}

    def call(self, tool, arguments):
        self.rows.append({"tool": tool, "arguments": arguments})
        return "tool:" + str(len(self.rows))

    def query(self, fact_id):
        native = self.fixture["native_bindings"][fact_id]
        return self.call(
            "query_source",
            {
                "source_id": native["raw_object_id"],
                "concept": "us-gaap:" + native["tag"],
                "limit": 2,
            },
        )

    def read(self, fact_id):
        if fact_id not in self.reads:
            native = self.fixture["native_bindings"][fact_id]
            self.reads[fact_id] = self.call(
                "read_source",
                {
                    "source_id": native["raw_object_id"],
                    "native_pointer": native["pointer"],
                    "unit": "million USD",
                },
            )
        return self.reads[fact_id]

    def calculate(self, expression, references, unit="million USD"):
        return self.call(
            "calculate",
            {
                "expression": expression,
                "variables": {key: {"result_id": value} for key, value in references.items()},
                "unit": unit,
            },
        )

    def finish(self, value, result_id, *, unit="million USD", **fields):
        return [
            *copy.deepcopy(self.rows),
            {"final": {"value": str(value), "unit": unit, "result_id": result_id, **fields}},
        ]


def _source_value(fixture, identifier):
    return number(fixture["native_bindings"][identifier]["record"]["val"]) / 1000000


def _metric_period_facts(fixture, metric):
    bundle = fixture["bundle"]
    leaves = bundle["private"]["relation_certificate"]["leaf_fact_ids"]
    bindings = fixture["native_bindings"]
    result = []
    for period in bundle["public"]["period_contract"]["periods"]:
        matches = [
            identifier
            for identifier in leaves
            if bindings[identifier]["metric_id"] == metric
            and actual_period(bindings[identifier]["record"])["period_id"] == period["period_id"]
        ]
        require(len(matches) == 1, "controls.unique_registered_metric_period_fact")
        result.append(matches[0])
    return result


def _dual_script(fixture, witness):
    script = _Script(fixture)
    bindings, outputs, amounts = witness["input_bindings"], {}, {}
    first = next(value for value in bindings.values() if isinstance(value, str))
    script.query(first)
    for step in witness["operator_dag"]["operators"]:
        references, values = {}, []
        for index, argument in enumerate(step["inputs"]):
            if "binding" in argument:
                fact_id = bindings[argument["binding"]]
                reference, value = script.read(fact_id), _source_value(fixture, fact_id)
            else:
                reference, value = outputs[argument["step"]], amounts[argument["step"]]
            references["v" + str(index)] = reference
            values.append(value)
        operator, unit = step["operator"], "million USD"
        if operator == "difference":
            expression, amount = "v1-v0", values[1] - values[0]
        elif operator == "sum":
            expression, amount = "+".join(references), sum(values)
        elif operator == "linear_combination":
            coefficients = [number(coefficient) for coefficient in step["params"]["coefficients"]]
            expression = "+".join(
                f"({coefficient})*v{index}" for index, coefficient in enumerate(coefficients)
            )
            amount = sum(
                coefficient * value for coefficient, value in zip(coefficients, values, strict=True)
            )
        elif operator == "ratio_percent":
            expression, amount, unit = "v0/v1", 100 * values[0] / values[1], "percent"
        else:
            raise ValueError("controls.unregistered_dual_operator:" + operator)
        outputs[step["step_id"]] = script.calculate(expression, references, unit)
        amounts[step["step_id"]] = amount
    output_step = witness["operator_dag"]["output_step"]
    return script.finish(
        amounts[output_step],
        outputs[output_step],
        unit=fixture["bundle"]["private"]["canonical_target"]["unit"],
    )


def source_bound_cases(fixtures):
    """Fixed new-structure cases for already registered, manifest-bound fixtures.

    This helper does not choose task identities, load any file, query a model,
    tokenize, or replace failed fixtures. The caller freezes selection before
    invoking it. Witness use here only constructs transparent scripted controls;
    ``generate`` still receives public messages and complete snapshots alone.
    """
    require(isinstance(fixtures, (list, tuple)), "controls.fixture_sequence")
    require(
        len({fixture["identity"]["task_id"] for fixture in fixtures}) == len(fixtures),
        "controls.unique_registered_fixture_tasks",
    )
    cases = []

    def add(fixture, name, script, valid=True, mapped="MAPPED", **notes):
        cases.append(
            {
                "name": fixture["identity"]["task_id"] + ":" + name,
                "fixture": fixture,
                "scripted": script,
                "expected_financial_valid": valid,
                "expected_full_mapping_status": mapped,
                "source_bound": True,
                "control_notes": {
                    "construction": "offline_scripted_contract_control_not_model_output",
                    **notes,
                },
            }
        )

    for fixture in fixtures:
        bundle = fixture["bundle"]
        target = bundle["private"]["canonical_target"]
        if bundle["family"] == "dual_sufficient":
            for witness in bundle["private"]["relation_certificate"]["witnesses"]:
                require(
                    witness["basis"] in {"endpoint", "movement"}, "controls.dual_registered_basis"
                )
                script = _dual_script(fixture, witness)
                add(fixture, "dual_" + witness["basis"], script)
                if witness["basis"] == "endpoint":
                    # Actual endpoint support remains endpoint under opposite guidance.
                    add(fixture, "dual_endpoint_opposite_guidance", script)
                    cases[-1]["requested_basis"] = "movement"
        elif bundle["family"] == "composition_required":
            identifiers = _metric_period_facts(fixture, target["metric_ids"][0])
            values = [_source_value(fixture, identifier) for identifier in identifiers]
            expected = sum(values) / 3
            script = _Script(fixture)
            script.query(identifiers[0])
            references = {
                key: script.read(identifier)
                for key, identifier in zip("abc", identifiers, strict=True)
            }
            result = script.calculate("avg(a,b,c)", references)
            direct = script.finish(expected, result)
            add(fixture, "mean_avg", direct)
            add(
                fixture,
                "mean_format_recovery_retained",
                ["not valid JSON", *direct],
                mapped="PENDING_REVIEW",
            )
            script = _Script(fixture)
            script.query(identifiers[0])
            references = {
                key: script.read(identifier)
                for key, identifier in zip("abc", identifiers, strict=True)
            }
            subtotal = script.calculate("a+b", {key: references[key] for key in "ab"})
            result = script.calculate(
                "(subtotal+c)/3", {"subtotal": subtotal, "c": references["c"]}
            )
            add(fixture, "mean_equivalent_multistep", script.finish(expected, result))
            omitted = _Script(fixture)
            omitted.query(identifiers[0])
            a, c = omitted.read(identifiers[0]), omitted.read(identifiers[2])
            endpoint_average = (values[0] + values[2]) / 2
            expression, claimed = "avg(a,c)", endpoint_average
            equal_construction = endpoint_average == expected
            if endpoint_average:
                expression = f"avg(a,c)*({expected / endpoint_average})"
                claimed, equal_construction = expected, True
            elif values[0] or values[2]:
                # Preserve both endpoints while avoiding a zero scaling base.
                base = values[0] + 2 * values[2]
                expression = f"(a+2*c)*({expected / base})"
                claimed, equal_construction = expected, True
            result = omitted.calculate(expression, {"a": a, "c": c})
            add(
                fixture,
                "mean_omitted_middle_even_when_answer_equal",
                omitted.finish(claimed, result),
                False,
                "PENDING_REVIEW",
                answer_equal_to_correct=equal_construction,
                unsupported_scale_constant_used=expression != "avg(a,c)",
                zero_endpoint_nonzero_mean_edge_not_hidden=not equal_construction,
            )
        elif bundle["family"] == "other_financial":
            primary_ids = _metric_period_facts(fixture, target["metric_ids"][0])
            secondary_ids = _metric_period_facts(fixture, target["metric_ids"][1])
            primary_values = [_source_value(fixture, identifier) for identifier in primary_ids]
            peak = max(range(3), key=primary_values.__getitem__)
            require(
                sum(value == primary_values[peak] for value in primary_values) == 1,
                "controls.unique_registered_peak",
            )
            expected = _source_value(fixture, secondary_ids[peak])
            periods = bundle["public"]["period_contract"]["periods"]
            selected_period = periods[peak]["period_id"]
            for style in ("array", "pairwise"):
                script = _Script(fixture)
                script.query(primary_ids[0])
                primary_refs = [script.read(identifier) for identifier in primary_ids]
                if style == "array":
                    selected = script.call("select_max", {"result_ids": primary_refs})
                else:
                    # The complete set is unchanged. Starting with the unique
                    # peak avoids an immaterial tie between two losing amounts.
                    others = [index for index in range(3) if index != peak]
                    selected = script.call(
                        "compare",
                        {
                            "left_result_id": primary_refs[peak],
                            "right_result_id": primary_refs[others[0]],
                        },
                    )
                    selected = script.call(
                        "compare",
                        {"left_result_id": selected, "right_result_id": primary_refs[others[1]]},
                    )
                secondary = script.read(secondary_ids[peak])
                add(
                    fixture,
                    "peak_" + style + "_selection",
                    script.finish(
                        expected, secondary, selection_result_id=selected, period_id=selected_period
                    ),
                )
                if style == "array":
                    linked = script.call(
                        "lookup_selected",
                        {"selection_result_id": selected, "source_result_id": secondary},
                    )
                    add(
                        fixture,
                        "peak_lookup_dependency",
                        script.finish(expected, linked, period_id=selected_period),
                    )
            script = _Script(fixture)
            script.query(secondary_ids[peak])
            secondary = script.read(secondary_ids[peak])
            add(
                fixture,
                "peak_only_secondary_hit",
                script.finish(expected, secondary, period_id=selected_period),
                False,
                "PENDING_REVIEW",
            )
            script = _Script(fixture)
            script.query(primary_ids[0])
            selected_indices = [peak, next(index for index in range(3) if index != peak)]
            primary_refs = [script.read(primary_ids[index]) for index in selected_indices]
            selected = script.call("select_max", {"result_ids": primary_refs})
            secondary = script.read(secondary_ids[peak])
            add(
                fixture,
                "peak_missing_losing_candidate_same_answer",
                script.finish(
                    expected, secondary, selection_result_id=selected, period_id=selected_period
                ),
                False,
                "PENDING_REVIEW",
            )
            script = _Script(fixture)
            script.query(primary_ids[0])
            selected = script.call(
                "select_max",
                {"result_ids": [script.read(identifier) for identifier in primary_ids]},
            )
            other = next(index for index in range(3) if index != peak)
            secondary = script.read(secondary_ids[other])
            wrong_value = _source_value(fixture, secondary_ids[other])
            add(
                fixture,
                "peak_wrong_actual_interval_secondary",
                script.finish(
                    wrong_value, secondary, selection_result_id=selected, period_id=selected_period
                ),
                False,
                "PENDING_REVIEW",
                wrong_interval_value_happens_to_equal_correct=wrong_value == expected,
            )
        else:
            raise ValueError("controls.unregistered_fixture_family")
    return cases


def raw_package(session, assessment):
    """Pure original-row conversion, intentionally no tokenizer/model imports."""
    from .assessment import _body_valid

    _body_valid(session)
    _body_valid(assessment)
    require(
        assessment["session_id"] == session["id"] and assessment["raw_history_and_tools_replayed"],
        "controls.replayed_assessment_join",
    )
    require(session["origin"] == "scripted_evaluation_control", "controls.scripted_packages_only")
    candidates = []
    for turn, event in zip(session["turns"], session["events"], strict=True):
        require(
            turn["response_index"] == event["response_index"]
            and sha(turn["raw_response"].encode()) == turn["raw_response_sha256"],
            "controls.exact_original_response",
        )
        if not (
            event["final"]
            or event["tool_call"] is not None
            and event["tool_call"]["status"] == "ok"
        ):
            continue
        candidates.append(
            record(
                "original_evaluation_response_candidate",
                task_id=session["identity"]["task_id"],
                session_id=session["id"],
                qualification_id=assessment["id"],
                response_index=turn["response_index"],
                public_runtime_state_id="history:" + sha(encode(turn["input_messages"])),
                messages=copy.deepcopy(turn["input_messages"]),
                target_text=turn["raw_response"],
                target_raw_sha256=turn["raw_response_sha256"],
                response_kind="Final" if event["final"] else event["tool_call"]["tool"],
                requested_basis=session["requested_basis"],
                actual_method=assessment["actual_method"],
                surface_version_id=session["identity"]["surface_version_id"],
                public_messages_sha256=session["identity"]["public_messages_sha256"],
                origin=session["origin"],
                training_eligible=False,
                training_sample=False,
                class_weights_assigned=False,
            )
        )
    return record(
        "original_evaluation_package",
        task_id=session["identity"]["task_id"],
        session_id=session["id"],
        assessment_id=assessment["id"],
        candidates=candidates,
        all_raw_turns_retained=copy.deepcopy(session["turns"]),
        failed_or_format_responses_retained_in_original_later_histories=True,
        financial_valid=assessment["financial_valid"],
        actual_method=assessment["actual_method"],
        full_mapping_status=assessment["full_mapping_status"],
        full_class=assessment["full_class"],
        origin=session["origin"],
        training_eligible=False,
        training_samples=0,
        complete_first_final_package=bool(candidates)
        and candidates[-1]["response_kind"] == "Final",
    )


def raw_packages(report):
    """Retain every new script package; the caller explicitly selects CPU checks."""
    from .assessment import _body_valid

    _body_valid(report)
    return [raw_package(row["session"], row["assessment"]) for row in report["controls"]]
