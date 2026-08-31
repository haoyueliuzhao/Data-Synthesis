# Finance v26.184 QA Release Authority External Envelope

## Scope and Status

v26.184 is the credential-free successor authorized by the 2026-08-31 independent re-audit of
v26.183. It does not replace or reinterpret the frozen v26.183 nine-file directory. It closes only
the authorization, source projection, exact population, cross-catalog envelope, report authority,
attack-denominator, and runtime-identity defects identified by that audit.

The external audit consumed by this revision is the exact uploaded byte sequence:

```text
SHA-256    68a7c3247fa1f64171b99bada692704e5fc128dc43c75ba574a7c7aa331352b3
bytes      28,302
```

Provider generation, model-generated QA rows, archive-backed Finance Pilot execution, production
release, training, Contribution, VTDO, and any change to the v26.181 empirical result are outside
the authorized transition. Provider calls for this stage remain exactly zero.

## Re-audit Reclassification of v26.183

The v26.183 implementation repairs the v26.182 constructor-path failures and its exact historical
2-Fixture / 6-Record run remains reproducible. The stronger phrase “QA Release Authority passed”
is narrowed to:

> Fixed-Fixture same-snapshot source replay and immutable-publication smoke passed.

The v26.183 formal interface did not itself close the following general contracts:

- external audit bytes as an object-level authorization parent;
- one Archive-derived projection into the executed root and recomputed Git tree;
- an externally expected exact Release Population identity;
- joint authority over Report, Markdown, Bundle, Selection, Records, attacks, and source catalog;
- an exact attack-ID denominator with independently observed typed stages;
- interpreter, dependency, OS, libc, locale, timezone, and environment-root identity.

v26.184 introduces new versioned objects instead of changing the historical v26.183 schemas or
artifact bytes.

## Authority Chain

```text
External audit bytes
  -> QAReleaseAuthorityAuthorization
Exact Git commit
  -> internally generated Git archive
  -> safe internal extraction
  -> every-member SourceSnapshotManifest
  -> recomputed Git blob/tree identity
  -> QAReleaseSourceProjection
Authorization + SourceProjection + pre-outcome surfaces
  -> QAReleasePopulationManifest
Source-replayed v26.183 Bundle
  -> Selection + Records
Exact typed attacks
  -> AuthorityAttackAudit
All semantic sidecars
  -> QAReleaseAuthorityArtifactManifest
Reconstructed parent facts
  -> content-addressed QAReleaseAuthorityReport
All parents + Report + Markdown hash
  -> externally expected QAReleaseAuthorityEnvelope
```

The directory Loader requires three values that cannot be learned from the directory being
validated:

```text
expected_authorization_id
expected_population_id
expected_envelope_id
```

It additionally requires the exact external audit path and source archive path. It never reads an
expected identity from the candidate Report.

## External Authorization Contract

`QAReleaseAuthorityAuthorization` freezes:

- actual audit SHA-256, byte count, and a typed audit-byte identity;
- predecessor commit `2485d44b506814a507b4c45fa3245758bcd16d11`;
- exact successor source commit;
- the only permitted transition;
- an exact, sorted Git change-path set;
- the observed Git change-path set;
- an exact forbidden-operation set;
- a content-addressed `authorization_id`.

The source-projected runner computes the observed path set with
`git diff --name-only <authorized-predecessor> <source-commit>`. Authorization validation requires
exact tuple equality, not subset membership or a caller-supplied descriptive label.

The formal artifact directory stores the exact audit bytes as `external_audit.txt`. The Loader
requires those bytes to equal both the external file supplied by the auditor and the authorization
hash/count. Omitting or replacing either copy fails at the typed `authorization` stage.

## Exact Source Projection

The outer runner performs the only permitted source construction:

1. resolve the exact source commit in the repository;
2. derive its Git tree with `git rev-parse <commit>^{tree}`;
3. generate a mandatory tar using `git archive`;
4. extract regular files and symlinks into a newly created temporary root;
5. set `PYTHONPATH` only to that extracted root;
6. execute the inner preflight module from that extracted root.

The inner preflight independently:

- obtains the archive-embedded commit with `git get-tar-commit-id`;
- streams and hashes the actual archive bytes;
- rejects absolute, empty, dot, parent-traversal, duplicate, hard-link, device, and other non-Git
  members;
- derives every file/symlink byte count, SHA-256, executable mode, and Git blob ID;
- recursively recomputes the Git tree object ID from Git modes, names, and blob IDs;
- requires exact equality with the bound commit/tree;
- compares exact archive membership and every member byte/mode against the root containing the
  executing module;
- binds the executed module path and SHA-256 into `QAReleaseSourceProjection`.

There is no public `source_root` argument in this stage. Archive, Manifest, Tree ID, and executed
root can no longer be supplied as unrelated parallel assertions.

The reusable Loader extracts the supplied archive into its own temporary directory and rebuilds
the same Projection and Manifest. The formal run separately proves that the executing interpreter
used that extracted root.

## Exact Release Population

`QAReleasePopulationManifest` is a pre-outcome identity. It contains:

- authorization and source-projection parents;
- exact sorted Fixture indexes and Fixture input IDs;
- exact sorted SemanticInstance IDs;
- one content-addressed member per pre-evaluation realized surface;
- task type, semantic schema, semantic instance, BindingSnapshot, RealizedTaskPackage, and
  SurfaceRealization identities;
- source selection contract over Fixture indexes and frozen Release/Split policies;
- `fail_closed_exact_set_equality` missing/duplicate/extra policy;
- a content-addressed `population_id`.

