# Finance v25.26-v25.29 Answer Contract And Confirmation Report

Audit date: 2026-08-14

## Scope

This report closes the answer-contract repair, transport stabilization, fresh Finance support,
Flash Development, and held-out Confirmation sequence. It does not evaluate Pro, a Beneficiary,
Exact Target, GP-C, VTDO updates, Student training, or production Contribution.

The scientific transition remained fail-closed throughout:

```text
v25.26 answer-contract defect
-> v25.27 deterministic answer projection
-> v25.28 Flash Development
-> v25.29 fresh held-out Confirmation
-> Confirmation failed one preregistered primary-geometry gate
```

## Answer And Transport Repairs

The original public answer contract did not force the model to emit the exact projected answer
shape. A semantically reasonable free-form answer could therefore fail deterministic replay. The
repaired task population now exposes an answer-type-specific JSON projection and exact public
calculation instruction while keeping Oracle evidence IDs, hidden programs, and reference answers
private.

The iterative Runtime also separates two retry classes:

- transient transport failures repeat the same request with bounded backoff;
- semantic JSON-contract failures use the separately counted contract-repair prompt.

Recovered transient calls no longer become an L0 failure merely because an earlier attempt failed.
The terminal outcome is determined from the final transport state, while every attempt remains in
telemetry. Focused regression tests cover transient recovery, retry exhaustion, answer-contract
fail-closed behavior, and terminal attribution.

## v25.28 Flash Development

The immutable v25.28 run used 20 typed submechanisms, three realizations per task, and the exact
`deepseek-v4-flash` identity.

| Metric | Result |
| --- | ---: |
| Requested / recorded rollouts | 60 / 60 |
| Runtime-eligible rollouts | 60 |
| Complete tasks | 20 / 20 |
| API transport resolution | 100% |
| Bounded JSON resolution | 100% |
| Observation replay | 100% |
| Authority integrity | 100% |
| Runtime pathology | 0% |
| Independent valid success | 48.33% |
| Semantic accuracy given eligible | 58.33% |
| API calls | 545 |
| Provider-reported tokens | 2,634,221 |
| Provider telemetry estimate | `$0.2547436528` |

The telemetry estimate is not an invoice and must not be interpreted as actual billed cost.

The Development primary geometry passed every frozen gate:

| Metric | Result |
| --- | ---: |
| Boundary-task fraction | 0.30 |
| Nonzero-weight tasks | 6 |
| Residual numerical rank | 4 |
| Residual effective rank | 3.280741 |
| Residual condition number | 10.867373 |
| General-factor fraction | 0.385850 |
| Informative axes | 7 / 7 |
| Maximum parent information share | 0.50 |

This authorized only construction of a fresh held-out Confirmation. Diagnostics did not rescue the
primary response, and no Pro call or downstream objective access occurred.

## Fresh Finance Support

The first Confirmation materialization attempts exposed a real capacity problem. A single A or B
source partition could not support all 20 submechanisms after excluding every prior mechanism and
Development population. A 240-task source request also exceeded the archive's measured
corpus-disjoint prefix capacity, while a capacity-bounded 100-task extension produced 41 valid new
tasks but lacked comparison and ratio breadth.

Three immutable source populations were therefore audited together:

- B partition: 180 tasks;
- A partition: 153 tasks;
- fresh extension: 41 tasks.

The A and B populations were not mutually Evidence-disjoint: they shared 515 Evidence Versions and
37 task artifacts. Direct concatenation was rejected.

Two explicit union products were created:

1. A record-level audit union retained 288 of 374 rows, dropping 37 duplicate artifacts and 49
   additional rows with partial Evidence-Version overlap.
2. The materialization input is an Evidence-level union. It merged 3,838 public Evidence
   occurrences into 3,323 unique Evidence IDs and Versions. All 515 duplicate occurrences had
   identical content-bound payloads; there were zero superseded-version and zero content conflicts.

The Evidence-level union preserves the 369 unique evidence items that would have been lost by
discarding an entire source task when only part of its public Corpus overlapped. This relaxation
applies only to the upstream evidence supply. The final Confirmation tasks remain strictly
Evidence-disjoint from each other and from Development.

The resulting 20-task population passed operation replay, Host scenario replay, wrong-branch
rejection, public/Oracle isolation, projected answer-contract coverage, and prior Evidence and
Evidence-Version disjointness. The frozen Confirmation contract independently verified zero
overlap with Development across:

- Evidence IDs;
- Evidence Version IDs;
- Task IDs;
- semantic signatures.

## v25.29 Held-out Confirmation

The immutable Confirmation used five realizations per task and eight parallel API workers.

| Metric | Result |
| --- | ---: |
| Requested / recorded rollouts | 100 / 100 |
| Runtime-eligible rollouts | 100 |
| Complete eligible tasks | 20 / 20 |
| API transport resolution | 100% |
| Bounded JSON resolution | 100% |
| Observation replay | 100% |
| Authority integrity | 100% |
| Runtime pathology | 0% |
| Semantic accuracy given eligible | 63.00% |
| End-to-end valid success | 53.00% |
| Host trigger observed | 80.00% |
| Host resolution observed | 54.00% |
| Ordered behavior success | 54.00% |
| API calls | 887 |
| Provider-reported tokens | 4,253,197 |
| Provider telemetry estimate | `$0.4593833384` |

