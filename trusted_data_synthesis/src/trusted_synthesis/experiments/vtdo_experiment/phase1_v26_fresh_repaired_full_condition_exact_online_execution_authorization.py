# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_action_interface_full_condition_integration_preflight_models as v206_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_exact_online_execution_authorization_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_continuity_independent_audit_models as v210_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)

RUN_ID: Final = (
    "finance_v26_211_fresh_repaired_full_condition_exact_192_job_"
    "online_execution_authorization_v1_20260902"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
EXTERNAL_REVIEW_SHA256: Final = "6f620c16c86a10098691156500af98cd014810d63fe2fe4915b67ab850138b82"
EXTERNAL_REVIEW_BYTES: Final = 12_940
OPERATOR_DIRECTIVE: Final = "参照审计，继续实验"
V210_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_210_fresh_repaired_full_condition_final_request_"
    "continuity_independent_audit_v1_20260902"
)
V209_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_209_fresh_repaired_full_condition_executable_runner_"
    "final_request_contract_continuity_repair_preflight_v1_20260902"
)
V206_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_206_fresh_repaired_action_interface_full_condition_"
    "integration_preflight_v1_20260902"
)
V192_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_192_json_explicit_prompt_contract_preflight_v1_20260831"
)
MODEL_PROFILE: Final = (
    "trusted_data_synthesis/config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
)
V209_SOURCE_COMMIT: Final = "5809e9782515e55ee797b43730584d5d860aaa5c"
V209_SOURCE_TREE: Final = "b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf"
V210_SOURCE_COMMIT: Final = "56238892be483da4bab0d188dcc1fe69287174bf"
V210_SOURCE_TREE: Final = "b0e329e53318f17b2d1930023c3bd872660bea64"
IMPLEMENTATION_FILES: Final = tuple(
    sorted(
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_full_condition_exact_online_execution_authorization.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_full_condition_exact_online_execution_authorization_models.py",
            "trusted_data_synthesis/tests/"
            "test_v26_fresh_repaired_full_condition_exact_online_execution_authorization.py",
        )
    )
)


