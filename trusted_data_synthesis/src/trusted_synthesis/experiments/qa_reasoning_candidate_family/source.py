"""Construct finite candidates from frozen sources, without executing any route.

The direct-evidence candidate uses the already implemented TaskProgram reference
grammar. It removes four transparent projections, not a registered semantic
operation. Its existence establishes neither a distinct behavior nor a quotient
class. Source checks never call an Operation executor or Oracle verifier.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.operations.registry import operation_semantic_contract
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    TaskProgram,
    make_program,
)
from trusted_synthesis.core.task.realization import RealizedTaskPackage
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    build_catalog_descriptor,
    catalog_operation_registry,
    historical_catalog_snapshot,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_plus.patterns import (
    depth_three_patterns,
)

from . import models

_SOURCE_BASE = "trusted_data_synthesis/src/trusted_synthesis/"
_SOURCE_PATHS = (
    "core/task/program.py",
    "core/task/pattern.py",
    "core/task/pattern_compiler.py",
    "core/task/program_depth.py",
    "core/operations/schema.py",
    "core/operations/registry.py",
    "core/operations/program.py",
    "core/operations/executors/numeric.py",
    "core/operations/verifiers/numeric.py",
    "core/trajectory/candidate_verifier.py",
    "domains/finance/operations.py",
    "domains/finance/patterns.py",
    "experiments/qa_semantic_depth_three_plus/operations.py",
    "experiments/qa_semantic_depth_three_plus/patterns.py",
    "experiments/qa_semantic_depth_three_catalog_integration/catalog.py",
    "experiments/qa_reasoning_behavior_design/contracts.py",
)
_ARCHIVE_MEMBERS = (
    "parameter_case_rows.jsonl",
    "evidence_bundles.jsonl",
    "realized_task_packages.jsonl",
    "catalog_freeze.json",
    "catalog_resolution_receipts.jsonl",
)


def _fail(stage: str, reason: str) -> None:
    raise models.CandidateFamilyError(stage, reason)


def _binding(value: Any) -> dict[str, Any]:
    data = canonical_json_bytes(value)
    return {"sha256": hashlib.sha256(data).hexdigest(), "byte_count": len(data)}


def _file_binding(repo_root: Path, relative_path: str) -> dict[str, Any]:
    data = (repo_root / relative_path).read_bytes()
    return {
        "relative_path": relative_path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_count": len(data),
    }


def _jsonl_index(
    path: Path, key: str, *, allow_identical_duplicates: bool = False
) -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    result = {str(row[key]): row for row in rows}
    if len(result) != len(rows) and (
        not allow_identical_duplicates
        or any(
            canonical_json_bytes(row) != canonical_json_bytes(result[str(row[key])]) for row in rows
        )
    ):
        _fail("source.unique_rows", f"duplicate or colliding identity in {path.name}")
    return result


def _freeze_archive(repo_root: Path) -> dict[str, Any]:
    """Verify every archived byte, including the fixed manifest and member Root."""

    directory = repo_root / models.ARCHIVE_DIRECTORY
    paths = tuple(directory.rglob("*"))
    if directory.is_symlink() or any(path.is_symlink() for path in paths):
        _fail("source.archive_path", "Archive must contain actual files, not symbolic aliases")
    files = {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in paths
        if path.is_file()
    }
    manifest_bytes = files.get("artifact_manifest.json", b"")
    if (
        len(files) != models.ARCHIVE_FILE_COUNT
        or sum(map(len, files.values())) != models.ARCHIVE_TOTAL_BYTES
        or len(manifest_bytes) != models.ARCHIVE_MANIFEST_BYTES
        or hashlib.sha256(manifest_bytes).hexdigest() != models.ARCHIVE_MANIFEST_SHA256
    ):
        _fail("source.archive_bytes", "Archive file count, bytes or fixed Manifest differs")
    manifest = json.loads(manifest_bytes)
    members = manifest["members"]
    member_paths = tuple(member["relative_path"] for member in members)
    if (
        manifest["manifest_id"] != models.ARCHIVE_MANIFEST_ID
        or manifest["artifact_root"] != models.ARCHIVE_ROOT_ID
        or manifest["file_count"] != models.ARCHIVE_MEMBER_COUNT
        or manifest["member_bytes"] != models.ARCHIVE_MEMBER_BYTES
        or len(members) != models.ARCHIVE_MEMBER_COUNT
        or len(set(member_paths)) != len(member_paths)
        or set(member_paths) != set(files) - {"artifact_manifest.json"}
        or sum(len(files[relative]) for relative in member_paths) != models.ARCHIVE_MEMBER_BYTES
        or strict_canonical_hash(
            {key: value for key, value in manifest.items() if key != "manifest_id"},
            prefix="qa_archive_parameter_space_artifact_manifest:",
        )
        != models.ARCHIVE_MANIFEST_ID
        or strict_canonical_hash(members, prefix="qa_archive_parameter_space_artifact_root:")
        != models.ARCHIVE_ROOT_ID
    ):
        _fail("source.archive_manifest", "Archive Manifest paths or content-addressed Root differs")
    if any(
        member["byte_count"] != len(files[member["relative_path"]])
        or member["sha256"] != hashlib.sha256(files[member["relative_path"]]).hexdigest()
        for member in members
    ):
        _fail("source.archive_member", "Archive member bytes differ from frozen Manifest")
    return {
        "directory": models.ARCHIVE_DIRECTORY,
        "file_count": len(files),
        "total_bytes": sum(map(len, files.values())),
        "member_count": len(members),
        "member_bytes": manifest["member_bytes"],
        "manifest_id": manifest["manifest_id"],
        "artifact_root": manifest["artifact_root"],
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "all_member_paths_and_bytes_verified": True,
        "all_archive_bytes_used_only_for_integrity_not_candidate_outcome_selection": True,
    }


def _fixture_type_checks(fixture: dict[str, Any]) -> dict[str, Any]:
    package, bundle, roles = fixture["package"], fixture["bundle"], fixture["roles"]
    if set(roles) != set(models.ROLE_ORDER) or len(bundle.evidence) != 4:
        _fail("source.evidence_domain", "fixture must preserve exactly four source roles")
    if any(not isinstance(item.payload, ScalarObservation) for item in roles.values()):
        _fail("source.evidence_type", "fixture roles must contain registered scalar payloads")
    if any(not Decimal(str(item.payload.value)).is_finite() for item in roles.values()):
        _fail("source.finite_numeric", "fixture source contains nonfinite numeric data")
    if tuple(package.task.oracle.gold_evidence_ids) != tuple(
        item.evidence_id for item in bundle.evidence
    ):
        _fail("source.gold_evidence", "frozen citation order differs from source universe")
    if len({item.subject.subject_id for item in roles.values()}) != 1:
        _fail("source.subject", "fixture sources do not preserve one subject")
    registry = catalog_operation_registry()
    for metric, earlier, later in (
        ("revenue", "revenue_earlier", "revenue_later"),
        ("operating_income", "income_earlier", "income_later"),
    ):
        first, second = roles[earlier], roles[later]
        if first.predicate != metric or second.predicate != metric:
            _fail("source.metric_role", "frozen source metric role differs")
        if Decimal(str(first.payload.value)) <= 0:
            _fail("source.positive_base", "registered branch pattern requires positive bases")
        first_key = first.domain_context.get("economic_period_sort_key")
        second_key = second.domain_context.get("economic_period_sort_key")
        if first_key is None or second_key is None or first_key >= second_key:
            _fail("source.period_role", "source roles do not preserve strict economic periods")
        registry.validate_compatibility(registry.require("growth"), (first, second), {})
    for suffix in ("earlier", "later"):
        if roles[f"revenue_{suffix}"].domain_context.get("economic_period_sort_key") != roles[
            f"income_{suffix}"
        ].domain_context.get("economic_period_sort_key"):
            _fail("source.aligned_window", "growth branches have different economic windows")
    pattern = next(
        item
        for item in depth_three_patterns()
        if item.task_type == "derived_growth_absolute_spread"
    )
    program = package.task.oracle.task_program
    if len(program.nodes) != len(pattern.program_template):
        _fail("source.registered_template", "frozen Oracle is not the registered source template")
    for template, node in zip(pattern.program_template, program.nodes, strict=True):
        if (
            node.node_id != template.node_role_id
            or node.operator_id != template.operator_id
            or node.output_schema != template.output_schema
            or node.parameters != template.parameters
        ):
            _fail("source.registered_template", "Oracle node differs from registered template")
        expected_refs = tuple(
            (
                InputRefKind.EVIDENCE.value
                if ref.kind.value == "evidence_role"
                else InputRefKind.OPERATION.value,
                roles[ref.ref_id].evidence_id if ref.kind.value == "evidence_role" else ref.ref_id,
                ref.selector,
            )
            for ref in template.input_refs
        )
        if (
            tuple((ref.kind.value, ref.ref_id, ref.selector) for ref in node.input_refs)
            != expected_refs
        ):
            _fail(
                "source.registered_template", "Oracle operands differ from registered source roles"
            )
        registry.validate_node_contract(node)
    return {
        "passed": True,
        "only_source_role_type_and_nonzero_preconditions_checked": True,
        "operation_executor_invocations": 0,
        "operation_oracle_invocations": 0,
        "outcome_based_selection": False,
        "registered_pattern_id": pattern.pattern_id,
        "registered_pattern_version": pattern.pattern_version,
        "registered_pattern_hash": pattern.pattern_hash,
    }


def source_inventory(repo_root: Path) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Load exactly the two fixed identities; saved successes are not selection criteria."""

    repo_root = Path(repo_root)
    archive_freeze = _freeze_archive(repo_root)
    archive = repo_root / models.ARCHIVE_DIRECTORY
    rows = _jsonl_index(archive / "parameter_case_rows.jsonl", "row_id")
    bundles = _jsonl_index(archive / "evidence_bundles.jsonl", "bundle_id")
    packages = _jsonl_index(archive / "realized_task_packages.jsonl", "realized_package_id")
    receipts = _jsonl_index(
        archive / "catalog_resolution_receipts.jsonl", "receipt_id", allow_identical_duplicates=True
    )
    freeze = json.loads((archive / "catalog_freeze.json").read_text(encoding="utf-8"))
    descriptor = build_catalog_descriptor(historical_catalog_snapshot()["snapshot_id"])
    descriptor_artifact_bytes = canonical_json_bytes(descriptor) + b"\n"
    if (
        descriptor["catalog_id"] != models.FROZEN_CATALOG_ID
        or descriptor["catalog_id"] != freeze["catalog_id"]
        or hashlib.sha256(descriptor_artifact_bytes).hexdigest()
        != freeze["catalog_descriptor_sha256"]
        or len(descriptor_artifact_bytes) != freeze["catalog_descriptor_byte_count"]
    ):
        _fail("source.catalog_freeze", "current registered catalog differs from frozen Archive")
    fixtures = []
    fixture_bindings = []
    for fixture_id, case_id, row_id, task_id in models.FIXTURE_SPECS:
        row = rows[row_id]
        bundle = EvidenceBundle.model_validate(bundles[row["evidence_bundle_id"]])
        package = RealizedTaskPackage.model_validate(packages[row["realized_package_id"]])
        receipt = receipts[row["resolution_receipt_id"]]
        if (
            row["case_id"] != case_id
            or package.task.task_id != task_id
            or row["task_type"] != "derived_growth_absolute_spread"
            or package.binding_snapshot.bundle_id != bundle.bundle_id
            or package.task.oracle.task_program.program_id != row["source_program_id"]
            or package.task.oracle.task_program.program_hash != row["source_program_hash"]
            or row["catalog_id"] != descriptor["catalog_id"]
            or receipt["catalog_id"] != descriptor["catalog_id"]
            or receipt["task_type"] != row["task_type"]
        ):
            _fail("source.fixture_parent", f"frozen source parent differs for {fixture_id}")
        evidence = {item.evidence_id: item for item in bundle.evidence}
        bindings = package.binding_snapshot.role_bindings
        if any(len(ids) != 1 or ids[0] not in evidence for ids in bindings.values()):
            _fail("source.role_binding", "source role must resolve exactly once in frozen Evidence")
        roles = {role: evidence[ids[0]] for role, ids in bindings.items()}
        scope = models.identified(
            {
                "fixture_id": fixture_id,
                "case_id": case_id,
                "task_id": task_id,
                "row_id": row_id,
                "row_bytes": _binding(row),
                "realized_package_id": package.realized_package_id,
                "package_bytes": _binding(package),
                "task_bytes": _binding(package.task),
                "question": package.task.public.instruction,
                "evidence_bundle_id": bundle.bundle_id,
                "evidence_universe_bytes": _binding(bundle),
                "role_bindings": bindings,
                "role_source_bytes": {role: _binding(item) for role, item in roles.items()},
                "answer_oracle_program_id": package.task.oracle.task_program.program_id,
                "answer_oracle_bytes": _binding(package.task.oracle),
                "answer_schema": package.semantic_plan.answer_schema,
                "answer_unit": "percentage_points",
                "numeric_contract": {"mode": "exact_decimal", "tolerance": "0", "rounding": "none"},
                "citation_evidence_ids": package.task.oracle.gold_evidence_ids,
                "citation_selection_contract": package.task.oracle.selection_contract,
                "catalog_resolution_receipt": receipt,
                "source_program_is_answer_authority_not_unique_candidate_route": True,
                "field_origin": "frozen_contract",
                "schema_version": "qa_reasoning_candidate_scope_binding.v1",
            },
            "scope_binding_id",
            "qa_reasoning_candidate_scope_binding:",
        )
        fixture = {
            "fixture_id": fixture_id,
            "case_id": case_id,
            "row": row,
            "bundle": bundle,
            "package": package,
            "roles": roles,
            "task_id": task_id,
            "task_instance_id": task_id,
            "scope_bindings": scope,
        }
        fixture["source_type_check"] = _fixture_type_checks(fixture)
        fixtures.append(fixture)
        fixture_bindings.append({**scope, "source_type_check": fixture["source_type_check"]})
    registry = catalog_operation_registry()
    inventory = models.identified(
        {
            "stage": models.STAGE,
            "archive_freeze": archive_freeze,
            "catalog_descriptor": descriptor,
            "catalog_descriptor_bytes": _binding(descriptor),
            "archived_catalog_descriptor_jsonl_bytes": {
                "sha256": hashlib.sha256(descriptor_artifact_bytes).hexdigest(),
                "byte_count": len(descriptor_artifact_bytes),
            },
            "registered_operation_semantics": tuple(
                operation_semantic_contract(registry.require(str(row["operator_id"])))
                for row in descriptor["operation_registrations"]
            ),
            "source_file_bindings": tuple(
                _file_binding(repo_root, _SOURCE_BASE + relative) for relative in _SOURCE_PATHS
            ),
            "archive_member_bindings": tuple(
                _file_binding(repo_root, models.ARCHIVE_DIRECTORY + "/" + member)
                for member in _ARCHIVE_MEMBERS
            ),
            "fixture_bindings": tuple(fixture_bindings),
            "selection": {
                "rule": "exact prior F1 then F2 identities; no reselection",
                "row_ids": tuple(spec[2] for spec in models.FIXTURE_SPECS),
                "historical_outcome_fields_used_for_selection": (),
                "candidate_executor_calls_before_freeze": 0,
                "candidate_oracle_calls_before_freeze": 0,
            },
            "finite_language": {
                "task_count": 2,
                "source_forms": ("registered_lookup_backed", "registered_direct_evidence"),
                "primary_axis": "registered_derivation_dependencies",
                "semantic_operations_preserved": (
                    "growth",
                    "growth",
                    "signed_percentage_point_gap",
                    "absolute_percentage_point_gap",
                ),
                "registered_projection_optional_in_direct_form": "lookup",
                "max_registered_actions": models.MAX_REGISTERED_ACTIONS,
                "max_main_candidates": models.MAX_MAIN_CANDIDATES,
                "max_positive_executions_including_controls": models.MAX_POSITIVE_EXECUTIONS,
                "arbitrary_registered_DAG_enumeration": False,
                "new_operations_or_algebraic_rules": (),
                "new_evidence_or_tasks": (),
                "not_a_complete_search_of_all_registered_programs": True,
            },
            "source_census": (
                {
                    "candidate_form": "registered_direct_evidence",
                    "status": "admissible_registered_direct_evidence_candidate",
                    "basis": (
                        "TaskProgram v2 permits Evidence payload value selectors; growth "
                        "inputs are ordered numeric"
                    ),
                    "retained_semantic_alternative_status": "not_established",
                    "semantic_distinctness_claim": False,
                },
                {
                    "candidate_form": "growth_to_compare",
                    "status": "outside_declared_candidate_bound",
                    "reason": (
                        "compare requires same_unit_and_definition lineage; the "
                        "registered derived comparison Pattern requires the same metric "
                        "and distinct subjects, unlike these fixed cross-metric "
                        "same-subject tasks"
                    ),
                },
                {
                    "candidate_form": "growth_formula_decomposition_or_reverse_signed_gap",
                    "status": "required_operation_or_composition_rule_absent",
                    "reason": (
                        "no such route is licensed by the bounded source forms; generic "
                        "numeric acceptance does not register a growth rewrite or "
                        "substitution of signed operand roles"
                    ),
                    "global_impossibility_claim": False,
                },
            ),
            "validator_boundary": {
                "operation_replay_entry": "TaskProgramOracleVerifier.verify",
                "registered_execution_entry": "OperationDefinition.executor.execute",
                "own_route_validator_required": True,
                "old_candidate_workflow_verifier_not_used_as_unique_route_authority": True,
                "reason": (
                    "old hidden-plan verification loops over all frozen Oracle nodes and "
                    "cannot establish missing lookup acceptance for a four-node candidate"
                ),
                "role_and_unit_validation_required_beyond_numeric_registry": True,
            },
            "provider_calls": 0,
            "schema_version": "qa_reasoning_candidate_source_inventory.v1",
        },
        "inventory_id",
        "qa_reasoning_candidate_source_inventory:",
    )
    return inventory, tuple(fixtures)


