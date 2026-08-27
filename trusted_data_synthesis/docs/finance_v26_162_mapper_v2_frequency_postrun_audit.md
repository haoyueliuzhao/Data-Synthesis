# Finance v26.162 Mapper v2 Frequency Independent Postrun Audit

Date: 2026-08-27

## Decision Summary

Finance v26.162 consumed only:

```text
fresh_mapper_v2_reachability_frequency_postrun_audit_only
```

It independently replayed the immutable v26.161 execution with zero Provider calls, parsed all
360 Raw Executions and 3,134 Provider artifact triples, rebuilt every public trajectory and
joint-validity projection, and reproduced the failed Measurement Gate and all-null frequency
decision. It did not call the v26.161 online projector, Gate, Mapper, or summary helper as an
outcome oracle.

```text
complete Raw Executions                         360 / 360
model endpoints                                 359 / 360
validity-evaluable rows                         359 / 360
Measurement Support exits                               1
Raw-native Instrument failures                          0
resource-accounting failures                            0
Privacy failures                                        0
exact-model / Thinking / Usage failures                 0
typed budget no-calls                                    0
unresolved Transport failures                            0
Gate passed                                          false
```

The single failed row is one Measurement Support exit with Raw-native Instrument and resource
integrity. The historical v26.161 formal Instrument and rollout-budget failures remain immutable
but are confirmed as an inherited projection overlap on the same Job, not a second cause and not
a resource overrun.

All exact Mapper-v2 frequency estimands remain null. Production Mapper, Reference Mapper,
formal Assignment, structural State, and empirical Route Signature counts remain zero. This
audit neither repairs the v26.161 denominator nor creates a 359-row substitute.

## Review Reconciliation

| Review requirement | Independent evidence | Decision |
| --- | --- | --- |
| Parse all 360 Raw rows | 360 Raw descriptors and projections reconstructed | Passed |
| Validate all 3,134 Provider triples | 3,134 Envelope/Projection/Transport triples complete | Passed |
| Rebuild public trajectories and joint validity | 360 independent projections, 359 evaluable endpoints | Passed |
| Reproduce the second Detour | Exact Job, two Detours, typed exit, and frozen prefix match | Passed |
| Verify three calls, 40,041 tokens, and no later call | Raw and artifacts agree exactly | Passed |
| Separate Instrument, Support, Resource, Detour, endpoint, and validity | Orthogonal independent fields emitted | Passed |
| Rebuild 139 Base/Qualified and 270 Mechanism outcomes | Exact counts reproduced without relabeling | Passed |
| Rebuild eight zero-Qualified Cells | One Unconditional and seven conditioned Cells | Passed |
| Prove Mapper, Assignment, and State counts are zero | All mapping outputs remain zero | Passed |
| Reproduce 48 failed-Gate null reports | 48/48 reports null, no imputation | Passed |
| Avoid v26.161 outcome helpers as oracles | Independent Raw adapter and projection path used | Passed |

The audit deletes no Job, infers no missing endpoint, changes no historical terminal, computes no
frequency from 359 rows, maps none of the 139 Qualified rows, changes no Detour threshold, and
authorizes no VTDO operation.

## Immutable Replay

The audit binds and byte-matches all 9,797 files in the authoritative v26.161 execution
directory. It binds both v26.161 implementation files and the new audit implementation.
Credential lookup was not attempted.

```text
v26.161 report ID  finance_v26_mapper_v2_frequency_execution_report:
                    152679635b6d16da3ae3723bcbf827c322a859cbcd782025022de8dfc0eafd06
report SHA-256     53f24149e5f981c67ad438060cf1826b2efaf74430633f5973b20b527c24165e
files matched      9,797 / 9,797
```

The missing v25.44 snapshot remains a historical setup limitation. v26.162 does not convert
v26.158 or v26.160 into a full-transitive replay pass.

The Provider audit reparses 360 Raw Executions and 3,134 each of Envelopes, public Projections,
and Transport certificates. Exact-model, Thinking, Usage, Privacy, and unresolved Transport
failures are zero. Stage 2 Provider calls, persisted private reasoning payloads, Raw HTTP bodies,
and Raw request bodies are zero.

## Orthogonal Failure Decomposition

The sole non-endpoint Job remains:

```text
Job                         finance_v26_frequency_job:
                            53e29a176c06a64c701928ec7d2e958de595de83261e9abe95a45d63def57857
mechanism                   state_dependent_stopping
tier                        hard_control
sampling mode               reachability_conditioned
requested Path              search_then_open
historical terminal         measurement_support_exit
historical failure type     ordinary_detour_allowance_exhausted
observed Ordinary Detours   2
Stage 1 calls               3
Transport invocations       3
total tokens                40,041
later Provider calls        0
task-Verifier calls         0
State Mapping rows          0
```

