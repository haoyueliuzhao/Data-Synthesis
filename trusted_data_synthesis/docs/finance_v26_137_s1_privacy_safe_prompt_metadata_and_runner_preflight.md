# Finance v26.137 S1 Privacy-Safe Prompt Metadata Rematerialization And Runner Preflight

Audit date: 2026-08-24

## Scope And Authorization

Finance v26.137 consumed only the credential-free successor authorized by v26.136:

```text
fresh_s1_privacy_safe_prompt_metadata_rematerialization_and_runner_preflight_only
```

The stage repairs only the two classifier-sensitive model-visible Prompt metadata Keys identified
by v26.136. It preserves the exact S1 projection, Candidate authority and presentation, Action and
Final Grammars, privacy classifier, model and Thinking profile, Completion and rollout bounds,
ABI/Semantic/Transport recovery channels, Ordinary Detour allowance, privacy-first persistence,
and zero-Provider Stage 2.

The stage did not read a credential, construct a real model client, make a Provider call, expose a
role source, create an empirical row, or reclassify a historical result. All model-like responses
used by the Runner preflight came from the deterministic local scripted client.

The formal v26.134-v26.136 result remains unchanged:

```text
S1 representation Qualification = failed
```

The historical privacy-rejected row remains privacy-rejected. Its omitted payload and rejected Key
remain unavailable, and v26.137 makes no claim that either repaired Prompt Key caused that row.

## Complete Source Replay

Before Prompt compilation or Runner construction, v26.137 replayed 3,884/3,884 files:

- all 3,873 v26.136 transitive entries;
- all ten v26.136 output files;
- the exact v26.137 implementation.

It then independently rebuilt all ten v26.136 outputs and matched them byte for byte. The replay
retains the v26.136 Gate decomposition: Entry quantity 31/32 passed, all 12/12 Mechanism x Path
cells were covered, Instrument integrity passed over 197 calls, Privacy passed for 31/32 Jobs, and
the noncompensatory overall Gate failed.

## Strong Privacy-Safe Prompt Metadata Contract

The Host-internal typed policy retains the original facts:

```text
private_reasoning_reused = false
private_reasoning_content = forbidden
```

Only their model-visible structured projections change. The new strong Prompt Schema freezes:

```text
private_reasoning_reused
    -> hidden_model_content_reused

response_grammar.private_reasoning_content
    -> response_grammar.hidden_model_content
```

The new Prompt protocol is:

```text
prospective_role_scalable_semantic_action_prompt.v2
```

The replacement Key names contain no casefolded `reasoning` substring. The privacy prohibition is
retained as a scalar value, which the unchanged classifier does not scan:

```text
Do not include or reuse private chain-of-thought or hidden reasoning in the public JSON response.
```

This is compiled through `PrivacySafeVisibleGrammar` and `PrivacySafePromptEnvelope`; it is not an
ad hoc serialized-string replacement. The strong Schema rejects the old Keys, any new structured
Key containing `reasoning`, `hidden_model_content_reused=true`, and any weakened privacy
instruction.

The exact permitted model-visible differences from v26.133 are limited to:

1. the Prompt protocol value moving from v1 to v2;
2. the top-level privacy metadata Key rename;
3. the nested response-Grammar privacy metadata Key rename and its explicit scalar instruction.

All other serialized Prompt objects must compare equal after those three typed projections are
removed.

## Prompt-Privacy Joint Compilation

The static denominator remains:

```text
324 registered S1 states
x Primary / ABI Rescue / Semantic Recovery
= 972 model-visible Action Prompts
```

The predecessor and successor controls are:

| Check | v26.133 Prompt | v26.137 Prompt |
| --- | ---: | ---: |
| classifier-sensitive Key occurrences | 1,944 | 0 |
| Prompts with a sensitive Key | 972 | 0 |
| full Prompt-payload echo privacy rejection | 972 | 0 |
| full Prompt-payload echo privacy acceptance | 0 | 972 |
| intended exact Action payload privacy acceptance | 972 | 972 |

The full new Prompt payload is still invalid under the four-field Action Grammar. Privacy
acceptance therefore does not turn Prompt echo into an accepted Action; it only removes the
system-created privacy rejection hazard. A dedicated control proves this separation.

Every intended exact Action payload passes both the unchanged Action Grammar and unchanged privacy
classifier. Twenty-four synthetic forbidden `reasoning`-Key payloads remain privacy-rejected, and
all 24 frozen v26.136 classifier type-system cases retain their expected result.

Across all 972 predecessor/successor pairs, the following are exact:

- public-state reconstruction: 972/972;
- Candidate set and presentation order: 972/972;
- reference Proposal: 972/972;
- reversible same-action Stage 2 Commit: 972/972;
- only-authorized-difference comparison: 972/972;
- fresh Prompt hash: 972/972.

No full-object fallback is present. The Action Grammar remains the exact four scalar string fields
`state_id`, `action_id`, `decision_kind`, and `protocol`. Stage 2 still has no Provider route.

## Fresh Identity Chain

