# Generalization Validation Report v0.4.1

## Scope

This report validates architecture and contract portability, not legal or scientific production
readiness. Finance remains the scale reference implementation. Legal and Science are compact,
versioned contract fixtures with controlled candidate workflows and mutations.

The strongest justified claim is:

> The framework enforces domain generality as an executable architecture and release contract and
> validates contract-level portability across finance, legal, and scientific evidence regimes.

It does not yet establish real-model, real-corpus cross-domain transfer.

## Remediated Findings

The v0.4.1 hardening closes the review findings as follows:

| Finding | Resolution |
| --- | --- |
| Missing Legal/Science node output passed | Empty or missing observed output now fails strict equality |
| Executor and Oracle shared helpers | Legal/Science execution and oracle paths are independent; defect mutation is tested |
| Structured output lacked a contract | Pydantic output models reject missing, mistyped, and extra fields |
| Candidate required hidden node IDs | Explicit `PLAN_GIVEN` and semantic `PLAN_HIDDEN` tracks were added |
| Public scope exposed exact Oracle selection | Public semantic constraints and hidden exact selection are separate |
| Runtime candidate was finance-specific | Concrete generator moved to `experiments/finance_pilot`; Runtime exposes a protocol |
| Audit covered only Core | It now scans `core`, `runtime`, and `architecture` |
| AST audit bypasses | Relative/dynamic import, aliases, dict dispatch, and subscript access are detected |
| Plugin protocols lived under Domains | Protocols moved to `core/plugins.py`; old module re-exports them |
| Tools defaulted to calculator | Operations declare tool capability, action type, and execution mode |
| Mixed-domain evidence was implicit | Builder requires all evidence to match the single task domain |
| Helper changes escaped implementation hash | Registered helper dependencies are included in the operation hash |
| Missing source verifier passed silently | Required missing verifier fails; not-applicable is explicit |
| Release omitted portability artifacts | Plugin, verifier, mutation, fixture, and suite manifests are frozen |

## Static Architecture Audit

`generalization_contract.v1.2` scans every Python module in the three declared common packages:

```text
trusted_synthesis/core
trusted_synthesis/runtime
trusted_synthesis/architecture
```

Concrete domains are discovered from `trusted_synthesis/domains`. The audit implementation is
explicitly exempted from judging its own rule vocabulary but remains part of the file-hash identity.

| Metric | Required |
| --- | ---: |
| Common-package domain imports | 0 |
| Concrete-domain branches | 0 |
| Domain-field interpretation accesses | 0 |
| Dynamic domain imports | 0 |
| Dictionary domain dispatches | 0 |

The release process runs this audit fail-closed and freezes its complete result and hash.

## Public And Oracle Isolation

Public tasks now contain only semantic retrieval constraints. Exact evidence versions, source IDs,
build IDs, context hashes, gold bindings, expected outputs, and Proof Graph identities are held in
the Oracle contract. Recursive leakage checks reject these keys if they appear in public JSON.

`PLAN_GIVEN` exposes a public program skeleton without gold evidence or outputs. `PLAN_HIDDEN`
accepts candidate-local node IDs and aligns the produced DAG semantically. Tests cover both a valid
local plan and an operator mutation that must be rejected.

## Operation And Grounding Contracts

Legal and Science operations now bind strict result models:

```text
LegalRuleDecision
LegalAuthorityDecision
ScienceProtocolAlignment
ScienceEffectComparison
```

Missing node results and undeclared fields are rejected. Executor and oracle implementations use
independent algorithms, and an executor-helper mutation is caught by independent replay. Operation
identity includes executor, oracle, and declared helper dependencies.

Source grounding is also fail-closed:

```text
required + verifier available     -> VERIFIED or FAILED
required + verifier missing       -> MISSING_REQUIRED_VERIFIER
declared not applicable           -> NOT_APPLICABLE
```

Only `VERIFIED` and explicitly declared `NOT_APPLICABLE` can pass.

## Cross-domain Candidate Suite

The current deterministic suite executes one Legal and one Science candidate against hard in-scope
distractors, then applies seven mutation classes to each:

```text
missing evidence
time shift
scope mismatch
definition mismatch
wrong derivation
citation mismatch
unsupported claim
```

Expected deterministic result:

| Metric | Result |
| --- | ---: |
| Domains | 2 |
| Tasks | 2 |
| Clean candidates | 2 |
| Mutated candidates | 14 |
| Reference acceptance | 100% |
| Clean candidate acceptance | 100% |
| Mutation rejection | 100% |

The candidate sees only the public task and searchable corpus boundary. It does not read the Oracle
contract when selecting evidence or constructing its trace. These fixtures test contract behavior,
not natural-language model competence.

## Finance Regression

The deterministic finance pilot was rerun against pinned KG
`kg_20260711_062123_bc4b4394` after the v0.4.1 changes:

| Metric | Result |
| --- | ---: |
| Compiled tasks | 24 / 24 |
| Accepted references | 24 / 24 |
| Accepted clean candidates | 24 / 24 |
| Rejected mutations | 386 / 386 |
| Critical false acceptances | 0 |
| Error-detection F1 | 1.00 |
| Failure localization rate | 1.00 |
| Check localization rate | 0.9689 |
| Step/node localization rate | 1.00 |
| Semantic split leakage | 0 |
| Release hash replay | passed |

All 24 tasks retrieved seven hard distractor classes while selecting none of them. Source grounding
accepted 4,147 of 5,103 checked facts; the 956 rejected facts were FRED source-entailment failures,
so the architecture still exposes upstream data defects rather than normalizing them away.

The generated Release Manifest uses framework `0.4.1`, embeds all three plugin sets, records the
Finance source-grounding verifier, and freezes the passing two-domain Candidate Contract Suite.
These are deterministic architecture results and must not be presented as a real-model evaluation.

## Automated Verification

The v0.4.1 local gate consists of:

```text
Ruff format and lint
Mypy over the package
55 unit and integration tests
Python bytecode compilation
Generalization Contract v1.2 audit
Cross-domain Candidate Contract Suite
Finance deterministic pilot regression when archive data is available
```

Release reproducibility tests rebuild the manifest and require stable hashes for the audit, plugin
sets, source-grounding verifier, mutation taxonomy, fixture suite, and operation implementations.

## Remaining Boundary

The project now demonstrates:

```text
Schema generality
+ Task Program generality
+ public/oracle isolation across planning tracks
+ universal quality-gate reuse
+ domain operation and grounding extension
+ controlled cross-domain candidate/mutation portability
```

It still does not demonstrate:

```text
real Legal/Science agent candidates
production Legal/Science corpora
learned cross-domain Quality Critic
leave-one-domain-out transfer
real multi-domain release quality
```

The next evidence milestone should therefore use real model candidates on the compact Legal and
Science suite, followed by leave-one-domain-out critic experiments. Finance remains the primary
scale and stress-test domain while those tests constrain every common-layer evolution.
