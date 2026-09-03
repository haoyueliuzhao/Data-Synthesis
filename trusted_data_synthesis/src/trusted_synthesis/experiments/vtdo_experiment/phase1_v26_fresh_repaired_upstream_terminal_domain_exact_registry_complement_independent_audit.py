# ruff: noqa: E501
from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_independent_audit_models as models,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = (
    "finance_v26_219_fresh_repaired_upstream_terminal_domain_exact_registry_"
    "complement_binding_preflight_independent_audit_v1_20260903"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
EXTERNAL_REVIEW_SHA256: Final = "a631683b8532ff22cc015317fb31116a6d72179f682fcba0a94f93cd2d1ae56e"
EXTERNAL_REVIEW_BYTES: Final = 9_045
OPERATOR_DIRECTIVE: Final = "参照审计报告继续实验"
V218_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_218_fresh_repaired_upstream_terminal_domain_exact_registry_"
    "complement_binding_preflight_v1_20260903"
)
V217_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_217_fresh_repaired_upstream_typed_failure_event_authority_"
    "and_artifact_backing_preflight_v1_20260903"
)
V195_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_195_fresh_artifact_backed_outcome_authority_preflight_v1_20260901"
)
MODELS_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_"
    "independent_audit_models.py"
)
AUDIT_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_"
    "independent_audit.py"
)
TEST_FILE: Final = (
    "trusted_data_synthesis/tests/"
    "test_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_"
    "independent_audit.py"
)
IMPLEMENTATION_FILES: Final = tuple(sorted((MODELS_FILE, AUDIT_FILE, TEST_FILE)))
V218_MODULE: Final = (
    "trusted_synthesis.experiments.vtdo_experiment."
    "phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_preflight"
)
RUNTIME_PREFIXES: Final = (
    "consumer_ingress/",
    "exit_surface_controls/",
    "upstream_event_descriptors/",
    "upstream_events/",
    "upstream_observation_descriptors/",
    "upstream_observations/",
)
EXIT_ORDER: Final = (
    "E0_invalid_dispatch_chain",
    "E1_empty_queue",
    "E2_authenticated_rethrow",
    "E3_reasoning_key",
    "E4_non_object",
)
IDENTITY_SPECS: Final = (
    ("raw", "raw_id", "fresh_repaired_upstream_event_authority_raw:"),
    ("result", "result_id", "fresh_repaired_upstream_event_authority_result:"),
    ("trace", "trace_id", "fresh_repaired_upstream_event_authority_trace:"),
    ("outcome", "outcome_id", "fresh_repaired_upstream_event_authority_outcome:"),
    (
        "checkpoint",
        "checkpoint_id",
        "fresh_repaired_upstream_event_authority_checkpoint:",
    ),
)


