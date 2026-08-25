# Finance v26.154 Fresh Reachability Execution Protocol

Preparation date: 2026-08-26

## Authorization

This protocol consumes only the v26.153 transition:

~~~text
fresh_reachability_execution_only
~~~

It may execute exactly the fresh 360-Job Reachability Manifest
`finance_v26_fresh_reachability_manifest:65e2e92ed30915fd615bf0dba6c72a7b764ab2c927dc355339bac303fb9830c0`.
It may not alter or resample a source, task, Tier, Path, condition, seed, Prompt, Candidate,
Grammar, classifier, model/Thinking profile, resource value, recovery allowance, Measurement
Support rule, Verifier rule, or qualified-validity rule.

Capability rerun or pooling, historical reclassification, State Mapping Contract or rows,
training, release, and production Contribution are forbidden.

## Credential-Free Preparation

The final implementation completed `--prepare-only` before credential loading. It replayed
10,156/10,156 files:

- all 10,136 v26.153 transitive source bindings;
- all nineteen v26.153 formal outputs; and
- the exact v26.154 implementation.

It independently rebuilt all nineteen v26.153 files byte for byte. The nested rebuild reproduced
all nine v26.152 outputs, all 96 v26.152 Raw projections, the 411-state current Support Closure,
the 159/203 current Detour partition, the 360-Job scripted fixture, 33 Runner controls, and 34
destructive rejections.

The authoritative preparation identities are:

- execution source replay:
  `finance_v26_fresh_reachability_execution_source_replay:70da94ec0428dc2c8600b0f22b0b491af36932ba2fcd2bf125db459a17a517c6`;
- preexecution binding:
  `finance_v26_fresh_reachability_preexecution_binding:54e89cf62e0a7310d9e237c08821b400b1ed2501464ce086be351e4f09d3b43c`;
- Runner Contract:
  `finance_v26_fresh_reachability_runner_contract:1c98edf4575b941b63dd81ea9e2bdf231a797ec6e979588bc80de550bc171206`;
- Outcome Contract:
  `finance_v26_fresh_reachability_outcome_contract:92b5aa2dd501538181b52613604f505d120a3d468ab3b70fd5cd539f63aa1663`;
- prospective execution:
  `finance_v26_fresh_reachability_execution:3ecaeff28dba29932b0e4d8aff506af152bb36b3dd59859941ed6b98a795842c`;
- prospective report:
  `finance_v26_fresh_reachability_execution_report:d6f431047ec9c5f620dbaea2408ed394127a45190630eb8ca046baa23af1c556`.

The formal prepare directory contains only seventeen source/preexecution/frozen-input files.
Raw Execution, Provider Envelope, public Projection, Transport certificate, checkpoint, result,
and report counts are zero. Model-client construction and Provider calls are zero.

## Exact Denominator

The Manifest contains:

~~~text
source Tasks                              12
Mechanism x Tier cells                    12
registered conditioned Paths             36
unconditional Jobs                       144
conditioned Jobs                         216
exact Jobs                               360
distinct preserved seeds                 360
historical Job overlap                     0
~~~

Unconditional Jobs have twelve repeated measures per independent Task and carry no requested Path
or public route condition. Conditioned Jobs have six repeated measures per registered Path and
bind the exact Path ID, strategy, public condition, and condition identity. A common pre-call
binding helper validates the complete Job-to-Task-to-Path chain and renders the same condition in
Action Primary, ABI Rescue, Semantic Recovery, Final Primary, and Final Rescue Prompts.

Static Compiler Paths are target conditions only. Neither a static Path nor a local fixture is an
empirical structural state.

## Online Runner

The Runner retains exact `deepseek-v4-flash`, `thinking.type=enabled`, JSON response mode,
16,384 requested Completion tokens plus the frozen one-token accounting margin, privacy-first
Envelope/Projection persistence, and zero-Provider Stage 2.

Every call requires dynamic state, exact request, resource, route, and single-use invocation
bindings before Provider behavior. The execution uses eight workers by default. It drains every
future before deciding whether the attempt is complete.

After each complete Raw and measurement projection, the main thread atomically rewrites a
canonical checkpoint in Manifest order. A completed report with pending Jobs fails closed.