def _program(fixture: dict[str, Any], group: str) -> TaskProgram:
    original = fixture["package"].task.oracle.task_program
    source_nodes = {node.node_id: node for node in original.nodes}
    kept = tuple(node for node in original.nodes if group != "A" or node.operator_id != "lookup")
    namespace = f"candidate-{fixture['fixture_id'].lower()}-{group.lower()}"
    renamed = {node.node_id: f"{namespace}-node-{index:02d}" for index, node in enumerate(kept, 1)}
    nodes = []
    for node in kept:
        refs = []
        for ref in node.input_refs:
            if ref.kind == InputRefKind.EVIDENCE:
                refs.append(ref)
            elif ref.ref_id in renamed:
                refs.append(ref.model_copy(update={"ref_id": renamed[ref.ref_id]}))
            else:
                projection = source_nodes[ref.ref_id]
                registry = catalog_operation_registry()
                if (
                    group != "A"
                    or registry.require(projection.operator_id).program_role
                    != "transparent_projection"
                    or projection.operator_id != "lookup"
                    or len(projection.input_refs) != 1
                    or projection.input_refs[0].kind != InputRefKind.EVIDENCE
                    or projection.input_refs[0].selector is not None
                    or ref.selector != "payload.value"
                ):
                    _fail(
                        "source.direct_evidence_rule",
                        "projection does not support direct scalar selection",
                    )
                refs.append(
                    ProgramInputRef(
                        kind=InputRefKind.EVIDENCE,
                        ref_id=projection.input_refs[0].ref_id,
                        selector="value",
                    )
                )
        nodes.append(
            OperationNode(
                node_id=renamed[node.node_id],
                operator_id=node.operator_id,
                input_refs=tuple(refs),
                parameters=node.parameters,
                output_schema=node.output_schema,
                verifier_id=node.verifier_id,
                dependencies=tuple(
                    dict.fromkeys(ref.ref_id for ref in refs if ref.kind == InputRefKind.OPERATION)
                ),
            )
        )
    return make_program(tuple(nodes), renamed[original.output_node_id])


