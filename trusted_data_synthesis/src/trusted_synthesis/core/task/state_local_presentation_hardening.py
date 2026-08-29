from __future__ import annotations

import hashlib
import itertools
from collections.abc import Sequence
from typing import Final, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.joint_presentation_receipt_hardening import (
    DISPLAY_CHOICE_PATTERN,
    VALUE_HANDLE_PATTERN,
    ActionAcceptanceReport,
    ExactFailureReceipt,
    HardenedLegendEntry,
    HardenedPublicObservation,
    HardenedPublicPrompt,
    HardenedPublicState,
    HardenedStepRecord,
    ReplicaSemanticValue,
    StateBoundMechanismQualification,
    StateBoundQualifiedValidity,
    StepRuntimeResult,
    classify_action_acceptance,
    execution_parent_hash,
    make_hardened_observation,
    make_identity_model,
    public_only_select_hardened_action,
    resolve_encoded_operation,
    resolve_runtime_operation,
    topological_components,
)
from trusted_synthesis.core.task.public_semantic_capability_depth import (
    PUBLIC_ACTION_ID_LENGTH,
    canonical_bytes,
)
from trusted_synthesis.core.task.validity_separated_capability_depth import (
    CausalTargetComponent,
    PresentedChoiceCandidate,
    ValiditySeparatedPublicTask,
)
from trusted_synthesis.hashing import canonical_hash

STATE_LOCAL_PRESENTATION_VERSION: Final = "state_local_higher_order_presentation.v1"
STATE_LOCAL_PRESENTATION_SALT: Final = "finance-v26.175-state-local-higher-order-presentation-v1"
BASE_VISIBLE_RANK_CHANNELS: Final = (
    "candidate",
    "action",
    "legend",
    "display",
)
T = TypeVar("T")


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


class StateLocalRankSchedule(FrozenModel):
    schedule_id: str = Field(min_length=1)
    schedule_contract_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    source_choice_handles: tuple[str, ...] = Field(min_length=2, max_length=3)
    reference_choice_handle: str = Field(min_length=1)
    argument_fields: tuple[str, ...] = Field(min_length=1)
    derivation_nonce: int = Field(ge=0)
    seed_commitment: str = Field(pattern=r"^[0-9a-f]{64}$")
    master_rank_by_replica: tuple[tuple[int, ...], ...] = Field(
        min_length=6,
        max_length=6,
    )
    channel_rank_relabelings: dict[str, tuple[int, ...]] = Field(min_length=5)
    frozen_before_model_outcome: Literal[True] = True
    reference_first_source_normalization: Literal[False] = False
    schema_version: str = STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_schedule(self) -> StateLocalRankSchedule:
        choice_count = len(self.source_choice_handles)
        expected_ranks = set(range(choice_count))
        if len(set(self.source_choice_handles)) != choice_count:
            raise ValueError("State-local schedule repeats a source Choice")
        if self.reference_choice_handle not in self.source_choice_handles:
            raise ValueError("State-local schedule loses the reference Choice")
        if len(set(self.argument_fields)) != len(self.argument_fields):
            raise ValueError("State-local schedule repeats an argument field")
        expected_channels = set(BASE_VISIBLE_RANK_CHANNELS) | {
            f"value{index}" for index in range(len(self.argument_fields))
        }
        if set(self.channel_rank_relabelings) != expected_channels:
            raise ValueError("State-local schedule visible channel surface changed")
        for row in self.master_rank_by_replica:
            if len(row) != choice_count or set(row) != expected_ranks:
                raise ValueError("State-local master row is not a Choice permutation")
        baseline = 6 // choice_count
        for source_index in range(choice_count):
            observed = tuple(row[source_index] for row in self.master_rank_by_replica)
            if any(observed.count(rank) != baseline for rank in expected_ranks):
                raise ValueError("State-local master rank is not Replica-balanced")
        for channel, relabeling in self.channel_rank_relabelings.items():
            if len(relabeling) != choice_count or set(relabeling) != expected_ranks:
                raise ValueError(f"State-local channel relabeling is invalid:{channel}")
        seed_payload = {
            "salt": STATE_LOCAL_PRESENTATION_SALT,
            "schedule_contract_id": self.schedule_contract_id,
            "source_package_artifact_id": self.source_package_artifact_id,
            "component_key": self.component_key,
            "source_choice_handles": self.source_choice_handles,
            "reference_choice_handle": self.reference_choice_handle,
            "argument_fields": self.argument_fields,
            "derivation_nonce": self.derivation_nonce,
        }
        expected_seed = hashlib.sha256(canonical_bytes(seed_payload)).hexdigest()
        if self.seed_commitment != expected_seed:
            raise ValueError("State-local schedule seed commitment is invalid")
        if self.schedule_id != _identity(
            self,
            "schedule_id",
            "state_local_rank_schedule:",
        ):
            raise ValueError("State-local rank Schedule identity is invalid")
        return self


