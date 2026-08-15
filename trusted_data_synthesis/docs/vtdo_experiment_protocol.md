# VTDO Experiment Protocol v6

## 1. Purpose

This document defines the only active paper experiment for Valid Trajectory Distribution
Optimization (VTDO). It replaces the legacy v0.8 training-utility and v0.9 validation protocols.
Historical implementations remain only as explicit diagnostic modules; their production entry
points are disabled. Tracked source changes remain auditable through Git history, but no legacy
artifact is an accepted protocol input.

The experimental claim chain is:

```text
State validity and quotient identity
-> trajectory-state distribution optimization
-> downstream training utility
```

Each stage must be established with its own observable artifact. A result at an earlier stage
cannot be reported as evidence for a later stage.

## 2. Frozen Identity

The active identities are:

```text
experiment schema:       vtdo_experiment.v6
experiment config:       config/vtdo_experiment_finance.json
student config:          config/vtdo_qwen2_5_7b_500k.json
runner:                  trusted-synthesis run-vtdo-experiment
feedback compiler:       trusted-synthesis generate-vtdo-real-feedback
trainer:                 trusted-synthesis train-vtdo-arm
benchmark predictor:     trusted-synthesis predict-vtdo-benchmarks
default output:          artifacts/vtdo_experiment/finance_v6
```

Every run freezes the normalized experiment configuration, all external input hashes, execution
source-tree hash, Git commit, dirty-worktree status, state artifacts, round artifacts, arm data,
and final manifest. The output directory must be absent or empty.

## 3. Experiment 1: Controlled VTDO Validation

The controlled state space contains `K=200` states and uses five frozen seeds. Accepted-state
contribution is centered so that:

```text
E_{z ~ pi_0}[C(z)] = 0
```

Novelty follows the frozen density-ratio definition:

```text
N_t(z) = [log(r(z) / pi_t(z))]+
```

The initial fixed-potential target is retained only as a diagnostic:

```text
p*(z) proportional to r(z) Phi(z)^(1 / kappa)
```

Main methods:

```text
Random
Contribution Only
Novelty Only
CCGR
VTDO
```

Ablations are reported separately under explicit semantics:

```text
No Global Coverage Anchor
No Coverage Prior
No Iteration
No Quotient with Exact Contribution
No Quotient with Noisy Contribution
```

The production moving-potential methods are not ranked by distance to the initial target. Their
main diagnostics are expected log potential, coverage alignment, entropy, active support, and the
contribution-novelty phase trajectory. Fixed-point KL and projective contraction belong only to
the stationary-potential operator-control track. No contribution-oracle KL metric is used.

This experiment validates the update implementation and controlled estimator behavior. It does
not establish empirical causal contribution or downstream training gain.

## 4. Experiment 2: Real Financial Trajectory States

The primary real-data contract requires:

```text
100 unique financial tasks
3-5 independently accepted states per task
300-500 accepted trajectories in total
one frozen Oracle program per task
full JointCompilationArtifact and Omega_x persisted for every accepted task
Omega component manifest replayed before state discovery
```

Accepted states must differ through replayable decisions such as retrieval breadth, verification
frontier, selected evidence lineage, or output lineage. Surface paraphrases and deterministic
format variants are quotient probes only; they cannot increase positive training support.

Before provider invocation, each domain compiles its state semantics into the same Core variation
axes: Evidence Acquisition, Evidence Support, Execution Realization, Verification Policy, and
Lineage Policy. The resulting `TrajectoryStateSpaceCompilation` must embed the original immutable
`JointCompilationArtifact` and freeze the variation-provider manifest. Legal and Science
same-`Omega_x` contract tests must each realize at least two valid states. Domain strategy names
remain in plugins or experiment fixtures and cannot become Core enums.

For every attempted strategy, the artifact records:

```text
strategy attempt count
independent verifier pass count
rejected attempt count and reason
duplicate quotient-state count
raw-sequence and canonical-state identity
retrieval, operation, and evidence-lineage hashes
Omega component manifest and canonicalizer version
verified State discovery witnesses
```

The report must expose the complete funnel rather than computing a pass rate only over retained
states. Every accepted state is replayed by both `CandidateWorkflowVerifier` and the compiled
`QualityContractRuntime`; injected wrong-answer mutations must be rejected.

The configured task count is an **accepted-task quota**, not merely a candidate-attempt limit.
The provider deterministically overprovisions candidate tasks, the materializer continues until
the quota is filled or the candidate pool is exhausted, and the report records both successful
and rejected tasks. Exhaustion before the accepted quota is reached fails closed. This prevents a
nominal 100-task experiment from silently becoming a smaller experiment after state deduplication.

The current Finance implementation is explicitly a
`FinanceDeterministicStateFixtureProvider`. It validates state-space compilation and verifier
behavior; it is not an Explorer and must never be reported as observed model behavior. A real
Explorer or Materializer receives only `PublicStateGenerationRequest`, never full `Omega_x`, an
exact state object, gold Evidence IDs, hidden programs, Proof Graph, or reference answer. Every
request must pass the leakage audit before a provider call.

Final data materialization is a separate, fresh state-conditioned generation phase. It rejects
discovery reuse by trajectory ID, content hash, and normalized decision-trace hash; replays
`V(tau, Omega_x)`; and reproduces the requested quotient state. Reports must include requested,
attempted, off-target, and released counts per state; quota fill and per-state acceptance; source,
allocated-target, and released distributions; total variation and Jensen-Shannon divergence; public
request audits; and decision-trace uniqueness. A budget large enough for the positive support uses a
one-item support floor. A smaller budget declares support truncation. Failed quotas are never
reassigned to easier states.

### Active real-Agent entry path

The deterministic Finance state fixture remains a contract test only. The active empirical entry
path recompiles real Archive tasks as `semi_open + plan_hidden`, preserving Oracle semantics while
hiding the retrieval answer, Gold Evidence IDs, and task program. Development partition A and
sealed authorization partition B must each fill their accepted-task quota and expose 3--5
host-requestable quotient states per task. The authorization build consumes the complete
development Public Corpus as a frozen exclusion manifest. Task IDs, source task IDs, Gold and
distractor Evidence versions, and Source Record IDs must all have zero cross-partition overlap.

The unconditioned Explorer estimates `pi_0` with at least four frozen replicas per task. A passed
initial-distribution report requires every replica to be independently valid and mapped to the
registered state catalog. Coverage-prior smoothing may preserve positive support, but it cannot
turn a failed, invalid, or off-catalog observation into a passed empirical run. Checkpoints resume
only valid catalog hits; all other jobs are retried while their historical telemetry remains in the
cost audit.

Fresh state-conditioned materialization uses a separately derived provider identity and at least
three accepted independent trajectory draws per positive-probability state. Trajectory IDs and
content hashes must be unique, while identical decision structures remain valid empirical outcomes
and are reported through a separate decision-trace diversity diagnostic. The materializer consumes
the exact initial-distribution report and distribution hash, writes one atomic task checkpoint, and
replays the complete validity and state-assignment contracts before release. Explorer and
materializer identities are derived from the frozen model configuration and solver version rather
than accepted as caller-controlled labels.

Objective Support freezes a separate target boundary before Gradient planning. The active v6
support contract contains a `gradient_target_contract`, an
`objective_support_exclusion_contract`, and a `future_population_exclusion_contract`; these task
sets have distinct canonical identities and cannot be substituted for one another. The target and
Objective Support exclusions must be disjoint. Gradient Projection accepts only an Artifact path
and SHA-256 explicitly frozen by the target contract.

