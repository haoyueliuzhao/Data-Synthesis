from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Final, NoReturn, cast, get_args

from pydantic import BaseModel

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.task import fresh_artifact_backed_outcome_authority as authority
from trusted_synthesis.experiments.vtdo_experiment import (
    json_explicit_authoritative_execution_kernel as execution_kernel,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_models as v194_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_preflight as v194,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_outcome_authority_independent_audit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_explicit_prompt_contract_preflight as v192,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_prompt_authority_repair_models as v193_models,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = (
    "finance_v26_196_fresh_artifact_backed_outcome_authority_independent_audit_v1_20260901"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
AUDITED_V195_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_195_fresh_artifact_backed_outcome_authority_preflight_v1_20260901"
)
AUDITED_V194_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_194_authoritative_execution_kernel_parent_preflight_v1_20260901"
)
AUDITED_SOURCE_COMMIT: Final = "9c48c3bf308a93a908bfcea0dce2c3315044dd3d"
AUDITED_SOURCE_TREE: Final = "ec0875ab2325502563dadb528c4a893a31c7293c"
AUDITED_ARTIFACT_COMMIT: Final = "4ce98dbd711f3264e62ce2c6ee3d268c0144a113"
AUDITED_ARTIFACT_TREE: Final = "8a16aee93c24fb07d4657e829ee086214515ed3d"
AUDITED_REPORT_ID: Final = (
    "finance_v26_195_fresh_outcome_preflight_report:"
    "ec2ae9613cd4110a41eb74de005a2ec0e4c6aa0e062dde76a7e6ff5f9eba5264"
)
AUDITED_SEALED_ROOT: Final = (
    "finance_v26_195_sealed_evidence_artifact_root:"
    "be910ff7aa14a082cf83c218968937a140c09a212761304f247d982ad2d0762c"
)
AUDITED_DISTRIBUTION_ROOT: Final = (
    "finance_v26_195_distribution_artifact_root:"
    "ad4a020b60938855d730603033cfc62ba73d9498b69897f20410d4bcf56d1a77"
)
AUDITED_MANIFEST_SHA256: Final = "27bfa3a52481a665c67085d3ba73db425f7a02f44ad47ad76946c87d3ad53f23"
AUDITED_MANIFEST_BYTES: Final = 75_898
EXPECTED_EXTERNAL_AUDIT_SHA256: Final = (
    "19531134d019d4724a97602c14a95da57db6a05b28e32c2568bc8faeb5937ed9"
)
EXPECTED_EXTERNAL_AUDIT_BYTES: Final = 8_957
EXPECTED_FORMAL_FILE_COUNT: Final = 403
EXPECTED_FORMAL_BYTE_COUNT: Final = 2_300_542

REACHABLE_TERMINALS: Final = tuple(
    value
    for value in get_args(authority.TerminalKind)
    if value not in {"policy_horizon_exhausted", "measurement_support_exit"}
)
NOT_APPLICABLE_TERMINALS: Final = (
    "measurement_support_exit",
    "policy_horizon_exhausted",
)


class IndependentAuditError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}:{reason}")


