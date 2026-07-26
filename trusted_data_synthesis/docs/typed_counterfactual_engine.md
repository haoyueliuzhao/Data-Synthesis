# Typed Counterfactual Engine

## Purpose

Version 0.7 turns a sample-specific `QualityContract` into an executable error
generation specification. The engine answers a narrow question:

> Can the quality runtime detect and localize failures generated from the
> same contract that defines acceptable output?

```text
Proof-Carrying Sample
-> Quality Contract v2
-> Clause Dependency Graph
-> Mutation Opportunity Mining
-> Typed Counterfactual Operator
-> One-factor Minimality Validation
-> Contract Runtime Replay
-> Detection / Root Cause / Failure Closure Calibration
```

The counterfactual engine is a calibration layer. It does not replace clean
candidate evaluation, domain semantic policy, or release gates.

## Violation Space

`ClauseMutationSpec` is attached to a `QualityClause` and freezes:

- mutation operator ID and version;
- mutation family;
- optional upstream root clause kind;
- immutable operator parameters.

The planner resolves every specification through a fail-closed operator
registry. An unknown operator or unavailable version aborts planning. The
resolved dependency graph produces the expected root and transitive failure
closure before any mutation is applied.

```text
Quality Clause
  defines what must hold

Mutation Spec
  defines an allowed way to violate it

Mutation Opportunity
  binds the spec to one sample and one concrete target
```

## Operator Boundary

Core owns structurally universal mutations:

- remove selected evidence;
- mark a trajectory step failed;
- inject an Oracle reference into the public workflow;
- replace an allowed tool;
- perturb a Program output;
- replace a Program operator;
- break a Program dependency;
- perturb the final answer;
- replace a citation source;
- append an unsupported claim.

Domain plugins own semantic distractor selectors:

- Finance: definition, version, forecast, unit, currency, and scope;
- Legal: effective date, jurisdiction, and rule definition;
- Science: observation version, population, and outcome definition.

Core applies domain selectors through `ReplaceSelectedEvidenceOperator`. It
does not inspect fiscal periods, jurisdictions, populations, or other domain
fields. The selector implementation and parameters are included in the
operator manifest hash.

The current evidence-domain mutations are candidate-selection
counterfactuals: they replace a selected gold item with a typed hard
distractor already present in the immutable corpus. They do not rewrite the
archived Evidence object or pinned Proof Graph. This keeps calibration focused
on agent behavior and avoids constructing an inconsistent evidence world.

## Minimality

Every operator declares the JSON path prefixes it may modify. The validator:

1. removes generated trajectory identity fields;
2. computes changed leaf paths;
3. rejects paths outside the declared envelope;
4. computes normalized edit distance;
5. requires a minimality score of at least 0.9.

Minimality means one semantic factor, not necessarily one serialized leaf. A
single Evidence replacement may update matching search and selection
references together.

## Failure Closure

Contract dependencies form a directed acyclic graph. If clause B depends on
clause A, a failure in A can block or invalidate B. The planner freezes:

```text
expected_root_clause
expected_failed_clauses = transitive_closure(expected_root_clause)
```

Runtime replay records detection, observed roots, observed closure, root F1,
and closure F1. Domain clauses depend on the aggregate universal checks used
by the runtime. This avoids claiming per-item localization when a verifier
emits one aggregate result.

## Calibration Gates

A domain calibration passes only when all checks pass:

```text
clean false positives               = 0
mutation validity                   > 0.95
mean minimality score               > 0.90
minimality pass rate                > 0.95
detection F1                        > 0.95
root-cause F1                       > 0.90
failure-closure F1                  > 0.85
mutable-clause coverage             > 0.95
registered-operator coverage        > 0.95
```

The report includes aggregate metrics and slices by mutation family, mutation
operator, and source clause kind. A passing average cannot hide one weak
operator family.

## Reproducibility

Opportunity, trajectory, case, calibration, and operator-manifest identities
are content-addressed. Proof Certificates and Release Manifests freeze the
counterfactual operator manifest. Quality-enabled plugins cannot be created
without one, and the cross-domain suite is release-blocking.

Published component versions:

```text
quality_contract.v2
quality_contract_compiler.v3
proof_certificate.v3
proof_carrying_compiler.v3
counterfactual_planner.v1
typed_counterfactual_generator.v1
counterfactual_minimality.v1
counterfactual_calibration.v3
```

## Commands

```bash
trusted-synthesis validate-counterfactuals \
  --tasks-per-domain 10 \
  --output artifacts/counterfactual_validation/v07_contract_30.json
```

```bash
trusted-synthesis finance-pilot \
  --config config/finance_archive.json \
  --pilot-config config/finance_pilot_v06_pattern_50.json \
  --output-dir artifacts/finance_pilot/v07_counterfactual_50 \
  --output artifacts/finance_pilot/v07_counterfactual_50/cli_report.json
```

The Pilot writes counterfactual cases as JSONL and a calibration report as
JSON alongside clean and legacy mutation artifacts.

## Current Boundary

Version 0.7 calibrates deterministic Contract Runtime behavior. It does not
yet establish human realism, learned critic transfer across held-out domains,
immutable Evidence mutation, or open retrieval robustness. Those are
experiment-layer extensions and must not introduce domain branches into Core.
