# Finance v26.197 Fresh Artifact-Backed Terminal-to-Outcome Integration Repair Preflight

Audit date: 2026-09-01

## Decision

Finance v26.197 consumed only:

```text
fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_only
```

The credential-free repair preflight passed. It repairs the two production seams identified by
v26.196 without changing the frozen v26.194 experiment inputs or any of the six v26.195 Outcome
authority identities. The formal decision is:

```text
fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_passed_
independent_audit_required_online_execution_blocked
```

This is an integration preflight, not an online execution result. Provider calls, Development
model outcomes, empirical Outcome rows, empirical estimates, Mapper, State, frequency,
Contribution, VTDO, QA changes, training, release, and production remain zero.

The only permitted successor is:

```text
fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_
independent_audit_only
```

## Exact Authorization And Frozen Parents

The operator-supplied review is retained byte for byte with CRLF line endings:

```text
byte_count  10,305
sha256      079e1e5d7c98d2b7c54fae6d033ef76f47476fb9b6fe166ddc9e59854284ece9
```

Its authorization identity is:

```text
finance_v26_197_external_repair_authorization:
e2b5d5815e6e0c82895ddc30aa877d97bc8c082ceb077f6c208c893ef2181fdd
```

The preflight validates all thirteen v26.196 formal files against the exact distribution
Manifest. It retains the v26.196 negative decision, sealed Root, distribution Root, and permitted
transition:

```text
v26.196 report
  finance_v26_196_fresh_outcome_independent_audit_report:
  5b3b8043bffe3b97a007ce60348860894a382f5fe8c7eb19b3a9b6c7a980741b

v26.196 transition
  finance_v26_196_transition:
  4a50922db8b29f60fb1df8436e3bbe16cc215250d4727144e47528b9a5e0a8a8

v26.196 sealed Root
  finance_v26_196_sealed_evidence_artifact_root:
  5859c971c2b9316d4250363552da38551ef433382c79f44dd1ef201534a0b3f9

v26.196 distribution Root
  finance_v26_196_distribution_artifact_root:
  e8d0770c063fc6847feb045e355ba7c9ba42f2d7740af6930ec4dd4c1b1d6b83
```

The exact v26.194 Catalog, Manifest, Runner, and Execution Contract are loaded from immutable
artifacts and strictly parsed. The exact v26.195 Terminal Registry and five downstream Contracts
are also strictly parsed. Their six identities change zero times:

```text
FreshTerminalRegistry
FreshRawExecutionDescriptorContract
FreshJobResultDescriptorContract
FreshJobBoundAttemptTraceContract
FreshOutcomeRowContract
FreshExactEvidenceSetEvaluatorContract
```

The v26.194 source and artifact bytes remain untouched. In particular, its historical
`AuthoritativeJsonExplicitExecutionKernel.complete_job` still emits `fixture_complete`; that
method remains the negative evidence observed by v26.196 and is not silently rewritten.

## Fresh Successor Integration Identity

The repair introduces a separate successor implementation and Contract:

```text
implementation binding
  fresh_terminal_to_outcome_implementation_binding:
  b5f2ca3cff51b6563b58c7840f244f4bb21cf9b07f0ceb4fe9b526046fa1ce57

integration Contract
  fresh_terminal_to_outcome_integration_contract:
  d8de732958e439dabedd63baec87e3f504f29dfd8bd2050881652da4aef29c58
```

The implementation binding source-freezes the new production integration module, the preflight
and report models, and the exact v26.195 `FreshOutcomeArtifactWriter` source. It separately binds
the authorization guard, dispatcher, successor Kernel constructor, `invoke`, `complete_job`,
bundle validator, and both writer methods.

The new `FreshOutcomeIntegratedExecutionKernel` composes, rather than changes, the frozen v26.194
Kernel. Its production-shaped path is:

```text
exact external authorization bytes
  -> PrecredentialAuthorizationGuard
  -> zero-Provider certified client construction
  -> v26.194 AuthoritativeJsonExplicitExecutionKernel.invoke
  -> TerminalExecutionEvidence
  -> AuthoritativeTerminalDispatcher.dispatch
  -> successor complete_job(job_id=...)
  -> v26.195 FreshOutcomeArtifactWriter.write_raw
  -> v26.195 FreshOutcomeArtifactWriter.write_result
  -> reconstructed FailureLocus / AttemptTrace / Outcome
```

