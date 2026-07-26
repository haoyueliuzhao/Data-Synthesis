# Generalization Contract v1.2

## Position

Finance is the first reference implementation and the primary scale and stress-test domain. It is
not the specification of the framework. Domain generality is enforced as an architecture and
release contract, not deferred to a later benchmark.

```text
Core Framework
  Evidence identity, Proof Graph, Task Program, trajectories, universal gates, release

Domain Plugin
  semantic policy, task families, domain operations, claims, grounding, domain gates

Experiment
  sources, sampling, prompts, models, quotas, target distributions
```

The shared abstraction is the compilation, execution, verification, and release interface. Domains
do not need to share one lowest-common-denominator fact schema or identical operation semantics.

## Enforced Boundaries

Every release and CI run executes `generalization_contract.v1.2`.

1. Domain-neutral packages `core/`, `runtime/`, and `architecture/` cannot import
   `trusted_synthesis.domains` or a concrete domain package.
2. Those packages cannot branch or dispatch on any concrete domain discovered under `domains/`.
3. They cannot interpret domain fields such as fiscal period, currency, jurisdiction, protocol, or
   confidence interval. They may carry serialized domain context opaquely.
4. New task families, source rules, semantic policies, and domain claims belong to a plugin.
5. A common capability must be structural, workflow-oriented, mathematical, or covered by a
   non-finance complex contract test.
6. A release embeds the complete architecture audit and rejects any violation.

The AST audit resolves relative imports, direct and dynamic imports, module-level constant aliases,
dictionary dispatch, branch expressions, and both attribute and subscript field access. Concrete
domains are discovered from the repository rather than maintained in a fixed allowlist. Its hash
covers the protected rule manifest and every scanned source file, including the explicitly exempted
audit implementation itself.

```bash
trusted-synthesis audit-generalization --source-root src
```

## Plugin Contract

Common plugin protocols live in `core/plugins.py`; `domains/contracts.py` is only a compatibility
re-export. A domain can provide:

```text
EvidenceAdapterProtocol
SemanticPolicyProtocol
ClaimVerifierProtocol
SourceGroundingVerifierProtocol
OperationRegistryProvider
TaskFamilyPluginProtocol
DomainQualityClauseProviderProtocol
```

`DomainPluginSet` freezes the concrete plugin IDs and versions used by a release. Core consumes
these protocols without importing or selecting a domain implementation. A required verifier that is
not supplied fails closed; an intentionally unsupported check must be declared `NOT_APPLICABLE`.
Quality-clause providers may contribute only domain clauses; dependency ordering, gate aggregation,
runtime execution, and release decisions remain common-layer responsibilities.

## Operation Boundary

Core owns mathematical and workflow primitives such as lookup, filter, comparison, difference,
ratio, aggregation, selection, DAG execution, and independent replay. A mathematical operator does
not decide when a domain permits its use.

Domain registries extend this set:

```text
Finance: financial period alignment, growth eligibility, financial ratios
Legal: rule applicability, exception handling, authority resolution
Science: protocol alignment, effect comparison, uncertainty preservation
```

Every operation declares its tool capability, action type, execution mode, strict output model, and
implementation dependencies. Structured outputs reject missing fields, wrong types, and undeclared
extra fields. The implementation hash includes executor, independent oracle, and registered helper
dependencies, so helper changes cannot silently retain an old contract identity.

Executor and oracle implementations must be independent enough for a helper-defect mutation in the
executor path to be caught by replay. A missing observed node output is always a failure.

## Task And Oracle Boundary

`TaskPackageBuilder` is the universal compiler boundary:

```text
Domain Evidence Binding + Domain Operation DAG
                    -> TaskPackageBuilder
                    -> Public Task + Isolated Oracle Contract
```

The builder derives allowed tools from operation definitions and rejects implicit mixed-domain
evidence. Cross-domain tasks require a future explicit multi-domain policy.

The public and hidden contracts are deliberately different:

```text
Public semantic scope
  subject, predicate, time, authority, requested definition, aliases

Hidden exact selection
  evidence/version/source/build IDs, context hashes, gold bindings, expected outputs
```

Exact evidence identity must never appear in model-visible retrieval scope. The leakage gate rejects
oracle-only keys recursively.

Two planning tracks are supported:

```text
PLAN_GIVEN
  Public program skeleton exposes operators, dependencies, role references, and public node IDs.
  Gold evidence IDs, outputs, and Proof Graph remain hidden.

PLAN_HIDDEN
  Candidate creates local node IDs and a local plan. Verification aligns operators, dependencies,
  references, and outputs semantically rather than requiring Oracle node identity.
```

