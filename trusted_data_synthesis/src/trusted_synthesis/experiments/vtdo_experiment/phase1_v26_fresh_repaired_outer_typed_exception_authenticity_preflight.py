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
    phase1_v26_fresh_repaired_observation_derived_terminal_models as v213_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_outer_typed_exception_authenticity_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_outer_typed_exception_authenticity_runtime as runtime,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = (
    "finance_v26_214_fresh_repaired_outer_typed_exception_observation_authenticity_"
    "and_single_consumer_failure_terminalization_preflight_v1_20260903"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
REVIEW_SHA256: Final = "64c6b8c6bc2a62f8205ae7007169cedfc3d9fe184b2740b3d93b398c672339a7"
REVIEW_BYTES: Final = 14_653
OPERATOR_DIRECTIVE: Final = "参照审计继续实验修订"
V213_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_213_fresh_repaired_full_condition_observation_derived_terminal_"
    "single_consumer_path_repair_preflight_v1_20260902"
)
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
RUNTIME_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_outer_typed_exception_authenticity_runtime.py"
)
IMPLEMENTATION_FILES: Final = tuple(
    sorted(
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_outer_typed_exception_authenticity_models.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_outer_typed_exception_authenticity_runtime.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_outer_typed_exception_authenticity_preflight.py",
            "trusted_data_synthesis/tests/"
            "test_v26_fresh_repaired_outer_typed_exception_authenticity_preflight.py",
        )
    )
)
SYMBOLS: Final = (
    (
        runtime.RunnerFailureObservationAuthority.record_from_runner,
        "RunnerFailureObservationAuthority.record_from_runner",
    ),
    (
        runtime.ObservationAuthenticFullConditionRunner._invoke_current_state,
        "ObservationAuthenticFullConditionRunner._invoke_current_state",
    ),
    (runtime.AuthenticTypedFailureDispatcher.dispatch, "AuthenticTypedFailureDispatcher.dispatch"),
    (
        runtime.AuthenticFailurePersistencePipeline.persist,
        "AuthenticFailurePersistencePipeline.persist",
    ),
    (runtime.FailureConsumerParentGuard.admit, "FailureConsumerParentGuard.admit"),
    (
        runtime.FailureTerminalizingConsumer.execute_preflight,
        "FailureTerminalizingConsumer.execute_preflight",
    ),
    (runtime._run_negative_controls, "_run_negative_controls"),
)


class V214Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V214Error(stage, reason)


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
        ("git", *args), cwd=repository_root, check=False, capture_output=True
    )
    if completed.returncode:
        _fail("source.git", completed.stderr.decode("utf-8", errors="replace"))
    return completed.stdout


def _external_authorization(
    review_path: Path,
) -> tuple[models.ExternalRevisionAuthorization, bytes, bytes]:
    review = review_path.read_bytes()
    if len(review) != REVIEW_BYTES or _sha(review) != REVIEW_SHA256:
        _fail("authorization.review", "v26.214 external review bytes differ")
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
            prefix="finance_v26_214_external_revision_authorization:",
        ),
    )
    return authorization, review, directive


