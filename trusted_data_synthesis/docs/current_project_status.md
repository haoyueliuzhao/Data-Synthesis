# Current Project Status

Audit date: 2026-08-21

This status is reconstructed only from the current Git tree, immutable experiment artifacts,
credential-redacted recovery records, and checks rerun on the migrated server. Missing chat
messages are not treated as experimental evidence.

## Repository Identity

- Canonical implementation repository: `/data1/zhuxinrui/projects/Data-Synthesis`
- Immutable experiment artifact root: `/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis`
- Integration branch: `main`; isolated worktrees are temporary implementation staging only
- v22 exact-target measurement source commit: `3aa1b0c39d040f79f11bba6166573ec82d729377`
- v22 exact-target source tree: `b61605018f35ed9550aa02d6c89e164bbe7252c8`
- Credentials remain process-environment inputs and are not tracked or serialized

## Prospective Thinking-Mode Policy

Effective 2026-08-21, every newly materialized Provider model call must explicitly request
`thinking.type=enabled`. A new future-only policy layer rejects missing, disabled, differently
cased, or structurally extended `thinking` values before credential lookup and client
construction. It creates a content-addressed binding between the policy and each prospective
`AgentModelConfig`.

The policy identity is
`prospective_thinking_mode_policy:b9ba7be1e8ee2ab343e31fe57b3c50cbbd604abf26b3da4297f5ad76dfbb158f`.
The initial prospective exact-Flash profile binds model configuration
`agent_model_config:727b3867544c4eac844eb260b9673dee41be7b8787b07ea2e3d6c69113e68bd1`.

This is a prospective generation-kernel constraint, not an empirical result. The v26.83 Contract
and all 241 v26.86 Provider calls remain immutable evidence from `thinking.type=disabled`; no
historical outcome is rerun, rescored, pooled, or reclassified. Future thinking responses retain
only reasoning presence, length, and token telemetry, never private reasoning content. Reasoning
tokens remain completion Usage and count against the unchanged 4,096-token completion bound and
120,000-token rollout ceiling.

The policy implementation and concrete profile pass 10/10 focused tests with zero API calls and
zero GPU jobs. It does not materialize a task Population, empirical Contract, or Job Manifest and
did not by itself change the then-current permitted transition. See
`docs/finance_v26_prospective_thinking_mode_policy.md`.

## v26.94 Thinking Completion And Response-Telemetry Repair Preflight Decision

Finance v26.94 completed the only credential-free transition authorized by v26.93. Before
freezing a new Contract or Manifest it replayed 485 distinct files: the v26.93 report and six
detail outputs, 371 v26.93 transitive execution/source bindings, the v26.90 report and 24 detail
outputs, 56 v26.90 source bindings, 22 v26.90 implementation bindings, and four v26.94 profile
or implementation files. All expected and observed SHA-256 values matched before any credential
lookup or model-client construction.

The preflight rematerialized all 24 model-unexposed v26.90 role TaskPackages under fresh
Completion-repair identities: 12 Capability and 12 Reachability sources, with three per role and
mechanism. They have zero v26.92 overlap in source task, Semantic Source, operational
TaskPackage, repair TaskPackage, and Job identity. All 24 source role packages are now
prospectively retired from Capability and Reachability execution. No historical model outcome or
Compiler fixture outcome entered selection.

The prospective Completion protocol removes the Provider Plan call without replacing it with a
Host-selected plan. Primary requests retain the complete action-neutral v26.90 public state but
require only tool/argument or answer JSON, with no free-text rationale. The model retains tool,
argument, and answer choice. At most one rescue is allowed per Job. It receives only a
state-sensitive compact public projection and one typed failure, never the previous response or
private reasoning, requests immediate JSON, and forbids repeated planning or deliberation.

All 324 requests across all 48 paths pass a frozen minimum 10% rescue-size reduction Gate. The
actual rescue reduction ranges from 730 to 2,959 UTF-8 bytes, or 11.54% to 64.39%. All 276
decision and 48 final-answer Compiler projections preserve exact model action or answer fields.
They remain static fixtures and contribute zero empirical rows.

The future-only client now captures a nullable privacy-redacted response field set before strict
envelope validation and final-content parsing, then applies the v26.93 exact-model, native-tool,
Thinking, and schema Gates. This preserves any response model and native-tool value actually
observed even if another envelope field is malformed, while never inferring a missing model.
Reasoning-only, invalid-JSON, native-tool, missing-model, and malformed-Usage controls retain the
allowed telemetry. Private reasoning content, its hash, and raw HTTP bodies remain unpersisted.
Typed failure artifacts validate before serialization.

Every primary request plus a 64-token static margin is no larger than its v26.90 predecessor.
The removed Plan request and retained repair reserve fund one worst-case rescue under the
unchanged resource Contract. All 48 paths pass: upper bounds range from 52,898 to 111,966,
minimum rollout headroom is 8,034, and the largest Prompt is 8,369 bytes.

The frozen 32-Job Manifest covers all 24 repair TaskPackages and every Mechanism x Path cell with
two or three Jobs. Each mechanism has eight Jobs; `structured_direct`,
`search_then_structured`, and `search_then_open` receive 12, 8, and 12 Jobs. All Job identities
and seeds are distinct. Typed no-call and Completion-unusable remain separate zero-failure Gates:
the one-sided 95% upper bound is 0.08936819898626475 for zero failures and
0.139849460274226 for one at the exact denominator.

All 21 destructive mutations failed closed. Formal and independent builds reproduced all eleven
outputs byte for byte with zero API calls and zero GPU jobs. The authoritative identities are:

- report:
  `finance_v26_thinking_completion_telemetry_repair_preflight_report:efae8ea77b8b67a48cb0cfd90559df7fd77b313855a6088ee778ab1dc8926689`;
- Completion protocol:
  `prospective_thinking_completion_protocol:4fd11877d7a7ed795efc80e07382cea4dd2ba7c3915bfe05439665301084f5f1`;
- repair Contract:
  `finance_v26_thinking_repair_contract:573eb1493ad87832eade20407db775b093a7c4168c63bf19113ee5ceb4dd4f72`;
- Job Manifest:
  `finance_v26_thinking_repair_manifest:56ada3c9430d56c20c6611986cc0fa51f19c3f80fbee3b7b63b07dffddcf5945`.

The only permitted transition is:

```text
thinking_completion_telemetry_repair_execution_runner_and_preflight_only
```

This is a positive static preflight, not empirical Completion usability or permission to execute
the v26.95 Manifest. The next stage must implement and credential-free preflight an exact Runner
before any model call. Capability Development, State Reachability, Fresh Confirmation, No-C
VTDO, Student training, Exact Target, GP-C, and production Contribution remain forbidden.
Production Contribution remains zero. See
`docs/finance_v26_94_thinking_completion_telemetry_repair_preflight.md`.

## v26.92-v26.93 Thinking Calibration Execution And Audit Decision

Finance v26.92 executed exactly the frozen v26.91 32-Job Thinking Budget Calibration Manifest.
Before credential lookup and client construction it replayed 160/160 files: all 31 v26.91
outputs, all 104 predecessor bindings, and 25 execution implementation bindings. The frozen
TaskPackages, paths, stress padding, Contract, Manifest, seeds, model profile, Thinking policy,
Prompt ceiling, completion bound, rollout ceiling, and reserves were unchanged. Each Job was
opened once, and no historical Job was rerun.

All 32 Jobs completed after 318 HTTP-success Provider calls. The run used 1,294,797
provider-reported tokens, including 682,847 reasoning tokens within 708,632 completion tokens,
and recorded estimated cost telemetry of USD 0.24562028400000002152. It used no local GPU.
Every successful call had positive reasoning presence, length, and token telemetry; private
reasoning content and hashes were never persisted.

The empirical Budget Adequacy Gate passed with zero typed no-call outcomes. Its frozen one-sided
95% Clopper-Pearson upper bound is 0.08936819898626475, below 0.10. Provider transport failures,
Thinking-continuity failures, and per-rollout budget failures were all zero.

The separately frozen Completion Usability Gate failed. Thirty of 32 Jobs ended with an unusable
Completion, giving a one-sided 95% upper bound of 0.9887805056361199. The distinct-source
sensitivity result was 29/31 failures with upper bound 0.9884146841385564. There were 78
completion-limit hits across 199 logical requests. All 32 Jobs invoked Contract repair: 119
repair requests produced 89 usable repaired decisions and 30 terminal repair failures. The
Provider-level outcomes were 80 directly usable decisions, 89 usable repaired decisions, 27
reasoning-only length truncations, one partial length truncation, and two unrepaired Decision
Contract failures.

Exact-model execution integrity also failed because 79 HTTP-success parse failures did not retain
response-model telemetry. All 318 calls requested and selected exact `deepseek-v4-flash`, all
fallback flags were false, and all 239 retained response-model values were exact. The missing
values cover 74 `ReasoningBudgetExhaustedError` and five `JSONDecodeError` responses and cannot be
recovered from persisted payloads. Thus zero model mismatches were observed, but exact model
identity cannot be proved for the complete denominator. Provider-native-tool absence was also not
explicitly captured before content parsing.

All 32 persisted terminals are `instrument_failure`, because every Job contains at least one
exact-model telemetry gap. The behavioral diagnostics remain descriptive: requested-path
adherence is 10/32, local mechanism success is 6/32, Program closure is 0/32, and independent
validity is 0/32. The calibration rows do not enter Capability, Reachability, State Mapping, or
release denominators.

The Raw Lineage audit passed all 32 Raw Executions and 318 Provider artifacts. All 350 files are
canonical JSON and reparse under strong schemas, checkpoint and final results match 32/32, and
private reasoning payload count is zero. A credential-free completed-run replay resumed at 32/32,
executed zero Jobs, constructed no client, and reproduced the same report and top-level hashes.
The authoritative v26.92 report is
`finance_v26_thinking_budget_calibration_execution:f3bd9954b1c1f8e465bcca968ef5165d037a7da52b0c0f54ec87e1b9a34aec9b`.

Finance v26.93 then independently replayed 393 execution, Raw Lineage, and implementation files
with a separate credential-free implementation. It reproduced the Completion counts, Usage,
cost, Thinking telemetry, both Clopper-Pearson bounds, the 79-call response-model gap, all schema
reparses, and the zero-private-reasoning result. Formal and independent builds reproduced all
seven outputs byte for byte with zero API calls and zero GPU jobs.

v26.93 freezes a prospective privacy-redacted response envelope before content parsing. It must
retain response model, finish reason, public content hash and length, explicit native-tool
presence, reasoning presence and length, and token telemetry even when parsing fails. Private
reasoning content, reasoning hashes, and raw HTTP bodies remain forbidden. Five local mutations
for missing or changed model, native tool presence, missing reasoning telemetry, and private
reasoning persistence all failed closed.

The authoritative v26.93 report is
`finance_v26_thinking_postrun_audit_report:c6cb718b06f403e8603f4a2520bef8e374aefea2357245a16a8b982071529d44`.
Its prospective repair Contract is
`finance_v26_thinking_telemetry_repair_contract:10f084cc4aac9172cede50ab7f0fbaf339997c9a1cac43f74aed8f107d886343`.
The only permitted transition is:

```text
fresh_thinking_completion_and_response_telemetry_repair_preflight_only
```

The successor requires fresh task, Contract, Manifest, and Job identities and a Completion
protocol redesign before execution. It may not rerun or reclassify v26.92, relax the Completion
threshold, or infer missing response models. A thinking-enabled role protocol is not frozen.
Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training,
Exact Target, GP-C, and production Contribution remain forbidden. Production Contribution
remains zero. See
`docs/finance_v26_92_v26_93_thinking_budget_calibration_execution_and_audit.md`.

## v26.91 Thinking Budget Calibration Preflight Decision

Finance v26.91 completed the credential-free preflight authorized by v26.90. Before freezing a
new calibration identity it replayed all 25 v26.90 output files, 57 source bindings, and 22
implementation bindings, for 104/104 exact-file passes. It then selected 31 fresh calibration
source tasks using immutable structure and a frozen salt. Historical model outcomes and Compiler
fixture outcomes were neither loaded nor used for selection.

The selected Population contains five Context, ten Reconciliation, eight Recovery, and eight
Stopping tasks. It has zero historical or v26.90 role overlap on all nine frozen channels. The
audit covers 156 historical task records and 1,200 historical Job or Recovery-Job identities; the
fresh sets contain 31 source tasks, 209 Evidence/Evidence Version/source-record identities, 31
Semantic Sources, 62 operational plus calibration TaskPackages, and 32 Jobs.

All three public paths were compiled for each task, producing 93 Compiler paths and 580 local
Observations. Verifier v2 Replay, shared completed scoring, Operation Closure, authority,
mechanism necessity, and operational admission all passed. These fixtures remain model-hidden and
contribute zero empirical rows.

The frozen 32-Job Manifest covers every Mechanism x Path cell with at least two Jobs. Context has
only five fully disjoint source tasks after exclusion, so one Context source task binds two
different-path Jobs; all 32 Job identities and seeds remain distinct. Reconciliation Search
receives four Jobs per path, Recovery and Stopping Search receive three, and all other cells
receive two.

Each registered Compiler prefix is stress-qualified against the maximum v26.90 role prefix in its
cell plus a frozen 64-token margin. Calibration-only trailing ASCII-space padding is content
addressed and never enters role measurement; semantic equivalence is explicitly not assumed.
All 32 registered stress paths pass the unchanged 60,000-byte Prompt and 120,000-token rollout
ceilings. Bounds range from 58,760 to 115,676, minimum headroom is 4,324, and the largest Prompt is
8,432 bytes.

The prospective Completion Usability Contract keeps typed no-call, transport failure, and model
completion usability separate. At 32 Jobs, the frozen one-sided 95% Clopper-Pearson upper bounds
are 0.08936819898626475 for zero failures and 0.13984946027422601 for one; therefore both the
typed-no-call and Completion-Unusable Gates require zero failures at the exact denominator.
Reasoning-only truncation, partial truncation, empty content, missing Thinking telemetry, and
unrepaired JSON or Decision Contract failures are tracked separately.

The Thinking Continuity Contract uses Host-instrumented JSON decisions and forbids Provider-native
tool calls. Every HTTP-success turn requires positive reasoning presence, length, and token
telemetry. Ordered attestations bind only public request hashes, public final-content hashes,
telemetry, and parent identities. Private reasoning content is neither persisted nor hashed, and
Verifier or State Mapper dependence on it is forbidden.

The main destructive preflight rejected 13/13 mutations; separate Thinking and Completion fixtures
rejected 6/6 and 2/2 mutations. Formal and independent builds reproduced all 31 output files byte
for byte with zero API calls and zero GPU jobs. Calibration execution has not occurred.

The authoritative identities are:

- report:
  `finance_v26_thinking_budget_calibration_preflight_report:4af68e0667d05639885b985dd7d9091ed8fba03202e6b6c4ebf1d243586a8324`;
- Contract:
  `finance_v26_thinking_budget_calibration_contract:e147742ac18e0766b84162a25f87880340f0f2c57c79883e75db03fef935973d`;
- Job Manifest:
  `finance_v26_thinking_budget_calibration_manifest:3c6877014f6fdd2de41cc3e0c52983b4242942967ec674fecc3630cbccdc630b`;
- Thinking Continuity Contract:
  `thinking_continuity_contract:a4c8025741e13e38025ac6250e18d57ad5e317a2f2db23d66b54d9d8de2144e8`;
- Completion Usability Contract:
  `finance_v26_completion_usability_contract:e7ebf169c798a6af386024652e5b720d1157cd0c825c3c634bed9629cbe5498b`.

The only permitted transition is:

```text
thinking_budget_calibration_execution_only
```

This is a positive preflight, not empirical Budget Adequacy, Thinking usability, Capability, or
Reachability evidence. A passing later calibration may authorize only a thinking-enabled role
protocol freeze. Task-depth and capability-informativeness remain unresolved. Capability
Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training, Exact Target,
GP-C, and production Contribution remain forbidden. Production Contribution remains zero. See
`docs/finance_v26_91_thinking_budget_calibration_preflight.md`.

## v26.90 Budget-Feasible Role Task Rematerialization Decision

Finance v26.90 completed the only static transition authorized by v26.89. It replayed 57 source,
contract, verifier, model-profile, historical task-record, and historical Job-manifest files
before materializing 24 fresh role TaskPackages: 12 Capability and 12 Reachability tasks, with
three tasks per mechanism in each role. Selection used only immutable source structure and a
frozen salt; source-task outcomes, historical model outcomes, v26.81 diagnostic candidates, and
Compiler fixture outcomes were neither loaded nor used.

The Population has zero historical overlap and zero Capability/Reachability overlap on all nine
frozen channels: source task, semantic signature, source hash, Evidence, Evidence Version, source
record, Semantic Source, TaskPackage, and Job identity. The exclusion denominator contains 156
historical task records and 1,200 historical Job or Recovery-Job identities. No Job was selected
or materialized.

v26.90 prospectively reduces each fresh public Program to an independently replayed two-Evidence
leaf Operation, then rebuilds its Public Operation, action-neutral repair, Stop Readiness, exact
terminal-verification target, Environment, and Verifier v2 binding. A new compact public Prompt
representation retains unresolved semantic state, selected facts, operation references, typed
failures, and exact stop state while dropping superseded search candidates and replay telemetry.
It exposes no Oracle, target Evidence, expected arguments, correct next action, or private
mechanism state.

All 12 Capability tasks have one complete budget-qualified `structured_direct` Witness. All 12
Reachability tasks have three independently qualified public paths, for 36/36 paths across
`structured_direct`, `search_then_structured`, and `search_then_open`. Every prefix uses the
unchanged v26.89 arithmetic: UTF-8 Prompt bytes plus the 256-token chat envelope, the 4,096-token
completion bound, and the currently required 4,096-token repair and final-answer reserves.

