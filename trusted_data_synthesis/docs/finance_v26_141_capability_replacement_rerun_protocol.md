# Finance v26.141 Capability Replacement Rerun Protocol

Date: 2026-08-24

## Decision

This stage performs the operator-authorized replacement rerun requested after the first v26.141
process lost its entire temporary worktree and execution directory. The replacement uses the
exact v26.140 96-Job Capability Manifest and the exact frozen v2 S1 execution surface. It writes
all formal files directly under the canonical persistent artifact root.

This is not represented as a pristine first-exposure denominator. The twelve Capability sources
were model-unexposed at the v26.140 freeze, but an earlier process may have exposed a subset before
its temporary storage disappeared. No artifact from that process survives in the canonical Git
tree or canonical artifact root. Consequently:

- the unavailable process contributes zero auditable Jobs and zero empirical rows;
- no observed console count or transient diagnostic is imported;
- no prior response, Usage value, terminal, or Provider-call count is reconstructed;
- no unavailable row is pooled with the replacement denominator;
- the replacement report must carry `pristine_first_exposure_claimed=false`;
- interpretation is limited to the exact operator-authorized replacement denominator.

The replacement does not alter or reinterpret v26.140. It is an explicit operational override of
the one-exposure condition, not a claim that the earlier process never contacted the Provider.

## Frozen Inputs

The replacement must bind the exact v26.140 identities:

- preflight report:
  `finance_v26_privacy_safe_capability_preflight_report:9e74e45831e0c8db50dc5969f680f81732b1ad71d9edd771fcfd40c496bce1f4`;
- TaskPackage catalog:
  `finance_v26_privacy_safe_capability_task_catalog:8ed09b94a9d5adbbc53481698def5fbc9cffc4d9969598c2409919ddd306cb82`;
- Path catalog:
  `finance_v26_privacy_safe_capability_path_catalog:eae754107fb5dda4b61e9236aeabd191b1a129a2c91df52023bce44745e6f0a7`;
- execution Contract:
  `finance_v26_privacy_safe_capability_execution_contract:e0d40a58cdf970c5842a65a8808147fee5494f46857d4f4f121f1b7b2d44cc10`;
- Manifest:
  `finance_v26_privacy_safe_capability_manifest:971a74faf28d07402aa90a31ec202644f617410e4a49ec7f25e5a265458b1301`;
- outcome Contract:
  `finance_v26_privacy_safe_capability_outcome_contract:a9cfe6d9fe21c26652fb01b75655aa119f50a992d40a93620db5832512d86162`;
- Runner Contract:
  `finance_v26_privacy_safe_capability_runner_contract:e080bd0622b653e73b67a834aefe8b10f54ecf06e95334d574038c21d88ca35d`;
- prospective execution:
  `finance_v26_privacy_safe_s1_capability_execution:d1925103511060775b84b546c2d149926602b6eef249c50e3e57a1bc526f9c4a`.

The denominator remains twelve tasks, eight unconditional replicas per task, 96 preserved seeds,
and all twelve Mechanism x Tier cells. Reachability identity creation, Reachability execution,
State Mapping, Host repair, task deletion, threshold changes, protocol changes, and Stage 2
Provider calls remain zero.

## Unchanged Execution Surface

The replacement preserves:

- exact `deepseek-v4-flash`;
- `thinking.type=enabled` and the frozen 16K Stage 1 profile;
- `prospective_role_scalable_semantic_action_prompt.v2`;
- the exact four-field Action Grammar and two-field Final Grammar;
- the unchanged privacy classifier and privacy-first Envelope/Projection order;
- complete Candidate authority and presentation, including states with up to 63 Candidates;
- one independent ABI Rescue, Semantic Recovery, Transport replacement, and Ordinary Detour;
- 60,000 Prompt bytes, 21 Primary requests, 23 Stage 1 Provider calls, 24 transport-inclusive
  invocations, and 1,120,000 Provider-reported tokens per Job;
- deterministic zero-Provider Stage 2 Commit;
- task-primary and rollout-secondary Capability summaries;
- independent postrun audit before any successor authorization.

## Durable Execution

Formal output is written only to:

```text
/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis/artifacts/vtdo_experiment/finance_v26_141_privacy_safe_s1_capability_execution_v1_20260824
```

No formal execution file may depend on `/tmp`. Before credential lookup, the runner:

1. replays all 4,535 v26.140 transitive source files;
2. verifies all seventeen v26.140 formal outputs;
3. binds the committed v26.141 implementation;
4. independently rebuilds the seventeen v26.140 outputs byte for byte;
5. verifies all 96 Job, TaskPackage, Manifest, Contract, model, Thinking, resource, and Runner
   bindings;
6. writes the replacement-rerun provenance and frozen inputs to the durable output directory.

`--prepare-only` constructs no real client and makes zero Provider calls. The execution source and
this protocol are committed before online execution.

## Recovery And Concurrency

Each complete Raw Execution is immutable and eligible only for zero-client reprojection. A Job
with Provider artifacts but no complete Raw is an orphan and is never retried. A complete report
resumes with zero client construction and zero calls.

