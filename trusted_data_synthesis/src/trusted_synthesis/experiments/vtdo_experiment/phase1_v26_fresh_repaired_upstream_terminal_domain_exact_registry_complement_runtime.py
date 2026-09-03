# ruff: noqa: E501
from __future__ import annotations

import hashlib
from typing import Any, cast

from trusted_synthesis.core.task import fresh_artifact_backed_outcome_authority as outcome_authority
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_runtime as v217_runtime,
)
from trusted_synthesis.hashing import canonical_hash


class LifetimeStableSourceExitProofAuthority(v217_runtime.SourceExitProofAuthority):
    """Preserves exception identities for the lifetime of the v26.217 authority."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._retained_error_objects: list[Any] = []

    def record_transport_exit(self, *, error: Any, exit_code: str, dispatch: Any) -> Any:
        proof = super().record_transport_exit(error=error, exit_code=exit_code, dispatch=dispatch)
        self._retained_error_objects.append(error)
        return proof

    def record_projection_exit(self, *, error: Any, response: Any) -> Any:
        proof = super().record_projection_exit(error=error, response=response)
        self._retained_error_objects.append(error)
        return proof


class ExactRegistryComplementAuthority:
    """Admits a terminal partition only against the actual frozen Registry object."""

    def __init__(
        self,
        *,
        registry: outcome_authority.FreshTerminalRegistry,
        expected_binding: models.ExactRegistryComplementBinding,
    ) -> None:
        self._registry = registry
        self._expected = expected_binding

    def _actual_reachable_items(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted(
                (item.terminal_kind, item.policy_id)
                for item in self._registry.policies
                if item.registration_status == "reachable"
            )
        )

    def admit(
        self, candidate: models.ExactRegistryComplementBinding
    ) -> models.ExactRegistryComplementBinding:
        strict = models.ExactRegistryComplementBinding.model_validate(
            candidate.model_dump(mode="python", warnings=False)
        )
        actual = self._actual_reachable_items()
        admitted = set(strict.admitted_terminal_kinds)
        actual_kinds = {item[0] for item in actual}
        exact_forbidden = tuple(sorted(actual_kinds - admitted))
        if (
            models.canonical_bytes(strict) != models.canonical_bytes(self._expected)
            or self._registry.registry_id != models.EXACT_V195_REGISTRY_ID
            or strict.exact_v195_terminal_registry_id != self._registry.registry_id
            or strict.reachable_terminal_policy_items != actual
            or strict.forbidden_terminal_kinds != exact_forbidden
            or admitted | set(strict.forbidden_terminal_kinds) != actual_kinds
            or admitted & set(strict.forbidden_terminal_kinds)
        ):
            raise ValueError("terminal domain is not the exact v26.195 reachable complement")
        return strict


class ComplementParentGuard:
    def __init__(
        self,
        *,
        binding: models.ExactRegistryComplementBinding,
        composition: models.CompositionContract,
    ) -> None:
        self._binding = binding
        self._composition = composition

    def admit(
        self,
        binding: models.ExactRegistryComplementBinding,
        composition: models.CompositionContract,
    ) -> None:
        strict_binding = models.ExactRegistryComplementBinding.model_validate(
            binding.model_dump(mode="python", warnings=False)
        )
        strict_composition = models.CompositionContract.model_validate(
            composition.model_dump(mode="python", warnings=False)
        )
        if (
            models.canonical_bytes(strict_binding) != models.canonical_bytes(self._binding)
            or models.canonical_bytes(strict_composition)
            != models.canonical_bytes(self._composition)
            or strict_composition.complement_binding_id != strict_binding.binding_id
        ):
            raise ValueError("v26.218 complement consumer parents differ")


class ExactComplementFailureConsumer:
    """Runs complement admission before the unchanged v26.217 single consumer."""

    def __init__(
        self,
        *,
        binding: models.ExactRegistryComplementBinding,
        composition: models.CompositionContract,
        authority: ExactRegistryComplementAuthority,
        v217_consumer: v217_runtime.ArtifactBackedFailureConsumer,
    ) -> None:
        self._binding = binding
        self._composition = composition
        self._authority = authority
        self._v217_consumer = v217_consumer
        self._guard = ComplementParentGuard(binding=binding, composition=composition)

    def execute_preflight(self, **kwargs: Any) -> v217_runtime.PreflightExecution:
        self._guard.admit(self._binding, self._composition)
        self._authority.admit(self._binding)
        module = cast(Any, v217_runtime)
        original = module.SourceExitProofAuthority
        module.SourceExitProofAuthority = LifetimeStableSourceExitProofAuthority
        try:
            return self._v217_consumer.execute_preflight(**kwargs)
        finally:
            module.SourceExitProofAuthority = original


def _candidate_identity(values: dict[str, Any], prefix: str) -> str:
    return canonical_hash(values, prefix=prefix)


def run_same_length_full_rehash_attack(
    *,
    authority: ExactRegistryComplementAuthority,
    binding: models.ExactRegistryComplementBinding,
    composition: models.CompositionContract,
) -> models.ComplementNegativeControl:
    wrong_forbidden = tuple(
        sorted(
            {
                (
                    "provider_no_payload_failure"
                    if item == "provider_failure_no_payload"
                    else "resource_failure"
                    if item == "resource_budget_exhausted"
                    else item
                )
                for item in binding.forbidden_terminal_kinds
            }
        )
    )
    if len(wrong_forbidden) != 15:
        raise ValueError("same-length Registry complement attack geometry differs")
    binding_values = binding.model_dump(mode="python", exclude={"binding_id"}, warnings=False)
    binding_values["forbidden_terminal_kinds"] = wrong_forbidden
    candidate_binding_id = _candidate_identity(
        binding_values, "fresh_repaired_exact_v195_registry_complement_binding:"
    )
    candidate = models.ExactRegistryComplementBinding.model_construct(
        binding_id=candidate_binding_id, **binding_values
    )
    composition_values = composition.model_dump(
        mode="python", exclude={"contract_id"}, warnings=False
    )
    composition_values["complement_binding_id"] = candidate_binding_id
    candidate_composition_id = _candidate_identity(
        composition_values,
        "fresh_repaired_exact_registry_complement_composition_contract:",
    )
    candidate_gate_id = _candidate_identity(
        {
            "gate_name": "exact_v195_reachable_terminal_complement",
            "evidence_id": candidate_binding_id,
            "passed": True,
            "schema_version": models.SCHEMA_VERSION,
        },
        "finance_v26_218_gate:",
    )
    candidate_report_id = _candidate_identity(
        {
            "candidate_binding_id": candidate_binding_id,
            "candidate_composition_id": candidate_composition_id,
            "candidate_gate_id": candidate_gate_id,
            "claimed_result": "passed",
            "schema_version": models.SCHEMA_VERSION,
        },
        "finance_v26_218_fully_rehashed_attack_report:",
    )
    try:
        authority.admit(candidate)
    except ValueError as error:
        return cast(
            models.ComplementNegativeControl,
            models.make_identity(
                models.ComplementNegativeControl,
                {
                    "candidate_binding_id": candidate_binding_id,
                    "candidate_composition_id": candidate_composition_id,
                    "candidate_gate_id": candidate_gate_id,
                    "candidate_report_id": candidate_report_id,
                    "rejection_reason_sha256": hashlib.sha256(
                        str(error).encode("utf-8")
                    ).hexdigest(),
                },
                field="control_id",
                prefix="finance_v26_218_registry_complement_negative_control:",
            ),
        )
    raise ValueError("same-length misspelled Registry complement attack was admitted")
