from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.builder import TaskPackageBuilder
from trusted_synthesis.core.task.schema import (
    PlanningTrack,
    RetrievalTrack,
    VerifierRequirement,
)
from trusted_synthesis.core.vtdo import make_public_state_generation_request
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import ContractCase
from trusted_synthesis.experiments.finance_archive import FinanceArchiveBindingProvider
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    DEFAULT_FINANCE_DISCOVERY_STRATEGIES,
    FinanceTaskStateArtifact,
    build_finance_task_state_artifact,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import VTDOExperimentConfig
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.state_conditioned import (
    assess_state_condition_controllability,
)

FINANCE_AGENT_POPULATION_VERSION = "finance_agent_population.v15"
FINANCE_AGENT_INTERFACE_VERSION = "finance_agent_interface.v1"
EXCLUSION_IDENTITY_INDEX_VERSION = "finance_population_exclusion_identity_index.v1"
AGENT_DISCOVERY_STRATEGIES = DEFAULT_FINANCE_DISCOVERY_STRATEGIES


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceAgentPopulationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    experiment_config_hash: str = Field(min_length=1)
    archive_config_sha256: str = Field(min_length=64, max_length=64)
    kg_build_id: str = Field(min_length=1)
    candidate_pool_id: str = Field(min_length=1)
    sampling_partition: str = Field(min_length=1)
    requested_task_count: int = Field(ge=1)
    attempted_task_count: int = Field(ge=0)
    accepted_task_count: int = Field(ge=0)
    accepted_state_count: int = Field(ge=0)
    requestable_state_count: int = Field(ge=0)
    state_count_by_task: dict[str, int] = Field(default_factory=dict)
    task_type_counts: dict[str, int] = Field(default_factory=dict)
    failure_counts: dict[str, int] = Field(default_factory=dict)
    source_to_agent_task_ids: dict[str, str] = Field(default_factory=dict)
    excluded_population_artifact_sha256s: tuple[str, ...] = Field(default_factory=tuple)
    excluded_population_artifact_set_id: str | None = Field(default=None, min_length=1)
    exclusion_identity_index_version: str = EXCLUSION_IDENTITY_INDEX_VERSION
    excluded_population_record_count: int = Field(ge=0)
    excluded_public_evidence_version_count: int = Field(ge=0)
    excluded_public_evidence_version_set_id: str | None = Field(default=None, min_length=1)
    artifact_sha256: str = Field(min_length=64, max_length=64)
    status: str = Field(pattern="^(passed|partial|blocked)$")
    schema_version: str = FINANCE_AGENT_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceAgentPopulationReport:
        if self.accepted_task_count != len(self.state_count_by_task):
            raise ValueError("Agent population task accounting is inconsistent")
        if self.accepted_task_count != len(self.source_to_agent_task_ids):
            raise ValueError("Agent population lineage accounting is inconsistent")
        if self.accepted_state_count != sum(self.state_count_by_task.values()):
            raise ValueError("Agent population state accounting is inconsistent")
        expected = (
            "passed"
            if self.accepted_task_count == self.requested_task_count
            else ("partial" if self.accepted_task_count else "blocked")
        )
        if self.status != expected:
            raise ValueError("Agent population status is inconsistent")
        if self.status == "passed" and self.requestable_state_count != self.accepted_state_count:
            raise ValueError("a passed Agent population contains an uncontrollable state")
        if self.exclusion_identity_index_version != EXCLUSION_IDENTITY_INDEX_VERSION:
            raise ValueError("Agent population exclusion-index version is invalid")
        has_exclusions = bool(self.excluded_population_artifact_sha256s)
        if has_exclusions != (self.excluded_population_record_count > 0):
            raise ValueError("Agent population exclusion record accounting is inconsistent")
        if has_exclusions != (self.excluded_public_evidence_version_count > 0):
            raise ValueError("Agent population exclusion lineage is inconsistent")
        if has_exclusions != bool(self.excluded_public_evidence_version_set_id):
            raise ValueError("Agent population exclusion Evidence identity is inconsistent")
        expected_set_id = (
            canonical_hash(
                tuple(sorted(self.excluded_population_artifact_sha256s)),
                prefix="finance_agent_population_exclusion_set:",
            )
            if has_exclusions
            else None
        )
        if self.excluded_population_artifact_set_id != expected_set_id:
            raise ValueError("Agent population exclusion-set identity is inconsistent")
        if len(set(self.excluded_population_artifact_sha256s)) != len(
            self.excluded_population_artifact_sha256s
        ):
            raise ValueError("Agent population exclusion artifacts are duplicated")
        if self.report_id != finance_agent_population_report_id(self):
            raise ValueError("Agent population report identity is invalid")
        return self