def _fail(stage: str, reason: str) -> NoReturn:
    raise IndependentAuditError(stage, reason)


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", warnings=False)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _canonical_bytes(value: Any, *, newline: bool = True) -> bytes:
    payload = json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return payload + (b"\n" if newline else b"")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_hash(value: Any, *, prefix: str) -> str:
    return prefix + _sha256_bytes(_canonical_bytes(value, newline=False))


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _git(repository_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(repository_root), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git_identity(repository_root: Path) -> tuple[str, str]:
    return (
        _git(repository_root, "rev-parse", "HEAD^{commit}"),
        _git(repository_root, "rev-parse", "HEAD^{tree}"),
    )


def _file_binding(path: Path, *, relative_to: Path) -> models.FileBinding:
    payload = path.read_bytes()
    return models.FileBinding(
        relative_path=path.relative_to(relative_to).as_posix(),
        sha256=_sha256_bytes(payload),
        byte_count=len(payload),
    )


def _recursive_bindings(root: Path) -> tuple[models.FileBinding, ...]:
    bindings: list[models.FileBinding] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            _fail("formal.files", f"formal directory contains symlink:{path}")
        if path.is_dir():
            continue
        if not path.is_file():
            _fail("formal.files", f"formal directory contains nonregular file:{path}")
        bindings.append(_file_binding(path, relative_to=root))
    return tuple(bindings)


def _authorization(audit_path: Path) -> tuple[models.IndependentAuditAuthorization, bytes]:
    try:
        payload = audit_path.read_bytes()
    except FileNotFoundError:
        _fail("authorization", "independent audit parent is missing")
    if len(payload) != EXPECTED_EXTERNAL_AUDIT_BYTES or _sha256_bytes(payload) != (
        EXPECTED_EXTERNAL_AUDIT_SHA256
    ):
        _fail("authorization", "independent audit parent bytes differ")
    authorization = cast(
        models.IndependentAuditAuthorization,
        models.make_identity(
            models.IndependentAuditAuthorization,
            {
                "audit_sha256": EXPECTED_EXTERNAL_AUDIT_SHA256,
                "audit_byte_count": EXPECTED_EXTERNAL_AUDIT_BYTES,
                "conditional_successor": (
                    "frozen_v26_194_192_job_online_development_execution_only_if_all_three_"
                    "audit_gates_pass"
                ),
            },
            field="authorization_id",
            prefix="finance_v26_196_external_independent_audit_authorization:",
        ),
    )
    return authorization, payload


def _verify_manifest_and_formal_directory(root: Path) -> tuple[models.FileBinding, ...]:
    bindings = _recursive_bindings(root)
    if len(bindings) != EXPECTED_FORMAL_FILE_COUNT:
        _fail("formal.files", "v26.195 formal file denominator differs")
    if sum(item.byte_count for item in bindings) != EXPECTED_FORMAL_BYTE_COUNT:
        _fail("formal.bytes", "v26.195 formal byte denominator differs")
    manifest_path = root / "artifact_manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    if (
        len(manifest_bytes) != AUDITED_MANIFEST_BYTES
        or _sha256_bytes(manifest_bytes) != AUDITED_MANIFEST_SHA256
    ):
        _fail("formal.manifest", "v26.195 distribution Manifest bytes differ")
    manifest = _load(manifest_path)
    members = manifest.get("members")
    if not isinstance(members, list) or len(members) != 402:
        _fail("formal.manifest", "v26.195 distribution Manifest denominator differs")
    expected_by_path = {item.relative_path: item for item in bindings}
    observed_paths: list[str] = []
    for item in members:
        relative_path = item["relative_path"]
        observed_paths.append(relative_path)
        binding = expected_by_path.get(relative_path)
        if binding is None or (binding.sha256, binding.byte_count) != (
            item["sha256"],
            item["byte_count"],
        ):
            _fail("formal.manifest", "v26.195 Manifest member differs from actual bytes")
    if observed_paths != sorted(set(observed_paths)):
        _fail("formal.manifest", "v26.195 Manifest member ordering or uniqueness differs")
    if set(expected_by_path) != set(observed_paths) | {"artifact_manifest.json"}:
        _fail("formal.manifest", "v26.195 Manifest member set differs from directory")
    expected_root = _canonical_hash(
        tuple(members),
        prefix="finance_v26_195_distribution_artifact_root:",
    )
    if manifest.get("artifact_root") != expected_root or expected_root != (
        AUDITED_DISTRIBUTION_ROOT
    ):
        _fail("formal.manifest", "v26.195 distribution Root differs")
    canonical_count = 0
    for binding in bindings:
        if binding.relative_path.endswith(".json"):
            payload = (root / binding.relative_path).read_bytes()
            decoded = json.loads(payload)
            if payload not in {
                _canonical_bytes(decoded, newline=False),
                _canonical_bytes(decoded, newline=True),
            }:
                _fail("formal.canonical", f"noncanonical JSON:{binding.relative_path}")
            canonical_count += 1
    if canonical_count != 402:
        _fail("formal.canonical", "v26.195 canonical JSON denominator differs")
    return bindings


