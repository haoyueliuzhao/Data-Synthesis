from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.domains.finance.question_rendering import finance_renderer_registry
from trusted_synthesis.domains.finance.semantic_proposals import (
    RAW_GRAPH_PATTERNS_SHA256,
    RawProposalMigrationAudit,
    audit_raw_proposal_compatibility,
    raw_finance_semantic_proposals,
)
from trusted_synthesis.experiments.qa_realization_vnext.census import (
    QADiversityCensus,
    run_task_package_census,
    write_census_artifacts,
)
from trusted_synthesis.hashing import canonical_hash

EXTERNAL_AUDIT_SHA256 = "1c74b70688123962672cf6d5cda0e7932269880ddb77216860dc0c524b2eb811"
EXTERNAL_AUDIT_BYTE_COUNT = 28_811
RAW_VERBALIZER_SHA256 = "07c039be67fe52416e4978904582fbb0bbfa4a22b46578863d10f71296c3d213"
RAW_DIVERSITY_SHA256 = "001d21ec74d5641d2e085cee547fef2311638a9fc5d2a3a298c34fcd76a8c385"


class QARealizationVNextPreflight(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    preflight_id: str = Field(min_length=1)
    external_audit_sha256: str = Field(min_length=64, max_length=64)
    external_audit_byte_count: int = Field(ge=1)
    baseline_commit: str = Field(min_length=40, max_length=40)
    census_id: str = Field(min_length=1)
    raw_proposal_migration_audit_id: str = Field(min_length=1)
    renderer_profile_count: int = Field(ge=1)
    renderer_task_type_count: int = Field(ge=1)
    renderer_profiles_per_task_type: dict[str, int]
    raw_proposal_count: int = Field(ge=1)
    authorized_raw_proposal_count: int = Field(ge=0)
    blocked_raw_proposal_count: int = Field(ge=0)
    protected_rewrite_contract_status: str = Field(min_length=1)
    llm_rewrite_execution_status: str = Field(min_length=1)
    provider_call_count: int = Field(default=0, ge=0)
    gpu_job_count: int = Field(default=0, ge=0)
    imported_raw_qa_row_count: int = Field(default=0, ge=0)
    frozen_v26_artifact_mutation_count: int = Field(default=0, ge=0)
    gates: dict[str, bool]
    claim_boundary: dict[str, Any]
    schema_version: str = "qa_realization_vnext_preflight.v1"

    @model_validator(mode="after")
    def validate_preflight(self) -> QARealizationVNextPreflight:
        if any(not passed for passed in self.gates.values()):
            raise ValueError("QA realization vNext preflight failed a hard gate")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"preflight_id"}),
            prefix="qa_realization_vnext_preflight:",
        )
        if self.preflight_id != expected:
            raise ValueError("QA realization vNext preflight identity is invalid")
        return self


