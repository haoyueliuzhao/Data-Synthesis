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
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.experiments.vtdo_experiment import (
    json_explicit_authoritative_execution_kernel as kernel,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_empirical_evaluation_interface_localization as v202,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_empirical_evaluation_interface_localization_models as v202_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_execution as v200,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_calibration_preflight_models as models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    prospective_semantic_action_response_grammar as action_grammar,
)

RUN_ID: Final = (
    "finance_v26_203_fresh_first_response_action_interface_disambiguation_"
    "stratified_calibration_population_preflight_v1_20260902"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
EXTERNAL_AUDIT_SHA256: Final = "1c3009fc757fed7ea92aa8d522efb0bc9bf91ce3660d2da11e8d526c3c088795"
EXTERNAL_AUDIT_BYTES: Final = 15_697
V202_DECISION_ID: Final = (
    "finance_v26_202_decision:79d4dc83e6aea9fce43ae2c5016a1f7ad5c5a66bb888281696b68ebc70d1a3aa"
)
V202_TRANSITION_ID: Final = (
    "finance_v26_202_transition:e2eb5e4004d4bd744800e9c54222fd877aefe42b3fed85ececec38aa35595163"
)
V202_EVALUATION_ID: Final = (
    "finance_v26_202_exact_empirical_evidence_set_evaluation:"
    "0c055496991bb3e37dba0f18bada7b87a3a60d857ce9652d677b785002864e23"
)
V202_LOCALIZATION_ID: Final = (
    "finance_v26_202_first_response_interface_localization:"
    "45956f898d66005e6d8b49177b7bbf4b9ece7b9682c16d9e782d6c9cbce783ea"
)
V202_ARTIFACT_MANIFEST_ID: Final = (
    "finance_v26_202_artifact_manifest:"
    "6e80c2f33a92705d82e1dd6c4f9097db5103658dae487f26255af1a847fe3022"
)
V202_ARTIFACT_ROOT: Final = (
    "finance_v26_202_artifact_root:1c41c278c4c879586160715822a48ed9e8a39deb4fe9ca8b950e871424245b87"
)
V202_SOURCE_COMMIT: Final = "a4508dc1c896cb13533f2838d3d74d08d75a40ef"
V202_SOURCE_TREE: Final = "6fb1bf2ee025ed4db1a6910b5500626e1ac3d09f"
V202_FORMAL_FILE_COUNT: Final = 11
V202_FORMAL_BYTES: Final = 674_872
SELECTION_RULE: Final = (
    "within_answer_schema_x_depth_band_sort_prompt_bytes_package_replica_job_"
    "select_first_middle_last"
)


class V203Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V203Error(stage, reason)


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _write_no_replace(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (_canonical_json(value) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


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
    if len(commit) != 40 or len(tree) != 40:
        _fail("source.identity", "v26.203 Git source identity differs")
    return commit, tree


def _authorization(audit_path: Path) -> tuple[models.ExternalAuditAuthorization, bytes]:
    payload = audit_path.read_bytes()
    if len(payload) != EXTERNAL_AUDIT_BYTES or _sha256_bytes(payload) != EXTERNAL_AUDIT_SHA256:
        _fail("authorization", "v26.203 external Audit bytes differ")
    authorization = cast(
        models.ExternalAuditAuthorization,
        models.make_identity(
            models.ExternalAuditAuthorization,
            {
                "audit_sha256": EXTERNAL_AUDIT_SHA256,
                "audit_byte_count": EXTERNAL_AUDIT_BYTES,
                "revision_decision": "v26_201_retrospective_interpretation_revision_accepted",
            },
            field="authorization_id",
            prefix="finance_v26_203_external_audit_authorization:",
        ),
    )
    return authorization, payload


def _v202_freeze(
    package_root: Path,
    authorization_id: str,
) -> models.V202Freeze:
    root = package_root / v202.OUTPUT_DIR
    files = tuple(sorted(path for path in root.rglob("*") if path.is_file()))
    if len(files) != V202_FORMAL_FILE_COUNT or sum(path.stat().st_size for path in files) != (
        V202_FORMAL_BYTES
    ):
        _fail("v202.freeze.geometry", "v26.202 formal directory geometry differs")
    manifest = v202_models.ArtifactManifest.model_validate(_load(root / "artifact_manifest.json"))
    members = {item.relative_path: item for item in manifest.members}
    if set(members) != {
        path.relative_to(root).as_posix() for path in files if path.name != "artifact_manifest.json"
    }:
        _fail("v202.freeze.members", "v26.202 formal member set differs")
    for relative, member in members.items():
        path = root / relative
        if _sha256(path) != member.sha256 or path.stat().st_size != member.byte_count:
            _fail("v202.freeze.bytes", f"v26.202 formal member bytes differ:{relative}")
    decision = v202_models.Decision.model_validate(_load(root / "decision.json"))
    transition = v202_models.Transition.model_validate(_load(root / "prospective_transition.json"))
    evaluation = v202_models.ExactEmpiricalEvidenceSetEvaluation.model_validate(
        _load(root / "exact_empirical_evidence_set_evaluation.json")
    )
    localization = v202_models.FirstResponseInterfaceLocalization.model_validate(
        _load(root / "first_response_interface_localization.json")
    )
    source = _load(root / "source_identity.json")
    report = _load(root / "report.json")
    if (
        manifest.manifest_id != V202_ARTIFACT_MANIFEST_ID
        or manifest.artifact_root != V202_ARTIFACT_ROOT
        or decision.decision_id != V202_DECISION_ID
        or transition.transition_id != V202_TRANSITION_ID
        or evaluation.evaluation_id != V202_EVALUATION_ID
        or localization.audit_id != V202_LOCALIZATION_ID
        or source != {"source_commit": V202_SOURCE_COMMIT, "source_tree": V202_SOURCE_TREE}
        or report.get("q_first_fraction") != "0/192"
        or report.get("q_bounded_correction_fraction") != "0/192"
        or report.get("post_action_abi_denominator") != 0
        or report.get("provider_calls") != 0
    ):
        _fail("v202.freeze.identity", "v26.202 formal authority differs")
    return cast(
        models.V202Freeze,
        models.make_identity(
            models.V202Freeze,
            {
                "authorization_id": authorization_id,
                "v202_decision_id": decision.decision_id,
                "v202_transition_id": transition.transition_id,
                "v202_evaluation_id": evaluation.evaluation_id,
                "v202_localization_id": localization.audit_id,
                "v202_artifact_manifest_id": manifest.manifest_id,
                "v202_artifact_root": manifest.artifact_root,
                "v202_source_commit": V202_SOURCE_COMMIT,
                "v202_source_tree": V202_SOURCE_TREE,
            },
            field="freeze_id",
            prefix="finance_v26_203_v202_freeze:",
        ),
    )


def _action_contract(
    *,
    authorization: models.ExternalAuditAuthorization,
    freeze: models.V202Freeze,
    prepared: v200.PreparedOnlineExecution,
) -> models.ExactActionInterfaceContract:
    grammar = action_grammar.compile_semantic_action_response_grammar()
    parser_source = inspect.getsource(action_grammar.parse_exact_canonical_action_payload).encode()
    grammar_source = inspect.getsource(
        action_grammar.compile_semantic_action_response_grammar
    ).encode()
    if (
        tuple(action_grammar.ExactCanonicalActionPayload.model_fields) != action_grammar.FIELD_ORDER
        or grammar.grammar_id != prepared.runtime.profile.action_grammar_id
        or grammar.field_order != action_grammar.FIELD_ORDER
        or grammar.extra_fields_allowed
        or grammar.wrapper_allowed
    ):
        _fail("contract.grammar", "frozen exact Action parser or Grammar differs")
    return cast(
        models.ExactActionInterfaceContract,
        models.make_identity(
            models.ExactActionInterfaceContract,
            {
                "authorization_id": authorization.authorization_id,
                "v202_freeze_id": freeze.freeze_id,
                "frozen_action_grammar_id": grammar.grammar_id,
                "frozen_parser_source_sha256": _sha256_bytes(parser_source),
                "frozen_grammar_source_sha256": _sha256_bytes(grammar_source),
            },
            field="contract_id",
            prefix="fresh_first_response_exact_action_interface_contract:",
        ),
    )


def _interface_profiles(
    contract: models.ExactActionInterfaceContract,
) -> tuple[models.InterfaceProfile, models.InterfaceProfile]:
    control = cast(
        models.InterfaceProfile,
        models.make_identity(
            models.InterfaceProfile,
            {
                "contract_id": contract.contract_id,
                "arm": "C",
                "name": "contemporaneous_control",
                "message_roles": ("user",),
                "source_prompt_bytes_exact": True,
                "authoritative_system_contract_present": False,
                "old_response_abi_visible": True,
                "action_id_inside_authoritative_contract": False,
                "answer_and_operation_fields_marked_nonresponse": False,
                "grammar_id_host_side_only": False,
                "composite_interface_repair_package": False,
            },
            field="profile_id",
            prefix="fresh_first_response_interface_profile:",
        ),
    )
    repair = cast(
        models.InterfaceProfile,
        models.make_identity(
            models.InterfaceProfile,
            {
                "contract_id": contract.contract_id,
                "arm": "R",
                "name": "disambiguated_action_interface",
                "message_roles": ("system", "user"),
                "source_prompt_bytes_exact": False,
                "authoritative_system_contract_present": True,
                "old_response_abi_visible": False,
                "action_id_inside_authoritative_contract": True,
                "answer_and_operation_fields_marked_nonresponse": True,
                "grammar_id_host_side_only": True,
                "composite_interface_repair_package": True,
            },
            field="profile_id",
            prefix="fresh_first_response_interface_profile:",
        ),
    )
    return control, repair


def _depth_band(depth: str) -> models.DepthBand:
    if depth in {"d0_observability_anchor", "d1_basic"}:
        return "lower"
    if depth in {"d2_compositional", "d3_stress"}:
        return "higher"
    _fail("population.depth", f"unknown frozen depth:{depth}")


def _schema_family(answer_fields: tuple[str, ...]) -> models.SchemaFamily:
    if answer_fields == ("difference", "higher_ref"):
        return "comparison"
    if answer_fields == ("value",):
        return "scalar_value"
    _fail("population.answer_schema", f"unregistered Answer Schema:{answer_fields}")


def _source_rows(prepared: v200.PreparedOnlineExecution) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for job_id in prepared.authorization.exact_job_ids:
        parents = prepared.job_parents[job_id]
        context = v200.frozen_runtime.prepare_job(
            parents.runtime_job,
            prepared.runtime.runtime_catalog,
        )
        state = v200.frozen_runtime._initialize(context)  # noqa: SLF001
        public_prompt = v200.step_runtime.render_next_prompt(state)
        core = v200.v192._action_core(public_prompt, prepared.runtime)  # noqa: SLF001
        rendered = v200.v192._render_prompt(  # noqa: SLF001
            prompt_kind="action",
            core=core,
            contract=prepared.prompt_contract,
            schema=prepared.prompt_schema,
        )
        payload = json.loads(rendered)
        public = payload["prompt_core"]["public_prompt"]
        semantic = public["task"]["semantic_task"]
        candidates = tuple(public["candidates"])
        candidate_ids = tuple(str(item["action_id"]) for item in candidates)
        answer_fields = tuple(sorted(str(item) for item in semantic["answer_fields"]))
        family = _schema_family(answer_fields)
        depth = parents.runtime_job.depth.value
        band = _depth_band(depth)
        rows.append(
            {
                "source_v200_job_id": job_id,
                "source_package_id": parents.kernel_job.package_id,
                "source_runtime_job_id": parents.runtime_job.job_id,
                "source_group_id": parents.runtime_job.source_group_id,
                "capability_family": parents.runtime_job.capability_family.value,
                "replica_index": parents.runtime_job.replica_index,
                "schedule_ids": tuple(parents.runtime_job.schedule_ids),
                "depth": depth,
                "depth_band": band,
                "answer_schema_family": family,
                "answer_fields": answer_fields,
                "stratum_id": f"{family}:{band}",
                "control_prompt": rendered,
                "control_prompt_sha256": _sha256_bytes(rendered.encode()),
                "control_prompt_byte_count": len(rendered.encode()),
                "public_task_semantic_sha256": models.canonical_sha256(semantic),
                "current_state_semantic_sha256": models.canonical_sha256(public["state"]),
                "candidate_set_order_sha256": models.canonical_sha256(candidates),
                "current_state_id": payload["prompt_core"]["response_abi"]["state_id"],
                "candidate_action_ids": candidate_ids,
                "candidate_count": len(candidate_ids),
                "public_prompt": public,
                "semantic_task": semantic,
                "candidates": candidates,
            }
        )
    if len(rows) != 192:
        _fail("population.source", "frozen source Prompt denominator differs")
    return tuple(rows)


def _population(
    *,
    authorization: models.ExternalAuditAuthorization,
    freeze: models.V202Freeze,
    source_rows: Sequence[dict[str, Any]],
) -> tuple[models.StratifiedCalibrationPopulation, dict[str, dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        grouped[row["stratum_id"]].append(row)
    if set(grouped) != {
        "comparison:lower",
        "comparison:higher",
        "scalar_value:lower",
        "scalar_value:higher",
    }:
        _fail("population.strata", "registered calibration strata differ")
    cells: list[models.SourceCell] = []
    bound: dict[str, dict[str, Any]] = {}
    for stratum_id in sorted(grouped):
        ordered = sorted(
            grouped[stratum_id],
            key=lambda item: (
                item["control_prompt_byte_count"],
                item["source_package_id"],
                item["replica_index"],
                item["source_v200_job_id"],
            ),
        )
        ranks = (0, (len(ordered) - 1) // 2, len(ordered) - 1)
        for position, rank in zip(("short", "median", "long"), ranks, strict=True):
            row = ordered[rank]
            cell = cast(
                models.SourceCell,
                models.make_identity(
                    models.SourceCell,
                    {
                        key: row[key]
                        for key in (
                            "source_v200_job_id",
                            "source_package_id",
                            "source_runtime_job_id",
                            "source_group_id",
                            "capability_family",
                            "replica_index",
                            "schedule_ids",
                            "depth",
                            "depth_band",
                            "answer_schema_family",
                            "answer_fields",
                            "stratum_id",
                            "control_prompt_sha256",
                            "control_prompt_byte_count",
                            "public_task_semantic_sha256",
                            "current_state_semantic_sha256",
                            "candidate_set_order_sha256",
                            "current_state_id",
                            "candidate_action_ids",
                            "candidate_count",
                        )
                    }
                    | {
                        "stratum_size": len(ordered),
                        "selection_position": position,
                        "selection_rank": rank,
                    },
                    field="source_cell_id",
                    prefix="fresh_first_response_calibration_source_cell:",
                ),
            )
            cells.append(cell)
            bound[cell.source_cell_id] = row
    population = cast(
        models.StratifiedCalibrationPopulation,
        models.make_identity(
            models.StratifiedCalibrationPopulation,
            {
                "authorization_id": authorization.authorization_id,
                "v202_freeze_id": freeze.freeze_id,
                "cells": tuple(sorted(cells, key=lambda item: item.source_cell_id)),
                "selection_rule": SELECTION_RULE,
            },
            field="population_id",
            prefix="fresh_first_response_stratified_calibration_population:",
        ),
    )
    return population, bound


def _message(role: str, content: str) -> models.RequestMessage:
    return models.RequestMessage(
        role=cast(Any, role),
        content=content,
        content_sha256=_sha256_bytes(content.encode()),
        content_byte_count=len(content.encode()),
    )


def _recursive_key_count(value: Any, target: str) -> int:
    if isinstance(value, dict):
        return int(target in value) + sum(
            _recursive_key_count(item, target) for item in value.values()
        )
    if isinstance(value, list):
        return sum(_recursive_key_count(item, target) for item in value)
    return 0


def _repair_messages(
    *,
    row: dict[str, Any],
    contract: models.ExactActionInterfaceContract,
) -> tuple[models.RequestMessage, models.RequestMessage]:
    public = copy.deepcopy(row["public_prompt"])
    semantic = public["task"]["semantic_task"]
    answer_fields = semantic.pop("answer_fields")
    output_fields = semantic.pop("operator_output_fields")
    verifier_metadata = {
        "answer_fields": answer_fields,
        "classification": "verifier_internal_task_metadata_not_model_response_schema",
        "model_response_schema": False,
        "operator_output_fields": output_fields,
    }
    system_payload = {
        "authoritative_response_contract": {
            "additional_properties": False,
            "allowed_fields": list(contract.allowed_fields),
            "exactly_one_json_object": True,
            "field_values": {
                "action_id": {"one_of": list(row["candidate_action_ids"])},
                "decision_kind": contract.decision_kind_value,
                "protocol": contract.protocol_value,
                "state_id": row["current_state_id"],
            },
            "required_fields": list(contract.required_fields),
            "wrapper_allowed": False,
        },
        "instruction": (
            "Return exactly one JSON object conforming only to the authoritative four-field "
            "Action response contract. Do not answer the task directly and do not emit any "
            "additional field or wrapper."
        ),
    }
    user_payload = {
        "interface_profile": "disambiguated_action_interface",
        "prompt_kind": "action",
        "public_prompt": public,
        "response_contract_location": "system_message_only",
        "verifier_internal_task_metadata": verifier_metadata,
    }
    if (
        _recursive_key_count(user_payload, "response_abi")
        or _recursive_key_count(user_payload, "grammar_id")
        or _recursive_key_count(system_payload, "grammar_id")
        or _recursive_key_count(user_payload, "answer_fields") != 1
        or _recursive_key_count(user_payload, "operator_output_fields") != 1
    ):
        _fail("interface.repair", "repaired model-visible interface projection differs")
    return _message("system", _canonical_json(system_payload)), _message(
        "user", _canonical_json(user_payload)
    )


def _request_body(
    config: v200.AgentModelConfig,
    messages: tuple[models.RequestMessage, ...],
) -> dict[str, Any]:
    body = kernel.make_stage_one_request_body(config, messages[-1].content)
    body["messages"] = [{"role": item.role, "content": item.content} for item in messages]
    return body


def _jobs_and_manifest(
    *,
    prepared: v200.PreparedOnlineExecution,
    population: models.StratifiedCalibrationPopulation,
    source_by_cell: dict[str, dict[str, Any]],
    contract: models.ExactActionInterfaceContract,
    profiles: tuple[models.InterfaceProfile, models.InterfaceProfile],
) -> tuple[models.CalibrationManifest, v200.AgentModelConfig]:
    profile_by_arm = {item.arm: item for item in profiles}
    profile_payload = _load(prepared.package_root / v200.MODEL_PROFILE_PATH)
    config = v200.require_stage_one_model_config(
        v200.AgentModelConfig.model_validate(profile_payload.get("model", profile_payload))
    )
    config_sha = models.canonical_sha256(config.model_dump(mode="json"))
    hash_order = sorted(
        population.cells,
        key=lambda item: _sha256_bytes(item.source_cell_id.encode()),
    )
    control_first_cells = {item.source_cell_id for item in hash_order[:6]}
    jobs: list[models.CalibrationJob] = []
    requests: list[models.FirstRequestDescriptor] = []
    for cell in population.cells:
        row = source_by_cell[cell.source_cell_id]
        pair_id = canonical_hash(
            {
                "population_id": population.population_id,
                "source_cell_id": cell.source_cell_id,
            },
            prefix="fresh_first_response_calibration_pair:",
        )
        arm_order = ("C", "R") if cell.source_cell_id in control_first_cells else ("R", "C")
        for arm in ("C", "R"):
            profile = profile_by_arm[arm]
            messages = (
                (_message("user", row["control_prompt"]),)
                if arm == "C"
                else _repair_messages(row=row, contract=contract)
            )
            namespace_parent = {
                "population_id": population.population_id,
                "source_cell_id": cell.source_cell_id,
                "pair_id": pair_id,
                "arm": arm,
            }
            job = cast(
                models.CalibrationJob,
                models.make_identity(
                    models.CalibrationJob,
                    {
                        "pair_id": pair_id,
                        "source_cell_id": cell.source_cell_id,
                        "source_v200_job_id": cell.source_v200_job_id,
                        "arm": arm,
                        "interface_profile_id": profile.profile_id,
                        "execution_order_within_pair": arm_order.index(arm),
                        "raw_namespace": canonical_hash(
                            namespace_parent,
                            prefix="fresh_first_response_calibration_raw_namespace:",
                        ),
                        "result_namespace": canonical_hash(
                            namespace_parent,
                            prefix="fresh_first_response_calibration_result_namespace:",
                        ),
                        "observation_namespace": canonical_hash(
                            namespace_parent,
                            prefix="fresh_first_response_calibration_observation_namespace:",
                        ),
                        "model_config_id": prepared.authorization.model_config_id,
                        "model_request_config_sha256": config_sha,
                        "thinking_policy_id": prepared.runtime.profile.thinking_policy_id,
                        "bounded_generation_policy_id": (
                            prepared.runtime.profile.bounded_generation_policy_id
                        ),
                        "resource_contract_id": prepared.runtime.profile.resource_contract_id,
                        "public_task_semantic_sha256": cell.public_task_semantic_sha256,
                        "current_state_semantic_sha256": cell.current_state_semantic_sha256,
                        "candidate_set_order_sha256": cell.candidate_set_order_sha256,
                        "schedule_ids": cell.schedule_ids,
                    },
                    field="job_id",
                    prefix="fresh_first_response_calibration_job:",
                ),
            )
            body = _request_body(config, messages)
            request = cast(
                models.FirstRequestDescriptor,
                models.make_identity(
                    models.FirstRequestDescriptor,
                    {
                        "job_id": job.job_id,
                        "pair_id": pair_id,
                        "source_cell_id": cell.source_cell_id,
                        "arm": arm,
                        "interface_profile_id": profile.profile_id,
                        "messages": messages,
                        "canonical_request_body_sha256": models.canonical_sha256(body),
                        "model_request_config_sha256": config_sha,
                        "public_task_semantic_sha256": cell.public_task_semantic_sha256,
                        "current_state_semantic_sha256": cell.current_state_semantic_sha256,
                        "candidate_set_order_sha256": cell.candidate_set_order_sha256,
                    },
                    field="request_id",
                    prefix="fresh_first_response_request_descriptor:",
                ),
            )
            jobs.append(job)
            requests.append(request)
    manifest = cast(
        models.CalibrationManifest,
        models.make_identity(
            models.CalibrationManifest,
            {
                "authorization_id": population.authorization_id,
                "population_id": population.population_id,
                "action_contract_id": contract.contract_id,
                "interface_profile_ids": tuple(sorted(item.profile_id for item in profiles)),
                "jobs": tuple(sorted(jobs, key=lambda item: item.job_id)),
                "requests": tuple(sorted(requests, key=lambda item: item.request_id)),
                "expected_job_ids": tuple(sorted(item.job_id for item in jobs)),
                "expected_request_ids": tuple(sorted(item.request_id for item in requests)),
            },
            field="manifest_id",
            prefix="fresh_first_response_calibration_manifest:",
        ),
    )
    _validate_authoritative_manifest(
        candidate=manifest,
        expected=manifest,
        population=population,
        source_by_cell=source_by_cell,
        contract=contract,
        profiles=profiles,
        config=config,
    )
    return manifest, config


def _reconstruct_repair_semantics(
    request: models.FirstRequestDescriptor,
) -> tuple[dict[str, Any], dict[str, Any], tuple[dict[str, Any], ...]]:
    system = json.loads(request.messages[0].content)
    user = json.loads(request.messages[1].content)
    public = user["public_prompt"]
    semantic = copy.deepcopy(public["task"]["semantic_task"])
    metadata = user["verifier_internal_task_metadata"]
    semantic["answer_fields"] = metadata["answer_fields"]
    semantic["operator_output_fields"] = metadata["operator_output_fields"]
    return system, semantic, tuple(public["candidates"])


def _validate_authoritative_manifest(
    *,
    candidate: models.CalibrationManifest,
    expected: models.CalibrationManifest,
    population: models.StratifiedCalibrationPopulation,
    source_by_cell: dict[str, dict[str, Any]],
    contract: models.ExactActionInterfaceContract,
    profiles: tuple[models.InterfaceProfile, models.InterfaceProfile],
    config: v200.AgentModelConfig,
) -> None:
    strict = models.CalibrationManifest.model_validate(
        candidate.model_dump(mode="json", warnings=False)
    )
    if _canonical_bytes(strict) != _canonical_bytes(expected):
        _fail("manifest.exact", "calibration Manifest differs from the precommitted exact set")
    cells = {item.source_cell_id: item for item in population.cells}
    requests = {item.job_id: item for item in strict.requests}
    profile_by_arm = {item.arm: item for item in profiles}
    for job in strict.jobs:
        cell = cells[job.source_cell_id]
        row = source_by_cell[job.source_cell_id]
        request = requests[job.job_id]
        if (
            job.source_v200_job_id != cell.source_v200_job_id
            or job.schedule_ids != cell.schedule_ids
            or job.public_task_semantic_sha256 != cell.public_task_semantic_sha256
            or job.current_state_semantic_sha256 != cell.current_state_semantic_sha256
            or job.candidate_set_order_sha256 != cell.candidate_set_order_sha256
            or job.interface_profile_id != profile_by_arm[job.arm].profile_id
        ):
            _fail("manifest.parent", "calibration Job changed a frozen semantic parent")
        if job.arm == "C":
            if request.messages[0].content != row["control_prompt"]:
                _fail("interface.control", "control Prompt is not byte-exact v26.200 input")
        else:
            system, semantic, candidates = _reconstruct_repair_semantics(request)
            contract_payload = system["authoritative_response_contract"]
            if (
                tuple(contract_payload["required_fields"]) != contract.required_fields
                or tuple(contract_payload["allowed_fields"]) != contract.allowed_fields
                or contract_payload["additional_properties"] is not False
                or contract_payload["wrapper_allowed"] is not False
                or tuple(contract_payload["field_values"]["action_id"]["one_of"])
                != cell.candidate_action_ids
                or contract_payload["field_values"]["state_id"] != cell.current_state_id
                or contract_payload["field_values"]["decision_kind"] != contract.decision_kind_value
                or contract_payload["field_values"]["protocol"] != contract.protocol_value
                or models.canonical_sha256(semantic) != cell.public_task_semantic_sha256
                or models.canonical_sha256(candidates) != cell.candidate_set_order_sha256
                or _recursive_key_count(json.loads(request.messages[1].content), "response_abi")
                or _recursive_key_count(json.loads(request.messages[1].content), "grammar_id")
            ):
                _fail("interface.repair", "repaired Prompt changes or duplicates its interface")
        body = _request_body(config, request.messages)
        if models.canonical_sha256(body) != request.canonical_request_body_sha256:
            _fail("request.body", "calibration request body identity differs")


def _response(
    *,
    job: models.CalibrationJob,
    request: models.FirstRequestDescriptor,
    payload: dict[str, Any],
) -> models.FirstResponseDescriptor:
    return cast(
        models.FirstResponseDescriptor,
        models.make_identity(
            models.FirstResponseDescriptor,
            {
                "job_id": job.job_id,
                "request_id": request.request_id,
                "source_cell_id": job.source_cell_id,
                "arm": job.arm,
                "evidence_kind": "scripted_preflight_control",
                "response_sha256": models.canonical_sha256(payload),
                "typed_outer_terminal": None,
                "exact_json_object": payload,
                "usage": None,
                "thinking_present": None,
                "provider_call_count": 0,
            },
            field="response_id",
            prefix="fresh_first_response_descriptor:",
        ),
    )


def _observation(
    *,
    response: models.FirstResponseDescriptor,
) -> models.FirstActionInterfaceObservation:
    return cast(
        models.FirstActionInterfaceObservation,
        models.make_identity(
            models.FirstActionInterfaceObservation,
            {
                "job_id": response.job_id,
                "request_id": response.request_id,
                "response_id": response.response_id,
                "source_cell_id": response.source_cell_id,
                "arm": response.arm,
                "evidence_kind": response.evidence_kind,
                "typed_outer_terminal": None,
                "exact_json_object": response.exact_json_object,
                "exact_four_field_abi_valid": True,
                "action_reference_valid": True,
                "state_binding_valid": True,
                "runtime_step_committed": None,
                "answer_schema_exact_match": False,
                "operation_output_schema_exact_match": False,
                "usage": None,
                "thinking_present": None,
            },
            field="observation_id",
            prefix="fresh_first_action_interface_observation:",
        ),
    )


def _validate_evidence_chain(
    *,
    manifest: models.CalibrationManifest,
    responses: Sequence[models.FirstResponseDescriptor],
    observations: Sequence[models.FirstActionInterfaceObservation],
) -> None:
    jobs = {item.job_id: item for item in manifest.jobs}
    requests = {item.request_id: item for item in manifest.requests}
    response_map = {item.response_id: item for item in responses}
    for response in responses:
        job = jobs.get(response.job_id)
        request = requests.get(response.request_id)
        if (
            job is None
            or request is None
            or request.job_id != response.job_id
            or job.source_cell_id != response.source_cell_id
            or job.arm != response.arm
        ):
            _fail("evidence.response_parent", "FirstResponseDescriptor parent differs")
    for observation in observations:
        found_response = response_map.get(observation.response_id)
        if (
            found_response is None
            or observation.job_id != found_response.job_id
            or observation.request_id != found_response.request_id
            or observation.source_cell_id != found_response.source_cell_id
            or observation.arm != found_response.arm
            or observation.evidence_kind != found_response.evidence_kind
            or observation.exact_json_object != found_response.exact_json_object
        ):
            _fail("evidence.observation_parent", "FirstActionInterfaceObservation parent differs")


def _evidence_schema_audit(
    manifest: models.CalibrationManifest,
) -> tuple[
    models.EvidenceSchemaAudit,
    tuple[models.FirstResponseDescriptor, ...],
    tuple[models.FirstActionInterfaceObservation, ...],
]:
    cell_id = manifest.jobs[0].source_cell_id
    jobs = tuple(
        sorted(
            (item for item in manifest.jobs if item.source_cell_id == cell_id),
            key=lambda item: item.arm,
        )
    )
    requests = {item.job_id: item for item in manifest.requests}
    responses: list[models.FirstResponseDescriptor] = []
    observations: list[models.FirstActionInterfaceObservation] = []
    for job in jobs:
        request = requests[job.job_id]
        cell_request = request
        if job.arm == "R":
            system = json.loads(request.messages[0].content)["authoritative_response_contract"]
            action_id = system["field_values"]["action_id"]["one_of"][0]
            state_id = system["field_values"]["state_id"]
        else:
            prompt = json.loads(request.messages[0].content)
            action_id = prompt["prompt_core"]["public_prompt"]["candidates"][0]["action_id"]
            state_id = prompt["prompt_core"]["response_abi"]["state_id"]
        payload = {
            "action_id": action_id,
            "decision_kind": "execute_public_operation",
            "protocol": action_grammar.RESPONSE_PROTOCOL_VERSION,
            "state_id": state_id,
        }
        parsed = action_grammar.parse_exact_canonical_action_payload(payload)
        if {
            "action_id": parsed.action_id,
            "decision_kind": parsed.decision_kind,
            "protocol": action_grammar.RESPONSE_PROTOCOL_VERSION,
            "state_id": parsed.state_id,
        } != payload:
            _fail("evidence.fixture", "exact parser fixture differs")
        response = _response(job=job, request=cell_request, payload=payload)
        responses.append(response)
        observations.append(_observation(response=response))
    _validate_evidence_chain(
        manifest=manifest,
        responses=responses,
        observations=observations,
    )
    schema_hashes = {
        "calibration_job_schema_sha256": models.canonical_sha256(
            models.CalibrationJob.model_json_schema()
        ),
        "request_descriptor_schema_sha256": models.canonical_sha256(
            models.FirstRequestDescriptor.model_json_schema()
        ),
        "response_descriptor_schema_sha256": models.canonical_sha256(
            models.FirstResponseDescriptor.model_json_schema()
        ),
        "observation_schema_sha256": models.canonical_sha256(
            models.FirstActionInterfaceObservation.model_json_schema()
        ),
        "evaluation_schema_sha256": models.canonical_sha256(
            models.ExactPairedCalibrationEvaluation.model_json_schema()
        ),
    }
    audit = cast(
        models.EvidenceSchemaAudit,
        models.make_identity(
            models.EvidenceSchemaAudit,
            {"manifest_id": manifest.manifest_id, **schema_hashes},
            field="audit_id",
            prefix="finance_v26_203_calibration_evidence_schema_audit:",
        ),
    )
    return audit, tuple(responses), tuple(observations)


def _online_gate_contract(manifest: models.CalibrationManifest) -> models.OnlineGateContract:
    return cast(
        models.OnlineGateContract,
        models.make_identity(
            models.OnlineGateContract,
            {"manifest_id": manifest.manifest_id},
            field="contract_id",
            prefix="fresh_first_response_online_calibration_gate_contract:",
        ),
    )


def _capture(call: Callable[[], None]) -> str:
    try:
        call()
    except (V203Error, ValidationError, ValueError) as exc:
        if isinstance(exc, V203Error):
            return f"{exc.stage}:{exc.reason}"
        return f"{type(exc).__name__}:{exc}"
    raise AssertionError("v26.203 preflight control was accepted")


def _control_result(
    *,
    name: str,
    expected: str,
    calls: Sequence[Callable[[], None]],
) -> models.ControlClassResult:
    reasons = tuple(_capture(call) for call in calls)
    return cast(
        models.ControlClassResult,
        models.make_identity(
            models.ControlClassResult,
            {
                "control_class": name,
                "case_count": len(reasons),
                "rejected_case_count": len(reasons),
                "expected_reason": expected,
                "observed_reasons": reasons,
            },
            field="result_id",
            prefix="finance_v26_203_preflight_control_class_result:",
        ),
    )


def _validate_contract_exact(
    candidate: models.ExactActionInterfaceContract, expected: models.ExactActionInterfaceContract
) -> None:
    strict = models.ExactActionInterfaceContract.model_validate(candidate.model_dump(mode="json"))
    if _canonical_bytes(strict) != _canonical_bytes(expected):
        _fail("contract.exact", "Action parser/Grammar Contract differs")


def _reject_historical_adapter(enabled: bool) -> None:
    if enabled:
        _fail("history.adaptation", "historical response adaptation is forbidden")


def _preflight_controls(
    *,
    manifest: models.CalibrationManifest,
    population: models.StratifiedCalibrationPopulation,
    source_by_cell: dict[str, dict[str, Any]],
    contract: models.ExactActionInterfaceContract,
    profiles: tuple[models.InterfaceProfile, models.InterfaceProfile],
    config: v200.AgentModelConfig,
    evidence_audit: models.EvidenceSchemaAudit,
    fixture_responses: tuple[models.FirstResponseDescriptor, ...],
    fixture_observations: tuple[models.FirstActionInterfaceObservation, ...],
) -> models.PreflightControlAudit:
    first_job = manifest.jobs[0]

    def changed_job(field: str) -> None:
        bad = first_job.model_copy(update={field: "0" * 64})
        jobs = (bad,) + manifest.jobs[1:]
        candidate = manifest.model_copy(update={"jobs": jobs})
        _validate_authoritative_manifest(
            candidate=candidate,
            expected=manifest,
            population=population,
            source_by_cell=source_by_cell,
            contract=contract,
            profiles=profiles,
            config=config,
        )

    semantic_parent = _control_result(
        name="repair_task_state_candidate_semantic_byte_change",
        expected="frozen semantic parent mismatch",
        calls=tuple(
            partial(changed_job, field)
            for field in (
                "public_task_semantic_sha256",
                "current_state_semantic_sha256",
                "candidate_set_order_sha256",
            )
        ),
    )

    def relaxed_contract() -> None:
        changed = contract.model_copy(update={"additional_properties_allowed": True})
        _validate_contract_exact(changed, contract)

    parser = _control_result(
        name="parser_relaxation_for_answer_or_value_payload",
        expected="exact parser Contract mismatch",
        calls=(relaxed_contract,),
    )
    adaptation = _control_result(
        name="historical_public_response_adaptation",
        expected="historical adaptation forbidden",
        calls=(lambda: _reject_historical_adapter(True),),
    )

    def changed_denominator(kind: str) -> None:
        if kind == "missing":
            jobs = manifest.jobs[:-1]
        elif kind == "duplicate":
            jobs = manifest.jobs[:-1] + (manifest.jobs[0],)
        else:
            jobs = manifest.jobs + (manifest.jobs[0].model_copy(update={"job_id": "extra"}),)
        models.CalibrationManifest.model_validate(
            manifest.model_dump(mode="json")
            | {"jobs": [item.model_dump(mode="json") for item in jobs]}
        )

    denominator = _control_result(
        name="calibration_job_missing_duplicate_or_extra",
        expected="exact 24-Job denominator mismatch",
        calls=tuple(
            partial(changed_denominator, kind) for kind in ("missing", "duplicate", "extra")
        ),
    )

    def crossed_response() -> None:
        left, right = fixture_responses
        bad = left.model_copy(update={"request_id": right.request_id})
        _validate_evidence_chain(
            manifest=manifest,
            responses=(bad, right),
            observations=fixture_observations,
        )

    def crossed_observation() -> None:
        left, right = fixture_observations
        bad = left.model_copy(update={"response_id": right.response_id})
        _validate_evidence_chain(
            manifest=manifest,
            responses=fixture_responses,
            observations=(bad, right),
        )

    crossed = _control_result(
        name="cross_arm_request_response_or_observation_parent",
        expected="cross-arm evidence parent mismatch",
        calls=(crossed_response, crossed_observation),
    )

    def unauthorized_field(field: str, value: Any) -> None:
        bad = first_job.model_copy(update={field: value})
        models.CalibrationJob.model_validate(bad.model_dump(mode="json"))

    unauthorized = _control_result(
        name="qa_old_job_retry_or_recovery_injection",
        expected="unauthorized parent or execution path",
        calls=(
            lambda: unauthorized_field("qa_parent_count", 1),
            lambda: unauthorized_field("job_id", first_job.source_v200_job_id),
            lambda: unauthorized_field("automatic_retries", 1),
            lambda: unauthorized_field("recovery_calls", 1),
        ),
    )
    controls = (semantic_parent, parser, adaptation, denominator, crossed, unauthorized)
    return cast(
        models.PreflightControlAudit,
        models.make_identity(
            models.PreflightControlAudit,
            {
                "manifest_id": manifest.manifest_id,
                "evidence_schema_audit_id": evidence_audit.audit_id,
                "controls": controls,
            },
            field="audit_id",
            prefix="finance_v26_203_preflight_control_audit:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_audit_path: Path,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    package_root = repository_root / "trusted_data_synthesis"
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"v26.203 output already exists:{output_dir}")
    authorization, audit_bytes = _authorization(external_audit_path)
    freeze = _v202_freeze(package_root, authorization.authorization_id)
    prepared = v200.prepare_execution(
        repository_root=repository_root,
        output_dir=output_dir,
        external_audit_path=package_root / v200.OUTPUT_DIR / "external_v26_199_execution_audit.txt",
    )
    contract = _action_contract(
        authorization=authorization,
        freeze=freeze,
        prepared=prepared,
    )
    profiles = _interface_profiles(contract)
    source_rows = _source_rows(prepared)
    population, source_by_cell = _population(
        authorization=authorization,
        freeze=freeze,
        source_rows=source_rows,
    )
    manifest, config = _jobs_and_manifest(
        prepared=prepared,
        population=population,
        source_by_cell=source_by_cell,
        contract=contract,
        profiles=profiles,
    )
    evidence_audit, fixture_responses, fixture_observations = _evidence_schema_audit(manifest)
    gate_contract = _online_gate_contract(manifest)
    controls = _preflight_controls(
        manifest=manifest,
        population=population,
        source_by_cell=source_by_cell,
        contract=contract,
        profiles=profiles,
        config=config,
        evidence_audit=evidence_audit,
        fixture_responses=fixture_responses,
        fixture_observations=fixture_observations,
    )
    decision = cast(
        models.Decision,
        models.make_identity(
            models.Decision,
            {
                "authorization_id": authorization.authorization_id,
                "population_id": population.population_id,
                "manifest_id": manifest.manifest_id,
                "evidence_schema_audit_id": evidence_audit.audit_id,
                "gate_contract_id": gate_contract.contract_id,
                "control_audit_id": controls.audit_id,
                "decision": (
                    "fresh_first_response_action_interface_disambiguation_stratified_"
                    "24_job_population_preflight_passed"
                ),
                "first_root_blocker": (
                    "model_visible_first_response_action_interface_not_yet_empirically_instantiated"
                ),
            },
            field="decision_id",
            prefix="finance_v26_203_decision:",
        ),
    )
    transition = cast(
        models.Transition,
        models.make_identity(
            models.Transition,
            {"decision_id": decision.decision_id},
            field="transition_id",
            prefix="finance_v26_203_transition:",
        ),
    )
    source_commit, source_tree = _git_identity(repository_root)
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_bytes_no_replace(output_dir / "external_audit.txt", audit_bytes)
    _write_no_replace(output_dir / "external_authorization.json", authorization)
    _write_no_replace(output_dir / "v26_202_freeze.json", freeze)
    _write_no_replace(output_dir / "exact_action_interface_contract.json", contract)
    _write_no_replace(
        output_dir / "interface_profiles.json",
        {
            "profiles": [item.model_dump(mode="json") for item in profiles],
            "schema_version": models.SCHEMA_VERSION,
        },
    )
    _write_no_replace(output_dir / "stratified_calibration_population.json", population)
    _write_no_replace(output_dir / "calibration_manifest.json", manifest)
    _write_no_replace(output_dir / "calibration_evidence_schema_audit.json", evidence_audit)
    _write_no_replace(output_dir / "online_gate_contract.json", gate_contract)
    _write_no_replace(output_dir / "preflight_control_audit.json", controls)
    _write_no_replace(output_dir / "decision.json", decision)
    _write_no_replace(output_dir / "prospective_transition.json", transition)
    stratum_counts = Counter(item.stratum_id for item in population.cells)
    report = {
        "run_id": RUN_ID,
        "consumed_stage": models.CONSUMED_STAGE,
        "source_commit": source_commit,
        "source_tree": source_tree,
        "authorization_id": authorization.authorization_id,
        "v202_freeze_id": freeze.freeze_id,
        "action_contract_id": contract.contract_id,
        "interface_profile_ids": [item.profile_id for item in profiles],
        "population_id": population.population_id,
        "manifest_id": manifest.manifest_id,
        "evidence_schema_audit_id": evidence_audit.audit_id,
        "online_gate_contract_id": gate_contract.contract_id,
        "control_audit_id": controls.audit_id,
        "decision_id": decision.decision_id,
        "transition_id": transition.transition_id,
        "source_prompt_census_count": 192,
        "source_cell_count": 12,
        "stratum_counts": dict(sorted(stratum_counts.items())),
        "control_job_count": 12,
        "repair_job_count": 12,
        "fresh_calibration_job_count": 24,
        "planned_future_stage_one_calls_after_authorization": 24,
        "planned_stage_two_calls": 0,
        "automatic_retries": 0,
        "recovery_calls": 0,
        "provider_calls": 0,
        "credential_lookups": 0,
        "historical_response_reads_for_selection": 0,
        "historical_response_adaptation_count": 0,
        "parser_relaxation_count": 0,
        "empirical_response_count": 0,
        "empirical_observation_count": 0,
        "empirical_evaluation_count": 0,
        "qa_mapper_state_frequency_contribution_vtdo_rows": 0,
        "decision": decision.decision,
        "first_root_blocker": decision.first_root_blocker,
        "next_decision": transition.next_decision,
        "planned_online_stage": transition.planned_online_stage,
        "schema_version": models.SCHEMA_VERSION,
    }
    _write_no_replace(output_dir / "report.json", report)
    _write_no_replace(
        output_dir / "source_identity.json",
        {"source_commit": source_commit, "source_tree": source_tree},
    )
    members = tuple(
        models.ArtifactMember(
            relative_path=path.relative_to(output_dir).as_posix(),
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
        for path in sorted(item for item in output_dir.rglob("*") if item.is_file())
    )
    artifact_manifest = models.artifact_manifest(run_id=RUN_ID, members=members)
    _write_no_replace(output_dir / "artifact_manifest.json", artifact_manifest)
    return {
        **report,
        "artifact_manifest_id": artifact_manifest.manifest_id,
        "artifact_root": artifact_manifest.artifact_root,
        "formal_file_count": artifact_manifest.file_count + 1,
        "formal_total_byte_count": (
            artifact_manifest.total_byte_count
            + (output_dir / "artifact_manifest.json").stat().st_size
        ),
    }


def _default_output(package_root: Path) -> Path:
    return package_root / OUTPUT_DIR


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--external-audit", type=Path, required=True)
    args = parser.parse_args()
    repository_root = args.repository_root.resolve()
    package_root = repository_root / "trusted_data_synthesis"
    output_dir = (args.output_dir or _default_output(package_root)).resolve()
    print(
        _canonical_json(
            build(
                repository_root=repository_root,
                output_dir=output_dir,
                external_audit_path=args.external_audit.resolve(),
            )
        )
    )


if __name__ == "__main__":
    main()
