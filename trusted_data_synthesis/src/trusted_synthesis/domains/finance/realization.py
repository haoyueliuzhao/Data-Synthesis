from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.pattern_compiler import TaskPatternInstantiation
from trusted_synthesis.core.task.realization import (
    RealizationPortfolio,
    RealizedTaskPackage,
    realize_task,
    select_realization_portfolio,
)
from trusted_synthesis.core.task.semantic import (
    SemanticBindingBundle,
    build_semantic_binding_bundle,
)
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.question_rendering import (
    finance_question_slots,
    finance_renderer_registry,
)
from trusted_synthesis.hashing import canonical_hash


class FinanceRealizationCompilation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    compilation_id: str = Field(min_length=1)
    semantic_binding: SemanticBindingBundle
    candidates: tuple[RealizedTaskPackage, ...] = Field(min_length=1)
    portfolio: RealizationPortfolio
    selected: tuple[RealizedTaskPackage, ...] = Field(min_length=1)
    gates: dict[str, bool]
    schema_version: str = "finance_realization_compilation.v1"

    @model_validator(mode="after")
    def validate_compilation(self) -> FinanceRealizationCompilation:
        failures = tuple(check_id for check_id, passed in self.gates.items() if not passed)
        if failures:
            raise ValueError(f"finance realization compilation failed gates: {failures}")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"compilation_id"}),
            prefix="finance_realization_compilation:",
        )
        if self.compilation_id != expected:
            raise ValueError("finance realization compilation identity is invalid")
        return self


def compile_finance_realization_portfolio(
    instantiation: TaskPatternInstantiation,
    bundle: EvidenceBundle,
    proof_graph: ProofGraph,
    *,
    max_realizations: int = 3,
) -> FinanceRealizationCompilation:
    registry = finance_vnext_operation_registry()
    semantic_binding = build_semantic_binding_bundle(
        pattern=instantiation.pattern,
        program=instantiation.program,
        binding=instantiation.binding,
        bundle=bundle,
        proof_graph=proof_graph,
        registry=registry,
    )
    evidence_by_role = _resolve_evidence_by_role(instantiation, bundle)
    available_slots = finance_question_slots(instantiation.pattern.task_type, evidence_by_role)
    renderer_registry = finance_renderer_registry()
    profiles = renderer_registry.for_task_type(instantiation.pattern.task_type)
    candidates = tuple(
        realize_task(
            plan=semantic_binding.plan,
            binding=semantic_binding.binding,
            task=instantiation.task,
            profile=profile,
            slot_values={
                slot: available_slots[slot]
                for slot in (*profile.required_slots, *profile.optional_slots)
            },
        )
        for profile in profiles
    )
    canonical = next(
        (
            row
            for row in candidates
            if row.realization.renderer_profile_id == instantiation.pattern.instruction_renderer_id
        ),
        None,
    )
    portfolio, selected = select_realization_portfolio(
        candidates,
        max_realizations=max_realizations,
    )
    realization_ids = [row.realization.realization_id for row in candidates]
    instructions = [row.realization.final_instruction for row in candidates]
    gates = {
        "renderer_profile_count_at_least_four": len(profiles) >= 4,
        "canonical_profile_present": canonical is not None,
        "canonical_instruction_byte_identical": bool(
            canonical is not None
            and canonical.realization.final_instruction == instantiation.task.public.instruction
        ),
        "canonical_task_hash_preserved": bool(
            canonical is not None and canonical.task.task_hash == instantiation.task.task_hash
        ),
        "all_realizations_valid": all(row.realization.validation.passed for row in candidates),
        "answer_exposure_zero": sum(
            row.realization.validation.answer_exposure_count for row in candidates
        )
        == 0,
        "semantic_parent_identity_match": all(
            row.realization.semantic_task_id == semantic_binding.plan.semantic_task_id
            for row in candidates
        ),
        "binding_snapshot_identity_match": all(
            row.binding_snapshot_id == semantic_binding.binding.binding_snapshot_id
            for row in candidates
        ),
        "legacy_task_identity_preserved": all(
            row.task.task_id == instantiation.task.task_id for row in candidates
        ),
        "realization_identity_collision_zero": len(realization_ids) == len(set(realization_ids)),
        "instruction_collision_zero": len(instructions) == len(set(instructions)),
        "portfolio_bound_respected": len(selected) <= max_realizations,
        "parent_weight_conserved": portfolio.child_weight_denominator == len(selected),
    }
    payload = {
        "semantic_binding": semantic_binding,
        "candidates": candidates,
        "portfolio": portfolio,
        "selected": selected,
        "gates": gates,
        "schema_version": "finance_realization_compilation.v1",
    }
    compilation_id = canonical_hash(
        {
            key: (
                [item.model_dump(mode="json") for item in value]
                if isinstance(value, tuple)
                else value.model_dump(mode="json")
                if isinstance(value, BaseModel)
                else value
            )
            for key, value in payload.items()
        },
        prefix="finance_realization_compilation:",
    )
    return FinanceRealizationCompilation(compilation_id=compilation_id, **payload)


def _resolve_evidence_by_role(
    instantiation: TaskPatternInstantiation,
    bundle: EvidenceBundle,
) -> dict[str, tuple[EvidenceItem, ...]]:
    by_id = {item.evidence_id: item for item in bundle.evidence}
    resolved: dict[str, tuple[EvidenceItem, ...]] = {}
    for role in instantiation.pattern.evidence_roles:
        try:
            resolved[role.role_id] = tuple(
                by_id[evidence_id]
                for evidence_id in instantiation.binding.role_bindings[role.role_id]
            )
        except KeyError as exc:
            raise ValueError(
                f"realization evidence is absent from the exact binding: {exc.args[0]}"
            ) from exc
    return resolved
