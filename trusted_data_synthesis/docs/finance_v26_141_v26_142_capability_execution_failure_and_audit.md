# Finance v26.141-v26.142 Capability Replacement Execution Failure And Audit

Date: 2026-08-24

## Decision

Finance v26.141 performed the operator-authorized replacement run of the exact fresh 96-Job
Capability Manifest frozen by v26.140. The first process had lost its temporary worktree and
execution directory, so the replacement explicitly records
`pristine_first_exposure_claimed=false`. The unavailable process contributes zero auditable Jobs,
zero pooled rows, and no reconstructed Usage or terminal.

The replacement failed closed after all 96 submitted Futures were drained. Ninety-three Jobs
persisted complete Raw Executions and checkpoint rows. Three Jobs persisted exactly one valid
Provider Envelope, public Projection, and Transport certificate but no Raw Execution. No completed
v26.141 report exists, none of the three Jobs was retried, and the exact Capability denominator is
incomplete.

Finance v26.142 independently audits that failed lineage with zero credential lookup, zero model
client construction, zero Provider calls, zero Stage 2 Provider calls, and zero GPU jobs. It
reproduces the three orphan failure paths and freezes the only permitted successor as a fresh,
credential-free orphan support-exit recovery preflight.

## Frozen Execution

The replacement retained the exact v26.140 Capability chain:

- twelve frozen Capability tasks and eight unconditional replicas per task;
- all twelve Mechanism x Tier cells and 96 preserved seeds;
- exact `deepseek-v4-flash`, `thinking.type=enabled`, and the frozen 16K profile;
- `prospective_role_scalable_semantic_action_prompt.v2`;
- the exact four-field Action Grammar and two-field Final Grammar;
- the unchanged privacy classifier and privacy-first Envelope/Projection persistence;
- complete Candidate authority and presentation;
- independent ABI, Semantic, Transport, and Ordinary Detour allowances;
- 60,000 Prompt bytes, 21 Primary requests, 23 Stage 1 calls, 24 transport-inclusive
  invocations, and 1,120,000 reported tokens per Job;
- deterministic zero-Provider Stage 2.

The exact Manifest is
`finance_v26_privacy_safe_capability_manifest:971a74faf28d07402aa90a31ec202644f617410e4a49ec7f25e5a265458b1301`.
The exact Runner is
`finance_v26_privacy_safe_capability_runner_contract:e080bd0622b653e73b67a834aefe8b10f54ecf06e95334d574038c21d88ca35d`,
and the exact outcome Contract is
`finance_v26_privacy_safe_capability_outcome_contract:a9cfe6d9fe21c26652fb01b75655aa119f50a992d40a93620db5832512d86162`.

The online implementation was committed at `fb65a8d` before credential lookup. The failed durable
execution directory and its 2,680 files were frozen at `197969e` before v26.142 audit development.

## Failed Lineage

The durable v26.141 directory contains:

```text
exact Manifest Jobs                              96
complete Raw Executions                          93
checkpoint results                               93
Provider Envelopes                              858
public Projections                              858
Transport certificates                          858
calls bound by complete Raw                     855
calls bound only by orphan prefixes               3
completed report                                  0
```

All 858 artifact triples validate. Every call was HTTP success, requested, selected, and returned
exact `deepseek-v4-flash`, and retained complete positive Thinking and Usage telemetry. The
Projection partition is 851 validated public payloads, seven generic Provider-failure no-payload
rows, and zero privacy rejections. Private reasoning content or hashes, invalid payload content or
keys, Raw HTTP bodies, and Raw request bodies were not persisted.

Artifact-backed Usage is 8,042,572 tokens: 4,211,294 Prompt, 3,831,278 Completion, and 3,699,772
Reasoning tokens. The exact Reasoning/Completion fraction is
`0.9656756831532454705714385644`. Estimated cost telemetry is USD
`1.28198986720000011600`. The maximum Prompt among complete Raw Jobs is 49,504 bytes, and the
maximum complete-Raw Job Usage is 223,783 tokens.

## Descriptive Complete-Raw Subset

The 93 complete Raw rows independently reproject to seventeen `model_valid_trajectory` and 76
`model_invalid_trajectory` terminals. Ninety-two cross the first Action interface. At least one
independently valid complete trajectory appears in each of the four mechanisms. The Ordinary
Detour partition is 92 zero and one single-Detour Job.

