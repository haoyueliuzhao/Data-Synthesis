# Finance v26.189 Artifact-Backed Online Post-run Independent Audit

Audit date: 2026-08-31

## Authorization and boundary

This stage consumes only:

```text
capability_observation_artifact_backed_192_job_postrun_independent_audit_only
```

The external v26.188 result audit is exactly 11,240 bytes with SHA-256
`25b3049a42cd22f3613ce4e29df77b8eb92299f69f3dce625964914434a5a762`.
It authorizes a credential-free independent replay of the immutable v26.188 online directory. It
does not authorize Provider rerun, RecoveryJobs, request-route repair, Mapper, State, frequency,
Contribution, VTDO, Student, training, release, or production.

The implementation fails before predecessor loading when `DEEPSEEK_API_KEY` is present. Provider
client construction, Provider discovery, Stage 1 and Stage 2 Provider calls, and Confirmation
payload access are absent from the audit path.

## Frozen predecessor

The audit binds the exact v26.188 Git identities:

```text
source commit   53d0128f22043a88efb612af835aa99bdc78ede4
source tree     38456681dfd2e3d18fa65b1268245affc1e34d39
artifact commit da40cb1512d86296cbeb14b127ace4c20cfd076e
artifact tree   ac3371743c1ec3d010bf27dea6afb860e7297530
```

It reads the immutable directory
`finance_v26_188_artifact_backed_online_development_execution_v1_20260831` before and after the
complete replay and requires byte-identical snapshots. The expected geometry is 1,350 files and
3,618,348 bytes.

The v26.188 documentation records content root
`finance_v26_188_online_execution_content_root:c2aac4f4cfcfad9729bcd64fd8945026d75b5fb85a067d7022a4db22f55bd3a7`,
but did not persist that root's exact preimage. v26.189 therefore preserves the recorded value as
a predecessor statement and separately defines a reproducible content root over a sorted tuple of
`relative_path`, `sha256`, and `byte_count` bindings. The two differently defined identities are
not compared as if they shared a preimage.

## Independent reconstruction method

The audit does not import or call the v26.188 online projector, execution Gate, report builder, or
summary helper as an outcome oracle. It directly loads and strictly validates:

- the exact v26.179 Development Manifest and Runner;
- the exact v26.181 Terminal Registry;
- the exact v26.186 Artifact-backed Outcome Contract;
- all 192 v26.188 Job records and checkpoints;
- all 192 canonical Raw and 192 canonical Result artifacts;
- all 192 Provider Envelopes, 192 public no-payload Projections, and 192 Transport certificates.

For every Job in the exact frozen `expected_job_ids` order, the replay independently checks:

1. Job-record content identity and exact checkpoint ordinal;
2. Manifest Job, Runner, execution Package, source Package, Replica, Raw namespace, and Result
   namespace parents;
3. Raw -> Result -> AttemptTrace -> Outcome identities and cross-object parents;
4. canonical Raw/Result bytes against descriptor SHA-256 and byte count;
5. Provider/Projection/Transport descriptor bytes and content identities;
6. Dynamic request, Stage 1 request, and Transport certificate parent bindings;
7. exact HTTP-400 telemetry and absence of response Envelope, public payload, model identity, and
   Usage;
8. frozen `provider_identity_failure` terminal projection and its derived FailureLocus;
9. `first_policy_qualified_valid=false` and `bounded_policy_qualified_valid=false`;
10. independent reconstruction of the exact frozen empirical evaluation identity.

Raw/Result artifacts use canonical model JSON with a trailing newline. The privacy-first Provider
and public-projection journal uses canonical compact JSON without a trailing newline, while the
Transport journal uses canonical JSON with a trailing newline. v26.189 validates each actual byte
representation instead of imposing one unrelated serialization convention on all three stores.

## Independent result

The exact replay closes the evidence surface as:

```text
Job records / checkpoints                 192 / 192
Raw / Result                              192 / 192
Raw/Result byte matches                   384 / 384
Provider Envelope descriptors             192 / 192
public Projection descriptors             192 / 192
Transport certificates                    192 / 192
Provider/Projection/Transport byte matches 576 / 576
exact parent-chain matches                 192 / 192
typed terminal projections                192 / 192
```

The recomputed empirical evaluation identity is exactly
`capability_artifact_backed_empirical_evaluation:71771453c6fe86b832e7b7924b03896c8643ceda27d572972fcf826a2672842a`.
No v26.188 row, file, label, terminal, or estimate is changed.

## Raw-event decomposition

The independent raw-event layer is:

```text
Stage 1 requests                              192
Stage 2 requests                                0
HTTPError / HTTP 400                    192 / 192
HTTP success                                    0
response Envelope                               0
model identity evaluable                        0
observed wrong-model response                   0
public response payload                         0
Usage observations / Usage tokens             0 / 0
raw HTTP response body persisted                0
frozen provider_identity_failure              192
actual responding model                   unknown
```

The frozen terminal label remains correct under its historical Registry and estimator. The
independent event decomposition narrows its interpretation: missing `response_model` followed an
HTTP rejection before model identity became evaluable. It is not evidence that another model
answered. Because the HTTP 400 bodies were not persisted, the Provider's server-side reason is
unavailable and is not guessed.

## Estimand separation

The frozen end-to-end Job estimands remain:

```text
q_first              0 / 192
q_bounded_correction 0 / 192
paired gain          0 / 192
```

These values describe the exact route, request protocol, model configuration, Runner, and
resource system jointly. The independently defined model-endpoint indicator has denominator zero:

```text
HTTP-success model endpoints       0
Qualified semantic endpoints       0
q_semantic_given_model_endpoint null
```

The conditional semantic value is `null`, not zero. Model semantic Capability, D0-D3 Capability
Depth, planning, correction, Tool selection, and Final-answer behavior were not instantiated.

## Layered Gate result

```text
Job exact-set                      PASS
Raw/Result completeness            PASS
Artifact-byte authority            PASS
Typed terminal totality            PASS
Parent-chain reconstruction        PASS
Frozen terminal admission          PASS
Provider request acceptance        FAIL
Model endpoint observability       UNINSTANTIATED
Semantic Capability measurement    UNAVAILABLE
Mapper / State admission           NOT_AUTHORIZED
```

The six evidence-authority layers pass. They are not renamed as a passing Capability Measurement
Gate. The first blocker is exactly `HTTP 400 before response Envelope and model endpoint`.

## Determinism and controls

The focused suite covers complete 192-Job replay, layered Gate and estimand separation, false
model-observation rejection, exact external-audit bytes, credential rejection, byte-identical
empty-directory rebuild, and no-replace publication. The formal build uses kernel
`renameat2(RENAME_NOREPLACE)` through the shared immutable-artifact writer.

Final test counts, formal identities, and the formal artifact Root are recorded after the
source-freeze build.

## Decision

After consuming the exact post-run independent-audit authorization, the decision is:

```text
no_further_experiment_authorized_without_new_audit_decision
```

The audit records
`exact_route_http_400_request_contract_root_cause_audit_only` only as the external review's
recommended subject for a future new audit decision. That stage is not authorized now. Provider
rerun, RecoveryJobs, route repair, and downstream empirical work remain forbidden.
