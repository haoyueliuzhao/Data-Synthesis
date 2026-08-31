# Finance v26.183 QA Release Authority

Audit and implementation date: 2026-08-31

## Audit Input And Preserved Boundaries

This revision responds to the external audit attachment with SHA-256
`9fb5cc07c0db8ceb95c745bcec3dede6a52e82f2555de77784ee1498360ab649`
and byte count 34,207. The work is isolated on branch
`codex/v26-183-qa-release-authority`.

The following facts remain frozen:

- v26.181 source commit `a934a7557caab65cf7f4e6bc65fa87222a2d7461` and its fifteen
  formal artifacts are not modified.
- The independently failed v26.181 empirical Gate remains failed; online execution, production
  release, training, Contribution, and VTDO reinterpretation remain unauthorized.
- v26.182 historical artifact directories remain byte-for-byte unchanged. Their direct
  fifteen-file source manifest is historical evidence for their frozen source commit, not a
  complete source authority for future releases.
- This revision makes zero Provider calls and creates no new model-generated population.

The repair is intentionally a new successor rather than a reinterpretation of either historical
result.

## P0 Closure Map

| Audit finding | Implemented authority |
| --- | --- |
| Hand-listed source root omitted dependencies | Exact full Git tree archive SHA-256, tree ID, and every-file source manifest; preflight executes from the extracted snapshot |
| Plan was self-hashed but not source-derived | Loader recompiles Pattern, EvidenceBinding, Program, and CanonicalSemanticPlan from the current Registry and exact evidence parents |
| Operation semantic contract omitted tool capability | `tool_capability` is included in the operation semantic contract, CanonicalProgramNode, node keys, Plan projections, and allowed-tools derivation |
| BindingSnapshot lacked reload parents | Top-level fixture inputs embed exact EvidenceBundle, EvidenceCorpus, ProofGraph, and EvidenceBinding; loader compares them with source-derived fixtures and recompiles |
| Surface/Task could diverge after full rehash | RealizedTaskPackage requires final instruction equality, exact Answer Schema, protected rendering, derived validation, and Plan-derived allowed tools; loader reruns authoritative realization |
| Quality decision could be laundered | QualityAssessment derives gate partitions, fatal failures, weighted total, and decision; loader reruns CandidateQualityEvaluator |
| Sibling trajectory could be rebound | TrajectoryExecutionDescriptor binds realized package, full public task hash, corpus ID/hash, generator contract, raw generated trajectory, and bound trajectory ID/hash; loader reruns the deterministic generator |
| Release selection trusted summaries | Selection embeds exact Policy, SplitPolicy, and every package/trajectory/assessment/binding record; model load reruns the deterministic selector and compares every field |
| Fraction, quota, Split, and release plan could drift | Exact Fraction assignments, instance Split, instance/schema counts, quotas, release plan, distributions, skeleton metrics, and hard gates are source-derived |
| Artifact catalogs were not top-level authority | QAReleaseAuthorityBundle is cataloged under a report-bound artifact manifest/root and exact directory loader |
| Finance Pilot could overwrite files | Pilot builds bytes in memory, hashes every catalog, binds root to report, fsyncs staged files, and publishes once with RENAME_NOREPLACE |

## Source-Derived Authority Chain

The persisted release chain is:

```text
full Git tree snapshot
  -> Operation Registry + Pattern manifest + Renderer manifest
  -> EvidenceBundle + EvidenceCorpus + ProofGraph + EvidenceBinding
  -> source-compiled Program + CanonicalSemanticPlan
  -> BindingSnapshot + SemanticInstance
  -> protected SurfaceRealization + RealizedTaskPackage
  -> deterministic generation input + raw Trajectory
  -> TrajectoryExecutionDescriptor + bound Trajectory
  -> source-rerun QualityAssessment
  -> RealizationExecutionBinding
  -> authoritative ReleasePolicy + SplitPolicy
  -> source-rerun DiversityAwareReleaseSelection
  -> QAReleaseAuthorityBundle
  -> artifact manifest/root
  -> report-bound release authority
```

A content hash remains necessary but is never treated as sufficient. The exact loader reconstructs
the authoritative object from source-owned parents and compares the reconstructed result to the
persisted result.

## Operation, Plan, And Tool Authority

