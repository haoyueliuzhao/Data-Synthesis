"""Public structural diagnostics, never financial qualification or actual_method.

Executed public events enter the scan; source roles come from a separate offline
bundle/native index. Syntactic dependency closure is not symbolic effective
support: cancellation, units, periods and financial sufficiency remain untested.
"""

import ast
from collections import Counter

from ..finance_qa_vnext_catalog_bridge.assessment import source_fact_bindings
from .protocol import checked_record, encode, record, require, sha


def build_support_index(bundle, native_bindings):
    """Bind source provenance to witness-input roles without copying amounts."""
    require(isinstance(bundle, dict) and isinstance(native_bindings, dict), "signal.offline_inputs")
    witnesses = bundle["private"]["basis_witnesses"]
    require(isinstance(witnesses, list), "signal.witness_list")
    by_basis = {}
    for witness in witnesses:
        require(witness["basis"] not in by_basis, "signal.unique_witness_basis")
        by_basis[witness["basis"]] = witness
    endpoint = by_basis.get("endpoint", by_basis.get("fixed_control_reference", {}))
    movement = by_basis.get("movement", {})
    inputs = endpoint.get("input_bindings", {})
    endpoint_ids, movement_ids = (
        set(inputs.values()),
        set(movement.get("input_bindings", {}).values()),
    )
    locators = source_fact_bindings(bundle, native_bindings)
    return record(
        "structural_support_index",
        task_id=bundle["task_id"],
        bundle_id=bundle["id"],
        native_bindings_sha256=sha(encode(native_bindings)),
        locator_facts={key: sorted(value) for key, value in sorted(locators.items())},
        fact_roles={
            identifier: {
                "endpoint_input": identifier in endpoint_ids,
                "endpoint_previous": identifier == inputs.get("previous"),
                "endpoint_current": identifier == inputs.get("current"),
                "movement_input": identifier in movement_ids,
                "movement_exclusive_input": identifier in movement_ids - endpoint_ids,
                "shared_endpoint_movement_input": identifier in endpoint_ids & movement_ids,
            }
            for identifier in sorted(
                {fact for facts in locators.values() for fact in facts}
                | endpoint_ids
                | movement_ids
            )
        },
        movement_witness_present=bool(movement),
        roles_from_requested_basis=False,
        values_or_private_answers_in_index=False,
        structural_only=True,
        financial_qualification=False,
    )


def growth_delta_hazard(bundle):
    """Inspect the old literal 'change' lookup without replacing the qualifier."""
    movement = next(
        (w for w in bundle["private"]["basis_witnesses"] if w["basis"] == "movement"), None
    )
    if movement is None:
        return record(
            "growth_delta_hazard",
            task_id=bundle["task_id"],
            movement_present=False,
            percentage_output_used_as_currency_delta=False,
            structural_only=True,
        )
    dag = movement["operator_dag"]
    steps = {step["step_id"]: step for step in dag["operators"]}
    require(
        len(steps) == len(dag["operators"]) and dag["output_step"] in steps,
        "signal.original_witness_steps",
    )
    selected = "change" if "change" in steps else dag["output_step"]
    return record(
        "growth_delta_hazard",
        task_id=bundle["task_id"],
        movement_present=True,
        witness_id=movement.get("id"),
        output_step=dag["output_step"],
        output_operator=steps[dag["output_step"]]["operator"],
        step_ids=list(steps),
        literal_change_step_present="change" in steps,
        original_delta_selected_step=selected,
        original_delta_selected_operator=steps[selected]["operator"],
        percentage_output_used_as_currency_delta=steps[selected]["operator"] == "ratio_percent",
        original_consumer="catalog_bridge.assessment:movement[2].get('change', movement[1])",
        structural_only=True,
        actual_session_requalified=False,
        hazard_alone_proves_observed_failure=False,
    )


