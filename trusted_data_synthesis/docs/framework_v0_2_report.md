# Trusted Synthesis v0.2 Framework Report

## 1. Purpose

This iteration removes the remaining finance-shaped assumptions from the core
and establishes enforceable separation between public tasks and hidden gold
contracts. The archived `raw_financial_data_lake` is unchanged and remains the
first read-only validation producer.

## 2. Implemented Changes

### Evidence IR v2

The scalar-only Evidence record is replaced by discriminated payloads:

```text
scalar_observation | textual_claim | rule_statement
relation_assertion | experimental_result | derived_result
```

Assertion identity and evidence-version identity are separate. Source location,
temporal validity, scope, epistemic status, semantic definition, and derivation
parents are represented explicitly.

### Proof Graph

The former generic `EvidenceGraph` is renamed and narrowed to `ProofGraph`.
Its edges make claim lineage executable:

```text
Subject -HAS_EVIDENCE-> Evidence -ASSERTS-> Predicate
Evidence -FROM_SOURCE-> Source
Evidence -IN_TIME-> Time
Evidence -APPLIES_TO-> Scope
Evidence -HAS_DEFINITION-> Definition
Evidence -DERIVED_FROM-> Parent Evidence
```

Tasks cannot be constructed unless all Oracle Evidence IDs occur in the pinned
Proof Graph.

### Task and Workflow Isolation

```text
TaskPublicSpec: instruction + tools + retrieval scope + answer schema
TaskOracleContract: gold evidence + Task Program + Proof Graph + rubric
```

Reference compilation can use the Oracle Contract. Candidate generation accepts
only the Public Spec and a search runtime. This boundary is enforced by the API
and covered by tests.

### Operation DAG and Independent Verification

Single-operation tasks have been replaced by Task Programs. A temporal-growth
task now executes:

```text
lookup earlier -> lookup later -> growth
```

Executors and Oracle Verifiers use separate modules and separate arithmetic
implementations. Mutated node outputs are rejected during independent replay.

### Quality and Release Contracts

Quality evaluation now separates fatal hard gates from diagnostic scores. It
also freezes a required-check manifest; absent checks fail closed. Semantic
cluster split policy and a release-manifest schema were added to prevent leakage
and make builds reproducible.

## 3. Cross-domain Validation

The same `lookup` Task Program and workflow compiler were exercised with:

- a finance scalar observation with fiscal scope and source definition;
- a legal rule containing conditions, exception, authority, legal effect, and
  effective date;
- a scientific experimental result containing method, comparator, sample size,
  and uncertainty interval.

No finance branch exists in the task compiler, operation registry, workflow
compiler, or quality evaluator.

## 4. Current Scope

Implemented in v0.2:

- Evidence IR v2;
- task-local Proof Graph;
- Public/Oracle split;
- operation DAG registry;
- independent Reference verification;
- public-only Candidate runtime boundary;
- hard-gate quality model;
- adapter capability manifest;
- independent domain semantic/task/verification plugin contracts;
- proof-subgraph extraction from a larger proof graph;
- release/split contracts.

Still intentionally deferred:

- domain-graph loaders and graph-pattern miners for finance, legal, and science;
- graph-pattern task mining;
- model-generated surface forms;
- production Candidate agents for multi-step programs;
- ten-class mutation suite and CI workflow;
- release selector and persistent build catalog.

These are extensions over stable v0.2 contracts rather than reasons to retain
the v0.1 interfaces.
