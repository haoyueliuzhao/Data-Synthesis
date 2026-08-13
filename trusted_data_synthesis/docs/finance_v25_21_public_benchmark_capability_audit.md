# Finance v25.21 Public Benchmark Capability Audit

Audit date: 2026-08-13

## 1. Decision

v25.21 turns the v25.20 information-geometry failure into a typed task-mechanism redesign. It also
adds a deterministic public-benchmark audit, while keeping every public question and answer outside
the synthesis and training surfaces.

```text
v25.20 qualified Runtime + failed information geometry
  -> frozen financial benchmark statistics
  -> aggregate Agent benchmark design references
  -> seven-axis capability gap map
  -> seven irreducible Finance mechanisms
  -> Easy / Bridge / Frontier / Hard population contract
```

The audit passed, but no v25.21 task population has been materialized. The only permitted next
stage is:

```text
finance_v25_21_mechanism_population_construction_only
```

Pro, Beneficiary screening, Exact Target, GP-C, Contribution, VTDO updates, and Student training
remain forbidden.

## 2. Benchmark Isolation

Two different public-data roles are enforced.

### Frozen financial evaluation snapshots

FinQA and TAT-QA are read item by item only to compute aggregate structural statistics. Their
questions, answers, contexts, programs, and evidence text are never emitted by the audit.

```text
usage = evaluation_statistics_only
synthesis_access = forbidden
training_access = forbidden
paraphrase_access = forbidden
task_content_export = forbidden
```

Snapshot SHA-256, source revision, source blob, split, adapter version, metric version, and exact
denominator are all validated before statistics are computed.

A post-run scan compared all 2,810 frozen question strings with every emitted artifact and found
zero collisions. The serialized artifacts also contain none of the `question`, `answer`, `prompt`,
`program`, or `context` content keys.

### Public Agent benchmark references

GAIA, BFCL V4, WebArena, SWE-bench, and AgentBench are represented only by published aggregate
counts and interaction-design metadata. No task snapshot was loaded. In particular, benchmark
questions are not used as templates, few-shot examples, paraphrase sources, synthesis seeds, or
training records.

This distinction matters: the project transfers interaction mechanisms, not benchmark content.

## 3. Financial Benchmark Statistics

The complete frozen evaluation population contains 2,810 examples.

| Benchmark | Items | Structural signatures | Max signature share | Normalized entropy |
| --- | ---: | ---: | ---: | ---: |
| FinQA | 1,147 | 51 | 32.00% | 0.5883 |
| TAT-QA | 1,663 | 66 | 20.32% | 0.7315 |

### FinQA

| Signal | Count | Share |
| --- | ---: | ---: |
| At least two operations | 493 | 42.98% |
| At least three operations | 84 | 7.32% |
| At least two annotated evidence items | 579 | 50.48% |
| Table and text evidence | 158 | 13.78% |
| Explicit comparison operator | 20 | 1.74% |

Program depth is distributed as follows:

| Depth | Count |
| ---: | ---: |
| 1 | 654 |
| 2 | 409 |
| 3 | 55 |
| 4 | 10 |
| 5 | 19 |

The released programs contain 1,713 arithmetic operations, 39 table aggregations, and 20 explicit
comparisons. This is useful evidence for dependent financial calculation design. It is not evidence
of tool planning, recovery, or state-dependent stopping because the report context is already
provided.

### TAT-QA

| Signal | Count | Share |
| --- | ---: | ---: |
| Arithmetic answer | 699 | 42.03% |
| Multi-span answer | 210 | 12.63% |
| Table and text answer source | 546 | 32.83% |
| Explicit comparison annotation | 93 | 5.59% |
| At least two annotated facts | 913 | 54.90% |

TAT-QA contains 714 span, 699 arithmetic, 210 multi-span, and 40 count answers. Scale annotations
are present for thousand, million, and percent outputs. These structures inform semantic alignment
and output-contract construction, but they still use static evidence-given evaluation rather than
interactive reconciliation.

## 4. Public Agent Benchmark Design Statistics

The aggregate reference manifest is pinned at
`benchmarks/manifests/v25_21_public_agent_design_references.json`.

| Benchmark | Published population statistic | Design feature reused |
| --- | ---: | --- |
| GAIA | 466 questions | Open multi-tool investigation with objective answers |
| BFCL V4 | 100 web-search questions | Typed function selection, arguments, multi-turn repair |
| WebArena | 812 tasks | Stateful action-observation dependencies and functional checks |
| SWE-bench | 2,294 full instances | Independent verification and iterative repair |
| AgentBench | 8 environments | Multi-environment feedback, decision, and stopping |

The BFCL count is deliberately scoped to its published 100-question web-search component; it is
not presented as the total size of the evolving V4 suite. The manifest separately records the
200-entry format-sensitivity sample and its 2,351-entry source pool.

