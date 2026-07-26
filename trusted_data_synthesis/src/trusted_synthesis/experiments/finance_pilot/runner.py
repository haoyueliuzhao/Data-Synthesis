from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from statistics import mean
from typing import Any

from pydantic import BaseModel

from trusted_synthesis.core.evaluation.contracts import (
    ContractQualityAssessment,
    DecisionParityReport,
    QualityContract,
    QualityContractCompiler,
    QualityContractRuntime,
    compare_decisions,
)
from trusted_synthesis.core.evaluation.evaluator import (
    CandidateQualityEvaluator,
    ReferenceQualityEvaluator,
)
from trusted_synthesis.core.evaluation.schema import QualityAssessment, ReleaseDecision
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.release import (
    SplitPolicy,
    assign_split,
    build_release_manifest,
    select_candidate_release,
)
from trusted_synthesis.core.release.split import semantic_cluster_id
from trusted_synthesis.core.synthesis import (
    ProofCarryingSample,
    ProofCarryingSampleCompiler,
    ProofCertificate,
)
from trusted_synthesis.core.task.schema import VerifierRequirement
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.plugins import finance_plugin_set
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.quality_clauses import FinanceQualityClauseProvider
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.experiments.cross_domain_contract_suite import (
    run_cross_domain_contract_suite,
)
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.experiments.finance_pilot.mutations import (
    MutationCase,
    generate_mutations,
)
from trusted_synthesis.experiments.finance_pilot.sampler import (
    discover_bindings,
    sample_evidence,
)
from trusted_synthesis.experiments.finance_pilot.schema import FinancePilotConfig
from trusted_synthesis.experiments.finance_pilot.task_factory import (
    PilotTaskCase,
    build_task_cases,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime


def run_finance_pilot(
    adapter: FinanceArchiveAdapter,
    config: FinancePilotConfig,
    output_dir: Path,
) -> dict[str, Any]:
    inspection = adapter.inspect()
    if not inspection["compatible"]:
        raise ValueError(f"incompatible finance archive: {inspection['errors']}")
    output_dir.mkdir(parents=True, exist_ok=True)
    policy = FinanceSemanticPolicy()
    source_grounding_verifier = adapter.source_grounding_verifier()
    sample = sample_evidence(
        adapter,
        config,
        policy,
        source_grounding_verifier,
    )
    bindings = discover_bindings(sample.evidence, config)
    cases = build_task_cases(
        bindings,
        sample.evidence,
        distractors_per_task=config.distractors_per_task,
        hard_distractors_per_task=config.hard_distractors_per_task,
        hard_distractor_types=config.hard_distractor_types,
        task_synthesizer=FinanceTaskPlugin(
            allow_structured_claims=True,
            source_grounding_requirement=VerifierRequirement.REQUIRED,
        ),
    )

    reference_compiler = ReferenceWorkflowCompiler()
    candidate_generator = FinanceNumericCandidateGenerator()
    reference_evaluator = ReferenceQualityEvaluator(
        semantic_policy=policy,
        source_grounding_verifier=source_grounding_verifier,
    )
    registry = default_registry()
    plugin_set = finance_plugin_set(adapter, registry, source_grounding_verifier)
    quality_contract_compiler = QualityContractCompiler(
        registry,
        domain_provider=FinanceQualityClauseProvider(),
    )
    proof_compiler = ProofCarryingSampleCompiler(
        registry,
        quality_contract_compiler,
        plugin_set,
        semantic_policy=policy,
        source_grounding_verifier=source_grounding_verifier,
    )
    candidate_workflow_verifier = CandidateWorkflowVerifier(
        registry,
        semantic_policy=policy,
        claim_verifier=FinanceClaimVerifier(),
        source_grounding_verifier=source_grounding_verifier,
    )
    candidate_evaluator = CandidateQualityEvaluator(
        semantic_policy=policy,
        claim_verifier=FinanceClaimVerifier(),
        source_grounding_verifier=source_grounding_verifier,
        workflow_verifier=candidate_workflow_verifier,
    )
    contract_runtime = QualityContractRuntime(
        candidate_workflow_verifier,
        verifier_registry=quality_contract_compiler.verifier_registry,
    )
    references: list[Trajectory] = []
    reference_assessments: list[QualityAssessment] = []
    clean_candidates: list[Trajectory] = []
    clean_assessments: list[QualityAssessment] = []
    mutation_cases: list[MutationCase] = []
    mutation_assessments: list[QualityAssessment] = []
    proof_samples: list[ProofCarryingSample] = []
    quality_contracts: list[QualityContract] = []
    proof_certificates: list[ProofCertificate] = []
    clean_contract_assessments: list[ContractQualityAssessment] = []
    mutation_contract_assessments: list[ContractQualityAssessment] = []
    decision_parities: list[DecisionParityReport] = []
    candidate_records = []

    for case in cases:
        reference = reference_compiler.compile(case.task, case.bundle)
        reference_assessment = reference_evaluator.evaluate(
            case.task, case.bundle, case.proof_graph, reference
        )
        compiled = proof_compiler.compile(
            case.task,
            case.bundle,
            case.proof_graph,
            pattern_id=case.task.public.task_type,
            binding_id=case.binding.binding_hash,
            reference_trajectory=reference,
            reference_assessment=reference_assessment,
        )
        candidate = candidate_generator.generate(
            case.task.public,
            InMemoryEvidenceToolRuntime(case.corpus),
        )
        candidate_assessment = candidate_evaluator.evaluate(
            case.task, case.corpus, case.proof_graph, candidate
        )
        contract_assessment = contract_runtime.evaluate(
            compiled.quality_contract,
            case.task,
            case.corpus,
            case.proof_graph,
            candidate,
        )
        references.append(reference)
        reference_assessments.append(reference_assessment)
        clean_candidates.append(candidate)
        clean_assessments.append(candidate_assessment)
        proof_samples.append(compiled.sample)
        quality_contracts.append(compiled.quality_contract)
        proof_certificates.append(compiled.sample.certificate)
        clean_contract_assessments.append(contract_assessment)
        decision_parities.append(compare_decisions(candidate_assessment, contract_assessment))
        candidate_records.append((case.task, candidate, candidate_assessment))
        for mutation in generate_mutations(case, candidate, config.mutation_types):
            assessment = candidate_evaluator.evaluate(
                case.task,
                case.corpus,
                case.proof_graph,
                mutation.trajectory,
            )
            contract_assessment = contract_runtime.evaluate(
                compiled.quality_contract,
                case.task,
                case.corpus,
                case.proof_graph,
                mutation.trajectory,
            )
            mutation_cases.append(mutation)
            mutation_assessments.append(assessment)
            mutation_contract_assessments.append(contract_assessment)
            decision_parities.append(compare_decisions(assessment, contract_assessment))
            candidate_records.append((case.task, mutation.trajectory, assessment))

    split_policy = SplitPolicy(policy_id="finance_pilot_semantic_split.v1")
    selection = select_candidate_release(candidate_records, split_policy)
    cross_domain_contracts = run_cross_domain_contract_suite()
    release_plugin_sets = (
        plugin_set,
        *cross_domain_contracts.plugin_sets,
    )
    release_id = canonical_hash(
        {
            "pilot_id": config.pilot_id,
            "config_hash": config.config_hash,
            "kg_build_id": inspection["kg_build_id"],
            "task_ids": sorted(case.task.task_id for case in cases),
        },
        prefix="finance_pilot_release:",
    )
    manifest = build_release_manifest(
        release_id=release_id,
        tasks=(case.task for case in cases),
        adapters=(adapter,),
        registry=registry,
        split_policy=split_policy,
        source_build_ids={"finance_kg": str(inspection["kg_build_id"])},
        candidate_selection=selection,
        domain_plugin_sets=release_plugin_sets,
        source_grounding_verifiers=(source_grounding_verifier,),
        cross_domain_contract_suite=cross_domain_contracts.result,
        quality_contracts=quality_contracts,
        proof_certificates=proof_certificates,
    )
    reproducibility = _reproducibility_check(
        cases=cases,
        config=config,
        reference_compiler=reference_compiler,
        candidate_generator=candidate_generator,
        reference_evaluator=reference_evaluator,
        candidate_evaluator=candidate_evaluator,
        references=references,
        reference_assessments=reference_assessments,
        clean_candidates=clean_candidates,
        clean_assessments=clean_assessments,
        mutation_cases=mutation_cases,
        selection_id=selection.selection_id,
        manifest_hash=manifest.manifest_hash,
        adapter=adapter,
        split_policy=split_policy,
        release_id=release_id,
        inspection=inspection,
        candidate_records=candidate_records,
        proof_compiler=proof_compiler,
        quality_contracts=quality_contracts,
        proof_certificates=proof_certificates,
    )
    report = _build_report(
        inspection=inspection,
        config=config,
        sample=sample,
        cases=cases,
        references=references,
        reference_assessments=reference_assessments,
        clean_candidates=clean_candidates,
        clean_assessments=clean_assessments,
        mutation_cases=mutation_cases,
        mutation_assessments=mutation_assessments,
        selection=selection,
        manifest=manifest,
        split_policy=split_policy,
        reproducibility=reproducibility,
        proof_samples=proof_samples,
        quality_contracts=quality_contracts,
        proof_certificates=proof_certificates,
        clean_contract_assessments=clean_contract_assessments,
        mutation_contract_assessments=mutation_contract_assessments,
        decision_parities=decision_parities,
    )
    _write_artifacts(
        output_dir=output_dir,
        config=config,
        cases=cases,
        references=references,
        reference_assessments=reference_assessments,
        clean_candidates=clean_candidates,
        clean_assessments=clean_assessments,
        mutation_cases=mutation_cases,
        mutation_assessments=mutation_assessments,
        manifest=manifest,
        report=report,
        proof_samples=proof_samples,
        quality_contracts=quality_contracts,
        clean_contract_assessments=clean_contract_assessments,
        mutation_contract_assessments=mutation_contract_assessments,
        decision_parities=decision_parities,
    )
    return report


def _build_report(
    *,
    inspection: dict[str, Any],
    config: FinancePilotConfig,
    sample: Any,
    cases: tuple[PilotTaskCase, ...],
    references: list[Trajectory],
    reference_assessments: list[QualityAssessment],
    clean_candidates: list[Trajectory],
    clean_assessments: list[QualityAssessment],
    mutation_cases: list[MutationCase],
    mutation_assessments: list[QualityAssessment],
    selection: Any,
    manifest: Any,
    split_policy: SplitPolicy,
    reproducibility: dict[str, bool],
    proof_samples: list[ProofCarryingSample],
    quality_contracts: list[QualityContract],
    proof_certificates: list[ProofCertificate],
    clean_contract_assessments: list[ContractQualityAssessment],
    mutation_contract_assessments: list[ContractQualityAssessment],
    decision_parities: list[DecisionParityReport],
) -> dict[str, Any]:
    task_counts = Counter(case.task.public.task_type for case in cases)
    region_counts = Counter(case.binding.stratum[0] for case in cases)
    metric_category_counts = Counter(case.binding.stratum[1] for case in cases)
    frequency_counts = Counter(case.binding.stratum[2] for case in cases)
    source_counts = Counter(case.binding.stratum[3] for case in cases)
    verification_status_counts = Counter(case.binding.stratum[4] for case in cases)
    program_depths = Counter(len(case.task.oracle.task_program.nodes) for case in cases)
    reference_accepted = sum(
        assessment.decision == ReleaseDecision.ACCEPTED for assessment in reference_assessments
    )
    clean_accepted = sum(
        assessment.decision == ReleaseDecision.ACCEPTED for assessment in clean_assessments
    )
    mutation_rejected = sum(
        assessment.decision == ReleaseDecision.REJECTED for assessment in mutation_assessments
    )
    false_acceptances = len(mutation_assessments) - mutation_rejected
    false_rejections = len(clean_assessments) - clean_accepted
    per_type = _mutation_metrics(mutation_cases, mutation_assessments)
    per_family = _mutation_family_metrics(mutation_cases, mutation_assessments)
    localization_values = [
        set(mutation.expected_failure_gates).issubset(assessment.fatal_failures)
        for mutation, assessment in zip(mutation_cases, mutation_assessments, strict=True)
    ]
    check_localization_values = [
        set(mutation.expected_failure_checks).issubset(assessment.failed_check_ids)
        for mutation, assessment in zip(mutation_cases, mutation_assessments, strict=True)
    ]
    detail_localization_values = [
        set(mutation.expected_detail_tokens).issubset(
            {detail for details in assessment.check_failure_details.values() for detail in details}
        )
        for mutation, assessment in zip(mutation_cases, mutation_assessments, strict=True)
        if mutation.expected_detail_tokens
    ]
    hard_retrieval_values = []
    hard_selection_count = 0
    for case, candidate in zip(cases, clean_candidates, strict=True):
        retrieved = {
            evidence_id
            for step in candidate.steps
            if step.action.value == "search"
            for evidence_id in step.evidence_ids
        }
        selected = {
            evidence_id
            for step in candidate.steps
            if step.action.value == "select_evidence"
            for evidence_id in step.evidence_ids
        }
        hard_retrieval_values.append(set(case.hard_distractor_ids).issubset(retrieved))
        hard_selection_count += len(selected & set(case.hard_distractor_ids))
    split_clusters: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        split_clusters[semantic_cluster_id(case.task, split_policy)].add(
            assign_split(case.task, split_policy).value
        )
    leakage_count = sum(len(values) > 1 for values in split_clusters.values())
    error_precision, error_recall, error_f1 = _binary_detection_metrics(
        clean_assessments,
        mutation_assessments,
    )
    reference_rate = _rate(reference_accepted, len(reference_assessments))
    clean_rate = _rate(clean_accepted, len(clean_assessments))
    far = _rate(false_acceptances, len(mutation_assessments))
    far_95_upper = (
        1 - 0.05 ** (1 / len(mutation_assessments))
        if mutation_assessments and false_acceptances == 0
        else None
    )
    localization_rate = _rate(sum(localization_values), len(localization_values))
    check_localization_rate = _rate(sum(check_localization_values), len(check_localization_values))
    detail_localization_rate = _rate(
        sum(detail_localization_values), len(detail_localization_values)
    )
    macro_detection = (
        mean(item["detection_rate"] for item in per_type.values()) if per_type else 0.0
    )
    theoretical_mutations = len(cases) * len(config.mutation_types)
    parity_matches = sum(item.decisions_match for item in decision_parities)
    parity_rate = _rate(parity_matches, len(decision_parities))
    contract_clean_accepted = sum(
        item.decision == ReleaseDecision.ACCEPTED for item in clean_contract_assessments
    )
    contract_mutation_rejected = sum(
        item.decision == ReleaseDecision.REJECTED for item in mutation_contract_assessments
    )
    coverage_warnings = []
    if not region_counts.get("mainland_hong_kong_macau"):
        coverage_warnings.append(
            "No mainland/Hong Kong/Macau task was available in the pinned KG build."
        )
    if len(source_counts) < 4:
        coverage_warnings.append("The pilot task pool covers fewer than four source systems.")
    coverage_warnings.extend(
        (
            "No live model candidate or human-alignment judgment was evaluated.",
            "Resolved retrieval does not validate open search or entity disambiguation.",
        )
    )
    thresholds = {
        "full_task_quota": len(cases) == sum(config.task_quotas.values()),
        "reference_acceptance_rate_gte_0_995": reference_rate >= 0.995,
        "clean_candidate_acceptance_rate_gte_0_95": clean_rate >= 0.95,
        "critical_false_acceptance_rate_lte_0_01": far <= 0.01,
        "observed_zero_far_95_upper_lte_0_01": (far_95_upper is not None and far_95_upper <= 0.01),
        "mutation_macro_detection_rate_gte_0_90": macro_detection >= 0.90,
        "failure_localization_rate_gte_0_90": localization_rate >= 0.90,
        "check_localization_rate_gte_0_90": check_localization_rate >= 0.90,
        "step_or_node_localization_rate_gte_0_90": detail_localization_rate >= 0.90,
        "hard_distractors_retrieved_and_rejected": (
            all(hard_retrieval_values) and hard_selection_count == 0
        ),
        "hash_stability": all(reproducibility.values()),
        "split_semantic_leakage_zero": leakage_count == 0,
        "release_contains_only_clean_accepted": (
            len(selection.accepted_trajectory_ids) == clean_accepted
        ),
        "proof_carrying_sample_coverage": len(proof_samples) == len(cases),
        "quality_contract_coverage": len(quality_contracts) == len(cases),
        "proof_certificate_coverage": len(proof_certificates) == len(cases),
        "contract_runtime_decision_parity": parity_rate == 1,
    }
    return {
        "pilot_id": config.pilot_id,
        "pilot_config_hash": config.config_hash,
        "architecture_feasible": all(thresholds.values()),
        "production_ready": False,
        "feasibility_scope": "global_financial_numeric_resolved_track",
        "coverage_warnings": coverage_warnings,
        "thresholds": thresholds,
        "archive": {
            "adapter_id": inspection["adapter_id"],
            "kg_build_id": inspection["kg_build_id"],
            "graph_schema_version": inspection["graph_schema_version"],
            "quality_gate_status": inspection["quality_gate_status"],
            "read_only": inspection["read_only"],
            "fact_node_count": inspection["fact_node_count"],
            "node_count": inspection["node_count"],
            "edge_count": inspection["edge_count"],
        },
        "evidence_mapping": {
            "scanned_count": sample.scanned_count,
            "domain_valid_count": sample.domain_valid_count,
            "domain_rejected_count": sample.rejected_count,
            "domain_valid_rate": _rate(sample.domain_valid_count, sample.scanned_count),
            "observed_stratum_count": len(sample.stratum_counts),
            "sampled_count": sample.sampled_count,
            "sampled_stratum_count": len(sample.sampled_stratum_counts),
            "complete_stream_scan": sample.complete_stream_scan,
            "source_grounding_checked_count": sample.source_grounding_checked_count,
            "source_grounding_valid_count": sample.source_grounding_valid_count,
            "source_grounding_rejected_count": sample.source_grounding_rejected_count,
            "source_grounding_valid_rate": _rate(
                sample.source_grounding_valid_count,
                sample.source_grounding_checked_count,
            ),
            "source_grounding_failure_counts": sample.source_grounding_failure_counts,
            "source_grounding_rejected_source_counts": (
                sample.source_grounding_rejected_source_counts
            ),
        },
        "task_synthesis": {
            "requested_count": sum(config.task_quotas.values()),
            "compiled_count": len(cases),
            "compilation_rate": _rate(len(cases), sum(config.task_quotas.values())),
            "task_type_counts": dict(sorted(task_counts.items())),
            "region_counts": dict(sorted(region_counts.items())),
            "metric_category_counts": dict(sorted(metric_category_counts.items())),
            "frequency_counts": dict(sorted(frequency_counts.items())),
            "source_counts": dict(sorted(source_counts.items())),
            "verification_status_counts": dict(sorted(verification_status_counts.items())),
            "program_depth_counts": {
                str(key): value for key, value in sorted(program_depths.items())
            },
            "minimum_distractors": min((len(case.distractor_ids) for case in cases), default=0),
            "mean_distractors": (mean(len(case.distractor_ids) for case in cases) if cases else 0),
            "minimum_hard_distractors": min(
                (len(case.hard_distractor_ids) for case in cases), default=0
            ),
            "mean_hard_distractors": (
                mean(len(case.hard_distractor_ids) for case in cases) if cases else 0
            ),
            "hard_distractor_kind_counts": dict(
                sorted(
                    Counter(
                        kind for case in cases for kind in case.distractor_kinds.values()
                    ).items()
                )
            ),
            "hard_distractor_retrieval_rate": _rate(
                sum(hard_retrieval_values), len(hard_retrieval_values)
            ),
            "selected_hard_distractor_count": hard_selection_count,
        },
        "reference_validation": {
            "attempted": len(references),
            "accepted": reference_accepted,
            "acceptance_rate": reference_rate,
        },
        "candidate_validation": {
            "clean_attempted": len(clean_candidates),
            "clean_accepted": clean_accepted,
            "clean_acceptance_rate": clean_rate,
            "false_rejection_count": false_rejections,
            "false_rejection_rate": _rate(false_rejections, len(clean_assessments)),
            "mutation_attempted": len(mutation_cases),
            "mutation_theoretical_attempts": theoretical_mutations,
            "mutation_generation_rate": _rate(len(mutation_cases), theoretical_mutations),
            "mutation_generation_shortfall": theoretical_mutations - len(mutation_cases),
            "mutation_rejected": mutation_rejected,
            "false_acceptance_count": false_acceptances,
            "critical_false_acceptance_rate": far,
            "zero_failure_one_sided_95_far_upper": far_95_upper,
            "error_detection_precision": error_precision,
            "error_detection_recall": error_recall,
            "error_detection_f1": error_f1,
            "failure_localization_rate": localization_rate,
            "check_localization_rate": check_localization_rate,
            "step_or_node_localization_rate": detail_localization_rate,
            "step_or_node_localization_count": len(detail_localization_values),
            "macro_detection_rate": macro_detection,
            "per_mutation_type": per_type,
            "per_generic_mutation_family": per_family,
        },
        "proof_carrying_quality_contract": {
            "proof_sample_count": len(proof_samples),
            "quality_contract_count": len(quality_contracts),
            "proof_certificate_count": len(proof_certificates),
            "contract_clause_count_min": min(
                (len(item.clauses) for item in quality_contracts), default=0
            ),
            "contract_clause_count_max": max(
                (len(item.clauses) for item in quality_contracts), default=0
            ),
            "contract_clean_accepted": contract_clean_accepted,
            "contract_mutation_rejected": contract_mutation_rejected,
            "dual_track_evaluation_count": len(decision_parities),
            "dual_track_decision_match_count": parity_matches,
            "dual_track_decision_parity_rate": parity_rate,
            "quality_contract_compiler_versions": sorted(
                {item.compiler_version for item in quality_contracts}
            ),
            "proof_compiler_versions": sorted(
                {item.compiler_version for item in proof_certificates}
            ),
            "clause_verifier_manifest_hashes": sorted(
                {item.verifier_manifest_hash for item in quality_contracts}
            ),
        },
        "release": {
            "release_id": manifest.release_id,
            "release_manifest_hash": manifest.manifest_hash,
            "accepted_candidate_count": len(selection.accepted_trajectory_ids),
            "failure_distribution": selection.failure_distribution,
            "split_counts": selection.split_counts,
            "semantic_leakage_count": leakage_count,
            "generalization_contract": manifest.metadata,
        },
        "reproducibility": reproducibility,
        "current_boundaries": [
            "resolved retrieval track only",
            "deterministic candidate generator rather than a live LLM agent",
            "no human alignment sample in this small pilot",
            "advanced ratio comparison and multi-entity growth DAGs remain future work",
            "cross-domain contracts run in CI, outside this finance-only pilot",
        ],
    }


def _mutation_metrics(
    mutations: list[MutationCase],
    assessments: list[QualityAssessment],
) -> dict[str, dict[str, Any]]:
    rows: dict[str, list[tuple[MutationCase, QualityAssessment]]] = defaultdict(list)
    for mutation, assessment in zip(mutations, assessments, strict=True):
        rows[mutation.mutation_type].append((mutation, assessment))
    output = {}
    for mutation_type, items in sorted(rows.items()):
        rejected = sum(assessment.decision == ReleaseDecision.REJECTED for _, assessment in items)
        localized = sum(
            set(mutation.expected_failure_gates).issubset(assessment.fatal_failures)
            for mutation, assessment in items
        )
        output[mutation_type] = {
            "count": len(items),
            "rejected": rejected,
            "detection_rate": _rate(rejected, len(items)),
            "localized": localized,
            "localization_rate": _rate(localized, len(items)),
            "check_localized": sum(
                set(mutation.expected_failure_checks).issubset(assessment.failed_check_ids)
                for mutation, assessment in items
            ),
            "check_localization_rate": _rate(
                sum(
                    set(mutation.expected_failure_checks).issubset(assessment.failed_check_ids)
                    for mutation, assessment in items
                ),
                len(items),
            ),
        }
    return output


def _mutation_family_metrics(
    mutations: list[MutationCase],
    assessments: list[QualityAssessment],
) -> dict[str, dict[str, Any]]:
    rows: dict[str, list[QualityAssessment]] = defaultdict(list)
    for mutation, assessment in zip(mutations, assessments, strict=True):
        rows[mutation.mutation_family.value].append(assessment)
    return {
        family: {
            "count": len(items),
            "rejected": sum(item.decision == ReleaseDecision.REJECTED for item in items),
            "detection_rate": _rate(
                sum(item.decision == ReleaseDecision.REJECTED for item in items),
                len(items),
            ),
        }
        for family, items in sorted(rows.items())
    }


def _binary_detection_metrics(
    clean: list[QualityAssessment],
    mutated: list[QualityAssessment],
) -> tuple[float, float, float]:
    true_positive = sum(item.decision == ReleaseDecision.REJECTED for item in mutated)
    false_negative = len(mutated) - true_positive
    false_positive = sum(item.decision != ReleaseDecision.ACCEPTED for item in clean)
    precision = _rate(true_positive, true_positive + false_positive)
    recall = _rate(true_positive, true_positive + false_negative)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def _reproducibility_check(
    *,
    cases: tuple[PilotTaskCase, ...],
    config: FinancePilotConfig,
    reference_compiler: ReferenceWorkflowCompiler,
    candidate_generator: FinanceNumericCandidateGenerator,
    reference_evaluator: ReferenceQualityEvaluator,
    candidate_evaluator: CandidateQualityEvaluator,
    references: list[Trajectory],
    reference_assessments: list[QualityAssessment],
    clean_candidates: list[Trajectory],
    clean_assessments: list[QualityAssessment],
    mutation_cases: list[MutationCase],
    selection_id: str,
    manifest_hash: str,
    adapter: FinanceArchiveAdapter,
    split_policy: SplitPolicy,
    release_id: str,
    inspection: dict[str, Any],
    candidate_records: list[Any],
    proof_compiler: ProofCarryingSampleCompiler,
    quality_contracts: list[QualityContract],
    proof_certificates: list[ProofCertificate],
) -> dict[str, bool]:
    replay_references: list[Trajectory] = []
    replay_reference_assessments: list[QualityAssessment] = []
    replay_candidates: list[Trajectory] = []
    replay_candidate_assessments: list[QualityAssessment] = []
    replay_mutation_ids: list[str] = []
    replay_quality_contracts: list[QualityContract] = []
    replay_proof_certificates: list[ProofCertificate] = []
    for case in cases:
        reference = reference_compiler.compile(case.task, case.bundle)
        candidate = candidate_generator.generate(
            case.task.public, InMemoryEvidenceToolRuntime(case.corpus)
        )
        replay_references.append(reference)
        reference_assessment = reference_evaluator.evaluate(
            case.task, case.bundle, case.proof_graph, reference
        )
        replay_reference_assessments.append(reference_assessment)
        compiled = proof_compiler.compile(
            case.task,
            case.bundle,
            case.proof_graph,
            pattern_id=case.task.public.task_type,
            binding_id=case.binding.binding_hash,
            reference_trajectory=reference,
            reference_assessment=reference_assessment,
        )
        replay_quality_contracts.append(compiled.quality_contract)
        replay_proof_certificates.append(compiled.sample.certificate)
        replay_candidates.append(candidate)
        replay_candidate_assessments.append(
            candidate_evaluator.evaluate(case.task, case.corpus, case.proof_graph, candidate)
        )
        replay_mutation_ids.extend(
            mutation.mutation_id
            for mutation in generate_mutations(case, candidate, config.mutation_types)
        )
    selection_replay = select_candidate_release(candidate_records, split_policy)
    replay_source_grounding = adapter.source_grounding_verifier()
    replay_registry = default_registry()
    replay_cross_domain_contracts = run_cross_domain_contract_suite()
    manifest_replay = build_release_manifest(
        release_id=release_id,
        tasks=(case.task for case in cases),
        adapters=(adapter,),
        registry=replay_registry,
        split_policy=split_policy,
        source_build_ids={"finance_kg": str(inspection["kg_build_id"])},
        candidate_selection=selection_replay,
        domain_plugin_sets=(
            finance_plugin_set(adapter, replay_registry, replay_source_grounding),
            *replay_cross_domain_contracts.plugin_sets,
        ),
        source_grounding_verifiers=(replay_source_grounding,),
        cross_domain_contract_suite=replay_cross_domain_contracts.result,
        quality_contracts=replay_quality_contracts,
        proof_certificates=replay_proof_certificates,
    )
    return {
        "reference_trajectory_ids": [item.trajectory_id for item in references]
        == [item.trajectory_id for item in replay_references],
        "reference_assessment_ids": [item.assessment_id for item in reference_assessments]
        == [item.assessment_id for item in replay_reference_assessments],
        "candidate_trajectory_ids": [item.trajectory_id for item in clean_candidates]
        == [item.trajectory_id for item in replay_candidates],
        "candidate_assessment_ids": [item.assessment_id for item in clean_assessments]
        == [item.assessment_id for item in replay_candidate_assessments],
        "mutation_ids": [item.mutation_id for item in mutation_cases] == replay_mutation_ids,
        "quality_contract_hashes": [item.contract_hash for item in quality_contracts]
        == [item.contract_hash for item in replay_quality_contracts],
        "proof_certificate_hashes": [item.certificate_hash for item in proof_certificates]
        == [item.certificate_hash for item in replay_proof_certificates],
        "candidate_selection_id": selection_id == selection_replay.selection_id,
        "release_manifest_hash": manifest_hash == manifest_replay.manifest_hash,
    }


def _write_artifacts(
    *,
    output_dir: Path,
    config: FinancePilotConfig,
    cases: tuple[PilotTaskCase, ...],
    references: list[Trajectory],
    reference_assessments: list[QualityAssessment],
    clean_candidates: list[Trajectory],
    clean_assessments: list[QualityAssessment],
    mutation_cases: list[MutationCase],
    mutation_assessments: list[QualityAssessment],
    manifest: Any,
    report: dict[str, Any],
    proof_samples: list[ProofCarryingSample],
    quality_contracts: list[QualityContract],
    clean_contract_assessments: list[ContractQualityAssessment],
    mutation_contract_assessments: list[ContractQualityAssessment],
    decision_parities: list[DecisionParityReport],
) -> None:
    config.write(output_dir / "config.json")
    _write_jsonl(output_dir / "task_packages.jsonl", (case.task for case in cases))
    _write_jsonl(
        output_dir / "task_contexts.jsonl",
        (
            {
                "task_id": case.task.task_id,
                "binding_hash": case.binding.binding_hash,
                "binding_stratum": case.binding.stratum,
                "bundle": case.bundle,
                "proof_graph": case.proof_graph,
                "corpus_id": case.corpus.corpus_id,
                "distractor_ids": case.distractor_ids,
            }
            for case in cases
        ),
    )
    _write_jsonl(output_dir / "reference_workflows.jsonl", references)
    _write_jsonl(output_dir / "reference_assessments.jsonl", reference_assessments)
    _write_jsonl(output_dir / "proof_carrying_samples.jsonl", proof_samples)
    _write_jsonl(output_dir / "quality_contracts.jsonl", quality_contracts)
    _write_jsonl(output_dir / "clean_candidate_workflows.jsonl", clean_candidates)
    _write_jsonl(output_dir / "clean_candidate_assessments.jsonl", clean_assessments)
    _write_jsonl(
        output_dir / "clean_contract_assessments.jsonl", clean_contract_assessments
    )
    _write_jsonl(
        output_dir / "mutated_candidate_workflows.jsonl",
        (
            {
                "mutation_id": mutation.mutation_id,
                "mutation_type": mutation.mutation_type,
                "mutation_family": mutation.mutation_family.value,
                "source_trajectory_id": mutation.source_trajectory_id,
                "expected_failure_gates": mutation.expected_failure_gates,
                "expected_failure_checks": mutation.expected_failure_checks,
                "expected_detail_tokens": mutation.expected_detail_tokens,
                "trajectory": mutation.trajectory,
                "assessment": assessment,
            }
            for mutation, assessment in zip(mutation_cases, mutation_assessments, strict=True)
        ),
    )
    _write_jsonl(
        output_dir / "mutated_contract_assessments.jsonl",
        mutation_contract_assessments,
    )
    _write_jsonl(output_dir / "decision_parity.jsonl", decision_parities)
    _write_json(output_dir / "release_manifest.json", manifest)
    _write_json(output_dir / "pilot_report.json", report)
    (output_dir / "pilot_report.md").write_text(
        _markdown_report(report),
        encoding="utf-8",
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(_json_value(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: Iterable[Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True) + "\n")


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _markdown_report(report: dict[str, Any]) -> str:
    task = report["task_synthesis"]
    candidate = report["candidate_validation"]
    reference = report["reference_validation"]
    release = report["release"]
    lines = [
        "# Finance Synthesis Pilot Report",
        "",
        f"- Architecture feasible: **{report['architecture_feasible']}**",
        f"- KG build: {report['archive']['kg_build_id']}",
        f"- Evidence scanned: {report['evidence_mapping']['scanned_count']:,}",
        f"- Tasks compiled: {task['compiled_count']} / {task['requested_count']}",
        f"- Reference accepted: {reference['accepted']} / {reference['attempted']}",
        (
            f"- Clean candidates accepted: {candidate['clean_accepted']} / "
            f"{candidate['clean_attempted']}"
        ),
        (
            f"- Mutated candidates rejected: {candidate['mutation_rejected']} / "
            f"{candidate['mutation_attempted']}"
        ),
        (f"- Critical false acceptance rate: {candidate['critical_false_acceptance_rate']:.4%}"),
        f"- Failure localization rate: {candidate['failure_localization_rate']:.4%}",
        f"- Split semantic leakage: {release['semantic_leakage_count']}",
        "",
        "## Task Distribution",
        "",
        json.dumps(task["task_type_counts"], ensure_ascii=False, indent=2),
        "",
        "## Mutation Detection",
        "",
        json.dumps(candidate["per_mutation_type"], ensure_ascii=False, indent=2),
        "",
        "## Thresholds",
        "",
    ]
    lines.extend(
        f"- [{'x' if passed else ' '}] {name}" for name, passed in report["thresholds"].items()
    )
    lines.extend(
        [
            "",
            "## Current Boundaries",
            "",
            *(f"- {item}" for item in report["current_boundaries"]),
            "",
        ]
    )
    return "\n".join(lines)


def _rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator
