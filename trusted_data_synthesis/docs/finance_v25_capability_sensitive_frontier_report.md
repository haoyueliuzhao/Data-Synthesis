# Finance v25 Capability-Sensitive Frontier Report

Date: 2026-08-12

## Scientific Status

Finance v25 replaces the v24 surface-balanced ladder with a capability-identifiable task
construction stage. The result is:

```text
Runtime qualification:                    inherited from v24, passed
Executable structural Frontier:           passed
Capability-direction coverage:            passed
Empirical Pro--Flash capability boundary: not evaluated
Exact Target / GP-C / VTDO:               forbidden
```

The only newly authorized transition is `paired_model_capability_boundary_calibration`. This is
not an authorization for state conditioning, Exact Target, Validation, Authorization Objective
access, GP-C, a VTDO update, or a nonzero production Contribution.

## Why v24 Could Not Continue

v24 balanced six Finance labels, entities, periods, and metrics, but retained almost identical
Program shapes across Easy, Frontier, and Hard. Its Frontier--Easy semantic gain was `0.0117`, so a
larger rollout would only have measured the same low-information task direction more precisely.

v25 makes the missing prerequisite explicit:

> A task distribution is capability-informative only if it spans distinct capability directions,
> contains irreducible decision depth, and later places empirical mass near the beneficiary's
> capability boundary.

Balancing labels without these conditions is a pseudo-distribution: it can look diverse while its
capability information matrix is low-rank or ill-conditioned.

## Frozen Construction Contract

The construction uses seven axes and seven separately registered families:

| Capability axis | Executable family |
| --- | --- |
| Retrieval | `finance.multi_hop_retrieval_join` |
| Planning | `finance.branching_operation_plan` |
| Calculation | `finance.calculation_chain` |
| Reconciliation | `finance.definition_reconciliation` |
| Verification | `finance.verification_sensitive_selection` |
| Recovery | `finance.recovery_guided_search` |
| Stopping | `finance.stopping_decision_control` |

Family names do not add weight to capability vectors. They are used only by a fail-closed audit
that checks whether each family's centered structural demand has its largest positive component on
the registered axis.

Each family has three Easy, five Frontier, and two Hard-Control tasks, for 70 tasks in total. The
builder reserves scarce multi-entity bindings before abundant temporal bindings and records the
complete 420-artifact source manifest, source SHA-256, run ID, and sampling salt.

## Evidence And Program Integrity

The input is the immutable 420-task real Finance population built from the read-only Archive. The
new builder considers Gold Evidence and independently Finance-policy-valid public Evidence as a
candidate construction pool. Every selected composite task then receives:

- a new immutable Evidence Bundle and public Evidence Corpus;
- a Proof Graph;
- a typed Task Program DAG;
- deterministic execution;
- independent Oracle replay;
- a projected answer contract;
- typed query, reconciliation, verification, recovery, and stopping requirements.

All 70 Programs executed and independently replayed. Public Evidence is disjoint across all 70
tasks. The tasks reference 182 of the 420 frozen source artifacts, while the full source-artifact
identity set remains part of the population hash.

`public_source_count` measures source heterogeneity in the frozen public search space, including
distractors. It does **not** claim that every Gold answer integrates the same number of independent
sources. Cross-source Gold reconciliation remains a later data-construction requirement.

## Tier Audit

All preregistered dimensions are strictly monotonic:

| Dimension | Easy | Frontier | Hard |
| --- | ---: | ---: | ---: |
| Evidence hop count | 2.143 | 3.143 | 4.143 |
| Public source count | 1.000 | 2.000 | 3.000 |
| Operation DAG depth | 1.143 | 2.143 | 3.143 |
| Query decomposition rounds | 1.143 | 2.143 | 3.143 |
| Reconciliation count | 1.143 | 2.143 | 3.143 |
| Required verification count | 1.143 | 2.143 | 3.143 |
| Required recovery count | 0.000 | 1.143 | 2.143 |
| Distractor branches | 0.000 | 3.000 | 6.000 |
| Tool types | 3.000 | 5.000 | 6.000 |
| Minimum tool calls | 5.000 | 10.714 | 17.714 |
| Stopping conditions | 1.143 | 2.143 | 3.143 |

