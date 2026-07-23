# Greater China QA Constraint Contract

## Purpose

This contract defines the admission boundary for a future Greater China QA rebuild. It deliberately does not generate questions: `generation_enabled=false` remains a hard switch until the new fact build and KG pass their quality gates.

The design goal is to preserve the auditability of the raw lake while making future Chinese and bilingual questions financially unambiguous. A sample is admitted only after its facts have passed candidate promotion, standardization, source-definition matching, fact-quality checks, and KG construction.

## Authority Boundary

Corporate facts must originate from CNInfo, Beijing Stock Exchange disclosures, or HKEXnews. Market, index, monetary, external-sector, and national statistics must originate from the relevant exchange, CSI, NBS, PBOC, or SAFE. Every numerical fact must resolve to a graph-ready standardized fact, an official source definition, and a passed raw object. Parsed PDF candidates are never directly eligible.

## Entity Boundary

Company and security are separate identities. A-share, H-share, and ADR securities remain distinct even when they belong to one canonical company. Cross-listing questions require an explicit canonical-company relation and listing venue; ticker-only joins are forbidden. Historical names and ticker validity intervals must be available before company-renaming or cross-listing tasks are admitted.

## Financial Scope

The coverage gate uses explicit metric-applicability profiles rather than assuming every issuer presents the same five lines:

1. General consolidated companies require five-year operating-performance and financial-position evidence.
2. Regulated banks, insurers, and financial-market institutions require earnings plus at least two balance-sheet anchors; revenue and operating cash flow remain presentation-dependent.
3. HKEX issuers using a net-assets or UK-style primary statement may omit standalone total-assets and total-liabilities lines; the profile still requires operating evidence plus equity or operating-cash-flow evidence.

`not_applicable` is a semantic status, not a substitute for missing data. It may be assigned only by a frozen profile with a written rationale. Missing, unknown, and not-applicable values must never be rendered as zero.

## Accounting And Time

ASBE, HKFRS, and IFRS facts may coexist, but cross-standard comparisons require an explicit compatibility rule. Consolidated and parent-only values, segment and group values, and GAAP and non-GAAP values cannot be mixed. Parent-attributable profit does not silently replace consolidated net income.

Questions must distinguish fiscal period, calendar period, period end, filing date, and report date. Point-in-time balance-sheet metrics cannot be directly compared with period-flow metrics. Quarterly YTD values cannot be treated as single-quarter values, and temporal operations require continuous, frequency-compatible windows.

## Units And Currencies

Source scale is retained for traceability; calculations use a pinned normalized scale. CNY, HKD, and USD are never treated as interchangeable. Cross-currency operations require a pinned FX fact, rate date, and rate type. The future question or output contract must state currency, unit, answer format, and precision or tolerance.

## Future Language And Distribution

When QA generation is eventually enabled, Greater China samples must include Chinese, English, and Chinese-English bilingual forms. Chinese is the majority language, bilingual samples have a protected minimum share, and no single surface template may dominate. Surface diversification, including synonym replacement or natural omission of redundant wording, must pass a structured semantic round trip so that direction, threshold, scope, metric, period, unit, and currency do not change.

Market quotas are applied only after quality filtering. The intended distribution reserves explicit shares for A-shares, HKEX, and BSE; quota pressure can never relax source, scope, or evidence gates.

## Activation Checklist

Generation may be enabled only after all of the following are true:

1. The Greater China raw annual-report scope meets the five-year document contract.
2. The company metric-profile pass ratio is at least 90%, with the remaining gap published and a 100% target retained.
3. The scoped graph-ready fact ratio is at least 90%.
4. All required official publication targets have passed download and checksum validation.
5. A pinned KG build passes node, edge, scope, source-definition, and evidence-lineage checks.
6. Chinese and bilingual parser/verbalizer round-trip tests exist for every enabled task pattern.

Until then, this file is a design and admission contract only; it must not be interpreted as approval to build QA samples.
