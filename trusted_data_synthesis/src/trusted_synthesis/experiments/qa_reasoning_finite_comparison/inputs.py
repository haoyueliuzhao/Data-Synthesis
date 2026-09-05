"""Read-only exact-byte admission; no candidate source construction or execution."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.operations.registry import operation_semantic_contract
from trusted_synthesis.core.task.realization import RealizedTaskPackage
from trusted_synthesis.experiments.qa_reasoning_candidate_family.models import CandidateRoute
from trusted_synthesis.experiments.qa_reasoning_candidate_family.validation import (
    validate_candidate,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    catalog_operation_registry,
)

PREDECESSOR = (
    "trusted_data_synthesis/artifacts/qa_reasoning_candidate_family/"
    "finance_qa_vnext_reasoning_behavior_typed_candidate_family_constr"
    "uctibility_preflight_v1_20260905"
)
MANIFEST = (
    "qa_reasoning_candidate_family_manifest:a9fa15d097fa30dada250c69ca"
    "17906cc4a197e0aa635b1d4b80b5f62931bb64"
)
ARTIFACT_ROOT = (
    "qa_reasoning_candidate_family_root:9e6be2dea9a8566e613374b726f654"
    "715a9f458ba9ca82fd490ed01e6696b83b"
)
SOURCE_COMMIT = "bc4a6217ab22e2f24e8a40ca14824291ae09b576"
SOURCE_TREE = "a41d7d2748187a82f0ddcec35287b4b90c9c6966"
REFERENCE_COMMIT = "2109f8ce9cab0a73539cc4d29f731aaa0e6793f3"
DESIGN_DIRECTORY = (
    "trusted_data_synthesis/artifacts/qa_reasoning_behavior_design/"
    "finance_qa_vnext_public_reasoning_semantics_allowed_behavior_and_"
    "quotient_contract_design_v1_20260905"
)
DESIGN_MANIFEST = (
    "qa_reasoning_behavior_design_manifest:38e699777f456718203633e7cab"
    "8c23b6b74c0e8c2714e2af5953d234fdc2283"
)
DESIGN_ROOT = (
    "qa_reasoning_behavior_design_root:94618bb1c74e77c5056bfc98f124d6e"
    "2a063723e0cf5c0c42bb79f9547784afb"
)
FIXED_TASKS = {
    "F1": "task:8d0e3d8dd2b5f4f981b72d7c9e600798229e246dd909a15746b5232ad648d2af",
    "F2": "task:c3c91045437afe06ab99c74655f93989bb9525428e76b14d41f792dfbb595c28",
}
GROUPS = ("B", "A", "C")


class ComparisonInputError(ValueError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def require(condition: bool, stage: str, message: str) -> None:
    if not condition:
        raise ComparisonInputError(stage, message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identified(body: Mapping[str, Any], kind: str, field: str = "audit_id") -> dict[str, Any]:
    result = dict(body)
    result.setdefault("schema_version", f"qa_reasoning_finite_comparison_{kind}.v1")
    require(field not in result, "identity.input", "identity must be independently calculated")
    result[field] = strict_canonical_hash(result, prefix=f"qa_reasoning_finite_comparison_{kind}:")
    return result


def files_at(directory: Path) -> dict[str, bytes]:
    require(directory.is_dir() and not directory.is_symlink(), "freeze.path", "invalid directory")
    paths = sorted(directory.rglob("*"))
    require(not any(p.is_symlink() for p in paths), "freeze.path", "symlink in frozen directory")
    return {p.relative_to(directory).as_posix(): p.read_bytes() for p in paths if p.is_file()}


def validate_manifest(
    files: Mapping[str, bytes], manifest_id: str, artifact_root: str
) -> dict[str, Any]:
    manifest = json.loads(files["artifact_manifest.json"])
    members = manifest["members"]
    paths = [m["relative_path"] for m in members]
    count = manifest.get("member_count", manifest.get("file_count"))
    require(
        len(paths) == len(set(paths)) == count
        and set(paths) == set(files) - {"artifact_manifest.json"}
        and manifest["member_bytes"] == sum(len(files[p]) for p in paths)
        and all(
            m["sha256"] == sha(files[m["relative_path"]])
            and m["byte_count"] == len(files[m["relative_path"]])
            for m in members
        ),
        "freeze.members",
        "exact member path/hash/byte relations differ",
    )
    require(
        manifest["manifest_id"] == manifest_id
        and manifest["artifact_root"] == artifact_root
        and strict_canonical_hash(
            {k: v for k, v in manifest.items() if k != "manifest_id"},
            prefix=manifest_id.split(":")[0] + ":",
        )
        == manifest_id
        and strict_canonical_hash(members, prefix=artifact_root.split(":")[0] + ":")
        == artifact_root,
        "freeze.identity",
        "exact Manifest/Root identity differs",
    )
    return manifest


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(("git", "-C", str(root), *args), capture_output=True, check=False)
    require(result.returncode == 0, "source.git", "exact Git object unavailable")
    return result.stdout


def source_group(root: Path, commit: str, tree: str, paths: tuple[str, ...]) -> dict[str, Any]:
    require(
        git(root, "cat-file", "-t", commit).strip() == b"commit"
        and git(root, "rev-parse", f"{commit}^{{commit}}").decode().strip() == commit
        and git(root, "rev-parse", f"{commit}^{{tree}}").decode().strip() == tree,
        "source.commit_tree",
        "source commit/tree relation differs",
    )
    rows = []
    for path in paths:
        data = git(root, "show", f"{commit}:{path}")
        blob = hashlib.sha1(
            f"blob {len(data)}\0".encode() + data, usedforsecurity=False
        ).hexdigest()
        require(
            git(root, "rev-parse", f"{commit}:{path}").decode().strip() == blob
            and (root / path).read_bytes() == data,
            "source.member",
            "declared committed/blob/current member differs",
        )
        rows.append(
            {
                "path": path,
                "blob_oid": blob,
                "sha256": sha(data),
                "byte_count": len(data),
                "committed_current_equal": True,
            }
        )
    return {
        "commit": commit,
        "tree": tree,
        "members": rows,
        "member_count": len(rows),
        "member_set_sha256": sha(canonical_json_bytes(rows)),
    }


def validate_identity(value: Mapping[str, Any], field: str) -> None:
    name = value[field]
    require(isinstance(name, str) and ":" in name, "input.identity", "missing content identity")
    require(
        strict_canonical_hash(
            {k: v for k, v in value.items() if k != field}, prefix=name.split(":")[0] + ":"
        )
        == name,
        "input.identity",
        "saved content identity differs",
    )


def index_jsonl(data: bytes, key: str, *, identical_duplicates: bool = False) -> dict[str, Any]:
    rows = [json.loads(line) for line in data.splitlines() if line]
    result: dict[str, Any] = {}
    for row in rows:
        identity = row[key]
        require(
            identity not in result or (identical_duplicates and result[identity] == row),
            "input.join",
            "duplicate or crossed object identity",
        )
        result[identity] = row
    return result


class FrozenReader:
    """No write API; every opened runtime byte must still equal the admitted snapshot."""

    def __init__(self, root: Path, files: Mapping[str, bytes]) -> None:
        self.root = root
        self.files = files

    def read_bytes(self, path: str) -> bytes:
        require(
            path in self.files and not Path(path).is_absolute() and ".." not in Path(path).parts,
            "input.path",
            "read outside admitted artifact snapshot",
        )
        value = (self.root / path).read_bytes()
        require(value == self.files[path], "input.changed_bytes", "frozen artifact changed on disk")
        return value


def load_inputs(root: Path) -> dict[str, Any]:
    """Join six saved trajectories and exact original sources, never construct a candidate."""
    files = files_at(root / PREDECESSOR)
    manifest = validate_manifest(files, MANIFEST, ARTIFACT_ROOT)
    require(
        len(files) == 278 and sum(map(len, files.values())) == 1_176_762,
        "freeze.geometry",
        "candidate-family formal geometry differs",
    )
    require(
        git(root, "rev-parse", f"{SOURCE_COMMIT}^{{tree}}").decode().strip() == SOURCE_TREE,
        "freeze.source",
        "frozen candidate source tree differs",
    )
    transition = json.loads(files["transition.json"])
    validate_identity(transition, "transition_id")
    require(
        transition["next_stage_authorized"] is False
        and transition["prospective_next_stage"]
        == "finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_only",
        "freeze.transition",
        "candidate-family transition differs",
    )
    inventory = json.loads(files["source_inventory.json"])
    validate_identity(inventory, "inventory_id")
    archive_info = inventory["archive_freeze"]
    archive_files = files_at(root / archive_info["directory"])
    validate_manifest(archive_files, archive_info["manifest_id"], archive_info["artifact_root"])
    require(
        len(archive_files) == archive_info["file_count"]
        and sum(map(len, archive_files.values())) == archive_info["total_bytes"],
        "freeze.archive",
        "exact archived source geometry differs",
    )
    design_files = files_at(root / DESIGN_DIRECTORY)
    validate_manifest(design_files, DESIGN_MANIFEST, DESIGN_ROOT)
    design = json.loads(design_files["behavior_contract.json"])
    validate_identity(design, "contract_id")
    rows = index_jsonl(archive_files["parameter_case_rows.jsonl"], "row_id")
    bundles = index_jsonl(archive_files["evidence_bundles.jsonl"], "bundle_id")
    packages = index_jsonl(archive_files["realized_task_packages.jsonl"], "realized_package_id")
    fixtures: dict[str, Any] = {}
    for binding in inventory["fixture_bindings"]:
        fixture_id = binding["fixture_id"]
        require(
            fixture_id in FIXED_TASKS
            and fixture_id not in fixtures
            and binding["task_id"] == FIXED_TASKS[fixture_id],
            "input.task",
            "fixed Task differs",
        )
        scope = {k: v for k, v in binding.items() if k != "source_type_check"}
        validate_identity(scope, "scope_binding_id")
        row = rows[scope["row_id"]]
        bundle = EvidenceBundle.model_validate(bundles[row["evidence_bundle_id"]])
        package = RealizedTaskPackage.model_validate(packages[row["realized_package_id"]])
        require(
            bundle.bundle_id == scope["evidence_bundle_id"]
            and package.realized_package_id == scope["realized_package_id"]
            and package.task.task_id == scope["task_id"],
            "input.source_join",
            "source join differs",
        )
        evidence = {item.evidence_id: item for item in bundle.evidence}
        # Restore the frozen in-memory tuple type without changing canonical source bytes.
        scope["role_bindings"] = package.binding_snapshot.role_bindings
        fixture = {
            "fixture_id": fixture_id,
            "case_id": scope["case_id"],
            "task_id": scope["task_id"],
            "task_instance_id": scope["task_id"],
            "scope_bindings": scope,
            "row": row,
            "bundle": bundle,
            "package": package,
            "source_type_check": binding["source_type_check"],
            "roles": {k: evidence[v[0]] for k, v in package.binding_snapshot.role_bindings.items()},
        }
        fixtures[fixture_id] = fixture
    require(set(fixtures) == set(FIXED_TASKS), "input.task", "missing fixed Task")
    declarations = index_jsonl(files["candidate_declarations.jsonl"], "candidate_id")
    executions = index_jsonl(files["execution_descriptors.jsonl"], "candidate_id")
    validations = index_jsonl(files["independent_validations.jsonl"], "candidate_id")
    result_rows = index_jsonl(files["candidate_rows.jsonl"], "candidate_id")
    require(
        set(declarations) == set(executions) == set(validations) == set(result_rows)
        and len(declarations) == 6,
        "input.population",
        "six frozen candidate parents differ",
    )
    selected = []
    for fixture_id in FIXED_TASKS:
        for group in GROUPS:
            matches = [
                v
                for v in declarations.values()
                if v["fixture_id"] == fixture_id and v["group"] == group
            ]
            require(
                len(matches) == 1, "input.population", "missing or duplicate primary/control cell"
            )
            candidate = CandidateRoute.model_validate(matches[0]).model_dump(mode="python")
            # Preserve the parsed Program for the exact existing read-only validator.
            candidate["program"] = CandidateRoute.model_validate(matches[0]).program
            identity = candidate["candidate_id"]
            row, execution = result_rows[identity], executions[identity]
            validate_identity(row, "row_id")
            require(
                row["task_id"] == execution["task_id"] == FIXED_TASKS[fixture_id]
                and row["group"] == execution["group"] == group
                and row["population_role"]
                == ("schedule_control" if group == "C" else "primary_candidate")
                and row["qualified"] is True
                and validations[identity]["qualified"] is True
                and row["quotient_class_count"] is None,
                "input.admission",
                "frozen qualified population or role differs",
            )
            selected.append(
                {
                    "fixture": fixtures[fixture_id],
                    "candidate": candidate,
                    "execution": execution,
                    "saved_validation": validations[identity],
                    "row": row,
                }
            )
    frozen_source = json.loads(files["source_authority.json"])
    validate_identity(frozen_source, "audit_id")
    inherited = []
    for key in ("implementation", "declared_references"):
        group = frozen_source[key]
        actual = source_group(
            root, group["commit"], group["tree"], tuple(m["path"] for m in group["members"])
        )
        require(
            canonical_json_bytes(actual) == canonical_json_bytes(group),
            "source.inherited",
            "saved predecessor source authority differs",
        )
        inherited.append(actual)
    registry = catalog_operation_registry()
    contracts = {v["operator_id"]: v for v in inventory["registered_operation_semantics"]}
    current = {
        str(v["operator_id"]): operation_semantic_contract(registry.require(str(v["operator_id"])))
        for v in registry.manifest()
    }
    require(
        canonical_json_bytes(contracts) == canonical_json_bytes(current),
        "source.registry",
        "actual registered semantics differ from frozen inventory",
    )
    freeze = identified(
        {
            "directory": PREDECESSOR,
            "manifest_id": MANIFEST,
            "artifact_root": ARTIFACT_ROOT,
            "files": len(files),
            "bytes": sum(map(len, files.values())),
            "manifest_members": manifest["member_count"],
            "member_bytes": manifest["member_bytes"],
            "transition_id": transition["transition_id"],
            "historical_next_stage_authorized": False,
            "source_commit": SOURCE_COMMIT,
            "source_tree": SOURCE_TREE,
            "archive_root": archive_info["artifact_root"],
            "design_contract_id": design["contract_id"],
            "selected_trajectories": 6,
            "primary_candidates": 4,
            "schedule_controls": 2,
            "new_candidate_declarations": 0,
            "input_runtime_executions": 0,
            "inherited_source_groups": inherited,
            "passed": True,
        },
        "input_freeze",
    )
    return {
        "freeze": freeze,
        "files": files,
        "archive_files": archive_files,
        "archive_directory": archive_info["directory"],
        "design_files": design_files,
        "design": design,
        "inventory": inventory,
        "fixtures": fixtures,
        "selected": selected,
        "registry": registry,
        "operation_contracts": contracts,
        "reader": FrozenReader(root / PREDECESSOR, files),
    }


def revalidate_six(inputs: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validations = []
    for item in inputs["selected"]:
        result = validate_candidate(
            writer=inputs["reader"],
            fixture=item["fixture"],
            candidate=item["candidate"],
            result=item["execution"],
            registry=inputs["registry"],
        )
        require(
            result["qualified"] is True
            and canonical_json_bytes(result) == canonical_json_bytes(item["saved_validation"]),
            "input.revalidation",
            "actual own-validation differs or candidate is unqualified",
        )
        validations.append(result)
    audit = identified(
        {
            "read_only_validator_calls": len(validations),
            "qualified": len(validations),
            "actual_byte_projection_matches": len(validations),
            "own_route_oracle_nodes": sum(
                v["trajectory_oracle_node_replay_count"] for v in validations
            ),
            "answer_oracle_nodes": sum(v["answer_oracle_node_replay_count"] for v in validations),
            "operation_executor_calls": 0,
            "runtime_calls": 0,
            "new_candidate_declarations": 0,
            "saved_qualification_used_as_outcome_oracle": False,
            "passed": True,
        },
        "input_revalidation",
    )
    return validations, audit
