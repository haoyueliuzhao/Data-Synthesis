# Finance v26.65-v26.68 Authority-Preserving Instrument and Empirical Protocol

Audit date: 2026-08-19

## Summary

Finance v26.65-v26.68 closes the two prospective contract gaps found by v26.64, requalifies the
real Agent instrument under fresh identities, independently audits the completed run, and freezes
the next empirical role protocols without authorizing their execution.

| Stage | Purpose | Result | API / GPU |
| --- | --- | --- | ---: |
| v26.65 | Action-neutral repair and unified terminal verification | Static pass | 0 / 0 |
| v26.66 | 32-job authority-preserving instrument requalification | Instrument pass | 294 / 0 |
| v26.67 | Recovery and post-run source audit | Read-only pass | 0 / 0 |
| v26.68 | Capability/Reachability role and freshness protocol | Frozen, execution blocked | 0 / 0 |

The current support ladder is:

~~~text
static public support                         established
operational Runtime instrument                established
authority-preserving repair/verification      established as an instrument
model-valid trajectory smoke                  observed, 4/32
balanced capability support                   not established
empirical VTDO state reachability              not evaluated
~~~

The authoritative v26.67 audit is
finance_v26_authority_preserving_postrun_audit:7675e7cbce93713a53f94c8da85bbb47fb93961dd67d1f2d8eb08e8205d3e658.

The latest transition is:

~~~text
fresh_capability_population_and_authority_preserving_reachability_runner_only
~~~

Capability Development execution, State Reachability execution, Fresh Confirmation, No-C VTDO,
Student training, Exact Target, GP-C, and production Contribution remain forbidden. Production
Contribution remains zero.

## Scientific Boundary

v26.64 distinguished four support layers:

~~~text
Z_static
  -> Z_operational
  -> Z_authority_preserving
  -> Z_model_runtime_reachable
~~~

v26.63 established the Operation instrument but not the third layer. Failed-action feedback still
exposed action-bearing patches, while the public cross-check tool and Stop Readiness used different
terminal-verification shapes.

v26.65 prospectively repairs those interfaces. v26.66 asks only whether the repaired Runtime is
correctly exposed, action-neutral, replayable, and internally consistent. Independent trajectory
validity remains descriptive for that instrument gate. v26.67 audits the result without rescoring
it. v26.68 freezes later empirical denominators but does not execute them.

## v26.65 Static Contract Hardening

### Action-neutral repair

Each fresh TaskPackage binds one public repair contract. Failed-action feedback may expose only:

~~~text
failed_tool_id
error_category
unresolved_semantic_requirements
unresolved_public_variables
identical_arguments_forbidden
~~~

It may not expose the correct next Tool, Operator, parameters, complete expected arguments,
required next tools, or an argument patch. Both failed tool Observations and later decision
Prompts use this same projection.

### Unified terminal verification

Each task also binds one typed PublicTerminalVerificationTarget to the same Semantic Source,
Public Operation Contract, Verifier DAG, Runtime Projection, and Stop Readiness Contract.

The prospective public claim is exactly:

~~~json
{"operation_ref": "<terminal_operation_ref>"}
~~~

Additional claim fields are forbidden. The cross-check tool, Runtime Progress, Stop Readiness,
Runtime Witness, and independent Verifier all consume this target. Missing, wrong, extra-field,
early-verification, and post-completion mutations fail closed.

### Static result

v26.65 creates fresh identities for all 24 tasks and all dependent contracts.

| Gate | Result |
| --- | ---: |
| Fresh TaskPackages | 24 / 24 |
| Action-neutral Repair Contracts | 24 / 24 |
| Terminal Verification Targets | 24 / 24 |
| Repair Prompt audits | 24 / 24 |
| Terminal verification audits | 24 / 24 |
| Public Runtime Witnesses | 24 / 24 |
| All compiler Witness paths | 48 / 48 |
| Mechanism Necessity | 24 / 24 |
| Legacy Operation mutations | 192 / 192 failed closed |
| New authority/verification mutations | 144 / 144 failed closed |
| Static model-authority paths | 36 |

Compiler Witnesses remain hidden fixtures with zero empirical weight.

