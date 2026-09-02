# ruff: noqa: E501, SLF001
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter, deque
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_models as v194_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_online_execution as v188,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_action_interface_full_condition_integration_preflight_models as v206_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_continuity_independent_audit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight as v209,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_explicit_prompt_contract_preflight as v192,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_prompt_authority_repair_models as v193_models,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = (
    "finance_v26_210_fresh_repaired_full_condition_final_request_"
    "continuity_independent_audit_v1_20260902"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
EXTERNAL_REVIEW_SHA256: Final = "c826ba2618807789f2eb427ddadb54977ad0d8dea9c472ddeef8965ec8319ee3"
EXTERNAL_REVIEW_BYTES: Final = 15_336
OPERATOR_DIRECTIVE: Final = "参照审计开展后续实验"
V209_COMMIT: Final = "5809e9782515e55ee797b43730584d5d860aaa5c"
V209_TREE: Final = "b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf"
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
V194_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_194_authoritative_execution_kernel_parent_preflight_v1_20260901"
)
V193_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_193_json_prompt_authority_repair_preflight_v2_20260901"
)
V192_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_192_json_explicit_prompt_contract_preflight_v1_20260831"
)
MODEL_PROFILE: Final = (
    "trusted_data_synthesis/config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
)
IMPLEMENTATION_FILES: Final = tuple(
    sorted(
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_full_condition_final_request_continuity_independent_audit.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_full_condition_final_request_continuity_independent_audit_models.py",
            "trusted_data_synthesis/tests/"
            "test_v26_fresh_repaired_full_condition_final_request_continuity_independent_audit.py",
        )
    )
)


class V210Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V210Error(stage, reason)


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


def _authorization(
    external_review_path: Path,
) -> tuple[models.ExternalIndependentAuditAuthorization, bytes, bytes]:
    review = external_review_path.read_bytes()
    if len(review) != EXTERNAL_REVIEW_BYTES or _sha(review) != EXTERNAL_REVIEW_SHA256:
        _fail("A0.authorization", "v26.210 external review bytes differ")
    directive = OPERATOR_DIRECTIVE.encode("utf-8")
    authorization = cast(
        models.ExternalIndependentAuditAuthorization,
        _make(
            models.ExternalIndependentAuditAuthorization,
            {
                "review_sha256": _sha(review),
                "review_byte_count": len(review),
                "operator_directive_sha256": _sha(directive),
                "operator_directive_byte_count": len(directive),
            },
            "authorization_id",
            "finance_v26_210_external_independent_audit_authorization:",
        ),
    )
    return authorization, review, directive


@dataclass(frozen=True)
class SavedV209:
    root: Path
    report: v209_models.FinalRequestContinuityPreflightReport
    gate: v209_models.FinalRequestContinuityGateAudit
    transition: v209_models.ProspectiveTransition
    source: v209_models.SourceIdentity
    implementation: v209_models.ImplementationBinding
    manifest: v209_models.ExecutableDevelopmentManifest
    execution: v209_models.ExecutableExecutionContract
    census: v209_models.ExecutableInvocationCensus
    continuity: v209_models.FrozenRequestContinuityAudit
    dynamic: v209_models.DynamicNonReferenceBranchAudit
    artifact: v209_models.ArtifactManifest
    file_names: tuple[str, ...]


def _saved_v209(repository_root: Path) -> SavedV209:
    root = repository_root / V209_DIR
    artifact = v209_models.ArtifactManifest.model_validate(_load(root / "artifact_manifest.json"))
    names = tuple(sorted(path.name for path in root.iterdir() if path.is_file()))
    if len(names) != 21 or sum((root / name).stat().st_size for name in names) != 44_916_386:
        _fail("A0.saved_geometry", "v26.209 formal directory geometry differs")
    if {item.relative_path for item in artifact.members} != set(names) - {"artifact_manifest.json"}:
        _fail("A0.saved_paths", "v26.209 Manifest path set differs")
    for member in artifact.members:
        payload = (root / member.relative_path).read_bytes()
        if len(payload) != member.byte_count or _sha(payload) != member.sha256:
            _fail("A0.saved_bytes", f"v26.209 formal member differs:{member.relative_path}")
    saved = SavedV209(
        root=root,
        report=v209_models.FinalRequestContinuityPreflightReport.model_validate(
            _load(root / "report.json")
        ),
        gate=v209_models.FinalRequestContinuityGateAudit.model_validate(
            _load(root / "final_request_continuity_gate_audit.json")
        ),
        transition=v209_models.ProspectiveTransition.model_validate(
            _load(root / "prospective_transition.json")
        ),
        source=v209_models.SourceIdentity.model_validate(_load(root / "source_identity.json")),
        implementation=v209_models.ImplementationBinding.model_validate(
            _load(root / "implementation_binding.json")
        ),
        manifest=v209_models.ExecutableDevelopmentManifest.model_validate(
            _load(root / "executable_development_manifest.json")
        ),
        execution=v209_models.ExecutableExecutionContract.model_validate(
            _load(root / "executable_execution_contract.json")
        ),
        census=v209_models.ExecutableInvocationCensus.model_validate(
            _load(root / "executable_invocation_census.json")
        ),
        continuity=v209_models.FrozenRequestContinuityAudit.model_validate(
            _load(root / "frozen_request_continuity_audit.json")
        ),
        dynamic=v209_models.DynamicNonReferenceBranchAudit.model_validate(
            _load(root / "dynamic_nonreference_branch_audit.json")
        ),
        artifact=artifact,
        file_names=names,
    )
    if (
        saved.source.source_commit != V209_COMMIT
        or saved.source.source_tree != V209_TREE
        or saved.report.decision != v209_models.DECISION
        or not saved.gate.all_gates_passed
        or saved.transition.next_stage != v209_models.NEXT_STAGE
        or (
            saved.dynamic.diagnostic_action_dispatch_count,
            saved.dynamic.diagnostic_final_dispatch_count,
            saved.dynamic.diagnostic_transport_dispatch_count,
        )
        != (4, 1, 5)
    ):
        _fail("A0.saved_semantics", "v26.209 frozen decision or corrected dynamic count differs")
    return saved


