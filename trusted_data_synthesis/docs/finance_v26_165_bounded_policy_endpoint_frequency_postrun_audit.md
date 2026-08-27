# Finance v26.165 Bounded-Policy Endpoint Frequency Independent Postrun Audit

Date: 2026-08-28

## Decision Summary

Finance v26.165 consumed only:

```text
fresh_bounded_policy_endpoint_frequency_postrun_audit_only
```

It performs a credential-free independent postrun audit over the complete frozen v26.164 online
and Raw-only recovery lineage. It makes zero Provider calls and does not use the v26.164 endpoint
projector, Global Integrity Gate, Mapper summary, or Cell-frequency summary as an outcome oracle.

The audit independently confirms:

```text
complete Raw Executions                         360/360
complete Provider artifact triples            2,919/2,919
bounded-policy endpoint matches                 360/360
Global Integrity Gate match                       exact
Qualified-valid rows                            106
Production / Reference Mapper matches           106/106
recovered Assignment canonical-byte matches     106/106
Cell frequency report matches                    48/48
Provider calls during audit                           0
```

The v26.164 bounded-policy finite-sample empirical `q_c` and success-conditional `pi_c`
reports are independently confirmed. The audit authorizes no unrestricted natural-agent
distribution, cross-task State probability, Path causal effect, simultaneous multinomial
coverage, VTDO, training, release, or production claim.

The final decision is:

```text
no_further_experiment_authorized_without_new_audit_decision
```

## Source And Immutability Replay

Before loading a recovered result, v26.165 recomputes the exact failed execution directory:

```text
files                                  9,143
bytes                             64,601,865
content root  finance_v26_bounded_policy_failed_execution_content_root:
              060ae57a88d85a209029331701181e6e48aa846116c8463bcb32317093773446
```

It matches the v26.164 freeze exactly. It separately binds all thirteen Raw-only recovery files
and six implementation files covering the original execution, Raw-only recovery, and independent
audit implementations. The audit then reconstructs the exact prepared v26.163 authorization from
the failed directory's frozen inputs.

Credential lookup, real model-client construction, Provider calls, Stage 2 Provider calls, row
deletion, and historical reclassification are zero.

The source replay identity is:

`finance_v26_bounded_policy_postrun_source_replay:c66840bb13d166db111c57e8f60cd928a0ab61aaa3b9dcdcf6c89f26c495b79a`.

## Independent Raw And Provider Audit

For each of the 360 exact Manifest Jobs, the audit:

1. locates the Raw artifact through the Runner's content-addressed Raw path;
2. requires exact Job identity and payload equality;
3. reparses every referenced Provider Envelope, public Projection, and Transport certificate;
4. reconstructs exact-model, fallback-absence, native-tool-absence, Thinking, and Usage flags;
5. checks dynamic request, resource, artifact-pairing, reversible Commit, Privacy, Transport, and
   Stage 2 integrity;
6. independently reconstructs Measurement Support and model-terminal status;
7. invokes the established independent task/Mechanism Verifier only where the frozen endpoint
   language requires it;
8. constructs the Route B endpoint from those independent fields;
9. compares the finished endpoint to the recovered production endpoint only after construction.

The complete independent Provider artifact result is:

```text
Provider calls / Envelopes / Projections / Transports   2,919 each
exact-model failures                                         0
Thinking failures                                            0
Usage failures                                               0
Privacy failures                                             0
unresolved Transport failures                                0
Stage 2 Provider calls                                       0
Prompt tokens                                       15,302,382
Completion tokens                                   13,237,351
Reasoning tokens                                    12,793,715
total tokens                                        28,539,733
```

The authoritative Provider audit identity is:

`finance_v26_bounded_policy_independent_provider_artifacts:3f39f9d03eb7b340965a6a8ee8c6903f160831c8a0f7ffab2a4bd6058a5849fb`.

## Typed Semantic-Rejection Boundary

The two typed semantic-rejection Raw rows are an explicit cross-version boundary rather than an
implicit repair. The legacy independent projection reproduces:

```text
validity evaluable             false
Base validity                   null
Mechanism qualification         null
Qualified validity              null
task-Verifier calls                 0
```

Only after confirming that exact legacy-null shape does v26.165 apply the already frozen Route B
terminal rule:

```text
model terminal observed         true
task completion                false
Base validity                  false
Mechanism qualification        false
Qualified validity             false
State Mapping eligibility      false
```

Both final Route B endpoints match the v26.164 recovered endpoints exactly. The audit does not
claim that the legacy Verifier independently returned false, does not invoke a task Verifier,
does not map either row, and does not change either Raw terminal.

## Independent Endpoint Catalog

The independently reconstructed endpoint partition is:

```text
completed_model_endpoint             150
model_result_failure                 207
model_typed_rejection                  2
policy_horizon_exhausted               1
total                                 360
```

