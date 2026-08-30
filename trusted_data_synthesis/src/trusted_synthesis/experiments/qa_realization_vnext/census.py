from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.release.schema import SplitPolicy
from trusted_synthesis.core.release.split import assign_semantic_parent_split
from trusted_synthesis.core.task.program import InputRefKind, TaskProgram
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.hashing import canonical_hash

CENSUS_POLICY_ID = "qa_semantic_surface_identity_and_diversity_census.v1"
LEXICAL_NEAR_DUPLICATE_THRESHOLD = 0.92


class TaskCensusRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    row_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    source_line: int = Field(ge=1)
    legacy_task_id: str = Field(min_length=1)
    legacy_task_hash: str = Field(min_length=1)
    semantic_parent_id: str = Field(min_length=1)
    binding_snapshot_id: str = Field(min_length=1)
    realization_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    task_family: str = Field(min_length=1)
    proposal_source: str = Field(min_length=1)
    retrieval_track: str = Field(min_length=1)
    planning_track: str = Field(min_length=1)
    program_topology_hash: str = Field(min_length=1)
    parameterized_program_hash: str = Field(min_length=1)
    operator_sequence: tuple[str, ...] = Field(min_length=1)
    operator_bigrams: tuple[str, ...] = ()
    answer_schema_hash: str = Field(min_length=1)
    renderer_profile_id: str = Field(min_length=1)
    language: str = Field(min_length=2)
    style: str = Field(min_length=1)
    slot_variant_id: str = Field(min_length=1)
    normalized_skeleton: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    split: str = Field(pattern="^(train|dev|test)$")

    @model_validator(mode="after")
    def validate_identity(self) -> TaskCensusRow:
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"row_id"}),
            prefix="qa_census_row:",
        )
        if self.row_id != expected:
            raise ValueError("QA census row identity is invalid")
        return self


class QADiversityCensus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    census_id: str = Field(min_length=1)
    policy_id: str = CENSUS_POLICY_ID
    input_files: tuple[dict[str, Any], ...] = Field(min_length=1)
    row_manifest_hash: str = Field(min_length=1)
    rows: tuple[TaskCensusRow, ...] = Field(min_length=1)
    semantic_metrics: dict[str, Any]
    surface_metrics: dict[str, Any]
    coupling_metrics: dict[str, Any]
    split_audit: dict[str, Any]
    hard_gates: dict[str, bool]
    claim_boundary: dict[str, Any]
    schema_version: str = "qa_diversity_census.v1"

    @model_validator(mode="after")
    def validate_census(self) -> QADiversityCensus:
        if any(not passed for passed in self.hard_gates.values()):
            raise ValueError("QA diversity census failed a noncompensatory gate")
        expected_row_manifest = canonical_hash(
            tuple(row.row_id for row in self.rows),
            prefix="qa_census_row_manifest:",
        )
        if self.row_manifest_hash != expected_row_manifest:
            raise ValueError("QA diversity census row manifest is invalid")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"census_id", "rows"}),
            prefix="qa_diversity_census:",
        )
        if self.census_id != expected:
            raise ValueError("QA diversity census identity is invalid")
        return self


