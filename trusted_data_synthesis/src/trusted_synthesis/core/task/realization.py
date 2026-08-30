from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.task.semantic import (
    BindingSnapshot,
    CanonicalSemanticPlan,
    SemanticInstance,
)
from trusted_synthesis.hashing import canonical_hash

REALIZATION_SCHEMA_VERSION = "surface_realization.v2"
PROTECTED_REWRITE_VERSION = "protected_question_rewrite.v1"

_PROTECTED_SLOT_PATTERN = re.compile(r"<slot_([a-z][a-z0-9_]*)>")
_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?")
_FORBIDDEN_EXTENSION = re.compile(
    r"\b(?:forecast|predict|investment advice|buy|sell|caused? by|why did)\b",
    flags=re.IGNORECASE,
)
_PROHIBITED_SLOT_TOKENS = frozenset({"answer", "expected", "gold", "payload", "result", "value"})
_REALIZATION_CHECK_IDS = (
    "protected_template_round_trip",
    "slot_schema_exact",
    "required_slots_non_empty",
    "required_operator_cues_present",
    "response_form_valid",
    "numeric_grounding",
    "semantic_extension_absent",
    "answer_exposure_absent",
)


class QuestionRendererProfile(BaseModel):
    """A deterministic, versioned surface policy over one semantic task type."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    language: str = Field(min_length=2)
    style: str = Field(min_length=1)
    protected_template: str = Field(min_length=1)
    required_slots: tuple[str, ...] = Field(min_length=1)
    optional_slots: tuple[str, ...] = ()
    required_operator_cues: tuple[str, ...] = Field(min_length=1)
    source_requirement: str = Field(pattern="^(explicit|optional|not_applicable)$")
    response_form: str = Field(default="question", pattern="^(question|directive)$")
    rewrite_version: str = "deterministic_renderer.v1"
    schema_version: str = "question_renderer_profile.v1"

    @model_validator(mode="after")
    def validate_contract(self) -> QuestionRendererProfile:
        placeholders = tuple(_PROTECTED_SLOT_PATTERN.findall(self.protected_template))
        declared_slots = (*self.required_slots, *self.optional_slots)
        if len(set(declared_slots)) != len(declared_slots):
            raise ValueError("renderer profile repeats a declared slot")
        exposed_slots = [
            slot
            for slot in declared_slots
            if set(slot.casefold().split("_")) & _PROHIBITED_SLOT_TOKENS
        ]
        if exposed_slots:
            raise ValueError(f"renderer profile declares answer-like slots: {exposed_slots}")
        if sorted(placeholders) != sorted(declared_slots):
            raise ValueError("renderer template placeholders do not match required slots")
        if len(placeholders) != len(set(placeholders)):
            raise ValueError("renderer template repeats a protected slot")
        question_count = self.protected_template.count("?")
        expected_question_count = 1 if self.response_form == "question" else 0
        if question_count != expected_question_count:
            raise ValueError("renderer template punctuation disagrees with its response form")
        if _NUMBER_PATTERN.search(self.protected_template):
            raise ValueError("renderer template contains an unprotected number")
        folded = self.protected_template.casefold()
        missing = [cue for cue in self.required_operator_cues if cue.casefold() not in folded]
        if missing:
            raise ValueError(f"renderer template is missing operator cues: {missing}")
        if _FORBIDDEN_EXTENSION.search(self.protected_template):
            raise ValueError("renderer template contains a forbidden semantic extension")
        return self

    @property
    def profile_hash(self) -> str:
        return canonical_hash(self, prefix="question_renderer_profile:")


class QuestionContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = Field(min_length=1)
    semantic_task_id: str = Field(min_length=1)
    renderer_profile_hash: str = Field(min_length=1)
    required_slots: tuple[str, ...] = Field(min_length=1)
    optional_slots: tuple[str, ...] = ()
    required_operator_cues: tuple[str, ...] = Field(min_length=1)
    response_form: str = Field(pattern="^(question|directive)$")
    answer_exposure_forbidden: bool = True
    semantic_extension_forbidden: bool = True
    schema_version: str = "question_contract.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> QuestionContract:
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"contract_id"}),
            prefix="question_contract:",
        )
        if self.contract_id != expected:
            raise ValueError("question contract identity is invalid")
        return self


class RealizationValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    checks: dict[str, bool]
    issues: tuple[str, ...] = ()
    answer_exposure_count: int = Field(default=0, ge=0)
    unprotected_number_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_summary(self) -> RealizationValidationReport:
        if len(self.checks) != len(_REALIZATION_CHECK_IDS) or set(self.checks) != set(
            _REALIZATION_CHECK_IDS
        ):
            raise ValueError("realization validation check manifest is not exact")
        expected_issues = tuple(
            check_id for check_id in _REALIZATION_CHECK_IDS if not self.checks[check_id]
        )
        if self.passed != (not expected_issues):
            raise ValueError("realization validation pass flag disagrees with checks")
        if self.issues != expected_issues:
            raise ValueError("realization validation issues disagree with checks")
        return self


class SurfaceRealization(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    realization_id: str = Field(min_length=1)
    semantic_task_id: str = Field(min_length=1)
    semantic_instance_id: str = Field(min_length=1)
    binding_snapshot_id: str = Field(min_length=1)
    legacy_task_id: str = Field(min_length=1)
    renderer_profile_id: str = Field(min_length=1)
    renderer_profile_hash: str = Field(min_length=1)
    question_contract_id: str = Field(min_length=1)
    language: str = Field(min_length=2)
    style: str = Field(min_length=1)
    slot_values: dict[str, str] = Field(min_length=1)
    slot_variant_ids: dict[str, str] = Field(min_length=1)
    protected_template: str = Field(min_length=1)
    normalized_skeleton: str = Field(min_length=1)
    final_instruction: str = Field(min_length=1)
    rewrite_version: str = Field(min_length=1)
    realized_task_hash: str = Field(min_length=1)
    validation: RealizationValidationReport
    schema_version: str = REALIZATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> SurfaceRealization:
        declared_slots = set(self.slot_values)
        if declared_slots != set(self.slot_variant_ids):
            raise ValueError("surface realization slot variants do not cover exact slots")
        if sorted(_PROTECTED_SLOT_PATTERN.findall(self.protected_template)) != sorted(
            declared_slots
        ):
            raise ValueError("surface realization protected slots do not match slot values")
        if normalize_question_skeleton(self.protected_template) != self.normalized_skeleton:
            raise ValueError("surface realization normalized skeleton is invalid")
        if render_protected_template(self.protected_template, self.slot_values) != (
            self.final_instruction
        ):
            raise ValueError("surface realization instruction is not rendered from protected slots")
        expected_validation = _validate_surface_without_profile(
            self.slot_values,
            self.final_instruction,
        )
        for check_id in (
            "protected_template_round_trip",
            "slot_schema_exact",
            "numeric_grounding",
            "semantic_extension_absent",
            "answer_exposure_absent",
        ):
            if self.validation.checks[check_id] != expected_validation[check_id]:
                raise ValueError("surface realization persisted validation is not derived")
        expected = canonical_hash(
            _realization_identity(self.model_dump(mode="json")),
            prefix="surface_realization:",
        )
        if self.realization_id != expected:
            raise ValueError("surface realization identity is invalid")
        return self


class RealizedTaskPackage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    realized_package_id: str = Field(min_length=1)
    semantic_plan: CanonicalSemanticPlan
    binding_snapshot: BindingSnapshot
    semantic_instance: SemanticInstance
    realization: SurfaceRealization
    task: TaskPackage
    schema_version: str = "realized_task_package.v2"

    @model_validator(mode="after")
    def validate_lineage(self) -> RealizedTaskPackage:
        CanonicalSemanticPlan.model_validate(
            self.semantic_plan.model_dump(mode="python", warnings=False)
        )
        BindingSnapshot.model_validate(
            self.binding_snapshot.model_dump(mode="python", warnings=False)
        )
        SemanticInstance.model_validate(
            self.semantic_instance.model_dump(mode="python", warnings=False)
        )
        SurfaceRealization.model_validate(
            self.realization.model_dump(mode="python", warnings=False)
        )
        TaskPackage.model_validate(self.task.model_dump(mode="python", warnings=False))
        if (
            self.semantic_instance.semantic_task_id != self.semantic_plan.semantic_task_id
            or self.semantic_instance.semantic_plan_id != self.semantic_plan.plan_id
            or self.semantic_instance.binding_snapshot_id
            != self.binding_snapshot.binding_snapshot_id
        ):
            raise ValueError("realized package crosses its semantic instance parents")
        if (
            self.realization.semantic_task_id != self.semantic_plan.semantic_task_id
            or self.realization.semantic_instance_id != self.semantic_instance.semantic_instance_id
            or self.realization.binding_snapshot_id != self.binding_snapshot.binding_snapshot_id
        ):
            raise ValueError("realization crosses its semantic instance")
        if self.task.task_id != self.realization.legacy_task_id:
            raise ValueError("realized task does not preserve the legacy task identity")
        if self.task.task_hash != self.realization.realized_task_hash:
            raise ValueError("realized task hash does not match the realization")
        if self.task.public.instruction != self.realization.final_instruction:
            raise ValueError("realized task instruction crosses the SurfaceRealization")
        if (
            self.task.oracle.task_program.program_id != self.semantic_plan.source_program_id
            or self.task.oracle.task_program.program_hash != self.semantic_plan.source_program_hash
        ):
            raise ValueError("realized task Program crosses the CanonicalSemanticPlan")
        if (
            self.task.public.domain != self.semantic_plan.domain
            or self.task.public.task_type != self.semantic_plan.task_type
            or self.task.public.retrieval_track != self.semantic_plan.retrieval_track
            or self.task.public.planning_track != self.semantic_plan.planning_track
        ):
            raise ValueError("realized task public semantics cross the CanonicalSemanticPlan")
        expected_tools = (
            "evidence.search",
            *sorted(
                {
                    node.tool_capability
                    for node in self.semantic_plan.nodes
                    if node.tool_capability is not None
                }
            ),
        )
        if self.task.public.allowed_tools != expected_tools:
            raise ValueError("realized task tools cross the CanonicalSemanticPlan")
        if self.task.public.answer_schema != self.semantic_plan.answer_schema:
            raise ValueError("realized task Answer Schema crosses the CanonicalSemanticPlan")
        if set(self.task.oracle.gold_evidence_ids) != set(
            self.binding_snapshot.evidence_ids
        ) or len(self.task.oracle.gold_evidence_ids) != len(self.binding_snapshot.evidence_ids):
            raise ValueError("realized task Evidence crosses the BindingSnapshot")
        if (
            self.task.oracle.proof_graph_id != self.binding_snapshot.proof_graph_id
            or self.task.oracle.proof_graph_hash != self.binding_snapshot.proof_graph_hash
        ):
            raise ValueError("realized task ProofGraph crosses the BindingSnapshot")
        pattern_binding = self.task.oracle.selection_contract.get("pattern_binding")
        observed_role_bindings: dict[str, tuple[str, ...]] | None = None
        if isinstance(pattern_binding, dict):
            raw_role_bindings = pattern_binding.get("role_bindings")
            if isinstance(raw_role_bindings, dict):
                try:
                    observed_role_bindings = {
                        str(role_id): tuple(str(value) for value in values)
                        for role_id, values in raw_role_bindings.items()
                    }
                except TypeError:
                    observed_role_bindings = None
        if not isinstance(pattern_binding, dict) or (
            pattern_binding.get("binding_id") != self.binding_snapshot.evidence_binding.binding_id
            or pattern_binding.get("binding_hash")
            != self.binding_snapshot.evidence_binding.binding_hash
            or observed_role_bindings != self.binding_snapshot.evidence_binding.role_bindings
        ):
            raise ValueError("realized task Pattern Binding crosses the BindingSnapshot")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"realized_package_id"}),
            prefix="realized_task_package:",
        )
        if self.realized_package_id != expected:
            raise ValueError("realized task package identity is invalid")
        return self

    @property
    def semantic_plan_id(self) -> str:
        return self.semantic_plan.plan_id

    @property
    def binding_snapshot_id(self) -> str:
        return self.binding_snapshot.binding_snapshot_id

    @property
    def semantic_instance_id(self) -> str:
        return self.semantic_instance.semantic_instance_id


class RealizationPortfolio(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    portfolio_id: str = Field(min_length=1)
    semantic_schema_id: str = Field(min_length=1)
    semantic_instance_id: str = Field(min_length=1)
    binding_snapshot_id: str = Field(min_length=1)
    candidate_realized_package_ids: tuple[str, ...] = Field(min_length=1)
    selected_realized_package_ids: tuple[str, ...] = Field(min_length=1)
    rejected_realized_package_ids: tuple[str, ...] = ()
    candidate_realization_ids: tuple[str, ...] = Field(min_length=1)
    selected_realization_ids: tuple[str, ...] = Field(min_length=1)
    rejected_realization_ids: tuple[str, ...] = ()
    parent_weight_numerator: int = Field(default=1, ge=1)
    child_weight_denominator: int = Field(ge=1)
    selection_policy_id: str = "deterministic_realization_portfolio.v2"
    schema_version: str = "realization_portfolio.v2"

    @model_validator(mode="after")
    def validate_portfolio(self) -> RealizationPortfolio:
        candidate_packages = set(self.candidate_realized_package_ids)
        selected_packages = set(self.selected_realized_package_ids)
        rejected_packages = set(self.rejected_realized_package_ids)
        candidate_set = set(self.candidate_realization_ids)
        selected_set = set(self.selected_realization_ids)
        rejected_set = set(self.rejected_realization_ids)
        if len(candidate_packages) != len(self.candidate_realized_package_ids):
            raise ValueError("realization portfolio contains duplicate candidate packages")
        if len(selected_packages) != len(self.selected_realized_package_ids):
            raise ValueError("realization portfolio contains duplicate selected packages")
        if len(rejected_packages) != len(self.rejected_realized_package_ids):
            raise ValueError("realization portfolio contains duplicate rejected packages")
        if len(candidate_set) != len(self.candidate_realization_ids):
            raise ValueError("realization portfolio contains duplicate candidates")
        if len(selected_set) != len(self.selected_realization_ids):
            raise ValueError("realization portfolio contains duplicate selections")
        if len(rejected_set) != len(self.rejected_realization_ids):
            raise ValueError("realization portfolio contains duplicate rejections")
        if not selected_set.issubset(candidate_set) or not rejected_set.issubset(candidate_set):
            raise ValueError("realization portfolio disposition is outside the candidate set")
        if selected_set & rejected_set or selected_set | rejected_set != candidate_set:
            raise ValueError("realization portfolio does not partition candidates")
        if (
            selected_packages & rejected_packages
            or selected_packages | rejected_packages != candidate_packages
        ):
            raise ValueError("realization portfolio does not partition candidate packages")
        if (
            len(self.candidate_realized_package_ids) != len(self.candidate_realization_ids)
            or len(self.selected_realized_package_ids) != len(self.selected_realization_ids)
            or len(self.rejected_realized_package_ids) != len(self.rejected_realization_ids)
        ):
            raise ValueError("realization portfolio package/realization cardinality differs")
        if self.child_weight_denominator != len(self.selected_realized_package_ids):
            raise ValueError("realization portfolio does not conserve parent weight")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"portfolio_id"}),
            prefix="realization_portfolio:",
        )
        if self.portfolio_id != expected:
            raise ValueError("realization portfolio identity is invalid")
        return self


class ProtectedRewriteValidation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    question_template: str = ""
    errors: tuple[str, ...] = ()


class RendererRegistry:
    def __init__(self, profiles: Iterable[QuestionRendererProfile] = ()) -> None:
        self._profiles: dict[str, QuestionRendererProfile] = {}
        for profile in profiles:
            self.register(profile)

    def register(self, profile: QuestionRendererProfile) -> None:
        if profile.profile_id in self._profiles:
            raise ValueError(f"renderer profile already registered: {profile.profile_id}")
        self._profiles[profile.profile_id] = profile

    def require(self, profile_id: str) -> QuestionRendererProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise ValueError(f"unknown renderer profile: {profile_id}") from exc

    def for_task_type(self, task_type: str) -> tuple[QuestionRendererProfile, ...]:
        return tuple(
            sorted(
                (item for item in self._profiles.values() if item.task_type == task_type),
                key=lambda item: item.profile_id,
            )
        )

    def manifest(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                **profile.model_dump(mode="json"),
                "profile_hash": profile.profile_hash,
            }
            for profile in sorted(self._profiles.values(), key=lambda item: item.profile_id)
        )


def make_question_contract(
    plan: CanonicalSemanticPlan,
    profile: QuestionRendererProfile,
) -> QuestionContract:
    payload = {
        "semantic_task_id": plan.semantic_task_id,
        "renderer_profile_hash": profile.profile_hash,
        "required_slots": profile.required_slots,
        "optional_slots": profile.optional_slots,
        "required_operator_cues": profile.required_operator_cues,
        "response_form": profile.response_form,
        "answer_exposure_forbidden": True,
        "semantic_extension_forbidden": True,
        "schema_version": "question_contract.v1",
    }
    contract_id = canonical_hash(payload, prefix="question_contract:")
    return QuestionContract(contract_id=contract_id, **payload)


def realize_task(
    *,
    plan: CanonicalSemanticPlan,
    binding: BindingSnapshot,
    instance: SemanticInstance,
    task: TaskPackage,
    profile: QuestionRendererProfile,
    slot_values: Mapping[str, str],
    slot_variant_ids: Mapping[str, str] | None = None,
) -> RealizedTaskPackage:
    if binding.semantic_task_id != plan.semantic_task_id:
        raise ValueError("realization binding does not target the semantic plan")
    if (
        instance.semantic_task_id != plan.semantic_task_id
        or instance.semantic_plan_id != plan.plan_id
        or instance.binding_snapshot_id != binding.binding_snapshot_id
    ):
        raise ValueError("realization semantic instance crosses its Plan or BindingSnapshot")
    if profile.task_type != plan.task_type or task.public.task_type != plan.task_type:
        raise ValueError("renderer profile does not target the task type")
    values = {str(key): str(value) for key, value in slot_values.items()}
    declared_slots = set((*profile.required_slots, *profile.optional_slots))
    if set(values) != declared_slots or any(
        not values[slot].strip() for slot in profile.required_slots
    ):
        raise ValueError("realization slots must exactly match the profile slot contract")
    variants = {
        slot: str((slot_variant_ids or {}).get(slot) or "canonical")
        for slot in (*profile.required_slots, *profile.optional_slots)
    }
    instruction = render_protected_template(profile.protected_template, values)
    contract = make_question_contract(plan, profile)
    validation = validate_realized_question(profile, values, instruction)
    realized_public = task.public.model_copy(update={"instruction": instruction})
    realized_task = task.model_copy(update={"public": realized_public})
    identity_payload = {
        "semantic_task_id": plan.semantic_task_id,
        "semantic_instance_id": instance.semantic_instance_id,
        "binding_snapshot_id": binding.binding_snapshot_id,
        "legacy_task_id": task.task_id,
        "renderer_profile_id": profile.profile_id,
        "renderer_profile_hash": profile.profile_hash,
        "question_contract_id": contract.contract_id,
        "language": profile.language,
        "style": profile.style,
        "slot_values": values,
        "slot_variant_ids": variants,
        "protected_template": profile.protected_template,
        "normalized_skeleton": normalize_question_skeleton(profile.protected_template),
        "final_instruction": instruction,
        "rewrite_version": profile.rewrite_version,
        "realized_task_hash": realized_task.task_hash,
        "schema_version": REALIZATION_SCHEMA_VERSION,
    }
    realization_id = canonical_hash(
        {
            **identity_payload,
            "validation": validation.model_dump(mode="json"),
        },
        prefix="surface_realization:",
    )
    realization = SurfaceRealization(
        realization_id=realization_id,
        validation=validation,
        **identity_payload,
    )
    package_payload = {
        "semantic_plan": plan,
        "binding_snapshot": binding,
        "semantic_instance": instance,
        "realization": realization,
        "task": realized_task,
        "schema_version": "realized_task_package.v2",
    }
    provisional = RealizedTaskPackage.model_construct(
        realized_package_id="pending",
        **package_payload,
    )
    package_id = canonical_hash(
        provisional.model_dump(mode="json", exclude={"realized_package_id"}),
        prefix="realized_task_package:",
    )
    return RealizedTaskPackage(
        realized_package_id=package_id,
        **package_payload,
    )


def validate_realized_question(
    profile: QuestionRendererProfile,
    slot_values: Mapping[str, str],
    instruction: str,
) -> RealizationValidationReport:
    expected = render_protected_template(profile.protected_template, slot_values)
    allowed_numbers = {
        number for value in slot_values.values() for number in _NUMBER_PATTERN.findall(str(value))
    }
    observed_numbers = set(_NUMBER_PATTERN.findall(instruction))
    unprotected_numbers = observed_numbers - allowed_numbers
    folded = instruction.casefold()
    checks = {
        "protected_template_round_trip": instruction == expected,
        "slot_schema_exact": set(slot_values)
        == set((*profile.required_slots, *profile.optional_slots)),
        "required_slots_non_empty": all(
            str(slot_values[slot]).strip() for slot in profile.required_slots
        ),
        "required_operator_cues_present": all(
            cue.casefold() in folded for cue in profile.required_operator_cues
        ),
        "response_form_valid": instruction.count("?")
        == (1 if profile.response_form == "question" else 0),
        "numeric_grounding": not unprotected_numbers,
        "semantic_extension_absent": _FORBIDDEN_EXTENSION.search(instruction) is None,
        "answer_exposure_absent": not any(
            set(slot.casefold().split("_")) & _PROHIBITED_SLOT_TOKENS
            for slot in (*profile.required_slots, *profile.optional_slots)
        ),
    }
    issues = tuple(check_id for check_id, passed in checks.items() if not passed)
    return RealizationValidationReport(
        passed=not issues,
        checks=checks,
        issues=issues,
        answer_exposure_count=0,
        unprotected_number_count=len(unprotected_numbers),
    )


def _validate_surface_without_profile(
    slot_values: Mapping[str, str],
    instruction: str,
) -> dict[str, bool]:
    allowed_numbers = {
        number for value in slot_values.values() for number in _NUMBER_PATTERN.findall(str(value))
    }
    observed_numbers = set(_NUMBER_PATTERN.findall(instruction))
    return {
        "protected_template_round_trip": True,
        "slot_schema_exact": True,
        "numeric_grounding": not (observed_numbers - allowed_numbers),
        "semantic_extension_absent": _FORBIDDEN_EXTENSION.search(instruction) is None,
        "answer_exposure_absent": not any(
            set(slot.casefold().split("_")) & _PROHIBITED_SLOT_TOKENS for slot in slot_values
        ),
    }


def validate_protected_rewrite(
    candidate: Any,
    required_slots: Iterable[str],
) -> ProtectedRewriteValidation:
    if not isinstance(candidate, Mapping):
        return ProtectedRewriteValidation(passed=False, errors=("rewrite_not_object",))
    allowed_fields = {"rewrite_version", "question_template"}
    errors: list[str] = []
    if set(candidate) != allowed_fields:
        errors.append("rewrite_fields_not_exact")
    if str(candidate.get("rewrite_version") or "") != PROTECTED_REWRITE_VERSION:
        errors.append("rewrite_version_invalid")
    template = str(candidate.get("question_template") or "").strip()
    expected_placeholders = sorted(f"<slot_{slot}>" for slot in required_slots)
    observed_placeholders = _PROTECTED_SLOT_PATTERN.findall(template)
    observed_tokens = sorted(f"<slot_{slot}>" for slot in observed_placeholders)
    if observed_tokens != expected_placeholders:
        errors.append("rewrite_placeholder_mismatch")
    if len(observed_placeholders) != len(set(observed_placeholders)):
        errors.append("rewrite_placeholder_duplicate")
    if _NUMBER_PATTERN.search(template):
        errors.append("rewrite_unprotected_number")
    if template.count("?") != 1:
        errors.append("rewrite_not_single_question")
    if _FORBIDDEN_EXTENSION.search(template):
        errors.append("rewrite_forbidden_extension")
    return ProtectedRewriteValidation(
        passed=not errors,
        question_template=template,
        errors=tuple(dict.fromkeys(errors)),
    )


def render_protected_template(template: str, slot_values: Mapping[str, str]) -> str:
    output = template
    for slot, value in sorted(slot_values.items()):
        output = output.replace(f"<slot_{slot}>", str(value))
    if _PROTECTED_SLOT_PATTERN.search(output):
        raise ValueError("protected template contains unresolved slots")
    return output


def normalize_question_skeleton(value: str) -> str:
    normalized = _PROTECTED_SLOT_PATTERN.sub("<slot>", value.casefold())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def select_realization_portfolio(
    candidates: Iterable[RealizedTaskPackage],
    *,
    max_realizations: int = 3,
) -> tuple[RealizationPortfolio, tuple[RealizedTaskPackage, ...]]:
    rows = tuple(candidates)
    if not rows:
        raise ValueError("realization portfolio requires candidates")
    if max_realizations < 1:
        raise ValueError("realization portfolio maximum must be positive")
    semantic_ids = {row.realization.semantic_task_id for row in rows}
    instance_ids = {row.semantic_instance_id for row in rows}
    binding_ids = {row.binding_snapshot_id for row in rows}
    if len(semantic_ids) != 1 or len(instance_ids) != 1 or len(binding_ids) != 1:
        raise ValueError("realization portfolio candidates must share one semantic binding")
    if any(not row.realization.validation.passed for row in rows):
        raise ValueError("realization portfolio cannot compensate for invalid candidates")
    realization_ids = [row.realization.realization_id for row in rows]
    package_ids = [row.realized_package_id for row in rows]
    if len(package_ids) != len(set(package_ids)):
        raise ValueError("realization portfolio contains duplicate realized packages")
    if len(realization_ids) != len(set(realization_ids)):
        raise ValueError("realization portfolio contains duplicate realization identities")
    if len({row.realization.final_instruction for row in rows}) != len(rows):
        raise ValueError("realization portfolio contains duplicate final instructions")

    remaining = list(rows)
    selected: list[RealizedTaskPackage] = []
    seen_skeletons: set[str] = set()
    seen_styles: set[str] = set()
    seen_languages: set[str] = set()
    while remaining and len(selected) < min(max_realizations, len(rows)):

        def score(row: RealizedTaskPackage) -> tuple[int, int, int, int, str]:
            realization = row.realization
            return (
                int(realization.style == "canonical" and not selected),
                int(realization.normalized_skeleton not in seen_skeletons),
                int(realization.style not in seen_styles),
                int(realization.language not in seen_languages),
                canonical_hash(
                    {
                        "binding_snapshot_id": realization.binding_snapshot_id,
                        "renderer_profile_id": realization.renderer_profile_id,
                    }
                ),
            )

        chosen = max(remaining, key=score)
        remaining.remove(chosen)
        selected.append(chosen)
        seen_skeletons.add(chosen.realization.normalized_skeleton)
        seen_styles.add(chosen.realization.style)
        seen_languages.add(chosen.realization.language)

    candidate_ids = tuple(sorted(realization_ids))
    candidate_package_ids = tuple(sorted(package_ids))
    selected_ids = tuple(row.realization.realization_id for row in selected)
    selected_package_ids = tuple(row.realized_package_id for row in selected)
    selected_set = set(selected_ids)
    rejected_ids = tuple(item for item in candidate_ids if item not in selected_set)
    selected_package_set = set(selected_package_ids)
    rejected_package_ids = tuple(
        item for item in candidate_package_ids if item not in selected_package_set
    )
    payload = {
        "semantic_schema_id": next(iter(semantic_ids)),
        "semantic_instance_id": next(iter(instance_ids)),
        "binding_snapshot_id": next(iter(binding_ids)),
        "candidate_realized_package_ids": candidate_package_ids,
        "selected_realized_package_ids": selected_package_ids,
        "rejected_realized_package_ids": rejected_package_ids,
        "candidate_realization_ids": candidate_ids,
        "selected_realization_ids": selected_ids,
        "rejected_realization_ids": rejected_ids,
        "parent_weight_numerator": 1,
        "child_weight_denominator": len(selected),
        "selection_policy_id": "deterministic_realization_portfolio.v2",
        "schema_version": "realization_portfolio.v2",
    }
    portfolio_id = canonical_hash(payload, prefix="realization_portfolio:")
    return RealizationPortfolio(portfolio_id=portfolio_id, **payload), tuple(selected)


def _realization_identity(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "realization_id"}
