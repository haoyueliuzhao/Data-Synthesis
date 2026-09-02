# ruff: noqa: E501
from __future__ import annotations

import argparse
import copy
import hashlib
import inspect
import json
import os
import subprocess
from collections import Counter, defaultdict
from collections.abc import Sequence
from decimal import Decimal
from math import comb
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel

from trusted_synthesis.experiments.vtdo_experiment import (
    json_explicit_authoritative_execution_kernel as kernel,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_execution as v200,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_calibration_preflight as v203,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_calibration_preflight_models as v203_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_paired_online_calibration as v204,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_paired_online_calibration_models as v204_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_paired_postrun_independent_audit_models as models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    prospective_semantic_action_response_grammar as action_grammar,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

RUN_ID: Final = (
    "finance_v26_205_fresh_first_response_action_interface_disambiguation_"
    "paired_online_calibration_postrun_independent_audit_v1_20260902"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
V203_DIR: Final = v203.OUTPUT_DIR
V204_DIR: Final = v204.OUTPUT_DIR
EXTERNAL_AUDIT_SHA256: Final = "37c146cd27119983506520f1d5bbdabe3ca2003165d52510b184803eaa9a2d3d"
EXTERNAL_AUDIT_BYTES: Final = 13_644
V204_ONLINE_AUTHORIZATION_ID: Final = (
    "finance_v26_204_external_online_authorization:"
    "ed97a4df5f599157006bb0d02bc3c6d50535e4f86e6ee7d2ff955abe81eb993b"
)
V204_RUN_START_ID: Final = (
    "finance_v26_204_online_run_start_receipt:"
    "0ce21fe746b83fae8c62b084209ad2ab809f198224c3d3fc72d9153731ae6e06"
)
V204_SUMMARY_ID: Final = (
    "finance_v26_204_online_execution_summary:"
    "bee66b004f5078509406559122bfe808e0ef933217b8f284118f2119bdb8b73b"
)
V204_PAIRED_EVALUATION_ID: Final = (
    "fresh_first_response_exact_paired_calibration_evaluation:"
    "8e31638c2929c0d9c09853cac76c786f40f72704c9079646fd05246639942341"
)
V204_GATE_EVALUATION_ID: Final = (
    "finance_v26_204_online_gate_evaluation:"
    "d629e49ceeb6c24a4391dede3b98927b1ae2eb952b7f3c7e3b0d85aba92984e1"
)
V204_ARTIFACT_MANIFEST_ID: Final = (
    "finance_v26_204_execution_artifact_manifest:"
    "335f29b37782da4c7ac0803ce2cc3f6de4a6a4cf744c7a2433f6383a3a1290ec"
)
V204_ARTIFACT_ROOT: Final = (
    "finance_v26_204_execution_artifact_root:"
    "10d7d5d17b518d2758c3e746a39a29f0a381cb5d3a267fb79e67e860093e8a3f"
)
V204_SOURCE_COMMIT: Final = "01924d88f9e57502cd981c9d3be16b298b2ad45c"
V204_SOURCE_TREE: Final = "70db179b44eb8834c5fc09d77a7ca89b56ce3d44"


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write_bytes_no_replace(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _write_no_replace(path: Path, value: Any) -> None:
    _write_bytes_no_replace(path, models.canonical_bytes(value))


def _git_identity(repository_root: Path) -> tuple[str, str]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, tree


def _tree_for_commit(repository_root: Path, commit: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", f"{commit}^{{tree}}"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _independent_identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def _independent_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> BaseModel:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    identifier = _independent_identity(provisional, field, prefix)
    return model_type(**{field: identifier}, **values)


def _request_body(
    config: AgentModelConfig,
    messages: tuple[v203_models.RequestMessage, ...],
) -> dict[str, Any]:
    body = kernel.make_stage_one_request_body(config, messages[-1].content)
    body["messages"] = [{"role": message.role, "content": message.content} for message in messages]
    return body


def _usage(telemetry: ModelCallTelemetry) -> dict[str, Any] | None:
    values = {
        "prompt_tokens": telemetry.prompt_tokens,
        "prompt_cache_hit_tokens": telemetry.prompt_cache_hit_tokens,
        "prompt_cache_miss_tokens": telemetry.prompt_cache_miss_tokens,
        "completion_tokens": telemetry.completion_tokens,
        "reasoning_tokens": telemetry.reasoning_tokens,
        "total_tokens": telemetry.total_tokens,
        "estimated_cost": telemetry.estimated_cost,
        "cost_estimation_method": telemetry.cost_estimation_method,
    }
    return None if all(value is None for value in values.values()) else values


def _schema_fields(
    request: v203_models.FirstRequestDescriptor,
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    if request.arm == "C":
        prompt = json.loads(request.messages[0].content)["prompt_core"]["public_prompt"]
        semantic = prompt["task"]["semantic_task"]
        answer_fields = semantic["answer_fields"]
        operator_fields = semantic["operator_output_fields"]
    else:
        metadata = json.loads(request.messages[1].content)["verifier_internal_task_metadata"]
        answer_fields = metadata["answer_fields"]
        operator_fields = metadata["operator_output_fields"]
    answer = tuple(sorted(str(item) for item in answer_fields))
    operations = tuple(
        sorted({tuple(sorted(str(item) for item in values)) for values in operator_fields.values()})
    )
    return answer, operations


def _mcnemar_p(repair_only: int, control_only: int) -> str:
    discordant = repair_only + control_only
    if discordant == 0:
        return "1"
    lower = min(repair_only, control_only)
    numerator = 2 * sum(comb(discordant, index) for index in range(lower + 1))
    denominator = 2**discordant
    return format(min(Decimal(1), Decimal(numerator) / Decimal(denominator)), "f")


def _revalidate_v203(v203_root: Path) -> v203_models.ArtifactManifest:
    files = tuple(sorted(path for path in v203_root.iterdir() if path.is_file()))
    if len(files) != 15 or sum(path.stat().st_size for path in files) != 582_364:
        raise ValueError("v26.203 formal directory geometry differs")
    manifest = v203_models.ArtifactManifest.model_validate(
        _load(v203_root / "artifact_manifest.json")
    )
    actual = {
        path.relative_to(v203_root).as_posix(): path
        for path in files
        if path.name != "artifact_manifest.json"
    }
    members = {member.relative_path: member for member in manifest.members}
    if len(members) != 14 or set(actual) != set(members):
        raise ValueError("v26.203 Artifact Manifest path set differs")
    for relative_path, member in members.items():
        path = actual[relative_path]
        if _sha256(path) != member.sha256 or path.stat().st_size != member.byte_count:
            raise ValueError(f"v26.203 Artifact Manifest member differs:{relative_path}")
    return manifest


def _recompute_v204_root(
    members: Sequence[v204_models.ArtifactMember],
) -> str:
    return canonical_hash(
        tuple(member.model_dump(mode="json") for member in members),
        prefix="finance_v26_204_execution_artifact_root:",
    )


def _assert_exact_row_set(
    rows: Sequence[models.IndependentObservationRow], expected_job_ids: set[str]
) -> None:
    actual = [row.job_id for row in rows]
    if len(actual) != 24 or len(set(actual)) != 24 or set(actual) != expected_job_ids:
        raise ValueError("exact Job denominator differs")


def _negative_result(
    *,
    control_name: str,
    expected: str,
    operation: Any,
) -> models.NegativeControlResult:
    try:
        operation()
    except Exception as exc:
        observed = str(exc)
        if expected not in observed:
            raise ValueError(
                f"negative Control {control_name} rejected for an unexpected reason:{observed}"
            ) from exc
    else:
        raise ValueError(f"negative Control {control_name} was accepted")
    return cast(
        models.NegativeControlResult,
        models.make_identity(
            models.NegativeControlResult,
            {
                "control_name": control_name,
                "expected_rejection_reason": expected,
                "observed_rejection_reason": observed,
            },
            field="result_id",
            prefix="finance_v26_205_negative_control_result:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_audit_path: Path,
    source_identity: tuple[str, str] | None = None,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    package_root = repository_root / "trusted_data_synthesis"
    v203_root = package_root / V203_DIR
    v204_root = package_root / V204_DIR
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"v26.205 output already exists: {output_dir}")

    external_audit_bytes = external_audit_path.read_bytes()
    if (
        len(external_audit_bytes) != EXTERNAL_AUDIT_BYTES
        or _sha256_bytes(external_audit_bytes) != EXTERNAL_AUDIT_SHA256
    ):
        raise ValueError("v26.205 external postrun Audit bytes differ")
    authorization = cast(
        models.ExternalPostrunAuditAuthorization,
        models.make_identity(
            models.ExternalPostrunAuditAuthorization,
            {
                "audit_sha256": EXTERNAL_AUDIT_SHA256,
            },
            field="authorization_id",
            prefix="finance_v26_205_external_postrun_audit_authorization:",
        ),
    )

    _revalidate_v203(v203_root)
    manifest = v203_models.CalibrationManifest.model_validate(
        _load(v203_root / "calibration_manifest.json")
    )
    population = v203_models.StratifiedCalibrationPopulation.model_validate(
        _load(v203_root / "stratified_calibration_population.json")
    )
    action_contract = v203_models.ExactActionInterfaceContract.model_validate(
        _load(v203_root / "exact_action_interface_contract.json")
    )
    gate_contract = v203_models.OnlineGateContract.model_validate(
        _load(v203_root / "online_gate_contract.json")
    )

    v204_files = tuple(sorted(path for path in v204_root.rglob("*") if path.is_file()))
    if len(v204_files) != 108 or sum(path.stat().st_size for path in v204_files) != 276_582:
        raise ValueError("v26.204 execution directory geometry differs")
    artifact_manifest = v204_models.ExecutionArtifactManifest.model_validate(
        _load(v204_root / "execution_artifact_manifest.json")
    )
    actual_members = {
        path.relative_to(v204_root).as_posix(): path
        for path in v204_files
        if path.name != "execution_artifact_manifest.json"
    }
    saved_members = {member.relative_path: member for member in artifact_manifest.members}
    if (
        artifact_manifest.manifest_id != V204_ARTIFACT_MANIFEST_ID
        or artifact_manifest.artifact_root != V204_ARTIFACT_ROOT
        or artifact_manifest.file_count != 107
        or artifact_manifest.total_byte_count != 261_434
        or len(saved_members) != 107
        or set(actual_members) != set(saved_members)
    ):
        raise ValueError("v26.204 execution Artifact Manifest authority differs")
    path_matches = sha_matches = byte_matches = 0
    for relative_path, member in saved_members.items():
        path = actual_members[relative_path]
        path_matches += path.is_file()
        sha_matches += _sha256(path) == member.sha256
        byte_matches += path.stat().st_size == member.byte_count
    if (path_matches, sha_matches, byte_matches) != (107, 107, 107):
        raise ValueError("v26.204 execution Artifact member bytes differ")
    recomputed_v204_root = _recompute_v204_root(artifact_manifest.members)
    if recomputed_v204_root != V204_ARTIFACT_ROOT:
        raise ValueError("v26.204 independently reconstructed Artifact Root differs")

    online_authorization = v204_models.ExternalOnlineAuthorization.model_validate(
        _load(v204_root / "external_online_authorization.json")
    )
    run_start = v204_models.RunStartReceipt.model_validate(
        _load(v204_root / "run_start_receipt.json")
    )
    summary = v204_models.OnlineExecutionSummary.model_validate(
        _load(v204_root / "execution_summary.json")
    )
    saved_paired = v203_models.ExactPairedCalibrationEvaluation.model_validate(
        _load(v204_root / "exact_paired_calibration_evaluation.json")
    )
    saved_gate = v204_models.OnlineGateEvaluation.model_validate(
        _load(v204_root / "online_gate_evaluation.json")
    )
    preparation = v204_models.OnlineExecutionPreparation.model_validate(
        _load(v204_root / "online_execution_preparation.json")
    )
    admission = v204_models.OnlineAuthorizationAdmission.model_validate(
        _load(v204_root / "online_authorization_admission.json")
    )
    if (
        online_authorization.authorization_id != V204_ONLINE_AUTHORIZATION_ID
        or run_start.receipt_id != V204_RUN_START_ID
        or summary.summary_id != V204_SUMMARY_ID
        or saved_paired.evaluation_id != V204_PAIRED_EVALUATION_ID
        or saved_gate.gate_evaluation_id != V204_GATE_EVALUATION_ID
        or run_start.execution_source_commit != V204_SOURCE_COMMIT
        or run_start.execution_source_tree != V204_SOURCE_TREE
        or summary.execution_status != "completed"
        or not admission.authorization_consumed
        or admission.execution_ordinal != 1
        or not run_start.authorization_consumed
        or run_start.manifest_execution_ordinal != 1
    ):
        raise ValueError("v26.204 execution authority differs")
    if _tree_for_commit(repository_root, V204_SOURCE_COMMIT) != V204_SOURCE_TREE:
        raise ValueError("v26.204 source commit/tree differs")

    freeze = cast(
        models.V204ExecutionFreeze,
        models.make_identity(
            models.V204ExecutionFreeze,
            {
                "authorization_id": authorization.authorization_id,
                "v204_online_authorization_id": online_authorization.authorization_id,
                "run_start_receipt_id": run_start.receipt_id,
                "execution_summary_id": summary.summary_id,
                "saved_paired_evaluation_id": saved_paired.evaluation_id,
                "saved_gate_evaluation_id": saved_gate.gate_evaluation_id,
                "execution_artifact_manifest_id": artifact_manifest.manifest_id,
                "execution_artifact_root": artifact_manifest.artifact_root,
                "v203_manifest_id": manifest.manifest_id,
                "v203_population_id": population.population_id,
                "v203_action_contract_id": action_contract.contract_id,
                "v203_gate_contract_id": gate_contract.contract_id,
                "execution_source_commit": run_start.execution_source_commit,
                "execution_source_tree": run_start.execution_source_tree,
            },
            field="freeze_id",
            prefix="finance_v26_205_v204_execution_freeze:",
        ),
    )
    byte_audit = cast(
        models.ArtifactByteReconstructionAudit,
        models.make_identity(
            models.ArtifactByteReconstructionAudit,
            {
                "freeze_id": freeze.freeze_id,
                "independently_recomputed_artifact_root": recomputed_v204_root,
                "saved_artifact_root": artifact_manifest.artifact_root,
            },
            field="audit_id",
            prefix="finance_v26_205_artifact_byte_reconstruction_audit:",
        ),
    )

    parser_source_sha = _sha256_bytes(
        inspect.getsource(action_grammar.parse_exact_canonical_action_payload).encode("utf-8")
    )
    grammar_source_sha = _sha256_bytes(
        inspect.getsource(action_grammar.compile_semantic_action_response_grammar).encode("utf-8")
    )
    compiled_grammar = action_grammar.compile_semantic_action_response_grammar()
    parser_source_match = parser_source_sha == action_contract.frozen_parser_source_sha256
    grammar_source_match = grammar_source_sha == action_contract.frozen_grammar_source_sha256
    if (
        not parser_source_match
        or not grammar_source_match
        or compiled_grammar.grammar_id != action_contract.frozen_action_grammar_id
        or tuple(action_grammar.ExactCanonicalActionPayload.model_fields)
        != action_contract.field_order
    ):
        raise ValueError("v26.203 frozen Action parser or Grammar differs")

    profile_payload = _load(package_root / v200.MODEL_PROFILE_PATH)
    config = v200.require_stage_one_model_config(
        AgentModelConfig.model_validate(profile_payload.get("model", profile_payload))
    )
    jobs = {job.job_id: job for job in manifest.jobs}
    requests = {request.job_id: request for request in manifest.requests}
    cells = {cell.source_cell_id: cell for cell in population.cells}
    order = preparation.execution_order
    if tuple(entry.ordinal for entry in order) != tuple(range(24)):
        raise ValueError("v26.204 execution order differs")

    reconstructed_request_hash_matches = 0
    raw_request_hash_matches = 0
    telemetry_request_hash_matches = 0
    job_request_parent_matches = 0
    sequential_matches = 0
    http_success = model_match = thinking_present = complete_usage = 0
    private_reasoning = typed_outer = 0
    stage_one_calls = stage_two_calls = retries = recoveries = corrections = finals = 0
    semantic_parent_mismatches = 0
    rows: list[models.IndependentObservationRow] = []
    raw_payloads: dict[int, dict[str, Any]] = {}

    for pair_index in range(0, 24, 2):
        left = order[pair_index]
        right = order[pair_index + 1]
        if left.source_cell_id != right.source_cell_id or left.pair_id != right.pair_id:
            raise ValueError("v26.204 adjacent pair relation differs")
        left_job = jobs[left.job_id]
        right_job = jobs[right.job_id]
        semantic_parent_mismatches += sum(
            (
                left_job.public_task_semantic_sha256 != right_job.public_task_semantic_sha256,
                left_job.current_state_semantic_sha256 != right_job.current_state_semantic_sha256,
                left_job.candidate_set_order_sha256 != right_job.candidate_set_order_sha256,
                left_job.schedule_ids != right_job.schedule_ids,
                left_job.model_request_config_sha256 != right_job.model_request_config_sha256,
            )
        )
    if semantic_parent_mismatches:
        raise ValueError("v26.204 paired semantic parent differs")

    for entry in order:
        ordinal = entry.ordinal
        job = jobs[entry.job_id]
        request = requests[entry.job_id]
        cell = cells[entry.source_cell_id]
        raw_path = v204_root / "raw" / f"job_{ordinal:03d}.json"
        result_path = v204_root / "results" / f"job_{ordinal:03d}.json"
        observation_path = v204_root / "observations" / f"job_{ordinal:03d}.json"
        checkpoint_path = v204_root / "checkpoints" / f"job_{ordinal:03d}.json"
        raw_dict = _load(raw_path)
        raw_payloads[ordinal] = raw_dict
        raw = v204_models.PublicProviderCallRaw.model_validate(raw_dict)
        result = v204_models.CalibrationJobResult.model_validate(_load(result_path))
        saved_observation = v204_models.ObservationRecord.model_validate(_load(observation_path))
        checkpoint = v204_models.ExecutionCheckpoint.model_validate(_load(checkpoint_path))

        request_hash = models.canonical_sha256(_request_body(config, request.messages))
        reconstructed_request_hash_matches += request_hash == request.canonical_request_body_sha256
        raw_request_hash_matches += raw.canonical_request_body_sha256 == request_hash
        telemetry_request_hash_matches += raw.telemetry.request_hash == request_hash
        parent_match = (
            raw.ordinal
            == result.ordinal
            == saved_observation.ordinal
            == checkpoint.ordinal
            == ordinal
            and raw.job_id
            == result.job_id
            == saved_observation.job_id
            == checkpoint.job_id
            == job.job_id
            and raw.request_id == result.request_id == request.request_id
            and raw.source_cell_id == result.source_cell_id == entry.source_cell_id
            and raw.arm == result.arm == request.arm == job.arm == entry.arm
            and result.raw_id == saved_observation.raw_id == checkpoint.raw_id == raw.raw_id
            and saved_observation.result_id == checkpoint.result_id == result.result_id
            and checkpoint.observation_record_id == saved_observation.record_id
        )
        job_request_parent_matches += parent_match
        sequential_matches += raw.ordinal == entry.ordinal
        if not parent_match:
            raise ValueError(f"v26.204 evidence parent chain differs:{ordinal}")

        if raw.raw_id != _independent_identity(
            raw, "raw_id", "fresh_first_response_calibration_public_provider_raw:"
        ):
            raise ValueError(f"v26.204 Raw identity differs:{ordinal}")
        if result.result_id != _independent_identity(
            result, "result_id", "fresh_first_response_calibration_job_result:"
        ):
            raise ValueError(f"v26.204 Result identity differs:{ordinal}")
        if saved_observation.record_id != _independent_identity(
            saved_observation,
            "record_id",
            "fresh_first_response_calibration_observation_record:",
        ):
            raise ValueError(f"v26.204 Observation Record identity differs:{ordinal}")
        if checkpoint.checkpoint_id != _independent_identity(
            checkpoint, "checkpoint_id", "finance_v26_204_online_execution_checkpoint:"
        ):
            raise ValueError(f"v26.204 Checkpoint identity differs:{ordinal}")

        stage_one_calls += raw.provider_call_count
        stage_two_calls += raw.stage_two_call_count
        retries += raw.retry_count
        recoveries += raw.recovery_call_count
        corrections += raw.correction_call_count
        finals += raw.final_call_count
        http_success += raw.telemetry.http_success is True
        model_match += (
            raw.telemetry.model_requested
            == raw.telemetry.model_selected
            == raw.telemetry.response_model
            == "deepseek-v4-flash"
        )
        thinking_present += raw.telemetry.reasoning_content_present is True
        complete_usage += all(
            value is not None
            for value in (
                raw.telemetry.prompt_tokens,
                raw.telemetry.completion_tokens,
                raw.telemetry.reasoning_tokens,
                raw.telemetry.total_tokens,
            )
        )
        private_reasoning += raw.private_reasoning_content_persisted
        typed_outer += raw.typed_outer_terminal is not None
        payload = raw.public_response_object
        if payload is None:
            raise ValueError(f"v26.204 unexpected outer terminal:{ordinal}")

        exact_abi = False
        reference_valid: bool | None = None
        state_valid: bool | None = None
        parser_rejection: str | None = None
        try:
            parsed = action_grammar.parse_exact_canonical_action_payload(payload)
        except action_grammar.SemanticActionResponseRejection as exc:
            parser_rejection = f"{type(exc).__name__}:{exc}"
        else:
            exact_abi = True
            reference_valid = parsed.action_id in set(cell.candidate_action_ids)
            state_valid = parsed.state_id == cell.current_state_id
        answer_fields, operation_fields = _schema_fields(request)
        shape = tuple(sorted(payload))
        usage = _usage(raw.telemetry)
        response_hash = models.canonical_sha256(payload)
        reconstructed_response = cast(
            v203_models.FirstResponseDescriptor,
            _independent_model(
                v203_models.FirstResponseDescriptor,
                {
                    "job_id": job.job_id,
                    "request_id": request.request_id,
                    "source_cell_id": job.source_cell_id,
                    "arm": job.arm,
                    "evidence_kind": "empirical_calibration",
                    "response_sha256": response_hash,
                    "typed_outer_terminal": None,
                    "exact_json_object": payload,
                    "usage": usage,
                    "thinking_present": raw.telemetry.reasoning_content_present,
                    "provider_call_count": 1,
                },
                field="response_id",
                prefix="fresh_first_response_descriptor:",
            ),
        )
        response_matches = reconstructed_response == result.response
        if not response_matches:
            raise ValueError(f"v26.204 independently reconstructed Response differs:{ordinal}")
        reconstructed_observation = cast(
            v203_models.FirstActionInterfaceObservation,
            _independent_model(
                v203_models.FirstActionInterfaceObservation,
                {
                    "job_id": job.job_id,
                    "request_id": request.request_id,
                    "response_id": reconstructed_response.response_id,
                    "source_cell_id": job.source_cell_id,
                    "arm": job.arm,
                    "evidence_kind": "empirical_calibration",
                    "typed_outer_terminal": None,
                    "exact_json_object": payload,
                    "exact_four_field_abi_valid": exact_abi,
                    "action_reference_valid": reference_valid,
                    "state_binding_valid": state_valid,
                    "runtime_step_committed": None,
                    "answer_schema_exact_match": shape == answer_fields,
                    "operation_output_schema_exact_match": shape in operation_fields,
                    "usage": usage,
                    "thinking_present": raw.telemetry.reasoning_content_present,
                },
                field="observation_id",
                prefix="fresh_first_action_interface_observation:",
            ),
        )
        observation_matches = reconstructed_observation == saved_observation.observation
        if not observation_matches:
            raise ValueError(f"v26.204 independently reconstructed Observation differs:{ordinal}")
        rows.append(
            cast(
                models.IndependentObservationRow,
                models.make_identity(
                    models.IndependentObservationRow,
                    {
                        "ordinal": ordinal,
                        "job_id": job.job_id,
                        "request_id": request.request_id,
                        "source_cell_id": cell.source_cell_id,
                        "stratum_id": cell.stratum_id,
                        "arm": job.arm,
                        "raw_id": raw.raw_id,
                        "result_id": result.result_id,
                        "response_id": reconstructed_response.response_id,
                        "saved_observation_id": saved_observation.observation.observation_id,
                        "observation_record_id": saved_observation.record_id,
                        "checkpoint_id": checkpoint.checkpoint_id,
                        "public_response_sha256": response_hash,
                        "public_response_shape": shape,
                        "exact_four_field_abi_valid": exact_abi,
                        "action_reference_valid": reference_valid,
                        "state_binding_valid": state_valid,
                        "answer_schema_exact_match": shape == answer_fields,
                        "operation_output_schema_exact_match": shape in operation_fields,
                        "parser_rejection_reason": parser_rejection,
                    },
                    field="row_id",
                    prefix="finance_v26_205_independent_first_action_interface_observation_row:",
                ),
            )
        )

    if any(
        count != 24
        for count in (
            reconstructed_request_hash_matches,
            raw_request_hash_matches,
            telemetry_request_hash_matches,
            job_request_parent_matches,
            sequential_matches,
            stage_one_calls,
            http_success,
            model_match,
            thinking_present,
            complete_usage,
        )
    ) or any(
        count != 0
        for count in (
            stage_two_calls,
            retries,
            recoveries,
            corrections,
            finals,
            private_reasoning,
            typed_outer,
        )
    ):
        raise ValueError("v26.204 request or one-call execution geometry differs")

    request_audit = cast(
        models.RequestIdentityAudit,
        models.make_identity(
            models.RequestIdentityAudit,
            {
                "freeze_id": freeze.freeze_id,
            },
            field="audit_id",
            prefix="finance_v26_205_request_identity_and_execution_geometry_audit:",
        ),
    )
    repair_rows = [row for row in rows if row.arm == "R"]
    repair_four_fields = sum(
        row.public_response_shape == tuple(sorted(action_contract.field_order))
        for row in repair_rows
    )
    invalid_repair_rows = [row for row in repair_rows if not row.exact_four_field_abi_valid]
    invalid_decision_kind = sum(
        raw_payloads[row.ordinal]["public_response_object"].get("decision_kind")
        == "revise_selector"
        for row in invalid_repair_rows
    )
    if (
        len(rows) != 24
        or repair_four_fields != 12
        or len(invalid_repair_rows) != 1
        or invalid_decision_kind != 1
    ):
        raise ValueError("v26.204 independent Repair response partition differs")
    catalog = cast(
        models.IndependentObservationCatalog,
        models.make_identity(
            models.IndependentObservationCatalog,
            {
                "freeze_id": freeze.freeze_id,
                "request_identity_audit_id": request_audit.audit_id,
                "rows": tuple(rows),
                "frozen_parser_source_match": parser_source_match,
                "frozen_grammar_source_match": grammar_source_match,
            },
            field="catalog_id",
            prefix="finance_v26_205_independent_observation_catalog:",
        ),
    )

    by_cell: dict[str, dict[str, models.IndependentObservationRow]] = defaultdict(dict)
    for row in rows:
        by_cell[row.source_cell_id][row.arm] = row
    if len(by_cell) != 12 or any(set(pair) != {"C", "R"} for pair in by_cell.values()):
        raise ValueError("v26.204 independently reconstructed pair set differs")
    control_abi = sum(pair["C"].exact_four_field_abi_valid for pair in by_cell.values())
    repair_abi = sum(pair["R"].exact_four_field_abi_valid for pair in by_cell.values())
    control_reference_state = sum(
        pair["C"].exact_four_field_abi_valid
        and pair["C"].action_reference_valid is True
        and pair["C"].state_binding_valid is True
        for pair in by_cell.values()
    )
    repair_reference_state = sum(
        pair["R"].exact_four_field_abi_valid
        and pair["R"].action_reference_valid is True
        and pair["R"].state_binding_valid is True
        for pair in by_cell.values()
    )
    repair_only = sum(
        pair["R"].exact_four_field_abi_valid and not pair["C"].exact_four_field_abi_valid
        for pair in by_cell.values()
    )
    control_only = sum(
        pair["C"].exact_four_field_abi_valid and not pair["R"].exact_four_field_abi_valid
        for pair in by_cell.values()
    )
    control_answer = sum(row.answer_schema_exact_match for row in rows if row.arm == "C")
    repair_answer = sum(row.answer_schema_exact_match for row in rows if row.arm == "R")
    control_operation = sum(
        row.operation_output_schema_exact_match for row in rows if row.arm == "C"
    )
    repair_operation = sum(
        row.operation_output_schema_exact_match for row in rows if row.arm == "R"
    )
    stratum_counts: Counter[str] = Counter(
        row.stratum_id
        for row in repair_rows
        if row.exact_four_field_abi_valid
        and row.action_reference_valid is True
        and row.state_binding_valid is True
    )
    saved_paired_match = (
        set(saved_paired.exact_job_ids) == {row.job_id for row in rows}
        and set(saved_paired.observation_ids) == {row.saved_observation_id for row in rows}
        and saved_paired.repair_abi_success_count == repair_abi
        and saved_paired.repair_reference_state_valid_count == repair_reference_state
        and saved_paired.paired_repair_only_abi_success_count == repair_only
        and saved_paired.paired_control_only_abi_success_count == control_only
        and saved_paired.delta_abi_numerator == repair_only - control_only
        and saved_paired.capability_estimate is None
    )
    observed_counts = (
        control_abi,
        repair_abi,
        control_reference_state,
        repair_reference_state,
        control_answer,
        repair_answer,
        control_operation,
        repair_operation,
        repair_only,
        control_only,
    )
    if observed_counts != (0, 11, 0, 11, 10, 0, 10, 0, 11, 0) or not saved_paired_match:
        raise ValueError(
            f"v26.204 independently reconstructed paired result differs:{observed_counts}"
        )
    independent_evaluation = cast(
        models.IndependentPairedEvaluation,
        models.make_identity(
            models.IndependentPairedEvaluation,
            {
                "freeze_id": freeze.freeze_id,
                "catalog_id": catalog.catalog_id,
                "exact_job_ids": tuple(sorted(row.job_id for row in rows)),
                "row_ids": tuple(sorted(row.row_id for row in rows)),
                "stratum_repair_reference_state_valid_counts": dict(sorted(stratum_counts.items())),
            },
            field="evaluation_id",
            prefix="finance_v26_205_independent_paired_calibration_evaluation:",
        ),
    )

    g0 = len(rows) == gate_contract.g0_exact_job_raw_result_observation_count
    g1_count = semantic_parent_mismatches
    g2_count = 0 if parser_source_match and grammar_source_match else 1
    g7_count = retries + recoveries + corrections + finals
    forbidden_member_tokens = ("qa", "mapper", "state_assignment", "contribution", "vtdo_row")
    g8_count = sum(
        any(token in relative_path.lower() for token in forbidden_member_tokens)
        for relative_path in actual_members
    )
    gate_passes = (
        g0,
        g1_count <= gate_contract.g1_paired_semantic_parent_mismatch_maximum,
        g2_count <= gate_contract.g2_parser_grammar_candidate_change_maximum,
        repair_abi >= gate_contract.g3_repair_exact_action_abi_minimum,
        repair_reference_state >= gate_contract.g4_repair_reference_state_valid_minimum,
        repair_only >= gate_contract.g5_paired_repair_only_abi_success_minimum,
        control_only <= gate_contract.g6_paired_control_only_abi_success_maximum,
        g7_count <= gate_contract.g7_adaptation_relaxation_retry_count_maximum,
        g8_count <= gate_contract.g8_qa_mapper_state_contribution_vtdo_count_maximum,
    )
    mcnemar_p = _mcnemar_p(repair_only, control_only)
    saved_gate_match = (
        saved_gate.g0_actual_complete_evidence_count == len(rows)
        and saved_gate.g1_actual_paired_semantic_parent_mismatch_count == g1_count
        and saved_gate.g2_actual_parser_grammar_candidate_change_count == g2_count
        and saved_gate.g3_actual_repair_exact_action_abi_count == repair_abi
        and saved_gate.g4_actual_repair_reference_state_valid_count == repair_reference_state
        and saved_gate.g5_actual_paired_repair_only_abi_success_count == repair_only
        and saved_gate.g6_actual_paired_control_only_abi_success_count == control_only
        and saved_gate.g7_actual_adaptation_relaxation_retry_count == g7_count
        and saved_gate.g8_actual_qa_mapper_state_contribution_vtdo_count == g8_count
        and tuple(getattr(saved_gate, f"g{index}_passed") for index in range(9)) == gate_passes
        and saved_gate.all_gates_passed == all(gate_passes)
        and saved_gate.exact_mcnemar_supplementary_two_sided_p == mcnemar_p
        and saved_gate.capability_estimate is None
    )
    if not all(gate_passes) or mcnemar_p != "0.0009765625" or not saved_gate_match:
        raise ValueError("v26.204 independently reconstructed G0-G8 differs")
    gate_reconstruction = cast(
        models.IndependentGateReconstruction,
        models.make_identity(
            models.IndependentGateReconstruction,
            {
                "freeze_id": freeze.freeze_id,
                "evaluation_id": independent_evaluation.evaluation_id,
            },
            field="gate_reconstruction_id",
            prefix="finance_v26_205_independent_online_gate_reconstruction:",
        ),
    )

    expected_job_ids = set(manifest.expected_job_ids)

    def changed_response_bytes() -> None:
        candidate = copy.deepcopy(raw_payloads[0])
        candidate["public_response_object"]["audit_mutation"] = True
        if (
            _sha256_bytes(models.canonical_bytes(candidate))
            != saved_members["raw/job_000.json"].sha256
        ):
            raise ValueError("actual Raw response bytes differ")

    def crossed_arm() -> None:
        left = rows[0]
        right = rows[1]
        if left.arm != right.arm:
            raise ValueError("cross-arm parent binding differs")

    def missing_job() -> None:
        _assert_exact_row_set(rows[:-1], expected_job_ids)

    def duplicate_job() -> None:
        _assert_exact_row_set((*rows[:-1], rows[0]), expected_job_ids)

    def adapted_revise_selector() -> None:
        failing = invalid_repair_rows[0]
        candidate = copy.deepcopy(raw_payloads[failing.ordinal]["public_response_object"])
        candidate["decision_kind"] = action_contract.decision_kind_value
        action_grammar.parse_exact_canonical_action_payload(candidate)
        if models.canonical_sha256(candidate) != failing.public_response_sha256:
            raise ValueError("posthoc response adaptation forbidden")

    controls = (
        _negative_result(
            control_name="changed_raw_response_bytes",
            expected="actual Raw response bytes differ",
            operation=changed_response_bytes,
        ),
        _negative_result(
            control_name="cross_arm_parent_binding",
            expected="cross-arm parent binding differs",
            operation=crossed_arm,
        ),
        _negative_result(
            control_name="missing_job",
            expected="exact Job denominator differs",
            operation=missing_job,
        ),
        _negative_result(
            control_name="duplicate_job",
            expected="exact Job denominator differs",
            operation=duplicate_job,
        ),
        _negative_result(
            control_name="revise_selector_posthoc_adaptation",
            expected="posthoc response adaptation forbidden",
            operation=adapted_revise_selector,
        ),
    )
    negative_audit = cast(
        models.NegativeControlAudit,
        models.make_identity(
            models.NegativeControlAudit,
            {
                "freeze_id": freeze.freeze_id,
                "catalog_id": catalog.catalog_id,
                "controls": controls,
            },
            field="audit_id",
            prefix="finance_v26_205_postrun_negative_control_audit:",
        ),
    )
    decision = cast(
        models.PostrunIndependentAuditDecision,
        models.make_identity(
            models.PostrunIndependentAuditDecision,
            {
                "authorization_id": authorization.authorization_id,
                "freeze_id": freeze.freeze_id,
                "byte_reconstruction_audit_id": byte_audit.audit_id,
                "request_identity_audit_id": request_audit.audit_id,
                "observation_catalog_id": catalog.catalog_id,
                "independent_evaluation_id": independent_evaluation.evaluation_id,
                "gate_reconstruction_id": gate_reconstruction.gate_reconstruction_id,
                "negative_control_audit_id": negative_audit.audit_id,
                "decision": (
                    "v26_204_paired_online_calibration_complete_auditable_and_scientific_result_accepted_as_scoped"
                ),
                "v204_actual_artifact_authority": "independently_reconstructed",
                "v204_scientific_result": "accepted_as_scoped",
                "first_response_interface_gate": (
                    "empirically_passed_on_exact_calibration_surface"
                ),
            },
            field="decision_id",
            prefix="finance_v26_205_postrun_independent_audit_decision:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        models.make_identity(
            models.ProspectiveTransition,
            {"decision_id": decision.decision_id},
            field="transition_id",
            prefix="finance_v26_205_transition:",
        ),
    )
    audit_source_commit, audit_source_tree = source_identity or _git_identity(repository_root)
    if not (
        len(audit_source_commit) == len(audit_source_tree) == 40
        and all(
            character in "0123456789abcdef" for character in audit_source_commit + audit_source_tree
        )
    ):
        raise ValueError("v26.205 Audit source identity is malformed")
    source = {"source_commit": audit_source_commit, "source_tree": audit_source_tree}
    report = {
        "run_id": RUN_ID,
        "authorization_id": authorization.authorization_id,
        "v204_freeze_id": freeze.freeze_id,
        "artifact_byte_reconstruction_audit_id": byte_audit.audit_id,
        "request_identity_audit_id": request_audit.audit_id,
        "independent_observation_catalog_id": catalog.catalog_id,
        "independent_paired_evaluation_id": independent_evaluation.evaluation_id,
        "independent_gate_reconstruction_id": gate_reconstruction.gate_reconstruction_id,
        "negative_control_audit_id": negative_audit.audit_id,
        "decision_id": decision.decision_id,
        "transition_id": transition.transition_id,
        "v204_directory_file_count": 108,
        "v204_directory_total_byte_count": 276_582,
        "v204_manifest_member_count": 107,
        "v204_manifest_member_total_byte_count": 261_434,
        "independently_reconstructed_control_abi": "0/12",
        "independently_reconstructed_repair_abi": "11/12",
        "independently_reconstructed_control_reference_state_valid": "0/12",
        "independently_reconstructed_repair_reference_state_valid": "11/12",
        "paired_repair_only_abi_success_count": 11,
        "paired_control_only_abi_success_count": 0,
        "delta_abi_fraction": "11/12",
        "exact_mcnemar_supplementary_two_sided_p": mcnemar_p,
        "g0_g8_all_passed": True,
        "saved_observation_used_as_outcome_oracle": False,
        "saved_paired_evaluation_used_as_outcome_oracle": False,
        "saved_gate_evaluation_used_as_outcome_oracle": False,
        "provider_calls": 0,
        "credential_lookups": 0,
        "capability_estimate": None,
        "current_decision": decision.decision,
        "next_stage": transition.next_stage,
        "full_repaired_192_job_execution_authorized": False,
        "qa_mapper_state_contribution_vtdo_authorized": False,
        "schema_version": models.SCHEMA_VERSION,
    }

    output_dir.mkdir(parents=True)
    _write_bytes_no_replace(output_dir / "external_audit.txt", external_audit_bytes)
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_authorization.json", authorization),
        ("v26_204_execution_freeze.json", freeze),
        ("artifact_byte_reconstruction_audit.json", byte_audit),
        ("request_identity_and_execution_geometry_audit.json", request_audit),
        ("independent_observation_catalog.json", catalog),
        ("independent_paired_calibration_evaluation.json", independent_evaluation),
        ("independent_online_gate_reconstruction.json", gate_reconstruction),
        ("negative_control_audit.json", negative_audit),
        ("decision.json", decision),
        ("prospective_transition.json", transition),
        ("source_identity.json", source),
        ("report.json", report),
    )
    for relative_path, value in outputs:
        _write_no_replace(output_dir / relative_path, value)
    members = tuple(
        models.ArtifactMember(
            relative_path=path.relative_to(output_dir).as_posix(),
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
        for path in sorted(item for item in output_dir.rglob("*") if item.is_file())
        if path.name != "artifact_manifest.json"
    )
    artifact = models.artifact_manifest(run_id=RUN_ID, members=members)
    _write_no_replace(output_dir / "artifact_manifest.json", artifact)
    report["artifact_manifest_id"] = artifact.manifest_id
    report["artifact_root"] = artifact.artifact_root
    report["formal_file_count"] = artifact.file_count + 1
    report["formal_total_byte_count"] = sum(
        path.stat().st_size for path in output_dir.rglob("*") if path.is_file()
    )
    return report


def _default_output(repository_root: Path) -> Path:
    return repository_root / "trusted_data_synthesis" / OUTPUT_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Finance v26.205 independent postrun audit")
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output = args.output_dir or _default_output(args.repository_root.resolve())
    report = build(
        repository_root=args.repository_root,
        output_dir=output,
        external_audit_path=args.external_audit,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
