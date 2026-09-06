"""Freeze eight existing source tasks and sixteen fresh, non-replaceable sessions.

Only the finite population budget differs from the inherited HTTP transport.
Catalog, source admission, adapters, public protocol and model-facing prompt are
reused unchanged.  The historical nine fixture rows supply source identities,
never model examples or model outcomes; their two Share rows name one task.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.action_public_contract import public_action_contract
from trusted_synthesis.domains.finance.qa_vnext.catalog import CatalogCase, FinanceQACatalog
from trusted_synthesis.domains.finance.qa_vnext.measurement import _request, _state
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.domains.finance.qa_vnext.runner import build_catalog
from trusted_synthesis.domains.finance.qa_vnext.runtime import TaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import SHARE_FAMILY, ShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import public_update_contract

from ..finance_qa_vnext_model_execution.models import identity, read_json, record, require
from ..finance_qa_vnext_model_execution.plan import BASELINE_ENTRY
from ..finance_qa_vnext_model_execution.transport import SYSTEM_PROMPT, TransportConfig

STAGE = "finance_qa_vnext_fixed_task_panel_collection_and_representation_pilot"
PREDECESSOR = "171035326e1f88b9e8691e02742cadacdcb94dce"
DESIGN_BYTES = 25_917
DESIGN_SHA256 = "67199bf4810f0e6d01da5069429326459ccc29c90fd410f73e23cd4d70ad65d1"
BASELINE_REPORT_ID = (
    "finance_qa_vnext_entry_report:e0c20b27fbc35fb981f90141c0f0a93e07ec675e9715d13c6a04ad6d805ad7c6"
)
TASK_GROUPS = {
    "F": "fact_retrieval",
    "C": "registered_cross_metric_comparison",
    "G": "temporal_growth",
    "A": "temporal_average",
    "D": "temporal_absolute_change",
    "R": "registered_ratio",
    "B": "derived_growth_absolute_spread",
    "S": "source_explicit_part_whole_share",
}
ROUND_TASK_ORDER = ("F", "C", "G", "A", "D", "R", "B", "S")
UNINSTANTIATED_TASK_TYPES = (
    "comparison",
    "derived_growth_comparison",
    "registered_margin_target_gap",
)
SOURCE_USAGE = "source_development_not_blindtest"


class PanelTransportConfig(TransportConfig):
    """Population-only override; inherited single-attempt/session bounds stay fixed.

    The old TransportConfig retains its historical upper bound of 384.  This
    subtype permits exactly the sixteen-session panel's 512 total reservations,
    not a wider retry space or different HTTP/model generation behavior.
    """

    maximum_pilot_attempts: Literal[512] = 512


def configuration() -> TransportConfig:
    return PanelTransportConfig(attempts_per_session=32, system_prompt=SYSTEM_PROMPT)


@dataclass
class TaskPanel:
    root: Path
    catalog: FinanceQACatalog
    cases: dict[str, CatalogCase]
    coverage: list[dict[str, Any]]
    source_bindings: dict[str, dict[str, Any]] = field(default_factory=dict)

    def adapter(self, group: str) -> TaskAdapter:
        require(group in TASK_GROUPS, "task_panel.group")
        if group == "S":
            return ShareTaskAdapter(
                self.root, self.catalog.registry, self.catalog.resolve(SHARE_FAMILY).receipt
            )
        case = self.cases[group]
        self.catalog.admit_case(case)
        return ProgramTaskAdapter(case, self.catalog.registry)


def load_panel(root: Path) -> TaskPanel:
    """Recover the exact previously instantiated tasks, failing before substitution."""
    root = root.resolve()
    baseline = read_json((root / BASELINE_ENTRY / "report.json").read_bytes())
    require(
        strict_canonical_hash(
            {key: value for key, value in baseline.items() if key != "id"},
            prefix="finance_qa_vnext_entry_report:",
        )
        == baseline["id"]
        == BASELINE_REPORT_ID,
        "task_panel.baseline_report_identity",
    )
    catalog = build_catalog(root)
    require(catalog.descriptor["id"] == baseline["catalog_id"], "task_panel.fixed_catalog")
    require(
        set(catalog.task_types) == set(TASK_GROUPS.values()) | set(UNINSTANTIATED_TASK_TYPES)
        and len(catalog.task_types) == 11
        and set(baseline["uninstantiated_task_types"]) == set(UNINSTANTIATED_TASK_TYPES),
        "task_panel.registered_source_boundary",
    )
    cases, source_rows = catalog.frozen_source_cases(root)
    by_case = {case.case_id: case for case in cases}
    require(len(by_case) == len(cases), "task_panel.unique_source_cases")
    selected = {}
    original_by_group = {}
    registry_hash = strict_canonical_hash(catalog.registry.manifest())
    for group, task_type in TASK_GROUPS.items():
        original = [row for row in baseline["coverage_rows"] if row["task_type"] == task_type]
        require(len(original) == (2 if group == "S" else 1), "task_panel.fixed_case_count")
        require(
            all(
                row["registered"] is True
                and row["source_bindable"] is True
                and row["catalog_id"] == catalog.descriptor["id"]
                and row["registry_hash"] == registry_hash
                for row in original
            ),
            "task_panel.fixed_source_registry",
        )
        original_by_group[group] = original
        if group != "S":
            case_id = original[0]["case_id"]
            require(case_id in by_case, "task_panel.exact_source_case_unavailable")
            case = by_case[case_id]
            require(
                case.task_type == task_type
                and case.source_binding["id"] == original[0]["source_binding_id"],
                "task_panel.fixed_source_binding",
            )
            selected[group] = case
    panel = TaskPanel(root, catalog, selected, [])
    for group, task_type in TASK_GROUPS.items():
        adapter = panel.adapter(group)
        original = original_by_group[group]
        require(
            all(
                row["context_id"] == adapter.context["id"]
                and row["task_id"] == adapter.context["task_id"]
                and row["source_binding_id"] == adapter.context["source_binding"]["id"]
                for row in original
            ),
            "task_panel.fixed_source_context",
        )
        panel.source_bindings[group] = record(
            "task_panel_source_binding",
            task_group=group,
            task_type=task_type,
            task_id=adapter.context["task_id"],
            context_id=adapter.context["id"],
            source_binding_id=adapter.context["source_binding"]["id"],
            existing_case_ids=[row["case_id"] for row in original],
            baseline_report_id=baseline["id"],
            catalog_id=catalog.descriptor["id"],
            registry_hash=registry_hash,
            source_usage=SOURCE_USAGE,
            distinct_task_count=1,
            examples_or_reference_routes=False,
            old_fixture_success_is_model_coverage=False,
        )
    status_by_type = {row["task_type"]: row for row in source_rows}
    for task_type in catalog.task_types:
        selected_group = next(
            (key for key, value in TASK_GROUPS.items() if value == task_type), None
        )
        source_available = (
            True if task_type == SHARE_FAMILY else status_by_type[task_type]["source_bindable"]
        )
        require(
            source_available is (selected_group is not None),
            "task_panel.source_availability_boundary",
        )
        binding = panel.source_bindings[selected_group] if selected_group else {}
        panel.coverage.append(
            record(
                "population_coverage",
                task_type=task_type,
                registered=True,
                source_available=source_available,
                selected_for_model_population=selected_group is not None,
                task_group=selected_group,
                population_status="selected_model_task"
                if selected_group
                else "source_uninstantiated",
                registered_model_sessions=2 if selected_group else 0,
                source_usage=SOURCE_USAGE,
                source_binding_id=binding.get("source_binding_id"),
                context_id=binding.get("context_id"),
                task_id=binding.get("task_id"),
                old_fixture_success_is_model_coverage=False,
                new_source_or_synthetic_substitution=False,
            )
        )
    require(
        len({row["task_id"] for row in panel.source_bindings.values()}) == 8
        and len({row["context_id"] for row in panel.source_bindings.values()}) == 8,
        "task_panel.eight_distinct_tasks",
    )
    return panel


def initial_request(adapter: TaskAdapter) -> dict[str, Any]:
    state = _state(
        adapter.context["id"], [], None, {"submissions": 0, "actions": 0, "updates": 0}, None, False
    )
    return _request(adapter, state, contract())


def freeze_condition(
    root: Path,
    config: dict[str, Any],
    implementation: dict[str, Any],
    representation_policy: dict[str, Any],
    *,
    run_tag: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], TaskPanel]:
    identity(implementation, "implementation")
    identity(config, "transport_config")
    require(config == configuration().as_record(), "task_panel.fixed_configuration")
    identity(representation_policy, "task_panel_representation_policy")
    require(
        representation_policy.get("maximum_sequence_length") == 32_768
        and representation_policy.get("truncation") is False,
        "task_panel.fixed_representation_policy",
    )
    require(
        isinstance(run_tag, str) and bool(run_tag) and "/" not in run_tag and "\\" not in run_tag,
        "task_panel.run_tag",
    )
    require(tuple(TASK_GROUPS) == ROUND_TASK_ORDER, "task_panel.fixed_round_order")
    panel = load_panel(root)
    task_marginal = [
        {
            "task_group": group,
            "task_type": TASK_GROUPS[group],
            "task_id": panel.source_bindings[group]["task_id"],
            "numerator": 1,
            "denominator": 8,
        }
        for group in ROUND_TASK_ORDER
    ]
    labels = [f"{group}{round_number:02d}" for round_number in (1, 2) for group in ROUND_TASK_ORDER]
    condition = record(
        "task_panel_condition",
        stage=STAGE,
        run_tag=run_tag,
        predecessor_commit=PREDECESSOR,
        design_sha256=DESIGN_SHA256,
        design_byte_count=DESIGN_BYTES,
        current_user_directive="参照审计继续实验",
        current_directive_authorizes_the_proposed_online_stage=True,
        implementation_id=implementation["id"],
        model_configuration_id=config["id"],
        representation_policy_id=representation_policy["id"],
        new_candidate_dataset_and_token_dataset_identities_required=True,
        historical_length_condition_or_dataset_identity_reused=False,
        catalog_id=panel.catalog.descriptor["id"],
        registry_hash=strict_canonical_hash(panel.catalog.registry.manifest()),
        protocol_id=contract()["id"],
        public_update_contract=public_update_contract(),
        public_action_contract=public_action_contract(),
        source_baseline_report_id=BASELINE_REPORT_ID,
        source_bindings=panel.source_bindings,
        source_usage=SOURCE_USAGE,
        task_contexts={group: panel.adapter(group).context for group in ROUND_TASK_ORDER},
        declared_task_marginal=task_marginal,
        task_marginal_is_design_choice_not_population_estimate=True,
        successful_pool_task_marginal_is_separate=True,
        token_fit_and_complete_package_task_marginals_are_separate=True,
        task_marginal_redefined_after_failure_or_filtering=False,
        given_plan_and_legal_candidates=True,
        autonomous_planning=False,
        private_reasoning_requested=False,
        accept_only_instruction=False,
        share_route_preassignment=None,
        historical_pending_states_or_model_responses_used_as_prefix=False,
        historical_response_examples_in_prompt=False,
        task_count=8,
        source_instances_per_task_type=1,
        source_uninstantiated_task_types=list(UNINSTANTIATED_TASK_TYPES),
        new_sources=0,
        session_count=16,
        sessions_per_task=2,
        registered_denominator=16,
        rounds=2,
        round_task_order=list(ROUND_TASK_ORDER),
        round_launch_order=labels,
        fixed_round_waves=[["F", "C"], ["G", "A"], ["D", "R"], ["B", "S"]],
        within_round_wave_barrier=True,
        maximum_parallel_sessions=2,
        next_round_waits_for_current_round=True,
        outcome_adaptive_reordering=False,
        automatic_network_retries=0,
        model_fallbacks=0,
        session_replacements=0,
        maximum_actions_per_session=12,
        maximum_submissions_per_session=32,
        maximum_provider_attempts_per_session=32,
        maximum_provider_attempts=512,
        maximum_http_body_bytes=98_304,
        input_admission_allowance=99_328,
        output_token_limit=8192,
        maximum_request_reserved_token_allowance=107_520,
        maximum_reserved_token_allowance=55_050_240,
        allowance_is_actual_usage=False,
        missing_usage_is_unknown=True,
        unknown_and_not_started_have_null_success_indicator=True,
        model_failures_remain_in_registered_population=True,
        valid_final_stops_immediately=True,
        public_correction_is_a_new_model_submission_not_a_network_retry=True,
        halt_future_rounds_on_integrity_or_internal_execution_failure=True,
        halt_future_launches_on_integrity_failure=True,
        halt_unstarted_sessions_on_integrity_or_internal_execution_failure=True,
        already_started_sessions_remain_in_registered_population=True,
        maximum_same_task_comparison_pairs=8,
        qualified_but_projection_undetermined_is_allowed=True,
        unmapped_qualified_sessions_remain_in_class_frequency_denominator=True,
        scientific_success_is_not_workflow_gate=True,
        minimum_success_count_for_workflow_completion=None,
        minimum_quotient_class_count_for_workflow_completion=None,
        every_task_success_witness_is_separate_result=True,
        no_cross_condition_success_pooling=True,
        old_results_combined=False,
        old_quotient_assignments_or_weights_reused=False,
        raw_supervision="actual Qualified sessions; admitted original responses only",
        maximum_representation_sequence_length=32_768,
        overlength_candidates_preserved_without_truncation=True,
        overlength_does_not_change_model_qualification=True,
        package_denominator="all admitted session events, never the fit subset",
        historical_length_result_24576_unchanged=True,
        student_parameter_loads=0,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
        training_or_utility_validated=False,
        old_mainline="remains_paused",
    )
    registrations: list[dict[str, Any]] = []
    for round_number in (1, 2):
        for group in ROUND_TASK_ORDER:
            adapter = panel.adapter(group)
            session_id = strict_canonical_hash(
                {"condition_id": condition["id"], "group": group, "round": round_number},
                prefix="qa_vnext_task_panel_session:",
            )
            # The unchanged independent qualifier requires this existing wire identity.
            registrations.append(
                record(
                    "session_registration",
                    session_id=session_id,
                    label=f"{group}{round_number:02d}",
                    ordinal=len(registrations),
                    round=round_number,
                    task_group=group,
                    task_type=TASK_GROUPS[group],
                    task_id=adapter.context["task_id"],
                    context_id=adapter.context["id"],
                    protocol_id=contract()["id"],
                    registry_hash=condition["registry_hash"],
                    model_configuration_id=config["id"],
                    run_condition_id=condition["id"],
                    representation_policy_id=representation_policy["id"],
                    source_usage=SOURCE_USAGE,
                    maximum_actions=12,
                    maximum_submissions=32,
                    maximum_provider_attempts=32,
                    replacement_allowed=False,
                    reference_route=None,
                    independent_initial_state=True,
                    reads_other_session_responses=False,
                )
            )
    require(
        len(registrations) == 16
        and len({row["session_id"] for row in registrations}) == 16
        and [row["label"] for row in registrations] == labels
        and sum(row["maximum_provider_attempts"] for row in registrations) == 512,
        "task_panel.fixed_population",
    )
    return condition, registrations, panel
