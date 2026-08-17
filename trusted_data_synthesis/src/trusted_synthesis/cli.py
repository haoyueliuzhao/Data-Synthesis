from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast, get_args

from trusted_synthesis.architecture.generalization import audit_generalization_contract
from trusted_synthesis.core.evaluation.contracts import (
    QualityContractCompiler,
    QualityContractRuntime,
)
from trusted_synthesis.core.evaluation.evaluator import (
    CandidateQualityEvaluator,
    ReferenceQualityEvaluator,
)
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.release import (
    SplitPolicy,
    assign_split,
    build_release_manifest,
    build_release_validation_summary,
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
from trusted_synthesis.experiments.finance_archive import FinanceArchiveBindingProvider
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
from trusted_synthesis.experiments.vtdo_experiment import (
    VTDO_TRAINING_ARMS,
    BenchmarkGenerationConfig,
    RealFeedbackProductionConfig,
    VTDOExperimentConfig,
    evaluate_external_benchmark_predictions,
    produce_real_vtdo_feedback,
    run_benchmark_predictions,
    run_vtdo_experiment,
    train_vtdo_arm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_heterogeneous_mainline import (
    CapabilityHeterogeneousMainlineProtocol,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    build_v26_fresh_task_population,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_stage_router import (
    V26_STAGES,
    StageArtifactRole,
    advance_v26_stage,
    initialize_v26_stage_ledger,
    load_v26_stage_ledger,
    make_v26_stage_artifact_reference,
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
    if args.command == "run-vtdo-experiment":
        vtdo_config = VTDOExperimentConfig.from_json(args.vtdo_config)
        vtdo_manifest = run_vtdo_experiment(vtdo_config)
        _emit(vtdo_manifest.model_dump(mode="json"), args.output)
        return 0 if vtdo_manifest.status == "passed" else 1
    if args.command == "generate-vtdo-real-feedback":
        feedback_config = RealFeedbackProductionConfig.from_json(args.feedback_config)
        feedback_report = produce_real_vtdo_feedback(feedback_config)
        _emit(feedback_report.model_dump(mode="json"), args.output)
        return 0 if feedback_report.status == "passed" else 1
    if args.command == "train-vtdo-arm":
        try:
            result = train_vtdo_arm(
                student_config_path=args.training_config,
                preflight_path=args.preflight,
                arm_manifest_path=args.arm_manifest,
                arm_id=args.arm,
                dataset_path=args.dataset,
                output_dir=args.output_dir,
                training_seed=args.seed,
            )
        except ValueError as exc:
            _emit(
                {
                    "status": "blocked",
                    "arm_id": args.arm,
                    "reason": str(exc),
                },
                args.output,
            )
            return 1
        _emit(result.model_dump(mode="json"), args.output)
        return 0
    if args.command == "evaluate-vtdo-benchmarks":
        vtdo_config = VTDOExperimentConfig.from_json(args.vtdo_config)
        report = evaluate_external_benchmark_predictions(
            vtdo_config.training.external_benchmarks,
            args.predictions,
            args.prediction_manifest,
        )
        _emit(report.model_dump(mode="json"), args.output)
        return 0 if report.status == "passed" else 1
    if args.command == "predict-vtdo-benchmarks":
        vtdo_config = VTDOExperimentConfig.from_json(args.vtdo_config)
        generation = BenchmarkGenerationConfig.model_validate(
            json.loads(args.generation_config.read_text(encoding="utf-8"))
        )
        manifest = run_benchmark_predictions(
            vtdo_config.training.external_benchmarks,
            args.training_result,
            generation,
            args.output_dir,
        )
        _emit(manifest.model_dump(mode="json"), args.output)
        return 0 if manifest.status == "completed" else 1
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
    if args.command == "freeze-release-validation":
        validation_summary = build_release_validation_summary(
            repo_root=args.repo_root,
            artifacts=tuple(args.artifact),
            test_command=args.test_command,
            test_count=args.test_count,
            test_status=args.test_status,
            online_status=args.online_status,
            supersedes=tuple(args.supersedes or ()),
        )
        _emit(validation_summary.model_dump(mode="json"), args.output)
        return 0 if validation_summary.status == "passed" else 1
    if args.command == "v26-build-fresh-population":
        protocol = CapabilityHeterogeneousMainlineProtocol.model_validate_json(
            args.protocol.read_text(encoding="utf-8")
        )
        population = build_v26_fresh_task_population(
            protocol_id=protocol.protocol_id,
            phase=args.phase,
            source_population_path=args.source_population,
            selection_salt=args.selection_salt,
            output_path=args.output,
        )
        _emit(population.model_dump(mode="json"), args.report)
        return 0
    if args.command == "v26-stage-init":
        ledger = initialize_v26_stage_ledger(
            run_id=args.run_id,
            protocol_path=args.protocol,
            preflight_path=args.preflight,
        )
        _emit(ledger.model_dump(mode="json"), args.output)
        return 0
    if args.command == "v26-stage-advance":
        ledger = load_v26_stage_ledger(args.ledger)
        artifact_args = tuple(_parse_v26_artifact(item) for item in args.artifact)
        references = tuple(
            make_v26_stage_artifact_reference(role, path)
            for role, path in artifact_args
        )
        advanced = advance_v26_stage(
            ledger,
            stage=args.stage,
            artifacts=references,
            model_api_calls=args.model_api_calls,
            gpu_jobs=args.gpu_jobs,
        )
        _emit(advanced.model_dump(mode="json"), args.output)
        return 0
    if args.command == "v26-stage-status":
        ledger = load_v26_stage_ledger(args.ledger)
        _emit(ledger.model_dump(mode="json"), args.output)
        return 0
    adapter = FinanceArchiveAdapter(FinanceArchiveConfig.from_json(args.config))
    if args.command == "audit-finance-synthesis-capacity":
        provider = FinanceArchiveBindingProvider(
            adapter,
            candidate_pool_id=args.candidate_pool_id,
            sampling_partition_id=args.sampling_partition,
            pool_split_seed=args.pool_split_seed,
            evidence_scan_limit=args.evidence_scan_limit,
            evidence_sample_size=args.evidence_sample_size,
            stratum_reservoir_size=args.stratum_reservoir_size,
            candidates_per_pattern=args.candidates_per_pattern,
        )
        capacity = provider.capacity_report(
            target_sample_count=args.target_sample_count,
            distractor_evaluation_limit_per_pattern=(args.distractor_evaluation_limit_per_pattern),
        )
        _emit(capacity.model_dump(mode="json"), args.output)
        return 0 if capacity.status == "ready" else 1
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
    finance_capacity = subparsers.add_parser("audit-finance-synthesis-capacity")
    finance_capacity.add_argument("--config", required=True)
    finance_capacity.add_argument(
        "--candidate-pool-id",
        default="finance_archive_capacity_audit",
    )
    finance_capacity.add_argument("--sampling-partition", choices=("A", "B"), default="A")
    finance_capacity.add_argument("--pool-split-seed", type=int, default=20260729)
    finance_capacity.add_argument("--evidence-scan-limit", type=int, default=200_000)
    finance_capacity.add_argument("--evidence-sample-size", type=int, default=50_000)
    finance_capacity.add_argument("--stratum-reservoir-size", type=int, default=5_000)
    finance_capacity.add_argument("--candidates-per-pattern", type=int, default=2_000)
    finance_capacity.add_argument("--target-sample-count", type=int, default=1_000)
    finance_capacity.add_argument(
        "--distractor-evaluation-limit-per-pattern",
        type=int,
        default=50,
    )
    finance_capacity.add_argument("--output", type=Path)
    audit = subparsers.add_parser("audit-generalization")
    audit.add_argument("--source-root", type=Path, default=Path("src"))
    audit.add_argument("--output", type=Path)
    pattern_validation = subparsers.add_parser("validate-task-patterns")
    pattern_validation.add_argument("--tasks-per-domain", type=int, default=10)
    pattern_validation.add_argument("--output", type=Path)
    counterfactual_validation = subparsers.add_parser("validate-counterfactuals")
    counterfactual_validation.add_argument("--tasks-per-domain", type=int, default=10)
    counterfactual_validation.add_argument("--output", type=Path)
    v26_population = subparsers.add_parser("v26-build-fresh-population")
    v26_population.add_argument("--protocol", type=Path, required=True)
    v26_population.add_argument(
        "--phase",
        choices=("development", "fresh_confirmation"),
        required=True,
    )
    v26_population.add_argument("--source-population", type=Path, required=True)
    v26_population.add_argument("--selection-salt", required=True)
    v26_population.add_argument("--output", type=Path, required=True)
    v26_population.add_argument("--report", type=Path)
    v26_init = subparsers.add_parser("v26-stage-init")
    v26_init.add_argument("--run-id", required=True)
    v26_init.add_argument("--protocol", type=Path, required=True)
    v26_init.add_argument("--preflight", type=Path, required=True)
    v26_init.add_argument("--output", type=Path, required=True)
    v26_advance = subparsers.add_parser("v26-stage-advance")
    v26_advance.add_argument("--ledger", type=Path, required=True)
    v26_advance.add_argument("--stage", choices=V26_STAGES, required=True)
    v26_advance.add_argument("--artifact", action="append", required=True)
    v26_advance.add_argument("--model-api-calls", type=int, default=0)
    v26_advance.add_argument("--gpu-jobs", type=int, default=0)
    v26_advance.add_argument("--output", type=Path, required=True)
    v26_status = subparsers.add_parser("v26-stage-status")
    v26_status.add_argument("--ledger", type=Path, required=True)
    v26_status.add_argument("--output", type=Path)
    vtdo_experiment = subparsers.add_parser("run-vtdo-experiment")
    vtdo_experiment.add_argument("--vtdo-config", type=Path, required=True)
    vtdo_experiment.add_argument("--output", type=Path)
    vtdo_feedback = subparsers.add_parser("generate-vtdo-real-feedback")
    vtdo_feedback.add_argument("--feedback-config", type=Path, required=True)
    vtdo_feedback.add_argument("--output", type=Path)
    vtdo_train = subparsers.add_parser("train-vtdo-arm")
    vtdo_train.add_argument("--training-config", type=Path, required=True)
    vtdo_train.add_argument("--preflight", type=Path, required=True)
    vtdo_train.add_argument("--arm-manifest", type=Path, required=True)
    vtdo_train.add_argument(
        "--arm",
        choices=VTDO_TRAINING_ARMS,
        required=True,
    )
    vtdo_train.add_argument("--dataset", type=Path, required=True)
    vtdo_train.add_argument("--output-dir", type=Path, required=True)
    vtdo_train.add_argument("--seed", type=int, required=True)
    vtdo_train.add_argument("--output", type=Path)
    vtdo_evaluate = subparsers.add_parser("evaluate-vtdo-benchmarks")
    vtdo_evaluate.add_argument("--vtdo-config", type=Path, required=True)
    vtdo_evaluate.add_argument("--predictions", type=Path, required=True)
    vtdo_evaluate.add_argument("--prediction-manifest", type=Path, required=True)
    vtdo_evaluate.add_argument("--output", type=Path)
    vtdo_predict = subparsers.add_parser("predict-vtdo-benchmarks")
    vtdo_predict.add_argument("--vtdo-config", type=Path, required=True)
    vtdo_predict.add_argument("--training-result", type=Path, required=True)
    vtdo_predict.add_argument("--generation-config", type=Path, required=True)
    vtdo_predict.add_argument("--output-dir", type=Path, required=True)
    vtdo_predict.add_argument("--output", type=Path)
    agent_capacity = subparsers.add_parser("audit-agent-capacity")
    agent_capacity.add_argument("--agent-config", type=Path, required=True)
    agent_capacity.add_argument("--output", type=Path)
    agent_validation = subparsers.add_parser("validate-agents")
    agent_validation.add_argument("--agent-config", type=Path, required=True)
    agent_validation.add_argument("--output-dir", type=Path, required=True)
    agent_validation.add_argument("--output", type=Path)
    release_validation = subparsers.add_parser("freeze-release-validation")
    release_validation.add_argument("--repo-root", type=Path, default=Path("."))
    release_validation.add_argument("--artifact", type=Path, action="append", required=True)
    release_validation.add_argument("--test-command", required=True)
    release_validation.add_argument("--test-count", type=int, required=True)
    release_validation.add_argument(
        "--test-status",
        choices=("passed", "failed", "not_run"),
        required=True,
    )
    release_validation.add_argument(
        "--online-status",
        choices=("not_run", "offline_only", "online_passed", "online_failed"),
        default="offline_only",
    )
    release_validation.add_argument("--supersedes", action="append")
    release_validation.add_argument("--output", type=Path, required=True)
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
        corpus = EvidenceCorpus.from_bundle(bundle)
        compiled = proof_compiler.compile(
            task,
            bundle,
            graph,
            public_corpus=corpus,
            reference_trajectory=trajectory,
            reference_assessment=assessment,
        )
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
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(output)
    else:
        print(text, end="")


def _parse_v26_artifact(value: str) -> tuple[StageArtifactRole, Path]:
    role, separator, path = value.partition("=")
    if not separator or not path:
        raise ValueError("v26 artifact must use ROLE=PATH")
    if role not in get_args(StageArtifactRole):
        raise ValueError(f"unknown v26 stage artifact role: {role}")
    return cast(StageArtifactRole, role), Path(path)


if __name__ == "__main__":
    raise SystemExit(main())
