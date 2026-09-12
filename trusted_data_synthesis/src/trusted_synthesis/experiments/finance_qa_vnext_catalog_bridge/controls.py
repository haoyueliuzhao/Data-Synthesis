"""Offline scripted interface controls; reference programs are never Teacher data."""

import copy

from .assessment import assess_session
from .materials import materialize_packages, raw_package
from .worker import generate, record, require


def script_for_witness(bundle, native_bindings, basis="endpoint", *, alternative=False):
    """Offline fixture construction. Its private inputs never enter the worker."""
    witnesses = bundle["private"]["basis_witnesses"]
    witness = next((w for w in witnesses if w["basis"] == basis), None)
    if witness is None and bundle["family"] == "control":
        witness = witnesses[0]
    require(witness is not None, "controls.reference_basis_available")
    script, inputs = [], {}
    read_refs = {}
    for name, fact_id in witness["input_bindings"].items():
        if fact_id not in read_refs:
            native = native_bindings[fact_id]
            args = {"source_id": fact_id, "unit": "million USD"}
            if native.get("source_kind") == "issuer_report_table":
                args.update(
                    source_id=native["table_id"],
                    cells=[
                        [cell["row"], cell["cell"]]
                        for cell in native["record"]["cell_reference"]["cells"]
                    ],
                )
            script.append({"tool": "read_source", "arguments": args})
            read_refs[fact_id] = "tool:" + str(len(script))
        inputs[name] = read_refs[fact_id]
    steps = {}
    for step in witness["operator_dag"]["operators"]:
        refs = [
            inputs[arg["binding"]] if "binding" in arg else steps[arg["step"]]
            for arg in step["inputs"]
        ]
        variables = {"v" + str(i): {"result_id": ref} for i, ref in enumerate(refs)}
        names = list(variables)
        op = step["operator"]
        unit = "million USD"
        if op == "difference":
            expression = "v1 + (-v0)" if alternative else "v1-v0"
        elif op == "linear_combination":
            terms = [
                f"({c})*{name}"
                for c, name in zip(step["params"]["coefficients"], names, strict=True)
            ]
            expression = "sum([" + ",".join(reversed(terms) if alternative else terms) + "])"
        elif op == "ratio_percent":
            # calculate_with_units applies the ratio -> percent factor itself.
            expression, unit = ("v0*(1/v1)" if alternative else "v0/v1"), "percent"
        elif op == "sum":
            expression = "sum([" + ",".join(names) + "])"
        else:
            raise ValueError("controls.unregistered_operator:" + op)
        script.append(
            {
                "tool": "calculate",
                "arguments": {"expression": expression, "variables": variables, "unit": unit},
            }
        )
        steps[step["step_id"]] = "tool:" + str(len(script))
    script.append(
        {
            "final": {
                "value": bundle["private"]["answer_exact"],
                "unit": bundle["private"]["canonical_target"]["unit"],
                "result_id": steps[witness["operator_dag"]["output_step"]],
            }
        }
    )
    return script