Easy is single-retrieval-solvable; Frontier and Hard are not. Frontier gain exceeded the frozen
minimum in all seven families, rather than only in a global aggregate. All 77 registered
family-by-dimension monotonic checks and all seven family-specific single-retrieval transitions
pass; one collapsed family can no longer be hidden by the other six.

## Capability Information Audit

For each task, v25 derives a positive seven-axis demand vector only from executable Program and
typed workflow fields. It normalizes each vector, subtracts the population mean, and computes the
structural-demand covariance.

Because seven centered family contrasts have at most six independent between-family directions,
authorization uses the leading six-dimensional contrast subspace. The seventh eigenvalue and full
condition number remain mandatory diagnostics; they are not deleted or silently rounded away.

| Metric | Result | Gate |
| --- | ---: | ---: |
| Numerical rank | 7/7 | at least 6 |
| Full effective rank | 5.227 | diagnostic |
| Contrast-subspace effective rank | 5.141 | at least 4.0 |
| Contrast-subspace condition number | 4.726 | at most 100 |
| Full condition number | 106.603 | diagnostic |
| Registered family primary-axis matches | 7/7 | 7/7 |

The complete spectrum is:

```text
0.017485598527
0.011376508911
0.007024386162
0.006755375794
0.003805890035
0.003699545143
0.000164024778
```

Mutation tests prove that equal vectors under balanced family labels fail closed, relabeling
structural vectors leaves the spectrum unchanged but fails primary-axis alignment, and flattening
one registered Easy--Frontier--Hard dimension blocks the next stage. Missing or unknown capability
families are rejected before covariance estimation.

## Determinism

Two independent executions with identical source file, run ID, and sampling salt produced the same
Population ID and byte-identical outputs:

```text
Population ID:
finance_capability_sensitive_frontier_population:
81b49ce6e389312102ccb003230657259b1078248b6e979c65095ad7e1462488

Population SHA-256:
e6dbf78b51a03e1d33a3d87dee596560476f4f25ae62096e279d69eec6a0fab4

Report SHA-256:
c710205106a406458caffc6b7ef58adcac109887844f9b9a0bf1be106b5df538
```

## Runner Boundary

The v24 runner is intentionally not reused. It accepts the old `FinanceTaskStateArtifact`, six
families, and old Runtime Task identities. Adapting v25 by parsing it into those types would erase
the new Program, Corpus, recovery, stopping, and capability-demand identities.

The next runner must freeze a v25-native contract and independently rebuild:

- the Trajectory Verification Context;
- the public tool manifest and Corpus hash;
- three Runtime arms;
- model and provider identity;
- per-family task quotas;
- validity, recovery, verification, and stopping metrics;
- checkpoint and incremental resume identities.

Before the balanced comparison, run a seven-task qualification with one task per family:

```text
7 tasks x 2 models x 3 runtimes x 3 replicas = 126 rollouts
```

Only if all frozen runtime and semantic gates pass may the experiment run four Frontier tasks per
family:

```text
28 tasks x 2 models x 3 runtimes x 10 replicas = 1,680 rollouts
```

Use parallel API workers with incremental checkpoints. The empirical gate must test whether tasks
fall near the Pro, Flash, and beneficiary capability boundaries; structural readiness alone cannot
establish boundary sensitivity.

## Revalidation

At this stage no API or GPU was used. The focused checks were:

```text
v25 pseudo-distribution and Frontier mutations: 5 passed
Adjacent capability / Operation / Finance tests: 24 passed
Ruff: passed
Mypy, v25 module: passed
Program execution and independent replay: 70/70
Deterministic full construction replay: byte-identical
```