def run_task_package_census(
    input_paths: Iterable[str | Path],
    *,
    split_policy: SplitPolicy | None = None,
) -> QADiversityCensus:
    policy = split_policy or SplitPolicy(policy_id="qa_realization_semantic_parent_split.v1")
    paths = tuple(Path(path).resolve() for path in input_paths)
    if not paths:
        raise ValueError("QA diversity census requires at least one input file")
    rows: list[TaskCensusRow] = []
    input_files: list[dict[str, Any]] = []
    for path in paths:
        input_bytes = path.read_bytes()
        input_files.append(
            {
                "path": path.name,
                "sha256": sha256(input_bytes).hexdigest(),
                "byte_count": len(input_bytes),
                "row_count": sum(1 for line in input_bytes.splitlines() if line.strip()),
            }
        )
        for line_number, line in enumerate(input_bytes.splitlines(), start=1):
            if not line.strip():
                continue
            task = TaskPackage.model_validate_json(line)
            rows.append(_task_census_row(task, path.name, line_number, policy))
    rows_tuple = tuple(sorted(rows, key=lambda item: item.row_id))
    row_manifest_hash = canonical_hash(
        tuple(row.row_id for row in rows_tuple),
        prefix="qa_census_row_manifest:",
    )
    semantic_metrics = _semantic_metrics(rows_tuple)
    surface_metrics = _surface_metrics(rows_tuple)
    coupling_metrics = _coupling_metrics(rows_tuple)
    split_audit = _split_audit(rows_tuple)
    hard_gates = {
        "input_files_read_only": True,
        "task_rows_parsed_complete": len(rows_tuple)
        == sum(int(item["row_count"]) for item in input_files),
        "census_row_identity_collision_zero": len({item.row_id for item in rows_tuple})
        == len(rows_tuple),
        "row_manifest_bound": bool(row_manifest_hash),
        "realization_identity_collision_zero": len({item.realization_id for item in rows_tuple})
        == len(rows_tuple),
        "sibling_cross_split_leakage_zero": split_audit["leaking_semantic_parent_count"] == 0,
        "provider_call_count_zero": True,
        "gpu_job_count_zero": True,
        "frozen_artifact_write_count_zero": True,
        "surface_only_vtdo_state_count_zero": True,
    }
    claim_boundary = {
        "scope": "exact listed legacy TaskPackage JSONL inputs only",
        "identity_mode": "legacy_package_inference_v1",
        "semantic_parent_interpretation": (
            "renderer-free identity inferred from domain, task family, canonicalized program, "
            "answer schema, retrieval/planning tracks, and quality profile"
        ),
        "included": (
            "legacy TaskPackage semantics",
            "binding lineage",
            "canonical instructions",
            "program topology",
            "surface skeletons",
        ),
        "excluded": (
            "v26 capability catalogs",
            "raw_financial_data_lake QA candidate/sample rows",
            "embedding near-duplicate measurements",
            "Provider rewrites",
            "program replay without exact EvidenceBundle inputs",
            "VTDO State inference",
        ),
        "not_claimed": (
            "repository-wide maximum skeleton share",
            "model readability",
            "model behavior equivalence",
            "unrestricted task distribution",
            "training quality improvement",
        ),
        "thresholds_are_descriptive": True,
        "provider_call_count": 0,
        "gpu_job_count": 0,
        "historical_artifact_mutation_count": 0,
    }
    census_payload = {
        "policy_id": CENSUS_POLICY_ID,
        "input_files": tuple(input_files),
        "row_manifest_hash": row_manifest_hash,
        "semantic_metrics": semantic_metrics,
        "surface_metrics": surface_metrics,
        "coupling_metrics": coupling_metrics,
        "split_audit": split_audit,
        "hard_gates": hard_gates,
        "claim_boundary": claim_boundary,
        "schema_version": "qa_diversity_census.v1",
    }
    census_id = canonical_hash(census_payload, prefix="qa_diversity_census:")
    return QADiversityCensus(census_id=census_id, rows=rows_tuple, **census_payload)


def write_census_artifacts(census: QADiversityCensus, output_dir: str | Path) -> tuple[str, ...]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    semantic_parents: dict[str, dict[str, Any]] = {}
    bindings: dict[str, dict[str, Any]] = {}
    for row in census.rows:
        semantic = semantic_parents.setdefault(
            row.semantic_parent_id,
            {
                "semantic_parent_id": row.semantic_parent_id,
                "domain": row.domain,
                "task_family": row.task_family,
                "proposal_source": row.proposal_source,
                "program_topology_hash": row.program_topology_hash,
                "parameterized_program_hash": row.parameterized_program_hash,
                "answer_schema_hash": row.answer_schema_hash,
                "legacy_task_ids": [],
                "binding_snapshot_ids": [],
                "realization_ids": [],
            },
        )
        semantic["legacy_task_ids"].append(row.legacy_task_id)
        semantic["binding_snapshot_ids"].append(row.binding_snapshot_id)
        semantic["realization_ids"].append(row.realization_id)
        bindings.setdefault(
            row.binding_snapshot_id,
            {
                "binding_snapshot_id": row.binding_snapshot_id,
                "semantic_parent_id": row.semantic_parent_id,
                "legacy_task_id": row.legacy_task_id,
                "source_path": row.source_path,
                "source_line": row.source_line,
            },
        )
    for value in semantic_parents.values():
        for key in ("legacy_task_ids", "binding_snapshot_ids", "realization_ids"):
            value[key] = sorted(set(value[key]))
    artifacts = {
        "semantic_parent_manifest.jsonl": tuple(
            semantic_parents[key] for key in sorted(semantic_parents)
        ),
        "binding_snapshot_manifest.jsonl": tuple(bindings[key] for key in sorted(bindings)),
        "realization_census.jsonl": tuple(row.model_dump(mode="json") for row in census.rows),
        "program_topology_census.json": census.semantic_metrics,
        "question_skeleton_census.json": census.surface_metrics,
        "family_skeleton_coupling.json": census.coupling_metrics,
        "cross_split_realization_audit.json": census.split_audit,
        "claim_boundary.json": census.claim_boundary,
        "report.json": census.model_dump(mode="json", exclude={"rows"}),
    }
    for name, value in artifacts.items():
        path = output / name
        if name.endswith(".jsonl"):
            path.write_text(
                "".join(_canonical_json(item) + "\n" for item in value),
                encoding="utf-8",
            )
        else:
            path.write_text(_canonical_json(value) + "\n", encoding="utf-8")
    return tuple(sorted(artifacts))


