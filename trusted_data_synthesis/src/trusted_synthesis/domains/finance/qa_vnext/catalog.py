"""One domain Catalog for Finance QA patterns, operators and source-bound cases.

The historical experimental Catalog and its artifacts remain unchanged. This
entry resolves and compiles every default pattern through the same injected
OperationRegistry. Registration, source availability and compilation are separate
facts; neither a controlled fixture nor an old execution report supplies missing
source coverage or a new public-protocol execution result.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.plugins import TaskPatternRuntimeProtocol
from trusted_synthesis.core.task.binding import make_evidence_binding
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.core.task.pattern_compiler import (
    TaskPatternCompiler,
    TaskPatternInstantiation,
)
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.pattern_runtime import FinanceTaskPatternRuntime
from trusted_synthesis.domains.finance.patterns import finance_task_patterns
from trusted_synthesis.experiments.finance_pilot.sampler import discover_bindings
from trusted_synthesis.experiments.finance_pilot.schema import FinancePilotConfig
from trusted_synthesis.experiments.qa_semantic_depth_three_plus.operations import (
    depth_three_operation_registry,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_plus.patterns import (
    DepthThreePatternRuntime,
    depth_three_patterns,
)

CATALOG_VERSION = "finance.qa_vnext.catalog.v1"
DEPTH_OPERATIONS = (
    "absolute_percentage_point_gap",
    "scale_ratio_percent",
    "signed_percentage_point_gap",
)
FROZEN_SOURCE_DIRECTORY = (
    "trusted_data_synthesis/artifacts/qa_semantic_depth_three_archive_grounding/"
    "qa_semantic_operation_depth_three_plus_archive_grounded_parameter_space_"
    "constructibility_preflight_v1_20260904"
)
FROZEN_SOURCE_MANIFEST_ID = (
    "qa_archive_parameter_space_artifact_manifest:"
    "29dbf80f462d7dbf079df99e77d44dc5739b2a9ece8525356b43dc9ddc0f63b7"
)
FROZEN_SOURCE_ROOT_ID = (
    "qa_archive_parameter_space_artifact_root:"
    "b24d054bbf6cd5275675636f7a3f69fac127b2ab1a42483911c384c1cae60f98"
)
FROZEN_SOURCE_MANIFEST_SHA256 = "8a86354d574311631e0b38faa6acb79d13602291d4bcac350af0edfdb92b83c2"
SOURCE_MEMBERS = (
    (
        "evidence_bundles.jsonl",
        114_959,
        "ec5572e6a03c0f0b7e2b3ee0c322f174274501492fa5984b77e68da604831b2b",
    ),
    (
        "parameter_case_rows.jsonl",
        27_356,
        "5342394b93664a5e52872d68dbc222dee5226ad2d4f53aed70d5017991fbf15c",
    ),
    (
        "archive_binding.json",
        2_049,
        "548d291653e272d2b9652816edb7fbc6203d6666ae9f88dca7b03cb70248605c",
    ),
    (
        "archive_records.jsonl",
        1_104,
        "53f90bbba0961d6c6875578c00223b869178add291245ffb59bfe8547e51f85b",
    ),
)
ARCHIVE_PATH = "trusted_data_synthesis/benchmarks/finqa/frozen/test.json"
ARCHIVE_BYTES = 14_395_143
ARCHIVE_SHA256 = "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
ARCHIVE_ID = "qa_frozen_finqa_source_archive:" + ARCHIVE_SHA256


class CatalogAdmissionError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = self.stage = code
        super().__init__(code + (": " + detail if detail else ""))


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise CatalogAdmissionError(code, detail)


def _record(kind: str, **fields: Any) -> dict[str, Any]:
    body = {"schema_version": f"finance_qa_vnext_{kind}.v1", **copy.deepcopy(fields)}
    return {**body, "id": strict_canonical_hash(body, prefix=f"finance_qa_vnext_{kind}:")}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_start_date(item: EvidenceItem) -> date:
    value = item.temporal_context.valid_from
    _require(value is not None, "catalog.branch_source_start_date")
    assert value is not None
    return value


def catalog_operation_registry() -> OperationRegistry:
    """The actual historical Finance registry, including registered_compare, plus depth three."""
    registry = finance_vnext_operation_registry()
    extensions = depth_three_operation_registry()
    for operator_id in DEPTH_OPERATIONS:
        registry.register(extensions.require(operator_id))
    return registry


@dataclass(frozen=True)
class ResolvedTask:
    receipt: dict[str, Any]
    registration: dict[str, Any]
    pattern: TaskPatternSpec | None
    runtime: TaskPatternRuntimeProtocol | None


@dataclass(frozen=True)
class CatalogCase:
    case_id: str
    task_type: str
    task: TaskPackage
    bundle: EvidenceBundle
    proof_graph: ProofGraph
    corpus: EvidenceCorpus
    instantiation: TaskPatternInstantiation
    resolution: dict[str, Any]
    source_binding: dict[str, Any]

    def coverage_row(self) -> dict[str, Any]:
        """Only this exact instance's registration/source/compile facts; no runtime claims."""
        return _record(
            "source_coverage",
            case_id=self.case_id,
            task_type=self.task_type,
            registered=True,
            source_bindable=self.source_binding["source_bindable"],
            source_binding_status=self.source_binding["status"],
            source_binding_id=self.source_binding["id"],
            compiled=True,
            compilation_status="compiled",
            reason=None,
            catalog_id=self.resolution["catalog_id"],
            resolution_id=self.resolution["id"],
            task_id=self.task.public.task_id,
            task_hash=self.task.task_hash,
            evidence_bundle_id=self.bundle.bundle_id,
            evidence_bundle_hash=self.bundle.bundle_hash,
            proof_graph_id=self.proof_graph.graph_id,
            corpus_id=self.corpus.corpus_id,
            program_id=self.instantiation.program.program_id,
            program_hash=self.instantiation.program.program_hash,
            new_protocol_executable=None,
            qa_valid=None,
            trajectory_valid=None,
            model_executed=False,
            columns_from_one_case_only=True,
        )


