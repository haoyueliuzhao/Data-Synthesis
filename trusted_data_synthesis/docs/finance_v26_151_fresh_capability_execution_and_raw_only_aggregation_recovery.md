# Finance v26.151 Fresh Capability Execution And Raw-Only Aggregation Recovery

Audit date: 2026-08-26

## Decision

Finance v26.151 consumed only the exact authoritative 96-Job fresh Capability execution
transition frozen by v26.150. The online process completed the full model-result denominator but
failed after the ninety-sixth checkpoint because its aggregate JSON helper did not recursively
project Pydantic models nested inside a tuple. The failed v2 directory and source remain immutable.
No Job was rerun.

A fresh v3 recovery replayed the complete predecessor chain without a credential, reconstructed
all 96 measurement rows from the persisted Raw Executions, required exact canonical equality with
the frozen checkpoint, and aggregated the denominator with zero Provider calls. The unchanged
noncompensatory Measurement Gate passes. Capability estimates are therefore authorized pending
one independent postrun audit; no Reachability identity or State Mapping row is authorized yet.

The authoritative recovery directory is:

~~~text
artifacts/vtdo_experiment/
finance_v26_151_fresh_capability_raw_recovery_v3_20260826
~~~

## Frozen Execution Lineage

Before the original online execution, v26.151 replayed 7,364/7,364 files and independently rebuilt
all twenty v26.150 outputs byte for byte. The exact 96 Jobs cover twelve fresh model-unexposed
Tasks, one in each Mechanism x Tier cell, with eight unconditional replicas per Task and 96
preserved distinct seeds. Historical Job and seed overlap are zero. The exact v26.150 Manifest,
Outcome Contract, Runner Contract, Support Contract, Verifier vNext Contract, qualified Final
Grammar, resources, and source-selection binding remained unchanged.

The original process started at 0/96 with eight workers. All 96 Jobs completed before aggregation.
The immutable failed denominator contains:

~~~text
checkpoint measurement rows        96
Fresh Capability Raw Executions    96
Provider Envelopes                 879
Public Payload Projections         879
Transport invocation certificates 879
Stage 2 Provider calls               0
~~~

The terminal partition is 58 `completed_model_endpoint` and 38 `model_result_failure`. The latter
contains 37 `response_not_exact_qualified_grammar` outcomes and one
`length_truncated_content` outcome. These remain model results; none is repaired or removed.

## Raw-Only Recovery

The recovery changes the generic aggregate serializer so that BaseModel, Mapping, list, and tuple
containers are recursively converted to canonical JSON data. It does not change a Task, Prompt,
Candidate, Grammar, classifier, model profile, Completion bound, resource bound, recovery channel,
Verifier check, mechanism check, or empirical row.

The v3 entry point requires the complete 96-row checkpoint before any possible client construction.
A partial checkpoint, missing Raw, changed Raw descriptor, or report with pending Jobs fails closed.
For every frozen Job it then:

1. loads the persisted Raw Execution;
2. independently reruns the public Measurement Support, endpoint, Runtime replay,
   noninterference, answer semantics, Base validity, mechanism, and qualified-validity projection;
3. compares the recomputed result with the checkpoint result in canonical bytes;
4. refuses aggregation on any difference.

All 96/96 recomputations match. The recovery also compares the checkpoint plus all Raw,
Envelope, Projection, and invocation files between the failed and recovered directories. All
2,734/2,734 files are byte-identical. The old and recovered checkpoint SHA-256 is:

~~~text
fb50e711536016e4993408c3a4ed18a87c811f76e23d7cacc8cda8a7068601cb
~~~

Credential lookup, real client construction, model-result reruns, recovery Provider calls, and
Stage 2 Provider calls are all zero.

## Measurement Gate

The pre-registered Gate is noncompensatory. Every condition must pass independently:

~~~text
complete Raw Executions                       96/96
observed model endpoints                      96/96
Measurement Support exits                         0
Instrument failures                               0
Privacy failures                                  0
exact-model / Thinking / Usage failures           0
typed budget no-calls                              0
unresolved Transport failures                      0
~~~

The Gate therefore passes and authorizes Capability estimation. Outcome quality does not
compensate for this Gate, and the Gate does not imply outcome validity.

## Capability Results

The exact trajectory funnel is:

~~~text
model endpoints observed                    96
Programs closed                             73
terminal verification complete              61
exact qualified Final payloads              58
Base-valid trajectories                     31
Mechanism-qualified trajectories            74
Qualified-valid trajectories                31
~~~

`Qualified = Base and Mechanism` is applied per trajectory. Base and Mechanism remain separately
reported. The 31 Qualified rows are not inferred from terminal labels, and the 38 model-result
failures remain in the exact denominator.

