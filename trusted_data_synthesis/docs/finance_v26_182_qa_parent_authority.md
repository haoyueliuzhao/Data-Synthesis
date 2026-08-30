# Finance v26.182 QA Parent Authority

Audit and implementation date: 2026-08-31

## Scope And Evidence Boundary

This change consumes the QA Parent Authority repair scope identified after the independent
v26.181 negative audit. It does not edit v26.181 source or any v26.167-v26.181 formal artifact.
It makes no Provider call and does not reinterpret the frozen failed v26.181 Gate. The exact
independent audit is documented separately in
`docs/finance_v26_182_authoritative_outcome_terminal_independent_audit.md`.

The implementation deliberately favors a strong v2 identity chain over serialization
compatibility with the first QA realization prototype. Historical `TaskPackage` files remain
readable and immutable; the new authoritative objects are content-addressed sidecars.

## Authoritative Parent Chain

The release-bearing chain is now:

```text
Operation Semantic Contract
  -> CanonicalSemanticPlan
  -> BindingSnapshot (embedded EvidenceBinding)
  -> SemanticInstance
  -> RealizedTaskPackage (embedded Plan, BindingSnapshot, Instance, Surface, Task)
  -> RealizationPortfolio
  -> RealizationExecutionBinding
  -> content-addressed QualityAssessment
  -> ReleaseWeightAssignment
  -> DiversityAwareReleaseSelection
```

Every persisted child validator revalidates embedded Pydantic parents from ordinary Python data.
This is intentional: a parent inserted with `model_construct()` does not become authoritative by
being nested inside a frozen child. The child recomputes every content identity before accepting
the object.

### Operation Semantic Contract

Each Registry definition now has a strict canonical semantic-contract hash covering operator and
verifier identities, input/output schemas, compatibility and invariant rules, output model JSON
Schema, action and execution semantics, program role, role/parameter/downstream contracts, input
order, executor/verifier/semantic versions, formula, rounding, and tolerance policy.

`CanonicalProgramNode` carries both that semantic-contract hash and the implementation hash. The
semantic Program identity includes the former. The Plan identity additionally persists the
implementation hash and exact source Program ID/hash. An implementation-only refactor can
therefore retain semantic equivalence while still producing a new exact Plan identity; a formula,
version, compatibility, or schema change produces a new semantic identity.

### Semantic Instance

`semantic_task_id` remains the renderer-free schema identity. It is no longer used as the concrete
split, quota, or weight parent. `SemanticInstance` is the exact binding-level parent:

```text
semantic_instance_id = H(semantic_task_id, binding_snapshot_id, schema_version)
```

The object also carries the exact Plan ID and validators require the Plan, Snapshot, and Instance
lineage to agree. Sibling surface realizations share one Instance; different evidence bindings of
the same semantic schema do not.

### Realized Task Content Identity

`RealizedTaskPackage` v2 embeds and validates the exact Plan, BindingSnapshot, SemanticInstance,
SurfaceRealization, and realized `TaskPackage`. Its identity is the canonical hash of all of that
content. Validation additionally checks:

- source Program ID and Program hash against the Plan;
- public domain, task type, retrieval track, planning track, and declared Answer Schema;
- exact Evidence set and cardinality against the BindingSnapshot;
- ProofGraph ID/hash;
- the compiler's Pattern Binding ID, hash, and exact role assignments;
- realized task ID/hash against the SurfaceRealization.

An arbitrary `semantic_plan_id` string is no longer a parent. A stale package ID, a forged Plan,
or a sibling BindingSnapshot fails validation even when the nested object was produced with
`model_construct()`.

## Evaluation And Release Authority

`QualityAssessment` v2 is content-addressed over gates, diagnostic values, dimensions, decision,
failure details, evaluator version, task ID, and trajectory ID. It also exposes a separate full
assessment content hash. Changing a decision or any score while retaining the old assessment ID
is rejected.

`RealizationExecutionBinding` binds one portfolio-selected realized package to:

```text
semantic schema / SemanticInstance / BindingSnapshot
realized package / realization / realized task hash
embedded RealizationPortfolio and portfolio ID
trajectory ID and content hash
QualityAssessment ID and content hash
evaluator contract ID
```

The release selector consumes a four-object record, recomputes the Execution Binding from the
other three objects and its embedded Portfolio, and requires exact equality. A trajectory and
assessment from one same-`task_id` surface sibling can no longer be substituted for another
sibling.

Release policy v2 applies quotas separately to `semantic_instance_id` and semantic schema. Split
assignment hashes `semantic_instance_id`. Every selected child gets an explicit immutable
`ReleaseWeightAssignment` containing numerator, denominator, reduced exact Fraction text,
package/realization/execution IDs, and release-plan ID. Selection validation requires one
assignment per selected child and recomputes each Instance sum with `fractions.Fraction`; deleting
one child weight or retaining a stale denominator fails closed.

## Verification At The Parent-Chain Checkpoint

The checkpoint used no network or Provider. Results before the subsequent source-root and Pilot
integration work were:

```text
focused QA realization tests                         9 passed
QA + release + task-pattern adjacent tests          22 passed
Ruff over all changed source and QA test files       passed
Mypy over 9 changed source modules                   passed
Python byte compilation                              passed
```

Registered negative controls at this checkpoint include nested forged-Plan injection,
BindingSnapshot/EvidenceBinding crossing, invalid SurfaceRealization content, same-`task_id`
sibling Execution Binding substitution, and deletion of one exact child-weight assignment.

These are engineering controls. They do not establish empirical model quality, production
Contribution, training authorization, or release authorization. Those remain gated by the final
credential-free Parent Authority preflight and Finance Pilot portfolio integration described in
the completion section appended after those stages run.