`operation_semantic_contract` now includes `tool_capability`. Each canonical node persists the
capability and incorporates it into topology and parameterized node keys. The compiler and model
validator use the same frozen canonical input order, preventing a second permutation sort from
changing multi-input node identities during reload.

CanonicalSemanticPlan loading additionally enforces:

- unique parameterized and topology node keys;
- exact output node/topology pairing;
- declared evidence role positions and role maxima;
- operation dependency key/topology pairing;
- dependency existence and acyclicity;
- exact topology, parameterized, semantic-task, and Plan identities.

RealizedTaskPackage derives `allowed_tools` as `evidence.search` plus the sorted non-null Plan
tool capabilities. A task whose tools are changed and whose visible hashes are fully recomputed
still fails the Plan authority check.

## Generation, Evaluation, And Release Replay

`TrajectoryExecutionDescriptor` stores the complete raw deterministic generator output and binds
it to:

- realized package ID;
- canonical public-task content hash;
- EvidenceCorpus ID and content hash;
- generator contract ID;
- generation-input hash;
- generated and bound trajectory hashes.

The bound trajectory ID is derived from all of those fields. The execution binding accepts only
the exact descriptor-derived trajectory. The QAReleaseAuthorityBundle loader reruns
`FinanceNumericCandidateGenerator` for every selected realization and compares the result before
rerunning evaluation.

QualityAssessment no longer accepts persisted summaries independently. Universal/domain gate
partitions, fatal failures, dimension weights, weighted total, and release decision are derived
from hard gates and dimensions. The bundle loader reruns CandidateQualityEvaluator with
`FinanceSemanticPolicy`.

DiversityAwareReleaseSelection v3 embeds all release records and both policies. Pydantic reload
recomputes every record binding, reruns selection, and compares the complete persisted payload.
Exact `fractions.Fraction` conservation remains instance-local.

## Fully-Rehashed Negative Controls

The formal preflight registers twelve counted negative controls. Each records expected exception
type, exact reason token, authority stage, actual exception type/reason/stage, and whether the
target validator was reached:

1. Operation semantic contract changed and top Bundle rehashed.
2. Full source tree identity changed and top Bundle rehashed.
3. Exact evidence row changed in Bundle and Corpus with fixture and Bundle IDs rehashed.
4. Evidence input relabeled as a nonexistent operation dependency with node and Plan identities
   recomputed.
5. Task allowed tools changed with Task, Surface, and package identities recomputed.
6. Persisted Surface validation changed with realization identity recomputed.
7. Accepted assessment relabeled rejected with assessment identity recomputed.
8. One sibling descriptor rebound to another sibling execution.
9. Weight assignment execution pairs swapped with assignment and selection IDs recomputed.
10. Release plan and every assignment ID recomputed around a forged plan.
11. Instance quota changed while persisted hard gates remain true and selection is rehashed.
12. Artifact catalog replaced and manifest root recomputed while the report remains bound to the
    original root.

A separate unrelated `RuntimeError` is deliberately not counted as rejection evidence. This
prevents arbitrary pre-Gate exceptions from laundering a negative-control result.

## Immutable Artifact Publication

Both the QA authority preflight and Finance Pilot use the shared immutable directory writer:

1. Refuse an existing target before expensive work.
2. Serialize every catalog to bytes in memory.
3. Record exact SHA-256 and byte count.
4. Derive an artifact root.
5. Bind manifest hash and root into the report.
6. Create every staging file with exclusive creation.
7. Flush and fsync files and staging directory.
8. Publish with Linux `renameat2(RENAME_NOREPLACE)`.
9. fsync the parent directory.
10. Reopen and rehash the published directory with an exact-membership loader.

No file is opened in overwrite mode on the publication path.

## Verification Results Before Formal Snapshot Freeze

The following results were observed without Provider access:

```text
Ruff changed-file check                                      passed
QA authority + Pilot + realization + historical v2 tests    29 passed
QA authority formal smoke                                   passed
  frozen fixtures                                            2
  release records                                            6
  selected records                                           6
  task types                                                 8
  renderer profiles                                         32
  fully-rehashed attacks                                  12/12 rejected
  unrelated exception counted                            false
  Provider calls                                             0
Broader suite before interruption                           397 passed, 2 skipped
```