def _hash_order(values: Sequence[T], *, seed: str, channel: str) -> tuple[T, ...]:
    return tuple(
        sorted(
            values,
            key=lambda value: hashlib.sha256(
                canonical_bytes(
                    {
                        "seed": seed,
                        "channel": channel,
                        "value": value,
                    }
                )
            ).hexdigest(),
        )
    )


def _argument_fields(
    *,
    source_package_artifact_id: str,
    component: CausalTargetComponent,
) -> tuple[str, ...]:
    operations = tuple(item.operation for item in component.public_state.choice_legend)
    if len({item.decision_kind for item in operations}) != 1:
        raise ValueError("State-local Prompt crosses Decision kinds")
    if len({item.tool_id for item in operations}) != 1:
        raise ValueError("State-local Prompt crosses Tool schemas")
    canonical_fields = tuple(sorted(operations[0].arguments))
    if any(tuple(sorted(item.arguments)) != canonical_fields for item in operations):
        raise ValueError("State-local Prompt crosses an argument schema")
    unique_count_by_field = {
        field: len({canonical_bytes(item.arguments[field]) for item in operations})
        for field in canonical_fields
    }
    return tuple(
        sorted(
            canonical_fields,
            key=lambda field: (
                -unique_count_by_field[field],
                hashlib.sha256(
                    (
                        f"{STATE_LOCAL_PRESENTATION_SALT}|{source_package_artifact_id}|"
                        f"{component.component_key}|field|{field}"
                    ).encode()
                ).hexdigest(),
            ),
        )
    )


def make_state_local_rank_schedule(
    *,
    schedule_contract_id: str,
    source_package_artifact_id: str,
    component: CausalTargetComponent,
    derivation_nonce: int = 0,
) -> StateLocalRankSchedule:
    source_entries = tuple(component.public_state.choice_legend)
    ordered_entries = tuple(
        sorted(
            source_entries,
            key=lambda item: (
                canonical_bytes(item.operation.model_dump(mode="json")),
                item.choice_handle,
            ),
        )
    )
    source_choice_handles = tuple(item.choice_handle for item in ordered_entries)
    fields = _argument_fields(
        source_package_artifact_id=source_package_artifact_id,
        component=component,
    )
    seed_payload = {
        "salt": STATE_LOCAL_PRESENTATION_SALT,
        "schedule_contract_id": schedule_contract_id,
        "source_package_artifact_id": source_package_artifact_id,
        "component_key": component.component_key,
        "source_choice_handles": source_choice_handles,
        "reference_choice_handle": component.reference_choice_handle,
        "argument_fields": fields,
        "derivation_nonce": derivation_nonce,
    }
    seed = hashlib.sha256(canonical_bytes(seed_payload)).hexdigest()
    choice_count = len(source_choice_handles)
    permutations = tuple(itertools.permutations(range(choice_count)))
    if choice_count == 3:
        tagged_master = tuple((permutation, 0) for permutation in permutations)
    elif choice_count == 2:
        tagged_master = tuple(
            (permutation, repetition) for permutation in permutations for repetition in range(3)
        )
    else:
        raise ValueError("State-local schedule supports exactly two or three Choices")
    ordered_master = _hash_order(tagged_master, seed=seed, channel="master")
    master_rows = tuple(item[0] for item in ordered_master)
    channels = (*BASE_VISIBLE_RANK_CHANNELS, *(f"value{i}" for i in range(len(fields))))
    relabelings = {
        channel: _hash_order(permutations, seed=seed, channel=channel)[0] for channel in channels
    }
    values = {
        "schedule_contract_id": schedule_contract_id,
        "source_package_artifact_id": source_package_artifact_id,
        "component_key": component.component_key,
        "source_choice_handles": source_choice_handles,
        "reference_choice_handle": component.reference_choice_handle,
        "argument_fields": fields,
        "derivation_nonce": derivation_nonce,
        "seed_commitment": seed,
        "master_rank_by_replica": master_rows,
        "channel_rank_relabelings": relabelings,
    }
    provisional = StateLocalRankSchedule.model_construct(schedule_id="pending", **values)
    return StateLocalRankSchedule(
        schedule_id=_identity(provisional, "schedule_id", "state_local_rank_schedule:"),
        **values,
    )


