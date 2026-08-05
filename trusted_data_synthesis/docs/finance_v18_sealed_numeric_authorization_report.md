# Finance v18 Sealed Numeric Authorization

Experiment date: 2026-08-06

## Decision

The inherited sealed Finance population passed the frozen v17 numerical execution contract under
the only authorized profile, `fp32_activation_strict`.

This result closes the numerical authorization stage:

- `sealed_numeric_contract_passed=true`;
- `production_authorized=false`;
- `contribution_authorized=false`;
- the only allowed next stage is
  `preregister_contribution_authorization_experiment`.

The experiment does not establish that GP-C predicts finite intervention utility. It does not
authorize a VTDO distribution update, production synthesis, Student training, or a downstream
performance claim.

## Frozen Population

The sealed population was inherited without replacement from the three-way v17 split:

- six Finance tasks, one from each active task family;
- 20 quotient trajectory states;
- three independently verified realizations per state;
- 60 total state-conditioned realizations;
- 20 preregistered diagnostic jobs, selected as the lowest realization index per task-state;
- zero overlap with the v17 development and validation task, Evidence-version, and semantic
  partitions.

The source lineage remained fixed to:

- numeric contract:
  `finance_gradient_numeric_contract:e2a1c890af575f477389b0bfb1475810aeecec3e5f4bf3a6213c552a82fa86b7`;
- task set:
  `finance_gradient_calibration_task_set:884e85bc9a8f531c8fe36aab2920dc0ff1432428b1c0efca61122b92767cf034`;
- initial distribution report:
  `finance_initial_distribution_report:24e65aa9e663264f6e028a26feb1f18c83390defd684898c018471eb4095af38`;
- state realization report:
  `finance_state_realization_report:dfcead48218389cf3bfe6b16b630510727770a70c89ca0de9ffa90af13a296fd`;
- authorization objective-gradient manifest:
  `finance_contribution_evaluation_gradient_manifest:94e767938b1b9f47222b5a17b03d617a275c72408449a38a1fd21cde5fa8decf`.

The source manifest records one recoverable `LLMClientError` during state generation. The final
state artifact nevertheless contains all 60 required realizations, and the frozen DeepSeek route
had no fallback model. The numerical run made no API calls.

## Pre-observation Execution Recovery

The first execution attempt is preserved as immutable negative engineering evidence:

- plan:
  `finance_gradient_numeric_sealed_plan:c64af960ddd164defbccd3a8c7fc8ad5e50f7fff247a880dbc16aef5825d02c5`;
- result:
  `finance_gradient_numeric_sealed_result:bb7665addb22d6bca8a965e46bdc496dff8fb309f3a8e0ee2981fef7a478dc25`;
- status: `execution_failed`;
- error: `KeyError('jobs')`;
- checkpoint count: 0;
- numeric summary present: false.

The failure occurred after model loading but before the first state job. The checkpoint loader read
`jobs` from the outer source manifest, while the frozen schema stores jobs in the nested source
descriptor. No sealed state metric was computed or exposed.

A new retry plan was therefore scientifically admissible. Its explicit retry contract allows only
`source_manifest_checkpoint_job_lookup_only` and freezes all scientific inputs unchanged:
task set, trajectories, realizations, authorization objective gradient, numeric profile, thresholds,
uncertainty envelope, and gradient seed.

Retry identities:

- plan:
  `finance_gradient_numeric_sealed_plan:1084b81bc24f341aabced0fe0649913dc1163495736ed6461605fd5714850313`;
- implementation SHA-256:
  `1e9533f4c67096874ba28aa3f28e0319ed9e8d2d609d08b92f0d2197e6ad285a`;
- source:
  `finance_gradient_numeric_sealed_source:6a58465d7121e0606a1d69fa501ca086da8b0925ba9509cae6da6c793d74630a`.

## Numeric Results

All 20 diagnostic checkpoints were computed in the retry run. No checkpoint was resumed.

| Gate | Observed | Frozen threshold | Result |
| --- | ---: | ---: | --- |
| Maximum GP-score absolute delta | 0.00081042 | <= 0.0023 | passed |
| Maximum gradient relative error | 0.00633034 | <= 0.027 | passed |
| Minimum recomposition cosine | 0.99997997 | >= 0.99967 | passed |
| Maximum loss identity error | 5.31e-8 | <= 1e-6 | passed |
| Maximum update JS | 3.37e-9 | <= 1e-6 | passed |
| Maximum update TV | 0.00005026 | <= 0.00023 | passed |

Margin-aware ordering also passed:

- 24 of 25 state pairs were resolvable under the frozen `0.0011` envelope;
- resolvable-pair direction agreement: 24/24;
- task winner agreement: 6/6;
- strict task permutation agreement: 6/6;
- ordering violations: 0.

The retry result and aggregate identities are:

- result:
  `finance_gradient_numeric_sealed_result:ed13f8f07830ad47471293a8c73c22f464844959699b1b91d7c6cc99c94721d2`;
- report:
  `finance_gradient_numeric_sealed_report:2cdddbc561c67cbcca6728d2a1a54c6fa89a80c3b499f4e22d4097947a36c745`.

## Runtime

The one-shot GPU run used A100 devices 3, 4, and 5:

- runtime: 2,665.88 seconds;
- completed before resume: 0;
- completed in this run: 20;
- peak allocated memory: approximately 16.7, 22.8, and 26.6 GiB.

The result was produced under PyTorch `2.7.1+cu128`.

## Claim Boundary

The supported claim is narrowly:

> The frozen FP32 activation Gradient Projection execution path satisfies its preregistered
> numerical decomposition and ordering contract on the untouched inherited sealed population.

The experiment does not support:

- GP-C Contribution validity;
- prediction of independent finite intervention utility;
- a production VTDO update;
- a Student training gain;
- model or data-release superiority.

The next experiment must be separately preregistered, use independent Contribution estimation and
finite-intervention targets, and preserve this numeric profile without post hoc threshold changes.

## Verification

After the implementation repair and completed experiment, an independent read-only replay:

- verified the plan and source canonical identities;
- verified all 20 checkpoint identities and their frozen job order;
- replayed the result and aggregate canonical identities;
- recomputed the complete numeric and ordering summary from checkpoint rows;
- matched the persisted summary after JSON container normalization.

Repository validation then reported:

- focused sealed-candidate tests: 6 passed;
- Ruff: passed;
- Mypy: passed for 237 source files;
- full Pytest: 379 passed in 116.96 seconds;
- Core generalization, Legal contracts, and Science contracts remained covered by the full suite.

## Artifacts

Authoritative directory:

`artifacts/vtdo_experiment/finance_v17_sealed_numeric_candidate_retry_v2_20260806/`

File SHA-256 values:

- `plan.json`: `1f47d7a624f508dbc53220300ec99dc986138ed46c3467f102f9bc4a94c96615`;
- `source_manifest.json`: `aa3e2f1ee24cf6e6f92bc3b0b4dd32ef14654ac8b1a7a16b5213e11688568ede`;
- `result.json`: `5917c27162a8211add2e3fdc5028f6fd39041b639e85f525500d7a2197eb686f`;
- `report.json`: `d42da48ee44a872c3b797a4f0c8fa4c0807db937e9b6e2d64577bb71aa1322dd`.
