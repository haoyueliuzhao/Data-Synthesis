# Architecture v0.2

## Boundary

The active project is a domain-neutral trusted synthesis compiler. The archived
financial lake remains a read-only producer. Domain adapters map frozen producer
artifacts into shared contracts; they do not move domain normalization into the
core.

```text
Domain archive / domain KG
        -> Adapter capability plugins
        -> Evidence IR v2
        -> Task-local Proof Graph
        -> Public Task + isolated Oracle Contract
        -> Task Program DAG
        -> Reference Workflow / Candidate Workflow
        -> Independent Oracle Replay
        -> Hard Gates + Diagnostic Quality Vector
        -> Semantic-cluster Split + Release Manifest
```

## Evidence IR v2

Evidence is a versioned assertion, not a financial scalar. `payload.kind`
discriminates scalar observations, textual claims, rule statements, relation
assertions, experimental results, and derived results. Shared fields cover:

- generic subject and predicate;
- multi-axis temporal context;
- scope;
- source and exact source locator;
- semantic definition;
- archive/build lineage and parent evidence;
- epistemic status and extraction confidence.

Finance-specific fiscal, statement, market, and comparability fields live in
`domain_context`, `scope.attributes`, or definition attributes.

## Two Graphs

The framework distinguishes two graph layers:

1. **Domain Evidence Graph**: owned by the adapter/source domain. It supports
   discovery and domain-native relations.
2. **Task Proof Graph**: built from the selected Evidence Bundle. It records the
   exact subject, predicate, time, scope, definition, source, and derivation
   relations required to prove a task.

Task synthesis fails when a gold evidence item is absent from the Proof Graph.
The graph is therefore an executable contract, not an optional export.

## Public And Oracle Separation

`TaskPublicSpec` contains the natural-language instruction, answer schema,
allowed tools, and retrieval scope. It contains no gold evidence IDs or program.

`TaskOracleContract` separately contains gold Evidence IDs, the Task Program,
Proof Graph identity, and rubric. `CandidateTrajectoryGenerator.generate()`
accepts only `TaskPublicSpec` and an `EvidenceToolRuntime`; its API cannot accept
an Oracle Contract.

## Task Program

A Task Program is a topologically ordered operation DAG. Inputs can reference
versioned Evidence or earlier operation outputs. The registry currently includes
lookup, compare, difference, ratio, growth, and aggregate.

Executors and Oracle Verifiers are separate classes in separate modules. The
Oracle Verifier independently recomputes every node and never imports executor
logic. This prevents a shared implementation defect from validating itself.

## Workflows

- **ReferenceWorkflowCompiler** may read the Oracle Contract and produces a
  deterministic gold workflow with complete citations.
- **CandidateTrajectoryGenerator** searches through public retrieval constraints
  and never receives hidden IDs.

Both produce the same auditable trajectory schema, tagged by `workflow_kind`.

## Quality

Release decisions use fail-closed hard gates before weighted diagnostics:

- required-check manifest completeness;
- evidence structural validity;
- Proof Graph and citation coverage;
- independent program replay and final-answer agreement.

The diagnostic vector reports evidence validity, graph coverage, operation
replay, citation coverage, workflow completeness, and program depth. A missing
required check is equivalent to a failed check.

## Versioning And Split

Release manifests freeze Evidence, Proof Graph, Task Program, operation registry,
quality-check manifest, adapter capability, source build, and split policy
contracts. Split assignment hashes a semantic cluster composed of domain, task
type, subjects, predicates, and program identity so equivalent tasks cannot leak
across train/dev/test.