def _task_census_row(
    task: TaskPackage,
    source_path: str,
    source_line: int,
    split_policy: SplitPolicy,
) -> TaskCensusRow:
    topology_hash = _program_hash(task.oracle.task_program, task, include_parameters=False)
    parameterized_hash = _program_hash(task.oracle.task_program, task, include_parameters=True)
    answer_schema = _answer_schema_semantics(task.public.answer_schema)
    answer_schema_hash = canonical_hash(answer_schema, prefix="answer_schema_semantics:")
    pattern = task.public.metadata.get("task_pattern")
    pattern_identity = pattern if isinstance(pattern, Mapping) else {}
    semantic_parent_payload = {
        "domain": task.public.domain,
        "task_family": task.public.task_type,
        "parameterized_program_hash": parameterized_hash,
        "answer_schema_hash": answer_schema_hash,
        "retrieval_track": task.public.retrieval_track.value,
        "planning_track": task.public.planning_track.value,
        "quality_profile_id": pattern_identity.get("quality_profile_id"),
        "schema_version": "legacy_semantic_parent_inference.v1",
    }
    semantic_parent_id = canonical_hash(semantic_parent_payload, prefix="semantic_task:")
    selection = task.oracle.selection_contract
    binding_payload = {
        "semantic_parent_id": semantic_parent_id,
        "gold_evidence_ids": task.oracle.gold_evidence_ids,
        "evidence_version_ids": selection.get("evidence_version_ids") or (),
        "pattern_binding": selection.get("pattern_binding") or {},
        "required_build_ids": selection.get("required_build_ids") or {},
        "proof_graph_id": task.oracle.proof_graph_id,
        "proof_graph_hash": task.oracle.proof_graph_hash,
        "schema_version": "legacy_binding_snapshot_inference.v1",
    }
    binding_snapshot_id = canonical_hash(binding_payload, prefix="binding_snapshot:")
    renderer_profile_id = str(
        pattern_identity.get("renderer_profile_id")
        or pattern_identity.get("pattern_id")
        or f"legacy.{task.public.task_type}.canonical"
    )
    skeleton = normalize_legacy_question_skeleton(task)
    realization_payload = {
        "binding_snapshot_id": binding_snapshot_id,
        "renderer_profile_id": renderer_profile_id,
        "language": "en",
        "style": "legacy_canonical",
        "slot_variant_id": "legacy_canonical",
        "normalized_skeleton": skeleton,
        "final_instruction": task.public.instruction,
        "schema_version": "legacy_surface_realization_inference.v1",
    }
    realization_id = canonical_hash(realization_payload, prefix="surface_realization:")
    operators = tuple(node.operator_id for node in task.oracle.task_program.nodes)
    bigrams = tuple(
        f"{left}->{right}" for left, right in zip(operators, operators[1:], strict=False)
    )
    proposal_source = str(
        task.public.metadata.get("proposal_source")
        or (
            "raw_static_graph_pattern"
            if str(task.public.metadata.get("pattern_catalog") or "").startswith("finance_raw")
            else "current_pattern"
        )
    )
    payload = {
        "source_path": source_path,
        "source_line": source_line,
        "legacy_task_id": task.task_id,
        "legacy_task_hash": task.task_hash,
        "semantic_parent_id": semantic_parent_id,
        "binding_snapshot_id": binding_snapshot_id,
        "realization_id": realization_id,
        "domain": task.public.domain,
        "task_family": task.public.task_type,
        "proposal_source": proposal_source,
        "retrieval_track": task.public.retrieval_track.value,
        "planning_track": task.public.planning_track.value,
        "program_topology_hash": topology_hash,
        "parameterized_program_hash": parameterized_hash,
        "operator_sequence": operators,
        "operator_bigrams": bigrams,
        "answer_schema_hash": answer_schema_hash,
        "renderer_profile_id": renderer_profile_id,
        "language": "en",
        "style": "legacy_canonical",
        "slot_variant_id": "legacy_canonical",
        "normalized_skeleton": skeleton,
        "instruction": task.public.instruction,
        "split": assign_semantic_parent_split(semantic_parent_id, split_policy).value,
    }
    row_id = canonical_hash(payload, prefix="qa_census_row:")
    return TaskCensusRow(row_id=row_id, **payload)


