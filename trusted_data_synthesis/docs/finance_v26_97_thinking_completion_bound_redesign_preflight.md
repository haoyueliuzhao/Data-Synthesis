# Finance v26.97 Thinking Completion-Bound Redesign Preflight

Date: 2026-08-22

## Decision

Finance v26.97 completed the credential-free redesign authorized by the v26.96 failure audit:

```text
thinking_completion_bound_or_two_stage_protocol_redesign_only
```

The preflight passed. It prospectively selected an 8,192-token Completion candidate for one
future engineering calibration and registered a separate 16,384-token fallback candidate. It
materialized fresh TaskPackage, Contract, Manifest, Job, future-execution, and report identities
for the 8K candidate only. It did not implement an execution Runner, authorize execution, make a
model API call, construct a model client, or use a GPU.

The authoritative report is:

```text
finance_v26_completion_bound_preflight_report:09cfd5171d2cd29dd36ab51d5124900f513cbaac3a9fcd0f96aa0fdcb66d7486
```

The only permitted transition is:

```text
thinking_8k_completion_calibration_runner_and_preflight_only
```

## Evidence Boundary

The redesign binds the v26.96 result without changing it:

- 27 complete Raw Jobs were all `completion_unusable`;
- the formal lower bound of 27 failures already made the zero-failure Gate impossible;
- the exact 32-Job denominator was incomplete, so no exact-denominator interval is reported;
- 184 HTTP-success calls contained 444,089 Completion tokens and 433,062 reasoning tokens;
- the reasoning-token share was 97.5169391721%, or 9,751 basis points after flooring;
- 48 calls ended in reasoning-only length truncation and two in partial length truncation;
- another Prompt-only repair under the 4,096-token Completion bound is forbidden.

These observations select a Completion-bound change as the next protocol family. They do not
identify 8,192 or 16,384 as an empirically sufficient value. Semantic outcomes, local mechanism
successes, Program closure, and task validity do not select the bound.

v26.97 chooses 8,192 as the smallest preregistered geometric successor above the failed 4,096
bound. The 16,384 candidate is registered prospectively so that a later 8K length failure has a
predeclared interpretation. This is a design choice, not a claim that either value controls
Provider-private reasoning length.

## Source Replay

Before freezing the new design, the builder replayed 733 distinct files:

| Source class | Files |
| --- | ---: |
| v26.96 transitive source replay | 723 |
| v26.96 output files | 8 |
| v26.97 implementation files | 2 |
| **Total** | **733** |

Every expected and observed SHA-256 matched. The v26.96 report and prospective transition
Contract reparsed under their strong schemas and retained the exact permitted transition. Replay
occurred before design freeze and without credential lookup or client construction.

## Candidate Ladder

The content-addressed protocol is:

```text
prospective_thinking_completion_bound_protocol:178f682e29a7f8bb19ec7e5bba87b68ea2777ea37539fab007ead74456995b50
```

It contains exactly two ordered candidates:

| Rank | Candidate | Completion | Rollout | Materialized Jobs |
| ---: | --- | ---: | ---: | ---: |
| 1 | `prospective_completion_bound_candidate:f62cca7bf763864c8c1be10138afa68999b434a6110f16b711a5abedae6ae838` | 8,192 | 160,000 | 32 |
| 2 | `prospective_completion_bound_candidate:6dfb2358d92a7b1e39a8cf741033e43974dad1a77114d01533ef673115a59dc2` | 16,384 | 240,000 | 0 |

The Prompt ceiling remains 60,000 UTF-8 bytes. The chat envelope remains 256 tokens and the
static per-request margin remains 64 tokens. Every future Provider call must still request exact
`thinking.type=enabled`.

The future 8K calibration may not switch to 16K in the same run. A length or reasoning-only
failure at 8K may authorize only a fresh 16K Runner/preflight under new execution identities. A
non-length Completion failure instead requires a Completion-Contract root-cause audit. No
semantic result can trigger, suppress, or rescue bound escalation.

## Dynamic Rescue Closure

v26.97 replaces the historical relative 10% reduction Gate with a 6,144-byte absolute Rescue
Prompt ceiling. The relative Gate is retired rather than weakened: an actual Rescue must satisfy
the absolute bound before Provider invocation regardless of Primary Prompt size.

The renderer consumes the actual dynamic Primary Prompt, infers and validates its actual request
kind, and projects only the current public decision or terminal state. A decision Rescue may
retain:

- the current instruction and answer schema;
- the requested path;
- the currently ready Operation frontier and unresolved public variables;
- current semantic Progress;
- selected Evidence references and available compact fact summaries;
- one current pending-search result when present;
- the latest typed failure without failed arguments or earlier failure replay;
- currently allowed public tools;
- the action-neutral repair rule when a repair is active;
- terminal verification only when the terminal node is complete.

A final-answer Rescue retains the already admitted final Context, answer Observation, path, and
minimal answer response Contract. Both request kinds retain model tool, argument, and answer
choice.

The renderer excludes:

- the full transcript;
- superseded Operation replay;
- acquisition envelopes and stale search history;
- complete repeated-failure history and failed arguments;
- the previous Completion content;
- private reasoning content or hashes;
- Host-selected actions, expected arguments, Oracle fields, and target Evidence;
- raw HTTP bodies.

Every call must be certified before invocation. A Primary requires actual request-kind, actual
Primary Prompt, and resource certificates. A Rescue additionally requires an actual Rescue
Prompt certificate. The schema requires zero Provider calls before certificate construction.

The v26.96 root-cause state changes as follows under the new renderer:

| Prompt | UTF-8 bytes |
| --- | ---: |
| Historical dynamic Primary | 7,914 |
| Historical v26.95 Rescue | 7,176 |
| Prospective bounded Rescue | 3,888 |

This is deterministic local projection, not a new model response or evidence that the Provider
will emit usable content.

## Dynamic State Coverage

The preflight reconstructed two separate public-state sets:

| State source | States | Decision | Final answer |
| --- | ---: | ---: | ---: |
| v26.94 registered Compiler requests | 324 | 276 | 48 |
| v26.95 exposed Primary calls | 156 | 156 | 0 |
| **Total** | **480** | **432** | **48** |

Each state was rendered for all five frozen Completion failures, producing 2,400 Rescue
projections and 2,400 four-certificate fixtures. All passed the 6,144-byte ceiling. The largest
Compiler Rescue was 5,702 bytes; the largest historical off-Compiler Rescue was 5,626 bytes. The
global maximum was 5,702, leaving 442 bytes of frozen headroom.

The resource-certificate fixtures use zero cumulative Usage and zero future reserve to exercise
the certificate implementation. They do not establish online dynamic resource adequacy. The
future Runner must calculate actual cumulative Usage and all required remaining reserves before
each Provider call. The 48 complete static path audits provide a separate conservative path
qualification.

Compiler states and historical-state projections are implementation fixtures. They contribute
zero empirical Completion, Capability, Reachability, State Mapping, or release rows.

## Static Path Qualification

All 324 v26.94 registered Primary Prompts replayed to their exact hashes and byte lengths. The 48
paths retain five to nine post-Plan Primary requests and at most one Rescue. Candidate arithmetic
adds the actual Prompt byte upper bound, 256-token chat envelope, 64-token margin, candidate
Completion bound, and one worst-case Rescue.

| Diagnostic | 8K initial | 16K fallback |
| --- | ---: | ---: |
| Qualified paths | 48/48 | 48/48 |
| Full-path lower bound | 76,817 | 125,969 |
| Full-path upper bound | 151,653 | 233,573 |
| Minimum rollout headroom | 8,347 | 6,427 |
| Maximum Primary Prompt | 8,369 bytes | 8,369 bytes |
| Maximum Rescue Prompt | 5,702 bytes | 5,702 bytes |

The 160,000 and 240,000 rollout values are prospective ceilings selected to close these exact
static paths with positive headroom. They are not inferred from v26.95 observed Usage, expected
cost estimates, or trajectory-completion probabilities. Passing a static bound does not establish
online Budget Adequacy.

## Repeated Source Boundary

The successor requires fresh TaskPackage identities but no unexposed fresh source Population is
available under the current evidence boundary. v26.97 therefore deliberately rematerializes all
24 v26.94 engineering-calibration sources under fresh Completion-bound identities:

- all 24 source tasks overlap the v26.95 design;
- 22 source TaskPackages were model-exposed by at least one v26.95 Provider call;
- two source TaskPackages remained model-unexposed;
- the source tasks are explicitly not claimed fresh;
- all 24 new TaskPackage identities are fresh;
- all 32 new Job identities and seeds are fresh;
- no v26.95 Job is rerun, continued, recovered, or reclassified.

Repeated-source use is restricted to engineering Completion calibration. These tasks and every
future row under this Contract are permanently ineligible for Capability, Reachability, State
Mapping, State Support, or release evidence. v26.95 Completion outcomes selected the protocol
family, but neither v26.95 semantic outcomes nor Compiler outcomes selected tasks, paths, Jobs, or
seeds.

## Contract And Manifest

The fresh Contract is:

```text
finance_v26_completion_bound_contract:cf71fa07ae0be111c1e2843b14c1a8f6f3903371a365396da2c749217401ada4
```

The fresh 8K-only Manifest is:

```text
finance_v26_completion_bound_manifest:11b3bb1f686f52f6c673f5e59b30757104d1769aaec0bae51eba4c4f25dbbdae
```

The Manifest contains 32 distinct Jobs and 32 distinct seeds, covers all 24 TaskPackages, and
retains all twelve Mechanism x Path cells. Each mechanism has eight Jobs;
`structured_direct`, `search_then_structured`, and `search_then_open` have 12, 8, and 12 Jobs.
Each cell has two or three Jobs. Every Job binds 8,192 Completion tokens, 160,000 rollout tokens,
exact Thinking mode, and one maximum Rescue.

The inherited exact-denominator Gate remains zero-failure. At 32 Jobs, zero failures has a
one-sided 95% Clopper-Pearson upper bound of 0.08936819898626475, while one failure has an upper
bound of 0.139849460274226. Typed no-call, Completion-unusable, Provider transport, response
telemetry, exact-model, and Instrument outcomes remain separate. Semantic validity cannot rescue
any execution-integrity or Completion Gate.