All 360 endpoints match production exactly. There are 359 model terminals and one policy
terminal. All 360 are evaluable under the exact Route B endpoint language. Base-valid,
Mechanism-qualified, and Qualified-valid counts are 106, 226, and 106.

The Horizon reason partition remains one `ordinary_detour_limit` and zero for every other
declared reason. Its later Provider-call count is zero.

The endpoint Catalog identity is:

`finance_v26_bounded_policy_independent_endpoint_catalog:62b5c5ddea08edcca7ac47d6718319f27d902d44bda0d43324233f77e0d40788`.

## Independent Global Integrity Gate

v26.165 builds the Global Integrity Gate directly from the 360 independent endpoint rows. The
result passes with:

```text
complete Raw                                      360/360
bounded-policy endpoints                         360/360
Raw Instrument failures                                0
Resource-accounting failures                           0
Privacy failures                                       0
Provider identity / Thinking / Usage failures          0
unresolved Transport failures                          0
unsupported Measurement Support exits                  0
failure IDs                                             0
```

Its complete object and Gate identity equal the recovered production Gate. The independent Gate
identity is:

`finance_v26_bounded_policy_independent_gate_audit:52ad6e08d0051679980be077e66431f055fc93e8c799adc3e532de993b382e7f`.

## Independent Mapper Replay

Only after the independent Gate passes does v26.165 map the 106 independently Qualified-valid
rows. For each row it independently reconstructs:

- the Runtime Operation alias binding;
- the public semantic trajectory projection;
- Answer comparison and Verifier-input binding;
- Mapper-v2 Production State;
- independent Reference Mapper State;
- empirical Route Signature.

Production and Reference State objects match 106/106. The independently rebuilt Assignment
canonical bytes match the recovered formal Assignment bytes 106/106. Canonical-byte equality is
the artifact rule; Python object identity or Pydantic private implementation state is not used as
evidence.

The independently confirmed mapping result is:

```text
formal Assignments                         106
unique structural States                    53
unique empirical Route Signatures           57
pre-Gate Mapper invocations                   0
Horizon mapping attempts                      0
typed-rejection mapping attempts              0
Provider calls                                0
```

The independent Mapper audit identity is:

`finance_v26_bounded_policy_independent_mapper_audit:17b803386c13eacd09348765ba206751891c24a71c1f4157766d0c13a4b560db`.

## Independent Cell Frequencies

v26.165 groups independent endpoint rows only by the frozen strong statistics key:

```text
(task_package_id, experimental_condition_id, generation_policy_id)
```

It does not use empirical Route as a key and does not pool Unconditional or conditioned Cells.
For every Cell it independently recomputes exact endpoint completeness, `N_qualified`,
`q_hat`, its 95% Wilson interval, State counts, success-conditional `pi_hat`, each marginal
95% Wilson interval, and the empirical non-degeneracy flag.

All 48 canonical Cell report bytes match production:

```text
Cell reports                                  48/48
total exact endpoints                        360
Qualified rows                               106
q instantiated Cells                          48
pi instantiated Cells                         38
zero-Qualified Cells                          10
empirically non-degenerate Cells              27
imputed zero-State vectors                      0
simultaneous multinomial claims                 0
```

The complete 48-Cell table is recorded in
`docs/finance_v26_164_bounded_policy_endpoint_frequency_execution.md`; the content-addressed
JSON remains the statistical authority.

The independent Cell audit identity is:

`finance_v26_bounded_policy_independent_cell_frequency_audit:99ab80662395bd9154863ad2c59a03f47f06df6daf224f8f0240c97dfc2c517b`.

## Recovery Boundary

The audit independently confirms:

```text
failed online directory unchanged                  true
direct checkpoint byte matches                  358/358
typed semantic rejections                             2
legacy-null to Route-B-false normalizations           2
typed-rejection mapping attempts                       0
policy-horizon endpoints                               1
later calls after policy Horizon                       0
row deletions                                          0
historical reclassifications                           0
recovery Provider calls                                0
```

The recovery-boundary identity is:

`finance_v26_bounded_policy_recovery_boundary_audit:cf0ed4aa09c4c5bbb9090b738c01c9914fbb30fc0d4100c5f4c434cd48504fb0`.

## Preliminary Fail-Closed Attempts

Three preliminary audit implementation attempts stopped before formal output:

1. A directory-snapshot helper initially used the audit-output prefix when checking the failed
   v26.164 root. The computed hash correctly failed against the frozen root. The final helper
   uses the original content-root namespace for that exact comparison.
2. The first endpoint loop incorrectly required the legacy independent Verifier to emit boolean
   validity for typed semantic rejections. It failed on the first such Job after reproducing the
   expected nulls. The final implementation verifies the null boundary before applying the
   separate frozen Route B rule.
3. The first Mapper comparison used Pydantic object equality. It failed even though State ID,
   Route ID, and every canonical JSON field matched and the difference set was empty. The final
   implementation uses canonical-byte equality, consistent with the repository's immutable
   artifact rule.

