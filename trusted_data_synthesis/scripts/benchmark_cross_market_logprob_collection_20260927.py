"""Bounded synthetic CUDA benchmark; never loads a student or calls an API."""

import argparse
import hashlib
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import torch

import cross_market_logprob_collection_20260927 as collection


def original(output, scores):
    return [
        float(torch.log_softmax(score[0].float(), -1)[token])
        for token, score in zip(output, scores, strict=True)
    ]


def run():
    if not torch.cuda.is_available():
        raise RuntimeError("Synthetic equivalence benchmark requires CUDA")
    cases = []
    torch.manual_seed(20260927)
    torch.cuda.manual_seed_all(20260927)
    for dtype in (torch.float32, torch.bfloat16):
        for count in (32, 128):
            vocabulary = 151936
            scores = tuple(torch.randn(1, vocabulary, device="cuda", dtype=dtype) for _ in range(count))
            output = [(index * 7919 + 13) % vocabulary for index in range(count)]
            cpu_state = torch.get_rng_state().clone()
            device_state = torch.cuda.get_rng_state().clone()
            expected = original(output, scores)
            actual = collection.collected_logprobs(output, scores)
            # All outputs are finite FP32 values exactly representable as Python floats.
            exact = expected == actual
            rng_unchanged = torch.equal(cpu_state, torch.get_rng_state()) and torch.equal(
                device_state, torch.cuda.get_rng_state()
            )
            times = {"original": [], "collected": []}
            functions = {"original": original, "collected": collection.collected_logprobs}
            # Alternate the order because the device is shared with real workers.
            for repeat in range(7):
                order = ("original", "collected") if repeat % 2 == 0 else ("collected", "original")
                for name in order:
                    torch.cuda.synchronize()
                    before = time.perf_counter()
                    value = functions[name](output, scores)
                    torch.cuda.synchronize()
                    times[name].append((time.perf_counter() - before) * 1000)
                    exact = exact and value == expected
            rng_unchanged = rng_unchanged and torch.equal(cpu_state, torch.get_rng_state()) and torch.equal(
                device_state, torch.cuda.get_rng_state()
            )
            cases.append(dict(
                dtype=str(dtype), rows=count, vocabulary=vocabulary,
                bit_exact=exact, rng_unchanged=rng_unchanged,
                original_ms_median=statistics.median(times["original"]),
                collected_ms_median=statistics.median(times["collected"]),
                samples_ms=times,
            ))
            del scores
            torch.cuda.empty_cache()
    exact = all(case["bit_exact"] for case in cases)
    rng_unchanged = all(case["rng_unchanged"] for case in cases)
    return dict(
        kind="cross_market_logprob_collection_synthetic_cuda_benchmark",
        at=datetime.now(timezone.utc).isoformat(),
        test=dict(passed=exact and rng_unchanged, bit_exact=exact, rng_unchanged=rng_unchanged),
        helper_sha256=hashlib.sha256(Path(collection.__file__).read_bytes()).hexdigest(),
        anchor_decoder_sha256=collection.SOURCE_SHA256,
        benchmark_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        device=torch.cuda.get_device_name(), torch_version=torch.__version__,
        max_memory_allocated_MiB=torch.cuda.max_memory_allocated() / 2**20,
        max_memory_reserved_MiB=torch.cuda.max_memory_reserved() / 2**20,
        model_calls=0, api_calls=0, cases=cases,
        limitations=["Synthetic scores, not student inference", "Shared GPU; timings can be noisy"],
        full_generation_equivalence_claimed=False,
        end_to_end_speedup_claimed=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = run()
    # Use the experiment's durable artifact writer, not an ad-hoc replacement.
    import fixed_kernel_cross_market_evaluation_20260926 as evaluation
    evaluation.Context(args.output.parent).write(args.output, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["test"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
