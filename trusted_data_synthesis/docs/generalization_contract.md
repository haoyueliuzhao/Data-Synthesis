# Generalization Contract v1.1

## Position

Finance is the first reference implementation and the primary stress-test domain. It is not the
specification of the framework. Generalization is a release constraint, not a later benchmark.

```text
Core Framework
  Evidence identity, Proof Graph, Task Program, trajectories, universal gates, release

Domain Plugin
  semantic policy, task binding, domain operations, domain claims, domain gates

Experiment
  sources, sampling, prompts, model configuration, quotas, target distribution
```

The common contract is the compilation and verification interface. Domains do not have to share a
lowest-common-denominator fact model or all operation semantics.

## Enforced Boundaries

Every release and CI run executes `generalization_contract.v1.1`.

1. `core/` cannot import `trusted_synthesis.domains` or a concrete domain package.
2. `core/` cannot branch on `finance`, `legal`, or `science`.
3. `core/` cannot interpret domain fields such as fiscal period, currency, jurisdiction, or
   confidence interval. It may carry their serialized context opaquely.
4. New task families belong to a domain plugin. Core only packages an Evidence binding, Operation
   DAG, public contract, and isolated oracle.
5. A Core capability must be structurally generic or have a non-finance complex contract test.
6. A Release Manifest embeds the Generalization Contract version, audit hash, and violation counts.
   The hash covers the protected rule manifest and every scanned Core source file's content digest.

The audit is available directly:

```bash
trusted-synthesis audit-generalization --source-root src
```

## Operation Boundary

Core owns mathematical and workflow primitives such as lookup, comparison, difference, ratio,
aggregation, DAG execution, and independent replay. A mathematical operator does not decide when a
domain permits its use.

Domain registries extend the Core registry:

```text
Finance: period alignment, financial growth eligibility, financial ratios
Legal: rule applicability, exception handling, authority resolution
Science: protocol alignment, effect comparison, uncertainty preservation
```

`growth` remains a pure mathematical implementation. `FinanceSemanticPolicy` decides whether a
financial series has compatible definitions and a valid base.

## Task Boundary

`TaskPackageBuilder` is the universal compiler boundary:

```text
Domain Evidence Binding + Domain Operation DAG
                    -> TaskPackageBuilder
                    -> Public Task + Oracle Contract
```

Domain plugins own task discovery and language:

```text
LegalTaskPlugin.rule_application
ScienceTaskPlugin.compare_experiments
Finance task factories and pilots
```

The older `ProofGraphTaskSynthesizer` remains a compatibility convenience for generic scalar
retrieval/comparison/temporal examples. New domain task families must not be added there.

## Quality Gates

Every `HardGateResult` has an explicit scope. Every `QualityAssessment` publishes both lists:

```json
{
  "universal_gates": [],
  "domain_gates": [],
  "diagnostic_vector": {},
  "decision": "accepted"
}
```

Universal gates cover identity, public/oracle isolation, tools, structural Evidence validity,
retrieval coverage, Proof Graph integrity, operation replay, answer schema, and citation binding.
Domain gates cover semantic Evidence validity, source-grounding policy, domain comparability, and
domain claim boundaries. A domain failure cannot be hidden inside a generic answer gate.

## Retrieval Tracks

All domains use the same three track contracts:

```text
resolved   normalized constraints
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

Experiments implement concrete mutations and map them to this taxonomy. For example, a wrong fiscal
year, wrong effective date, and wrong study version all map to `temporal`; their construction remains
domain-specific.

## Cross-domain Contract Suite

Schema portability is insufficient. CI therefore includes non-lookup programs:

```text
Legal
  retrieve rules -> check conditions/exceptions -> resolve authority -> legal effect

Science
  retrieve results -> align protocol -> compare effect -> preserve uncertainty
```

Both programs use the shared Evidence/Proof Graph/Task Program/Reference Workflow/Quality Assessment
pipeline and their own policy and operation registries. A mutated legal operation output must be
rejected by the same universal replay gate used for finance.

## Pull Request Rule

A Core change is admissible only when at least one condition holds:

1. it is pure structure, workflow, or mathematics;
2. it has real use in two domains;
3. it includes one finance and one non-finance complex contract test.

Otherwise the capability starts in a Domain Plugin. Promotion to Core requires evidence of reuse.

## Release Metrics

The following are hard targets:

```text
core_domain_import_count        = 0
core_domain_branch_count        = 0
core_domain_field_access_count  = 0
cross_domain_contract_pass_rate = 100%
```

Future learned quality critics must additionally report leave-one-domain-out error F1, critical
false acceptance rate, step localization, and calibration. Those metrics are not claimed by the
current deterministic Contract Suite.
