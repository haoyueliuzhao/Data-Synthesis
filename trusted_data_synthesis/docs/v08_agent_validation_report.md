# v0.8 Agent-Centered Quality Validation Report

## Executive Summary

v0.8 adds a real-model candidate boundary without weakening the v0.7 Quality Contract.
The strong-model reference is now DeepSeek V4 Pro. Model output is treated as an
untrusted candidate trajectory: it is normalized structurally, replayed independently,
projected to a five-dimensional Quality Vector, and only then considered for selection.

The implementation is complete at the framework and offline integration level. Provider
discovery confirmed that the exact requested model ID `deepseek-v4-pro` is available; no
fallback model is configured. A content-generation smoke was not executed in this run
because `DEEPSEEK_API_KEY` was not exported into the process environment. The framework
does not read credentials from repository files, historical logs, prompts, or manifests.

## Architecture Delivered

```text
Task Release
  -> Resolved / Semi-open / Open retrieval track
  -> PLAN_GIVEN / PLAN_HIDDEN planning track
  -> DeepSeek V4 Pro candidate generation
  -> normalized model-reported Trajectory
  -> independent Quality Contract replay
  -> Quality Vector
  -> typed counterfactual + real-candidate Critic corpus
  -> advisory Quality Critic
  -> Contract-authoritative quality selection
  -> frozen D1-D5 utility protocol
```

### Candidate boundary

The Agent receives only `TaskPublicSpec` and an evidence runtime. Semi-open and Open tasks
use a separate typed search request before answer generation. The host restores the corpus
boundary, while the model controls public semantic constraints. Gold Evidence IDs and the
Oracle Contract are not representable in the search schema.

The normalizer preserves selected Evidence, reported operation results, verification output,
answer, and citations. It does not execute operations on behalf of the model. PLAN_HIDDEN
permits candidate node IDs, but independent replay maps them by operator, input, dependency,
parameter, and output semantics.

### DeepSeek routing

The checked-in profile requires the exact `deepseek-v4-pro` identifier, enables model
discovery, disables fallback, and reads its credential only from `DEEPSEEK_API_KEY`.
Telemetry records selected and returned model IDs, token usage, latency, status, and content
hashes. Cost is intentionally `null` until an audited tariff is frozen; zero-valued placeholder
rates are not reported as zero cost.

Both Agent and Critic contracts support one bounded repair request. The repair receives the
previous JSON and validation error, but no oracle answer or Contract decision. All attempts,
including invalid contracts, remain in telemetry.

### Quality and selection

The Quality Vector contains `evidence`, `program`, `trajectory`, `citation`, and `claim`.
Non-applicable dimensions remain null, and unknown diagnostic dimensions fail closed.

The Critic output is explicitly `model_advisory`. It cannot become a human label or override
a Contract rejection. Unreviewed accepted samples receive a neutral 0.5 Critic prior rather
than a perfect score. This prevents review-budget coverage from becoming a hidden ranking
advantage.

### Training utility protocol

D1-D5 identities, policies, model, seed, optimizer invariants, metrics, and held-out domains
are frozen. The protocol remains `planned`; no training gain is claimed. In particular, the
current smoke has no independent random synthetic pool, so D1 is recorded as `planned` with
no sample IDs. Prepared real Agent samples are not relabeled as random data.

## Verification Results

Run date: 2026-07-26.

| Check | Result |
| --- | ---: |
| Ruff | passed |
| Mypy | passed, 149 source files |
| Pytest | 86 passed |
| Cold-process public imports | passed |
| Core domain imports | 0 |
| Core domain branches | 0 |
| Core domain field accesses | 0 |
| Domain dispatch in Core | 0 |
| Cross-domain compiled Task Patterns | 6 |
| Clean candidate pass rate | 100% |
| Contract decision parity | 100% |
| Counterfactual source samples | 9 |
| Generated typed counterfactuals | 177 |
| Mutation validity | 100% |
| Detection F1 | 100% |
| Root-cause F1 | 100% |
| Failure-closure F1 | 100% |
| Minimality pass rate | 100% |
| Mean minimality score | 0.9908 |

The scripted integration suite covers Finance, Legal, and Science; PLAN_GIVEN and
PLAN_HIDDEN; Semi-open and Open model-controlled search; positive real-candidate fixtures;
typed counterfactual negatives; Critic contract repair; and Contract-authoritative selection.
These are deterministic framework tests, not measurements of DeepSeek answer quality.

## DeepSeek Validation Status

Provider model discovery returned two model IDs and included the exact requested
`deepseek-v4-pro` ID. No fallback was used or configured. The online content-generation run
is pending a credential supplied through the process environment:

```bash
export DEEPSEEK_API_KEY="<secret>"
PYTHONPATH=src python -m trusted_synthesis.cli validate-agents \
  --agent-config config/deepseek_v4_pro_agent_smoke.json \
  --output-dir artifacts/agent_validation/v08_deepseek_v4_pro_smoke \
  --output artifacts/agent_validation/v08_deepseek_v4_pro_smoke_report.json
```

The intended smoke contains six Agent candidates: one task per domain across PLAN_GIVEN and
PLAN_HIDDEN, plus up to six stratified Critic reviews spanning domain, candidate source, and
Contract acceptability. The report will expose real provider token usage and leave estimated
cost unset.

## Remaining Boundaries

1. Human alignment has not been established. DeepSeek Critic agreement is model agreement,
   not a replacement for human labels.
2. D1 is not materialized, and no D1-D5 SFT run has been executed. Training utility remains a
   falsifiable protocol rather than a result.
3. Open retrieval currently operates over a bounded in-memory corpus. It validates Agent
   search behavior but is not a web-scale retrieval benchmark.
4. The online DeepSeek candidate smoke is pending secure environment credential injection.
5. The current sample scale validates contracts and orchestration, not production error
   distributions or the target human agreement thresholds.

## Acceptance Decision

v0.8 is ready as an Agent-centered validation framework and for a credentialed DeepSeek V4
Pro smoke. It is not yet evidence that quality-selected data improves downstream training.
That claim requires materializing D1, freezing equally sized D1-D5 cohorts, running the five
training jobs, and publishing held-out utility metrics.
