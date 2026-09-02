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
    phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_runtime as runtime,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = (
    "finance_v26_212_fresh_repaired_full_condition_exact_online_execution_"
    "consumer_terminal_persistence_integration_preflight_v1_20260902"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
REVIEW_SHA256: Final = "400e1b6960df1d69ed71a9265bf084551abb465ad92b9718045132be4b7fd462"
REVIEW_BYTES: Final = 14_475
OPERATOR_DIRECTIVE: Final = "参照审计报告修订"
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
V211_SOURCE_COMMIT: Final = "ed62189a162601e97a48b2ab91840c680abe7794"
V211_SOURCE_TREE: Final = "d35134034991a7b330b2214cc67036a60f4fa289"
RUNTIME_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_runtime.py"
)
IMPLEMENTATION_FILES: Final = tuple(
    sorted(
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_preflight.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_models.py",
            RUNTIME_FILE,
            "trusted_data_synthesis/tests/"
            "test_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_preflight.py",
        )
    )
)
SYMBOLS: Final = (
    (
        runtime.DurableAuthorizationConsumer.consume_preflight_lease,
        "DurableAuthorizationConsumer.consume_preflight_lease",
    ),
    (runtime.DurableRunStartReceiptWriter.write, "DurableRunStartReceiptWriter.write"),
    (runtime.RepairedImplementationParentGuard.admit, "RepairedImplementationParentGuard.admit"),
    (runtime.CredentialBoundFactoryGate.open, "CredentialBoundFactoryGate.open"),
    (runtime.PreflightProviderTransport.send, "PreflightProviderTransport.send"),
    (runtime.execute_exact_v209_runner, "execute_exact_v209_runner"),
    (runtime.CompleteTerminalDispatcher.dispatch, "CompleteTerminalDispatcher.dispatch"),
    (runtime.RawResultWriter.write_raw, "RawResultWriter.write_raw"),
    (runtime.RawResultWriter.write_result, "RawResultWriter.write_result"),
    (
        runtime.TraceOutcomeCheckpointReconstructor.reconstruct_and_write,
        "TraceOutcomeCheckpointReconstructor.reconstruct_and_write",
    ),
    (runtime.EvidencePersistencePipeline.persist, "EvidencePersistencePipeline.persist"),
)


class V212Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V212Error(stage, reason)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _bytes(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _write(path: Path, payload: bytes) -> None:
    runtime._durable_write_no_replace(path, payload)


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
) -> tuple[models.ExternalRepairAuthorization, bytes, bytes]:
    review = review_path.read_bytes()
    if len(review) != REVIEW_BYTES or _sha(review) != REVIEW_SHA256:
        _fail("authorization.review", "v26.212 external review bytes differ")
    directive = OPERATOR_DIRECTIVE.encode("utf-8")
    authorization = cast(
        models.ExternalRepairAuthorization,
        models.make_identity(
            models.ExternalRepairAuthorization,
            {
                "review_sha256": _sha(review),
                "review_byte_count": len(review),
                "operator_directive_sha256": _sha(directive),
                "operator_directive_byte_count": len(directive),
            },
            field="authorization_id",
            prefix="finance_v26_212_external_repair_authorization:",
        ),
    )
    return authorization, review, directive


def _verify_v211_manifest(
    root: Path,
    manifest: v211_models.ArtifactManifest,
) -> tuple[int, int]:
    files = tuple(sorted(path for path in root.iterdir() if path.is_file()))
    expected = {path.name for path in files if path.name != "artifact_manifest.json"}
    if {item.relative_path for item in manifest.members} != expected:
        _fail("freeze.paths", "v26.211 formal path set differs")
    for member in manifest.members:
        payload = (root / member.relative_path).read_bytes()
        if len(payload) != member.byte_count or _sha(payload) != member.sha256:
            _fail("freeze.bytes", f"v26.211 member differs:{member.relative_path}")
    return len(files), sum(path.stat().st_size for path in files)