API credentials are process-environment inputs only. They must not appear in command arguments,
JSON configuration, checkpoints, telemetry, or reports. Model discovery may validate the requested
model before a run, but one experiment identity cannot silently mix fallback models. A replacement
model therefore requires a new frozen model configuration and a fresh run identity.

The current real-Agent preflight, population hashes, disjointness report, cost ladder, and exact
smoke command are recorded in `docs/finance_v12_real_agent_preflight_report.md`.

## 5. Experiment 3: Empirical Contribution Validation

The only active production-candidate approximation family is Scheme 3, Gradient Projection. Local
beneficiary Probes and single-state finite interventions are historical diagnostics; they cannot
authorize a real VTDO Contribution update. The theoretical estimand is unchanged.

The active production protocol freezes the exact typed `ConditionalTrajectoryDistribution` for every
task-round. Each task has 3--5 positive-probability quotient states, each state has 3--5 fresh and
independently verified trajectory realizations, and the objective support contains 16 estimation,
16 validation, and 16 sealed authorization records. The three partitions and all state
realizations are mutually disjoint. A support-scaling pretest at 4/8/16/32 records must select at
least 16 records, and objective records are balanced across at least three available trajectory
strategies. For state training-loss gradient `g_z`, objective-loss gradient `g_v`, and optimizer
descent map `U`, the diagnostic variants are:

```text
GP-A = cosine(g_z,g_v) - E_pi[cosine(g_z,g_v)]
GP-B = <g_v, g_z - E_pi[g_z]>
GP-C = <g_v, U(g_z) - E_pi[U(g_z)]>
```

GP-A is the direction-only baseline. GP-B retains gradient magnitude and centers in gradient
space. GP-C is the only production-candidate estimator. Its current engineering claim is local:
one state-homogeneous, cold-start AdamW step with zero weight decay, no inherited optimizer state,
no mixed-state batch, fixed clipping, and a frozen LoRA parameter space. It does not approximate
the full Student optimizer trajectory. With plain SGD and a positive scalar learning rate, GP-C
and GP-B have identical rankings and are not independent estimators.

The production runner requires at least 30 tasks, complete 3--5-state support, and 3--5 realization
gradients per state. Every artifact binds the task, round, state, exact nonuniform distribution,
beneficiary checkpoint, tokenizer, supervised-token mask, source record, objective split, dtype,
and content hash. Each target is split into an aligned common-token region and a
state-differential-token region. Full, common, and differential gradients use the same RNG
realization; their token-count-weighted recomposition must recover the full gradient. Every
realization must retain non-empty common and differential regions. The hard lexical-coverage gate
applies to pooled differential-token mass per task because an individual state may legitimately
lie close to the shared task skeleton; record- and state-level fractions remain immutable
diagnostics. Differential-gradient fraction, sign agreement, gradient variance, effective sample
size, split-half cosine, AdamW update cosine, and sign saturation remain fail-closed stability
gates.

Proxy stability is necessary but not sufficient. Independent validation constructs a complete
zero-sum contrast basis inside each task, partitions the coordinates into salted blocks of 5--10,
and evaluates multiple frozen Hadamard designs. Every design includes a null replay and uses central
differences at radii `h`, `h/2`, and `h/4`, followed by Richardson extrapolation:

```text
D_h = (J(theta - eta*(g_base + h*H G))
       - J(theta - eta*(g_base - h*H G))) / (2*h)
D_R = Richardson(D_h, D_(h/2), D_(h/4))
```

The intervention binds the complete conditional distribution, so task marginal `mu(x)`, state
support, and total update mass remain fixed. The learning-rate ladder is preregistered and may be
selected only by parameter-step fidelity. The final-test outcome cannot select the scale. A target
is interpretable only when probabilities remain positive, numeric replays are deterministic, block
reconstruction and radius-stability gates pass, the signal exceeds null replay, and the actual
float32 parameter update matches the intended update. The independent objective gradient is
evaluated after the frozen global local-update vector. Leave-one-realization-out Jackknife
pseudovalues carry state uncertainty through proxy construction and Contribution materialization.

Estimation, validation, and the independently opened authorization partition each receive rank and
next-distribution gates. The latter include total variation, Jensen--Shannon divergence,
update-direction agreement, absolute target regret, and normalized target regret. Normalized
regret is computed only when attainable target gain exceeds its frozen floor; at least 80% of tasks
must be normalizable. Missing support, token-region dominance, realization reuse, Jackknife drift,
leakage, parameter-step non-identifiability, source-scale mismatch, or any failed gate blocks
authorization.

The current executable gradient contract is `finance_contribution_gradient_projection.v15`, and
the current Objective Support contract is `finance_contribution_evaluation_support.v6`.
Vocabulary logits are materialized only at causal predecessor positions of supervised labels; this
is exactly equivalent to mean causal NLL with ignored prompt labels. Objective gradients keep all
stochastic children in eval mode while enabling only gradient-checkpoint wrappers. Token-region
losses share one decoder activation graph. Multi-GPU placement is a strict whitelist: all
nonselected devices receive zero placement capacity, and the resolved Hugging Face device map is
hashed into the objective-gradient manifest. A run that touches an undeclared device is invalid
even when its numerical outputs complete.

The independently frozen v3 numeric contract governed the v14 production candidate. It is now
historical evidence rather than an active production authorization because v14 failed that
contract. Any successor must be calibrated and validated on disjoint task populations before it
can be frozen. Loss identity, gradient direction and relative error, GP score drift, margin-aware
ordering, and induced-distribution TV/JS remain joint fail-closed gates; no threshold or execution
profile may be changed after observing its validation population.

The 2026-08-04 three-task v10 smoke completed the real-Agent-to-gradient path but did not satisfy
production gates. Weighted common/differential losses recovered full loss to `5.27e-8`, while
separate BF16 VJPs retained a maximum 1.793% gradient discrepancy and each state had only one
realization. The frozen `1e-4` gradient-recomposition threshold was not relaxed. The run therefore
remains diagnostic and cannot open GP-C or finite-intervention authorization. Full evidence is in
`docs/finance_v13_real_agent_gradient_smoke_report.md`.

The first completed 30-task run found estimation-versus-validation Spearman `0.717`, but its
independent cached-SGD target failed both rank gates. The selected numerically identifiable
learning rate was `5e-4`, not the source `5e-5`.

The subsequent GP-A/B/C comparison retained the 30-task support and froze a one-step cold-start
AdamW target before final evaluation. Estimation/validation Spearman against that matching target
was `0.417/0.450` for GP-A, `0.483/0.467` for GP-B, and `0.517/0.517` for GP-C. All passed the
frozen rank gate. Paired intervals did not establish GP-C as better than GP-B, and none of the
three transferred to the old SGD target. Because the historical continuation optimizer state is
unavailable, this is mechanism evidence under a diagnostic optimizer contract, not production
authorization. Real Finance VTDO rounds still use `Contribution=0`. Immutable evidence is in
`docs/finance_gradient_projection_abc_validation_report.md`.

The independent authorization run then froze GP-C as Primary, GP-B as Secondary, a strictly fresh
30-task population, disjoint Estimation/Validation/Authorization objectives, the one-step cold-start
AdamW contract, and state-homogeneous `E_pi[U(g_z)]` batch semantics. Calibration was fit on
Estimation only. In addition to rank evidence, the gate compared proxy- and finite-target-induced
next distributions using TV, Jensen-Shannon divergence, probability-update direction, and target
variational regret. GP-C failed the internal rank and distribution gates: Estimation/Validation
Spearman was `0.150/0.300`, direction agreement was `0.544/0.589`, and mean normalized regret was
`3.867/3.010`. The untouched Authorization objective was not opened and no production credential
was issued. A post-global-update objective-gradient diagnostic did not recover GP-C. This negative
result supersedes any interpretation that the earlier diagnostic population was sufficient for
production authorization; it does not erase that run's bounded mechanism evidence. Full evidence
is in `docs/finance_gradient_projection_independent_authorization_report.md`.

