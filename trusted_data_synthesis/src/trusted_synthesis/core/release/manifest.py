from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from trusted_synthesis import __version__
from trusted_synthesis.architecture.generalization import assert_generalization_contract
from trusted_synthesis.core.evaluation.contracts.runtime import (
    QUALITY_CONTRACT_RUNTIME_VERSION,
)
from trusted_synthesis.core.evaluation.contracts.schema import QualityContract
from trusted_synthesis.core.evaluation.evaluator import (
    CANDIDATE_REQUIRED_CHECK_MANIFEST,
    REQUIRED_CHECK_MANIFEST,
)
from trusted_synthesis.core.evaluation.mutations import mutation_taxonomy_manifest_hash
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.plugins import (
    DomainPluginSet,
    EvidenceAdapterProtocol,
    SourceGroundingVerifierProtocol,
)
from trusted_synthesis.core.release.schema import (
    CandidateReleaseSelection,
    CrossDomainContractSuiteResult,
    ReleaseManifest,
    SplitPolicy,
)
from trusted_synthesis.core.release.split import assign_split
from trusted_synthesis.core.synthesis.schema import ProofCertificate
from trusted_synthesis.core.task.schema import TaskPackage, VerifierRequirement
from trusted_synthesis.hashing import canonical_hash


def build_release_manifest(
    *,
    release_id: str,
    tasks: Iterable[TaskPackage],
    adapters: Iterable[EvidenceAdapterProtocol],
    registry: OperationRegistry,
    split_policy: SplitPolicy,
    source_build_ids: dict[str, str],
    candidate_selection: CandidateReleaseSelection | None = None,
    domain_plugin_sets: Iterable[DomainPluginSet] = (),
    source_grounding_verifiers: Iterable[SourceGroundingVerifierProtocol] = (),
    cross_domain_contract_suite: CrossDomainContractSuiteResult,
    quality_contracts: Iterable[QualityContract] = (),
    proof_certificates: Iterable[ProofCertificate] = (),
) -> ReleaseManifest:
    source_root = Path(__file__).resolve().parents[3]
    generalization = assert_generalization_contract(source_root)
    task_items = tuple(tasks)
    adapter_items = tuple(adapters)
    contract_items = tuple(quality_contracts)
    certificate_items = tuple(proof_certificates)
    plugin_items = tuple(sorted(domain_plugin_sets, key=lambda item: item.domain))
    if len({item.domain for item in plugin_items}) != len(plugin_items):
        raise ValueError("release cannot freeze multiple plugin sets for the same domain")
    task_domains = {task.public.domain for task in task_items}
    missing_plugin_domains = task_domains - {item.domain for item in plugin_items}
    if missing_plugin_domains:
        raise ValueError(f"release is missing domain plugin sets: {sorted(missing_plugin_domains)}")
    task_ids = {task.task_id for task in task_items}
    if len(task_ids) != len(task_items):
        raise ValueError("release cannot contain duplicate task IDs")
    contract_task_ids = {item.task_id for item in contract_items}
    certificate_task_ids = {item.task_id for item in certificate_items}
    if len(contract_task_ids) != len(contract_items):
        raise ValueError("release requires exactly one quality contract per task")
    if len(certificate_task_ids) != len(certificate_items):
        raise ValueError("release requires exactly one proof certificate per task")
    if contract_task_ids != task_ids:
        raise ValueError("release quality contracts do not exactly cover release tasks")
    if certificate_task_ids != task_ids:
        raise ValueError("release proof certificates do not exactly cover release tasks")
    contracts_by_task = {item.task_id: item for item in contract_items}
    for certificate in certificate_items:
        contract_hash = contracts_by_task[certificate.task_id].contract_hash
        if certificate.quality_contract_hash != contract_hash:
            raise ValueError("release certificate does not bind its task quality contract")
    grounding_items = tuple(source_grounding_verifiers)
    grounding_versions = {item.verifier_id: item.verifier_version for item in grounding_items}
    if len(grounding_versions) != len(grounding_items):
        raise ValueError("source grounding verifier IDs must be unique")
    plugins_by_domain = {item.domain: item for item in plugin_items}
    for task in task_items:
        contract = contracts_by_task[task.task_id]
        plugin = plugins_by_domain[task.public.domain]
        provider_identity = plugin.quality_provider_identity
        if provider_identity != contract.domain_provider_identity:
            raise ValueError(
                f"quality contract provider is not frozen for domain {task.public.domain}"
            )
        requirement = task.public.metadata.get("source_grounding_requirement")
        if requirement != VerifierRequirement.REQUIRED.value:
            continue
        registered = set(plugin.verification_plugin_ids) & set(grounding_versions)
        if not registered:
            raise ValueError(
                f"required source grounding verifier is not frozen for domain {task.public.domain}"
            )
    if not cross_domain_contract_suite.passed:
        raise ValueError("cross-domain contract suite did not pass")
    missing_suite_plugin_domains = set(cross_domain_contract_suite.domains) - {
        item.domain for item in plugin_items
    }
    if missing_suite_plugin_domains:
        raise ValueError(
            "release is missing plugin sets for cross-domain contract suite: "
            f"{sorted(missing_suite_plugin_domains)}"
        )
    if candidate_selection:
        unknown_tasks = set(candidate_selection.accepted_task_ids) - {
            task.task_id for task in task_items
        }
        if unknown_tasks:
            raise ValueError(
                f"candidate selection refers to unknown tasks: {sorted(unknown_tasks)}"
            )
    split_counts = (
        Counter(candidate_selection.split_counts)
        if candidate_selection
        else Counter(assign_split(task, split_policy).value for task in task_items)
    )
    released_total = (
        len(candidate_selection.accepted_trajectory_ids) if candidate_selection else len(task_items)
    )
    return ReleaseManifest(
        release_id=release_id,
        framework_version=__version__,
        evidence_schema_version="evidence_ir.v2",
        proof_graph_schema_version="proof_graph.v3",
        task_program_version="task_program.v2",
        operation_manifest_hash=canonical_hash(registry.manifest(), prefix="operation_manifest:"),
        required_check_manifest_hash=canonical_hash(
            REQUIRED_CHECK_MANIFEST, prefix="check_manifest:"
        ),
        candidate_required_check_manifest_hash=canonical_hash(
            CANDIDATE_REQUIRED_CHECK_MANIFEST, prefix="check_manifest:"
        ),
        quality_contract_compiler_versions=tuple(
            sorted(
                {
                    *(item.compiler_version for item in contract_items),
                    *cross_domain_contract_suite.quality_contract_compiler_versions,
                }
            )
        ),
        quality_contract_runtime_version=QUALITY_CONTRACT_RUNTIME_VERSION,
        clause_verifier_manifest_hashes=tuple(
            sorted(
                {
                    *(item.verifier_manifest_hash for item in contract_items),
                    *cross_domain_contract_suite.clause_verifier_manifest_hashes,
                }
            )
        ),
        quality_contract_hashes=tuple(
            sorted(
                {
                    *(item.contract_hash for item in contract_items),
                    *cross_domain_contract_suite.quality_contract_hashes,
                }
            )
        ),
        proof_compiler_versions=tuple(
            sorted(
                {
                    *(item.compiler_version for item in certificate_items),
                    *cross_domain_contract_suite.proof_compiler_versions,
                }
            )
        ),
        proof_certificate_hashes=tuple(
            sorted(
                {
                    *(item.certificate_hash for item in certificate_items),
                    *cross_domain_contract_suite.proof_certificate_hashes,
                }
            )
        ),
        mutation_taxonomy_manifest_hash=mutation_taxonomy_manifest_hash(),
        split_policy_hash=split_policy.policy_hash,
        domain_plugin_sets=plugin_items,
        source_grounding_verifiers=dict(sorted(grounding_versions.items())),
        cross_domain_contract_suite=cross_domain_contract_suite,
        cross_domain_contract_suite_hash=cross_domain_contract_suite.result_hash,
        adapter_capabilities={
            adapter.adapter_id: tuple(item.value for item in adapter.capability_manifest())
            for adapter in adapter_items
        },
        source_build_ids=source_build_ids,
        sample_counts={"total": released_total, **dict(split_counts)},
        accepted_candidate_trajectory_ids=(
            candidate_selection.accepted_trajectory_ids if candidate_selection else ()
        ),
        quality_assessment_ids=(
            candidate_selection.quality_assessment_ids if candidate_selection else ()
        ),
        failure_distribution=(
            candidate_selection.failure_distribution if candidate_selection else {}
        ),
        domain_task_distribution=(
            candidate_selection.domain_task_distribution if candidate_selection else {}
        ),
        metadata={
            "generalization_contract_version": generalization.contract_version,
            "generalization_audit_hash": generalization.audit_hash,
            "core_domain_import_count": generalization.core_domain_import_count,
            "core_domain_branch_count": generalization.core_domain_branch_count,
            "core_domain_field_access_count": generalization.core_domain_field_access_count,
            "dynamic_domain_import_count": generalization.dynamic_domain_import_count,
            "domain_dispatch_count": generalization.domain_dispatch_count,
            "generalization_scanned_packages": generalization.scanned_packages,
            "generalization_discovered_domains": generalization.discovered_domains,
            "generalization_exempted_files": generalization.exempted_files,
        },
    )
