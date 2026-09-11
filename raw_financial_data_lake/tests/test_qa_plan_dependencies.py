"""Local DAG admission regression; no database or historical QA rebuild."""

from finraw.qa.plans import execute_plan, validate_plan


def step(identifier, *inputs):
    return {"step_id": identifier, "operator": "lookup", "inputs": list(inputs)}


def plan(*steps):
    return {"operators": list(steps), "output_step": steps[-1]["step_id"]}


def test_self_reference_is_not_a_previous_dependency():
    value = plan(step("a", {"step": "a"}))
    assert validate_plan(value) == ["step a references a non-previous step: a"]
    execution = execute_plan(value, {}, {})
    assert execution.status == "failed" and execution.intermediate_results == []


def test_forward_reference_rejected_before_any_execution():
    value = plan(step("a", {"step": "b"}), step("b", {"binding": "fact"}))
    assert validate_plan(value) == ["step a references a non-previous step: b"]
    assert execute_plan(value, {}, {}).intermediate_results == []


def test_duplicate_step_id_is_rejected():
    value = plan(step("a", {"binding": "fact"}), step("a", {"step": "a"}))
    assert "duplicate step_id: a" in validate_plan(value)


def test_fact_binding_and_legal_branch_dependencies_pass():
    value = plan(
        step("a", {"binding": "fact"}),
        step("left", {"step": "a"}),
        step("right", {"step": "a"}),
    )
    assert validate_plan(value) == []


def test_valid_plan_still_executes_with_source_lineage():
    value = plan(step("a", {"binding": "fact"}))
    facts = {
        "F1": {"fact_id": "F1", "normalized_value": "12", "normalized_unit": "USD"}
    }
    execution = execute_plan(value, {"fact": "F1"}, facts)
    assert execution.status == "passed"
    assert execution.output["lineage"]["input_fact_ids"] == ["F1"]


def test_output_step_must_exist():
    value = plan(step("a", {"binding": "fact"}))
    value["output_step"] = "missing"
    assert validate_plan(value) == ["output_step does not exist: missing"]