def _source_type_check(fixture: dict[str, Any], program: TaskProgram) -> dict[str, Any]:
    registry = catalog_operation_registry()
    evidence = {item.evidence_id: item for item in fixture["bundle"].evidence}
    inferred: dict[str, str] = {}
    direct_refs = 0
    for node in program.nodes:
        definition = registry.validate_node_contract(node)
        cardinality = definition.input_schema.split(":", 1)[0]
        if len(node.input_refs) != {"one": 1, "two": 2}[cardinality] or node.parameters:
            _fail("source.input_contract", "candidate exceeds the empty-parameter finite language")
        for ref in node.input_refs:
            if ref.kind == InputRefKind.EVIDENCE:
                item = evidence.get(ref.ref_id)
                if item is None or not isinstance(item.payload, ScalarObservation):
                    _fail(
                        "source.candidate_evidence",
                        "candidate ref is outside typed source universe",
                    )
                allowed = (None,) if node.operator_id == "lookup" else ("value",)
                if ref.selector not in allowed:
                    _fail("source.selector", "candidate Evidence selector differs from source rule")
                direct_refs += 1
            else:
                if ref.ref_id not in inferred:
                    _fail("source.dependency", "candidate consumes a future or absent producer")
                expected = "payload.value" if inferred[ref.ref_id] == "payload" else "value"
                if ref.selector != expected:
                    _fail(
                        "source.selector",
                        "candidate output selector differs from registered contract",
                    )
        inferred[node.node_id] = definition.output_schema
    count = Counter(node.operator_id for node in program.nodes)
    if (
        count["growth"] != 2
        or count["signed_percentage_point_gap"] != 1
        or count["absolute_percentage_point_gap"] != 1
        or count["lookup"] not in (0, 4)
        or len(program.nodes) != 4 + count["lookup"]
        or len(program.nodes) > models.MAX_REGISTERED_ACTIONS
    ):
        _fail("source.finite_language", "candidate is outside the declared finite source forms")
    return {
        "passed": True,
        "registered_action_count": len(program.nodes),
        "semantic_operation_count": 4,
        "transparent_projection_count": count["lookup"],
        "direct_evidence_ref_count": direct_refs,
        "operation_executor_invocations": 0,
        "operation_oracle_invocations": 0,
        "answer_outcome_inspected": False,
        "actual_validity_status": "pending_own_execution_and_independent_validation",
    }


