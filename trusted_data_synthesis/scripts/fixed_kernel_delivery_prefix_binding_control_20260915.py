"""One six-prefix interface control using public Probe references, not a Student."""

import argparse
import importlib.util
import json
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

OUTPUT = Path("trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value")
GRADER = Path("trusted_data_synthesis/scripts/fixed_kernel_delivery_prefix_semantics_20260915.py")


def run(root):
    root = Path(root).resolve()
    target = root / OUTPUT / "delivery_r1_contrast_20260915/preflight/prefix_semantics_binding.json"
    p.require(not target.exists(), "prefix_binding_control.once_only")
    spec = importlib.util.spec_from_file_location("delivery_prefix_grader_control", root / GRADER)
    grader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(grader)
    rows = []
    for family in ("annual_flow", "stock_rollforward", "company_defined_metric"):
        for boundary in ("calculate", "final"):
            path = (
                root
                / OUTPUT
                / "delivery_diagnostic_20260915/stage_B/prefixes"
                / f"{family}_before_{boundary}.json"
            )
            raw = path.read_bytes()
            prefix = json.loads(raw)
            prediction = p.record(
                "delivery_prefix_prediction",
                prefix_record_id=prefix["id"],
                prefix_record_sha256=p.sha(p.encode(prefix)),
                boundary=prefix["boundary"],
                raw_response=prefix["reference_response"],
                model_identity_id="synthetic_public_Probe_reference_not_a_Student",
                execution_kind="synthetic_cpu_control",
                actual_model_generation_calls=0,
                actual_GPU_generation_calls=0,
                source="original_frozen_public_Probe_reference_response",
            )
            try:
                semantics = grader.grade_prefix(prefix, prediction)
                passed = (
                    semantics[
                        "semantic_calculation_success"
                        if boundary == "calculate"
                        else "semantic_immediate_final_success"
                    ]
                    is True
                )
                error = None
            except Exception as caught:
                semantics, passed = None, False
                error = {"type": type(caught).__name__, "message": str(caught)}
            rows.append(
                {
                    "prefix_path": str(path.relative_to(root)),
                    "prefix_file_sha256": p.sha(raw),
                    "prefix_record_id": prefix["id"],
                    "boundary": boundary,
                    "synthetic_prediction": prediction,
                    "semantics": semantics,
                    "interface_control_passed": passed,
                    "error": error,
                }
            )
    result = p.record(
        "delivery_prefix_semantics_binding_control",
        status="PASS_AS_SCOPED" if all(row["interface_control_passed"] for row in rows) else "FAIL",
        grader_path=str(GRADER),
        grader_sha256=p.sha(root / GRADER),
        cases=rows,
        synthetic_reference_replays=6,
        original_packages_opened=0,
        model_calls=0,
        GPU_loads=0,
        tokenizer_calls=0,
        private_or_sealed_material_opened=False,
        public_references_sent_to_Student=False,
        Student_capability_result=False,
        scope="new semantic grader interface to six already frozen public histories only",
        four_synthetic_unit_tests_rerun=False,
    )
    p.write_once(target, result)
    return {
        "status": result["status"],
        "id": result["id"],
        "passed": sum(row["interface_control_passed"] for row in rows),
        "grader_sha256": result["grader_sha256"],
        "output": str(target),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    print(json.dumps(run(parser.parse_args().root), ensure_ascii=False))
