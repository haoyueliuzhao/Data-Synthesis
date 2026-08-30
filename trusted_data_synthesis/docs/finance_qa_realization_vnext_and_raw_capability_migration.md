# Finance QA Realization vNext And Raw Capability Migration

Audit date: 2026-08-30

## Decision And Scope

This engineering stage implements the audit-directed QA synthesis redesign as an independent,
credential-free `qa_realization_vNext` path. It does not modify any v26.167-v26.181 task,
Population, Job, Runner, model outcome, terminal, or formal evidence identity.

The bound external audit is exactly 28,811 bytes with SHA-256
`1c74b70688123962672cf6d5cda0e7932269880ddb77216860dc0c524b2eb811`. The implementation
starts from commit `a934a7557caab65cf7f4e6bc65fa87222a2d7461`.

The stage reads the following Raw modules only as implementation references:

```text
raw_financial_data_lake/finraw/qa/graph_patterns.py
  SHA-256 763f52bcb391b1678f8833fda8662f20f08c3abf549550f07f2e3cb48bd007c7

raw_financial_data_lake/finraw/qa/verbalizer.py
  SHA-256 07c039be67fe52416e4978904582fbb0bbfa4a22b46578863d10f71296c3d213

raw_financial_data_lake/finraw/qa/diversity.py
  SHA-256 001d21ec74d5641d2e085cee547fef2311638a9fc5d2a3a298c34fcd76a8c385
```

No Raw QA candidate, sample, answer, split, or release row is imported. Provider-client
construction, Provider calls, Stage 2 calls, GPU jobs, online QA generation, model outcomes,
Mapper, State Assignment, frequency, Contribution, VTDO, Student visibility, training, release,
and production counts are zero.

## Three-Layer Identity Closure

The old `TaskPackage`, `TaskPublicSpec`, `TaskPatternSpec`, and `task_id` schemas remain unchanged.
Adding defaulted fields to those frozen models would change historical serialization and
`task_hash`, so vNext uses content-addressed sidecar objects instead.

### Semantic Task Identity

`SemanticTaskProposal` is renderer-free and records:

```text
proposal source
domain / task family / task type
typed Evidence roles and cardinalities
Operation templates
Answer Schema
retrieval and planning tracks
semantic constraints
question intents
mechanism contract
```

`CanonicalSemanticPlan` is compiled from a concrete authorized Program while removing local node
IDs and exact Evidence IDs. Operation dependencies are represented by structural node hashes.
Evidence inputs are represented by declared role and role position. Inputs to an Operation whose
Registry definition is `permutation_invariant` are sorted before hashing. The Plan retains both:

```text
program_topology_hash
parameterized_program_hash
```

The `semantic_task_id` binds the parameterized Program, Evidence-role semantics, Answer Schema,
retrieval/planning tracks, semantic constraints, and mechanism contract. It does not bind a
Renderer ID, final instruction, concrete Evidence ID, or migration provenance label.

A focused control changes only `instruction_renderer_id`. The two Proposal IDs differ because
their source artifacts differ, while their `semantic_task_id` and parameterized Program hash
remain equal. This preserves provenance without treating a rewrite as a new semantic task.

### Binding Snapshot Identity

`BindingSnapshot` binds one Semantic Task to:

```text
exact role -> Evidence ID assignments
Evidence Version IDs
source record IDs
source build/snapshot IDs
EvidenceBundle ID and hash
ProofGraph ID and hash
KG build ID
```

Every exact Evidence item must exist in both the supplied Bundle and ProofGraph. Duplicate
Evidence IDs, Evidence/Version cardinality drift, graph mismatch, and content-address mismatch
fail closed.

### Surface Realization Identity

`SurfaceRealization` binds:

```text
semantic_task_id
binding_snapshot_id
legacy task_id
Renderer profile ID and hash
Question Contract ID
language and style
protected public slots and variant IDs
protected template and normalized skeleton
final instruction
rewrite version
realized TaskPackage hash
```

Every Realization preserves the `task_id` produced by the current compiler; alternate
instructions produce distinct `task_hash` and `realization_id`. For the same current source and
binding inputs, the canonical profile reproduces the pre-refactor instruction, `task_id`, and
`task_hash`. This gives Split, Release, and training-weight logic an explicit parent without
rewriting immutable package identities.

