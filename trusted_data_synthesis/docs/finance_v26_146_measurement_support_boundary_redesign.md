# Finance v26.146 Measurement-Support Boundary Redesign

Date: 2026-08-25

## Decision

Finance v26.146 consumed only the credential-free
`capability_measurement_support_boundary_redesign_only` transition authorized by v26.145. It
implements and freezes a future-only typed Measurement Support boundary. It does not change the
historical v26.141 Runner, the three v26.144 support exits, any historical terminal or validity
label, the Verifier, the Final Grammar, the Candidate language, or a role task identity.

The redesign passes its typed-closure Gate:

```text
registered role Paths                              48
registered state instances                        522
Candidate events                                 3,089
unique typed public states                       3,306
Host exceptions                                     0
failed-Observation Baseline calls                   0
progress-Observation Baseline calls                 0
model action selection/replacement/repair            0
Provider calls                                       0
Stage 2 Provider calls                               0
historical reclassifications                         0
```

Passing this Gate means every audited boundary has a typed result. It does not mean every legal
counterfactual trajectory remains inside Measurement Support. Eighty failed public Operation
events have no selectable public successor and therefore end in a typed Measurement Support exit.
They are not model-invalid trajectories and are not Instrument failures.

The only permitted successor is:

```text
historical_capability_validity_decomposition_audit_only
```

That successor may perform only the v26.147 read-only diagnostic decomposition over the 93 frozen
complete Raw model outcomes. Provider calls, Verifier changes, new Capability identities,
Capability execution, Reachability, State Mapping, training, release, and production remain
forbidden.

## Frozen Inputs

Before loading the new support design, v26.146 replays 7,294 files:

```text
v26.145 transitive source and execution bindings   7,283
v26.145 direct formal outputs                          7
v26.146 implementation files                           4
total                                               7,294
```

It then independently runs the complete v26.145 postrun audit in an empty temporary directory.
All seven outputs are byte-identical. The frozen predecessor partition remains:

```text
auditable lineage endpoints                         96
frozen model outcomes                               93
frozen model-valid trajectories                     17
frozen model-invalid trajectories                   76
historical measurement-support exits                 3
```

No exact Capability estimate is derived from these values. Neither `17/93` nor `17/96` is
promoted to a formal result.

## Prospective Core

The redesign adds two new ownership layers:

- `core/measurement/support.py` defines the generic immutable event, Baseline resolution,
  decision, Contract, and lazy classifier;
- `runtime/agent/prospective_measurement_support.py` adapts the frozen public
  `SemanticActionState` and Candidate ABI to that generic Contract.

The historical `prompt_only_reference_proposal` and all historical Runners remain byte-immutable.
The new adapter is prospective and cannot be used online until a later joint preflight and fresh
Runner rematerialization are separately authorized.

The Measurement Support status is exactly one of:

```text
available      Baseline classification was required and a complete public Baseline Set exists
not_required   this event must not invoke the Baseline classifier
unavailable    the trajectory leaves pre-registered Measurement Support
```

The frozen lazy order is:

```text
public Commit and Observation
  -> no selectable public successor: typed unavailable, zero Baseline calls
  -> failed Observation with a successor: not_required, zero Baseline calls
  -> success with public Progress: not_required, zero Baseline calls
  -> success with no Progress: resolve the public Baseline Action Set exactly once
```

Terminal Verification, Final Commit, and non-public Commit are also `not_required` and make zero
Baseline calls. A Baseline resolver exception is privacy-minimized to typed
`baseline_classifier_exception`; its internal exception text is not retained in the public ABI.

## Public Baseline Action Set

The old Host-only diagnostic selected one reference Action and could raise
`Prompt-only acquisition policy cannot satisfy its public route`. The successor policy returns a
content-addressed set and never chooses an action for the model.

For a state with unresolved inputs, the set contains every visible acquisition Candidate for the
first public unresolved symbol whose acquisition mode has not already succeeded for that symbol.
This keeps alternate public recovery choices while preventing a repeated successful no-progress
mode from becoming its own baseline indefinitely.

For later states, the set contains:

- every schema-compatible Candidate for the first public executable Operation node, falling back
  to every Candidate for that node only when no output schema is required;
- every terminal-verification Candidate with the maximum visible Evidence coverage;
- the visible Final Candidate when Final is ready.

The policy reads only the current public state. It does not read a Path condition, role, Oracle,
Gold, correct answer, future trajectory, target Evidence, expected arguments, or reference
workflow. It does not enter the model Prompt, modify Candidate order, delete a Candidate, or
select, replace, or repair the model Action.

An independent implementation recomputes every Baseline ID. Across 3,306 unique typed states,
all Baseline Sets are available and are exact subsets of the visible Candidate set. Their size
distribution is:

```text
Baseline Actions per state        state count
1                                      1,467
2                                        402
3                                        940
4                                        493
6                                          4
```

The AST authority audit finds zero prohibited reads and zero Prompt exposure.

## Closure Census

The Census reconstructs all 48 already-frozen role Paths and 522 registered state instances.
Those instances contain 477 unique registered state identities because some Path surfaces are
content-identical. Primary, ABI Rescue, and Semantic Recovery coverage contributes 1,566
registered phase-state instances. The independent recovery construction yields 501 unique
Semantic Recovery states.

Every visible Candidate is evaluated through the frozen public Validator and reversible Commit.
Every public call is then executed by the local deterministic Runtime against the exact public
Observation prefix. This creates 3,089 event rows:

```text
failed public Observations                         1,667
  with selectable successor, not_required          1,587
  without selectable successor, typed unavailable     80
successful Observations with Progress                864
successful Observations without Progress             510
Terminal or Final events                              48
total                                               3,089
```