The independent projection is:

```text
raw_native_instrument_integrity       true
measurement_support_available         false
resource_accounting_integrity         true
model_endpoint_observed               false
validity_evaluable                    false
```

The historical online projection remains frozen with `instrument_integrity=false` and
`rollout_budget_passed=false`. v26.162 freezes the causal classification
`one_measurement_support_exit_with_projection_overlap`; it does not rewrite that projection.

The independent Gate fails only on:

```text
measurement_support_exit_zero
model_endpoint_360_of_360
validity_evaluable_360_of_360
```

There is no independent Instrument or resource failure. This corrected attribution does not
repair the Gate because the Support exit alone disqualifies the complete denominator.

## Validity And Cell Audit

The 359 validity-evaluable endpoints reproduce 139 Base-valid, 270 Mechanism-qualified, and 139
Qualified-valid rows. These remain descriptive facts, not a selected mapping denominator.

```text
strong Cells                              48
N_total sum                              360
N_evaluable sum                          359
N_qualified sum                          139
per-Cell N_qualified range              0-10
zero-Qualified Cells                       8
  Unconditional                            1
  conditioned                              7
null frequency reports                    48
```

All 48 reports retain `measurement_gate_failed`. Production and Reference Mapper invocations,
formal Assignments, structural States, empirical Route Signatures, and imputed State vectors are
all zero. The eight zero-Qualified Cells are a separate prospective support issue and are not
converted to zero-probability States.

## Route B Decision

The operator selected Route B from the supplied audit: future work will measure a fully specified
bounded generation policy rather than claim an unrestricted natural-agent process. v26.162
freezes only that prospective decision; it does not reclassify v26.161 or authorize execution.

The successor must make policy-horizon exhaustion an observed bounded-policy endpoint that is
task-incomplete, Base-invalid, Qualified-invalid, and mapping-ineligible. It must be neither a
Measurement Support exit nor a model semantic error. Raw Instrument, Support, Resource, Provider
identity, Thinking/Usage, Privacy, Transport, policy endpoint, validity, and mapping eligibility
must remain orthogonal. Each Task-condition Cell remains a fixed estimand, and future reporting
must include both bounded-policy success support `q_c` and success-conditional State frequency
`pi_c`.

The Route B decision identity is
`finance_v26_route_b_bounded_policy_decision:6a7fb04af06ee74c95de0bce29e6d3bd8506c180ac4a5c928e6e37e6ca775704`.

## Authoritative Identities

- report:
  `finance_v26_mapper_v2_frequency_postrun_audit_report:a536a3a85e2011587d880ac527b4e6a6ca1bec494bbfbe28b7421be8113fdc5e`;
- report SHA-256:
  `0603bb3c0cf84bab38cec287cba59de47f60d0f6bf8cbe787adec1697bbb9b62`;
- source replay:
  `finance_v26_mapper_v2_frequency_postrun_source_replay:f5c59e6de40635c37346fc200c9abc6ddba1a7f1a371e53c4e141a85f1f1793e`;
- Provider artifact audit:
  `finance_v26_mapper_v2_frequency_independent_provider_artifacts:85dd5abc4fc0357ee288115165fcedf95706ed2c4decf1901a31587487bd7ffd`;
- projection Catalog:
  `finance_v26_mapper_v2_frequency_independent_projection_catalog:74b3e138be0ca5695aba194a2705a3250da7965eae0eebbe0a0b28f140919e11`;
- independent Gate:
  `finance_v26_mapper_v2_frequency_independent_gate:dc9900949b626ae40abf7945082571b344a716ab627f3b9934e10d38dc000d91`;
- Cell/null audit:
  `finance_v26_mapper_v2_frequency_independent_cell_null_audit:83bed4ae08e84d69ab86d1592809ec8f8626bda094655d9da323f72e44d4136d`;
- Support boundary:
  `finance_v26_mapper_v2_frequency_support_boundary:a6e2ff5029a8114edbfab126424033b7d4571958e16d118e2fd8d4f0dedcba63`;
- destructive audit:
  `finance_v26_mapper_v2_frequency_postrun_destructive:6bbceb8df5d1649be5549e05317862abc9f3eac25a14e21348620aa25a03f407`.

## Verification And Transition

All destructive controls fail closed with zero Provider calls. The formal output contains nine
files, all reproduced byte for byte by the combined v26.162-v26.163 rebuild test.

At the v26.162 freeze, the only permitted transition was:

```text
fresh_bounded_policy_endpoint_frequency_preflight_only
```

That transition has now been consumed by v26.163. All v26.161 and v26.162 artifacts remain
immutable.
