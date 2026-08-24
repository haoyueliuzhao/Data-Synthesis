# Finance v26.136 S1 Privacy Compatibility Root-Cause Audit

Audit date: 2026-08-24

## Decision

Finance v26.136 consumed only the credential-free transition authorized by v26.135:

```text
s1_representation_root_cause_audit_only
```

The formal v26.134-v26.135 result remains unchanged:

```text
S1 representation Qualification = failed
```

The new audit separates that formal authorization result from its scientific interpretation. The
entry-quantity Gate passed at 31/32, all twelve Mechanism x Path Strategy cells had a qualified
entry, and Instrument integrity passed. Privacy compliance failed at 31/32 under the frozen zero-
failure policy, so overall authorization remains failed.

The audit finds no deterministic incompatibility between the exact four-field Action Grammar and
the frozen privacy classifier. It does find a narrower deterministic hazard: every frozen S1
Action Prompt contains two model-visible metadata keys that the same privacy classifier would
reject if they appeared in a public response:

```text
private_reasoning_reused
response_grammar.private_reasoning_content
```

This lexical overlap is established for all 972 regenerated Primary, ABI Rescue, and Semantic
Recovery Prompts. It is not a claim that the historical rejected response echoed either key. The
exact rejected payload and key remain intentionally absent, and the unique historical cause
remains unidentified.

The only permitted successor is:

```text
fresh_s1_privacy_safe_prompt_metadata_rematerialization_and_runner_preflight_only
```

## Scope And Source Replay

Before classifier or Prompt analysis, v26.136 replayed 3,873/3,873 files:

- all 3,864 transitive files bound by v26.135;
- all eight v26.135 output files;
- the exact v26.136 implementation.

The replay binds v26.135 report
`finance_v26_s1_qualification_postrun_audit_report:4d4ebc3600d44dd29e468f2f386a4fcb50565fa62a36e5da915d5b5002be4fcc`,
its exact SHA-256
`7c533813325c0703f5e646a93f911ab41a54a3c9f26b42d5f52d82603620c031`,
and transition
`finance_v26_s1_postrun_transition:08ed4da1a36805bf0d68f7fcae29d874e7f38023796b4e7f666fa154b66b2452`.

The stage looked up no credential, constructed no model client, made zero Provider or Stage 2
Provider calls, used zero GPU jobs, exposed zero role sources, and created zero empirical or State
Mapping rows. It did not recover, infer, hash, or persist the historical rejected payload or key.

## Gate Decomposition

The frozen overall Gate is a noncompensatory conjunction. v26.136 reports its components
separately without changing that conjunction:

```text
Entry quantity       31/32   passed
Cell coverage        12/12   passed
Instrument integrity 197/197 passed
Privacy compliance   31/32   failed
Overall authorization         failed
```

All 197 historical calls remain HTTP-success, exact-model, Thinking-complete, Usage-complete,
privacy-paired rows. Transport Replacement, typed budget no-call, Instrument terminal, and Stage
2 Provider-call counts remain zero.

The observed entry count is 31. Because the last public payload is absent by policy and is not
reclassified, the content-identifiable entry range remains `[31, 32]`. The 31 positive rows remain
strong descriptive evidence for the basic S1 Action entry surface on repeated engineering tasks.
They neither compensate for the privacy failure nor authorize role-scale readability.

## Classifier Type System

The exact frozen classifier was inspected from its bound source and exercised with 24 synthetic
cases. All 24 outcomes matched the independently registered expectations, with ten rejections and
fourteen acceptances.

Its exact behavior is:

- recursively inspect Mapping keys and Mapping/List/Tuple descendants;
- normalize each key with `casefold()`;
- reject when the normalized key contains the substring `reasoning`;
- exempt exactly `reasoning_content_present`, `reasoning_content_length`, and
  `reasoning_tokens`;
- do not scan scalar values;
- do not reject keys merely containing `analysis`, `thought`, `rationale`, `plan`, or `reason`.

Consequently, arbitrary business strings cannot trigger rejection as values, while any nested
Mapping key containing the non-whitelisted `reasoning` substring can. This is a type-system result,
not an inference about the omitted historical key.

## Grammar Compatibility

The exact Action response Grammar requires only these four top-level scalar-string fields:

```text
state_id
action_id
decision_kind
protocol
```

