# Finance v13 Real-Agent and Gradient Projection Smoke

Date: 2026-08-04

## Decision

The v13 smoke establishes an executable real-Agent-to-gradient path over archived public finance
evidence. It does not authorize a production Contribution estimate. Agent state control, exact
state materialization, objective gradients, state gradients, and aggregation all executed with
immutable artifacts. The final Gradient Projection report remains `partial` and
`production_authorized=false`.

## Frozen inputs

- Finance archive KG: `kg_20260711_062123_bc4b4394`.
- Beneficiary: local Qwen2.5-7B LoRA checkpoint
  `qwen_beneficiary_checkpoint:4cb8b6730b3299ddb31a0b3b08c85443867c8597f9786f8b9fb557488f2c3a4e`.
- Explorer: `deepseek-v4-pro`, selected exactly; no fallback model was used.
- Agent population artifact SHA-256:
  `92551c56a9034c187509db490c8fcba306b9ccae2f59e05e23321caf40bd588d`.
- State realization SHA-256:
  `27d8909ffe8a5e322478b81fdff407f95c08572dc0692155d6adbb99c2778639`.
- GP v10 plan hash:
  `finance_contribution_gradient_plan:f3ac15078b6a363b8ae9dbf09bcc00ba6de2e9dc737e2b9e605a18af773b5dfa`.

## Population and Agent funnel

The rebuilt State Space v3 population attempted 31 tasks, accepted 30, and rejected one
host-blocked state catalog. The accepted population contains 100 states, all requestable. Task
coverage is: comparison 5, derived-growth comparison 10, registered ratio 5, temporal absolute
change 3, temporal average 3, and temporal growth 4.

The six-family initial-distribution run requested 24 trajectories and produced 24 complete,
catalog-valid observations over six tasks. All six task distributions have full support and are
nonuniform. It used 72 successful API calls and 402,098 tokens.

The state-realization run requested 20 target states and released all 20 with exact diagonal
target-state control. It recorded 41 generation attempts: 40 successful generation records and one
typed `LLMClientError`; retries still produced all requested released realizations. It used 127
successful API calls and 1,015,767 tokens.

Across the six-family runs, API use was 199 successful calls and 1,417,865 tokens. The provider
configuration estimated cost at 0.345717497. Including the earlier two-task control run, this
session used 1,959,457 tokens with a configuration estimate of 0.472828267. These are configuration
estimates, not provider invoice totals.

## GP execution contract

GP v10 uses:

1. exact sparse causal loss: only predecessor positions of supervised labels materialize vocabulary
   logits;
2. deterministic objective mode: stochastic children remain in eval mode while checkpoint wrappers
   recompute activations;
3. a strict CUDA whitelist: nonselected devices receive zero placement capacity and the resolved
   Hugging Face map is sealed in the manifest;
4. one shared decoder forward for full, common-token, and differential-token losses;
5. no sequence truncation beyond the already frozen 24,576-token contract and no relaxed quality
   threshold.

A loader-only whitelist replay selected physical GPUs 6 and 7. The resolved map placed embeddings
and layers 0--14 on GPU 6 and layers 15--27, norm, rotary embedding, and LM head on GPU 7; no other
device appeared in the map.

The longest frozen record contains 22,909 processed tokens. Objective gradients completed on one
A100 rather than the four-card workaround: eight record gradients plus estimation and validation
aggregates completed in 61.36 seconds with 30,877,878,784 peak allocated bytes on GPU 2.

Eleven state realizations produced 33 gradient artifacts: full, common-token, and
differential-token gradients for each state. Four workers completed partitions of 3/3/3/2 states.
The slowest worker took 81.20 seconds; per-worker peak allocation ranged from 30,716,343,296 to
31,462,938,112 bytes.

## Aggregate result

The final report hash is
`finance_contribution_gradient_report:f6b4dca38daa9c45b99bbd2a9b1348a6da691674bce2450876b9b3f601050c9e`.
It reports:

| Metric | Result |
| --- | ---: |
| Tasks / states / realizations | 3 / 11 / 11 |
| Objective records per split | 4 |
| Macro task Spearman | 0.2333 |
| Macro pairwise concordance | 0.6000 |
| Winner agreement | 0.6667 |
| Minimum differential token fraction | 0.05158 |
| Minimum differential gradient fraction | 0.27591 |
| Minimum recomposition cosine | 0.999846 |
| Maximum gradient recomposition relative error | 0.01793 |

The common/differential loss weighted sum recovers the full loss with maximum absolute error
`5.27e-8`. The remaining 1.793% gradient discrepancy is finite-precision BF16 VJP disagreement,
not a token partition or loss-weighting error. It still fails the frozen `1e-4` gradient
recomposition gate and is not waived.

The final blockers are:

- `gradient_realization_instability`: smoke has one realization per state, so effective sample size
  is 1.0 rather than the required 1.5; the BF16 recomposition bound also fails;
- `post_global_update_gp_c_not_run`;
- `independent_local_distribution_intervention_not_run`.

## Failure evidence retained

The experiment did not hide failed attempts:

- full-logit v7 runs exhausted one, two, and four A100 placements;
- sparse v8 completed numerical gradients but Accelerate escaped the requested GPU set; its manifest
  is retained as `evaluation_gradient_manifest.invalid_unrestricted_device_map.json` and is not
  eligible evidence;
- v9 completed objective and state gradients, but three independent region forwards produced a
  1.993% maximum recomposition error;
- v10 shared the forward graph and reduced that error to 1.793%, while proving loss decomposition
  to `5.27e-8`.

## Next admissible experiment

A production candidate must be a new run identity. It requires at least 30 tasks, 3--5 independent
realizations per state, 16 estimation and 16 validation objective records, a sealed authorization
split, a preregistered finite-precision decomposition policy, post-global-update GP-C, and the
independent local distribution intervention. No v13 smoke artifact can be promoted in place.
