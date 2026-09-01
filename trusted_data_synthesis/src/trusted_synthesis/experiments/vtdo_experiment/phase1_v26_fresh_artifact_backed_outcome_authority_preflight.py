# ruff: noqa: E501
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any, NoReturn, cast, get_args

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.task import fresh_artifact_backed_outcome_authority as authority
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_models as kernel_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_outcome_authority_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment.json_explicit_authoritative_execution_kernel import (
    NoReplaceKernelJournalWriter,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID = "finance_v26_195_fresh_artifact_backed_outcome_authority_preflight_v1_20260901"
V194_DIR = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_194_authoritative_execution_kernel_parent_preflight_v1_20260901"
)
SOURCE_FILE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_artifact_backed_outcome_authority_preflight.py"
)
EXPECTED_V194_FILES = (
    "artifact_manifest.json",
    "authoritative_development_manifest.json",
    "authoritative_execution_contract.json",
    "authoritative_kernel_runner_implementation_binding.json",
    "authoritative_runner_contract.json",
    "authoritative_runner_package_catalog.json",
    "certified_client_transport_binding.json",
    "destructive_audit.json",
    "external_v26_193_anchor.json",
    "external_v26_193_audit.txt",
    "json_renderer_implementation_binding.json",
    "kernel_invocation_audit.json",
    "kernel_resource_persistence_contract.json",
    "outcome_authority_gap_register.json",
    "privacy_resource_recovery_persistence_binding.json",
    "prospective_transition.json",
    "report.json",
    "runtime_implementation_binding.json",
    "runtime_semantic_contract.json",
    "sealed_evidence_manifest.json",
    "stage_one_request_builder_certificate_binding.json",
    "static_audit.json",
)
OLD_V186_AUTHORITY_IDENTITIES = {
    "capability_authoritative_terminal_registry:2fb3fa1572ac9681702ff0b3488152a1da8396c73683d4c7d67cb9a3257fb4c1",
    "capability_artifact_backed_outcome_contract:00fd9874ff98b5e58bc999ee76328639580393b49652417bf9ab7cdf22bd8376",
    "capability_job_bound_development_manifest:ab33e14cb0dbf81ab38682bfa4785cc1dc8eb5031b696d738a12acc9a97b203a",
    "capability_job_bound_multistep_runner_contract:11e3e81775a4c38e2c888957cb704c0a718213b25db52a376efbe6f3f4f52238",
    "capability_artifact_backed_preflight_evaluation:af044448bb3fb8fdf173249f887fa3410f06d00a803e9df5577f862a1ce00f07",
}


class FreshOutcomePreflightError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise FreshOutcomePreflightError(stage, reason)


def _canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _file_bytes(value: Any) -> bytes:
    return _canonical_bytes(value) + b"\n"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_no_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)


def _git_identity(repository_root: Path) -> tuple[str, str]:
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ("git", "show", "-s", "--format=%T", "HEAD"),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if len(commit) != 40 or len(tree) != 40:
        _fail("source.git_identity", "current Git source identity is not exact")
    return commit, tree


def _file_binding(repository_root: Path, relative_path: str) -> models.FileBinding:
    payload = (repository_root / relative_path).read_bytes()
    return models.FileBinding(
        relative_path=relative_path,
        sha256=_sha256_bytes(payload),
        byte_count=len(payload),
    )


def _find_symbol(tree: ast.Module, dotted: str) -> ast.AST:
    nodes: list[ast.AST] = list(tree.body)
    found: ast.AST | None = None
    for part in dotted.split("."):
        found = next(
            (
                item
                for item in nodes
                if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == part
            ),
            None,
        )
        if found is None:
            _fail("source.symbol", f"fresh Outcome writer symbol missing:{dotted}")
        nodes = list(found.body) if isinstance(found, ast.ClassDef) else []
    assert found is not None
    return found


def _symbol_binding(
    repository_root: Path,
    relative_path: str,
    symbol: str,
) -> models.SymbolBinding:
    source = (repository_root / relative_path).read_text(encoding="utf-8")
    node = _find_symbol(ast.parse(source), symbol)
    segment = ast.get_source_segment(source, node)
    if not segment:
        _fail("source.symbol", f"fresh Outcome writer symbol bytes missing:{symbol}")
    payload = segment.encode("utf-8")
    return models.SymbolBinding(
        relative_path=relative_path,
        symbol=symbol,
        source_sha256=_sha256_bytes(payload),
        source_byte_count=len(payload),
    )


