from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    make_program,
)
from trusted_synthesis.domains.finance.agent_tools import (
    finance_archive_agent_tool_specs,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_capability_boundary_analysis as analysis,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_capability_boundary_runner as runner,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_beneficiary_frontier import (
    BeneficiaryFamilyOrdering,
    freeze_beneficiary_identity,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CAPABILITY_AXES,
    CapabilityRuntimeArm,
    TechnicalQualificationThresholds,
    TierLocalizationThresholds,
    _capability_agent_contract_guidance,
    default_information_thresholds,
    make_model_visible_demand,
    runtime_public_allowed_tools,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    BoundaryStage,
    CapabilityRolloutOutcome,
    ConfidenceInterval,
    SignedConfidenceInterval,
    _information_matrices,
    capability_outcome_set_hash,
    capability_rollout_outcome_id,
    make_empirical_information_audit,
    make_qualification_report,
    make_tier_localization_report,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_runner import (
    _captured_failure_authority,
    _replay_discovered_models,
    _scripted_tool_authority,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_SENSITIVE_FAMILIES,
    FAMILY_PRIMARY_CAPABILITY,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_regression import (
    _contains_operation_reference_model_violation,
    _contains_ratio_pair_model_violation,
    _task_evidence_identity_sets,
    public_task_exposure_signature,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_satisfiability import (
    replay_tool_preconditions,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import FailedActionPlan, HostInteractionProgress


def _outcome(
    *,
    contract_id: str,
    stage: BoundaryStage,
    binding: SimpleNamespace,
    model: ExplorerArm,
    replicate: int,
    semantic_success: bool,
) -> CapabilityRolloutOutcome:
    interactive = binding.runtime_arm != CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL
    values = {
        "contract_id": contract_id,
        "stage": stage,
        "binding_id": binding.binding_id,
        "task_artifact_id": binding.task_artifact_id,
        "family": binding.family,
        "model_arm": model,
        "runtime_arm": binding.runtime_arm,
        "replicate": replicate,
        "completed": True,
        "raw_json_contract_success": True,
        "bounded_json_resolution_success": True,
        "api_call_count": 1,
        "json_contract_success_count": 1,
        "contract_repair_count": 0,
        "tool_call_count": int(interactive),
        "semantically_successful_tool_call_count": int(interactive),
        "bounded_tool_resolution_count": int(interactive),
        "runtime_infrastructure_failure_count": 0,
        "final_answer_emitted": True,
        "terminal_result_emitted": True,
        "observation_replay_success": True,
        "authority_integrity_success": True,
        "host_verification_repair_count": 0,
        "budget_exhausted": False,
        "deterministic_valid": semantic_success,
        "semantic_answer_correct": semantic_success,
        "valid_success": semantic_success,
        "tool_semantic_success": semantic_success,
        "verification_success": semantic_success,
        "query_reformulated": False,
        "recovery_opportunity": False,
        "recovery_success": False,
        "stop_quality_success": semantic_success,
        "state_id": f"state:{binding.binding_id}" if semantic_success else None,
        "decision_trace_hash": f"trace:{binding.binding_id}:{replicate}",
        "tool_sequence_hash": (f"tools:{binding.binding_id}:{replicate}" if interactive else None),
        "total_model_tokens": 100,
        "estimated_cost_usd": 0.01,
        "mean_api_latency_ms": 10.0,
    }
    provisional = CapabilityRolloutOutcome.model_construct(outcome_id="pending", **values)
    return CapabilityRolloutOutcome(outcome_id=capability_rollout_outcome_id(provisional), **values)


def test_runtime_projection_removes_host_controlled_capability_demand() -> None:
    task = SimpleNamespace(
        artifact_id="task:projection",
        capability_demand=SimpleNamespace(
            values={axis: float(index + 1) for index, axis in enumerate(CAPABILITY_AXES)}
        ),
    )

    direct = make_model_visible_demand(task, CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL)
    scripted = make_model_visible_demand(task, CapabilityRuntimeArm.SCRIPTED_TOOL)
    autonomous = make_model_visible_demand(task, CapabilityRuntimeArm.AUTONOMOUS_AGENT)

    assert direct.model_visible_axes == (
        "calculation",
        "reconciliation",
        "verification",
    )
    assert scripted.model_visible_axes == (
        "retrieval",
        "calculation",
        "reconciliation",
        "verification",
        "recovery",
    )
    assert autonomous.model_visible_axes == CAPABILITY_AXES
    assert all(
        autonomous.values[axis] == task.capability_demand.values[axis] for axis in CAPABILITY_AXES
    )


def test_qualification_semantic_accuracy_is_descriptive_not_a_runtime_gate() -> None:
    bindings = tuple(
        SimpleNamespace(
            binding_id=f"binding:{runtime.value}",
            task_artifact_id=f"task:{runtime.value}",
            family=CAPABILITY_SENSITIVE_FAMILIES[0],
            runtime_arm=runtime,
        )
        for runtime in CapabilityRuntimeArm
    )
    contract = SimpleNamespace(
        contract_id="contract:qualification",
        qualification_bindings=bindings,
        qualification_replicas=1,
        requested_qualification_rollouts=6,
        technical_thresholds=TechnicalQualificationThresholds(),
    )
    outcomes = tuple(
        _outcome(
            contract_id=contract.contract_id,
            stage=BoundaryStage.RUNTIME_QUALIFICATION,
            binding=binding,
            model=model,
            replicate=0,
            semantic_success=False,
        )
        for binding in bindings
        for model in ExplorerArm
    )

    report = make_qualification_report(contract, outcomes)

    assert report.status == "passed"
    assert report.semantic_results_are_descriptive_only is True
    assert all(cell.semantic_accuracy == 0 for cell in report.cells)
    assert report.next_permitted_stage == "capability_tier_localization"
    assert report.outcome_set_hash == capability_outcome_set_hash(outcomes)
    report_payload = report.model_dump()
    report_payload["recorded_rollout_count"] -= 1
    report_payload["report_id"] = "report:tampered"
    with pytest.raises(ValueError, match="incomplete rollout denominator"):
        type(report).model_validate(report_payload)


def test_direct_runtime_compiles_operation_tools_not_archive_tools(
    finance_evidence: EvidenceItem,
) -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle:direct_tool_contract",
        evidence=(finance_evidence,),
        purpose="Direct Runtime allowed-tool regression",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().fact_retrieval(
        graph, bundle, finance_evidence.evidence_id
    )
    artifact = SimpleNamespace(task=task)
    manifest = SimpleNamespace(
        tools=(SimpleNamespace(tool_id="query_structured_fact"),)
    )

    direct = runtime_public_allowed_tools(
        artifact,
        CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL,
        manifest,
    )
    scripted = runtime_public_allowed_tools(
        artifact,
        CapabilityRuntimeArm.SCRIPTED_TOOL,
        manifest,
    )

    assert direct == ("evidence.search",)
    assert scripted == ("query_structured_fact",)


def test_scripted_tool_preconditions_require_explicit_evidence_selection() -> None:
    with pytest.raises(ValueError, match="selected_evidence"):
        replay_tool_preconditions(
            ("search_archive", "normalize_metric_unit_period")
        )

    trace, terminal = replay_tool_preconditions(
        (
            "search_archive",
            "query_structured_fact",
            "normalize_metric_unit_period",
            "calculator",
            "cross_check_evidence",
        )
    )

    assert len(trace) == 5
    assert "selected_evidence" in trace[1].state_after
    assert "verified_result" in terminal


def test_capability_guidance_exposes_exact_prior_operation_contract() -> None:
    difference = OperationNode(
        node_id="difference",
        operator_id="difference",
        input_refs=(
            ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id="evidence:earlier"),
            ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id="evidence:later"),
        ),
        parameters={},
        output_schema="numeric",
        verifier_id="operation_replay",
    )
    ratio = OperationNode(
        node_id="ratio",
        operator_id="ratio",
        input_refs=(
            ProgramInputRef(
                kind=InputRefKind.OPERATION,
                ref_id="difference",
                selector="value",
            ),
            ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id="evidence:earlier"),
        ),
        parameters={"registered_pair": "revenue/revenue"},
        output_schema="numeric",
        verifier_id="operation_replay",
        dependencies=("difference",),
    )
    program = make_program((difference, ratio), "ratio")

    guidance = _capability_agent_contract_guidance(program, existing=None)
    operation_contract = guidance["calculator_operation_reference_contract"]

    assert operation_contract["allowed_selectors"] == ("value",)
    assert operation_contract["selector_base"] == (
        "prior calculator observation result.result.output"
    )
    assert operation_contract["literal_operation_names_are_forbidden"] is True
    assert guidance["registered_ratio_pairs"] == ("revenue/revenue",)

    calculator = next(
        item for item in finance_archive_agent_tool_specs() if item.tool_id == "calculator"
    )
    operand_contract = str(calculator.input_contract["operands"])
    assert "result.result.operation_ref" in operand_contract
    assert "selector='value'" in operand_contract
    assert "never use output, output.value" in operand_contract


def test_regression_detects_operation_and_ratio_contract_failures() -> None:
    def record(message: str) -> SimpleNamespace:
        return SimpleNamespace(
            model_dump=lambda **_: {
                "failure_artifact": {"failure_message": message}
            }
        )

    assert _contains_operation_reference_model_violation(
        record("operation selector is invalid: output.value")
    )
    assert _contains_operation_reference_model_violation(
        record("calculator operation reference is unknown: difference")
    )
    assert _contains_ratio_pair_model_violation(
        record("ratio pair is not explicitly registered: revenue/revenue")
    )


def test_public_task_exposure_signature_binds_semantics_not_artifact_id() -> None:
    def task(instruction: str, subject_id: str) -> dict[str, object]:
        return {
            "artifact_id": "ignored:artifact-identity",
            "family": "finance.calculation_chain",
            "task": {
                "public": {
                    "task_type": "calculation_chain",
                    "instruction": instruction,
                },
                "oracle": {
                    "task_program": {
                        "nodes": [
                            {
                                "operator_id": "lookup",
                                "input_refs": [
                                    {
                                        "kind": "evidence",
                                        "role_id": "reported_value",
                                        "selector": None,
                                    }
                                ],
                                "parameters": {},
                            }
                        ]
                    }
                },
            },
            "public_corpus": {
                "evidence": [
                    {
                        "subject": {"subject_id": subject_id},
                        "predicate": "revenue",
                        "temporal_context": {"label": "FY2024"},
                        "definition": {"definition_id": "metric:revenue"},
                        "source": {"source_id": "official-filing"},
                    }
                ]
            },
        }

    baseline = task("What was Alpha revenue in FY2024?", "entity:alpha")
    same_semantics = {**baseline, "artifact_id": "another:artifact-identity"}
    changed_semantics = task("What was Beta revenue in FY2024?", "entity:beta")

    assert public_task_exposure_signature(baseline) == public_task_exposure_signature(
        same_semantics
    )
    assert public_task_exposure_signature(baseline) != public_task_exposure_signature(
        changed_semantics
    )


def test_exposure_identity_set_binds_evidence_and_version_ids() -> None:
    task = {
        "public_corpus": {
            "evidence": [
                {
                    "evidence_id": "evidence:1",
                    "evidence_version_id": "evidence-version:1",
                },
                {
                    "evidence_id": "evidence:2",
                    "evidence_version_id": "evidence-version:2",
                },
            ]
        }
    }

    evidence_ids, version_ids = _task_evidence_identity_sets((task,))

    assert evidence_ids == {"evidence:1", "evidence:2"}
    assert version_ids == {"evidence-version:1", "evidence-version:2"}

    del task["public_corpus"]["evidence"][0]["evidence_version_id"]  # type: ignore[index]
    with pytest.raises(ValueError, match="lacks a Version ID"):
        _task_evidence_identity_sets((task,))


def _localization_contract_and_outcomes(
    *,
    all_fail: bool = False,
) -> tuple[SimpleNamespace, SimpleNamespace, tuple[CapabilityRolloutOutcome, ...]]:
    bindings = tuple(
        SimpleNamespace(
            binding_id=f"binding:{family}:{tier.value}:{runtime.value}",
            task_artifact_id=f"task:{family}:{tier.value}",
            family=family,
            tier=tier,
            runtime_arm=runtime,
        )
        for family in CAPABILITY_SENSITIVE_FAMILIES
        for tier in DifficultyTier
        for runtime in CapabilityRuntimeArm
    )
    contract = SimpleNamespace(
        contract_id="contract:tier-localization",
        localization_bindings=bindings,
        localization_replicas=5,
        requested_localization_rollouts=630,
        localization_thresholds=TierLocalizationThresholds(),
    )
    qualification = SimpleNamespace(
        contract_id=contract.contract_id,
        report_id="qualification:passed",
        status="passed",
    )
    success_limits = {
        DifficultyTier.EASY_CONTROL: {
            ExplorerArm.PRO: 5,
            ExplorerArm.FLASH: 4,
        },
        DifficultyTier.FRONTIER: {
            ExplorerArm.PRO: 3,
            ExplorerArm.FLASH: 2,
        },
        DifficultyTier.HARD_CONTROL: {
            ExplorerArm.PRO: 0,
            ExplorerArm.FLASH: 0,
        },
    }
    outcomes = tuple(
        _outcome(
            contract_id=contract.contract_id,
            stage=BoundaryStage.TIER_LOCALIZATION,
            binding=binding,
            model=model,
            replicate=replicate,
            semantic_success=(
                False
                if all_fail
                else replicate < success_limits[binding.tier][model]
            ),
        )
        for binding in bindings
        for model in ExplorerArm
        for replicate in range(contract.localization_replicas)
    )
    return contract, qualification, outcomes


def test_tier_localization_selects_common_empirical_frontier() -> None:
    contract, qualification, outcomes = _localization_contract_and_outcomes()

    report = make_tier_localization_report(contract, qualification, outcomes)

    assert report.recorded_rollout_count == 630
    assert report.all_runtime_localization_ready is True
    assert report.calibration_frontier_compatible is True
    assert report.next_permitted_stage == "paired_capability_calibration"
    assert report.monotonic_response_fraction == 1.0
    assert all(
        item.selected_tier == DifficultyTier.FRONTIER
        for item in report.selections
    )


def test_tier_localization_rejects_all_floor_response_distribution() -> None:
    contract, qualification, outcomes = _localization_contract_and_outcomes(all_fail=True)

    report = make_tier_localization_report(contract, qualification, outcomes)

    assert report.all_runtime_localization_ready is False
    assert report.calibration_frontier_compatible is False
    assert report.next_permitted_stage == "task_or_runtime_redesign_only"
    assert not any(item.boundary_identified for item in report.selections)


def test_empirical_information_rejects_response_saturated_pseudo_distribution() -> None:
    bindings = []
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        axis = FAMILY_PRIMARY_CAPABILITY[family]
        for runtime in CapabilityRuntimeArm:
            mask = {demand_axis: float(demand_axis == axis) for demand_axis in CAPABILITY_AXES}
            bindings.append(
                SimpleNamespace(
                    binding_id=f"binding:{family}:{runtime.value}",
                    task_artifact_id=f"task:{family}",
                    family=family,
                    runtime_arm=runtime,
                    general_difficulty=5.0,
                    visible_demand=SimpleNamespace(values=mask),
                )
            )
    thresholds = default_information_thresholds().model_copy(update={"bootstrap_replicates": 100})
    contract = SimpleNamespace(
        contract_id="contract:calibration",
        calibration_bindings=tuple(bindings),
        calibration_replicas=2,
        requested_calibration_rollouts=len(bindings) * len(tuple(ExplorerArm)) * 2,
        information_thresholds=thresholds,
    )
    qualification = SimpleNamespace(
        contract_id=contract.contract_id,
        report_id="qualification:passed",
        status="passed",
    )
    outcomes = tuple(
        _outcome(
            contract_id=contract.contract_id,
            stage=BoundaryStage.PAIRED_CALIBRATION,
            binding=binding,
            model=model,
            replicate=replicate,
            semantic_success=True,
        )
        for binding in bindings
        for model in ExplorerArm
        for replicate in range(contract.calibration_replicas)
    )

    audit = make_empirical_information_audit(contract, qualification, outcomes)

    assert audit.empirical_capability_ready is False
    assert audit.next_permitted_stage == "task_or_runtime_redesign_only"
    assert all(cell.residual_numerical_rank == 0 for cell in audit.cells)
    assert all(set(cell.marginal_axis_intervals) == set(CAPABILITY_AXES) for cell in audit.cells)
    audit_payload = audit.model_dump()
    audit_payload["recorded_rollout_count"] -= 1
    audit_payload["audit_id"] = "audit:tampered"
    with pytest.raises(ValueError, match="incomplete rollout denominator"):
        type(audit).model_validate(audit_payload)


def test_correct_answer_cannot_masquerade_as_recovery_success() -> None:
    binding = SimpleNamespace(
        binding_id="binding:no-recovery",
        task_artifact_id="task:no-recovery",
        family=CAPABILITY_SENSITIVE_FAMILIES[0],
        runtime_arm=CapabilityRuntimeArm.AUTONOMOUS_AGENT,
    )
    outcome = _outcome(
        contract_id="contract:no-recovery",
        stage=BoundaryStage.PAIRED_CALIBRATION,
        binding=binding,
        model=ExplorerArm.PRO,
        replicate=0,
        semantic_success=True,
    )
    payload = outcome.model_dump()
    payload["recovery_success"] = True
    payload["outcome_id"] = "outcome:tampered"

    with pytest.raises(ValueError, match="recovery opportunity"):
        CapabilityRolloutOutcome.model_validate(payload)


def test_raw_empirical_information_uses_uncentered_demand_second_moment() -> None:
    first = [0.0 for _ in CAPABILITY_AXES]
    second = [0.0 for _ in CAPABILITY_AXES]
    first[0] = 1.0
    second[0] = 3.0
    rows = [
        ("task:1", CAPABILITY_SENSITIVE_FAMILIES[0], 0.5, 1.0, first, (0, 1)),
        ("task:2", CAPABILITY_SENSITIVE_FAMILIES[0], 0.5, 2.0, second, (0, 1)),
    ]

    raw, _, _, _, _ = _information_matrices(rows)

    assert raw[0][0] == pytest.approx(1.25)


def test_completed_checkpoint_replay_does_not_require_live_model_discovery(tmp_path) -> None:
    discovered, source = _replay_discovered_models(
        output_dir=tmp_path,
        stage=BoundaryStage.RUNTIME_QUALIFICATION,
        run_identity="run:checkpoint-only",
    )

    assert source == "checkpoint_contract_replay"
    assert set(discovered) == set(ExplorerArm)
    assert all(values for values in discovered.values())


def test_beneficiary_ordering_uses_uncertainty_not_only_point_means() -> None:
    ordering = BeneficiaryFamilyOrdering(
        family=CAPABILITY_SENSITIVE_FAMILIES[0],
        ordering_tolerance=0.05,
        beneficiary_success_interval=ConfidenceInterval(
            lower=0.2,
            point=0.4,
            upper=0.65,
        ),
        flash_success_rate=0.5,
        pro_success_rate=0.6,
        pro_minus_flash_interval=SignedConfidenceInterval(
            lower=0.02,
            point=0.1,
            upper=0.18,
        ),
        beneficiary_not_above_flash=False,
        flash_not_above_pro=True,
        ordered=False,
    )

    assert ordering.ordered is False
    payload = ordering.model_dump()
    payload["beneficiary_not_above_flash"] = True
    with pytest.raises(ValueError, match="beneficiary-to-Flash"):
        BeneficiaryFamilyOrdering.model_validate(payload)


def test_direct_semantic_action_failure_is_a_typed_terminal_result() -> None:
    failure = FailedActionPlan(
        task_id="task:direct",
        failure_category="semantic_action",
        error_code="public_selector_mismatch",
        error_message="selectors do not preserve the public plan",
    )
    progress = HostInteractionProgress(
        action_plan_attempted=True,
        action_plan_contract_succeeded=True,
    )
    record = SimpleNamespace(
        error_type="LLMClientError",
        failure_artifact=failure,
        interaction_progress=progress,
        task_id="task:direct",
        protocol_profile_hash="protocol:unused-for-direct",
    )
    binding = SimpleNamespace(
        runtime_arm=CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL,
    )

    assert _captured_failure_authority(record, binding) is True
    record.failure_artifact = failure.model_copy(update={"failure_category": "interface_security"})
    assert _captured_failure_authority(record, binding) is False


def test_scripted_authority_advances_only_after_success() -> None:
    observations = (
        SimpleNamespace(call=SimpleNamespace(tool_id="search"), status="failed"),
        SimpleNamespace(call=SimpleNamespace(tool_id="search"), status="succeeded"),
        SimpleNamespace(call=SimpleNamespace(tool_id="inspect"), status="succeeded"),
    )

    assert _scripted_tool_authority(
        observations,
        ("search", "inspect"),
        require_complete=True,
    )
    assert not _scripted_tool_authority(
        (SimpleNamespace(call=SimpleNamespace(tool_id="inspect"), status="failed"),),
        ("search", "inspect"),
        require_complete=False,
    )


def test_beneficiary_identity_recomputes_checkpoint_contract(tmp_path) -> None:
    base_dir = tmp_path / "base"
    adapter_dir = tmp_path / "adapter"
    base_dir.mkdir()
    adapter_dir.mkdir()
    base_file = base_dir / "config.json"
    adapter_file = adapter_dir / "adapter.safetensors"
    base_file.write_bytes(b"base-model")
    adapter_file.write_bytes(b"adapter")
    base_files = {
        base_file.name: {
            "sha256": hashlib.sha256(base_file.read_bytes()).hexdigest(),
            "size": base_file.stat().st_size,
        }
    }
    manifest_hash = canonical_hash(base_files, prefix="base_model_content_manifest:")
    manifest = {
        "model_dir": str(base_dir),
        "files": base_files,
        "manifest_hash": manifest_hash,
    }
    manifest_path = tmp_path / "base_model_content_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    adapter_files = {
        adapter_file.name: {
            "sha256": hashlib.sha256(adapter_file.read_bytes()).hexdigest(),
            "size": adapter_file.stat().st_size,
        }
    }
    adapter_tensor_sha256 = "a" * 64
    checkpoint_hash = canonical_hash(
        {
            "base_model_manifest_hash": manifest_hash,
            "adapter_tensor_sha256": adapter_tensor_sha256,
            "adapter_files": adapter_files,
        },
        prefix="qwen_beneficiary_checkpoint:",
    )
    model_state_id = canonical_hash(
        {
            "checkpoint_hash": checkpoint_hash,
            "role": "vtdo_beneficiary",
            "task_family": "finance_phase1",
        },
        prefix="beneficiary_model_state:",
    )
    report = {
        "adapter_dir": str(adapter_dir),
        "adapter_files": adapter_files,
        "adapter_tensor_sha256": adapter_tensor_sha256,
        "base_model_manifest_hash": manifest_hash,
        "checkpoint_hash": checkpoint_hash,
        "model_state_id": model_state_id,
    }
    report["report_hash"] = canonical_hash(report, prefix="finance_phase1_beneficiary:")
    report_path = tmp_path / "beneficiary_training_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    identity = freeze_beneficiary_identity(
        training_report_path=report_path,
        base_model_manifest_path=manifest_path,
    )

    assert identity.checkpoint_hash == checkpoint_hash
    report["checkpoint_hash"] = "checkpoint:tampered"
    report.pop("report_hash")
    report["report_hash"] = canonical_hash(report, prefix="finance_phase1_beneficiary:")
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="checkpoint hash"):
        freeze_beneficiary_identity(
            training_report_path=report_path,
            base_model_manifest_path=manifest_path,
        )


