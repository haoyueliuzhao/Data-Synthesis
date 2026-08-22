# Finance v26.110-v26.111 Two-Stage Semantic Proposal Calibration Execution And Audit

Audit date: 2026-08-23

## Scope And Authorization

v26.110 consumed exactly the online transition authorized by the v26.109 Runner preflight:

```text
two_stage_semantic_proposal_calibration_execution_only
```

The execution used the frozen 32-Job v26.108 Manifest, all preserved Job assignments and seeds,
the exact `deepseek-v4-flash` Stage 1 profile with `thinking.type=enabled` and
`max_tokens=16384`, the 260,000-token rollout ceiling, one global Rescue, and the deterministic
zero-Provider Stage 2 compiler. It did not resample tasks, alter Prompts, change the profile or
resource bounds, reuse a v26.105 Job, or create a role, State Mapping, release, or production
denominator.

v26.111 is a separate credential-free independent audit. It made no model call and did not
reclassify a v26.110 terminal. Its purpose was to reproduce the exact execution lineage,
Provider telemetry, response-interface failures, Completion/Rescue partition, and Stage 2
authority boundary before permitting any repair.

## Preexecution Closure

The final v26.110 `--prepare-only` replay passed 1,911/1,911 files before credential lookup or
client construction:

- 1,900 transitive v26.109 source bindings;
- all ten v26.109 outputs;
- the exact v26.110 implementation source.

The source replay identity is
`finance_v26_two_stage_execution_source_replay:0f947f1cf99af08f1f17be70242a4182c0d0006e20f9f6e4314226ad694e441f`.
It constructed no real model client and made zero Provider calls.

A new computed preexecution validity audit addressed a claim-strength gap in v26.109. The
v26.109 direct control did verify compiler semantic projection, final answer equality, and
Verifier v3 Replay, but its top-level independent-validity and mechanism counts were defaults
rather than computed per-Job scores. v26.110 therefore reran all 32 scripted controls before any
credential access and actually calculated the missing rows. All 32 passed Verifier v3 Replay,
independent validity, and mechanism scoring; they contained 256 scripted Stage 1 calls, 224
reversible Stage 2 Commits, and zero real or Stage 2 Provider calls. The audit identity is
`finance_v26_preexecution_validity_audit:625434163b8129e9e29e248ee4a6b91d89904441654bd32e17831be546405424`.
This correction changes no v26.109 artifact and contributes zero empirical rows.

## v26.110 Online Execution

The online Runner started at 0/32 with eight workers, zero Raw-recovery Jobs, and no historical
Job rerun. All 32 Jobs completed and persisted one checkpoint row and one complete Raw Execution.
The aggregate contains 64 privacy-redacted Raw Provider artifacts, exactly two per Job: one
Primary and one Rescue.

Every call returned HTTP success from exact `deepseek-v4-flash`. Exact requested, selected, and
response model identity; Thinking telemetry; Usage; dynamic pre-call certificates; exact request
certificates; resource certificates; native-tool absence; fallback absence; and model-discovery
absence passed throughout. All actual Provider Usage was charged without clipping. There were no
typed no-calls, transport failures, Instrument failures, one-token accounting-margin calls, or
two-or-more-token excess calls.

Provider telemetry was:

| Metric | Primary | Rescue | Total |
| --- | ---: | ---: | ---: |
| Calls | 32 | 32 | 64 |
| Prompt tokens | 48,248 | 49,877 | 98,125 |
| Completion tokens | 177,998 | 463,957 | 641,955 |
| Reasoning tokens | 169,442 | 456,874 | 626,316 |
| Total tokens | 226,246 | 513,834 | 740,080 |
| Reasoning fraction | `0.951932044180` | `0.984733499010` | `0.975638479333` |
| Estimated cost telemetry | USD `0.0559970656000000044` | USD `0.1368907400000000156` | USD `0.1928878056000000200` |

Fifty calls ended with `finish_reason=stop`. Fourteen ended with `finish_reason=length`: thirteen
exact-bound reasoning-only failures at 16,384 Completion and reasoning tokens, and one
16,383-token response with public JSON that still failed the response contract. No call reported
16,385 or 16,386 or more Completion tokens.

## Exact Outcome Denominator

No Primary or Rescue response produced an accepted Stage 1 semantic proposal. The frozen terminal
denominator is:

| Terminal | Jobs |
| --- | ---: |
| `model_invalid_trajectory` | 20 |
| `completion_unusable` | 12 |
| `typed_budget_no_call` | 0 |
| `provider_transport_failure` | 0 |
| `instrument_failure` | 0 |

The Completion-unusable one-sided 95% Clopper-Pearson upper bound is
`0.5356393016383838`, so the zero-failure Completion Gate failed. The 64 attempts split exactly
as follows:

| Phase | Exact response-contract failure | Reasoning-only length failure | Usable |
| --- | ---: | ---: | ---: |
| Primary | 31 | 1 | 0 |
| Rescue | 20 | 12 | 0 |

All 32 Jobs consumed the single Rescue and none recovered. Rescue Prompts were larger than their
Primary in 32/32 Jobs: 31 increased by 202 UTF-8 bytes and the one channel-failure Rescue
increased by 189 bytes. Rescue Completion Usage was 2.61 times Primary Completion Usage and its
reasoning fraction increased from `0.951932044180` to `0.984733499010`. These observations do not
identify a better Completion bound. They show that the frozen Rescue did not function as a short
serialization correction under this response contract.

Program closure, mechanism success, independent validity, and requested-path adherence were all
0/32. Those zeros are not evidence of semantic incapability: every Job stopped before the first
accepted proposal, deterministic Stage 2 Commit, Tool Observation, or semantic compile attempt.
The correct semantic-behavior status is `unmeasured`.