def compile_finance_agent_case(case: ContractCase) -> ContractCase:
    """Recompile one real Finance task without exposing its Oracle retrieval/program plan."""

    source_task = case.task
    evidence_by_id = {item.evidence_id: item for item in case.bundle.evidence}
    gold_evidence = tuple(
        evidence_by_id[evidence_id] for evidence_id in source_task.oracle.gold_evidence_ids
    )
    metadata = {
        **source_task.public.metadata,
        "agent_interface": {
            "interface_version": FINANCE_AGENT_INTERFACE_VERSION,
            "retrieval_track": RetrievalTrack.SEMI_OPEN.value,
            "planning_track": PlanningTrack.PLAN_HIDDEN.value,
            "oracle_semantics_preserved": True,
        },
    }
    requirement = VerifierRequirement(
        str(
            source_task.public.metadata.get(
                "source_grounding_requirement",
                VerifierRequirement.NOT_APPLICABLE.value,
            )
        )
    )
    task = TaskPackageBuilder(case.registry).build(
        task_domain=source_task.public.domain,
        task_type=source_task.public.task_type,
        level=source_task.public.level,
        instruction=source_task.public.instruction,
        evidence=gold_evidence,
        bundle=case.bundle,
        proof_graph=case.proof_graph,
        program=source_task.oracle.task_program,
        answer_schema=dict(source_task.public.answer_schema),
        retrieval_scope=_semi_open_retrieval_scope(case),
        retrieval_track=RetrievalTrack.SEMI_OPEN,
        planning_track=PlanningTrack.PLAN_HIDDEN,
        oracle_selection_contract=dict(source_task.oracle.selection_contract),
        source_grounding_requirement=requirement,
        allow_structured_claims=bool(source_task.public.answer_schema.get("allow_claims", False)),
        metadata=metadata,
        quality_rubric=dict(source_task.oracle.quality_rubric),
        identity_context={
            "source_task_id": source_task.task_id,
            "agent_interface_version": FINANCE_AGENT_INTERFACE_VERSION,
        },
    )
    if task.oracle.task_program != source_task.oracle.task_program:
        raise ValueError("Agent recompilation changed the Oracle program")
    if task.oracle.gold_evidence_ids != source_task.oracle.gold_evidence_ids:
        raise ValueError("Agent recompilation changed the gold evidence")
    if task.public.program_skeleton is not None:
        raise ValueError("Agent recompilation exposed the Oracle program skeleton")
    return ContractCase(
        domain=case.domain,
        bundle=case.bundle,
        corpus=case.corpus,
        proof_graph=case.proof_graph,
        task=task,
        registry=case.registry,
        semantic_policy=case.semantic_policy,
        quality_clause_provider=case.quality_clause_provider,
        plugin_set=case.plugin_set,
        counterfactual_registry=case.counterfactual_registry,
        source_grounding_verifier=case.source_grounding_verifier,
    )