def _v195_freeze(
    *,
    repository_root: Path,
    authorization: models.IndependentAuditAuthorization,
) -> models.V195FreezeAudit:
    if _git(repository_root, "rev-parse", f"{AUDITED_SOURCE_COMMIT}^{{tree}}") != (
        AUDITED_SOURCE_TREE
    ):
        _fail("freeze.source", "v26.195 source tree differs")
    if _git(repository_root, "rev-parse", f"{AUDITED_ARTIFACT_COMMIT}^{{tree}}") != (
        AUDITED_ARTIFACT_TREE
    ):
        _fail("freeze.artifact", "v26.195 artifact tree differs")
    root = repository_root / AUDITED_V195_DIR
    bindings = _verify_manifest_and_formal_directory(root)
    report = _load(root / "report.json")
    expected = {
        "source_commit": AUDITED_SOURCE_COMMIT,
        "source_tree": AUDITED_SOURCE_TREE,
        "report_id": AUDITED_REPORT_ID,
        "sealed_evidence_artifact_root": AUDITED_SEALED_ROOT,
        "execution_contract_id": (
            "authoritative_execution_kernel_contract:"
            "53dccfcd1a4516ae8c79c9b64cd41193b99e8594598a25049335db565070786d"
        ),
        "manifest_id": (
            "authoritative_kernel_manifest:"
            "15da508affe0a4727f85fbc727ac1a4b6772b014fdb6a40d4e5c93ae374cd803"
        ),
        "runner_id": (
            "authoritative_execution_kernel_runner:"
            "7a3b8ae6bfb178c351f10a00c08c18373ee61f0bf64b500f245644cc99e1e034"
        ),
        "package_catalog_id": (
            "authoritative_kernel_package_catalog:"
            "cd7bee78c7ed7bc618d7b4d6441546264d1a6392336dceedee9abb89ea7e7211"
        ),
        "terminal_registry_id": (
            "fresh_kernel_terminal_registry:"
            "a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
        ),
        "raw_descriptor_contract_id": (
            "fresh_raw_execution_descriptor_contract:"
            "d18a1ce55e7e223cc4baf0cec054252beacfb7e46a34f0a3f3c98b8830ec0f6c"
        ),
        "result_descriptor_contract_id": (
            "fresh_job_result_descriptor_contract:"
            "6ae9c0bfcdc610f817e783941c60300c5d15947b5eea8052f67b9a61a04eb9f5"
        ),
        "attempt_trace_contract_id": (
            "fresh_job_bound_attempt_trace_contract:"
            "012365c9a24f52899ff83cd54846708ecd6fb79c570bf671eb6a28560ed6a141"
        ),
        "outcome_row_contract_id": (
            "fresh_outcome_row_contract:"
            "c11f5e5540e7dea3dd4b40f2e17a1a9b0464e958cc289c3966369ad39fe40035"
        ),
        "evaluator_contract_id": (
            "fresh_exact_evidence_set_evaluator_contract:"
            "af7f9630a81ea9227570996e8e3a60ddebd1cef2a82d3257c0d90f1fd247f62b"
        ),
        "writer_implementation_binding_id": (
            "fresh_outcome_writer_implementation_binding:"
            "d4cfa2626b454bd1c124c48c929c4993f9eced9c56aa35f58181e813e80d24b9"
        ),
        "external_anchor_id": (
            "finance_v26_194_external_anchor:"
            "966762eba752011f16c4097c105d24755e668e0d6f7f8252376659d72d28f8c4"
        ),
    }
    matches = sum(report.get(key) == value for key, value in expected.items())
    if matches != len(expected):
        _fail("freeze.parents", "v26.195 Report upstream constant differs")
    raw_count = sum(item.relative_path.startswith("raw/") for item in bindings)
    result_count = sum(item.relative_path.startswith("result/") for item in bindings)
    root_count = sum("/" not in item.relative_path for item in bindings)
    if (raw_count, result_count, root_count) != (192, 192, 19):
        _fail("freeze.denominator", "v26.195 file partition differs")
    return cast(
        models.V195FreezeAudit,
        models.make_identity(
            models.V195FreezeAudit,
            {
                "authorization_id": authorization.authorization_id,
                "source_commit": AUDITED_SOURCE_COMMIT,
                "source_tree": AUDITED_SOURCE_TREE,
                "artifact_commit": AUDITED_ARTIFACT_COMMIT,
                "artifact_tree": AUDITED_ARTIFACT_TREE,
                "report_id": AUDITED_REPORT_ID,
                "sealed_artifact_root": AUDITED_SEALED_ROOT,
                "distribution_artifact_root": AUDITED_DISTRIBUTION_ROOT,
                "upstream_constant_match_count": matches,
                "upstream_constant_count": len(expected),
            },
            field="audit_id",
            prefix="finance_v26_196_v195_freeze_audit:",
        ),
    )