This is deliberately not stated as a reconstruction of the frozen v06 package hashes. Rebuilding
the exact fifty v06 task contexts with unmodified `main` and with this branch produces the same
current-compiler root,
`rebuilt_v06_root:e5e08b6ba8517271c12c109b95a137d663760970999550b1a7c7f8d403aa3e01`,
but both current trees match zero of fifty frozen v06 package hashes because the compiler and
Runtime metadata evolved after that artifact was created. The branch changes no frozen v06 file
and neither introduces nor repairs that pre-existing historical drift.

## Deterministic Renderer Portfolio

The seven hard-coded Finance instruction branches now resolve their canonical instruction through
a versioned `RendererRegistry`. The old Renderer IDs remain the canonical profile IDs. One newly
authorized Raw-derived task type is also registered.

The exact manifest contains:

```text
task types                                      8
profiles per task type                          4
total Renderer profiles                        32
languages                                       1 (English)
styles          canonical / concise / analyst / evidence_explicit
```

Each Profile declares exact protected slots, optional slots, operator cues, source requirement,
response form, intent, language, style, and rewrite version. A Profile fails construction when it
has a missing, extra, or duplicate placeholder; an unprotected number; a missing operator cue; a
forbidden semantic extension; or punctuation inconsistent with question/directive form.

For one Binding, the current implementation materializes all four valid candidates and uses a
deterministic coverage selector to retain at most three. Selection occurs only after every hard
Question Contract Gate passes. Each selected child receives weight `1 / child_count`, so all
siblings sum to one parent-task weight. Evaluation can continue to retain only the canonical
Realization.

Renderer manifest SHA-256:
`57d32c5b5bba22811d702696d4883e0f10c72f7192cc3befefcc2a0410722948`.

## Protected Rewrite Migration

The high-value Raw protected-placeholder contract is migrated without activating an LLM. The
strict validator accepts exactly:

```json
{
  "rewrite_version": "protected_question_rewrite.v1",
  "question_template": "..."
}
```

It rejects:

```text
non-object payload
missing or extra top-level fields
rewrite-version drift
missing, extra, or duplicate protected placeholders
unprotected numeric literals
multiple or absent questions
forecast, prediction, causal, or investment-advice extensions
```

Rendering then replaces only registered public slots. Numeric grounding requires every numeric
token in the final instruction to originate in a registered slot. The Provider-facing repair
loop, telemetry, and optional controlled LLM invocation remain deferred; this stage makes zero
Provider calls and does not claim semantic equivalence for free paraphrases.

## Raw GraphPattern Migration

Three audit-priority Raw Graph Patterns are translated into current `SemanticTaskProposal`
objects. Proposal manifest SHA-256 is
`f5a180fd18d75e11a51305e87bdb33ef08a3370b2e081c64efa110b1e5c52635`.

| Translated task type | Proposal ID suffix | Current decision | Exact reason |
| --- | --- | --- | --- |
| `registered_cross_metric_comparison` | `66126c...cac7` | authorized | exact Role, DAG, parameter, answer, semantic, Renderer-intent, Quality, Policy, Executor, and Oracle contracts close |
| `temporal_peak_secondary_lookup` | `878299...b3b1` | blocked | `argmax` and `select_by_period` are absent from the current Registry |
| `growth_filter_margin_rank` | `fc5af8...60ead` | blocked | `growth_by_entity`, `filter`, `ratio_by_entity`, `intersect_on_entity`, and `rank` are absent |

The complete identities are:

```text
semantic_task_proposal:66126ce110a65bd7a0fa1791a38f0dfaf0a09a14fd8656508851a818f550cac7
semantic_task_proposal:8782995821998354f8f5839a2f91c3691aced10e9ece00c4d42118741c12b3b1
semantic_task_proposal:fc5af82b9a609b9b1b28c840d9c17a151d628092b283aebf0550b3dc80360ead
```

The authorized cross-metric path adds a Finance-vNext `registered_compare` Operation. It reuses
the deterministic Compare Executor and an independently implemented Compare Oracle Verifier, but
uses a new compatibility policy. The exact binding must provide a registered ordered metric pair
and preserve:

```text
distinct metrics
same subject
same temporal identity
same scope identity
same source
same payload context, including unit and currency
non-empty and compatible source definitions
same statement type
same metric period type
historical, non-forecast Evidence
```

The first registered pairs are revenue/gross profit, revenue/operating income, revenue/net income,
total assets/total liabilities, current assets/current liabilities, and operating cash flow/net
income. An unregistered pair or any public context drift rejects before Task materialization.

Authorization separately matches the translated Role contract, Operation DAG, dynamic parameter
contract, Answer Schema, semantic constraints, Renderer intents, and Quality profile against the
current TaskPattern. No matching dimension is inferred from task-type equality alone.

The other two Proposals remain useful, content-addressed migration inputs, but they cannot produce
a TaskPackage, empirical denominator, or training row. Missing Operation names are explicit and
cannot be compensated by Renderer coverage or proposal novelty. Their blocked proposal objects
nevertheless preserve the Raw contracts exactly: temporal lookup retains `unit` and `currency`,
and the rank proposal retains `normalized_value > 10` plus `top_k=3`.

Raw migration audit identity:
`raw_proposal_migration_audit:a39fe7baa8a32a13f3ea4887b03a387c2a154b16542e4f4ff5a1d66159028d17`.

## QA Chain Integration

`FinanceTaskPlugin.materialize_evidence_ids()` now owns generic Pattern-role binding:

```text
one declared role       -> complete ordered Evidence tuple
N single-value roles    -> declaration-order one-to-one binding
registered pair task    -> exact predicate pair derived from bound Evidence
```

`finance_pilot/task_factory.py` no longer contains a seven-way `if/elif` Task dispatch. It sends
the selected `task_type` and Evidence IDs through the unified plugin entry. Existing public task
methods remain available and existing Pilot behavior is byte-stable under the canonical profiles.

The Sampler adds a separately typed cross-metric binding source. It groups only exact shared
subject/period/scope/source/payload contexts, applies `FinanceSemanticPolicy`, and adds
`raw_static_graph_pattern` plus the exact registered pair to its stratum. Existing fact strata
remain unchanged.

## Split And Release

`assign_semantic_parent_split()` hashes `semantic_task_id`, not final instruction or
Realization ID. `assign_realization_split()` delegates to that parent key. All sibling
Realizations therefore inherit one split by construction.

The existing `select_candidate_release()` remains unchanged. A new
`select_diversity_aware_release()` API consumes exact `(RealizedTaskPackage, Trajectory,
QualityAssessment)` triples and applies this order:

```text
identity equality
Realization Contract pass
Quality decision == accepted
duplicate rejection
Semantic Parent quota
deterministic coverage gain minus lexical similarity penalty
parent-weight conservation
Semantic Parent split assignment
```

Rejected or quarantined rows contribute only failure diagnostics. A novel Skeleton cannot rescue
an invalid Realization or failed Quality assessment.

## Read-Only v06 Census

The P0 Census reads only the immutable 50-row
`artifacts/finance_pilot/v06_pattern_50/task_packages.jsonl` input from the canonical repository.
It writes no predecessor file and makes zero Provider/GPU calls.

Exact results are:

```text
TaskPackages                                      50
inferred Semantic Parents                         4
Binding Snapshots                                 50
Surface Realizations                              50
Program topologies                                 4
Parameterized Programs                             4
Answer Schemas                                     4
Operator bigrams                                   3
Normalized question Skeletons                      4
largest Program-topology share                  0.26
largest Skeleton share                          0.26
Skeleton entropy                         1.998845535995 bits
NMI(Task Family; Skeleton)                       1.0
H(Skeleton | Task Family)                        0.0 bits
Retrieval track                            resolved: 50
Planning track                           plan_given: 50
Realizations per exact Binding                    1 / 1 min/max
Slot variants                       legacy_canonical: 50
Lexical near-duplicate clusters                     4
largest lexical near-duplicate cluster             13
sibling Semantic Parents                          4
cross-split sibling leakage                       0
```

