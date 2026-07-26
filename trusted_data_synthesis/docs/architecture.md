# Architecture

## Positioning

The active project is a trusted training-data synthesis framework, not a second
financial data lake. Finance is the first domain adapter and validation domain.
The framework owns Evidence, Task, Trajectory, and Quality contracts; it does
not own SEC, FRED, CNInfo, financial normalization, or finance KG construction.

## Project Boundary

```text
raw_financial_data_lake/            trusted_data_synthesis/
-------------------------           -----------------------
raw objects                         domain-neutral contracts
canonical finance entities          evidence graph
metric ontology                     task synthesis
standardized facts        ------>   trajectory generation
versioned finance KG       read      independent verification
historical QA builds       only      quality-aware release
```

The only supported handoff is a frozen, quality-passed archive artifact. The
active project never imports `finraw` modules and never writes into the archive.

## Core Objects

### Evidence

An Evidence item represents one verifiable assertion in any domain:

```text
Entity + Property + Value + Time + Source + Definition + Provenance
```

Finance maps Company/Metric/Fact into these fields. A future science adapter can
map Paper/Experiment/Result without changing Task or Quality code.

### Evidence Graph

Evidence is connected to Entity, Property, Source, and Time nodes. Derivation
and Scope nodes are first-class extensions. Graph identity is content-addressed,
so paths and tasks can bind to a stable graph version.

### Task

Task is separate from answer realization. It contains a public instruction and
a hidden contract: Evidence Bundle, operation, answer schema, and requirements.
The MVP supports direct retrieval and comparable-evidence comparison.

### Trajectory

A trajectory stores an auditable workflow:

```text
Plan -> Search -> Select Evidence -> Calculate -> Verify -> Answer
```

It stores actions, tool inputs, observations, evidence IDs, and concise
rationale summaries. It deliberately does not persist hidden chain-of-thought.

### Quality

Quality is evaluated on five independent dimensions:

```text
Evidence 30% + Reasoning 20% + Tool Use 15% + Verification 20% + Answer 15%
```

Evidence and answer correctness are fail-closed. Operation results are replayed
with deterministic arithmetic rather than accepted from the generator.

## Evolution

1. Current: schemas, Finance Adapter, deterministic retrieval workflow.
2. Next: operation registry, graph-pattern task mining, trajectory tool runtime.
3. Then: science adapter and cross-domain contract tests.
4. Later: model-generated surface forms and trajectories behind deterministic gates.
