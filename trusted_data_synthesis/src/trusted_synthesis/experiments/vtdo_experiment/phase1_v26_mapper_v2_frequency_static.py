from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from trusted_synthesis.core.evaluation.joint_support_validity import JointSupportValidityContract
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_dynamic_role_preflight as bounded,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_runner_preflight as reachability,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_role_kernel_compatibility_preflight as source_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_preflight_inputs as base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_verifier_bound_task_rematerialization as verifier_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    TargetMechanism,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    FreshFrequencySourcePopulation,
    SourceSelectionAudit,
)
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    ExactFinalResponseGrammar,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    SemanticActionResponseGrammar,
)
from trusted_synthesis.runtime.agent.prospective_thinking import (
    bind_prospective_thinking,
    require_prospective_thinking,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

VERIFIER_REPLAY_TEMPLATE_PATH = (
    "artifacts/vtdo_experiment/"
    "finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/"
    "verifier_v2_replay_bindings.json"
)


def load_static_inputs(package_root: Path) -> Any:
    profile_path = package_root / bounded.PROFILE_PATH
    if base._sha256(profile_path) != bounded.EXPECTED_PROFILE_SHA256:
        raise ValueError("v26.160 exact Stage 1 profile bytes changed")
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    model_config = require_prospective_thinking(AgentModelConfig.model_validate(payload["model"]))
    thinking = bind_prospective_thinking(model_config)
    if (
        model_config.public_manifest_hash != bounded.EXPECTED_MODEL_CONFIG_ID
        or thinking.binding_id != bounded.EXPECTED_THINKING_BINDING_ID
        or model_config.max_output_tokens != 16_384
    ):
        raise ValueError("v26.160 exact model/Thinking profile changed")
    action_grammar = SemanticActionResponseGrammar.model_validate_json(
        (package_root / source_base.ACTION_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    final_grammar = ExactFinalResponseGrammar.model_validate_json(
        (package_root / source_base.FINAL_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    if (
        action_grammar.grammar_id != bounded.EXPECTED_ACTION_GRAMMAR_ID
        or final_grammar.grammar_id != bounded.EXPECTED_FINAL_GRAMMAR_ID
    ):
        raise ValueError("v26.160 frozen Action or Final Grammar changed")
    return SimpleNamespace(
        agent_model_config=model_config,
        action_grammar=action_grammar,
        final_grammar=final_grammar,
        stage_two=SimpleNamespace(profile_id=bounded.EXPECTED_STAGE_TWO_PROFILE_ID),
    )


def _replay_template(package_root: Path) -> Any:
    rows = json.loads((package_root / VERIFIER_REPLAY_TEMPLATE_PATH).read_text(encoding="utf-8"))
    bindings = tuple(
        verifier_binding.VerifierV2TaskReplayBinding.model_validate(item) for item in rows
    )
    if not bindings:
        raise ValueError("v26.160 verifier replay template is empty")
    fields = (
        "qualified_verifier_report_id",
        "qualified_verifier_report_sha256",
        "qualified_replay_contract_id",
        "replay_execution_order",
        "qualified_implementation_sources",
    )
    if any(
        getattr(item, field) != getattr(bindings[0], field)
        for item in bindings[1:]
        for field in fields
    ):
        raise ValueError("v26.160 verifier replay template crossed shared qualification metadata")
    return bindings[0]


def _make_replay_binding(
    record: Any,
    environment: Any,
    template: verifier_binding.VerifierV2TaskReplayBinding,
) -> verifier_binding.VerifierV2TaskReplayBinding:
    package = record.task_package
    repair = package.action_neutral_repair_contract
    target = package.terminal_verification_target
    if repair is None or target is None:
        raise ValueError("v26.160 Verifier v2 binding requires task contracts")
    values: dict[str, Any] = {
        "semantic_source_id": package.semantic_source.semantic_source_id,
        "qualified_verifier_report_id": template.qualified_verifier_report_id,
        "qualified_verifier_report_sha256": template.qualified_verifier_report_sha256,
        "qualified_replay_contract_id": template.qualified_replay_contract_id,
        "public_operation_contract_id": package.operation_contract.contract_id,
        "action_neutral_repair_contract_id": repair.contract_id,
        "terminal_verification_target_id": target.target_id,
        "public_runtime_contract_id": package.public_runtime_contract.contract_id,
        "stop_readiness_contract_id": package.stop_readiness_contract.contract_id,
        "runtime_projection_id": package.runtime_projection.projection_id,
        "answer_projection_contract_id": package.answer_projection.contract_id,
        "evidence_support_lattice_id": package.evidence_support_lattice.lattice_id,
        "citation_contract_id": package.citation_contract.contract_id,
        "mechanism_contract_id": package.mechanism_contract.contract_id,
        "source_program_dag_hash": package.operation_contract.source_program_dag_hash,
        "source_verifier_dag_hash": package.operation_contract.source_verifier_dag_hash,
        "environment_manifest_id": environment.manifest_id,
        "environment_manifest_hash": record.environment_manifest_hash,
        "replay_execution_order": template.replay_execution_order,
        "qualified_implementation_sources": template.qualified_implementation_sources,
    }
    provisional = verifier_binding.VerifierV2TaskReplayBinding.model_construct(
        contract_id="pending",
        **values,
    )
    return verifier_binding.VerifierV2TaskReplayBinding(
        contract_id=verifier_binding.verifier_v2_task_replay_binding_id(provisional),
        **values,
    )


def make_task_catalog(
    *,
    package_root: Path,
    population: FreshFrequencySourcePopulation,
    selection: SourceSelectionAudit,
    joint: JointSupportValidityContract,
    grammar: QualifiedFinalResponseGrammar,
) -> reachability.TaskPackageCatalog:
    template = _replay_template(package_root)
    packages: list[reachability.FreshReachabilityTaskPackage] = []
    for binding in population.tasks:
        if binding.mechanism_id not in bounded.predecessor.TARGET_MECHANISMS:
            raise ValueError("v26.160 source mechanism is outside the frozen language")
        mechanism = cast(TargetMechanism, binding.mechanism_id)
        draft = bounded.predecessor._role_draft(  # noqa: SLF001
            binding.source_task,
            role="reachability",
            mechanism=mechanism,
        )
        source_record, source_environment = bounded.predecessor._upgrade_role_task(draft)  # noqa: SLF001
        environment = bounded.predecessor._verifier_bound_environment(  # noqa: SLF001
            bounded.predecessor._harden_environment(source_environment)  # noqa: SLF001
        )
        authority_record = bounded.predecessor._harden_record(  # noqa: SLF001
            source_record,
            environment,
        )
        replay_binding = _make_replay_binding(
            authority_record,
            environment,
            template,
        )
        record = bounded.predecessor._bind_verifier_v2(  # noqa: SLF001
            authority_record,
            replay_binding,
        )
        prompt_contract = bounded.predecessor._make_compact_prompt_contract(  # noqa: SLF001
            role="reachability",
            record=record,
            environment=environment,
        )
        values = {
            "source_population_id": population.population_id,
            "frozen_input_audit_id": selection.audit_id,
            "source_binding_id": binding.binding_id,
            "source_task_artifact_id": binding.source_task_artifact_id,
            "mechanism_id": binding.mechanism_id,
            "tier": binding.tier,
            "operational_record": record,
            "environment": environment,
            "prompt_contract": prompt_contract,
            "joint_support_validity_contract_id": joint.contract_id,
            "verifier_vnext_contract_id": joint.verifier_vnext_contract_id,
            "qualified_final_grammar_id": grammar.grammar_id,
        }
        provisional = reachability.FreshReachabilityTaskPackage.model_construct(
            task_package_id="pending",
            **values,
        )
        packages.append(
            reachability.FreshReachabilityTaskPackage(
                task_package_id=reachability._identity(  # noqa: SLF001
                    provisional,
                    "task_package_id",
                    "finance_v26_fresh_reachability_task_package:",
                ),
                **values,
            )
        )
    values = {
        "source_population_id": population.population_id,
        "frozen_input_audit_id": selection.audit_id,
        "packages": tuple(sorted(packages, key=lambda item: item.task_package_id)),
    }
    provisional = reachability.TaskPackageCatalog.model_construct(catalog_id="pending", **values)
    return reachability.TaskPackageCatalog(
        catalog_id=reachability._identity(  # noqa: SLF001
            provisional,
            "catalog_id",
            "finance_v26_fresh_reachability_task_catalog:",
        ),
        **values,
    )
