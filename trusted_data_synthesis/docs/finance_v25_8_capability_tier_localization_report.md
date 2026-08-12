# Finance v25.8 Capability Tier Localization Report

## Status

Finance v25.8 completed the two pre-registered API stages on 2026-08-12:

- Runtime Qualification: 126/126 rollouts;
- Easy/Frontier/Hard Tier Localization: 630/630 rollouts;
- Paired Calibration: not authorized and not run;
- Beneficiary screening, Exact Target, GP-C, and VTDO updates: forbidden.

The immutable experiment identities are:

- contract: `finance_capability_boundary_contract:993641c46b398559e66c293cb07d5ff12dbace20c497545952ceaa763e9e3a5a`;
- Qualification report: `capability_qualification_report:740eadf4798141353cc712a80a6d71cdc6b5481fbdbfaab7e85c634cb7954bdf`;
- Localization report: `capability_tier_localization_report:37b5de050423db61c3147c87dcea4ec2c190faf75124642b659f03921e8c8ea8`.

The frozen artifact directory is
`artifacts/vtdo_experiment/finance_v25_8_capability_tier_localization_v1_20260812`.

## Runtime Qualification

All technical gates passed:

| Gate | Observed | Requirement |
| --- | ---: | ---: |
| Completion | 1.0000 | 1.0000 |
| Raw JSON contract | 0.9934 | >= 0.8500 |
| Bounded JSON resolution | 1.0000 | 1.0000 |
| Bounded tool resolution | 1.0000 | 1.0000 |
| Terminal result emission | 1.0000 | 1.0000 |
| Observation replay | 1.0000 | 1.0000 |
| Authority integrity | 1.0000 | 1.0000 |
| Host verification repair | 0.0000 | <= 0.1500 |
| Budget exhaustion | 0 | 0 |

The v25.7 Direct tool-identity repair worked. No Direct record failed
`allowed_tool_compliance`. Pro and Flash produced 11/21 and 3/21 valid Direct
responses respectively, so the former all-zero Direct result cannot be reused.

Qualification consumed 762 API calls and 3,317,740 model tokens. The recorded
provider estimate was USD 0.431691. No fallback model or HTTP failure occurred.

## Tier Localization

Localization evaluated one frozen task per Family x Tier, five replicas per
Model x Runtime cell:

```text
7 families x 3 tiers x 2 models x 3 runtimes x 5 replicas = 630
```

The pre-registered boundary-family results were:

| Runtime | Identified families | Required | Ready |
| --- | ---: | ---: | --- |
| Direct Fixed Retrieval | 6/7 | 2 | yes |
| Scripted Tool | 1/7 | 3 | no |
| Autonomous Agent | 1/7 | 4 | no |

Only 33/42 Model x Runtime x Family response ladders were monotone from Easy to
Frontier to Hard, for a monotonic-response fraction of 0.7857. Consequently:

```text
all_runtime_localization_ready = false
calibration_frontier_compatible = false
next_permitted_stage = task_or_runtime_redesign_only
```

The selected diagnostic tiers were:

| Runtime | Family | Selected tier |
| --- | --- | --- |
| Direct | multi-hop retrieval | Easy |
| Direct | branching operation | Hard |
| Direct | calculation chain | none |
| Direct | definition reconciliation | Frontier |
| Direct | verification-sensitive selection | Hard |
| Direct | recovery-guided search | Easy |
| Direct | stopping decision | Frontier |
| Scripted | multi-hop retrieval | Frontier |
| Scripted | all other families | none |
| Autonomous | definition reconciliation | Easy |
| Autonomous | all other families | none |

These selections are diagnostics, not a replacement calibration population.
The Runtime failures below invalidate a direct model-capability interpretation
for several cells.

### Aggregate response

| Model | Runtime | Tier | Technical | Semantic | Valid |
| --- | --- | --- | ---: | ---: | ---: |
| Pro | Direct | Easy | 1.000 | 0.543 | 0.400 |
| Pro | Direct | Frontier | 1.000 | 0.514 | 0.514 |
| Pro | Direct | Hard | 1.000 | 0.400 | 0.400 |
| Flash | Direct | Easy | 1.000 | 0.286 | 0.229 |
| Flash | Direct | Frontier | 1.000 | 0.086 | 0.086 |
| Flash | Direct | Hard | 1.000 | 0.114 | 0.114 |
| Pro | Scripted | Easy | 1.000 | 0.000 | 0.000 |
| Pro | Scripted | Frontier | 1.000 | 0.086 | 0.086 |
| Pro | Scripted | Hard | 0.743 | 0.000 | 0.000 |
| Flash | Scripted | Easy | 1.000 | 0.000 | 0.000 |
| Flash | Scripted | Frontier | 1.000 | 0.114 | 0.114 |
| Flash | Scripted | Hard | 0.686 | 0.000 | 0.000 |
| Pro | Autonomous | Easy | 1.000 | 0.171 | 0.171 |
| Pro | Autonomous | Frontier | 1.000 | 0.000 | 0.000 |
| Pro | Autonomous | Hard | 1.000 | 0.029 | 0.000 |
| Flash | Autonomous | Easy | 1.000 | 0.200 | 0.200 |
| Flash | Autonomous | Frontier | 1.000 | 0.000 | 0.000 |
| Flash | Autonomous | Hard | 1.000 | 0.000 | 0.000 |

