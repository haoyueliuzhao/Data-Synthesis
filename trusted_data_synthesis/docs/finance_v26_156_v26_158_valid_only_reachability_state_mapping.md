# Finance v26.156-v26.158 Valid-Only Reachability State Mapping

Audit date: 2026-08-26

## Decision

Finance v26.156-v26.158 completes discussion item H: Reachability plus valid-only State Mapping.
It does not repair or reinterpret the failed v26.154-v26.155 Reachability Measurement Gate.
Instead, it freezes a separate eligibility boundary and maps only the 100 independently Qualified
model trajectories that already satisfy `V_qualified is True`.

The completed chain is:

~~~text
v26.156  valid-only Mapper Contract, Candidate Manifest, and Runner preflight
v26.157  exact 100-Candidate Raw-only mapping execution
v26.158  independent Raw remapping and Assignment audit
~~~

The empirical result is 100 valid-only Assignments, 41 unique structural states, and 44 unique
route-condition projections. Ten of the twelve tasks have at least one Qualified Assignment and
all ten exhibit more than one observed Qualified structural state. Two tasks have zero Qualified
Assignments. These are descriptive existence and support facts only.

No Reachability frequency, route-conditioned frequency, state probability distribution, VTDO
update, training row, release row, or production Contribution is authorized. The final decision
freezes the evidence and authorizes no further experiment without a new audit decision.

## Valid-Only API Boundary

The shared public entry point is:

~~~text
map_independently_valid_trajectory_to_state(
    trajectory,
    qualified_validity_report,
    mapper_contract,
)
~~~

The function validates the exact Mapper Contract, requires
`qualified_validity_report.valid is True`, requires that the trajectory crossed the frozen task
Verifier, validates all required Assignment parents, and only then invokes the structural-state
mapping callback. `False` and `None` validity both fail before the callback.

The Contract forbids mapping any:

- Measurement Support exit;
- Instrument failure;
- Privacy rejection;
- Base-invalid trajectory;
- Mechanism-unqualified trajectory;
- row missing an independent Qualified validity report;
- local scripted fixture or static Compiler Path.

The frozen eligibility rule is exactly:

~~~text
V_qualified == true
~~~

No endpoint recovery, Host repair, threshold relaxation, validity alias, or inferred validity is
accepted.

## Required Assignment Bindings

Every Assignment contains and validates all eight required parents:

~~~text
trajectory_content_hash
qualified_validity_report_id
omega_task_context_id
mapper_contract_id
structural_state_id
route_condition_id
static_path_catalog_id
raw_observation_prefix_hash
~~~

The Assignment identity is content-addressed over those bindings and the complete structural State
and route projection. A missing, stale, crossed, or recomputed parent fails closed. The static
Path catalog remains a lineage and route-condition parent; it is never the empirical State.

## Empirical Structural State

The structural canonicalizer is
`public_dependency_multiset.v1` under
`empirical_structural_state_mapping.v1`. It derives a state from the independently reconstructed
public model trajectory and Omega Task Context. The state contains:

- canonical Action classes with multiplicity;
- canonical Evidence and Operation reference classes;
- dependency-edge classes with relation and multiplicity;
- normalized result-semantics hash;
- Evidence-lineage hash;
- typed failure-pattern hash.

Runtime Operation references are normalized through a separately bound Runtime-to-Program alias
table before structural hashing. Independent acquisition order does not split an otherwise equal
state. Surface content addresses in semantic rejections remain in the full trajectory content
hash but are excluded from the structural failure semantics, so proposal, rejection, state, and
selected-action IDs do not manufacture distinct structural states.

The mapper does not read a static expected State, Gold workflow, reference answer, Candidate
position, or Compiler Path as its empirical state. It maps what the Qualified Raw trajectory
actually did.

## Route Projection Is Separate

Each Assignment also binds an `EmpiricalRouteProjection`. The projection retains sampling mode,
public condition, requested Path identity and strategy when conditioned, the frozen static Path
catalog, and empirical Decision/Tool sequences. It is explicitly not a structural State.