All 48/48 complete paths pass the 60,000-byte Prompt and 120,000-token rollout ceilings. Static
path upper bounds range from 57,634 to 115,612, minimum headroom is 4,388 tokens, and the largest
Prompt is 8,438 bytes. These are conservative certification bounds, not expected Provider Usage,
model-success estimates, or permission to weaken the resource Contract.

The 48 Compiler paths produced 276 deterministic local Observations. Verifier v2 Replay, shared
completed scoring, trace sidecars, Operation Closure, mechanism necessity, authority, and
operational admission all passed. All 11 thinking, Prompt-projection, and role-package destructive
mutations failed closed. Compiler fixtures contribute zero empirical rows, State Mapping rows, or
releases.

Every future model-bearing identity binds exact `thinking.type=enabled` before client
construction. v26.90 itself constructed no client, made zero API calls, ran zero GPU jobs, and
materialized neither an empirical role Contract nor a Job Manifest. Formal and independent builds
reproduced all 25 output files byte for byte.

The initial v1 build remains immutable and is superseded because package-wide Mypy found seven
local dictionary-inference diagnostics after the focused source check had passed. The v2 successor
uses distinct local variable names and changes no runtime value. All 24 scientific detail files
are byte-identical across v1/v2; only the source-bound report identity changes. Package-wide Mypy
returns to the one retained historical v26.70 diagnostic.

The authoritative report is
`finance_v26_budget_feasible_role_rematerialization_report:9d6e1de192bf267aa45dfbf7b49c1270c0ec995e03b734f208663763a01ef17e`.
Its only permitted transition is:

```text
thinking_budget_calibration_preflight_only
```

This is a positive static path-feasibility result, not empirical Budget Adequacy or a model
Capability/Reachability result. Calibration execution, Capability Development, State
Reachability, Fresh Confirmation, No-C VTDO, Student training, Exact Target, GP-C, and production
Contribution remain forbidden. Production Contribution remains zero. See
`docs/finance_v26_90_budget_feasible_role_task_rematerialization.md`.

## v26.88-v26.89 Budget Adequacy Audit And Static Role Preflight Decision

Finance v26.88 completed the credential-free root-cause audit authorized after the passing v26.87
Instrument audit. It replayed 545 source and experiment files and independently reconstructed all
32 v26.86 budget histories without a model client, API call, GPU job, historical rescore, or task
selection.

All 24 typed no-call terminals occurred at a decision request. Sixteen were caused by required
repair/final reserves not being available and eight by the next request upper bound exceeding the
remaining rollout budget; zero were caused by the 60,000-byte Prompt ceiling. Provider Usage
before denial ranged from 72,689 to 79,489 tokens, denied Prompts from 35,859 to 39,494 bytes, and
certified deficits from 1,755 to 9,333 tokens.

Twenty-one no-call rows had completed zero registered Program nodes, three had positive but
incomplete progress, one had completed the terminal node without verification, and none was a
final-answer-only candidate. The rows contain 57 failed Observations, 43 repeated call signatures,
and 25 repeated failed-call signatures. These are descriptive associations, not a causal
attribution to Prompt growth or repeated failures.

The diagnostic common ceiling of 129,333 would fit only the observed next denied calls. It does
not imply trajectory completion and does not authorize a budget change. v26.88 retains budget
compliance but rejects budget adequacy. Its authoritative report is
finance_v26_budget_adequacy_root_cause_report:bfc54e2c179a475e6f7e6996d844cf4df2e162094668e51e701dd4ce8385ae3f.

Finance v26.89 then froze a prospective Budget Adequacy Contract while retaining the 120,000-token
rollout ceiling, 60,000-byte Prompt ceiling, 4,096-token completion upper bound, 256-token chat
envelope, and both 4,096-token reserves. Every future Capability task requires one Budgeted Public
Witness; every Reachability task requires three budget-qualified public paths under the same
Contract. Resource terminals remain in their role denominator and remain excluded from validity,
State Mapping, and release.

The prospective independent calibration requires at least 32 Jobs and a one-sided 95%
Clopper-Pearson no-call upper bound at or below 0.10. The threshold was selected as an operational
design requirement without using v26.86 outcomes. No calibration was executed.

v26.89 also exercised the previously unobserved completed Runner path with eight fresh-identity
local controls driven by the exposed v26.82 Compiler Witnesses. Raw Execution persistence,
Verifier v2 Replay, independently reconstructed non-Replay Gates, shared completed scoring,
schema-closed sidecars, and report aggregation passed 8/8. The controls made 96 deterministic
local fixture calls, zero API calls, and contribute zero empirical rows.

The separate static full-path audit sums every certified request upper bound plus the current
required reserve. All 8/8 individual Prompts pass the 60,000-byte ceiling, but 0/8 complete paths
fit 120,000 tokens. Conservative path upper bounds range from 366,569 to 575,686. These are static
qualification diagnostics, not expected Usage estimates or permission to raise the ceiling.

No fresh Capability or Reachability task exists, the exposed Instrument fixture catalogs contain
zero Reachability paths, and no role Contract or Manifest was materialized. Formal and independent
v26.89 builds reproduced all fourteen output files byte for byte after replaying
551 source and experiment files. Both used zero API calls and zero GPU jobs.

The authoritative v26.89 identities are:

- Contract:
  finance_v26_budget_adequacy_contract:e3f16d80ca6953dcb77c7e153df5b8881c16fd1bec60240e3285168543db3cfe;
- Runner control audit:
  finance_v26_budget_adequacy_runner_control_audit:3275551e0df1085131e107fc17a240a8699e8b10ee9d0e339a8adcc8a56e034d;
- static Witness audit:
  finance_v26_budgeted_public_witness_audit:a202dbd97e1959d4bdf671d81188233934c090aa5aa8501a057e7adc7b797ccb;
- role preflight:
  finance_v26_budget_adequacy_role_protocol_preflight:c10c62c9d0c9af295503ce4514d7bf17ba29a54b07839d31ecb38f3c6fbd2ca3;
- report:
  finance_v26_budget_adequacy_contract_preflight_report:805432345e0fb8db286daaa80bbbf49b509857eb89861af88086db20ccc8c71f.

The only permitted transition is:

~~~text
fresh_budget_feasible_role_task_rematerialization_only
~~~

Capability Development execution, State Reachability execution, Fresh Confirmation, No-C VTDO,
Student training, Exact Target, GP-C, and production Contribution remain forbidden. Production
Contribution remains zero. See
docs/finance_v26_88_v26_89_budget_adequacy_audit_and_contract_preflight.md.

## v26.84-v26.87 Budget-Closed Instrument Execution, Recovery, And Audit Decision

Finance v26.84 attempted exactly the frozen v26.83 32-Job Manifest. It exposed 20 Jobs and left
12 unopened. The immutable attempt persisted 152 successful exact-Flash Provider calls,
1,380,628 provider-reported tokens, and USD 0.17555657840000001851 estimated cost telemetry before
the Runner failed closed. Four Raw Executions and three checkpoint rows were present.

The Provider budget wrapper had correctly denied 16 requests before invocation and emitted typed
`budget_exhausted_no_call` terminals. A later Host fallback was correctly short-circuited with no
certificate and no Provider call. The v26.84 Raw Execution validator nevertheless required the
certificate count to equal all Host attempts and rejected this valid post-terminal suffix. This
was an Instrument assembly failure after budget closure, not a resource breach or model result.

v26.85 zero-generation replayed all 20 exposed streams and all 152 Provider files, reconstructing
4 model-contract failures, 16 typed no-calls, 128 Observations, and 16 post-terminal short-circuit
Prompts. Its Recovery Contract froze zero model calls for the 20 exposed Jobs and exactly one
execution of each of the 12 unopened Jobs. Formal and independent preflights reproduced all eight
files byte for byte. The authoritative preflight is
`finance_v26_budget_recovery_preflight:f3e1af83b0b380fd14602417fd3770df7e92a532a4196fb4651bc0ab1d6ad964`.

v26.86 replayed the 20 exposed Jobs before client construction and then executed only the 12
unopened Jobs. The continuation made 89 Provider calls, used 823,541 tokens, and recorded USD
0.093130273600000008853 estimated cost telemetry. The complete denominator contains 241 unique
Provider calls, 2,204,169 tokens, and USD 0.268686852000000027363 estimated cost telemetry. No
v26.84 Job was repeated.

All 32 Jobs have one terminal: 24 typed `budget_exhausted_no_call` and 8
`model_invalid_trajectory`. Runtime, Instrument, report-completeness, Replay, exact-model,
fallback, per-rollout resource, and aggregate-cost failures are all zero. The largest rollout used
79,489 tokens against the 120,000 ceiling. All 32 Verifier v2 Replays and all 32 independent
non-Replay audits passed. The authoritative Recovery report is
`finance_v26_budget_recovery_report:4afbad8525b598269630912e79048490dbe4e3235d8789aad0f10b922798c4ea`.

The model result remains negative and descriptive: zero completed trajectories, zero independently
valid trajectories, one full Program lineage, and five local mechanism successes. The online
completed-trajectory scorer and trace sidecar therefore have a zero empirical denominator in this
run; the v26.82 Compiler qualification remains static evidence only.

The credential-free v26.87 audit used an independent implementation and replayed 538 source and
artifact files. It reproduced 32/32 Raw Executions, 152/152 original Provider files byte for byte,
all 89 continuation files, 241/241 unique call and telemetry bindings, all terminal/resource
classifications, 32/32 Replay and non-Replay vectors, 32/32 Instrument admissions, and the entire
v26.86 aggregate with zero mismatched fields. Formal and independent builds reproduced all six
files byte for byte with zero API/GPU. Its report is
`finance_v26_budget_closed_postrun_audit:a7318da72819ce66bdc93ab5117faec5f9f59b32aebd33f5324f2198bd705939`.

The passing Instrument result authorizes only:

```text
fresh_capability_and_reachability_protocol_design_only
```

Capability Development execution, State Reachability execution, Fresh Confirmation, No-C VTDO,
Student training, Exact Target, GP-C, and production Contribution remain forbidden. Production
Contribution remains zero. See
`docs/finance_v26_84_v26_87_budget_closed_instrument_recovery_and_audit.md`.

## v26.82-v26.83 Budget-Closed Rematerialization And Preflight Decision

Finance v26.82-v26.83 completed the only zero-API transition authorized by v26.81. The successor
uses fresh TaskPackage, Contract, Manifest, Job, trajectory, and report identities. No Job from
v26.78-v26.80 was rerun or reclassified, and none of the six v26.81 prospective-valid candidates
entered selection, Capability support, State Mapping, or release counts.

The prospective completed-trajectory scorer now binds the current twelve-field `TrajectoryStep`
schema and uses `observation`, not the nonexistent `observation_id`. Core terminal classification
is frozen after Verifier v2 Replay and independent non-Replay scoring but before the descriptive
trace sidecar. Raw lineage, Provider capture, Runtime Replay, core scoring, diagnostic sidecar,
resource, and report-aggregation failures have separate content-addressed namespaces.

The Provider budget wrapper now certifies every token-bearing call before invoking the underlying
client. It freezes a conservative Prompt bound of UTF-8 bytes plus a 256-token chat envelope, a
4,096-token completion bound, 4,096-token Contract-repair and final-answer reserves, a 60,000-byte
Prompt ceiling, and the existing 120,000-token rollout ceiling. If the request plus required
reserves cannot fit, the Runtime emits a typed `budget_exhausted_no_call` model-invalid terminal
without a Provider call; the Job remains in the denominator.

v26.82 materialized eight fully fresh Instrument TaskPackages, two for each of Context-conditioned
Action, Semantic Reconciliation, Failure Recovery, and State-dependent Stopping. Selection used
four frozen source Populations and no historical model outcome. Freshness overlap is zero on
source task, semantic signature, source hash, Evidence, Evidence Version, source record, Semantic
Source, and TaskPackage identity. After all exclusions, Reconciliation retained 124,284 eligible
Evidence items, four Definition pairs, and exactly two-task capacity.

All 8/8 Compiler Runtime Witnesses, Verifier v2 Replays, shared completed scores, schema-closed
trace sidecars, Operation Closure audits, Mechanism Necessity artifacts, and operational
admissions passed. The build produced 80 Compiler Observations, rejected all 64 legacy Operation
and 40 authority/terminal mutations, and contributed zero empirical rows. The authoritative
v26.82 report is
`finance_v26_budget_closed_verifier_bound_instrument_population_report:9f60f8d7c7522a1fd934bb5a7cdfefb2c91becc73f7e68b2f815dea352ad6484`.

v26.83 froze a balanced 32-Job Instrument-only design. Before any client construction it replayed
67 source files, independently reproduced 8/8 Compiler trajectories and completed scores, passed
public/private isolation, and found zero overlap against 584 historical Job or Recovery-Job
identities from six Manifests.

All 24 destructive Replay mutations failed closed. The budget audit allowed the exact-boundary
positive control, rejected one-token-over, oversized-Prompt, missing-final-reserve, and
missing-repair-reserve cases before Provider invocation, and failed changed or missing successful
Usage after exactly one fixture response. The legacy `observation_id`, Trajectory schema, and
failure-namespace mutations were also rejected without reclassifying the frozen core terminal.
Formal and independent v26.82 builds reproduced all nineteen files byte for byte; formal and
independent v26.83 builds reproduced all ten files byte for byte. Both stages made zero API calls
and zero GPU jobs.

The initial zero-API v1 builds remain immutable and are superseded. Package-wide Mypy found eight
Optional-narrowing diagnostics in the budget Usage implementation after the focused source check
had passed. The v2 successor caches the same telemetry fields in local variables and applies the
identical checks. All eighteen v26.82 scientific detail files are byte-identical across v1/v2;
six v26.83 scientific audits are byte-identical, while source replay, Contract, Manifest, and
report identities bind the type-complete source. No task, Witness, mutation, or scientific count
changed.

The authoritative v26.83 report is
`finance_v26_budget_closed_instrument_preflight:6c279f69cb080458952dfb000633f17c4f901aa8098dfac0cb423656ad9684a7`.
Its Contract is
`finance_v26_budget_closed_instrument_contract:12c9789ccbe3d557411cf5428a15ee0e3d26337b846f47b61b830c86e1415121`,
and its Job Manifest is
`finance_v26_budget_closed_instrument_manifest:38f4a8f5b40c2c576c690c3069c66bc1f43a64f52ef554a16ea28a4656c2434c`.

The current transition is:

```text
fresh_budget_closed_verifier_bound_instrument_requalification_only
```

This is a positive static Instrument precondition, not an online Instrument result or a
Capability/Reachability result. Capability Development, State Reachability, Fresh Confirmation,
No-C VTDO, Student training, Exact Target, GP-C, and production Contribution remain forbidden.
Production Contribution remains zero. See
`docs/finance_v26_82_v26_83_budget_closed_rematerialization_and_preflight.md`.

## v26.78-v26.81 Verifier-Bound Instrument Execution And Failure Decision

Finance v26.78 attempted the exact v26.77 32-job Instrument Manifest. Raw Provider payloads were
persisted before Agent parsing, but the run failed after 17 Jobs had been exposed because the
Runner compared raw Provider telemetry to telemetry after the Host had added
`response_shape.prompt_component_bytes`. The immutable failure contains 146 successful Provider
calls, 1,336,075 provider-reported tokens, USD 0.168894560800000016264 estimated cost telemetry,
zero Raw Execution Artifacts, and zero Rollout rows. The other 15 Jobs were never opened.

A zero-generation audit consumed all 146 stored responses in exact order. All Prompts and all
Provider fields before the single Host augmentation matched. It reconstructed 5 completed
trajectories, 12 model-contract failures, and 118 Observations without an API call. No v26.78 Job
was repeated.

v26.79 froze a Recovery Contract that forbids model calls for the 17 exposed Jobs and permits
exactly one execution of each of the 15 unopened Jobs. It replayed 73 source and failed-run files,
146/146 Provider Artifacts, and 17/17 complete streams before client construction. Formal and
independent builds reproduced all eight files byte for byte. The authoritative preflight is
`finance_v26_verifier_bound_recovery_preflight:a25d500a2ea292f2274b7b1e305d4f5bfadc9b82b8ebaa0ee59474368aff8ccc`.

v26.80 then zero-generation replayed the 17 exposed Jobs and executed only the 15 unopened Jobs.
The continuation made 123 Provider calls, used 1,247,381 tokens, and recorded USD
0.140205408000000015860 estimated cost telemetry. The complete 32-job denominator contains 269
unique Provider calls, 2,583,456 tokens, and USD 0.309099968800000032124 estimated cost telemetry.
All 32 rows used exact DeepSeek V4-Flash with zero fallback and zero Runtime failure; all 32
Verifier v2 Replays passed.

The frozen v26.80 aggregate remains blocked with 25 model-invalid outcomes and 7 Instrument
failures. All seven Instrument failures are completed trajectories that encounter
`AttributeError: 'TrajectoryStep' object has no attribute 'observation_id'` while constructing a
descriptive decision-trace hash after Verifier scoring. The authoritative Recovery report is
`finance_v26_verifier_bound_instrument_recovery:645531ad63c93055f9a29f6a179e6bce16a65441ea7facca4f2d7e8381e52a67`.

The credential-free v26.81 audit replayed 19 implementation files and 477 experiment files. It
independently reproduced 32/32 Replay passes and all non-Replay Gate vectors. A schema-valid,
diagnostic-only reconstruction classifies the seven completed rows as six prospective valid and
one prospective invalid trajectory. These candidates do not reclassify v26.80.

The strict resource gate fails independently. Five Jobs consumed 122,752 to 132,963
provider-reported tokens, exceeding the frozen 120,000 ceiling by 2,752 to 12,963. Aggregate cost
passed, but the Runtime checks cumulative usage only after each response and the frozen profile
has no certified pre-call token upper bound. Therefore the six diagnostic validity candidates
cannot rescue Instrument admission.