`complete_job` accepts only `job_id`; it has no terminal parameter. The dispatcher receives
orthogonal observed response or exception evidence and is the only component that selects a
registered terminal policy. The test harness retains expected terminal names only for subsequent
comparison; it does not pass them into `invoke`, the dispatcher, or `complete_job`.

The richer zero-Provider control evidence remains bound by the unchanged v26.195 descriptor,
Result, Trace, Outcome, and evaluator Contract identities. It adds only successor-owned evidence
preimages under the new integration identity. The old v26.195 scripted bundle and evaluator are
not used as an Outcome oracle for these controls.

## Sixteen Reachable Terminal Controls

Sixteen distinct exact v26.194 Manifest Jobs each make one local certified-client invocation
through the actual frozen `invoke`. The client either returns a concrete public payload or raises
one concrete typed local failure. It never makes a Provider call. The successor Kernel derives
and persists one terminal projection per Job.

The exact control result is:

```text
distinct exact Jobs                              16
v26.194 invoke calls                             16
dispatcher decisions                             16
terminal projections                             16
FreshOutcomeArtifactWriter Raw calls             16
FreshOutcomeArtifactWriter Result calls          16
actual typed Raw / Result files                16 / 16
actual Raw/Result byte matches                    32
reconstructed Traces / Outcomes                16 / 16
reconstructed FailureLoci                         15
correction counts                                  3
fixture_complete Results                           0
Python/Pydantic/ValueError escapes                  0
Provider calls                                      0
```

Every reachable terminal occurs exactly once:

| Terminal | Observed evidence class | Verifier/validity projection |
| --- | --- | --- |
| `completed_qualified` | final payload | Base=true, Mechanism=true, Qualified=true |
| `completed_invalid` | final payload | Base=false, Mechanism=true, Qualified=false |
| `first_response_abi_invalid` | primary payload | non-Verifier null factors |
| `correction_response_abi_invalid` | correction payload | non-Verifier null factors |
| `first_action_reference_invalid` | primary payload | non-Verifier null factors |
| `correction_action_reference_invalid` | correction payload | non-Verifier null factors |
| `correction_attempt_typed_invalid` | correction payload | non-Verifier null factors |
| `final_response_abi_invalid` | final payload | Final ABI=false, Verifier not invoked |
| `provider_failure_no_payload` | typed client exception | non-Verifier null factors |
| `provider_transport_failure` | typed client exception | non-Verifier null factors |
| `privacy_rejection` | actual v26.194 privacy rejection | non-Verifier null factors |
| `resource_budget_exhausted` | typed client exception | non-Verifier null factors |
| `instrument_failure` | typed client exception | non-Verifier null factors |
| `provider_identity_failure` | typed client exception | non-Verifier null factors |
| `thinking_integrity_failure` | typed client exception | non-Verifier null factors |
| `usage_integrity_failure` | typed client exception | non-Verifier null factors |

All Raw files precede their matching Result files. Every descriptor binds the actual canonical
bytes, SHA-256, byte count, exact Job namespace, and exact frozen parent. Reconstruction reruns
the dispatcher from the persisted Raw evidence and separately recomputes the attempt, validity,
FailureLocus, Trace, and Outcome projections.

These are branch and persistence controls. They are not empirical model outcomes and do not
estimate the probability of any terminal.

## Dispatcher-Specific Exclusion Witnesses

The two v26.195 not-applicable names receive separate source-bound witnesses:

```text
measurement_support_exit
policy_horizon_exhausted
```

For each name, the exact successor dispatcher method and successor `invoke` method contain zero
branch tokens, and `complete_job` contains zero caller terminal parameters. The witness binds both
method hashes and the exact integration Contract. Both names enter zero empirical denominators.

This result is deliberately narrow. It shows that the concrete v26.197 dispatcher and Runner
have no branch ownership for these terminals. It is not a universal claim that later Runner
identities can never introduce such branches.

