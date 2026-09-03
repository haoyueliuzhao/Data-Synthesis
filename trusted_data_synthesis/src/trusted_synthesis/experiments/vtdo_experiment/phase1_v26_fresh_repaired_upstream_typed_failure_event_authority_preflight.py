# ruff: noqa: E501
from __future__ import annotations

import argparse
import ast
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
    phase1_v26_fresh_repaired_typed_failure_exit_provenance_models as v216_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_typed_failure_exit_provenance_runtime as v216_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_runtime as runtime,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = (
    "finance_v26_217_fresh_repaired_upstream_typed_failure_event_authority_"
    "and_artifact_backing_preflight_v1_20260903"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
REVIEW_SHA256: Final = "b63396f5321a6c99cf6fade8fd501a8387a7e172470250b2e931413afc4ba871"
REVIEW_BYTES: Final = 14_940
OPERATOR_DIRECTIVE: Final = "参照审计报告继续实验修订"
V216_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_216_fresh_repaired_actual_v209_typed_failure_exit_surface_"
    "callsite_and_rethrow_provenance_preflight_v1_20260903"
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
V209_SOURCE_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight.py"
)
V216_RUNTIME_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_typed_failure_exit_provenance_runtime.py"
)
RUNTIME_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_runtime.py"
)
IMPLEMENTATION_FILES: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_runtime.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_preflight.py",
    "trusted_data_synthesis/tests/test_v26_fresh_repaired_upstream_typed_failure_event_authority_preflight.py",
)
SYMBOLS: Final = (
    (
        runtime.UpstreamEventArtifactAuthority.record_instrument_failure,
        "UpstreamEventArtifactAuthority.record_instrument_failure",
        RUNTIME_FILE,
    ),
    (
        runtime.BoundUpstreamInstrumentEventSource.emit_instrument_failure,
        "BoundUpstreamInstrumentEventSource.emit_instrument_failure",
        RUNTIME_FILE,
    ),
    (
        runtime.ArtifactBackedUpstreamFailureObserver.observe_failure,
        "ArtifactBackedUpstreamFailureObserver.observe_failure",
        RUNTIME_FILE,
    ),
    (
        runtime.ArtifactBackedUpstreamFailureAuthority.record_observation,
        "ArtifactBackedUpstreamFailureAuthority.record_observation",
        RUNTIME_FILE,
    ),
    (
        runtime.SourceExitProofAuthority.record_transport_exit,
        "SourceExitProofAuthority.record_transport_exit",
        RUNTIME_FILE,
    ),
    (runtime.ExitTracingScriptedTransport.send, "ExitTracingScriptedTransport.send", RUNTIME_FILE),
    (
        v216_runtime.ExitProvenanceRunner._invoke_current_state,
        "ExitProvenanceRunner._invoke_current_state",
        V216_RUNTIME_FILE,
    ),
    (
        runtime.ArtifactBackedExitProvenanceRunner._terminalize_actual_failure,
        "ArtifactBackedExitProvenanceRunner._terminalize_actual_failure",
        RUNTIME_FILE,
    ),
    (
        runtime.RunnerFailureObservationAuthority.record_from_runner,
        "RunnerFailureObservationAuthority.record_from_runner",
        RUNTIME_FILE,
    ),
    (
        runtime.ArtifactBackedExitDispatcher.dispatch,
        "ArtifactBackedExitDispatcher.dispatch",
        RUNTIME_FILE,
    ),
    (
        runtime.ArtifactBackedExitPersistencePipeline.persist,
        "ArtifactBackedExitPersistencePipeline.persist",
        RUNTIME_FILE,
    ),
    (runtime.ConsumerParentGuard.admit, "ConsumerParentGuard.admit", RUNTIME_FILE),
    (
        runtime.ArtifactBackedFailureConsumer.execute_preflight,
        "ArtifactBackedFailureConsumer.execute_preflight",
        RUNTIME_FILE,
    ),
    (runtime._upstream_authority_attacks, "_upstream_authority_attacks", RUNTIME_FILE),
)


class V217Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V217Error(stage, reason)


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
        _fail("authorization.review", "v26.217 external review bytes differ")
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
            prefix="finance_v26_217_external_revision_authorization:",
        ),
    )
    return authorization, review, directive


