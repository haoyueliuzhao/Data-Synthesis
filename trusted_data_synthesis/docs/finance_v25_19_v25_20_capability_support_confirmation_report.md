# Finance v25.19-v25.20 Capability-Support Confirmation Report

Audit date: 2026-08-13

## 1. Decision

v25.19-v25.20 executed the independent experiment prescribed by the v25.18 audit:

```text
v25.18 Development evidence
  -> frozen Runtime x family support policy
  -> fresh real-Finance source extension
  -> 35 new matched ladder groups
  -> five replicas per selected task
  -> Flash-only Runtime and information confirmation
```

The measurement instrument passed. The response-weighted capability geometry did not pass every
frozen information gate. This is a task-support result, not a Runtime failure, a Flash failure, or
a Contribution result.

```text
runtime_qualification_passed = true
information_matrix_ready = false
pro_sparse_anchor_authorized = false
beneficiary_screening_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = capability_task_support_redesign_only
```

No Pro call, local GPU computation, Objective access, model ranking, or VTDO update occurred.

## 2. Preregistered Changes

The v25.18 Runtime, Agent prompt, Host responsibilities, tool environment, terminal taxonomy, and
information thresholds remained frozen. v25.19 changed only task-support development:

1. five independent matched groups were required for each of seven capability families;
2. each selected Runtime binding received five independent replicas;
3. Scripted Planning and Stopping remained excluded because the Host owns those decisions;
4. saturated families were pushed toward harder structural support;
5. floor and mixed families retained adjacent Tier probes rather than being selected from fresh
   Confirmation responses;
6. Family and Ladder-Group information dominance were added as fail-closed gates;
7. correctness remained a model response, never a Runtime-qualification gate.

The policy was frozen before constructing or observing the fresh Confirmation population. Its ID
is:

```text
finance_capability_support_development:
c495d9618dba97b940adc7286e8c361ac43907432c8f6fccdccdb28b6e2e14ff
```

## 3. Capacity And Freshness

The original source pool could produce only three fresh Verification groups. The build stopped
instead of lowering the five-group requirement. A new real-Finance source extension was then
materialized from the immutable Archive while excluding 4,488 earlier public Evidence Versions.

| Source-extension item | Result |
| --- | ---: |
| Accepted tasks | 420 |
| Accepted/requestable states | 1,466 / 1,466 |
| KG build | `kg_20260711_062123_bc4b4394` |
| Extension status | passed |

The resulting v25.20 population contains 35 matched groups and 105 static Tier variants. Sixty
Runtime-specific bindings select 50 unique tasks. Every static public contract passed. Freshness
overlap was zero for all six preregistered channels:

| Freshness channel | Overlap |
| --- | ---: |
| Task artifact | 0 |
| Matched group | 0 |
| Evidence ID | 0 |
| Evidence Version ID | 0 |
| Core semantic signature | 0 |
| Task signature | 0 |

The population and contract IDs are:

```text
finance_capability_support_population:
5a9a440a8081b0019bc9d9079d0c80c5f850ec9fd9cea65be8f77c254fefe02f

finance_capability_support_confirmation_contract:
ee2e70271df233466cc127057538016cf21efc8daacf8b5c982b8de91ecc426c
```

## 4. Online Execution

All 300 requested Flash rollouts completed with 32 parallel workers. Checkpoint, canonical record,
outcome, and terminal-outcome files each contain exactly 300 rows. The aggregation resumed from
the complete checkpoint and executed zero replacement jobs after the sparse-Tier reporting fix.

| Execution item | Result |
| --- | ---: |
| Requested / recorded | 300 / 300 |
| Runtime eligible | 300 |
| API calls | 3,698 |
| Provider-reported model tokens | 21,388,724 |
| Telemetry-derived cost estimate | USD 2.454394 |
| Pro API calls | 0 |

The cost value is a telemetry-derived estimate, not an authoritative provider invoice.

All global and per-Runtime instrument gates passed:

```text
API transport resolution       100%
bounded JSON resolution        100%
Observation replay             100%
authority integrity            100%
terminal resolution            100%
failure attribution            100%
L0 external failure              0%
L1 Runtime-contract failure      0%
L2 tool-environment failure      0%
unattributed failure             0%
prompt pathology                 0%
```

The 145 failures were all capability observations: 117 L4 Agent-decision failures and 28 L5
semantic failures. There was no measurement-instrument failure.

## 5. Capability Responses