def test_calibration_authorization_replays_qualification_artifacts(
    tmp_path,
    monkeypatch,
) -> None:

    bindings = tuple(
        SimpleNamespace(
            binding_id=f"binding:{runtime.value}",
            task_artifact_id=f"task:{runtime.value}",
            family=CAPABILITY_SENSITIVE_FAMILIES[0],
            runtime_arm=runtime,
        )
        for runtime in CapabilityRuntimeArm
    )
    contract = SimpleNamespace(
        contract_id="contract:qualification-lineage",
        qualification_bindings=bindings,
        qualification_replicas=1,
        requested_qualification_rollouts=6,
        technical_thresholds=TechnicalQualificationThresholds(),
    )
    stage = BoundaryStage.RUNTIME_QUALIFICATION
    run_identity = runner._run_identity(contract, stage, bindings, 1)
    records = []
    outcomes = []
    for binding in bindings:
        for model in ExplorerArm:
            values = {
                "run_identity": run_identity,
                "contract_id": contract.contract_id,
                "stage": stage,
                "binding_id": binding.binding_id,
                "task_artifact_id": binding.task_artifact_id,
                "task_id": binding.task_artifact_id,
                "family": binding.family,
                "model_arm": model,
                "runtime_arm": binding.runtime_arm,
                "replicate": 0,
                "attempt_id": f"attempt:{binding.binding_id}:{model.value}",
                "requested_model": runner.EXPECTED_MODELS[model.value],
                "model_config_hash": "model-config:test",
                "omega_context_id": "omega:test",
                "omega_context_hash": "omega-hash:test",
                "environment_manifest_id": "environment:test",
                "environment_manifest_hash": "environment-hash:test",
                "protocol_profile_hash": "protocol:test",
                "status": "failed",
                "trajectory": None,
                "agent_audit": None,
                "observations": (),
                "verification": None,
                "verification_payload": None,
                "state_assignment": None,
                "telemetry": (),
                "failure_artifact": None,
                "interaction_progress": None,
                "error_type": "SyntheticInfrastructureFailure",
                "error_message": "synthetic record for lineage replay",
                "budget_exhausted": False,
            }
            provisional = runner.CapabilityBoundaryRolloutRecord.model_construct(
                record_id="pending",
                **values,
            )
            records.append(
                runner.CapabilityBoundaryRolloutRecord(
                    record_id=runner.capability_boundary_record_id(provisional),
                    **values,
                )
            )
            outcomes.append(
                _outcome(
                    contract_id=contract.contract_id,
                    stage=stage,
                    binding=binding,
                    model=model,
                    replicate=0,
                    semantic_success=False,
                )
            )
    records_tuple = tuple(records)
    outcomes_tuple = tuple(outcomes)
    outcome_by_key = {
        (item.model_arm, item.binding_id, item.replicate): item for item in outcomes_tuple
    }
    monkeypatch.setattr(
        runner,
        "_to_outcome",
        lambda record, _: outcome_by_key[(record.model_arm, record.binding_id, record.replicate)],
    )

    checkpoint_path = tmp_path / "runtime_qualification.checkpoint.jsonl"
    records_path = tmp_path / "runtime_qualification_records.jsonl"
    outcomes_path = tmp_path / "runtime_qualification_outcomes.jsonl"
    report_path = tmp_path / "finance_runtime_qualification_report.json"
    manifest_path = tmp_path / "runtime_qualification_run_manifest.json"
    serialized_records = "".join(
        json.dumps(item.model_dump(mode="json"), sort_keys=True) + "\n" for item in records_tuple
    )
    checkpoint_path.write_text(serialized_records, encoding="utf-8")
    records_path.write_text(serialized_records, encoding="utf-8")
    outcomes_path.write_text(
        "".join(
            json.dumps(item.model_dump(mode="json"), sort_keys=True) + "\n"
            for item in outcomes_tuple
        ),
        encoding="utf-8",
    )
    report = make_qualification_report(contract, outcomes_tuple)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    manifest = {
        "run_identity": run_identity,
        "runner_version": runner.CAPABILITY_BOUNDARY_RUNNER_VERSION,
        "contract_id": contract.contract_id,
        "stage": stage.value,
        "checkpoint_sha256": runner._sha256(checkpoint_path),
        "records_sha256": runner._sha256(records_path),
        "outcomes_sha256": runner._sha256(outcomes_path),
        "outcome_set_hash": report.outcome_set_hash,
        "report_id": report.report_id,
        "report_schema_version": report.schema_version,
        "report_sha256": runner._sha256(report_path),
    }
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    assert runner._load_passing_qualification(tmp_path, contract) == report

    tampered_cells = (
        report.cells[0].model_copy(update={"semantic_correct_count": 1}),
        *report.cells[1:],
    )
    provisional_report = report.model_copy(update={"report_id": "pending", "cells": tampered_cells})
    tampered_payload = report.model_dump(mode="json")
    tampered_payload["cells"] = [item.model_dump(mode="json") for item in tampered_cells]
    tampered_payload["report_id"] = analysis.qualification_report_id(provisional_report)
    tampered_report = analysis.CapabilityQualificationReport.model_validate(tampered_payload)
    report_path.write_text(
        json.dumps(tampered_report.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    manifest.update(
        {
            "report_id": tampered_report.report_id,
            "report_sha256": runner._sha256(report_path),
        }
    )
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="not authorized by replay"):
        runner._load_passing_qualification(tmp_path, contract)
