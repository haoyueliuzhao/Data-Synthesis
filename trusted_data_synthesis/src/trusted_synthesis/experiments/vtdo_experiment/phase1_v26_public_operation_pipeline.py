from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from trusted_synthesis.core.trajectory.executable_support import MechanismNecessityArtifact
from trusted_synthesis.core.trajectory.executable_task import (
    BoundPublicExecutableWitness,
    StaticModelAuthorityPathCatalog,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    MechanismCounterfactualReplayRecord,
    _base_draft,
    _load_definition_pairs,
    _reconciliation_draft,
    _role,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_builder import (
    _artifact_file,
    _freshness_audit,
    _implementation_source_files,
    _load_sources,
    _merge_values,
    _record_evidence_values,
    _select_source_tasks,
    _source_task_values,
    _upgrade_task,
    _write_json,
    _write_models,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    TARGET_MECHANISMS,
    V26_PUBLIC_OPERATION_REMATERIALIZATION_VERSION,
    OperationalTaskAdmission,
    OperationalTaskRecord,
    OperationClosureAudit,
    PathStrategy,
    PublicOperationRematerializationReport,
    public_operation_rematerialization_report_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_witness import (
    build_operation_closure_audit,
    build_operational_admission,
    compile_operational_witness,
    mechanism_necessity_and_catalog,
)
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest, AgentToolObservation


def build_v26_public_operation_rematerialization(
    *,
    run_id: str,
    development_population_path: Path,
    secondary_source_path: Path,
    tertiary_source_path: Path,
    tertiary_no_api_report_path: Path,
    prior_rematerialization_dir: Path,
    snapshot_path: Path,
    exposure_receipt_path: Path,
    sampling_salt: str,
    output_dir: Path,
) -> PublicOperationRematerializationReport:
    (
        development,
        development_tasks,
        sources,
        prior_report,
        prior_records,
        receipt,
        tertiary_no_api_report_sha256,
    ) = _load_sources(
        development_population_path=development_population_path,
        secondary_source_path=secondary_source_path,
        tertiary_source_path=tertiary_source_path,
        tertiary_no_api_report_path=tertiary_no_api_report_path,
        prior_rematerialization_dir=prior_rematerialization_dir,
        snapshot_path=snapshot_path,
        exposure_receipt_path=exposure_receipt_path,
    )
    source_by_id = {item.artifact_id: item for source in sources for item in source.tasks}
    prior_source_tasks = tuple(
        source_by_id[source_id]
        for record in prior_records
        for source_id in record.source_task_artifact_ids
        if source_id in source_by_id
    )
    prior_values = _merge_values(
        _source_task_values(development_tasks),
        _source_task_values(prior_source_tasks),
        _record_evidence_values(prior_records),
    )
    selected = _select_source_tasks(
        sources,
        excluded=prior_values,
        sampling_salt=sampling_salt,
    )
    selected_source_tasks: tuple[CapabilitySensitiveTaskArtifact, ...] = tuple(
        item
        for mechanism in (
            "context_conditioned_action",
            "failure_recovery",
            "state_dependent_stopping",
        )
        for item in selected[mechanism]
    )
    base_selected_evidence = {
        evidence.evidence_id
        for item in selected_source_tasks
        for evidence in item.public_corpus.evidence
    }
    definition_pairs, capacity_audit = _load_definition_pairs(
        snapshot_path=snapshot_path,
        receipt=receipt,
        exposure_receipt_path=exposure_receipt_path,
        additional_excluded_ids=prior_values["evidence_id"] | base_selected_evidence,
        sampling_salt=sampling_salt,
    )

    drafts = []
    for mechanism in (
        "context_conditioned_action",
        "failure_recovery",
        "state_dependent_stopping",
    ):
        for index, task in enumerate(selected[mechanism]):
            drafts.append(
                _base_draft(
                    task,
                    mechanism_id=mechanism,
                    intended_use=_role(index),
                )
            )
    for index in range(6):
        drafts.append(
            _reconciliation_draft(
                definition_pairs[index * 2],
                definition_pairs[index * 2 + 1],
                intended_use=_role(index),
            )
        )
    drafts.sort(key=lambda item: (TARGET_MECHANISMS.index(item.mechanism_id), item.instruction))
    if Counter(item.mechanism_id for item in drafts) != Counter(
        {mechanism: 6 for mechanism in TARGET_MECHANISMS}
    ):
        raise ValueError("v26.60 draft mechanism quotas are incomplete")
    freshness = _freshness_audit(
        development=development,
        prior_report=prior_report,
        sources=sources,
        prior_records=prior_records,
        tertiary_no_api_report_sha256=tertiary_no_api_report_sha256,
        prior_values=prior_values,
        selected_source_tasks=selected_source_tasks,
        drafts=drafts,
    )

    records: list[OperationalTaskRecord] = []
    environments: list[AgentToolEnvironmentManifest] = []
    witnesses: list[BoundPublicExecutableWitness] = []
    observations: list[AgentToolObservation] = []
    necessities: list[MechanismNecessityArtifact] = []
    counterfactuals: list[MechanismCounterfactualReplayRecord] = []
    catalogs: list[StaticModelAuthorityPathCatalog] = []
    closure_audits: list[OperationClosureAudit] = []
    admissions: list[OperationalTaskAdmission] = []
    primary_witnesses: list[BoundPublicExecutableWitness] = []

    for draft in drafts:
        record, environment = _upgrade_task(draft)
        strategies: tuple[PathStrategy, ...] = (
            ("structured_direct",)
            if record.intended_use == "capability_measurement"
            else (
                "structured_direct",
                "search_then_structured",
                "search_then_open",
            )
        )
        task_witnesses = []
        task_histories = []
        for strategy in strategies:
            witness, history = compile_operational_witness(
                record,
                environment,
                strategy=strategy,
            )
            task_witnesses.append(witness)
            task_histories.append(history)
            witnesses.append(witness)
            observations.extend(history)
        necessity, task_counterfactuals, catalog = mechanism_necessity_and_catalog(
            record,
            task_witnesses,
        )
        closure = build_operation_closure_audit(
            record,
            task_witnesses,
            task_histories,
            necessity,
            catalog,
        )
        admission = build_operational_admission(
            record,
            task_witnesses[0],
            necessity,
            catalog,
            closure,
        )
        records.append(record)
        environments.append(environment)
        witnesses.extend(())
        primary_witnesses.append(task_witnesses[0])
        necessities.append(necessity)
        counterfactuals.extend(task_counterfactuals)
        catalogs.append(catalog)
        closure_audits.append(closure)
        admissions.append(admission)

    if len({item.record_id for item in records}) != len(records):
        raise ValueError("v26.60 produced duplicate operational records")
    if len({item.task_package.package_id for item in records}) != len(records):
        raise ValueError("v26.60 produced duplicate TaskPackage identities")
    evidence_ids = [
        item.evidence_id for record in records for item in record.public_corpus.evidence
    ]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("v26.60 rematerialized tasks reuse Public Corpus Evidence")

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "freshness": output_dir / "source_freshness_audit.json",
        "capacity": output_dir / "definition_pair_capacity_audit.json",
        "records": output_dir / "operational_task_records.json",
        "environments": output_dir / "tool_environment_manifests.json",
        "witnesses": output_dir / "operational_public_witnesses.json",
        "observations": output_dir / "operational_witness_observations.json",
        "necessities": output_dir / "mechanism_necessity_artifacts.json",
        "counterfactuals": output_dir / "mechanism_counterfactual_replays.json",
        "catalogs": output_dir / "static_model_authority_path_catalogs.json",
        "closures": output_dir / "operation_closure_audits.json",
        "admissions": output_dir / "operational_task_admissions.json",
    }
    _write_json(paths["freshness"], freshness.model_dump(mode="json"))
    _write_json(paths["capacity"], capacity_audit.model_dump(mode="json"))
    _write_models(paths["records"], records, identity="record_id")
    _write_models(paths["environments"], environments, identity="manifest_id")
    _write_models(paths["witnesses"], witnesses, identity="witness_id")
    _write_models(paths["observations"], observations, identity="observation_id")
    _write_models(paths["necessities"], necessities, identity="artifact_id")
    _write_models(paths["counterfactuals"], counterfactuals, identity="replay_id")
    _write_models(paths["catalogs"], catalogs, identity="catalog_id")
    _write_models(paths["closures"], closure_audits, identity="audit_id")
    _write_models(paths["admissions"], admissions, identity="admission_id")
    counts = {
        "freshness": 1,
        "capacity": 1,
        "records": len(records),
        "environments": len(environments),
        "witnesses": len(witnesses),
        "observations": len(observations),
        "necessities": len(necessities),
        "counterfactuals": len(counterfactuals),
        "catalogs": len(catalogs),
        "closures": len(closure_audits),
        "admissions": len(admissions),
    }
    files = tuple(
        _artifact_file(path, output_dir, counts[key]) for key, path in sorted(paths.items())
    )
    capability_count = sum(item.operational_capability_eligible for item in admissions)
    vtdo_count = sum(item.operational_vtdo_candidate_eligible for item in admissions)
    closure_count = sum(item.status == "passed" for item in closure_audits)
    passed = capability_count == 24 and vtdo_count == 12 and closure_count == 24
    values: dict[str, Any] = {
        "run_id": run_id,
        "development_population_id": development.population_id,
        "prior_rematerialization_report_id": prior_report.report_id,
        "exposure_receipt_id": receipt.receipt_id,
        "definition_pair_capacity_audit_id": capacity_audit.audit_id,
        "freshness_audit_id": freshness.audit_id,
        "target_mechanism_task_counts": {
            mechanism: sum(item.mechanism_id == mechanism for item in records)
            for mechanism in TARGET_MECHANISMS
        },
        "public_operation_contract_count": len(records),
        "operation_closure_pass_count": closure_count,
        "public_witness_pass_count": sum(item.full_validity_passed for item in primary_witnesses),
        "mechanism_necessity_pass_count": sum(item.status == "passed" for item in necessities),
        "operational_capability_eligible_count": capability_count,
        "operational_vtdo_candidate_eligible_count": vtdo_count,
        "static_model_authority_path_count": sum(len(item.paths) for item in catalogs),
        "destructive_mutation_count": sum(len(item.mutation_results) for item in closure_audits),
        "compiler_generated_witness_count": len(witnesses),
        "compiler_witness_pass_count": sum(item.full_validity_passed for item in witnesses),
        "task_records": tuple(sorted(records, key=lambda item: item.record_id)),
        "admissions": tuple(sorted(admissions, key=lambda item: item.admission_id)),
        "immutable_artifact_files": files,
        "implementation_source_files": _implementation_source_files(),
        "status": "passed" if passed else "blocked",
        "next_permitted_stage": (
            "fresh_operation_closure_regression_protocol_only"
            if passed
            else "fresh_public_operation_contract_rematerialization_only"
        ),
        "small_regression_protocol_authorized": passed,
        "schema_version": V26_PUBLIC_OPERATION_REMATERIALIZATION_VERSION,
    }
    provisional = PublicOperationRematerializationReport.model_construct(
        report_id="pending", **values
    )
    report = PublicOperationRematerializationReport(
        report_id=public_operation_rematerialization_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the credential-free Finance v26.60 public Operation Population"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--development-population", type=Path, required=True)
    parser.add_argument("--secondary-source", type=Path, required=True)
    parser.add_argument("--tertiary-source", type=Path, required=True)
    parser.add_argument("--tertiary-no-api-report", type=Path, required=True)
    parser.add_argument("--prior-rematerialization-dir", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--exposure-receipt", type=Path, required=True)
    parser.add_argument("--sampling-salt", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build_v26_public_operation_rematerialization(
        run_id=args.run_id,
        development_population_path=args.development_population,
        secondary_source_path=args.secondary_source,
        tertiary_source_path=args.tertiary_source,
        tertiary_no_api_report_path=args.tertiary_no_api_report,
        prior_rematerialization_dir=args.prior_rematerialization_dir,
        snapshot_path=args.snapshot,
        exposure_receipt_path=args.exposure_receipt,
        sampling_salt=args.sampling_salt,
        output_dir=args.output_dir,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
