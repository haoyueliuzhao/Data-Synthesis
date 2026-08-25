# Finance v26.151 Fresh Capability Execution Aggregation Failure

Audit date: 2026-08-26

## Decision

Finance v26.151 opened only the exact fresh 96-Job Capability Manifest authorized by v26.150.
The run completed all 96 Raw Executions and all 96 checkpoint measurement rows. It then failed
after the denominator was complete, before writing the aggregate result and report, because the
execution implementation attempted to pass a tuple of Pydantic models directly to json.dumps.

The failed execution directory is immutable evidence:

~~~text
artifacts/vtdo_experiment/
finance_v26_151_fresh_capability_execution_v2_20260825
~~~

No Job may be rerun. The only permitted repair is a credential-free, Raw-only aggregate recovery
under a fresh output and report identity. Reachability materialization or execution and State
Mapping remain forbidden.

## Exact Pre-call Closure

Immediately before the online denominator, the Runner independently completed:

- 7,364/7,364 source-file replays;
- 20/20 byte-identical v26.150 output reconstructions;
- exact v26.150 Manifest, Runner, Outcome, resource, Support, Final Grammar, and joint Verifier
  bindings;
- 96 distinct Jobs and seeds over twelve fresh Tasks;
- zero Raw recovery Jobs and zero orphan Provider artifacts;
- zero Provider calls before the online start line.

The exact start was:

~~~text
resuming 0/96; raw-only recovery 0; executing 96 Jobs with 8 workers
~~~

The source replay identity is:

~~~text
finance_v26_fresh_capability_execution_source_replay:
70b86aa5814b6e3a167c9f21005d7f83564c8e1e3adbb69ea2c67607ea6ca7b2
~~~

## Complete Raw Denominator

All 96 Jobs completed before the aggregation exception. The persisted denominator contains:

~~~text
checkpoint measurement rows       96
Fresh Capability Raw Executions   96
Provider Envelope pairs          879
Transport invocation rows        879
Stage 2 Provider calls             0
~~~

Every checkpoint row records:

~~~text
measurement_support_available = true
model_endpoint_observed        = true
instrument_integrity           = true
privacy_compliant              = true
measurement_gate_failure_ids   = []
~~~

The endpoint partition is 58 completed_model_endpoint and 38 model_result_failure. There are zero
measurement-support exits, Instrument failures, privacy failures, exact-model/Thinking/Usage
failures, typed budget no-calls, unresolved Transport failures, and worker failures.

Artifact-backed Provider Usage is:

~~~text
Prompt tokens       4,306,207
Completion tokens   3,708,191
Reasoning tokens    3,570,653
Total tokens        8,014,398
estimated cost USD  1.37431394800000011533
~~~

Private reasoning content and hashes, Raw HTTP bodies, Raw request bodies, Host answer insertion,
Host Citation insertion, and Stage 2 Provider calls remain zero.

The complete checkpoint has SHA-256:

~~~text
fb50e711536016e4993408c3a4ed18a87c811f76e23d7cacc8cda8a7068601cb
~~~

The exact failed implementation has SHA-256:

~~~text
66a27c0d22c3e4b6f01210f3ec4757a350137eb87a64ca3506f75a4a699f7409
~~~

A copy is retained as failed_aggregation_implementation.py inside the failed directory.

## Failure Localization

The exception occurred only after the 96th checkpoint row and Raw Execution were atomically
persisted. The failing operation was:

~~~text
_write_json_atomic(
    output_dir / "fresh_capability_measurement_results.json",
    results,
)
~~~

The serializer handled a top-level BaseModel, but did not recursively project a tuple of
CapabilityMeasurementResult objects. Python therefore raised:

~~~text
TypeError:
Object of type CapabilityMeasurementResult is not JSON serializable
when serializing tuple item 0
~~~

The failure did not involve Provider behavior, model output parsing, privacy classification,
Measurement Support, task verification, resource accounting, or any individual Job result. No
aggregate report exists in the failed directory.

The checkpoint-only counts are descriptively 31 Base-valid, 74 Mechanism-qualified, and 31
Qualified-valid rows. They are not yet an authorized Capability estimand because the formal
noncompensatory Measurement Gate, task-first summaries, and report were not persisted.

## Authorized Recovery

The only permitted transition is:

~~~text
fresh_capability_complete_raw_aggregation_recovery_only
~~~

The recovery must:

1. retain this failed directory byte-immutably;
2. change only generic aggregate serialization and the fresh recovery output/report identity;
3. copy and independently hash-check the exact 96 Raw Executions, 96 checkpoint rows, and all 879
   Envelope/Projection/Transport triples;
4. replay the complete v26.150 pre-call chain before loading the copied Raw;
5. construct no real model client and make zero Provider calls;
6. recompute every Job measurement row from Raw and require byte identity with the checkpoint;
7. apply the unchanged eight-part noncompensatory Measurement Gate;
8. write task-first Base, Mechanism, and Qualified summaries;
9. preserve zero Reachability and State Mapping rows;
10. authorize only an independent post-run audit.

Any Raw mismatch, missing descriptor, orphan, checkpoint mismatch, source-binding mismatch, or
attempt to construct a client must fail closed. The model results may not be rerun, repaired,
pooled with historical Capability rows, or used to tune any threshold.
