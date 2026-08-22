from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.domains.finance.executable_support_runtime import (
    FinanceExecutableSupportRuntime,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceTypedRecoveryScenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    UNKNOWN_TOOL_ERROR_CODE,
    resolve_model_selectable_tool_or_typed_failure,
)
from trusted_synthesis.runtime.agent.public_operation import (
    public_action_neutral_repair_result,
    public_operation_step_rejection,
    public_postcompletion_action_rejection,
    public_terminal_verification_rejection,
)
from trusted_synthesis.runtime.tools import (
    ARGUMENT_PATCH_REQUIRED_POLICY,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    AgentToolResult,
    agent_tool_argument_rejection,
)

VERIFIER_V3_CONTRACT_VERSION: Final[Literal["finance_v26_authority_verifier_contract.v3"]] = (
    "finance_v26_authority_verifier_contract.v3"
)
VERIFIER_V3_REPLAY_VERSION: Final[Literal["finance_v26_authority_verifier_replay.v3"]] = (
    "finance_v26_authority_verifier_replay.v3"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AuthorityPreservingReplayV3Contract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_contract_id: str = Field(min_length=1)
    shared_runtime_verifier_tool_availability_gate: Literal[True] = True
    unknown_or_unselectable_tool_error_code: Literal["unknown_or_unselectable_tool"] = (
        UNKNOWN_TOOL_ERROR_CODE
    )
    unavailable_tool_replayed_as_exact_typed_failure: Literal[True] = True
    verifier_may_insert_or_choose_model_action: Literal[False] = False
    historical_result_reclassification_allowed: Literal[False] = False
    schema_version: Literal["finance_v26_authority_verifier_contract.v3"] = (
        VERIFIER_V3_CONTRACT_VERSION
    )

    @model_validator(mode="after")
    def validate_contract(self) -> AuthorityPreservingReplayV3Contract:
        if self.contract_id != authority_preserving_replay_v3_contract_id(self):
            raise ValueError("Verifier v3 Contract identity changed")
        return self


class AuthorityPreservingReplayV3Result(FrozenModel):
    replay_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    predecessor_contract_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    observation_count: int = Field(ge=0)
    replayed_observation_count: int = Field(ge=0)
    exact_unavailable_tool_failure_count: int = Field(ge=0)
    selected_evidence_ids: tuple[str, ...]
    failure_ids: tuple[str, ...]
    passed: bool
    historical_observations_mutated: Literal[False] = False
    schema_version: Literal["finance_v26_authority_verifier_replay.v3"] = VERIFIER_V3_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> AuthorityPreservingReplayV3Result:
        if self.replayed_observation_count != self.observation_count:
            raise ValueError("Verifier v3 did not Replay every Observation")
        if self.passed != (not self.failure_ids):
            raise ValueError("Verifier v3 pass flag differs from failures")
        if self.replay_id != authority_preserving_replay_v3_result_id(self):
            raise ValueError("Verifier v3 Replay identity changed")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def authority_preserving_replay_v3_contract_id(
    value: AuthorityPreservingReplayV3Contract,
) -> str:
    return _identity(value, "contract_id", "finance_v26_authority_verifier_contract_v3:")


def authority_preserving_replay_v3_result_id(
    value: AuthorityPreservingReplayV3Result,
) -> str:
    return _identity(value, "replay_id", "finance_v26_authority_verifier_replay_v3:")


def make_authority_preserving_replay_v3_contract(
    predecessor: AuthorityPreservingReplayContract,
) -> AuthorityPreservingReplayV3Contract:
    values = {"predecessor_contract_id": predecessor.contract_id}
    provisional = AuthorityPreservingReplayV3Contract.model_construct(
        contract_id="pending",
        **values,
    )
    return AuthorityPreservingReplayV3Contract(
        contract_id=authority_preserving_replay_v3_contract_id(provisional),
        **values,
    )


def _canonical_payload(value: AgentToolResult | AgentToolObservation) -> dict[str, Any]:
    payload = {
        "status": value.status,
        "result": value.result,
        "evidence_ids": value.evidence_ids,
        "provenance_hashes": value.provenance_hashes,
        "host_events": value.host_events,
        "error_code": value.error_code,
        "error_message": value.error_message,
    }
    loaded = json.loads(json.dumps(payload, sort_keys=True))
    if not isinstance(loaded, dict):
        raise ValueError("Verifier v3 canonical payload is not an object")
    return loaded


def _call_signature(observation: AgentToolObservation) -> str:
    return canonical_hash(
        {
            "tool_id": observation.call.tool_id,
            "arguments": observation.call.arguments,
        },
        prefix="finance_v26_authority_verifier_v3_failed_call:",
    )


def _observation_identity_valid(observation: AgentToolObservation) -> bool:
    try:
        AgentToolObservation.model_validate(observation.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def replay_authority_preserving_observations_v3(
    contract: AuthorityPreservingReplayV3Contract,
    predecessor_contract: AuthorityPreservingReplayContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    observations: Sequence[AgentToolObservation],
) -> AuthorityPreservingReplayV3Result:
    if contract.predecessor_contract_id != predecessor_contract.contract_id:
        raise ValueError("Verifier v3 is detached from its qualified predecessor")
    package = record.task_package
    if (
        package.operation_contract is None
        or package.action_neutral_repair_contract is None
        or package.terminal_verification_target is None
    ):
        raise ValueError("Verifier v3 requires authority-preserving public contracts")
    recovery = (
        FinanceTypedRecoveryScenario.model_validate(record.recovery_scenario)
        if record.recovery_scenario is not None
        else None
    )
    runtime = FinanceExecutableSupportRuntime(
        record.public_corpus,
        environment,
        recovery_scenario=recovery,
    )
    task = package.task.public
    failures: list[str] = []
    failed_signatures: set[str] = set()
    observed: list[AgentToolObservation] = []
    replayed_count = 0
    unavailable_count = 0
    for index, observation in enumerate(observations):
        if not _observation_identity_valid(observation):
            failures.append(f"observation:{index}:identity")
            observed.append(observation)
            replayed_count += 1
            continue
        if observation.environment_manifest_id != environment.manifest_id:
            failures.append(f"observation:{index}:environment_identity")
            observed.append(observation)
            replayed_count += 1
            continue
        spec, unavailable = resolve_model_selectable_tool_or_typed_failure(
            environment,
            observation.call,
        )
        if unavailable is not None:
            replayed = unavailable
            unavailable_count += 1
        else:
            if spec is None:
                raise ValueError("Verifier v3 availability gate returned no outcome")
            signature = _call_signature(observation)
            if signature in failed_signatures:
                replayed = AgentToolResult(
                    status="failed",
                    result={
                        "retry_contract": {
                            "policy": ARGUMENT_PATCH_REQUIRED_POLICY,
                            "suggested_argument_patch": {
                                "rule": (
                                    "change at least one argument according to the latest public "
                                    "error; the identical failed action remains blocked"
                                )
                            },
                        }
                    },
                    error_code="identical_failed_action_blocked",
                    error_message=(
                        "The Host blocked an identical failed action without executing it."
                    ),
                )
            else:
                replayed = (
                    public_postcompletion_action_rejection(
                        task,
                        tuple(observed),
                        observation.call,
                    )
                    or agent_tool_argument_rejection(spec, observation.call)
                    or public_terminal_verification_rejection(
                        task,
                        tuple(observed),
                        observation.call,
                    )
                    or public_operation_step_rejection(
                        task,
                        tuple(observed),
                        observation.call,
                    )
                    or runtime.execute(observation.call)
                )
            replayed = public_action_neutral_repair_result(
                task,
                tuple(observed),
                observation.call,
                replayed,
            )
            if replayed.status == "succeeded":
                try:
                    spec.validate_output(replayed.result)
                except ValueError as error:
                    failures.append(f"observation:{index}:output_contract:{error}")
            signature = _call_signature(observation)
            if observation.status == "succeeded":
                failed_signatures.clear()
            else:
                failed_signatures.add(signature)
        if _canonical_payload(replayed) != _canonical_payload(observation):
            failures.append(f"observation:{index}:replay_mismatch")
        replayed_count += 1
        observed.append(observation)
    values = {
        "contract_id": contract.contract_id,
        "predecessor_contract_id": predecessor_contract.contract_id,
        "task_package_id": package.package_id,
        "environment_manifest_id": environment.manifest_id,
        "observation_count": len(observations),
        "replayed_observation_count": replayed_count,
        "exact_unavailable_tool_failure_count": unavailable_count,
        "selected_evidence_ids": tuple(sorted(runtime.selected_evidence_ids)),
        "failure_ids": tuple(failures),
        "passed": not failures,
    }
    provisional = AuthorityPreservingReplayV3Result.model_construct(
        replay_id="pending",
        **values,
    )
    return AuthorityPreservingReplayV3Result(
        replay_id=authority_preserving_replay_v3_result_id(provisional),
        **values,
    )
