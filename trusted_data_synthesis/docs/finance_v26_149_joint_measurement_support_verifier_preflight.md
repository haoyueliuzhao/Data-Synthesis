# Finance v26.149 Joint Measurement Support And Verifier vNext Preflight

Audit date: 2026-08-25

## Decision

Finance v26.149 consumed only the credential-free
`measurement_support_verifier_vnext_joint_preflight_only` transition authorized by v26.148. It
binds the v26.146 Measurement Support Contract to the v26.148 Verifier vNext Contract in one
prospective state machine and exercises the combined boundary before any fresh Capability
identity exists.

The joint preflight passes. The only permitted successor is:

```text
fresh_capability_population_and_runner_rematerialization_preflight_only
```

This stage does not materialize a Capability or Reachability TaskPackage, Path, Contract,
Manifest, Job, Runner, execution, or report identity. It does not rescore a historical row,
construct a model client, call a Provider, run State Mapping, or create a training, release, or
production row.

## Source Integrity

The exact direct predecessor is v26.148 report
`finance_v26_verifier_vnext_freeze_report:3d75e805997c2511626db93cafc095a2a21bf988d6269cfdb6bd9e953788ff75`,
SHA-256 `93a300c4a2284fe2213a7797940912490a9894b8e9ff0e4183db6a849bfa335e`,
and transition
`finance_v26_verifier_vnext_transition:eab4f37ae38bc033981ab72b2b38a4fc939a52d8e353349a540baca35b4172d9`.

Before loading the joint Runtime, v26.149 replayed 7,332/7,332 files:

```text
v26.148 transitive bindings             7,318
v26.148 direct formal outputs               12
v26.149 implementation files                 2
total                                    7,332
```

It rebuilt the complete twelve-file v26.148 formal directory in an empty temporary directory.
Every file was byte-identical. Historical Capability terminals and labels remain unchanged;
historical reclassification count is zero.

The final implementation is isolated in:

```text
core/evaluation/joint_support_validity.py
experiments/vtdo_experiment/phase1_v26_joint_support_verifier_preflight.py
```

No historical bound module is edited.

## Authority Binding

The joint preflight binds without modification:

- Measurement Support Contract
  `prospective_measurement_support_contract:b49e6a5d66ee7d423ef9944739b30a516d5df84003e157055e99faefdb84398b`;
- public Baseline authority audit
  `finance_v26_public_baseline_authority_audit:ef276425a9786d7edd8301320ffc4218f4dd40f9cfc484eba06f43f56c2779c3`;
- Verifier vNext Contract
  `finance_v26_verifier_vnext_contract:7302fab2d9c0942cddc712c3724d45c138c9f5c806b620e98976ad21eb676790`;
- exact model-owned Final Grammar
  `prospective_qualified_final_response_grammar:2370b603f1243c500e19ef0b45e6bdfa32434a7b4242b0c884ee977dd169d3fc`;
- Answer Semantics, Eligibility, Mechanism, and Responsibility/Noninterference Contracts frozen
  by v26.148.

The Baseline classifier retains zero Oracle, Gold, correct-answer, private-state, or hidden
reference reads. It cannot insert, delete, reorder, choose, or repair a Candidate. Stage 2 remains
deterministic and has no Provider route.

## Joint State Machine

The exact prospective order is:

```text
Public State
Model Action
Stage 2 Commit
Public Observation
Measurement Support
Model Endpoint
Validity Eligibility
Base Validity
Mechanism Qualification
Qualified Validity
```

Measurement Support is evaluated before endpoint validity. Only an endpoint satisfying
`M and O and R and P` may invoke the task Verifier. Here `M`, `O`, `R`, and `P` are Measurement
Support availability, model endpoint observation, Instrument integrity, and privacy compliance.

The following outcomes remain outside every model-valid/model-invalid denominator and invoke the
task Verifier zero times:

```text
measurement_support_exit
model_endpoint_unobserved
instrument_failure
privacy_rejection
```

An eligible endpoint invokes the task Verifier exactly once. It produces separate Base and
Mechanism reports, followed by `V_qualified = V_base and Q_mech`. State Mapping eligibility is
identical to Qualified validity and is false for every null or unqualified result.

The joint Contract is
`prospective_joint_support_validity_contract:40c88c6abb299b83ebae7644f3f5e3d964cdbf0a61bfe4cd3ae520a5593714b2`.

## Positive Fixtures

Nineteen local fixtures pass with zero Provider calls. Their computed partition is:

```text
eligible model-qualified trajectories            10
eligible model-unqualified trajectories           5
typed Measurement Support exits                    1
model endpoints unobserved                         1
Instrument failures                                1
Privacy rejections                                 1
total                                              19
```

The fifteen eligible semantic fixtures cover exact Decimal string/JSON-number equivalence, true
numeric error rejection, all Base/Mechanism truth combinations, model Citation presence and
Evidence mismatch, all four mechanism contracts, and the three Measurement Support Baseline
branches.

