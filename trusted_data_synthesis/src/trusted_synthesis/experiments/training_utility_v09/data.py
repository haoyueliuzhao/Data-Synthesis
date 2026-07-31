from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any

from trusted_synthesis.core.evaluation.critic.schema import (
    AcceptabilityLabel,
    QualityCriticExample,
)
from trusted_synthesis.core.evaluation.utility import UtilityCohort
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.refinement import (
    ClauseFeedback,
    PolicyUpdateResult,
    RefinedSynthesisArtifact,
    RefinedSynthesisMaterializer,
    SynthesisBindingProviderProtocol,
    SynthesisCell,
    SynthesisMaterializationReport,
    build_synthesis_cell,
)
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack, TaskPublicSpec
from trusted_synthesis.domains.finance import FinanceArchiveAdapter, FinanceArchiveConfig
from trusted_synthesis.domains.finance.schema import ARCHIVE_BACKED_FINANCE_ADAPTER_IDS
from trusted_synthesis.experiments.agent_validation.schema import AgentValidationReport
from trusted_synthesis.experiments.agent_validation.tracks import materialize_track_variant
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import ContractCase
from trusted_synthesis.experiments.training_utility_mvp.data import (
    _evaluation_isolation,
    _reference_and_evaluation_records,
    _reference_response,
    _student_operation_registry,
    _task_structure_metadata,
    make_sft_record,
    record_from_quality_example,
)
from trusted_synthesis.experiments.training_utility_mvp.schema import (
    TRAINING_UTILITY_AGENT_PROMPT_VERSION,
    SFTMessage,
    SFTRecord,
    TrainingUtilityMVPConfig,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.host_execution import (
    execute_action_plan,
    make_host_execution_feedback,
)
from trusted_synthesis.runtime.agent.schema import (
    AgentActionPlanContract,
    AgentAnswerDecisionContract,
)

from .finance_archive_materialization import FinanceArchiveBindingProvider
from .materialization import (
    V09FixtureBindingProvider,
    fresh_fixture_start_index,
)
from .schema import (
    TRAINING_UTILITY_V09_VERSION,
    V09Cohort,
    V09CohortDatasetManifest,
    V09RefinementConfig,
    V09RefinementManifest,
    V09TrainingDataManifest,
)

_TASK_MIGRATION_POLICY_ID = "training_utility_v09_task_migration.v2"
_TASK_MIGRATION_POLICY = {
    "direct_task_id_requires_semantic_signature_match": True,
    "signature_fields": (
        "domain",
        "task_type",
        "instruction",
        "level",
        "requirements",
        "retrieval_scope",
        "corpus_family",
        "fixture_slot",
    ),
    "normalize_subject_numeric_suffix": True,
    "preserve_corpus_family": True,
    "require_unique_semantic_match": True,
}
_TASK_MIGRATION_POLICY_HASH = canonical_hash(
    _TASK_MIGRATION_POLICY,
    prefix="training_utility_v09_task_migration_policy:",
)


def build_v09_training_datasets(
    refinement_config: V09RefinementConfig,
    training_config: TrainingUtilityMVPConfig,
    refinement_manifest: V09RefinementManifest,
    agent_report: AgentValidationReport,
    critic_examples: tuple[QualityCriticExample, ...],
    source_critic_dataset_id: str,
    source_critic_artifact_sha256: str,
    *,
    allow_offline_refinement_pilot: bool = False,
    reference_cache_dir: Path | None = None,
) -> tuple[
    dict[V09Cohort, tuple[SFTRecord, ...]],
    tuple[SFTRecord, ...],
    V09TrainingDataManifest,
]:
    """Materialize the frozen C1-C4 causal comparison without hidden fallbacks."""

    _validate_build_contract(
        refinement_config,
        training_config,
        refinement_manifest,
        allow_offline_refinement_pilot=allow_offline_refinement_pilot,
    )
    reference_records, evaluation_records = _cached_reference_records(
        training_config,
        reference_cache_dir,
        refinement_config=refinement_config,
        agent_report=agent_report,
    )
    reference_by_task = {item.task_id: item for item in reference_records}
    reference_by_signature: dict[str, list[SFTRecord]] = defaultdict(list)
    for record in reference_records:
        reference_by_signature[_record_task_signature(record)].append(record)
    mapped_examples: list[tuple[QualityCriticExample, str]] = []
    migration_domain_counts: Counter[str] = Counter()
    for item in critic_examples:
        if item.candidate_source != "real_agent":
            continue
        source_signature = _task_signature(dict(item.critic_input["task"]))
        current_task_id = item.task_id if item.task_id in reference_by_task else None
        if current_task_id is not None and source_signature != _record_task_signature(
            reference_by_task[current_task_id]
        ):
            raise ValueError(
                f"real-agent task ID was reused with different semantics: {item.task_id}"
            )
        if current_task_id is None:
            matches = reference_by_signature.get(source_signature, [])
            if len(matches) == 1:
                current_task_id = matches[0].task_id
                migration_domain_counts[item.domain] += 1
        if current_task_id is not None:
            mapped_examples.append((item, current_task_id))
    real_examples = tuple(item for item, _ in mapped_examples)
    if len(real_examples) != len({item.task_id for item in real_examples}):
        raise ValueError("v0.9 requires one real Agent candidate per source task")
    unfiltered_records, unfiltered_example_ids = _representable_real_records(
        real_examples, prompt_version=training_config.prompt_version
    )
    current_task_by_source = {item.task_id: task_id for item, task_id in mapped_examples}
    accepted_examples = tuple(
        item
        for item in real_examples
        if item.contract_annotation.acceptability == AcceptabilityLabel.ACCEPT
    )
    accepted_example_ids = {
        current_task_by_source[item.task_id]: item.example_id
        for item in accepted_examples
        if item.task_id in unfiltered_records
    }
    real_source_example_ids: dict[str, str] = {}
    for item in real_examples:
        if item.task_id not in unfiltered_records:
            continue
        current_task_id = current_task_by_source[item.task_id]
        previous = real_source_example_ids.get(current_task_id)
        if previous is not None and previous != item.example_id:
            raise ValueError("multiple real Agent candidates map to one current task identity")
        real_source_example_ids[current_task_id] = item.example_id

    full_update = next(
        item for item in refinement_manifest.ccgr_updates if item.ablation_id == "full_ccgr"
    )
    static_update = next(
        item for item in refinement_manifest.ccgr_updates if item.ablation_id == "static_verified"
    )
    declared_quotas = _domain_quotas(
        refinement_config.cohort_example_budget,
        refinement_config.domain_weights,
    )
    quotas = _active_domain_quotas(declared_quotas)

    c1_source = tuple(unfiltered_records.values())
    c1_selected = _quota_take(
        c1_source,
        quotas,
        seed=refinement_config.training_seed + 101,
    )
    c1 = tuple(
        _prepare_unverified_record(
            item,
            V09Cohort.CONVENTIONAL_SYNTHETIC,
            source_example_id=unfiltered_example_ids[item.task_id],
        )
        for item in c1_selected
    )

    c2_selected = _quota_take(
        reference_records,
        quotas,
        seed=refinement_config.training_seed + 201,
    )
    c2 = tuple(_prepare_grounded_record(item, V09Cohort.EVIDENCE_GROUNDED) for item in c2_selected)

    feedback_source_records: list[SFTRecord] = []
    source_cells: dict[str, SynthesisCell] = {}
    for task_id in sorted(real_source_example_ids):
        source_record = reference_by_task.get(task_id)
        if source_record is None:
            raise ValueError("mapped real Agent feedback has no current reference task")
        cell = _record_cell(source_record)
        if (
            cell.cell_id not in static_update.cell_transition_map
            or cell.cell_id not in full_update.cell_transition_map
        ):
            continue
        static_cell = static_update.cell_transition_map[cell.cell_id]
        full_cell = full_update.cell_transition_map[cell.cell_id]
        if (
            static_cell not in static_update.next_policy.probabilities
            or full_cell not in full_update.next_policy.probabilities
        ):
            continue
        feedback_source_records.append(source_record)
        source_cells[task_id] = cell
    feedback_source_pool = tuple(feedback_source_records)
    if not feedback_source_pool:
        raise ValueError("C3/C4 have no mapped real feedback source records")
    feedback_source_pool_hash = canonical_hash(
        tuple((item.task_id, item.record_hash) for item in feedback_source_pool),
        prefix="training_utility_v09_feedback_source_pool:",
    )

    candidate_pool_id = "route_b_closed_loop_superpool"
    fixture_start = fresh_fixture_start_index(
        refinement_config,
        cohort_namespace=candidate_pool_id,
    )
    c3_partition, c4_partition = (
        ("A", "B") if refinement_config.materialization_seed % 2 == 0 else ("B", "A")
    )
    c3_fixture_provider = V09FixtureBindingProvider(
        namespace="c3_static_verified",
        start_index=fixture_start,
        candidate_pool_id=candidate_pool_id,
        candidate_pool_size=refinement_config.materialization_superpool_size,
        sampling_partition_id=c3_partition,
        pool_split_seed=refinement_config.materialization_seed,
        maximum_scan_multiplier=refinement_config.materialization_scan_multiplier,
        enabled_domains=("finance",),
    )
    c4_fixture_provider = V09FixtureBindingProvider(
        namespace="c4_feedback_refined",
        start_index=fixture_start,
        candidate_pool_id=candidate_pool_id,
        candidate_pool_size=refinement_config.materialization_superpool_size,
        sampling_partition_id=c4_partition,
        pool_split_seed=refinement_config.materialization_seed,
        maximum_scan_multiplier=refinement_config.materialization_scan_multiplier,
        enabled_domains=("finance",),
    )
    finance_source_adapter_ids = _domain_evidence_adapter_ids(
        feedback_source_pool,
        domain="finance",
    )
    finance_archive_source = (
        len(finance_source_adapter_ids) == 1
        and finance_source_adapter_ids <= ARCHIVE_BACKED_FINANCE_ADAPTER_IDS
    )
    archive_config_path = refinement_config.finance_archive_config_path
    c3_provider: SynthesisBindingProviderProtocol
    c4_provider: SynthesisBindingProviderProtocol
    if finance_archive_source:
        if archive_config_path is None:
            raise ValueError("archive-backed Finance feedback requires finance_archive_config_path")
        archive_adapter = FinanceArchiveAdapter(FinanceArchiveConfig.from_json(archive_config_path))
        c3_archive_provider = FinanceArchiveBindingProvider(
            archive_adapter,
            candidate_pool_id="route_b_finance_archive_superpool",
            sampling_partition_id=c3_partition,
            pool_split_seed=refinement_config.materialization_seed,
        )
        c4_archive_provider = c3_archive_provider.for_partition(c4_partition)
        c3_provider = c3_archive_provider
        c4_provider = c4_archive_provider
        finance_archive_provider_used = True
    else:
        c3_provider = c3_fixture_provider
        c4_provider = c4_fixture_provider
        finance_archive_provider_used = False
    if static_update.conditioning_mode != "fixed_group_marginals":
        raise ValueError("C3 policy must freeze group marginals before materialization")
    if full_update.conditioning_mode != "fixed_group_marginals":
        raise ValueError("C4 policy must freeze group marginals before materialization")
    if static_update.allocated_group_counts != quotas:
        raise ValueError("C3 conditional allocation does not match frozen domain quotas")
    if full_update.allocated_group_counts != quotas:
        raise ValueError("C4 conditional allocation does not match frozen domain quotas")
    c3_requested_counts = static_update.allocated_counts
    c4_requested_counts = full_update.allocated_counts
    frozen_identity_records = (*reference_records, *evaluation_records)
    forbidden_task_ids = {item.task_id for item in frozen_identity_records}
    forbidden_binding_ids = _record_binding_ids(frozen_identity_records)
    forbidden_evidence_version_ids = _record_evidence_version_ids(frozen_identity_records)
    evaluation_subject_ids = _record_subject_ids(evaluation_records)
    c3_materializer = RefinedSynthesisMaterializer(c3_provider)
    c3_artifacts, c3_materialization_report = c3_materializer.materialize(
        static_update,
        requested_counts=c3_requested_counts,
        seed=refinement_config.materialization_seed,
        forbidden_task_ids=forbidden_task_ids,
        forbidden_binding_ids=forbidden_binding_ids,
        forbidden_evidence_version_ids=forbidden_evidence_version_ids,
        forbidden_subject_ids=evaluation_subject_ids,
    )
    if c3_materialization_report.status != "passed":
        raise ValueError(
            f"C3 fresh synthesis materialization failed: {c3_materialization_report.failure_counts}"
        )
    c3 = _materialized_records(
        c3_artifacts,
        V09Cohort.VERIFIED_STATIC,
        update=static_update,
        source_cells_by_task=source_cells,
        source_example_ids=real_source_example_ids,
        accepted_example_ids=accepted_example_ids,
        materialization_report=c3_materialization_report,
        clause_feedback=refinement_manifest.clause_feedback,
        source_kind="quality_contract_verified_new_compilation",
        prompt_version=training_config.prompt_version,
    )

    c3_task_ids = {item.compiled.task.task_id for item in c3_artifacts}
    c3_binding_ids = {item.binding.binding_id for item in c3_artifacts}
    c3_evidence_version_ids = {
        evidence.evidence_version_id
        for item in c3_artifacts
        for evidence in item.candidate.corpus.evidence
    }
    c4_materializer = RefinedSynthesisMaterializer(c4_provider)
    c4_artifacts, c4_materialization_report = c4_materializer.materialize(
        full_update,
        requested_counts=c4_requested_counts,
        seed=refinement_config.materialization_seed,
        forbidden_task_ids=forbidden_task_ids | c3_task_ids,
        forbidden_binding_ids=forbidden_binding_ids | c3_binding_ids,
        forbidden_evidence_version_ids=(forbidden_evidence_version_ids | c3_evidence_version_ids),
        forbidden_subject_ids=evaluation_subject_ids,
    )
    if c4_materialization_report.status != "passed":
        raise ValueError(
            f"C4 fresh synthesis materialization failed: {c4_materialization_report.failure_counts}"
        )
    c4 = _materialized_records(
        c4_artifacts,
        V09Cohort.FEEDBACK_REFINED,
        update=full_update,
        source_cells_by_task=source_cells,
        source_example_ids=real_source_example_ids,
        accepted_example_ids=accepted_example_ids,
        materialization_report=c4_materialization_report,
        clause_feedback=refinement_manifest.clause_feedback,
        source_kind="ccgr_refined_verified_new_compilation",
        prompt_version=training_config.prompt_version,
        feedback_source=refinement_manifest.feedback_source,
    )
    cohorts = {
        V09Cohort.CONVENTIONAL_SYNTHETIC: c1,
        V09Cohort.EVIDENCE_GROUNDED: c2,
        V09Cohort.VERIFIED_STATIC: c3,
        V09Cohort.FEEDBACK_REFINED: c4,
    }
    for cohort, records in cohorts.items():
        if len(records) != refinement_config.cohort_example_budget:
            raise ValueError(
                f"{cohort.value} has {len(records)} records; expected "
                f"{refinement_config.cohort_example_budget}"
            )
        observed = dict(sorted(Counter(item.domain for item in records).items()))
        if observed != quotas:
            raise ValueError(f"{cohort.value} domain quota mismatch: {observed}")

    cohort_manifests = (
        _cohort_manifest(
            V09Cohort.CONVENTIONAL_SYNTHETIC,
            c1,
            selection_policy_id="unfiltered_real_agent_hash_sample.v1",
            eligible_source_records=c1_source,
            accepted_real_link_count=0,
        ),
        _cohort_manifest(
            V09Cohort.EVIDENCE_GROUNDED,
            c2,
            selection_policy_id="deterministic_reference_hash_sample.v1",
            eligible_source_records=reference_records,
            accepted_real_link_count=0,
        ),
        _cohort_manifest(
            V09Cohort.VERIFIED_STATIC,
            c3,
            selection_policy_id=static_update.update_id,
            eligible_source_records=feedback_source_pool,
            eligible_source_pool_hash=feedback_source_pool_hash,
            accepted_real_link_count=_accepted_real_link_count(c3),
            real_feedback_link_count=len(c3),
            materialization_report=c3_materialization_report,
        ),
        _cohort_manifest(
            V09Cohort.FEEDBACK_REFINED,
            c4,
            selection_policy_id=full_update.update_id,
            eligible_source_records=feedback_source_pool,
            eligible_source_pool_hash=feedback_source_pool_hash,
            accepted_real_link_count=_accepted_real_link_count(c4),
            real_feedback_link_count=len(c4),
            materialization_report=c4_materialization_report,
        ),
    )
    training_records = tuple(item for values in cohorts.values() for item in values)
    isolation = _evaluation_isolation(training_records, evaluation_records)
    task_overlap = len(
        {item.task_id for item in training_records} & {item.task_id for item in evaluation_records}
    )
    causal_status = (
        "online_ready" if refinement_manifest.round0_real_agent_feedback else "offline_pilot_only"
    )
    status = "ready" if causal_status == "online_ready" else "pilot_ready"
    limitations = (
        "The evaluation set is internal and contract-generated, not an external benchmark.",
        "C1 is an unfiltered real-Agent baseline; its targets may contain model errors.",
        "C3 and C4 use one deterministic compiler, one fresh candidate super-pool, "
        "a shared materialization seed, and disjoint cross-over partitions; "
        "their conditional Cell allocation is the intended variable.",
        "C1/C2/C3 form an exploratory co-compilation axis because program visibility, "
        "planning track, task pool, and teacher target are not jointly controlled.",
        *(
            ()
            if finance_archive_provider_used
            else (
                "This run's Finance feedback Cells are fixture-backed; the native "
                "FinanceArchiveBindingProvider is available but was not causally linked "
                "to this source pool.",
            )
        ),
        *(
            ()
            if refinement_manifest.round0_real_agent_feedback
            else (
                "C4 uses offline typed-counterfactual feedback and cannot identify "
                "real-Agent beta utility.",
            )
        ),
    )
    evaluation_hash = canonical_hash(
        tuple(item.record_hash for item in evaluation_records),
        prefix="training_utility_evaluation_dataset:",
    )
    representable_domain_counts = dict(
        sorted(Counter(item.domain for item in unfiltered_records.values()).items())
    )
    identity = {
        "version": TRAINING_UTILITY_V09_VERSION,
        "experiment_protocol_id": refinement_config.experiment_protocol_id,
        "research_question_ids": refinement_config.research_question_ids,
        "primary_training_domain": refinement_config.primary_training_domain,
        "cross_domain_validation_domains": (refinement_config.cross_domain_validation_domains),
        "refinement_config_hash": refinement_config.config_hash,
        "training_config_hash": training_config.config_hash,
        "refinement_manifest_id": refinement_manifest.manifest_id,
        "source_agent_run_id": agent_report.run_id,
        "source_critic_dataset_id": source_critic_dataset_id,
        "source_critic_artifact_sha256": source_critic_artifact_sha256,
        "task_migration_policy_hash": _TASK_MIGRATION_POLICY_HASH,
        "source_real_candidate_count": len(critic_examples),
        "mapped_real_candidate_count": len(mapped_examples),
        "semantic_migration_domain_counts": dict(sorted(migration_domain_counts.items())),
        "representable_real_domain_counts": representable_domain_counts,
        "accepted_mapped_candidate_count": len(accepted_example_ids),
        "cohort_hashes": tuple(item.dataset_hash for item in cohort_manifests),
        "c3_materialization_report_id": c3_materialization_report.report_id,
        "c4_materialization_report_id": c4_materialization_report.report_id,
        "candidate_pool_contract_hash": (c3_materialization_report.candidate_pool_contract_hash),
        "experiment_axes": refinement_manifest.experiment_axes,
        "finance_source_adapter_ids": tuple(sorted(finance_source_adapter_ids)),
        "finance_archive_provider_used": finance_archive_provider_used,
        "evaluation_hash": evaluation_hash,
        "causal_status": causal_status,
    }
    c3_task_identity_ids = {item.task_id for item in c3}
    c4_task_identity_ids = {item.task_id for item in c4}
    c3_record_binding_ids = _record_binding_ids(c3)
    c4_record_binding_ids = _record_binding_ids(c4)
    c3_record_evidence_ids = _record_evidence_version_ids(c3)
    c4_record_evidence_ids = _record_evidence_version_ids(c4)
    compiler_contract_shared = (
        c3_materialization_report.compiler_contract_hash
        == c4_materialization_report.compiler_contract_hash
    )
    candidate_superpool_shared = (
        c3_materialization_report.candidate_pool_contract_hash
        == c4_materialization_report.candidate_pool_contract_hash
    )
    sampling_partitions_disjoint = (
        c3_materialization_report.sampling_partition_id
        != c4_materialization_report.sampling_partition_id
    )
    manifest = V09TrainingDataManifest(
        manifest_id=canonical_hash(
            identity,
            prefix="training_utility_v09_data_manifest:",
        ),
        experiment_protocol_id=refinement_config.experiment_protocol_id,
        research_question_ids=refinement_config.research_question_ids,
        primary_training_domain=refinement_config.primary_training_domain,
        cross_domain_validation_domains=(refinement_config.cross_domain_validation_domains),
        engineering_regression_cohort_ids=(refinement_config.engineering_regression_cohort_ids),
        refinement_config_hash=refinement_config.config_hash,
        training_config_hash=training_config.config_hash,
        refinement_manifest_id=refinement_manifest.manifest_id,
        canonical_base_model=refinement_config.base_model,
        canonical_model_revision=refinement_config.base_model_revision,
        runtime_base_model=training_config.base_model,
        runtime_model_revision=training_config.model_revision or "local_unversioned",
        source_agent_run_id=agent_report.run_id,
        source_critic_dataset_id=source_critic_dataset_id,
        source_critic_artifact_sha256=source_critic_artifact_sha256,
        task_migration_policy_id=_TASK_MIGRATION_POLICY_ID,
        task_migration_policy_hash=_TASK_MIGRATION_POLICY_HASH,
        source_real_candidate_count=len(critic_examples),
        mapped_real_candidate_count=len(mapped_examples),
        unmapped_real_candidate_count=len(critic_examples) - len(mapped_examples),
        semantic_migration_count=sum(migration_domain_counts.values()),
        semantic_migration_domain_counts=dict(sorted(migration_domain_counts.items())),
        representable_real_candidate_count=len(unfiltered_records),
        representable_real_domain_counts=representable_domain_counts,
        accepted_mapped_candidate_count=len(accepted_example_ids),
        round0_real_agent_feedback=refinement_manifest.round0_real_agent_feedback,
        offline_refinement_override=allow_offline_refinement_pilot,
        causal_status=causal_status,
        full_ccgr_update_id=full_update.update_id,
        supervised_token_budget=refinement_config.supervised_token_budget,
        cohort_example_budget=refinement_config.cohort_example_budget,
        expected_domain_counts=declared_quotas,
        cohorts=cohort_manifests,
        evaluation_record_count=len(evaluation_records),
        evaluation_domain_counts=dict(
            sorted(Counter(item.domain for item in evaluation_records).items())
        ),
        evaluation_record_ids=tuple(item.record_id for item in evaluation_records),
        evaluation_dataset_hash=evaluation_hash,
        train_evaluation_task_overlap_count=task_overlap,
        train_evaluation_subject_overlap_count=isolation["subject_overlap_count"],
        train_evaluation_evidence_overlap_count=isolation["evidence_overlap_count"],
        train_evaluation_evidence_version_overlap_count=(
            isolation["evidence_version_overlap_count"]
        ),
        train_evaluation_source_record_overlap_count=(isolation["source_record_overlap_count"]),
        train_evaluation_binding_overlap_count=isolation["binding_overlap_count"],
        c3_c4_task_overlap_count=len(c3_task_identity_ids & c4_task_identity_ids),
        c3_c4_binding_overlap_count=len(c3_record_binding_ids & c4_record_binding_ids),
        c3_c4_evidence_version_overlap_count=len(c3_record_evidence_ids & c4_record_evidence_ids),
        c3_c4_source_pool_shared=True,
        c3_c4_compiler_contract_shared=compiler_contract_shared,
        finance_source_adapter_ids=tuple(sorted(finance_source_adapter_ids)),
        finance_archive_provider_used=finance_archive_provider_used,
        c3_c4_candidate_superpool_shared=candidate_superpool_shared,
        c3_c4_sampling_partitions_disjoint=sampling_partitions_disjoint,
        c3_c4_materialization_seed_shared=(
            c3_materialization_report.materialization_seed
            == c4_materialization_report.materialization_seed
        ),
        experiment_axes=refinement_manifest.experiment_axes,
        synthesis_closed_loop_status="new_binding_compilation",
        limitations=limitations,
        status=status,
    )
    return cohorts, evaluation_records, manifest


def load_v09_real_agent_artifacts(
    artifact_dir: Path,
) -> tuple[
    AgentValidationReport,
    tuple[QualityCriticExample, ...],
    str,
]:
    """Stream only real Agent rows while hashing the complete immutable archive."""

    report = AgentValidationReport.model_validate_json(
        (artifact_dir / "agent_validation_report.json").read_text(encoding="utf-8")
    )
    critic_path = artifact_dir / "quality_critic_dataset.jsonl"
    digest = sha256()
    examples: list[QualityCriticExample] = []
    with critic_path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            if (
                b'"candidate_source": "real_agent"' not in raw_line
                and b'"candidate_source":"real_agent"' not in raw_line
            ):
                continue
            examples.append(QualityCriticExample.model_validate_json(raw_line))
    if len(examples) != len({item.task_id for item in examples}):
        raise ValueError("real Agent archive contains duplicate task candidates")
    if report.critic_dataset_id is None:
        raise ValueError("Agent report does not pin a Quality Critic dataset")
    return report, tuple(examples), digest.hexdigest()


def _cached_reference_records(
    config: TrainingUtilityMVPConfig,
    cache_dir: Path | None,
    *,
    refinement_config: V09RefinementConfig,
    agent_report: AgentValidationReport,
) -> tuple[tuple[SFTRecord, ...], tuple[SFTRecord, ...]]:
    finance_cases, source_contract_hash = _finance_reference_cases(
        config,
        refinement_config,
        agent_report,
    )
    if cache_dir is None:
        return _reference_and_evaluation_records(config, finance_cases=finance_cases)
    manifest_path = cache_dir / "manifest.json"
    training_path = cache_dir / "training_pool.jsonl"
    evaluation_path = cache_dir / "evaluation.jsonl"
    if manifest_path.is_file() and training_path.is_file() and evaluation_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("config_hash") != config.config_hash:
            raise ValueError("reference cache belongs to a different training config")
        if manifest.get("source_contract_hash") != source_contract_hash:
            raise ValueError("reference cache belongs to a different task source contract")
        training = tuple(
            SFTRecord.model_validate_json(line)
            for line in training_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        evaluation = tuple(
            SFTRecord.model_validate_json(line)
            for line in evaluation_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        observed_hash = canonical_hash(
            {
                "training": tuple(item.record_hash for item in training),
                "evaluation": tuple(item.record_hash for item in evaluation),
            },
            prefix="training_utility_v09_reference_cache:",
        )
        if observed_hash != manifest.get("cache_hash"):
            raise ValueError("reference cache content hash is invalid")
        return training, evaluation
    training, evaluation = _reference_and_evaluation_records(
        config,
        finance_cases=finance_cases,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(training_path, training)
    _write_jsonl(evaluation_path, evaluation)
    cache_hash = canonical_hash(
        {
            "training": tuple(item.record_hash for item in training),
            "evaluation": tuple(item.record_hash for item in evaluation),
        },
        prefix="training_utility_v09_reference_cache:",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "config_hash": config.config_hash,
                "source_contract_hash": source_contract_hash,
                "finance_task_source": agent_report.finance_task_source,
                "finance_archive_kg_build_id": agent_report.finance_archive_kg_build_id,
                "training_record_count": len(training),
                "evaluation_record_count": len(evaluation),
                "cache_hash": cache_hash,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return training, evaluation


def _finance_reference_cases(
    config: TrainingUtilityMVPConfig,
    refinement_config: V09RefinementConfig,
    agent_report: AgentValidationReport,
) -> tuple[tuple[ContractCase, ...] | None, str]:
    if agent_report.finance_task_source != "archive":
        return None, canonical_hash(
            {"source": "fixture", "config_hash": config.config_hash},
            prefix="training_utility_v09_reference_source:",
        )
    archive_path = refinement_config.finance_archive_config_path
    if archive_path is None:
        raise ValueError("archive-backed Agent feedback requires finance_archive_config_path")
    archive_config = FinanceArchiveConfig.from_json(archive_path)
    if archive_config.required_kg_build_id != agent_report.finance_archive_kg_build_id:
        raise ValueError("Agent and training reference KG builds do not match")
    source_contract = dict(agent_report.finance_task_source_contract)
    required_fields = {
        "candidate_pool_id",
        "sampling_partition",
        "pool_split_seed",
        "selection_seed",
        "retrieval_tracks",
        "planning_tracks",
        "evidence_scan_limit",
        "evidence_sample_size",
        "stratum_reservoir_size",
        "candidates_per_pattern",
    }
    missing = required_fields - set(source_contract)
    if missing:
        raise ValueError(f"Agent Archive source contract is incomplete: {sorted(missing)}")
    if source_contract.get("source") != "archive":
        raise ValueError("Agent task-source contract is not Archive-backed")
    if source_contract.get("kg_build_id") != agent_report.finance_archive_kg_build_id:
        raise ValueError("Agent task-source contract pins another KG build")
    if source_contract.get("require_corpus_disjoint") is not True:
        raise ValueError("Agent task-source contract must require corpus-disjoint cases")
    retrieval_tracks = _required_contract_str_tuple(source_contract, "retrieval_tracks")
    planning_tracks = _required_contract_str_tuple(source_contract, "planning_tracks")
    if retrieval_tracks != (RetrievalTrack.RESOLVED.value,) or planning_tracks != (
        PlanningTrack.PLAN_GIVEN.value,
    ):
        raise ValueError("v0.9 training requires resolved retrieval and plan-given Agent tracks")
    observed_archive_hash = canonical_hash(
        archive_config,
        prefix="finance_archive_config:",
    )
    if source_contract.get("archive_config_hash") != observed_archive_hash:
        raise ValueError("Agent and training Archive configs do not match")
    adapter = FinanceArchiveAdapter(archive_config)
    provider = FinanceArchiveBindingProvider(
        adapter,
        candidate_pool_id=_required_contract_str(source_contract, "candidate_pool_id"),
        sampling_partition_id=_required_contract_str(source_contract, "sampling_partition"),
        pool_split_seed=_required_contract_int(source_contract, "pool_split_seed"),
        evidence_scan_limit=_required_contract_int(source_contract, "evidence_scan_limit"),
        evidence_sample_size=_required_contract_int(source_contract, "evidence_sample_size"),
        stratum_reservoir_size=_required_contract_int(source_contract, "stratum_reservoir_size"),
        candidates_per_pattern=_required_contract_int(source_contract, "candidates_per_pattern"),
    )
    training_target = config.candidate_task_target("finance")
    evaluation_target = config.evaluation_task_target("finance")
    total = training_target + evaluation_target
    selection_seed = _required_contract_int(source_contract, "selection_seed")
    agent_task_ids = {item.task_id for item in agent_report.samples if item.domain == "finance"}
    if len(agent_task_ids) > training_target:
        raise ValueError("Finance candidate pool is smaller than the real Agent prefix")
    cases: tuple[ContractCase, ...] | None = None
    split_error: ValueError | None = None
    for multiplier in (1, 2, 4, 8):
        superpool = provider.contract_cases(total * multiplier, seed=selection_seed)
        try:
            cases = _subject_disjoint_finance_case_split(
                superpool,
                training_count=training_target,
                evaluation_count=evaluation_target,
                fixed_training_prefix_count=len(agent_task_ids),
                seed=selection_seed,
            )
        except ValueError as error:
            split_error = error
            continue
        break
    if cases is None:
        raise ValueError(
            "Finance Archive cannot form a subject-disjoint train/evaluation split"
        ) from split_error
    expected_prefix_ids = {
        materialize_track_variant(
            item.task,
            item.corpus,
            retrieval_track=RetrievalTrack.RESOLVED,
            planning_track=PlanningTrack.PLAN_GIVEN,
        ).task_id
        for item in cases[: len(agent_task_ids)]
    }
    if agent_task_ids != expected_prefix_ids:
        raise ValueError(
            "real Finance Agent tasks are not the exact prefix of the pinned Archive reference pool"
        )
    source_hash = canonical_hash(
        {
            "agent_task_source_manifest_hash": agent_report.task_source_manifest_hash,
            "source_contract": source_contract,
            "provider_contract_hash": provider.provider_contract_hash,
            "reference_task_ids": tuple(item.task.task_id for item in cases),
        },
        prefix="training_utility_v09_reference_source:",
    )
    return cases, source_hash


def _case_subject_ids(case: ContractCase) -> frozenset[str]:
    retrieval_scope = case.task.public.retrieval_scope
    if isinstance(retrieval_scope, Mapping):
        subject_ids = retrieval_scope.get("subject_ids") or ()
    else:
        subject_ids = getattr(retrieval_scope, "subject_ids", ())
    return frozenset(str(subject_id) for subject_id in subject_ids if subject_id)


def _subject_disjoint_finance_case_split(
    cases: tuple[ContractCase, ...],
    *,
    training_count: int,
    evaluation_count: int,
    fixed_training_prefix_count: int,
    seed: int,
) -> tuple[ContractCase, ...]:
    if fixed_training_prefix_count > training_count:
        raise ValueError("fixed Finance training prefix exceeds the candidate target")
    if len(cases) < training_count + evaluation_count:
        raise ValueError("Finance split super-pool is smaller than the requested split")

    fixed_training = list(cases[:fixed_training_prefix_count])
    fixed_subjects = (
        set().union(
            *(_case_subject_ids(case) for case in fixed_training),
        )
        if fixed_training
        else set()
    )
    tail = tuple(cases[fixed_training_prefix_count:])
    needed_training = training_count - len(fixed_training)
    for trial in range(64):
        evaluation_order = sorted(
            (case for case in tail if not (_case_subject_ids(case) & fixed_subjects)),
            key=lambda case: (
                len(_case_subject_ids(case)),
                canonical_hash(
                    {
                        "seed": seed,
                        "trial": trial,
                        "role": "evaluation",
                        "task_id": case.task.task_id,
                    },
                    prefix="v09_finance_subject_split:",
                ),
            ),
        )
        evaluation = evaluation_order[:evaluation_count]
        if len(evaluation) != evaluation_count:
            continue
        evaluation_task_ids = {case.task.task_id for case in evaluation}
        evaluation_subjects = (
            set().union(
                *(_case_subject_ids(case) for case in evaluation),
            )
            if evaluation
            else set()
        )
        training_tail = sorted(
            (
                case
                for case in tail
                if case.task.task_id not in evaluation_task_ids
                and not (_case_subject_ids(case) & evaluation_subjects)
            ),
            key=lambda case: canonical_hash(
                {
                    "seed": seed,
                    "trial": trial,
                    "role": "training",
                    "task_id": case.task.task_id,
                },
                prefix="v09_finance_subject_split:",
            ),
        )[:needed_training]
        if len(training_tail) != needed_training:
            continue
        training = (*fixed_training, *training_tail)
        observed_training_subjects = (
            set().union(
                *(_case_subject_ids(case) for case in training),
            )
            if training
            else set()
        )
        if observed_training_subjects & evaluation_subjects:
            raise AssertionError("subject-disjoint Finance split construction failed")
        return (*training, *evaluation)
    raise ValueError("subject-disjoint Finance split search exhausted deterministic trials")


def _required_contract_str(contract: Mapping[str, object], key: str) -> str:
    value = contract.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Archive task-source contract field {key!r} must be a string")
    return value


def _required_contract_str_tuple(contract: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = contract.get(key)
    if (
        not isinstance(value, (list, tuple))
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ValueError(f"Archive task-source contract field {key!r} must be a string sequence")
    return tuple(value)


def _required_contract_int(contract: Mapping[str, object], key: str) -> int:
    value = contract.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Archive task-source contract field {key!r} must be an integer")
    return value


def write_v09_training_datasets(
    output_dir: Path,
    cohorts: Mapping[V09Cohort, tuple[SFTRecord, ...]],
    evaluation_records: tuple[SFTRecord, ...],
    manifest: V09TrainingDataManifest,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifests_by_cohort = {item.cohort: item for item in manifest.cohorts}
    for cohort in V09Cohort:
        _write_jsonl(output_dir / f"{cohort.value}.jsonl", cohorts[cohort])
        materialization = manifests_by_cohort[cohort].materialization_report
        if materialization is not None:
            (output_dir / f"{cohort.value}_materialization_report.json").write_text(
                json.dumps(
                    materialization.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
    _write_jsonl(output_dir / "evaluation.jsonl", evaluation_records)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    cohort_summary: dict[str, dict[str, Any]] = {}
    for cohort in V09Cohort:
        cohort_manifest = manifests_by_cohort[cohort]
        report = cohort_manifest.materialization_report
        cohort_summary[cohort.value] = {
            "record_count": cohort_manifest.record_count,
            "dataset_hash": cohort_manifest.dataset_hash,
            "materialization_report_id": report.report_id if report is not None else None,
        }

    materialization_contracts: dict[str, dict[str, Any]] = {}
    for cohort in (V09Cohort.VERIFIED_STATIC, V09Cohort.FEEDBACK_REFINED):
        report = manifests_by_cohort[cohort].materialization_report
        if report is None:
            continue
        materialization_contracts[cohort.value] = {
            "compiler_contract_hash": report.compiler_contract_hash,
            "candidate_pool_contract_hash": report.candidate_pool_contract_hash,
            "candidate_pool_id": report.candidate_pool_id,
            "sampling_contract_hash": report.sampling_contract_hash,
            "sampling_partition_id": report.sampling_partition_id,
            "materialization_seed": report.materialization_seed,
            "seed_effective": report.seed_effective,
            "requested_sample_count": report.requested_sample_count,
            "successfully_materialized_count": report.successfully_materialized_count,
            "contract_pass_rate": report.contract_pass_rate,
            "failure_counts": report.failure_counts,
        }

    route_b = {
        "manifest_id": manifest.manifest_id,
        "manifest_hash": canonical_hash(
            manifest.model_dump(mode="json"),
            prefix="route_b_training_manifest:",
        ),
        "causal_status": manifest.causal_status,
        "synthesis_closed_loop_status": manifest.synthesis_closed_loop_status,
        "experiment_axes": [item.model_dump(mode="json") for item in manifest.experiment_axes],
        "fixed_group_counts": manifest.expected_domain_counts,
        "finance_binding": {
            "source_adapter_ids": manifest.finance_source_adapter_ids,
            "archive_provider_used": manifest.finance_archive_provider_used,
        },
        "cohorts": cohort_summary,
        "materialization_contracts": materialization_contracts,
        "c3_c4": {
            "task_overlap_count": manifest.c3_c4_task_overlap_count,
            "binding_overlap_count": manifest.c3_c4_binding_overlap_count,
            "evidence_version_overlap_count": (manifest.c3_c4_evidence_version_overlap_count),
            "compiler_contract_shared": manifest.c3_c4_compiler_contract_shared,
            "candidate_superpool_shared": manifest.c3_c4_candidate_superpool_shared,
            "sampling_partitions_disjoint": (manifest.c3_c4_sampling_partitions_disjoint),
            "materialization_seed_shared": (manifest.c3_c4_materialization_seed_shared),
        },
    }
    (output_dir / "route_b_materialization_summary.json").write_text(
        json.dumps(route_b, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_build_contract(
    refinement_config: V09RefinementConfig,
    training_config: TrainingUtilityMVPConfig,
    manifest: V09RefinementManifest,
    *,
    allow_offline_refinement_pilot: bool,
) -> None:
    failures: list[str] = []
    if manifest.config_hash != refinement_config.config_hash:
        failures.append("refinement_config_hash_mismatch")
    if training_config.cohort_size != refinement_config.cohort_example_budget:
        failures.append("cohort_example_budget_mismatch")
    if training_config.supervised_token_budget != refinement_config.supervised_token_budget:
        failures.append("supervised_token_budget_mismatch")
    if training_config.seed != refinement_config.training_seed:
        failures.append("training_seed_mismatch")
    if training_config.model_revision != refinement_config.base_model_revision:
        failures.append("model_revision_mismatch")
    if training_config.student_interaction_protocol != refinement_config.student_training_format:
        failures.append("training_protocol_mismatch")
    if manifest.round0_real_agent_feedback:
        if manifest.status != "initial_ready" or manifest.online_gate.status != "passed":
            failures.append("online_round0_gate_not_passed")
    elif not allow_offline_refinement_pilot:
        failures.append("offline_refinement_requires_explicit_pilot_override")
    full = next(
        (item for item in manifest.ccgr_updates if item.ablation_id == "full_ccgr"),
        None,
    )
    if full is None or full.status != "passed":
        failures.append("full_ccgr_update_not_passed")
    if failures:
        raise ValueError("v0.9 training data contract blocked: " + "; ".join(failures))


def _representable_real_records(
    examples: tuple[QualityCriticExample, ...],
    *,
    prompt_version: str,
) -> tuple[dict[str, SFTRecord], dict[str, str]]:
    records: dict[str, SFTRecord] = {}
    example_ids: dict[str, str] = {}
    for example in examples:
        try:
            record = record_from_quality_example(
                example,
                UtilityCohort.RANDOM_SYNTHETIC,
                prompt_version=prompt_version,
            )
        except ValueError:
            continue
        records[record.task_id] = record
        example_ids[record.task_id] = example.example_id
    return records, example_ids


def _prepare_unverified_record(
    record: SFTRecord,
    cohort: V09Cohort,
    *,
    source_example_id: str,
) -> SFTRecord:
    payload = json.loads(record.user_prompt)
    selected = set(_action_plan(record).selected_evidence_ids)
    evidence = [
        item for item in payload["evidence_corpus"] if str(item.get("evidence_id")) in selected
    ]
    if len(evidence) != len(selected):
        raise ValueError("C1 selected evidence is absent from its public corpus")
    return _rebuild_record(
        record,
        cohort,
        source_kind="unfiltered_real_agent",
        evidence=evidence,
        hide_program=True,
        metadata={
            "source_real_example_id": source_example_id,
            "quality_contract_applied": False,
            "evidence_grounding_status": "unverified_candidate",
        },
    )


def _prepare_grounded_record(record: SFTRecord, cohort: V09Cohort) -> SFTRecord:
    payload = json.loads(record.user_prompt)
    return _rebuild_record(
        record,
        cohort,
        source_kind="deterministic_evidence_grounded_reference",
        evidence=list(payload["evidence_corpus"]),
        hide_program=True,
        metadata={
            "quality_contract_applied": False,
            "evidence_grounding_status": "deterministic_reference",
        },
    )


def _rebuild_record(
    record: SFTRecord,
    cohort: V09Cohort,
    *,
    source_kind: str,
    evidence: list[dict[str, Any]],
    hide_program: bool,
    metadata: Mapping[str, Any],
) -> SFTRecord:
    payload = json.loads(record.user_prompt)
    task = dict(payload["public_task"])
    if hide_program:
        task["planning_track"] = "plan_hidden"
        task.pop("program_skeleton", None)
        task_metadata = dict(task.get("metadata") or {})
        task_metadata["proof_required"] = False
        task_metadata["quality_contract_required"] = False
        task["metadata"] = task_metadata
    payload["public_task"] = task
    payload["evidence_corpus"] = evidence
    action = _action_plan(record)
    answer = AgentAnswerDecisionContract.model_validate_json(record.messages[4].content)
    public_task = TaskPublicSpec.model_validate(task)
    evidence_items = tuple(EvidenceItem.model_validate(item) for item in evidence)
    trace = execute_action_plan(
        public_task,
        evidence_items,
        action,
        _student_operation_registry(public_task.domain),
    )
    host = make_host_execution_feedback(trace)
    user_prompt = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    action_text = action.model_dump_json()
    host_text = host.model_dump_json()
    answer_text = answer.model_dump_json()
    assistant_target = json.dumps(
        {
            "schema_version": "host_instrumented_student_target.v1",
            "action_plan": action.model_dump(mode="json"),
            "answer_decision": answer.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    messages = (
        record.messages[0],
        SFTMessage(role="user", content=user_prompt, phase="context"),
        SFTMessage(
            role="assistant",
            content=action_text,
            supervise=True,
            phase="action_plan",
        ),
        SFTMessage(role="tool", content=host_text, phase="host_execution"),
        SFTMessage(
            role="assistant",
            content=answer_text,
            supervise=True,
            phase="answer_decision",
        ),
    )
    identity = {
        "cohort": cohort.value,
        "task_id": record.task_id,
        "source_kind": source_kind,
        "user_prompt": user_prompt,
        "assistant_target": assistant_target,
        "system_prompt": record.system_prompt,
        "prompt_version": record.prompt_version,
        "training_format": record.training_format,
    }
    return SFTRecord(
        record_id=canonical_hash(identity, prefix="training_utility_record:"),
        cohort=cohort.value,
        task_id=record.task_id,
        domain=record.domain,
        system_prompt=record.system_prompt,
        user_prompt=user_prompt,
        assistant_target=assistant_target,
        training_format=record.training_format,
        messages=messages,
        source_kind=source_kind,
        contract_label=record.contract_label,
        counterfactual_repair=False,
        metadata={**record.metadata, **metadata},
        prompt_version=record.prompt_version,
    )


def _relabel_record(
    record: SFTRecord,
    cohort: V09Cohort,
    *,
    source_kind: str,
    metadata: Mapping[str, Any],
) -> SFTRecord:
    identity = {
        "cohort": cohort.value,
        "task_id": record.task_id,
        "source_kind": source_kind,
        "user_prompt": record.user_prompt,
        "assistant_target": record.assistant_target,
        "system_prompt": record.system_prompt,
        "prompt_version": record.prompt_version,
        "training_format": record.training_format,
    }
    return record.model_copy(
        update={
            "record_id": canonical_hash(identity, prefix="training_utility_record:"),
            "cohort": cohort.value,
            "source_kind": source_kind,
            "metadata": {**record.metadata, **metadata},
        }
    )


def _action_plan(record: SFTRecord) -> AgentActionPlanContract:
    if len(record.messages) != 5:
        raise ValueError("v0.9 requires host-instrumented five-message records")
    return AgentActionPlanContract.model_validate_json(record.messages[2].content)


def _record_task_signature(record: SFTRecord) -> str:
    return _task_signature(dict(json.loads(record.user_prompt)["public_task"]))


def _task_signature(task: dict[str, Any]) -> str:
    """Match immutable task semantics across prompt-contract metadata revisions."""

    retrieval_scope = dict(task.get("retrieval_scope") or {})
    corpus_boundary = str(retrieval_scope.pop("corpus_boundary", ""))
    fixture_slot_match = re.search(r"(_\d+)$", corpus_boundary)
    fixture_slot = fixture_slot_match.group(1) if fixture_slot_match else None
    corpus_family = re.sub(r"_\d+$", "", corpus_boundary)
    retrieval_scope["subject_ids"] = [
        re.sub(r"_\d+$", "", str(value)) for value in retrieval_scope.get("subject_ids") or ()
    ]
    return canonical_hash(
        {
            "domain": task.get("domain"),
            "task_type": task.get("task_type"),
            "instruction": task.get("instruction"),
            "level": task.get("level"),
            "requirements": task.get("requirements"),
            "retrieval_scope": retrieval_scope,
            "corpus_family": corpus_family,
            "fixture_slot": fixture_slot,
        },
        prefix="training_utility_v09_task_migration_signature:",
    )


def _record_cell(record: SFTRecord) -> SynthesisCell:
    payload = json.loads(record.user_prompt)
    task = TaskPublicSpec.model_validate(payload["public_task"])
    evidence = tuple(EvidenceItem.model_validate(item) for item in payload["evidence_corpus"])
    corpus = EvidenceCorpus(
        corpus_id=canonical_hash(
            tuple(item.evidence_version_id for item in evidence),
            prefix="training_utility_v09_corpus:",
        ),
        evidence=evidence,
    )
    return build_synthesis_cell(task, corpus, _action_plan(record).selected_evidence_ids)


def _materialized_records(
    artifacts: tuple[RefinedSynthesisArtifact, ...],
    cohort: V09Cohort,
    *,
    update: PolicyUpdateResult,
    source_cells_by_task: Mapping[str, SynthesisCell],
    source_example_ids: Mapping[str, str],
    accepted_example_ids: Mapping[str, str],
    materialization_report: SynthesisMaterializationReport,
    source_kind: str,
    prompt_version: str = TRAINING_UTILITY_AGENT_PROMPT_VERSION,
    clause_feedback: tuple[ClauseFeedback, ...] = (),
    feedback_source: str | None = None,
) -> tuple[SFTRecord, ...]:
    links_by_target_cell: dict[str, list[str]] = defaultdict(list)
    accepted_links_by_target_cell: dict[str, list[str]] = defaultdict(list)
    policy_contributors_by_target_cell: dict[str, list[ClauseFeedback]] = defaultdict(list)
    contributors_by_target_cell: dict[str, list[ClauseFeedback]] = defaultdict(list)
    statistics_by_prior_cell = {item.cell_id: item for item in update.statistics}
    prior_cell_by_target = {
        target_cell_id: prior_cell_id
        for prior_cell_id, target_cell_id in update.cell_transition_map.items()
    }
    for task_id, cell in source_cells_by_task.items():
        if task_id not in source_example_ids:
            raise ValueError("feedback source Cell has no real Agent example identity")
        target_cell_id = update.cell_transition_map.get(cell.cell_id)
        if target_cell_id is not None:
            links_by_target_cell[target_cell_id].append(task_id)
            if task_id in accepted_example_ids:
                accepted_links_by_target_cell[target_cell_id].append(task_id)
    for item in clause_feedback:
        target_cell_id = update.cell_transition_map.get(item.cell_id)
        if (
            target_cell_id is not None
            and item.calibrated_weight > 0
            and item.route.value != "interface_failure"
        ):
            policy_contributors_by_target_cell[target_cell_id].append(item)
            if item.task_id in source_cells_by_task and item.task_id in source_example_ids:
                contributors_by_target_cell[target_cell_id].append(item)
    for link_values in links_by_target_cell.values():
        link_values.sort()
    for accepted_values in accepted_links_by_target_cell.values():
        accepted_values.sort()
    for feedback_values in policy_contributors_by_target_cell.values():
        feedback_values.sort(key=lambda item: item.feedback_id)
    for feedback_values in contributors_by_target_cell.values():
        feedback_values.sort(key=lambda item: item.feedback_id)
    target_offsets: Counter[str] = Counter()
    records: list[SFTRecord] = []
    for artifact in artifacts:
        target_cell_id = artifact.request.cell.cell_id
        policy_contributors = policy_contributors_by_target_cell.get(target_cell_id, [])
        contributors = contributors_by_target_cell.get(target_cell_id, [])
        contributing_task_ids = sorted({item.task_id for item in contributors})
        links = (
            contributing_task_ids
            or accepted_links_by_target_cell.get(target_cell_id)
            or links_by_target_cell.get(target_cell_id)
            or []
        )
        if not links:
            raise ValueError(
                f"fresh synthesis Cell is not linked to evaluated real feedback: {target_cell_id}"
            )
        source_task_id = links[target_offsets[target_cell_id] % len(links)]
        target_offsets[target_cell_id] += 1
        source_cell = source_cells_by_task[source_task_id]
        source_candidate_accepted = source_task_id in accepted_example_ids
        prior_cell_id = prior_cell_by_target[target_cell_id]
        statistics = statistics_by_prior_cell[prior_cell_id]
        linked_feedback = tuple(item for item in contributors if item.task_id == source_task_id)
        task = artifact.compiled.task
        metadata = {
            **_task_structure_metadata(task.public),
            "source_real_example_id": source_example_ids[source_task_id],
            "source_real_task_id": source_task_id,
            "source_candidate_accepted": source_candidate_accepted,
            "feedback_lineage_mode": (
                "cell_policy_contribution"
                if contributors
                else "external_policy_cell_context"
                if policy_contributors
                else "cell_context_only"
            ),
            "linked_clause_feedback_ids": tuple(item.feedback_id for item in linked_feedback),
            "contributing_clause_feedback_ids": tuple(item.feedback_id for item in contributors),
            "policy_clause_feedback_ids": tuple(item.feedback_id for item in policy_contributors),
            "unlinked_policy_clause_feedback_ids": tuple(
                item.feedback_id for item in policy_contributors if item not in contributors
            ),
            "contributing_failure_families": tuple(
                sorted({item.failure_family for item in contributors})
            ),
            "policy_failure_families": tuple(
                sorted({item.failure_family for item in policy_contributors})
            ),
            "contributing_feedback_task_ids": tuple(contributing_task_ids),
            "cell_capability_gap_demand": statistics.capability_gap_demand,
            "cell_synthesis_defect_risk": statistics.synthesis_defect_risk,
            "cell_coverage_gap": statistics.coverage_gap,
            "cell_exposure_count": statistics.exposure_count,
            "cell_minimum_exposure_met": statistics.minimum_exposure_met,
            "base_synthesis_cell_id": source_cell.cell_id,
            "synthesis_cell_id": target_cell_id,
            "selection_update_id": update.update_id,
            "materialization_report_id": materialization_report.report_id,
            "synthesis_cell_request_id": artifact.request.request_id,
            "binding_provider_candidate_id": artifact.candidate.candidate_id,
            "binding_id": artifact.binding.binding_id,
            "evidence_bundle_id": artifact.candidate.bundle.bundle_id,
            "proof_graph_id": artifact.candidate.proof_graph.graph_id,
            "quality_contract_id": artifact.compiled.quality_contract.contract_id,
            "reference_trajectory_id": (artifact.compiled.reference_trajectory.trajectory_id),
            "proof_carrying_sample_id": artifact.compiled.sample.sample_id,
            "quality_contract_applied": True,
            "new_identity_compilation": True,
        }
        if source_candidate_accepted:
            metadata["accepted_real_example_id"] = accepted_example_ids[source_task_id]
            metadata["accepted_source_task_id"] = source_task_id
        if feedback_source is not None:
            metadata["feedback_source"] = feedback_source
        records.append(
            make_sft_record(
                cohort=cohort.value,
                task=task.public.model_dump(mode="json", exclude_none=True),
                evidence=[
                    item.model_dump(mode="json", exclude_none=True)
                    for item in artifact.candidate.corpus.evidence
                ],
                target=_reference_response(
                    task,
                    artifact.candidate.bundle,
                    artifact.candidate.operation_registry,
                ),
                source_kind=source_kind,
                contract_label="accept",
                prompt_version=prompt_version,
                metadata=metadata,
            )
        )
    records.sort(
        key=lambda item: canonical_hash(
            item.record_id,
            prefix="v09_materialized_cohort_order:",
        )
    )
    return tuple(records)


def _domain_evidence_adapter_ids(
    records: Iterable[SFTRecord],
    *,
    domain: str,
) -> set[str]:
    adapters: set[str] = set()
    for record in records:
        if record.domain != domain:
            continue
        payload = json.loads(record.user_prompt)
        for evidence in payload.get("evidence_corpus") or ():
            adapter_id = str((evidence.get("provenance") or {}).get("adapter_id") or "")
            if adapter_id:
                adapters.add(adapter_id)
    return adapters


def _record_binding_ids(records: Iterable[SFTRecord]) -> set[str]:
    return {str(item.metadata["binding_id"]) for item in records if item.metadata.get("binding_id")}


def _record_subject_ids(records: Iterable[SFTRecord]) -> set[str]:
    identities: set[str] = set()
    for record in records:
        payload = json.loads(record.user_prompt)
        public_task = payload.get("public_task") or {}
        retrieval_scope = public_task.get("retrieval_scope") or {}
        identities.update(
            str(subject_id) for subject_id in retrieval_scope.get("subject_ids") or () if subject_id
        )
    return identities


def _record_evidence_version_ids(records: Iterable[SFTRecord]) -> set[str]:
    identities: set[str] = set()
    for record in records:
        payload = json.loads(record.user_prompt)
        for evidence in payload.get("evidence_corpus") or ():
            evidence_version_id = str(evidence.get("evidence_version_id") or "")
            if evidence_version_id:
                identities.add(evidence_version_id)
    return identities


def _accepted_real_link_count(records: Iterable[SFTRecord]) -> int:
    return sum(1 for item in records if item.metadata.get("source_candidate_accepted") is True)


def _domain_quotas(
    total: int,
    weights: Mapping[str, float],
) -> dict[str, int]:
    if set(weights) != {"finance", "legal", "science"}:
        raise ValueError("v0.9 domain weights must cover finance, legal, and science")
    raw = {domain: total * value for domain, value in weights.items()}
    quotas = {domain: math.floor(value) for domain, value in raw.items()}
    for domain in sorted(
        weights,
        key=lambda item: (-(raw[item] - quotas[item]), item),
    )[: total - sum(quotas.values())]:
        quotas[domain] += 1
    return dict(sorted(quotas.items()))


def _active_domain_quotas(quotas: Mapping[str, int]) -> dict[str, int]:
    active = {domain: quota for domain, quota in sorted(quotas.items()) if quota > 0}
    if not active:
        raise ValueError("v0.9 requires at least one active domain quota")
    return active


def _quota_take(
    records: tuple[SFTRecord, ...],
    quotas: Mapping[str, int],
    *,
    seed: int,
) -> tuple[SFTRecord, ...]:
    _require_pool_capacity(records, quotas, label="cohort source pool")
    selected: list[SFTRecord] = []
    for domain, quota in sorted(quotas.items()):
        domain_records = [item for item in records if item.domain == domain]
        domain_records.sort(
            key=lambda item: canonical_hash(
                {"seed": seed, "record_id": item.record_id},
                prefix="training_utility_v09_hash_sample:",
            )
        )
        selected.extend(domain_records[:quota])
    selected.sort(key=lambda item: canonical_hash(item.record_id, prefix="v09_cohort_order:"))
    return tuple(selected)


def _policy_quota_take(
    records: tuple[SFTRecord, ...],
    quotas: Mapping[str, int],
    *,
    cell_by_task: Mapping[str, str],
    probabilities: Mapping[str, float],
    seed: int,
) -> tuple[SFTRecord, ...]:
    _require_pool_capacity(records, quotas, label="policy source pool")
    selected: list[SFTRecord] = []
    for domain, quota in sorted(quotas.items()):
        groups: dict[str, list[SFTRecord]] = defaultdict(list)
        for record in records:
            if record.domain != domain:
                continue
            cell_id = cell_by_task[record.task_id]
            if cell_id in probabilities:
                groups[cell_id].append(record)
        capacities = {cell_id: len(values) for cell_id, values in groups.items()}
        allocation = _bounded_weighted_allocation(
            quota,
            capacities,
            {cell_id: probabilities[cell_id] for cell_id in groups},
        )
        for cell_id, count in sorted(allocation.items()):
            values = groups[cell_id]
            values.sort(
                key=lambda item: canonical_hash(
                    {"seed": seed, "cell_id": cell_id, "record_id": item.record_id},
                    prefix="training_utility_v09_policy_sample:",
                )
            )
            selected.extend(values[:count])
    selected.sort(key=lambda item: canonical_hash(item.record_id, prefix="v09_cohort_order:"))
    return tuple(selected)


def _bounded_weighted_allocation(
    total: int,
    capacities: Mapping[str, int],
    weights: Mapping[str, float],
) -> dict[str, int]:
    if total > sum(capacities.values()):
        raise ValueError("weighted selection capacity is below the requested total")
    selected = {cell_id: 0 for cell_id in capacities}
    for _ in range(total):
        available = [
            cell_id
            for cell_id, capacity in capacities.items()
            if selected[cell_id] < capacity and weights.get(cell_id, 0) > 0
        ]
        if not available:
            raise ValueError("positive-weight cell capacity cannot satisfy policy quota")
        cell_id = min(
            available,
            key=lambda item: (
                (selected[item] + 1) / weights[item],
                item,
            ),
        )
        selected[cell_id] += 1
    return {key: value for key, value in sorted(selected.items()) if value}


def _require_pool_capacity(
    records: tuple[SFTRecord, ...],
    quotas: Mapping[str, int],
    *,
    label: str,
) -> None:
    counts = Counter(item.domain for item in records)
    shortfalls = {
        domain: f"{counts[domain]}<{quota}"
        for domain, quota in quotas.items()
        if counts[domain] < quota
    }
    if shortfalls:
        raise ValueError(f"{label} has domain shortfalls: {shortfalls}")


def _complete_domain_counts(records: Iterable[SFTRecord]) -> dict[str, int]:
    counts = Counter(item.domain for item in records)
    return {domain: counts[domain] for domain in ("finance", "legal", "science")}


def _cohort_manifest(
    cohort: V09Cohort,
    records: tuple[SFTRecord, ...],
    *,
    selection_policy_id: str,
    eligible_source_records: tuple[SFTRecord, ...],
    accepted_real_link_count: int,
    real_feedback_link_count: int = 0,
    eligible_source_pool_hash: str | None = None,
    materialization_report: SynthesisMaterializationReport | None = None,
) -> V09CohortDatasetManifest:
    cell_counts = Counter(
        str(item.metadata.get("synthesis_cell_id") or _record_cell(item).cell_id)
        for item in records
    )
    source_pool_hash = eligible_source_pool_hash or canonical_hash(
        tuple((item.task_id, item.record_hash) for item in eligible_source_records),
        prefix="training_utility_v09_source_pool:",
    )
    policy_hash = canonical_hash(
        {
            "selection_policy_id": selection_policy_id,
            "cell_counts": dict(sorted(cell_counts.items())),
            "source_pool_hash": source_pool_hash,
            "materialization_report_id": (
                materialization_report.report_id if materialization_report is not None else None
            ),
        },
        prefix="training_utility_v09_selection_policy:",
    )
    return V09CohortDatasetManifest(
        cohort=cohort,
        record_count=len(records),
        domain_counts=_complete_domain_counts(records),
        source_kind_counts=dict(sorted(Counter(item.source_kind for item in records).items())),
        pattern_counts=dict(
            sorted(
                Counter(
                    str(item.metadata.get("pattern_id") or "unknown") for item in records
                ).items()
            )
        ),
        synthesis_cell_counts=dict(sorted(cell_counts.items())),
        selection_policy_id=selection_policy_id,
        selection_policy_hash=policy_hash,
        eligible_source_record_count=len(eligible_source_records),
        eligible_source_domain_counts=_complete_domain_counts(eligible_source_records),
        eligible_source_pool_hash=source_pool_hash,
        accepted_real_link_count=accepted_real_link_count,
        real_feedback_link_count=real_feedback_link_count,
        materialization_mode=(
            "new_compilation" if materialization_report is not None else "selection"
        ),
        materialization_report=materialization_report,
        compiler_contract_hash=(
            materialization_report.compiler_contract_hash
            if materialization_report is not None
            else None
        ),
        record_ids=tuple(item.record_id for item in records),
        task_ids=tuple(item.task_id for item in records),
        dataset_hash=canonical_hash(
            tuple(item.record_hash for item in records),
            prefix="training_utility_cohort_dataset:",
        ),
    )


def _write_jsonl(path: Path, records: Iterable[SFTRecord]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in records:
            handle.write(
                json.dumps(item.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
            )