@dataclass(frozen=True)
class _FrozenSourcePool:
    repository_root: Path
    scope: dict[str, Any]
    evidence: dict[str, EvidenceItem]
    branch_candidates: tuple[tuple[dict[str, Any], EvidenceBundle], ...]
    serial_candidates: tuple[dict[str, Any], ...]


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise CatalogAdmissionError("catalog.source_file_unavailable", str(path)) from error


def _jsonl(data: bytes) -> tuple[dict[str, Any], ...]:
    values = tuple(json.loads(line) for line in data.splitlines())
    _require(all(isinstance(value, dict) for value in values), "catalog.source_record_shape")
    return values


def _frozen_source_pool(repo_root: Path) -> _FrozenSourcePool:
    root = repo_root.resolve()
    directory = root / FROZEN_SOURCE_DIRECTORY
    raw_manifest = _read(directory / "artifact_manifest.json")
    _require(_sha(raw_manifest) == FROZEN_SOURCE_MANIFEST_SHA256, "catalog.source_manifest_bytes")
    manifest = json.loads(raw_manifest)
    _require(
        manifest["manifest_id"] == FROZEN_SOURCE_MANIFEST_ID
        and manifest["artifact_root"] == FROZEN_SOURCE_ROOT_ID,
        "catalog.source_manifest_identity",
    )
    members = []
    files = {}
    for name, size, digest in SOURCE_MEMBERS:
        data = _read(directory / name)
        _require(len(data) == size and _sha(data) == digest, "catalog.source_member_bytes", name)
        members.append({"relative_path": name, "sha256": digest, "byte_count": size})
        files[name] = data
    archive_raw = _read(root / ARCHIVE_PATH)
    _require(
        len(archive_raw) == ARCHIVE_BYTES and _sha(archive_raw) == ARCHIVE_SHA256,
        "catalog.archive_bytes",
    )
    archive_binding = json.loads(files["archive_binding.json"])
    _require(
        archive_binding["archive_id"] == ARCHIVE_ID
        and archive_binding["relative_path"] == ARCHIVE_PATH
        and archive_binding["sha256"] == ARCHIVE_SHA256
        and archive_binding["byte_count"] == ARCHIVE_BYTES,
        "catalog.archive_binding",
    )
    bundles = {
        bundle.bundle_id: bundle
        for bundle in (
            EvidenceBundle.model_validate(value)
            for value in _jsonl(files["evidence_bundles.jsonl"])
        )
    }
    case_rows = _jsonl(files["parameter_case_rows.jsonl"])
    branch = tuple(
        (row, bundles[row["evidence_bundle_id"]])
        for row in sorted(case_rows, key=lambda row: row["case_id"])
        if row["task_type"] == "derived_growth_absolute_spread" and row["constructible"] is True
    )
    serial = tuple(row for row in case_rows if row["task_type"] == "registered_margin_target_gap")
    _require(
        bool(branch)
        and len(branch) == len(bundles)
        and all(
            row["constructible"] is False
            and row["evidence_bundle_id"] is None
            and row["typed_blocker"] == "authoritative_gross_margin_target_evidence_absent"
            for row in serial
        ),
        "catalog.source_case_domain",
    )
    evidence: dict[str, EvidenceItem] = {}
    for _, bundle in branch:
        for item in bundle.evidence:
            _require(
                item.source.source_id == ARCHIVE_ID
                and item.provenance.archive_id == ARCHIVE_ID
                and item.source_locator.storage_uri == ARCHIVE_PATH
                and item.source_locator.document_version == ARCHIVE_SHA256
                and item.domain_context.get("archive_grounded") is True,
                "catalog.source_evidence_provenance",
            )
            _require(
                item.evidence_id not in evidence or evidence[item.evidence_id] == item,
                "catalog.source_evidence_identity",
            )
            evidence[item.evidence_id] = item
    scope = _record(
        "source_scope",
        source_kind="previously_frozen_real_finqa_table_cells",
        archive_path=ARCHIVE_PATH,
        archive_id=ARCHIVE_ID,
        archive_sha256=ARCHIVE_SHA256,
        archive_byte_count=ARCHIVE_BYTES,
        predecessor_directory=FROZEN_SOURCE_DIRECTORY,
        predecessor_manifest_id=FROZEN_SOURCE_MANIFEST_ID,
        predecessor_artifact_root=FROZEN_SOURCE_ROOT_ID,
        predecessor_manifest_sha256=FROZEN_SOURCE_MANIFEST_SHA256,
        selected_members=members,
        original_archive_binding_id=archive_binding["binding_id"],
        unique_cell_count=len(evidence),
        original_branch_binding_count=len(branch),
        original_uninstantiated_serial_count=len(serial),
        selected_source_record_ids=archive_binding["selected_record_ids"],
        source_claim="the admitted frozen table-cell adapter domain, not all financial sources",
        original_execution_or_qualification_rerun=False,
        original_artifacts_modified=False,
    )
    return _FrozenSourcePool(root, scope, evidence, branch, serial)