The report identity is
finance_v26_authority_preserving_hardening_report:1bd44d38c3b75db70928eeafb72e0e88837dc4f010bcf17decfc3ed60f875221.
Its report SHA-256 is
daba4ed5d9f72304cb1229ae2b42d16aa1a85ea17555f370e5f5c79f1bf5158b.
All twelve JSON outputs were reproduced byte for byte in an independent build.

## v26.66 Instrument Requalification

### Frozen design

v26.66 selects two capability-only tasks per mechanism before observing any new outcome:

~~~text
4 mechanisms x 2 tasks x 4 unconditional replicas = 32 jobs
~~~

The exact requested model is deepseek-v4-flash, fallback is empty, and the aggregate resource
ceiling is USD 2.00. The instrument gate requires 32/32 model outcomes, zero Runtime and instrument
failures, exact-model equality, raw integrity, public/private isolation, complete public contract
and terminal-target visibility, zero action-bearing repair feedback, and zero Stop-readiness false
positive or false negative.

Frozen identities:

~~~text
contract =
finance_v26_operation_closure_regression_contract:
dd73f89ee55e1f0041fc40983db32b84c033f39f2ef1b57b7ac48c8777841d89

Job Manifest =
finance_v26_operation_closure_regression_jobs:
9764ab0ef14f6015bf22b5b9f01ce26b4e5ea5d179130642f0599579a08a3592
~~~

### Execution result

| Metric | Result |
| --- | ---: |
| Model outcomes | 32 / 32 |
| Runtime failures | 0 |
| Instrument failures | 0 |
| Exact requested model | 32 / 32 |
| Fallback | 0 |
| Provider calls | 294 |
| Provider-reported tokens | 3,029,733 |
| Estimated cost telemetry | USD 0.3621166696 |
| Public contract / Progress / target Prompt gates | 32 / 32 |
| Repair Prompts | 81 |
| Action-bearing Repair Prompts | 0 |
| Failed Observations | 92 |
| Action-bearing failed Observations | 0 |
| Stop-ready false positive / false negative | 0 / 0 |
| Complete Program lineage | 5 / 32 |
| Terminal Operation | 5 / 32 |
| Exact post-terminal target acceptance | 5 / 32 |
| Independently valid trajectories | 4 / 32 |

The USD 2.00 resource gate passed. No local GPU job was used. The authoritative recovered report is
finance_v26_operation_closure_regression_report:a48da87c17a703819673c9e4d8c468e9e7685a7ee0ef9efcbebdad17b85389a3.

### Zero-generation finalization recovery

The 32 jobs were initially executed in the same directory as the immutable preflight report. The
runner persisted all 32 checkpoint rows and generated the aggregate, raw audit, and diagnostics,
then correctly refused to replace the preflight report with different bytes. This was a
finalization orchestration defect, not a model, Runtime, or instrument failure.

The interrupted directory remains immutable. Its preflight report is
finance_v26_operation_closure_regression_report:61cba56292ba27a06d0050977afff8b9641f308bdade96d447d27d746cd6f083.

A separate recovery directory received byte-identical copies of the frozen execution Contract,
Job Manifest, and complete checkpoint. The runner resumed at 32/32, had zero pending jobs, did not
construct a model client, and regenerated only aggregate outputs.

~~~text
checkpoint                  8dc549694954c671a9142f21fbf3f455fd7f2ac8c8625a4d57a9351eb540fe8f
empirical rollouts          2a277a972064febaa4af570423a6c0705d0181b9d403da3f2ee24a543139e817
raw integrity audit         e3eba377be84993d2f0cb84abfd686082eacdb08cda1590d96cfa2365641bdc5
rollout diagnostics         4db4aa881ecb4130d69cd26830c34df6b69e0b403ab6a1bc335f53530e1f80f3
~~~

These hashes are identical before and after recovery. No model-invalid row was retried and no
Provider call was repeated.

## v26.67 Independent Post-run Audit

v26.67 replays 53 source files, including all 32 canonical raw artifacts, both checkpoint
locations, the v26.65 task source, the frozen v26.66 inputs, and the recovered aggregate. It
independently rebuilds the raw-integrity audit and all rollout diagnostics.

