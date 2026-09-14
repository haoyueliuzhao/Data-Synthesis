"""Execution-only performance revision over the already closed original kernel.

No generation, resampling, token encoding or changes to scientific conditions.
The original material gate remains the authority for the complete material ID.
"""

import argparse
import json
import subprocess
from pathlib import Path

from . import execution, training
from . import protocol as p

BRANCH = "codex/fixed-kernel-fast-execution-20260914"
PARENT_COMMIT = "1697fef5012ad823c0a930b5f8aea20188edb590"
PARENT_ROOT = Path("/tmp/data-synthesis-fixed-kernel-completion-20260914")
DATA_ROOT = Path("/data1/zhuxinrui/projects/Data-Synthesis")
MATERIALS = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/study_20260914_budget_completion"
)
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/fast_execution_20260914"
RUNTIME = "trusted_data_synthesis/runtime/fixed_kernel_fast_execution_20260914"
EXPECTED_GATE = "material_gate:16d9491e7ca7b6b506bc5308b67dc9de5b2958e94cba0d2944c5b9395f23e763"
EXPECTED_KERNEL = "fixed_kernel:f67d9edd0712d87d6d63d6e9535f8ff2db677cb81c884780afc8315c1d15c729"


def root_path():
    return Path(__file__).resolve().parents[5]


def guard(root):
    root = Path(root).resolve()
    p.require(root == root_path() and root != PARENT_ROOT, "fast_execution.isolated_source_root")
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=root, text=True
    ).strip()
    p.require(branch == BRANCH, "fast_execution.successor_branch")
    return root


def prepare(root, *, resume_existing_receipt=False):
    root = guard(root)
    material, output = root / MATERIALS, root / OUTPUT
    p.require(
        not output.exists() or resume_existing_receipt,
        "fast_execution.one_prospective_prepare",
    )
    gate = p.checked(p.read_json(material / "material_gate.json"), "material_gate")
    parent_gate = p.read_json(PARENT_ROOT / MATERIALS / "material_gate.json")
    generation = p.checked(
        p.read_json(material / "generation_report.json"), "material_generation_report"
    )
    completion = p.checked(
        p.read_json(material / "completion_freeze.json"), "kernel_completion_freeze"
    )
    original = p.checked(p.read_json(material / "freeze.json"), "study_freeze")
    p.require(
        gate == parent_gate
        and gate["id"] == EXPECTED_GATE
        and gate["kernel_id"] == EXPECTED_KERNEL
        and gate["training_gate"] == gate["material_gate"] == gate["dose_gate"] == "PASS"
        and generation["id"] == gate["generation_report_id"]
        and generation["generation_closed"] is True
        and generation["no_inflight_requests"] is True
        and generation["registered_sessions"] == generation["finished_sessions"] == 10240,
        "fast_execution.actual_original_complete_PASS_gate",
    )
    p.require(
        not (PARENT_ROOT / MATERIALS / "student_execution/execution_started.json").exists(),
        "fast_execution.no_duplicate_parent_Student_execution",
    )
    unchanged = []
    for name in (
        "consumer.py",
        "evaluation.py",
        "runtime.py",
        "transport.py",
        "semantic_mapping.py",
        "source_boundary.py",
    ):
        old, new = PARENT_ROOT / p.PACKAGE / name, root / p.PACKAGE / name
        p.require(
            p.sha(old) == p.sha(new),
            "fast_execution.unchanged_numerical_or_scientific_code:" + name,
        )
        unchanged.append({"path": p.PACKAGE + "/" + name, "sha256": p.sha(new)})
    bound = execution.prepare(
        root,
        output,
        source_root=DATA_ROOT,
        study_freeze_id=original["id"],
        population_path=material / "population.json",
        registry_path=material / "registry.json",
        materialization_index_path=material / "materialization_index.json",
        base_binding=p.read_json(material / "checkpoint_binding.json"),
        tokenizer_binding=p.read_json(material / "tokenizer_binding.json"),
        material_gate_path=material / "material_gate.json",
        resume_existing_receipt=resume_existing_receipt,
    )
    p.require(bound["kernel_id"] == EXPECTED_KERNEL, "fast_execution.actual_full_kernel_ID_parity")
    authority = p.record(
        "fast_execution_authority",
        execution_freeze_id=bound["id"],
        original_material_gate_id=gate["id"],
        original_kernel_id=EXPECTED_KERNEL,
        original_generation_report_id=generation["id"],
        completion_freeze_id=completion["id"],
        original_registry_freeze_id=original["id"],
        parent_source_root=str(PARENT_ROOT),
        parent_commit=PARENT_COMMIT,
        user_directive="减少冗余校验，尽快实验",
        execution_only_performance_revision=True,
        numerical_or_scientific_conditions_changed=False,
        actual_full_original_kernel_ID_equal=True,
        material_packages_reencoded=False,
        original_finished_slots_resampled=False,
        original_parent_reports_relabelled=False,
        changed_implementation="immutable owned token trees and reuse of content-bound material validation",
        public_record_mutable_input_copy_isolation_preserved=True,
        unchanged_code=unchanged,
        training_configuration_id=training.training_config()["id"],
        new_API_calls=0,
        new_token_encodings=0,
        engineering_GPU_checks_repeated=False,
        completed_material_validation_reused_after_environment_fix=resume_existing_receipt,
        created_at=p.now(),
    )
    p.write_once(output / "preparation/fast_execution_authority.json", authority)
    return {"execution_freeze": bound, "authority": authority}


def run(root):
    root = guard(root)
    output = root / OUTPUT
    authority = p.checked(
        p.read_json(output / "preparation/fast_execution_authority.json"),
        "fast_execution_authority",
    )
    frozen = p.checked(
        p.read_json(output / "preparation/execution_freeze.json"), "execution_freeze"
    )
    p.require(
        authority["execution_freeze_id"] == frozen["id"]
        and authority["original_kernel_id"] == frozen["kernel_id"] == EXPECTED_KERNEL,
        "fast_execution.actual_bound_release",
    )
    p.require(
        not (PARENT_ROOT / MATERIALS / "student_execution/execution_started.json").exists(),
        "fast_execution.no_parallel_parent_training",
    )
    return execution.run(root, output / "preparation/execution_freeze.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, default=root_path())
    parser.add_argument("--phase", choices=("prepare", "finish_prepare", "run"), required=True)
    args = parser.parse_args()
    result = (
        prepare(args.code_root, resume_existing_receipt=True)
        if args.phase == "finish_prepare"
        else {"prepare": prepare, "run": run}[args.phase](args.code_root)
    )
    if args.phase in {"prepare", "finish_prepare"}:
        print(
            json.dumps(
                {
                    "execution_freeze_id": result["execution_freeze"]["id"],
                    "authority_id": result["authority"]["id"],
                    "kernel_id": result["execution_freeze"]["kernel_id"],
                }
            ),
            flush=True,
        )
    else:
        print(p.encode(result).decode(), flush=True)


if __name__ == "__main__":
    main()
