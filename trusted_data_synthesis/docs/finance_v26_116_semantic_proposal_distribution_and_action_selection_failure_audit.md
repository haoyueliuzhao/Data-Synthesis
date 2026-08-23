# Finance v26.116 Semantic Proposal Distribution And Action Selection Failure Audit

Audit date: 2026-08-23

## Decision

Finance v26.116 performs the credential-free follow-up required after the v26.114-v26.115
review. It does not optimize the exact response Grammar, move the fixed `stage` field, change a
model or resource bound, or execute another Job. It independently reconstructs the 54
ABI-accepted v26.114 Semantic Proposals against the exact certified public state that preceded
each call and measures where the accepted Proposal distribution lost executable actions and
trajectory progress.

The result is:

```text
81 public payloads
  -> 54 exact-ABI accepted Semantic Proposals
  -> 30 reversible Stage 2 Commits
  -> 23 successful and 7 failed public Observations
  -> 0 verification Proposals
  -> 0 final-answer Proposals
  -> 0 Program closures
  -> 0 independently valid trajectories
```

The 24 ABI-accepted Proposals without a Commit partition exactly into:

| Failure dimension | Count |
| --- | ---: |
| Direct Tool-argument grammar | 10 |
| Unresolved public Operation frontier | 7 |
| Registered operand-source grounding | 4 |
| Repeated previously failed public call | 3 |

No accepted-without-Commit row selected an unregistered Tool, a nonexistent ready Node, an
unavailable Operator, or unavailable Evidence. This is a measured Semantic Action Selection and
multi-step progression failure distribution, not a residual response-serialization diagnosis.
It is not claimed as a unique causal explanation of all model behavior.

The only permitted transition is:

```text
semantic_action_selection_protocol_design_only
```

No Provider call is authorized.

## Scope And Immutability

v26.116 reads only:

- all 2,172 files in the v26.115 transitive replay;
- all eight v26.115 output files;
- the exact v26.116 implementation;
- the already bound v26.114 Raw Executions and privacy-redacted Raw Provider artifacts reached
  through that lineage.

It changes none of the following:

- the 32 v26.114 Job identities, assignments, seeds, or terminals;
- the 81 Provider calls or their Prompt, Completion, Reasoning, Usage, and model telemetry;
- the exact v2 response Grammar or its historical 54/81 acceptance result;
- the 30 historical Commits and Observations;
- Verifier v3 Replay, mechanism, path-adherence, Program-closure, or independent-validity values;
- model, Thinking, Completion, rollout, Rescue, PublicActionState, or Stage 2 behavior.

The 27 historical fixed-`stage` failures remain immutable response-ABI failures. v26.116 does
not normalize them, treat them as Proposals, or infer their hypothetical semantics. It analyzes
only the 54 payloads already accepted by the frozen parser.

The audit looks up no credential, constructs no model client, makes zero Provider calls, makes
zero Stage 2 Provider calls, and uses zero GPU jobs. It creates zero Capability, Reachability,
State Mapping, release, training, or production rows.

## Source Replay

Before constructing a Proposal diagnostic, v26.116 replayed 2,181/2,181 files:

| Source class | Files |
| --- | ---: |
| v26.115 transitive replay | 2,172 |
| v26.115 outputs | 8 |
| exact v26.116 implementation | 1 |
| total | 2,181 |

Every path is canonical and unique and every expected SHA-256 equals the observed SHA-256. The
seven v26.115 detail outputs reproduce the hashes and byte counts bound by the v26.115 report;
the report itself reparses under its strong Schema and reproduces identity
`finance_v26_exact_grammar_postrun_audit_report:853fba47e8c1c00a3f189dc2fe6a9114167a4422e5751527f5f6a488466e0eaf`.

The v26.116 source-replay identity is
`finance_v26_semantic_distribution_source_replay:5dc8e7a1db3ae5f2ff3e94e16a609c8e8a5bd6967084cd63f44717a8f6218ccf`.

## Independent Proposal Reconstruction

For every v26.114 attempt whose frozen disposition is `usable`, v26.116:

1. reparses the bound privacy-redacted Raw Provider artifact;
2. reconstructs the exact `PublicActionState` from the frozen Task, Environment, and public
   Observation prefix at that logical request index;