The independent lineage-only audit passes 32/32 Raw Executions, 146/146 original exact-byte
Provider files, 269/269 binding and pre-Host telemetry checks, and 269 unique Provider identities.
The v26.80 lineage object's `failed` label is caused by coupling its failure list to the seven
downstream scoring failures, not by a raw lineage breach. Historical files remain unchanged.

The authoritative v26.81 report is
`finance_v26_verifier_bound_postrun_audit:eb7316f9b5e9dcd09013bf3662da64b5f8290f02f1a9e966e3a0268f92d87297`.
Its transition is:

```text
fresh_budget_closed_verifier_bound_task_rematerialization_and_instrument_preflight_only
```

All eight v26.76 tasks are now empirically exposed. A successor requires fresh TaskPackage,
Contract, Manifest, Job, execution, trajectory, and report identities; a schema-valid completed
trace scorer; separated lineage and Instrument failures; and a certified pre-call token bound.
Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training,
Exact Target, GP-C, and production Contribution remain forbidden. Production Contribution is
zero. See
`docs/finance_v26_78_v26_81_verifier_bound_instrument_recovery_and_audit.md`.

## v26.76-v26.77 Verifier-Bound Rematerialization And Preflight Decision

Finance v26.76-v26.77 completed the only zero-API transition authorized by v26.75. The formal
experiment identities and directories were frozen on 2026-08-19; the independent rebuild,
repository validation, documentation, and commit completed after local midnight on 2026-08-20.
The content-addressed `20260819` identities were not renamed post hoc.

v26.76 materialized eight entirely fresh Instrument TaskPackages, two for each of
Context-conditioned Action, Semantic Reconciliation, Failure Recovery, and State-dependent
Stopping. Every package binds the qualified Verifier v2 report, Replay Contract, implementation
source hashes, Semantic Source, Public Operation, action-neutral Repair, typed terminal target,
Runtime, Stop Readiness, Answer Projection, Evidence Support, Citation, Mechanism Contract,
Program DAG, Verifier DAG, and Environment before TaskPackage identity freeze.

The Population is zero-overlap against the v26.42 Development and v26.56, v26.65, and v26.69
inputs on source task, semantic signature, source hash, Evidence, Evidence Version, source record,
Semantic Source, and TaskPackage identity. No historical model outcome or any of the 15 v26.75
diagnostic candidates entered selection. After all exclusions, the Snapshot retained 124,329
eligible Evidence items, eight Definition pairs, and four Reconciliation-task capacity; four
pairs were selected for the two frozen Instrument tasks.

All 8/8 Compiler Runtime Witnesses, Operation Closure audits, authority-preserving Task audits,
Mechanism Necessity artifacts, and operational admissions passed. The build produced 81 Compiler
Witness Observations. All 64 legacy Operation mutations and 40 authority/terminal mutations
failed closed. Compiler Witnesses remain model-hidden and contribute zero empirical rows. The
authoritative v26.76 report is
`finance_v26_verifier_bound_instrument_population_report:4c810296a03f0491d60b20d6e74061a269e70eb35f8054cfa34eb34ea5547cb0`.

v26.77 froze a 32-job Instrument-only design: four mechanisms, two tasks per mechanism, and four
unconditional replicas per task. Before client construction it replayed 52 source and
implementation files, replayed all 81 Compiler Witness Observations through Verifier v2, passed
public/private isolation for 8/8 tasks, and found zero Job identity overlap against the v26.63,
v26.66, v26.71, and v26.72 Manifests.

The preflight rejected 8/8 wrong-environment mutations, 8/8 changed-result mutations, and 8/8
content-addressed action-bearing failed-result injections. The latter first pass an unmodified
action-neutral failed-result baseline and then fail by exact Replay mismatch, rather than by a
stale hash. The existing 40/40 authority/terminal and 64/64 Operation mutation rejections were
retained. Formal and independent v26.76 builds reproduced all sixteen files byte for byte;
formal and independent v26.77 builds reproduced all seven files byte for byte. Both stages made
zero API calls and zero GPU jobs.

The authoritative v26.77 report is
`finance_v26_verifier_bound_instrument_preflight:d8c88785a217da74a6772a51a658ff7a0ee40ee77d3a11ebe5454f795721b263`.
Its frozen Contract is
`finance_v26_verifier_bound_instrument_contract:3ecdc9bff3a2a846ede932c28763abbac1c67c345553eacfec69b2de0985afda`,
and its Job Manifest is
`finance_v26_verifier_bound_instrument_manifest:300bc703e726e04bbf22138a01bf8e09302a54906be8e7510ffa012d7256e724`.

The current transition is:

```text
fresh_verifier_v2_bound_instrument_requalification_only
```

This is a positive static Instrument precondition, not an online Instrument result or a
Capability/Reachability result. Capability Development, State Reachability, Fresh Confirmation,
No-C VTDO, Student training, Exact Target, GP-C, and production Contribution remain forbidden.
Production Contribution remains zero. See
`docs/finance_v26_76_v26_77_verifier_bound_rematerialization_and_preflight.md`.

## v26.74-v26.75 Failure Audit And Verifier Replay Decision

Finance v26.74 completed the read-only root-cause audit requested after v26.71-v26.72. It
replayed all 456 raw Artifacts without a model call, GPU job, historical rescore, mapping change,
or State Support change. The frozen results remain 4/96 Capability-valid, 21/360
Reachability-valid and mapped, 2 releases, 0/36 admitted states, and 0/12 admitted tasks.

The Capability cascade contains 82 model-contract failures and 10 frozen Runtime Replay failures.
Across all mechanisms, local mechanism success is 30/96, independent validity is 4/96,
`P(V=1 | Y=1)=4/30`, and `P(Y=1 | V=1)=4/4`. Recovery has 12 local successes but only one
Program closure and no independently verified row: seven terminate at the failed-tool budget,
three select unavailable `open_document`, and two reach the model-token budget.

The audit found a prior instrument interpretation blocker before task or condition redesign. The
Agent Runtime applies public Operation gates and the v26.65 action-neutral failed-result
projection, while the frozen v1 Verifier Replay reconstructed the legacy failed-action result.
Eighteen completed trajectories therefore have `runtime_replay_passed=false` under mismatched
Replay semantics: ten Capability rows and eight Reachability rows. Fifteen have Replay as their
only frozen failed check.

All eight Capability Stopping local-success rows complete Program, terminal Operation, exact
post-terminal verification, Evidence Support, Answer Projection, Citation, mechanism, and
post-completion control; only frozen Replay fails. Consequently the historical Stopping 0/24
cannot be interpreted as a clean task-support result. Capability and Reachability Stopping also
use disjoint tasks, Semantic Sources, structural profiles, roles, and conditions, so their 0 versus
16 historical-valid contrast remains descriptive.

The route audit retains the frozen adherence counts `52/72`, `6/72`, and `7/72`.
The six historical-valid rows requested as `search_then_structured` and eight requested as
`search_then_open` all map to `structured_direct`, leaving 14/14 search-requested valid rows
Off-target. Four states have any valid natural or conditioned hit. The two released Stopping
states each still have one release, below the frozen minimum of three.

The authoritative v26.74 v2 report is
`finance_v26_capability_reachability_failure_audit:aa3787b164a9df684f05744110a44001dfcf01cea9cabff54a1c4532c6cc0e95`.
Its seven scientific detail files are byte-identical to the initial zero-API v1 build. The v2
identity records the local type-complete source and supersedes v1 without changing a scientific
count. Its transition is `authority_preserving_verifier_replay_repair_only`.

v26.75 implemented a prospective Verifier v2. Replay now mirrors the executed gate order, applies
the same action-neutral result projection, and uses canonical JSON semantic equality. All 45
historical completed trajectories pass v2 Replay and preserve every non-Replay Gate value. The 15
potential validity flips, eight Capability Stopping and seven Reachability Context, are diagnostic
candidates only: no historical validity, path assignment, release, or Freeze is changed.

Verifier v2 rejected 108/108 destructive mutations: 45 environment-identity changes, 45 result
payload changes, and 18 action-bearing failed-result injections. The authoritative v26.75 v2 report
is `finance_v26_authority_verifier_qualification:f61be6be022c2c8506e818e3bb9690e71fa316c6820fec69458c7ab7c8fa7bb1`.
The initial zero-API v1 build remains immutable and is superseded because the final implementation
manifest did not include its imported v26.74 source dependency.

The current transition is:

~~~text
fresh_verifier_bound_task_rematerialization_and_instrument_preflight_only
~~~

Capability Development, State Reachability execution, Fresh Confirmation, No-C VTDO, Student
training, Exact Target, GP-C, and production Contribution remain forbidden. Production
Contribution is zero. See
`docs/finance_v26_74_v26_75_failure_audit_and_verifier_repair.md`.

## v26.69-v26.73 Capability And Reachability Decision

Finance v26.69-v26.73 completed the two empirical roles designed in v26.68 after supplying their
missing prerequisites. v26.69 created a fully fresh 12-task capability-only Population, balanced
at three tasks for each of Context-conditioned Action, Semantic Reconciliation, Failure Recovery,
and State-dependent Stopping. It is disjoint from prior v26 empirical inputs on source task,
semantic signature, source hash, Evidence, Evidence Version, source record, Semantic Source, and
TaskPackage identity. No historical outcome entered selection.

All 12 fresh tasks passed Public Runtime Witness, Operation Closure, authority/terminal-target,
Mechanism Necessity, and Capability admission gates. All 98 legacy Operation mutations and 60
authority/verification mutations failed closed. The zero-API report is
`finance_v26_fresh_capability_population_report:8b7aeb2a9d9044640d41b73eb17d13780cc4bcf5229a1794b751bceee4b12f1e`.

v26.70 implemented one authority-preserving Runner with separate frozen Contracts and Job
Manifests for the 96-job Capability denominator and the unchanged 360-row Reachability design. It
replays all source and implementation bytes before client construction, preserves raw-first
Provider and Prompt telemetry, audits action-neutral repair and the typed terminal target per
rollout, and permits only independently valid model-generated trajectories to enter State
Mapping. Independent preflights reproduced both four-file outputs byte for byte with zero API/GPU.

v26.71 completed all 96 exact DeepSeek V4-Flash Capability jobs with zero Runtime or instrument
failure, zero fallback, and zero Stop-readiness error. All raw-byte, identity, Prompt,
noninterference, repair-neutrality, and terminal-target audits passed. It used 811 Provider calls,
7,755,553 provider-reported tokens, estimated cost telemetry of USD 0.8699810616, and no local GPU.
Four trajectories were independently valid, all in Context-conditioned Action. Reconciliation,
Recovery, and Stopping had zero independently valid trajectories despite 2, 12, and 8 local
mechanism successes respectively. This is a complete balanced Development measurement, not
balanced Capability support.

v26.72 completed the exact v26.68 Reachability denominator: 144 natural unconditional attempts
and 216 state-conditioned attempts. All 360 jobs were model outcomes with zero Runtime or
instrument failure, zero fallback, zero Stop-readiness error, and passing raw/instrument audits.
The run used 3,415 Provider calls, 32,960,134 provider-reported tokens, estimated cost telemetry of
USD 3.4768128360, and no local GPU.

Twenty-one Reachability trajectories were independently valid and all were mapped. There were
five natural on-state hits across three states, two conditioned on-target hits across two states,
and two released realizations. Every state still lacked three independent releases. Therefore
0/36 states and 0/12 tasks passed the frozen reachability and realization-yield contract. The
State Support Freeze is
`finance_v26_empirical_state_support_freeze:4b451c2d3d94937331c46ae5c7089f13f86f6b67c8ea62a26b3c4ab8c897f6ed`
and remains `blocked`.

Conditioned route adherence was 52/72 for `structured_direct`, 6/72 for
`search_then_structured`, and 7/72 for `search_then_open`. Only the two `structured_direct` rows
were on-target valid. This is an observed route-realization diagnostic, not proof that condition
adherence is the sole cause of all failures.

The credential-free v26.73 audit replayed all 456 raw artifacts, both frozen preflights, 31
contract source files, and 13 implementation files per role. It independently reproduced both raw
audits, diagnostics, and reports. Capability and Reachability have zero overlap in TaskPackage,
Semantic Source, Evidence, Evidence Version, source record, source-design Job, execution Job,
Provider call, and trajectory identities. Formal and independent builds reproduced all five audit
files byte for byte. The authoritative report is
`finance_v26_authority_role_postrun_audit:2b3cdbec5671c1cdc38c3f978cca1eb5ef07ed59afcda91298625976edf1331e`.
The initial zero-API v1 audit remains immutable but is superseded because it reused the Runner's
private aggregation functions. v2 independently rebuilds Prompt/Observation diagnostics,
Capability summaries, state intervals and releases, and the global Freeze. v3 adds only explicit
local type annotations required by package-wide Mypy and is authoritative; the empirical result
is unchanged.

The final transition is:

```text
capability_task_or_reachability_condition_redesign_only
```

Capability Confirmation, State-support Confirmation, No-C VTDO, Student training, Exact Target,
GP-C, and production Contribution remain forbidden. Production Contribution remains zero. See
`docs/finance_v26_69_v26_73_capability_and_reachability_report.md`.

## v26.65-v26.68 Authority-Preserving Instrument And Protocol Decision

Finance v26.65 repaired the two prospective contract gaps found by v26.64 under fresh task and
contract identities. Failed-action feedback now exposes only the failed tool, typed error,
unresolved public semantics, unresolved public variables, and the identical-retry rule. One typed
Public Terminal Verification Target now governs the cross-check tool, Runtime Progress, Stop
Readiness, Runtime Witness, and independent Verifier.

The credential-free v26.65 build passed 24/24 Repair Prompt audits, Terminal Verification audits,
Operation Closure audits, Public Runtime Witnesses, and Mechanism Necessity artifacts. All 48
compiler Witness paths passed. All 192 legacy Operation mutations and 144 new repair/verification
mutations failed closed. The 12 VTDO candidates retain 36 static paths. Formal and independent
builds reproduced all twelve JSON files byte for byte with zero API calls and zero GPU jobs. The
report is
finance_v26_authority_preserving_hardening_report:1bd44d38c3b75db70928eeafb72e0e88837dc4f010bcf17decfc3ed60f875221.

v26.66 then executed the frozen 32-job authority-preserving instrument requalification:

~~~text
4 mechanisms x 2 capability-only tasks x 4 unconditional replicas = 32 jobs
~~~

All 32 jobs produced model outcomes with zero Runtime failure, zero instrument failure, exact
DeepSeek V4-Flash identity, zero fallback, and zero Stop-readiness false positive or false
negative. Raw byte, Job identity, actual Prompt, recursive noninterference, public contract,
semantic Progress, private-identity, repair-neutrality, and terminal-target audits passed for
32/32. The run made 294 Provider calls, used 3,029,733 provider-reported tokens, recorded estimated
cost telemetry of USD 0.3621166696, passed the USD 2.00 ceiling, and used no local GPU.

There were 81 failed-action repair contexts and 92 failed tool Observations; none contained a
registered action-bearing Tool, Operator, parameter, expected-argument, or repair-patch binding.
Five trajectories completed the full Program, terminal Operation, and exact typed post-terminal
verification. Four were independently valid: one Context-conditioned Action and three
State-dependent Stopping trajectories, covering three tasks. Reconciliation and Recovery each had
zero valid trajectories. This is a positive model-validity smoke, not balanced mechanism support.

The initial execution persisted all 32 checkpoint rows and complete aggregate detail, then failed
only because the immutable preflight report occupied the formal report path. A zero-generation
recovery copied the exact Contract, Job Manifest, and checkpoint to a separate directory and
resumed at 32/32 with zero pending jobs and no model client. Checkpoint, rollout aggregate, raw
audit, and diagnostics are byte-identical before and after recovery. No model row or Provider call
was repeated. The recovered report is
finance_v26_operation_closure_regression_report:a48da87c17a703819673c9e4d8c468e9e7685a7ee0ef9efcbebdad17b85389a3.

The credential-free v26.67 audit replayed 53 source files and all 32 raw Artifacts. It independently
reproduced the frozen raw-integrity audit and rollout diagnostics, retained the instrument pass,
and bound the zero-generation recovery. Its report is
finance_v26_authority_preserving_postrun_audit:7675e7cbce93713a53f94c8da85bbb47fb93961dd67d1f2d8eb08e8205d3e658.
Formal and independent builds reproduced all four outputs byte for byte with zero API/GPU.

v26.68 then froze separate empirical role protocols without executing either. The v26.65 source
has 12 capability tasks, but v26.66 exposed eight and left only four unopened; this is below the
12-task balanced Development minimum. Capability execution therefore requires an entirely fresh
identity-incompatible 12-task Population. Its prospective denominator remains 96 rollouts.

All 12 VTDO candidates and all 36 static states remain unopened. v26.68 freezes 144 natural
unconditional attempts and 216 conditioned attempts, 360 total. Natural hits and conditioned
acceptance remain separate; only independently valid model-generated trajectories may enter State
Mapping; compiler Witnesses contribute zero. The 360 rows remain a static design because the
historical v26.57 runner is not bound to v3 repair and terminal-target audits. Formal and
independent v26.68 builds are byte-identical. The protocol is
finance_v26_empirical_role_protocol:647274046b92ae6c8320ee376e58c06e18d580fbbd0b625f5e6b3fa4c0d27f19.

The current transition is:

~~~text
fresh_capability_population_and_authority_preserving_reachability_runner_only
~~~

Capability Development execution, State Reachability execution, Fresh Confirmation, No-C VTDO,
Student training, Exact Target, GP-C, and production Contribution remain forbidden. Production
Contribution is zero. See
docs/finance_v26_65_v26_68_authority_preserving_instrument_and_protocol_report.md.

## v26.61-v26.64 Operation Instrument Decision

Finance v26.61-v26.64 executed the frozen 32-job Operation-closure regression, repaired its Host
instrument defect under fresh identities, passed a fresh real-model requalification, and then
completed a credential-free post-run contract audit before freezing any Capability Development or
State Reachability protocol.

