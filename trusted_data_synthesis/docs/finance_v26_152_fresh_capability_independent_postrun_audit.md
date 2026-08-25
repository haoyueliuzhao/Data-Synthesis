# Finance v26.152 Fresh Capability Independent Postrun Audit

Audit date: 2026-08-26

## Decision

Finance v26.152 consumed only the credential-free independent postrun audit authorized by
v26.151. It replayed the complete source and execution lineage before loading any Capability
result, independently parsed all Raw and Provider artifacts, and reconstructed all 96 public
measurement projections from the shared frozen contracts without calling the v26.151 per-row
projector, Measurement Gate, or summary helpers as result oracles.

Every reconstructed projection, joint Verifier result, online Prompt audit, task summary,
mechanism summary, and report aggregate matches the immutable v26.151 evidence. The independent
noncompensatory Measurement Gate passes. The exact task-primary Capability estimates and the
four-mechanism minimum-support result are confirmed.

This audit authorizes only a fresh Reachability identity chain and credential-free Runner
preflight over the already frozen model-unexposed Reachability Source Population. It does not
materialize a Reachability identity, call a Provider, execute Reachability, or map a state.

## Source And Artifact Replay

Before result loading, v26.152 replayed:

~~~text
v26.151 transitive source files      7,364
v26.151 execution files              2,760
v26.152 implementation                   1
total                               10,125
exact matches                       10,125
~~~

The execution-file set includes the v26.151 frozen inputs, complete checkpoint and aggregate,
96 Raw Executions, 879 Provider Envelopes, 879 public Projections, 879 Transport invocation
certificates, recovery audit, Gate, summaries, Raw Lineage, and report. Credential lookup, real
client construction, Provider calls, Stage 2 Provider calls, and GPU jobs are zero.

The independent artifact audit validates:

~~~text
Raw Executions                                  96
checkpoint rows                                 96
aggregate rows                                  96
Provider Envelope / Projection pairs           879
Transport invocation certificates              879
validated descriptor bytes                    2,733
checkpoint-to-aggregate exact row matches        96
Raw-to-checkpoint parent matches                  96
~~~

All 879 Envelope/Projection pairs cross the frozen privacy-first pair validator. Every Transport
certificate parses under its exact schema and binds the same Job as its Raw parent. The complete
formal descriptor set equals the independently reconstructed descriptor set.

## Independent Scientific Projection

For each of the 96 Jobs, v26.152 independently rebuilds:

1. the terminal model-endpoint classification;
2. the typed Measurement Support decision;
3. exact-model, fallback, native-tool, Thinking, Usage, request, resource, transport, and privacy
   integrity;
4. every reached Action and Final Prompt hash, byte count, presentation salt, and Final Host
   Envelope;
5. authority-preserving Runtime replay;
6. Decimal-aware answer semantics and reference identity;
7. all fourteen Base-validity checks;
8. mechanism events for Context-conditioned Action, Semantic Reconciliation, Failure Recovery,
   and State-dependent Stopping;
9. the joint Base, Mechanism, Qualified, endpoint, and State-Mapping-eligibility reports.

The exact comparison result is:

~~~text
checkpoint projection matches       96/96
aggregate projection matches        96/96
joint-result identity matches       96/96
online Prompt-audit matches         96/96
Qualified = Base and Mechanism      96/96
~~~

The audit explicitly records that it did not invoke the v26.151 projector, Gate, or summary
helpers. It does reuse the shared frozen Measurement Support, answer-semantics, Runtime replay,
mechanism, and joint-validity core APIs, which are the contracts under independent audit rather
than v26.151 aggregate outputs.

The independently counted Base-check passes are:

~~~text
action ABI complete                      95
Program closed                           73
Operation lineage complete               47
required Evidence support complete       81
Runtime-selected support complete        81
model Citation support complete          58
terminal verification complete           61
Final ABI complete                        58
answer Schema complete                    58
answer canonical semantic match           44
reference identity match                  48
verification support complete             60
no post-completion violation              96
noninterference Artifact bound            96
~~~

These checks are conjunctive within Base validity, so their marginal pass counts are not an
alternative validity score.

## Independent Measurement Gate

The independently reconstructed Gate exactly matches the formal v26.151 Gate:

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

The Gate passes noncompensatorily. No outcome-quality value is used to repair a Gate component.
There are zero support or integrity rows with an inferred non-null validity value.

## Capability Reconstruction

The independently reconstructed terminal and validity funnel is:

~~~text
completed model endpoints                   58
model-result failures                       38
Programs closed                             73
terminal verification complete              61
exact qualified Final payloads              58
Base-valid                                  31
Mechanism-qualified                         74
Qualified-valid                             31
State-Mapping eligible under frozen rule    31
~~~

The 38 model-result failures remain 37 `response_not_exact_qualified_grammar` and one
`length_truncated_content`. They remain part of the exact denominator.

All twelve task summaries and all four mechanism summaries match their v26.151 canonical bytes.
The confirmed task-primary fractions are:

~~~text
Base       0.3229166666666666666666666667
Mechanism  0.7708333333333333333333333333
Qualified  0.3229166666666666666666666667
~~~

The mechanism Qualified partition remains Context-conditioned Action 4/24, Failure Recovery
8/24, Semantic Reconciliation 8/24, and State-dependent Stopping 11/24. All four mechanisms have
at least one independent Task with a Qualified trajectory. This passes the frozen minimum-support
condition but establishes only nonzero support in this Development Population. It does not
establish a stable mechanism-population success rate.

Eighteen top-level report aggregates independently match, including terminal counts, all three
validity counts and task-weighted fractions, minimum mechanism support, 879 Provider calls,
879 Transport invocations, 4,306,207 Prompt tokens, 3,708,191 Completion tokens, 3,570,653
Reasoning tokens, 8,014,398 total tokens, and USD `1.37431394800000011533` estimated cost.
Historical Capability rows are not pooled.

## Governance Controls

Twenty-four destructive controls fail closed. They cover Capability rerun or pooling, outcome-
conditioned task or Reachability selection, Support/Instrument/Privacy/mechanism reclassification,
missing endpoint inference, use of v26.151 projection or aggregation helpers as oracles, private
reasoning persistence, Provider-client construction, immediate Reachability execution, and every
premature State Mapping path.

The successor is bound to the already frozen, model-unexposed Reachability Source Population:

~~~text
finance_v26_fresh_role_source_population:
cf4ff4407c4ca727c9b9c140e87261d3358c4974d92ea8605ce66bae2d316d99
~~~

This prevents selecting Reachability sources after observing the Capability results. Future State
Mapping for the current mechanism-conditioned role requires `V_qualified is True`; a Compiler
static Path remains a target condition and cannot substitute for an empirical model state.

## Identity And Verification

The authoritative identities are:

- report:
  `finance_v26_fresh_capability_postrun_audit_report:933a824cf81fda37f2a965a8b61640b4bc772058f04b25cd9f6033a9bb965a17`;
- source replay:
  `finance_v26_fresh_capability_postrun_source_replay:18ee52cef4999139882ce6b252a41661a3fb01010c742bb446fe0b54edd4ca00`;
- Provider artifact audit:
  `finance_v26_fresh_capability_independent_provider_artifacts:6e83b0ecdac29228685244123826332cebfd7bf2880372b71c66989b26849f63`;
- independent projection:
  `finance_v26_fresh_capability_independent_projection:4f53840e68af4f9dfbbdc9e27d5199cb2aa1beeff3b155d86255835418e76b0b`;
- independent Measurement Gate:
  `finance_v26_fresh_capability_independent_measurement_gate:9bd9cb10a2f52121e55be41f3c044935643a3201c88eed189c501032df180ad3`;
- independent Estimand:
  `finance_v26_fresh_capability_independent_estimand:a8f269bb9b1d05ea7d4ff67a1a357046686c5bd6d8485033afa999a4c0c899ec`;
- validity decomposition:
  `finance_v26_fresh_capability_validity_decomposition:9d6a9b5a6d5f88f68527f766aa7009552bddee7f476b1d35049f1d6089ecbf9a`;
- destructive audit:
  `finance_v26_fresh_capability_postrun_destructive:b71c723df3a620c720ab32b91d63405ff664e3b91dc42855014551c823187877`;
- transition:
  `finance_v26_fresh_capability_postrun_transition:303b783806e77e47c9ddd84aa5fb00c879abecd8b08e17c04e0e9b2981bb89d3`.

The report SHA-256 is
`821b65586bdb8f850724a34280f4cf6f5ff0d31d663afe33d82ac2d7bf8e1f45`.
The implementation SHA-256 is
`77e0055e0fff12359ef7e15f1fddb4b84d6e326985890c0741c0990297fb909b`.
Focused Ruff and Mypy pass. Focused Pytest passes 4/4 in 130.37 seconds, including a complete
independent rebuild with 9/9 output files byte-identical. The adjacent v26.151-v26.152
regression passes 7/7 in 130.68 seconds. Package-wide Mypy checks 477 source files and retains
only the three pre-existing v26.70/v26.129 diagnostics, with zero v26.152 diagnostics.

## Permitted Transition

The only permitted transition is:

~~~text
fresh_reachability_identity_chain_and_runner_preflight_only
~~~

The successor may bind only the exact frozen model-unexposed Reachability Source Population to
fresh TaskPackage, Path, resource, execution, outcome, Manifest, Job, Runner, prospective
execution, and report identities under the unchanged Measurement Support, S1, Candidate, Prompt,
Grammar, privacy, model/Thinking, recovery, Detour, resource, Verifier vNext, and qualified-
validity contracts. It must complete a credential-free Runner preflight before any Provider call.

Reachability Provider calls or execution, Capability rerun or pooling, source reselection, task or
threshold changes, State Mapping identity or execution, treating static Compiler Paths as
empirical states, Host repair, training, release, and production Contribution remain forbidden.