3. verifies that the reconstructed state identity equals the pre-call dynamic certificate;
4. reparses the exact ten-field payload against that state;
5. independently compiles the resulting `SemanticDecisionProposal`;
6. compares a successful independent compilation to the persisted Stage 2 Commit byte-for-field;
7. detects a duplicate only when the same Tool and exact public Arguments match a prior failed
   Observation in that Job.

All 54 dynamic state reconstructions and state bindings pass. All 30 persisted Commits equal the
independent compilation. The audit retains public semantic selections and direct-argument field
names, but not direct-argument values, previous Completion content, private reasoning content, or
reasoning hashes.

The 54-row diagnostic-set identity is
`finance_v26_semantic_proposal_diagnostic_set:bcb740ea4586f344b1c0eff691f9a1bfb53bd45269f6763e3b6c29d3072d645e`.

## Proposal Distribution

### Decision Kinds

| Decision Kind | ABI accepted | Committed | Commit fraction |
| --- | ---: | ---: | ---: |
| `acquire_public_input` | 42 | 29 | 0.690476190476 |
| `execute_public_operation` | 12 | 1 | 0.083333333333 |
| `verify_terminal_operation` | 0 | 0 | undefined |
| `emit_final_answer` | 0 | 0 | undefined |

Thus the accepted-to-Commit fraction is `30/54 = 0.555555555556`. The much lower Operation
Commit fraction is the principal stage-local contrast, but this denominator is diagnostic and
was not preregistered for inferential model comparison.

Accepted Tool selections were:

| Tool | Accepted Proposals |
| --- | ---: |
| `query_structured_fact` | 40 |
| `calculator` | 9 |
| `normalize_metric_unit_period` | 3 |
| `search_archive` | 2 |

There were 42 accepted Primary and twelve accepted Rescue Proposals. Logical request positions
0/1/2/3 contributed 30/16/7/1 accepted Proposals.

### Mechanism And Path Description

Accepted Proposal counts by mechanism were 10 Context-conditioned Action, 15 Semantic
Reconciliation, 17 Failure Recovery, and twelve State-dependent Stopping. Their Commit counts
were 3, 9, 12, and 6 respectively.

Accepted Proposal counts by requested path were 21 `structured_direct`, ten
`search_then_structured`, and 23 `search_then_open`. Their Commit counts were 12, 3, and 15.
These are descriptive counts over repeated engineering sources, not role support or route-effect
estimates.

The distribution identity is
`finance_v26_semantic_proposal_distribution:5b17f3b27122863bb2fdd27f424ff25efd380cad8790a7349aa6d49af1f4277c`.

## Action Selection Failures

### Tool Argument Grammar

All ten Tool-grammar rejections are `acquire_public_input` Proposals. Each supplied an alternate
or wrapped argument object and omitted all four exact top-level fields required by the exposed
`query_structured_fact` grammar:

```text
metric_alias
period_label
public_filters
subject_alias
```

The unexpected shapes include wrappers such as `acquisition_requests` and
`evidence_role_queries`, symbol/query pairs, required-Evidence-role maps, and flattened public
record fields. Their field names are retained for diagnosis; their argument values are not.

### Public State Frontier

Seven `execute_public_operation` Proposals selected `operation_stage_01` while that registered
ready Node still had unresolved public symbols. In every row:

- the Tool was registered;
- the Node existed in the ready frontier;
- the Tool matched the Node;
- the Operator was available;
- the rejection occurred specifically because the selected Operation was not executable yet.

These are frontier-resolution failures, not nonexistent-Node or unavailable-Tool failures.

### Operand Grounding

Four `execute_public_operation` Proposals selected the correct ready Node and Tool but supplied
resolved Evidence identities in `operand_sources`. The exact semantic interface requires the
registered public source symbols, preserving their order, because Stage 2 alone maps those
symbols to public Evidence or prior Operation references. The Host did not replace the model
selection.

### Duplicate Failed Calls

Three independently compilable acquisition Proposals reproduced an earlier public Tool call that
already had a typed failed Observation. Matching the complete prior history by Tool and exact
public Arguments yields:

| Prior typed failure | Duplicate Proposals |
| --- | ---: |
| `structured_query_no_match` | 1 |
| `typed_selector_requires_refinement` | 2 |

