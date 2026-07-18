# Semi-open Analysis API Test Report

Generated: 2026-07-18

## Purpose

This run validates the semi-open Financial Analysis Compiler, not the closed-form QA Sentence Plan API. The model receives bounded Signals, mandatory Claim contracts, valid conclusions, caveats, and Numeric Slots. It may organize the analysis language, but it may not invent facts, entities, periods, causal explanations, forecasts, or recommendations.

## Implemented controls

- Separate `analysis.generation.mode=controlled_llm` path and non-secret 50/50/50 profile.
- Credential-safe OpenAI-compatible JSON client; API keys, prompts, and raw responses are not persisted.
- Per-request HTTP, JSON, latency, token, model, request-hash, and response-hash audit.
- Independent Signal semantic gate and deterministic Signal replay from pinned facts.
- Claim Graph with dependency and contradiction relations.
- Predicate-filtered Valid Conclusion Set.
- Numeric Slot value, unit, tolerance, source-signal, and allowed-period grounding.
- Independent Claim and conclusion stance parsing; a correct Claim ID cannot hide opposite text.
- Bounded semantic repair: at most two attempts per sample, with every attempt persisted separately.
- API gates separately measure requests, retries, controlled samples, and final fallback samples.
- Component-based split with entity, peer-scope, evidence-window, and semantic-cluster leakage audit.

## Full 150-sample run

Build: `analysis_build_19318b7f3106cbca90b2b130`  
KG: `kg_20260711_062123_bc4b4394`  
Activation: disabled

| Measure | Result |
| --- | ---: |
| Candidates / samples | 150 / 150 |
| Pattern allocation | 50 operating trend / 50 growth quality / 50 peer positioning |
| Signal instances | 557 |
| HTTP success | 150/150 |
| Structurally valid responses | 150/150 |
| Controlled LLM generations | 150/150 |
| Deterministic fallback | 0 |
| Verifier passed | 148/150 |
| Total tokens | 688,309 |
| Prompt / completion tokens | 629,095 / 59,214 |
| Mean API latency | 8,102 ms |
| Estimated cost | unavailable because model prices were not configured |

The strict 100% analysis gate rejected two growth-quality samples. In both cases the response copied the correct risk Claim ID and evidence IDs but described the operating-cash-flow relationship as supporting profit growth. The independent stance verifier correctly classified the language as positive rather than risk-bearing. The build therefore remains failed, non-active, and non-exportable.

The run also exposed split skew: 104 passed samples shared a dominant recent window and entered `test_temporal_holdout`. Split version 1.1 now hashes the disjoint component identity together with the period window, preserving leakage safety without allowing one common window to absorb the dataset.

## Repair and regression

The generator now validates Claim and conclusion stance before accepting the response. A semantic mismatch triggers one bounded repair request; each attempt records `attempt_index`, `is_final_attempt`, and validation errors. Build statistics now distinguish request count, retry count, controlled sample count, final fallback count, and cost availability.

Post-repair real API build: `analysis_build_04e803b53439561a67cdf839`.

| Measure | Result |
| --- | ---: |
| Samples | 3 |
| HTTP / structured / controlled | 3/3 / 3/3 / 3/3 |
| Analysis verifier | 3/3 passed |
| Fallback / retries | 0 / 0 |
| Total tokens | 13,617 |
| Mean latency | 6,874 ms |
| Split leakage violations | 0 |

This preflight is quality-passed at sample level. Its overall build gate is intentionally failed because the production profile still requires 50 samples per pattern; a three-sample preflight does not satisfy that volume contract.

## Current status

The original 150-sample run is retained as an immutable failed audit build. The repaired code path is covered by unit tests that inject an opposite-stanced first response and verify that only a semantically valid retry is accepted. A second full 150-call run was not launched automatically, avoiding another roughly 0.69M-token expense solely to reproduce the same quota after the focused repair passed.