def _freeze(
    authorization_id: str,
    saved: SavedV209,
) -> models.V209PreflightFreeze:
    return cast(
        models.V209PreflightFreeze,
        _make(
            models.V209PreflightFreeze,
            {
                "authorization_id": authorization_id,
                "v209_report_id": saved.report.report_id,
                "v209_gate_audit_id": saved.gate.audit_id,
                "v209_transition_id": saved.transition.transition_id,
                "v209_manifest_id": saved.manifest.manifest_id,
                "v209_execution_contract_id": saved.execution.contract_id,
                "v209_invocation_census_id": saved.census.census_id,
                "v209_continuity_audit_id": saved.continuity.audit_id,
                "v209_dynamic_branch_audit_id": saved.dynamic.audit_id,
                "v209_artifact_manifest_id": saved.artifact.manifest_id,
                "v209_artifact_root": saved.artifact.artifact_root,
                "v209_source_commit": V209_COMMIT,
                "v209_source_tree": V209_TREE,
                "v209_decision": saved.report.decision,
            },
            "freeze_id",
            "finance_v26_210_v209_preflight_freeze:",
        ),
    )


def _detached_rebuild(
    repository_root: Path,
    freeze_id: str,
    saved: SavedV209,
) -> models.DetachedRebuildAudit:
    with tempfile.TemporaryDirectory(prefix="v26-210-detached-") as temporary:
        base = Path(temporary)
        archive = base / "source.tar"
        snapshot = base / "snapshot"
        snapshot.mkdir()
        subprocess.run(
            ["git", "archive", "--format=tar", f"--output={archive}", V209_COMMIT],
            cwd=repository_root,
            check=True,
            capture_output=True,
        )
        with tarfile.open(archive) as stream:
            stream.extractall(snapshot, filter="data")
        tree = subprocess.run(
            ["git", "rev-parse", f"{V209_COMMIT}^{{tree}}"],
            cwd=repository_root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        if tree != V209_TREE:
            _fail("A0.detached_tree", "v26.209 exact source tree differs")
        archived_files = sum(path.is_file() for path in snapshot.rglob("*"))
        rebuilt = base / "rebuilt"
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(snapshot / "trusted_data_synthesis/src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LC_ALL": "C.UTF-8",
        }
        credential_like = tuple(
            key
            for key in env
            if any(token in key.casefold() for token in ("key", "token", "secret", "credential"))
        )
        if credential_like:
            _fail("A0.detached_environment", f"credential-like environment keys:{credential_like}")
        module = (
            "trusted_synthesis.experiments.vtdo_experiment."
            "phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight"
        )
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                module,
                "--repository-root",
                str(repository_root),
                "--output-dir",
                str(rebuilt),
                "--external-review",
                str(saved.root / "external_review.txt"),
                "--source-commit",
                V209_COMMIT,
                "--source-tree",
                V209_TREE,
            ],
            cwd=snapshot,
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )
        if run.returncode:
            _fail("A0.detached_execution", run.stderr[-4000:])
        rebuilt_names = tuple(sorted(path.name for path in rebuilt.iterdir() if path.is_file()))
        if rebuilt_names != saved.file_names:
            _fail("A0.detached_paths", "detached v26.209 rebuild path set differs")
        sha_matches = byte_count_matches = actual_matches = 0
        for name in rebuilt_names:
            left = (rebuilt / name).read_bytes()
            right = (saved.root / name).read_bytes()
            sha_matches += int(_sha(left) == _sha(right))
            byte_count_matches += int(len(left) == len(right))
            actual_matches += int(left == right)
        rebuilt_total = sum((rebuilt / name).stat().st_size for name in rebuilt_names)
        if (sha_matches, byte_count_matches, actual_matches, rebuilt_total) != (
            21,
            21,
            21,
            44_916_386,
        ):
            _fail(
                "A0.detached_match",
                f"detached match differs:{sha_matches}/{byte_count_matches}/{actual_matches}/{rebuilt_total}",
            )
    return cast(
        models.DetachedRebuildAudit,
        _make(
            models.DetachedRebuildAudit,
            {
                "freeze_id": freeze_id,
                "exact_source_commit": V209_COMMIT,
                "exact_source_tree": V209_TREE,
                "archived_transitive_source_file_count": archived_files,
            },
            "audit_id",
            "finance_v26_210_detached_rebuild_audit:",
        ),
    )


