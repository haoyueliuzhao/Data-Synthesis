# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from trusted_synthesis.core.task import fresh_artifact_backed_outcome_authority as outcome_authority
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_online_execution as v188,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_exact_online_execution_authorization_models as v211_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight as v209,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_models as v212_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_runtime as v212_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_observation_derived_terminal_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_observation_derived_terminal_runtime as runtime,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = (
    "finance_v26_213_fresh_repaired_full_condition_observation_derived_terminal_"
    "single_consumer_path_repair_preflight_v1_20260902"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
REVIEW_SHA256: Final = "941b3137f2d0823ef1ec681c4364ee6d6aca242d9edc9d35b1b3dfdbea8396a9"
REVIEW_BYTES: Final = 16_582
OPERATOR_DIRECTIVE: Final = "参照审计报告继续实验修订"
V212_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_212_fresh_repaired_full_condition_exact_online_execution_"
    "consumer_terminal_persistence_integration_preflight_v1_20260902"
)
V211_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_211_fresh_repaired_full_condition_exact_192_job_"
    "online_execution_authorization_v1_20260902"
)
V209_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_209_fresh_repaired_full_condition_executable_runner_"
    "final_request_contract_continuity_repair_preflight_v1_20260902"
)
V195_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_195_fresh_artifact_backed_outcome_authority_preflight_v1_20260901"
)
MODEL_PROFILE: Final = (
    "trusted_data_synthesis/config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
)
V212_SOURCE_COMMIT: Final = "9173b16cc1340449fa18b4030b8d2c7686fa3b5f"
V212_SOURCE_TREE: Final = "2b3562714d70b587c4ef1424e15885e5f1e92880"
RUNTIME_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_observation_derived_terminal_runtime.py"
)
IMPLEMENTATION_FILES: Final = tuple(
    sorted(
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_observation_derived_terminal_models.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_observation_derived_terminal_runtime.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_observation_derived_terminal_preflight.py",
            "trusted_data_synthesis/tests/"
            "test_v26_fresh_repaired_observation_derived_terminal_preflight.py",
        )
    )
)
SYMBOLS: Final = (
    (
        runtime.ObservationDerivedTerminalDispatcher.dispatch,
        "ObservationDerivedTerminalDispatcher.dispatch",
    ),
    (
        runtime.ObservationBoundPersistencePipeline.persist,
        "ObservationBoundPersistencePipeline.persist",
    ),
    (runtime.SingleConsumerParentGuard.admit, "SingleConsumerParentGuard.admit"),
    (
        runtime.RepairedOnlineExecutionConsumer.execute_preflight,
        "RepairedOnlineExecutionConsumer.execute_preflight",
    ),
    (runtime._execute_manifest_main_path, "_execute_manifest_main_path"),
    (runtime._diagnostic_evidences, "_diagnostic_evidences"),
)