~~~text
checkpoint rows before / after     32 / 32
unique Job identities              32 / 32
missing / duplicate Jobs           0 / 0
model Jobs executed in recovery     0
API calls in recovery               0
GPU jobs in recovery                0
repair Prompts                     81
action-bearing repair Prompts       0
failed Observations                92
action-bearing failed Observations  0
terminal completions                5
exact terminal target accepts       5
independently valid trajectories    4
~~~

The four valid trajectories cover three tasks:

| Mechanism | Valid rollouts | Valid tasks |
| --- | ---: | ---: |
| Context-conditioned action | 1 | 1 |
| Semantic reconciliation | 0 | 0 |
| Failure recovery | 0 | 0 |
| State-dependent stopping | 3 | 2 |

One additional Stopping trajectory reached Program closure, exact terminal verification, and Stop
Readiness but failed independent Runtime replay. It remains model-invalid.

This is a positive model-validity smoke under the authority-preserving instrument. It is not
balanced capability support: two mechanisms have zero valid trajectories, and the 32 jobs cover
only eight capability-only tasks. It is also not a State Reachability result: no VTDO candidate,
conditioned state, or state mapper entered the run.

The v26.67 report SHA-256 is
47b51917aa95aa5c605c5851773c59e5c23200318facb5eeb35569e3497fc1de.
Formal and independent builds reproduced all four output files byte for byte.

## v26.68 Role-separated Protocol Freeze

### Capability role

The v26.65 source contains 12 capability-measurement tasks. v26.66 exposed eight of them, two per
mechanism, and left only four unopened tasks, one per mechanism.

~~~text
registered capability tasks        12
v26.66-exposed tasks                 8
unopened tasks                        4
minimum balanced Development tasks  12
numeric shortage                      8
~~~

The four-task complement is insufficient for the planned task-first Development estimator.
v26.68 freezes the future denominator at 12 tasks x 8 rollouts = 96 jobs, but requires one entirely
fresh, identity-incompatible, balanced capability Population. It does not append eight
post-outcome tasks to the four-task complement and does not reuse the v26.66 tasks.

### State Reachability role

All 12 registered VTDO candidates and all 36 static states are unopened. The protocol freezes:

~~~text
12 tasks x 12 unconditional attempts       = 144
36 states x 6 conditioned attempts          = 216
total planned State Reachability attempts   = 360
~~~

Natural hits and conditioned acceptance remain separate. Only independently valid,
model-generated trajectories may enter State Mapping. Every state requires at least one natural
hit, a positive conditioned-acceptance LCB95, at least three released realizations, and an
estimated yield of at most 60 attempts for three realizations. Compiler Witnesses remain excluded.

The three public conditions retain behavior guidance only:

~~~text
structured_direct
search_then_structured
search_then_open
~~~

They expose no state, path, Witness, Gold Evidence, hidden Program, or complete action sequence.

The 360 rows are a static job design, not an executable Job Manifest. The historical v26.57 runner
loads the v26.56 report schema, binds legacy record/Runtime versions, and lacks the v3 repair and
terminal-target instrument audits. A fresh authority-preserving runner must be implemented and
replayed before execution.

Authoritative identities:

~~~text
protocol =
finance_v26_empirical_role_protocol:
647274046b92ae6c8320ee376e58c06e18d580fbbd0b625f5e6b3fa4c0d27f19

report =
finance_v26_empirical_role_protocol_report:
13b672c62ebffc68a81815cccdc2561f4c5186e61e0e1d91cf5e1b7d695f5c39
~~~

Formal and independent builds reproduced all four v26.68 outputs byte for byte.

## Immutable Outputs

~~~text
artifacts/vtdo_experiment/finance_v26_65_authority_preserving_operation_hardening_20260819/
artifacts/vtdo_experiment/finance_v26_66_authority_preserving_instrument_requalification_20260819/
artifacts/vtdo_experiment/finance_v26_66_authority_preserving_instrument_requalification_finalization_recovery_20260819/
artifacts/vtdo_experiment/finance_v26_67_authority_preserving_postrun_audit_20260819/
artifacts/vtdo_experiment/finance_v26_68_empirical_role_protocol_20260819/
~~~

