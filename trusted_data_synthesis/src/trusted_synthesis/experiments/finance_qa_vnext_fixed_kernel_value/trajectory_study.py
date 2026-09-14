"""Prospective fresh-Student trajectory representation revision.

The complete original material authority is reused directly from the parent.
Only a derived compact prefix-union cache is built. Identical labels, weights,
tasks, seeds and global update counts do not imply identical dropout paths or
bitwise identical optimization. Interrupted parent Students are not resumed.
"""

import argparse
import json
import subprocess
from pathlib import Path

from . import execution
from . import protocol as p

BRANCH = "codex/fixed-kernel-trajectory-execution-20260914"
PARENT_COMMIT = "ba07c5655eeceb60a222ec6a25bdf8cf33ffd05f"
PARENT_ROOT = Path("/tmp/data-synthesis-fixed-kernel-fast-execution-20260914")
MATERIALS_ROOT = Path("/tmp/data-synthesis-fixed-kernel-completion-20260914")
DATA_ROOT = Path("/data1/zhuxinrui/projects/Data-Synthesis")
MATERIALS = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/study_20260914_budget_completion"
)
PARENT_OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/fast_execution_20260914"
)
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/trajectory_execution_20260914"
)
RUNTIME = "trusted_data_synthesis/runtime/fixed_kernel_trajectory_execution_20260914"
EXPECTED_GATE = "material_gate:16d9491e7ca7b6b506bc5308b67dc9de5b2958e94cba0d2944c5b9395f23e763"
EXPECTED_KERNEL = "fixed_kernel:f67d9edd0712d87d6d63d6e9535f8ff2db677cb81c884780afc8315c1d15c729"


def root_path():
    return Path(__file__).resolve().parents[5]


def guard(root):
    root = Path(root).resolve()
    p.require(
        root == root_path() and root not in (PARENT_ROOT, MATERIALS_ROOT),
        "trajectory_execution.isolated_source_root",
    )
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=root, text=True
    ).strip()
    p.require(branch == BRANCH, "trajectory_execution.prospective_revision_branch")
    return root


def prepare(root, *, workers=24):
    root = guard(root)
    output = root / OUTPUT
    p.require(not output.exists(), "trajectory_execution.one_new_cache_and_prepare")
    p.require(
        not (PARENT_ROOT / PARENT_OUTPUT / "report.json").exists(),
        "trajectory_execution.incomplete_parent_not_relabelled_complete",
    )
    frozen = execution.prepare(
        root,
        output,
        input_root=PARENT_ROOT,
        parent_freeze_path=PARENT_ROOT / PARENT_OUTPUT / "preparation/execution_freeze.json",
        parent_authority_path=PARENT_ROOT
        / PARENT_OUTPUT
        / "preparation/fast_execution_authority.json",
        workers=workers,
    )
    p.require(
        frozen["kernel_id"] == EXPECTED_KERNEL
        and frozen["original_material_gate_id"] == EXPECTED_GATE
        and frozen["source_material_validation_reused"] is True
        and frozen["full_kernel_rebuilds"] == 0
        and frozen["new_full_kernel_identity_measurement_claimed"] is False,
        "trajectory_execution.exact_reused_original_authority",
    )
    previous = frozen["parent_authority"]
    authority = p.record(
        "trajectory_execution_authority",
        execution_freeze_id=frozen["id"],
        parent_execution_freeze_id=frozen["parent_execution_freeze_id"],
        parent_execution_authority_id=previous["id"],
        parent_source_root=str(PARENT_ROOT),
        original_material_source_root=str(MATERIALS_ROOT),
        parent_commit=PARENT_COMMIT,
        original_material_gate_id=EXPECTED_GATE,
        original_kernel_id=EXPECTED_KERNEL,
        original_generation_report_id=previous["original_generation_report_id"],
        completion_freeze_id=previous["completion_freeze_id"],
        original_registry_freeze_id=frozen["study_freeze_id"],
        training_configuration_id=frozen["training_configuration"]["id"],
        parent_training_configuration_id=frozen["parent_training_configuration_id"],
        source_material_verification_id=frozen["material_verification"]["id"],
        source_material_validation_reused=True,
        original_kernel_ID_recomputed=False,
        trajectory_cache_id=frozen["trajectory_cache"]["manifest_id"],
        trajectory_cache=frozen["trajectory_cache"],
        user_directive="暂停后优化，严禁冗余校验，尽快正式训练",
        revision="trajectory_prefix_union_and_compact_cache",
        supervised_token_IDs_context_prefixes_and_weights_preserved=True,
        tasks_roles_seeds_epochs_and_global_update_counts_preserved=True,
        dropout_correlation_changed=True,
        bitwise_equivalence_claimed=False,
        fresh_Students_from_original_base_and_seed=True,
        parent_partial_Students_or_optimizers_resumed=False,
        parent_incomplete_run_claimed_complete=False,
        original_parent_reports_relabelled=False,
        new_full_kernel_rebuilds=0,
        new_corpus_copies=0,
        new_API_calls=0,
        new_tokenizer_encodings=0,
        engineering_GPU_checks_repeated=False,
        created_at=p.now(),
    )
    p.write_once(output / "preparation/trajectory_execution_authority.json", authority)
    return {"execution_freeze": frozen, "authority": authority}


def run(root):
    root = guard(root)
    output = root / OUTPUT
    authority = p.checked(
        p.read_json(output / "preparation/trajectory_execution_authority.json"),
        "trajectory_execution_authority",
    )
    frozen_path = output / "preparation/execution_freeze.json"
    frozen = p.checked(p.read_json(frozen_path), "execution_freeze")
    p.require(
        authority["execution_freeze_id"] == frozen["id"]
        and authority["original_kernel_id"] == frozen["kernel_id"] == EXPECTED_KERNEL
        and authority["original_material_gate_id"]
        == frozen["original_material_gate_id"]
        == EXPECTED_GATE
        and authority["trajectory_cache_id"] == frozen["trajectory_cache"]["manifest_id"]
        and authority["source_material_verification_id"] == frozen["material_verification"]["id"]
        and authority["parent_partial_Students_or_optimizers_resumed"] is False
        and authority["dropout_correlation_changed"] is True
        and authority["bitwise_equivalence_claimed"] is False,
        "trajectory_execution.prospective_fresh_run_authority",
    )
    return execution.run(root, frozen_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, default=root_path())
    parser.add_argument("--phase", choices=("prepare", "run"), required=True)
    parser.add_argument("--workers", type=int, default=24)
    args = parser.parse_args()
    result = (
        prepare(args.code_root, workers=args.workers)
        if args.phase == "prepare"
        else run(args.code_root)
    )
    if args.phase == "prepare":
        print(
            json.dumps(
                {
                    "execution_freeze_id": result["execution_freeze"]["id"],
                    "authority_id": result["authority"]["id"],
                    "kernel_id": result["execution_freeze"]["kernel_id"],
                    "trajectory_cache_id": result["execution_freeze"]["trajectory_cache"][
                        "manifest_id"
                    ],
                    "source_material_validation_reused": True,
                    "new_full_kernel_rebuilds": 0,
                }
            ),
            flush=True,
        )
    else:
        print(p.encode(result).decode(), flush=True)


if __name__ == "__main__":
    main()