## v26.111 Independent Reconstruction

v26.111 replayed 2,017/2,017 files before diagnostics:

- all 1,911 v26.110 bound source files;
- all 105 v26.110 execution files;
- the exact v26.111 implementation.

It reparsed all 32 checkpoint rows, 32 final results, 32 Raw Executions, 64 Raw Provider
artifacts, and 96 Raw descriptors under strong schemas. All 104 JSON files and all 32 canonical
JSONL rows reproduced. Descriptor hashes, result-to-Raw parents, Provider-to-Raw parents,
Provider telemetry, dynamic certificates, exact request certificates, and resource certificate
references all matched. Private reasoning content and hashes, raw HTTP bodies, and raw request
bodies remained absent.

Formal and independent builds reproduced all ten v26.111 outputs byte for byte. Focused tests
passed 4/4; focused Ruff format/check and focused Mypy passed. All 20 destructive mutations were
rejected with zero Provider calls. The canonical v26.103-v26.111 adjacent regression passed
55/55 in 90.10 seconds against the complete immutable artifact root.

## Response-Interface Root Cause

The 51 public JSON payloads had 46 distinct top-level key sets. None had the exact ten-field
payload shape and none passed `StageOneSemanticProposalPayload` validation. Their top-level field
coverage was:

| Field observation | Count |
| --- | ---: |
| `state_id` present | 2/51 |
| `decision_kind` present | 28/51 |
| `stage` present | 2/51 |
| `protocol` present | 1/51 |
| exact response protocol present | 0/51 |
| `tool_id` present | 7/51 |
| `direct_arguments` present | 0/51 |

The Primary split is particularly diagnostic: 31/31 visible Primary payloads omitted top-level
`state_id`; 28 selected `decision_kind=acquire_public_input`, while three omitted
`decision_kind`. The Rescue split is worse at the exact interface: all 20 visible Rescue payloads
omitted top-level `decision_kind`, and 18 omitted top-level `state_id`.

v26.111 independently regenerated every initial public state and reproduced all 32 Primary and
32 Rescue Prompt hashes and byte counts. The exact accepted response model has ten named fields:
`decision_kind`, `direct_arguments`, `evidence_ids`, `node_id`, `operand_sources`, `operator_id`,
`protocol`, `stage`, `state_id`, and `tool_id`. Both frozen model-visible `response_contract`
objects explicitly name only one of those exact fields: `stage`. The Primary contract does not
state the required `state_id` output binding, exact `protocol` field, conditional field rules,
null/empty defaults, or one-proposal top-level shape. Rescue exposes the response-protocol value
under a different outer key but likewise omits the exact output grammar.

This supports `exact_stage_one_response_grammar_not_model_visible` as the dominant prospective
engineering root cause for the observed interface failure. It is not claimed as the sole cause of
model behavior and does not validate any rejected payload semantically. Post-hoc alias
normalization or Host selection would violate the two-stage authority contract and is forbidden.

## Stage 2 And Evidence Boundary

Online Stage 2 Provider calls were exactly zero, as required. Online Stage 2 Commits were also
zero because no Stage 1 proposal crossed the boundary. Thus the positive scripted Stage 2
authority preflight remains intact, but its online reversible-Commit denominator is zero.
No semantic choice was inserted by the Host.

The 24 sources remain repeated engineering sources. v26.110 and v26.111 contribute zero
Capability, Reachability, State Mapping, State Support, release, or production rows. Production
Contribution remains zero.

## Authoritative Identities

- v26.110 report:
  `finance_v26_two_stage_execution_report:c1fe9d9dc947fb2d9ed1898b5f11f43174a1072a79a5b5d7b6515938d415834b`;
- v26.110 Raw Lineage:
  `finance_v26_two_stage_raw_lineage:519e8948f0d128891dcceb231ab25b5d0e6fb7c10c54016f4b92f88cbaedc951`;
- v26.111 report:
  `finance_v26_two_stage_postrun_audit_report:44cc58aae8ca49faeb7843d0cd77e8bc4824028f047d1d87b0e2f298be80339a`;
- response-interface audit:
  `finance_v26_two_stage_response_interface:f46ea841c3e38533c3686ca179f68de299cd6e3677f3f310b2459446ffaa784a`;
- Prompt-disclosure audit:
  `finance_v26_two_stage_prompt_disclosure:0ae330a2e31d5b72775383e54bfd4d0ecee1ba626f6dcb7ea4df8621de197778`;
- Completion/Rescue audit:
  `finance_v26_two_stage_completion_rescue:63454d470a9c33769524d03d773e0e0d9236c1aed0a0f384c1b135e178d3878c`;
- prospective transition:
  `finance_v26_two_stage_postrun_transition:6ae62c72a6f9023a1da40267c4515d0d23c8e833e919a4eb1285e84a0ab0c4bb`.

## Decision

The only permitted transition is:

```text
fresh_exact_response_grammar_taskpackage_contract_manifest_and_runner_preflight_only
```

The successor must expose the exact Stage 1 response field names, state binding, conditional
requirements, null/empty defaults, response protocol field, and one-proposal shape in both
Primary and Rescue. Rescue must request immediate schema-conformant serialization without reusing
the previous public response or private reasoning. The Host may not normalize aliases, choose a
Tool, fill semantic fields, or rescue an unavailable model choice.

The successor requires fresh response-protocol, Prompt, TaskPackage, Contract, Manifest, Job,
Runner, execution, and report identities and an exact credential-free Runner preflight before any
Provider call. It does not authorize a profile, model, Completion-bound, rollout-ceiling, or
Stage 2 Provider-route change. v26.110 may not be rerun or reclassified. Capability Development,
State Reachability, Fresh Confirmation, No-C VTDO, Student training, Exact Target, GP-C, and
production Contribution remain forbidden.
