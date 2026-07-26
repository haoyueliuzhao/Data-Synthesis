# Architecture v0.3

## Boundary

`trusted_data_synthesis` is the active domain-neutral compiler. The archived
`raw_financial_data_lake` remains a read-only producer. Domain adapters map
immutable producer artifacts into shared contracts and never move acquisition or
domain normalization into the core.

```text
Domain archive / KG
        -> Domain Adapter
        -> Evidence IR v2 + executable semantic policy
        -> Proof Graph v3 + content validation
        -> Public Task / isolated Oracle Contract
        -> Task Program DAG v2
        -> Reference Compiler | Candidate Agent
        -> Independent replay and candidate reconstruction
        -> Separate hard-gate evaluators
        -> Candidate-aware release selector
        -> Semantic-cluster split + immutable manifest
```

## Evidence And Corpus

An `EvidenceItem` is a versioned assertion. Discriminated payloads support scalar
observations, textual claims, legal rules, relations, experiments, and derived
results. Subject, predicate, temporal context, scope, source, semantic definition,
epistemic status, archive lineage, and derivation parents remain explicit.

`EvidenceCorpus` is distinct from a task-local bundle and may contain distractors.
Public tasks declare either a `resolved` or `open` retrieval track. The current
deterministic candidate supports the resolved track; the contract leaves open-track
entity resolution and search to future production agents.

## Proof Graph v3

The Proof Graph is a verifier-facing proof object, not a query-serving domain KG.
In addition to Subject, Predicate, Evidence, Source, Time, Scope, and Definition,
v3 represents `SourceLocator` as a first-class node:

```text
Subject -HAS_EVIDENCE-> Evidence -ASSERTS-> Predicate
Evidence -FROM_SOURCE-> Source
Evidence -LOCATED_AT-> SourceLocator
Evidence -IN_TIME-> Time
Evidence -APPLIES_TO-> Scope
Evidence -HAS_DEFINITION-> Definition
Evidence -DERIVED_FROM-> Parent Evidence
```

`ProofGraphValidator` checks exact Evidence payload/version identity, mandatory
relations, locator payload binding, and DerivedResult parent consistency. The
recursive extractor follows derivation/support/qualification/contradiction edges
and then restores every discovered Evidence node's semantic neighborhood. Oracle
contracts bind both `proof_graph_id` and `proof_graph_hash`.

## Public And Oracle Separation

`TaskPublicSpec` exposes instruction, requirements, allowed tools, retrieval track,
retrieval scope, and answer schema. It contains no gold Evidence IDs or program.
`TaskOracleContract` separately pins Evidence IDs, Task Program, Proof Graph ID and
content hash, and the rubric. Candidate APIs cannot receive the Oracle type.

## Operation Contract

Task Program v2 is a topologically ordered DAG. `ProgramInputRef.selector` makes
cross-node field selection explicit. Every operation freezes:

```text
operator and verifier IDs
input and output schemas
compatibility and invariant policies
executor/verifier/semantic versions
formula, rounding, and tolerance policies
executor + verifier implementation hash
```

Execution and oracle replay both validate the node contract, input cardinality and
type, evidence-lineage compatibility, and output structure. Failures become
node-addressed `ProgramExecutionError` records. Executor and Oracle Verifier
implementations remain separate.

## Domain Runtime

Core structural validation is composed with executable domain policy. Finance v1
checks scalar shape, units/currency, historical status, time basis, frequency,
scope, source definition, and cross-fact comparability. `FinanceClaimVerifier`
permits only bounded structured claims and rejects ungrounded causal, forecast, or
investment claims. Legal and Science currently prove schema portability through
lookup tasks only; complex rule application and evidence synthesis remain future
work.

## Candidate-Centered Quality

Reference and Candidate quality are deliberately separate:

```text
ReferenceQualityEvaluator
  certifies the deterministic compiler and independent oracle replay

CandidateQualityEvaluator
  reconstructs retrieval, selection, calculation, answer, citation, and claims
```

Candidate hard gates cover public-only generation, allowed tools, retrieved
Evidence validity, recall and precision, operation correctness, Proof Graph hash,
answer schema and value, exact source/locator citation binding, domain claims, and
oracle leakage. Each task family has a frozen required-check manifest. Missing
checks are ordinary failed gates, never dictionary exceptions.

## Release And Split

Split fields are executed from `SplitPolicy.cluster_fields`. Program clustering
uses an Evidence-ID-independent semantic hash, while instance identity retains
versioned Evidence IDs. `CandidateReleaseSelection` publishes only accepted
trajectories and records assessment IDs, failure distribution, domain/task
distribution, and split counts. Release manifests freeze both Reference and
Candidate check manifests plus operation implementation hashes.