def build_finance_agent_population(
    *,
    experiment_config_path: Path,
    output_dir: Path,
    task_count: int | None = None,
    seed: int | None = None,
    excluded_population_artifacts_paths: tuple[Path, ...] = (),
) -> tuple[FinanceAgentPopulationReport, tuple[FinanceTaskStateArtifact, ...]]:
    experiment = VTDOExperimentConfig.from_json(experiment_config_path)
    source_config = experiment.multi_state
    requested = task_count or source_config.task_count
    if requested < 1:
        raise ValueError("Agent population task count must be positive")
    effective_seed = source_config.random_seed if seed is None else seed
    state_config = source_config.model_copy(
        update={
            "task_count": requested,
            "maximum_states_per_task": len(AGENT_DISCOVERY_STRATEGIES),
            "random_seed": effective_seed,
        }
    )
    archive_config = FinanceArchiveConfig.from_json(state_config.finance_archive_config_path)
    adapter = FinanceArchiveAdapter(archive_config)
    provider = FinanceArchiveBindingProvider(
        adapter,
        candidate_pool_id=state_config.candidate_pool_id,
        sampling_partition_id=state_config.sampling_partition,
        pool_split_seed=state_config.pool_split_seed,
        evidence_scan_limit=state_config.evidence_scan_limit,
        evidence_sample_size=state_config.evidence_sample_size,
        stratum_reservoir_size=state_config.stratum_reservoir_size,
        candidates_per_pattern=state_config.candidates_per_pattern,
    )
    candidate_count = math.ceil(requested * state_config.candidate_task_oversampling_factor)
    resolved_exclusion_paths = tuple(path.resolve() for path in excluded_population_artifacts_paths)
    if len(set(resolved_exclusion_paths)) != len(resolved_exclusion_paths):
        raise ValueError("excluded Agent population paths are duplicated")
    excluded_artifact_sha256s = tuple(sorted(_sha256(path) for path in resolved_exclusion_paths))
    if len(set(excluded_artifact_sha256s)) != len(excluded_artifact_sha256s):
        raise ValueError("excluded Agent population contents are duplicated")
    exclusion_sources = tuple(
        _read_population_identity_source(path) for path in resolved_exclusion_paths
    )
    excluded_evidence_versions = frozenset(
        evidence_version_id
        for source in exclusion_sources
        for evidence_version_id in source["evidence_version_ids"]
    )
    if resolved_exclusion_paths and not excluded_evidence_versions:
        raise ValueError("excluded Agent populations have no public Evidence")
    excluded_evidence_version_set_id = (
        canonical_hash(
            tuple(sorted(excluded_evidence_versions)),
            prefix="finance_population_excluded_evidence_version_set:",
        )
        if excluded_evidence_versions
        else None
    )
    excluded_artifact_set_id = (
        canonical_hash(
            excluded_artifact_sha256s,
            prefix="finance_agent_population_exclusion_set:",
        )
        if excluded_artifact_sha256s
        else None
    )
    cases = provider.contract_cases(
        candidate_count,
        seed=effective_seed,
        require_corpus_disjoint=state_config.require_corpus_disjoint,
        excluded_evidence_version_ids=excluded_evidence_versions,
    )
    artifacts: list[FinanceTaskStateArtifact] = []
    failures: Counter[str] = Counter()
    source_to_agent: dict[str, str] = {}
    requestable_state_count = 0
    attempted = 0
    for source_case in cases:
        if len(artifacts) >= requested:
            break
        attempted += 1
        try:
            agent_case = compile_finance_agent_case(source_case)
            artifact = build_finance_task_state_artifact(
                agent_case,
                state_config,
                strategies=AGENT_DISCOVERY_STRATEGIES,
                discovery_method="verified_finance_agent_interface_fixture",
                revision_reason="semi_open_plan_hidden_agent_state_catalog",
            )
            requestable = _requestable_state_count(artifact, seed=effective_seed)
            if requestable != len(artifact.accepted_states):
                raise ValueError("Agent state catalog contains a host-blocked condition")
        except Exception as exc:
            failures[f"{type(exc).__name__}:{str(exc).split(':', 1)[0]}"] += 1
            continue
        artifacts.append(artifact)
        requestable_state_count += requestable
        source_to_agent[source_case.task.task_id] = artifact.omega.task.task_id

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "finance_agent_task_states.jsonl"
    _write_jsonl_atomic(
        artifact_path,
        (item.model_dump(mode="json") for item in artifacts),
    )
    report_values: dict[str, Any] = {
        "experiment_config_hash": experiment.config_hash,
        "archive_config_sha256": _sha256(state_config.finance_archive_config_path),
        "kg_build_id": provider.kg_build_id,
        "candidate_pool_id": state_config.candidate_pool_id,
        "sampling_partition": state_config.sampling_partition,
        "requested_task_count": requested,
        "attempted_task_count": attempted,
        "accepted_task_count": len(artifacts),
        "accepted_state_count": sum(len(item.accepted_states) for item in artifacts),
        "requestable_state_count": requestable_state_count,
        "state_count_by_task": {
            item.omega.task.task_id: len(item.accepted_states) for item in artifacts
        },
        "task_type_counts": dict(
            sorted(Counter(item.omega.task.public.task_type for item in artifacts).items())
        ),
        "failure_counts": dict(sorted(failures.items())),
        "source_to_agent_task_ids": dict(sorted(source_to_agent.items())),
        "excluded_population_artifact_sha256s": excluded_artifact_sha256s,
        "excluded_population_artifact_set_id": excluded_artifact_set_id,
        "exclusion_identity_index_version": EXCLUSION_IDENTITY_INDEX_VERSION,
        "excluded_population_record_count": sum(
            int(source["record_count"]) for source in exclusion_sources
        ),
        "excluded_public_evidence_version_count": len(excluded_evidence_versions),
        "excluded_public_evidence_version_set_id": excluded_evidence_version_set_id,
        "artifact_sha256": _sha256(artifact_path),
        "status": (
            "passed" if len(artifacts) == requested else "partial" if artifacts else "blocked"
        ),
        "schema_version": FINANCE_AGENT_POPULATION_VERSION,
    }
    provisional = FinanceAgentPopulationReport.model_construct(report_id="pending", **report_values)
    report = FinanceAgentPopulationReport(
        report_id=finance_agent_population_report_id(provisional),
        **report_values,
    )
    _write_json_atomic(
        output_dir / "finance_agent_population_report.json",
        report.model_dump(mode="json"),
    )
    return report, tuple(artifacts)