def _v216_freeze(*, repository_root: Path, external_authorization_id: str) -> models.V216Freeze:
    root = repository_root / V216_DIR
    artifact = v216_models.ArtifactManifest.model_validate(_load(root / "artifact_manifest.json"))
    files = tuple(sorted(path for path in root.rglob("*") if path.is_file()))
    members = {item.relative_path: item for item in artifact.members}
    actual_names = {
        path.relative_to(root).as_posix() for path in files if path.name != "artifact_manifest.json"
    }
    if set(members) != actual_names:
        _fail("freeze.paths", "v26.216 formal path set differs")
    for name, member in members.items():
        payload = (root / name).read_bytes()
        if len(payload) != member.byte_count or _sha(payload) != member.sha256:
            _fail("freeze.bytes", f"v26.216 formal member differs:{name}")
    if (
        len(files) != 50
        or sum(path.stat().st_size for path in files) != 1_038_367
        or artifact.file_count != 49
        or artifact.total_byte_count != 1_029_127
        or artifact.manifest_id
        != "finance_v26_216_artifact_manifest:79dcd85ab4f51995140d1c617c80f390f03108450f7ca9dfc11362d73d4054de"
        or artifact.artifact_root
        != "finance_v26_216_artifact_root:f6f63cf1a7b2dac420011a8d30bf621071b70255a3eda4d2841295ebe2fc19a0"
    ):
        _fail("freeze.geometry", "v26.216 formal geometry differs")
    report = v216_models.Report.model_validate(_load(root / "report.json"))
    decision = v216_models.Decision.model_validate(_load(root / "decision.json"))
    transition = v216_models.Transition.model_validate(_load(root / "prospective_transition.json"))
    source = v216_models.SourceIdentity.model_validate(_load(root / "source_identity.json"))
    if (
        report.report_id
        != "finance_v26_216_exit_provenance_report:5cd18205461952e0b3ec10322df11bc4116b7c61e89fd0409bb51c27d598bfbb"
        or decision.decision_id
        != "finance_v26_216_exit_provenance_decision:31626a5629847fb9669d296d17463fd735eb9648f31e782eadb345fae613fd68"
        or transition.transition_id
        != "finance_v26_216_transition:ce42bba3aa26130be7ab5be70f9859c1e64b04be43bd29f014d2b36408605b18"
        or report.decision_id != decision.decision_id
        or report.transition_id != transition.transition_id
        or source.source_commit != "a3e6589a71cbf40b0c93488343e406641f0d017a"
        or source.source_tree != "ed56a5dfaa45510535647343b534db557fb3aefd"
        or report.current_v211_authorization_consumed
        or report.provider_calls != 0
    ):
        _fail("freeze.semantics", "v26.216 formal authority differs")
    return cast(
        models.V216Freeze,
        models.make_identity(
            models.V216Freeze,
            {
                "external_authorization_id": external_authorization_id,
                "v216_report_id": report.report_id,
                "v216_decision_id": decision.decision_id,
                "v216_transition_id": transition.transition_id,
                "v216_artifact_manifest_id": artifact.manifest_id,
                "v216_artifact_root": artifact.artifact_root,
            },
            field="freeze_id",
            prefix="finance_v26_217_v216_freeze:",
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
            prefix="finance_v26_217_source_identity:",
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
            _fail("source.tree", "v26.217 source tree differs")
    files: list[models.SourceBinding] = []
    for relative in IMPLEMENTATION_FILES:
        live = (repository_root / relative).read_bytes()
        if source.source_commit != "1" * 40:
            committed = _git(repository_root, "show", f"{source.source_commit}:{relative}")
            if committed != live:
                _fail("source.file", f"v26.217 live source differs:{relative}")
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
            relative_path=relative,
            symbol=name,
            sha256=_sha(inspect.getsource(symbol).encode("utf-8")),
            byte_count=len(inspect.getsource(symbol).encode("utf-8")),
        )
        for symbol, name, relative in SYMBOLS
    )
    dispatcher_parameters = tuple(
        inspect.signature(runtime.ArtifactBackedExitDispatcher.dispatch).parameters
    )
    observer_parameters = tuple(
        inspect.signature(runtime.ArtifactBackedUpstreamFailureObserver.observe_failure).parameters
    )
    event_source_parameters = tuple(
        inspect.signature(
            runtime.BoundUpstreamInstrumentEventSource.emit_instrument_failure
        ).parameters
    )
    runner_source = inspect.getsource(v216_runtime.ExitProvenanceRunner._invoke_current_state)
    terminalizer_source = inspect.getsource(
        runtime.ArtifactBackedExitProvenanceRunner._terminalize_actual_failure
    )
    event_source = inspect.getsource(
        runtime.BoundUpstreamInstrumentEventSource.emit_instrument_failure
    )
    observer_source = inspect.getsource(
        runtime.ArtifactBackedUpstreamFailureObserver.observe_failure
    )
    runtime_source = (repository_root / RUNTIME_FILE).read_text(encoding="utf-8")
    forbidden = ("os.environ", "os.getenv", "requests.", "urllib.", "httpx.", "socket.")
    if (
        dispatcher_parameters != ("self", "evidence")
        or observer_parameters != ("self", "event")
        or event_source_parameters
        != ("self", "source_job_id", "source_invocation_request_parent_id")
        or runner_source.count("except v209.TypedTransportFailure as error:") != 2
        or "require_for_runner(error)" not in terminalizer_source
        or "record_from_runner(observation)" not in terminalizer_source
        or any(token in event_source for token in ("terminal_kind:", "reason:", "source_event_id:"))
        or "strict_event.reason" not in observer_source
        or "admitted_event_terminal_policy_items" not in observer_source
        or any(item in runtime_source for item in forbidden)
    ):
        _fail("source.interface", "v26.217 source-derived event or zero-network interface differs")
    return cast(
        models.ImplementationBinding,
        models.make_identity(
            models.ImplementationBinding,
            {
                "external_authorization_id": external_authorization_id,
                "v216_freeze_id": freeze_id,
                "source_commit": source.source_commit,
                "source_tree": source.source_tree,
                "files": tuple(files),
                "symbols": symbols,
            },
            field="binding_id",
            prefix="fresh_repaired_upstream_typed_failure_event_authority_implementation_binding:",
        ),
    )