def _run(*args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, check=True, capture_output=True, env=env)


def _formal_rebuild(
    *,
    repository_root: Path,
    authorization: models.IndependentAuditAuthorization,
    freeze: models.V195FreezeAudit,
) -> models.FormalRebuildAudit:
    frozen_root = repository_root / AUDITED_V195_DIR
    frozen = _recursive_bindings(frozen_root)
    with tempfile.TemporaryDirectory(prefix="v26-196-v195-rebuild-") as temporary:
        temporary_root = Path(temporary)
        clone = temporary_root / "source"
        rebuilt = temporary_root / "rebuilt"
        _run(
            "git",
            "clone",
            "--quiet",
            "--shared",
            "--no-checkout",
            str(repository_root),
            str(clone),
        )
        _run("git", "-C", str(clone), "sparse-checkout", "init", "--no-cone")
        _run(
            "git",
            "-C",
            str(clone),
            "sparse-checkout",
            "set",
            "/trusted_data_synthesis/src/",
            "/trusted_data_synthesis/tests/fixtures/v26_194_fresh_outcome_authority_audit.txt",
            "/" + AUDITED_V194_DIR + "/",
        )
        _run("git", "-C", str(clone), "checkout", "--quiet", "--detach", AUDITED_SOURCE_COMMIT)
        detached_commit, detached_tree = _git_identity(clone)
        if (detached_commit, detached_tree) != (AUDITED_SOURCE_COMMIT, AUDITED_SOURCE_TREE):
            _fail("rebuild.source", "detached v26.195 source identity differs")
        environment = os.environ.copy()
        environment.pop("DEEPSEEK_API_KEY", None)
        environment["PYTHONPATH"] = str(clone / "trusted_data_synthesis/src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        _run(
            sys.executable,
            "-m",
            "trusted_synthesis.experiments.vtdo_experiment."
            "phase1_v26_fresh_artifact_backed_outcome_authority_preflight",
            "--repository-root",
            str(clone),
            "--audit-path",
            str(
                clone / "trusted_data_synthesis/tests/fixtures/"
                "v26_194_fresh_outcome_authority_audit.txt"
            ),
            "--output-dir",
            str(rebuilt),
            env=environment,
        )
        observed = _verify_manifest_and_formal_directory(rebuilt)
        frozen_map = {item.relative_path: item for item in frozen}
        observed_map = {item.relative_path: item for item in observed}
        if frozen_map != observed_map:
            _fail("rebuild.bindings", "rebuilt v26.195 file binding set differs")
        byte_matches = sum(
            (frozen_root / relative).read_bytes() == (rebuilt / relative).read_bytes()
            for relative in sorted(frozen_map)
        )
        if byte_matches != EXPECTED_FORMAL_FILE_COUNT:
            _fail("rebuild.bytes", "rebuilt v26.195 file bytes differ")
    return cast(
        models.FormalRebuildAudit,
        models.make_identity(
            models.FormalRebuildAudit,
            {
                "authorization_id": authorization.authorization_id,
                "v195_freeze_audit_id": freeze.audit_id,
            },
            field="audit_id",
            prefix="finance_v26_196_v195_formal_rebuild_audit:",
        ),
    )


def _load_v194_parents(
    repository_root: Path,
) -> tuple[
    v194_models.AuthoritativeRunnerPackageCatalog,
    v194_models.AuthoritativeDevelopmentManifest,
    v194_models.AuthoritativeRunnerContract,
    v194_models.AuthoritativeExecutionContract,
]:
    root = repository_root / AUDITED_V194_DIR
    return (
        v194_models.AuthoritativeRunnerPackageCatalog.model_validate(
            _load(root / "authoritative_runner_package_catalog.json")
        ),
        v194_models.AuthoritativeDevelopmentManifest.model_validate(
            _load(root / "authoritative_development_manifest.json")
        ),
        v194_models.AuthoritativeRunnerContract.model_validate(
            _load(root / "authoritative_runner_contract.json")
        ),
        v194_models.AuthoritativeExecutionContract.model_validate(
            _load(root / "authoritative_execution_contract.json")
        ),
    )


