# Generalization Validation Report

## Scope

This report validates architecture portability, not legal or scientific dataset readiness. Finance
remains the large-scale reference implementation; Legal and Science are small, manually controlled
contract fixtures.

## Static Architecture Audit

`generalization_contract.v1.1` scanned the complete `trusted_synthesis/core` package. Its audit
identity includes the rule manifest and content digest of every scanned Core source file.

| Metric | Result | Contract |
| --- | ---: | ---: |
| Core domain imports | 0 | 0 |
| Core concrete-domain branches | 0 | 0 |
| Core domain-field interpretation accesses | 0 | 0 |

The Release Manifest now runs this audit fail-closed and freezes its hash.

The finance production entry points now instantiate `FinanceTaskPlugin`; Core retains only the
generic package builder and compatibility examples. The package and release manifest versions were
advanced together to `0.4.0`, so a release cannot report the earlier framework contract after using
the new boundary rules.

## Reasoning Contracts

| Domain | Program | Depth | Result |
| --- | --- | ---: | --- |
| Legal | condition/exception checks -> authority resolution | 3 | passed |
| Science | protocol alignment -> qualified effect comparison | 2 | passed |

Both contracts passed structural Evidence checks, domain semantic checks, Proof Graph validation,
independent operation replay, citation binding, and separate Universal/Domain hard gates. A mutated
legal operation output was rejected by `independent_recompute` while all domain gates remained valid,
which confirms that the generic replay gate detects a non-financial derivation error.

## Finance Regression

The deterministic small finance pilot was rerun after moving production task construction behind
the finance plugin.

| Metric | Result |
| --- | ---: |
| Compiled tasks | 24 / 24 |
| Accepted references | 24 / 24 |
| Accepted clean candidates | 24 / 24 |
| Rejected mutations | 386 / 386 |
| Critical false acceptances | 0 |
| Error-detection F1 | 1.00 |
| Failure localization rate | 1.00 |
| Step/node localization rate | 1.00 |
| Semantic split leakage | 0 |

The mutation run exercised nine generic families: evidence, temporal, scope, definition,
trajectory, citation, derivation, claim, and composite. Every realized family had a 100% detection
rate. The generic `provenance` family is registered but was not independently realized by this
small finance configuration; source-object entailment remains covered by the ordinary quality
pipeline rather than this mutation count.

The generated Release Manifest embedded the same passing architecture audit:

```text
core_domain_import_count       = 0
core_domain_branch_count       = 0
core_domain_field_access_count = 0
```

This regression shows that enforcing the plugin boundary did not weaken the existing finance
reference implementation.

## Automated Gates

The validation suite currently requires:

```text
Ruff lint and format
Mypy over the complete package
45 unit and integration tests
Python bytecode compilation
Generalization Contract audit
Finance deterministic pilot regression
```

The cross-domain tests deliberately include non-lookup Legal and Science programs. They establish
reasoning-contract reuse, rather than merely proving that different payloads can pass through a
shared schema.

## Current Interpretation

The project now demonstrates:

```text
Schema generality
+ Task Program generality
+ Universal quality-gate reuse
+ Domain operation-registry extension
```

It does not yet demonstrate model-level cross-domain transfer. Legal and Science use controlled
fixtures, not production corpora or live candidates. Leave-one-domain-out Quality Critic experiments
remain a later milestone and must not be inferred from these contract results.

The next generalization milestone is therefore not a large second data lake. It is a compact,
versioned Legal/Science contract corpus with hard distractors and domain mutations, followed by a
leave-one-domain-out critic experiment. Finance remains the scale and stress-test domain throughout.