def materialized_channel_schedule(
    schedule: StateLocalRankSchedule,
    channel: str,
) -> tuple[tuple[int, ...], ...]:
    try:
        relabeling = schedule.channel_rank_relabelings[channel]
    except KeyError as exc:
        raise ValueError(f"State-local visible rank channel is absent:{channel}") from exc
    return tuple(
        tuple(relabeling[master_rank] for master_rank in row)
        for row in schedule.master_rank_by_replica
    )


def schedule_codebook_signature(schedule: StateLocalRankSchedule) -> str:
    channels = tuple(sorted(schedule.channel_rank_relabelings))
    payload = {
        "choice_count": len(schedule.source_choice_handles),
        "channels": channels,
        "materialized": {
            channel: materialized_channel_schedule(schedule, channel) for channel in channels
        },
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _rank_by_source(
    schedule: StateLocalRankSchedule,
    *,
    channel: str,
    replica_index: int,
) -> dict[str, int]:
    rows = materialized_channel_schedule(schedule, channel)
    try:
        row = rows[replica_index]
    except IndexError as exc:
        raise ValueError("State-local Replica index is outside the frozen schedule") from exc
    return dict(zip(schedule.source_choice_handles, row, strict=True))


def _opaque_pool(prefix: str, context: str, count: int) -> tuple[str, ...]:
    return tuple(
        sorted(
            prefix
            + hashlib.sha256(
                f"{STATE_LOCAL_PRESENTATION_SALT}|{context}|pool|{index}".encode()
            ).hexdigest()
            for index in range(count)
        )
    )


def make_state_local_prompt(
    *,
    package_id: str,
    task: ValiditySeparatedPublicTask,
    component: CausalTargetComponent,
    replica_index: int,
    predecessor_observations: Sequence[HardenedPublicObservation],
    failure_receipt: ExactFailureReceipt | None,
    schedule: StateLocalRankSchedule,
) -> tuple[HardenedPublicPrompt, dict[str, str]]:
    if component.component_key != schedule.component_key:
        raise ValueError("State-local Prompt crosses its Component Schedule")
    source_entries = tuple(component.public_state.choice_legend)
    by_source_handle = {item.choice_handle: item for item in source_entries}
    if set(by_source_handle) != set(schedule.source_choice_handles):
        raise ValueError("State-local Prompt Choice set differs from its Schedule")
    operations = {key: value.operation for key, value in by_source_handle.items()}
    fields = _argument_fields(
        source_package_artifact_id=schedule.source_package_artifact_id,
        component=component,
    )
    if fields != schedule.argument_fields:
        raise ValueError("State-local Prompt argument fields differ from its Schedule")
    choice_count = len(schedule.source_choice_handles)
    catalogs: dict[str, tuple[ReplicaSemanticValue, ...]] = {}
    value_handle_by_source: dict[str, dict[str, str]] = {}
    for field_index, field in enumerate(fields):
        channel = f"value{field_index}"
        rank_by_source = _rank_by_source(
            schedule,
            channel=channel,
            replica_index=replica_index,
        )
        pool = _opaque_pool(
            "public_value:",
            f"{package_id}|{component.component_key}|{replica_index}|{channel}|{field}",
            choice_count,
        )
        assignments = {
            source_handle: pool[rank_by_source[source_handle]]
            for source_handle in schedule.source_choice_handles
        }
        value_handle_by_source[field] = assignments
        entries = tuple(
            ReplicaSemanticValue(
                value_handle=assignments[source_handle],
                semantic_value=operations[source_handle].arguments[field],
            )
            for source_handle in schedule.source_choice_handles
        )
        catalogs[field] = tuple(sorted(entries, key=lambda item: item.value_handle))
    display_pool = _opaque_pool(
        "public_choice:",
        f"{package_id}|{component.component_key}|{replica_index}|display",
        choice_count,
    )
    action_pool = tuple(
        item.removeprefix("public_action:")[:PUBLIC_ACTION_ID_LENGTH]
        for item in _opaque_pool(
            "public_action:",
            f"{package_id}|{component.component_key}|{replica_index}|action",
            choice_count,
        )
    )
    display_rank = _rank_by_source(schedule, channel="display", replica_index=replica_index)
    action_rank = _rank_by_source(schedule, channel="action", replica_index=replica_index)
    legend_rank = _rank_by_source(schedule, channel="legend", replica_index=replica_index)
    candidate_rank = _rank_by_source(
        schedule,
        channel="candidate",
        replica_index=replica_index,
    )
    display_by_source = {
        source_handle: display_pool[display_rank[source_handle]]
        for source_handle in schedule.source_choice_handles
    }
    action_by_source = {
        source_handle: action_pool[action_rank[source_handle]]
        for source_handle in schedule.source_choice_handles
    }
    entries_by_source = {
        source_handle: HardenedLegendEntry(
            choice_handle=display_by_source[source_handle],
            value_handles=tuple(value_handle_by_source[field][source_handle] for field in fields),
        )
        for source_handle in schedule.source_choice_handles
    }
    ordered_entries = tuple(
        entries_by_source[source_handle]
        for source_handle in sorted(
            schedule.source_choice_handles,
            key=legend_rank.__getitem__,
        )
    )
    state_values = {
        "decision_kind": component.public_state.decision_kind,
        "tool_id": next(iter(operations.values())).tool_id,
        "facts": {
            key: value
            for key, value in component.public_state.facts.items()
            if key not in {"dependency_component_keys", "actual_failure_receipt"}
        },
        "argument_fields": fields,
        "argument_value_catalogs": catalogs,
        "choice_legend": ordered_entries,
        "prior_observations": tuple(predecessor_observations),
        "failure_receipt": failure_receipt,
    }
    provisional = HardenedPublicState.model_construct(state_token="0" * 24, **state_values)
    token_payload = provisional.model_dump(mode="json", exclude={"state_token"})
    state = HardenedPublicState(
        state_token=hashlib.sha256(canonical_bytes(token_payload)).hexdigest()[:24],
        **state_values,
    )
    source_order = tuple(sorted(schedule.source_choice_handles, key=candidate_rank.__getitem__))
    candidates = tuple(
        PresentedChoiceCandidate(
            action_id=action_by_source[source_handle],
            presentation_index=index,
            choice_handle=display_by_source[source_handle],
        )
        for index, source_handle in enumerate(source_order)
    )
    payload = {
        "task": task.model_dump(mode="json"),
        "state": state.model_dump(mode="json"),
        "candidates": [item.model_dump(mode="json") for item in candidates],
    }
    rendered = canonical_bytes(payload)
    prompt = HardenedPublicPrompt(
        prompt_hash=hashlib.sha256(rendered).hexdigest(),
        rendered_bytes=len(rendered),
        task=task,
        state=state,
        candidates=candidates,
    )
    source_by_display = {
        display_by_source[source_handle]: source_handle
        for source_handle in schedule.source_choice_handles
    }
    return prompt, source_by_display


def state_local_factorization_holds(schedule: StateLocalRankSchedule) -> bool:
    channels = tuple(schedule.channel_rank_relabelings)
    for replica_index, master_row in enumerate(schedule.master_rank_by_replica):
        for source_index, master_rank in enumerate(master_row):
            for channel in channels:
                materialized = materialized_channel_schedule(schedule, channel)
                if (
                    materialized[replica_index][source_index]
                    != (schedule.channel_rank_relabelings[channel][master_rank])
                ):
                    return False
    return True


__all__ = [
    "ActionAcceptanceReport",
    "DISPLAY_CHOICE_PATTERN",
    "ExactFailureReceipt",
    "HardenedPublicObservation",
    "HardenedPublicPrompt",
    "HardenedStepRecord",
    "StateBoundMechanismQualification",
    "StateBoundQualifiedValidity",
    "StateLocalRankSchedule",
    "StepRuntimeResult",
    "VALUE_HANDLE_PATTERN",
    "classify_action_acceptance",
    "execution_parent_hash",
    "make_hardened_observation",
    "make_identity_model",
    "make_state_local_prompt",
    "make_state_local_rank_schedule",
    "materialized_channel_schedule",
    "public_only_select_hardened_action",
    "resolve_encoded_operation",
    "resolve_runtime_operation",
    "schedule_codebook_signature",
    "state_local_factorization_holds",
    "topological_components",
]
