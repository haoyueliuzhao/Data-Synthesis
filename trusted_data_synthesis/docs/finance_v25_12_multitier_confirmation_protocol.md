# Finance v25.12 Multi-Tier Confirmation Protocol

## Status

v25.12 is a fresh, Flash-first confirmation experiment. It responds to the v25.11
negative identifiability result without reusing v25.11 outcomes for confirmation and
without reopening Beneficiary, Exact Target, GP-C, Authorization, or VTDO updates.

The current implementation status is `flash_stage_ready`. No v25.12 model outcome was
used to construct the population, select the support rule, or choose Pro anchors.

## Scientific separation

The experiment has three immutable layers:

1. v25.11 Development outcomes compare candidate multi-Tier support policies.
2. a fresh v25.12 population independently confirms the selected policy with Flash;
3. Pro is invoked only on a preregistered sparse anchor subset, and only if every Flash
   information cell passes.

DeepSeek is used to generate real Host-instrumented Agent trajectories. It is not used to
rewrite or polish the public tasks after construction. Public instructions, Evidence,
Programs, support rules, and anchor identities are frozen before the first API response.

## Development policy

The policy builder reads the frozen 1,260-rollout v25.11 Development run and evaluates four
multi-Tier supports. Scripted Branching and Stopping are secondary-only because their primary
Planning and Stopping axes are Host-controlled. Recovery Easy is also secondary-only because
it has no typed failure/recovery contrast.

The primary criterion is the worst Model x Runtime regularized residual-information log
determinant. Ties are resolved by effective rank, numerical rank, condition number, and
Family/Group dominance in that order.

| Candidate | Worst logdet | Min rank | Min effective rank | Max condition | Max family share | Max group share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| complete ladder | -69.609 | 5 | 2.719 | 14761.15 | 0.491 | 0.252 |
| easy + frontier | -70.155 | 5 | 2.503 | 6964.70 | 0.482 | 0.277 |
| frontier + hard | -75.216 | 5 | 2.369 | 8791.40 | 0.491 | 0.309 |
| easy + hard | -73.737 | 5 | 2.480 | 10398.42 | 0.539 | 0.280 |

The selected candidate is the conditional complete ladder. This is not a claim that the
Development information gates pass: the large worst-cell condition number remains a
known failure. Selection only determines which support is tested on fresh tasks. The fresh
Flash report must independently satisfy all frozen information gates.

## Fresh population

The v25.12 population contains:

- 7 capability families;
- 3 matched groups per family;
- Easy, Frontier, and Hard workflow variants per group;
- 21 groups and 63 public tasks;
- 189 static Runtime satisfiability records across Direct, Scripted, and Autonomous.

All 189 static contracts pass. Direct remains a static positive execution control and does
not enter the empirical information matrix.

Freshness is enforced at three levels:

- Task semantic signature;
- Evidence ID;
- Evidence Version ID.

The preflight excludes 470 historically exposed Evidence Versions. The fresh population
has zero Evidence-Version overlap with v25.11 and prior frozen exposures. Capacity remains
21 groups and 63 tasks after this exclusion.

## Task corrections

The core Program tier is selected by family before workflow variants are generated:

| Family | Core Program tier |
| --- | --- |
| Multi-hop retrieval/join | Hard |
| Branching operation plan | Easy |
| Calculation chain | Frontier |
| Definition reconciliation | Frontier |
| Verification-sensitive selection | Frontier |
| Recovery-guided search | Frontier |
| Stopping decision control | Frontier |

This makes Multi-hop structurally harder and Branching structurally easier while preserving
the same Gold Evidence, Program, answer, and semantic identity across the three workflow
variants within a matched group.

Recovery Frontier and Hard tasks freeze a typed Runtime intervention. The first otherwise
successful structured query returns a typed failure. Repeating the same selector is rejected;
the Agent must change a public subject, metric, period, or filter selector. The corrected
query must then succeed, and the entire observation sequence is independently replayed.

Comparison answers now project internal Evidence references to frozen public entity labels
before Oracle/Candidate equivalence. The difference remains the canonical non-negative
absolute difference produced by the comparison operator.

## Asymmetric model design

Flash is the primary Explorer. Pro is a sparse strong-capability anchor.

| Stage | Support | Replicas | Rollouts |
| --- | --- | ---: | ---: |
| Flash full support | 63 tasks x 2 workflow Runtimes | 5 | 630 |
| Pro sparse anchor | 1 preregistered group/family x 3 tiers x 2 Runtimes | 3 | 126 |

The Pro/Flash rollout ratio is 0.20. Pro group identities are selected by a frozen salted
hash before fresh outcomes exist. No Pro/Flash ranking claim is authorized by this design.

The Pro stage is unavailable unless both Flash Scripted and Flash Autonomous cells pass:

- residual numerical rank;
- residual effective rank;
- residual condition number;
- boundary-task fraction;
- general-factor fraction;
- informative-axis count with bootstrap lower bounds;
- Family information dominance;
- Ladder Group information dominance;
- Runtime primary-axis alignment.

Scripted Branching and Stopping are excluded from the primary matrix and retained as secondary
diagnostics. Recovery Easy is also secondary-only. The other selected Family/Tier supports
are shared across groups and are not selected from fresh outcomes.

## Fail-closed transitions

```text
population/static contract failure
  -> multitier_population_repair_only

Flash technical failure
  -> runtime_contract_repair_only

Flash information failure
  -> flash_support_or_task_redesign_only

Flash technical + information pass
  -> pro_sparse_anchor

Pro technical/anchor failure
  -> pro_anchor_or_runtime_repair_only

Flash pass + Pro sparse anchor pass
  -> beneficiary_boundary_screening_preparation
```

Even the final transition authorizes only preparation of a separately frozen Qwen2.5-7B
Beneficiary screen. It does not authorize Exact Target, GP-C, Contribution, or training.

## Reproducibility and cost controls

Both stages use immutable contracts, content hashes, model discovery evidence, append-only
checkpoints, complete denominator validation, and parallel workers. The default worker counts
are 32 for Flash and 16 for Pro. A resumed completed stage performs no API call and requires
the original model-discovery artifact.

Every report records API calls, model tokens, and provider-estimated cost. Flash failure stops
the experiment before any Pro call, preventing an expensive 1:1 comparison on another
low-information population.

## Offline preflight

- Ruff: passed for touched modules and tests;
- targeted Mypy: passed;
- focused capability/runtime tests: 41 passed;
- strict Evidence-disjoint population: 21/21 groups, 63/63 tasks;
- static public contracts: 189/189 passed;
- frozen Development policy: built and replayed;
- confirmation contract: 630 Flash + 126 Pro, next stage `flash_full_support`.

These results establish experiment readiness only. Empirical Flash/Pro results must be added
after the staged API run.