class V219Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V219Error(stage, reason)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _bytes(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()


def _git(repository_root: Path, *args: str) -> bytes:
    run = subprocess.run(("git", *args), cwd=repository_root, check=False, capture_output=True)
    if run.returncode:
        _fail("source.git", run.stderr.decode("utf-8", errors="replace"))
    return run.stdout


def _all_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@dataclass(frozen=True)
class SavedV218:
    root: Path
    files: dict[str, bytes]
    artifact: dict[str, Any]
    report: dict[str, Any]
    decision: dict[str, Any]
    transition: dict[str, Any]
    source: dict[str, Any]
    complement: dict[str, Any]
    composition: dict[str, Any]
    retained: dict[str, Any]
    negative: dict[str, Any]


def _saved_v218(repository_root: Path) -> SavedV218:
    root = repository_root / V218_DIR
    files = _all_files(root)
    if len(files) != 51 or sum(map(len, files.values())) != 1_054_511:
        _fail("A0.saved_geometry", "v26.218 formal directory geometry differs")
    artifact = cast(dict[str, Any], _load(root / "artifact_manifest.json"))
    member_by_name = {item["relative_path"]: item for item in artifact["members"]}
    if (
        artifact["file_count"] != 50
        or artifact["total_byte_count"] != 1_044_590
        or set(member_by_name) != set(files) - {"artifact_manifest.json"}
    ):
        _fail("A0.saved_manifest", "v26.218 formal Manifest geometry differs")
    for name, member in member_by_name.items():
        payload = files[name]
        if len(payload) != member["byte_count"] or _sha(payload) != member["sha256"]:
            _fail("A0.saved_member", f"v26.218 formal member differs:{name}")
    saved = SavedV218(
        root=root,
        files=files,
        artifact=artifact,
        report=cast(dict[str, Any], _load(root / "report.json")),
        decision=cast(dict[str, Any], _load(root / "decision.json")),
        transition=cast(dict[str, Any], _load(root / "prospective_transition.json")),
        source=cast(dict[str, Any], _load(root / "source_identity.json")),
        complement=cast(dict[str, Any], _load(root / "exact_registry_complement_binding.json")),
        composition=cast(dict[str, Any], _load(root / "composition_contract.json")),
        retained=cast(dict[str, Any], _load(root / "retained_execution_audit.json")),
        negative=cast(
            dict[str, Any], _load(root / "registry_complement_negative_control_audit.json")
        ),
    )
    if (
        saved.artifact["manifest_id"]
        != "finance_v26_218_artifact_manifest:81b777673ed46c08fb6010ac3241f2fd87e087af4dc6f0c8266e4886dcb2276e"
        or saved.artifact["artifact_root"]
        != "finance_v26_218_artifact_root:b9b4524a734249133d34007af751537cd25e8a705a31657c66bde5bd9b7b34e1"
        or saved.report["report_id"]
        != "finance_v26_218_registry_complement_report:1f055b20f0f5492f69f821763ea415539cafd3f6b622ae4457689582037231b8"
        or saved.decision["decision_id"]
        != "finance_v26_218_registry_complement_decision:b086be873e0509689d3ebc733e5d790e28bb456a412f2b178ae191643521eea6"
        or saved.transition["transition_id"]
        != "finance_v26_218_transition:04ff36b08d531ad5419ce8da8dffe6fcde3447b192a971f2cce3b2da9e094edb"
        or saved.source["source_commit"] != models.V218_COMMIT
        or saved.source["source_tree"] != models.V218_TREE
        or saved.report["decision"] != models.V218_DECISION
        or saved.report["provider_calls"] != 0
        or saved.report["current_v211_authorization_consumed"] is not False
    ):
        _fail("A0.saved_authority", "v26.218 saved authority differs")
    return saved


def _authorization(
    review_path: Path,
) -> tuple[models.ExternalIndependentAuditAuthorization, bytes, bytes]:
    review = review_path.read_bytes()
    if len(review) != EXTERNAL_REVIEW_BYTES or _sha(review) != EXTERNAL_REVIEW_SHA256:
        _fail("A0.authorization", "v26.219 external review bytes differ")
    directive = OPERATOR_DIRECTIVE.encode("utf-8")
    return (
        cast(
            models.ExternalIndependentAuditAuthorization,
            models.make_identity(
                models.ExternalIndependentAuditAuthorization,
                {
                    "review_sha256": _sha(review),
                    "review_byte_count": len(review),
                    "operator_directive_sha256": _sha(directive),
                    "operator_directive_byte_count": len(directive),
                },
                field="authorization_id",
                prefix="finance_v26_219_external_independent_audit_authorization:",
            ),
        ),
        review,
        directive,
    )


def _freeze(authorization_id: str, saved: SavedV218) -> models.V218Freeze:
    return cast(
        models.V218Freeze,
        models.make_identity(
            models.V218Freeze,
            {
                "external_authorization_id": authorization_id,
                "v218_report_id": saved.report["report_id"],
                "v218_decision_id": saved.decision["decision_id"],
                "v218_transition_id": saved.transition["transition_id"],
                "v218_complement_binding_id": saved.complement["binding_id"],
                "v218_composition_contract_id": saved.composition["contract_id"],
                "v218_artifact_manifest_id": saved.artifact["manifest_id"],
                "v218_artifact_root": saved.artifact["artifact_root"],
            },
            field="freeze_id",
            prefix="finance_v26_219_v218_freeze:",
        ),
    )


def _source_identity(value: tuple[str, str]) -> models.SourceIdentity:
    return cast(
        models.SourceIdentity,
        models.make_identity(
            models.SourceIdentity,
            {
                "source_commit": value[0],
                "source_tree": value[1],
                "implementation_files": IMPLEMENTATION_FILES,
            },
            field="source_identity_id",
            prefix="finance_v26_219_source_identity:",
        ),
    )


def _implementation_binding(
    *,
    repository_root: Path,
    authorization_id: str,
    freeze_id: str,
    source: models.SourceIdentity,
) -> models.ImplementationBinding:
    if source.source_commit != "1" * 40:
        actual_tree = (
            _git(repository_root, "rev-parse", f"{source.source_commit}^{{tree}}").decode().strip()
        )
        if actual_tree != source.source_tree:
            _fail("source.tree", "v26.219 source tree differs")
    files: list[models.SourceBinding] = []
    for relative in IMPLEMENTATION_FILES:
        live = (repository_root / relative).read_bytes()
        if source.source_commit != "1" * 40:
            committed = _git(repository_root, "show", f"{source.source_commit}:{relative}")
            if committed != live:
                _fail("source.file", f"v26.219 live source differs:{relative}")
        files.append(
            models.SourceBinding(
                relative_path=relative,
                symbol="<file>",
                sha256=_sha(live),
                byte_count=len(live),
            )
        )
    values = (
        _detached_rebuild,
        _independent_registry_complement,
        _independent_retained_runtime,
        _independent_source_exit_persistence,
        _independent_full_rehash_attack,
        build,
    )
    symbols = tuple(
        models.SourceBinding(
            relative_path=AUDIT_FILE,
            symbol=value.__name__,
            sha256=_sha(inspect.getsource(value).encode("utf-8")),
            byte_count=len(inspect.getsource(value).encode("utf-8")),
        )
        for value in values
    )
    tree = ast.parse((repository_root / AUDIT_FILE).read_text(encoding="utf-8"))
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    candidate_helpers = {
        "_complement_binding",
        "ExactRegistryComplementAuthority",
        "run_same_length_full_rehash_attack",
        "ArtifactBackedFailureConsumer",
    }
    imported_roots = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    if called & candidate_helpers or imported_roots & {
        "requests",
        "urllib",
        "httpx",
        "socket",
    }:
        _fail("source.independence", "v26.219 calls a candidate helper or network route")
    return cast(
        models.ImplementationBinding,
        models.make_identity(
            models.ImplementationBinding,
            {
                "authorization_id": authorization_id,
                "freeze_id": freeze_id,
                "source_commit": source.source_commit,
                "source_tree": source.source_tree,
                "files": tuple(files),
                "symbols": symbols,
            },
            field="binding_id",
            prefix="fresh_repaired_registry_complement_independent_audit_implementation_binding:",
        ),
    )


def _detached_rebuild(
    *,
    repository_root: Path,
    freeze_id: str,
    saved: SavedV218,
    work_root: Path,
) -> tuple[models.DetachedRebuildAudit, Path]:
    archive = work_root / "v218-source.tar"
    snapshot = work_root / "snapshot"
    snapshot.mkdir()
    archive_run = subprocess.run(
        [
            "git",
            "archive",
            "--format=tar",
            f"--output={archive}",
            models.V218_COMMIT,
            "trusted_data_synthesis/src",
        ],
        cwd=repository_root,
        check=False,
        capture_output=True,
    )
    if archive_run.returncode:
        _fail("A1.archive", archive_run.stderr.decode("utf-8", errors="replace"))
    with tarfile.open(archive) as stream:
        stream.extractall(snapshot, filter="data")
    tree = _git(repository_root, "rev-parse", f"{models.V218_COMMIT}^{{tree}}").decode().strip()
    if tree != models.V218_TREE:
        _fail("A1.tree", "detached v26.218 source tree differs")
    archived_files = sum(path.is_file() for path in snapshot.rglob("*"))
    rebuilt = work_root / "rebuilt"
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(snapshot / "trusted_data_synthesis/src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C.UTF-8",
    }
    credential_like = tuple(
        key
        for key in env
        if any(token in key.casefold() for token in ("key", "token", "secret", "credential"))
    )
    if credential_like:
        _fail("A1.environment", f"credential-like detached environment keys:{credential_like}")
    rebuild_run = subprocess.run(
        [
            sys.executable,
            "-m",
            V218_MODULE,
            "--repository-root",
            str(repository_root),
            "--output-dir",
            str(rebuilt),
            "--external-review",
            str(saved.root / "external_review.txt"),
            "--source-commit",
            models.V218_COMMIT,
            "--source-tree",
            models.V218_TREE,
        ],
        cwd=snapshot,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if rebuild_run.returncode:
        _fail("A1.detached_execution", rebuild_run.stderr[-6000:])
    rebuilt_files = _all_files(rebuilt)
    if set(rebuilt_files) != set(saved.files):
        _fail("A1.paths", "detached v26.218 rebuild path set differs")
    sha_matches = sum(_sha(rebuilt_files[name]) == _sha(saved.files[name]) for name in saved.files)
    count_matches = sum(len(rebuilt_files[name]) == len(saved.files[name]) for name in saved.files)
    actual_matches = sum(rebuilt_files[name] == saved.files[name] for name in saved.files)
    total = sum(map(len, rebuilt_files.values()))
    if (sha_matches, count_matches, actual_matches, total) != (51, 51, 51, 1_054_511):
        _fail("A1.bytes", "detached v26.218 rebuild bytes differ")
    audit = cast(
        models.DetachedRebuildAudit,
        models.make_identity(
            models.DetachedRebuildAudit,
            {
                "freeze_id": freeze_id,
                "archived_source_file_count": archived_files,
            },
            field="audit_id",
            prefix="finance_v26_219_detached_rebuild_audit:",
        ),
    )
    return audit, rebuilt


def _registry_pairs(registry: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    try:
        return tuple(
            sorted(
                (str(item["terminal_kind"]), str(item["policy_id"]))
                for item in registry["policies"]
                if item["registration_status"] == "reachable"
            )
        )
    except (KeyError, TypeError) as error:
        _fail("A2.registry_shape", f"v26.195 Registry shape differs:{error}")


def _independent_registry_complement(
    *, repository_root: Path, freeze_id: str, saved: SavedV218
) -> models.IndependentRegistryComplementAudit:
    registry_path = repository_root / V195_DIR / "fresh_terminal_registry.json"
    registry_bytes = registry_path.read_bytes()
    registry = cast(dict[str, Any], json.loads(registry_bytes))
    if registry.get("registry_id") != models.REGISTRY_ID:
        _fail("A2.registry_identity", "v26.195 Registry identity differs")
    reachable_pairs = _registry_pairs(registry)
    admitted_mapping = tuple(
        tuple(str(value) for value in item)
        for item in cast(list[list[Any]], saved.complement["admitted_event_terminal_policy_items"])
    )
    admitted = tuple(sorted({item[1] for item in admitted_mapping}))
    reachable = {item[0] for item in reachable_pairs}
    forbidden = tuple(sorted(reachable - set(admitted)))
    expected = dict(saved.complement)
    independent_projection = dict(expected)
    independent_projection.update(
        {
            "reachable_terminal_policy_items": [list(item) for item in reachable_pairs],
            "admitted_event_terminal_policy_items": [list(item) for item in admitted_mapping],
            "admitted_terminal_kinds": list(admitted),
            "forbidden_terminal_kinds": list(forbidden),
        }
    )
    if (
        len(reachable_pairs) != 16
        or admitted != ("instrument_failure",)
        or len(forbidden) != 15
        or set(admitted) | set(forbidden) != reachable
        or set(admitted) & set(forbidden)
        or "provider_failure_no_payload" not in forbidden
        or "resource_budget_exhausted" not in forbidden
        or "provider_no_payload_failure" in forbidden
        or "resource_failure" in forbidden
        or models.canonical_bytes(independent_projection) != models.canonical_bytes(expected)
    ):
        _fail("A2.complement", "independent Registry complement differs")
    return cast(
        models.IndependentRegistryComplementAudit,
        models.make_identity(
            models.IndependentRegistryComplementAudit,
            {
                "freeze_id": freeze_id,
                "exact_v195_registry_file_sha256": _sha(registry_bytes),
                "candidate_binding_id": saved.complement["binding_id"],
                "reachable_terminal_policy_items": reachable_pairs,
                "admitted_event_terminal_policy_items": admitted_mapping,
                "admitted_terminal_kinds": admitted,
                "forbidden_terminal_kinds": forbidden,
            },
            field="audit_id",
            prefix="finance_v26_219_independent_registry_complement_audit:",
        ),
    )


def _independent_retained_runtime(
    *,
    repository_root: Path,
    freeze_id: str,
    saved: SavedV218,
    detached: models.DetachedRebuildAudit,
    rebuilt: Path,
) -> models.IndependentRetainedRuntimeAudit:
    paths = tuple(sorted(name for name in saved.files if name.startswith(RUNTIME_PREFIXES)))
    v217_root = repository_root / V217_DIR
    if (
        len(paths) != 35
        or sum(name.startswith("consumer_ingress/") for name in paths) != 2
        or sum(name.startswith("exit_surface_controls/") for name in paths) != 25
        or sum(name.startswith("upstream_") for name in paths) != 8
    ):
        _fail("A3.geometry", "retained runtime path geometry differs")
    v217_matches = sum(saved.files[name] == (v217_root / name).read_bytes() for name in paths)
    detached_matches = sum(saved.files[name] == (rebuilt / name).read_bytes() for name in paths)
    v217_execution = _load(v217_root / "exit_surface_execution_audit.json")
    embedded = saved.retained["v217_execution"]
    if (
        v217_matches != 35
        or detached_matches != 35
        or models.canonical_bytes(v217_execution) != models.canonical_bytes(embedded)
    ):
        _fail("A3.bytes", "retained v26.217 runtime or execution object differs")
    return cast(
        models.IndependentRetainedRuntimeAudit,
        models.make_identity(
            models.IndependentRetainedRuntimeAudit,
            {
                "freeze_id": freeze_id,
                "detached_rebuild_audit_id": detached.audit_id,
                "runtime_relative_paths_sha256": _sha(models.canonical_bytes(paths)),
            },
            field="audit_id",
            prefix="finance_v26_219_independent_retained_runtime_audit:",
        ),
    )


def _identity_matches(payload: dict[str, Any], field: str, prefix: str) -> bool:
    values = dict(payload)
    observed = values.pop(field)
    return observed == canonical_hash(values, prefix=prefix)


def _descriptor_relative(descriptor: dict[str, Any], directory: str) -> str:
    return f"{directory}/{_sha(str(descriptor['descriptor_id']).encode('utf-8'))}.json"


def _validate_e2_artifacts(root: Path, chain: dict[str, Any]) -> None:
    event = cast(dict[str, Any], chain["event"])
    event_descriptor = cast(dict[str, Any], chain["event_descriptor"])
    observation = cast(dict[str, Any], chain["observation"])
    observation_descriptor = cast(dict[str, Any], chain["observation_descriptor"])
    expected = (
        (str(event_descriptor["relative_path"]), event),
        (_descriptor_relative(event_descriptor, "upstream_event_descriptors"), event_descriptor),
        (str(observation_descriptor["relative_path"]), observation),
        (
            _descriptor_relative(observation_descriptor, "upstream_observation_descriptors"),
            observation_descriptor,
        ),
    )
    if any((root / name).read_bytes() != _bytes(value) for name, value in expected):
        _fail("A4.e2_artifacts", "E2 upstream artifact bytes differ")


def _independent_source_exit_persistence(
    *,
    repository_root: Path,
    freeze_id: str,
    saved: SavedV218,
    rebuilt: Path,
) -> models.IndependentSourceExitPersistenceAudit:
    v217_root = repository_root / V217_DIR
    raw_root = saved.root / "exit_surface_controls/raw"
    by_exit: dict[str, models.IndependentSourceExitChainRow] = {}
    common = (
        "job_id",
        "invocation_id",
        "source_exit_id",
        "observation_id",
        "evidence_id",
        "decision_id",
        "terminal_kind",
        "persistence_binding_id",
        "formal_empirical_row",
        "provider_calls",
    )
    for raw_path in sorted(raw_root.glob("*.json")):
        basename = raw_path.name
        layer_by_name = {
            layer: cast(
                dict[str, Any], _load(saved.root / "exit_surface_controls" / layer / basename)
            )
            for layer, _, _ in IDENTITY_SPECS
        }
        raw = layer_by_name["raw"]
        observation = cast(dict[str, Any], raw["failure_observation"])
        proof = cast(dict[str, Any], observation["source_exit_proof"])
        evidence = cast(dict[str, Any], raw["authenticated_evidence"])
        decision = cast(dict[str, Any], raw["derived_terminal_decision"])
        exit_code = str(proof["exit_code"])
        terminal = str(raw["terminal_kind"])
        if exit_code not in EXIT_ORDER or exit_code in by_exit:
            _fail("A4.exit_set", "source-exit set differs")
        if (
            evidence["failure_observation"] != observation
            or decision["terminal_kind"] != terminal
            or observation["caught_terminal_kind"] != terminal
            or observation["invocation_record"]["typed_terminal"] != terminal
            or proof["terminal_kind"] != terminal
            or any(
                any(layer[key] != raw[key] for key in common) for layer in layer_by_name.values()
            )
            or layer_by_name["result"]["raw_id"] != raw["raw_id"]
            or layer_by_name["trace"]["result_id"] != layer_by_name["result"]["result_id"]
            or layer_by_name["outcome"]["trace_id"] != layer_by_name["trace"]["trace_id"]
            or layer_by_name["checkpoint"]["outcome_id"] != layer_by_name["outcome"]["outcome_id"]
        ):
            _fail("A4.parents", f"source-exit chain parents differ:{exit_code}")
        identity_matches = sum(
            _identity_matches(layer_by_name[layer], field, prefix)
            for layer, field, prefix in IDENTITY_SPECS
        )
        saved_to_v217 = sum(
            (saved.root / "exit_surface_controls" / layer / basename).read_bytes()
            == (v217_root / "exit_surface_controls" / layer / basename).read_bytes()
            for layer, _, _ in IDENTITY_SPECS
        )
        detached_matches = sum(
            (saved.root / "exit_surface_controls" / layer / basename).read_bytes()
            == (rebuilt / "exit_surface_controls" / layer / basename).read_bytes()
            for layer, _, _ in IDENTITY_SPECS
        )
        if (identity_matches, saved_to_v217, detached_matches) != (5, 5, 5):
            _fail("A4.layer_bytes", f"source-exit layer bytes differ:{exit_code}")
        chain = proof.get("upstream_artifact_chain")
        if exit_code == "E2_authenticated_rethrow":
            if not isinstance(chain, dict):
                _fail("A4.e2_chain", "E2 upstream artifact chain absent")
            _validate_e2_artifacts(saved.root, chain)
        elif chain is not None:
            _fail("A4.non_e2_chain", "non-E2 source exit has upstream chain")
        by_exit[exit_code] = cast(
            models.IndependentSourceExitChainRow,
            models.make_identity(
                models.IndependentSourceExitChainRow,
                {
                    "exit_code": exit_code,
                    "terminal_kind": terminal,
                    "job_id": raw["job_id"],
                    "invocation_id": raw["invocation_id"],
                    "source_exit_id": raw["source_exit_id"],
                    "observation_id": raw["observation_id"],
                    "evidence_id": raw["evidence_id"],
                    "decision_id": raw["decision_id"],
                    "raw_id": raw["raw_id"],
                    "result_id": layer_by_name["result"]["result_id"],
                    "trace_id": layer_by_name["trace"]["trace_id"],
                    "outcome_id": layer_by_name["outcome"]["outcome_id"],
                    "checkpoint_id": layer_by_name["checkpoint"]["checkpoint_id"],
                    "e2_upstream_artifact_chain_present": isinstance(chain, dict),
                },
                field="row_id",
                prefix="finance_v26_219_independent_source_exit_chain_row:",
            ),
        )
    rows = tuple(by_exit[code] for code in EXIT_ORDER)
    return cast(
        models.IndependentSourceExitPersistenceAudit,
        models.make_identity(
            models.IndependentSourceExitPersistenceAudit,
            {"freeze_id": freeze_id, "rows": rows},
            field="audit_id",
            prefix="finance_v26_219_independent_source_exit_persistence_audit:",
        ),
    )


def _independent_admit(
    candidate: dict[str, Any], reachable_pairs: tuple[tuple[str, str], ...]
) -> None:
    reachable = {item[0] for item in reachable_pairs}
    admitted = set(candidate["admitted_terminal_kinds"])
    forbidden = tuple(candidate["forbidden_terminal_kinds"])
    if (
        tuple(tuple(item) for item in candidate["reachable_terminal_policy_items"])
        != reachable_pairs
        or tuple(sorted(reachable - admitted)) != forbidden
        or admitted | set(forbidden) != reachable
        or admitted & set(forbidden)
    ):
        _fail(
            "independent_registry_complement_admission",
            "candidate terminal domain is not the exact v26.195 reachable complement",
        )


def _independent_full_rehash_attack(
    *,
    freeze_id: str,
    saved: SavedV218,
    registry_audit: models.IndependentRegistryComplementAudit,
) -> models.IndependentFullRehashAttackAudit:
    candidate = dict(saved.complement)
    wrong = tuple(
        sorted(
            "provider_no_payload_failure"
            if item == "provider_failure_no_payload"
            else "resource_failure"
            if item == "resource_budget_exhausted"
            else item
            for item in registry_audit.forbidden_terminal_kinds
        )
    )
    if len(wrong) != 15:
        _fail("A5.geometry", "same-length independent attack geometry differs")
    binding_values = dict(candidate)
    binding_values.pop("binding_id")
    binding_values["forbidden_terminal_kinds"] = list(wrong)
    candidate_binding_id = canonical_hash(
        binding_values, prefix="fresh_repaired_exact_v195_registry_complement_binding:"
    )
    candidate["binding_id"] = candidate_binding_id
    candidate["forbidden_terminal_kinds"] = list(wrong)
    composition_values = dict(saved.composition)
    composition_values.pop("contract_id")
    composition_values["complement_binding_id"] = candidate_binding_id
    candidate_composition_id = canonical_hash(
        composition_values,
        prefix="fresh_repaired_exact_registry_complement_composition_contract:",
    )
    candidate_gate_id = canonical_hash(
        {
            "gate_name": "exact_v195_reachable_terminal_complement",
            "evidence_id": candidate_binding_id,
            "passed": True,
            "schema_version": saved.complement["schema_version"],
        },
        prefix="finance_v26_218_gate:",
    )
    candidate_report_id = canonical_hash(
        {
            "candidate_binding_id": candidate_binding_id,
            "candidate_composition_id": candidate_composition_id,
            "candidate_gate_id": candidate_gate_id,
            "claimed_result": "passed",
            "schema_version": saved.complement["schema_version"],
        },
        prefix="finance_v26_218_fully_rehashed_attack_report:",
    )
    try:
        _independent_admit(candidate, registry_audit.reachable_terminal_policy_items)
    except V219Error as error:
        if error.stage != "independent_registry_complement_admission":
            raise
        saved_control = cast(dict[str, Any], saved.negative["control"])
        calculated = (
            candidate_binding_id,
            candidate_composition_id,
            candidate_gate_id,
            candidate_report_id,
        )
        expected = (
            saved_control["candidate_binding_id"],
            saved_control["candidate_composition_id"],
            saved_control["candidate_gate_id"],
            saved_control["candidate_report_id"],
        )
        if calculated != expected:
            _fail("A5.identity_match", "independent attack identities differ")
        return cast(
            models.IndependentFullRehashAttackAudit,
            models.make_identity(
                models.IndependentFullRehashAttackAudit,
                {
                    "freeze_id": freeze_id,
                    "registry_complement_audit_id": registry_audit.audit_id,
                    "candidate_binding_id": candidate_binding_id,
                    "candidate_composition_id": candidate_composition_id,
                    "candidate_gate_id": candidate_gate_id,
                    "candidate_report_id": candidate_report_id,
                    "saved_negative_control_id": saved_control["control_id"],
                    "rejection_reason_sha256": _sha(str(error).encode("utf-8")),
                },
                field="audit_id",
                prefix="finance_v26_219_independent_full_rehash_attack_audit:",
            ),
        )
    _fail("A5.accepted", "same-length full-rehash attack was independently admitted")


def _gate(name: str, evidence_id: str) -> models.GateResult:
    return cast(
        models.GateResult,
        models.make_identity(
            models.GateResult,
            {"gate_name": name, "evidence_id": evidence_id},
            field="gate_id",
            prefix="finance_v26_219_gate:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.Report:
    if output_dir.exists():
        raise FileExistsError(f"v26.219 output already exists:{output_dir}")
    external, review_bytes, directive_bytes = _authorization(external_review_path)
    saved = _saved_v218(repository_root)
    freeze = _freeze(external.authorization_id, saved)
    source = _source_identity(source_identity)
    implementation = _implementation_binding(
        repository_root=repository_root,
        authorization_id=external.authorization_id,
        freeze_id=freeze.freeze_id,
        source=source,
    )
    with tempfile.TemporaryDirectory(prefix="v26-219-independent-") as temporary:
        detached, rebuilt = _detached_rebuild(
            repository_root=repository_root,
            freeze_id=freeze.freeze_id,
            saved=saved,
            work_root=Path(temporary),
        )
        registry = _independent_registry_complement(
            repository_root=repository_root, freeze_id=freeze.freeze_id, saved=saved
        )
        retained = _independent_retained_runtime(
            repository_root=repository_root,
            freeze_id=freeze.freeze_id,
            saved=saved,
            detached=detached,
            rebuilt=rebuilt,
        )
        source_exits = _independent_source_exit_persistence(
            repository_root=repository_root,
            freeze_id=freeze.freeze_id,
            saved=saved,
            rebuilt=rebuilt,
        )
        attack = _independent_full_rehash_attack(
            freeze_id=freeze.freeze_id, saved=saved, registry_audit=registry
        )
    scope = cast(
        models.ScopeBoundaryAudit,
        models.make_identity(
            models.ScopeBoundaryAudit,
            {
                "authorization_id": external.authorization_id,
                "freeze_id": freeze.freeze_id,
            },
            field="audit_id",
            prefix="finance_v26_219_scope_boundary_audit:",
        ),
    )
    gates = cast(
        models.GateEvaluation,
        models.make_identity(
            models.GateEvaluation,
            {
                "gates": (
                    _gate("external_scope_and_exact_v218_freeze", freeze.freeze_id),
                    _gate("detached_exact_directory_rebuild", detached.audit_id),
                    _gate("independent_exact_registry_complement", registry.audit_id),
                    _gate("independent_retained_runtime_bytes", retained.audit_id),
                    _gate("independent_five_source_exit_persistence_chains", source_exits.audit_id),
                    _gate("independent_same_length_full_rehash_attack", attack.audit_id),
                    _gate("zero_provider_credential_empirical_boundary", scope.audit_id),
                )
            },
            field="evaluation_id",
            prefix="finance_v26_219_gate_evaluation:",
        ),
    )
    decision = cast(
        models.Decision,
        models.make_identity(
            models.Decision,
            {
                "authorization_id": external.authorization_id,
                "freeze_id": freeze.freeze_id,
                "detached_rebuild_audit_id": detached.audit_id,
                "registry_complement_audit_id": registry.audit_id,
                "retained_runtime_audit_id": retained.audit_id,
                "source_exit_persistence_audit_id": source_exits.audit_id,
                "full_rehash_attack_audit_id": attack.audit_id,
                "gate_evaluation_id": gates.evaluation_id,
            },
            field="decision_id",
            prefix="finance_v26_219_independent_audit_decision:",
        ),
    )
    transition = cast(
        models.Transition,
        models.make_identity(
            models.Transition,
            {"decision_id": decision.decision_id},
            field="transition_id",
            prefix="finance_v26_219_transition:",
        ),
    )
    report = cast(
        models.Report,
        models.make_identity(
            models.Report,
            {
                "run_id": RUN_ID,
                "source_identity_id": source.source_identity_id,
                "implementation_binding_id": implementation.binding_id,
                "authorization_id": external.authorization_id,
                "freeze_id": freeze.freeze_id,
                "detached_rebuild_audit_id": detached.audit_id,
                "registry_complement_audit_id": registry.audit_id,
                "retained_runtime_audit_id": retained.audit_id,
                "source_exit_persistence_audit_id": source_exits.audit_id,
                "full_rehash_attack_audit_id": attack.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "gate_evaluation_id": gates.evaluation_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
            },
            field="report_id",
            prefix="finance_v26_219_independent_audit_report:",
        ),
    )
    payloads = {
        "external_review.txt": review_bytes,
        "operator_authorization.txt": directive_bytes,
        "external_independent_audit_authorization.json": _bytes(external),
        "v218_freeze.json": _bytes(freeze),
        "source_identity.json": _bytes(source),
        "implementation_binding.json": _bytes(implementation),
        "detached_rebuild_audit.json": _bytes(detached),
        "independent_registry_complement_audit.json": _bytes(registry),
        "independent_retained_runtime_audit.json": _bytes(retained),
        "independent_source_exit_persistence_audit.json": _bytes(source_exits),
        "independent_full_rehash_attack_audit.json": _bytes(attack),
        "scope_boundary_audit.json": _bytes(scope),
        "gate_evaluation.json": _bytes(gates),
        "decision.json": _bytes(decision),
        "prospective_transition.json": _bytes(transition),
        "report.json": _bytes(report),
    }
    for name, payload in sorted(payloads.items()):
        _write(output_dir / name, payload)
    members = {
        path.relative_to(output_dir).as_posix(): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    }
    manifest = models.artifact_manifest(RUN_ID, members)
    _write(output_dir / "artifact_manifest.json", _bytes(manifest))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-review", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    report = build(
        repository_root=args.repository_root.resolve(),
        output_dir=args.output_dir.resolve(),
        external_review_path=args.external_review.resolve(),
        source_identity=(args.source_commit, args.source_tree),
    )
    print(models.canonical_bytes(report).decode("utf-8"))


if __name__ == "__main__":
    main()