None of those field names matches the classifier predicate, and the classifier does not inspect
their string values. The audit therefore establishes the structural implication:

```text
exact Action Grammar valid => privacy classifier accepts
```

The reverse implication does not hold because privacy acceptance is intentionally broader than
the exact ABI.

The computed controls include:

- 16/16 synthetic legal payloads passing both Grammar and privacy classification;
- 141/141 immutable exact v26.134 Action payloads passing both;
- eight Grammar-neighborhood mutations;
- zero privacy-rejected, Grammar-valid mutations;
- four privacy-accepted, Grammar-invalid mutation classes.

No Action Grammar, Candidate, S1 projection, classifier, model, Thinking profile, resource bound,
or recovery count change is supported. The historical privacy row is not retroactively parsed or
reclassified.

## Prompt Compatibility

The audit regenerated all 324 registered S1 states under Primary, ABI Rescue, and Semantic
Recovery, producing 972 exact Prompts. All 972 matched the frozen hashes and byte counts,
reconstructed the exact state, and produced an intended exact four-field reference payload that
passed privacy classification.

The exact response prefixes and response-shape rules contain zero positive requests for analysis,
reasoning, rationale, thought, or plan. A broader scan finds 216 `plan` substrings in public task
or context values; these are not response-format instructions and scalar values are outside the
classifier predicate.

Nevertheless, all 972 model-visible Prompt payloads contain both classifier-sensitive metadata
keys listed above. As a deterministic control, classifying a full Prompt-payload echo rejects
972/972, while classifying the intended four-field response accepts 972/972. The Prompt explicitly
marks private reasoning content as not allowed and private reasoning reuse as false, so the result
is a lexical response-surface hazard, not a positive request for private reasoning.

The audit does not claim that the historical rejected response was a Prompt echo. Content hash,
length, and Usage cannot establish that causal attribution.

## Accepted-Row Boundary

The 31 accepted first-entry rows all have exactly the four required keys, four scalar-string
values, Mapping depth one, and a canonical payload size of 326 UTF-8 bytes. Provider public-content
length is 326-343 bytes with median 326.

Their first accepted phase partition is 26 Primary and five ABI Rescue rows. Candidate counts are
four for nine rows and six for 22 rows. All twelve Mechanism x Path Strategy cells are represented.

Eight local mutations were applied to each accepted payload, producing 248 zero-call boundary
controls:

```text
privacy rejected                 93
privacy accepted                155
Grammar accepted                 31
Grammar rejected                217
privacy rejected + Grammar valid  0
privacy accepted + Grammar invalid 124
```

The 31 historical rows remain byte-immutable and unmodified. These controls locate the public
interface boundary; they do not estimate or reconstruct the omitted row.

## Root-Cause Interpretation

The strongest supported interpretation is:

```text
S1 Entry quantity and coverage passed on repeated engineering tasks.
Instrument integrity passed.
Privacy-safe overall authorization failed.
The exact Action Grammar and privacy classifier are compatible.
The frozen model-visible Prompt has a deterministic classifier-sensitive metadata hazard.
The unique cause of the historical Privacy Rejection remains unidentified.
```

The audit does not claim any of the following:

- S1 is generally unreadable;
- S1 is role-scale readable;
- the classifier produced a historical false positive;
- the model leaked private reasoning;
- the historical response echoed the Prompt;
- the one rejected row may be removed, recovered, or reclassified.

Program closure 24/32, post-terminal verification 16/32, exact Final ABI 10/32, and independent
validity 9/32 remain descriptive trajectory outcomes. They are not part of the narrow Entry Gate
and are not Capability, Reachability, State Mapping, release, or production evidence.

## Validation

All sixteen destructive mutations failed closed. Formal and independent builds reproduced all ten
v26.136 output files byte for byte. Focused Pytest passed 2/2 in 45.78 seconds. The adjacent
v26.134-v26.136 regression passed 6/6 in 198.91 seconds. Focused Ruff and Mypy passed.

Package-wide Mypy checked 453 source files and retained only the three pre-existing diagnostics in
v26.70 and v26.129, with zero v26.136 diagnostics.

## Authoritative Identities

- report:
  `finance_v26_s1_privacy_root_cause_audit_report:5ac66c4c25b021406c49628c67aa06b6aa776c59550810d8cc7c9e06e1451b65`;