The executor drains every submitted Future even if one Future raises. Successful results continue
to update the canonical checkpoint. After all Futures finish, only Jobs with an already persisted
complete Raw may be reprojected with `client=None`. Missing-Raw or repeated projection failures
fail the process after all recoverable checkpoints have been written. Exception details and
invalid payload content are not persisted by this mechanism.

## Measurement And Gate

The report keeps separate counts for Instrument eligibility, privacy compliance, Action Entry,
reversible Commit, public progress, Program closure, terminal verification, Final ABI, emitted
answer, semantic validity, mechanism success, and independently valid complete trajectory.

The frozen prospective Capability Gate requires:

- all 96 complete Raw Executions;
- at least one independently valid trajectory in each of the four mechanisms;
- zero combined Instrument, privacy, exact-model, Thinking, or Usage failures;
- zero typed budget no-call, Provider transport, or second-Detour support exits.

Model-invalid trajectories remain model outcomes. Final ABI and answer validity remain separate.
Passing the Gate still authorizes no Reachability execution until an independent postrun audit
reconstructs the full replacement denominator.

## Pre-Run Status

The recovered online implementation passes focused Ruff, Mypy, and Python compilation. The
focused Pytest regression passes 2/2 in 698.56 seconds. It exercises exact source binding,
explicit replacement provenance, all 96 scripted Jobs, 984 local calls, 888 Action choices, 792
public Observations, 63-Candidate diagnostics, and zero-client completed-run replay. Online
results will be added only after the persistent execution directory closes and the independent
audit completes.

## Replacement Execution Outcome

The committed source at Git commit `fb65a8d` completed its credential-free replay and started from
`0/96` with zero Raw recovery and eight workers. The executor drained all 96 submitted Futures.
Ninety-three Jobs produced complete immutable Raw Executions and checkpoint rows. Three Jobs
raised a Host `ValueError` after their first persisted Provider artifact triple and before Raw
persistence. The runner did not retry those Jobs and generated no completed report.

The durable directory contains 858 Provider Envelopes, 858 public Projections, and 858 Transport
certificates. All 858 calls were HTTP success and requested, selected, and returned exact
`deepseek-v4-flash`. Artifact-backed Usage is 8,042,572 tokens: 4,211,294 Prompt, 3,831,278
Completion, and 3,699,772 Reasoning tokens. Estimated cost telemetry is USD
`1.28198986720000011600`. The Projection partition is 851 validated public payloads, seven
generic Provider-failure no-payload rows, and zero privacy rejections. Maximum complete-Raw Prompt
size is 49,504 bytes and maximum complete-Raw Job Usage is 223,783 tokens.

The 93 complete Raw results contain seventeen `model_valid_trajectory` and 76
`model_invalid_trajectory` terminals. Ninety-two cross the first Action interface. At least one
independently valid complete trajectory occurs in each of the four mechanisms. The Ordinary
Detour partition is 92 zero and one single-Detour Job. These are descriptive values over the
complete-Raw subset, not a completed exact-denominator Capability estimate.

The three orphan Jobs are Failure Recovery rows:

- Easy, replicate 2, Job suffix `e3ac0be4a8a1`;
- Easy, replicate 4, Job suffix `9b354e7884df`;
- Hard, replicate 0, Job suffix `ef32ef59e0f7`.

Each orphan contains only `call_000` Envelope, public Projection, and Transport certificate. Each
call is exact-model HTTP success with complete Thinking and Usage telemetry and an exact
privacy-compliant four-field Action payload. No Raw, checkpoint row, second invocation, invalid
payload content, private reasoning content or hash, Raw HTTP body, or Raw request body exists for
any orphan.

A zero-call staged diagnostic independently reconstructs each initial State and exact public
payload. All three parse, select a visible Candidate with matching Decision kind, compile a
reversible `query_structured_fact` Commit, execute a public Observation, rebuild the successor
State, construct the Commit and Choice records, compute Progress, render and decode the successor
v2 Prompt, preserve exact State and Candidate order, and retain zero classifier-sensitive Keys.
All three then fail at the same successor-only diagnostic call:

```text
prompt_only_reference_proposal
ValueError: Prompt-only acquisition policy cannot satisfy its public route
```

The reference Proposal is a Host-side Ordinary Detour classifier. It neither selected nor repaired
the model Action. Treating its unavailability as an uncaught exception after a persisted model
result is an Instrument defect. The strongest current root-cause statement is
`dynamic_successor_reference_policy_unavailable_not_typed_as_measurement_support_exit`. This is a
reproduced prospective localization, not a reconstructed Raw terminal for any orphan.

The exact 96-Job Capability Gate fails because complete Raw count is 93/96 and the three missing
rows cannot be pooled, inferred, or relabeled. The only defensible next transition is a zero-call
independent failed-lineage audit and, only if that audit closes, a fresh orphan-only recovery
preflight that converts reference-policy unavailability into a typed measurement-support exit
without changing the model Action, public Observation, S1, Candidate authority, model, Thinking,
resource bounds, or historical bytes. Reachability and State Mapping remain unauthorized.