class V213Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V213Error(stage, reason)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _bytes(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _write(path: Path, payload: bytes) -> None:
    v212_runtime._durable_write_no_replace(path, payload)


def _git(repository_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ("git", *args),
        cwd=repository_root,
        check=False,
        capture_output=True,
    )
    if completed.returncode:
        _fail("source.git", completed.stderr.decode("utf-8", errors="replace"))
    return completed.stdout


def _external_authorization(
    review_path: Path,
) -> tuple[models.ExternalRevisionAuthorization, bytes, bytes]:
    review = review_path.read_bytes()
    if len(review) != REVIEW_BYTES or _sha(review) != REVIEW_SHA256:
        _fail("authorization.review", "v26.213 external review bytes differ")
    directive = OPERATOR_DIRECTIVE.encode("utf-8")
    authorization = cast(
        models.ExternalRevisionAuthorization,
        models.make_identity(
            models.ExternalRevisionAuthorization,
            {
                "review_sha256": _sha(review),
                "review_byte_count": len(review),
                "operator_directive_sha256": _sha(directive),
                "operator_directive_byte_count": len(directive),
            },
            field="authorization_id",
            prefix="finance_v26_213_external_revision_authorization:",
        ),
    )
    return authorization, review, directive


def _v212_freeze(
    *,
    repository_root: Path,
    external_authorization_id: str,
) -> models.V212Freeze:
    root = repository_root / V212_DIR
    artifact = v212_models.ArtifactManifest.model_validate(_load(root / "artifact_manifest.json"))
    files = tuple(sorted(path for path in root.rglob("*") if path.is_file()))
    members = {item.relative_path: item for item in artifact.members}
    actual_names = {
        path.relative_to(root).as_posix() for path in files if path.name != "artifact_manifest.json"
    }
    if set(members) != actual_names:
        _fail("freeze.paths", "v26.212 formal path set differs")
    for name, member in members.items():
        payload = (root / name).read_bytes()
        if len(payload) != member.byte_count or _sha(payload) != member.sha256:
            _fail("freeze.bytes", f"v26.212 formal member differs:{name}")
    if (
        len(files) != 1_067
        or sum(path.stat().st_size for path in files) != 2_239_071
        or artifact.file_count != 1_066
        or artifact.total_byte_count != 2_017_584
        or artifact.artifact_root
        != "finance_v26_212_artifact_root:38bf8efc1d0b1e1ca55d91deef759b02974e26163d192be52897a3e1d79de3c2"
    ):
        _fail("freeze.geometry", "v26.212 formal geometry differs")
    report = v212_models.RepairReport.model_validate(_load(root / "report.json"))
    decision = v212_models.RepairDecision.model_validate(_load(root / "repair_decision.json"))
    transition = v212_models.ProspectiveTransition.model_validate(
        _load(root / "prospective_transition.json")
    )
    consumer = v212_models.OnlineExecutionConsumerImplementationBinding.model_validate(
        _load(root / "online_execution_consumer_implementation_binding.json")
    )
    composition = v212_models.RepairedCompositionContract.model_validate(
        _load(root / "repaired_composition_contract.json")
    )
    source = v212_models.SourceIdentity.model_validate(_load(root / "source_identity.json"))
    if (
        report.decision_id != decision.decision_id
        or report.transition_id != transition.transition_id
        or report.consumer_binding_id != consumer.binding_id
        or report.composition_contract_id != composition.contract_id
        or source.source_commit != V212_SOURCE_COMMIT
        or source.source_tree != V212_SOURCE_TREE
        or report.current_v211_authorization_consumed
        or report.provider_calls != 0
    ):
        _fail("freeze.semantics", "v26.212 formal authority differs")
    return cast(
        models.V212Freeze,
        models.make_identity(
            models.V212Freeze,
            {
                "external_authorization_id": external_authorization_id,
                "v212_report_id": report.report_id,
                "v212_decision_id": decision.decision_id,
                "v212_transition_id": transition.transition_id,
                "v212_consumer_binding_id": consumer.binding_id,
                "v212_composition_contract_id": composition.contract_id,
                "v212_artifact_manifest_id": artifact.manifest_id,
                "v212_artifact_root": artifact.artifact_root,
                "v212_source_commit": source.source_commit,
                "v212_source_tree": source.source_tree,
            },
            field="freeze_id",
            prefix="finance_v26_213_v212_freeze:",
        ),
    )


def _source_identity(value: tuple[str, str]) -> models.SourceIdentity:
    return cast(
        models.SourceIdentity,
        models.make_identity(
            models.SourceIdentity,
            {
                "source_commit": value[0],
                "source_tree": value[1],
                "implementation_files": IMPLEMENTATION_FILES,
            },
            field="source_identity_id",
            prefix="finance_v26_213_source_identity:",
        ),
    )


def _implementation_binding(
    *,
    repository_root: Path,
    external_authorization_id: str,
    freeze_id: str,
    source: models.SourceIdentity,
) -> models.ImplementationBinding:
    if source.source_commit != "1" * 40:
        tree = (
            _git(repository_root, "rev-parse", f"{source.source_commit}^{{tree}}").decode().strip()
        )
        if tree != source.source_tree:
            _fail("source.tree", "v26.213 source tree differs")
    files: list[models.SourceBinding] = []
    for relative in IMPLEMENTATION_FILES:
        live = (repository_root / relative).read_bytes()
        if source.source_commit != "1" * 40:
            committed = _git(repository_root, "show", f"{source.source_commit}:{relative}")
            if committed != live:
                _fail("source.file", f"v26.213 live source differs:{relative}")
        files.append(
            models.SourceBinding(
                relative_path=relative,
                symbol="<file>",
                sha256=_sha(live),
                byte_count=len(live),
            )
        )
    symbols = tuple(
        models.SourceBinding(
            relative_path=RUNTIME_FILE,
            symbol=name,
            sha256=_sha(inspect.getsource(symbol).encode("utf-8")),
            byte_count=len(inspect.getsource(symbol).encode("utf-8")),
        )
        for symbol, name in SYMBOLS
    )
    dispatcher_parameters = inspect.signature(
        runtime.ObservationDerivedTerminalDispatcher.dispatch
    ).parameters
    terminal_parameters = sum("terminal" in name for name in dispatcher_parameters)
    runtime_source = (repository_root / RUNTIME_FILE).read_text(encoding="utf-8")
    forbidden = ("os.environ", "os.getenv", "requests.", "urllib.", "httpx.", "socket.")
    if terminal_parameters or any(item in runtime_source for item in forbidden):
        _fail("source.interface", "v26.213 source exposes prohibited terminal/network input")
    return cast(
        models.ImplementationBinding,
        models.make_identity(
            models.ImplementationBinding,
            {
                "external_authorization_id": external_authorization_id,
                "v212_freeze_id": freeze_id,
                "source_commit": source.source_commit,
                "source_tree": source.source_tree,
                "files": tuple(files),
                "symbols": symbols,
            },
            field="binding_id",
            prefix="fresh_repaired_observation_derived_terminal_implementation_binding:",
        ),
    )


def _symbol_sha(binding: models.ImplementationBinding, name: str) -> str:
    values = tuple(item.sha256 for item in binding.symbols if item.symbol == name)
    if len(values) != 1:
        _fail("source.symbol", f"v26.213 symbol binding differs:{name}")
    return values[0]


def _load_v209(
    repository_root: Path,
) -> tuple[
    v209_models.ImplementationBinding,
    v209_models.ExecutableDevelopmentManifest,
    v209_models.ExecutableRunnerContract,
    v209_models.ExecutableExecutionContract,
    v209_models.ExecutableInvocationCensus,
    v209_models.FullConditionExecutionControlAudit,
]:
    root = repository_root / V209_DIR
    return (
        v209_models.ImplementationBinding.model_validate(
            _load(root / "implementation_binding.json")
        ),
        v209_models.ExecutableDevelopmentManifest.model_validate(
            _load(root / "executable_development_manifest.json")
        ),
        v209_models.ExecutableRunnerContract.model_validate(
            _load(root / "executable_runner_contract.json")
        ),
        v209_models.ExecutableExecutionContract.model_validate(
            _load(root / "executable_execution_contract.json")
        ),
        v209_models.ExecutableInvocationCensus.model_validate(
            _load(root / "executable_invocation_census.json")
        ),
        v209_models.FullConditionExecutionControlAudit.model_validate(
            _load(root / "full_condition_execution_control_audit.json")
        ),
    )


def _bindings(
    *,
    repository_root: Path,
    implementation: models.ImplementationBinding,
    freeze: models.V212Freeze,
    v209_implementation: v209_models.ImplementationBinding,
    manifest: v209_models.ExecutableDevelopmentManifest,
    runner: v209_models.ExecutableRunnerContract,
    execution: v209_models.ExecutableExecutionContract,
    v211_authorization: v211_models.ExactOnlineExecutionAuthorization,
    registry: outcome_authority.FreshTerminalRegistry,
) -> tuple[
    models.ObservationDerivedDispatcherBinding,
    models.ObservationBoundPersistenceBinding,
    models.SingleConsumerImplementationBinding,
    models.SingleConsumerCompositionContract,
    v212_models.AuthorizationConsumptionReceiptContract,
    v212_models.RunStartReceiptContract,
]:
    policy_by_kind = {
        item.terminal_kind: item
        for item in registry.policies
        if item.registration_status == "reachable"
    }
    if set(policy_by_kind) != set(models.TERMINAL_KINDS):
        _fail("terminal.registry", "v26.195 reachable terminal Registry differs")
    dispatcher = cast(
        models.ObservationDerivedDispatcherBinding,
        models.make_identity(
            models.ObservationDerivedDispatcherBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "source_v195_terminal_registry_id": registry.registry_id,
                "exact_v209_runner_id": runner.runner_id,
                "dispatcher_symbol_sha256": _symbol_sha(
                    implementation, "ObservationDerivedTerminalDispatcher.dispatch"
                ),
                "terminal_policy_ids": tuple(
                    policy_by_kind[kind].policy_id for kind in models.TERMINAL_KINDS
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_observation_derived_terminal_dispatcher_binding:",
        ),
    )
    v212_root = repository_root / V212_DIR
    source_writer = v212_models.RawResultWriterBinding.model_validate(
        _load(v212_root / "raw_result_writer_binding.json")
    )
    source_trace = v212_models.TraceOutcomeCheckpointBinding.model_validate(
        _load(v212_root / "trace_outcome_checkpoint_binding.json")
    )
    consumption = v212_models.AuthorizationConsumptionReceiptContract.model_validate(
        _load(v212_root / "authorization_consumption_receipt_contract.json")
    )
    run_start = v212_models.RunStartReceiptContract.model_validate(
        _load(v212_root / "run_start_receipt_contract.json")
    )
    source_transport = v212_models.ProviderTransportImplementationBinding.model_validate(
        _load(v212_root / "provider_transport_implementation_binding.json")
    )
    persistence = cast(
        models.ObservationBoundPersistenceBinding,
        models.make_identity(
            models.ObservationBoundPersistenceBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "dispatcher_binding_id": dispatcher.binding_id,
                "source_v212_raw_result_writer_binding_id": source_writer.binding_id,
                "source_v212_trace_outcome_checkpoint_binding_id": source_trace.binding_id,
                "persistence_symbol_sha256": _symbol_sha(
                    implementation, "ObservationBoundPersistencePipeline.persist"
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_observation_bound_persistence_binding:",
        ),
    )
    consumer = cast(
        models.SingleConsumerImplementationBinding,
        models.make_identity(
            models.SingleConsumerImplementationBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "exact_v211_authorization_id": v211_authorization.authorization_id,
                "exact_v209_implementation_id": v209_implementation.implementation_id,
                "exact_v209_manifest_id": manifest.manifest_id,
                "exact_v209_runner_id": runner.runner_id,
                "exact_v209_execution_contract_id": execution.contract_id,
                "source_v212_consumption_contract_id": consumption.contract_id,
                "source_v212_run_start_contract_id": run_start.contract_id,
                "source_v212_provider_transport_binding_id": source_transport.binding_id,
                "dispatcher_binding_id": dispatcher.binding_id,
                "persistence_binding_id": persistence.binding_id,
                "execute_preflight_symbol_sha256": _symbol_sha(
                    implementation, "RepairedOnlineExecutionConsumer.execute_preflight"
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_single_online_consumer_implementation_binding:",
        ),
    )
    composition = cast(
        models.SingleConsumerCompositionContract,
        models.make_identity(
            models.SingleConsumerCompositionContract,
            {
                "v212_freeze_id": freeze.freeze_id,
                "consumer_binding_id": consumer.binding_id,
                "dispatcher_binding_id": dispatcher.binding_id,
                "persistence_binding_id": persistence.binding_id,
            },
            field="contract_id",
            prefix="fresh_repaired_observation_derived_single_consumer_composition_contract:",
        ),
    )
    return dispatcher, persistence, consumer, composition, consumption, run_start


def _gate(name: str, evidence_id: str) -> models.GateResult:
    return cast(
        models.GateResult,
        models.make_identity(
            models.GateResult,
            {"gate_name": name, "evidence_id": evidence_id},
            field="gate_id",
            prefix="finance_v26_213_observation_terminal_gate:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.Report:
    if output_dir.exists():
        raise FileExistsError(f"v26.213 output already exists:{output_dir}")
    external, review_bytes, directive_bytes = _external_authorization(external_review_path)
    freeze = _v212_freeze(
        repository_root=repository_root,
        external_authorization_id=external.authorization_id,
    )
    source = _source_identity(source_identity)
    implementation = _implementation_binding(
        repository_root=repository_root,
        external_authorization_id=external.authorization_id,
        freeze_id=freeze.freeze_id,
        source=source,
    )
    (
        v209_implementation,
        v209_manifest,
        v209_runner,
        v209_execution,
        saved_census,
        saved_control,
    ) = _load_v209(repository_root)
    registry = outcome_authority.FreshTerminalRegistry.model_validate(
        _load(repository_root / V195_DIR / "fresh_terminal_registry.json")
    )
    v211_root = repository_root / V211_DIR
    v211_authorization_path = v211_root / "exact_online_execution_authorization.json"
    v211_authorization_bytes = v211_authorization_path.read_bytes()
    v211_authorization = v211_models.ExactOnlineExecutionAuthorization.model_validate(
        json.loads(v211_authorization_bytes)
    )
    (
        dispatcher_binding,
        persistence_binding,
        consumer_binding,
        composition,
        consumption_contract,
        run_start_contract,
    ) = _bindings(
        repository_root=repository_root,
        implementation=implementation,
        freeze=freeze,
        v209_implementation=v209_implementation,
        manifest=v209_manifest,
        runner=v209_runner,
        execution=v209_execution,
        v211_authorization=v211_authorization,
        registry=registry,
    )
    consumer = runtime.RepairedOnlineExecutionConsumer(
        binding=consumer_binding,
        composition=composition,
        dispatcher_binding=dispatcher_binding,
        persistence_binding=persistence_binding,
        consumption_contract=consumption_contract,
        run_start_contract=run_start_contract,
        authorization=v211_authorization,
        authorization_bytes=v211_authorization_bytes,
    )
    parents = v209._predecessor_freeze(
        repository_root=repository_root,
        authorization_id=external.authorization_id,
    )
    config = AgentModelConfig.model_validate(_load(repository_root / MODEL_PROFILE)["model"])
    with tempfile.TemporaryDirectory(prefix="v26_213_prepared_") as temporary:
        prepared = v188.prepare_execution(
            package_root=repository_root / "trusted_data_synthesis",
            output_dir=Path(temporary) / "provider_forbidden",
        )
        executed = consumer.execute_preflight(
            root=output_dir,
            manifest=v209_manifest,
            execution=v209_execution,
            implementation=v209_implementation,
            parents=parents,
            prepared=prepared,
            config=config,
            saved_census=saved_census,
            saved_control=saved_control,
        )
    scope = cast(
        models.ScopeBoundaryAudit,
        models.make_identity(
            models.ScopeBoundaryAudit,
            {
                "external_authorization_id": external.authorization_id,
                "v212_freeze_id": freeze.freeze_id,
                "consumer_binding_id": consumer_binding.binding_id,
            },
            field="audit_id",
            prefix="finance_v26_213_scope_boundary_audit:",
        ),
    )
    gates = cast(
        models.GateEvaluation,
        models.make_identity(
            models.GateEvaluation,
            {
                "gates": (
                    _gate("external_scope_and_exact_v212_freeze", freeze.freeze_id),
                    _gate(
                        "source_bound_observation_union_and_no_label_api", implementation.binding_id
                    ),
                    _gate(
                        "durable_ingress_mechanics_retained",
                        executed.consumption_receipt.receipt_id,
                    ),
                    _gate(
                        "exact_v209_runner_replay",
                        executed.execution_audit.v209_invocation_census_id,
                    ),
                    _gate(
                        "runner_evidence_to_authoritative_terminal",
                        executed.execution_audit.audit_id,
                    ),
                    _gate(
                        "authoritative_terminal_to_persistence_single_path",
                        executed.execution_audit.audit_id,
                    ),
                    _gate(
                        "sixteen_evidence_triggered_terminals_and_negative_controls",
                        executed.terminal_audit.audit_id,
                    ),
                    _gate("zero_provider_credential_empirical_boundary", scope.audit_id),
                )
            },
            field="evaluation_id",
            prefix="finance_v26_213_observation_terminal_gate_evaluation:",
        ),
    )
    decision = cast(
        models.Decision,
        models.make_identity(
            models.Decision,
            {
                "external_authorization_id": external.authorization_id,
                "v212_freeze_id": freeze.freeze_id,
                "composition_contract_id": composition.contract_id,
                "execution_audit_id": executed.execution_audit.audit_id,
                "terminal_evidence_audit_id": executed.terminal_audit.audit_id,
                "negative_control_audit_id": executed.negative_audit.audit_id,
                "gate_evaluation_id": gates.evaluation_id,
            },
            field="decision_id",
            prefix="finance_v26_213_observation_terminal_decision:",
        ),
    )
    transition = cast(
        models.Transition,
        models.make_identity(
            models.Transition,
            {
                "decision_id": decision.decision_id,
                "composition_contract_id": composition.contract_id,
            },
            field="transition_id",
            prefix="finance_v26_213_transition:",
        ),
    )
    report = cast(
        models.Report,
        models.make_identity(
            models.Report,
            {
                "run_id": RUN_ID,
                "source_identity_id": source.source_identity_id,
                "external_authorization_id": external.authorization_id,
                "v212_freeze_id": freeze.freeze_id,
                "consumer_binding_id": consumer_binding.binding_id,
                "composition_contract_id": composition.contract_id,
                "execution_audit_id": executed.execution_audit.audit_id,
                "terminal_evidence_audit_id": executed.terminal_audit.audit_id,
                "negative_control_audit_id": executed.negative_audit.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "gate_evaluation_id": gates.evaluation_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
            },
            field="report_id",
            prefix="finance_v26_213_observation_terminal_report:",
        ),
    )
    payloads = {
        "external_review.txt": review_bytes,
        "operator_authorization.txt": directive_bytes,
        "external_revision_authorization.json": _bytes(external),
        "v212_freeze.json": _bytes(freeze),
        "implementation_binding.json": _bytes(implementation),
        "observation_derived_dispatcher_binding.json": _bytes(dispatcher_binding),
        "observation_bound_persistence_binding.json": _bytes(persistence_binding),
        "single_consumer_implementation_binding.json": _bytes(consumer_binding),
        "single_consumer_composition_contract.json": _bytes(composition),
        "preflight_consumption_receipt.json": _bytes(executed.consumption_receipt),
        "preflight_run_start_receipt.json": _bytes(executed.run_start_receipt),
        "single_consumer_execution_audit.json": _bytes(executed.execution_audit),
        "terminal_evidence_audit.json": _bytes(executed.terminal_audit),
        "negative_control_audit.json": _bytes(executed.negative_audit),
        "scope_boundary_audit.json": _bytes(scope),
        "gate_evaluation.json": _bytes(gates),
        "decision.json": _bytes(decision),
        "prospective_transition.json": _bytes(transition),
        "source_identity.json": _bytes(source),
        "report.json": _bytes(report),
    }
    for name, payload in sorted(payloads.items()):
        _write(output_dir / name, payload)
    members = {
        path.relative_to(output_dir).as_posix(): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    }
    artifact = models.artifact_manifest(RUN_ID, members)
    _write(output_dir / "artifact_manifest.json", _bytes(artifact))
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