That report is immutable historical evidence for the retired protocol. Its artifacts do not
satisfy `vtdo.v12` / `aevtdr.v7` and cannot be promoted or replayed as a current authorization.
A subsequent v12 integration smoke rebuilt the 16+16+16 Objective Support, replayed the calibrated
numeric contract, and recomputed 32 Objective gradients plus 11 state gradients on A100 GPUs. The
numeric gate passed, but every state still had one realization, so mean ESS remained `1.0` and the
realization-stability gate failed. Post-global GP-C and independent intervention remained closed;
`production_authorized=false`. Evidence is in
`docs/finance_v13_gradient_projection_v12_target_boundary_report.md`.

The 2026-08-04 v14 production candidate then completed the real-Agent entry path for 30 tasks,
100 states, and 300 fresh realizations. The sampling-stability contract passed, but the immutable
finite-precision contract failed on seven realization-level tail cases and three strict task-rank
comparisons. All 1,065 referenced gradient files passed a separate full content-hash replay, so
this is a numeric-contract failure rather than artifact corruption. Post-global GP-C, independent
distribution intervention, Jackknife proxy materialization, and typed authorization remain closed;
`production_authorized=false`. The current 300 realizations are a held-out production-validation
population and may not be reused to tune a replacement numeric contract. Full evidence is in
`docs/finance_v14_real_agent_gradient_projection_report.md`.

The 2026-08-05 v16 recalibration implemented that recovery protocol on three disjoint, balanced
six-task partitions: development, validation, and an unopened sealed candidate. It also used fresh
4+4+4 Objective Support records and a shared-forward numeric algorithm with one causal CE loss
vector and three VJPs. Two BF16 profiles passed development. The preregistered selector froze the
TF32 control profile and its thresholds before validation. On independent validation, all 25
margin-resolvable state pairs and all six task winners agreed, and TV/JS stayed within contract,
but raw fidelity did not generalize: maximum relative error was `0.0300558` against `0.027`, minimum
cosine was `0.9995483` against `0.99967`, and maximum GP-score delta was `0.0028211` against
`0.0023`. The aggregate status is therefore `failed`, no `frozen_numeric_contract.json` exists,
and the sealed candidate, GP-C, and intervention remain unopened. The validation profile cannot be
replaced post hoc by the other development profile. Full evidence is in
`docs/finance_v16_numeric_contract_validation_report.md`.

The 2026-08-05 v17 root-cause experiment then constructed a fresh three-partition population and
kept the inherited sealed candidate unopened. It evaluated eight preregistered execution profiles
on one lowest-index realization per task-state: 20 of 60 development realizations per profile.
Sparse-projection FP32, FP64 loss accumulation, TF32-off, checkpoint changes, separate forwards,
and functional VJP extraction all failed the unchanged joint numeric gate. Only
`fp32_activation_strict` passed. Relative-error reduction against the otherwise matched TF32-off
profile was positive for 20/20 jobs, with a task-cluster bootstrap 95% interval of
`[0.011827, 0.018466]`. The selector froze that profile and a `0.0011` pairwise uncertainty envelope
before validation.

On the disjoint validation diagnostic subset, the selected profile completed 20/20 checkpoints.
Maximum relative error was `0.006024`, minimum cosine was `0.9999819`, maximum GP-score delta was
`0.0006838`, maximum TV was `0.00005472`, and all frozen gates passed. All 25 resolvable pairs, six
task winners, and six strict task permutations agreed. The resulting
`finance_gradient_numeric_contract.v17` authorizes exactly one inherited
`independent_sealed_candidate` numeric run. It does not authorize Contribution, GP-C, a VTDO
update, Student training, or a downstream claim, and `production_authorized` remains false. Full
evidence is in `docs/finance_v17_numeric_root_cause_report.md`.

On 2026-08-06 the inherited sealed numeric candidate was opened exactly once under that frozen
contract. Its first process attempt failed before any state metric was computed because the
checkpoint loader used the outer source-manifest schema instead of the nested source descriptor.
The immutable failure has zero checkpoints and no numeric summary. A separately hashed retry plan
allowed only that lookup repair and froze the task set, trajectories, state realizations,
authorization objective gradient, profile, thresholds, uncertainty envelope, and gradient seed.

The retry computed 20/20 fresh diagnostic checkpoints. Maximum relative error was `0.0063303`,
minimum cosine was `0.9999800`, maximum GP-score delta was `0.0008104`, maximum TV was
`0.00005026`, and all frozen raw gates passed. All 24 resolvable pairs, six task winners, and six
strict task permutations agreed. The sealed numeric stage is therefore complete, while
`production_authorized=false` and `contribution_authorized=false`. The only authorized transition
is preregistration of a separate Contribution authorization experiment with independent finite
intervention targets. Full evidence is in
`docs/finance_v18_sealed_numeric_authorization_report.md`.

The 2026-08-06 v19 sealed causal pilot exercised that transition on six frozen tasks, 20 states,
and 60 fresh state realizations. Estimation and Validation each used four mutually disjoint
Objective Support records; the Authorization objective remained forbidden. The strict FP32
activation path passed again: maximum loss-identity error was `5.31e-8`, maximum token-gradient
recomposition relative error was `0.0068513`, minimum recomposition cosine was `0.9999770`,
maximum GP-score drift was `0.0007361`, and the induced update remained within TV
`3.8020e-5` and JS `2.2476e-9`.

The independent finite target nevertheless failed its preregistered identifiability gate before
GP-C execution. Estimation/Validation reconstruction relative error was `0.5065/0.3774` against a
maximum of `0.1`; p95 radius instability was `1.5420/1.4557` against a maximum of `0.25`. Each
partition completed 204 observations over the frozen `0.1/0.05/0.025` radius ladder, and the
signal exceeded deterministic null replay, so this is not an execution failure or a null-signal
result. A post-failure, non-authorizing diagnostic on eight deterministically selected directions
per partition used radii `0.025/0.0125/0.00625`; median instability worsened from `0.6258` to
`0.6680` on Estimation and from `0.5014` to `0.9350` on Validation. Smaller radii therefore did not
restore local linearity on this diagnostic subset.

Because the target gate failed, GP-C rank, distribution, and regret comparisons were not run;
Authorization was not opened; `Contribution=0`; and no VTDO update, Student training, or downstream
claim is permitted. The result establishes that the current finite-intervention target is not
stably identifiable at the tested radii. It does not establish that Gradient Projection itself is
invalid. Full evidence and the next-stage estimator redesign requirements are recorded in
`docs/finance_v19_sealed_causal_pilot_report.md`.

The 2026-08-06 v20 finite-target identifiability study then tested the measurement redesign without
running GP-C. It used six new tasks, 20 states, 60 three-realization state samples, and disjoint
16-record Estimation and Validation objectives divided into four micro-splits each. A separate
16-record Authorization identity was frozen but its Objective remained forbidden. Perturbations
were normalized to actual parameter-step ratios `0.01/0.005/0.0025`; the design contained seven
direct anchors, block sizes 2/4/7, and a null replay; local response used an odd-cubic slope model.

The formal run completed 186 observations per role. Numeric, parameter-scale, Objective-replay,
and null gates passed. Target identifiability did not: direct-anchor identifiable rate was zero in
both roles; maximum p95 nonlinearity was `16.0095/63.3579`; maximum block reconstruction error was
`1.8606/1.8830`; and block direction agreement was `0.6522/0.5652`. All direct-anchor confidence
intervals crossed zero, and only four of seven signs agreed across roles. Block error was not
monotonic with block size, so the failure cannot be assigned only to large combined directions.