The task-primary aggregate is:

~~~text
Base-valid task-weighted fraction       0.3229166666666666666666666667
Mechanism task-weighted fraction        0.7708333333333333333333333333
Qualified task-weighted fraction        0.3229166666666666666666666667
~~~

Every Task has exactly eight replicas, so these task-weighted values numerically equal 31/96,
74/96, and 31/96. The estimand still treats the twelve Tasks as primary sampling units and the
eight replicas as secondary repeated measures.

The mechanism-level partition is:

~~~text
Mechanism                      Base  Mechanism  Qualified  Tasks with Qualified
Context-conditioned Action      4/24    19/24      4/24            1/3
Failure Recovery                8/24    22/24      8/24            3/3
Semantic Reconciliation         8/24    17/24      8/24            3/3
State-dependent Stopping       11/24    16/24     11/24            3/3
~~~

All four mechanisms have at least one independent Task with a Qualified trajectory. The frozen
minimum-support condition for a later Reachability preflight therefore passes. This is not a
Reachability result and does not authorize Reachability execution.

Base-check failures are non-exclusive. The largest public partitions are 52 answer semantic
mismatches, 49 incomplete Operation lineage bindings, 48 reference-identity mismatches, 38
missing exact Final/answer-schema/model-citation completions, 36 incomplete verification support,
35 incomplete terminal verification, and 23 unclosed Programs. Mechanism-event failures are also
non-exclusive and remain separate from Base failures. These values localize observed behavior;
they do not select a repair or modify a threshold.

## Usage And Privacy

Artifact-backed Provider telemetry is:

~~~text
Provider calls                    879
transport-inclusive invocations   879
Prompt tokens                4,306,207
Completion tokens            3,708,191
Reasoning tokens             3,570,653
Total tokens                 8,014,398
estimated cost USD  1.37431394800000011533
~~~

All calls preserve exact-model, Thinking, Usage, request, resource, Envelope/Projection, and
transport bindings required by the Gate. Private reasoning payloads or hashes, invalid public
payload persistence, Raw HTTP bodies, Raw request bodies, Host answer or Citation insertion, and
Stage 2 Provider calls are zero.

## Identity And Verification

The authoritative identities are:

- execution report:
  `finance_v26_fresh_capability_execution_report:a50a33b3bbb9393930e0135e6fa208a5cecaeed2828ee64aaa4957cefdbdb821`;
- source replay:
  `finance_v26_fresh_capability_execution_source_replay:b60516aee8e226e45dacab6c54220d8b2f35618792a63ce547f19103d27b4e6d`;
- preexecution binding:
  `finance_v26_fresh_capability_preexecution_binding:03e77d878a38a6997081e3cdd623e73d17c0b616ad6c90f1c69dc1c809c0040e`;
- Raw Lineage:
  `finance_v26_fresh_capability_raw_lineage:9fb1a136839fb9e8894f94199b4f9f6e08771f7e932abaa6c1af1de35b9934a2`;
- Measurement Gate:
  `finance_v26_fresh_capability_measurement_gate:e7935ebf5078062553a961d55217e44c3194537ea155674c8beb121da7906e12`;
- aggregation recovery:
  `finance_v26_fresh_capability_aggregation_recovery:8aaa7e21b51d2faf5b86e4309649fcab5ade3c11d9afc9693592d7934360433d`.

The report SHA-256 is
`05baabf3ef73fcd4677f472b8070f1b9f95b28b114a97ff948e54268c4408cfc`.
The exact recovery implementation SHA-256 is
`adee838e3cac58e7cf165103e619b0a81c5dabe1086d25721b2f28449df348aa`.
Focused Ruff and Mypy pass. Focused Pytest passes 3/3, including formal object validation,
recursive aggregate serialization, old/new denominator byte comparison, and a destructive
noncompensatory-Gate control.

## Permitted Transition

The only permitted transition is:

~~~text
fresh_capability_postrun_audit_only
~~~

The successor must independently replay the complete v26.151 lineage, parse every Raw Execution
and every Provider artifact triple, reconstruct all 96 public measurement projections without
calling the v26.151 aggregate helpers as an oracle, reproduce all task-first and mechanism-first
summaries, and confirm the Measurement Gate and minimum mechanism support. It may make zero
Provider calls and create zero Reachability or State Mapping identities.

Only a passing independent audit may authorize a separate fresh Reachability identity-chain and
credential-free Runner preflight. Reachability execution, State Mapping, task or threshold
changes, historical pooling or reclassification, Host repair, training, release, and production
Contribution remain forbidden.