def _symbol_sha(binding: models.ImplementationBinding, name: str) -> str:
    values = tuple(item.sha256 for item in binding.symbols if item.symbol == name)
    if len(values) != 1:
        _fail("source.symbol", f"v26.217 symbol binding differs:{name}")
    return values[0]


def _source_contract(
    *, repository_root: Path, implementation: models.ImplementationBinding
) -> models.TypedFailureExitSurfaceContract:
    live = (repository_root / V209_SOURCE_FILE).read_bytes()
    frozen = _git(
        repository_root,
        "show",
        f"5809e9782515e55ee797b43730584d5d860aaa5c:{V209_SOURCE_FILE}",
    )
    if (
        live != frozen
        or _sha(live) != "4529523fc737f26801118cc5cf78b682f2e510c5f887ed0d14a60a5bd26d9b35"
    ):
        _fail("source.v209", "exact v26.209 source bytes differ")
    tree = ast.parse(live.decode("utf-8"), filename=V209_SOURCE_FILE)
    scripted = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ScriptedTransport"
    )
    send = next(
        node for node in scripted.body if isinstance(node, ast.FunctionDef) and node.name == "send"
    )
    projection = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_project_public_payload"
    )
    expected = (
        (
            "E0_invalid_dispatch_chain",
            "ScriptedTransport.send",
            "transport_send",
            "direct_constructor",
            647,
            "instrument_failure",
            "injected transport received an invalid request/certificate/receipt chain",
        ),
        (
            "E1_empty_queue",
            "ScriptedTransport.send",
            "transport_send",
            "direct_constructor",
            652,
            "instrument_failure",
            "injected scripted transport queue is empty",
        ),
        (
            "E2_authenticated_rethrow",
            "ScriptedTransport.send",
            "transport_send",
            "authenticated_rethrow",
            658,
            None,
            None,
        ),
        (
            "E3_reasoning_key",
            "_project_public_payload",
            "public_projection",
            "direct_constructor",
            819,
            "privacy_rejection",
            "public response contains a classifier-sensitive private key",
        ),
        (
            "E4_non_object",
            "_project_public_payload",
            "public_projection",
            "direct_constructor",
            824,
            "instrument_failure",
            "public response is not a JSON object",
        ),
    )
    found = tuple(
        sorted(
            (node.lineno, node, symbol, origin)
            for function, symbol, origin in (
                (send, "ScriptedTransport.send", "transport_send"),
                (projection, "_project_public_payload", "public_projection"),
            )
            for node in ast.walk(function)
            if isinstance(node, ast.Raise)
        )
    )
    if len(found) != 5:
        _fail("source.ast", "v26.209 typed-failure exit count differs")
    declarations: list[models.SourceExitDeclaration] = []
    symbol_ids: dict[str, str] = {}
    for observed, declared in zip(found, expected, strict=True):
        line, node, symbol, origin = observed
        exit_code, expected_symbol, expected_origin, kind, expected_line, terminal, reason = (
            declared
        )
        if line != expected_line or symbol != expected_symbol or origin != expected_origin:
            _fail("source.ast", f"v26.209 source exit coordinate differs:{exit_code}")
        if kind == "direct_constructor":
            if not (
                isinstance(node.exc, ast.Call)
                and isinstance(node.exc.func, ast.Name)
                and node.exc.func.id == "TypedTransportFailure"
                and len(node.exc.args) == 2
                and isinstance(node.exc.args[0], ast.Constant)
                and isinstance(node.exc.args[1], ast.Constant)
                and node.exc.args[0].value == terminal
                and node.exc.args[1].value == reason
            ):
                _fail("source.ast", f"v26.209 direct constructor differs:{exit_code}")
        elif not isinstance(node.exc, ast.Name) or node.exc.id != "value":
            _fail("source.ast", "v26.209 queued typed-failure rethrow differs")
        if symbol not in symbol_ids:
            function = send if symbol == "ScriptedTransport.send" else projection
            symbol_ids[symbol] = models.canonical_hash(
                {
                    "source_relative_path": V209_SOURCE_FILE,
                    "source_symbol": symbol,
                    "symbol_ast_sha256": _sha(
                        ast.dump(function, include_attributes=True).encode("utf-8")
                    ),
                },
                prefix="fresh_repaired_v209_typed_failure_source_symbol:",
            )
        declarations.append(
            cast(
                models.SourceExitDeclaration,
                models.make_identity(
                    models.SourceExitDeclaration,
                    {
                        "exit_code": exit_code,
                        "source_relative_path": V209_SOURCE_FILE,
                        "source_symbol": symbol,
                        "source_symbol_id": symbol_ids[symbol],
                        "source_line": line,
                        "source_col_offset": node.col_offset,
                        "source_exit_kind": kind,
                        "failure_origin": origin,
                        "direct_terminal_kind": terminal,
                        "direct_reason_sha256": _sha(reason.encode("utf-8"))
                        if reason is not None
                        else None,
                        "upstream_authority_required": kind == "authenticated_rethrow",
                        "ast_node_sha256": _sha(
                            ast.dump(node, include_attributes=True).encode("utf-8")
                        ),
                    },
                    field="source_exit_id",
                    prefix="fresh_repaired_v209_typed_failure_source_exit:",
                ),
            )
        )
    return cast(
        models.TypedFailureExitSurfaceContract,
        models.make_identity(
            models.TypedFailureExitSurfaceContract,
            {
                "implementation_binding_id": implementation.binding_id,
                "ast_module_sha256": _sha(ast.dump(tree, include_attributes=True).encode("utf-8")),
                "exits": tuple(declarations),
            },
            field="contract_id",
            prefix="fresh_repaired_actual_v209_typed_failure_exit_surface_contract:",
        ),
    )


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
    freeze: models.V216Freeze,
    source_contract: models.TypedFailureExitSurfaceContract,
    manifest: v209_models.ExecutableDevelopmentManifest,
    runner: v209_models.ExecutableRunnerContract,
    v211_authorization: v211_models.ExactOnlineExecutionAuthorization,
    registry: outcome_authority.FreshTerminalRegistry,
) -> tuple[
    models.UpstreamEventSourceBinding,
    models.UpstreamObservationBinding,
    models.RunnerObservationBinding,
    models.DispatcherBinding,
    models.PersistenceBinding,
    models.ConsumerBinding,
    models.CompositionContract,
    v212_models.AuthorizationConsumptionReceiptContract,
    v212_models.RunStartReceiptContract,
]:
    reachable = tuple(
        sorted(
            (item.terminal_kind, item.policy_id)
            for item in registry.policies
            if item.registration_status == "reachable"
        )
    )
    if len(reachable) != 16:
        _fail("terminal.registry", "v26.195 reachable terminal Registry differs")
    policy_by_terminal = dict(reachable)
    event_source = cast(
        models.UpstreamEventSourceBinding,
        models.make_identity(
            models.UpstreamEventSourceBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "source_v195_terminal_registry_id": registry.registry_id,
                "admitted_event_terminal_policy_items": (
                    (
                        models.UPSTREAM_EVENT_KIND,
                        "instrument_failure",
                        policy_by_terminal["instrument_failure"],
                    ),
                ),
                "forbidden_terminal_kinds": models.FORBIDDEN_UPSTREAM_TERMINALS,
                "event_source_symbol_sha256": _symbol_sha(
                    implementation, "BoundUpstreamInstrumentEventSource.emit_instrument_failure"
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_upstream_failure_event_source_binding:",
        ),
    )
    observation = cast(
        models.UpstreamObservationBinding,
        models.make_identity(
            models.UpstreamObservationBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "event_source_binding_id": event_source.binding_id,
                "observe_failure_symbol_sha256": _symbol_sha(
                    implementation, "ArtifactBackedUpstreamFailureObserver.observe_failure"
                ),
                "authority_symbol_sha256": _symbol_sha(
                    implementation, "ArtifactBackedUpstreamFailureAuthority.record_observation"
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_upstream_failure_observation_binding:",
        ),
    )
    runner_binding = cast(
        models.RunnerObservationBinding,
        models.make_identity(
            models.RunnerObservationBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "source_contract_id": source_contract.contract_id,
                "upstream_event_source_binding_id": event_source.binding_id,
                "upstream_observation_binding_id": observation.binding_id,
                "exact_v209_runner_id": runner.runner_id,
                "inherited_v216_runner_symbol_sha256": _symbol_sha(
                    implementation, "ExitProvenanceRunner._invoke_current_state"
                ),
                "terminalizer_symbol_sha256": _symbol_sha(
                    implementation, "ArtifactBackedExitProvenanceRunner._terminalize_actual_failure"
                ),
                "source_exit_authority_symbol_sha256": _symbol_sha(
                    implementation, "SourceExitProofAuthority.record_transport_exit"
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_upstream_event_authority_runner_observation_binding:",
        ),
    )
    dispatcher = cast(
        models.DispatcherBinding,
        models.make_identity(
            models.DispatcherBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "runner_observation_binding_id": runner_binding.binding_id,
                "source_contract_id": source_contract.contract_id,
                "source_v195_terminal_registry_id": registry.registry_id,
                "dispatcher_symbol_sha256": _symbol_sha(
                    implementation, "ArtifactBackedExitDispatcher.dispatch"
                ),
                "terminal_policy_items": reachable,
            },
            field="binding_id",
            prefix="fresh_repaired_upstream_event_authority_dispatcher_binding:",
        ),
    )
    source_persistence = v216_models.PersistenceBinding.model_validate(
        _load(repository_root / V216_DIR / "persistence_binding.json")
    )
    persistence = cast(
        models.PersistenceBinding,
        models.make_identity(
            models.PersistenceBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "dispatcher_binding_id": dispatcher.binding_id,
                "source_v216_persistence_binding_id": source_persistence.binding_id,
                "persistence_symbol_sha256": _symbol_sha(
                    implementation, "ArtifactBackedExitPersistencePipeline.persist"
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_upstream_event_authority_persistence_binding:",
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
                "upstream_event_source_binding_id": event_source.binding_id,
                "upstream_observation_binding_id": observation.binding_id,
                "runner_observation_binding_id": runner_binding.binding_id,
                "dispatcher_binding_id": dispatcher.binding_id,
                "persistence_binding_id": persistence.binding_id,
                "execute_preflight_symbol_sha256": _symbol_sha(
                    implementation, "ArtifactBackedFailureConsumer.execute_preflight"
                ),
            },
            field="binding_id",
            prefix="fresh_repaired_upstream_event_authority_failure_consumer_binding:",
        ),
    )
    composition = cast(
        models.CompositionContract,
        models.make_identity(
            models.CompositionContract,
            {
                "v216_freeze_id": freeze.freeze_id,
                "source_contract_id": source_contract.contract_id,
                "upstream_event_source_binding_id": event_source.binding_id,
                "upstream_observation_binding_id": observation.binding_id,
                "consumer_binding_id": consumer.binding_id,
                "runner_observation_binding_id": runner_binding.binding_id,
                "dispatcher_binding_id": dispatcher.binding_id,
                "persistence_binding_id": persistence.binding_id,
            },
            field="contract_id",
            prefix="fresh_repaired_upstream_event_authority_composition_contract:",
        ),
    )
    return (
        event_source,
        observation,
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
            prefix="finance_v26_217_gate:",
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
        raise FileExistsError(f"v26.217 output already exists:{output_dir}")
    external, review_bytes, directive_bytes = _external_authorization(external_review_path)
    freeze = _v216_freeze(
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
    source_contract = _source_contract(
        repository_root=repository_root, implementation=implementation
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
        event_source_binding,
        observation_binding,
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
        source_contract=source_contract,
        manifest=v209_manifest,
        runner=v209_runner,
        v211_authorization=v211_authorization,
        registry=registry,
    )
    consumer = runtime.ArtifactBackedFailureConsumer(
        binding=consumer_binding,
        composition=composition,
        source_contract=source_contract,
        event_source_binding=event_source_binding,
        observation_binding=observation_binding,
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
    with tempfile.TemporaryDirectory(prefix="v26_217_prepared_") as temporary:
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
                "v216_freeze_id": freeze.freeze_id,
                "consumer_binding_id": consumer_binding.binding_id,
            },
            field="audit_id",
            prefix="finance_v26_217_scope_boundary_audit:",
        ),
    )
    gates = cast(
        models.GateEvaluation,
        models.make_identity(
            models.GateEvaluation,
            {
                "gates": (
                    _gate("external_scope_and_exact_v216_freeze", freeze.freeze_id),
                    _gate(
                        "exact_v209_five_exit_ast_contract_retained", source_contract.contract_id
                    ),
                    _gate(
                        "source_derived_upstream_event_and_restricted_terminal_domain",
                        event_source_binding.binding_id,
                    ),
                    _gate(
                        "durable_upstream_event_observation_artifact_chain",
                        observation_binding.binding_id,
                    ),
                    _gate(
                        "five_actual_v209_source_exit_controls_terminalize",
                        executed.execution_audit.audit_id,
                    ),
                    _gate(
                        "artifact_backed_exit_terminal_to_five_layer_persistence",
                        persistence_binding.binding_id,
                    ),
                    _gate(
                        "five_upstream_authority_attacks_reject", executed.negative_audit.audit_id
                    ),
                    _gate("zero_provider_credential_empirical_boundary", scope.audit_id),
                )
            },
            field="evaluation_id",
            prefix="finance_v26_217_gate_evaluation:",
        ),
    )
    decision = cast(
        models.Decision,
        models.make_identity(
            models.Decision,
            {
                "external_authorization_id": external.authorization_id,
                "v216_freeze_id": freeze.freeze_id,
                "composition_contract_id": composition.contract_id,
                "execution_audit_id": executed.execution_audit.audit_id,
                "negative_control_audit_id": executed.negative_audit.audit_id,
                "gate_evaluation_id": gates.evaluation_id,
            },
            field="decision_id",
            prefix="finance_v26_217_upstream_event_authority_decision:",
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
            prefix="finance_v26_217_transition:",
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
                "v216_freeze_id": freeze.freeze_id,
                "source_contract_id": source_contract.contract_id,
                "upstream_event_source_binding_id": event_source_binding.binding_id,
                "upstream_observation_binding_id": observation_binding.binding_id,
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
            prefix="finance_v26_217_upstream_event_authority_report:",
        ),
    )
    payloads = {
        "external_review.txt": review_bytes,
        "operator_authorization.txt": directive_bytes,
        "external_revision_authorization.json": _bytes(external),
        "v216_freeze.json": _bytes(freeze),
        "implementation_binding.json": _bytes(implementation),
        "typed_failure_exit_surface_contract.json": _bytes(source_contract),
        "upstream_event_source_binding.json": _bytes(event_source_binding),
        "upstream_observation_binding.json": _bytes(observation_binding),
        "runner_observation_binding.json": _bytes(runner_binding),
        "dispatcher_binding.json": _bytes(dispatcher_binding),
        "persistence_binding.json": _bytes(persistence_binding),
        "consumer_binding.json": _bytes(consumer_binding),
        "composition_contract.json": _bytes(composition),
        "preflight_consumption_receipt.json": _bytes(executed.consumption_receipt),
        "preflight_run_start_receipt.json": _bytes(executed.run_start_receipt),
        "exit_surface_execution_audit.json": _bytes(executed.execution_audit),
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