The combined result is fail-closed. GP-C was not evaluated, Authorization observation count is
zero, and real Finance VTDO retains `Contribution=0`. Any successor must preregister a fresh target
measurement and may not tune v20 thresholds or promote its records into Authorization. Full
evidence is in `docs/finance_v20_target_identifiability_report.md`.

The 2026-08-07 v21 successor changes the scientific question from finite-target reconstruction to
Direct Coordinate observability. Before any v21 outcome, it froze a new 420-task population, six
fresh target tasks with 20 states, 60 three-realization state samples, and disjoint
128/128/128-record Estimation, Validation, and sealed Authorization partitions. Estimation and
Validation are each partitioned into 32 immutable four-record micro-splits. Authorization content
access remains forbidden.

The v21 design contains seven preregistered Direct Coordinates and one Null replay; no block or
Hadamard reconstruction is present. Actual parameter-step ratios are `0.01` and `0.005`, with
`0.005` primary. The engineering minimum practical effect is `0.005` in raw Objective-slope units
and is not a downstream or business-effect threshold. A coordinate is resolved only as a
meaningful nonzero effect or a practically equivalent effect under the frozen confidence-interval
policy. Both radii must agree, both Objective roles must resolve all seven coordinates, and
cross-role resolutions must agree exactly.

All state and global update directions are computed Objective-blind. Runtime role files physically
contain only the permitted Objective role. Observation replay binds the plan, direction and scale
manifests, design role, coordinate IDs, numeric seed, baseline micro-splits, and exact registered
radius keys. A successful target-observability result permits only preregistration of a new
independent GP-C comparison. It does not open Authorization, evaluate GP-C, authorize
Contribution, or update VTDO. A failure retains `Contribution=0`. The design and eventual result
are recorded in `docs/finance_v21_target_observability_report.md`.

The v21 run was cancelled after 9 of 32 planned observations in each Objective role. No aggregate
target result exists and its partial observations are ineligible for successor tuning or reuse. The
2026-08-07 v22 successor therefore returns to a Development-only variance and power stage. It
freezes 30 balanced target tasks with 100 states, 10 planned unconditioned Explorer replicas per
task, five planned realizations per state, and 64 disjoint Development Objective records split into
eight micro-splits. Validation and Authorization do not exist in the v22 artifact. The MPE is the
minimum centered Contribution contrast that changes a selected next-round state probability by
0.02 under the frozen anchored update and task-conditional Reachability. Final target sample size
remains unfrozen until nested variance is observed.

The v22 Development measurement is now complete. The exact one-step AdamW chain derivative produced
4,000 observations from 30 tasks, 100 states, five realizations per state, and eight Objective
micro-splits. All 100 state intervals were contained in their update-derived practical-equivalence
regions; 83 were also statistically nonzero, demonstrating why significance and equivalence must
be reported as separate axes. Objective variation accounted for `99.9443%` of nested measurement
variance. The original homogeneous one-MPE mean-power diagnostic does not freeze future
task-specific proxy-validation support. The next recommended but unopened design contains 60 fresh
tasks and 128 disjoint Objective records. A separate proxy-target agreement power contract must be
frozen before GP-C is exposed. See `docs/finance_v22_development_power_plan.md` and
`docs/finance_v22_development_exact_target_report.md`.

### 5.3 Capability-Sensitive Agent Runtime Gate

The 60-task exact-target Validation is no longer the immediate post-v22 transition. First qualify
a Development-only paired Explorer factorial on shared Finance tasks. `deepseek-v4-pro` is the
strong baseline and `deepseek-v4-flash` is a separately identified medium-capability candidate;
neither may fall back to the other. Each model runs the same three Runtime arms:

```text
Direct/Bare
Scripted Tool: Host fixes sequence, model supplies public arguments
Autonomous Agent: model chooses tool, query, verification, recovery, and stop
```

Scripted and Autonomous must share the same frozen tool manifest, Evidence snapshot, token and
tool-call budgets, timeout, and verifier. Host execution emits content-addressed Observations. The
model cannot access Gold Evidence IDs, Oracle programs, reference answers, Proof Graphs, or target
states. Each arm receives 8-12 unconditional runs; 12-18 balanced tasks receive 5-8 conditioned
attempts per state and a small exact-target measurement. The independent verifier, quotient-state
mapper, and exact-target design are content-hashed in the Pilot contract before API outcomes.

A six-task calibration gate precedes the 30-task, ten-replicate factorial Discovery. Calibration
requires exact model identity, 100% completion in every model-runtime cell, at least 95% JSON
contract success per cell, at least one independently valid trajectory per cell, and at least 80%
interactive-tool success. Calibration outcomes cannot change thresholds.

All later state-space, validity, provenance, target-sensitivity, and non-length-only gates must
pass. A
failure returns to Agent environment design. A pass permits only Beneficiary frontier screening and
a new Agent population. Fresh Development must re-estimate variance before any Validation task
count is frozen. Validation, Authorization, GP-C, and production Contribution remain inaccessible
throughout this Pilot. See `docs/finance_v23_capability_sensitive_agent_plan.md`.

The final v9 qualification completed 36/36 requested records but failed closed. Its minimum cell
completion was `0.8333` against `1.0`, and minimum JSON-contract success was `0.9048` against
`0.95`. Exact models, independent validity smoke, and interactive tool execution passed. The
formal next stage is `protocol_repair_only`; Discovery, state conditioning, exact target, GP-C,
Validation, and Authorization were not executed. This is an Explorer qualification failure, not a
Contribution or GP-C result. See `docs/finance_v23_explorer_runtime_factorial_report.md`.

v24 supersedes the six-task qualification with two independent Development gates. Runtime Stage A
uses 18 Easy-Control tasks, three per Finance family, and requires exact models, 100% completion and
final emission, no budget exhaustion, complete replay and authority integrity, at least 95% tool
success, and bounded JSON resolution of 100%. Raw provider JSON is retained as a separate diagnostic
with an 85% floor; repaired logical calls are never counted twice. Stage B requires a separately
frozen semantic Frontier: mean Frontier gain must be at least 1.0 and at least four families must
gain 0.5. Runtime success cannot override semantic failure.

The fresh v24.4 Runtime qualification passed all gates over 216/216 records with zero Host-forced
verification. Its semantic audit failed: Frontier minus Easy was `0.0117`, with zero passing
families. The only permitted transition is `frontier_task_construction_only`. An attempted Stage B
entry revalidated the Stage A report, checkpoint, and canonical rollout, then failed before client
construction. Completed stages may be replayed without credentials: the
runner verifies checkpoint, canonical rollout, run, denominator, and semantic-audit identities
before returning the frozen report, and performs no model discovery. No capability-calibration,
Exact Target, GP-C, Validation, or Authorization work was performed. See
`docs/finance_v24_capability_ladder_experiment.md`.

v25 supersedes the label-balanced semantic ladder with a capability-identifiability construction
gate. A Finance task population must cover Retrieval, Planning, Calculation, Reconciliation,
Verification, Recovery, and Stopping through executable Program or typed workflow requirements.
Every Easy--Frontier--Hard structural dimension must be strictly monotonic; every Program must
execute and independently replay; public Evidence must be cross-sample disjoint; and all seven
families must meet their Frontier-gain requirement.

The capability information audit derives demand vectors only from frozen structure. It normalizes
and centers them, evaluates the six-dimensional family-contrast subspace, retains the complete
seven-eigenvalue spectrum as a diagnostic, and verifies that each family mean is primarily aligned
with its preregistered axis. Balanced labels with identical vectors, relabeled vectors, or a flat
tier dimension fail closed. Structural readiness does not imply empirical frontier placement.