The formal writer runs only after every endpoint, Gate, Mapper, Cell, and recovery-boundary check
passes. These attempts wrote no formal v26.165 JSON files, made zero Provider calls, and changed
no predecessor artifact.

## Format-Complete Rematerialization

The first complete v26.165 v1 audit over the successful v26.164 v2 recovery remains immutable.
A later focused format check found one local formatting difference in the recovery implementation.
The recovery source was formatted and bound to a fresh v3 recovery directory; v26.165 was then
rerun under a fresh v2 audit identity. Both stages made zero Provider calls.

Every scientific detail file retained exact bytes and identity: endpoint Catalog, Provider audit,
Gate, Mapper audit, Cell audit, recovery boundary, recovered execution report, Assignment
Catalog, and Cell Catalog. Only the implementation-bound recovery Freeze and top-level reports,
plus the v26.165 source replay and top-level report, changed. The v3 recovery plus v2 audit is the
authoritative format-complete chain.

## Reproducibility

The authoritative formal v26.165 v2 directory contains seven detail files and one report. A
fresh credential-free build from an empty output directory independently reconstructs all eight
and matches 8/8 exact bytes.

The authoritative v26.164-v26.165 focused suite passes 15/15 in 77.53 seconds. The v26.162-v26.163
fast adjacent regression passes 3/3 in 3.77 seconds. Focused Ruff format and check, focused Mypy,
and PyCompile pass for all six new source files and two new test files. Package-wide Ruff check
passes. Package-wide Mypy checks 515 source files and retains only the four pre-existing
v26.70/v26.129/v26.154 diagnostics; v26.164-v26.165 contribute zero diagnostics.

## Scientific Interpretation

The audit confirms empirical frequencies for one exact finite experiment:

- twelve fresh first-exposure tasks;
- 48 fixed strong Cells;
- 360 secondary rollout replicates;
- the exact one-Detour Route B bounded generation Policy;
- the exact frozen model, Thinking, Prompt, Candidate, Support, resource, recovery, Verifier, and
  Mapper Contracts.

It does not establish a task-population probability distribution. Ten Cells have no Qualified
row, so their success-conditional State distribution remains null rather than an imputed State.
A further 11 instantiated `pi` Cells fail the predeclared empirical non-degeneracy rule. Even
the 27 non-degenerate finite-sample Cells carry only marginal interval statements within this
experiment.

No current result authorizes a VTDO value, policy comparison, mechanism causal effect, training
selection, release decision, or production Contribution.

## Authoritative Identities

- v26.165 report:
  `finance_v26_bounded_policy_postrun_audit_report:b3386f7af43fcabc874ab77de8676529b9dd8cbbed381ccee4433fc6eaeab1fa`;
- source replay:
  `finance_v26_bounded_policy_postrun_source_replay:c66840bb13d166db111c57e8f60cd928a0ab61aaa3b9dcdcf6c89f26c495b79a`;
- independent endpoint Catalog:
  `finance_v26_bounded_policy_independent_endpoint_catalog:62b5c5ddea08edcca7ac47d6718319f27d902d44bda0d43324233f77e0d40788`;
- independent Provider artifacts:
  `finance_v26_bounded_policy_independent_provider_artifacts:3f39f9d03eb7b340965a6a8ee8c6903f160831c8a0f7ffab2a4bd6058a5849fb`;
- independent Gate:
  `finance_v26_bounded_policy_independent_gate_audit:52ad6e08d0051679980be077e66431f055fc93e8c799adc3e532de993b382e7f`;
- independent Mapper:
  `finance_v26_bounded_policy_independent_mapper_audit:17b803386c13eacd09348765ba206751891c24a71c1f4157766d0c13a4b560db`;
- independent Cell frequencies:
  `finance_v26_bounded_policy_independent_cell_frequency_audit:99ab80662395bd9154863ad2c59a03f47f06df6daf224f8f0240c97dfc2c517b`;
- recovery boundary:
  `finance_v26_bounded_policy_recovery_boundary_audit:cf0ed4aa09c4c5bbb9090b738c01c9914fbb30fc0d4100c5f4c434cd48504fb0`;
- recovered v26.164 execution report:
  `finance_v26_bounded_policy_frequency_execution_report:624fd8e910ad154cefd084ce6dac9dd9b53e8b7454f8428e24edc6843808e4df`.

## Final Decision

The exact current decision is:

```text
no_further_experiment_authorized_without_new_audit_decision
```

The v26.163 Population, v26.164 Raw denominator, failed execution directory, recovery projection,
Gate, Mapper Assignments, and frequency reports, plus the v26.165 independent audit are frozen.
No Provider execution, Population or Policy change, denominator repair, row deletion, Cell
reselection, State probability, VTDO, training, release, or production Contribution is
authorized without a new explicit audit decision.
