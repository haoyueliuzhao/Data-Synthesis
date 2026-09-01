# Finance v26.201 Fresh Terminal-to-Outcome Postrun Independent Audit

Audit date: 2026-09-02

## Scope And Decision

Finance v26.201 consumes only:

```text
fresh_artifact_backed_terminal_to_outcome_integration_repair_exact_192_job_
online_execution_postrun_independent_audit_only
```

It makes zero Provider calls and does not invoke the v26.200 execution implementation, the
v26.195 estimator, Mapper, State, frequency, Contribution, or VTDO. It independently reads the
immutable v26.200 execution files, recomputes their hashes and parent relations, reconstructs
terminal and FailureLocus values from actual Raw/Result bytes, and classifies the persisted public
response shapes and redacted telemetry.

The decision accepts v26.200 as a complete execution with intact evidence. It does not claim
Capability success: no response crossed the exact Action ABI, so no Job reached a model-owned
accepted Action, correction, Final, or Qualified endpoint. No empirical Capability estimate is
materialized within v26.201.

## Frozen v26.200 Execution

The audited execution is bound by:

- Run Start Receipt:
  `finance_v26_200_online_run_start_receipt:c0320a61e0103fcbe81a0678b4f6ad11d6e7d9f28d474da6f2b10403fa66145e`;
- execution Summary:
  `finance_v26_200_online_execution_summary:efe14591ff3551b83cbcc4e4b39e396780b13e65f92ebe8e5903d51a3bbeb4ef`;
- execution Artifact Manifest:
  `finance_v26_200_execution_artifact_manifest:e50288c4c7e2bf1b13e89e1ecef3079ab3736521450ad243a9017f216606d1a6`;
- execution Artifact Root:
  `finance_v26_200_execution_artifact_root:e95f87d91231f1ab22df15742661c535052b87f5b4fbbc84c32337e0d4b023a5`;
- online Authorization:
  `fresh_terminal_to_outcome_exact_online_execution_authorization:42aaca7f87e5766e7338c04a22d0eb49132a718e46506f4d1ca4459811cce600`;
- execution source commit/tree:
  `e3d1b8d2922e44a5edde0d63433a8f3781edecef` /
  `738c30f294cca2097baffed3a5e17e7c298fab80`.

The exact execution directory contains 1,154 files and 4,304,518 bytes. The distribution
Manifest binds 1,153 members; all 1,153 paths, SHA-256 values, and byte counts independently
match. The single excluded file is the Manifest itself.

The authorization was consumed exactly once before credential lookup. Replacement, rerun, and
recovery counts are zero.

## Evidence Reconstruction

All 192 Job records are loaded independently. For every Job, the audit:

1. reads the actual fresh Raw and Result file;
2. checks their actual bytes against the saved descriptor hashes and lengths;
3. checks Raw -> Result parentage;
4. checks the Trace Raw/Result parents;
5. checks the Outcome Raw/Result/Trace parents;
6. independently reconstructs terminal kind from the Raw public projection or typed exception;
7. independently reconstructs the exact FailureLocus and its content identity;
8. compares reconstructed values with the persisted Trace and Outcome;
9. checks Raw file creation time is no later than Result creation time.

The result is 192/192 Raw, Result, Trace, and Outcome objects; 192/192 actual Raw byte matches;
192/192 actual Result byte matches; 192/192 Raw-before-Result checks; 192/192 independent
terminal matches; and 192/192 FailureLocus matches. Each layer has 192 unique identities.
`fixture_complete` terminal rows, missing terminal projections, duplicate Jobs, exception escapes,
and post-outcome exclusions are zero.

The authoritative audit identities are:

- v26.200 Freeze:
  `finance_v26_201_v200_execution_freeze:996e8de92c73c6fe2c828c504598f875d525a0b2385131de2555895549fd6f53`;
- byte reconstruction Audit:
  `finance_v26_201_byte_reconstruction_audit:f2d6057508fbca3dc6e0939ac15817fbbab40cf9d1c687724aa0867ad24595d5`.