def _terminal_totality(
    *,
    repository_root: Path,
    authorization: models.IndependentAuditAuthorization,
) -> models.ProductionTerminalTotalityAudit:
    _, manifest, runner, execution = _load_v194_parents(repository_root)
    v192_root = repository_root / v194.V192_DIR
    prompt_contract = v192.JsonExplicitPromptContract.model_validate(
        _load(v192_root / "json_explicit_prompt_contract.json")
    )
    prompt_schema = v192.JsonExplicitPromptSchema.model_validate(
        _load(v192_root / "json_explicit_prompt_schema.json")
    )
    config = AgentModelConfig.model_validate(_load(repository_root / v194.MODEL_PROFILE)["model"])
    evidence = v193_models.ExactPromptEvidenceSet.model_validate(
        _load(repository_root / v194.V193_DIR / "exact_prompt_evidence_set.json")
    )
    rows_by_source: dict[str, list[Any]] = {}
    for row in evidence.rows:
        rows_by_source.setdefault(row.coordinate.fresh_job_id, []).append(row)
    jobs = tuple(sorted(manifest.jobs, key=lambda item: item.job_id))[:16]
    controls: list[models.TerminalControlObservation] = []
    with tempfile.TemporaryDirectory(prefix="v26-196-terminal-gap-") as temporary:
        root = Path(temporary)
        writer = execution_kernel.NoReplaceKernelJournalWriter(root)
        client = v194._ZeroProviderCertifiedClient(config)  # noqa: SLF001
        kernel = execution_kernel.AuthoritativeJsonExplicitExecutionKernel(
            execution_contract_id=execution.contract_id,
            runner_id=runner.runner_id,
            manifest_id=manifest.manifest_id,
            prompt_contract=prompt_contract,
            prompt_schema=prompt_schema,
            client=client,
            writer=writer,
        )
        for terminal_kind, job in zip(REACHABLE_TERMINALS, jobs, strict=True):
            source_rows = sorted(
                rows_by_source[job.source_job_id],
                key=lambda item: item.coordinate.invocation_index,
            )
            source = source_rows[0]
            rendered = json.loads(source.rendered_prompt)
            kernel.invoke(
                job_id=job.job_id,
                logical_request_index=0,
                prompt_kind=source.coordinate.prompt_kind,
                public_attempt_phase=(
                    "semantic_recovery"
                    if source.coordinate.prompt_kind == "correction"
                    else "primary"
                ),
                core=rendered["prompt_core"],
            )
            kernel.complete_job(job_id=job.job_id)
            safe = hashlib.sha256(job.job_id.encode("utf-8")).hexdigest()
            raw_bytes = (root / "raw" / f"{safe}.json").read_bytes()
            result_bytes = (root / "result" / f"{safe}.json").read_bytes()
            raw_payload = json.loads(raw_bytes)
            result_payload = json.loads(result_bytes)
            if raw_bytes != _canonical_bytes(raw_payload, newline=False):
                _fail("terminal.raw", "v26.194 control Raw is not canonical JSON")
            if result_bytes != _canonical_bytes(result_payload, newline=False):
                _fail("terminal.result", "v26.194 control Result is not canonical JSON")
            if result_payload.get("terminal") != "fixture_complete":
                _fail("terminal.fixture", "v26.194 completion shape unexpectedly changed")
            controls.append(
                cast(
                    models.TerminalControlObservation,
                    models.make_identity(
                        models.TerminalControlObservation,
                        {
                            "target_terminal_kind": terminal_kind,
                            "exact_job_id": job.job_id,
                            "actual_runner_entry": (
                                "AuthoritativeJsonExplicitExecutionKernel.invoke_then_complete_job"
                            ),
                            "actual_completion_symbol": (
                                "json_explicit_authoritative_execution_kernel."
                                "AuthoritativeJsonExplicitExecutionKernel.complete_job"
                            ),
                            "actual_writer_symbol": (
                                "json_explicit_authoritative_execution_kernel."
                                "NoReplaceKernelJournalWriter"
                            ),
                            "first_failed_seam": (
                                "v26_194_complete_job_emits_fixture_complete_without_terminal_"
                                "dispatch"
                            ),
                        },
                        field="observation_id",
                        prefix="finance_v26_196_terminal_control_observation:",
                    ),
                )
            )
        kernel.assert_closed()
        if client.local_invocation_count != 16:
            _fail("terminal.invocation", "terminal audit local invocation denominator differs")
    return cast(
        models.ProductionTerminalTotalityAudit,
        models.make_identity(
            models.ProductionTerminalTotalityAudit,
            {
                "authorization_id": authorization.authorization_id,
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "terminal_registry_id": (
                    "fresh_kernel_terminal_registry:"
                    "a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
                ),
                "controls": tuple(controls),
            },
            field="audit_id",
            prefix="finance_v26_196_production_terminal_totality_audit:",
        ),
    )


