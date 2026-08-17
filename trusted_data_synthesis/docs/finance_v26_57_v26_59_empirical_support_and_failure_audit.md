# Finance v26.57-v26.59 Empirical Support and Failure Audit

Audit date: 2026-08-18

## Summary

Finance v26.57 executed the two empirical stages authorized by v26.56 while keeping their
denominators separate:

```text
Capability Development:          12 tasks x 8 unconditional rollouts =  96
Natural State Reachability:       12 tasks x 12 rollouts              = 144
Conditioned State Reachability:   12 tasks x 3 states x 6 attempts    = 216
Total formal denominator:                                              456
```

The corrected result is a valid negative empirical-support result:

```text
Complete model outcomes                 = 456 / 456
Independently valid trajectories        =   0 / 456
Natural valid state hits                =   0
Conditioned valid state hits            =   0
Admitted empirical states               =   0 / 36
Tasks with all three states admitted    =   0 / 12
Production Contribution                 =   0
```

This is not evidence that the public state-condition channel is inert. The conditions changed
pre-calculation acquisition behavior, particularly for `search_then_structured`. The dominant
remaining engineering blocker is that none of the 24 rematerialized tasks binds a model-visible
public Operation-execution contract, while the generic Agent stop gate accepts one successful
calculation as satisfying the calculation requirement. Consequently, every one of the 416
completed trajectories failed frozen Program lineage.

The final transition is:

```text
fresh_public_operation_contract_rematerialization_only
```

Fresh Confirmation, No-C VTDO, Student training, Exact Target, GP-C, and production Contribution
remain forbidden.

## Frozen Protocol

### Role separation

The 12 `capability_measurement` tasks received only unconditional rollouts. The 12
`vtdo_multistate_candidate` tasks received an independent natural sample and three conditioned
samples. Capability-only tasks never acquired a state target. Compiler Witnesses were used only
for credential-free verifier regression and contributed zero empirical observations.

### Public condition contract

Each conditioned request exposed one broad acquisition objective:

- direct typed selection when public selectors are sufficient;
- broad discovery followed by exact typed selection;
- broad discovery followed by public document inspection.

The request did not expose the target Quotient State ID, Static Path ID, Compiler Witness ID, Gold
Evidence ID, hidden Program, or a complete action/tool sequence. Acceptance remained post hoc:

```text
independent complete validity
and
empirical path mapper agrees with the Host-only requested state
```

### Reachability gate

A state could be admitted only if all of the following held:

1. at least one unconditional natural hit;
2. a strictly positive conditioned Wilson LCB95;
3. at least three content- and decision-trace-distinct valid realizations;
4. stable deterministic remapping to the requested state;
5. model-generated realizations only;
6. estimated attempts for three releases no greater than 60.

No threshold was changed after observing model output.

## Execution Integrity

The initial v26.57 run completed all 456 requested jobs with 24 parallel workers. It made 4,536
Provider calls. All 456 raw Artifacts passed byte, Job identity, actual Prompt, Host side-channel,
recursive noninterference, condition noninterference, and Provider-call uniqueness checks.

One row was initially classified as a Runtime failure. Its redacted telemetry showed:

```text
one SSL UNEXPECTED_EOF transient
same request hash retried successfully
four HTTP-success calls in the partial trajectory
no completed trajectory
```

The Provider retry itself worked. The failure arose because `_total_model_tokens` required token
usage on the failed HTTP attempt even though a later same-request success supplied usage. The
permanent fix excludes only `http_success=false` attempts from token accounting; an HTTP-success
response missing usage still fails closed.

v26.58 prospectively authorized exactly one retry for that Job. It explicitly forbade retrying any
of the 455 model-invalid outcomes and was result-quality blind. The replacement produced a complete
but independently invalid Flash trajectory. The corrected denominator is therefore 456 model
outcomes, not a favorable-outcome substitution.

The corrected aggregate is:

| Item | Corrected value |
| --- | ---: |
| Model-invalid trajectories | 456 / 456 |
| Runtime failures | 0 |
| Instrument failures | 0 |
| Provider calls | 4,540 |
| Provider-reported tokens | 20,915,421 |
| Estimated cost telemetry | USD 1.5227473128 |
| Exact requested model | 456 / 456 |
| Fallback use | 0 |
| Raw integrity | 456 / 456 |
| Local GPU jobs | 0 |

v26.58 also corrected a statistical implementation defect: floating arithmetic yielded a tiny
positive Wilson lower bound for `0/6`. Exact zero-success and all-success boundaries are now
clamped to `0.0` and `1.0`, respectively. The original v26.57 report remains immutable.

## Capability Development

Capability behavior and complete trajectory validity were reported separately. A target mechanism
could succeed even when downstream Program execution or answer closure failed.

| Mechanism | Behavior successes | Independent validity | Boundary tasks |
| --- | ---: | ---: | ---: |
| Context-conditioned action | 8 / 24 | 0 / 24 | 0 / 3 |
| Semantic reconciliation | 15 / 24 | 0 / 24 | 3 / 3 |
| Failure recovery | 23 / 24 | 0 / 24 | 1 / 3 |
| State-dependent stopping | 24 / 24 | 0 / 24 | 0 / 3 |

