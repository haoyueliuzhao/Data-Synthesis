# Finance v26.56 Fresh Executable-Task Rematerialization

Audit date: 2026-08-18

## Summary

Finance v26.56 implements the fresh no-API Population construction required by the v26.55
contract audit. It does not patch any immutable v26.42 or v26.43 task. Instead, it creates a new
task identity only after the required public tools are closed and binds every executable-support
contract to one pre-identity semantic source.

The new Population contains 24 real-Finance tasks:

```text
4 mechanisms x 6 tasks = 24 tasks
3 capability-only + 3 VTDO-candidate tasks per mechanism
```

All static gates pass:

| Gate | Result |
| --- | ---: |
| Required-tools closure | 24 / 24 |
| Single-source package binding | 24 / 24 |
| Citation-complete Public Executable Witness | 24 / 24 |
| Target-matched Mechanism Necessity | 24 / 24 |
| Capability prerequisite eligibility | 24 / 24 |
| Static VTDO-candidate eligibility | 12 / 12 |
| Static model-authority paths | 36 |

The `24/24` capability count is a prerequisite count. Intended use remains frozen at 12
capability-measurement tasks and 12 VTDO-multistate candidates; passing the weaker capability gate
does not change a task's registered role.

The authoritative report identity is:

```text
finance_v26_executable_task_rematerialization_report:abc3df8dfbb4c01e17693b48a777f3679c7d8656a88a96c3d1d41a6e5736ea81
```

The result permits only:

```text
capability_development_and_state_reachability_pilot
```

Fresh Confirmation, No-C VTDO, Student training, Exact Target, GP-C, and production Contribution
remain forbidden. Production Contribution remains zero.

## Frozen Sources

### Task source

The task source is the previously unopened v26.42 Confirmation Population:

| Item | Identity |
| --- | --- |
| Population | `finance_v26_fresh_task_population:a05192aee372acaf5504cadffc9274295591d0a6ffcda42fdca55bffd2d75e14` |
| File SHA-256 | `449f124b86b7edfc69051e980e31e858255a1ae17e27613f5ee3ab9d26a12852` |
| Cross-population freshness audit | `finance_v26_cross_population_freshness_audit:bb85de840bdf2aa184b8702825903071c16959eebb0cc7b06a6afdb5da58a539` |

Using this source for rematerialization permanently retires it from the Confirmation role. A later
Confirmation must be newly sampled and must be disjoint from v26.56 by task, Evidence, Evidence
Version, semantic signature, and trajectory identity.

### Evidence source

The builder replays the v26.29 exposure-clean receipt and the v25.44 hardened Finance Snapshot
before selecting any new Reconciliation task:

| Item | Value |
| --- | ---: |
| Snapshot SHA-256 | `c6ac2b985607a0f964cb919010bd9a7c9eee9ac57534983e4ab09a7b10c3f17e` |
| Exposure receipt | `finance_v26_exposure_clean_population_receipt:c7986e19da5c9b63bf25c0af8bc6c9783c6942abe5f33db49919cc2f0478d6d7` |
| Source Evidence | 151,114 |
| Exposure/Grounding exclusion union | 26,290 |
| Additional selected-source/Development exclusions | 261 |
| Eligible Evidence | 124,574 |
| Eligible Definition pairs | 38 |
| Reconciliation task capacity | 19 |
| Selected Definition pairs | 12 |
| Materialized Reconciliation tasks | 6 |

The capacity audit identity is:

```text
finance_v26_definition_pair_capacity_audit:e31d0bac1e865234af15446b9d2b7a4ee7191226535a75c7538998aeafa36361
```

All 24 selected Definition-pair Evidence identities are unique. Public Corpus Evidence is also
disjoint across all 24 rematerialized tasks.

## Identity Architecture

### Tool closure before task identity

For every draft, the materializer derives:

```text
RequiredTools = ProgramTools union VerificationTools union RecoveryTools
```

and requires:

```text
RequiredTools subseteq AllowedTools
```

before computing the executable TaskPackage identity. Removing any required tool causes the typed
`ToolClosureContract` to fail; the draft cannot receive a valid package identity.

