from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from typing import Any, NoReturn

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.task.binding import make_evidence_binding
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.core.task.pattern_compiler import TaskPatternCompiler
from trusted_synthesis.core.task.realization import (
    QuestionRendererProfile,
    RealizedTaskPackage,
    realize_task,
)
from trusted_synthesis.core.task.semantic import build_semantic_binding_bundle
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.pattern_runtime import FinanceTaskPatternRuntime
from trusted_synthesis.domains.finance.question_rendering import finance_renderer_registry
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.qa_semantic_depth_three_plus.operations import (
    depth_three_operation_registry,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_plus.patterns import (
    DepthThreePatternRuntime,
    depth_three_patterns,
    depth_three_renderer_profiles,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_plus.preflight import (
    _fixture_inputs,
)

from . import models


class CatalogAdmissionError(ValueError):
    """A candidate Catalog or catalog-mediated execution failed a typed boundary."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise CatalogAdmissionError(stage, reason)


def _identified(values: dict[str, Any], field: str, prefix: str) -> dict[str, Any]:
    result = dict(values)
    result[field] = strict_canonical_hash(result, prefix=prefix)
    return result


def _manifest_hash(rows: Any) -> str:
    return strict_canonical_hash(rows, prefix="manifest:")


def catalog_operation_registry() -> OperationRegistry:
    """Return the historical Finance Registry plus the three audited extensions."""

    registry = finance_vnext_operation_registry()
    extension_source = depth_three_operation_registry()
    for operator_id in models.EXTENSION_OPERATION_IDS:
        registry.register(extension_source.require(operator_id))
    return registry


def historical_catalog_snapshot() -> dict[str, Any]:
    plugin = FinanceTaskPlugin()
    task_types = tuple(sorted(plugin.task_family_ids))
    patterns = tuple(
        {
            "task_type": item.task_type,
            "pattern_id": item.pattern_id,
            "pattern_version": item.pattern_version,
            "pattern_hash": item.pattern_hash,
            "instruction_renderer_id": item.instruction_renderer_id,
        }
        for item in plugin.pattern_manifest
    )
    renderers = finance_renderer_registry().manifest()
    operations = finance_vnext_operation_registry().manifest()
    if task_types != models.HISTORICAL_TASK_TYPES:
        _fail("historical_catalog.task_domain", "historical Finance task domain changed")
    return _identified(
        {
            "plugin_id": plugin.plugin_id,
            "realization_plugin_id": plugin.realization_plugin_id,
            "task_types": task_types,
            "task_count": len(task_types),
            "pattern_rows": patterns,
            "pattern_manifest_sha256": _manifest_hash(patterns),
            "renderer_manifest_sha256": _manifest_hash(renderers),
            "operation_manifest_sha256": _manifest_hash(operations),
            "historical_objects_modified": False,
            "schema_version": "finance_qa_historical_catalog_snapshot.v1",
        },
        "snapshot_id",
        "finance_qa_historical_catalog_snapshot:",
    )


def _task_rows() -> tuple[dict[str, Any], ...]:
    plugin = FinanceTaskPlugin()
    rows: list[dict[str, Any]] = []
    for pattern in plugin.pattern_manifest:
        rows.append(
            {
                "task_type": pattern.task_type,
                "pattern_id": pattern.pattern_id,
                "pattern_version": pattern.pattern_version,
                "pattern_hash": pattern.pattern_hash,
                "instruction_renderer_id": pattern.instruction_renderer_id,
                "runtime_id": FinanceTaskPatternRuntime.runtime_id,
                "registration_kind": "historical",
                "topology_kind": None,
            }
        )
    profiles = {item.task_type: item for item in depth_three_renderer_profiles()}
    for pattern in depth_three_patterns():
        rows.append(
            {
                "task_type": pattern.task_type,
                "pattern_id": pattern.pattern_id,
                "pattern_version": pattern.pattern_version,
                "pattern_hash": pattern.pattern_hash,
                "instruction_renderer_id": profiles[pattern.task_type].profile_id,
                "runtime_id": DepthThreePatternRuntime.runtime_id,
                "registration_kind": "depth_three_extension",
                "topology_kind": pattern.metadata["topology_kind"],
            }
        )
    return tuple(sorted(rows, key=lambda item: str(item["task_type"])))


def _operation_rows(registry: OperationRegistry) -> tuple[dict[str, Any], ...]:
    extension = set(models.EXTENSION_OPERATION_IDS)
    return tuple(
        {
            **row,
            "registration_kind": (
                "depth_three_extension" if row["operator_id"] in extension else "historical"
            ),
        }
        for row in registry.manifest()
    )


def validate_catalog_rows(
    task_rows: tuple[dict[str, Any], ...],
    operation_rows: tuple[dict[str, Any], ...],
) -> None:
    task_counts = Counter(str(row.get("task_type")) for row in task_rows)
    operation_counts = Counter(str(row.get("operator_id")) for row in operation_rows)
    if any(count != 1 for count in task_counts.values()):
        _fail("catalog.task_uniqueness", "Catalog repeats a task registration")
    if any(count != 1 for count in operation_counts.values()):
        _fail("catalog.operation_uniqueness", "Catalog repeats an Operation registration")
    historical = tuple(
        sorted(
            str(row["task_type"])
            for row in task_rows
            if row.get("registration_kind") == "historical"
        )
    )
    extensions = tuple(
        sorted(
            str(row["task_type"])
            for row in task_rows
            if row.get("registration_kind") == "depth_three_extension"
        )
    )
    if historical != models.HISTORICAL_TASK_TYPES:
        _fail("catalog.historical_domain", "historical task registrations differ")
    if extensions != models.EXTENSION_TASK_TYPES:
        _fail("catalog.extension_task_domain", "extension task registrations differ")
    extension_operations = tuple(
        sorted(
            str(row["operator_id"])
            for row in operation_rows
            if row.get("registration_kind") == "depth_three_extension"
        )
    )
    if extension_operations != models.EXTENSION_OPERATION_IDS:
        _fail("catalog.extension_operation_domain", "extension Operation registrations differ")
    if any(
        row.get("program_role") != "semantic"
        for row in operation_rows
        if row.get("registration_kind") == "depth_three_extension"
    ):
        _fail("catalog.operation_role", "extension Operation role is not semantic")

    actual_patterns = {
        item.task_type: item
        for item in (*FinanceTaskPlugin().pattern_manifest, *depth_three_patterns())
    }
    for row in task_rows:
        pattern = actual_patterns.get(str(row["task_type"]))
        if pattern is None or (
            row.get("pattern_id"),
            row.get("pattern_version"),
            row.get("pattern_hash"),
            row.get("instruction_renderer_id"),
        ) != (
            pattern.pattern_id,
            pattern.pattern_version,
            pattern.pattern_hash,
            pattern.instruction_renderer_id,
        ):
            _fail("catalog.pattern_relation", "task registration crosses its source Pattern")

    actual_operations = {
        str(row["operator_id"]): row for row in catalog_operation_registry().manifest()
    }
    for row in operation_rows:
        operator_id = str(row["operator_id"])
        comparable = {key: value for key, value in row.items() if key != "registration_kind"}
        if actual_operations.get(operator_id) != comparable:
            _fail("catalog.operation_relation", "Operation registration differs from Registry")

    available = set(operation_counts)
    required = {
        node.operator_id
        for pattern in actual_patterns.values()
        for node in pattern.program_template
    }
    if not required <= available:
        _fail("catalog.operation_closure", "registered Patterns reference missing Operations")


def build_catalog_descriptor(parent_snapshot_id: str) -> dict[str, Any]:
    registry = catalog_operation_registry()
    task_rows = _task_rows()
    operation_rows = _operation_rows(registry)
    validate_catalog_rows(task_rows, operation_rows)
    return _identified(
        {
            "catalog_version": "finance_qa_registered_catalog.v3-depth-three-preflight.1",
            "parent_historical_snapshot_id": parent_snapshot_id,
            "task_registrations": task_rows,
            "operation_registrations": operation_rows,
            "historical_task_count": 8,
            "extension_task_count": 2,
            "total_task_count": 10,
            "extension_operation_count": 3,
            "task_registration_set_sha256": _manifest_hash(task_rows),
            "operation_registration_set_sha256": _manifest_hash(operation_rows),
            "preflight_only": True,
            "catalog_promoted": False,
            "schema_version": "finance_qa_registered_catalog.v3",
        },
        "catalog_id",
        "finance_qa_registered_catalog:",
    )


@dataclass(frozen=True)
class ResolvedTask:
    receipt: dict[str, Any]
    pattern: TaskPatternSpec
    renderer: QuestionRendererProfile
    runtime: DepthThreePatternRuntime


class RegisteredFinanceQACatalog:
    """Runtime facade whose positive path starts with exact Catalog discovery."""

    def __init__(self, descriptor: dict[str, Any]) -> None:
        task_rows = tuple(descriptor["task_registrations"])
        operation_rows = tuple(descriptor["operation_registrations"])
        validate_catalog_rows(task_rows, operation_rows)
        expected = build_catalog_descriptor(str(descriptor["parent_historical_snapshot_id"]))
        if descriptor != expected:
            _fail("catalog.expected_bytes", "Catalog descriptor differs from expected bytes")
        self.descriptor = descriptor
        self.registry = catalog_operation_registry()
        self._task_rows = {str(row["task_type"]): row for row in task_rows}
        self._patterns = {item.task_type: item for item in depth_three_patterns()}
        self._renderers = {item.task_type: item for item in depth_three_renderer_profiles()}
        self._runtime = DepthThreePatternRuntime()

    def resolve(self, task_type: str) -> ResolvedTask:
        try:
            row = self._task_rows[task_type]
        except KeyError as exc:
            raise CatalogAdmissionError(
                "catalog.task_lookup", f"task type is not registered: {task_type}"
            ) from exc
        if row["registration_kind"] != "depth_three_extension":
            _fail("catalog.extension_lookup", "requested task is not a depth-three extension")
        pattern = self._patterns[task_type]
        renderer = self._renderers[task_type]
        receipt = _identified(
            {
                "catalog_id": self.descriptor["catalog_id"],
                "task_type": task_type,
                "task_registration_sha256": _manifest_hash(row),
                "pattern_id": pattern.pattern_id,
                "pattern_version": pattern.pattern_version,
                "pattern_hash": pattern.pattern_hash,
                "renderer_profile_id": renderer.profile_id,
                "renderer_profile_hash": renderer.profile_hash,
                "runtime_id": self._runtime.runtime_id,
                "schema_version": "finance_qa_catalog_resolution_receipt.v1",
            },
            "receipt_id",
            "finance_qa_catalog_resolution_receipt:",
        )
        return ResolvedTask(receipt, pattern, renderer, self._runtime)

    def control_input(self, task_type: str) -> tuple[EvidenceBundle, dict[str, tuple[str, ...]]]:
        self.resolve(task_type)
        case_id = {
            "derived_growth_absolute_spread": "branch_merge_growth_gap",
            "registered_margin_target_gap": "serial_margin_target_gap",
        }[task_type]
        return _fixture_inputs()[case_id]

    def compile_control(
        self,
        task_type: str,
        bundle: EvidenceBundle,
        role_bindings: dict[str, tuple[str, ...]],
    ) -> tuple[ResolvedTask, RealizedTaskPackage]:
        resolved = self.resolve(task_type)
        graph = ProofGraphBuilder().build(bundle)
        binding = make_evidence_binding(
            pattern_id=resolved.pattern.pattern_id,
            pattern_version=resolved.pattern.pattern_version,
            pattern_hash=resolved.pattern.pattern_hash,
            role_bindings=role_bindings,
            source_graph_id=graph.graph_id,
            domain_snapshot_id=graph.source_build_id,
        )
        instantiation = TaskPatternCompiler(self.registry, resolved.runtime).compile(
            resolved.pattern, binding, bundle, graph
        )
        semantic = build_semantic_binding_bundle(
            pattern=resolved.pattern,
            program=instantiation.program,
            binding=binding,
            bundle=bundle,
            proof_graph=graph,
            registry=self.registry,
            effective_answer_schema=instantiation.task.public.answer_schema,
        )
        by_id = {item.evidence_id: item for item in bundle.evidence}
        evidence_by_role = {
            role: tuple(by_id[evidence_id] for evidence_id in ids)
            for role, ids in role_bindings.items()
        }
        package = realize_task(
            plan=semantic.plan,
            binding=semantic.binding,
            instance=semantic.instance,
            task=instantiation.task,
            profile=resolved.renderer,
            slot_values=resolved.runtime.slot_values(task_type, evidence_by_role),
        )
        self.admit_package(task_type, resolved.receipt, package)
        return resolved, package

    def admit_package(
        self,
        task_type: str,
        receipt: dict[str, Any] | None,
        package: RealizedTaskPackage,
    ) -> None:
        expected = self.resolve(task_type).receipt
        if receipt != expected:
            _fail("catalog.resolution_receipt", "execution lacks exact Catalog resolution")
        if (
            package.task.public.task_type != task_type
            or package.task.oracle.task_program.program_id
            != package.semantic_plan.source_program_id
            or package.task.oracle.task_program.program_hash
            != package.semantic_plan.source_program_hash
        ):
            _fail("catalog.execution_lineage", "package crosses Catalog task lineage")


def catalog_manifest_sha256(descriptor: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(descriptor)).hexdigest()
