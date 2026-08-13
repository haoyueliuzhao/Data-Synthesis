# Frozen Financial Benchmarks

These files are immutable, evaluation-only snapshots. They must not enter synthesis,
training, paraphrasing, or trajectory-state construction.

| Benchmark | Split | Examples | Pinned revision |
|---|---|---:|---|
| FinQA | public test | 1,147 | `0f16e2867befa6840783e58be38c9efb9229d742` |
| TAT-QA | released gold test | 1,663 | `870accc41953dcde885aabeb963d94aabdc0fbc3` |

`SHA256SUMS` freezes file contents. The manifest additionally freezes repository,
revision, source blob, native adapter, native metric, split, and usage identity.

`manifests/v25_21_public_agent_design_references.json` is a separate aggregate-only
design-reference manifest for GAIA, BFCL V4, WebArena, SWE-bench, and AgentBench. It contains
published counts and interaction structures only. No task content is loaded, and its contract
forbids synthesis, training, paraphrasing, and question/answer access.

The active `native_financial_benchmark_adapter.v4` contract reconstructs full report context.
`native_financial_benchmark_metric.v4` separately reports answer correctness and FinQA program
execution correctness, while retaining TAT-QA answer/scale scoring. As an adapter self-check, all
1,147 frozen FinQA gold programs replay to their released executable answers and all 1,663 TAT-QA
gold answer/scale pairs score exactly against themselves. These are evaluator consistency checks,
not trained-model results. The public releases do not expose a document-content identity shared
with the synthesis archive; the required document-hash leakage channel therefore remains
unavailable and blocks training preflight until an explicit, auditable identity map is frozen.
