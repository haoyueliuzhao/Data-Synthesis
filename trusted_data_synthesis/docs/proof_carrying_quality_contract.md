# Proof-Carrying Synthesis And Quality Contracts

## Purpose

Version 0.5 turns task construction and task-specific verification into one compilation flow:

```text
Domain-instantiated Task Package
        + Evidence Bundle
        + Proof Graph
        + Operation Registry
        + Domain Quality Provider
        -> Reference Workflow + independent replay
        -> Sample-specific Quality Contract
        -> Proof Certificate
        -> Proof-Carrying Sample
```

The proof object is executable evidence and program provenance. It is not a claim of formal theorem
proving. The design makes it possible to answer two questions independently:

1. Which exact artifacts define this sample?
2. Which exact checks must a candidate satisfy for this sample?

## Core Objects

### Quality Clause

A `QualityClause` is the smallest executable check. It freezes:

```text
clause kind and Universal/Domain scope
fatal, quarantine, or diagnostic severity
typed target and optional JSON path
verifier ID and version
expected reference and parameters
topologically ordered dependencies
failure family and diagnostic dimensions
```

Clause IDs are content-addressed. A change to the target, verifier, expected value, dependency, or
failure semantics produces a new ID.

### Quality Contract

A `QualityContract` contains all clauses and their gate aggregation for one task. Its identity also
binds the compiler version, verifier registry manifest, and optional domain provider ID/version.
Contract validation rejects duplicate clauses, forward or unknown dependencies, unknown gate
references, unassigned clauses, incomplete provider identities, and stale hashes.

### Proof Certificate

A `ProofCertificate` binds:

```text
Task identity
Evidence Bundle hash
Proof Graph hash
Task Program hash
Quality Contract hash
expected output hash
Reference Workflow execution hash
Operation Registry manifest hash
Domain Plugin manifest hash
Source-grounding manifest hash, when applicable
compiler and schema versions
```

The certificate prevents an Evidence Bundle, graph, program, evaluator, policy, or answer from being
silently replaced while retaining the old sample identity.

### Proof-Carrying Sample

The internal sample stores stable references and hashes for the task, Evidence Bundle, Proof Graph,
Reference Workflow, Quality Contract, and certificate. The public projection contains only the
Public Task and proof identity. It cannot serialize the Oracle Contract, gold Evidence IDs, or
reference answer.

## Contract Compilation

`QualityContractCompiler` validates that the Task Oracle, Evidence Bundle, and Proof Graph describe
the same task before producing any clause.

### Boundary clauses

Derived from the Public/Oracle and workflow contracts:

```text
task identity
candidate workflow kind
required actions and successful step states
action sequence
planning and retrieval tracks
public-only generation
allowed tools
```

### Evidence and proof clauses

For every gold Evidence item, the compiler emits independently locatable clauses for existence,
selection, and Proof Graph presence. Set-level checks cover known/valid retrieval, recall, precision,
selection provenance, and source grounding.

### Program clauses

For every Task Program node, the compiler validates the operation contract against the frozen
Operation Registry and emits a node-targeted execution clause. Dependencies include selected
Evidence clauses and predecessor Program nodes. This produces a clause DAG aligned with the Task
Program DAG.

### Answer and citation clauses

The answer schema produces result and required-field clauses. Every gold Evidence item also receives
an exact citation-binding clause. Existing strict schema, value, unsupported-claim, and citation
checks remain represented during the parity migration.

### Domain clauses

Core calls a `DomainQualityClauseProviderProtocol`; it never selects or imports a concrete domain.
Providers currently cover:

```text
Finance: evidence semantics, financial comparability, operation eligibility, bounded claims
Legal: jurisdiction/effect/authority semantics and claim boundaries
Science: protocol/population/metric comparability, uncertainty, and qualified claims
```

Provider identity is frozen in both `DomainPluginSet` and the task contract. A provider cannot own
common dependency ordering, gate aggregation, runtime behavior, or release policy.

## Runtime

`QualityContractRuntime` follows a fail-closed sequence:

```text
Candidate Trajectory
        -> Candidate Observation Index
        -> topological Clause execution
        -> Universal and Domain Gate aggregation
        -> root-failure and unexecuted-clause analysis
        -> accepted or rejected decision
```

The verifier registry is versioned and content-addressed. Contract and runtime registry manifests
must match. Unknown verifiers, verifier exceptions, failed dependencies, and missing observations do
not disappear; they yield failed or unexecuted clauses and reject fatal gates.

`ContractQualityAssessment` records every clause result, every gate result, failed clauses,
unexecuted clauses, root failures, fatal gates, and the exact contract/runtime identities.

## Dual-Track Migration

Version 0.5 intentionally keeps the previous `CandidateQualityEvaluator`:

```text
Candidate
   |-> fixed evaluator -----------|
   |-> compiled Contract Runtime -|-> decision parity
```

This is a migration invariant, not two competing final architectures. Finance Pilot and the Legal /
Science Contract Suite run every clean and mutated candidate through both paths. Any decision
mismatch blocks the suite or Pilot. The fixed manifest can be removed only after sustained parity on
production candidates and after all required legacy semantics have native clause verifiers.

## Release Contract

A release with tasks must provide exactly one Quality Contract and one Proof Certificate per task.
The builder validates task coverage, duplicate identities, certificate-to-contract binding, and
domain provider identity. The immutable manifest freezes:

```text
Quality Contract compiler versions
Contract Runtime version
Clause verifier manifest hashes
all Quality Contract hashes
Proof-Carrying compiler versions
all Proof Certificate hashes
cross-domain Contract Runtime parity results
```

The cross-domain suite contributes its own Contract and Certificate hashes even when a release has no
explicit task payload, so architecture portability remains part of every release identity.

## Current Validation

The v0.5 small finance run on the immutable archive produced:

```text
compiled tasks                       24 / 24
accepted references                  24 / 24
accepted clean candidates            24 / 24
rejected counterfactual mutations   386 / 386
compiled Quality Contracts           24 / 24
compiled Proof Certificates          24 / 24
dual-track decisions matched        410 / 410
contract clause range                36..54
```

The Legal and Science Contract Suite produced two independent contracts and certificates, evaluated
two clean and fourteen mutated candidates, and achieved complete decision parity. These results
validate compiler/runtime portability for the controlled suite; they do not claim production-scale
legal/scientific data or real-agent quality.

## Deliberate Boundaries

This milestone does not implement:

```text
Task Pattern IR or automatic Evidence Binding
Contract-derived typed counterfactual generation
failure-closure calibration and minimality scoring
learned Contract-aware quality critics
dataset-level utility/diversity optimization
```

Those capabilities build on this contract DAG. They should not be added by expanding the fixed
manifest or by placing finance-specific logic in Core. The next method milestone is typed
counterfactual planning from clause targets and dependencies; Task Pattern IR remains a separate task
discovery concern.