The first v26.61 run completed 32 jobs but produced 20 instrument failures and only 12 model
outcomes. Credential-free Witness replay localized all 20 failures to a new-gate/legacy-gate
composition defect: the public Operation gate accepted a valid call with two ready nodes and
`next_required_step=null`, then the legacy single-step gate dereferenced that null step. Historical
v26.61 remains blocked and immutable. Its 143 recorded Provider calls, 1,184,311 tokens, and USD
0.1193173296 estimate omit post-call telemetry from the crashed rows and are therefore lower-bound
telemetry rather than a complete cost denominator.

v26.62 created a fresh 24-task Population after making public Progress semantic-only, removing
Semantic Source identity from the public stop view, giving the new public gate precedence over the
legacy gate, strengthening recursive private-field rejection, and persisting raw-first Prompt and
Provider telemetry. It passed 24/24 Operation contracts, closure audits, primary Runtime Witnesses,
and Mechanism Necessity artifacts; 48/48 compiler Witness paths, 192/192 destructive mutations,
24/24 capability prerequisites, 12/12 VTDO-candidate prerequisites, and 36 static paths also
passed. The run used zero API calls and zero GPU jobs. Its report is
`finance_v26_public_operation_rematerialization_report:0a73cb6e9d90313bdeafd4dd7b42c455c25a1bcfab8300a943d49ed0f157fba3`.

The fresh v26.63 requalification completed 32/32 exact DeepSeek V4-Flash jobs. All 32 were model
outcomes; Runtime and instrument failures, fallback, Stop-ready false positives, and Stop-ready
false negatives were zero. Raw byte, identity, Prompt hash, recursive noninterference, Public
Contract, semantic-only Public Progress, and private-identity audits passed for 32/32 rows. The run
made 403 Provider calls, used 3,930,087 provider-reported tokens, recorded estimated cost telemetry
of USD 0.4368207872, passed its USD 2.00 resource ceiling, and used no local GPU. The authoritative
instrument report is
`finance_v26_operation_closure_regression_report:04cd426a734f4fe6fcbf90e4e07ee750bc19ed6b17809ad43bac5fa4a107a599`.
A credential-free completed-run replay executed zero jobs and left all seven top-level hashes and
the report identity unchanged.

Independent validity remained descriptive. All 32 trajectories were model-invalid; 24/32
completed every required Program node and the terminal Operation, 0/32 satisfied the frozen
post-terminal verification predicate, and 0/32 were independently valid. Twenty-one early final
answers were rejected, with zero premature-verification flag and zero Stop-readiness error.

The v26.64 read-only audit replayed 51 source files and retained the passing v26.63 instrument
result. Public Progress had zero action-bearing ready/next projections. A separate failed-action
path still returned 27 repair patches containing exact action bindings across 22 rollouts; 27 such
patches entered later Prompts across 21 rollouts. This prevents a prospective model-owned repair
claim even though it does not retroactively alter the narrower v26.63 Progress gate.

The audit also found 73 local `verified=true` cross-checks after terminal completion across 23
rollouts. Sixty-six verified answer-shaped payloads and seven verified a matching terminal
`operation_ref` plus extra fields; zero used the exact terminal-reference shape required by frozen
Stop Readiness. This is evidence of a public verification-binding mismatch, not evidence that
Flash performed no useful verification behavior. Historical outcomes were not rescored.

Successful-tool traces had 15 unique sequences, effective count 12.563884, and maximum share
0.21875. All 32 acquisition routes were `structured_direct`, but these were unconditional
capability-only tasks without requested VTDO paths, so multiroute support and path collapse remain
unevaluable.

The authoritative v26.64 report is
`finance_v26_operation_closure_postrun_audit:75ba366bac4afba3efc7784029b5e53aadd855cbab9509ed2489b7cdc71f030e`.
The formal and independent builds reproduced all three output files byte for byte with zero API
calls and zero GPU jobs. Its transition is:

```text
public_repair_and_postterminal_verification_contract_hardening_only
```

Capability Development, State Reachability execution, Fresh Confirmation, No-C VTDO, Student
training, Exact Target, GP-C, and production Contribution remain forbidden. Production
Contribution remains zero. See
`docs/finance_v26_61_v26_64_operation_instrument_repair_and_requalification.md`.

## v26.60 Public Operation Closure

Finance v26.60 completed the fresh identity-incompatible rematerialization authorized by v26.59.
Joint Compilation now binds a model-visible Public Operation Execution Contract, public symbolic
variables, node dependencies, a terminal Operation, Runtime progress, post-terminal verification,
and Host Stop Readiness to the same Semantic Source, Program DAG, Verifier DAG, Answer Projection,
Evidence Support Lattice, and Citation Contract.

The new Population contains 24 real-Finance tasks, six per mechanism and split into 12
capability-only tasks and 12 VTDO candidates. All 24 Public Operation contracts, Operation Closure
audits, primary Runtime Witnesses, target-matched Mechanism Necessity artifacts, and operational
capability prerequisites pass. All 12 VTDO candidates retain three static model-authority paths,
for 36 paths overall.

The Public Reference Policy uses the same Runtime contract as the Agent and does not consult the
Oracle Program for the next action. Forty-eight compiler Witnesses execute 588 public-tool
Observations and remain excluded from empirical state counts. All 192 destructive mutations fail
closed: 72 required-node ablations plus 24 each for terminal-before-prerequisite, first calculation
only, premature verification, missing terminal, and post-completion action.

All six freshness channels are zero-overlap against v26.42 Development and v26.56. Reconciliation
shares one immutable source container but zero selected source-record identities. An independent
build reproduced all eleven detail files and the report byte for byte. The run used zero API calls
and zero GPU jobs.

The authoritative report is
`finance_v26_public_operation_rematerialization_report:1b82fb0bcc1c3be058b48789e1e7c7cb65c46c7e8e968bef66186ae540a0907f`.
It authorizes only a fresh, small Operation-closure instrument regression. Capability Development,
State Reachability, Confirmation, No-C VTDO, Student training, Exact Target, GP-C, and production
Contribution remain forbidden. See
`docs/finance_v26_60_public_operation_and_v26_61_preflight_report.md`.
The first zero-API build remains immutable but is superseded because its implementation manifest
precedes the explicit terminal-operand type guard found by repository-wide Mypy. The authoritative
v2 build has byte-identical eleven detail artifacts and a new source-bound report identity. No
model call, task outcome, or task selection occurred between the builds.


## v26.61 Historical Failure And v26.62 Repair

The v26.61 preflights remain immutable zero-denominator records. The formal v26.61 execution is
also immutable and is the authoritative negative result for that historical implementation:

```text
completed jobs       = 32 / 32
model outcomes       = 12 / 32
instrument failures  = 20 / 32
status               = blocked
next permitted stage = runtime_or_public_operation_instrument_repair_only
```

Its report identity is
`finance_v26_operation_closure_regression_report:1520782d212f40e9d4bc88c8eab3cbb5e2bb03a96f21957c9cd04ac9615e25b3`.
No v26.61 row was retried or reclassified. v26.62 used fresh task, public-contract, Runtime,
Verifier, execution-contract, and Job identities. Its independent static rebuild was byte
identical and authorized only the fresh v26.63 instrument protocol.

## v26.57-v26.59 Empirical Support Decision

Finance v26.57 executed the two empirical stages authorized by v26.56 while preserving separate
denominators: 96 unconditional Capability Development rollouts, 144 unconditional natural-state
rollouts, and 216 state-conditioned attempts. The formal denominator was 456 DeepSeek V4-Flash
jobs. Compiler Witnesses remained verifier fixtures and contributed zero empirical observations.

The first aggregate contained 455 model-invalid outcomes and one Runtime failure. All 456 raw
artifacts passed byte, Job identity, actual Prompt, Host side-channel, recursive noninterference,
condition noninterference, and Provider-call uniqueness checks. The Runtime failure followed one
transient SSL EOF whose same-request retry succeeded; token accounting incorrectly required usage
telemetry from the failed HTTP attempt. The permanent Runtime repair ignores only
`http_success=false` attempts while continuing to reject an HTTP-success response that omits usage.

v26.58 prospectively authorized exactly that one transport retry and explicitly forbade retrying
the 455 model-invalid rows. The replacement was a complete but independently invalid trajectory.
The corrected experiment therefore contains 456/456 model outcomes, zero Runtime failures, zero
instrument failures, and zero independently valid trajectories. It used 4,540 Provider calls,
20,915,421 provider-reported tokens, estimated cost telemetry of USD 1.5227473128, exact requested
model identity throughout, no fallback, and no local GPU job.

No natural or conditioned valid state hit was observed. Consequently, 0/36 states and 0/12 VTDO
candidate tasks passed the frozen reachability and realization-yield contract. Public conditions
did alter pre-calculation acquisition behavior: conditioned adherence was 38/72 for
`structured_direct`, 71/72 for `search_then_structured`, and 36/72 for `search_then_open`. These
invalid-path diagnostics do not create state support.

The credential-free v26.59 audit replayed all corrected raw artifacts. Of 456 rows, 40 first failed
at the model contract, 86 at Evidence selection, and 330 at Operation execution. All 416 complete
trajectories failed full frozen Program lineage: 106 matched zero Program nodes, 193 matched one,
and 117 matched two. The audit also found 207 local verification passes before Program completion,
67 projected-answer matches despite incomplete Program lineage, and 382 local mechanism successes
without complete validity.

Static inspection found that 24/24 tasks lacked a model-visible public
`operation_execution_contract`. The conjunction of that omission, universal Program-lineage
failure, prefix-only execution, and premature stop readiness supports a public Program/stop
contract gap as the dominant engineering blocker. It is not claimed as the sole cause of all model
errors; Reconciliation also retains an Evidence-support weakness.

The authoritative v26.59 decision is:

```text
status                  = public_operation_contract_gap_observed
next_permitted_stage    = fresh_public_operation_contract_rematerialization_only
production_contribution = 0
```

The next Population must receive a fresh identity after Joint Compilation binds a model-visible
ordered Operation contract, terminal-node stop readiness, symbolic public variables, and an
early-stop counterfactual to the same semantic source and Verifier DAG. Capability Confirmation,
state-support Confirmation, No-C VTDO, Student training, Exact Target, GP-C, and production
Contribution remain forbidden. See
`docs/finance_v26_57_v26_59_empirical_support_and_failure_audit.md`.

## v26.56 Fresh Executable-Task Rematerialization

Finance v26.56 completes the no-API task redesign required by v26.55. It does not patch the
immutable v26.42 Development tasks. It uses the previously unopened v26.42 Confirmation source,
retires that source from any future Confirmation role, and creates 24 new task identities only
after required public tools are closed.

The Population contains six tasks for each of Context-conditioned Action, Semantic
Reconciliation, Failure Recovery, and State-dependent Stopping. Three tasks per mechanism are
registered as capability-only and three as VTDO-multistate candidates. All 24 bind one semantic
source to Tool Closure, Typed Answer Projection, Evidence Support Lattice, Citation Contract,
Public Runtime, Mechanism Contract, and Verifier before TaskPackage identity freeze.

The static result passed:

```text
required-tools closure                    24 / 24
single-source package binding             24 / 24
Citation-complete Public Witness          24 / 24
target-matched Mechanism Necessity        24 / 24
capability prerequisite eligibility       24 / 24
static VTDO-candidate eligibility         12 / 12
static model-authority paths                    36
counterfactual Replay records                   48
```

The Finance Runtime now emits a typed normalization operation reference that the downstream
Calculator consumes. Citation uses registered sufficient-set membership rather than exact Gold
equality. The 48 counterfactual rows retain a fully valid baseline, target the exact enclosing
mechanism, remove its registered events, and fail complete validity.

All 36 VTDO paths are compiler generated. They record `model_generated=false` and empirical
reachability `unmeasured`; no compiler Witness contributes to an empirical state count. Thus this
is a positive static-executability and construct-validity result, not a positive Agent
state-support result.

The authoritative report is
`finance_v26_executable_task_rematerialization_report:abc3df8dfbb4c01e17693b48a777f3679c7d8656a88a96c3d1d41a6e5736ea81`.
Its three implementation source hashes and nine immutable detail-file hashes are part of the
report identity. An independent build reproduced all ten JSON outputs byte for byte. The run used
zero API calls and zero GPU jobs.

The only newly permitted stages are capability Development on the 12 registered capability tasks
and an empirical state-Reachability Pilot on the 12 registered VTDO candidates. Fresh
Confirmation, No-C VTDO, Student training, Exact Target, GP-C, and production Contribution remain
forbidden. Production Contribution remains zero. See
`docs/finance_v26_56_executable_task_rematerialization_report.md`.

## v26.55 Executable-Support Contract v2

Finance v26.55 is a credential-free hardening replication of v26.54. A prospective contract audit
found that v1 did not explicitly include Citation completeness in Public Witness validity and
would reject a future capability-measurement task merely because it lacked three VTDO paths. The
v2 Core contract adds sorted selected Citation support to `V=1`, admits the capability-only role
without weakening VTDO, and requires every necessity counterfactual to target its enclosing
mechanism. Historical v1 Witness identities retain their original hash semantics.

The same immutable 24-task source was rebuilt with compiler `1.1.0`. All 24 Witnesses have complete
Citation support; complete Public Witness validity remains 18/24. The same six tasks fail because
a declared Reconciliation axis has no allowed `normalize_metric_unit_period` tool. Projection and
Lattice binding, Mechanism Necessity, and three-path support remain 0/24, so both capability and
VTDO eligibility remain 0/24. This confirms that the v26.54 blocker was not caused by omitted
Citation accounting or task-role conflation.

The authoritative v2 report is
`finance_v26_executable_support_audit:9f3b34ae4fcb75fb7226ba9d5e67a20fe5e596d8fb45bdf689208d5323c9bbae`.
It used zero API calls and zero GPU jobs. Its transition remains
`capability_task_or_scaffold_redesign_only`; Fresh Confirmation, State-support Discovery, No-C
VTDO, Student training, Exact Target, GP-C, and production Contribution remain forbidden.
Production Contribution is zero. v26.54 remains immutable historical evidence at source commit
`c67671c`, while v26.55 is the required contract for all future rematerialized tasks. See
`docs/finance_v26_55_executable_support_contract_hardening.md`.

## v26.54 Executable-Support Precondition Audit

Finance v26.54 implements the credential-free compiler redesign authorized by v26.53. It adds
domain-neutral Core contracts for Typed Answer Projection, Public Executable Witness, Mechanism
Necessity, Alternative Valid Paths, Evidence Support Lattices, and separate capability/VTDO task
admission. The audit replays all 24 immutable v26.42 Development tasks without rescoring v26.43.

A new public-tool compiler produced 226 content-addressed Observations. Eighteen of 24 tasks have
a complete Public Executable Witness. The other six declare a Reconciliation axis while omitting
`normalize_metric_unit_period` from Allowed Tools; the compiler blocks them as
`required_normalization_tool_not_allowed`. Historical Oracle Reference Workflows are not counted
as Witnesses because they use Oracle-only tools, and compiler Witnesses are explicitly not counted
as model-owned VTDO paths.

All 24 Typed Answer Projection contracts and Evidence Support Lattices compile, but zero are bound
to the immutable historical TaskPackages or current Verifier. Mechanism Necessity is 0/24:
Context wrong-action irreparability is 0/8, Reconciliation normalized-reference consumption is
0/8, and the historical eight-task Recovery/Stopping mechanism remains combined. The prospective
taxonomy records 8 Context, 8 Reconciliation, 4 Recovery, and 4 Stopping tasks without relabeling
historical artifacts. No task has three independently valid, model-owned, state-distinct paths.

The role-specific result is therefore:

```text
capability_measurement_eligible = 0/24
vtdo_multistate_eligible        = 0/24
```

The authoritative report is
`finance_v26_executable_support_audit:1c82f661174e1e62783272df1333fdfdaac9797422052b29c28f98f1784b7cc1`.
The run used zero API calls and zero GPU jobs. It preserves
`capability_task_or_scaffold_redesign_only`; Fresh Confirmation, State-support Discovery, No-C
VTDO, Student training, Exact Target, GP-C, and production Contribution remain forbidden.
Production Contribution is zero. See
`docs/finance_v26_54_executable_support_precondition_audit.md`.

## v26.53 Read-only Statistical Audit

Finance v26.53 completed a credential-free, non-authorizing audit of all 576 immutable v26.43
rollouts. It produced 576 rollout diagnostics, 96 mechanism/Scaffold/task Cell summaries, and 24
task-level Scaffold influence records. Exact source and output hashes replay successfully; an
independent rebuild reproduced all three detail artifacts byte for byte. Both builds used zero
API calls and zero GPU jobs. v26.53 supersedes the uncommitted v26.50 through v26.52 development
diagnostics.

The ordered failure cascade accounts for all 553 invalid trajectories: 288 first fail at operation
execution, 198 at answer projection, 32 at Evidence selection, 24 at verification, 8 at model
contract, 2 at argument construction, and 1 at citation. The 198 answer-only failures are not all
formatting defects: 137 combine value and reference errors, 26 are numeric/scalar only, 25
exactly match the compiled human-facing Answer Projection, and 10 contain a wrong Evidence
reference or projected label.

The trajectory audit rejects a global template-collapse explanation. Across the 96 six-rollout
Cells, mean unique normalized trace count is 5.323 and mean effective trace count is 5.188.
However, this variation is carried predominantly by invalid paths. Only 23 trajectories are valid,
covering 3/24 tasks and 9/96 Cells; 21/23 come from Semantic Reconciliation. Positive state-support
inference therefore remains unsupported. All 23 valid trajectories have a Quotient State, with
21 unique states, entropy 4.3496 bits, and effective count 20.3880. No invalid trajectory is mapped;
its state entropy is undefined rather than zero.