def _v211_freeze(
    *,
    repository_root: Path,
    external_authorization_id: str,
) -> tuple[
    models.V211Freeze,
    v211_models.ExactOnlineExecutionAuthorization,
    bytes,
]:
    root = repository_root / V211_DIR
    artifact = v211_models.ArtifactManifest.model_validate(_load(root / "artifact_manifest.json"))
    if (
        _verify_v211_manifest(root, artifact) != (17, 137_306)
        or artifact.file_count != 16
        or artifact.total_byte_count != 134_503
    ):
        _fail("freeze.geometry", "v26.211 formal geometry differs")
    report = v211_models.OnlineAuthorizationReport.model_validate(_load(root / "report.json"))
    decision = v211_models.OnlineAuthorizationDecision.model_validate(
        _load(root / "online_authorization_decision.json")
    )
    transition = v211_models.ProspectiveTransition.model_validate(
        _load(root / "prospective_transition.json")
    )
    source = v211_models.SourceIdentity.model_validate(_load(root / "source_identity.json"))
    composition = v211_models.OnlineExecutionCompositionContract.model_validate(
        _load(root / "online_execution_composition_contract.json")
    )
    authorization_path = root / "exact_online_execution_authorization.json"
    authorization_bytes = authorization_path.read_bytes()
    authorization = v211_models.ExactOnlineExecutionAuthorization.model_validate(
        json.loads(authorization_bytes)
    )
    if (
        source.source_commit != V211_SOURCE_COMMIT
        or source.source_tree != V211_SOURCE_TREE
        or report.authorization_id != authorization.authorization_id
        or report.decision_id != decision.decision_id
        or report.transition_id != transition.transition_id
        or report.composition_contract_id != composition.contract_id
        or report.authorization_consumed
        or authorization_bytes != v211_models.canonical_bytes(authorization) + b"\n"
    ):
        _fail("freeze.semantics", "v26.211 authority differs")
    freeze = cast(
        models.V211Freeze,
        models.make_identity(
            models.V211Freeze,
            {
                "external_authorization_id": external_authorization_id,
                "v211_report_id": report.report_id,
                "v211_decision_id": decision.decision_id,
                "v211_transition_id": transition.transition_id,
                "v211_authorization_id": authorization.authorization_id,
                "v211_composition_contract_id": composition.contract_id,
                "v211_artifact_manifest_id": artifact.manifest_id,
                "v211_artifact_root": artifact.artifact_root,
                "v211_source_commit": source.source_commit,
                "v211_source_tree": source.source_tree,
                "exact_authorization_sha256": _sha(authorization_bytes),
            },
            field="freeze_id",
            prefix="finance_v26_212_v211_freeze:",
        ),
    )
    return freeze, authorization, authorization_bytes


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
            prefix="finance_v26_212_source_identity:",
        ),
    )


def _implementation_binding(
    *,
    repository_root: Path,
    external_authorization_id: str,
    freeze_id: str,
    source_identity: models.SourceIdentity,
) -> models.ImplementationBinding:
    if source_identity.source_commit != "1" * 40:
        actual_tree = (
            _git(
                repository_root,
                "rev-parse",
                f"{source_identity.source_commit}^{{tree}}",
            )
            .decode("ascii")
            .strip()
        )
        if actual_tree != source_identity.source_tree:
            _fail("source.tree", "v26.212 source commit/tree differs")
    files: list[models.SourceSymbolBinding] = []
    for relative_path in IMPLEMENTATION_FILES:
        live = (repository_root / relative_path).read_bytes()
        if source_identity.source_commit != "1" * 40:
            committed = _git(
                repository_root,
                "show",
                f"{source_identity.source_commit}:{relative_path}",
            )
            if live != committed:
                _fail("source.file", f"v26.212 live source differs:{relative_path}")
        files.append(
            models.SourceSymbolBinding(
                relative_path=relative_path,
                symbol="<file>",
                sha256=_sha(live),
                byte_count=len(live),
            )
        )
    symbols = tuple(
        models.SourceSymbolBinding(
            relative_path=RUNTIME_FILE,
            symbol=name,
            sha256=_sha(inspect.getsource(symbol).encode("utf-8")),
            byte_count=len(inspect.getsource(symbol).encode("utf-8")),
        )
        for symbol, name in SYMBOLS
    )
    runtime_source = (repository_root / RUNTIME_FILE).read_text(encoding="utf-8")
    forbidden = (
        "os.environ",
        "os.getenv",
        "requests.",
        "urllib.",
        "httpx.",
        "socket.",
    )
    if any(token in runtime_source for token in forbidden):
        _fail("source.boundary", "v26.212 Runtime contains a network or credential route")
    return cast(
        models.ImplementationBinding,
        models.make_identity(
            models.ImplementationBinding,
            {
                "external_authorization_id": external_authorization_id,
                "v211_freeze_id": freeze_id,
                "source_commit": source_identity.source_commit,
                "source_tree": source_identity.source_tree,
                "files": tuple(files),
                "symbols": symbols,
            },
            field="binding_id",
            prefix=("fresh_repaired_online_consumer_terminal_persistence_implementation_binding:"),
        ),
    )


def _symbol_sha(implementation: models.ImplementationBinding, name: str) -> str:
    matches = tuple(item.sha256 for item in implementation.symbols if item.symbol == name)
    if len(matches) != 1:
        _fail("source.symbol", f"v26.212 source symbol binding differs:{name}")
    return matches[0]


