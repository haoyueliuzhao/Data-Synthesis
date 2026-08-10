# Finance v23 Pro--Flash Explorer Runtime Factorial Report

Status date: 2026-08-11

Final status: `calibration_failed_discovery_not_permitted`

## Question And Claim Boundary

This experiment asks whether a lower-capability Explorer from the same provider family can expose
more capability-sensitive valid Agent states while holding the public task, frozen Archive, Host
runtime, verifier, tool and token budgets, and sampling protocol fixed. `deepseek-v4-flash` is a
new Explorer identity; it is not an in-place replacement for `deepseek-v4-pro`.

The experiment is ordered as:

```text
six-task protocol qualification
-> 30-task paired factorial Discovery
-> state-conditioned materialization
-> small exact target
-> later frontier screening and fresh Development
```

Every arrow is fail-closed. The qualification failed, so only the first stage exists. This report
does not evaluate state entropy, meaningful-coordinate rate, Exact Target, GP-C, Contribution,
VTDO updates, Student training, or downstream performance.

## Frozen Design

The exact models are `deepseek-v4-pro` and `deepseek-v4-flash`, with no fallback. Both use
temperature `0.6`, `top_p=0.9`, disabled provider thinking, a 4,096-token per-response cap, and a
90,000-token cumulative rollout budget. Interactive arms share 12 tool calls, three failed-tool
calls, one Archive snapshot, one six-tool manifest, and one independent verifier.

| Arm | Model authority | Host authority |
| --- | --- | --- |
| Direct/Bare | complete response and answer | independent verification |
| Scripted Tool | query arguments and answer | tool order, execution, verification |
| Autonomous Agent | tool, query, continue, recovery, stop, answer | execution, budgets, verification |

The Host supports typed failed observations, stop rejection and correction, exact calculator
outputs, content-addressed provenance, checkpointed parallel execution, and replay. Public tool
guidance exposes only supported filters and answer schemas. Gold Evidence IDs, hidden programs,
reference answers, Proof Graphs, target states, and Objective data are inaccessible.

## Protocol Development And Isolation

v4-v5 were implementation-debugging runs and are not scientific evidence. v6-v8 progressively
localized remaining contract and recovery defects. Each formal successor used fresh tasks:

| Run | Minimum completion | Minimum JSON | Minimum tool success | Estimated cost (USD) |
| --- | ---: | ---: | ---: | ---: |
| v6 | 0.3333 | 0.8955 | 0.8400 | 0.2286 |
| v7 | 0.8333 | 0.9792 | 0.9688 | 0.2494 |
| v8 | 0.8333 | 0.9434 | 0.9333 | 0.2734 |
| v9 final | 0.8333 | 0.9048 | 0.9259 | 0.2782 |

v7 excluded all v6 tasks; v8 excluded v6 and v7; v9 excluded v6-v8 plus 42 historical
v20/v21/v22 identities. The v9 frozen exclusion set contains 150 task IDs and 1,562 Evidence
versions. No calibration threshold was relaxed, and v9 was declared final before its API outcomes.

## v9 Qualification Result

The 12-worker run completed all 36 requested records and wrote an incremental checkpoint. It made
265 successful HTTP calls, with zero fallback and zero requested/selected model mismatch. Seven
individual API responses failed their JSON contract; recovery allowed most rollouts to continue.
Provider telemetry reports 1,151,551 tokens and an estimated `$0.2782318716`; this is not an invoice.

| Model | Runtime | Completed | Valid | Answer correct | Tool success |
| --- | --- | ---: | ---: | ---: | ---: |
| Pro | Direct/Bare | 6/6 | 6/6 | 6/6 | n/a |
| Pro | Scripted Tool | 6/6 | 5/6 | 5/6 | 41/43 |
| Pro | Autonomous Agent | 6/6 | 4/6 | 4/6 | 37/37 |
| Flash | Direct/Bare | 6/6 | 6/6 | 6/6 | n/a |
| Flash | Scripted Tool | 6/6 | 4/6 | 4/6 | 41/44 |
| Flash | Autonomous Agent | 5/6 | 3/6 | 4/6 | 25/27 |

Formal gates:

| Gate | Observed | Requirement | Result |
| --- | ---: | ---: | --- |
| Exact requested models | 1.0000 | exact Pro and Flash | pass |
| Minimum cell completion | 0.8333 | 1.0000 | fail |
| Minimum cell JSON contract | 0.9048 | 0.9500 | fail |
| Minimum valid trajectories | 3 | at least 1 | pass |
| Minimum interactive tool success | 0.9259 | 0.8000 | pass |

The incomplete record was Flash Autonomous on a derived-growth comparison, which exhausted the
frozen cumulative token budget after a contract repair. Independent answer verification also
rejected eight completed-or-attempted interactive records, concentrated in comparison,
derived-growth comparison, registered ratio, and temporal growth. These are retained as negative
qualification evidence; they are not silently dropped.

## Decision

The immutable report decision is:

```text
status = failed
decision = stop_after_factorial_calibration
next_permitted_stage = protocol_repair_only
```

Therefore:

- the reserved 30-task, 1,800-rollout Discovery was not run;
- no state-conditioned materialization or Pro rematerialization contract was opened;
- no GPU or exact-target computation was run;
- Validation and Authorization Objective access remain forbidden;
- `gp_c_evaluated=false` and production `Contribution=0`;
- Flash is not selected as the Explorer.

The scientifically supported conclusion is narrow: under the frozen v9 protocol, Flash did not
qualify for the paired state-discovery experiment. The result does not show that Flash lacks
capability-sensitive states; it shows that the current Host-instrumented contract could not obtain
the preregistered reliability needed to estimate them. More failures are not evidence of more
useful states.

## Implementation Verification

The source and report changes were verified after the API run:

| Check | Result |
| --- | --- |
| Ruff | passed |
| Ruff format on every changed Python file | passed |
| Mypy | passed, 260 source files |
| Pytest | 480 passed in 135.67 seconds |
| API-key pattern scan outside `.env` and artifacts | zero matches |
| New Core domain imports or Finance branches | zero |

The test suite includes failed tool-argument replay, recoverable no-match queries, corrected stop
attempts, cumulative token enforcement, Scripted/Autonomous authority separation, exact model
identity, task/Evidence isolation, checkpoint resume, and fail-closed stage routing.

## Next Permitted Work

Any continuation must use a new experiment identity and fresh tasks. It may redesign the Agent
environment or introduce a separately calibrated intermediate Explorer, but it must not relax v9
thresholds, reuse v9 outcomes to select tasks, or open reserved Discovery/Objective data. The
Objective-support bottleneck from v22 remains independent: changing Explorer models cannot by
itself repair the `99.9443%` Objective micro-split variance share.

Authoritative artifacts:

- `artifacts/vtdo_experiment/finance_v23_explorer_runtime_factorial_v9_20260811/finance_pro_flash_base_contract.json`
- `artifacts/vtdo_experiment/finance_v23_explorer_runtime_factorial_v9_20260811/finance_explorer_runtime_factorial_contract.json`
- `artifacts/vtdo_experiment/finance_v23_explorer_runtime_factorial_v9_20260811/factorial_calibration_rollouts.jsonl`
- `artifacts/vtdo_experiment/finance_v23_explorer_runtime_factorial_v9_20260811/finance_factorial_calibration_report.json`