def _load_fresh_parents(
    repository_root: Path,
) -> tuple[Any, ...]:
    root = repository_root / AUDITED_V195_DIR
    catalog, manifest, runner, execution = _load_v194_parents(repository_root)
    return (
        catalog,
        manifest,
        runner,
        execution,
        authority.FreshTerminalRegistry.model_validate(
            _load(root / "fresh_terminal_registry.json")
        ),
        authority.FreshRawExecutionDescriptorContract.model_validate(
            _load(root / "fresh_raw_execution_descriptor_contract.json")
        ),
        authority.FreshJobResultDescriptorContract.model_validate(
            _load(root / "fresh_job_result_descriptor_contract.json")
        ),
        authority.FreshJobBoundAttemptTraceContract.model_validate(
            _load(root / "fresh_job_bound_attempt_trace_contract.json")
        ),
        authority.FreshOutcomeRowContract.model_validate(
            _load(root / "fresh_outcome_row_contract.json")
        ),
        authority.FreshExactEvidenceSetEvaluatorContract.model_validate(
            _load(root / "fresh_exact_evidence_set_evaluator_contract.json")
        ),
    )


def _not_applicable_audit(repository_root: Path) -> models.NotApplicableTerminalExclusionAudit:
    parents = _load_fresh_parents(repository_root)
    reasons: list[str] = []
    for _terminal in NOT_APPLICABLE_TERMINALS:
        try:
            authority.evaluate_fresh_evidence_set(
                artifact_root=repository_root / AUDITED_V195_DIR,
                bundles=(),
                catalog=parents[0],
                manifest=parents[1],
                runner=parents[2],
                execution=parents[3],
                registry=parents[4],
                raw_contract=parents[5],
                result_contract=parents[6],
                trace_contract=parents[7],
                outcome_contract=parents[8],
                evaluator_contract=parents[9],
                expected_evidence_kind="empirical_execution",
            )
        except ValueError as error:
            reasons.append(str(error))
        else:
            _fail("not_applicable", "not-applicable terminal entered empirical evaluator")
    expected = "empirical evaluation remains unauthorized pending independent audit"
    if reasons != [expected, expected]:
        _fail("not_applicable", "not-applicable rejection reason differs")
    return cast(
        models.NotApplicableTerminalExclusionAudit,
        models.make_identity(
            models.NotApplicableTerminalExclusionAudit,
            {
                "terminal_registry_id": parents[4].registry_id,
                "terminal_kinds": NOT_APPLICABLE_TERMINALS,
                "exact_rejection_reason": expected,
            },
            field="audit_id",
            prefix="finance_v26_196_not_applicable_terminal_exclusion_audit:",
        ),
    )


def _authorization_control(name: str, reason: str) -> models.AuthorizationControl:
    return cast(
        models.AuthorizationControl,
        models.make_identity(
            models.AuthorizationControl,
            {"control_name": name, "rejected": True, "rejection_reason": reason},
            field="control_id",
            prefix="finance_v26_196_online_authorization_control:",
        ),
    )


