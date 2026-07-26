# Architecture Adjustment and Migration Plan

## Completed Adjustment

The repository is split by responsibility rather than by historical pipeline
stage:

```text
Archive producer: raw_financial_data_lake
Active consumer:  trusted_data_synthesis
```

No archive code or data was moved. This avoids breaking 36 GB of raw objects,
existing PostgreSQL build identities, 4.7 GB of KG exports, and historical QA
audit artifacts. The active framework consumes one explicitly pinned,
quality-passed KG build through a read-only adapter.

## Reuse Matrix

| Existing finance capability | New treatment |
| --- | --- |
| Source connectors and raw storage | Remain archived; not generalized |
| Entity and metric normalization | Remain Finance Adapter inputs |
| Standardized graph-ready facts | Map to shared EvidenceItem |
| Finance KG nodes and edges | Source for Evidence Graph construction |
| Derived facts and QA operation plans | Future task-pattern inputs |
| QA evidence and quality checks | Design reference, not imported runtime code |
| LLM rewrite and judge clients | Deferred behind core deterministic gates |

## Active Module Ownership

```text
core/evidence      universal assertion and provenance contracts
core/graph         universal evidence graph and reasoning paths
core/task          public instruction plus hidden executable contract
core/trajectory    auditable action trace and deterministic replay
core/evaluation    weighted quality dimensions and release decision
domains/finance    read-only archived-finance mapping
domains/science    next domain extension point
```

## Compatibility Contract

The Finance Adapter currently pins:

```text
archive adapter:       finance_archive.v1
KG build:              kg_20260711_062123_bc4b4394
graph schema:          3.0
KG quality gate:       passed
accepted fact status:  single_source or cross_verified
forecast policy:       excluded
```

Every emitted Evidence ID includes the KG build ID. This makes a future archive
refresh a new immutable evidence release rather than an in-place update.

## Current End-to-End Capability

The MVP executes:

```text
Archived graph-ready Fact
-> Finance Adapter
-> Evidence Bundle
-> Evidence Graph
-> Retrieval or Comparison Task
-> Deterministic Trajectory
-> Independent Operation Replay
-> Five-dimension Quality Assessment
```

The framework already accepts a science Evidence object through the same core
pipeline, demonstrating that task, trajectory, and quality code is not finance
specific.

## Deliberately Deferred

The following should not be copied wholesale from the archive:

- raw acquisition and document parsing;
- finance-specific metric comparability policies;
- historical QA tables and templates;
- LLM rewrite prompts and provider secrets;
- large JSONL query serving.

They will be integrated through interfaces only when needed.

## Next Build Order

1. Add an operation registry for ratio, growth, aggregation, filtering, and ranking.
2. Import selected DerivedFact and Scope graph structures into generic derivations.
3. Add graph-pattern Task mining and task-level evidence completeness gates.
4. Add an isolated tool runtime for replayable search and calculation trajectories.
5. Add release storage, split leakage controls, and quality-aware selection.
6. Implement a small science adapter and cross-domain transfer experiment.

LLM generation should enter only after deterministic task and trajectory
contracts are stable. It may diversify instructions or propose plans, but it may
not create unbound evidence, operations, values, or conclusions.