def _load_v209_objects(
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


def _mechanism_bindings(
    *,
    implementation: models.ImplementationBinding,
    freeze: models.V211Freeze,
    v211_authorization: v211_models.ExactOnlineExecutionAuthorization,
    v209_implementation: v209_models.ImplementationBinding,
    v209_manifest: v209_models.ExecutableDevelopmentManifest,
    v209_runner: v209_models.ExecutableRunnerContract,
    v209_execution: v209_models.ExecutableExecutionContract,
    registry: outcome_authority.FreshTerminalRegistry,
) -> tuple[
    models.AuthorizationConsumptionReceiptContract,
    models.RunStartReceiptContract,
    models.ProviderTransportImplementationBinding,
    models.TerminalRegistryDispatcherBinding,
    models.RawResultWriterBinding,
    models.TraceOutcomeCheckpointBinding,
    models.OnlineExecutionConsumerImplementationBinding,
    models.RepairedCompositionContract,
]:
    consumption = cast(
        models.AuthorizationConsumptionReceiptContract,
        models.make_identity(
            models.AuthorizationConsumptionReceiptContract,
            {
                "implementation_binding_id": implementation.binding_id,
                "exact_v211_authorization_id": v211_authorization.authorization_id,
            },
            field="contract_id",
            prefix="fresh_repaired_authorization_consumption_receipt_contract:",
        ),
    )
    run_start = cast(
        models.RunStartReceiptContract,
        models.make_identity(
            models.RunStartReceiptContract,
            {
                "implementation_binding_id": implementation.binding_id,
                "consumption_contract_id": consumption.contract_id,
            },
            field="contract_id",
            prefix="fresh_repaired_run_start_receipt_contract:",
        ),
    )
    transport = cast(
        models.ProviderTransportImplementationBinding,
        models.make_identity(
            models.ProviderTransportImplementationBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "exact_v209_runner_id": v209_runner.runner_id,
                "transport_symbol_sha256": _symbol_sha(
                    implementation,
                    "PreflightProviderTransport.send",
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_provider_transport_implementation_binding:",
        ),
    )
    policy_by_kind = {
        item.terminal_kind: item
        for item in registry.policies
        if item.registration_status == "reachable"
    }
    if set(policy_by_kind) != set(models.TERMINAL_KINDS):
        _fail("terminal.registry", "v26.195 reachable terminal set differs")
    terminal = cast(
        models.TerminalRegistryDispatcherBinding,
        models.make_identity(
            models.TerminalRegistryDispatcherBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "source_v195_terminal_registry_id": registry.registry_id,
                "exact_v209_runner_id": v209_runner.runner_id,
                "terminal_kinds": models.TERMINAL_KINDS,
                "terminal_policy_ids": tuple(
                    policy_by_kind[kind].policy_id for kind in models.TERMINAL_KINDS
                ),
                "dispatcher_symbol_sha256": _symbol_sha(
                    implementation,
                    "CompleteTerminalDispatcher.dispatch",
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_terminal_registry_dispatcher_binding:",
        ),
    )
    writer = cast(
        models.RawResultWriterBinding,
        models.make_identity(
            models.RawResultWriterBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "writer_symbol_sha256": _symbol_sha(implementation, "RawResultWriter.write_raw"),
            },
            field="binding_id",
            prefix="fresh_repaired_raw_result_writer_binding:",
        ),
    )
    trace = cast(
        models.TraceOutcomeCheckpointBinding,
        models.make_identity(
            models.TraceOutcomeCheckpointBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "reconstructor_symbol_sha256": _symbol_sha(
                    implementation,
                    "TraceOutcomeCheckpointReconstructor.reconstruct_and_write",
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_trace_outcome_checkpoint_binding:",
        ),
    )
    consumer = cast(
        models.OnlineExecutionConsumerImplementationBinding,
        models.make_identity(
            models.OnlineExecutionConsumerImplementationBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "exact_v211_authorization_id": v211_authorization.authorization_id,
                "exact_v209_implementation_id": v209_implementation.implementation_id,
                "exact_v209_manifest_id": v209_manifest.manifest_id,
                "exact_v209_runner_id": v209_runner.runner_id,
                "exact_v209_execution_contract_id": v209_execution.contract_id,
                "consumption_contract_id": consumption.contract_id,
                "run_start_contract_id": run_start.contract_id,
                "provider_transport_binding_id": transport.binding_id,
                "terminal_registry_dispatcher_binding_id": terminal.binding_id,
                "raw_result_writer_binding_id": writer.binding_id,
                "trace_outcome_checkpoint_binding_id": trace.binding_id,
            },
            field="binding_id",
            prefix="fresh_repaired_online_execution_consumer_implementation_binding:",
        ),
    )
    composition = cast(
        models.RepairedCompositionContract,
        models.make_identity(
            models.RepairedCompositionContract,
            {
                "v211_freeze_id": freeze.freeze_id,
                "consumer_binding_id": consumer.binding_id,
            },
            field="contract_id",
            prefix=("fresh_repaired_online_consumer_terminal_persistence_composition_contract:"),
        ),
    )
    return consumption, run_start, transport, terminal, writer, trace, consumer, composition


def _control(
    *,
    name: str,
    admitted: bool,
    reason: str | None,
    counts: tuple[int, int, int, int, int],
) -> models.IngressOrderControl:
    return cast(
        models.IngressOrderControl,
        models.make_identity(
            models.IngressOrderControl,
            {
                "control_name": name,
                "admitted": admitted,
                "rejected": not admitted,
                "rejection_reason_sha256": None if reason is None else _sha(reason.encode("utf-8")),
                "consumption_write_count": counts[0],
                "run_start_receipt_write_count": counts[1],
                "credential_boundary_probe_count": counts[2],
                "transport_factory_count": counts[3],
                "writer_factory_count": counts[4],
            },
            field="control_id",
            prefix="finance_v26_212_ingress_order_control:",
        ),
    )


def _ingress_order_audit(
    *,
    output_dir: Path,
    consumption_contract: models.AuthorizationConsumptionReceiptContract,
    run_start_contract: models.RunStartReceiptContract,
    consumer_binding: models.OnlineExecutionConsumerImplementationBinding,
    composition: models.RepairedCompositionContract,
    v211_authorization: v211_models.ExactOnlineExecutionAuthorization,
    authorization_bytes: bytes,
    manifest: v209_models.ExecutableDevelopmentManifest,
) -> tuple[
    models.IngressOrderAudit,
    models.PreflightConsumptionReceipt,
    models.PreflightRunStartReceipt,
    runtime.GuardedFactoryProducts,
]:
    guard = runtime.RepairedImplementationParentGuard(
        expected_consumer=consumer_binding,
        expected_composition=composition,
    )
    guard.admit(consumer=consumer_binding, composition=composition)
    consumer = runtime.DurableAuthorizationConsumer(
        contract=consumption_contract,
        consumer_binding_id=consumer_binding.binding_id,
        expected_authorization=v211_authorization,
        expected_authorization_file_bytes=authorization_bytes,
    )
    run_writer = runtime.DurableRunStartReceiptWriter(
        contract=run_start_contract,
        consumer_binding_id=consumer_binding.binding_id,
        manifest_id=manifest.manifest_id,
        exact_job_set_sha256=models.canonical_sha256(manifest.expected_job_ids),
    )
    gate = runtime.CredentialBoundFactoryGate()
    legal_root = output_dir / "control_ingress"
    consumption = consumer.consume_preflight_lease(legal_root)
    run_start = run_writer.write(legal_root, consumption)
    counts = {"credential": 0, "transport": 0, "writer": 0}

    def credential_probe() -> None:
        counts["credential"] += 1

    def transport_builder() -> runtime.ProviderTransportFactory:
        counts["transport"] += 1
        return runtime.ProviderTransportFactory()

    def writer_builder() -> object:
        counts["writer"] += 1
        return object()

    products = gate.open(
        root=legal_root,
        consumption=consumption,
        run_start=run_start,
        credential_boundary_probe=credential_probe,
        transport_factory_builder=transport_builder,
        writer_factory_builder=writer_builder,
    )
    if counts != {"credential": 1, "transport": 1, "writer": 1}:
        _fail("ingress.legal", "v26.212 legal ingress order differs")
    controls = [
        _control(name="exact_legal_order", admitted=True, reason=None, counts=(1, 1, 1, 1, 1))
    ]

    empty_root = output_dir / "control_factory_before_consumption"
    try:
        gate.open(
            root=empty_root,
            consumption=consumption,
            run_start=run_start,
            credential_boundary_probe=lambda: _fail("ingress.attack", "probe reached"),
            transport_factory_builder=lambda: _fail("ingress.attack", "factory reached"),
            writer_factory_builder=lambda: _fail("ingress.attack", "writer reached"),
        )
    except (ValueError, FileNotFoundError):
        controls.append(
            _control(
                name="factory_before_consumption",
                admitted=False,
                reason="durable_consumption_receipt_absent",
                counts=(0, 0, 0, 0, 0),
            )
        )
    else:
        _fail("ingress.attack", "factory-before-consumption attack admitted")

    no_run_root = output_dir / "control_factory_before_run_start"
    consumer.consume_preflight_lease(no_run_root)
    try:
        gate.open(
            root=no_run_root,
            consumption=consumption,
            run_start=run_start,
            credential_boundary_probe=lambda: _fail("ingress.attack", "probe reached"),
            transport_factory_builder=lambda: _fail("ingress.attack", "factory reached"),
            writer_factory_builder=lambda: _fail("ingress.attack", "writer reached"),
        )
    except (ValueError, FileNotFoundError):
        controls.append(
            _control(
                name="factory_before_run_start_receipt",
                admitted=False,
                reason="durable_run_start_receipt_absent",
                counts=(1, 0, 0, 0, 0),
            )
        )
    else:
        _fail("ingress.attack", "factory-before-Run-Start attack admitted")

    try:
        consumer.consume_preflight_lease(legal_root)
    except FileExistsError:
        controls.append(
            _control(
                name="second_consumption",
                admitted=False,
                reason="durable_consumption_receipt_already_exists",
                counts=(1, 1, 0, 0, 0),
            )
        )
    else:
        _fail("ingress.attack", "second consumption attack admitted")
    audit = cast(
        models.IngressOrderAudit,
        models.make_identity(
            models.IngressOrderAudit,
            {
                "consumer_binding_id": consumer_binding.binding_id,
                "controls": tuple(controls),
            },
            field="audit_id",
            prefix="finance_v26_212_ingress_order_audit:",
        ),
    )
    return audit, consumption, run_start, products


def _source_mutation_audit(
    *,
    consumer: models.OnlineExecutionConsumerImplementationBinding,
    composition: models.RepairedCompositionContract,
) -> models.SourceMutationAudit:
    guard = runtime.RepairedImplementationParentGuard(
        expected_consumer=consumer,
        expected_composition=composition,
    )
    fields = (
        "implementation_binding_id",
        "consumption_contract_id",
        "run_start_contract_id",
        "provider_transport_binding_id",
        "terminal_registry_dispatcher_binding_id",
        "raw_result_writer_binding_id",
        "trace_outcome_checkpoint_binding_id",
    )
    controls: list[models.SourceMutationControl] = []
    for field in fields:
        values = consumer.model_dump(mode="python", exclude={"binding_id"}, warnings=False)
        values[field] = f"attack.v26_212.{field}"
        mutant = cast(
            models.OnlineExecutionConsumerImplementationBinding,
            models.make_identity(
                models.OnlineExecutionConsumerImplementationBinding,
                values,
                field="binding_id",
                prefix="fresh_repaired_online_execution_consumer_implementation_binding:",
            ),
        )
        composition_values = composition.model_dump(
            mode="python",
            exclude={"contract_id"},
            warnings=False,
        )
        composition_values["consumer_binding_id"] = mutant.binding_id
        mutant_composition = cast(
            models.RepairedCompositionContract,
            models.make_identity(
                models.RepairedCompositionContract,
                composition_values,
                field="contract_id",
                prefix=(
                    "fresh_repaired_online_consumer_terminal_persistence_composition_contract:"
                ),
            ),
        )
        try:
            guard.admit(consumer=mutant, composition=mutant_composition)
        except ValueError:
            controls.append(
                cast(
                    models.SourceMutationControl,
                    models.make_identity(
                        models.SourceMutationControl,
                        {
                            "attack_name": f"fully_rehashed_{field}",
                            "mutated_parent_id": str(values[field]),
                        },
                        field="control_id",
                        prefix="finance_v26_212_source_mutation_control:",
                    ),
                )
            )
        else:
            _fail("mutation.guard", f"v26.212 source mutation admitted:{field}")
    return cast(
        models.SourceMutationAudit,
        models.make_identity(
            models.SourceMutationAudit,
            {
                "consumer_binding_id": consumer.binding_id,
                "controls": tuple(controls),
            },
            field="audit_id",
            prefix="finance_v26_212_source_mutation_audit:",
        ),
    )


def _file_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _scripted_persistence_audit(
    *,
    output_dir: Path,
    consumer: models.OnlineExecutionConsumerImplementationBinding,
    composition: models.RepairedCompositionContract,
    run_start: models.PreflightRunStartReceipt,
    terminal_binding: models.TerminalRegistryDispatcherBinding,
    writer_binding: models.RawResultWriterBinding,
    trace_binding: models.TraceOutcomeCheckpointBinding,
    census: v209_models.ExecutableInvocationCensus,
    execution: v209_models.FullConditionExecutionControlAudit,
) -> models.ScriptedPersistenceAudit:
    dispatcher = runtime.CompleteTerminalDispatcher(terminal_binding)
    pipeline = runtime.EvidencePersistencePipeline(
        root=output_dir,
        raw_result_binding=writer_binding,
        trace_outcome_checkpoint_binding=trace_binding,
    )
    records: list[models.ScriptedEvidenceRecord] = []
    for row in sorted(execution.rows, key=lambda item: item.job_id):
        signal, decision = dispatcher.dispatch(
            terminal_kind="completed_qualified",
            source_binding_id=row.row_id,
            job_id=row.job_id,
        )
        chain = pipeline.persist(
            namespace="scripted_evidence",
            job_id=row.job_id,
            source_binding_id=row.row_id,
            invocation_ids=row.invocation_ids,
            terminal_signal=signal,
            terminal_decision=decision,
        )
        records.append(
            cast(
                models.ScriptedEvidenceRecord,
                models.make_identity(
                    models.ScriptedEvidenceRecord,
                    {
                        "job_id": row.job_id,
                        "v209_control_row_id": row.row_id,
                        "invocation_ids": row.invocation_ids,
                        "raw_id": chain.raw["raw_id"],
                        "result_id": chain.result["result_id"],
                        "trace_id": chain.trace["trace_id"],
                        "outcome_id": chain.outcome["outcome_id"],
                        "checkpoint_id": chain.checkpoint["checkpoint_id"],
                        "raw_relative_path": chain.raw_path.relative_to(output_dir).as_posix(),
                        "result_relative_path": chain.result_path.relative_to(
                            output_dir
                        ).as_posix(),
                        "trace_relative_path": chain.trace_path.relative_to(output_dir).as_posix(),
                        "outcome_relative_path": chain.outcome_path.relative_to(
                            output_dir
                        ).as_posix(),
                        "checkpoint_relative_path": chain.checkpoint_path.relative_to(
                            output_dir
                        ).as_posix(),
                        "raw_sha256": _file_sha(chain.raw_path),
                        "result_sha256": _file_sha(chain.result_path),
                        "trace_sha256": _file_sha(chain.trace_path),
                        "outcome_sha256": _file_sha(chain.outcome_path),
                        "checkpoint_sha256": _file_sha(chain.checkpoint_path),
                        "persistence_sequence": chain.sequence,
                    },
                    field="record_id",
                    prefix="finance_v26_212_scripted_evidence_record:",
                ),
            )
        )
    return cast(
        models.ScriptedPersistenceAudit,
        models.make_identity(
            models.ScriptedPersistenceAudit,
            {
                "consumer_binding_id": consumer.binding_id,
                "composition_contract_id": composition.contract_id,
                "run_start_receipt_id": run_start.receipt_id,
                "v209_invocation_census_id": census.census_id,
                "v209_execution_control_audit_id": execution.audit_id,
                "records": tuple(records),
            },
            field="audit_id",
            prefix="finance_v26_212_scripted_persistence_audit:",
        ),
    )


def _terminal_persistence_audit(
    *,
    output_dir: Path,
    terminal_binding: models.TerminalRegistryDispatcherBinding,
    writer_binding: models.RawResultWriterBinding,
    trace_binding: models.TraceOutcomeCheckpointBinding,
    implementation: models.ImplementationBinding,
) -> models.TerminalPersistenceAudit:
    dispatcher = runtime.CompleteTerminalDispatcher(terminal_binding)
    pipeline = runtime.EvidencePersistencePipeline(
        root=output_dir,
        raw_result_binding=writer_binding,
        trace_outcome_checkpoint_binding=trace_binding,
    )
    controls: list[models.TerminalPersistenceControl] = []
    for terminal_kind, policy_id in zip(
        terminal_binding.terminal_kinds,
        terminal_binding.terminal_policy_ids,
        strict=True,
    ):
        job_id = canonical_hash(
            {
                "terminal_kind": terminal_kind,
                "policy_id": policy_id,
                "implementation_binding_id": implementation.binding_id,
            },
            prefix="finance_v26_212_terminal_control_job:",
        )
        source_binding_id = canonical_hash(
            {
                "terminal_kind": terminal_kind,
                "policy_id": policy_id,
                "dispatcher_symbol_sha256": terminal_binding.dispatcher_symbol_sha256,
                "runtime_file_sha256": next(
                    item.sha256
                    for item in implementation.files
                    if item.relative_path == RUNTIME_FILE
                ),
            },
            prefix="finance_v26_212_terminal_control_source_binding:",
        )
        signal, decision = dispatcher.dispatch(
            terminal_kind=terminal_kind,
            source_binding_id=source_binding_id,
            job_id=job_id,
        )
        chain = pipeline.persist(
            namespace="terminal_controls",
            job_id=job_id,
            source_binding_id=source_binding_id,
            invocation_ids=(source_binding_id, policy_id),
            terminal_signal=signal,
            terminal_decision=decision,
        )
        controls.append(
            cast(
                models.TerminalPersistenceControl,
                models.make_identity(
                    models.TerminalPersistenceControl,
                    {
                        "terminal_kind": terminal_kind,
                        "terminal_policy_id": policy_id,
                        "terminal_signal_id": signal["signal_id"],
                        "terminal_decision_id": decision["decision_id"],
                        "raw_id": chain.raw["raw_id"],
                        "result_id": chain.result["result_id"],
                        "trace_id": chain.trace["trace_id"],
                        "outcome_id": chain.outcome["outcome_id"],
                        "checkpoint_id": chain.checkpoint["checkpoint_id"],
                    },
                    field="control_id",
                    prefix="finance_v26_212_terminal_persistence_control:",
                ),
            )
        )
    return cast(
        models.TerminalPersistenceAudit,
        models.make_identity(
            models.TerminalPersistenceAudit,
            {
                "terminal_registry_dispatcher_binding_id": terminal_binding.binding_id,
                "trace_outcome_checkpoint_binding_id": trace_binding.binding_id,
                "controls": tuple(controls),
            },
            field="audit_id",
            prefix="finance_v26_212_terminal_persistence_audit:",
        ),
    )


def _gate(name: str, evidence_id: str) -> models.GateResult:
    return cast(
        models.GateResult,
        models.make_identity(
            models.GateResult,
            {"gate_name": name, "evidence_id": evidence_id},
            field="gate_id",
            prefix="finance_v26_212_consumer_terminal_persistence_gate:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.RepairReport:
    if output_dir.exists():
        raise FileExistsError(f"v26.212 output already exists:{output_dir}")
    external, review_bytes, directive_bytes = _external_authorization(external_review_path)
    freeze, v211_authorization, authorization_bytes = _v211_freeze(
        repository_root=repository_root,
        external_authorization_id=external.authorization_id,
    )
    source = _source_identity(source_identity)
    implementation = _implementation_binding(
        repository_root=repository_root,
        external_authorization_id=external.authorization_id,
        freeze_id=freeze.freeze_id,
        source_identity=source,
    )
    (
        v209_implementation,
        v209_manifest,
        v209_runner,
        v209_execution,
        saved_census,
        saved_execution,
    ) = _load_v209_objects(repository_root)
    registry = outcome_authority.FreshTerminalRegistry.model_validate(
        _load(repository_root / V195_DIR / "fresh_terminal_registry.json")
    )
    (
        consumption_contract,
        run_start_contract,
        transport_binding,
        terminal_binding,
        writer_binding,
        trace_binding,
        consumer_binding,
        composition,
    ) = _mechanism_bindings(
        implementation=implementation,
        freeze=freeze,
        v211_authorization=v211_authorization,
        v209_implementation=v209_implementation,
        v209_manifest=v209_manifest,
        v209_runner=v209_runner,
        v209_execution=v209_execution,
        registry=registry,
    )
    ingress, consumption_receipt, run_start_receipt, products = _ingress_order_audit(
        output_dir=output_dir,
        consumption_contract=consumption_contract,
        run_start_contract=run_start_contract,
        consumer_binding=consumer_binding,
        composition=composition,
        v211_authorization=v211_authorization,
        authorization_bytes=authorization_bytes,
        manifest=v209_manifest,
    )
    parents = v209._predecessor_freeze(
        repository_root=repository_root,
        authorization_id=external.authorization_id,
    )
    config = AgentModelConfig.model_validate(_load(repository_root / MODEL_PROFILE)["model"])
    with tempfile.TemporaryDirectory(prefix="v26_212_prepared_") as temporary:
        prepared = v188.prepare_execution(
            package_root=repository_root / "trusted_data_synthesis",
            output_dir=Path(temporary) / "provider_forbidden",
        )
        census, execution = runtime.execute_exact_v209_runner(
            manifest=v209_manifest,
            execution=v209_execution,
            implementation=v209_implementation,
            parents=parents,
            prepared=prepared,
            config=config,
            transport_factory=products.transport_factory,
        )
    if (
        census != saved_census
        or execution != saved_execution
        or products.transport_factory.construction_count != 192
        or sum(len(item.dispatches) for item in products.transport_factory.transports) != 792
        or any(item.provider_calls for item in products.transport_factory.transports)
    ):
        _fail("runner.replay", "v26.212 exact v26.209 Runner replay differs")
    scripted = _scripted_persistence_audit(
        output_dir=output_dir,
        consumer=consumer_binding,
        composition=composition,
        run_start=run_start_receipt,
        terminal_binding=terminal_binding,
        writer_binding=writer_binding,
        trace_binding=trace_binding,
        census=census,
        execution=execution,
    )
    terminal = _terminal_persistence_audit(
        output_dir=output_dir,
        terminal_binding=terminal_binding,
        writer_binding=writer_binding,
        trace_binding=trace_binding,
        implementation=implementation,
    )
    mutations = _source_mutation_audit(
        consumer=consumer_binding,
        composition=composition,
    )
    scope = cast(
        models.ScopeBoundaryAudit,
        models.make_identity(
            models.ScopeBoundaryAudit,
            {
                "external_authorization_id": external.authorization_id,
                "v211_freeze_id": freeze.freeze_id,
                "consumer_binding_id": consumer_binding.binding_id,
            },
            field="audit_id",
            prefix="finance_v26_212_scope_boundary_audit:",
        ),
    )
    gates = cast(
        models.GateEvaluation,
        models.make_identity(
            models.GateEvaluation,
            {
                "gates": (
                    _gate("external_scope_and_exact_v211_freeze", freeze.freeze_id),
                    _gate("source_bound_consumer_and_composition", implementation.binding_id),
                    _gate("durable_consumption_receipt_factory_order", ingress.audit_id),
                    _gate("exact_v209_runner_and_192_job_persistence", scripted.audit_id),
                    _gate("complete_16_terminal_persistence", terminal.audit_id),
                    _gate("fully_rehashed_source_parent_attacks", mutations.audit_id),
                    _gate("zero_provider_credential_empirical_boundary", scope.audit_id),
                )
            },
            field="evaluation_id",
            prefix="finance_v26_212_consumer_terminal_persistence_gate_evaluation:",
        ),
    )
    decision = cast(
        models.RepairDecision,
        models.make_identity(
            models.RepairDecision,
            {
                "external_authorization_id": external.authorization_id,
                "v211_freeze_id": freeze.freeze_id,
                "composition_contract_id": composition.contract_id,
                "ingress_order_audit_id": ingress.audit_id,
                "scripted_persistence_audit_id": scripted.audit_id,
                "terminal_persistence_audit_id": terminal.audit_id,
                "source_mutation_audit_id": mutations.audit_id,
                "gate_evaluation_id": gates.evaluation_id,
            },
            field="decision_id",
            prefix="finance_v26_212_repair_decision:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        models.make_identity(
            models.ProspectiveTransition,
            {
                "decision_id": decision.decision_id,
                "composition_contract_id": composition.contract_id,
            },
            field="transition_id",
            prefix="finance_v26_212_transition:",
        ),
    )
    report = cast(
        models.RepairReport,
        models.make_identity(
            models.RepairReport,
            {
                "run_id": RUN_ID,
                "source_identity_id": source.source_identity_id,
                "external_authorization_id": external.authorization_id,
                "v211_freeze_id": freeze.freeze_id,
                "consumer_binding_id": consumer_binding.binding_id,
                "composition_contract_id": composition.contract_id,
                "ingress_order_audit_id": ingress.audit_id,
                "scripted_persistence_audit_id": scripted.audit_id,
                "terminal_persistence_audit_id": terminal.audit_id,
                "source_mutation_audit_id": mutations.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "gate_evaluation_id": gates.evaluation_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
            },
            field="report_id",
            prefix="finance_v26_212_consumer_terminal_persistence_report:",
        ),
    )
    payloads = {
        "external_review.txt": review_bytes,
        "operator_authorization.txt": directive_bytes,
        "external_repair_authorization.json": _bytes(external),
        "v211_freeze.json": _bytes(freeze),
        "implementation_binding.json": _bytes(implementation),
        "authorization_consumption_receipt_contract.json": _bytes(consumption_contract),
        "run_start_receipt_contract.json": _bytes(run_start_contract),
        "provider_transport_implementation_binding.json": _bytes(transport_binding),
        "terminal_registry_dispatcher_binding.json": _bytes(terminal_binding),
        "raw_result_writer_binding.json": _bytes(writer_binding),
        "trace_outcome_checkpoint_binding.json": _bytes(trace_binding),
        "online_execution_consumer_implementation_binding.json": _bytes(consumer_binding),
        "repaired_composition_contract.json": _bytes(composition),
        "ingress_order_audit.json": _bytes(ingress),
        "scripted_persistence_audit.json": _bytes(scripted),
        "terminal_persistence_audit.json": _bytes(terminal),
        "source_mutation_audit.json": _bytes(mutations),
        "scope_boundary_audit.json": _bytes(scope),
        "gate_evaluation.json": _bytes(gates),
        "repair_decision.json": _bytes(decision),
        "prospective_transition.json": _bytes(transition),
        "source_identity.json": _bytes(source),
        "report.json": _bytes(report),
    }
    for name, payload in sorted(payloads.items()):
        _write(output_dir / name, payload)
    manifest_payloads = {
        path.relative_to(output_dir).as_posix(): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    }
    artifact = models.artifact_manifest(RUN_ID, manifest_payloads)
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