### v26.67 hashes

| Artifact | SHA-256 |
| --- | --- |
| Finalization recovery audit | df44535e2262ee16a94616f62c48707a91c25f877ce71d0b07a14a673d5622f0 |
| Rollout authority audits | a43bda267edb0d15450226bfc91052f7268468acc54e7c6b53ebb47476b361e4 |
| Mechanism authority summaries | 11706bf74c85337c785f9a097c87840d991e2a16799896407f7a4d3de451f486 |
| Report | 47b51917aa95aa5c605c5851773c59e5c23200318facb5eeb35569e3497fc1de |

### v26.68 hashes

| Artifact | SHA-256 |
| --- | --- |
| Task exposure audits | a018cf93146f3432df9b29d817b61bc5701c1029591282870c7cb0366c958ca8 |
| Reachability job design | f5dc4824d242498b14cadc0b0b7f4ff140c22fade4113ce00fa665de23b44424 |
| Protocol | b9ec2c800cd20690220a3ff01ab7bcb03480c1cdaf6f4160cb65c48e4499dcc1 |
| Report | 95c24fcd862785f70c51c2ece69dd998ce0e2f346712e1f65964f45848ea0d45 |

## Validation

| Check | Result |
| --- | ---: |
| v26.65 focused tests | 6 passed |
| v26.66 current-source regression tests | 7 passed |
| v26.67 focused tests | 7 passed |
| v26.68 focused tests | 6 passed |
| Combined current/historical boundary regression | 34 passed |
| Ruff | passed |
| Mypy | passed, 364 source files |
| Full Pytest | 939 passed in 491.38 seconds |

One existing Pydantic serializer warning is emitted by a destructive test that intentionally
constructs dict-valued node-binding mutations. It does not affect an experiment artifact or test
result.

Repository-wide Mypy found three annotation-only narrowing issues after the formal artifacts were
created. The current successor adds an explicit optional-binding dictionary type and one
PathStrategy tuple annotation. Runtime branches and accepted artifact details are unchanged, but
the source bytes differ. Historical v26.65-v26.67 manifests and reports therefore retain their
original hashes; their tests validate immutable bytes and reject rebuilding them under the
successor source. Current behavior is tested through a fresh in-test v26.65 build.

## Supported Conclusions

- Action-neutral repair and one shared terminal-verification target are implemented under fresh
  identities.
- Static Witnesses and destructive mutations pass for all 24 tasks.
- The authority-preserving real-model instrument passes every frozen integrity and resource gate.
- Repair feedback contains no registered action-bearing binding in 81 Prompts or 92 failed
  Observations.
- Exact public terminal verification is achievable by the model and is recognized consistently by
  Runtime Progress and Stop Readiness.
- Four independently valid trajectories provide a positive model-validity smoke.
- The next Capability and Reachability denominators are separated and content addressed.
- All 12 VTDO candidates remain unopened, while the capability role requires a fresh Population.

## Unsupported Conclusions

- All four mechanisms have empirical support.
- The current task distribution has stable capability information geometry.
- Any v26.65 VTDO state has positive natural probability.
- Public conditions produce valid state-conditioned acceptance.
- Three states per task have sufficient realization yield.
- Capability Development or State Reachability execution is currently authorized.
- VTDO, Student training, Exact Target, GP-C, or Contribution is effective.

## Next Step

Only two no-API implementation branches are permitted:

1. Materialize a fresh, balanced 12-task capability Population under the v26.65 authority-
   preserving contracts and with zero task, Evidence, Evidence Version, semantic-signature, and
   trajectory overlap against all v26.65-v26.66 empirical inputs.
2. Implement an authority-preserving Reachability runner that consumes the 360-row v26.68 design,
   binds v3 TaskPackage/Runtime/Verifier identities, preserves raw-first telemetry, audits repair
   neutrality and terminal-target projection per rollout, and fails before model-client
   construction on any source or contract mismatch.

Neither branch may execute a model until its own static preflight passes. Capability and
Reachability results must retain separate denominators. Fresh Confirmation, No-C VTDO, Student
training, Exact Target, GP-C, and production Contribution remain forbidden.