The six Reconciliation tasks now include `normalize_metric_unit_period` in both the required and
allowed sets. This directly closes the v26.54/v26.55 defect in which normalization was required
but publicly unavailable.

### One semantic source

Each `ExecutableTaskSemanticSource` binds:

- source task artifacts and Evidence Versions;
- Evidence Bundle, Public Corpus, Proof Graph, and Task Program hashes;
- retrieval scope;
- answer source specification;
- mechanism source specification;
- intended task role.

The following objects must all reference that same semantic source:

- Tool Closure;
- Typed Answer Projection;
- Evidence Support Lattice;
- Citation Contract;
- Public Runtime Contract;
- Mechanism Causal Contract;
- Executable Verifier Binding.

The final `ExecutableTaskPackage` identity includes all of these contracts. Public task metadata
contains only public binding IDs. Evidence-lattice, mechanism, semantic-source, and Verifier IDs
remain in the Oracle contract.

### Implementation bytes

The report identity also binds the exact source bytes used to create it:

| Source | SHA-256 |
| --- | --- |
| `core/trajectory/executable_task.py` | `9556791c47df831852976dc86319989bdc19eca87c8dcf5583e99ad19ac9c7be` |
| `domains/finance/executable_support_runtime.py` | `6722da53a86ea220e113309b1109c57bf7f35a7ecb222e9ebfa84266ee9839a3` |
| `experiments/vtdo_experiment/phase1_v26_executable_task_rematerialization.py` | `d7d361a71a81a2b96634b190cfd8f7a2bcf0c1390105c01322757cfcf9072e34` |

This prevents a report from retaining the same version strings after implementation bytes change.

## Mechanism Construction

The Population contains six tasks for each of four mechanisms.

### Context-conditioned action

The public contract exposes one irreversible operation-choice slot, a symmetric registered action
set, and a public selection rule. Replacing the target action must change the projected operation;
bypassing the decision removes required operation lineage.

### Semantic reconciliation

Each task combines two periods, with daily and monthly records for each period. The public target
is monthly. `normalize_metric_unit_period` emits a typed `normalized_operation_ref`, stores a
content-addressed normalized operation, and returns a selector. The downstream Calculator consumes
that operation reference and selector rather than a raw Evidence ID.

All compiler Witnesses demonstrate both registered events:

```text
normalization_reference_emitted
normalization_reference_consumed
```

### Failure recovery

The first exact-selector attempt deterministically produces a typed recoverable failure. A valid
path must inspect the retry contract, revise at least one public selector field, and recover the
required Evidence. Missing recovery and an identical retry are separate invalid mutations.

### State-dependent stopping

A valid path must perform the public completion verification and stop immediately after it. Early
stop and a redundant post-completion action are separately invalid.

Recovery and Stopping use separate task identities and separate causal contracts; the historical
combined label is not retained.

## Public Witness And Citation Semantics

The compiler executed 48 complete Public Witnesses and persisted 494 typed public-tool
Observations. Capability-only tasks have one compiler Witness. Each VTDO candidate has three:

```text
structured_direct
search_then_structured
search_then_open
```

Every Witness passes the full conjunction:

```text
public inputs
allowed tools
operation lineage
Evidence support
verification
answer projection
Citation completeness
target mechanism
no post-completion violation
```

Citation validity uses registered sufficient-set membership. It accepts a cited superset that
contains a registered sufficient set; it does not require equality with one Gold list. The current
tasks each register one sufficient set, but semantic-alternative search is incomplete and no task
claims uniqueness. Therefore `exact_equality_required=false` for all tasks.

## Mechanism Necessity

Each of the 24 primary Witnesses has two target-matched mutations, producing 48 content-addressed
counterfactual Replay records. For every row:

- the baseline Gate vector is fully valid;
- `mutation_target` equals the enclosing Mechanism Contract ID;
- the registered target-mechanism events are removed;
- `mechanism_complete=false`;
- at least one additional validity component fails where required by the mechanism;
- complete validity is false.

The resulting 24 Mechanism Necessity artifacts all pass. These are deterministic contract-level
counterfactual replays over compiler Witnesses. They are not model rollouts and do not establish
that an Agent naturally visits the baseline or mutated behavior.

## Role-specific Path Support

