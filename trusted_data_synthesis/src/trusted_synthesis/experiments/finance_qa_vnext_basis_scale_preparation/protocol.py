"""Freeze the new study design without authorizing unprepared online work."""

from .core import AUDIT_SHA, record, require
from .design import budget_design

TEACHER_TOKEN_CAP = 1_000_000_000


def preparation_protocol():
    return record(
        "basis_scale_preparation_protocol",
        status="SOURCE_PREPARATION_ONLY",
        accepted_audit_sha256=AUDIT_SHA,
        design=budget_design(),
        resource_stop=record(
            "basis_scale_token_stop_registration",
            maximum_cumulative_Teacher_input_plus_output_tokens=TEACHER_TOKEN_CAP,
            cached_prompt_tokens_included=True,
            all_attempts_including_errors_and_retries_count=True,
            concurrent_requests_require_atomic_reservation=True,
            reserve_before_request="upper bound on prompt tokens plus maximum completion tokens",
            unknown_usage="retain the full reservation as consumed; do not release on errors",
            known_usage="release only the verified unused reservation",
            input_bound_unavailable="STOP; no request with an unproven token upper bound",
            reservation_too_small="STOP on accounting defect; never silently overspend",
            resource_stop_before_fixed_collection_complete=(
                "FIXED_COLLECTION_INCOMPLETE; retain all attempts; no population selection, "
                "top-up or training from the partial collection"
            ),
            monetary_cap=None,
            audit_requires_explicit_token_OR_monetary_stop=True,
            token_cap_is_new_budget_choice_not_yield_or_cost_forecast=True,
            token_cap_derived_from_old_two_task_average=False,
            semantic_model_requests_authorized_by_preparation=0,
            independent_reviewer_model_budget_requires_separate_pre_call_registration=True,
            current_phase_model_requests_authorized=0,
            resource_registration_is_not_source_or_execution_authorization=True,
        ),
        source_requirements={
            "training_candidate_dual_cap": 160,
            "training_candidate_control_cap": 100,
            "desired_final_training": {"dual_per_group": 40, "control": 80},
            "minimum_final_training": {"dual_per_group": 36, "control": 72},
            "development": {"dual": 60, "component_needed": 60, "other": 60},
            "confirmation": {"dual": 240, "component_needed": 240, "other": 240},
            "task_identity": [
                "company",
                "report",
                "financial_object",
                "period",
                "physical_quantity",
            ],
            "source_fields": [
                "public_question",
                "source_bytes",
                "object_period_unit",
                "target_scope",
                "sufficient_relations_with_source_roles",
                "real_company_and_source_cluster",
            ],
            "new_source_based_questions_allowed_with_new_ids": True,
            "original_question_paraphrases_or_fictional_values_add_independent_tasks": False,
            "public_unit_contract_parameterized": [
                "money",
                "ratio",
                "percent",
                "shares",
                "other_explicit_quantity",
            ],
            "offline_answers_formulas_or_role_maps_in_Teacher_extra_prompt": False,
            "original_table_ori_authoritative": True,
            "dash_cells_automatically_zero": False,
            "exact_evaluation_only_sources_can_be_reauthorized_by_redownload": False,
            "source_split_labels_equal_new_study_splits": False,
        },
        independent_review={
            "qualified_packages_per_pool": (
                "fixed random sample; sample rule frozen before collection"
            ),
            "confirmation_discordances": "symmetrical review of candidate wins and baseline wins",
            "blind_to_training_arm_as_far_as_feasible": True,
            "agent_review_is_financial_expert_or_fully_independent": False,
            "reviewer_assignment_and_sampling_parameters": (
                "NOT_YET_REGISTERED; required before collection"
            ),
        },
        unresolved_before_execution=[
            "real historical issuer identity and source-cluster isolation",
            "source-supported unique tasks at required train/dev/confirmation composition",
            "complete source relations, unit contracts and public task scope",
            "fixed candidate order, task IDs, qualification and full-class mapping",
            "prospective tokenizer/length limits and immutable independent A/B session plans",
            "semantic review protocol, fixed sampling and any model-review resource allowance",
            "actual company/report cluster power simulation before outcome observation",
            "online collector and token ledger integration; "
            "concurrency-safe durable implementation",
            "new five-task trainer with no automatic pool-B development evaluation",
        ],
        budget_math_and_stop_limit_frozen=True,
        full_collection_protocol_frozen=False,
        actual_final_training_tasks=0,
        actual_Teacher_sessions=0,
        actual_Student_runs=0,
        support_generation_allowed=False,
        training_allowed=False,
    )


class TokenReservationControl:
    """Offline exact-integer control, NOT a concurrent/persistent API ledger."""

    def __init__(self, cap=TEACHER_TOKEN_CAP):
        require(type(cap) is int and cap > 0, "budget.positive_integer_cap")
        self.cap, self.consumed, self.reservations, self.closed = cap, 0, {}, set()
        self.accounting_failed = False

    def reserve(self, request_id, upper_bound):
        require(not self.accounting_failed, "budget.accounting_failed_STOP")
        require(isinstance(request_id, str) and bool(request_id.strip()), "budget.request_identity")
        require(
            request_id not in self.reservations and request_id not in self.closed,
            "budget.unique_attempt",
        )
        require(type(upper_bound) is int and upper_bound > 0, "budget.proven_positive_bound")
        require(
            self.consumed + sum(self.reservations.values()) + upper_bound <= self.cap,
            "budget.token_stop",
        )
        self.reservations[request_id] = upper_bound

    def finish(self, request_id, *, prompt_tokens=None, completion_tokens=None):
        require(request_id in self.reservations, "budget.existing_reservation")
        bound = self.reservations[request_id]
        if prompt_tokens is None or completion_tokens is None:
            consumed = bound
        else:
            require(
                type(prompt_tokens) is int
                and prompt_tokens >= 0
                and type(completion_tokens) is int
                and completion_tokens >= 0,
                "budget.valid_provider_usage",
            )
            consumed = prompt_tokens + completion_tokens
        del self.reservations[request_id]
        self.closed.add(request_id)
        self.consumed += consumed
        if consumed > bound:
            self.accounting_failed = True
            raise ValueError("budget.reservation_bound_violated_STOP")


def require_online_authority():
    """There is deliberately no runnable Teacher or Student path in this stage."""
    raise ValueError("basis_scale.source_tasks_and_full_protocol_not_ready_STOP")