@dataclass(frozen=True)
class IndependentParents:
    profile: v206_models.FullConditionRepairProfile
    source_manifest: v206_models.RepairedDevelopmentManifest
    source_callsites: v206_models.RepairedCallsiteCensus
    source_execution: v206_models.RepairedExecutionContract
    source_estimand: v206_models.ProspectiveEstimandContract
    v194_manifest: v194_models.AuthoritativeDevelopmentManifest
    v193_evidence: v193_models.ExactPromptEvidenceSet
    prompt_contract: v192.JsonExplicitPromptContract
    prompt_schema: v192.JsonExplicitPromptSchema


def _parents(repository_root: Path) -> IndependentParents:
    v206_root = repository_root / V206_DIR
    v194_root = repository_root / V194_DIR
    v193_root = repository_root / V193_DIR
    v192_root = repository_root / V192_DIR
    return IndependentParents(
        profile=v206_models.FullConditionRepairProfile.model_validate(
            _load(v206_root / "full_condition_repair_profile.json")
        ),
        source_manifest=v206_models.RepairedDevelopmentManifest.model_validate(
            _load(v206_root / "repaired_development_manifest.json")
        ),
        source_callsites=v206_models.RepairedCallsiteCensus.model_validate(
            _load(v206_root / "repaired_callsite_census.json")
        ),
        source_execution=v206_models.RepairedExecutionContract.model_validate(
            _load(v206_root / "repaired_execution_contract.json")
        ),
        source_estimand=v206_models.ProspectiveEstimandContract.model_validate(
            _load(v206_root / "prospective_estimand_contract.json")
        ),
        v194_manifest=v194_models.AuthoritativeDevelopmentManifest.model_validate(
            _load(v194_root / "authoritative_development_manifest.json")
        ),
        v193_evidence=v193_models.ExactPromptEvidenceSet.model_validate(
            _load(v193_root / "exact_prompt_evidence_set.json")
        ),
        prompt_contract=v192.JsonExplicitPromptContract.model_validate(
            _load(v192_root / "json_explicit_prompt_contract.json")
        ),
        prompt_schema=v192.JsonExplicitPromptSchema.model_validate(
            _load(v192_root / "json_explicit_prompt_schema.json")
        ),
    )


def _geometry(
    freeze_id: str,
    parents: IndependentParents,
) -> models.IndependentCallsiteGeometryAudit:
    jobs = {item.job_id for item in parents.v194_manifest.jobs}
    evidence = {item.row_id: item for item in parents.v193_evidence.rows}
    rows = tuple(parents.source_callsites.rows)
    phase_counts = Counter(row.phase for row in rows)
    keys = tuple(
        (
            row.fresh_job_id,
            row.invocation_index,
            row.phase,
            row.source_v193_coordinate_id,
        )
        for row in rows
    )
    matches = sum(
        row.source_v194_job_id in jobs
        and row.source_v193_evidence_row_id in evidence
        and evidence[row.source_v193_evidence_row_id].coordinate.coordinate_id
        == row.source_v193_coordinate_id
        and evidence[row.source_v193_evidence_row_id].coordinate.phase == row.phase
        for row in rows
    )
    observed = (
        len(jobs),
        len(rows),
        len(set(keys)),
        phase_counts["first_action"],
        phase_counts["subsequent_action"],
        phase_counts["correction"],
        phase_counts["final"],
        matches,
    )
    if observed != (192, 792, 792, 192, 288, 120, 192, 792):
        _fail("A1.geometry", f"independent callsite geometry differs:{observed}")
    return cast(
        models.IndependentCallsiteGeometryAudit,
        _make(
            models.IndependentCallsiteGeometryAudit,
            {
                "freeze_id": freeze_id,
                "source_v194_manifest_id": parents.v194_manifest.manifest_id,
                "source_v193_evidence_set_id": parents.v193_evidence.evidence_set_id,
                "source_v206_callsite_census_id": parents.source_callsites.census_id,
                "coordinate_set_sha256": models.canonical_sha256(tuple(sorted(keys))),
            },
            "audit_id",
            "finance_v26_210_independent_callsite_geometry_audit:",
        ),
    )


class AuditTransport:
    def __init__(self) -> None:
        self._queue: deque[Mapping[str, Any] | v209.TypedTransportFailure] = deque()
        self.dispatches: list[v209.TransportDispatch] = []

    def queue(self, value: Mapping[str, Any] | v209.TypedTransportFailure) -> None:
        self._queue.append(value)

    def send(self, dispatch: v209.TransportDispatch) -> Mapping[str, Any]:
        if (
            dispatch.receipt.certificate_id != dispatch.certificate.certificate_id
            or dispatch.receipt.request_id != dispatch.certificate.request_id
            or models.canonical_sha256(dispatch.request_body)
            != dispatch.certificate.canonical_request_body_sha256
        ):
            raise v209.TypedTransportFailure(
                "instrument_failure", "independent audit rejected transport parent chain"
            )
        if not self._queue:
            raise v209.TypedTransportFailure(
                "instrument_failure", "independent audit transport queue empty"
            )
        self.dispatches.append(dispatch)
        value = self._queue.popleft()
        if isinstance(value, v209.TypedTransportFailure):
            raise value
        return value