- source replay:
  `finance_v26_s1_root_cause_source_replay:73b74723dbe69790539112ad00f66db5574f3774ed0ca90c7146663a79386352`;
- classifier type-system audit:
  `finance_v26_privacy_classifier_type_system_audit:32f846dc58a1675fd1aeaf309ff6c152c9ad974674d6f5d513e35b573043039b`;
- Action Grammar/privacy compatibility:
  `finance_v26_action_grammar_privacy_compatibility:3fb0a2947cd134fc1ae212a4136bbbfe6b83bf4143f5079f764aa80aefdcbe4a`;
- Prompt/privacy compatibility:
  `finance_v26_s1_prompt_privacy_compatibility:75867629bcee4ff4f86ed6072b1faac379759559e015a510bf467aa14d25f1af`;
- accepted-entry boundary:
  `finance_v26_s1_accepted_entry_boundary_audit:a158d3888081b2035f208d93acc26ab6569d006dee556d20f368f92c72ef4f33`;
- Gate decomposition:
  `finance_v26_s1_qualification_gate_decomposition:bd47399403171f962acd6fcbb09af4bdb8d3480aacf6f2cf7bb4564fee995ac3`;
- root-cause decision:
  `finance_v26_s1_privacy_root_cause_decision:60054e8f265c13fb3f056403e3f053299a7dfc75f77720b178301f70634a4792`;
- destructive audit:
  `finance_v26_s1_privacy_root_cause_destructive:74e33d34d958da0db47d2e33c4eb76fc829dd2f55a8abf27aa3e1c966bb60cd5`;
- transition:
  `finance_v26_s1_privacy_root_cause_transition:a8ebfd89e76d2717c58577d6e08286b737ccd18b961832abad09ced217077b74`.

The report SHA-256 is
`282de86de46d76073e115af7fa5e1e772f59532bb4c3d08f0d68b95922907bfb`.

## Permitted Transition

The successor may only remove or rename the two classifier-sensitive model-visible Prompt metadata
keys while preserving their privacy prohibition semantics. It must retain the exact S1 projection,
Candidate authority and presentation, Action and Final Grammars, privacy classifier, model and
Thinking profile, Completion and rollout bounds, recovery channels, Ordinary Detour allowance,
and zero-Provider Stage 2.

Any model-visible Prompt change requires fresh Prompt, TaskPackage, Path, Contract, Manifest, Job,
Runner, execution, and report identities plus a complete credential-free Runner preflight before
any Provider call. Future reports must keep Entry, Privacy, Instrument, and overall authorization
separate while preserving the noncompensatory Privacy Gate.

Provider calls, v26.134 rerun or recovery, historical reclassification, role Provider calls,
Capability or Reachability execution, State Mapping, classifier relaxation, training, release,
and production Contribution remain forbidden.


## v26.137 Successor Clarification

The credential-free transition above has now been consumed by v26.137. The v26.136 classifier,
Grammar, Prompt-hazard, accepted-boundary, Gate, historical-causality, and transition artifacts
remain immutable.

v26.137 replaces only the two classifier-sensitive model-visible metadata Keys under one fresh
strong Prompt Schema, retains the privacy prohibition as a scalar instruction, and rematerializes
fresh Prompt, 24-TaskPackage, 48-Path, two-Contract, 32-Job, Manifest, Runner, execution, and
report identities. Across 972 new Action Prompts the classifier-sensitive Key count is zero, full
Prompt-payload echo has zero privacy rejections, and exact State, Candidate order, reference
Proposal, Action Grammar, and Stage 2 Commit are preserved in 972/972 cases.

Its 32-Job scripted Runner fixture completes in 256 local calls; all 17 controls and 28 destructive
mutations pass with zero real Provider calls and zero Stage 2 Provider calls. This is a positive
credential-free preflight, not evidence that the repaired Keys caused the historical rejection or
that S1 has now passed empirical qualification.

The current transition is:

```text
privacy_safe_s1_representation_qualification_execution_only
```

Only the exact fresh v26.137 32-Job engineering Manifest may be executed. Role Provider calls,
Capability, Reachability, State Mapping, historical rerun or reclassification, classifier or
Grammar relaxation, output repair, training, release, and production Contribution remain
forbidden. See
`docs/finance_v26_137_s1_privacy_safe_prompt_metadata_and_runner_preflight.md`.