Failed Observations and successful progress Observations both produce `not_required` with zero
Baseline-classifier calls. Successful no-progress invokes the public Baseline classifier exactly
once and produces `available`. A successor-unavailable failed Observation produces the typed
support exit with zero Baseline calls.

For the four ineligible fixtures, Base validity, Mechanism success, and Qualified validity are all
null; task-Verifier calls and State Mapping eligibility are zero. No null endpoint is relabeled as
model-invalid.

The positive fixture audit is
`finance_v26_joint_positive_fixture:5ea6911039c4781b3ae410b895ed9dada2f9780f165f1dc0dc615e134ba127f5`.

## Destructive Controls

All 20 destructive mutations fail closed. They cover Host Citation or Mechanism insertion,
support-exit conversion to model-invalid, failed-Observation conversion to Detour, Oracle reads,
Candidate deletion, floating tolerance, hardcoded noninterference, task verification on null
rows, old Verifier identity reuse, historical reclassification, pre-Qualified State Mapping,
missing-endpoint conversion, Privacy answer inference, Instrument task verification, mixed
Qualified parents, a Stage 2 Provider route, Candidate-authority change, Host action repair, and a
Provider call.

The destructive audit is
`finance_v26_joint_support_verifier_destructive:d20aebd656e5eff509fd78d9a3253a22756809ccaac85cf0341c77ad2ab29bd4`.

## Reproducibility

The final formal build writes nine files and reports zero Provider calls, zero Stage 2 Provider
calls, zero GPU jobs, zero Capability or Reachability identities, zero State Mapping rows, and
zero production Contribution.

Focused v26.149 Pytest passes 4/4 in 961.09 seconds, including an independent empty-directory
rebuild and byte comparison of all nine files. The v26.148-v26.149 adjacent non-rebuild regression
passes 6/6 in 3.34 seconds. Focused Ruff and Mypy pass. Package-wide Mypy checks 473 source files
and retains only the three pre-existing v26.70/v26.129 diagnostics; v26.149 contributes zero
diagnostics.

## Authoritative Identities

- report:
  `finance_v26_joint_support_verifier_preflight_report:6f86c51ee9e3229b088bf772d741ea10f0da4befd995bc97f74ba33d3e8e338e`;
- report SHA-256:
  `cde39718dcc471aaeb413ab36f0c675759bd7ae5a20f6b522ccac4c77a41e9f6`;
- source replay:
  `finance_v26_joint_support_verifier_source_replay:64c0a60a070e8d35f47603b2648c23601d1754f86ce8bf3b26f5564af6847163`;
- predecessor integrity:
  `finance_v26_joint_support_verifier_predecessor_integrity:742d30d3e67ada05c9effc2babdc245fd39813c8eb55ad803c18f268d8e8055c`;
- authority binding:
  `finance_v26_joint_authority_binding:e57fe6a3e3f588bff371a21b48f45bfc0ace644c0e6a7e11ea5e7a7b86fb89e3`;
- joint Contract:
  `prospective_joint_support_validity_contract:40c88c6abb299b83ebae7644f3f5e3d964cdbf0a61bfe4cd3ae520a5593714b2`;
- positive fixture:
  `finance_v26_joint_positive_fixture:5ea6911039c4781b3ae410b895ed9dada2f9780f165f1dc0dc615e134ba127f5`;
- stage ordering:
  `finance_v26_joint_stage_ordering:9b04339ba238e39296cd73ab17092ff6e3a3475f0155b08e6dadae2de9f777f8`;
- destructive audit:
  `finance_v26_joint_support_verifier_destructive:d20aebd656e5eff509fd78d9a3253a22756809ccaac85cf0341c77ad2ab29bd4`;
- transition:
  `finance_v26_joint_support_verifier_transition:f8065841b124eba0a4313e5a6b5a7569604153dab122cc27c7f5ac312696ddc3`.

## Permitted Transition

The only permitted transition is:

```text
fresh_capability_population_and_runner_rematerialization_preflight_only
```

The successor may rematerialize a fresh Capability-only Population/TaskPackage/Path/Contract/
Manifest/Job/Runner/execution/report identity chain and perform a complete credential-free Runner
preflight. It must preserve the frozen Capability source Population, tasks, mechanisms, Tiers,
S1 and Candidate authority, v2 Prompt metadata, exact Action Grammar, model/Thinking profile,
resource and recovery bounds, Ordinary Detour allowance, privacy-first capture, zero-Provider
Stage 2, v26.146 Measurement Support Contract, and v26.148 Verifier vNext contracts.

Provider calls, Capability execution, Reachability identity or execution, historical rerun or
reclassification, State Mapping, Host semantic repair, threshold changes, training, release, and
production Contribution remain forbidden.
