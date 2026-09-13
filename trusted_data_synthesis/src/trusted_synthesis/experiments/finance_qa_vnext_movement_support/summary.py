"""Strict joins and metadata-only conclusions from the completed Phase-0 cohort."""

from collections import Counter

from ..finance_qa_vnext_catalog_bridge.worker import FAMILY_TO_SCALE_GROUP
from . import protocol as p


def _cross(rows, fields):
    counts = Counter(tuple(row[field] for field in fields) for row in rows)
    return [
        {**dict(zip(fields, key, strict=True)), "sessions": count}
        for key, count in sorted(counts.items(), key=lambda item: p.encode(item[0]))
    ]


def _source_flags(signal):
    diagnostics = signal["all_public_tool_diagnostics"]
    by_result = {row["result_id"]: row for row in diagnostics}
    closure = signal["first_final_closure_result_ids"]
    p.require(
        len(by_result) == len(diagnostics)
        and len(closure) == len(set(closure))
        and set(closure) <= set(by_result),
        "summary.unique_public_tool_and_closure_ids",
    )
    any_status, closure_status, roles = Counter(), Counter(), Counter()
    any_movement, closure_movement = [], []
    for result_id, row in by_result.items():
        if "source" not in row:
            continue
        source = row["source"]
        p.require(
            row["tool"] == "read_source" and row["status"] == "ok",
            "summary.source_roles_only_from_successful_public_reads",
        )
        status, facts = source["status"], source["fact_ids"]
        p.require(
            isinstance(facts, list)
            and len(facts) == len(set(facts))
            and (status != "UNIQUE_SOURCE_LOCATOR" or len(facts) == 1)
            and (status != "UNBOUND_SOURCE" or not facts)
            and (status != "AMBIGUOUS_SOURCE" or len(facts) > 1),
            "summary.unique_unbound_and_multicandidate_are_distinct",
        )
        any_status[status] += 1
        if result_id in closure:
            closure_status[status] += 1
        if status == "UNIQUE_SOURCE_LOCATOR":
            p.require(
                all(type(value) is bool for value in source["roles"].values()),
                "summary.exact_boolean_witness_roles",
            )
            if result_id in closure:
                roles.update(name for name, present in source["roles"].items() if present)
            if source["roles"].get("movement_exclusive_input") is True:
                any_movement.append(result_id)
                if result_id in closure:
                    closure_movement.append(result_id)
    p.require(
        dict(closure_status) == signal["closure_source_status_counts"]
        and dict(roles) == signal["closure_witness_role_counts"],
        "summary.recomputed_closure_source_and_role_counts",
    )
    return dict(
        unique_movement_exclusive_any_read=bool(any_movement),
        unique_movement_exclusive_first_Final_closure=bool(closure_movement),
        any_read_unbound_source=any_status["UNBOUND_SOURCE"] > 0,
        any_read_ambiguous_source=any_status["AMBIGUOUS_SOURCE"] > 0,
        closure_unbound_source=closure_status["UNBOUND_SOURCE"] > 0,
        closure_ambiguous_source=closure_status["AMBIGUOUS_SOURCE"] > 0,
        any_read_source_event_counts=dict(any_status),
        closure_source_event_counts=dict(closure_status),
        unique_movement_any_read_result_ids=any_movement,
        unique_movement_closure_result_ids=closure_movement,
    )


def _counts(rows):
    flags = (
        "unique_movement_exclusive_any_read",
        "unique_movement_exclusive_first_Final_closure",
        "any_read_unbound_source",
        "any_read_ambiguous_source",
        "closure_unbound_source",
        "closure_ambiguous_source",
    )
    any_events, closure_events = Counter(), Counter()
    for row in rows:
        any_events.update(row["any_read_source_event_counts"])
        closure_events.update(row["closure_source_event_counts"])
    return dict(
        registered_sessions=len(rows),
        **{flag + "_sessions": sum(row[flag] for row in rows) for flag in flags},
        any_read_source_event_counts=dict(sorted(any_events.items())),
        first_Final_closure_source_event_counts=dict(sorted(closure_events.items())),
    )