class V211Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V211Error(stage, reason)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _bytes(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _make(model_type: type[Any], values: dict[str, Any], field: str, prefix: str) -> Any:
    return models.make_identity(model_type, values, field=field, prefix=prefix)


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()


def _verify_manifest(
    root: Path, manifest: Any, manifest_name: str = "artifact_manifest.json"
) -> tuple[int, int]:
    files = tuple(sorted(path for path in root.iterdir() if path.is_file()))
    expected = {path.name for path in files if path.name != manifest_name}
    if {item.relative_path for item in manifest.members} != expected:
        _fail("freeze.paths", f"formal path set differs:{root.name}")
    for member in manifest.members:
        payload = (root / member.relative_path).read_bytes()
        if len(payload) != member.byte_count or _sha(payload) != member.sha256:
            _fail("freeze.bytes", f"formal member differs:{member.relative_path}")
    return len(files), sum(path.stat().st_size for path in files)


def _external_decision(
    review_path: Path,
) -> tuple[models.ExternalOnlineAuthorizationDecision, bytes, bytes]:
    review = review_path.read_bytes()
    if len(review) != EXTERNAL_REVIEW_BYTES or _sha(review) != EXTERNAL_REVIEW_SHA256:
        _fail("authorization.external_review", "v26.211 external review bytes differ")
    directive = OPERATOR_DIRECTIVE.encode("utf-8")
    decision = cast(
        models.ExternalOnlineAuthorizationDecision,
        _make(
            models.ExternalOnlineAuthorizationDecision,
            {
                "review_sha256": _sha(review),
                "review_byte_count": len(review),
                "operator_directive_sha256": _sha(directive),
                "operator_directive_byte_count": len(directive),
            },
            "decision_id",
            "finance_v26_211_external_online_authorization_decision:",
        ),
    )
    return decision, review, directive


def _v210_freeze(
    *,
    repository_root: Path,
    external_decision_id: str,
) -> models.V210AuthorityFreeze:
    root = repository_root / V210_DIR
    artifact = v210_models.ArtifactManifest.model_validate(_load(root / "artifact_manifest.json"))
    file_count, total_bytes = _verify_manifest(root, artifact)
    if (file_count, total_bytes, artifact.file_count, artifact.total_byte_count) != (
        15,
        1_344_368,
        14,
        1_341_853,
    ):
        _fail("freeze.v210_geometry", "v26.210 formal geometry differs")
    report = v210_models.IndependentAuditReport.model_validate(_load(root / "report.json"))
    decision = v210_models.IndependentAuditDecision.model_validate(
        _load(root / "independent_audit_decision.json")
    )
    gate = v210_models.IndependentAuditGateEvaluation.model_validate(
        _load(root / "independent_audit_gate_evaluation.json")
    )
    transition = v210_models.ProspectiveTransition.model_validate(
        _load(root / "prospective_transition.json")
    )
    source = v210_models.SourceIdentity.model_validate(_load(root / "source_identity.json"))
    if (
        source.source_commit != V210_SOURCE_COMMIT
        or source.source_tree != V210_SOURCE_TREE
        or report.decision != v210_models.DECISION
        or decision.decision != v210_models.DECISION
        or not gate.all_gates_passed
        or transition.next_stage != models.CONSUMED_STAGE
        or any((report.provider_calls, report.credential_lookups, report.empirical_rows))
    ):
        _fail("freeze.v210_semantics", "v26.210 authority differs")
    return cast(
        models.V210AuthorityFreeze,
        _make(
            models.V210AuthorityFreeze,
            {
                "external_decision_id": external_decision_id,
                "v210_report_id": report.report_id,
                "v210_decision_id": decision.decision_id,
                "v210_gate_id": gate.gate_id,
                "v210_transition_id": transition.transition_id,
                "v210_artifact_manifest_id": artifact.manifest_id,
                "v210_artifact_root": artifact.artifact_root,
                "v210_source_commit": source.source_commit,
                "v210_source_tree": source.source_tree,
                "v210_decision": report.decision,
            },
            "freeze_id",
            "finance_v26_211_v210_authority_freeze:",
        ),
    )


def _frozen_condition(
    *,
    repository_root: Path,
    freeze: models.V210AuthorityFreeze,
) -> models.FrozenExecutionConditionBinding:
    root = repository_root / V209_DIR
    artifact = v209_models.ArtifactManifest.model_validate(_load(root / "artifact_manifest.json"))
    if _verify_manifest(root, artifact) != (21, 44_916_386):
        _fail("condition.v209_geometry", "v26.209 formal geometry differs")
    source = v209_models.SourceIdentity.model_validate(_load(root / "source_identity.json"))
    implementation = v209_models.ImplementationBinding.model_validate(
        _load(root / "implementation_binding.json")
    )
    catalog = v209_models.ExecutableRunnerPackageCatalog.model_validate(
        _load(root / "executable_runner_package_catalog.json")
    )
    manifest = v209_models.ExecutableDevelopmentManifest.model_validate(
        _load(root / "executable_development_manifest.json")
    )
    runner = v209_models.ExecutableRunnerContract.model_validate(
        _load(root / "executable_runner_contract.json")
    )
    execution = v209_models.ExecutableExecutionContract.model_validate(
        _load(root / "executable_execution_contract.json")
    )
    failures = v209_models.TypedFailureControlAudit.model_validate(
        _load(root / "typed_failure_control_audit.json")
    )
    geometry = v210_models.IndependentCallsiteGeometryAudit.model_validate(
        _load(repository_root / V210_DIR / "independent_callsite_geometry_audit.json")
    )
    profile = _load(repository_root / V192_DIR / "json_explicit_generation_profile.json")
    prompt_contract = _load(repository_root / V192_DIR / "json_explicit_prompt_contract.json")
    prompt_schema = _load(repository_root / V192_DIR / "json_explicit_prompt_schema.json")
    estimand = v206_models.ProspectiveEstimandContract.model_validate(
        _load(repository_root / V206_DIR / "prospective_estimand_contract.json")
    )
    model_profile = (repository_root / MODEL_PROFILE).read_bytes()
    packages = tuple(sorted(item.package_id for item in catalog.packages))
    jobs = tuple(sorted(item.job_id for item in manifest.jobs))
    namespaces = {
        field: tuple(sorted(getattr(item, field) for item in manifest.jobs))
        for field in (
            "raw_namespace",
            "result_namespace",
            "trace_namespace",
            "outcome_namespace",
        )
    }
    if (
        source.source_commit != V209_SOURCE_COMMIT
        or source.source_tree != V209_SOURCE_TREE
        or implementation.source_commit != V209_SOURCE_COMMIT
        or implementation.source_tree != V209_SOURCE_TREE
        or len(packages) != 32
        or len(set(packages)) != 32
        or len(jobs) != 192
        or len(set(jobs)) != 192
        or any(len(set(values)) != 192 for values in namespaces.values())
        or geometry.exact_coordinate_count != 792
        or geometry.source_parent_match_count != 792
        or runner.manifest_id != manifest.manifest_id
        or execution.runner_id != runner.runner_id
        or execution.manifest_id != manifest.manifest_id
        or execution.package_catalog_id != catalog.catalog_id
        or execution.online_execution_authorized
    ):
        _fail("condition.parents", "frozen repaired execution condition differs")
    return cast(
        models.FrozenExecutionConditionBinding,
        _make(
            models.FrozenExecutionConditionBinding,
            {
                "v210_freeze_id": freeze.freeze_id,
                "v209_source_commit": source.source_commit,
                "v209_source_tree": source.source_tree,
                "implementation_id": implementation.implementation_id,
                "package_catalog_id": catalog.catalog_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "execution_contract_id": execution.contract_id,
                "repair_profile_id": execution.repair_profile_id,
                "estimand_contract_id": estimand.contract_id,
                "typed_failure_control_audit_id": failures.audit_id,
                "generation_profile_id": profile["profile_id"],
                "prompt_contract_id": prompt_contract["contract_id"],
                "prompt_schema_id": prompt_schema["schema_id"],
                "model_config_id": profile["model_config_id"],
                "model_profile_sha256": _sha(model_profile),
                "thinking_policy_id": profile["thinking_policy_id"],
                "action_grammar_id": profile["action_grammar_id"],
                "final_grammar_id": profile["final_grammar_id"],
                "bounded_generation_policy_id": profile["bounded_generation_policy_id"],
                "generation_resource_contract_id": profile["resource_contract_id"],
                "kernel_resource_contract_id": execution.resource_contract_id,
                "exact_package_ids": packages,
                "exact_job_ids": jobs,
                "exact_package_set_sha256": models.canonical_sha256(packages),
                "exact_job_set_sha256": models.canonical_sha256(jobs),
                "exact_coordinate_set_sha256": geometry.coordinate_set_sha256,
                "raw_namespace_set_sha256": models.canonical_sha256(namespaces["raw_namespace"]),
                "result_namespace_set_sha256": models.canonical_sha256(
                    namespaces["result_namespace"]
                ),
                "trace_namespace_set_sha256": models.canonical_sha256(
                    namespaces["trace_namespace"]
                ),
                "outcome_namespace_set_sha256": models.canonical_sha256(
                    namespaces["outcome_namespace"]
                ),
            },
            "binding_id",
            "finance_v26_211_frozen_execution_condition_binding:",
        ),
    )


def _composition(
    condition: models.FrozenExecutionConditionBinding,
) -> models.OnlineExecutionCompositionContract:
    return cast(
        models.OnlineExecutionCompositionContract,
        _make(
            models.OnlineExecutionCompositionContract,
            {
                "condition_binding_id": condition.binding_id,
                "exact_v26_209_runner_id": condition.runner_id,
                "exact_v26_209_implementation_id": condition.implementation_id,
            },
            "contract_id",
            "fresh_repaired_full_condition_online_execution_composition_contract:",
        ),
    )


def _online_authorization(
    *,
    external: models.ExternalOnlineAuthorizationDecision,
    freeze: models.V210AuthorityFreeze,
    condition: models.FrozenExecutionConditionBinding,
    composition: models.OnlineExecutionCompositionContract,
) -> models.ExactOnlineExecutionAuthorization:
    return cast(
        models.ExactOnlineExecutionAuthorization,
        _make(
            models.ExactOnlineExecutionAuthorization,
            {
                "external_decision_id": external.decision_id,
                "v210_freeze_id": freeze.freeze_id,
                "condition_binding_id": condition.binding_id,
                "composition_contract_id": composition.contract_id,
                "implementation_id": condition.implementation_id,
                "package_catalog_id": condition.package_catalog_id,
                "manifest_id": condition.manifest_id,
                "runner_id": condition.runner_id,
                "execution_contract_id": condition.execution_contract_id,
                "repair_profile_id": condition.repair_profile_id,
                "estimand_contract_id": condition.estimand_contract_id,
                "terminal_policy_parent_id": condition.typed_failure_control_audit_id,
                "generation_profile_id": condition.generation_profile_id,
                "prompt_contract_id": condition.prompt_contract_id,
                "prompt_schema_id": condition.prompt_schema_id,
                "model_config_id": condition.model_config_id,
                "thinking_policy_id": condition.thinking_policy_id,
                "action_grammar_id": condition.action_grammar_id,
                "final_grammar_id": condition.final_grammar_id,
                "bounded_generation_policy_id": condition.bounded_generation_policy_id,
                "generation_resource_contract_id": condition.generation_resource_contract_id,
                "kernel_resource_contract_id": condition.kernel_resource_contract_id,
                "exact_job_ids": condition.exact_job_ids,
                "exact_job_set_sha256": condition.exact_job_set_sha256,
                "exact_coordinate_set_sha256": condition.exact_coordinate_set_sha256,
                "raw_namespace_set_sha256": condition.raw_namespace_set_sha256,
                "result_namespace_set_sha256": condition.result_namespace_set_sha256,
                "trace_namespace_set_sha256": condition.trace_namespace_set_sha256,
                "outcome_namespace_set_sha256": condition.outcome_namespace_set_sha256,
            },
            "authorization_id",
            "fresh_repaired_full_condition_exact_online_execution_authorization:",
        ),
    )


def _request_arguments(
    authorization: models.ExactOnlineExecutionAuthorization,
) -> dict[str, Any]:
    return {
        "authorization": authorization,
        "authorization_bytes": models.canonical_bytes(authorization),
        "requested_stage": authorization.authorized_stage,
        "requested_manifest_id": authorization.manifest_id,
        "requested_job_ids": authorization.exact_job_ids,
        "requested_runner_id": authorization.runner_id,
        "requested_execution_contract_id": authorization.execution_contract_id,
        "requested_composition_contract_id": authorization.composition_contract_id,
        "requested_coordinate_set_sha256": authorization.exact_coordinate_set_sha256,
        "requested_generation_profile_id": authorization.generation_profile_id,
        "requested_model_config_id": authorization.model_config_id,
        "requested_thinking_policy_id": authorization.thinking_policy_id,
        "requested_action_grammar_id": authorization.action_grammar_id,
        "requested_final_grammar_id": authorization.final_grammar_id,
        "requested_policy_id": authorization.bounded_generation_policy_id,
        "requested_generation_resource_contract_id": (
            authorization.generation_resource_contract_id
        ),
        "requested_kernel_resource_contract_id": authorization.kernel_resource_contract_id,
        "provider_execution_requested": True,
        "replacement_run_requested": False,
        "failed_job_rerun_requested": False,
        "recovery_run_requested": False,
        "historical_reuse_requested": False,
        "qa_integration_requested": False,
        "caller_terminal_provided": False,
        "historical_response_provided": False,
        "reference_choice_vector_provided": False,
        "prebuilt_final_provided": False,
    }


def _prepare_online_entry(
    *,
    guard: models.PrecredentialOnlineAuthorizationGuard,
    request: dict[str, Any],
    credential_boundary_probe: Any,
    transport_factory: Any,
    raw_writer_factory: Any,
    result_writer_factory: Any,
    outcome_writer_factory: Any,
    checkpoint_writer_factory: Any,
) -> models.OnlineAuthorizationAdmission:
    admission = guard.admit(**request)
    credential_boundary_probe()
    transport_factory()
    raw_writer_factory()
    result_writer_factory()
    outcome_writer_factory()
    checkpoint_writer_factory()
    return admission


def _admission_control(
    *,
    name: str,
    guard: models.PrecredentialOnlineAuthorizationGuard,
    request: dict[str, Any],
) -> tuple[models.AdmissionControl, models.OnlineAuthorizationAdmission | None]:
    counts = {
        "credential": 0,
        "transport": 0,
        "raw": 0,
        "result": 0,
        "outcome": 0,
        "checkpoint": 0,
    }

    def probe(key: str) -> object:
        counts[key] += 1
        return object()

    admission: models.OnlineAuthorizationAdmission | None = None
    reason_sha: str | None = None
    try:
        admission = _prepare_online_entry(
            guard=guard,
            request=request,
            credential_boundary_probe=lambda: probe("credential"),
            transport_factory=lambda: probe("transport"),
            raw_writer_factory=lambda: probe("raw"),
            result_writer_factory=lambda: probe("result"),
            outcome_writer_factory=lambda: probe("outcome"),
            checkpoint_writer_factory=lambda: probe("checkpoint"),
        )
    except (TypeError, ValueError) as exc:
        reason_sha = _sha(str(exc).encode("utf-8"))
    admitted = admission is not None
    control = cast(
        models.AdmissionControl,
        _make(
            models.AdmissionControl,
            {
                "control_name": name,
                "admitted": admitted,
                "rejected": not admitted,
                "rejection_reason_sha256": reason_sha,
                "credential_probe_count": counts["credential"],
                "transport_factory_count": counts["transport"],
                "raw_writer_factory_count": counts["raw"],
                "result_writer_factory_count": counts["result"],
                "outcome_writer_factory_count": counts["outcome"],
                "checkpoint_writer_factory_count": counts["checkpoint"],
            },
            "control_id",
            "finance_v26_211_precredential_admission_control:",
        ),
    )
    return control, admission


def _admission_audit(
    authorization: models.ExactOnlineExecutionAuthorization,
) -> tuple[models.OnlineAuthorizationAdmission, models.PrecredentialAdmissionAudit]:
    authorization_bytes = models.canonical_bytes(authorization)
    guard = models.PrecredentialOnlineAuthorizationGuard(
        expected_authorization=authorization,
        expected_authorization_bytes=authorization_bytes,
    )
    source = inspect.getsource(_prepare_online_entry)
    labels = (
        "guard.admit",
        "credential_boundary_probe()",
        "transport_factory()",
        "raw_writer_factory()",
        "result_writer_factory()",
        "outcome_writer_factory()",
        "checkpoint_writer_factory()",
    )
    positions = tuple(source.find(label) for label in labels)
    if min(positions) < 0 or positions != tuple(sorted(positions)):
        _fail("admission.order", "precredential guard does not precede every post-guard probe")
    exact = _request_arguments(authorization)
    self_declared = authorization.model_construct(authorization_id="self_declared")
    changed_jobs = list(authorization.exact_job_ids)
    changed_jobs[0] = (
        "fresh_repaired_final_continuity_executable_full_condition_development_job:" + "f" * 64
    )
    invalid = (
        ("missing_authorization", {**exact, "authorization": None}),
        ("missing_authorization_bytes", {**exact, "authorization_bytes": None}),
        (
            "modified_authorization_bytes",
            {**exact, "authorization_bytes": authorization_bytes + b" "},
        ),
        ("self_declared_authorization", {**exact, "authorization": self_declared}),
        ("changed_stage", {**exact, "requested_stage": "changed.stage"}),
        ("changed_manifest", {**exact, "requested_manifest_id": "changed.manifest"}),
        ("changed_job_set", {**exact, "requested_job_ids": tuple(sorted(changed_jobs))}),
        ("changed_runner", {**exact, "requested_runner_id": "changed.runner"}),
        (
            "changed_execution_contract",
            {**exact, "requested_execution_contract_id": "changed.execution"},
        ),
        (
            "changed_composition_contract",
            {**exact, "requested_composition_contract_id": "changed.composition"},
        ),
        (
            "changed_coordinate_set",
            {**exact, "requested_coordinate_set_sha256": "f" * 64},
        ),
        ("changed_model", {**exact, "requested_model_config_id": "changed.model"}),
        ("changed_thinking", {**exact, "requested_thinking_policy_id": "changed.thinking"}),
        ("changed_action_grammar", {**exact, "requested_action_grammar_id": "changed.action"}),
        ("changed_final_grammar", {**exact, "requested_final_grammar_id": "changed.final"}),
        ("changed_policy", {**exact, "requested_policy_id": "changed.policy"}),
        (
            "changed_generation_resource",
            {**exact, "requested_generation_resource_contract_id": "changed.resource"},
        ),
        (
            "changed_kernel_resource",
            {**exact, "requested_kernel_resource_contract_id": "changed.kernel"},
        ),
        ("provider_execution_absent", {**exact, "provider_execution_requested": False}),
        ("replacement_run", {**exact, "replacement_run_requested": True}),
        ("failed_job_rerun", {**exact, "failed_job_rerun_requested": True}),
        ("recovery_run", {**exact, "recovery_run_requested": True}),
        ("historical_reuse", {**exact, "historical_reuse_requested": True}),
        ("qa_integration", {**exact, "qa_integration_requested": True}),
        ("caller_terminal", {**exact, "caller_terminal_provided": True}),
        ("historical_response", {**exact, "historical_response_provided": True}),
        ("reference_choice_vector", {**exact, "reference_choice_vector_provided": True}),
        ("prebuilt_final", {**exact, "prebuilt_final_provided": True}),
    )
    legal, admission = _admission_control(
        name="exact_online_authorization",
        guard=guard,
        request=exact,
    )
    if admission is None:
        _fail("admission.legal", "exact repaired online authorization did not admit")
    controls = [legal]
    for name, request in invalid:
        control, result = _admission_control(name=name, guard=guard, request=request)
        if result is not None:
            _fail("admission.invalid", f"invalid online request admitted:{name}")
        controls.append(control)
    audit = cast(
        models.PrecredentialAdmissionAudit,
        _make(
            models.PrecredentialAdmissionAudit,
            {
                "authorization_id": authorization.authorization_id,
                "admission_id": admission.admission_id,
                "controls": tuple(controls),
                "invalid_control_count": len(invalid),
            },
            "audit_id",
            "finance_v26_211_precredential_admission_audit:",
        ),
    )
    return admission, audit


def _rehash_authorization(
    authorization: models.ExactOnlineExecutionAuthorization,
    updates: dict[str, Any],
) -> models.ExactOnlineExecutionAuthorization:
    values = authorization.model_dump(mode="python", warnings=False)
    values.pop("authorization_id")
    values.update(updates)
    return cast(
        models.ExactOnlineExecutionAuthorization,
        _make(
            models.ExactOnlineExecutionAuthorization,
            values,
            "authorization_id",
            "fresh_repaired_full_condition_exact_online_execution_authorization:",
        ),
    )


def _destructive_audit(
    authorization: models.ExactOnlineExecutionAuthorization,
) -> models.DestructiveAudit:
    changed_jobs = list(authorization.exact_job_ids)
    changed_jobs[0] = (
        "fresh_repaired_final_continuity_executable_full_condition_development_job:" + "e" * 64
    )
    changed_job_tuple = tuple(sorted(changed_jobs))
    mutations = (
        ("manifest_parent", {"manifest_id": "attack.manifest"}),
        ("runner_parent", {"runner_id": "attack.runner"}),
        ("execution_contract_parent", {"execution_contract_id": "attack.execution"}),
        ("composition_contract_parent", {"composition_contract_id": "attack.composition"}),
        (
            "job_set",
            {
                "exact_job_ids": changed_job_tuple,
                "exact_job_set_sha256": models.canonical_sha256(changed_job_tuple),
            },
        ),
        ("coordinate_set", {"exact_coordinate_set_sha256": "e" * 64}),
        ("raw_namespace_set", {"raw_namespace_set_sha256": "e" * 64}),
        ("result_namespace_set", {"result_namespace_set_sha256": "e" * 64}),
        ("trace_namespace_set", {"trace_namespace_set_sha256": "e" * 64}),
        ("outcome_namespace_set", {"outcome_namespace_set_sha256": "e" * 64}),
        ("model_parent", {"model_config_id": "attack.model"}),
        ("thinking_parent", {"thinking_policy_id": "attack.thinking"}),
        ("action_grammar_parent", {"action_grammar_id": "attack.action"}),
        ("final_grammar_parent", {"final_grammar_id": "attack.final"}),
        ("policy_parent", {"bounded_generation_policy_id": "attack.policy"}),
        ("generation_resource_parent", {"generation_resource_contract_id": "attack.resource"}),
        ("kernel_resource_parent", {"kernel_resource_contract_id": "attack.kernel"}),
        ("terminal_policy_parent", {"terminal_policy_parent_id": "attack.terminal"}),
        ("estimand_parent", {"estimand_contract_id": "attack.estimand"}),
        ("prompt_contract_parent", {"prompt_contract_id": "attack.prompt"}),
    )
    guard = models.PrecredentialOnlineAuthorizationGuard(
        expected_authorization=authorization,
        expected_authorization_bytes=models.canonical_bytes(authorization),
    )
    controls: list[models.DestructiveControl] = []
    for name, updates in mutations:
        mutant = _rehash_authorization(authorization, updates)
        control, admission = _admission_control(
            name=f"fully_rehashed_{name}",
            guard=guard,
            request=_request_arguments(mutant),
        )
        post_guard = sum(
            (
                control.credential_probe_count,
                control.transport_factory_count,
                control.raw_writer_factory_count,
                control.result_writer_factory_count,
                control.outcome_writer_factory_count,
                control.checkpoint_writer_factory_count,
            )
        )
        if admission is not None or post_guard:
            _fail("destructive", f"fully rehashed attack reached post-guard probe:{name}")
        controls.append(
            cast(
                models.DestructiveControl,
                _make(
                    models.DestructiveControl,
                    {
                        "control_name": name,
                        "mutated_authorization_id": mutant.authorization_id,
                    },
                    "control_id",
                    "finance_v26_211_authorization_destructive_control:",
                ),
            )
        )
    return cast(
        models.DestructiveAudit,
        _make(
            models.DestructiveAudit,
            {
                "authorization_id": authorization.authorization_id,
                "controls": tuple(controls),
                "attack_count": len(controls),
                "fully_rehashed_attack_count": len(controls),
                "rejected_attack_count": len(controls),
            },
            "audit_id",
            "finance_v26_211_authorization_destructive_audit:",
        ),
    )


def _gate(name: str, evidence_id: str) -> models.GateResult:
    return cast(
        models.GateResult,
        _make(
            models.GateResult,
            {"gate_name": name, "evidence_id": evidence_id},
            "gate_id",
            "finance_v26_211_online_authorization_gate:",
        ),
    )


def _source(value: tuple[str, str]) -> models.SourceIdentity:
    return cast(
        models.SourceIdentity,
        _make(
            models.SourceIdentity,
            {
                "source_commit": value[0],
                "source_tree": value[1],
                "implementation_files": IMPLEMENTATION_FILES,
            },
            "source_identity_id",
            "finance_v26_211_source_identity:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.OnlineAuthorizationReport:
    if output_dir.exists():
        raise FileExistsError(f"v26.211 output already exists:{output_dir}")
    external, review_bytes, directive_bytes = _external_decision(external_review_path)
    freeze = _v210_freeze(
        repository_root=repository_root,
        external_decision_id=external.decision_id,
    )
    condition = _frozen_condition(repository_root=repository_root, freeze=freeze)
    composition = _composition(condition)
    authorization = _online_authorization(
        external=external,
        freeze=freeze,
        condition=condition,
        composition=composition,
    )
    admission, admission_audit = _admission_audit(authorization)
    destructive = _destructive_audit(authorization)
    scope = cast(
        models.ScopeBoundaryAudit,
        _make(
            models.ScopeBoundaryAudit,
            {"authorization_id": authorization.authorization_id},
            "audit_id",
            "finance_v26_211_scope_boundary_audit:",
        ),
    )
    gates = (
        _gate("exact_external_v26_210_audit_decision", external.decision_id),
        _gate("v26_210_exact_15_file_authority", freeze.freeze_id),
        _gate("v26_210_exact_report_decision_gate_transition", freeze.freeze_id),
        _gate("v26_210_source_commit_tree", freeze.freeze_id),
        _gate("exact_v26_209_source_and_implementation", condition.binding_id),
        _gate("exact_32_package_condition", condition.binding_id),
        _gate("exact_192_job_manifest", condition.binding_id),
        _gate("exact_792_registered_coordinates", condition.binding_id),
        _gate("exact_raw_result_trace_outcome_namespaces", condition.binding_id),
        _gate("exact_task_component_candidate_schedule_presentation", condition.binding_id),
        _gate("exact_runtime_and_terminal_policy", condition.binding_id),
        _gate("exact_model_thinking_sampling", condition.binding_id),
        _gate("exact_action_and_final_grammars", condition.binding_id),
        _gate("exact_policy_and_resource_contracts", condition.binding_id),
        _gate("exact_correction_validity_denominator_threshold", condition.binding_id),
        _gate("exact_online_execution_composition", composition.contract_id),
        _gate("authorization_exactly_once_before_credentials", composition.contract_id),
        _gate("durable_run_start_receipt_required", composition.contract_id),
        _gate("exact_runner_current_state_loop", composition.contract_id),
        _gate("raw_before_result_trace_outcome_checkpoint", composition.contract_id),
        _gate("caller_terminal_and_prefabricated_inputs_forbidden", composition.contract_id),
        _gate("failure_does_not_reopen_authorization", composition.contract_id),
        _gate("exact_content_addressed_authorization", authorization.authorization_id),
        _gate("exact_request_admits_before_post_guard_probes", admission.admission_id),
        _gate("invalid_requests_reject_before_post_guard_probes", admission_audit.audit_id),
        _gate("fully_rehashed_authorization_attacks_reject", destructive.audit_id),
        _gate("authorization_issued_not_consumed", scope.audit_id),
        _gate("provider_and_credential_calls_zero", scope.audit_id),
        _gate("empirical_and_downstream_rows_zero", scope.audit_id),
        _gate("qa_integration_forbidden", scope.audit_id),
    )
    static = cast(
        models.StaticAudit,
        _make(
            models.StaticAudit,
            {"gates": gates, "passed_gate_count": len(gates)},
            "audit_id",
            "finance_v26_211_online_authorization_static_audit:",
        ),
    )
    decision = cast(
        models.OnlineAuthorizationDecision,
        _make(
            models.OnlineAuthorizationDecision,
            {
                "external_decision_id": external.decision_id,
                "v210_freeze_id": freeze.freeze_id,
                "condition_binding_id": condition.binding_id,
                "composition_contract_id": composition.contract_id,
                "authorization_id": authorization.authorization_id,
                "admission_audit_id": admission_audit.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "static_audit_id": static.audit_id,
            },
            "decision_id",
            "finance_v26_211_online_authorization_decision:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        _make(
            models.ProspectiveTransition,
            {
                "decision_id": decision.decision_id,
                "authorization_id": authorization.authorization_id,
            },
            "transition_id",
            "finance_v26_211_transition:",
        ),
    )
    source = _source(source_identity)
    report = cast(
        models.OnlineAuthorizationReport,
        _make(
            models.OnlineAuthorizationReport,
            {
                "run_id": RUN_ID,
                "source_identity_id": source.source_identity_id,
                "external_decision_id": external.decision_id,
                "v210_freeze_id": freeze.freeze_id,
                "condition_binding_id": condition.binding_id,
                "composition_contract_id": composition.contract_id,
                "authorization_id": authorization.authorization_id,
                "admission_id": admission.admission_id,
                "admission_audit_id": admission_audit.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "static_audit_id": static.audit_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
            },
            "report_id",
            "finance_v26_211_online_authorization_report:",
        ),
    )
    payloads = {
        "external_review.txt": review_bytes,
        "operator_authorization.txt": directive_bytes,
        "external_online_authorization_decision.json": _bytes(external),
        "v210_authority_freeze.json": _bytes(freeze),
        "frozen_execution_condition_binding.json": _bytes(condition),
        "online_execution_composition_contract.json": _bytes(composition),
        "exact_online_execution_authorization.json": _bytes(authorization),
        "online_authorization_admission.json": _bytes(admission),
        "precredential_admission_audit.json": _bytes(admission_audit),
        "authorization_destructive_audit.json": _bytes(destructive),
        "scope_boundary_audit.json": _bytes(scope),
        "static_audit.json": _bytes(static),
        "online_authorization_decision.json": _bytes(decision),
        "prospective_transition.json": _bytes(transition),
        "source_identity.json": _bytes(source),
        "report.json": _bytes(report),
    }
    artifact = models.artifact_manifest(RUN_ID, payloads)
    payloads["artifact_manifest.json"] = _bytes(artifact)
    for name, payload in sorted(payloads.items()):
        _write(output_dir / name, payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-review", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    report = build(
        repository_root=args.repository_root.resolve(),
        output_dir=args.output_dir.resolve(),
        external_review_path=args.external_review.resolve(),
        source_identity=(args.source_commit, args.source_tree),
    )
    print(models.canonical_bytes(report).decode("utf-8"))


if __name__ == "__main__":
    main()