def normalize_legacy_question_skeleton(task: TaskPackage) -> str:
    value = task.public.instruction.casefold()
    scope = task.public.retrieval_scope
    replacements: list[tuple[str, str]] = []
    replacements.extend((str(item), "<metric>") for item in scope.get("predicates") or ())
    replacements.extend((str(item), "<period>") for item in scope.get("temporal_labels") or ())
    contexts = (scope.get("semantic_constraints") or {}).get("payload_contexts") or ()
    for context in contexts:
        if not isinstance(context, Mapping):
            continue
        for key in ("unit", "currency"):
            if context.get(key):
                replacements.append((str(context[key]), f"<{key}>"))
    for source, target in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        value = re.sub(re.escape(source.casefold()), target, value)
    patterns = {
        "fact_retrieval": r"^(what is )(.+?)(\'s <metric>)",
        "comparison": r"^(compare <metric> for )(.+?)( for <period> with )(.+?)( for <period>)",
        "temporal_growth": r"^(how much did )(.+?)(\'s <metric>)",
        "temporal_average": r"^(what was the mean <metric> for )(.+?)( (?:across|over))",
        "temporal_absolute_change": (
            r"^(calculate the signed absolute change in )(.+?)(\'s <metric>)"
        ),
        "registered_ratio": r"^(calculate )(.+?)(\'s <metric>-to-<metric>)",
    }
    pattern = patterns.get(task.public.task_type)
    if pattern:
        match = re.search(pattern, value)
        if match:
            if task.public.task_type == "comparison":
                value = (
                    match.group(1)
                    + "<subject>"
                    + match.group(3)
                    + "<subject>"
                    + match.group(5)
                    + value[match.end() :]
                )
            else:
                value = match.group(1) + "<subject>" + match.group(3) + value[match.end() :]
    value = re.sub(r"(?<![a-z])\d+(?:\.\d+)?", "<number>", value)
    return re.sub(r"\s+", " ", value).strip()