def _authorization_parent_audit(
    *,
    audit_path: Path,
    authorization: models.IndependentAuditAuthorization,
) -> models.OnlineAuthorizationParentAudit:
    controls: list[models.AuthorizationControl] = []
    with tempfile.TemporaryDirectory(prefix="v26-196-authorization-") as temporary:
        root = Path(temporary)
        missing = root / "missing.txt"
        try:
            _authorization(missing)
        except IndependentAuditError as error:
            controls.append(_authorization_control("missing_parent", error.reason))
        else:
            _fail("authorization.control", "missing parent was accepted")
        forged = root / "forged.txt"
        forged.write_bytes(audit_path.read_bytes() + b"forged")
        try:
            _authorization(forged)
        except IndependentAuditError as error:
            controls.append(_authorization_control("forged_parent_bytes", error.reason))
        else:
            _fail("authorization.control", "forged parent was accepted")
        self_declared = root / "self-declared.json"
        self_declared.write_bytes(
            _canonical_bytes({"authorization_id": authorization.authorization_id})
        )
        try:
            _authorization(self_declared)
        except IndependentAuditError as error:
            controls.append(_authorization_control("self_declared_parent", error.reason))
        else:
            _fail("authorization.control", "self-declared parent was accepted")
    evaluator_signature = inspect.signature(authority.evaluate_fresh_evidence_set)
    kernel_signature = inspect.signature(execution_kernel.AuthoritativeJsonExplicitExecutionKernel)
    ingress_exists = "authorization" in evaluator_signature.parameters or (
        "authorization" in kernel_signature.parameters
    )
    if ingress_exists:
        _fail("authorization.ingress", "frozen online authorization ingress unexpectedly changed")
    controls.append(
        _authorization_control(
            "legal_external_parent_online_ingress",
            "legal audit parent has no frozen online precredential ingress",
        )
    )
    return cast(
        models.OnlineAuthorizationParentAudit,
        models.make_identity(
            models.OnlineAuthorizationParentAudit,
            {
                "authorization_id": authorization.authorization_id,
                "controls": tuple(controls),
            },
            field="audit_id",
            prefix="finance_v26_196_online_authorization_parent_audit:",
        ),
    )


def _gate(name: str, passed: bool, *evidence_ids: str) -> models.StaticGate:
    return models.StaticGate(name=name, passed=passed, evidence_ids=tuple(evidence_ids))


def _artifact_manifest(
    payloads: dict[str, bytes], *, run_id: str, scope: str
) -> models.ArtifactManifest:
    members = tuple(
        models.ArtifactMember(
            relative_path=name,
            sha256=_sha256_bytes(payload),
            byte_count=len(payload),
        )
        for name, payload in sorted(payloads.items())
    )
    root = _canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix=f"finance_v26_196_{scope}_artifact_root:",
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
                "artifact_root": root,
                "scope": scope,
            },
            field="manifest_id",
            prefix=f"finance_v26_196_{scope}_artifact_manifest:",
        ),
    )