def run_scripted_controls(fixtures, root, *, tokenize=False):
    """Fixtures contain bundle/native_bindings and public identity/messages.

    Parent selects fixed actual bundles by family/quantity/surface category before
    calling. This does not fetch data, rewrite old surfaces or use live models.
    """
    rows, sessions, assessments, packages = [], [], [], []

    def one(fixture, name, script, expected_valid, expected_method=None, guidance="neutral"):
        session = generate(
            fixture["messages"], fixture["identity"], scripted=script, requested_basis=guidance
        )
        assessment = assess_session(session, fixture["bundle"], fixture["native_bindings"])
        passed = assessment["financial_valid"] == expected_valid and (
            expected_method is None or assessment["actual_method"] == expected_method
        )
        rows.append(
            {
                "name": name,
                "task_id": fixture["bundle"]["task_id"],
                "family": fixture["bundle"]["family"],
                "quantity": fixture["bundle"]["private"]["canonical_target"]["quantity"],
                "surface_category": fixture["bundle"]
                .get("surface_realization", {})
                .get("category", "canonical"),
                "passed": passed,
                "expected_valid": expected_valid,
                "actual_valid": assessment["financial_valid"],
                "actual_method": assessment["actual_method"],
                "reason": assessment["reason"],
                "session_id": session["id"],
                "assessment_id": assessment["id"],
            }
        )
        sessions.append(session)
        assessments.append(assessment)
        if assessment["financial_valid"]:
            packages.append(raw_package(session, assessment))
        return session, assessment

    for fixture in fixtures:
        bundle, native = fixture["bundle"], fixture["native_bindings"]
        expected = "control" if bundle["family"] == "control" else "endpoint"
        script = script_for_witness(bundle, native, alternative=True)
        one(
            fixture, "equivalent_endpoint_with_movement_request", script, True, expected, "movement"
        )
        if bundle["family"] != "control":
            movement = script_for_witness(bundle, native, "movement", alternative=True)
            one(
                fixture,
                "equivalent_movement_with_endpoint_request",
                movement,
                True,
                "movement",
                "endpoint",
            )
    if fixtures:
        fixture = next(
            (
                f
                for f in fixtures
                if f["bundle"]["family"] == "annual_flow"
                and f["bundle"]["private"]["canonical_target"]["quantity"] == "difference"
            ),
            fixtures[0],
        )
        script = script_for_witness(fixture["bundle"], fixture["native_bindings"])
        expected = "control" if fixture["bundle"]["family"] == "control" else "endpoint"
        _, plain = one(fixture, "fine_class_equivalent_spelling", script, True, expected)
        equivalent = next(
            a
            for a in assessments
            if a["task_id"] == fixture["bundle"]["task_id"] and a["requested_basis"] == "movement"
        )
        rows[-1]["passed"] &= (
            plain["full_class"] is not None and plain["full_class"] == equivalent["full_class"]
        )
        verification_script = copy.deepcopy(script)
        verification_script.insert(-1, copy.deepcopy(script[-2]))
        _, verified = one(
            fixture, "fine_class_redundant_recomputation", verification_script, True, expected
        )
        rows[-1]["passed"] &= (
            verified["full_class"] is not None and verified["full_class"] != plain["full_class"]
        )
        revision_script = copy.deepcopy(script)
        correction = copy.deepcopy(script[-2])
        prior_result = "tool:" + str(len(script) - 1)
        revision_script[-2]["arguments"]["expression"] = "v0-v1"
        correction["arguments"]["revises_result_id"] = prior_result
        revision_script.insert(-1, correction)
        revision_script[-1]["final"]["result_id"] = "tool:" + str(len(script))
        _, revised = one(
            fixture, "fine_class_substantive_revision", revision_script, True, expected
        )
        rows[-1]["passed"] &= revised["full_class"] is not None and revised["full_class"] not in {
            plain["full_class"],
            verified["full_class"],
        }
        reordered = copy.deepcopy(script)
        reordered[0], reordered[1] = reordered[1], reordered[0]
        for value in reordered[2]["arguments"]["variables"].values():
            value["result_id"] = {"tool:1": "tool:2", "tool:2": "tool:1"}[value["result_id"]]
        _, differently_sourced = one(
            fixture, "fine_class_source_execution_order", reordered, True, expected
        )
        rows[-1]["passed"] &= (
            differently_sourced["full_class"] is not None
            and differently_sourced["full_class"] != plain["full_class"]
        )
        one(fixture, "format_recovery_original_history", ["not JSON\r\n", *script], True, expected)
        one(fixture, "no_final", script[:-1], False)
        one(
            fixture,
            "first_bad_final_no_second_attempt",
            [{"final": {"value": "bad"}}, *script],
            False,
        )
        wrong = copy.deepcopy(script)
        wrong[0]["arguments"]["source_id"] = "not_a_public_source"
        one(fixture, "wrong_source", wrong, False)
        year = copy.deepcopy(script)
        year[-2]["arguments"]["variables"]["v0"] = 2019
        one(fixture, "year_literal_is_not_source_amount", year, False)
        conflict = copy.deepcopy(script)
        conflict[0]["arguments"]["unit"] = "percent"
        one(fixture, "unit_conflict", conflict, False)
        invented = copy.deepcopy(script)
        invented[-2]["arguments"]["expression"] = fixture["bundle"]["private"]["answer_exact"]
        invented[-2]["arguments"]["unit"] = "million USD"
        one(fixture, "answer_equality_does_not_ground_program", invented, False)
        if fixture["bundle"]["family"] != "control":
            # Execute complete movement then publish an independently executed
            # endpoint chain. Merely executing movement must not define Final.
            movement = script_for_witness(
                fixture["bundle"], fixture["native_bindings"], "movement"
            )[:-1]
            offset = len(movement)
            endpoint = copy.deepcopy(script)
            for response in endpoint:
                args = response.get("arguments", {})
                for value in args.get("variables", {}).values():
                    if isinstance(value, dict) and "result_id" in value:
                        value["result_id"] = "tool:" + str(
                            int(value["result_id"].split(":")[1]) + offset
                        )
                if "final" in response:
                    response["final"]["result_id"] = "tool:" + str(
                        int(response["final"]["result_id"].split(":")[1]) + offset
                    )
            one(
                fixture,
                "alternative_basis_cross_check_keeps_endpoint_final_method",
                [*movement, *endpoint],
                True,
                "endpoint",
            )
    tokens = (
        materialize_packages(packages, root)
        if tokenize
        else {"status": "NOT_REQUESTED", "tokenizer_loads": 0}
    )
    return record(
        "scripted_controls",
        status="PASS" if all(row["passed"] for row in rows) else "FAIL",
        rows=rows,
        registered=len(rows),
        passed=sum(row["passed"] for row in rows),
        sessions=sessions,
        assessments=assessments,
        raw_packages=packages,
        materialization=tokens,
        origin="scripted_interface_control",
        teacher_sessions=0,
        provider_calls=0,
        training_samples=0,
        student_weight_loads=0,
        gpu_calls=0,
        full_complete_class_policy=(
            "finite executable-event signatures; unresolved recovery/intent retained "
            "without forced classes"
        ),
    )