The real 70-task v25 population passes this gate with contrast effective rank `5.141`, contrast
condition number `4.726`, and 7/7 family-axis matches. A separate destructive Capability Necessity
Audit withholds required Evidence or removes the registered Program, reconciliation, verification,
recovery, and stopping requirement. All 35 Frontier probes must be rejected by Program execution
or the typed task contract. This is contract necessity, not a model causal-effect estimate.

Runtime projection is explicit. Direct Fixed Retrieval exposes Calculation, Reconciliation, and
Verification. Scripted Tool exposes Retrieval, Calculation, Reconciliation, Verification, and
argument-level Recovery while the Host fixes the tool order. Autonomous Agent exposes all seven
axes. Host-controlled demand may not contribute to empirical model information.

The v25.6 contract permits only a seven-task, 126-rollout Runtime Qualification. Semantic accuracy
is descriptive at this stage: only bounded JSON, typed terminal outcomes, bounded tool resolution,
Observation/failure replay, authority integrity, and resource budgets gate the transition. A
passing Qualification permits the balanced 28-task, 1,680-rollout Pro--Flash comparison.

Calibration authorization must independently replay the frozen job identity, checkpoint,
canonical rollout records, typed outcomes, Qualification report, and run manifest. Their schema
versions, complete denominators, exact-model telemetry, content hashes, and outcome-set identity
must agree exactly. A missing or self-consistent summary artifact is insufficient and fails closed.

Calibration is paired at `task_id`. Its primary estimator is a task-cluster paired nested Bootstrap
that resamples tasks and the ten within-task realizations; unpaired aggregate percentages are
forbidden. For each Model x Runtime cell, the raw empirical information matrix is exactly:

```text
I_hat(M,R) = mean_x p_hat(x) (1-p_hat(x)) a(x,R) a(x,R)^T
```

The axis-specific diagnostic separately centers demand and removes the preregistered general-
difficulty factor. Rank, effective rank, condition number, boundary mass, general-factor fraction,
and informative-axis count all fail closed. Axis information and Autonomous Family separation use
95% interval lower bounds, not point estimates.

Recovery is a conditional behavioral diagnostic: a success requires an observed failure followed
by a successful corrected action. Query Reformulation and Tool-sequence Diversity are recorded
separately, so answer correctness cannot be reused as evidence of Recovery skill.

Only a passing six-cell empirical audit may create the independent 420-rollout Qwen Beneficiary
screen. Beneficiary--Flash--Pro ordering is uncertainty-aware, and only ordered task IDs with
Beneficiary boundary mass may enter state discovery. At least seven selected tasks are required.
Neither empirical readiness nor Beneficiary readiness directly authorizes Exact Target or GP-C.
The v24 runner may not be reused through a lossy adapter. Exact Target, GP-C, Validation,
Authorization Objective access, VTDO updates, and production Contribution remain forbidden. See
`docs/finance_v25_capability_sensitive_frontier_report.md` and
`docs/finance_v25_capability_boundary_revision.md`.

## 6. Experiment 4: Refinement Dynamics

### Fixed-potential control

For fixed `Phi`, the update has a unique fixed point and a projective contraction governed by
`rho`. The experiment runs the controlled update for ten rounds and verifies the numerical
contraction within the configured tolerance. Its experimental role is **update operator
verification**: it verifies the analytic implementation under a stationary potential, but it is
not evidence that the model-coupled VTDO loop converges to a static optimum.

### Controlled moving-potential tracking

For each round, the implementation independently evaluates the proximal objective

```text
F_t(pi) = E_pi[log Phi_t]
          - lambda KL(pi || pi_t)
          - kappa KL(pi || r)
```

and verifies both `F_t(pi_(t+1)) >= F_t(pi_t)` and equality with the exact proximal optimizer:

```text
pi_prox_t*(z) proportional to
    pi_t(z)^(lambda/(lambda+kappa))
    r(z)^(kappa/(lambda+kappa))
    Phi_t(z)^(1/(lambda+kappa))
```

Tracking is measured against the instantaneous anchored optimum with the historical proximal term
removed:

```text
G_t(pi) = E_pi[log Phi_t] - kappa KL(pi || r)
pi_anchor_t*(z) proportional to r(z) Phi_t(z)^(1/kappa)
TrackingError_t = KL(pi_(t+1) || pi_anchor_t*)
```

The five-round benchmark compares no feedback, one-shot static optimization, and full VTDO under
three explicitly separated tracks:

```text
Track A  exogenous_shared              primary, method-neutral potential sequence
Track B  vtdo_induced_shared           supplementary, shared sequence induced by VTDO exposure
Track C  method_specific_closed_loop   supplementary, each method induces its own potential
```

Track A is the headline comparison because every method sees the same exogenous drift and no
method exposure enters `Phi_t`. Tracks B and C analyze endogenous feedback and cannot replace the
method-neutral result. Every track reports tracking error, cumulative dynamic regret, exact
proximal-objective replay, and confidence intervals. When regret advantage is required, the lower
confidence bound, not merely the sample mean, must be nonnegative.

### Real feedback-loop stabilization

Production VTDO recomputes contribution and novelty after model feedback, so the optimum moves.
The primary analysis horizon is five rounds, with checkpoints at rounds 1, 3, and 5. The practical
stabilization score uses the current round potential on both sides:

```text
S_t = KL(pi_(t+1) || pi_t)
      + alpha * |E_pi_(t+1)[log Phi_t] - E_pi_t[log Phi_t]|
      + zeta * D_Phi(t)
```

`D_Phi(t)` is a projective potential-drift diagnostic over pairwise log-potential ratios. The
first transition cannot satisfy a consecutive-round stop criterion because no preceding potential
exists for drift comparison.

Practical stabilization requires `S_t < epsilon` for two consecutive transitions. The report also
tracks utility, entropy, active coverage, state entries/exits, tracking error, dynamic regret, and
per-round distribution identity. It may state that updates stabilize, track a moving optimum, or
exhibit diminishing returns; it must not claim mathematical convergence of the moving-potential
process.

Real financial refinement is accepted only from immutable, lineage-linked `VTDORoundArtifact`
files. Every round independently replays the variational objective and exact proximal optimizer.
Missing rounds are reported as blocked and are not replaced by the controlled run.

### Recorded real-feedback production

`generate-vtdo-real-feedback` consumes a frozen Finance state pool, recorded Explorer trajectories,
and atomic beneficiary intervention records. It independently replays every trajectory through the
Finance verifier, reconstructs exploration distributions and multi-seed Contribution probes,
builds `RealRoundAssemblyInput`, assembles the Round artifacts, and replays the serialized inputs a
second time. Checkpoint, generation, evaluation, budget, seed-set, and source-file hashes are part
of the report identity. Missing model outputs are never synthesized by this compiler.

### Beneficiary model-state shift

The primary causal refinement experiment freezes the beneficiary checkpoint so that only
`pi(z|x)` changes. A separate paired `M0 -> M1` experiment compares Contribution observations on
exactly the same task-state-seed support and frozen evaluation/probe contract. It reports task-clustered absolute
Contribution shift with a paired confidence bound, task-wise rank correlation, and direction-change
rate. This supports the
limited claim that `C_t(x,z)` can depend on model state; it does not substitute for the fixed-
beneficiary primary comparison.

## 7. Experiment 5: Equal-Supervised-Token Downstream Training

The frozen training matrix is:

| Arm | Definition |
|---|---|
| `B1_raw` | Unfiltered generated trajectories, including a controlled invalid attempt per task |
| `B2_validity` | Independently valid trajectories |
| `B2_contribution_only` | Same accepted support and selected Round, weighted only by normalized contribution |
| `B2_novelty_only` | Same accepted support and selected Round, weighted only by normalized novelty |
| `B3_ccgr` | States sampled from a current, frozen CCGR task distribution |
| `B4_random_state` | One deterministic random accepted state per task |
| `B5_vtdo` | States sampled from the selected real VTDO round distribution |

The primary causal arms are B2 Validity, Contribution Only, Novelty Only, B4 Random State, and B5
VTDO. Their per-task sampling weights each sum to one, freezing the task marginal `mu(x)` and
changing only `pi(z|x)`. B1 is a controlled-quality lower bound rather than a natural raw Explorer
distribution. B3 is a historical task-distribution baseline with a deliberately nonuniform task
marginal and is therefore not part of the strict causal comparison.

All training runs use the same Qwen2.5-7B revision, LoRA configuration, and supervised-token
budget. The protocol does **not** claim equal optimizer steps or equal compute. Every run records
assistant-supervised tokens, prompt tokens, total processed tokens, optimizer steps, scheduled
examples, unique records, and repetition rate. The three frozen primary seeds are supplied
explicitly to the trainer. The primary capacity contract requires at least 100 unique tasks and at
least 50 unique accepted states per arm. Dataset size alone is not readiness.

The feedback-loop ablation freezes trainable B5 datasets only at one-based refinement checkpoints
1 and 3. Every trainable checkpoint must contain all task conditions, replay a complete lineage-linked
round sequence from Round 1, preserve exact trajectory-state support, and satisfy the same task,
state, token, model, and benchmark contracts. Each checkpoint has an independent dataset hash and
manifest. Missing real rounds block the comparison; controlled synthetic distributions are never
substituted for these training datasets. Round 1 is the one-shot condition, Round 3 is the primary
iterative condition, and Round 5 is analysis-only and is never materialized as a training arm.

FinQA and TAT-QA are mandatory evaluation-only snapshots for the primary experiment; FinanceBench
is an optional extension. Exact repository revisions, split identities, adapter/metric versions,
and SHA-256 hashes must be frozen before training. The trainer validates the serialized preflight,
arm manifest,
dataset identity, task/state capacity, token schedule, model revision, and benchmark contract
before allocating a GPU.

The one-shot versus iterative comparison uses rounds 1 and 3 with identical task marginals,
supervised-token budgets, model settings, and seeds. Round 5 remains an analysis checkpoint.

## 8. Sensitivity And Quotient Analysis

The controlled run evaluates `eta` in `[0.1, 0.25, 0.5, 1.0]`. Quotient analysis compares raw
trajectory hashes with canonical state identities and reports merge rate, validity purity or
variance, and contribution consistency.

If a run does not preserve complete `Omega_x`, it may be reported only as a canonicalization probe.
It cannot be used to estimate the empirical conditional state distribution.

## 9. Fail-Closed Readiness

### Runtime roles for capability localization

Capability localization uses two separate ladders. They must not be pooled.

`direct_fixed_retrieval` is a positive execution control. Under `PLAN_GIVEN`,
the public Program Skeleton fixes the operation graph, Host code executes the
semantic operations, and the verified answer-result seed is available to the
final-answer realization step. Direct therefore verifies schema exposure,
Host execution, answer projection, and result emission. It is excluded from:

```text
capability-tier selection
response-weighted empirical information matrices
paired Pro/Flash calibration authorization
```

The workflow ladder contains only `scripted_tool` and `autonomous_agent`.
Difficulty must be varied within matched ladder groups that preserve core
answer semantics while changing model-visible workflow demand. Runtime-specific
tiers are allowed, but Pro and Flash must share the selected tier within each
Runtime x Family cell. At least two independent groups must support a selected
tier.

Every API-exposed task contract is an immutable freshness source. Future
populations must exclude all prior normalized core semantic signatures,
including diagnostic and positive-control exposures. Pool exhaustion is a
fail-closed capacity result; it must not be bypassed by weakening the signature.

The workflow localization contract freezes the complete denominator and exact
cost telemetry before execution. It may authorize only an empirical capability
information audit. It cannot directly authorize model ranking, Exact Target,
GP-C, Contribution, or a VTDO update.

### v25.11 workflow information decision

The fresh workflow-only localization completed all 1,260 requested Pro/Flash
rollouts. Technical resolution, bounded JSON, Observation replay, authority
integrity, and budget gates all passed. The source run used 10,457 API calls,
38,067,881 model tokens, and USD 7.3946316566 according to provider telemetry.
This technical result authorized an offline empirical information audit only.

The audit L2-normalizes each frozen model-visible demand vector and evaluates
the preregistered response-weighted second moment. The authorizing population
contains only the shared Tier selected for each workflow Runtime x Family
cell. Direct remains excluded. General difficulty is removed only for the
centered axis-specific diagnostic. Confidence intervals resample Ladder
Groups and within-task realizations. Rank, effective rank, condition number,
boundary mass, informative-axis count, family dominance, Ladder-Group
dominance, and selected-family primary-axis alignment all fail closed.

The audit replayed the complete 1,260-record source denominator, analyzed 270
selected-Tier rollouts, and retained the remaining 990 records only as source
and non-authorizing full-ladder sensitivity evidence. All four Model x Runtime
information cells failed. Selected-Tier residual rank was 3 for Scripted and 2
for Autonomous; effective rank ranged from 1.008 to 1.807. Scripted condition
numbers were 280.84 and 401.49; Flash Autonomous reached 1,014.39 and was
99.61% dominated by one family.

The complete three-Tier sensitivity is explicitly non-authorizing. It shows
that the Scripted full ladder has rank 5 and condition numbers 63.82/77.38,
while Autonomous remains unstable for at least one model. This localizes the
primary loss to single-shared-Tier compression and uneven response support,
not to technical execution failure.

The frozen decision is empirical_capability_information_ready=false,
paired_calibration_authorized=false, and
next_permitted_stage=workflow_task_redesign_only.

The next population must be independently fresh and pre-register multi-Tier
information support. It must not select and evaluate an information-optimal
subset on the same v25.11 outcomes. See
docs/finance_v25_11_workflow_information_audit_report.md.

### v25.12 Flash-first multi-Tier confirmation

v25.12 implements that transition with a separately hashed Development policy and a fresh
confirmation population. Policy selection uses only v25.11 outcomes; confirmation tasks exclude
historical Task signatures, Evidence IDs, and Evidence Version IDs. Flash receives the complete
frozen support (630 rollouts). Pro receives a 20% preregistered anchor subset (126 rollouts) only
after both Flash workflow information cells pass. Scripted Branching, Scripted Stopping, and
Recovery Easy are secondary diagnostics rather than primary information support.

The public task text is frozen before model execution. API calls generate Agent trajectories;
they cannot rewrite the confirmation questions, Programs, support policy, or anchor selection.
See `docs/finance_v25_12_multitier_confirmation_protocol.md`.

### v25.17-v25.18 Runtime Resolution and Flash information

Correctness is a model-capability observation, not a Runtime qualification gate. Let `R=1` denote
a valid measurement instrument and `Y=1` a model success. Every report must preserve both:

```text
P(Y=1 | R=1)  model capability under a valid instrument
P(Y=1)        end-to-end system success
```

Runtime qualification is based only on:

1. execution integrity;
2. typed terminal resolution;
3. Runtime-pathology limits;
4. failure-attribution coverage.