## External Authorization Ingress

The successor Kernel constructor accepts the external authorization object and its exact bytes.
`PrecredentialAuthorizationGuard` executes before `client_factory`, both writer factories, or any
credential lookup. Six constructor-level controls produce:

```text
legal repair-preflight parent              admitted; client constructions 1
missing parent                             rejected; client constructions 0
modified parent                            rejected; client constructions 0
self-declared parent                       rejected; client constructions 0
cross-experiment v26.196 parent            rejected; client constructions 0
legal parent with Provider request         rejected; client constructions 0
invalid-control credential lookups                                      0
Provider calls                                                          0
```

The current authorization permits only the credential-free repair preflight. A legal parent does
not imply online permission; requesting Provider execution with it rejects before credential
lookup.

## Destructive And Static Controls

All thirteen registered destructive controls reject. The set includes caller-supplied terminal,
duplicate completion, stale and rehashed terminal-decision crossing, stale Raw/Result/Trace/
Outcome parents, rehashed integration-Contract crossing, excluded-terminal injection,
Result-before-Raw, the old `fixture_complete` shape, and Raw terminal-parent drift. Four controls
recompute the directly mutated content identity before reaching the next validator.

All 28 noncompensatory static Gates pass. There is no compensatory scoring: authorization ingress,
all sixteen reachable terminal paths, both exclusion witnesses, exact Raw/Result bytes, Trace and
Outcome reconstruction, zero fixture fallback, frozen authority identities, zero Provider calls,
and online blocking each pass separately.

## Formal Artifacts And Verification

The authoritative source identity is:

```text
source commit  2551fc331f5e1327a5b78054423223d158f08d6a
source tree    a5b1699e8e1de3622f2ddb567d6df2148a47f47e
```

The formal directory is:

```text
artifacts/vtdo_experiment/
finance_v26_197_fresh_artifact_backed_terminal_to_outcome_integration_repair_
preflight_v1_20260901
```

It contains 48 files and 285,781 bytes: sixteen Raw files, sixteen Result files, and sixteen root
files. The exact report and Roots are:

```text
report
  finance_v26_197_terminal_outcome_repair_preflight_report:
  57692819ab14fc6f7f6a9fa90f7f6c9ddb887da77ce997286d0392aed5d07954

report SHA-256
  26003cb5b7861d513b03fe1e30f20afe9cd981943ce3f7367137094ed284dc81

sealed Root
  finance_v26_197_sealed_evidence_artifact_root:
  cc217ac3b877c74341070ad8cfb8298c6d232f5c1d6bb514aafc936fc1142598

distribution Root
  finance_v26_197_distribution_artifact_root:
  4d9760be75c4dc3f1acdd79648cddfadab30e84e823aaef2d27874346131e6e2
```

Verification results:

```text
focused v26.197 Pytest                         8 / 8 passed
adjacent v26.195-v26.197 Pytest              23 / 23 passed
empty-directory v26.197 rebuild              48 / 48 byte-identical
focused PyCompile                            passed
focused Ruff check / format                  passed
package-wide Ruff                            passed
focused no-import-follow Mypy                passed
```

Package-wide no-import-follow Mypy checked 626 source files and retained ten historical
diagnostics in six pre-v26.197 files. No v26.197 diagnostic occurred, so no package-wide Mypy pass
is claimed.

## Remaining Boundary

v26.197 closes only the first terminal-to-fresh-Outcome and external-authorization ingress seam.
It does not independently audit its own implementation and does not authorize online execution.
The 16 controls are a complete Registry branch denominator, not the 192-Job empirical Manifest
denominator. No model behavior, Capability, frequency, State, Contribution, or VTDO conclusion is
available.

The successor independent audit may only rebuild and inspect this exact preflight, repeat the
sixteen actual paths, verify the two dispatcher witnesses and authorization ordering, and decide
whether online authorization is warranted. It may not change source Tasks, Manifest Jobs,
Components, Candidates, Schedules, model, Thinking, Grammar, Policy, resource, validity,
threshold, six Outcome authority semantics, QA branch, or historical artifacts. Provider
execution remains forbidden until that independent audit produces a separate explicit online
authorization.