def _runner(
    transport: AuditTransport,
    *,
    config: AgentModelConfig,
    parents: IndependentParents,
    prepared: v188.PreparedExecution,
    implementation_id: str,
) -> v209.FinalContinuityRepairedFullConditionRunner:
    return v209.FinalContinuityRepairedFullConditionRunner(
        transport=transport,
        config=config,
        profile=parents.profile,
        prepared=prepared,
        implementation_id=implementation_id,
        prompt_contract=parents.prompt_contract,
        prompt_schema=parents.prompt_schema,
    )


def _action_payload(
    state_id: str,
    action_id: str,
    profile: v206_models.FullConditionRepairProfile,
) -> dict[str, Any]:
    return {
        "state_id": state_id,
        "action_id": action_id,
        "decision_kind": profile.decision_kind_value,
        "protocol": profile.protocol_value,
    }


def _final_payload(result: Any, source: Any) -> dict[str, Any]:
    result_payload = result.projected_public_answer or {"preflight_status": "completed_invalid"}
    citations = result.public_citations or (
        source.public_task.semantic_task.records[0].record_handle,
    )
    return {
        "answer": {
            "result": result_payload,
            "citations": tuple({"evidence_id": item} for item in citations),
        },
        "rationale_summary": "credential-free executable Runner route-closure preflight",
    }


def _context(
    job: v209_models.ExecutableDevelopmentJob,
    *,
    parents: IndependentParents,
    prepared: v188.PreparedExecution,
) -> Any:
    v206_job = {item.job_id: item for item in parents.source_manifest.jobs}[job.source_v206_job_id]
    v194_job = {item.job_id: item for item in parents.v194_manifest.jobs}[
        v206_job.source_v194_job_id
    ]
    rows = tuple(
        item
        for item in parents.v193_evidence.rows
        if item.coordinate.fresh_job_id == v194_job.source_job_id
    )
    old_ids = {item.coordinate.source_job_id for item in rows}
    if not rows or len(old_ids) != 1:
        _fail("A3.job_parent", "independent Runtime Job parent is not unique")
    old_job = {item.job_id: item for item in prepared.frozen.manifest.jobs}[old_ids.pop()]
    return frozen_runtime.prepare_job(old_job, prepared.runtime_catalog)


def _reference_complete_state(context: Any) -> Any:
    state = frozen_runtime._initialize(context)
    while state.current_index < len(state.ordered_components):
        prompt = step_runtime.render_next_prompt(state)
        rows = frozen_runtime._candidate_dispositions(state, prompt)
        selected = frozen_runtime._reference_selection(state, prompt, rows, state.current_index)
        if selected.action_id is None:
            _fail("A3.reference", "reference Action lacks Action ID")
        output = step_runtime.step(state, selected.action_id)
        if not getattr(output, "action_accepted", False):
            _fail("A3.reference", "reference Action did not commit")
    return state