L0 external, L1 task/contract, and L2 tool-environment failures invalidate measurement. L3 model
protocol, L4 Agent decision, and L5 semantic failures remain in the capability denominator. L6 is
success. A passing Runtime with saturated capability outcomes must transition to
`capability_support_redesign_only`, not Runtime repair.

Every formal confirmation uses a fresh group, semantic signature, source task, Evidence ID,
Evidence Version ID, and trajectory seed. The Held-out report may authorize only the Flash
information matrix.

The Flash information contract computes:

- Final Valid empirical information as the primary authorizing response;
- Retrieval, Planning, Calculation, Reconciliation, Verification, Recovery, and Stopping matrices
  as non-authorizing diagnostics;
- an equal-observed-axis joint capability matrix.

All matrices condition on Runtime eligibility, use L2-normalized model-visible demands, and remove
general difficulty only in the centered residual diagnostic. Information rank uses both an
absolute `1e-12` and relative `1e-6` eigenvalue tolerance. Bootstrap inference is stratified by
capability family and resamples both tasks and realizations.

Both Workflow Runtime cells must pass rank, effective-rank, condition-number, boundary-mass,
informative-axis, and family-dominance gates before a sparse Pro anchor can be prepared. Axis-only
matrices cannot independently authorize Pro, Beneficiary screening, Exact Target, or GP-C.

The v25.18 result is fail-closed:

```text
runtime_qualification_passed = true
information_matrix_ready = false
pro_sparse_anchor_authorized = false
next_permitted_stage = capability_task_support_redesign_only
```

See `docs/finance_v25_17_v25_18_runtime_resolution_and_information_report.md`.

### v25.19-v25.20 independent capability-support confirmation

The v25.18 Held-out outcomes may be used only to freeze Runtime-family support rules. They may not
be reused as Confirmation responses. A formal support Confirmation requires:

1. four to six independent matched groups per model-visible family;
2. four to five replicas per selected task;
3. exclusion of Host-controlled capability axes from the corresponding Runtime geometry;
4. zero overlap in source task, group, Evidence ID, Evidence Version ID, core semantic signature,
   and task signature;
5. complete static public-contract satisfiability before the first API call;
6. unchanged Runtime and information thresholds;
7. explicit Family and Ladder-Group information-dominance gates.

Correctness continues to define the response variable. It must not enter Runtime qualification.
The v25.20 Confirmation completed 300/300 Flash rollouts and passed every Runtime gate, but both
information cells did not pass. Scripted failed Final and Joint condition-number gates;
Autonomous failed Final and Joint effective-rank gates. The immutable transition is:

```text
runtime_qualification_passed = true
information_matrix_ready = false
pro_sparse_anchor_authorized = false
next_permitted_stage = capability_task_support_redesign_only
```

This result forbids selecting another subset from the same Confirmation responses and reporting it
as independent evidence. The next Development stage may use the result only to redesign
irreducible Retrieval, Calculation, Reconciliation, and Recovery mechanisms. A new confirmation
must again be disjoint on every frozen freshness channel. Pro, Beneficiary, Objective, Exact
Target, GP-C, Contribution, VTDO rounds, and Student training remain blocked.

See `docs/finance_v25_19_v25_20_capability_support_confirmation_report.md`.

### v25.21 public-benchmark capability audit and mechanism population

The v25.20 response may be used only to identify capability axes requiring a new irreducible task
mechanism. Public evaluation data has two strictly separated roles:

1. FinQA and TAT-QA frozen snapshots may be read only for deterministic aggregate structural
   statistics. Their task content, answers, programs, and report context may not enter synthesis,
   training, paraphrasing, prompting, or task-state construction.
2. GAIA, BFCL V4, WebArena, SWE-bench, and AgentBench may contribute published aggregate counts and
   interaction-design metadata only. Their task content must remain unloaded.

The mandatory v25.21 primary axes are Information Acquisition, Tool Planning, Compositional
Reasoning, Semantic Alignment, Verification, Recovery, and Control/Stopping. A population is valid
only if each axis has one typed mechanism with explicit required dependencies, prohibited
shortcuts, and observable outcomes.

The Development population contract is:

```text
tiers = Easy Control, Bridge, Frontier, Hard Control
groups per mechanism = 2, 4, 4, 2
mechanism count = 7
minimum Development groups = 84
fresh Confirmation groups per mechanism = 5
replicas per Confirmation task = 5
```

Development and Confirmation must be disjoint on Task, Group, Evidence ID, Evidence Version ID,
core semantic signature, task signature, and mechanism signature. Bridge is mandatory: a semantic
alignment mechanism must include a resolvable unit, period, alias, or compatible-definition case
between a trivial compatible control and a genuinely non-comparable hard control.

The Runtime, Agent prompt, tool environment, failure taxonomy, and Workflow Information thresholds
remain unchanged. Correctness is a capability response and cannot become a Runtime gate. Public
benchmark statistics cannot authorize a model call. Before Flash Development, every mechanism must
pass executable dependency checks and destructive shortcut mutations.

The current immutable transition is:

```text
audit_passed = true
experiment_readiness = design_ready_population_not_materialized
pro_api_calls_authorized = false
beneficiary_screening_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = finance_v25_21_mechanism_population_construction_only
```

See `docs/finance_v25_21_public_benchmark_capability_audit.md`.


### v25.22-v25.23 repaired mechanisms and mechanism geometry

v25.22 preserves the two replicated v25.21 findings and repairs only Candidate Verification and
State-dependent Stopping. Candidate Verification now requires independent replay and one
Oracle-frozen semantic repair while preserving unaffected fields. Stopping now requires an
externally observed incomplete state, a verified complete state, and an asymmetric post-completion
action cost. Exact scenario values remain Oracle-only.

Development selection is frozen before a new Confirmation population is sampled. Confirmation
must persist the Development Selection Freeze path, SHA-256, and ID in its Population, and the
Population, Freeze, and Contract identities are replayed again immediately before API execution.

The fresh Confirmation completed 100/100 Flash rollouts with 100% Runtime eligibility and zero
Runtime pathology. Candidate Verification produced 25/25 mechanism-behavior successes;
State-dependent Stopping produced 19/25, with all 19 evaluable trajectories satisfying every
behavior check. Both independently met the unchanged matched-pair rules. Combined with the two
v25.21 mechanisms, this authorizes only a mechanism-specific Information Geometry audit.

v25.23 must not reuse the legacy task-family Information Matrix through an adapter. Its primary
population is exactly the `mechanism_required` variant from each confirmed held-out group;
matched controls remain confirmation evidence and do not enter the matrix. It uses:

```text
I_hat = mean_x p_hat(x)(1-p_hat(x)) a(x)a(x)^T
response = valid_success
demand = frozen seven-axis task demand, L2 normalized
residual = Fisher-weighted centering and weighted least squares on general difficulty
bootstrap = mechanism-stratified task and realization resampling
implementation = complete numerical and typed-source manifest frozen before replay
```

The authoritative v25.23 v2 result fails closed. The initial v1 residual calculation used
unweighted centering/regression under a Fisher-weighted matrix and is retained only as a diagnostic
artifact. In v2, raw rank is 5, but effective rank is 1.20598 and condition number is 1270.31.
After the measure-consistent general-difficulty adjustment, rank is 3, effective rank is 2.40054,
and condition number is 5.26. Boundary mass, marginal-axis information, mechanism balance,
dominance, and residual conditioning gates pass; residual rank and effective rank do not. Therefore
confirmed mechanisms are not yet a well-conditioned capability distribution:

```text
information_geometry_ready = false
pro_sparse_anchor_authorized = false
next_permitted_stage = capability_mechanism_support_redesign_only
```

