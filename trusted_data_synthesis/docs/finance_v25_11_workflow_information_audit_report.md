# Finance v25.11 Workflow Localization And Information Audit

## Decision

v25.11 completed the real Pro/Flash workflow localization and then applied an
independent, offline, fail-closed empirical capability-information audit.

The final decision is:

    Workflow execution: technically passed
    Shared-Tier localization: passed its development gate
    Selected-Tier capability information: failed
    Paired calibration: not authorized
    Pro/Flash ranking: forbidden
    Exact Target / GP-C / Contribution: not evaluated
    Next stage: workflow task redesign only

This is a negative identifiability result for the selected workflow support. It
is not a model ranking and is not a negative GP-C result.

## 1. Immutable Inputs

The source workflow contract contains exactly 63 tasks x 2 workflow Runtimes x
2 model arms x 5 replicas = 1,260 rollouts. The workflow Runtimes are only
scripted_tool and autonomous_agent.

direct_fixed_retrieval remains a positive execution control and is forbidden
from boundary selection and empirical information.

The source report is
finance_matched_tier_localization_report:14189ccf4de1088bba4e1a4559df9de3048b1eecd779e48c3201384fc70a5493.
The offline audit contract is
finance_workflow_information_contract:a425dfb4fd23538a3c02774fe43b8b0cadaf30e8b6f24ea9d2cd489f3bc027ac.
The resulting audit is
finance_workflow_information_audit:0c1318591fb2da331d4c45e35c02016541dbabd54563b1936b9b03683a28144c.

All three source files are content-addressed by SHA-256. The audit reloads and
validates every typed outcome, replays the localization report, and rejects a
changed contract, report, outcome file, denominator, or outcome identity.

## 2. Workflow Execution

| Metric | Result |
| --- | ---: |
| Requested / completed rollouts | 1,260 / 1,260 |
| Technical resolution | 100% |
| Bounded JSON resolution | 100% |
| Observation replay | 100% |
| Authority integrity | 100% |
| Budget / infrastructure failures | 0 / 0 |
| Group-monotone ladders | 53 / 84 |
| API calls | 10,457 |
| Model tokens | 38,067,881 |
| Exact recorded cost | USD 7.3946316566 |

The technical result establishes that the workflow protocol is executable. It
does not establish that the resulting task distribution identifies multiple
model capability directions.

## 3. Selected Shared Tiers

Scripted selected Calculation, Definition reconciliation, Verification,
Recovery, and Stopping, all at Easy Control. Autonomous selected Definition
reconciliation at Frontier and Verification, Recovery, and Stopping at Easy
Control.

Multi-hop retrieval was response-saturated. Branching was at the response
floor. Autonomous Calculation lacked enough independent Ladder-Group support.

| Quantity | Count |
| --- | ---: |
| Runtime-task bindings | 27 |
| Unique tasks | 18 |
| Analyzed rollouts | 270 |
| Source rollouts excluded from primary matrix | 990 |

The 990 records are not discarded. They remain frozen source evidence and
support a complete-ladder sensitivity analysis, but they cannot rescue the
pre-registered selected-Tier gate.

## 4. Runtime Design Audit

| Runtime | Selected families | Distinct normalized demands | Primary-axis aligned | Host-controlled primary |
| --- | ---: | ---: | ---: | --- |
| Scripted | 5 | 4 | 3 | Stopping |
| Autonomous | 4 | 4 | 3 | none |

Recovery Easy Control did not create a primary Recovery contrast in either
Runtime. Scripted Stopping cannot expose model stopping because stopping is
Host-controlled in that Runtime. Calculation, Definition, and Verification
provided the three aligned Scripted directions. Definition, Verification, and
Stopping provided the three aligned Autonomous directions.

These design gates reached their minimum, but only narrowly. They did not
override the empirical matrix gates.

## 5. Primary Empirical Information Result