def _program_hash(program: TaskProgram, task: TaskPackage, *, include_parameters: bool) -> str:
    binding = task.oracle.selection_contract.get("pattern_binding") or {}
    role_bindings = binding.get("role_bindings") if isinstance(binding, Mapping) else {}
    evidence_roles = {
        evidence_id: (str(role_id), position)
        for role_id, evidence_ids in sorted((role_bindings or {}).items())
        for position, evidence_id in enumerate(evidence_ids)
    }
    fallback_roles: dict[str, tuple[str, int]] = {}
    structural_keys: dict[str, str] = {}
    nodes = []
    for node in program.nodes:
        inputs: list[dict[str, Any]] = []
        for ref in node.input_refs:
            if ref.kind == InputRefKind.OPERATION:
                inputs.append(
                    {
                        "kind": "operation",
                        "operation_key": structural_keys[ref.ref_id],
                        "selector": ref.selector,
                    }
                )
            else:
                role = evidence_roles.get(ref.ref_id)
                if role is None:
                    role = fallback_roles.setdefault(
                        ref.ref_id, ("inferred_evidence_role", len(fallback_roles))
                    )
                inputs.append(
                    {
                        "kind": "evidence_role",
                        "role_id": role[0],
                        "role_position": role[1],
                        "selector": ref.selector,
                    }
                )
        if node.operator_id == "aggregate":
            inputs.sort(key=canonical_hash)
        node_payload = {
            "operator_id": node.operator_id,
            "inputs": inputs,
            **({"parameters": node.parameters} if include_parameters else {}),
            "output_schema": node.output_schema,
            "verifier_id": node.verifier_id,
        }
        node_key = canonical_hash(node_payload, prefix="canonical_program_node:")
        structural_keys[node.node_id] = node_key
        nodes.append({"node_key": node_key, **node_payload})
    payload = {
        "nodes": sorted(nodes, key=canonical_hash),
        "output_node_key": structural_keys[program.output_node_id],
        "schema_version": (
            "legacy_parameterized_program_inference.v1"
            if include_parameters
            else "legacy_program_topology_inference.v1"
        ),
    }
    return canonical_hash(
        payload,
        prefix="parameterized_program:" if include_parameters else "program_topology:",
    )


def _answer_schema_semantics(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _answer_schema_semantics(item)
            for key, item in sorted(value.items())
            if key not in {"result_context", "comparison_entities"}
        }
    if isinstance(value, (list, tuple)):
        return [_answer_schema_semantics(item) for item in value]
    return value


def _semantic_metrics(rows: tuple[TaskCensusRow, ...]) -> dict[str, Any]:
    topology = Counter(row.program_topology_hash for row in rows)
    parameterized = Counter(row.parameterized_program_hash for row in rows)
    schemas = Counter(row.answer_schema_hash for row in rows)
    sources = Counter(row.proposal_source for row in rows)
    retrieval_tracks = Counter(row.retrieval_track for row in rows)
    planning_tracks = Counter(row.planning_track for row in rows)
    bigrams = sorted({bigram for row in rows for bigram in row.operator_bigrams})
    return {
        "task_package_count": len(rows),
        "unique_semantic_task_count": len({row.semantic_parent_id for row in rows}),
        "unique_binding_snapshot_count": len({row.binding_snapshot_id for row in rows}),
        "unique_program_topology_count": len(topology),
        "unique_parameterized_program_count": len(parameterized),
        "operator_bigram_coverage": len(bigrams),
        "operator_bigrams": bigrams,
        "unique_answer_schema_count": len(schemas),
        "answer_schema_entropy_bits": _entropy(schemas),
        "proposal_source_distribution": dict(sorted(sources.items())),
        "retrieval_track_distribution": dict(sorted(retrieval_tracks.items())),
        "planning_track_distribution": dict(sorted(planning_tracks.items())),
        "program_topology_distribution": dict(sorted(topology.items())),
        "parameterized_program_distribution": dict(sorted(parameterized.items())),
        "largest_program_topology_share": _largest_share(topology),
    }


def _surface_metrics(rows: tuple[TaskCensusRow, ...]) -> dict[str, Any]:
    skeletons = Counter(row.normalized_skeleton for row in rows)
    languages = Counter(row.language for row in rows)
    styles = Counter(row.style for row in rows)
    slot_variants = Counter(row.slot_variant_id for row in rows)
    per_parent = Counter(row.semantic_parent_id for row in rows)
    per_binding = Counter(row.binding_snapshot_id for row in rows)
    cluster_sizes = _lexical_near_duplicate_cluster_sizes(skeletons)
    return {
        "realization_count": len(rows),
        "accepted_realizations_per_semantic_parent": dict(sorted(per_parent.items())),
        "minimum_realizations_per_semantic_parent": min(per_parent.values(), default=0),
        "maximum_realizations_per_semantic_parent": max(per_parent.values(), default=0),
        "unique_normalized_skeleton_count": len(skeletons),
        "question_skeleton_distribution": dict(sorted(skeletons.items())),
        "accepted_realizations_per_binding_snapshot": dict(sorted(per_binding.items())),
        "minimum_realizations_per_binding_snapshot": min(per_binding.values(), default=0),
        "maximum_realizations_per_binding_snapshot": max(per_binding.values(), default=0),
        "largest_skeleton_share": _largest_share(skeletons),
        "skeleton_entropy_bits": _entropy(skeletons),
        "language_distribution": dict(sorted(languages.items())),
        "language_entropy_bits": _entropy(languages),
        "style_distribution": dict(sorted(styles.items())),
        "style_entropy_bits": _entropy(styles),
        "lexical_near_duplicate_threshold": LEXICAL_NEAR_DUPLICATE_THRESHOLD,
        "lexical_near_duplicate_cluster_count": len(cluster_sizes),
        "slot_variant_usage": dict(sorted(slot_variants.items())),
        "largest_lexical_near_duplicate_cluster_size": max(cluster_sizes, default=0),
        "embedding_near_duplicate_status": "not_measured",
    }


