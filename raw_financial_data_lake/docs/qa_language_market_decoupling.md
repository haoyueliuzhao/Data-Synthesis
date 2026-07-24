# QA Language and Market Decoupling

## Purpose

Language is a presentation attribute, not a market label. A QA build must not allow a model to infer Global or Greater China solely from whether the question is written in English or Chinese.

## Production distribution

| Market | English | Chinese | Mixed bilingual |
|---|---:|---:|---:|
| Global | 80% | 15% | 5% |
| Greater China | 20% | 65% | 15% |

The distribution is applied independently inside each market build. `mixed` questions use a registered bilingual template and remain subject to the same protected-slot and parser round-trip contract as monolingual questions.

## Deterministic assignment

Language assignment uses the stable candidate ID and `question_language_assignment.v1`. The allocator:

1. converts configured weights into exact build-level counts with largest-remainder allocation;
2. orders candidates by a stable hash;
3. uses deficit-based scheduling to spread languages through the candidate population;
4. records the selected language and configured distribution in sample metadata.

Candidate input order and thread scheduling therefore do not change the assignment.

For the current 496/504 regional sizes, a rebuild would produce:

| Market | English | Chinese | Mixed |
|---|---:|---:|---:|
| Global | 397 | 74 | 25 |
| Greater China | 101 | 328 | 75 |

## Quality gates

Each regional build enforces:

- minimum ratios for every configured language;
- a maximum share for the largest language;
- at least two observed language categories;
- parser/template support for `en`, `zh`, and `mixed`;
- unchanged semantic slots, operators, thresholds, units, currency, and precision after LLM rewriting.

The Global profile rejects a largest-language share above 82%. The Greater China profile rejects a largest-language share above 67%.

## Versioning

Mixed-language support changes the parser/template contract. New builds pin Question Parser `1.4.0` and its manifest hash. Existing released QA builds retain their original pinned parser contract and are not silently rewritten.
