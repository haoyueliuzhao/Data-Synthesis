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
    phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_runtime as runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_models as v217_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_preflight as v217_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_runtime as v217_runtime,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = (
    "finance_v26_218_fresh_repaired_upstream_terminal_domain_exact_registry_"
    "complement_binding_preflight_v1_20260903"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
REVIEW_SHA256: Final = "4af91cc69d550143fc21f8c8afd0adb61ac3377d6dc51fe0994db3dda397b21f"
REVIEW_BYTES: Final = 14_305
OPERATOR_DIRECTIVE: Final = "参照审计报告继续实验修订"
V217_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_217_fresh_repaired_upstream_typed_failure_event_authority_"
    "and_artifact_backing_preflight_v1_20260903"
)
MODELS_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_models.py"
)
RUNTIME_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_runtime.py"
)
PREFLIGHT_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_preflight.py"
)
TEST_FILE: Final = (
    "trusted_data_synthesis/tests/"
    "test_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_preflight.py"
)
IMPLEMENTATION_FILES: Final = tuple(sorted((MODELS_FILE, RUNTIME_FILE, PREFLIGHT_FILE, TEST_FILE)))


class V218Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V218Error(stage, reason)


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
        _fail("authorization.review", "v26.218 external review bytes differ")
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
            prefix="finance_v26_218_external_revision_authorization:",
        ),
    )
    return authorization, review, directive


