"""One original L1 session per final adapter; no scorer, gold or reviewer import."""

import argparse
import time
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration.tokens import (
    load_bound_assets,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.inference import LocalDecoder
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.model import load_student
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.runtime import run_session

from .guards import (
    artifact_guard,
    assert_unchanged,
    guard_record,
    inference_only,
    parameter_fingerprint,
)
from .plan import GENERATION_KIND, OUTPUT, TRAINED, read_json, record, require, worker_inputs


def run(root, variant):
    require(variant in TRAINED, "diagnostic.no_B0_L1_generation")
    started = time.perf_counter()
    with artifact_guard(root, "generation", variant) as (access, network):
        config, identity, binding = worker_inputs(root, variant)
        prep = root / OUTPUT / "preparation"
        verify_source_snapshot(root, read_json(prep / "implementation.json"))
        public = read_json(prep / "public/L1.json")
        tokenizer_binding, _, tokenizer = load_bound_assets(root)
        store = DurableStore(root / OUTPUT / "generation" / variant)
        store.json("identity.json", identity)
        model, _ = load_student(
            binding,
            identity["seed"],
            trainable=False,
            adapter_path=root / identity["adapter_path"],
            adapter_record=identity["adapter_record"],
        )
        model.gradient_checkpointing_disable()
        before = parameter_fingerprint(model)
        store.json("parameters_before.json", before)
        with inference_only() as updates:
            decoder = LocalDecoder(model, tokenizer)
            result = run_session(public, store.root / "sessions/L1", decoder, identity)
        after = parameter_fingerprint(model)
        assert_unchanged(before, after)
        store.json("parameters_after.json", after)
        report = record(
            "original_L1_student_generation",
            variant=variant,
            sessions=1,
            task="L1",
            origin="local_student_generation",
            model_identity_id=identity["id"],
            configuration_id=config["id"],
            inherited_decoder_configuration_id=decoder.config["id"],
            inherited_decoder_12_task_84_session_metadata_is_not_new_denominator=True,
            tokenizer_binding_id=tokenizer_binding["id"],
            result_id=result["id"],
            initial_messages_sha256=result["initial_request_messages_sha256"],
            model_requests=result["model_requests"],
            tool_calls=result["tool_calls"],
            terminal=result["terminal"],
            parameter_sha256=before["sha256"],
            parameters_unchanged=True,
            teacher_calls=0,
            training_updates=0,
            scoring_outputs_read=False,
            original_training_targets_read=False,
            elapsed_seconds=time.perf_counter() - started,
            training_task_diagnostic_not_generalization=True,
        )
        store.json("guard_report.json", guard_record("generation", access, network, updates))
        store.json("report.json", report)
        seal_directory(store, kind=GENERATION_KIND, report_id=report["id"])
        print("generated", variant, result["terminal"], result["model_requests"], flush=True)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--variant", required=True)
    args = parser.parse_args()
    run(args.root.resolve(), args.variant)