## Prospective Interpretation

The future 8K result must follow this frozen decision tree:

1. Any typed no-call, transport, response-telemetry, exact-model, privacy, or Instrument failure
   blocks interpretation under its own failure class.
2. Any reasoning-only or partial length failure blocks 8K and may authorize only a fresh 16K
   Runner/preflight. The current 16K candidate does not authorize execution by itself.
3. Any non-length Completion failure permits only a Completion-Contract root-cause audit.
4. A fully complete exact denominator with zero Completion and execution failures may authorize
   only a Thinking role-protocol freeze.
5. If Completion passes but Program closure or semantic validity is low, Completion tuning stops.
   The behavior remains descriptive and the role protocol must use a fresh role Population.

This tree prevents semantic success from masking an unusable output channel and prevents
automatic bound escalation from consuming the same denominator.

## Destructive Controls

All 18 mutations failed closed:

- reintroducing a 4,096-token candidate;
- automatic same-run fallback;
- semantic-outcome bound selection;
- materializing fallback execution Jobs;
- a Rescue above the absolute byte ceiling;
- dynamic request-kind mismatch;
- Provider invocation before certificate construction;
- a missing Primary certificate;
- a missing resource certificate;
- one-token rollout overflow;
- previous-Completion injection;
- private-reasoning injection;
- claiming repeated sources fresh;
- relaxing the zero-failure Completion Gate;
- authorizing execution without a Runner;
- authorizing Capability execution;
- inserting a fallback Job;
- reusing a historical Job identity.

The destructive audit is:

```text
finance_v26_completion_bound_destructive:7ad5d1a110f88db8c83d31628b8e710a998f4a2441f9565f53e4b7ea9988e4b7
```

## Determinism And Validation

Formal and independent builds reproduced all twelve output files byte for byte. Both builds
replayed 733 files, produced 480 state rows and 2,400 local Rescue projections, made zero API
calls, constructed no model client, and used zero GPU jobs.

Validation at freeze:

```text
Ruff focused check: passed
Ruff repository-wide check: passed
Ruff format for all three new Python files: passed
Mypy focused source check: passed
Package-wide Mypy: 398 files checked; one retained v26.70 diagnostic
v26.97 focused tests: 8 passed
```

The full adjacent and repository-wide Pytest results are recorded in `current_project_status.md`
after canonical integration. No historical source-bound file was reformatted or modified.

## Interpretation And Next Stage

This is a positive static preflight for the minimum 8K Completion candidate and a separately
registered 16K fallback. It establishes:

- exact replay of the v26.96 authorization boundary;
- a fresh engineering identity chain without historical Job reuse;
- explicit disclosure that source tasks are repeated and mostly model-exposed;
- an absolute, mechanically enforced Rescue byte ceiling;
- pre-call request-kind, Primary, Rescue, and resource certificate implementations;
- local coverage of all registered Compiler states and all v26.95 Primary states;
- static budget feasibility for both candidate ceilings;
- a balanced 8K-only 32-Job Manifest.

It does not establish:

- empirical 8K or 16K Completion usability;
- control of Provider-private reasoning length;
- online Budget Adequacy under either new rollout ceiling;
- arbitrary future-state semantic coverage;
- a passing execution Runner;
- Program closure, Capability, Reachability, or State Support;
- a Thinking-enabled role protocol;
- production Contribution.

The next stage may only implement an exact 8K Runner and complete another credential-free
preflight. That Runner must replay this report, all eleven detail outputs, all 733 bound source
files, and its exact implementation before credential lookup. It must issue the actual dynamic
certificates before every Provider invocation and must never switch to 16K automatically.

Any change to the renderer, absolute Rescue ceiling, candidate ladder, TaskPackages, paths,
Contract, Manifest, Jobs, seeds, Thinking profile, response telemetry envelope, or resource
bounds requires a new preflight identity.

Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training,
Exact Target, GP-C, and Contribution remain forbidden. Production Contribution remains zero.

## Authoritative Artifacts

- `artifacts/vtdo_experiment/finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822/report.json`
- `artifacts/vtdo_experiment/finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822/source_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822/completion_bound_evidence_audit.json`
- `artifacts/vtdo_experiment/finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822/completion_bound_protocol.json`
- `artifacts/vtdo_experiment/finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822/source_exposure_audit.json`
- `artifacts/vtdo_experiment/finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822/completion_bound_task_packages.json`
- `artifacts/vtdo_experiment/finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822/dynamic_rescue_coverage_audit.json`
- `artifacts/vtdo_experiment/finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822/completion_bound_path_audits.json`
- `artifacts/vtdo_experiment/finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822/completion_bound_contract.json`
- `artifacts/vtdo_experiment/finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822/completion_bound_job_manifest.json`
- `artifacts/vtdo_experiment/finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822/completion_bound_freshness_audit.json`
- `artifacts/vtdo_experiment/finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822/destructive_preflight_audit.json`
