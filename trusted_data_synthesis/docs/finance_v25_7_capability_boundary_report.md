# Finance v25.7 Capability Boundary Experiment

## Status

v25.7 completed both pre-registered API stages on the frozen v25 task
population:

- Runtime Qualification: 126/126 rollouts completed and all technical gates
  passed.
- Paired Calibration: 1,680/1,680 rollout records were materialized.
- Exact Target, Beneficiary screening, GP-C, and VTDO updates remained
  forbidden.

The paired calibration did not establish empirical capability
identifiability. The correct next stage is task or runtime redesign, not
Contribution authorization.

## Runtime Qualification

The v25.7 budget contract separates 12 required calls from three failed-call
recovery opportunities, for a total cap of 15 calls. This repaired the
self-contradictory v25.6 budget without changing the task population.

Observed technical gates all passed:

- completion rate: 1.0000
- bounded JSON resolution: 1.0000
- bounded tool resolution: 1.0000
- terminal result emission: 1.0000
- observation replay: 1.0000
- authority integrity: 1.0000
- budget exhaustion count: 0

The Qualification stage intentionally treats semantic accuracy as
descriptive. It qualifies the runtime protocol, not model capability.

## Paired Calibration

The calibration consumed 9,638 API calls and 38,641,013 tokens. The recorded
provider estimate was USD 5.02254179. No fallback model was accepted.

All model/runtime cells were response-saturated or response-floor cells. No
family separated Pro from Flash, and the empirical capability information
gate failed closed.

The most important post-run diagnosis is that the Direct Fixed Retrieval cell
contained a compiler/verifier mismatch:

- completed Direct trajectories often had the correct answer;
- their operation and verification steps succeeded;
- every such trajectory failed `allowed_tool_compliance`;
- the public task allowed interactive archive tools, while Direct trajectories
  used `evidence.search` and registered operation tool capabilities.

Therefore, the v25.7 Direct zero-valid rate is not a valid model-floor
measurement. The artifact remains immutable and is not reinterpreted after
repair.

Scripted and Autonomous cells exposed separate empirical problems. Scripted
cells were dominated by repeated failed calls outside the retrieval family.
Autonomous cells were dominated by incorrect answers and incomplete operation,
evidence, and verification lineage. Those outcomes are not fixed by the Direct
tool-identity repair.

## Scientific Decision

v25.7 supports these conclusions:

1. The v25-native iterative API runtime is technically executable under the
   repaired call budget.
2. A Direct Runtime tool-identity defect contaminated one experimental arm.
3. The all-Frontier response design does not locate a usable empirical boundary
   for the interactive arms.

v25.7 does not support these conclusions:

1. Pro and Flash have equal capability on the task population.
2. The Direct Runtime is at a semantic floor.
3. Beneficiary screening or Contribution estimation may begin.

The next protocol must repair Direct tool identity and localize empirical
boundaries across Easy, Frontier, and Hard tiers before another full paired
calibration.
