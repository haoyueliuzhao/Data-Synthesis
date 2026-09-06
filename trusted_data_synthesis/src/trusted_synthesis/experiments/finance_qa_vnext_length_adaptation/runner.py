"""Freeze once, adapt once, with byte-preserved historical inputs and CPU-only checks."""

from __future__ import annotations

import platform
from importlib import metadata
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from ..finance_qa_vnext_model_execution.models import require, sha
from . import core, source
from .controls import run_controls
from .cpu import build_batches
from .guards import guard_report, zero_execution_guard


class Store:
    def __init__(self, directory: Path):
        require(not directory.exists(), "length.output_already_exists")
        directory.mkdir(parents=True)
        self.root = directory

    def bytes(self, name: str, data: bytes):
        path = self.root / name
        require(not path.exists(), "length.artifact_already_exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)

    def json(self, name: str, value: Any):
        self.bytes(name, canonical_json_bytes(value))

    def seal(self, **fields: Any) -> dict[str, Any]:
        files = []
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                raw = path.read_bytes()
                files.append(
                    {
                        "path": path.relative_to(self.root).as_posix(),
                        "sha256": sha(raw),
                        "byte_count": len(raw),
                    }
                )
        manifest = core.record("manifest", **fields, files=files, file_count=len(files))
        self.json("manifest.json", manifest)
        return manifest


def verify(directory: Path) -> dict[str, Any]:
    manifest = source.load(directory / "manifest.json")
    core.identity(manifest, "manifest")
    actual = {
        path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()
    }
    require(
        actual == {item["path"] for item in manifest["files"]} | {"manifest.json"},
        "length.manifest_exhaustive",
    )
    for item in manifest["files"]:
        relative = Path(item["path"])
        require(not relative.is_absolute() and ".." not in relative.parts, "length.manifest_path")
        path = directory / relative
        require(not path.is_symlink(), "length.manifest_symlink")
        raw = path.read_bytes()
        require(
            len(raw) == item["byte_count"] and sha(raw) == item["sha256"], "length.manifest_bytes"
        )
    return manifest


def prepare(root: Path, directory: Path) -> dict[str, Any]:
    root, directory = root.resolve(), directory.resolve()
    require(not directory.exists(), "length.preparation_already_exists")
    with zero_execution_guard() as counts:
        anchor = source.source_anchor(root)
        history = source.history_inventory(root)
        inputs = source.read_source(root)
        tokenizer = core.assets.load_tokenizer(inputs["binding"])
        require(
            tokenizer.chat_template == inputs["binding"]["chat_template"], "length.prepare_template"
        )
        condition = core.freeze_condition(inputs)
        implementation = source.source_snapshot(root)
        store = Store(directory)
        store.json("condition.json", condition)
        store.json("tokenizer_assets.json", core.asset_binding(inputs["binding"]))
        # Copy exact historical binding bytes, with no new identity or changed cap.
        store.bytes(
            "historical_tokenizer_binding.json",
            (root / source.HISTORICAL_ROOT / "preparation/tokenizer_binding.json").read_bytes(),
        )
        store.json("source_anchor.json", anchor)
        store.json("history_inventory.json", history)
        store.json("implementation.json", implementation)
        store.json(
            "source_bindings.json", source.validate_candidates(inputs, inputs["dataset"]["rows"])
        )
        store.json(
            "software.json",
            core.record(
                "software",
                python=platform.python_version(),
                packages={
                    name: metadata.version(name)
                    for name in ("numpy", "torch", *core.assets.SOFTWARE_PACKAGES)
                },
                cpu_only=True,
            ),
        )
        report = core.record(
            "preparation",
            stage=core.STAGE,
            condition_id=condition["id"],
            source_anchor_id=anchor["id"],
            implementation_id=implementation["id"],
            history_inventory_id=history["id"],
            actual_assets_verified=True,
            input_sessions=2,
            original_candidates=34,
            new_length_conditions=1,
            output_results_not_yet_observed=True,
        )
        store.json("report.json", report)
    guards = guard_report(counts)
    require(guards["all_zero"] and not guards["cuda_initialized"], "length.prepare_zero_execution")
    store.json("execution_guards.json", guards)
    store.seal(stage=core.STAGE, condition_id=condition["id"], phase="preparation")
    verify(directory)
    return report


def run(root: Path, preparation: Path, directory: Path) -> dict[str, Any]:
    root, preparation, directory = root.resolve(), preparation.resolve(), directory.resolve()
    require(not directory.exists(), "length.adaptation_already_exists")
    prepared_manifest = verify(preparation)
    condition = source.load(preparation / "condition.json")
    implementation = source.load(preparation / "implementation.json")
    with zero_execution_guard() as counts:
        require(source.source_snapshot(root) == implementation, "length.frozen_source_changed")
        history = source.load(preparation / "history_inventory.json")
        require(source.history_inventory(root) == history, "length.history_changed_before_run")
        require(
            source.source_anchor(root) == source.load(preparation / "source_anchor.json"),
            "length.source_anchor_changed",
        )
        inputs = source.read_source(root)
        core.validate_condition(condition, inputs)
        tokenizer = core.assets.load_tokenizer(inputs["binding"])
        token_dataset, comparison = core.encode(inputs, condition, tokenizer)
        packages = core.session_packages(inputs, token_dataset)
        cpu, binaries = build_batches(inputs, token_dataset, condition, tokenizer)
        controls = run_controls(inputs, condition, token_dataset, tokenizer)
        unchanged_history = source.history_inventory(root) == history
        unchanged_source = source.source_snapshot(root) == implementation
        require(unchanged_history and unchanged_source, "length.input_or_source_changed_during_run")
        require(
            core.asset_binding(inputs["binding"])["id"] == condition["tokenizer_asset_id"],
            "length.assets_changed_during_run",
        )
        store = Store(directory)
        store.json("token_representations.json", token_dataset)
        store.json("historical_comparison.json", comparison)
        store.json("session_packages.json", packages)
        store.json("cpu_loading.json", cpu)
        store.json("controls.json", controls)
        for name, binary in binaries.items():
            store.bytes(name, binary)
            require((directory / name).read_bytes() == binary, "length.persisted_cpu_bytes")
        lengths = [
            {
                "candidate_id": row["id"],
                "session_id": row["session_id"],
                "display_turn": row["turn_index"] + 1,
                "kind": row["submission_kind"],
                "prompt": token["prompt_token_count"],
                "target": token["target_token_count"],
                "suffix": token["suffix_token_count"],
                "sequence": token["sequence_length"],
                "new_headroom": core.MAXIMUM_SEQUENCE_LENGTH - token["sequence_length"],
                "old_status": old["tokenrepresentation_status"],
                "new_status": token["tokenrepresentation_status"],
            }
            for row, old, token in zip(
                inputs["dataset"]["rows"],
                inputs["old_tokens"]["records"],
                token_dataset["records"],
                strict=True,
            )
        ]
        store.json("lengths.json", core.record("lengths", rows=lengths))
        completed = (
            token_dataset["positive_representation_validated"]
            and packages["complete_session_packages"] == 2
            and cpu["loaded_records"] == 34
            and controls["all_expected_outcomes"]
        )
        fields = dict(
            stage=core.STAGE,
            representation_condition_id=condition["id"],
            preparation_manifest_id=prepared_manifest["id"],
            implementation_id=implementation["id"],
            source_commit=implementation["git_commit"],
            historical_source_commit=source.PARENT_COMMIT,
            historical_teacher_condition_id=inputs["teacher_condition"]["id"],
            historical_supervision_dataset_id=inputs["dataset"]["id"],
            historical_token_dataset_id=inputs["old_tokens"]["id"],
            historical_24576_result={
                "status": "contains_not_fit",
                "fit_count": 32,
                "not_fit_count": 2,
                "complete_session_packages": 0,
                "unchanged": True,
            },
            status="complete" if completed else "adaptation_incomplete",
            raw_candidates=34,
            consumable_records=token_dataset["fit_count"],
            not_fit_records=token_dataset["not_fit_count"],
            complete_session_packages=packages["complete_session_packages"],
            new_maximum_sequence_length=core.MAXIMUM_SEQUENCE_LENGTH,
            actual_model_max_position_embeddings=condition["model_max_position_embeddings"],
            maximum_observed_sequence_length=max(
                item["sequence_length"] for item in token_dataset["records"]
            ),
            historical_fit_arrays_identical_count=sum(
                item["arrays_identical"] is True for item in comparison["rows"]
            ),
            historical_not_fit_reencoded_count=sum(
                item["old_not_fit_reencoded_from_original_candidate"] for item in comparison["rows"]
            ),
            local_control_count=controls["control_count"],
            cpu_batch_count=cpu["batch_count"],
            historical_file_count=history["file_count"],
            historical_byte_count=history["byte_count"],
            historical_inventory_id=history["id"],
            historical_files_unchanged=unchanged_history,
            source_files_unchanged=unchanged_source,
            original_content_and_parents_unchanged=True,
            model_qualification_recomputed=False,
            new_provider_calls=0,
            new_model_sessions=0,
            finance_runtime_executions=0,
            student_weight_loads=0,
            student_forward_calls=0,
            student_parameter_updates=0,
            GPU_jobs=0,
            training_or_utility_validated=False,
            class_weights_assigned=False,
            new_quotient_classes_claimed=False,
            new_task_panel_started=False,
            old_mainline_remains_paused=True,
        )
    guards = guard_report(counts)
    require(guards["all_zero"] and not guards["cuda_initialized"], "length.run_zero_execution")
    store.json("execution_guards.json", guards)
    report = core.record("report", **fields, execution_guard_report_id=guards["id"])
    store.json("report.json", report)
    store.seal(stage=core.STAGE, condition_id=condition["id"], phase="adaptation")
    verify(directory)
    return report