## Response Interface And Telemetry

The exact terminal partition is:

```text
first_response_abi_invalid       188
thinking_integrity_failure         4
total                            192
```

All 192 calls returned HTTP 200 and exact requested/selected/response model
`deepseek-v4-flash`. Thinking presence, reasoning-token telemetry, and complete Prompt,
Completion, and total Usage are each 192/192. Total Usage is 1,824,320 tokens. Private reasoning
content is not persisted.

The 188 successful public payload projections are privacy-valid, but exact four-field Action ABI
crossings are 0/188. The dominant non-ABI response shapes are 128 payloads with
`difference|higher_ref` and 39 payloads with `value`; the remaining 21 are split among nine
other incomplete or extended Action/result shapes. These counts describe the exact public
responses only. They do not prove a universal model limitation or authorize response adaptation.

The remaining four calls have `ReasoningBudgetExhaustedError`, retain HTTP 200, exact model,
Thinking, and Usage evidence, and independently reconstruct to `thinking_integrity_failure`.
Provider Transport, Privacy, Resource, Instrument, identity, and Usage-integrity terminal counts
are zero.

The response-interface Audit is
`finance_v26_201_response_interface_audit:afa82ffe7f7599a3a81dd98f6bff5836d3287ee006703415cc0f2262585d1690`.

## Interpretation Boundary

The formal Decision is
`v26_200_exact_online_execution_accepted_as_complete`, with identity
`finance_v26_201_postrun_independent_audit_decision:dbb4b76405df9b264679e987c9d75cce6d3375e0d82037323104e6b73b3587e9`.

The following is a retrospective v26.202 interpretation note and does not alter the immutable
v26.201 evidence artifacts. The v26.201 Markdown report is not a member of the eight-file formal
evidence directory; its Artifact Manifest, Artifact Root, member bytes, and identities remain
unchanged.

This means the one-shot Manifest execution and its terminal-to-persistence evidence are complete
and auditable. It does not mean the model passed the Action interface, completed a Program, or
demonstrated post-ABI Capability. This v26.201 stage did not invoke an empirical evaluator and
therefore did not materialize an estimate. Its original further inference that zero Action-ABI
crossings made the end-to-end `q_first` and `q_bounded_correction` estimands unavailable is
superseded by the external v26.202 review. Those frozen estimands use all 192 Manifest Jobs as
their denominator, so v26.202 formally materializes both as `0/192`. The post-Action-ABI
conditional semantic rate and trajectory-depth quantities remain null because their conditional
denominator is zero. No v26.200 or v26.201 evidence byte or identity changes.

The Transition identity is
`finance_v26_201_transition:8371dba68906030321e7945fb32560f185f3ad41b7b518ac49f8862247d56277`.
The final decision boundary is:

```text
no_further_experiment_authorized_without_new_audit_decision
```

Provider execution, replacement or rerun, recovery, Prompt/Grammar/model/policy changes,
empirical estimation, QA integration, Mapper, State, frequency, Contribution, VTDO, training,
release, and production are not authorized.

This historical no-further-experiment boundary was later consumed only by v26.202, under its exact
external authorization, for a zero-Provider empirical exact-set evaluation and first-response
interface localization. v26.202 does not authorize a Provider rerun or historical response
adaptation. See
`docs/finance_v26_202_exact_empirical_evaluation_and_first_response_interface_localization.md`.

The exact v26.201 audit source commit/tree are:

```text
42d071da62bfc538e555fbb4200c02627113913a
87ca269b075f629d9b36c21764536c5953a4ecb7
```

The deterministic formal directory contains eight files and 285,649 bytes. Artifact Manifest
identity is
`finance_v26_201_artifact_manifest:9c9e6d2adb452a24a07e549dc4f42aedae6305c7c0bc1d14891856bae272e73e`;
Artifact Root is
`finance_v26_201_artifact_root:c71a937d2c444ca1fbca14cc3fc1a989e83a16690c2ff6d5579cee80f57bcbe8`.
