"""Frozen-rule Share support measurement under a preregistered stratified source.

Profiles bind provenance, not behavioral labels.  This wrapper never executes,
qualifies, tokenizes, repairs responses, or expands the previously frozen rule.
Actual support is traced backward from Final through accepted producer Claims.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext import measurement as domain
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError

from ..finance_qa_vnext_model_execution.models import identity, record, require
from ..finance_qa_vnext_panel_quotient import comparison as frozen_comparison
from ..finance_qa_vnext_panel_quotient import projection as frozen_projection
from ..finance_qa_vnext_panel_quotient.rules import quotient_rule

TASK_FIELDS = ("task_group", "task_type", "task_id", "context_id", "protocol_id", "registry_hash")
PROFILES = ("N", "E")
LABELS = [f"{profile}{ordinal:02d}" for ordinal in range(1, 5) for profile in PROFILES]


def _identified(value: dict[str, Any]) -> None:
    ref = value.get("id")
    require(isinstance(ref, str) and ":" in ref, "support_quotient.record_identity")
    assert isinstance(ref, str)
    require(
        ref
        == strict_canonical_hash(
            {key: item for key, item in value.items() if key != "id"},
            prefix=ref.split(":", 1)[0] + ":",
        ),
        "support_quotient.record_identity",
    )


def comparison_contract(condition: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    """Freeze cross-profile comparability before sampling, with exact source parents."""
    _identified(condition)
    identity(rule, "panel_quotient_rule")
    require(
        rule == quotient_rule() and condition["rule_id"] == rule["id"],
        "support_quotient.frozen_rule",
    )
    require(
        condition["task_group"] == "S"
        and condition["task_type"] == "source_explicit_part_whole_share"
        and all(isinstance(condition.get(key), str) and condition[key] for key in TASK_FIELDS)
        and condition["registered_session_count"] == 8
        and condition["sessions_per_profile"] == 4
        and condition["registered_labels"] == LABELS
        and condition["profile_mixture"]
        == {key: {"numerator": 1, "denominator": 2} for key in PROFILES}
        and set(condition["profiles"]) == set(condition["configurations"]) == set(PROFILES),
        "support_quotient.preregistered_stratified_source",
    )
    bindings = []
    for profile in PROFILES:
        publication, config = condition["profiles"][profile], condition["configurations"][profile]
        _identified(publication)
        _identified(config)
        bindings.append(
            {
                "profile": profile,
                "profile_id": publication["id"],
                "model_configuration_id": config["id"],
            }
        )
    require(len({row["profile_id"] for row in bindings}) == 2, "support_quotient.distinct_profiles")
    return record(
        "support_exploration_comparison_contract",
        exploration_condition_id=condition["id"],
        generation_condition_id=condition["id"],
        rule_id=rule["id"],
        **{key: condition[key] for key in TASK_FIELDS},
        profile_bindings=bindings,
        exact_profiles=condition["profiles"],
        exact_configurations=condition["configurations"],
        registered_labels=LABELS,
        registered_session_count=8,
        maximum_pairs=28,
        same_task_context_protocol_registry_and_rule_required=True,
        cross_profile_comparison_predeclared=True,
        profile_names_are_behavior_labels=False,
        profile_config_identity_checks_removed=False,
        behavior_semantics="unchanged nodes, final and retained_interactions under the frozen rule",
        generation_condition_semantics=(
            "one fixed source with two declared prompt/configuration strata"
        ),
    )


def _entries(entries, condition, rule, contract):
    identity(contract, "support_exploration_comparison_contract")
    require(
        contract == comparison_contract(condition, rule),
        "support_quotient.comparison_contract_drift",
    )
    require(
        len(entries) == 8
        and [entry["label"] for entry in entries] == LABELS
        and Counter(entry["registration"]["profile"] for entry in entries) == {"N": 4, "E": 4}
        and len({entry["registration"]["id"] for entry in entries}) == 8
        and len({entry["registration"]["session_id"] for entry in entries}) == 8
        and len({entry["qualification"]["id"] for entry in entries}) == 8,
        "support_quotient.exact_eight_registration_inventory",
    )
    existing = [entry["session"]["id"] for entry in entries if entry["session"] is not None]
    require(len(existing) == len(set(existing)), "support_quotient.independent_sessions")
    for entry in entries:
        registration, qualification, session = (
            entry[key] for key in ("registration", "qualification", "session")
        )
        identity(registration, "session_registration")
        identity(qualification, "qualification")
        profile = registration["profile"]
        require(
            entry["label"] == registration["label"]
            and entry["label"].startswith(profile)
            and registration["profile_id"] == condition["profiles"][profile]["id"]
            and registration["model_configuration_id"] == condition["configurations"][profile]["id"]
            and registration["run_condition_id"] == condition["id"]
            and qualification["registration_id"] == registration["id"]
            and qualification["registered_session_id"] == registration["session_id"]
            and qualification["model_configuration_id"] == registration["model_configuration_id"]
            and all(
                qualification[key] == registration[key] == condition[key] for key in TASK_FIELDS
            )
            and qualification["session_id"] == (session["id"] if session else None),
            "support_quotient.profile_configuration_and_qualification_binding",
        )
        require(
            qualification["status"] in {"success", "known_failure", "unknown", "not_started"},
            "support_quotient.qualification_status",
        )
        if session is not None:
            domain._identity(session, "session")
            require(
                all(
                    session[key] == condition[key]
                    for key in ("context_id", "protocol_id", "registry_hash")
                ),
                "support_quotient.session_task_binding",
            )
        if qualification["qualified"] is True:
            require(
                session is not None
                and qualification["status"] == "success"
                and session.get("callback_binding", {}).get("origin") == "model"
                and all(
                    qualification.get(key) is True
                    for key in (
                        "model_origin_verified",
                        "evidence_complete",
                        "qa_valid",
                        "trajectory_valid",
                        "end_to_end_success",
                        "export_eligible",
                    )
                ),
                "support_quotient.independently_qualified_model_source",
            )
            audit = qualification["domain_audit"]
            domain._identity(audit, "session_audit")
            domain._identity(audit["actual_decision_graph"], "actual_decision_graph")
            require(
                qualification["domain_audit_id"] == audit["id"]
                and audit["session_id"] == qualification["session_id"]
                and all(
                    audit[key] == condition[key]
                    for key in ("task_id", "context_id", "protocol_id", "registry_hash")
                )
                and all(
                    audit.get(key) is True
                    for key in ("qualified", "qa_valid", "trajectory_valid", "validation_passed")
                )
                and audit["finite_projection"]["nodes"] == audit["actual_decision_graph"]["nodes"],
                "support_quotient.existing_audit_graph_binding",
            )


def _project(entry, condition, rule, contract):
    q, session, reg = (entry[key] for key in ("qualification", "session", "registration"))
    audit = q.get("domain_audit")
    metadata = dict(
        profile=reg["profile"],
        profile_id=reg["profile_id"],
        model_configuration_id=reg["model_configuration_id"],
        comparison_contract_id=contract["id"],
        qualification_status=q["status"],
        prompt_profile_is_not_behavior_semantics=True,
    )
    if session is None or not isinstance(audit, dict) or audit.get("actual_decision_graph") is None:
        require(q["qualified"] is not True, "support_quotient.qualified_graph_missing")
        return record(
            "panel_quotient_projection",
            rule_id=rule["id"],
            generation_condition_id=condition["id"],
            registration_id=reg["id"],
            label=entry["label"],
            **{key: condition[key] for key in TASK_FIELDS if key != "task_type"},
            session_id=q["session_id"],
            qualification_id=q["id"],
            old_domain_audit_id=q.get("domain_audit_id"),
            source_actual_graph_id=None,
            old_projection_supported=False,
            source_domain_audit=audit,
            status="ineligible",
            supported=False,
            behavior_projection=None,
            interpretation_ledger=[],
            reason="no independently qualified complete trajectory; original outcome retained",
            **metadata,
        )
    projected = frozen_projection.project_entry(
        {
            "label": entry["label"],
            "registration": reg,
            "qualification": q,
            "session": session,
            "audit": audit,
            "graph": audit["actual_decision_graph"],
            "old_projection": audit["finite_projection"],
        },
        rule,
        condition["id"],
    )
    return record(
        "panel_quotient_projection",
        **{key: value for key, value in projected.items() if key not in {"id", "schema_version"}},
        **metadata,
    )


def _one(values, predicate, code):
    found = [value for value in values if predicate(value)]
    require(len(found) == 1, "support_quotient." + code)
    return found[0]


def _node_trace(node_id, nodes, bindings, events):
    node = nodes[node_id]
    binding = _one(bindings, lambda item: item["node_id"] == node_id, "node_binding")
    action = _one(
        events,
        lambda item: item["submission"]["id"] == binding["action_submission_id"],
        "action_event",
    )
    update = _one(
        events,
        lambda item: item["submission"]["id"] == binding["update_submission_id"],
        "update_event",
    )
    execution, observation, claim = action["execution"], action["observation"], update["claim"]
    require(
        action["receipt"]["admitted"] is True
        and action["parsed"]["kind"] == "action"
        and execution["success"] is True
        and execution["id"] == binding["execution_id"] == observation["execution_id"]
        and execution["action_submission_id"] == action["submission"]["id"]
        and action["parsed"]["operation"]
        == execution["operation"]
        == node["operation"]
        == observation["selected_action"]["operation"]
        and observation["id"] == binding["observation_id"] == claim["observation_id"]
        and update["receipt"]["admitted"] is True
        and update["parsed"]["kind"] == "update"
        and update["parsed"]["disposition"] == "accept"
        and claim["status"] == "accepted"
        and claim["id"] == binding["accepted_claim_id"]
        and update["request"]["state"]["pending_observation"]["id"] == observation["id"]
        and claim["proposition"]
        == observation["proposition"]
        == node["proposition"]
        == execution["proposition"]
        and action["sequence"] == binding["sequence"] < update["sequence"],
        "support_quotient.actual_execution_explicit_update_claim_chain",
    )
    return {"node": node, "binding": binding, "action": action, "update": update, "claim": claim}


def _input(trace, role):
    return _one(trace["node"]["inputs"], lambda item: item["role"] == role, "graph_input_role")


def _resolved(trace, role):
    return _one(
        trace["action"]["execution"]["resolved_inputs"],
        lambda item: item["value"]["role"] == role,
        "resolved_input_role",
    )


def _consume(consumer, role, producer):
    graph_ref = _input(consumer, role)
    raw_ref = _one(
        consumer["action"]["parsed"]["inputs"],
        lambda item: item["role"] == role,
        "actual_input_role",
    )
    resolved = _resolved(consumer, role)
    claim = producer["claim"]
    require(
        graph_ref["kind"] == raw_ref["kind"] == resolved["value"]["kind"] == "claim"
        and graph_ref["reference"] == {"producer_action": producer["node"]["node_id"]}
        and raw_ref["ref_id"] == resolved["ref_id"] == resolved["value"]["ref_id"] == claim["id"]
        and resolved["value"]["producer_operation"] == producer["node"]["operation"]
        and resolved["value"]["value"] == claim["proposition"]["output"]["value"]
        and producer["node"]["node_id"] in consumer["node"]["input_dependencies"]
        and producer["update"]["sequence"] < consumer["action"]["sequence"]
        and any(
            item == claim for item in consumer["action"]["request"]["state"]["accepted_claims"]
        ),
        "support_quotient.actual_accepted_claim_consumption",
    )


def _trace_reference(trace):
    return {
        "node_id": trace["node"]["node_id"],
        "operation": trace["node"]["operation"],
        "action_submission_id": trace["action"]["submission"]["id"],
        "execution_id": trace["action"]["execution"]["id"],
        "observation_id": trace["action"]["observation"]["id"],
        "update_submission_id": trace["update"]["submission"]["id"],
        "accepted_claim_id": trace["claim"]["id"],
        "action_sequence": trace["action"]["sequence"],
        "update_sequence": trace["update"]["sequence"],
    }


def actual_support(entry: dict[str, Any], projection: dict[str, Any]) -> dict[str, Any]:
    """Read the actual Final <- percent <- ratio <- denominator path, never a route label."""
    q, reg, session = (entry[key] for key in ("qualification", "registration", "session"))
    fields = dict(
        label=entry["label"],
        profile=reg["profile"],
        profile_id=reg["profile_id"],
        model_configuration_id=reg["model_configuration_id"],
        qualification_id=q["id"],
        registration_id=reg["id"],
        session_id=q["session_id"],
        projection_id=projection["id"],
        qualification_status=q["status"],
        qualified=q["qualified"],
        source_actual_graph_id=projection["source_actual_graph_id"],
        classification_uses_profile_name=False,
        operation_execution_or_qualification_calls=0,
    )
    if q["qualified"] is not True:
        return record(
            "support_exploration_support",
            **fields,
            support="ineligible",
            proof_verified=False,
            reason="not independently Qualified",
            trace=None,
        )
    trace: dict[str, Any] = {}
    try:
        graph = q["domain_audit"]["actual_decision_graph"]
        base = q["domain_audit"]["finite_projection"]
        nodes = {node["node_id"]: node for node in graph["nodes"]}
        require(len(nodes) == len(graph["nodes"]), "support_quotient.unique_nodes")
        events, bindings = session["events"], graph["event_bindings"]
        percent = _node_trace(
            base["final"]["answer_producer"]["producer_action"], nodes, bindings, events
        )
        require(
            percent["node"]["operation"] == "scale_percent",
            "support_quotient.final_percent_producer",
        )
        final = _one(
            events,
            lambda event: event["submission"]["id"] == session["final"]["submission_id"],
            "final_event",
        )
        require(
            final["receipt"]["admitted"] is True
            and final["parsed"]["kind"] == "final"
            and final["parsed"]["answer_claim_id"]
            == session["final"]["answer"]["answer_claim_id"]
            == percent["claim"]["id"]
            and percent["update"]["sequence"] < final["sequence"]
            and any(
                claim == percent["claim"] for claim in final["request"]["state"]["accepted_claims"]
            )
            and base["final"]["result"] == session["final"]["answer"]["result"],
            "support_quotient.actual_final_claim_consumption",
        )
        ratio_ref = _input(percent, "ratio")
        require(ratio_ref["kind"] == "claim", "support_quotient.percent_input_is_claim")
        ratio = _node_trace(ratio_ref["reference"]["producer_action"], nodes, bindings, events)
        require(
            ratio["node"]["operation"] == "share_ratio", "support_quotient.actual_ratio_producer"
        )
        _consume(percent, "ratio", ratio)
        denominator = _input(ratio, "denominator")
        evidence = ratio["action"]["request"]["context"]["evidence"]
        trace.update(
            percent=_trace_reference(percent),
            ratio=_trace_reference(ratio),
            final_submission_id=final["submission"]["id"],
            actual_denominator=denominator,
            actual_resolved_denominator=_resolved(ratio, "denominator"),
        )
        if denominator["kind"] == "evidence":
            raw = _one(
                ratio["action"]["parsed"]["inputs"],
                lambda item: item["role"] == "denominator",
                "denominator_role",
            )
            resolved = _resolved(ratio, "denominator")
            require(
                denominator["reference"] == {"evidence_id": evidence["total"]["id"]}
                and raw["kind"] == resolved["value"]["kind"] == "evidence"
                and raw["ref_id"]
                == resolved["ref_id"]
                == resolved["value"]["ref_id"]
                == evidence["total"]["id"]
                and resolved["value"]["value"] == evidence["total"]["value"],
                "support_quotient.actual_disclosed_total_evidence",
            )
            support = "disclosed_total"
            trace["disclosed_total_evidence_id"] = evidence["total"]["id"]
            trace["sum_operation_presence_is_reconstructed_support"] = False
        elif denominator["kind"] == "claim":
            total = _node_trace(
                denominator["reference"]["producer_action"], nodes, bindings, events
            )
            require(
                total["node"]["operation"] == "relation_sum"
                and total["claim"]["obligation_id"] == "total",
                "support_quotient.total_is_actual_relation_sum",
            )
            _consume(ratio, "denominator", total)
            operands = total["action"]["parsed"]["inputs"]
            require(
                {
                    item["ref_id"]
                    for item in operands
                    if item["role"] == "member" and item["kind"] == "evidence"
                }
                == set(evidence["part_whole"]["member_ids"])
                and _one(operands, lambda item: item["role"] == "relation", "sum_relation")[
                    "ref_id"
                ]
                == evidence["part_whole"]["id"],
                "support_quotient.public_members_and_relation",
            )
            support = "reconstructed_total"
            trace["total"] = _trace_reference(total)
            trace["accepted_total_claim_actually_consumed_by_ratio"] = True
        else:
            raise ProtocolError("support_quotient.unsupported_denominator_kind")
        return record(
            "support_exploration_support",
            **fields,
            support=support,
            proof_verified=True,
            reason=None,
            trace=trace,
        )
    except (ProtocolError, KeyError, TypeError, ValueError, IndexError, StopIteration) as error:
        return record(
            "support_exploration_support",
            **fields,
            support="other_or_undetermined",
            proof_verified=False,
            reason=str(error),
            trace=trace,
        )


def _pair(left, right, contract):
    result = frozen_comparison.compare_projections(left, right)
    return record(
        "support_exploration_pair",
        comparison_contract_id=contract["id"],
        exploration_condition_id=contract["exploration_condition_id"],
        rule_id=contract["rule_id"],
        left_qualification_id=left["qualification_id"],
        right_qualification_id=right["qualification_id"],
        left_profile=left["profile"],
        right_profile=right["profile"],
        **{
            key: result[key]
            for key in (
                "left_projection_id",
                "right_projection_id",
                "relation",
                "equivalent",
                "proof_verified",
                "witness",
                "correspondence",
            )
        },
        comparison=result,
        cross_profile=left["profile"] != right["profile"],
        profile_is_behavior_label=False,
    )


def _classes(projections, pairs, condition, contract, rule):
    supported = [value for value in projections if value["supported"]]
    by_id = {value["id"]: value for value in supported}
    parent = {key: key for key in by_id}

    def root(key):
        while parent[key] != key:
            key = parent[key]
        return key

    for pair in pairs:
        if pair["relation"] == "equivalent":
            left, right = pair["left_projection_id"], pair["right_projection_id"]
            require(
                pair["proof_verified"] and pair["correspondence"] is not None,
                "support_quotient.equivalence_proof",
            )
            require(
                canonical_json_bytes(domain._ordered_graph(by_id[left]["behavior_projection"], {}))
                == canonical_json_bytes(
                    domain._ordered_graph(
                        by_id[right]["behavior_projection"], pair["correspondence"]
                    )
                ),
                "support_quotient.equivalence_correspondence",
            )
            parent[root(right)] = root(left)
    groups: list[list[dict[str, Any]]] = []
    for projection in supported:
        member = next(
            (group for group in groups if root(group[0]["id"]) == root(projection["id"])), None
        )
        if member is None:
            groups.append([projection])
        else:
            member.append(projection)
    ambiguous: set[str] = set()
    for pair in pairs:
        left, right = pair["left_projection_id"], pair["right_projection_id"]
        if pair["relation"] == "not_equivalent":
            require(
                root(left) != root(right)
                and pair["proof_verified"]
                and pair["witness"] is not None,
                "support_quotient.inconsistent_partition_proof",
            )
        elif pair["relation"] == "undetermined":
            ambiguous.update((root(left), root(right)))
    classes, assignments = [], []
    for group in groups:
        if root(group[0]["id"]) in ambiguous:
            continue
        ids = {item["id"] for item in group}
        inside = [
            pair["id"]
            for pair in pairs
            if pair["left_projection_id"] in ids and pair["right_projection_id"] in ids
        ]
        outside = [
            pair["id"]
            for pair in pairs
            if (pair["left_projection_id"] in ids) != (pair["right_projection_id"] in ids)
            and pair["relation"] == "not_equivalent"
        ]
        reference = record(
            "support_exploration_class",
            exploration_condition_id=condition["id"],
            rule_id=rule["id"],
            comparison_contract_id=contract["id"],
            **{key: condition[key] for key in TASK_FIELDS},
            representative_projection_id=group[0]["id"],
            member_projection_ids=[item["id"] for item in group],
            member_qualification_ids=[item["qualification_id"] for item in group],
            equivalence_pair_ids=inside,
            separation_pair_ids=outside,
            class_authority="exact finite correspondences and retained difference witnesses",
            graph_hash_is_class_authority=False,
            profile_is_behavior_label=False,
            all_possible_task_classes_enumerated=False,
        )
        classes.append(reference)
        for projection in group:
            assignments.append(
                record(
                    "support_exploration_assignment",
                    class_ref_id=reference["id"],
                    exploration_condition_id=condition["id"],
                    comparison_contract_id=contract["id"],
                    **{
                        key: projection[key]
                        for key in (
                            *TASK_FIELDS[:1],
                            "task_id",
                            "context_id",
                            "protocol_id",
                            "registry_hash",
                            "rule_id",
                            "registration_id",
                            "label",
                            "session_id",
                            "qualification_id",
                            "old_domain_audit_id",
                            "source_actual_graph_id",
                            "profile",
                            "profile_id",
                            "model_configuration_id",
                        )
                    },
                    projection_id=projection["id"],
                    proof_pair_ids=inside + outside,
                    class_identity_not_decided_by_profile_or_hash=True,
                )
            )
    return classes, assignments


def analyze_quotient(
    entries: list[dict[str, Any]],
    condition: dict[str, Any],
    rule: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Measure all eight outcomes; a local D/R witness need not close the full distribution."""
    _entries(entries, condition, rule, contract)
    projections = [_project(entry, condition, rule, contract) for entry in entries]
    supported = [value for value in projections if value["supported"]]
    pairs = [_pair(left, right, contract) for left, right in combinations(supported, 2)]
    require(len(pairs) <= 28, "support_quotient.same_task_pair_bound")
    classes, assignments = _classes(projections, pairs, condition, contract, rule)
    supports = [
        actual_support(entry, projection)
        for entry, projection in zip(entries, projections, strict=True)
    ]
    by_q = {item["qualification_id"]: item for item in supports}
    witness_pairs = [
        pair
        for pair in pairs
        if pair["relation"] == "not_equivalent"
        and pair["proof_verified"]
        and {
            by_q[pair["left_qualification_id"]]["support"],
            by_q[pair["right_qualification_id"]]["support"],
        }
        == {"disclosed_total", "reconstructed_total"}
        and by_q[pair["left_qualification_id"]]["proof_verified"]
        and by_q[pair["right_qualification_id"]]["proof_verified"]
    ]
    witness = record(
        "support_exploration_target_witness",
        established=bool(witness_pairs),
        exploration_condition_id=condition["id"],
        comparison_contract_id=contract["id"],
        rule_id=rule["id"],
        proof_pairs=[pair["id"] for pair in witness_pairs],
        support_proof_ids=sorted(
            {
                by_q[pair[key]]["id"]
                for pair in witness_pairs
                for key in ("left_qualification_id", "right_qualification_id")
            }
        ),
        requirement=(
            "independent Qualified supported D/R trajectories plus actual not-equivalent proof"
        ),
        unrelated_unknown_or_unmapped_observations_do_not_erase_this_existential_witness=True,
        more_than_one_class_alone_proves_target_support=False,
    )
    qualified = [
        entry["qualification"]["id"]
        for entry in entries
        if entry["qualification"]["qualified"] is True
    ]
    mapped = {item["qualification_id"] for item in assignments}
    unmapped = [ref for ref in qualified if ref not in mapped]
    return record(
        "support_exploration_quotient",
        exploration_condition_id=condition["id"],
        comparison_contract_id=contract["id"],
        comparison_contract=contract,
        rule_id=rule["id"],
        registration_ids=[entry["registration"]["id"] for entry in entries],
        qualification_ids=[entry["qualification"]["id"] for entry in entries],
        qualified_qualification_ids=qualified,
        projections=projections,
        pairs=pairs,
        assignments=assignments,
        classes=classes,
        support_rows=supports,
        target_witness=witness,
        all_valid_mapped=not unmapped,
        unmapped_qualification_ids=unmapped,
        qualified_count=len(qualified),
        supported_projection_count=len(supported),
        class_count=len(classes),
        complete_class_count=len(classes) if not unmapped else None,
        assignment_count=len(assignments),
        pair_count=len(pairs),
        maximum_pair_count=28,
        exact_eight_registered_outcomes_retained=True,
        post_outcome_rule_extension=False,
        historical_classes_or_samples_imported=False,
        profile_names_define_classes=False,
        provider_calls=0,
        runtime_calls=0,
        qualification_calls=0,
        tokenizer_calls=0,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
    )
