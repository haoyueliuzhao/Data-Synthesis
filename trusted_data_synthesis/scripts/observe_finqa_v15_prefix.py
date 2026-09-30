#!/usr/bin/env python3
"""Observe saved prefix commits and acceptance; do not load tensors or change a run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trusted_synthesis.finance_research.calibration import identity, now  # noqa: E402
from trusted_synthesis.finance_research.v6_collection import bound, persist  # noqa: E402


def read(path):
    raw = Path(path).read_bytes()
    value = json.loads(raw)
    ref = dict(path=str(Path(path).resolve()), sha256=hashlib.sha256(raw).hexdigest())
    if "id" in value:
        ref["id"] = value["id"]
    return value, ref


def observe(root):
    root = Path(root).resolve()
    launch, launch_ref = read(root / "workflow_launch/record.json")
    workflow, _ = read(root / "workflow/status.json")
    plan, plan_ref = read(root / "prefix_training/registration/record.json")
    children = {c["job_key"]: c for c in workflow.get("active_children", [])}
    seeds = {}
    for seed in (11, 29, 47):
        directory = root / "prefix_training" / f"seed{seed}"
        available = []
        for path in (directory / "shared").glob("step*_*/record.json"):
            match = re.fullmatch(r"step(\d+)_(initial|step)", path.parent.name)
            if match:
                available.append((int(match[1]), path))
        latest = max(available, default=None, key=lambda pair: pair[0])
        saved, saved_ref = read(latest[1]) if latest else ({}, None)
        acceptance = directory / "shared/first_step_acceptance/record.json"
        accepted, acceptance_ref = read(acceptance) if acceptance.exists() else ({}, None)
        first_launch = directory / "launch_attempts/attempt001/intent/record.json"
        intent, intent_ref = read(first_launch) if first_launch.exists() else ({}, None)
        child = children.get(f"prefix-seed{seed}")
        seeds[str(seed)] = dict(
            committed_step=latest[0] if latest else 0,
            latest_commit=saved_ref,
            latest_saved_state_digest=saved.get("actual_state_digest"),
            launch_intent=intent_ref,
            gpu_index=intent.get("gpu_observed", {}).get("index"),
            first_step_acceptance=acceptance_ref,
            first_step_acceptance_fields=accepted,
            process_alive=bool(child and identity(child["pid"]) == child["birth"]),
            physical_updates_not_repeated_for_acceptance=accepted.get("repeat_first_update")
            is False,
            stopped_records=[
                str(p) for p in directory.glob("launch_attempts/*/stopped/record.json")
            ],
        )
    seal_path, material_path = (
        root / "completion_seal/record.json",
        root / "material/result/record.json",
    )
    seal, seal_ref = read(seal_path) if seal_path.exists() else ({}, None)
    material, material_ref = read(material_path) if material_path.exists() else ({}, None)
    return bound(
        dict(
            schema="v15_prefix_progress_observation.v1",
            at=now(),
            source_launch=launch_ref,
            source_prefix_plan=plan_ref,
            source_code_commit=launch["code_commit"],
            source_worktree=launch["worktree"],
            workflow_phase=workflow["phase"],
            workflow_alive=identity(launch["pid"]) == launch["process_start_time_ticks"],
            seeds=seeds,
            hard_stop_per_seed=plan["stop_step"],
            mapping=dict(
                seal=seal_ref,
                expected=seal.get("expected_calls"),
                returned=seal.get("actual_returns"),
                usable=seal.get("mapping_complete_calls"),
                network_unknowns=seal.get("network_unknowns"),
            ),
            full_material=dict(
                result=material_ref,
                phase=material.get("phase"),
                binding_exists=(root / "material/binding/record.json").exists(),
            ),
            API_calls=0,
            tensor_files_loaded=0,
            run_modified=False,
            observer_script=dict(
                path=str(Path(__file__).resolve()),
                sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            ),
            snapshot_not_full_training_completion=True,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    value = observe(args.output)
    if args.snapshot is not None:
        if args.snapshot.exists():
            raise ValueError("new snapshot directory only")
        persist(args.snapshot, value)
    print(
        json.dumps(
            dict(
                id=value["id"],
                at=value["at"],
                workflow_alive=value["workflow_alive"],
                workflow_phase=value["workflow_phase"],
                seeds={
                    s: {
                        k: r[k]
                        for k in (
                            "committed_step",
                            "gpu_index",
                            "process_alive",
                            "physical_updates_not_repeated_for_acceptance",
                        )
                    }
                    for s, r in value["seeds"].items()
                },
                mapping=value["mapping"],
                full_material=value["full_material"],
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