Citation equality is not an isolated observed blocker: all 183 citation-equality failures are strict
Gold subsets, none are strict supersets, and none fail only the citation family. Semantic equivalence
of alternative non-Gold Evidence remains unevaluated. Static inspection also finds one registered
Reference Workflow per task and no dedicated Public Executable Witness, Mechanism Necessity, or
Alternative Valid Path artifact.

The final audit identity is
`finance_v26_bridge_statistical_audit:c7851d1487fbab1c5d4814451ea3f46aa52f54e68f01bc841cd66acfcd43c64b`.
It preserves `capability_task_or_scaffold_redesign_only`; no v26.43 outcome was rescored and no
downstream stage was authorized. See
`docs/finance_v26_53_failure_cascade_trace_statistical_audit.md`.

## Historical v26.43 Mainline Decision

The earlier Finance v26.43 Bridge Development experiment followed a new
source-exposure and grounding audit, a fresh v26.42 protocol, and a complete credential-free
24-task Joint/Scaffold prefix. It does not mutate or reauthorize v25.47.

The v26.42 no-API chain completed 24 Joint Compilations, 24 State Spaces, 72 Joint audit Evidence
records, 384 Joint atomic cases, 24 Joint Admissions, 24 Scaffold ladders, 672 Scaffold gate
Evidence records, 3,024 Scaffold atomic cases, 24 Scaffold Admissions, 96 ordered-history collision
cases, 96 cross-level mapping cases, and 3 Bridge static audits containing 144 atomic cases. All
eight Development/Confirmation freshness intersections are zero. Credential-free replay reproduced
the same Stage Ledger with zero API calls and zero GPU jobs.

The authorized v26.43 run then completed exactly 576 DeepSeek V4-Flash Development rollouts:

```text
3 mechanisms x 4 scaffold levels x 8 tasks x 6 rollouts = 576
```

All 5,166 Provider calls returned HTTP 200 with no fallback. Raw byte, identity, actual Prompt,
Scaffold, Host side-channel, and recursive noninterference checks passed for 576/576 artifacts.
There were no Runtime or instrument failures. Only 23/576 trajectories passed independent semantic
and evidential verification; 553 were model-invalid. Context-conditioned action produced 0 valid
trajectories, semantic reconciliation 21, and recovery-and-stopping 2.

Task-first, rollout-second hierarchical inference admitted no scaffold level for any mechanism.
The content-addressed Support Freeze is `blocked`, selects no scaffold, and authorizes only:

```text
capability_task_or_scaffold_redesign_only
```

Fresh Confirmation, State-support Discovery, No-C VTDO, Student training, Exact Target, GP-C, and
Contribution remain forbidden. Production Contribution is zero and unauthorized. This is a valid
negative Bridge Development result, not a Runtime failure and not evidence against VTDO itself.
See `docs/finance_v26_43_bridge_development_report.md`.

The source layer now rejects both historically API-exposed Evidence and Evidence that fails the
independent Finance source-grounding verifier before task resampling. Of 151,114 source Evidence
items, 1,657 were historically exposed, 24,714 failed source entailment, the effective exclusion
union contained 26,290 identities, and 124,824 remained eligible. The final 70-task source
Population and 24/24 Development/Confirmation selections were built from that eligible set.

The immutable v26.43 checkpoint required a zero-generation finalization recovery because the
then-frozen postprocessor had collection-order and JSON mapping-order defects. The 576-record
checkpoint SHA-256 was identical before and after recovery and no model call was repeated. The
permanent implementation uses Bridge Rollout observation v3, Bridge Level Inference v2, Bridge
Support Freeze v5, Bridge Runner v2, and Stage Router v6. It canonicalizes rollout/cell ordering,
validates registered metric key sets independently of mapping insertion order, compares exact cell
identity sets, persists raw-first failure telemetry, and derives the final report transition from
the Support Freeze.

The immutable v26.43 `report.json` retains the older blocking label
`capability_scaffold_repair_only`; it is not rewritten post hoc. The authoritative Support Freeze
uses `capability_task_or_scaffold_redesign_only`, and all future reports inherit that value
directly. Both labels block downstream stages, but only the Support Freeze label is current.

v25.47 replaced the opaque
v25.46 branch cue with one typed, action-neutral public relation state and one shared decision
policy. Its 48-task pre-API population passed every construct-validity check, including unique
public applicability, Context sufficiency, order and label invariance, Context removal and swap
mutations, action-description symmetry, deterministic replay, and lexical leakage rejection.

The 384-rollout DeepSeek V4-Flash execution was fully auditable, with zero recursive Host-field or
marker violations. The aggregate Contextual Shape was admitted, but the prospective mechanism
estimator failed: branch-balanced first-action accuracy was `0.34375`, below both the frozen
`0.625` requirement and the `0.5` constant-action baseline; contextual policy gain was `-0.15625`,
and its paired hierarchical-bootstrap LCB95 was `0.171875`. Only 3/4 matched pairs were
informative.

This is interpreted as a localized Flash contextual tool-selection limitation under sufficient
public Context, not as permission for another same-grammar Prompt repair. A separate immutable
scientific decision tightens the automatic report transition to
`contextual_tool_selection_limitation_recorded` and forbids threshold relaxation, post-hoc task
deletion, additional Flash replicas, Pro calls, Beneficiary screening, Exact Target, and GP-C.
Production Contribution remains zero. See `docs/finance_v25_47_context_sufficiency_report.md`.

## Runtime And Data

The migrated environment is operational with Python 3.12, PyTorch 2.7.1+cu128, CUDA 12.8, and
eight NVIDIA A100-SXM4-80GB GPUs. The completed v26.43 run used no local GPU. No sealed experiment process remained after aggregation.

After all v22 workers had exited, a separate root-owned process
`/opt/venv/render/bin/python3 --coin pearl` appeared at 10:22 and occupied GPUs 0, 1, 3, 4, 6, and
7. It is not a project process and was not terminated. At the same time, `/usr/bin/nvidia-smi` had
an invalid mixed-case ELF interpreter path; read-only inspection remained possible through the
system loader. Future GPU experiments should not start until the server operator reviews this
external workload and binary change. Neither event occurred during the completed v22 target
workers or changes their content-hashed artifacts.

The read-only Finance Archive remains the active data dependency:

| Item | Verified value |
| --- | ---: |
| KG build | `kg_20260711_062123_bc4b4394` |
| Graph schema | `3.0` |
| Nodes | 913,475 |
| Edges | 5,734,348 |
| Fact nodes | 658,535 |
| DerivedFact nodes | 135,990 |

The newest DB-only build from the previous server remains unavailable. The immutable archive used
by the experiment is present and readable.

## v21 Cancellation And v22 Development Expansion

v21 was stopped by operator request after Estimation and Validation each wrote 9 of 32 planned
observations. No aggregate was created, no GP-C evaluation occurred, and the partial rows are not
scientific evidence for target identifiability. All v21 workers are stopped.

v22 froze a pre-outcome Development-only population from the 420-task real Finance pool: 30 tasks
balanced across six families, 100 accepted states, and 312 public Evidence versions with zero
Evidence overlap across target tasks. A separate 64-record Objective role is task-, signature-, and
Evidence-disjoint from the targets and was frozen into eight micro-splits of eight. DeepSeek v4 Pro
completed 300 unconditioned Explorer draws and 500/500 state-conditioned realizations.

The exact target then completed 500/500 strict-FP32 state gradients and 8/8 Objective-gradient
micro-splits on two parallel three-GPU workers. It produced 4,000 crossed observations under one
shared global cold-start AdamW update. Maximum FP32/FP64 target delta was `1.0551e-11` and maximum
simplex-centering error was `1.1699e-11`.

Post-measurement dual-axis inference found that 26/30 primary coordinates were statistically
nonzero, while 30/30 primary coordinates and 100/100 total state coordinates were practically
equivalent under their update-derived MPE. No coordinate was meaningfully beyond MPE. Objective
micro-split variation accounted for `99.9443%` of nested measurement variance; realization
variation accounted for approximately `0.0005%`.

## v23 Pro--Flash Agent Runtime Qualification

v23 changes the generation kernel before attempting another exact-target study. It compares exact
`deepseek-v4-pro` and `deepseek-v4-flash` model identities across Direct/Bare, Host-scripted Tool,
and Autonomous Agent runtimes. Scripted and Autonomous share one frozen six-tool Archive
environment; all Observations are content addressed and independently replayed. The model never
receives Gold Evidence IDs, hidden programs, reference answers, Proof Graphs, or quotient targets.

Protocol-development runs v4-v8 localized output-contract, stop-correction, tool-argument,
no-match recovery, and cumulative-context-budget failures. v6, v7, and v8 each consumed a new
36-task set, and each successor excluded every earlier formal task set. No gate threshold was
relaxed. v9 was declared the final qualification and excluded 150 prior task identities before its
first API call.

v9 completed all 36 requested calibration records with 12 parallel workers. It made 265 API calls,
used 1,151,551 provider-reported tokens, and recorded an estimated API cost of `$0.2782318716`.
All calls used the requested exact model, with zero fallback, zero model-identity mismatch, and zero
HTTP failure. The six model-runtime cells were:

| Model | Runtime | Completed | Independently valid |
| --- | --- | ---: | ---: |
| Pro | Direct/Bare | 6/6 | 6/6 |
| Pro | Scripted Tool | 6/6 | 5/6 |
| Pro | Autonomous Agent | 6/6 | 4/6 |
| Flash | Direct/Bare | 6/6 | 6/6 |
| Flash | Scripted Tool | 6/6 | 4/6 |
| Flash | Autonomous Agent | 5/6 | 3/6 |

The exact-model, independent-validity-smoke, and interactive-tool gates passed. The minimum cell
completion rate was `0.8333 < 1.0`, and the minimum cell JSON-contract rate was
`0.9048 < 0.95`; both preregistered gates failed. The formal decision is
`stop_after_factorial_calibration`, with `next_permitted_stage=protocol_repair_only`. The 30-task,
1,800-rollout Discovery was not launched. No GPU, exact-target, GP-C, Validation, or Authorization
computation occurred.

## v24 Runtime Qualification And Semantic Ladder

v24 freezes semantic, Agentic, and protocol difficulty separately and requires both Runtime
qualification and a true semantic Frontier before capability measurement. Development revisions
removed premature verification, rejected `verified=false`, separated raw JSON response rate from
bounded logical resolution, and clarified exact public selector and JSON operand contracts.

The final v4 qualification excluded every v1-v3 task before sampling. It selected 60 new task IDs
with zero overlap against prior v24 qualification tasks and ran the 18 Easy-Control tasks with 24
workers. All 216 requested rollouts completed. Minimum raw JSON response rate was `0.9556`, bounded
logical resolution was `1.0`, minimum tool success was `0.9531`, final-answer emission was `1.0`,
and no budget or authority failure occurred. The run used 6,723,826 provider-reported tokens and an
estimated `$1.4765509822`; it used no local GPU.

The semantic audit failed independently: Easy, Frontier, and Hard means were `4.5833`, `4.5950`,
and `4.7292`; no family met the minimum Frontier gain. A deliberate Stage B invocation
revalidated the Stage A report, checkpoint, and canonical rollout, then failed before client
construction with `capability calibration requires a true semantic Frontier`. The formal transition is `frontier_task_construction_only`; Exact Target, GP-C, Validation, and Authorization
remain forbidden. A credential-free completed-run replay resumed `216/216`, executed zero jobs,
validated both content hashes, and returned the unchanged report identity without client
construction. See `docs/finance_v24_capability_ladder_experiment.md`.

## v25 Capability-Identifiable Frontier

v25 treats surface-balanced task labels as insufficient. It registers Retrieval, Planning,
Calculation, Reconciliation, Verification, Recovery, and Stopping as seven capability axes and
constructs an executable family for each axis. Each family contains three Easy, five Frontier, and
two Hard-Control tasks drawn from the immutable 420-task Finance source population.

All 70 composite Programs execute and independently replay, all public Corpora are mutually
Evidence-disjoint, and the same source, run ID, and sampling salt reproduce byte-identical JSON and
Markdown. The audit uses only Program and typed workflow structure to derive demand vectors; family
labels add no weight and are used only to verify expected primary-axis alignment. Equal-vector and
relabeling mutations fail closed.

The structural result authorizes construction of a v25-native boundary contract, not immediate
calibration. v25.0 and v25.1 each executed 126 Qualification attempts and failed closed with
`next_permitted_stage=protocol_repair_only`. The failures localized discarded Direct semantic
failure lineage, an incorrect Scripted retry-authority comparison, and ambiguous technical tool
success semantics. Their immutable reports remain diagnostics and are not reclassified.

v25.3 and v25.4 were unexecuted preflights. v25.5 was also retired before execution after a final
audit found that Calibration trusted a passing Qualification report without independently
replaying checkpoint, canonical records, outcomes, and the run manifest. None made an API call or
used a GPU. v25.6 uses incompatible v6 Contract, Runner, Record, Report, and empirical-audit
identities. Qualification accuracy remains descriptive; bounded JSON, typed terminal results,
bounded tool resolution, replay, authority, complete denominators, exact-model telemetry, and
resource budgets control the transition.

A passing report would unlock the balanced 28-task, 1,680-rollout Pro--Flash calibration. Model
differences are estimated with a task-cluster paired nested Bootstrap. The raw empirical
information matrix uses the preregistered uncentered demand formula; axis-specific information uses
confidence-interval lower bounds after removing the intercept and a general-difficulty factor. The
separately frozen Qwen Beneficiary identity is content-replayed; its uncertainty-aware 420-rollout
screen cannot start before the empirical audit passes and may release only explicitly selected
boundary-mass tasks.

The v25.6 contract ID is
`finance_capability_boundary_contract:45896e3eafdc2712657a83c8b0e5482d7849639485205e5f88e396313f248ef2`.
Its unchanged Population and split pass 35/35 destructive Capability Necessity probes. A
credential-free negative preflight confirmed that Calibration rejects an incomplete frozen
Qualification run before model-client construction. v25.6 has made no API call and used no GPU.

Exact Target, GP-C, Validation, Authorization Objective access, VTDO updates, and production
Contribution remain forbidden. See `docs/finance_v25_capability_sensitive_frontier_report.md` and
`docs/finance_v25_capability_boundary_revision.md`.

## v25.17-v25.18 Runtime Resolution And Information Geometry

Runtime Resolution v2 replaced the invalid `technical pass == semantic success` interpretation.
Instrument qualification now depends only on execution integrity, typed terminal resolution,
Runtime pathology, and failure-attribution coverage. Model protocol, decision, recovery, stopping,
verification, and semantic errors remain capability outcomes.

The final v25.18 source pool contains 420 accepted tasks and 1,394 states. Its 70-task Capability
Frontier covers seven capability families and passes all structural monotonicity and primary-axis
alignment audits. A Flash-only public regression excluded 133 prior task signatures and 371 prior
Evidence/Version identities, then completed 28/28 Scripted and Autonomous rollouts without a
deterministic contract defect.

Fresh Runtime Development and Held-out experiments each completed 84/84 rollouts. Held-out had
100% Runtime qualification, 73.81% Valid Success given Runtime eligibility, and 23.81% boundary
cells. Every failure was attributed to L4 Agent decision or L5 semantics; no L0-L2 failure was
observed.

The resulting Flash information audit failed closed. Scripted Final Valid had rank 3, effective
rank 2.000, 14.29% boundary mass, and 73.39% maximum family share. Autonomous Final Valid had rank
7 and effective rank 3.083, but condition number 135.21. The joint condition numbers were
237,575.79 and 167.80. Bootstrap lower bounds yielded zero informative axes in both Runtime cells.

The final transition is `capability_task_support_redesign_only`. Pro sparse anchors remain
unauthorized. See
`docs/finance_v25_17_v25_18_runtime_resolution_and_information_report.md`.

## v25.19-v25.20 Capability-Support Confirmation

v25.19 froze 14 Runtime-family rules from the v25.18 Development result. Host-controlled Scripted
Planning and Stopping were excluded from response geometry. Every model-visible family received
five independent matched groups and each selected binding received five replicas. The original
pool failed closed when it could provide only three fresh Verification groups; a disjoint
420-task real-Finance extension supplied the required capacity without lowering the contract.

The v25.20 population contains 35 groups, 105 static Tier tasks, 60 Runtime bindings, and 50 unique
selected tasks. All six freshness overlap channels are zero and all static public contracts pass.
The online run completed 300/300 Flash rollouts with 3,698 API calls and 21,388,724
provider-reported tokens. No Pro call or GPU computation occurred.

Runtime qualification passed. All 145 failures are attributable capability outcomes: 117 L4
Agent-decision and 28 L5 semantic failures. Family and Group dominance gates passed, boundary mass
rose to 56.00% for Scripted and 68.57% for Autonomous, and Autonomous became full-rank with all
seven marginal-axis Bootstrap lower bounds positive. The remaining failures are Scripted Final
and Joint condition number, plus Autonomous Final and Joint effective rank.

The experiment shows that independent groups and additional replicas improve observability, but
existing Tier selection alone cannot repair Retrieval/Calculation ceilings or the Reconciliation
floor. The next task population must change those axes' irreducible program and Evidence
dependencies. See `docs/finance_v25_19_v25_20_capability_support_confirmation_report.md`.

## v25.21 Public Benchmark Capability Audit

v25.21 deterministically audited all 1,147 frozen FinQA and 1,663 frozen TAT-QA evaluation items.
The resulting artifacts contain aggregate statistics only: no question, answer, context, program,
or Evidence text is exported. Snapshot content hash, source revision, source blob, split, adapter,
metric, and exact denominator are verified before parsing. Public Agent benchmarks are represented
only by aggregate design references for GAIA, BFCL V4, WebArena, SWE-bench, and AgentBench; their
task content was not loaded.

FinQA contains 493 multi-step programs (42.98%) and 84 programs with depth at least three (7.32%).
TAT-QA contains 699 arithmetic answers (42.03%) and 546 table-text examples (32.83%). These
statistics support financial calculation and semantic-alignment design, but both snapshots remain
static evidence-given QA and therefore cannot measure tool planning, recovery, or state-dependent
stopping.