def _unverified_source_binding(bundle: EvidenceBundle, case_id: str) -> dict[str, Any]:
    return _record(
        "source_binding",
        case_id=case_id,
        status="supplied_evidence_not_source_revalidated",
        source_bindable=False,
        source_availability_claimed=False,
        evidence_bundle_id=bundle.bundle_id,
        evidence_bundle_hash=bundle.bundle_hash,
        reason="compiler inputs alone are not proof of real source availability",
    )


def _bound_source_binding(
    pool: _FrozenSourcePool, bundle: EvidenceBundle, case_id: str
) -> dict[str, Any]:
    _require(
        all(pool.evidence.get(item.evidence_id) == item for item in bundle.evidence),
        "catalog.source_evidence_substitution",
    )
    return _record(
        "source_binding",
        case_id=case_id,
        status="bound_frozen_finqa_archive",
        source_bindable=True,
        source_availability_claimed=True,
        repository_root=str(pool.repository_root),
        source_scope=pool.scope,
        source_scope_id=pool.scope["id"],
        evidence_bundle_id=bundle.bundle_id,
        evidence_bundle_hash=bundle.bundle_hash,
        evidence_references=[
            {
                "evidence_id": item.evidence_id,
                "evidence_version_id": item.evidence_version_id,
                "record_sha256": _sha(canonical_json_bytes(item.model_dump(mode="json"))),
                "source_record_id": item.provenance.source_record_id,
                "source_locator": item.source_locator.model_dump(mode="json"),
            }
            for item in bundle.evidence
        ],
        old_execution_results_are_new_protocol_coverage=False,
        reason=None,
    )