Localization consumed 3,891 API calls and 18,241,658 model tokens. The
provider estimate was USD 2.429892. Combined with Qualification, v25.8 used
4,653 calls, 21,559,398 tokens, and an estimated USD 2.861583. There were no
fallbacks, HTTP failures, or Runtime infrastructure failures.

## Post-run Contract Audit

### Direct selector contradiction

All 30 Direct Calculation Chain observations failed the same typed action
contract before host execution. The public plan skeleton froze raw Evidence
inputs with `selector = null`, while the final model-visible baseline topology
instructed the model to use `selector = value`. Pro and Flash followed the
stronger final instruction and were rejected by `public_selector_mismatch`.

This is a compiler/prompt/verifier contradiction, not evidence that both
models are incapable of the calculation tasks. The Direct Calculation zero
cell must not enter an empirical information matrix.

### Scripted evidence-selection omission

The frozen Scripted sequence can compile `search_archive -> normalize`.
However, `search_archive` only discovers Evidence and exposes locators;
`normalize_metric_unit_period`, `calculator`, and verification require Evidence
that has been selected by `open_document` or `query_structured_fact`.

The failure telemetry reflects this mismatch:

- repeated identical failed calls: 70 Easy, 53 Frontier, and 46 Hard records;
- model-token exhaustion: 20 Hard records;
- failed-tool budget exhaustion: 3 Hard and 2 Frontier records.

The v25 structural minimum-call counter omitted this executable selection
transition. Scripted floor cells therefore measure a sequence compiler defect
as well as model behavior.

### Autonomous failure profile

Autonomous technical execution remained stable, but semantic completion was
usually at the floor. Dominant independent verifier failures were:

- wrong answer;
- operation lineage not covering Gold Evidence;
- verification support not covering Gold Evidence;
- incomplete citation and selected-evidence coverage;
- stopping before successful verification.

Unlike the two deterministic contradictions above, this is currently
consistent with a genuine model/runtime capability floor. It should be tested
again only after the shared task and tool contracts are repaired.

### Tier-instance confounding

Localization used one task per Family x Tier. The v25 population has three Easy,
five Frontier, and two Hard tasks per family, but it has no frozen matched
Easy/Frontier/Hard ladder-group identity. Non-monotone cells can therefore
reflect task-instance variation rather than tier response. A follow-up must use
matched ladder groups or multiple tasks per tier and retain task-level effects.

## Immutable Replay And Authorization

Re-running the Localization command resumed 630/630 records, executed zero API
jobs, and reproduced the exact report ID and outcome-set hash. A direct attempt
to start Paired Calibration failed before model configuration or API access
with:

```text
paired calibration is not authorized by Tier Localization replay
```

This confirms that the negative decision cannot be bypassed by a CLI stage
selection.

## Scientific Decision

v25.8 supports these claims:

1. the repaired v25-native API runtime is technically executable;
2. the v25.7 Direct allowed-tool result was a verifier artifact;
3. an all-Frontier calibration is not justified;
4. current Scripted and Direct Calculation measurements still contain
   deterministic contract defects;
5. the current Autonomous runtime is at or near a semantic floor for most
   families.

v25.8 does not support these claims:

1. Pro and Flash have equal capability;
2. Flash is a better VTDO Explorer;
3. the selected diagnostic tiers are a valid replacement population;
4. the empirical capability information matrix is identifiable;
5. Beneficiary screening, Exact Target, GP-C, or VTDO updates may begin.

## Required Next Experiment

The next experiment must be a fresh, versioned Runtime and sampling repair:

1. make the Plan-Given public selector contract internally consistent;
2. compile Scripted Evidence selection explicitly before normalization or
   calculation and recompute executable minimum-call structure;
3. freeze matched ladder-group identities or sample multiple tasks per tier;
4. run a small technical/semantic regression before another localization;
5. repeat tier localization on fresh tasks;
6. run Paired Calibration only if the new localization report authorizes it.

The v25.8 artifacts remain immutable and must never be re-scored after these
repairs.