The v25.20 response geometry was compiled into seven new primary mechanisms: disambiguating
information acquisition, typed tool planning, dependent compositional calculation, Bridge semantic
alignment, candidate verification and repair, cross-family recovery, and state-dependent control.
Every mechanism must support Easy, Bridge, Frontier, and Hard tiers. The preregistered Development
minimum is 84 matched groups, with four Bridge and four Frontier groups per mechanism. Existing
Runtime, Prompt, tool-environment, and Workflow Information thresholds remain frozen and
content-hashed.

The audit is `design_ready_population_not_materialized`; it made zero API calls and used zero GPU
jobs. See `docs/finance_v25_21_public_benchmark_capability_audit.md`.

## Revalidated Code State

| Check | Result |
| --- | --- |
| Development target/design focus | 10 passed |
| v24 Agent/runtime focus | 38 passed |
| v25 capability-identifiability focus | 11 passed |
| v25.19-v25.20 support-confirmation focus | 26 passed |
| v25.21 public-benchmark audit focus | 5 passed |
| Ruff check | passed |
| Ruff format | v26.94 source/tests passed; 116 historical baseline files remain unformatted |
| Mypy | 393 files checked; one source-bound v26.70 local-list annotation diagnostic retained |
| Pytest | 1088 passed, 4 expected v26.78/v26.84 success-state tests skipped in 848.39 seconds; one existing destructive-test warning |
| Prospective thinking-mode policy focus | 10 passed in 0.38 seconds; zero API/GPU |
| v26.94 focused regression | 16 passed in 5.01 seconds; zero API/GPU |
| v26.88-v26.94 adjacent thinking/budget regression | 66 passed in 72.86 seconds |
| v26.94 dual build | all eleven output files are byte-identical; zero API/GPU |
| v26.94 source replay | 485/485 distinct v26.90/v26.93/current files passed |
| v26.94 repair Population | 24 fresh repair TaskPackages; all 24 source role packages retired; zero v26.92 source overlap |
| v26.94 static Completion paths | 48/48 paths and 324/324 projections passed; bounds 52,898 to 111,966; minimum headroom 8,034 |
| v26.94 rescue projection | all 324 rescue Prompts at least 10% shorter; observed reduction 11.54% to 64.39% |
| v26.94 repair Manifest | 32 fresh Jobs; all 12 Mechanism x Path cells have two or three Jobs; execution forbidden |
| v26.94 telemetry/privacy controls | pre-parse exact-model/native-tool retention passed; zero private-reasoning persistence |
| v26.94 destructive controls | 21/21 mutations rejected |
| v26.92-v26.93 focused regression | 9 passed in 10.31 seconds |
| v26.88-v26.93 adjacent thinking/budget regression | 41 passed in 68.71 seconds |
| v26.92 online source replay | 160/160 files before credential lookup and client construction |
| v26.92 calibration execution | 32/32 Jobs; 318 HTTP-success calls; 1,294,797 tokens; zero GPU |
| v26.92 Budget/Thinking Gates | zero typed no-calls and zero Thinking-continuity failures; both passed |
| v26.92 Completion Gate | 30/32 unusable; 29/31 unique-source sensitivity; failed |
| v26.92 response-model telemetry | 239 known exact, 79 missing, zero known mismatch; exact-model Gate failed |
| v26.92 Raw Lineage and replay | 32 Raw plus 318 Provider files passed; completed replay executed zero Jobs |
| v26.93 independent source replay | 393/393 execution, Raw Lineage, and implementation files |
| v26.93 independent audit | Completion failure, persistence integrity, and response-model gap reproduced; zero API/GPU |
| v26.93 dual build | all seven output files are byte-identical; zero API/GPU |
| v26.93 repair fixtures | 5/5 telemetry/privacy mutations rejected |
| v26.91 focused regression | 10 passed in 24.76 seconds; zero API/GPU |
| v26.91 adjacent v26.89-v26.91 thinking/budget regression | 42 passed in 59.17 seconds |
| v26.91 dual build | all 31 output files are byte-identical; zero API/GPU |
| v26.91 predecessor replay | 104/104 files: 25 outputs, 57 source bindings, and 22 implementation bindings |
| v26.91 Calibration Population | 31 tasks and 32 Jobs; zero overlap on nine historical and v26.90 role channels |
| v26.91 static Compiler controls | 93/93 paths, 580 Observations, 31/31 admissions; zero empirical rows |
| v26.91 budget-shape coverage | 12/12 cells and 32/32 paths; bounds 58,760 to 115,676; minimum headroom 4,324 |
| v26.91 Thinking/Completion controls | 6/6 continuity, 2/2 completion, and 13/13 main destructive mutations rejected |
| v26.90 focused regression | 9 passed in 16.69 seconds; zero API/GPU |
| v26.90 adjacent thinking/budget regression | 32 passed in 55.21 seconds |
| v26.90 dual build | all 25 output files are byte-identical; zero API/GPU |
| v26.90 v1-v2 scientific details | all 24 detail files are byte-identical; v2 source-bound report is authoritative |
| v26.90 source replay | 57/57 source, contract, verifier, profile, task-record, and Job-manifest files replayed |
| v26.90 role Population | 12 Capability plus 12 Reachability tasks; zero overlap on nine historical and cross-role channels |
| v26.90 static Budgeted Public Witnesses | 12/12 Capability and 36/36 Reachability paths qualified; bounds 57,634 to 115,612; minimum headroom 4,388 |
| v26.90 Compiler and destructive controls | 48/48 Replay/shared-score passes, 24/24 admissions, and 11/11 destructive rejections; zero empirical rows |
| v26.88-v26.89 Budget Adequacy focused regression | 13 passed in 21.00 seconds |
| v26.89 dual build | all fourteen output files are byte-identical; zero API/GPU |
| v26.89 source replay | 551/551 source and experiment files replayed |
| v26.89 complete Runner controls | 8/8 Raw, Replay, non-Replay, shared-score, sidecar, and aggregation passes; zero empirical rows |
| v26.89 static Budgeted Public Witness audit | 8/8 Prompt ceilings; 0/8 full-path 120k qualifications; path bounds 366,569 to 575,686 |
| v26.89 role preflight | 0 fresh role tasks; zero Contracts/Manifests; Capability and Reachability execution forbidden |
| v26.88 dual build | all five output files are byte-identical; zero API/GPU |
| v26.88 source replay | 545/545 source and experiment files replayed |
| v26.88 denial audit | 24 decision no-calls: 16 reserve-bound and 8 request-bound; 21 zero-progress rows |
| v26.82-v26.87 budget-closed full focused regression | 26 passed, 2 expected v26.84 success-state tests skipped in 104.54 seconds |
| v26.87 independent post-run audit focus | 4 passed in 23.03 seconds |
| v26.87 dual build | all six output files are byte-identical; zero API/GPU |
| v26.87 independent source replay | 538/538 source and experiment files replayed |
| v26.87 independent raw lineage | 32/32 Raw Executions; 152/152 original exact-byte and 89/89 continuation Provider files; 241 unique identities |
| v26.87 independent terminal and scoring audit | 24 no-call plus 8 model-invalid terminals; 32/32 resource, Replay, non-Replay, and Instrument passes |
| v26.86 completed-run replay | 32/32 resumed; zero Jobs, zero model-client construction, byte-identical report |
| v26.86 recovered denominator | 20 zero-generation plus 12 first-execution Jobs; 32/32 terminals; zero Runtime/Instrument failure |
| v26.86 Provider accounting | 241 unique calls; 2,204,169 tokens; USD 0.268686852000000027363 estimate; maximum rollout 79,489 tokens |
| v26.85 Recovery preflight dual build | all eight output files are byte-identical; zero API/GPU |
| v26.85 failed-run replay | 20/20 streams, 152/152 calls, 128 Observations, and 16 short-circuit Prompts reproduced with zero generation |
| v26.84 failed execution | 20 exposed and 12 unopened Jobs; 152 Provider calls; 4 Raw Executions and 3 checkpoint rows |
| v26.82-v26.83 budget-closed focused regression | 11 passed in 31.81 seconds |
| v26.82 v2 fresh Population dual build | all nineteen output files are byte-identical; zero API/GPU |
| v26.82 v1-v2 scientific details | all eighteen detail files are byte-identical; v2 source-bound report is authoritative |
| v26.82 freshness and capacity | zero overlap on eight channels; 8 fresh TaskPackages; exact 2-task Reconciliation capacity |
| v26.82 Compiler shared scoring | 8/8 Replay and completed-score passes; 80 Observations; zero empirical rows |
| v26.83 v2 Instrument preflight dual build | all ten output files are byte-identical; zero API/GPU |
| v26.83 v1-v2 scientific audits | six audit files are byte-identical; v2 source/Contract/Manifest/report are authoritative |
| v26.83 source and Job isolation | 67/67 files replayed; zero overlap against 584 historical Job identities |
| v26.83 destructive mutations | 24/24 Replay, 7/7 budget, and 3/3 scoring/namespace cases passed |
| v26.76-v26.81 verifier-bound focused regression | 31 passed, 2 expected v26.78 success-state tests skipped in 72.58 seconds |
| v26.79-v26.81 recovery/audit focus | 13 passed in 21.28 seconds |
| v26.78 failed execution | 17 exposed and 15 unopened Jobs; 146 Provider calls; zero Raw Execution or Rollout rows |
| v26.79 Recovery preflight dual build | all eight output files are byte-identical; zero API/GPU |
| v26.79 failed-run Replay | 17/17 streams, 146/146 calls, and 118 Observations reproduced with zero generation |
| v26.80 recovered denominator | 17 zero-generation plus 15 first-execution Jobs; 32/32 Replay passes; zero repeated exposed Jobs |
| v26.80 Provider accounting | 269 unique calls; 2,583,456 tokens; USD 0.309099968800000032124 estimate |
| v26.81 post-run audit dual build | all five output files are byte-identical; zero API/GPU |
| v26.81 source/raw replay | 19 implementation and 477 experiment files; 32/32 Raw Executions replayed |
| v26.81 failure localization | 7 completed-trace scoring defects; 5 strict token-ceiling failures; lineage-only audit passed |
| v26.76-v26.77 focused regression | 13 passed in 51.77 seconds |
| v26.76 Verifier-bound Population dual build | all sixteen output files are byte-identical; zero API/GPU |
| v26.76 freshness | zero overlap on all eight channels; 8 fresh TaskPackages |
| v26.76 static task audit | 8/8 Witnesses; 64/64 Operation and 40/40 authority mutations rejected |
| v26.77 Instrument preflight dual build | all seven output files are byte-identical; zero API/GPU |
| v26.77 source and Compiler replay | 52/52 files and 81/81 Observations replayed |
| v26.77 destructive Replay mutations | 24/24 rejected with content-addressed mutated Observations |
| v26.75 authority-preserving Verifier focus | 6 passed |
| v26.75 v2 dual build | all four output files are byte-identical; zero API/GPU |
| v26.75 completed-trajectory qualification | 45/45 v2 Replay passes; all non-Replay Gates retained |
| v26.75 destructive Replay mutations | 108/108 rejected |
| v26.74 Capability/Reachability failure audit focus | 7 passed |
| v26.74 v2 dual build | all eight output files are byte-identical; zero API/GPU |
| v26.74 raw replay | 456/456 immutable raw Artifacts passed exact-byte replay |
| v26.74 v1-v2 scientific details | all seven detail files are byte-identical |
| v26.69 fresh Capability and v26.70 Runner focus | 6 passed |
| v26.69 dual build | all fourteen detail files and report are byte-identical; zero API/GPU |
| v26.70 dual preflights | four Capability and four Reachability files are byte-identical; zero API/GPU |
| v26.71 Capability Development | 96/96 model outcomes; zero Runtime/instrument failure |
| v26.72 State Reachability | 360/360 model outcomes; 0/36 states and 0/12 tasks admitted |
| v26.71-v26.72 completed-run replay | 96/96 and 360/360 resumed; zero jobs and unchanged report IDs |
| v26.73 independent post-run focus | 6 passed |
| v26.73 source/raw replay | 456/456 raw rows, both reports, and all source manifests reproduced |
| v26.73 dual build | all five output files are byte-identical; zero API/GPU |
| v26.69-v26.73 focused regression | 46 passed |
| v26.68 empirical role protocol focus | 6 passed |
| v26.68 dual build | all four output files are byte-identical; zero API/GPU |
| v26.67 authority-preserving post-run focus | 7 passed |
| v26.67 dual build | all four output files are byte-identical; zero API/GPU |
| v26.67 source replay | 53 source files and 32 raw Artifacts passed exact hash replay |
| v26.66 instrument requalification | 32/32 model outcomes; all instrument/resource gates passed |
| v26.66 finalization recovery | 32/32 resumed; zero model jobs; four aggregate hashes unchanged |
| v26.65 authority-preserving hardening focus | 6 passed |
| v26.65 dual build | all twelve JSON files are byte-identical; zero API/GPU |
| v26.65-v26.66 type-hardening successor | current-source focused regression 34 passed |
| v26.64 post-run audit focus | 8 passed |
| v26.64 dual build | all three output files are byte-identical; zero API/GPU |
| v26.64 source replay | 51 source files and 32 raw Artifacts passed exact hash replay |
| v26.63 instrument requalification | 32/32 model outcomes; all instrument and resource gates passed |
| v26.63 completed-run replay | 32/32 resumed, zero jobs, all seven top-level hashes unchanged |
| v26.62 static hardening dual build | all twelve JSON files are byte-identical; zero API/GPU |
| v26.61 historical execution | 32/32 completed; 20 instrument failures retained as blocked |
| v26.60 Public Operation rematerialization focus | 8 passed |
| v26.60 v2 dual build | all eleven detail artifacts and report are byte-identical |
| v26.60 v1-v2 scientific details | all eleven detail artifacts are byte-identical |
| v26.60 implementation manifest | historical hashes retained; current successor bytes intentionally differ |
| v26.63 Operation-closure requalification focus | 7 passed |
| v26.61 v2 dual preflight | execution Contract, Job Manifest, and report are byte-identical; zero API/GPU |
| Public Operation / Iterative Agent Runtime focus | 6 / 41 passed |
| v26.57-v26.59 focused regression | 55 passed |
| v26.58 completed-run replay | credential-free resume reused the existing result; four SHA-256 values unchanged |
| v26.58 implementation manifest | all four frozen source-file SHA-256 values match the current tree |
| v26.59 deterministic rebuild | zero API/GPU; diagnostics and report are byte-identical |
| v26.56 executable-task rematerialization focus | 10 passed |
| v26.56 dual build | all nine detail artifacts and report are byte-identical |
| v26.56 implementation manifest | three source files content-hashed in report identity |
| v26.55 executable-support v2 focus | 10 passed |
| v26.55 dual build | all seven detail artifacts and report are byte-identical |
| v26.54 executable-support focus | 8 passed |
| v26.54 dual build | all seven detail artifacts and report are byte-identical |
| v26.53 statistical-audit focus | 9 passed |
| v26.53 credential-free replay | authoritative and determinism builds each replayed |
| v26.53 dual build | all three detail artifacts are byte-identical |
| Core generalization boundary | 140 files, zero imports/branches/field accesses/violations |
| Tracked credential pattern scan | zero `sk-` plus 32-alphanumeric hits |
| v25.19 policy deterministic replay | byte-identical SHA-256 `01ff658e46a6...` |
| v25.20 population deterministic replay | byte-identical SHA-256 `8ee0b10046af...` |
| v25.20 contract deterministic replay | byte-identical SHA-256 `80cf20a2e526...` |
| v25.20 completed-run replay | 300/300 resumed, zero API jobs, identical report ID |
| v25.21 audit JSON replay | byte-identical SHA-256 `15b1c8fd99d4...` |
| v25.21 audit Markdown replay | byte-identical SHA-256 `fb0c4018068b...` |
| v25.21 mechanism manifest replay | byte-identical SHA-256 `f9765dc5b622...` |
| v25.21 benchmark-content isolation | 2,810/2,810 questions and all content keys absent |
| v25.29 completed-run replay | 100/100 resumed, zero API jobs, identical report ID |
| v22.1 deterministic replay | identical SHA-256 `a19bcc303026...` |
| Legal and Science contracts | retained by full suite |

The repository-wide formatter would rewrite historical files under the currently installed Ruff
version. Those unrelated files were deliberately not reformatted. The v25.20 contract binds the
exact bytes of `phase1_multitier_capability_population.py`; its pre-run formatting is retained so
the executed contract remains reproducible. All changed Python files pass lint, while the new
non-manifest-bound source and tests also pass the formatter.

Repository-wide Mypy reports one `var-annotated` diagnostic for the local `provider_ids` list in
the v26.70 Runner. Adding the obvious `list[str]` annotation would not change runtime values, but
would change source bytes already bound by the executed v26.70-v26.72 Contracts and the v26.73
source replay. The exact executed source is therefore retained. No global Mypy rule was relaxed;
the diagnostic is recorded rather than hidden.

The v17 tests reject altered plans, implementation manifests, profiles, splits, source jobs,
result rows, selection lineage, uncertainty envelopes, and stale contracts. Validation cannot run
before selection or with a nonselected profile. A failed aggregate cannot retain a stale numeric
contract.

## Historical Boundaries

### v14 production candidate

The immutable v14 candidate remains historical evidence:

- 30 real Finance tasks;
- 100 quotient trajectory states;
- 300 fresh state-conditioned realizations;
- 1,065/1,065 gradient artifact content hashes verified;
- stable realization sampling and positive internal proxy association;
- seven raw numeric-tail violations and three strict task-order reversals.

It was not reused to tune v16 or v17. Its status remains `partial` with
`production_authorized=false`.

### v16 recalibration