def summarize(funnel, signals, controls, witness_diagnostics):
    """Return complete-cohort tables, not new financial or method qualification."""
    for value, kind in (
        (funnel, "phase_zero_funnel"),
        (signals, "public_execution_signals"),
        (controls, "scripted_interface_controls"),
        (witness_diagnostics, "original_witness_diagnostics"),
    ):
        p.checked_record(value, kind)
    originals, observed = funnel["all_session_rows"], signals["rows"]
    p.require(
        len(originals)
        == len(observed)
        == signals["registered_sessions"]
        == funnel["declared_expected_session_count"]
        == 24640
        and funnel["is_original_24640_session_cohort"] is True
        and signals["all_original_registry_order_preserved"] is True
        and signals["finance_or_method_qualification"] is False
        and signals["reasoning_content_inspected"] is False,
        "summary.exact_original_full_cohort_and_structural_scope",
    )
    tasks = {}
    sessions, qualifications, matrix, rows = set(), set(), set(), []
    for index, (old, observation) in enumerate(zip(originals, observed, strict=True)):
        task = {"family": old["family"], "group": old["group"]}
        p.require(
            old["family"] in FAMILY_TO_SCALE_GROUP
            and FAMILY_TO_SCALE_GROUP[old["family"]] == old["group"]
            and tasks.get(old["task_id"], task) == task
            and old["registered_session_id"] not in sessions
            and old["qualification_id"] not in qualifications,
            "summary.unique_original_session_qualification_and_task_metadata",
        )
        tasks[old["task_id"]] = task
        sessions.add(old["registered_session_id"])
        qualifications.add(old["qualification_id"])
        matrix.add((old["task_id"], old["pool"], old["requested_basis"], old["replicate"]))
        p.require(
            observation["registry_index"] == index
            and all(
                observation[key] == old[key]
                for key in (
                    "registered_session_id",
                    "qualification_id",
                    "task_id",
                    "family",
                    "pool",
                    "requested_basis",
                )
            )
            and observation["original_actual_method"] == old["actual_method"]
            and observation["original_representation_eligible"] == old["representation_eligible"],
            "summary.exact_registry_order_and_qualification_signal_join",
        )
        signal = observation["signals"]
        p.checked_record(signal, "public_structural_signals")
        p.require(
            signal["task_id"] == old["task_id"]
            and signal["session_id"] == old["session_id"]
            and signal["first_final_index"] == old["first_final_index"]
            and signal["actual_method_inferred"] is False
            and signal["financial_qualification_performed"] is False
            and signal["units_values_periods_or_algebraic_sufficiency_verified"] is False,
            "summary.public_structural_evidence_is_not_new_qualification",
        )
        rows.append(
            dict(
                registry_index=index,
                registered_session_id=old["registered_session_id"],
                session_id=old["session_id"],
                qualification_id=old["qualification_id"],
                structural_signal_id=signal["id"],
                task_id=old["task_id"],
                **task,
                pool=old["pool"],
                requested_basis=old["requested_basis"],
                structural_shape=signal["structural_shape"],
                old_reason=old["reason"],
                original_actual_method=old["actual_method"],
                quantity_status=old["quantity_status"],
                support_status=old["support_status"],
                financial_valid=old["financial_valid"],
                full_mapping_status=old["full_mapping_status"],
                first_final_status=signal["first_final_status"],
                **_source_flags(signal),
            )
        )
    expected_matrix = {
        (task_id, pool, basis, replicate)
        for task_id, task in tasks.items()
        for pool in ("A", "B")
        for basis in (("control",) if task["family"] == "control" else ("endpoint", "movement"))
        for replicate in range(24 if basis == "control" else 32)
    }
    p.require(
        len(tasks) == 255
        and sum(task["family"] == "control" for task in tasks.values()) == 100
        and matrix == expected_matrix
        and len(matrix) == len(rows),
        "summary.original_155_dual_100_control_registration_matrix",
    )
    expected_cases = [
        (task_id, basis)
        for task_id, task in tasks.items()
        for basis in (("control",) if task["family"] == "control" else ("endpoint", "movement"))
    ]
    cases = controls["cases"]
    p.require(
        len(cases) == controls["case_count"] == 410
        and {(case["task_id"], case["requested_control_basis"]) for case in cases}
        == set(expected_cases)
        and controls["actual_generation_distribution_not_measured_by_scripts"] is True
        and controls["training_material"] is False,
        "summary.complete_155_movement_155_endpoint_100_control_matrix",
    )
    passed, by_basis = 0, Counter()
    for case in cases:
        p.checked_record(case, "offline_fixture_control")
        p.require(
            case["family"] == tasks[case["task_id"]]["family"]
            and case["expected_method"] == case["requested_control_basis"]
            and case["actual_provenance"] == "test_only_scripted_reference_callback"
            and case["test_only"] is True
            and all(
                case[key] is False
                for key in (
                    "authentic_Teacher_origin_verified",
                    "representation_eligible",
                    "training_eligible",
                )
            )
            and all(
                case[key] == 0
                for key in ("training_samples", "model_calls", "HTTP_requests", "GPU_operations")
            ),
            "summary.scripted_controls_never_real_Teacher_or_training",
        )
        checks = dict(
            original_runtime_replay=case["replay_verified"],
            financial_valid=case["financial_valid"] is True,
            expected_actual_method=case["actual_method"] == case["expected_method"],
            fine_mapping=case["full_mapping_status"] == "MAPPED",
        )
        valid = case["error"] is None and all(checks.values())
        p.require(
            checks == case["checks"]
            and case["status"] == ("PASS_INTERFACE_CONTROL" if valid else "FAIL_INTERFACE_CONTROL"),
            "summary.recomputed_control_status_not_success_self_report",
        )
        passed += valid
        by_basis[case["requested_control_basis"]] += 1
    witnesses = witness_diagnostics["rows"]
    p.require(
        len(witnesses) == witness_diagnostics["task_count"] == len(tasks)
        and {row["task_id"] for row in witnesses} == set(tasks)
        and witness_diagnostics["not_observed_Teacher_requalification"] is True,
        "summary.complete_original_witness_diagnostic_task_join",
    )
    hazards = 0
    for witness in witnesses:
        p.checked_record(witness, "growth_delta_hazard")
        p.require(
            witness["structural_only"] is True
            and witness.get("actual_session_requalified", False) is False
            and witness.get("hazard_alone_proves_observed_failure", False) is False,
            "summary.witness_hazard_does_not_requalify_observed_sessions",
        )
        hazards += witness["percentage_output_used_as_currency_delta"] is True
    ambiguity_rows = witness_diagnostics["source_locator_ambiguities"]
    p.require(
        len({row["task_id"] for row in ambiguity_rows}) == len(ambiguity_rows)
        and all(row["task_id"] in tasks for row in ambiguity_rows),
        "summary.source_locator_diagnostic_task_join",
    )
    locator_lengths = [
        len(facts) for row in ambiguity_rows for facts in row["ambiguous_locators"].values()
    ]
    cohort_keys = ("family", "group", "pool", "requested_basis")
    cohort_counts = []
    for key in sorted({tuple(row[field] for field in cohort_keys) for row in rows}):
        selected = [row for row in rows if tuple(row[field] for field in cohort_keys) == key]
        cohort_counts.append({**dict(zip(cohort_keys, key, strict=True)), **_counts(selected)})
    return p.record(
        "phase_zero_summary",
        qualification_funnel_id=funnel["id"],
        public_execution_signals_id=signals["id"],
        scripted_interface_controls_id=controls["id"],
        original_witness_diagnostics_id=witness_diagnostics["id"],
        totals=_counts(rows),
        cohort_counts=cohort_counts,
        shape_reason_method_cross=_cross(
            rows, (*cohort_keys, "structural_shape", "old_reason", "original_actual_method")
        ),
        shape_by_guidance=_cross(rows, ("requested_basis", "structural_shape")),
        original_method_by_guidance=_cross(rows, ("requested_basis", "original_actual_method")),
        unique_movement_any_read_cases_in_registry_order=[
            row for row in rows if row["unique_movement_exclusive_any_read"]
        ],
        all_unique_movement_any_read_cases_reported=True,
        control_summary=dict(
            case_count=410,
            passed=passed,
            failed=410 - passed,
            cases_by_expected_method=dict(sorted(by_basis.items())),
            complete_registered_matrix=True,
            measures_real_generation=False,
            training_material=False,
        ),
        witness_summary=dict(
            task_count=len(tasks),
            structural_growth_delta_hazards=hazards,
            empty_locator_entries=sum(length == 0 for length in locator_lengths),
            multicandidate_locator_entries=sum(length > 1 for length in locator_lengths),
            actual_sessions_requalified=0,
        ),
        source_status_counts_distinguish_sessions_from_read_events=True,
        unbound_source_is_not_multicandidate_ambiguity=True,
        any_read_is_not_first_Final_support=True,
        syntactic_Final_closure_is_not_algebraically_effective_financial_support=True,
        no_movement_closure_is_not_zero_generation_probability=True,
        scripted_controls_establish_interface_support_not_generation_frequency=True,
        hazard_alone_does_not_establish_actual_assessor_failure=True,
        raw_or_private_witness_content_copied=False,
        original_qualifications_changed=0,
        original_training_admission_changed=False,
        Student_results_read=False,
    )
