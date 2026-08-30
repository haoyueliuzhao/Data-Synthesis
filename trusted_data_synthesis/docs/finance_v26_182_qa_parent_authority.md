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

## Completion Gate And Finance Pilot Integration

The Finance Pilot factory now retains the full `FinanceRealizationCompilation` for every exact
Evidence Binding while preserving the canonical Task projection used by existing reference
quality machinery. The Pilot Runner additionally evaluates all three portfolio-selected surfaces.
It derives a distinct trajectory identity from the realized-package identity and generated
trajectory hash, content-addresses each assessment, constructs an Execution Binding, and runs the
instance-level diversity release. Pilot artifacts now include the portfolios, selected realized
packages, realized candidate workflows, assessments, Execution Bindings, and release selection.

The final credential-free Gate binds exact source commit
`e0581f17f69484dd4e49311908e766bed5ccbd97`, fifteen implementation Git blobs, and the actual
working-tree bytes. Its source Root is
`qa_parent_source_root:a7428b375c620ce301650fbe2bcce79907a525f5b51f067a693dc5087c02b847`.
It separately re-reads and hashes the three Raw reference files; their Root is
`qa_raw_reference_root:8324c964591c30eae2090847d81eff826a27f20e503ae11afa2543a897f132d7`.
The new external review is exactly 31,266 bytes with SHA-256
`f89dce636bb7176e4dea9466fb794cccdfc6d73d1f4b79578bcef6090b3f2557`.

The Gate uses two concrete Evidence bindings of the same semantic schema. They produce two
distinct SemanticInstances, proving that an abstract schema no longer consumes one instance
quota. The primary Instance produces three valid packages and accepted assessments; a policy cap
selects two, persists two `1/2` assignments, and verifies an exact Fraction sum of one.

All seventeen hard Gates pass and all eleven registered attacks reject:

```text
Operation semantic-version mutation
forged Plan through model_construct
forged BindingSnapshot through model_construct
same-task-id sibling execution substitution
stale assessment content hash
deleted child weight assignment
abstract schema used as instance quota
mutated source bytes
mutated Raw bytes
arbitrary 40-character Git identity
existing artifact-directory overwrite
```

Formal report identity:
`qa_parent_authority_preflight:843be597c47077eeb713f536d9f2530dbf6038cf594f833940b55ce3ed3ef355`.
Release selection identity:
`diversity_aware_release_selection:e41a702c12f578767334cb7d34d7a6011dac6d9aa10170721d2d50713620d894`.
The deterministic eleven-file formal set is 84,289 bytes with artifact Root
`qa_parent_authority_artifact_root:1e0d6eed4578d8b59e6bbdfb62c462f3b5c5d01ff0ca33912211f1e52cf2247a`.
An independent same-source rebuild matches all eleven files byte for byte.

The earlier immutable `parent_authority_v1_20260831` directory remains unchanged. Its Gates were
correct, but one attack detail embedded a randomized temporary path, so its 85,530 bytes are not a
byte-reproducible formal endpoint. The deterministic error-category repair is source-bound and
published only under the new `parent_authority_v2_20260831` identity; nothing overwrites v1.

The final adjacent suite passes 53 tests. The formal stage has zero Provider calls, zero GPU jobs,
zero imported Raw QA rows, and zero historical artifact mutations. It authorizes the corrected
credential-free QA parent chain and Finance Pilot portfolio plumbing only. It does not authorize
Provider generation, production release, training, Contribution, VTDO State, or any
reinterpretation of the independently frozen failed v26.181 empirical Gate.

## Completion Gate And Finance Pilot Integration

The Finance Pilot factory now retains the full `FinanceRealizationCompilation` for every exact
Evidence Binding while preserving the canonical Task projection used by existing reference
quality machinery. The Pilot Runner additionally evaluates all three portfolio-selected surfaces.
It derives a distinct trajectory identity from the realized-package identity and generated
trajectory hash, content-addresses each assessment, constructs an Execution Binding, and runs the
instance-level diversity release. Pilot artifacts now include the portfolios, selected realized
packages, realized candidate workflows, assessments, Execution Bindings, and release selection.

The final credential-free Gate binds exact source commit
`e0581f17f69484dd4e49311908e766bed5ccbd97`, fifteen implementation Git blobs, and the actual
working-tree bytes. Its source Root is
`qa_parent_source_root:a7428b375c620ce301650fbe2bcce79907a525f5b51f067a693dc5087c02b847`.
It separately re-reads and hashes the three Raw reference files; their Root is
`qa_raw_reference_root:8324c964591c30eae2090847d81eff826a27f20e503ae11afa2543a897f132d7`.
The new external review is exactly 31,266 bytes with SHA-256
`f89dce636bb7176e4dea9466fb794cccdfc6d73d1f4b79578bcef6090b3f2557`.

The Gate uses two concrete Evidence bindings of the same semantic schema. They produce two
distinct SemanticInstances, proving that an abstract schema no longer consumes one instance
quota. The primary Instance produces three valid packages and accepted assessments; a policy cap
selects two, persists two `1/2` assignments, and verifies an exact Fraction sum of one.

All seventeen hard Gates pass and all eleven registered attacks reject:

```text
Operation semantic-version mutation
forged Plan through model_construct
forged BindingSnapshot through model_construct
same-task-id sibling execution substitution
stale assessment content hash
deleted child weight assignment
abstract schema used as instance quota
mutated source bytes
mutated Raw bytes
arbitrary 40-character Git identity
existing artifact-directory overwrite
```

Formal report identity:
`qa_parent_authority_preflight:843be597c47077eeb713f536d9f2530dbf6038cf594f833940b55ce3ed3ef355`.
Release selection identity:
`diversity_aware_release_selection:e41a702c12f578767334cb7d34d7a6011dac6d9aa10170721d2d50713620d894`.
The deterministic eleven-file formal set is 84,289 bytes with artifact Root
`qa_parent_authority_artifact_root:1e0d6eed4578d8b59e6bbdfb62c462f3b5c5d01ff0ca33912211f1e52cf2247a`.
An independent same-source rebuild matches all eleven files byte for byte.

The earlier immutable `parent_authority_v1_20260831` directory remains unchanged. Its Gates were
correct, but one attack detail embedded a randomized temporary path, so its 85,530 bytes are not a
byte-reproducible formal endpoint. The deterministic error-category repair is source-bound and
published only under the new `parent_authority_v2_20260831` identity; nothing overwrites v1.

The final adjacent suite passes 53 tests. The formal stage has zero Provider calls, zero GPU jobs,
zero imported Raw QA rows, and zero historical artifact mutations. It authorizes the corrected
credential-free QA parent chain and Finance Pilot portfolio plumbing only. It does not authorize
Provider generation, production release, training, Contribution, VTDO State, or any reinterpretation
of the independently frozen failed v26.181 empirical Gate.