Domain plugins own task discovery and language. The generic builder only packages evidence
bindings, operation DAGs, public contracts, and isolated oracle state.

## Candidate Runtime Boundary

`runtime/` contains only generic agent, tool-runtime, trace, and execution protocols. It must not
branch on finance task types or assume scalar financial observations. The deterministic finance
numeric candidate is an experiment implementation under `experiments/finance_pilot/`.

## Quality Gates

Every `HardGateResult` has an explicit scope. Every assessment publishes separate gate groups:

```json
{
  "universal_gates": [],
  "domain_gates": [],
  "diagnostic_vector": {},
  "decision": "accepted"
}
```

Universal gates cover identity, public/oracle isolation, allowed tools, structural evidence,
retrieval coverage, Proof Graph integrity, operation replay, answer schema, and citation binding.
Domain gates cover semantic evidence validity, source grounding, comparability, and claim boundaries.
A domain failure cannot be hidden inside a generic answer check.

In v0.5, these requirements are compiled into a task-local `QualityContract`. Universal clauses are
derived from the Public/Oracle boundary, Evidence Bundle, Proof Graph, Program DAG, answer schema,
and citations. Domain clauses are injected through the frozen provider protocol. Every clause has a
typed target and dependency set, so failures can be localized without Core interpreting domain
payloads. Unknown verifier identities and missing observations fail closed.

The fixed evaluator remains a temporary compatibility path. Finance, Legal, and Science execute both
the fixed evaluator and Contract Runtime, and release requires exact decision parity. Removing the
fixed manifest is a later migration step, after production parity remains stable.

Source grounding has three explicit outcomes relevant to release decisions:

```text
VERIFIED
NOT_APPLICABLE
MISSING_REQUIRED_VERIFIER / FAILED
```

Only the first two can pass, and `NOT_APPLICABLE` must be declared by the task contract.

## Retrieval Tracks

All domains use the same retrieval-track meanings:

```text
resolved   normalized semantic constraints
semi_open  aliases or partial constraints + fixed corpus boundary
open       natural-language task + fixed corpus boundary
```

Resolvers remain domain plugins: company/metric resolution for finance, citation/jurisdiction
resolution for law, and paper/method resolution for science.

## Mutation Taxonomy

Core freezes cross-domain failure families:

```text
evidence, temporal, scope, definition, provenance, trajectory,
citation, derivation, claim, composite
```

The taxonomy includes a concrete `source_provenance_mismatch` entry. Experiments implement domain
mutations and map them to these shared labels; for example, a wrong fiscal year, effective date, and
study version all map to `temporal`.

## Cross-domain Contract Suite

Schema portability alone is insufficient. The versioned suite therefore executes non-lookup
candidate workflows with hard in-scope distractors:

```text
Legal
  search -> condition/exception application -> authority resolution -> supported claim

Science
  search -> protocol alignment -> qualified effect comparison -> uncertainty preservation
```

For each domain, a public-only clean candidate must pass and mutations of evidence, time, scope,
definition, derivation, citation, and claim must be rejected. Every suite task must also compile an
independent Quality Contract and Proof Certificate, and every clean or mutated candidate must have
the same decision under the fixed evaluator and Contract Runtime. The suite result and fixture
manifest hash are frozen in every release alongside plugin sets, source-grounding verifiers,
operation registries, contract/verifier identities, certificates, and mutation taxonomy.

This proves contract-level portability. It does not prove transfer to production legal/scientific
corpora or real model agents.

## Pull Request Rule

A common-layer change is admissible only when at least one condition holds:

1. it is pure structure, workflow, or mathematics;
2. it has real use in two domains;
3. it includes one finance and one non-finance complex contract test.

Otherwise it starts in a domain plugin. Promotion requires evidence of reuse.

## Release Contract

Each release freezes at least:

```text
generalization audit version/hash/result
scanned common packages and discovered domains
DomainPluginSet IDs and versions
operation and implementation manifests
source-grounding verifier IDs and versions
mutation taxonomy manifest hash
cross-domain fixture/result hash
public/oracle and planning-track contract versions
```

Hard targets are:

```text
core_domain_import_count          = 0
core_domain_branch_count          = 0
core_domain_field_access_count    = 0
dynamic_domain_import_count       = 0
domain_dispatch_count             = 0
cross_domain_reference_pass_rate  = 100%
cross_domain_candidate_pass_rate  = 100%
cross_domain_mutation_reject_rate = 100%
cross_domain_contract_coverage    = 100%
cross_domain_certificate_coverage = 100%
cross_domain_decision_parity      = 100%
```

Future learned quality critics must additionally report leave-one-domain-out error F1, critical
false acceptance rate, step localization, and calibration. Those metrics are not claimed by the
current deterministic contract suite.