v16 used disjoint development, validation, and sealed-candidate populations. The BF16 TF32 profile
passed development but failed independent validation on relative error, cosine, and GP-score delta.
No v16 numeric contract was issued. Margin-aware ordering remained stable, so v16 localized the
bottleneck to raw gradient-level numerical fidelity rather than sampling or task ordering.

The unused v16 profile was not substituted post hoc, and the v16 validation set was not reused for
v17 tuning.

## v17 Numeric Root-Cause Experiment

### Population and real-Agent inputs

v17 created three fresh, balanced six-task partitions. Every partition contains one task from each
of six task families and binds 63 Evidence versions. Task, Evidence-version, and semantic overlap
across development, validation, and sealed candidate are all zero.

Development and validation each produced:

- 24/24 valid initial trajectories;
- 20 trajectory states;
- 60/60 released state-conditioned realizations.

The full real-Agent input funnel used 554 DeepSeek-V4-Pro calls and 4,092,455 tokens. Every API call
and JSON contract succeeded, fallback use was zero, and the provider-reported estimate summed to
`0.484361248`. That value is telemetry rather than an invoice. The numeric experiment itself made
no additional API calls.

### Development diagnosis

The preregistered matrix evaluated 20 realization-level records under eight profiles. Seven
profiles failed the unchanged raw numeric contract. Only `fp32_activation_strict` passed:

| Metric | BF16 control | FP32 activation |
| --- | ---: | ---: |
| Maximum relative error | 0.03436155 | 0.00641550 |
| Minimum cosine | 0.99952628 | 0.99997942 |
| Maximum GP delta | 0.00212896 | 0.00052523 |
| Maximum update TV | 0.00012564 | 0.00004071 |
| Pairwise envelope | 0.0043 | 0.0011 |

The paired FP32-versus-TF32-off contrast reduced relative error in 20/20 records, with mean
reduction `0.01451894` and a task-cluster bootstrap 95% interval of
`[0.01182715, 0.01846619]`. Projection FP32, FP64 accumulation, TF32-off, checkpoint changes,
separate forwards, and functional VJP did not cross the joint gate.

The development tail was a long `derived_growth_comparison` record whose differential region was
474/5,126 supervised tokens. Its paired relative error fell from `0.03436155` to `0.00363419` under
FP32 activation. The supported engineering diagnosis is BF16 forward-activation rounding in small
differential regions.

### Frozen selection and independent validation

The selector froze `fp32_activation_strict` and an uncertainty envelope of `0.0011` before observing
validation. The independent validation then completed 20/20 fresh checkpoints and passed all gates:

| Metric | Observed | Frozen threshold |
| --- | ---: | ---: |
| Maximum GP delta | 0.00068376 | <= 0.0023 |
| Maximum relative error | 0.00602399 | <= 0.027 |
| Minimum cosine | 0.99998186 | >= 0.99967 |
| Maximum loss identity error | 5.95e-8 | <= 1e-6 |
| Maximum update JS | 5.86e-9 | <= 1e-6 |
| Maximum update TV | 0.00005472 | <= 0.00023 |

All 25 resolvable state pairs, all six task winners, and all six strict task permutations agreed.

Authoritative identities:

- report: `finance_gradient_numeric_root_cause_report:8f9db5c9249904f9846cb7482ad428f0181407a3580d7a00437fa885be57306c`;
- contract: `finance_gradient_numeric_contract:e2a1c890af575f477389b0bfb1475810aeecec3e5f4bf3a6213c552a82fa86b7`.

## v18 Inherited Sealed Numeric Candidate

The first attempt failed before any state metric was computed because the checkpoint loader read
`jobs` from the outer source manifest instead of its nested descriptor. The immutable v1 result
records `execution_failed`, `KeyError('jobs')`, zero checkpoints, and no numeric summary.

A new retry plan allowed only that source-manifest lookup repair and froze every scientific input
unchanged. It computed 20/20 fresh diagnostic checkpoints on GPUs 3-5 and passed all frozen gates:

| Metric | Observed | Frozen threshold |
| --- | ---: | ---: |
| Maximum GP delta | 0.00081042 | <= 0.0023 |
| Maximum relative error | 0.00633034 | <= 0.027 |
| Minimum cosine | 0.99997997 | >= 0.99967 |
| Maximum loss identity error | 5.31e-8 | <= 1e-6 |
| Maximum update JS | 3.37e-9 | <= 1e-6 |
| Maximum update TV | 0.00005026 | <= 0.00023 |

All 24 resolvable pairs, all six task winners, and all six strict task permutations agreed. The
result hash is
`finance_gradient_numeric_sealed_result:ed13f8f07830ad47471293a8c73c22f464844959699b1b91d7c6cc99c94721d2`.


## v19 Sealed Causal Pilot

v19 used six fresh Finance tasks, 20 states, and 60 state-conditioned realizations. The strict-FP32
Gradient execution contract passed, but the independent finite target failed before GP-C was
evaluated. Estimation/Validation reconstruction error was `0.5065/0.3774` against `0.1`, and p95
radius instability was `1.5420/1.4557` against `0.25`. A smaller-radius diagnostic did not restore
local linearity. Authorization remained unopened and `Contribution=0`.

## v20 Finite Target Identifiability Study

v20 implemented the target-measurement redesign requested by the v19 audit. It used six new tasks,
20 states, 60 fresh real-Agent realizations, 16 Estimation records, 16 Validation records, and a
frozen but unopened 16-record Authorization partition. Estimation and Validation were each split
into four mutually exclusive Objective micro-splits.

The frozen direction design contained 14 quotient coordinates and 31 rows: seven direct anchors,
seven block-2 rows, eight block-4 rows, eight block-7 rows, and one null row. Three perturbation
ratios were normalized against the measured global parameter-step norm and evaluated in both
directions. The formal study completed 186 observations per role and 372 overall.

Execution integrity passed again. Maximum parameter-step ratio relative error was `4.3255e-7`,
maximum Gradient recomposition relative error was `0.0073369`, minimum recomposition cosine was
`0.9999732`, and null Objective delta was exactly zero.

Finite-target identifiability nevertheless failed:

| Metric | Estimation | Validation | Frozen requirement |
| --- | ---: | ---: | ---: |
| Direct anchor identifiable rate | `0.0000` | `0.0000` | `>= 1.0000` |
| Maximum direct slope CV | `34.5470` | `4.3135` | `<= 0.5` |
| Maximum p95 nonlinearity ratio | `16.0095` | `63.3579` | `<= 0.25` |
| Maximum block reconstruction error | `1.8606` | `1.8830` | `<= 0.15` |
| Block direction agreement | `0.6522` | `0.5652` | `>= 0.8` |

All fourteen role-wise direct-anchor confidence intervals crossed zero. Only four of seven direct
coordinate signs agreed across Estimation and Validation, so the combined `0.5714` agreement also
failed its frozen `1.0` gate. Block-size error was not monotonic, and direct anchors themselves
were unstable; the evidence therefore localizes the blocker to Objective-level slope
observability, not only to Hadamard-style direction interaction.

The combined status is `failed`; GP-C was not evaluated; Authorization observation count is zero;
and the only valid transition is `retain_contribution_zero_and_redesign_target_measurement`.

## Authorization State

The scientifically correct state is:

- strict-FP32 numeric execution status: `passed`;
- v20 finite-target identifiability status: `failed`;
- v22 Development exact-target execution status: `passed`;
- v22 primary practical-equivalence status: `30/30`;
- v22 all-state practical-equivalence status: `100/100`;
- v22 meaningful-beyond-MPE count: `0/100`;
- v23 final Explorer qualification status: `failed`;
- v23 Factorial Discovery rollout count: `0/1800`;
- `gp_c_evaluated=false`;
- `authorization_objective_access=forbidden`;
- `authorization_objective_observation_count=0`;
- `production_authorized=false`;
- `contribution_authorized=false`;
- v23 report next permitted stage: `protocol_repair_only` under a new frozen contract;
- VTDO updates, Student training, and downstream claims remain unauthorized.

The current evidence establishes reliable strict-FP32 execution and a precise exact one-step target
on Development. It also shows that every observed Development coordinate is materially below the
current MPE. This neither validates nor falsifies GP-C or theoretical Contribution: a proxy cannot
be meaningfully ranked against a Development target with no practically meaningful coordinates,
and no fresh Validation result exists.

## Next Step

Do not reclassify the 15 prospective Verifier v2 candidates, add their paths to State Mapping,
or alter the historical v26.71 Capability and v26.72 Reachability reports. The 0/36 State Support
Freeze remains authoritative. The passing Compiler Witnesses are static verifier fixtures and may
not enter any empirical denominator.

The only permitted transition is:

```text
thinking_completion_telemetry_repair_execution_runner_and_preflight_only
```

The exact v26.91 Manifest has now been fully exposed by v26.92. Do not rerun, recover, or
reclassify any of its 32 Jobs. Its positive typed-no-call result and negative Completion result
remain jointly authoritative: zero typed no-calls pass empirical Budget Adequacy for this
calibration denominator, while 30/32 Completion-unusable outcomes independently block release.
No semantic outcome can rescue the Completion Gate.

The 79 missing response-model values are an unrecoverable historical telemetry gap. All known
response models are exact and zero mismatches were observed, but missing values may not be
inferred from the requested model, selected model, fallback flag, or neighboring responses. The
v26.92 exact-model Gate remains failed and all 32 historical terminals remain
`instrument_failure`.

v26.94 has frozen 24 fresh Completion-repair TaskPackages, 48 static path audits, a new Contract,
and an exact 32-Job Manifest. All 24 v26.90 source role packages are retired from Capability and
Reachability execution. The 324 Compiler projections remain fixtures and may not enter the later
repair denominator, Capability support, State Mapping, or release counts.

The next stage may only implement an exact v26.95 execution Runner and complete a credential-free
preflight. Before credential lookup and client construction it must replay the authoritative
v26.94 report, all eleven v26.94 outputs, all 485 replay bindings, and the exact Runner
implementation. v26.94 itself does not authorize a model call. Any TaskPackage, path selection,
Prompt projection, rescue policy, response-envelope field, model profile, Contract, Manifest,
seed, or resource-bound change requires a new preflight identity.

The Runner must use the frozen primary projection and at most one independent public
decision-terminal rescue per Job. It may not pass back previous final content or private
reasoning, request repeated rescue planning, insert a Host-selected action, or restore a Provider
Plan call. Every Provider call must continue to bind exact `thinking.type=enabled` before
credential lookup and client construction.

On every HTTP success the Runner must persist only the privacy-redacted response model, finish
reason, public final-content hash and length, explicit native-tool presence, reasoning presence
and length, and token telemetry before final-content parsing. A nullable redacted capture may
retain actually observed values when another field is malformed, but the strict response
envelope must still fail closed. Missing model values may never be inferred. Typed failure
artifacts must validate before serialization. Private reasoning content, private reasoning
hashes, and raw HTTP bodies remain forbidden.

At the exact 32-Job denominator, typed no-call and Completion-unusable remain separate
zero-failure Gates at one-sided 95% upper bound 0.10. Zero failures gives
0.08936819898626475 and passes; one gives 0.139849460274226 and fails. Provider transport is a
separate execution-integrity outcome, and semantic validity cannot rescue either Gate.

The 120,000-token rollout ceiling, 60,000-byte Prompt ceiling, 256-token chat envelope,
4,096-token Completion bound, and both 4,096-token reserves remain unchanged. The v26.92
reasoning-token share, 78 completion-limit hits, and repair outcomes motivate a prospective
Completion redesign but do not authorize a larger bound. The v26.94 static path bounds of 52,898
to 111,966 and minimum headroom of 8,034 are certification bounds, not expected Provider Usage or
empirical Completion adequacy.

All 93 v26.91 Compiler paths and 580 local Observations remain fixtures. The 32 model-generated
v26.92 rows remain separate from Capability, Reachability, State Mapping, and release
denominators. Do not rerun or reclassify any v26.78-v26.80 or v26.84-v26.86 Job. The six v26.81
prospective-valid candidates, all v26.82 Compiler Witnesses, all v26.86 descriptive local
successes, all v26.90 Compiler fixtures, and all v26.94 Compiler projections remain ineligible
for empirical support.

A later passing Runner preflight may authorize only execution of the exact v26.95 repair
Manifest. It cannot freeze a Thinking-enabled role protocol. Completion usability, task depth,
and capability informativeness remain unresolved.

Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training,
Exact Target, GP-C, and Contribution remain forbidden. Objective Support remains a separate
unresolved bottleneck.

## Authoritative References

- `docs/finance_v26_94_thinking_completion_telemetry_repair_preflight.md`
- `src/trusted_synthesis/runtime/agent/prospective_thinking_completion.py`
- `src/trusted_synthesis/runtime/agent/prospective_thinking_client.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_completion_telemetry_repair_preflight.py`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/report.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/source_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/role_population_retirement_audit.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/thinking_completion_protocol.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/thinking_repair_task_packages.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/thinking_repair_path_audits.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/telemetry_fixture_audit.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/thinking_repair_contract.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/thinking_repair_job_manifest.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/thinking_repair_freshness_audit.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/destructive_preflight_audit.json`

- `docs/finance_v26_92_v26_93_thinking_budget_calibration_execution_and_audit.md`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_budget_calibration_execution.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_calibration_postrun_audit.py`
- `artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821/report.json`
- `artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821/raw_lineage_audit.json`
- `artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821/calibration_job_results.json`
- `artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821/completion_usability_classifications.json`
- `artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821/thinking_history_audits.json`
- `artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821/provider_budget_audits.json`
- `artifacts/vtdo_experiment/finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821/report.json`
- `artifacts/vtdo_experiment/finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821/completion_root_cause_audit.json`
- `artifacts/vtdo_experiment/finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821/provider_telemetry_gap_audit.json`
- `artifacts/vtdo_experiment/finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821/persistence_integrity_audit.json`
- `artifacts/vtdo_experiment/finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821/telemetry_repair_contract.json`
- `artifacts/vtdo_experiment/finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821/repair_fixture_audit.json`

- `docs/finance_v26_91_thinking_budget_calibration_preflight.md`
- `src/trusted_synthesis/runtime/agent/thinking_history.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_budget_calibration_preflight.py`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/report.json`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/predecessor_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/calibration_source_capacity_audit.json`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/calibration_task_packages.json`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/role_prefix_budget_envelopes.json`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/calibration_stress_path_audits.json`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/thinking_continuity_contract.json`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/completion_usability_contract.json`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/calibration_contract.json`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/calibration_job_manifest.json`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/calibration_freshness_audit.json`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/budget_shape_coverage_audit.json`
- `artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/destructive_preflight_audit.json`


- `docs/finance_v26_90_budget_feasible_role_task_rematerialization.md`
- `src/trusted_synthesis/runtime/agent/compact_budget_prompt.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_budget_feasible_role_task_rematerialization.py`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/report.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/source_capacity_audit.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/source_freshness_audit.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/budget_feasible_role_task_packages.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/budget_qualified_path_audits.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/thinking_mode_binding.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/destructive_preflight_audit.json`

- `docs/finance_v26_prospective_thinking_mode_policy.md`
- `config/deepseek_v4_flash_agent_thinking_v1.json`
- `src/trusted_synthesis/runtime/agent/prospective_thinking.py`

- `docs/finance_v26_88_v26_89_budget_adequacy_audit_and_contract_preflight.md`
- `artifacts/vtdo_experiment/finance_v26_88_budget_adequacy_root_cause_audit_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_88_budget_adequacy_root_cause_audit_20260820/job_budget_diagnostics.json`
- `artifacts/vtdo_experiment/finance_v26_88_budget_adequacy_root_cause_audit_20260820/group_budget_summary.json`
- `artifacts/vtdo_experiment/finance_v26_88_budget_adequacy_root_cause_audit_20260820/budget_adequacy_decision.json`
- `artifacts/vtdo_experiment/finance_v26_89_budget_adequacy_contract_and_static_role_preflight_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_89_budget_adequacy_contract_and_static_role_preflight_20260820/budget_adequacy_contract.json`
- `artifacts/vtdo_experiment/finance_v26_89_budget_adequacy_contract_and_static_role_preflight_20260820/runner_completion_control_audit.json`
- `artifacts/vtdo_experiment/finance_v26_89_budget_adequacy_contract_and_static_role_preflight_20260820/budgeted_public_witness_audit.json`
- `artifacts/vtdo_experiment/finance_v26_89_budget_adequacy_contract_and_static_role_preflight_20260820/role_protocol_preflight.json`

- `docs/finance_v26_84_v26_87_budget_closed_instrument_recovery_and_audit.md`
- `artifacts/vtdo_experiment/finance_v26_84_budget_closed_verifier_bound_instrument_requalification_20260820/execution_binding.json`
- `artifacts/vtdo_experiment/finance_v26_85_budget_closed_recovery_preflight_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_85_budget_closed_recovery_preflight_20260820/recovery_contract.json`
- `artifacts/vtdo_experiment/finance_v26_85_budget_closed_recovery_preflight_20260820/recovery_manifest.json`
- `artifacts/vtdo_experiment/finance_v26_86_budget_closed_verifier_bound_instrument_recovery_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_86_budget_closed_verifier_bound_instrument_recovery_20260820/raw_lineage_audit.json`
- `artifacts/vtdo_experiment/finance_v26_87_budget_closed_postrun_audit_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_87_budget_closed_postrun_audit_20260820/provider_lineage_audit.json`
- `artifacts/vtdo_experiment/finance_v26_87_budget_closed_postrun_audit_20260820/budget_terminal_audit.json`
- `artifacts/vtdo_experiment/finance_v26_87_budget_closed_postrun_audit_20260820/verifier_scoring_audit.json`

- `docs/finance_v26_82_v26_83_budget_closed_rematerialization_and_preflight.md`
- `artifacts/vtdo_experiment/finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820/provider_token_budget_contract.json`
- `artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820/execution_contract.json`
- `artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820/job_manifest.json`