class FreshOutcomeArtifactWriter:
    """Typed adapter over the exact v26.194 no-replace Raw-before-Result writer."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._writer = NoReplaceKernelJournalWriter(root)

    def write_raw(
        self,
        *,
        job_id: str,
        payload: authority.FreshRawExecutionPayload,
    ) -> tuple[str, int]:
        digest = self._writer.write_raw(
            job_id=job_id,
            payload=payload.model_dump(mode="json", warnings=False),
        )
        path = self._root / authority.expected_raw_artifact_filename_from_id(job_id)
        encoded = path.read_bytes()
        if digest != _sha256_bytes(encoded) or encoded != authority.canonical_model_bytes(payload):
            raise ValueError("fresh Raw writer bytes differ from typed payload")
        return digest, len(encoded)

    def write_result(
        self,
        *,
        job_id: str,
        payload: authority.FreshJobResultPayload,
    ) -> tuple[str, int]:
        digest = self._writer.write_result(
            job_id=job_id,
            payload=payload.model_dump(mode="json", warnings=False),
        )
        path = self._root / authority.expected_result_artifact_filename_from_id(job_id)
        encoded = path.read_bytes()
        if digest != _sha256_bytes(encoded) or encoded != authority.canonical_model_bytes(payload):
            raise ValueError("fresh Result writer bytes differ from typed payload")
        return digest, len(encoded)

    def assert_closed(self) -> None:
        self._writer.assert_no_orphans()


def _authorization(audit_path: Path) -> tuple[models.ExternalAuditAuthorization, bytes]:
    payload = audit_path.read_bytes()
    if len(payload) != 8598 or _sha256_bytes(payload) != (
        "a1b70efd0a73261a71ac6d8e62e21fb590baecb294c2a7dc69dc191542ecfcc3"
    ):
        _fail("authorization", "v26.194 independent audit bytes differ")
    return (
        cast(
            models.ExternalAuditAuthorization,
            models.make_identity(
                models.ExternalAuditAuthorization,
                {
                    "audit_sha256": _sha256_bytes(payload),
                    "audit_byte_count": len(payload),
                    "audit_decision": (
                        "authoritative_execution_kernel_parent_binding_independent_audit_passed_"
                        "fresh_artifact_backed_outcome_authority_preflight_only_authorized"
                    ),
                },
                field="authorization_id",
                prefix="finance_v26_195_external_authorization:",
            ),
        ),
        payload,
    )


def _v194_anchor(
    repository_root: Path,
    authorization_id: str,
) -> tuple[
    models.V194ExternalAnchor,
    kernel_models.AuthoritativeRunnerPackageCatalog,
    kernel_models.AuthoritativeDevelopmentManifest,
    kernel_models.AuthoritativeRunnerContract,
    kernel_models.AuthoritativeExecutionContract,
]:
    root = repository_root / V194_DIR
    observed = tuple(sorted(path.name for path in root.iterdir() if path.is_file()))
    if observed != EXPECTED_V194_FILES:
        _fail("anchor.file_set", "v26.194 exact 22-file set differs")
    distribution = kernel_models.ArtifactManifest.model_validate(
        _load(root / "artifact_manifest.json")
    )
    if (
        distribution.manifest_id
        != "finance_v26_194_distribution_artifact_manifest:69031f0f4625b3ffbf74be0c02006011bc51ef60d8628266106dbe7b4632fe15"
        or distribution.artifact_root
        != "finance_v26_194_distribution_artifact_root:d9a9bf6d4345def14bd01379818e898a88b380fc95363ece291980d295e84b10"
        or distribution.file_count != 21
    ):
        _fail("anchor.distribution", "v26.194 frozen distribution identity differs")
    expected_members = {item.relative_path: item for item in distribution.members}
    if set(expected_members) != set(EXPECTED_V194_FILES) - {"artifact_manifest.json"}:
        _fail("anchor.distribution_set", "v26.194 distribution member set differs")
    bindings: list[models.FileBinding] = []
    for name in EXPECTED_V194_FILES:
        payload = (root / name).read_bytes()
        if name != "artifact_manifest.json":
            expected = expected_members[name]
            if (_sha256_bytes(payload), len(payload)) != (expected.sha256, expected.byte_count):
                _fail("anchor.file_bytes", f"v26.194 exact file bytes differ:{name}")
        bindings.append(
            models.FileBinding(
                relative_path=name,
                sha256=_sha256_bytes(payload),
                byte_count=len(payload),
            )
        )
    report = kernel_models.PreflightReport.model_validate(_load(root / "report.json"))
    if (
        report.report_id
        != "finance_v26_194_execution_kernel_preflight_report:f95f59b95819f081153774abba04a26f255d41b6ce7ce819db031625faec9747"
        or report.source_commit != "2a5b8322a94e7be84065375dd6720e532bfe05cb"
        or report.source_tree != "3f75f98f8ad11a3a7125523ee83233b23036a82d"
        or report.sealed_evidence_manifest_id
        != "finance_v26_194_sealed_evidence_artifact_manifest:5193780194eeaf7e7b53ce4954c01e835300f22cd8b2bad500402266e5092207"
        or report.sealed_evidence_artifact_root
        != "finance_v26_194_sealed_evidence_artifact_root:91c2492673c1ac9ba3c0c90bc1a17b20547355235abe357bb11af7383ee17b8f"
    ):
        _fail("anchor.report", "v26.194 source-frozen Report differs")
    catalog = kernel_models.AuthoritativeRunnerPackageCatalog.model_validate(
        _load(root / "authoritative_runner_package_catalog.json")
    )
    manifest = kernel_models.AuthoritativeDevelopmentManifest.model_validate(
        _load(root / "authoritative_development_manifest.json")
    )
    runner = kernel_models.AuthoritativeRunnerContract.model_validate(
        _load(root / "authoritative_runner_contract.json")
    )
    execution = kernel_models.AuthoritativeExecutionContract.model_validate(
        _load(root / "authoritative_execution_contract.json")
    )
    if (
        execution.contract_id != report.execution_contract_id
        or manifest.manifest_id != report.manifest_id
        or runner.runner_id != report.runner_id
        or catalog.catalog_id != report.package_catalog_id
        or execution.fresh_outcome_authority_materialized
    ):
        _fail("anchor.execution", "v26.194 exact execution parent projection differs")
    anchor = cast(
        models.V194ExternalAnchor,
        models.make_identity(
            models.V194ExternalAnchor,
            {
                "authorization_id": authorization_id,
                "source_commit": report.source_commit,
                "source_tree": report.source_tree,
                "report_id": report.report_id,
                "sealed_manifest_id": report.sealed_evidence_manifest_id,
                "sealed_artifact_root": report.sealed_evidence_artifact_root,
                "distribution_manifest_id": distribution.manifest_id,
                "distribution_artifact_root": distribution.artifact_root,
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "package_catalog_id": catalog.catalog_id,
                "runtime_semantic_contract_id": report.runtime_semantic_contract_id,
                "runtime_implementation_binding_id": report.runtime_implementation_binding_id,
                "exact_files": tuple(bindings),
            },
            field="anchor_id",
            prefix="finance_v26_194_external_anchor:",
        ),
    )
    return anchor, catalog, manifest, runner, execution


def _writer_binding(
    *,
    repository_root: Path,
    external_anchor_id: str,
    source_commit: str,
    source_tree: str,
) -> models.OutcomeWriterImplementationBinding:
    return cast(
        models.OutcomeWriterImplementationBinding,
        models.make_identity(
            models.OutcomeWriterImplementationBinding,
            {
                "external_anchor_id": external_anchor_id,
                "source_commit": source_commit,
                "source_tree": source_tree,
                "source_file": _file_binding(repository_root, SOURCE_FILE),
                "symbols": tuple(
                    _symbol_binding(repository_root, SOURCE_FILE, symbol)
                    for symbol in (
                        "FreshOutcomeArtifactWriter",
                        "FreshOutcomeArtifactWriter.write_raw",
                        "FreshOutcomeArtifactWriter.write_result",
                    )
                ),
            },
            field="binding_id",
            prefix="fresh_outcome_writer_implementation_binding:",
        ),
    )


def _terminal_registry(
    *,
    anchor: models.V194ExternalAnchor,
    catalog: kernel_models.AuthoritativeRunnerPackageCatalog,
    manifest: kernel_models.AuthoritativeDevelopmentManifest,
    runner: kernel_models.AuthoritativeRunnerContract,
    execution: kernel_models.AuthoritativeExecutionContract,
) -> authority.FreshTerminalRegistry:
    policies = []
    for terminal_kind in sorted(get_args(authority.TerminalKind)):
        rule = "nonverifier_null"
        if terminal_kind == "completed_qualified":
            rule = "qualified_conjunction_true"
        elif terminal_kind == "completed_invalid":
            rule = "factorized_conjunction_false"
        status = "reachable"
        if terminal_kind in {"policy_horizon_exhausted", "measurement_support_exit"}:
            status = "not_applicable_under_v26_194_execution_kernel"
        policies.append(
            cast(
                authority.FreshTerminalPolicy,
                authority.make_identity_model(
                    authority.FreshTerminalPolicy,
                    {
                        "terminal_kind": terminal_kind,
                        "registration_status": status,
                        "final_validity_rule": rule,
                        "exact_execution_contract_id": execution.contract_id,
                        "exact_runner_id": runner.runner_id,
                    },
                    field="policy_id",
                    prefix="fresh_kernel_terminal_policy:",
                ),
            )
        )
    return cast(
        authority.FreshTerminalRegistry,
        authority.make_identity_model(
            authority.FreshTerminalRegistry,
            {
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "package_catalog_id": catalog.catalog_id,
                "runtime_semantic_contract_id": anchor.runtime_semantic_contract_id,
                "runtime_implementation_binding_id": anchor.runtime_implementation_binding_id,
                "policies": tuple(policies),
            },
            field="registry_id",
            prefix="fresh_kernel_terminal_registry:",
        ),
    )


def _contracts(
    *,
    catalog: kernel_models.AuthoritativeRunnerPackageCatalog,
    manifest: kernel_models.AuthoritativeDevelopmentManifest,
    runner: kernel_models.AuthoritativeRunnerContract,
    execution: kernel_models.AuthoritativeExecutionContract,
    registry: authority.FreshTerminalRegistry,
) -> tuple[
    authority.FreshRawExecutionDescriptorContract,
    authority.FreshJobResultDescriptorContract,
    authority.FreshJobBoundAttemptTraceContract,
    authority.FreshOutcomeRowContract,
    authority.FreshExactEvidenceSetEvaluatorContract,
]:
    exact_jobs = tuple(manifest.expected_job_ids)
    package_map = {item.package_id: item for item in catalog.packages}
    sequences = tuple(
        cast(
            authority.JobComponentSequence,
            authority.make_identity_model(
                authority.JobComponentSequence,
                {
                    "job_id": job.job_id,
                    "package_id": job.package_id,
                    "ordered_component_keys": package_map[
                        job.package_id
                    ].topological_component_keys,
                },
                field="sequence_id",
                prefix="fresh_kernel_job_component_sequence:",
            ),
        )
        for job in sorted(manifest.jobs, key=lambda item: item.job_id)
    )
    common = {
        "terminal_registry_id": registry.registry_id,
        "execution_contract_id": execution.contract_id,
        "manifest_id": manifest.manifest_id,
        "runner_id": runner.runner_id,
    }
    raw = cast(
        authority.FreshRawExecutionDescriptorContract,
        authority.make_identity_model(
            authority.FreshRawExecutionDescriptorContract,
            {
                **common,
                "package_catalog_id": catalog.catalog_id,
                "exact_job_ids": exact_jobs,
            },
            field="contract_id",
            prefix="fresh_raw_execution_descriptor_contract:",
        ),
    )
    result = cast(
        authority.FreshJobResultDescriptorContract,
        authority.make_identity_model(
            authority.FreshJobResultDescriptorContract,
            {
                **common,
                "raw_descriptor_contract_id": raw.contract_id,
                "exact_job_ids": exact_jobs,
            },
            field="contract_id",
            prefix="fresh_job_result_descriptor_contract:",
        ),
    )
    trace = cast(
        authority.FreshJobBoundAttemptTraceContract,
        authority.make_identity_model(
            authority.FreshJobBoundAttemptTraceContract,
            {
                **common,
                "raw_descriptor_contract_id": raw.contract_id,
                "result_descriptor_contract_id": result.contract_id,
                "job_component_sequences": sequences,
            },
            field="contract_id",
            prefix="fresh_job_bound_attempt_trace_contract:",
        ),
    )
    outcome = cast(
        authority.FreshOutcomeRowContract,
        authority.make_identity_model(
            authority.FreshOutcomeRowContract,
            {
                **common,
                "raw_descriptor_contract_id": raw.contract_id,
                "result_descriptor_contract_id": result.contract_id,
                "attempt_trace_contract_id": trace.contract_id,
                "exact_job_ids": exact_jobs,
            },
            field="contract_id",
            prefix="fresh_outcome_row_contract:",
        ),
    )
    evaluator = cast(
        authority.FreshExactEvidenceSetEvaluatorContract,
        authority.make_identity_model(
            authority.FreshExactEvidenceSetEvaluatorContract,
            {
                **common,
                "outcome_row_contract_id": outcome.contract_id,
                "attempt_trace_contract_id": trace.contract_id,
                "result_descriptor_contract_id": result.contract_id,
                "raw_descriptor_contract_id": raw.contract_id,
                "package_catalog_id": catalog.catalog_id,
            },
            field="contract_id",
            prefix="fresh_exact_evidence_set_evaluator_contract:",
        ),
    )
    return raw, result, trace, outcome, evaluator


def _fresh_authority_audit(
    *,
    anchor: models.V194ExternalAnchor,
    writer_binding: models.OutcomeWriterImplementationBinding,
    catalog: kernel_models.AuthoritativeRunnerPackageCatalog,
    manifest: kernel_models.AuthoritativeDevelopmentManifest,
    runner: kernel_models.AuthoritativeRunnerContract,
    execution: kernel_models.AuthoritativeExecutionContract,
    registry: authority.FreshTerminalRegistry,
    raw_contract: authority.FreshRawExecutionDescriptorContract,
    result_contract: authority.FreshJobResultDescriptorContract,
    trace_contract: authority.FreshJobBoundAttemptTraceContract,
    outcome_contract: authority.FreshOutcomeRowContract,
    evaluator_contract: authority.FreshExactEvidenceSetEvaluatorContract,
) -> models.FreshAuthorityAudit:
    values = (
        registry.registry_id,
        raw_contract.contract_id,
        result_contract.contract_id,
        trace_contract.contract_id,
        outcome_contract.contract_id,
        evaluator_contract.contract_id,
    )
    if set(values) & OLD_V186_AUTHORITY_IDENTITIES:
        _fail("fresh.identity", "v26.186 Outcome authority identity was reused")
    return cast(
        models.FreshAuthorityAudit,
        models.make_identity(
            models.FreshAuthorityAudit,
            {
                "external_anchor_id": anchor.anchor_id,
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "package_catalog_id": catalog.catalog_id,
                "writer_implementation_binding_id": writer_binding.binding_id,
                "terminal_registry_id": registry.registry_id,
                "raw_descriptor_contract_id": raw_contract.contract_id,
                "result_descriptor_contract_id": result_contract.contract_id,
                "attempt_trace_contract_id": trace_contract.contract_id,
                "outcome_row_contract_id": outcome_contract.contract_id,
                "evaluator_contract_id": evaluator_contract.contract_id,
                "materialized_layers": (
                    "fresh_terminal_registry_binding",
                    "fresh_raw_execution_descriptor_contract",
                    "fresh_job_result_descriptor_contract",
                    "fresh_job_bound_attempt_trace_contract",
                    "fresh_outcome_row_contract",
                    "fresh_exact_evidence_set_evaluator",
                ),
            },
            field="audit_id",
            prefix="finance_v26_195_fresh_authority_audit:",
        ),
    )


def _rehash(
    value: BaseModel,
    *,
    updates: dict[str, Any],
    model_type: type[BaseModel],
    field: str,
    prefix: str,
) -> Any:
    values = value.model_dump(mode="python", exclude={field}, warnings=False)
    values.update(updates)
    return authority.make_identity_model(
        model_type,
        values,
        field=field,
        prefix=prefix,
    )


def _capture_attack(
    *,
    name: str,
    layer: str,
    reason: str,
    expected_fragment: str,
    fully_rehashed: bool,
    invoke: Callable[[], Any],
) -> models.AttackResult:
    try:
        invoke()
    except (ValueError, ValidationError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(
                f"attack {name} rejected at an unexpected boundary: {exc}"
            ) from exc
    else:
        raise AssertionError(f"attack {name} was accepted")
    return cast(
        models.AttackResult,
        models.make_identity(
            models.AttackResult,
            {
                "attack_name": name,
                "target_layer": layer,
                "expected_reason": reason,
                "actual_reason": reason,
                "fully_rehashed": fully_rehashed,
            },
            field="attack_id",
            prefix="fresh_outcome_authority_attack:",
        ),
    )


def _destructive_audit(
    *,
    repository_root: Path,
    artifact_root: Path,
    catalog: kernel_models.AuthoritativeRunnerPackageCatalog,
    manifest: kernel_models.AuthoritativeDevelopmentManifest,
    runner: kernel_models.AuthoritativeRunnerContract,
    execution: kernel_models.AuthoritativeExecutionContract,
    registry: authority.FreshTerminalRegistry,
    raw_contract: authority.FreshRawExecutionDescriptorContract,
    result_contract: authority.FreshJobResultDescriptorContract,
    trace_contract: authority.FreshJobBoundAttemptTraceContract,
    outcome_contract: authority.FreshOutcomeRowContract,
    evaluator_contract: authority.FreshExactEvidenceSetEvaluatorContract,
    bundles: tuple[authority.FreshEvidenceBundle, ...],
) -> models.DestructiveAudit:
    predecessor = kernel_models.DestructiveAudit.model_validate(
        _load(repository_root / V194_DIR / "destructive_audit.json")
    )
    if predecessor.attack_count != 12 or predecessor.rejection_count != 12:
        _fail("destructive.predecessor", "v26.194 twelve-attack regression differs")
    jobs = {item.job_id: item for item in manifest.jobs}
    sequences = {item.job_id: item for item in trace_contract.job_component_sequences}

    def evaluate(
        changed_bundles: tuple[authority.FreshEvidenceBundle, ...] = bundles,
        **parents: Any,
    ) -> authority.FreshExactEvidenceSetEvaluation:
        return authority.evaluate_fresh_evidence_set(
            artifact_root=artifact_root,
            bundles=changed_bundles,
            catalog=parents.get("catalog", catalog),
            manifest=parents.get("manifest", manifest),
            runner=parents.get("runner", runner),
            execution=parents.get("execution", execution),
            registry=parents.get("registry", registry),
            raw_contract=parents.get("raw_contract", raw_contract),
            result_contract=parents.get("result_contract", result_contract),
            trace_contract=parents.get("trace_contract", trace_contract),
            outcome_contract=parents.get("outcome_contract", outcome_contract),
            evaluator_contract=parents.get("evaluator_contract", evaluator_contract),
            expected_evidence_kind=parents.get(
                "expected_evidence_kind", "scripted_preflight_control"
            ),
        )

    first, second = bundles[0], bundles[1]
    attacks: list[models.AttackResult] = []

    def capture(
        name: str,
        layer: str,
        reason: str,
        fragment: str,
        fully: bool,
        invoke: Callable[[], Any],
    ) -> None:
        attacks.append(
            _capture_attack(
                name=name,
                layer=layer,
                reason=reason,
                expected_fragment=fragment,
                fully_rehashed=fully,
                invoke=invoke,
            )
        )

    capture(
        "catalog_model_construct_injection",
        "v26_194_parent",
        "v26_194_catalog_strict_revalidation_failed",
        "kernel Package Catalog identity differs",
        True,
        lambda: evaluate(
            catalog=kernel_models.AuthoritativeRunnerPackageCatalog.model_construct(
                **{
                    **catalog.model_dump(mode="python", exclude={"catalog_id"}),
                    "catalog_id": "authoritative_kernel_package_catalog:" + "0" * 64,
                }
            )
        ),
    )
    capture(
        "manifest_model_construct_injection",
        "v26_194_parent",
        "v26_194_manifest_strict_revalidation_failed",
        "kernel Manifest identity differs",
        True,
        lambda: evaluate(
            manifest=kernel_models.AuthoritativeDevelopmentManifest.model_construct(
                **{
                    **manifest.model_dump(mode="python", exclude={"manifest_id"}),
                    "manifest_id": "authoritative_kernel_manifest:" + "0" * 64,
                }
            )
        ),
    )
    changed_job = kernel_models.AuthoritativeDevelopmentJob.model_construct(
        **{
            **manifest.jobs[0].model_dump(mode="python", exclude={"job_id"}),
            "job_id": "authoritative_kernel_development_job:" + "0" * 64,
        }
    )
    capture(
        "nested_job_model_construct_injection",
        "v26_194_parent",
        "v26_194_nested_job_strict_revalidation_failed",
        "kernel Development Job identity differs",
        True,
        lambda: evaluate(
            manifest=kernel_models.AuthoritativeDevelopmentManifest.model_construct(
                **{
                    **manifest.model_dump(mode="python", exclude={"jobs"}),
                    "jobs": (changed_job, *manifest.jobs[1:]),
                }
            )
        ),
    )
    capture(
        "runner_model_construct_injection",
        "v26_194_parent",
        "v26_194_runner_strict_revalidation_failed",
        "authoritative Runner identity differs",
        True,
        lambda: evaluate(
            runner=kernel_models.AuthoritativeRunnerContract.model_construct(
                **{
                    **runner.model_dump(mode="python", exclude={"runner_id"}),
                    "runner_id": "authoritative_execution_kernel_runner:" + "0" * 64,
                }
            )
        ),
    )
    capture(
        "execution_contract_model_construct_injection",
        "v26_194_parent",
        "v26_194_execution_strict_revalidation_failed",
        "Execution Contract identity differs",
        True,
        lambda: evaluate(
            execution=kernel_models.AuthoritativeExecutionContract.model_construct(
                **{
                    **execution.model_dump(mode="python", exclude={"contract_id"}),
                    "contract_id": "authoritative_execution_kernel_contract:" + "0" * 64,
                }
            )
        ),
    )
    capture(
        "terminal_registry_model_construct_injection",
        "terminal_registry",
        "fresh_terminal_registry_strict_revalidation_failed",
        "fresh terminal registry identity differs",
        True,
        lambda: evaluate(
            registry=authority.FreshTerminalRegistry.model_construct(
                **{
                    **registry.model_dump(mode="python", exclude={"registry_id"}),
                    "registry_id": OLD_V186_AUTHORITY_IDENTITIES.copy().pop(),
                }
            )
        ),
    )
    parent_attacks = (
        (
            "raw_contract_model_construct_injection",
            "raw_contract",
            raw_contract,
            authority.FreshRawExecutionDescriptorContract,
            "fresh Raw Contract identity differs",
        ),
        (
            "result_contract_model_construct_injection",
            "result_contract",
            result_contract,
            authority.FreshJobResultDescriptorContract,
            "fresh Result Contract identity differs",
        ),
        (
            "trace_contract_model_construct_injection",
            "trace_contract",
            trace_contract,
            authority.FreshJobBoundAttemptTraceContract,
            "fresh AttemptTrace Contract identity differs",
        ),
        (
            "outcome_contract_model_construct_injection",
            "outcome_contract",
            outcome_contract,
            authority.FreshOutcomeRowContract,
            "fresh Outcome-row Contract identity differs",
        ),
        (
            "evaluator_contract_model_construct_injection",
            "evaluator_contract",
            evaluator_contract,
            authority.FreshExactEvidenceSetEvaluatorContract,
            "fresh evaluator Contract identity differs",
        ),
    )
    for name, key, value, model_type, fragment in parent_attacks:
        forged = model_type.model_construct(
            **{
                **value.model_dump(mode="python", exclude={"contract_id"}),
                "contract_id": f"{key}:" + "0" * 64,
            }
        )
        capture(
            name,
            key,
            f"{key}_strict_revalidation_failed",
            fragment,
            True,
            partial(evaluate, **{key: forged}),
        )
    raw_path = artifact_root / first.raw.artifact_relative_path
    raw_original = raw_path.read_bytes()

    def raw_byte_drift() -> None:
        raw_path.write_bytes(raw_original + b" ")
        try:
            evaluate()
        finally:
            raw_path.write_bytes(raw_original)

    capture(
        "raw_file_byte_drift",
        "raw_descriptor",
        "raw_artifact_bytes_differ",
        "artifact descriptor does not bind actual file bytes",
        False,
        raw_byte_drift,
    )
    result_path = artifact_root / first.result.artifact_relative_path
    result_original = result_path.read_bytes()

    def result_byte_drift() -> None:
        result_path.write_bytes(result_original + b" ")
        try:
            evaluate()
        finally:
            result_path.write_bytes(result_original)

    capture(
        "result_file_byte_drift",
        "result_descriptor",
        "result_artifact_bytes_differ",
        "artifact descriptor does not bind actual file bytes",
        False,
        result_byte_drift,
    )
    changed_raw = cast(
        authority.FreshRawExecutionDescriptor,
        _rehash(
            first.raw,
            updates={"job_id": second.row.job_id},
            model_type=authority.FreshRawExecutionDescriptor,
            field="raw_execution_id",
            prefix="fresh_kernel_raw_execution_descriptor:",
        ),
    )
    capture(
        "raw_descriptor_cross_job",
        "raw_descriptor",
        "raw_descriptor_crosses_exact_job",
        "fresh Raw descriptor crosses exact v26.194 Job",
        True,
        lambda: evaluate(
            (
                authority.FreshEvidenceBundle(
                    raw=changed_raw, result=first.result, trace=first.trace, row=first.row
                ),
                *bundles[1:],
            )
        ),
    )
    changed_result = cast(
        authority.FreshJobResultDescriptor,
        _rehash(
            first.result,
            updates={"raw_execution_id": second.raw.raw_execution_id},
            model_type=authority.FreshJobResultDescriptor,
            field="result_id",
            prefix="fresh_kernel_job_result_descriptor:",
        ),
    )
    capture(
        "result_descriptor_cross_raw",
        "result_descriptor",
        "result_descriptor_crosses_raw",
        "fresh Result descriptor crosses Raw or Job",
        True,
        lambda: evaluate(
            (
                authority.FreshEvidenceBundle(
                    raw=first.raw, result=changed_result, trace=first.trace, row=first.row
                ),
                *bundles[1:],
            )
        ),
    )
    invented_locus = cast(
        authority.FreshFailureLocus,
        authority.make_identity_model(
            authority.FreshFailureLocus,
            {
                "stage": "mechanism",
                "component_key": sequences[first.row.job_id].ordered_component_keys[0],
                "attempt_index": 0,
                "reason_code": "invented_mechanism_failure",
                "source_descriptor_id": first.result.result_id,
            },
            field="locus_id",
            prefix="fresh_kernel_failure_locus:",
        ),
    )
    changed_trace = cast(
        authority.FreshJobBoundAttemptTrace,
        _rehash(
            first.trace,
            updates={"failure_loci": (invented_locus,)},
            model_type=authority.FreshJobBoundAttemptTrace,
            field="trace_id",
            prefix="fresh_kernel_job_bound_attempt_trace:",
        ),
    )
    capture(
        "fully_rehashed_invented_failure_locus",
        "attempt_trace",
        "trace_not_reconstructed",
        "fresh AttemptTrace or FailureLocus is not reconstructed",
        True,
        lambda: evaluate(
            (
                authority.FreshEvidenceBundle(
                    raw=first.raw, result=first.result, trace=changed_trace, row=first.row
                ),
                *bundles[1:],
            )
        ),
    )
    changed_row = cast(
        authority.FreshOutcomeRow,
        _rehash(
            first.row,
            updates={"trace_id": second.trace.trace_id},
            model_type=authority.FreshOutcomeRow,
            field="row_id",
            prefix="fresh_kernel_outcome_row:",
        ),
    )
    capture(
        "fully_rehashed_outcome_trace_crossing",
        "outcome_row",
        "outcome_not_reconstructed",
        "fresh Outcome row is not reconstructed from artifacts",
        True,
        lambda: evaluate(
            (
                authority.FreshEvidenceBundle(
                    raw=first.raw, result=first.result, trace=first.trace, row=changed_row
                ),
                *bundles[1:],
            )
        ),
    )
    capture(
        "missing_exact_job",
        "exact_evidence_set",
        "exact_manifest_denominator_differs",
        "fresh evidence differs from exact Manifest denominator",
        False,
        lambda: evaluate(bundles[:-1]),
    )
    capture(
        "extra_exact_job",
        "exact_evidence_set",
        "exact_manifest_denominator_differs",
        "fresh evidence differs from exact Manifest denominator",
        False,
        lambda: evaluate((*bundles, bundles[-1])),
    )
    capture(
        "duplicate_job_with_192_rows",
        "exact_evidence_set",
        "evidence_repeats_job",
        "fresh evidence repeats a Job",
        True,
        lambda: evaluate((first, first, *bundles[2:])),
    )
    capture(
        "scripted_chain_promoted_to_empirical",
        "exact_evidence_set",
        "empirical_evaluation_requires_independent_audit",
        "empirical evaluation remains unauthorized pending independent audit",
        True,
        lambda: evaluate(expected_evidence_kind="empirical_execution"),
    )
    capture(
        "old_fixture_complete_payload",
        "result_payload",
        "legacy_fixture_payload_is_not_typed_outcome",
        "Field required",
        False,
        lambda: authority.FreshJobResultPayload.model_validate(
            {"job_id": first.row.job_id, "raw_sha256": "0" * 64, "terminal": "fixture_complete"}
        ),
    )
    noncanonical = json.dumps(
        json.loads(raw_original),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8")
    noncanonical_raw = cast(
        authority.FreshRawExecutionDescriptor,
        _rehash(
            first.raw,
            updates={
                "artifact_sha256": _sha256_bytes(noncanonical),
                "artifact_byte_count": len(noncanonical),
            },
            model_type=authority.FreshRawExecutionDescriptor,
            field="raw_execution_id",
            prefix="fresh_kernel_raw_execution_descriptor:",
        ),
    )

    def noncanonical_raw_attack() -> None:
        raw_path.write_bytes(noncanonical)
        try:
            authority.validate_fresh_bundle(
                artifact_root=artifact_root,
                job=jobs[first.row.job_id],
                sequence=sequences[first.row.job_id],
                manifest=manifest,
                runner=runner,
                execution=execution,
                registry=registry,
                raw_contract=raw_contract,
                result_contract=result_contract,
                trace_contract=trace_contract,
                outcome_contract=outcome_contract,
                bundle=authority.FreshEvidenceBundle(
                    raw=noncanonical_raw,
                    result=first.result,
                    trace=first.trace,
                    row=first.row,
                ),
                expected_evidence_kind="scripted_preflight_control",
            )
        finally:
            raw_path.write_bytes(raw_original)

    capture(
        "noncanonical_raw_json_with_rehashed_descriptor",
        "raw_artifact",
        "raw_artifact_not_canonical",
        "artifact bytes are not exact canonical model serialization",
        True,
        noncanonical_raw_attack,
    )
    return cast(
        models.DestructiveAudit,
        models.make_identity(
            models.DestructiveAudit,
            {
                "evaluator_contract_id": evaluator_contract.contract_id,
                "attacks": tuple(attacks),
                "attack_count": len(attacks),
                "rejection_count": len(attacks),
                "fully_rehashed_attack_count": sum(int(item.fully_rehashed) for item in attacks),
            },
            field="audit_id",
            prefix="finance_v26_195_fresh_outcome_destructive_audit:",
        ),
    )


def _gate(name: str, *evidence_ids: str) -> models.StaticGate:
    return models.StaticGate(name=name, evidence_ids=tuple(evidence_ids))


def _artifact_manifest(
    root: Path,
    *,
    run_id: str,
    scope: str,
) -> models.ArtifactManifest:
    members = tuple(
        models.ArtifactMember(
            relative_path=path.relative_to(root).as_posix(),
            sha256=_sha256_bytes(path.read_bytes()),
            byte_count=path.stat().st_size,
        )
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    )
    artifact_root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix=f"finance_v26_195_{scope}_artifact_root:",
    )
    return cast(
        models.ArtifactManifest,
        models.make_identity(
            models.ArtifactManifest,
            {
                "run_id": run_id,
                "members": members,
                "file_count": len(members),
                "total_byte_count": sum(item.byte_count for item in members),
                "artifact_root": artifact_root,
                "scope": scope,
            },
            field="manifest_id",
            prefix=f"finance_v26_195_{scope}_artifact_manifest:",
        ),
    )


def build(
    *,
    repository_root: Path,
    audit_path: Path,
    output_dir: Path,
) -> models.PreflightReport:
    if output_dir.exists():
        _fail("output", "v26.195 output directory already exists")
    authorization, audit_bytes = _authorization(audit_path)
    anchor, catalog, manifest, runner, execution = _v194_anchor(
        repository_root,
        authorization.authorization_id,
    )
    source_commit, source_tree = _git_identity(repository_root)
    writer_binding = _writer_binding(
        repository_root=repository_root,
        external_anchor_id=anchor.anchor_id,
        source_commit=source_commit,
        source_tree=source_tree,
    )
    registry = _terminal_registry(
        anchor=anchor,
        catalog=catalog,
        manifest=manifest,
        runner=runner,
        execution=execution,
    )
    raw_contract, result_contract, trace_contract, outcome_contract, evaluator_contract = (
        _contracts(
            catalog=catalog,
            manifest=manifest,
            runner=runner,
            execution=execution,
            registry=registry,
        )
    )
    fresh = _fresh_authority_audit(
        anchor=anchor,
        writer_binding=writer_binding,
        catalog=catalog,
        manifest=manifest,
        runner=runner,
        execution=execution,
        registry=registry,
        raw_contract=raw_contract,
        result_contract=result_contract,
        trace_contract=trace_contract,
        outcome_contract=outcome_contract,
        evaluator_contract=evaluator_contract,
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    writer = FreshOutcomeArtifactWriter(output_dir)
    sequence_map = {item.job_id: item for item in trace_contract.job_component_sequences}
    bundles = tuple(
        authority.build_scripted_bundle(
            artifact_root=output_dir,
            writer=writer,
            job=job,
            sequence=sequence_map[job.job_id],
            manifest=manifest,
            runner=runner,
            execution=execution,
            registry=registry,
            raw_contract=raw_contract,
            result_contract=result_contract,
            trace_contract=trace_contract,
            outcome_contract=outcome_contract,
        )
        for job in sorted(manifest.jobs, key=lambda item: item.job_id)
    )
    writer.assert_closed()
    evaluation = authority.evaluate_fresh_evidence_set(
        artifact_root=output_dir,
        bundles=bundles,
        catalog=catalog,
        manifest=manifest,
        runner=runner,
        execution=execution,
        registry=registry,
        raw_contract=raw_contract,
        result_contract=result_contract,
        trace_contract=trace_contract,
        outcome_contract=outcome_contract,
        evaluator_contract=evaluator_contract,
        expected_evidence_kind="scripted_preflight_control",
    )
    dag = cast(
        models.EvidenceDagAudit,
        models.make_identity(
            models.EvidenceDagAudit,
            {
                "fresh_authority_audit_id": fresh.audit_id,
                "evaluation_id": evaluation.evaluation_id,
                "writer_implementation_binding_id": writer_binding.binding_id,
            },
            field="audit_id",
            prefix="finance_v26_195_evidence_dag_audit:",
        ),
    )
    destructive = _destructive_audit(
        repository_root=repository_root,
        artifact_root=output_dir,
        catalog=catalog,
        manifest=manifest,
        runner=runner,
        execution=execution,
        registry=registry,
        raw_contract=raw_contract,
        result_contract=result_contract,
        trace_contract=trace_contract,
        outcome_contract=outcome_contract,
        evaluator_contract=evaluator_contract,
        bundles=bundles,
    )
    gates = (
        _gate("external_audit_exact", authorization.authorization_id),
        _gate("v26_194_exact_external_anchor", anchor.anchor_id),
        _gate("v26_194_exact_22_file_vector", anchor.anchor_id),
        _gate("v26_194_execution_parent_strict_revalidation", fresh.audit_id),
        _gate("fresh_terminal_registry_materialized", registry.registry_id),
        _gate("fresh_raw_descriptor_contract_materialized", raw_contract.contract_id),
        _gate("fresh_result_descriptor_contract_materialized", result_contract.contract_id),
        _gate("fresh_attempt_trace_contract_materialized", trace_contract.contract_id),
        _gate("fresh_outcome_row_contract_materialized", outcome_contract.contract_id),
        _gate("fresh_exact_evidence_evaluator_materialized", evaluator_contract.contract_id),
        _gate("old_v26_186_authority_identity_reuse_zero", fresh.audit_id),
        _gate("v26_194_writer_adapter_implementation_bound", writer_binding.binding_id),
        _gate("exact_192_raw_descriptors", evaluation.evaluation_id),
        _gate("exact_192_result_descriptors", evaluation.evaluation_id),
        _gate("exact_192_attempt_traces", evaluation.evaluation_id),
        _gate("exact_192_outcome_rows", evaluation.evaluation_id),
        _gate("exact_384_artifact_bytes", evaluation.evaluation_id),
        _gate("exact_manifest_job_set", evaluation.evaluation_id),
        _gate("raw_before_result_no_orphan", dag.audit_id),
        _gate("legacy_fixture_complete_rejected", dag.audit_id),
        _gate("v26_194_twelve_attack_regression", destructive.audit_id),
        _gate("fresh_outcome_attacks_reject", destructive.audit_id),
        _gate("scripted_rows_nonempirical", evaluation.evaluation_id),
        _gate("provider_calls_zero", dag.audit_id),
        _gate("development_outcomes_zero", dag.audit_id),
        _gate("empirical_estimates_zero", dag.audit_id),
        _gate("online_execution_blocked", evaluator_contract.contract_id),
    )
    static = cast(
        models.StaticAudit,
        models.make_identity(
            models.StaticAudit,
            {
                "gates": gates,
                "gate_count": len(gates),
                "passed_count": len(gates),
            },
            field="audit_id",
            prefix="finance_v26_195_static_audit:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        models.make_identity(
            models.ProspectiveTransition,
            {
                "evaluator_contract_id": evaluator_contract.contract_id,
                "evaluation_id": evaluation.evaluation_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
            },
            field="transition_id",
            prefix="finance_v26_195_transition:",
        ),
    )
    payloads: dict[str, bytes] = {
        "external_v26_194_independent_audit.txt": audit_bytes,
        "external_v26_194_anchor.json": _file_bytes(anchor),
        "outcome_writer_implementation_binding.json": _file_bytes(writer_binding),
        "fresh_terminal_registry.json": _file_bytes(registry),
        "fresh_raw_execution_descriptor_contract.json": _file_bytes(raw_contract),
        "fresh_job_result_descriptor_contract.json": _file_bytes(result_contract),
        "fresh_job_bound_attempt_trace_contract.json": _file_bytes(trace_contract),
        "fresh_outcome_row_contract.json": _file_bytes(outcome_contract),
        "fresh_exact_evidence_set_evaluator_contract.json": _file_bytes(evaluator_contract),
        "fresh_authority_audit.json": _file_bytes(fresh),
        "exact_evidence_set.json": _file_bytes(
            tuple(item.model_dump(mode="json") for item in bundles)
        ),
        "exact_evidence_set_evaluation.json": _file_bytes(evaluation),
        "evidence_dag_audit.json": _file_bytes(dag),
        "destructive_audit.json": _file_bytes(destructive),
        "static_audit.json": _file_bytes(static),
        "prospective_transition.json": _file_bytes(transition),
    }
    for name, payload in sorted(payloads.items()):
        _write_no_replace(output_dir / name, payload)
    sealed = _artifact_manifest(output_dir, run_id=RUN_ID, scope="sealed_evidence")
    _write_no_replace(output_dir / "sealed_evidence_manifest.json", _file_bytes(sealed))
    report = cast(
        models.PreflightReport,
        models.make_identity(
            models.PreflightReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "external_anchor_id": anchor.anchor_id,
                "source_commit": source_commit,
                "source_tree": source_tree,
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "package_catalog_id": catalog.catalog_id,
                "writer_implementation_binding_id": writer_binding.binding_id,
                "terminal_registry_id": registry.registry_id,
                "raw_descriptor_contract_id": raw_contract.contract_id,
                "result_descriptor_contract_id": result_contract.contract_id,
                "attempt_trace_contract_id": trace_contract.contract_id,
                "outcome_row_contract_id": outcome_contract.contract_id,
                "evaluator_contract_id": evaluator_contract.contract_id,
                "evaluation_id": evaluation.evaluation_id,
                "fresh_authority_audit_id": fresh.audit_id,
                "evidence_dag_audit_id": dag.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
                "transition_id": transition.transition_id,
                "sealed_evidence_manifest_id": sealed.manifest_id,
                "sealed_evidence_artifact_root": sealed.artifact_root,
                "decision": (
                    "fresh_artifact_backed_outcome_authority_preflight_passed_"
                    "independent_audit_required_online_execution_blocked"
                ),
            },
            field="report_id",
            prefix="finance_v26_195_fresh_outcome_preflight_report:",
        ),
    )
    _write_no_replace(output_dir / "report.json", _file_bytes(report))
    distribution = _artifact_manifest(output_dir, run_id=RUN_ID, scope="distribution")
    _write_no_replace(output_dir / "artifact_manifest.json", _file_bytes(distribution))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--audit-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build(
        repository_root=args.repository_root.resolve(),
        audit_path=args.audit_path.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