def _replay(
    *,
    freeze_id: str,
    saved: SavedV209,
    parents: IndependentParents,
    prepared: v188.PreparedExecution,
    config: AgentModelConfig,
) -> tuple[
    models.IndependentExecutableReplayAudit,
    tuple[v209_models.ExecutableInvocationRecord, ...],
]:
    saved_records = {(row.job_id, row.invocation_index): row for row in saved.census.rows}
    all_records: list[v209_models.ExecutableInvocationRecord] = []
    replay_rows: list[models.IndependentReplayJobRow] = []
    correction_distribution: Counter[int] = Counter()
    for job in sorted(saved.manifest.jobs, key=lambda item: item.job_id):
        context = _context(job, parents=parents, prepared=prepared)
        state = frozen_runtime._initialize(context)
        transport = AuditTransport()
        runner = _runner(
            transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=saved.implementation.implementation_id,
        )
        records: list[v209_models.ExecutableInvocationRecord] = []
        subsequent = correction_count = invocation_index = 0
        while state.current_index < len(state.ordered_components):
            component_index = state.current_index
            branch = copy.deepcopy(state)
            prompt = step_runtime.render_next_prompt(state)
            rows = frozen_runtime._candidate_dispositions(state, prompt)
            reference = frozen_runtime._reference_selection(state, prompt, rows, component_index)
            if reference.action_id is None:
                _fail("A3.reference", "reference Action lacks Action ID")
            transport.queue(
                _action_payload(prompt.state.state_token, reference.action_id, parents.profile)
            )
            action = runner.invoke_action(job=job, invocation_index=invocation_index, state=state)
            invocation_index += 1
            subsequent += int(component_index > 0)
            records.append(action.record)
            if action.terminal is not None or action.record.action_accepted is not True:
                _fail("A3.action", f"reference Action failed:{action.terminal}")
            invalid = next((item for item in rows if not item.acceptance.accepted), None)
            if invalid is None:
                continue
            rejected = step_runtime.step(branch, invalid.action_id)
            if not isinstance(rejected, step_runtime.PublicTypedRejectionObservation):
                _fail("A3.correction_setup", "registered invalid Action did not type-reject")
            correction_prompt = step_runtime.render_next_prompt(branch)
            correction_rows = frozen_runtime._candidate_dispositions(branch, correction_prompt)
            correction = frozen_runtime._reference_correction(
                branch,
                correction_prompt,
                correction_rows,
                component_index,
                invalid.action_id,
            )
            if correction.action_id is None:
                _fail("A3.correction", "reference Correction lacks Action ID")
            transport.queue(
                _action_payload(
                    correction_prompt.state.state_token,
                    correction.action_id,
                    parents.profile,
                )
            )
            corrected = runner.invoke_correction(
                job=job, invocation_index=invocation_index, state=branch
            )
            invocation_index += 1
            correction_count += 1
            records.append(corrected.record)
            if corrected.terminal is not None or corrected.record.action_accepted is not True:
                _fail("A3.correction", f"reference Correction failed:{corrected.terminal}")
        preview = step_runtime.finalize(copy.deepcopy(state))
        transport.queue(_final_payload(preview, context.source))
        final = runner.invoke_final(
            job=job,
            invocation_index=invocation_index,
            state=state,
            context=context,
        )
        records.append(final.record)
        if final.terminal is not None or final.final_result is None:
            _fail("A3.final", f"reference Final failed:{final.terminal}")
        result = final.final_result
        if not (
            result.task_validity.base_valid
            and result.mechanism_qualification.mechanism_semantically_qualified
            and result.qualified_validity.qualified_valid
        ):
            _fail("A3.validity", "reference main path is not Qualified")
        matches = sum(
            record.model_dump(mode="json")
            == saved_records[(record.job_id, record.invocation_index)].model_dump(mode="json")
            for record in records
        )
        if matches != len(records) or len(transport.dispatches) != len(records):
            _fail("A3.saved_match", f"Runner replay differs for {job.job_id}")
        all_records.extend(records)
        correction_distribution[correction_count] += 1
        replay_rows.append(
            cast(
                models.IndependentReplayJobRow,
                _make(
                    models.IndependentReplayJobRow,
                    {
                        "job_id": job.job_id,
                        "invocation_ids_sha256": models.canonical_sha256(
                            tuple(item.invocation_id for item in records)
                        ),
                        "subsequent_action_count": subsequent,
                        "correction_side_branch_count": correction_count,
                        "transport_dispatch_count": len(transport.dispatches),
                        "saved_invocation_match_count": matches,
                    },
                    "row_id",
                    "finance_v26_210_independent_replay_job_row:",
                ),
            )
        )
    ordered = tuple(sorted(all_records, key=lambda item: (item.job_id, item.invocation_index)))
    if len(ordered) != 792 or correction_distribution != Counter(
        {0: 144, 1: 12, 2: 12, 3: 12, 4: 12}
    ):
        _fail(
            "A3.denominator", f"replay denominator differs:{len(ordered)}/{correction_distribution}"
        )
    dynamic_matches = _dynamic_nonreference(
        saved=saved,
        parents=parents,
        prepared=prepared,
        config=config,
        reference_records=ordered,
    )
    if not dynamic_matches:
        _fail("A3.dynamic", "independent dynamic nonreference target differs")
    audit = cast(
        models.IndependentExecutableReplayAudit,
        _make(
            models.IndependentExecutableReplayAudit,
            {
                "freeze_id": freeze_id,
                "execution_contract_id": saved.execution.contract_id,
                "rows": tuple(replay_rows),
            },
            "audit_id",
            "finance_v26_210_independent_executable_replay_audit:",
        ),
    )
    return audit, ordered