A pending Job follows exactly one of three branches:

1. no artifacts: it may execute once;
2. complete Raw without checkpoint: it receives zero-call Raw-only measurement recovery; or
3. Provider/Projection/Transport artifacts without Raw: it is an orphan and cannot be retried.

Worker exceptions are retained until all futures drain. A Job with complete Raw is then
reprojected with no client. A Job without complete Raw remains unresolved and stops aggregation.
No automatic replacement Job or Transport recovery beyond the frozen Runner allowance is added.

## Measurement Projection

Each Raw produces one content-addressed Reachability measurement result. The result binds:

- Job, TaskPackage, source task, Mechanism, Tier, replica, and seed;
- sampling mode and all four optional route fields;
- Raw identity and exact Raw descriptor;
- Measurement Support, endpoint, Instrument, and Privacy eligibility;
- online Prompt noninterference and authority-preserving Runtime replay;
- Decimal-aware answer semantics and all fourteen Base checks;
- Mechanism event-language qualification;
- Qualified validity and State Mapping eligibility;
- Provider/Transport counts, Usage, cost, and telemetry integrity; and
- zero Stage 2 Provider and zero State Mapping rows.

`state_mapping_eligible` is exactly `V_qualified is True`. It is an eligibility flag, not a
Mapping Assignment or mapped state.

## Estimands And Gate

The noncompensatory Measurement Gate requires:

~~~text
complete Raw                         360/360
model endpoints                      360/360
Measurement Support exits                  0
Instrument failures                        0
Privacy failures                           0
exact model/Thinking/Usage failures        0
typed budget no-calls                      0
unresolved Transport failures              0
~~~

A Gate failure does not delete a Job or relax a threshold. It leaves all primary fractions null
while preserving complete terminal and validity diagnostics.

When the Gate passes, the primary summaries remain separate:

- twelve unconditional Task summaries with denominator 12 per Task;
- thirty-six conditioned Path summaries with denominator 6 per Path; and
- four Mechanism summaries that retain the Task-primary and Path-primary estimands separately.

Rollouts are secondary repeated measures. The aggregate 360-row counts are descriptive and do not
replace Task- or Path-primary fractions.

## Aggregation Safety

Canonical JSON projection recursively handles Pydantic models nested in Mapping, list, and tuple
containers before serialization. This prospectively closes the exact v26.151 tuple-nested
BaseModel aggregation failure shape without changing canonical key ordering or separators.

Formal outputs after a complete execution include the checkpoint, 360 Raw Executions, every
privacy-first Provider pair and Transport certificate, 360 measurement results, online
noninterference rows, Raw Lineage, Measurement Gate, twelve unconditional Task summaries,
thirty-six conditioned Path summaries, four Mechanism summaries, and one report.

## Local Verification

Focused Ruff and Mypy pass. Focused Pytest passes 2/2 in 236.56 seconds.

The local control reparses the seventeen prepare-only files and confirms zero online artifacts. It
then rebuilds all conditioned and unconditional reference Paths and executes one scripted Job of
each sampling mode. Both exact route bindings, Prompt noninterference audits, Runtime replays,
resource checks, privacy pairs, reversible Commits, and tuple serialization pass.

The scripted client does not certify Provider-native-tool absence, so these two local rows are
correctly Instrument-ineligible and contribute no Qualified or Mapping-eligibility evidence. This
does not relax the online zero-failure Gate; every real Provider row must certify native-tool
absence.

## Postrun Boundary

Regardless of whether the Measurement Gate passes, the only prospective next stage is:

~~~text
fresh_reachability_postrun_audit_only
~~~

The successor must independently replay every Raw and Provider artifact, reconstruct every Prompt,
Support decision, Runtime replay, Base report, Mechanism report, Qualified report, route binding,
Task summary, Path summary, Mechanism summary, Gate, and report aggregate without using the
v26.154 projector or aggregation helpers as an outcome oracle.

State Mapping Contract creation and State Mapping execution remain forbidden until that
independent audit closes the exact 360-Job denominator and explicitly authorizes a fresh
valid-only Mapper preflight.