def _v213_freeze(*, repository_root: Path, external_authorization_id: str) -> models.V213Freeze:
    root = repository_root / V213_DIR
    artifact = v213_models.ArtifactManifest.model_validate(_load(root / "artifact_manifest.json"))
    files = tuple(sorted(path for path in root.rglob("*") if path.is_file()))
    members = {item.relative_path: item for item in artifact.members}
    actual_names = {
        path.relative_to(root).as_posix() for path in files if path.name != "artifact_manifest.json"
    }
    if set(members) != actual_names:
        _fail("freeze.paths", "v26.213 formal path set differs")
    for name, member in members.items():
        payload = (root / name).read_bytes()
        if len(payload) != member.byte_count or _sha(payload) != member.sha256:
            _fail("freeze.bytes", f"v26.213 formal member differs:{name}")
    if (
        len(files) != 1_058
        or sum(path.stat().st_size for path in files) != 58_565_824
        or artifact.file_count != 1_057
        or artifact.total_byte_count != 58_336_116
        or artifact.manifest_id
        != "finance_v26_213_artifact_manifest:e3563bf59ba7aa8fc8d1d1cfb8a48c6e5b98f01725bc4a789f49752e9eea67bc"
        or artifact.artifact_root
        != "finance_v26_213_artifact_root:b671d9cef0322b83ea6b815736d09f54c59671e2083042822928d2f79ece01f8"
    ):
        _fail("freeze.geometry", "v26.213 formal geometry differs")
    report = v213_models.Report.model_validate(_load(root / "report.json"))
    decision = v213_models.Decision.model_validate(_load(root / "decision.json"))
    transition = v213_models.Transition.model_validate(_load(root / "prospective_transition.json"))
    source = v213_models.SourceIdentity.model_validate(_load(root / "source_identity.json"))
    if (
        report.report_id
        != "finance_v26_213_observation_terminal_report:2889dd181f71f5753018d87087af2e123b0991d72a7617a6be29938cb657d813"
        or report.decision_id != decision.decision_id
        or report.transition_id != transition.transition_id
        or source.source_commit != "904577d81bcd83183d3aae0bab4e9f53c9907f0d"
        or source.source_tree != "c2f2e7629b29f7dfbcc27153539a1aa5be1cdf23"
        or report.current_v211_authorization_consumed
        or report.provider_calls != 0
    ):
        _fail("freeze.semantics", "v26.213 formal authority differs")
    return cast(
        models.V213Freeze,
        models.make_identity(
            models.V213Freeze,
            {
                "external_authorization_id": external_authorization_id,
                "v213_report_id": report.report_id,
                "v213_decision_id": decision.decision_id,
                "v213_transition_id": transition.transition_id,
                "v213_artifact_manifest_id": artifact.manifest_id,
                "v213_artifact_root": artifact.artifact_root,
            },
            field="freeze_id",
            prefix="finance_v26_214_v213_freeze:",
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
            prefix="finance_v26_214_source_identity:",
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
            _fail("source.tree", "v26.214 source tree differs")
    files: list[models.SourceBinding] = []
    for relative in IMPLEMENTATION_FILES:
        live = (repository_root / relative).read_bytes()
        if source.source_commit != "1" * 40:
            committed = _git(repository_root, "show", f"{source.source_commit}:{relative}")
            if committed != live:
                _fail("source.file", f"v26.214 live source differs:{relative}")
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
    dispatcher_parameters = tuple(
        inspect.signature(runtime.AuthenticTypedFailureDispatcher.dispatch).parameters
    )
    runner_source = inspect.getsource(
        runtime.ObservationAuthenticFullConditionRunner._invoke_current_state
    )
    runtime_source = (repository_root / RUNTIME_FILE).read_text(encoding="utf-8")
    forbidden = ("os.environ", "os.getenv", "requests.", "urllib.", "httpx.", "socket.")
    if (
        dispatcher_parameters != ("self", "evidence")
        or "record_from_runner(observation)" not in runner_source
        or "except v209.TypedTransportFailure as error:" not in runner_source
        or any(item in runtime_source for item in forbidden)
    ):
        _fail("source.interface", "v26.214 source authenticity or zero-network interface differs")
    return cast(
        models.ImplementationBinding,
        models.make_identity(
            models.ImplementationBinding,
            {
                "external_authorization_id": external_authorization_id,
                "v213_freeze_id": freeze_id,
                "source_commit": source.source_commit,
                "source_tree": source.source_tree,
                "files": tuple(files),
                "symbols": symbols,
            },
            field="binding_id",
            prefix="fresh_repaired_outer_typed_exception_authenticity_implementation_binding:",
        ),
    )


def _symbol_sha(binding: models.ImplementationBinding, name: str) -> str:
    values = tuple(item.sha256 for item in binding.symbols if item.symbol == name)
    if len(values) != 1:
        _fail("source.symbol", f"v26.214 symbol binding differs:{name}")
    return values[0]


def _load_v209(
    repository_root: Path,
) -> tuple[
    v209_models.ImplementationBinding,
    v209_models.ExecutableDevelopmentManifest,
    v209_models.ExecutableRunnerContract,
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
    )


def _bindings(
    *,
    repository_root: Path,
    implementation: models.ImplementationBinding,
    freeze: models.V213Freeze,
    v209_implementation: v209_models.ImplementationBinding,
    manifest: v209_models.ExecutableDevelopmentManifest,
    runner: v209_models.ExecutableRunnerContract,
    v211_authorization: v211_models.ExactOnlineExecutionAuthorization,
    registry: outcome_authority.FreshTerminalRegistry,
) -> tuple[
    models.RunnerObservationBinding,
    models.AuthenticDispatcherBinding,
    models.PersistenceBinding,
    models.ConsumerBinding,
    models.CompositionContract,
    v212_models.AuthorizationConsumptionReceiptContract,
    v212_models.RunStartReceiptContract,
]:
    policy_by_kind = {
        item.terminal_kind: item
        for item in registry.policies
        if item.registration_status == "reachable"
    }
    if not set(models.OUTER_TERMINAL_KINDS).issubset(policy_by_kind):
        _fail("terminal.registry", "v26.195 outer terminal Registry differs")
    runner_binding = cast(
        models.RunnerObservationBinding,
        models.make_identity(
            models.RunnerObservationBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "exact_v209_runner_id": runner.runner_id,
                "exact_v209_request_implementation_id": v209_implementation.implementation_id,
                "runner_symbol_sha256": _symbol_sha(
                    implementation, "ObservationAuthenticFullConditionRunner._invoke_current_state"
                ),
                "observation_authority_symbol_sha256": _symbol_sha(
                    implementation, "RunnerFailureObservationAuthority.record_from_runner"
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_runner_owned_typed_failure_observation_binding:",
        ),
    )
    dispatcher = cast(
        models.AuthenticDispatcherBinding,
        models.make_identity(
            models.AuthenticDispatcherBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "runner_observation_binding_id": runner_binding.binding_id,
                "source_v195_terminal_registry_id": registry.registry_id,
                "dispatcher_symbol_sha256": _symbol_sha(
                    implementation, "AuthenticTypedFailureDispatcher.dispatch"
                ),
                "terminal_policy_ids": tuple(
                    policy_by_kind[kind].policy_id for kind in models.OUTER_TERMINAL_KINDS
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_authentic_typed_failure_dispatcher_binding:",
        ),
    )
    v213_root = repository_root / V213_DIR
    source_persistence = v213_models.ObservationBoundPersistenceBinding.model_validate(
        _load(v213_root / "observation_bound_persistence_binding.json")
    )
    persistence = cast(
        models.PersistenceBinding,
        models.make_identity(
            models.PersistenceBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "dispatcher_binding_id": dispatcher.binding_id,
                "source_v213_persistence_binding_id": source_persistence.binding_id,
                "persistence_symbol_sha256": _symbol_sha(
                    implementation, "AuthenticFailurePersistencePipeline.persist"
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_authentic_typed_failure_persistence_binding:",
        ),
    )
    v212_root = repository_root / V212_DIR
    consumption = v212_models.AuthorizationConsumptionReceiptContract.model_validate(
        _load(v212_root / "authorization_consumption_receipt_contract.json")
    )
    run_start = v212_models.RunStartReceiptContract.model_validate(
        _load(v212_root / "run_start_receipt_contract.json")
    )
    consumer = cast(
        models.ConsumerBinding,
        models.make_identity(
            models.ConsumerBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "exact_v211_authorization_id": v211_authorization.authorization_id,
                "exact_v209_manifest_id": manifest.manifest_id,
                "source_v212_consumption_contract_id": consumption.contract_id,
                "source_v212_run_start_contract_id": run_start.contract_id,
                "runner_observation_binding_id": runner_binding.binding_id,
                "dispatcher_binding_id": dispatcher.binding_id,
                "persistence_binding_id": persistence.binding_id,
                "execute_preflight_symbol_sha256": _symbol_sha(
                    implementation, "FailureTerminalizingConsumer.execute_preflight"
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_typed_failure_terminalizing_consumer_binding:",
        ),
    )
    composition = cast(
        models.CompositionContract,
        models.make_identity(
            models.CompositionContract,
            {
                "v213_freeze_id": freeze.freeze_id,
                "consumer_binding_id": consumer.binding_id,
                "runner_observation_binding_id": runner_binding.binding_id,
                "dispatcher_binding_id": dispatcher.binding_id,
                "persistence_binding_id": persistence.binding_id,
            },
            field="contract_id",
            prefix="fresh_repaired_typed_failure_single_consumer_composition_contract:",
        ),
    )
    return (
        runner_binding,
        dispatcher,
        persistence,
        consumer,
        composition,
        consumption,
        run_start,
    )


def _gate(name: str, evidence_id: str) -> models.GateResult:
    return cast(
        models.GateResult,
        models.make_identity(
            models.GateResult,
            {"gate_name": name, "evidence_id": evidence_id},
            field="gate_id",
            prefix="finance_v26_214_gate:",
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
        raise FileExistsError(f"v26.214 output already exists:{output_dir}")
    external, review_bytes, directive_bytes = _external_authorization(external_review_path)
    freeze = _v213_freeze(
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
    v209_implementation, v209_manifest, v209_runner = _load_v209(repository_root)
    registry = outcome_authority.FreshTerminalRegistry.model_validate(
        _load(repository_root / V195_DIR / "fresh_terminal_registry.json")
    )
    v211_path = repository_root / V211_DIR / "exact_online_execution_authorization.json"
    v211_bytes = v211_path.read_bytes()
    v211_authorization = v211_models.ExactOnlineExecutionAuthorization.model_validate(
        json.loads(v211_bytes)
    )
    (
        runner_binding,
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
        v211_authorization=v211_authorization,
        registry=registry,
    )
    consumer = runtime.FailureTerminalizingConsumer(
        binding=consumer_binding,
        composition=composition,
        runner_binding=runner_binding,
        dispatcher_binding=dispatcher_binding,
        persistence_binding=persistence_binding,
        consumption_contract=consumption_contract,
        run_start_contract=run_start_contract,
        authorization=v211_authorization,
        authorization_bytes=v211_bytes,
    )
    parents = v209._predecessor_freeze(
        repository_root=repository_root,
        authorization_id=external.authorization_id,
    )
    config = AgentModelConfig.model_validate(_load(repository_root / MODEL_PROFILE)["model"])
    with tempfile.TemporaryDirectory(prefix="v26_214_prepared_") as temporary:
        prepared = v188.prepare_execution(
            package_root=repository_root / "trusted_data_synthesis",
            output_dir=Path(temporary) / "provider_forbidden",
        )
        executed = consumer.execute_preflight(
            root=output_dir,
            manifest=v209_manifest,
            implementation=v209_implementation,
            parents=parents,
            prepared=prepared,
            config=config,
        )
    scope = cast(
        models.ScopeBoundaryAudit,
        models.make_identity(
            models.ScopeBoundaryAudit,
            {
                "external_authorization_id": external.authorization_id,
                "v213_freeze_id": freeze.freeze_id,
                "consumer_binding_id": consumer_binding.binding_id,
            },
            field="audit_id",
            prefix="finance_v26_214_scope_boundary_audit:",
        ),
    )
    gates = cast(
        models.GateEvaluation,
        models.make_identity(
            models.GateEvaluation,
            {
                "gates": (
                    _gate("external_scope_and_exact_v213_freeze", freeze.freeze_id),
                    _gate("runner_owned_catch_observation", runner_binding.binding_id),
                    _gate(
                        "generic_evidence_and_authority_bound_dispatch",
                        dispatcher_binding.binding_id,
                    ),
                    _gate(
                        "durable_ingress_mechanics_retained", executed.run_start_receipt.receipt_id
                    ),
                    _gate(
                        "single_consumer_actual_failure_terminal_branch",
                        executed.execution_audit.audit_id,
                    ),
                    _gate(
                        "authentic_terminal_to_five_layer_persistence",
                        persistence_binding.binding_id,
                    ),
                    _gate(
                        "four_fully_rehashed_provenance_attacks_reject",
                        executed.negative_audit.audit_id,
                    ),
                    _gate("zero_provider_credential_empirical_boundary", scope.audit_id),
                )
            },
            field="evaluation_id",
            prefix="finance_v26_214_gate_evaluation:",
        ),
    )
    decision = cast(
        models.Decision,
        models.make_identity(
            models.Decision,
            {
                "external_authorization_id": external.authorization_id,
                "v213_freeze_id": freeze.freeze_id,
                "composition_contract_id": composition.contract_id,
                "execution_audit_id": executed.execution_audit.audit_id,
                "negative_control_audit_id": executed.negative_audit.audit_id,
                "gate_evaluation_id": gates.evaluation_id,
            },
            field="decision_id",
            prefix="finance_v26_214_typed_failure_authenticity_decision:",
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
            prefix="finance_v26_214_transition:",
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
                "v213_freeze_id": freeze.freeze_id,
                "runner_observation_binding_id": runner_binding.binding_id,
                "consumer_binding_id": consumer_binding.binding_id,
                "composition_contract_id": composition.contract_id,
                "execution_audit_id": executed.execution_audit.audit_id,
                "negative_control_audit_id": executed.negative_audit.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "gate_evaluation_id": gates.evaluation_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
            },
            field="report_id",
            prefix="finance_v26_214_typed_failure_authenticity_report:",
        ),
    )
    payloads = {
        "external_review.txt": review_bytes,
        "operator_authorization.txt": directive_bytes,
        "external_revision_authorization.json": _bytes(external),
        "v213_freeze.json": _bytes(freeze),
        "implementation_binding.json": _bytes(implementation),
        "runner_observation_binding.json": _bytes(runner_binding),
        "authentic_dispatcher_binding.json": _bytes(dispatcher_binding),
        "persistence_binding.json": _bytes(persistence_binding),
        "consumer_binding.json": _bytes(consumer_binding),
        "composition_contract.json": _bytes(composition),
        "preflight_consumption_receipt.json": _bytes(executed.consumption_receipt),
        "preflight_run_start_receipt.json": _bytes(executed.run_start_receipt),
        "failure_execution_audit.json": _bytes(executed.execution_audit),
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