No current response may be subset post hoc, no threshold may be relaxed, and Pro, Beneficiary,
Exact Target, GP-C, Contribution, VTDO updates, and Student training remain blocked. See
`docs/finance_v25_22_v25_23_capability_mechanism_repair_and_geometry_report.md`.

### Runtime-conditioned observability and cross-population support

For Agent capability measurement, the Runtime exposes a public state
`o_t = psi_R(h_t)`. A capability response is admissible only when action-relevant public state is
both observable and replayable. A failed-action repair context may preserve public conflict
dimensions, available actions, action applicability conditions, and the decision rule, but it must
not select the correct action or expose parameters, Evidence IDs, canonical candidates, or hidden
programs.

Every new Runtime-conditioned experiment must therefore fail closed on:

```text
missing action-relevant public state
unreplayable typed failed-action context
unavailable public action
fixed-position action shortcut
generic failure memory overwriting a typed prerequisite
Host injection of an Oracle action or hidden identity
```

Stable support must be evaluated independently in each preregistered fresh population. Every
population must pass Runtime, geometry, parent minimum-information, and nonzero-task gates. Pairwise
claimed-subspace alignment must also pass. A pooled estimate is diagnostic only and cannot rescue
any failed population.

v25.35 validates the Runtime-conditioned instrument but fails stable support: only one of three
fresh populations passes all support gates, and all three pairwise bootstrap alignments fail.
Consequently Confirmation and Pro remain blocked; the only permitted transition is
`stable_support_redesign_only`.

The full training experiment is ready only when all of the following hold:

1. every requested Finance task has 3-5 independently verified canonical states;
2. empirical contribution observations satisfy the frozen sample and task thresholds;
3. real round artifacts cover the configured refinement checkpoints with exact lineage;
4. B3 uses a current CCGR distribution rather than a legacy synthesis-cell proxy;
5. B5 is derived from the selected real VTDO round;
6. every primary causal arm satisfies the fixed-task-marginal, state, supervised-token, model,
   and multi-seed contracts;
7. the mandatory FinQA and TAT-QA snapshots match their frozen identities and hashes;
8. no public training input contains Oracle evidence IDs, reference answers, or hidden programs;
9. no hard benchmark leakage collision or unavailable required hard channel is present;
   subject overlap is report-only.

The run status is `passed`, `partial`, or `blocked`. A partial run may be useful for component
validation but cannot support the full downstream-training claim.

## 10. Execution

```bash
source scripts/activate_project.sh

trusted-synthesis run-vtdo-experiment \
  --vtdo-config config/vtdo_experiment_finance.json
```

The run emits JSON reports, CSV tables, SVG figures, multi-state artifacts, causal and secondary
training-arm datasets,
preflight results, an input manifest, and a final manifest. A representative artifact set is:

```text
experiment_config.json
input_manifest.json
synthetic_experiment_report.json
synthetic_states.jsonl
synthetic_metric_points.csv
synthetic_phase_observations.csv
table1_synthetic_methods.csv
figure1_distribution_evolution.svg
figure2_contribution_novelty_phase.svg
finance_multi_state/finance_multi_state_report.json
finance_multi_state/finance_multi_state_tasks.jsonl
contribution_validation_report.json
refinement_dynamics_report.json
beneficiary_state_shift_report.json
controlled_refinement_rounds.csv
fixed_potential_operator_verification.csv
moving_potential_tracking_rounds.csv
real_refinement_rounds.csv
table2_moving_potential_tracking.csv
table3_refinement_dynamics.csv
table4_refinement_checkpoints.csv
figure3_moving_potential_tracking.svg
figure4_refinement_dynamics.svg
training_preflight.json
training_arms/*.jsonl
benchmark_leakage_audit.json
vtdo_experiment_report.md
manifest.json
```

GPU training is invoked per ready arm with `train-vtdo-arm`. A blocked preflight exits before model
loading or CUDA allocation. Each invocation must include a seed from the frozen preflight.

External predictions are first generated from an immutable training result and generation config,
then evaluated without training-data access:

```bash
trusted-synthesis predict-vtdo-benchmarks \
  --vtdo-config config/vtdo_experiment_finance.json \
  --training-result <model-run>/training_result.json \
  --generation-config config/vtdo_benchmark_generation.json \
  --output-dir <model-run>/benchmark_predictions

trusted-synthesis evaluate-vtdo-benchmarks \
  --vtdo-config config/vtdo_experiment_finance.json \
  --predictions <model-run>/benchmark_predictions/benchmark_predictions.jsonl \
  --prediction-manifest \
    <model-run>/benchmark_predictions/benchmark_prediction_manifest.json
```

The evaluator reports contract success, semantic accuracy conditional on a valid contract,
end-to-end accuracy, native F1, Wilson intervals, and FinQA program execution accuracy. FinQA
prompts contain pre-text, tables, post-text, and an answer/scale/program contract; TAT-QA prompts
contain tables, paragraphs, and an answer/scale contract. The immutable prediction manifest binds
the training arm/result/seed, adapter and base-model content, generator, generation config, and
evaluation snapshot. Exact/near prompt, evidence, source-record, document, and binding collisions
are hard blockers; an unavailable required hard channel also blocks the run, and subject overlap is
a soft diagnostic.

## 11. Claim Discipline

| Evidence available | Permitted claim |
|---|---|
| Controlled synthetic run | update implementation and controlled distribution behavior |
| Fixed-potential control | numerical verification of the contraction result |
| Exogenous moving-potential track | method-neutral finite-step tracking and dynamic regret |
| Endogenous moving-potential tracks | supplementary feedback-path diagnostics only |
| Real multi-state artifacts | state-construction feasibility and verified state diversity |
| Stable Gradient Projection splits | proxy reproducibility only, not causal Contribution validity |
| Independently authorized Contribution proxy | association with a frozen, numerically identifiable distribution target |
| Paired M0/M1 observations | model-state dependence under the frozen probe contract |
| Equal-budget trained arms | downstream utility comparison |
| Frozen external benchmarks | benchmark generalization under the declared snapshots |

No report may promote a blocked component, simulated observation, or distribution-only checkpoint
into a downstream empirical conclusion.

## 12. Legacy Removal

Historical v0.8/v0.9 source, tests, configurations, reports, checkpoints, and generated outputs
have been permanently removed from the working tree. Restoring tracked source requires an explicit
historical Git revision; ignored generated outputs are not recoverable. The active CLI and config
loader intentionally provide no compatibility alias.


### v25.24 submechanism direction design

After a blocked v25.23 mechanism geometry result, task support must be redesigned inside the four
confirmed parent mechanisms. Each parent supplies six typed candidates and retains exactly five.
Selection is model-free and exhaustive over the 1,296 balanced combinations. Capability demand
must be recomputed from Action primitives and Evidence dependencies; mechanism names and model
responses cannot enter the structural vector.

Before Flash is called, the selected design must satisfy:

```text
residual structural rank >= 5
residual structural effective rank >= 4
residual structural condition number <= 100
high-cosine pair fraction <= 0.35 at cosine >= 0.90
parent support per capability axis >= 2
distinct workflow backbones >= 10
maximum backbone share <= 0.20
```

All selected submechanisms must additionally have distinct, executable Host intervention and
real-Finance Materializer contracts. Structural pass without full Runtime coverage authorizes only
`submechanism_runtime_implementation_only`; it cannot authorize Flash. The primary future
response remains `valid_success`. Tool, verification, recovery, and stopping outcomes are
preregistered diagnostics and cannot rescue a failed primary matrix.

The v25.24 structural design passes, but Runtime coverage is 5/20. Consequently no API or GPU was
used, and Pro, Beneficiary, Exact Target, GP-C, Contribution, VTDO updates, and Student training
remain blocked.