def _dynamic_nonreference(
    *,
    saved: SavedV209,
    parents: IndependentParents,
    prepared: v188.PreparedExecution,
    config: AgentModelConfig,
    reference_records: tuple[v209_models.ExecutableInvocationRecord, ...],
) -> bool:
    reference_final = {row.job_id: row for row in reference_records if row.phase == "final"}
    for job in sorted(saved.manifest.jobs, key=lambda item: item.job_id):
        context = _context(job, parents=parents, prepared=prepared)
        initial = frozen_runtime._initialize(context)
        if len(initial.ordered_components) < 2:
            continue
        prompt = step_runtime.render_next_prompt(initial)
        rows = frozen_runtime._candidate_dispositions(initial, prompt)
        reference = frozen_runtime._reference_selection(initial, prompt, rows, 0)
        if reference.action_id is None:
            continue
        alternatives = tuple(
            item
            for item in rows
            if item.action_id != reference.action_id and item.acceptance.accepted
        )
        for alternative in alternatives:
            reference_state = copy.deepcopy(initial)
            if not getattr(
                step_runtime.step(reference_state, reference.action_id),
                "action_accepted",
                False,
            ):
                continue
            reference_next = step_runtime.render_next_prompt(reference_state)
            state = copy.deepcopy(initial)
            transport = AuditTransport()
            runner = _runner(
                transport,
                config=config,
                parents=parents,
                prepared=prepared,
                implementation_id=saved.implementation.implementation_id,
            )
            transport.queue(
                _action_payload(prompt.state.state_token, alternative.action_id, parents.profile)
            )
            first = runner.invoke_action(job=job, invocation_index=0, state=state)
            if first.terminal is not None or first.record.action_accepted is not True:
                continue
            nonreference_next = step_runtime.render_next_prompt(state)
            if nonreference_next.state.state_token == reference_next.state.state_token:
                continue
            invocation_index = 1
            second_state_id: str | None = None
            failed = False
            while state.current_index < len(state.ordered_components):
                current = step_runtime.render_next_prompt(state)
                dispositions = frozen_runtime._candidate_dispositions(state, current)
                selected = frozen_runtime._reference_selection(
                    state, current, dispositions, state.current_index
                )
                if selected.action_id is None:
                    failed = True
                    break
                transport.queue(
                    _action_payload(current.state.state_token, selected.action_id, parents.profile)
                )
                action = runner.invoke_action(
                    job=job, invocation_index=invocation_index, state=state
                )
                if invocation_index == 1:
                    second_state_id = action.record.current_state_id
                invocation_index += 1
                if action.terminal is not None or action.record.action_accepted is not True:
                    failed = True
                    break
            if failed:
                continue
            preview = step_runtime.finalize(copy.deepcopy(state))
            transport.queue(_final_payload(preview, context.source))
            final = runner.invoke_final(
                job=job, invocation_index=invocation_index, state=state, context=context
            )
            if final.terminal is not None or final.final_result is None:
                continue
            final_message = json.loads(final.record.canonical_messages_json)[0]["content"]
            target = saved.dynamic
            observed = (
                job.job_id,
                initial.ordered_components[0].component_key,
                prompt.state.state_token,
                reference.action_id,
                alternative.action_id,
                len(prompt.candidates),
                reference_next.state.state_token,
                nonreference_next.state.state_token,
                second_state_id,
                final_message,
                final.record.canonical_request_body_sha256,
                reference_final[job.job_id].canonical_request_body_sha256,
                invocation_index,
                1,
                len(transport.dispatches),
            )
            expected = (
                target.job_id,
                target.component_key,
                target.initial_state_id,
                target.reference_action_id,
                target.nonreference_action_id,
                target.candidate_count,
                target.reference_next_state_id,
                target.nonreference_next_state_id,
                target.second_invocation_current_state_id,
                target.dynamic_final_message_json,
                target.dynamic_final_request_sha256,
                target.reference_final_request_sha256,
                target.diagnostic_action_dispatch_count,
                target.diagnostic_final_dispatch_count,
                target.diagnostic_transport_dispatch_count,
            )
            return observed == expected == (*expected[:-3], 4, 1, 5)
    return False


def _continuity(
    *,
    freeze_id: str,
    geometry_id: str,
    saved: SavedV209,
    parents: IndependentParents,
    records: tuple[v209_models.ExecutableInvocationRecord, ...],
) -> models.IndependentRequestContinuityAudit:
    v206_jobs = {item.job_id: item for item in parents.source_manifest.jobs}
    source_calls = {
        (row.fresh_job_id, row.invocation_index): row for row in parents.source_callsites.rows
    }
    evidence = {row.row_id: row for row in parents.v193_evidence.rows}
    output: list[models.RequestContinuityRow] = []
    for record in records:
        job = {item.job_id: item for item in saved.manifest.jobs}[record.job_id]
        source = source_calls[(job.source_v206_job_id, record.invocation_index)]
        source_evidence = evidence[source.source_v193_evidence_row_id]
        if record.phase != source.phase:
            _fail("A2.phase", "observed/source callsite phase differs")
        if record.phase == "final":
            expected_messages = ({"role": "user", "content": source_evidence.rendered_prompt},)
            expected_request = json.loads(source_evidence.request_body_canonical_json)
            message_sha = models.canonical_sha256(expected_messages)
            request_sha = models.canonical_sha256(expected_request)
            final_message_equal = record.canonical_messages_json == models.canonical_bytes(
                expected_messages
            ).decode("utf-8")
            final_request_equal = record.canonical_request_body_json == models.canonical_bytes(
                expected_request
            ).decode("utf-8")
        else:
            message_sha = source.canonical_messages_sha256
            request_sha = source.canonical_request_body_sha256
            final_message_equal = final_request_equal = False
        if (
            record.canonical_messages_sha256 != message_sha
            or record.canonical_request_body_sha256 != request_sha
            or source.fresh_job_id not in v206_jobs
        ):
            _fail("A2.request", "independent request continuity differs")
        output.append(
            cast(
                models.RequestContinuityRow,
                _make(
                    models.RequestContinuityRow,
                    {
                        "job_id": record.job_id,
                        "source_v206_job_id": job.source_v206_job_id,
                        "invocation_index": record.invocation_index,
                        "phase": record.phase,
                        "source_v193_evidence_row_id": source.source_v193_evidence_row_id,
                        "source_v206_callsite_row_id": source.row_id,
                        "observed_invocation_id": record.invocation_id,
                        "observed_messages_sha256": record.canonical_messages_sha256,
                        "observed_request_sha256": record.canonical_request_body_sha256,
                        "source_messages_sha256": message_sha,
                        "source_request_sha256": request_sha,
                        "final_actual_message_bytes_equal": final_message_equal,
                        "final_actual_request_bytes_equal": final_request_equal,
                    },
                    "row_id",
                    "finance_v26_210_independent_request_continuity_row:",
                ),
            )
        )
    phase = Counter(item.phase for item in output)
    final_bytes = sum(item.final_actual_message_bytes_equal for item in output)
    final_requests = sum(item.final_actual_request_bytes_equal for item in output)
    observed = (
        len(output),
        phase["first_action"],
        phase["subsequent_action"],
        phase["correction"],
        phase["final"],
        final_bytes,
        final_requests,
        max(item.canonical_messages_byte_count for item in records),
        max(item.canonical_request_body_byte_count for item in records),
    )
    if observed != (792, 192, 288, 120, 192, 192, 192, 34_404, 34_565):
        _fail("A2.summary", f"independent continuity summary differs:{observed}")
    rebuilt = cast(
        models.IndependentRequestContinuityAudit,
        _make(
            models.IndependentRequestContinuityAudit,
            {
                "freeze_id": freeze_id,
                "callsite_geometry_audit_id": geometry_id,
                "rows": tuple(
                    sorted(output, key=lambda item: (item.job_id, item.invocation_index))
                ),
            },
            "audit_id",
            "finance_v26_210_independent_request_continuity_audit:",
        ),
    )
    if (
        rebuilt.total_message_match_count != saved.continuity.total_registered_message_match_count
        or rebuilt.total_request_match_count
        != saved.continuity.total_registered_request_match_count
        or rebuilt.maximum_message_byte_count != saved.continuity.maximum_message_byte_count
        or rebuilt.maximum_request_body_byte_count
        != saved.continuity.maximum_request_body_byte_count
    ):
        _fail("A2.saved_target", "independent continuity summary differs from saved target")
    return rebuilt