One duplicate returned to an older failed call after two later successful acquisitions, so the
audit does not substitute the latest Observation for the same-signature historical failure.

The Action Selection failure identity is
`finance_v26_action_selection_failure:3548800b21efa7ac0bdd56dd0ca137954f937ed7f1f76e9d60c1b46b35d2d72c`.

## Trajectory Progression

Thirty of 32 Jobs produced at least one ABI-accepted Proposal. Nineteen produced at least one
Commit and fifteen produced at least one successful Observation.

| Commits per Job | Jobs |
| --- | ---: |
| 0 | 13 |
| 1 | 11 |
| 2 | 5 |
| 3 | 3 |

Eight Jobs reached two or more Commits and the maximum was three. The 30 Commits occurred at
logical positions 0/1/2 with counts 19/8/3. The 23 successful Observations occurred at those
positions with counts 13/7/3.

Of 29 committed acquisition actions, 22 succeeded. Twenty successful acquisitions reduced the
number of unresolved public symbols; the two successful `search_archive` actions did not
directly resolve one. The sole committed public Operation was a successful normalization.
No Job reached a terminal-verification or final-answer Proposal, and no Job closed its Program.

The historical terminal partition remains 21 `semantic_compile_rejection`, three
`duplicate_failed_semantic_proposal`, and eight
`semantic_proposal_not_exact_response_grammar`. No terminal is reclassified.

The trajectory-progression identity is
`finance_v26_trajectory_progression:69c93c83aab4da4c5df208cd18fd9836e403f51f66d0fd619ba5e1f7a74d7b15`.

## Interpretation

The strongest supported interpretation is:

> Exact response Grammar repair made Semantic Proposal behavior measurable. Flash produced some
> executable public actions, especially acquisition actions, but its accepted Proposal
> distribution did not reliably respect direct Tool argument grammar, the executable public
> frontier, registered operand-source symbols, or typed failed-call history, and no trajectory
> reached verification or closure.

The audit rejects response serialization, Completion budget, and deterministic Stage 2
Compilation as the primary explanation of the measured 54-to-30 loss. It does not prove that
those mechanisms are irrelevant to every possible future protocol, and it does not claim that
the four observed Action Selection dimensions uniquely cause all zero-closure outcomes.

The residual fixed-`stage` failures remain real but are outside the 54-row semantic denominator.
v26.116 therefore does not prioritize a Host-bound `stage` metadata experiment. The immutable
v26.115 transition remains a historical audit decision; v26.116 supersedes only the current
priority after independently computing the requested Semantic Proposal distribution.

## Transition Contract

The transition Contract freezes:

- no further response-Grammar optimization from these semantic rejections;
- no Completion or rollout increase;
- no Host Tool, Node, Operator, Operand, Evidence, or failed-call repair;
- no historical rerun, recovery, normalization, or reclassification;
- no Provider call until a fresh protocol and credential-free preflight are separately frozen;
- no role experiment, State Mapping, training, release, or production Contribution.

Only credential-free Semantic Action Selection protocol design is permitted. Such design must
keep semantic choices model-owned and may use the v26.116 failure distribution as diagnostic
input; it may not turn the diagnostic categories into Host-selected actions.

The transition identity is
`finance_v26_semantic_action_selection_transition:82a944e8a123794a7add9a6615a4bdc44a985d363edb846f6ce20319fb3e7159`.

## Validation

Validation completed against the canonical immutable artifact root:

- formal and independent v26.116 builds produced all eight files byte for byte;
- 54/54 dynamic state reconstructions, exact state bindings, and Proposal diagnostics passed;
- 30/30 persisted Commits matched independent Compilation;
- all 21/21 computed Gate mutations were rejected with zero Provider calls;
- 2/2 focused v26.116 tests passed;
- 103/103 v26.97-v26.116 adjacent Completion, Two-Stage, and exact-response tests passed;
- focused Ruff format and check passed;
- focused Mypy passed with zero diagnostics.

The authoritative report is
`finance_v26_semantic_proposal_audit_report:fe7abe69942f51ed79ce1eddf62878a5f68f8e9f68f85328f45b12f2db85d171`.