def _calculation(result):
    issues, names, constants, parsed = [], set(), 0, False
    expression = result.get("expression")
    try:
        if not isinstance(expression, str) or len(expression) > 32768:
            raise ValueError("bounded expression required")
        nodes = list(ast.walk(ast.parse(expression, mode="eval")))
        if len(nodes) > 512:
            raise ValueError("bounded AST required")
        functions = {id(node.func) for node in nodes if isinstance(node, ast.Call)}
        names = {
            node.id for node in nodes if isinstance(node, ast.Name) and id(node) not in functions
        }
        constants = sum(
            isinstance(node, ast.Constant) and type(node.value) in (int, float) for node in nodes
        )
        parsed = True
    except (SyntaxError, TypeError, ValueError, RecursionError):
        issues.append("expression_not_structurally_parsed")
    variables = result.get("resolved_variables")
    if not isinstance(variables, dict):
        issues.append("resolved_variables_missing_or_malformed")
        variables = {}
    refs, expression_refs, literals = [], [], []
    for name, resolved in variables.items():
        if not isinstance(resolved, dict) or "result_id" not in resolved:
            issues.append("resolved_variable_record_malformed")
            continue
        ref = resolved["result_id"]
        if ref is None:
            literals.append(name)
        elif isinstance(ref, str) and ref:
            refs.append(ref)
            if name in names or not parsed:
                expression_refs.append(ref)
        else:
            issues.append("resolved_variable_reference_malformed")
    missing = sorted(names - set(variables))
    if missing:
        issues.append("expression_variable_missing_resolution")
    declared = result.get("used_result_ids")
    if not isinstance(declared, list) or not all(isinstance(x, str) and x for x in declared):
        issues.append("used_result_ids_missing_or_malformed")
        declared = []
    elif len(set(declared)) != len(declared):
        issues.append("duplicate_used_result_id")
    if set(declared) != set(refs):
        issues.append("declared_vs_resolved_reference_mismatch")
    return {
        "expression_parsed": parsed,
        "expression_variable_names": sorted(names),
        "missing_variable_names": missing,
        "unused_resolved_variable_names": sorted(set(variables) - names) if parsed else [],
        "resolved_reference_ids": sorted(set(refs)),
        "declared_reference_ids": sorted(set(declared)),
        "expression_reference_ids": sorted(set(expression_refs)),
        "literal_variable_names": sorted(literals),
        "expression_literal_variable_names": sorted(set(literals) & names),
        "numeric_expression_constant_count": constants,
        "issues": sorted(set(issues)),
    }


def _source(result, index):
    locator = result.get("source_locator")
    if not isinstance(locator, dict):
        return {"status": "UNKNOWN_LOCATOR", "fact_ids": [], "roles": {}}
    locator = dict(locator)
    if "cells" in locator:
        fragment = result.get("original_source_fragment")
        if not isinstance(fragment, list) or not all(
            isinstance(cell, dict)
            and {"row", "cell", "text"} <= set(cell)
            and isinstance(cell["text"], str)
            for cell in fragment
        ):
            return {"status": "UNKNOWN_CELL_FRAGMENT", "fact_ids": [], "roles": {}}
        locator["cells"] = [
            [cell["row"], cell["cell"]]
            for cell in fragment
            if cell["text"].strip() not in ("", "$")
        ]
    key = encode(locator).decode()
    facts = [] if index is None else index["locator_facts"].get(key, [])
    status = (
        "INDEX_NOT_PROVIDED"
        if index is None
        else "UNBOUND_SOURCE"
        if not facts
        else "AMBIGUOUS_SOURCE"
        if len(facts) != 1
        else "UNIQUE_SOURCE_LOCATOR"
    )
    roles = {} if len(facts) != 1 or index is None else index["fact_roles"].get(facts[0], {})
    return {"status": status, "locator_key": key, "fact_ids": list(facts), "roles": dict(roles)}