This exactly confirms the audit's narrow Pilot diagnosis: the 50 rows contain many fact bindings,
but every exact Binding has only one legacy-canonical Realization and each of the four Task
Families maps to one normalized Skeleton. The Census identity binds the exact ordered row
manifest at
`qa_census_row_manifest:252af8906787670058abf775be880bad4c2b123ae3485d3bc29896e682ec484d`.
It does not establish a repository-wide maximum Skeleton share because v26 catalogs and Raw QA
artifacts are outside this exact run.

Census identity:
`qa_diversity_census:f2b54aa6a4a89eaa91f4917e2b5fca655d9fa6b5556de3740285b18ff2c16b04`.

## Formal Artifacts

The new artifact directory contains fourteen files and 170,173 exact bytes:
`artifacts/qa_realization_vnext/v1`.

Core hashes are:

```text
preflight report SHA-256
  90b78647e1439d6597aa347512a34f6447edd1954d7b3041aedb0ce3937df82a

census report SHA-256
  b8557f557990c581f17e145509e3a907a65b02dad74557e8ff158b380052d49d

Raw proposal migration audit SHA-256
  eef8f1d1eaf95779c93e682b404068b259a1fa712ec816efa5e6083327923673

QA realization contract SHA-256
  c6ecf6866880da9a6bfdcf3f80d98f6a065152dcbea77133bdd5ec6861a0d196
```

The authoritative preflight identity is:

```text
qa_realization_vnext_preflight:051ffecc83238a3a85e3309fd264f4034b7be17b8f23fa516140bc298acd3614
```

All thirteen preflight Gates pass. Provider call, GPU job, imported Raw QA row, and frozen v26
artifact mutation counts are zero.

## Verification

Focused QA vNext tests pass 9/9. They cover:

```text
three-layer identity and current-compiler canonical identity/hash preservation
renderer exclusion from semantic identity
protected rewrite slot/numeric/semantic-extension rejection
Raw Proposal authorization and exact current-contract matching
faithful blocked-Proposal threshold, top-k, and answer-field retention
Binding/Realization stale-identity rejection
registered cross-metric execution and independent Oracle verification
unregistered cross-metric rejection
Semantic Parent split and parent-weight conservation
realization-local trajectory/Quality evaluation and foreign-task rejection
read-only Census artifact materialization
weighted near-duplicate cluster counting and row-manifest binding
```

The selected adjacent Task, Finance Pilot, Release, Operation, and Workflow suite passes 47/47.
The expanded suite including Generalization reports 49 passed and three failed; all three retain
one pre-existing diagnostic in the unchanged v26.181 file
`runtime/agent/prospective_two_stage_exact_response_grammar.py:424`. The same diagnostic is
independently reproduced on unmodified `main`; it is not introduced or repaired by this branch.

Focused PyCompile, Ruff check, Ruff format, and Mypy pass after final formatting. Package-wide
Ruff passes. Package-wide Mypy checks 585 source files and retains six diagnostics in four frozen
historical files, with zero diagnostics in the new or modified QA-vNext modules. The optional
Finance archive adapter test cannot collect in this environment because `pyarrow` is not
installed; no dependency is installed or compatibility claim inferred from that unrun test.

## Scientific Boundary And Next Work

This stage supports deterministic identity closure, protected public-slot rendering, one
re-authorized cross-metric Program family, explicit fail-closed Proposal compatibility, parent
split inheritance, valid-pool portfolio selection, and a scoped descriptive diversity baseline.

It does not support claims about model readability, model success, semantic equivalence of free
paraphrases, embedding diversity, repository-wide QA diversity, unrestricted task distributions,
VTDO State support, or training improvement.

The next safe work is credential-free and should proceed one boundary at a time:

```text
1. extend the read-only Census to explicitly selected v26 and Raw artifact schemas;
2. add and independently verify argmax/select_by_period Operation Contracts;
3. add and independently verify entity-table growth/filter/ratio/intersection/rank Contracts;
4. only after deterministic Profiles remain stable, preflight controlled Provider rewrite;
5. pre-register Release diversity thresholds from a larger frozen Census before production use.
```

Provider rewrite execution, automatic mined-Pattern publication, typed-walk publication, blocked
Proposal Task materialization, online QA generation, training, and production release require a
separate explicit authorization and fresh identities.