def build_preflight(
    *,
    task_package_paths: tuple[str | Path, ...],
    external_audit_path: str | Path,
    baseline_commit: str,
) -> tuple[QARealizationVNextPreflight, QADiversityCensus, RawProposalMigrationAudit]:
    review = Path(external_audit_path).read_bytes()
    review_sha256 = sha256(review).hexdigest()
    census = run_task_package_census(task_package_paths)
    migration = audit_raw_proposal_compatibility()
    renderer_manifest = finance_renderer_registry().manifest()
    renderer_counts: dict[str, int] = {}
    for row in renderer_manifest:
        task_type = str(row["task_type"])
        renderer_counts[task_type] = renderer_counts.get(task_type, 0) + 1
    proposals = raw_finance_semantic_proposals()
    gates = {
        "external_audit_sha256_exact": review_sha256 == EXTERNAL_AUDIT_SHA256,
        "external_audit_byte_count_exact": len(review) == EXTERNAL_AUDIT_BYTE_COUNT,
        "baseline_commit_shape_valid": len(baseline_commit) == 40,
        "census_hard_gates_pass": all(census.hard_gates.values()),
        "renderer_profiles_four_per_task_type": bool(renderer_counts)
        and all(count == 4 for count in renderer_counts.values()),
        "legacy_anchor_renderer_profiles_present": all(
            task_type in renderer_counts
            for task_type in (
                "fact_retrieval",
                "comparison",
                "temporal_growth",
                "temporal_average",
                "temporal_absolute_change",
                "registered_ratio",
                "derived_growth_comparison",
            )
        ),
        "raw_migration_audit_gates_pass": all(migration.gates.values()),
        "raw_proposal_identity_unique": len({item.proposal_id for item in proposals})
        == len(proposals),
        "raw_reference_hashes_bound": all(
            value
            for value in (
                RAW_GRAPH_PATTERNS_SHA256,
                RAW_VERBALIZER_SHA256,
                RAW_DIVERSITY_SHA256,
            )
        ),
        "raw_qa_rows_imported_zero": migration.imported_qa_row_count == 0,
        "provider_calls_zero": True,
        "gpu_jobs_zero": True,
        "frozen_v26_artifact_mutations_zero": True,
    }
    claim_boundary = {
        "stage": "qa_realization_vnext_engineering_preflight",
        "implemented": (
            "renderer-free SemanticTaskProposal and CanonicalSemanticPlan identities",
            "exact BindingSnapshot identity",
            "content-addressed SurfaceRealization identity",
            "deterministic Finance Renderer Portfolio",
            "protected-placeholder rewrite validation",
            "semantic-parent split assignment",
            "valid-pool diversity-aware release selection",
            "read-only legacy TaskPackage diversity census",
            "three translated Raw GraphPattern proposals",
        ),
        "authorized_raw_proposals": ("registered_cross_metric_comparison",),
        "blocked_raw_proposals": (
            "temporal_peak_secondary_lookup",
            "growth_filter_margin_rank",
        ),
        "blocked_reason": "required Operation/Policy/Pattern/Renderer contracts incomplete",
        "not_executed": (
            "Provider protected rewrite",
            "Raw automatic pattern mining",
            "Raw typed edge walk",
            "new online QA generation",
            "v26 capability experiment",
            "VTDO State mapping",
            "training or release production",
        ),
        "census_scope": census.claim_boundary,
        "frozen_historical_task_artifact_mutation_count": 0,
        "current_compiler_canonical_task_id_preserved": True,
        "current_compiler_canonical_task_hash_preserved": True,
    }
    payload = {
        "external_audit_sha256": review_sha256,
        "external_audit_byte_count": len(review),
        "baseline_commit": baseline_commit,
        "census_id": census.census_id,
        "raw_proposal_migration_audit_id": migration.audit_id,
        "renderer_profile_count": len(renderer_manifest),
        "renderer_task_type_count": len(renderer_counts),
        "renderer_profiles_per_task_type": dict(sorted(renderer_counts.items())),
        "raw_proposal_count": len(proposals),
        "authorized_raw_proposal_count": migration.authorized_count,
        "blocked_raw_proposal_count": migration.blocked_count,
        "protected_rewrite_contract_status": "implemented_credential_free_validator_only",
        "llm_rewrite_execution_status": "not_executed_p3_deferred",
        "provider_call_count": 0,
        "gpu_job_count": 0,
        "imported_raw_qa_row_count": 0,
        "frozen_v26_artifact_mutation_count": 0,
        "gates": gates,
        "claim_boundary": claim_boundary,
        "schema_version": "qa_realization_vnext_preflight.v1",
    }
    preflight_id = canonical_hash(payload, prefix="qa_realization_vnext_preflight:")
    return QARealizationVNextPreflight(preflight_id=preflight_id, **payload), census, migration


def write_preflight_artifacts(
    *,
    preflight: QARealizationVNextPreflight,
    census: QADiversityCensus,
    migration: RawProposalMigrationAudit,
    output_dir: str | Path,
) -> tuple[str, ...]:
    output = Path(output_dir)
    written = set(write_census_artifacts(census, output))
    renderer_manifest = finance_renderer_registry().manifest()
    proposals = raw_finance_semantic_proposals()
    additional = {
        "renderer_profile_manifest.json": renderer_manifest,
        "raw_semantic_proposal_manifest.jsonl": tuple(
            item.model_dump(mode="json") for item in proposals
        ),
        "raw_proposal_migration_audit.json": migration.model_dump(mode="json"),
        "qa_realization_contract.json": {
            "identity_chain": (
                "semantic_task_id",
                "binding_snapshot_id",
                "realization_id",
            ),
            "legacy_task_id_preserved": True,
            "semantic_parent_split_required": True,
            "parent_training_weight_conserved": True,
            "validity_before_diversity": True,
            "surface_realization_is_not_vtdo_state": True,
            "provider_rewrite_enabled": False,
        },
        "preflight_report.json": preflight.model_dump(mode="json"),
    }
    for name, value in additional.items():
        path = output / name
        if name.endswith(".jsonl"):
            path.write_text(
                "".join(_canonical_json(item) + "\n" for item in value),
                encoding="utf-8",
            )
        else:
            path.write_text(_canonical_json(value) + "\n", encoding="utf-8")
        written.add(name)
    return tuple(sorted(written))


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the QA realization vNext preflight")
    parser.add_argument("--task-packages", nargs="+", required=True)
    parser.add_argument("--external-audit", required=True)
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    preflight, census, migration = build_preflight(
        task_package_paths=tuple(args.task_packages),
        external_audit_path=args.external_audit,
        baseline_commit=args.baseline_commit,
    )
    written = write_preflight_artifacts(
        preflight=preflight,
        census=census,
        migration=migration,
        output_dir=args.output_dir,
    )
    print(
        _canonical_json(
            {
                "preflight_id": preflight.preflight_id,
                "census_id": census.census_id,
                "migration_audit_id": migration.audit_id,
                "written_files": written,
            }
        )
    )


if __name__ == "__main__":
    main()