def _v217_freeze(*, repository_root: Path, external_authorization_id: str) -> models.V217Freeze:
    root = repository_root / V217_DIR
    artifact = v217_models.ArtifactManifest.model_validate(_load(root / "artifact_manifest.json"))
    files = tuple(sorted(path for path in root.rglob("*") if path.is_file()))
    members = {item.relative_path: item for item in artifact.members}
    actual_names = {
        path.relative_to(root).as_posix() for path in files if path.name != "artifact_manifest.json"
    }
    if set(members) != actual_names:
        _fail("freeze.paths", "v26.217 formal path set differs")
    for name, member in members.items():
        payload = (root / name).read_bytes()
        if len(payload) != member.byte_count or _sha(payload) != member.sha256:
            _fail("freeze.bytes", f"v26.217 formal member differs:{name}")
    if (
        len(files) != 59
        or sum(path.stat().st_size for path in files) != 1_075_394
        or artifact.file_count != 58
        or artifact.total_byte_count != 1_064_349
        or artifact.manifest_id
        != "finance_v26_217_artifact_manifest:fe76430540c9cede679dbc67673dc62f94ae657e7e30fe6611901d725a0ce0de"
        or artifact.artifact_root
        != "finance_v26_217_artifact_root:dc123eaae7eae0e0bb9ad613b4b6e3a2ace675c780042fabc68b117c40d9fb21"
    ):
        _fail("freeze.geometry", "v26.217 formal geometry differs")
    report = v217_models.Report.model_validate(_load(root / "report.json"))
    decision = v217_models.Decision.model_validate(_load(root / "decision.json"))
    transition = v217_models.Transition.model_validate(_load(root / "prospective_transition.json"))
    source = v217_models.SourceIdentity.model_validate(_load(root / "source_identity.json"))
    if (
        report.report_id
        != "finance_v26_217_upstream_event_authority_report:69ecfea5345ed4ffb175a604bec5f94ee2517b9a0af425eba0b60e0fa7a7daa8"
        or decision.decision_id
        != "finance_v26_217_upstream_event_authority_decision:58111a628e66aa1a99d3501dddea02c27cd9471cbdfa5bd5264e8ec6a03532bd"
        or transition.transition_id
        != "finance_v26_217_transition:98c4f108f006d9df72a3c727f80f5c09ac70b853180ddbfc42eb4e5a1677dd4e"
        or source.source_commit != "650911314b8a65d7c7480ae405f983ca6083e114"
        or source.source_tree != "57fb9b657378174651c3e841d942314c8d1bdb83"
        or report.current_v211_authorization_consumed
        or report.provider_calls != 0
    ):
        _fail("freeze.semantics", "v26.217 formal authority differs")
    return cast(
        models.V217Freeze,
        models.make_identity(
            models.V217Freeze,
            {
                "external_authorization_id": external_authorization_id,
                "v217_report_id": report.report_id,
                "v217_decision_id": decision.decision_id,
                "v217_transition_id": transition.transition_id,
                "v217_artifact_manifest_id": artifact.manifest_id,
                "v217_artifact_root": artifact.artifact_root,
            },
            field="freeze_id",
            prefix="finance_v26_218_v217_freeze:",
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
            prefix="finance_v26_218_source_identity:",
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
            _fail("source.tree", "v26.218 source tree differs")
    files: list[models.SourceBinding] = []
    for relative in IMPLEMENTATION_FILES:
        live = (repository_root / relative).read_bytes()
        if source.source_commit != "1" * 40:
            committed = _git(repository_root, "show", f"{source.source_commit}:{relative}")
            if committed != live:
                _fail("source.file", f"v26.218 live source differs:{relative}")
        files.append(
            models.SourceBinding(
                relative_path=relative,
                symbol="<file>",
                sha256=_sha(live),
                byte_count=len(live),
            )
        )
    symbol_values = (
        (
            runtime.LifetimeStableSourceExitProofAuthority,
            "LifetimeStableSourceExitProofAuthority",
            RUNTIME_FILE,
        ),
        (
            runtime.ExactRegistryComplementAuthority.admit,
            "ExactRegistryComplementAuthority.admit",
            RUNTIME_FILE,
        ),
        (
            runtime.ExactComplementFailureConsumer.execute_preflight,
            "ExactComplementFailureConsumer.execute_preflight",
            RUNTIME_FILE,
        ),
        (
            runtime.run_same_length_full_rehash_attack,
            "run_same_length_full_rehash_attack",
            RUNTIME_FILE,
        ),
        (build, "build", PREFLIGHT_FILE),
    )
    symbols = tuple(
        models.SourceBinding(
            relative_path=relative,
            symbol=name,
            sha256=_sha(inspect.getsource(symbol).encode("utf-8")),
            byte_count=len(inspect.getsource(symbol).encode("utf-8")),
        )
        for symbol, name, relative in symbol_values
    )
    authority_parameters = tuple(
        inspect.signature(runtime.ExactRegistryComplementAuthority.admit).parameters
    )
    attack_source = inspect.getsource(runtime.run_same_length_full_rehash_attack)
    complement_source = inspect.getsource(_complement_binding)
    runtime_source = (repository_root / RUNTIME_FILE).read_text(encoding="utf-8")
    forbidden_routes = ("os.environ", "os.getenv", "requests.", "urllib.", "httpx.", "socket.")
    if (
        authority_parameters != ("self", "candidate")
        or "provider_failure_no_payload" not in attack_source
        or "resource_budget_exhausted" not in attack_source
        or "provider_no_payload_failure" not in attack_source
        or "resource_failure" not in attack_source
        or "reachable_terminal_policy_items" not in complement_source
        or "FORBIDDEN_UPSTREAM_TERMINALS" in complement_source
        or any(item in runtime_source for item in forbidden_routes)
    ):
        _fail("source.interface", "v26.218 Registry-complement or zero-network source differs")
    return cast(
        models.ImplementationBinding,
        models.make_identity(
            models.ImplementationBinding,
            {
                "external_authorization_id": external_authorization_id,
                "v217_freeze_id": freeze_id,
                "source_commit": source.source_commit,
                "source_tree": source.source_tree,
                "files": tuple(files),
                "symbols": symbols,
            },
            field="binding_id",
            prefix="fresh_repaired_upstream_terminal_domain_implementation_binding:",
        ),
    )


def _complement_binding(
    *,
    implementation: models.ImplementationBinding,
    registry: outcome_authority.FreshTerminalRegistry,
    v217_event_source: v217_models.UpstreamEventSourceBinding,
) -> models.ExactRegistryComplementBinding:
    reachable = tuple(
        sorted(
            (item.terminal_kind, item.policy_id)
            for item in registry.policies
            if item.registration_status == "reachable"
        )
    )
    admitted_mapping = tuple(v217_event_source.admitted_event_terminal_policy_items)
    admitted = tuple(sorted({item[1] for item in admitted_mapping}))
    reachable_kinds = {item[0] for item in reachable}
    forbidden = tuple(sorted(reachable_kinds - set(admitted)))
    return cast(
        models.ExactRegistryComplementBinding,
        models.make_identity(
            models.ExactRegistryComplementBinding,
            {
                "implementation_binding_id": implementation.binding_id,
                "v217_event_source_binding_id": v217_event_source.binding_id,
                "exact_v195_terminal_registry_id": registry.registry_id,
                "reachable_terminal_policy_items": reachable,
                "admitted_event_terminal_policy_items": admitted_mapping,
                "admitted_terminal_kinds": admitted,
                "forbidden_terminal_kinds": forbidden,
            },
            field="binding_id",
            prefix="fresh_repaired_exact_v195_registry_complement_binding:",
        ),
    )


def _load_v217_runtime_parents(repository_root: Path) -> dict[str, Any]:
    root = repository_root / V217_DIR
    return {
        "source_contract": v217_models.TypedFailureExitSurfaceContract.model_validate(
            _load(root / "typed_failure_exit_surface_contract.json")
        ),
        "event_source": v217_models.UpstreamEventSourceBinding.model_validate(
            _load(root / "upstream_event_source_binding.json")
        ),
        "observation": v217_models.UpstreamObservationBinding.model_validate(
            _load(root / "upstream_observation_binding.json")
        ),
        "runner": v217_models.RunnerObservationBinding.model_validate(
            _load(root / "runner_observation_binding.json")
        ),
        "dispatcher": v217_models.DispatcherBinding.model_validate(
            _load(root / "dispatcher_binding.json")
        ),
        "persistence": v217_models.PersistenceBinding.model_validate(
            _load(root / "persistence_binding.json")
        ),
        "consumer": v217_models.ConsumerBinding.model_validate(
            _load(root / "consumer_binding.json")
        ),
        "composition": v217_models.CompositionContract.model_validate(
            _load(root / "composition_contract.json")
        ),
        "execution": v217_models.ExitSurfaceExecutionAudit.model_validate(
            _load(root / "exit_surface_execution_audit.json")
        ),
    }


def _composition(
    *,
    freeze: models.V217Freeze,
    complement: models.ExactRegistryComplementBinding,
    parents: dict[str, Any],
) -> models.CompositionContract:
    return cast(
        models.CompositionContract,
        models.make_identity(
            models.CompositionContract,
            {
                "v217_freeze_id": freeze.freeze_id,
                "complement_binding_id": complement.binding_id,
                "v217_source_contract_id": parents["source_contract"].contract_id,
                "v217_event_source_binding_id": parents["event_source"].binding_id,
                "v217_observation_binding_id": parents["observation"].binding_id,
                "v217_runner_binding_id": parents["runner"].binding_id,
                "v217_dispatcher_binding_id": parents["dispatcher"].binding_id,
                "v217_persistence_binding_id": parents["persistence"].binding_id,
                "v217_consumer_binding_id": parents["consumer"].binding_id,
                "v217_composition_contract_id": parents["composition"].contract_id,
            },
            field="contract_id",
            prefix="fresh_repaired_exact_registry_complement_composition_contract:",
        ),
    )


def _load_v209(repository_root: Path) -> tuple[Any, Any]:
    root = repository_root / v217_preflight.V209_DIR
    implementation = v209_models.ImplementationBinding.model_validate(
        _load(root / "implementation_binding.json")
    )
    manifest = v209_models.ExecutableDevelopmentManifest.model_validate(
        _load(root / "executable_development_manifest.json")
    )
    return implementation, manifest


def _gate(name: str, evidence_id: str) -> models.GateResult:
    return cast(
        models.GateResult,
        models.make_identity(
            models.GateResult,
            {"gate_name": name, "evidence_id": evidence_id},
            field="gate_id",
            prefix="finance_v26_218_gate:",
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
        raise FileExistsError(f"v26.218 output already exists:{output_dir}")
    external, review_bytes, directive_bytes = _external_authorization(external_review_path)
    freeze = _v217_freeze(
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
    registry = outcome_authority.FreshTerminalRegistry.model_validate(
        _load(repository_root / v217_preflight.V195_DIR / "fresh_terminal_registry.json")
    )
    parents = _load_v217_runtime_parents(repository_root)
    complement = _complement_binding(
        implementation=implementation,
        registry=registry,
        v217_event_source=parents["event_source"],
    )
    composition = _composition(freeze=freeze, complement=complement, parents=parents)
    authority = runtime.ExactRegistryComplementAuthority(
        registry=registry, expected_binding=complement
    )
    authority.admit(complement)

    v211_path = (
        repository_root / v217_preflight.V211_DIR / "exact_online_execution_authorization.json"
    )
    v211_bytes = v211_path.read_bytes()
    v211_authorization = v211_models.ExactOnlineExecutionAuthorization.model_validate(
        json.loads(v211_bytes)
    )
    v212_root = repository_root / v217_preflight.V212_DIR
    consumption = v212_models.AuthorizationConsumptionReceiptContract.model_validate(
        _load(v212_root / "authorization_consumption_receipt_contract.json")
    )
    run_start = v212_models.RunStartReceiptContract.model_validate(
        _load(v212_root / "run_start_receipt_contract.json")
    )
    base_consumer = v217_runtime.ArtifactBackedFailureConsumer(
        binding=parents["consumer"],
        composition=parents["composition"],
        source_contract=parents["source_contract"],
        event_source_binding=parents["event_source"],
        observation_binding=parents["observation"],
        runner_binding=parents["runner"],
        dispatcher_binding=parents["dispatcher"],
        persistence_binding=parents["persistence"],
        consumption_contract=consumption,
        run_start_contract=run_start,
        authorization=v211_authorization,
        authorization_bytes=v211_bytes,
    )
    consumer = runtime.ExactComplementFailureConsumer(
        binding=complement,
        composition=composition,
        authority=authority,
        v217_consumer=base_consumer,
    )
    v209_implementation, manifest = _load_v209(repository_root)
    frozen_parents = v209._predecessor_freeze(
        repository_root=repository_root,
        authorization_id=external.authorization_id,
    )
    config = AgentModelConfig.model_validate(
        _load(repository_root / v217_preflight.MODEL_PROFILE)["model"]
    )
    with tempfile.TemporaryDirectory(prefix="v26_218_prepared_") as temporary:
        prepared = v188.prepare_execution(
            package_root=repository_root / "trusted_data_synthesis",
            output_dir=Path(temporary) / "provider_forbidden",
        )
        executed = consumer.execute_preflight(
            root=output_dir,
            manifest=manifest,
            implementation=v209_implementation,
            parents=frozen_parents,
            prepared=prepared,
            config=config,
        )
    if models.canonical_bytes(executed.execution_audit) != models.canonical_bytes(
        parents["execution"]
    ):
        _fail("execution.object", "retained v26.217 execution object differs")
    actual_runtime_files = {
        path.relative_to(output_dir).as_posix(): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    if len(actual_runtime_files) != 35:
        _fail("execution.geometry", "retained v26.217 runtime file count differs")
    v217_root = repository_root / V217_DIR
    for relative, payload in actual_runtime_files.items():
        if (v217_root / relative).read_bytes() != payload:
            _fail("execution.bytes", f"retained v26.217 runtime bytes differ:{relative}")
    retained = cast(
        models.RetainedExecutionAudit,
        models.make_identity(
            models.RetainedExecutionAudit,
            {
                "complement_binding_id": complement.binding_id,
                "composition_contract_id": composition.contract_id,
                "v217_execution": executed.execution_audit,
            },
            field="audit_id",
            prefix="finance_v26_218_retained_execution_audit:",
        ),
    )
    attack = runtime.run_same_length_full_rehash_attack(
        authority=authority,
        binding=complement,
        composition=composition,
    )
    negative = cast(
        models.NegativeControlAudit,
        models.make_identity(
            models.NegativeControlAudit,
            {"complement_binding_id": complement.binding_id, "control": attack},
            field="audit_id",
            prefix="finance_v26_218_registry_complement_negative_control_audit:",
        ),
    )
    scope = cast(
        models.ScopeBoundaryAudit,
        models.make_identity(
            models.ScopeBoundaryAudit,
            {
                "external_authorization_id": external.authorization_id,
                "v217_freeze_id": freeze.freeze_id,
                "complement_binding_id": complement.binding_id,
            },
            field="audit_id",
            prefix="finance_v26_218_scope_boundary_audit:",
        ),
    )
    gates = cast(
        models.GateEvaluation,
        models.make_identity(
            models.GateEvaluation,
            {
                "gates": (
                    _gate("external_scope_and_exact_v217_freeze", freeze.freeze_id),
                    _gate("exact_v195_reachable_registry_snapshot", complement.binding_id),
                    _gate("exact_reachable_complement_partition", complement.binding_id),
                    _gate("v217_event_observation_artifact_chain_retained", retained.audit_id),
                    _gate("five_v209_source_exit_controls_retained", retained.audit_id),
                    _gate("five_layer_persistence_bytes_retained", retained.audit_id),
                    _gate(
                        "same_length_misspelled_complement_full_rehash_rejects", negative.audit_id
                    ),
                    _gate("zero_provider_credential_empirical_boundary", scope.audit_id),
                )
            },
            field="evaluation_id",
            prefix="finance_v26_218_gate_evaluation:",
        ),
    )
    decision = cast(
        models.Decision,
        models.make_identity(
            models.Decision,
            {
                "external_authorization_id": external.authorization_id,
                "v217_freeze_id": freeze.freeze_id,
                "complement_binding_id": complement.binding_id,
                "composition_contract_id": composition.contract_id,
                "retained_execution_audit_id": retained.audit_id,
                "negative_control_audit_id": negative.audit_id,
                "gate_evaluation_id": gates.evaluation_id,
            },
            field="decision_id",
            prefix="finance_v26_218_registry_complement_decision:",
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
            prefix="finance_v26_218_transition:",
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
                "v217_freeze_id": freeze.freeze_id,
                "implementation_binding_id": implementation.binding_id,
                "complement_binding_id": complement.binding_id,
                "composition_contract_id": composition.contract_id,
                "retained_execution_audit_id": retained.audit_id,
                "negative_control_audit_id": negative.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "gate_evaluation_id": gates.evaluation_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
            },
            field="report_id",
            prefix="finance_v26_218_registry_complement_report:",
        ),
    )
    payloads = {
        "external_review.txt": review_bytes,
        "operator_authorization.txt": directive_bytes,
        "external_revision_authorization.json": _bytes(external),
        "v217_freeze.json": _bytes(freeze),
        "source_identity.json": _bytes(source),
        "implementation_binding.json": _bytes(implementation),
        "exact_registry_complement_binding.json": _bytes(complement),
        "composition_contract.json": _bytes(composition),
        "retained_execution_audit.json": _bytes(retained),
        "registry_complement_negative_control_audit.json": _bytes(negative),
        "scope_boundary_audit.json": _bytes(scope),
        "gate_evaluation.json": _bytes(gates),
        "decision.json": _bytes(decision),
        "prospective_transition.json": _bytes(transition),
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
