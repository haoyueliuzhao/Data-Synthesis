from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from trusted_synthesis.architecture.generalization import audit_generalization_contract
from trusted_synthesis.core.evaluation.contracts import (
    QualityContractCompiler,
    QualityContractRuntime,
)
from trusted_synthesis.core.evaluation.evaluator import (
    CandidateQualityEvaluator,
    ReferenceQualityEvaluator,
)
from trusted_synthesis.core.evaluation.utility import UtilityCohort
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.release import (
    SplitPolicy,
    assign_split,
    build_release_manifest,
    select_candidate_release,
)
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.task.schema import VerifierRequirement
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.plugins import finance_plugin_set
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.quality_clauses import FinanceQualityClauseProvider
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.experiments.agent_validation import (
    AgentValidationConfig,
    audit_agent_validation_capacity,
    run_agent_validation,
    write_agent_validation_artifacts,
)
from trusted_synthesis.experiments.counterfactual_validation import (
    run_counterfactual_validation,
)
from trusted_synthesis.experiments.cross_domain_contract_suite import (
    run_cross_domain_contract_suite,
)
from trusted_synthesis.experiments.finance_pilot import (
    FinancePilotConfig,
    run_finance_pilot,
)
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.experiments.task_pattern_validation import (
    run_task_pattern_validation,
)
from trusted_synthesis.experiments.training_utility_mvp import (
    TrainingUtilityDataManifest,
    TrainingUtilityMVPConfig,
    audit_training_utility_readiness,
    build_training_utility_datasets,
    build_training_utility_report,
    evaluate_sft_model,
    load_agent_artifacts,
    load_evaluation_result,
    load_training_result,
    train_sft_cohort,
    write_reference_training_preflight,
    write_training_utility_datasets,
    write_training_utility_report,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime import (
    InMemoryEvidenceToolRuntime,
    OpenAICompatibleJsonClient,
)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "audit-generalization":
        _emit(
            audit_generalization_contract(args.source_root).model_dump(mode="json"),
            args.output,
        )
        return 0
    if args.command == "validate-task-patterns":
        pattern_report = run_task_pattern_validation(tasks_per_domain=args.tasks_per_domain)
        _emit(pattern_report.model_dump(mode="json"), args.output)
        return 0 if pattern_report.status == "passed" else 1
    if args.command == "validate-counterfactuals":
        counterfactual_report = run_counterfactual_validation(
            tasks_per_domain=args.tasks_per_domain
        )
        _emit(counterfactual_report.model_dump(mode="json"), args.output)
        return 0 if counterfactual_report.status == "passed" else 1
    if args.command == "audit-agent-capacity":
        capacity_config = AgentValidationConfig.from_json(args.agent_config)
        capacity_report = audit_agent_validation_capacity(capacity_config)
        _emit(capacity_report.model_dump(mode="json"), args.output)
        return 0 if capacity_report.status == "ready" else 1
    if args.command == "validate-agents":
        agent_config = AgentValidationConfig.from_json(args.agent_config)
        agent_artifacts = run_agent_validation(
            agent_config,
            OpenAICompatibleJsonClient(agent_config.model),
            checkpoint_dir=args.output_dir / "checkpoints",
        )
        write_agent_validation_artifacts(agent_artifacts, args.output_dir)
        _emit(agent_artifacts.report.model_dump(mode="json"), args.output)
        return 0 if agent_artifacts.report.status == "completed" else 1
    if args.command == "prepare-training-utility":
        utility_config = TrainingUtilityMVPConfig.from_json(args.training_config)
        agent_report, critic_dataset = load_agent_artifacts(args.agent_artifacts)
        cohorts, evaluation, manifest = build_training_utility_datasets(
            utility_config,
            agent_report,
            critic_dataset,
        )
        write_training_utility_datasets(args.output_dir, cohorts, evaluation, manifest)
        _emit(manifest.model_dump(mode="json"), args.output)
        return 0
    if args.command == "audit-training-utility-readiness":
        utility_config = TrainingUtilityMVPConfig.from_json(args.training_config)
        agent_report, critic_dataset = load_agent_artifacts(args.agent_artifacts)
        readiness = audit_training_utility_readiness(
            utility_config,
            agent_report,
            critic_dataset,
        )
        _emit(readiness.model_dump(mode="json"), args.output)
        return 0 if readiness.status == "ready" else 1
    if args.command == "prepare-training-utility-reference":
        utility_config = TrainingUtilityMVPConfig.from_json(args.training_config)
        preflight_manifest = write_reference_training_preflight(
            utility_config,
            args.output_dir,
        )
        _emit(preflight_manifest, args.output)
        return 0
    if args.command == "train-training-utility":
        utility_config = TrainingUtilityMVPConfig.from_json(args.training_config)
        training_result = train_sft_cohort(
            utility_config,
            UtilityCohort(args.cohort),
            args.dataset,
            args.output_dir,
        )
        _emit(training_result.model_dump(mode="json"), args.output)
        return 0
    if args.command == "evaluate-training-utility":
        utility_config = TrainingUtilityMVPConfig.from_json(args.training_config)
        evaluation_result = evaluate_sft_model(
            utility_config,
            args.cohort,
            args.evaluation_dataset,
            args.output_dir,
            adapter_dir=args.adapter_dir,
        )
        _emit(evaluation_result.model_dump(mode="json"), args.output)
        return 0
    if args.command == "summarize-training-utility":
        utility_config = TrainingUtilityMVPConfig.from_json(args.training_config)
        data_manifest = TrainingUtilityDataManifest.model_validate_json(
            args.data_manifest.read_text(encoding="utf-8")
        )
        utility_report = build_training_utility_report(
            utility_config,
            data_manifest,
            load_evaluation_result(args.base_evaluation),
            tuple(load_training_result(path) for path in args.training_result),
            tuple(load_evaluation_result(path) for path in args.cohort_evaluation),
        )
        write_training_utility_report(args.output_dir, utility_report, data_manifest)
        _emit(utility_report.model_dump(mode="json"), args.output)
        return 0
    adapter = FinanceArchiveAdapter(FinanceArchiveConfig.from_json(args.config))
    if args.command == "inspect-finance":
        _emit(adapter.inspect(), args.output)
        return 0
    if args.command == "sample-finance":
        records = [
            item.model_dump(mode="json", exclude_none=True)
            for item in adapter.iter_evidence(limit=args.limit)
        ]
        _emit({"count": len(records), "evidence": records}, args.output)
        return 0
    if args.command == "demo-finance":
        _emit(_demo(adapter, args.limit), args.output)
        return 0
    if args.command == "finance-pilot":
        finance_report = run_finance_pilot(
            adapter,
            FinancePilotConfig.from_json(args.pilot_config),
            args.output_dir,
        )
        _emit(finance_report, args.output)
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trusted-synthesis")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect-finance", "sample-finance", "demo-finance"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--config", required=True)
        subparser.add_argument("--output", type=Path)
        if command != "inspect-finance":
            subparser.add_argument("--limit", type=int, default=3)
    pilot = subparsers.add_parser("finance-pilot")
    pilot.add_argument("--config", required=True)
    pilot.add_argument("--pilot-config", required=True)
    pilot.add_argument("--output-dir", type=Path, required=True)
    pilot.add_argument("--output", type=Path)
    audit = subparsers.add_parser("audit-generalization")
    audit.add_argument("--source-root", type=Path, default=Path("src"))
    audit.add_argument("--output", type=Path)
    pattern_validation = subparsers.add_parser("validate-task-patterns")
    pattern_validation.add_argument("--tasks-per-domain", type=int, default=10)
    pattern_validation.add_argument("--output", type=Path)
    counterfactual_validation = subparsers.add_parser("validate-counterfactuals")
    counterfactual_validation.add_argument("--tasks-per-domain", type=int, default=10)
    counterfactual_validation.add_argument("--output", type=Path)
    agent_capacity = subparsers.add_parser("audit-agent-capacity")
    agent_capacity.add_argument("--agent-config", type=Path, required=True)
    agent_capacity.add_argument("--output", type=Path)
    agent_validation = subparsers.add_parser("validate-agents")
    agent_validation.add_argument("--agent-config", type=Path, required=True)
    agent_validation.add_argument("--output-dir", type=Path, required=True)
    agent_validation.add_argument("--output", type=Path)
    utility_prepare = subparsers.add_parser("prepare-training-utility")
    utility_prepare.add_argument("--training-config", type=Path, required=True)
    utility_prepare.add_argument("--agent-artifacts", type=Path, required=True)
    utility_prepare.add_argument("--output-dir", type=Path, required=True)
    utility_prepare.add_argument("--output", type=Path)
    utility_readiness = subparsers.add_parser("audit-training-utility-readiness")
    utility_readiness.add_argument("--training-config", type=Path, required=True)
    utility_readiness.add_argument("--agent-artifacts", type=Path, required=True)
    utility_readiness.add_argument("--output", type=Path)
    utility_reference = subparsers.add_parser("prepare-training-utility-reference")
    utility_reference.add_argument("--training-config", type=Path, required=True)
    utility_reference.add_argument("--output-dir", type=Path, required=True)
    utility_reference.add_argument("--output", type=Path)
    utility_train = subparsers.add_parser("train-training-utility")
    utility_train.add_argument("--training-config", type=Path, required=True)
    utility_train.add_argument(
        "--cohort",
        choices=tuple(item.value for item in UtilityCohort),
        required=True,
    )
    utility_train.add_argument("--dataset", type=Path, required=True)
    utility_train.add_argument("--output-dir", type=Path, required=True)
    utility_train.add_argument("--output", type=Path)
    utility_eval = subparsers.add_parser("evaluate-training-utility")
    utility_eval.add_argument("--training-config", type=Path, required=True)
    utility_eval.add_argument("--cohort", required=True)
    utility_eval.add_argument("--evaluation-dataset", type=Path, required=True)
    utility_eval.add_argument("--adapter-dir", type=Path)
    utility_eval.add_argument("--output-dir", type=Path, required=True)
    utility_eval.add_argument("--output", type=Path)
    utility_summary = subparsers.add_parser("summarize-training-utility")
    utility_summary.add_argument("--training-config", type=Path, required=True)
    utility_summary.add_argument("--data-manifest", type=Path, required=True)
    utility_summary.add_argument("--base-evaluation", type=Path, required=True)
    utility_summary.add_argument(
        "--training-result",
        type=Path,
        action="append",
        required=True,
    )
    utility_summary.add_argument(
        "--cohort-evaluation",
        type=Path,
        action="append",
        required=True,
    )
    utility_summary.add_argument("--output-dir", type=Path, required=True)
    utility_summary.add_argument("--output", type=Path)
    return parser


def _demo(adapter: FinanceArchiveAdapter, limit: int) -> dict[str, Any]:
    semantic_policy = FinanceSemanticPolicy()
    source_grounding_verifier = adapter.source_grounding_verifier()
    task_synthesizer = FinanceTaskPlugin(source_grounding_requirement=VerifierRequirement.REQUIRED)
    registry = default_registry()
    trajectory_generator = ReferenceWorkflowCompiler(registry)
    candidate_generator = FinanceNumericCandidateGenerator()
    graph_builder = ProofGraphBuilder()
    evaluator = ReferenceQualityEvaluator(
        semantic_policy=semantic_policy,
        source_grounding_verifier=source_grounding_verifier,
    )
    plugin_set = finance_plugin_set(adapter, registry, source_grounding_verifier)
    quality_contract_compiler = QualityContractCompiler(
        registry,
        domain_provider=FinanceQualityClauseProvider(),
    )
    proof_compiler = ProofCarryingSampleCompiler(
        registry,
        quality_contract_compiler,
        plugin_set,
        semantic_policy=semantic_policy,
        source_grounding_verifier=source_grounding_verifier,
    )
    workflow_verifier = CandidateWorkflowVerifier(
        registry,
        semantic_policy=semantic_policy,
        claim_verifier=FinanceClaimVerifier(),
        source_grounding_verifier=source_grounding_verifier,
    )
    candidate_evaluator = CandidateQualityEvaluator(
        semantic_policy=semantic_policy,
        claim_verifier=FinanceClaimVerifier(),
        source_grounding_verifier=source_grounding_verifier,
        workflow_verifier=workflow_verifier,
    )
    contract_runtime = QualityContractRuntime(
        workflow_verifier,
        verifier_registry=quality_contract_compiler.verifier_registry,
    )
    samples = []
    tasks = []
    candidate_records = []
    quality_contracts = []
    proof_certificates = []
    split_policy = SplitPolicy(policy_id="semantic_split.v1")
    for evidence in adapter.iter_evidence(limit=limit):
        bundle_identity = {"purpose": "finance_demo", "evidence_id": evidence.evidence_id}
        bundle = EvidenceBundle(
            bundle_id=canonical_hash(bundle_identity, prefix="bundle:"),
            evidence=(evidence,),
            purpose="finance archive retrieval demo",
            graph_build_id=evidence.provenance.build_ids.get("kg"),
        )
        graph = graph_builder.build(bundle)
        task = task_synthesizer.fact_retrieval(graph, bundle, evidence.evidence_id)
        tasks.append(task)
        trajectory = trajectory_generator.compile(task, bundle)
        assessment = evaluator.evaluate(task, bundle, graph, trajectory)
        compiled = proof_compiler.compile(
            task,
            bundle,
            graph,
            reference_trajectory=trajectory,
            reference_assessment=assessment,
        )
        corpus = EvidenceCorpus.from_bundle(bundle)
        candidate = candidate_generator.generate(task.public, InMemoryEvidenceToolRuntime(corpus))
        candidate_assessment = candidate_evaluator.evaluate(task, corpus, graph, candidate)
        contract_assessment = contract_runtime.evaluate(
            compiled.quality_contract,
            task,
            corpus,
            graph,
            candidate,
        )
        quality_contracts.append(compiled.quality_contract)
        proof_certificates.append(compiled.sample.certificate)
        candidate_records.append((task, candidate, candidate_assessment))
        samples.append(
            {
                "bundle": bundle.model_dump(mode="json", exclude_none=True),
                "graph": graph.model_dump(mode="json", exclude_none=True),
                "task_public": task.public.model_dump(mode="json", exclude_none=True),
                "oracle_contract": task.oracle.model_dump(mode="json", exclude_none=True),
                "reference_workflow": trajectory.model_dump(mode="json", exclude_none=True),
                "quality": assessment.model_dump(mode="json", exclude_none=True),
                "candidate_workflow": candidate.model_dump(mode="json", exclude_none=True),
                "candidate_quality": candidate_assessment.model_dump(
                    mode="json", exclude_none=True
                ),
                "proof_carrying_public": compiled.public_artifact.model_dump(
                    mode="json", exclude_none=True
                ),
                "quality_contract": compiled.quality_contract.model_dump(
                    mode="json", exclude_none=True
                ),
                "contract_quality": contract_assessment.model_dump(mode="json", exclude_none=True),
                "split": assign_split(task, split_policy).value,
            }
        )
    inspection = adapter.inspect()
    candidate_selection = select_candidate_release(candidate_records, split_policy)
    cross_domain_contracts = run_cross_domain_contract_suite()
    manifest = build_release_manifest(
        release_id=canonical_hash(
            {
                "purpose": "finance_demo_v2",
                "kg_build_id": inspection.get("kg_build_id"),
                "task_ids": [task.task_id for task in tasks],
            },
            prefix="release:",
        ),
        tasks=tasks,
        adapters=(adapter,),
        registry=registry,
        split_policy=split_policy,
        source_build_ids={"finance_kg": str(inspection.get("kg_build_id"))},
        candidate_selection=candidate_selection,
        domain_plugin_sets=(
            plugin_set,
            *cross_domain_contracts.plugin_sets,
        ),
        source_grounding_verifiers=(source_grounding_verifier,),
        cross_domain_contract_suite=cross_domain_contracts.result,
        quality_contracts=quality_contracts,
        proof_certificates=proof_certificates,
    )
    return {
        "pipeline": [
            "finance_adapter",
            "evidence_bundle",
            "proof_graph",
            "task_synthesis",
            "reference_workflow_compilation",
            "quality_evaluation",
            "candidate_generation",
            "candidate_quality_evaluation",
        ],
        "sample_count": len(samples),
        "release_manifest": manifest.model_dump(mode="json", exclude_none=True),
        "samples": samples,
    }


def _emit(payload: Any, output: Path | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    raise SystemExit(main())