def _coupling_metrics(rows: tuple[TaskCensusRow, ...]) -> dict[str, Any]:
    joint = Counter((row.task_family, row.normalized_skeleton) for row in rows)
    families = Counter(row.task_family for row in rows)
    skeletons = Counter(row.normalized_skeleton for row in rows)
    total = len(rows)
    mutual_information = 0.0
    for (family, skeleton), count in joint.items():
        probability = count / total
        mutual_information += probability * math.log2(
            probability / ((families[family] / total) * (skeletons[skeleton] / total))
        )
    family_entropy = _entropy(families)
    skeleton_entropy = _entropy(skeletons)
    denominator = math.sqrt(family_entropy * skeleton_entropy)
    conditional_entropy = sum(
        (family_count / total)
        * _entropy(Counter(row.normalized_skeleton for row in rows if row.task_family == family))
        for family, family_count in families.items()
    )
    return {
        "family_distribution": dict(sorted(families.items())),
        "family_skeleton_joint_distribution": {
            f"{family}|{skeleton}": count for (family, skeleton), count in sorted(joint.items())
        },
        "mutual_information_bits": round(mutual_information, 12),
        "normalized_mutual_information": round(
            mutual_information / denominator if denominator else 0.0,
            12,
        ),
        "skeleton_entropy_given_family_bits": round(conditional_entropy, 12),
    }


def _split_audit(rows: tuple[TaskCensusRow, ...]) -> dict[str, Any]:
    by_parent: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_parent[row.semantic_parent_id].add(row.split)
    leaking = sorted(parent for parent, splits in by_parent.items() if len(splits) > 1)
    return {
        "semantic_parent_count": len(by_parent),
        "sibling_semantic_parent_count": sum(
            sum(row.semantic_parent_id == parent for row in rows) > 1 for parent in by_parent
        ),
        "leaking_semantic_parent_count": len(leaking),
        "leaking_semantic_parent_ids": leaking,
        "split_distribution": dict(sorted(Counter(row.split for row in rows).items())),
        "split_assignment_key": "semantic_parent_id",
    }


def _lexical_near_duplicate_cluster_sizes(skeleton_counts: Counter[str]) -> tuple[int, ...]:
    skeletons = tuple(sorted(skeleton_counts))
    parents = list(range(len(skeletons)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for left in range(len(skeletons)):
        for right in range(left + 1, len(skeletons)):
            similarity = SequenceMatcher(None, skeletons[left], skeletons[right]).ratio()
            if similarity >= LEXICAL_NEAR_DUPLICATE_THRESHOLD:
                union(left, right)
    cluster_weights: Counter[int] = Counter()
    for index, skeleton in enumerate(skeletons):
        cluster_weights[find(index)] += skeleton_counts[skeleton]
    return tuple(sorted(cluster_weights.values(), reverse=True))


def _entropy(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if not total:
        return 0.0
    return round(
        -sum((count / total) * math.log2(count / total) for count in counts.values()),
        12,
    )


def _largest_share(counts: Counter[str]) -> float:
    total = sum(counts.values())
    return round(max(counts.values(), default=0) / total if total else 0.0, 12)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the read-only QA identity/diversity census")
    parser.add_argument("inputs", nargs="+", help="TaskPackage JSONL inputs")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    census = run_task_package_census(args.inputs)
    written = write_census_artifacts(census, args.output_dir)
    print(
        _canonical_json(
            {
                "census_id": census.census_id,
                "task_package_count": len(census.rows),
                "written_files": written,
            }
        )
    )


if __name__ == "__main__":
    main()