Each task demand is L2-normalized. The raw second moment is the mean of
p(1-p) times the demand outer product. Only the centered axis diagnostic
removes general difficulty. Bootstrap intervals resample Ladder Groups and
then the five realizations within each task.

| Model | Runtime | Tasks | Boundary fraction | Rank | Effective rank | Condition | Informative axes | Max family share |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Pro | Scripted | 15 | 0.600 | 3 | 1.757 | 401.49 | 3 | 0.601 |
| Flash | Scripted | 15 | 0.667 | 3 | 1.807 | 280.84 | 4 | 0.510 |
| Pro | Autonomous | 12 | 0.750 | 2 | 1.708 | 3.41 | 2 | 0.455 |
| Flash | Autonomous | 12 | 0.333 | 2 | 1.008 | 1,014.39 | 0 | 0.996 |

All four cells failed:

- both Scripted cells failed effective-rank and condition-number gates;
- Pro Scripted also narrowly exceeded the 0.60 family-dominance ceiling;
- both Autonomous cells failed rank, effective rank, and informative-axis
  coverage;
- Flash Autonomous was nearly entirely supported by Verification, with one
  Ladder Group contributing 49.81%.

Every cell already fails at least one rank, effective-rank, or condition gate.
The added family and Ladder-Group dominance diagnostics therefore do not
create the negative decision; they localize where the remaining information is
concentrated.

The result is not caused by a general-difficulty-only factor. The selected
cells' residualized general-factor fractions remained within the frozen 0.85
limit.

## 6. Complete-Ladder Sensitivity

The complete 63-task ladder was analyzed separately and cannot authorize the
next stage.

| Model | Runtime | Boundary fraction | Rank | Effective rank | Condition | Max family share |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Pro | Scripted | 0.349 | 5 | 2.817 | 63.82 | 0.409 |
| Flash | Scripted | 0.508 | 5 | 2.930 | 77.38 | 0.350 |
| Pro | Autonomous | 0.333 | 7 | 3.690 | 144.76 | 0.368 |
| Flash | Autonomous | 0.222 | 7 | 3.162 | 31,422.39 | 0.491 |

Scripted becomes substantially healthier when all three Tiers are retained.
The single-shared-Tier selection removed structural directions that still
carried response-weighted information. Autonomous also recovers numerical
rank, but its conditioning and Flash boundary mass remain insufficient.

The sensitivity rejects two overly broad explanations: the entire ladder has
no capability structure, or the Runtime failed technically. It supports the
narrower conclusion that single-Tier compression plus missing, floor, and
saturated families produced a low-rank authorizing population.

## 7. Next Experiment

v25.12 must be a fresh confirmatory population, not a re-selection evaluated
on the same v25.11 records.

The redesign should:

1. replace one-Tier-per-family selection with a pre-registered multi-Tier
   support rule that preserves response-weighted capability rank;
2. keep task marginal and core semantics matched while allowing more than one
   boundary-bearing Tier per Runtime x Family;
3. add a Scripted recovery condition with real argument-level failure and
   recovery demand instead of the Easy baseline;
4. exclude Scripted stopping as a primary capability family while retaining it
   only as a secondary-demand diagnostic;
5. redesign multi-hop away from the ceiling and branching away from the floor;
6. create Autonomous calculation groups with enough independent support;
7. optimize structural coverage on Development data, then freeze the rule
   before generating fresh tasks or making new API calls;
8. rerun the same four-cell information audit before any paired calibration.

An information-optimal subset selected and evaluated on v25.11 would be
post-selection evidence and is forbidden as confirmatory support.

## Claim Boundary

v25.11 supports complete technical execution, deterministic source replay,
exact cost accounting, some workflow response variation, a low-rank
selected-Tier empirical information result, and evidence that complete-Tier
Scripted support is richer than the selected subset.

It does not support a Pro/Flash capability ranking, selection of either
Explorer, paired calibration, Beneficiary frontier placement, Exact Target,
GP-C, Contribution, a VTDO update, or Student-training claims.