The unrestricted test collection is not complete in the current environment because
`pyarrow` and `torch` are absent, causing five existing test modules to fail during collection.
A dependency-excluded run progressed to 397 passed and 2 skipped before it was stopped after two
pre-existing generalization-contract failures. Both failures point to
`runtime/agent/prospective_two_stage_exact_response_grammar.py:424`, a file not modified in this
revision. These facts are recorded as environmental/unrelated boundaries, not converted into a
passing claim.

## Formal Full-Tree Result

The formal successor is
`qa_parent_authority_fully_rehashed_source_derived_bundle_independent_audit_only`.
It executed only from the extracted archive of source commit
`794a546aa2f934939425d7ce929b49f2ce2d1d73`:

```text
Git tree ID                         c4a99bd20b25e5f7db59fab9056ab4255101b542
Git archive SHA-256                8b4f671fdbf04a543b33566e04db613518e9be9b1769d5c3b49e45826eb3483d
Git archive bytes                  986,398,720
source manifest SHA-256            cc04c596c51fc7e347b210af334d27403e4acbbcf93fbc6847aba1282fab470d
source manifest bytes              11,904,982
source manifest members            34,374
```

The runner directly rehashed the archive, required exact extracted-tree membership, and verified
each member's kind, executable bit, byte count, and SHA-256. It ran with Python bytecode writes
disabled so runtime cache files could not contaminate the snapshot.

The immutable formal directory is
`artifacts/qa_realization_vnext/qa_release_authority_v3_20260831`. It contains nine files totaling
12,546,211 bytes. The top identities are:

```text
QAReleaseAuthorityBundle
  qa_release_authority_bundle:c27d2eb35e029d48f267e4726d69c78fff904a9f684e6ecaecd2b878df320923
DiversityAwareReleaseSelection
  diversity_aware_release_selection:ea8359a70f1cedcfe9cf635a49dd347ab18467de2ade99ad063720d31f3afac0
artifact root
  qa_release_authority_artifact_root:54ccb4378c1d8397e218f65dff4776c1c341d9a2d0341a8b9cc29d3faa482f77
artifact manifest
  qa_release_authority_artifact_manifest:25c8dac0c6b7e0f279b8810c41c5a97d5b217058ae2627f17568f034fecc1ae0
```

All twelve counted fully-rehashed attacks reached the declared validator and rejected. The
unrelated RuntimeError did not count. A second independent execution from the same extracted
snapshot produced a directory that matched all nine formal files byte for byte. Provider calls
remained zero.


## Authorization Boundary

This historical successor establishes a deterministic fixed-Fixture source-replay and
immutable-publication smoke. It does not establish the general QA Release Authority or authorize
an archive-backed Finance Pilot. It also does not authorize Provider generation, production data
release, model training, online execution, Contribution, VTDO State changes, or any change to the
frozen v26.181 empirical failure.

## 2026-08-31 Independent Re-audit Reclassification

The latest independent re-audit preserves the exact historical facts recorded above:

- source commit `794a546aa2f934939425d7ce929b49f2ce2d1d73`;
- exact 2-Fixture / 6-Record deterministic replay;
- historical nine-file byte set;
- historical 12/12 observed negative-control rejections;
- zero Provider calls.

It narrows the earlier Gate wording. The v26.183 formal interface accepted Archive, source root,
Manifest, and tree-ID assertions separately; did not consume external audit bytes as a formal
parent; accepted caller-chosen Fixture populations; did not cross-validate every sidecar and
Report field; did not bind Markdown bytes; allowed a non-exact attack denominator; and recorded
stages for ordinary validation exceptions from the expected stage supplied by the test.

Therefore the precise historical result is:

```text
fixed-Fixture same-snapshot source replay          PASSED
historical immutable publication                   PASSED
general QA Release Authority                       NOT CLOSED
external authorization parent                      ABSENT
Archive -> executed Git tree formal projection     FAILED
exact externally expected Release Population       FAILED
cross-catalog Report/Markdown Envelope              FAILED
exact attack set and independently observed stage  PARTIAL
archive-backed Finance Pilot                       UNINSTANTIATED / BLOCKED
```

The successor that addresses these gaps is documented in
`docs/finance_v26_184_qa_release_authority_envelope.md`. This addendum changes no v26.183
artifact byte, Bundle identity, Selection identity, or v26.181 empirical result.
