# Framework v0.6 Validation Report

## Scope

Version 0.6 validates the missing front half of proof-carrying synthesis: a declarative Task Pattern
and concrete Evidence Binding now compile into the same Task Program, Quality Contract, Proof
Certificate, and Release machinery used in v0.5.

## Delivered Architecture

```text
Domain Pattern Catalog
        -> typed Evidence roles
        -> content-addressed Evidence Binding
        -> domain semantic validation
        -> deterministic Program expansion
        -> compiled difficulty profile
        -> task-local quality clauses
        -> proof and release identity
```

Core contains only the structural Pattern, Binding, compiler, and difficulty policy. Finance,
Legal, and Science own Pattern catalogs, semantic validators, instruction renderers, and task
discovery facades.

## Validation Results

| Validation | Result |
| --- | ---: |
| Unit and integration tests | 71 / 71 passed |
| Ruff | passed |
| Mypy | 117 source files, 0 issues |
| Finance Pattern tasks | 50 / 50 compiled |
| Finance reference and clean candidate acceptance | 100% / 100% |
| Finance mutation rejection | 803 / 803 |
| Finance dual-runtime parity | 853 / 853 |
| Finance Pattern/Binding and difficulty clause coverage | 100% / 100% |
| Legal Pattern tasks | 10 / 10 passed |
| Science Pattern tasks | 10 / 10 passed |
| Cross-domain Pattern contract parity | 100% |

Finance covered four task families and produced 50 distinct Binding hashes. Its difficulty profile
contained 13 easy, 13 medium, and 24 hard tasks. The Pilot remained a global, historical numeric,
resolved-retrieval test; it intentionally made no production-readiness claim.

## Remaining Risks

```text
Task discovery is still domain-owned; the Pattern compiler does not mine Pattern candidates.
Counterfactual generation is still largely mutation-code driven rather than Contract derived.
Legal and Science are controlled contract fixtures, not production archives.
No live model or human-calibrated quality critic has been evaluated.
Open and semi-open retrieval remain outside the Finance Pilot.
```

The next implementation target is Typed Counterfactual Engine v0.7. Real-agent and learned-critic
experiments should follow only after typed failure generation and minimality validation are stable.