These are immutable descriptive values over a nonrandom incomplete subset. They are not an exact
task-weighted Capability estimate, support no exact-denominator interval, and cannot satisfy the
frozen all-96-Raw Gate. Missing rows are not imputed, the three orphan rows are not classified as
model-invalid, and the unavailable first process remains unpooled.

## Orphan Root Cause

The three orphan Jobs are all Failure Recovery rows: Easy replicas two and four, and Hard replica
zero. Each persisted first call is a privacy-compliant exact four-field Action payload. v26.142
independently reconstructs, for all three rows:

1. the exact initial public State and salted Candidate presentation;
2. exact Action parsing, visible Candidate binding, and Decision-kind binding;
3. the same reversible `query_structured_fact` Commit;
4. a failed public Observation with error code `typed_selector_requires_refinement`;
5. the exact successor State, Progress event, Choice record, and v2 Prompt;
6. exact successor State and Candidate-order decoding with zero classifier-sensitive Keys;
7. zero later Provider invocations.

All three then reproduce the same Host-only diagnostic failure:

```text
prompt_only_reference_proposal
ValueError: Prompt-only acquisition policy cannot satisfy its public route
```

The failed function constructs the public ordinary-replan reference used only to classify an
Ordinary Detour. It is not a model-facing policy and may not choose, replace, or repair the model
Action. The strongest supported root cause is
`dynamic_successor_reference_policy_unavailable_not_typed_as_measurement_support_exit`.

This is an Instrument defect after a persisted model result, not an Action ABI failure, Candidate
error, Tool runtime error, privacy failure, or model terminal. v26.142 does not create historical
Raw Executions, assign historical terminals, or reclassify any orphan.

## Independent Audit

The v26.142 source replay verifies 7,234/7,234 files before loading role inputs: all 4,553 bound
v26.141 source files, all 2,680 failed execution files, and the exact audit implementation. It
independently reprojects 93/93 Raw rows, matches 93/93 checkpoints, validates all 858 artifact
triples, and reproduces the root cause for 3/3 orphans. Twelve destructive mutations fail closed,
including orphan deletion, Raw inference, model-invalid relabeling, reference-policy repair,
historical identity reuse, early Provider authorization, prior-attempt pooling, private-reasoning
hashing, and promotion of the partial subset to an exact Capability estimate.

Focused Ruff, Mypy, and Python compilation pass. Focused Pytest passes 2/2 in 349.18 seconds and
independently rebuilds all seven formal v26.142 files byte for byte.

The authoritative v26.142 identities are:

- report:
  `finance_v26_capability_failed_lineage_audit_report:93972cc33691eec1ab18a767ab2193a9eee490ed22c92e2c07c8eece858bdee2`;
- source replay:
  `finance_v26_capability_failed_lineage_source_replay:3a9edf9608a4de0550292427b836bea2e025187d8ae822b3efd873de1f11e751`;
- failed lineage:
  `finance_v26_capability_failed_lineage:b7b2b671fed238a52cd71c9473e3d1d3761b78b0ac6804577d2b34fbe88b1757`;
- partial outcome:
  `finance_v26_partial_capability_outcome:835e2970cda069f3303791f15e18c1a936a23ed069eeb02202b7873c7c2f6e7e`;
- orphan root cause:
  `finance_v26_orphan_reference_root_cause:41194a48e2f79183b5e1970fcac38b1915e57c25d0d5fb1ade1fb734a79dd5e1`;
- destructive audit:
  `finance_v26_capability_failed_lineage_destructive:2345dfa32827106819e7ffbd33be0ed90be679879484430f9ffd56162d5b2234`;
- transition:
  `finance_v26_capability_failed_lineage_transition:a242c1f561f6464801b1cb105158a991e4c252962bb524028c408d6467e1d9a3`.

## Permitted Transition

The only permitted transition is:

```text
fresh_orphan_reference_unavailable_support_exit_recovery_preflight_only
```

The successor may create exactly three fresh RecoveryJob identities bound to each exact persisted
orphan prefix and independently reconstructed Action, Commit, Observation, and successor Prompt.
It may only convert the reproduced reference-policy unavailability into a typed measurement-
support exit before any later Provider invocation. A complete credential-free Runner preflight is
required.

Provider calls, Capability continuation, historical Job rerun, historical Raw or terminal
creation, model-action replacement or repair, S1/Candidate/Prompt/Grammar/classifier/model/
Thinking/resource changes, Reachability identity or execution, State Mapping, training, release,
and production Contribution remain forbidden.
