# v0.7 Counterfactual Validation Report

## Scope

Validation used deterministic Finance, Legal, and Science fixtures plus the
immutable production finance KG archive. No network model or external
generated data was used.

## Cross-Domain Contract Run

```text
100 source tasks per domain
300 source tasks total
```

| Metric | Result |
| --- | ---: |
| Generated counterfactuals | 5,900 |
| Clean false positives | 0 |
| Mutation validity | 100% |
| Minimality pass rate | 100% |
| Mean minimality score | 0.9915 |
| Detection F1 | 100% |
| Root-cause F1 | 100% |
| Failure-closure F1 | 100% |

Every domain independently reached 100% mutable-clause coverage and 100%
registered-operator coverage.

Domain case counts:

| Domain | Cases |
| --- | ---: |
| Finance | 1,600 |
| Legal | 2,300 |
| Science | 2,000 |

Artifact:

```text
artifacts/counterfactual_validation/v07_contract_300.json
```

## Finance Archive Pilot

```text
KG build              kg_20260711_062123_bc4b4394
KG nodes              913,475
KG edges              5,734,348
Fact nodes            658,535
Source tasks          50
```

| Metric | Result |
| --- | ---: |
| Mutation opportunities | 1,284 |
| Generated counterfactuals | 1,284 |
| Registered / exercised operators | 16 / 16 |
| Clean false positives | 0 |
| Mutation validity | 100% |
| Minimality pass rate | 100% |
| Mean minimality score | 0.9933 |
| Detection F1 | 100% |
| Root-cause F1 | 100% |
| Failure-closure F1 | 100% |
| Mutable-clause coverage | 100% |
| Operator coverage | 100% |

| Mutation family | Cases |
| --- | ---: |
| Citation | 50 |
| Claim | 50 |
| Definition | 271 |
| Derivation | 380 |
| Evidence | 99 |
| Provenance | 99 |
| Scope | 86 |
| Temporal | 99 |
| Trajectory | 150 |

Artifacts:

```text
artifacts/finance_pilot/v07_counterfactual_50_final/counterfactual_cases.jsonl
artifacts/finance_pilot/v07_counterfactual_50_final/counterfactual_calibration_report.json
artifacts/finance_pilot/v07_counterfactual_50_final/pilot_report.md
```

## Interpretation

The result establishes that Contract-declared mutations are executable,
minimal, rejected, and localized on both cross-domain fixtures and the real
finance archive. The measured 100% values reflect deterministic runtime
calibration against typed violations, not general model accuracy or human
agreement.