The 12 capability-only tasks carry no VTDO path catalog entries and have status `not_required`.
They are not rejected for lacking three states.

The 12 VTDO candidates each have three static paths with distinct:

- model-owned decision signatures;
- behavior signatures;
- quotient-state IDs.

All three paths share one Scaffold surface signature. This prevents Scaffold wording from creating
the apparent state distinction.

However, every path records:

```text
materialization_origin = compiler
model_generated = false
empirical_reachability = unmeasured
```

Thus v26.56 proves static public executability and model authority at the decision point. It does
not prove Flash reachability, positive state probability, conditioned acceptance, or affordable
realization yield.

## Immutable Outputs

Artifact root:

```text
artifacts/vtdo_experiment/finance_v26_56_executable_task_rematerialization_20260818/
```

| Artifact | Records | SHA-256 |
| --- | ---: | --- |
| Definition-pair capacity audit | 1 | `8275181e2286ade26e70fa7f70d639680f54acf35ae5ab31ee044b9ed31d15f6` |
| Mechanism counterfactual Replays | 48 | `e572df7e74a4ae0c218c13444875c7864f65bb4c975f74f35d252d57dfc72057` |
| Mechanism Necessity artifacts | 24 | `b4c2e3ad55eafb19bcb1de7585b041163b7166d133f9ba4559eda2be59bcf8ea` |
| Public Executable Witnesses | 48 | `b5d26441178fa12894421dba38d7a177e06a5bf4873e43074ccccc64b02318a9` |
| Public Witness Observations | 494 | `736c9110828d5a187fcb91483589c196030503811e633869a59c551fcf863f24` |
| Rematerialized task records | 24 | `2e9c0f75707de2b4935b5b693717d8ca656da7b7df87d68c8840d9971b1a7e7d` |
| Static model-authority path catalogs | 24 | `29572863bde96eb6f8b0ece0ad7d55b63890c81fb814ed71c00abd6ffbbf439e` |
| Task admissions | 24 | `d18362bab3101f5678662e6ef1e7415a2f86b03e5305abdf43bd8eb9b4757516` |
| Tool environment manifests | 24 | `15f389a4ea83fdc17cd44406300e1023d1e550a50af65dc9fa34c0bf2951824d` |
| Report | 1 | `9ae06bb76fa945ada4c56a9187ce88c35bd313015c877e6a4195e70239e2d541` |

An independent rebuild under `/tmp` reproduced all ten files byte for byte. The focused test suite
also performs two complete Snapshot builds and compares every output byte.

## Interpretation And Limits

Supported conclusions:

- the historical v26.55 blockers can be removed by fresh identity-safe rematerialization;
- every new task has at least one complete public executable solution;
- all public tools, projections, Evidence support, Citations, Verifier semantics, and mechanisms
  are bound before admission;
- all four target mechanisms have static target-matched necessity evidence;
- capability-only and VTDO-candidate roles are now separated without weakening either gate;
- twelve tasks have three static model-authority path candidates.

Unsupported conclusions:

- Flash or Pro can reach all registered paths;
- the three static paths have positive natural probability;
- the paths remain distinct after empirical Quotient mapping;
- any state has sufficient realization yield for training;
- the capability task distribution has stable information geometry;
- VTDO, GP-C, Contribution, or Student training is effective.

The Reconciliation construction is also narrow: the current real-data capacity comes from one
federal-funds-rate daily/monthly semantic family. This is adequate for a mechanism Pilot but not
evidence of broad financial Reconciliation coverage.

## Next Permitted Experiment

The next experiment must keep the two roles separate:

1. run capability Development only on the 12 registered capability-measurement tasks;
2. run empirical state Reachability only on the 12 registered VTDO candidates;
3. preserve complete invalid model outcomes in capability denominators;
4. require independently valid model-generated trajectories before state mapping;
5. distinguish unconditional natural hits from state-conditioned acceptance;
6. keep compiler Witnesses out of every empirical state count;
7. freeze no VTDO support unless at least three states satisfy the registered reachability and
   realization-yield contract.

This next stage may call the authorized Explorer API. It still cannot open Fresh Confirmation,
training, Exact Target, GP-C, or Contribution.