def _semi_open_retrieval_scope(case: ContractCase) -> dict[str, Any]:
    source = case.task
    evidence_by_id = {item.evidence_id: item for item in case.bundle.evidence}
    evidence = tuple(evidence_by_id[item] for item in source.oracle.gold_evidence_ids)
    aliases = _unique(
        value
        for item in evidence
        for value in (
            item.subject.name,
            item.predicate,
            str(item.definition.attributes.get("metric_name") or ""),
            item.source.name,
        )
        if value
    )
    partial_constraints = {
        "domain": "finance",
        "subject_types": list(_unique(item.subject.subject_type for item in evidence)),
        "time_bases": list(_unique(item.temporal_context.basis for item in evidence)),
        "frequencies": list(_unique(item.temporal_context.frequency for item in evidence)),
        "source_authorities": list(_unique(item.source.authority.value for item in evidence)),
        "epistemic_statuses": list(_unique(item.epistemic_status.value for item in evidence)),
        "required_fact_count": len(evidence),
    }
    return {
        "aliases": list(aliases),
        "partial_constraints": partial_constraints,
        "corpus_boundary": {
            "boundary_type": "immutable_task_public_corpus",
            "corpus_version": case.corpus.corpus_hash,
            "domain": "finance",
            "evidence_count": len(case.corpus.evidence),
        },
    }


def _requestable_state_count(
    artifact: FinanceTaskStateArtifact,
    *,
    seed: int,
) -> int:
    count = 0
    for condition in artifact.state_catalog.public_state_conditions.values():
        request = make_public_state_generation_request(
            artifact.omega,
            condition,
            candidate_count=1,
            seed=seed,
        )
        audit = assess_state_condition_controllability(
            request,
            interaction_protocol="host_instrumented",
        )
        count += int(audit.condition_requestable)
    return count


def finance_agent_population_report_id(
    value: FinanceAgentPopulationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_agent_population_report:",
    )


def _unique(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value).strip()))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_population_identity_source(path: Path) -> dict[str, Any]:
    """Index immutable Evidence identities without loading a legacy object schema."""

    record_count = 0
    evidence_version_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            record_count += 1
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"excluded population contains invalid JSON at line {line_number}"
                ) from exc
            if not isinstance(value, dict):
                raise ValueError("excluded population row is not an object")
            joint = value.get("joint_compilation")
            omega = joint.get("omega") if isinstance(joint, dict) else None
            corpus = omega.get("public_corpus") if isinstance(omega, dict) else None
            evidence = corpus.get("evidence") if isinstance(corpus, dict) else None
            if not isinstance(evidence, list) or not evidence:
                raise ValueError(
                    "excluded population row lacks immutable public Evidence identities"
                )
            for item in evidence:
                version_id = item.get("evidence_version_id") if isinstance(item, dict) else None
                if not isinstance(version_id, str) or not version_id.strip():
                    raise ValueError("excluded population Evidence lacks an evidence_version_id")
                evidence_version_ids.add(version_id)
    if record_count == 0 or not evidence_version_ids:
        raise ValueError("excluded population identity source is empty")
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "record_count": record_count,
        "evidence_version_ids": tuple(sorted(evidence_version_ids)),
    }


def _write_jsonl_atomic(path: Path, values) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as sink:
        for value in values:
            sink.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile real Finance tasks for model-controllable VTDO state discovery"
    )
    parser.add_argument("--experiment-config-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--task-count", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--exclude-population-artifacts-paths",
        nargs="*",
        default=(),
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    report, _ = build_finance_agent_population(
        experiment_config_path=Path(args.experiment_config_path).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        task_count=args.task_count,
        seed=args.seed,
        excluded_population_artifacts_paths=tuple(
            Path(value).resolve() for value in args.exclude_population_artifacts_paths
        ),
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
