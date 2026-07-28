# v0.8 Refinement Report

> Historical refinement snapshot. Superseded by `docs/v08_audit_remediation_report.md`.

## Scope

This change refines v0.8 only. It does not introduce a v0.9 namespace, schema release, or claim of
training utility. The work follows the five priorities in the v0.8 audit: repair the real-Agent
protocol, establish three-domain candidate capacity, make D1-D5 executable, preserve quality-aware
selection, and prepare Qwen3-8B training.

## 1. Program Skeleton and Execution Trace

The public Task Program is now explicitly a **Program Skeleton**. It states which operations are
required, their dependencies, parameters, and output schema; it is not evidence that a model ran
those operations.

The model must return `agent_response.v2`, containing an independent
`agent_execution_trace.v1`:

```json
{
  "execution_trace": {
    "trace_version": "agent_execution_trace.v1",
    "steps": [
      {
        "execution_id": "exec_01",
        "planned_node_id": "operation_node_01",
        "operator_id": "lookup",
        "tool_name": "evidence.lookup",
        "input_refs": ["evidence:evidence_01"],
        "evidence_ids": ["evidence_01"],
        "observation": {"result": {}},
        "status": "succeeded"
      }
    ],
    "output_execution_id": "exec_01"
  }
}
```

Execution identities must be fresh and topologically valid. Copying a Program node ID into
`execution_id`, inventing an Evidence reference, or returning an output identity outside the trace
fails the response contract. PLAN_HIDDEN cannot claim planned-node identity. The normalizer keeps
the model report but does not fill missing semantic content or execute a node for the model.

Prompt v3 communicates four non-negotiable rules:

1. the public DAG is a specification, not an execution log;
2. each operation requires a concrete tool and direct inputs;
3. observations and results must come from the reported execution;
4. the final answer must bind to the trace output.

## 2. Independent Execution Metrics

The Candidate Verifier computes per-node status from the normalized trajectory and Program
contract. The model does not provide these scores.

| Metric | Definition | Current hard gate |
| --- | --- | ---: |
| Execution Coverage | executed required nodes / required nodes | 1.0 |
| Operation Grounding | independently grounded required operations / required nodes | 1.0 |
| Tool Necessity | required operations with admissible concrete tools, plus required search action | 1.0 |

Grounding checks operator identity, direct Evidence and dependency references, parameters,
topological order, output binding, reported status, tool binding, and independently replayed result.
The three checks are part of the compiled sample-specific Quality Contract and required-check
manifest. Missing checks fail closed.

Training Utility evaluation now reports these metrics separately from strict JSON-contract success,
answer correctness, citation correctness, and end-to-end correctness. Execution IDs are normalized
before comparing plans, so fresh valid identities do not create false failures.

## 3. Three-domain Real-Agent Capacity

The profile `config/deepseek_v4_pro_agent_v08_capacity.json` freezes:

| Domain | Target tasks |
| --- | ---: |
| Finance | 1,000 |
| Legal | 200 |
| Science | 200 |

The new `audit-agent-capacity` command materializes task identities without calling a model. The
checked-in preflight reports:

| Item | Result |
| --- | ---: |
| Target tasks | 1,400 |
| Materialized tasks | 1,400 |
| Unique tasks | 1,400 |
| Agent API-call floor | 1,400 |
| Critic API-call ceiling | 600 |
| Blocking capacity defects | 0 |

The audit hash-binds the config and fixture manifest. It verifies orchestration capacity only. It
does not claim that 1,400 DeepSeek candidates have been generated or accepted.

## 4. D1-D5 Training Utility

The five cohorts keep a fixed model, optimizer budget, task pool, domain mix, and hidden evaluation
set:

| Cohort | Data policy |
| --- | --- |
| D1 | unfiltered real candidates mixed with typed-counterfactual wrong responses |
| D2 | deterministic Reference Workflow responses |
| D3 | real candidates accepted by the authoritative Quality Contract |
| D4 | accepted responses plus typed-counterfactual repair supervision |
| D5 | Contract-accepted candidates ranked within domain by the advisory Quality Critic |

D1 remains an intentionally noisy baseline; an erroneous counterfactual can be a D1 target. D4
never learns the wrong response as its target. D5 cannot rescue a Contract rejection, and an
unreviewed accepted sample receives a neutral Critic prior rather than a perfect score.

Capacity bounds now support the intended v0.8 scale. Malformed counterfactual responses are
excluded deterministically instead of breaking cohort preparation. Readiness still fails closed if
any D1-D5 source pool cannot fill its exact per-domain quota or if training/evaluation identities
overlap.

## 5. Qwen3-8B Profile

`config/training_utility_v08_qwen3_8b.json` defines the current expansion experiment:

| Item | Value |
| --- | ---: |
| Base model | Qwen/Qwen3-8B |
| Records per D1-D5 cohort | 600 |
| Records per domain per cohort | 200 |
| Hidden evaluation tasks | 150 |
| Hidden tasks per domain | 50 |
| Maximum training steps | 600 |
| Context limit | 8,192 |

The offline D2 preflight successfully materialized 600 balanced reference records and 150 balanced
evaluation records. Training/evaluation overlap is zero. The model revision is intentionally not
pretended to be frozen: it must be resolved from the actual model artifact before a real run.
Qwen3-specific token lengths must also be measured before training.

## 6. Quality-aware Selection

Selection remains inside v0.8 and preserves the existing authority boundary:

```text
Quality Contract hard gates
  -> accepted candidate pool
  -> within-domain Quality Critic ranking
  -> deterministic quota fill
  -> D5 cohort manifest
```

The Critic is advisory. It may order candidates that already passed deterministic checks; it cannot
supply missing Evidence, repair an execution trace, override a failed gate, or act as a human label.
Every selected identity remains content-addressed.

## 7. Verification

Run date: 2026-07-27.

| Check | Result |
| --- | ---: |
| Full Pytest suite | 93 passed |
| Ruff | passed |
| Mypy | passed, 155 source files |
| Finance/Legal/Science capacity | 1,000 / 200 / 200 |
| D2 reference cohort | 600, balanced 200 / 200 / 200 |
| Hidden evaluation set | 150, balanced 50 / 50 / 50 |
| Train/evaluation overlap | 0 |

Regression coverage includes valid Prompt-v3 traces, skeleton-copy rejection, invalid execution
references, independent metric computation, Quality Contract hard gates, Training Utility scoring,
domain-specific capacity auditing, and clean Finance lineage.

## 8. Execution Boundary

The following work was **not** executed and no result is claimed:

- 1,400 credentialed DeepSeek V4 Pro Agent calls;
- up to 600 DeepSeek Quality Critic calls;
- complete D1, D3, D4, or D5 materialization from real candidates;
- five Qwen3-8B LoRA SFT jobs;
- D0-D5 hidden evaluation and utility comparison.

At validation time, `DEEPSEEK_API_KEY` was not present in the process environment. The available
GPU had insufficient free memory for a responsible Qwen3-8B training launch alongside existing
workloads. The implementation therefore stopped after deterministic offline preflight rather than
mislabeling prepared data as a completed experiment.

## 9. v0.8 Acceptance

v0.8 now satisfies the protocol and capacity prerequisites in the audit's first two priorities and
provides executable contracts for priorities three through five. The next valid action remains an
experiment within v0.8: securely inject the provider credential, generate the frozen candidate
pool, pass D1-D5 readiness, resolve and freeze the Qwen3 artifact, train identical cohorts, and
publish held-out utility metrics. Until then, the repository supports a falsifiable experiment but
does not claim that quality-selected data improves model training.