These results support mechanism-specific observations only:

- Flash often completed the registered typed recovery sequence.
- Reconciliation behavior remained heterogeneous and frequently failed before full Evidence
  support.
- Stopping's local estimand saturated even though complete validity was zero, showing that local
  completion verification was not equivalent to full Program completion.
- Context action behavior varied strongly by task rather than forming a stable boundary.

They do not support a capability Confirmation or a claim that any mechanism is sufficient for a
valid trajectory.

## Reachability

No independently valid trajectory occurred in either natural or conditioned sampling. Therefore
all empirical state counts are zero and no invalid trajectory is assigned a Quotient State.

The public conditions nevertheless changed invalid pre-calculation behavior:

| Requested behavior | Matching behavior | Rate | Independently valid |
| --- | ---: | ---: | ---: |
| `structured_direct` | 38 / 72 | 0.5278 | 0 |
| `search_then_structured` | 71 / 72 | 0.9861 | 0 |
| `search_then_open` | 36 / 72 | 0.5000 | 0 |

The unconditional 144-rollout acquisition distribution was:

| Observed behavior | Count |
| --- | ---: |
| `search_then_structured` | 128 |
| `structured_direct` | 12 |
| `search_then_open` | 4 |

This diagnostic does not create state support. It shows only that the condition channel can steer
one public behavior axis before validity is established.

## Failure Cascade

v26.59 replayed every corrected raw Artifact without an API key and produced one diagnostic row per
formal rollout.

### Earliest failure

| Stage | Count |
| --- | ---: |
| Model contract | 40 |
| Evidence selection | 86 |
| Operation execution | 330 |
| Total | 456 |

### Independent Gate failures

| Gate | Failed rows |
| --- | ---: |
| Operation lineage | 416 |
| Answer projection | 349 |
| Verification support | 209 |
| Citation completeness | 173 |
| Evidence support | 86 |
| Target mechanism | 35 |
| Post-completion control | 5 |

The 416 trajectories that reached an accepted final answer matched only a prefix of the frozen
Program:

| Matched Program nodes | Completed trajectories |
| --- | ---: |
| 0 | 106 |
| 1 | 193 |
| 2 | 117 |

No completed trajectory passed full Operation lineage. In addition:

- 207 trajectories passed local verification before Program completion;
- 67 trajectories matched the projected answer despite incomplete Program lineage;
- 382 trajectories completed their local mechanism estimand without complete validity.

These distinctions prevent local behavior success, verification success, or answer coincidence
from being promoted to valid Agent state support.

## Root-Cause Interpretation

Static inspection found:

```text
Tasks with public operation_execution_contract = 0 / 24
Tasks missing it                         = 24 / 24
```

The Compiler Witness executes the Oracle Program, but the model-visible Task metadata does not bind
that Program as a public execution contract. The generic Runtime checks only broad requirements
such as "at least one successful calculation" before allowing a final answer. This explains the
observed pattern in which models often retrieve Evidence, perform one or two calculations, verify a
partial result, and stop before the terminal Program node.

The supported engineering conclusion is:

> The current empirical Population is not yet a valid test of reachable multistate support because
> the public Runtime does not bind complete Program progress to stop readiness.

This is an inference from the conjunction of `416/416` Operation-lineage failures, prefix-only
Program progress, 207 premature verification passes, and the 24/24 missing public contract. It does
not claim that this omission is the sole cause of every model error. Reconciliation still shows a
separate Evidence-support weakness, and condition adherence is imperfect for direct and open paths.

## Required Rematerialization

The next Population must be fresh and identity-incompatible with v26.56. Before receiving a task
identity, Joint Compilation must bind a model-visible Operation-execution contract that:

1. derives from the same semantic source and Program DAG as the Verifier;
2. uses public symbolic variables and selectors rather than Gold Evidence IDs;
3. exposes ordered completion dependencies and the terminal Operation requirement;
4. makes Host stop readiness depend on all required Program nodes, not one calculation;
5. preserves the target mechanism as model-owned;
6. preserves acquisition-path freedom for VTDO candidates;
7. compiles an invalid early-stop counterfactual for every task.

For Context-conditioned action, the contract must not reveal the correct branch. It should expose a
symmetric public choice slot and bind complete execution only after the model chooses. For
Reconciliation, Recovery, and Stopping, downstream Program structure may be scaffolded while the
target normalization, selector-repair, or stop decision remains model-owned.

No additional rollouts, condition tuning, threshold relaxation, Fresh Confirmation, training, or
Contribution experiment is authorized before this rematerialization passes credential-free static
and destructive audits.

## Reproducibility Verification

The completed v26.58 directory was replayed with both `DEEPSEEK_API_KEY` and `OPENAI_API_KEY`
removed from the process environment. The runner reused the existing content-addressed recovery
result before client construction. The Authorization, Recovery Result, corrected rollout set, and
wrapper Report retained their exact SHA-256 values.