The combined v25.28-v25.29 provider telemetry is 1,432 calls and 6,887,418 tokens, with an
estimated `$0.7141269912`. This remains provider telemetry rather than verified billing.

Runtime measurement passed every gate. Primary geometry passed every gate except one:

| Primary gate | Observed | Requirement | Result |
| --- | ---: | ---: | --- |
| Nonzero-weight tasks | 7 | >= 5 | pass |
| Boundary-task fraction | 0.35 | >= 0.25 | pass |
| Residual numerical rank | 5 | >= 4 | pass |
| Residual effective rank | 3.437110 | >= 3.0 | pass |
| Residual condition number | 589.296750 | <= 100 | **fail** |
| General-factor fraction | 0.208947 | <= 0.85 | pass |
| Informative axes | 7 | >= 4 | pass |
| Maximum parent share | 0.50 | <= 0.60 | pass |

The residual eigenvalues were:

```text
0.00833230, 0.00594206, 0.00271743, 0.00180689, 0.00001414, 0, 0
```

The first four identifiable directions have condition number 4.6114. The formal condition number
is nevertheless 589.2968 because the frozen implementation treats the weak fifth positive
eigenvalue as part of the identifiable subspace. The preregistered gate cannot be changed after
observing this result.

The formal decision is therefore:

```text
runtime_measurement_ready = true
primary_information_geometry_confirmed = false
diagnostics_rescued_primary = false
pro_sparse_anchor_authorized = false
beneficiary_screening_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = submechanism_confirmation_failed
```

A credential-free completed-run replay resumed `100/100`, executed zero API jobs, revalidated the
implementation and source hashes, and reproduced the same report ID
`finance_capability_submechanism_confirmation_report:f708f8174ed813781c07355cce3d371dbe475ce7f4cf93660b58f36c1b2389ce`.

## Non-rescuing Stability Diagnostics

Post-outcome diagnostics were run only to localize the failure. They do not alter the formal
decision.

Across the same 20 submechanism identities, Development and Confirmation task response
probabilities remained related:

- Pearson correlation: 0.8914;
- Spearman correlation: 0.8288;
- mean absolute probability difference: 0.1333;
- boundary classification agreement: 65%;
- tasks on the boundary in both stages: 3 / 20.

The first two residual principal angles were numerically zero, the third was 2.18 degrees, and the
fourth was 36.25 degrees. Thus the leading subspace partly replicated, but its weakest required
direction was not stable.

A diagnostic-only 10,000-replicate simulation used the pooled 3+5 realization probability for
each submechanism and independently resampled three Development and five Confirmation outcomes.
It used seed 2529 and did not modify any gate:

| Diagnostic | Result |
| --- | ---: |
| Simulated Confirmation condition > 100 | 53.96% |
| Simulated Development rank/effective-rank/condition pass | 13.75% |
| Simulated Confirmation pass | 23.67% |
| Both stages pass | 3.20% |

This shows that the current all-positive-eigenvalue condition gate is highly sensitive to finite
replicates and weak tail directions. It does not justify post-hoc removal of the fifth dimension.

A second diagnostic gap is parent support. Candidate Verification contributed zero Fisher
information in both stages, while the other three parents carried all information mass. The
existing contract constrained only maximum parent share and therefore did not reject a zero-share
parent. Future contracts require a minimum parent-information gate.

## Scientific Conclusion

v25.28 established a valid Development signal under the frozen contract. v25.29 independently
confirmed Runtime integrity and partial leading-subspace structure, but failed the full frozen
geometry decision. It is not evidence for Pro superiority, Beneficiary relevance, Contribution,
or downstream training utility.

The next experiment must be separately identified and preregistered before using new held-out
tasks. It should:

1. define an identifiable residual subspace using an absolute information floor or the minimum
   required rank, rather than every numerically positive eigenvalue;
2. bootstrap the rank, effective rank, and condition decision under task-cluster sampling;
3. require positive minimum information from every parent mechanism;
4. increase repetitions enough to stabilize per-task boundary probabilities;
5. use a new Evidence-, Task-, and semantic-signature-disjoint Confirmation set;
6. keep Pro, Beneficiary, Exact Target, GP-C, and production Contribution blocked until that new
   contract passes.

## Authoritative Artifacts

- v25.28 contract:
  `artifacts/vtdo_experiment/finance_v25_28_submechanism_transport_stabilized_flash_contract_v1_20260814`
- v25.28 Development:
  `artifacts/vtdo_experiment/finance_v25_28_submechanism_transport_stabilized_flash_development_v1_20260814`
- v25.29 record-level source audit:
  `artifacts/vtdo_experiment/finance_v25_29_agent_source_union_v1_20260814`
- v25.29 Evidence-level source union:
  `artifacts/vtdo_experiment/finance_v25_29_agent_evidence_union_v1_20260814`
- v25.29 Confirmation population:
  `artifacts/vtdo_experiment/finance_v25_29_submechanism_confirmation_population_v1_20260814`
- v25.29 Confirmation contract:
  `artifacts/vtdo_experiment/finance_v25_29_submechanism_confirmation_contract_v1_20260814`
- v25.29 completed Confirmation:
  `artifacts/vtdo_experiment/finance_v25_29_submechanism_confirmation_v1_20260814`
