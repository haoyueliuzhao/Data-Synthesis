from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_action_constructibility_two_stage_preflight import (  # noqa: E501
    _path_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_profile_and_manifest_preflight import (  # noqa: E501
    TwoStageExecutionContract,
    TwoStageJob,
    TwoStageManifest,
    TwoStagePathAudit,
    TwoStageTaskPackage,
    two_stage_execution_contract_id,
    two_stage_job_id,
    two_stage_manifest_id,
    two_stage_path_audit_id,
    two_stage_task_package_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    TwoStageStaticInputs,
    load_two_stage_static_inputs,
    sha256_text,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    PublicActionState,
    build_public_action_state,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_exact_response_grammar import (
    ExactResponseModelRejection,
    StageOneResponseGrammarArtifact,
    compile_stage_one_response_grammar,
    parse_exact_semantic_proposal_payload,
    parse_prompt_only_reference_payload,
    prompt_only_reference_payload,
    render_exact_semantic_proposal_prompt,
    render_exact_semantic_proposal_rescue_prompt,
)
from trusted_synthesis.runtime.tools import AgentToolObservation

RUN_ID: Final = "finance_v26_112_exact_response_grammar_rematerialization_v1_20260823"
NEXT_STAGE: Final = "exact_response_grammar_runner_preflight_only"
PREDECESSOR_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_111_two_stage_semantic_proposal_calibration_postrun_audit_v1_20260823"
)
PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_two_stage_postrun_audit_report:"
    "44cc58aae8ca49faeb7843d0cd77e8bc4824028f047d1d87b0e2f298be80339a"
)
PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_two_stage_postrun_transition:"
    "6ae62c72a6f9023a1da40267c4515d0d23c8e833e919a4eb1285e84a0ab0c4bb"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_exact_response_grammar_rematerialization.py"
)
GRAMMAR_SOURCE_PATH: Final = (
    "src/trusted_synthesis/runtime/agent/prospective_two_stage_exact_response_grammar.py"
)
PROSPECTIVE_RUNNER_RUN_ID: Final = (
    "finance_v26_113_exact_response_grammar_runner_preflight_v1_20260823"
)
PROSPECTIVE_EXECUTION_RUN_ID: Final = (
    "finance_v26_114_exact_response_grammar_calibration_execution_v1_20260823"
)
PREDECESSOR_OUTPUTS: Final = (
    "authority_instrument_audit.json",
    "completion_rescue_audit.json",
    "destructive_audit.json",
    "execution_lineage_audit.json",
    "prompt_disclosure_audit.json",
    "prospective_transition_contract.json",
    "provider_telemetry_audit.json",
    "report.json",
    "response_interface_audit.json",
    "source_replay_audit.json",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal["v26_111_transitive_source", "v26_111_output", "v26_112_implementation"]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> SourceReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("v26.112 source replay changed")
        return self


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = PREDECESSOR_TRANSITION_ID
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2029, max_length=2029)
    predecessor_transitive_file_count: Literal[2017] = 2017
    predecessor_output_file_count: Literal[10] = 10
    implementation_file_count: Literal[2] = 2
    replayed_file_count: Literal[2029] = 2029
    replay_pass_count: Literal[2029] = 2029
    replay_before_grammar_compilation: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_grammar_source_replay.v1"] = (
        "finance_v26_exact_grammar_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.112 source replay paths are not canonical")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_exact_grammar_source_replay:"):
            raise ValueError("v26.112 source replay identity changed")
        return self


class PromptPathBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    successor_path_audit_id: str = Field(min_length=1)
    response_grammar_id: str = Field(min_length=1)
    semantic_proposal_prompt_sha256s: tuple[str, ...] = Field(min_length=1)
    rescue_prompt_sha256s: tuple[str, ...] = Field(min_length=1)
    final_answer_prompt_sha256: str = Field(min_length=64, max_length=64)
    semantic_proposal_prompt_byte_counts: tuple[int, ...] = Field(min_length=1)
    rescue_prompt_byte_counts: tuple[int, ...] = Field(min_length=1)
    prompt_only_primary_parse_pass_count: int = Field(gt=0)
    prompt_only_rescue_parse_pass_count: int = Field(gt=0)
    primary_rescue_semantic_projection_match_count: int = Field(gt=0)
    rescue_smaller_than_primary_count: int = Field(gt=0)
    state_binding_pass_count: int = Field(gt=0)
    schema_version: Literal["finance_v26_exact_grammar_prompt_path_binding.v1"] = (
        "finance_v26_exact_grammar_prompt_path_binding.v1"
    )

    @model_validator(mode="after")
    def validate_binding(self) -> PromptPathBinding:
        count = len(self.semantic_proposal_prompt_sha256s)
        if not all(
            value == count
            for value in (
                len(self.rescue_prompt_sha256s),
                len(self.semantic_proposal_prompt_byte_counts),
                len(self.rescue_prompt_byte_counts),
                self.prompt_only_primary_parse_pass_count,
                self.prompt_only_rescue_parse_pass_count,
                self.primary_rescue_semantic_projection_match_count,
                self.rescue_smaller_than_primary_count,
                self.state_binding_pass_count,
            )
        ):
            raise ValueError("v26.112 Prompt binding denominator changed")
        if self.binding_id != _identity(
            self, "binding_id", "finance_v26_exact_grammar_prompt_path_binding:"
        ):
            raise ValueError("v26.112 Prompt binding identity changed")
        return self


class ResponseConstructibilityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    response_grammar_id: str = Field(min_length=1)
    path_bindings: tuple[PromptPathBinding, ...] = Field(min_length=48, max_length=48)
    path_count: Literal[48] = 48
    semantic_proposal_state_count: Literal[324] = 324
    primary_prompt_count: Literal[324] = 324
    rescue_prompt_count: Literal[324] = 324
    prompt_only_parser_pass_count: Literal[648] = 648
    exact_state_binding_pass_count: Literal[648] = 648
    primary_rescue_semantic_projection_match_count: Literal[324] = 324
    rescue_smaller_than_primary_count: Literal[324] = 324
    maximum_primary_prompt_utf8_bytes: int = Field(gt=0, le=60_000)
    maximum_rescue_prompt_utf8_bytes: int = Field(gt=0, le=6_144)
    parser_schema_object_read_by_fixture: Literal[False] = False
    internal_proposal_instance_supplied_to_fixture: Literal[False] = False
    final_serialized_prompt_only_fixture_input: Literal[True] = True
    host_alias_normalization_count: Literal[0] = 0
    host_missing_field_insertion_count: Literal[0] = 0
    host_semantic_field_selection_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_response_constructibility_audit.v1"] = (
        "finance_v26_response_constructibility_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ResponseConstructibilityAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_response_constructibility_audit:"
        ):
            raise ValueError("v26.112 constructibility identity changed")
        return self


class CrossArtifactBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    response_grammar_id: str = Field(min_length=1)
    task_package_count: Literal[24] = 24
    path_count: Literal[48] = 48
    job_count: Literal[32] = 32
    task_response_grammar_binding_count: Literal[24] = 24
    path_prompt_binding_count: Literal[48] = 48
    job_contract_parent_binding_count: Literal[32] = 32
    job_task_parent_binding_count: Literal[32] = 32
    job_path_parent_binding_count: Literal[32] = 32
    profile_preservation_count: Literal[104] = 104
    resource_preservation_count: Literal[104] = 104
    task_identity_overlap_with_v26_108: Literal[0] = 0
    path_identity_overlap_with_v26_108: Literal[0] = 0
    job_identity_overlap_with_v26_108: Literal[0] = 0
    seed_projection_match_count: Literal[32] = 32
    source_projection_match_count: Literal[24] = 24
    path_projection_match_count: Literal[48] = 48
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_grammar_cross_binding.v1"] = (
        "finance_v26_exact_grammar_cross_binding.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CrossArtifactBindingAudit:
        if self.audit_id != _identity(self, "audit_id", "finance_v26_exact_grammar_cross_binding:"):
            raise ValueError("v26.112 cross-artifact identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_result(self) -> MutationResult:
        if self.mutation_id != _identity(
            self, "mutation_id", "finance_v26_exact_grammar_mutation:"
        ):
            raise ValueError("v26.112 mutation identity changed")
        return self


class DestructivePreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=16, max_length=16)
    mutation_count: Literal[16] = 16
    rejection_count: Literal[16] = 16
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_grammar_destructive.v1"] = (
        "finance_v26_exact_grammar_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructivePreflightAudit:
        if self.audit_id != _identity(self, "audit_id", "finance_v26_exact_grammar_destructive:"):
            raise ValueError("v26.112 destructive identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class ExactGrammarRematerializationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = PREDECESSOR_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    response_grammar_id: str = Field(min_length=1)
    response_constructibility_audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    cross_artifact_binding_audit_id: str = Field(min_length=1)
    destructive_preflight_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=9, max_length=9)
    status: Literal["exact_response_grammar_static_binding_passed"] = (
        "exact_response_grammar_static_binding_passed"
    )
    next_permitted_stage: str = NEXT_STAGE
    task_package_count: Literal[24] = 24
    path_count: Literal[48] = 48
    job_count: Literal[32] = 32
    model_profile_changed: Literal[False] = False
    completion_bound_changed: Literal[False] = False
    rollout_bound_changed: Literal[False] = False
    public_action_state_changed: Literal[False] = False
    stage_two_compiler_changed: Literal[False] = False
    task_or_seed_selection_changed: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_exact_grammar_rematerialization_report.v1"] = (
        "finance_v26_exact_grammar_rematerialization_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> ExactGrammarRematerializationReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.112 report details are not canonical")
        if self.report_id != _identity(
            self, "report_id", "finance_v26_exact_grammar_rematerialization_report:"
        ):
            raise ValueError("v26.112 report identity changed")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_source_replay(package_root: Path, implementation_root: Path) -> SourceReplayAudit:
    predecessor_root = package_root / PREDECESSOR_DIR
    report = _load_json(predecessor_root / "report.json")
    transition = _load_json(predecessor_root / "prospective_transition_contract.json")
    replay = _load_json(predecessor_root / "source_replay_audit.json")
    if (
        report["report_id"] != PREDECESSOR_REPORT_ID
        or transition["contract_id"] != PREDECESSOR_TRANSITION_ID
        or report["next_permitted_stage"]
        != "fresh_exact_response_grammar_taskpackage_contract_manifest_and_runner_preflight_only"
    ):
        raise ValueError("v26.112 predecessor authorization changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in replay["entries"]:
        relative = item["relative_path"]
        path = package_root / relative
        observed = _sha256(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_111_transitive_source",
            expected_sha256=item["observed_sha256"],
            observed_sha256=observed,
            byte_count=path.stat().st_size,
        )
    for name in PREDECESSOR_OUTPUTS:
        relative = f"{PREDECESSOR_DIR}/{name}"
        path = package_root / relative
        digest = _sha256(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_111_output",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    for relative in (GRAMMAR_SOURCE_PATH, IMPLEMENTATION_PATH):
        path = implementation_root / relative
        digest = _sha256(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_112_implementation",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    values = {"entries": tuple(entries[key] for key in sorted(entries))}
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_exact_grammar_source_replay:"),
        **values,
    )


def _build_tasks(
    predecessor: TwoStageStaticInputs, grammar: StageOneResponseGrammarArtifact
) -> tuple[TwoStageTaskPackage, ...]:
    rows = []
    for item in predecessor.tasks:
        values = item.model_dump(mode="python", exclude={"task_package_id"})
        values["compact_prompt_contract_id"] = grammar.grammar_id
        provisional = TwoStageTaskPackage.model_construct(task_package_id="pending", **values)
        rows.append(
            TwoStageTaskPackage(task_package_id=two_stage_task_package_id(provisional), **values)
        )
    return tuple(sorted(rows, key=lambda item: item.task_package_id))


def _semantic_prompts_and_final(
    predecessor: TwoStageStaticInputs, path: TwoStagePathAudit
) -> tuple[tuple[str, ...], str, tuple[PublicActionState, ...]]:
    exact_path = next(
        item
        for item in predecessor.historical.path_audits
        if item.audit_id == path.predecessor_path_audit_id
    )
    binding = _path_binding(predecessor.historical, exact_path)
    observations: list[AgentToolObservation] = []
    prompts: list[str] = []
    states: list[PublicActionState] = []
    condition = (
        None if binding.source_path.role == "capability" else binding.source_path.path_strategy_id
    )
    for step in binding.compiler_trajectory.steps:
        if step.tool_name is None:
            continue
        state = build_public_action_state(
            binding.record.task_package.task.public, binding.environment, tuple(observations)
        )
        states.append(state)
        prompts.append(
            render_exact_semantic_proposal_prompt(
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=condition,
            )
        )
        observations.append(AgentToolObservation.model_validate(step.observation))
    final_state = build_public_action_state(
        binding.record.task_package.task.public, binding.environment, tuple(observations)
    )
    if not final_state.final_answer_allowed:
        raise ValueError("v26.112 Compiler Path did not reach Final Ready")
    states.append(final_state)
    prompts.append(
        render_exact_semantic_proposal_prompt(
            instruction=binding.record.task_package.task.public.instruction,
            state=final_state,
            public_path_condition=condition,
        )
    )
    final_prompt = render_compact_final_prompt(
        binding.prompt_contract.public_context,
        binding.record.task_package.task.public,
        tuple(observations),
        public_path_condition=condition,
    )
    return tuple(prompts), final_prompt, tuple(states)


def _semantic_projection(value: BaseModel) -> dict[str, Any]:
    return value.model_dump(mode="json", exclude={"proposal_id"})


def _build_paths_and_prompts(
    predecessor: TwoStageStaticInputs,
    tasks: Sequence[TwoStageTaskPackage],
    grammar: StageOneResponseGrammarArtifact,
) -> tuple[
    tuple[TwoStagePathAudit, ...],
    tuple[PromptPathBinding, ...],
    ResponseConstructibilityAudit,
]:
    task_by_predecessor = {item.predecessor_task_package_id: item for item in tasks}
    path_rows: list[TwoStagePathAudit] = []
    pending_bindings: list[
        tuple[
            TwoStagePathAudit,
            TwoStagePathAudit,
            tuple[str, ...],
            str,
            tuple[PublicActionState, ...],
            tuple[str, ...],
        ]
    ] = []
    resource = predecessor.resource
    for old_path in predecessor.paths:
        semantic_prompts, final_prompt, states = _semantic_prompts_and_final(predecessor, old_path)
        rescues = tuple(
            render_exact_semantic_proposal_rescue_prompt(
                prompt,
                failure_family="response_serialization_failure",
                failure_subtype="semantic_proposal_not_exact_response_grammar",
            )
            for prompt in semantic_prompts
        )
        all_primary = (*semantic_prompts, final_prompt)
        upper = sum(
            len(prompt.encode("utf-8"))
            + resource.chat_envelope_tokens
            + resource.accounted_completion_bound_tokens
            for prompt in all_primary
        )
        upper += (
            resource.rescue_prompt_upper_bound_bytes
            + resource.chat_envelope_tokens
            + resource.accounted_completion_bound_tokens
        )
        task = task_by_predecessor[old_path.predecessor_task_package_id]
        values = old_path.model_dump(
            mode="python",
            exclude={
                "path_audit_id",
                "task_package_id",
                "maximum_primary_prompt_utf8_bytes",
                "static_complete_path_upper_bound_tokens",
                "static_rollout_headroom_tokens",
            },
        )
        values.update(
            task_package_id=task.task_package_id,
            maximum_primary_prompt_utf8_bytes=max(
                len(prompt.encode("utf-8")) for prompt in all_primary
            ),
            static_complete_path_upper_bound_tokens=upper,
            static_rollout_headroom_tokens=resource.rollout_upper_bound_tokens - upper,
        )
        provisional = TwoStagePathAudit.model_construct(path_audit_id="pending", **values)
        new_path = TwoStagePathAudit(path_audit_id=two_stage_path_audit_id(provisional), **values)
        path_rows.append(new_path)
        pending_bindings.append(
            (old_path, new_path, semantic_prompts, final_prompt, states, rescues)
        )
    paths = tuple(sorted(path_rows, key=lambda item: item.path_audit_id))
    bindings = []
    for old_path, new_path, prompts, final_prompt, states, rescues in pending_bindings:
        primary_proposals = tuple(parse_prompt_only_reference_payload(item) for item in prompts)
        rescue_proposals = tuple(parse_prompt_only_reference_payload(item) for item in rescues)
        if any(
            _semantic_projection(primary) != _semantic_projection(rescue)
            for primary, rescue in zip(primary_proposals, rescue_proposals, strict=True)
        ):
            raise ValueError("Primary and Rescue Prompt-only semantics differ")
        if any(
            proposal.state_id != state.state_id
            for proposal, state in zip(primary_proposals, states, strict=True)
        ):
            raise ValueError("Prompt-only proposal does not bind the current public state")
        values = {
            "predecessor_path_audit_id": old_path.path_audit_id,
            "successor_path_audit_id": new_path.path_audit_id,
            "response_grammar_id": grammar.grammar_id,
            "semantic_proposal_prompt_sha256s": tuple(sha256_text(item) for item in prompts),
            "rescue_prompt_sha256s": tuple(sha256_text(item) for item in rescues),
            "final_answer_prompt_sha256": sha256_text(final_prompt),
            "semantic_proposal_prompt_byte_counts": tuple(
                len(item.encode("utf-8")) for item in prompts
            ),
            "rescue_prompt_byte_counts": tuple(len(item.encode("utf-8")) for item in rescues),
            "prompt_only_primary_parse_pass_count": len(prompts),
            "prompt_only_rescue_parse_pass_count": len(rescues),
            "primary_rescue_semantic_projection_match_count": len(prompts),
            "rescue_smaller_than_primary_count": sum(
                len(rescue.encode("utf-8")) < len(primary.encode("utf-8"))
                for primary, rescue in zip(prompts, rescues, strict=True)
            ),
            "state_binding_pass_count": len(states),
        }
        provisional = PromptPathBinding.model_construct(binding_id="pending", **values)
        bindings.append(
            PromptPathBinding(
                binding_id=_identity(
                    provisional,
                    "binding_id",
                    "finance_v26_exact_grammar_prompt_path_binding:",
                ),
                **values,
            )
        )
    ordered_bindings = tuple(sorted(bindings, key=lambda item: item.binding_id))
    primary_sizes = tuple(
        size for item in ordered_bindings for size in item.semantic_proposal_prompt_byte_counts
    )
    rescue_sizes = tuple(
        size for item in ordered_bindings for size in item.rescue_prompt_byte_counts
    )
    values = {
        "response_grammar_id": grammar.grammar_id,
        "path_bindings": ordered_bindings,
        "maximum_primary_prompt_utf8_bytes": max(primary_sizes),
        "maximum_rescue_prompt_utf8_bytes": max(rescue_sizes),
    }
    provisional = ResponseConstructibilityAudit.model_construct(audit_id="pending", **values)
    constructibility = ResponseConstructibilityAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_response_constructibility_audit:"),
        **values,
    )
    return paths, ordered_bindings, constructibility


def _build_contract_jobs_manifest(
    replay: SourceReplayAudit,
    predecessor: TwoStageStaticInputs,
    tasks: Sequence[TwoStageTaskPackage],
    paths: Sequence[TwoStagePathAudit],
) -> tuple[TwoStageExecutionContract, tuple[TwoStageJob, ...], TwoStageManifest]:
    contract_values = predecessor.predecessor_contract.model_dump(
        mode="python",
        exclude={
            "contract_id",
            "predecessor_report_id",
            "source_replay_audit_id",
            "task_package_ids",
            "path_audit_ids",
            "prospective_runner_run_id",
            "prospective_execution_run_id",
        },
    )
    contract_values.update(
        predecessor_report_id=PREDECESSOR_REPORT_ID,
        source_replay_audit_id=replay.audit_id,
        task_package_ids=tuple(sorted(item.task_package_id for item in tasks)),
        path_audit_ids=tuple(sorted(item.path_audit_id for item in paths)),
        prospective_runner_run_id=PROSPECTIVE_RUNNER_RUN_ID,
        prospective_execution_run_id=PROSPECTIVE_EXECUTION_RUN_ID,
    )
    provisional_contract = TwoStageExecutionContract.model_construct(
        contract_id="pending", **contract_values
    )
    contract = TwoStageExecutionContract(
        contract_id=two_stage_execution_contract_id(provisional_contract), **contract_values
    )
    task_by_predecessor = {item.predecessor_task_package_id: item for item in tasks}
    path_by_predecessor = {item.predecessor_path_audit_id: item for item in paths}
    jobs = []
    for old_job in predecessor.manifest.jobs:
        task = task_by_predecessor[old_job.predecessor_task_package_id]
        path = path_by_predecessor[old_job.predecessor_path_audit_id]
        if path.task_package_id != task.task_package_id:
            raise ValueError("v26.112 Job Task and Path parents differ")
        values = old_job.model_dump(
            mode="python",
            exclude={"job_id", "contract_id", "task_package_id", "path_audit_id"},
        )
        values.update(
            contract_id=contract.contract_id,
            task_package_id=task.task_package_id,
            path_audit_id=path.path_audit_id,
        )
        provisional = TwoStageJob.model_construct(job_id="pending", **values)
        jobs.append(TwoStageJob(job_id=two_stage_job_id(provisional), **values))
    ordered_jobs = tuple(sorted(jobs, key=lambda item: item.job_id))
    mechanism = Counter(item.mechanism_id for item in ordered_jobs)
    path_counts = Counter(item.path_strategy_id for item in ordered_jobs)
    cells = Counter(f"{item.mechanism_id}|{item.path_strategy_id}" for item in ordered_jobs)
    manifest_values = {
        "contract_id": contract.contract_id,
        "stage_one_profile_id": predecessor.stage_one.profile_id,
        "stage_two_profile_id": predecessor.stage_two.profile_id,
        "resource_contract_id": predecessor.resource.contract_id,
        "prospective_runner_run_id": PROSPECTIVE_RUNNER_RUN_ID,
        "prospective_execution_run_id": PROSPECTIVE_EXECUTION_RUN_ID,
        "jobs": ordered_jobs,
        "mechanism_job_counts": dict(sorted(mechanism.items())),
        "path_job_counts": dict(sorted(path_counts.items())),
        "cell_job_counts": dict(sorted(cells.items())),
    }
    provisional_manifest = TwoStageManifest.model_construct(
        manifest_id="pending", **manifest_values
    )
    manifest = TwoStageManifest(
        manifest_id=two_stage_manifest_id(provisional_manifest), **manifest_values
    )
    return contract, ordered_jobs, manifest


def _build_cross(
    predecessor: TwoStageStaticInputs,
    grammar: StageOneResponseGrammarArtifact,
    tasks: Sequence[TwoStageTaskPackage],
    paths: Sequence[TwoStagePathAudit],
    bindings: Sequence[PromptPathBinding],
    jobs: Sequence[TwoStageJob],
    contract: TwoStageExecutionContract,
    manifest: TwoStageManifest,
) -> CrossArtifactBindingAudit:
    task_ids = {item.task_package_id for item in tasks}
    path_ids = {item.path_audit_id for item in paths}
    binding_paths = {item.successor_path_audit_id for item in bindings}
    if (
        set(contract.task_package_ids) != task_ids
        or set(contract.path_audit_ids) != path_ids
        or manifest.contract_id != contract.contract_id
        or binding_paths != path_ids
        or any(item.compact_prompt_contract_id != grammar.grammar_id for item in tasks)
        or any(item.contract_id != contract.contract_id for item in jobs)
        or any(item.task_package_id not in task_ids for item in jobs)
        or any(item.path_audit_id not in path_ids for item in jobs)
    ):
        raise ValueError("v26.112 cross-artifact binding failed")
    old_task_ids = {item.task_package_id for item in predecessor.tasks}
    old_path_ids = {item.path_audit_id for item in predecessor.paths}
    old_job_ids = {item.job_id for item in predecessor.manifest.jobs}
    old_tasks = {item.predecessor_task_package_id: item for item in predecessor.tasks}
    source_matches = sum(
        all(
            (
                item.source_task_artifact_id == old.source_task_artifact_id,
                item.source_role == old.source_role,
                item.mechanism_id == old.mechanism_id,
                item.operational_record_id == old.operational_record_id,
                item.operational_task_package_id == old.operational_task_package_id,
                item.environment_manifest_id == old.environment_manifest_id,
                item.semantic_source_id == old.semantic_source_id,
            )
        )
        for item in tasks
        for old in (old_tasks[item.predecessor_task_package_id],)
    )
    old_paths = {item.predecessor_path_audit_id: item for item in predecessor.paths}
    path_matches = sum(
        all(
            (
                item.compiler_trajectory_id == old.compiler_trajectory_id,
                item.role == old.role,
                item.mechanism_id == old.mechanism_id,
                item.path_strategy_id == old.path_strategy_id,
                item.compiler_tool_call_count == old.compiler_tool_call_count,
                item.semantic_proposal_request_count == old.semantic_proposal_request_count,
                item.final_answer_request_count == old.final_answer_request_count,
                item.primary_stage_one_request_count == old.primary_stage_one_request_count,
                item.stage_two_commit_count == old.stage_two_commit_count,
            )
        )
        for item in paths
        for old in (old_paths[item.predecessor_path_audit_id],)
    )
    old_jobs = {item.predecessor_job_id: item for item in predecessor.manifest.jobs}
    seed_matches = sum(
        all(
            (
                item.job_seed == old.job_seed,
                item.source_task_artifact_id == old.source_task_artifact_id,
                item.mechanism_id == old.mechanism_id,
                item.path_strategy_id == old.path_strategy_id,
                item.source_role == old.source_role,
            )
        )
        for item in jobs
        for old in (old_jobs[item.predecessor_job_id],)
    )
    path_by_id = {item.path_audit_id: item for item in paths}
    values = {
        "response_grammar_id": grammar.grammar_id,
        "task_response_grammar_binding_count": sum(
            item.compact_prompt_contract_id == grammar.grammar_id for item in tasks
        ),
        "path_prompt_binding_count": len(binding_paths & path_ids),
        "job_contract_parent_binding_count": sum(
            item.contract_id == contract.contract_id for item in jobs
        ),
        "job_task_parent_binding_count": sum(item.task_package_id in task_ids for item in jobs),
        "job_path_parent_binding_count": sum(
            item.path_audit_id in path_by_id
            and path_by_id[item.path_audit_id].task_package_id == item.task_package_id
            for item in jobs
        ),
        "profile_preservation_count": sum(
            item.stage_one_profile_id == predecessor.stage_one.profile_id
            and item.stage_two_profile_id == predecessor.stage_two.profile_id
            for item in (*tasks, *paths, *jobs)
        ),
        "resource_preservation_count": sum(
            item.resource_contract_id == predecessor.resource.contract_id
            for item in (*tasks, *paths, *jobs)
        ),
        "task_identity_overlap_with_v26_108": len(task_ids & old_task_ids),
        "path_identity_overlap_with_v26_108": len(path_ids & old_path_ids),
        "job_identity_overlap_with_v26_108": len({item.job_id for item in jobs} & old_job_ids),
        "seed_projection_match_count": seed_matches,
        "source_projection_match_count": source_matches,
        "path_projection_match_count": path_matches,
    }
    provisional = CrossArtifactBindingAudit.model_construct(audit_id="pending", **values)
    return CrossArtifactBindingAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_exact_grammar_cross_binding:"),
        **values,
    )