Official references:

- GAIA: <https://arxiv.org/abs/2311.12983>
- BFCL V4: <https://gorilla.cs.berkeley.edu/leaderboard.html>
- WebArena: <https://webarena.dev/>
- SWE-bench: <https://www.swebench.com/original.html>
- AgentBench: <https://github.com/THUDM/AgentBench>

## 5. v25.20 Gap Map

The audit reads the immutable v25.20 report instead of copying response rates into code.

| New axis | Scripted | Autonomous | Diagnosis |
| --- | ---: | ---: | --- |
| Information Acquisition | 100.00% | 100.00% | Saturated ceiling |
| Tool Planning | Host controlled | 51.43% | Autonomous boundary only |
| Compositional Reasoning | 77.60% | 98.29% | Autonomous ceiling |
| Semantic Alignment | 80.80% | 0.00% | Runtime-dependent split and Autonomous floor |
| Verification | 52.00% | 67.43% | Boundary but coupled |
| Recovery | 31.67% | 28.00% | Sparse opportunity support |
| Control / Stopping | Host controlled | 67.43% | Autonomous boundary but coupled |

This confirms that another entity/year resample or another replica increase would not address the
problem. The next population must change irreducible Evidence, Program, failure, and stopping
dependencies.

## 6. Seven Mechanisms

Each mechanism owns one primary capability axis and may expose secondary axes. Every mechanism
defines required structure, forbidden shortcuts, and observable outcomes.

1. `finance.disambiguating_information_acquisition`
2. `finance.typed_tool_plan_and_argument_recovery`
3. `finance.dependent_compositional_calculation`
4. `finance.bridge_semantic_alignment`
5. `finance.candidate_verification_and_repair`
6. `finance.cross_family_failure_recovery`
7. `finance.state_dependent_control_and_stopping`

Important changes from v25.20 include:

- Retrieval now requires plausible competing paths and a true join.
- Calculation requires at least three dependent operations and prior normalization.
- Reconciliation contains a resolvable Bridge between trivial compatibility and total conflict.
- Verification starts from an untrusted candidate and requires independent localized repair.
- Recovery opportunities occur across at least three primary families.
- Stopping depends on a public completeness invariant, not a fixed action count.

## 7. Population Contract

The Development population is preregistered before observing any new model response.

| Item | Contract |
| --- | ---: |
| Mechanisms | 7 |
| Tiers | Easy, Bridge, Frontier, Hard |
| Groups per mechanism | 12 |
| Easy / Bridge / Frontier / Hard groups | 2 / 4 / 4 / 2 |
| Minimum Development matched groups | 84 |
| Fresh Confirmation groups per mechanism | 5 |
| Replicas per Confirmation task | 5 |

Bridge is mandatory because v25.20 showed that Easy-compatible and Hard-incompatible cases alone
produce an Autonomous Semantic Alignment floor. Development and Confirmation must be disjoint on
Task, Group, Evidence, Evidence Version, core semantic signature, task signature, and the new
mechanism signature.

The existing Workflow Information thresholds are content-hashed into the population contract and
cannot be relaxed by this redesign. Correctness remains an observed model response rather than a
Runtime qualification gate.

## 8. Experimental Sequence

```text
Stage A: materialize 84 Development matched groups
Stage B: deterministic structure and shortcut audit
Stage C: Flash-only Development localization
Stage D: freeze mechanism/tier schedule without Confirmation access
Stage E: build disjoint five-group Confirmation population
Stage F: run Flash Runtime and information geometry
Stage G: authorize sparse Pro anchors only if both Runtime cells pass
```

The public benchmark audit does not itself authorize Stage C. First, every mechanism must prove
that its required dependency is executable and that each prohibited shortcut fails a mutation
test.

## 9. Results And Non-claims

The current result is:

```text
audit_passed = true
experiment_readiness = design_ready_population_not_materialized
model_api_calls = 0
gpu_jobs = 0
pro_api_calls_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
```

It supports the claim that the v25.20 response bottlenecks have been converted into an auditable
mechanism-level population contract. It does not yet support a claim that those mechanisms are
constructible at the required scale, fall on Flash's capability boundary, improve information
geometry, or produce meaningful Contribution effects.

## 10. Immutable Artifact

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/vtdo_experiment/
  finance_v25_21_public_benchmark_capability_audit_v1_20260813/
    public_benchmark_capability_audit.json
    public_benchmark_capability_audit.md
    v25_21_capability_mechanism_gap_manifest.json
```

Final audit ID:

```text
finance_public_benchmark_capability_audit:
9ab669a92fca1955c7960514b07cca69e42c745c8ca16da4040d690ceb962493
```
