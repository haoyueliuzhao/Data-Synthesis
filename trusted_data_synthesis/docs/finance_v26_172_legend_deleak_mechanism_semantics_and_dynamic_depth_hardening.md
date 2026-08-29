# Finance v26.172 Legend Deleak, Mechanism Semantics, And Dynamic Depth Hardening

Audit date: 2026-08-29

## Decision

Finance v26.172 consumes only:

```text
capability_observation_legend_deleak_mechanism_semantics_and_dynamic_depth_hardening_only
```

The bound external audit is exactly 24,338 bytes with SHA-256
`6ea8f1589fd3e6c56007f8d13385b0459a7a07b4a3c065bdf2f1d89a716ec517`.
Credential lookup, Provider-client construction, Stage 1 or Stage 2 Provider calls, Development
Jobs, sealed Confirmation payload access, GPU jobs, Mapper calls, State Assignment, Contribution,
VTDO, Student visibility, training, release, and production use are zero.

The stage preserves all v26.171 files and results. It blocks, without execution, the v26.171
transition
`capability_observation_validity_separated_causal_deleaked_development_runner_preflight_only`.
That transition cannot repair the reviewed presentation, mechanism, Candidate, or dynamic-depth
objects because it forbids changing those objects.

The strongest v26.172 result is a credential-free static and local-runtime hardening result. It is
not model behavior, an empirical Development boundary, or an unrestricted capability claim.

## Predecessor Replay And Defect Reproduction

The complete v26.171 directory is rebound as 23 immutable files. Before a v26.172 scientific
object is created, the current implementation independently rebuilds all 23 files in an empty
temporary directory and requires byte equality.

The reviewed defects are independently reproduced:

```text
v26.171 target States                                      80
v26.171 six-Replica Prompts                               480
reference at choice_legend[0] States                      80
legend-first reference recoveries                        480
unique reference semantic-length States                   32
declared dependency links                                  80
dependency-bearing Components                              48
predecessor-conditioned Prompts                             0
reverse-topological Stopping links                         12
Base-true / old canonical-Mechanism-false executions       26
Recovery wrong-current-Rule Runtime-legal Candidates       20
fully rehashed forged-baseline Catalog accepted by v26.171  1
```

The forged v26.171 control changes a saved baseline `chosen_choice_handles` value, recomputes the
Result, Package, Group, and Catalog identities, and confirms that the old schema accepts the new
graph. This does not mutate or invalidate the formal v26.171 Catalog; it reproduces the reviewed
parent-validation gap.

## Joint Legend And Candidate Presentation

The v26.172 model-visible Legend no longer serializes an ordered tuple of complete operations.
Each current State contains:

1. one shared semantic value catalog per argument field;
2. a fixed-width two-digit index row for each displayed Choice;
3. a Replica-local fixed-width display Choice handle;
4. separately balanced Legend and Candidate row order.

The semantic value catalogs remain public and sufficient to reconstruct every operation. The
equal-width index rows are a structural projection, not hidden padding. The public Prompt contains
no `padding` field.

For each exact `Package x Component`, six Replicas jointly balance:

```text
reference Legend position
reference Candidate position
reference display-handle lexical rank
```

Two-choice States place the reference three times in each position and rank. Three-choice States
place it twice in each position and rank. The display handle is a pre-outcome pseudonym and does
not equal the operation-derived v26.171 semantic handle.

Across 80 States, 480 presentations, and 1,356 displayed Candidates:

```text
unequal encoded Legend-row widths                 0
Legend reference-position imbalances              0
Candidate reference-position imbalances           0
display-handle rank imbalances                     0
visible padding fields                             0
registered full-recovery shortcut selectors       0
```

The exact registered shortcut success counts are:

```text
legend_first                  174 / 480
legend_last                   174 / 480
legend_index                  174 / 480
choice_handle_order           174 / 480
semantic_payload_length         0 / 480
lexical_shape                   0 / 480
```

The value 174 is the exact structural baseline induced by fourteen two-choice and 66 three-choice
States under six balanced Replicas. These six controls reject the reviewed deterministic
shortcut; they are not a proof against every possible model-visible statistical association.
The computed-evidence report states this scope explicitly.

## Mechanism Semantics

v26.172 replaces the old single interpretation with two content-addressed fields:

```text
reference_path_match
mechanism_semantically_qualified
```

`reference_path_match` is an exact canonical-path diagnostic only. It does not enter the semantic
mechanism Gate.

The semantic Gate is family-specific:

- Context-conditioned Action requires a real applied current-State decision and task closure;
- Semantic Reconciliation requires real normalized-reference emission and consumption in order,
  followed by task closure;
- Failure Recovery requires a real typed failure, a changed selector, a successful retry, ordered
  events, and task closure, but not one unique selector or record path;