Trajectory, assessment, and release outcome IDs are deliberately excluded from Population member
identity. They remain downstream results. The Loader reconstructs the Population from the source
replayed Bundle and compares it both to the persisted sidecar and to the caller's external expected
Population ID.

Removing Fixture 2 or adding a valid Fixture 3 produces a different Population ID and fails before
the altered outcome can authorize itself.

## Cross-Catalog Envelope

The v26.184 directory contains fifteen files:

```text
external_audit.txt
authorization.json
source_projection.json
source_snapshot_manifest.json
runtime_environment.json
release_population.json
qa_release_authority_bundle.json
release_selection.json
release_records.jsonl
attack_controls.json
attack_audit.json
artifact_manifest.json
report.json
report.md
envelope.json
```

The Artifact Manifest catalogs the eleven semantic sidecars. Its own bytes, the Report, Markdown,
and Envelope are not placed in a circular Merkle root. Instead:

- the content-addressed Report binds the Artifact Manifest identity/root and all semantic parent
  IDs;
- the Envelope embeds the Manifest, Report, Authorization, Projection, Population, Runtime,
  Bundle, Selection, Records, and Attack Audit;
- the Envelope binds the exact Report Markdown SHA-256 and byte count;
- the caller supplies the expected Envelope ID externally.

This breaks the self-reference cycle without leaving Report or Markdown unauthenticated.

The Loader parses and requires:

- `release_selection.json == Bundle.release_selection == Envelope.release_selection`;
- `release_records.jsonl == Selection.release_records == Envelope.release_records`;
- `attack_controls.json == AttackAudit.controls == Envelope.attack_audit.controls`;
- `source_snapshot_manifest.json == archive-derived manifest`;
- every remaining semantic sidecar equals its embedded Envelope object;
- all Report fields equal a fresh reconstruction from the validated parents;
- `report.md` equals the deterministic Markdown projection byte for byte.

A Report-only ID mutation, a Markdown mutation, or all Catalogs plus Manifest and Report jointly
rehashed cannot replace the externally expected Envelope.

## Exact Typed Attack Audit

The v26.184 frozen denominator is exactly 23 counted attack IDs. It preserves the twelve v26.183
control themes and adds the re-audit controls:

1. Operation semantic contract rehashed.
2. Full source binding rehashed.
3. Raw Evidence parents rehashed.
4. Plan dependency rehashed.
5. Task tool set rehashed.
6. Surface validation rehashed.
7. Assessment decision rehashed.
8. Sibling trajectory rebound.
9. Weight pairing swapped.
10. Release Plan rehashed.
11. Quota policy changed while hard Gates remain true.
12. Catalog/root replaced.
13. Report-only parent ID changed and Report ID rehashed.
14. Markdown bytes changed.
15. Catalogs, Manifest, and Report jointly rehashed.
16. One Fixture removed with downstream identities rebuilt.
17. One valid Fixture added with downstream identities rebuilt.
18. External audit omitted or replaced.
19. Unrelated Archive paired with the valid authority context.
20. Arbitrary tree ID paired with a valid Manifest.
21. One registered attack silently omitted.
22. Wrong validator emits the same exception phrase.
23. Archive-backed Pilot evaluator/profile substituted for the Fixture evaluator.

Every counted row must observe exactly:

```text
actual exception type == QAReleaseAuthorityError
actual reason_code     == frozen expected reason_code
actual stage           == frozen expected stage
```

`AuthorityAttackControl` derives all three rejection booleans from those actual fields.
`AuthorityAttackAudit` requires the exact ordered ID tuple and derives missing, duplicate, and
extra sets. A raw `ValueError` containing the expected phrase has no actual authority stage and is
not counted. A separate unrelated `RuntimeError` also remains uncounted.

## Runtime Environment Identity

`RuntimeEnvironmentIdentity` freezes:

- Python version and implementation;
- SHA-256 of the executing Python binary;
- Pydantic version;
- a sorted installed-distribution name/version lock hash and distribution count;
- source dependency-definition hash;
- OS and kernel release;
- libc identity;
- locale;
- timezone environment/name identity;
- resolved `sys.prefix` environment root.

The Loader recaptures the runtime and requires exact identity. This does not claim that absent
`pyarrow` or `torch` tests passed. It makes the environment limitation explicit and
fail-closed.

## Verification Before Formal Freeze

```text
new Envelope test module                         6 passed
exact attack registry                           23/23 typed rejections
wrong-validator phrase control                  not counted
unrelated RuntimeError                          not counted
Provider calls                                  0
```

The implementation-source snapshot and formal fifteen-file directory are frozen only after the
source commit is created and the source-projected runner completes. Exact formal identities and
independent rebuild results are added in the evidence-freeze commit; they are not predicted here.

## Scientific Boundary

If the formal Gate passes, it establishes only:

> The exact two-Fixture deterministic QA release can be externally authorized, reconstructed from
> one Git-archive source projection, checked against an externally expected pre-outcome
> population, and authenticated across all persisted catalogs and reports under the frozen
> runtime.

It does not establish:

- Archive-backed Finance Claim/Source Grounding/Workflow verification;
- general QA language or task diversity;
- model-generated QA Population validity;
- Student utility or training benefit;
- production release readiness;
- any repair of the five failed v26.181 empirical Outcome authorities.

The only permitted next decision after this Gate is an independent audit of these exact
credential-free artifacts. Archive-backed Pilot execution remains uninstantiated and blocked.