All 510 successful no-progress events invoke the Baseline classifier exactly once. Of those, 132
select a Baseline Action and 378 select a non-Baseline Action that is classified as one Ordinary
Detour. Baseline-unavailable events are zero.

The decision partition is:

```text
available                                            510
not_required                                       2,499
unavailable                                           80
```

The 3,306 unique typed-state rows have overlapping coverage categories:

```text
registered reference state                          477
ABI Rescue state                                    477
Semantic Recovery state                             501
blocked-action state                                  9
failed-Observation successor                      1,434
progress-Observation successor                      684
successful no-progress successor                    372
one-Detour successor                                267
terminal-verification state                          48
```

The category counts overlap by design and do not sum to 3,306.

## Newly Localized Support Exits

The exhaustive all-Candidate control exposes 80 events where a failed public Operation leaves no
selectable successor Action. The state compiler's exact historical exception is converted to a
typed terminal identity and reason:

```text
public_replan_state_unavailable_after_failed_observation
```

Their public Runtime error partition is:

```text
calculator_contract                                 76
normalize_metric_unit_period_contract                4
```

Every row is an `execute_public_operation` Candidate. Twenty occur on the existing Capability
static surface and sixty on the existing Reachability static surface. These are zero-generation
counterfactual Candidate classifications, not online model selections, empirical Capability or
Reachability rows, or evidence that the model would select them.

This result does not authorize a Candidate change. It establishes the exact typed support
boundary that a later joint Runner preflight must preserve. A future Capability execution still
has a noncompensatory zero-support-exit Measurement Gate.

## Historical Orphan Control

The three exact v26.142 orphan root-cause rows all have a real successor State after
`typed_selector_requires_refinement`. Under the future Contract, each produces:

```text
status                 not_required
reason_code             failed_observation
Baseline calls          0
future model replanning allowed
```

The control uses a resolver that raises immediately if called. It is not called in any of the
three rows. This is a future-only contract result. The v26.141 orphans and v26.144 support-exit
terminals remain unchanged and are not reclassified.

## Destructive Controls

Sixteen mutations fail closed, including:

- counting a failed Observation as an Ordinary Detour;
- invoking Baseline classification for a failed or progress Observation;
- deleting an independently recomputed Baseline Action;
- adding a non-visible or duplicate Baseline Action;
- increasing the one-Detour allowance;
- treating Support unavailable as model-invalid;
- authorizing historical reclassification, a Verifier or Final Grammar change, a Provider or
  Stage 2 Provider call, a new Capability Population, or State Mapping.

## Reproducibility

The formal output directory contains nine canonical JSON files: eight detail artifacts and the
top-level report. The closure Census retains all 3,306 state rows and 3,089 event rows, including
the exact public Observation error codes for all typed successor-unavailable exits.

Focused v26.146 Pytest passes 3/3 in 584.71 seconds, including a complete rebuild and
byte comparison of all nine formal files. On the final tree, the adjacent v26.145 tests pass
2/2 in 353.30 seconds, so the selected v26.145-v26.146 set passes 5/5. Focused Ruff check and
format, PyCompile, and Mypy pass. Package-wide Mypy checks 466 source files and retains only the
three pre-existing v26.70/v26.129 diagnostics, with zero v26.146 diagnostics.

## Authoritative Identities

- report:
  `finance_v26_measurement_support_redesign_report:aa2d6a079ef8ebe97d7d10fa90a6fcfb844faa39310a26e2b4a1e8120bfa41c5`;
- source replay:
  `finance_v26_measurement_support_source_replay:11468347f9f2fa06ac8d1858e20a8413fe6fcbfca3ae4be99d0e1666b02bcf86`;
- predecessor integrity:
  `finance_v26_measurement_support_predecessor_integrity:b3cbb8726c78daa0f951821f4cc296b523f5df6f0d99c110c7b9e66cae7fff6b`;
- Measurement Support Contract:
  `prospective_measurement_support_contract:b49e6a5d66ee7d423ef9944739b30a516d5df84003e157055e99faefdb84398b`;
- Baseline authority:
  `finance_v26_public_baseline_authority_audit:ef276425a9786d7edd8301320ffc4218f4dd40f9cfc484eba06f43f56c2779c3`;
- typed closure Census:
  `finance_v26_measurement_support_closure_census:8ba3f71d4db54e0d66da5f2b84fbaa31a303a9ef5cfb941e85df7a1e594812b1`;
- orphan future-only control:
  `finance_v26_orphan_future_support_control:86c93302b864eedf2339bb15533d424dd50267b6094280f9fb2c2368562911ea`;
- destructive audit:
  `finance_v26_measurement_support_destructive:fa5212e0c3929028a1f80f60426a752e892284f97b738c447d4a22c04aafba33`;
- transition:
  `finance_v26_measurement_support_transition:b72ddd97cb2440fea1eddb3553cefea584abc7168762c06321ba2a864ea5e982`.

## Permitted Transition

The only permitted transition is:

```text
historical_capability_validity_decomposition_audit_only
```

The successor may read only the 93 frozen complete Raw model outcomes and the three frozen
support exits. It must keep historical terminals and historical independent-validity labels
unchanged while emitting separate counterfactual diagnostic fields for base validity, mechanism
qualification, and qualified validity. The three support exits remain validity-unevaluable and
outside all validity denominators.

Verifier changes, Final Grammar changes, new Capability Population or identity materialization,
Provider calls, Capability execution, Reachability identity or execution, State Mapping,
training, release, and production Contribution remain forbidden.