- State-dependent Stopping requires Runtime-derived readiness, verified stopping, and no later
  postcompletion call.

The complete surface is 32 baselines plus 146 legal single-Choice nonreference executions. Its
result is:

```text
executions                                         178
exact reference-path matches                        32
semantic-mechanism-qualified                        66

Base=true,  semantic=true                           58
Base=true,  semantic=false                           0
Base=false, semantic=true                            8
Base=false, semantic=false                         112
```

All 26 old `Base=true / canonical-Mechanism=false` executions become semantic-Mechanism true:

```text
Context record-order alternatives                    6
Failure Recovery noncanonical successful paths      20
```

This establishes that those rows differed from the registered canonical path, not that the target
mechanism was absent. The eight `Base=false / semantic=true` rows are mechanism-occurrence
diagnostics only. They remain task-invalid and Qualified-invalid.

## Dynamic Interaction Contract

Every Package receives a dependency-derived topological Component order. In particular, Stopping
readiness Components precede `stopping.final_decision`; the old twelve reverse-topological links
become zero.

The local reference fixture exposes only one current Prompt at a time:

```text
current public State
  -> one selected displayed action
  -> exact Runtime-event-backed public Observation receipt
  -> content-derived next public State
  -> next Prompt
```

Each dependent next State contains the exact public predecessor receipt IDs required by its
Component graph. The Runner Contract forbids a precommitted Choice vector, future-Prompt access,
and complete Prompt-tuple materialization in a Runner input.

The static reference evidence contains:

```text
Packages                                        32
six-Replica local reference Traces             192
reached Prompts                                 480
reached public Observations                     480
declared dependency links                        80
predecessor-conditioned Prompts                 288
bound predecessor-receipt links                 480
reverse-topological links                         0
precommitted-vector rejection controls            1
future-Prompt access rejection controls           1
```

The complete 192 reference Traces are an audit artifact, not a Runner input. A separate
32-Package `DynamicRunnerInputCatalog` contains zero materialized Prompts, zero materialized
Observations, no trace payload field, and no access to the reference Trace Catalog. The successor
transition binds this zero-Prompt Catalog.

The reference fixture uses a public-only local selector and exact event partitions from a fresh
baseline Runtime replay. It measures local protocol constructibility, not how a model will choose
or how an online transport will behave.

Depth is deliberately interpreted as:

```text
bounded sequential target-decision depth, not a latent ability boundary
```

D0-D3 still contain one through four target decisions. A later success decline may therefore
include the multiplicative burden of repeated decisions. v26.172 does not identify a latent
capability threshold from that design.

## Candidate Legality Layers

Every one of the 226 exact semantic Candidates is classified separately as:

```text
publicly_grounded
publicly_executable
state_precondition_valid
mechanism_relevant
task_semantically_valid
```

The resulting counts are:

```text
publicly grounded                               226
publicly executable                             226
current-State precondition valid                206
mechanism relevant                              206
task semantically valid                         106
```

The twenty Recovery Candidates that refer to a Rule other than the current failed Rule remain
publicly grounded and executable distractors. All twenty are explicitly State-precondition false
and mechanism-irrelevant for that current State. The report does not call all 226 Candidates
"Runtime-legal" without qualification.

## Baseline Trace Parent Binding

All 32 baseline Results are rerun from the exact frozen Finance Core, public Task, Components, and
reference choices. Each binding records and compares:

```text
chosen Choice handles
Runtime event IDs
Runtime event order
task-validity report
old canonical mechanism report
Qualified-validity report
complete canonical Result bytes
```

Canonical Result, chosen-handle, event-ID, event-order, task-report, mechanism-report, and
Qualified-report matches are each 32/32.

Two independent whole-graph controls alter either selected handles or event order, recompute every
affected binding, Package, Group, and Catalog identity, and are then checked against a fresh exact
predecessor Runtime replay. Both reject. Together with the other protocol controls, all fourteen
production destructive mutations fail closed.

## Reproducibility And Checks

The formal directory contains 22 files and 7,990,956 bytes. Its report SHA-256 is
`176d0bec49d1d2816b992954b10f3aefb030107e356b09b14cb0a2b8f43500f8`.
The transitive implementation Root contains 310 local files and zero unresolved
`trusted_synthesis` import.

Focused Pytest passes 6/6 in 28.92 seconds, including a complete empty-directory byte-identical
rebuild. The adjacent v26.171-v26.172 non-rebuild regression passes 10/10 in 16.08 seconds.
Focused PyCompile and package-wide Ruff pass. Focused Mypy with
`--no-incremental --follow-imports=skip` reports no issue in the three new source modules.