def build(
    *,
    repository_root: Path,
    audit_path: Path,
    output_dir: Path,
) -> models.IndependentAuditReport:
    authorization, audit_bytes = _authorization(audit_path)
    freeze = _v195_freeze(repository_root=repository_root, authorization=authorization)
    rebuild = _formal_rebuild(
        repository_root=repository_root,
        authorization=authorization,
        freeze=freeze,
    )
    totality = _terminal_totality(
        repository_root=repository_root,
        authorization=authorization,
    )
    not_applicable = _not_applicable_audit(repository_root)
    authorization_parent = _authorization_parent_audit(
        audit_path=audit_path,
        authorization=authorization,
    )
    gates = (
        _gate("exact_external_independent_audit_parent", True, authorization.authorization_id),
        _gate("v26_195_source_and_artifact_freeze", True, freeze.audit_id),
        _gate("v26_195_exact_403_file_rebuild", True, rebuild.audit_id),
        _gate("v26_195_exact_upstream_constant_replay", True, freeze.audit_id),
        _gate("exact_16_reachable_terminal_partition", True, totality.audit_id),
        _gate("production_terminal_to_fresh_outcome_totality", False, totality.audit_id),
        _gate("not_applicable_terminals_excluded", True, not_applicable.audit_id),
        _gate("external_online_authorization_ingress", False, authorization_parent.audit_id),
        _gate("six_outcome_contract_ids_unchanged", True, authorization_parent.audit_id),
        _gate("provider_calls_zero", True, totality.audit_id),
        _gate("development_outcomes_zero", True, totality.audit_id),
        _gate("empirical_rows_and_estimates_zero", True, not_applicable.audit_id),
        _gate("qa_branch_unchanged", True, freeze.audit_id),
        _gate("online_execution_remains_blocked", True, authorization_parent.audit_id),
    )
    static = cast(
        models.StaticAudit,
        models.make_identity(
            models.StaticAudit,
            {
                "gates": gates,
                "gate_count": len(gates),
                "passed_count": sum(item.passed for item in gates),
                "failed_count": sum(not item.passed for item in gates),
            },
            field="audit_id",
            prefix="finance_v26_196_static_audit:",
        ),
    )
    decision = cast(
        models.IndependentAuditDecision,
        models.make_identity(
            models.IndependentAuditDecision,
            {
                "authorization_id": authorization.authorization_id,
                "formal_rebuild_audit_id": rebuild.audit_id,
                "terminal_totality_audit_id": totality.audit_id,
                "authorization_parent_audit_id": authorization_parent.audit_id,
                "static_audit_id": static.audit_id,
                "decision": (
                    "fresh_outcome_authority_independent_audit_failed_at_terminal_to_"
                    "persistence_integration"
                ),
                "first_failed_gate": "production_terminal_to_fresh_outcome_totality",
                "first_failed_seam": (
                    "v26_194_complete_job_emits_fixture_complete_without_terminal_dispatch"
                ),
            },
            field="decision_id",
            prefix="finance_v26_196_independent_audit_decision:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        models.make_identity(
            models.ProspectiveTransition,
            {
                "decision_id": decision.decision_id,
                "permitted_change": (
                    "first_terminal_to_fresh_outcome_and_external_authorization_ingress_seam_only"
                ),
            },
            field="transition_id",
            prefix="finance_v26_196_transition:",
        ),
    )
    source_commit, source_tree = _git_identity(repository_root)
    payloads: dict[str, bytes] = {
        "external_v26_195_independent_audit.txt": audit_bytes,
        "external_independent_audit_authorization.json": _canonical_bytes(authorization),
        "v26_195_source_and_artifact_freeze_audit.json": _canonical_bytes(freeze),
        "v26_195_formal_rebuild_audit.json": _canonical_bytes(rebuild),
        "production_terminal_totality_audit.json": _canonical_bytes(totality),
        "not_applicable_terminal_exclusion_audit.json": _canonical_bytes(not_applicable),
        "online_authorization_parent_audit.json": _canonical_bytes(authorization_parent),
        "static_audit.json": _canonical_bytes(static),
        "independent_audit_decision.json": _canonical_bytes(decision),
        "prospective_transition.json": _canonical_bytes(transition),
    }
    sealed = _artifact_manifest(payloads, run_id=RUN_ID, scope="sealed_evidence")
    payloads["sealed_evidence_manifest.json"] = _canonical_bytes(sealed)
    report = cast(
        models.IndependentAuditReport,
        models.make_identity(
            models.IndependentAuditReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "source_commit": source_commit,
                "source_tree": source_tree,
                "v195_freeze_audit_id": freeze.audit_id,
                "formal_rebuild_audit_id": rebuild.audit_id,
                "terminal_totality_audit_id": totality.audit_id,
                "not_applicable_audit_id": not_applicable.audit_id,
                "authorization_parent_audit_id": authorization_parent.audit_id,
                "static_audit_id": static.audit_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
                "sealed_manifest_id": sealed.manifest_id,
                "sealed_artifact_root": sealed.artifact_root,
                "decision": decision.decision,
            },
            field="report_id",
            prefix="finance_v26_196_fresh_outcome_independent_audit_report:",
        ),
    )
    payloads["report.json"] = _canonical_bytes(report)
    distribution = _artifact_manifest(payloads, run_id=RUN_ID, scope="distribution")
    payloads["artifact_manifest.json"] = _canonical_bytes(distribution)
    write_immutable_artifact_directory(output_dir, payloads)
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