def _find_correction_state(
    saved: SavedV209,
    *,
    parents: IndependentParents,
    prepared: v188.PreparedExecution,
) -> tuple[v209_models.ExecutableDevelopmentJob, Any]:
    for job in sorted(saved.manifest.jobs, key=lambda item: item.job_id):
        state = frozen_runtime._initialize(_context(job, parents=parents, prepared=prepared))
        while state.current_index < len(state.ordered_components):
            prompt = step_runtime.render_next_prompt(state)
            rows = frozen_runtime._candidate_dispositions(state, prompt)
            invalid = next((item for item in rows if not item.acceptance.accepted), None)
            if invalid is not None:
                step_runtime.step(state, invalid.action_id)
                return job, state
            reference = frozen_runtime._reference_selection(
                state, prompt, rows, state.current_index
            )
            if reference.action_id is None:
                break
            step_runtime.step(state, reference.action_id)
    _fail("A4.correction_state", "no registered Correction State found")


def _failures(
    *,
    freeze_id: str,
    saved: SavedV209,
    parents: IndependentParents,
    prepared: v188.PreparedExecution,
    config: AgentModelConfig,
) -> models.IndependentFailureBoundaryAudit:
    controls: list[models.IndependentFailureControl] = []

    def add(name: str, expected: str, outcome: v209.InvocationOutcome) -> None:
        if outcome.terminal != expected:
            _fail("A4.terminal", f"{name} terminal differs:{outcome.terminal}")
        controls.append(
            cast(
                models.IndependentFailureControl,
                _make(
                    models.IndependentFailureControl,
                    {
                        "control_name": name,
                        "expected_terminal": expected,
                        "observed_terminal": cast(str, outcome.terminal),
                        "invocation_id": outcome.record.invocation_id,
                    },
                    "control_id",
                    "finance_v26_210_independent_failure_control:",
                ),
            )
        )

    job = sorted(saved.manifest.jobs, key=lambda item: item.job_id)[0]
    context = _context(job, parents=parents, prepared=prepared)

    state = frozen_runtime._initialize(context)
    prompt = step_runtime.render_next_prompt(state)
    rows = frozen_runtime._candidate_dispositions(state, prompt)
    transport = AuditTransport()
    transport.queue(
        {
            "state_id": prompt.state.state_token,
            "action_id": rows[0].action_id,
            "decision_kind": parents.profile.decision_kind_value,
        }
    )
    add(
        "invalid_first_action_abi",
        "first_response_abi_invalid",
        _runner(
            transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=saved.implementation.implementation_id,
        ).invoke_action(job=job, invocation_index=0, state=state),
    )

    state = frozen_runtime._initialize(context)
    prompt = step_runtime.render_next_prompt(state)
    transport = AuditTransport()
    transport.queue(_action_payload(prompt.state.state_token, "f" * 24, parents.profile))
    add(
        "unknown_current_action",
        "first_action_reference_invalid",
        _runner(
            transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=saved.implementation.implementation_id,
        ).invoke_action(job=job, invocation_index=0, state=state),
    )

    correction_job, correction_state = _find_correction_state(
        saved, parents=parents, prepared=prepared
    )
    correction_prompt = step_runtime.render_next_prompt(correction_state)
    correction_rows = frozen_runtime._candidate_dispositions(correction_state, correction_prompt)
    transport = AuditTransport()
    transport.queue(
        {
            "state_id": correction_prompt.state.state_token,
            "action_id": correction_rows[0].action_id,
            "decision_kind": parents.profile.decision_kind_value,
        }
    )
    add(
        "invalid_correction_abi",
        "correction_response_abi_invalid",
        _runner(
            transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=saved.implementation.implementation_id,
        ).invoke_correction(job=correction_job, invocation_index=1, state=correction_state),
    )

    state = _reference_complete_state(context)
    transport = AuditTransport()
    transport.queue({})
    add(
        "invalid_final_abi",
        "final_response_abi_invalid",
        _runner(
            transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=saved.implementation.implementation_id,
        ).invoke_final(
            job=job,
            invocation_index=len(state.ordered_components),
            state=state,
            context=context,
        ),
    )

    state = frozen_runtime._initialize(context)
    transport = AuditTransport()
    transport.queue(
        v209.TypedTransportFailure("instrument_failure", "independent typed outer control")
    )
    add(
        "typed_outer_failure",
        "instrument_failure",
        _runner(
            transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=saved.implementation.implementation_id,
        ).invoke_action(job=job, invocation_index=0, state=state),
    )
    return cast(
        models.IndependentFailureBoundaryAudit,
        _make(
            models.IndependentFailureBoundaryAudit,
            {"freeze_id": freeze_id, "controls": tuple(controls)},
            "audit_id",
            "finance_v26_210_independent_failure_boundary_audit:",
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
            "finance_v26_210_source_identity:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.IndependentAuditReport:
    if output_dir.exists():
        raise FileExistsError(f"v26.210 output already exists:{output_dir}")
    authorization, review_bytes, directive_bytes = _authorization(external_review_path)
    saved = _saved_v209(repository_root)
    freeze = _freeze(authorization.authorization_id, saved)
    detached = _detached_rebuild(repository_root, freeze.freeze_id, saved)
    parents = _parents(repository_root)
    geometry = _geometry(freeze.freeze_id, parents)
    config = AgentModelConfig.model_validate(_load(repository_root / MODEL_PROFILE)["model"])
    package_root = repository_root / "trusted_data_synthesis"
    with tempfile.TemporaryDirectory(prefix="v26-210-provider-forbidden-") as temporary:
        prepared = v188.prepare_execution(
            package_root=package_root,
            output_dir=Path(temporary) / "provider_forbidden",
        )
        replay, records = _replay(
            freeze_id=freeze.freeze_id,
            saved=saved,
            parents=parents,
            prepared=prepared,
            config=config,
        )
        failures = _failures(
            freeze_id=freeze.freeze_id,
            saved=saved,
            parents=parents,
            prepared=prepared,
            config=config,
        )
    continuity = _continuity(
        freeze_id=freeze.freeze_id,
        geometry_id=geometry.audit_id,
        saved=saved,
        parents=parents,
        records=records,
    )
    gate = cast(
        models.IndependentAuditGateEvaluation,
        _make(
            models.IndependentAuditGateEvaluation,
            {
                "freeze_id": freeze.freeze_id,
                "detached_rebuild_audit_id": detached.audit_id,
                "callsite_geometry_audit_id": geometry.audit_id,
                "request_continuity_audit_id": continuity.audit_id,
                "executable_replay_audit_id": replay.audit_id,
                "failure_boundary_audit_id": failures.audit_id,
            },
            "gate_id",
            "finance_v26_210_independent_audit_gate_evaluation:",
        ),
    )
    decision = cast(
        models.IndependentAuditDecision,
        _make(
            models.IndependentAuditDecision,
            {"gate_id": gate.gate_id},
            "decision_id",
            "finance_v26_210_independent_audit_decision:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        _make(
            models.ProspectiveTransition,
            {"decision_id": decision.decision_id, "gate_id": gate.gate_id},
            "transition_id",
            "finance_v26_210_transition:",
        ),
    )
    source = _source(source_identity)
    report = cast(
        models.IndependentAuditReport,
        _make(
            models.IndependentAuditReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "freeze_id": freeze.freeze_id,
                "detached_rebuild_audit_id": detached.audit_id,
                "callsite_geometry_audit_id": geometry.audit_id,
                "request_continuity_audit_id": continuity.audit_id,
                "executable_replay_audit_id": replay.audit_id,
                "failure_boundary_audit_id": failures.audit_id,
                "gate_id": gate.gate_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
                "source_identity_id": source.source_identity_id,
            },
            "report_id",
            "finance_v26_210_independent_audit_report:",
        ),
    )
    payloads = {
        "external_review.txt": review_bytes,
        "operator_authorization.txt": directive_bytes,
        "external_authorization.json": _bytes(authorization),
        "v209_preflight_freeze.json": _bytes(freeze),
        "detached_rebuild_audit.json": _bytes(detached),
        "independent_callsite_geometry_audit.json": _bytes(geometry),
        "independent_request_continuity_audit.json": _bytes(continuity),
        "independent_executable_replay_audit.json": _bytes(replay),
        "independent_failure_boundary_audit.json": _bytes(failures),
        "independent_audit_gate_evaluation.json": _bytes(gate),
        "independent_audit_decision.json": _bytes(decision),
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