The v26.59 audit was independently rebuilt into `/tmp` without credentials. Both generated files
were byte-identical to the authoritative artifacts:

```text
rollout_failure_diagnostics.json
2eed4e7e0d9bdb6441ae11e50440c8a55521e628c9e49dd0d4087238a301da44

report.json
6d8f088666f8b7c51c4e7303f7d4e1f3af825abc73cfc845f4a3dec3022bcf84
```

The original v26.57 Contract retains the direct implementation hashes present before the Runtime
and Wilson-boundary repairs. It is not rewritten. The v26.58 Authorization separately freezes the
corrected implementation and is the authoritative implementation manifest for the recovered
denominator. The current source tree matches all four v26.58 entries exactly:

| Source | Frozen/current SHA-256 |
| --- | --- |
| `phase1_v26_empirical_support_pilot.py` | `c7c1be3e4821ebd3236f5d082e0f3d0d7797278ef98f6322af3fb28cc3123160` |
| `phase1_v26_empirical_support_runner.py` | `8ea5812234ea1af3643ef8cf5b41aa0d9050c640c0590ecd60cd3f4acfe68025` |
| `phase1_v26_empirical_transport_recovery.py` | `e52806723dab7af1e46070710f92365f5e51106ea703d846d03aa7d6e1b182ee` |
| `runtime/agent/iterative.py` | `cde0d687b62fe60d1c62fc773706c0880df6a63c5d854ee3763b82ef1dd2b757` |

The v26.59 implementation hash is
`a1a904070c9a6d15d7fa0fdfda6a1d59faa77f1e1c6fa4bdb561d2021cf0f485`, matching its immutable
Report. The full repository validation completed with 890 tests, Ruff, and Mypy over 353 source
files passing.

## Authoritative Identities

```text
v26.57 source contract
finance_v26_empirical_support_contract:735fcd65a45c426e92033ecaafd1ab55b52e53df1c74b783f0585ca1a01c5695

v26.57 immutable source report
finance_v26_empirical_support_pilot_report:51ee3375dec6b96b0f64334a894d090f3c847262b28f84a5eac5ccbfc6d5bdaa

v26.58 transport authorization
finance_v26_transport_recovery_authorization:1b2b31c26e89e6723bdc9f5bb38bfe13d64f9ef6b9f6dc1469788a7911410c38

v26.58 authoritative recovered report
finance_v26_transport_recovered_pilot_report:fa38e9cd94ecc3efed1632b67bbfbf47a8f7eb320475aa942a0e4a2a0d7ec481

v26.58 corrected Pilot report
finance_v26_empirical_support_pilot_report:b2a68d82475bb086eb8e7b61854d2b864c1eaf824916bedc51aab6cdad718b33

v26.59 failure audit
finance_v26_empirical_failure_audit:d31dfe84d92b26c54c04d4e0fc230614f29f3ca6e6e76f3fa5656423c537af07
```

## Immutable Outputs

### v26.57

| Artifact | SHA-256 |
| --- | --- |
| `execution_contract.json` | `a5c93293502de9ed624467c5373d563526bf3f295506cb2aa95ccf1465ec1e82` |
| `job_manifest.json` | `3b161b33470b64bdcd52bf62f21ad2bc4564db8b4ae7e985cafd4887b17c50c3` |
| `empirical_rollouts.json` | `cb79f29f6d8624fe219e3473c9965dfc22836b752402e5e108cbfebcc7b1f35e` |
| `report.json` | `a58f50680365aafe39b0b0d3c08d1217e795a18eb977016c1e813a4944e1a743` |

### v26.58

| Artifact | SHA-256 |
| --- | --- |
| `transport_recovery_authorization.json` | `a268df0bb308e1416ebd0c0a222d25c301f5fd702bcd5dd356d0796d52f83f5d` |
| `transport_recovery_result.json` | `e5f75ab5c82ab5f3409c8a5ed8c4ba14ae01b90f1bbd0c65aaf93a7b2c0232d2` |
| `corrected_empirical_rollouts.json` | `e22757f030deede1531e68d850fc21f44e41f98990f01db7aaa99e55e7043289` |
| `report.json` | `9aa77da25bc4ce0b430f1da2cfea0de7ce9325ac6180c837faec527f55f548f8` |

### v26.59

| Artifact | SHA-256 |
| --- | --- |
| `rollout_failure_diagnostics.json` | `2eed4e7e0d9bdb6441ae11e50440c8a55521e628c9e49dd0d4087238a301da44` |
| `report.json` | `6d8f088666f8b7c51c4e7303f7d4e1f3af825abc73cfc845f4a3dec3022bcf84` |

Artifact roots:

```text
artifacts/vtdo_experiment/finance_v26_57_empirical_support_pilot_20260818/
artifacts/vtdo_experiment/finance_v26_58_transport_recovery_20260818/
artifacts/vtdo_experiment/finance_v26_59_empirical_failure_audit_20260818/
```