def _expect_rejection(name: str, action: Callable[[], Any]) -> MutationResult:
    try:
        action()
    except (ValueError, ExactResponseModelRejection):
        provisional = MutationResult.model_construct(mutation_id="pending", name=name)
        return MutationResult(
            mutation_id=_identity(
                provisional, "mutation_id", "finance_v26_exact_grammar_mutation:"
            ),
            name=name,
        )
    raise AssertionError(f"mutation was accepted: {name}")


def _build_destructive(
    sample_prompt: str, sample_state: PublicActionState
) -> DestructivePreflightAudit:
    valid = prompt_only_reference_payload(sample_prompt)

    def rejected(payload: Any, *, state: PublicActionState = sample_state) -> None:
        if not isinstance(payload, Mapping):
            raise ValueError("payload is not a single object")
        parse_exact_semantic_proposal_payload(payload, expected_state=state)

    def mutate(**updates: Any) -> dict[str, Any]:
        payload = dict(valid)
        payload.update(updates)
        return payload

    tests: tuple[tuple[str, Callable[[], Any]], ...] = (
        ("missing_state_id", lambda: rejected({k: v for k, v in valid.items() if k != "state_id"})),
        ("stale_state_id", lambda: rejected(mutate(state_id="public_action_state:stale"))),
        ("missing_protocol", lambda: rejected({k: v for k, v in valid.items() if k != "protocol"})),
        (
            "wrong_protocol",
            lambda: rejected(mutate(protocol="prospective_two_stage_stage_one_response.v1")),
        ),
        ("alias_field", lambda: rejected({**valid, "stateId": valid["state_id"]})),
        ("proposal_wrapper", lambda: rejected({"proposal": valid})),
        (
            "missing_conditional_empty_field",
            lambda: rejected({k: v for k, v in valid.items() if k != "evidence_ids"}),
        ),
        ("null_for_array", lambda: rejected(mutate(evidence_ids=None))),
        ("array_for_object", lambda: rejected(mutate(direct_arguments=[]))),
        ("extra_field", lambda: rejected({**valid, "rationale": "public"})),
        (
            "decision_kind_field_mismatch",
            lambda: rejected(mutate(decision_kind="emit_final_answer")),
        ),
        ("multiple_proposals", lambda: rejected([valid, valid])),
        (
            "host_missing_field_insertion",
            lambda: rejected({k: v for k, v in valid.items() if k != "tool_id"}),
        ),
        (
            "host_alias_normalization",
            lambda: rejected(
                {**{k: v for k, v in valid.items() if k != "tool_id"}, "tool": valid["tool_id"]}
            ),
        ),
        ("wrong_stage", lambda: rejected(mutate(stage="final_answer"))),
        (
            "rescue_uses_different_grammar",
            lambda: parse_prompt_only_reference_payload(
                sample_prompt.replace(
                    compile_stage_one_response_grammar().grammar_id,
                    "prospective_stage_one_response_grammar:changed",
                )
            ),
        ),
    )
    mutations = tuple(_expect_rejection(name, action) for name, action in tests)
    values = {"mutations": tuple(sorted(mutations, key=lambda item: item.name))}
    provisional = DestructivePreflightAudit.model_construct(audit_id="pending", **values)
    return DestructivePreflightAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_exact_grammar_destructive:"),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build(
    *, package_root: Path, implementation_root: Path, output_dir: Path
) -> ExactGrammarRematerializationReport:
    replay = _build_source_replay(package_root, implementation_root)
    predecessor = load_two_stage_static_inputs(package_root, package_root)
    grammar = compile_stage_one_response_grammar()
    tasks = _build_tasks(predecessor, grammar)
    paths, prompt_bindings, constructibility = _build_paths_and_prompts(predecessor, tasks, grammar)
    contract, jobs, manifest = _build_contract_jobs_manifest(replay, predecessor, tasks, paths)
    cross = _build_cross(
        predecessor,
        grammar,
        tasks,
        paths,
        prompt_bindings,
        jobs,
        contract,
        manifest,
    )
    sample_old_path = predecessor.paths[0]
    sample_prompts, _, sample_states = _semantic_prompts_and_final(predecessor, sample_old_path)
    destructive = _build_destructive(sample_prompts[0], sample_states[0])
    outputs: tuple[tuple[str, Any], ...] = (
        ("source_replay_audit.json", replay),
        ("stage_one_response_grammar.json", grammar),
        ("response_constructibility_audit.json", constructibility),
        ("two_stage_task_packages.json", [item.model_dump(mode="json") for item in tasks]),
        ("two_stage_path_audits.json", [item.model_dump(mode="json") for item in paths]),
        ("two_stage_execution_contract.json", contract),
        ("two_stage_job_manifest.json", manifest),
        ("cross_artifact_binding_audit.json", cross),
        ("destructive_preflight_audit.json", destructive),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    paths_written = []
    for name, value in outputs:
        path = output_dir / name
        _write_json(path, value)
        paths_written.append(path)
    details = tuple(
        sorted(
            (_detail(path, output_dir) for path in paths_written),
            key=lambda item: item.relative_path,
        )
    )
    values = {
        "source_replay_audit_id": replay.audit_id,
        "response_grammar_id": grammar.grammar_id,
        "response_constructibility_audit_id": constructibility.audit_id,
        "execution_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "cross_artifact_binding_audit_id": cross.audit_id,
        "destructive_preflight_audit_id": destructive.audit_id,
        "detail_files": details,
    }
    provisional = ExactGrammarRematerializationReport.model_construct(report_id="pending", **values)
    report = ExactGrammarRematerializationReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_exact_grammar_rematerialization_report:",
        ),
        **values,
    )
    _write_json(output_dir / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--implementation-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json())


if __name__ == "__main__":
    main()