The Prompt change is not attached to a historical identity. v26.137 materializes:

- one fresh Prompt metadata Contract and Prompt protocol;
- 24 fresh engineering-only TaskPackages;
- 48 fresh Paths containing 324 typed state rows and 972 new Prompt bindings;
- one fresh Resource Contract;
- one fresh Qualification Contract;
- one fresh 32-Job Manifest;
- one fresh Outcome Contract;
- one fresh Runner Contract;
- fresh prospective execution and report identities.

TaskPackage, Path, and Job overlap with their direct predecessors is zero. All 32 source
assignments and seeds are preserved exactly. Candidate presentation uses the predecessor
qualification Job as an explicit salt parent so that fresh Job identity does not silently reorder
the frozen Candidate presentation. Each fresh Job also binds its direct predecessor Path and its
underlying engineering Path separately.

The 24 sources are the already model-exposed, permanently engineering-only sources used by the
prior S1 qualification. No frozen role source is included or exposed. These rows remain ineligible
for Capability, Reachability, State Mapping, training, release, or production evidence.

## Resource Requalification

The bounds remain exactly:

```text
Prompt bytes                              60,000
Primary Stage 1 requests                      21
Stage 1 Provider calls with recoveries        23
transport-inclusive invocations               24
Completion request tokens                 16,384
Provider accounting margin                     1
rollout tokens                          1,120,000
ABI / Semantic / Transport / Detour       1/1/1/1
```

The explicit scalar privacy instruction increases the registered Action Prompt maxima by 84 bytes
relative to v26.133:

```text
Action Primary maximum                    14,035
Action ABI Rescue maximum                 14,139
Action Semantic Recovery maximum          14,135
Final Primary maximum                      5,152
Final Rescue maximum                       5,286
maximum registered complete Path         340,428 tokens
```

The resource limits themselves do not change. Every registered Path remains within the 60K and
1.12M ceilings.

## Credential-Free Runner Preflight

The future Runner renders the v2 privacy-safe Action Prompt directly. It does not patch or mutate
the historical renderer. It retains dynamic request, exact request-body, resource, and transport
certificates before scripted invocation; privacy-redacted Envelope persistence before public
Projection; exact Action and Final parsing; reversible Stage 2 Commit; separate ABI and Semantic
recovery; one Transport replacement; the Ordinary Detour limit; and Raw-only recovery.

The 32-Job direct fixture produced:

```text
scripted Jobs                                      32
completed Jobs                                     32
first-action interface-qualified Jobs              32
covered Mechanism x Path cells                     12
privacy-safe Action payloads / Prompts             224
reversible Stage 2 Commits                         224
public Observations                                192
exact Final payloads                                32
privacy-first Envelope / Projection pairs          256
complete Raw zero-call recoveries                   32
scripted local calls                               256
real Provider calls                                  0
Stage 2 Provider calls                               0
```

All 224 model-visible Action Prompts use the v2 protocol and contain zero classifier-sensitive
Keys. The fixture uses zero full-object Action Prompt.

Seventeen Runner controls pass for:

- privacy-safe ABI Rescue and separate Semantic Recovery;
- single Transport replacement;
- privacy-first generic rejection with no rejected payload or Key persistence;
- Completion Usage 16,384/16,385 admission and 16,386 Instrument failure;
- one Ordinary Detour plus ordinary replanning;
- second-Detour terminal after the Proposal and Tool Observation but before a later call;
- exact Final ABI separated from answer validity;
- complete Raw zero-call recovery and orphan blocking;
- S1-only execution with no full-object fallback;
- role class-external opportunity separation;
- exact resource/counter binding;
- 972-Prompt structured-Key noninterference;
- unchanged privacy prohibition and classifier behavior;
- immutable historical failed Gate and rejected row;
- clean Prompt echo privacy acceptance separated from Action Grammar rejection.

All 28 destructive mutations fail closed. They cover restoration or introduction of sensitive
Keys, privacy-instruction weakening, classifier/Grammar/Candidate/S1/model/Thinking changes,
resource or counter changes, a Stage 2 Provider route, full-object fallback, predecessor identity
reuse, seed change, role-source insertion, historical reclassification, a compensatory Privacy
Gate, and role Provider authorization.

## Prospective Outcome And Stop Rules

The fresh Outcome Contract keeps Entry, cell coverage, Instrument integrity, Privacy, and overall
authorization separate. The integrity-failure tolerance remains zero and the Privacy Gate remains
noncompensatory.

It freezes three interpretations before any future model result:

1. If the exact future denominator has zero Privacy rejection and passes the complete Gate, it
   still requires an independent postrun audit before any role transition.
2. If a Privacy rejection occurs after the Prompt Key surface is clean, it is a model privacy-
   noncompliant public output under that exact condition. The run fails closed; classifier
   relaxation, Alias handling, output-field stripping, Host repair, or repeated Prompt tuning
   until 32/32 are forbidden.
3. If Action Entry decreases, that is behavior under a new Prompt condition. The historical
   31/32 result is not pooled or borrowed as pass evidence.

## Authoritative Identities

