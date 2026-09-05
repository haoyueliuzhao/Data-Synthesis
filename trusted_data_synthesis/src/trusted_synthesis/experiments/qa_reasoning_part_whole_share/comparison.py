"""A finite retained-semantics comparison for actual revenue-share trajectories.

The normal form retains source identities and references, operand use roles,
the explicit part/whole relation, parameters, Observation-grounded Claims and
actual accepted updates.  Runtime names, IDs and node counts are not separation
authorities.  Only the two exact sum members have exchangeable input order.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from .validation import CONTEXT, RECORD_FIELDS, STEP_FIELDS, validate_records

EQUIVALENT = "equivalent"
DIFFERENT = "different_retained_semantics"
UNDETERMINED = "undetermined"
MEASUREMENT_VERSION = "part_whole_share_retained_support_comparison.v1"


class UnsupportedSemantics(ValueError):
    pass


def comparison_rule_contract() -> dict[str, Any]:
    """Freeze this finite interpretation before either positive execution."""
    return {
        "schema_version": MEASUREMENT_VERSION,
        "domain": (
            "one frozen task; disclosed total or exact source-explicit two-member reconstruction"
        ),
        "operations": ["relation_sum", "share_ratio", "scale_percent"],
        "numeric_comparison": "finite exact decimal values; no comparison tolerance",
        "retained_fields": [
            "common_task_question_target_context_answer_numeric_contract",
            "actual_source_record_document_cell_context_identity",
            "distinct_source_metric_definition_value",
            "actual_numerator_denominator_roles_and_consumer_dependencies",
            "source_relation_members_total_metric_exhaustiveness_nonoverlap_references",
            "operation_contract_all_semantic_fields_and_exact_parameters",
            "accepted_claim_proposition_and_actual_grounding",
            "actual_observation_output_and_success",
            "actual_acceptance_update_and_dependency_before_consumption",
            "final_producer_answer_and_actual_citations",
        ],
        "exchange_rule": (
            "sort only relation_sum member inputs by complete retained source identity; "
            "preserve exact multiset; relation remains separately typed"
        ),
        "unsupported_parameters": "own-validation fails before semantic comparison; never erased",
        "transparent_metadata": [
            "runtime_object_ids",
            "candidate_route_label",
            "node_names",
            "serialization_dictionary_order",
            "sum_member_input_order",
        ],
        "non_authorities": [
            "route_label",
            "runtime_id_spelling",
            "graph_hash",
            "node_count",
            "final_answer_alone",
        ],
        "missing_or_unsupported_objects": UNDETERMINED,
        "qualification_required": (
            "independent replay of both complete actual object bundles, not supplied labels"
        ),
        "witness_requires": "both qualified and explicit retained-semantic difference",
        "class_count_requires": "complete relation on the two original qualified candidates",
        "maximum_formal_same_task_pairs": 1,
        "projection_controls_are_candidate_runtime_executions": False,
        "measurement_status": "known finite candidate design; not data-blind or a universal Mapper",
    }


def _number(value: Any) -> str:
    if not isinstance(value, str):
        raise UnsupportedSemantics("only exact decimal strings have numeric normalization")
    try:
        decimal = Decimal(value)
    except InvalidOperation as error:
        raise UnsupportedSemantics("invalid decimal") from error
    if not decimal.is_finite():
        raise UnsupportedSemantics("nonfinite decimal")
    if decimal.is_zero():
        return "0"
    result = format(decimal, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _key(value: Any) -> tuple[Any, ...]:
    """Exact typed structural equality, with no graph hash or search heuristic."""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise UnsupportedSemantics("non-string semantic object key")
        return ("object", tuple((key, _key(value[key])) for key in sorted(value)))
    if isinstance(value, (list, tuple)):
        return ("array", tuple(_key(item) for item in value))
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, str):
        return ("str", value)
    raise UnsupportedSemantics(f"unsupported semantic scalar {type(value).__name__}")


def _without_identity(obj: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in obj.items() if key not in {"id", "schema_version"}}


def _reference(ref: Mapping[str, Any]) -> dict[str, Any]:
    # Content digest is an integrity aid, not a source identity/equality shortcut.
    return {key: value for key, value in ref.items() if key != "source_value_sha256"}


def _project_validated(
    contract: Mapping[str, Any],
    source: Mapping[str, Any],
    records: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    by_id = {item["id"]: item for item in source["evidence"].values()}
    evidence_cache: dict[str, Any] = {}

    def evidence(ref: str) -> dict[str, Any]:
        if ref in evidence_cache:
            return evidence_cache[ref]
        item = by_id[ref]
        semantics = _without_identity(item)
        semantics["source_references"] = sorted(
            (_reference(r) for r in item["source_references"]), key=_key
        )
        if item["kind"] == "numeric":
            semantics["value"] = {"exact_decimal": _number(item["value"])}
        elif item["kind"] == "part_whole":
            semantics.pop("member_ids")
            semantics.pop("total_id")
            semantics["members"] = sorted(
                (evidence(member) for member in item["member_ids"]), key=_key
            )
            total = by_id[item["total_id"]]
            semantics["total_target"] = {
                **{key: total[key] for key in ("metric", "definition", *CONTEXT)},
                "source_record_id": total["source_record_id"],
                "source_document_id": total["source_document_id"],
                "value_is_arithmetic_operand": False,
            }
            # The relation states which metrics partition the total; list order
            # does not change the already retained exact member identities.
            semantics["member_metrics"] = sorted(semantics["member_metrics"])
        else:
            raise UnsupportedSemantics("unknown Evidence kind")
        evidence_cache[ref] = semantics
        return semantics

    def scalar(obj: Mapping[str, Any]) -> dict[str, Any]:
        expected = {"value", "metric", "definition", *CONTEXT, "lineage"}
        if set(obj) != expected:
            raise UnsupportedSemantics("incomplete or extended scalar semantic object")
        return {
            **{key: value for key, value in obj.items() if key not in {"value", "lineage"}},
            "value": {"exact_decimal": _number(obj["value"])},
            "grounding": sorted((evidence(ref) for ref in obj["lineage"]), key=_key),
        }

    steps = {step["claim"]["id"]: step for step in records["steps"]}
    cache: dict[str, Any] = {}
    visiting: set[str] = set()

    def claim_expression(ref: str) -> dict[str, Any]:
        if ref in cache:
            return cache[ref]
        if ref in visiting:
            raise UnsupportedSemantics("cyclic accepted-Claim dependency")
        visiting.add(ref)
        step = steps[ref]
        execution = step["execution"]
        operation = execution["operation"]
        uses = []
        for operand in execution["inputs"]:
            support = (
                evidence(operand["ref_id"])
                if operand["kind"] == "evidence"
                else claim_expression(operand["ref_id"])
            )
            uses.append(
                {"role": operand["role"], "kind": operand["kind"], "actual_support": support}
            )
        if operation == "relation_sum":
            members = [item for item in uses if item["role"] == "member"]
            relation = [item for item in uses if item["role"] == "relation"]
            if len(members) != 2 or len(relation) != 1:
                raise UnsupportedSemantics("unsupported sum member/relation roles")
            uses = [*sorted(members, key=_key), *relation]
        output = scalar(execution["output"])
        result = {
            "kind": "accepted_derived_claim",
            "operation_contract": _without_identity(contract["operations"][operation]),
            "actual_parameters": execution["parameters"],
            "actual_uses": uses,
            "actual_execution_output": output,
            "observation": {
                "success": step["observation"]["success"],
                "output": scalar(step["observation"]["output"]),
            },
            "claim": {
                "status": step["claim"]["status"],
                "proposition": scalar(step["claim"]["proposition"]),
                "grounding": sorted((evidence(r) for r in step["claim"]["grounding"]), key=_key),
            },
            "actual_update": {
                "decision": step["update"]["decision"],
                "accepted_this_observed_claim": True,
                "dependencies_accepted_before_consumption": True,
            },
        }
        visiting.remove(ref)
        cache[ref] = result
        return result

    final = records["final"]
    root = claim_expression(final["answer_claim_id"])
    accepted = sorted(
        (claim_expression(step["claim"]["id"]) for step in records["steps"]), key=_key
    )
    task = _without_identity(contract["task"])
    task.pop("source_binding_id")
    task.pop("evidence_universe_ids")
    task["visible_evidence_universe"] = sorted((evidence(ref) for ref in by_id), key=_key)
    denominator = validation["actual_denominator"]
    denominator_expression = (
        evidence(denominator["ref_id"])
        if denominator["kind"] == "evidence"
        else claim_expression(denominator["ref_id"])
    )
    return {
        "schema_version": "part_whole_share_retained_support_projection.v1",
        "measurement_version": MEASUREMENT_VERSION,
        "task": task,
        "numeric_contract": dict(contract["numeric"]),
        "shared_obligations": list(contract["shared_obligations"]),
        "answer_schema": dict(contract["answer_schema"]),
        "final": {
            "answer": {
                "value": {"exact_decimal": _number(final["answer"]["value"])},
                "unit": final["answer"]["unit"],
            },
            "actual_producer": root,
            "actual_citations": sorted((evidence(ref) for ref in final["citations"]), key=_key),
        },
        "all_actual_accepted_updates": accepted,
        "denominator_support": {
            "kind": denominator["kind"],
            "actual_support": denominator_expression,
        },
    }


def project_records(
    contract: Mapping[str, Any], source: Mapping[str, Any], records: Mapping[str, Any]
) -> dict[str, Any]:
    """Revalidate actual objects before projection; unsupported objects give null."""
    validation = validate_records(contract, source, records)
    result: dict[str, Any] = {
        "status": UNDETERMINED,
        "projection": None,
        "validation": validation,
        "candidate_runtime_executions": 0,
        "formal_pair_comparisons": 0,
    }
    if not validation["qualified"]:
        result["reason"] = "actual object bundle is not own-qualified"
        return result
    try:
        if contract["measurement"] != comparison_rule_contract():
            raise UnsupportedSemantics("frozen measurement rule contract differs")
        projection = _project_validated(contract, source, records, validation)
        _key(projection)
    except (KeyError, TypeError, ValueError, IndexError, RecursionError) as error:
        result["reason"] = str(error)
        return result
    result.update(status="projected", projection=projection, reason=None)
    return result


def _differences(
    left: Any, right: Any, path: str = "retained", limit: int = 20
) -> list[dict[str, Any]]:
    if _key(left) == _key(right):
        return []
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        found = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                found.append(
                    {
                        "path": f"{path}.{key}",
                        "left_present": key in left,
                        "right_present": key in right,
                    }
                )
            else:
                found.extend(
                    _differences(left[key], right[key], f"{path}.{key}", limit - len(found))
                )
            if len(found) >= limit:
                break
        return found
    if isinstance(left, list) and isinstance(right, list):
        # Report actual retained members, not the number of operation nodes.
        return [{"path": path, "left_retained_items": left, "right_retained_items": right}]
    return [{"path": path, "left": left, "right": right}]


def _complete_bundle(records: Any) -> bool:
    """Missing objects are unknown, while complete invalid traces have no witness."""
    try:
        if set(records) != {"candidate", "initial_state", "steps", "final"}:
            return False
        objects = [
            (records["candidate"], "candidate"),
            (records["initial_state"], "state"),
            (records["final"], "final"),
        ]
        if not records["steps"]:
            return False
        for step in records["steps"]:
            if set(step) != STEP_FIELDS:
                return False
            objects.extend((step[kind], kind) for kind in STEP_FIELDS)
        return all(
            isinstance(obj, Mapping) and set(obj) == RECORD_FIELDS[kind] | {"id", "schema_version"}
            for obj, kind in objects
        )
    except (KeyError, TypeError):
        return False


def compare_records(
    contract: Mapping[str, Any],
    source: Mapping[str, Any],
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    """The single finite formal pair; eligibility is rederived from actual objects."""
    left_projection = project_records(contract, source, left)
    right_projection = project_records(contract, source, right)
    result: dict[str, Any] = {
        "schema_version": "part_whole_share_finite_comparison.v1",
        "measurement_version": MEASUREMENT_VERSION,
        "status": UNDETERMINED,
        "formal_class_count": None,
        "relation": UNDETERMINED,
        "comparison": UNDETERMINED,
        "W_share": None,
        "qualified_class_count": None,
        "class_count": None,
        "left_qualified": left_projection["validation"]["qualified"],
        "right_qualified": right_projection["validation"]["qualified"],
        "retained_difference_witnesses": [],
        "candidate_runtime_executions": 0,
        "semantic_pair_count": 1,
        "graph_hash_used_as_authority": False,
        "route_label_used_as_authority": False,
        "node_count_used_as_authority": False,
    }
    if left_projection["status"] != "projected" or right_projection["status"] != "projected":
        result["reason"] = {
            "left": left_projection.get("reason"),
            "right": right_projection.get("reason"),
        }
        if not result["left_qualified"] or not result["right_qualified"]:
            result["witness_state"] = "candidate_not_qualified_no_multiclass_witness"
            if (
                _complete_bundle(left)
                and _complete_bundle(right)
                and left_projection["validation"].get("source_task_replay_valid")
                and right_projection["validation"].get("source_task_replay_valid")
            ):
                result["W_share"] = 0
                result["evaluation_state"] = (
                    "complete_object_bundles_evaluated_at_least_one_invalid"
                )
            else:
                result["evaluation_state"] = "missing_or_unbound_objects_undetermined"
        return result
    lvalue, rvalue = left_projection["projection"], right_projection["projection"]
    if _key(lvalue["task"]) != _key(rvalue["task"]):
        result["reason"] = (
            "task semantics differ; cross-task comparison is outside the finite domain"
        )
        return result
    equivalent = _key(lvalue) == _key(rvalue)
    result.update(
        status=EQUIVALENT if equivalent else DIFFERENT,
        formal_class_count=1 if equivalent else 2,
        relation=EQUIVALENT if equivalent else DIFFERENT,
        comparison=EQUIVALENT if equivalent else DIFFERENT,
        W_share=0 if equivalent else 1,
        qualified_class_count=1 if equivalent else 2,
        class_count=1 if equivalent else 2,
        reason=None,
    )
    if not equivalent:
        # Lead with a concrete producer/consumer support witness. The complete
        # normal forms also retain every actual Observation and accepted update.
        result["retained_difference_witnesses"] = _differences(
            lvalue["denominator_support"],
            rvalue["denominator_support"],
            "ratio.denominator.actual_support",
        )
        if not result["retained_difference_witnesses"]:
            result["retained_difference_witnesses"] = _differences(lvalue, rvalue)
    result["left_denominator"] = left_projection["validation"]["actual_denominator"]
    result["right_denominator"] = right_projection["validation"]["actual_denominator"]
    result["both_final_answers_equal"] = _key(lvalue["final"]["answer"]) == _key(
        rvalue["final"]["answer"]
    )
    result["support_difference_is_node_count_inference"] = False
    return result
