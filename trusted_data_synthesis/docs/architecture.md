# Architecture v0.5

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
        -> Reference Workflow + independent replay
        -> Proof-Carrying Sample + Proof Certificate
        -> Sample-specific Quality Contract
        -> Candidate Agent + observation reconstruction
        -> Contract Runtime + legacy parity gate
        -> Candidate-aware release selector
        -> Semantic-cluster split + immutable manifest
```

## Evidence And Corpus

An `EvidenceItem` is a versioned assertion. Discriminated payloads support scalar
observations, textual claims, legal rules, relations, experiments, and derived
results. Subject, predicate, temporal context, scope, source, semantic definition,
epistemic status, archive lineage, and derivation parents remain explicit.

`EvidenceCorpus` is distinct from a task-local bundle and may contain distractors.
Public tasks declare a `resolved`, `semi_open`, or `open` retrieval track. Semi-open
tasks carry aliases or partial constraints inside a fixed corpus boundary. The current
deterministic candidate supports the resolved track; domain resolvers own semi-open and
open interpretation.

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

## Proof-Carrying Sample

`ProofCarryingSampleCompiler` is the common compilation boundary after a domain task has been
instantiated. It does not discover finance, legal, or scientific tasks. It binds the already-built
Task Package, Evidence Bundle, Proof Graph, Task Program, accepted Reference Workflow, compiled
Quality Contract, operation manifest, domain plugin identity, and optional source-grounding
manifest into one deterministic `ProofCertificate`.

The certificate detects partial replacement or stale compilation: changing Evidence, graph,
program, expected output, reference execution, verifier implementation, domain policy, or source
grounding changes the sample identity. `ProofCarryingPublicArtifact` exposes only the Public Task,
sample identity, and certificate hash. It excludes Oracle state, exact Evidence IDs, and the
reference answer.

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

Core structural validation is composed with executable domain policy. Finance v2
checks scalar shape, units/currency, historical status, time basis, frequency,
scope, source definition, and cross-fact comparability. `FinanceClaimVerifier`
permits only bounded structured claims and rejects ungrounded causal, forecast, or
investment claims. Legal now runs condition and exception checks followed by authority
resolution. Science aligns protocols before comparing effects and preserves uncertainty
in its qualified result. These are compact contract fixtures, not production datasets.

## Compiled Quality Contracts

Reference and Candidate quality remain deliberately separate:

```text
ReferenceQualityEvaluator
  certifies the deterministic compiler and independent oracle replay

CandidateQualityEvaluator
  reconstructs retrieval, selection, calculation, answer, citation, and claims
```

`QualityContractCompiler` derives a different executable contract for each task. Boundary clauses
come from Public/Oracle separation and planning/retrieval tracks; Evidence and Proof clauses are
created for every gold Evidence item; Program clauses are created for every DAG node; answer and
citation clauses are derived from the answer schema and evidence bindings. A domain clause provider
adds finance, legal, or scientific semantic checks through a protocol consumed by Core.

`QualityContractRuntime` indexes the candidate trajectory once, executes clauses in dependency
order through a versioned verifier registry, and aggregates Universal and Domain gates. Unknown
verifiers, missing observations, and blocked dependencies fail closed and remain locatable by
clause, Evidence ID, Program node, answer field, or citation. The runtime publishes unexecuted
clauses and root failures rather than reducing all failures to one global check name.

The previous fixed `CandidateQualityEvaluator` remains active only as a migration oracle. Every
Pilot and cross-domain contract case is evaluated through both paths; any decision mismatch is a
release failure. This preserves current behavior while moving task-specific check selection out of
the global manifest.

## Generalization Boundary

`generalization_contract.v1.2` is enforced in CI and every Release Manifest. All declared
common packages (`core`, `runtime`, and `architecture`) cannot import a concrete domain,
branch or dispatch on a discovered domain label, or interpret domain fields. The audit also
detects relative and dynamic imports, aliased labels, and subscript field access.
`TaskPackageBuilder` accepts domain-bound Evidence and Operation DAGs through typed plugin
protocols without knowing how the domain discovered them. Public tasks expose semantic retrieval
constraints and an optional program skeleton; exact Evidence selection and expected execution
remain isolated in the Oracle. See `docs/generalization_contract.md` for the executable rules.

## Release And Split

Split fields are executed from `SplitPolicy.cluster_fields`. Program clustering
uses an Evidence-ID-independent semantic hash, while instance identity retains
versioned Evidence IDs. `CandidateReleaseSelection` publishes only accepted
trajectories and records assessment IDs, failure distribution, domain/task
distribution, and split counts. Release manifests freeze both Reference and Candidate check
manifests, operation implementation hashes, domain plugin and source-grounding identities,
mutation taxonomy, Quality Contract compiler/runtime/verifier manifests, every task contract hash,
Proof-Carrying compiler versions, every certificate hash, and the versioned cross-domain Candidate
Contract Suite result. For a non-empty task release, Contract and Certificate coverage must exactly
equal the released task set.