def _obligations(fixture: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    roles = fixture["roles"]
    all_ids = tuple(roles[role].evidence_id for role in models.ROLE_ORDER)
    return (
        {
            "kind": "source_comparability",
            "required_evidence_ids": all_ids,
            "requires": (),
            "discharge": (
                "same subject, aligned ordered periods, fixed metrics, definitions, "
                "units, authority and positive bases"
            ),
        },
        {
            "kind": "revenue_growth",
            "required_evidence_ids": all_ids[:2],
            "requires": ("source_comparability",),
            "discharge": "registered growth with revenue earlier/later ordered roles",
        },
        {
            "kind": "operating_income_growth",
            "required_evidence_ids": all_ids[2:],
            "requires": ("source_comparability",),
            "discharge": "registered growth with operating-income earlier/later ordered roles",
        },
        {
            "kind": "absolute_growth_spread",
            "required_evidence_ids": all_ids,
            "requires": ("revenue_growth", "operating_income_growth"),
            "discharge": (
                "registered signed observed revenue minus reference income gap, then "
                "absolute percentage-point magnitude"
            ),
        },
        {
            "kind": "final_answer_and_citations",
            "required_evidence_ids": all_ids,
            "requires": ("absolute_growth_spread",),
            "discharge": (
                "frozen exact answer schema, percentage-point unit, Oracle and source citations"
            ),
        },
    )


def build_family(
    fixtures: tuple[dict[str, Any], ...], inventory: dict[str, Any]
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Choose exactly B/A/C in source order before any route is executed."""

    if tuple(fixture["fixture_id"] for fixture in fixtures) != ("F1", "F2"):
        _fail("source.fixture_order", "finite family must use the exact F1/F2 order")
    candidates = []
    kinds = {
        "B": "registered_lookup_backed_baseline",
        "A": "registered_direct_evidence_projection",
        "C": "baseline_independent_growth_swap_control",
    }
    for fixture in fixtures:
        for group in models.GROUP_ORDER:
            program = _program(fixture, group)
            schedule = [node.node_id for node in program.nodes]
            if group == "C":
                positions = [
                    index
                    for index, node in enumerate(program.nodes)
                    if node.operator_id == "growth"
                ]
                first, second = positions
                schedule[first], schedule[second] = schedule[second], schedule[first]
            candidate = models.identified(
                {
                    "fixture_id": fixture["fixture_id"],
                    "case_id": fixture["case_id"],
                    "task_id": fixture["task_id"],
                    "task_instance_id": fixture["task_id"],
                    "group": group,
                    "route_kind": kinds[group],
                    "program": program,
                    "program_json": program.model_dump(mode="json"),
                    "schedule": tuple(schedule),
                    "scheduled_node_ids": tuple(schedule),
                    "source_inventory_id": inventory["inventory_id"],
                    "scope_binding_id": fixture["scope_bindings"]["scope_binding_id"],
                    "source_rule_bindings": {
                        "catalog_id": models.FROZEN_CATALOG_ID,
                        "source_pattern_id": "finance.experimental.derived_growth_absolute_spread",
                        "source_pattern_version": "1.0.0",
                        "program_schema": "task_program.v2",
                        "reference_grammar_symbols": (
                            "core.task.program.InputRefKind.EVIDENCE",
                            "core.task.program.ProgramInputRef.selector",
                            "core.operations.program._resolve_inputs",
                            "core.operations.program._select_value",
                        ),
                        "projection_registration": "lookup.program_role=transparent_projection",
                        "existing_projection_semantics_source": (
                            "core.trajectory.candidate_verifier._collapse_transparent_ref"
                        ),
                        "ordered_operand_contracts_preserved": True,
                        "algebraic_rewrite_applied": False,
                        "new_registry_entries": (),
                        "semantic_difference_not_assumed": True,
                    },
                    "obligation_specs": _obligations(fixture),
                    "field_provenance": {
                        "scope_bindings": "frozen_contract",
                        "source_rule_bindings": "frozen_contract",
                        "program": "deterministic_fixture",
                        "schedule": "deterministic_fixture",
                        "node_ids": "host_derived",
                        "obligation_specs": "host_derived",
                        "model_proposed_fields": (),
                    },
                    "source_type_check": _source_type_check(fixture, program),
                    "schema_version": "qa_reasoning_candidate_route.v1",
                },
                "candidate_id",
                "qa_reasoning_candidate_route:",
            )
            models.CandidateRoute.model_validate(candidate)
            candidates.append(candidate)
    preregistration = models.identified(
        {
            "stage": models.STAGE,
            "inventory_id": inventory["inventory_id"],
            "fixture_order": ("F1", "F2"),
            "group_order_per_fixture": models.GROUP_ORDER,
            "candidate_ids": tuple(item["candidate_id"] for item in candidates),
            "candidate_declaration_bindings": tuple(
                {"candidate_id": item["candidate_id"], **_binding(item)} for item in candidates
            ),
            "main_candidate_ids": tuple(
                item["candidate_id"] for item in candidates if item["group"] != "C"
            ),
            "control_candidate_ids": tuple(
                item["candidate_id"] for item in candidates if item["group"] == "C"
            ),
            "selected_candidate_count": len(candidates),
            "main_candidate_count": 4,
            "independent_swap_control_count": 2,
            "max_positive_executions": models.MAX_POSITIVE_EXECUTIONS,
            "max_registered_actions_per_candidate": models.MAX_REGISTERED_ACTIONS,
            "termination": (
                "stop after declared schedule and frozen final-answer validation; "
                "terminate on first failed action without repairing or replacing the "
                "route"
            ),
            "on_alternative_failure": "retain failure row; no outcome-selected replacement",
            "source_selection_before_execution": True,
            "executor_oracle_calls_in_source_selection": 0,
            "semantic_alternative_result": "not_established_by_constructibility",
            "quotient_projection_or_class_assignment_performed": False,
            "provider_calls": 0,
            "field_origin": "deterministic_fixture",
            "schema_version": "qa_reasoning_candidate_family_preregistration.v1",
        },
        "preregistration_id",
        "qa_reasoning_candidate_family_preregistration:",
    )
    return preregistration, tuple(candidates)