| Runtime | Rollouts | Valid success | Boundary tasks |
| --- | ---: | ---: | ---: |
| Scripted Tool | 125 | 52.00% | 56.00% |
| Autonomous Agent | 175 | 51.43% | 68.57% |
| Combined | 300 | 51.67% | 85.19% of evaluated cells |

Combined Tier success was 44.44% for Easy Control, 60.00% for Frontier, and 45.00% for Hard
Control. These rates are descriptive responses. They are not Runtime gates and should not be read
as a monotonic semantic ladder across different Runtime-family allocations.

The primary-axis diagnostics localize the remaining support problem:

| Runtime | Axis | Success | Interpretation |
| --- | --- | ---: | --- |
| Scripted | Retrieval | 100.00% | ceiling |
| Scripted | Calculation | 77.60% | informative but high |
| Scripted | Reconciliation | 80.80% | informative but high |
| Scripted | Verification | 52.00% | boundary |
| Scripted | Recovery | 31.67% | boundary, 12 opportunity tasks |
| Autonomous | Retrieval | 100.00% | ceiling |
| Autonomous | Planning | 51.43% | boundary |
| Autonomous | Calculation | 98.29% | ceiling |
| Autonomous | Reconciliation | 0.00% | floor |
| Autonomous | Verification | 67.43% | boundary |
| Autonomous | Recovery | 28.00% | boundary, 5 opportunity tasks |
| Autonomous | Stopping | 67.43% | boundary |

## 6. Information Geometry

| Runtime | Final rank | Final effective rank | Final condition | Joint effective rank | Joint condition | Max family share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Scripted Tool | 5 | 2.499 | 267.23 | 2.603 | 139.21 | 29.67% |
| Autonomous Agent | 7 | 2.799 | 92.46 | 2.935 | 96.93 | 44.13% |

The five-group redesign substantially improved v25.18:

- both Family dominance gates passed;
- both Group dominance gates passed;
- Scripted boundary mass increased from 14.29% to 56.00%;
- Autonomous boundary mass increased from 33.33% to 68.57%;
- Autonomous condition numbers moved below 100;
- all seven Autonomous marginal axes had positive Bootstrap lower bounds.

Four frozen gates still failed:

```text
Scripted final_valid_condition_number       267.225 > 100
Scripted joint_condition_number             139.206 > 100
Autonomous final_valid_effective_rank          2.799 < 3
Autonomous joint_effective_rank                 2.935 < 3
```

The new result therefore removes replica quantization and group scarcity as primary explanations.
Information is still concentrated because Retrieval remains saturated, Autonomous Calculation is
nearly saturated, and Autonomous Reconciliation remains at the floor.

## 7. Scientific Interpretation

v25.20 supports three claims:

1. the v25.18 Agent Runtime is a stable capability-measurement instrument on a larger fresh set;
2. more independent groups and five replicas materially improve response-geometry estimation;
3. selecting among the existing Tier variants is insufficient to make every capability direction
   informative.

It does not support claims about Pro--Flash ranking, Beneficiary boundaries, Exact Target, GP-C,
Contribution, VTDO optimization, or Student utility.

The next redesign must change irreducible capability mechanisms, not merely add replicas:

- Retrieval: require disambiguating multi-hop joins with adversarially plausible distractors;
- Calculation: require dependent multi-stage arithmetic and unit/period normalization;
- Reconciliation: introduce a genuine Bridge program between trivial compatibility and total
  definition conflict;
- Recovery: create independent failure-and-revision opportunities across several families;
- Scripted geometry: decorrelate Calculation, Reconciliation, Verification, and Recovery demands.

The redesigned tasks must be frozen on a new Development split and confirmed on another
task-, group-, Evidence-, and semantic-signature-disjoint population. Frozen information gates
must not be relaxed. Pro remains blocked until both Flash Runtime cells pass.

## 8. Immutable Artifacts

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/vtdo_experiment/
  finance_v25_19_capability_support_development_v1_20260813/
  finance_v25_20_agent_source_extension420_v2_20260813/
  finance_v25_20_capability_support_population_v2_20260813/
  finance_v25_20_capability_support_confirmation_contract_v1_20260813/
  finance_v25_20_capability_support_confirmation_v1_20260813/
```

The final report ID is:

```text
finance_capability_support_confirmation_report:
b64351383f2a024a786e767b15375bfae43577b72fb2ed8943e84fdafe43cf9b
```