def public_trace_signals(session, support_index=None):
    """Scan public executed events only; no IO, transport reasoning, or models."""
    require(isinstance(session, dict), "signal.session_object")
    identity = session.get("identity", {})
    if support_index is not None:
        checked_record(support_index, "structural_support_index")
        require(identity.get("task_id") == support_index["task_id"], "signal.task_index_join")
    events = session.get("events")
    require(isinstance(events, list) and len(events) <= 64, "signal.bounded_original_events")
    tools, diagnostics, issues = {}, {}, []
    first = session.get("first_final_index")
    if first is not None and (type(first) is not int or first < 0):
        issues.append("malformed_first_final_index")
    for position, event in enumerate(events):
        if not isinstance(event, dict):
            issues.append("malformed_event")
            continue
        tool = event.get("tool_call")
        if tool is None:
            continue
        if not isinstance(tool, dict) or not isinstance(tool.get("call_id"), str):
            issues.append("malformed_tool_call")
            continue
        key = tool["call_id"]
        if key in tools:
            issues.append("duplicate_tool_call_id")
            continue
        response_index = event.get("response_index", position)
        tools[key] = {"position": position, "response_index": response_index, "tool": tool}
        detail = {
            "result_id": key,
            "tool": tool.get("tool"),
            "status": tool.get("status"),
            "response_index": response_index,
            "issues": [],
        }
        if type(first) is int and type(response_index) is int and response_index >= first:
            detail["issues"].append("tool_not_before_first_final")
        if tool.get("status") == "ok":
            result = tool.get("result")
            if not isinstance(result, dict):
                detail["issues"].append("successful_tool_result_missing")
            elif tool.get("tool") == "calculate":
                detail["calculation"] = _calculation(result)
                detail["issues"].extend(detail["calculation"]["issues"])
            elif tool.get("tool") == "read_source":
                detail["source"] = _source(result, support_index)
            else:
                detail["issues"].append("unknown_successful_numeric_tool")
        diagnostics[key] = detail
    for key, detail in diagnostics.items():
        if "calculation" in detail:
            for ref in detail["calculation"]["resolved_reference_ids"]:
                if ref not in tools:
                    detail["issues"].append("missing_resolved_result_reference")
                elif tools[ref]["position"] >= tools[key]["position"]:
                    detail["issues"].append("nonprior_resolved_result_reference")
    final = session.get("raw_final")
    final_result = final.get("result_id") if isinstance(final, dict) else None
    closure, active, closure_issues = set(), set(), []

    def visit(key, consumer_position=None):
        if not isinstance(key, str) or key not in tools:
            closure_issues.append("missing_result_reference")
            return
        entry = tools[key]
        if consumer_position is not None and entry["position"] >= consumer_position:
            closure_issues.append("nonprior_result_reference")
        if key in active:
            closure_issues.append("cyclic_result_reference")
            return
        if key in closure:
            return
        closure.add(key)
        active.add(key)
        detail = diagnostics[key]
        closure_issues.extend(detail["issues"])
        if detail["status"] != "ok":
            closure_issues.append("failed_result_in_first_final_closure")
        if "calculation" in detail:
            for ref in detail["calculation"]["expression_reference_ids"]:
                visit(ref, entry["position"])
        active.remove(key)

    if first is None:
        final_status = "NO_FINAL"
    elif not isinstance(final, dict) or not isinstance(final_result, str):
        final_status = "FINAL_WITHOUT_RESULT_REFERENCE"
        closure_issues.append("final_missing_result_reference")
    else:
        final_status = "FINAL_WITH_RESULT_REFERENCE"
        visit(final_result)
    rows = [diagnostics[key] for key in tools if key in closure]
    sources = [row["source"] for row in rows if "source" in row]
    unique = [row for row in sources if row["status"] == "UNIQUE_SOURCE_LOCATOR"]
    roles = Counter(role for row in unique for role, present in row["roles"].items() if present)
    calculations = [row["calculation"] for row in rows if "calculation" in row]
    if final_status != "FINAL_WITH_RESULT_REFERENCE" or closure_issues or issues:
        shape = "UNRESOLVED_STRUCTURE"
    elif not sources:
        shape = "NO_REFERENCED_SOURCE_IN_SYNTACTIC_CLOSURE"
    elif len(sources) != len(unique):
        shape = "UNRESOLVED_SOURCE_BINDING"
    elif roles["movement_exclusive_input"] and roles["endpoint_current"]:
        shape = "MOVEMENT_EXCLUSIVE_AND_CURRENT_REFERENCED"
    elif roles["movement_exclusive_input"]:
        shape = "MOVEMENT_EXCLUSIVE_INPUT_REFERENCED"
    elif all(row["roles"].get("endpoint_input") for row in unique):
        shape = "ONLY_ENDPOINT_INPUTS_REFERENCED"
    else:
        shape = "OTHER_SOURCE_INPUTS_REFERENCED"
    return record(
        "public_structural_signals",
        session_id=session.get("id"),
        task_id=identity.get("task_id"),
        support_index_id=support_index["id"] if support_index is not None else None,
        first_final_status=final_status,
        first_final_index=first,
        first_final_result_id=final_result,
        structural_shape=shape,
        first_final_closure_result_ids=[key for key in tools if key in closure],
        closure_kind="syntactic_expression_reference_closure_not_symbolic_effective_support",
        closure_tool_count=len(closure),
        closure_source_status_counts=dict(Counter(row["status"] for row in sources)),
        closure_witness_role_counts=dict(roles),
        closure_referenced_fact_ids=sorted({fact for row in unique for fact in row["fact_ids"]}),
        closure_literal_variable_count=sum(
            len(row["expression_literal_variable_names"]) for row in calculations
        ),
        closure_numeric_expression_constant_count=sum(
            row["numeric_expression_constant_count"] for row in calculations
        ),
        constants_do_not_erase_reference_support=True,
        closure_issues=sorted(set(closure_issues)),
        trace_issues=sorted(set(issues)),
        all_tool_count=len(tools),
        all_tool_status_counts=dict(Counter(row["status"] for row in diagnostics.values())),
        all_protocol_error_count=sum(
            bool(event.get("protocol_error")) for event in events if isinstance(event, dict)
        ),
        all_public_tool_diagnostics=list(diagnostics.values()),
        actual_method_inferred=False,
        financial_qualification_performed=False,
        units_values_periods_or_algebraic_sufficiency_verified=False,
        requested_basis_consumed=False,
        transport_private_reasoning_or_Student_data_read=False,
    )