The 36 unconditional Qualified rows carry typed absence:

~~~text
public_condition_id       null
requested_path_id         null
requested_path_strategy   null
~~~

The 64 conditioned Qualified rows bind all three fields. Both cases receive a content-addressed
route projection ID, which serves as `route_condition_id` in the Assignment. This preserves an
exact route parent without fabricating a condition for unconditional sampling.

## v26.156 Preflight

v26.156 first independently rebuilds all ten v26.155 formal outputs byte for byte before loading
mapping inputs. It freezes twelve Omega Task Contexts and one Mapper protocol and Contract. The
Candidate Manifest is derived from the exact 360-row Reachability denominator:

~~~text
exact Reachability rows                    360
Qualified-only Candidates                  100
excluded nonqualified rows                 260
unconditional Candidates                    36
conditioned Candidates                      64
Omega Task Contexts                         12
actual State Assignments                     0
actual structural States                     0
Provider calls                                0
Stage 2 Provider calls                        0
GPU jobs                                      0
~~~

All 100 Candidates independently match their Qualified report, Omega binding, route binding, Raw
descriptor, Runtime alias binding, and complete required-input set. Support-exit, Instrument,
Privacy, Base-invalid, and Mechanism-unqualified Candidate counts are each zero.

The preflight uses synthetic constructibility trajectories only to exercise the Mapper. It creates
no empirical State row. Twenty recomputed destructive mutations reject invalid eligibility,
crossed parents, route/Path promotion, static-State substitution, missing Raw binding, Host State
insertion, and unauthorized execution or Provider behavior.

A preliminary v26.156 build failed closed after the predecessor rebuild because unconditional
Rows had `public_condition_id=None` while the first route-projection schema required a string. It
wrote no formal output and made zero calls. The final type explicitly requires all route fields
for conditioned rows and typed absence for unconditional rows. This changes no v26.154 outcome or
Candidate eligibility.

## v26.157 Mapping Execution

v26.157 rebuilds all eleven v26.156 files byte for byte before reading the Candidate Manifest. It
then processes each Candidate exactly once from its bound Raw Execution. For each row it:

1. revalidates the Raw descriptor and Job parent;
2. independently reconstructs the public trajectory projection;
3. reparses the independent Qualified validity report;
4. rebuilds the Omega Task Context and Runtime alias binding;
5. rebuilds the separate route projection;
6. invokes the valid-only gate and structural Mapper once;
7. persists the complete content-addressed Assignment.

The exact integrity result is:

~~~text
Candidates                                  100
Mapper authorizations                        100
Mapper invocations                           100
Raw trajectory reconstructions               100
Runtime alias binding matches                100
eight-parent binding matches                 100
Assignments                                  100
unique structural States                      41
unique route projections                      44
Host-inserted States                           0
nonqualified mapping attempts                  0
Provider or Stage 2 Provider calls             0
~~~

The 100 Assignments retain the 36 unconditional and 64 conditioned partition. State identity can
repeat across rollouts and route projections. Route identity can also repeat without forcing
State identity. The two catalogs are therefore separately content-addressed and separately
audited.

At task level, ten tasks have Qualified Assignments and two Hard tasks have none. The ten supported
tasks each show two to six unique structural states; assignment counts range from two to seventeen.
Every `frequency_or_probability_estimate` remains `null`. Multiple observed states establish only
that more than one Qualified structural outcome exists for those tasks under this fixed sample.
They do not estimate their population probabilities.

## v26.158 Independent Raw Remapping

v26.158 independently rebuilds all eight v26.157 files before loading saved Assignments. It then
uses Raw, Candidate, Qualified report, Omega Context, route, Path catalog, and Runtime bindings to
remap every row. It deliberately does not call the v26.156 trajectory-projection helper, the
v26.156 Runtime-alias helper, or the v26.157 Assignment helper. Saved Assignment fields are not
used as Mapper inputs.

The shared frozen Mapper core is used because the object under audit is the exact frozen Mapper
Contract. The independent Raw adapter and parent reconstruction are separately implemented. The
result is:

~~~text
saved Assignments                            100
independent Raw remaps                       100
exact Assignment byte matches               100
exact structural State ID matches           100
exact route projection ID matches           100
exact trajectory content-hash matches       100
exact Qualified-report ID matches           100
exact Omega Context ID matches              100
exact static Path catalog matches           100
exact Raw observation-prefix matches        100
~~~

The independent Assignment audit also confirms 100/100 Mapper Contract, structural State, and
route-condition bindings, with zero support-exit, Instrument, Privacy, Base-invalid, or
Mechanism-unqualified Assignments and zero static Paths used as empirical States.

Sixteen destructive mutations fail closed. They cover saved-Assignment trust, helper reuse,
parent substitution, eligibility corruption, State/route crossing, Raw-prefix mutation, static
Path promotion, frequency authorization, Provider authorization, and VTDO/release promotion.

A preliminary v26.158 build passed the complete v26.157 8/8 replay and then failed closed because
its canonical serializer handled a top-level model but not a tuple of models. It wrote no formal
output and made zero calls. The final source recursively canonicalizes models, Mappings, and
sequences. This is a representation-layer correction and changes no Assignment or scientific
claim.

Package-wide Mypy subsequently exposed two locally over-narrow dictionary inferences in v26.156.
The authoritative type-complete source gives those heterogeneous dictionaries explicit names and
`dict[str, Any]` annotations. Rematerialization preserves the Mapper Contract, protocol, Omega
catalog, Candidate Manifest, Runner, 100 Assignment bytes, 41 State IDs, 44 route IDs, and every
scientific count. Only source-replay and report identities change through the corrected source
lineage. No Provider call or empirical remapping choice changes.

## Interpretation Boundary

The failed Reachability Measurement Gate does not logically invalidate an independently Qualified
endpoint Mapping. Mapping asks which structural State a valid observed trajectory instantiates;
Reachability estimation asks how frequently states or valid trajectories occur under a sampling
design. The first can be answered for the 100 Qualified rows even though the second cannot be
estimated from this failed denominator.

Accordingly, the evidence supports:

- 100 exact Qualified trajectories mapped to 41 structural states;
- ten tasks with multiple observed Qualified structural states;
- exact structural and route identities for each mapped row;
- zero invalid-category Assignments.

It does not support:

- a Reachability frequency or probability;
- a state probability distribution;
- task, Path, Tier, or mechanism prevalence comparisons;
- causal attribution to route condition or Candidate presentation;
- VTDO Energy, Contribution, Novelty, training, release, or production rows.

## Verification

- valid-only gate plus empirical Mapper Pytest: 11/11 passed in 0.12 seconds;
- v26.156-v26.158 end-to-end Pytest: 4/4 passed in 188.37 seconds;
- focused Ruff and Mypy pass for all final sources and tests;
- package-wide Mypy checks 486 source files and retains four diagnostics: the three historical
  v26.70/v26.129 rows plus one diagnostic in the byte-frozen exact-online v26.154 source; final
  v26.155-v26.158 sources contribute zero diagnostics;
- v26.158 rebuild reproduces all eight formal audit files byte for byte;
- every v26.156-v26.158 stage makes zero Provider, Stage 2 Provider, and GPU calls.

## Authoritative Identities

- v26.156 report:
  `finance_v26_valid_only_mapping_preflight_report:ac21b3b79c2906540da1bd2b2501e962026d7794ca451d5802981fc2390dc975`;
- v26.156 report SHA-256:
  `64264e761653b11db245f8fe13bffc5ae6aaa80b48e0f7021a20b0f91136b978`;
- Mapper Contract:
  `valid_only_state_mapper_contract:36c1f1b9521e5eb0a9cb208b68fd35bfabd3ce658d328c04aa6340e0dead1f2a`;
- Mapper protocol:
  `finance_v26_empirical_state_mapper_protocol:7037f1b479d419918adcfbd074067da32df2baf2d84f33e6355e9ed317711de6`;