The current Python 3.14 / Pydantic 2.13 environment makes ordinary focused Mypy recursively inspect
historical imports and reports 5,692 existing `model_construct(**dict)`-style diagnostics across
158 files. Therefore v26.172 does not claim a package-wide Mypy pass in this environment. This
toolchain result is separate from the focused new-source pass and from the scientific Gates.

## Authoritative Identities

- report:
  `finance_v26_dynamic_depth_hardening_report:4a909817dea422643854a5452b2f932111147b8257974371aedadbe228d2c8d2`;
- transitive source Root:
  `finance_v26_dynamic_depth_transitive_source_root:371f46d0315fc081bb675c1bc905b74b76440dae29b67024b227f5749388daa7`;
- v26.171 Freeze audit:
  `finance_v26_v171_predecessor_freeze_audit:f5a97ef6e74e0454808eb92d60dd43fec2a504d6c7c3fa7a00fafa828005e35e`;
- v26.171 defect reproduction:
  `finance_v26_v171_dynamic_depth_defect_reproduction:e373622367065c7630c995ac5ea75011d94233411ff6152bcaf406e5817c96bd`;
- Joint Legend Presentation Contract:
  `joint_legend_candidate_presentation_contract:23afa9fb1217b361f055158f5c9e8b28261b1504588269896add7db3e883712a`;
- Mechanism Semantics Contract:
  `capability_mechanism_semantics_contract:387b6a2749d1f77387847626cb18a9544af60f96ff0034c71576097dc867a1f6`;
- Dynamic Depth Runner Contract:
  `dynamic_depth_runner_contract:bb078f09aeec576d8e2581f353a36727e7bc819fad624611819f54e47276a04a`;
- Candidate Legality Contract:
  `layered_candidate_legality_contract:ad307d45db7cc1b04aa112d7424c7d1240d23328f1753f1a0bc3d5c7d7b744c0`;
- Baseline Trace Binding Contract:
  `baseline_trace_parent_binding_contract:8192d19122ae836aa8ac97fb57f15a5d1b37e74f4c7ff8cd753b4db07843612d`;
- Dynamic Development Catalog:
  `finance_v26_dynamic_depth_development_catalog:38d6f3d60384356e5a455ce0aac54931f20f31ace92bab1919940b110bb1eb97`;
- zero-Prompt Runner Input Catalog:
  `finance_v26_dynamic_depth_runner_input_catalog:370662e3268cf6943e4ed7ea6db50ce3802ecccdee2b880a3dad1b823741a8d5`;
- Legend Shortcut audit:
  `finance_v26_legend_shortcut_audit:16aebb20584fa5ebb0ef507623de988d787ec0187882eabe3b720aacef36baa7`;
- Mechanism Semantics audit:
  `finance_v26_mechanism_semantics_audit:e227dec520dec70f9a6d197369d8ca84ed1c64b38aa9e9cda04f663b83c15e80`;
- Dynamic Interaction audit:
  `finance_v26_dynamic_depth_interaction_audit:358c6332b8779dbe00379edb8445a9f142365b3987e3d47acb62e5d76770dc1a`;
- Candidate Legality Catalog:
  `finance_v26_layered_candidate_legality_catalog:b14613fc46560d5f89548c54585da2ea459f62e79a9b1944dbf6ac59b68fc1bc`;
- Baseline Trace Parent audit:
  `finance_v26_baseline_trace_parent_audit:428d9683f72f346a2982c14283b73a48728a7758a481faa8380dd320ae30df70`;
- static audit:
  `finance_v26_dynamic_depth_static_audit:30dc2810a9385e6c80cbe48ebf542d9872e0045dbc2faefda64a32e9ab081cdc`;
- transition:
  `finance_v26_dynamic_depth_transition:4a8c5ce21861c38324df055a31c7cb42574dc6c372e2a6497ad0429b54d1f3bc`.

## Permitted Transition

The only permitted transition is:

```text
capability_observation_dynamic_depth_development_runner_preflight_only
```

The successor may materialize only the exact future 192-Job Development Manifest and perform a
credential-free Runner preflight from the exact zero-Prompt Runner Input Catalog. It must generate
one current Prompt at a time, accept one model-owned action, commit its public Observation, and
rebuild the next State from exact predecessor receipts under all frozen v26.172 source, public
Task, topological Component, shared semantic table, joint Legend/Candidate balance, Mechanism
Semantics, Candidate Legality, baseline trace, model/Thinking, Grammar, Policy, resource,
threshold, terminal, and sealed-receipt parents.

Provider execution, Development outcomes, loading static reference Trace payloads as Runner
inputs, precommitted Choice vectors, future-Prompt materialization, Confirmation payload loading,
source Core or task change, semantic Candidate change, threshold tuning, historical rewrite,
Mapper, State, frequency, Contribution, VTDO, Student visibility, training, release, and
production remain forbidden.