- report:
  `finance_v26_privacy_safe_s1_prompt_preflight_report:f3521184c8788b69eaffdba3d655ddeca236e6ce92dcee5fb0edfb5fc996ad3d`;
- report SHA-256:
  `182e77d42ad959ca95868c866087b14a855e13646f7fa37c3d54ff1bbc98e870`;
- source replay:
  `finance_v26_privacy_safe_s1_source_replay:f28ea80580092d958029f0f68881d62d7c23699917f703c69d09c7ebc9be350a`;
- predecessor integrity:
  `finance_v26_privacy_safe_s1_predecessor_integrity:ab130b7b801afa3d1c68c32028c88b681eb81c4eff53e7e5bf30ecd192558513`;
- Prompt metadata Contract:
  `finance_v26_privacy_safe_prompt_metadata_contract:13b048dc569ea491edbf4f6dbf636240634537e55f3f30a50e6cfb8410c4da72`;
- TaskPackage catalog:
  `finance_v26_privacy_safe_s1_task_package_catalog:a374b63b6d302639f5ea5dd9e04f8ade004e77ad8147348c445dea181d308ebe`;
- Path catalog:
  `finance_v26_privacy_safe_s1_path_catalog:6237687d3c3848ff95c0e0f6da0c1d54b4da3d167bc893fb147ded9992388492`;
- Prompt/privacy noninterference audit:
  `finance_v26_prompt_privacy_noninterference_audit:7d5e97c6185c2152fdbd2dd70e4309dbc134f912b735f9941f38b9082a34da52`;
- Resource Contract:
  `finance_v26_privacy_safe_s1_resource_contract:872b73c646ea0cee8b7175f89ac93b12c0eaa39a57824fe186c4c549319ef4fd`;
- Qualification Contract:
  `finance_v26_privacy_safe_s1_qualification_contract:8a30551b948f00c97dd977f5cbff681276dfc754198a89c1d6b30eb02724d8e1`;
- Manifest:
  `finance_v26_privacy_safe_s1_qualification_manifest:2dbf821ed38afcab1a11523b20908bf712a559f2eaa3e1c400932785c62c9bd0`;
- Outcome Contract:
  `finance_v26_privacy_safe_s1_outcome_contract:79e46804cab483f04ebaead93a4b11cd6b2055df604585c291262cd8dc9b1518`;
- Runner Contract:
  `finance_v26_privacy_safe_s1_runner_contract:0ddeec858f4c7d9d3453de485bf4d034fe78be6ec421010d03909615f9c38963`;
- Runner fixture:
  `finance_v26_privacy_safe_s1_runner_fixture:9cde2723360987aacef11bdacb1be7a7c5405ba1cad408cc843ccea58260794c`;
- Runner controls:
  `finance_v26_privacy_safe_s1_runner_control_audit:da6525e3d610a4c734332edfdd2b27d4b663cbaf4c7ffb6da23fa2be4e80a00d`;
- destructive audit:
  `finance_v26_privacy_safe_s1_destructive:61fe644a105e507b54843659133c42306b8287fa02f5352d94472e216cced59c`;
- prospective execution:
  `finance_v26_privacy_safe_s1_qualification_execution:e7a530dbabdeda98f707d8bb36da0e54af1cdf5b7ea2706a35f8e251ef953738`;
- prospective report:
  `finance_v26_privacy_safe_s1_qualification_execution_report:43e0915a0dbac37838040c24bbe5dcb3f344df6b19905a9eef1930bb927147eb`;
- transition:
  `finance_v26_privacy_safe_s1_transition:c28fd435b662b42b8d5f58e4f7157d1272e86c92fa3f3b280c7d2451f1f13636`.

## Validation

Focused v26.137 Pytest passes 2/2 in 101.12 seconds, including an independent complete build and
byte comparison of all sixteen formal files. The adjacent v26.136-v26.137 regression passes 4/4
in 143.40 seconds. Focused Ruff and Mypy pass. Package-wide Mypy checks 454 source files and
retains only the three pre-existing v26.70/v26.129 diagnostics, with zero v26.137 diagnostics. No
local GPU job ran.

## Decision

The only permitted transition is:

```text
privacy_safe_s1_representation_qualification_execution_only
```

The successor may execute only the exact fresh 32-Job engineering Manifest under the exact v2
Prompt, Runner, Resource, Qualification, and Outcome Contracts. It must replay the complete
v26.137 chain before credential lookup or client construction. Provider calls are authorized only
for that exact denominator.

This preflight is static Prompt/privacy compatibility and Runner-Instrument evidence. It is not an
online Flash result, empirical proof that the lexical hazard caused the v26.134 rejection, formal
S1 qualification, role-scale readability, Capability, Reachability, or State Mapping evidence.

Role Provider calls; Capability or Reachability execution; State Mapping; v26.134 rerun or
recovery; historical reclassification; rejected-content inference; classifier, Action/Final
Grammar, Candidate, S1, model, Thinking, resource, recovery, or Detour changes; Alias handling;
output repair; training; release; and production Contribution remain forbidden.