- Omega Task Context catalog:
  `finance_v26_valid_only_omega_task_context_catalog:a549aa65632952d0de05870cd79a797a81cd7dafd85931fd94ebb3b95fc8d51b`;
- Candidate Manifest:
  `finance_v26_valid_only_mapping_candidate_manifest:15ba332a17ab5c43b3095e655a74faf6839260e2d0adffe55acb855714136a10`;
- preflight audit:
  `finance_v26_valid_only_mapping_preflight:f04fa040f064f1a111542a37edd4c1026404a1a0de57fae5bfa160ca64e1ec06`;
- Runner Contract:
  `finance_v26_valid_only_mapping_runner_contract:362a8474cfd31fb63153a9616f6145bdb360f4f0905ba8fc9bb552be6354b2c4`;
- v26.156 transition:
  `finance_v26_valid_only_mapping_transition:c09299f19017eb91def5ee9517f0ae9e45cae67051420c24b492c9b04220253f`;
- v26.157 report:
  `finance_v26_valid_only_mapping_execution_report:ea5e59df17b02b2a78423d0bd6187ae7a50514b94fd3b3233e5125c882824405`;
- v26.157 report SHA-256:
  `c475849a468c099ca076e0de5439782b5279b010049326b058bc54002359f12f`;
- Assignment Catalog:
  `finance_v26_valid_only_state_assignment_catalog:24118eb0223869ccd484b73af8595b0407fbc8da6ce3f11d3cfb2a849895156a`;
- structural State Catalog:
  `finance_v26_valid_only_structural_state_catalog:4fb6dede053d7f5f88e6addabd4308b8afed2be0b47b8a4cc04af6b5081edb6a`;
- route projection Catalog:
  `finance_v26_valid_only_route_projection_catalog:60fb8b540be216ee1843b36e801ae01b9893d0c3b3e5e683cb1d2f8b1bb6afb3`;
- execution integrity:
  `finance_v26_valid_only_mapping_execution_integrity:0f4a9c957173edaf1b417aa43c64be93fdd5104db8c8f4b83d715d2fb102b3f3`;
- observed State support:
  `finance_v26_valid_only_observed_state_support:5628b1256606a1b66d6cee484298b13141571c9d6e86829670f211ffab096a71`;
- v26.157 transition:
  `finance_v26_valid_only_mapping_execution_transition:cfec069ea14dd7148e81cdc395cfb9b4f1cc67b3a99a97b20cabf064e7db6311`;
- v26.158 report:
  `finance_v26_valid_only_mapping_postrun_audit_report:cbb21c961f277786490746c5f31956a53e6fee4ee49badf6076b413285ce370f`;
- v26.158 report SHA-256:
  `dcb3a04b29b07f9854d9a98ea9c50acab079ad1e4107f8ed89a28229083a98f8`;
- independent Raw remapping:
  `finance_v26_valid_only_independent_raw_remapping:ec45624d3127bdba6e00c9b3a8b60a0834680dbaa4cfa07b1ede9a2572daabbf`;
- independent Assignment binding:
  `finance_v26_valid_only_assignment_binding_audit:7ee07e5583f8c6c5b53a1d81d5bdf26767ae5e7d161867701f0a57132ff3ebe2`;
- independent observed State audit:
  `finance_v26_valid_only_independent_observed_state:844a873cc9da7460073f837656be037245b5397301d83d73b3985f9e3630cc58`;
- final decision:
  `finance_v26_valid_only_mapping_final_decision:bbf482f9de42af83af3443ae1b36cbd5a276e2d0f937e1c5ff9183d2b9dc0e8f`.

## Final Transition

The final decision is:

~~~text
no_further_experiment_authorized_without_new_audit_decision
~~~

Provider calls, Reachability rerun or recovery, State Mapping rerun or repair, support/validity
threshold change, frequency or probability estimation, task deletion, historical pooling, Host
State insertion, VTDO update, training, release, and production Contribution remain forbidden.
The valid-only State Mapping evidence is frozen and may be used as bounded descriptive evidence in
a future separately authorized audit decision.