- `docs/finance_v26_78_v26_81_verifier_bound_instrument_recovery_and_audit.md`
- `artifacts/vtdo_experiment/finance_v26_78_verifier_bound_instrument_requalification_20260820/execution_binding.json`
- `artifacts/vtdo_experiment/finance_v26_79_verifier_bound_recovery_preflight_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_80_verifier_bound_instrument_recovery_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_81_verifier_bound_postrun_audit_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_81_verifier_bound_postrun_audit_20260820/completed_trace_scoring_audit.json`
- `artifacts/vtdo_experiment/finance_v26_81_verifier_bound_postrun_audit_20260820/resource_budget_audit.json`
- `artifacts/vtdo_experiment/finance_v26_81_verifier_bound_postrun_audit_20260820/raw_lineage_independent_audit.json`

- `docs/finance_v26_76_v26_77_verifier_bound_rematerialization_and_preflight.md`
- `artifacts/vtdo_experiment/finance_v26_76_verifier_bound_instrument_population_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_77_verifier_bound_instrument_preflight_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_77_verifier_bound_instrument_preflight_20260819/execution_contract.json`
- `artifacts/vtdo_experiment/finance_v26_77_verifier_bound_instrument_preflight_20260819/job_manifest.json`

- `docs/finance_v26_74_v26_75_failure_audit_and_verifier_repair.md`
- `artifacts/vtdo_experiment/finance_v26_74_capability_reachability_failure_audit_v2_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_75_authority_preserving_verifier_qualification_v2_20260819/report.json`

- `docs/finance_v26_69_v26_73_capability_and_reachability_report.md`
- `artifacts/vtdo_experiment/finance_v26_69_fresh_capability_population_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_70_capability_development_preflight_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_70_state_reachability_preflight_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_71_capability_development_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_72_state_reachability_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_73_authority_role_postrun_audit_v3_20260819/report.json`

- `docs/finance_v26_65_v26_68_authority_preserving_instrument_and_protocol_report.md`
- `artifacts/vtdo_experiment/finance_v26_65_authority_preserving_operation_hardening_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_66_authority_preserving_instrument_requalification_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_66_authority_preserving_instrument_requalification_finalization_recovery_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_67_authority_preserving_postrun_audit_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_68_empirical_role_protocol_20260819/report.json`

- `docs/finance_v26_61_v26_64_operation_instrument_repair_and_requalification.md`
- `artifacts/vtdo_experiment/finance_v26_61_operation_closure_regression_v2_20260818/report.json`
- `artifacts/vtdo_experiment/finance_v26_62_public_operation_instrument_hardening_20260818/report.json`
- `artifacts/vtdo_experiment/finance_v26_63_operation_closure_requalification_20260818/report.json`
- `artifacts/vtdo_experiment/finance_v26_64_operation_closure_postrun_audit_20260818/report.json`

- `docs/finance_v26_60_public_operation_and_v26_61_preflight_report.md`
- `artifacts/vtdo_experiment/finance_v26_60_public_operation_rematerialization_v2_20260818/report.json`
- `artifacts/vtdo_experiment/finance_v26_61_operation_closure_regression_preflight_v2_20260818/report.json`

- `docs/finance_v26_57_v26_59_empirical_support_and_failure_audit.md`
- `artifacts/vtdo_experiment/finance_v26_57_empirical_support_pilot_20260818/report.json`
- `artifacts/vtdo_experiment/finance_v26_58_transport_recovery_20260818/report.json`
- `artifacts/vtdo_experiment/finance_v26_59_empirical_failure_audit_20260818/report.json`

- `docs/finance_v26_56_executable_task_rematerialization_report.md`
- `docs/finance_v26_55_executable_support_contract_hardening.md`
- `docs/finance_v26_54_executable_support_precondition_audit.md`
- `artifacts/vtdo_experiment/finance_v26_56_executable_task_rematerialization_20260818/report.json`
- `docs/finance_v25_26_v25_29_answer_contract_and_confirmation_report.md`
- `docs/finance_v20_target_identifiability_report.md`
- `docs/finance_v22_development_power_plan.md`
- `docs/finance_v22_development_exact_target_report.md`
- `docs/finance_v23_capability_sensitive_agent_plan.md`
- `docs/finance_v23_explorer_runtime_factorial_report.md`
- `docs/finance_v19_sealed_causal_pilot_report.md`
- `docs/finance_v18_sealed_numeric_authorization_report.md`
- `docs/finance_v17_numeric_root_cause_report.md`
- `docs/finance_v16_numeric_contract_validation_report.md`
- `docs/finance_v14_real_agent_gradient_projection_report.md`
- `docs/vtdo_experiment_protocol.md`
- `docs/valid_trajectory_distribution_optimization.md`
- `docs/server_recovery.md`
- `artifacts/vtdo_experiment/finance_v20_target_identifiability_study_p2_v1_20260806/combined_report.json`
- `artifacts/vtdo_experiment/finance_v20_target_identifiability_study_p2_v1_20260806/estimation_report.json`
- `artifacts/vtdo_experiment/finance_v20_target_identifiability_study_p2_v1_20260806/validation_report.json`
- `artifacts/vtdo_experiment/finance_v17_sealed_numeric_candidate_retry_v2_20260806/report.json`
- `artifacts/vtdo_experiment/finance_v17_numeric_root_cause_dev20_val20_temp02_v13_20260805/report.json`
- `artifacts/vtdo_experiment/finance_v17_numeric_root_cause_dev20_val20_temp02_v13_20260805/frozen_numeric_contract.json`

## v25.22-v25.23 Mechanism Repair And Information Geometry

The v25.21 Candidate Verification and State-dependent Stopping mechanisms were repaired without
rerunning the two already-replicated recovery mechanisms. The final Flash Development run
completed 96/96 rollouts and froze both repaired mechanisms. A new held-out Population persisted
the Development Selection Freeze identity and passed every static freshness, semantic, scenario,
and public/Oracle isolation gate.

Held-out Confirmation completed 100/100 rollouts. Runtime eligibility, API transport, bounded JSON,
Observation replay, and authority integrity were 100%, with zero Runtime pathology. Candidate
Verification was behavior-successful on 25/25 mechanism trajectories. Stopping was evaluable and
behavior-successful on 19/25; the six unevaluable outcomes remain model failures. Both mechanisms
passed the unchanged matched-pair criteria, so all four frozen mechanisms are independently
confirmed.

The corrected v25.23 v2 geometry audit used 20 mechanism-required tasks and 100 rollouts from the
two held-out Confirmation sources. Coverage was balanced at five groups per mechanism and boundary
mass was 45%. The v2 replay freezes every numerical/source-contract dependency and uses the same
Fisher weights for the information matrix, centering, and general-difficulty regression. The
initial unweighted-residual v1 artifact is superseded.

| Matrix | Numerical rank | Effective rank | Condition number |
| --- | ---: | ---: | ---: |
| Raw | 5 | 1.20598 | 1270.31 |
| General-difficulty residual | 3 | 2.40054 | 5.26 |

The raw distribution remains dominated by a common direction. Removing that direction restores
numerical conditioning but leaves only three independent residual directions, below the frozen
rank-4 and effective-rank-3 requirements.

The current authorization state is:

```text
all_four_mechanisms_confirmed = true
information_geometry_ready = false
pro_sparse_anchor_authorized = false
beneficiary_screening_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = capability_mechanism_support_redesign_only
```

Mechanism confirmation is retained as a positive result. The current task support is rejected as a
well-conditioned capability distribution. See
`docs/finance_v25_22_v25_23_capability_mechanism_repair_and_geometry_report.md`.

## v25.30-v25.33 Stable Capability-decision Support

The measurement contract now uses `capability_contract_success`: semantic answer validity must
co-occur with the registered Host trigger/resolution behavior and no post-completion violation.
Public tasks no longer expose oracle mechanism identity or canonical repair values.

v25.33 completed 480/480 fresh Flash rollouts. Runtime transport, bounded JSON, Observation replay,
and authority integrity were 100%, with zero reported Runtime pathology. The common Top-4 geometry
passed with effective rank 3.5929, condition number 3.4290, and 99.90% bootstrap joint-geometry
success.

The experiment nevertheless failed its preregistered parent-support contract. State-dependent
Stopping contributed only 3.16% of information, had one nonzero task, and had a zero bootstrap
lower bound. Confirmation and Pro remain blocked. Failure-artifact replay also identified a
state-dependent unreachable `uncertain_source_coverage` recovery path, which must be repaired
before a new Stopping boundary calibration.

```text
runtime_measurement_ready = true
common_top4_geometry_passed = true
capability_support_admitted = false
fresh_confirmation_authorized = false
pro_sparse_anchor_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stable_support_redesign_only
```

See `docs/finance_v25_30_v25_33_stable_capability_decision_report.md`.

## v25.34 Stopping Boundary Calibration

v25.34 used one fresh Population, five State-dependent Stopping tasks, and 12 Flash realizations
per task. The first 60-rollout run proved that source coverage was repaired but conflict resolution
remained 0/12. Trace replay identified a generic Runtime defect: typed public conflict dimensions,
candidate actions, and the action-selection rule were omitted from the next decision Prompt and
were lost entirely after an identical failed-call block.

The paired v2 run changed only the content-hashed implementation. It preserved the latest typed
prerequisite contract without selecting the correct action for the model. Runtime remained 60/60
eligible with zero pathology. Conflict resolution reached 10/12, complete Contract success reached
9/12, and the task became a boundary response at 0.75. All frozen v25.34-v2 gates passed.

```text
runtime_measurement_ready = true
stopping_instrument_repair_validated = true
boundary_signal_observed = true
fresh_stable_support_development_permitted = true
historical_result_reclassified = false
fresh_confirmation_authorized = false
pro_sparse_anchor_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = fresh_stable_support_development_population_build
```

See `docs/finance_v25_34_stopping_boundary_calibration_report.md`.

## v25.35 Cross-population Stable-support Development

v25.35 froze all 30 prior submechanism populations, built three mutually disjoint fresh
populations, and completed 480/480 DeepSeek V4-Flash rollouts. Every population passed exact
execution integrity, terminal resolution, Observation replay, authority integrity, zero L0-L2
failures, zero Runtime pathology, and complete typed failed-action context replay.

Stable support did not generalize. Only Population 2 passed all per-population support gates.
Population 1 had a zero Stopping bootstrap lower bound; Population 3 had only one nonzero Stopping
task and a 78.25% joint-geometry bootstrap pass rate. All three pairwise Top-4 bootstrap alignment
rates failed at 38.10%, 54.35%, and 23.30%.

The pooled diagnostic would have passed with 99.95% joint geometry and a 5.60% Stopping LCB, which
empirically confirms that pooled results cannot rescue population failures.

```text
all_population_runtime_ready = true
all_population_capability_support_admitted = false
cross_population_alignment_ready = false
development_admitted = false
fresh_confirmation_preparation_authorized = false
pro_sparse_anchor_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stable_support_redesign_only
```

See `docs/finance_v25_35_cross_population_stable_support_report.md`.


## v25.24 Submechanism Direction Design

v25.24 replaced parent-mechanism labels with 24 typed submechanism candidates: six candidates
inside each of the four independently confirmed mechanisms. A deterministic 6-choose-5 search per
parent evaluates 1,296 balanced designs before any model response is observed. Demand vectors are
mechanically derived from typed Action primitives and Evidence dependencies, then projected off the
common workflow direction.

The selected 20-task design passes every frozen structural gate:

- residual numerical rank 6;
- residual effective rank 4.698069;
- residual condition number 18.862716;
- high-cosine pair fraction 9.47%;
- every axis supported by at least two parent mechanisms;
- 20 distinct workflow backbones.

Only 5/20 selected variants currently have both a Host intervention and real-Finance Materializer
implementation. Static success therefore does not authorize an API run:

```text
structural_geometry_ready = true
runtime_population_ready = false
api_calls = 0
gpu_jobs = 0
next_permitted_stage = submechanism_runtime_implementation_only
```

Flash, Pro, Beneficiary, Exact Target, GP-C, production Contribution, and Student training remain
blocked. See `docs/finance_v25_24_submechanism_direction_design_report.md`.

## v25.36 Stopping Shape Stability Development

v25.36 first replayed v25.35 offline and rejected a Stopping-only explanation for the observed
cross-population geometry drift. It then changed the primary sampling unit from repeated rollout
to independent Finance task: six Stopping Shapes each received four fresh tasks spanning retrieval
join, calculation chain, definition reconciliation, and verification-sensitive selection, with
eight Flash realizations per task.

All 192/192 rollouts completed. Execution integrity, terminal resolution, API transport, bounded
JSON resolution, Observation replay, and authority integrity were 100%; Runtime pathology and
L0-L2 failures were zero. The measurement instrument therefore remains valid.

Shape-level stable support did not fully pass. `authority_coverage_gap` and
`contextual_resolution_choice` passed every task-level gate. `partial_required_evidence` failed
only its hierarchical bootstrap information lower bound. `single_dimension_conflict` was too hard
in three of four strata and derived all observed information from one task. The
`verified_extra_call_cost` control also failed its success and heterogeneity gates, while the
error-risk control passed.

```text
runtime_measurement_ready = true
all_shapes_admitted = false
difficulty_policy_frozen = false
fresh_cross_population_preparation_authorized = false
pro_api_call_count = 0
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stopping_shape_support_redesign_only
```

No pooled estimate, post-hoc task selection, threshold relaxation, or post-hoc Finalizer repair was
used. The only permitted transition is a fresh Shape-redesign Development. See
`docs/finance_v25_36_stopping_shape_stability_report.md`.

## v25.37 Stopping Shape Redesign Development

v25.37 materialized 48 fully fresh Finance tasks: six Shapes, four structural strata, two tasks per
Shape-stratum cell, and eight Flash realizations per task. The three v25.36 passing items were
frozen as positive controls; only partial evidence, single conflict, and extra-call cost received
typed redesigns.

All 384/384 rollouts completed. Runtime execution, terminal resolution, API transport, bounded
JSON, Observation replay, and authority integrity were 100%; Runtime pathology and L0-L2 failures
were zero. All run-manifest hashes and four 384-row denominators verify.

The Shape result remains negative:

- authority coverage gap and contextual resolution choice replicated;
- partial required evidence was saturated in six of eight tasks;
- single-dimensional conflict moved from floor to ceiling but had only four nonzero tasks;
- verified extra-call cost retained a full zero-to-one task range;
- verified extra-call error risk regressed to 0.7188 and missed its 0.75 control threshold.

~~~
runtime_measurement_ready = true
positive_control_regression_count = 1
redesigned_shape_admission_count = 0
all_shapes_admitted = false
difficulty_policy_frozen = false
fresh_three_population_preparation_authorized = false
pro_api_call_count = 0
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stopping_shape_redesign_only
~~~

Both post-completion controls had 100% ordered Host behavior but lower full valid-trajectory
success. This is a preregistered-response diagnostic, not permission to rescue the failed controls.
A future Development must prospectively freeze the Control estimand and redesign the task
dependencies before any new API call. Pro, Beneficiary, Exact Target, GP-C, Contribution, VTDO
updates, and Student training remain blocked.

See `docs/finance_v25_37_stopping_shape_redesign_report.md`.

## v25.40 Stopping Shape Policy Development

v25.40 completed 384/384 fresh Flash rollouts after repairing the Partial tool-output
manifest and replacing descriptive conflict labels with typed public Evidence states.
All Runtime integrity gates passed. Authority and Partial were admitted and both
controls passed; Contextual and Conflict did not.

A causal audit found query-based states were emitted only after their required record
had already been selected and used, making the required query redundant. The next
stage is restricted to a fresh causal-timing repair.

```text
estimand_semantics_frozen = true
shape_support_policy_frozen = false
boundary_candidate_admission_count = 2/4
runtime_control_pass_count = 2/2
pro_api_call_count = 0
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stopping_shape_causal_timing_repair_only
```

See `docs/finance_v25_40_stopping_shape_policy_report.md`.

## v25.43-v25.44 Stopping Instrument Audit

v25.43 and the first v25.44 run historically appeared to validate the
agent_tool_observation.v2 side channel and, in the first v25.44 population,
admitted all four boundary candidates plus both controls. A hardened Snapshot v3
repair subsequently restored exact Definition-pair capacity in the real Finance
Archive:

    Archive scanned / eligible        = 564,297 / 512,845
    base / companion / final facts    = 151,022 / 92 / 151,114
    period / definition pair capacity = 75,509 / 90
    Snapshot status                   = passed

The hardened fresh run completed 384/384 Flash rollouts. Its diagnostic result
was 3/4 boundary candidates and 2/2 controls, with Authority failing only
between-task heterogeneity:

    stopping behavior success       = 268/384 = 69.79%
    full valid-trajectory success   = 183/384 = 47.66%
    answer-semantic success         = 194/384 = 50.52%
    API calls / model tokens        = 3,700 / 19,293,960
    estimated cost                  = USD 1.9192

A recursive raw audit then found the actual P0: 219 of 1,449 tool observations,
covering 32 of 48 tasks, still embedded Host-only event metadata inside nested
strict business results (host_event 219 times and host_event_sequence 63
times). The previous zero-leak audit checked only top-level keys.

The Runtime now recursively rejects reserved Host metadata, emits trigger and
resolution events only through the outer typed side channel, recursively audits
historical predecessors, and verifies aggregate response rates against atomic
Shape rows. Repository-wide validation passes: Ruff, Mypy over 318 source files,
and 733 tests.

All historical v25.43/v25.44 Shape outcomes remain immutable diagnostics but are
invalid for authorization:

    estimand semantics                 = retained
    shape support policy               = not frozen
    three-population preparation       = withdrawn
    Pro / Beneficiary / Exact / GP-C   = blocked
    production Contribution            = 0
    next permitted stage               = fresh instrument-reset protocol only

See:

- docs/finance_v25_43_v25_44_stopping_role_position_validation_report.md
- docs/finance_v25_44_snapshot_v3_capacity_hardening_report.md
- docs/finance_v25_44_hardened_replication_instrument_audit.md