class FinanceQACatalog:
    """Extensible domain entry, not the old two-extension preflight facade."""

    def __init__(self, registry: OperationRegistry | None = None) -> None:
        self.registry = registry if registry is not None else catalog_operation_registry()
        expected = {row["operator_id"]: row for row in catalog_operation_registry().manifest()}
        actual = {row["operator_id"]: row for row in self.registry.manifest()}
        _require(
            all(actual.get(name) == row for name, row in expected.items()),
            "catalog.registry_closure",
            "the shared registry must retain exact historical and depth-three contracts",
        )
        self._registrations: dict[str, dict[str, Any]] = {}
        self._patterns: dict[str, TaskPatternSpec] = {}
        self._runtimes: dict[str, TaskPatternRuntimeProtocol] = {}
        historical_runtime = FinanceTaskPatternRuntime()
        extension_runtime = DepthThreePatternRuntime()
        _require(
            isinstance(extension_runtime.renderer_ids, tuple)
            and bool(extension_runtime.renderer_ids)
            and all(isinstance(value, str) and value for value in extension_runtime.renderer_ids),
            "catalog.extension_renderer_contract",
        )
        for pattern in finance_task_patterns():
            self.register_pattern(pattern, historical_runtime, registration_kind="historical")
        for pattern in depth_three_patterns():
            self.register_pattern(
                pattern,
                # The legacy runtime uses a fixed-length tuple; Catalog never mutates it.
                # register_pattern separately checks the domain and renderer membership.
                cast(TaskPatternRuntimeProtocol, extension_runtime),
                registration_kind="depth_three_extension",
            )

    @property
    def task_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._registrations))

    @property
    def task_family_ids(self) -> tuple[str, ...]:
        return self.task_types

    @property
    def descriptor(self) -> dict[str, Any]:
        registrations = [self._registrations[name] for name in self.task_types]
        return _record(
            "catalog",
            catalog_version=CATALOG_VERSION,
            task_registrations=registrations,
            operation_registrations=list(self.registry.manifest()),
            historical_task_count=sum(
                row["registration_kind"] == "historical" for row in registrations
            ),
            extension_task_count=sum(
                row["registration_kind"] != "historical" for row in registrations
            ),
            total_task_count=len(registrations),
            pattern_compilation_entry="FinanceQACatalog.compile",
            registered_does_not_mean_source_bindable_or_protocol_executed=True,
            old_experimental_catalog_or_artifacts_modified=False,
        )

    def register_pattern(
        self,
        pattern: TaskPatternSpec,
        runtime: TaskPatternRuntimeProtocol,
        *,
        registration_kind: str = "additional_pattern",
    ) -> None:
        _require(pattern.task_type not in self._registrations, "catalog.duplicate_task")
        _require(
            pattern.domain == runtime.domain == "finance"
            and pattern.instruction_renderer_id in runtime.renderer_ids,
            "catalog.pattern_runtime",
        )
        required = sorted({node.operator_id for node in pattern.program_template})
        for operator_id in required:
            self.registry.require(operator_id)
        self._patterns[pattern.task_type] = pattern
        self._runtimes[pattern.task_type] = runtime
        self._registrations[pattern.task_type] = {
            "task_type": pattern.task_type,
            "registration_kind": registration_kind,
            "compilation_kind": "task_pattern",
            "pattern_id": pattern.pattern_id,
            "pattern_version": pattern.pattern_version,
            "pattern_hash": pattern.pattern_hash,
            "runtime_id": runtime.runtime_id,
            "runtime_version": runtime.runtime_version,
            "instruction_renderer_id": pattern.instruction_renderer_id,
            "required_operations": required,
        }

    def register_adapter_family(
        self,
        task_type: str,
        adapter_id: str,
        required_operations: tuple[str, ...],
        contract_id: str,
        *,
        version: str = "1.0.0",
    ) -> None:
        _require(task_type not in self._registrations, "catalog.duplicate_task")
        _require(
            all(
                isinstance(value, str) and value
                for value in (task_type, adapter_id, contract_id, version)
            )
            and bool(required_operations)
            and len(set(required_operations)) == len(required_operations),
            "catalog.adapter_registration",
        )
        for operator_id in required_operations:
            self.registry.require(operator_id)
        self._registrations[task_type] = {
            "task_type": task_type,
            "registration_kind": "additional_adapter",
            "compilation_kind": "external_adapter",
            "adapter_id": adapter_id,
            "adapter_version": version,
            "contract_id": contract_id,
            "required_operations": sorted(required_operations),
        }

    def resolve(self, task_type: str) -> ResolvedTask:
        _require(task_type in self._registrations, "catalog.task_lookup", task_type)
        registration = self._registrations[task_type]
        receipt = _record(
            "resolution",
            catalog_id=self.descriptor["id"],
            task_type=task_type,
            registration=registration,
            registry_manifest=list(self.registry.manifest()),
        )
        return ResolvedTask(
            receipt,
            copy.deepcopy(registration),
            self._patterns.get(task_type),
            self._runtimes.get(task_type),
        )

    def bind_frozen_source(
        self, repo_root: Path, bundle: EvidenceBundle, *, case_id: str
    ) -> dict[str, Any]:
        return _bound_source_binding(_frozen_source_pool(repo_root), bundle, case_id)

    def _admit_source_binding(
        self, bundle: EvidenceBundle, case_id: str, source_binding: dict[str, Any]
    ) -> None:
        status = source_binding.get("status")
        if status == "supplied_evidence_not_source_revalidated":
            expected = _unverified_source_binding(bundle, case_id)
        elif status == "bound_frozen_finqa_archive":
            root = source_binding.get("repository_root")
            _require(isinstance(root, str), "catalog.source_repository")
            assert isinstance(root, str)
            expected = _bound_source_binding(_frozen_source_pool(Path(root)), bundle, case_id)
        else:
            raise CatalogAdmissionError("catalog.source_binding_status")
        _require(source_binding == expected, "catalog.source_binding_identity")

    def compile(
        self,
        task_type: str,
        bundle: EvidenceBundle,
        role_bindings: dict[str, tuple[str, ...]],
        *,
        case_id: str | None = None,
        source_binding: dict[str, Any] | None = None,
        node_parameters: dict[str, dict[str, Any]] | None = None,
    ) -> CatalogCase:
        resolved = self.resolve(task_type)
        pattern, runtime = resolved.pattern, resolved.runtime
        _require(
            pattern is not None and runtime is not None,
            "catalog.external_adapter_compilation_required",
            task_type,
        )
        assert pattern is not None and runtime is not None
        graph = ProofGraphBuilder().build(bundle)
        if node_parameters is None and task_type in {
            "registered_ratio",
            "registered_cross_metric_comparison",
        }:
            by_id = {item.evidence_id: item for item in bundle.evidence}
            role_names = (
                ("numerator", "denominator")
                if task_type == "registered_ratio"
                else ("left_metric", "right_metric")
            )
            try:
                left, right = (by_id[role_bindings[name][0]] for name in role_names)
            except (KeyError, IndexError) as error:
                raise CatalogAdmissionError("catalog.registered_pair_roles") from error
            node_parameters = {"result": {"registered_pair": f"{left.predicate}/{right.predicate}"}}
        binding = make_evidence_binding(
            pattern_id=pattern.pattern_id,
            pattern_version=pattern.pattern_version,
            pattern_hash=pattern.pattern_hash,
            role_bindings=role_bindings,
            source_graph_id=graph.graph_id,
            domain_snapshot_id=graph.source_build_id,
            node_parameters=node_parameters,
        )
        identifier = case_id or strict_canonical_hash(
            {"catalog_id": resolved.receipt["catalog_id"], "binding_hash": binding.binding_hash},
            prefix="finance_qa_vnext_case:",
        )
        source = source_binding or _unverified_source_binding(bundle, identifier)
        self._admit_source_binding(bundle, identifier, source)
        try:
            instantiation = TaskPatternCompiler(self.registry, runtime).compile(
                pattern, binding, bundle, graph
            )
        except ValueError as error:
            raise CatalogAdmissionError("catalog.compilation_rejected", str(error)) from error
        case = CatalogCase(
            identifier,
            task_type,
            instantiation.task,
            bundle,
            graph,
            EvidenceCorpus.from_bundle(bundle),
            instantiation,
            resolved.receipt,
            copy.deepcopy(source),
        )
        self.admit_case(case)
        return case

    def admit_case(self, case: CatalogCase) -> None:
        expected = self.resolve(case.task_type)
        _require(
            case.resolution == expected.receipt
            and case.task.public.task_type == case.task_type
            and case.instantiation.task == case.task
            and case.instantiation.program == case.task.oracle.task_program
            and case.instantiation.binding.source_graph_id == case.proof_graph.graph_id
            and case.corpus == EvidenceCorpus.from_bundle(case.bundle),
            "catalog.compiled_case_binding",
        )
        self._admit_source_binding(case.bundle, case.case_id, case.source_binding)

    def frozen_source_cases(
        self, repo_root: Path, task_types: tuple[str, ...] | None = None, limit_per_type: int = 1
    ) -> tuple[list[CatalogCase], list[dict[str, Any]]]:
        """Discover in one frozen 14-cell pool; return one honest row per selected instance.

        Default selection requests every Pattern type, not the old four-type
        Pilot quota. A type without an admitted binding still gets its own row.
        Additional adapter families use their explicitly registered source loader.
        """
        requested = task_types if task_types is not None else tuple(sorted(self._patterns))
        _require(
            type(limit_per_type) is int
            and limit_per_type > 0
            and bool(requested)
            and len(set(requested)) == len(requested),
            "catalog.source_request",
        )
        for task_type in requested:
            self.resolve(task_type)
        pool = _frozen_source_pool(repo_root)
        historical = tuple(
            name
            for name in requested
            if self._registrations[name]["registration_kind"] == "historical"
        )
        discovered = (
            discover_bindings(
                tuple(pool.evidence[key] for key in sorted(pool.evidence)),
                FinancePilotConfig(
                    task_quotas={name: limit_per_type for name in historical},
                    require_full_quota=False,
                ),
            )
            if historical
            else ()
        )
        cases: list[CatalogCase] = []
        coverage: list[dict[str, Any]] = []
        for task_type in requested:
            candidates: list[tuple[str, EvidenceBundle, dict[str, tuple[str, ...]]]] = []
            pattern = self._patterns.get(task_type)
            if task_type == "derived_growth_absolute_spread":
                for original, bundle in pool.branch_candidates[:limit_per_type]:
                    roles: dict[str, tuple[str, ...]] = {}
                    for predicate, prefix in (
                        ("revenue", "revenue"),
                        ("operating_income", "income"),
                    ):
                        selected = sorted(
                            (item for item in bundle.evidence if item.predicate == predicate),
                            key=_source_start_date,
                        )
                        _require(len(selected) == 2, "catalog.branch_source_roles")
                        roles[prefix + "_earlier"] = (selected[0].evidence_id,)
                        roles[prefix + "_later"] = (selected[1].evidence_id,)
                    candidates.append((original["case_id"], bundle, roles))
            elif pattern is not None:
                for source in (item for item in discovered if item.task_type == task_type):
                    identifier = task_type + "__" + source.binding_hash.rsplit(":", 1)[-1]
                    evidence = tuple(pool.evidence[key] for key in source.evidence_ids)
                    bundle = EvidenceBundle(
                        bundle_id=strict_canonical_hash(
                            {
                                "case_id": identifier,
                                "source_scope_id": pool.scope["id"],
                                "evidence_ids": source.evidence_ids,
                            },
                            prefix="finance_qa_vnext_source_bundle:",
                        ),
                        evidence=evidence,
                        purpose="QA-vNext compilation from exact previously frozen source cells",
                        graph_build_id="finance_qa_vnext_source_graph:" + identifier,
                        metadata={"source_scope_id": pool.scope["id"], "provider_generated": False},
                    )
                    if len(pattern.evidence_roles) == 1:
                        roles = {pattern.evidence_roles[0].role_id: source.evidence_ids}
                    else:
                        _require(
                            len(pattern.evidence_roles) == len(source.evidence_ids),
                            "catalog.source_role_cardinality",
                        )
                        roles = {
                            role.role_id: (evidence_id,)
                            for role, evidence_id in zip(
                                pattern.evidence_roles, source.evidence_ids, strict=True
                            )
                        }
                    candidates.append((identifier, bundle, roles))
            if not candidates:
                reason = (
                    "authoritative_gross_margin_target_evidence_absent"
                    if task_type == "registered_margin_target_gap"
                    else "registered_adapter_requires_own_source_loader"
                    if pattern is None
                    else "no_admissible_binding_in_this_frozen_source_pool"
                )
                coverage.append(
                    _record(
                        "source_coverage",
                        case_id=None,
                        task_type=task_type,
                        registered=True,
                        source_bindable=False,
                        source_binding_status="not_instantiated",
                        source_binding_id=None,
                        source_scope_id=pool.scope["id"],
                        compiled=False,
                        compilation_status="not_instantiated",
                        reason=reason,
                        catalog_id=self.descriptor["id"],
                        resolution_id=self.resolve(task_type).receipt["id"],
                        task_id=None,
                        new_protocol_executable=None,
                        qa_valid=None,
                        trajectory_valid=None,
                        model_executed=False,
                        columns_from_one_case_only=True,
                    )
                )
            for identifier, bundle, roles in candidates:
                source_binding = _bound_source_binding(pool, bundle, identifier)
                try:
                    case = self.compile(
                        task_type, bundle, roles, case_id=identifier, source_binding=source_binding
                    )
                except CatalogAdmissionError as error:
                    coverage.append(
                        _record(
                            "source_coverage",
                            case_id=identifier,
                            task_type=task_type,
                            registered=True,
                            source_bindable=True,
                            source_binding_status=source_binding["status"],
                            source_binding_id=source_binding["id"],
                            source_scope_id=pool.scope["id"],
                            compiled=False,
                            compilation_status="compilation_rejected",
                            reason=str(error),
                            catalog_id=self.descriptor["id"],
                            resolution_id=self.resolve(task_type).receipt["id"],
                            task_id=None,
                            new_protocol_executable=None,
                            qa_valid=None,
                            trajectory_valid=None,
                            model_executed=False,
                            columns_from_one_case_only=True,
                        )
                    )
                else:
                    cases.append(case)
                    coverage.append(case.coverage_row())
        return cases, coverage
